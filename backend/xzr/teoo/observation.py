"""Total Observation architecture (TEOO's own relation layer; it imports nothing from totalobs, hpo or meos).

An *observation configuration* says what could be observed of a declared set of targets: sensors (channels, resolution, sampling period, window, detection limit, delay, health), couplings between
sensors and targets (reach, gain, delay, link), resource conditions (an energy budget and its cost), memory conditions (how long a sample is kept before it is overwritten and how long retrieval takes),
and observation boundaries (the opacity of a target against a sensor's penetration). It is versioned: every revision makes a new version (see ``revision.py``) and the state of observability at any time can
be replayed from the history.

Naming. "Total" does not mean that the world is completely acquired. A configuration is a *conditional cross-section* of what a declared task can reach under its conditions (the reading of Total Relational
Observation Theory that this layer implements: relations that were left out to make a local observation tractable are kept as declared exclusions, and a claim stays *epistemically open* while a relation that
could change its judgment lies outside the observed field). Differences that were not observed, not measured, or invisible to the apparatus are kept as such; nothing here says they are absent. The completeness
reported is always relative to the *declared* targets and relations, never to the world.

Statuses are those of ``status.py``; where a condition has no status of its own (a spent resource budget, an overwritten sample, a dead link) it is mapped onto the nearest one and the reason is kept in ``detail``.
"""

from __future__ import annotations

import copy
from typing import Any

from . import status as ST
from .provenance import digest_of, now_iso

CLAIM_NOTE = ("A cross-section of the declared targets and relations under the stated conditions, not an acquisition of the world: what lies outside the declaration is unknown, not absent.")


def sensor(sid: str, channels: list[str], *, resolution: float | None = None, sampling_period_s: float | None = None, window_s: float | None = None, detection_limit: float | None = None,
           penetration: float | None = None, delay_s: float | None = None, health: float = 1.0, reach: list[str] | None = None, cost_per_s: float = 0.0) -> dict:
    return {"id": sid, "channels": list(channels), "resolution": resolution, "sampling_period_s": sampling_period_s, "window_s": window_s, "detection_limit": detection_limit, "penetration": penetration,
            "delay_s": delay_s, "health": health, "reach": reach, "cost_per_s": cost_per_s}


def target_spec(tid: str, channel: str, *, scale: float | None = None, phenomenon_period_s: float | None = None, amplitude: float | None = None, opacity: float | None = None) -> dict:
    return {"id": tid, "channel": channel, "scale": scale, "phenomenon_period_s": phenomenon_period_s, "amplitude": amplitude, "opacity": opacity}


def new_configuration(sensors: list[dict], *, couplings: dict[str, dict] | None = None, resources: dict | None = None, memory: dict | None = None, variables: list[str] | None = None, at: float = 0.0,
                      body_version: int | None = None, label: str = "initial") -> dict:
    """``couplings``: {"sensor:target": {"gain", "delay_s", "link"}}; ``resources``: {"energy_budget"}; ``memory``: {"buffer_s", "retrieval_delay_s"}; ``variables``: the measured variables of this configuration."""
    return {"version": 1, "parent": None, "label": label, "at": at, "sensors": copy.deepcopy(sensors), "couplings": copy.deepcopy(couplings or {}), "resources": dict(resources or {"energy_budget": None}),
            "memory": dict(memory or {"buffer_s": None, "retrieval_delay_s": 0.0}), "variables": list(variables or []), "body_version": body_version, "change": {"op": "declare"}}


def digest(cfg: dict) -> str:
    return digest_of({k: v for k, v in cfg.items() if k != "at"})


def channels_of(cfg: dict) -> tuple[str, ...]:
    return tuple(sorted({c for s in cfg["sensors"] for c in s["channels"] if s["health"] > 0}))


def energy_remaining(cfg: dict, t: float) -> float | None:
    b = cfg["resources"].get("energy_budget")
    if b is None:
        return None
    return b - sum(s["cost_per_s"] for s in cfg["sensors"] if s["health"] > 0) * max(0.0, t - cfg["at"])


