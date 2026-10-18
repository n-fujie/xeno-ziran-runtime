"""Xeno-14: the fourteen principles are the ones of the existing specification, not renamed, not summed into one score."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from xzr.xbtro import engine, metrics, xeno14
from xzr.xbtro.experiments import base_config

HERE = Path(__file__).resolve()
SIBLING = [p for p in (HERE.parents[3] / "ziran-xeno-simulator", Path("/Users/user/Desktop/BIM/ziran-xeno-simulator")) if p.exists()]
SEEDS = [5000 + i for i in range(6)]


def test_there_are_fourteen_principles_with_the_canonical_names():
    assert len(xeno14.PRINCIPLES) == 14 and len({p["id"] for p in xeno14.PRINCIPLES}) == 14


@pytest.mark.skipif(not SIBLING, reason="the sibling repository ziran-xeno-simulator is not available")
def test_names_and_order_match_the_source_files():
    root = SIBLING[0]
    body = (root / "src/domains/body.ts").read_text()
    block = body[body.index("export const XENO14 = ["): body.index("] as const")]
    source_ids = re.findall(r"'([a-z\-]+)'", block)
    assert [p["id"] for p in xeno14.PRINCIPLES] == source_ids
    py = (root / "embodied/xeno14/principles.py").read_text()
    pairs = re.findall(r'\("([a-z\-]+)", "([^"]+)"\)', py)
    assert [(p["id"], p["alias"]) for p in xeno14.PRINCIPLES] == pairs      # aliases unchanged, including the one flagged uncertain


@pytest.mark.skipif(not SIBLING, reason="the sibling repository ziran-xeno-simulator is not available")
def test_the_thresholds_quoted_in_the_definitions_are_in_the_source():
    body = (SIBLING[0] / "src/domains/body.ts").read_text()
    for pid, needles in {"axis-maintenance": ["> 0.02"], "lower-abdominal-continuity": ["< 0.6"], "whole-skin-sensing": ["> 0.03"],
                         "anti-collapse-posture": ["0.55"], "breathing-synchronization": ["> 0.04"], "slow-movement": ["> 0.6"],
                         "fingertip-tension": ["< 0.4"], "narrow-step-balance": ["0.7"]}.items():
        for n in needles:
            assert n in body, (pid, n)
            assert n.strip("<> ") in xeno14.BY_ID[pid]["source_rule"], (pid, n)


def test_every_principle_states_its_fidelity_and_proxies_are_named():
    for p in xeno14.PRINCIPLES:
        assert p["fidelity"] in ("translated", "partial", "proxy-only") and p["gap"] and p["source_rule"]
    proxies = {p["id"] for p in xeno14.PRINCIPLES if p["fidelity"] == "proxy-only"}
    assert proxies == {"minimal-approach-distance", "fingertip-tension", "long-duration-sedimentation"}


def test_principles_can_fire_in_parallel_and_each_has_its_own_line():
    cfg = xeno14.apply(base_config("human-like-planar"), ["axis-maintenance", "whole-skin-sensing", "lower-abdominal-continuity", "breathing-synchronization"])
    ids = {ln["id"] for ln in cfg["lines"]}
    assert {"xeno.axis-maintenance", "xeno.whole-skin-sensing", "xeno.lower-abdominal-continuity", "xeno.breathing-synchronization"} <= ids
    r = engine.simulate(cfg, SEEDS)
    fired = [lid for lid in r.line_ids if lid.startswith("xeno.") and r["line_active"][:, :, r.line_ids.index(lid)].any()]
    assert len(fired) >= 2                                 # more than one principle ignites in the same configuration


def test_a_principle_with_an_unreachable_condition_does_not_ignite():
    cfg = xeno14.apply(base_config("human-like-planar"), ["anti-collapse-posture"])
    r = engine.simulate(cfg, SEEDS)
    j = r.line_ids.index("xeno.anti-collapse-posture")
    assert not r["line_active"][:, :, j].any()             # the excursion needed for ignition never happens in the protocol


def test_no_single_score_the_effects_are_per_organization():
    cfg = xeno14.apply(base_config("human-like-planar"), ["axis-maintenance"])
    om = metrics.organization(engine.simulate(cfg, SEEDS))
    assert set(om) == set(metrics.ORGANIZATION) and len(om) == 7


def test_a_switched_off_rule_line_contributes_nothing():
    """Regression: the ablation control (same edits, rule line off) must really remove the rule's drive."""
    on = xeno14.apply(base_config("human-like-planar"), ["axis-maintenance"])
    off = copy_with_line_off(on, "xeno.axis-maintenance")
    r_on, r_off = engine.simulate(on, SEEDS), engine.simulate(off, SEEDS)
    j = r_on.line_ids.index("xeno.axis-maintenance")
    assert r_on["line_active"][:, :, j].any() and not r_off["line_active"][:, :, j].any()
    assert np.abs(r_off["line_u"][:, :, j]).max() == 0.0
    base = engine.simulate(base_config("human-like-planar"), SEEDS)
    assert np.array_equal(base["com"], r_off["com"])        # axis-maintenance has no parameter edits: with its line off the body is the control


def copy_with_line_off(cfg, lid):
    import copy
    out = copy.deepcopy(cfg)
    for ln in out["lines"]:
        if ln["id"] == lid:
            ln["enabled"] = False
    return out
