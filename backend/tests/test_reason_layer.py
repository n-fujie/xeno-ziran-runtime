"""Reasoning layer: representation equivalence, where representations differ, closed loop, collapse, hygiene."""

from __future__ import annotations

import copy
import random
import re
from pathlib import Path

import numpy as np
import pytest

from xzr.experiments.reason import _rand_edit, _rand_graph, make_loop
from xzr.reasonlab.loop import InterventionGate
from xzr.reasonlab.representations import Edit, apply_edit, build, effective
from xzr.runtime.intervention import Connect, Gate, Sever
from xzr.scenario.io import load_sample

ROOT = Path(__file__).resolve().parents[1] / "xzr"


def lab_json() -> dict:
    return copy.deepcopy(load_sample("reason-lab").practice)


def test_scorekeeping_equals_terminology_free_support_graph_on_random_graphs():
    rng = random.Random(7)
    for _ in range(300):
        pj = _rand_graph(rng)
        a, b = build("scorekeeping", pj), build("support_greatest", pj)
        for _step in range(4):
            assert effective(a) == effective(b)
            e = _rand_edit(rng, pj)
            apply_edit(a, e)
            apply_edit(b, e)


def test_single_status_differs_exactly_where_an_unentitled_commitment_carries_support():
    pj = lab_json()
    for c in pj["claims"]:
        if c["id"] == "K9":
            c["commitment"] = 1.0  # defeats K4 (0.9) through the K4/K9 incompatibility
    sk, single = effective(build("scorekeeping", pj)), effective(build("support_single", pj))
    assert sk["K4"] == 0.0 and single["K4"] == 0.0  # K4 committed, not entitled
    assert sk["K8"] == pytest.approx(0.9)  # self-standing consequence of an unentitled commitment
    assert single["K8"] == 0.0  # one status: no support flows out of K4
    assert {k: v for k, v in sk.items() if k != "K8"} == {k: v for k, v in single.items() if k != "K8"}


def test_dropping_entitlement_tracking_reactivates_defeated_commitments():
    pj = lab_json()
    for c in pj["claims"]:
        if c["id"] == "K9":
            c["commitment"] = 1.0
    assert effective(build("scorekeeping", pj))["K4"] == 0.0
    assert effective(build("scorekeeping_no_entitlement", pj))["K4"] == pytest.approx(0.9)


def test_least_and_greatest_fixpoints_differ_only_on_circular_support():
    pj = {"concepts": [], "claims": [
        {"id": "A", "commitment": 1.0, "default_entitled": False, "bindings": [{"op": "gate", "target": "X"}]},
        {"id": "B", "commitment": 1.0, "default_entitled": False, "bindings": []}],
        "dependencies": [{"premises": ["A"], "conclusion": "B"}, {"premises": ["B"], "conclusion": "A"}],
        "incompatibilities": []}
    assert effective(build("scorekeeping", pj))["A"] == 1.0
    assert effective(build("support_greatest", pj))["A"] == 1.0
    assert effective(build("support", pj))["A"] == 0.0


def test_alternate_representation_uses_no_scorekeeping_terminology():
    words = re.compile(r"commit|entitle|brandom|wolfendale|responsib|human", re.IGNORECASE)
    src = (ROOT / "practice" / "support.py").read_text()
    assert not words.search(src)


# ------------------------------------------------------------------------------------------------ closed loop
def test_reasoning_enabled_changes_interventions_and_disabled_does_not():
    on, off = make_loop("scorekeeping"), make_loop("none")
    on.run(200)  # the world's own record level first meets the enabling conditions around t≈90
    off.run(200)
    assert any(r["phase"] == "reasoning" for r in on.timeline)
    assert not any(r["phase"] == "reasoning" for r in off.timeline if r.get("effective"))
    assert len(on.overlay) > len(off.overlay)
    assert on.world.engine.fingerprint() != off.world.engine.fingerprint()


def test_replaying_the_intervention_schedule_reproduces_the_reasoning_run_exactly():
    from xzr.experiments.reason import _schedule_json
    from xzr.runtime.intervention import from_dict
    src = make_loop("scorekeeping")
    src.run(150)
    assert len(src.overlay_changes) > 2  # the schedule really contains reasoning-driven changes
    sched = [(t, [from_dict(x) for x in items]) for t, items in _schedule_json(src)]
    rep = make_loop("replay", replay=sched)
    rep.run(150)
    assert rep.world.engine.fingerprint() == src.world.engine.fingerprint()


def test_intervention_gate_accepts_only_operational_overlay_records():
    loop = make_loop("none")
    g = InterventionGate(loop.world.engine)
    g.set_overlay([Gate((1, 2), 0.5)])
    for bad in (Sever((1,)), Connect(1, 2), "claim K1", {"op": "gate"}):
        with pytest.raises(TypeError):
            g.set_overlay([bad])


