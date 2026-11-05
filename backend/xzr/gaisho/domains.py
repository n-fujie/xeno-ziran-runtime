"""The other research domains of the laboratory. Each has its own comparison conditions and its OWN completion judgement (``STATUS``): a successful knowledge domain completes none of the others.

002 Bias, 003 Freedom: small synthetic models whose RULES are declared; what they exhibit is what those rules imply, so they test the instrument (does the laboratory tell the declared non-identities apart by intervention?) and
say nothing about bias or freedom as such. 005 Credit reuses the existing TRUTH-ERROR institution engine (no second institution model); the institution's scoring operation is NOT an individual's Gaisho. 004 Body needs the
existing XenoSNN (the snnTorch server of the P/A repository), which is not part of this runtime: it is specified and NOT executed, and no substitute computation is made.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from . import bodylink
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
    max_seeds = 10  # about 1.8 s of the institution engine per seed and condition: 10 seeds is about 18 s per request

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
                if "labels" not in r["process"] or "complement" not in r["process"]:  # this domain reads outputs that exist only from TRUTH-ERROR phase 4 (complement) and phase 5 (labels, commit 1af5700)
                    raise RuntimeError("005-credit needs the TRUTH-ERROR engine outputs process.complement (phase 4) and process.labels (phase 5, commit 1af5700); this engine does not provide them")
                raw[j, i] = r["summary"]["access"]  # the share of subjects with access in the late periods
                if i == 2:
                    sc.append((float(beta), r["process"]["complement"]["state_change_unfav"], r["process"]["labels"]["metrics"]["target_change_abs"]))
        snaps = {"end": {"surface": record_surface(self, raw, obs, rg["recording"]), "weights": None, "stability": float(raw.mean())}}
        slope = float(np.polyfit([s[0] for s in sc], [s[2] for s in sc], 1)[0])
        step = float((self.x_values[1] - self.x_values[0]) * obs.scale)
        rel = _simple_relations(self, snaps, obs, step, {"state_transformation": (slope, {"axes": ("y",), "min_window": 20}), "unfav_state_change": (float(sc[-1][1]), {"axes": ("y",), "min_window": 20})})
        return {"accuracy": float(raw.mean()), "snapshots": snaps, "relations": rel, "operation_digest": digest({"cond": cond, "seed": seed, "raw": raw.tolist()})}


# ------------------------------------------------------------------------------------------------ 004 Body (the XB-TRO planar body, through the optional link of bodylink.py)
class BodyDomain(Domain):
    """A planar N-link body with delayed, noisy sensing, operation lines and feedback (XB-TRO), under two interventions of XB-TRO's own registry. R37 X, fourth family: whether sensing, feedback and the world's disturbance determine
    different continuation classes of a bodily configuration, without inferring a thinking subject from a controller. The outcome is a continuation class of the body (it falls or it does not), per replication seed; it is a
    prereflective bodily operation (R37's P register) and nothing in it is an episode, a spike or a Gaisho."""

    id = "004-body"
    title = "BODY — SENSORIMOTOR CONTINUATION OF A PLANAR BODY UNDER INTERVENTION (XB-TRO)"
    x_name, y_name = "sensory feedback delay added, s (do)", "external disturbance, push force N (do)"
    outcome_meaning = "the continuation class of the body: 1 if the body falls within the horizon, 0 if it stays up, for one replication seed (one body per cell and seed); the cell value is the share of seeds that fall, with the delay and the push set by XB-TRO's interventions"
    x_values = np.linspace(0.0, 0.2, 5)
    y_values = np.linspace(0.0, 200.0, 5)
    snapshots = ("end",)
    relation_names = ("effect_x", "effect_y", "baseline_fall")
    # R37 X (fourth family): sensor, memory and resource conditions of the bodily configuration, besides its morphology (the two presets). 'edits' are applied in order to the configuration before the two axes are set.
    conditions = {
        "human-like planar body": {"preset": "human-like-planar", "edits": []},
        "machine-like planar body": {"preset": "machine-like-planar", "edits": []},
        "human-like planar body, visual feedback blocked (sensor)": {"preset": "human-like-planar", "edits": [("intervention", "visual_block", 0.0)]},
        "human-like planar body, slow gain adaptation off (memory)": {"preset": "human-like-planar", "edits": [("set", ("adaptation", "enabled"), False)]},
        "human-like planar body, resource-constrained (resources)": {"preset": "human-like-planar", "edits": [("intervention", "resource_constraint", 0.4)]},
    }
    default_conditions = ("human-like planar body", "machine-like planar body")  # a run without a named condition runs the two morphologies (the others are chosen by name: about 20 s each for 6 seeds)
    seed_count = 6
    max_seeds = 8  # about 0.9 s per cell for a batch of 8 seeds: 25 cells and one condition are about 25 s

    def __init__(self) -> None:
        link = bodylink.load()
        if link is None:
            raise RuntimeError("the XB-TRO body is not linked (set XZR_XBTRO_PATH to the directory of the xbtro package)")
        self.link = link
        self._cache: dict[tuple, np.ndarray] = {}

    def provenance(self) -> dict:
        return {"body": "XB-TRO", "model_version": self.link.model_version, "source_sha256": self.link.source_sha256, "files": self.link.n_files}

    def base_config(self, cond: str) -> dict:
        """The body's configuration for a condition, before the two axes are set."""
        import copy

        spec = self.conditions[cond]
        cfg0 = self.link.config.build(spec["preset"])
        for kind, what, value in spec["edits"]:
            if kind == "intervention":
                cfg0 = self.link.config.apply_intervention(cfg0, what, value)
            else:  # a plain switch of the body's own configuration (here: the slow adaptation), applied to a copy
                cfg0 = copy.deepcopy(cfg0)
                cfg0[what[0]][what[1]] = value
        return cfg0

    def run_cell(self, cond: str, delay: float, push: float, seeds: list[int], cfg0: dict | None = None):
        """One body batch at a cell of the grid (the delay and the disturbance set by XB-TRO's interventions)."""
        cfg = self.base_config(cond) if cfg0 is None else cfg0
        if delay > 0:
            cfg = self.link.config.apply_intervention(cfg, "sensory_delay", float(delay))
        cfg = self.link.config.apply_intervention(cfg, "perturbation", float(push))
        return self.link.engine.simulate(cfg, seeds=list(seeds))

    def prepare(self, cond: str, seeds: tuple[int, ...], obs: Observation) -> None:
        key = (cond, tuple(seeds))
        if key in self._cache:
            return
        cfg0 = self.base_config(cond)
        fell = np.zeros((len(self.y_values), len(self.x_values), len(seeds)))
        for j, push in enumerate(self.y_values):
            for i, delay in enumerate(self.x_values):
                run = self.run_cell(cond, float(delay), float(push), list(seeds), cfg0)
                fell[j, i, :] = np.asarray(run.fell, dtype=float)
        self._cache[key] = fell

    def simulate(self, cond: str, seed: int, obs: Observation) -> dict:
        key = next((k for k in self._cache if k[0] == cond and seed in k[1]), None)
        if key is None:
            raise RuntimeError("the body batch of this request was not prepared")
        raw = self._cache[key][:, :, key[1].index(seed)]
        rg = _streams(seed, ("recording",))
        obs_one = dataclasses.replace(obs, temporal_window=1)  # one body per cell and seed: the 'trials' of a cell are the seeds, not a window
        obs_rel = dataclasses.replace(obs, temporal_window=max(20, obs.temporal_window))  # the window axis is not applicable to a trajectory; it must not gate the relations
        snaps = {"end": {"surface": record_surface(self, raw, obs_one, rg["recording"]), "weights": None, "stability": float(raw.mean())}}
        step = float((self.x_values[1] - self.x_values[0]) * obs.scale)
        rel = _simple_relations(self, snaps, obs_rel, step, {"baseline_fall": (float(raw[0, 0]), {"axes": (), "min_window": 1})})
        return {"accuracy": float(1.0 - raw.mean()), "snapshots": snaps, "relations": rel, "operation_digest": digest({"cond": cond, "seed": seed, "fell": raw.tolist(), "body": self.link.source_sha256})}


# ------------------------------------------------------------------------------------------------ the registry, with the completion judgement of each domain
STATUS = {
    "001-knowledge": {"executed": True, "completion": "INITIAL_EXPERIMENT_EXECUTED", "criteria": "the four comparison conditions run with interventions, relations and shapes generated from them, competing explanations compared, the attribution kept apart: executed for a synthetic judging agent; nothing about knowledge as such is shown"},
    "002-bias": {"executed": True, "completion": "INITIAL_CONDITIONS_EXECUTED", "criteria": "the four sources of bias and the intervention are compared by intervention on a declared synthetic rule set; adaptive and inappropriate bias are told apart by the matched environment; competing models, ablations and a body-derived condition beyond a calibration offset are NOT done"},
    "003-freedom": {"executed": True, "completion": "INITIAL_CONDITIONS_EXECUTED", "criteria": "the four conditions of the brief are separated by intervention on declared coupling rules (what they exhibit follows from the rules); an effective action space with real alternatives, competing explanations and ablations are NOT done"},
    "004-body": {"executed": False, "completion": "NOT_EXECUTED", "criteria": "needs the existing XenoSNN (the snnTorch server of the P/A repository) connected to this runtime: sensor input and time, spike firing and time, internal state, weights, plasticity, memory, bodily output and the return from the environment as separate records; no substitute computation is made"},
    "005-credit": {"executed": True, "completion": "INITIAL_CONDITIONS_EXECUTED", "criteria": "the institution's scoring, classification, access constraint and a correction are intervened on through the existing TRUTH-ERROR engine; the institution's operation is not an individual's Gaisho and an individual's orientation to their own evaluation is NOT modelled"},
}


BODY_STATUS = {"executed": True, "completion": "INITIAL_CONDITIONS_EXECUTED", "criteria": "B1 only: a real planar body (XB-TRO, through the optional link) under two interventions, the continuation class (falls or not) as the outcome, two body configurations. Morphology, memory and resource axes are not crossed; no spiking component exists (XenoSNN is not connected and cannot be closed-loop); the body is a prereflective operation (R37 P), not a thinker, and no attribution is made"}


def status_of(dom_id: str) -> dict:
    """The completion judgement of a domain; the body domain is executed only where the XB-TRO link is configured."""
    return BODY_STATUS if dom_id == "004-body" and bodylink.load() is not None else STATUS[dom_id]


def domain_registry() -> dict[str, Domain | None]:
    return {"001-knowledge": KnowledgeDomain(), "002-bias": BiasDomain(), "003-freedom": FreedomDomain(), "004-body": BodyDomain() if bodylink.load() is not None else None, "005-credit": CreditDomain()}
