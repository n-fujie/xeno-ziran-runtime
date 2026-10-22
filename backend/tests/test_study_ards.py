"""ARDS bridge: protocol rules (no node needed), the registry snapshot against the live ARDS registry, and one real arm run in ARDS's
software-test mode, with the ARDS repository left untouched."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from xzr.study import ards, runner, templates
from xzr.study import protocol as P

needs_ards = pytest.mark.skipif(ards.available() is not None, reason=str(ards.available()))


def doc(**kw):
    d = templates.template("ards-comparison", n_seeds=1)
    d.update(kw)
    return d


def test_template_validates_and_fairness_is_computed_from_ards_arm_facts():
    d = doc()
    assert P.validate(d) == [] and P.fairness_issues(d) == []
    prof = P.fairness(d)["profiles"]
    assert prof["existing-blind"]["information"]["reads"] == "observer-view" == prof["pa-validated"]["information"]["reads"]
    assert prof["existing-blind"]["history_reinsertion"] is False and prof["pa-validated"]["history_reinsertion"] is True
    assert prof["fixed-noise"]["controller"] == "preset" and prof["existing-blind"]["controller"] == "revised-from-data"
    c1 = next(c for c in P.fairness(d)["contrasts"] if c["contrast"] == "C1")
    assert set(c1["differences"]) == {
        "history_reinsertion"
    }  # same information, same permissions, same budget: only the history differs


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda d: d.update(mode="exploratory"), "only functional"),
        (lambda d: d["seeds"].update(list=[[2000, 2000]]), "reserved seed range"),
        (lambda d: d["seeds"].update(list=[[3980, 3981]]), "reserved seed range"),
        (lambda d: d["arms"][0]["ards"].update(arm="NOT-AN-ARM"), "unknown ARDS arm"),
        (lambda d: d["arms"][0]["ards"].update(arm="V2-PA-shuffled"), "another replicate"),
        (lambda d: d["environment"].update(ards_env="env9"), "ards_env"),
        (lambda d: d.update(seeds={"gen_base": 3980, "engine_base": 3980, "n": 2}), "explicit list"),
    ],
)
def test_ards_protocols_that_could_reach_gated_data_are_refused(mutate, needle):
    d = doc()
    mutate(d)
    issues = P.validate(d)
    assert issues and any(needle in i for i in issues), issues


def test_confirmatory_and_exploratory_ards_studies_cannot_be_created(tmp_path):
    for mode in ("exploratory", "confirmatory"):
        d = doc(mode=mode)
        d["seeds"] = {"list": [[12000, 12000]]}
        with pytest.raises(P.ProtocolInvalid):
            runner.Study.create(d, tmp_path)


@needs_ards
def test_registry_snapshot_matches_the_live_ards_registry():
    root = ards.ards_root()
    p = subprocess.run(
        [str(root / "node_modules/.bin/vite-node"), str(ards.JOB), "--", "describe"],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "XZR_ARDS_ROOT": str(root), "PATH": f"{ards.node_dir()}:{os.environ['PATH']}"},
        timeout=300,
        check=False,
    )
    live = json.loads([x for x in p.stdout.splitlines() if x.startswith("{")][-1])
    snap = ards.registry()
    assert snap["envs"] == live["envs"]
    key = ("id", "role", "factors", "reads", "mayRevise", "implementedIn")
    assert snap["arms"] == [{k: a[k] for k in key} for a in live["arms"]], (
        "ARDS arm registry changed: regenerate ards_registry.json"
    )


@needs_ards
def test_one_ards_arm_runs_verified_in_test_mode_and_leaves_the_ards_repo_untouched(tmp_path):
    root = ards.ards_root()

    def snapshot():
        return subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False).stdout

    before = snapshot()
    d = doc()
    d["arms"] = [a for a in d["arms"] if a["name"] == "existing-blind"]
    d["contrasts"] = []
    d["hypotheses"] = []
    d["stop"]["timeout_per_run_s"] = 900
    st = runner.Study.create(d, tmp_path)
    st.execute(inline=True)
    (r,) = st.runs()
    assert r["status"] == "ok", r.get("error")
    assert r["ards"]["mode"] == "test" and r["ards"]["replicate"] == 3980 and r["ards"]["verification_failed"] == []
    assert r["ards"]["verification_checks"] > 0 and r["ards"]["spec"]["id"] == "EXISTING-blind"
    assert 0.0 <= r["metrics"]["unseen_coverage"] <= 1.0 and r["metrics"]["body_runs"] > 0
    assert snapshot() == before  # nothing written into the ARDS repository
