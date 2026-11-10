// On-device face measurement (browser port of looksmax/measure.py).
// The reference model for the web app is built by running THIS file over the
// 5,500 reference images, so phone scans and reference use identical code.
import { FaceLandmarker, FilesetResolver } from "../vendor/vision_bundle.mjs";

// MediaPipe face-mesh landmark indices
const R_IRIS = 468, L_IRIS = 473;
const R_EYE_OUT = 33, R_EYE_IN = 133, L_EYE_IN = 362, L_EYE_OUT = 263;
const R_LID_TOP = 159, L_LID_TOP = 386, R_BROW_MID = 105, L_BROW_MID = 334;
const ZYG_R = 234, ZYG_L = 454, GON_R = 172, GON_L = 397;
const NASION = 168, SUBNASALE = 2, ALAR_R = 48, ALAR_L = 278;
const MID_BROW = 9, FOREHEAD = 10, CHIN = 152;
const LIP_TOP_OUTER = 0, LIP_BOTTOM_OUTER = 17, LIP_TOP = 13, LIP_BOTTOM = 14, MOUTH_R = 61, MOUTH_L = 291;
const SKIN_PATCHES = [[50, 0.18], [280, 0.18], [151, 0.18]];
export const LM = { ZYG_R, ZYG_L, GON_R, GON_L, R_EYE_IN, R_EYE_OUT, L_EYE_IN, L_EYE_OUT,
  R_BROW_MID, R_LID_TOP, L_BROW_MID, L_LID_TOP, NASION, SUBNASALE, CHIN, ALAR_R, ALAR_L };

const REF_SIZE = 350, REF_FACE_H = 0.634, REF_CY = 0.56;

export async function createMeasurer(base = "./") {
  const fileset = await FilesetResolver.forVisionTasks(base + "vendor/wasm");
  const fl = await FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: base + "models/face_landmarker.task", delegate: "CPU" },
    runningMode: "IMAGE", numFaces: 1, outputFacialTransformationMatrixes: true,
  });
  return {
    measure: (src) => measure(fl, src),
    close: () => fl.close(),
  };
}

function detect(fl, canvas) {
  const res = fl.detect(canvas);
  if (!res.faceLandmarks || !res.faceLandmarks.length) return null;
  const w = canvas.width, h = canvas.height;
  const pts = res.faceLandmarks[0].map((p) => [p.x * w, p.y * h]);
  return { pts, pose: headPose(res.facialTransformationMatrixes[0]) };
}

function headPose(mat) {
  // 4x4 rigid transform; detect storage order from where the translation sits
  const d = mat.data;
  const colMajor = Math.abs(d[14]) > Math.abs(d[11]);
  const m = (r, c) => (colMajor ? d[c * 4 + r] : d[r * 4 + c]);
  const col = (c) => Math.hypot(m(0, c), m(1, c), m(2, c));
  const r = (i, j) => m(i, j) / col(j);
  const deg = 180 / Math.PI;
  return [
    Math.asin(-Math.max(-1, Math.min(1, r(2, 0)))) * deg, // yaw
    Math.atan2(r(2, 1), r(2, 2)) * deg,                    // pitch
    Math.atan2(r(1, 0), r(0, 0)) * deg,                    // roll
  ];
}

function makeCanvas(w, h) {
  const c = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(w, h) : Object.assign(document.createElement("canvas"), { width: w, height: h });
  return c;
}

// Draw any image source into a canvas no larger than maxSide, halving in
// steps so large phone photos downscale smoothly.
export function toCanvas(src, maxSide = 1600) {
  let w = src.width || src.naturalWidth, h = src.height || src.naturalHeight;
  let cur = src, cw = w, ch = h;
  while (Math.max(cw, ch) / 2 >= maxSide) {
    const c = makeCanvas(Math.round(cw / 2), Math.round(ch / 2));
    const ctx = c.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(cur, 0, 0, c.width, c.height);
    cur = c; cw = c.width; ch = c.height;
  }
  const s = Math.min(1, maxSide / Math.max(cw, ch));
  const out = makeCanvas(Math.round(cw * s), Math.round(ch * s));
  const ctx = out.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(cur, 0, 0, out.width, out.height);
  return out;
}

// Square crop around the face, resized to the reference framing (350x350).
function standardCrop(canvas, pts) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
  const side = (y1 - y0) / REF_FACE_H;
  const cx = (x0 + x1) / 2, top = (y0 + y1) / 2 - REF_CY * side;
  // pre-shrink so the final draw scales by < 2x (keeps resampling smooth)
  let src = canvas, scale = 1;
  while (side * scale / 2 >= REF_SIZE) {
    const c = makeCanvas(Math.max(1, Math.round(src.width / 2)), Math.max(1, Math.round(src.height / 2)));
    const ctx = c.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(src, 0, 0, c.width, c.height);
    scale *= c.width / src.width; src = c;
  }
  const out = makeCanvas(REF_SIZE, REF_SIZE);
  const ctx = out.getContext("2d");
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, REF_SIZE, REF_SIZE);
  ctx.imageSmoothingQuality = "high";
  const k = REF_SIZE / (side * scale);
  ctx.setTransform(k, 0, 0, k, -(cx - side / 2) * scale * k, -top * scale * k);
  ctx.drawImage(src, 0, 0);
  return out;
}

