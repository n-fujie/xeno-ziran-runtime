"""MO / DO / ZCA / MS on the XB-TRO body model — limited instances, with the Ziran System specification quoted, not redefined.

Sources (read, not paraphrased into new definitions)
  pa-philosophy-in-audit/data/ziran.ts                    the responsibility definitions (quoted verbatim in ``SPEC``)
  pa-simulation-environment/docs/ZIRAN_CURRENT_SPECIFICATION.md   the 2026-09-05 reconciliation: status per responsibility
  pa-simulation-environment/src/ziran/address/types.ts    the ZCA address type <N, ID, t, s, b, v, p> and its four-state fields
  pa-simulation-environment/docs/ZIRAN_MO_READINESS_AUDIT.md      what an MO decision layer would need (and that none exists)

What this module is: instances of those responsibilities over *this simulated planar body*, so that the experiments here can use
them. What it is not: the Ziran System. The repository status in the specification stays as it is there (MO: NOT IMPLEMENTED,
MS: NOT IMPLEMENTED, DO: PARTIAL, ZCA: PARTIAL); nothing here upgrades it. ``STATUS`` states, per responsibility, what the
instance covers and what it leaves out. Address is not reality: no function here decides that two addresses name the same thing.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import numpy as np

from . import MODEL_VERSION, config, engine, metrics, observation, records, stats, tro, velocity, xeno14

SPEC_SOURCES = {
    "definitions": "pa-philosophy-in-audit/data/ziran.ts",
    "reconciliation": "pa-simulation-environment/docs/ZIRAN_CURRENT_SPECIFICATION.md (2026-09-05 baseline)",
    "zca_type": "pa-simulation-environment/src/ziran/address/types.ts",
    "mo_readiness": "pa-simulation-environment/docs/ZIRAN_MO_READINESS_AUDIT.md",
}

# The definitions, verbatim from data/ziran.ts (the project's own text). Not edited here.
SPEC: dict[str, dict[str, str]] = {
    "MO": {"name": "Maximal Observation Theory",
           "definition": "The responsibility for maximizing revisable observational reach across potentially relevant relations, scales, boundaries, and time intervals.",
           "not_this": "Not complete, total, or permanent recording. Actual observation stays selective and conditional, and observing can itself cost latency, perturbation, or trade-offs."},
    "DO": {"name": "Total-Relational Distributed Observation",
           "definition": "The implementation architecture for heterogeneous distributed observation, privileging no single sensor, observer, scale, or computational system. “Total-relational” means classes of relations are not excluded in advance.",
           "not_this": "Not a claim that every relation is already observed."},
    "ZCA": {"name": "Ziran Configuration Address",
            "definition": "A transversal address / provenance layer, ⟨N, ID, t, s, b, v, p⟩, giving stable reference across configuration, physical state, observation, intervention, model, gaishō, concept, theory, and system layers — without identifying those layers with one another. A linked Concept Address Layer assigns relatively stable series addresses to concepts (life, subject, belief, AI) while tracking definition, application-condition, relation, counterexample, and version changes without erasing the concept.",
            "not_this": "Not conditional activation. Address ≠ reality — a shared address shape never implies two records are the same kind of thing."},
    "MS": {"name": "Maximal-Speed Flow System",
           "definition": "Conditionally selects and reallocates executable transition paths under measured physical constraints — latency, energy, information gain, intervention reach time, reconstruction cost, recovery time — never collapsed into one speed score. Stopping can be the fastest path.",
           "not_this": "Not “Modular Switching.”"},
}

STATUS: dict[str, dict[str, Any]] = {
    "MO": {"repository_status": "NOT IMPLEMENTED — Readiness Audited (PHASE M)",
           "xbtro_instance": "mo_policy(): over the observation configuration of this body model, generate candidate changes, cost each (set-up time, apparatus "
                             "perturbation as a vector), choose among the non-dominated ones, apply, measure the actual identifiability gain and the "
                             "actual perturbation of the body, and retract a change that proves to perturb what it observes. Reach is reported as a vector.",
           "not_covered": "relations, scales, boundaries and time intervals outside this body model; redirection into unrepresented territory (a new instrument "
                          "is always one from the fixed inventory); anything outside the simulation. The cost model is nominal."},
    "DO": {"repository_status": "PARTIAL",
           "xbtro_instance": "distributed_observation(): every deployed observation model is a source with its own provenance, scale, boundary and time resolution; no "
                             "source is privileged; where several sources can estimate the same quantity their verdicts are kept side by side, and disagreement is "
                             "recorded as a conflict, never averaged away; classes of relations without any instrument are listed as unobserved, not as absent.",
           "not_covered": "real observers and real sensors; computational systems other than the simulated models"},
    "ZCA": {"repository_status": "PARTIAL — Minimal Address Layer v1",
            "xbtro_instance": "address(), address_record(), address_observation_configuration(), address_body_configuration(): addresses with the specification's "
                              "fields (namespace, localId, time, scale, boundary, version, provenance), each optional field in one of the four states "
                              "(known / unknown / not-recorded / not-applicable). The local id reuses the record's own id.",
            "not_covered": "no global registry, no address equivalence (no 'same object' function), no content-hash identity, no address resolution, no Concept Address Layer"},
    "MS": {"repository_status": "NOT IMPLEMENTED",
           "xbtro_instance": "ms_paths(): executable alternatives (sets of operation lines, Xeno-14 conditions, a stopped response) are run for one stated consequence; "
                             "each is measured on latency, energy, information gain, intervention reach time, reconstruction cost and recovery time, kept as a vector; "
                             "the non-dominated set is reported; a choice is made only under constraints stated by the caller. The stopped response is one of the paths.",
           "not_covered": "physical flows other than this body's; reallocation while running (paths are compared across runs); latency/energy of real hardware"},
}


def status() -> dict[str, Any]:
    return {"sources": SPEC_SOURCES, "spec": SPEC, "status": STATUS,
            "statement": "These are limited instances over a simulated body. The repository-level status of MO and MS in the Ziran System remains NOT IMPLEMENTED; "
                         "DO and ZCA remain PARTIAL. Nothing here is evidence about the Ziran System itself."}


# --------------------------------------------------------------------------------------------------------------- ZCA

NAMESPACE = {"RECORD": "xbtro-experiment-record", "OBSERVATION_CONFIGURATION": "xbtro-observation-configuration",
             "BODY_CONFIGURATION": "xbtro-body-configuration", "INTERVENTION": "xbtro-intervention"}
FIELD_STATES = ("known", "unknown", "not-recorded", "not-applicable")
RELATIONS = ("produced-by", "derived-from", "references", "revises")
VERSION_KINDS = ("contract-version", "record-version", "software-version", "runtime-version", "model-version", "concept-version", "audit-operation-version")


def known(value: Any) -> dict[str, Any]:
    return {"status": "known", "value": value}


def unknown() -> dict[str, Any]:
    return {"status": "unknown"}


def not_recorded() -> dict[str, Any]:
    return {"status": "not-recorded"}


def not_applicable() -> dict[str, Any]:
    return {"status": "not-applicable"}


def address(namespace: str, local_id: str, time: dict | None = None, scale: dict | None = None, boundary: dict | None = None,
            version: dict | None = None, provenance: dict | None = None) -> dict[str, Any]:
    a = {"namespace": namespace, "localId": local_id, "time": time or not_recorded(), "scale": scale or not_recorded(),
         "boundary": boundary or not_recorded(), "version": version or not_recorded(), "provenance": provenance or not_recorded()}
    validate_address(a)
    return a


def validate_address(a: dict[str, Any]) -> None:
    """Structural check against the specification's type. Raises ValueError. It checks shape only: it cannot say that an address
    names anything real."""
    if set(a) != {"namespace", "localId", "time", "scale", "boundary", "version", "provenance"}:
        raise ValueError("an address has exactly namespace, localId, time, scale, boundary, version, provenance")
    if not (isinstance(a["namespace"], str) and a["namespace"] and isinstance(a["localId"], str) and a["localId"]):
        raise ValueError("namespace and localId are mandatory text")
    for k in ("time", "scale", "boundary", "version", "provenance"):
        f = a[k]
        if f.get("status") not in FIELD_STATES or (f["status"] == "known") != ("value" in f):
            raise ValueError(f"{k}: a field is in exactly one of {FIELD_STATES}, and only 'known' carries a value")
    if a["version"]["status"] == "known":
        for v in a["version"]["value"]:
            if v.get("kind") not in VERSION_KINDS or not isinstance(v.get("value"), str):
                raise ValueError("version entries are {kind, value} with a kind from the specification")
    if a["provenance"]["status"] == "known":
        for p in a["provenance"]["value"]:
            if p.get("relation") not in RELATIONS or not isinstance(p.get("localId"), str):
                raise ValueError("provenance entries are references {namespace?, localId, relation}, never payloads")


def _ref(namespace: str, local_id: str, relation: str) -> dict[str, Any]:
    return {"namespace": namespace, "localId": local_id, "relation": relation}


def address_body_configuration(rec: dict[str, Any]) -> dict[str, Any]:
    cfg = rec["initial_configuration"]
    return address(NAMESPACE["BODY_CONFIGURATION"], f"{rec['id']}#body", scale=known({"time_step_s": cfg["task"]["dt"], "horizon_s": cfg["task"]["horizon"]}),
                   boundary=known({"links": [ln["id"] for ln in cfg["links"]], "operation_lines": len(cfg["lines"])}),
                   version=known([{"kind": "model-version", "value": MODEL_VERSION}]), provenance=not_applicable())


def address_observation_configuration(rec: dict[str, Any], k: int) -> dict[str, Any]:
    obs = rec["observation_configurations"][k]
    return address(NAMESPACE["OBSERVATION_CONFIGURATION"], f"{rec['id']}#obs{k}",
                   scale=known({m["id"]: m.get("spatial") for m in obs.get("models", [])}),
                   boundary=known({"window": obs.get("window"), "blind": {m["id"]: {"windows": m.get("blind_windows", []), "regions": m.get("blind_regions", [])}
                                                                             for m in obs.get("models", [])}}),
                   version=known([{"kind": "model-version", "value": MODEL_VERSION}]), provenance=not_applicable())


def address_record(rec: dict[str, Any]) -> dict[str, Any]:
    """The address of an experiment record. The local id is the record's own id; the references are to the body configuration and
    observation configurations of the same record and, if the history says so, to the record it was derived from."""
    refs = [_ref(NAMESPACE["BODY_CONFIGURATION"], f"{rec['id']}#body", "derived-from")]
    refs += [_ref(NAMESPACE["OBSERVATION_CONFIGURATION"], f"{rec['id']}#obs{k}", "references") for k in range(len(rec["observation_configurations"]))]
    parent = (rec.get("history") or {}).get("parent")
    if parent:
        refs.append(_ref(NAMESPACE["RECORD"], parent, "derived-from"))
    prov = rec.get("provenance", {})
    versions = [{"kind": "model-version", "value": rec["model_version"]}, {"kind": "record-version", "value": rec["schema"]}]
    if prov.get("numpy"):
        versions.append({"kind": "runtime-version", "value": f"numpy {prov['numpy']}"})
    return address(NAMESPACE["RECORD"], rec["id"], time=not_recorded(),     # the simulation is deterministic: no wall-clock time is stored
                   scale=known({"time_step_s": rec["time_step_s"], "seeds": len(rec["seeds"])}),
                   boundary=known({"experiment": rec["experiment"], "body": rec["initial_configuration"].get("name")}),
                   version=known(versions), provenance=known(refs))


# --------------------------------------------------------------------------------------------------------------- DO

def sources(run: engine.Run, obs: dict[str, Any]) -> list[dict[str, Any]]:
    """Every deployed observation model as a source, with its own provenance, scale, boundary and time resolution. Ordered as
    deployed; the order carries no priority."""
    cov = observation.coverage(run.cfg, obs)
    out = []
    for m in obs["models"]:
        out.append({"source": m["id"], "kind": m["kind"], "provenance": {"sample_hz": m["sample_hz"], "noise": m["noise"], "delay_s": m["delay_s"],
                                                                         "dropout": m["dropout"]},
                    "scale": m.get("spatial"), "boundary": {"regions": cov["models"].get(m["id"], cov["models"].get(m["kind"], [])),
                                                            "blind_windows": m.get("blind_windows", []), "blind_regions": m.get("blind_regions", [])},
                    "time_resolution_s": 1.0 / max(m["sample_hz"], 1e-9)})
    return out


def distributed_observation(run_a: engine.Run, run_b: engine.Run, obs: dict[str, Any]) -> dict[str, Any]:
    """The Total-Relational Distributed Observation of a pair of conditions under one observation configuration.

    For each catalogued relation (quantity), every usable source feature gives its own verdict on the difference between the two
    conditions. Verdicts are never merged: ``agreement`` is 'agree', 'conflict' (sources disagree on identification or on sign),
    'single-source' or 'no-source'; ``fused`` is always None. Relation classes with no instrument at all are listed explicitly."""
    ref = tro.reference_effects(run_a, run_b)
    oa, ob = observation.observe(run_a, obs), observation.observe(run_b, obs)
    fa, fb = observation.features(run_a, oa, obs), observation.features(run_b, ob, obs)
    rows = []
    for d in tro.catalog():
        cap = tro.capability(d, obs, run_a.cfg)
        per = []
        for a in cap["usable"]:
            if a["feature"] in fa and a["feature"] in fb:
                e = stats.paired_effect(fa[a["feature"]], fb[a["feature"]])
                ident = bool(np.isfinite(e["p"]) and e["p"] < tro.IDENT_P and abs(e["d"]) >= tro.IDENT_D)
                per.append({"source_feature": a["feature"], "kind": a["kind"], "proxy": a["proxy"], "d": _f(e["d"]), "p": _f(e["p"]), "n": e["n"], "identified": ident})
        if len(per) == 0:
            agreement = "no-source"
        elif len(per) == 1:
            agreement = "single-source"
        else:
            idents = {p["identified"] for p in per}
            signs = {int(np.sign(p["d"])) for p in per if p["d"] is not None and abs(p["d"]) >= tro.IDENT_D}
            agreement = "conflict" if len(idents) > 1 or len(signs) > 1 else "agree"
        r = ref[d["id"]]
        rows.append({"relation": d["id"], "label": d["label"], "family": d["family"], "exists_in_model_reference": bool(np.isfinite(r["p"]) and r["p"] < tro.EXIST_P and abs(r["d"]) >= tro.EXIST_D),
                     "capable": cap["capable"], "states": cap["states"], "per_source": per, "agreement": agreement, "fused": None})
    families = {}
    for fam in sorted({d["family"] for d in tro.catalog()}):
        rel = [r for r in rows if r["family"] == fam]
        families[fam] = {"relations": len(rel), "with_a_source": sum(1 for r in rel if r["per_source"]), "without_any_source": [r["relation"] for r in rel if not r["per_source"]],
                         "excluded_in_advance": []}       # nothing is excluded in advance: a relation without a source is reported as unobserved
    return {"sources": sources(run_a, obs), "relations": rows, "families": families, "conflicts": [r["relation"] for r in rows if r["agreement"] == "conflict"],
            "privileged_source": None}


def _f(x: float) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)


# --------------------------------------------------------------------------------------------------------------- MO

def reach(rows: list[dict[str, Any]], obs: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Observational reach as a vector (never one number): what is identified, what is instrumented, at which scales and time
    resolutions, how much of the body is outside the boundary."""
    s = tro.summarize(rows)
    cov = observation.coverage(cfg, obs)
    regions = cov["regions"]
    hz = [m["sample_hz"] for m in obs["models"]]
    return {"differences_existing": s["existing"], "differences_identified": s["identified"], "identifiability": s["identifiability"],
            "unobserved_by_reason": {k: v for k, v in s["counts"].items() if k.startswith("unobserved")},
            "instrumented_kinds": sorted({m["kind"] for m in obs["models"]}), "scales": {m["id"]: m.get("spatial") for m in obs["models"]},
            "time_resolution_hz": [min(hz), max(hz)] if hz else [0, 0],
            "unobserved_regions": cov["unobserved_regions"], "observed_region_fraction": 1.0 - len(cov["unobserved_regions"]) / max(len(regions), 1)}


