"""The six standard experiments (A-F) and the helpers they share.

Every experiment is a generator: it yields ``{"stage", "progress"}`` between simulation chunks (so a host without threads can
advance it in time slices and a host with threads can report progress) and returns ``(record, slow_state)``. Nothing is shown
that was not computed: all tables and series in a record come from the runs of that experiment.

A  Observation-Cut Transformation   motion only / motion + muscle activity + contact force / dynamic observation change
B  Sensorimotor Coupling            feedback delay, block, reconnection; coupling reconstruction with interventional evidence
C  Fragility Transfer               the fourteen Xeno-14 conditions and pairs of them against a matched control
D  Operational Velocity             ten separate velocity measures; established / varied / lapsed (and why)
E  Adaptive Observation             the observation configuration is changed automatically; reason, information, expected, actual
F  Human-Machine Operational Comparison   a human-like and a machine-like nominal body against one stated consequence
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import MODEL_VERSION, config, coupling, engine, metrics, observation, records, stats, tro, velocity, xeno14

SETUP_S = {"posture": 60.0, "emg": 90.0, "imu": 30.0, "contact": 30.0, "respiration": 20.0, "eeg": 120.0, "latency": 5.0,
           "threshold": 45.0, "set": 10.0, "window": 5.0, "remove": 5.0}
MAX_SEEDS = 32

# The short protocol of the experiments (the default protocol, config.build() without overrides, has no push and a longer
# horizon). Windows: cue 0.8 s -> settling until the push at 3.2 s -> recovery until the turn at 5.2 s -> settling until 7.5 s.
PROTOCOL = {
    "task": {"horizon": 7.5, "t_cue": 0.8, "t_turn": 5.2, "ramp_s": 0.3, "x_target": 0.035, "x_turn": -0.02},
    "environment": {"pushes": [{"t": 3.2, "dur": 0.12, "force": 35.0, "link": 2, "point_frac": 0.8}]},
}

EXPERIMENTS: dict[str, dict[str, Any]] = {
    "A": {"title": "Observation-Cut Transformation", "n_seeds": 12, "sims": 2,
          "question": "Does changing the observation configuration change which differences between two body conditions are identified, and why do the rest stay unobserved?",
          "params": {"alteration": ["mixed", "delay-only", "tone-only", "fatigue-only"], "rounds": [1, 6]}},
    "B": {"title": "Sensorimotor Coupling", "n_seeds": 10, "sims": 10,
          "question": "How do feedback delay, block and reconnection change the body's operation lines, transitions and couplings, and which couplings are supported by intervention rather than by correlation?",
          "params": {}},
    "C": {"title": "Fragility Transfer", "n_seeds": 8, "sims": 18,
          "question": "Does improving one organization (by a Xeno-14 condition) weaken another, and which conditions do nothing or make things worse?",
          "params": {"principles": "list of principle ids (default all fourteen)", "combos": [True, False]}},
    "D": {"title": "Operational Velocity", "n_seeds": 12, "sims": 10,
          "question": "How fast do separate operations take hold, and when does a velocity description vary or lapse, and why?",
          "params": {}},
    "E": {"title": "Adaptive Observation", "n_seeds": 12, "sims": 2,
          "question": "When the observation configuration is changed automatically for unobserved differences, does identifiability change as expected?",
          "params": {"rounds": [1, 6], "alteration": ["mixed", "delay-only", "tone-only", "fatigue-only"]}},
    "F": {"title": "Human-Machine Operational Comparison", "n_seeds": 10, "sims": 14,
          "question": "For one stated consequence, how do a human-like and a machine-like nominal body compare in speed, resources, correction and reachability?",
          "params": {}},
}


class ExperimentError(ValueError):
    pass


def catalog() -> list[dict[str, Any]]:
    return [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "sims"}, "default_n_seeds": v["n_seeds"]} for k, v in EXPERIMENTS.items()]


# ------------------------------------------------------------------------------------------------ helpers

class Ctx:
    """Progress bookkeeping for one experiment run."""

    def __init__(self, total: int) -> None:
        self.total = max(total, 1)
        self.done = 0

    def sim(self, cfg: dict[str, Any], seeds: list[int], slow: dict[str, Any] | None = None, label: str = ""):
        gen = engine.simulate(cfg, seeds, slow, chunk=100)
        while True:
            try:
                frac = next(gen)
            except StopIteration as stop:
                self.done += 1
                return stop.value
            yield {"stage": label, "progress": (self.done + frac) / self.total}


def base_config(preset: str, short: bool = True, extra: dict[str, Any] | None = None, push: bool = True) -> dict[str, Any]:
    over: dict[str, Any] = copy.deepcopy(PROTOCOL) if short else {}
    if not push and "environment" in over:
        over["environment"]["pushes"] = []
    if extra:
        over = config.deep_merge(over, extra)
    return config.build(preset, over)


def seeds_for(params: dict[str, Any], default: int) -> list[int]:
    n = int(params.get("n_seeds", default))
    if not 4 <= n <= MAX_SEEDS:
        raise ExperimentError(f"n_seeds must be within 4..{MAX_SEEDS}")
    base = int(params.get("seed", 1000))
    return [base + i for i in range(n)]


def alteration(cfg: dict[str, Any], kind: str) -> dict[str, Any]:
    """The hidden body change the observation experiments try to detect. All variants only edit configuration values."""
    out = copy.deepcopy(cfg)
    by = {ln["id"]: ln for ln in out["lines"]}
    if kind in ("mixed", "delay-only"):
        for lid in ("sens.proprio", "sens.vestibular", "sens.tactile"):
            by[lid]["timescale_s"] += 0.02
    if kind in ("mixed", "tone-only"):
        out["neural"]["cocontraction_base"] = out["neural"]["cocontraction_base"] * 2.4
    if kind in ("mixed", "fatigue-only"):
        out["internal"]["fatigue_rate"] = out["internal"]["fatigue_rate"] * 3.0
    if kind == "mixed":
        out["internal"]["breath_amp"] = out["internal"]["breath_amp"] * 2.5
    if kind not in ("mixed", "delay-only", "tone-only", "fatigue-only"):
        raise ExperimentError(f"unknown alteration {kind!r}")
    return config.validate(out)


def decimated_series(run: engine.Run, key: str, every: int = 5, component: int | None = None) -> dict[str, Any]:
    x = run[key] if component is None else run[key][:, :, component]
    x = x[:, ::every]
    t = (np.arange(x.shape[1]) * every * run.dt)
    return {"t": t, "mean": np.nanmean(x, axis=0), "sd": np.nanstd(x, axis=0)}


def table(name: str, title: str, columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {"name": name, "title": title, "columns": columns, "rows": rows}


def status_rows(rows: list[dict[str, Any]], label: str) -> list[list[Any]]:
    out = []
    for r in rows:
        out.append([label, r["id"], r["label"], "yes" if r["reference"]["exists"] else "no", r["reference"]["d"], r["status"], r["reason"] or "",
                    r["identified_by"] or "", (r["observed"] or {}).get("d"), (r["observed"] or {}).get("p")])
    return out


STATUS_COLUMNS = ["configuration", "difference", "label", "exists in model reference", "reference d", "status", "reason unobserved",
                  "identified by feature", "observed d", "observed p"]


def unobserved_entries(rows: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    return [{"id": r["id"], "status": r["status"] if r["status"] != "unobserved" else "unobserved", "reason": r["reason"], "configuration": label}
            for r in rows if r["reference"]["exists"]]


def setup_cost(changes: list[dict[str, Any]]) -> float:
    c = 0.0
    for ch in changes:
        c += SETUP_S.get(ch.get("kind", ch["op"]), 10.0) if ch["op"] == "add" else SETUP_S.get(ch["op"], 10.0)
    return c


def _scalar(x: Any) -> Any:
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else x


# ------------------------------------------------------------------------------------------------ A and E: observation

def _observation_rounds(ra: engine.Run, rb: engine.Run, obs0: dict[str, Any], ref: dict[str, Any], rounds: int, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Automatic observation reconfiguration: each round assesses, takes the most promising candidate changes for the differences
    that exist but are not identified, applies them, and records the reason, the information used, the expectation and the result."""
    log: list[dict[str, Any]] = []
    obs = obs0
    rows = tro.assess(ra, rb, obs, ref)
    elapsed = 0.0
    for k in range(1, rounds + 1):
        summ = tro.summarize(rows)
        cands = [c for c in tro.candidates(rows, obs, cfg) if c["changes"]]
        cands.sort(key=lambda c: -c["expected_identifiability"] / max(setup_cost(c["changes"]), 1.0))
        if not cands:
            log.append({"round": k, "stopped": True, "why": "no candidate change remains for an existing, unidentified difference",
                        "identified": summ["identified"], "existing": summ["existing"]})
            break
        chosen: list[dict[str, Any]] = []
        used: set[str] = set()
        for c in cands:
            key = repr(c["changes"])
            if key not in used and len(chosen) < 2:
                chosen.append(c)
                used.add(key)
        changes = [ch for c in chosen for ch in c["changes"]]
        trans = tro.boundary_transformation(obs, changes, reason="; ".join(c["why"] for c in chosen),
                                            info={"differences": [c["difference"] for c in chosen], "categories": [c["category"] for c in chosen],
                                                  "reference_d": [c["reference_d"] for c in chosen]},
                                            expected={"identifiability_gain": [c["expected_identifiability"] for c in chosen]})
        before = {r["id"]: r["status"] for r in rows}
        new_rows = tro.assess(ra, rb, trans["observation"], ref)
        after = {r["id"]: r["status"] for r in new_rows}
        newly = [i for i in after if after[i].startswith("identified") and not before[i].startswith("identified")]
        lost = [i for i in after if before[i].startswith("identified") and not after[i].startswith("identified")]
        cost = setup_cost(changes)
        elapsed += cost
        s2 = tro.summarize(new_rows)
        trans["record"]["actual"] = {"newly_identified": newly, "lost": lost, "identified_before": summ["identified"], "identified_after": s2["identified"],
                                     "existing": s2["existing"]}
        log.append({"round": k, "changes": changes, "reason": trans["record"]["reason"], "information_used": trans["record"]["information_used"],
                    "expected": trans["record"]["expected"], "actual": trans["record"]["actual"], "setup_time_s": cost, "elapsed_setup_s": elapsed,
                    "identifiability": s2["identifiability"], "observation": trans["observation"], "rows": new_rows})
        obs, rows = trans["observation"], new_rows
    return log


