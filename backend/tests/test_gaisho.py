"""GAISHO - Operational Shape Laboratory: the properties of the laboratory's own model (reproducibility, seed independence, the separation of operation from record, the retention of unresolved regions and negative
results, the separation of operation results from the Gaisho attribution, the reproduction of the saved results, the HTTP boundary). Synthetic computational experiments; none of it is evidence about a Gaisho."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from xzr.gaisho import MODEL_VERSION
from xzr.gaisho.compare import attribution_tests, compare_models, compare_observations
from xzr.gaisho.domains import STATUS, domain_registry
from xzr.gaisho.export import observation_from, restore, run_experiment
from xzr.gaisho.figure import figure_svg
from xzr.gaisho.knowledge import KnowledgeDomain
from xzr.gaisho.lab import FULL, Observation, paired, run_domain
from xzr.gaisho.model import LEVELS, PROHIBITED_INFERENCES, UNOBSERVED, VERDICTS, attribute, refuse
from xzr.gaisho.shape import build_shape, compare_shapes

SAVED = Path(__file__).resolve().parents[2] / "docs" / "gaisho" / "experiments.json"
SEEDS = (1, 2, 3, 4, 5, 6)
RESPONSIVE = "ground-responsive judgement"
CUE = "accidental correct: coincidental cue"
BASE = "accidental correct: base-rate guess"
MISJ = "misjudgement: miscalibrated reading"
FEEDBACK = "correction and reconfiguration (feedback on)"
NOFEEDBACK = "no correction (feedback off)"


@pytest.fixture(scope="module")
def dom():
    return KnowledgeDomain()


@pytest.fixture(scope="module")
def full(dom):
    return run_domain(dom, FULL, SEEDS)


def rel(res, cond, name):
    return res["conditions"][cond]["relations"][name]


# ------------------------------------------------------------------------------------------------ reproducibility and seeds
def test_the_same_specification_gives_the_same_digest(dom):
    a, b = run_domain(dom, FULL, SEEDS, [RESPONSIVE]), run_domain(dom, FULL, SEEDS, [RESPONSIVE])
    assert a["digest"] == b["digest"] and a["model_version"] == MODEL_VERSION


def test_seeds_are_independent_replications_and_change_the_run(dom):
    a, b = run_domain(dom, FULL, (1, 2, 3, 4), [RESPONSIVE]), run_domain(dom, FULL, (5, 6, 7, 8), [RESPONSIVE])
    assert a["digest"] != b["digest"]
    # a run does not depend on which other seeds are run with it: seed 3 alone equals seed 3 among others
    solo = dom.simulate(RESPONSIVE, 3, FULL)["operation_digest"]
    assert solo == dom.simulate(RESPONSIVE, 3, FULL)["operation_digest"] and solo != dom.simulate(RESPONSIVE, 4, FULL)["operation_digest"]


def test_the_replication_unit_is_the_seed_and_intervals_are_t_based(full):
    r = rel(full, RESPONSIVE, "effect_E")
    assert r["n"] == len(SEEDS) and len(r["per_seed"]) == len(SEEDS)
    half = (r["ci95"][1] - r["ci95"][0]) / 2
    assert half == pytest.approx(2.093 * r["se"])  # the t value of the laboratory (20 seeds); the statement is in LIMITS/docs


def test_paired_difference_uses_the_same_seeds_and_detects_only_when_the_interval_excludes_zero():
    d = paired([1.0, 1.1, 0.9, 1.0], [0.0, 0.1, -0.1, 0.0])
    assert d["detected"] is True and d["mean"] == pytest.approx(1.0)
    z = paired([0.1, -0.1, 0.05, -0.05], [0.0, 0.0, 0.0, 0.0])
    assert z["detected"] is False and z["ci95"][0] <= 0 <= z["ci95"][1]


# ------------------------------------------------------------------------------------------------ the candidates differ in their intervention-relative profile, not in accuracy
def test_conditions_with_a_similar_accuracy_differ_in_their_intervention_profile(full):
    acc = {c: full["conditions"][c]["accuracy_pre_shift"]["mean"] for c in (BASE, CUE, RESPONSIVE)}
    assert max(acc.values()) - min(acc.values()) < 0.1  # similar accuracy before the shift
    assert rel(full, RESPONSIVE, "effect_E")["value"] > 0.8 and abs(rel(full, RESPONSIVE, "effect_S")["value"]) < 0.1
    assert rel(full, CUE, "effect_S")["value"] > 0.8 and abs(rel(full, CUE, "effect_E")["value"]) < 0.1
    assert rel(full, CUE, "shift_drop")["value"] > 0.2 > rel(full, RESPONSIVE, "shift_drop")["value"]


def test_correction_and_reconfiguration_is_recorded_as_a_change_of_the_dependence(full):
    assert rel(full, FEEDBACK, "revision_E")["value"] > 0.3 and rel(full, FEEDBACK, "revision_S")["value"] < -0.3
    assert abs(rel(full, NOFEEDBACK, "revision_E")["value"]) < 0.2  # without feedback the dependence is kept


def test_every_condition_has_its_own_shape_and_the_shapes_are_not_one_geometry(dom, full):
    axes = {"x": dom.x_name, "y": dom.y_name}
    shapes = {c: build_shape(full, c, "end", axes) for c in full["conditions"]}
    assert len({s["digest"] for s in shapes.values()}) == len(shapes)
    cmp = compare_shapes(shapes[RESPONSIVE], shapes[CUE])
    assert cmp["comparable"] and cmp["mean_abs_difference"] > 0.2
    same = compare_shapes(shapes[CUE], shapes[CUE])
    assert same["mean_abs_difference"] == 0 and not same["cuts_only_in_first"]


def test_every_point_line_and_surface_is_traceable_to_its_source_and_projection_is_declared(dom, full):
    s = build_shape(full, CUE, "end", {"x": dom.x_name, "y": dom.y_name})
    assert s["projection"]["kind"] == "VISUALIZATION_PROJECTION"
    op = full["conditions"][CUE]["operation_digest"]
    assert all(v["source"]["operation_digest"] == op for v in s["vertices"])
    assert all(e["source"]["operation_digest"] == op and e["source"]["provenance"] == "RECONSTRUCTED_RELATION" for e in s["edges"] + s["cuts"])
    assert all(b["source"]["provenance"] == "RECONSTRUCTED_RELATION" for b in s["branch"])
    ids = {v["id"] for v in s["vertices"]}
    assert all(e["a"] in ids and e["b"] in ids for e in s["edges"] + s["cuts"])


def test_before_after_snapshots_are_comparable(dom, full):
    axes = {"x": dom.x_name, "y": dom.y_name}
    a, b = build_shape(full, CUE, "before shift", axes), build_shape(full, CUE, "end", axes)
    c = compare_shapes(a, b)
    assert c["comparable"] and c["cells_compared"] == len(a["vertices"]) == len(b["vertices"])
    assert len(c["cell_differences"]) == c["cells_compared"]


# ------------------------------------------------------------------------------------------------ total relational observation
def test_scale_window_and_speed_misfits_are_reported_as_such_not_as_zero(dom):
    r = run_domain(dom, Observation(temporal_window=10), SEEDS, [RESPONSIVE])
    assert all(v["status"] == "TEMPORAL_MISFIT" for v in r["conditions"][RESPONSIVE]["relations"].values())
    r = run_domain(dom, Observation(speed=3), SEEDS, [RESPONSIVE])
    assert rel(r, RESPONSIVE, "stability_do_W")["status"] == "TEMPORAL_MISFIT"
    r = run_domain(dom, Observation(scale=4), SEEDS, [RESPONSIVE])
    assert rel(r, RESPONSIVE, "effect_E")["status"] == "SCALE_MISFIT"


def test_temporal_window_sensitivity_a_longer_window_keeps_the_relation(dom, full):
    r = run_domain(dom, Observation(temporal_window=100), SEEDS, [RESPONSIVE])
    assert rel(r, RESPONSIVE, "effect_E")["value"] == pytest.approx(rel(full, RESPONSIVE, "effect_E")["value"], abs=0.05)


def test_unobserved_regions_are_kept_with_their_class_in_the_shape(dom):
    axes = {"x": dom.x_name, "y": dom.y_name}
    cases = {"passive": Observation(coupling="passive"), "boundary": Observation(boundary=("y",)), "scale": Observation(scale=2), "resources": Observation(resources=30)}
    for name, obs in cases.items():
        res = run_domain(dom, obs, SEEDS[:3], [CUE])
        s = build_shape(res, CUE, "end", axes)
        assert s["unresolved"], name
        assert {u["reason"] for u in s["unresolved"]} <= set(UNOBSERVED), name
        assert len(s["vertices"]) + len(s["unresolved"]) == len(dom.x_values) * len(dom.y_values), name  # nothing is dropped


def test_passive_coupling_cannot_separate_the_axes_and_says_so(dom):
    res = run_domain(dom, Observation(coupling="passive"), SEEDS, [RESPONSIVE])
    for n in ("effect_E", "effect_S", "revision_E", "revision_S"):
        assert rel(res, RESPONSIVE, n)["status"] == "IDENTIFICATION_UNRESOLVED", n


def test_boundary_memory_and_instrument_classes(dom):
    assert rel(run_domain(dom, Observation(boundary=("y",)), SEEDS, [RESPONSIVE]), RESPONSIVE, "effect_S")["status"] == "BOUNDARY_INVISIBLE"
    assert rel(run_domain(dom, Observation(memory=False), SEEDS, [RESPONSIVE]), RESPONSIVE, "revision_E")["status"] == "UNMEASURED"
    noisy = run_domain(dom, Observation(sensor_noise=0.3), SEEDS, [RESPONSIVE])
    assert rel(noisy, RESPONSIVE, "effect_E")["value"] < rel(run_domain(dom, FULL, SEEDS, [RESPONSIVE]), RESPONSIVE, "effect_E")["value"]  # the instrument attenuates the record


def test_an_instrument_change_alters_the_record_not_the_operation(dom):
    c = compare_observations(dom, RESPONSIVE, FULL, Observation(scale=2), SEEDS)
    assert c["same_realized_operation"] is True and c["observation_changed_the_operation"] is False
    c = compare_observations(dom, RESPONSIVE, FULL, Observation(sensor_noise=0.3), SEEDS)
    assert c["same_realized_operation"] is True
    assert any(r["kind"] == "RECORD_DIFFERENCE" for r in c["relations"])
    assert not any(r["kind"] == "OPERATION_DIFFERENCE" for r in c["relations"])


def test_a_probe_changes_the_operation_and_is_recorded_as_doing_so(dom):
    c = compare_observations(dom, CUE, FULL, Observation(probe=1.0), SEEDS)
    assert c["same_realized_operation"] is False and c["observation_changed_the_operation"] is True
    assert c["operation_part_first"]["probe"] == 0.0 and c["operation_part_second"]["probe"] == 1.0
    assert any(r["kind"] == "OPERATION_DIFFERENCE" for r in c["relations"])


def test_an_environment_change_is_a_change_of_the_operation(dom):
    c = compare_observations(dom, FEEDBACK, FULL, Observation(environment="harder evidence (sigma 1.2)"), SEEDS)
    assert c["observation_changed_the_operation"] is True


# ------------------------------------------------------------------------------------------------ competing explanations, ablations, negative results
def test_the_competing_model_comparison_has_verdict_classes_and_no_score(dom):
    m = compare_models(dom, SEEDS)
    assert {r["condition"] for r in m["rows"]} == set(dom.conditions)
    for row in m["rows"]:
        for v in row["verdicts"]:
            assert v["verdict"] in VERDICTS
    assert "score" not in json.dumps(m).lower().replace("scored", "")


def test_the_candidate_construction_is_not_always_non_redundant(dom):
    m = compare_models(dom, SEEDS)
    verdicts = {v["verdict"] for row in m["rows"] for v in row["verdicts"]}
    assert verdicts & {"REDUNDANT", "HARMFUL"}  # the negative verdicts are kept, not removed


def test_the_ablation_of_the_evidence_channel_removes_the_responsiveness(dom):
    """A condition that keeps the cue and no evidence reading shows the same accuracy but not the evidence effect: the evidence reading is what the difference rests on."""
    res = run_domain(dom, FULL, SEEDS, [CUE, RESPONSIVE])
    assert rel(res, CUE, "effect_E")["value"] < 0.1 < rel(res, RESPONSIVE, "effect_E")["value"]


def test_the_operational_test_can_fail_and_never_returns_an_attribution(full):
    tests = {t["condition"]: t for t in attribution_tests(full)}
    assert tests[BASE]["operational_test"] == "CRITERION_NEGATIVE" and tests[CUE]["operational_test"] == "CRITERION_NEGATIVE"
    assert tests[NOFEEDBACK]["operational_test"] == "CRITERION_NEGATIVE"
    assert tests[RESPONSIVE]["operational_test"] == "NOT_NEGATED"
    assert all(t["attribution"] == "UNRESOLVED" for t in tests.values())  # passing the operational test is not an attribution


def test_misjudgement_is_not_separated_by_the_operational_criterion_a_negative_result(full):
    assert {t["condition"]: t["operational_test"] for t in attribution_tests(full)}[MISJ] == "NOT_NEGATED"


def test_a_criterion_relation_that_is_unobserved_makes_the_test_unresolved(dom):
    res = run_domain(dom, Observation(coupling="passive"), SEEDS, [RESPONSIVE])
    t = attribution_tests(res)[0]
    assert t["operational_test"] == "UNRESOLVED" and t["attribution"] == "UNRESOLVED"


# ------------------------------------------------------------------------------------------------ the five levels and the forbidden inferences
def test_the_five_levels_are_separate_records_and_the_attribution_is_never_derived():
    lv = attribute({"real_operation": "EXECUTED_IN_MODEL", "operational_shape": "RECONSTRUCTED"})
    assert tuple(lv) == LEVELS
    assert lv["gaisho_operational_shape"]["state"] == "NOT_ESTABLISHED" and lv["gaisho_attribution"]["state"] == "UNRESOLVED"
    # a bearer and an interval alone do not give an attribution; the evidence is the researcher's and is only recorded
    lv = attribute({"real_operation": "EXECUTED_IN_MODEL"}, bearer="b", historical_interval="i")
    assert lv["gaisho_attribution"]["state"] == "UNRESOLVED"
    lv = attribute({"real_operation": "EXECUTED_IN_MODEL"}, bearer="b", historical_interval="i", independent_evidence=["e"])
    assert lv["gaisho_attribution"]["state"] == "ASSERTED_BY_RESEARCHER" and "not computed" in lv["gaisho_attribution"]["note"]
    lv = attribute({"real_operation": "EXECUTED_IN_MODEL"}, independent_evidence=["e"])
    assert lv["gaisho_attribution"]["state"] == "UNRESOLVED"  # evidence without a bearer and an interval is not enough


def test_every_forbidden_inference_is_refused_and_an_unlisted_one_is_not():
    assert len(PROHIBITED_INFERENCES) == 8
    for p, c, why in PROHIBITED_INFERENCES:
        assert refuse(p, c) == why and why
    assert refuse("spike_fired", "neuron_model_fired") is None


def test_no_result_of_an_executed_experiment_has_a_gaisho_level_above_not_established():
    out = run_experiment({"domain": "001-knowledge", "seeds": list(SEEDS[:3]), "conditions": [RESPONSIVE, CUE]})
    for lv in out["levels"].values():
        assert lv["gaisho_operational_shape"]["state"] == "NOT_ESTABLISHED" and lv["gaisho_attribution"]["state"] == "UNRESOLVED"
        assert lv["conceptual_operational_shape"]["state"] == "NOT_MODELLED"


# ------------------------------------------------------------------------------------------------ record, restore, figure
def test_the_record_restores_by_rerunning_its_specification():
    out = run_experiment({"domain": "001-knowledge", "seeds": list(SEEDS[:3]), "conditions": [RESPONSIVE]})
    r = restore({"spec": out["spec"], "digest": out["digest"]})
    assert r["same_digest"] is True
    assert restore({"spec": out["spec"], "digest": "0" * 64})["same_digest"] is False


def test_the_record_keeps_negative_results_limits_and_the_figure_kind():
    out = run_experiment({"domain": "001-knowledge", "seeds": list(SEEDS[:3])})
    kinds = {n["kind"] for n in out["negative_results"]}
    assert "NOT_DONE" in kinds and {"CRITERION_NEGATIVE"} <= kinds
    assert out["figure_kind"] == "EXECUTED_COMPUTATIONAL_EXPERIMENT" and "human neural activity" in out["limits"]
    assert set(out["research_objects"]) == set(out["result"]["conditions"])
    ro = out["research_objects"][RESPONSIVE]
    assert ro["unresolved_attribution"] == "UNRESOLVED" and len(ro) == 13  # id, candidate and the twelve questions less the candidate


def test_the_figure_is_regenerated_from_the_record_and_is_deterministic():
    out = run_experiment({"domain": "001-knowledge", "seeds": list(SEEDS[:3]), "conditions": [CUE]})
    a, b = figure_svg(out, "end"), figure_svg(run_experiment(out["spec"]), "end")
    assert a == b and a.startswith("<svg") and "EXECUTED" in a.upper()
    assert out["digest"][:8] in a  # the figure carries the digest of the record it is drawn from
    assert "#0B3D91" in a  # limited Institutional Blue


def test_the_domains_not_executed_are_specified_and_not_substituted():
    reg = domain_registry()
    assert reg["004-body"] is None and STATUS["004-body"]["executed"] is False
    out = run_experiment({"domain": "004-body"})
    assert out["executed"] is False and "result" not in out and "no substitute computation" in out["note"]
    assert out["figure_kind"] == "CONCEPTUAL_RECONSTRUCTION"


def test_one_domain_completing_does_not_complete_the_others():
    done = {k: v["completion"] for k, v in STATUS.items()}
    assert done["001-knowledge"] != done["004-body"]
    assert len(set(done.values())) > 1 and all(v for v in done.values())


def test_the_other_executed_domains_run_and_keep_their_own_relations():
    for dom_id in ("002-bias", "003-freedom", "005-credit"):
        d = domain_registry()[dom_id]
        out = run_experiment({"domain": dom_id, "seeds": [1, 2, 3, 4]})
        assert out["executed"] is True and set(out["result"]["conditions"]) == set(d.conditions)
        assert set(next(iter(out["result"]["conditions"].values()))["relations"]) == set(d.relation_names)
        assert out["negative_results"], dom_id


def test_observation_from_validates_nothing_but_builds_tuples():
    o = observation_from({"boundary": ["x"], "sensor_channels": ["x", "y"]})
    assert o.boundary == ("x",) and o.sensor_channels == ("x", "y") and dataclasses.is_dataclass(o)


# ------------------------------------------------------------------------------------------------ the saved results still reproduce
def test_the_saved_experiment_results_reproduce_their_digests():
    saved = json.loads(SAVED.read_text())
    assert saved["model_version"] == MODEL_VERSION
    for dom_id in ("002-bias", "003-freedom", "005-credit"):
        rec = saved["domains"][dom_id]
        assert run_experiment(rec["spec"])["digest"] == rec["digest"], dom_id


def test_the_saved_knowledge_record_reproduces_with_its_negative_results():
    rec = json.loads(SAVED.read_text())["domains"]["001-knowledge"]
    again = run_experiment(rec["spec"])
    assert again["digest"] == rec["digest"] and len(again["negative_results"]) == len(rec["negative_results"])


def test_the_saved_observation_sensitivity_table_has_the_unobserved_classes():
    s = json.loads(SAVED.read_text())["knowledge_observation_sensitivity"]
    classes = {r for row in s.values() for c in row["conditions"].values() for r in c["relations"].values() if isinstance(r, str)}
    assert classes >= {"TEMPORAL_MISFIT", "SCALE_MISFIT", "IDENTIFICATION_UNRESOLVED", "BOUNDARY_INVISIBLE", "UNMEASURED"}


# ------------------------------------------------------------------------------------------------ existing runtime is untouched
def test_the_laboratory_reuses_the_truth_error_engine_without_changing_its_digests():
    from xzr.truth_error import institution as I  # noqa: E741

    d = domain_registry()["005-credit"]
    assert d.__class__.__module__ == "xzr.gaisho.domains"
    a = I.run(I.Config(n=60, periods=12, seed=3))["result_digest"]
    run_domain(d, FULL, (1, 2), None)
    assert I.run(I.Config(n=60, periods=12, seed=3))["result_digest"] == a  # running the lab leaves the engine as it was


def test_numpy_global_state_is_not_used():
    np.random.seed(123)
    before = np.random.random()
    np.random.seed(123)
    run_domain(KnowledgeDomain(), FULL, (1, 2), [RESPONSIVE])
    assert np.random.random() == before  # the laboratory draws from its own seeded streams only


# ------------------------------------------------------------------------------------------------ the API
def test_the_api_is_local_only_stateless_and_validated(monkeypatch):
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod
    from xzr.service import studies as studies_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    spec = c.get("/api/gaisho/spec").json()
    assert spec["model_version"] == MODEL_VERSION and "R37" in spec["source_status"] and set(spec["domains"]) == set(STATUS)
    body = {"domain": "001-knowledge", "seeds": [1, 2, 3], "conditions": [RESPONSIVE]}
    r = c.post("/api/gaisho/run", json=body).json()
    assert r["digest"] == run_experiment({**body, "observation": FULL.asdict()})["digest"]
    json.dumps(r, allow_nan=False)
    assert c.post("/api/gaisho/restore", json={"spec": r["spec"], "digest": r["digest"]}).json()["same_digest"] is True
    fig = c.post("/api/gaisho/figure", json={**body, "snapshot": "end"}).json()
    assert fig["svg"].startswith("<svg") and fig["figure_kind"] == "EXECUTED_COMPUTATIONAL_EXPERIMENT"
    cmp = c.post("/api/gaisho/compare-shapes", json={**body, "conditions": [RESPONSIVE, CUE], "first": {"condition": RESPONSIVE, "snapshot": "end"}, "second": {"condition": CUE, "snapshot": "end"}}).json()
    assert cmp["comparison"]["comparable"] is True
    co = c.post("/api/gaisho/compare-observations", json={**body, "condition": CUE, "first": {}, "second": {"probe": 1.0}}).json()
    assert co["observation_changed_the_operation"] is True
    for bad in (
        {"domain": "nope"},
        {"domain": "001-knowledge", "seeds": []},
        {"domain": "001-knowledge", "seeds": list(range(1, 22))},
        {"domain": "001-knowledge", "seeds": [0]},
        {"domain": "001-knowledge", "seeds": [True]},
        {"domain": "001-knowledge", "conditions": ["nope"]},
        {"domain": "001-knowledge", "observation": {"scale": 9}},
        {"domain": "001-knowledge", "observation": {"coupling": "x"}},
        {"domain": "001-knowledge", "observation": {"environment": "x"}},
        {"domain": "001-knowledge", "observation": {"memory": 1}},
        {"domain": "001-knowledge", "observation": {"boundary": ["z"]}},
        {"domain": "001-knowledge", "observation": {"unknown": 1}},
        {"domain": "001-knowledge", "observation": {"sensor_noise": 0.9}},
    ):
        assert c.post("/api/gaisho/run", json=bad).status_code == 422, bad
    assert c.post("/api/gaisho/restore", json={"spec": body}).status_code == 422
    assert c.post("/api/gaisho/compare-shapes", json={**body, "first": {}, "second": {}}).status_code == 422
    assert c.post("/api/gaisho/compare-observations", json={**body, "condition": "nope"}).status_code == 422
    assert c.post("/api/gaisho/figure", json={"domain": "004-body"}).status_code == 422
    assert c.post("/api/gaisho/run", json=body, headers={"origin": "http://evil.example"}).status_code == 403
    pub = dataclasses.replace(studies_mod.LIMITS, public=True)
    monkeypatch.setattr(studies_mod, "LIMITS", pub)
    assert c.get("/api/gaisho/spec").status_code == 403 and c.post("/api/gaisho/run", json=body).status_code == 403


def test_the_package_is_excluded_from_the_public_build_and_the_ios_engine():
    here = Path(__file__).resolve().parents[2]
    stage = (here / "ios" / "scripts" / "stage_engine.py").read_text()
    assert '"gaisho"' in stage and 'Path("service") / "gaisho.py"' in stage


# ------------------------------------------------------------------------------------------------ the construction of the shapes: where every cell and every edge comes from
def test_every_cell_and_edge_of_every_shape_is_traced_to_its_construction(dom, full):
    """91 cells = the 13 x 7 grid of the two interventions; 162 edges = 12 x 7 along E + 13 x 6 along S; each cell is one intervention pair with its value, trials, seeds and provenance."""
    from xzr.gaisho.construction import explain_shape

    rec = {"result": full, "shapes": {c: {s: build_shape(full, c, s, {"x": dom.x_name, "y": dom.y_name}) for s in dom.snapshots} for c in full["conditions"]}}
    for cond in full["conditions"]:
        for snap in dom.snapshots:
            e = explain_shape(rec, cond, snap, dom)
            c = e["counts"]
            assert c["grid"] == [13, 7] and c["cells_expected"] == 91 and c["cells_recorded"] == 91 and c["cells_unresolved"] == 0
            assert c["edges_expected_if_all_recorded"] == 12 * 7 + 13 * 6 == 162 and c["edges_drawn"] == 162 and e["counts_consistent"] is True
            assert len(e["cells"]) == 91 and len(e["edges"]) == 162
            cell = e["cells"][0]
            assert set(cell["intervention"]) == {dom.x_name, dom.y_name} and cell["trials_per_cell_and_seed"] == 40 and cell["seeds"] == len(SEEDS) and cell["provenance"] == "RECORDED_OBSERVATION"
            assert {ed["along"] for ed in e["edges"]} == {dom.x_name, dom.y_name}
            assert sum(1 for ed in e["edges"] if ed["along"] == dom.x_name) == 84 and sum(1 for ed in e["edges"] if ed["along"] == dom.y_name) == 78
    assert "P(J = +1" in explain_shape(rec, RESPONSIVE, "end", dom)["outcome_of_the_domain"]


def test_the_cells_of_a_shape_carry_the_weights_of_the_decision_rule_and_nothing_more(dom, full):
    """The 91 recorded cells are reproduced by three numbers (the agent's weights at the moment) up to sampling noise: the surface is a reading of the decision rule under intervention, not a record of the run's history."""
    from xzr.gaisho.construction import explain_shape

    rec = {"result": full, "shapes": {c: {s: build_shape(full, c, s, {"x": dom.x_name, "y": dom.y_name}) for s in dom.snapshots} for c in full["conditions"]}}
    for cond in full["conditions"]:
        for snap in dom.snapshots:
            w = explain_shape(rec, cond, snap, dom)["what_the_surface_carries"]
            for k in ("a", "b", "c"):
                assert w["fitted_weights"][k] == pytest.approx(w["weights_of_the_operation"][k], abs=0.35), (cond, snap, k)
            assert w["rms_residual_of_the_fit"] < 1.6 * w["expected_sampling_rms"], (cond, snap)  # nothing beyond the weights and sampling noise is in the cells
    assert "not a record of the run's history" in w["reading"]


def test_unrecorded_cells_stay_in_the_count(dom):
    from xzr.gaisho.construction import explain_shape

    res = run_domain(dom, Observation(scale=2), SEEDS[:3], [RESPONSIVE])
    rec = {"result": res, "shapes": {RESPONSIVE: {s: build_shape(res, RESPONSIVE, s, {"x": dom.x_name, "y": dom.y_name}) for s in dom.snapshots}}}
    e = explain_shape(rec, RESPONSIVE, "end", dom)
    assert e["counts"]["cells_unresolved"] > 0 and e["counts"]["cells_total"] == 91 and e["counts_consistent"] is True and {u["reason"] for u in e["unresolved"]} == {"SCALE_MISFIT"}
    assert e["counts"]["edges_drawn"] < 162  # an edge needs two recorded ends


def test_the_relations_are_the_readings_of_the_same_cells_the_shape_is_drawn_from(dom, full):
    """3D and relations agree: effect_E, effect_S and the revisions recomputed from the cells of the shapes equal the recorded relations."""
    def eff(cond, snap, axis):
        s = build_shape(full, cond, snap, {"x": dom.x_name, "y": dom.y_name})
        z = {tuple(v["cell"]): v["z"] for v in s["vertices"]}
        return float(np.mean([z[(12, j)] - z[(0, j)] for j in range(7)])) if axis == "E" else float(np.mean([z[(i, 6)] - z[(i, 0)] for i in range(13)]))
    for cond in full["conditions"]:
        assert eff(cond, "end", "E") == pytest.approx(rel(full, cond, "effect_E")["value"], abs=1e-9)
        assert eff(cond, "end", "S") == pytest.approx(rel(full, cond, "effect_S")["value"], abs=1e-9)
        assert eff(cond, "end", "E") - eff(cond, "start", "E") == pytest.approx(rel(full, cond, "revision_E")["value"], abs=1e-9)
        assert eff(cond, "end", "S") - eff(cond, "start", "S") == pytest.approx(rel(full, cond, "revision_S")["value"], abs=1e-9)


# ------------------------------------------------------------------------------------------------ real operation / record / reconstruction / display
def test_a_difference_between_two_shapes_is_read_as_operation_record_or_noise(dom, full):
    from xzr.gaisho.construction import reading_of_difference

    def shapes(res, cond):
        ax = {"x": dom.x_name, "y": dom.y_name}
        return build_shape(res, cond, "start", ax), build_shape(res, cond, "end", ax)
    for cond in (CUE, RESPONSIVE, NOFEEDBACK):  # the weights do not change: the cells differ by sampling noise only
        a, b = shapes(full, cond)
        r = reading_of_difference(a, b, compare_shapes(a, b))
        assert r["real_operation"].startswith("SAME_OPERATION") and r["recorded_observation"]["reading"] == "WITHIN_SAMPLING_NOISE", cond
        assert r["display"].startswith("none")
    a, b = shapes(full, FEEDBACK)  # the weights change: a real change of the operation, far beyond the noise
    r = reading_of_difference(a, b, compare_shapes(a, b))
    assert r["real_operation"].startswith("OPERATION_CHANGED") and r["recorded_observation"]["reading"] == "BEYOND_SAMPLING_NOISE" and max(abs(x) for x in r["weight_change"].values()) > 1
    nomem = run_domain(dom, Observation(memory=False), SEEDS[:3], [RESPONSIVE])  # no memory record: the cause cannot be read from the shapes, and the reading says so
    a, b = build_shape(nomem, RESPONSIVE, "end", {"x": dom.x_name, "y": dom.y_name}), build_shape(nomem, RESPONSIVE, "before shift", {"x": dom.x_name, "y": dom.y_name})
    assert reading_of_difference(a, b, compare_shapes(a, b))["real_operation"].startswith("UNDETERMINED")


def test_observation_comparisons_state_the_four_kinds(dom):
    from xzr.gaisho.construction import change_kinds_of_observations

    k = change_kinds_of_observations(compare_observations(dom, CUE, FULL, Observation(scale=2), SEEDS))
    assert k["real_operation"] == "SAME" and k["display"].startswith("none")
    k = change_kinds_of_observations(compare_observations(dom, CUE, FULL, Observation(probe=1.0), SEEDS))
    assert k["real_operation"].startswith("CHANGED")
    k = change_kinds_of_observations(compare_observations(dom, CUE, FULL, Observation(coupling="passive"), SEEDS))
    assert k["real_operation"] == "SAME" and "effect_E" in k["reconstructed_relation"]["unobserved_in_one"]


# ------------------------------------------------------------------------------------------------ what is supported, what is negative, what is an untested hypothesis
def test_every_claim_has_a_status_and_the_supported_and_negative_ones_hold_on_the_saved_results():
    from xzr.gaisho.claims import CLAIMS, LIMITED_OR_NEGATIVE, SUPPORTED_IN_MODEL, UNTESTED_HYPOTHESIS, claims_by_status

    assert {c["status"] for c in CLAIMS} == {SUPPORTED_IN_MODEL, LIMITED_OR_NEGATIVE, UNTESTED_HYPOTHESIS} and len({c["id"] for c in CLAIMS}) == len(CLAIMS)
    assert all(c["claim"] and c["rests_on"] for c in CLAIMS) and len(claims_by_status()[UNTESTED_HYPOTHESIS]) >= 4
    k = json.loads(SAVED.read_text())["domains"]["001-knowledge"]
    conds = k["result"]["conditions"]
    ci = lambda c, n: k["result"]["conditions"][c]["relations"][n]["ci95"]  # noqa: E731
    acc = [conds[c]["accuracy_pre_shift"]["mean"] for c in (BASE, CUE, RESPONSIVE)]
    assert max(acc) - min(acc) < 0.05 and ci(CUE, "effect_S")[0] > 0.8 and ci(RESPONSIVE, "effect_E")[0] > 0.9 and ci(CUE, "effect_E")[1] < 0.2 and ci(RESPONSIVE, "effect_S")[1] < 0.2  # K1
    assert ci(CUE, "shift_drop")[0] > 0.2 and ci(RESPONSIVE, "shift_drop")[1] < 0.1  # K2
    assert ci(FEEDBACK, "revision_E")[0] > 0.3 and ci(FEEDBACK, "revision_S")[1] < -0.3 and ci(NOFEEDBACK, "revision_E")[1] < 0.1  # K3
    tests = {t["condition"]: t["operational_test"] for t in k["attribution_tests"]}
    assert tests[MISJ] == "NOT_NEGATED" and tests[RESPONSIVE] == "NOT_NEGATED"  # N1
    assert all(next(x for x in row["verdicts"] if x["competitor"].startswith("M1"))["verdict"] in ("REDUNDANT", "HARMFUL") for row in k["models"]["rows"])  # N2
    assert any(n["kind"] == "NOT_DETECTED" for n in k["negative_results"]) and any(n["kind"] == "UNOBSERVED" for n in json.loads(SAVED.read_text())["domains"]["002-bias"]["negative_results"] + k["negative_results"])  # N4


def test_the_shapes_of_the_knowledge_domain_have_no_cuts_so_the_domain_shows_no_richer_shape_than_its_weights(full, dom):
    for cond in full["conditions"]:
        assert build_shape(full, cond, "end", {"x": dom.x_name, "y": dom.y_name})["cuts"] == []  # claim N3, kept as a test so that a change of the model that adds cuts is noticed


# ------------------------------------------------------------------------------------------------ the attribution is not derived from accuracy, spikes, internal state or classification
def test_the_attribution_takes_nothing_from_an_operational_result():
    import inspect

    assert list(inspect.signature(attribute).parameters) == ["operational", "bearer", "historical_interval", "independent_evidence"]  # no accuracy, spike, state or classification parameter
    base = attribute({"real_operation": "EXECUTED_IN_MODEL", "operational_shape": "RECONSTRUCTED"})
    for ops in ({"real_operation": "EXECUTED_IN_MODEL", "operational_shape": "RECONSTRUCTED", "conceptual_operational_shape": "RECONSTRUCTED"}, {"real_operation": "CRITERION_NEGATIVE"}, {"accuracy": "1.0", "spike": "fired", "classification_correct": "True"}):
        got = attribute(ops)  # whatever the operational states, the Gaisho levels do not move without a bearer, an interval and independent evidence
        assert got["gaisho_attribution"] == base["gaisho_attribution"] and got["gaisho_operational_shape"]["state"] == "NOT_ESTABLISHED"
    for premise, conclusion in (("spike_fired", "gaisho_fired"), ("ai_internal_state_changed", "thought_established"), ("concept_classification_succeeded", "gaisho_established"), ("accuracy_improved", "knowledge_established")):
        assert refuse(premise, conclusion)


def test_no_condition_of_any_executed_domain_has_an_attribution_or_an_established_gaisho_shape():
    for dom_id in ("001-knowledge", "002-bias", "003-freedom", "005-credit"):
        out = run_experiment({"domain": dom_id, "seeds": [1, 2, 3]})
        assert out["executed"] and all(v["gaisho_attribution"]["state"] == "UNRESOLVED" and v["gaisho_operational_shape"]["state"] == "NOT_ESTABLISHED" for v in out["levels"].values()), dom_id
        assert all(t["attribution"] == "UNRESOLVED" for t in out.get("attribution_tests", [])), dom_id


def test_the_api_traces_the_construction_and_reads_the_difference(monkeypatch):
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    body = {"domain": "001-knowledge", "seeds": [1, 2, 3], "conditions": [RESPONSIVE, FEEDBACK]}
    e = c.post("/api/gaisho/construction", json={**body, "condition": RESPONSIVE, "snapshot": "end"}).json()
    assert e["counts"]["cells_total"] == 91 and e["counts"]["edges_drawn"] == 162 and e["counts_consistent"] is True and len(e["cells"]) == 91
    assert c.post("/api/gaisho/construction", json={**body, "condition": "nope", "snapshot": "end"}).status_code == 422
    assert c.post("/api/gaisho/construction", json={"domain": "004-body", "condition": "x", "snapshot": "end"}).status_code == 422
    r = c.post("/api/gaisho/compare-shapes", json={**body, "first": {"condition": FEEDBACK, "snapshot": "start"}, "second": {"condition": FEEDBACK, "snapshot": "end"}}).json()
    assert r["reading"]["real_operation"].startswith("OPERATION_CHANGED")
    r = c.post("/api/gaisho/compare-shapes", json={**body, "first": {"condition": RESPONSIVE, "snapshot": "start"}, "second": {"condition": RESPONSIVE, "snapshot": "end"}}).json()
    assert r["reading"]["real_operation"].startswith("SAME_OPERATION") and r["reading"]["recorded_observation"]["reading"] == "WITHIN_SAMPLING_NOISE"
    co = c.post("/api/gaisho/compare-observations", json={**body, "condition": RESPONSIVE, "first": {}, "second": {"scale": 2}}).json()
    assert co["change_kinds"]["real_operation"] == "SAME"
    sp = c.get("/api/gaisho/spec").json()
    assert {x["status"] for x in sp["claims"]} == {"SUPPORTED_IN_MODEL", "LIMITED_OR_NEGATIVE", "UNTESTED_PHILOSOPHICAL_HYPOTHESIS"}


def test_the_saved_results_are_untouched_by_the_additions():
    """The construction readings are not part of a record: the saved digests of every executed domain still reproduce."""
    saved = json.loads(SAVED.read_text())
    for dom_id in ("001-knowledge", "002-bias", "003-freedom", "005-credit"):
        rec = saved["domains"][dom_id]
        assert run_experiment(rec["spec"])["digest"] == rec["digest"], dom_id


def test_the_same_specification_gives_the_same_record_whatever_writes_its_numbers():
    """Found on the real screen: a browser writes 0.0 as 0, and the digest told them apart, so the UI's run of the saved specification did not reproduce its digest. The observation is cast to its declared types."""
    saved = json.loads(SAVED.read_text())["domains"]["002-bias"]
    obs_js = {**FULL.asdict(), "sensor_noise": 0, "probe": 0, "scale": 1.0, "temporal_window": 40.0, "memory": 1}  # what a JSON client may send
    obs_js["sensor_channels"], obs_js["boundary"] = list(obs_js["sensor_channels"]), list(obs_js["boundary"])
    a = run_experiment({**saved["spec"], "observation": obs_js})
    assert a["digest"] == saved["digest"] and json.loads(json.dumps(a["spec"]["observation"])) == saved["spec"]["observation"]
    o = observation_from(obs_js)
    assert isinstance(o.sensor_noise, float) and isinstance(o.probe, float) and isinstance(o.scale, int) and isinstance(o.temporal_window, int) and o.memory is True


# ------------------------------------------------------------------------------------------------ the security invariants of the routes (reviewed one by one, not only listed)
def _gaisho_routes():
    from xzr.service import app as app_mod

    out = []
    for r in app_mod.app.routes:
        out += list(r.original_router.routes) if hasattr(r, "original_router") else [r]
    return [(m, r.path) for r in out if getattr(r, "path", "").startswith("/api/gaisho") for m in sorted(getattr(r, "methods", ()) or ()) if m not in ("HEAD", "OPTIONS")]


def test_every_gaisho_route_refuses_before_it_computes_when_public_or_cross_origin(monkeypatch):
    """The routes run CPU-bound experiments: the refusal must come BEFORE any computation, for every route (found by enumerating the app, so a new route that forgets local_only fails here)."""
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod
    from xzr.service import gaisho as svc
    from xzr.service import studies as studies_mod

    def boom(*a, **k):
        raise AssertionError("an experiment was computed for a refused request")
    for name in ("run_experiment", "compare_observations", "restore", "figure_svg", "explain_shape", "compare_models", "run_countermodels", "replay_cell"):
        monkeypatch.setattr(svc, name, boom)
    routes = _gaisho_routes()
    assert {p for _, p in routes} == {f"/api/gaisho/{x}" for x in ("spec", "run", "compare-observations", "compare-shapes", "figure", "restore", "construction", "comparators", "countermodels", "body-snn")}
    body = {"domain": "001-knowledge", "seeds": [1, 2], "condition": RESPONSIVE, "snapshot": "end", "spec": {"domain": "001-knowledge"}, "digest": "x", "first": {}, "second": {}}
    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    call = lambda m, p, **kw: c.request(m, p, json=body if m == "POST" else None, **kw)  # noqa: E731
    for m, p in routes:
        assert call(m, p, headers={"origin": "http://evil.example"}).status_code == 403, (m, p)
    monkeypatch.setattr(studies_mod, "LIMITS", dataclasses.replace(studies_mod.LIMITS, public=True))
    for m, p in routes:
        assert call(m, p).status_code == 403, (m, p)


def test_the_gaisho_code_touches_no_file_no_network_and_starts_no_process():
    """The routes read and write nothing: no file access, no network, no subprocess, no dynamic code, in the engine or in its service (the saved results are read by tests and by the script only)."""
    import re

    root = Path(__file__).resolve().parents[1] / "xzr"
    sources = {p.name: p.read_text() for p in [*(root / "gaisho").glob("*.py"), root / "service" / "gaisho.py"] if p.name not in ("bodylink.py", "snnlink.py")}  # the two reviewed exceptions (tests/test_gaisho_body.py)
    forbidden = r"\b(open|exec|eval|compile|__import__)\(|\b(subprocess|socket|urllib|requests|httpx|shutil|tempfile|pathlib|os\.system|os\.popen|importlib)\b|\.(write_text|write_bytes|read_text|read_bytes|unlink|mkdir)\("
    for name, src in sources.items():
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
        code = re.sub(r'""".*?"""', "", code, flags=re.S)  # docstrings may name what the code does not do
        assert not re.search(forbidden, code), (name, re.search(forbidden, code).group(0))


def test_the_cost_of_a_request_is_bounded_by_seeds_distinct_conditions_and_concurrency(monkeypatch):
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod
    from xzr.service import gaisho as svc

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    k = "001-knowledge"
    assert c.post("/api/gaisho/run", json={"domain": k, "conditions": [RESPONSIVE] * 50}).status_code == 422  # a repeated condition would repeat its runs
    assert c.post("/api/gaisho/run", json={"domain": k, "conditions": []}).status_code == 422
    assert c.post("/api/gaisho/run", json={"domain": k, "conditions": [1]}).status_code == 422
    assert c.post("/api/gaisho/run", json={"domain": "005-credit", "seeds": list(range(1, 12))}).status_code == 422  # the institution engine costs about 1.8 s per seed and condition
    assert c.post("/api/gaisho/run", json={"domain": k, "seeds": list(range(1, 22))}).status_code == 422
    with pytest.raises(ValueError):
        run_experiment({"domain": "005-credit", "seeds": list(range(1, 12))})  # the engine refuses it too, whoever calls it
    with pytest.raises(ValueError):
        run_experiment({"domain": k, "conditions": [RESPONSIVE, RESPONSIVE]})
    held = [svc._BUSY.acquire(blocking=False) for _ in range(2)]
    try:
        assert all(held)
        r = c.post("/api/gaisho/run", json={"domain": k, "seeds": [1, 2], "conditions": [RESPONSIVE]})
        assert r.status_code == 429  # a third computation is refused, not queued
        assert c.get("/api/gaisho/spec").status_code == 200  # reading the specification costs nothing
    finally:
        for _ in held:
            svc._BUSY.release()
    assert c.post("/api/gaisho/run", json={"domain": k, "seeds": [1, 2], "conditions": [RESPONSIVE]}).status_code == 200


def test_the_figure_is_inert_markup_whatever_the_request_says(dom, full):
    hostile = '"><script>alert(1)</script><img src=x onerror=alert(1)>'
    rec = {"result": full, "shapes": {c: {s: build_shape(full, c, s, {"x": dom.x_name, "y": dom.y_name}) for s in dom.snapshots} for c in full["conditions"]}, "axes": {"x": dom.x_name, "y": dom.y_name},
           "figure_kind": "EXECUTED_COMPUTATIONAL_EXPERIMENT", "model_version": MODEL_VERSION, "limits": "l", "digest": "d" * 64, "negative_results": []}
    svg = figure_svg(rec, hostile)
    assert "<script" not in svg and "<img" not in svg and "&lt;script&gt;" in svg and "&lt;img" in svg


# ------------------------------------------------------------------------------------------------ the comparators: what each is given, and what the results do and do not say
def test_the_comparators_are_declared_and_the_records_comparison_is_unchanged(dom):
    from xzr.gaisho.compare import COMPARATORS

    base, ext = compare_models(dom, SEEDS), compare_models(dom, SEEDS, extended=True)
    assert base["digest"] == compare_models(dom, SEEDS)["digest"] and "comparators" not in base  # the record's own comparison (M0, M1, the candidate) is exactly as before
    assert [v["competitor"][:2] for v in ext["rows"][0]["verdicts"]] == ["M0", "M1", "M4"]
    assert {k: v["parameters"] for k, v in COMPARATORS.items()} == {"M0": 1, "M1": 3, "CAND": 2, "M4": 2}  # CAND and M4 have the same number of parameters
    assert all(v["history"] is False and v["information"] == "end-snapshot training cells" for v in COMPARATORS.values()) and "attention" in ext["not_run"]
    by = {r["condition"]: {v["competitor"][:2]: v["verdict"] for v in r["verdicts"]} for r in ext["rows"]}
    # with the same number of parameters the right single factor wins: the candidate construction (evidence alone) has no advantage of its own
    assert by[CUE]["M4"] == "HARMFUL" and by[NOFEEDBACK]["M4"] == "HARMFUL" and by[RESPONSIVE]["M4"] == "NON_REDUNDANT"
    assert by[RESPONSIVE]["M1"] == "REDUNDANT" and by[BASE]["M1"] == "REDUNDANT" and by[CUE]["M1"] == "HARMFUL"
    assert "nested model cannot beat" in ext["reading"]


def test_the_comparators_endpoint_is_bounded_and_only_for_the_knowledge_domain():
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    r = c.post("/api/gaisho/comparators", json={"domain": "001-knowledge", "seeds": [1, 2, 3]}).json()
    assert r["comparators"]["M4"]["parameters"] == 2 and len(r["rows"]) == 6
    assert c.post("/api/gaisho/comparators", json={"domain": "002-bias"}).status_code == 422
    assert c.post("/api/gaisho/comparators", json={"domain": "001-knowledge", "conditions": [RESPONSIVE]}).status_code == 422


# ------------------------------------------------------------------------------------------------ cell / edge / branch / unresolved / face: which layer each is
def test_each_element_of_a_shape_is_classified_by_layer_and_the_first_run_results_are_kept(dom, full):
    from xzr.gaisho.construction import LAYERS

    assert set(LAYERS) == {"cell", "edge", "branch_point", "unresolved", "surface_between_cells"}
    assert all(set(v) == {"real_operation", "recorded_observation", "reconstructed_relation", "display"} for v in LAYERS.values())
    s = build_shape(full, CUE, "end", {"x": dom.x_name, "y": dom.y_name})
    assert {v["source"]["provenance"] for v in s["vertices"]} == {"RECORDED_OBSERVATION"}  # a cell is a recorded observation, not a difference between interventions
    assert {e["source"]["provenance"] for e in s["edges"] + s["cuts"]} == {"RECONSTRUCTED_RELATION"} and {b["source"]["provenance"] for b in s["branch"]} == {"RECONSTRUCTED_RELATION"}
    assert {u["provenance"] for u in build_shape(run_domain(dom, Observation(scale=2), SEEDS[:2], [CUE]), CUE, "end", {"x": dom.x_name, "y": dom.y_name})["unresolved"]} == {"VISUALIZATION_PROJECTION"}


def test_correcting_the_cell_label_changed_digests_and_nothing_else():
    """The first run (before the label correction) is kept as experiments_first_run.json: every number, relation, verdict and negative result is identical; only the digests (which cover the label) differ."""
    first = json.loads(SAVED.with_name("experiments_first_run.json").read_text())
    now = json.loads(SAVED.read_text())

    def strip(o):
        if isinstance(o, dict):  # the title (retitled after R37) and the failure-registry labels (added after R37) are the only new text
            return {k: strip(v) for k, v in o.items() if "digest" not in k and k not in ("title", "registry", "registry_meaning", "note_on_domains")}
        return [strip(x) for x in o] if isinstance(o, list) else o
    for k in ("001-knowledge", "002-bias", "003-freedom", "005-credit"):
        assert strip(first["domains"][k]["result"]) == strip(now["domains"][k]["result"]), k
        assert strip(first["domains"][k]["negative_results"]) == strip(now["domains"][k]["negative_results"]), k
        assert first["domains"][k]["digest"] != now["domains"][k]["digest"], k
    assert strip(first["domains"]["001-knowledge"]["models"]) == strip(now["domains"]["001-knowledge"]["models"]) and strip(first["knowledge_observation_sensitivity"]) == strip(now["knowledge_observation_sensitivity"])


def test_the_credit_domain_names_the_engine_outputs_it_depends_on(monkeypatch):
    """005-credit reads process.complement (TRUTH-ERROR phase 4) and process.labels (phase 5, commit 1af5700): an engine without them is refused with a message, not read as zero."""
    from xzr.gaisho import domains as D
    from xzr.truth_error import institution as I  # noqa: E741

    d = D.CreditDomain()
    real = I.run
    monkeypatch.setattr(I, "run", lambda cfg: {**real(cfg), "process": {k: v for k, v in real(cfg)["process"].items() if k != "labels"}})
    with pytest.raises(RuntimeError, match="1af5700"):
        d.simulate(next(iter(d.conditions)), 1, FULL)


# ------------------------------------------------------------------------------------------------ correspondence with the manuscript GAISHO R37 (read 2026-11-05; see r37.py for what was and was not read)
def test_the_attribution_carries_r37s_applicability_gate_and_stays_unresolved():
    from xzr.gaisho.r37 import LEVEL_TERMS

    out = run_experiment({"domain": "001-knowledge", "seeds": list(SEEDS[:3]), "conditions": [RESPONSIVE, CUE]})
    for lv in out["levels"].values():
        a = lv["gaisho_attribution"]
        assert a["state"] == "UNRESOLVED" and a["applicability_gate"].startswith("NOT_PASSED") and "A_G(b,t,w;e,K)" in a["r37_term"]  # unresolved, not defeated-for-K: the gate fails before any A_G value
        assert "NO R37 TERM" in lv["gaisho_operational_shape"]["r37_term"] and lv["gaisho_operational_shape"]["state"] == "NOT_ESTABLISHED"
    assert [k for k, v in LEVEL_TERMS.items() if not v["in_r37"]] == ["gaisho_operational_shape"]
    ok = attribute({"real_operation": "EXECUTED_IN_MODEL"}, bearer="b", historical_interval="i", independent_evidence=["e"])
    assert ok["gaisho_attribution"]["applicability_gate"] == "PASSED_BY_RESEARCHER_ASSERTION" and ok["gaisho_attribution"]["state"] == "ASSERTED_BY_RESEARCHER"


def test_the_six_registers_are_kept_apart_per_domain():
    from xzr.gaisho.r37 import registers

    r = registers("001-knowledge")
    assert set(r) == {"S", "Occ_G", "Det_D", "A_G", "C", "P", "E", "N", "I"}
    assert r["Occ_G"]["lab"] == "NOT_ASSESSED" and r["A_G"]["lab"] == "UNRESOLVED" and r["A_G"]["applicability_gate"] == "NOT_PASSED" and r["N"]["lab"] == "NOT_MODELLED" and "entitlement" in r["N"]["note"]
    assert registers("005-credit")["I"]["lab"] == "EXECUTED_IN_MODEL" and r["I"]["lab"] == "NOT_MODELLED"  # execution exists only where the TRUTH-ERROR institution is run, and is not a standing
    assert registers("004-body")["P"]["lab"] == "EXECUTED_IN_MODEL" and "not a thinker" in registers("004-body")["P"]["note"] and r["P"]["lab"] == "NOT_MODELLED"
    assert all(registers(d)["A_G"]["lab"] == "UNRESOLVED" and registers(d)["Occ_G"]["lab"] == "NOT_ASSESSED" for d in ("001-knowledge", "002-bias", "003-freedom", "004-body", "005-credit"))


def test_every_kept_negative_result_belongs_to_one_r37_failure_registry():
    from xzr.gaisho.r37 import FAILURE_REGISTRIES, NEGATIVE_KIND_TO_REGISTRY

    out = run_experiment({"domain": "001-knowledge", "seeds": list(SEEDS[:3])})
    for n in out["negative_results"]:
        assert n["registry"] == NEGATIVE_KIND_TO_REGISTRY[n["kind"]][0] and (n["registry"] in FAILURE_REGISTRIES or n["registry"] in ("F4-access", "NOT_RUN")), n
    kinds = {n["kind"]: n["registry"] for n in out["negative_results"]}
    assert kinds["NOT_DETECTED"] == "F1" and kinds["CRITERION_NEGATIVE"] == "F1" and kinds["NOT_DONE"] == "NOT_RUN" and kinds.get("UNOBSERVED", "F4-access") == "F4-access"
    assert set(NEGATIVE_KIND_TO_REGISTRY) >= {"REDUNDANT", "HARMFUL", "UNRESOLVED"} and NEGATIVE_KIND_TO_REGISTRY["REDUNDANT"][0] == "F2"  # rival equivalence is its own registry and is not moved into the others


def test_the_comparators_state_their_inquiry_q_and_never_claim_r37s_third_outcome(dom):
    ext = compare_models(dom, SEEDS, extended=True)
    assert {"target_discrimination", "boundaries", "observation_channels", "time_horizon", "admissible_interventions", "history", "resources", "endpoints"} <= set(ext["Q"])
    assert "not about a Gaisho" in ext["Q"]["target_discrimination"] and ext["Q"]["history"].startswith("none")
    assert ext["r37_outcome_classes"]["iii"].startswith("a distinct, independently validated difference") and "NOT ASSESSED" in ext["r37_outcome_classes"]["iii"]
    assert "Q" not in compare_models(dom, SEEDS)  # the record's own comparison is exactly as before


def test_the_r37_constraints_are_stated_with_their_status_and_the_arms_with_missing_cells_marked():
    from xzr.gaisho.r37 import ARMS, CONSTRAINTS

    assert len({c["id"] for c in CONSTRAINTS}) == len(CONSTRAINTS) and {c["status"] for c in CONSTRAINTS} <= {"IMPLEMENTED", "PARTIAL", "NOT_IMPLEMENTED"}
    assert all(c["where"] and c["constraint"] and c["how"] for c in CONSTRAINTS)
    by = {c["id"]: c["status"] for c in CONSTRAINTS}
    assert by["R6"] == "NOT_IMPLEMENTED" and by["R8"] == "NOT_IMPLEMENTED" and by["R15"] == "PARTIAL"  # R37's comparative claims and Gaisho ignition are not done; the formation histories only as finite models
    assert set(ARMS) == set("ABCDEFG") and {k for k, v in ARMS.items() if v["lab"] == "NOT_EXECUTED"} == set("BCDEF") and {k for k, v in ARMS.items() if v["lab"] == "PARTIAL"} == {"A", "G"}


def test_the_claims_do_not_register_an_r37_proposition_as_proved_and_do_not_reuse_r37s_h_identifiers():
    from xzr.gaisho.claims import CLAIMS, SUPPORTED_IN_MODEL, UNTESTED_HYPOTHESIS

    ids = [c["id"] for c in CLAIMS]
    assert not {"H1", "H2", "H3", "H4"} & set(ids) and {"U1", "U2", "U3", "U4", "R37-H1..H3"} <= set(ids)  # R37's H1-H3 are formation histories, not the laboratory's claims
    claims = {c["id"]: c for c in CLAIMS}
    assert claims["U3"]["status"] == UNTESTED_HYPOTHESIS and "UNVERIFIED" in claims["U3"]["rests_on"] and "necessary and sufficient" in claims["U3"]["claim"] and "Not to be read as an R37-proved or Dictionary-proved proposition" in claims["U3"]["rests_on"]
    assert "71-entry" in claims["U3"]["rests_on"] and "not supported" in claims["U3"]["rests_on"] and "no Gaisho entry" in claims["U3"]["rests_on"]  # checked against the file that exists, not against the edition R37 cites
    assert claims["R37-H1..H3"]["status"] == UNTESTED_HYPOTHESIS and "formation histories" in claims["R37-H1..H3"]["claim"]
    assert all("R37 proves" not in c["claim"] and "proved by R37" not in c["claim"] for c in CLAIMS) and all(c["status"] != SUPPORTED_IN_MODEL or "R37" not in c["claim"] for c in CLAIMS)


def test_the_dictionary_block_cites_only_entries_that_were_read_in_full_and_states_which_edition_it_is():
    from xzr.gaisho import dictionary as D

    assert set(D.READ_IN_FULL).isdisjoint(D.HEADINGS_ONLY) and set(D.READ_IN_FULL) | set(D.HEADINGS_ONLY) | {2} == set(range(1, 72))  # every entry is read in full, read in part (002) or headings only
    ids = [c["id"] for c in D.CONSTRAINTS]
    assert ids == [f"D{i}" for i in range(1, 10)] and {c["status"] for c in D.CONSTRAINTS} <= {"IMPLEMENTED", "PARTIAL", "NOT_IMPLEMENTED"}
    for c in D.CONSTRAINTS:
        assert c["constraint"] and c["how"] and c["entries"]
        assert set(c["entries"]) <= set(D.READ_IN_FULL), c["id"]  # a constraint is never stated from an entry of which only the heading was seen
        assert set(c["entries"]) <= set(D.HEADWORDS), c["id"]
    assert {c["id"]: c["status"] for c in D.CONSTRAINTS}["D7"] == "NOT_IMPLEMENTED" and {c["id"]: c["status"] for c in D.CONSTRAINTS}["D8"] == "PARTIAL"  # B2 has none of XenoSNN's controls; only single-block swaps of the two bodies were matched
    ref = D.DICTIONARY_REF
    assert ref["entries_in_file"] == 71 and ref["gaisho_in_file"] is False and "112 entries" in ref["edition_cited_by_r37"] and len(ref["sha256"]) == 64
    assert "not the 112-entry" in D.EDITION_STATUS and "Gaisho" in D.EDITION_STATUS and "072-112" in D.EDITION_STATUS
    assert D.HEADWORDS[22] == "Non-Accidental Success" and D.HEADWORDS[58] == "XenoSNN" and D.HEADWORDS[60] == "XenoBody"


def test_the_dictionary_block_is_served_by_the_spec_and_is_not_in_any_record():
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    spec = c.get("/api/gaisho/spec").json()
    d = spec["dictionary"]
    assert d["reference"]["entries_in_file"] == 71 and [x["id"] for x in d["constraints"]] == [f"D{i}" for i in range(1, 10)] and all(isinstance(x["entries"], list) for x in d["constraints"])
    assert "71-entry" in spec["source_status"] and "not the 112-entry" in spec["source_status"]
    out = run_experiment({"domain": "001-knowledge", "seeds": [1, 2, 3], "conditions": [RESPONSIVE]})
    assert "dictionary" not in out and "Dictionary" not in str(out["r37"].get("reference", ""))  # the record (and so its digest) does not depend on the file read afterwards


def test_the_research_objects_label_ignition_maintenance_expiry_and_reignition_as_operational_analogues():
    out = run_experiment({"domain": "001-knowledge", "seeds": list(SEEDS[:3]), "conditions": [RESPONSIVE]})
    ro = out["research_objects"][RESPONSIVE]
    assert ro["candidate"].startswith("OPERATIONAL REPORT, NOT A GAISHO CANDIDATE")
    for f in ("ignition_conditions", "maintenance_conditions"):
        assert all("OPERATIONAL ANALOGUE ONLY" in x for x in ro[f])
    assert all("OPERATIONAL ANALOGUE ONLY" in x["meaning"] for x in ro["transformation_expiry_conditions"] + ro["history_and_reignition"])
    assert out["result"]["title"] == "KNOWLEDGE — NON-ACCIDENTAL SUCCESS AS AN OPERATIONAL DIFFERENCE"


def test_the_first_runs_are_kept_and_the_r37_alignment_changed_text_and_digests_only():
    saved = json.loads(SAVED.read_text())
    before = json.loads(SAVED.with_name("experiments_before_r37_alignment.json").read_text())

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if "digest" not in k and k not in ("title", "registry", "registry_meaning", "r37_term", "applicability_gate", "r37", "note_on_domains")}
        return [strip(x) for x in o] if isinstance(o, list) else o
    for k in ("001-knowledge", "002-bias", "003-freedom", "005-credit"):
        assert strip(before["domains"][k]["result"]) == strip(saved["domains"][k]["result"]), k
        assert strip(before["domains"][k]["negative_results"]) == strip(saved["domains"][k]["negative_results"]), k
        assert before["domains"][k]["digest"] != saved["domains"][k]["digest"], k
    assert strip(before["knowledge_observation_sensitivity"]) == strip(saved["knowledge_observation_sensitivity"])


