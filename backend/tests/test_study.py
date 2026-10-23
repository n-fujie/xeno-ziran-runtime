"""Study layer: protocols, seed discipline, fairness, execution (inline and worker processes), safe stop, resume, timeouts,
amendments, analysis, reports, packaging, verification and reproduction."""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from xzr.hpo import experiments as X
from xzr.study import analysis, envs, report, runner, templates
from xzr.study import protocol as P


def quick(n=3, horizon=120, **kw):
    d = templates.template("quick", n_seeds=n, horizon=horizon)
    d.update(kw)
    return d


@pytest.fixture(scope="module")
def finished(tmp_path_factory):
    root = tmp_path_factory.mktemp("studies")
    st = runner.Study.create(quick(4), root)
    st.execute(procs=2)
    return st


# ------------------------------------------------------------------------------------------ protocol
def test_templates_validate_and_have_no_undeclared_differences():
    for name in templates.TEMPLATES:
        d = templates.template(name)
        assert P.validate(d) == [], name
        assert P.fairness_issues(d) == [], name


def test_protocol_digest_is_stable_and_ignores_amendments():
    d = quick()
    assert P.digest(d) == P.digest(copy.deepcopy(d))
    d2 = copy.deepcopy(d)
    d2["amendments"] = [{"x": 1}]
    assert P.digest(d2) == P.digest(d)
    d2["title"] = "other"
    assert P.digest(d2) != P.digest(d)


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda d: d.update(mode="nope"), "mode"),
        (lambda d: d["arms"][0].pop("description"), "description"),
        (lambda d: d["arms"][1].update(name=d["arms"][0]["name"]), "unique"),
        (lambda d: d["contrasts"][0].update(a="ghost"), "arms of this protocol"),
        (lambda d: d["arms"][1]["controller"].update(authority=["not.a.path"]), "outside the sandbox"),
        (lambda d: d["arms"][1].update(initial_changes=[{"path": "instruments.closure.level", "value": 99}]), "rejected"),
        (lambda d: d["stop"].update(timeout_per_run_s=0), "timeout"),
        (lambda d: d["metrics"].update(primary=[]), "primary"),
    ],
)
def test_invalid_protocols_are_refused_with_a_reason(mutate, needle):
    d = quick()
    mutate(d)
    issues = P.validate(d)
    assert issues and any(needle in i for i in issues), issues


def test_seed_discipline_by_mode():
    d = quick()
    d["mode"] = "exploratory"
    assert any("reserved functional" in i for i in P.validate(d))  # functional range cannot be reused as exploratory
    d["seeds"] = {"gen_base": 3000, "engine_base": 30000, "n": 3}  # a published HPO range
    assert any("overlap development or published" in i for i in P.validate(d))
    d["seeds"] = {"gen_base": 12000, "engine_base": 120000, "n": 3}
    assert P.validate(d) == []
    d["mode"] = "functional"
    assert any("reserved seed range" in i for i in P.validate(d))


def test_confirmatory_needs_declared_contrasts_and_criteria_and_registers_a_digest():
    d = templates.template("revision-study", n_seeds=4, mode="confirmatory", gen_base=12000, engine_base=120000)
    assert P.validate(d) == []
    frozen = P.freeze(d, "abc")
    assert frozen["freeze"]["digest"] == P.digest(d) and P.is_registered_unchanged(frozen)
    bad = copy.deepcopy(d)
    bad["contrasts"] = []
    bad["criteria"] = {"success": [], "failure": []}
    assert any("declare the contrasts" in i for i in P.validate(bad))


def test_fairness_flags_an_undeclared_difference():
    d = quick()
    d["contrasts"][0]["varies"] = []  # the arms do differ in controller and revision authority
    f = P.fairness(d)["contrasts"][0]
    assert set(f["undeclared"]) >= {"controller", "revision_authority"}
    assert P.fairness_issues(d)
    d["mode"] = "confirmatory"
    d["seeds"] = {"gen_base": 12000, "engine_base": 120000, "n": 4}
    with pytest.raises(P.ProtocolInvalid):
        P.freeze(d)


def test_high_cost_protocols_need_an_approval_record():
    d = quick(5000, 240)
    d["mode"] = "exploratory"
    d["seeds"] = {"gen_base": 12000, "engine_base": 120000, "n": 5000}
    assert any("approval.high_cost" in i for i in P.validate(d))
    d["approval"] = {"high_cost": True, "by": "researcher", "at": "2026-10-22"}
    assert P.validate(d) == []