def exp_AE(which: str, params: dict[str, Any]):
    preset = params.get("preset", "human-like-planar")
    seeds = seeds_for(params, EXPERIMENTS[which]["n_seeds"])
    rounds = int(params.get("rounds", 4))
    if not 1 <= rounds <= 6:
        raise ExperimentError("rounds must be within 1..6")
    ctx = Ctx(2)
    a_cfg = base_config(preset)
    b_cfg = alteration(a_cfg, params.get("alteration", "mixed"))
    ra = yield from ctx.sim(a_cfg, seeds, None, "baseline body")
    rb = yield from ctx.sim(b_cfg, seeds, None, "altered body")
    ref = tro.reference_effects(ra, rb)
    obs1 = observation.validate(observation.config("motion-only"))
    obs2 = observation.validate(observation.config("motion+emg+contact"))
    r1, r2 = tro.assess(ra, rb, obs1, ref), tro.assess(ra, rb, obs2, ref)
    log = _observation_rounds(ra, rb, obs1, ref, rounds, a_cfg)
    final_rows = log[-1]["rows"] if log and "rows" in log[-1] else r1
    final_obs = log[-1]["observation"] if log and "observation" in log[-1] else obs1
    tables = [table("identifiability_by_configuration", "Identifiability of each difference under each observation configuration", STATUS_COLUMNS,
                    status_rows(r1, "motion only") + status_rows(r2, "motion + EMG-like + contact") + status_rows(final_rows, "dynamic (after reconfiguration)"))]
    tables.append(table("summary", "Counts per observation configuration", ["configuration", "existing differences", "identified", "identifiability", "unobserved reasons"],
                        [[lab, s["existing"], s["identified"], s["identifiability"], "; ".join(f"{k}={v}" for k, v in s["counts"].items() if k.startswith("unobserved"))]
                         for lab, s in (("motion only", tro.summarize(r1)), ("motion + EMG-like + contact", tro.summarize(r2)),
                                        ("dynamic (after reconfiguration)", tro.summarize(final_rows)))]))
    tables.append(table("reconfiguration_log", "Automatic observation reconfiguration (reason, information used, expected, actual)",
                        ["round", "changes", "reason", "differences targeted", "expected gain", "newly identified", "lost", "identified before", "identified after", "setup time s"],
                        [[g["round"], str(g.get("changes", "")), g.get("reason", g.get("why", "")), str(g.get("information_used", {}).get("differences", "")),
                          str(g.get("expected", {}).get("identifiability_gain", "")), str(g.get("actual", {}).get("newly_identified", "")), str(g.get("actual", {}).get("lost", "")),
                          g.get("actual", {}).get("identified_before", g.get("identified")), g.get("actual", {}).get("identified_after", g.get("identified")), g.get("setup_time_s")]
                         for g in log]))
    series = {"com_a": decimated_series(ra, "com"), "com_b": decimated_series(rb, "com"), "xref": decimated_series(ra, "xref_true"),
              "trunk_a": decimated_series(ra, "theta", component=2), "trunk_b": decimated_series(rb, "theta", component=2)}
    s1, s2, sf = tro.summarize(r1), tro.summarize(r2), tro.summarize(final_rows)
    negative = []
    for r in r1 + r2 + final_rows:
        pass
    still = [r for r in final_rows if r["reference"]["exists"] and not r["status"].startswith("identified")]
    for r in still:
        negative.append({"statement": f"difference '{r['id']}' exists in the model reference but is not identified by the final observation configuration ({r['status']}{': ' + r['reason'] if r['reason'] else ''})",
                         "evidence": {"reference_d": r["reference"]["d"], "states": r["states"]}})
    for g in log:
        act = g.get("actual")
        if act and act["lost"]:
            negative.append({"statement": f"round {g['round']} lost identification of {act['lost']} while adding others",
                             "evidence": act})
        if act and not act["newly_identified"]:
            negative.append({"statement": f"round {g['round']}: the changes expected to help identified nothing new", "evidence": {"expected": g["expected"], "actual": act}})
    unobs = unobserved_entries(r1, "motion only") + unobserved_entries(r2, "motion + EMG-like + contact") + unobserved_entries(final_rows, "dynamic")
    results = {"tables": tables, "series": series, "summary": {"motion_only": s1, "motion_emg_contact": s2, "dynamic": sf},
               "pair": {"a": a_cfg, "b": b_cfg}, "reconfiguration": [{k: v for k, v in g.items() if k not in ("rows",)} for g in log],
               "final_observation": final_obs, "reference_effects": ref,
               "reading": "The reference column is simulator-internal. A difference is 'identified' only from observation outputs; 'unobserved' names why."}
    rec = records.make_record(which, {**params, "preset": preset, "rounds": rounds}, seeds, a_cfg, [obs1, obs2, final_obs], [{"alteration": params.get("alteration", "mixed")}],
                              results, negative, unobs, {"reentry": []}, a_cfg["task"]["dt"])
    return rec, ra.slow_end


