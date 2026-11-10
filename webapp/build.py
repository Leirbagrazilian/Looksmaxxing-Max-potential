"""Build the static web app into webapp/dist.

    python webapp/build.py            # needs `npm install` in webapp/ first

- copies src/ and the pinned MediaPipe web bundle + wasm (from node_modules)
- downloads the face landmark model once (cached in webapp/.cache)
- exports the knowledge base (habits, quests, ranks, metric labels) from the
  Python package to data/knowledge.json, so Python and web share one source
"""

import json
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from looksmax import daily, habits as H                     # noqa: E402
from looksmax.measure import MODEL_URL                       # noqa: E402
from looksmax.report import COMP_LABEL, METRICS, R_MIN       # noqa: E402

DIST = HERE / "dist"
MP = HERE / "node_modules" / "@mediapipe" / "tasks-vision"
MODEL_CACHE = HERE / ".cache" / "face_landmarker.task"


def knowledge():
    return {
        "habits": [{k: (list(v) if isinstance(v, tuple) else v) for k, v in h.items()} for h in daily.HABITS],
        "slots": daily.SLOTS, "ranks": daily.RANKS,
        "area_actions": H.AREA_ACTIONS, "presentation": H.PRESENTATION,
        "core_habits": H.CORE_HABITS, "lesser_known": H.LESSER_KNOWN,
        "overrated": H.OVERRATED, "avoid": H.AVOID, "surgical_note": H.SURGICAL_NOTE,
        "metrics": {k: list(v) for k, v in METRICS.items()}, "comp_label": COMP_LABEL, "r_min": R_MIN,
    }


def build(dist=DIST):
    if not MP.exists():
        sys.exit("Run `npm install` in webapp/ first.")
    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree(HERE / "src", dist)
    (dist / "vendor" / "wasm").mkdir(parents=True)
    shutil.copy(MP / "vision_bundle.mjs", dist / "vendor")
    for f in ("vision_wasm_internal.js", "vision_wasm_internal.wasm",
              "vision_wasm_nosimd_internal.js", "vision_wasm_nosimd_internal.wasm"):
        shutil.copy(MP / "wasm" / f, dist / "vendor" / "wasm")
    if not MODEL_CACHE.exists():
        MODEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL_CACHE)
    (dist / "models").mkdir()
    shutil.copy(MODEL_CACHE, dist / "models")
    (dist / "data").mkdir(exist_ok=True)
    (dist / "data" / "knowledge.json").write_text(json.dumps(knowledge()))
    version = json.loads((MP / "package.json").read_text())["version"]
    sw = dist / "sw.js"
    if sw.exists():  # bump the service-worker cache whenever the build changes
        import hashlib
        h = hashlib.sha1()
        for p in sorted(dist.rglob("*")):
            if p.is_file() and p.name != "sw.js" and p.suffix != ".wasm":
                h.update(p.read_bytes())
        sw.write_text(sw.read_text().replace("__BUILD__", f"{version}-{h.hexdigest()[:10]}"))
    print(f"built {dist}")


if __name__ == "__main__":
    build()
