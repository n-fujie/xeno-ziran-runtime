"""The other research domains of the laboratory. Each has its own comparison conditions and its OWN completion judgement (``STATUS``): a successful knowledge domain completes none of the others.

002 Bias, 003 Freedom: small synthetic models whose RULES are declared; what they exhibit is what those rules imply, so they test the instrument (does the laboratory tell the declared non-identities apart by intervention?) and
say nothing about bias or freedom as such. 005 Credit reuses the existing TRUTH-ERROR institution engine (no second institution model); the institution's scoring operation is NOT an individual's Gaisho. 004 Body needs the
existing XenoSNN (the snnTorch server of the P/A repository), which is not part of this runtime: it is specified and NOT executed, and no substitute computation is made.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .knowledge import KnowledgeDomain, sigmoid
from .lab import Domain, Observation, classify_unobserved, record_surface, surface_effects
from .model import digest


def _streams(seed: int, names: tuple[str, ...]) -> dict[str, np.random.Generator]:
    return dict(zip(names, (np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(len(names))), strict=True))


def _simple_relations(dom: Domain, snaps: dict, obs: Observation, step: float, extra: dict[str, tuple[float | None, dict]]) -> dict:
    rel: dict[str, dict] = {}
    end = snaps.get("end") or next(iter(snaps.values()), None)
    nx, ny = len(dom.x_values), len(dom.y_values)
    eff = {"effect_x": None, "effect_y": None}
    if end:
        hi_x, hi_y = max(i for i in range(nx) if i % max(1, obs.scale) == 0), max(j for j in range(ny) if j % max(1, obs.scale) == 0)
        eff = surface_effects(end["surface"], hi_x, 0, hi_y, 0)
    for name, key, axis in (("effect_x", "effect_x", "x"), ("effect_y", "effect_y", "y")):
        why = classify_unobserved(name, {"axes": (axis,), "separate_axes": True, "min_window": 20}, obs, True, None, step)
        rel[name] = {"status": why or "IDENTIFIED", "value": None if why else eff[key]}
    for name, (value, needs) in extra.items():
        why = classify_unobserved(name, needs, obs, True, None, step)
        rel[name] = {"status": why or "IDENTIFIED", "value": None if why else value}
    return rel


# ------------------------------------------------------------------------------------------------ 002 Bias
class BiasDomain(Domain):
    id = "002-bias"
    title = "BIAS — SELECTIVITY, HISTORY AND THE BODY"
    x_name, y_name = "base rate of the world (do)", "noise of the evidence (do)"
    outcome_meaning = "the accuracy of the agent's judgement in a world with the base rate and the evidence noise of the cell (set by intervention), over n trials"
    x_values = np.linspace(0.1, 0.9, 9)
    y_values = np.linspace(0.4, 1.6, 5)
    snapshots = ("before intervention", "end")
    relation_names = ("effect_x", "effect_y", "matched_advantage", "retention")
    conditions = {
        "no bias (evidence only)": {"kind": "plain"},
        "perception-derived selectivity (attends only to strong evidence)": {"kind": "selective", "tau": 0.7},
        "training-history prior (trained at base rate 0.8)": {"kind": "prior", "prior": 0.8},
        "sensor/body offset (calibration +0.6)": {"kind": "offset", "delta": 0.6},
        "history prior, then retraining at base rate 0.3": {"kind": "prior", "prior": 0.8, "retrain": 0.3},
    }

    def _accuracy(self, kind: dict, pi: float, sigma: float, n: int, rng: np.random.Generator, prior: float | None = None) -> float:
        w = np.where(rng.uniform(size=n) < pi, 1, -1)
        E = w + sigma * rng.normal(size=n)
        k = kind["kind"]
        pr = kind.get("prior") if prior is None else prior
        pr = 0.5 if pr is None else float(pr)
        if k == "plain":
            z = 2.5 * E
        elif k == "selective":
            z = np.where(np.abs(E) > kind["tau"], 2.5 * E, 0.0)
        elif k == "offset":
            z = 2.5 * (E + kind["delta"])
        else:
            z = 2.5 * E + float(np.log(pr / (1 - pr)))
        J = np.where(rng.uniform(size=n) < sigmoid(z), 1, -1)
        return float((w == J).mean())

    def simulate(self, cond: str, seed: int, obs: Observation) -> dict:
        kind = self.conditions[cond]
        rg = _streams(seed, ("surface", "recording", "main"))
        n = max(1, obs.temporal_window)
        kept = {nm for i, nm in enumerate(self.snapshots) if i % max(1, obs.speed) == 0}
        snaps = {}
        priors: dict[str, float | None] = {"before intervention": kind.get("prior"), "end": kind.get("prior")}
        if kind.get("retrain") is not None:
            priors["end"] = float(kind["retrain"] * 0.7 + float(kind["prior"]) * 0.3)  # retraining moves the prior part of the way (a declared rule), it does not erase it
        for nm in self.snapshots:
            raw = np.array([[self._accuracy(kind, float(pi), float(sg), n, rg["surface"], priors[nm]) for pi in self.x_values] for sg in self.y_values])
            if nm in kept:
                snaps[nm] = {"surface": record_surface(self, raw, obs, rg["recording"]), "weights": ({"prior": priors[nm]} if obs.memory and priors[nm] is not None else None), "stability": float(raw.mean())}
        mid = int(np.argmin(np.abs(self.y_values - 1.0)))
        p0, p1 = priors["before intervention"], priors["end"]
        end_raw = np.array([self._accuracy(kind, float(pi), 1.0, 10 * n, rg["main"], p1) for pi in self.x_values])
        matched = float(end_raw[7] - end_raw[1])  # base rate 0.8 against 0.2
        ret = None if p0 is None or p1 is None else float(p1 - 0.5) / max(1e-9, float(p0 - 0.5))
        step = float((self.x_values[1] - self.x_values[0]) * obs.scale)
        rel = _simple_relations(self, snaps, obs, step, {"matched_advantage": (matched, {"axes": (), "min_window": 20}), "retention": (ret, {"axes": (), "snapshots": True, "min_window": 20, "time_constant_snapshots": 2})})
        acc = float(end_raw[mid])
        return {"accuracy": acc, "snapshots": snaps, "relations": rel, "operation_digest": digest({"cond": cond, "seed": seed, "end": end_raw.tolist(), "priors": priors})}


# ------------------------------------------------------------------------------------------------ 003 Freedom
class FreedomDomain(Domain):
    id = "003-freedom"
    title = "FREEDOM — SELF-INTERPRETATION, EFFECTIVE POSSIBILITY, INSTITUTIONAL CLASSIFICATION, CONSTRAINT"
    x_name, y_name = "material/bodily constraint (do)", "self-interpretation as free (do)"
    outcome_meaning = "the reach (the share of n trials in which the action is effectively possible) given the constraint and the belief set by intervention, under the declared coupling rules of the condition"
    x_values = np.linspace(0.0, 1.0, 9)
    y_values = np.linspace(0.0, 1.0, 5)
    snapshots = ("end",)
    relation_names = ("effect_x", "effect_y", "label_to_belief", "label_to_reach")
    conditions = {
        "effective possibility only (reach is set by the constraint)": {"belief_effort": 0.0, "label_to_belief": 0.0},
        "self-interpretation drives effort (belief changes the reach where the constraint allows)": {"belief_effort": 0.8, "label_to_belief": 0.0},
        "institutional free-classification (the label is adopted as a belief)": {"belief_effort": 0.0, "label_to_belief": 0.9},
        "constraint also lowers the belief (embodied coupling)": {"belief_effort": 0.8, "label_to_belief": 0.0, "constraint_to_belief": 0.9},
        "institutional label adopted as a belief that drives effort": {"belief_effort": 0.8, "label_to_belief": 0.9},
    }

    def _reach(self, p: dict, kappa: float, belief: float, n: int, rng: np.random.Generator) -> float:
        eff_belief = belief * (1 - p.get("constraint_to_belief", 0.0) * kappa)
        prob = (1 - kappa) * (1 - p["belief_effort"] + p["belief_effort"] * eff_belief)
        return float(rng.binomial(n, min(1.0, max(0.0, prob))) / n)

    def simulate(self, cond: str, seed: int, obs: Observation) -> dict:
        p = self.conditions[cond]
        rg = _streams(seed, ("surface", "recording", "labels"))
        n = max(1, obs.temporal_window)
        raw = np.array([[self._reach(p, float(k), float(b), n, rg["surface"]) for k in self.x_values] for b in self.y_values])
        snaps = {"end": {"surface": record_surface(self, raw, obs, rg["recording"]), "weights": None, "stability": float(raw.mean())}}
        # do(label): the institution's label ('free' / 'unfree') is set by the institution, not by the agent; it acts on the belief through the declared coupling and on the reach only through that belief
        m = 10 * n
        kap = rg["labels"].uniform(size=m)
        belief = {lab: np.clip(0.5 + p["label_to_belief"] * (lab - 0.5), 0, 1) for lab in (1.0, 0.0)}
        l2b = float(belief[1.0] - belief[0.0])
        reach = {lab: float(np.mean([self._reach(p, float(k), float(belief[lab]), 1, rg["labels"]) for k in kap])) for lab in (1.0, 0.0)}
        step = float((self.x_values[1] - self.x_values[0]) * obs.scale)
        rel = _simple_relations(self, snaps, obs, step, {"label_to_belief": (l2b, {"axes": (), "min_window": 20}), "label_to_reach": (reach[1.0] - reach[0.0], {"axes": (), "min_window": 20})})
        return {"accuracy": float(raw.mean()), "snapshots": snaps, "relations": rel, "operation_digest": digest({"cond": cond, "seed": seed, "raw": raw.tolist()})}


# ------------------------------------------------------------------------------------------------ 005 Credit (the TRUTH-ERROR institution engine)
class CreditDomain(Domain):
    id = "005-credit"
    title = "CREDIT — INSTITUTIONAL SCORE OPERATION AND THE ACCESS IT SETS (SYNTHETIC)"
    x_name, y_name = "score threshold (do)", "feedback of resources to the state beta (do)"
    outcome_meaning = "the share of subjects with access in the late periods of one run of the existing TRUTH-ERROR institution engine with the threshold and the feedback of the cell (a run per cell and seed; the cell value is that share, not a share of trials)"
    x_values = np.linspace(-0.4, 0.4, 5)
    y_values = np.array([0.0, 0.03, 0.06, 0.09, 0.12])
    snapshots = ("end",)
    relation_names = ("effect_x", "effect_y", "state_transformation", "unfav_state_change")
    conditions = {
        "score computed, allocation inert (the score changes, the resources do not)": {"gain": 0.0, "loss": 0.0},
        "institutional classification with an access constraint": {},
        "access constraint with a resource floor (a hypothetical guarantee)": {"resource_floor": 0.3},
        "after a correction (audit, approval, release)": {"audit_every": 2, "request_delay": 1, "approval_delay": 2, "release_mode": "after_approval"},
    }
    N, PERIODS = 60, 24
    seed_count = 6  # a run of the institution engine per cell: fewer seeds by default (the unit of replication is still the seed)

    def _run(self, over: dict, seed: int, tau: float, beta: float):
        from ..truth_error.institution import Config, run

        return run(dataclasses.replace(Config(n=self.N, periods=self.PERIODS, lock_after=4, tau_a=tau, beta=beta), seed=seed, **over))

    def simulate(self, cond: str, seed: int, obs: Observation) -> dict:
        over = self.conditions[cond]
        rg = _streams(seed, ("recording",))
        raw = np.zeros((len(self.y_values), len(self.x_values)))
        sc = []
        for j, beta in enumerate(self.y_values):
            for i, tau in enumerate(self.x_values):
                r = self._run(over, seed, float(tau), float(beta))
                raw[j, i] = r["summary"]["access"]  # the share of subjects with access in the late periods
                if i == 2:
                    sc.append((float(beta), r["process"]["complement"]["state_change_unfav"], r["process"]["labels"]["metrics"]["target_change_abs"]))
        snaps = {"end": {"surface": record_surface(self, raw, obs, rg["recording"]), "weights": None, "stability": float(raw.mean())}}
        slope = float(np.polyfit([s[0] for s in sc], [s[2] for s in sc], 1)[0])
        step = float((self.x_values[1] - self.x_values[0]) * obs.scale)
        rel = _simple_relations(self, snaps, obs, step, {"state_transformation": (slope, {"axes": ("y",), "min_window": 20}), "unfav_state_change": (float(sc[-1][1]), {"axes": ("y",), "min_window": 20})})
        return {"accuracy": float(raw.mean()), "snapshots": snaps, "relations": rel, "operation_digest": digest({"cond": cond, "seed": seed, "raw": raw.tolist()})}


# ------------------------------------------------------------------------------------------------ the registry, with the completion judgement of each domain
STATUS = {
    "001-knowledge": {"executed": True, "completion": "INITIAL_EXPERIMENT_EXECUTED", "criteria": "the four comparison conditions run with interventions, relations and shapes generated from them, competing explanations compared, the attribution kept apart: executed for a synthetic judging agent; nothing about knowledge as such is shown"},
    "002-bias": {"executed": True, "completion": "INITIAL_CONDITIONS_EXECUTED", "criteria": "the four sources of bias and the intervention are compared by intervention on a declared synthetic rule set; adaptive and inappropriate bias are told apart by the matched environment; competing models, ablations and a body-derived condition beyond a calibration offset are NOT done"},
    "003-freedom": {"executed": True, "completion": "INITIAL_CONDITIONS_EXECUTED", "criteria": "the four conditions of the brief are separated by intervention on declared coupling rules (what they exhibit follows from the rules); an effective action space with real alternatives, competing explanations and ablations are NOT done"},
    "004-body": {"executed": False, "completion": "NOT_EXECUTED", "criteria": "needs the existing XenoSNN (the snnTorch server of the P/A repository) connected to this runtime: sensor input and time, spike firing and time, internal state, weights, plasticity, memory, bodily output and the return from the environment as separate records; no substitute computation is made"},
    "005-credit": {"executed": True, "completion": "INITIAL_CONDITIONS_EXECUTED", "criteria": "the institution's scoring, classification, access constraint and a correction are intervened on through the existing TRUTH-ERROR engine; the institution's operation is not an individual's Gaisho and an individual's orientation to their own evaluation is NOT modelled"},
}


def domain_registry() -> dict[str, Domain | None]:
    return {"001-knowledge": KnowledgeDomain(), "002-bias": BiasDomain(), "003-freedom": FreedomDomain(), "004-body": None, "005-credit": CreditDomain()}
