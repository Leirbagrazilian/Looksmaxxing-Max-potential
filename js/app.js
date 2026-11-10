// Ascend web app: routing, views and interactions. Everything runs on-device.
import { store } from "./store.js";
import { Reference, photoWarnings, flaggedMetrics, priorityAreas, planFor, tipFor, rankFor,
  coachLine, ordinal, COMPONENTS } from "./logic.js";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const fromIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const fmt = (d, o) => d.toLocaleDateString("en-US", o);
const round = (x) => Math.round(x);

let K, REF, measurerP = null, urls = [];
const view = () => $("#view");

// ---------------------------------------------------------------- boot
async function boot() {
  [K, REF] = await Promise.all([
    fetch("data/knowledge.json").then((r) => r.json()),
    fetch("data/reference.json").then((r) => r.json()).then((j) => new Reference(j)),
  ]);
  K.habitById = Object.fromEntries(K.habits.map((h) => [h.id, h]));
  window.addEventListener("hashchange", route);
  document.addEventListener("click", onClick);
  document.addEventListener("change", onChange);
  route();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
}

function ensureMeasurer() {
  measurerP ??= import("./measure.js").then((m) => m.createMeasurer("./"));
  return measurerP;
}

// ---------------------------------------------------------------- routing
async function route() {
  urls.forEach(URL.revokeObjectURL); urls = [];
  const [path, qs] = (location.hash.slice(1) || "/").split("?");
  const q = new URLSearchParams(qs);
  const settings = await store.settings();
  const parts = path.split("/").filter(Boolean);
  const name = parts[0] || "quests";
  if (!settings.sex && name !== "profile") return (location.hash = "#/profile?setup=1");
  const today = new Date();
  let day = q.get("d") ? fromIso(q.get("d")) : today;
  if (day > today) day = today;
  const views = { quests: viewQuests, scan: viewScan, report: viewReport, progress: viewProgress, profile: viewProfile };
  await chrome(name);
  await (views[name] || viewQuests)({ day, q, settings, parts });
  window.scrollTo(0, 0);
}

async function chrome(active) {
  const xp = (await store.habitLog()).reduce((s, r) => s + (K.habitById[r.habit]?.xp || 0), 0);
  const rank = rankFor(xp, K);
  const chip = $(".rankchip");
  chip.title = `${xp} XP`;
  $(".tier", chip).textContent = rank.tier;
  $(".rname", chip).textContent = rank.name;
  $("b", chip).style.setProperty("--p", round(100 * rank.progress) + "%");
  const map = { quests: "quests", scan: "scan", report: "scan", progress: "progress", profile: "profile" };
  $$(".tabs a").forEach((a) => a.classList.toggle("on", a.dataset.tab === map[active]));
  return rank;
}

function blobUrl(b) { if (!b) return ""; const u = URL.createObjectURL(b); urls.push(u); return u; }

async function prioritiesFor(dayIso, all) {
  const c = all ? all.filter((x) => x.day <= dayIso && x.assessment).pop() : await store.latestCheckin(dayIso);
  if (!c) return [];
  return priorityAreas(c.assessment, flaggedMetrics(c.assessment, K), K);
}
const shortTitle = (area) => K.area_actions[area].title.split(" (")[0];

