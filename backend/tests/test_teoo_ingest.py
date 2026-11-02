"""TEOO ingestion: CSV and JSON into sealed records; errors are returned and never repaired; raw bytes are kept; missing is never 0."""

from __future__ import annotations

import json

from xzr.teoo import provenance as P
from xzr.teoo.body import human_simplified_skeleton
from xzr.teoo.ingest import ingest
from xzr.teoo.schema import Variable, default_registry

BODY = human_simplified_skeleton(at="2026-01-01T00:00:00.000000Z")


def manifest(**over):
    m = {"schema_version": "teoo.observation/1", "provenance": "MEASURED", "creator": {"name": "lab"}, "source": {"kind": "device", "description": "IMU", "declared_by": "lab"},
         "body": {"id": BODY.id, "version": 1}, "time_column": "t", "time": {"unit": "s", "device_clock": "imu-1", "sampling_period_s": 0.02},
         "channels": [{"column": "knee", "variable": "joint.angle.knee_l", "unit": "deg", "target": "tgt.knee_l"}]}
    m.update(over)
    return m


CSV = b"t,knee\n0.00,10.5\n0.02,11.2\n0.04,12.0\n"


def run(raw=CSV, mt="text/csv", **kw):
    kw.setdefault("manifest", manifest())
    return ingest(raw, media_type=mt, registry=default_registry(), body=BODY, created_at="2026-01-01T00:00:00.000000Z", **kw)


def test_a_csv_with_a_declared_provenance_becomes_a_sealed_measured_record():
    res = run()
    assert res.ok and res.record and res.record["provenance"] == "MEASURED" and res.record["kind"] == "OBSERVATION"
    ch = res.record["payload"]["channels"][0]
    assert ch["times"] == [0.0, 0.02, 0.04] and [s["value"] for s in ch["samples"]] == [10.5, 11.2, 12.0] and {s["status"] for s in ch["samples"]} == {"MEASURED_VALID"}
    assert res.record["raw"]["digest"] == P.sha256(CSV) and res.record["raw"]["origin"] == "supplied" and P.verify_record(res.record) == []


def test_a_json_document_is_ingested_by_the_same_rules():
    doc = {"manifest": manifest(), "rows": [{"t": 0.0, "knee": 10.5}, {"t": 0.02, "knee": None}, {"t": 0.04, "knee": 12.0}]}
    res = run(json.dumps(doc).encode(), "application/json", manifest=None)
    assert res.ok
    st = [s["status"] for s in res.record["payload"]["channels"][0]["samples"]]
    assert st == ["MEASURED_VALID", "MISSING", "MEASURED_VALID"] and res.record["payload"]["channels"][0]["samples"][1]["value"] is None
    assert any(w.code == "MISSING_VALUES" for w in res.warnings)  # reported, not hidden


def test_blank_and_invalid_cells_are_missing_or_invalid_never_zero_and_the_raw_text_is_kept():
    res = run(b"t,knee\n0,1\n1,\n2,NA\n3,abc\n4,500\n")
    assert res.ok
    s = res.record["payload"]["channels"][0]["samples"]
    assert [x["status"] for x in s] == ["MEASURED_VALID", "MISSING", "MISSING", "INVALID", "MEASURED_VALID"] and [x["value"] for x in s] == [1.0, None, None, None, 500.0]
    assert s[3]["detail"]["raw_text"] == "abc" and not s[3]["cause_known"] and not s[1]["cause_known"]  # no reason is attached to an unexplained gap
    reg = default_registry()
    reg.register(Variable("t.limited", "kinematics", "an angle with a valid interval", "deg", valid_interval=(-180.0, 180.0)))
    m = manifest(channels=[{"column": "knee", "variable": "t.limited", "unit": "deg", "target": "tgt.knee_l"}])
    r2 = ingest(b"t,knee\n0,10\n1,999\n", media_type="text/csv", registry=reg, body=BODY, manifest=m)
    assert r2.ok and [x["status"] for x in r2.record["payload"]["channels"][0]["samples"]] == ["MEASURED_VALID", "INVALID"]  # outside the valid interval: INVALID, value not kept


