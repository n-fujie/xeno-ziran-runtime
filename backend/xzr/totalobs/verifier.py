"""The verifier: the only place where the world's state is compared with what was identified. The research agent never imports this module.

Truth here means *the synthetic world's own state at full resolution*, not reality and not "the whole": the verifier knows ``u`` of this model,
nothing outside it. Its objects are connected sets of regions above a fixed truth threshold. Scores are reported to the study, never given to the agent.
"""

from __future__ import annotations

import numpy as np

from .identify import _components
from .world import World

TRUTH_THETA = 0.18


def true_objects(w: World, theta: float = TRUTH_THETA, connect: int = 1) -> list[set[int]]:
    return _components({int(i) for i in np.flatnonzero(w.u > theta)}, w.d, connect)


def score(w: World, identified: list[dict], theta: float = TRUTH_THETA) -> dict:
    """recall / precision at full resolution, spurious (identified with no true counterpart), merged (one identified over several true), split."""
    truth = true_objects(w, theta)
    ident = [set(o["cells"]) for o in identified]
    t_hit = [any(t & i for i in ident) for t in truth]
    i_hit = [any(t & i for t in truth) for i in ident]
    merged = sum(1 for i in ident if sum(1 for t in truth if t & i) >= 2)
    split = sum(1 for t in truth if sum(1 for i in ident if t & i) >= 2)
    return {
        "n_true": len(truth),
        "n_identified": len(ident),
        "recall": (sum(t_hit) / len(truth)) if truth else None,
        "precision": (sum(i_hit) / len(ident)) if ident else None,
        "spurious": sum(1 for h in i_hit if not h),
        "merged": merged,
        "split": split,
    }


def classify_identified(w: World, identified: list[dict], theta: float = TRUTH_THETA) -> dict[str, str]:
    """Per identified object key: 'world' (overlaps a true object) or 'configuration' (an object the observing configuration made and the world did not)."""
    truth = true_objects(w, theta)
    return {o["key"]: ("world" if any(set(o["cells"]) & t for t in truth) else "configuration") for o in identified}
