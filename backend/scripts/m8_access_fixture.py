"""Fixture for the M8 viewer: what each system could experimentally access at each decision step, computed by the
backend itself (xzr/lab/science.py `coverage` and `candidates`), for published records.

The high-fidelity viewer derives "experimentally accessible" from recorded state (coverage, material, containment,
isolation, reach). This fixture is the backend's own answer for the same steps; a frontend test compares the two.
The re-executed run is checked against the published record (runtime fingerprint at every step).

Usage: cd backend && PYTHONPATH=. python scripts/m8_access_fixture.py <record.json> <out.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from xzr.lab.record import LabRun
    rec = json.loads(Path(sys.argv[1]).read_text())
    r = LabRun(rec["config"])
    sci = r.science
    assert sci is not None
    steps = []
    while not r.done:
        out = r.step()
        st = out["step"]
        i = len(r.steps) - 1
        if rec["steps"][i]["fingerprint"] != st["fingerprint"]:
            raise SystemExit(f"re-executed run differs from the record at step {st['t']}")
        if st["t"] % 4:
            continue
        sci.invalidate()
        row = {"i": i, "t": st["t"], "systems": {}}
        for sid, s in sci.systems.items():
            cov = sci.coverage(s)
            row["systems"][sid] = {"coverage": sorted(cov), "accessible": sorted(f"{a}>{b}" for a, b in sci.candidates(s, cov))}
        steps.append(row)
    Path(sys.argv[2]).write_text(json.dumps({"record": Path(sys.argv[1]).name, "steps": steps}, separators=(",", ":")))
    print(sys.argv[2], len(steps), "decision steps")


if __name__ == "__main__":
    main()
