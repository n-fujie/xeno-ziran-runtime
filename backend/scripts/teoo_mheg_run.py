"""MHEG duties x fifteen guarantees: experiments MH-EXP-01 .. 04. Pre-register (freeze), run, analyse, save. Run: PYTHONPATH=. python scripts/teoo_mheg_run.py OUT_DIR [--workers N] [--check] [--only ID]

New experiment ids: the results of EXP-01..10, CMP-01 and LG2-EXP-01..07 are not touched and not re-labelled. Same discipline: protocols are frozen in a hash-chained registry before the first datum, confirmatory or exploratory is the
registry's decision, and every result is kept. There was no pilot: the code was exercised on seed 6001 only (the shape of the units; the outcomes were read for that one seed). MH-EXP-01 and 03 are Implementation Properties, MH-EXP-02
an Implementation Property with a paired contrast, MH-EXP-04 a Synthetic-world Result. The duties are functional summaries and the crosswalk is as reported (R16 not available); the guarantees' wording is held privately."""

from __future__ import annotations

import gzip
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

from xzr.teoo import legal as L
from xzr.teoo import mheg_experiments as X
from xzr.teoo import protocol as PR
from xzr.teoo import stats as S
from xzr.teoo.provenance import digest_of

SEEDS = {"MH-EXP-01": [6001], "MH-EXP-02": list(range(6101, 6131)), "MH-EXP-03": list(range(6201, 6231)), "MH-EXP-04": list(range(6301, 6331))}
CLASS = {"MH-EXP-01": "Implementation Property", "MH-EXP-02": "Implementation Property", "MH-EXP-03": "Implementation Property", "MH-EXP-04": "Synthetic-world Result"}
H = lambda i, t: {"id": i, "statement": t}  # noqa: E731


def A(i: str, h: str, outcome: str, method: str, conf: bool = True, **kw: Any) -> dict:
    return {"id": i, "hypothesis": h, "outcome": outcome, "method": method, "confirmatory": conf, **kw}


def P(eid: str, hyps: list, conds: list, control: str, outcomes: dict, analyses: list, inst: dict) -> dict:
    seeds = SEEDS[eid]
    return PR.new_protocol(experiment_id=eid, hypotheses=hyps, targets=["findings, duties and outcomes of a synthetic institution"], instrument_conditions=inst, control_condition=control, conditions=conds, seeds=seeds, trials_per_condition=1,
                           stopping_rule={"type": "fixed-n", "units": len(seeds), "no interim analysis": True}, outcomes=outcomes, analyses=analyses, multiplicity="holm", failure_conditions=[f"fewer than {len(seeds)} units"],
                           reproduction={"generator": "xzr.teoo.mheg_experiments", "steps": ["run unit per seed", "analyse"], "world": "xzr.teoo.legal (SYNTHETIC institution) and xzr.teoo.mheg (duties, crosswalk as reported, directive states)"})


