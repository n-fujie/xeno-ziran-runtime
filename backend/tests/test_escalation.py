"""Resolution escalation: observers, statistics, classification rules, structures, triggers, runtime variants,
compression and deterministic replay."""

from __future__ import annotations

import numpy as np
import pytest

from xzr.experiments.escalation import compression as comp
from xzr.experiments.escalation.harness import build, compare, condition, run
from xzr.experiments.escalation.stats import (
    SESOI,
    classify_condition,
    factor_dependence,
    maxt_test,
    time_pattern,
)
from xzr.reasonlab.mixed import MixedSupport
from xzr.reasonlab.representations import Edit, apply_edit, effective
from xzr.reasonlab.structures import STRUCTURES, build_variant, descriptors, generate, revert_to_reference
from xzr.reasonlab.triggers import trigger_set
from xzr.runtime.engine import Engine
from xzr.runtime.flags import Flags
from xzr.runtime.generator import latent_geometric
from xzr.scenario.topologies import DISCONNECTION_STRUCTURES, TOPOLOGIES, disconnection_structure, topology
from xzr.shapes.multiscale import MultiScaleObserver, aggregate, scale_values, window_distance

GAINS = {"multi_region|300": {"gain": 2.75, "activity": 0.04, "reached": True},
         "modular|300": {"gain": 3.2, "activity": 0.04, "reached": True}}


def _small(**over) -> dict:
    return condition(id="t", n=300, horizon=160, reasoning_from=60, size=12, **over)


def _res(det=False, eq=True, pattern="none", onset=None):
    return {"detected": det, "equivalent": eq, "pattern": pattern, "onset_segment": onset}


def _rows(**status):
    base = {r: _res() for r in ("node", "local", "meso", "macro", "global")}
    base.update(status)
    return base


# ------------------------------------------------------------------------------------------------ resolution
def test_resolution_sensitive_equivalence_node_vs_cluster():
    """Swapping activity between two configurations of the same cluster changes the node resolution and leaves
    every coarser resolution unchanged."""
    labels = {"local": np.array([0, 0, 1, 1]), "meso": np.array([0, 0, 0, 0]), "macro": np.array([0, 0, 0, 0])}
    a = np.array([[1.0, 0.0, 2.0, 2.0]])
    b = np.array([[0.0, 1.0, 2.0, 2.0]])
    assert window_distance(scale_values(a, labels, "node"), scale_values(b, labels, "node"))[0] > 0.3
    for r in ("local", "meso", "macro", "global"):
        assert window_distance(scale_values(a, labels, r), scale_values(b, labels, r))[0] == pytest.approx(0.0)
    assert aggregate(np.array([1.0, 3.0, 5.0]), np.array([0, 0, 1]), 2).tolist() == [2.0, 5.0]


def test_hidden_difference_classifier():
    fine_only = {"exact_identical_share": 0.0, "horizon": 4000,
                 "resolutions": _rows(local=_res(True, False, "persistent", 1))}
    c = classify_condition(fine_only)
    assert c["primary"] == "HIDDEN AT COARSE RESOLUTION" and c["visible_from"] == "local"
    exact_only = {"exact_identical_share": 0.0, "horizon": 4000, "resolutions": _rows()}
    c = classify_condition(exact_only)
    assert c["primary"] == "HIDDEN AT COARSE RESOLUTION" and c["hidden_kind"] == "exact-only"


def test_invisibility_is_not_redundancy():
    """Coarse aggregates that cannot be shown equivalent (underpowered) are UNRESOLVED, never REDUNDANT; only
    bit-identical runs are REDUNDANT."""
    under = {"exact_identical_share": 0.0, "horizon": 4000,
             "resolutions": _rows(macro=_res(False, False), global_=_res())}
    under["resolutions"]["global"] = _res(False, False)
    assert classify_condition(under)["primary"] == "UNRESOLVED"
    same = {"exact_identical_share": 1.0, "horizon": 4000, "resolutions": _rows()}
    assert classify_condition(same)["primary"] == "REDUNDANT"


