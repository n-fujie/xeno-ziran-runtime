"""EXPLORATORY analysis (not part of the frozen M9 protocol): substitute paths during an apparatus outage (M9-C X4, X4b).

At every decision of system A during the outage [T+30, T+190) after the bay-0 gantry failed without repair resources:

    available    experiments the laboratory can execute: material in the source, a source the system's reach rule
                 allows, an open target containment, and a working gantry in every bay of the transfer's route
                 (observation ignored). A first version checked only the source's bay; a substitute whose target is in
                 bay 0 still needs the failed bay-0 gantry for its last leg, so that version over-counted.
    detectable   the experiments the system itself knows as candidates (its observation)
    selectable   detectable and executable
    selected     the experiment the system chose, and whether it was executable
    executed     substitute transfers that completed (the source outside bay 0)

The runs are the confirmatory runs (fingerprints checked against results/lab9/m9c.json); the probe only reads.

Usage: cd backend && PYTHONPATH=. python scripts/m9_substitutes.py <published m9c.json> <out.json> [procs]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def one(args: tuple) -> dict:
    from xzr.lab import m9
    from xzr.lab.record import LabRun
    from xzr.lab.science import Science
    cond, i = args
    gen0, seed0 = m9.RANGES["confirm"]
    T = m9.T_EXT
    r = LabRun(m9.config(m9.M9C[cond], gen0 + i, seed0 + i))
    sci = r.science
    assert sci is not None and r.lab is not None
    lab = r.lab
    rows: list[dict] = []
    orig = Science._choose

    def probe(self, sys_, cands, cov, t):
        out = orig(self, sys_, cands, cov, t)
        if T + 30 <= t < T + 190 and sys_.spec.sid == "A":
            sp = sys_.spec
            def works(a: str, b: str) -> bool:  # every gantry on the transfer's route (source bay ... target bay)
                return all(not lab.gantries[bay].failed for bay in lab._route(lab.bay_of[a], lab.bay_of[b]))
            avail = [(a, b) for a in (c.cid for c in self.cs) if lab.contents.get(a)
                     for b in (c.cid for c in self.cs) if b != a and self._reach_ok(sp, a, b) and self.shutter(b) >= 0.5
                     and works(a, b)]
            sel = [(a, b) for a, b in cands if works(a, b)]
            ch = out[0]
            rows.append({"t": t, "available": len(avail), "detectable": len(cands), "selectable": len(sel),
                         "selected_executable": None if ch is None else bool(works(*ch))})
        return out

    Science._choose = probe  # type: ignore[method-assign]
    try:
        while not r.done:
            r.step()
    finally:
        Science._choose = orig  # type: ignore[method-assign]
    executed = sum(1 for e in sci.events if e["type"] == "material_delivered" and e["t"] >= T and
                   lab.bay_of[e["src"]] != "0")
    return {"cond": cond, "i": i, "fingerprint": r.w.engine.fingerprint(), "decisions": len(rows),
            "available_mean": float(np.mean([x["available"] for x in rows])) if rows else 0.0,
            "detectable_mean": float(np.mean([x["detectable"] for x in rows])) if rows else 0.0,
            "selectable_mean": float(np.mean([x["selectable"] for x in rows])) if rows else 0.0,
            "selected_executable_share": float(np.mean([x["selected_executable"] for x in rows
                                                        if x["selected_executable"] is not None]))
            if any(x["selected_executable"] is not None for x in rows) else None,
            "decisions_with_a_selectable_substitute": sum(1 for x in rows if x["selectable"] > 0),
            "executed_substitutes": executed}


def main() -> None:
    from xzr.hpo.experiments import clean, run_pool
    pub = json.loads(Path(sys.argv[1]).read_text())
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    runs = run_pool(one, [(c, i) for c in ("X4", "X4b") for i in range(pub["seeds"])], procs)
    for x in runs:
        x["fingerprint_matches_published"] = x["fingerprint"] == pub["fingerprints"][f"{x['cond']}/confirm/{x['i']}"]
    summ = {}
    for c in ("X4", "X4b"):
        rs = [x for x in runs if x["cond"] == c]
        summ[c] = {k: float(np.mean([x[k] for x in rs if x[k] is not None])) for k in
                   ("available_mean", "detectable_mean", "selectable_mean", "selected_executable_share",
                    "decisions_with_a_selectable_substitute", "executed_substitutes")}
        summ[c]["seeds_with_a_selectable_substitute"] = sum(1 for x in rs if x["decisions_with_a_selectable_substitute"])
        summ[c]["seeds_with_an_executed_substitute"] = sum(1 for x in rs if x["executed_substitutes"])
    out = {"exploratory": True, "definitions": __doc__.split("Usage")[0].strip(), "summary": summ,
           "all_fingerprints_match_published": all(x["fingerprint_matches_published"] for x in runs), "runs": runs}
    Path(sys.argv[2]).write_text(json.dumps(clean(out), indent=1, allow_nan=False))
    print(json.dumps(summ, indent=1), "fingerprints ok:", out["all_fingerprints_match_published"])


if __name__ == "__main__":
    main()
