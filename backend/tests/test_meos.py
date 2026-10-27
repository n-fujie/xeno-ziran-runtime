"""MEOS (XENO ECOSYSTEM) — the simulation, its status criteria, the reduction experiments and the API.

These test the model's operational relations, not a rendering: every outcome below is measured by running the engine. The outcomes are properties of
MEOS-0 as parameterised here; the parameters were chosen so that the unperturbed run sustains the recursion, and nothing else about the perturbation
results was assumed. Software checks on a model, not evidence about any physical or biological ecosystem."""

from __future__ import annotations

import base64
import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from xzr.meos import analysis as A
from xzr.meos import engine as E
from xzr.service import app as app_mod
from xzr.service import studies as studies_mod
from xzr.service.limits import LIMITS


def run(ivs=None, **cfg):
    return E.run_record(E.default_config(**cfg), ivs or [])


def status_labels(rec):
    return [s["label"] for s in rec["status_log"]]


@pytest.fixture(scope="module")
def base():
    return run()


# ---------------------------------------------------------------------------------------------------- 1. deterministic replay
def test_meos0_baseline_sustains_the_recursion_and_replays_bit_for_bit(base):
    assert base["final_status"]["label"] == "ACTIVE" and len(base["cycles"]) >= 40
    assert status_labels(base) == ["DEGRADED", "ACTIVE"]  # forming, then sustained
    again = run()
    assert again["result_digest"] == base["result_digest"] and again["initial_config_digest"] == base["initial_config_digest"]
    assert E.replay(base) == {"identical": True, "expected": base["result_digest"], "got": base["result_digest"]}
    assert base["frames"][-1] == again["frames"][-1] and base["fields"]["b64"] == again["fields"]["b64"]


def test_replay_depends_on_seed_configuration_and_interventions_and_detects_a_difference(base):
    assert run(seed=2)["result_digest"] != base["result_digest"]  # the seed is the initial jitter and the sensor noise
    assert run(grid=15)["result_digest"] != base["result_digest"]
    assert (
        run([{"tick": 5, "op": "ALTER_SSS", "size": 1.0}])["result_digest"] != base["result_digest"]
    )  # an intervention is part of the run, even a no-op value
    tampered = dict(base, result_digest="0" * 64)
    assert E.replay(tampered)["identical"] is False


def test_the_record_carries_what_is_needed_to_reconstruct_the_run(base):
    for k in (
        "config",
        "final_config",
        "seed",
        "interventions",
        "intervention_log",
        "events",
        "frames",
        "status_log",
        "termination",
        "fields",
        "engine",
    ):
        assert k in base
    assert base["seed"] == 1 and base["engine"] == E.ENGINE_VERSION and base["termination"]["reason"] == "horizon reached"
    g = base["fields"]["grid"]
    raw = base["fields"]["b64"]
    assert len(base64.b64decode(raw)) == len(base["frames"]) * 3 * g * g  # R, M1, M2 for every tick
    assert any(
        e["kind"] == "fire" and e["actor"] == "A1" and e["checks"] for e in base["events"]
    )  # preconditions are in the record
    assert any(f.get("ad") for f in base["frames"])  # the Address Domain parts that only interventions change


# ---------------------------------------------------------------------------------------------------- the recursion itself
def test_a_cycle_is_a_chain_of_attributed_events_and_history_re_enters(base):
    ev = {e["id"]: e for e in base["events"]}
    cyc = [e for e in base["events"] if e["kind"] == "cycle"]
    assert cyc
    for c in cyc[:10]:
        a1_act, a2_fire, reconf, a1_fire = (ev[c[k]] for k in ("a1_act", "a2_fire", "reconfigure", "a1_fire"))
        assert a1_act["actor"] == "A1" and a1_act["action"] == "consume+deposit"
        assert a2_fire["actor"] == "A2" and a2_fire["source"] == a1_act["id"]  # A2 fired on A1's alteration
        assert reconf["actor"] == "A2" and reconf["action"] == "reconfigure" and reconf["renewed"] > 0
        assert a1_fire["actor"] == "A1" and a1_fire["source"] == reconf["id"]  # A1 fired on A2's reconfiguration
        assert a1_act["tick"] <= a2_fire["tick"] <= reconf["tick"] <= a1_fire["tick"]
    assert sum(1 for c in cyc if c["history_reentry"] > 0) > len(cyc) / 2  # history lowered thresholds in the cycles