# ------------------------------------------------------------------------------------------------ B: sensorimotor coupling

B_CONDITIONS = [
    ("sensory delay +0.03 s", [("sensory_delay", 0.03)]),
    ("sensory delay +0.06 s", [("sensory_delay", 0.06)]),
    ("visual feedback blocked", [("visual_block", 0.0)]),
    ("visual feedback blocked, reconnected at 3.0 s", [("visual_block", 3.0)]),
    ("neural delay +0.03 s", [("neural_delay", 0.03)]),
    ("contact condition 0.4", [("contact_change", 0.4)]),
    ("posture: initial lean 0.04", [("posture_change", 0.04)]),
    ("resource constraint 0.4", [("resource_constraint", 0.4)]),
    ("second disturbance 50 N", [("perturbation", 50.0)]),
]
B_COUPLING_IV = {"sensory_delay": 0.04, "visual_block": 0.0, "neural_delay": 0.03, "resource_constraint": 0.4, "contact_change": 0.4,
                 "perturbation": 50.0, "posture_change": 0.04}


def exp_B(params: dict[str, Any]):
    preset = params.get("preset", "human-like-planar")
    seeds = seeds_for(params, EXPERIMENTS["B"]["n_seeds"])
    ctx = Ctx(len(B_CONDITIONS) + 1 + len(B_COUPLING_IV) - 6)
    ctx.total = 1 + len(B_CONDITIONS) + len(B_COUPLING_IV)
    base = base_config(preset)
    ctrl = yield from ctx.sim(base, seeds, None, "control")
    runs: dict[str, engine.Run] = {}
    for label, ivs in B_CONDITIONS:
        runs[label] = yield from ctx.sim(config.apply_interventions(base, [{"id": i, "magnitude": m} for i, m in ivs]), seeds, None, label)
    iv_runs: dict[str, engine.Run] = {}
    for iid, mag in B_COUPLING_IV.items():
        iv_runs[iid] = yield from ctx.sim(config.apply_intervention(base, iid, mag), seeds, None, f"coupling: {iid}")
    cm = metrics.summary(ctrl)
    obs = observation.validate(observation.config("motion+emg+contact", kinds=["posture", "emg", "contact", "latency"]))
    rows = []
    negative = []
    keys = (("sway_rms", "trunk sway"), ("peak_dev", "peak deviation after push"), ("recovery_rmst", "recovery time (restricted mean, censored at the window)"),
            ("settle_turn_rmst", "settling after turn (restricted mean, censored at the window)"),
            ("fall", "fall rate"), ("energy_used", "energy used"))
    for label, run in runs.items():
        m = metrics.summary(run)
        for k, nm in keys:
            e = stats.paired_effect(cm[k], m[k])
            rows.append([label, nm, _scalar(e["mean_a"]), _scalar(e["mean_b"]), _scalar(e["d"]), _scalar(e["p"]), e["n"], e["dropped"]])
            if k in ("sway_rms", "peak_dev", "recovery_rmst") and not (np.isfinite(e["p"]) and e["p"] < 0.05 and abs(e["d"]) >= 0.5):
                negative.append({"statement": f"'{label}' did not detectably change {nm} (paired p={_scalar(e['p'])}, d={_scalar(e['d'])})",
                                 "evidence": {"n": e["n"], "dropped": e["dropped"]}})
    oc = observation.observe(ctrl, obs)
    fc = observation.features(ctrl, oc, obs)
    coup = coupling.reconstruct(ctrl, iv_runs)
    for e in coup["edges"]:
        if e["class"] == "correlational-only":
            negative.append({"statement": f"{e['source']} -> {e['target']} is associated (r={e['correlation']:.2f}, lag {e['lag_s']:.2f} s) but the intervention targeting {e['source']} "
                             f"did not change {e['target']} detectably: correlation alone does not support the coupling", "evidence": e})
    tables = [table("condition_effects", "Reference effects of each condition against the matched control (paired by seed)",
                    ["condition", "metric", "control mean", "condition mean", "d (paired)", "p", "pairs used", "pairs dropped (undefined)"], rows),
              table("coupling_edges", "Reconstructed couplings (association, prediction, interventional evidence)",
                    ["source", "target", "correlation", "lag s", "predictive gain", "intervention", "d", "p", "class"],
                    [[e["source"], e["target"], e["correlation"], e["lag_s"], e["predictive_gain"], (e["interventional"] or {}).get("intervention"),
                      (e["interventional"] or {}).get("d"), (e["interventional"] or {}).get("p"), e["class"]] for e in coup["edges"]]),
              table("line_effects", "Operation lines most changed by each intervention (paired effect on command magnitude)",
                    ["intervention", "line", "d", "p", "ignitions/s control", "ignitions/s intervention"],
                    [[iid, le["line"], le["d"], le["p"], le["ignitions_per_s"][0], le["ignitions_per_s"][1]] for iid, ef in coup["effects"].items() for le in ef["lines"][:4]]),
              table("transitions", "Body-state transition frequencies: change under each intervention (intervention minus control, normalised)",
                    ["intervention", *[f"{a}->{b}" for a in coupling.STATES for b in coupling.STATES if a != b]],
                    [[iid, *[ef["transition_change"][i][j] for i in range(5) for j in range(5) if i != j]] for iid, ef in coup["effects"].items()])]
    series = {"control_com": decimated_series(ctrl, "com"), "xref": decimated_series(ctrl, "xref_true")}
    for label in ("sensory delay +0.06 s", "visual feedback blocked", "visual feedback blocked, reconnected at 3.0 s", "neural delay +0.03 s"):
        series[label] = decimated_series(runs[label], "com")
    results = {"tables": tables, "series": series, "coupling": {"nodes": coup["nodes"], "edges": coup["edges"], "classes": coup["classes"], "states": coup["states"],
                                                                "effects": {k: {kk: vv for kk, vv in v.items() if kk in ("lines", "outcome", "association_with_outcome", "note")} for k, v in coup["effects"].items()}},
               "observed_latency_estimate": {k: _scalar(float(np.nanmean(v))) if np.isfinite(v).any() else None for k, v in fc.items() if k.endswith("onset_push") or k == "corr_latency_est"},
               "reading": "Edges are classified by intervention, not by correlation: 'interventionally-supported' needs an intervention on the source to change the target."}
    rec = records.make_record("B", {**params, "preset": preset}, seeds, base, [obs], [{"id": i, "magnitude": m} for i, m in B_COUPLING_IV.items()], results, negative, [], {"reentry": []}, base["task"]["dt"])
    return rec, ctrl.slow_end


