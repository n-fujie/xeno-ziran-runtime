"""TEOO Phase 3: pre-registered protocols (freeze, amend, replay), the confirmatory / exploratory distinction, and statistics that do not assume independent observations."""

from __future__ import annotations

import copy

import pytest

from xzr.teoo import protocol as PR
from xzr.teoo import stats as S


def proto(**over):
    p = PR.new_protocol(experiment_id="exp-t", hypotheses=[{"id": "H1", "statement": "B differs from A"}], targets=["v"], instrument_conditions={"observation_config_version": 1}, control_condition="A", conditions=["A", "B"],
                        seeds=[1, 2, 3], trials_per_condition=6, stopping_rule={"type": "fixed-n"}, outcomes={"primary": ["value"], "secondary": []},
                        analyses=[{"id": "AN1", "hypothesis": "H1", "outcome": "value", "method": "randomization-test", "confirmatory": True, "compare": "B", "n_perm": 1000, "seed": 0}], multiplicity="none-declared-single-test",
                        failure_conditions=["no valid trial"], reproduction={"generator": "synthetic-two-condition/1", "steps": ["run"]})
    p.update(over)
    return p


def test_a_protocol_names_everything_a_pre_registration_needs():
    assert PR.validate(proto()) == []
    for k in PR.REQUIRED:
        assert any(k in m for m in PR.validate(proto(**{k: None}))), k
    assert PR.validate(proto(conditions=["A"])) and PR.validate(proto(control_condition="C")) and PR.validate(proto(seeds=[1, 1]))
    assert PR.validate(proto(analyses=[{"id": "X", "hypothesis": "H9", "outcome": "v", "method": "randomization-test"}])) and PR.validate(proto(analyses=[{"id": "X", "hypothesis": "H1", "outcome": "v", "method": "anova"}]))
    two = [{"id": "A1", "hypothesis": "H1", "outcome": "v", "method": "randomization-test", "confirmatory": True}, {"id": "A2", "hypothesis": "H1", "outcome": "v", "method": "randomization-test", "confirmatory": True}]
    assert any("multiplicity" in m for m in PR.validate(proto(analyses=two))) and PR.validate(proto(analyses=two, multiplicity="holm")) == []


def test_a_frozen_protocol_cannot_be_changed_and_a_change_is_a_new_version_with_its_parent_and_reason():
    reg = PR.ProtocolRegistry()
    reg.register(proto())
    reg.freeze("exp-t", 1, 10.0)
    with pytest.raises(ValueError):
        reg.freeze("exp-t", 1, 11.0)
    with pytest.raises(ValueError):
        reg.register(proto())  # the same version cannot be registered twice
    v2 = reg.amend("exp-t", 1, {"trials_per_condition": 12}, "more trials")
    assert v2["version"] == 2 and v2["parent_version"] == 1 and v2["change_reason"] == "more trials" and reg.get("exp-t", 1)["trials_per_condition"] == 6 and reg.get("exp-t", 2)["trials_per_condition"] == 12
    with pytest.raises(ValueError):
        reg.amend("exp-t", 1, {"seeds": [9]}, "")
    assert reg.verify() == []
    tampered = copy.deepcopy(reg.log.entries[0])
    tampered["body"]["protocol"]["seeds"] = [9, 9, 9]
    reg.log.entries[0] = tampered
    assert reg.verify()  # an edit of the stored protocol is detected (chain and digest)


def test_an_analysis_is_confirmatory_only_if_declared_in_a_version_frozen_before_the_first_data():
    reg = PR.ProtocolRegistry()
    reg.register(proto())
    assert reg.analysis_class("exp-t", 1, "AN1") == "exploratory (the protocol was not frozen)"
    assert reg.analysis_class("exp-t", 1, "AN9") == "exploratory (not declared in this version)"
    reg.freeze("exp-t", 1, 10.0)
    assert reg.analysis_class("exp-t", 1, "AN1") == "confirmatory"
    reg.note_first_data("exp-t", 1, 5.0)  # data existed before the freeze
    assert reg.analysis_class("exp-t", 1, "AN1") == "exploratory (declared after the first data)"
    reg2 = PR.ProtocolRegistry()
    reg2.register(proto(analyses=[{"id": "AN1", "hypothesis": "H1", "outcome": "value", "method": "randomization-test", "confirmatory": False}]))
    reg2.freeze("exp-t", 1, 10.0)
    assert reg2.analysis_class("exp-t", 1, "AN1") == "exploratory (declared but not marked confirmatory)"


