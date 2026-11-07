"""Tests of the SBS follow-ups: sensitivity variants, replication, ON-02 persistence criteria and ON-03 fragility transfer (xzr.sbs)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from xzr.sbs import on_fragility as of
from xzr.sbs import on_persistence as op
from xzr.sbs import organisation as org
from xzr.sbs import protocol as P
from xzr.sbs import sensitivity as sens

DOCS = Path(__file__).resolve().parents[2] / "docs" / "sbs"


def test_a_sensitivity_variant_changes_the_protocol_only_inside_the_context_and_restores_it_even_after_an_error():
    before, r0 = copy.deepcopy(P.PROTOCOL), org.R_BOND
    with sens.applied({"model.n": 40, "r_bond": 1.2, "scale_steps": 2}):
        assert P.PROTOCOL["model"]["n"] == 40 and org.R_BOND == 1.2
        assert P.PROTOCOL["formation_steps"] == 2 * before["formation_steps"]
        assert P._cfg().n == 40
    assert before == P.PROTOCOL and r0 == org.R_BOND
    with pytest.raises(RuntimeError), sens.applied({"model.density": 0.15}):
        raise RuntimeError("boom")
    assert before == P.PROTOCOL and r0 == org.R_BOND


def test_the_default_contact_cutoff_is_bit_identical_to_the_explicit_one_and_a_variant_cutoff_changes_the_graph():
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 8, size=(40, 2))
    assert np.array_equal(org.contact_graph(x, 8.0), org.contact_graph(x, 8.0, org.R_BOND))
    with sens.applied({"r_bond": 2.5}):
        assert org.contact_graph(x, 8.0).sum() > org.contact_graph(x, 8.0, 1.35).sum()


def test_every_variant_changes_exactly_one_convention_and_the_frozen_digest_is_untouched():
    digest = P.PROTOCOL_DIGEST
    for name, (kind, change) in sens.VARIANTS.items():
        assert kind in ("world", "hold")
        assert len({k.split(".")[0] for k in change if k != "scale_steps"}) <= 1, name  # one section of the protocol (the hold variants move the hold and its measuring window together)
    assert digest == P.PROTOCOL_DIGEST


def test_bond_retention_and_shape_without_membership_on_a_constructed_configuration():
    box = 30.0
    ref_pos = np.array([[0.0, 0.0], [1.1, 0.0], [0.0, 1.1], [1.1, 1.1], [2.2, 0.0]])
    others = np.array([[15.0 + 1.1 * i, 15.0 + 1.1 * j] for i in range(3) for j in range(2)])
    x = np.vstack([ref_pos, others])
    ref = np.arange(5)
    pairs = op.reference_pairs(x, box, ref)
    assert len(pairs) > 0 and op.bond_retention(x, box, pairs) == 1.0
    y = x.copy()
    y[4] = [10.0, 10.0]
    assert op.bond_retention(y, box, pairs) < 1.0
    # the reference stays together: no 'shape without membership'
    assert op.shape_without_membership(x, box, ref) is False
    # the reference is scattered while a different group of about its size exists: shape without membership
    z = x.copy()
    z[:5] = np.array([[3.0, 20.0], [9.0, 25.0], [20.0, 3.0], [26.0, 9.0], [5.0, 12.0]])
    assert org.partition(z, box).max() >= 0
    assert op.shape_without_membership(z, box, ref) is True


def _cell(**persists):
    base = {"physical_cohesion_at_end": True, "membership_at_end": True, "local_configuration_at_end": True, "functional_dependency_at_end": True, "cohesion_never_lost_during_run": True}
    return {"persists": {**base, **persists}}


def test_disagreements_count_each_pair_of_criteria_and_skip_undefined_ones():
    cells = [_cell(), _cell(membership_at_end=False), _cell(membership_at_end=False, functional_dependency_at_end=None), _cell(cohesion_never_lost_during_run=False)]
    d = op.disagreements(cells)
    a = d["physical_cohesion_at_end vs membership_at_end"]
    assert a == {"cells": 4, "disagree": 2, "only_first": 2, "only_second": 0}
    assert d["membership_at_end vs functional_dependency_at_end"]["cells"] == 3
    assert d["membership_at_end vs cohesion_never_lost_during_run"]["only_second"] == 2  # membership lost although cohesion was never lost (two cells)


def _rows(perf, single, steps, mob, anneal_after, anneal_ctrl, load=1.0, n=8):
    rows = {e: {} for e in of.DESIGNS}
    rng = np.random.default_rng(1)
    for e in of.DESIGNS:
        for s in range(n):
            j = rng.normal(0, 0.01)
            high = e == 2.0
            r = {"seed": s, "eps": e, "performance_overlap": (perf if high else 0.5) + j, "repair": {"single_group": bool(single if high else True), "steps_to_half": steps if high else 250, "largest_share_after_recovery": 0.5},
                 "mobility_msd_500": (mob if high else 0.3) + abs(j), "load_retention": load, "energy_per_particle": -1.0}
            if not (single if high else True):
                r["anneal"] = {"single_group_after_anneal": anneal_after, "single_group_after_control": anneal_ctrl}
            rows[e][s] = r
    return rows


def test_fragility_transfer_needs_the_mechanism_evidence_and_an_association_alone_is_not_enough():
    transfer = of.verdicts(_rows(perf=0.8, single=False, steps=2500, mob=0.1, anneal_after=True, anneal_ctrl=False))["2.0"]
    assert transfer["verdict"] == "TRANSFER_SUPPORTED" and transfer["mechanism_a_present"] and transfer["mechanism_b_present"]
    assoc = of.verdicts(_rows(perf=0.8, single=False, steps=2500, mob=0.1, anneal_after=False, anneal_ctrl=False))["2.0"]
    assert assoc["verdict"] == "WORSE_REPAIR_MECHANISM_NOT_SHOWN"
    no_mob = of.verdicts(_rows(perf=0.8, single=False, steps=2500, mob=0.5, anneal_after=True, anneal_ctrl=False))["2.0"]
    assert no_mob["verdict"] == "WORSE_REPAIR_MECHANISM_NOT_SHOWN"
    free = of.verdicts(_rows(perf=0.8, single=True, steps=250, mob=0.1, anneal_after=True, anneal_ctrl=False))["2.0"]
    assert free["verdict"] == "IMPROVEMENT_WITHOUT_DETECTED_TRANSFER"
    flat = of.verdicts(_rows(perf=0.5, single=True, steps=250, mob=0.3, anneal_after=True, anneal_ctrl=False))["2.0"]
    assert flat["verdict"] == "NOT_AN_IMPROVEMENT"


def test_pareto_keeps_incomparable_designs_and_marks_only_dominated_ones():
    rows = {e: {0: {"performance_overlap": p, "repair": {"single_group": bool(s)}, "load_retention": ld}} for e, (p, s, ld) in zip(of.DESIGNS, [(0.4, 1, 0.9), (0.5, 1, 0.9), (0.9, 0, 0.9), (0.4, 1, 0.5)])}
    out = of.pareto(rows)
    assert 1.5 in out["retained_non_dominated"] and 2.0 in out["retained_non_dominated"]  # incomparable: better performance vs better repair
    assert out["dominated_by"]["1.0"] == [1.5] and out["dominated_by"]["2.5"] == [1.0, 1.5]


def test_the_replication_record_uses_the_frozen_protocol_and_worlds_that_the_first_run_did_not_use():
    rec = json.loads((DOCS / "sbs_replication.json").read_text())
    first = json.loads((DOCS / "sbs_records.json").read_text())
    assert rec["protocol_digest"] == P.PROTOCOL_DIGEST == first["protocol_digest"]
    assert not set(rec["seeds"]["worlds"]) & set(first["seeds"]["worlds"])
    assert not set(rec["seeds"]["test"]) & set(first["seeds"]["train"] + first["seeds"]["test"])
    assert len(rec["seeds"]["test"]) == 32 and rec["comparison"]["margin"] == first["comparison"]["margin"]


def test_on02_series_agree_with_the_sbs_records_at_the_end_of_the_intervention():
    rec = json.loads((DOCS / "sbs_on02.json").read_text())
    first = json.loads((DOCS / "sbs_records.json").read_text())
    assert rec["protocol_digest"] == first["protocol_digest"]
    worlds = {w["seed"]: w for w in first["worlds"]}
    checked = 0
    for c in rec["cells"]:
        b = next(b for b in worlds[c["seed"]]["branches"] if b["kind"] == c["kind"] and b["level"] == c["level"])
        # the persistence record and the SBS record come from the same branch (same noise): the values at the end agree
        assert abs(b["reconfiguration"]["organizational"]["best_overlap"] - c["values_at_end"]["overlap"]) < 1e-12
        assert abs(b["reconfiguration"]["physical"]["largest_share"] - c["values_at_end"]["largest_share"]) < 1e-12
        checked += 1
    assert checked == 32 * len(op.BRANCHES)
    assert rec["not_applicable_on_this_substrate"] and "task performance (no task)" in rec["not_applicable_on_this_substrate"]


def test_on03_record_reports_every_design_the_not_applicable_measures_and_retains_the_pareto_set():
    rec = json.loads((DOCS / "sbs_on03.json").read_text())
    assert rec["designs_eps"] == of.DESIGNS and str(of.BASELINE) not in rec["verdicts_against_baseline"]
    assert set(rec["per_design"]) == {str(e) for e in of.DESIGNS}
    assert rec["pareto"]["retained_non_dominated"]
    assert "maintenance" in rec["not_applicable_on_this_substrate"]
    allowed = {"NOT_AN_IMPROVEMENT", "TRANSFER_SUPPORTED", "WORSE_REPAIR_MECHANISM_NOT_SHOWN", "IMPROVEMENT_WITHOUT_DETECTED_TRANSFER"}
    assert all(v["verdict"] in allowed for v in rec["verdicts_against_baseline"].values())