def perturbation(obs: dict[str, Any]) -> dict[str, float]:
    e = observation.apparatus_effects(obs)
    return {"added_mass_kg": float(sum(e["mass_add"].values())), "added_noise": float(e["noise_add"]), "added_delay_s": float(e["delay_add_s"]),
            "tactile_gain_loss": float(1.0 - e["tactile_gain_scale"])}


def _dominates(a: dict[str, float], b: dict[str, float]) -> bool:
    keys = ("setup_s", "added_mass_kg", "neg_gain")
    return all(a[k] <= b[k] for k in keys) and any(a[k] < b[k] for k in keys)


def mo_policy(run_a: engine.Run, run_b: engine.Run, obs0: dict[str, Any], rounds: int = 4, setup_budget_s: float = 600.0,
              seeds: list[int] | None = None) -> dict[str, Any]:
    """An MO-style policy over the observation configuration of the body model (see STATUS['MO'] for its limits)."""
    from .experiments import setup_cost
    cfg = run_a.cfg
    ref = tro.reference_effects(run_a, run_b)
    obs = obs0
    rows = tro.assess(run_a, run_b, obs, ref)
    log: list[dict[str, Any]] = []
    spent = 0.0
    reach0 = reach(rows, obs, cfg)
    stop = "round limit"
    retracted: set[str] = set()
    for k in range(1, rounds + 1):
        cands = [c for c in tro.candidates(rows, obs, cfg) if c["changes"] and repr(c["changes"]) not in retracted]
        for c in cands:
            trial = tro.boundary_transformation(obs, c["changes"])["observation"]
            c["cost"] = {"setup_s": setup_cost(c["changes"]), **perturbation(trial), "neg_gain": -c["expected_identifiability"]}
        front = [c for c in cands if c["expected_identifiability"] > 0 and not any(_dominates(o["cost"], c["cost"]) for o in cands if o is not c)]
        if not front:
            stop = "no candidate with an expected gain remains"
            break
        front.sort(key=lambda c: -c["expected_identifiability"] / max(c["cost"]["setup_s"], 1.0))
        pick = front[0]
        if spent + pick["cost"]["setup_s"] > setup_budget_s:
            stop = "set-up budget would be exceeded"
            break
        tr = tro.boundary_transformation(obs, pick["changes"], reason=pick["why"],
                                         info={"difference": pick["difference"], "category": pick["category"], "front_size": len(front)},
                                         expected={"identifiability_gain": pick["expected_identifiability"], "cost": pick["cost"]})
        new_rows = tro.assess(run_a, run_b, tr["observation"], ref)
        before, after = tro.summarize(rows), tro.summarize(new_rows)
        ind = tro.induced_change(cfg, tr["observation"], seeds or run_a.seeds[:8], engine.simulate)
        perturbs = [r for r in ind["rows"] if r.get("p") is not None and r["p"] < 0.01 and abs(r.get("d") or 0) >= 0.8]   # six metrics are tested: a strict level
        entry = {"round": k, "changes": pick["changes"], "why": pick["why"], "expected": tr["record"]["expected"], "cost": pick["cost"],
                 "actual": {"identified_before": before["identified"], "identified_after": after["identified"], "existing": after["existing"],
                            "gain": after["identified"] - before["identified"]},
                 "induced_change": ind["rows"], "perturbs_the_body": [r["id"] for r in perturbs]}
        if perturbs:      # revisable: an instrument that measurably changes what it observes is retracted, and the reason is kept
            entry["decision"] = "retracted: the apparatus changes the body it observes (measured)"
            retracted.add(repr(pick["changes"]))
        elif after["identified"] < before["identified"]:
            entry["decision"] = "retracted: identification was lost"
            retracted.add(repr(pick["changes"]))
        elif after["identified"] == before["identified"]:
            entry["decision"] = "retracted: no measured gain, so the set-up and perturbation cost is not justified (the expected gain was wrong)"
            retracted.add(repr(pick["changes"]))
        else:
            entry["decision"] = "kept"
            obs, rows = tr["observation"], new_rows
            spent += pick["cost"]["setup_s"]
        log.append(entry)
    return {"rounds": log, "reach_before": reach0, "reach_after": reach(rows, obs, cfg), "setup_time_s": spent, "stopped_because": stop,
            "final_observation": obs, "not_total_recording": "unobserved_regions and unobserved_by_reason remain in reach_after: the policy does not claim total reach"}


