"""Tests of the SBS substrate, the observer's records and the comparison (xzr.sbs)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np

from xzr.sbs import comparison as cmp
from xzr.sbs import organisation as org
from xzr.sbs.engine import Config, Sim
from xzr.sbs.lab_stats import holm, paired_t
from xzr.sbs.protocol import PROTOCOL, PROTOCOL_DIGEST, classify

DOCS = Path(__file__).resolve().parents[2] / "docs" / "sbs"


def test_a_run_is_reproduced_exactly_by_its_seeds_and_a_branch_with_the_same_noise_differs_only_by_the_intervention():
    cfg = Config(n=24, eps=1.5)
    a, b = Sim(cfg, 3), Sim(cfg, 3)
    a.step(300)
    b.step(300)
    assert np.array_equal(a.x, b.x)
    c1, c2 = a.clone(11), a.clone(11)
    c1.step(200)
    c2.step(200)
    assert np.array_equal(c1.x, c2.x)  # same noise, same intervention: identical
    c3 = a.clone(11)
    c3.step(200, eps=0.0)
    assert not np.array_equal(c1.x, c3.x)  # the intervention is the only difference


def test_the_substrate_does_not_contain_a_body_a_coupled_gas_condenses_and_an_uncoupled_one_does_not():
    cfg = Config(n=40, eps=1.5)
    coupled, free = Sim(cfg, 5), Sim(cfg, 5)
    coupled.step(5000)
    free.step(5000, eps=0.0)
    assert org.physical(coupled.x, coupled.box)["largest_share"] > org.physical(free.x, free.box)["largest_share"] + 0.2
    src = Path(inspect.getfile(Sim)).read_text()
    assert "body" in src.lower() and "nothing in it is a body" in src  # the module says so


def test_adjusted_rand_index_is_one_for_identical_partitions_and_the_known_value_for_orthogonal_ones():
    a = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
    assert abs(org.adjusted_rand(a, a) - 1.0) < 1e-12
    assert abs(org.adjusted_rand(a, np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])) + 1 / 3) < 1e-12  # orthogonal partitions of a 3 x 3 table: ARI = -1/3 by the formula


def test_the_outcome_classes_follow_the_frozen_thresholds_and_an_unreadable_observation_is_unresolved_not_a_class():
    full = {"groups_tracked": 1, "largest_share": 0.5, "bonds": 50}
    assert classify(full, {"best_overlap": 0.9}, 60, 1.0) == "PERSISTENCE"
    assert classify(full, {"best_overlap": 0.6}, 60, 1.0) == "PARTIAL_RECOVERY"
    assert classify(full, {"best_overlap": 0.2}, 60, 1.0) == "DIFFERENT_ORGANIZATION"
    assert classify({"groups_tracked": 3, "largest_share": 0.3, "bonds": 40}, {"best_overlap": 0.2}, 60, 1.0) == "MULTIPLE_ORGANIZATIONS"
    assert classify({"groups_tracked": 0, "largest_share": 0.02, "bonds": 0}, {"best_overlap": 0.0}, 60, 1.0) == "NO_RECONSTITUTION"
    assert classify(full, {"best_overlap": 0.9}, 60, 0.2) == "UNRESOLVED_OBSERVATION"


def test_the_feature_functions_take_only_an_observed_frame_and_an_intervention_descriptor_so_no_model_can_read_the_simulation():
    for fn in (cmp.features, cmp.descriptor):
        assert "sim" not in inspect.signature(fn).parameters
    assert list(inspect.signature(cmp.features).parameters) == ["model", "frame", "box", "desc"]
    rng = np.random.default_rng(0)
    frame = rng.uniform(0, 15, size=(60, 2))
    desc = cmp.descriptor("heating", 1.2)
    for m, k in (("A", 7), ("B", 7), ("C", 7), ("N", 3)):
        assert cmp.features(m, frame, 15.0, desc).shape == (60, k)
        assert np.array_equal(cmp.features(m, frame, 15.0, desc), cmp.features(m, frame.copy(), 15.0, desc))  # a pure function of the frame


def test_the_models_are_matched_in_capacity_where_the_design_says_so_and_the_null_is_smaller():
    assert {cmp.MODELS[m]["parameters"] for m in "ABC"} == {8} and cmp.MODELS["N"]["parameters"] == 4
    assert cmp.features("A", np.zeros((60, 2)) + np.random.default_rng(1).uniform(0, 15, (60, 2)), 15.0, [0, 0, 0]).shape[1] + 1 == 8  # 7 features + intercept
    assert cmp.features("B", np.random.default_rng(1).uniform(0, 15, (60, 2)), 15.0, [0, 0, 0]).shape[1] + 1 == 8
    assert cmp.features("C", np.random.default_rng(1).uniform(0, 15, (60, 2)), 15.0, [0, 0, 0]).shape[1] + 1 == 8


def test_logistic_fit_recovers_a_known_relation_and_the_statistics_are_correct():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(4000, 2))
    y = (rng.uniform(size=4000) < 1 / (1 + np.exp(-(1.5 * X[:, 0] - 1.0 * X[:, 1])))).astype(float)
    w, mu, sd = cmp.fit_logistic(X, y)
    p = cmp.predict(w, mu, sd, X)
    assert np.mean((p - y) ** 2) < 0.19 and w[0] > 0 > w[1]
    t = paired_t([0.1, 0.12, 0.09, 0.11, 0.1])
    assert 0.089 < t["ci95"][0] < t["mean"] < t["ci95"][1] < 0.13 and t["p"] < 0.001
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]


def test_the_saved_records_state_their_provenance_and_keep_every_dissolution_outcome_separate():
    f = DOCS / "sbs_records.json"
    if not f.exists():  # pragma: no cover - before the first full run
        return
    r = json.loads(f.read_text())
    assert r["classification"] == "NEW EXECUTION" and r["protocol_digest"] == PROTOCOL_DIGEST and r["protocol"] == json.loads(json.dumps(PROTOCOL))
    for w in r["worlds"]:
        for b in w["branches"]:
            d = b["dissolution"]
            assert set(d) >= {"physical", "organizational", "functional_transmission", "attributional", "agentic", "observational"}
            assert d["agentic"].startswith("NOT_APPLICABLE")