def test_the_api_exposes_the_r37_correspondence_and_says_what_was_read():
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    sp = TestClient(app_mod.app, headers={"origin": "http://testserver"}).get("/api/gaisho/spec").json()
    assert "read on 2026-11-05" in sp["source_status"] and "NOT a full-text verification" in sp["source_status"] and "R37 was not found" not in sp["source_status"]
    assert {c["id"] for c in sp["r37"]["constraints"]} >= {"R1", "R2", "R16"} and set(sp["r37"]["arms"]) == set("ABCDEFG") and set(sp["r37"]["failure_registries"]) == {"F1", "F2", "F3", "F4", "F5"}


def test_a_record_does_not_depend_on_whether_the_body_link_is_configured(monkeypatch):
    """Found on the real screen with the XB-TRO link set: the knowledge record's digest differed from the saved one because its 'domains not executed' list read the environment. A record is a function of its specification only."""
    from xzr.gaisho import bodylink

    spec = {"domain": "001-knowledge", "seeds": [1, 2, 3], "conditions": [RESPONSIVE]}
    monkeypatch.delenv(bodylink.ENV, raising=False)
    bodylink._CACHE.clear()
    a = run_experiment(spec)["digest"]
    xb = Path("/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend/xzr/xbtro")
    if (xb / "engine.py").is_file():
        monkeypatch.setenv(bodylink.ENV, str(xb))
        bodylink._CACHE.clear()
        assert run_experiment(spec)["digest"] == a
    bodylink._CACHE.clear()


