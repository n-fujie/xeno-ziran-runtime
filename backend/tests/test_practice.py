"""Scorekeeping, compilation into interventions, and the command grammar."""

from __future__ import annotations

import numpy as np
import pytest

from xzr.practice.compile import InterventionConfig, compile_config
from xzr.practice.graph import Practice
from xzr.practice.parser import GRAMMAR, ParseError, parse
from xzr.runtime.intervention import Gate, ScaleThreshold

SPEC = {
    "concepts": ["h", "b"],
    "claims": [
        {"id": "A", "text": "a", "uses": ["b"], "commitment": 1.0},
        {"id": "B", "text": "b", "uses": ["h"], "commitment": 0.8,
         "bindings": [{"op": "scale_threshold", "target": "S", "factor": 2.0}]},
        {"id": "C", "text": "c", "uses": [], "default_entitled": False,
         "bindings": [{"op": "gate", "target": "S", "factor": 0.0}]},
        {"id": "D", "text": "d", "uses": [], "commitment": 0.0},
    ],
    "dependencies": [{"premises": ["A", "B"], "conclusion": "C"}],
    "incompatibilities": [["B", "D"]],
}


def resolver(target, want):
    return np.arange(5, dtype=np.int32) if want == "nodes" else np.arange(3, dtype=np.int32)


def test_consequence_inherits_weakest_premise():
    sc = Practice.from_json(SPEC).score()
    assert sc.commitment["C"] == 0.8 and sc.entitled["C"]
    assert "consequence of A, B" in sc.status["C"]


def test_removing_a_concept_propagates_to_consequences():
    p = Practice.from_json(SPEC)
    assert p.dependencies_of("h")["direct"] == ["B"] and p.dependencies_of("h")["consequences"] == ["C"]
    p.remove_concept("h")
    sc = p.score()
    assert sc.effective("B") == 0 and sc.effective("C") == 0 and sc.effective("A") == 1.0


def test_incompatibility_stronger_wins_ties_lose_both():
    p = Practice.from_json(SPEC)
    p.assert_claim("D", 0.5)
    sc = p.score()
    assert sc.entitled["B"] and not sc.entitled["D"]
    p.revise("D", 0.8)
    sc = p.score()
    assert not sc.entitled["B"] and not sc.entitled["D"] and not sc.entitled["C"]  # C loses entitled support


def test_weaken_scales_bound_effect_and_withdraw_removes_it():
    p = Practice.from_json(SPEC)
    cfg = InterventionConfig(p, {})
    ov, _, prov, _ = compile_config(cfg, resolver)
    st = [x for x in ov if isinstance(x, ScaleThreshold)][0]
    assert np.isclose(st.factor, 1 + (2 - 1) * 0.8)
    gate = [x for x in ov if isinstance(x, Gate)][0]
    assert np.isclose(gate.factor, 1 + (0 - 1) * 0.8)
    p.weaken("B", 0.5)
    ov, _, _, _ = compile_config(cfg, resolver)
    assert np.isclose([x for x in ov if isinstance(x, ScaleThreshold)][0].factor, 1.4)
    p.withdraw("A")
    ov, _, prov, _ = compile_config(cfg, resolver)
    assert not any(isinstance(x, Gate) for x in ov)
    assert any("inactive" in r["effect"] for r in prov)


def test_boundaries_can_be_removed():
    cfg = InterventionConfig(Practice(), {"S": 0.2})
    ov, _, _, _ = compile_config(cfg, resolver)
    assert ov == [Gate((0, 1, 2), 0.2)]
    cfg.removed_boundaries.add("S")
    ov, _, _, _ = compile_config(cfg, resolver)
    assert ov == []


def test_reconnect_and_disconnect():
    p = Practice.from_json(SPEC)
    assert p.disconnect("C", "B") == 1
    assert p.score().commitment.get("C") is None
    p.reconnect("C", ("A",))
    assert p.score().commitment["C"] == 1.0


@pytest.mark.parametrize("op,rx,example", GRAMMAR)
def test_every_grammar_example_parses_to_its_op(op, rx, example):
    assert parse(example).op == op


def test_parser_forms():
    c = parse("sever relation c12 → c40")
    assert c.op == "sever" and c.args == {"a": "c12", "b": "c40"}
    c = parse("Change ignition threshold of configuration C7 to 0.4")
    assert c.op == "set_threshold" and c.args == {"target": "C7", "value": 0.4}
    c = parse("weaken commitment K2")
    assert c.args["factor"] == 0.5
    c = parse("introduce claim K9 uses a,b binds gate B1 0.2 from K1, K2")
    assert c.args["uses"] == ["a", "b"] and c.args["premises"] == ["K1", "K2"]
    assert c.args["binding"] == {"op": "gate", "target": "B1", "factor": 0.2}
    with pytest.raises(ParseError) as err:
        parse("remove everything")
    assert err.value.suggestions and all(s.startswith("remove") for s in err.value.suggestions)