def test_errors_are_returned_with_field_code_and_fixability_and_nothing_is_repaired():
    cases = {
        "UNIT_MISMATCH": dict(manifest=manifest(channels=[{"column": "knee", "variable": "joint.angle.knee_l", "unit": "rad", "target": "tgt.knee_l"}])),
        "VARIABLE_UNREGISTERED": dict(manifest=manifest(channels=[{"column": "knee", "variable": "no.such.var", "unit": "deg", "target": "tgt.knee_l"}])),
        "TARGET_UNKNOWN": dict(manifest=manifest(channels=[{"column": "knee", "variable": "joint.angle.knee_l", "unit": "deg", "target": "tgt.nowhere"}])),
        "SCHEMA_UNKNOWN": dict(manifest=manifest(schema_version="teoo.observation/9")),
        "BODY_VERSION_UNKNOWN": dict(manifest=manifest(body={"id": BODY.id, "version": 7})),
        "TIME_UNIT": dict(manifest=manifest(time={"unit": "ms"})),
        "RAW_DIGEST_MISMATCH": dict(manifest=manifest(expected_raw_digest="0" * 64)),
        "COLUMN_MISSING": dict(manifest=manifest(channels=[{"column": "elbow", "variable": "joint.angle.knee_l", "unit": "deg", "target": "tgt.knee_l"}])),
    }
    for code, kw in cases.items():
        q = P.Quarantine()
        res = run(quarantine=q, **kw)
        assert not res.ok and res.record is None and code in {i.code for i in res.errors}, code
        assert res.quarantined and q.items[0]["raw_digest"] == P.sha256(CSV)  # the original is kept with the reasons, outside the ledger
        issue = next(i for i in res.errors if i.code == code)
        assert issue.field and issue.message and isinstance(issue.fixable, bool)
    unit = run(**cases["UNIT_MISMATCH"])
    assert "no conversion" in next(i for i in unit.errors if i.code == "UNIT_MISMATCH").message  # TEOO does not convert a unit silently


def test_time_problems_are_errors_duplicates_and_disorder_are_not_silently_fixed():
    dup = run(b"t,knee\n0,1\n0,2\n")
    assert not dup.ok and "DUPLICATE_TIME" in {i.code for i in dup.errors}
    back = run(b"t,knee\n0,1\n2,2\n1,3\n")
    assert not back.ok and "TIME_NOT_MONOTONIC" in {i.code for i in back.errors} and next(i for i in back.errors if i.code == "TIME_NOT_MONOTONIC").fixable
    bad = run(b"t,knee\n0,1\nlater,2\n")
    assert not bad.ok and "TIME_INVALID" in {i.code for i in bad.errors}
    same = run(b"t,knee\n0,1\n1,2\n1,2\n")
    assert {"DUPLICATE_TIME", "DUPLICATE_ROW"} <= {i.code for i in same.errors}


def test_an_explicit_status_column_is_kept_with_its_cause_and_no_value():
    m = manifest(channels=[{"column": "knee", "status_column": "knee_status", "variable": "joint.angle.knee_l", "unit": "deg", "target": "tgt.knee_l"}])
    res = run(b"t,knee,knee_status\n0,1.0,\n1,,BOUNDARY_INVISIBLE\n2,,UNKNOWN_CAUSE\n", manifest=m)
    s = res.record["payload"]["channels"][0]["samples"]
    assert [x["status"] for x in s] == ["MEASURED_VALID", "BOUNDARY_INVISIBLE", "UNKNOWN_CAUSE"] and s[1]["causes"] == ["BOUNDARY_INVISIBLE"] and s[2]["causes"] == [] and s[2]["cause_known"] is False
    bad = run(b"t,knee,knee_status\n0,1.0,SOMETHING\n", manifest=m)
    assert not bad.ok and "STATUS_UNKNOWN" in {i.code for i in bad.errors}


def test_an_accepted_ingestion_is_in_the_ledger_with_its_raw_original(tmp_path):
    ledger, raw = P.Ledger(tmp_path / "l.jsonl"), P.RawStore(tmp_path / "raw")
    res = run(ledger=ledger, raw_store=raw)
    assert res.ok and len(ledger.entries) == 1 and raw.get(res.record["raw"]["digest"]) == CSV and ledger.verify(raw) == []
    again = run(ledger=ledger, raw_store=raw)  # the same document cannot be registered twice as a rewrite
    assert not again.ok and "ALREADY_RECORDED" in {i.code for i in again.errors}
    assert len(ledger.entries) == 1


def test_unsupported_and_unparseable_input_is_refused_without_a_guess():
    assert "MEDIA_TYPE_UNSUPPORTED" in {i.code for i in run(b"x", "application/pdf").errors}
    assert "UNPARSEABLE" in {i.code for i in run(b"{not json", "application/json", manifest=None).errors}
    assert "MANIFEST_MISSING" in {i.code for i in run(CSV, manifest=None).errors}


def test_a_synthetic_declaration_stays_synthetic_through_ingestion():
    m = manifest(provenance="SYNTHETIC", source={"kind": "generator", "description": "g", "declared_by": "lab"})
    res = run(manifest=m)
    assert res.ok and res.record["provenance"] == "SYNTHETIC" and res.record["lineage_classes"] == ["SYNTHETIC"]