def test_a_noise_triggered_firing_is_never_attributed_to_the_other_configuration():
    rec = run([{"tick": 0, "op": "REMOVE", "target": "environmental_persistence"}])
    assert rec["cycles"] == []  # the alteration does not outlive the tick: whatever fires by noise starts no chain
    assert all(e["source"] is None for e in rec["events"] if e["kind"] == "fire" and e["actor"] == "A2")


# ---------------------------------------------------------------------------------------------------- 2. A2 removal
def test_removing_a2_collapses_meos_and_names_the_dependency_while_a1_keeps_firing():
    rec = run([{"tick": 0, "op": "REMOVE", "target": "A2"}])
    assert rec["final_status"]["label"] == "COLLAPSED" and rec["termination"]["collapsed"] and rec["cycles"] == []
    dep = rec["termination"]["failed_dependency"]
    assert dep["entity"] == "A2" and dep["precondition"] == "present" and "absent" in dep["detail"]
    assert any(
        e["kind"] == "fire" and e["actor"] == "A1" for e in rec["events"]
    )  # activity alone is not MEOS: A1 still fires, the status does not follow


def test_removing_a2_in_a_running_ecosystem_degrades_then_collapses_in_order():
    rec = run([{"tick": 100, "op": "REMOVE", "target": "A2"}])
    assert status_labels(rec) == ["DEGRADED", "ACTIVE", "DEGRADED", "COLLAPSED"]
    t = {s["label"]: s["tick"] for s in rec["status_log"]}
    assert 100 < t["COLLAPSED"] <= 100 + 48 + 24 and rec["termination"]["failed_dependency"]["entity"] == "A2"
    assert [i["op"] for i in rec["intervention_log"]] == ["REMOVE"] and rec["intervention_log"][0]["tick"] == 100


# ---------------------------------------------------------------------------------------------------- 3. history removal
def test_history_removal_collapses_the_loop_and_history_is_causal_not_decorative():
    h = A.history_comparison(E.default_config())
    assert h["H+"]["persists"] and h["H+"]["mean_threshold_reduction"] > 0
    for k in ("H- removed", "H- prevented"):
        assert not h[k]["persists"] and h[k]["status"] == "COLLAPSED" and h[k]["mean_threshold_reduction"] == 0.0
        assert h[k]["first_divergence_from_H+"] is not None  # the firing sequences part ways at a stated tick
        assert h[k]["cycles"] < h["H+"]["cycles"]
    assert h["H- removed"]["failed_dependency"]["entity"] == "A2"  # the first dependency that fails is named


def test_prevented_history_is_still_recorded_but_does_not_re_enter():
    rec = run([{"tick": 0, "op": "DISABLE_HISTORY", "mode": "prevented"}])
    assert max(f["A1"]["h"] for f in rec["frames"]) > 0  # the trace exists ...
    assert all(f["A1"]["reentry"] == 0.0 and f["A2"]["reentry"] == 0.0 for f in rec["frames"])  # ... and lowers no threshold


