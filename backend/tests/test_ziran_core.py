"""Ziran core additions on the HPO layer: reachability records of configuration changes."""

from __future__ import annotations

import json

import numpy as np
import pytest

from xzr.hpo import experiments as X
from xzr.hpo import reconfig
from xzr.hpo.field import Field
from xzr.hpo.metarevision import BOUNDS, DEFAULTS, MetaReviser, MetaSandboxError, RuleTable
from xzr.hpo.observe import Veil
from xzr.hpo.reachability import delta, reachability
from xzr.hpo.world import build_world


@pytest.fixture(scope="module")
def warm():
    w = build_world(800, 9001, 90001)
    for _ in range(40):
        w.step()
    return w


# ------------------------------------------------------------------------------------------ reachability record
def test_removing_an_essential_channel_closes_the_operation_and_adding_it_reopens(warm):
    f = Field(warm.fork(), {}, 1)
    base = reachability(f)
    assert any(v["runnable"] for v in base.values())
    target = next(oid for oid, v in base.items() if "withdrawal" in v["kinds"] and v["runnable"])

    reconfig.apply(f, {"path": "instruments.withdrawal.channels", "value": "boundary_flow", "op": "remove"}, [])
    closed = reachability(f)
    d = delta(base, closed)
    assert target in d["runnable_closed"] and not d["runnable_opened"]
    assert closed[target]["blocked"]["boundary_flow"] == "instrument_mismatch"
    assert {"oid": target, "channel": "boundary_flow", "now": "instrument_mismatch"} in d["channels_closed"]

    reconfig.apply(f, {"path": "instruments.withdrawal.channels", "value": "boundary_flow", "op": "add"}, [])
    d2 = delta(closed, reachability(f))
    assert target in d2["runnable_opened"]
    assert {"oid": target, "channel": "boundary_flow", "was": "instrument_mismatch"} in d2["channels_opened"]


def test_scale_and_window_changes_are_reported_with_the_reason(warm):
    f = Field(warm.fork(), {}, 1)
    base = reachability(f)
    reconfig.apply(f, {"path": "instruments.transduction.level", "value": 0}, [])
    after = reachability(f)
    tr = [oid for oid, v in after.items() if "transduction" in v["kinds"]]
    assert tr and all(after[o]["blocked"].get("tension") == "scale_mismatch" for o in tr)
    assert all(not after[o]["runnable"] for o in tr)
    reconfig.apply(f, {"path": "instruments.transduction.level", "value": 2}, [])
    reconfig.apply(f, {"path": "instruments.transduction.window", "value": 16}, [])
    assert all(reachability(f)[o]["blocked"].get("tension") == "time_window_mismatch" for o in tr)
    assert delta(base, base)["runnable_opened"] == [] and delta(base, base)["channels_closed"] == []


def test_reachability_reads_the_configuration_and_changes_nothing(warm):
    f = Field(warm.fork(), {}, 1)
    before = json.dumps(f.s, sort_keys=True, default=str)
    n_events = len(f.history.events)
    reachability(f)
    assert json.dumps(f.s, sort_keys=True, default=str) == before and len(f.history.events) == n_events


# ------------------------------------------------------------------------------------------ controller option
def _run_controller(warm, trace: bool):
    f = Field(warm.fork(), X.settings_for("D"), 7)
    ctl = reconfig.Controller("recursive", 7, trace_reachability=trace)
    ctl.start(f)
    for ep in range(3):
        f.run(reconfig.EPOCH)
        ctl.end_epoch(f, ep)
    return f, ctl


def test_tracing_reachability_does_not_change_the_run(warm):
    f0, c0 = _run_controller(warm, False)
    f1, c1 = _run_controller(warm, True)
    strip = [{k: v for k, v in r.items() if k not in ("reachability", "levels", "realised")} for r in c1.trace]
    assert json.dumps(strip, sort_keys=True, default=str) == json.dumps(c0.trace, sort_keys=True, default=str)
    assert f0.s == f1.s and len(f0.history.events) == len(f1.history.events)
    assert all("reachability" not in r for r in c0.trace)
    assert all("reachability" in r for r in c1.trace)


# ------------------------------------------------------------------------------------------ revision of revision rules


