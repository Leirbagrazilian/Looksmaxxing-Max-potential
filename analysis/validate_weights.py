"""Validate the proposed rubric weights against SCUT-FBP5500 ratings.

Usage:
    python analysis/validate_weights.py <features.csv> <out_dir>
(expects <features>.shapes.npy next to the CSV, written by extract_features.py)

Proposed weights being tested:
    harmony 30%, dimorphism 25%, adiposity 20%, skin 15%, symmetry 10%
"""

import itertools
import math
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold

PROPOSED = {"harmony": .30, "dimorphism": .25, "adiposity": .20,
            "skin": .15, "symmetry": .10}
COMPONENTS = list(PROPOSED)
CONFOUNDS = ["yaw", "pitch", "roll", "mouth_open", "mouth_w", "log_sharp"]


# ---------------------------------------------------------------- shape work
def procrustes_align(shapes, iters=5):
    """Generalised Procrustes analysis (2-D): remove position, scale, rotation."""
    X = shapes - shapes.mean(axis=1, keepdims=True)
    X /= np.linalg.norm(X, axis=(1, 2), keepdims=True)
    ref = X[0]
    for _ in range(iters):
        for i in range(len(X)):
            u, _, vt = np.linalg.svd(X[i].T @ ref)
            X[i] = X[i] @ (u @ vt)
        ref = X.mean(axis=0)
        ref /= np.linalg.norm(ref)
    return X


def mirror_pairs(mean_shape):
    """For each landmark, the index of its left/right counterpart."""
    mirrored = mean_shape * np.array([-1, 1])
    d = np.linalg.norm(mean_shape[:, None, :] - mirrored[None, :, :], axis=2)
    return d.argmin(axis=1)


def asymmetry(shape, pairs):
    """Procrustes residual between a face and its own mirror image."""
    m = (shape * np.array([-1, 1]))[pairs]
    a, b = shape - shape.mean(0), m - m.mean(0)
    u, _, vt = np.linalg.svd(b.T @ a)
    return np.linalg.norm(a - b @ (u @ vt)) / np.linalg.norm(a)


# ---------------------------------------------------------------- features
def zscore_within(df, cols, by):
    return df.groupby(by)[cols].transform(lambda s: (s - s.mean()) / s.std())


def build_components(df, shapes, control_photo):
    X = procrustes_align(shapes)
    df["group"] = df.ethnicity + df.sex

    # harmony = closeness to the average face of the same sex + ethnicity
    dist = np.empty(len(df))
    for g, idx in df.groupby("group").indices.items():
        dist[idx] = np.linalg.norm(X[idx] - X[idx].mean(0), axis=(1, 2))
    df["avg_dist"] = dist

    # dimorphism = position on the male<->female shape axis, signed so that
    # higher = more typical of the face's own sex (masculine men, feminine women)
    flat = X.reshape(len(X), -1)
    pcs = PCA(n_components=40, random_state=0).fit_transform(flat)
    lda = LinearDiscriminantAnalysis().fit(pcs, df.sex == "M")
    proj = lda.transform(pcs)[:, 0]
    if proj[df.sex.values == "M"].mean() < proj[df.sex.values == "F"].mean():
        proj = -proj
    df["masc_axis"] = proj
    df["sex_typicality"] = np.where(df.sex == "M", proj, -proj)

    # symmetry
    pairs = mirror_pairs(X.mean(0))
    df["asym"] = [asymmetry(s, pairs) for s in X]

    raw = ["avg_dist", "sex_typicality", "fwhr", "cheek_jaw", "perim_area",
           "skin_rough", "skin_uneven", "asym"]
    # Remove what head pose, expression and photo sharpness explain, so a
    # component measures the face rather than how the photo was taken.
    if control_photo:
        for g, idx in df.groupby("group").indices.items():
            C = df.iloc[idx][CONFOUNDS].values
            for col in raw:
                v = df[col].values[idx]
                df.loc[df.index[idx], col] = v - LinearRegression().fit(C, v).predict(C)
    z = zscore_within(df, raw + ["rating"], "group")
    out = pd.DataFrame({
        "harmony": -z.avg_dist,
        "dimorphism": z.sex_typicality,
        # Coetzee et al.: fuller faces have higher width/height and a lower
        # cheek-to-jaw ratio. Sign flipped so higher = leaner (better).
        "adiposity": -(z.fwhr - z.cheek_jaw) / 2,
        "skin": -(z.skin_rough + z.skin_uneven) / 2,
        "symmetry": -z.asym,
        "rating_z": z.rating,
    })
    out = (out - out.mean()) / out.std()      # every component on one scale
    detail = z.drop(columns="rating").add_prefix("z_")
    return pd.concat([df, out, detail], axis=1)


