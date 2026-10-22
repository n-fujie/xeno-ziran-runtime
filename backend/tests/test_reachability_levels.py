"""Levels of reachability (hpo/reachability.py): available, executable, success, reachable, observable, identified, used.
Each required kind of change runs on a real field; an enabled operation is never taken for grown research possibilities."""

from __future__ import annotations

import numpy as np
import pytest

from xzr.hpo import experiments as X
from xzr.hpo import reconfig
from xzr.hpo.field import Field
from xzr.hpo.observe import Veil
from xzr.hpo.reachability import compare_levels, levels
from xzr.hpo.world import build_world


@pytest.fixture(scope="module")
def warm():
    w = build_world(800, 9001, 90001)
    for _ in range(40):
        w.step()
    return w


def field(warm, settings=None, seed=1):
    f = Field(warm.fork(), settings if settings is not None else X.settings_for("D"), seed, keep_states=False)
    f.run(40)
    return f


def apply(f, **ch):
    return reconfig.apply(f, ch, [])


def test_removing_and_restoring_a_channel_contracts_then_expands_what_is_available(warm):
    f = field(warm)
    l0 = levels(f)
    apply(f, path="instruments.withdrawal.channels", value="boundary_flow", op="remove")
    l1 = levels(f)
    c = compare_levels(l0, l1)
    assert (
        c["available"]["lost"]
        and not c["available"]["gained"]
        and c["observable_cells"]["lost"]
        and c["effect"] in ("contracted", "mixed")
    )
    apply(f, path="instruments.withdrawal.channels", value="boundary_flow", op="add")
    c2 = compare_levels(l1, levels(f))
    assert c2["available"]["gained"] and not c2["available"]["lost"] and c2["effect"] == "expanded"


def test_observability_is_lost_behind_a_veil_and_regained_by_penetration_without_changing_availability(warm):
    f = field(warm)
    n = len(f.world.h.labels[0])
    before = levels(f)
    f.instruments.veils.append(Veil("external", np.arange(n), 0.95, -1, "test"))
    veiled = levels(f)
    assert veiled["n_observable_cells"] < before["n_observable_cells"]
    assert veiled["available"] == before["available"]  # the instruments still carry the channels: available is not observable
    for kind in ("withdrawal", "transduction", "concrescence", "picturing", "assemblage", "closure"):
        apply(f, path=f"instruments.{kind}.penetration", value=1.0)
    regained = levels(f)
    assert (
        regained["n_observable_cells"] > veiled["n_observable_cells"]
        and compare_levels(veiled, regained)["observable_cells"]["gained"]
    )


def test_resource_exhaustion_makes_operations_inexecutable_while_they_stay_available(warm):
    f = field(warm, {**X.settings_for("D"), "resources": {"pool_per_step": 0.0}})
    lv = levels(f)
    assert lv["available"] and lv["executable"] == []  # available ≠ executable
    assert f.stats["evaluations"]["FIRED"] == 0 and f.stats["evaluations"]["UNOBSERVABLE"] > 0
    rich = levels(field(warm))
    assert rich["executable"], "with resources the same operations execute"


def test_a_scale_change_that_the_operation_needs_blocks_it_and_the_next_evaluation_shows_it(warm):
    f = field(warm)
    before = levels(f)
    tr = [o for o in before["executable"] if o.startswith("TR")]
    if not tr:
        pytest.skip("no executable transduction operation on this seed")  # a property of the seed, not of the check
    apply(f, path="instruments.transduction.level", value=0)
    static = compare_levels(before, levels(f))
    assert set(tr) <= set(static["available"]["lost"])  # blocked at once (static)...
    f.run(20)
    dyn = compare_levels(before, levels(f))
    assert set(tr) <= set(dyn["executable"]["lost"])  # ...and inexecutable after the next evaluation (dynamic)


def test_a_boundary_change_branches_the_later_history(warm):
    a = Field(warm.fork(), X.settings_for("D"), 3, keep_states=False)
    b = Field(warm.fork(), {**X.settings_for("D"), "boundary": {"veil_scale": 1.0, "gate_scale": 1.8}}, 3, keep_states=False)
    first = None
    for t in range(120):
        a.step()
        b.step()
        if first is None and a.world.engine.fingerprint() != b.world.engine.fingerprint():
            first = t
    assert first is not None and first > 0  # the two histories separate after the change takes effect, not at once
    assert a.world.total_ignitions != b.world.total_ignitions


def test_history_reinsertion_changes_what_the_operations_request_afterwards(warm):
    on = Field(warm.fork(), X.settings_for("D"), 5, keep_states=False)
    off = Field(warm.fork(), X.settings_for("C"), 5, keep_states=False)
    on.run(200)
    off.run(200)
    reins = [e for e in on.history.events if e["type"] == "reinsert"]
    assert reins and not [e for e in off.history.events if e["type"] == "reinsert"]
    req = lambda f: sorted(
        (e["source"], tuple(e.get("detail", {}).get("requests", []))) for e in f.history.events if e["type"] == "act"
    )  # noqa: E731
    assert req(on) != req(off)  # a different later selection of acts (not a presumed better one)


def test_an_invalid_revision_is_refused_recorded_and_changes_nothing(warm):
    f = field(warm)
    before = levels(f)
    with pytest.raises(reconfig.SandboxError):
        apply(f, path="instruments.closure.level", value=9)
    assert compare_levels(before, levels(f))["effect"] == "equivalent"
    ctl = reconfig.Controller("recursive", 1, authority=["allocation.*"], trace_reachability=True)
    ctl.start(f)
    f.run(reconfig.EPOCH)
    ctl.end_epoch(f, 0)
    assert all(r["path"].startswith("allocation.") for r in ctl.trace)


def test_a_change_to_the_value_already_in_force_is_equivalent(warm):
    f = field(warm)
    cur = f.s["instruments"].get("closure", {}).get("level", 1)
    before = levels(f)
    apply(f, path="instruments.closure.level", value=cur)
    assert compare_levels(before, levels(f))["effect"] == "equivalent"


def test_controller_records_levels_before_after_and_the_next_epoch_with_what_was_realised(warm):
    f = Field(warm.fork(), X.settings_for("D"), 7, keep_states=False)
    ctl = reconfig.Controller("recursive", 7, trace_reachability=True)
    ctl.start(f)
    for ep in range(3):
        f.run(reconfig.EPOCH)
        if ep < 2:
            ctl.end_epoch(f, ep)
    ctl.finalize(f, 2)
    assert ctl.trace
    for r in ctl.trace:
        lv = r["levels"]
        assert (
            {"before", "after", "static", "next", "dynamic"} <= set(lv) and "success" in r["realised"] and "used" in r["realised"]
        )
        assert lv["static"]["effect"] in ("expanded", "contracted", "mixed", "equivalent")
        # opened is not success, success is not use: the three are separate numbers
        assert sum(r["realised"]["used"].values()) <= sum(r["realised"]["success"].values())
