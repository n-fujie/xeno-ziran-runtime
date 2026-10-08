"""Statistics and classification rules for the resolution-escalation experiments.

Paired design: for every seed the two runs of a comparison share world, generator seed, engine random stream and
schedule; only the structural variant differs. For a resolution with U units (configurations, clusters or global
aggregates) × K time segments × F features, the per-seed paired differences d[s, ·] are tested with a sign-flip
max-|t| permutation test (all 2^S sign patterns), which controls the family-wise error over every unit, segment and
feature of that resolution. Across the five resolutions the level is Bonferroni-split (α = 0.01 / 5).

An effect counts only when it is (a) family-wise significant and (b) practically non-negligible: |mean d| ≥ 2 %
of the mean absolute baseline of that unit. A null result is *adequately powered* when the minimum detectable
effect (80 % power at the permutation critical value) is ≤ the smallest effect of interest (5 %); otherwise it is
UNRESOLVED.

Equivalence (for calling a resolution EQUIVALENT rather than UNRESOLVED) follows the two-one-sided-tests logic per
quantity: the 90 % confidence half-width of the paired difference must be ≤ 5 % of the baseline; a resolution is
equivalent when this holds for the median quantity of its last two segments. Paired differences smaller than
1e-6 of the baseline are exact zeros (float32 rounding of identical runs).
"""

from __future__ import annotations

import itertools

import numpy as np
from scipy.stats import t as student_t

ALPHA = 0.01
RESOLUTIONS = ("node", "local", "meso", "macro", "global")
FAMILIES = ("segment", "aggregate")  # per resolution: time segments, and the post-reasoning time average
ALPHA_PER_RESOLUTION = ALPHA / (len(RESOLUTIONS) * len(FAMILIES))
PRACTICAL = 0.02
SESOI = 0.05  # smallest effect size of interest (relative) for calling a null adequately powered
T_POWER = 0.88  # ≈ t quantile for 80 % power (df ≈ 10); added to the critical value for the MDE


MAX_EXACT_SEEDS = 14
MC_PATTERNS = 4096


def sign_matrix(s: int) -> np.ndarray:
    """All 2^s sign patterns (exact test) for s ≤ 14; otherwise the identity plus 4,096 seeded random patterns
    (Monte Carlo permutation test)."""
    if s <= MAX_EXACT_SEEDS:
        return np.array(list(itertools.product((1.0, -1.0), repeat=s)), dtype=np.float32)
    rng = np.random.default_rng(12345)
    m = rng.choice((1.0, -1.0), size=(MC_PATTERNS, s)).astype(np.float32)
    return np.concatenate([np.ones((1, s), np.float32), m])


def maxt_test(d: np.ndarray, base: np.ndarray, alpha: float = ALPHA_PER_RESOLUTION, chunk: int = 4096) -> dict:
    """d: (S, M) paired differences (seeds × tests); base: (M,) mean absolute baseline per test.

    Returns the family-wise p value of the largest |t|, the critical |t|, the detected tests (significant and ≥ the
    practical threshold), relative effects and the relative minimum detectable effect per test."""
    s, m = d.shape
    d = d.astype(np.float64)
    d[np.abs(d) <= 1e-6 * np.maximum(base, 1e-9)[None, :]] = 0.0
    ss = (d ** 2).sum(0)
    mean = d.mean(0)
    var = (ss - s * mean ** 2) / (s - 1)
    sd = np.sqrt(np.maximum(var, 0))
    # a difference that is the same in every seed (zero spread, nonzero mean) is deterministic: no random stream
    # changes it. It is reported as such and kept out of the permutation maximum (its flips are ±inf).
    determ = (sd <= 1e-5 * np.abs(mean)) & (mean != 0)  # float32 summaries: 1e-5 relative spread = none
    with np.errstate(divide="ignore", invalid="ignore"):
        t_obs = np.where(sd > 0, mean / (sd / np.sqrt(s)), np.where(mean != 0, np.inf, 0.0))
    t_obs = np.where(determ, np.copysign(np.inf, mean), t_obs)
    signs = sign_matrix(s)
    maxes = np.zeros(len(signs))
    signs64 = signs.astype(np.float64)
    for a in range(0, m, chunk):
        dd = d[:, a:a + chunk]  # float64: near-constant columns lose precision in float32 (ss − s·m² cancels)
        mm = signs64 @ dd / s  # (P, chunk)
        v = (ss[a:a + chunk][None, :] - s * mm ** 2) / (s - 1)
        sdp = np.sqrt(np.maximum(v, 1e-300))
        tt = np.abs(mm) / (sdp / np.sqrt(s))
        tt[:, (sd[a:a + chunk] == 0) | determ[a:a + chunk]] = 0.0
        maxes = np.maximum(maxes, tt.max(1))
    fin = np.isfinite(t_obs)
    obs = float(np.max(np.abs(t_obs[fin]))) if fin.any() else 0.0
    # the identity pattern is one of the permutations, so p ≥ 1/2^S (float32 rounding tolerated)
    p = max(float((maxes >= obs * (1 - 1e-4)).mean()), 1.0 / len(signs))
    crit = float(np.quantile(maxes, 1 - alpha))
    base = np.maximum(base, 1e-12)
    rel = mean / base
    sig = fin & (np.abs(t_obs) >= crit) & (p <= alpha)
    detected = (sig | determ) & (np.abs(rel) >= PRACTICAL)
    mde = (crit + T_POWER) * (sd / np.sqrt(s)) / base
    half = float(student_t.ppf(0.95, s - 1)) * (sd / np.sqrt(s)) / base  # 90 % CI half-width, relative
    return {"p": p, "crit": crit, "max_t": obs if np.isfinite(obs) else "inf", "detected": detected,
            "rel": rel, "t": t_obs, "mde": mde, "ci_half": half, "deterministic": determ & (np.abs(rel) >= PRACTICAL),
            "min_p_attainable": 2.0 / len(signs)}