def test_the_classification_agrees_with_the_study_layers_own_rule_on_the_same_cases():
    from xzr.study.analysis import evidence_class

    doc = {"mode": "confirmatory"}
    reg = {"contrasts": [{"id": "AN1"}], "freeze": True}
    assert evidence_class(doc, reg, [], "AN1") == "confirmatory" and evidence_class(doc, reg, [{"runs_started": True}], "AN1").startswith("exploratory")
    assert evidence_class(doc, {"contrasts": [], "freeze": True}, [], "AN1").startswith("exploratory")  # declared / frozen / late: the same three questions as the TEOO registry asks


def test_a_synthetic_experiment_replays_exactly_and_a_different_seed_or_parameter_does_not():
    p = proto()
    params = {"baseline": 10.0, "shifts": {"B": 2.0}, "noise": 1.0}
    run = PR.run_protocol(p, params=params)
    assert run["n_trials"] == 2 * 6 * 3 and {t["condition"] for t in run["trials"]} == {"A", "B"} and all(t["assignment"].startswith("randomized") for t in run["trials"])
    assert PR.reproduce(p, run, params=params)["identical"] is True
    assert PR.reproduce(p, run, params={**params, "noise": 1.5})["identical"] is False
    assert PR.reproduce(proto(seeds=[1, 2, 4]), run, params=params)["identical"] is False
    assert run["results"]["AN1"]["effect"] > 1.0 and run["results"]["AN1"]["p"] < 0.01 and "SYNTHETIC" in run["generator_note"]


def test_a_null_effect_stays_a_null_result_and_is_kept():
    run = PR.run_protocol(proto(), params={"baseline": 10.0, "shifts": {}, "noise": 1.0})
    r = run["results"]["AN1"]
    assert abs(r["effect"]) < 1.0 and r["p"] > 0.05 and r["inferential"]  # no effect was built in: no effect is found, and the result is reported as it is


def test_the_randomisation_test_is_valid_by_design_and_a_non_randomised_comparison_is_only_descriptive():
    y = [1.0, 1.2, 0.9, 1.1, 3.0, 3.2, 2.9, 3.1]
    lab = ["A"] * 4 + ["B"] * 4
    r = S.randomization_test(y, lab, a="A", b="B", randomized=True, n_perm=5000, seed=1)
    assert r["inferential"] and r["effect"] == pytest.approx(2.0, abs=0.01) and r["p"] < 0.05 and r["p"] == S.randomization_test(y, lab, a="A", b="B", randomized=True, n_perm=5000, seed=1)["p"]
    d = S.randomization_test(y, lab, a="A", b="B", randomized=False)
    assert d["p"] is None and not d["inferential"] and "descriptive" in d["reason"] and d["effect"] == r["effect"]
    few = S.randomization_test([1.0, 2.0, 3.0], ["A", "B", "B"], a="A", b="B", randomized=True)
    assert few["p"] is None and "fewer than two" in few["reason"]
    drift = [float(i) for i in range(12)]  # a trend: strongly autocorrelated; with an unrandomised assignment a warning is raised
    w = S.randomization_test(drift, ["A"] * 6 + ["B"] * 6, a="A", b="B", randomized=False)
    assert w["autocorrelation_warning"] and S.lag1_autocorrelation([1.0, 1.0, 1.0, 1.0]) is None


def test_holm_corrects_a_family_and_leaves_a_missing_p_missing():
    out = S.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert out["a"]["p_holm"] == pytest.approx(0.03) and out["c"]["p_holm"] == pytest.approx(0.06) and out["b"]["p_holm"] == pytest.approx(0.06)  # 3*0.01, 2*0.03, then monotone
    assert out["d"] == {"p": None, "p_holm": None} and all(v["p_holm"] >= v["p"] for k, v in out.items() if k != "d")
    assert S.cohen_d([1, 2, 3], [4, 5, 6]) == pytest.approx(3.0) and S.cohen_d([1], [2, 3]) is None
