"""Non-redundancy tests: does removing a descriptive element degrade a capability in a regime?

Elements are operationalised as removable parts of the comparator (``pai/controllers.py`` ABLATIONS):

    agent             no_agent            no persisting controller state (prior reset, no learning, no rebuild)
    boundary          no_boundary         channels and actuator sample the whole field (no sensory/active partition);
                                          also applied to the model-light controller
    model             no_model            no transition model (B uniform, never learned)
    prediction error  no_prediction_error no learning from prediction errors after calibration
    free energy       no_free_energy      no surprise-triggered structural revision
    expected FE       no_efe_epistemic    policies scored without the epistemic term
    latent state      no_latent           no latent-state inference (belief = one-hot observation)
    policy            no_policy           no policy selection (uniformly random action)

The reference is the full adaptive comparator (``aif_adaptive``), on the same world, seed, perturbation and channels.

Capabilities (comparator-side; perturbation phase unless stated):

    prediction                     one_step_acc_pert
    intervention                   success_pert
    recovery                       success_rec
    reachable_state_estimation     support_coverage_pert
    perturbation_localisation      channel_localisation_auc
    structural_transition_detection surprise detection at onset (hit = 1)
    history_reuse                  success_rec, cells of memory.history_reactivation only

Re-ignition detection and configuration-crossing recurrence are properties of the tracker. The comparator has no
counterpart, so they are reported as "not applicable" rather than tested.

Test: per regime (each cell's majority label from the classifier; the control cell is the reference regime), paired
differences d = full − ablated over (seed, cell) pairs; two-sided sign-flip test; Holm correction over every
(element, capability, regime) test.

    NON-REDUNDANT  Holm-adjusted p < 0.05 and mean d ≥ MARGIN (removal degrades)
    REDUNDANT      95 % bootstrap CI of d within ±MARGIN (removal changes nothing material)
    HARMFUL        Holm-adjusted p < 0.05 and mean d ≤ −MARGIN (removal improves the capability)
    UNRESOLVED     otherwise (underpowered or mixed)

No element is assumed non-redundant: every status comes from the test.
"""
from __future__ import annotations

import numpy as np

from pai.stats import holm, paired

MARGIN = 0.05
ELEMENTS = {"agent": "no_agent", "boundary": "no_boundary", "model": "no_model",
            "prediction_error": "no_prediction_error", "free_energy": "no_free_energy",
            "expected_free_energy": "no_efe_epistemic", "latent_state": "no_latent", "policy": "no_policy"}


def _cap(rec: dict, cap: str, cell_key: str | None):
    if rec is None or rec.get("status") != "ok":
        return None
    m = rec["metrics"]
    if cap == "prediction":
        return m.get("one_step_acc_pert")
    if cap == "intervention":
        return m.get("success_pert")
    if cap == "recovery":
        return m.get("success_rec")
    if cap == "reachable_state_estimation":
        return m.get("support_coverage_pert")
    if cap == "perturbation_localisation":
        return m.get("channel_localisation_auc")
    if cap == "structural_transition_detection":
        d = m.get("surprise_detect_onset")
        return None if d is None else float(d["hit"])
    if cap == "history_reuse":
        return m.get("success_rec") if cell_key and "history_reactivation" in cell_key else None
    raise ValueError(cap)


CAPABILITIES = ("prediction", "intervention", "recovery", "reachable_state_estimation", "perturbation_localisation",
                "structural_transition_detection", "history_reuse")
NOT_APPLICABLE = {"reignition_detection": "tracker-only capability (exact from the step records); no comparator analogue",
                  "configuration_crossing_recurrence": "tracker-only capability; no comparator analogue"}


def analyse(cells: list[dict]) -> dict:
    """cells: [{"key", "severity", "regime", "seed", "runs": {controller: record}}] (ablation cells only)."""
    rows = []
    for el, abl in ELEMENTS.items():
        for cap in CAPABILITIES:
            for regime in sorted({c["regime"] for c in cells if c["regime"]}):
                d = []
                for c in cells:
                    if c["regime"] != regime:
                        continue
                    full = _cap(c["runs"].get("aif_adaptive"), cap, c["key"])
                    ab = _cap(c["runs"].get(f"aif_adaptive-{abl}"), cap, c["key"])
                    if full is not None and ab is not None:
                        d.append(full - ab)
                if len(d) < 3:
                    continue
                rows.append({"element": el, "ablation": abl, "capability": cap, "regime": regime, **paired(d, MARGIN)})
            # boundary ablation on the model-light controller as well
        if el == "boundary":
            for cap in ("intervention", "recovery"):
                for regime in sorted({c["regime"] for c in cells if c["regime"]}):
                    d = []
                    for c in cells:
                        if c["regime"] != regime:
                            continue
                        full = _cap(c["runs"].get("ost"), cap, c["key"])
                        ab = _cap(c["runs"].get("ost-no_boundary"), cap, c["key"])
                        if full is not None and ab is not None:
                            d.append(full - ab)
                    if len(d) >= 3:
                        rows.append({"element": "boundary (model-light controller)", "ablation": "no_boundary",
                                     "capability": cap, "regime": regime, **paired(d, MARGIN)})
    adj = holm([r["p"] for r in rows]) if rows else []
    for r, p in zip(rows, adj, strict=True):
        r["p_holm"] = p
        if p < 0.05 and r["mean"] >= MARGIN:
            r["status"] = "NON-REDUNDANT"
        elif p < 0.05 and r["mean"] <= -MARGIN:
            r["status"] = "HARMFUL"
        elif r["within_margin"]:
            r["status"] = "REDUNDANT"
        else:
            r["status"] = "UNRESOLVED"
    table: dict = {}
    for r in rows:
        table.setdefault(r["element"], {}).setdefault(r["regime"], {})[r["capability"]] = r["status"]
    return {"tests": rows, "table": table, "margin": MARGIN, "n_tests": len(rows), "not_applicable": NOT_APPLICABLE,
            "correction": "Holm over all tests"}


def summary_status(table: dict) -> dict:
    """Per element and regime: NON-REDUNDANT if any capability is; REDUNDANT if all tested capabilities are;
    otherwise UNRESOLVED (HARMFUL listed when present)."""
    out: dict = {}
    for el, regs in table.items():
        for reg, caps in regs.items():
            v = list(caps.values())
            st = "NON-REDUNDANT" if "NON-REDUNDANT" in v else ("REDUNDANT" if v and all(x == "REDUNDANT" for x in v)
                                                               else "UNRESOLVED")
            out.setdefault(el, {})[reg] = {"status": st, "harmful_for": [k for k, x in caps.items() if x == "HARMFUL"],
                                           "non_redundant_for": [k for k, x in caps.items() if x == "NON-REDUNDANT"]}
    return out


__all__ = ["analyse", "summary_status", "ELEMENTS", "CAPABILITIES", "MARGIN", "np"]
