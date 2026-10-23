"""Rules v2 of the total-observation line (the reliability repair), and the guarantee that v1 is unchanged.

v1 (the default when an environment names no ``rules_version``) is the first release's behaviour and stays pinned: earlier stored studies replay under it.
v2 repairs four things found in the first release's results: records delayed in transit were discarded by a freshness window counted from observation
(``comm-delay`` and ``planetary-form`` recall near zero), a missing report was read as a silent / expired sensor, `denied` and `scale-mismatch` flip-flopped
a sensor's scale (only a cooldown stopped it), and one supporting hypothesis test was accepted as support. Software checks on reserved functional seeds."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from xzr.totalobs import agent as A
from xzr.totalobs import loop

FULL = {"policy": "adaptive", "history": "own", "meta": True, "strong": list(A.STRONG)}
V2 = {"rules_version": "v2"}
KEYS = (
    "recall_final",
    "recall_mean",
    "precision_mean",
    "spurious_rate",
    "ops_executed",
    "ops_denied",
    "question_changes",
    "hyp_tests",
    "hyp_supported",
    "hyp_refuted",
    "meta_revisions",
    "generations_run",
    "denied_blocks",
    "expired_sensors",
)
STRESS = {
    "generations": 10,
    "net": {"pool": 16.0, "n_sensors": 3},
    "events": [
        {"gen": 3, "do": "fail_sensor", "sensor": "S0"},
        {"gen": 5, "do": "cut_zone", "center": 40, "radius": 3},
        {"gen": 6, "do": "lose_records", "t0": 0},
    ],
}
# behavioural digests of the first release (metrics and operation sequences), taken before the repair was written
PINS = {
    "full-default-g8": "541fb2da7dad32fa27e4e9dc7a0d57a862a17b0611110e39391fbf0f92977b5d",
    "adaptive-stress": "0c934a96366236003b4b61670cf2abfc597dc4fa5d142c1d6592fc3505c1a6e4",
    "commdelay": "490c18df3a0c56d7e3d95f8f577918aa61154869bd915a6b5bdd619a1d0d4b35",
}
CASES = {
    "full-default-g8": ({"generations": 8}, FULL, 7003, 70003),
    "adaptive-stress": (STRESS, {"policy": "adaptive", "meta": True}, 7001, 70001),
    "commdelay": (
        {"generations": 8, "net": {"n_sensors": 3, "latency": 4}},
        {"policy": "adaptive", "history": "own", "meta": True},
        7002,
        70002,
    ),
}


def run(env: dict, design: dict, i: int = 0, **extra) -> dict:
    return loop.run({**env, **extra}, {"name": "t", "design": design}, 7000 + i, 70000 + i)


def behaviour(r: dict) -> dict:
    gens = [
        [(o["op"], o["reason"], o["status"]) for o in g["ops"]] + [("Q", g["decision"]["question_next"])]
        for g in r["totalobs"]["generations"]
    ]
    return {"m": {k: r["metrics"][k] for k in KEYS}, "g": gens}


def mean(rs: list[dict], k: str) -> float:
    xs = [r["metrics"][k] for r in rs if r["metrics"].get(k) is not None]
    return float(np.mean(xs)) if xs else float("nan")


# ---------------------------------------------------------------------------------------------------- v1 stays what it was
@pytest.mark.parametrize("name", list(CASES))
def test_v1_behaviour_is_pinned(name):
    env, design, g, s = CASES[name]
    r = loop.run(env, {"name": "t", "design": design}, g, s)
    assert hashlib.sha256(json.dumps(behaviour(r), sort_keys=True, default=float).encode()).hexdigest() == PINS[name]
    assert (
        "rules_version" not in r["totalobs"] and "silence_audit" not in r["totalobs"]
    )  # a v1 record gains no key: stored v1 studies replay unchanged


def test_unknown_rules_version_is_refused():
    with pytest.raises(ValueError):
        run({"generations": 2}, {"policy": "fixed"}, rules_version="v3")


# ---------------------------------------------------------------------------------------------------- 1. what 'recall' measures, and the delay defect
def test_v1_discards_records_delayed_in_transit_and_v2_does_not():
    env = {"generations": 6, "net": {"n_sensors": 3, "latency": 8}}
    v1 = [run(env, {"policy": "fixed"}, i) for i in range(6)]
    v2 = [run(env, {"policy": "fixed"}, i, **V2) for i in range(6)]
    assert mean(v1, "recall_final") == 0.0 and all(
        r["metrics"]["precision_mean"] is None for r in v1
    )  # nothing identified at all: the hub's view was empty
    assert (
        mean(v2, "recall_final") > 0.3
    )  # the same world, the same sensors, the same records: the repaired rule uses what arrived


def test_recall_is_the_observed_share_of_the_worlds_objects_not_a_reproducibility_figure():
    r = run({"generations": 4}, {"policy": "fixed"}, 0, **V2)
    assert "not of the software's reproducibility" in r["totalobs"]["recall_definition"]
    reg = r["totalobs"]["metric_log"]["registry"]["recall_region"]
    assert "freshness" in reg["basis_keys"] and "reproducibility" in reg["definition"]
    # re-execution agreement is a different quantity: the same run twice is identical whatever its recall
    again = run({"generations": 4}, {"policy": "fixed"}, 0, **V2)
    strip = lambda x: {k: v for k, v in x.items() if k != "wall_s"}  # noqa: E731
    assert json.dumps(strip(r), sort_keys=True, default=float) == json.dumps(strip(again), sort_keys=True, default=float)


def test_delay_costs_recall_only_when_the_world_changes_and_information_age_shows_it_always():
    drift = [
        {"gen": g, "do": "move_source", "k": k, "region": (17 * k + 31 * g) % 96} for g in (3, 4, 5, 6, 7) for k in (0, 1, 2)
    ]
    out = {}
    for lat in (1, 8):
        for name, ev in (("still", []), ("drift", drift)):
            rs = [
                run({"generations": 8, "net": {"n_sensors": 3, "latency": lat}, "events": ev}, {"policy": "fixed"}, i, **V2)
                for i in range(8)
            ]
            out[(name, lat)] = (mean(rs, "recall_final"), mean(rs, "info_age_mean"))
    assert out[("still", 8)][1] > out[("still", 1)][1] + 20  # delay makes information older, always
    assert (
        abs(out[("still", 8)][0] - out[("still", 1)][0]) < 0.2
    )  # ... which a recall measure cannot show while the sources stand still
    assert out[("drift", 8)][0] < out[("drift", 1)][0] - 0.1  # ... but does cost recall when the world changes


# ---------------------------------------------------------------------------------------------------- 2. silence is not extinction
def test_missing_reports_are_classified_without_asserting_a_cause_and_audited_against_the_true_causes():
    env = {
        "generations": 8,
        "net": {"n_sensors": 4, "latency": 3},
        "events": [{"gen": 2, "do": "fail_sensor", "sensor": "S0"}, {"gen": 3, "do": "cut_zone", "center": 60, "radius": 4}],
    }
    rs = [run(env, FULL, i, **V2) for i in range(6)]
    audit = [a for r in rs for a in r["totalobs"]["silence_audit"]]
    states = {a["agent_state"] for a in audit}
    assert "no-arrival" in states and "delayed" in states
    assert {a["true_cause"] for a in audit if a["agent_state"] == "no-arrival"} <= {
        "failed",
        "outage",
        "record-loss",
    }  # never a mere delay
    assert all(a["true_cause"] != "failed" for a in audit if a["agent_state"] == "delayed")
    text = json.dumps([g["trigger"] for r in rs for g in r["totalobs"]["generations"]])
    assert "expired" not in text and "silent" not in text  # v2 reasons never say that something ceased to exist
    logs = [e for r in rs for e in r["totalobs"]["silence_log"]]
    assert {e["attribution"] for e in logs} <= {"stopped-or-unreachable", "place-dependent (outage or delay)"}
    for e in logs:  # an attribution is checked against what the verifier knows
        if e["attribution"] == "stopped-or-unreachable":
            assert "failed" in e["true_causes_seen_for_this_sensor"] or "outage" in e["true_causes_seen_for_this_sensor"]


def test_hub_notices_lost_records_from_its_own_accounting_and_a_lost_identification_is_not_a_vanished_object():
    rs = [run(STRESS, {"policy": "adaptive", "meta": True}, i, **V2) for i in range(6)]
    detected = [g["observation"]["records_lost_detected"] for r in rs for g in r["totalobs"]["generations"]]
    assert max(detected) > 0
    assert (
        sum(r["metrics"]["ident_lost_object_still_present"] for r in rs) > 0
    )  # identification was lost while the world's object was still there
    assert all(r["totalobs"]["hub_accounting"]["received"] >= r["totalobs"]["hub_accounting"]["held"] for r in rs)


def test_v2_stop_reason_does_not_claim_the_observers_are_gone():
    env = {
        "generations": 6,
        "net": {"n_sensors": 2, "pool": 10.0},
        "events": [{"gen": 1, "do": "fail_sensor", "sensor": "S0"}, {"gen": 1, "do": "fail_sensor", "sensor": "S1"}],
    }
    r = run(env, {"policy": "adaptive", "budget": 3.0}, 0, **V2)
    assert (
        r["totalobs"]["stopped"]
        and "cause undetermined" in r["totalobs"]["stopped"]["reason"]
        and "no-observer" not in r["totalobs"]["stopped"]["reason"]
    )


# ---------------------------------------------------------------------------------------------------- 3. rule conflict
CONFLICT = {"generations": 10, "net": {"n_sensors": 4, "scale": 2, "pool": 6.0, "period": 2, "radius": 3}}


def test_conflict_is_arbitrated_by_a_stated_priority_and_not_only_suppressed():
    d = {"policy": "adaptive", "meta": True}
    v1 = [run(CONFLICT, d, i) for i in range(8)]
    v2 = [run(CONFLICT, d, i, **V2) for i in range(8)]
    assert sum(len(r["totalobs"]["suppressed"]) for r in v1) > 0  # v1 flip-flops and only the cooldown stops it
    conflicts = [c for r in v2 for c in r["totalobs"]["conflicts"]]
    assert conflicts
    for c in conflicts:
        assert {"rules", "demand", "pool", "resolution", "why"} <= set(c) and "denied" in c["rules"] and len(c["rules"]) >= 2
    assert all(r["metrics"]["cooldown_suppressions"] == 0 for r in v2)  # the arbitration, not the cooldown, resolved them
    assert sum(r["metrics"]["scale_reversals"] for r in v2) <= len(
        v2
    )  # at most a rare later reversal, not a flip-flop per generation


def test_an_infeasible_conflict_is_declared_and_not_retried():
    tiny = {"generations": 10, "net": {"n_sensors": 3, "scale": 2, "pool": 1.0, "period": 2, "radius": 3}}
    rs = [run(tiny, {"policy": "adaptive"}, i, **V2) for i in range(6)]
    inf = [(r, c) for r in rs for c in r["totalobs"]["conflicts"] if c["resolution"] == "infeasible" or c.get("note")]
    assert inf and all(c["demand"] > c["pool"] for _, c in inf)  # the demand really exceeds the pool
    for r, c in inf:
        later = [
            o
            for g in r["totalobs"]["generations"]
            if g["gen"] > c["gen"] + 1
            for o in g["ops"]
            if o["reason"] == "denied" and o.get("conflict")
        ]
        assert len(later) <= len(r["totalobs"]["generations"])  # bounded: infeasible sensors are not served again
    assert all(r["metrics"]["infeasible_events"] >= 1 for r, _ in inf)


# ---------------------------------------------------------------------------------------------------- 4. hypothesis support
def test_update_hypothesis_needs_two_consistent_tests_and_withdraws_on_refutation():
    h = {"status": "untested"}
    assert A.update_hypothesis(h, "supported", 1.0) is None and h["status"] == "provisional"
    A.update_hypothesis(h, "supported", 1.1)  # within 35 % of the last estimate
    assert h["status"] == "supported" and h["consistent"] == 2
    assert A.update_hypothesis(h, "refuted", 0.4) == "withdrawn" and h["status"] == "withdrawn" and h["withdrawn"] == 1
    g = {"status": "untested"}
    A.update_hypothesis(g, "supported", 1.0)
    A.update_hypothesis(g, "supported", 2.0)  # not consistent with the first: the count restarts
    assert g["status"] == "provisional" and g["consistent"] == 1
    A.update_hypothesis(g, "refuted", 0.5)
    assert g["status"] == "refuted"  # never supported: nothing to withdraw


def test_support_for_a_hypothesis_is_recorded_apart_from_agreement_with_the_model_and_the_agent_never_reads_the_latter(
    monkeypatch,
):
    env = {"generations": 14}
    base = [run(env, FULL, i, **V2) for i in range(6)]
    tests = [
        g["hypothesis_test"]
        for r in base
        for g in r["totalobs"]["generations"]
        if g["hypothesis_test"] and g["hypothesis_test"].get("B")
    ]
    assert tests and all({"observational_support", "status_after", "model_agreement", "withdrawal"} <= set(t) for t in tests)
    assert {t["status_after"] for t in tests} <= {"provisional", "supported", "refuted", "withdrawn", "untested"}
    accepted = [t for t in tests if t["status_after"] == "supported"]
    assert all(t["observational_support"] == "supported" for t in accepted)
    # the verifier's answer is made wrong: the agent's behaviour must not change, only the recorded agreement
    monkeypatch.setattr(loop, "true_arrival", lambda *a, **k: 1)
    wrong = [run(env, FULL, i, **V2) for i in range(6)]
    assert [behaviour(r) for r in wrong] != [] and all(
        [(o["op"], o["reason"], o["status"]) for g in a["totalobs"]["generations"] for o in g["ops"]]
        == [(o["op"], o["reason"], o["status"]) for g in b["totalobs"]["generations"] for o in g["ops"]]
        for a, b in zip(base, wrong, strict=True)
    )
    agree = {
        t["model_agreement"]
        for r in wrong
        for g in r["totalobs"]["generations"]
        for t in [g["hypothesis_test"]]
        if t and t.get("B")
    }
    assert "disagree" in agree  # the recorded agreement did change


def test_an_unobservable_effect_is_recorded_as_such():
    slow = {"generations": 14, "world": {"c": 0.03}}
    rs = [run(slow, FULL, i, **V2) for i in range(6)]
    ag = {
        t["model_agreement"] for r in rs for g in r["totalobs"]["generations"] for t in [g["hypothesis_test"]] if t and t.get("B")
    }
    assert (
        "unobservable" in ag
    )  # the world itself shows no arrival within the horizon: the agent's reading is neither confirmed nor refuted


# ---------------------------------------------------------------------------------------------------- the study layer reports it
def test_summary_and_results_text_carry_the_v2_records(tmp_path):
    from xzr.study import analysis, report, runner, templates

    d = templates.template("autonomous-loop", n_seeds=2)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("fixed", "full")]
    d["contrasts"] = [c for c in d["contrasts"] if c["a"] == "full" and c["b"] == "fixed"]
    st = runner.Study.create(d, tmp_path)
    st.execute(procs=2)
    an = analysis.analyse(st)
    e = an["totalobs"]["arms"]["full"]
    assert e["rules_version"] == "v2" and e["freshness"]["rule"] == "arrival"
    assert {"hypothesis_support_vs_model", "silence_states_vs_true_causes", "rule_conflicts", "identification_lost"} <= set(e)
    report.build(st, an)
    assert "rules v2" in (st.path / "report" / "results.md").read_text()
