"""Is a generated variable a new variable, or the old one under another name? Two measurements on the runtime world.

1. Redundancy: how much of the derived variable (``activity_trend``) is explained, across regions and seeds, by the variables the instruments
   already carry (activity, tension, memory, recursion, structure) — the share of variance a least-squares fit on them reproduces (R²). Novelty
   = 1 − R². A variable that is a relabelling of an existing one has novelty ≈ 0.
2. Downstream difference: the same seeds run with and without the variable adopted (paired); the operations that read it (picturing) are
   compared on the measures they produce (error, revisions, fired samples). A variable that changes nothing downstream has not entered the
   research, whatever its novelty.

Neither measurement says the variable is *useful*; they say whether it is distinguishable from what was there and whether anything depended on it.
"""

from __future__ import annotations

import numpy as np

from ..hpo import experiments as X
from ..hpo.field import Field
from ..hpo.metrics import measure
from ..hpo.observe import DEFAULT_CATALOG, Instruments, InstrumentSpec
from ..hpo.stats import contrast
from ..hpo.world import build_world

BASE_CHANNELS = ("activity", "tension", "memory", "recursion", "structure")


def novelty(n_seeds: int = 8, level: int = 1, window: int = 16, gen: int = 7200, seed0: int = 72000, steps: int = 24) -> dict:
    X_rows, y_rows = [], []
    for i in range(n_seeds):
        w = build_world(800, gen + i, seed0 + i)
        for _ in range(40 + steps):
            w.step()
        inst = Instruments(w, (*DEFAULT_CATALOG, "activity_trend"))
        cols = {}
        for ch in (*BASE_CHANNELS, "activity_trend"):
            obs, _ = inst.observe(
                InstrumentSpec(channels=(ch,), level=level, window=window, period=1, noise=0.0),
                {ch: (0, 99)},
                np.arange(w.state.n),
                float("inf"),
                None,
                "var",
            )
            cols[ch] = np.array(obs.values[ch], float)
        ok = ~np.isnan(np.stack(list(cols.values()))).any(axis=0)
        X_rows.append(np.stack([cols[c][ok] for c in BASE_CHANNELS], axis=1))
        y_rows.append(cols["activity_trend"][ok])
    Xm, y = np.vstack(X_rows), np.concatenate(y_rows)
    A = np.column_stack([Xm, np.ones(len(Xm))])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    var = float(np.var(y))
    r2 = 1.0 - float(np.var(resid)) / var if var > 0 else None
    corr = {
        c: float(np.corrcoef(Xm[:, k], y)[0, 1]) if np.std(Xm[:, k]) > 0 and var > 0 else None
        for k, c in enumerate(BASE_CHANNELS)
    }
    return {
        "level": level,
        "window": window,
        "n_regions_seeds": int(len(y)),
        "r2_from_existing_channels": r2,
        "novelty": None if r2 is None else 1.0 - r2,
        "correlation_with_each": corr,
        "note": "novelty = 1 - R² of a least-squares fit of the variable on the channels the instruments already carry",
    }


def downstream(n_seeds: int = 8, horizon: int = 240, gen_base: int = 7300, seed_base: int = 73000) -> dict:
    with_v, without = [], []
    for i in range(n_seeds):
        base = X._warm({"n": 800, "regime": "intermittent"}, gen_base + i, seed_base + i, 40)
        ref = base.fork()
        for _ in range(horizon):
            ref.step()
        s = X.settings_for("D", {"warmup": 40, "horizon": horizon})
        for store, extra in ((without, {}), (with_v, {"variables": ["activity_trend"]})):
            f = Field(base.fork().track_rng(), {**s, **extra}, seed_base + i, keep_states=False)
            f.run(horizon)
            store.append(measure(f, ref))
    names = ["picturing_error", "revisions", "fired_samples", "ignitions", "field_ignitions"]
    c = contrast(with_v, without, names, None, 7301)
    return {
        "n_seeds": n_seeds,
        "horizon": horizon,
        "paired_with_vs_without": {m: {k: c[m].get(k) for k in ("n", "mean", "ci95", "dz", "p_holm", "status")} for m in names},
        "note": "same seeds, same settings, static controller; only the adopted variable differs",
    }