def test_reasoning_layer_never_writes_world_state_directly():
    src = (ROOT / "reasonlab" / "loop.py").read_text()
    assert not re.search(r"state\.\w+(\[[^\]]*\])?\s*[-+*/]?=(?!=)", src)
    assert ".apply(" not in src.replace("self.gate", "")  # only overlay records via the gate


def test_enabling_conditions_are_configurable():
    never = [{"metric": "memory", "target": "R", "op": ">", "value": 1e9}]
    loop = make_loop("scorekeeping", enabling=never)
    loop.run(60)
    assert {r["phase"] for r in loop.timeline} == {"not_enabled"}
    assert loop.overlay == [] or all(type(i).__name__ != "MemoryCondition" for i in loop.overlay)
    free = make_loop("scorekeeping", enabling=[])
    free.run(40)
    assert free.timeline[-1]["phase"] == "reasoning"


def test_reasoning_collapses_when_external_memory_is_removed():
    loop = make_loop("scorekeeping", world_events=[{"t": 200, "items": [
        {"kind": "memory_condition", "target": "R", "decay": 0.3}]}])
    loop.run(400)
    phases = [r["phase"] for r in loop.timeline]
    assert "reasoning" in phases[:20] and phases[-1] == "collapsed"
    assert max(loop.rep.asserted.values()) < 0.5  # records decayed while collapsed


def test_grounded_revision_activates_the_commitment_distinction():
    g = [{"claim": "K9", "when": {"metric": "activity", "target": "B", "op": "<", "value": 1.0}, "window": 1,
          "effect": "assert", "level": 1.0}]
    loop = make_loop("scorekeeping", enabling=[], groundings=g)
    loop.run(40)
    assert loop.revisions >= 1
    assert loop.timeline[-1]["effective"]["K9"] == 1.0
    assert loop.timeline[-1]["commitment_distinction"] and loop.timeline[-1]["entitlement_distinction"]


def test_scheduled_edit_applies_through_compiled_interventions():
    loop = make_loop("scorekeeping", enabling=[], edits=[(40, Edit("remove_token", a="responsibility"))])
    loop.run(40)
    before = len(loop.overlay)
    assert before > 0
    loop.run(5)
    assert len(loop.overlay) < before  # K4 (gate BB), K6, K8 lose their effects


def test_closed_loop_is_deterministic():
    a, b = make_loop("scorekeeping"), make_loop("scorekeeping")
    a.run(120)
    b.run(120)
    assert a.world.engine.fingerprint() == b.world.engine.fingerprint()
    assert np.array_equal([r["enabled"] for r in a.timeline], [r["enabled"] for r in b.timeline])


def test_no_entitlement_scorekeeping_equals_backed_only_support_graph():
    rng = random.Random(11)
    for _ in range(300):
        pj = _rand_graph(rng)
        a, b = build("scorekeeping_no_entitlement", pj), build("support_backed_only", pj)
        for _step in range(4):
            assert effective(a) == effective(b)
            e = _rand_edit(rng, pj)
            apply_edit(a, e)
            apply_edit(b, e)


def test_every_representation_disagreement_is_located_in_a_structural_cause():
    from xzr.experiments.reason import representation_equivalence
    r = representation_equivalence(graphs=400, seed=5)
    for name, st in r["vs_scorekeeping"].items():
        assert st["explained"] == st["disagreements"], name
    assert r["vs_scorekeeping"]["support_greatest"]["disagreements"] == 0
    assert r["vs_scorekeeping"]["support_backed_only"]["disagreements"] == 0


def test_error_detection_from_dependency_records_has_no_false_alarms():
    from xzr.experiments.reason import error_detection
    r = error_detection(trials=120, seed=2)
    assert r["rates"]["dependency_records"]["clean"] == 0.0
    for k in ("orphan", "lost", "tampered"):
        assert r["rates"]["dependency_records"][k] == 1.0


def test_collapse_is_recognised_when_enabling_preceded_permission():
    """Regression: enabling conditions met before reasoning is allowed must still count as 'was active' once it is."""
    loop = make_loop("scorekeeping", reasoning_from=150, world_events=[{"t": 260, "items": [
        {"kind": "memory_condition", "target": "R", "decay": 0.3}]}])
    loop.run(360)
    phases = [r["phase"] for r in loop.timeline]
    assert "reasoning" in phases and phases[-1] == "collapsed"
    assert not any(r.get("commitment_distinction") for r in loop.timeline if r["phase"] != "reasoning")


def test_replay_matches_at_every_step_not_only_eventually():
    from xzr.experiments.reason import _schedule_json
    from xzr.runtime.intervention import from_dict
    src = make_loop("scorekeeping")
    src.run(200)
    sched = [(t, [from_dict(x) for x in items]) for t, items in _schedule_json(src)]
    a, b = make_loop("scorekeeping"), make_loop("replay", replay=sched)
    for _ in range(200):
        a.step()
        b.step()
        assert np.array_equal(a.world.state.gate, b.world.state.gate)
        assert np.array_equal(a.world.state.theta_mod, b.world.state.theta_mod)
    assert a.world.engine.fingerprint() == b.world.engine.fingerprint()
