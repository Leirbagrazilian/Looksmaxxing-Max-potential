// Tiny static server for testing dist/ with the same headers Netlify will send.
//   node tools/serve.cjs [dir] [port]
const http = require("http"), fs = require("fs"), path = require("path");
const dir = path.resolve(process.argv[2] || "dist"), port = +(process.argv[3] || 8800);
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".wasm": "application/wasm", ".png": "image/png", ".jpg": "image/jpeg", ".webmanifest": "application/manifest+json", ".task": "application/octet-stream" };
const csp = (fs.readFileSync(path.join(dir, "_headers"), "utf8").match(/Content-Security-Policy: (.*)/) || [])[1];
http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split("?")[0]);
  if (p.endsWith("/")) p += "index.html";
  const f = path.join(dir, p);
  if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  const h = { "Content-Type": types[path.extname(f)] || "application/octet-stream" };
  if (csp) h["Content-Security-Policy"] = csp;
  res.writeHead(200, h);
  fs.createReadStream(f).pipe(res);
}).listen(port, () => console.log(`serving ${dir} on ${port}`));
