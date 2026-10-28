"""MEOS-0, fourth stage: the research readings of a run — operational paths, XenoBody boundary perturbations, Address Domain intervention effects, the per-run log and the
SSS region of one point.

Every function runs the real engine (seeded, deterministic) or reads a record it produced; nothing here feeds back into a run, so none of it can change a digest. What a
path, a boundary or a region *is* in this model is stated beside the number: the operational paths are groupings of the engine's components and traces, not new mechanisms.
Operational state, observed state and observability status stay three separate fields throughout (see ``analysis.observe``).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any

import numpy as np

from . import analysis as A
from . import engine as E
from . import experiments as X

# ---------------------------------------------------------------------------------------------------- operational paths
# A path is the route along which one kind of thing moves between the configurations and their environment. Its components are engine components (the things an
# intervention can remove), its signal an engine trace (what actually moved). ``resource`` and ``recovery`` share the renewal components: recovery is the path along which
# a collapsed operation is restored (renewal, the feedback to the source, the power reserve), resource the path along which material flows in normal operation.
PATHS: dict[str, dict[str, Any]] = {
    "resource": {
        "label": "resource path",
        "components": ["resource_gradient", "feedback", "resource_renewal"],
        "signal": "resource_flow",
        "means": "material moving from the source field to the configurations and back (trace resource_flow)",
    },
    "coupling": {
        "label": "coupling path",
        "components": ["interaction_channel"],
        "signal": "interaction_strength",
        "means": "A1's alteration of the environment reaching A2 (trace interaction_strength)",
    },
    "history_access": {
        "label": "history-access path",
        "components": ["history"],
        "signal": "history_contribution",
        "means": "recorded traces re-entering the next firing as a threshold reduction (traces history_contribution_a1 + _a2)",
    },
    "observation": {
        "label": "observation path",
        "components": ["sensor_resource", "sensor_alteration"],
        "signal": "differentiated",
        "means": "the differentiated stimulus each configuration senses (traces a1_differentiated, a2_differentiated); not the research observer",
    },
    "recovery": {
        "label": "recovery path",
        "components": ["resource_renewal", "feedback"],
        "signal": "renewal",
        "means": "renewal events, material returned to the source and the power reserve rising (traces renewal_events, resource_renewed, power_balance)",
    },
}
BOUNDARY_KINDS = ("observation", "coupling", "resource_exchange", "history_access", "address_domain")


def _signal(T: dict, name: str) -> np.ndarray:
    def arr(k: str) -> np.ndarray:
        return np.array([0.0 if v is None else float(v) for v in T[k]])

    if name == "history_contribution":
        return arr("history_contribution_a1") + arr("history_contribution_a2")
    if name == "differentiated":
        return np.maximum(arr("a1_differentiated"), 0.0) + np.maximum(arr("a2_differentiated"), 0.0)
    if name == "renewal":
        return arr("renewal_events") + arr("resource_renewed") + np.maximum(arr("power_balance"), 0.0)
    return np.abs(arr(name))


def component_presence(rec: dict) -> dict[str, list[tuple[int, bool]]]:
    """Per component, the ticks at which it was cut (False) or restored (True), from the intervention log. A component never mentioned is present throughout."""
    out: dict[str, list[tuple[int, bool]]] = {}
    for iv in rec["intervention_log"]:
        if iv["op"] in ("REMOVE", "ISOLATE"):
            out.setdefault(iv["target"], []).append((iv["tick"], False))
        elif iv["op"] == "RECONNECT":
            out.setdefault(iv["target"], []).append((iv["tick"], True))
    return out


def _present(timeline: list[tuple[int, bool]] | None, t: int) -> bool:
    ok = True
    for tick, state in sorted(timeline or []):
        if tick <= t:
            ok = state
    return ok


def path_activity(rec: dict) -> dict:
    """Per operational path: its components, the tick-by-tick signal (as measured), the intervals in which a component was cut or the signal was quiet, and a summary."""
    T = rec["traces"]
    n = len(T["t"])
    pres = component_presence(rec)
    out: dict[str, Any] = {}
    for key, p in PATHS.items():
        sig = _signal(T, p["signal"])
        top = float(sig.max()) if len(sig) else 0.0
        norm = (sig / top) if top > 0 else sig
        cut_ticks = [t for t in range(n) if any(not _present(pres.get(c), t) for c in p["components"])]
        state = ["cut" if t in set(cut_ticks) else ("active" if norm[t] > 0.05 else "quiet") for t in range(n)]
        intervals: list[dict[str, Any]] = []
        start = 0
        for t in range(1, n + 1):
            if t == n or state[t] != state[start]:
                intervals.append({"from": start, "to": t - 1, "state": state[start]})
                start = t
        out[key] = {
            "label": p["label"],
            "components": p["components"],
            "means": p["means"],
            "signal_name": p["signal"],
            "peak": round(top, 5),
            "mean": round(float(sig.mean()), 5) if n else 0.0,
            "active_ticks": int(sum(1 for s in state if s == "active")),
            "cut_ticks": len(cut_ticks),
            "series": [round(float(v), 4) for v in norm],
            "state_intervals": intervals,
        }
    return out


# ---------------------------------------------------------------------------------------------------- the three bodies and the legs
def _bodies(affected: list[str]) -> dict[str, Any]:
    """For B1 / B2 / B3: which affected components lie inside the body, which legs of the recursion lie wholly inside it, and which of those legs the perturbation breaks."""
    out = {}
    for key, part in A.PARTITIONS.items():
        body = list(part["components"])
        inside = A.legs_inside(body)
        broken = [leg for leg, needs in A.LEGS.items() if inside[leg] and any(c in affected for c in needs)]
        out[key] = {
            "label": part["label"],
            "components": body,
            "affected_inside": [c for c in affected if c in body],
            "affected_outside": [c for c in affected if c not in body],
            "legs_closed": [leg for leg, ok in inside.items() if ok],
            "legs_closed_count": sum(inside.values()),
            "legs_broken_by_perturbation": broken,
            "legs_total": len(A.LEGS),
        }
    return out


# ---------------------------------------------------------------------------------------------------- boundary perturbation
def _perturbation(kind: str, tick: int, duration: int, params: dict) -> dict:
    end = tick + duration
    if kind == "observation":
        region = params.get("region") or [0, 0, 2, 13]
        return {
            "ivs": [],
            "restore": [],
            "observation": {"region": region},
            "affected": [],
            "label": f"observation boundary: the observer's region {region}",
        }
    if kind == "coupling":
        return {
            "ivs": [{"tick": tick, "op": "ISOLATE", "target": "interaction_channel"}],
            "restore": [{"tick": end, "op": "RECONNECT", "target": "interaction_channel"}],
            "observation": None,
            "affected": ["interaction_channel"],
            "label": "coupling boundary: the interaction channel cut",
        }
    if kind == "resource_exchange":
        tgt = params.get("target") or "feedback"
        return {
            "ivs": [{"tick": tick, "op": "ISOLATE", "target": tgt}],
            "restore": [{"tick": end, "op": "RECONNECT", "target": tgt}],
            "observation": None,
            "affected": [tgt],
            "label": f"resource-exchange boundary: {tgt} cut",
        }
    if kind == "history_access":
        return {
            "ivs": [{"tick": tick, "op": "ISOLATE", "target": "history"}],
            "restore": [{"tick": end, "op": "RECONNECT", "target": "history"}],
            "observation": None,
            "affected": ["history"],
            "label": "history-access boundary: history cut off from later firing",
        }
    if kind == "address_domain":
        tgt = params.get("target") or "A2"
        mode = params.get("mode") or "loss"
        iv: dict[str, Any] = {"tick": tick, "op": "ADDRESS", "target": tgt, "mode": mode}
        for k in ("x", "y", "fraction", "delay", "duration"):
            if k in params:
                iv[k] = params[k]
        if mode == "reassign" and "x" not in iv:
            iv.update(x=9, y=6)
        if mode == "delayed" and "x" not in iv:
            iv.update(x=9, y=6, delay=duration)
        if mode in ("fragment", "partial") and "fraction" not in iv:
            iv["fraction"] = 0.5
        restore = [{"tick": end, "op": "ADDRESS", "target": tgt, "mode": "restore"}]
        return {
            "ivs": [iv],
            "restore": restore,
            "observation": None,
            "affected": [tgt],
            "label": f"Address Domain boundary: {mode} of {tgt}",
        }
    raise E.MeosError(f"boundary kind must be one of {BOUNDARY_KINDS}")


def _window_mean(path: dict, a: int, b: int) -> float:
    s = path["series"][a : b + 1]
    return float(np.mean(s)) if s else 0.0


def boundary_perturbation(
    cfg: dict, kind: str, tick: int = 100, duration: int = 40, seeds: tuple[int, ...] = (1,), params: dict | None = None
) -> dict:
    """Perturb one XenoBody boundary, observe the same run apart, and say what changed.

    For each seed: the unperturbed run, the perturbed run (the boundary is restored after ``duration`` ticks) and the perturbed run with a resource pulse after the restoration.
    Reported: the state before / during / at the end, the affected paths and components, collapse, recovery possibility, the effect on observability, and — for B1, B2 and B3 —
    which affected components lie inside the body and which legs of the recursion the perturbation breaks. B3-only persistence is a property of the unperturbed
    arrangement (``analysis.boundary_analysis``); this function does not recompute it."""
    params = params or {}
    sp = _perturbation(kind, tick, duration, params)
    horizon = max(int(cfg["horizon"]), tick + duration + 140)
    rows = []
    for sd in seeds:
        c = X.cfg_with(cfg, seed=sd, horizon=horizon)
        base = E.run_record(c, [])
        pert = E.run_record(c, sp["ivs"])  # the boundary stays perturbed
        back = E.run_record(c, [*sp["ivs"], *sp["restore"]])  # perturbed for ``duration`` ticks, then restored
        pulsed = E.run_record(c, [*sp["ivs"], *sp["restore"], X.pulse(tick + duration + 1, 2.0)])
        obs_cfg = sp["observation"] or {}
        ob = A.observe(back, obs_cfg)
        pa_base, pa_back = path_activity(base), path_activity(back)
        lo, hi = tick, min(horizon - 1, tick + duration + 30)
        paths = {}
        for key in PATHS:
            before, after = _window_mean(pa_base[key], lo, hi), _window_mean(pa_back[key], lo, hi)
            direct = any(c_ in sp["affected"] for c_ in PATHS[key]["components"])
            paths[key] = {
                "mean_unperturbed": round(before, 4),
                "mean_perturbed": round(after, 4),
                "changed": direct or abs(after - before) > 0.05 * max(before, 0.02),
                "cut_directly": direct,
            }
        collapse = next((s["tick"] for s in back["status_log"] if s["label"] == "COLLAPSED" and s["tick"] >= tick), None)
        rows.append(
            {
                "seed": sd,
                "state_before": base["frames"][tick - 1]["status"],
                "state_end_of_perturbation": back["frames"][min(horizon - 1, tick + duration)]["status"],
                "state_final_perturbed_open": pert["final_status"]["label"],
                "state_final_restored": back["final_status"]["label"],
                "state_final_restored_and_pulse": pulsed["final_status"]["label"],
                "state_final_unperturbed": base["final_status"]["label"],
                "collapse_tick": collapse,
                "collapsed": collapse is not None,
                "recovers_without_pulse": collapse is not None and back["final_status"]["label"] == "ACTIVE",
                "recovers_with_pulse": pulsed["final_status"]["label"] == "ACTIVE",
                "operation_changed": back["result_digest"] != base["result_digest"],
                "paths": paths,
                "observability": {
                    "operational_state": ob["operational_state"],
                    "observed_state": ob["observed_state"],
                    "status": ob["observability"]["status"],
                    "observation": ob["observation"],
                },
                "digests": {
                    "unperturbed": base["result_digest"],
                    "perturbed_restored": back["result_digest"],
                    "pulsed": pulsed["result_digest"],
                },
            }
        )
    return {
        "boundary": kind,
        "label": sp["label"],
        "tick": tick,
        "duration": duration,
        "interventions": [*sp["ivs"], *sp["restore"]],
        "affected_components": sp["affected"],
        "bodies": _bodies(sp["affected"]),
        "rows": rows,
        "affected_paths": sorted({k for r in rows for k, v in r["paths"].items() if v["changed"]}),
        "paths_cut_directly": sorted(
            {k for r in rows for k, v in r["paths"].items() if v["cut_directly"]}
        ),  # the rest changed downstream of the cut
        "note": "operational state, observed state and observability status are separate: an observation boundary changes what is seen, not what the run did",
    }


# ---------------------------------------------------------------------------------------------------- Address Domain effects
def address_effects(rec: dict, observation: dict | None = None) -> list[dict]:
    """One record per Address Domain intervention of a run: tick, affected address, old and new state, affected path, operational and observed effect, recovery status."""
    obs = A.observe(rec, observation)
    frames = rec["frames"]
    log = [iv for iv in rec["intervention_log"] if iv["op"] == "ADDRESS"]
    out = []
    for i, iv in enumerate(log):
        t, tgt = iv["tick"], iv["target"]
        names = [tgt] if tgt in E.ENTITIES else list(E.ENTITIES)
        nxt = next((j["tick"] for j in log[i + 1 :] if j["target"] == tgt or tgt == "both"), len(frames))
        old = {
            n: {
                "cell": [frames[max(0, t - 1)][n]["x"], frames[max(0, t - 1)][n]["y"]],
                **(frames[max(0, t - 1)].get("address") or {}).get(n, {"mode": None, "integrity": 1.0}),
            }
            for n in names
        }
        new = {
            n: {
                "cell": [frames[min(t, len(frames) - 1)][n]["x"], frames[min(t, len(frames) - 1)][n]["y"]],
                **(frames[min(t, len(frames) - 1)].get("address") or {}).get(n, {"mode": None, "integrity": 1.0}),
            }
            for n in names
        }
        before = frames[max(0, t - 1)]["status"]
        later = [f["status"] for f in frames[t : min(len(frames), nxt + 60)]]
        collapsed = next((f["t"] for f in frames[t:] if f["status"] == "COLLAPSED"), None)
        recovered = next((f["t"] for f in frames[collapsed:] if f["status"] == "ACTIVE"), None) if collapsed is not None else None
        out.append(
            {
                "tick": t,
                "mode": iv["address_mode"],
                "affected_address": names,
                "old_state": old,
                "new_state": new,
                "affected_path": ["observation", "coupling"]
                if iv["address_mode"] != "restore"
                else ["observation", "coupling", "recovery"],
                "operational_effect": {
                    "state_before": before,
                    "worst_state_after": "COLLAPSED"
                    if "COLLAPSED" in later
                    else ("DEGRADED" if "DEGRADED" in later else "ACTIVE"),
                    "collapse_tick": collapsed,
                },
                "observed_effect": {
                    "observed_state_final": obs["observed_state"],
                    "observability": obs["observability"]["status"],
                },
                "recovery_status": "not collapsed"
                if collapsed is None
                else (f"recovered at tick {recovered}" if recovered is not None else "not recovered"),
                "params": {k: iv[k] for k in ("x", "y", "fraction", "delay", "duration") if k in iv},
            }
        )
    return out


def address_intervention(
    cfg: dict,
    mode: str,
    target: str = "A2",
    tick: int = 100,
    duration: int = 40,
    seed: int = 1,
    params: dict | None = None,
    observation: dict | None = None,
) -> dict:
    """One Address Domain intervention (loss, reassign, fragment, collision, partial, delayed, stale), restored after ``duration`` ticks: the run, its effects and the unperturbed run."""
    sp = _perturbation("address_domain", tick, duration, {**(params or {}), "target": target, "mode": mode})
    c = X.cfg_with(cfg, seed=seed, horizon=max(int(cfg["horizon"]), tick + duration + 140))
    base = E.run_record(c, [])
    rec = E.run_record(c, [*sp["ivs"], *sp["restore"]])
    pulsed = E.run_record(c, [*sp["ivs"], *sp["restore"], X.pulse(tick + duration + 1, 2.0)])
    effects = address_effects(rec, observation)
    pulse_effects = address_effects(pulsed, observation)
    for e, pe in zip(effects, pulse_effects, strict=False):
        e["recovery_with_pulse"] = pe[
            "recovery_status"
        ]  # the same intervention followed by a resource pulse after the restoration
    return {
        "mode": mode,
        "target": target,
        "effects": effects,
        "operational_state": rec["final_status"]["label"],
        "unperturbed_state": base["final_status"]["label"],
        "restored_and_pulse_state": pulsed["final_status"]["label"],
        "observed": A.observe(rec, observation) | {"timeline": None},
        "digests": {"unperturbed": base["result_digest"], "intervened": rec["result_digest"], "pulsed": pulsed["result_digest"]},
        "record": rec,
    }


# ---------------------------------------------------------------------------------------------------- the per-run log
def run_log(rec: dict, observation: dict | None = None) -> dict:
    """Everything needed to analyse and replay one run, in one document: seed, configuration, initial condition, intervention schedule, the observation / boundary / Address
    Domain / SSS / M2 configuration, the operational, observed and observability timelines, collapse and recovery ticks and the digests."""
    obs = A.observe(rec, observation)
    cfg = rec["config"]
    log = rec["status_log"]
    collapse = next((s["tick"] for s in log if s["label"] == "COLLAPSED"), None)
    recovery = next((s["tick"] for s in log if s["label"] == "ACTIVE" and collapse is not None and s["tick"] > collapse), None)
    addr = address_effects(rec, observation)
    doc = {
        "schema": "xzr.meos.runlog/1",
        "engine": rec["engine"],
        "seed": rec["seed"],
        "horizon": cfg["horizon"],
        "initial_configuration": cfg,
        "initial_configuration_digest": rec["initial_config_digest"],
        "intervention_schedule": rec["interventions"],
        "intervention_log": rec["intervention_log"],
        "configuration": {
            "observation": obs["observation"],
            "boundary": {
                "arena_radius": cfg["environment"]["arena_radius"],
                "history_access": cfg.get("history", {}).get("access"),
                "channels": cfg["channels"],
            },
            "address_domain": {"interventions": addr},
            "sss": cfg["sss"],
            "m2": cfg.get("m2"),
            "phil": cfg.get("phil"),
        },
        "timelines": {
            "operational": [f["status"] for f in rec["frames"]],
            "observed": obs["observed_trajectory"],
            "observability": [r["observability"] for r in obs["timeline"]],
        },
        "status": {
            "operational_final": obs["operational_state"],
            "observed_final": obs["observed_state"],
            "observability": obs["observability"],
        },
        "collapse_tick": collapse,
        "recovery_tick": recovery,
        "paths": {k: {kk: vv for kk, vv in v.items() if kk != "series"} for k, v in path_activity(rec).items()},
        "digests": {"result": rec["result_digest"], "trace": rec.get("trace_digest"), "full": rec.get("full_digest")},
    }
    body = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    doc["log_digest"] = hashlib.sha256(body.encode()).hexdigest()
    return doc


def run_log_csv(rec: dict, observation: dict | None = None) -> str:
    """The per-tick table of one run: operational / observed / observability state with the path signals, the Address Domain integrity, the resource, the energy and the power."""
    obs = A.observe(rec, observation)
    T = rec["traces"]
    pa = path_activity(rec)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(
        [
            "tick",
            "operational",
            "observed",
            "observability",
            "limiting",
            "resource_total",
            "power_reserve",
            "a1_energy",
            "address_integrity_a1",
            "address_integrity_a2",
        ]
        + [f"path_{k}" for k in PATHS]
    )
    for t, row in enumerate(obs["timeline"]):
        w.writerow(
            [
                t,
                row["operational"],
                row["observed"],
                row["observability"],
                "|".join(row["limiting"]),
                T["resource_total"][t],
                T["power_reserve"][t],
                T["a1_energy"][t],
                T["address_integrity_a1"][t],
                T["address_integrity_a2"][t],
            ]
            + [pa[k]["series"][t] for k in PATHS]
        )
    return buf.getvalue()


# ---------------------------------------------------------------------------------------------------- SSS region of one point
def sss_classify(cfg: dict, scale: float, size: float, speed: float, seeds: tuple[int, ...] = (1, 2)) -> dict:
    """The region of one (scale, size, speed) point: ACTIVE / COLLAPSED / metastable, recovery-capable, observation-sensitive (same definition as ``experiments.sss_phase``)."""
    ph = X.sss_phase(cfg, (scale,), (size,), (speed,), seeds)
    p = ph["points"][0]
    cls = p["class"]
    if cls == "metastable":
        region = "METASTABLE"
    elif cls == "ACTIVE":
        region = "OBSERVATION-SENSITIVE" if p["observation_sensitive"] else "ACTIVE"
    else:
        region = "RECOVERY-CAPABLE" if p["recovery_capable"] else "COLLAPSED"
    return {
        **{k: p[k] for k in ("scale", "size", "speed", "class", "recovery_capable", "observation_sensitive", "per_seed")},
        "region": region,
        "seeds": list(seeds),
    }
