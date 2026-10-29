"""MEOS-0, sixth stage: world-state repair. The action space, the cost model, the definition of recovery, and the runner.

Three kinds of recovery action are kept apart everywhere (code, experiments, documents) and never mixed under one name:

  A  internal reconfiguration  components enabled or disabled, routes switched (stage 5: ``reconf.py``, ``midrun.py``). Listed here only as the reference ``internal.m2_tap``.
  B  world-state repair        an intervention on the state or the parameters of the world the operation runs in: coupling, resource, renewal, Address. New in stage 6.
  C  observation repair        a change of how the run is observed (sampling, region, resolution). It changes the *observed* state, never the operational one.

Nothing here changes the engine: every B action is built from operations MEOS-0 already has (``RECONFIGURE``, ``ALTER_RESOURCE``, ``RECONNECT``, ``ADDRESS``, ``ROUTE``), so a run without a repair is identical to the same run in stage 5 (the baseline digests are untouched).
An action that has no mechanism in the engine is registered with status ``not implemented`` and a reason, and is never run or simulated by something else.

Recovery is not a flash of ACTIVE. A run *recovers at horizon H* if it is ACTIVE on every tick of the last ``W`` ticks before H, has no collapse after a sustained ACTIVE stretch of at least ``W`` ticks that followed the action (no secondary collapse), and its resource field is not exhausted at H.
The three horizons (short, medium, long) are evaluated on one run; the engine is deterministic, so the prefix of a long run is the shorter run.
"""

from __future__ import annotations

import copy
import functools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import engine as E
from . import experiments as X

STRESS_TICK = 100  # the tick at which the stress arrives (as in stage 5, experiments I and L)
T_ACT = 113  # the default action tick: the first decision of the stage 5 controllers
HORIZONS = {"short": 180, "medium": 300, "long": 480}
HORIZON = HORIZONS["long"]
W = 30  # a recovery must be ACTIVE over the last W ticks before the horizon; a sustained stretch is W ticks
SEARCH_SEEDS = (1, 2, 3, 4, 5)  # exploration
VALIDATION_SEEDS = (6, 7, 8, 9, 10)
EVAL_SEEDS = tuple(range(11, 31))
PULSE_CELL = (3, 6)  # A1's cell: where a resource pulse is inserted (the stage 3 recovery experiments used it)
BASE = {"coupling.gain": 1.0, "environment.regrow": 0.02, "power.charge": 0.4, "environment.renew_efficiency": 1.0, "entities.A2.renew": 0.5, "power.reserve": 24.0, "environment.diffusion": 0.03}


# ---------------------------------------------------------------------------------------------------- stresses (the world-state damage)
@dataclass(frozen=True)
class Stress:
    id: str
    family: str  # the family of world state that is damaged: coupling / resource / renewal / address / history
    label: str
    make: Callable[[int], list[dict]]  # onset tick -> interventions
    stressed: dict[str, float] = field(default_factory=dict)  # the stressed value of each parameter it changes (the value a bridge returns to)


def _rc(path: str, v: float, t: int) -> dict:
    return {"tick": t, "op": "RECONFIGURE", "path": path, "value": v}


def stress_coupling(gain: float = 0.5) -> Stress:
    return Stress(f"coupling gain {gain}", "coupling", f"coupling weakened (gain {gain})", lambda t: [_rc("coupling.gain", gain, t)], {"coupling.gain": gain})


def stress_resource(regrow: float = 0.01, charge: float = 0.2) -> Stress:
    return Stress(f"resource regrow {regrow} charge {charge}", "resource", f"resource reduced (regrow {regrow}, charge {charge})", lambda t: [_rc("environment.regrow", regrow, t), _rc("power.charge", charge, t)],
                  {"environment.regrow": regrow, "power.charge": charge})


def stress_renewal_efficiency(eff: float = 0.6) -> Stress:
    return Stress(f"renewal efficiency {eff}", "renewal", f"renewal efficiency {eff}", lambda t: [_rc("environment.renew_efficiency", eff, t)], {"environment.renew_efficiency": eff})


