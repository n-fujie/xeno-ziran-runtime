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
