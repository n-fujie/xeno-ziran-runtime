"""Active Inference math, vendored verbatim from the sibling repository (reuse, not a second framework).

Source: ziran-xeno-simulator, embodied/active_inference/ at commit d4ad6a7544bbb515027e1a97fa914423f01bf8e6
    state_inference.py       sha256 29c03c1a483bb29051684b4763ce60250a544299b778fb9dfca0581ae9a5600e
    expected_free_energy.py  sha256 81a68c643d953594775d0fff6f2fa8ff13185e19d6346d923c5dac49dd99e0bd
    policy_selection.py      sha256 1788e97a9ea23ada7df7ac3f2974fab3d238141adb0b9a4e98a219c949d62f94

Function bodies are unchanged; the optional ``timer`` argument is kept. ``tests/test_aif_vendor.py`` compares
the outputs with the sibling copy when that repository is present next to this one.
"""
from __future__ import annotations

import numpy as np

EPS = 1e-16


# ---- state_inference.py --------------------------------------------------------------------------------------
def posterior(A: np.ndarray, prior: np.ndarray, o: int) -> np.ndarray:
    q = A[o, :] * prior; s = q.sum()  # noqa: E702
    return q / s if s > 0 else np.full_like(prior, 1.0 / len(prior))


def vfe(A: np.ndarray, prior: np.ndarray, q: np.ndarray, o: int) -> float:
    """F = E_q[ln q(s) − ln p(o|s) − ln p(s)] (≥ −ln p(o); equality at the exact posterior)."""
    return float(np.sum(q * (np.log(q + EPS) - np.log(A[o, :] + EPS) - np.log(prior + EPS))))


# ---- expected_free_energy.py ---------------------------------------------------------------------------------
def entropy(p): return float(-np.sum(p * np.log(p + EPS)))  # noqa: E704


def efe(A: np.ndarray, B_pi: np.ndarray, q: np.ndarray, logC: np.ndarray, timer=None) -> dict:
    """`timer` (optional) records the preference and epistemic terms separately; it does not affect the values."""
    import time
    t0 = time.perf_counter_ns()
    qs = B_pi @ q                         # predicted state distribution
    qo = A @ qs                           # predicted observation distribution
    t1 = time.perf_counter_ns()
    pragmatic = float(np.sum(qo * logC))  # expected log preference (higher = better)
    t2 = time.perf_counter_ns()
    ambiguity = float(np.sum(qs * np.array([entropy(A[:, s]) for s in range(A.shape[1])])))
    epistemic = entropy(qo) - ambiguity   # mutual information I(s; o | π)
    t3 = time.perf_counter_ns()
    if timer is not None: timer["prediction"] += t1 - t0; timer["preference"] += t2 - t1; timer["epistemic"] += t3 - t2  # noqa: E701,E702,E501
    return {"G": -pragmatic - epistemic, "pragmatic": pragmatic, "epistemic": epistemic, "risk_proxy": -pragmatic, "ambiguity": ambiguity, "predicted_obs": qo}  # noqa: E501


# ---- policy_selection.py -------------------------------------------------------------------------------------
def select(model, q: np.ndarray, gamma: float, timer=None) -> dict:
    """`timer` (optional dict of ns totals) records EFE parts and the selection step separately; values unaffected."""
    import time
    t0 = time.perf_counter_ns()
    scores = [efe(model.A, model.B[p], q, model.C, timer) for p in range(model.nP)]
    t1 = time.perf_counter_ns()
    G = np.array([s["G"] for s in scores]); logits = np.log(model.E) - gamma * G  # noqa: E702
    pp = np.exp(logits - logits.max()); pp /= pp.sum(); chosen = int(np.argmax(pp))  # noqa: E702
    t2 = time.perf_counter_ns()
    if timer is not None: timer["efe_total"] += t1 - t0; timer["policy_selection"] += t2 - t1  # noqa: E701,E702
    return {"chosen": chosen, "policy_posterior": pp, "scores": scores}