# ---------------------------------------------------------------------------------------------------- 4. resource gradient / renewal removal
def test_resource_gradient_removal_is_measured_not_assumed_and_renewal_removal_collapses():
    flat = run([{"tick": 0, "op": "REMOVE", "target": "resource_gradient"}])
    assert (
        flat["final_status"]["label"] == "ACTIVE"
    )  # in this model A2's reconfiguration, not the gradient, supplies what A1 detects
    no_renewal = run([{"tick": 0, "op": "REMOVE", "target": "resource_renewal"}])
    assert (
        no_renewal["final_status"]["label"] == "COLLAPSED"
        and no_renewal["final_status"]["dependency"]["precondition"] != "present"
    )
    assert no_renewal["frames"][-1]["power"] < 1.0  # the finite reserve is what ran out
    assert (
        run(power={"infinite": True})["frames"][-1]["power"] == 24.0
    )  # the infinite-resource control is explicit and never the default


def test_the_power_reserve_is_finite_by_default_and_the_control_condition_is_explicit():
    cfg = E.default_config()
    assert cfg["power"]["infinite"] is False and cfg["power"]["capacity"] == cfg["power"]["reserve"] == 24.0
    rec = run()
    assert min(f["power"] for f in rec["frames"]) < 24.0  # the reserve is actually drawn on


# ---------------------------------------------------------------------------------------------------- 5. interaction interruption and 10. recovery
def test_interrupting_the_interaction_channel_degrades_then_collapses_and_names_the_channel():
    rec = run([{"tick": 100, "op": "ISOLATE", "target": "interaction_channel"}])
    assert status_labels(rec) == ["DEGRADED", "ACTIVE", "DEGRADED", "COLLAPSED"]
    assert rec["final_status"]["dependency"]["precondition"] == "interaction channel"
    assert "interrupted" in rec["final_status"]["dependency"]["detail"]


