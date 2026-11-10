"""Measure one face photo: landmarks, head pose, structural ratios, skin.

Every number here is computed the same way for the user's photo and for the
5,500 rated reference faces, so the two can be compared directly.
"""

import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
             "face_landmarker/float16/1/face_landmarker.task")
MODEL_PATH = Path(os.environ.get("LOOKSMAX_MODEL",
                                 Path.home() / ".cache" / "looksmax" / "face_landmarker.task"))

# MediaPipe face-mesh landmark indices
R_IRIS, L_IRIS = 468, 473
R_EYE_OUT, R_EYE_IN, L_EYE_IN, L_EYE_OUT = 33, 133, 362, 263
R_LID_TOP, L_LID_TOP = 159, 386
R_BROW_MID, L_BROW_MID = 105, 334
ZYG_R, ZYG_L = 234, 454          # cheekbones (bizygomatic width)
GON_R, GON_L = 172, 397          # jaw angles (gonial width)
NASION, SUBNASALE, NOSE_TIP = 168, 2, 1
ALAR_R, ALAR_L = 48, 278
MID_BROW, FOREHEAD, CHIN = 9, 10, 152
LIP_TOP_OUTER, LIP_BOTTOM_OUTER = 0, 17
LIP_TOP, LIP_BOTTOM, MOUTH_R, MOUTH_L = 13, 14, 61, 291
SKIN_PATCHES = [(50, 0.18), (280, 0.18), (151, 0.18)]  # cheeks, forehead


def ensure_model():
    if not MODEL_PATH.exists():
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading face landmark model to {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return str(MODEL_PATH)


class FaceMeasurer:
    def __init__(self, model_path=None):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        self._mp = mp
        opts = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path or ensure_model()),
            num_faces=1, output_facial_transformation_matrixes=True)
        self._det = vision.FaceLandmarker.create_from_options(opts)

    def detect(self, img_bgr):
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        res = self._det.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb))
        if not res.face_landmarks:
            return None, None
        h, w = img_bgr.shape[:2]
        pts = np.array([[p.x * w, p.y * h] for p in res.face_landmarks[0]])
        return pts, head_pose(np.array(res.facial_transformation_matrixes[0]))

    def close(self):
        self._det.close()

    def measure(self, img_bgr):
        """Returns (metrics, eye-normalised 468x2 shape, landmarks in the crop, crop) or None.

        Every photo is first cropped and resized to the framing of the reference
        images (350x350, face ~63% of the height). Skin texture and sharpness
        depend on resolution, so this keeps a 12 MP phone photo comparable
        with the reference set."""
        pts, _ = self.detect(img_bgr)
        if pts is None:
            return None
        crop = standard_crop(img_bgr, pts)
        pts, pose = self.detect(crop)
        if pts is None:
            return None
        n = normalise(pts)
        return compute_metrics(crop, pts, n, pose), n[:468], pts, crop


REF_SIZE, REF_FACE_H, REF_CY = 350, 0.634, 0.56   # framing of the SCUT-FBP5500 images


def standard_crop(img, pts):
    """Square crop around the face, resized to the reference framing."""
    x0, y0 = pts.min(0)
    x1, y1 = pts.max(0)
    side = (y1 - y0) / REF_FACE_H
    cx = (x0 + x1) / 2
    top = (y0 + y1) / 2 - REF_CY * side
    src = np.float32([[cx - side / 2, top], [cx + side / 2, top], [cx - side / 2, top + side]])
    dst = np.float32([[0, 0], [REF_SIZE, 0], [0, REF_SIZE]])
    M = cv2.getAffineTransform(src, dst)
    interp = cv2.INTER_AREA if side > REF_SIZE else cv2.INTER_LINEAR
    return cv2.warpAffine(img, M, (REF_SIZE, REF_SIZE), flags=interp, borderMode=cv2.BORDER_REPLICATE)


def head_pose(m):
    """Yaw, pitch, roll in degrees from MediaPipe's 3-D face transform."""
    r = m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0)
    pitch = np.degrees(np.arctan2(r[2, 1], r[2, 2]))
    yaw = np.degrees(np.arcsin(-np.clip(r[2, 0], -1, 1)))
    roll = np.degrees(np.arctan2(r[1, 0], r[0, 0]))
    return yaw, pitch, roll


def normalise(pts):
    """Rotate so the eyes are level, scale so interpupillary distance = 1."""
    r, l = pts[R_IRIS], pts[L_IRIS]
    ang = np.arctan2(l[1] - r[1], l[0] - r[0])
    c, s = np.cos(-ang), np.sin(-ang)
    out = (pts - (r + l) / 2) @ np.array([[c, -s], [s, c]]).T
    return out / np.linalg.norm(l - r)


def _d(n, a, b):
    return float(np.linalg.norm(n[a] - n[b]))