class _Ctx:
    """What is the same for every target under one configuration: the channels that can be carried and the sensors by channel. Built once per configuration, not once per (target, sensor)."""

    __slots__ = ("channels", "by_channel")

    def __init__(self, cfg: dict):
        self.channels = channels_of(cfg)
        self.by_channel: dict[str, list[dict]] = {}
        for s in cfg["sensors"]:
            for c in s["channels"]:
                self.by_channel.setdefault(c, []).append(s)


def _assess_static(cfg: dict, spec: dict, ctx: _Ctx, measured: bool = True) -> dict:
    """The part of a target's assessment that does not depend on the time t: the sensors, the couplings, the scale, the window, the boundary, the signal, the memory is applied in :func:`_apply_time`."""
    best: dict | None = None
    carrying = ctx.by_channel.get(spec["channel"], [])
    in_reach = [s for s in carrying if s["reach"] is None or spec["id"] in s["reach"]]
    for s in (in_reach or carrying):  # a sensor whose reach excludes the target is not a candidate unless every sensor of the channel excludes it (then the target is outside every reach)
        key = f"{s['id']}:{spec['id']}"
        cpl = cfg["couplings"].get(key, {"gain": 1.0, "delay_s": 0.0, "link": True})
        local_detail: list[str] = []
        reach = s["reach"]
        extra: list[ST.ObsStatus] = []
        if s["health"] <= 0:
            local_detail.append(f"sensor {s['id']} has failed")
            r: dict[str, Any] = {"status": "INSTRUMENT_MISMATCH", "causes": ["INSTRUMENT_MISMATCH"], "cause_known": True, "undetermined": []}
        else:
            if (reach is not None and spec["id"] not in reach) or not cpl.get("link", True):
                extra.append(ST.ObsStatus.BOUNDARY_INVISIBLE)
                local_detail.append("outside the sensor's reach" if reach is not None and spec["id"] not in reach else "the coupling link is down")
            amp = None if spec["amplitude"] is None else spec["amplitude"] * float(cpl.get("gain", 1.0))
            limit = None if s["detection_limit"] is None else s["detection_limit"] / max(s["health"], 1e-9)
            inst = ST.Instrument(s["id"], tuple(s["channels"]), s["resolution"], s["sampling_period_s"], s["window_s"], limit, s["penetration"])
            r = ST.assess(ctx.channels, inst, ST.Target(spec["channel"], spec["scale"], spec["phenomenon_period_s"], amp, spec["opacity"]), measured=measured)
            if extra:
                causes = [ST.ObsStatus(c) for c in r["causes"]] + extra
                st, allc = ST.combine([c for c in causes if c in ST.PRECEDENCE])
                r = {**r, "status": st.value, "causes": allc, "cause_known": True}
            if s["health"] < 1.0:
                local_detail.append(f"sensor health {s['health']}: the detection limit is raised to {limit}")
        r = {**r, "sensor": s["id"], "detail": local_detail}
        if best is None or (r["status"] == "MEASURED_VALID") or (best["status"] != "MEASURED_VALID" and len(r["causes"]) < len(best["causes"])):
            best = r
    if best is None:
        base = ST.assess(ctx.channels, None, ST.Target(spec["channel"], spec["scale"], spec["phenomenon_period_s"], spec["amplitude"], spec["opacity"]), measured=measured)
        best = {**base, "sensor": None, "detail": ["no sensor of this configuration carries the channel"]}
    return best


def _apply_time(best: dict, cfg: dict, t: float) -> dict:
    """The time-dependent conditions: a spent energy budget; the memory condition. Returns a fresh dictionary (the static assessment may be shared between times)."""
    rem = energy_remaining(cfg, t)
    out = {**best, "causes": list(best["causes"]), "detail": list(best["detail"]), "undetermined": list(best.get("undetermined", []))}
    if out["status"] == "MEASURED_VALID":
        if rem is not None and rem <= 0:
            out = {**out, "status": "UNMEASURED", "causes": [], "detail": out["detail"] + ["the energy budget is spent: it could be measured, it is not"]}
        elif cfg["memory"].get("buffer_s") is not None and cfg["memory"].get("retrieval_delay_s", 0.0) > cfg["memory"]["buffer_s"]:
            out = {**out, "status": "MISSING", "causes": [], "cause_known": True, "detail": out["detail"] + ["the sample is overwritten before it is retrieved (memory condition)"]}
    return out


