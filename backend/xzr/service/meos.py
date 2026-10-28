"""MEOS API: the XENO ECOSYSTEM view's simulation endpoints (xzr.meos) over HTTP.

Stateless and read-only on the server: a request carries a configuration, a seed and an intervention list, and the answer is the deterministic record
of that run (nothing is stored; replay is the same request). Local runtime only, like the study routes: a run costs CPU, so on a public deployment
(XZR_PUBLIC=1) every route answers 403 and a request made from another site's page is refused. Sizes are bounded before anything runs.
"""

from __future__ import annotations

import copy
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from ..meos import analysis as A
from ..meos import engine as E
from ..meos import experiments as X
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
