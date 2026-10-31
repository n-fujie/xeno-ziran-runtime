"""A research session bundle: the coherent SYNTHETIC example that Views A-H draw from. Everything in it is generated (functional-test data); nothing was measured and no real-world experiment was done.

All views read the same records (by id), the same time base (device time in seconds), and the same body configuration versions; the bundle is built by calling the layers of this package, not by typing results.
"""

from __future__ import annotations

import copy
import math

from . import body as B
from . import causal as CA
from . import evidence as EV
from . import export as EX
from . import observation as OB
from . import protocol as PR
from . import reconstruction as RC
from . import revision as RV
from . import status as ST
from . import synthetic as SY
from .mapping import coverage
from .provenance import Kind, Ledger, Provenance, seal
from .timebase import Interpolation

AT = "2026-01-01T00:00:00.000000Z"
CREATOR = {"name": "teoo.session/1", "role": "generator"}
SOURCE = {"kind": "generator", "description": "TEOO synthetic session generator (functional-test data, not a body model)", "declared_by": "teoo.session"}


def _spec_list() -> list[dict]:
    return [OB.target_spec("tgt.knee_l", "angle", scale=2.0, phenomenon_period_s=2.0, amplitude=30.0, opacity=0.1), OB.target_spec("tgt.hip_l", "angle", scale=2.0, phenomenon_period_s=2.0, amplitude=20.0, opacity=0.1),
            OB.target_spec("tgt.elbow_r", "angle", scale=2.0, phenomenon_period_s=2.0, amplitude=25.0, opacity=0.8), OB.target_spec("tgt.ankle_l", "angle", scale=2.0, phenomenon_period_s=0.2, amplitude=10.0, opacity=0.1),
            OB.target_spec("tgt.head", "temp", scale=2.0, phenomenon_period_s=600.0, amplitude=0.05, opacity=0.0), OB.target_spec("tgt.trunk", "hr", scale=2.0, phenomenon_period_s=20.0, amplitude=3.0, opacity=0.0),
            OB.target_spec("tgt.thigh_l", "emg", scale=1.0, phenomenon_period_s=0.01, amplitude=0.5, opacity=0.1)]


def _observation_history() -> tuple[list[dict], list[dict], list[dict]]:
    sensors = [OB.sensor("imu1", ["angle"], resolution=1.0, sampling_period_s=0.02, window_s=20, detection_limit=0.1, penetration=0.3, reach=["tgt.knee_l", "tgt.hip_l", "tgt.elbow_r"]),
               OB.sensor("imu_slow", ["angle"], resolution=1.0, sampling_period_s=1.0, window_s=20, detection_limit=0.1, penetration=0.3, reach=["tgt.ankle_l"]),
               OB.sensor("thermo", ["temp"], resolution=0.5, sampling_period_s=1.0, window_s=600, detection_limit=0.1, penetration=0.3, reach=["tgt.head"]),
               OB.sensor("pulse", ["hr"], resolution=1.0, sampling_period_s=1.0, window_s=20, detection_limit=0.5, penetration=0.3, reach=["tgt.trunk"])]
    h = [OB.new_configuration(sensors, resources={"energy_budget": None}, variables=["joint.angle.knee_l", "joint.angle.hip_l", "hr.beat", "temp.skin.forehead"], at=0.0, body_version=1, label="initial")]
    specs = _spec_list()
    log: list[dict] = []
    h, _ = RV.revise(h, specs, "sensor_change", {"op": "add", "sensor": OB.sensor("emg1", ["emg"], resolution=0.5, sampling_period_s=0.001, window_s=20, detection_limit=0.01, penetration=0.3, reach=["tgt.thigh_l"])},
                     reason="add a surface EMG to observe the left thigh", at=6.0, log=log)
    h, _ = RV.revise(h, specs, "time_window_change", {"sensor": "imu_slow", "sampling_period_s": 0.05}, reason="sample the ankle faster than its movement", at=10.0, log=log)
    h, _ = RV.revise(h, specs, "boundary_change", {"sensor": "imu1", "reach": ["tgt.knee_l", "tgt.hip_l", "tgt.elbow_r"], "penetration": 0.9}, reason="a sensor that sees through the garment covering the right elbow", at=14.0, log=log)
    _, _ = RV.revise(h, specs, "coupling_change", {"key": "thermo:tgt.head", "coupling": {"gain": 3.0}}, reason="proposal: raise the coupling of the thermometer to the forehead", at=16.0, status="proposed", log=log, initiated_by="researcher")
    return h, specs, log


