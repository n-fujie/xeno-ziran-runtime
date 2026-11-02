"""Compare an independent re-run of the HPO experiments with the published (frozen) result files.

    python backend/scripts/hpo_compare_reproduction.py REPRO_DIR

REPRO_DIR holds hpo001.json, hpo002.json, general.json, hpo003.json written by a separate re-run (from a clean clone of
the published commit; the published files are never touched). Every field is compared recursively except run
bookkeeping: elapsed time and provenance (timestamps, commit / dirty flags, interpreter). Writes
backend/experiments/results/hpo/reproduction.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "backend" / "experiments" / "results" / "hpo"
SKIP = {"elapsed_s", "provenance"}


def diffs(a, b, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k in SKIP and path.count(".") <= 1:
                continue
            if k not in a or k not in b:
                out.append(f"{path}.{k}: present on one side only")
            else:
                out += diffs(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b, strict=True)) for d in diffs(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {str(a)[:60]} != {str(b)[:60]}"]


def main() -> None:
    repro = Path(sys.argv[1])
    out = {"method": "Re-run of every confirmatory experiment with its original protocol, seeds and code, from a "
                     "clean clone of the published commit on the same machine, written to a separate directory; "
                     "compared field by field with the published files (run bookkeeping excluded).",
           "repro_dir": repro.name, "experiments": {}}
    for name in ("hpo001", "hpo002", "general", "hpo003"):
        p, q = RES / f"{name}.json", repro / f"{name}.json"
        if not q.exists():
            out["experiments"][name] = {"compared": [], "identical": None, "differences": ["not re-run"]}
            continue
        a, b = json.loads(p.read_text()), json.loads(q.read_text())
        d = diffs(a, b)
        out["experiments"][name] = {"compared": sorted(k for k in a if k not in SKIP), "identical": not d,
                                    "differences": d[:25], "n_differences": len(d),
                                    "protocol_sha256": b.get("provenance", {}).get("protocol_sha256")}
    (RES / "reproduction.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for k, v in out["experiments"].items():
        print(k, "identical" if v["identical"] else f"{v.get('n_differences')} differences", v["differences"][:3])


if __name__ == "__main__":
    main()