# --------------------------------------------------------------------------------------------------------------- MS

def _paths(base: dict[str, Any]) -> list[tuple[str, dict[str, Any], bool]]:
    def off(cfg: dict[str, Any], *ids: str) -> dict[str, Any]:
        out = copy.deepcopy(cfg)
        for ln in out["lines"]:
            if ln["id"] in ids:
                ln["enabled"] = False
        return out
    return [("all lines (baseline)", base, False),
            ("without the hip balance line", off(base, "neural.central.hip"), False),
            ("without the reflex line", off(base, "neural.reflex"), False),
            ("Xeno-14: zero-run-up transition", xeno14.apply(base, ["zero-run-up-transition"]), False),
            ("Xeno-14: endpoint removal", xeno14.apply(base, ["endpoint-removal"]), False),
            ("Xeno-14: slow movement", xeno14.apply(base, ["slow-movement"]), False),
            ("stop: the response to the cue is switched off", off(base, "sens.cue", "neural.central.cue"), True)]


MS_MINIMISE = ("latency_s", "energy", "neg_information_gain", "intervention_reach_s", "lines_changed", "recovery_rmst_s", "fall_rate")


def ms_vector(run: engine.Run, base_run: engine.Run, base_cfg: dict[str, Any], obs: dict[str, Any], consequence: str) -> dict[str, Any]:
    m = metrics.summary(run)
    prof = velocity.profile(run)
    ev = metrics.events(run.cfg)
    dt = run.dt
    if consequence == "reach-target":
        # the target (within 2 bands) reached after the cue and before the protocol's push, which would otherwise move the COM by itself
        i_cue = metrics.idx(ev["cue"], dt)
        i_stop = metrics.idx(ev["pushes"][0], dt) if ev["pushes"] else run["com"].shape[1]
        near = (np.abs(run["com"] - run.cfg["task"]["x_target"]) < 2 * metrics.band(run.cfg)) & run["alive"]
        near[:, :i_cue] = False
        near[:, i_stop:] = False
        first = np.where(near.any(axis=1), near.argmax(axis=1), -1)
        lat = np.where(first >= 0, (first - i_cue) * dt, np.nan)
        reach_t = np.asarray(prof["muscle_onset"]["values"], dtype=float)
    else:  # stay upright through the disturbance: time to be settled again after the push; 0 if the body was never displaced beyond the band
        displaced = m["peak_dev"] > metrics.band(run.cfg)
        lat = np.where(run.fell | run.diverged, np.nan, np.where(displaced, m["recovery"], 0.0))
        reach_t = np.asarray(prof["correction"]["values"], dtype=float)
    ra = tro.assess(base_run, run, obs) if run is not base_run else []
    info = float(tro.summarize(ra)["identified"]) if ra else 0.0
    slow_dist = float(np.mean([np.mean(np.abs(run.slow_end[k] - base_run.slow_end[k])) for k in ("fatigue", "kc", "sediment", "core") if k in run.slow_end]))
    def enabled(c: dict[str, Any]) -> set[str]:
        return {ln["id"] for ln in c["lines"] if ln["enabled"]}
    changed = len(enabled(base_cfg) ^ enabled(run.cfg)) + len(set(run.cfg.get("xeno14") or []) ^ set(base_cfg.get("xeno14") or []))
    def mean(v):
        v = np.asarray(v, dtype=float)
        return float(np.nanmean(v)) if np.isfinite(v).any() else None
    return {"latency_s": mean(lat), "latency_defined": float(np.isfinite(lat).mean()), "energy": mean(m["energy_used"]), "information_gain": info,
            "neg_information_gain": -info, "intervention_reach_s": mean(reach_t), "lines_changed": float(changed), "slow_state_distance": slow_dist,
            "recovery_rmst_s": mean(m["recovery_rmst"]), "recovered_fraction": float(np.isfinite(m["recovery"]).mean()), "fall_rate": float(run.fell.mean()),
            "diverged_fraction": float(run.diverged.mean())}


