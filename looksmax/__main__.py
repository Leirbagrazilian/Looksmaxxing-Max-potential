"""Assess a face photo and write an improvement report.

    python -m looksmax photo.jpg --sex M [--ethnicity asian|caucasian] [--out report_dir]
"""

import argparse
import json
from pathlib import Path

import cv2

from .measure import FaceMeasurer
from .reference import Reference
from .report import annotate, render


def main(argv=None):
    p = argparse.ArgumentParser(prog="looksmax", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("photo", help="frontal face photo (jpg/png)")
    p.add_argument("--sex", required=True, choices=["M", "F"],
                   help="reference group: compare with rated men (M) or women (F)")
    p.add_argument("--ethnicity", choices=["asian", "caucasian"],
                   help="optional: compare only with that subgroup of the reference data")
    p.add_argument("--out", default="looksmax_report", help="output folder")
    args = p.parse_args(argv)

    img = cv2.imread(args.photo)
    if img is None:
        p.error(f"cannot read image: {args.photo}")
    fm = FaceMeasurer()
    res = fm.measure(img)
    fm.close()
    if res is None:
        p.error("no face found; use a clear, front-facing photo")
    metrics, shape, pts, crop = res

    eth = {"asian": "A", "caucasian": "C", None: None}[args.ethnicity]
    assessment = Reference().assess(metrics, shape, args.sex, eth)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    annotate(crop, pts, out / "landmarks.jpg")
    (out / "report.md").write_text(render(assessment, args.sex, Path(args.photo).name, "landmarks.jpg"))
    (out / "assessment.json").write_text(json.dumps(assessment, indent=2, default=float))
    print(f"Report written to {out / 'report.md'}")


if __name__ == "__main__":
    main()
