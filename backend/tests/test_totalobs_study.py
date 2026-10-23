"""The total-observation line inside the Study Engine and the API: protocol validation and fairness, a stored study (runs, analysis, Methods / Results, package),
replay of a stored run, re-execution of the whole study, the capability map, and the endpoints. Software checks on reserved functional seeds."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from xzr import lineage
from xzr.study import analysis, report, runner, templates
from xzr.study import protocol as P

NEW = ("total-observation", "autonomous-loop", "planetary-observation", "sss-axes")


@pytest.mark.parametrize("name", NEW)
def test_templates_validate_and_have_no_undeclared_differences(name):
    d = templates.template(name)
    assert P.validate(d) == [] and P.fairness_issues(d) == [] and d["mode"] == "functional"


def test_protocol_validation_refuses_what_the_line_cannot_run():
    d = templates.template("total-observation", n_seeds=2)
    d["arms"][0]["design"] = {"policy": "adaptive", "strong": ["rewrite-code"]}
    assert any("rewrite-code" in i or "unknown policy" in i for i in P.validate(d))
    d = templates.template("total-observation", n_seeds=2)
    d["arms"][1]["environment"] = {"world": {"rows": 40, "cols": 40}}
    assert any("regions" in i for i in P.validate(d))
    d = templates.template("total-observation", n_seeds=2)
    d["arms"][1]["environment"] = {"events": [{"gen": 1, "do": "format_disk"}]}
    assert any("event" in i for i in P.validate(d))
    d = templates.template("total-observation", n_seeds=2)
    d["arms"][1]["environment"] = {"secret": 1}
    assert any("outside" in i for i in P.validate(d))


def test_fairness_names_every_difference_and_flags_an_undeclared_one():
    d = templates.template("total-observation", n_seeds=2)
    f = P.fairness(d)
    c1 = next(c for c in f["contrasts"] if c["contrast"] == "C1")
    assert set(c1["declared"]) == {"policy", "revision_authority"} and c1["undeclared"] == []
    assert "information" in c1["equal_on"] and "compute" in c1["equal_on"]  # same information and compute in every arm
    d["contrasts"][0]["varies"] = ["policy"]  # forget to declare the authority difference
    assert P.fairness_issues(d)


def test_cost_gate_counts_the_loops_steps():
    d = templates.template("total-observation", n_seeds=2)
    base = P.step_runs(d)
    d["environment"]["generations"] = 20
    assert P.step_runs(d) > base


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    root = tmp_path_factory.mktemp("totalobs-study")
    d = templates.template("total-observation", n_seeds=3)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("fixed", "adaptive", "full")]
    d["contrasts"] = [c for c in d["contrasts"] if c["a"] in ("adaptive", "full") and c["b"] in ("fixed", "adaptive")]
    st = runner.Study.create(d, root)
    st.execute(procs=2)
    return st, root


def test_study_runs_analyses_and_reports(study):
    st, _ = study
    assert {r["status"] for r in st.runs()} == {"ok"} and len(st.runs()) == 9
    an = analysis.analyse(st)
    to = an["totalobs"]
    assert set(to["arms"]) == {"fixed", "adaptive", "full"} and "metric_registry" in to
    assert (
        to["arms"]["fixed"]["operations"] == {} and to["arms"]["full"]["operations"]
    )  # the fixed arm did nothing; the full arm's operations are counted with their status
    assert all(a["ontology_audit"]["runs_with_issues"] == 0 for a in to["arms"].values())
    assert an["nonredundancy"]["verdict"] != "established" and an["criteria"]["verdict"].startswith("no criteria")
    out = report.build(st, an)
    text = (st.path / "report" / "results.md").read_text()
    methods = (st.path / "report" / "methods.md").read_text()
    assert "Total observation records" in text and "earth_claim" not in methods  # (the claim lives in the planetary block)
    assert "not reality as a whole" in text and "Functional check" in text or "functional" in text.lower()
    assert "synthetic regional world" in methods and "verifier" in methods
    assert out["files"]


def test_numbers_in_the_text_match_the_stored_records(study):
    st, _ = study
    an = analysis.analyse(st)
    rows = {(r["arm"], r["index"]): r for r in st.runs()}
    for arm in ("fixed", "adaptive", "full"):
        stored = [
            rows[(arm, k)]["metrics"]["recall_final"] for k in range(3) if rows[(arm, k)]["metrics"]["recall_final"] is not None
        ]
        d = an["descriptives"][arm]["recall_final"]
        assert d["n"] == len(stored) and d["mean"] == pytest.approx(sum(stored) / len(stored), abs=1e-6)


def test_stored_run_replays_identically_and_the_whole_study_reproduces(study, tmp_path):
    st, _ = study
    for arm in ("adaptive", "full"):
        assert runner.replay_run(st, arm, 1)["agreement"] is True
    new, cmp = runner.reproduce(st, tmp_path, procs=2)
    assert cmp["identical_share"] == 1.0 and cmp["runs_compared"] == 9


def test_package_verifies_and_detects_tampering(study, tmp_path):
    import shutil

    st, _ = study
    report.package(st)
    assert report.verify(st.path)["ok"] is True
    copy = runner.copy_study(st, tmp_path / "copy")
    run_file = next((copy.path / "runs").rglob("*.json"))
    run_file.write_text(run_file.read_text().replace('"recall_final"', '"recall_finaI"', 1))  # alter a stored result
    assert report.verify(copy.path)["ok"] is False
    shutil.rmtree(copy.path)


def test_sss_effects_are_computed_from_a_complete_design(tmp_path):
    d = templates.template("sss-axes", n_seeds=2)
    assert len(d["arms"]) == 8 and all(a["sss"] for a in d["arms"])
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=2)
    an = analysis.analyse(st)
    sx = an["totalobs"]["sss"]
    assert sx["complete"] and set(sx["main"]) == {"scale", "size", "speed"} and "scalexsizexspeed" in sx["interaction"]
    d["arms"] = d["arms"][:6]  # a design with missing cells gives no effects
    from xzr.totalobs import summary

    assert summary.sss_effects(d, {a["name"]: 0.5 for a in d["arms"]})["complete"] is False


def test_planetary_template_reports_the_structural_conditions(tmp_path):
    d = templates.template("planetary-observation", n_seeds=1)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("distributed", "planetary-form")]
    d["contrasts"] = [c for c in d["contrasts"] if c["a"] == "planetary-form"]
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=1)
    an = analysis.analyse(st)
    pl = an["totalobs"]["planetary"]
    assert pl["planetary-form"]["all_met"] and not pl["distributed"]["all_met"] and pl["planetary-form"]["earth_claim"] is False


# ---------------------------------------------------------------------------------------------------- capability map
def test_capability_map_is_computed_from_evidence_not_from_names(monkeypatch):
    m = lineage.capability_map()
    by = {r["line"]: r for r in m["lines"]}
    assert by["ANESCIRE"]["status"] == "Unavailable"  # no implementation and no record exist
    assert by["Xenoscience"]["status"] == "Reference"
    for name in ("Total Observation", "Planetary-Scale Observation", "SSS (Scale / Size / Speed)"):
        assert by[name]["status"] == "Native"
    assert all(r["status"] in lineage.ORDER for r in m["lines"]) and sum(m["counts"].values()) == len(m["lines"])
    assert "not a module" in m["reality_as_a_whole"].lower()
    # remove the evidence of a native line: the status falls to Unavailable instead of keeping the name
    real = lineage._m
    monkeypatch.setattr(
        lineage,
        "_m",
        lambda mod: {"kind": "module", "target": mod, "exists": False} if mod.startswith("xzr.totalobs") else real(mod),
    )
    assert {r["line"]: r["status"] for r in lineage.capability_map()["lines"]}["Total Observation"] == "Unavailable"


# ---------------------------------------------------------------------------------------------------- endpoints
@pytest.fixture()
def http():
    from xzr.service import app as app_mod

    with TestClient(app_mod.app) as c:
        yield c


def test_endpoints_serve_the_capability_map_and_the_conditions(http):
    m = http.get("/api/studies/lineage").json()
    assert m["counts"] and any(r["line"] == "ANESCIRE" for r in m["lines"])
    env = {"world": {"rows": 12, "cols": 24, "span": 3}, "net": {"n_sensors": 4, "latency": 2, "pool": 24.0}}
    r = http.get("/api/studies/totalobs/conditions", params={"env": json.dumps(env)}).json()
    assert r["issues"] == [] and r["conditions"]["all_met"] and r["conditions"]["earth_claim"] is False
    bad = http.get("/api/studies/totalobs/conditions", params={"env": json.dumps({"world": {"rows": 99, "cols": 99}})}).json()
    assert bad["issues"] and bad["conditions"] is None
    tpl = http.get("/api/studies/templates").json()
    assert set(NEW) <= set(tpl)
    v = http.post("/api/studies/validate", json={"protocol": tpl["total-observation"]}).json()
    assert v["valid"] is True and json.dumps(v)  # strict JSON


# ---------------------------------------------------------------------------------------------------- confirmatory preparation (a draft, never run here)
def test_confirmatory_draft_is_complete_sized_from_exploration_and_cannot_be_created_without_the_approvals(tmp_path):
    d = templates.template("total-observation-confirmatory")
    assert d["mode"] == "confirmatory" and d["environment"]["rules_version"] == "v2" and d["status"].startswith("DRAFT")
    issues = P.validate(d)
    assert (
        len(issues) == 2 and any("confirmatory_run" in i for i in issues) and any("step-runs" in i for i in issues)
    )  # nothing else is missing
    assert not [i for i in P.preregistration_issues(d)] and P.fairness_issues(d) == []
    pl = d["planning"]
    assert d["seeds"]["n"] == max(pl["pairs_needed_for_80pct_power_at_alpha_0.025"].values()) and pl["underpowered"] == []
    gens = [g for g, _ in P.seed_list(d)]
    assert min(gens) >= 21000 and not set(gens) & {
        7000 + i for i in range(12)
    }  # fresh seeds, disjoint from the exploration that sized it
    prov = {p["derived_from"] for p in d["preregistration"]["condition_provenance"]}
    assert "exploration" in prov  # rules v2 was chosen after seeing earlier results, and the protocol says so
    with pytest.raises(P.ProtocolInvalid):
        runner.Study.create(d, tmp_path)  # refused: no study, no run
    d["approval"] = {
        "high_cost": {"who": "owner", "when": "2026-10-24"},
        "confirmatory_run": {"who": "owner", "when": "2026-10-24"},
    }
    assert P.validate(d) == []  # with the approvals recorded it would be a valid protocol (it is not created here)


def test_a_declared_execution_gate_is_enforced_only_when_declared():
    d = templates.template("total-observation", n_seeds=2)
    assert P.validate(d) == []
    d["approval"] = {"confirmatory_run": None}
    assert any("confirmatory_run" in i for i in P.validate(d))
    d["approval"] = {"confirmatory_run": {"who": "a", "when": "b"}}
    assert P.validate(d) == []