// ---------------------------------------------------------------- quests
async function viewQuests({ day, settings }) {
  const ds = iso(day), isToday = ds === iso(new Date());
  const prios = await prioritiesFor(ds);
  const plan = planFor(day, prios, settings.sex, K);
  const done = await store.habitsDone(ds);
  const checkin = await store.checkin(ds);
  const nDone = plan.filter((h) => done.has(h.id)).length;
  const pct = plan.length ? round((100 * nDone) / plan.length) : 0;
  const hour = new Date().getHours();
  const slotNow = !isToday ? "morning" : hour < 11 ? "morning" : hour < 18 ? "day" : "evening";
  const tip = tipFor(day, prios, K);
  const next = isToday ? null : iso(addDays(day, 1));

  view().innerHTML = `
  <div class="daynav">
    <a href="#/?d=${iso(addDays(day, -1))}" aria-label="Previous day">‹</a>
    <div><h1>${isToday ? "Today" : fmt(day, { weekday: "short", month: "short", day: "numeric" })}</h1>
      <p class="sub">${isToday ? fmt(day, { weekday: "long", month: "long", day: "numeric" }) : "Filling in a past day"}</p></div>
    ${next ? `<a href="#/?d=${next}" aria-label="Next day">›</a>` : "<span></span>"}
  </div>
  <section class="hero card">
    <div class="ring" id="ring" style="--p:${pct}">
      <svg viewBox="0 0 36 36"><circle class="track" cx="18" cy="18" r="15.9"/><circle class="fill" cx="18" cy="18" r="15.9" pathLength="100"/></svg>
      <div><b id="count">${nDone}</b><span>/ ${plan.length}</span></div>
    </div>
    <div class="hero-text">
      <p class="coach" id="coach">${esc(coachLine(plan, done, !!checkin, isToday))}</p>
      <p class="xp"><span class="gold" id="xp-today">+${plan.filter((h) => done.has(h.id)).reduce((s, h) => s + h.xp, 0)}</span> / ${plan.reduce((s, h) => s + h.xp, 0)} XP today</p>
      ${isToday && !done.has("photo") ? `<a class="btn sm" href="#/scan">Scan now</a>` : ""}
    </div>
  </section>
  ${prios.length ? `<p class="focusline">Tuned for: ${prios.slice(0, 2).map((p) => `<span class="chip">${esc(shortTitle(p))}</span>`).join("")}</p>` : ""}
  <section class="card quests" data-day="${ds}">
    <div class="seg" role="tablist">
      ${K.slots.map(([key, label]) => {
        const items = plan.filter((h) => h.slot === key);
        return `<button role="tab" data-slot="${key}" class="${key === slotNow ? "on" : ""}" ${items.length ? "" : "disabled"}>${label} <small data-count="${key}">${items.filter((h) => done.has(h.id)).length}/${items.length}</small></button>`;
      }).join("")}
    </div>
    ${K.slots.map(([key]) => {
      const items = plan.filter((h) => h.slot === key);
      return `<ul class="checklist" data-slot="${key}" ${key === slotNow ? "" : "hidden"}>
        ${items.map((h) => `
        <li class="${done.has(h.id) ? "done" : ""}">
          <label>
            <input type="checkbox" data-habit="${h.id}" data-xp="${h.xp}" ${done.has(h.id) ? "checked" : ""} ${h.id === "photo" ? "disabled" : ""}>
            <span class="lbl">${esc(h.label)}${h.targeted ? ' <i class="tag">for you</i>' : ""}</span>
            <span class="xp-pill">+${h.xp}</span>
          </label>
          ${h.note ? `<details><summary aria-label="Why"></summary><p>${esc(h.note)}${h.evidence !== "-" ? ` <span class="ev">Evidence: ${h.evidence}</span>` : ""}</p></details>` : ""}
        </li>`).join("") || '<li class="empty">Nothing in this block today.</li>'}
      </ul>`;
    }).join("")}
  </section>
  <details class="card tip">
    <summary><span class="eyebrow">Today's focus · ${esc(tip.title.split(" (")[0])}</span><span class="tip-short">${esc(tip.text.split(". ")[0].split(": ")[0])}</span></summary>
    <p>${esc(tip.text)}</p>
    <p class="meta">Evidence: ${tip.evidence} · Risk: ${tip.risk}</p>
  </details>`;
  // if the slot for now is empty, open the first non-empty one
  const on = $(".seg button.on");
  if (!on || on.disabled) $(".seg button:not([disabled])")?.click();
}