def test_a_rule_that_keeps_failing_is_revised_stepwise_then_exhausted():
    m = MetaReviser()
    blind = {"closure": {"boundary_invisible": [1]}}
    seen = []
    for ep in range(12):
        m.register("closure", "boundary_invisible", 100 + ep, ep, [1])
        seen += m.judge(blind, ep)
    revs = [r for r in seen if r["revision"] == "parameter"]
    assert [r["to"] for r in revs] == [0.85, 1.0]  # 0.7 → 0.85 → 1.0 (bound), one revision per PATIENCE failures
    assert seen[-1]["revision"] == "exhausted" and "boundary_invisible" in m.rules.exhausted
    assert m.rules.params["penetration"] == 1.0
    assert all(r["after"] and r["evidence_epochs"] == 2 for r in seen)


def test_a_rule_that_works_is_not_revised():
    m = MetaReviser()
    for ep in range(6):
        m.register("closure", "boundary_invisible", ep, ep, [])
        assert m.judge({}, ep) == []  # the blindness is gone in the next epoch
    assert m.rules.params == DEFAULTS and not m.rules.exhausted


def test_a_failure_streak_is_broken_by_a_success():
    m = MetaReviser()
    out = []
    for ep, persists in enumerate([True, False, True, False, True]):
        m.register("closure", "boundary_invisible", ep, ep, [])
        out += m.judge({"closure": {"boundary_invisible": [1]}} if persists else {}, ep)
    assert out == []


def test_rule_table_is_sandboxed():
    t = RuleTable()
    for bad in (("penetration", 1.5), ("alloc_step", 0.5), ("nonexistent", 1.0), ("lag_step", -1.0)):
        with pytest.raises(MetaSandboxError):
            t.set(*bad)
    assert t.params == DEFAULTS and set(DEFAULTS) == set(BOUNDS)


def test_default_controller_uses_the_original_parameters(warm):
    f0, c0 = _run_controller(warm, False)
    assert c0.rules.params == DEFAULTS and c0.meta is None


def test_controller_with_meta_is_deterministic_and_revision_changes_the_next_change(warm):
    # a thick veil over the whole field: penetration 0.7 cannot see through opacity 0.95, 1.0 can
    def run():
        f = Field(warm.fork(), X.settings_for("D"), 7)
        f.instruments.veils.append(Veil("external", np.arange(len(f.world.h.labels[0])), 0.95, -1, "test"))
        meta = MetaReviser()
        ctl = reconfig.Controller("recursive", 7, meta=meta)
        ctl.start(f)
        for ep in range(6):
            f.run(reconfig.EPOCH)
            ctl.end_epoch(f, ep)
        return ctl, meta

    a, ma = run()
    b, mb = run()
    assert json.dumps(a.trace, sort_keys=True, default=str) == json.dumps(b.trace, sort_keys=True, default=str)
    assert ma.trace == mb.trace
    pens = [(r["epoch"], r["value"]) for r in a.trace if r["path"].endswith(".closure.penetration")]
    assert [r["to"] for r in ma.trace if r["param"] == "penetration"] == [0.85, 1.0]
    assert pens[0][1] == 0.7 and max(v for _, v in pens) == 1.0  # the revision reached the controller's next changes
    assert [e for e, v in pens if v == 0.85][0] > ma.trace[0]["epoch"] - 1


# ------------------------------------------------------------------------------------------ is a generated variable new?
def test_a_derived_variable_is_distinguishable_from_existing_ones_and_its_downstream_effect_is_measured():
    from xzr.study import variables

    n = variables.novelty(n_seeds=3)
    assert 0.0 <= n["novelty"] <= 1.0 and n["novelty"] > 0.5  # activity_trend is not a relabelling of any existing channel
    assert all(abs(c) < 0.9 for c in n["correlation_with_each"].values() if c is not None)
    d = variables.downstream(n_seeds=3, horizon=120)
    assert set(d["paired_with_vs_without"]) >= {"picturing_error", "revisions"} and all(
        v["n"] == 3 for v in d["paired_with_vs_without"].values()
    )
    # a rename would be caught: a variable equal to an existing channel has novelty 0 by construction of the fit
    import numpy as np

    x = np.random.default_rng(0).random((50, 2))
    A = np.column_stack([x, np.ones(50)])
    beta, *_ = np.linalg.lstsq(A, x[:, 0] * 3 + 1, rcond=None)
    assert np.var(x[:, 0] * 3 + 1 - A @ beta) / np.var(x[:, 0] * 3 + 1) < 1e-9  # novelty of a pure relabelling is 0
