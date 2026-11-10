// Scoring + quest logic (browser port of looksmax/reference.py, report.py, daily.py).
// Rules and texts come from data/knowledge.json, exported from the Python package.

export const STRUCTURAL = ["fwhr", "cheek_jaw", "jaw_width_ratio", "canthal_tilt", "eye_separation_ratio",
  "intercanthal_eye_ratio", "midface_ratio", "mid_lower_third", "chin_philtrum_ratio", "brow_eye_distance",
  "nose_width_ratio", "lip_height_ratio", "face_height_width", "skin_rough", "skin_uneven", "avg_dist", "asym", "masc"];
export const COMPONENTS = ["leanness", "dimorphism", "symmetry", "harmony", "skin"];
const CONFOUNDS = ["yaw", "pitch", "roll", "mouth_open", "log_sharp"];

// ------------------------------------------------------------ shapes
function unit(s) {
  let mx = 0, my = 0;
  for (const [x, y] of s) { mx += x; my += y; }
  mx /= s.length; my /= s.length;
  const c = s.map(([x, y]) => [x - mx, y - my]);
  let n = 0;
  for (const [x, y] of c) n += x * x + y * y;
  n = Math.sqrt(n);
  return c.map(([x, y]) => [x / n, y / n]);
}
// Orthogonal Procrustes (same as numpy u @ vt: the orthogonal polar factor of s^T ref)
function alignTo(s, ref) {
  s = unit(s);
  let a = 0, b = 0, c = 0, d = 0;               // M = s^T ref
  for (let i = 0; i < s.length; i++) {
    a += s[i][0] * ref[i][0]; b += s[i][0] * ref[i][1];
    c += s[i][1] * ref[i][0]; d += s[i][1] * ref[i][1];
  }
  let R;
  if (a * d - b * c >= 0) { const n = Math.hypot(a + d, c - b); R = [[(a + d) / n, (b - c) / n], [(c - b) / n, (a + d) / n]]; }
  else { const n = Math.hypot(a - d, b + c); R = [[(a - d) / n, (b + c) / n], [(b + c) / n, (d - a) / n]]; }
  return s.map(([x, y]) => [x * R[0][0] + y * R[1][0], x * R[0][1] + y * R[1][1]]);
}
function procrustesDistance(s, ref) {
  const al = alignTo(s, ref);
  let t = 0;
  for (let i = 0; i < al.length; i++) t += (al[i][0] - ref[i][0]) ** 2 + (al[i][1] - ref[i][1]) ** 2;
  return Math.sqrt(t);
}
function asymmetry(shape, pairs) {
  const s = unit(shape);
  const m = unit(pairs.map((j) => [-s[j][0], s[j][1]]));
  return procrustesDistance(m, s);
}

// ------------------------------------------------------------ reference
export class Reference {
  constructor(json) { Object.assign(this, json); }

  shapeMetrics(shape, key) {
    const al = alignTo(shape, this.gpa_mean).flat();
    const pcs = this.pca_components.map((row) => row.reduce((s, w, i) => s + w * (al[i] - this.pca_mean[i]), 0));
    const masc = pcs.reduce((s, p, i) => s + (p - this.lda_xbar[i]) * this.lda_scalings[i][0], 0) * this.meta.masc_sign;
    return { avg_dist: procrustesDistance(shape, this[`mean_shape_${key}`]), asym: asymmetry(shape, this.pairs), masc };
  }

  confoundVector(m, bounds) {
    const v = {};
    for (const k of CONFOUNDS) v[k] = bounds && bounds[k] ? Math.min(Math.max(m[k], bounds[k][0]), bounds[k][1]) : m[k];
    return [Math.abs(v.yaw), v.yaw ** 2, v.pitch, v.pitch ** 2, Math.abs(v.roll), v.mouth_open, v.log_sharp];
  }

  percentile(name, value, key) {
    const q = this.dist[`${key}_${name}`], p = this.quantile_pcts;
    if (value <= q[0]) return 0;
    if (value >= q[q.length - 1]) return 100;
    let lo = 0, hi = q.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (q[mid] <= value) lo = mid; else hi = mid; }
    const f = q[hi] > q[lo] ? (value - q[lo]) / (q[hi] - q[lo]) : 0;
    return p[lo] + f * (p[hi] - p[lo]);
  }
  quantile(name, key, pct) {
    const q = this.dist[`${key}_${name}`];
    return q[Math.round(pct / 100 * (q.length - 1))];
  }

  assess(metrics, shape, sex, eth) {
    const key = eth ? eth + sex : sex;
    const m = this.meta.keys[key];
    metrics = { ...metrics, ...this.shapeMetrics(shape, key) };
    const c = this.confoundVector(metrics, m.confound_bounds);
    const adj = {}, z = {};
    for (const col of STRUCTURAL) {
      const b = m.pose_coef[col];
      adj[col] = metrics[col] - b.reduce((s, bi, i) => s + bi * (c[i] - m.confound_mean[i]), 0);
      z[col] = (adj[col] - m.mean[col]) / m.sd[col];
    }
    const typ = sex === "M" ? z.masc : -z.masc;
    const comp = {
      leanness: -(z.fwhr - z.cheek_jaw) / 2, dimorphism: typ, symmetry: -z.asym,
      harmony: -z.avg_dist, skin: -(z.skin_rough + z.skin_uneven) / 2,
    };
    const overall = m.overall_intercept + COMPONENTS.reduce((s, k) => s + m.overall_coef[k] * comp[k], 0);
    const out = {
      key, n_reference: m.n, metrics, adjusted: adj, components: {}, metric_pct: {}, iqr: {}, median: {},
      overall: { value: overall, pct: this.percentile("overall", overall, key), cv_r2: m.overall_cv_r2, coef: m.overall_coef },
      rating_corr_adj: m.rating_corr_adj, pose_rating_corr: m.pose_rating_corr,
    };
    for (const k of COMPONENTS) out.components[k] = { z: comp[k], pct: this.percentile(k, comp[k], key) };
    for (const k of STRUCTURAL) {
      out.metric_pct[k] = this.percentile(k, adj[k], key);
      out.iqr[k] = [this.quantile(k, key, 25), this.quantile(k, key, 75)];
      out.median[k] = this.quantile(k, key, 50);
    }
    return out;
  }
}