def test_amendments_are_recorded_and_the_registered_digest_stays():
    d = templates.template("revision-study", n_seeds=4, mode="confirmatory", gen_base=12000, engine_base=120000)
    frozen = P.freeze(d)
    a = P.amend(frozen, "stop.timeout_per_run_s", 120, "runs are fast", runs_started=False)
    assert a["amendments"][0]["status"] == "pre-registered change" and a["freeze"]["digest"] == frozen["freeze"]["digest"]
    assert P.digest(a) != frozen["freeze"]["digest"] and not P.is_registered_unchanged(a)
    b = P.amend(a, "metrics.primary", ["ignitions"], "changed my mind", runs_started=True)
    assert b["amendments"][-1]["status"] == "exploratory"
    with pytest.raises(P.ProtocolInvalid):
        P.amend(a, "stop.timeout_per_run_s", 1, "  ", runs_started=False)


# ------------------------------------------------------------------------------------------ execution
def test_fixed_arm_equals_the_hpo_layers_own_run(tmp_path):
    """The study runner adds no behaviour: a static D arm gives the metrics hpo.experiments.run_one gives for the same seed."""
    d = quick(1, 120)
    rec = envs.run_one(d, "fixed", 7000, 70000)
    base = X._warm({"n": 800, "regime": "intermittent"}, 7000, 70000, 40)
    from xzr.hpo.field import Field
    from xzr.hpo.metrics import measure

    ref = base.fork().track_rng()
    for _ in range(120):
        ref.step()
    f = Field(base.fork().track_rng(), X.settings_for("D", {"warmup": 40, "horizon": 120}), 70000, keep_states=False)
    f.run(120)
    want = measure(f, ref)
    for k in ("fired_samples", "ignitions", "field_ignitions", "reinsertions", "unobservable_samples", "causal_depth"):
        assert rec["metrics"][k] == pytest.approx(want[k]), k


def test_run_is_deterministic():
    d = quick(1, 120)
    a, b = envs.run_one(d, "recursive", 7000, 70000), envs.run_one(d, "recursive", 7000, 70000)
    for r in (a, b):
        for k in ("wall_s", "cpu_s", "peak_rss_mb"):
            r.pop(k)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_finished_study_has_every_record(finished):
    s = finished.status()
    assert s["state"] == "finished" and s["n_ok"] == 8 and s["n_failed"] == 0
    names = {p.name for p in finished.path.iterdir()}
    assert {"protocol.json", "protocol.registered.json", "manifest.json", "status.json", "log.jsonl", "runs"} <= names
    m = finished.manifest()
    assert m["environment"]["git_commit"] and m["environment"]["dependencies"]["numpy"] and m["protocol_digest"]
    for r in finished.runs():
        assert r["experiment_id"] == finished.id and r["protocol_digest"] == m["protocol_digest"] and r["status"] == "ok"
    assert any(e["event"] == "run_ok" for e in finished.log_lines())


def test_resume_runs_only_what_is_missing(tmp_path):
    st = runner.Study.create(quick(3), tmp_path)
    st.execute(inline=True)
    victim = st.run_files()[0]
    victim.unlink()
    assert len(st.pending()) == 1
    before = {p.name: p.read_text() for p in st.run_files()}
    st.execute(inline=True)
    assert len(st.run_files()) == 6
    assert all(p.read_text() == before[p.name] for p in st.run_files() if p.name in before)  # untouched


def test_stop_request_stops_cleanly_and_resume_completes(tmp_path):
    st = runner.Study.create(quick(4), tmp_path)
    st.stop()
    (st.path / "stop.flag").write_text("x")  # a request made while the run is starting is honoured
    orig = st._stopping
    calls = {"n": 0}

    def stopping():
        calls["n"] += 1
        return calls["n"] > 2

    st._stopping = stopping  # type: ignore[method-assign]
    st.execute(inline=True)
    assert st.status()["state"] == "stopped" and 0 < len(st.run_files()) < 8
    st._stopping = orig  # type: ignore[method-assign]
    st.execute(inline=True)
    assert st.status()["state"] == "finished" and len(st.run_files()) == 8


