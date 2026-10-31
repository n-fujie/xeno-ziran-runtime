"""TEOO provenance: classes, sealing, digests, derivation, the ledger, the raw store, quarantine. A class is part of the record's digest and is never rewritten."""

from __future__ import annotations

import copy

import pytest

from xzr.teoo import provenance as P
from xzr.teoo import synthetic as SY
from xzr.teoo.ingest import ingest
from xzr.teoo.schema import default_registry

CREATOR = {"name": "tester"}
MEAS_SRC = {"kind": "device", "description": "an IMU", "declared_by": "tester"}
SYN_SRC = {"kind": "generator", "description": "a generator", "declared_by": "tester"}


def _meas(payload=None):
    return P.seal(payload or {"x": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source=MEAS_SRC, created_at="2026-01-01T00:00:00.000000Z")


def _syn(payload=None):
    return P.seal(payload or {"x": 1}, provenance="SYNTHETIC", kind="OBSERVATION", creator=CREATOR, source=SYN_SRC, created_at="2026-01-01T00:00:00.000000Z")


def test_measured_and_synthetic_are_separate_classes_with_separate_digests():
    a, b = _meas(), _syn()
    assert a["provenance"] == "MEASURED" and b["provenance"] == "SYNTHETIC"
    assert a["record_digest"] != b["record_digest"] and a["record_id"] != b["record_id"]  # the same payload, a different class, a different record
    assert P.verify_record(a) == [] and P.verify_record(b) == []


def test_changing_a_synthetic_record_to_measured_fails_verification():
    r = _syn()
    forged = copy.deepcopy(r)
    forged["provenance"] = "MEASURED"
    codes = {i.code for i in P.verify_record(forged)}
    assert "DIGEST_MISMATCH" in codes
    forged["lineage_classes"] = ["MEASURED"]  # a fuller forgery that also fixes the lineage still fails: the digest covers the class
    assert "DIGEST_MISMATCH" in {i.code for i in P.verify_record(forged)}
    ledger = P.Ledger()
    ledger.append(r)
    ledger.entries[0]["record"]["provenance"] = "MEASURED"
    assert {i.code for i in ledger.verify()} & {"DIGEST_MISMATCH", "ENTRY_HASH_MISMATCH"}


def test_changing_the_content_of_a_stored_record_fails_verification():
    r = _meas({"series": [1, 2, 3]})
    r["payload"]["series"][1] = 99
    assert "DIGEST_MISMATCH" in {i.code for i in P.verify_record(r)}
    ledger = P.Ledger()
    ledger.append(_meas({"series": [1, 2, 3]}))
    ledger.entries[0]["record"]["payload"]["series"][1] = 99
    assert ledger.verify()


def test_the_raw_original_is_verified_by_its_digest(tmp_path):
    raw = P.RawStore(tmp_path / "raw")
    data = b"t,knee\n0,1.0\n"
    d = raw.put(data)
    rec = P.seal({"x": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source=MEAS_SRC, raw_bytes=data)
    assert rec["raw"]["digest"] == d == P.sha256(data) and P.verify_record(rec, None, raw) == []
    (tmp_path / "raw" / d).chmod(0o644)
    (tmp_path / "raw" / d).write_bytes(b"t,knee\n0,9.9\n")  # the stored original is altered
    assert "RAW_CORRUPT" in {i.code for i in P.verify_record(rec, None, raw)}
    other = P.RawStore(tmp_path / "empty")
    assert "RAW_MISSING" in {i.code for i in P.verify_record(rec, None, other)}


def test_a_derived_record_keeps_its_parents_and_the_upstream_classes():
    parent = _syn({"series": [1, 2, 3]})
    child = P.derive([parent], payload={"smoothed": [1.5, 2.5]}, provenance="RECONSTRUCTED_ESTIMATE", kind="ESTIMATE", creator=CREATOR, source={"kind": "computation", "description": "smoothing"},
                     transformations=[{"method": "smoothing", "preserves_provenance": False}])
    assert child["derived_from"] == [{"record_id": parent["record_id"], "record_digest": parent["record_digest"]}]
    assert child["lineage_classes"] == ["RECONSTRUCTED_ESTIMATE", "SYNTHETIC"]  # the synthetic ancestry is not dropped
    ledger = P.Ledger()
    ledger.append(parent)
    ledger.append(child)
    assert ledger.verify() == []
    assert parent["record_digest"] == ledger.entries[0]["record"]["record_digest"]  # the parent was not touched by the derivation


def test_a_record_derived_from_synthetic_data_cannot_be_measured():
    parent = _syn()
    with pytest.raises(P.ProvenanceError) as e:
        P.derive([parent], payload={"y": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source=MEAS_SRC, transformations=[{"method": "filtering", "preserves_provenance": True}])
    assert {"CLASS_CHANGE_FORBIDDEN", "TAINTED_LINEAGE"} <= {i.code for i in e.value.issues}
    mixed = P.derive([_meas({"a": 1}), _syn({"b": 2})], payload={"c": 3}, provenance="RECONSTRUCTED_ESTIMATE", kind="ESTIMATE", creator=CREATOR, source={"kind": "computation", "description": "fusion"},
                     transformations=[{"method": "fusion"}])
    assert mixed["lineage_classes"] == ["MEASURED", "RECONSTRUCTED_ESTIMATE", "SYNTHETIC"]


def test_a_measured_record_derived_from_measured_data_needs_an_allowed_processing_step():
    m = _meas()
    ok = P.derive([m], payload={"y": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source=MEAS_SRC, transformations=[{"method": "filtering", "preserves_provenance": True}])
    assert ok["provenance"] == "MEASURED" and ok["lineage_classes"] == ["MEASURED"]
    for bad in ([], [{"method": "modelling", "preserves_provenance": True}], [{"method": "filtering"}]):
        with pytest.raises(P.ProvenanceError):
            P.derive([m], payload={"y": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source=MEAS_SRC, transformations=bad)


def test_an_unknown_provenance_is_never_registered_as_measured():
    for bad in (None, "", "UNKNOWN", "measured", "REAL"):
        with pytest.raises(P.ProvenanceError):
            P.seal({"x": 1}, provenance=bad, kind="OBSERVATION", creator=CREATOR, source=MEAS_SRC)
    with pytest.raises(P.ProvenanceError) as e:  # a MEASURED record must say where it came from and who vouches for it
        P.seal({"x": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source={"description": "something"})
    assert "MEASURED_SOURCE_UNDECLARED" in {i.code for i in e.value.issues}
    q, ledger = P.Quarantine(), P.Ledger()
    manifest = {"schema_version": "teoo.observation/1", "creator": CREATOR, "source": MEAS_SRC, "time_column": "t", "time": {"unit": "s"}, "channels": [{"column": "k", "variable": "joint.angle.knee_l", "unit": "deg"}]}
    res = ingest(b"t,k\n0,1\n1,2\n", media_type="text/csv", registry=default_registry(), manifest=manifest, ledger=ledger, quarantine=q)  # no 'provenance' in the manifest
    assert not res.ok and res.quarantined and "PROVENANCE_UNDECLARED" in {i.code for i in res.errors} and ledger.entries == [] and len(q.items) == 1


def test_kinds_are_a_separate_axis_and_a_measured_reference_state_does_not_exist():
    with pytest.raises(P.ProvenanceError):
        P.seal({"x": 1}, provenance="MEASURED", kind="REFERENCE_STATE", creator=CREATOR, source=MEAS_SRC)
    with pytest.raises(P.ProvenanceError):
        P.seal({"x": 1}, provenance="RECONSTRUCTED_ESTIMATE", kind="OBSERVATION", creator=CREATOR, source={"kind": "computation", "description": "x"})
    obs = P.seal({"x": 1}, provenance="SYNTHETIC", kind="OBSERVATION", creator=CREATOR, source=SYN_SRC)  # an observation taken from a synthetic world is not a real-world measurement
    assert obs["kind"] == "OBSERVATION" and obs["provenance"] != "MEASURED"


def test_the_ledger_is_append_only_with_a_chain_and_a_checkpoint():
    ledger = P.Ledger()
    a, b = _meas({"n": 1}), _meas({"n": 2})
    ledger.append(a)
    cp = ledger.checkpoint()
    ledger.append(b)
    assert ledger.verify() == [] and ledger.verify_checkpoint(cp) == []
    with pytest.raises(P.ProvenanceError):
        ledger.append(a)  # a record is never rewritten
    assert not hasattr(ledger, "update") and not hasattr(ledger, "delete")
    ledger.entries[0]["record"]["payload"]["n"] = 5  # the history is rewritten...
    assert ledger.verify()
    forged = P.Ledger()  # ...and even a ledger rebuilt consistently from scratch differs from the checkpoint taken earlier
    forged.append(_meas({"n": 5}))
    forged.append(b)
    assert forged.verify() == []  # internally consistent...
    assert {i.code for i in forged.verify_checkpoint(cp)} == {"CHECKPOINT_MISMATCH"}  # ...but not the history the checkpoint recorded


def test_the_ledger_persists_to_a_file_and_detects_a_file_edit(tmp_path):
    path = tmp_path / "l.jsonl"
    led = P.Ledger(path)
    led.append(_meas({"n": 1}))
    led.append(_syn({"n": 2}))
    again = P.Ledger(path)
    assert [e["record"]["record_id"] for e in again.entries] == [e["record"]["record_id"] for e in led.entries] and again.verify() == []
    path.write_text(path.read_text().replace('"SYNTHETIC"', '"MEASURED"'))
    assert P.Ledger(path).verify()


def test_the_protections_say_what_is_not_implemented():
    assert "digital signatures (nobody vouches for a record; a digest is not a signature)" in P.PROTECTIONS["not_implemented"]
    assert any("access control" in x for x in P.PROTECTIONS["not_implemented"]) and any("consent" in x for x in P.PROTECTIONS["not_implemented"])
    assert P.PROTECTIONS["implemented"] and "signature" not in " ".join(P.PROTECTIONS["implemented"])


def test_the_synthetic_demo_is_sealed_synthetic_and_verifies():
    d = SY.make_demo()
    rec = d["records"][0]
    assert rec["provenance"] == "SYNTHETIC" and rec["payload"]["banner"].startswith("SYNTHETIC") and d["ledger"].verify() == []
