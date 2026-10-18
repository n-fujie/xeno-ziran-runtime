"""Experiment G — Directional Fragility Transfer (an independent check of the Fragility Transfer proposition).

Question: when a Xeno-14 condition strengthens one bodily operation, does it weaken another, in the same configuration — measured
by more than falls? Each condition is run against the matched control (same seeds, same protocol: common random numbers) on

  posture            trunk sway in quiet standing; peak COM deviation after a forward push met at rest
  direction          disturbance tolerance forwards and backwards (how many rungs of a force ladder are survived), and the recovery region
                     (how many rungs are recovered from inside the window)
  timing             movement-correction latency (push met at rest); settling after the later direction change (restricted mean, censored)
  resource           energy used beyond the condition's own declared line cost; steps with two lines driving a joint in opposite directions;
                     time with actuators saturated
  availability       baseline operation lines that stopped igniting although they ignite in the control
  reachability       whether a later operation (the direction change) is still established after the protocol's disturbance

The ladder pushes are met at rest (before any cue): all conditions are in the same state when the push comes. Measures that need
the cue (settling, reachability, resources, lines) come from the full protocol run.

A *transfer* is recorded when one group improves and a different group worsens, or when the tolerance improves in one direction and
worsens in the other — each under the Benjamini-Hochberg q < 0.05 over the whole table and |d| >= 0.8, both fixed in advance. It is
reported whether any body fell (a transfer without falls is possible) and whether the worsened group is one the principle's
definition names. For principles with a rule line, an *ablation* run (the same parameter edits, the rule line switched off) separates the
line's contribution from the edits'. Falls alone are never taken as a transfer. Nothing about the sign of any effect is assumed.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import engine, metrics, records, stats, tro, velocity, xeno14

LADDER = [30.0, 60.0, 90.0]  # N, per direction
EFFECT_Q, EFFECT_D = 0.05, 0.8
GROUPS = {
    "posture": ["posture_sway", "peak_dev_forward"],
    "direction": ["tolerance_forward", "tolerance_backward", "recovery_region"],
    "timing": ["correction_latency", "turn_settling_after_push"],
    "resource": ["energy_beyond_declared", "line_conflicts", "actuator_saturation"],
    "availability": ["silenced_lines"],
    "reachability": ["turn_not_established"],
}
METRIC_GROUP = {m: g for g, ms in GROUPS.items() for m in ms}
LABELS = {
    "posture_sway": "trunk sway in quiet standing",
    "peak_dev_forward": "peak COM deviation after a forward push at rest (60 N)",
    "tolerance_forward": "forward disturbance tolerance (rungs not survived)",
    "tolerance_backward": "backward disturbance tolerance (rungs not survived)",
    "recovery_region": "recovery region (rungs not recovered from inside the window, both directions)",
    "correction_latency": "movement-correction latency after a forward push at rest",
    "turn_settling_after_push": "settling after the direction change (restricted mean)",
    "energy_beyond_declared": "energy used beyond the condition's declared line cost",
    "line_conflicts": "line conflicts (steps per s)",
    "actuator_saturation": "time with a muscle drive saturated",
    "silenced_lines": "baseline lines that stopped igniting",
    "turn_not_established": "direction change not established after the protocol push (0/1 per seed)",
}


REST_PUSH_T = 0.8


def _ladder_cfg(base: dict[str, Any], force: float) -> dict[str, Any]:
    """A push while standing at rest, before any cue: every condition meets the push in the same state (no movement under way), so
    differences in what the push does are not differences in what the body was doing when it came."""
    c = copy.deepcopy(base)
    c["environment"]["pushes"] = [{"t": REST_PUSH_T, "dur": 0.12, "force": force, "link": 2, "point_frac": 0.8}]
    c["task"].update({"horizon": 3.4, "t_cue": 3.6, "t_turn": 3.9})  # the cue never comes inside the record
    return c


def _survived(runs: list[engine.Run]) -> tuple[np.ndarray, np.ndarray]:
    """Per seed: rungs survived (no fall before the first fall, counted from the bottom) and rungs recovered inside the window."""
    fell = np.stack([r.fell | r.diverged for r in runs])  # (L, S)
    rec = np.stack([np.isfinite(metrics.summary(r)["recovery"]) for r in runs])
    survived = np.cumprod(~fell, axis=0).sum(axis=0).astype(float)
    return survived, rec.sum(axis=0).astype(float)


def condition_metrics(
    cfg: dict[str, Any], base_run: engine.Run, fwd: list[engine.Run], bwd: list[engine.Run], control_activity: np.ndarray | None
) -> dict[str, np.ndarray]:
    m = metrics.summary(base_run)
    L = len(LADDER)
    s_f, r_f = _survived(fwd)
    s_b, r_b = _survived(bwd)
    mid = fwd[len(LADDER) // 2]  # the middle rung, forward, at rest
    mm = metrics.summary(mid)
    i_push = metrics.idx(REST_PUSH_T, mid.dt)
    corr = velocity.onset(mid["tau"][:, :, 0], i_push, mid.dt, 5.0, direction=-1, end=i_push + metrics.idx(1.5, mid.dt))
    net = base_run["act"][:, :, :, 0] - base_run["act"][:, :, :, 1]
    sat = (np.abs(net) >= 0.98).any(axis=2).mean(axis=1)
    excess = m["energy_used"] - metrics.declared_line_cost(base_run)
    turn_established = np.isfinite(m["settle_turn"]).astype(float)
    act = np.array(
        [base_run["line_active"][:, :, j].mean(axis=1) for j, lid in enumerate(base_run.line_ids) if not lid.startswith("xeno.")]
    ).T
    silenced = np.zeros(act.shape[0])
    if control_activity is not None:
        baseline_active = control_activity.mean(axis=0) >= 0.05
        silenced = ((act < 0.2 * control_activity.mean(axis=0)[None]) & baseline_active[None]).sum(axis=1).astype(float)
    return {
        "posture_sway": m["sway_rms"],
        "peak_dev_forward": mm["peak_dev"],
        "tolerance_forward": L - s_f,
        "tolerance_backward": L - s_b,
        "recovery_region": 2 * L - (r_f + r_b),
        "correction_latency": corr,
        "turn_settling_after_push": m["settle_turn_rmst"],
        "energy_beyond_declared": excess,
        "line_conflicts": tro._conflicts(base_run),
        "actuator_saturation": sat,
        "silenced_lines": silenced,
        "turn_not_established": 1.0 - turn_established,
    }


def _activity(run: engine.Run) -> np.ndarray:
    return np.array(
        [run["line_active"][:, :, j].mean(axis=1) for j, lid in enumerate(run.line_ids) if not lid.startswith("xeno.")]
    ).T


def _line_off(cfg: dict[str, Any], pid: str) -> dict[str, Any] | None:
    lid = f"xeno.{pid}"
    out = copy.deepcopy(cfg)
    hit = False
    for ln in out["lines"]:
        if ln["id"] == lid:
            ln["enabled"] = False
            hit = True
    return out if hit else None


def exp_G(params: dict[str, Any], base_config, seeds_for, Ctx, ExperimentError, table, decimated_series):
    preset = params.get("preset", "human-like-planar")
    seeds = seeds_for(params, 12)
    ids = list(params.get("principles") or [p["id"] for p in xeno14.PRINCIPLES])
    for i in ids:
        if i not in xeno14.BY_ID:
            raise ExperimentError(f"unknown principle {i!r}")
    ablate = bool(params.get("ablate", True))
    base = base_config(preset)
    ablations = {pid: _line_off(xeno14.apply(base, [pid]), pid) for pid in ids} if ablate else {}
    n_cond = 1 + len(ids) + sum(1 for v in ablations.values() if v is not None)
    ctx = Ctx(n_cond * (1 + 2 * len(LADDER)), params.get("carry_over"))

    def one(cfg: dict[str, Any], label: str, ctrl_act: np.ndarray | None):
        b = yield from ctx.sim(cfg, seeds, None, f"{label}: protocol")
        fwd, bwd = [], []
        for f in LADDER:
            fwd.append((yield from ctx.sim(_ladder_cfg(cfg, f), seeds, None, f"{label}: +{f:.0f} N")))
        for f in LADDER:
            bwd.append((yield from ctx.sim(_ladder_cfg(cfg, -f), seeds, None, f"{label}: -{f:.0f} N")))
        return (
            b,
            condition_metrics(cfg, b, fwd, bwd, ctrl_act),
            {
                "falls_protocol": float((b.fell | b.diverged).mean()),
                "falls_ladder": float(np.mean([(r.fell | r.diverged).mean() for r in fwd + bwd])),
            },
        )

    cb, cmx, cinfo = yield from one(base, "control", None)
    c_act = _activity(cb)
    results: dict[str, dict[str, np.ndarray]] = {}
    infos: dict[str, dict[str, float]] = {}
    ign: dict[str, float | None] = {}
    for pid in ids:
        cfg = xeno14.apply(base, [pid])
        b, mx, info = yield from one(cfg, pid, c_act)
        results[pid], infos[pid] = mx, info
        lid = f"xeno.{pid}"
        ign[pid] = float(b["line_active"][:, :, b.line_ids.index(lid)].any(axis=1).mean()) if lid in b.line_ids else None
    abl: dict[str, dict[str, np.ndarray]] = {}
    for pid, acfg in ablations.items():
        if acfg is not None:
            _, mx, _ = yield from one(acfg, f"{pid} (line off)", c_act)
            abl[pid] = mx
    names = list(cmx)
    effs = {(pid, k): stats.paired_effect(cmx[k], results[pid][k]) for pid in ids for k in names}
    keys = list(effs)
    q = dict(zip(keys, stats.bh_adjust(np.array([effs[k]["p"] for k in keys])), strict=True))

    def lab(e, qq):
        if not (np.isfinite(qq) and np.isfinite(e["d"])):
            return "undefined"
        if qq < EFFECT_Q and abs(e["d"]) >= EFFECT_D:
            return "improved" if e["d"] < 0 else "worsened"
        return "no detectable effect"

    rows: list[list[Any]] = []
    matrix: dict[str, dict[str, Any]] = {}
    for pid in ids:
        matrix[pid] = {}
        for k in names:
            e = effs[(pid, k)]
            L = lab(e, q[(pid, k)])
            line_part = None
            if pid in abl:
                ea = stats.paired_effect(cmx[k], abl[pid][k])
                line_part = (
                    None
                    if not np.isfinite(ea["mean_diff"]) or not np.isfinite(e["mean_diff"])
                    else float(e["mean_diff"] - ea["mean_diff"])
                )
            matrix[pid][k] = {
                "group": METRIC_GROUP[k],
                "d": _s(e["d"]),
                "p": _s(e["p"]),
                "q": _s(q[(pid, k)]),
                "label": L,
                "mean_control": _s(e["mean_a"]),
                "mean": _s(e["mean_b"]),
                "n": e["n"],
                "dropped": e["dropped"],
                "effect_of_the_rule_line": line_part,
            }
            rows.append(
                [
                    pid,
                    METRIC_GROUP[k],
                    LABELS[k],
                    matrix[pid][k]["mean_control"],
                    matrix[pid][k]["mean"],
                    matrix[pid][k]["d"],
                    matrix[pid][k]["p"],
                    matrix[pid][k]["q"],
                    L,
                    line_part,
                    ign[pid],
                ]
            )
    transfers, negative = [], []
    for pid in ids:
        imp = {k: matrix[pid][k] for k in names if matrix[pid][k]["label"] == "improved"}
        wor = {k: matrix[pid][k] for k in names if matrix[pid][k]["label"] == "worsened"}
        gi, gw = {METRIC_GROUP[k] for k in imp}, {METRIC_GROUP[k] for k in wor}
        cross = [(a, b) for a in sorted(gi) for b in sorted(gw) if a != b]   # sorted: set order differs between processes
        directional = ("tolerance_forward" in imp and "tolerance_backward" in wor) or (
            "tolerance_backward" in imp and "tolerance_forward" in wor
        )
        named = set(xeno14.BY_ID[pid]["acts_on"])
        if cross or directional:
            transfers.append(
                {
                    "principle": pid,
                    "improved": sorted(imp),
                    "worsened": sorted(wor),
                    "group_pairs": cross,
                    "directional": directional,
                    "falls_in_any_condition_run": infos[pid]["falls_protocol"] > 0
                    or infos[pid]["falls_ladder"] > cinfo["falls_ladder"],
                    "worsened_groups_named_by_the_definition": sorted(g for g in gw if any(o.startswith(g[:4]) for o in named)),
                    "ablation_available": pid in abl,
                    "line_accounts_for": {k: matrix[pid][k]["effect_of_the_rule_line"] for k in wor} if pid in abl else None,
                }
            )
        elif not imp and not wor:
            if ign[pid] == 0.0:
                negative.append(
                    {
                        "statement": f"{pid}: its rule never ignited in the protocol; no effect could occur",
                        "evidence": {"ignition": 0.0},
                    }
                )
            else:
                negative.append(
                    {
                        "statement": f"{pid}: no detectable effect on any group (BH q < {EFFECT_Q}, |d| >= {EFFECT_D}, {len(seeds)} seeds)",
                        "evidence": {"ignition": ign[pid]},
                    }
                )
        elif imp and not wor:
            negative.append(
                {
                    "statement": f"{pid}: improved {sorted(imp)} without a detectable weakening elsewhere (no Fragility Transfer)",
                    "evidence": {},
                }
            )
        elif wor and not imp:
            negative.append({"statement": f"{pid}: only worsened {sorted(wor)}; nothing improved", "evidence": {}})
    tables = [
        table(
            "effects",
            "Paired effect of each condition on each measure (lower is better for all)",
            [
                "principle",
                "group",
                "measure",
                "control mean",
                "condition mean",
                "d (paired)",
                "p",
                "q (BH)",
                "label",
                "of which the rule line (mean, vs ablation)",
                "ignition of the rule line",
            ],
            rows,
        ),
        table(
            "transfers",
            "Fragility Transfers: one group improves while another weakens, or one direction improves while the other weakens",
            ["principle", "improved", "worsened", "directional", "falls involved", "ablation available"],
            [
                [
                    t["principle"],
                    ", ".join(t["improved"]),
                    ", ".join(t["worsened"]),
                    t["directional"],
                    t["falls_in_any_condition_run"],
                    t["ablation_available"],
                ]
                for t in transfers
            ],
        ),
    ]
    res = {
        "tables": tables,
        "matrix": matrix,
        "transfers": transfers,
        "groups": GROUPS,
        "ladder_N": LADDER,
        "control": {k: _s(float(np.nanmean(v))) for k, v in cmx.items()},
        "design": {
            **stats.design_note(len(seeds)),
            "label_rule": f"BH q < {EFFECT_Q} over {len(keys)} tests and |d| >= {EFFECT_D}; falls alone are not a transfer",
        },
        "ignition": ign,
        "series": {"control_com": decimated_series(cb, "com")},
        "reading": "Conditions are compared with the matched control on identical seeds. 'No detectable effect' is not 'no effect' (see design.min_detectable_dz).",
    }
    rec = records.make_record(
        "G",
        {**params, "preset": preset, "principles": ids, "ablate": ablate},
        seeds,
        base,
        [],
        [{"xeno14": [i]} for i in ids],
        res,
        negative,
        [],
        {"reentry": []},
        base["task"]["dt"],
    )
    return rec, cb.slow_end


def _s(x: float) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)
