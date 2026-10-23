"""The total-observation line: world, observers, identification, verifier, SSS, planetary conditions, ontology, and the research loop.

Checks of the machinery on small deterministic runs (reserved functional seeds). They show that each mechanism operates and is recorded; none of them is a
scientific result."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from xzr.hpo.reachability import SET_KEYS
from xzr.totalobs import agent as A
from xzr.totalobs import loop, ontology, planetary, sss
from xzr.totalobs import verifier as V
from xzr.totalobs.identify import IdentParams, identify
from xzr.totalobs.observers import ObserverNet, Record, Sensor
from xzr.totalobs.world import World, WorldConfig

GEN, SEED = 7001, 70001
FULL = {"policy": "adaptive", "history": "own", "meta": True, "strong": list(A.STRONG)}


def warm(cfg: WorldConfig | None = None, steps: int = 40) -> World:
    w = World(cfg or WorldConfig(), GEN, SEED)
    for _ in range(steps):
        w.step()
    return w


def run(design: dict, env: dict | None = None, i: int = 0) -> dict:
    return loop.run(env or {}, {"name": "t", "design": design}, GEN + i, SEED + i)


# ---------------------------------------------------------------------------------------------------- world
def test_world_is_deterministic_and_advances_without_observers():
    a, b = warm(), warm()
    assert np.array_equal(a.u, b.u) and a.t == 40
    assert a.u.sum() > 0  # the object system changes by itself: no observer was involved
    other = World(WorldConfig(), GEN, SEED + 1)
    for _ in range(40):
        other.step()
    assert np.array_equal(other.src_region, a.src_region)  # the generator seed fixes the sources, the engine seed only the noise
    assert not np.array_equal(other.u, a.u)


def test_propagation_is_finite_and_speed_dependent():
    def arrival(c: float, site: int, target: int) -> int | None:
        w = warm(WorldConfig(c=c, noise=0.0))
        f0, f1 = copy.deepcopy(w), copy.deepcopy(w)
        f1.perturb(site, 30.0, 1)
        for k in range(1, 40):
            f0.step()
            f1.step()
            if f1.u[target] - f0.u[target] > 0.05:
                return k
        return None

    cfg = WorldConfig()
    site = 20
    near = next(i for i in range(cfg.n) if World(cfg, GEN, SEED).d[site, i] == 3)
    far = next(i for i in range(cfg.n) if World(cfg, GEN, SEED).d[site, i] == 5)
    assert arrival(1.0, site, near) < arrival(1.0, site, far)  # farther regions are reached later: no instantaneous action
    assert arrival(0.5, site, near) > arrival(2.0, site, near)  # a slower medium delays the same arrival


# ---------------------------------------------------------------------------------------------------- observers
def make_net(**kw) -> tuple[World, ObserverNet]:
    w = warm()
    net = ObserverNet(w.cfg, hub=0, **{k: v for k, v in kw.items() if k in ("latency", "pool", "capacity")})
    net.seed(SEED)
    net.add(
        Sensor(
            "A",
            20,
            radius=3,
            scale=kw.get("scale", 1),
            period=1,
            backaction=kw.get("backaction", 0.05),
            wear=kw.get("wear", 0.08),
        )
    )
    return w, net


def test_scale_costs_resources_and_pool_denies_blocks():
    w1, n1 = make_net(scale=1, pool=1000.0)
    w2, n2 = make_net(scale=2, pool=1000.0)
    n1.observe(w1)
    n2.observe(w2)
    assert n1.stats["blocks_read"] > n2.stats["blocks_read"]  # a coarser scale reads fewer blocks
    w3, n3 = make_net(scale=1, pool=5.0)
    n3.observe(w3)
    assert (
        n3.stats["denied_blocks"] > 0 and n3.stats["blocks_read"] == 5
    )  # resource competition: blocks are not read when the pool is spent


def test_observation_disturbs_and_wears_the_observer_and_the_observer_can_fail():
    w, net = make_net(backaction=0.5, wear=200.0)
    before = float(w.u.sum())
    net.observe(w)
    assert w.u.sum() < before and net.stats["interference"] > 0  # observing changed the observed
    h0 = net.sensors["A"].health
    for _ in range(40):
        w.step()
        net.observe(w)
    assert (
        net.sensors["A"].health < h0 and not net.sensors["A"].alive and net.stats["expired"] == 1
    )  # the observed wore the observer out
    n_records = len(net.store)
    w.step()
    net.observe(w)
    assert len(net.store) == n_records  # an expired observing condition produces nothing more


def test_communication_delay_outage_and_record_loss_leave_the_world_alone():
    w, net = make_net(latency=3)
    net.observe(w)
    rec = net.store[-1]
    assert rec.t_arrive - rec.t_obs == 3 * int(w.d[20, 0])  # delay = hops x latency
    assert net.view(w.t, 1000) == [] or all(r.t_arrive <= w.t for r in net.view(w.t, 1000))
    net.cut(w, 20, 2)
    w.step()
    net.observe(w)
    assert net.stats["lost_in_transit"] == 1  # a sensor inside the outage zone observes but does not report
    net.restore_links()
    # record loss: the material consequence of an intervention outlives every record of it
    w.perturb(20, 10.0, 1)
    marks = float(w.m.sum())
    for _ in range(10):
        w.step()
        net.observe(w)
    lost = net.lose_records(0, w.t + 1)
    assert lost > 0 and len(net.store) == 0 and net.stats["records_lost"] == lost
    assert float(w.m.sum()) > 0.9 * marks  # the marks (material consequence) are still there; only the records are gone


def test_order_of_observation_and_intervention_matters_and_is_deterministic():
    def go(observe_first: bool) -> float:
        w, net = make_net(backaction=0.3)
        if observe_first:
            net.observe(w)
            w.perturb(20, 5.0, 1)
        else:
            w.perturb(20, 5.0, 1)
            net.observe(w)
        for _ in range(8):
            w.step()
        return float(w.u.sum())

    assert go(True) == go(True) and go(False) == go(False)
    assert (
        abs(go(True) - go(False)) > 1e-6
    )  # observe-then-intervene differs from intervene-then-observe (non-commuting in this model; not a quantum claim)


# ---------------------------------------------------------------------------------------------------- identification and verifier
def rec(sid: str, scale: int, blocks: dict, t: int = 5) -> Record:
    return Record(sid, t, t, scale, (0, 0), blocks)


def test_identified_objects_depend_on_the_observing_configuration_not_only_on_the_world():
    cfg = WorldConfig()
    cells = (21, 22, 33, 34)  # a 2x2 patch
    r = rec("A", 2, {(0, 0): (0.3, cells)})
    low = identify(cfg, [r], IdentParams(theta=0.18))
    high = identify(cfg, [r], IdentParams(theta=0.5))
    assert len(low) == 1 and high == []  # the same record: an object exists under one classification and not under another


def test_integration_rule_can_lose_identification():
    cfg = WorldConfig()
    fine = rec("F", 1, {(2, 4): (0.3, (28,))})
    coarse = rec("C", 2, {(1, 2): (0.0, (28, 29, 40, 41))})  # the same region, diluted by a coarse block
    sets = {m: identify(cfg, [fine, coarse], IdentParams(integrate=m)) for m in ("separate", "mean", "finest")}
    assert len(sets["separate"]) == 1 and len(sets["finest"]) == 1  # kept by the rules that keep the fine report
    assert sets["mean"] == []  # lost by averaging: integration can shrink what is identifiable


def test_verifier_separates_world_objects_from_configuration_made_ones():
    w = warm(steps=60)
    truth = V.true_objects(w)
    assert truth, "the world must have an object for this test"
    t_cells = sorted(next(iter(truth)))
    real = {"key": "r", "cells": t_cells}
    ghost_cells = [int(i) for i in np.flatnonzero(w.u < 1e-6)][:2]
    ghost = {"key": "g", "cells": ghost_cells}
    cls = V.classify_identified(w, [real, ghost])
    assert cls == {"r": "world", "g": "configuration"}
    s = V.score(w, [real, ghost])
    assert s["recall"] > 0 and s["spurious"] == 1


# ---------------------------------------------------------------------------------------------------- ontology: what the agent can and cannot see
def test_agent_module_cannot_reach_the_world_or_the_verifier():
    tree = ast.parse(Path(A.__file__).read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not any(
        m in ("world", "verifier", "observers") or m.endswith((".world", ".verifier", ".observers")) for m in imported
    ), imported
    fields = set(A.Findings.__dataclass_fields__)
    assert not ({"u", "m", "world", "truth", "true_objects"} & fields)


def test_ledger_keeps_eight_layers_apart_and_the_audit_catches_violations():
    r = run({"policy": "fixed"})
    t = r["totalobs"]
    assert t["scope_audit"] == [] and list(t["ledger"]["layers"]) == [n for n, _, _ in ontology.LAYERS]
    assert t["ledger"]["layers"]["constructions"]["constructed"] is True
    bad = copy.deepcopy({"ledger": t["ledger"]})
    bad["ledger"]["layers"]["agent_access"]["u"] = [0.1]
    bad["ledger"]["claims"]["earth_claim"] = True
    del bad["ledger"]["layers"]["recording"]
    issues = ontology.scope_audit(bad)
    assert (
        any("world-state fields" in i for i in issues)
        and any("earth_claim" in i for i in issues)
        and any("layers missing" in i for i in issues)
    )


# ---------------------------------------------------------------------------------------------------- the research loop
def test_loop_is_deterministic_and_records_ten_items_per_generation():
    a, b = run(FULL, {"generations": 8}), run(FULL, {"generations": 8})
    strip = lambda r: {k: v for k, v in r.items() if k not in ("wall_s",)}  # noqa: E731
    assert json.dumps(strip(a), sort_keys=True) == json.dumps(strip(b), sort_keys=True)
    gens = a["totalobs"]["generations"]
    assert len(gens) == 8
    for g in gens:
        for key in (
            "before",
            "trigger",
            "changes",
            "levels",
            "ops",
            "world_delta",
            "observation",
            "decision",
            "failure",
            "rule_revision",
        ):
            assert key in g, key  # the ten items of the research loop


def test_loop_runs_several_generations_through_question_changes_and_a_return():
    rs = [run(FULL, {"generations": 12}, i) for i in range(6)]
    qs = {c["to"] for r in rs for g in r["totalobs"]["generations"] for c in g["changes"] if c["what"] == "question"}
    assert {"resolve", "trace"} <= qs  # the question changed with what was found
    assert any(
        r["totalobs"]["final_rc"]["cycle"] >= 1 for r in rs
    )  # a supported hypothesis returned the loop to the first question
    outcomes = {(g["hypothesis_test"] or {}).get("outcome") for r in rs for g in r["totalobs"]["generations"]}
    assert {"supported", "refuted"} & outcomes  # a hypothesis was changed by an experiment
    assert any(
        g["hypothesis_test"] and g["hypothesis_test"].get("true_lag") for r in rs for g in r["totalobs"]["generations"]
    )  # and checked against the verifier


def test_authority_is_a_closed_grammar():
    fixed = run({"policy": "fixed"})
    assert fixed["metrics"]["ops_executed"] == 0
    base = run({"policy": "adaptive"}, {"generations": 10})
    allowed = set(A.GRAMMAR_0) | {"reenter", "extend-grammar"}
    ops = {o["op"] for g in base["totalobs"]["generations"] for o in g["ops"]}
    assert ops <= allowed and "perturb" not in ops  # no intervention without the grammar's extension
    full = [run(FULL, {"generations": 12}, i) for i in range(5)]
    ext = [(g["gen"], o) for r in full for g in r["totalobs"]["generations"] for o in g["ops"] if o["op"] == "extend-grammar"]
    assert ext and all(o["reason"] == "untestable" for _, o in ext)  # an extension has its reason
    with pytest.raises(ValueError):
        A.Design.from_dict({"strong": ["rewrite-the-code"]})  # nothing outside the closed list can be asked for


def test_extension_of_the_grammar_is_withdrawn_when_it_does_not_work():
    env = {"generations": 14, "world": {"c": 0.05}}  # the effect of an intervention does not arrive within a generation
    rs = [run(FULL, env, i) for i in range(6)]
    assert any(r["metrics"]["rollbacks"] >= 1 for r in rs)
    r = next(r for r in rs if r["metrics"]["rollbacks"] >= 1)
    assert any(c["what"] == "grammar" and "withdrawn" in str(c["to"]) for g in r["totalobs"]["generations"] for c in g["changes"])


def test_meta_revision_records_before_evidence_after_and_reaches_later_decisions():
    stress = {"generations": 10, "net": {"pool": 16.0, "n_sensors": 3}}
    rs = [run({"policy": "adaptive", "meta": True}, stress, i) for i in range(8)]
    traces = [m for r in rs for m in r["totalobs"]["meta_trace"]]
    assert traces, "stress should make at least one rule fail twice"
    for m in traces:
        assert {"before", "after", "evidence", "reason", "epoch"} <= set(m) and m["revision"] in ("parameter", "exhausted")
    param = [m for m in traces if m["revision"] == "parameter"]
    assert param and all(m["before"]["params"][m["param"]] != m["after"]["params"][m["param"]] for m in param)
    seen = [
        {k: v for k, v in o["rules_in_force"].items()}
        for r in rs
        for g in r["totalobs"]["generations"]
        for o in g["ops"]
        if o.get("rules_in_force")
    ]
    assert (
        len({json.dumps(s, sort_keys=True) for s in seen}) > 1
    )  # operations after a revision were made under the revised parameters
    none = run({"policy": "adaptive"}, stress)
    assert none["totalobs"]["meta_trace"] == []  # the no-revision control revises nothing


def test_history_is_scoped_by_question_and_a_shuffled_memory_carries_no_outcomes():
    m = A.Memory(mode="own")
    m.write("a@survey", 0.9, {})
    m.write("b@trace", 0.95, {})
    assert m.best_other("c@survey", 0.1)[0] == "a@survey"  # the better condition of the same question, not the other question's
    assert A.Memory(mode=False).best_other("c@survey", 0.1) is None
    s = A.Memory(mode="shuffled")
    for k, v in (("a@q", 0.9), ("b@q", 0.1), ("c@q", 0.5)):
        s.write(k, v, {})
    assert {k: r["score"] for k, r in s._readable().items()} != {k: r["score"] for k, r in s.rows.items()}


def test_failure_stop_and_expiry_are_recorded_not_hidden():
    env = {
        "generations": 6,
        "net": {"n_sensors": 2, "pool": 10.0},
        "events": [{"gen": 1, "do": "fail_sensor", "sensor": "S0"}, {"gen": 1, "do": "fail_sensor", "sensor": "S1"}],
    }
    r = run({"policy": "adaptive", "budget": 3.0}, env)
    assert r["metrics"]["expired_sensors"] >= 2
    assert r["totalobs"]["stopped"] and "no-observer" in r["totalobs"]["stopped"]["reason"]
    assert r["metrics"]["generations_run"] == 6  # the world went on and was scored after the research stopped
    assert any(g["stopped"] for g in r["totalobs"]["generations"])


def test_reachability_levels_use_the_shared_comparison_and_record_expansion_and_contraction():
    r = run(FULL, {"generations": 8, "events": [{"gen": 3, "do": "fail_sensor", "sensor": "S0"}]})
    for g in r["totalobs"]["generations"]:
        lv = g["levels"]
        assert set(SET_KEYS) <= set(lv["dynamic"]) and lv["dynamic_effect"] in ("expanded", "contracted", "mixed", "equivalent")
        assert lv["static_effect"] in ("expanded", "contracted", "mixed", "equivalent")
    g3 = r["totalobs"]["generations"][3]
    assert any(
        "sensor:S0" in x
        for x in g3["levels"]["dynamic_compare"]["executable"]["lost"] + g3["levels"]["dynamic_compare"]["available"]["lost"]
    )  # an expired sensor leaves the sets
    added = [
        g for g in r["totalobs"]["generations"] if any(o["op"] == "add-sensor" and o["status"] == "executed" for o in g["ops"])
    ]
    assert added and any(
        g["levels"]["static_effect"] in ("expanded", "mixed") for g in added
    )  # a new sensor expands what can be observed


def test_derived_variable_is_adopted_only_against_a_matched_control():
    w, net = make_net()
    cfg = w.cfg
    rc = A.RC()
    for _ in range(30):
        w.step()
        net.observe(w)
    res = loop.adopt_variable(cfg, net.view(w.t, 30), rc, "change", w.d, 1)
    assert set(res) >= {"objects_level", "objects_candidate", "objects_control", "adopted", "classes"}
    assert res["adopted"] == (
        res["objects_candidate"] > res["objects_level"] and res["objects_candidate"] > res["objects_control"]
    )
    assert res["classes"][0] in ("transformation", "not adopted")


# ---------------------------------------------------------------------------------------------------- SSS
BASE = {"world": {"rows": 8, "cols": 12, "c": 1.0, "source_period": 28}, "net": {"scale": 1, "period": 4}}


def test_axes_are_changed_independently():
    for ax in sss.AXES:
        e = sss.vary(BASE, ax, "high")
        assert sss.independent(BASE, e, ax) == {
            "changed": {ax: sss.AXIS_PARAMS[ax][:0] + sss.independent(BASE, e, ax)["changed"][ax]},
            "independent": True,
        }
    with pytest.raises(ValueError):
        sss.vary(BASE, "scale", {"world.rows": 3})  # a parameter of another axis cannot be smuggled in
    crossed = sss.vary(sss.vary(BASE, "scale", "high"), "speed", "high")
    assert not sss.independent(BASE, crossed, "scale")["independent"]  # two axes changed: not independent, and said so


def test_factorial_interactions_are_exact_and_undefined_cells_stay_undefined():
    f = lambda e: float(
        e["net"]["scale"] + 2 * (e["world"]["rows"] == 10) + 3 * (e["net"]["scale"] == 2) * (e["world"]["c"] == 2.0)
    )  # noqa: E731
    out = sss.factorial(BASE, ("scale", "size", "speed"), f)
    assert out["main"]["size"] == pytest.approx(2.0) and out["interaction"]["scalexspeed"] == pytest.approx(1.5)
    assert out["interaction"]["sizexspeed"] == pytest.approx(0.0) and out["interaction"]["scalexsizexspeed"] == pytest.approx(0.0)
    holey = sss.factorial(BASE, ("scale", "size"), lambda e: None if e["net"]["scale"] == 2 and e["world"]["rows"] == 10 else 1.0)
    assert holey["main"]["scale"] is None and holey["interaction"]["scalexsize"] is None  # not replaced by 0


def test_metrics_with_changed_definitions_are_not_compared():
    a = {
        "metric": "identified_count",
        "version": 1,
        "basis": {
            "rows": 8,
            "cols": 12,
            "theta": 0.18,
            "connect": 1,
            "scale_profile": (1, 1),
            "variable": "level",
            "integrate": "separate",
        },
    }
    b = {**a, "basis": {**a["basis"], "scale_profile": (2, 2)}}
    c = sss.comparable(a, b)
    assert c["comparable"] is False and any("scale_profile" in r for r in c["reasons"])
    assert sss.comparable(
        {"metric": "recall_region", "version": 1, "basis": {}}, {"metric": "recall_region", "version": 1, "basis": {"rows": 99}}
    )["comparable"]  # a fraction is comparable across Size
    log = sss.MetricLog()
    for t, v in enumerate((0.2, 0.4)):
        log.measure("eval_success", v, {"eval_rule": "E0"}, t)
    log.revise("eval_success", "rule E0 -> E1", 2)
    for t, v in enumerate((0.9, 1.0), start=3):
        log.measure("eval_success", v, {"eval_rule": "E1"}, t)
    segs = log.segments("eval_success")
    assert [len(s) for s in segs] == [2, 2]
    cmp = log.compare("eval_success", 0, 1)
    assert cmp["comparable"] is False and cmp["delta"] is None  # no number across a break of definition
    assert log.registry["eval_success"]["history"][-1]["change"] == "rule E0 -> E1"


def test_a_run_records_breaks_when_the_evaluation_rule_changes():
    r = run(FULL, {"generations": 12})
    for ch in (c for g in r["totalobs"]["generations"] for c in g["changes"] if c["what"] == "evaluation-rule"):
        assert ch["comparable_with_before"] is False
    assert r["totalobs"]["metric_log"]["registry"]["eval_success"]["version"] >= 1


# ---------------------------------------------------------------------------------------------------- planetary conditions
def test_planetary_conditions_are_structural_and_not_met_by_counts_alone():
    base = planetary.conditions({"world": {"rows": 8, "cols": 12}, "net": {}})
    assert base["earth_claim"] is False and base["synthetic"] is True and not base["all_met"]
    big = planetary.conditions(
        {"world": {"rows": 12, "cols": 24, "span": 3, "c": 1.0}, "net": {"n_sensors": 4, "latency": 2, "pool": 24.0, "period": 4}}
    )
    assert big["all_met"]
    # the same number of regions, but instantaneous propagation and a huge pool: not planetary in structure
    flat = planetary.conditions(
        {
            "world": {"rows": 12, "cols": 24, "span": 3, "c": 1000.0},
            "net": {"n_sensors": 400, "latency": 0, "pool": 1e6, "period": 4},
        }
    )
    assert not flat["all_met"] and {r["condition"] for r in flat["conditions"] if not r["met"]} >= {
        "propagation time",
        "resource allocation",
    }
    assert flat["limits"] and flat["requires_for_real_world_claims"]


def test_scaling_law_needs_enough_points_and_recovers_a_known_exponent():
    assert planetary.scaling_law([(8, 3.0), (12, 4.0)])["exponent"] is None
    pts = [(x, 2.0 * x**1.5) for x in (4, 8, 12, 16, 24)]
    fit = planetary.scaling_law(pts)
    assert fit["exponent"] == pytest.approx(1.5, abs=1e-3) and fit["interval"] is not None
    assert "no law is asserted" in fit["note"]


def test_planetary_metrics_and_block_are_in_every_run():
    r = run({"policy": "fixed"})
    assert 0 <= r["metrics"]["planetary_conditions_met"] <= 1 and r["totalobs"]["planetary"]["earth_claim"] is False