def pareto(vectors: list[dict[str, Any]]) -> list[int]:
    """Indices of the non-dominated paths over the minimised measures (None = the consequence was not established = worst)."""
    def key(v):
        return [float("inf") if v[k] is None else v[k] for k in MS_MINIMISE]
    ks = [key(v) for v in vectors]
    out = []
    for i, a in enumerate(ks):
        if not any(all(b[j] <= a[j] for j in range(len(a))) and any(b[j] < a[j] for j in range(len(a))) for k2, b in enumerate(ks) if k2 != i):
            out.append(i)
    return out


def select(vectors: list[dict[str, Any]], constraints: dict[str, float], priority: list[str]) -> int | None:
    """Choose a path only under constraints stated by the caller (e.g. {'fall_rate': 0.0}) and a stated priority order; never
    by a combined score. Returns None if no path satisfies the constraints."""
    ok = [i for i, v in enumerate(vectors) if all(v.get(k) is not None and v[k] <= lim for k, lim in constraints.items())]
    if not ok:
        return None
    return min(ok, key=lambda i: [float("inf") if vectors[i][k] is None else vectors[i][k] for k in priority])


def ms_paths(preset: str, consequence: str, seeds: list[int], obs: dict[str, Any] | None = None, push_force: float = 60.0):
    """Generator (yields progress); returns the MS-style comparison of executable paths for one consequence."""
    from .experiments import Ctx, base_config
    obs = obs or observation.validate(observation.config("motion+emg+contact"))
    extra = {"environment": {"pushes": [{"t": 3.2, "dur": 0.12, "force": push_force, "link": 2, "point_frac": 0.8}]}}
    base = base_config(preset, extra=extra)
    paths = _paths(base)
    ctx = Ctx(len(paths))
    runs = []
    for name, cfg, _stop in paths:
        runs.append((yield from ctx.sim(cfg, seeds, None, name)))
    vectors = [ms_vector(r, runs[0], base, obs, consequence) for r in runs]
    front = pareto(vectors)
    return {"consequence": consequence, "information_gain_note": "information gain = number of reference differences, relative to the baseline path, that the observation "
            "configuration identifies; it is 0 for the baseline by construction",
            "paths": [{"path": p[0], "is_stop_path": p[2], **v, "non_dominated": i in front} for i, (p, v) in enumerate(zip(paths, vectors, strict=True))],
            "front": front, "measures": list(MS_MINIMISE), "collapsed_score": None,
            "stop_is_on_front": any(paths[i][2] for i in front)}


def digest_of(obj: Any) -> str:
    return records.digest(json.loads(json.dumps(records.clean(obj))))