async function measure(fl, src) {
  const canvas = src instanceof HTMLCanvasElement || (typeof OffscreenCanvas !== "undefined" && src instanceof OffscreenCanvas) ? src : toCanvas(src);
  const first = detect(fl, canvas);
  if (!first) return null;
  const crop = standardCrop(canvas, first.pts);
  const det = detect(fl, crop);
  if (!det) return null;
  const n = normalise(det.pts);
  const img = crop.getContext("2d").getImageData(0, 0, REF_SIZE, REF_SIZE);
  return { metrics: computeMetrics(img, det.pts, n, det.pose), shape: n.slice(0, 468), pts: det.pts, crop };
}

// ------------------------------------------------------------ geometry
function normalise(pts) {
  const r = pts[R_IRIS], l = pts[L_IRIS];
  const ang = Math.atan2(l[1] - r[1], l[0] - r[0]);
  const c = Math.cos(-ang), s = Math.sin(-ang);
  const cx = (r[0] + l[0]) / 2, cy = (r[1] + l[1]) / 2;
  const d = Math.hypot(l[0] - r[0], l[1] - r[1]);
  return pts.map(([x, y]) => {
    const dx = x - cx, dy = y - cy;
    return [(c * dx - s * dy) / d, (s * dx + c * dy) / d];
  });
}
const dist = (n, a, b) => Math.hypot(n[a][0] - n[b][0], n[a][1] - n[b][1]);

function computeMetrics(img, pts, n, pose) {
  const bizyg = dist(n, ZYG_L, ZYG_R), jaw = dist(n, GON_L, GON_R);
  const stomionY = (n[LIP_TOP][1] + n[LIP_BOTTOM][1]) / 2;
  const tilt = (inner, outer) => Math.atan2(n[inner][1] - n[outer][1], Math.abs(n[outer][0] - n[inner][0])) * 180 / Math.PI;
  const [rough, uneven] = skinMeasures(img, pts);
  const [yaw, pitch, roll] = pose;
  return {
    fwhr: bizyg / dist(n, LIP_TOP_OUTER, MID_BROW),
    cheek_jaw: bizyg / jaw,
    jaw_width_ratio: jaw / bizyg,
    canthal_tilt: (tilt(R_EYE_IN, R_EYE_OUT) + tilt(L_EYE_IN, L_EYE_OUT)) / 2,
    eye_separation_ratio: 1 / bizyg,
    intercanthal_eye_ratio: dist(n, R_EYE_IN, L_EYE_IN) / ((dist(n, R_EYE_IN, R_EYE_OUT) + dist(n, L_EYE_IN, L_EYE_OUT)) / 2),
    midface_ratio: 1 / n[LIP_TOP_OUTER][1],
    mid_lower_third: (n[SUBNASALE][1] - n[NASION][1]) / (n[CHIN][1] - n[SUBNASALE][1]),
    chin_philtrum_ratio: (n[CHIN][1] - stomionY) / (stomionY - n[SUBNASALE][1]),
    brow_eye_distance: ((n[R_LID_TOP][1] - n[R_BROW_MID][1]) + (n[L_LID_TOP][1] - n[L_BROW_MID][1])) / 2,
    nose_width_ratio: dist(n, ALAR_R, ALAR_L) / dist(n, R_EYE_IN, L_EYE_IN),
    lip_height_ratio: dist(n, LIP_TOP_OUTER, LIP_BOTTOM_OUTER) / dist(n, MOUTH_R, MOUTH_L),
    face_height_width: (n[CHIN][1] - n[FOREHEAD][1]) / bizyg,
    skin_rough: rough, skin_uneven: uneven,
    yaw, pitch, roll,
    mouth_open: dist(n, LIP_TOP, LIP_BOTTOM),
    log_sharp: Math.log(laplacianVar(img, pts) + 1),
    face_px: Math.hypot(pts[L_IRIS][0] - pts[R_IRIS][0], pts[L_IRIS][1] - pts[R_IRIS][1]),
  };
}

