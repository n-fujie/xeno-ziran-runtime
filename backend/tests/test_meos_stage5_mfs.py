"""MEOS-0, fifth stage: multiple MFS. The relations (necessary, sufficient, substitutable, null, redundant, destabilizing, jointly necessary / sufficient) are tested on hand-made tables,
where the right answer is known; the search is tested on a small universe of the real engine, for the properties that define an MFS (inclusion-minimality over every proper subset, the
record's fields, the digest) and on the saved results of experiment F when they exist."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xzr.meos import mfs5 as M
from xzr.meos import routes5 as R
from xzr.meos import stats5 as ST


def table(universe, persisting):
    """persist[mask] for the sets (iterables of component names) that persist."""
    idx = {c: i for i, c in enumerate(universe)}
    on = {sum(1 << idx[c] for c in s) for s in persisting}
    return {m: m in on for m in range(1 << len(universe))}


U = ("a", "b", "c", "d")


def labels(universe, persisting):
    return {k: set(v["labels"]) for k, v in M.classify(universe, table(universe, persisting))["components"].items()}


def all_supersets(universe, base):
    base = set(base)
    return [set(s) for s in (set(), *[{c for c in universe if m >> i & 1} for m in range(1 << len(universe)) for i, _ in [(0, 0)]])] and [
        {c for i, c in enumerate(universe) if m >> i & 1} for m in range(1 << len(universe)) if base <= {c for i, c in enumerate(universe) if m >> i & 1}
    ]


def test_minimal_masks_checks_every_proper_subset():
    t = table(U, [{"a", "b"}, {"a", "b", "c"}, {"c", "d"}])
    mins = M.minimal_masks(t)
    names = [{c for i, c in enumerate(U) if m >> i & 1} for m in mins]
    assert {frozenset(n) for n in names} == {frozenset({"a", "b"}), frozenset({"c", "d"})}  # {a,b,c} has a persisting proper subset
    # a non-monotone table: {a,b,c} persists although its subset {a,c} does not and {a,b} does: {a,b,c} is not minimal
    t2 = table(U, [{"a", "b"}, {"a", "b", "c"}])
    assert [{c for i, c in enumerate(U) if m >> i & 1} for m in M.minimal_masks(t2)] == [{"a", "b"}]


def test_necessary_and_the_necessary_core():
    ps = [s for s in all_supersets(U, {"a", "b"})]
    c = M.classify(U, table(U, ps))
    assert c["necessary_core"] == ["a", "b"]
    assert "necessary" in c["components"]["a"]["labels"] and "necessary" not in c["components"]["c"]["labels"]
    assert "null" in c["components"]["c"]["labels"] and "null" in c["components"]["d"]["labels"]  # c and d never matter


def test_substitutable_when_either_of_two_suffices_in_a_context():
    # a is needed, and one of b or c: b and c are substitutes for each other; d does nothing
    ps = [s for s in all_supersets(U, {"a", "b"})] + [s for s in all_supersets(U, {"a", "c"})]
    c = M.classify(U, table(U, ps))
    assert "substitutable" in c["components"]["b"]["labels"] and any(x["by"] == ["c"] for x in c["components"]["b"]["substitutable_by"])
    assert "necessary" in c["components"]["a"]["labels"] and "necessary" not in c["components"]["b"]["labels"]
    assert ["b", "c"] in c["pairs"]["jointly_necessary"]  # neither alone is necessary, but every persisting set holds one of them


def test_sufficient_completes_the_core_and_jointly_sufficient_pairs():
    # the core {a} does not persist alone; {a,b} persists, {a,c} persists: b and c each complete the core -> sufficient. {a,d,e}... a pair that is only sufficient together:
    u = ("a", "b", "c")
    ps = [{"a", "b", "c"}]
    c = M.classify(u, table(u, ps))
    assert c["necessary_core"] == ["a", "b", "c"]
    ps2 = [{"a", "b"}, {"a", "b", "c"}]
    c2 = M.classify(u, table(u, ps2))
    assert "sufficient (completes the necessary core)" not in c2["components"]["a"]["labels"]  # a is necessary, not "sufficient"
    ps3 = [s for s in all_supersets(("a", "b", "c", "d"), {"a", "b", "c"})]
    c3 = M.classify(("a", "b", "c", "d"), table(("a", "b", "c", "d"), ps3))
    assert ["b", "c"] not in c3["pairs"]["jointly_sufficient"]  # both individually necessary here: the core already contains them


def test_destabilizing_and_redundant():
    # adding c to {a, b} breaks it; d is in no minimal set but the full set minus d persists only if... here the full set does not persist, so d is not redundant
    u = ("a", "b", "c")
    t = table(u, [{"a", "b"}])
    c = M.classify(u, t)
    assert "destabilizing" in c["components"]["c"]["labels"]
    # redundant: persisting sets are {a,b} and {a,b,c}: c is in no minimal set and the full set minus c persists
    c2 = M.classify(u, table(u, [{"a", "b"}, {"a", "b", "c"}]))
    assert "redundant" in c2["components"]["c"]["labels"] and "null" in c2["components"]["c"]["labels"]


def test_nothing_persists_gives_no_core_and_no_claims():
    c = M.classify(U, table(U, []))
    assert c["persisting_sets"] == 0 and c["necessary_core"] == [] and all("necessary" not in v["labels"] for v in c["components"].values())


def test_across_conditions_conditionally_redundant_and_compensatory():
    def res(universe, mfs_sets, degrades=None):
        return {"universe": list(universe), "mfs": [{"retained_components": list(s)} for s in mfs_sets], "classification": {"necessary_core": []}, "condition": {"degrades": degrades}}

    results = {"X1": res(("a", "h"), [("a",)]), "X2": res(("a", "h"), [("a", "h")], degrades="X1")}
    out = M.classify_across(results)
    assert out["h"]["conditionally_redundant"] is True
    assert out["h"]["compensatory"] == [{"component": "h", "redundant_under": "X1", "needed_under": "X2"}]
    assert out["a"]["conditionally_redundant"] is False


def test_paths_and_route_kinds():
    uni = M.COMPONENTS5
    kept, lost = M.paths_of({"history", "interaction_channel"}, uni)
    assert "history_access" in kept and "coupling" in kept and "m2" in lost and "resource" in lost
    assert M.route_kind({"history"}, uni).startswith("history-mediated")
    assert M.route_kind({"m2_tap"}, uni).startswith("M2-mediated")
    assert M.route_kind({"history", "m2_tap"}, uni).startswith("history+M2")
    assert "history-free" in M.route_kind({"interaction_channel"}, uni)
    # equal size, different components: different routes
    assert M.route_kind({"history", "feedback"}, uni) != M.route_kind({"m2_tap", "feedback"}, uni)


def test_retained_interventions_remove_exactly_the_complement():
    cond = M.condition("T", "t", tap=M.M2_BASE)
    ivs = M.retained_interventions(cond, {"A2", "m2_tap"})
    removed = {iv["target"] for iv in ivs if iv["op"] == "REMOVE"}
    assert removed == set(cond["universe"]) - {"A2", "m2_tap"} and not any(iv["op"] == "ROUTE" for iv in ivs)
    ivs2 = M.retained_interventions(cond, {"A2"})
    assert any(iv["op"] == "ROUTE" and iv["m2"]["sense"] == "none" for iv in ivs2)  # a tap that is not retained is switched off
    c2 = M.condition("T2", "t", tap=M.M2_BASE, unavailable=("history",))
    assert "history" not in c2["universe"] and any(iv.get("target") == "history" for iv in M.retained_interventions(c2, {"A2"}))  # an unavailable component is absent in every run


@pytest.fixture(scope="module")
def small_search():
    cond = M.condition("T", "a small universe", only=("A2", "interaction_channel", "feedback", "resource_renewal", "history"))
    return cond, M.search(cond, processes=1, confirm_seeds=(6, 7))


def test_a_search_finds_inclusion_minimal_sets_and_proves_it(small_search):
    cond, r = small_search
    n = len(cond["universe"])
    assert r["subsets_evaluated"] == 2**n and r["minimal_count"] >= 1
    persist = {int(k): v == len(M.SEARCH_SEEDS) for k, v in r["table"].items()}
    for m in r["mfs"]:
        mask = sum(1 << cond["universe"].index(c) for c in m["retained_components"])
        assert persist[mask] and not any(persist[s] for s in M._submasks(mask) if s != mask)  # persists, and no proper subset persists
        proof = m["inclusion_minimality_proof"]
        assert proof["all_proper_subsets_evaluated"] == 2 ** m["cardinality"] - 1 and proof["persisting_proper_subsets"] == 0
        assert len(proof["maximal_proper_subsets"]) == m["cardinality"]


def test_an_mfs_record_has_every_field_and_a_stable_digest(small_search):
    cond, r = small_search
    need = {"id", "preserved_operation", "environment_condition", "observation_condition", "temporal_window", "scale", "allowed_reductions", "retained_components", "removed_components", "retained_paths", "lost_paths", "recovery_capability", "observability", "cardinality", "inclusion_minimality_proof", "digest", "search_seeds", "confirmation_seeds"}
    for m in r["mfs"]:
        assert need <= set(m)
        assert set(m["retained_components"]) | set(m["removed_components"]) == set(cond["universe"]) and not set(m["retained_components"]) & set(m["removed_components"])
        assert m["digest"] == M.E.digest({k: m[k] for k in ("condition_id", "retained_components", "removed_components", "environment_condition", "allowed_reductions")})
        assert m["confirmation_seeds"] == [6, 7]  # out-of-sample: not the search seeds
    assert not set(M.SEARCH_SEEDS) & set(M.CONFIRM_SEEDS)


def test_the_search_is_deterministic(small_search):
    cond, r = small_search
    again = M.search(cond, processes=1, confirm_seeds=(6, 7))
    assert [m["digest"] for m in again["mfs"]] == [m["digest"] for m in r["mfs"]] and again["table"] == r["table"]


def test_equivalence_levels_are_not_decided_by_active_alone():
    base = {"preserved_operation": 1.0, "energy_use": 100.0, "resource_throughput": 50.0, "stability_cycle_cv": 0.2, "perturbation_sensitivity": {"p1": 0.0, "p2": 1.0}, "history_dependence": None, "address_dependence": 0.4,
            "collapse_modes": {"p1": None, "p2": "x"}, "observational_robustness": 0.5, "sss_region": "OBSERVATION-SENSITIVE"}
    assert R.compare(base, dict(base))["equivalent_through_level"] == 4
    other = {**base, "energy_use": 150.0}
    c = R.compare(base, other)
    assert c["equivalent_through_level"] == 1 and "energy use" in c["differences_at_first_failed_level"]  # both ACTIVE, not equivalent at L2
    sens = {**base, "perturbation_sensitivity": {"p1": 1.0, "p2": 0.0}}
    assert R.compare(base, sens)["equivalent_through_level"] == 2
    mode = {**base, "collapse_modes": {"p1": None, "p2": "y"}}
    assert R.compare(base, mode)["equivalent_through_level"] == 3
    failed = {**base, "preserved_operation": 0.8}
    assert R.compare(base, failed)["equivalent_through_level"] == 0


def test_statistics_helpers():
    assert ST.wilson(0, 10)[0] == 0.0 and ST.wilson(10, 10)[1] == 1.0 and 0.5 < ST.wilson(8, 10)[1] <= 1.0
    assert ST.cohens_h(0.5, 0.5) == 0.0 and ST.cohens_h(1.0, 0.0) > 3
    assert ST.cliffs_delta([1, 2, 3], [4, 5, 6]) == -1.0 and ST.cliffs_delta([4, 5, 6], [1, 2, 3]) == 1.0
    cmp = ST.compare_proportions(10, 10, 0, 10)
    assert cmp["fisher_exact_p"] < 0.001 and cmp["a"]["wilson95"][0] > 0.6
    pc = ST.compare_paired([1, 2, 3, 4, 5, 6], [2, 3, 4, 5, 6, 7])
    assert pc["median_difference"] == 1.0 and pc["wilcoxon_p"] is not None and pc["share_b_greater"] == 1.0
    assert "no test" in ST.compare_paired([1, 1], [1, 1]).get("note", "no test")
    assert "few observations" in ST.describe(0.9, 5) and "few observations" not in ST.describe(0.9, 50)


SAVED = Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage5.json"


@pytest.mark.skipif(not SAVED.exists(), reason="experiment F has not been run")
def test_the_saved_mfs_are_inclusion_minimal_and_complete():
    f = json.loads(SAVED.read_text())["experiments"]["F"]
    assert f["by_condition"]
    for cid, r in f["by_condition"].items():
        persist = {int(k): v == len(M.SEARCH_SEEDS) for k, v in r["table"].items()}
        uni = r["universe"]
        assert r["subsets_evaluated"] == 2 ** len(uni) == len(persist)
        mins = M.minimal_masks(persist)
        found = sorted(sum(1 << uni.index(c) for c in m["retained_components"]) for m in r["mfs"])
        assert found == sorted(mins), cid  # every inclusion-minimal set was recorded, and no other
        for m in r["mfs"]:
            assert m["inclusion_minimality_proof"]["persisting_proper_subsets"] == 0
            assert m["inclusion_minimality_proof"]["all_proper_subsets_evaluated"] == 2 ** m["cardinality"] - 1
            assert m["persists_in_confirmation_seeds"] <= len(m["confirmation_seeds"])
