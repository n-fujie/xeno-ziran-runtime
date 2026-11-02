"""Stage 6: the saved results say what the document says (the numbers of the document come from these files), and the semantics that were corrected are kept."""

from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
need = pytest.mark.skipif(not (DOCS / "experiments_stage6_final.json").exists(), reason="the stage 6 experiments have not been run")


def load(name: str) -> dict:
    return json.loads((DOCS / f"experiments_stage6{name}.json").read_text())


@need
def test_an_open_window_is_open_through_the_tested_limit_and_has_no_irreversible_tick():
    """The rule: a window still effective at the last tick tested has not closed (no irreversible tick). Shown on the saved Pipeline B windows as they were before the extension (three are open at tick 330), and then on the extended measurement (all closed)."""
    from xzr.meos import stage6_final as F

    a, b, o = load(""), load("_refine"), load("_open_windows")
    three = ("coupling gain 0.5", "renewal stopped", "Address partial 0.5")
    for sid in three:
        r = F.stress_row(a, b, sid)
        assert r["irreversibility"] == "OPEN_THROUGH_TESTED_LIMIT" and r["irreversible_tick"] is None and r["latest_successful_repair_tick"] == r["tested_range_end"] == 330  # the end of the range is not a closure
    ext = F.with_extension(b, o)
    for sid, latest in zip(three, (388, 383, 383), strict=True):
        r = F.stress_row(a, ext, sid)
        assert r["irreversibility"] == "CLOSED" and r["latest_successful_repair_tick"] == latest and r["irreversible_tick"] == latest + 1 and r["tested_range_end"] is None
    for w in o["windows"]:  # every window of the extension ended inside the range tested, and none is effective after its last effective tick
        assert w["latest_effective_tick"] < w["ticks_tested"][1] and not [t for t in w["effective_ticks"] if t > w["latest_effective_tick"]]
    rows = {r["stress"]: r for r in load("_final")["stress_table"]}
    for r in rows.values():
        assert r["irreversibility"] == "CLOSED" and r["irreversible_tick"] == r["latest_successful_repair_tick"] + 1 and r["tested_range_end"] is None
    assert [r["irreversible_tick"] for r in rows.values()] == [389, 110, 112, 384, 384, 121]


@need
def test_the_three_pulse_windows_that_stayed_open_were_measured_to_tick_330_and_then_to_1140():
    b = load("_refine")
    assert b["B1_extension"]["ticks"] == [171, 330] and b["B1_extension"]["windows_extended"] == 3
    want = {("coupling gain 0.5", (("resource.pulse", 1.0, 0),)), ("Address partial 0.5", (("address.restore", 0.0, 0), ("resource.pulse", 1.0, 0))), ("renewal stopped", (("renewal.restart", 0.0, 0), ("resource.pulse", 1.0, 0)))}
    got = {(w["stress"], tuple(map(tuple, w["parts"]))): w for w in b["B1_windows"] if w["latest_effective_tick"] == 330}
    assert set(got) == want  # Pipeline B as it was: the first range ended at 330 with these three still effective
    for w in got.values():
        assert w["effective_intervals"][-1][1] == 330 and w["ticks_tested"][1] == 330 and len(w["per_tick"]) == 230  # every tick 101-330 has its per-tick result, failures included
    o = load("_open_windows")
    assert o["extended_horizon"] == 1200 and o["last_tick_tested"] == 1140 and {(w["stress"], tuple(map(tuple, w["parts"]))) for w in o["windows"]} == want
    for w in o["windows"]:
        assert w["ticks_tested"] == [331, 1140] and len(w["per_tick"]) == 810  # every tick 331-1140, failures included


@need
def test_the_closure_ticks_are_recomputed_from_the_per_tick_results_and_the_energy_gate_explains_them():
    """Independent of the stored summaries: the last effective tick is recomputed from the per-tick counts, and the closure is checked against the rule read from the traces (A1's energy at the start of the intervention tick must reach its firing cost)."""
    o, m = load("_open_windows"), load("_open_mechanism")
    for w in o["windows"]:
        eff = [int(t) for t, v in w["per_tick"].items() if v["exploration"] == "5/5" and v["validation"] == "5/5"]
        assert max(eff) == w["latest_effective_tick"] and sorted(eff) == w["effective_ticks"]
        assert all(int(t) <= w["latest_effective_tick"] for t in eff) and not [t for t in eff if t > w["latest_effective_tick"]]
    cost = m["a1_firing_cost"]
    names = {"coupling gain 0.5": "coupling", "renewal stopped": "renewal stopped", "Address partial 0.5": "Address"}
    for w in o["windows"]:
        b = m["boundary"][names[w["stress"]]]
        assert b["last_effective_tick"] == w["latest_effective_tick"]
        for t, v in b["by_tick"].items():
            lo, hi = v["a1_energy_at_start_of_t"]
            assert (v["recovered_at_1200"] == v["seeds"]) == (lo >= cost - 1e-9)  # every seed recovers exactly when every seed has the energy to fire
            assert (v["recovered_at_1200"] > 0) == (hi >= cost - 1e-9)  # some seed recovers exactly when some seed has it
            assert v["sustained_within_60"] == v["recovered_at_1200"] and v["tracked_ticks"] == 1200 - int(t) and v["tracked_ticks"] >= 2 * m["recovery_window"]  # the post-intervention criterion that is the same for every tick agrees; every run is followed for at least 2W ticks
    for c in m["upkeep_control"].values():
        assert all(v["recovered_at_1200"] == v["of"] for v in c["branch_at_300"].values())  # with the common history and upkeep 0 after tick 300 every tested tick recovers