def test_delayed_transient_persistent_recurrent_divergence():
    assert time_pattern([False] * 8) == "none"
    assert time_pattern([False, False, False, True, True, True, True, True]) == "persistent"
    assert time_pattern([False, True, True, False, False, False, False, False]) == "transient"
    assert time_pattern([True, False, False, True, True, False, True, True]) == "recurrent"
    delayed = {"exact_identical_share": 0.0, "horizon": 4000,
               "resolutions": _rows(macro=_res(True, False, "persistent", 4))}
    labels = classify_condition(delayed)["labels"]
    assert "NON-REDUNDANT" in labels and "TIME-WINDOW-DEPENDENT" in labels
    early_transient = {"exact_identical_share": 0.0, "horizon": 4000,
                       "resolutions": _rows(**{"global": _res(True, False, "transient", 0)})}
    assert "TRANSIENT" in classify_condition(early_transient)["labels"]


def test_null_result_power_classification_and_error_control():
    rng = np.random.default_rng(1)
    false_pos = 0
    for _ in range(40):
        d = rng.normal(0, 1, (12, 300))
        r = maxt_test(d, np.full(300, 10.0))
        false_pos += bool(r["detected"].any())
    assert false_pos <= 2  # family-wise level 0.002 per call; 40 calls
    precise = maxt_test(rng.normal(0, 0.05, (12, 50)), np.full(50, 10.0))
    noisy = maxt_test(rng.normal(0, 5.0, (12, 50)), np.full(50, 10.0))
    assert np.median(precise["ci_half"]) <= SESOI < np.median(noisy["ci_half"])
    shifted = rng.normal(0, 0.1, (12, 50))
    shifted[:, 3] += 2.0
    r = maxt_test(shifted, np.full(50, 10.0))
    assert r["detected"][3] and r["detected"].sum() == 1
    determ = np.zeros((12, 5))
    determ[:, 0] = 1.0  # the same difference in every seed: deterministic effect
    assert maxt_test(determ, np.full(5, 10.0))["detected"][0]


def test_factor_dependence_rule():
    vis = {"labels": ["NON-REDUNDANT"]}
    absent = {"labels": ["HIDDEN AT COARSE RESOLUTION"]}
    unres = {"labels": ["UNRESOLVED"]}
    d = factor_dependence({"a": vis, "b": absent, "c": unres})
    assert d["dependent"] and d["visible_at"] == ["a"] and d["absent_at"] == ["b"] and d["unresolved_at"] == ["c"]
    assert not factor_dependence({"a": vis, "c": unres})["dependent"]  # absence must be established


# ------------------------------------------------------------------------------------------------ structures
@pytest.mark.parametrize("kind", STRUCTURES)
def test_structures_generate_and_vocabulary_representation_is_identical(kind):
    spec = generate(kind, 32, 2)
    d = descriptors(spec, edits=3)
    assert d["items"] == 32 and 0 <= d["fixpoint_sensitivity"] <= 1
    b, c = build_variant("B", spec), build_variant("C", spec)
    rng = np.random.default_rng(3)
    for _ in range(12):
        i = spec["items"][int(rng.integers(32))]["id"]
        e = [Edit("retract", a=i), Edit("set_level", a=i, value=float(rng.random())),
             Edit("remove_token", a=f"t{int(rng.integers(8))}")][int(rng.integers(3))]
        apply_edit(b, e)
        apply_edit(c, e)
        assert effective(b) == effective(c)


def test_alternate_structures_differ_where_the_structure_says():
    spec = generate("unsupported_addressable", 32, 1)
    c, e, h = (effective(build_variant(x, spec)) for x in ("C", "E", "H"))
    in_conflict = {x for pair in spec["conflicts"] for x in pair}
    unsup = [it["id"] for it in spec["items"] if it["base_level"] > 0 and not it["self_standing"]
             and not any(r["target"] == it["id"] for r in spec["requirements"]) and it["id"] not in in_conflict]
    assert unsup and all(c[i] == 0 for i in unsup) and all(e[i] > 0 for i in unsup) and all(h[i] > 0 for i in unsup)
    cyc = generate("strongly_cyclic", 9, 1)
    assert effective(build_variant("F", cyc)) != effective(build_variant("C", cyc))


