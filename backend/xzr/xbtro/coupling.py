"""Coupling and transition reconstruction.

Three different things are kept apart, because only the last supports a causal reading:
* association   — how strongly two operation lines' activities move together (peak cross-correlation, with its lag);
* prediction    — whether the past of one line improves a linear prediction of another (Granger-style; still observational);
* intervention  — whether changing one line (an intervention that targets it) changes the other, measured against a matched control.

An edge is ``interventionally-supported`` only when an intervention targeting its source line changes its target line's
activity (paired p < 0.01, |d| >= 0.8) *and* the two are associated; ``correlational-only`` when they are associated but the
intervention that targets the source did not change the target; ``untested`` when no available intervention targets the source.
Correlation or synchrony alone never produces an interventionally-supported edge.

Body transitions are read from five reference states (quiet, moving, correcting, recovering, fallen); the change of the
transition frequencies under an intervention is reported next to the line whose activity changed most.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import metrics, stats
from .engine import Run

STATES = ("quiet", "moving", "correcting", "recovering", "fallen")
TARGETS = {  # intervention -> the operation lines (nodes) it targets directly
    "sensory_delay": ["sens.proprio", "sens.vestibular", "sens.tactile"],
    "visual_block": ["sens.visual"],
    "neural_delay": ["neural.reflex", "neural.central.ankle", "neural.central.hip", "neural.central.cue"],
    "resource_constraint": ["metabolic.supply"],
    "contact_change": ["environment"],
    "perturbation": ["environment"],
    "posture_change": ["mech.passive"],
}
ASSOC_CORR, ASSOC_PRED = 0.5, 0.15
SUPPORT_P, SUPPORT_D = 0.01, 0.8


def activity(run: Run) -> dict[str, np.ndarray]:
    """One activity series (S, T) per operation line (and the environment), from the reference record."""
    out: dict[str, np.ndarray] = {}
    for j, lid in enumerate(run.line_ids):
        ln = next(x for x in run.cfg["lines"] if x["id"] == lid)
        if not ln["enabled"]:
            continue
        if lid.startswith("sens."):
            out[lid] = run["line_active"][:, :, j].astype(float)
        elif lid == "metabolic.supply":
            out[lid] = run["energy"]
        elif lid == "adapt.gain":
            out[lid] = run["kc"]
        elif lid == "breath.cycle":
            out[lid] = np.sin(run["phi"])
        elif lid == "core.tonic":
            out[lid] = run["cc"].mean(axis=2)
        elif lid == "mech.passive":
            out[lid] = np.abs(run["theta"]).mean(axis=2)
        else:
            out[lid] = np.abs(run["line_u"][:, :, j]).sum(axis=2)
    out["environment"] = np.abs(run["push_force"]) + run["slip"].astype(float)
    return out


def line_stats(run: Run) -> dict[str, dict[str, np.ndarray]]:
    """Per line and seed: fraction of time active, ignitions per second, mean command magnitude."""
    T = run["com"].shape[1]
    res: dict[str, dict[str, np.ndarray]] = {}
    for j, lid in enumerate(run.line_ids):
        a = run["line_active"][:, :, j]
        rise = (a[:, 1:] & ~a[:, :-1]).sum(axis=1)
        res[lid] = {
            "active_frac": a.mean(axis=1),
            "ignitions_per_s": rise / (T * run.dt),
            "mean_u": np.abs(run["line_u"][:, :, j]).sum(axis=2).mean(axis=1),
        }
    return res


def body_states(run: Run) -> np.ndarray:
    """(S, T) integer state per step from reference quantities."""
    cfg = run.cfg
    dt = run.dt
    com, vcom, ref = run["com"], run["vcom"], run["xref_true"]
    s, T = com.shape
    err = np.abs(com - ref)
    ref_rate = np.abs(np.gradient(ref, dt, axis=1))
    state = np.zeros((s, T), dtype=int)
    state[(ref_rate > 0.01) | (np.abs(vcom) > 0.03)] = 1
    state[(err >= metrics.band(cfg) * 1.5) & (state == 0)] = 2
    for p in cfg["environment"].get("pushes", []):
        i0 = metrics.idx(p["t"], dt)
        state[:, i0 : i0 + metrics.idx(1.2, dt)] = np.where(
            state[:, i0 : i0 + metrics.idx(1.2, dt)] > 0, 3, state[:, i0 : i0 + metrics.idx(1.2, dt)]
        )
    state[~run["alive"]] = 4
    return state


def transitions(states: np.ndarray) -> np.ndarray:
    """Counts of transitions between distinct consecutive states, summed over seeds (5x5)."""
    m = np.zeros((5, 5))
    a, b = states[:, :-1], states[:, 1:]
    change = a != b
    for i in range(5):
        for j in range(5):
            if i != j:
                m[i, j] = float(((a == i) & (b == j) & change).sum())
    return m


def _assoc(x: np.ndarray, y: np.ndarray, max_lag: int) -> tuple[float, int, float]:
    """Mean over seeds of the signed peak cross-correlation, median lag (samples), mean predictive gain at that lag."""
    cs, ls, gs = [], [], []
    for i in range(x.shape[0]):
        if np.std(x[i]) < 1e-9 or np.std(y[i]) < 1e-9:
            continue
        c, lag = stats.cross_correlation(x[i], y[i], max_lag)
        cs.append(c)
        ls.append(lag)
        gs.append(stats.predictive_gain(x[i], y[i], max(lag, 1) if lag > 0 else 1))
    if not cs:
        return 0.0, 0, 0.0
    return float(np.mean(cs)), int(np.median(ls)), float(np.mean(gs))


def reconstruct(control: Run, interventions: dict[str, Run], max_lag_s: float = 0.3, decimate: int = 2) -> dict[str, Any]:
    """The coupling network of the control run (association, prediction) with interventional evidence from the matching
    intervened runs, plus the transition changes and the lines that changed under each intervention."""
    dt = control.dt
    act = activity(control)
    nodes = [k for k, v in act.items() if float(np.std(v)) > 1e-9]
    max_lag = max(1, int(round(max_lag_s / (dt * decimate))))
    series = {k: act[k][:, ::decimate] for k in nodes}
    iv_act = {iid: activity(r) for iid, r in interventions.items()}
    edges = []
    for x in nodes:
        for y in nodes:
            if x == y:
                continue
            corr, lag, pred = _assoc(series[x], series[y], max_lag)
            associated = abs(corr) >= ASSOC_CORR or pred >= ASSOC_PRED
            if not associated:
                continue
            tested = [iid for iid, tg in TARGETS.items() if x in tg and iid in interventions]
            evidence = None
            if tested and y in act:
                best = None
                for iid in tested:
                    if y not in iv_act[iid]:
                        continue
                    e = stats.paired_effect(act[y].mean(axis=1), iv_act[iid][y].mean(axis=1))
                    if best is None or (np.isfinite(e["p"]) and e["p"] < best["p"]):
                        best = {"intervention": iid, "d": float(e["d"]), "p": float(e["p"]), "n": e["n"]}
                evidence = best
            if evidence and np.isfinite(evidence["p"]) and evidence["p"] < SUPPORT_P and abs(evidence["d"]) >= SUPPORT_D:
                cls = "interventionally-supported"
            elif evidence:
                cls = "correlational-only"
            else:
                cls = "untested"
            edges.append(
                {
                    "source": x,
                    "target": y,
                    "correlation": corr,
                    "lag_s": lag * dt * decimate,
                    "predictive_gain": pred,
                    "interventional": evidence,
                    "class": cls,
                }
            )
    ctrl_states = body_states(control)
    tr0 = transitions(ctrl_states)
    effects = {}
    ctrl_stats = line_stats(control)
    ctrl_m = metrics.summary(control)
    for iid, run in interventions.items():
        st = body_states(run)
        tr1 = transitions(st)
        iv_stats = line_stats(run)
        iv_m = metrics.summary(run)
        line_eff: list[dict[str, Any]] = []
        for lid in ctrl_stats:
            le = stats.paired_effect(ctrl_stats[lid]["mean_u"], iv_stats[lid]["mean_u"]) if lid in iv_stats else None
            if le is not None and np.isfinite(le["d"]):
                line_eff.append(
                    {
                        "line": lid,
                        "d": float(le["d"]),
                        "p": float(le["p"]),
                        "ignitions_per_s": [
                            float(np.nanmean(ctrl_stats[lid]["ignitions_per_s"])),
                            float(np.nanmean(iv_stats[lid]["ignitions_per_s"])),
                        ],
                    }
                )
        line_eff.sort(key=lambda r: -abs(r["d"]))
        outcome = {
            k: stats.paired_effect(ctrl_m[k], iv_m[k])
            for k in ("sway_rms", "peak_dev", "settle_turn_rmst", "recovery_rmst", "fall", "energy_used")
        }
        # association across seeds between a line's change and the change of the outcome (observational; ranked, not causal)
        assoc: list[dict[str, Any]] = []
        for lid in ctrl_stats:
            dl = iv_stats[lid]["mean_u"] - ctrl_stats[lid]["mean_u"]
            for k in ("peak_dev", "recovery_rmst", "sway_rms"):
                do = iv_m[k] - ctrl_m[k]
                ok = np.isfinite(dl) & np.isfinite(do)
                if ok.sum() >= 4 and np.std(dl[ok]) > 1e-12 and np.std(do[ok]) > 1e-12:
                    assoc.append({"line": lid, "outcome": k, "r": float(np.corrcoef(dl[ok], do[ok])[0, 1]), "n": int(ok.sum())})
        assoc.sort(key=lambda r: -abs(float(r["r"])))
        effects[iid] = {
            "lines": line_eff[:8],
            "outcome": {
                k: {"d": _f(v["d"]), "p": _f(v["p"]), "mean_control": _f(v["mean_a"]), "mean_intervention": _f(v["mean_b"])}
                for k, v in outcome.items()
            },
            "transition_change": (_norm(tr1) - _norm(tr0)).tolist(),
            "transitions": tr1.tolist(),
            "association_with_outcome": assoc[:6],
            "note": "line ranking is the paired effect of the intervention on each line's command magnitude; the association list is "
            "observational (across seeds) and is not evidence of causation by itself",
        }
    return {
        "nodes": nodes,
        "edges": edges,
        "states": list(STATES),
        "control_transitions": tr0.tolist(),
        "effects": effects,
        "classes": {
            c: sum(1 for e in edges if e["class"] == c) for c in ("interventionally-supported", "correlational-only", "untested")
        },
    }


def _norm(m: np.ndarray) -> np.ndarray:
    tot = m.sum()
    return m / tot if tot > 0 else m


def _f(x: float) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)