def stress_renewal_stopped() -> Stress:
    return Stress("renewal stopped", "renewal", "renewal stopped (feedback removed)", lambda t: [{"tick": t, "op": "REMOVE", "target": "feedback"}])


def stress_address(fraction: float = 0.5) -> Stress:
    return Stress(f"Address partial {fraction}", "address", f"Address degraded (A2 partial {int(fraction * 100)} %)", lambda t: [{"tick": t, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": fraction}])


def stress_history_lost() -> Stress:
    return Stress("history lost", "history", "history lost", lambda t: [{"tick": t, "op": "REMOVE", "target": "history"}])


STRESSES: dict[str, Stress] = {s.id: s for s in (stress_coupling(), stress_resource(), stress_renewal_efficiency(), stress_renewal_stopped(), stress_address(), stress_history_lost())}
STRESS_ORDER = tuple(STRESSES)


# ---------------------------------------------------------------------------------------------------- the action space
@dataclass(frozen=True)
class Action:
    id: str
    klass: str  # "A" internal, "B" world-state repair, "C" observation repair
    family: str  # coupling / resource / renewal / address / internal / observation
    label: str
    status: str  # "implemented" (an engine operation does it), "proxy" (the nearest engine parameter does it: stated in ``note``), "not implemented"
    magnitudes: tuple[float, ...] = ()
    magnitude_meaning: str = ""
    durations: tuple[int, ...] = (0,)
    build: Callable[[Stress, float, int, int], list[dict]] | None = None
    latency: str = ""
    side_effect: str = ""
    reversibility: str = ""
    cost: dict[str, str] = field(default_factory=dict)  # declared cost model: how each cost is incurred (the measured values are in the runs)
    note: str = ""


def _restore_gain(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("coupling.gain", mag, t)]


def _gradual_gain(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    g0, steps = s.stressed.get("coupling.gain", 0.5), max(1, dur // 5)
    return [_rc("coupling.gain", round(g0 + (mag - g0) * (i + 1) / steps, 4), t + 5 * i) for i in range(steps)]


def _bridge_gain(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("coupling.gain", mag, t), _rc("coupling.gain", s.stressed.get("coupling.gain", 1.0), t + dur)]  # strengthened for ``dur`` ticks, then back to the (still damaged) value


def _pulse(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [{"tick": t, "op": "ALTER_RESOURCE", "inject": {"x": PULSE_CELL[0], "y": PULSE_CELL[1], "amount": mag}}]


def _inflow(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("environment.regrow", mag, t), _rc("power.charge", BASE["power.charge"] * mag / BASE["environment.regrow"], t), _rc("environment.regrow", s.stressed.get("environment.regrow", BASE["environment.regrow"]), t + dur),
            _rc("power.charge", s.stressed.get("power.charge", BASE["power.charge"]), t + dur)]


def _diffusion(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("environment.diffusion", mag, t), _rc("environment.diffusion", BASE["environment.diffusion"], t + dur)]


def _reserve(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("power.reserve", mag, t)]


def _restore_eff(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("environment.renew_efficiency", mag, t)]


def _restart(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [{"tick": t, "op": "RECONNECT", "target": "feedback"}]


def _aux_renew(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("entities.A2.renew", mag, t)]


def _eff_pulse(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [_rc("environment.renew_efficiency", mag, t), _rc("environment.renew_efficiency", s.stressed.get("environment.renew_efficiency", 1.0), t + dur)]


def _addr_restore(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [{"tick": t, "op": "ADDRESS", "target": "A2", "mode": "restore"}]


def _addr_reassign(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [{"tick": t, "op": "ADDRESS", "target": "A2", "mode": "reassign", "x": 5, "y": 6}]  # to the cell A2 starts in


def _m2_tap(s: Stress, mag: float, t: int, dur: int) -> list[dict]:
    return [{"tick": t, "op": "ROUTE", "m2": {"sense": "direct", "weight": 4.0}}]


_PARAM = "a parameter of the world"
ACTION_LIST: tuple[Action, ...] = (
    Action("internal.m2_tap", "A", "internal", "switch the M2 tap on (stage 5 internal reconfiguration; reference)", "implemented", build=_m2_tap, latency="1 tick", side_effect="A1 also senses M2", reversibility="reversible (ROUTE m2 none)",
           cost={"switching": "1 operation"}),
    # ---- coupling
    Action("coupling.restore", "B", "coupling", "restore the coupling gain (full at 1.0, partial below)", "implemented", (0.6, 0.7, 0.8, 0.9, 1.0), "target gain (stressed value 0.5, baseline 1.0)", build=_restore_gain, latency="1 tick",
           side_effect="none expected: the parameter returns to a value it had", reversibility="reversible", cost={"switching": "1 RECONFIGURE", "persistence": "none after the change"}),
    Action("coupling.gradual", "B", "coupling", "restore the coupling gain in steps of 5 ticks", "implemented", (1.0,), "target gain", (10, 20, 40), _gradual_gain, "duration/2 ticks to complete", "intermediate gains pass through the dynamics", "reversible", {"switching": "duration/5 RECONFIGURE"}),
    Action("coupling.bridge", "B", "coupling", "temporary bridge: strengthen the coupling above baseline for a while, then return it to its (damaged) value", "implemented", (1.25, 1.5, 2.0), "boost gain (maximum 2.0)", (10, 20, 40), _bridge_gain,
           "1 tick", "the damage remains after the bridge", "reversible by construction", {"switching": "2 RECONFIGURE", "persistence": "none after the bridge"}),
    Action("coupling.bypass", "B", "coupling", "local bypass of the damaged coupling", "not implemented", note="the coupling of MEOS-0 is one scalar share of A1's alteration reaching A2; there is no spatial coupling path to bypass, so no action is built"),
    # ---- resource
    Action("resource.pulse", "B", "resource", "resource pulse at A1's cell (graded by amount)", "implemented", (0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0), "amount of resource inserted", build=_pulse, latency="1 tick",
           side_effect="oversupply is a failure mode (stage 3: 2.0 recovers, 4.0 re-collapses)", reversibility="not reversible (material added)", cost={"resource": "the amount", "switching": "1 ALTER_RESOURCE"}),
    Action("resource.inflow", "B", "resource", "sustained inflow: raise regrow (and the charge in proportion) for a duration", "implemented", (0.02, 0.03, 0.04), "regrow rate (stressed 0.01, baseline 0.02)", (20, 60, 120), _inflow, "1 tick",
           side_effect="a higher regrow rate is a different regime", reversibility="reversible (returns to the stressed values)", cost={"resource": "extra regrow over the duration", "persistence": "while it lasts"}),
    Action("resource.redistribute", "B", "resource", "redistribution: raise the diffusion of the resource field for a duration", "proxy", (0.06, 0.12, 0.24), "diffusion coefficient (baseline 0.03)", (10, 30), _diffusion, "1 tick",
           side_effect="flattens the gradient the configurations use", reversibility="reversible", cost={"switching": "2 RECONFIGURE"}, note="MEOS-0 has no operation that moves resource from one cell to another; diffusion is the nearest mechanism and is a proxy for redistribution"),
    Action("resource.reserve", "B", "resource", "reserve release: raise the power reserve (the energy reserve of the renewal system)", "proxy", (24.0, 48.0, 96.0), "power reserve (baseline 24)", build=_reserve, latency="1 tick", side_effect="energy, not resource, is added",
           reversibility="not reversible", cost={"energy": "the reserve added"}, note="the power reserve is energy for A2's renewal, not the resource field: a proxy for a local reserve release"),
    Action("resource.rerouting", "B", "resource", "transport rerouting", "not implemented", note="MEOS-0 has no transport network for the resource; no action is built"),
    # ---- renewal
    Action("renewal.restore", "B", "renewal", "restore the renewal efficiency (partial below 1.0)", "implemented", (0.7, 0.8, 0.9, 1.0), "target efficiency (stressed 0.6, baseline 1.0)", build=_restore_eff, latency="1 tick", reversibility="reversible",
           cost={"switching": "1 RECONFIGURE"}),
    Action("renewal.restart", "B", "renewal", "restart renewal: reconnect the removed feedback", "implemented", build=_restart, latency="1 tick", side_effect="the feedback component returns", reversibility="reversible (REMOVE feedback)",
           cost={"switching": "1 RECONNECT"}),
    Action("renewal.auxiliary", "B", "renewal", "auxiliary renewal: raise how much resource A2 transfers per action step", "implemented", (0.75, 1.0, 1.5, 2.0), "A2 renew amount (baseline 0.5)", build=_aux_renew, latency="1 tick",
           side_effect="A2 transfers more per action", reversibility="reversible", cost={"switching": "1 RECONFIGURE", "resource": "more transferred per step"}),
    Action("renewal.pulse", "B", "renewal", "temporary renewal: renewal efficiency above baseline for a duration, then back to the stressed value", "implemented", (1.25, 1.5, 2.0), "boost efficiency (maximum 2.0)", (10, 20, 40), _eff_pulse, "1 tick",
           side_effect="the damage remains afterwards", reversibility="reversible by construction", cost={"switching": "2 RECONFIGURE"}),
    # ---- Address
    Action("address.restore", "B", "address", "restore the Address of A2 (also the refresh of a stale address)", "implemented", build=_addr_restore, latency="1 tick", reversibility="reversible", cost={"switching": "1 ADDRESS"}),
    Action("address.reassign", "B", "address", "local reconstruction: reassign A2 its Address at the cell it starts in", "implemented", build=_addr_reassign, latency="1 tick",
           side_effect="A2 is moved to (5, 6) with its state kept", reversibility="reversible", cost={"switching": "1 ADDRESS"}),
    Action("address.temporary_local", "B", "address", "temporary local addressing", "not implemented", note="no engine mode gives a bounded-duration local address (the ``stale`` and ``delayed`` modes are faults, not repairs)"),
    # ---- observation (class C: changes the observed state, not the run)
    Action("observation.sampling", "C", "observation", "increase the sampling frequency (sampling interval 1)", "implemented", note="applied to the observation of a recorded run (analysis.observe), not to the run"),
    Action("observation.region", "C", "observation", "expand the observation region to the whole arena", "implemented", note="applied to the observation of a recorded run"),
    Action("observation.resolution", "C", "observation", "increase the spatial resolution (stride 1)", "implemented", note="applied to the observation of a recorded run"),
    Action("observation.address", "C", "observation", "resolve the Address ambiguity (address resolution 1.0)", "implemented", note="applied to the observation of a recorded run"),
)
ACTIONS: dict[str, Action] = {a.id: a for a in ACTION_LIST}
RUNNABLE = tuple(a.id for a in ACTION_LIST if a.klass in ("A", "B") and a.status != "not implemented")  # the internal reference (class A) is run beside the world-state repairs (class B), never merged with them


def action_table() -> list[dict]:
    """The registry as data (for the saved results and the service): everything declared about each action, including what is not implemented."""
    return [{"id": a.id, "class": a.klass, "family": a.family, "label": a.label, "status": a.status, "magnitudes": list(a.magnitudes), "magnitude_meaning": a.magnitude_meaning, "durations": list(a.durations), "latency": a.latency, "side_effect": a.side_effect,
             "reversibility": a.reversibility, "declared_cost": a.cost, "note": a.note} for a in ACTION_LIST]


def build_action(action_id: str, stress: Stress, magnitude: float, t: int, duration: int = 0) -> list[dict]:
    a = ACTIONS[action_id]
    if a.build is None or a.status == "not implemented":
        raise ValueError(f"{action_id} is {a.status}: {a.note}")
    return a.build(stress, magnitude, t, duration)


# ---------------------------------------------------------------------------------------------------- running and measuring
def config(seed: int, horizon: int = HORIZON) -> dict:
    return X.cfg_with(E.default_config(), seed=seed, horizon=horizon)


def schedule(stress: Stress | None, repairs: list[dict], onset: int = STRESS_TICK) -> list[dict]:
    """The intervention schedule of a run: the dormant M2 tap (as in stage 5), the stress, the repair interventions."""
    return [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}, *(stress.make(onset) if stress else []), *copy.deepcopy(repairs)]


def run(stress: Stress | None, repairs: list[dict], seed: int, horizon: int = HORIZON, onset: int = STRESS_TICK, extra_config: dict | None = None) -> dict:
    cfg = config(seed, horizon)
    for k, v in (extra_config or {}).items():
        cfg[k] = v
    return E.run_record(cfg, schedule(stress, repairs, onset))


@functools.lru_cache(maxsize=64)
def reference(seed: int, horizon: int = HORIZON) -> dict:
    """The same seed without stress and without repair: what 'undamaged' looks like (cached per process)."""
    return run(None, [], seed, horizon)


_COLLATERAL = ("interaction_strength", "resource_total", "power_reserve", "resource_flow")


def _runs(st: list[str], lo: int, hi: int, label: str) -> list[tuple[int, int]]:
    out, i = [], lo
    while i < hi:
        if st[i] == label:
            j = i
            while j < hi and st[j] == label:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def outcome_at(st: list[str], H: int, t_act: int) -> dict:
    """The recovery outcome of a status sequence at horizon ``H`` (not a flash of ACTIVE): see the module docstring."""
    H = min(H, len(st))
    final_active = H >= W and all(s == "ACTIVE" for s in st[H - W:H])
    stretches = [(a, b) for a, b in _runs(st, t_act, H, "ACTIVE") if b - a >= W]
    secondary = any(s == "COLLAPSED" for _, b in stretches for s in st[b:H])  # a collapse after a sustained ACTIVE stretch that followed the action
    collapsed = any(s == "COLLAPSED" for s in st[t_act:H])
    stable_from = None
    if final_active:
        k = H - W
        while k > t_act and st[k - 1] == "ACTIVE":
            k -= 1
        stable_from = k
    label = "recovered" if final_active and not secondary and collapsed else "prevented" if final_active and not secondary else "secondary collapse" if secondary else "failed"
    return {"outcome": label, "success": label in ("recovered", "prevented"), "collapsed_after_action": collapsed, "secondary_collapse": secondary, "stable_from": stable_from, "latency": None if stable_from is None else max(0, stable_from - t_act)}


def costs(rec: dict, ref: dict, repairs: list[dict], t_act: int, H: int, stable_from: int | None) -> dict:
    """Raw costs of one run over the window from the action to ``H`` (measured from the traces), and the same costs normalised by the undamaged reference of the same seed. Nothing is weighted here."""
    T, R = rec["traces"], ref["traces"]
    lo = t_act
    win = min(H, len(T["t"])) - lo
    energy = sum(T["power_draw"][lo:lo + win])
    energy_ref = sum(R["power_draw"][lo:lo + win]) or 1.0
    # the resource the action added, as the resource mass present over the window (a run that is kept going consumes more; the reference is the undamaged run, so the number is not a pure 'added' amount)
    res = sum(T["resource_total"][lo:lo + win])
    res_ref = sum(R["resource_total"][lo:lo + win]) or 1.0
    steady = slice(stable_from, min(H, len(T["t"]))) if stable_from is not None else slice(lo, lo + win)
    p_rate = sum(T["power_draw"][steady]) / max(1, len(T["power_draw"][steady]))
    p_ref = sum(R["power_draw"][steady]) / max(1, len(R["power_draw"][steady])) or 1.0
    coll = {}
    for k in _COLLATERAL:
        a, b = T[k][lo:lo + win], R[k][lo:lo + win]
        scale = (sum(abs(x) for x in b) / max(1, len(b))) or 1.0
        coll[k] = round(sum(abs(x - y) for x, y in zip(a, b, strict=True)) / max(1, len(a)) / scale, 4)
    return {"raw": {"energy_use": round(energy, 4), "resource_mass": round(res, 4), "switching": len(repairs), "persistence_energy_rate": round(p_rate, 5), "collateral": round(sum(coll.values()) / len(coll), 4)},
            "normalised": {"energy_use": round(energy / energy_ref, 4), "resource_mass": round(res / res_ref, 4), "persistence_energy_rate": round(p_rate / p_ref, 5)}, "collateral_by_trace": coll}


def evaluate(rec: dict, ref: dict, repairs: list[dict], t_act: int = T_ACT) -> dict:
    """One run at the three horizons: the outcome, the latency, and the costs at the long horizon."""
    st = [f["status"] for f in rec["frames"]]
    out: dict[str, Any] = {"horizons": {}}
    for name, H in HORIZONS.items():
        o = outcome_at(st, H, t_act)
        res_end = rec["traces"]["resource_total"][min(H, len(st)) - 1]
        res_ref = ref["traces"]["resource_total"][min(H, len(st)) - 1] or 1.0
        o["resource_exhausted"] = res_end < 0.25 * res_ref  # a run that is ACTIVE on an exhausted field is not counted as recovered
        if o["resource_exhausted"]:
            o["success"] = False
            o["outcome"] = "failed (resource exhausted)"
        out["horizons"][name] = o
    lo = out["horizons"]["long"]
    out["costs"] = costs(rec, ref, repairs, t_act, HORIZONS["long"], lo["stable_from"])
    out["final_status"] = rec["final_status"]["label"]
    return out


def run_eval(stress: Stress | None, repairs: list[dict], seed: int, t_act: int = T_ACT, onset: int = STRESS_TICK) -> dict:
    rec = run(stress, repairs, seed, HORIZON, onset)
    return evaluate(rec, reference(seed), repairs, t_act)


# ---------------------------------------------------------------------------------------------------- failure taxonomy
FAILURE_IDS = {
    "no effective action": "NO_EFFECTIVE_ACTION", "no effective action at this setting (action too weak or the wrong target)": "NO_EFFECTIVE_ACTION", "action too weak": "ACTION_TOO_WEAK",
    "action too late": "ACTION_TOO_LATE", "action too late (after the collapse)": "ACTION_TOO_LATE", "overshoot": "OVERSHOOT", "secondary collapse (overshoot)": "OVERSHOOT",
    "secondary collapse": "SECONDARY_COLLAPSE", "detection failure": "DETECTION_FAILURE", "Address unresolved": "ADDRESS_UNRESOLVED",
    "insufficient resource": "INSUFFICIENT_RESOURCE", "insufficient resource (resource field exhausted)": "INSUFFICIENT_RESOURCE", "action cost too high": "EXCESSIVE_COST",
    "action destabilized system": "DESTABILIZED_BY_ACTION", "action destabilized the system (recovered short, not long)": "DESTABILIZED_BY_ACTION", "outside tested action space": "OUTSIDE_TESTED_ACTION_SPACE",
    "partial: effective on some seeds only": "SEED_DEPENDENT",
}
FAILURE_ID_LIST = ("NO_EFFECTIVE_ACTION", "ACTION_TOO_WEAK", "ACTION_TOO_LATE", "OVERSHOOT", "SECONDARY_COLLAPSE", "DETECTION_FAILURE", "ADDRESS_UNRESOLVED", "INSUFFICIENT_RESOURCE", "EXCESSIVE_COST", "DESTABILIZED_BY_ACTION", "OUTSIDE_TESTED_ACTION_SPACE", "SEED_DEPENDENT")  # SEED_DEPENDENT is an addition: a setting effective on some seeds only


def failure_id(text: str | None) -> str | None:
    return None if text in (None, "effective") else FAILURE_IDS.get(text, "NO_EFFECTIVE_ACTION")

