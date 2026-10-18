"""Numerical verification of the body simulator: a-priori stability, time-step / integrator convergence, the eight-condition
matrix for both presets, and a diagnosis for user-edited configurations.

Failure modes are kept apart in every table:
* **physical fall**       the body leaves the recoverable range (segment angle or COM beyond the support) — a result;
* **numerical divergence** non-finite values, joint rates or torques far beyond any physical value — a failure of the numerics;
* **control instability** the closed loop oscillates with growing amplitude without leaving the range yet (reported as
  ``growth``: late-window COM sway divided by early-window sway);
* **not achieved in window** a recovery / settling that did not happen in the observation window (a censored observation).
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import config, engine, metrics, records
from .experiments import base_config

SUBSTEP_LEVELS = (1, 2, 4, 8)


def noiseless(cfg: dict[str, Any]) -> dict[str, Any]:
    """The same body without any random input (sensor and motor noise off) — for numerical studies, where the comparison must
    not be blurred by noise realisations that differ when the step changes."""
    out = copy.deepcopy(cfg)
    for k in ("proprio", "vestibular", "visual", "tactile"):
        out["sensors"][k]["noise"] = 0.0
    out["sensors"]["cue"]["noise"] = 0.0
    out["neural"]["motor_noise"] = 0.0
    out["internal"]["breath_variability"] = 0.0
    return config.validate(out)


def _rms(a: np.ndarray, b: np.ndarray) -> float:
    n = min(a.shape[-1], b.shape[-1])
    return float(np.sqrt(np.mean((a[..., :n] - b[..., :n]) ** 2)))


def _com_at(cfg: dict[str, Any], step_s: float = 0.01) -> tuple[np.ndarray, engine.Run]:
    r = engine.simulate(cfg, [1])
    stride = max(1, int(round(step_s / r.dt)))
    return r["com"][0, ::stride], r


def stability_table(preset: str) -> dict[str, Any]:
    """A-priori RK4 / Euler stability radii (passive plant) for a preset, co-contraction 0 .. CC_MAX."""
    cfg = base_config(preset)
    P = engine.Params(cfg)
    rows = []
    for integ in ("rk4", "semi-implicit-euler", "explicit-euler"):
        for cc in (0.0, 0.3, engine.CC_MAX):
            ns = P.numeric_stability(cc, integ)
            rows.append(
                [
                    preset,
                    integ,
                    cc,
                    P.dt,
                    P.substeps,
                    ns["margin"],
                    "stable" if ns["stable"] else "UNSTABLE",
                    ns["max_abs_lambda_h"],
                    ns["mass_matrix_condition"],
                ]
            )
    return {
        "columns": [
            "preset",
            "integrator",
            "co-contraction",
            "control dt s",
            "plant substeps",
            "spectral radius of the step matrix",
            "passive plant",
            "max |lambda| h",
            "condition number of M",
        ],
        "rows": rows,
    }


def convergence_study(preset: str) -> dict[str, Any]:
    """Noiseless runs of the short protocol. (a) plant sub-steps 1,2,4,8 against the finest; (b) integrators at the preset's
    sub-steps against RK4 at 8 sub-steps; (c) control step halved (delays kept in seconds) against the preset's step."""
    base = noiseless(base_config(preset))
    base["task"]["integrator"] = "rk4"
    ref_cfg = copy.deepcopy(base)
    ref_cfg["task"]["substeps"] = 8
    ref, _ = _com_at(ref_cfg)
    rows = []
    for sub in SUBSTEP_LEVELS[:-1]:
        c = copy.deepcopy(base)
        c["task"]["substeps"] = sub
        try:
            x, r = _com_at(c)
            rows.append(
                [
                    preset,
                    f"RK4, {sub} plant sub-step(s)",
                    base["task"]["dt"] / sub,
                    _rms(x, ref),
                    float(np.abs(x - ref[: len(x)]).max()),
                    "numerical divergence" if r.diverged.any() else ("fell" if r.fell.any() else "ok"),
                ]
            )
        except config.ConfigError as e:
            rows.append(
                [preset, f"RK4, {sub} plant sub-step(s)", base["task"]["dt"] / sub, None, None, "refused: " + str(e)[:80]]
            )
    for integ in ("semi-implicit-euler", "explicit-euler"):
        c = copy.deepcopy(base)
        c["task"]["integrator"] = integ
        try:
            x, r = _com_at(c)
            rows.append(
                [
                    preset,
                    f"{integ}, {c['task']['substeps']} plant sub-step(s)",
                    base["task"]["dt"] / c["task"]["substeps"],
                    _rms(x, ref),
                    float(np.abs(x - ref[: len(x)]).max()),
                    "numerical divergence" if r.diverged.any() else ("fell" if r.fell.any() else "ok"),
                ]
            )
        except config.ConfigError as e:
            rows.append(
                [
                    preset,
                    f"{integ}, {c['task']['substeps']} plant sub-step(s)",
                    base["task"]["dt"] / c["task"]["substeps"],
                    None,
                    None,
                    "refused by the stability check: " + str(e)[:60],
                ]
            )
    c = copy.deepcopy(base)
    c["task"]["dt"] = base["task"]["dt"] / 2
    try:
        x, r = _com_at(c)
        rows.append(
            [
                preset,
                "RK4, control step halved",
                c["task"]["dt"] / c["task"]["substeps"],
                _rms(x, ref),
                float(np.abs(x - ref[: len(x)]).max()),
                "numerical divergence" if r.diverged.any() else ("fell" if r.fell.any() else "ok"),
            ]
        )
    except config.ConfigError as e:
        rows.append([preset, "RK4, control step halved", None, None, None, "refused: " + str(e)[:80]])
    # the a-priori criterion against real runs, in both directions: configurations the check refuses are run anyway
    for label, edit in (
        ("RK4, 1 plant sub-step", {"substeps": 1}),
        ("semi-implicit Euler", {"integrator": "semi-implicit-euler"}),
        ("explicit Euler", {"integrator": "explicit-euler"}),
    ):
        c = copy.deepcopy(base)
        c["task"].update(edit)
        ns = engine.Params(c).numeric_stability(engine.CC_MAX)
        if ns["stable"]:
            continue
        r = engine.simulate(c, [1, 2, 3, 4], enforce_stability=False)
        hi = copy.deepcopy(c)
        hi["neural"]["cocontraction_base"] = 0.9  # the worst case the check covers
        r2 = engine.simulate(hi, [1, 2, 3, 4], enforce_stability=False)
        rows.append(
            [
                preset,
                f"{label} (refused by the check; forced to run, 4 seeds)",
                c["task"]["dt"] / c["task"]["substeps"],
                None,
                None,
                f"check (cc up to {engine.CC_MAX}): unstable, rho={ns['margin']:.2f}; nominal co-contraction run: diverged {int(r.diverged.sum())}/4, "
                f"fell {int(r.fell.sum())}/4; co-contraction 0.9 run: diverged {int(r2.diverged.sum())}/4, fell {int(r2.fell.sum())}/4",
            ]
        )
    return {
        "columns": [
            "preset",
            "variant",
            "plant step s",
            "RMS COM difference to reference (m)",
            "max COM difference (m)",
            "state",
        ],
        "rows": rows,
    }


