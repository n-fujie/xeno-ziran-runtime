"""How much the verdict "this success is not accidental" depends on WHICH perturbations are asked for (Dictionary entry 022: the class of nearby errors has to be specified, and the choice of the neighbourhood can manufacture either safety or fragility; dictionary.D2).

The laboratory's own criterion of non-accidental success (knowledge.py, claims N1) names one neighbourhood: do(E), do(S) and the cue decoupled from the state. Here the SAME six agents of the knowledge domain (the weights each seed ends with, at the full observation and the default environment) are put
into eight declared worlds, and the question is asked of each: does the agent's share of correct judgements stay within a stated tolerance of its share in the world it ran in? The worlds are written below as PROTOCOL BEFORE the run, with the
predictions made about the result; the record carries the digest of the protocol. (That is a protocol frozen in the code, not an external registration: the order of the commits is the only time stamp.)

What this can and cannot say. It tests one question (stability of the share correct under eight neighbourhoods), on a synthetic agent of three weights. It does not say what the right neighbourhood is, and no verdict of it is knowledge, or a Gaisho."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import MODEL_VERSION
from .knowledge import ENVIRONMENTS, KnowledgeDomain, sigmoid
from .lab import FULL, SEEDS, t975
from .model import digest

TOLERANCE = 0.10  # the largest drop of the share correct that still counts as stable
DRAWS = 4000  # judgements per agent, seed and world

HOME = "home: the world the agent ran in (prior 0.9, cue right with probability 0.9)"
WORLDS: dict[str, dict[str, float]] = {
    HOME: {"pi": 0.9, "sigma": 0.78, "q": 0.9, "weight_noise": 0.0},
    "cue decoupled (right with probability 0.5)": {"pi": 0.9, "sigma": 0.78, "q": 0.5, "weight_noise": 0.0},
    "cue reversed (right with probability 0.1)": {"pi": 0.9, "sigma": 0.78, "q": 0.1, "weight_noise": 0.0},
    "balanced world, cue decoupled (the laboratory's do(W))": {"pi": 0.5, "sigma": 0.78, "q": 0.5, "weight_noise": 0.0},
    "prior reversed (state +1 with probability 0.1)": {"pi": 0.1, "sigma": 0.78, "q": 0.9, "weight_noise": 0.0},
    "evidence twice as noisy (sigma 1.56)": {"pi": 0.9, "sigma": 1.56, "q": 0.9, "weight_noise": 0.0},
    "evidence nearly absent (sigma 5)": {"pi": 0.9, "sigma": 5.0, "q": 0.9, "weight_noise": 0.0},
    "the agent's weights jittered (sd 0.5 each judgement)": {"pi": 0.9, "sigma": 0.78, "q": 0.9, "weight_noise": 0.5},
}

PREDICTIONS = (
    "P1: the cue-driven agent keeps its share correct in the worlds that leave the cue coupled (prior reversed excepted) and loses it where the cue is decoupled or reversed.",
    "P2: the ground-responsive agent keeps its share correct where the cue is decoupled or reversed and loses it where the evidence is nearly absent.",
    "P3: the miscalibrated agent (right responsiveness, shifted threshold) is not told apart from the ground-responsive one by any world that changes the cue only; a change of the prior can tell them apart.",
    "P4: the set of agents called stable is not the same in every world, i.e. the verdict depends on the neighbourhood chosen (the worry of entry 022). If it were the same in all eight, this study would show no such dependence.",
)

PROTOCOL = {"model_version": MODEL_VERSION, "domain": "001-knowledge", "seeds": list(SEEDS), "tolerance": TOLERANCE, "draws": DRAWS, "worlds": WORLDS, "predictions": list(PREDICTIONS),
            "verdict": "STABLE if the upper end of the 95 % t-interval of the drop (share correct at home minus in the world, over the seeds) is at most the tolerance; NOT_STABLE if its lower end is above the tolerance; otherwise UNRESOLVED"}


def _share_correct(weights: dict[str, float], world: dict[str, float], rng: np.random.Generator) -> float:
    m = DRAWS
    w = np.where(rng.uniform(size=m) < world["pi"], 1, -1)
    E = w + world["sigma"] * rng.normal(size=m)
    S = np.where(rng.uniform(size=m) < world["q"], w, -w)
    a, b, c = (weights[k] + world["weight_noise"] * rng.normal(size=m) if world["weight_noise"] else weights[k] for k in ("a", "b", "c"))
    J = np.where(rng.uniform(size=m) < sigmoid(a * E + b * S + c), 1, -1)
    return float((w == J).mean())


def _verdict(drops: list[float]) -> dict[str, Any]:
    n = len(drops)
    m = float(np.mean(drops))
    se = float(np.std(drops, ddof=1)) / float(np.sqrt(n))
    t = t975(n)
    lo, hi = m - t * se, m + t * se
    return {"mean_drop": m, "ci95": [lo, hi], "verdict": "STABLE" if hi <= TOLERANCE else "NOT_STABLE" if lo > TOLERANCE else "UNRESOLVED"}


def run_perturbation(seeds: list[int] | None = None) -> dict[str, Any]:
    seeds = list(seeds or SEEDS)
    dom = KnowledgeDomain()
    assert ENVIRONMENTS["default"]["pi"] == WORLDS[HOME]["pi"] and ENVIRONMENTS["default"]["q"] == WORLDS[HOME]["q"]  # the home world is the default environment before the shift
    share: dict[str, dict[str, list[float]]] = {c: {w: [] for w in WORLDS} for c in dom.conditions}
    for cond in dom.conditions:
        for s in seeds:
            wt = dom.simulate(cond, s, FULL)["snapshots"]["end"]["weights"]
            for k, (wname, world) in enumerate(WORLDS.items()):
                share[cond][wname].append(_share_correct(wt, world, np.random.default_rng(np.random.SeedSequence([s, k]))))
    rows: dict[str, dict[str, Any]] = {}
    for cond in dom.conditions:
        rows[cond] = {}
        for wname in WORLDS:
            drops = [h - x for h, x in zip(share[cond][HOME], share[cond][wname], strict=True)]
            rows[cond][wname] = {"share_correct": float(np.mean(share[cond][wname])), **_verdict(drops)}
    stable = {w: sorted(c for c in dom.conditions if rows[c][w]["verdict"] == "STABLE") for w in WORLDS}
    calls = {c: {v: sorted(w for w in WORLDS if rows[c][w]["verdict"] == v) for v in ("STABLE", "NOT_STABLE", "UNRESOLVED")} for c in dom.conditions}
    ref = "ground-responsive judgement"
    told_apart = {c: sorted(w for w in WORLDS if {rows[c][w]["verdict"], rows[ref][w]["verdict"]} == {"STABLE", "NOT_STABLE"}) for c in dom.conditions if c != ref}
    sets = {tuple(v) for v in stable.values()}
    body = {"protocol": PROTOCOL, "protocol_digest": digest(PROTOCOL), "rows": rows, "stable_by_world": stable, "verdicts_by_condition": calls, "worlds_that_tell_apart_from_ground_responsive": told_apart,
            "same_stable_set_in_every_world": len(sets) == 1,
            "meaning": "the share correct of a fixed agent in a declared world; STABLE is a statement about that neighbourhood only. Nothing here is knowledge, accuracy of a reading, or a Gaisho; attribution stays UNRESOLVED."}
    return {**body, "digest": digest(body)}
