"""Observation-identifiability on the runtime world (environment ``oi``).

The question is ARDS's: which differences between a baseline system and an altered system can an observer identify under a given
observation configuration, and how should the configuration be revised to identify more? The system is this runtime's world
(xzr.hpo.World: the engine, an exogenous input stream, the HPO instruments); the observer reads it only through ``Instruments``.

Task
    * presets: two worlds (regimes ``intermittent`` and ``sparse``, fixed generator seeds); seeds change the exogenous and endogenous
      streams only. 400 configurations, 40 warm-up steps, then 16 recorded steps.
    * alterations (applied to the warmed world at the first recorded step): ``input-shift`` (external input rate x2.5), ``coupling-shift``
      (connection weights x0.3), ``retention-shift`` (retention x0.92), ``threshold-shift`` (thresholds x1.15).
    * differences: twelve features of the recorded steps, each readable through one instrument channel at a minimum scale (hierarchy
      level), a maximum sampling period and a minimum window (see DIFFS). A feature is *capable* under a configuration when the
      channel is carried, the level is fine enough, the period short enough and the window long enough; otherwise the reason is named in
      ARDS's vocabulary (device-mismatch, unmeasured, scale-mismatch, time-window-mismatch, boundary-invisible).
    * an observation of one configuration for n seeds: per feature the paired effect (baseline vs altered, same seed) d_z and its two-sided
      p; *identified* iff p < identP and |d_z| >= identD.
    * ground truth (evaluation only): 64 reference seeds with an ideal configuration (all channels, finest level, no noise, window 16);
      a difference *exists* iff |d_z| >= 0.5 and p < 0.001 there. Truth is never part of what an observer is given.

Mapping of ARDS's observation configuration to the HPO instrument: kinds = channels; overrides ``noise`` (multiplier of a 0.25 relative
noise), ``spatial`` (macro / cluster / local / config = hierarchy level 0..3; boundary_flow stops at local), ``sample_hz`` (period =
round(10 / sample_hz) steps, as in the instrument's period); ``window`` [t0, t1] in seconds (0.1 s per step) selects the recorded steps
aggregated. The instrument's period gates capability only (it never changes the data), exactly as in xzr.hpo.observe.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats as sps

from ...hpo.observe import Instruments, InstrumentSpec
from ...hpo.world import World, build_world

ENV_ID = "xzr.oi-env3"
N_CONFIG = 400
WARM = 40
RECORD = 16
DT = 0.1  # seconds per recorded step
ANALYSIS_S = RECORD * DT
PRESETS = ("intermittent", "sparse")
PRESET_GEN = {"intermittent": 7101, "sparse": 7102}
ALTERATIONS = ("input-shift", "coupling-shift", "retention-shift", "threshold-shift")
THRESHOLDS = {"identP": 0.01, "identD": 0.8, "existP": 0.05, "existD": 0.5}
TRUTH_REF = {"base": 90_000_000, "n": 64, "existP": 0.001, "existD": 0.5}
NOISE_REL = 0.25
SPATIAL = ("macro", "cluster", "local", "config")  # hierarchy levels 0..3
KINDS = ("activity", "tension", "memory", "recursion", "structure", "boundary_flow")
SETUP = {
    "activity": 60,
    "tension": 60,
    "memory": 60,
    "recursion": 90,
    "structure": 40,
    "boundary_flow": 90,
    "set": 10,
    "window": 5,
    "remove": 5,
}
DEFAULTS = {k: {"sample_hz": 5, "noise": 1, "spatial": "macro"} for k in KINDS}
SPATIAL_CHOICES = {k: (list(SPATIAL[:3]) if k == "boundary_flow" else list(SPATIAL)) for k in KINDS}
SCALE = {k: {c: i for i, c in enumerate(SPATIAL_CHOICES[k])} for k in KINDS}
DEFAULT_WINDOW_STEPS = 8  # a configuration without a window aggregates the last 8 steps
START_CONFIG = {"name": "control", "kinds": ["activity", "tension", "memory"], "overrides": {}, "window": None}


@dataclass(frozen=True)
class Alt:
    feature: str
    kind: str
    min_scale: int
    max_period: int  # steps: the sampling period must not exceed it
    min_window: int  # recorded steps aggregated


@dataclass(frozen=True)
class Diff:
    id: str
    label: str
    family: str
    alt: Alt


def _spread(v: np.ndarray) -> float:
    v = v[~np.isnan(v)]
    return float(v.std()) if v.size > 1 else 0.0


def _flow_total(f: np.ndarray) -> float:
    return float(np.nansum(f))


def _flow_asym(f: np.ndarray) -> float:
    tot = float(np.nansum(np.abs(f)))
    return float(np.nansum(np.abs(f - f.T)) / tot) if tot > 0 else 0.0


# difference id → (compute function over the channel's per-cluster values at the configured level)
COMPUTE = {
    "activity_pooled": lambda v: float(np.nanmean(v)),
    "activity_spread": _spread,
    "activity_peak": lambda v: float(np.nanmax(v)),
    "tension_pooled": lambda v: float(np.nanmean(v)),
    "tension_spread": _spread,
    "memory_pooled": lambda v: float(np.nanmean(v)),
    "memory_gradient": _spread,
    "recursion_pooled": lambda v: float(np.nanmean(v)) if np.any(~np.isnan(v)) else 0.0,
    "structure_pooled": lambda v: float(np.nanmean(v)),
    "structure_spread": _spread,
    "flow_total": _flow_total,
    "flow_asymmetry": _flow_asym,
}
DIFFS: tuple[Diff, ...] = (
    Diff("activity_pooled", "overall ignition rate", "activity", Alt("mean activity", "activity", 0, 2, 4)),
    Diff(
        "activity_spread",
        "unevenness of ignition across regions",
        "activity",
        Alt("std of regional activity", "activity", 1, 2, 4),
    ),
    Diff("activity_peak", "most active region", "activity", Alt("max regional activity", "activity", 2, 1, 4)),
    Diff("tension_pooled", "share of metastable configurations", "tension", Alt("mean tension", "tension", 0, 4, 1)),
    Diff("tension_spread", "unevenness of tension across regions", "tension", Alt("std of regional tension", "tension", 2, 4, 1)),
    Diff("memory_pooled", "mean retained history", "memory", Alt("mean memory", "memory", 0, 8, 1)),
    Diff("memory_gradient", "unevenness of retained history", "memory", Alt("std of regional memory", "memory", 1, 8, 1)),
    Diff(
        "recursion_pooled",
        "share of ignitions caused from inside a region",
        "recursion",
        Alt("mean recursion", "recursion", 1, 1, 8),
    ),
    Diff("structure_pooled", "live connections inside regions", "structure", Alt("mean structure", "structure", 0, 8, 1)),
    Diff(
        "structure_spread",
        "unevenness of internal structure",
        "structure",
        Alt("std of regional structure", "structure", 2, 8, 1),
    ),
    Diff("flow_total", "total flow across region boundaries", "flow", Alt("total boundary flow", "boundary_flow", 1, 2, 4)),
    Diff("flow_asymmetry", "one-way share of boundary flow", "flow", Alt("flow asymmetry", "boundary_flow", 2, 1, 8)),
)
DIFF_BY_ID = {d.id: d for d in DIFFS}


def catalog() -> dict:
    return {
        "differences": [
            {
                "id": d.id,
                "label": d.label,
                "family": d.family,
                "alternatives": [
                    {
                        "feature": d.alt.feature,
                        "kind": d.alt.kind,
                        "regions": [],
                        "min_scale": d.alt.min_scale,
                        "max_period_s": d.alt.max_period * DT,
                        "proxy": False,
                    }
                ],
            }
            for d in DIFFS
        ],
        "kinds": {k: {"family": "instrument", "defaults": DEFAULTS[k], "spatialChoices": SPATIAL_CHOICES[k]} for k in KINDS},
        "setupSeconds": SETUP,
        "scale": SCALE,
        "thresholds": THRESHOLDS,
        "maxSeeds": 32,
        "alterations": list(ALTERATIONS),
        "presets": list(PRESETS),
    }


# ----------------------------------------------------------------------------------------------------- configuration
def _settings(cfg: dict, kind: str) -> dict:
    d, o = DEFAULTS[kind], (cfg.get("overrides") or {}).get(kind, {})
    return {
        "sample_hz": float(o.get("sample_hz", d["sample_hz"])),
        "noise": float(o.get("noise", d["noise"])),
        "spatial": str(o.get("spatial", d["spatial"])),
    }


def _window_steps(cfg: dict) -> tuple[int, int]:
    w = cfg.get("window")
    if not w:
        return RECORD - DEFAULT_WINDOW_STEPS, RECORD
    a, b = max(0, int(round(w[0] / DT))), min(RECORD, int(round(w[1] / DT)))
    return a, max(a, b)


def capability_of(cfg: dict, d: Diff) -> dict:
    a = d.alt
    kinds = cfg.get("kinds") or []
    if a.kind not in kinds:
        return {
            "capable": False,
            "reason": "unmeasured" if not kinds else "device-mismatch",
            "usable": [],
            "states": [[a.feature, a.kind, "absent"]],
        }
    s = _settings(cfg, a.kind)
    if SCALE[a.kind].get(s["spatial"], 0) < a.min_scale:
        return {"capable": False, "reason": "scale-mismatch", "usable": [], "states": [[a.feature, a.kind, "scale"]]}
    period = max(1, round(10 / s["sample_hz"]))
    if period > a.max_period:
        return {"capable": False, "reason": "time-window-mismatch", "usable": [], "states": [[a.feature, a.kind, "time"]]}
    w0, w1 = _window_steps(cfg)
    if w1 - w0 < a.min_window:
        return {"capable": False, "reason": "boundary-invisible", "usable": [], "states": [[a.feature, a.kind, "window"]]}
    return {"capable": True, "reason": None, "usable": [a.feature], "states": [[a.feature, a.kind, "ok"]]}


def is_identified(o: dict | None, thr: dict = THRESHOLDS) -> bool:
    return bool(
        o
        and o["p"] is not None
        and o["d"] is not None
        and math.isfinite(o["p"])
        and math.isfinite(o["d"])
        and o["p"] < thr["identP"]
        and abs(o["d"]) >= thr["identD"]
    )


def paired_effect(a: list[float], b: list[float]) -> dict:
    n = len(a)
    if n < 3:
        return {"d": None, "p": None, "n": n}
    diff = np.array(b, float) - np.array(a, float)
    m, sd = float(diff.mean()), float(diff.std(ddof=1))
    if not sd > 0:
        return {"d": 0.0 if m == 0 else math.copysign(50.0, m), "p": 1.0 if m == 0 else 1e-12, "n": n}
    t = m / (sd / math.sqrt(n))
    return {"d": m / sd, "p": float(2 * sps.t.sf(abs(t), n - 1)), "n": n}


# ----------------------------------------------------------------------------------------------------- the worlds
def _alter(w: World, alteration: str) -> None:
    st = w.state
    if alteration == "input-shift":
        w.input_rate *= 2.5
    elif alteration == "coupling-shift":
        st.weight *= 0.3
        st.base_weight *= 0.3
    elif alteration == "retention-shift":
        st.retention *= 0.92
    elif alteration == "threshold-shift":
        st.theta *= 1.15
    else:
        raise ValueError(f"unknown alteration {alteration!r}")


_BASE_CACHE: OrderedDict[tuple[str, int], World] = OrderedDict()
_RUN_CACHE: OrderedDict[tuple[str, str, int], tuple[World, list]] = OrderedDict()


def _warm(preset: str, seed: int) -> World:
    key = (preset, seed)
    w = _BASE_CACHE.get(key)
    if w is None:
        w = build_world(N_CONFIG, PRESET_GEN[preset], seed, regime=preset)
        for _ in range(WARM):
            w.step()
        _BASE_CACHE[key] = w
        if len(_BASE_CACHE) > 48:
            _BASE_CACHE.popitem(last=False)
    return w


def recorded(preset: str, alteration: str, seed: int) -> tuple[World, list]:
    """The world after RECORD steps from the warmed state (``alteration`` = "base" or an alteration) and its step records."""
    key = (preset, alteration, seed)
    hit = _RUN_CACHE.get(key)
    if hit is not None:
        return hit
    w = _warm(preset, seed).fork()
    if alteration != "base":
        _alter(w, alteration)
    for _ in range(RECORD):
        w.step()
    out = (w, list(w.records[-RECORD:]))
    _RUN_CACHE[key] = out
    if len(_RUN_CACHE) > 160:
        _RUN_CACHE.popitem(last=False)
    return out


def _channel_values(world: World, recs: list, kind: str, cfg: dict, seed: int, level: int) -> np.ndarray:
    """The channel's per-cluster values at the scale the feature is defined at (a finer instrument can always be read coarsely)."""
    s = _settings(cfg, kind)
    w0, w1 = _window_steps(cfg)
    view = World(world.engine, world.h, world.exo, world.input_rate, world.input_amp, list(recs[w0:w1]))
    spec = InstrumentSpec(channels=(kind,), level=level, window=max(1, w1 - w0), period=1, noise=s["noise"] * NOISE_REL)
    inst = Instruments(view)
    rng = np.random.default_rng([seed, 0x4F49, KINDS.index(kind)])
    obs, _ = inst.observe(spec, {kind: (0, 99)}, np.arange(world.state.n), math.inf, rng, viewer="oi")
    v = obs.values[kind]
    return np.array(v, float)


