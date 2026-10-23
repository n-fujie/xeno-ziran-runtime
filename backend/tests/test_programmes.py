"""The four research-programme protocols, the optional environment settings they use, the pre-execution audits, the proposed amendment of the Level 2 draft (which must
leave the draft untouched and the approval gates closed), and the evidence record of a new study. Software checks on reserved functional seeds; no programme is run as an experiment."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from xzr.study import protocol as P
from xzr.study import runner, templates
from xzr.totalobs import loop, profiles

ROOT = Path(__file__).resolve().parents[2]
RP = ("rp1-ziran-self-revision", "rp2-total-observation", "rp3-planetary-placement", "rp4-sss-self-revision")
L2_DIGEST = "d7748ff9dc7e49911d59cac4ecbf41db3e4e998d0a1f6888f401fe0b58ab0aed"  # the Level 2 draft as committed in ced7b3c


def script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "backend" / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------------------------------- the four protocols
@pytest.mark.parametrize("name", RP)
def test_programme_templates_validate_pass_fairness_and_are_functional_never_confirmatory(name):
    d = templates.template(name)
    assert P.validate(d) == [] and P.fairness_issues(d) == []
    assert d["mode"] == "functional" and "freeze" not in d and "preregistration" not in d
    assert len({a["name"] for a in d["arms"]}) == len(d["arms"]) and all(a["description"] for a in d["arms"])
    arms = {a["name"] for a in d["arms"]}
    assert all(c["a"] in arms and c["b"] in arms and c["varies"] for c in d["contrasts"])  # every contrast declares what differs
    if name != "rp1-ziran-self-revision":
        assert d["environment"]["rules_version"] == "v2" and d["environment"]["measures"] == "extended"


def test_programme_arm_counts_and_declared_comparisons():
    n = {k: len(templates.template(k)["arms"]) for k in RP}
    assert n == {
        "rp1-ziran-self-revision": 9,
        "rp2-total-observation": 11,
        "rp3-planetary-placement": 12,
        "rp4-sss-self-revision": 16,
    }
    rp2 = {a["name"] for a in templates.template("rp2-total-observation")["arms"]}
    assert {
        "obs-single",
        "adaptive-base",
        "int-mean",
        "int-finest",
        "int-adaptive",
        "intf-none",
        "intf-strong",
        "loss-none",
        "loss-events",
        "selfrev-on",
    } <= rp2
    rp3 = templates.template("rp3-planetary-placement")
    assert {"fixed-lat1", "random-lat1", "adaptive-lat1", "selfrev-lat1", "fixed-lat4", "fixed-lat1-intf"} <= {
        a["name"] for a in rp3["arms"]
    }
    assert rp3["environment"]["events"], "the sources move: otherwise delay cannot show in recall"
    rp4 = templates.template("rp4-sss-self-revision")
    assert sum(1 for a in rp4["arms"] if a.get("sss")) == 8 and len(rp4["arms"]) == 16  # the complete 2^3 design on the off arms


def test_observation_programmes_give_every_arm_the_same_information_and_rp1_declares_where_it_differs():
    for name in RP[1:]:
        prof = P.fairness(templates.template(name))["profiles"]
        assert len({json.dumps(p["information"], sort_keys=True) for p in prof.values()}) == 1, (
            name
        )  # observer side only, identical in every arm
    rp1 = P.fairness(templates.template("rp1-ziran-self-revision"))
    differ = [c for c in rp1["contrasts"] if "information" in c["differences"]]
    assert differ and all(
        "information" in c["declared"] and not c["undeclared"] for c in differ
    )  # imposed observation conditions are declared, never silent


# ---------------------------------------------------------------------------------------------------- the optional environment settings
def run(env: dict, design: dict, i: int = 0) -> dict:
    return loop.run({"rules_version": "v2", "generations": 5, **env}, {"name": "t", "design": design}, 7000 + i, 70000 + i)


def test_initial_integration_and_random_placement_are_options_and_defaults_are_unchanged():
    for integ in ("mean", "finest"):
        assert run({"integration": integ}, {"policy": "fixed"})["totalobs"]["final_rc"]["ident"]["integrate"] == integ
    assert run({}, {"policy": "fixed"})["totalobs"]["final_rc"]["ident"]["integrate"] == "separate"
    regs = lambda r: [s["region"] for s in r["totalobs"]["generations"][0]["before"]["sensors"].values()]  # noqa: E731
    a = regs(run({"net": {"placement": "random", "n_sensors": 4}}, {"policy": "fixed"}))
    b = regs(run({"net": {"placement": "random", "n_sensors": 4}}, {"policy": "fixed"}))
    c = regs(run({"net": {"n_sensors": 4}}, {"policy": "fixed"}))
    d = regs(run({"net": {"placement": "random", "n_sensors": 4}}, {"policy": "fixed"}, 1))
    assert (
        a == b and a != c and a != d and len(set(a)) == 4
    )  # seeded and deterministic, different from the spread layout and between seeds


def test_extended_measures_exist_only_when_asked_and_only_under_rules_v2():
    plain = run({}, {"policy": "adaptive"})["metrics"]
    assert "coverage_final" not in plain  # a record without the flag is the record of every earlier study
    ext = run(
        {"measures": "extended", "events": [{"gen": 2, "do": "move_source", "k": 0, "region": 10}]}, {"policy": "adaptive"}
    )["metrics"]
    for k in (
        "coverage_final",
        "identification_count_error",
        "change_failure_rate",
        "ops_cost_spent",
        "cycles_completed",
        "observation_loss_share",
        "expiry_rate",
        "reachable_regions_final",
        "recall_post_change",
        "metric_definition_breaks",
    ):
        assert k in ext, k
    assert 0 <= ext["coverage_final"] <= 1 and ext["recall_post_change"] is not None  # a source moved: tracking is defined
    assert (
        run({"measures": "extended"}, {"policy": "adaptive"})["metrics"]["recall_post_change"] is None
    )  # no source moved: undefined, not 0
    bad = {"kind": "total-observation", "measures": "extended", "net": {"placement": "somewhere"}}
    issues = profiles.validate_env(profiles.effective_env(bad), "environment")
    assert any("rules_version v2" in i for i in issues) and any("placement" in i for i in issues)


def test_the_new_options_do_not_touch_a_v1_run():
    v1 = loop.run({"generations": 4}, {"name": "t", "design": {"policy": "adaptive"}}, 7000, 70000)
    assert "rules_version" not in v1["totalobs"] and "coverage_final" not in v1["metrics"]


# ---------------------------------------------------------------------------------------------------- the audits
def test_comparator_audit_does_not_call_a_named_method_compared_unless_it_is_an_arm():
    audit = script("comparators_audit").audit()
    by = {m["method"]: m for m in audit}
    for name in (
        "Active Learning",
        "Active Sensing / information-gain sensor selection",
        "Bayesian Optimization",
        "Adaptive control",
    ):
        assert (
            by[name]["status"] == "not implemented"
            and by[name]["implementation_files"] == []
            and not by[name]["compared_in_this_repository"]
        )
    ai = by["Active Inference"]
    assert not ai["compared_in_this_repository"] and ai["imports_into_study_layers"] == []  # no study layer imports it
    assert ai["status"] in (
        "implemented elsewhere; NOT connected to any study environment as an arm",
        "not implemented",
    )  # never "compared"
    assert [m["method"] for m in audit if m["compared_in_this_repository"]] in (
        [],
        ["The project's own prior adaptive observation procedure (ARDS existing-blind)"],
    )


def test_a_new_study_records_its_numerical_build_and_passes_the_evidence_check(tmp_path):
    d = templates.template("autonomous-loop", n_seeds=2)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("fixed", "adaptive")]
    d["contrasts"] = [c for c in d["contrasts"] if c["a"] == "adaptive" and c["b"] == "fixed"]
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=2)
    from xzr.study import analysis, report

    an = analysis.analyse(st)
    report.build(st, an)
    report.package(st)
    env = st.manifest()["environment"]
    assert env["hierarchy_method"] == 1 and env["numeric_build"].startswith("BLAS ") and "LAPACK" in env["numeric_build"]
    ev = script("evidence_check").check(st.path)
    assert all(ev["items"].values()) and ev["grade"] in ("COMPLETE", "COMPLETE-WITH-LIMITS")
    assert not any("numerical build" in lim for lim in ev["limits"])  # recorded for a new study
    copy = runner.copy_study(st, tmp_path / "tampered")
    next((copy.path / "runs").rglob("*.json")).write_text("{}")
    assert script("evidence_check").check(copy.path)["grade"] == "INCOMPLETE"  # a changed file is caught


# ---------------------------------------------------------------------------------------------------- the proposed amendment of the Level 2 draft
def test_the_level2_draft_is_unchanged_and_the_proposed_amendment_adds_only_what_it_says_and_closes_no_gate():
    draft = json.loads((ROOT / "docs/level2/PROTOCOL_L2_DRAFT.json").read_text())
    prop = json.loads((ROOT / "docs/level2/PROTOCOL_L2_DRAFT.proposed.json").read_text())
    assert P.digest(draft) == L2_DIGEST and "freeze" not in draft  # the draft is as committed and is not frozen
    assert all(prop[k] == draft[k] for k in draft if k not in ("preregistration", "status"))
    added = set(prop["preregistration"]) - set(draft["preregistration"])
    assert added == {"known_incomparabilities", "numerical_environment"}
    assert {k: v for k, v in prop["preregistration"].items() if k in draft["preregistration"] and k != "analysis_plan"} == {
        k: v for k, v in draft["preregistration"].items() if k != "analysis_plan"
    }
    assert (
        prop["preregistration"]["analysis_plan"]["sensitivity"][:-1] == draft["preregistration"]["analysis_plan"]["sensitivity"]
    )
    assert prop["preregistration"]["numerical_environment"]["hierarchy_method"] == 1
    assert len(prop["preregistration"]["known_incomparabilities"]) >= 6 and any(
        "762" in x for x in prop["preregistration"]["known_incomparabilities"]
    )
    assert (
        P.validate(prop) == P.validate(draft) and len(P.validate(prop)) == 1 and "approval.high_cost" in P.validate(prop)[0]
    )  # the cost gate stays closed
    assert prop["approval"] == draft["approval"] and not prop["approval"]["high_cost"]
    assert P.preregistration_issues(prop) == [] and "freeze" not in prop
    audit = script("protocol_audit")
    assert audit.audit("draft", draft)["items"]["18 known incomparabilities declared in the protocol"] is False
    assert audit.audit("proposed", prop)["items"]["18 known incomparabilities declared in the protocol"] is True


def test_the_c3_power_limit_is_kept_in_the_draft_and_in_the_proposal():
    for f in ("PROTOCOL_L2_DRAFT.json", "PROTOCOL_L2_DRAFT.proposed.json"):
        d = json.loads((ROOT / "docs/level2" / f).read_text())
        assert d["planning"]["pairs_needed_for_80pct_power"]["C3 recursive vs random-matched"] == 762 and d["seeds"]["n"] == 200
        assert d["planning"]["underpowered"] == ["C3 recursive vs random-matched"]
