"""MO / DO / ZCA / MS instances over the body model: the specification is quoted, the addresses are well formed, nothing is fused."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from xzr.xbtro import engine, experiments, observation, ziran

SIBLING = [p for p in (Path("/Users/user/Desktop/BIM/pa-philosophy-in-audit"),) if p.exists()]
SEEDS = [5000 + i for i in range(8)]


@pytest.mark.skipif(not SIBLING, reason="pa-philosophy-in-audit is not available")
def test_the_quoted_definitions_are_the_source_text():
    src = (SIBLING[0] / "data/ziran.ts").read_text()
    for code, spec in ziran.SPEC.items():
        block = src[src.index(f'code: "{code}"') :]
        block = block[: block.index("},")]
        definition = re.search(r'definition:\s*"((?:[^"\\]|\\.)*)"', block, re.S).group(1)
        assert definition.replace('\\"', '"') == spec["definition"], code
        not_this = re.search(r'notThis:\s*"((?:[^"\\]|\\.)*)"', block, re.S).group(1)
        assert not_this.replace('\\"', '"') == spec["not_this"], code


def test_repository_status_is_not_upgraded():
    assert ziran.STATUS["MO"]["repository_status"].startswith("NOT IMPLEMENTED")
    assert ziran.STATUS["MS"]["repository_status"].startswith("NOT IMPLEMENTED")
    assert ziran.STATUS["DO"]["repository_status"] == "PARTIAL" and ziran.STATUS["ZCA"]["repository_status"].startswith("PARTIAL")
    assert "not_covered" in ziran.STATUS["MO"] and "Nothing here is evidence" in ziran.status()["statement"]


def test_address_has_the_specified_shape_and_four_field_states():
    a = ziran.address(
        "xbtro-experiment-record", "r1", time=ziran.known("2026-10-18"), scale=ziran.unknown(), boundary=ziran.not_applicable()
    )
    assert set(a) == {"namespace", "localId", "time", "scale", "boundary", "version", "provenance"}
    assert [a[k]["status"] for k in ("time", "scale", "boundary", "version", "provenance")] == [
        "known",
        "unknown",
        "not-applicable",
        "not-recorded",
        "not-recorded",
    ]
    with pytest.raises(ValueError):
        ziran.validate_address({**a, "time": {"status": "known"}})  # 'known' without a value
    with pytest.raises(ValueError):
        ziran.validate_address({**a, "version": ziran.known([{"kind": "my-version", "value": "1"}])})
    with pytest.raises(ValueError):
        ziran.validate_address(
            {**a, "provenance": ziran.known([{"localId": "x", "relation": "caused-by"}])}
        )  # not a relation of the specification


def test_record_address_reuses_the_record_id_and_references_do_not_embed_payloads():
    rec, _ = experiments.run_to_end("A", {"n_seeds": 4, "rounds": 1})
    a = ziran.address_record(rec)
    assert a["localId"] == rec["id"] and a["time"]["status"] == "not-recorded"
    refs = a["provenance"]["value"]
    assert all(set(r) <= {"namespace", "localId", "relation"} for r in refs)
    assert {r["relation"] for r in refs} <= set(ziran.RELATIONS)
    ziran.validate_address(ziran.address_body_configuration(rec))
    ziran.validate_address(ziran.address_observation_configuration(rec, 0))
    assert not hasattr(ziran, "same_object") and not hasattr(ziran, "equivalent")  # addressability without identity


@pytest.fixture(scope="module")
def pair():
    a = experiments.base_config("human-like-planar")
    b = experiments.alteration(a, "mixed")
    return engine.simulate(a, SEEDS), engine.simulate(b, SEEDS)


def test_distributed_observation_keeps_sources_side_by_side(pair):
    ra, rb = pair
    obs = observation.validate(observation.config("full"))
    do = ziran.distributed_observation(ra, rb, obs)
    assert do["privileged_source"] is None
    assert all(r["fused"] is None for r in do["relations"])
    assert {s["source"] for s in do["sources"]} == {m["id"] for m in obs["models"]}
    multi = [r for r in do["relations"] if len(r["per_source"]) > 1]
    assert multi and all(r["agreement"] in ("agree", "conflict") for r in multi)
    assert all(f["excluded_in_advance"] == [] for f in do["families"].values())
    # a relation without any instrument is listed as such, not dropped
    none = ziran.distributed_observation(ra, rb, observation.validate(observation.config("motion-only")))
    assert any(not r["per_source"] for r in none["relations"])


def test_mo_policy_keeps_reach_as_a_vector_and_retracts(pair):
    ra, rb = pair
    pol = ziran.mo_policy(ra, rb, observation.validate(observation.config("motion-only")), rounds=4, seeds=SEEDS)
    assert isinstance(pol["reach_after"], dict) and "unobserved_regions" in pol["reach_after"]
    assert pol["reach_after"]["unobserved_regions"], "the policy must not claim total reach"
    assert all(g["decision"] == "kept" or g["decision"].startswith("retracted") for g in pol["rounds"])
    for g in pol["rounds"]:
        assert {"setup_s", "added_mass_kg"} <= set(g["cost"]) and "expected" in g and "actual" in g
    kept = [g for g in pol["rounds"] if g["decision"] == "kept"]
    assert all(g["actual"]["gain"] > 0 for g in kept)  # nothing is kept that did not pay


def test_ms_pareto_and_selection_use_stated_constraints_only():
    mk = lambda lat, en, info, reach, lines, rec, fall: {
        "latency_s": lat,
        "energy": en,
        "neg_information_gain": -info,
        "intervention_reach_s": reach,
        "lines_changed": lines,
        "recovery_rmst_s": rec,
        "fall_rate": fall,
    }
    v = [
        mk(1.0, 0.1, 0, 0.1, 0, 1.0, 0.0),
        mk(0.5, 0.1, 0, 0.1, 0, 1.0, 0.0),
        mk(0.5, 0.2, 0, 0.1, 0, 1.0, 0.0),
        mk(None, 0.05, 0, 0.1, 0, 1.0, 0.0),
    ]
    assert ziran.pareto(v) == [
        1,
        3,
    ]  # 0 and 2 are dominated by 1; the stop-like path (no latency, lowest energy) is not dominated
    assert ziran.select(v, {"fall_rate": 0.0}, ["latency_s", "energy"]) == 1
    assert ziran.select(v, {"fall_rate": -1.0}, ["latency_s"]) is None


def test_ms_paths_run_includes_the_stopped_response_and_no_single_score():
    gen = ziran.ms_paths("human-like-planar", "reach-target", SEEDS[:6])
    while True:
        try:
            next(gen)
        except StopIteration as st:
            out = st.value
            break
    assert out["collapsed_score"] is None
    stop = [p for p in out["paths"] if p["is_stop_path"]]
    assert len(stop) == 1 and stop[0]["latency_s"] is None  # switching the cue response off does not reach the target
    assert {"latency_s", "energy", "information_gain", "intervention_reach_s", "lines_changed", "recovery_rmst_s"} <= set(
        out["paths"][0]
    )