def protocols() -> dict[str, tuple[dict, list]]:
    out: dict[str, tuple[dict, list]] = {}

    # ---- 01 the crosswalk as a projection
    def e01(u):
        x = u[0]
        sing, pair = x["single"], x["pair"]
        uncovered = sorted(f for f, d in sing.items() if not d)
        groups: dict[tuple, list[str]] = {}
        for f, d in sing.items():
            groups.setdefault(tuple(d), []).append(f)
        collisions = sorted([g for g in groups.values() if len(g) > 1], key=lambda g: g[0])
        sigs = {tuple(d) for d in list(sing.values()) + list(pair.values())}
        return {"method": "descriptive", "single_patterns": len(sing), "pair_patterns": len(pair), "uncovered_singles": uncovered, "single_collision_groups": collisions, "distinct_duty_signatures_among_190": len(sigs), "patterns": len(sing) + len(pair),
                "noncompensation_violations": x["noncompensation_violations"], "baseline_all_satisfied": x["baseline_all_satisfied"]}

    out["MH-EXP-01"] = (P("MH-EXP-01", [H("H1", "Removing a finding that no duty names changes no duty, and removing any other changes at least one; the only finding the crosswalk does not name is G1"),
                                         H("H2", "The duty view cannot tell some single failures apart: at least two findings share one duty signature"),
                                         H("H3", "Over the 19 single and 171 pair removals the duty signatures distinguish fewer patterns than the findings do (information is lost in the projection)"),
                                         H("H4", "No duty is SATISFIED while a finding it maps is VIOLATED, in any of the 190 patterns, and the intact institution satisfies every duty")],
                          ["crosswalk projection", "finding-level reading"], "finding-level reading", {"primary": ["uncovered findings", "collision groups", "distinct duty signatures", "non-compensation violations"], "secondary": ["duties per finding"]},
                          [A("M101", "H1", "uncovered findings", "descriptive"), A("M102", "H2", "collision groups", "descriptive"), A("M103", "H3", "distinct signatures", "descriptive"), A("M104", "H4", "violations", "descriptive")],
                          {"patterns": "19 single + 171 pair removals from a fully provisioned institution; evidence set directly (no simulation)"}),
                         [("M101", lambda u: {**e01(u), "criterion": "the findings with an empty signature are exactly ['G1'] and every other single removal changes at least one duty", "criterion_met": e01(u)["uncovered_singles"] == ["G1"]}),
                          ("M102", lambda u: {**{k: v for k, v in e01(u).items() if k in ("single_collision_groups",)}, "criterion": "at least one group of two or more findings with the same non-empty signature", "criterion_met": any(len(g) > 1 and sig for g, sig in
                                                                                                                                                                                                      [(g, [d for d in u[0]["single"][g[0]]]) for g in e01(u)["single_collision_groups"]])}),
                          ("M103", lambda u: {**{k: e01(u)[k] for k in ("distinct_duty_signatures_among_190", "patterns")}, "criterion": "distinct duty signatures < 190", "criterion_met": e01(u)["distinct_duty_signatures_among_190"] < 190}),
                          ("M104", lambda u: {"method": "descriptive", "noncompensation_violations": e01(u)["noncompensation_violations"], "baseline_all_satisfied": e01(u)["baseline_all_satisfied"], "criterion": "0 violations and the intact institution satisfies every duty",
                                              "criterion_met": e01(u)["noncompensation_violations"] == 0 and e01(u)["baseline_all_satisfied"]})])

    # ---- 02 itemising the provisions
    def rows(u):
        return [r for x in u for r in x["rows"]]

    def e02_rate(u):
        rs = [r for r in rows(u) if r["base_secured"]]
        miss = [r for r in rs if sum(r["missing"].values()) > 0]
        fa = sum(any(r["flag"][f] == "SECURED" and r["item"][f] != "SECURED" for f in r["flag"]) for r in miss)
        return {"method": "descriptive", "configurations": len(rows(u)), "base_secured": len(rs), "with_a_missing_component": len(miss), "flag_only_SECURED_but_itemised_not": fa, "rate_among_missing": fa / max(1, len(miss)),
                "itemised_states": {f: {s: int(sum(r["item"][f] == s for r in rs)) for s in ("SECURED", "PARTIAL", "ABSENT", "INDETERMINATE")} for f in ("G3", "G5", "G9", "G15A")}}

    out["MH-EXP-02"] = (P("MH-EXP-02", [H("H1", "Itemising G3, G5, G9 and G15A never raises a finding relative to the single provision"),
                                         H("H2", "A single yes/no provision reports SECURED for findings whose components are partly missing (false assurance of the single provision)"),
                                         H("H3", "Fewer configurations are advised 'continue with monitored compliance' when the provisions are itemised than when they are single yes/no provisions")],
                          ["single provision", "itemised"], "single provision", {"primary": ["findings raised by itemising", "flag-only SECURED but itemised not", "configurations advised to continue with monitoring"], "secondary": ["itemised state distribution", "duties unmet"]},
                          [A("M201", "H1", "findings raised", "descriptive"), A("M202", "H2", "false assurance", "descriptive"),
                           A("M203", "H3", "advice", "paired-sign-flip", paired=True)], {"components_present_probability": 0.85, "configurations_per_world": 8, "itemised": {k: len(v) for k, v in L.COMPONENTS.items()}}),
                         [("M201", lambda u: {"method": "descriptive", "findings_raised": int(sum(r["raised"] for r in rows(u))), "comparisons": 4 * len(rows(u)), "criterion": "0 findings raised", "criterion_met": sum(r["raised"] for r in rows(u)) == 0}),
                          ("M202", lambda u: {**e02_rate(u), "criterion": "flag-only SECURED but itemised not, in at least half of the configurations that lack a component", "criterion_met": e02_rate(u)["rate_among_missing"] >= 0.5}),
                          ("M203", lambda u: {**S.paired_sign_flip([float(sum(r["rec_flag"] == "continue with monitored compliance" for r in x["rows"]) - sum(r["rec_item"] == "continue with monitored compliance" for r in x["rows"])) for x in u], seed=31),
                                              "contrast": "configurations per world advised 'continue with monitored compliance': single provision minus itemised", "predicted_sign": 1})])

    # ---- 03 the vocabulary and the duty projection under partial audits
    def e03(u):
        keys = list(u[0]["violations"])
        tot = {k: int(sum(x["violations"][k] for x in u)) for k in keys}
        seen = sorted(set().union(*[set(x["n"]["states_seen"]) for x in u]))
        return {"method": "descriptive", "violations": tot, "findings_checked": int(sum(x["n"]["findings"] for x in u)), "duties_checked": int(sum(x["n"]["duties"] for x in u)), "audits": int(sum(x["n"]["audits"] for x in u)), "states_seen": seen,
                "criterion": "0 violations of every invariant, and all six states of the vocabulary occur", "criterion_met": all(v == 0 for v in tot.values()) and len(seen) == 6}

    out["MH-EXP-03"] = (P("MH-EXP-03", [H("H1", "Under random partial audits an unobserved applicable finding is NOT_EVALUATED, an observed indeterminate one is INSUFFICIENT_EVIDENCE, VIOLATED coincides with ABSENT, and NOT_APPLICABLE occurs only where the finding is inapplicable"),
                                         H("H2", "A duty is never SATISFIED while a mapped finding is unmet, never VIOLATED without a violated finding, and is NOT_APPLICABLE only when every mapped finding is; no total is formed")],
                          ["vocabulary and projection", "evaluator's own states"], "evaluator's own states", {"primary": ["violations of each invariant"], "secondary": ["states seen"]},
                          [A("M301", "H1", "violations", "descriptive"), A("M302", "H2", "violations", "descriptive")], {"configurations_per_world": 8, "observed_probability": 0.7, "unknown_evidence_probability": 0.12}),
                         [("M301", lambda u: {**e03(u)}), ("M302", lambda u: {**e03(u)})])

    # ---- 04 the chain, one stage broken at a time
    primary = {"classification": ("exclusion_qualified", -1), "institutional_treatment": ("exclusion_persistence", -1), "effective_access": ("overturn_rate_of_wrongful", 1), "contestation": ("overturn_rate_of_wrongful", 1),
               "revision": ("downstream_access_qualified", 1), "material_restoration": ("reentered_qualified", 1)}  # (outcome, sign of intact minus broken that is predicted: +1 intact higher; -1 broken higher)

    def stage_test(stage: str, sd: int):
        o, sg = primary[stage]
        return lambda u: {**S.paired_sign_flip([x["arms"]["intact"]["outcomes"][o] - x["arms"][stage]["outcomes"][o] for x in u], seed=sd), "contrast": f"{o}: intact minus {stage} broken", "outcome": o, "predicted_sign_of_intact_minus_broken": sg}

    def e04_h1(u):
        blind = ("legal_source", "translation", "data_representation")
        same = {s: int(sum(all(x["arms"][s]["outcomes"][o] == x["arms"]["intact"]["outcomes"][o] for o in X.OUTCOMES) for x in u)) for s in blind}
        seen = {s: int(sum(len(x["arms"][s]["own_findings_not_satisfied"]) > 0 for x in u)) for s in blind}
        return {"method": "descriptive", "worlds": len(u), "outcomes_identical_to_intact": same, "own_findings_not_satisfied": seen, "criterion": "in every world the outcomes are identical and the audit finds the stage's findings unmet", "criterion_met": all(v == len(u) for v in list(same.values()) + list(seen.values()))}

    def e04_h3(u):
        stages = X.M.CHAIN_IDS
        return {"method": "descriptive", "spillover_share": {s: float(np.mean([len(x["arms"][s]["spillover"]) > 0 for x in u])) for s in stages}, "own_violated_share": {s: float(np.mean([len(x["arms"][s]["own_findings_violated"]) > 0 for x in u])) for s in stages},
                "first_violated_stage_counts": {s: {str(k): int(sum(x["arms"][s]["first_violated_stage"] == k for x in u)) for k in {x["arms"][s]["first_violated_stage"] for x in u}} for s in stages},
                "duties_violated_mean": {s: float(np.mean([len(x["arms"][s]["duties_violated"]) for x in u])) for s in stages}}

    stg = list(primary)
    out["MH-EXP-04"] = (P("MH-EXP-04", [H("H1", "Breaking the legal source, the translation or the data representation changes none of the simulated outcomes, while the audit finds the stage's findings unmet (outcome-blind failures)"),
                                         H("H2", "Breaking a stage that the simulation carries worsens its registered primary outcome (classification: qualified people excluded; treatment: persistence of exclusion; effective access and contestation: wrongful denials overturned; revision: downstream access; restoration: qualified people re-entered)"),
                                         H("H3", "Breaking one stage is not confined to it: other stages' findings are also violated in some worlds (shared levers)")],
                          ["intact"] + list(X.M.CHAIN_IDS), "intact", {"primary": ["registered primary outcome per stage", "outcome identity for the audit-only stages"], "secondary": ["spillover", "first violated stage", "duties violated"]},
                          [A("M401", "H1", "outcomes", "descriptive")] + [A(f"M402{chr(97 + i)}", "H2", primary[s][0], "paired-sign-flip", paired=True) for i, s in enumerate(stg)] + [A("M403", "H3", "spillover", "descriptive", conf=False)],
                          {"stages": list(X.M.CHAIN_IDS), "levers": {k: v for k, v in X.M.STAGE_LEVERS.items()}}),
                         [("M401", e04_h1)] + [(f"M402{chr(97 + i)}", stage_test(s, 40 + i)) for i, s in enumerate(stg)] + [("M403", e04_h3)])
    return out