def time_pattern(seg_detect: list[bool]) -> str:
    """none | persistent | transient | recurrent from per-segment detection."""
    if not any(seg_detect):
        return "none"
    first = seg_detect.index(True)
    tail = seg_detect[first:]
    if all(tail):
        return "persistent"
    runs = sum(1 for a, b in zip([False, *tail], tail, strict=False) if b and not a)
    if runs >= 2:
        return "recurrent"
    return "transient"


# ------------------------------------------------------------------------------------------------ classification
LABELS = ("NON-REDUNDANT", "HIDDEN AT COARSE RESOLUTION", "TRANSIENT", "REGIME-DEPENDENT", "SCALE-DEPENDENT",
          "TOPOLOGY-DEPENDENT", "TIME-WINDOW-DEPENDENT", "MEMORY-DEPENDENT", "REDUNDANT", "UNRESOLVED")
COARSE = ("meso", "macro", "global")
FINE = ("node", "local")


def resolution_status(r: dict) -> str:
    if r["detected"]:
        return "DETECTED"
    return "EQUIVALENT" if r["equivalent"] else "UNRESOLVED"


def classify_condition(res: dict) -> dict:
    """Classification of one comparison in one condition.

    res: {"exact_identical_share", "resolutions": {r: {"detected", "equivalent", "pattern", "onset_segment"}},
          "horizon"}"""
    rs = res["resolutions"]
    status = {r: resolution_status(rs[r]) for r in RESOLUTIONS}
    out: dict = {"labels": [], "status": status, "visible_from": None}
    if res["exact_identical_share"] >= 1.0:
        out["labels"] = ["REDUNDANT"]
        out["primary"] = "REDUNDANT"
        out["evidence"] = "bit-identical in every seed"
        return out
    hit = [r for r in RESOLUTIONS if status[r] == "DETECTED"]
    coarse_hit = [r for r in COARSE if status[r] == "DETECTED"]
    fine_hit = [r for r in FINE if status[r] == "DETECTED"]
    out["visible_from"] = hit[0] if hit else "exact"  # finest resolution with a systematic difference
    out["visible_up_to"] = hit[-1] if hit else "exact"  # coarsest resolution with a systematic difference
    macro_global_equivalent = status["macro"] == "EQUIVALENT" and status["global"] == "EQUIVALENT"
    if coarse_hit:
        out["labels"].append("NON-REDUNDANT")
        pats = {rs[r]["pattern"] for r in coarse_hit}
        if pats <= {"transient"}:
            out["labels"].append("TRANSIENT")
        # onset from the segment family only (a detection of the time average alone has no onset)
        onsets = [rs[r]["onset_segment"] for r in coarse_hit if rs[r]["onset_segment"] is not None]
        if onsets and min(onsets) >= 2 and res["horizon"] >= 4000:
            out["labels"].append("TIME-WINDOW-DEPENDENT")
        out["primary"] = "NON-REDUNDANT"
        out["evidence"] = f"systematic difference at {', '.join(coarse_hit)}"
    elif macro_global_equivalent:
        out["labels"].append("HIDDEN AT COARSE RESOLUTION")
        out["hidden_kind"] = "systematic fine-scale" if fine_hit else "exact-only"
        if status["meso"] == "UNRESOLVED":
            out["hidden_kind"] += " (meso unresolved)"
        out["primary"] = "HIDDEN AT COARSE RESOLUTION"
        out["evidence"] = ("trajectories differ" + (f"; systematic at {', '.join(fine_hit)}" if fine_hit else "") +
                           "; macro and global equivalent within 5 %")
    else:
        out["labels"].append("UNRESOLVED")
        if fine_hit:
            out["labels"].append("HIDDEN AT COARSE RESOLUTION")  # fine difference shown; coarse equivalence not
        out["primary"] = "UNRESOLVED"
        out["evidence"] = "trajectories differ; coarse equivalence not established (confidence half-width > 5 %)"
    return out


FACTOR_LABEL = {"topology": "TOPOLOGY-DEPENDENT", "memory": "MEMORY-DEPENDENT", "horizon": "TIME-WINDOW-DEPENDENT",
                "n": "SCALE-DEPENDENT", "size": "SCALE-DEPENDENT", "coupling": "REGIME-DEPENDENT",
                "mutation": "REGIME-DEPENDENT", "return": "REGIME-DEPENDENT", "address": "REGIME-DEPENDENT",
                "structure": "REGIME-DEPENDENT"}


def factor_dependence(levels: dict[str, dict]) -> dict:
    """levels: factor level -> condition classification. A comparison is dependent on the factor when it is visible
    at a coarse resolution at some levels and equivalent within the margin — with adequate power — at others."""
    vis = {k: "NON-REDUNDANT" in v["labels"] for k, v in levels.items()}
    null_adequate = {k: (not vis[k]) and "UNRESOLVED" not in v["labels"] for k, v in levels.items()}
    on = sorted(k for k, x in vis.items() if x)
    off = sorted(k for k, x in null_adequate.items() if x)
    unresolved = sorted(k for k in levels if not vis[k] and not null_adequate[k])
    return {"visible_at": on, "absent_at": off, "unresolved_at": unresolved,
            "dependent": bool(on) and bool(off)}