async function toggleHabit(box) {
  const q = box.closest(".quests"), day = q.dataset.day;
  box.closest("li").classList.toggle("done", box.checked);
  await store.setHabit(day, box.dataset.habit, box.checked);
  const boxes = $$("input[type=checkbox]", q), done = boxes.filter((b) => b.checked);
  $("#count").textContent = done.length;
  $("#ring").style.setProperty("--p", boxes.length ? round((100 * done.length) / boxes.length) : 0);
  $("#xp-today").textContent = "+" + done.reduce((s, b) => s + +b.dataset.xp, 0);
  $$("[data-count]").forEach((c) => {
    const l = $$(`.checklist[data-slot="${c.dataset.count}"] input`);
    c.textContent = `${l.filter((b) => b.checked).length}/${l.length}`;
  });
  const left = boxes.filter((b) => !b.checked);
  $("#coach").textContent = !left.length ? `All ${boxes.length} quests cleared. Nice work.`
    : `${done.length} done, ${left.length} to go. Next: ${$(".lbl", left[0].closest("label")).firstChild.textContent.trim()}.`;
  const before = $(".rname").textContent;
  const rank = await chrome("quests");
  if (box.checked) toast(rank.name !== before ? `🏆 Rank up: ${rank.name}` : `<span class="gold">+${box.dataset.xp} XP</span>${left.length ? "Quest cleared" : "All quests cleared"}`);
}

// ---------------------------------------------------------------- scan
const UPLOAD = (ds) => `
  <label class="file" id="pick">
    <input type="file" accept="image/*" data-day="${ds}" id="photo-input">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>
    <span>Take or choose a photo</span>
  </label>
  <p class="status" id="scan-status" hidden></p>`;

async function viewScan({ day, settings }) {
  const ds = iso(day), isToday = ds === iso(new Date());
  ensureMeasurer().catch(() => {});                       // start loading the model now
  const c = await store.checkin(ds);
  let html = `<h1>Scan${isToday ? "" : ` <small class="sub">${fmt(day, { month: "short", day: "numeric" })}</small>`}</h1>`;
  if (c?.assessment) {
    const a = c.assessment;
    const prios = priorityAreas(a, flaggedMetrics(a, K), K);
    const plan = planFor(day, prios, settings.sex, K);
    const top = prios[0];
    html += `
    <section class="card result">
      <img class="thumb" src="${blobUrl(c.photo)}" alt="Your scan">
      <div><p class="eyebrow">Structure index</p>
        <p class="big">${round(a.overall.pct)}<small>${ordinal(a.overall.pct)} pct</small></p>
        <p class="sub">vs ${a.n_reference.toLocaleString("en-US")} rated faces</p></div>
    </section>
    ${top ? `<section class="card callout">
      <p class="eyebrow">Your biggest lever</p><h2>${esc(shortTitle(top))}</h2>
      <p>${esc(K.area_actions[top].why.split(". ")[0])}.</p>
      <a class="btn sm" href="#/?d=${ds}">${plan.filter((h) => h.targeted).length} quests target this →</a></section>` : ""}
    <section class="card">
      <ul class="bars">${COMPONENTS.map((k) => `<li><span>${K.comp_label[k]}</span><b style="--p:${round(a.components[k].pct)}%"></b><em>${round(a.components[k].pct)}</em></li>`).join("")}</ul>
      ${(c.warnings || []).map((w) => `<p class="warn">${esc(w)}</p>`).join("")}
      <a class="btn ghost" href="#/report/${ds}">Full breakdown →</a>
    </section>
    <details class="card"><summary>Retake scan</summary>${UPLOAD(ds)}</details>`;
  } else {
    html += `
    <section class="card">
      ${c ? (c.warnings || []).map((w) => `<p class="warn">${esc(w)}</p>`).join("") : `<p class="lead">One photo a day. Same setup every time, so changes reflect you, not the camera.</p>`}
      <ul class="howto">
        <li><b>1.5 m</b><span>Phone at arm's length or more. Close selfies inflate the nose.</span></li>
        <li><b>Level</b><span>Look straight into the lens, head level, neutral face.</span></li>
        <li><b>Light</b><span>Face a window. No overhead light or flash.</span></li>
      </ul>
      ${UPLOAD(ds)}
      <p class="privacy">🔒 Analysed on this phone. Your photo is never uploaded.</p>
    </section>`;
  }
  view().innerHTML = html;
}

