"""The reproducible record of an experiment of the laboratory: the specification, the seeds, the model version, the results, the shapes, the comparisons, the five levels of every candidate, the twelve questions of the research
object, the figure and the NEGATIVE results, with digests. ``restore`` re-runs the specification and checks that the digests are the same: the history of an experiment is recovered by running it again, not by trusting a stored copy."""

from __future__ import annotations

from . import MODEL_VERSION
from .compare import attribution_tests, compare_models
from .domains import STATUS, domain_registry
from .lab import FULL, SEEDS, Observation, run_domain
from .model import FIGURE_KINDS, LIMITS, PROHIBITED_INFERENCES, ResearchObject, attribute, digest
from .shape import build_shape, structural_similarity

MAX_SEEDS = 20


def observation_from(d: dict | None) -> Observation:
    base = FULL.asdict()
    base.update(d or {})
    for k in ("sensor_channels", "boundary"):
        base[k] = tuple(base[k])
    # the digest tells 0 and 0.0 apart (as it does for any JSON writer that drops the decimal of a whole number): the numbers are cast to the declared types so that the same specification gives the same record from any client
    for k in ("sensor_noise", "probe"):
        base[k] = float(base[k])
    for k in ("scale", "temporal_window", "speed", "resources"):
        base[k] = int(base[k])
    base["memory"] = bool(base["memory"])
    return Observation(**base)


def run_experiment(spec: dict) -> dict:
    """spec: {domain, observation (the ten axes), seeds, conditions (optional)}."""
    reg = domain_registry()
    dom_id = spec["domain"]
    dom = reg.get(dom_id)
    if dom is None:
        return {"model_version": MODEL_VERSION, "spec": spec, "executed": False, "status": STATUS.get(dom_id, {"completion": "UNKNOWN"}), "note": "this domain is specified and not executed; no substitute computation is made", "figure_kind": "CONCEPTUAL_RECONSTRUCTION"}
    obs = observation_from(spec.get("observation"))
    seeds = tuple(spec.get("seeds") or SEEDS[: getattr(dom, "seed_count", len(SEEDS))])[:MAX_SEEDS]
    conds = spec.get("conditions") or None
    res = run_domain(dom, obs, seeds, conds)
    axes = {"x": dom.x_name, "y": dom.y_name}
    shapes = {c: {s: build_shape(res, c, s, axes) for s in dom.snapshots} for c in res["conditions"]}
    similarity = structural_similarity(res) if len(res["conditions"]) > 1 else []
    out = {
        "model_version": MODEL_VERSION,
        "spec": {"domain": dom_id, "observation": obs.asdict(), "seeds": list(seeds), "conditions": conds},
        "executed": True,
        "status": STATUS[dom_id],
        "figure_kind": "EXECUTED_COMPUTATIONAL_EXPERIMENT",
        "axes": axes,
        "result": res,
        "shapes": shapes,
        "structural_similarity": similarity,
        "levels": {c: _levels(v) for c, v in res["conditions"].items()},
        "limits": LIMITS,
        "prohibited_inferences": [{"premise": p, "conclusion": c, "reason": w} for p, c, w in PROHIBITED_INFERENCES],
    }
    if dom_id == "001-knowledge":
        full = len(res["conditions"]) == len(dom.conditions)
        out["models"] = compare_models(dom, seeds, obs) if full else None
        out["attribution_tests"] = attribution_tests(res)
        out["research_objects"] = {c: asdict_ro(_knowledge_object(c, v, out)) for c, v in res["conditions"].items()}
    out["negative_results"] = negative_results(out)
    out["digest"] = digest({k: v for k, v in out.items() if k != "digest"})
    return out


def _levels(v: dict) -> dict:
    ident = [n for n, r in v["relations"].items() if r["status"] == "IDENTIFIED"]
    return attribute({"real_operation": "EXECUTED_IN_MODEL", "operational_shape": "RECONSTRUCTED" if ident else "UNRESOLVED", "conceptual_operational_shape": "NOT_MODELLED"})


def asdict_ro(o: ResearchObject) -> dict:
    import dataclasses

    return dataclasses.asdict(o)


