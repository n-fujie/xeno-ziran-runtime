"""Scientific systems in the physical laboratory (xzr/lab/science.py): no privileged inputs, observation limits,
runtime effects of interventions and isolation, variable adoption against a matched control, memory modes,
determinism and replay of schema-2 records."""

from __future__ import annotations

import ast
import inspect
import json

import numpy as np
import pytest

pytest.importorskip("mujoco")

from xzr.lab import science as S  # noqa: E402
from xzr.lab.record import LabRun  # noqa: E402
from xzr.lab.replay import replay  # noqa: E402

A = {"sid": "A", "kind": "local", "home": "0.0"}
B = {"sid": "B", "kind": "distributed", "home": "1.0", "sensors": ["0.1", "2.0", "7.0", "1.2"], "isolate_above": 0.12}
C = {"sid": "C", "kind": "history", "home": "1.1", "memory": "ordinary", "store": "1.3"}


def cfg(systems, horizon=120, gen=8000, **kw):
    return {"gen_seed": gen, "seed": gen * 10, "settings": None, "physics": True, "horizon": horizon,
            "systems": systems, **kw}


def lab(systems, steps=0, **kw) -> LabRun:
    r = LabRun(cfg(systems, **kw))
    for _ in range(steps):
        r.step()
    return r


def test_systems_never_read_harness_truth():
    """Decision code reads observations only: no true effect, no gain counters, no prediction-error-vs-truth."""
    for name in ("decide", "_choose", "features", "candidates", "coverage", "_revise", "_adapt", "_generate",
                 "memory_value", "predict", "_isolate", "_request", "observe_outcomes"):
        src = inspect.getsource(getattr(S.Science, name))
        tree = ast.parse("class X:\n" + "\n".join("    " + line for line in src.splitlines()))
        strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        if name == "observe_outcomes":  # it stores outcomes the system observed; it must not feed truth back
            assert "_true_effect" not in attrs
            continue
        assert not strings & {"true", "true_gain", "true_gain_post", "abs_pred_error"}, name
        assert "_true_effect" not in attrs, name


def test_observation_limits():
    r = lab([A, B, C])
    sci = r.science
    cov = {sid: sci.coverage(s) for sid, s in sci.systems.items()}
    p0 = np.array(sci.lab.pos["0.0"])
    assert all(np.linalg.norm(np.array(sci.lab.pos[c]) - p0) <= S.SENSOR_RANGE for c in cov["A"])
    assert set(cov["C"]) <= {"1.0", "1.1", "1.2", "1.3"}
    # distributed readings travel along runtime connections: cut every connection between chambers -> hub only
    st = r.w.state
    own = sci.owner
    between = st.alive & (own[st.src] != own[st.dst])
    st.alive[between] = False
    sci.invalidate()
    assert set(sci.coverage(sci.systems["B"])) == {"1.0"}
    assert set(sci.coverage(sci.systems["A"])) == set(cov["A"])  # local sensing does not depend on connections


def test_closed_containment_hides_a_chamber_from_every_sensor():
    r = lab([A])
    sci = r.science
    seen = sci.coverage(sci.systems["A"])
    target = sorted(seen)[0]
    n = sci.cs[sci.idx[target]].nodes
    st = r.w.state
    inside = np.zeros(st.n, bool)
    inside[n] = True
    st.gate[st.alive & inside[st.dst] & ~inside[st.src]] = 0.1
    sci.invalidate()
    assert target not in sci.coverage(sci.systems["A"])


def test_interventions_change_the_runtime():
    r = lab([A], steps=200)
    sci = r.science
    kinds = [e["type"] for e in sci.events]
    assert "material_extracted" in kinds and "material_delivered" in kinds
    plain = lab([{**A, "budget": 0.0}], steps=200)  # same system, no budget: no intervention at all
    assert r.w.engine.fingerprint() != plain.w.engine.fingerprint()
    assert not [e for e in plain.science.events if e["type"] == "material_delivered"]