def test_failing_runs_are_recorded_and_stop_the_study_safely(tmp_path):
    d = quick(4)
    d["arms"][1]["settings"] = {"horizon": 120}  # valid, but we break the run below through the adapter
    st = runner.Study.create(d, tmp_path)
    orig = envs.RUNNERS["hpo-world"]

    def boom(doc, arm, g, e):
        if arm["name"] == "recursive":
            raise RuntimeError("synthetic failure")
        return orig(doc, arm, g, e)

    envs.RUNNERS["hpo-world"] = boom
    try:
        st.execute(inline=True)
    finally:
        envs.RUNNERS["hpo-world"] = orig
    s = st.status()
    assert s["state"] == "stopped" and "failures" in s["stop_reason"]
    failed = [r for r in st.runs() if r["status"] == "failed"]
    assert len(failed) == 3 and "synthetic failure" in failed[0]["error"]
    a = analysis.analyse(st)
    assert a["accounting"]["recursive"]["failed"] == 3 and a["accounting"]["recursive"]["failure_rate"] > 0


def test_timeout_is_recorded_in_worker_processes(tmp_path):
    d = quick(2, 240)
    d["stop"]["timeout_per_run_s"] = 0.05
    d["stop"]["max_failures"] = 2
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=1)
    assert {r["status"] for r in st.runs()} <= {"timeout", "failed"} and st.runs()
    assert st.status()["state"] == "stopped"


def test_wall_clock_budget_stops_the_study(tmp_path):
    d = quick(4)
    d["stop"]["max_wall_seconds"] = 0.001
    st = runner.Study.create(d, tmp_path)
    st.execute(inline=True)
    assert st.status()["state"] == "stopped" and "wall-clock" in st.status()["stop_reason"]


def test_amend_after_runs_started_is_labelled_exploratory(tmp_path):
    st = runner.Study.create(quick(2), tmp_path)
    st.execute(inline=True)
    rec = st.amend("metrics.secondary", ["ignitions"], "restrict the secondary metrics after seeing the runs")
    assert rec["runs_started"] and rec["status"] == "exploratory"
    assert st.amendments() == [rec] and st.registered()["metrics"] != st.protocol()["metrics"]


# ------------------------------------------------------------------------------------------ analysis
def test_analysis_reports_every_contrast_and_metric(finished):
    a = analysis.analyse(finished)
    assert a["label"].startswith("FUNCTIONAL") and a["n_seeds"] == 4
    c = a["contrasts"][0]
    assert set(c["metrics"]) == set(a["metrics"]) and c["evidence"].startswith("functional check")
    r = c["metrics"]["fired_samples"]
    for k in ("n", "mean", "sd", "dz", "ci95", "p", "p_holm", "p_bh", "status", "independent", "sensitivity"):
        assert k in r
    assert r["n"] == 4 and 0 < r["p"] <= 1 and r["p_holm"] >= r["p"] - 1e-12 and r["p_bh"] <= r["p_holm"] + 1e-12
    d = a["descriptives"]["fixed"]["fired_samples"]
    assert d["n"] == 4 and d["min"] <= d["median"] <= d["max"] and d["sd"] >= 0
    assert "scope" in a["criteria"] and "not a statement about any theory" in a["criteria"]["scope"]


def test_analysis_statistics_match_independent_calculation(finished):
    a = analysis.analyse(finished, write=False)
    runs = {(r["arm"], r["index"]): r["metrics"]["fired_samples"] for r in finished.runs()}
    x = np.array([runs[("recursive", k)] for k in range(4)], float)
    y = np.array([runs[("fixed", k)] for k in range(4)], float)
    d = x - y
    r = a["contrasts"][0]["metrics"]["fired_samples"]
    assert r["mean"] == pytest.approx(d.mean()) and r["sd"] == pytest.approx(d.std(ddof=1))
    assert r["dz"] == pytest.approx(d.mean() / d.std(ddof=1))
    assert r["independent"]["hedges_g"] is not None


def test_undefined_values_are_not_zeros():
    x = np.array([1.0, math.nan, 3.0])
    d = analysis.describe(x, np.random.default_rng(0))
    assert d["n"] == 2 and d["undefined"] == 1 and d["mean"] == 2.0


def test_outliers_are_listed_and_kept():
    x = np.array([10, 11, 10, 12, 11, 10, 11, 100.0])
    assert [o["index"] for o in analysis.outliers(x)] == [7]


def test_multiplicity_corrections():
    ps = {"a": 0.01, "b": 0.02, "c": 0.5}
    bh = analysis._bh(ps)
    assert bh["a"] == pytest.approx(0.03) and bh["b"] == pytest.approx(0.03) and bh["c"] == pytest.approx(0.5)