def assess_target(cfg: dict, spec: dict, t: float, *, measured: bool = True) -> dict:
    """The observability of one target under a configuration at time t. Several limits can apply at once; undetermined metadata gives UNKNOWN_CAUSE; a spent budget or an overwritten sample is reported with its reason."""
    return _apply_time(_assess_static(cfg, spec, _Ctx(cfg), measured), cfg, t)


def version_at(history: list[dict], t: float) -> dict:
    cur = history[0]
    for c in history:
        if c["at"] <= t:
            cur = c
    return cur


def _freeze(x: Any) -> Any:
    if isinstance(x, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in x.items()))
    if isinstance(x, (list, tuple)):
        return tuple(_freeze(v) for v in x)
    return x


class _Cache:
    """The time-independent assessments of one replay. The observation state at many times shares them: the state depends on t only through the configuration in force and the energy budget (applied afterwards).
    Between versions an assessment is reused when everything it was computed from is equal: the spec of the target, the channels that can be carried at all, the parameters of every sensor carrying the target's channel
    (reach included) and the couplings of the target. A change to one channel therefore recomputes the targets of that channel and no others. Reuse is by equality of inputs, so a reused assessment is the one that would be
    computed again; ``tests/test_teoo_observation.py`` checks that against the first implementation on random worlds."""

    def __init__(self) -> None:
        self.ctx: dict[int, _Ctx] = {}
        self.static: dict[tuple[int, str], dict] = {}
        self.digest: dict[int, str] = {}
        self.chan_sig: dict[tuple[int, str], int] = {}
        self.cpl_by_target: dict[int, dict[str, tuple]] = {}
        self.sig_ids: dict[Any, int] = {}
        self.by_key: dict[tuple, dict] = {}
        self.hits = 0  # served for this (configuration, target) again (another time in the same version)
        self.reused = 0  # served from an earlier version with equal inputs
        self.misses = 0  # computed

    def _id(self, sig: Any) -> int:
        return self.sig_ids.setdefault(sig, len(self.sig_ids))

    def target(self, cfg: dict, spec: dict) -> dict:
        key = (id(cfg), spec["id"])
        got = self.static.get(key)
        if got is not None:
            self.hits += 1
            return got
        if id(cfg) not in self.ctx:
            self.ctx[id(cfg)] = _Ctx(cfg)
            by: dict[str, list] = {}
            for ck, cv in cfg["couplings"].items():  # a key is "sensor:target"; either id may contain ':', so the key is registered under every suffix (a superset: never misses a coupling)
                for i, ch in enumerate(ck):
                    if ch == ":":
                        by.setdefault(ck[i + 1:], []).append((ck, _freeze(cv)))
            self.cpl_by_target[id(cfg)] = {t: tuple(sorted(v)) for t, v in by.items()}
        ctx = self.ctx[id(cfg)]
        ck2 = (id(cfg), spec["channel"])
        if ck2 not in self.chan_sig:
            self.chan_sig[ck2] = self._id(tuple((s["id"], _freeze({k: v for k, v in s.items() if k != "cost_per_s"})) for s in ctx.by_channel.get(spec["channel"], [])))
        full = (_freeze(spec), self._id(ctx.channels), self.chan_sig[ck2], self.cpl_by_target[id(cfg)].get(spec["id"], ()))
        got = self.by_key.get(full)
        if got is None:
            self.misses += 1
            got = self.by_key[full] = _assess_static(cfg, spec, ctx)
        else:
            self.reused += 1
        self.static[key] = got
        return got


