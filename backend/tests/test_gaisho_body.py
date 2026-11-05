"""GAISHO domain 004 (Body, B1): the XB-TRO planar body reached through the optional link of bodylink.py. These tests need the XB-TRO package (branch feat/xb-tro, not merged here): they run when XZR_XBTRO_PATH, or the
default checkout path below, names it, and are SKIPPED otherwise (a skip is not a pass). The link and the registry behaviour without it are tested unconditionally."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from xzr.gaisho import bodylink
from xzr.gaisho.domains import BODY_STATUS, STATUS, domain_registry, status_of
from xzr.gaisho.export import run_experiment
from xzr.gaisho.lab import FULL, Observation

XB = Path(os.environ.get("XZR_XBTRO_TEST_PATH", "/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend/xzr/xbtro"))
needs_body = pytest.mark.skipif(not (XB / "engine.py").is_file(), reason="the XB-TRO package is not on this machine (it is not part of this branch)")
HUMAN, MACHINE = "human-like planar body", "machine-like planar body"
SEEDS = [1, 2, 3, 4]


@pytest.fixture
def linked(monkeypatch):
    monkeypatch.setenv(bodylink.ENV, str(XB))
    bodylink._CACHE.clear()
    yield
    bodylink._CACHE.clear()


def test_without_the_link_the_body_domain_is_not_executed_and_nothing_is_substituted(monkeypatch):
    monkeypatch.delenv(bodylink.ENV, raising=False)
    bodylink._CACHE.clear()
    assert domain_registry()["004-body"] is None and status_of("004-body") is STATUS["004-body"] and STATUS["004-body"]["executed"] is False
    out = run_experiment({"domain": "004-body"})
    assert out["executed"] is False and "no substitute computation" in out["note"]
    for bad in ("", "/nonexistent/path", "/tmp"):  # a path that is not the package is refused, not imported
        monkeypatch.setenv(bodylink.ENV, bad)
        bodylink._CACHE.clear()
        assert bodylink.load() is None and domain_registry()["004-body"] is None
    bodylink._CACHE.clear()


def test_the_link_module_is_the_only_one_that_reads_files_and_it_does_nothing_else():
    src = (Path(bodylink.__file__)).read_text()
    code = re.sub(r'""".*?"""', "", "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#")), flags=re.S)
    assert not re.search(r"\b(subprocess|socket|urllib|requests|httpx|shutil|tempfile|os\.system|os\.popen|eval|exec)\b\(?", code.replace("exec_module", "")), "the link must use no process, network or dynamic code"
    assert not re.search(r"\.(write_text|write_bytes|unlink|mkdir|touch)\(|open\([^)]*[\"']w", code)  # it reads, it never writes
    assert "sys.path" not in code.replace("sys.modules", "")  # the path is never added to sys.path
    assert code.count("os.environ.get(ENV") == 1  # the path comes from the environment only, never from a request


@needs_body
def test_the_link_loads_the_leaf_package_and_names_the_body_it_ran_on(linked):
    link = bodylink.load()
    assert link is not None and link.model_version == "xb-tro/1.0" and len(link.source_sha256) == 64 and link.n_files > 10
    again = bodylink._load(XB)
    assert again is not None and again.source_sha256 == link.source_sha256  # the hash is of the files, so a changed body gives a different record
    reg = domain_registry()
    assert reg["004-body"] is not None and status_of("004-body") is BODY_STATUS and BODY_STATUS["executed"] is True


@needs_body
def test_the_body_experiment_runs_gives_continuation_classes_and_keeps_every_layer_apart(linked):
    out = run_experiment({"domain": "004-body", "seeds": SEEDS, "conditions": [HUMAN]})
    assert out["executed"] is True and out["body"]["body"] == "XB-TRO" and out["figure_kind"] == "EXECUTED_COMPUTATIONAL_EXPERIMENT"
    c = out["result"]["conditions"][HUMAN]
    assert c["relations"]["baseline_fall"]["value"] == 0.0  # the undisturbed, undelayed body stays up
    assert c["relations"]["effect_x"]["status"] == "IDENTIFIED" and c["relations"]["effect_x"]["value"] > 0.3  # a sensory delay turns continuation into a fall
    sh = out["shapes"][HUMAN]["end"]
    assert len(sh["vertices"]) == 25 and {v["z"] for v in sh["vertices"]} <= {i / len(SEEDS) for i in range(len(SEEDS) + 1)}  # a cell is the share of seeds that fall
    assert {v["source"]["provenance"] for v in sh["vertices"]} == {"RECORDED_OBSERVATION"} and len(sh["cuts"]) > 0  # the body has real steps, unlike the logistic ridge of the knowledge domain
    # the attribution is untouched by any of it: a body that falls less is an operational difference, a prereflective operation (R37 P), not a Gaisho
    lv = out["levels"][HUMAN]
    assert lv["gaisho_attribution"]["state"] == "UNRESOLVED" and lv["gaisho_attribution"]["applicability_gate"].startswith("NOT_PASSED") and lv["gaisho_operational_shape"]["state"] == "NOT_ESTABLISHED"
    reg = out["r37"]["registers"]
    assert reg["P"]["lab"] == "EXECUTED_IN_MODEL" and "not a thinker" in reg["P"]["note"] and reg["A_G"]["lab"] == "UNRESOLVED" and reg["Occ_G"]["lab"] == "NOT_ASSESSED" and reg["C"]["lab"] == "NOT_MODELLED"
    assert not any("spike" in json.dumps(v).lower() for v in (out["result"], out["shapes"]))  # there are no spikes in this body


@needs_body
def test_the_body_record_is_reproducible_and_restorable(linked):
    from xzr.gaisho.export import restore

    a = run_experiment({"domain": "004-body", "seeds": SEEDS, "conditions": [MACHINE]})
    b = run_experiment({"domain": "004-body", "seeds": SEEDS, "conditions": [MACHINE]})
    assert a["digest"] == b["digest"] and restore({"spec": a["spec"], "digest": a["digest"]})["same_digest"] is True
    assert run_experiment({"domain": "004-body", "seeds": [5, 6, 7, 8], "conditions": [MACHINE]})["digest"] != a["digest"]  # seeds are independent replications


@needs_body
def test_the_two_bodies_differ_in_their_profile_under_the_same_interventions(linked):
    out = run_experiment({"domain": "004-body", "seeds": SEEDS})
    z = {c: [v["z"] for v in out["shapes"][c]["end"]["vertices"]] for c in out["shapes"]}
    assert z[HUMAN] != z[MACHINE]  # the same two interventions do not give one shape for every body


@needs_body
def test_observation_changes_the_record_of_the_body_not_the_body(linked):
    from xzr.gaisho.compare import compare_observations

    dom = domain_registry()["004-body"]
    c = compare_observations(dom, HUMAN, FULL, Observation(scale=2), (1, 2, 3, 4))
    assert c["same_realized_operation"] is True and c["observation_changed_the_operation"] is False


@needs_body
def test_the_api_runs_the_body_within_its_seed_cap(linked):
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    assert c.post("/api/gaisho/run", json={"domain": "004-body", "seeds": list(range(1, 10))}).status_code == 422  # the cap is 8 seeds
    r = c.post("/api/gaisho/run", json={"domain": "004-body", "seeds": [1, 2], "conditions": [HUMAN]})
    assert r.status_code == 200 and r.json()["executed"] is True
    sp = c.get("/api/gaisho/spec").json()["domains"]["004-body"]
    assert sp["status"]["executed"] is True and sp["max_seeds"] == 8 and sp["conditions"] == [HUMAN, MACHINE]
