"""Stage 6, Pipeline A: Experiments M-Q and the derived readings, on one protocol for single and combined repairs.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6.py        # needs experiments_stage6_raw.jsonl.gz (meos_experiments_stage6_explore.py); about 4 minutes

Protocol (the same for a single action and for a pair), fixed before the runs were read:
  exploration  seeds 1-5   every setting; a setting that is *effective* on all five is a candidate.
  validation   seeds 6-10  every candidate is run again; it is *validated* only if it is effective on all five. A candidate that is effective on 3 or 4 of the 5 validation seeds, or a setting effective on 3 or 4 of the 5 exploration seeds, is a *near miss*:
               the data cannot separate it, it is kept and it makes the stress INCONCLUSIVE if nothing is validated.
  evaluation   seeds 11-30 validated settings and near misses are evaluated (reported; never used to choose).
Nothing is dropped: a candidate that failed validation is in the output with its validation result.

Writes docs/ecosystem/experiments_stage6.json and experiments_stage6_raw_combined.jsonl.gz."""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import repair6 as R
from xzr.meos import stage6_experiments as S6

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
OUT = DOCS / "experiments_stage6.json"


def eff_seeds(rs: list[dict]) -> int:
    return sum(1 for r in rs if all(r["ok"]) and not r["secondary"] and not r["exhausted"])