def _knowledge_object(cond: str, v: dict, out: dict) -> ResearchObject:
    r = v["relations"]
    val = lambda n: None if r[n]["status"] != "IDENTIFIED" else round(r[n]["value"], 3)  # noqa: E731
    o = ResearchObject(id=f"001/{cond}", candidate="the non-accidentality of a judgement (a candidate characteristic: it is not assumed to be a core, necessary or invariant)")
    o.relation_to_object = "the judgement is about a hidden state of the synthetic world; the agent reaches it only through an evidence channel (and, in some conditions, a coincidental cue)"
    o.characteristic_configuration = [{"relation": n, "value": val(n), "status": r[n]["status"]} for n in r]
    o.candidate_core = ["the relations that differ from the accidental conditions: a large effect of the evidence, a small effect of the coincidental cue, correctness that holds under do(W) (an operational reading; whether a core exists is not decided)"] if r["effect_E"]["status"] == "IDENTIFIED" and (val("effect_E") or 0) > 0.5 else ["no candidate core is read from this condition"]
    o.ignition_conditions = ["the evidence channel informative about the state and read by the agent (effect of E above 0.5)"]
    o.maintenance_conditions = ["for the reconfiguring agent: the feedback on the true state; without it the cue dependence is kept"]
    o.transformation_expiry_conditions = [{"relation": "shift_drop", "value": val("shift_drop"), "meaning": "the loss of correctness when the cue decouples from the state"}]
    o.history_and_reignition = [{"relation": n, "value": val(n)} for n in ("revision_E", "revision_S")]
    o.structural_similarity = [s for s in out["structural_similarity"] if cond in (s["a"], s["b"])]
    o.competing_explanations = [next((row for row in out["models"]["rows"] if row["condition"] == cond), None)] if out.get("models") else []
    o.intervention_differences = [{"intervention": "do(E)", "relation": "effect_E", "value": val("effect_E")}, {"intervention": "do(S)", "relation": "effect_S", "value": val("effect_S")}, {"intervention": "do(W), cue decoupled", "relation": "stability_do_W", "value": val("stability_do_W")}]
    return o


def negative_results(out: dict) -> list[dict]:
    """Everything that did not come out as a difference or could not be recorded, kept: relations whose 95 % interval includes 0, relations unobserved under the observation (with the class), operational tests that failed, verdicts of
    redundancy, harm or no resolution, and the domains that were not executed."""
    neg = []
    for cond, v in out["result"]["conditions"].items():
        for n, r in v["relations"].items():
            if r["status"] != "IDENTIFIED":
                neg.append({"kind": "UNOBSERVED", "condition": cond, "relation": n, "class": r["status"]})
            elif r["ci95"][0] <= 0 <= r["ci95"][1]:
                neg.append({"kind": "NOT_DETECTED", "condition": cond, "relation": n, "mean": r["value"], "ci95": r["ci95"], "note": "no difference was detected: this is not shown to be zero"})
    for t in out.get("attribution_tests") or []:
        if t["operational_test"] in ("CRITERION_NEGATIVE", "UNRESOLVED"):
            neg.append({"kind": t["operational_test"], "condition": t["condition"], "why": t["why"]})
    for row in (out.get("models") or {}).get("rows", []):
        for vd in row["verdicts"]:
            if vd["verdict"] in ("REDUNDANT", "HARMFUL", "UNRESOLVED"):
                neg.append({"kind": vd["verdict"], "condition": row["condition"], "competitor": vd["competitor"], "why": "the candidate construction (the response to the evidence alone) did not predict held-out interventions better than the competitor" if vd["verdict"] != "UNRESOLVED" else vd.get("why", "")})
    neg.append({"kind": "NOT_DONE", "what": "competing explanations beyond a reliability statistic and a static causal model (attention, memory, predictive processing, sensorimotor, cognitive appraisal, concept learning, SNN, dynamical systems, operational-shape analysis) were not run", "domains_not_executed": [k for k, s in STATUS.items() if not s["executed"]]})
    return neg


def restore(bundle: dict) -> dict:
    """Re-run the specification of a record and compare: the experiment is recovered by running it again."""
    again = run_experiment(bundle["spec"])
    return {"restored": True, "same_digest": again.get("digest") == bundle.get("digest"), "digest_recorded": bundle.get("digest"), "digest_rerun": again.get("digest"), "spec": bundle["spec"]}


__all__ = ["run_experiment", "restore", "observation_from", "FIGURE_KINDS"]
