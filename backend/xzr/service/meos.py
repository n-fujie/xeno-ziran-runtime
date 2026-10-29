"""MEOS API: the XENO ECOSYSTEM view's simulation endpoints (xzr.meos) over HTTP.

Stateless and read-only on the server: a request carries a configuration, a seed and an intervention list, and the answer is the deterministic record
of that run (nothing is stored; replay is the same request). Local runtime only, like the study routes: a run costs CPU, so on a public deployment
(XZR_PUBLIC=1) every route answers 403 and a request made from another site's page is refused. Sizes are bounded before anything runs.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from ..meos import analysis as A
from ..meos import engine as E
from ..meos import experiments as X
from ..meos import mfs5 as M5
from ..meos import reconf as RC
from ..meos import repair6 as R6
from ..meos import repair_ctl as RCTL
from ..meos import repair_events as RE
from ..meos import routes5 as R5
from ..meos import stage4 as S4
from .studies import local_only

router = APIRouter(prefix="/api/meos")
MAX_HORIZON = 600
MAX_SEEDS = 5


def _config(body: dict) -> dict:
    over = body.get("config") or {}
    if not isinstance(over, dict):
        raise HTTPException(422, "config must be an object")
    cfg = E.default_config()
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            for k2, v2 in v.items():
                if isinstance(v2, dict) and isinstance(cfg[k].get(k2), dict):
                    cfg[k][k2].update(v2)
                else:
                    cfg[k][k2] = v2
        else:
            cfg[k] = v
    if isinstance(cfg.get("horizon"), int) and cfg["horizon"] > MAX_HORIZON:
        raise HTTPException(422, f"horizon is limited to {MAX_HORIZON} ticks on this API")
    return cfg


def _ivs(body: dict) -> list[dict]:
    ivs = body.get("interventions") or []
    if not isinstance(ivs, list) or not all(isinstance(i, dict) for i in ivs):
        raise HTTPException(422, "interventions must be a list of objects")
    return ivs


def _guard(fn, *args: Any, **kw: Any) -> Any:
    try:
        return fn(*args, **kw)
    except E.MeosError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/spec")
def spec(request: Request) -> dict:
    """Everything a client needs to build the experiment controls: defaults, the removable components, the settable parameters, the operations, the status
    criteria and the named boundary partitions."""
    local_only(request)
    return {
        "engine": E.ENGINE_VERSION,
        "schema": E.SCHEMA,
        "defaults": E.default_config(),
        "components": list(E.COMPONENTS),
        "entities": list(E.ENTITIES),
        "operations": list(E.OPS),
        "settable": {k: list(v) for k, v in E.SETTABLE.items()},
        "partitions": A.PARTITIONS,
        "body_components": list(A.BODY_COMPONENTS),
        "legs": {k: list(v) for k, v in A.LEGS.items()},
        "status_criteria": {
            "ACTIVE": "at least 2 complete cycles in the last 48 ticks and the latest cycle no older than 24 ticks",
            "DEGRADED": "at least one cycle in the window but fewer than required or stale, or no cycle yet during the first 48 ticks (forming)",
            "COLLAPSED": "no complete cycle in the last 48 ticks after the first 48 ticks",
            "cycle": "A1 acts (alters the environment) -> A2 detects that alteration and fires -> A2 reconfigures the environment -> A1 detects the change and fires; "
            "every link is a causal attribution to a recorded event of the other configuration within 6 ticks",
        },
        "limits": {"max_horizon": MAX_HORIZON, "max_interventions": 64, "max_seeds": MAX_SEEDS},
    }


@router.post("/run")
def run(request: Request, body: dict[str, Any]) -> dict:
    """Run to the horizon: the full record (frames, events, cycles, status log, fields) with its input and result digests, and the observed status
    for an optional observation configuration."""
    local_only(request)
    cfg, ivs = _config(body), _ivs(body)
    rec = _guard(E.run_record, cfg, ivs)
    out: dict[str, Any] = {"record": rec, "summary": A.summarize(rec)}
    if body.get("observation") is not None:
        out["observed"] = A.observe(rec, body["observation"])
    if body.get("paths"):
        out["paths"] = S4.path_activity(rec)
    return out


@router.post("/replay")
def replay(request: Request, body: dict[str, Any]) -> dict:
    """Re-run a record's initial configuration, seed and interventions and compare the result digests bit for bit."""
    local_only(request)
    cfg, ivs = _config(body), _ivs(body)
    expected = body.get("result_digest")
    if not isinstance(expected, str):
        raise HTTPException(422, "result_digest is required")
    rec = _guard(E.run_record, cfg, ivs)
    return {"identical": rec["result_digest"] == expected, "expected": expected, "got": rec["result_digest"]}


