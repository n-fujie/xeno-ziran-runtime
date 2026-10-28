"""Per-crop image statistics of captures against an earlier set of captures taken with the same cameras (no reference images needed).

    python backend/scripts/visual_crops_local.py --crop-spec docs/ecosystem/visual/crops.json --captures NEW_DIR --before docs/ecosystem/visual --out OUT.json [--resample-width 766]

The statistics are those of ``visual_compare.crop_metrics`` (crude proxies, none a perceptual judgement). The reference values of the third stage are in
``docs/ecosystem/visual/metrics_crops_at_reference_resolution.json``; the reference images themselves are not stored in the repository."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import visual_compare as V

ap = argparse.ArgumentParser()
ap.add_argument("--crop-spec", required=True)
ap.add_argument("--captures", required=True)
ap.add_argument("--before", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--resample-width", type=int)
ap.add_argument("--only", default="")
a = ap.parse_args()
spec = json.loads(Path(a.crop_spec).read_text())
rows: dict = {}
for shot, d in spec["shots"].items():
    if a.only and not any(o in shot for o in a.only.split(",")):
        continue
    new, old = Path(a.captures) / f"{shot}.png", Path(a.before) / f"{shot}.png"
    if not new.exists() or not old.exists():
        continue
    img_new, img_old = V.load(V.resampled(new, a.resample_width)), V.load(V.resampled(old, a.resample_width))
    out = {}
    for name, box in d["crops"].items():
        def cut(img, b=box):
            h, w = img.shape[:2]
            return img[int(b[1] * h) : int(b[3] * h), int(b[0] * w) : int(b[2] * w)]
        out[name] = {"after": V.crop_metrics(cut(img_new)), "before": V.crop_metrics(cut(img_old))}
    rows[shot] = out
Path(a.out).write_text(json.dumps({"note": "crop statistics are crude proxies; none of them establishes that a picture matches a reference", "captures_resampled_to_width": a.resample_width, "shots": rows}, indent=1))
print("crops:", sum(len(v) for v in rows.values()), "in", len(rows), "shots ->", a.out)