# ------------------------------------------------------------------------------------------------ C: fragility transfer

C_COMBOS = [("axis-maintenance", "anti-collapse-posture"), ("lower-abdominal-continuity", "tensegrity"), ("narrow-step-balance", "breathing-synchronization")]


def _label_effect(e: dict[str, Any]) -> str:
    if not (np.isfinite(e["p"]) and np.isfinite(e["d"])):
        return "undefined"
    if e["p"] < 0.05 and abs(e["d"]) >= 0.5:
        return "improved" if e["d"] < 0 else "worsened"
    return "no detectable effect"


def exp_C(params: dict[str, Any]):
    preset = params.get("preset", "human-like-planar")
    seeds = seeds_for(params, EXPERIMENTS["C"]["n_seeds"])
    ids = list(params.get("principles") or [p["id"] for p in xeno14.PRINCIPLES])
    for i in ids:
        if i not in xeno14.BY_ID:
            raise ExperimentError(f"unknown principle {i!r}")
    combos = [c for c in C_COMBOS if c[0] in ids or c[1] in ids] if params.get("combos", True) else []
    ctx = Ctx(1 + len(ids) + len(combos))
    base = base_config(preset)
    ctrl = yield from ctx.sim(base, seeds, None, "matched control")
    cm = metrics.organization(ctrl)
    runs: dict[str, engine.Run] = {}
    for pid in ids:
        runs[pid] = yield from ctx.sim(xeno14.apply(base, [pid]), seeds, None, f"Xeno-14: {pid}")
    combo_runs: dict[str, engine.Run] = {}
    for a, b in combos:
        combo_runs[f"{a} + {b}"] = yield from ctx.sim(xeno14.apply(base, [a, b]), seeds, None, f"pair: {a} + {b}")
    orgs = list(metrics.ORGANIZATION)
    matrix: dict[str, dict[str, Any]] = {}
    rows = []
    for pid, run in runs.items():
        om = metrics.organization(run)
        matrix[pid] = {}
        for o in orgs:
            e = stats.paired_effect(cm[o], om[o])
            lab = _label_effect(e)
            matrix[pid][o] = {"d": _scalar(e["d"]), "p": _scalar(e["p"]), "label": lab, "mean_control": _scalar(e["mean_a"]), "mean": _scalar(e["mean_b"]), "n": e["n"]}
            rows.append([pid, o, matrix[pid][o]["mean_control"], matrix[pid][o]["mean"], matrix[pid][o]["d"], matrix[pid][o]["p"], lab, "yes" if o in xeno14.BY_ID[pid]["acts_on"] else "no"])
    transfers, negative = [], []
    for pid in ids:
        imp = [o for o in orgs if matrix[pid][o]["label"] == "improved"]
        wor = [o for o in orgs if matrix[pid][o]["label"] == "worsened"]
        touched = xeno14.BY_ID[pid]["acts_on"]
        if imp and wor:
            transfers.append({"principle": pid, "improved": imp, "worsened": wor})
        if not imp and not wor:
            negative.append({"statement": f"{pid}: no detectable effect on any organization (paired, {len(seeds)} seeds)", "evidence": {o: matrix[pid][o]["d"] for o in orgs}})
        if [o for o in touched if matrix[pid][o]["label"] == "worsened"]:
            negative.append({"statement": f"{pid}: worsened an organization its own definition touches: {[o for o in touched if matrix[pid][o]['label'] == 'worsened']}",
                             "evidence": {o: matrix[pid][o] for o in touched}})
        if not [o for o in touched if matrix[pid][o]["label"] == "improved"] and (imp or wor):
            negative.append({"statement": f"{pid}: improved none of the organizations its definition touches ({touched}); changes occurred elsewhere: improved {imp}, worsened {wor}",
                             "evidence": {}})
    combo_rows = []
    for name, run in combo_runs.items():
        a, b = name.split(" + ")
        om = metrics.organization(run)
        conf = float(np.nanmean(tro._conflicts(run)))
        for o in orgs:
            e = stats.paired_effect(cm[o], om[o])
            da, db = matrix[a][o]["d"], matrix[b][o]["d"]
            combo_rows.append([name, o, _scalar(e["d"]), _label_effect(e), da, db, None if None in (e["d"], da, db) or not np.isfinite(e["d"]) else float(e["d"] - (da + db)), conf])
    mcm = metrics.summary(ctrl)
    tables = [table("transfer_matrix", "Paired effect of each Xeno-14 condition on each organization (all 'lower is better': negative d = improvement)",
                    ["principle", "organization", "control mean", "condition mean", "d (paired)", "p", "label", "touched by the definition"], rows),
              table("fragility_transfers", "Conditions that improved one organization and worsened another", ["principle", "improved", "worsened"],
                    [[t["principle"], ", ".join(t["improved"]), ", ".join(t["worsened"])] for t in transfers]),
              table("pairs", "Pairs of conditions active together: effect, the two single effects, interaction (pair minus sum of singles), line conflicts per second",
                    ["pair", "organization", "d pair", "label", "d first", "d second", "interaction", "conflict steps per s"], combo_rows)]
    series = {"control_com": decimated_series(ctrl, "com"), "xref": decimated_series(ctrl, "xref_true")}
    for pid in ids[:6]:
        series[pid] = decimated_series(runs[pid], "com")
    results = {"tables": tables, "series": series, "matrix": matrix, "organizations": {k: v[1] for k, v in metrics.ORGANIZATION.items()}, "transfers": transfers,
               "principles": {p["id"]: {k: p[k] for k in ("alias", "definition", "operationalization", "ignition", "acts_on")} for p in xeno14.PRINCIPLES if p["id"] in ids},
               "control_summary": {k: _scalar(float(np.nanmean(v))) if np.isfinite(v).any() else None for k, v in metrics.numeric_only(mcm).items()},
               "reading": f"Principles are experimental conditions (planar translations of {xeno14.SOURCE}); no sign of effect was assumed. Positive, negative and null results are all listed."}
    rec = records.make_record("C", {**params, "preset": preset, "principles": ids}, seeds, base, [], [{"xeno14": [i]} for i in ids], results, negative, [], {"reentry": []}, base["task"]["dt"])
    return rec, ctrl.slow_end


