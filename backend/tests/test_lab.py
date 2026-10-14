"""Laboratory layer (xzr/lab): apparatus state is a function of runtime state, events carry runtime provenance,
recording does not change the run, and an independent replay agrees step by step."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from xzr.hpo.field import ALL_ON, Field
from xzr.hpo.world import build_world
from xzr.lab import apparatus
from xzr.lab.record import DEFAULT_CONFIG, run
from xzr.lab.replay import replay

SHORT = {**DEFAULT_CONFIG, "horizon": 80}
LAB = Path(__file__).resolve().parents[1] / "xzr" / "lab"


@pytest.fixture(scope="module")
def rec():
    return run(SHORT)


def test_recording_does_not_change_the_run(rec):
    """The taps only read: the same field without the lab layer reaches the same runtime fingerprint."""
    w = build_world(SHORT["n"], SHORT["gen_seed"], SHORT["seed"], regime=SHORT["regime"])
    for _ in range(SHORT["warmup"]):
        w.step()
    f = Field(w, {"interaction": dict(ALL_ON), "history": {"reinsert": True}, "warmup": 40, "horizon": 80},
              SHORT["seed"], keep_states=False)
    f.run(80)
    assert w.engine.fingerprint() == rec["steps"][-1]["fingerprint"]


def test_independent_replay_agrees_step_by_step(rec):
    r = replay(rec)
    assert r["agreement"] and r["mismatched_steps"] == 0 and r["events_identical"]


def test_replay_detects_a_tampered_record(rec):
    bad = json.loads(json.dumps(rec))
    bad["steps"][30]["shutter"][0] = 0.123
    assert not replay(bad)["agreement"]


def test_apparatus_state_is_derived_from_runtime_state_only():
    w = build_world(400, 9101, 91001)
    for _ in range(20):
        w.step()
    cs = apparatus.chambers(w.h)
    s1 = apparatus.state(w.state, cs, np.zeros(0, np.int32))
    edges = np.flatnonzero(w.state.alive)
    inside = np.isin(w.state.dst[edges], cs[0].nodes) & ~np.isin(w.state.src[edges], cs[0].nodes)
    w.state.gate[edges[inside]] = 0.25  # a runtime gate closes the chamber's incoming boundary
    s2 = apparatus.state(w.state, cs, np.zeros(0, np.int32))
    assert s2["shutter"][0] == pytest.approx(0.25, abs=1e-4) and s1["shutter"][0] == 1.0
    assert s2["shutter"][1:] == s1["shutter"][1:]
    ev = apparatus.events(s1, s2, cs, 1)
    assert [e["type"] for e in ev] == ["containment_close"] and ev[0]["chamber"] == cs[0].cid


def test_every_apparatus_event_has_a_runtime_cause(rec):
    assert rec["events"], "no apparatus event in the run"
    for e in rec["events"]:
        assert e["cause"] and not any(c == "runtime:unattributed" for c in e["cause"]), e
        if e["type"].startswith("containment"):
            assert any(c.startswith(("operation:", "runtime:connection_turnover")) for c in e["cause"])


def test_events_are_exactly_the_threshold_crossings_of_the_recorded_states(rec):
    cs = [apparatus.Chamber(c["cid"], np.zeros(0, np.int32), tuple(c["position"])) for c in rec["chambers"]]
    derived = []
    for a, b in zip(rec["steps"], rec["steps"][1:], strict=False):
        derived += apparatus.events(a, b, cs, b["t"])
    strip = lambda es: [{k: v for k, v in e.items() if k != "cause"} for e in es if e["t"] > 1]  # noqa: E731
    assert strip(derived) == strip(rec["events"])


def test_lab_layer_has_no_rendering_dependency():
    for p in LAB.glob("*.py"):
        mods = {n.module or "" for n in ast.walk(ast.parse(p.read_text())) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(ast.parse(p.read_text())) if isinstance(n, ast.Import) for a in n.names}
        assert not {m for m in mods if any(x in m for x in ("three", "render", "frontend", "service"))}, p.name


def test_records_are_never_overwritten(tmp_path):
    p = tmp_path / "r.json"
    run({**SHORT, "horizon": 20}, p)
    with pytest.raises(FileExistsError):
        run({**SHORT, "horizon": 20}, p)


def test_records_from_before_the_physical_layer_still_replay(rec):
    """A record without the later optional fields (layout, physical_events) — the published m2 record's format."""
    old = {k: v for k, v in json.loads(json.dumps(rec)).items() if k not in ("layout", "physical_events")}
    old["config"] = {k: v for k, v in old["config"].items() if k not in ("physics", "resources")}
    assert replay(old)["agreement"]


def test_published_records_replay():
    root = Path(__file__).resolve().parents[1] / "experiments" / "results" / "lab"
    for p in sorted(root.glob("*.json")):
        r = json.loads(p.read_text())
        if r["config"].get("physics"):
            pytest.importorskip("mujoco")
        assert replay(r)["agreement"], p.name
