// Measure the reference dataset with the web app's own measurement code.
//   node tools/measure_dataset.cjs <server_base_url> <images_url_prefix> <labels.csv> <out.json>
// The server must serve dist/ (with tools/harness.html copied in) and the images.
const fs = require("fs");
const { chromium } = require("playwright");

(async () => {
  const [base, imgPrefix, labelsCsv, outPath] = process.argv.slice(2);
  const files = fs.readFileSync(labelsCsv, "utf8").trim().split("\n").map((l) => l.split(",")[0]);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.error("page error:", e.message));
  await page.goto(base + "/harness.html");
  await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  const results = [];
  const B = 50;
  for (let i = 0; i < files.length; i += B) {
    const urls = files.slice(i, i + B).map((f) => imgPrefix + f);
    const r = await page.evaluate((u) => window.measureUrls(u), urls);
    r.forEach((x, j) => (x.file = files[i + j]));
    results.push(...r);
    if (i % 500 === 0) console.log(`${i}/${files.length}`);
  }
  fs.writeFileSync(outPath, JSON.stringify(results));
  console.log(`done: ${results.filter((r) => r.metrics).length}/${files.length} faces`);
  await browser.close();
})();