# ------------------------------------------------------------------------------------------------ R37's finite countermodels, made executable (countermodels.py)
def test_the_questioning_models_have_the_same_record_and_different_histories():
    from fractions import Fraction

    from xzr.gaisho.countermodels import questioning_models

    q = questioning_models()["models"]
    r = q["report"]
    assert r["same_recorded_joint"] is True and r["joint"] == {"(0,BOT)": "1/2", "(1,0)": "1/4", "(1,1)": "1/4"}  # R37 A.3: P(X=0,R=bot)=1/2, P(1,0)=1/4, P(1,1)=1/4
    assert r["P_E0_equals_1"] == {"H_R": "1/2", "H_F": "0"} and r["P_E0_identified_by_the_record"] is False
    c = q["common_endpoint"]
    assert c["same_recorded_joint"] is True and c["joint"] == {"(0,0)": "1/2", "(1,0)": "1/4", "(1,1)": "1/4"} and "(0,1)" not in c["joint"]
    assert c["effect_identified"] is True and set(c["effect_of_the_question_on_Y"].values()) == {"1/2"} and Fraction(c["P_E0_equals_1"]["H_R*"]) == Fraction(1, 2) and Fraction(c["P_E0_equals_1"]["H_F*"]) == 0
    assert "not modelled" in questioning_models()["limits"] and "third" in questioning_models()["limits"]  # R37's third history is not invented


