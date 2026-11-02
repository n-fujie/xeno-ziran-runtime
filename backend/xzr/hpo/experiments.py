"""HPO-001 / HPO-002 / HPO-003: protocols, paired seed jobs and analysis.

The protocol (conditions, seeds, metrics, success and stopping conditions) is fixed in docs/HPO_PROTOCOL.md before the
confirmatory runs; its SHA-256 is pinned here (``PROTOCOL_SHA256``) and the confirmatory runners refuse to run if the
file differs. Development (calibration of thresholds, debugging) used only the development seeds listed in the
protocol, which are disjoint from every confirmatory and held-out seed range below.

Every run of one seed shares: the initial world (generator seed), the warm-up, the exogenous input stream and the
endogenous stream; conditions differ only in their HPO settings (the noise branch C~ also in its endogenous stream).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from . import registry
from .field import ALL_OFF, ALL_ON, INTERACTION_KEYS, Field, validate
from .metrics import EXTERNAL_EFFECTS, measure, world_measure
from .operations import ESSENTIAL
from .reconfig import EPOCH, Controller
from .registry import KINDS
from .stats import contrast
from .world import NOISE_OFFSET, World, build_world

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "HPO_PROTOCOL.md"
PROTOCOL_SHA256 = "71e589c7d88cdb1119810579121e65a89c4557b98856c66fd047d6c031f67685"
RESULTS = ROOT / "backend" / "experiments" / "results" / "hpo"

WORLD = {"n": 800, "regime": "intermittent"}
WARMUP = 40
HORIZON = 240
DEV_SEEDS = {"gen": list(range(0, 8)) + [3], "engine": list(range(1000, 1008)) + [101, 102, 103]}
RANGES = {  # (generator seed base, engine seed base) — disjoint from the development seeds and from each other
    "hpo001": (3000, 30000), "hpo002": (100, 20000), "general": (5000, 50000), "hpo003": (4000, 40000),
    "hpo003_validation": (4500, 45000), "smoke": (9000, 90000), "smoke_validation": (9500, 95000),
}
B_SWITCHES = {"share_info": True, "share_resources": True, "share_history": True}
ABLATIONS = ["transform", "observation_change", "competition_adapt", "partition", "reclassify", "action_filter",
             "share_info", "share_resources", "share_history", "feedback"]
CEASE_AT, RESTORE_AT = 80, 160
GENERAL_SETTINGS: dict[str, dict[str, dict]] = {
    "sparse": {"world": {"regime": "sparse"}},
    "churn": {"world": {"regime": "churn"}},
    "memory_heavy": {"world": {"regime": "memory_heavy"}},
    "n1200": {"world": {"n": 1200}},
    "separate": {"settings": {"placement": "separate"}},
    "boundary": {"settings": {"boundary": {"veil_scale": 0.5, "gate_scale": 1.5}}},
}
WORLD_METRICS = ["field_ignitions", "memory_mean", "alive_connections", "gate_mean", "reachable_share"]
OP_DOWNSTREAM = ["ignitions", "fired_samples", "cessations", "reignitions", "unobservable_samples", "ops_final",
                 "first_ignition_mean", "ceased_share", "reach_from_regions", "op_states_visited"]


class ProtocolError(RuntimeError):
    pass


def protocol_hash() -> str:
    return hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() if PROTOCOL.exists() else "missing"


def check_protocol() -> None:
    h = protocol_hash()
    if PROTOCOL_SHA256 == "UNFROZEN" or h != PROTOCOL_SHA256:
        raise ProtocolError(f"protocol {PROTOCOL.name} is not frozen at the pinned hash (pinned {PROTOCOL_SHA256[:12]}, "
                            f"file {h[:12]}); confirmatory runs refuse to start")


# ---------------------------------------------------------------------------------------------- conditions
def settings_for(cond: str, base: dict | None = None) -> dict | None:
    """HPO settings of a named HPO-002 condition (None = R0, no HPO)."""
    base = copy.deepcopy(base or {})
    base.setdefault("warmup", WARMUP)
    base.setdefault("horizon", HORIZON)
    ix_c = dict(ALL_ON)
    if cond == "R0":
        return None
    if cond == "A":
        return {**base, "interaction": dict(ALL_OFF)}
    if cond == "B":
        return {**base, "interaction": {**ALL_OFF, **B_SWITCHES}}
    if cond in ("C", "C~"):
        return {**base, "interaction": ix_c}
    if cond == "D":
        return {**base, "interaction": ix_c, "history": {**base.get("history", {}), "reinsert": True}}
    if cond.startswith("E:") or cond.startswith("F:"):
        kind = cond[2:]
        ch = ESSENTIAL[kind][0]
        sched = [{"at": CEASE_AT, "type": "remove_channel", "kind": kind, "channel": ch}]
        if cond.startswith("F:"):
            sched += [{"at": RESTORE_AT, "type": "relocate", "kind": kind, "slot": 1},
                      {"at": RESTORE_AT, "type": "restore_channel", "kind": kind, "channel": ch}]
        return {**base, "interaction": ix_c, "schedule": sched}
    if cond.startswith("G:-"):
        sw = cond[3:]
        s = settings_for("D", base)
        assert s is not None
        if sw == "feedback":
            s["feedback"] = False
        else:
            s["interaction"] = {**s["interaction"], sw: False}
        return s
    raise ValueError(cond)


HPO002_CONDITIONS = (["R0", "A", "B", "C", "C~", "D"] + [f"E:{k}" for k in KINDS] + [f"F:{k}" for k in KINDS]
                     + [f"G:-{x}" for x in ABLATIONS])
HPO002_CONTRASTS = ([("B", "A"), ("C", "B"), ("C", "A"), ("C~", "C"), ("D", "C"), ("A", "R0"), ("C", "R0")]
                    + [(f"E:{k}", "C") for k in KINDS] + [(f"F:{k}", f"E:{k}") for k in KINDS]
                    + [(f"G:-{x}", "D") for x in ABLATIONS])


def _warm(world_cfg: dict, gen: int, seed: int, warmup: int) -> World:
    w = build_world(world_cfg["n"], gen, seed, regime=world_cfg["regime"])
    for _ in range(warmup):
        w.step()
    return w


def run_one(base: World, settings: dict | None, seed: int, ref: World | None, noise: bool = False,
            controller: Controller | None = None, keep_states: bool = False) -> tuple[dict, World, Field | None]:
    w = base.fork(endogenous_seed=seed + NOISE_OFFSET if noise else None).track_rng()
    if settings is None:
        for _ in range(HORIZON):
            w.step()
        return world_measure(w), w, None
    f = Field(w, settings, seed, keep_states=keep_states)
    if controller is None:
        f.run(settings.get("horizon", HORIZON))
    else:
        controller.start(f)
        epochs = settings.get("horizon", HORIZON) // EPOCH
        for ep in range(epochs):
            f.run(EPOCH)
            if f.stopped_at is not None:
                break
            if ep < epochs - 1:
                controller.end_epoch(f, ep)
    return measure(f, ref), w, f


def trace(f: Field, limit: int = 600) -> dict:
    """A compact, display-oriented record of one run: operations (with lineage and status timeline), the run's own
    registry of kinds (including composite kinds created at run time), causal events, and one deepest causal chain."""
    evs = f.history.events
    ops = []
    for o in f.ops.values():
        timeline = [{"t": e["t"] - f.t0, "type": e["type"]} for e in evs
                    if e["target"] == o.oid and e["type"] in ("config", "ignite", "reignite", "cease", "split",
                                                              "couple", "reclassify", "revise")]
        ops.append({"oid": o.oid, "label": o.label, "status": o.status, "lineage": o.lineage,
                    "created_at": o.created_at - f.t0, "region_size": int(len(o.region)),
                    "instrument": o.instrument.to_dict(), "timeline": timeline[:60]})
    kinds_seen = sorted({o.label for o in f.ops.values()})
    keep = [e for e in evs if e["type"] not in ("unobservable", "feedback")][:limit]
    deepest = f.history.deepest()
    return {"operations": ops, "runtime_kinds": [{"label": k, "registry": all(x in KINDS for x in k.split("∘")),
                                                  "composite": "∘" in k} for k in kinds_seen],
            "events": [{**{k: v for k, v in e.items() if k not in ("before", "after")}, "t": e["t"] - f.t0}
                       for e in keep],
            "events_total": len(evs), "deepest_chain": f.history.chain(deepest, 14) if deepest is not None else [],
            "summary": f.history.summary(),
            "transform_examples": [{"t": e["t"] - f.t0, "source": e["source"], "target": e["target"],
                                    "rule": e.get("detail", {}).get("rule"), "before": e.get("before"),
                                    "after": e.get("after")} for e in evs if e["type"] == "transform"][:12],
            "series": {k: v[::4] for k, v in f.stats["series"].items()}, "rules_note": "see field.RULES"}


# ---------------------------------------------------------------------------------------------- HPO-002 seed job
def hpo002_job(args: tuple) -> dict:
    i, world_cfg, base_settings, conds, want_trace = args
    gen0, seed0 = RANGES[world_cfg.get("_range") or "hpo002"]
    gen, seed = gen0 + i, seed0 + i
    base = _warm(world_cfg, gen, seed, WARMUP)
    out: dict[str, Any] = {"i": i, "gen": gen, "seed": seed, "metrics": {}}
    r0m, r0w, _ = run_one(base, None, seed, None)
    out["metrics"]["R0"] = r0m
    t0 = time.time()
    for c in conds:
        if c == "R0":
            continue
        s = settings_for(c, base_settings)
        m, _, f = run_one(base, s, seed, r0w, noise=c == "C~", keep_states=want_trace and c == "D")
        out["metrics"][c] = m
        if want_trace and c == "D" and f is not None:
            out["trace"] = trace(f)
    out["seconds"] = time.time() - t0
    return out


def _metric_names(rows: list[dict]) -> list[str]:
    names: list[str] = []
    for r in rows:
        for k in r:
            if k not in names:
                names.append(k)
    return names


def analyse_contrasts(jobs: list[dict], pairs: list[tuple[str, str]], seed: int) -> dict:
    noise_x = [j["metrics"]["C~"] for j in jobs if "C~" in j["metrics"]]
    noise_y = [j["metrics"]["C"] for j in jobs if "C~" in j["metrics"]]
    noise = None
    if noise_x:
        names = _metric_names(noise_x)
        noise = {m: np.array([a.get(m, math.nan) - b.get(m, math.nan) for a, b in zip(noise_x, noise_y, strict=True)],
                             float) for m in names}
    out = {}
    for x, y in pairs:
        rx = [j["metrics"][x] for j in jobs]
        ry = [j["metrics"][y] for j in jobs]
        names = [m for m in _metric_names(rx) if m in _metric_names(ry) and not m.startswith("div_")
                 and m != "endogenous_divergence_step"]
        if y == "R0":
            names = [m for m in WORLD_METRICS if m in names]
        out[f"{x} vs {y}"] = contrast(rx, ry, names, None if (x, y) == ("C~", "C") else noise, seed)
    return out


def verdicts(c: dict) -> dict:
    """Pre-registered hypotheses (docs/HPO_PROTOCOL.md §5) evaluated on the contrast table."""
    def det(key: str, ms: list[str]) -> list[str]:
        return [m for m in ms if c[key].get(m, {}).get("status") == "DETECTED"]

    out: dict[str, Any] = {}
    cb = "C vs B"
    world_hit = det(cb, WORLD_METRICS)
    op_hit = det(cb, OP_DOWNSTREAM)
    out["H1_mutual_transformation"] = {
        "mechanism_present": c[cb]["transformations"]["status"] == "DETECTED" and c[cb]["transformations"]["mean"] > 0,
        "world_downstream_detected": world_hit, "operation_downstream_detected": op_hit,
        "verdict": ("SUPPORTED IN THIS PROXY" if world_hit and op_hit and c[cb]["transformations"]["mean"] > 0 else
                    "PARTIAL" if (world_hit or op_hit) else "NOT SUPPORTED")}
    dc = "D vs C"
    down = det(dc, WORLD_METRICS + OP_DOWNSTREAM + ["transformations", "conflicts", "couplings"])
    out["H2_historical_reinsertion"] = {"reinsertions_mean": c[dc]["reinsertions"]["mean_x"], "downstream_detected": down,
                                        "verdict": "SUPPORTED IN THIS PROXY" if down and c[dc]["reinsertions"]["mean_x"] > 0
                                        else "NOT SUPPORTED"}
    h3, h4 = {}, {}
    for k in KINDS:
        e = c[f"E:{k} vs C"]
        ceased = e.get(f"cessations:{k}", {}).get("mean", 0) > 0 or e.get(f"cessations:{k}", {}).get("status") == "DETECTED"
        others = det(f"E:{k} vs C", WORLD_METRICS + OP_DOWNSTREAM + ["transformations", "filtered", "conflicts"])
        h3[k] = {"target_cessations_delta": e.get(f"cessations:{k}", {}).get("mean"), "downstream_detected": others,
                 "verdict": "CONSEQUENCES DETECTED" if others else "NO DETECTED CONSEQUENCE",
                 "target_ceased_more": ceased}
        fk = c[f"F:{k} vs E:{k}"]
        r = fk.get(f"reignitions:{k}", {})
        h4[k] = {"reignitions_F": r.get("mean_x"), "reignitions_E": r.get("mean_y"), "status": r.get("status"),
                 "verdict": "RE-IGNITION UNDER CHANGED CONFIGURATION DETECTED" if r.get("status") == "DETECTED"
                 and r.get("mean", 0) > 0 else "NOT DETECTED"}
    out["H3_cessation"] = h3
    out["H4_reignition"] = h4
    h5 = {}
    for x in ABLATIONS:
        g = f"G:-{x} vs D"
        hit = det(g, WORLD_METRICS + OP_DOWNSTREAM + ["transformations", "filtered", "conflicts", "couplings",
                                                      "splits", "reinsertions", "revisions", "param_drift"])
        h5[x] = {"detected": hit, "verdict": "CONTRIBUTES" if hit else "NO DETECTED CONTRIBUTION"}
    out["H5_ablation"] = h5
    out["H6_real_effects"] = {k: det(f"{k} vs R0", WORLD_METRICS) for k in ("A", "C")}
    nz = c["C~ vs C"]
    n_det = sum(1 for v in nz.values() if v.get("status") == "DETECTED")
    n_all = sum(1 for v in nz.values() if v.get("n", 0))
    out["control_noise"] = {"detected": n_det, "metrics": n_all, "share": n_det / max(1, n_all),
                            "valid": n_det / max(1, n_all) <= 0.05}
    return out


def run_pool(fn, args: list, procs: int) -> list:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    if procs <= 1:
        return [fn(a) for a in args]
    with ProcessPoolExecutor(procs) as ex:
        return list(ex.map(fn, args, chunksize=1))


def provenance() -> dict:
    from ..experiments.escalation.runner import provenance as p
    return {**p(), "protocol_sha256": protocol_hash(), "pinned_protocol_sha256": PROTOCOL_SHA256}


def hpo002(seeds: int, procs: int, confirmatory: bool = True, range_name: str = "hpo002") -> dict:
    if confirmatory:
        check_protocol()
    t0 = time.time()
    world = {**WORLD, "_range": range_name}
    jobs = run_pool(hpo002_job, [(i, world, {}, HPO002_CONDITIONS, i == 0) for i in range(seeds)], procs)
    c = analyse_contrasts(jobs, HPO002_CONTRASTS, 2002)
    v = verdicts(c)
    real = {cond: {m: float(np.mean([j["metrics"][cond].get(m, math.nan) for j in jobs]))
                   for m in ("div_connections", "div_memory", "div_identical", "endogenous_divergence_step")}
            for cond in HPO002_CONDITIONS if cond != "R0"}
    means = {cond: {m: _nanmean([j["metrics"][cond].get(m) for j in jobs]) for m in _metric_names([jobs[0]["metrics"][cond]])}
             for cond in HPO002_CONDITIONS}
    n_cmp = seeds * len(HPO002_CONTRASTS)
    return {"experiment": "HPO-002 Cross-Operational Transformation", "seeds": seeds,
            "seed_ranges": {"name": range_name, "generator": [RANGES[range_name][0], RANGES[range_name][0] + seeds - 1],
                            "engine": [RANGES[range_name][1], RANGES[range_name][1] + seeds - 1]},
            "world": WORLD, "warmup": WARMUP, "horizon": HORIZON, "conditions": HPO002_CONDITIONS,
            "condition_settings": {k: settings_for(k) for k in HPO002_CONDITIONS},
            "contrast_pairs": [f"{x} vs {y}" for x, y in HPO002_CONTRASTS], "paired_comparisons": n_cmp,
            "contrasts": c, "verdicts": v, "means": means, "divergence_from_R0": real,
            "trace": jobs[0].get("trace"), "elapsed_s": round(time.time() - t0, 1),
            "external_effects": EXTERNAL_EFFECTS, "provenance": provenance(), "registry": registry.snapshot(),
            "rules": [list(r[:4]) + [list(r[4])] for r in _rules()]}


def _rules() -> list:
    from .field import RULES
    return RULES


def _nanmean(xs: list) -> float | None:
    v = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return float(np.mean(v)) if v else None


# ---------------------------------------------------------------------------------------------- generalization
def general_job(args: tuple) -> dict:
    i, name, range_name = args
    spec = GENERAL_SETTINGS[name]
    world_cfg = {**WORLD, **spec.get("world", {}), "_range": range_name}
    return hpo002_job((i, world_cfg, spec.get("settings", {}), ["R0", "A", "B", "C", "C~", "D"], False))


def generalization(seeds: int, procs: int, confirmatory: bool = True, range_name: str = "general") -> dict:
    if confirmatory:
        check_protocol()
    out: dict[str, Any] = {"settings": GENERAL_SETTINGS, "seeds_per_setting": seeds, "results": {}}
    pairs = [("B", "A"), ("C", "B"), ("C~", "C"), ("D", "C"), ("C", "R0")]
    for name in GENERAL_SETTINGS:
        jobs = run_pool(general_job, [(i, name, range_name) for i in range(seeds)], procs)
        c = analyse_contrasts(jobs, pairs, 2003)
        nz = c["C~ vs C"]
        out["results"][name] = {
            "contrasts": {k: {m: {x: v[x] for x in ("status", "mean", "relative", "dz", "p_holm", "n") if x in v}
                              for m, v in t.items()} for k, t in c.items()},
            "H1_world": [m for m in WORLD_METRICS if c["C vs B"][m]["status"] == "DETECTED"],
            "H1_operation": [m for m in OP_DOWNSTREAM if c["C vs B"].get(m, {}).get("status") == "DETECTED"],
            "H2_downstream": [m for m in WORLD_METRICS + OP_DOWNSTREAM if c["D vs C"].get(m, {}).get("status") == "DETECTED"],
            "noise_detected_share": sum(v.get("status") == "DETECTED" for v in nz.values()) / max(1, len(nz)),
        }
    out["paired_comparisons"] = seeds * len(pairs) * len(GENERAL_SETTINGS)
    out["seed_ranges"] = {"name": range_name, "generator": RANGES[range_name][0], "engine": RANGES[range_name][1]}
    out["provenance"] = provenance()
    return out


# ---------------------------------------------------------------------------------------------- HPO-001
def hpo001_job(args: tuple) -> dict:
    i, range_name = args
    gen, seed = RANGES[range_name][0] + i, RANGES[range_name][1] + i
    base = _warm(WORLD, gen, seed, WARMUP)
    out: dict[str, Any] = {"i": i, "metrics": {}}
    r0m, r0w, _ = run_one(base, None, seed, None)
    out["metrics"]["R0"] = r0m
    nm, nw, _ = run_one(base, None, seed, None, noise=True)
    out["metrics"]["R0~"] = {**nm, "div_connections": float(np.mean((nw.state.alive != r0w.state.alive) |
                                                                     (np.abs(nw.state.weight - r0w.state.weight) > 1e-9)))}
    for k in KINDS:
        for mode in ("instrument", "oracle"):
            s = {"kinds": [k], "interaction": dict(ALL_OFF), "warmup": WARMUP, "horizon": HORIZON}
            if mode == "oracle":
                s["instruments"] = {k: {"oracle": True}}
            m, _, _ = run_one(base, s, seed, r0w)
            out["metrics"][f"{mode}:{k}"] = m
    return out


def hpo001(seeds: int, procs: int, confirmatory: bool = True, range_name: str = "hpo001") -> dict:
    if confirmatory:
        check_protocol()
    jobs = run_pool(hpo001_job, [(i, range_name) for i in range(seeds)], procs)
    res: dict[str, Any] = {}
    metrics = ["ignitions", "fired_samples", "first_ignition_mean", "cessations", "reignitions", "applied_records",
               "unobservable_samples", "picturing_error"] + WORLD_METRICS
    for k in KINDS:
        rows_i = [j["metrics"][f"instrument:{k}"] for j in jobs]
        rows_o = [j["metrics"][f"oracle:{k}"] for j in jobs]
        rows_r = [j["metrics"]["R0"] for j in jobs]
        ms = [m for m in metrics if m in rows_i[0]]
        res[k] = {
            "truth_leak (oracle vs instrument)": contrast(rows_o, rows_i, ms, None, 1001),
            "instrument vs R0 (world)": contrast(rows_i, rows_r, WORLD_METRICS, None, 1002),
            "branching": {
                "endogenous_divergence_step_mean": _nanmean([r.get("endogenous_divergence_step") for r in rows_i]),
                "share_identical_to_R0": _nanmean([r.get("div_identical") for r in rows_i]),
                "div_connections_mean": _nanmean([r.get("div_connections") for r in rows_i]),
                "noise_div_connections_mean": _nanmean([j["metrics"]["R0~"]["div_connections"] for j in jobs])},
        }
    return {"experiment": "HPO-001 (re-specified; pilot not inherited)", "seeds": seeds,
            "pilot_assets": {"HPO_001_Pilot.zip": "not available in the implementation environment (searched the "
                             "machine); no pilot code or result was inherited, reconstructed or estimated"},
            "corrections_implemented": [
                "operations receive instrument observations only; the world's true state is read by the harness "
                "(oracle access exists only as the explicit truth-leak control)",
                "exogenous input comes from its own stream, identical in every paired branch; the endogenous stream "
                "is tracked and its first divergence from the no-HPO branch is reported (intervention-branched "
                "continuation) separately from the exogenously matched comparison",
                "prediction error (picturing) is reported as a property of the proxy under this configuration, never "
                "as a ranking of philosophical theories"],
            "results": res, "paired_comparisons": seeds * len(KINDS) * 2, "provenance": provenance(),
            "not_a_ranking": "No metric here ranks the philosophical series against one another; the series do "
                             "different things and their proxies are not commensurable as theories."}


# ---------------------------------------------------------------------------------------------- HPO-003
def hpo003_job(args: tuple) -> dict:
    i, range_name = args
    gen, seed = RANGES[range_name][0] + i, RANGES[range_name][1] + i
    base = _warm(WORLD, gen, seed, WARMUP)
    _, r0w, _ = run_one(base, None, seed, None)
    s = settings_for("D")
    out: dict[str, Any] = {"i": i, "metrics": {}}
    st = Controller("static", seed)
    out["metrics"]["static"], _, _ = run_one(base, s, seed, r0w, controller=st)
    rc = Controller("recursive", seed)
    out["metrics"]["recursive"], _, f = run_one(base, s, seed, r0w, controller=rc)
    rd = Controller("random", seed, budget=rc.counts)
    out["metrics"]["random"], _, _ = run_one(base, s, seed, r0w, controller=rd)
    out["metrics"]["recursive"]["reconfigurations"] = float(len(rc.trace))
    out["metrics"]["random"]["reconfigurations"] = float(len(rd.trace))
    out["metrics"]["static"]["reconfigurations"] = 0.0
    out["trace"] = rc.trace
    out["proposals"] = rc.proposals
    out["rejected"] = rc.rejected + rd.rejected
    out["trace_sha256"] = hashlib.sha256(json.dumps(rc.trace, sort_keys=True, default=str).encode()).hexdigest()
    out["final_settings"] = {k: f.s[k] for k in ("instruments", "order", "allocation", "history", "stop", "variables")} \
        if f is not None else None
    return out


def hpo003_validation_job(args: tuple) -> dict:
    i, variable, range_name = args
    gen, seed = RANGES[range_name][0] + i, RANGES[range_name][1] + i
    base = _warm(WORLD, gen, seed, WARMUP)
    _, r0w, _ = run_one(base, None, seed, None)
    s = settings_for("D")
    assert s is not None
    m0, _, _ = run_one(base, s, seed, r0w)
    m1, _, _ = run_one(base, {**s, "variables": [variable]}, seed, r0w)
    return {"i": i, "without": m0, "with": m1}


def hpo003(seeds: int, procs: int, validation_seeds: int, confirmatory: bool = True, range_name: str = "hpo003",
           validation_range: str = "hpo003_validation") -> dict:
    if confirmatory:
        check_protocol()
    jobs = run_pool(hpo003_job, [(i, range_name) for i in range(seeds)], procs)
    rows = {k: [j["metrics"][k] for j in jobs] for k in ("static", "recursive", "random")}
    ms = [m for m in _metric_names(rows["recursive"]) if not m.startswith("div_") and m != "endogenous_divergence_step"]
    c = {"recursive vs static": contrast(rows["recursive"], rows["static"], ms, None, 3001),
         "random vs static": contrast(rows["random"], rows["static"], ms, None, 3002),
         "recursive vs random": contrast(rows["recursive"], rows["random"], ms, None, 3003)}
    paths: dict[str, int] = {}
    for j in jobs:
        for ch in j["trace"]:
            p = ch["path"].split(".")
            key = ".".join(p[:1] + (["*"] + p[2:] if p[0] in ("instruments", "allocation") else p[1:]))
            paths[key] = paths.get(key, 0) + 1
    props: dict[str, dict] = {}
    for j in jobs:
        for p in j["proposals"]:
            e = props.setdefault(p["name"], {"name": p["name"], "seeds_proposed": 0, "rationale": p["rationale"],
                                             "status": p["status"]})
            e["seeds_proposed"] += 1
    validation = {}
    for name, p in props.items():
        if name == "activity_trend":
            vj = run_pool(hpo003_validation_job, [(i, name, validation_range) for i in range(validation_seeds)], procs)
            vc = contrast([v["with"] for v in vj], [v["without"] for v in vj],
                          ["picturing_error", "revisions", "fired_samples", "ignitions", "field_ignitions"], None, 3004)
            pe = vc["picturing_error"]
            ok = pe["status"] == "DETECTED" and pe["mean"] < 0
            p["status"] = "validated (held-out seeds)" if ok else "not validated (held-out seeds)"
            validation[name] = {"seeds": validation_seeds, "contrast": vc, "criterion": "picturing_error DETECTED "
                                "and lower with the variable than without, on held-out seeds"}
    # reproducibility: re-run two seeds and compare the reconfiguration traces
    again = run_pool(hpo003_job, [(i, range_name) for i in range(min(2, seeds))], 1)
    repro = all(a["trace_sha256"] == b["trace_sha256"] for a, b in zip(again, jobs, strict=False))
    return {"experiment": "HPO-003 Recursive Reconfiguration of Ziran System", "seeds": seeds, "epoch": EPOCH,
            "horizon": HORIZON, "base_condition": "D", "contrasts": c,
            "means": {k: {m: _nanmean([r.get(m) for r in v]) for m in ms} for k, v in rows.items()},
            "changed_paths": dict(sorted(paths.items(), key=lambda kv: -kv[1])), "proposals": list(props.values()),
            "validation": validation, "rejected_changes": sum(len(j["rejected"]) for j in jobs),
            "trace_example": jobs[0]["trace"], "final_settings_example": jobs[0]["final_settings"],
            "reproducible_trace": repro, "paired_comparisons": seeds * 3, "sandbox": sorted(_sandbox_paths()),
            "provenance": provenance()}


def _sandbox_paths() -> list[str]:
    from .reconfig import SANDBOX
    return list(SANDBOX)


# ---------------------------------------------------------------------------------------------- reproducibility
def reproducibility(seeds: int = 2) -> dict:
    """Same seed, same conditions → identical metrics (re-run in this process)."""
    conds = ["A", "C", "D", "E:withdrawal", "F:picturing"]
    a = [hpo002_job((i, {**WORLD, "_range": "smoke"}, {}, ["R0", *conds], False)) for i in range(seeds)]
    b = [hpo002_job((i, {**WORLD, "_range": "smoke"}, {}, ["R0", *conds], False)) for i in range(seeds)]
    same = all(json.dumps(x["metrics"], sort_keys=True, default=str) == json.dumps(y["metrics"], sort_keys=True, default=str)
               for x, y in zip(a, b, strict=True))
    return {"seeds": seeds, "conditions": conds, "identical": same}


def clean(x: Any) -> Any:
    """JSON-safe copy: NaN/±inf → None (strict JSON for the viewer), numpy → Python, sets/tuples → lists."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, list | tuple | set | frozenset):
        return [clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return clean(x.tolist())
    if isinstance(x, np.generic):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def write(name: str, doc: dict, root: Path | None = None) -> Path:
    out = root or RESULTS
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.json"
    p.write_text(json.dumps(clean(doc), indent=1, default=_default, ensure_ascii=False, allow_nan=False))
    return p


def _default(x: Any) -> Any:
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, set | frozenset | tuple):
        return list(x)
    if isinstance(x, float) and math.isnan(x):
        return None
    raise TypeError(type(x).__name__)


__all__ = ["hpo001", "hpo002", "hpo003", "generalization", "reproducibility", "settings_for", "validate",
           "INTERACTION_KEYS"]
