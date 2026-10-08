"""Long-run compression of recurrent trajectories into higher-order shapes.

Every 10 steps the field is summarised at macro resolution (8 clusters × activity, memory, difference) — a
24-dimensional state. Compression: the states are quantized into 32 recurrent shapes (k-means codebook fitted on
all runs of that seed pooled, and shared by them); the symbol
sequence is then factorised into recurring phrases (LZ78). Compressed shapes remain detected summaries — they are
never fed back into the runtime.

For 400, 4,000 and 40,000 steps and the pairs C/D (one-status), C/F (least fixpoint), C/A (no reasoning) plus the
noise replicate C~, measured per seed:
    compression ratio        raw bits / (codebook + phrase) bits
    replay fidelity          R² of the reconstructed 24-d trajectory (centroid of each symbol)
    path dependence          lag-5 autocorrelation of the first principal component, compressed / raw
    intervention fidelity    pair distance ÷ noise-pair distance, compressed vs raw
    counterfactual discrim.  systematic pair difference detected on raw macro means vs on symbol frequencies
    delayed divergence       first window at which the pair differs: raw vs compressed
    hidden local differences correlation between the raw local (512-cluster) activity difference of a pair and
                             the difference reconstructable from the compressed sequence
"""

from __future__ import annotations

import json
import time

import numpy as np

from ...shapes.multiscale import LEVEL_OF, aggregate
from .harness import RESULTS, calibrations, condition, run
from .runner import SEED0, _jsonable, provenance
from .stats import maxt_test

HORIZONS = (400, 4000, 40000)
PAIRS = ("D", "F", "A")
K = 32
EVERY = 10


class _Sampler:
    def __init__(self):
        self.macro: list[np.ndarray] = []
        self.local: list[np.ndarray] = []

    def __call__(self, loop, spec) -> None:
        s = loop.world.state
        if s.t % EVERY:
            return
        h = loop.world.hierarchy
        m, loc = h.labels[LEVEL_OF["macro"]], h.labels[LEVEL_OF["local"]]
        act = loop.probe.ign
        self.macro.append(np.concatenate([aggregate(act, m, 8), aggregate(s.memory, m, 8),
                                          aggregate(s.diff, m, 8)]).astype(np.float32))
        self.local.append(aggregate(act, loc, int(loc.max()) + 1).astype(np.float32))


def kmeans(x: np.ndarray, k: int, seed: int = 0, iters: int = 30) -> np.ndarray:
    """k-means with deterministic k-means++ initialisation."""
    rng = np.random.default_rng(seed)
    k = min(k, len(x))
    init = [x[int(rng.integers(len(x)))].astype(np.float64)]
    for _ in range(1, k):
        d2 = ((x[:, None, :] - np.asarray(init)[None]) ** 2).sum(-1).min(1)
        init.append(x[int(rng.choice(len(x), p=d2 / d2.sum()))] if d2.sum() > 0 else x[int(rng.integers(len(x)))])
    c = np.asarray(init, dtype=np.float64)
    for _ in range(iters):
        lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        for j in range(len(c)):
            if (lab == j).any():
                c[j] = x[lab == j].mean(0)
    return c


def encode(x: np.ndarray, c: np.ndarray) -> np.ndarray:
    return ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)


def lz78_phrases(sym: np.ndarray) -> int:
    d: dict[tuple, int] = {}
    cur: tuple = ()
    n = 0
    for s in sym.tolist():
        nxt = (*cur, s)
        if nxt in d:
            cur = nxt
        else:
            d[nxt] = len(d)
            n += 1
            cur = ()
    return n + (1 if cur else 0)


def _bits(sym: np.ndarray, dims: int, k: int) -> tuple[float, float]:
    raw = len(sym) * dims * 32.0
    ph = lz78_phrases(sym)
    comp = k * dims * 32.0 + ph * (np.log2(max(ph, 2)) + np.log2(k))
    return raw, comp


def _pc1_autocorr(x: np.ndarray, lag: int = 5) -> float:
    z = (x - x.mean(0)) / (x.std(0) + 1e-9)
    u, s_, vt = np.linalg.svd(z, full_matrices=False)
    p = z @ vt[0]
    if len(p) <= lag + 2:
        return 0.0
    return float(np.corrcoef(p[:-lag], p[lag:])[0, 1])