def test_no_report_only_rule_decides_the_prior_orientation_and_the_probe_is_what_would_break_the_equivalence():
    from xzr.gaisho.countermodels import report_indeterminacy, z_equivalence

    ri = report_indeterminacy()
    assert ri["rules_that_decide_P_on_every_history"] == 0 and ri["report_only_rules_checked"] == 8 and len(ri["witness_pair"]) == 1
    z = z_equivalence()
    assert z["Z_equivalent_on_Z"] is True and z["Z_equivalent_with_probe"] is False and "validity is stipulated" in z["reading"]


def test_the_r12_structural_study_is_reexecuted_and_agrees_with_what_r37_reports():
    from xzr.gaisho.countermodels import R37_REPORTED, scm_equal_records

    s = scm_equal_records()
    assert s["worlds"] == 524_288 == R37_REPORTED["seeds"] * R37_REPORTED["units_per_seed"] * 1 and s["observational_records_identical_in_every_seed"] is True and s["masked_records_identical_in_every_seed"] is True
    assert s["effect_of_do_M_in_B"] == {"mean": 0.0, "interval95": [0.0, 0.0], "seeds": 128}  # exactly zero for every seed
    assert s["executed_sham_relabel_effect_is_zero"] is True  # the R13 control is executed, not entered analytically
    assert abs(s["effect_of_do_M_in_A"]["mean"] - 0.8) < 0.003 and abs(s["association"]["mean"] - 0.8) < 0.003  # 1 - 2 P(E=1)
    cmp = s["compared_with_r37"]
    assert cmp["association_interval_overlaps"] and cmp["effect_A_interval_overlaps"] and cmp["effect_B_equal"] and "not of the seed-level numbers" in cmp["note"]
    assert "Gaisho attribution unresolved" in s["reading"]