async function decodeFile(file) {
  try { return await createImageBitmap(file, { imageOrientation: "from-image" }); }
  catch {
    const img = new Image();
    img.src = URL.createObjectURL(file);
    await img.decode();
    return img;
  }
}
const toBlob = (cv) => cv.convertToBlob ? cv.convertToBlob({ type: "image/jpeg", quality: 0.9 })
  : new Promise((r) => cv.toBlob(r, "image/jpeg", 0.9));

async function runScan(input) {
  const file = input.files[0];
  if (!file) return;
  const ds = input.dataset.day;
  const status = $("#scan-status"), pick = $("#pick");
  const say = (t, cls = "") => { status.hidden = false; status.className = "status " + cls; status.innerHTML = t; };
  pick.classList.add("busy");
  try {
    say('<span class="spin"></span>Loading face model…');
    const m = await ensureMeasurer();
    say('<span class="spin"></span>Reading photo…');
    let img;
    try { img = await decodeFile(file); }
    catch { throw new Error("This photo format can't be read here. Use JPEG or PNG (on iPhone: Settings → Camera → Formats → Most Compatible)."); }
    say('<span class="spin"></span>Analysing your face…');
    await new Promise((r) => setTimeout(r, 30));
    const res = await m.measure(img);
    const settings = await store.settings();
    if (!res) {
      await store.saveCheckin({ day: ds, assessment: null, warnings: ["No face found. Face the camera in good light, with your whole face in frame."] });
    } else {
      const a = REF.assess(res.metrics, res.shape, settings.sex, { asian: "A", caucasian: "C" }[settings.ethnicity] || "");
      const { annotate } = await import("./measure.js");
      await store.saveCheckin({ day: ds, assessment: a, warnings: photoWarnings(res.metrics),
        photo: await toBlob(res.crop), annotated: await toBlob(annotate(res.crop, res.pts)) });
    }
    await store.setHabit(ds, "photo", true);
    navigator.storage?.persist?.();
    toast(res ? '<span class="gold">+20 XP</span>Scan complete' : "No face found");
    route();
  } catch (e) {
    pick.classList.remove("busy");
    say(esc(e.message || "Something went wrong. Try another photo."), "err");
  }
}