// ------------------------------------------------------------ pixels
const srgbLin = new Float64Array(256).map((_, i) => { const v = i / 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
function lab(r, g, b) {
  const R = srgbLin[r], G = srgbLin[g], B = srgbLin[b];
  const X = (0.412453 * R + 0.357580 * G + 0.180423 * B) / 0.950456;
  const Y = 0.212671 * R + 0.715160 * G + 0.072169 * B;
  const Z = (0.019334 * R + 0.119193 * G + 0.950227 * B) / 1.088754;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  const fx = f(X), fy = f(Y), fz = f(Z);
  const L = Y > 0.008856 ? 116 * fy - 16 : 903.3 * Y;
  return [L * 255 / 100, 500 * (fx - fy) + 128, 200 * (fy - fz) + 128];
}

const reflect101 = (i, n) => (n === 1 ? 0 : i < 0 ? -i : i >= n ? 2 * n - 2 - i : i);
function gaussianBlur(a, w, h, sigma) {
  const k = Math.round(sigma * 8 + 1) | 1, half = k >> 1, ker = [];
  let sum = 0;
  for (let i = 0; i < k; i++) { const x = i - half; ker.push(Math.exp(-(x * x) / (2 * sigma * sigma))); sum += ker[i]; }
  for (let i = 0; i < k; i++) ker[i] /= sum;
  const tmp = new Float64Array(w * h), out = new Float64Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let s = 0;
    for (let i = 0; i < k; i++) s += ker[i] * a[y * w + reflect101(x + i - half, w)];
    tmp[y * w + x] = s;
  }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let s = 0;
    for (let i = 0; i < k; i++) s += ker[i] * tmp[reflect101(y + i - half, h) * w + x];
    out[y * w + x] = s;
  }
  return out;
}
const std = (arr) => { let m = 0; for (const v of arr) m += v; m /= arr.length; let s = 0; for (const v of arr) s += (v - m) ** 2; return Math.sqrt(s / arr.length); };

function skinMeasures(img, pts) {
  const iod = Math.hypot(pts[L_IRIS][0] - pts[R_IRIS][0], pts[L_IRIS][1] - pts[R_IRIS][1]);
  const { width: W, height: H, data } = img;
  const rough = [], uneven = [];
  for (const [idx, frac] of SKIN_PATCHES) {
    const [cx, cy] = pts[idx];
    const hs = Math.max(3, Math.trunc(frac * iod));
    const x0 = Math.trunc(Math.max(0, cx - hs)), x1 = Math.trunc(Math.min(W, cx + hs));
    const y0 = Math.trunc(Math.max(0, cy - hs)), y1 = Math.trunc(Math.min(H, cy + hs));
    const w = x1 - x0, h = y1 - y0;
    if (w < 6 || h < 6) continue;
    const L = new Float64Array(w * h), A = new Float64Array(w * h), B = new Float64Array(w * h);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const o = ((y0 + y) * W + x0 + x) * 4;
      const [l, a, b] = lab(data[o], data[o + 1], data[o + 2]);
      L[y * w + x] = l; A[y * w + x] = a; B[y * w + x] = b;
    }
    const bl = gaussianBlur(L, w, h, 2);
    rough.push(std(L.map((v, i) => v - bl[i])));
    uneven.push(std(A) + std(B));
  }
  if (!rough.length) return [NaN, NaN];
  return [rough.reduce((a, b) => a + b) / rough.length, uneven.reduce((a, b) => a + b) / uneven.length];
}

function laplacianVar(img, pts) {
  const { width: W, data } = img;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
  x0 = Math.max(0, Math.trunc(x0)); y0 = Math.max(0, Math.trunc(y0));
  x1 = Math.min(W, Math.trunc(x1)); y1 = Math.min(img.height, Math.trunc(y1));
  const w = x1 - x0, h = y1 - y0;
  if (w < 3 || h < 3) return 0;
  const g = new Float64Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const o = ((y0 + y) * W + x0 + x) * 4;
    g[y * w + x] = Math.round(0.299 * data[o] + 0.587 * data[o + 1] + 0.114 * data[o + 2]);
  }
  const lap = new Float64Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const c = g[y * w + x];
    lap[y * w + x] = g[y * w + reflect101(x - 1, w)] + g[y * w + reflect101(x + 1, w)]
      + g[reflect101(y - 1, h) * w + x] + g[reflect101(y + 1, h) * w + x] - 4 * c;
  }
  return std(lap) ** 2;
}

// Draw landmark guide lines on the standard crop (for the breakdown view).
export function annotate(crop, pts) {
  const out = makeCanvas(crop.width, crop.height);
  const ctx = out.getContext("2d");
  ctx.drawImage(crop, 0, 0);
  const lines = [[[ZYG_R, ZYG_L], "#ffc800"], [[GON_R, GON_L], "#ff8c00"], [[R_EYE_IN, R_EYE_OUT], "#00c8ff"],
    [[L_EYE_IN, L_EYE_OUT], "#00c8ff"], [[R_BROW_MID, R_LID_TOP], "#00ffc8"], [[L_BROW_MID, L_LID_TOP], "#00ffc8"],
    [[NASION, SUBNASALE], "#ff78b4"], [[SUBNASALE, CHIN], "#b478ff"], [[ALAR_R, ALAR_L], "#b4ff78"], [[R_EYE_IN, L_EYE_IN], "#ffffff"]];
  ctx.lineWidth = 1.2;
  for (const [[a, b], col] of lines) { ctx.strokeStyle = col; ctx.beginPath(); ctx.moveTo(...pts[a]); ctx.lineTo(...pts[b]); ctx.stroke(); }
  ctx.fillStyle = "rgba(230,230,230,.8)";
  for (let i = 0; i < 468; i += 3) { ctx.beginPath(); ctx.arc(pts[i][0], pts[i][1], 0.8, 0, 7); ctx.fill(); }
  return out;
}