def test_a_collapsed_ecosystem_is_not_restored_by_reconnecting_alone_but_refires_after_a_resource_pulse():
    iso = [
        {"tick": 100, "op": "ISOLATE", "target": "interaction_channel"},
        {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"},
    ]
    alone = run(iso, horizon=360)
    assert alone["final_status"]["label"] == "COLLAPSED"  # nothing in the environment re-triggers A1
    pulse = {"tick": 151, "op": "ALTER_RESOURCE", "inject": {"x": 3, "y": 6, "amount": 2.0}}
    healed = run([*iso, pulse], horizon=360)
    assert healed["final_status"]["label"] == "ACTIVE"
    assert status_labels(healed) == [
        "DEGRADED",
        "ACTIVE",
        "DEGRADED",
        "COLLAPSED",
        "DEGRADED",
        "ACTIVE",
    ]  # collapse, refiring, recovery
    assert len(healed["cycles"]) > len(alone["cycles"])
    assert [i["op"] for i in healed["intervention_log"]] == ["ISOLATE", "RECONNECT", "ALTER_RESOURCE"]


def test_recovery_is_not_automatic_and_an_overshooting_pulse_collapses_again():
    iso = [
        {"tick": 100, "op": "ISOLATE", "target": "interaction_channel"},
        {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"},
    ]
    big = run([*iso, {"tick": 151, "op": "ALTER_RESOURCE", "inject": {"x": 3, "y": 6, "amount": 4.0}}], horizon=360)
    assert (
        big["final_status"]["label"] == "COLLAPSED" and "ACTIVE" not in status_labels(big)[4:]
    )  # a larger insertion is not a better one


def test_reconnecting_a2_after_removal_refires_it_briefly_but_does_not_by_itself_sustain():
    rec = run([{"tick": 100, "op": "REMOVE", "target": "A2"}, {"tick": 130, "op": "RECONNECT", "target": "A2"}])
    assert status_labels(rec).count("ACTIVE") == 2  # the cycles resume after the reconnection ...
    assert rec["final_status"]["label"] == "COLLAPSED"  # ... and are not sustained


# ---------------------------------------------------------------------------------------------------- 6. boundary reconfiguration
def test_a_spatial_boundary_that_confines_the_configurations_degrades_the_recursion_and_a_wide_one_does_not():
    tight = run([{"tick": 50, "op": "CHANGE_BOUNDARY", "arena_radius": 2}])
    wide = run([{"tick": 50, "op": "CHANGE_BOUNDARY", "arena_radius": 4}])
    assert tight["final_status"]["label"] == "COLLAPSED" and wide["final_status"]["label"] == "ACTIVE"
    assert tight["intervention_log"][0]["arena_radius"] == 2
    assert all(2 <= f["A1"]["x"] <= 11 for f in tight["frames"][51:])  # the entities were brought inside the new boundary
    assert tight["frames"][60]["ad"]["A1"]["operational_boundary"]["arena_radius"] == 2 if "ad" in tight["frames"][60] else True


def test_the_xenobody_partitions_are_measured_on_the_same_arrangement():
    b = A.boundary_analysis(E.default_config())
    by = {p["id"]: p for p in b["partitions"]}
    assert b["unperturbed"]["persists"]
    assert [by[k]["closure"] for k in ("B1", "B2", "B3")] == [
        pytest.approx(2 / 6, abs=1e-3),
        pytest.approx(3 / 6, abs=1e-3),
        1.0,
    ]  # legs wholly inside the body
    assert not by["B1"]["persists_when_only_the_body_is_retained"] and not by["B2"]["persists_when_only_the_body_is_retained"]
    assert by["B3"]["persists_when_only_the_body_is_retained"]
    assert by["B1"]["failed_dependency"]["entity"] == "A2"  # a body that excludes A2 cannot contain the recursion
    custom = A.boundary_analysis(
        E.default_config(),
        {
            "X": {
                "label": "A1 + A2 without history",
                "components": [c for c in A.PARTITIONS["B3"]["components"] if c != "history"],
            }
        },
    )
    assert custom["partitions"][0]["legs_inside"]["history re-enters the next firing"] is False
    assert (
        custom["partitions"][0]["persists_when_only_the_body_is_retained"] is False
    )  # the history leg is outside this body and the recursion needs it


# ---------------------------------------------------------------------------------------------------- 7. SSS perturbation
def test_sss_changes_the_operating_conditions_not_the_view():
    rows = {(r["axis"], r["value"]): r for r in A.sss_sweep(E.default_config())["rows"]}
    assert rows[("scale", 1.0)]["persists"] and rows[("size", 1.0)]["persists"] and rows[("speed", 1.0)]["persists"]
    for k in (("scale", 2.0), ("size", 2.0), ("size", 0.5), ("speed", 0.5), ("speed", 2.0)):
        assert not rows[k]["persists"], k  # the unperturbed run is not robust to every SSS: a narrow band in this model
    assert rows[("scale", 0.5)]["persists"]  # and not fragile to all of them either
    rec = run([{"tick": 0, "op": "ALTER_SSS", "scale": 2.0, "speed": 1.0, "size": 1.0}])
    ad = rec["frames"][0]["ad"]
    assert ad["A1"]["sss"]["scale"] == 2.0 and ad["A1"]["operational_boundary"]["sensor_radius"] == 4  # the sensing reach doubled
    assert (
        ad["A1"]["operational_boundary"]["sensor_radius"]
        > run()["frames"][0]["ad"]["A1"]["operational_boundary"]["sensor_radius"]
    )
    fast = run([{"tick": 0, "op": "ALTER_SSS", "speed": 2.0}])["frames"][0]["ad"]["A2"]["temporal_window"]
    assert (
        fast["persist"] < E.default_config()["entities"]["A2"]["persist"]
        and fast["window"] < E.default_config()["entities"]["A2"]["window"]
    )  # a faster process clock


def test_an_sss_change_in_a_running_ecosystem_is_logged_and_takes_effect_at_that_tick():
    rec = run([{"tick": 100, "op": "ALTER_SSS", "scale": 2.0}])
    assert rec["intervention_log"][0]["scale"] == 2.0 and rec["intervention_log"][0]["tick"] == 100
    assert rec["final_status"]["label"] == "COLLAPSED" and rec["status_log"][-1]["tick"] > 100
    before = [c for c in rec["cycles"] if c["tick"] < 100]
    assert len(before) == len([c for c in run()["cycles"] if c["tick"] < 100])  # the past is untouched by a later intervention


# ---------------------------------------------------------------------------------------------------- 8. Address Domain perturbation
def test_changing_an_address_domain_parameter_alters_the_simulation():
    rows = {(r["path"], r["value"]): r for r in A.address_sweep(E.default_config())["rows"]}
    assert not rows[("entities.A2.x", 9)]["persists"] and not rows[("entities.A2.sensor_radius", 0)]["persists"]
    assert rows[("entities.A2.x", 4)]["persists"] and rows[("entities.A2.sensor_radius", 3)]["persists"]
    rec = run([{"tick": 0, "op": "RECONFIGURE", "path": "entities.A2.x", "value": 9}])
    assert rec["frames"][0]["A2"]["x"] == 9  # the configuration is where the Address Domain says
    assert rec["final_status"]["label"] == "COLLAPSED" and rec["final_status"]["dependency"]["entity"] == "A2"
    win = run([{"tick": 0, "op": "RECONFIGURE", "path": "entities.A1.window", "value": 2}])
    assert win["final_status"]["label"] == "COLLAPSED"  # the temporal window is part of the operational conditions


def test_the_address_domain_exposes_every_required_part():
    r = E.Run(E.default_config())
    ad = r.address_domain("A1")
    for k in (
        "spatial",
        "operational_boundary",
        "temporal_window",
        "speed",
        "history",
        "connectivity",
        "environment",
        "resource",
    ):
        assert k in ad
    assert ad["spatial"] == {"x": 3, "y": 6} and ad["temporal_window"] == {"window": 6, "persist": 3, "refractory": 2}


# ---------------------------------------------------------------------------------------------------- 9. collapse detection
def test_status_is_derived_from_cycles_with_explicit_criteria_not_from_activity():
    rec = run([{"tick": 0, "op": "REMOVE", "target": "A2"}])
    fires = [e for e in rec["events"] if e["kind"] == "fire"]
    assert fires and rec["frames"][-1]["status"] == "COLLAPSED"
    for f in rec["frames"]:
        n = f["cycles"]
        if f["status"] == "ACTIVE":
            assert n >= 2
        if f["status"] == "COLLAPSED":
            assert n == 0 and f["t"] >= 48
    log = {s["label"]: s for s in rec["status_log"]}
    assert log["COLLAPSED"]["tick"] == 48 and "no complete cycle" in log["COLLAPSED"]["reason"]


def test_every_ablation_names_the_failed_dependency_it_found():
    for comp in E.COMPONENTS:
        rec = run([{"tick": 0, "op": "REMOVE", "target": comp}])
        if rec["final_status"]["label"] == "ACTIVE":
            assert rec["termination"]["failed_dependency"] is None
        else:
            dep = rec["termination"]["failed_dependency"]
            assert dep and dep["detail"] and dep["precondition"], comp


# ---------------------------------------------------------------------------------------------------- the reduction experiment (MFS)
def test_the_minimal_operational_configuration_is_relational_and_one_minimal():
    m = A.minimal_configuration(E.default_config(), horizon=160)
    assert m["baseline_persists"] and m["retained_is_one_minimal"] and m["retained_sustains_operation"]
    assert set(m["retained"]) | set(m["removed"]) == set(E.COMPONENTS) and not set(m["retained"]) & set(m["removed"])
    assert {
        "A2",
        "interaction_channel",
        "feedback",
        "sensor_resource",
        "sensor_alteration",
        "environmental_persistence",
        "resource_renewal",
    } <= set(m["retained"])
    assert all(not v for v in m["leave_one_out_persists"].values())  # removing any retained component ends the operation
    assert m["single_removal_persists"]["resource_gradient"] is True and m["single_removal_persists"]["history"] is False
    assert (
        "graphical" not in json.dumps(m) and m["relative_to"]["scale"] == E.default_config()["sss"]
    )  # relative to an operation, conditions and scale


def test_the_exhaustive_search_finds_every_minimal_set_and_the_greedy_one_is_among_them():
    m = A.minimal_configuration(E.default_config(), exhaustive=True, horizon=130)
    ex = m["exhaustive"]
    assert ex["subsets_evaluated"] == 2 ** len(E.COMPONENTS) and ex["minimal_retained_sets"]
    assert sorted(m["retained"]) in [sorted(s) for s in ex["minimal_retained_sets"]]
    for s in ex["minimal_retained_sets"]:
        assert not any(set(t) < set(s) for t in ex["minimal_retained_sets"])  # none contains another


def test_a_configuration_that_does_not_sustain_the_operation_has_no_minimal_configuration():
    m = A.minimal_configuration(E.default_config(**{"power": {"charge": 0.0, "reserve": 3.0, "capacity": 3.0}}), horizon=120)
    assert m["baseline_persists"] is False and "no reduction is meaningful" in m["note"]


# ---------------------------------------------------------------------------------------------------- observation
def test_observation_is_a_parameter_of_what_is_found(base):
    full = A.observe(base, {"sampling_interval": 1})
    assert full["agrees"] and full["observed_status"] == "ACTIVE" and full["observed_cycles"] == full["true_cycles"]
    sparse = A.observe(base, {"sampling_interval": 4})
    assert sparse["observed_cycles"] < sparse["true_cycles"] and sparse["agrees"] is False and sparse["true_status"] == "ACTIVE"
    region = A.observe(base, {"region": [0, 0, 1, 1]})  # an observational boundary that excludes the habitat's active cells
    assert region["observed_cycles"] == 0


# ---------------------------------------------------------------------------------------------------- validation
def test_invalid_configurations_and_interventions_are_refused_before_running():
    with pytest.raises(E.MeosError, match="grid"):
        E.Run(E.default_config(grid=3))
    bad = [
        {"tick": 5, "op": "EXPLODE"},
        {"tick": 5, "op": "REMOVE", "target": "nothing"},
        {"tick": 999, "op": "REMOVE", "target": "A2"},
        {"tick": 5, "op": "RECONFIGURE", "path": "grid", "value": 3},
        {"tick": 5, "op": "RECONFIGURE", "path": "sss.scale", "value": 99},
        {"tick": 5, "op": "CHANGE_BOUNDARY", "arena_radius": 0},
        {"tick": 5, "op": "ALTER_SSS"},
        {"tick": 5, "op": "ALTER_RESOURCE", "inject": {"x": 3, "y": 6, "amount": 999}},
    ]
    for iv in bad:
        with pytest.raises(E.MeosError):
            E.Run(E.default_config(), [iv])
    with pytest.raises(E.MeosError, match="at most 64"):
        E.Run(E.default_config(), [{"tick": 1, "op": "REMOVE", "target": "A2"}] * 65)


def test_the_entities_are_operational_configurations_not_organisms_subjects_or_minds():
    src = (Path(E.__file__).read_text() + Path(A.__file__).read_text()).lower()
    for word in ("organism", "subject", "mind", "agent"):
        assert word not in src.replace("agents or minds", "").replace("not organisms, subjects", ""), word
    assert set(E.ENTITIES) == {"A1", "A2"}


# ---------------------------------------------------------------------------------------------------- API
@pytest.fixture
def client():
    return TestClient(app_mod.app, headers={"origin": "http://testserver"})


def test_the_api_serves_the_spec_runs_replays_and_stores_nothing(client, tmp_path, monkeypatch):
    monkeypatch.setenv("XZR_STUDY_ROOT", str(tmp_path))
    spec = client.get("/api/meos/spec").json()
    assert (
        spec["components"] == list(E.COMPONENTS)
        and "COLLAPSED" in spec["status_criteria"]
        and spec["defaults"]["power"]["infinite"] is False
    )
    r = client.post(
        "/api/meos/run",
        json={"interventions": [{"tick": 100, "op": "REMOVE", "target": "A2"}], "observation": {"sampling_interval": 2}},
    )
    assert r.status_code == 200
    out = r.json()
    rec = out["record"]
    assert out["summary"]["status"] == "COLLAPSED" and rec["final_status"]["dependency"]["entity"] == "A2" and "observed" in out
    back = client.post(
        "/api/meos/replay", json={"interventions": rec["interventions"], "result_digest": rec["result_digest"]}
    ).json()
    assert back["identical"] is True
    assert client.post("/api/meos/replay", json={"result_digest": "0" * 64}).json()["identical"] is False
    assert list(tmp_path.iterdir()) == []  # a run is computed, never written


def test_the_api_reductions_and_experiments(client):
    abl = client.post("/api/meos/ablation", json={"subsets": [["A2"], ["history"], ["A2", "history"]], "seeds": [1, 2]}).json()
    assert [r["removed"] for r in abl["rows"]] == [[], ["A2"], ["history"], ["A2", "history"]] and abl["rows"][0][
        "persists_in_all_seeds"
    ]
    assert not abl["rows"][1]["persists_in_all_seeds"]
    assert client.post("/api/meos/boundary", json={}).json()["partitions"][2]["persists_when_only_the_body_is_retained"] is True
    assert client.post("/api/meos/history", json={}).json()["H+"]["persists"] is True
    assert len(client.post("/api/meos/sss", json={}).json()["rows"]) == 12
    assert client.post("/api/meos/address", json={}).json()["rows"]
    m = client.post("/api/meos/mfs", json={"horizon": 120}).json()
    assert m["retained_is_one_minimal"] is True


def test_the_api_refuses_bad_input_with_422_and_bounds_the_work(client):
    assert client.post("/api/meos/run", json={"interventions": [{"tick": 1, "op": "NOPE"}]}).status_code == 422
    assert client.post("/api/meos/run", json={"config": {"horizon": 100000}}).status_code == 422
    assert client.post("/api/meos/run", json={"config": "x"}).status_code == 422
    assert client.post("/api/meos/ablation", json={"seeds": list(range(9))}).status_code == 422
    assert client.post("/api/meos/ablation", json={"subsets": [["nope"]]}).status_code == 422
    assert client.post("/api/meos/boundary", json={"partitions": {"X": {"components": ["nope"]}}}).status_code == 422
    assert client.post("/api/meos/replay", json={}).status_code == 422


def test_the_api_is_local_only_and_stateless(client, monkeypatch):
    pub = dataclasses.replace(LIMITS, public=True)
    monkeypatch.setattr(studies_mod, "LIMITS", pub)
    for method, path in (
        ("get", "/api/meos/spec"),
        ("post", "/api/meos/run"),
        ("post", "/api/meos/mfs"),
        ("post", "/api/meos/ablation"),
    ):
        r = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
        assert r.status_code == 403, path
    monkeypatch.setattr(studies_mod, "LIMITS", LIMITS)
    foreign = TestClient(app_mod.app, headers={"origin": "https://elsewhere.example"})
    assert foreign.post("/api/meos/run", json={}).status_code == 403


def test_rendering_cannot_touch_the_simulation_state(base):
    """The frame stream is plain data: decoding or drawing it is a pure function of the record (nothing in the engine reads a camera or a frame rate)."""
    src = Path(E.__file__).read_text()
    for word in ("camera", "fps", "requestanimationframe", "webgl", "three"):
        assert word not in src.lower(), word
    f = np.frombuffer(base64.b64decode(base["fields"]["b64"]), dtype=np.uint8)
    assert f.size and f.max() > 0