def test_sticky_conflicts_persist_until_the_defeater_is_unusable():
    spec = {"items": [{"id": "a", "tokens": [], "effects": [], "base_level": 0.9, "self_standing": True},
                      {"id": "b", "tokens": [], "effects": [], "base_level": 0.5, "self_standing": True}],
            "requirements": [], "conflicts": [["a", "b"]], "retracted": [], "blocked_tokens": []}
    g = build_variant("G", {**spec, "clusters": 1})
    assert effective(g)["b"] == 0.0
    apply_edit(g, Edit("set_level", a="a", value=0.1))  # b would now win on levels, but its defeat persists
    assert effective(g)["b"] == 0.0 and effective(build_variant("C", spec))["b"] == 0.0
    ref = build_variant("C", spec)
    apply_edit(ref, Edit("set_level", a="a", value=0.1))
    assert effective(ref)["b"] > 0  # recomputed from scratch, b wins
    apply_edit(g, Edit("retract", a="a"))
    assert effective(g)["b"] > 0
    revert_to_reference(g)
    assert not g.sticky


def test_multiple_clusters_and_mixed_rules():
    spec = generate("multiple_clusters", 32, 1)
    regions = {c: {e["target"] for it in spec["items"] if it["cluster"] == c for e in it["effects"]}
               for c in range(spec["clusters"])}
    assert spec["clusters"] == 4
    assert all(not (regions[a] & regions[b]) for a in regions for b in regions if a != b)
    k = build_variant("K", spec)
    assert isinstance(k, MixedSupport) and set(k.rules.values()) == {"greatest", "single", "least", "backed"}
    # a cross-cluster requirement takes the source cluster's eligible level as input
    rec = build_variant("C", {**spec, "items": [
        {"id": "s", "tokens": [], "effects": [], "base_level": 0.7, "self_standing": True, "cluster": 0},
        {"id": "t", "tokens": [], "effects": [], "base_level": 0.0, "self_standing": False, "cluster": 1}],
        "requirements": [{"sources": ["s"], "target": "t", "mode": "carry"}], "conflicts": []})
    mixed = MixedSupport(rec, {"s": 0, "t": 1}, {0: "greatest", 1: "greatest"})
    assert effective(mixed)["t"] == pytest.approx(0.7)
    local = build_variant("I", {**spec, "items": [
        {"id": "s", "tokens": [], "effects": [], "base_level": 0.7, "self_standing": True, "cluster": 0},
        {"id": "t", "tokens": [], "effects": [], "base_level": 0.0, "self_standing": False, "cluster": 1}],
        "requirements": [{"sources": ["s"], "target": "t", "mode": "carry"}], "conflicts": []})
    assert effective(local)["t"] == 0.0


def test_record_loss_and_reconstruction_edits():
    spec = generate("record_loss_reconstruction", 32, 1)
    g = build_variant("C", spec)
    before = effective(g)
    apply_edit(g, Edit("lose_records"))
    assert g.requirements == [] and effective(g) != before
    apply_edit(g, Edit("restore_records"))
    assert effective(g) == before


# ------------------------------------------------------------------------------------------------ worlds
@pytest.mark.parametrize("kind", TOPOLOGIES)
def test_topologies_build(kind):
    a = topology(kind, 400, 1)
    assert a.state.alive.sum() > 400 and len(a.sets) >= 8


@pytest.mark.parametrize("kind", DISCONNECTION_STRUCTURES)
def test_disconnection_structures_have_weak_bridges(kind):
    a = disconnection_structure(kind, 400, 1)
    st = a.state
    assert a.info["bridge_connections"] > 0
    assert np.isclose(st.base_weight[st.alive].min(), a.info["bridge_base_weight"])


def _world(bridge: bool):
    from xzr.runtime.state import Params
    if bridge:  # weak bridges: disconnection fires
        return disconnection_structure("single_bridge", 600, 1, Params(gain=3.2)).state
    return latent_geometric(600, 4, geo_fraction=0).state


def _fp(flags: dict, steps: int = 400, bridge: bool = False) -> tuple[str, int, int]:
    st = _world(bridge)
    e = Engine(st, 4, checkpoint_every=0, flags=Flags(**flags))
    cuts = removed = 0
    for _ in range(steps):
        d = e.step()
        cuts += len(d.cuts)
        removed += len(d.removed_connections)
    return e.fingerprint(), cuts, removed


def test_disconnection_replacements_and_relabellings():
    full = _fp({}, bridge=True)
    assert full[2] > 0  # disconnection fires in this world
    assert _fp({"disconnect": "as_mutation"}, bridge=True)[0] == full[0]  # generic removal path: identical state
    as_cut = _fp({"disconnect": "as_cut"}, bridge=True)
    assert as_cut[0] == full[0] and as_cut[1] == full[1] + full[2]  # identical state, relabelled events
    assert _fp({"disconnect": "off"}, bridge=True)[0] != full[0]
    st = _world(True)
    e = Engine(st, 4, checkpoint_every=0, flags=Flags(disconnect="weight_zero"))
    for _ in range(400):
        assert len(e.step().removed_connections) == 0
    assert (st.alive & (st.weight == 0.0)).any()


