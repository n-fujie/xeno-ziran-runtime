"""MEOS-0 simulation core: a deterministic, seeded, discrete-time model of two operational configurations in one environment.

MEOS = Minimal Ecosystem Operational Shape. This module builds the first minimal ecosystem experiment, MEOS-0:

    Environment field F   a grid carrying a resource field R and two alteration (mark) fields M1, M2
    Operational entity A1 senses R, differentiates it from an adapted baseline, fires, acts on R and deposits M1
    Operational entity A2 senses M1, differentiates it, fires, acts: it moves to the alteration and reconfigures R from a finite power reserve
    Resource gradient R   a source gradient that is consumed, diffuses and is renewed only from the reserve
    Interaction relation I the alteration of the environment is the only way A2 detects A1; the reconfigured R is the only way A1 detects A2
    History H             a decaying trace per entity that, when it re-enters, lowers the next firing threshold

The recursion the model is asked about is

    sense -> differentiate -> fire -> act -> alter environment -> the other configuration detects the alteration -> fire -> act
          -> environmental reconfiguration -> history re-entry

A1 and A2 are not organisms, subjects, agents or minds: they are operational configurations (a sensing window, a threshold, a firing persistence,
an action rule) and nothing else. Their operational boundary is a property of the experiment (a set of components), not of a visible body.

Everything here is a model. The parameters were chosen so that the unperturbed run sustains the recursion; what every perturbation then does is
measured, not assumed. A result is a property of this model's operational relations, not of any physical or biological ecosystem.

Determinism: the only randomness is a small sensor noise drawn from ``numpy.random.default_rng(seed)`` in a fixed order; the same configuration,
seed and intervention list reproduce the same record bit for bit (the record carries its digest). Rendering never touches this module's state.
"""

from __future__ import annotations

import base64
import collections
import copy
import hashlib
import json
from typing import Any

import numpy as np

ENGINE_VERSION = "meos-0.5"
SCHEMA = "xzr.meos/1"
ENTITIES = ("A1", "A2")

# The reductions a researcher may apply (also the components the minimal-configuration search ranges over).
COMPONENTS = (
    "A2",
    "resource_gradient",
    "history",
    "interaction_channel",
    "sensor_resource",
    "sensor_alteration",
    "environmental_persistence",
    "feedback",
    "resource_renewal",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "schema": SCHEMA,
    "seed": 1,
    "horizon": 240,
    "grid": 14,
    "noise": 0.002,
    "init_jitter": 0.02,
    "environment": {
        "gradient": True,
        "r_max": 1.0,
        "gradient_length": 4.0,
        "r_flat": 0.25,
        "diffusion": 0.03,
        "relax": 0.06,
        "regrow": 0.02,
        "persistence": 0.10,
        "mark_diffusion": 0.20,
        "arena_radius": None,
    },
    "power": {"reserve": 24.0, "capacity": 24.0, "charge": 0.40, "infinite": False},
    "channels": {"sensor_resource": True, "sensor_alteration": True, "interaction": True, "feedback": True},
    "history": {"enabled": True, "mode": "removed", "gain": 1.0, "decay": 0.05, "kappa": 0.10, "theta_floor": 0.4},
    "sss": {"scale": 1.0, "size": 1.0, "speed": 1.0},
    "entities": {
        "A1": {
            "present": True,
            "pos": [3, 6],
            "sensor_radius": 2,
            "window": 6,
            "persist": 3,
            "refractory": 2,
            "speed": 1.0,
            "size": 1.0,
            "threshold": 0.20,
            "cost": 0.30,
            "consume": 0.35,
            "gain": 0.9,
            "deposit": 0.60,
            "upkeep": 0.02,
            "energy": 3.0,
            "energy_max": 6.0,
        },
        "A2": {
            "present": True,
            "pos": [5, 6],
            "sensor_radius": 2,
            "window": 6,
            "persist": 3,
            "refractory": 2,
            "speed": 1.0,
            "size": 1.0,
            "threshold": 0.05,
            "cost": 0.25,
            "renew": 0.5,
            "deposit": 0.25,
        },
    },
}

# Parameters a RECONFIGURE / ALTER_* intervention may set (dotted path -> (low, high)); anything else is refused.
SETTABLE: dict[str, tuple[float, float]] = {
    "environment.diffusion": (0.0, 0.5),
    "environment.relax": (0.0, 0.5),
    "environment.regrow": (0.0, 0.2),
    "environment.persistence": (0.0, 1.0),
    "environment.mark_diffusion": (0.0, 0.5),
    "environment.arena_radius": (1, 14),
    "environment.gradient_length": (0.5, 20),
    "power.charge": (0.0, 3.0),
    "power.reserve": (0.0, 200.0),
    "history.kappa": (0.0, 0.5),
    "history.decay": (0.0, 1.0),
    "sss.scale": (0.25, 4.0),
    "sss.size": (0.25, 4.0),
    "sss.speed": (0.25, 4.0),
    "noise": (0.0, 0.2),
    "environment.renew_efficiency": (
        0.1,
        2.0,
    ),  # the share of A2's renewal that reaches the field: an environmental regime parameter (absent = 1)
}
for _e in ENTITIES:
    for _k, _r in {
        "sensor_radius": (0, 8),
        "window": (1, 60),
        "persist": (1, 20),
        "refractory": (0, 40),
        "speed": (0.25, 4.0),
        "size": (0.25, 4.0),
        "threshold": (0.001, 2.0),
    }.items():
        SETTABLE[f"entities.{_e}.{_k}"] = _r
    SETTABLE[f"entities.{_e}.x"] = (0, 13)
    SETTABLE[f"entities.{_e}.y"] = (0, 13)

# Fifth-stage parameters (all absent from the default configuration, so a run that does not set them is the run of the earlier stages)
SETTABLE["coupling.gain"] = (0.0, 2.0)  # the share of A1's alteration M1 that A2's sensor receives (a weakened or strengthened coupling; absent = 1)
SETTABLE["environment.renew_delay"] = (0, 40)  # ticks between A2's renewal action and the renewed resource reaching the field (absent = 0)
SETTABLE["history.lag"] = (0, 40)  # ticks of delay of the history trace that lowers a threshold (absent = 0)
SETTABLE["entities.A2.renew"] = (0.05, 3.0)  # how much resource A2 transfers per action step (a configuration parameter of A2)
SETTABLE["coupling.bypass"] = (0.0, 1.0)  # sixth-stage follow-up: a second path for A1's alteration to reach A2, beside ``coupling.gain`` (absent = 0, no bypass)

OPS = (
    "REMOVE",
    "ISOLATE",
    "RECONNECT",
    "RECONFIGURE",
    "CHANGE_BOUNDARY",
    "DISABLE_HISTORY",
    "ALTER_SSS",
    "ALTER_RESOURCE",
    "ADDRESS",
    "ROUTE",
)
ADDRESS_MODES = ("loss", "reassign", "fragment", "collision", "partial", "restore", "delayed", "stale")
ADDRESS_MODES_REPAIR = ("temporary",)  # sixth-stage follow-up (kept apart from ADDRESS_MODES: the experiments that range over the fault modes are unchanged)
M2_SENSE = ("none", "direct", "delayed", "noisy", "threshold")
PHIL_MODES = ("none", "expression", "scorekeeping", "revision")


class MeosError(ValueError):
    pass


def default_config(**over: Any) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj: Any) -> str:
    return hashlib.sha256(_canon(obj).encode()).hexdigest()


def _get(cfg: dict, path: str) -> Any:
    node = cfg
    for p in path.split("."):
        node = node[p]
    return node