def seed_job(args: tuple) -> dict:
    horizon, seed, gains = args
    c = condition(id=f"compression:{horizon}", horizon=horizon)
    runs: dict[str, _Sampler] = {}
    timing: dict[str, float] = {}
    for key, letter, s in (("C", "C", seed), ("C~", "C", seed + 1000), *((p, p, seed) for p in PAIRS)):
        smp = _Sampler()
        run(c, letter, s, gains, configure=lambda loop, spec: None, per_step=smp)
        runs[key] = smp
    pooled = np.concatenate([np.stack(smp.macro) for smp in runs.values()])  # one codebook per seed, all runs
    mu, sd = pooled.mean(0), pooled.std(0) + 1e-9
    t0 = time.perf_counter()
    cb = kmeans((pooled - mu) / sd, K, seed)
    timing["codebook_s"] = time.perf_counter() - t0
    enc = {}
    t0 = time.perf_counter()
    for key, smp in runs.items():
        x = (np.stack(smp.macro) - mu) / sd
        enc[key] = (x, encode(x, cb))
    timing["encode_s"] = time.perf_counter() - t0
    out: dict = {"seed": seed, "per_run": {}, "pairs": {}, "timing": timing}
    for key, (x, sym) in enc.items():
        raw, comp = _bits(sym, x.shape[1], K)
        rec = cb[sym]
        r2 = 1 - ((x - rec) ** 2).sum() / ((x - x.mean(0)) ** 2).sum()
        out["per_run"][key] = {"windows": len(sym), "ratio": raw / comp, "phrases": lz78_phrases(sym),
                               "replay_r2": float(r2),
                               "path_dependence": {"raw": _pc1_autocorr(x), "compressed": _pc1_autocorr(rec)},
                               "symbol_freq": np.bincount(sym, minlength=K).astype(float) / len(sym),
                               "macro_mean": x.mean(0)}
    xc, sc = enc["C"]
    xn, sn = enc["C~"]
    loc_c = np.stack(runs["C"].local)
    for p in PAIRS:
        xp, sp = enc[p]
        loc_p = np.stack(runs[p].local)
        raw_d = float(np.linalg.norm(xp - xc, axis=1).mean() / (np.linalg.norm(xn - xc, axis=1).mean() + 1e-12))
        comp_d = float(np.mean(sp != sc) / (np.mean(sn != sc) + 1e-12))
        diff_raw = np.flatnonzero(np.any(np.abs(xp - xc) > 1e-9, axis=1))
        diff_sym = np.flatnonzero(sp != sc)
        # local differences reconstructable from symbols: mean local vector per symbol (from the reference run)
        means = np.stack([loc_c[sc == j].mean(0) if (sc == j).any() else loc_c.mean(0) for j in range(K)])
        rec_diff = (means[sp] - means[sc]).mean(0)
        raw_diff = (loc_p - loc_c).mean(0)
        corr = float(np.corrcoef(raw_diff, rec_diff)[0, 1]) if raw_diff.std() > 0 and rec_diff.std() > 0 else 0.0
        out["pairs"][p] = {"raw_distance_ratio": raw_d, "compressed_distance_ratio": comp_d,
                           "onset_raw": int(diff_raw[0]) if len(diff_raw) else None,
                           "onset_compressed": int(diff_sym[0]) if len(diff_sym) else None,
                           "local_difference_correlation": corr,
                           "local_difference_magnitude_raw": float(np.abs(raw_diff).mean()),
                           "local_difference_magnitude_compressed": float(np.abs(rec_diff).mean())}
    return out


def _systematic(jobs: list[dict], key: str, field: str) -> dict:
    a = np.stack([j["per_run"][key][field] for j in jobs])
    b = np.stack([j["per_run"]["C"][field] for j in jobs])
    r = maxt_test((a - b).astype(np.float64), np.abs(b).mean(0) + 1e-3)
    return {"detected": bool(r["detected"].any()), "p": r["p"], "max_t": r["max_t"]}


def main(procs: int = 7, seeds: int = 12) -> dict:
    from concurrent.futures import ProcessPoolExecutor
    path = RESULTS / "compression.json"
    doc = json.loads(path.read_text()) if path.exists() else {"horizons": {}}
    gains = calibrations([condition()], procs)
    for h in HORIZONS:
        if str(h) in doc["horizons"]:
            continue
        with ProcessPoolExecutor(procs) as ex:
            jobs = list(ex.map(seed_job, [(h, SEED0 + k, gains) for k in range(seeds)]))
        res: dict = {"seeds": seeds, "symbols": K, "every": EVERY, "per_variant": {}, "pairs": {}}
        for key in ("C", "C~", *PAIRS):
            pr = [j["per_run"][key] for j in jobs]
            res["per_variant"][key] = {
                "compression_ratio": _ms([x["ratio"] for x in pr]), "phrases": _ms([x["phrases"] for x in pr]),
                "replay_r2": _ms([x["replay_r2"] for x in pr]),
                "path_dependence_raw": _ms([x["path_dependence"]["raw"] for x in pr]),
                "path_dependence_compressed": _ms([x["path_dependence"]["compressed"] for x in pr])}
        for p in PAIRS:
            pp = [j["pairs"][p] for j in jobs]
            onsets = [(x["onset_raw"], x["onset_compressed"]) for x in pp]
            res["pairs"][p] = {
                "raw_distance_ratio": _ms([x["raw_distance_ratio"] for x in pp]),
                "compressed_distance_ratio": _ms([x["compressed_distance_ratio"] for x in pp]),
                "systematic_raw": _systematic(jobs, p, "macro_mean"),
                "systematic_compressed": _systematic(jobs, p, "symbol_freq"),
                "onset_delay_windows": _ms([b - a for a, b in onsets if a is not None and b is not None]),
                "onset_missing_compressed": sum(1 for a, b in onsets if a is not None and b is None),
                "local_difference_correlation": _ms([x["local_difference_correlation"] for x in pp]),
                "local_magnitude_ratio": _ms([x["local_difference_magnitude_compressed"] /
                                             (x["local_difference_magnitude_raw"] + 1e-12) for x in pp])}
        res["timing"] = {k: _ms([j["timing"][k] for j in jobs]) for k in jobs[0]["timing"]}
        res["provenance"] = {**provenance(), "experiment": "compression", "horizon": h,
                             "engine_seeds": [j["seed"] for j in jobs]}
        doc["horizons"][str(h)] = _jsonable(res)
        path.write_text(json.dumps(doc))
        print("compression", h, "done", flush=True)
    return doc


def _ms(xs: list) -> dict:
    a = np.asarray([x for x in xs if x is not None], dtype=float)
    if not a.size:
        return {"mean": None, "sd": None}
    return {"mean": round(float(a.mean()), 4), "sd": round(float(a.std(ddof=1)) if a.size > 1 else 0.0, 4)}
