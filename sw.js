// Offline support: the app shell is cached on install; the face model and
// wasm are cached the first time they load. 1.1.1-aa1f36e0c2 is replaced at build.
const CACHE = "ascend-1.1.1-aa1f36e0c2";
const SHELL = ["./", "index.html", "css/style.css", "js/app.js", "js/logic.js", "js/store.js", "js/measure.js",
  "data/knowledge.json", "data/reference.json", "manifest.webmanifest", "icons/icon-192.png", "vendor/vision_bundle.mjs"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin && !url.hostname.endsWith("gstatic.com") && !url.hostname.endsWith("googleapis.com")) return;
  e.respondWith(
    caches.match(req, { ignoreSearch: url.origin === location.origin }).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok || res.type === "opaque") {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
      }
      return res;
    }).catch(() => (req.mode === "navigate" ? caches.match("index.html") : Response.error())))
  );
});