def _set(cfg: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    node = cfg
    for p in parts[:-1]:
        node = node.setdefault(p, {}) if p == "coupling" else node[p]  # ``coupling`` is an optional block: created when first set
    node[parts[-1]] = value


def validate_config(cfg: dict) -> list[str]:
    issues = []
    if cfg.get("schema") != SCHEMA:
        issues.append(f"schema must be {SCHEMA!r}")
    n = cfg.get("grid")
    if not (isinstance(n, int) and 8 <= n <= 24):
        issues.append("grid must be an integer in 8..24")
    if not (isinstance(cfg.get("horizon"), int) and 1 <= cfg["horizon"] <= 1200):
        issues.append("horizon must be an integer in 1..1200")
    if not isinstance(cfg.get("seed"), int):
        issues.append("seed must be an integer")
    m2 = cfg.get("m2")
    if m2 is not None and not (isinstance(m2, dict) and m2.get("sense", "none") in M2_SENSE):
        issues.append(f"m2.sense must be one of {M2_SENSE}")
    if isinstance(m2, dict) and "threshold" in m2 and not (isinstance(m2["threshold"], int | float) and 0 <= m2["threshold"] <= 2):
        issues.append("m2.threshold must be a number in 0..2")
    ph = cfg.get("phil")
    if ph is not None and not (isinstance(ph, dict) and ph.get("mode", "none") in PHIL_MODES):
        issues.append(f"phil.mode must be one of {PHIL_MODES}")
    acc = cfg.get("history", {}).get("access")
    if acc is not None and not (isinstance(acc, dict) and set(acc) <= set(ENTITIES)):
        issues.append("history.access must map A1 / A2 to booleans")
    for e in ENTITIES:
        ent = cfg.get("entities", {}).get(e)
        if not isinstance(ent, dict):
            issues.append(f"entities.{e} missing")
            continue
        x, y = ent.get("pos", [None, None])
        if not (isinstance(x, int) and isinstance(y, int) and 0 <= x < (n or 0) and 0 <= y < (n or 0)):
            issues.append(f"entities.{e}.pos must be integer cell coordinates inside the grid")
    return issues


def validate_interventions(ivs: list[dict], horizon: int) -> list[str]:
    issues = []
    if len(ivs) > 64:
        issues.append("at most 64 interventions per run")
    for i, iv in enumerate(ivs):
        if not isinstance(iv, dict) or iv.get("op") not in OPS:
            issues.append(f"interventions[{i}].op must be one of {OPS}")
            continue
        t = iv.get("tick")
        if not (isinstance(t, int) and 0 <= t < horizon):
            issues.append(f"interventions[{i}].tick must be an integer in 0..{horizon - 1}")
        op, tgt = iv["op"], iv.get("target")
        if op in ("REMOVE", "ISOLATE", "RECONNECT") and tgt not in COMPONENTS and tgt not in ("A1", "A2"):
            issues.append(f"interventions[{i}].target must be a component: {COMPONENTS}")
        if op == "RECONFIGURE" and iv.get("path") not in SETTABLE:
            issues.append(f"interventions[{i}].path is not a settable parameter")
        if op == "RECONFIGURE" and iv.get("path") in SETTABLE:
            lo, hi = SETTABLE[iv["path"]]
            v = iv.get("value")
            if not (isinstance(v, int | float) and not isinstance(v, bool) and lo <= v <= hi):
                issues.append(f"interventions[{i}].value must be a number in {lo}..{hi}")
        if op == "ROUTE":
            m2r, hr = iv.get("m2"), iv.get("history")
            if m2r is None and hr is None:
                issues.append(f"interventions[{i}] ROUTE needs an m2 block and / or a history setting")
            if m2r is not None and not (isinstance(m2r, dict) and m2r.get("sense", "none") in M2_SENSE):
                issues.append(f"interventions[{i}].m2.sense must be one of {M2_SENSE}")
            if hr is not None and hr not in ("on", "off"):
                issues.append(f"interventions[{i}].history must be on or off")
        if op == "CHANGE_BOUNDARY" and not (isinstance(iv.get("arena_radius"), int) and 1 <= iv["arena_radius"] <= 14):
            issues.append(f"interventions[{i}].arena_radius must be an integer in 1..14")
        if op == "ADDRESS":
            mode = iv.get("mode")
            if mode not in (*ADDRESS_MODES, *ADDRESS_MODES_REPAIR) or iv.get("target") not in (*ENTITIES, "both"):
                issues.append(f"interventions[{i}] needs mode in {(*ADDRESS_MODES, *ADDRESS_MODES_REPAIR)} and target A1 / A2 / both")
            elif mode == "temporary" and not (isinstance(iv.get("duration"), int) and 1 <= iv["duration"] <= 400):
                issues.append(f"interventions[{i}] temporary needs an integer duration in 1..400 ticks")
            elif mode in ("reassign", "delayed") and not all(isinstance(iv.get(k), int) and 0 <= iv[k] < 24 for k in ("x", "y")):
                issues.append(f"interventions[{i}] {mode} needs integer cell x, y")
            elif mode == "delayed" and not (isinstance(iv.get("delay"), int) and 1 <= iv["delay"] <= 100):
                issues.append(f"interventions[{i}] delayed needs an integer delay in 1..100 ticks")
            elif mode == "stale" and "duration" in iv and not (isinstance(iv["duration"], int) and 1 <= iv["duration"] <= 400):
                issues.append(f"interventions[{i}] stale takes an optional integer duration in 1..400 ticks")
            elif mode in ("fragment", "partial") and not (
                isinstance(iv.get("fraction"), int | float) and 0 <= iv["fraction"] <= 1
            ):
                issues.append(f"interventions[{i}] {mode} needs fraction in 0..1")
        if op == "ALTER_SSS" and not any(k in iv for k in ("scale", "size", "speed")):
            issues.append(f"interventions[{i}] needs scale, size or speed")
        if op == "ALTER_RESOURCE" and "inject" in iv:
            inj = iv["inject"]
            ok = isinstance(inj, dict) and all(
                isinstance(inj.get(k), int | float) and not isinstance(inj.get(k), bool) for k in ("x", "y", "amount")
            )
            ok = ok and 0 <= inj["x"] < 24 and 0 <= inj["y"] < 24 and 0 < inj["amount"] <= 20
            if not ok:
                issues.append(
                    f"interventions[{i}].inject must be {{x, y, amount}} with a cell inside the grid and 0 < amount <= 20"
                )
        elif op == "ALTER_RESOURCE" and "reroute" in iv:
            rr = iv["reroute"]
            ok = isinstance(rr, dict) and all(isinstance(rr.get(k), dict) for k in ("from", "to"))
            ok = ok and all(isinstance(rr[k].get(c), int) and not isinstance(rr[k].get(c), bool) and 0 <= rr[k][c] < 24 for k in ("from", "to") for c in ("x", "y"))
            ok = ok and isinstance(rr.get("rate"), int | float) and not isinstance(rr.get("rate"), bool) and 0 < rr["rate"] <= 1
            ok = ok and isinstance(rr.get("duration"), int) and 1 <= rr["duration"] <= 400
            if not ok:
                issues.append(f"interventions[{i}].reroute must be {{from: {{x, y}}, to: {{x, y}}, rate: 0 < rate <= 1, duration: 1..400}} with cells inside the grid")
        elif op == "ALTER_RESOURCE" and iv.get("path") not in SETTABLE:
            issues.append(f"interventions[{i}].path is not a settable resource parameter")
    return issues


class Run:
    """One run: configuration + interventions -> state per tick. ``step`` advances one environment tick."""

    def __init__(self, config: dict, interventions: list[dict] | None = None):
        issues = validate_config(config) + validate_interventions(interventions or [], config.get("horizon", 0) or 0)
        if issues:
            raise MeosError("; ".join(issues))
        self.initial_config = copy.deepcopy(config)
        self.cfg = copy.deepcopy(config)
        self.interventions = sorted(copy.deepcopy(interventions or []), key=lambda iv: (iv["tick"], _canon(iv)))
        self.n = self.cfg["grid"]
        self.rng = np.random.default_rng(self.cfg["seed"])
        self.t = 0
        self.next_id = 1
        env = self.cfg["environment"]
        n = self.n
        xs = np.arange(n, dtype=float)
        base = env["r_max"] * np.exp(-xs / env["gradient_length"]) if env["gradient"] else np.full(n, env["r_flat"])
        self.R = np.tile(base[:, None], (1, n)).astype(float)  # R[x, y]: a gradient along x, source at x = 0
        self.R *= 1.0 + self.cfg["init_jitter"] * self.rng.standard_normal((n, n))  # the seed's only effect on the initial state
        self.R0 = self.R.copy()  # the field the resource relaxes toward (the environment's own gradient)
        self.R0_gradient = self.R.copy()
        self.M1 = np.zeros((n, n))
        self.M2 = np.zeros((n, n))
        self.prov_m1 = np.zeros((n, n), dtype=int)  # id of the latest deposit event per cell (causal provenance)
        self.prov_r = np.zeros((n, n), dtype=int)  # id of the latest renewal event per cell
        self.power = float(self.cfg["power"]["reserve"])
        self.ent: dict[str, dict] = {}
        for name in ENTITIES:
            c = self.cfg["entities"][name]
            self.ent[name] = {
                "present": bool(c["present"]),
                "x": int(c["pos"][0]),
                "y": int(c["pos"][1]),
                "energy": float(c.get("energy", 0.0)),
                "baseline": 0.0,
                "h": 0.0,  # history trace (kept also when it does not re-enter, as h_shadow)
                "active": 0,  # remaining ticks of the current firing (persistence)
                "cool": 0,  # ticks until it may fire again (refractory)
                "fires": 0,
                "last_fire": None,
                "last_fire_id": None,
                "last_expire": None,
                "move_acc": 0.0,
                "d": 0.0,
                "s": 0.0,
                "s0": 0.0,
                "theta": c["threshold"],
                "fired_now": False,
                "reentry_now": 0.0,
                "last_eval": [],
                "failed": None,
            }
        self._last_ad: dict | None = None
        self.events: list[dict] = []
        self.ev_tick: dict[int, int] = {}
        self.cycles: list[dict] = []
        self.status_log: list[dict] = []
        self.frames: list[dict] = []
        self.field_bytes = bytearray()
        self.intervention_log: list[dict] = []
        self.status: dict[str, Any] = {"label": "DEGRADED", "reason": "forming", "dependency": None, "cycles_in_window": 0}
        self.pending_chain: dict[int, dict] = {}  # fire-event id -> chain info for cycle detection
        self.end_reason: str | None = None
        # optional features: all inert unless configured or intervened, and none of them draws from the main random stream
        self.rng_aux = np.random.default_rng(int(self.cfg["seed"]) + 104729)
        self.addr: dict[str, dict] = {name: {"mode": None, "fraction": 1.0, "mask": None} for name in ENTITIES}
        self.addr_events = 0
        self.reroutes: list[dict] = []  # resource transport rerouted by an intervention: {from, to, rate, until} (empty unless intervened)
        self.m2_hist: collections.deque = collections.deque(maxlen=64)
        self.h_hist: dict[str, collections.deque] = {name: collections.deque(maxlen=64) for name in ENTITIES}  # history trace per tick (for a delayed history)
        self.renew_queue: list[tuple[int, tuple, float]] = []  # (due tick, cells, amount per cell) of renewals not yet delivered (a delayed renewal)
        self.m2_sensed = 0.0  # what A1's M2 tap added to its sensor signal at the latest evaluation (recorded as a trace only when M2 sensing is configured)
        self.tick_acc: dict[str, float] = {}
        self.traces: dict[str, list] = collections.defaultdict(list)
        self.phil = None
        if (self.cfg.get("phil") or {}).get("mode", "none") != "none":
            from .phil import PhilOps

            self.phil = PhilOps(self)
        self._apply_due()  # tick-0 interventions are part of the initial configuration
        self._record(first=True)

    # ------------------------------------------------------------------------------------------------ helpers
    def _acc(self, key: str, amount: float = 1.0) -> None:
        self.tick_acc[key] = self.tick_acc.get(key, 0.0) + amount

    def _renew_efficiency(self) -> float:
        return float(self.cfg["environment"].get("renew_efficiency", 1.0))

    def _cell(self, name: str) -> tuple[int, int]:
        """The cell a configuration senses and acts at: its own position, or, while its address is stale or its update is delayed, the cell its address still names."""
        at = self.addr[name].get("at")
        return (int(at[0]), int(at[1])) if at is not None else (self.ent[name]["x"], self.ent[name]["y"])

    def _expire_addresses(self) -> None:
        """A delayed address update arrives, or a stale address's duration ends: the address names the configuration's own position again."""
        for name in ENTITIES:
            a = self.addr[name]
            if a.get("temp_until") is not None and self.t >= a["temp_until"]:
                prior = a.pop("prior")
                a.pop("temp_until")
                if prior.get("until") is not None and self.t >= prior["until"]:  # the fault it would have returned to has ended meanwhile
                    prior = dict(mode=None, fraction=1.0, mask=None, at=None, until=None)
                a.update(prior)
                self._event("address_update", name, action="the temporary local address ends: the address state returns")
                continue
            if a.get("until") is not None and self.t >= a["until"]:
                a.update(mode=None, fraction=1.0, mask=None, at=None, until=None)
                self._event("address_update", name, action="the address is updated to the configuration's position")

    def _addressable(self, name: str) -> bool:
        return self.addr[name]["mode"] != "loss"

    def _partial_ok(self, name: str) -> bool:
        """Partial addressability: each sensing or action step reaches its address with probability ``fraction`` (its own random stream)."""
        a = self.addr[name]
        return a["mode"] != "partial" or bool(self.rng_aux.random() < a["fraction"])

    def _eid(self) -> int:
        i = self.next_id
        self.next_id += 1
        return i

    def _event(self, kind: str, actor: str | None, **kw: Any) -> dict:
        e = {"id": self._eid(), "tick": self.t, "kind": kind, "actor": actor, **kw}
        self.events.append(e)
        self.ev_tick[e["id"]] = self.t
        return e

    def _scaled_radius(self, name: str) -> int:
        c = self.cfg["entities"][name]
        return max(0, int(round(c["sensor_radius"] * self.cfg["sss"]["scale"])))

    def _footprint(self, name: str) -> int:
        c = self.cfg["entities"][name]
        return max(0, int(round(c["size"] * self.cfg["sss"]["size"])) - 1)

    def _speed(self, name: str) -> float:
        return float(self.cfg["entities"][name]["speed"]) * float(self.cfg["sss"]["speed"])

    def _clock(self, name: str, key: str) -> int:
        """A temporal parameter in environment ticks: speed is the ratio of the configuration's process clock to the environment's, so a faster
        configuration has a shorter sensing window, firing persistence and refractory period."""
        v = self.cfg["entities"][name][key] / max(1e-9, self._speed(name))
        return max(0 if key == "refractory" else 1, int(round(v)))

    def _window(self, f: np.ndarray, x: int, y: int, r: int) -> np.ndarray:
        n = self.n
        return f[max(0, x - r) : min(n, x + r + 1), max(0, y - r) : min(n, y + r + 1)]

    def _in_arena(self, x: int, y: int) -> bool:
        ar = self.cfg["environment"]["arena_radius"]
        if ar is None:
            return True
        c = (self.n - 1) / 2
        return max(abs(x - c), abs(y - c)) <= ar

    def _clamp_arena(self, x: int, y: int) -> tuple[int, int]:
        ar = self.cfg["environment"]["arena_radius"]
        x, y = min(self.n - 1, max(0, x)), min(self.n - 1, max(0, y))
        if ar is None:
            return x, y
        c = (self.n - 1) / 2
        lo, hi = int(np.ceil(c - ar)), int(np.floor(c + ar))
        return min(hi, max(lo, x)), min(hi, max(lo, y))

    # ------------------------------------------------------------------------------------------------ interventions
    def _apply_due(self) -> None:
        for iv in [i for i in self.interventions if i["tick"] == self.t]:
            self._apply(iv)

    def _remove_component(self, comp: str, restore: bool = False) -> None:
        cfg = self.cfg
        on = restore
        if comp == "A2":
            self.ent["A2"]["present"] = on
            cfg["entities"]["A2"]["present"] = on
        elif comp == "A1":
            self.ent["A1"]["present"] = on
            cfg["entities"]["A1"]["present"] = on
        elif comp == "resource_gradient":
            cfg["environment"]["gradient"] = on
            if not on:  # flatten to the mean level: the resource stays, its gradient goes
                self.R0[:] = self.R0_gradient.mean()
                self.R[:] = self.R.mean()
            else:
                self.R0[:] = self.R0_gradient
        elif comp == "history":
            cfg["history"]["enabled"] = on
        elif comp == "interaction_channel":
            cfg["channels"]["interaction"] = on
        elif comp == "sensor_resource":
            cfg["channels"]["sensor_resource"] = on
        elif comp == "sensor_alteration":
            cfg["channels"]["sensor_alteration"] = on
        elif comp == "environmental_persistence":
            cfg["environment"]["persistence"] = DEFAULT_CONFIG["environment"]["persistence"] if on else 1.0
        elif comp == "feedback":
            cfg["channels"]["feedback"] = on
        elif comp == "resource_renewal":
            cfg["environment"]["regrow"] = DEFAULT_CONFIG["environment"]["regrow"] if on else 0.0
            cfg["power"]["charge"] = DEFAULT_CONFIG["power"]["charge"] if on else 0.0

    def _apply(self, iv: dict) -> None:
        op, cfg = iv["op"], self.cfg
        detail: dict[str, Any] = {}
        if op in ("REMOVE", "ISOLATE"):
            tgt = iv["target"]
            self._remove_component(tgt, restore=False)
            detail = {"target": tgt}
        elif op == "RECONNECT":
            self._remove_component(iv["target"], restore=True)
            detail = {"target": iv["target"]}
        elif op == "ALTER_RESOURCE" and "inject" in iv:
            inj = iv["inject"]  # a resource pulse: material inserted into the environment at a cell
            self.R[int(inj["x"]), int(inj["y"])] += float(inj["amount"])
            detail = {"inject": {"x": int(inj["x"]), "y": int(inj["y"]), "amount": float(inj["amount"])}}
        elif op == "ALTER_RESOURCE" and "reroute" in iv:
            rr = iv["reroute"]  # a conduit: for ``duration`` ticks a share ``rate`` of the resource in one cell is moved to another (mass is moved, not created)
            fx, fy, tx, ty = (int(rr[k][c]) for k in ("from", "to") for c in ("x", "y"))
            self.reroutes.append({"from": (fx, fy), "to": (tx, ty), "rate": float(rr["rate"]), "until": self.t + int(rr["duration"])})
            detail = {"reroute": {"from": {"x": fx, "y": fy}, "to": {"x": tx, "y": ty}, "rate": float(rr["rate"]), "duration": int(rr["duration"])}}
        elif op in ("RECONFIGURE", "ALTER_RESOURCE"):
            path, v = iv["path"], iv["value"]
            if path.endswith((".x", ".y")):
                _, name, axis = path.split(".")
                ent = self.ent[name]
                ent[axis] = int(v)
                cfg["entities"][name]["pos"][0 if axis == "x" else 1] = int(v)
            else:
                _set(cfg, path, v)
            if path == "power.reserve":
                self.power = float(v)
            detail = {"path": path, "value": v}
        elif op == "CHANGE_BOUNDARY":
            cfg["environment"]["arena_radius"] = iv["arena_radius"]
            for name in ENTITIES:
                e = self.ent[name]
                e["x"], e["y"] = self._clamp_arena(e["x"], e["y"])
            detail = {"arena_radius": iv["arena_radius"]}
        elif op == "DISABLE_HISTORY":
            cfg["history"]["enabled"] = False
            if iv.get("mode") in ("removed", "prevented"):
                cfg["history"]["mode"] = iv["mode"]
            detail = {"mode": cfg["history"]["mode"]}
        elif op == "ALTER_SSS":
            for k in ("scale", "size", "speed"):
                if k in iv:
                    cfg["sss"][k] = float(iv[k])
            detail = {k: cfg["sss"][k] for k in ("scale", "size", "speed")}
        elif op == "ADDRESS":
            detail = self._apply_address(iv)
        elif op == "ROUTE":
            # a change of the operational route: which of M2 sensing and history re-entry is in use (the configuration's own components are unchanged); the optional
            # metadata of a controller (``why``, ``from``, ``to``, ``cost``) is kept in the log and read by nothing in the engine
            if "m2" in iv:
                cfg["m2"] = dict(iv["m2"])
                detail["m2"] = dict(iv["m2"])
            if "history" in iv:
                cfg["history"]["enabled"] = iv["history"] == "on"
                detail["history"] = iv["history"]
            detail.update({k: iv[k] for k in ("why", "from", "to", "cost", "trigger") if k in iv})
        e = self._event("intervention", None, op=op, **detail)
        self.intervention_log.append({"tick": self.t, "op": op, "event": e["id"], **detail})

    def _apply_address(self, iv: dict) -> dict:
        """Address Domain interventions: loss (the configuration can no longer address the field: it senses nothing and its actions reach nothing),
        reassignment (a new address, state kept), fragmentation (only a fraction of its sensing window remains addressable), collision (it is
        assigned the other configuration's address), partial addressability (each step reaches its address with a probability) and restoration."""
        mode = iv["mode"]
        names = ENTITIES if iv["target"] == "both" else (iv["target"],)
        self.addr_events += 1
        for name in names:
            a, e = self.addr[name], self.ent[name]
            if a.get("temp_until") is not None:  # a later address intervention ends a temporary local address; the state it would have returned to is kept
                a.update(a.pop("prior"))
                a.pop("temp_until")
            if mode == "temporary":
                # a local address for a bounded time: the configuration is fully addressable for ``duration`` ticks, then the address state it had returns
                a["prior"] = {k: a.get(k) for k in ("mode", "fraction", "mask", "at", "until")}
                a["temp_until"] = self.t + int(iv["duration"])
                a.update(mode=None, fraction=1.0, mask=None, at=None, until=None)
            elif mode == "restore":
                a.update(mode=None, fraction=1.0, mask=None, at=None, until=None)
            elif mode == "loss":
                a.update(mode="loss", fraction=0.0, mask=None)
            elif mode == "reassign":
                e["x"], e["y"] = self._clamp_arena(int(iv["x"]), int(iv["y"]))
                self.cfg["entities"][name]["pos"] = [e["x"], e["y"]]
                a.update(mode=None, fraction=1.0, mask=None, at=None, until=None)
            elif mode == "delayed":
                # the body moves at once; the address that names where it is arrives ``delay`` ticks later: until then it names the old cell
                a.update(mode="delayed", fraction=1.0, mask=None, at=(e["x"], e["y"]), until=self.t + int(iv["delay"]))
                e["x"], e["y"] = self._clamp_arena(int(iv["x"]), int(iv["y"]))
                self.cfg["entities"][name]["pos"] = [e["x"], e["y"]]
            elif mode == "stale":
                # the address stops following the configuration: it keeps naming the cell the configuration was in when this began
                a.update(mode="stale", fraction=1.0, mask=None, at=(e["x"], e["y"]), until=(self.t + int(iv["duration"])) if "duration" in iv else None)
            elif mode == "collision":
                other = self.ent["A1" if name == "A2" else "A2"]
                e["x"], e["y"] = other["x"], other["y"]
            elif mode == "fragment":
                g = np.random.default_rng(int(self.cfg["seed"]) * 1000 + self.t * 10 + self.addr_events)
                a.update(mode="fragment", fraction=float(iv["fraction"]), mask=g.random((self.n, self.n)) < float(iv["fraction"]))
            elif mode == "partial":
                a.update(mode="partial", fraction=float(iv["fraction"]), mask=None)
        return {"address_mode": mode, "target": iv["target"], **{k: iv[k] for k in ("x", "y", "fraction", "delay", "duration") if k in iv}}

    # ------------------------------------------------------------------------------------------------ one tick
    def _history_theta(self, name: str, theta0: float) -> tuple[float, float]:
        h = self.cfg["history"]
        if not h["enabled"] or not (h.get("access") or {}).get(name, True):
            return theta0, 0.0
        floor = h["theta_floor"] * theta0  # history can lower a threshold, never remove it
        lag = int(h.get("lag", 0))
        trace = self.ent[name]["h"] if lag <= 0 else (self.h_hist[name][-lag] if len(self.h_hist[name]) >= lag else 0.0)
        theta = max(floor, theta0 - h["kappa"] * trace)
        return theta, theta0 - theta

    def _evaluate(self, name: str) -> dict:
        """The sensing, differentiation and preconditions of one entity at this tick; nothing is changed except its adapted baseline."""
        c, e = self.cfg["entities"][name], self.ent[name]
        ch = self.cfg["channels"]
        checks: list[dict] = []

        def chk(label: str, ok: bool, value: Any = None, need: Any = None) -> None:
            checks.append({"precondition": label, "ok": bool(ok), "value": value, "need": need})

        chk("present", e["present"])
        if not e["present"]:
            return {"fire": False, "checks": checks}
        x, y = self._cell(name)
        r = self._scaled_radius(name)
        if name == "A1":
            chan_ok = ch["sensor_resource"]
            field = self.R
        else:
            chan_ok = ch["sensor_alteration"] and ch["interaction"]
            field = self.M1
        chk("sensor channel connected", chan_ok)
        a = self.addr[name]
        if a["mode"] is not None:  # Address Domain faults: a configuration that cannot address the field senses nothing there
            chan_ok = chan_ok and self._addressable(name) and self._partial_ok(name)
            chk("addressable", self._addressable(name))
        win = self._window(field, x, y, r)
        if a["mode"] == "fragment":
            win = np.where(self._window(a["mask"], x, y, r), win, 0.0)
        s0 = float(win.max()) if chan_ok and win.size else 0.0  # a peak detector over the sensing window
        if name == "A2":
            gain = float((self.cfg.get("coupling") or {}).get("gain", 1.0))
            if gain != 1.0:  # a weakened (or strengthened) coupling: what A2 receives of A1's alteration
                s0 *= gain
            bypass = float((self.cfg.get("coupling") or {}).get("bypass", 0.0))
            if bypass > 0.0 and chan_ok and self.ent["A1"]["present"]:  # a second path: a share ``bypass`` of what is peaked in A1's own sensing window reaches A2 without the coupling
                a1 = self.ent["A1"]
                w1 = self._window(self.M1, a1["x"], a1["y"], r)
                if w1.size:
                    s0 = max(s0, bypass * float(w1.max()))
        if chan_ok and name == "A1":
            self.m2_sensed = self._m2_signal(x, y, r)
            s0 += self.m2_sensed
        s = s0 + (float(self.rng.normal(0.0, self.cfg["noise"])) if chan_ok else 0.0)
        e["s0"] = s0
        d = s - e["baseline"]
        theta, red = self._history_theta(name, c["threshold"])
        e["s"], e["d"], e["theta"], e["reentry_now"] = s, d, theta, red
        chk("differentiated stimulus >= threshold", d >= theta, round(d, 4), round(theta, 4))
        if name == "A1":
            chk("energy >= firing cost", e["energy"] >= c["cost"], round(e["energy"], 3), c["cost"])
        else:
            chk(
                "power reserve >= firing cost",
                self.cfg["power"]["infinite"] or self.power >= c["cost"],
                round(self.power, 3),
                c["cost"],
            )
        chk("not active or refractory", e["active"] == 0 and e["cool"] == 0, e["cool"], 0)
        chk("inside the spatial boundary", self._in_arena(x, y))
        fire = all(k["ok"] for k in checks)
        # the adapted baseline moves toward the stimulus over the temporal window: the entity responds to difference
        if chan_ok:
            e["baseline"] += (s - e["baseline"]) / self._clock(name, "window")
        return {"fire": fire, "checks": checks, "s": s, "d": d, "theta": theta, "red": red}

    LAG_MAX = 6  # a firing is attributed to an event of the other configuration only if that event touched its sensor window within this many ticks

    def _m2_signal(self, x: int, y: int, r: int) -> float:
        """A1's optional sensing of A2's alteration M2 (default: none). Direct, delayed (the field ``delay`` ticks ago) or noisy (its own random stream)."""
        m2 = self.cfg.get("m2") or {}
        sense = m2.get("sense", "none")
        if sense == "none":
            return 0.0
        if sense == "delayed":
            d = int(m2.get("delay", 3))
            if len(self.m2_hist) < d:
                return 0.0
            field = self.m2_hist[-d]
        else:
            field = self.M2
        v = float(self._window(field, x, y, r).max())
        if sense == "noisy":
            v = max(0.0, v + float(self.rng_aux.normal(0.0, float(m2.get("noise", 0.05)))))
        if sense == "threshold" and v < float(m2.get("threshold", 0.05)):  # a thresholded tap passes only a variation above the threshold
            v = 0.0
        return float(m2.get("weight", 0.5)) * v

    def _source_event(self, name: str, signal: float) -> int | None:
        """The event of the other configuration this firing is causally attributed to, or None: the latest event that touched the sensor window
        within LAG_MAX ticks, provided the sensed signal itself (before sensor noise) rose above the noise."""
        if signal < 2.0 * self.cfg["noise"]:
            return None
        r = self._scaled_radius(name)
        prov = self.prov_r if name == "A1" else self.prov_m1
        cx, cy = self._cell(name)
        ident = int(self._window(prov, cx, cy, r).max())
        if ident == 0 or self.t - self.ev_tick[ident] > self.LAG_MAX:
            return None
        return ident

    def _move_toward(self, name: str, field: np.ndarray) -> None:
        e = self.ent[name]
        e["move_acc"] += self._speed(name)
        steps = int(e["move_acc"])
        e["move_acc"] -= steps
        r = max(1, self._scaled_radius(name))
        for _ in range(steps):
            x, y = e["x"], e["y"]
            win = self._window(field, x, y, r)
            if win.size == 0 or win.max() <= field[x, y] + 1e-9:
                break
            x0, y0 = max(0, x - r), max(0, y - r)
            ix, iy = np.unravel_index(int(np.argmax(win)), win.shape)
            tx, ty = x0 + ix, y0 + iy
            nx, ny = x + int(np.sign(tx - x)), y + int(np.sign(ty - y))
            e["x"], e["y"] = self._clamp_arena(nx, ny)

    def _blocked(self, name: str, fid: int) -> bool:
        """An action that cannot reach its address (lost, or a partial step that missed) has no effect on the environment; the firing still ran."""
        if self.addr[name]["mode"] is None or (self._addressable(name) and self._partial_ok(name)):
            return False
        cx, cy = self._cell(name)
        self._event("act", name, action="blocked: not addressable", fire=fid, cell=[cx, cy])
        return True

    def _act_a1(self, fid: int) -> None:
        if self._blocked("A1", fid):
            return
        e, c = self.ent["A1"], self.cfg["entities"]["A1"]
        fp = self._footprint("A1")
        size = float(c["size"]) * self.cfg["sss"]["size"]
        x, y = self._cell("A1")
        reg = (slice(max(0, x - fp), min(self.n, x + fp + 1)), slice(max(0, y - fp), min(self.n, y + fp + 1)))
        want = c["consume"] * size
        avail = float(self.R[reg].sum())
        take = min(want, avail)
        if avail > 0:
            self.R[reg] -= self.R[reg] * (take / avail)
        self._acc("consumed", take)
        e["energy"] = min(c["energy_max"], e["energy"] + c["gain"] * take)
        dep = c["deposit"] * (take / max(want, 1e-9)) * size
        self.M1[reg] += dep / self.R[reg].size
        ev = self._event(
            "act", "A1", action="consume+deposit", consumed=round(take, 4), deposited=round(dep, 4), fire=fid, cell=[x, y]
        )
        self.prov_m1[reg] = ev["id"]

    def _act_a2(self, fid: int) -> None:
        if self._blocked("A2", fid):
            return
        c = self.cfg["entities"]["A2"]
        self._move_toward("A2", self.M1)
        fp = self._footprint("A2")
        size = float(c["size"]) * self.cfg["sss"]["size"]
        x, y = self._cell("A2")
        reg = (slice(max(0, x - fp), min(self.n, x + fp + 1)), slice(max(0, y - fp), min(self.n, y + fp + 1)))
        self.M2[reg] += c["deposit"] / self.M2[reg].size
        amt = 0.0
        if self.cfg["channels"]["feedback"]:
            want = c["renew"] * size * (self.phil.boost if self.phil else 1.0)
            amt = want if self.cfg["power"]["infinite"] else min(want, self.power)
            if not self.cfg["power"]["infinite"]:
                self.power -= amt
            eff = self._renew_efficiency()
            # reconfigure the environment around A1's reach: the renewed resource is placed where this configuration is
            delay = int(self.cfg["environment"].get("renew_delay", 0))
            if delay > 0:
                self.renew_queue.append((self.t + delay, reg, amt * eff / self.R[reg].size))
            else:
                self.R[reg] += amt * eff / self.R[reg].size
            self._acc("renewed", amt * eff)
            self._acc("renew_requested", amt)
            self._acc("power_renew", amt)
            self._acc("renewal_events")
            if self.phil:
                self.phil.on_renewal(self, amt, eff)
        ev = self._event("act", "A2", action="reconfigure", renewed=round(amt, 4), fire=fid, cell=[x, y])
        if amt > 0:
            self.prov_r[reg] = ev["id"]
            if fid in self.pending_chain:
                self.pending_chain[fid].setdefault("reconfigs", []).append(
                    ev["id"]
                )  # the middle leg of the chain started by this firing

    def _fire(self, name: str, ev_info: dict) -> dict:
        e, c = self.ent[name], self.cfg["entities"][name]
        src = self._source_event(name, e["s0"])
        refire = e["last_expire"] is not None
        fe = self._event(
            "fire",
            name,
            refire=refire,
            source=src,
            stimulus=round(e["s"], 4),
            baseline=round(e["baseline"], 4),
            differentiated=round(e["d"], 4),
            threshold=round(e["theta"], 4),
            history_reentry=round(ev_info["red"], 4),
            checks=ev_info["checks"],
            previous_fire=e["last_fire_id"],
            cell=[e["x"], e["y"]],
        )
        e["active"] = self._clock(name, "persist")
        e["cool"] = self._clock(name, "persist") + self._clock(name, "refractory")
        e["fires"] += 1
        e["last_fire"], e["last_fire_id"] = self.t, fe["id"]
        e["fired_now"] = True
        if name == "A1":
            e["energy"] -= c["cost"]
        elif not self.cfg["power"]["infinite"]:
            self.power -= c["cost"]
            self._acc("power_fire", c["cost"])
        if name == "A1" and self.phil:
            self.phil.on_a1_fire(self, fe)
        # causal chain for cycle detection: A1.act -> A2.fire -> A2.reconfigure -> A1.fire
        if name == "A2":
            if (
                src is not None
            ):  # only a firing attributed to an event of A1 can start a chain; a noise-triggered firing starts none
                self.pending_chain[fe["id"]] = {"a1_act": src, "reentry": ev_info["red"]}
        else:
            for fid, ch in list(self.pending_chain.items()):
                reconf = src if src in ch.get("reconfigs", ()) else None
                if reconf is not None and "closed" not in ch:
                    ch["closed"] = fe["id"]
                    reentry = ch["reentry"] + ev_info["red"]
                    cyc = self._event(
                        "cycle",
                        None,
                        a1_act=ch["a1_act"],
                        a2_fire=fid,
                        reconfigure=reconf,
                        a1_fire=fe["id"],
                        history_reentry=round(reentry, 4),
                    )
                    self.cycles.append({"tick": self.t, "id": cyc["id"], "history_reentry": reentry > 1e-9})
                    del self.pending_chain[fid]
                    break
        return fe

    def step(self) -> bool:
        """Advance one tick. Returns False when the run ended (horizon reached)."""
        if self.t >= self.cfg["horizon"] - 1:
            self.end_reason = self.end_reason or "horizon reached"
            return False
        self.t += 1
        self.tick_acc = {}
        self._apply_due()
        self._expire_addresses()
        for name in ENTITIES:
            self.ent[name]["fired_now"] = False
        evals = {name: self._evaluate(name) for name in ENTITIES}
        for name in ENTITIES:
            e = self.ent[name]
            if e["present"] and evals[name]["fire"]:
                self._fire(name, evals[name])
            e["last_eval"] = evals[name]["checks"]
        # action: every entity with a running firing acts once per tick (speed scales movement)
        for name in ENTITIES:
            e = self.ent[name]
            if e["present"] and e["active"] > 0:
                fid = e["last_fire_id"]
                if name == "A1":
                    self._act_a1(fid)
                else:
                    self._act_a2(fid)
                e["active"] -= 1
                if e["active"] == 0:
                    e["last_expire"] = self.t
                    self._event("expire", name, fire=fid)
            if e["cool"] > 0:
                e["cool"] -= 1
        # environment: diffusion, decay of alterations, renewal from the finite reserve, upkeep of A1
        env = self.cfg["environment"]
        if self.renew_queue:  # renewals whose delay has run out reach the field
            due = [q for q in self.renew_queue if q[0] <= self.t]
            self.renew_queue = [q for q in self.renew_queue if q[0] > self.t]
            for _, cells, per_cell in due:
                self.R[cells] += per_cell
        if self.reroutes:  # resource conduits: a share of the source cell is moved to the target cell
            self.reroutes = [q for q in self.reroutes if q["until"] > self.t]
            for q in self.reroutes:
                moved = q["rate"] * float(self.R[q["from"]])
                self.R[q["from"]] -= moved
                self.R[q["to"]] += moved
        pad = np.pad(self.R, 1, mode="edge")
        lap = pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:] - 4 * self.R
        self.R = np.clip(
            self.R + env["diffusion"] * self.cfg["sss"]["scale"] ** 2 * lap + env["relax"] * (self.R0 - self.R), 0.0, None
        )
        if env["regrow"] > 0:
            src = self.R0[0, :]
            draw = env["regrow"] * self.n
            if not self.cfg["power"]["infinite"]:
                draw = min(draw, self.power)
                self.power -= draw
                self._acc("power_regrow", draw)
            gain = draw / self.n
            self.R[0, :] = np.minimum(src * 1.5, self.R[0, :] + gain)
        for f in (self.M1, self.M2):
            pad = np.pad(f, 1, mode="edge")
            lap = pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:] - 4 * f
            f += env["mark_diffusion"] * lap
            f *= 1.0 - env["persistence"]
            np.clip(f, 0.0, None, out=f)
        pw = self.cfg["power"]
        before = self.power
        self.power = pw["capacity"] if pw["infinite"] else min(pw["capacity"], self.power + pw["charge"])
        self._acc("power_in", self.power - before)
        a1 = self.ent["A1"]
        if a1["present"]:
            a1["energy"] = max(0.0, a1["energy"] - self.cfg["entities"]["A1"]["upkeep"])
        # history: a decaying trace of firing and of detected difference; it re-enters only when enabled
        h = self.cfg["history"]
        for name in ENTITIES:
            e = self.ent[name]
            e["h"] = (
                e["h"] * (1.0 - h["decay"]) + (h["gain"] if e["fired_now"] else 0.0) + (0.2 * h["gain"] if e["d"] > 0.02 else 0.0)
            )
        for name in ENTITIES:
            self.h_hist[name].append(self.ent[name]["h"])
        if (self.cfg.get("m2") or {}).get("sense") == "delayed":
            self.m2_hist.append(self.M2.copy())
        if self.phil:
            self.phil.step(self)
        self._record()
        return self.t < self.cfg["horizon"] - 1

    # ------------------------------------------------------------------------------------------------ status
    def _diagnose(self) -> dict | None:
        """The first unmet dependency of the loop. Structure first (a part that is absent, disconnected or disabled), then the latest precondition
        evaluations in the order of the loop, then the finite power reserve. Derived from state and evaluations, never from the animation."""
        cfg, ch = self.cfg, self.cfg["channels"]

        def dep(entity: str | None, pre: str, detail: str, value: Any = None, need: Any = None) -> dict:
            return {"entity": entity, "precondition": pre, "detail": detail, "value": value, "need": need}

        if not self.ent["A1"]["present"]:
            return dep("A1", "present", "A1 is absent")
        if not self.ent["A2"]["present"]:
            return dep("A2", "present", "A2 is absent: nothing reconfigures the environment for A1")
        if not ch["sensor_resource"]:
            return dep("A1", "sensor channel connected", "A1's resource sensor is disconnected")
        if not ch["sensor_alteration"]:
            return dep("A2", "sensor channel connected", "A2's alteration sensor is disconnected")
        if not ch["interaction"]:
            return dep("A2", "interaction channel", "the interaction channel between A1's alteration and A2 is interrupted")
        if cfg["environment"]["persistence"] >= 0.999:
            return dep(
                None, "environmental persistence", "alterations do not persist: A1's alteration is gone before A2 can detect it"
            )
        if not ch["feedback"]:
            return dep(
                "A2", "environmental reconfiguration", "A2's reconfiguration of the resource is disabled (no feedback to A1)"
            )
        for who, label, why in (
            (
                "A2",
                "differentiated stimulus >= threshold",
                "A2 detects no alteration above its threshold (the signal decayed, is too weak or is out of reach)",
            ),
            ("A2", "power reserve >= firing cost", "the power reserve cannot pay A2's firing"),
            (
                "A1",
                "differentiated stimulus >= threshold",
                "A1 detects no resource change above its threshold (the reconfiguration did not reach it, or history no longer lowers its threshold)",
            ),
            ("A1", "energy >= firing cost", "A1 has too little energy to fire"),
            ("A2", "inside the spatial boundary", "A2 is outside the spatial boundary"),
            ("A1", "inside the spatial boundary", "A1 is outside the spatial boundary"),
        ):
            for k in self.ent[who]["last_eval"]:
                if k["precondition"] == label and not k["ok"]:
                    return dep(who, label, why, k["value"], k["need"])
        if self.power <= 1e-9 and not cfg["power"]["infinite"]:
            return dep(None, "power reserve", "the power reserve is empty", round(self.power, 3))
        return None

    def _classify(self) -> None:
        win, k_active, stale = 48, 2, 24
        cyc = [c for c in self.cycles if self.t - c["tick"] < win]
        n = len(cyc)
        last = self.cycles[-1]["tick"] if self.cycles else None
        age = None if last is None else self.t - last
        reentry = sum(1 for c in cyc if c["history_reentry"])
        if n >= k_active and age is not None and age <= stale:
            label, reason = "ACTIVE", "complete cycles are being sustained"
        elif n >= 1:
            label, reason = "DEGRADED", "fewer cycles than required in the window" if n < k_active else "the last cycle is stale"
        elif self.t < win:
            label, reason = "DEGRADED", "forming: no complete cycle yet"
        else:
            label, reason = "COLLAPSED", f"no complete cycle in the last {win} ticks"
        dep = self._diagnose() if label != "ACTIVE" else None
        prev = self.status["label"]
        self.status = {
            "label": label,
            "reason": reason,
            "dependency": dep,
            "cycles_in_window": n,
            "history_reentry_cycles": reentry,
            "age": age,
        }
        if label != prev or not self.status_log:
            self.status_log.append({"tick": self.t, "label": label, "reason": reason, "dependency": dep})
            if self.t > 0:
                self._event("status", None, label=label, reason=reason, dependency=dep)

    def _quant(self, f: np.ndarray, top: float) -> bytes:
        return np.clip(np.rint(f / top * 255.0), 0, 255).astype(np.uint8).tobytes()

    def _address_integrity(self, name: str) -> float:
        a = self.addr[name]
        if a["mode"] == "loss":
            return 0.0
        if a["mode"] == "partial":
            return float(a["fraction"])
        if a["mode"] == "fragment":
            return float(a["mask"].mean())
        if a["mode"] in ("stale", "delayed"):
            return 0.0 if a.get("at") is not None and tuple(a["at"]) != (self.ent[name]["x"], self.ent[name]["y"]) else 1.0  # the address names somewhere else than the body
        return 1.0

    def _trace(self) -> None:
        """The intermediate quantities of the operation, one value per tick (a separate block of the record: the status never reads it)."""
        T, A = self.traces, self.tick_acc
        a1, a2, ev = self.ent["A1"], self.ent["A2"], self.status
        n_cyc, age = ev["cycles_in_window"], ev.get("age")
        margin_age = -1.0 if age is None else (24 - age) / 24
        consumed, renewed = A.get("consumed", 0.0), A.get("renewed", 0.0)
        draw = A.get("power_fire", 0.0) + A.get("power_renew", 0.0) + A.get("power_regrow", 0.0) + A.get("power_phil", 0.0)
        cols = {
            "t": self.t,
            "resource_consumed": consumed,
            "resource_renewed": renewed,
            "resource_flow": consumed + renewed,
            "resource_total": float(self.R.sum()),
            "power_reserve": self.power,
            "power_in": A.get("power_in", 0.0),
            "power_draw": draw,
            "power_balance": A.get("power_in", 0.0) - draw,
            "renewal_requested": A.get("renew_requested", 0.0),
            "renewal_events": A.get("renewal_events", 0.0),
            "a1_energy": a1["energy"],
            "a1_activity": 1.0 if a1["active"] > 0 else 0.0,
            "a2_activity": 1.0 if a2["active"] > 0 else 0.0,
            "a1_fired": 1.0 if a1["fired_now"] else 0.0,
            "a2_fired": 1.0 if a2["fired_now"] else 0.0,
            "interaction_strength": a2["s0"],  # the alteration A2 senses of A1
            "reconfiguration_signal": a1["s0"],  # what A1 senses of the resource field (and of M2 if connected)
            "a1_differentiated": a1["d"],
            "a2_differentiated": a2["d"],
            "history_contribution_a1": a1["reentry_now"],
            "history_contribution_a2": a2["reentry_now"],
            "history_trace_a1": a1["h"],
            "history_trace_a2": a2["h"],
            "sensor_radius_a1": float(self._scaled_radius("A1")),
            "sensor_radius_a2": float(self._scaled_radius("A2")),
            "speed_a1": self._speed("A1"),
            "speed_a2": self._speed("A2"),
            "address_integrity_a1": self._address_integrity("A1"),
            "address_integrity_a2": self._address_integrity("A2"),
            "cycles_in_window": float(n_cyc),
            "target_margin": min(n_cyc / 2 - 1, margin_age),  # >= 0 exactly when the ACTIVE criteria hold
        }
        if self.phil:
            cols.update(self.phil.trace_columns())
        if (self.cfg.get("m2") or {}).get("sense", "none") != "none" or "m2_sensed" in T:
            if "m2_sensed" not in T:  # M2 sensing was switched on during the run (a route change): the ticks before it sensed nothing
                T["m2_sensed"] = [0.0] * len(T["t"])
            cols["m2_sensed"] = self.m2_sensed  # absent unless M2 sensing is configured, so that the traces of every other run are what they were
        for k, v in cols.items():
            T[k].append(round(float(v), 5) if k != "t" else int(v))

    def _record(self, first: bool = False) -> None:
        self._classify()
        self._trace()
        fr: dict[str, Any] = {
            "t": self.t,
            "status": self.status["label"],
            "cycles": self.status["cycles_in_window"],
            "power": round(self.power, 4),
            "R": round(float(self.R.sum()), 4),
            "M1": round(float(self.M1.sum()), 4),
            "M2": round(float(self.M2.sum()), 4),
        }
        for name in ENTITIES:
            e = self.ent[name]
            fr[name] = {
                "present": e["present"],
                "x": e["x"],
                "y": e["y"],
                "energy": round(e["energy"], 4),
                "h": round(e["h"], 4),
                "active": e["active"],
                "cool": e["cool"],
                "fired": e["fired_now"],
                "s": round(e["s"], 4),
                "d": round(e["d"], 4),
                "theta": round(e["theta"], 4),
                "baseline": round(e["baseline"], 4),
                "reentry": round(e["reentry_now"], 4),
                "r_local": round(float(self.R[e["x"], e["y"]]), 4),
                "m1_local": round(float(self.M1[e["x"], e["y"]]), 4),
                "fires": e["fires"],
                "failed": [k["precondition"] for k in e["last_eval"] if not k["ok"]],
            }
        ad = {name: self._ad_static(name) for name in ENTITIES}
        if any(a["mode"] is not None for a in self.addr.values()):
            fr["address"] = {
                name: {
                    "mode": self.addr[name]["mode"],
                    "integrity": round(self._address_integrity(name), 4),
                    **({"at": list(self.addr[name]["at"])} if self.addr[name].get("at") is not None else {}),
                }
                for name in ENTITIES
            }
        if ad != self._last_ad:
            fr["ad"] = ad
            self._last_ad = ad
        self.frames.append(fr)
        top = max(1.5, self.cfg["environment"]["r_max"] * 1.5)
        self.field_bytes += self._quant(self.R, top) + self._quant(self.M1, 1.0) + self._quant(self.M2, 1.0)

    def run(self) -> dict:
        while self.step():
            pass
        return self.record()

    def inject(self, iv: dict) -> None:
        """Schedule an intervention for the next tick while the run is stepping (a controller reacting to what the run has done so far). The intervention joins the schedule in the
        order a stored schedule is replayed in, so replaying the recorded schedule without the controller gives the same run."""
        iv = copy.deepcopy(iv)
        iv["tick"] = self.t + 1
        issues = validate_interventions([iv], self.cfg["horizon"])
        if issues:
            raise MeosError("; ".join(issues))
        self.interventions.append(iv)
        self.interventions.sort(key=lambda i: (i["tick"], _canon(i)))

    # ------------------------------------------------------------------------------------------------ record
    def address_domain(self, name: str, t: int | None = None) -> dict:
        """The Address Domain of an operational configuration now: where, within what, over what window, how fast, with what history."""
        c, e = self.cfg["entities"][name], self.ent[name]
        ch = self.cfg["channels"]
        r = self._scaled_radius(name)
        x, y = e["x"], e["y"]
        return {
            "spatial": {"x": x, "y": y},
            "operational_boundary": {
                "sensor_radius": r,
                "footprint": self._footprint(name),
                "arena_radius": self.cfg["environment"]["arena_radius"],
            },
            "temporal_window": {"window": c["window"], "persist": c["persist"], "refractory": c["refractory"]},
            "speed": self._speed(name),
            "history": {
                "trace": round(e["h"], 4),
                "enabled": self.cfg["history"]["enabled"],
                "fires": e["fires"],
                "last_fire": e["last_fire"],
            },
            "connectivity": {
                "sensor_resource": ch["sensor_resource"],
                "sensor_alteration": ch["sensor_alteration"],
                "interaction": ch["interaction"],
                "feedback": ch["feedback"],
            },
            "environment": {
                "M1_local": round(float(self.M1[x, y]), 4),
                "M2_local": round(float(self.M2[x, y]), 4),
                "mark_persistence": self.cfg["environment"]["persistence"],
            },
            "resource": {
                "R_local": round(float(self.R[x, y]), 4),
                "energy": round(e["energy"], 4),
                "power_reserve": round(self.power, 4),
            },
        }

    def _ad_static(self, name: str) -> dict:
        """The parts of an Address Domain that change only by intervention (the rest is in every frame): boundary, temporal window, speed, connectivity."""
        c, ch = self.cfg["entities"][name], self.cfg["channels"]
        return {
            "operational_boundary": {
                "sensor_radius": self._scaled_radius(name),
                "footprint": self._footprint(name),
                "arena_radius": self.cfg["environment"]["arena_radius"],
            },
            "temporal_window": {
                "window": self._clock(name, "window"),
                "persist": self._clock(name, "persist"),
                "refractory": self._clock(name, "refractory"),
            },
            "speed": self._speed(name),
            "connectivity": {
                "sensor_resource": ch["sensor_resource"],
                "sensor_alteration": ch["sensor_alteration"],
                "interaction": ch["interaction"],
                "feedback": ch["feedback"],
            },
            "history_reentry_enabled": self.cfg["history"]["enabled"],
            "mark_persistence": self.cfg["environment"]["persistence"],
            "sss": dict(self.cfg["sss"]),
            "present": self.ent[name]["present"],
            "threshold": c["threshold"],
        }

    def record(self) -> dict:
        rec = {
            "schema": SCHEMA,
            "engine": ENGINE_VERSION,
            "config": self.initial_config,
            "final_config": self.cfg,
            "initial_config_digest": None,
            "seed": self.cfg["seed"],
            "interventions": self.interventions,
            "intervention_log": self.intervention_log,
            "frames": self.frames,
            "events": self.events,
            "cycles": self.cycles,
            "status_log": self.status_log,
            "final_status": self.status,
            "termination": {
                "reason": ("horizon reached" if self.end_reason else None)
                or ("collapsed" if self.status["label"] == "COLLAPSED" else "horizon reached"),
                "tick": self.t,
                "collapsed": self.status["label"] == "COLLAPSED",
                "failed_dependency": self.status["dependency"] if self.status["label"] != "ACTIVE" else None,
            },
            "traces": {k: list(v) for k, v in self.traces.items()},
            "fields": {
                "grid": self.n,
                "channels": ["R", "M1", "M2"],
                "encoding": "uint8, frame-major, channel-major, x-major; R scaled to 0..1.5*r_max, M1 and M2 to 0..1",
                "r_top": max(1.5, self.cfg["environment"]["r_max"] * 1.5),
                "b64": base64.b64encode(bytes(self.field_bytes)).decode(),
            },
        }
        return rec


