"""Synthetic demonstration worlds for the Brassier Machine (NEW; nothing here is a result about any real system).

Three pairs of mechanisms, each seen only through ``Observer`` functions (a protocol in, observations out):

* clamp_vs_free      identical under passive observation; they differ only when the ``clamp`` intervention is applied: IDENTIFIED BY that intervention
* hidden_label       differ only in a label that no protocol can reach: OPEN
* gain_vs_offset     differ already under passive observation: DISTINGUISHABLE_UNDER_BASE

``demo_ledger`` assembles the claims, the identifications and the standard AIC/BIC comparison on the same observations."""

from __future__ import annotations

from typing import Any

import numpy as np

from .brassier import Claim, Evidence, Observer, Protocol, identify, standard_comparison, with_brassier

BASE: Protocol = {"name": "passive observation", "interventions": [], "sensors": ["y"], "window": 200, "seeds": [0]}
CLAMP: Protocol = {"name": "clamp intervention", "interventions": ["clamp"], "sensors": ["y"], "window": 200, "seeds": [0]}
LONG: Protocol = {"name": "longer window", "interventions": [], "sensors": ["y"], "window": 600, "seeds": [0]}
SENSOR2: Protocol = {"name": "second sensor", "interventions": [], "sensors": ["y", "z"], "window": 200, "seeds": [0]}


def _signal(p: Protocol) -> np.ndarray:
    return np.sin(0.1 * np.arange(p["window"]))


def free(p: Protocol) -> np.ndarray:
    return _signal(p)


def clamped(p: Protocol) -> np.ndarray:
    y = _signal(p)
    if "clamp" in p["interventions"]:
        y = y.copy()
        y[p["window"] // 2:] = 0.0
    return y


def label_a(p: Protocol) -> np.ndarray:
    return _signal(p)


def label_b(p: Protocol) -> np.ndarray:
    return _signal(p)


def gain(p: Protocol) -> np.ndarray:
    return 1.5 * _signal(p)


def offset(p: Protocol) -> np.ndarray:
    return _signal(p) + 0.5


PAIRS: dict[str, dict[str, Observer]] = {
    "clamp_vs_free": {"M1": free, "M2": clamped},
    "hidden_label": {"M1": label_a, "M2": label_b},
    "gain_vs_offset": {"M1": gain, "M2": offset},
}


def demo_ledger() -> dict[str, Any]:
    ident = {
        "claim-clamp": identify(PAIRS["clamp_vs_free"], BASE, [LONG, SENSOR2, CLAMP]),
        "claim-hidden": identify(PAIRS["hidden_label"], BASE, [LONG, SENSOR2, CLAMP]),
        "claim-gain": identify(PAIRS["gain_vs_offset"], BASE, [LONG]),
    }
    claims = [
        Claim("claim-clamp", "a state-dependent clamp is operating in the system (mechanism M2, not the free mechanism M1)", evidence=[
            Evidence("e-passive", "inconclusive", "observation", BASE, [0], "demo: passive record", "identical under M1 and M2"),
            Evidence("e-clamp", "supports", "intervention", CLAMP, [0], "demo: clamp record", "the clamp intervention separates M1 from M2 and the record follows M2")],
            revision_conditions=["a sensor that reads the clamp state directly would replace this identification"], withdrawal_conditions=["a repeated clamp record that follows M1"]),
        Claim("claim-hidden", "a hidden structure behind the label that separates M1 from M2 exists", evidence=[Evidence("e-model", "supports", "model_output", BASE, [0], "demo: the model states it")],
              revision_conditions=["a new instrument that reaches the label"], withdrawal_conditions=["a protocol is found under which M1 and M2 agree to be the same"]),
        Claim("claim-gain", "the system has gain 1.5 (M1), not an offset of 0.5 (M2)", evidence=[
            Evidence("e-obs-a", "contradicts", "observation", BASE, [0], "demo: passive record", "the record follows M2"),
            Evidence("e-obs-b", "supports", "observation", LONG, [0], "demo: long record", "the earlier part of the record is ambiguous")],
            withdrawal_conditions=["any record that follows M1 over the whole window"]),
    ]
    obs = _signal(BASE)
    # the standard comparison on the same passive observations: the two mechanisms of clamp_vs_free give the same predictions, so the criteria tie
    standard = standard_comparison(obs, {"M1": free(BASE), "M2": clamped(BASE)}, {"M1": 1, "M2": 2})
    out = with_brassier({"synthetic": True, "note": "the base results of the demonstration are untouched by the ledger"}, claims, ident)
    out["standard_comparison_clamp_vs_free_passive"] = standard
    out["note"] = "SYNTHETIC demonstration worlds; no real system is described. The standard comparison ties under passive observation (identical predictions; BIC prefers the fewer parameters); the ledger records the equivalence and the protocol that separates the mechanisms."
    return out
