"""The frozen protocol of the SBS experiments and the runs that follow it (SBS-01 formation, SBS-02 metastability, SBS-03 dissolution, SBS-04 reconfiguration).

The protocol is a plain dictionary hashed into every record (``PROTOCOL_DIGEST``). It was written in this file before the first run of the experiments below, and the thresholds were not changed after seeing results; that is a freeze inside the code, not an external registration, and the records say so. Every threshold is a convention of this synthetic model.

A WORLD is one initial gas (``seed``). It is formed once; every intervention is a BRANCH of the formed state that shares the noise of the control branch (common random numbers), so a branch differs from its control only by the intervention."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from . import organisation as org
from .engine import Config, Sim

PROTOCOL: dict[str, Any] = {
    "model": {"n": 60, "density": 0.25, "kT": 0.3, "eps_formation": 1.5, "dt": 0.002},
    "gas_equilibration": {"steps": 2000, "eps": 0.0, "kT": 1.0},
    "formation_steps": 6000,
    "hold_steps": 1000,
    "interventions": {
        "decoupling": {"variable": "eps", "levels": [1.0, 0.6, 0.3, 0.0], "duration_steps": 1500},
        "heating": {"variable": "kT", "levels": [0.5, 0.8, 1.2, 2.0], "duration_steps": 1500},
    },
    "recovery_steps": 3000,
    "sample_every": 250,
    "outcome_thresholds": {"persistence": 0.8, "partial": 0.5, "no_reconstitution_share": 0.07},
    "observation": {"sigma_fine": 0.05, "sigma_coarse": 0.3, "unresolved_if_ari_below": 0.5},
    "metastability": {"eps_up": [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8], "hold_steps": 1500, "measure_last_steps": 500},
    "tracking": {"r_bond": org.R_BOND, "min_group": org.MIN_GROUP, "probe_steps": org.TRANSMIT_WINDOW, "probe_pull": org.PULL},
}
PROTOCOL_DIGEST = hashlib.sha256(json.dumps(PROTOCOL, sort_keys=True).encode()).hexdigest()


def _cfg() -> Config:
    m = PROTOCOL["model"]
    return Config(n=m["n"], density=m["density"], kT=m["kT"], eps=m["eps_formation"], dt=m["dt"])


def form(seed: int) -> tuple[Sim, dict[str, Any]]:
    """Gas, then formation under the formation coupling, with a control that is never coupled (same noise). Returns the formed simulation and the formation record (SBS-01)."""
    cfg = _cfg()
    sim = Sim(cfg, seed)
    g = PROTOCOL["gas_equilibration"]
    sim.step(g["steps"], eps=g["eps"], kT=g["kT"])
    control = sim.clone(seed + 777)
    coupled = sim.clone(seed + 777)
    rows = []
    n_samples = PROTOCOL["formation_steps"] // PROTOCOL["sample_every"]
    for k in range(n_samples + 1):
        rows.append({"t_steps": k * PROTOCOL["sample_every"], "coupled": org.physical(coupled.x, coupled.box), "uncoupled_control": org.physical(control.x, control.box)})
        if k < n_samples:
            coupled.step(PROTOCOL["sample_every"])
            control.step(PROTOCOL["sample_every"], eps=0.0)
    coupled.step(PROTOCOL["hold_steps"])
    return coupled, {"series": rows, "end_coupled": org.physical(coupled.x, coupled.box)}


def classify(end: dict[str, Any], org_end: dict[str, Any], n: int, ari: float | None) -> str:
    """The outcome of a reconfiguration, from the records of the END of the recovery. UNRESOLVED when the observed partition does not agree with the true one (the observation cannot support an organizational statement)."""
    th = PROTOCOL["outcome_thresholds"]
    if ari is not None and ari < PROTOCOL["observation"]["unresolved_if_ari_below"]:
        return "UNRESOLVED_OBSERVATION"
    if end["groups_tracked"] == 0 or end["largest_share"] < th["no_reconstitution_share"] * 1.0 and end["bonds"] < 3:
        return "NO_RECONSTITUTION"
    ov = org_end["best_overlap"]
    if ov >= th["persistence"]:
        return "PERSISTENCE"
    if ov >= th["partial"]:
        return "PARTIAL_RECOVERY"
    if end["largest_share"] >= 0.5:
        return "DIFFERENT_ORGANIZATION"
    return "MULTIPLE_ORGANIZATIONS" if end["groups_tracked"] >= 2 else "NO_RECONSTITUTION"


def run_branch(formed: Sim, reference: np.ndarray, kind: str | None, level: float | None, seed: int, keep_frames: bool = False) -> dict[str, Any]:
    """One branch from the formed state: the intervention (or none) for its duration, then recovery under the formation conditions. Records at the end of the intervention (dissolution) and at the end of the recovery (reconfiguration); the probes and observations use their own noise, so they do not alter the branch."""
    sim = formed.clone(seed + 31)
    spec = PROTOCOL["interventions"].get(kind) if kind else None
    steps = spec["duration_steps"] if spec else PROTOCOL["interventions"]["decoupling"]["duration_steps"]
    se = PROTOCOL["sample_every"]
    over: dict[str, Any] = {} if not spec else {spec["variable"]: level}
    frames, transitions, prev_cohesive = [], 0, True
    def sample(phase: str) -> None:
        nonlocal transitions, prev_cohesive
        p = org.physical(sim.x, sim.box)
        cohesive = p["largest_share"] >= 0.5
        if phase == "recovery" and cohesive != prev_cohesive:
            transitions += 1
        prev_cohesive = cohesive
        if keep_frames:
            frames.append({"t_steps": sim.t / sim.cfg.dt, "phase": phase, "x": np.round(sim.x, 3).tolist()})
    for _ in range(steps // se):
        sim.step(se, **over)
        sample("intervention")
    at_end_of_intervention = sim.snapshot()
    d_phys = org.physical(sim.x, sim.box)
    d_org = org.organizational(sim.x, sim.box, reference)
    d_fun = org.transmission(sim, reference)
    obs_rng = np.random.default_rng(seed + 5)
    obs_frame = {name: org.observe(sim.x, sim.box, s, obs_rng) for name, s in (("fine", PROTOCOL["observation"]["sigma_fine"]), ("coarse", PROTOCOL["observation"]["sigma_coarse"]))}
    for _ in range(PROTOCOL["recovery_steps"] // se):
        sim.step(se)
        sample("recovery")
    r_phys = org.physical(sim.x, sim.box)
    r_org = org.organizational(sim.x, sim.box, reference)
    true_part = org.partition(sim.x, sim.box)
    final_obs = {}
    for name, sg in (("fine", PROTOCOL["observation"]["sigma_fine"]), ("coarse", PROTOCOL["observation"]["sigma_coarse"])):
        fr = org.observe(sim.x, sim.box, sg, obs_rng)
        ari = org.adjusted_rand(true_part, org.partition(fr, sim.box))
        final_obs[name] = {"ari_vs_true_partition": ari, "outcome_as_read_by_observer": classify(org.physical(fr, sim.box), org.organizational(fr, sim.box, reference), sim.cfg.n, None)}
    outcome_true = classify(r_phys, r_org, sim.cfg.n, None)
    rec: dict[str, Any] = {
        "kind": kind or "control",
        "level": level,
        "dissolution": {"physical": d_phys, "organizational": d_org, "functional_transmission": d_fun, "attributional": "decided by the model comparison (comparison.py)", "agentic": "NOT_APPLICABLE (the substrate has no agent)", "observational": "read from the observed frames of the comparison and from reconfiguration.final_observation"},
        "reconfiguration": {"physical": r_phys, "organizational": r_org, "outcome": outcome_true, "transitions_of_cohesion": transitions, "final_observation": final_obs},
        "_state_at_end_of_intervention": at_end_of_intervention,
        "_observed_at_end_of_intervention": obs_frame,
        "_final_largest_group": org.largest_group(sim.x, sim.box),
    }
    if keep_frames:
        rec["frames"] = frames
    return rec


def run_world(seed: int, keep_frames: bool = False) -> dict[str, Any]:
    """Formation, then the control and the eight interventions."""
    formed, formation = form(seed)
    reference = org.largest_group(formed.x, formed.box)
    branches = [run_branch(formed, reference, None, None, seed, keep_frames)]
    for kind, spec in PROTOCOL["interventions"].items():
        for level in spec["levels"]:
            branches.append(run_branch(formed, reference, kind, level, seed, keep_frames))
    return {"seed": seed, "formation": formation, "reference_group_size": int(len(reference)), "branches": branches, "protocol_digest": PROTOCOL_DIGEST}


def run_metastability(seed: int) -> dict[str, Any]:
    """SBS-02. Sweep the coupling up and then down at fixed kT, each level held; the largest-group share at the end of each hold is the order parameter. The indicator appropriate to this model is HYSTERESIS: the share at the same coupling differs between the up and the down sweep. Nothing here is a claim about Simondon's metastability."""
    m = PROTOCOL["metastability"]
    sim = Sim(_cfg(), seed)
    sim.step(PROTOCOL["gas_equilibration"]["steps"], eps=0.0, kT=PROTOCOL["gas_equilibration"]["kT"])
    def level(eps: float) -> float:
        sim.step(m["hold_steps"] - m["measure_last_steps"], eps=eps)
        vals = []
        for _ in range(m["measure_last_steps"] // 100):
            sim.step(100, eps=eps)
            vals.append(org.physical(sim.x, sim.box)["largest_share"])
        return float(np.mean(vals))
    up = [level(e) for e in m["eps_up"]]
    down = [level(e) for e in reversed(m["eps_up"])][::-1]  # aligned with eps_up
    return {"seed": seed, "eps": m["eps_up"], "largest_share_up": up, "largest_share_down": down, "hysteresis_area": float(np.trapezoid(np.array(down) - np.array(up), m["eps_up"]))}