def test_criteria_use_effect_and_interval_not_p_alone():
    res = {"n": 10, "mean": 5.0, "scale": 100.0, "ci95": [1.0, 9.0]}
    ok = analysis._criterion({"direction": "greater", "min_relative_effect": 0.02, "ci_excludes_zero": True}, res)
    small = analysis._criterion({"direction": "greater", "min_relative_effect": 0.10, "ci_excludes_zero": True}, res)
    wide = analysis._criterion(
        {"direction": "greater", "min_relative_effect": 0.02, "ci_excludes_zero": True}, {**res, "ci95": [-1.0, 11.0]}
    )
    assert ok["result"] == "met" and small["result"] == "not met" and wide["result"] == "not met"
    assert analysis._criterion({"direction": "greater"}, None)["result"] == "not evaluable"


def test_ziran_records_are_aggregated_from_the_runs(finished):
    z = analysis.analyse(finished, write=False)["ziran"]
    assert z["recursive"]["observation_changes"]["controller"] > 0
    assert "history_reentry" in z["recursive"] and z["recursive"]["history_reentry"]["reinsertions"] > 0
    assert z["fixed"]["observation_changes"]["controller"] == 0


def test_revision_study_records_reachability_and_checks_it_against_what_the_operations_did(tmp_path):
    d = templates.template("revision-study", n_seeds=3, horizon=240)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("recursive", "observation-narrowed", "random-matched")]
    d["contrasts"] = [c for c in d["contrasts"] if {c["a"], c["b"]} <= {a["name"] for a in d["arms"]}]
    d["hypotheses"] = []
    d["criteria"] = {"success": [], "failure": []}
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=2)
    z = analysis.analyse(st, write=False)["ziran"]
    narrowed = z["observation-narrowed"]
    assert narrowed["observation_changes"]["protocol"] > 0  # the imposed observation change is recorded as a protocol change
    r = narrowed["reachability"]
    assert r["closed_predictions"] > 0 and r["closed_consistency_rate"] is not None
    assert r["opened_predictions"] >= r["opened_then_acted"]  # opening is not success: the two are counted separately
    rm = z["random-matched"]["observation_changes"]
    assert rm["controller"] == z["recursive"]["observation_changes"]["controller"]  # matched change budget per seed


def test_authority_and_change_budget_reject_and_record(tmp_path):
    d = quick(2, 240)
    arm = d["arms"][1]
    arm["controller"].update(authority=["allocation.*"], max_changes_per_epoch=1)
    st = runner.Study.create(d, tmp_path)
    st.execute(inline=True)
    rs = [r for r in st.runs() if r["arm"] == "recursive"]
    ch = [c for r in rs for c in r["controller_changes"]]
    assert all(c["path"].startswith("allocation.") for c in ch)
    assert any(
        "outside this controller's revision authority" in x["error"] or "over the change budget" in x["error"]
        for r in rs
        for x in r["controller"]["rejected"]
    )


def test_shape_detection_separates_record_detector_and_interpretation(tmp_path):
    d = quick(1, 120)
    d["environment"]["detect_shapes"] = True
    rec = envs.run_one(d, "recursive", 7000, 70000)
    sd = rec["shape_detection"]
    assert sd["interpretation"] is None and "does not interpret" in sd["detector_limits"]
    assert sd["transition_record"]["steps"] > 0 and sd["detector_output"]


# ------------------------------------------------------------------------------------------ outputs
def test_report_package_verify_and_reproduce(finished, tmp_path):
    an = analysis.analyse(finished)
    idx = report.build(finished, an)
    rep = finished.path / "report"
    assert {
        "methods.md",
        "results.md",
        "runs.csv",
        "descriptives.csv",
        "contrasts.csv",
        "accounting.csv",
        "ziran.csv",
        "figures.json",
    } <= set(idx["files"])
    methods = (rep / "methods.md").read_text()
    for needle in (
        finished.id,
        finished.manifest()["protocol_digest"],
        "Seeds and sample",
        "Software and environment",
        "FUNCTIONAL CHECK",
    ):
        assert needle in methods
    results = (rep / "results.md").read_text()
    assert "Interpretation boundary" in results and ("IDENTICAL" in results or "UNRESOLVED" in results)
    assert all(f["experiment_id"] == finished.id for f in idx["figures"]) and idx["figures"]
    svg = (rep / idx["figures"][0]["file"]).read_text()
    assert svg.startswith("<svg") and "</svg>" in svg and finished.id in svg
    import csv

    rows = list(csv.DictReader((rep / "runs.csv").open()))
    assert len(rows) == 8 and {"arm", "gen", "seed", "fired_samples"} <= set(rows[0])

    z = report.package(finished)
    assert z.exists()
    assert report.verify(finished.path)["ok"]
    copy = runner.copy_study(finished, tmp_path / "tampered")  # tamper with a copy: the fixture is shared by later tests
    (copy.path / "runs" / copy.run_files()[0].name).write_text("{}")
    assert not report.verify(copy.path)["ok"] and report.verify(finished.path)["ok"]