def state_at(history: list[dict], specs: list[dict], t: float, *, _cache: _Cache | None = None) -> dict:
    """The observation state at time t, replayed from the history: the configuration version in force and the status of every declared target."""
    cfg = version_at(history, t)
    cache = _cache or _Cache()
    targets = {s["id"]: _apply_time(cache.target(cfg, s), cfg, t) for s in specs}
    counts: dict[str, int] = {}
    for a in targets.values():
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    if id(cfg) not in cache.digest:
        cache.digest[id(cfg)] = digest(cfg)
    return {"t": t, "version": cfg["version"], "config_digest": cache.digest[id(cfg)], "body_version": cfg["body_version"], "targets": targets, "summary": counts, "claim_note": CLAIM_NOTE,
            "declared_targets": len(specs), "observed": counts.get("MEASURED_VALID", 0), "note": "the denominator is the declared targets, not the world"}


def diff_states(before: dict, after: dict) -> dict:
    """What a change gained and lost, target by target (information that became obtainable, information that was lost, and status changes that are neither)."""
    gained, lost, changed, same = [], [], [], []
    for tid, a in after["targets"].items():
        b = before["targets"].get(tid)
        if b is None:
            continue
        if b["status"] == a["status"]:
            same.append(tid)
        elif a["status"] == "MEASURED_VALID":
            gained.append({"target": tid, "from": b["status"], "causes": b["causes"]})
        elif b["status"] == "MEASURED_VALID":
            lost.append({"target": tid, "to": a["status"], "causes": a["causes"]})
        else:
            changed.append({"target": tid, "from": b["status"], "to": a["status"]})
    return {"gained": gained, "lost": lost, "changed": changed, "unchanged": same}


def replay(history: list[dict], specs: list[dict], times: list[float], *, _cache: _Cache | None = None) -> list[dict]:
    cache = _cache if _cache is not None else _Cache()
    return [state_at(history, specs, t, _cache=cache) for t in times]


def observability_changes(history: list[dict], specs: list[dict], target_id: str) -> list[dict]:
    """The status of one target version by version: where its observability changed and which change did it."""
    out, prev = [], None
    for cfg in history:
        a = assess_target(cfg, next(s for s in specs if s["id"] == target_id), cfg["at"])
        if prev is None or a["status"] != prev:
            out.append({"version": cfg["version"], "at": cfg["at"], "status": a["status"], "causes": a["causes"], "change": cfg["change"]})
        prev = a["status"]
    return out


# ------------------------------------------------------------------------------------------------ the relation field (Total Relational Observation)
DIMENSIONS = ("spatial", "temporal", "material", "hierarchical", "infrastructural", "causal")


def relation_field(task: str, relations: list[dict]) -> dict:
    """The relations declared for a task. Each: {"id", "dimension", "observed": bool, "accessible": bool | None, "judgment_changing": bool | None, "note"}. ``None`` is unknown (never False)."""
    bad = [r["id"] for r in relations if r["dimension"] not in DIMENSIONS]
    if bad:
        raise ValueError(f"dimension must be one of {DIMENSIONS}: {bad}")
    obs = [r["id"] for r in relations if r["observed"]]
    acc = [r["id"] for r in relations if not r["observed"] and r.get("accessible") is True]
    inacc = [r["id"] for r in relations if not r["observed"] and r.get("accessible") is False]
    unk = [r["id"] for r in relations if not r["observed"] and r.get("accessible") is None]
    open_rel = [r["id"] for r in relations if not r["observed"] and r.get("judgment_changing") in (True, None)]
    return {"task": task, "relations": copy.deepcopy(relations), "observed": obs, "accessible_but_unobserved": acc, "inaccessible": inacc, "access_unknown": unk, "judgment_open": open_rel,
            "epistemically_open": bool(open_rel), "generalisation_allowed": not open_rel,
            "reading": "a conditional cross-section of the declared field: a local result is not general while a relation that could change its judgment is outside the observed field (unknown counts as possible)",
            "completeness_claim": None, "note": "completeness is relative to the declared relations; the world is not claimed to be covered"}


def now() -> str:
    return now_iso()


__all__: list[Any] = ["sensor", "target_spec", "new_configuration", "assess_target", "state_at", "diff_states", "replay", "observability_changes", "relation_field"]