def _features(world: World, recs: list, cfg: dict, seed: int, ids: list[str]) -> dict[str, float]:
    cache: dict[tuple[str, int], np.ndarray] = {}
    out = {}
    for i in ids:
        a = DIFF_BY_ID[i].alt
        if (a.kind, a.min_scale) not in cache:
            cache[(a.kind, a.min_scale)] = _channel_values(world, recs, a.kind, cfg, seed, a.min_scale)
        out[i] = COMPUTE[i](cache[(a.kind, a.min_scale)])
    return out


# the configuration of the ground truth: every channel, finest scale, finest sampling, no noise, the whole record
IDEAL = {
    "name": "ideal",
    "kinds": list(KINDS),
    "overrides": {k: {"sample_hz": 10, "noise": 0, "spatial": SPATIAL_CHOICES[k][-1]} for k in KINDS},
    "window": [0.0, ANALYSIS_S],
}


def observe_config(cfg: dict, preset: str, alteration: str, seeds: list[int]) -> dict:
    caps = {d.id: capability_of(cfg, d) for d in DIFFS}
    ids = [d.id for d in DIFFS if caps[d.id]["capable"]]
    va: dict[str, list[float]] = {i: [] for i in ids}
    vb: dict[str, list[float]] = {i: [] for i in ids}
    for s in seeds:
        wa, ra = recorded(preset, "base", s)
        wb, rb = recorded(preset, alteration, s)
        fa, fb = _features(wa, ra, cfg, s * 31 + 1, ids), _features(wb, rb, cfg, s * 31 + 2, ids)
        for i in ids:
            va[i].append(fa[i])
            vb[i].append(fb[i])
    rows = []
    for d in DIFFS:
        cap = caps[d.id]
        observed = None
        if cap["capable"]:
            e = paired_effect(va[d.id], vb[d.id])
            observed = {"feature": d.alt.feature, "kind": d.alt.kind, "proxy": False, "d": e["d"], "p": e["p"], "n": e["n"]}
        rows.append(
            {"id": d.id, "family": d.family, "capability": cap, "observed": observed, "identified": is_identified(observed)}
        )
    return {"name": cfg["name"], "config": cfg, "rows": rows}