@need
def test_the_regenerated_validation_and_evaluation_rows_give_the_saved_summaries():
    """The run-level rows of the validation (6-10) and evaluation (11-30) runs were regenerated (they were saved only as summaries): every setting's counts and outcome counts equal the saved summary."""
    v = json.loads((DOCS / "evidence" / "run_rows_verification.json").read_text())
    assert v["settings"] == v["settings_matching_the_saved_summary"] == len(v["results"]) and v["mismatches"] == []
    with gzip.open(DOCS / "experiments_stage6_validation_evaluation_rows.jsonl.gz", "rt") as f:
        head = json.loads(f.readline())
        rows = [json.loads(line) for line in f]
    assert head["note"].startswith("regenerated") and len(rows) == v["runs"]
    seeds = {r["seed"] for r in rows}
    assert seeds == set(range(6, 31)) and {r["origin"] for r in rows} == {"A", "follow-up"}  # validation and evaluation seeds only; the exploration rows (1-5) are in the original raw files


@need
def test_every_cell_of_the_grid_is_in_the_csv_whatever_its_outcome():
    a = load("")
    rows = list(csv.DictReader((DOCS / "experiments_stage6_cells.csv").open()))
    assert len(rows) == len(a["table"]) and {"effective", "partial", "not effective"} == {r["status"] for r in rows}
    assert sum(r["status"] == "not effective" for r in rows) > sum(r["status"] == "effective" for r in rows)  # failures outnumber successes and none was dropped
    t = list(csv.DictReader((DOCS / "experiments_stage6_results_table.csv").open()))
    assert [r["irreversibility"] for r in t] == ["CLOSED"] * 6 and [r["irreversible_tick"] for r in t] == ["389", "110", "112", "384", "384", "121"]  # no window is open at the end of the extended range


@need
def test_the_raw_rows_keep_the_seed_sets_apart_and_every_run():
    with gzip.open(DOCS / "experiments_stage6_raw.jsonl.gz", "rt") as f:
        seeds = {json.loads(line)["seed"] for line in f}
    assert seeds == {1, 2, 3, 4, 5}  # exploration only: validation (6-10) and evaluation (11-30) are never mixed into it
    a = load("")
    assert a["seeds"] == {"exploration": [1, 2, 3, 4, 5], "validation": [6, 7, 8, 9, 10], "evaluation": [11, 30]} and a["counts"]["exploration_runs"] == 12390
    for n in ("", "_refine", "_cross", "_controllers", "_final"):
        assert (DOCS / f"experiments_stage6{n}_all_horizons_criterion.json").exists()  # the results of the first criterion are kept


@need
def test_the_resource_pulse_is_not_monotone_for_the_coupling_stress():
    p = next(s for s in load("_refine")["B2_pulse_sweeps"] if s["stress"] == "coupling gain 0.5")
    assert p["effective_band"] == [0.6, 2.5]
    ph = {r["magnitude"]: r["phase"] for r in p["rows"]}
    assert ph[0.5] == "insufficient intervention" and ph[0.6] == "effective recovery" and ph[2.5] == "effective recovery" and ph[2.6] == "overshoot" and ph[6.0] == "overshoot"


@need
def test_stage_5_results_stand_under_the_stage_6_criterion():
    c = load("_refine")["B4_stage5_consistency"]["by_seed_set"]
    for v in c.values():
        n = v["stage6_long"].split("/")[1]
        assert v["stage5_style_active_at_300"] == v["stage6_short"] == v["stage6_medium"] == v["stage6_long"] == f"{n}/{n}"


@need
def test_the_controllers_say_what_the_document_says():
    c = load("_controllers")
    idx = {(s["stress"], s["controller"]): s["success_long"]["k"] for s in c["summary"]}
    assert (idx[("coupling gain 0.5", "fixed")], idx[("coupling gain 0.5", "cost_aware")], idx[("coupling gain 0.5", "rule_based")]) == (20, 20, 0)  # a known fixed repair equals the cost-aware one; restoring the parameter alone is null
    assert (idx[("Address partial 0.5", "cost_aware")], idx[("Address partial 0.5", "rule_based")]) == (0, 8)  # the cost-aware controller is worse than the simple rule here
    assert idx[("history lost", "rule_based")] == idx[("history lost", "cost_aware")] == 9 and idx[("coupling gain 0.3 (stronger drop)", "fixed")] == 0  # a held-out stronger drop is not generalised
    fp = {s["controller"]: s for s in c["false_positives"]}
    assert all(fp[k]["mean_attempts"] == 0 for k in ("fixed", "rule_based", "cost_aware", "delayed", "none")) and fp["noisy"]["mean_attempts"] > 0 and all(s["success_long"]["k"] == 20 for s in fp.values())
    assert c["seeds"]["evaluation"] == [11, 30]


@need
def test_the_address_repair_is_three_restorations_and_the_observation_is_not_the_run():
    x = load("_cross")
    rows = {r["case"]: r for r in x["C4_address_three_restorations"]["rows"]}
    r113 = rows["Address restore at 113"]
    assert r113["operational_restoration"] == "0/5" and r113["address_restoration"] == "5/5"  # the Address returns, the operation does not
    assert x["C3_observation"]["operationally_recovered_but_not_observed"] > 0
    assert all(r["agrees"] for r in x["C3_observation"]["rows"] if r["observation"] == "full observation")


@need
def test_the_document_is_what_the_data_produce():
    out = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "make_stage6_doc.py"), "--check"], capture_output=True, text=True, env={"PYTHONPATH": str(Path(__file__).resolve().parents[1]), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr[-400:]