def main() -> None:
    t0 = time.time()
    raw = S6.load_raw()
    table = S6.stress_action_table(raw)
    cl = S6.cells(raw)
    # ---------------------------------------------------------------- A1: single actions
    cand = sorted(k for k, rs in cl.items() if k[1] and S6.effective(rs))
    vres = S6.validate_all(cand)
    validated = {k for k in cand if S6.effective(vres[k])}
    s_near = {k for k in cand if k not in validated and 3 <= eff_seeds(vres[k]) < 5} | {k for k, rs in cl.items() if k[1] and 3 <= eff_seeds(rs) < 5}
    single_eval_keys = sorted(validated | s_near)
    ev = S6.evaluate_all(single_eval_keys)
    # ---------------------------------------------------------------- A2: combined repairs on the stresses no single world-state action recovers at the decision tick
    single_b_at_113 = {k[0] for k in validated if k[4] == R.T_ACT and R.ACTIONS[k[1]].klass == "B"}
    q_stresses = tuple(s for s in R.STRESS_ORDER if s not in single_b_at_113)
    crows = S6.explore_combined(q_stresses)
    with gzip.open(DOCS / "experiments_stage6_raw_combined.jsonl.gz", "wt") as f:
        for r in crows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    cc = S6.combined_cells(crows)
    ccand = sorted(k for k, rs in cc.items() if S6.effective(rs))
    cvres = {k: [S6._cjob((k[0], k[1], k[2], sd)) for sd in R.VALIDATION_SEEDS] for k in ccand}
    cvalidated = {k for k in ccand if S6.effective(cvres[k])}
    c_near = {k for k in ccand if k not in cvalidated and 3 <= eff_seeds(cvres[k]) < 5} | {k for k, rs in cc.items() if 3 <= eff_seeds(rs) < 5}
    # a combined repair is a *combined* recovery only if none of its parts is effective alone at that tick (otherwise the second part adds nothing)
    csyn = {k for k in cvalidated if not any((k[0], a, m, d, k[2]) in validated for (a, m, d) in k[1])}
    cev = {k: [S6._cjob((k[0], k[1], k[2], sd)) for sd in R.EVAL_SEEDS] for k in sorted(cvalidated | c_near)}

    def status(k: tuple, v: set, nm: set) -> str:
        return "validated" if k in v else "near miss" if k in nm else "failed validation"

    # ---------------------------------------------------------------- derived
    mins = S6.minimum_effective(table, validated)
    rep = {}
    for sid in R.STRESS_ORDER:
        def has(klass: str, tick: int | None, sid: str = sid) -> bool:
            return any(k[0] == sid and R.ACTIONS[k[1]].klass == klass and (tick is None or k[4] == tick) for k in validated)
        comb = {tick: any(k[0] == sid and (tick is None or k[2] == tick) for k in csyn) for tick in (None, R.T_ACT)}
        near = any(k[0] == sid for k in s_near | c_near)
        ticks_s = sorted({k[4] for k in validated if k[0] == sid})
        ticks_c = sorted({k[2] for k in csyn if k[0] == sid})
        all_t = sorted(set(ticks_s) | set(ticks_c))
        rep[sid] = {
            "at_decision_tick_113": S6.classify_repairability(has("A", R.T_ACT), has("B", R.T_ACT), comb[R.T_ACT], any(k[0] == sid and (k[4] if len(k) == 5 else k[2]) == R.T_ACT for k in s_near | c_near)),
            "at_any_tested_tick": S6.classify_repairability(has("A", None), has("B", None), comb[None], near),
            "internal_validated_ticks": sorted({k[4] for k in validated if k[0] == sid and R.ACTIONS[k[1]].klass == "A"}), "world_single_validated_ticks": sorted({k[4] for k in validated if k[0] == sid and R.ACTIONS[k[1]].klass == "B"}),
            "world_combined_synergistic_ticks": ticks_c, "world_combined_synergistic": [{"parts": list(map(list, k[1])), "t": k[2]} for k in sorted(csyn) if k[0] == sid][:40],
            "earliest_effective_tick_grid": all_t[0] if all_t else None, "latest_effective_tick_grid": all_t[-1] if all_t else None,
            "latest_effective_tick_by_action": {a: max(k[4] for k in validated if k[0] == sid and k[1] == a) for a in R.RUNNABLE if any(k[0] == sid and k[1] == a for k in validated)},
            "near_miss": near,
        }
    maps = [S6.phase_map(table, sid, aid) for sid in R.STRESS_ORDER for aid in R.RUNNABLE if S6.applicable(aid, sid) and aid != "internal.m2_tap"]

    def single_row(k: tuple) -> dict:
        rs = cl[k]
        s = S6.summarise(rs)
        v = vres.get(k)
        return {"stress": k[0], "action": k[1], "klass": R.ACTIONS[k[1]].klass, "magnitude": k[2], "duration": k[3], "t": k[4], "exploration_effective": f"{eff_seeds(rs)}/{len(rs)}", "validation_effective": f"{eff_seeds(v)}/{len(v)}" if v else None,
                "status": status(k, validated, s_near), "evaluation": S6.wilson_rate(ev[k]) if k in ev else None, "evaluation_outcomes_long": S6._count([r["outcome"][2] for r in ev[k]]) if k in ev else None,
                "horizons_exploration": {"short": s["short"], "medium": s["medium"], "long": s["long"]}, "latency_median": s["latency_median"], "secondary_collapse": s["secondary_collapse"],
                "costs": {"raw": {"energy_use": s["energy_use_raw"], "collateral": s["collateral"], "switching": s["switching"]}, "energy_rate_norm": s["energy_rate_norm"]}, "costly": S6.costly(s)}

    def comb_row(k: tuple) -> dict:
        rs, v, e = cc[k], cvres.get(k), cev.get(k)
        return {"stress": k[0], "parts": list(map(list, k[1])), "t": k[2], "exploration_effective": f"{eff_seeds(rs)}/{len(rs)}", "validation_effective": f"{eff_seeds(v)}/{len(v)}" if v else None, "status": status(k, cvalidated, c_near),
                "synergistic": k in csyn, "evaluation": S6.wilson_rate(e) if e else None, "evaluation_outcomes_long": S6._count([r["outcome"][2] for r in e]) if e else None,
                "costs": {"switching": len(k[1]), "collateral": round(sum(r["raw"]["collateral"] for r in e) / len(e), 4), "energy_rate_norm": round(sum(r["norm"]["persistence_energy_rate"] for r in e) / len(e), 4)} if e else None}

    res = {
        "engine": E.ENGINE_VERSION, "baseline_result_digest": "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5", "seconds": None,
        "seeds": {"exploration": list(R.SEARCH_SEEDS), "validation": list(R.VALIDATION_SEEDS), "evaluation": [R.EVAL_SEEDS[0], R.EVAL_SEEDS[-1]]}, "stress_tick": R.STRESS_TICK, "decision_tick": R.T_ACT, "ticks_tested": list(S6.TIMINGS), "combined_ticks": list(S6.COMBO_TICKS),
        "horizons": R.HORIZONS, "recovery_window": R.W, "criteria": S6.__doc__, "protocol": __doc__, "actions": R.action_table(), "stresses": {s.id: {"family": s.family, "label": s.label} for s in R.STRESSES.values()},
        "counts": {"exploration_runs": len(raw), "exploration_cells": len(cl), "single_candidates": len(cand), "single_validated": len(validated), "single_near_miss": len(s_near), "combined_runs": len(crows), "combined_cells": len(cc), "combined_candidates": len(ccand),
                   "combined_validated": len(cvalidated), "combined_synergistic": len(csyn), "combined_near_miss": len(c_near)},
        "no_action": [r for r in table if r["action"] == "no action"],
        "single_settings": [single_row(k) for k in single_eval_keys + [k for k in cand if k not in single_eval_keys]],
        "combined_stresses": list(q_stresses), "combined_settings": [comb_row(k) for k in sorted(set(ccand) | c_near)],
        "minimum_effective": mins, "repairability": rep, "phase_maps": maps, "table": table,
    }
    res["seconds"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(res, indent=0))
    print(f"wrote {OUT} in {res['seconds']} s; counts {res['counts']}")
    for sid, r in rep.items():
        print(f"{sid[:28]:28} t113: {r['at_decision_tick_113']:30} any: {r['at_any_tested_tick']:28} grid window {r['earliest_effective_tick_grid']}-{r['latest_effective_tick_grid']}")


if __name__ == "__main__":
    main()
