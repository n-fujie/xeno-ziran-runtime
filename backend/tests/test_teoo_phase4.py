"""TEOO Phase 4: the SYNTHETIC world keeps its truth apart from what is observed, each parameter of the sensor acts through its mechanism, the detectors are calibrated, the experiments are deterministic and honest about what they
cannot decide, and the pre-registration runs before the data."""

from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from xzr.teoo import experiments as X
from xzr.teoo import observation as OB
from xzr.teoo import protocol as PR
from xzr.teoo import stats as S
from xzr.teoo import world as W

T = np.arange(0, 20.0, W.DT)


def one_comp_world(f=1.0, amp=1.5, scale=2.0, opacity=0.0, n=2):
    comps = [W.Component(f"c{i}", f=f, amp=amp, scale=scale, opacity=opacity) for i in range(n)]
    return W.World(comps, {})


def test_the_world_is_deterministic_and_its_couplings_run_from_lower_to_higher_index():
    a, b = W.make_world(5), W.make_world(5)
    assert a.edges == b.edges and [c.__dict__ for c in a.comps] == [c.__dict__ for c in b.comps] and W.make_world(6).edges != a.edges
    assert all(s < t for s, t in a.edges) and X.components(a.n(), a.edges) == 1  # acyclic and connected
    x1, x2 = W.latent(a, T, np.random.default_rng(1)), W.latent(a, T, np.random.default_rng(1))
    assert np.array_equal(x1, x2) and not np.array_equal(x1, W.latent(a, T, np.random.default_rng(2)))


def test_a_coupling_carries_the_signal_of_a_source_to_a_sink_and_nothing_else_does():
    w = one_comp_world(n=3)
    w.edges[(0, 1)] = 0.8
    x = W.latent(w, T, np.random.default_rng(3), only=0)
    assert np.std(x[1]) > 0.5 and np.allclose(x[2], 0)  # component 1 inherits from 0; component 2 is joined to nothing
    assert X.operability(w, 0, 1, np.random.default_rng(0)) > 0.1 and X.operability(w, 0, 2, np.random.default_rng(0)) == 0.0
    w.edges.clear()
    assert X.operability(w, 0, 1, np.random.default_rng(0)) == 0.0  # cut: no path, no operability (by the world's own definition)


def test_each_sensor_parameter_acts_through_its_mechanism_and_a_missing_value_is_never_zero():
    w = one_comp_world(f=1.8)
    x = W.latent(w, T, np.random.default_rng(1))
    rng = np.random.default_rng(1)
    fine = W.observe(w, x, T, W.sensor_of(0.5, 0.02, 20, 0.05, 0.9), rng, [0])[0]
    assert abs(W.feature("frequency", fine) - 1.8) < 0.1  # sampled finely: the frequency is recovered
    coarse = W.observe(w, x, T, W.sensor_of(0.5, 1.0, 20, 0.05, 0.9), rng, [0])[0]
    assert abs(W.feature("frequency", coarse) - 1.8) > 0.5  # 1.8 Hz sampled once a second aliases (Nyquist 0.5 Hz): the TEOO status TIME_WINDOW_MISMATCH predicts exactly this
    mixed = W.observe(w, x, T, W.sensor_of(8.0, 0.02, 20, 0.05, 0.9), rng, [0])[0]
    assert np.std(mixed[1][~np.isnan(mixed[1])]) < np.std(fine[1][~np.isnan(fine[1])])  # coarser than the structure: the reading is diluted by the others
    w2 = one_comp_world(opacity=0.8)
    hidden = W.observe(w2, W.latent(w2, T, np.random.default_rng(1)), T, W.sensor_of(0.5, 0.02, 20, 0.05, 0.3), rng, [0])[0]
    assert np.nanstd(hidden[1]) < 0.5 * np.nanstd(W.observe(w2, W.latent(w2, T, np.random.default_rng(1)), T, W.sensor_of(0.5, 0.02, 20, 0.05, 0.9), rng, [0])[0][1])  # attenuated behind a boundary it cannot penetrate
    dead = W.observe(w, x, T, W.sensor_of(0.5, 0.02, 20, 5.0, 0.9), rng, [0])[0][1]
    assert np.isnan(dead).all() and W.feature("amplitude", (T[: len(dead)], dead)) is None  # everything below the detection limit carries no value, and no feature is computed from nothing


