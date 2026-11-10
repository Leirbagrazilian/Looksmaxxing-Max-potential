"""Extract facial-attractiveness features from SCUT-FBP5500 images.

Usage:
    python analysis/extract_features.py <images_dir> <labels_csv> <face_landmarker.task> <out_csv>

Each image gets 478 MediaPipe landmarks. From them (plus the pixels for skin)
we compute the five components of the proposed rubric:

  harmony      -> Procrustes distance to the mean face of the same sex+ethnicity
  dimorphism   -> projection on the male-vs-female shape axis (LDA)
  adiposity    -> facial adiposity proxies (Coetzee et al. 2009):
                  width-to-height ratio, cheek-to-jaw ratio, perimeter-to-area
  skin         -> texture roughness + colour unevenness on cheeks/forehead
  symmetry     -> mean left/right landmark mismatch after mirroring

Photo confounds (head yaw/pitch, mouth opening, smile width, sharpness) are
also recorded so they can be controlled for.

Raw per-face measurements go to the CSV; standardisation and modelling are
done in validate_weights.py.
"""

import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# MediaPipe face-mesh indices
R_IRIS, L_IRIS = 468, 473
ZYG_R, ZYG_L = 234, 454          # bizygomatic (cheekbone) width
GON_R, GON_L = 172, 397          # gonial (jaw angle) width
MID_BROW, UPPER_LIP, CHIN, FOREHEAD = 9, 0, 152, 10
NOSE_TIP, LIP_TOP, LIP_BOTTOM, MOUTH_R, MOUTH_L = 1, 13, 14, 61, 291
# lower-face outline from right cheekbone, round the jaw, to left cheekbone
LOWER_CONTOUR = [234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152,
                 377, 400, 378, 379, 365, 397, 288, 361, 323, 454]
# skin sample patches: (centre landmark, half-size as fraction of IOD)
SKIN_PATCHES = [(50, 0.18), (280, 0.18), (151, 0.18)]  # R cheek, L cheek, forehead


def load_detector(model_path):
    opts = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        num_faces=1,
        output_facial_transformation_matrixes=True)
    return vision.FaceLandmarker.create_from_options(opts)


def landmarks(detector, img_bgr):
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    res = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.face_landmarks:
        return None, None
    h, w = img_bgr.shape[:2]
    pts = np.array([[p.x * w, p.y * h] for p in res.face_landmarks[0]])
    return pts, head_pose(np.array(res.facial_transformation_matrixes[0]))


def head_pose(m):
    """Yaw, pitch, roll in degrees from MediaPipe's 3-D face transform."""
    r = m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0)
    pitch = np.degrees(np.arctan2(r[2, 1], r[2, 2]))
    yaw = np.degrees(np.arcsin(-np.clip(r[2, 0], -1, 1)))
    roll = np.degrees(np.arctan2(r[1, 0], r[0, 0]))
    return yaw, pitch, roll


def normalise(pts):
    """Rotate so the eyes are level, scale so interocular distance = 1."""
    r, l = pts[R_IRIS], pts[L_IRIS]
    ang = np.arctan2(l[1] - r[1], l[0] - r[0])
    c, s = np.cos(-ang), np.sin(-ang)
    rot = np.array([[c, -s], [s, c]])
    centre = (r + l) / 2
    out = (pts - centre) @ rot.T
    return out / np.linalg.norm(l - r)


def polygon_area_perimeter(poly):
    x, y = poly[:, 0], poly[:, 1]
    area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    perim = np.sum(np.linalg.norm(poly - np.roll(poly, 1, axis=0), axis=1))
    return area, perim


def skin_measures(img_bgr, pts_px):
    iod = np.linalg.norm(pts_px[L_IRIS] - pts_px[R_IRIS])
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    grey = lab[:, :, 0]
    rough, uneven = [], []
    h, w = grey.shape
    for idx, frac in SKIN_PATCHES:
        cx, cy = pts_px[idx]
        hs = max(3, int(frac * iod))
        x0, x1 = int(max(0, cx - hs)), int(min(w, cx + hs))
        y0, y1 = int(max(0, cy - hs)), int(min(h, cy + hs))
        if x1 - x0 < 6 or y1 - y0 < 6:
            continue
        patch_l = grey[y0:y1, x0:x1]
        # fine texture: residual after removing low-frequency shading
        rough.append(np.std(patch_l - cv2.GaussianBlur(patch_l, (0, 0), 2)))
        # colour unevenness: spread of a*/b* chroma (redness, blotches)
        patch = lab[y0:y1, x0:x1]
        uneven.append(np.std(patch[:, :, 1]) + np.std(patch[:, :, 2]))
    if not rough:
        return np.nan, np.nan
    return float(np.mean(rough)), float(np.mean(uneven))


def main(img_dir, labels_csv, model_path, out_csv):
    labels = pd.read_csv(labels_csv, header=None, names=["file", "rating"])
    paths = {p.name: p for p in Path(img_dir).rglob("*.jpg")}
    det = load_detector(model_path)

    rows, shapes = [], []
    for i, r in enumerate(labels.itertuples()):
        img = cv2.imread(str(paths[r.file]))
        pts, pose = landmarks(det, img)
        if pts is None:
            continue
        n = normalise(pts)
        bizyg = np.linalg.norm(n[ZYG_L] - n[ZYG_R])
        jaw = np.linalg.norm(n[GON_L] - n[GON_R])
        upper_h = np.linalg.norm(n[UPPER_LIP] - n[MID_BROW])
        face_h = np.linalg.norm(n[CHIN] - n[FOREHEAD])
        area, perim = polygon_area_perimeter(n[LOWER_CONTOUR])
        rough, uneven = skin_measures(img, pts)
        # photo confounds: head turn, head tilt up/down, expression, sharpness
        yaw, pitch, roll = pose
        midface = n[NOSE_TIP, 1] / (n[CHIN, 1] - n[FOREHEAD, 1])
        mouth_open = np.linalg.norm(n[LIP_TOP] - n[LIP_BOTTOM])
        mouth_w = np.linalg.norm(n[MOUTH_L] - n[MOUTH_R])
        x0, y0 = np.maximum(pts.min(0).astype(int), 0)
        x1, y1 = pts.max(0).astype(int)
        face_grey = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        sharp = cv2.Laplacian(face_grey, cv2.CV_64F).var()
        rows.append(dict(
            file=r.file, rating=r.rating,
            sex=r.file[1], ethnicity=r.file[0],   # e.g. AM = Asian Male
            fwhr=bizyg / upper_h,
            cheek_jaw=bizyg / jaw,
            perim_area=perim / np.sqrt(area),
            jaw_face_w=jaw / bizyg,
            face_h_w=face_h / bizyg,
            skin_rough=rough, skin_uneven=uneven,
            midface_2d=midface,
            yaw=abs(yaw), pitch=pitch, roll=abs(roll), mouth_open=mouth_open,
            mouth_w=mouth_w, log_sharp=np.log(sharp + 1)))
        shapes.append(n[:468])
        if i % 500 == 0:
            print(f"{i}/{len(labels)}", flush=True)

    df = pd.DataFrame(rows)
    np.save(Path(out_csv).with_suffix(".shapes.npy"), np.stack(shapes))
    df.to_csv(out_csv, index=False)
    print(f"done: {len(df)} faces with landmarks out of {len(labels)}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