// ---------------------------------------------------------------- report
async function viewReport({ parts }) {
  const ds = parts[1], c = await store.checkin(ds);
  if (!c?.assessment) return (location.hash = "#/scan");
  const a = c.assessment, flags = flaggedMetrics(a, K), prios = priorityAreas(a, flags, K).slice(0, 4);
  const measures = Object.entries(K.metrics).map(([name, [label, , expl]]) => ({
    label, expl, value: a.adjusted[name], lo: a.iqr[name][0], hi: a.iqr[name][1],
    pct: a.metric_pct[name], r: a.rating_corr_adj[name], matters: Math.abs(a.rating_corr_adj[name]) >= K.r_min,
  })).sort((x, y) => (y.matters - x.matters) || (Math.abs(y.r) - Math.abs(x.r)));
  const li = (arr, f) => arr.map(f).join("");
  view().innerHTML = `
  <p class="back"><a href="#/scan?d=${ds}">‹ Scan</a></p>
  <h1>Breakdown <small class="sub">${fmt(fromIso(ds), { month: "short", day: "numeric" })}</small></h1>
  <section class="card result">
    <img class="thumb" src="${blobUrl(c.annotated)}" alt="Your landmarks">
    <div><p class="eyebrow">Structure index</p>
      <p class="big">${round(a.overall.pct)}<small>${ordinal(a.overall.pct)} pct</small></p>
      <p class="sub">Explains only ~${round(Math.max(0, a.overall.cv_r2) * 100)}% of rating differences. Hair, eyes, grooming and lighting matter too. A guide, not a verdict.</p></div>
  </section>
  <section class="card"><h2>Where to focus</h2>
    <ol class="prio">${li(prios, (p) => `<li><b>${esc(K.area_actions[p].title)}</b><span class="chip ${K.area_actions[p].changeable}">${K.area_actions[p].changeable} changeability</span></li>`) || "<li>No area is clearly below the reference. Keep up the habits.</li>"}</ol>
  </section>
  ${li(prios, (p, i) => `<details class="card acc" ${i ? "" : "open"}><summary><span>${esc(K.area_actions[p].title)}</span></summary>
    <p class="sub">${esc(K.area_actions[p].why)}</p>
    <ul class="actions">${li(K.area_actions[p].actions, ([t, ev, risk, tf]) => `<li><p>${esc(t)}</p><p class="meta"><span class="ev">${ev}</span> · risk ${risk} · ${esc(tf)}</p></li>`)}</ul></details>`)}
  <details class="card acc"><summary><span>All measurements</span><small>${measures.length}</small></summary>
    <p class="sub">Bold rows actually predicted ratings in the data (|r| ≥ 0.10). The rest are community metrics that barely mattered.</p>
    <table class="mtable"><thead><tr><th>Measure</th><th>You</th><th>Pct</th><th>r</th></tr></thead><tbody>
    ${li(measures, (m) => `<tr class="${m.matters ? "matters" : ""}"><td>${esc(m.label)}<small>${esc(m.expl)} · typical ${m.lo.toFixed(2)}–${m.hi.toFixed(2)}</small></td><td>${m.value.toFixed(2)}</td><td>${round(m.pct)}</td><td>${(m.r > 0 ? "+" : "") + m.r.toFixed(2)}</td></tr>`)}
    </tbody></table></details>
  <details class="card acc"><summary><span>Presentation</span></summary>
    <ul class="actions">${li(K.presentation, ([t, ev]) => `<li><p>${esc(t)}</p><p class="meta"><span class="ev">${ev}</span></p></li>`)}</ul></details>
  <details class="card acc"><summary><span>Lesser-known habits</span></summary>
    <ul class="actions">${li(K.lesser_known, ([n, ev, risk, note]) => `<li><p><b>${esc(n)}</b>. ${esc(note)}</p><p class="meta"><span class="ev">${ev}</span> · risk ${risk}</p></li>`)}</ul></details>
  <details class="card acc"><summary><span>Overrated &amp; avoid</span></summary>
    <ul class="actions">${li(K.overrated, ([n, ev, , note]) => `<li><p><b>${esc(n)}</b>. ${esc(note)}</p><p class="meta"><span class="ev">${ev}</span></p></li>`)}
    ${li(K.avoid, ([n, why]) => `<li class="avoid"><p><b>${esc(n)}</b>. ${esc(why)}</p></li>`)}</ul>
    <p class="sub">${esc(K.surgical_note)}</p></details>
  <details class="card acc"><summary><span>How this works</span></summary>
    <p class="sub">478 landmarks are measured on your photo, on this phone, and compared with the same measurements on ${a.n_reference.toLocaleString("en-US")} faces rated by 60 people each (SCUT-FBP5500). Head angle, expression and sharpness are removed statistically. A frontal photo can't measure profile features (maxilla, chin projection), hair, height, body or style. Most raters were young Chinese adults.</p></details>`;
}