def _series(seed: int, n: int, hz: float, amp: float, mean: float, noise: float, phase: float = 0.0) -> tuple[list[float], list[float]]:
    import random
    r = random.Random(seed)
    t = [round(i / hz, 6) for i in range(n)]
    return t, [round(mean + amp * math.sin(2 * math.pi * 0.5 * x + phase) + r.gauss(0, noise), 3) for x in t]


def _obs_record(variable: str, target: str, unit: str, t: list[float], v: list[float], seed: int, label: str, body_version: int) -> dict:
    ch = {"variable": variable, "target": target, "unit": unit, "times": t, "samples": [ST.sample(x, ST.ObsStatus.MEASURED_VALID) for x in v], "counts": {"MEASURED_VALID": len(v)}}
    return seal({"body": {"id": "body.human-simplified-skeleton", "version": body_version}, "banner": SY.BANNER, "label": label, "time": {"device_clock": "synthetic-clock", "unit": "s", "sync": None}, "channels": [ch]},
                provenance=Provenance.SYNTHETIC, kind=Kind.OBSERVATION, creator=CREATOR, source=SOURCE, created_at=AT)


def build_session(seed: int = 7) -> dict:
    demo = SY.make_demo(seed)
    rec = demo["records"][0]
    body1 = demo["body"]
    knee = next(c for c in rec["payload"]["channels"] if c["variable"] == "joint.angle.knee_l")
    # --- reconstruction: the dropout of the knee channel filled by linear interpolation, with an assumed growing uncertainty
    t, s = knee["times"], knee["samples"]
    gap = [i for i, x in enumerate(s) if x["status"] != "MEASURED_VALID"]
    a, b = gap[0] - 1, gap[-1] + 1
    vals = [x["value"] for x in s]
    est_v, est_sd = [], []
    for i in range(len(s)):
        if i in gap:
            f = (i - a) / (b - a)
            est_v.append(round(vals[a] + f * (vals[b] - vals[a]), 3))
            est_sd.append(round(0.5 + 8.0 * math.sin(math.pi * f), 3))
        else:
            est_v.append(vals[i])
            est_sd.append(0.4)
    est = RC.make_reconstruction([rec], method="linear interpolation across the dropout (assumed random-walk uncertainty)", creator=CREATOR, reconstruction_time_s=(t[a] + t[b]) / 2, time_uncertainty_s=None, synchronised_inputs=False,
                                 value={"variable": "joint.angle.knee_l", "times": t, "values": est_v, "sd": est_sd, "gap_s": [t[gap[0]], t[gap[-1]]]}, uncertainty={"sd": "assumed; grows to 8.5 deg at the middle of the gap"},
                                 assumptions=["the joint moves smoothly across the dropout", "no event occurred inside it"], interpolation=[Interpolation("linear", t[a], t[b], tuple(gap), "the 40 missing samples are replaced by a straight line")],
                                 kind=Kind.RECONSTRUCTION, created_at=AT)
    lost = {"interval_s": [t[gap[0]], t[gap[-1]]], "n_samples": len(gap), "statement": "what the joint did inside the dropout is not known; the line is an assumption, not an observation (a movement shorter than the gap may have happened)"}
    # --- intervention: a brace is added at the left knee (the body changes: version 1 -> 2); the observation configuration is the same
    brace = B.add_component(body1, B.component("brace_knee_l", "tool", "knee brace", concept_only=True), at=AT)
    brace = B.connect(brace, B.relation("brace_mount", "brace_knee_l", "shank_l", "mount", directed=True), at=AT)
    bv_after = brace.current["version"]  # adding the component and connecting it are two versions of the body: the intervention's "after" is the last
    t10, v_pre = _series(seed + 1, 500, 50.0, 35.0, 30.0, 0.4)
    t10b, v_post = _series(seed + 2, 500, 50.0, 28.0, 26.0, 0.4)
    pre = _obs_record("joint.angle.knee_l", "tgt.knee_l", "deg", t10, v_pre, seed + 1, "before the brace", 1)
    post = _obs_record("joint.angle.knee_l", "tgt.knee_l", "deg", t10b, v_post, seed + 2, "after the brace", bv_after)
    iv = CA.intervention_record(description="a brace is fitted at the left knee", kind_of_action="fit-brace", target="knee_l", applied_at_s=10.0, assignment="researcher-chosen", body_version_before=1, body_version_after=bv_after,
                                config_version_before=1, config_version_after=1, provenance=Provenance.SYNTHETIC, creator=CREATOR, source=SOURCE, created_at=AT)
    diff = CA.compare_pre_post(pre, post, "joint.angle.knee_l", iv)
    ident = CA.identify({"assignment": "researcher-chosen", "protocol_analysis_class": "exploratory (not declared in this version)", "confounders_unaddressed": ["practice effect between the two windows"], "n": 2})
    model = CA.StructuralModel({"brace": {"parents": {}, "intercept": 0.0, "noise_sd": 0.0}, "amplitude": {"parents": {"brace": -7.0}, "intercept": 35.0, "noise_sd": 0.5}},
                               assumptions=["amplitude depends on the brace only through the stated coefficient", "no other cause of the change between the two windows", "linear and additive"],
                               identification=["the brace assignment is independent of the noise (not true here: the researcher chose it)"], scope="this synthetic example only; no real body")
    cf = CA.counterfactual_record(model, {"brace": 1.0, "amplitude": 28.0}, {"brace": 0.0}, parents=[post], creator=CREATOR, created_at=AT)
    # --- protocol and a replayable synthetic experiment
    proto = PR.new_protocol(experiment_id="exp-demo-brace", hypotheses=[{"id": "H1", "statement": "the knee-angle amplitude differs between the no-brace and the brace condition (synthetic generator)"}], targets=["joint.angle.knee_l"],
                            instrument_conditions={"observation_config_version": 1, "sensor": "imu1"}, control_condition="no-brace", conditions=["no-brace", "brace"], seeds=[1, 2, 3, 4, 5], trials_per_condition=8,
                            stopping_rule={"type": "fixed-n", "n_per_condition_per_seed": 8}, outcomes={"primary": ["amplitude"], "secondary": []},
                            analyses=[{"id": "AN1", "hypothesis": "H1", "outcome": "amplitude", "method": "randomization-test", "confirmatory": True, "compare": "brace", "n_perm": 2000, "seed": 0}], multiplicity="none-declared-single-test",
                            failure_conditions=["fewer than two valid trials in a condition", "the generator's output digest differs on reproduction"], reproduction={"generator": "synthetic-two-condition/1", "steps": ["PR.run_protocol(protocol, params)", "PR.reproduce(protocol, run, params)"]})
    reg = PR.ProtocolRegistry()
    reg.register(proto)
    reg.freeze("exp-demo-brace", 1, 100.0)
    reg.note_first_data("exp-demo-brace", 1, 200.0)
    params = {"baseline": 30.0, "shifts": {"brace": -4.0}, "noise": 2.5, "drift": 0.0}
    run = PR.run_protocol(proto, params=params, created_at=AT)
    rep = PR.reproduce(proto, run, params=params)
    classes = {aid: reg.analysis_class("exp-demo-brace", 1, aid) for aid in run["results"]}
    amended = reg.amend("exp-demo-brace", 1, {"trials_per_condition": 10}, "more trials per condition (a changed condition is a new version)")
    # --- observation configuration history and the relation field
    hist, specs, log = _observation_history()
    times = [float(x) for x in range(0, 21)]
    states = OB.replay(hist, specs, times)
    field = OB.relation_field("estimate the left-knee movement during a brace trial", [
        {"id": "joint-angle", "dimension": "spatial", "observed": True, "accessible": True, "judgment_changing": True, "note": "observed by imu1"},
        {"id": "ambient-temperature", "dimension": "material", "observed": False, "accessible": True, "judgment_changing": None, "note": "no sensor; could change muscle behaviour (unknown)"},
        {"id": "instruction-presence", "dimension": "infrastructural", "observed": False, "accessible": True, "judgment_changing": True, "note": "who was instructed what is not recorded"},
        {"id": "sleep-history", "dimension": "temporal", "observed": False, "accessible": False, "judgment_changing": None, "note": "not obtainable for this session"},
        {"id": "sensor-wear", "dimension": "hierarchical", "observed": True, "accessible": True, "judgment_changing": False, "note": "sensor health recorded"}])
    records = [rec, est, pre, post, iv, cf]
    ledger = Ledger()
    for r in records:
        ledger.append(r)
    ids = {r["record_id"]: {"provenance": r["provenance"], "kind": r["kind"], "label": EV.classify(r)["label"]} for r in records}
    return {"banner": SY.BANNER, "synthetic": True, "seed": seed, "time_base": "device time, seconds (unsynchronised: no reference clock is declared)", "records": records, "record_index": ids,
            "evidence": [EV.classify(r) for r in records], "bodies": {"1": body1.to_dict(), str(bv_after): brace.to_dict()}, "body_versions": {"before": 1, "after": bv_after}, "coverage": coverage(body1, [rec]),
            "observation": {"history": hist, "specs": specs, "revisions": log, "times": times, "states": states, "replay_check": RV.replay_revisions(hist, log, specs)},
            "reconstruction": {"record_id": est["record_id"], "input_record_id": rec["record_id"], "lost": lost, "variable": "joint.angle.knee_l"},
            "intervention": {"record_id": iv["record_id"], "pre": pre["record_id"], "post": post["record_id"], "counterfactual": cf["record_id"], "observed_difference": diff, "identification": ident,
                             "model": {"assumptions": model.assumptions, "identification": model.identification, "scope": model.scope}},
            "protocol": {"protocol": proto, "amended": {"version": amended["version"], "parent_version": amended["parent_version"], "change_reason": amended["change_reason"]}, "run": {k: v for k, v in run.items() if k != "trials"},
                         "n_trials": run["n_trials"], "trials_head": run["trials"][:10], "analysis_classes": classes, "reproduction": rep, "registry_ok": not reg.verify(), "params": params},
            "relation_field": field, "ledger": {"entries": len(ledger.entries), "issues": [i.to_dict() for i in ledger.verify()]}, "export_note": "figures are rendered by POST /api/teoo/figure with the evidence band and watermarks built in"}


