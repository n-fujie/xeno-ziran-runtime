"""Stage 6 follow-up: the three newly built actions (engine meos-0.5): exploration, validation, evaluation, one-tick windows, combined repairs, and the classification with the extended action space.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_followup.py     # needs experiments_stage6.json and _refine.json; about 20 minutes on 8 cores

Writes docs/ecosystem/experiments_stage6_followup.json and experiments_stage6_followup_raw.jsonl.gz (every exploration row)."""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import repair6 as R
from xzr.meos import stage6_experiments as S6
from xzr.meos import stage6_followup as F
from xzr.meos import stage6_refine as RF

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
OUT = DOCS / "experiments_stage6_followup.json"
RAW = DOCS / "experiments_stage6_followup_raw.jsonl.gz"


def n_ok(rs: list[dict]) -> int:
    return sum(1 for r in rs if S6.row_ok(r))


def main() -> None:
    t0 = time.time()
    base = json.loads((DOCS / "experiments_stage6.json").read_text())
    rows = F.explore()
    with gzip.open(RAW, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    cl = S6.cells(rows)
    print("explored", len(rows), "runs", round(time.time() - t0), "s", flush=True)
    cand = sorted(k for k, rs in cl.items() if S6.effective(rs))
    vres = S6.validate_all(cand)
    validated = {k for k in cand if S6.effective(vres[k])}
    near = {k for k in cand if k not in validated and 3 <= n_ok(vres[k]) < 5} | {k for k, rs in cl.items() if 3 <= n_ok(rs) < 5}
    ev = S6.evaluate_all(sorted(validated | near))
    print("single: candidates", len(cand), "validated", len(validated), "near", len(near), round(time.time() - t0), "s", flush=True)

    def single_row(k: tuple) -> dict:
        rs, v = cl[k], vres.get(k)
        s = S6.summarise(rs)
        return {"stress": k[0], "action": k[1], "magnitude": k[2], "duration": k[3], "t": k[4], "exploration_effective": f"{n_ok(rs)}/{len(rs)}", "validation_effective": f"{n_ok(v)}/{len(v)}" if v else None,
                "status": "validated" if k in validated else "near miss" if k in near else "failed validation", "evaluation": S6.wilson_rate(ev[k]) if k in ev else None,
                "evaluation_outcomes_long": S6._count([r["outcome"][2] for r in ev[k]]) if k in ev else None, "horizons_exploration": {h: s[h] for h in ("short", "medium", "long")},
                "latency_median": s["latency_median"], "secondary_collapse": s["secondary_collapse"], "costs": {"raw": {"energy_use": s["energy_use_raw"], "collateral": s["collateral"], "switching": s["switching"]}, "energy_rate_norm": s["energy_rate_norm"]},
                "costly": S6.costly(s)}

    singles = [single_row(k) for k in sorted(cand + [k for k in near if k not in cand])]
    table = S6.stress_action_table(rows)
    min_rows = []  # the minimum-magnitude reading: the smallest validated magnitude of each (stress, action)
    for sid in R.STRESS_ORDER:
        for aid in F.NEW:
            ks = [k for k in validated if k[0] == sid and k[1] == aid]
            if ks:
                lo = min(k[2] for k in ks)
                min_rows.append({"stress": sid, "action": aid, "minimum_effective_magnitude": lo, "ticks_at_that_magnitude": sorted({k[4] for k in ks if k[2] == lo}), "durations_at_that_magnitude": sorted({k[3] for k in ks if k[2] == lo}),
                                 "effective_ticks": sorted({k[4] for k in ks}), "validated_settings": len(ks)})
    # ---- windows (one tick, 101-170, extended to 330 where open at 165 or later) for the minimum and the strongest validated setting of each (stress, action), and for each near miss
    targets: dict[tuple, tuple[str, list]] = {}
    for sid in R.STRESS_ORDER:
        for aid in F.NEW:
            ks = sorted(k for k in validated | near if k[0] == sid and k[1] == aid)
            if not ks:
                continue
            for k in (min(ks, key=lambda x: (x[2], x[3], x[4])), max(ks, key=lambda x: (x[2], x[3], x[4]))):
                targets[(sid, aid, k[2], k[3])] = (sid, [(aid, k[2], k[3])])
    wins = []
    for sid, parts in targets.values():
        w = RF.window(sid, parts)
        if w["latest_effective_tick"] is not None and w["latest_effective_tick"] >= 165:
            x = RF.window(sid, parts, tuple(range(171, 331)))
            w["per_tick"].update(x["per_tick"])
            eff = sorted({*w["effective_ticks"], *x["effective_ticks"]})
            w.update(effective_ticks=eff, effective_intervals=RF.intervals(eff), earliest_effective_tick=eff[0], latest_effective_tick=eff[-1], near_miss_ticks=sorted({*w["near_miss_ticks"], *x["near_miss_ticks"]}), ticks_tested=[w["ticks_tested"][0], 330])
        wins.append(w)
        print("window", sid[:22], parts, w["effective_intervals"], flush=True)
    # ---- combined repairs
    crows = F.explore_combined(R.STRESS_ORDER)
    cc = F.by_cell(crows)
    ccand = sorted(k for k, rs in cc.items() if S6.effective(rs))
    cv = {k: [S6._cjob((k[0], [list(p) for p in k[1]], k[2], sd)) for sd in R.VALIDATION_SEEDS] for k in ccand}
    cvalid = {k for k in ccand if S6.effective(cv[k])}
    cnear = {k for k in ccand if k not in cvalid and 3 <= n_ok(cv[k]) < 5} | {k for k, rs in cc.items() if 3 <= n_ok(rs) < 5}
    cev = {k: [S6._cjob((k[0], [list(p) for p in k[1]], k[2], sd)) for sd in R.EVAL_SEEDS] for k in sorted(cvalid | cnear)}
    # the Stage 6 validated single settings (the original action space), to test synergy
    old_valid = {(r["stress"], r["action"], r["magnitude"], r["duration"], r["t"]) for r in base["single_settings"] if r["status"] == "validated"}
    all_valid = old_valid | validated
    csyn = {k for k in cvalid if not any((k[0], a, m, d, k[2]) in all_valid for (a, m, d) in k[1])}
    print("combined: candidates", len(ccand), "validated", len(cvalid), "synergistic", len(csyn), "near", len(cnear), round(time.time() - t0), "s", flush=True)
    comb = []
    for k in sorted(set(ccand) | cnear):
        e = cev.get(k)
        comb.append({"stress": k[0], "parts": [list(p) for p in k[1]], "t": k[2], "exploration_effective": f"{n_ok(cc[k])}/{len(cc[k])}", "validation_effective": f"{n_ok(cv[k])}/{len(cv[k])}" if k in cv else None,
                     "status": "validated" if k in cvalid else "near miss" if k in cnear else "failed validation", "synergistic": k in csyn, "evaluation": S6.wilson_rate(e) if e else None,
                     "evaluation_outcomes_long": S6._count([r["outcome"][2] for r in e]) if e else None})
    # ---- classification: the original action space (Stage 6) and the extended one
    old_comb = {(r["stress"], tuple(map(tuple, r["parts"])), r["t"]) for r in base["combined_settings"] if r["status"] == "validated" and r["synergistic"]}
    cls = {}
    for sid in R.STRESS_ORDER:
        def has(klass: str, tick: int | None, valid: set, sid: str = sid) -> bool:
            return any(k[0] == sid and (R.ACTIONS[k[1]].klass if k[1] in R.ACTIONS else R.FOLLOWUP[k[1]].klass) == klass and (tick is None or k[4] == tick) for k in valid)

        def hc(tick: int | None, syn: set, sid: str = sid) -> bool:
            return any(k[0] == sid and (tick is None or k[2] == tick) for k in syn)

        def nm(tick: int | None, singles_nm: set, combo_nm: set, sid: str = sid) -> bool:
            return any(k[0] == sid and (tick is None or (k[4] if len(k) == 5 else k[2]) == tick) for k in singles_nm | combo_nm)

        old_nm = {(r["stress"], r["action"], r["magnitude"], r["duration"], r["t"]) for r in base["single_settings"] if r["status"] == "near miss"}
        old_cnm = {(r["stress"], tuple(map(tuple, r["parts"])), r["t"]) for r in base["combined_settings"] if r["status"] == "near miss"}
        row = {}
        for label, valid, syn, snm, cnm in (("original", old_valid, old_comb, old_nm, old_cnm), ("extended", all_valid, old_comb | csyn, old_nm | near, old_cnm | cnear)):
            for tag, tick in (("at_decision_tick_113", R.T_ACT), ("at_any_tested_tick", None)):
                row[f"{label}_{tag}"] = S6.classify_repairability(has("A", tick, valid), has("B", tick, valid), hc(tick, syn), nm(tick, snm, cnm))
        cls[sid] = row
    res = {"engine": E.ENGINE_VERSION, "protocol": F.__doc__, "actions": R.followup_table(), "seeds": {"exploration": list(R.SEARCH_SEEDS), "validation": list(R.VALIDATION_SEEDS), "evaluation": [R.EVAL_SEEDS[0], R.EVAL_SEEDS[-1]]},
           "ticks_tested": list(S6.TIMINGS), "combined_ticks": list(S6.COMBO_TICKS), "counts": {"exploration_runs": len(rows), "single_candidates": len(cand), "single_validated": len(validated), "single_near_miss": len(near), "combined_runs": len(crows),
           "combined_candidates": len(ccand), "combined_validated": len(cvalid), "combined_synergistic": len(csyn), "combined_near_miss": len(cnear)}, "single_settings": singles, "minimum_effective": min_rows, "windows": wins,
           "combined_settings": comb, "classification": cls, "table": table, "seconds": round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(res, indent=0))
    print("wrote", OUT, res["seconds"], "s")
    for sid, c in cls.items():
        print(sid[:28].ljust(28), c["original_at_decision_tick_113"], "->", c["extended_at_decision_tick_113"], "|", c["original_at_any_tested_tick"], "->", c["extended_at_any_tested_tick"])


if __name__ == "__main__":
    main()