def test_reproduction_matches_run_for_run(tmp_path):
    src = runner.Study.create(quick(3), tmp_path / "a")
    src.execute(procs=2)
    new, cmp = runner.reproduce(src, tmp_path / "b", procs=2)
    assert cmp["identical_share"] == 1.0 and not cmp["differing"] and not cmp["missing"]
    assert new.manifest()["reproduces"] == src.id and (new.path / "reproduction.json").exists()


def test_cli_end_to_end(tmp_path):
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1]), "PATH": "/usr/bin:/bin"}

    def run(*a):
        return subprocess.run([sys.executable, "-m", "xzr.study", *a], capture_output=True, text=True, env=env, check=False)

    p = tmp_path / "p.json"
    assert run("new", "quick", "--out", str(p), "--seeds", "2").returncode == 0
    assert run("validate", str(p)).returncode == 0
    created = run("create", str(p), "--root", str(tmp_path))
    study = created.stdout.strip()
    assert Path(study, "protocol.json").exists()
    assert run("run", study, "--procs", "2").returncode == 0
    assert run("report", study).returncode == 0
    assert run("package", study).returncode == 0
    assert run("verify", study).returncode == 0
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "x"}))
    assert run("validate", str(bad)).returncode == 1


def test_lab_population_environment_runs(tmp_path):
    pytest.importorskip("mujoco")
    st = runner.Study.create(templates.template("lab-population", n_seeds=2, sizes=(3, 12)), tmp_path)
    st.execute(procs=2)
    assert st.status()["state"] == "finished"
    a = analysis.analyse(st, write=False)
    assert a["contrasts"][0]["metrics"]["requests"]["n"] == 2
    assert all(r["population"]["n"] in (3, 12) for r in st.runs())


# ------------------------------------------------------------------------------------------ performance measurements
def test_performance_measurements_report_their_conditions(tmp_path):
    from xzr.study import perf

    par = perf.parallel(tmp_path / "p", (1, 2), n_seeds=2, horizon=120)
    assert [r["procs"] for r in par["rows"]] == [1, 2] and par["rows"][0]["speedup"] == 1.0
    assert all(r["failure_rate"] == 0 and r["ok"] == r["runs"] == 4 and r["peak_run_rss_mb"] for r in par["rows"])
    sr = perf.storage_and_replay(tmp_path / "s", n_seeds=2, horizon=120)
    assert sr["verify_ok"] and sr["replay"]["agreement_rate"] == 1.0 and sr["bytes_per_run"] > 0
    hl = perf.history_load(tmp_path / "h", n_seeds=1, horizon=120)
    assert hl["mean_reinsertions"]["recursive"] > 0 == hl["mean_reinsertions"]["no-history"]


# ------------------------------------------------------------------------------------------ confirmatory discipline
def _confirmatory(n=3):
    d = quick(n, 120)
    d["mode"] = "confirmatory"
    d["seeds"] = {"gen_base": 12000, "engine_base": 120000, "n": n}
    return d


def test_confirmatory_study_is_registered_before_the_first_run_and_labelled_as_such(tmp_path):
    st = runner.Study.create(_confirmatory(), tmp_path)
    reg = st.registered()
    assert reg["freeze"]["digest"] == P.digest(reg) and not st.runs_started()
    st.execute(procs=2)
    a = analysis.analyse(st)
    assert a["mode"] == "confirmatory" and a["contrasts"][0]["evidence"] == "confirmatory"
    # a change made after the first run is recorded, and the affected contrast is no longer reported as confirmatory
    st.amend("metrics.secondary", ["ignitions"], "dropped secondary metrics after seeing the runs")
    again = analysis.analyse(st)
    assert again["contrasts"][0]["evidence"].startswith("exploratory")
    assert again["amendments"][0]["status"] == "exploratory" and st.registered()["freeze"]["digest"] == reg["freeze"]["digest"]


def test_confirmatory_run_is_refused_if_the_registered_protocol_was_altered(tmp_path):
    st = runner.Study.create(_confirmatory(), tmp_path)
    reg = st.registered()
    reg["title"] = "edited after registration"
    (st.path / "protocol.registered.json").write_text(json.dumps(reg))
    with pytest.raises(P.ProtocolInvalid):
        st.execute(inline=True)