// ---------------------------------------------------------------- progress
function trendSvg(points, label, width = 320, height = 140) {
  if (!points.length) return '<p class="sub">No scans yet.</p>';
  const pl = 28, pr = 10, pt = 10, pb = 22, w = width - pl - pr, h = height - pt - pb;
  const days = points.map(([d]) => fromIso(d)), d0 = days[0], d1 = days[days.length - 1];
  const span = Math.max((d1 - d0) / 864e5, 1);
  const x = (d) => pl + (+d0 === +d1 ? w / 2 : ((d - d0) / 864e5 / span) * w), y = (v) => pt + (1 - v / 100) * h;
  const vals = points.map(([, v]) => v);
  const roll = vals.map((_, i) => { const s = vals.slice(Math.max(0, i - 6), i + 1); return s.reduce((a, b) => a + b) / s.length; });
  let o = `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)} over time">`;
  for (const g of [0, 50, 100]) o += `<line class="grid" x1="${pl}" x2="${pl + w}" y1="${y(g)}" y2="${y(g)}"/><text class="axis" x="${pl - 6}" y="${y(g) + 3}" text-anchor="end">${g}</text>`;
  o += `<text class="axis" x="${pl}" y="${height - 6}">${fmt(d0, { month: "short", day: "2-digit" })}</text>`;
  if (+d1 !== +d0) o += `<text class="axis" x="${pl + w}" y="${height - 6}" text-anchor="end">${fmt(d1, { month: "short", day: "2-digit" })}</text>`;
  if (points.length > 1) o += `<path class="line" d="${days.map((d, i) => `${i ? "L" : "M"}${x(d).toFixed(1)},${y(roll[i]).toFixed(1)}`).join(" ")}"/>`;
  days.forEach((d, i) => { o += `<g class="pt"><circle class="hit" cx="${x(d)}" cy="${y(vals[i])}" r="9"/><circle class="dot" cx="${x(d)}" cy="${y(vals[i])}" r="4"/><title>${fmt(d, { weekday: "short", month: "short", day: "numeric" })}: ${round(vals[i])} (7-scan avg ${round(roll[i])})</title></g>`; });
  return o + "</svg>";
}

