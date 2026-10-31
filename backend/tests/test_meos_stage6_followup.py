"""The sixth-stage follow-up engine features (meos-0.5): coupling.bypass, resource rerouting, a temporary local address. All are opt-in: a run that does not use them is the run of the earlier stages."""

from __future__ import annotations

import pytest

from xzr.meos import engine as E
from xzr.meos import repair6 as R


def _run(cfg: dict, ivs: list[dict], ticks: int) -> E.Run:
    r = E.Run(cfg, ivs)
    for _ in range(ticks):
        r.step()
    return r


def _cfg(seed: int = 1, horizon: int = 200) -> dict:
    return R.config(seed, horizon)


def test_engine_version_and_a_run_without_the_features_is_unchanged():
    assert E.ENGINE_VERSION == "meos-0.5"
    base = [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}]
    a = E.run_record(_cfg(), base)
    b = E.run_record(_cfg(), base + [{"tick": 50, "op": "RECONFIGURE", "path": "coupling.bypass", "value": 0.0}])
    assert a["frames"][-1] == b["frames"][-1]  # a bypass of 0 is no bypass


def test_the_bypass_lets_a2_sense_without_the_coupling():
    cfg = _cfg()
    off = [{"tick": 0, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.0}]
    on = [*off, {"tick": 0, "op": "RECONFIGURE", "path": "coupling.bypass", "value": 1.0}]

    def peak(ivs: list[dict]) -> float:
        r = E.Run(cfg, ivs)
        best = 0.0
        for _ in range(60):
            r.step()
            best = max(best, r.ent["A2"]["s0"])
        return best

    assert peak(off) == 0.0
    assert peak(on) > 0.0


def test_rerouting_moves_resource_and_conserves_the_total():
    cfg = _cfg()
    base = [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}]
    rr = {"from": {"x": 0, "y": 6}, "to": {"x": 3, "y": 6}, "rate": 0.5, "duration": 1}
    a = _run(cfg, base, 10)
    b = _run(cfg, [*base, {"tick": 11, "op": "ALTER_RESOURCE", "reroute": rr}], 10)
    assert b.R[0, 6] == a.R[0, 6]  # nothing moved before the intervention tick
    a = _run(cfg, base, 11)
    b = _run(cfg, [*base, {"tick": 11, "op": "ALTER_RESOURCE", "reroute": rr}], 11)
    d = b.R - a.R
    assert d[0, 6] < 0 < d[3, 6]
    assert abs(float(d.sum())) < 1e-9


def test_a_conduit_ends_after_its_duration():
    cfg = _cfg()
    rr = {"from": {"x": 0, "y": 6}, "to": {"x": 3, "y": 6}, "rate": 0.5, "duration": 3}
    r = _run(cfg, [{"tick": 5, "op": "ALTER_RESOURCE", "reroute": rr}], 20)
    assert r.reroutes == []


def test_a_temporary_local_address_returns_the_prior_state():
    cfg = _cfg()
    ivs = [{"tick": 5, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 0.5}, {"tick": 10, "op": "ADDRESS", "target": "A2", "mode": "temporary", "duration": 8}]
    r = E.Run(cfg, ivs)
    modes = {}
    for _ in range(30):
        r.step()
        modes[r.t] = r.addr["A2"]["mode"]
    assert modes[7] == "partial"
    assert modes[12] is None  # locally addressed
    assert modes[17] is None
    assert modes[19] == "partial"  # the prior state is back
    assert r.addr["A2"]["fraction"] == 0.5


def test_a_later_address_intervention_ends_a_temporary_address():
    cfg = _cfg()
    ivs = [{"tick": 5, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 0.5}, {"tick": 10, "op": "ADDRESS", "target": "A2", "mode": "temporary", "duration": 50}, {"tick": 15, "op": "ADDRESS", "target": "A2", "mode": "restore"}]
    r = _run(cfg, ivs, 40)
    assert r.addr["A2"]["mode"] is None and "temp_until" not in r.addr["A2"] or r.addr["A2"].get("temp_until") is None


def test_validation_of_the_new_interventions():
    assert E.validate_interventions([{"tick": 5, "op": "ADDRESS", "mode": "temporary", "target": "A2", "duration": 10}], 100) == []
    assert E.validate_interventions([{"tick": 5, "op": "ADDRESS", "mode": "temporary", "target": "A2"}], 100)
    assert E.validate_interventions([{"tick": 5, "op": "RECONFIGURE", "path": "coupling.bypass", "value": 1.5}], 100)
    assert E.validate_interventions([{"tick": 5, "op": "RECONFIGURE", "path": "coupling.bypass", "value": 0.5}], 100) == []
    ok = {"from": {"x": 0, "y": 6}, "to": {"x": 3, "y": 6}, "rate": 0.5, "duration": 10}
    assert E.validate_interventions([{"tick": 5, "op": "ALTER_RESOURCE", "reroute": ok}], 100) == []
    assert E.validate_interventions([{"tick": 5, "op": "ALTER_RESOURCE", "reroute": {**ok, "rate": 0}}], 100)
    assert E.validate_interventions([{"tick": 5, "op": "ALTER_RESOURCE", "reroute": {**ok, "to": {"x": 99, "y": 0}}}], 100)


def test_the_fault_modes_are_not_extended():
    assert "temporary" not in E.ADDRESS_MODES and E.ADDRESS_MODES_REPAIR == ("temporary",)


def test_the_followup_actions_are_built_and_the_frozen_registry_is_unchanged():
    st = R.STRESSES["coupling gain 0.5"]
    assert R.ACTIONS["coupling.bypass"].status == "not implemented" and R.ACTIONS["resource.rerouting"].status == "not implemented" and R.ACTIONS["address.temporary_local"].status == "not implemented"
    assert R.build_action("coupling.bypass", st, 0.5, 113) == [{"tick": 113, "op": "RECONFIGURE", "path": "coupling.bypass", "value": 0.5}]
    assert R.build_action("resource.rerouting", st, 0.5, 113, 30)[0]["reroute"]["duration"] == 30
    assert R.build_action("address.temporary_local", R.STRESSES["Address partial 0.5"], 0.0, 113, 30)[0]["mode"] == "temporary"
    with pytest.raises(KeyError):
        R.build_action("coupling.bypass_x", st, 0.5, 113)
