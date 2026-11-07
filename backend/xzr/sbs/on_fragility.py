"""ON-03 on the SBS substrate: does an identified improvement move a vulnerability or a cost elsewhere? NEW condition; not an ON Lab reproduction.

The 'design' is the formation coupling ``eps`` of the substrate (the well depth of the attraction; the dynamics are otherwise the SBS protocol). Four designs: DESIGNS. The comparison is always against the baseline design 1.5 (the SBS default), world by world (the same initial gas).

Fixed BEFORE the first run (in this file; not changed after seeing results):

1. The IMPROVEMENT under test: membership persistence after the harsh-heating perturbation (heating kT 1.2 for 1500 steps, then recovery 3000): the best Jaccard overlap of the reference group with any current group. It is 'established' for a design when the paired 95% interval of its difference from the baseline lies above 0.05.
2. The measures, kept apart (none is combined into a score):
   performance         membership overlap after heating 1.2 (higher is better)
   repair              after complete decoupling (eps 0 for 1500 steps) and 3000 steps of recovery under the design's own coupling: whether a SINGLE dominant group is present (largest share >= 0.7), and the steps until the largest share first reaches 0.5 (lower is better)
   load failure        fraction of the reference group still in one group after the leading fifth is pulled for 400 steps, against the same noise without the pull (higher is better)
   stored cohesive energy  mean pair-attraction energy per particle at the end of formation (no direction: it is recorded, not ranked)
   NOT APPLICABLE: communication, maintenance (no maintenance process), resource dependence, dependence on external systems, latency of an external signal. Not computed.
3. The proposed TRANSFER MECHANISM (stated here before the data): stronger coupling traps a poorly merged arrangement (kinetic arrest), so repair gets worse as robustness improves. Evidence is demanded in two separate forms and an association between the outcomes is NOT accepted as evidence: (a) mobility: mean squared displacement of the particles in the largest group over 500 steps at the design's own coupling is lower than at the baseline (paired 95% interval above zero for the difference baseline minus design); (b) an intervention on the mechanism: of the end-of-recovery states that are NOT a single dominant group, an anneal (kT 0.5 for 1000 steps, then 500 at kT 0.3) merges more of them into a single dominant group than the same-noise no-anneal control does (a count over worlds; the anneal is applied only to worlds where repair failed).
4. Verdict per design against the baseline (the first matching line):
   NOT_AN_IMPROVEMENT          the improvement is not established
   TRANSFER_SUPPORTED          improvement established AND repair worse (the single-group share lower, or the repair time longer, with a paired 95% interval excluding zero) AND both forms of mechanism evidence present
   WORSE_REPAIR_MECHANISM_NOT_SHOWN   improvement established AND repair worse as above, but mechanism evidence is missing: an association only; Fragility Transfer is NOT established
   IMPROVEMENT_WITHOUT_DETECTED_TRANSFER   improvement established and no worsening of repair or load failure established
   (load failure worse with improvement established is reported in the record as a separate flag and, in the same way, needs its own mechanism evidence; it is not scored here)
5. PARETO: designs are compared on (performance, single-group share after decoupling, load retention) by mean; a design is dominated only if another is at least as good on all three and better on one. Incomparable designs are all retained and listed. The mean comparison ignores the uncertainty, and the record says so."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import organisation as org
from . import protocol as P
from .engine import Config, Sim
from .lab_stats import paired_t

DESIGNS = [1.0, 1.5, 2.0, 2.5]
BASELINE = 1.5
IMPROVEMENT_MARGIN = 0.05
SINGLE_GROUP_SHARE = 0.7
HEAT, DECOUPLE = 1.2, 0.0


def _cfg(eps: float) -> Config:
    m = P.PROTOCOL["model"]
    return Config(n=m["n"], density=m["density"], kT=m["kT"], eps=eps, dt=m["dt"])


def form_design(seed: int, eps: float) -> Sim:
    """The SBS formation (gas, then coupling), but at the design's coupling."""
    sim = Sim(_cfg(eps), seed)
    g = P.PROTOCOL["gas_equilibration"]
    sim.step(g["steps"], eps=0.0, kT=g["kT"])
    sim.step(P.PROTOCOL["formation_steps"] + P.PROTOCOL["hold_steps"])
    return sim


