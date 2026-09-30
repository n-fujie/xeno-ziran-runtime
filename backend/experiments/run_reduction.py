"""Run the primitive reduction study and write experiments/results/reduction.json."""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")  # one BLAS thread per worker process
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xzr.experiments.reduction import main  # noqa: E402
from xzr.experiments.reduction_rules import reclassify  # noqa: E402

if __name__ == "__main__":
    out = str(Path(__file__).parent / "results" / "reduction.json")
    r = reclassify(out) if "--reclassify" in sys.argv else main(out)
    for row in r["classification"]:
        print(f"{row['primitive']:36s} {row['status']}")
    print("elapsed", r["elapsed_s"], "s")
