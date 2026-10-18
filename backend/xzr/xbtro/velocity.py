"""Operational Velocity Engine: ten separate measures of how fast operations take hold.

Each measure has its own definition and its own events; none is derived from another and none is a single "speed". Measures are
computed from the model reference record here (what really happened in the simulation); the observation side re-estimates the
measures it can reach from its own signals (observation.py), so the two can be compared.

Status of a velocity description across conditions (``compare_status``): *established* (defined and unchanged), *varied* (defined
in both, significantly changed), *lapsed* (defined in the baseline but not in the condition). A lapse is classified separately as
* ``line-stopped``: the operation line behind the measure was disabled or never ignited;
* ``observation-lost``: the quantity still exists in the reference but the current observation configuration cannot measure it;
* ``description-inapplicable``: the lines were active but the defining event did not occur (e.g. the body fell first, or no
  crossing happened), so the existing velocity description no longer applies;
* ``not-achieved-in-window``: the recovery / settling did not happen inside the observation window. This is a censored
  observation: no time is recorded for it (never the window length), and it is counted separately from the three kinds above.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import metrics, stats
from .engine import Run

MEASURES: list[dict[str, Any]] = [
    {
        "id": "sensory_detection",
        "label": "sensory detection latency",
        "unit": "s",
        "stimulus": "cue",
        "definition": "time from a cue to the first ignition of the cue-perception line",
        "lines": ["sens.cue"],
    },
    {
        "id": "neural_response",
        "label": "neural response latency",
        "unit": "s",
        "stimulus": "cue",
        "definition": "time from a cue to the first ignition of the central movement command line",
        "lines": ["neural.central.cue"],
    },
    {
        "id": "muscle_onset",
        "label": "muscle activation onset latency",
        "unit": "s",
        "stimulus": "cue",
        "definition": "time from a cue until the ankle net activation deviates from its baseline by more than 0.03",
        "lines": ["neural.central.ankle"],
    },
    {
        "id": "movement_onset",
        "label": "movement onset latency",
        "unit": "s",
        "stimulus": "cue",
        "definition": "time from a cue until the COM has moved 3 mm towards the target",
        "lines": ["neural.central.cue", "neural.central.ankle"],
    },
    {
        "id": "correction",
        "label": "movement correction latency",
        "unit": "s",
        "stimulus": "push",
        "definition": "time from a push until the ankle torque deviates by more than 5 Nm against the push",
        "lines": ["neural.central.ankle", "mech.passive"],
    },
    {
        "id": "settling",
        "label": "settling time",
        "unit": "s",
        "stimulus": "turn",
        "definition": "time after the direction change until the COM stays within the pre-registered tolerance band of the new target for 0.4 s",
        "lines": ["neural.central.ankle"],
    },
    {
        "id": "adaptation",
        "label": "adaptation speed",
        "unit": "1/trial",
        "stimulus": "trials",
        "definition": "rate at which the peak deviation after a push falls over repeated trials (slope of log deviation)",
        "lines": ["adapt.gain"],
    },
    {
        "id": "recovery",
        "label": "recovery time",
        "unit": "s",
        "stimulus": "push",
        "definition": "time after a push (from the largest deviation) until the COM is back within the pre-registered tolerance band of the reference and slow, for 0.4 s, inside the window that ends at the next protocol event",
        "lines": ["neural.central.ankle"],
    },
    {
        "id": "reconfiguration",
        "label": "observation reconfiguration speed",
        "unit": "rounds / s",
        "stimulus": "observation",
        "definition": "rounds and simulated set-up time needed until an unobserved difference becomes identified (Experiment E)",
        "lines": [],
    },
    {
        "id": "consequence",
        "label": "time to the consequence",
        "unit": "s",
        "stimulus": "cue / push",
        "definition": "time from the stimulus until the consequence is established: the target reached, or a fall",
        "lines": [],
    },
]
BY_ID = {m["id"]: m for m in MEASURES}


def onset(
    signal: np.ndarray,
    i0: int,
    dt: float,
    thr: float,
    direction: int = 0,
    base_steps: int = 20,
    hold: int = 2,
    end: int | None = None,
) -> np.ndarray:
    """Seconds from step ``i0`` until ``signal`` deviates from its pre-event mean by more than ``thr`` for ``hold`` steps.
    ``direction`` +1 / −1 requires the deviation to have that sign, 0 either. NaN if it never does."""
    s, t = signal.shape
    end = t if end is None else min(end, t)
    b0 = max(0, i0 - base_steps)
    base = signal[:, b0:i0].mean(axis=1) if i0 > b0 else signal[:, 0]
    dev = signal[:, i0:end] - base[:, None]
    hit = (np.abs(dev) > thr) if direction == 0 else (direction * dev > thr)
    if hold > 1 and hit.shape[1] >= hold:
        ok = np.ones_like(hit)
        for h in range(hold):
            ok[:, : hit.shape[1] - h] &= hit[:, h:]
            ok[:, hit.shape[1] - h :] = False
        hit = ok
    first = np.where(hit.any(axis=1), hit.argmax(axis=1), -1)
    return np.where(first >= 0, first * dt, np.nan)


def _line_first_active(run: Run, lid: str, i0: int) -> tuple[np.ndarray, str | None]:
    if lid not in run.line_ids:
        return np.full(run["com"].shape[0], np.nan), "line-stopped"
    j = run.line_ids.index(lid)
    ln = next(x for x in run.cfg["lines"] if x["id"] == lid)
    if not ln["enabled"]:
        return np.full(run["com"].shape[0], np.nan), "line-stopped"
    act = run["line_active"][:, i0:, j]
    # ignition = a rising edge after the stimulus (a line already active before the stimulus does not "ignite" at it)
    prev = run["line_active"][:, max(i0 - 1, 0) : -1, j]
    rise = act & ~prev[:, : act.shape[1]]
    first = np.where(rise.any(axis=1), rise.argmax(axis=1), -1)
    return np.where(first >= 0, first * run.dt, np.nan), None


def profile(run: Run) -> dict[str, dict[str, Any]]:
    """Reference velocity measures of a run: per measure the per-seed values, how many seeds defined it, and per-seed reasons
    for the undefined ones."""
    cfg = run.cfg
    ev = metrics.events(cfg)
    dt = run.dt
    s = run["com"].shape[0]
    alive = run["alive"]
    out: dict[str, dict[str, Any]] = {}

    def put(mid: str, values: np.ndarray, reasons: np.ndarray | None = None) -> None:
        defined = np.isfinite(values)
        reasons = reasons if reasons is not None else np.full(s, "", dtype=object)
        r = np.where(defined, "", reasons)
        out[mid] = {"values": values, "defined": float(defined.mean()), "reasons": r.tolist()}

    def classify_missing(values: np.ndarray, lines: list[str], i_event: int, line_reason: str | None) -> np.ndarray:
        reasons = np.full(s, "", dtype=object)
        miss = ~np.isfinite(values)
        if line_reason:
            reasons[miss] = line_reason
            return reasons
        fell_before = run.fell & (run.fall_time <= (i_event + 1) * dt + 1.0)
        reasons[miss] = "description-inapplicable"
        reasons[miss & fell_before] = "description-inapplicable (the body fell first)"
        # a measure whose lines never ignited anywhere in the run lapsed because the operation stopped
        for lid in lines:
            if lid in run.line_ids:
                j = run.line_ids.index(lid)
                never = ~run["line_active"][:, i_event:, j].any(axis=1)
                reasons[miss & never] = "line-stopped"
        return reasons

    # --- cue-triggered
    i_cue = metrics.idx(ev["cue"], dt)
    det, why = _line_first_active(run, "sens.cue", i_cue)
    put("sensory_detection", det, classify_missing(det, ["sens.cue"], i_cue, why))
    nr, why = _line_first_active(run, "neural.central.cue", i_cue)
    put("neural_response", nr, classify_missing(nr, ["neural.central.cue"], i_cue, why))
    ank = run["act"][:, :, 0, 0] - run["act"][:, :, 0, 1]
    mo = onset(ank, i_cue, dt, 0.03, end=metrics.idx(ev["turn"] - 0.1, dt))
    put("muscle_onset", mo, classify_missing(mo, ["neural.central.ankle"], i_cue, None))
    direction = int(np.sign(cfg["task"]["x_target"])) or 1
    mv = onset(run["com"], i_cue, dt, 0.003, direction=direction, end=metrics.idx(ev["turn"] - 0.1, dt))
    put("movement_onset", mv, classify_missing(mv, ["neural.central.cue", "neural.central.ankle"], i_cue, None))
    # --- push-triggered
    if ev["pushes"]:
        i_push = metrics.idx(ev["pushes"][0], dt)
        sign = int(np.sign(ev["push_forces"][0])) or 1
        # the body resists a push with an opposing ankle torque deviation
        co = onset(run["tau"][:, :, 0], i_push, dt, 5.0, direction=-sign, end=i_push + metrics.idx(1.5, dt))
        put("correction", co, classify_missing(co, ["neural.central.ankle"], i_push, None))
        m = metrics.summary(run)
        rec_def = m["recovery"].copy()  # NaN where the body did not recover inside the window (censored, not a time)
        rr = classify_missing(rec_def, ["neural.central.ankle"], i_push, None)
        rr = np.where(m["recovery_status"] == "not-achieved-in-window", "not-achieved-in-window", rr)
        put("recovery", rec_def, rr)
    else:
        put("correction", np.full(s, np.nan), np.full(s, "no push in this protocol", dtype=object))
        put("recovery", np.full(s, np.nan), np.full(s, "no push in this protocol", dtype=object))
    # --- settling after the turn
    m = metrics.summary(run)
    st = m["settle_turn"].copy()
    sr = classify_missing(st, ["neural.central.ankle"], metrics.idx(ev["turn"], dt), None)
    sr = np.where(m["settle_turn_status"] == "not-achieved-in-window", "not-achieved-in-window", sr)
    put("settling", st, sr)
    # --- time to the consequence: the cue's target reached (within 2 bands) or a fall, whichever comes first
    tgt = cfg["task"]["x_target"]
    near = (np.abs(run["com"] - tgt) < 2 * metrics.band(run.cfg)) & alive
    near[:, :i_cue] = False
    first = np.where(near.any(axis=1), near.argmax(axis=1), -1)
    reached = np.where(first >= 0, (first - i_cue) * dt, np.nan)
    fell_t = np.where(run.fell, run.fall_time - ev["cue"], np.nan)
    cons = np.where(np.isfinite(reached), reached, fell_t)
    outcome = np.where(np.isfinite(reached), "goal", np.where(run.fell, "fall", "none"))
    put("consequence", cons, classify_missing(cons, [], i_cue, None))
    out["consequence"]["outcome"] = outcome.tolist()
    # adaptation and reconfiguration need several runs / rounds: filled by the experiments that make them
    put("adaptation", np.full(s, np.nan), np.full(s, "needs repeated trials (Experiment D)", dtype=object))
    put("reconfiguration", np.full(s, np.nan), np.full(s, "needs observation rounds (Experiment E)", dtype=object))
    return out


def adaptation_speed(peak_by_trial: np.ndarray) -> np.ndarray:
    """Per seed, the rate (per trial) at which the peak deviation falls: negative slope of log(peak) over trials. ``peak_by_trial``
    has shape (trials, seeds). Positive = adapting (deviation shrinking); NaN if fewer than 3 valid trials."""
    k, s = peak_by_trial.shape
    out = np.full(s, np.nan)
    x = np.arange(k, dtype=float)
    for i in range(s):
        y = peak_by_trial[:, i]
        ok = np.isfinite(y) & (y > 1e-9)
        if ok.sum() >= 3:
            slope = np.polyfit(x[ok], np.log(y[ok]), 1)[0]
            out[i] = -float(slope)
    return out


def compare_status(
    base: dict[str, dict[str, Any]], cond: dict[str, dict[str, Any]], observed: set[str] | None = None
) -> list[dict[str, Any]]:
    """For each measure: established / varied / lapsed (and the kind of lapse), comparing a condition with the baseline.
    ``observed`` is the set of measure ids the current observation configuration can estimate (None = not asked)."""
    rows = []
    for m in MEASURES:
        mid = m["id"]
        b, c = base[mid], cond[mid]
        row: dict[str, Any] = {
            "id": mid,
            "label": m["label"],
            "unit": m["unit"],
            "baseline_defined": b["defined"],
            "condition_defined": c["defined"],
        }
        if b["defined"] < 0.5:
            row.update(status="not-established-in-baseline", reason=None)
        elif c["defined"] < 0.5:
            reasons = [r for r in c["reasons"] if r]
            kinds: dict[str, int] = {}
            for r in reasons:
                key = r.split(" (")[0]
                kinds[key] = kinds.get(key, 0) + 1
            top = max(kinds, key=lambda k: kinds[k]) if kinds else "description-inapplicable"
            row.update(status="lapsed", reason=top, reason_counts=kinds)
        else:
            eff = stats.paired_effect(b["values"], c["values"])
            changed = eff["p"] < 0.05 and abs(eff["d"]) >= 0.8
            row.update(status="varied" if changed else "established", reason=None, effect=eff)
        if observed is not None and row["status"] in ("established", "varied") and mid not in observed:
            row["observation"] = "observation-lost"
        rows.append(row)
    return rows