def skin_measures(img_bgr, pts_px):
    iod = np.linalg.norm(pts_px[L_IRIS] - pts_px[R_IRIS])
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    rough, uneven = [], []
    for idx, frac in SKIN_PATCHES:
        cx, cy = pts_px[idx]
        hs = max(3, int(frac * iod))
        x0, x1 = int(max(0, cx - hs)), int(min(w, cx + hs))
        y0, y1 = int(max(0, cy - hs)), int(min(h, cy + hs))
        if x1 - x0 < 6 or y1 - y0 < 6:
            continue
        patch = lab[y0:y1, x0:x1]
        L = patch[:, :, 0]
        rough.append(np.std(L - cv2.GaussianBlur(L, (0, 0), 2)))
        uneven.append(np.std(patch[:, :, 1]) + np.std(patch[:, :, 2]))
    if not rough:
        return np.nan, np.nan
    return float(np.mean(rough)), float(np.mean(uneven))


def compute_metrics(img_bgr, pts, n, pose):
    bizyg = _d(n, ZYG_L, ZYG_R)
    jaw = _d(n, GON_L, GON_R)
    stomion = (n[LIP_TOP] + n[LIP_BOTTOM]) / 2

    def tilt(inner, outer):  # degrees; positive = outer corner higher
        dx = abs(n[outer, 0] - n[inner, 0])
        return np.degrees(np.arctan2(n[inner, 1] - n[outer, 1], dx))

    rough, uneven = skin_measures(img_bgr, pts)
    x0, y0 = np.maximum(pts.min(0).astype(int), 0)
    x1, y1 = pts.max(0).astype(int)
    grey = cv2.cvtColor(img_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    yaw, pitch, roll = pose

    return dict(
        # adiposity proxies (Coetzee et al. 2009)
        fwhr=bizyg / _d(n, LIP_TOP_OUTER, MID_BROW),
        cheek_jaw=bizyg / jaw,
        # structural ratios used by the community, measured on a frontal photo
        jaw_width_ratio=jaw / bizyg,
        canthal_tilt=(tilt(R_EYE_IN, R_EYE_OUT) + tilt(L_EYE_IN, L_EYE_OUT)) / 2,
        eye_separation_ratio=1.0 / bizyg,              # pupil distance / face width
        intercanthal_eye_ratio=_d(n, R_EYE_IN, L_EYE_IN) /
            ((_d(n, R_EYE_IN, R_EYE_OUT) + _d(n, L_EYE_IN, L_EYE_OUT)) / 2),
        midface_ratio=1.0 / (n[LIP_TOP_OUTER, 1] - 0.0),  # pupil distance / pupils-to-lip height
        mid_lower_third=(n[SUBNASALE, 1] - n[NASION, 1]) / (n[CHIN, 1] - n[SUBNASALE, 1]),
        chin_philtrum_ratio=(n[CHIN, 1] - stomion[1]) / (stomion[1] - n[SUBNASALE, 1]),
        brow_eye_distance=((n[R_LID_TOP, 1] - n[R_BROW_MID, 1]) +
                           (n[L_LID_TOP, 1] - n[L_BROW_MID, 1])) / 2,
        nose_width_ratio=_d(n, ALAR_R, ALAR_L) / _d(n, R_EYE_IN, L_EYE_IN),
        lip_height_ratio=_d(n, LIP_TOP_OUTER, LIP_BOTTOM_OUTER) / _d(n, MOUTH_R, MOUTH_L),
        face_height_width=(n[CHIN, 1] - n[FOREHEAD, 1]) / bizyg,
        # skin
        skin_rough=rough, skin_uneven=uneven,
        # photo conditions
        yaw=float(yaw), pitch=float(pitch), roll=float(roll),
        mouth_open=_d(n, LIP_TOP, LIP_BOTTOM),
        log_sharp=float(np.log(cv2.Laplacian(grey, cv2.CV_64F).var() + 1)),
        face_px=float(np.linalg.norm(pts[L_IRIS] - pts[R_IRIS])),
    )


# ------------------------------------------------------------ shape helpers
def unit_shape(s):
    s = s - s.mean(0)
    return s / np.linalg.norm(s)


def align_to(s, ref):
    """Orthogonal Procrustes: rotate unit-normalised s onto ref."""
    s = unit_shape(s)
    u, _, vt = np.linalg.svd(s.T @ ref)
    return s @ (u @ vt)


def procrustes_distance(s, ref):
    return float(np.linalg.norm(align_to(s, ref) - ref))


def mirror_pairs(mean_shape):
    mirrored = mean_shape * np.array([-1, 1])
    d = np.linalg.norm(mean_shape[:, None, :] - mirrored[None, :, :], axis=2)
    return d.argmin(axis=1)


def asymmetry(shape, pairs):
    s = unit_shape(shape)
    m = unit_shape((s * np.array([-1, 1]))[pairs])
    return procrustes_distance(m, s)