def test_cut_reconfiguration_trigger_variants():
    full = _fp({})
    # deterministic regression for this world only: executing both triggers as generic connection mutation places
    # new connections in other slots, which changes float summation order; in other worlds the runs are equivalent
    # only statistically (see docs/DISCONNECTION.md, topology-trigger study)
    assert _fp({"topology_trigger": "generic_conditions"})[0] == full[0]
    uni = _fp({"topology_trigger": "unified"})
    assert uni[1] == 0 and uni[0] != full[0]
    st = latent_geometric(600, 4, geo_fraction=0).state
    e = Engine(st, 4, checkpoint_every=0, flags=Flags(topology_trigger="merged"))
    for _ in range(300):
        d = e.step()
        assert len(d.cuts) == 0
        assert not set(d.retired.tolist()) & set(d.new_connections[:, 0].tolist())  # no same-step slot reuse


# ------------------------------------------------------------------------------------------------ loop, triggers
def test_world_responsive_triggers_calibrate_then_fire():
    c = _small(triggers=("memory_level", "mismatch", "failed_intervention", "unexpected_closure"))
    loop, world, spec, info, _ = build(c, 7, GAINS, "C")
    ts = loop.cfg.triggers
    for _ in range(59):
        loop.step()
    assert ts.stats == {} and ts.fired == []  # still calibrating
    for _ in range(100):
        loop.step()
    assert ts.stats  # baselines frozen after calibration
    assert all(t >= 60 for t, *_ in ts.fired)


def test_memory_grounding_lowers_levels_when_region_memory_drops():
    spec = generate("local_external_memory", 12, 1)
    ts = trigger_set((), spec, record_region="R")
    assert ts.memory_groundings and list(ts.memory_groundings) == ["R"]


def test_reasoning_reaches_the_world_only_through_the_gate():
    c = _small()
    loop, world, spec, info, _ = build(c, 3, GAINS, "D")
    calls = []
    orig = world.engine.set_overlay

    def spy(items):
        import inspect
        calls.append(inspect.stack()[1].function)
        return orig(items)
    world.engine.set_overlay = spy
    for _ in range(160):
        loop.step()
    assert calls and set(calls) == {"set_overlay"}  # InterventionGate.set_overlay is the only caller


def test_deterministic_replay_and_pairing():
    c = _small()
    a, b = run(c, "C", 11, GAINS), run(c, "C", 11, GAINS)
    assert a["final_fp"] == b["final_fp"] and a["effects"] == b["effects"]
    n = run(c, "C", 12, GAINS)
    assert n["final_fp"] != a["final_fp"]


def test_persistent_records_differ_only_when_records_would_change():
    """J (records immune to decay) is bit-identical to C when nothing decays records (no enabling gate, no record
    dynamics) and differs when the reasoning layer collapses and C's records decay."""
    free = _small(enabling=False)
    assert compare(run(free, "J", 11, GAINS), run(free, "C", 11, GAINS), {})["identical"]
    gated = _small()
    cr = run(gated, "C", 11, GAINS)
    if "collapsed" in cr["phases"]:
        assert not compare(run(gated, "J", 11, GAINS), cr, {})["identical"]


def test_open_loop_replay_of_own_schedule_reproduces_the_closed_loop():
    c = _small()
    rec = run(c, "C", 5, GAINS, configure=lambda loop, spec: setattr(loop.cfg, "light", False))
    sched = [(t, list(items)) for t, items in rec.pop("loop").overlay_changes]

    def replay(loop, spec):
        loop.rep, loop.cfg.triggers, loop.cfg.representation, loop.cfg.replay = None, None, "replay", sched
        for at, items in sched:
            if at == loop.world.state.t:
                loop._replay_apply(items)
    r = run(c, "C", 5, GAINS, configure=replay)
    assert r["final_fp"] == rec["final_fp"]