async function viewProgress({ settings }) {
  const today = new Date(), all = await store.checkins(), scans = all.filter((c) => c.assessment);
  const doneBy = {};
  for (const r of await store.habitLog()) (doneBy[r.day] ??= new Set()).add(r.habit);
  const grid = [];
  for (let i = 27; i >= 0; i--) {
    const d = addDays(today, -i), ds = iso(d);
    const ids = new Set(planFor(d, await prioritiesFor(ds, all), settings.sex, K).map((h) => h.id));
    const got = [...ids].filter((id) => doneBy[ds]?.has(id)).length;
    grid.push({ d, ds, ids, got, total: ids.size, pct: ids.size ? got / ids.size : 0 });
  }
  let streak = 0;
  for (const g of [...grid].reverse()) {
    if (g.ds === iso(today) && g.pct < 0.7) continue;
    if (g.pct < 0.7) break;
    streak++;
  }
  const week = grid.slice(-7), weekPct = week.reduce((s, g) => s + g.got, 0) / Math.max(1, week.reduce((s, g) => s + g.total, 0));
  const stats = K.habits.map((h) => {
    const sched = grid.filter((g) => g.ids.has(h.id));
    const got = sched.filter((g) => doneBy[g.ds]?.has(h.id)).length;
    return sched.length ? { label: h.label, got, total: sched.length, pct: got / sched.length } : null;
  }).filter(Boolean).sort((a, b) => a.pct - b.pct);
  const headline = !scans.length && !Object.keys(doneBy).length ? "Nothing logged yet. Your first scan starts the timeline."
    : stats.length ? `${round(100 * weekPct)}% of quests done this week. Strongest: ${stats[stats.length - 1].label.toLowerCase()}. Weakest: ${stats[0].label.toLowerCase()}.` : "";
  const series = [["overall", "Structure index"], ...COMPONENTS.map((k) => [k, K.comp_label[k]])];

  view().innerHTML = `
  <h1>Progress</h1>
  <section class="statrow">
    <div class="card stat"><b class="gold">${streak}</b><span>day streak</span></div>
    <div class="card stat"><b>${round(100 * weekPct)}%</b><span>this week</span></div>
    <div class="card stat"><b>${scans.length}</b><span>scans</span></div>
  </section>
  ${headline ? `<p class="coach">${esc(headline)}</p>` : ""}
  <div class="seg" role="tablist">
    <button role="tab" data-pane="habits" class="on">Habits</button><button role="tab" data-pane="face">Face</button><button role="tab" data-pane="photos">Photos</button>
  </div>
  <section class="pane" data-pane="habits">
    <div class="card"><p class="eyebrow">Last 4 weeks · streak counts days at 70%+</p>
      <div class="heat">${grid.map((g) => `<a href="#/?d=${g.ds}" class="cell" style="--p:${g.pct}" title="${fmt(g.d, { weekday: "short", month: "short", day: "numeric" })}: ${g.got}/${g.total}"><span>${g.d.getDate()}</span></a>`).join("")}</div></div>
    <details class="card acc"><summary><span>Per habit</span><small>weakest first</small></summary>
      <table class="stats">${stats.map((s) => `<tr><td>${esc(s.label)}</td><td>${s.got}/${s.total}</td><td class="bar"><b style="width:${round(100 * s.pct)}%"></b></td></tr>`).join("")}</table></details>
  </section>
  <section class="pane" data-pane="face" hidden>
    <p class="sub">Dots are single scans; the line is the 7-scan average. Watch the line, not the dots.</p>
    <div class="charts">${series.map(([k, label]) => {
      const pts = scans.map((c) => [c.day, k === "overall" ? c.assessment.overall.pct : c.assessment.components[k].pct]);
      return `<figure class="card"><figcaption>${esc(label)}${pts.length ? ` <b>${round(pts[pts.length - 1][1])}</b>` : ""}</figcaption>${trendSvg(pts, label)}</figure>`;
    }).join("")}</div>
  </section>
  <section class="pane" data-pane="photos" hidden>
    ${scans.length ? `<div class="gallery">${[...scans].reverse().slice(0, 30).map((c) => `<a href="#/scan?d=${c.day}"><img src="${blobUrl(c.photo)}" alt="${c.day}" loading="lazy"><span>${c.day.slice(5)}</span></a>`).join("")}</div>` : '<p class="sub">No scans yet.</p>'}
  </section>`;
}

