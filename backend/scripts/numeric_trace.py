"""Numerical trace of the engine, for comparing runtimes (desktop CPython vs the browser's Pyodide/WebAssembly).

    python backend/scripts/numeric_trace.py <scenario> <out.json> [--steps 0,50,200,500,1000] [--seed N]

Runs the scenario from its bundled definition and records, at each requested step, every state array exactly
(dtype, shape, raw bytes as base64), the state fingerprint, and the ignition counts of the last step. It also records a
'libm probe': elementary functions on fixed inputs, so a difference in the platform's math library can be told apart
from a difference in the engine. The same file runs unchanged on both platforms (numpy only; xzr on the path);
backend/scripts/numeric_compare.py compares two traces.
"""

from __future__ import annotations

import base64
import json
import os
import sys

import numpy as np


def probe() -> dict:
    x = np.linspace(-6.0, 6.0, 4001)
    y = np.linspace(0.01, 50.0, 4001)
    out = {}
    for name, v in {
        "exp": np.exp(x), "log": np.log(y), "tanh": np.tanh(x), "sin": np.sin(x), "power": np.power(y, 0.37),
        "sqrt": np.sqrt(y), "arctan": np.arctan(x), "expm1": np.expm1(x / 8), "log1p": np.log1p(y / 8),
        "sum": np.array([np.sum(np.sin(np.arange(n))) for n in (10, 100, 1000, 10007)]),
        "dot": np.array([np.dot(np.sin(np.arange(n)), np.cos(np.arange(n))) for n in (10, 100, 1000, 10007)]),
    }.items():
        out[name] = base64.b64encode(np.ascontiguousarray(v, dtype=np.float64).tobytes()).decode()
    return out


def main() -> None:
    name, out = sys.argv[1], sys.argv[2]
    steps = [0, 50, 200, 500, 1000]
    if "--steps" in sys.argv:
        steps = [int(v) for v in sys.argv[sys.argv.index("--steps") + 1].split(",")]
    from xzr.scenario.build import build_world
    from xzr.scenario.io import load_sample

    sc = load_sample(name)
    if "--seed" in sys.argv:
        sc = sc.model_copy(update={"seed": int(sys.argv[sys.argv.index("--seed") + 1])})
    world = build_world(sc)
    eng = world.engine
    t0 = eng.state.t
    trace = {"scenario": name, "numpy": np.__version__, "python": sys.version.split()[0], "platform": sys.platform,
             "itemsize_intp": np.dtype(np.intp).itemsize, "t0": t0, "checkpoints": {}, "probe": probe()}
    done = 0
    for target in sorted(set(steps)):
        while done < target:
            d = eng.step()
            done += 1
        arrays = eng.state.arrays()
        trace["checkpoints"][str(target)] = {
            "fingerprint": eng.fingerprint(),
            "arrays": {k: {"dtype": str(v.dtype), "shape": list(v.shape),
                           "b64": base64.b64encode(np.ascontiguousarray(v).tobytes()).decode()}
                       for k, v in sorted(arrays.items())},
            "ignitions_last_step": int(len(d.ignitions)) if done else 0,
        }
    with open(out, "w") as f:
        json.dump(trace, f)
    print(f"{name}: {len(steps)} checkpoints written to {out}")


if __name__ == "__main__":
    os.environ.setdefault("XZR_MAX_NODES", "50000")
    main()
