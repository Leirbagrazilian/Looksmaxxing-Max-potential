// On-device storage (IndexedDB). Nothing is ever uploaded.
const DB = "ascend", VERSION = 1;
let dbp;

function db() {
  dbp ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, VERSION);
    req.onupgradeneeded = () => {
      const d = req.result;
      d.createObjectStore("kv");
      d.createObjectStore("checkins", { keyPath: "day" });
      d.createObjectStore("habits", { keyPath: "key" }).createIndex("day", "day");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbp;
}

async function tx(store, mode, fn) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const t = d.transaction(store, mode);
    const s = t.objectStore(store);
    let result;
    Promise.resolve(fn(s)).then((r) => (result = r));
    t.oncomplete = () => resolve(result);
    t.onerror = () => reject(t.error);
  });
}
const req2p = (r) => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });

export const store = {
  async settings() { return (await tx("kv", "readonly", (s) => req2p(s.get("settings")))) || {}; },
  saveSettings: (v) => tx("kv", "readwrite", (s) => s.put(v, "settings")),

  saveCheckin: (c) => tx("checkins", "readwrite", (s) => s.put(c)),
  checkin: (day) => tx("checkins", "readonly", (s) => req2p(s.get(day))),
  async checkins() { return (await tx("checkins", "readonly", (s) => req2p(s.getAll()))).sort((a, b) => a.day.localeCompare(b.day)); },
  async latestCheckin(onOrBefore) {
    const all = await this.checkins();
    return all.filter((c) => c.day <= onOrBefore && c.assessment).pop() || null;
  },

  setHabit: (day, habit, done) => tx("habits", "readwrite", (s) => s.put({ key: `${day}|${habit}`, day, habit, done: !!done })),
  async habitsDone(day) {
    const rows = await tx("habits", "readonly", (s) => req2p(s.index("day").getAll(day)));
    return new Set(rows.filter((r) => r.done).map((r) => r.habit));
  },
  async habitLog() { return (await tx("habits", "readonly", (s) => req2p(s.getAll()))).filter((r) => r.done); },

  // ---- backup
  async exportAll() {
    const toB64 = (blob) => blob ? new Promise((r) => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(blob); }) : null;
    const checkins = [];
    for (const c of await this.checkins()) checkins.push({ ...c, photo: await toB64(c.photo), annotated: await toB64(c.annotated) });
    const habits = await tx("habits", "readonly", (s) => req2p(s.getAll()));
    return { app: "ascend", version: 1, exported: new Date().toISOString(), settings: await this.settings(), checkins, habits };
  },
  async importAll(data) {
    if (data?.app !== "ascend") throw new Error("Not an Ascend backup file.");
    const fromB64 = async (u) => (u ? (await fetch(u)).blob() : null);
    const checkins = [];
    for (const c of data.checkins || []) checkins.push({ ...c, photo: await fromB64(c.photo), annotated: await fromB64(c.annotated) });
    await this.saveSettings(data.settings || {});
    await tx("checkins", "readwrite", (s) => checkins.forEach((c) => s.put(c)));
    await tx("habits", "readwrite", (s) => (data.habits || []).forEach((h) => s.put(h)));
    return { checkins: checkins.length, habits: (data.habits || []).length };
  },
  async wipe() {
    for (const s of ["kv", "checkins", "habits"]) await tx(s, "readwrite", (st) => st.clear());
  },
};
