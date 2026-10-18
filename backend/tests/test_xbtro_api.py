"""The XB-TRO HTTP API: workspaces, experiments as jobs, records (JSON/CSV), repeat / re-observe / re-enter, live bodies, ownership."""

from __future__ import annotations

import csv
import io
import json
import time

import pytest
from fastapi.testclient import TestClient

from xzr.service.app import app

BASE = "/api/xbtro"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def ws(client):
    r = client.post(f"{BASE}/workspaces")
    assert r.status_code == 200
    return r.json()["id"]


def wait(client, ws, jid, timeout=240):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"{BASE}/workspaces/{ws}/jobs/{jid}").json()
        if j["status"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def run(client, ws, exp, params):
    r = client.post(f"{BASE}/workspaces/{ws}/experiments", json={"experiment": exp, "params": params})
    assert r.status_code == 200, r.text
    j = wait(client, ws, r.json()["job"]["id"])
    assert j["status"] == "done", j
    return j


def test_catalog_states_scope_and_ziran_status(client):
    c = client.get(f"{BASE}/catalog").json()
    assert {e["id"] for e in c["experiments"]} >= {"A", "B", "C", "D", "E", "F"}
    assert len(c["xeno14"]) == 14 and {p["id"] for p in c["presets"]} == {"human-like-planar", "machine-like-planar"}
    assert "not a measurement" in c["scope"].lower() or "not a measurement of" in c["scope"].lower()
    assert c["ziran"]["status"]["MO"]["repository_status"].startswith("NOT IMPLEMENTED")
    assert set(c["interventions"]) == {
        "sensory_delay",
        "visual_block",
        "contact_change",
        "posture_change",
        "neural_delay",
        "perturbation",
        "resource_constraint",
    }


def test_experiment_job_record_exports_and_rerun(client, ws):
    j = run(client, ws, "B", {"n_seeds": 4})
    rid = j["record_id"]
    hist = client.get(f"{BASE}/workspaces/{ws}/history").json()
    assert [r["id"] for r in hist["records"]] == [rid]
    rec = client.get(f"{BASE}/workspaces/{ws}/records/{rid}").json()
    assert rec["experiment"] == "B" and rec["results"]["tables"]
    js = client.get(f"{BASE}/workspaces/{ws}/records/{rid}?format=json")
    assert js.headers["content-disposition"].endswith(f'{rid}.json"') and json.loads(js.text)["digest"] == rec["digest"]
    cs = client.get(f"{BASE}/workspaces/{ws}/records/{rid}?format=csv")
    assert cs.headers["content-type"].startswith("text/csv")
    assert any(row and row[0].startswith("# table:") for row in csv.reader(io.StringIO(cs.text)))
    j2 = client.post(f"{BASE}/workspaces/{ws}/records/{rid}/rerun").json()["job"]
    done = wait(client, ws, j2["id"])
    assert done["status"] == "done" and done["summary"]["digest"] == rec["digest"][:12]
    rec2 = client.get(f"{BASE}/workspaces/{ws}/records/{done['record_id']}").json()
    assert rec2["history"]["parent"] == rid and rec2["history"]["operation"] == "rerun"


def test_reanalyse_and_reenter(client, ws):
    a = run(client, ws, "A", {"n_seeds": 4, "rounds": 1})["record_id"]
    r = client.post(f"{BASE}/workspaces/{ws}/records/{a}/reanalyse", json={"observation": {"name": "full"}}).json()["job"]
    done = wait(client, ws, r["id"])
    rec = client.get(f"{BASE}/workspaces/{ws}/records/{done['record_id']}").json()
    assert rec["results"]["re_observation_of_a_simulation"] and rec["history"]["parent"] == a
    e = client.post(f"{BASE}/workspaces/{ws}/records/{a}/reenter", json={"experiment": "B", "params": {"n_seeds": 4}}).json()[
        "job"
    ]
    d2 = wait(client, ws, e["id"])
    rec2 = client.get(f"{BASE}/workspaces/{ws}/records/{d2['record_id']}").json()
    assert rec2["history"]["operation"] == "reenter" and rec2["parameters"]["carry_over"]
    bad = client.post(f"{BASE}/workspaces/{ws}/records/{d2['record_id']}/reanalyse", json={})
    assert bad.status_code == 422


def test_import_roundtrip_and_tamper_refused(client, ws):
    hist = client.get(f"{BASE}/workspaces/{ws}/history").json()["records"]
    rid = hist[0]["id"]
    rec = client.get(f"{BASE}/workspaces/{ws}/records/{rid}").json()
    w2 = client.post(f"{BASE}/workspaces").json()["id"]
    assert client.post(f"{BASE}/workspaces/{w2}/records", json=rec).status_code == 200
    rec["results"]["tables"][0]["rows"][0][2] = 999
    assert client.post(f"{BASE}/workspaces/{w2}/records", json=rec).status_code == 422


def test_bad_inputs_are_refused_with_the_reason(client, ws):
    for exp, params, text in (
        ("B", {"n_seeds": 3}, "n_seeds"),
        ("B", {"n_seeds": 999}, "n_seeds"),
        ("B", {"bogus": 1}, "unknown parameter"),
        ("C", {"principles": ["nope"]}, "principles"),
        ("B", {"carry_over": {"x": [1]}}, "carry_over"),
        ("Z", {}, "not available"),
    ):
        r = client.post(f"{BASE}/workspaces/{ws}/experiments", json={"experiment": exp, "params": params})
        assert r.status_code in (404, 422), (exp, params, r.text)
        assert text in json.dumps(r.json()), r.text


def test_ownership_other_clients_see_nothing(client, ws):
    other = TestClient(app)
    assert other.get(f"{BASE}/workspaces/{ws}/history").status_code == 404
    assert other.post(f"{BASE}/workspaces/{ws}/experiments", json={"experiment": "B"}).status_code == 404


def test_diagnose_reports_unstable_configurations(client):
    ok = client.post(f"{BASE}/diagnose", json={"preset": "machine-like-planar"}).json()
    assert ok["integrator_stable"] and ok["probe"]["diverged_fraction"] == 0
    bad = client.post(f"{BASE}/diagnose", json={"preset": "human-like-planar", "overrides": {"task": {"substeps": 1}}}).json()
    assert bad["integrator_stable"] is False and "unstable" in bad["verdict"]
    assert client.post(f"{BASE}/diagnose", json={"preset": "human-like-planar", "overrides": {"joints": []}}).status_code == 422


def test_live_body_three_kinds_of_values_and_commands(client, ws):
    b = client.post(f"{BASE}/workspaces/{ws}/bodies", json={"preset": "human-like-planar", "n_seeds": 1, "horizon_s": 8}).json()
    bid = b["id"]
    assert set(b["labels"]) == {"reference", "observation", "estimates"} and b["numeric_stability"]["stable"]
    out = client.post(f"{BASE}/workspaces/{ws}/bodies/{bid}/step", json={"n": 20}).json()
    f = out["frames"][-1]
    assert {"reference", "estimates"} <= set(f) and "observation" not in f["reference"]
    assert out["observation"] and all(v["label"] == "observation" for v in out["observation"].values())
    pre = client.post(f"{BASE}/workspaces/{ws}/bodies/{bid}/step", json={"n": 10}).json()
    cmd = client.post(
        f"{BASE}/workspaces/{ws}/bodies/{bid}/command", json={"type": "intervention", "id": "perturbation", "magnitude": 50}
    ).json()
    assert cmd["applied"] == "perturbation"
    post = client.post(f"{BASE}/workspaces/{ws}/bodies/{bid}/step", json={"n": 30}).json()
    assert max(fr["reference"]["push_force"][0] for fr in post["frames"]) > 0 and pre["t1"] < post["t1"]
    r = client.post(f"{BASE}/workspaces/{ws}/bodies/{bid}/command", json={"type": "observation", "observation": {"name": "full"}})
    assert r.status_code == 200 and "eeg" in r.json()["models"]
    ins = client.get(f"{BASE}/workspaces/{ws}/bodies/{bid}/inspect", params={"part": "joint:ankle", "seconds": 2}).json()
    assert ins["observation"]["covered"] and ins["lines"] and ins["kind"].startswith("reference")
    assert (
        client.post(
            f"{BASE}/workspaces/{ws}/bodies/{bid}/command", json={"type": "intervention", "id": "sensory_delay", "magnitude": 9}
        ).status_code
        == 422
    )
    assert client.post(f"{BASE}/workspaces/{ws}/bodies/{bid}/step", json={"n": 9999}).status_code == 422
    saved = client.post(f"{BASE}/workspaces/{ws}/bodies/{bid}/save").json()["record"]
    assert saved["experiment"] == "L"
    assert client.delete(f"{BASE}/workspaces/{ws}/bodies/{bid}").status_code == 200
    assert client.get(f"{BASE}/workspaces/{ws}/bodies/{bid}").status_code == 404


def test_a_numerically_unstable_live_edit_is_refused_and_leaves_the_body_unchanged(client, ws):
    b = client.post(f"{BASE}/workspaces/{ws}/bodies", json={"preset": "human-like-planar", "horizon_s": 3}).json()
    bad = client.post(f"{BASE}/workspaces", json=None)
    assert bad.status_code == 200
    r = client.post(
        f"{BASE}/workspaces/{ws}/bodies", json={"preset": "human-like-planar", "overrides": {"task": {"substeps": 1}}}
    )
    assert r.status_code == 422 and "unstable" in json.dumps(r.json())
    assert client.post(f"{BASE}/workspaces/{ws}/bodies/{b['id']}/step", json={"n": 5}).status_code == 200


def test_cooperative_mode_runs_the_same_job_in_time_slices(monkeypatch, client, ws):
    """The browser edition has no threads: jobs are advanced by run_deferred() between other work. The record must be the same."""
    from xzr.service import session as S
    from xzr.service import xbtro_ops as xb

    threaded = run(client, ws, "B", {"n_seeds": 4})
    ref = client.get(f"{BASE}/workspaces/{ws}/records/{threaded['record_id']}").json()["digest"]
    monkeypatch.setattr(S, "COOPERATIVE", True)
    workspace = xb.workspace(ws, next(w.owner for w in xb.WORKSPACES.values() if w.id == ws))
    job = xb.start_experiment(workspace, "B", {"n_seeds": 4})
    slices = 0
    while S.DEFERRED and slices < 5000:
        S.run_deferred(0.002)
        slices += 1
    j = xb.job_view(workspace, job["id"])
    assert j["status"] == "done" and slices > 5, (j, slices)  # it really was advanced in many small slices
    assert workspace.history.get(j["record_id"])["digest"] == ref