// ---------------------------------------------------------------- profile
async function viewProfile({ q, settings }) {
  const setup = q.get("setup") && !settings.sex;
  const rank = await chrome("profile");
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  const radio = (name, val, label, cur) => `<label><input type="radio" name="${name}" value="${val}" ${cur === val ? "checked" : ""} ${name === "sex" ? "required" : ""}><span>${label}</span></label>`;
  view().innerHTML = `
  ${setup ? `<h1>Welcome to Ascend</h1><p class="lead">Scan your face daily, clear your quests, climb the ranks. Everything stays on this phone. One quick choice to start.</p>` : `
  <h1>Profile</h1>
  <section class="card rankcard"><div class="badge">${rank.tier}</div><div>
    <p class="eyebrow">Rank</p><h2>${rank.name}</h2>
    <div class="xpbar"><b style="width:${round(100 * rank.progress)}%"></b></div>
    <p class="sub">${rank.xp} XP${rank.next_name ? ` · ${rank.next_at - rank.xp} to ${rank.next_name}` : ""}</p></div></section>
  <p class="sub note">Ranks measure consistency, not looks. Quests earn XP: strong-evidence habits 15, moderate 10, weak 5, scans 20.</p>`}
  <form class="card form" id="settings-form">
    <fieldset><legend>Compare my scans with</legend><div class="radios">${radio("sex", "M", "Men", settings.sex)}${radio("sex", "F", "Women", settings.sex)}</div></fieldset>
    <fieldset><legend>Reference subgroup</legend><div class="radios">${radio("ethnicity", "", "Everyone", settings.ethnicity || "")}${radio("ethnicity", "asian", "Asian", settings.ethnicity)}${radio("ethnicity", "caucasian", "Caucasian", settings.ethnicity)}</div></fieldset>
    <button class="btn" type="submit">${setup ? "Start" : "Save"}</button>
  </form>
  ${setup ? "" : `
  ${standalone ? "" : `<section class="card"><h2>Install on your phone</h2><p class="sub">${isIOS ? "In Safari tap <b>Share</b> → <b>Add to Home Screen</b>." : "In Chrome tap <b>⋮</b> → <b>Add to Home screen</b> / <b>Install app</b>."} It then opens full-screen, works offline and keeps your data safe from browser clean-ups.</p></section>`}
  <details class="card acc"><summary><span>Ranks</span></summary>
    <ol class="ranks">${K.ranks.map(([f, n]) => `<li class="${n === rank.name ? "here" : ""}"><b>${n}</b><span>${f} XP</span></li>`).join("")}</ol></details>
  <details class="card acc"><summary><span>Backup &amp; data</span></summary>
    <p class="sub">Your data lives only on this phone. Export a backup now and then, and to move to a new phone.</p>
    <div class="btnrow"><button class="btn sm" data-action="export">Export backup</button>
      <label class="btn sm ghostbtn">Import backup<input type="file" accept="application/json,.json" id="import-input" hidden></label></div>
    <button class="linkdanger" data-action="wipe">Delete all data on this phone</button></details>`}`;
}

// ---------------------------------------------------------------- events
function onClick(e) {
  const seg = e.target.closest(".seg button");
  if (seg && !seg.disabled) {
    const wrap = seg.parentElement;
    $$("button", wrap).forEach((b) => b.classList.toggle("on", b === seg));
    const key = seg.dataset.slot ? "slot" : "pane", val = seg.dataset[key];
    $$(`[data-${key}]:not(button)`).forEach((p) => (p.hidden = p.dataset[key] !== val));
    return;
  }
  const act = e.target.closest("[data-action]")?.dataset.action;
  if (act === "export") exportBackup();
  if (act === "wipe" && confirm("Delete all scans, quests and settings on this phone? This can't be undone.")) store.wipe().then(() => (location.hash = "#/profile?setup=1", location.reload()));
}

async function onChange(e) {
  const t = e.target;
  if (t.matches(".checklist input[type=checkbox]")) return toggleHabit(t);
  if (t.id === "photo-input") return runScan(t);
  if (t.id === "import-input" && t.files[0]) {
    try {
      const r = await store.importAll(JSON.parse(await t.files[0].text()));
      toast(`Imported ${r.checkins} scans, ${r.habits} quest ticks`);
      route();
    } catch (err) { toast(esc(err.message)); }
  }
}
document.addEventListener("submit", async (e) => {
  if (e.target.id !== "settings-form") return;
  e.preventDefault();
  const f = new FormData(e.target);
  await store.saveSettings({ sex: f.get("sex"), ethnicity: f.get("ethnicity") || "" });
  toast("Saved");
  location.hash = "#/";
});

async function exportBackup() {
  const data = await store.exportAll();
  const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
  const name = `ascend-backup-${iso(new Date())}.json`;
  const file = new File([blob], name, { type: "application/json" });
  if (navigator.canShare?.({ files: [file] })) {
    try { await navigator.share({ files: [file], title: "Ascend backup" }); return; } catch { /* fall back to download */ }
  }
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

function toast(html) {
  const t = $("#toast");
  t.innerHTML = html;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 2000);
}

boot().catch((e) => { view().innerHTML = `<p class="warn">Couldn't start: ${esc(e.message)}</p>`; });