# --------------------------------------------------------------------------------------------------------- truth
def definition() -> dict:
    return {
        "version": 1,
        "env": ENV_ID,
        "n": N_CONFIG,
        "warm": WARM,
        "record": RECORD,
        "dt": DT,
        "presets": PRESETS,
        "gen": PRESET_GEN,
        "alterations": ALTERATIONS,
        "thresholds": THRESHOLDS,
        "truth": TRUTH_REF,
        "noise_rel": NOISE_REL,
        "defaults": DEFAULTS,
        "setup": SETUP,
        "diffs": [[d.id, d.alt.feature, d.alt.kind, d.alt.min_scale, d.alt.max_period, d.alt.min_window] for d in DIFFS],
        "start": START_CONFIG,
    }


def definition_digest() -> str:
    return hashlib.sha256(json.dumps(definition(), sort_keys=True, default=list).encode()).hexdigest()


def _cache_path() -> Path:
    return (
        Path(os.environ.get("XZR_CACHE", Path(__file__).resolve().parents[3] / ".cache"))
        / f"oi_truth_{definition_digest()[:16]}.json"
    )


_TRUTH: dict[str, Any] | None = None


def _ref_features(preset: str, alteration: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {d.id: [] for d in DIFFS}
    ids = [d.id for d in DIFFS]
    for i in range(TRUTH_REF["n"]):
        seed = TRUTH_REF["base"] + i
        w, recs = recorded(preset, alteration, seed)
        f = _features(w, recs, IDEAL, seed, ids)
        for k, v in f.items():
            out[k].append(v)
        _RUN_CACHE.pop((preset, alteration, seed), None)  # 64 reference seeds per system would evict the working set
    return out


def truth_of(preset: str, alteration: str) -> dict:
    """Evaluation only. Cached on disk (it is a function of the environment definition alone)."""
    global _TRUTH
    if _TRUTH is None:
        p = _cache_path()
        _TRUTH = json.loads(p.read_text()) if p.exists() else {}
    key = f"{preset}|{alteration}"
    if key not in _TRUTH:
        base = _ref_features(preset, "base")
        alt = _ref_features(preset, alteration)
        ref = {}
        for d in DIFFS:
            e = paired_effect(base[d.id], alt[d.id])
            ref[d.id] = {
                "exists": bool(
                    e["p"] is not None
                    and e["d"] is not None
                    and e["p"] < TRUTH_REF["existP"]
                    and abs(e["d"]) >= TRUTH_REF["existD"]
                ),
                "d": e["d"],
                "p": e["p"],
            }
        _TRUTH[key] = {"reference": ref}
        p = _cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_TRUTH))
    return _TRUTH[key]


def observe(req: dict) -> dict:
    preset, alteration = req["preset"], req["alteration"]
    if preset not in PRESETS:
        raise ValueError(f"oi: unknown preset {preset!r}")
    if alteration not in ALTERATIONS:
        raise ValueError(f"oi: unknown alteration {alteration!r}")
    n = int(req["nSeeds"])
    if not 4 <= n <= 32:
        raise ValueError("oi: nSeeds must be an integer in 4..32")
    cfgs = req["configs"]
    if not 1 <= len(cfgs) <= 6:
        raise ValueError("oi: 1..6 configurations")
    for c in cfgs:
        for k in c["kinds"]:
            if k not in KINDS:
                raise ValueError(f"oi: unknown device kind {k!r}")
    seeds = [int(req["seedBase"]) + i for i in range(n)]
    return {"bodyRuns": 2 * n, "configs": [observe_config(c, preset, alteration, seeds) for c in cfgs]}