def cohesive_energy(sim: Sim) -> float:
    """Mean pair-attraction energy per particle, from the tail term -eps cos^2(arg) of the substrate."""
    from scipy.spatial import cKDTree
    from .engine import RM, WC, R_CUT
    pairs = cKDTree(sim.x, boxsize=sim.box).query_pairs(R_CUT, output_type="ndarray")
    if pairs.size == 0:
        return 0.0
    d = sim.x[pairs[:, 0]] - sim.x[pairs[:, 1]]
    d -= sim.box * np.round(d / sim.box)
    r = np.sqrt((d**2).sum(-1))
    tail = r >= RM
    u = np.where(tail, -sim.cfg.eps * np.cos(np.pi * (r - RM) / (2.0 * WC)) ** 2, -sim.cfg.eps)  # inside the core minimum the well depth is taken as the full depth (an approximation of the energy scale, not of the force)
    return float(u.sum() / sim.cfg.n)


def mobility(sim: Sim, group: np.ndarray, steps: int = 500) -> float:
    c = sim.clone(int(sim.noise.integers(1 << 31)))
    u0 = c.unwrapped[group].copy()
    c.step(steps)
    return float(((c.unwrapped[group] - u0) ** 2).sum(-1).mean())


def run_design_world(seed: int, eps: float) -> dict[str, Any]:
    formed = form_design(seed, eps)
    ref = org.largest_group(formed.x, formed.box)
    out: dict[str, Any] = {"seed": seed, "eps": eps, "reference_size": int(len(ref)), "energy_per_particle": cohesive_energy(formed), "formation_largest_share": org.physical(formed.x, formed.box)["largest_share"]}
    # performance: heating then recovery
    s = formed.clone(seed + 31)
    s.step(P.PROTOCOL["interventions"]["heating"]["duration_steps"], kT=HEAT)
    s.step(P.PROTOCOL["recovery_steps"])
    out["performance_overlap"] = org.organizational(s.x, s.box, ref)["best_overlap"]
    # repair: complete decoupling then recovery
    r = formed.clone(seed + 31)
    r.step(P.PROTOCOL["interventions"]["decoupling"]["duration_steps"], eps=DECOUPLE)
    t_first = None
    for k in range(P.PROTOCOL["recovery_steps"] // P.PROTOCOL["sample_every"]):
        r.step(P.PROTOCOL["sample_every"])
        if t_first is None and org.physical(r.x, r.box)["largest_share"] >= 0.5:
            t_first = (k + 1) * P.PROTOCOL["sample_every"]
    share = org.physical(r.x, r.box)["largest_share"]
    out["repair"] = {"largest_share_after_recovery": share, "single_group": bool(share >= SINGLE_GROUP_SHARE), "steps_to_half": t_first}
    # mechanism (a): mobility of the largest group of the formed state
    out["mobility_msd_500"] = mobility(formed, ref)
    # mechanism (b): anneal vs control, only where repair failed
    if share < SINGLE_GROUP_SHARE:
        seed2 = int(r.noise.integers(1 << 31))
        a, c = r.clone(seed2), r.clone(seed2)
        a.step(1000, kT=0.5)
        a.step(500)
        c.step(1500)
        out["anneal"] = {"single_group_after_anneal": bool(org.physical(a.x, a.box)["largest_share"] >= SINGLE_GROUP_SHARE), "single_group_after_control": bool(org.physical(c.x, c.box)["largest_share"] >= SINGLE_GROUP_SHARE)}
    # load failure: pull vs no pull on the formed reference
    if len(ref) >= 5:
        order = ref[np.argsort(formed.unwrapped[ref, 0])]
        k = max(1, len(order) // 5)
        pull = np.zeros_like(formed.x)
        pull[order[-k:], 0] = org.PULL
        seed3 = seed + 4242
        p = formed.clone(seed3)
        p.step(org.TRANSMIT_WINDOW, pull=pull)
        lab = org.partition(p.x, p.box)
        labs = lab[ref]
        out["load_retention"] = float(np.bincount(labs[labs >= 0]).max() / len(ref)) if (labs >= 0).any() else 0.0
    else:
        out["load_retention"] = None
    return out


def _paired(rows: dict[float, dict[int, dict]], eps: float, key) -> dict[str, Any]:
    seeds = sorted(set(rows[eps]) & set(rows[BASELINE]))
    pairs = [(key(rows[eps][s]), key(rows[BASELINE][s])) for s in seeds]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    return paired_t([a - b for a, b in pairs]) if len(pairs) > 1 else {"n": len(pairs), "mean": None, "ci95": None, "p": None}


def verdicts(rows: dict[float, dict[int, dict]]) -> dict[str, Any]:
    res: dict[str, Any] = {}
    for eps in DESIGNS:
        if eps == BASELINE:
            continue
        perf = _paired(rows, eps, lambda r: r["performance_overlap"])
        single = _paired(rows, eps, lambda r: float(r["repair"]["single_group"]))
        # time to half: unrepaired worlds are right-censored at the length of the recovery window, a stated convention
        T = P.PROTOCOL["recovery_steps"]
        t_half = _paired(rows, eps, lambda r: float(r["repair"]["steps_to_half"] if r["repair"]["steps_to_half"] is not None else T))
        load = _paired(rows, eps, lambda r: r["load_retention"])
        mob = {"baseline_minus_design": paired_t([rows[BASELINE][s]["mobility_msd_500"] - rows[eps][s]["mobility_msd_500"] for s in sorted(set(rows[eps]) & set(rows[BASELINE]))])}
        an = [r["anneal"] for r in rows[eps].values() if "anneal" in r]
        anneal = {"worlds_with_failed_repair": len(an), "merged_after_anneal": sum(a["single_group_after_anneal"] for a in an), "merged_after_control": sum(a["single_group_after_control"] for a in an)}
        improved = perf["ci95"] is not None and perf["ci95"][0] > IMPROVEMENT_MARGIN
        worse_repair = (single["ci95"] is not None and single["ci95"][1] < 0) or (t_half["ci95"] is not None and t_half["ci95"][0] > 0)
        mech_a = mob["baseline_minus_design"]["ci95"][0] > 0 if mob["baseline_minus_design"]["n"] > 1 else False
        mech_b = anneal["worlds_with_failed_repair"] > 0 and anneal["merged_after_anneal"] > anneal["merged_after_control"]
        if not improved:
            v = "NOT_AN_IMPROVEMENT"
        elif worse_repair and mech_a and mech_b:
            v = "TRANSFER_SUPPORTED"
        elif worse_repair:
            v = "WORSE_REPAIR_MECHANISM_NOT_SHOWN"
        else:
            v = "IMPROVEMENT_WITHOUT_DETECTED_TRANSFER"
        res[str(eps)] = {"verdict": v, "performance_diff": perf, "single_group_share_diff": single, "steps_to_half_diff_censored_at_recovery_length": t_half, "load_retention_diff": load, "load_retention_worse_flag": bool(load["ci95"] is not None and load["ci95"][1] < 0), "mechanism_mobility_a": mob, "mechanism_anneal_b": anneal, "mechanism_a_present": bool(mech_a), "mechanism_b_present": bool(mech_b)}
    return res


def pareto(rows: dict[float, dict[int, dict]]) -> dict[str, Any]:
    means = {}
    for eps in DESIGNS:
        rs = list(rows[eps].values())
        means[eps] = (float(np.mean([r["performance_overlap"] for r in rs])), float(np.mean([r["repair"]["single_group"] for r in rs])), float(np.mean([r["load_retention"] for r in rs if r["load_retention"] is not None])))
    dominated = {e: [o for o in DESIGNS if o != e and all(means[o][i] >= means[e][i] for i in range(3)) and any(means[o][i] > means[e][i] for i in range(3))] for e in DESIGNS}
    return {"axes": ["performance_overlap", "single_group_share_after_decoupling", "load_retention"], "means": {str(e): list(v) for e, v in means.items()}, "dominated_by": {str(e): d for e, d in dominated.items()}, "retained_non_dominated": [e for e in DESIGNS if not dominated[e]], "note": "dominance on means; the uncertainty is not part of this comparison"}