// ------------------------------------------------------------ report logic
export function photoWarnings(m) {
  const w = [];
  if (Math.abs(m.yaw) > 10) w.push(`Head turned ${Math.abs(m.yaw).toFixed(0)}° sideways. Face the camera straight on.`);
  if (Math.abs(m.roll) > 8) w.push(`Head tilted ${Math.abs(m.roll).toFixed(0)}° to the side. Keep it level.`);
  if (m.pitch < -8 || m.pitch > 15) w.push(`Head tilted ${m.pitch > 0 ? "down" : "up"} ${Math.abs(m.pitch).toFixed(0)}°. Keep it level for a reliable scan.`);
  if (m.mouth_open > 0.12) w.push("Mouth open. Use a neutral, closed-mouth expression.");
  return w;
}

export function flaggedMetrics(a, K) {
  const out = [];
  for (const [name, [label, area]] of Object.entries(K.metrics)) {
    const r = a.rating_corr_adj[name];
    if (Math.abs(r) < K.r_min) continue;
    const pct = a.metric_pct[name];
    const fav = r > 0 ? pct : 100 - pct;
    if (fav < 35) out.push({ name, label, area, r, fav });
  }
  return out.sort((x, y) => x.fav - y.fav);
}

export function priorityAreas(a, flags, K) {
  const change = { high: 1, medium: 0.6, low: 0.3 };
  const scores = new Map();
  for (const [c, v] of Object.entries(a.components)) {
    const gap = Math.max(0, 35 - v.pct) / 35;
    const w = Math.abs(a.overall.coef[c] ?? 0.05) + 0.05;
    scores.set(c, gap * w * change[K.area_actions[c].changeable]);
  }
  for (const f of flags) {
    const s = ((50 - f.fav) / 50) * Math.abs(f.r) * change[K.area_actions[f.area].changeable];
    scores.set(f.area, Math.max(scores.get(f.area) ?? 0, s));
  }
  return [...scores.entries()].filter(([, v]) => v > 0).sort((x, y) => y[1] - x[1]).map(([k]) => k);
}

// ------------------------------------------------------------ quests
export const weekday = (d) => (d.getDay() + 6) % 7;                 // Monday = 0, like Python
const ordinalDay = (d) => Math.round(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 864e5) + 719163;

export function planFor(day, priorities, sex, K) {
  const wd = weekday(day);
  return K.habits.filter((h) => h.days.includes(wd) && (!h.sex || h.sex === sex)
    && (!h.areas || h.areas.some((a) => priorities.includes(a))))
    .map((h) => ({ ...h, targeted: !!h.areas }));
}

export function tipFor(day, priorities, K) {
  const pool = [];
  for (const area of priorities.slice(0, 3)) {
    const info = K.area_actions[area];
    for (const [text, evidence, risk] of info.actions) pool.push({ title: info.title, text, evidence, risk });
  }
  for (const [name, evidence, risk, note] of K.lesser_known) pool.push({ title: "Lesser-known habit", text: `${name}. ${note}`, evidence, risk });
  for (const [text, evidence, risk] of K.presentation) pool.push({ title: "Presentation", text, evidence, risk });
  return pool[ordinalDay(day) % pool.length];
}

export function rankFor(xp, K) {
  let idx = 0;
  K.ranks.forEach(([floor], i) => { if (xp >= floor) idx = i; });
  const [floor, name] = K.ranks[idx], nxt = K.ranks[idx + 1];
  return { name, tier: idx + 1, xp, floor, next_name: nxt?.[1], next_at: nxt?.[0],
    progress: nxt ? (xp - floor) / (nxt[0] - floor) : 1 };
}

export function coachLine(plan, done, hasScan, isToday) {
  const left = plan.filter((h) => !done.has(h.id));
  if (!plan.length) return "Rest day. Nothing scheduled.";
  if (!left.length) return `All ${plan.length} quests cleared. +${plan.reduce((s, h) => s + h.xp, 0)} XP banked.`;
  if (isToday && !hasScan) return "Start with today's scan. It takes 10 seconds and tunes your quests.";
  if (left.length === plan.length) return `New day. Start with: ${left[0].label}.`;
  return `${plan.length - left.length} done, ${left.length} to go. Next: ${left[0].label}.`;
}

export const ordinal = (n) => {
  n = Math.round(n);
  const suf = n % 100 >= 10 && n % 100 <= 20 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
  return `${n}${suf}`;
};
