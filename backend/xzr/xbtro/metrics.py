"""Reference metrics: computed from the model reference record of a run (simulator-internal quantities).

These are the *ground truth* of the simulation, used to know what really differs between two conditions. They are never
presented as observations of a body; an observation configuration has its own, separate features (observation.py).

Conventions: every organization metric is "lower is better" so that a negative paired effect is an improvement; a body that
fell has its time-to-event metrics censored at the end of the record and is counted in ``fall``; quantities that are undefined
(e.g. the push-recovery time of a run without a push) are NaN.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .engine import Run

# Tolerance bands are fixed BEFORE any experiment is evaluated, from the steady-state fluctuation of the nominal body:
#   band = 3 x (SD of the COM about its own quadratic drift in the steady hold windows [3.0, 3.8] s and [5.8, 7.8] s of the
#   default protocol, unperturbed), exploration seeds 1000..1031, rounded up to the next millimetre (``calibrate_band`` reproduces it).
# They are NOT adjusted to the outcome of an experiment. Final experiments use other seeds (FINAL_SEED_BASE).
TOLERANCE: dict[str, dict[str, Any]] = {
    "human-like": {"band": 0.009, "rule": "max(3 x detrended steady COM SD, 0.25 x smallest step), exploration seeds 1000..1031"},
    "machine-like": {
        "band": 0.009,
        "rule": "max(3 x detrended steady COM SD, 0.25 x smallest step), exploration seeds 1000..1031",
    },
}
HOLD = 0.4  # s, how long a body must stay inside the band
STEP_FRACTION = 0.25
VEL_BAND = 0.04  # m/s, together with the COM band: a settled body is also nearly still
EXPLORATION_SEEDS = list(range(1000, 1032))
FINAL_SEED_BASE = 5000


def band(cfg: dict[str, Any]) -> float:
    if cfg["task"].get("band") is not None:
        return float(cfg["task"]["band"])
    return float(TOLERANCE.get(cfg.get("family", "human-like"), TOLERANCE["human-like"])["band"])


def calibrate_band(preset: str) -> float:
    """Reproduce the pre-registered band of a preset from its exploration runs (see TOLERANCE)."""
    from . import config, engine

    cfg = config.build(preset)
    r = engine.simulate(cfg, EXPLORATION_SEEDS)
    dt = r.dt
    res = []
    for a, b in ((3.0, 3.8), (5.8, 7.8)):
        x = r["com"][:, int(a / dt) : int(b / dt)]
        tt = np.linspace(-1.0, 1.0, x.shape[1])
        V = np.vander(tt, 3)  # slow drift (quadratic) is not fluctuation
        coef = np.linalg.lstsq(V, x.T, rcond=None)[0]
        res.append(x - (V @ coef).T)
    sd = float(np.sqrt(np.mean(np.concatenate(res, axis=1) ** 2)))
    step = min(abs(cfg["task"]["x_target"]), abs(cfg["task"]["x_turn"] - cfg["task"]["x_target"]))
    return float(np.ceil(max(3.0 * sd, STEP_FRACTION * step) * 1000.0) / 1000.0)


def idx(t: float, dt: float) -> int:
    return int(round(t / dt))


def events(cfg: dict[str, Any]) -> dict[str, Any]:
    """The protocol's own schedule. Pushes tagged ``role: intervention`` (added by an intervention) are disturbances inside the
    windows of the protocol, not events that cut them."""
    task = cfg["task"]
    pushes = sorted((p for p in cfg["environment"].get("pushes", []) if p.get("role") != "intervention"), key=lambda p: p["t"])
    return {
        "cue": task["t_cue"],
        "turn": task["t_turn"],
        "pushes": [p["t"] for p in pushes],
        "push_forces": [p["force"] for p in pushes],
        "horizon": task["horizon"],
        "dt": task["dt"],
    }


def window_end(ev: dict[str, Any], t_after: float) -> float:
    """End of the observation window that starts at ``t_after``: the next protocol event, or the end of the record."""
    nxt = [t for t in [ev["cue"], ev["turn"], *ev["pushes"]] if t > t_after + 1e-9]
    return min([*nxt, ev["horizon"]])


def _hold_entry(inside: np.ndarray, start: int, hold: int, stop: int | None = None) -> np.ndarray:
    """For each row: first index >= start from which ``inside`` stays true for ``hold`` steps and that run ends before ``stop``
    (default: the end of the record); -1 if never."""
    s, t = inside.shape
    stop = t if stop is None else min(stop, t)
    out = np.full(s, -1)
    for i in range(s):
        row = inside[i]
        run_len = 0
        for k in range(start, stop):
            run_len = run_len + 1 if row[k] else 0
            if run_len >= hold:
                out[i] = k - hold + 1
                break
    return out


STATUSES = ("achieved", "not-achieved-in-window", "fell", "diverged")


def time_to_hold(
    run: Run, inside: np.ndarray, t_event: float, t_end: float, start_idx: np.ndarray | None = None
) -> dict[str, np.ndarray]:
    """Time from ``t_event`` until ``inside`` has held for HOLD within the window ending at ``t_end``.

    ``time`` is NaN where it was not achieved (a censored observation, NOT a time). ``status`` says why: achieved,
    not-achieved-in-window, fell (a physical fall before the window ended), diverged (numerical failure). ``window`` is the
    length of the observation window (the censoring time) and ``rmst`` is the restricted mean: the time where achieved, the
    window length otherwise; it is NaN for numerically diverged runs, which are excluded, not scored."""
    dt = run.dt
    s = inside.shape[0]
    i0, i1 = idx(t_event, dt), idx(t_end, dt)
    hold = max(1, int(round(HOLD / dt)))
    hit = np.full(s, -1)
    for k in range(s):
        st = i0 if start_idx is None else int(start_idx[k])
        hit[k] = _hold_entry(inside[k : k + 1], st, hold, i1)[0]
    window = (i1 - i0) * dt
    ok = hit >= 0
    time = np.where(ok, (hit - i0) * dt, np.nan)
    fell = run.fell & (run.fall_time <= t_end + 1e-9)
    status = np.where(ok, "achieved", np.where(run.diverged, "diverged", np.where(fell, "fell", "not-achieved-in-window")))
    rmst = np.where(ok, time, np.where(run.diverged, np.nan, window))
    return {"time": time, "status": status.astype(object), "window": np.full(s, window), "rmst": rmst}


def settle_time(run: Run, t_event: float, target: np.ndarray, t_end: float | None = None) -> dict[str, np.ndarray]:
    """Time after ``t_event`` until the COM is within the pre-registered band of ``target`` (per seed) and nearly still, and
    stays so for HOLD, inside the window that ends at the next protocol event."""
    ev = events(run.cfg)
    t_end = window_end(ev, t_event) if t_end is None else t_end
    inside = (np.abs(run["com"] - target) < band(run.cfg)) & (np.abs(run["vcom"]) < VEL_BAND * 2) & run["alive"]
    return time_to_hold(run, inside, t_event, t_end)


def summary(run: Run) -> dict[str, np.ndarray]:
    """Per-seed reference metrics of a run."""
    cfg = run.cfg
    ev = events(cfg)
    dt = run.dt
    s, T = run["com"].shape
    trunk = min(2, run["theta"].shape[2] - 1)
    alive = run["alive"]
    out: dict[str, np.ndarray] = {}
    out["fall"] = run.fell.astype(float)
    out["fall_time"] = np.where(run.fell, run.fall_time, np.nan)
    # posture stability: trunk sway in the quiet window before the cue (undefined if the body fell inside it)
    q0, q1 = idx(0.3, dt), max(idx(ev["cue"] - 0.1, dt), idx(0.4, dt))
    th = run["theta"][:, q0:q1, trunk]
    ok = alive[:, q0:q1].all(axis=1)
    sway = np.sqrt(((th - th.mean(axis=1, keepdims=True)) ** 2).mean(axis=1))
    out["sway_rms"] = np.where(ok, sway, np.nan)
    # tracking of the true reference over the whole task; fallen bodies score the error they reached (censored by the record)
    err = run["com"] - run["xref_true"]
    out["track_rms"] = np.sqrt((err**2).mean(axis=1))
    last = max(T - idx(1.0, dt), 0)  # the last second of the record (the horizon for a complete run)
    out["precision"] = np.sqrt((err[:, last:] ** 2).mean(axis=1))
    # settling after the cue and after the turn (censored)
    for key, t_ev, tgt in (
        ("settle_cue", ev["cue"], cfg["task"]["x_target"]),
        ("settle_turn", ev["turn"], cfg["task"]["x_turn"]),
    ):
        res = settle_time(run, t_ev + cfg["task"]["ramp_s"] * 0.5, np.full((s, T), tgt))
        out[key], out[key + "_status"], out[key + "_window"], out[key + "_rmst"] = (
            res["time"],
            res["status"],
            res["window"],
            res["rmst"],
        )
    # push response
    if ev["pushes"]:
        t_push = ev["pushes"][0]
        i0 = idx(t_push, dt)
        base = run["com"][:, max(i0 - 5, 0)]
        win = run["com"][:, i0 : i0 + idx(1.5, dt)]
        out["peak_dev"] = np.abs(win - base[:, None]).max(axis=1)
        tgt = run["xref_true"]
        inside = (np.abs(run["com"] - tgt) < band(cfg)) & (np.abs(run["vcom"]) < VEL_BAND) & alive
        # the search starts at the time of the largest deviation, so a body that has not yet been moved by the push is not "recovered"
        i_peak = i0 + np.abs(win - base[:, None]).argmax(axis=1)
        res = time_to_hold(run, inside, t_push, window_end(ev, t_push), start_idx=i_peak)
        out["recovery"], out["recovery_status"], out["recovery_window"], out["recovery_rmst"] = (
            res["time"],
            res["status"],
            res["window"],
            res["rmst"],
        )
    else:
        out["peak_dev"] = np.full(s, np.nan)
        out["recovery"] = np.full(s, np.nan)
        out["recovery_status"] = np.full(s, "undefined", dtype=object)
        out["recovery_window"] = np.full(s, np.nan)
        out["recovery_rmst"] = np.full(s, np.nan)
    out["energy_used"] = run["energy"][:, 0] - run["energy"][:, -1]
    out["fatigue_end"] = run["fatigue"][:, -1]
    out["cc_mean"] = run["cc"].mean(axis=(1, 2))
    out["act_mean"] = run["act"].sum(axis=3).mean(axis=(1, 2))
    out["cop_rms"] = np.sqrt((run["cop"] ** 2).mean(axis=1))
    out["cop_range"] = run["cop"].max(axis=1) - run["cop"].min(axis=1)
    out["kc_end"] = run["kc"][:, -1]
    out["slip_frac"] = run["slip"].mean(axis=1)
    out["diverged"] = run.diverged.astype(float)
    for k, v in out.items():  # a numerically diverged run is not scored on anything
        if (
            k not in ("diverged",)
            and np.issubdtype(np.asarray(v).dtype, np.floating)
            and np.asarray(v).shape == run.diverged.shape
        ):
            out[k] = np.where(run.diverged, np.nan, v)
    return out


def declared_line_cost(run: Run, prefix: str = "xeno.") -> np.ndarray:
    """Per seed: the energy the operation lines whose id starts with ``prefix`` (the condition's own rule lines) were declared to cost
    while active (cost_per_s x active time, summed over those lines). Extra activity of the body's own lines is NOT counted: it is emergent.
    Part of ``energy_used`` by construction — a rise in energy use that equals it is the price written into the condition, not an
    emergent weakness."""
    out = np.zeros(run["com"].shape[0])
    for j, lid in enumerate(run.line_ids):
        ln = next(x for x in run.cfg["lines"] if x["id"] == lid)
        c = float((ln.get("resource") or {}).get("cost_per_s", 0.0))
        if c and lid.startswith(prefix):
            out += c * run["line_active"][:, :, j].sum(axis=1) * run.dt
    return out


def numeric_only(m: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """The numeric entries of a summary (the ``*_status`` entries are text)."""
    return {k: v for k, v in m.items() if np.issubdtype(np.asarray(v).dtype, np.number)}


# organization metrics used by the Fragility Transfer analysis: name -> (reference metric key, label)
ORGANIZATION = {
    "posture_stability": ("sway_rms", "posture stability (trunk sway, lower is better)"),
    "correction_quality": ("peak_dev", "correction quality (peak COM deviation after a push, lower is better)"),
    "turn_speed": ("settle_turn_rmst", "direction-change speed (settling time after the turn, lower is better)"),
    "precision": ("precision", "precision (COM error in the last second, lower is better)"),
    "fatigue_cost": ("energy_used", "fatigue / energy cost (energy used, lower is better)"),
    "recovery_time": ("recovery_rmst", "recovery time after a push (lower is better)"),
    "fall_rate": ("fall", "fall rate (lower is better)"),
}


def organization(run: Run) -> dict[str, np.ndarray]:
    m = summary(run)
    return {name: m[key] for name, (key, _) in ORGANIZATION.items()}
