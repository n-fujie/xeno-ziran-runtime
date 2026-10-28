"""Replay every stored study run with this backend's code and compare it with the stored record.

    python backend/scripts/replay_stored_studies.py BACKEND_DIR IDS_JSON OUT_JSON [STUDIES_ROOT]

IDS_JSON is a list of [label, experiment_id]; the ids used for the 264-run check are in docs/ecosystem/evidence/replay_meos*.json. The stored studies live in
the ``backend/experiments/studies`` directory of the checkout that produced them (default: the zrs checkout)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

DEFAULT_ROOT = Path("/Users/user/Desktop/BIM/xeno-ziran-runtime-zrs/backend/experiments/studies")


def main() -> None:
    backend, ids_path, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    root = Path(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_ROOT
    sys.path.insert(0, str(backend))
    from xzr.study import runner

    t0 = time.time()
    total = agree = 0
    studies = []
    for label, sid in json.loads(ids_path.read_text()):
        study = runner.Study(root / sid)
        n = ok = 0
        bad = []
        for f in sorted(study.run_files()):
            arm, k = f.stem.rsplit("__", 1)
            r = runner.replay_run(study, arm, int(k))
            n += 1
            ok += bool(r["agreement"])
            if not r["agreement"]:
                bad.append([arm, int(k), r["metrics_differing"]])
        total += n
        agree += ok
        studies.append({"environment": label, "experiment_id": sid, "runs": n, "agree": ok, "mismatch": bad})
        print(label, n, ok, flush=True)
    secs = round(time.time() - t0, 1)
    print("TOTAL", agree, "/", total, secs, "s")
    out_path.write_text(json.dumps({"backend": str(backend), "seconds": secs, "total_runs": total, "total_agree": agree, "studies": studies}, indent=1))


if __name__ == "__main__":
    main()