def _job(a: tuple[str, int]) -> dict:
    return X.RUN[a[0]](a[1])


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    check = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    reg_path = out / "protocol_registry.jsonl"
    if reg_path.exists() and not check and only is None:
        reg_path.unlink()
    reg = PR.ProtocolRegistry(reg_path)
    protos = {k: v for k, v in protocols().items() if only is None or k == only}
    if not check:
        for p, _ in protos.values():
            reg.register(p)
            reg.freeze(p["experiment_id"], 1, time.time())
        for p, _ in protos.values():
            reg.note_first_data(p["experiment_id"], 1, time.time() + 1.0)
    summary: dict[str, Any] = {}
    for key, (p, analyses) in protos.items():
        t0 = time.time()
        if check:
            u = X.RUN[key](p["seeds"][0])
            saved = json.loads((out / f"{key}_unit_first.json").read_text())
            summary[key] = {"replay_identical": digest_of(json.loads(json.dumps(u, default=str))) == saved["digest"]}
            continue
        with Pool(workers) as pool:
            units = pool.map(_job, [(key, s) for s in p["seeds"]])
        res: dict[str, Any] = {aid: fn(units) for aid, fn in analyses}
        fam = {a: r["p"] for a, r in res.items() if r.get("p") is not None and next(x for x in p["analyses"] if x["id"] == a).get("confirmatory")}
        for aid, h in S.holm(fam).items():
            res[aid]["p_holm"] = h["p_holm"]
            sg = res[aid].get("predicted_sign_of_intact_minus_broken", res[aid].get("predicted_sign"))
            md = res[aid].get("mean_diff")
            res[aid]["supported"] = bool(h["p_holm"] < 0.05 and md is not None and sg is not None and (md > 0) == (sg > 0))
        for a in p["analyses"]:
            res[a["id"]]["registered_class"] = reg.analysis_class(p["experiment_id"], 1, a["id"])
            res[a["id"]]["evidence_class"] = CLASS[key]
        doc = {"experiment_id": p["experiment_id"], "protocol_version": 1, "protocol_digest": PR.body_digest(p), "protocol": p, "units": len(units), "seeds": p["seeds"], "evidence_class": CLASS[key], "seconds": round(time.time() - t0, 1), "results": res,
               "catalogue": L.CATALOGUE_STATUS, "note": "results about a SYNTHETIC institution and this implementation; the twelve duties are functional summaries and their crosswalk is as reported (R16 not available); not an observation of any institution, law or person"}
        (out / f"{key}.json").write_text(json.dumps(doc, indent=1, default=str))
        (out / f"{key}_unit_first.json").write_text(json.dumps({"seed": p["seeds"][0], "digest": digest_of(json.loads(json.dumps(units[0], default=str)))}))
        with gzip.open(out / f"{key}_units.json.gz", "wt") as f:
            json.dump(units, f, default=str, separators=(",", ":"))
        summary[key] = {a: {k: res[a].get(k) for k in ("mean_diff", "p", "p_holm", "supported", "criterion_met")} for a in res}
        print(key, round(time.time() - t0, 1), "s", json.dumps(summary[key], default=str)[:700], flush=True)
    print(json.dumps(summary) if check else f"registry verify: {reg.verify()}")


if __name__ == "__main__":
    main()
