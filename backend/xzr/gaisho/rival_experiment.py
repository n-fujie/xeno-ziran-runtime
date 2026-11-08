"""The matched-rival comparison on the XB-TRO body, as R20 section 18D asks for it (see ``rival.py`` for the rival and for why it is built as it is).

Frozen BEFORE the final run (and hashed into every record, ``PROTOCOL_DIGEST``):

* Q (target relation): does the body fall within the horizon, per replication seed, on the grid of the laboratory's domain 004 (sensory delay added 0 - 0.2 s x push 0 - 200 N, 5 x 5 cells, 8 seeds).
* O: the engine's reference record of the run (this is a simulator-internal comparison, not an observation of a body). Primary endpoint: share of falls. Secondary endpoints, never merged into a score: energy used among the runs
  that stay up (a policy that stays up by refusing the task would not be efficient; here the task is only "stay up under the cue and the push"), sway RMS and peak deviation among the runs that stay up.
* Conditions: the human-like planar preset; a strategy swap alone (``neural.strategy`` = whole-body, no Xeno-14 rule); the Xeno-14 principles (all fourteen together as the XenoBody condition, and each alone); the ordinary
  optimal-feedback rival (default cost; two cost sensitivities; the preset's nominal delay assumed instead of the true one; the rival acting on a whole-body reference); controls.
* Same seeds, same noise streams (common random numbers), same plant, same sensors, same lines' latency, same activation and energy ledger, same slow gain adaptation, same torque limits.
* Contrast: paired over the replication seeds, on the share of falls over the grid, Student t interval (8 seeds: 2.365), margin ``DELTA`` = 0.03 (the margin of the laboratory's surface models, kept so that the two are comparable).
* Verdicts: A_BETTER / B_BETTER (the interval lies beyond the margin), EQUIVALENT (inside +/- the margin), UNRESOLVED (neither). A conclusion drawn from an EQUIVALENT is only "non-exclusive for this task, apparatus,
  scale and horizon": it does not withdraw a practice, a vocabulary, or the existence of a mechanism.
* H-L (label invariance): the labels, aliases and notes of the configuration are replaced and the records must be bit-identical.
* Exploration seeds (1000 - 1007) were used only to check that the rival is a working controller (the viability criterion below); the final seeds are 5000 - 5007 (``metrics.FINAL_SEED_BASE``).

Viability criterion of the rival, fixed before the final run: it holds the unperturbed, undelayed cell without a fall on 8 of 8 exploration seeds. It is NOT tuned to beat or to lose to anything.

What this is not: a statement about a person, a practice, a Gaisho, or XenoBody as practised; the result is about a simulated planar body with these stipulated lines and this controller."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import numpy as np

from xzr.xbtro import config, engine, metrics, xeno14

from .model import digest
from .rival import R_SCALES, OrdinaryFeedback

DELAYS = [0.0, 0.05, 0.10, 0.15, 0.20]
PUSHES = [0.0, 50.0, 100.0, 150.0, 200.0]
FINAL_SEEDS = list(range(5000, 5008))
EXPLORATION_SEEDS = list(range(1000, 1008))
DELTA = 0.03
T975_8 = 2.365
PRESET = "human-like-planar"
ALL14 = [p["id"] for p in xeno14.PRINCIPLES]

#: name -> specification. ``rival`` None = the preset's own law.
CONDITIONS: dict[str, dict[str, Any]] = {
    "baseline": {},
    "baseline, whole-body reference (strategy swap only)": {"strategy": "whole-body"},
    "XenoBody: all fourteen principles": {"x14": ALL14},
    "rival (ordinary optimal feedback)": {"rival": {}},
    "rival, whole-body reference": {"rival": {}, "strategy": "whole-body"},
    "rival, cost x0.3": {"rival": {"r_scale": R_SCALES[0]}},
    "rival, cost x3": {"rival": {"r_scale": R_SCALES[2]}},
    "rival, nominal delay assumed": {"rival": {"nominal_delay": True}},
}
for _pid in ALL14:
    CONDITIONS[f"XenoBody: {_pid} alone"] = {"x14": [_pid]}
MAIN = [k for k in CONDITIONS if not k.startswith("XenoBody: ") or k == "XenoBody: all fourteen principles"]
SINGLES = [k for k in CONDITIONS if k.startswith("XenoBody: ") and k != "XenoBody: all fourteen principles"]

CONTRASTS: list[tuple[str, str, str, str]] = [
    # (id, A, B, what it asks)
    ("C1", "XenoBody: all fourteen principles", "baseline", "is there a preferred result to compare at all (XenoBody against the preset's own law)?"),
    ("C2", "XenoBody: all fourteen principles", "rival (ordinary optimal feedback)", "does XenoBody differ from the ordinary optimal-feedback rival (same body, same signals, same ledger)?"),
    ("C3", "XenoBody: all fourteen principles", "rival, whole-body reference", "the same, with the rival also given the whole-body reference"),
    ("C4", "baseline, whole-body reference (strategy swap only)", "baseline", "does an ordinary strategy swap alone move the result?"),
    ("C5", "rival (ordinary optimal feedback)", "baseline", "is the rival better than the preset's own law (a check on the rival, not on XenoBody)?"),
    ("C6", "XenoBody: all fourteen principles", "rival, cost x0.3", "sensitivity of C2 to the rival's control cost"),
    ("C7", "XenoBody: all fourteen principles", "rival, cost x3", "sensitivity of C2 to the rival's control cost"),
    ("C8", "XenoBody: all fourteen principles", "rival, nominal delay assumed", "sensitivity of C2 to the delay the rival believes"),
]

PROTOCOL = {
    "model": "xbtro matched-rival comparison v1",
    "preset": PRESET,
    "grid": {"delay_added_s": DELAYS, "push_N": PUSHES},
    "final_seeds": FINAL_SEEDS,
    "exploration_seeds": EXPLORATION_SEEDS,
    "delta": DELTA,
    "t975": T975_8,
    "conditions": CONDITIONS,
    "contrasts": [list(c) for c in CONTRASTS],
    "rival": {"module": "xzr.gaisho.rival", "cost_scales": list(R_SCALES)},
    "endpoints": {"primary": "share of falls over the grid", "secondary": ["energy_used among survivors", "sway_rms among survivors", "peak_dev among survivors"]},
}
PROTOCOL_DIGEST = digest(PROTOCOL)


def build_config(spec: dict[str, Any], delay: float, push: float) -> dict[str, Any]:
    cfg = config.build(PRESET)
    if spec.get("strategy"):
        cfg = copy.deepcopy(cfg)
        cfg["neural"]["strategy"] = spec["strategy"]
    if spec.get("x14"):
        cfg = xeno14.apply(cfg, spec["x14"])
    if delay > 0:
        cfg = config.apply_intervention(cfg, "sensory_delay", float(delay))
    cfg = config.apply_intervention(cfg, "perturbation", float(push))
    return cfg


def rival_for(spec: dict[str, Any]) -> OrdinaryFeedback | None:
    if "rival" not in spec:
        return None
    r = spec["rival"]
    assumed = None
    if r.get("nominal_delay"):
        nom = engine.Params(config.build(PRESET))
        assumed = (nom.delay_steps("sens.proprio"), nom.delay_steps("neural.central.ankle"))
    return OrdinaryFeedback(r_scale=r.get("r_scale", 1.0), assumed_delay_steps=assumed)


def run_cell(name: str, delay: float, push: float, seeds: list[int]) -> dict[str, Any]:
    spec = CONDITIONS[name]
    run = engine.simulate(build_config(spec, delay, push), seeds, ext_ctrl=rival_for(spec))
    m = metrics.summary(run)
    fell = np.asarray(run.fell, dtype=float)
    stay = fell < 0.5

    def surv(key: str) -> list[float | None]:
        v = np.asarray(m[key], dtype=float)
        return [float(x) if (ok and np.isfinite(x)) else None for x, ok in zip(v, stay, strict=True)]

    return {"fell": fell.tolist(), "energy_used": surv("energy_used"), "sway_rms": surv("sway_rms"), "peak_dev": surv("peak_dev")}


def _job(args: tuple[str, list[int]]) -> tuple[str, dict[str, Any]]:
    name, seeds = args
    cells: dict[str, Any] = {}
    for p in PUSHES:
        for d in DELAYS:
            cells[f"{d:g}|{p:g}"] = run_cell(name, d, p, seeds)
    return name, cells


def run_conditions(names: list[str], seeds: list[int]) -> dict[str, Any]:
    """Sequential; ``scripts/gaisho_rival.py`` runs the same ``_job`` in a process pool (this package touches no file and starts no process, see tests/test_gaisho.py)."""
    return {nm: _job((nm, seeds))[1] for nm in names}


# ------------------------------------------------------------------------------------------------ analysis
def fall_share_by_seed(cells: dict[str, Any], keys: list[str] | None = None) -> np.ndarray:
    ks = keys or list(cells)
    return np.mean([np.asarray(cells[k]["fell"], dtype=float) for k in ks], axis=0)


def paired(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    d = a - b
    n = len(d)
    m = float(d.mean())
    se = float(d.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
    lo, hi = m - T975_8 * se, m + T975_8 * se
    if hi < -DELTA:
        v = "A_BETTER"  # A falls less
    elif lo > DELTA:
        v = "B_BETTER"
    elif lo >= -DELTA and hi <= DELTA:
        v = "EQUIVALENT"
    else:
        v = "UNRESOLVED"
    return {"mean_difference_A_minus_B": m, "interval": [lo, hi], "verdict": v, "n": n}


def regime_keys() -> dict[str, list[str]]:
    keys = {f"{d:g}|{p:g}": (d, p) for p in PUSHES for d in DELAYS}
    return {
        "whole grid": list(keys),
        "low demand (delay <= 0.05 s and push <= 100 N)": [k for k, (d, p) in keys.items() if d <= 0.05 and p <= 100],
        "high demand (delay >= 0.15 s or push >= 150 N)": [k for k, (d, p) in keys.items() if d >= 0.15 or p >= 150],
    }


def survivors_mean(cells_a: dict[str, Any], cells_b: dict[str, Any], key: str) -> dict[str, Any]:
    """Secondary endpoint among the cells x seeds where BOTH conditions stay up (so that neither is credited for a run it did not complete)."""
    da, db = [], []
    for k in cells_a:
        for x, y in zip(cells_a[k][key], cells_b[k][key], strict=True):
            if x is not None and y is not None:
                da.append(x)
                db.append(y)
    if not da:
        return {"n_pairs": 0}
    da_a, db_a = np.asarray(da), np.asarray(db)
    return {"n_pairs": len(da), "mean_A": float(da_a.mean()), "mean_B": float(db_a.mean()), "mean_difference_A_minus_B": float((da_a - db_a).mean())}


def analyse(results: dict[str, Any]) -> dict[str, Any]:
    rk = regime_keys()
    out: dict[str, Any] = {"fall_share_by_condition": {}, "contrasts": {}}
    for nm, cells in results.items():
        out["fall_share_by_condition"][nm] = {reg: float(fall_share_by_seed(cells, ks).mean()) for reg, ks in rk.items()}
    for cid, a, b, ask in CONTRASTS:
        if a not in results or b not in results:
            continue
        row: dict[str, Any] = {"A": a, "B": b, "asks": ask, "primary": {}, "secondary_among_survivors_of_both": {}}
        for reg, ks in rk.items():
            row["primary"][reg] = paired(fall_share_by_seed(results[a], ks), fall_share_by_seed(results[b], ks))
        for key in ("energy_used", "sway_rms", "peak_dev"):
            row["secondary_among_survivors_of_both"][key] = survivors_mean(results[a], results[b], key)
        out["contrasts"][cid] = row
    return out


def classify(analysis: dict[str, Any]) -> dict[str, Any]:
    """The reading of C1 / C2 / C3 in the vocabulary of 18D: is there a preferred result, and does an information-matched rival reproduce it?"""
    c = analysis["contrasts"]
    whole = "whole grid"
    out: dict[str, Any] = {}
    if "C1" in c:
        v = c["C1"]["primary"][whole]["verdict"]
        out["preferred_result"] = {"A_BETTER": "XenoBody falls less than the preset's own law by more than the margin", "EQUIVALENT": "no difference beyond the margin", "B_BETTER": "XenoBody falls MORE than the preset's own law", "UNRESOLVED": "unresolved"}[v]
    rivals = [x for x in ("C2", "C3", "C6", "C7", "C8") if x in c]
    if rivals:
        verdicts = {x: c[x]["primary"][whole]["verdict"] for x in rivals}
        out["against_rival_variants"] = verdicts
        if all(v == "A_BETTER" for v in verdicts.values()):
            out["reading"] = "DISTINGUISHED_FROM_ALL_RIVAL_VARIANTS_ON_THIS_GRID"
        elif any(v in ("EQUIVALENT", "B_BETTER") for v in verdicts.values()):
            out["reading"] = "NON_EXCLUSIVE_ON_THIS_GRID: at least one information-matched rival variant reproduces or exceeds the XenoBody result"
        else:
            out["reading"] = "UNRESOLVED_ON_THIS_GRID"
    return out


# ------------------------------------------------------------------------------------------------ H-L: label invariance
LABEL_KEYS = ("label", "note", "alias", "name", "family", "kind_label")


def scramble_labels(obj: Any, tag: str = "x") -> Any:
    if isinstance(obj, dict):
        return {k: (f"{tag}-{hashlib.sha1(str(v).encode()).hexdigest()[:6]}" if k in LABEL_KEYS and isinstance(v, str) and k != "family" else scramble_labels(v, tag)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scramble_labels(v, tag) for v in obj]
    return obj


def label_invariance(seeds: list[int]) -> dict[str, Any]:
    """The same condition with every label / note / alias replaced must give bit-identical records (R81 / R86 style sham-label control, H-L)."""
    rows = []
    for nm in ("XenoBody: all fourteen principles", "rival (ordinary optimal feedback)"):
        spec = CONDITIONS[nm]
        cfg = build_config(spec, 0.1, 100.0)
        cfg2 = scramble_labels(cfg)
        r1 = engine.simulate(cfg, seeds, ext_ctrl=rival_for(spec))
        r2 = engine.simulate(cfg2, seeds, ext_ctrl=rival_for(spec))
        same = all(np.array_equal(np.asarray(r1[k]), np.asarray(r2[k])) for k in ("theta", "omega", "tau", "energy", "line_u"))
        rows.append({"condition": nm, "labels_changed": cfg != cfg2, "records_bit_identical": bool(same)})
    return {"cell": "delay 0.1 s, push 100 N", "seeds": seeds, "rows": rows}


def record(results: dict[str, Any], seeds: list[int], mode: str, code_digest: str = "") -> dict[str, Any]:
    an = analyse(results)
    body = {
        "protocol_digest": PROTOCOL_DIGEST,
        "code_digest": code_digest,
        "mode": mode,
        "seeds": seeds,
        "analysis": an,
        "reading": classify(an),
        "cells": results,
    }
    body["record_digest"] = digest({k: v for k, v in body.items() if k != "cells"})
    return body


def dumps(rec: dict[str, Any]) -> str:
    return json.dumps(rec, indent=1, sort_keys=True)