# ---------------------------------------------------------------- statistics
def r2(X, y):
    return LinearRegression().fit(X, y).score(X, y) if X.shape[1] else 0.0


def shapley_r2(df, cols, y):
    """Share of explained variance each predictor is responsible for."""
    n, out = len(cols), {}
    for c in cols:
        others, val = [k for k in cols if k != c], 0.0
        for k in range(n):
            for S in itertools.combinations(others, k):
                w = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
                val += w * (r2(df[list(S) + [c]].values, y) - r2(df[list(S)].values, y))
        out[c] = val
    return out


def cv_r2_fixed(df, weights, y, folds):
    """Out-of-sample R^2 of a fixed weighted sum (only scale+offset fitted)."""
    s = df[list(weights)].values @ np.array(list(weights.values()))
    pred = np.empty_like(y)
    for tr, te in folds:
        m = LinearRegression().fit(s[tr, None], y[tr])
        pred[te] = m.predict(s[te, None])
    return 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def cv_r2_fitted(df, cols, y, folds):
    pred = np.empty_like(y)
    for tr, te in folds:
        pred[te] = LinearRegression().fit(df[cols].values[tr], y[tr]).predict(df[cols].values[te])
    return 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def analyse(sub, label):
    y = sub.rating_z.values
    folds = list(KFold(10, shuffle=True, random_state=0).split(sub))
    ols = LinearRegression().fit(sub[COMPONENTS].values, y)
    shap = shapley_r2(sub, COMPONENTS, y)
    total = sum(shap.values())
    data_w = {c: max(shap[c], 0) / total for c in COMPONENTS}

    # top tier (~HTN and above, top 12%) vs everyone else
    top = sub.rating_z >= sub.rating_z.quantile(.88)
    tier_gap = {c: float(sub.loc[top, c].mean() - sub.loc[~top, c].mean()) for c in COMPONENTS}

    res = {
        "group": label, "n": int(len(sub)),
        "correlation": {c: float(np.corrcoef(sub[c], y)[0, 1]) for c in COMPONENTS},
        "std_beta": dict(zip(COMPONENTS, map(float, ols.coef_))),
        "shapley_r2": {c: float(v) for c, v in shap.items()},
        "data_weight": data_w,
        "proposed_weight": PROPOSED,
        "top12_minus_rest_sd": tier_gap,
        "cv_r2": {
            "proposed_weights": float(cv_r2_fixed(sub, PROPOSED, y, folds)),
            "equal_weights": float(cv_r2_fixed(sub, {c: .2 for c in COMPONENTS}, y, folds)),
            "fitted_weights": float(cv_r2_fitted(sub, COMPONENTS, y, folds)),
        },
        "photo_confound_correlation": {
            c: float(np.corrcoef(sub[c], y)[0, 1]) for c in CONFOUNDS},
        "subcomponent_correlation": {
            c: float(np.corrcoef(sub[c], y)[0, 1])
            for c in sub.columns if c.startswith("z_")},
    }
    return res


def main(features_csv, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(features_csv)
    shapes = np.load(Path(features_csv).with_suffix(".shapes.npy"))
    all_results = {}
    for mode, control in (("raw", False), ("pose_controlled", True)):
        print(f"\n################ {mode}")
        all_results[mode] = run(build_components(df.copy(), shapes, control))
    (out_dir / "results.json").write_text(json.dumps(all_results, indent=2))


def run(df):
    results = [analyse(df[df.sex == "M"].reset_index(drop=True), "male"),
               analyse(df[df.sex == "F"].reset_index(drop=True), "female")]
    for eth, name in (("A", "male_asian"), ("C", "male_caucasian")):
        results.append(analyse(df[(df.sex == "M") & (df.ethnicity == eth)].reset_index(drop=True), name))

    for r in results:
        print(f"\n=== {r['group']} (n={r['n']})")
        print(f"{'component':<12}{'r':>7}{'beta':>7}{'data_w':>8}{'prop_w':>8}{'top-gap':>9}")
        for c in COMPONENTS:
            print(f"{c:<12}{r['correlation'][c]:>7.2f}{r['std_beta'][c]:>7.2f}"
                  f"{r['data_weight'][c]:>8.0%}{PROPOSED[c]:>8.0%}{r['top12_minus_rest_sd'][c]:>9.2f}")
        print("CV R2:", {k: round(v, 3) for k, v in r["cv_r2"].items()})
        print("sub-measures r:", {k: round(v, 2) for k, v in r["subcomponent_correlation"].items()})
    return results


if __name__ == "__main__":
    main(*sys.argv[1:3])
