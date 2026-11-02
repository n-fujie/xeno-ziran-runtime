"""Stage 6 regression: a re-run of parts of the Stage 5 experiments with the Stage 6 tree, compared with the saved Stage 5 results (nothing is overwritten).

    PYTHONPATH=backend python backend/scripts/reproduce_stage5_subset.py         # about 5 minutes

  - experiment L, 'history lost': every set of components at tick 113 (512 sets, seeds 1-5): the sets that persist, the validated cheapest set;
  - experiment F, condition F14: the exhaustive search (1024 sets, seeds 1-5) and the validation (6-10): the validated MFS and their composition;
  - experiment F, F8 (one validated MFS: the second candidate did not survive) and F9 (no retaining set);
  - the adaptive controller's first decisions in every scenario (the diagnosis of why it did not act);
  - the Stage 4 strict nulls (collision and stale on A1 and A2 leave the dynamics identical to the control);
  - the baseline result digest and trace digest.
Writes docs/ecosystem/evidence/stage5_reproduction_stage6.json."""

from __future__ import annotations

import json
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import mfs5 as M5
from xzr.meos import midrun as ML

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"


def main() -> None:
    s5 = json.loads((DOCS / "experiments_stage5.json").read_text())["experiments"]
    mid = json.loads((DOCS / "experiments_stage5_midrun.json").read_text())
    out: dict = {}
    r = ML.l1_existence("history lost")
    saved = mid["L1_existence"]["history lost"]
    out["L_history_lost"] = {"persisting_on_all_search_seeds": [r["persisting_on_all_search_seeds"], saved["persisting_on_all_search_seeds"]], "any_validated": [r["any_validated"], saved["any_validated"]], "cheapest_set": [r["cheapest_persisting_sets"][0]["retained"], saved["cheapest_persisting_sets"][0]["retained"]],
                             "validation": [r["cheapest_persisting_sets"][0]["validation_persists"], saved["cheapest_persisting_sets"][0]["validation_persists"]], "identical": r["persisting_on_all_search_seeds"] == saved["persisting_on_all_search_seeds"] and r["cheapest_persisting_sets"][0]["retained"] == saved["cheapest_persisting_sets"][0]["retained"]}
    cond = next(c for c in M5.conditions_f() if c["id"] == "F14")
    res = M5.search(cond)
    got = sorted(sorted(m["retained_components"]) for m in res["mfs"])
    was = sorted(sorted(m["retained_components"]) for m in s5["F"]["by_condition"]["F14"]["mfs"])
    out["F14_search"] = {"mfs_found": got, "mfs_saved": was, "identical": got == was, "digests_identical": sorted(m["digest"] for m in res["mfs"]) == sorted(m["digest"] for m in s5["F"]["by_condition"]["F14"]["mfs"])}
    for cid, expect_n in (("F8", 1), ("F9", 0)):  # F8: one validated MFS (the second candidate did not survive); F9: no retaining set
        c = next(c for c in M5.conditions_f() if c["id"] == cid)
        r_ = M5.search(c)
        saved_f = s5["F"]["by_condition"][cid]
        out[f"{cid}_search"] = {"validated_mfs": len(r_["mfs"]), "saved": len(saved_f["mfs"]), "expected": expect_n, "composition_identical": sorted(sorted(m["retained_components"]) for m in r_["mfs"]) == sorted(sorted(m["retained_components"]) for m in saved_f["mfs"]), "identical": len(r_["mfs"]) == len(saved_f["mfs"]) == expect_n}
    from xzr.meos import reconf as RC
    from xzr.meos import stage4 as S4
    from xzr.meos import stage5_experiments as X5
    ad = json.loads((DOCS / "experiments_stage5_adaptive_diagnosis.json").read_text())
    lib = RC.library_from(s5["F"]["by_condition"])
    arrangement = {"tap": M5.M2_BASE, "tap_feature": "direct", "universe": M5.COMPONENTS5}
    import copy

    ok = True
    for row in ad["rows"]:
        first = []
        for sd in row["seeds"]:
            cfg = X5.X.cfg_with(E.default_config(), seed=sd, horizon=300)
            rec_ = RC.run_controlled(cfg, [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}, *copy.deepcopy(X5.SCENARIOS[row["scenario"]][0])], RC.Controller("adaptive", lib, arrangement, noise=0.05, seed=sd))
            d = [e for e in rec_["controller"]["log"] if e["kind"] == "decide"]
            first.append("switch" if d and not d[0].get("outcome", "").startswith(("no switch", "no known")) else "already wholly enabled (cost 0, no action)" if d and d[0]["outcome"].startswith("no switch") else "other")
        ok = ok and {k: first.count(k) for k in set(first)} == row["first_decision"]
    out["adaptive_controller_first_decisions"] = {"identical": ok}
    nulls = {}
    for mode, extra in (("collision", {}), ("stale", {"duration": 30})):  # Stage 4 strict nulls: collision and stale on A1/A2 at tick 100 leave the dynamics identical to the control
        cfg = E.default_config()
        ctl = S4.dynamics_digest(E.run_record(cfg, []))
        nulls[mode] = all(S4.dynamics_digest(E.run_record(cfg, [{"tick": 100, "op": "ADDRESS", "target": tg, "mode": mode, **extra}])) == ctl for tg in ("A1", "A2"))
    out["stage4_strict_nulls"] = {"collision_and_stale_identical_to_control": nulls, "identical": all(nulls.values())}
    rec = E.run_record(E.default_config(), [])
    out["baseline"] = {"engine": E.ENGINE_VERSION, "result_digest": rec["result_digest"], "result_digest_unchanged": rec["result_digest"] == "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5", "trace_digest": rec.get("trace_digest"), "trace_digest_unchanged": str(rec.get("trace_digest", "")).startswith("bd3e5886")}
    out["all_identical"] = out["L_history_lost"]["identical"] and out["F14_search"]["identical"] and out["F8_search"]["identical"] and out["F9_search"]["identical"] and out["adaptive_controller_first_decisions"]["identical"] and out["stage4_strict_nulls"]["identical"] and out["baseline"]["result_digest_unchanged"] and out["baseline"]["trace_digest_unchanged"]
    (DOCS / "evidence" / "stage5_reproduction_stage6.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) else {a: b for a, b in v.items() if a in ("identical", "digests_identical", "result_digest_unchanged", "trace_digest_unchanged")}) for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
