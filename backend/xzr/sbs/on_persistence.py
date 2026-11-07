"""ON-02 on the SBS substrate: persistence is not one thing. NEW condition; not a reproduction of any ON Lab experiment (the ON Lab sources are not on this machine).

For one formed world and a few interventions, the SAME run is read by SEVERAL persistence criteria that are kept apart, and the record asks where they disagree:

* local configuration       share of the reference group's initial contact PAIRS that are still in contact
* organizational relations  best Jaccard overlap of the reference membership with any current group (as in SBS-04)
* functional dependency     force transmission of the pulled group (as in SBS-03), at the end of the intervention and at the end of the recovery
* repair capacity           steps after the end of the intervention until the largest group holds half of the particles again (None if never)
* physical continuity       the largest-group share
* survival time             first sample at which each of the above falls below its convention (a finite-run summary, kept as ONE record among several, not as the measure)
* shape without membership  at the end, a group whose size is within 20% of the reference size exists but its overlap with the reference is below 0.5: a description that sees only the shape would call it continuous
* historically identified continuity: here only the tracked MEMBERSHIP (particle labels carried through the run) stands for it; particles have no other history, so this is a very thin stand-in and the record says so

Not applicable on this substrate and therefore NOT computed: task performance (no task), resource access (no resources), technical lineage (no producers or copies). No quantity here is a probability of failure, and no number is offered as a measure of existential non-guarantee; the finite run is one view among several, as the specification demands.

The branches reuse the noise seeds of ``protocol.run_branch`` (seed + 31), so the end-of-intervention fields can be checked against ``docs/sbs/sbs_records.json`` (a test does)."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import organisation as org
from . import protocol as P
from .engine import Sim

BRANCHES = [(None, None), ("decoupling", 0.3), ("decoupling", 0.0), ("heating", 1.2), ("heating", 2.0)]
CONVENTIONS = {"membership_overlap": 0.8, "bond_retention": 0.8, "cohesion_share": 0.5, "shape_size_tolerance": 0.2, "shape_membership_below": 0.5, "transmission_fraction_of_control": 0.5}


def reference_pairs(x: np.ndarray, box: float, reference: np.ndarray) -> set[tuple[int, int]]:
    adj = org.contact_graph(x, box)
    ref = sorted(int(i) for i in reference)
    return {(a, b) for a in ref for b in ref if a < b and adj[a, b]}


def bond_retention(x: np.ndarray, box: float, pairs0: set[tuple[int, int]]) -> float:
    if not pairs0:
        return 0.0
    adj = org.contact_graph(x, box)
    return sum(bool(adj[a, b]) for a, b in pairs0) / len(pairs0)


def shape_without_membership(x: np.ndarray, box: float, reference: np.ndarray) -> bool:
    """True when the reference membership has no continuation (best overlap with any current group below 0.5) although some group has about the reference size: a description that reads shape only would call that group the continuation."""
    lab = org.partition(x, box)
    tol, below = CONVENTIONS["shape_size_tolerance"], CONVENTIONS["shape_membership_below"]
    ref = set(int(i) for i in reference)
    groups = [set(int(i) for i in np.flatnonzero(lab == k)) for k in set(int(v) for v in lab if v >= 0)]
    if not groups or max(len(ref & g) / len(ref | g) for g in groups) >= below:
        return False
    return any(abs(len(g) - len(ref)) <= tol * len(ref) for g in groups)


def run_branch(formed: Sim, reference: np.ndarray, pairs0: set, kind: str | None, level: float | None, seed: int) -> dict[str, Any]:
    sim = formed.clone(seed + 31)
    spec = P.PROTOCOL["interventions"].get(kind) if kind else None
    steps = spec["duration_steps"] if spec else P.PROTOCOL["interventions"]["decoupling"]["duration_steps"]
    se = P.PROTOCOL["sample_every"]
    over: dict[str, Any] = {} if not spec else {spec["variable"]: level}
    series: list[dict[str, Any]] = []
    def sample(phase: str, t: int) -> None:
        o = org.organizational(sim.x, sim.box, reference)
        series.append({"t": t, "phase": phase, "largest_share": org.physical(sim.x, sim.box)["largest_share"], "overlap": o["best_overlap"], "bond_retention": bond_retention(sim.x, sim.box, pairs0), "shape_without_membership": shape_without_membership(sim.x, sim.box, reference)})
    t = 0
    for _ in range(steps // se):
        sim.step(se, **over)
        t += se
        sample("intervention", t)
    trans_after_intervention = org.transmission(sim, reference)
    t_end_intervention = t
    for _ in range(P.PROTOCOL["recovery_steps"] // se):
        sim.step(se)
        t += se
        sample("recovery", t)
    trans_after_recovery = org.transmission(sim, reference)
    return {"kind": kind or "control", "level": level, "series": series, "t_end_intervention": t_end_intervention, "transmission_after_intervention": trans_after_intervention, "transmission_after_recovery": trans_after_recovery}


def run_world(seed: int) -> dict[str, Any]:
    formed, _ = P.form(seed)
    reference = org.largest_group(formed.x, formed.box)
    pairs0 = reference_pairs(formed.x, formed.box, reference)
    return {"seed": seed, "reference_size": int(len(reference)), "reference_pairs": len(pairs0), "branches": [run_branch(formed, reference, pairs0, k, v, seed) for k, v in BRANCHES]}


def _first_below(series: list[dict[str, Any]], key: str, threshold: float) -> int | None:
    for s in series:
        if s[key] < threshold:
            return int(s["t"])
    return None


def read_branch(b: dict[str, Any], control_transmission: float | None) -> dict[str, Any]:
    """The persistence criteria of one branch, each on its own convention."""
    s, c = b["series"], CONVENTIONS
    end = s[-1]
    t_int = b["t_end_intervention"]
    repair = None
    if any(x["largest_share"] < c["cohesion_share"] for x in s if x["phase"] == "intervention"):
        repair = next((int(x["t"] - t_int) for x in s if x["phase"] == "recovery" and x["largest_share"] >= c["cohesion_share"]), None)
        repair_status = "repaired" if repair is not None else "not_repaired_within_recovery"
    else:
        repair, repair_status = 0, "never_lost_cohesion"
    ratio = b["transmission_after_recovery"].get("ratio")
    functional = None if ratio is None or not control_transmission else bool(ratio >= c["transmission_fraction_of_control"] * control_transmission)
    return {
        "kind": b["kind"], "level": b["level"],
        "persists": {
            "physical_cohesion_at_end": bool(end["largest_share"] >= c["cohesion_share"]),
            "membership_at_end": bool(end["overlap"] >= c["membership_overlap"]),
            "local_configuration_at_end": bool(end["bond_retention"] >= c["bond_retention"]),
            "functional_dependency_at_end": functional,
            "cohesion_never_lost_during_run": bool(all(x["largest_share"] >= c["cohesion_share"] for x in s)),
        },
        "values_at_end": {"largest_share": end["largest_share"], "overlap": end["overlap"], "bond_retention": end["bond_retention"], "transmission_ratio": ratio},
        "repair": {"status": repair_status, "steps_after_end_of_intervention": repair},
        "survival_time_steps": {"cohesion_lost_at": _first_below(s, "largest_share", c["cohesion_share"]), "membership_below_convention_at": _first_below(s, "overlap", c["membership_overlap"]), "bonds_below_convention_at": _first_below(s, "bond_retention", c["bond_retention"])},
        "shape_without_membership_at_end": bool(end["shape_without_membership"]),
    }


def read_world(w: dict[str, Any]) -> list[dict[str, Any]]:
    ctl = next(b for b in w["branches"] if b["kind"] == "control")
    ct = ctl["transmission_after_recovery"].get("ratio")
    return [{**read_branch(b, ct), "seed": w["seed"]} for b in w["branches"]]


def disagreements(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts of (world, branch) cells in which two persistence criteria give different answers; and the cells where the finite-run summary 'cohesion never lost' disagrees with membership."""
    names = ["physical_cohesion_at_end", "membership_at_end", "local_configuration_at_end", "functional_dependency_at_end", "cohesion_never_lost_during_run"]
    out: dict[str, Any] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            rows = [c for c in cells if c["persists"][a] is not None and c["persists"][b] is not None]
            out[f"{a} vs {b}"] = {"cells": len(rows), "disagree": sum(c["persists"][a] != c["persists"][b] for c in rows), "only_first": sum(c["persists"][a] and not c["persists"][b] for c in rows), "only_second": sum(c["persists"][b] and not c["persists"][a] for c in rows)}
    return out