def test_report_and_figures_survive_a_single_seed_where_intervals_are_undefined(tmp_path):
    d = quick(1, 120)
    d["contrasts"], d["criteria"], d["hypotheses"] = [], {"success": [], "failure": []}, []
    st = runner.Study.create(d, tmp_path)
    st.execute(inline=True)
    idx = report.build(st, analysis.analyse(st))
    assert idx["figures"] and (st.path / "report" / "methods.md").exists()


# ------------------------------------------------------------------------------------------ small samples: undefined stays undefined
def _small_study(tmp_path, n, fail=False):
    d = quick(max(n, 1), 120)
    d["contrasts"], d["criteria"], d["hypotheses"] = (
        [d["contrasts"][0]],
        {"success": [d["criteria"]["success"][0]], "failure": []},
        [],
    )
    d["seeds"] = {"gen_base": 7000, "engine_base": 70000, "n": max(n, 1)}
    st = runner.Study.create(d, tmp_path)
    if fail:
        orig = envs.RUNNERS["hpo-world"]
        envs.RUNNERS["hpo-world"] = lambda *a: (_ for _ in ()).throw(RuntimeError("synthetic"))
        try:
            d["stop"]["max_failures"] = 99
            st.execute(inline=True)
        finally:
            envs.RUNNERS["hpo-world"] = orig
    else:
        st.execute(inline=True)
    return st


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_every_sample_size_analyses_reports_and_serialises_without_inventing_numbers(tmp_path, n):
    st = _small_study(tmp_path, n, fail=(n == 0))
    a = analysis.analyse(st)  # strict JSON: allow_nan=False inside analyse()
    c = a["contrasts"][0]["metrics"]["fired_samples"]
    d = a["descriptives"]["fixed"]["fired_samples"]
    idx = report.build(st, a)
    assert (st.path / "report" / "results.md").exists() and (st.path / "report" / "methods.md").exists()
    assert c["n"] == n and d["n"] == n
    if n == 0:
        assert c["status"] == "NOT MEASURED" and "mean" not in d and a["accounting"]["fixed"]["failed"] == 1
        assert a["criteria"]["verdict"].startswith("not evaluable") and not idx["figures"]
    elif n == 1:
        assert (
            c["status"] == "INSUFFICIENT DATA"
            and c["sd"] is None
            and c["dz"] is None
            and c["p"] is None
            and c["ci95"] == [None, None]
        )
        assert c["p_holm"] is None and c["p_bh"] is None  # no test was possible: not p = 1, not significant
        assert d["sd"] is None and d["var"] is None and d["ci95_mean"] == [None, None]
        assert a["criteria"]["verdict"].startswith("not evaluable")
        assert "not estimable" in c["insufficient"] and isinstance(c["mean"], float)  # the single difference itself is a number
    else:
        assert c["sd"] is not None and c["p"] is not None and c["ci95"][0] is not None and d["sd"] is not None
        assert c["insufficient"] is None
        if n == 2:  # two pairs: defined, but the interval rests on two values and the verdict says so
            assert "fewer than 8 pairs" in a["criteria"]["verdict"] or a["criteria"]["verdict"].startswith("not evaluable")


def test_missing_values_and_a_zero_effect_are_different(tmp_path):
    safe = analysis.paired_safe
    rng = np.random.default_rng(0)
    nan = float("nan")
    zero = safe(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), rng)
    assert zero["identical"] and zero["mean"] == 0.0 and zero["n"] == 3  # a real zero effect
    missing = safe(np.array([1.0, nan, nan]), np.array([1.0, 2.0, nan]), rng)
    assert (
        missing["n"] == 1 and missing["mean"] == 0.0 and missing["insufficient"]
    )  # one pair: its difference is 0, but nothing else is estimable
    none = safe(np.array([nan, nan]), np.array([1.0, 2.0]), rng)
    assert none["n"] == 0 and "mean" not in none and none["undefined_pairs"] == 2
    one = analysis.describe(np.array([5.0]), rng)
    assert (
        one["mean"] == 5.0
        and one["sd"] is None
        and one["var"] is None
        and one["ci95_mean"][0] is None
        or one["ci95_mean"][0] != one["ci95_mean"][0]
    )


