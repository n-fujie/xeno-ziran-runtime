"""Heterogeneous Philosophical Operations (xzr/hpo): information separation, configuration-dependent ignition,
unobservability, cross-operational transformation, history reinsertion, recursive reconfiguration (sandbox),
statistics, registry and published results."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import numpy as np
import pytest

from xzr.hpo import experiments as X
from xzr.hpo import reconfig, registry, stats
from xzr.hpo.field import ALL_OFF, ALL_ON, RULES, Field, SettingsError, validate
from xzr.hpo.metrics import measure
from xzr.hpo.observe import REASONS, Instruments, InstrumentSpec, Observation, Veil
from xzr.hpo.operations import FIRED, NOT_FIRED, UNOBSERVABLE, make
from xzr.hpo.world import build_world

HPO = Path(__file__).resolve().parents[1] / "xzr" / "hpo"


def _world(seed: int = 90001, gen: int = 9001, n: int = 800):
    w = build_world(n, gen, seed)
    for _ in range(40):
        w.step()
    return w


@pytest.fixture(scope="module")
def warm():
    return _world()


def _run(warm, settings: dict, steps: int = 160, seed: int = 90001, keep: bool = True) -> Field:
    f = Field(warm.fork(), {"horizon": steps, **settings}, seed, keep_states=keep)
    f.run(steps)
    return f


# ------------------------------------------------------------------------------------------ separation of truth
def test_operations_cannot_reach_the_world():
    """operations.py imports no world, engine or state; operations see Observations and return Requests."""
    tree = ast.parse((HPO / "operations.py").read_text())
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in mods if m and ("world" in m or "runtime" in m or "field" in m)}, mods
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"engine", "World", "world", "state", "theta_eff", "diff", "memory"}, names & {
        "engine", "World", "world", "state", "theta_eff", "diff", "memory"}


def test_exogenous_input_is_identical_across_branches_and_noise_changes_only_the_endogenous_stream(warm):
    a, b = warm.fork(), warm.fork(endogenous_seed=12345)
    fa = Field(a, {"interaction": ALL_ON}, 1)
    for _ in range(30):
        fa.step()
        b.step()
    assert a.exo.bit_generator.state == b.exo.bit_generator.state  # same exogenous draws, whatever happened
    assert a.engine.rng.bit_generator.state != b.engine.rng.bit_generator.state


def test_fork_is_bit_identical(warm):
    a, b = warm.fork(), warm.fork()
    for _ in range(25):
        a.step()
        b.step()
    assert a.engine.fingerprint() == b.engine.fingerprint()


# ------------------------------------------------------------------------------------------ unobservability
def test_every_unobservability_reason_is_distinguished_and_never_zero(warm):
    ins = Instruments(warm, catalog=("activity", "tension", "boundary_flow", "recursion"))
    own = warm.h.resolve("0")
    cases = {
        "unmeasurable": (InstrumentSpec(), {"memory": (0, 8)}, 10.0),
        "instrument_mismatch": (InstrumentSpec(channels=("activity",)), {"tension": (0, 8)}, 10.0),
        "scale_mismatch": (InstrumentSpec(level=0), {"tension": (2, 8)}, 10.0),
        "time_window_mismatch": (InstrumentSpec(window=8), {"activity": (0, 4)}, 10.0),
        "unmeasured": (InstrumentSpec(level=2), {"activity": (0, 8)}, 0.0),
    }
    for reason, (spec, needs, budget) in cases.items():
        obs, _ = ins.observe(spec, needs, own, budget, None, viewer="x")
        ch = next(iter(needs))
        assert np.isnan(obs.values[ch]).all(), reason
        assert obs.reason(ch) == reason
    ins.veils.append(Veil("other", warm.h.resolve("1"), 0.9))
    obs, _ = ins.observe(InstrumentSpec(), {"activity": (0, 8)}, own, 10.0, None, viewer="x")
    hidden = obs.reasons["activity"] == "boundary_invisible"
    assert hidden.any() and np.isnan(obs.values["activity"][hidden]).all()
    assert not np.isnan(obs.values["activity"][~hidden]).any()
    assert set(REASONS) == {*cases, "boundary_invisible"}


def test_a_veil_hides_a_region_from_others_but_not_from_its_owner(warm):
    ins = Instruments(warm)
    region = warm.h.resolve("2")
    ins.veils.append(Veil("W", region, 0.8))
    lab = warm.h.labels[1]
    c = np.unique(lab[region])
    o_other, _ = ins.observe(InstrumentSpec(), {"activity": (1, 8)}, region, 10.0, None, viewer="X")
    o_owner, _ = ins.observe(InstrumentSpec(), {"activity": (1, 8)}, region, 10.0, None, viewer="W")
    o_pen, _ = ins.observe(InstrumentSpec(penetration=0.9), {"activity": (1, 8)}, region, 10.0, None, viewer="X")
    assert np.isnan(o_other.values["activity"][c]).all()
    assert not np.isnan(o_owner.values["activity"][c]).any()
    assert not np.isnan(o_pen.values["activity"][c]).any()


def test_missing_essential_value_is_unobservable_not_a_negative_ignition():
    op = make("T", "withdrawal", np.arange(10))
    obs = Observation(t=1, level=1, n_clusters=4, own_clusters=np.array([0]), labels=np.zeros(10, int))
    obs.values["boundary_flow"] = np.full((4, 4), np.nan)
    obs.reasons["boundary_flow"] = np.full(4, "scale_mismatch", dtype=object)
    g = op.evaluate(obs)[0]
    assert g.outcome == UNOBSERVABLE and g.reason == "scale_mismatch"


def test_ignition_reads_observed_values_against_its_threshold():
    op = make("C", "closure", np.arange(10))
    obs = Observation(t=1, level=1, n_clusters=2, own_clusters=np.array([0]), labels=np.zeros(10, int))
    obs.values["activity"] = np.array([0.1, 0.0])
    obs.reasons["activity"] = np.array(["", ""], dtype=object)
    for value, outcome in ((0.9, FIRED), (0.1, NOT_FIRED)):
        obs.values["recursion"] = np.array([value, 0.0])
        obs.reasons["recursion"] = np.array(["", ""], dtype=object)
        assert op.evaluate(obs)[0].outcome == outcome


# ------------------------------------------------------------------------------------------ configuration & ignition
def test_settings_are_validated_and_unknown_keys_rejected():
    assert validate({})["interaction"] == ALL_OFF
    for bad in ({"nonsense": 1}, {"interaction": {"telepathy": True}}, {"ign": {"withdrawal": {"x": 1}}},
                {"kinds": ["hegel"]}, {"schedule": [{"type": "delete_world"}]}):
        with pytest.raises(SettingsError):
            validate(bad)


def test_removing_a_condition_ceases_and_a_changed_configuration_can_reignite(warm):
    """E/F mechanics: removing the essential channel makes the series blind (unobservable, never 'no difference')
    and it ceases; restored under another placement it is evaluated again."""
    sched = [{"at": 20, "type": "remove_channel", "kind": "withdrawal", "channel": "boundary_flow"},
             {"at": 100, "type": "relocate", "kind": "withdrawal", "slot": 1},
             {"at": 100, "type": "restore_channel", "kind": "withdrawal", "channel": "boundary_flow"}]
    always = {"withdrawal": {"threshold": -1.0, "persist": 1}}  # the condition holds whenever it can be observed
    f = _run(warm, {"kinds": ["withdrawal"], "schedule": sched, "ign": always}, 200)
    types = [(e["t"] - f.t0, e["type"]) for e in f.history.events if e["source"] in ("WI", "config")]
    assert any(t < 20 and ty == "ignite" for t, ty in types)
    assert any(t > 20 and ty == "cease" for t, ty in types)
    assert any(t > 100 and ty in ("reignite", "ignite") for t, ty in types)
    assert f.stats["evaluations"][UNOBSERVABLE] > 0


# ------------------------------------------------------------------------------------------ interaction engine
@pytest.fixture(scope="module")
def runs(warm):
    return {c: _run(warm, X.settings_for(c), 200) for c in ("A", "B", "C", "D")}


def test_independent_operations_do_not_transform_each_other(runs):
    by = runs["A"].history.summary()["by_type"]
    for t in ("transform", "filter", "couple", "reclassify"):
        assert by.get(t, 0) == 0, t


def test_transformations_record_before_after_and_their_cause(runs):
    evs = runs["C"].history.events
    tr = [e for e in evs if e["type"] == "transform"]
    assert tr, "mutual transformation condition produced no transformation"
    for e in tr:
        assert e["before"] != e["after"]
        assert e["causes"] and all(evs[c]["type"] in ("act", "revise", "conflict") for c in e["causes"])
        assert e["source"] != e["target"]


def test_rules_are_explicit_and_name_registry_kinds():
    for sk, trig, rel, tk, eff in RULES:
        assert sk in registry.KINDS and (tk == "*" or tk in registry.KINDS)
        assert trig in ("act", "deposit") and rel in ("overlap", "near") and eff[0] in ("primary", "ign", "rule", "budget")


def test_mutual_transformation_produces_a_different_world(runs):
    a, c = runs["B"], runs["C"]
    assert a.world.engine.fingerprint() != c.world.engine.fingerprint()
    assert measure(c)["transformations"] > 0


def test_history_reinsertion_enters_later_conditions(runs):
    d, c = runs["D"], runs["C"]
    assert d.stats["reinsertions"] > 0
    rein = {e["id"] for e in d.history.events if e["type"] == "reinsert"}
    assert d.world.engine.fingerprint() != c.world.engine.fingerprint()
    # some later event lists a reinsertion among its causes, or a reinsertion changed an operation's parameters
    assert any(set(e["causes"]) & rein for e in d.history.events) or any(
        e["type"] == "reinsert" and e.get("before") != e.get("after") and e["target"] != "world" for e in d.history.events)


def test_partition_changes_create_composite_kinds_with_lineage(warm):
    found = False
    for seed in range(90001, 90007):
        w = _world(seed, 9000 + seed % 7)
        f = Field(w, {"interaction": ALL_ON}, seed)
        f.run(240)
        comps = [o for o in f.ops.values() if len(o.kinds) > 1]
        if comps:
            found = True
            for z in comps:
                assert z.lineage and z.label == "∘".join(z.kinds)
                assert all(k in registry.KINDS for k in z.kinds)
            break
    assert found, "no coupling in six seeds"


def test_closure_filter_changes_other_operations_acts(warm):
    for seed in range(90001, 90007):
        f = _run(_world(seed, 9000 + seed % 7), {"interaction": ALL_ON}, 240, seed)
        filt = [e for e in f.history.events if e["type"] == "filter"]
        if filt:
            e = filt[0]
            assert e["before"] != e["after"] and e["source"] != e["target"]
            return
    pytest.fail("no filtered act in six seeds")


def test_runs_are_reproducible(warm):
    a = _run(warm, X.settings_for("D"), 120, keep=False)
    b = _run(warm, X.settings_for("D"), 120, keep=False)
    assert a.world.engine.fingerprint() == b.world.engine.fingerprint()
    assert json.dumps(X.clean(measure(a)), sort_keys=True) == json.dumps(X.clean(measure(b)), sort_keys=True)


# ------------------------------------------------------------------------------------------ HPO-003 sandbox
def test_sandbox_rejects_everything_outside_its_paths(warm):
    f = Field(warm.fork(), {}, 1)
    for bad in ({"path": "world.diff", "value": 1}, {"path": "rule.withdrawal.depth", "value": 0.1},
                {"path": "instruments.withdrawal.level", "value": 9}, {"path": "catalog", "value": "interior"},
                {"path": "order", "value": ["withdrawal"]}, {"path": "instruments.hegel.level", "value": 1},
                {"path": "allocation.closure", "value": 100.0}, {"path": "catalog", "value": "x", "code": "import os"}):
        with pytest.raises(reconfig.SandboxError):
            reconfig.apply(f, bad, [])
    assert not [e for e in f.history.events if e["source"] == "ziran"]


def test_reconfiguration_is_recorded_and_changes_live_operations(warm):
    f = Field(warm.fork(), {}, 1)
    eid = reconfig.apply(f, {"path": "instruments.withdrawal.level", "value": 2}, [])
    ev = f.history.events[eid]
    assert ev["source"] == "ziran" and ev["before"] != ev["after"]
    assert all(o.instrument.level == 2 for o in f.live() if "withdrawal" in o.kinds)


def test_recursive_controller_is_deterministic_and_proposals_are_not_validations(warm):
    traces = []
    for _ in range(2):
        f = Field(warm.fork(), X.settings_for("D"), 7)
        ctl = reconfig.Controller("recursive", 7)
        ctl.start(f)
        for ep in range(3):
            f.run(reconfig.EPOCH)
            ctl.end_epoch(f, ep)
        traces.append(json.dumps(ctl.trace, sort_keys=True, default=str))
        assert all(p["status"] != "validated (held-out seeds)" for p in ctl.proposals)
    assert traces[0] == traces[1]


# ------------------------------------------------------------------------------------------ statistics
def test_sign_flip_exact_and_holm():
    rng = np.random.default_rng(0)
    assert stats.sign_flip_p(np.ones(10), rng) == pytest.approx(2 / 1024)
    assert stats.sign_flip_p(np.zeros(5), rng) == 1.0
    h = stats.holm({"a": 0.01, "b": 0.02, "c": 0.5})
    assert h["a"] == pytest.approx(0.03) and h["b"] == pytest.approx(0.04) and h["c"] == 0.5


def test_classification_uses_noise_floor_and_keeps_undefined_apart():
    rows_x = [{"m": 1.0 + 0.01 * i, "u": math.nan} for i in range(20)]
    rows_y = [{"m": 0.0, "u": math.nan} for _ in range(20)]
    c = stats.contrast(rows_x, rows_y, ["m", "u"], {"m": np.full(20, 5.0)}, 1)
    assert c["m"]["status"] == "UNRESOLVED"  # larger effect than chance, but not than the noise comparison
    assert c["u"]["status"] == "NOT MEASURED"
    c2 = stats.contrast(rows_x, rows_y, ["m"], None, 1)
    assert c2["m"]["status"] == "DETECTED"


# ------------------------------------------------------------------------------------------ registry & protocol
def test_registry_entries_are_complete_and_honest_about_sources():
    need = {"kind", "series", "sources", "central_claim", "minimal_shape", "configuration_conditions", "ignition",
            "rule", "coupling", "split", "cessation", "reignition", "observables", "history_reinsertion",
            "real_effects", "approximation", "failure", "revision"}
    snap = registry.snapshot()
    assert snap["fidelity"] == "engineering proxy"
    for e in snap["entries"]:
        assert need <= set(e), e["kind"]
        assert all(s["status"] in ("bibliographic", "consulted") for s in e["sources"])
        assert e["fidelity"] == "engineering proxy"
    assert {e["kind"] for e in snap["entries"]} == set(registry.KINDS)
    assert all(c["status"].startswith("not implemented") for c in snap["candidates"])


def test_no_series_requires_a_human_subject_or_language_by_default():
    snap = json.dumps(registry.snapshot()).lower()
    assert "human" not in snap
    s = validate({})
    assert s["picturing_requires_symbol_channel"] is False and s["symbol_layer"] is False


def test_protocol_is_frozen_at_the_pinned_hash():
    assert X.PROTOCOL.exists()
    assert X.PROTOCOL_SHA256 != "UNFROZEN" and X.protocol_hash() == X.PROTOCOL_SHA256


# ------------------------------------------------------------------------------------------ published results
RESULT_FILES = ("hpo001", "hpo002", "hpo003", "general", "verification")


@pytest.mark.parametrize("name", RESULT_FILES)
def test_published_results_are_strict_json_and_record_the_protocol(name):
    p = X.RESULTS / f"{name}.json"
    if not p.exists():
        pytest.skip(f"{p.name} not generated yet")
    doc = json.loads(p.read_text(), parse_constant=lambda c: pytest.fail(f"non-strict JSON constant {c}"))
    if name != "verification":
        assert doc.get("provenance", {}).get("protocol_sha256") == doc["provenance"]["pinned_protocol_sha256"]


def test_hpo_texts_do_not_claim_validation_of_doctrines():
    root = Path(__file__).resolve().parents[2]
    bad = __import__("re").compile(r"\b(proves?\b|confirm(s|ed)? (the|that) (philosoph|doctrine|theory)|validat(es|ed) "
                                   r"(the )?(philosoph|doctrine|theory)|empirically (validated|verified))", 2)
    for p in (root / "docs" / "HPO.md", root / "frontend" / "src" / "views" / "research" / "HPOView.tsx",
              HPO / "registry.py"):
        assert not bad.search(p.read_text()), p.name