# ------------------------------------------------------------------------------------------------------ classification
def identification(n_seeds: int = 12, seed0: int = 7400000, preset: str = "intermittent") -> dict:
    """Does the derived variable identify a difference that no existing pooled channel identifies? For each alteration of the shared task
    (xzr.study.shared.oi_world): paired effect of the pooled trend against the pooled existing channels, same worlds, no noise."""
    from .shared import oi_world as O

    inst_cache: dict[int, Instruments] = {}
    rows = {}
    chans = ("activity", "tension", "memory", "recursion", "structure")
    for alt in O.ALTERATIONS:
        va: dict[str, list[float]] = {c: [] for c in (*chans, "activity_trend")}
        vb: dict[str, list[float]] = {c: [] for c in va}
        for i in range(n_seeds):
            for store, name in ((va, "base"), (vb, alt)):
                w, recs = O.recorded(preset, name, seed0 + i)
                key = id(w)
                inst = inst_cache.get(key) or Instruments(w, (*DEFAULT_CATALOG, "activity_trend"))
                for ch in store:
                    obs, _ = inst.observe(
                        InstrumentSpec(channels=(ch,), level=0, window=16, period=1, noise=0.0),
                        {ch: (0, 99)},
                        np.arange(w.state.n),
                        float("inf"),
                        None,
                        "var",
                    )
                    v = np.asarray(obs.values[ch], float)
                    store[ch].append(float(np.nanmean(v)) if np.any(~np.isnan(v)) else 0.0)
        eff = {c: O.paired_effect(va[c], vb[c]) for c in va}
        ident = {c: O.is_identified(e) for c, e in eff.items()}
        rows[alt] = {
            "d": {c: (None if e["d"] is None else round(float(e["d"]), 3)) for c, e in eff.items()},
            "identified": ident,
            "trend_alone": bool(ident["activity_trend"] and not any(ident[c] for c in chans)),
            "existing_alone": bool(any(ident[c] for c in chans) and not ident["activity_trend"]),
        }
    return {
        "preset": preset,
        "n_seeds": n_seeds,
        "alterations": rows,
        "trend_identifies_what_no_existing_channel_does": [a for a, r in rows.items() if r["trend_alone"]],
        "existing_identify_what_trend_does_not": [a for a, r in rows.items() if r["existing_alone"]],
    }


def availability() -> dict:
    """What adopting the variable changes in what the operations can do (levels of reachability before / after)."""
    from ..hpo import reconfig
    from ..hpo.reachability import compare_levels, levels

    base = X._warm({"n": 800, "regime": "intermittent"}, 7500, 75000, 40)
    f = Field(base.fork(), X.settings_for("D"), 75000, keep_states=False)
    f.run(40)
    before = levels(f)
    reconfig.apply(f, {"path": "variables", "value": "activity_trend", "op": "add", "why": "variable adopted"}, [])
    after = levels(f)
    c = compare_levels(before, after)
    reading = sorted(o.oid for o in f.live() if "activity_trend" in o.needs())
    return {
        "operations_that_read_it": reading,
        "available": {k: c["available"][k] for k in ("gained", "lost")},
        "observable_cells": {"gained": len(c["observable_cells"]["gained"]), "lost": len(c["observable_cells"]["lost"])},
        "effect": c["effect"],
        "note": "static: immediately after adoption; whether the operations then act differently is the downstream measurement",
    }


def classify(n_seeds: int = 8) -> dict:
    """The six things 'a new variable' can be, each with its own measurement and none read as scientific validity:
    new name (never claimed on its own) / transformation of existing variables / compression of existing information / new identification ability /
    new intervention (operation) possibility / change of later research conditions."""
    nv = novelty(n_seeds)
    ident = identification()
    avail = availability()
    down = downstream(n_seeds)
    resolved = [m for m, v in down["paired_with_vs_without"].items() if v["status"] == "DETECTED"]
    return {
        "variable": "activity_trend",
        "definition": "activity in the later half of the window minus the earlier half (per region)",
        "new_name": "not evidence of anything: the variable is a derived channel, never a new name for an existing one (max |correlation| "
        f"with an existing channel {max(abs(c) for c in nv['correlation_with_each'].values() if c is not None):.2f})",
        "transformation_of_existing": {
            "r2_from_existing_channels": nv["r2_from_existing_channels"],
            "novelty": nv["novelty"],
            "reading": "low R² = mostly not a function of the existing channels",
        },
        "compression_of_existing_information": "a difference of two window halves discards the level of activity (it keeps its change): it compresses, it does not contain, the existing channel",
        "new_identification_ability": ident,
        "new_operation_possibility": avail,
        "later_research_conditions": {
            "paired_with_vs_without": down["paired_with_vs_without"],
            "detected_downstream": resolved,
            "reading": "no downstream measure resolved at this sample size" if not resolved else f"resolved: {resolved}",
        },
        "claim_boundary": "novelty and identification ability describe the variable; whether adopting it improves any research outcome is the downstream "
        "measurement only, and a variable that changes nothing downstream has not entered the research whatever its novelty",
    }
