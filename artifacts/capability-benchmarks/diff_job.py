import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "/Users/user/Desktop/BIM/xeno-ziran-runtime/backend")
from xzr.experiments.escalation.harness import RESULTS, calibrations, condition, seed_job

def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b: out.append((path + "." + str(k), "missing")); continue
            walk(a[k], b[k], path + "." + str(k), out)
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b): out.append((path, f"len {len(a)} vs {len(b)}")); return
        for i, (x, y) in enumerate(zip(a, b)): walk(x, y, f"{path}[{i}]", out)
    elif isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        if not np.array_equal(np.asarray(a), np.asarray(b), equal_nan=True): out.append((path, "array differs"))
    elif a != b and not (isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b)):
        out.append((path, f"{a!r} vs {b!r}"[:80]))

if __name__ == "__main__":
    c = condition(id="pool", n=1500, horizon=400, seeds=1, variants=("A", "C", "E", "H"))
    here = Path(sys.argv[0]).resolve().parent
    gains = calibrations([c], 1, here / "calibration-private.json", RESULTS / "calibration.json")
    a = seed_job((c, 100, gains)); b = seed_job((c, 100, gains))
    out = []; walk(a, b, "job", out)
    keys = sorted({p.split("[")[0] for p, _ in out})
    print("differing fields:", len(out)); [print("  ", p, d) for p, d in out[:15]]
    print("distinct field names:", sorted({p.rsplit('.', 1)[-1].split('[')[0] for p, _ in out}))
