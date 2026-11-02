"""TEOO API: local only, nothing stored, the synthetic banner is always there, verification endpoints, protections stated; data and rendering reference the same records."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from xzr.service import app as app_mod

client = TestClient(app_mod.app)

MANIFEST = {"schema_version": "teoo.observation/1", "provenance": "MEASURED", "creator": {"name": "lab"}, "source": {"kind": "device", "description": "IMU", "declared_by": "lab"},
            "body": {"id": "body.human-simplified-skeleton", "version": 1}, "time_column": "t", "time": {"unit": "s", "device_clock": "imu"},
            "channels": [{"column": "knee", "variable": "joint.angle.knee_l", "unit": "deg", "target": "tgt.knee_l"}]}


def test_the_demo_is_synthetic_with_a_banner_and_a_verified_ledger():
    r = client.get("/api/teoo/demo").json()
    assert r["synthetic"] is True and r["banner"].startswith("SYNTHETIC") and r["records"][0]["provenance"] == "SYNTHETIC" and r["ledger"]["issues"] == []
    assert r["evidence"][0]["is_evidence"] is False and r["info"]["stored_on_server"] is False
    assert client.get("/api/teoo/demo", params={"seed": 8}).json()["records"][0]["record_id"] != r["records"][0]["record_id"]  # a different seed is a different record
    assert client.get("/api/teoo/demo", params={"seed": 7}).json()["records"][0]["record_id"] == r["records"][0]["record_id"]  # deterministic
    assert client.get("/api/teoo/demo", params={"seed": 99999}).status_code == 422


def test_the_views_data_and_the_records_it_cites_are_the_same_data():
    r = client.get("/api/teoo/demo").json()
    ids = {x["record_id"] for x in r["records"]}
    comps = {c["id"] for c in r["body"]["versions"][-1]["components"]} | {c["id"] for c in r["body"]["versions"][-1]["relations"]}
    for t in r["coverage"]["targets"].values():
        assert set(t["records"]) <= ids and t["ref"] in comps  # a drawn region cites a record that exists and a part that exists
    assert set(r["coverage"]["by_ref"]) <= comps and r["coverage"]["body"] == r["body"]["id"]
    chans = {c["target"] for rec in r["records"] for c in rec["payload"]["channels"]}
    assert chans <= set(r["coverage"]["targets"])


def test_the_demo_covers_every_observation_limit_and_unmeasured_targets():
    r = client.get("/api/teoo/demo").json()
    seen = {s["status"] for rec in r["records"] for c in rec["payload"]["channels"] for s in c["samples"]}
    assert {"MEASURED_VALID", "MISSING", "BOUNDARY_INVISIBLE", "TIME_WINDOW_MISMATCH", "INSTRUMENT_MISMATCH", "SIGNAL_BELOW_THRESHOLD"} <= seen
    cov = r["coverage"]["targets"]
    assert cov["tgt.thigh_l"]["display_class"] == "unmeasured" and cov["tgt.thigh_l"]["state"] == "UNMEASURED" and "not the same as being absent" in cov["tgt.thigh_l"]["note"]
    assert cov["tgt.knee_l"]["display_class"] == "synthetic" and cov["tgt.elbow_r"]["display_class"] == "limited" and r["coverage"]["summary"]["measured"] == 0  # nothing here was measured


def test_ingest_returns_the_sealed_record_and_stores_nothing():
    body = {"media_type": "text/csv", "text": "t,knee\n0,1.5\n0.02,2.5\n", "manifest": MANIFEST}
    r = client.post("/api/teoo/ingest", json=body).json()
    assert r["ok"] and r["stored"] is False and r["record"]["provenance"] == "MEASURED" and r["evidence"]["label"] == "recorded observation" and r["evidence"]["is_evidence"] is False
    assert "access control" in " ".join(r["protections"]["not_implemented"]) and "consent" in " ".join(r["protections"]["not_implemented"])  # what is not implemented is stated with the result


def test_ingest_without_a_declared_provenance_is_refused_with_the_reason():
    m = dict(MANIFEST)
    m.pop("provenance")
    r = client.post("/api/teoo/ingest", json={"media_type": "text/csv", "text": "t,knee\n0,1\n", "manifest": m}).json()
    assert not r["ok"] and r["record"] is None and r["quarantined"] and "PROVENANCE_UNDECLARED" in {i["code"] for i in r["issues"]}


def test_verify_detects_a_changed_class_and_a_missing_parent():
    d = client.get("/api/teoo/demo").json()
    rec = d["records"][0]
    assert client.post("/api/teoo/verify", json={"records": [rec]}).json()["ok"] is True
    forged = json.loads(json.dumps(rec))
    forged["provenance"] = "MEASURED"
    res = client.post("/api/teoo/verify", json={"records": [forged]}).json()
    assert not res["ok"] and "DIGEST_MISMATCH" in {i["code"] for i in res["results"][0]["issues"]}
    child = client.post("/api/teoo/verify", json={"records": [{**rec, "derived_from": [{"record_id": "rec-x", "record_digest": "0"}]}]}).json()
    assert not child["ok"]
    assert client.post("/api/teoo/verify", json={"records": "no"}).status_code == 422


def test_presets_are_served_and_unknown_ones_are_not():
    for name in ("human-simplified-skeleton", "distributed-array", "articulated-artificial", "radial-non-human"):
        r = client.get(f"/api/teoo/body/{name}").json()
        assert r["issues"] == [] and r["concept_only"] is True
    assert client.get("/api/teoo/body/nope").status_code == 404


def test_the_routes_are_local_only_and_refused_on_a_public_deployment(monkeypatch):
    import dataclasses

    from xzr.service import studies
    from xzr.service.limits import LIMITS

    routes = (("get", "/api/teoo/info", {}), ("get", "/api/teoo/demo", {}), ("get", "/api/teoo/body/human-simplified-skeleton", {}), ("post", "/api/teoo/ingest", {"json": {"text": "", "media_type": "text/csv"}}),
              ("post", "/api/teoo/verify", {"json": {"records": []}}), ("post", "/api/teoo/coverage", {"json": {"records": []}}))
    assert all(getattr(client, m)(p, **kw).status_code == 200 for m, p, kw in routes if p != "/api/teoo/ingest")
    monkeypatch.setattr(studies, "LIMITS", dataclasses.replace(LIMITS, public=True))
    for m, p, kw in routes:
        assert getattr(client, m)(p, **kw).status_code == 403, p  # body observation data pass through these routes: not on a public deployment
    monkeypatch.setattr(studies, "LIMITS", LIMITS)
    foreign = TestClient(app_mod.app, headers={"origin": "https://elsewhere.example"})
    assert foreign.post("/api/teoo/verify", json={"records": []}).status_code == 403 and foreign.get("/api/teoo/demo").status_code == 403
    text = Path(app_mod.__file__).with_name("teoo.py").read_text()
    assert text.count("local_only(request)") >= len([1 for r in app_mod.app.routes if "/api/teoo" in getattr(r, "path", "")])


def test_info_states_the_limits_the_retained_results_and_the_xeno14_source():
    i = client.get("/api/teoo/info").json()
    assert i["stored_on_server"] is False and i["xeno14"]["ids"][0] == "lower-abdominal-continuity" and len(i["xeno14"]["ids"]) == 14
    assert {r["id"] for r in i["retained_results"]} == {"X14-1", "X14-1b", "BS-1"} and len(i["domains"]) == 16 and "not_implemented" in i["protections"]
    assert any("not a photograph" in x for x in i["limits"])