def test_renaming_and_an_executed_update_are_different_interventions():
    from xzr.gaisho.countermodels import label_control

    g = label_control()["gates"]
    a, b = g["A (the gate reads the marker)"], g["B (the gate does not read the marker)"]
    assert a["renaming_changes_outcomes"] == 0 and b["renaming_changes_outcomes"] == 0 and a["executed_update_changes_outcomes"] == a["units"] and b["executed_update_changes_outcomes"] == 0


def test_the_countermodels_never_support_an_attribution_and_the_api_bounds_them():
    from fastapi.testclient import TestClient

    from xzr.gaisho.countermodels import run_all
    from xzr.service import app as app_mod

    r = run_all(seeds=8, units=256)
    assert r["supports_a_gaisho_attribution"] is False and r["attribution"] == "UNRESOLVED" and "do not simulate Gaisho" in r["scope"]
    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    j = c.post("/api/gaisho/countermodels", json={"seeds": 8, "units": 256}).json()
    assert j["digest"] == r["digest"] and j["questioning"]["models"]["report"]["same_recorded_joint"] is True
    for bad in ({"seeds": 1}, {"seeds": 129}, {"units": 63}, {"units": 4097}, {"seeds": True}, {"seeds": "8"}):
        assert c.post("/api/gaisho/countermodels", json=bad).status_code == 422, bad


def test_the_new_r37_constraints_are_stated_with_their_status():
    from xzr.gaisho.r37 import CONSTRAINTS

    by = {c["id"]: c["status"] for c in CONSTRAINTS}
    assert by["R15"] == "PARTIAL" and by["R17"] == "IMPLEMENTED" and by["R18"] == "IMPLEMENTED" and by["R19"] == "IMPLEMENTED" and by["R20"] == "NOT_IMPLEMENTED"
    assert by["R6"] == "NOT_IMPLEMENTED" and by["R8"] == "NOT_IMPLEMENTED"  # the comparative claims and Gaisho ignition remain undone