@router.post("/ablation")
def ablation(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    cfg = _config(body)
    seeds = body.get("seeds") or [cfg["seed"]]
    if not (isinstance(seeds, list) and 1 <= len(seeds) <= MAX_SEEDS and all(isinstance(s, int) for s in seeds)):
        raise HTTPException(422, f"seeds must be 1..{MAX_SEEDS} integers")
    subsets = body.get("subsets")
    if subsets is not None and not (
        isinstance(subsets, list)
        and len(subsets) <= 24
        and all(isinstance(s, list) and set(s) <= set(E.COMPONENTS) for s in subsets)
    ):
        raise HTTPException(422, "subsets must be lists of components")
    return _guard(A.ablation_table, cfg, subsets, tuple(seeds))


@router.post("/mfs")
def mfs(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(A.minimal_configuration, _config(body), bool(body.get("exhaustive")), body.get("horizon"))


@router.post("/boundary")
def boundary(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    parts = body.get("partitions")
    if parts is not None:
        ok = (
            isinstance(parts, dict)
            and len(parts) <= 8
            and all(
                isinstance(p, dict)
                and isinstance(p.get("components"), list)
                and set(p["components"]) <= {"A1", *A.BODY_COMPONENTS}
                for p in parts.values()
            )
        )
        if not ok:
            raise HTTPException(422, "partitions must map ids to {components: [...]} of operational components")
        parts = copy.deepcopy(parts)
    return _guard(A.boundary_analysis, _config(body), parts)


@router.post("/history")
def history(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(A.history_comparison, _config(body))


@router.post("/sss")
def sss(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(A.sss_sweep, _config(body))


@router.post("/address")
def address(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(A.address_sweep, _config(body))


# ---------------------------------------------------------------------------------------------- second-stage experiments (bounded sizes)
def _seeds(body: dict, default: tuple[int, ...], limit: int = 5) -> tuple[int, ...]:
    seeds = body.get("seeds")
    if seeds is None:
        return default
    if not (isinstance(seeds, list) and 1 <= len(seeds) <= limit and all(isinstance(s, int) for s in seeds)):
        raise HTTPException(422, f"seeds must be 1..{limit} integers")
    return tuple(seeds)


@router.post("/causal")
def causal(request: Request, body: dict[str, Any]) -> dict:
    """intervention -> change of intermediate quantities -> persistence failure -> collapse, from the run and its counterfactual (same seed, no intervention)."""
    local_only(request)
    cfg, ivs = _config(body), _ivs(body)
    if not ivs:
        raise HTTPException(422, "interventions are required")
    _guard(E.validate_interventions, ivs, cfg["horizon"])
    return _guard(X.causal_path, cfg, ivs)


@router.post("/factorial")
def factorial(request: Request, body: dict[str, Any]) -> dict:
    """history (on/off) x resource gradient (on/off) x power (finite/unlimited)."""
    local_only(request)
    return _guard(X.factorial_history_gradient_power, _config(body), _seeds(body, tuple(range(1, 6)), 10))


@router.post("/necessity")
def necessity(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(X.history_necessity_map, _config(body), seeds=_seeds(body, (1, 2), 3))


@router.post("/minimal-configurations")
def minimal_configurations(request: Request, body: dict[str, Any]) -> dict:
    """Every subset of the admissible reductions is run; all inclusion-minimal preserving sets are reported."""
    local_only(request)
    horizon = body.get("horizon", 160)
    if not (isinstance(horizon, int) and 60 <= horizon <= 240):
        raise HTTPException(422, "horizon must be an integer in 60..240")
    obs = body.get("observation")
    if obs is not None and not isinstance(obs, dict):
        raise HTTPException(422, "observation must be an object")
    out = _guard(X.minimal_configurations, _config(body), _seeds(body, (1,), 2), horizon, obs)
    if not body.get("all_subsets"):
        out.pop("all_subsets", None)
    return out


@router.post("/boundary-experiments")
def boundary_experiments(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    cfg = _config(body)
    return {"kinds": _guard(X.boundary_experiments, cfg, _seeds(body, (1, 2), 3)), "closure": _guard(X.body_closure, cfg)}


@router.post("/recovery")
def recovery(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    amounts = body.get("amounts")
    if amounts is not None and not (
        isinstance(amounts, list)
        and 1 <= len(amounts) <= 30
        and all(isinstance(a, int | float) and 0 <= a <= 20 for a in amounts)
    ):
        raise HTTPException(422, "amounts must be 1..30 numbers in 0..20")
    scenario = body.get("scenario", "interaction cut 100-150")
    if scenario not in ("interaction cut 100-150", "A2 removed 100-150"):
        raise HTTPException(422, "unknown scenario")
    return _guard(X.recovery_phase, _config(body), tuple(amounts) if amounts else None, _seeds(body, (1, 2), 5), scenario)


@router.post("/sss-phase")
def sss_phase(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    axes = {}
    for k, default in (("scales", (0.5, 1.0, 1.5)), ("sizes", (1.0, 2.0)), ("speeds", (0.5, 1.0, 2.0))):
        v = body.get(k, default)
        if not (
            isinstance(v, list | tuple) and 1 <= len(v) <= 8 and all(isinstance(x, int | float) and 0.25 <= x <= 4 for x in v)
        ):
            raise HTTPException(422, f"{k} must be 1..8 numbers in 0.25..4")
        axes[k] = tuple(v)
    if len(axes["scales"]) * len(axes["sizes"]) * len(axes["speeds"]) > 48:
        raise HTTPException(422, "at most 48 grid points on this API")
    return _guard(X.sss_phase, _config(body), axes["scales"], axes["sizes"], axes["speeds"], _seeds(body, (1,), 2))


@router.post("/address-experiments")
def address_experiments(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(X.address_experiments, _config(body), _seeds(body, (1,), 3))


@router.post("/m2")
def m2(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(X.m2_experiment, _config(body), _seeds(body, (1,), 3))


@router.post("/phil")
def phil(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    return _guard(X.phil_experiment, _config(body), _seeds(body, (1,), 3))


@router.post("/observe")
def observe(request: Request, body: dict[str, Any]) -> dict:
    """Run, then observe with a configured observation: operational state, observed state and why they differ."""
    local_only(request)
    cfg, ivs = _config(body), _ivs(body)
    obs = body.get("observation")
    if obs is not None and not isinstance(obs, dict):
        raise HTTPException(422, "observation must be an object")
    rec = _guard(E.run_record, cfg, ivs)
    return A.observe(rec, obs)


# ---------------------------------------------------------------------------------------------- fourth stage (research readings; nothing here changes a run)
def _obs(body: dict) -> dict | None:
    obs = body.get("observation")
    if obs is not None and not isinstance(obs, dict):
        raise HTTPException(422, "observation must be an object")
    return obs


@router.post("/paths")
def paths(request: Request, body: dict[str, Any]) -> dict:
    """The five operational paths of a run (resource, coupling, history access, observation, recovery): components, signal per tick, intervals of cut / quiet / active."""
    local_only(request)
    return S4.path_activity(_guard(E.run_record, _config(body), _ivs(body)))


@router.post("/boundary-perturbation")
def boundary_perturbation(request: Request, body: dict[str, Any]) -> dict:
    """Perturb one XenoBody boundary (observation, coupling, resource exchange, history access, Address Domain) and report before / after state, affected paths and
    components, collapse, recovery possibility, observability effect and the B1 / B2 / B3 relation closure."""
    local_only(request)
    kind = body.get("kind")
    if kind not in S4.BOUNDARY_KINDS:
        raise HTTPException(422, f"kind must be one of {S4.BOUNDARY_KINDS}")
    cfg = _config(body)
    tick, duration = body.get("tick", 100), body.get("duration", 40)
    if not (isinstance(tick, int) and 20 <= tick <= 300 and isinstance(duration, int) and 1 <= duration <= 200):
        raise HTTPException(422, "tick must be an integer in 20..300 and duration an integer in 1..200")
    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise HTTPException(422, "params must be an object")
    return _guard(S4.boundary_perturbation, cfg, kind, tick, duration, _seeds(body, (1,), 3), params)


@router.post("/address-intervention")
def address_intervention(request: Request, body: dict[str, Any]) -> dict:
    """One Address Domain intervention (loss, reassign, fragment, collision, partial, delayed, stale), restored after ``duration`` ticks, with its recorded effects."""
    local_only(request)
    mode, target = body.get("mode"), body.get("target", "A2")
    if mode not in E.ADDRESS_MODES or mode == "restore":
        raise HTTPException(422, f"mode must be one of {tuple(m for m in E.ADDRESS_MODES if m != 'restore')}")
    if target not in (*E.ENTITIES, "both"):
        raise HTTPException(422, "target must be A1, A2 or both")
    tick, duration, seed = body.get("tick", 100), body.get("duration", 40), body.get("seed", 1)
    if not (isinstance(tick, int) and 20 <= tick <= 300 and isinstance(duration, int) and 1 <= duration <= 200 and isinstance(seed, int)):
        raise HTTPException(422, "tick must be an integer in 20..300, duration in 1..200, seed an integer")
    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise HTTPException(422, "params must be an object")
    return _guard(S4.address_intervention, _config(body), mode, target, tick, duration, seed, params, _obs(body))


@router.post("/run-log")
def run_log(request: Request, body: dict[str, Any]) -> Any:
    """The per-run log of a run (``format``: json, csv). The JSON log carries seed, configuration, intervention schedule, the observation / boundary / Address / SSS / M2
    configuration, the operational, observed and observability timelines, collapse and recovery ticks and the digests; the CSV is the per-tick table."""
    local_only(request)
    fmt = body.get("format", "json")
    if fmt not in ("json", "csv"):
        raise HTTPException(422, "format must be json or csv")
    rec = _guard(E.run_record, _config(body), _ivs(body))
    if fmt == "csv":
        return PlainTextResponse(S4.run_log_csv(rec, _obs(body)), media_type="text/csv")
    return S4.run_log(rec, _obs(body))


@router.post("/sss-classify")
def sss_classify(request: Request, body: dict[str, Any]) -> dict:
    """The SSS region (ACTIVE / COLLAPSED / METASTABLE / RECOVERY-CAPABLE / OBSERVATION-SENSITIVE) of one scale, size, speed point."""
    local_only(request)
    vals = [body.get(k, 1.0) for k in ("scale", "size", "speed")]
    if not all(isinstance(v, int | float) and not isinstance(v, bool) and 0.25 <= v <= 4 for v in vals):
        raise HTTPException(422, "scale, size and speed must be numbers in 0.25..4")
    return _guard(S4.sss_classify, _config(body), *[float(v) for v in vals], _seeds(body, (1, 2), 3))


# ---------------------------------------------------------------------------------------------- fifth stage (routes, the MFS library, a controlled run)
STAGE5_FILE = Path(os.environ.get("XZR_MEOS_STAGE5", Path(__file__).resolve().parents[3] / "docs" / "ecosystem" / "experiments_stage5.json"))


def _stage5() -> dict:
    """The saved results of experiment F (the MFS library). The routes never run the exhaustive search: it takes minutes and is run by ``scripts/meos_experiments_v5.py``."""
    if not STAGE5_FILE.exists():
        raise HTTPException(404, "the fifth-stage results are not saved on this server: run backend/scripts/meos_experiments_v5.py")
    return json.loads(STAGE5_FILE.read_text())["experiments"]


def _library_entries(f: dict) -> list[dict]:
    return [{"id": m["id"], "condition_id": cid, "condition": r["condition"]["label"], "features": m["environment_condition"]["features"], "retained": m["retained_components"], "removed": m["removed_components"], "cardinality": m["cardinality"],
             "route_kind": m["route_kind"], "retained_paths": m["retained_paths"], "lost_paths": m["lost_paths"], "digest": m["digest"]} for cid, r in f["by_condition"].items() for m in r["mfs"]]


@router.get("/mfs-library")
def mfs_library(request: Request) -> dict:
    """The MFS found by experiment F (saved) with, for each, its profile, its SSS points and its robustness scores; the candidate sets that were rejected or are near misses; the final table of
    conditions F1-F16; the scenarios and controllers of experiment I."""
    local_only(request)
    ex = _stage5()
    f, j, k = ex["F"], ex.get("J", {"rows": [], "points": []}), ex.get("K", {"rows": []})
    from ..meos import stage5_experiments as X5

    final = json.loads(STAGE5_FILE.read_text()).get("final", {})
    pts: dict[str, list[dict]] = {}
    for p in j.get("points", []):
        pts.setdefault(p["mfs"], []).append({"scale": p["scale"], "size": p["size"], "speed": p["speed"], "region": p["region"]})
    jr = {r["mfs"]: r for r in j.get("rows", [])}
    kr = {r["mfs"]: r for r in k.get("rows", [])}
    entries = _library_entries(f)
    for m in entries:
        pr = f.get("profiles", {}).get(m["id"], {})
        sens = pr.get("perturbation_sensitivity") or {}
        m["card"] = {
            "preserved_operation": pr.get("preserved_operation"), "energy_use": pr.get("energy_use"), "resource_throughput": pr.get("resource_throughput"), "recovery_latency": pr.get("recovery_latency"),
            "perturbation_collapse_share": (sum(sens.values()) / len(sens)) if sens else None, "history_dependence": pr.get("history_dependence"), "address_dependence": pr.get("address_dependence"),
            "observational_robustness": pr.get("observational_robustness"), "sss_region": pr.get("sss_region"), "ranges_along_axes": jr.get(m["id"], {}).get("ranges_along_axes"),
            "operational_robustness": kr.get(m["id"], {}).get("operational_robustness"), "addressability": kr.get(m["id"], {}).get("addressability"), "recoverability": kr.get(m["id"], {}).get("recoverability"),
        }
        m["sss_points"] = pts.get(m["id"], [])
    rejected = [{"condition_id": cid, **c} for cid, v in final.get("candidates", {}).items() for c in [*v["rejected"], *v["near_misses"]]]
    return {"mfs": entries, "rejected_candidates": rejected, "conditions": [r["condition"] for r in f["by_condition"].values()], "classification_table": final.get("F_table", []), "scenarios": list(X5.SCENARIOS),
            "controllers": list(X5.CONTROLLERS), "levels": f.get("levels", []), "route_equivalence": final.get("route_equivalence", [])}


@router.post("/mfs-run")
def mfs_run(request: Request, body: dict[str, Any]) -> dict:
    """Run the configuration of one saved MFS (its condition, with only its retained components in place) on a seed: the record, its summary, the path activity and the route topology."""
    local_only(request)
    mid, seed = body.get("mfs"), body.get("seed", 1)
    if not isinstance(mid, str) or not isinstance(seed, int) or isinstance(seed, bool):
        raise HTTPException(422, "mfs must be an MFS id and seed an integer")
    ex = _stage5()
    found = next(((cid, m) for cid, r in ex["F"]["by_condition"].items() for m in r["mfs"] if m["id"] == mid), None)
    if found is None:
        raise HTTPException(404, f"unknown MFS {mid}")
    cond = next(c for c in M5.conditions_f() if c["id"] == found[0])
    rec = _guard(E.run_record, M5._config(cond, seed, 240), M5.retained_interventions(cond, frozenset(found[1]["retained_components"])))
    return {"record": rec, "summary": A.summarize(rec), "paths": S4.path_activity(rec), "topology": R5.topology(rec),
            "mfs": {"id": mid, "condition_id": found[0], "retained": found[1]["retained_components"], "removed": found[1]["removed_components"]}}


@router.post("/route-topology")
def route_topology(request: Request, body: dict[str, Any]) -> dict:
    """The route topology of a run (when each component was enabled or cut, the route changes, the transitions) with the library entries to read it against."""
    local_only(request)
    rec = _guard(E.run_record, _config(body), _ivs(body))
    out: dict[str, Any] = {"topology": R5.topology(rec), "summary": A.summarize(rec)}
    if STAGE5_FILE.exists():
        out["library"] = _library_entries(_stage5()["F"])
    return out


@router.post("/reconfigure")
def reconfigure(request: Request, body: dict[str, Any]) -> dict:
    """Run a scenario of experiment I under a controller (none, fixed, adaptive, delayed, noisy) that moves between the MFS of the saved library, and return the record, the controller's
    log, what each switch did and the route topology. The recorded schedule replays the same run without the controller."""
    local_only(request)
    from ..meos import stage5_experiments as X5

    kind, scen, seed = body.get("controller", "adaptive"), body.get("scenario", "history lost"), body.get("seed", 1)
    if kind not in X5.CONTROLLERS or scen not in X5.SCENARIOS or not isinstance(seed, int):
        raise HTTPException(422, f"controller must be one of {X5.CONTROLLERS}, scenario one of {list(X5.SCENARIOS)}, seed an integer")
    ex = _stage5()
    library = RC.library_from(ex["F"]["by_condition"])
    arrangement = {"tap": M5.M2_BASE, "tap_feature": "direct", "universe": M5.COMPONENTS5}
    cfg = _config({"config": {"seed": seed, "horizon": 300}})
    ivs = [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}, *copy.deepcopy(X5.SCENARIOS[scen][0])]
    ctl = None if kind == "none" else RC.Controller(kind, library, arrangement, noise=0.05, seed=seed)
    rec = _guard(RC.run_controlled, cfg, ivs, ctl)
    return {"record": rec, "summary": A.summarize(rec), "paths": S4.path_activity(rec), "controller": rec["controller"], "outcomes": RC.switch_outcomes(rec, X5.STRESS_TICK), "topology": R5.topology(rec),
            "replay_identical": E.replay(rec)["identical"]}


# ---------------------------------------------------------------------------------------------------- stage 6: world-state repair
S6_DIR = Path(os.environ.get("XZR_MEOS_STAGE6", Path(__file__).resolve().parents[3] / "docs" / "ecosystem"))
_S6_CACHE: dict[str, Any] = {}


def _s6(name: str) -> dict | None:
    """A saved stage 6 result file (experiments_stage6.json, _refine, _controllers), or None when that experiment has not been run on this server."""
    f = S6_DIR / f"experiments_stage6{name}.json"
    if not f.exists():
        return None
    key = f"{f}:{f.stat().st_mtime_ns}"
    if key not in _S6_CACHE:
        _S6_CACHE.clear()
        _S6_CACHE[key] = json.loads(f.read_text())
    return _S6_CACHE[key]


def _all_stresses() -> dict[str, tuple[R6.Stress, int]]:
    from ..meos import stage6_controllers as C6

    out = {sid: (st, R6.STRESS_TICK) for sid, st in R6.STRESSES.items()}
    for sid, st, onset, _ in C6.unknown_stresses():
        out[sid] = (st, onset)
    return out


_LIBRARY: dict[str, Any] = {}


def _repair_library() -> list[dict]:
    a = _s6("")
    if a is None:
        return []
    if _LIBRARY.get("from") != id(a):
        from ..meos import stage6_controllers as C6

        _LIBRARY.update({"from": id(a), "lib": C6.build_library(a)[0]})
    return _LIBRARY["lib"]


@router.get("/repair-library")
def repair_library(request: Request) -> dict:
    """The repair action space (what each action is, whether the engine can do it, its declared cost model), the stresses (the six of the library and the held-out variations), and, where the experiments have been run, their results: repairability, timing windows, minimum
    interventions, the resource sweeps, the controllers."""
    local_only(request)
    from ..meos import stage6_controllers as C6

    a, b, c = _s6(""), _s6("_refine"), _s6("_controllers")
    return {"actions": R6.action_table(), "stresses": {sid: {"family": st.family, "label": st.label, "onset": on} for sid, (st, on) in _all_stresses().items()}, "controllers": list(RCTL.KINDS), "failure_classes": list(C6.FAILURE_CLASSES),
            "horizons": R6.HORIZONS, "recovery_window": R6.W, "decision_tick": R6.T_ACT, "stress_tick": R6.STRESS_TICK, "results": a, "refine": b, "controller_results": c, "has_results": a is not None}


@router.post("/repair-run")
def repair_run(request: Request, body: dict[str, Any]) -> dict:
    """One repaired run: a stress (by id; ``no stress`` for none), repair actions at given ticks and/or a repair controller, a seed. Returns the record, its summary, the path activity, the evaluation at the three horizons with the costs, and the events of the repair (from the schedule, the
    status record and the controller log). A controller's recorded schedule (the injected interventions included) replays the same run without it."""
    local_only(request)
    sid, seed, kind = body.get("stress", "history lost"), body.get("seed", 1), body.get("controller")
    stresses = _all_stresses()
    if (sid != "no stress" and sid not in stresses) or not isinstance(seed, int) or isinstance(seed, bool) or (kind is not None and kind not in RCTL.KINDS):
        raise HTTPException(422, f"stress must be one of {list(stresses)} or 'no stress', seed an integer, controller one of {list(RCTL.KINDS)}")
    acts = body.get("actions") or []
    if not isinstance(acts, list) or len(acts) > 4:
        raise HTTPException(422, "actions: a list of at most 4 {action, magnitude, duration, t}")
    st, onset = (None, R6.STRESS_TICK) if sid == "no stress" else stresses[sid]
    reps: list[dict] = []
    norm: list[dict] = []
    for a in acts:
        aid = a.get("action")
        if aid not in R6.ACTIONS or R6.ACTIONS[aid].status == "not implemented" or R6.ACTIONS[aid].klass == "C":
            raise HTTPException(422, f"unknown or non-runnable action {aid!r}")
        m, d, t = float(a.get("magnitude", 0.0)), int(a.get("duration", 0)), int(a.get("t", R6.T_ACT))
        reps += R6.build_action(aid, st or R6.STRESSES["history lost"], m, t, d)
        norm.append({"action": aid, "magnitude": m, "duration": d, "t": t})
    ctl = None
    if kind and kind != "none":
        lib = _repair_library() if kind in ("cost_aware", "delayed", "noisy") else []
        if kind in ("cost_aware", "delayed", "noisy") and not lib:
            raise HTTPException(503, "the repair library needs experiments_stage6.json: run backend/scripts/meos_experiments_stage6.py")
        ctl = RCTL.RepairController(kind, lib, seed=seed, noise=0.1)
    base = R6.schedule(st, sorted(reps, key=lambda i: i["tick"]), onset)
    cfg = R6.config(seed)
    rec = _guard(RCTL.run_repaired, cfg, base, ctl)
    injected = [i for i in rec["interventions"] if i not in base]
    t_act = min([a["t"] for a in norm] + [onset + 13])
    ev = R6.evaluate(rec, R6.reference(seed), [*reps, *injected], t_act)
    b = _s6("_refine")
    irr = None
    if b and st:
        eff_ticks = [t for w in b["B1_windows"] if w["stress"] == sid for t in w["effective_ticks"]]
        irr = (max(eff_ticks) + 1) if eff_ticks else None
    rep = RE.build(st, onset, norm, rec, ev, rec["controller"]["log"] if ctl else None, irr)
    return {"record": rec, "summary": A.summarize(rec), "paths": S4.path_activity(rec), "topology": R5.topology(rec), "repair": rep, "replay_identical": E.replay(rec)["identical"]}

