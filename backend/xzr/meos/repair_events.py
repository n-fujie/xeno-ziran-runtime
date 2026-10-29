"""MEOS-0, sixth stage: the events of a repaired run, read from the run and from what was done to it (the stress, the repair actions or the controller's log, the status record), for the replay timeline, the research map and the technical view.

Nothing is invented: every event is a tick of the run's own schedule, status record or controller log, or the tick of a result saved by an experiment (the earliest irreversible tick of a stress), and says where it comes from.
"""

from __future__ import annotations

from typing import Any

from . import repair6 as R

FAMILY_PATH = {"coupling": "coupling", "resource": "resource", "renewal": "recovery", "address": "address", "history": "history_access", "internal": "m2"}  # the path a family of world state lies on (the technical view and the research map draw on these)


def stress_events(stress: R.Stress, onset: int) -> list[dict]:
    """The onset of the stress: one event, from the schedule (the first intervention it makes names what was damaged)."""
    ivs = stress.make(onset)
    iv = ivs[0]
    return [{"tick": onset, "kind": "stress-onset", "label": f"STRESS {stress.label}", "detail": f"{iv['op']} {iv.get('path') or iv.get('target') or ''} {iv.get('value', '')} {iv.get('mode', '')}".strip() + (f" (+{len(ivs) - 1} more)" if len(ivs) > 1 else ""),
             "family": stress.family, "path": FAMILY_PATH.get(stress.family), "source": "schedule"}]


def action_events(actions: list[dict], decided: dict[int, dict] | None = None) -> list[dict]:
    """One event per action: ``actions`` are {action, magnitude, duration, t}; ``decided`` maps a tick to the controller's decision (its estimates), where there was one."""
    out = []
    for a in actions:
        spec = R.ACTIONS[a["action"]]
        d = (decided or {}).get(a["t"])
        out.append({"tick": a["t"], "kind": "repair-action", "label": f"REPAIR {spec.label.split(':')[0][:48]}", "detail": f"{a['action']} magnitude {a['magnitude']} duration {a['duration']} ({'internal reconfiguration' if spec.klass == 'A' else 'world-state repair'})", "family": spec.family, "klass": spec.klass,
                    "action": a["action"], "magnitude": a["magnitude"], "duration": a["duration"], "path": FAMILY_PATH.get(spec.family), "expected_recovery": d.get("expected_recovery") if d else None, "estimated_cost": d.get("estimated_cost") if d else None, "source": "controller log" if d else "schedule"})
    return out


def status_events(frames: list[dict], t_first: int) -> list[dict]:
    """Collapse, recovery (the first tick of an ACTIVE stretch of at least W ticks) and secondary collapse (a collapse after such a stretch), from the status record alone."""
    st = [f["status"] for f in frames]
    out: list[dict] = []
    seen_collapse, stable = False, False
    i = t_first
    while i < len(st):
        if st[i] == "COLLAPSED" and not seen_collapse:
            out.append({"tick": i, "kind": "collapse", "label": "COLLAPSE", "detail": "status COLLAPSED", "source": "status record"})
            seen_collapse = True
        if st[i] == "COLLAPSED" and stable:
            out.append({"tick": i, "kind": "secondary-collapse", "label": "SECONDARY COLLAPSE", "detail": "COLLAPSED after a sustained ACTIVE stretch that followed the repair", "source": "status record"})
            stable = False
        if st[i] == "ACTIVE":
            j = i
            while j < len(st) and st[j] == "ACTIVE":
                j += 1
            if j - i >= R.W and not stable and (seen_collapse or i > t_first):
                out.append({"tick": i, "kind": "full-recovery" if seen_collapse else "partial-recovery", "label": "RECOVERED" if seen_collapse else "ACTIVE SUSTAINED", "detail": f"ACTIVE for {j - i} ticks from here" + ("" if seen_collapse else " (no collapse occurred: prevented)"), "source": "status record"})
                stable = True
            i = j
            continue
        i += 1
    return out


def build(stress: R.Stress | None, onset: int, actions: list[dict], rec: dict, evaluation: dict, controller_log: list[dict] | None, irreversible_tick: int | None = None) -> dict[str, Any]:
    """The ``repair`` block of a repaired run."""
    decided = {e["tick"] + 1: e for e in (controller_log or [])}
    ev: list[dict] = []
    if stress:
        ev += stress_events(stress, onset)
    for e in controller_log or []:
        if e["selected"] is None:
            ev.append({"tick": e["tick"], "kind": "repair-failed", "label": "NO ACTION AVAILABLE", "detail": f"detected {', '.join(e['detected']) or 'nothing'}; no plan matches (outside the tested action space of this controller)", "source": "controller log"})
            continue
        ev.append({"tick": e["tick"], "kind": "repair-decision", "label": f"DECISION {e['selected'][:44]}", "detail": f"detected {', '.join(e['detected']) or 'nothing'}; available {len(e['available'])}, rejected {len(e['rejected'])}; selected {e['selected']} (expected recovery {e['expected_recovery']}, estimated cost {e['estimated_cost']})",
                   "source": "controller log", "attempt": e["attempt"], "actual": e.get("actual")})
        if e.get("actual") and not e["actual"]["recovered_so_far"]:
            ev.append({"tick": e["actual"]["tick"], "kind": "repair-failed", "label": "REPAIR FAILED", "detail": f"attempt {e['attempt']} ({e['selected']}): the run had not recovered {e['actual']['tick'] - e['tick']} ticks later", "source": "controller log"})
    acts = list(actions)
    for e in [x for x in (controller_log or []) if x["selected"]]:
        for a in e["actions"]:
            acts.append({"action": a["action"], "magnitude": a["magnitude"], "duration": a["duration"], "t": e["tick"] + 1})
    ev += action_events(acts, decided)
    t0 = min([e["tick"] for e in ev] or [0])
    ev += status_events(rec["frames"], t0)
    h = evaluation["horizons"]
    if any(x["secondary_collapse"] for x in h.values()) and not any(e["kind"] == "secondary-collapse" for e in ev):
        ev.append({"tick": len(rec["frames"]) - 1, "kind": "secondary-collapse", "label": "SECONDARY COLLAPSE", "detail": "by the horizon evaluation", "source": "evaluation"})
    if any("pulse" in a["action"] and a["magnitude"] >= 3.0 for a in acts) and any(x["secondary_collapse"] for x in h.values()):
        ev.append({"tick": min(a["t"] for a in acts if "pulse" in a["action"]), "kind": "overshoot", "label": "OVERSHOOT", "detail": "a resource pulse of 3.0 or more followed by a secondary collapse (the stage 3 and stage 6 non-monotonicity)", "source": "schedule and evaluation"})
    if irreversible_tick is not None:
        ev.append({"tick": irreversible_tick, "kind": "irreversible", "label": "IRREVERSIBLE (tested action space)", "detail": "from this tick no tested repair action was effective (experiments_stage6_refine.json)", "source": "saved result"})
    ev.sort(key=lambda e: (e["tick"], e["kind"]))
    return {"stress": stress.id if stress else "no stress", "label": stress.label if stress else "no stress", "family": stress.family if stress else "none", "onset": onset, "actions": acts, "events": ev,
            "evaluation": {"horizons": h, "costs": evaluation["costs"], "final_status": evaluation["final_status"]}, "controller": {"attempts": len(controller_log or []), "log": controller_log or []}}
