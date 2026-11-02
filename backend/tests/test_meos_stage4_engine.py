"""MEOS-0, fourth stage, engine: the Address Domain `delayed` and `stale` faults and the thresholded M2 tap.

These are optional features: a run that does not use them is bit for bit the run of the earlier stages. The outcomes below are measured by running the engine."""

from __future__ import annotations

import pytest

from xzr.meos import engine as E

BASELINE_RESULT_DIGEST = "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5"


def run(ivs=None, m2=None):
    cfg = E.default_config()
    if m2 is not None:
        cfg["m2"] = dict(cfg.get("m2") or {}, **m2)
    return E.run_record(cfg, ivs or [])


def addr(mode, **kw):
    return {"tick": 40, "op": "ADDRESS", "target": "A1", "mode": mode, **kw}


def test_the_baseline_digest_is_unchanged_by_the_stage_four_engine():
    assert run()["result_digest"] == BASELINE_RESULT_DIGEST


def test_new_modes_are_declared_and_validated():
    assert "delayed" in E.ADDRESS_MODES and "stale" in E.ADDRESS_MODES and "threshold" in E.M2_SENSE
    cfg = E.default_config()
    for bad in (
        addr("delayed"),
        addr("delayed", x=8, y=8),
        addr("delayed", x=8, y=8, delay=0),
        addr("delayed", x=8, y=8, delay=500),
        addr("stale", duration=0),
    ):
        with pytest.raises(E.MeosError):
            E.run_record(cfg, [bad])
    with pytest.raises(E.MeosError):
        run(m2={"sense": "threshold", "threshold": 5})


def test_a_delayed_address_names_the_old_cell_until_the_update_arrives():
    r = run([addr("delayed", x=8, y=8, delay=15)])
    at = {f["t"]: f["address"]["A1"] for f in r["frames"] if f.get("address")}
    assert (
        at[40]["mode"] == "delayed" and at[40]["integrity"] == 0.0 and at[40]["at"] == [3, 6]
    )  # the body moved, the address still names (3, 6)
    updates = [e for e in r["events"] if e["kind"] == "address_update"]
    assert len(updates) == 1 and updates[0]["tick"] == 55 and updates[0]["actor"] == "A1"
    assert r["frames"][60].get("address") is None or r["frames"][60]["address"]["A1"]["mode"] is None
    assert r["intervention_log"][0]["address_mode"] == "delayed" and r["intervention_log"][0]["delay"] == 15


def test_a_stale_address_ends_at_its_duration_or_at_restore():
    timed = run([addr("stale", duration=30)])
    assert [e["tick"] for e in timed["events"] if e["kind"] == "address_update"] == [70]
    open_ended = run([addr("stale")])
    assert not [e for e in open_ended["events"] if e["kind"] == "address_update"]
    restored = run([addr("stale"), {"tick": 90, "op": "ADDRESS", "target": "A1", "mode": "restore"}])
    f = {x["t"]: x for x in restored["frames"]}
    assert "address" not in f[120] or f[120]["address"]["A1"]["mode"] is None


def test_the_new_modes_replay_bit_for_bit():
    for ivs in ([addr("delayed", x=8, y=8, delay=15)], [addr("stale", duration=30)]):
        rec = run(ivs)
        assert E.replay(rec)["identical"]


def test_a_thresholded_tap_passes_only_variation_above_the_threshold():
    none_digest = run()["result_digest"]
    zero = run(m2={"sense": "threshold", "threshold": 0.0})
    direct = run(m2={"sense": "direct"})
    assert zero["result_digest"] == direct["result_digest"]  # a threshold of zero passes everything: the direct tap
    # a threshold above every signal the tap sees passes nothing: the run is the run without M2 (measured, not assumed)
    high = run(m2={"sense": "threshold", "threshold": 0.3})
    assert high["result_digest"] == none_digest
