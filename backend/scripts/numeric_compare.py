"""Compare two numeric traces (backend/scripts/numeric_trace.py): desktop CPython vs the browser's Pyodide.

    python backend/scripts/numeric_compare.py <a.json> <b.json> [--out report.json]

Reports, per checkpoint: arrays bit-identical, float arrays that differ (max absolute / relative difference, in ULPs of
the larger value), discrete (integer / boolean) arrays that differ, and the first step at which any discrete state
differs. Also compares the libm probe (which elementary functions round differently) and flags dtype / shape mismatches.
Exit status is 0 always: this is a measurement, not a pass/fail gate (the gate is in web_conformance.mjs).
"""

from __future__ import annotations

import base64
import json
import sys

import numpy as np


def arr(entry: dict) -> np.ndarray:
    return np.frombuffer(base64.b64decode(entry["b64"]), dtype=np.dtype(entry["dtype"])).reshape(entry["shape"])


def ulps(x: np.ndarray, y: np.ndarray) -> float:
    m = np.isfinite(x) & np.isfinite(y)
    if not m.any():
        return 0.0
    a, b = x[m], y[m]
    spacing = np.spacing(np.maximum(np.abs(a), np.abs(b)))
    spacing = np.where(spacing == 0, np.finfo(np.float64).tiny, spacing)
    return float(np.max(np.abs(a - b) / spacing))


def main() -> None:
    with open(sys.argv[1]) as fa, open(sys.argv[2]) as fb:
        a, b = json.load(fa), json.load(fb)
    meta = ("scenario", "numpy", "python", "platform", "itemsize_intp")
    out = {"a": {k: a[k] for k in meta}, "b": {k: b[k] for k in meta}, "checkpoints": {}, "probe": {}}
    first_discrete = None
    for step in sorted(a["checkpoints"], key=int):
        ca, cb = a["checkpoints"][step], b["checkpoints"][step]
        rec = {"fingerprint_equal": ca["fingerprint"] == cb["fingerprint"], "identical": 0, "float_differ": {},
               "discrete_differ": {}, "dtype_or_shape_mismatch": []}
        for k in ca["arrays"]:
            ea, eb = ca["arrays"][k], cb["arrays"].get(k)
            if eb is None or ea["dtype"] != eb["dtype"] or ea["shape"] != eb["shape"]:
                rec["dtype_or_shape_mismatch"].append(k)
                continue
            x, y = arr(ea), arr(eb)
            if x.tobytes() == y.tobytes():
                rec["identical"] += 1
            elif x.dtype.kind == "f":
                same_nan = np.array_equal(np.isnan(x), np.isnan(y))
                d = np.abs(x - y)
                rel = d / np.maximum(np.abs(x), 1e-300)
                nan_both = int((np.isnan(x) & np.isnan(y)).sum())
                rec["float_differ"][k] = {
                    "max_abs": float(np.nanmax(d)) if np.isfinite(d).any() else 0.0,
                    "max_rel": float(np.nanmax(rel)) if np.isfinite(rel).any() else 0.0,
                    "max_ulps": ulps(x, y), "differing": int((x != y).sum()) - nan_both,
                    "of": int(x.size), "nan_pattern_equal": bool(same_nan)}
            else:
                rec["discrete_differ"][k] = {"differing": int((x != y).sum()), "of": int(x.size)}
        if rec["discrete_differ"] and first_discrete is None:
            first_discrete = int(step)
        rec["arrays"] = len(ca["arrays"])
        rec["worst_rel"] = max((v["max_rel"] for v in rec["float_differ"].values()), default=0.0)
        out["checkpoints"][step] = rec
    out["first_step_with_discrete_difference"] = first_discrete
    for name in a["probe"]:
        x = np.frombuffer(base64.b64decode(a["probe"][name]), dtype=np.float64)
        y = np.frombuffer(base64.b64decode(b["probe"][name]), dtype=np.float64)
        out["probe"][name] = {"differing": int((x != y).sum()), "of": int(x.size), "max_ulps": ulps(x, y)}
    if "--out" in sys.argv:
        with open(sys.argv[sys.argv.index("--out") + 1], "w") as fo:
            json.dump(out, fo, indent=1)
    pa, pb = out["a"], out["b"]
    print(f"{pa['scenario']}: {pa['platform']}/numpy {pa['numpy']}  vs  {pb['platform']}/numpy {pb['numpy']}")
    for step, r in out["checkpoints"].items():
        same = "equal" if r["fingerprint_equal"] else "differ"
        print(f"  t+{step:>5}: fingerprints {same}; {r['identical']}/{r['arrays']} arrays bit-identical; "
              f"{len(r['float_differ'])} float arrays differ (worst relative {r['worst_rel']:.2e}); "
              f"{len(r['discrete_differ'])} integer/boolean arrays differ; "
              f"dtype/shape mismatches {len(r['dtype_or_shape_mismatch'])}")
    print("  first step with a discrete difference:", first_discrete)
    print("  libm probe:", {k: f"{v['differing']}/{v['of']} differ, <= {v['max_ulps']:.1f} ulp"
                           for k, v in out["probe"].items()})


if __name__ == "__main__":
    main()
