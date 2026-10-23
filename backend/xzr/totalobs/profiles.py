"""Study-engine side of the total-observation line: validation of its protocols and the fairness profile of an arm.

The profile lists everything in which two arms may differ (information, authority, policy, history, rule revision, strong revision, compute, resources,
environment); the study's fairness check reports every difference that a contrast does not declare. The research agent's information is the same in every
arm: the hub's records (``ontology``); authority differs only through the declared operation grammar.
"""

from __future__ import annotations

import copy

from . import agent as A
from . import sss
from .loop import DEFAULT_ENV, merge_env

EVENTS = ("fail_sensor", "cut_zone", "restore_links", "lose_records", "move_source", "add_source", "set_pool")
OVERRIDE_KEYS = ("world", "net", "generations", "gen_steps", "warmup", "checkpoint", "events")
LIMITS = {"generations": (1, 30), "gen_steps": (5, 200), "regions": 600, "sensors": 12}


def effective_env(env: dict, arm: dict | None = None) -> dict:
    """The environment an arm runs in: the study's environment (without ``kind``) with the arm's own overrides on top."""
    base = {k: copy.deepcopy(v) for k, v in env.items() if k not in ("kind", "horizon")}
    out = merge_env(base)
    for k, v in ((arm or {}).get("environment") or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def validate_env(e: dict, where: str) -> list[str]:
    out: list[str] = []
    g, t = int(e["generations"]), int(e["gen_steps"])
    if not LIMITS["generations"][0] <= g <= LIMITS["generations"][1]:
        out.append(f"{where}: generations must be in {LIMITS['generations']}")
    if not LIMITS["gen_steps"][0] <= t <= LIMITS["gen_steps"][1]:
        out.append(f"{where}: gen_steps must be in {LIMITS['gen_steps']}")
    w = e["world"]
    if int(w.get("rows", 8)) * int(w.get("cols", 12)) > LIMITS["regions"]:
        out.append(f"{where}: more than {LIMITS['regions']} regions")
    if int(e["net"]["n_sensors"]) > LIMITS["sensors"] or int(e["net"]["n_sensors"]) < 1:
        out.append(f"{where}: n_sensors must be in 1..{LIMITS['sensors']}")
    for ev in e["events"]:
        if ev.get("do") not in EVENTS or "gen" not in ev:
            out.append(f"{where}: event {ev!r} is not one of {EVENTS} with a generation")
    unknown = set(e) - set(DEFAULT_ENV)
    if unknown:
        out.append(f"{where}: unknown environment keys {sorted(unknown)}")
    return out


def validate(doc: dict) -> list[str]:
    out = validate_env(effective_env(doc["environment"]), "environment")
    for a in doc["arms"]:
        try:
            A.Design.from_dict(a.get("design"))
        except (TypeError, ValueError) as e:
            out.append(f"arm {a['name']}: {e}")
            continue
        bad = set(a.get("environment") or {}) - set(OVERRIDE_KEYS)
        if bad:
            out.append(f"arm {a['name']}: environment overrides outside {OVERRIDE_KEYS}: {sorted(bad)}")
        else:
            out += validate_env(effective_env(doc["environment"], a), f"arm {a['name']}")
        tag = a.get("sss")
        if tag is not None and (set(tag) - set(sss.AXES) or any(v not in ("low", "high") for v in tag.values())):
            out.append(f"arm {a['name']}: sss must map axes {sss.AXES} to 'low' or 'high'")
    return out


def authority_of(d: A.Design) -> list[str]:
    if d.policy == "fixed":
        return []
    ops = set(A.GRAMMAR_0) | {o for s in d.strong for o in A.UNLOCKS[s]}
    if "grammar" in d.strong:
        ops.add("perturb")  # reachable only by the reversible grammar extension (adaptive) or from the start (random)
    if d.authority is not None:
        ops &= set(d.authority)
    return sorted(ops)


def profile(arm: dict, env: dict) -> dict:
    d = A.Design.from_dict(arm.get("design"))
    e = effective_env(env, arm)
    return {
        "information": "the hub's records only (observer side); identical in every arm; the verifier is never read by an arm",
        "revision_authority": authority_of(d),
        "policy": d.policy,
        "history": d.history if d.history else "off",
        "meta_revision": bool(d.meta),
        "strong_revision": sorted(d.strong),
        "compute": {
            "generations": e["generations"],
            "gen_steps": e["gen_steps"],
            "max_ops_per_generation": d.max_ops,
            "budget": d.budget,
        },
        "resources": {"pool_per_step": e["net"]["pool"], "sensors": e["net"]["n_sensors"]},
        "environment": arm.get("environment") or {},
    }