# ------------------------------------------------------------------------------------------------ D: operational velocity

def exp_D(params: dict[str, Any]):
    preset = params.get("preset", "human-like-planar")
    seeds = seeds_for(params, EXPERIMENTS["D"]["n_seeds"])
    trials = int(params.get("trials", 5))
    ctx = Ctx(5 + trials)
    base = base_config(preset)
    r0 = yield from ctx.sim(base, seeds, None, "baseline")
    p0 = velocity.profile(r0)
    c_neural = config.apply_intervention(base, "neural_delay", 0.03)
    c_stop = copy.deepcopy(base)
    for ln in c_stop["lines"]:
        if ln["id"] == "sens.cue":
            ln["enabled"] = False
    c_unreach = config.validate({**copy.deepcopy(base), "task": {**base["task"], "x_target": 0.15}})
    c_push = config.apply_intervention(base, "perturbation", 240.0)
    runs = {}
    for label, cfg in (("neural delay +0.03 s", c_neural), ("cue-perception line stopped", c_stop), ("target beyond the base of support (15 cm)", c_unreach),
                       ("very strong push (240 N, extra)", c_push)):
        runs[label] = yield from ctx.sim(cfg, seeds, None, label)
    # adaptation: repeated pushes with the slow state carried from trial to trial
    peaks = []
    slow = None
    short = config.build(preset, {"task": {"horizon": 4.0, "t_cue": 3.5, "t_turn": 3.8, "ramp_s": 0.1},
                                  "environment": {"pushes": [{"t": 1.0, "dur": 0.12, "force": 45.0, "link": 2, "point_frac": 0.8}]}})
    for k in range(trials):
        rt = yield from ctx.sim(short, seeds, slow, f"adaptation trial {k + 1}")
        peaks.append(metrics.summary(rt)["peak_dev"])
        slow = rt.slow_end
    adapt = velocity.adaptation_speed(np.array(peaks))
    p0["adaptation"] = {"values": adapt, "defined": float(np.isfinite(adapt).mean()), "reasons": [("" if np.isfinite(v) else "needs 3 valid trials") for v in adapt]}
    obs_full = observation.validate(observation.config("full"))
    obs_lost = observation.validate(observation.config("motion-only"))
    est = observed_measures(r0, obs_full)
    est_lost = observed_measures(r0, obs_lost)
    status_rows_ = {}
    tables_rows = []
    negative = []
    for label, run in runs.items():
        pc = velocity.profile(run)
        pc["adaptation"] = {"values": np.full(len(seeds), np.nan), "defined": 0.0, "reasons": [""] * len(seeds)}
        st = velocity.compare_status(p0, pc, observed=set(est))
        status_rows_[label] = st
        for r in st:
            if r["id"] in ("adaptation", "reconfiguration"):
                continue
            tables_rows.append([label, r["id"], r["label"], r["baseline_defined"], r["condition_defined"], r["status"], r.get("reason") or "", (r.get("effect") or {}).get("d")])
            if r["status"] == "lapsed":
                negative.append({"statement": f"{r['label']} lapsed under '{label}': {r.get('reason')}", "evidence": r.get("reason_counts", {})})
    for mid in est_lost_ids(est, est_lost):
        negative.append({"statement": f"the quantity '{mid}' exists in the reference but the motion-only observation configuration cannot estimate it (observation-lost)", "evidence": {}})
    base_rows = []
    for m in velocity.MEASURES:
        v = p0[m["id"]]["values"]
        ok = np.isfinite(v)
        mean = float(np.mean(v[ok])) if ok.any() else None
        sd = float(np.std(v[ok], ddof=1)) if ok.sum() > 1 else None
        o = est.get(m["id"])
        base_rows.append([m["id"], m["label"], m["unit"], m["definition"], p0[m["id"]]["defined"], mean, sd, None if o is None else _scalar(float(np.nanmean(o))), "yes" if m["id"] in est else "no"])
    tables = [table("baseline_measures", "The ten velocity measures in the baseline (reference), and the estimate an observation configuration can make",
                    ["measure", "label", "unit", "definition", "fraction of seeds defined", "reference mean", "reference sd", "estimated from observations (full set)", "estimable"], base_rows),
              table("status_by_condition", "Established / varied / lapsed per measure and condition", ["condition", "measure", "label", "baseline defined", "condition defined", "status", "reason", "paired d"], tables_rows),
              table("adaptation_trials", "Peak COM deviation after the push in repeated trials (retained state carried over), mean over seeds",
                    ["trial", "mean peak deviation (m)"], [[i + 1, float(np.nanmean(p))] for i, p in enumerate(peaks)])]
    series = {"baseline_com": decimated_series(r0, "com"), "xref": decimated_series(r0, "xref_true")}
    for label, run in runs.items():
        series[label] = decimated_series(run, "com")
    results = {"tables": tables, "series": series, "measures": {m["id"]: {**m, "values_mean": base_rows[i][5], "defined": base_rows[i][4]} for i, m in enumerate(velocity.MEASURES)},
               "status": {k: [{kk: vv for kk, vv in r.items() if kk != "effect"} for r in v] for k, v in status_rows_.items()},
               "estimable": sorted(est), "estimable_motion_only": sorted(est_lost),
               "reading": "'lapsed' is split into line-stopped, observation-lost and description-inapplicable; they are different findings."}
    rec = records.make_record("D", {**params, "preset": preset, "trials": trials}, seeds, base, [obs_full, obs_lost], [{"condition": k} for k in runs], results, negative, [], {"reentry": []}, base["task"]["dt"])
    return rec, r0.slow_end