# ------------------------------------------------------------------------------------------ failure, exhaustion, stop (Scenario F)
def test_scarcity_study_records_revision_exhaustion_blindness_and_stop(tmp_path):
    d = templates.template("scarcity-study", n_seeds=2, horizon=600)
    keep = {"fixed-moderate", "recursive-meta-severe", "recursive-meta-none", "recursive-meta-abundant"}
    d["arms"] = [a for a in d["arms"] if a["name"] in keep]
    d["contrasts"] = [c for c in d["contrasts"] if {c["a"], c["b"]} <= keep]
    d["hypotheses"] = []
    assert P.validate(d) == [] and P.fairness_issues(d) == []
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=3)
    a = analysis.analyse(st)
    desc = {
        arm: {
            m: a["descriptives"][arm][m].get("mean")
            for m in ("fired_samples", "meta_revisions", "meta_exhausted", "stopped_early")
        }
        for arm in a["arms"]
    }
    assert desc["recursive-meta-none"]["fired_samples"] == 0.0  # no resources: every measurement fails, nothing ignites
    assert (
        desc["recursive-meta-severe"]["meta_revisions"] >= 2 and desc["recursive-meta-severe"]["meta_exhausted"] >= 1
    )  # failing rules revised, then exhausted
    assert (
        desc["recursive-meta-abundant"]["fired_samples"] > desc["recursive-meta-severe"]["fired_samples"]
    )  # scarcity costs what the operations can do
    assert desc["fixed-moderate"]["stopped_early"] is not None and desc["fixed-moderate"]["meta_revisions"] == 0
    z = a["ziran"]["recursive-meta-severe"]["meta_revision"]
    assert z["exhausted_rules"] >= 1 and z["runs_with_a_revision"] == 2
    run = next(r for r in st.runs() if r["arm"] == "recursive-meta-severe")
    assert any(m["revision"] == "exhausted" for m in run["controller"]["meta_trace"])  # the record names what was exhausted
    # the revision reached the next decisions: the allocation changes made after a revision use the revised step
    steps = [m["to"] for m in run["controller"]["meta_trace"] if m["revision"] == "parameter" and m["param"] == "alloc_step"]
    assert steps == sorted(steps) and steps[0] > 1.5


# ------------------------------------------------------------------------------------------ generated text and numbers
FORBIDDEN = (
    "prove",
    "proof",
    "demonstrat",
    "confirms the theory",
    "validates the theory",
    "superior",
    "outperform",
    "breakthrough",
    "novel",
    "first to",
)


def test_generated_text_makes_no_claim_the_experiment_cannot_support(finished):
    an = analysis.analyse(finished)
    report.build(finished, an)
    rep = finished.path / "report"
    for name in ("methods.md", "results.md"):
        text = (rep / name).read_text().lower()
        assert not [w for w in FORBIDDEN if w in text], (name, [w for w in FORBIDDEN if w in text])
    results = (rep / "results.md").read_text()
    assert (
        "FUNCTIONAL CHECK" in results and "Interpretation boundary" in results and "not a statement about any theory" in results
    )
    # every verdict line is about the declared criteria; no sentence interprets an effect as support for a proposition
    assert "supports" not in results.lower() and "theory" not in results.lower().replace(
        "not a statement about any theory", ""
    ).replace("theoretical proposition", "")


def test_numbers_in_the_outputs_equal_the_stored_run_logs(finished):
    import csv

    an = analysis.analyse(finished)
    report.build(finished, an)
    rep = finished.path / "report"
    runs = list(csv.DictReader((rep / "runs.csv").open()))
    stored = {(r["arm"], r["index"]): r for r in finished.runs()}
    for row in runs:
        s = stored[(row["arm"], int(row["index"]))]
        assert int(row["seed"]) == s["seed"] and float(row["fired_samples"]) == s["metrics"]["fired_samples"]
    for row in csv.DictReader((rep / "descriptives.csv").open()):
        vals = (
            [float(r["fired_samples"]) for r in runs if r["arm"] == row["arm"] and r["status"] == "ok"]
            if row["metric"] == "fired_samples"
            else None
        )
        if vals:
            assert float(row["mean"]) == pytest.approx(sum(vals) / len(vals)) and int(row["n"]) == len(vals)
    c1 = next(r for r in csv.DictReader((rep / "contrasts.csv").open()) if r["metric"] == "fired_samples")
    a = [float(r["fired_samples"]) for r in runs if r["arm"] == c1["a"]]
    b = [float(r["fired_samples"]) for r in runs if r["arm"] == c1["b"]]
    assert float(c1["mean_diff"]) == pytest.approx(sum(x - y for x, y in zip(a, b, strict=True)) / len(a))
    assert f"{float(c1['mean_diff']):.3g}" in (rep / "results.md").read_text()  # the formatted table carries the same number


