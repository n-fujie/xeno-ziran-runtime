"""What an observer can say about a configuration of the SBS substrate, and what it cannot.

Everything here is a declared analytical convention applied to positions; none of it is part of the dynamics. The six outcomes of Bodily Dissolution are separate functions with separate thresholds, and no function returns a single 'body' flag:

* physical        connectivity of the contact graph (bond cut-off ``R_BOND``): the share of particles in the largest connected component, the number of bonds
* organizational  the persistence of a tracked group's MEMBERSHIP: the best Jaccard overlap between the reference group and any group now
* functional      force transmission: a probe pulls the leading fifth of the reference group along +x and the displacement of the trailing fifth is compared with the same run without the pull (same noise)
* attributional   whether a group-level description is supported at all: decided by the model comparison of ``comparison.py``, not here
* agentic         NOT APPLICABLE: the substrate has no agent, policy or goal, and nothing is recorded for it
* observational   the disagreement between the partition read from an OBSERVED frame (noisy positions) and the partition read from the true positions

A tracked group is the largest component at the reference time, nothing more: the reference group is not a body; it is the object whose fate the records follow."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from .engine import Sim

R_BOND = 1.35  # two particles closer than this are in contact (just inside the attractive well)
MIN_GROUP = 4  # a connected set of fewer particles is not tracked as a group
TRANSMIT_WINDOW = 400  # steps of the force-transmission probe
PULL = 1.5  # force applied to the leading fifth during the probe


def contact_graph(x: np.ndarray, box: float, r_bond: float | None = None) -> np.ndarray:
    r_bond = R_BOND if r_bond is None else r_bond  # read at call time so that a sensitivity run can change the cut-off
    d = x[:, None, :] - x[None, :, :]
    d -= box * np.round(d / box)
    r = np.sqrt((d**2).sum(-1))
    np.fill_diagonal(r, np.inf)
    return r < r_bond


def partition(x: np.ndarray, box: float, r_bond: float | None = None) -> np.ndarray:
    """Labels of the connected components of the contact graph (label -1 for components smaller than ``MIN_GROUP``)."""
    adj = contact_graph(x, box, r_bond)
    _, lab = connected_components(csr_matrix(adj))
    size = np.bincount(lab)
    out = np.where(size[lab] >= MIN_GROUP, lab, -1)
    return out


def physical(x: np.ndarray, box: float) -> dict[str, Any]:
    adj = contact_graph(x, box)
    _, lab = connected_components(csr_matrix(adj))
    sizes = np.sort(np.bincount(lab))[::-1]
    return {"largest_share": float(sizes[0] / len(x)), "components": int(len(sizes)), "bonds": int(adj.sum() // 2), "groups_tracked": int((sizes >= MIN_GROUP).sum())}


def largest_group(x: np.ndarray, box: float) -> np.ndarray:
    """Indices of the largest connected component."""
    _, lab = connected_components(csr_matrix(contact_graph(x, box)))
    return np.flatnonzero(lab == np.bincount(lab).argmax())


def organizational(x: np.ndarray, box: float, reference: np.ndarray) -> dict[str, Any]:
    """Membership persistence of a reference group: the best Jaccard overlap with any current group, and how the reference has split."""
    lab = partition(x, box)
    ref = set(int(i) for i in reference)
    best, best_label = 0.0, -1
    for k in set(int(v) for v in lab if v >= 0):
        mem = set(int(i) for i in np.flatnonzero(lab == k))
        j = len(ref & mem) / len(ref | mem)
        if j > best:
            best, best_label = j, k
    pieces = sorted((int(((lab == k) & np.isin(np.arange(len(x)), reference)).sum()) for k in set(int(v) for v in lab if v >= 0)), reverse=True)
    retained = 0.0 if best_label < 0 else len(ref & set(int(i) for i in np.flatnonzero(lab == best_label))) / len(ref)
    return {"best_overlap": float(best), "reference_retained_in_best_group": float(retained), "reference_pieces": [p for p in pieces if p > 0], "groups_now": int(len(set(int(v) for v in lab if v >= 0)))}


def transmission(sim: Sim, reference: np.ndarray, steps: int = TRANSMIT_WINDOW) -> dict[str, Any]:
    """Functional probe. Pull the leading fifth (largest unwrapped x) of the reference group along +x for ``steps`` steps and compare the displacement of the trailing fifth with the control branch that shares the noise but has no pull. The ratio 1 means the group moves as one; 0 means the pull does not reach the trailing particles."""
    if len(reference) < 5:
        return {"ratio": None, "why": "reference group smaller than five particles"}
    order = reference[np.argsort(sim.unwrapped[reference, 0])]
    k = max(1, len(order) // 5)
    trail, lead = order[:k], order[-k:]
    seed = int(sim.noise.integers(1 << 31))
    pulled, control = sim.clone(seed), sim.clone(seed)
    pull = np.zeros_like(sim.x)
    pull[lead, 0] = PULL
    pulled.step(steps, pull=pull)
    control.step(steps)
    dl = float((pulled.unwrapped[lead, 0] - control.unwrapped[lead, 0]).mean())
    dt = float((pulled.unwrapped[trail, 0] - control.unwrapped[trail, 0]).mean())
    return {"ratio": (dt / dl) if abs(dl) > 1e-9 else None, "lead_shift": dl, "trail_shift": dt}


def observe(x: np.ndarray, box: float, sigma_obs: float, rng: np.random.Generator) -> np.ndarray:
    """The frame an observer gets: positions with Gaussian measurement error (an apparatus condition, not a change of the system)."""
    return (x + sigma_obs * rng.normal(size=x.shape)) % box


def adjusted_rand(a: np.ndarray, b: np.ndarray) -> float:
    """Adjusted Rand index between two labelings (labels -1 are treated as singletons)."""
    a = np.where(a < 0, 1_000_000 + np.arange(len(a)), a)
    b = np.where(b < 0, 2_000_000 + np.arange(len(b)), b)
    _, ai = np.unique(a, return_inverse=True)
    _, bi = np.unique(b, return_inverse=True)
    table = np.zeros((ai.max() + 1, bi.max() + 1))
    np.add.at(table, (ai, bi), 1)
    comb = lambda v: v * (v - 1) / 2  # noqa: E731
    sum_cells = comb(table).sum()
    sum_a, sum_b = comb(table.sum(1)).sum(), comb(table.sum(0)).sum()
    expected = sum_a * sum_b / comb(len(a))
    maximum = (sum_a + sum_b) / 2
    return 1.0 if maximum == expected else float((sum_cells - expected) / (maximum - expected))