def input_digest(config: dict, interventions: list[dict] | None = None) -> str:
    return digest(
        {
            "engine": ENGINE_VERSION,
            "config": config,
            "interventions": sorted(interventions or [], key=lambda iv: (iv["tick"], _canon(iv))),
        }
    )


def run_record(config: dict, interventions: list[dict] | None = None) -> dict:
    """Run to the horizon and return the full record, with the digest of its inputs and of its outputs (what replay must reproduce)."""
    r = Run(config, interventions)
    return finalize(r.run(), config, interventions)


def finalize(rec: dict, config: dict, interventions: list[dict] | None) -> dict:
    """Add the digests of the inputs and of the outputs to a record of a finished run (``run_record`` does this; a controller that stepped the run itself does it with the schedule it recorded)."""
    rec["initial_config_digest"] = input_digest(config, interventions)
    out = {k: rec[k] for k in ("frames", "events", "cycles", "status_log", "final_status", "termination")}
    out["fields"] = rec["fields"]["b64"]
    rec["result_digest"] = digest(out)
    # the intermediate quantities are a separate block with its own digest, so that the result digest of a run (what earlier records and tests pin) is
    # the digest of the same things as before; full_digest covers both
    rec["trace_digest"] = digest(rec["traces"])
    rec["full_digest"] = digest({"result": rec["result_digest"], "traces": rec["trace_digest"]})
    return rec


def replay(rec: dict) -> dict:
    """Re-run a stored record from its recorded initial configuration, seed and interventions. ``identical`` compares the result digests bit for bit."""
    again = run_record(rec["config"], rec["interventions"])
    return {
        "identical": again["result_digest"] == rec["result_digest"]
        and again.get("trace_digest") == rec.get("trace_digest", again.get("trace_digest")),
        "expected": rec["result_digest"],
        "got": again["result_digest"],
    }
