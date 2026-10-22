"""Measurements of a population of research systems (lab/multisystem.py): the ten properties, each checked against a
control that lacks the property, the stop / start harness operations, determinism.
Checks of the measurements, not claims about autonomy."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("mujoco")

from xzr.lab import multisystem as M  # noqa: E402
from xzr.lab.population import population  # noqa: E402
from xzr.lab.record import LabRun  # noqa: E402

GEN, SEED, STEPS = 8000, 80000, 100
BASE = {"name": "b", "population": {"n": 20}}


def arm(**scn):
    return {**BASE, "scenario": scn}


def run(a, steps=STEPS):
    return M.run(a, GEN, SEED, steps)["metrics"]


@pytest.fixture(scope="module")
def baseline():
    return run(BASE)


def test_diverse_populations_have_different_periods_windows_and_are_deterministic():
    d = population(20, diverse=True)
    assert len({s["period"] for s in d}) == 4 and len({s["window"] for s in d}) == 3
    assert population(20, diverse=True) == d and "period" not in population(20)[0]  # the default population is unchanged
    assert json.dumps(run(BASE), sort_keys=True) == json.dumps(run(BASE), sort_keys=True)


def test_independent_histories_different_conditions_and_asynchronous_activity(baseline):
    assert (
        baseline["history_overlap_mean"] is not None and baseline["history_overlap_mean"] < 0.5
    )  # systems ran mostly different experiments
    assert baseline["distinct_conditions"] > 10 and baseline["distinct_boundaries"] > 3
    assert baseline["first_request_spread"] > 0 and baseline["simultaneity"] < 0.5  # not in lockstep
    lock = run({"name": "lock", "population": {"n": 20, "diverse": False}})
    assert lock["first_request_spread"] == 0  # the control without diversity starts all at once: the measure sees the difference


def test_stop_and_start_harness_operations():
    cfg = M.build_config(arm(stop={"fraction": 0.3, "at": 30}), GEN, SEED, STEPS)
    stops = [h for h in cfg["harness"] if h["do"] == "stop_system"]
    assert len(stops) == 6 and all(h["at"] == 30 for h in stops)
    r = LabRun(cfg)
    victim = stops[0]["system"]
    at_stop = None
    for t in range(60):
        r.step()
        if t == 30:
            at_stop = r.science.systems[victim].stats["requests"]
    assert victim in r.science.stopped and r.science.systems[victim].stats["requests"] == at_stop  # no request after the stop
    assert r.record()["summary"][victim]["requests"] == at_stop and r.science.state()[victim].get("stopped")
    with pytest.raises(ValueError):
        LabRun({**cfg, "harness": [{"at": 1, "do": "stop_system", "system": "NOPE"}]}).step()


def test_partial_stop_does_not_stop_the_others(baseline):
    s = run(arm(stop={"fraction": 0.3, "at": 50}))
    assert s["stopped_systems"] == 6 and s["stop_applied"] == 1.0 and baseline["stop_applied"] == 0.0
    assert s["rate_after_stop"] > 0  # the running systems kept requesting


def test_exchange_and_inheritance_are_reads_of_another_systems_results(baseline):
    ex = run(arm(exchange={"fraction": 0.6}))
    assert baseline["exchange_reads"] == 0 and ex["exchange_reads"] > 0 and ex["exchange_systems"] > 0
    cfg = M.build_config(arm(inherit={"start_at": 50}), GEN, SEED, STEPS)
    succ = next(h["system"] for h in cfg["harness"] if h["do"] == "start_system")
    r = LabRun(cfg)
    for _ in range(49):
        r.step()
    assert (
        succ in r.science.stopped and r.science.systems[succ].stats["requests"] == 0
    )  # the successor has not acted before it starts
    inh = run(arm(inherit={"start_at": 50}))
    assert (
        inh["exchange_systems"] == 1 and inh["exchange_reads"] > 0
    )  # the successor read the predecessor's store after it started


def test_expansion_and_shrinking_of_what_can_be_investigated(baseline):
    v = run(arm(harness=[{"at": 25, "do": "close_view", "system": "S000"}, {"at": 75, "do": "open_view", "system": "S000"}]))
    assert v["coverage_shrinks"] > baseline["coverage_shrinks"] and v["coverage_expansions"] > baseline["coverage_expansions"]
    assert v["external_coverage_drops"] >= baseline["external_coverage_drops"]


def test_resource_competition_grows_with_the_number_of_systems(baseline):
    many = run({"name": "many", "population": {"n": 100}})
    assert many["requests"] > baseline["requests"] and many["contention_rate"] >= baseline["contention_rate"]
    assert many["denied"] + many["failed"] > baseline["denied"] + baseline["failed"]


def test_study_environment_uses_the_measurements(tmp_path):
    from xzr.study import runner, templates

    d = templates.template("multi-system", n_seeds=2, n=10, horizon=60)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("baseline", "stop-30pct")]
    d["contrasts"] = [c for c in d["contrasts"] if c["a"] == "stop-30pct"]
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=2)
    assert {r["status"] for r in st.runs()} == {"ok"} and all("distinct_conditions" in r["metrics"] for r in st.runs())
    assert any(r["metrics"]["stopped_systems"] > 0 for r in st.runs() if r["arm"] == "stop-30pct")