def figure_for(session: dict, kind: str, generated_at: str = AT) -> dict:
    """One of the session's figures, rendered with its metadata (used by the export endpoint and by the tests)."""
    recs = {r["record_id"]: r for r in session["records"]}
    rec = session["records"][0]
    body = session["bodies"]["1"]
    if kind == "timeseries":
        ch = next(c for c in rec["payload"]["channels"] if c["variable"] == "joint.angle.knee_l")
        est = recs[session["reconstruction"]["record_id"]]
        v = est["payload"]["reconstruction"]["value"]
        return EX.build_figure("timeseries", "Left knee angle: observed samples, the dropout, and a reconstruction (SYNTHETIC input)", {"channel": ch, "label": "left knee angle", "estimate": {"times": v["times"], "values": v["values"], "sd": v["sd"]}},
                               [rec, est], body=body, generated_at=generated_at, units={"deg": "degrees", "s": "seconds, device time"})
    if kind == "body":
        return EX.build_figure("body", "Body observation: which parts have records (conceptual drawing)", {"body": body, "by_ref": session["coverage"]["by_ref"]}, [rec], body=body, generated_at=generated_at)
    if kind == "limits":
        st = session["observation"]["states"][int(len(session["observation"]["states"]) // 2)]
        return EX.build_figure("limits", "Observation limits at one time (declared targets only)", st, [rec], body=body, observation=st, generated_at=generated_at)
    if kind == "evidence":
        run = session["protocol"]["run"]
        data = {**run, "classes": session["protocol"]["analysis_classes"]}
        return EX.build_figure("evidence", "Experimental evidence: a pre-registered synthetic experiment", data, [rec], body=body, protocol=session["protocol"]["protocol"], generated_at=generated_at)
    raise KeyError(kind)


__all__ = ["build_session", "figure_for", "copy"]