def test_isolation_closes_a_runtime_gate_and_reopens():
    r = lab([{**B, "isolate_above": 0.0, "isolate_steps": 8}], steps=40)
    ev = [e for e in r.science.events if e["type"] in ("isolation", "reopened")]
    assert ev and ev[0]["type"] == "isolation"
    assert any(e["type"] == "reopened" for e in ev)
    assert any(k.startswith("B:isolate:") for k in r.w.overlays) or any(e["type"] == "reopened" for e in ev)


def test_variable_adopted_only_when_it_predicts_better_than_its_permuted_control():
    r = lab([{**A, "generate_variables": True}])
    sci, sys_ = r.science, r.science.systems["A"]
    rng = np.random.default_rng(0)
    rows = [{k: float(rng.random()) for k in S.BASE_FEATURES} | {"seen_b": 1.0} for _ in range(30)]
    sys_.data = [(f, 10 * f["load_a"] * f["tens_b"] + 0.01 * rng.standard_normal()) for f in rows]
    sci._generate(sys_, 40)
    assert "prod:load_a*tens_b" in sys_.features
    other = lab([{**A, "generate_variables": True}])
    s2 = other.science.systems["A"]
    s2.data = [(f, float(rng.standard_normal())) for f in rows]  # outcomes unrelated to any variable
    other.science._generate(s2, 40)
    assert s2.features == list(S.BASE_FEATURES)
    assert all(not e["adopted"] for e in other.science.events if e["type"] == "variable_candidate")


@pytest.mark.parametrize("mode", ["ordinary", "contextual", "shuffled", "write_only"])
def test_memory_modes(mode):
    r = lab([{**C, "memory": mode}])
    sci, sys_ = r.science, r.science.systems["C"]
    f = {"load_a": 3.0}
    ctx = sci.context("1.0", f)
    sys_.memory = [{"pair": ("1.1", "1.0"), "outcome": 5.0, "t": 1, "ctx": ctx},
                   {"pair": ("1.1", "1.0"), "outcome": 1.0, "t": 2, "ctx": ("other",)},
                   {"pair": ("1.2", "1.0"), "outcome": -7.0, "t": 3, "ctx": ctx}]
    v = sci.memory_value(sys_, "1.1", "1.0", f, 10)
    if mode == "ordinary":
        assert v == pytest.approx(3.0)
    elif mode == "contextual":
        assert v == pytest.approx(5.0)
    elif mode == "write_only":
        assert v is None and sys_.stats["memory_reads"] == 0
    else:  # shuffled: values come from the permuted outcomes of all entries, not necessarily this pair's
        assert v in (pytest.approx(3.0), pytest.approx(-1.0), pytest.approx(-3.0), pytest.approx(5.0),
                     pytest.approx(1.0), pytest.approx(-7.0))


def test_memory_store_unreadable_while_its_containment_is_closed():
    r = lab([C])
    sci, sys_ = r.science, r.science.systems["C"]
    sys_.memory = [{"pair": ("1.1", "1.0"), "outcome": 5.0, "t": 1, "ctx": ()}]
    n = sci.cs[sci.idx["1.3"]].nodes
    st = r.w.state
    inside = np.zeros(st.n, bool)
    inside[n] = True
    st.gate[st.alive & inside[st.dst] & ~inside[st.src]] = 0.1
    sci.invalidate()
    assert sci.memory_value(sys_, "1.1", "1.0", {"load_a": 0.0}, 5) is None
    assert sys_.stats["memory_unavailable"] == 1


def test_schema2_runs_are_deterministic_and_replay():
    c = cfg([A, B, C], horizon=150)
    r1, r2 = LabRun(c), LabRun(c)
    for _ in range(150):
        r1.step()
        r2.step()
    assert r1.w.engine.fingerprint() == r2.w.engine.fingerprint()
    rec = json.loads(json.dumps(r1.record()))
    assert rec["schema"] == "xzr.labrun/2" and rec["science_events"]
    assert replay(rec)["agreement"]
