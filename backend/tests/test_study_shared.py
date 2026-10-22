"""The shared ARDS-HPO environment (env3): the task on the runtime world, its worker protocol, the HPO arm and its independent verification,
the operations table, fairness between the two arm families, and (when ARDS and node are present) ARDS arms and the HPO arm scored by ARDS's own
held-out code."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from xzr.hpo.metarevision import MetaReviser, RuleTable
from xzr.study import ards, runner, templates
from xzr.study import protocol as P
from xzr.study.shared import hpo_arm as H
from xzr.study.shared import oi_worker, ops
from xzr.study.shared import oi_world as O

needs_ards = pytest.mark.skipif(ards.available() is not None, reason=str(ards.available()))
REQ = {"preset": "intermittent", "alteration": "retention-shift", "nSeeds": 8, "seedBase": 4_100_000}


# ------------------------------------------------------------------------------------------------ the task
def test_catalog_and_capability_follow_the_instrument_rules():
    cat = O.catalog()
    assert len(cat["differences"]) == 12 and set(cat["kinds"]) == set(O.KINDS) and cat["thresholds"]["identD"] == 0.8
    d = O.DIFF_BY_ID
    start = O.START_CONFIG
    assert O.capability_of(start, d["activity_pooled"])["capable"]
    assert O.capability_of(start, d["recursion_pooled"])["reason"] == "device-mismatch"
    assert (
        O.capability_of(start, d["activity_spread"])["reason"] == "scale-mismatch"
    )  # macro scale cannot carry a between-region feature
    fine = {**start, "kinds": [*start["kinds"], "activity"], "overrides": {"activity": {"spatial": "local", "sample_hz": 5}}}
    assert O.capability_of(fine, d["activity_peak"])["reason"] == "time-window-mismatch"  # period 2 > the 1 step it needs
    fine["overrides"]["activity"]["sample_hz"] = 10
    assert O.capability_of(fine, d["activity_peak"])["capable"]
    short = {**fine, "window": [0.0, 0.2]}
    assert O.capability_of(short, d["activity_pooled"])["reason"] == "boundary-invisible"
    assert O.capability_of({**start, "kinds": []}, d["activity_pooled"])["reason"] == "unmeasured"


def test_identification_rule_and_paired_effect():
    assert (
        O.is_identified({"p": 0.001, "d": 1.0})
        and not O.is_identified({"p": 0.02, "d": 1.0})
        and not O.is_identified({"p": 0.001, "d": 0.5})
    )
    assert not O.is_identified(None) and not O.is_identified({"p": None, "d": None})
    e = O.paired_effect([1, 2, 3, 4, 5, 6, 7, 8], [2, 3, 4, 5, 6, 7, 8, 9.5])
    assert e["d"] > 5 and e["p"] < 1e-6 and e["n"] == 8
    assert O.paired_effect([1, 2], [3, 4])["d"] is None  # fewer than 3 pairs: undefined, never 0


def test_observation_is_deterministic_and_noise_matters():
    a = O.observe({**REQ, "configs": [O.START_CONFIG]})
    b = O.observe({**REQ, "configs": [O.START_CONFIG]})
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    noisy = {**O.START_CONFIG, "name": "noisy", "overrides": {k: {"noise": 4} for k in O.START_CONFIG["kinds"]}}
    quiet = {**O.START_CONFIG, "name": "quiet", "overrides": {k: {"noise": 0} for k in O.START_CONFIG["kinds"]}}
    r = O.observe({**REQ, "configs": [noisy, quiet]})
    dn = {x["id"]: abs(x["observed"]["d"]) for x in r["configs"][0]["rows"] if x["observed"]}
    dq = {x["id"]: abs(x["observed"]["d"]) for x in r["configs"][1]["rows"] if x["observed"]}
    assert dn and sum(dq[i] > dn[i] for i in dn) >= len(dn) - 1  # less noise: larger standardized effects


def test_requests_are_validated():
    for bad in (
        {"preset": "nope"},
        {"alteration": "nope"},
        {"nSeeds": 3},
        {"configs": []},
        {"configs": [{"name": "x", "kinds": ["zzz"], "overrides": {}, "window": None}]},
    ):
        with pytest.raises(ValueError):
            O.observe({**REQ, "configs": [O.START_CONFIG], **bad})


def test_ground_truth_is_a_function_of_the_definition_and_separates_alterations():
    t = O.truth_of("intermittent", "coupling-shift")["reference"]  # cached on disk after the first computation
    existing = sorted(k for k, v in t.items() if v["exists"])
    assert existing == ["structure_pooled", "structure_spread"]  # only the structure channel carries this alteration
    assert all(O.truth_of("intermittent", a)["reference"] for a in O.ALTERATIONS)
    assert O.definition_digest() == O.definition_digest() and len(O.definition_digest()) == 64


def test_a_hidden_difference_becomes_identifiable_only_by_revising_the_configuration():
    """Invisibility is not absence. The structure difference of coupling-shift exists in the truth. The start configuration cannot see it (no
    structure channel); adding the channel at the scale it needs makes it capable but still not identified (noise); lowering the noise as well
    identifies it. Three states, three different statements: device-blind, capable-but-unidentified, identified."""
    req = {"preset": "intermittent", "alteration": "coupling-shift", "nSeeds": 12, "seedBase": 4_200_000}
    added = {
        **O.START_CONFIG,
        "name": "added",
        "kinds": [*O.START_CONFIG["kinds"], "structure"],
        "overrides": {"structure": {"spatial": "local"}},
    }
    quiet = {**added, "name": "quiet", "overrides": {"structure": {"spatial": "local", "noise": 0}}}
    r = O.observe({**req, "configs": [O.START_CONFIG, added, quiet]})
    row = [{x["id"]: x for x in c["rows"]}["structure_spread"] for c in r["configs"]]
    assert row[0]["capability"]["reason"] == "device-mismatch" and row[0]["observed"] is None and not row[0]["identified"]
    assert row[1]["capability"]["capable"] and not row[1]["identified"]
    assert row[2]["capability"]["capable"] and row[2]["identified"]
    assert O.truth_of("intermittent", "coupling-shift")["reference"]["structure_spread"]["exists"]


def test_worker_protocol():
    assert oi_worker.handle({"cmd": "catalog"})["catalog"]["thresholds"]["identP"] == 0.01
    d = oi_worker.handle({"cmd": "describe"})
    assert d["digest"] == O.definition_digest() and d["env"] == O.ENV_ID
    cap = oi_worker.handle({"cmd": "capability", "configs": [O.START_CONFIG]})["capability"]["control"]
    assert set(cap) == {x.id for x in O.DIFFS}
    r = oi_worker.handle({"cmd": "observe", "req": {**REQ, "configs": [O.START_CONFIG]}, "truth": True})
    assert r["ok"] and r["bodyRuns"] == 16 and "truth" in r and set(r["truth"]["reference"]) == set(O.DIFF_BY_ID)
    with pytest.raises(ValueError):
        oi_worker.handle({"cmd": "bogus"})
    json.dumps(r, allow_nan=False, default=lambda x: None if x != x else float(x))  # strict JSON for the TypeScript side


# ------------------------------------------------------------------------------------------------ the HPO arm
def test_hpo_arm_spends_the_budget_and_its_record_verifies_independently():
    r = H.run(3980)
    assert r["bodyRuns"] == H.BODY_RUN_BUDGET == 72 and r["setupSecondsSpent"] <= r["setupBudget"] == 300
    assert [c for c in H.verify(r) if not c["pass"]] == []
    assert set(r["opsUsed"]) <= set(ops.REVISION_OPS)
    assert all(c["request"]["seedBase"] < 5_000_000 for c in r["cycles"])  # never the held-out or truth seeds


def test_hpo_arm_is_deterministic():
    assert json.dumps(H.run(3981, meta=True), sort_keys=True) == json.dumps(H.run(3981, meta=True), sort_keys=True)


def test_hpo_arm_never_reads_the_ground_truth():
    src = Path(H.__file__).read_text()
    tree = ast.parse(src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert (
        not names & {"truth_of", "TRUTH_REF", "_ref_features", "IDEAL"} and "truth" not in strings and "reference" not in strings
    )


def test_verification_catches_a_doctored_record():
    r = H.run(3980)
    bad = json.loads(json.dumps(r))
    bad["finalConfig"]["kinds"].append("recursion")
    assert any(not c["pass"] for c in H.verify(bad))
    bad = json.loads(json.dumps(r))
    bad["bodyRuns"] = 60
    assert any(not c["pass"] for c in H.verify(bad))
    bad = json.loads(json.dumps(r))
    bad["setupSecondsSpent"] = 9999
    assert any(not c["pass"] for c in H.verify(bad))


def test_history_off_removes_the_noise_rule_and_the_memory():
    cap = [{"id": d.id, "capability": O.capability_of(O.START_CONFIG, d)} for d in O.DIFFS]
    cat = O.catalog()
    with_h = H.propose(O.START_CONFIG, cap, {"activity": 3}, cat, RuleTable(H.OI_SPEC), True)
    without = H.propose(O.START_CONFIG, cap, {"activity": 3}, cat, RuleTable(H.OI_SPEC), False)
    assert any(c["rule"] == "lower-noise" for c in with_h) and not any(c["rule"] == "lower-noise" for c in without)
    assert with_h[0]["rule"] == "bundle" and len(with_h[0]["changes"]) > 1  # the HPO controller's one-epoch bundle comes first


def test_meta_revision_with_this_policys_own_rule_spec():
    m = MetaReviser(RuleTable(H.OI_SPEC))
    seen = []
    for ep in range(8):
        m.register("activity", "unidentified", ep, ep, [])
        seen += m.judge({"activity": {"unidentified": [0]}}, ep)
    steps = [r["to"] for r in seen if r["revision"] == "parameter"]
    assert steps == [0.35, 0.2] and seen[-1]["revision"] == "exhausted"  # 0.5 -> 0.35 -> 0.2, then the bound: exhausted, recorded
    assert m.rules.params["noise_factor"] == 0.2 and "unidentified" in m.rules.exhausted


# ------------------------------------------------------------------------------------------------ operations and fairness
def test_operations_table_names_what_is_shared_internal_and_unavailable():
    assert set(ops.SHARED) == {
        "observe",
        "sensor-change",
        "noise-change",
        "time-resolution-change",
        "scale-change",
        "time-window-change",
        "capability-query",
    }
    unavailable = {k for k, v in ops.OPERATIONS.items() if v["status"] == "not available"}
    assert {
        "variable-generation",
        "boundary-change",
        "intervention",
        "evaluation-change",
    } == unavailable  # named, never silently assumed
    ex = ops.access("ards", ards.arm_spec("EXISTING-blind"))
    pa = ops.access("ards", ards.arm_spec("V2-PA"))
    h = ops.access("hpo", {"history": True, "meta": True})
    assert not ex["external-memory"] and pa["external-memory"] and h["rule-revision"] and not pa["rule-revision"]
    assert (
        all(ex[k] for k in ("sensor-change", "noise-change", "scale-change"))
        and not ops.access("ards", ards.arm_spec("V1-A"))["sensor-change"]
    )


def test_shared_template_validates_and_declares_every_difference():
    d = templates.template("shared-comparison")
    assert P.validate(d) == [] and P.fairness_issues(d) == []
    f = P.fairness(d)
    assert "operations" in f and set(f["operations"]["access"]) == {a["name"] for a in d["arms"]}
    c1 = next(c for c in f["contrasts"] if c["contrast"] == "C1")
    assert set(c1["differences"]) == {
        "proposal_policy",
        "history_reinsertion",
    }  # same information, authority, budget; the policy and the history differ
    p = f["profiles"]
    assert (
        p["hpo-rules"]["information"] == p["existing-blind"]["information"]
        and p["hpo-rules"]["revision_authority"] == p["existing-blind"]["revision_authority"]
    )


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda d: d["arms"][5].update(ards={"arm": "V2-PA"}), "not both"),
        (lambda d: d["arms"][5]["hpo"].update(bogus=True), "unknown hpo option"),
        (lambda d: d.update(mode="exploratory"), "only functional"),
        (lambda d: d["seeds"].update(list=[[100, 100]]), "reserved seed range"),
    ],
)
def test_shared_protocol_refuses_what_could_reach_gated_data(mutate, needle):
    d = templates.template("shared-comparison")
    mutate(d)
    assert any(needle in i for i in P.validate(d)), P.validate(d)


# ------------------------------------------------------------------------------------------------ with ARDS (needs node and the ARDS repo)
@needs_ards
def test_ards_equivalence_on_env3_and_the_ards_repo_is_untouched():
    import subprocess

    root = ards.ards_root()
    before = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False).stdout
    row = ards.equivalence("env3", "V1-A", 3980)
    assert row["metrics_identical"] and row["verification_failed_bridge"] == 0 == row["verification_failed_direct"]
    assert (
        subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False).stdout == before
    )


@needs_ards
def test_hpo_arm_and_an_ards_arm_run_in_one_study_and_are_scored_by_ards_code(tmp_path):
    d = templates.template("shared-comparison", n_seeds=1)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("existing-blind", "hpo-rules")]
    d["contrasts"] = [c for c in d["contrasts"] if {c["a"], c["b"]} == {"hpo-rules", "existing-blind"}]
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=2)
    runs = {r["arm"]: r for r in st.runs()}
    assert {r["status"] for r in runs.values()} == {"ok"}, [r.get("error") for r in runs.values()]
    for r in runs.values():
        m = r["metrics"]
        assert (
            m["body_runs"] == 72
            and m["verification_failed"] == 0
            and 0 <= m["unseen_coverage"] <= 1
            and not math.isnan(m["seen_coverage"])
        )
    assert runs["hpo-rules"]["hpo_arm"]["verification_failed"] == [] and runs["hpo-rules"]["ards_eval"]["mode"] == "test"
    assert runs["existing-blind"]["ards"]["env"] == "env3"