# the eight conditions of the preset matrix: name -> function(cfg) -> cfg
def _cond_none(c):
    return c


def _cond_small(c):
    return config.apply_intervention(c, "perturbation", 25.0)


def _cond_large(c):
    return config.apply_intervention(c, "perturbation", 120.0)


def _cond_delay(c):
    return config.apply_intervention(c, "neural_delay", 0.06)


def _cond_resource(c):
    return config.apply_intervention(c, "resource_constraint", 0.7)


def _cond_contact(c):
    return config.apply_intervention(c, "contact_change", 0.5)


def _cond_noise(c):
    out = copy.deepcopy(c)
    for k in ("proprio", "vestibular", "tactile"):
        out["sensors"][k]["noise"] = out["sensors"][k]["noise"] * 4.0
    return config.validate(out)


def _cond_dt(c):
    out = copy.deepcopy(c)
    out["task"]["dt"] = out["task"]["dt"] / 2
    return config.validate(out)


CONDITIONS = [
    ("no disturbance", _cond_none, False),
    ("small disturbance (25 N, extra push)", _cond_small, True),
    ("large disturbance (120 N, extra push)", _cond_large, True),
    ("control delay +0.06 s", _cond_delay, False),
    ("resource constraint 0.7", _cond_resource, False),
    ("sensor noise x4", _cond_noise, False),
    ("contact condition 0.5", _cond_contact, False),
    ("control time step halved", _cond_dt, False),
]


def preset_matrix(preset: str, seeds: list[int], protocol: str = "short") -> dict[str, Any]:
    rows: list[list[Any]] = []
    for name, fn, _ in CONDITIONS:
        cfg = fn(base_config(preset, short=(protocol == "short"), push=(protocol == "short")))
        try:
            r = engine.simulate(cfg, seeds)
        except config.ConfigError as e:
            rows.append(
                [
                    preset,
                    protocol,
                    name,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "refused: " + str(e)[:90],
                ]
            )
            continue
        m = metrics.summary(r)
        T = r["com"].shape[1]
        a, b = slice(int(0.2 * T), int(0.45 * T)), slice(int(0.75 * T), T)
        early = np.nanstd(r["theta"][:, a, 2], axis=1)
        late = np.nanstd(r["theta"][:, b, 2], axis=1)
        growth = float(np.nanmedian(late / np.maximum(early, 1e-9)))
        st = m["recovery_status"]
        rows.append(
            [
                preset,
                protocol,
                name,
                len(seeds),
                float(r.fell.mean()),
                float(r.diverged.mean()),
                float(np.nanmax(np.abs(r["com"]))),
                float(np.nanmax(np.abs(r["theta"]))),
                float(np.nanmax(np.abs(r["omega"]))),
                float(np.nanmax(np.abs(r["tau"]))),
                float(np.nanmin(r["energy"])),
                float(np.nanmean(m["recovery_rmst"])) if np.isfinite(m["recovery_rmst"]).any() else None,
                float((st == "achieved").mean()),
                float(np.isfinite(m["settle_turn"]).mean()),
                growth,
                "ok",
            ]
        )
    cols = [
        "preset",
        "protocol",
        "condition",
        "seeds",
        "fall fraction (physical)",
        "numerical divergence fraction",
        "max |COM| m",
        "max |segment angle| rad",
        "max |angular rate| rad/s",
        "max |joint torque| Nm",
        "min energy",
        "recovery time, restricted mean s",
        "recovered in window (fraction)",
        "settled after the turn (fraction)",
        "late/early trunk sway growth",
        "state",
    ]
    return {"columns": cols, "rows": rows}