def est_lost_ids(full: dict[str, np.ndarray], lost: dict[str, np.ndarray]) -> list[str]:
    return sorted(set(full) - set(lost))


def observed_measures(run: engine.Run, obs: dict[str, Any]) -> dict[str, np.ndarray]:
    """The velocity measures an observation configuration can estimate, from its own features only."""
    o = observation.observe(run, obs)
    f = observation.features(run, o, obs)
    out: dict[str, np.ndarray] = {}
    if "neural_onset_cue" in f:
        out["neural_response"] = f["neural_onset_cue"]
    if "emg_onset_cue" in f:
        out["muscle_onset"] = f["emg_onset_cue"]
    for key in ("emg_onset_push", "cop_onset_push", "imu_onset_push", "com_onset_push"):
        if key in f:
            out["correction"] = f[key]
            break
    if "turn_error_obs" in f:
        out["settling"] = f["turn_error_obs"]
    return out


# ------------------------------------------------------------------------------------------------ F: human-machine

def exp_F(params: dict[str, Any]):
    seeds = seeds_for(params, EXPERIMENTS["F"]["n_seeds"])
    t_goal, t_rec = float(params.get("t_goal", 1.6)), float(params.get("t_recover", 1.5))
    forces = [20.0, 40.0, 60.0, 80.0, 100.0, 130.0, 160.0]
    ctx = Ctx(2 * (1 + len(forces) // 2 + 1))
    presets = ["human-like-planar", "machine-like-planar"]
    summary, rows, negative, series = {}, [], [], {}
    curves: dict[str, list[float]] = {}
    crit: dict[str, float] = {}
    shifts: dict[str, float] = {}
    for preset in presets:
        base = base_config(preset)
        r = yield from ctx.sim(base, seeds, None, f"{preset}: criterion trial")
        m = metrics.summary(r)
        prof = velocity.profile(r)
        dt = r.dt
        i_cue = metrics.idx(base["task"]["t_cue"], dt)
        near = (np.abs(r["com"] - base["task"]["x_target"]) < 2 * metrics.band(base)) & r["alive"]
        near[:, :i_cue] = False
        first = np.where(near.any(axis=1), near.argmax(axis=1), -1)
        t_goal_s = np.where(first >= 0, (first - i_cue) * dt, np.nan)
        success = (t_goal_s <= t_goal) & np.isfinite(t_goal_s) & ~r.fell & (m["recovery"] <= t_rec)
        # corrections: sign changes of the ankle torque derivative above a small threshold after the push
        ank = r["tau"][:, :, 0]
        i_push = metrics.idx(base["environment"]["pushes"][0]["t"], dt)
        d = np.diff(ank[:, i_push: i_push + metrics.idx(1.5, dt)], axis=1)
        corr = ((np.diff(np.sign(np.where(np.abs(d) > 0.5, d, 0)), axis=1) != 0) & (np.sign(d[:, 1:]) != 0)).sum(axis=1)
        summary[preset] = {"criterion_met": float(success.mean()), "time_to_goal": t_goal_s, "energy": m["energy_used"], "peak_dev": m["peak_dev"],
                           "recovery": m["recovery"], "recovery_rmst": m["recovery_rmst"], "recovered": np.isfinite(m["recovery"]).astype(float),
                           "corrections": corr, "falls": float(r.fell.mean())}
        series[preset] = decimated_series(r, "com")
        # reachability: recovery probability against push force, and the strongest push recovered (50 %)
        probs = []
        for f in forces:
            cfg_f = base_config(preset, extra={"environment": {"pushes": [{"t": 3.2, "dur": 0.12, "force": f, "link": 2, "point_frac": 0.8}]}, "task": {"horizon": 5.5}})
            rf = yield from ctx.sim(cfg_f, seeds, None, f"{preset}: push {f:.0f} N")
            mf = metrics.summary(rf)
            probs.append(float(((~rf.fell) & ~rf.diverged & np.isfinite(mf["recovery"])).mean()))   # recovered inside the 2 s window
        curves[preset] = probs
        above = [f for f, p in zip(forces, probs, strict=True) if p >= 0.5]
        crit[preset] = max(above) if above else 0.0
        shifts[preset] = float(prof["consequence"]["defined"])
    for preset in presets:
        s = summary[preset]
        for k, lab in (("time_to_goal", "time to goal (s)"), ("energy", "resource used (energy units)"), ("peak_dev", "peak deviation after push (m)"),
                       ("recovery", "recovery time (s), recovered seeds only"), ("recovered", "fraction recovered inside the window"),
                       ("corrections", "corrective reversals after the push")):
            v = s[k]
            ok = np.isfinite(v)
            rows.append([preset, lab, float(np.mean(v[ok])) if ok.any() else None, float(np.std(v[ok], ddof=1)) if ok.sum() > 1 else None, int(ok.sum())])
        rows.append([preset, "criterion met (fraction of seeds)", s["criterion_met"], None, len(seeds)])
        rows.append([preset, "strongest push recovered (N, 50 % of seeds)", crit[preset], None, len(seeds)])
    cmp_rows = []
    for k, lab in (("time_to_goal", "time to goal"), ("energy", "resource used"), ("peak_dev", "peak deviation"), ("recovery_rmst", "recovery time (restricted mean)"), ("recovered", "fraction recovered"), ("corrections", "corrections")):
        e = stats.paired_effect(summary[presets[0]][k], summary[presets[1]][k])
        cmp_rows.append([lab, _scalar(e["mean_a"]), _scalar(e["mean_b"]), _scalar(e["d"]), _scalar(e["p"]), e["n"]])
        if not (np.isfinite(e["p"]) and e["p"] < 0.05 and abs(e["d"]) >= 0.5):
            negative.append({"statement": f"no detectable difference between the bodies in {lab} (paired by seed, p={_scalar(e['p'])})", "evidence": {"n": e["n"]}})
    tables = [table("per_body", "Per body: the stated consequence, speed, resources, correction", ["body", "measure", "mean", "sd", "n"], rows),
              table("comparison", "Human-like (first) vs machine-like (second), paired by seed (common random numbers)", ["measure", "human-like mean", "machine-like mean", "d (paired)", "p", "n"], cmp_rows),
              table("reachability", "Fraction of seeds that stay up and recover after a push of the given force", ["push (N)", *presets], [[f, curves[presets[0]][i], curves[presets[1]][i]] for i, f in enumerate(forces)])]
    results = {"tables": tables, "series": series, "curves": {"forces": forces, **curves}, "critical_push": crit,
               "criterion": {"target_shift_m": base_config(presets[0])["task"]["x_target"], "within_s": t_goal, "then_recover_from_push_within_s": t_rec},
               "reading": "One consequence is stated for both bodies. The two presets are nominal and not matched in mass, height or actuation; the comparison is of these two specified models, not of people and machines."}
    rec = records.make_record("F", {**params, "t_goal": t_goal, "t_recover": t_rec}, seeds, base_config(presets[0]), [], [{"body": p} for p in presets], results, negative, [], {"reentry": []}, 0.01)
    return rec, {}


# ------------------------------------------------------------------------------------------------ dispatch

def run(exp_id: str, params: dict[str, Any] | None = None):
    """Generator: yields progress dicts, returns (record, slow_state). Raises ExperimentError / config errors for bad input."""
    params = dict(params or {})
    if exp_id not in EXPERIMENTS:
        raise ExperimentError(f"unknown experiment {exp_id!r}; known: {sorted(EXPERIMENTS)}")
    if exp_id in ("A", "E"):
        return exp_AE(exp_id, params)
    return {"B": exp_B, "C": exp_C, "D": exp_D, "F": exp_F}[exp_id](params)


def run_to_end(exp_id: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    gen = run(exp_id, params)
    while True:
        try:
            next(gen)
        except StopIteration as stop:
            return stop.value


MODEL = MODEL_VERSION
