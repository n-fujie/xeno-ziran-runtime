"""Experiments A-F (and the additions): they run, are deterministic, store their conditions, keep negative results, export JSON/CSV."""

from __future__ import annotations

import csv
import io
import json

import pytest

from xzr.xbtro import experiments, metrics, records

SMALL = {"n_seeds": 4}


@pytest.fixture(scope="module")
def recs():
    out = {}
    out["A"], _ = experiments.run_to_end("A", {**SMALL, "rounds": 2})
    out["B"], _ = experiments.run_to_end("B", SMALL)
    out["C"], _ = experiments.run_to_end(
        "C", {**SMALL, "principles": ["axis-maintenance", "anti-collapse-posture"], "combos": False}
    )
    out["D"], _ = experiments.run_to_end("D", {**SMALL, "trials": 3})
    out["F"], _ = experiments.run_to_end("F", SMALL)
    return out


def test_catalog_keeps_the_original_experiments_and_their_questions():
    ids = [e["id"] for e in experiments.catalog()]
    assert ids[:6] == ["A", "B", "C", "D", "E", "F"]
    titles = {e["id"]: e["title"] for e in experiments.catalog()}
    assert (
        titles["A"] == "Observation-Cut Transformation"
        and titles["C"] == "Fragility Transfer"
        and titles["F"] == "Human-Machine Operational Comparison"
    )


@pytest.mark.parametrize("eid", ["A", "B", "C", "D", "F"])
def test_record_stores_everything_needed_to_repeat_and_read_it(recs, eid):
    r = recs[eid]
    for k in (
        "schema",
        "id",
        "experiment",
        "model_version",
        "seeds",
        "initial_configuration",
        "observation_configurations",
        "interventions",
        "time_step_s",
        "numerical_method",
        "parameters",
        "results",
        "negative_results",
        "unobserved_differences",
        "history",
        "rerun",
        "digest",
        "provenance",
        "labels",
    ):
        assert k in r, k
    assert r["experiment"] == eid and r["seeds"] == [
        metrics.FINAL_SEED_BASE + i for i in range(4)
    ]  # final seeds, disjoint from the exploration seeds
    assert not set(r["seeds"]) & set(metrics.EXPLORATION_SEEDS)
    assert records.digest(r["results"]) == r["digest"]
    assert r["results"]["tables"] and all(t["rows"] for t in r["results"]["tables"][:1])
    assert "reference" in r["labels"] and "observation" in r["labels"] and "estimate" in r["labels"]


def test_rerun_reproduces_the_digest():
    a, _ = experiments.run_to_end("B", SMALL)
    b, _ = experiments.run_to_end(a["rerun"]["experiment"], a["rerun"]["parameters"])
    assert a["digest"] == b["digest"] and a["id"] == b["id"]
    assert records.compare(a, b)["equal_digest"]


def test_json_and_csv_round_trip(recs):
    r = recs["C"]
    back = json.loads(records.to_json(r))
    assert records.digest(back["results"]) == r["digest"]
    text = records.to_csv(r)
    rows = list(csv.reader(io.StringIO(text)))
    names = [row[0] for row in rows if row and row[0].startswith("# table:")]
    assert len(names) >= len(r["results"]["tables"])
    assert any(row and row[0] == "# digest" and row[1] == r["digest"] for row in rows)


def test_negative_and_null_results_are_kept(recs):
    c = recs["C"]
    assert any("never ignited" in n["statement"] for n in c["negative_results"])  # anti-collapse-posture: not ignited, said so
    assert recs["F"]["negative_results"] is not None and recs["B"]["negative_results"]


def test_experiment_c_reports_design_and_ignition(recs):
    d = recs["C"]["results"]["design"]
    assert d["n_pairs"] == 4 and d["min_detectable_dz"] > 1.0  # four seeds can only resolve large effects: stated, not hidden
    assert recs["C"]["results"]["design"]["ignition"]["anti-collapse-posture"] == 0.0


def test_recovery_in_experiment_b_is_not_saturated(recs):
    rows = [r for r in recs["B"]["results"]["tables"][0]["rows"] if "recovery" in r[1]]
    means = {round(r[3], 3) for r in rows if r[3] is not None}
    assert len(means) > 2  # the earlier defect: every condition at the cap


def test_history_store_registry_and_import_guard(recs):
    h = records.HistoryStore()
    a = h.add(recs["A"])
    h.add(recs["B"], parent=a["id"])
    assert [x["experiment"] for x in h.listing()] == ["A", "B"] and h.listing()[1]["parent"] == a["id"]
    assert isinstance(h.registry(), list)
    data = h.export()
    h2 = records.HistoryStore()
    assert h2.load(data) == 2
    tampered = json.loads(json.dumps(recs["B"]))
    tampered["results"]["tables"][0]["rows"][0][3] = 123.0
    with pytest.raises(ValueError, match="digest"):
        records.HistoryStore().import_record(tampered)


def test_unknown_experiment_and_bad_seed_counts_are_refused():
    with pytest.raises(experiments.ExperimentError):
        experiments.run("Z", {})
    with pytest.raises(experiments.ExperimentError):
        experiments.run_to_end("B", {"n_seeds": 3})