def test_the_teoo_status_predicts_what_the_mechanisms_do_to_a_detector():
    w = one_comp_world(f=1.8, amp=1.5)
    cfg_fine, cfg_coarse = X.cfg_of(W.sensor_of(0.5, 0.02, 20, 0.05, 0.9)), X.cfg_of(W.sensor_of(0.5, 1.0, 20, 0.05, 0.9))
    assert OB.assess_target(cfg_fine, W.spec_of(w, 0), 0)["status"] == "MEASURED_VALID" and OB.assess_target(cfg_coarse, W.spec_of(w, 0), 0)["status"] == "TIME_WINDOW_MISMATCH"
    w1 = w.copy()
    w1.comps[0].f = 1.8 * 1.25
    rng = np.random.default_rng(7)

    def sens_(sn):
        hits = 0
        for k in range(10):
            r = np.random.default_rng(k)
            a0 = [W.observe(w, W.latent(w, T, r), T, sn, r, [0])[0] for _ in range(8)]
            a1 = [W.observe(w1, W.latent(w1, T, r), T, sn, r, [0])[0] for _ in range(8)]
            hits += W.detect("frequency", a0, a1, rng)["result"] == "identified"
        return hits / 10
    assert sens_(W.sensor_of(0.5, 0.02, 20, 0.05, 0.9)) >= 0.8
    # what the status predicts is the loss of the *value* (the recovered frequency is wrong, shown above), not necessarily the loss of the *difference*: here both conditions alias to different frequencies
    # (1.8 Hz -> 0.2 Hz, 2.25 Hz -> 0.25 Hz), so a difference is still detected although it is not the true one. This limit of the status model is a result, kept in the experiment report.
    assert sens_(W.sensor_of(0.5, 1.0, 20, 0.05, 0.9)) >= 0.8


def test_the_detectors_do_not_find_differences_that_are_not_there_and_find_large_ones():
    w = one_comp_world(f=1.0, amp=1.5, n=2)
    sn = W.sensor_of(0.5, 0.02, 20, 0.05, 0.9)
    rng = np.random.default_rng(11)
    fp = {k: 0 for k in ("amplitude", "frequency", "burst")}
    n = 60
    for i in range(n):
        r = np.random.default_rng(i)
        t0 = [W.observe(w, W.latent(w, T, r), T, sn, r, [0])[0] for _ in range(8)]
        t1 = [W.observe(w, W.latent(w, T, r), T, sn, r, [0])[0] for _ in range(8)]
        for k in fp:
            fp[k] += W.detect(k, t0, t1, rng)["result"] == "identified"
    assert all(v / n <= 0.06 for v in fp.values()), fp  # alpha = 0.01: a handful of false identifications at most
    w1 = w.copy()
    w1.comps[0].amp = 3.0
    big = [W.observe(w1, W.latent(w1, T, np.random.default_rng(i)), T, sn, np.random.default_rng(i), [0])[0] for i in range(8)]
    small = [W.observe(w, W.latent(w, T, np.random.default_rng(i)), T, sn, np.random.default_rng(i), [0])[0] for i in range(8)]
    assert W.detect("amplitude", small, big, rng)["result"] == "identified"
    assert W.detect("amplitude", small[:2], big[:2], rng)["result"] == "undetermined"  # too few traces: undetermined, not 'no difference'


def test_the_experiment_units_are_deterministic_also_across_hash_seeds():
    code = "import json,hashlib;from xzr.teoo import experiments as X;print(hashlib.sha256(json.dumps([X.run_graph(2),X.run_e(2)],default=str).encode()).hexdigest())"
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={"PYTHONPATH": ".", "PYTHONHASHSEED": h, "PATH": ""}, cwd=Path(__file__).resolve().parents[1]).stdout.strip() for h in ("1", "99")}
    assert len(outs) == 1 and len(next(iter(outs))) == 64


def test_exp_a_rows_keep_the_truth_the_status_and_the_undetermined_apart():
    u = X.run_a(3, trials=6, cases_per_type=1)
    rows = u["rows"]
    assert len(rows) == 24 * 8 and {r["kind"] for r in rows} == set(X.TYPES) and {r["truth"] for r in rows} == {True, False}
    assert {r["result"] for r in rows} <= {"identified", "not_identified", "undetermined"} and any(r["result"] == "undetermined" for r in rows)
    assert all(isinstance(r["status_valid"], bool) and r["statuses"] for r in rows)
    assert X.run_a(3, trials=6, cases_per_type=1) == u


