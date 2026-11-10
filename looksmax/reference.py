"""Reference model built from SCUT-FBP5500 (5,500 faces rated 1-5 by 60 people).

Only derived statistics are stored (means, spreads, sorted metric values,
average face shapes, regression coefficients), never the images.

Build:  python -m looksmax.reference <images_dir> <All_labels.csv> [out.npz]
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LinearRegression

from .measure import (FaceMeasurer, align_to, asymmetry, mirror_pairs,
                      procrustes_distance, unit_shape)

DEFAULT_PATH = Path(__file__).parent / "data" / "reference.npz"
KEYS = ["M", "F", "AM", "CM", "AF", "CF"]   # sex, or ethnicity+sex
CONFOUNDS = ["yaw", "pitch", "roll", "mouth_open", "log_sharp"]


def confound_vector(m):
    """Photo-condition covariates. Turning left or right distorts a face the
    same way, so yaw and roll enter by magnitude; pitch has a curved effect."""
    return np.array([abs(m["yaw"]), m["yaw"] ** 2, m["pitch"], m["pitch"] ** 2,
                     abs(m["roll"]), m["mouth_open"], m["log_sharp"]])
STRUCTURAL = ["fwhr", "cheek_jaw", "jaw_width_ratio", "canthal_tilt",
              "eye_separation_ratio", "intercanthal_eye_ratio", "midface_ratio",
              "mid_lower_third", "chin_philtrum_ratio", "brow_eye_distance",
              "nose_width_ratio", "lip_height_ratio", "face_height_width",
              "skin_rough", "skin_uneven", "avg_dist", "asym", "masc"]
COMPONENTS = ["leanness", "dimorphism", "symmetry", "harmony", "skin"]


def components(z, sex):
    """Five rubric components from pose-adjusted, standardised metrics.
    Higher = better on every component."""
    typ = z["masc"] if sex == "M" else -z["masc"]
    return {
        "leanness": -(z["fwhr"] - z["cheek_jaw"]) / 2,
        "dimorphism": typ,
        "symmetry": -z["asym"],
        "harmony": -z["avg_dist"],
        "skin": -(z["skin_rough"] + z["skin_uneven"]) / 2,
    }


class Reference:
    def __init__(self, path=DEFAULT_PATH):
        d = np.load(path, allow_pickle=False)
        self.a = {k: d[k] for k in d.files}
        self.meta = json.loads(str(self.a.pop("meta")))
        self.pairs = self.a["pairs"]
        self.gpa_mean = self.a["gpa_mean"]

    # shape-derived metrics need the reference shapes
    def shape_metrics(self, shape, key):
        al = align_to(shape, self.gpa_mean).reshape(1, -1)
        pcs = (al - self.a["pca_mean"]) @ self.a["pca_components"].T
        masc = float(((pcs - self.a["lda_xbar"]) @ self.a["lda_scalings"])[0, 0]) * self.meta["masc_sign"]
        return {"avg_dist": procrustes_distance(shape, self.a[f"mean_shape_{key}"]),
                "asym": asymmetry(shape, self.pairs),
                "masc": masc}

    def adjust(self, metrics, key):
        """Remove the effect of head pose / expression / sharpness."""
        m = self.meta["keys"][key]
        c = confound_vector(metrics)
        out = {}
        for col in STRUCTURAL:
            b = np.array(m["pose_coef"][col])
            out[col] = metrics[col] - float(b @ (c - np.array(m["confound_mean"])))
        return out

    def zscores(self, adj, key):
        m = self.meta["keys"][key]
        return {c: (adj[c] - m["mean"][c]) / m["sd"][c] for c in STRUCTURAL}

    def percentile(self, name, value, key):
        dist = self.a[f"dist_{key}_{name}"]
        return float(np.searchsorted(dist, value) / len(dist) * 100)

    def assess(self, metrics, shape, sex, ethnicity=None):
        key = (ethnicity + sex) if ethnicity else sex
        metrics = {**metrics, **self.shape_metrics(shape, key)}
        adj = self.adjust(metrics, key)
        z = self.zscores(adj, key)
        comp = components(z, sex)
        m = self.meta["keys"][key]
        overall = m["overall_intercept"] + sum(m["overall_coef"][c] * comp[c] for c in COMPONENTS)
        return {
            "key": key, "n_reference": m["n"],
            "metrics": metrics, "adjusted": adj, "z": z,
            "components": {c: {"z": comp[c], "pct": self.percentile(c, comp[c], key)} for c in COMPONENTS},
            "metric_pct": {c: self.percentile(c, adj[c], key) for c in STRUCTURAL},
            "overall": {"value": overall, "pct": self.percentile("overall", overall, key),
                        "cv_r2": m["overall_cv_r2"], "coef": m["overall_coef"]},
            "rating_corr": m["rating_corr"], "rating_corr_adj": m["rating_corr_adj"],
            "pose_rating_corr": m["pose_rating_corr"],
            "median": {c: float(np.median(self.a[f"dist_{key}_{c}"])) for c in STRUCTURAL},
            "iqr": {c: [float(np.percentile(self.a[f"dist_{key}_{c}"], q)) for q in (25, 75)] for c in STRUCTURAL},
        }


# ------------------------------------------------------------------ build
def build(img_dir, labels_csv, out_path=DEFAULT_PATH):
    labels = pd.read_csv(labels_csv, header=None, names=["file", "rating"])
    paths = {p.name: p for p in Path(img_dir).rglob("*.jpg")}
    fm = FaceMeasurer()
    rows, shapes = [], []
    for i, r in enumerate(labels.itertuples()):
        res = fm.measure(cv2.imread(str(paths[r.file])))
        if res is None:
            continue
        metrics, shape, _ = res
        rows.append({**metrics, "file": r.file, "rating": r.rating,
                     "sex": r.file[1], "eth": r.file[0]})
        shapes.append(shape)
        if i % 1000 == 0:
            print(f"{i}/{len(labels)}", flush=True)
    fm.close()
    df = pd.DataFrame(rows)
    S = np.stack(shapes)

    # generalised Procrustes mean
    gpa = unit_shape(S[0])
    for _ in range(5):
        gpa = unit_shape(np.mean([align_to(s, gpa) for s in S], axis=0))
    aligned = np.stack([align_to(s, gpa) for s in S])
    pairs = mirror_pairs(gpa)

    flat = aligned.reshape(len(S), -1)
    pca = PCA(n_components=40, random_state=0).fit(flat)
    pcs = pca.transform(flat)
    lda = LinearDiscriminantAnalysis().fit(pcs, df.sex == "M")
    proj = ((pcs - lda.xbar_) @ lda.scalings_)[:, 0]
    sign = 1.0 if proj[df.sex.values == "M"].mean() > proj[df.sex.values == "F"].mean() else -1.0
    df["masc"] = proj * sign
    df["asym"] = [asymmetry(s, pairs) for s in S]

    arrays = {"pairs": pairs, "gpa_mean": gpa, "pca_mean": pca.mean_,
              "pca_components": pca.components_, "lda_xbar": lda.xbar_,
              "lda_scalings": lda.scalings_[:, :1]}
    meta = {"masc_sign": sign, "source": "SCUT-FBP5500", "keys": {}}

    for key in KEYS:
        sel = (df.sex == key[-1]) & ((df.eth == key[0]) if len(key) == 2 else True)
        sub = df[sel].copy()
        idx = np.where(sel)[0]
        mean_shape = unit_shape(aligned[idx].mean(0))
        arrays[f"mean_shape_{key}"] = mean_shape
        sub["avg_dist"] = [procrustes_distance(S[i], mean_shape) for i in idx]

        C = np.stack([confound_vector(r) for r in sub.to_dict("records")])
        coef, adj = {}, pd.DataFrame(index=sub.index)
        for col in STRUCTURAL:
            lr = LinearRegression().fit(C, sub[col].values)
            coef[col] = lr.coef_.tolist()
            adj[col] = sub[col].values - (C - C.mean(0)) @ lr.coef_
        mean, sd = adj.mean(), adj.std()
        z = (adj - mean) / sd
        comp = pd.DataFrame(components(z, key[-1]))
        rating_z = (sub.rating - sub.rating.mean()) / sub.rating.std()

        # data-derived weights for an overall structure index (pose-adjusted)
        lr = LinearRegression().fit(comp.values, rating_z.values)
        overall = lr.predict(comp.values)
        folds = np.arange(len(sub)) % 10
        pred = np.empty(len(sub))
        for f in range(10):
            tr, te = folds != f, folds == f
            pred[te] = LinearRegression().fit(comp.values[tr], rating_z.values[tr]).predict(comp.values[te])
        cv_r2 = 1 - ((rating_z.values - pred) ** 2).sum() / ((rating_z.values - rating_z.mean()) ** 2).sum()

        for col in STRUCTURAL:
            arrays[f"dist_{key}_{col}"] = np.sort(adj[col].values)
        for col in COMPONENTS:
            arrays[f"dist_{key}_{col}"] = np.sort(comp[col].values)
        arrays[f"dist_{key}_overall"] = np.sort(overall)

        meta["keys"][key] = {
            "n": int(len(sub)),
            "confound_mean": C.mean(0).tolist(), "pose_coef": coef,
            "mean": mean.to_dict(), "sd": sd.to_dict(),
            "overall_coef": dict(zip(COMPONENTS, lr.coef_.tolist())),
            "overall_intercept": float(lr.intercept_), "overall_cv_r2": float(cv_r2),
            "rating_corr": {c: float(np.corrcoef(sub[c], sub.rating)[0, 1]) for c in STRUCTURAL},
            "rating_corr_adj": {c: float(np.corrcoef(adj[c], sub.rating)[0, 1]) for c in STRUCTURAL},
            "pose_rating_corr": {c: float(np.corrcoef(sub[c].abs() if c in ("yaw", "roll") else sub[c],
                                                      sub.rating)[0, 1]) for c in CONFOUNDS},
        }
        print(f"{key}: n={len(sub)} overall CV R2={cv_r2:.3f}")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, meta=json.dumps(meta), **arrays)
    print(f"saved {out_path}")


if __name__ == "__main__":
    build(*sys.argv[1:4])
