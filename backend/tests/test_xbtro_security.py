"""Security of the research environment: owner scoping of every resource, resource limits, oversized / malformed input, tampered imports."""

from __future__ import annotations

import dataclasses
import json
import time

import pytest
from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.service import xbtro_ops as xb
from xzr.service.app import app

B = "/api/xbtro"


@pytest.fixture(autouse=True)
def _isolated_workspaces():
    """Each test starts from an empty set of workspaces (the per-process workspace limit is itself a tested behaviour)."""
    xb.WORKSPACES.clear()
    yield
    xb.WORKSPACES.clear()


@pytest.fixture()
def alice():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def bob():
    with TestClient(app) as c:
        yield c


def make_ws(c):
    r = c.post(f"{B}/workspaces")
    assert r.status_code == 200
    return r.json()["id"]


def finish(c, ws, jid, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        j = c.get(f"{B}/workspaces/{ws}/jobs/{jid}").json()
        if j["status"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_every_resource_of_a_workspace_is_invisible_to_another_client(alice, bob):
    ws = make_ws(alice)
    job = alice.post(f"{B}/workspaces/{ws}/experiments", json={"experiment": "B", "params": {"n_seeds": 4}}).json()["job"]
    done = finish(alice, ws, job["id"])
    rid = done["record_id"]
    body = alice.post(f"{B}/workspaces/{ws}/bodies", json={"n_seeds": 1, "horizon_s": 3}).json()["id"]
    bob_make = make_ws(bob)  # bob has his own workspace, with its own cookie
    probes = [
        ("GET", f"{B}/workspaces/{ws}/history"),
        ("GET", f"{B}/workspaces/{ws}/history/export"),
        ("GET", f"{B}/workspaces/{ws}/jobs"),
        ("GET", f"{B}/workspaces/{ws}/jobs/{job['id']}"),
        ("POST", f"{B}/workspaces/{ws}/jobs/{job['id']}/cancel"),
        ("GET", f"{B}/workspaces/{ws}/records/{rid}"),
        ("GET", f"{B}/workspaces/{ws}/records/{rid}?format=csv"),
        ("DELETE", f"{B}/workspaces/{ws}/records/{rid}"),
        ("POST", f"{B}/workspaces/{ws}/records/{rid}/rerun"),
        ("GET", f"{B}/workspaces/{ws}/bodies/{body}"),
        ("POST", f"{B}/workspaces/{ws}/bodies/{body}/step"),
        ("GET", f"{B}/workspaces/{ws}/bodies/{body}/inspect?part=ground"),
        ("DELETE", f"{B}/workspaces/{ws}/bodies/{body}"),
        ("DELETE", f"{B}/workspaces/{ws}"),
    ]
    for method, path in probes:
        r = (
            bob.request(method, path, json={"n": 1} if method == "POST" else None)
            if method == "POST"
            else bob.request(method, path)
        )
        assert r.status_code == 404, (method, path, r.status_code)
        assert "no such" in r.text
    # and a workspace of his own cannot be used to reach hers
    assert bob.get(f"{B}/workspaces/{bob_make}/records/{rid}").status_code == 404
    # the owner is unaffected
    assert alice.get(f"{B}/workspaces/{ws}/records/{rid}").status_code == 200


def test_ids_cannot_traverse_or_be_guessed_by_shape(alice):
    ws = make_ws(alice)
    for bad in ("..%2f..%2fetc%2fpasswd", "../x", "a/b", "%00", "x" * 5000):
        r = alice.get(f"{B}/workspaces/{ws}/records/{bad}")
        assert r.status_code in (404, 422, 400, 414), (bad[:20], r.status_code)
    assert alice.get(f"{B}/workspaces/not-hex/history").status_code == 404
    assert alice.get(f"{B}/workspaces/{ws}/records/does-not-exist").status_code == 404


def test_resource_limits_are_named_and_enforced(monkeypatch, alice):
    ws = make_ws(alice)
    small = dataclasses.replace(xb.XB, max_bodies=1, max_records=2, max_body_cells=20_000, max_obs_models=3, max_workspaces=2)
    monkeypatch.setattr(xb, "XB", small)
    assert alice.post(f"{B}/workspaces/{ws}/bodies", json={"n_seeds": 1, "horizon_s": 5}).status_code == 200
    r = alice.post(f"{B}/workspaces/{ws}/bodies", json={"n_seeds": 1, "horizon_s": 5})
    assert r.status_code == 422 and "max_bodies" in r.text
    ws2 = make_ws(alice)
    r = alice.post(f"{B}/workspaces/{ws2}/bodies", json={"n_seeds": 8, "horizon_s": 60})
    assert r.status_code == 422 and "max_body_cells" in r.text  # seeds x steps bounds the memory of a body
    r = alice.post(f"{B}/workspaces/{ws2}/bodies", json={"overrides": {"task": {"dt": 0.0001}}})
    assert r.status_code == 422
    too_many = {"config": {"name": "x", "models": [{"id": f"m{i}", "kind": "posture"} for i in range(4)], "window": None}}
    r = alice.post(f"{B}/workspaces/{ws2}/bodies", json={"observation": too_many})
    assert r.status_code == 422 and "at most 3 models" in r.text
    r = alice.post(f"{B}/workspaces/{ws2}/experiments", json={"experiment": "B", "params": {"n_seeds": 4}})
    done = finish(alice, ws2, r.json()["job"]["id"])
    assert done["status"] == "done"
    r = alice.post(f"{B}/workspaces/{ws2}/experiments", json={"experiment": "A", "params": {"n_seeds": 4}})
    done = finish(alice, ws2, r.json()["job"]["id"])
    r = alice.post(f"{B}/workspaces/{ws2}/experiments", json={"experiment": "A", "params": {"n_seeds": 5}})
    assert r.status_code == 422 and "max_records" in r.text
    before = len(xb.WORKSPACES)
    third = alice.post(f"{B}/workspaces")  # at max_workspaces the owner's oldest workspace is replaced: the count does not grow
    assert third.status_code == 200 and len(xb.WORKSPACES) <= before


def test_only_one_experiment_runs_at_a_time_in_a_workspace_on_a_public_runtime(monkeypatch, alice):
    from xzr.service import limits as limits_mod

    monkeypatch.setattr(xb, "LIMITS", dataclasses.replace(xb.LIMITS, public=True))
    monkeypatch.setenv("XZR_XBTRO", "1")
    assert limits_mod  # (the module is the one xb reads)
    ws = make_ws(alice)
    first = alice.post(f"{B}/workspaces/{ws}/experiments", json={"experiment": "B", "params": {"n_seeds": 4}})
    assert first.status_code == 200
    second = alice.post(f"{B}/workspaces/{ws}/experiments", json={"experiment": "B", "params": {"n_seeds": 4}})
    assert second.status_code in (422, 429, 503) and "max_active_jobs_per_workspace" in second.text
    finish(alice, ws, first.json()["job"]["id"])


def test_oversized_and_deeply_nested_bodies_are_refused(monkeypatch, alice):
    ws = make_ws(alice)
    from xzr.service import security as sec

    tight = dataclasses.replace(app_mod.LIMITS, max_body_bytes=2000, max_depth=8, max_string=100)
    monkeypatch.setattr(app_mod, "LIMITS", tight)
    monkeypatch.setattr(sec, "LIMITS", tight)
    big = alice.post(
        f"{B}/workspaces/{ws}/records", content=json.dumps({"x": "y" * 5000}), headers={"content-type": "application/json"}
    )
    assert big.status_code == 413
    nest: dict = {}
    cur = nest
    for _ in range(20):
        cur["a"] = {}
        cur = cur["a"]
    deep = alice.post(f"{B}/workspaces/{ws}/records", json=nest)
    assert deep.status_code == 413 and "max_depth" in deep.text
    long_str = alice.post(f"{B}/workspaces/{ws}/diagnose", json={"preset": "x" * 500})
    assert long_str.status_code in (413, 422)
    bad_json = alice.post(f"{B}/workspaces/{ws}/records", content="{not json", headers={"content-type": "application/json"})
    assert bad_json.status_code == 400


def test_tampered_and_foreign_imports_are_refused(alice):
    ws = make_ws(alice)
    job = alice.post(f"{B}/workspaces/{ws}/experiments", json={"experiment": "F", "params": {"n_seeds": 4}}).json()["job"]
    rid = finish(alice, ws, job["id"])["record_id"]
    rec = alice.get(f"{B}/workspaces/{ws}/records/{rid}").json()
    other = make_ws(alice)
    ok = dict(rec)
    assert alice.post(f"{B}/workspaces/{other}/records", json=ok).status_code == 200
    for mutate in (
        lambda r: r["results"]["tables"][0]["rows"][0].__setitem__(1, "edited"),
        lambda r: r.__setitem__("schema", "evil/1"),
        lambda r: r.pop("results"),
    ):
        bad = json.loads(json.dumps(rec))
        mutate(bad)
        w = make_ws(alice)
        r = alice.post(f"{B}/workspaces/{w}/records", json=bad)
        assert r.status_code == 422, r.text
    assert (
        alice.post(f"{B}/workspaces/{other}/history/import", json={"schema": "xbtro.history/1", "records": "nope"}).status_code
        == 422
    )
    assert alice.post(f"{B}/workspaces/{other}/history/import", json=[1, 2, 3]).status_code == 422


def test_parameters_are_validated_before_anything_runs(alice):
    ws = make_ws(alice)
    bad = [
        {"experiment": "B", "params": {"n_seeds": "12"}},
        {"experiment": "B", "params": {"n_seeds": 1e9}},
        {"experiment": "B", "params": {"n_seeds": True}},
        {"experiment": "C", "params": {"principles": "axis-maintenance"}},
        {"experiment": "C", "params": {"principles": ["x"] * 20}},
        {"experiment": "D", "params": {"trials": 1000}},
        {"experiment": "S", "params": {"push_force": float("inf")}},
        {"experiment": "B", "params": {"carry_over": {"fatigue": [float("nan")]}}},
        {"experiment": "B", "params": {"carry_over": {"__proto__": [1]}}},
        {"experiment": "B", "params": {"carry_over": {"fatigue": [1] * 500}}},
        {"experiment": "../../etc", "params": {}},
        {"params": {}},
        {"experiment": ["B"]},
    ]
    for payload in bad:
        r = alice.post(
            f"{B}/workspaces/{ws}/experiments",
            content=json.dumps(payload, allow_nan=True),
            headers={"content-type": "application/json"},
        )
        assert r.status_code in (400, 404, 422), (payload, r.status_code, r.text[:120])
    assert not xb.WORKSPACES[ws].history.order  # nothing ran
    assert not [j for j in xb.S.JOBS.values() if j.get("workspace") == ws]


def test_a_live_body_command_cannot_reach_outside_the_model(alice):
    ws = make_ws(alice)
    bid = alice.post(f"{B}/workspaces/{ws}/bodies", json={"n_seeds": 1, "horizon_s": 3}).json()["id"]
    for cmd in (
        {"type": "eval", "code": "1"},
        {"type": "intervention", "id": "__class__"},
        {"type": "intervention", "id": "perturbation", "magnitude": 1e12},
        {"type": "line", "id": "../../x", "enabled": True},
        {"type": "xeno14", "ids": ["nope"]},
        {"type": "observation", "observation": {"config": {"models": "x"}}},
        "text",
        None,
    ):
        r = alice.post(
            f"{B}/workspaces/{ws}/bodies/{bid}/command", content=json.dumps(cmd), headers={"content-type": "application/json"}
        )
        assert r.status_code in (400, 422), (cmd, r.status_code, r.text[:100])
    assert alice.post(f"{B}/workspaces/{ws}/bodies/{bid}/step", json={"n": 5}).status_code == 200  # and the body is still usable