def diagnose(cfg: dict[str, Any], seeds: list[int] | None = None) -> dict[str, Any]:
    """Stability diagnosis of a (possibly user-edited) configuration: the a-priori check (what it guarantees and what not) and a
    short run-time probe. Never raises for an unstable configuration: it reports it."""
    cfg = config.validate(cfg)
    P = engine.Params(cfg)
    out: dict[str, Any] = {
        "a_priori": [P.numeric_stability(cc) for cc in (0.0, 0.3, engine.CC_MAX)],
        "guarantee": "The a-priori check covers the passive joint dynamics of the explicit step only. It does not cover feedback delays, "
        "gains or contact switching: a stable passive plant can still have an unstable closed loop. The probe below runs the "
        "configuration; it is evidence, not a proof.",
    }
    out["integrator_stable"] = all(x["stable"] for x in out["a_priori"])
    if not out["integrator_stable"]:
        out["probe"] = None
        out["verdict"] = "numerically unstable (refused to run)"
        return out
    probe = copy.deepcopy(cfg)
    probe["task"]["horizon"] = min(probe["task"]["horizon"], 4.0)
    probe["task"]["t_cue"] = min(probe["task"]["t_cue"], 1.0)
    probe["task"]["t_turn"] = min(probe["task"]["t_turn"], 3.0)
    r = engine.simulate(probe, seeds or [1, 2, 3, 4])
    T = r["com"].shape[1]
    early = np.nanstd(r["theta"][:, int(0.2 * T) : int(0.45 * T), 2], axis=1)
    late = np.nanstd(r["theta"][:, int(0.75 * T) :, 2], axis=1)
    growth = float(np.nanmedian(late / np.maximum(early, 1e-9)))
    out["probe"] = {
        "seeds": len(r.seeds),
        "fall_fraction": float(r.fell.mean()),
        "diverged_fraction": float(r.diverged.mean()),
        "late_over_early_sway": growth,
        "max_abs_torque_over_tau_max": float(np.nanmax(np.abs(r["tau"])) / float(max(j["tau_max"] for j in probe["joints"]))),
    }
    if out["probe"]["diverged_fraction"] > 0:
        out["verdict"] = "numerical divergence in the probe"
    elif out["probe"]["fall_fraction"] > 0.5:
        out["verdict"] = "the body falls in the probe (physical fall or an unstable control loop; see sway growth)"
    elif growth > 3.0:
        out["verdict"] = "growing oscillation: the closed loop looks unstable"
    else:
        out["verdict"] = "no instability seen in the probe"
    return out


def run_all(seeds: list[int], presets: tuple[str, ...] = ("human-like-planar", "machine-like-planar")) -> dict[str, Any]:
    tables = []
    for p in presets:
        st = stability_table(p)
        tables.append({"name": f"stability_{p}", "title": f"A-priori stability of the passive plant ({p})", **st})
        cv = convergence_study(p)
        tables.append({"name": f"convergence_{p}", "title": f"Time-step and integrator convergence, noiseless ({p})", **cv})
    cols, rows = None, []
    for p in presets:
        for proto in ("default", "short"):
            pm = preset_matrix(p, seeds, proto)
            cols = pm["columns"]
            rows += pm["rows"]
    tables.append(
        {"name": "preset_matrix", "title": "Eight conditions x two presets x two protocols", "columns": cols, "rows": rows}
    )
    return {"tables": tables, "bands": metrics.TOLERANCE, "seeds": seeds}


def make_record(seeds: list[int] | None = None) -> dict[str, Any]:
    seeds = seeds or [metrics.FINAL_SEED_BASE + i for i in range(12)]
    res = run_all(seeds)
    return records.make_record(
        "V",
        {"seeds": seeds},
        seeds,
        base_config("human-like-planar"),
        [],
        [{"condition": n} for n, _, _ in CONDITIONS],
        res,
        [],
        [],
        {"reentry": []},
        0.01,
    )