def test_exp_c_arms_respect_the_budget_the_adaptive_rule_uses_statuses_only_and_no_event_claims_autonomy():
    u = X.run_c(4, trials=6)
    assert set(u["arms"]) == {"fixed", "prespecified", "random", "adaptive", "static_costmatched"}
    assert all(a["cost_over_initial"] <= u["budget"] + 1e-9 for a in u["arms"].values()) and u["arms"]["fixed"]["identified"] <= u["arms"]["adaptive"]["identified"]
    ad = u["arms"]["adaptive"]
    assert len(ad["events"]) == len(ad["sequence"]) > 0 and all(e["initiated_by"] == "system" and e["autonomous_revision_demonstrated"] is False and e["status"] == "recorded" for e in ad["events"])
    assert "statuses only" in ad["decider"] and all(e["initiated_by"] == "researcher" for e in u["arms"]["prespecified"]["events"])
    assert all(isinstance(g, dict) for e in ad["events"] for g in e["gained"])
    assert X.cost(X.INITIAL) < X.cost(X.step(X.INITIAL, "r")) and X.step(X.step(X.step(X.INITIAL, "ts"), "ts"), "ts")["ts"] == 0.125


def test_exp_e_never_fills_what_cannot_be_identified_and_the_zero_predictor_is_always_defined():
    u = X.run_e(5)
    coarse = u["conditions"]["coarse"]["methods"]
    assert u["conditions"]["reference"]["methods"]["interp"][0]["identifiable"]
    assert any(not c["identifiable"] for c in coarse["interp"]) and all("nrmse" not in c for m in coarse.values() for c in m if not c["identifiable"])
    assert all(c["identifiable"] for c in coarse["zero"]) and abs(np.mean([c["nrmse"] for c in coarse["zero"]]) - 1.0) < 0.3
    partial = u["conditions"]["partial"]["methods"]
    own = {c["c"] for c in partial["interp"] if c["identifiable"]}
    assert own and len(own) < 10  # half the components have samples of their own
    # a component with samples of its own is reconstructed from them by the graph method too (the pilot's defect)
    assert all(g["nrmse"] == pytest.approx(i["nrmse"]) for g in partial["graph"] for i in partial["interp"] if g["c"] == i["c"] and i["identifiable"] and g["identifiable"])


def test_the_new_statistics_are_calibrated_and_the_exact_bound_is_the_exact_bound():
    rng = np.random.default_rng(0)
    ps = [S.paired_sign_flip(list(rng.normal(0, 1, 20)), n_perm=999, seed=i)["p"] for i in range(200)]
    assert np.mean(np.array(ps) < 0.05) < 0.10  # about 5% under the null
    assert S.paired_sign_flip(list(rng.normal(1.0, 1, 20)), seed=1)["p"] < 0.01 and S.paired_sign_flip([1.0, 2.0])["p"] is None
    assert S.equivalence(list(rng.normal(0, 0.05, 30)), 0.1)["supported"] is True and S.equivalence(list(rng.normal(0.3, 0.05, 30)), 0.1)["supported"] is False
    assert S.upper_bound(0, 30) == pytest.approx(1 - 0.05 ** (1 / 30), rel=1e-6) and S.upper_bound(30, 30) == 1.0 and S.upper_bound(0, 0) is None
    assert math.isfinite(S.bootstrap_ci([1.0, 2.0, 3.0, 4.0])[0])


def _runner():
    spec = importlib.util.spec_from_file_location("teoo_phase4_run", Path(__file__).resolve().parents[1] / "scripts" / "teoo_phase4_run.py")
    m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def test_every_protocol_validates_and_version_2_changes_only_what_it_says():
    R = _runner()
    protos = R.protocols()
    assert set(protos) == {"EXP-A", "EXP-B", "EXP-C", "EXP-D", "EXP-E"} and all(PR.validate(p) == [] for p in protos.values())
    assert all(a["method"] in PR.METHODS for p in protos.values() for a in p["analyses"])
    reg = PR.ProtocolRegistry()
    for key, (changes, reason) in R.amendments(protos).items():
        p1 = protos[key]
        reg.register(p1)
        reg.freeze(p1["experiment_id"], 1, 1.0)
        p2 = reg.amend(p1["experiment_id"], 1, changes, reason)
        assert p2["version"] == 2 and p2["parent_version"] == 1 and "pilot" in p2["change_reason"] and set(p2["seeds"]).isdisjoint(p1["seeds"])
        assert p2["hypotheses"] == p1["hypotheses"] or key == "EXP-E"
        assert [a["id"] for a in p2["analyses"]] == [a["id"] for a in p1["analyses"]] and all({k: v for k, v in a2.items() if k != "outcome"} == {k: v for k, v in a1.items() if k != "outcome"} for a1, a2 in zip(p1["analyses"], p2["analyses"], strict=True))
        reg.freeze(p2["experiment_id"], 2, 2.0)
        reg.note_first_data(p2["experiment_id"], 2, 3.0)
        assert all(reg.analysis_class(p2["experiment_id"], 2, a["id"]) in ("confirmatory", "exploratory (declared but not marked confirmatory)") for a in p2["analyses"])
        assert reg.get(p1["experiment_id"], 1)["seeds"] == p1["seeds"] and reg.verify() == []  # the frozen first version is unchanged
    e1, e2 = reg.get("TEOO4-EXP-E", 1), reg.get("TEOO4-EXP-E", 2)
    assert e1["analyses"][1]["outcome"] != e2["analyses"][1]["outcome"] and "ignored a component's own samples" in e2["change_reason"]