def test_multiscale_observer_exact_onsets_penetrate_outward():
    g = latent_geometric(800, 2, geo_fraction=0)
    from xzr.lod.hierarchy import build_hierarchy, symmetric_adjacency
    st = g.state
    h = build_hierarchy(symmetric_adjacency(st.src[st.alive], st.dst[st.alive], st.n))
    obs = []
    for eps in (0.0, 0.5):
        s2 = latent_geometric(800, 2, geo_fraction=0).state
        node = int(np.flatnonzero(h.labels[0] == 0)[0])
        s2.diff[node] += eps
        e = Engine(s2, 9, checkpoint_every=0)
        o = MultiScaleObserver(800, 10, macro_labels=h.labels[0], keep_frames=True)
        for _ in range(60):
            o.observe(e.step(), s2)
        obs.append(np.array(o.exact_macro))
    a, b = obs
    first = [next((t for t in range(len(a)) if a[t, k] != b[t, k]), None) for k in range(8)]
    assert first[0] == 0  # the perturbed macro cluster differs from the first step
    later = [f for f in first[1:] if f is not None]
    assert all(f >= 0 for f in later)
    assert not later or min(later) >= first[0]


# ------------------------------------------------------------------------------------------------ compression
def test_long_run_compression_fidelity_on_recurrent_sequences():
    per = np.array([0, 1, 2, 3] * 250)
    assert comp.lz78_phrases(per) < len(per) / 8
    rng = np.random.default_rng(0)
    assert comp.lz78_phrases(rng.integers(0, 32, 1000)) > comp.lz78_phrases(per) * 3
    centers = rng.normal(0, 10, (4, 3))
    x = np.concatenate([centers[k] + rng.normal(0, 0.1, (50, 3)) for k in range(4)])
    cb = comp.kmeans(x, 4, 0)
    sym = comp.encode(x, cb)
    r2 = 1 - ((x - cb[sym]) ** 2).sum() / ((x - x.mean(0)) ** 2).sum()
    assert r2 > 0.99 and len(set(sym.tolist())) == 4


def test_coarse_detection_by_time_average_only_has_no_onset():
    """Regression: a coarse resolution detected only by the time-averaged family has no segment onset; the
    classifier must not fail and must not label it time-window dependent."""
    res = _rows(macro=_res(True, False, "aggregate-only", None))
    c = classify_condition({"exact_identical_share": 0.0, "horizon": 4000, "resolutions": res})
    assert c["primary"] == "NON-REDUNDANT" and "TIME-WINDOW-DEPENDENT" not in c["labels"]
    mixed = _rows(macro=_res(True, False, "aggregate-only", None), meso=_res(True, False, "persistent", 3))
    assert "TIME-WINDOW-DEPENDENT" in classify_condition(
        {"exact_identical_share": 0.0, "horizon": 4000, "resolutions": mixed})["labels"]


def test_runner_persists_jobs_and_resumes_only_missing_seeds(tmp_path, monkeypatch):
    from xzr.experiments.escalation import runner
    calls = []

    def fake_job(args):
        c, seed, _ = args
        calls.append(seed)
        return {"seed": seed, "runs": {}}

    monkeypatch.setattr(runner, "seed_job", fake_job)
    monkeypatch.setattr(runner, "calibrations", lambda conds, procs=7, path=None, base=None: {})
    monkeypatch.setattr(runner, "analyse", lambda c, res, ex: {"n": len(res), "seeds": [r["seed"] for r in res]})

    class Inline:  # run the pool inline (the fake job is not importable by worker processes)
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def submit(self, fn, arg):
            from concurrent.futures import Future
            f = Future()
            f.set_result(fn(arg))
            return f

    monkeypatch.setattr(runner, "ProcessPoolExecutor", Inline)
    monkeypatch.setattr(runner, "as_completed", lambda futs: list(futs))
    out = tmp_path / "m.json"
    c = {"id": "x", "seeds": 3, "n": 10, "horizon": 10, "variants": ("C",)}
    runner._save_job(out, "x", {"seed": runner.SEED0 + 1, "runs": {}})  # one seed already on disk
    doc = runner.run_conditions([c], out, procs=1)
    assert sorted(calls) == [runner.SEED0, runner.SEED0 + 2]  # only the missing seeds ran
    assert doc["conditions"]["x"]["n"] == 3 and len(list((tmp_path / "jobs" / "m" / "x").glob("*.pkl.gz"))) == 3
    calls.clear()
    runner.run_conditions([c], out, procs=1)
    assert calls == []  # complete: nothing reruns
