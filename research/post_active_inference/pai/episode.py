"""One run: world + perturbation schedule + controller + tracker (+ ground-truth probes) → a compact record.

Phases (steps; set in the config):

    0 … warmup             no actions (transient: activity ramps up and the connection pool saturates near
                           t ≈ 1000 in the default world, so control starts in the saturated steady state)
    warmup … calib_end     calibration: a seeded random action sequence (identical for every controller of a seed),
                           used to fit the comparator's A/B and the model-light controller's effect table
    calib_end … t_p        control, pre-perturbation (baseline for every score)
    t_p … t_r              perturbation phase (hooks: onset, per_step, per_decision)
    t_r … horizon          recovery / reconfiguration phase (revert hook; permanent perturbations are not reverted)

Decisions happen every ``world.dt`` steps (dt itself is perturbable). Every run returns ``status`` and a failure
category; nothing is discarded.
"""
from __future__ import annotations

import math
import time
import traceback

import numpy as np

from . import controllers as C
from .perturbations import ALIASES, REGISTRY, ctx_for
from .tracker import OperationalTracker, sensor_only_detection
from .world import ACTIONS, N_LEVELS, BenchWorld, WorldConfig, aggregate, level_of, probe, setpoint

PHASES = {"warmup": 1000, "calib_end": 3000, "t_p": 3200, "t_r": 3700, "horizon": 4200}