def test_the_first_datum_of_a_version_comes_after_its_freeze_in_the_registry_the_script_writes(tmp_path):
    R = _runner()
    protos = R.protocols()
    reg = PR.ProtocolRegistry(tmp_path / "r.jsonl")
    p = protos["EXP-C"]
    reg.register(p)
    reg.note_first_data(p["experiment_id"], 1, 1.0)  # data before the freeze
    reg.freeze(p["experiment_id"], 1, 2.0)
    assert reg.analysis_class(p["experiment_id"], 1, "C1") == "exploratory (declared after the first data)"


def test_the_total_observation_record_of_a_unit_replays_identically_and_keeps_its_ledger_intact(tmp_path):
    R = _runner()
    doc = R.total_observation_records(tmp_path, 7)
    assert doc["replay_is_identical"] and doc["ledger_issues"] == [] and all(i["issues"] == [] and i["provenance"] == "SYNTHETIC" for i in doc["interventions"])
    assert [v["change"]["op"] for v in doc["body"]["versions"]][0] == "declare" and doc["body"]["version_disconnected"] > doc["body"]["version_connected"] and doc["body"]["version_reconnected"] > doc["body"]["version_disconnected"]
    s = {x["t"]: x for x in doc["replayed_states"]}
    assert s[9.9]["config_version"] == 1 and s[10.0]["config_version"] == 2 and s[0.0]["summary"] != s[10.0]["summary"]  # the coarser sensor from t = 10 s changes what is observable
    assert (tmp_path / "total_observation_records.json").exists()


def test_the_saved_phase4_figures_verify_carry_their_metadata_and_are_not_removable():
    from xzr.teoo import export as EX

    d = Path(__file__).resolve().parents[2] / "docs" / "teoo_evidence" / "phase4" / "figures"
    svgs = sorted(d.glob("fig*.svg"))
    assert len(svgs) == 8
    for f in svgs:
        svg = f.read_text()
        md = json.loads((d / f"{f.stem}.metadata.json").read_text())
        assert EX.verify_svg(svg) == [] and md["evidence"]["classes"] == ["SYNTHETIC"] and md["evidence"]["real_world_experiment_recorded"] is False and md["experiment"]["protocol_id"].startswith("TEOO4-EXP-")
        png = EX.inspect_png((d / f"{f.stem}.png").read_bytes())
        assert png["ok"] and png["metadata"] == md and (png["width"], png["height"]) == (1600, 840)
        assert EX.verify_svg(svg.replace('class="teoo-band-bg"', 'class="x"'))  # the band cannot be taken off unnoticed


def test_the_saved_confirmatory_results_are_those_of_the_registered_protocol():
    d = Path(__file__).resolve().parents[2] / "docs" / "teoo_evidence" / "phase4" / "confirmatory_v2"
    reg = PR.ProtocolRegistry(d / "protocol_registry.jsonl")
    assert reg.verify() == []
    for k in "ABCDE":
        doc = json.loads((d / f"EXP-{k}.json").read_text())
        p2 = reg.get(doc["experiment_id"], 2)
        assert PR.body_digest(p2) == doc["protocol_digest"] and doc["protocol_version"] == 2 and p2["parent_version"] == 1 and doc["units"] == len(p2["seeds"]) == 30
        pilot = json.loads((d.parent / "pilot_seeds_1_30" / f"EXP-{k}.json").read_text())
        assert set(doc["seeds"]).isdisjoint(pilot["seeds"])  # the confirmatory seeds were not used in the pilot
        for a in p2["analyses"]:
            assert doc["results"][a["id"]]["registered_class"] == reg.analysis_class(doc["experiment_id"], 2, a["id"])