def test_meta_revision_followup_tracks_evidence_reflection_cost_and_both_directions(tmp_path):
    d = templates.template("scarcity-study", n_seeds=3, horizon=600)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("recursive-moderate", "recursive-meta-moderate")]
    d["contrasts"] = [
        {"id": "C1", "a": "recursive-meta-moderate", "b": "recursive-moderate", "varies": ["meta_revision"], "role": "primary"}
    ]
    d["hypotheses"] = []
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=2)
    a = analysis.analyse(st)
    (m,) = a["meta_followup"]
    assert m["pairs"] == 3 and m["improved"] + m["worsened"] + m["unchanged"] == 3 and "no direction is assumed" in m["note"]
    revised = [r for r in m["rows"] if r["revisions"]]
    assert revised and all(r["evidence_recorded"] for r in m["rows"])
    assert any(
        r["changes_using_revised_rules"] > 0 for r in revised
    )  # later decisions were made under the revised rule parameters
    assert all(r["changes_using_revised_rules"] == 0 for r in m["rows"] if not r["revisions"])  # no revision, nothing to reflect
    run = next(r for r in st.runs() if r["arm"] == "recursive-meta-moderate" and r["controller"]["meta_trace"])
    rev = run["controller"]["meta_trace"][0]
    assert (
        rev["before"]["params"] != rev["after"]["params"]
        and rev["evidence"]
        and {"kind", "reason", "epoch"} <= set(rev["evidence"][0])
    )
    assert all(
        "measure_cost" in r["metrics"] and r["metrics"]["measure_cost"] <= r["metrics"]["measure_budget"] for r in st.runs()
    )


# ------------------------------------------------------------------------------------------ non-redundancy is never presumed
def _fake_analysis(mode, status, evidence, ci=(0.4, 0.6), mean=0.5, scale=10.0):
    return {
        "experiment_id": "S0",
        "mode": mode,
        "metrics": ["unseen_coverage"],
        "contrasts": [
            {
                "id": "C1",
                "a": "pa",
                "b": "existing",
                "evidence": evidence,
                "metrics": {"unseen_coverage": {"n": 8, "mean": mean, "ci95": list(ci), "scale": scale, "status": status}},
            }
        ],
    }


def test_non_redundancy_defaults_to_not_established_and_needs_an_independent_confirmatory_comparison():
    from xzr.study import nonredundancy as N

    f = N.assess(_fake_analysis("functional", "DETECTED", "functional check (not evidence)"))
    assert f["verdict"].startswith("not evaluated") and f["unestablished_by_default"]
    e = N.assess(_fake_analysis("exploratory", "DETECTED", "exploratory"))
    assert e["verdict"].startswith("not evaluated")
    c = N.assess(_fake_analysis("confirmatory", "DETECTED", "confirmatory"))
    assert c["verdict"].startswith("established on at least one comparable axis")
    n = N.assess(_fake_analysis("confirmatory", "UNRESOLVED", "confirmatory", ci=(-5, 5)))
    assert n["verdict"].startswith("not established")
    eq = N.assess(_fake_analysis("confirmatory", "EQUIVALENT", "confirmatory", ci=(-0.1, 0.1)))
    assert eq["verdict"].startswith("equivalent")
    late = N.assess(_fake_analysis("confirmatory", "DETECTED", "exploratory (declared after the first run or not registered)"))
    assert not late["verdict"].startswith("established")  # a contrast declared after the data is exploratory


def test_non_redundancy_names_incomparable_axes_and_what_the_environment_cannot_evaluate():
    from xzr.study import nonredundancy as N

    a = N.assess(_fake_analysis("functional", "UNRESOLVED", "functional check (not evidence)"))
    comp = {x["axis"]: x["comparable"] for x in a["axes"]}
    assert comp["observability"] and comp["reachability"]
    assert not comp["prediction"] and not comp["action on reality"] and not comp["intervention"]
    assert any("human-readability" in x for x in a["not_evaluable_by_this_environment"])


def test_every_analysis_carries_the_assessment_and_the_results_text_states_it_is_not_a_finding(finished):
    an = analysis.analyse(finished)
    assert an["nonredundancy"]["verdict"].startswith("not evaluated")
    report.build(finished, an)
    text = (finished.path / "report" / "results.md").read_text()
    assert (
        "Operational non-redundancy (assessment, not a finding)" in text
        and "never inferred from the existence of revision" in text
    )