def _probe_at(ph: dict) -> dict:
    """Ground-truth probes: 50 steps before onset, three points across the perturbation phase (policy identity can
    change within the phase, e.g. under drift), mid recovery phase."""
    L = ph["t_r"] - ph["t_p"]
    return {"pre": ph["t_p"] - 50, "p1": ph["t_p"] + L // 4, "mid": ph["t_p"] + L // 2, "p3": ph["t_p"] + 3 * L // 4,
            "post": (ph["t_r"] + ph["horizon"]) // 2}


def resolve(key: str | None):
    if key is None:
        return None
    return REGISTRY[ALIASES.get(key, key)]


def run_episode(world_cfg: dict, seed: int, pert: str | None, severity: float, controller: str,
                phases: dict | None = None, probes: bool = False, trace: bool = True) -> dict:
    ph = {**PHASES, **(phases or {})}
    t0 = time.time()
    rec: dict = {"seed": seed, "perturbation": pert, "severity": severity, "controller": controller,
                 "status": "ok", "failure": None}
    try:
        _run(rec, WorldConfig.from_dict(world_cfg), seed, resolve(pert) if severity > 0 else None, severity,
             controller, ph, probes, trace)
    except FloatingPointError as e:
        rec.update(status="failed", failure={"category": "numerical_failure", "error": repr(e)[:300]})
    except Exception as e:  # noqa: BLE001 - classified, never discarded
        tb = traceback.format_exc()
        cat = "simulator_failure" if "/xzr/" in tb.splitlines()[-3] or "engine" in tb else "benchmark_failure"
        rec.update(status="failed", failure={"category": cat, "error": repr(e)[:300], "trace": tb[-1500:]})
    rec["wall_s"] = round(time.time() - t0, 2)
    return rec


_PREFIX: dict = {}


def _prefix(wcfg: WorldConfig, seed: int, boundary: bool, ph: dict) -> dict:
    """Warm-up + calibration (identical for every controller and perturbation of a seed): simulated once per
    process and deep-copied for every run. Bit-identical to simulating it inside each run (tested)."""
    import copy
    import json
    key = json.dumps([wcfg.__dict__, seed, boundary, ph], sort_keys=True, default=str)
    if key not in _PREFIX:
        world = BenchWorld(wcfg, seed, boundary=boundary)
        tracker = OperationalTracker(world)
        cal_rng = np.random.default_rng(seed * 7 + 1)
        calib = {"readings": [], "true": [], "actions": [], "x": []}
        rows: list[dict] = []
        next_dec, last_dt = ph["warmup"], world.dt
        while world.t < ph["calib_end"]:
            t = world.t
            if t >= next_dec:
                x = world.sensors.read(world.ring, world.filled)
                tl = world.true_level(last_dt)
                a = int(cal_rng.integers(len(ACTIONS)))
                calib["readings"].append(aggregate(x))
                calib["true"].append(tl)
                calib["actions"].append(a)
                calib["x"].append(x.tolist())
                world.act(a)
                rows.append(_row(world, t, x, tl, None, a, a, last_dt))
                last_dt, next_dec = world.dt, t + world.dt
            world.step()
        true_edges = _true_edges(calib["true"])
        r = np.asarray(calib["readings"], float)
        xs = np.asarray(calib["x"], float)
        summary = {"readings": r.tolist(), "reading_sd": float(np.nanstd(xs)),
                   "reading_range": float(np.nanmax(r) - np.nanmin(r)),
                   "reading_iqr": float(np.subtract(*np.nanpercentile(r, [75, 25]))),
                   "true_edges": true_edges.tolist(), "true_median": float(np.median(calib["true"])),
                   "true_centres": [float(np.quantile(calib["true"], (k + 0.5) / N_LEVELS)) for k in range(N_LEVELS)],
                   "levels": [level_of(v, true_edges) for v in calib["true"]], "actions": calib["actions"]}
        if len(_PREFIX) >= 2:
            _PREFIX.clear()
        _PREFIX[key] = {"world": world, "tracker": tracker, "calib": summary, "rows": rows, "next_dec": next_dec,
                        "last_dt": last_dt}
    return copy.deepcopy(_PREFIX[key])


def _row(world, t, x, tl, s_true, a, ea, last_dt) -> dict:
    return {"t": t, "x": [round(float(v), 5) if np.isfinite(v) else None for v in x], "agg": aggregate(x),
            "true": tl, "s": s_true, "a": a, "ea": ea, "dt": world.dt,
            "N": world.activity(world.N, last_dt), "halves": [world.activity(h, last_dt) for h in world.halves],
            "quarters": [world.activity(q, last_dt) for q in world.quarters]}


def _run(rec, wcfg, seed, P, sev, spec, ph, probes, trace) -> None:
    b = _prefix(wcfg, seed, not spec.endswith("no_boundary"), ph)
    world, tracker, rows = b["world"], b["tracker"], b["rows"]
    rec["calib"] = b["calib"]
    true_edges = np.asarray(b["calib"]["true_edges"])
    ctrl = C.make(spec, seed)
    ctrl.calibrate({"readings": b["calib"]["readings"], "actions": b["calib"]["actions"],
                    "levels": b["calib"]["levels"]})
    ctx = None
    probe_out: dict = {}
    next_dec, last_dt = b["next_dec"], b["last_dt"]
    while world.t < ph["horizon"]:
        t = world.t
        # perturbation schedule
        if P is not None:
            if t == ph["t_p"]:
                tracker.mark_edges(t)
                ctx = ctx_for(P.key, seed, rec["calib"])
                P.onset(world, sev, ctx)
            if ph["t_p"] <= t < ph["t_r"] and P.per_step is not None:
                P.per_step(world, sev, ctx)
            if t == ph["t_r"]:
                tracker.mark_edges(t)
                if P.revert is not None:
                    P.revert(world, sev, ctx)
        elif t in (ph["t_p"], ph["t_r"]):
            tracker.mark_edges(t)
        if probes and t in _probe_at(ph).values():
            probe_out[next(k for k, v in _probe_at(ph).items() if v == t)] = probe(world)
        if t >= next_dec:
            if P is not None and ctx is not None and ph["t_p"] <= t < ph["t_r"] and P.per_decision is not None:
                P.per_decision(world, sev, ctx, t)
            x = world.sensors.read(world.ring, world.filled)
            tl = world.true_level(last_dt)
            s_true = level_of(tl, true_edges)
            goal = setpoint(t, ph["calib_end"])
            a = ctrl.decide(x, s_true, t, goal)
            ea = world.act(a)
            rows.append(_row(world, t, x, tl, s_true, a, ea, last_dt) | {"goal": goal})
            last_dt, next_dec = world.dt, t + world.dt
        world.step()
        if not np.isfinite(world.state.diff).all():
            raise FloatingPointError(f"non-finite runtime state at t={world.t}")
    footprint = list(ctx["footprint"]) if ctx is not None else []
    tr = tracker.finalize(ph["t_p"], ph["t_r"], footprint, pre_from=ph["calib_end"])
    from metrics import (
        channel_auc,
        episode_metrics,  # top-level module of the benchmark (research/post_active_inference)
    )
    m = episode_metrics(rows, ctrl, tr, ph, rec["calib"], P, sev, ctx)
    cs = m.pop("_channel_score", None)
    m["channel_localisation_auc"] = channel_auc(cs, world.sensors.base_channels, wcfg.n, footprint) \
        if cs is not None and footprint else None
    rec["metrics"] = m
    rec["tracker"] = {k: v for k, v in tr.items() if not k.startswith("_")}
    rec["tracker_sensor_only"] = sensor_only_detection(
        [{"t": r["t"], "x": [np.nan if v is None else v for v in r["x"]]} for r in rows], ph["t_p"], ph["t_r"], pre_from=ph["calib_end"])
    rec["profiles"] = _profiles(tr, world, ph, ctx)
    rec["probes"] = probe_out
    rec["side"] = P.side if P is not None else None
    rec["perturbation_info"] = _ctx_info(ctx)
    rec["controller_summary"] = ctrl.summary()
    rec["calib"] = {k: v for k, v in rec["calib"].items() if k != "readings"}
    if trace:
        rec["trace"] = _trace(rows, ctrl)


def _true_edges(true: list[float]) -> np.ndarray:
    x = np.asarray(true, float)
    e = np.quantile(x, np.linspace(0, 1, N_LEVELS + 1)[1:-1])
    for i in range(1, len(e)):
        if e[i] <= e[i - 1]:
            e[i] = e[i - 1] + 1e-9
    return e


def _profiles(tr: dict, world, ph: dict, ctx) -> dict:
    """Per-configuration mean activity of T (and the migration destination) per phase, for pattern recurrence."""
    A, t = tr["_A"], tr["_t"]

    def prof(lo, hi, nodes):
        m = (t > lo) & (t <= hi)
        return A[m][:, nodes].mean(0) if m.any() else None

    T = world.T
    pre = prof(ph["t_p"] - 100, ph["t_p"], T)
    out = {"T_pre_vs_rec": _corr(pre, prof(ph["t_r"], ph["t_r"] + 100, T)),
           "T_pre_vs_pert": _corr(pre, prof(ph["t_p"], ph["t_p"] + 100, T))}
    if ctx is not None and "dest" in ctx and "mem_sel" in ctx:
        sel = np.asarray(ctx["mem_sel"], int)
        dest = np.asarray(ctx["dest"], int)
        k = min(len(sel), len(dest))
        if k >= 3:
            a = prof(ph["t_p"] - 100, ph["t_p"], sel[:k])
            out["migration_dest_corr"] = _corr(a, prof(ph["t_p"], ph["t_p"] + 100, dest[:k]))
            out["migration_dest_corr_pre"] = _corr(a, prof(ph["t_p"] - 100, ph["t_p"], dest[:k]))
    return out


def _corr(a, b) -> float | None:
    if a is None or b is None or len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _ctx_info(ctx) -> dict:
    if ctx is None:
        return {}
    out = {"footprint_size": len(ctx["footprint"])}
    for k in ("period", "connect_failed", "hubs", "relocated"):
        if k in ctx:
            out[k] = ctx[k]
    if "changes" in ctx:
        out["changes"] = len(ctx["changes"])
    return out


def _r(x, d=4):
    if x is None:
        return None
    if isinstance(x, float):
        return round(x, d) if math.isfinite(x) else None
    return x


def _trace(rows: list[dict], ctrl) -> dict:
    """Per-decision trace (control phase), compact."""
    h = {r["t"]: r for r in getattr(ctrl, "hist", [])}
    cols: dict[str, list] = {k: [] for k in ("t", "agg", "true", "s", "a", "ea", "dt", "F", "G", "surprise", "o", "pred_reading")}
    for r in rows:
        if r["s"] is None:
            continue
        c = h.get(r["t"], {})
        for k in ("t", "agg", "true", "s", "a", "ea", "dt"):
            cols[k].append(_r(r[k]))
        for k in ("F", "G", "surprise", "o", "pred_reading"):
            cols[k].append(_r(c.get(k)))
    return cols
