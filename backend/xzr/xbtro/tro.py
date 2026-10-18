"""Total Relational Observation: what a given observation configuration can and cannot identify.

Given two body conditions (paired by seed) and an observation configuration, ``assess`` answers, for each catalogued difference:
does it exist in the model reference? could this configuration observe it at all? is it identified from the observations alone?
If it is not observed, *why* (one of six reasons) — and separately from differences that do not exist in the model.

The six reasons an existing difference stays unobserved
  unmeasured                no model of the kind that could see it is deployed (but such a model exists in the inventory)
  device-mismatch           a model of the same aspect is deployed but its signal cannot carry this quantity
  scale-mismatch            the model's spatial resolution is coarser than the quantity needs
  time-window-mismatch      the model's time resolution is too coarse for the quantity's time scale
  boundary-invisible        the quantity lies outside the observation boundary (region not covered, blind window or region)
  measurement-impossible    no observation signal in the inventory can carry it at all (it exists only as model-internal state)
and one more outcome, ``noise-limited``: capable and in range, but the observed effect is not distinguishable from noise.

Operations: ``boundary_transformation`` (change boundary, scale, time window, placement and record why), ``observability_comparison``
(two configurations on the same pair of conditions), ``induced_change`` (what the apparatus does to the body), ``reconfigure``
(candidate changes for unobserved differences, with the reason, the information used, the expected and the actual result).
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import metrics, observation, stats, velocity
from .engine import Run

SCALE = {"posture": {"joint": 3, "segment": 2, "pooled": 1}, "imu": {"segment": 2, "pooled": 1},
         "emg": {"joint-pair": 4, "joint": 3, "pooled": 1}, "contact": {"detailed": 3, "pooled": 1},
         "respiration": {"chest": 2}, "eeg": {"regional": 2, "pooled": 1}, "latency": {"derived": 3}, "threshold": {"derived": 3}}
FAMILY_KINDS = {"kinematic": {"posture", "imu"}, "muscular": {"emg"}, "contact": {"contact"}, "respiratory": {"respiration"},
                "neural": {"eeg"}, "internal": {"respiration", "emg"}, "latent": set()}
ATTENUATION = {"posture": 0.9, "imu": 0.8, "emg": 0.7, "contact": 0.8, "eeg": 0.4, "respiration": 0.5, "latency": 0.7, "threshold": 0.6}
ALL_BODY = ["shank", "thigh", "trunk", "head"]
EXIST_P, EXIST_D = 0.05, 0.5          # a reference difference "exists" when paired p < 0.05 and |d| >= 0.5
IDENT_P, IDENT_D = 0.01, 0.8          # an observed difference is "identified" when p < 0.01, |d| >= 0.8 and the sign agrees
CATEGORIES = ("unmeasured", "device-mismatch", "scale-mismatch", "time-window-mismatch", "boundary-invisible", "measurement-impossible")


def _alt(feature: str, kind: str, regions: list[str], min_scale: int, max_period: float, proxy: bool = False) -> dict[str, Any]:
    return {"feature": feature, "kind": kind, "regions": regions, "min_scale": min_scale, "max_period_s": max_period, "proxy": proxy}


def _conflicts(run: Run) -> np.ndarray:
    """Steps per second in which two lines drive the same joint in opposite directions (both above 0.05)."""
    u = run["line_u"]
    pos = (u > 0.05).sum(axis=2)
    neg = (u < -0.05).sum(axis=2)
    return ((pos > 0) & (neg > 0)).sum(axis=(1, 2)) / max(run.arrays["com"].shape[1] * run.dt, 1e-9)


def _line_mean(run: Run, lid: str) -> np.ndarray:
    return run["line_active"][:, :, run.line_ids.index(lid)].mean(axis=1) if lid in run.line_ids else np.zeros(run["com"].shape[0])


def _breath_amp(run: Run) -> np.ndarray:
    if "breath.cycle" not in run.line_ids:
        return np.zeros(run["com"].shape[0])
    j = run.line_ids.index("breath.cycle")
    return np.ptp(run["line_u"][:, :, j, min(2, run["theta"].shape[2] - 1)], axis=1)


def catalog() -> list[dict[str, Any]]:
    """The differences an experiment can ask about. ``reference`` computes the true quantity from the model reference record;
    ``alternatives`` are the ways an observation configuration could carry it (``proxy`` = indirect, possibly confounded)."""
    return [
        {"id": "posture_sway", "label": "trunk sway in quiet standing", "family": "kinematic", "timescale_s": 0.5,
         "reference": lambda r, m, p: m["sway_rms"],
         "alternatives": [_alt("posture_sway_rms", "posture", ["trunk"], 1, 0.15), _alt("sway_rms_imu", "imu", ["trunk"], 1, 0.15)]},
        {"id": "com_excursion", "label": "peak centre-of-mass deviation after a push", "family": "kinematic", "timescale_s": 0.3,
         "reference": lambda r, m, p: m["peak_dev"],
         "alternatives": [_alt("peak_dev_obs", "posture", ALL_BODY, 3, 0.1),
                          _alt("imu_rate_peak", "imu", ["trunk"], 2, 0.1, True), _alt("cop_range_obs", "contact", ["ground"], 3, 0.1, True)]},
        {"id": "cop_activity", "label": "centre-of-pressure activity", "family": "contact", "timescale_s": 0.3,
         "reference": lambda r, m, p: m["cop_rms"], "alternatives": [_alt("cop_rms_obs", "contact", ["ground"], 3, 0.1)]},
        {"id": "correction_latency", "label": "movement-correction latency after a push", "family": "muscular", "timescale_s": 0.04,
         "reference": lambda r, m, p: p["correction"]["values"],
         "alternatives": [_alt("emg_onset_push", "emg", ["shank"], 3, 0.02), _alt("cop_onset_push", "contact", ["ground"], 3, 0.02),
                          _alt("imu_onset_push", "imu", ["trunk"], 2, 0.02, True), _alt("com_onset_push", "posture", ALL_BODY, 3, 0.02, True)]},
        {"id": "central_latency", "label": "central command latency after a cue", "family": "neural", "timescale_s": 0.04,
         "reference": lambda r, m, p: p["neural_response"]["values"],
         "alternatives": [_alt("neural_onset_cue", "eeg", ["neural"], 1, 0.03), _alt("emg_onset_cue", "emg", ["shank"], 3, 0.03, True)]},
        {"id": "cocontraction", "label": "antagonist co-contraction", "family": "muscular", "timescale_s": 0.5,
         "reference": lambda r, m, p: m["cc_mean"],
         "alternatives": [_alt("emg_cc", "emg", ["shank", "thigh", "trunk"], 4, 0.1), _alt("emg_mean", "emg", [], 1, 0.2, True)]},
        {"id": "muscle_activation", "label": "mean muscle activation (effort)", "family": "muscular", "timescale_s": 1.0,
         "reference": lambda r, m, p: m["act_mean"], "alternatives": [_alt("emg_mean", "emg", [], 1, 0.2)]},
        {"id": "settling_turn", "label": "settling after a direction change", "family": "kinematic", "timescale_s": 0.5,
         "reference": lambda r, m, p: m["settle_turn_rmst"], "alternatives": [_alt("turn_error_obs", "posture", ALL_BODY, 3, 0.1)]},
        {"id": "stability_loss", "label": "loss of balance (falls)", "family": "kinematic", "timescale_s": 1.0,
         "reference": lambda r, m, p: m["fall"], "alternatives": [_alt("posture_peak_lean", "posture", ["trunk"], 2, 0.2)]},
        {"id": "energy_use", "label": "energy used (internal resource)", "family": "internal", "timescale_s": 8.0,
         "reference": lambda r, m, p: m["energy_used"],
         "alternatives": [_alt("breath_amp_obs", "respiration", ["internal"], 1, 0.3, True), _alt("emg_mean", "emg", [], 1, 0.2, True)]},
        {"id": "fatigue_state", "label": "fatigue (internal state)", "family": "internal", "timescale_s": 8.0,
         "reference": lambda r, m, p: m["fatigue_end"], "alternatives": [_alt("emg_drift", "emg", [], 1, 0.5, True)]},
        {"id": "adaptation_gain", "label": "adapted control gain (retained state)", "family": "internal", "timescale_s": 8.0,
         "reference": lambda r, m, p: m["kc_end"], "alternatives": [_alt("posture_sway_rms", "posture", ["trunk"], 1, 0.15, True)]},
        {"id": "breath_amplitude", "label": "breathing-related drive", "family": "respiratory", "timescale_s": 4.0,
         "reference": lambda r, m, p: _breath_amp(r), "alternatives": [_alt("breath_amp_obs", "respiration", ["trunk", "internal"], 1, 0.3)]},
        {"id": "line_conflicts", "label": "conflicts between operation lines (model-internal events)", "family": "latent", "timescale_s": 0.1,
         "reference": lambda r, m, p: _conflicts(r), "alternatives": []},
        {"id": "visual_use", "label": "use of visual feedback (line activity)", "family": "latent", "timescale_s": 1.0,
         "reference": lambda r, m, p: _line_mean(r, "sens.visual"), "alternatives": []},
    ]


# ------------------------------------------------------------------------------------------------ capability

def _model_state(req: dict[str, Any], m: dict[str, Any], cfg: dict[str, Any], events: dict[str, Any]) -> str:
    n = len(cfg["links"])
    regions = [ln["region"] for ln in cfg["links"]]
    reach = observation.model_regions(m, n, regions)
    if any(r not in reach for r in req["regions"]):
        return "region"
    scale = SCALE.get(m["kind"], {}).get(m["spatial"], 1)
    if scale < req["min_scale"]:
        return "scale"
    if 1.0 / float(m["sample_hz"]) > req["max_period_s"] + 1e-9:
        return "time"
    for a, b in m.get("blind_windows", []):
        for t in (events["cue"], events["turn"], *events["pushes"]):
            if a <= t + 0.5 and b >= t:
                return "blind"
    return "ok"


RANK = {"ok": 0, "time": 1, "scale": 2, "region": 3, "blind": 3, "absent": 4}


def requirement_state(req: dict[str, Any], obs: dict[str, Any], cfg: dict[str, Any], events: dict[str, Any]) -> str:
    models = [m for m in obs["models"] if m["kind"] == req["kind"]]
    if not models:
        return "absent"
    return min((_model_state(req, m, cfg, events) for m in models), key=lambda s: RANK[s])


def capability(diff: dict[str, Any], obs: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Which alternatives are usable, and, if none is, the reason."""
    events = metrics.events(cfg)
    states = [(a, requirement_state(a, obs, cfg, events)) for a in diff["alternatives"]]
    usable = [a for a, s in states if s == "ok"]
    if usable:
        return {"capable": True, "usable": usable, "reason": None, "states": [(a["feature"], a["kind"], s) for a, s in states]}
    if not diff["alternatives"]:
        reason = "measurement-impossible"
    else:
        direct = [(a, s) for a, s in states if not a["proxy"]] or states
        best = min(direct, key=lambda x: RANK[x[1]])[1]
        if best == "absent":
            # nothing of the needed kind is deployed: "device-mismatch" if a model of ANOTHER kind already reaches the region
            # (the right place, the wrong instrument), otherwise "unmeasured"
            n = len(cfg["links"])
            names = [ln["region"] for ln in cfg["links"]]
            want = set(direct[0][0]["regions"]) or {*names, "ground"}
            reached = set()
            for m in obs["models"]:
                if m["kind"] not in ("latency", "threshold"):
                    reached |= observation.model_regions(m, n, names)
            reason = "device-mismatch" if reached & want else "unmeasured"
        else:
            reason = {"time": "time-window-mismatch", "scale": "scale-mismatch", "region": "boundary-invisible",
                      "blind": "boundary-invisible"}[best]
    return {"capable": False, "usable": [], "reason": reason, "states": [(a["feature"], a["kind"], s) for a, s in states]}


# ------------------------------------------------------------------------------------------------ assessment

def reference_effects(run_a: Run, run_b: Run) -> dict[str, dict[str, Any]]:
    ma, mb = metrics.summary(run_a), metrics.summary(run_b)
    pa, pb = velocity.profile(run_a), velocity.profile(run_b)
    out = {}
    for d in catalog():
        a, b = d["reference"](run_a, ma, pa), d["reference"](run_b, mb, pb)
        out[d["id"]] = stats.paired_effect(a, b)
    return out


def assess(run_a: Run, run_b: Run, obs: dict[str, Any], ref: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The identifiability table of two paired conditions under one observation configuration."""
    cfg = run_a.cfg
    ref = ref or reference_effects(run_a, run_b)
    oa, ob = observation.observe(run_a, obs), observation.observe(run_b, obs)
    fa, fb = observation.features(run_a, oa, obs), observation.features(run_b, ob, obs)
    rows = []
    for d in catalog():
        r = ref[d["id"]]
        exists = bool(np.isfinite(r["p"]) and r["p"] < EXIST_P and abs(r["d"]) >= EXIST_D)
        cap = capability(d, obs, cfg)
        row: dict[str, Any] = {"id": d["id"], "label": d["label"], "family": d["family"],
                               "reference": {"exists": exists, "d": _f(r["d"]), "p": _f(r["p"]), "mean_a": _f(r["mean_a"]),
                                             "mean_b": _f(r["mean_b"]), "n": r["n"], "ci": [_f(x) for x in r["ci"]]},
                               "capable": cap["capable"], "states": cap["states"], "identified_by": None, "observed": None}
        best = None
        if cap["capable"]:
            for a in cap["usable"]:
                if a["feature"] in fa and a["feature"] in fb:
                    e = stats.paired_effect(fa[a["feature"]], fb[a["feature"]])
                    if np.isfinite(e["p"]) and (best is None or e["p"] < best[1]["p"]):
                        best = (a, e)
            if best is not None:
                row["observed"] = {"feature": best[0]["feature"], "kind": best[0]["kind"], "proxy": best[0]["proxy"], "d": _f(best[1]["d"]),
                                   "p": _f(best[1]["p"]), "n": best[1]["n"]}
        if not exists:
            row["status"], row["reason"] = "no-difference-in-model", None
        elif best is not None and best[1]["p"] < IDENT_P and abs(best[1]["d"]) >= IDENT_D and (np.sign(best[1]["d"]) == np.sign(r["d"]) or not np.isfinite(r["d"])):
            row["status"] = "identified-by-proxy" if best[0]["proxy"] else "identified"
            row["reason"] = None
            row["identified_by"] = best[0]["feature"]
        elif cap["capable"]:
            row["status"], row["reason"] = "noise-limited", None
        else:
            row["status"], row["reason"] = "unobserved", cap["reason"]
        rows.append(row)
    return rows


def _f(x: float) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for r in rows:
        key = r["status"] if r["status"] != "unobserved" else f"unobserved:{r['reason']}"
        counts[key] = counts.get(key, 0) + 1
    existing = [r for r in rows if r["reference"]["exists"]]
    ident = [r for r in existing if r["status"].startswith("identified")]
    return {"counts": counts, "existing": len(existing), "identified": len(ident),
            "identifiability": (len(ident) / len(existing)) if existing else None}


# ------------------------------------------------------------------------------------------------ operations

def boundary_transformation(obs: dict[str, Any], changes: list[dict[str, Any]], reason: str = "", info: dict[str, Any] | None = None,
                            expected: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply a list of changes to an observation configuration: add / remove a model, change a model's setting (scale, time
    resolution, placement, noise, delay, blind windows), set the observation window. Returns the new configuration and a record of
    the transformation (what changed, why, which information was used, what was expected); the actual result is added by the caller."""
    new = copy.deepcopy(obs)
    for ch in changes:
        op = ch["op"]
        if op == "add":
            new["models"].append(observation.model(ch["kind"], ch.get("id"), **ch.get("settings", {})))
        elif op == "remove":
            new["models"] = [m for m in new["models"] if m["id"] != ch["model"]]
        elif op == "set":
            for m in new["models"]:
                if m["id"] == ch["model"]:
                    m[ch["field"]] = ch["value"]
        elif op == "window":
            new["window"] = ch["window"]
        else:
            raise observation.ObservationError(f"unknown boundary change {op!r}")
    new = observation.validate(new)
    return {"observation": new, "record": {"changes": changes, "reason": reason, "information_used": info or {}, "expected": expected or {},
                                            "actual": None}}


def induced_change(cfg: dict[str, Any], obs: dict[str, Any], seeds: list[int], simulate: Any) -> dict[str, Any]:
    """Run the same body with and without the observation apparatus fitted; the reference difference is the change the
    observation itself induces. ``simulate(cfg, seeds)`` is the engine's batch run (passed in to keep this module free of a loop)."""
    a = simulate(cfg, seeds)
    b = simulate(observation.apply_apparatus(cfg, obs), seeds)
    ma, mb = metrics.summary(a), metrics.summary(b)
    rows = []
    for key, label in (("sway_rms", "trunk sway"), ("track_rms", "tracking error"), ("energy_used", "energy used"), ("cc_mean", "co-contraction"),
                       ("peak_dev", "push deviation"), ("fall", "falls")):
        e = stats.paired_effect(ma[key], mb[key])
        rows.append({"id": key, "label": label, "d": _f(e["d"]), "p": _f(e["p"]), "mean_without": _f(e["mean_a"]), "mean_with": _f(e["mean_b"]),
                     "changed": bool(np.isfinite(e["p"]) and e["p"] < EXIST_P and abs(e["d"]) >= EXIST_D)})
    return {"effects": observation.apparatus_effects(obs), "rows": rows, "note": "assumed apparatus effects (mass, burden, feedback); "
            "not measured properties of any real device"}


def _new_model_for(alt: dict[str, Any]) -> dict[str, Any]:
    kind = alt["kind"]
    settings: dict[str, Any] = {}
    if kind == "posture":
        settings = {"spatial": "joint"}
    elif kind == "emg":
        settings = {"spatial": "joint-pair" if alt["min_scale"] >= 4 else "joint"}
    elif kind == "contact":
        settings = {"spatial": "detailed"}
    elif kind == "imu":
        settings = {"segments": [2]}
    if 1.0 / 100.0 > alt["max_period_s"]:
        settings["sample_hz"] = min(1000.0, 2.0 / alt["max_period_s"])
    return {"op": "add", "kind": kind, "id": f"{kind}-added", "settings": settings}


def candidates(rows: list[dict[str, Any]], obs: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Candidate observation changes for the unobserved differences that exist in the model reference, each with its reason, the
    information used and the expected identifiability (a heuristic: |reference effect| attenuated by the kind's typical noise)."""
    out: list[dict[str, Any]] = []
    cat = {d["id"]: d for d in catalog()}
    for r in rows:
        if r["status"] not in ("unobserved", "noise-limited") or not r["reference"]["exists"]:
            continue
        d = cat[r["id"]]
        base = {"difference": r["id"], "category": r["reason"] or "noise-limited", "reference_d": r["reference"]["d"]}
        if r["status"] == "noise-limited":
            fb = next((a for a in d["alternatives"] if any(m["kind"] == a["kind"] for m in obs["models"])), None)
            if fb is None:
                continue
            mdl = next(m for m in obs["models"] if m["kind"] == fb["kind"])
            if float(mdl["noise"]) <= 0.1:
                continue
            mid, new_noise = mdl["id"], round(float(mdl["noise"]) * 0.5, 4)
            out.append({**base, "changes": [{"op": "set", "model": mid, "field": "noise", "value": new_noise}],
                        "why": f"capable but below the noise: halve {mid}'s noise ({mdl['noise']:g} -> {new_noise:g} of nominal; a better instrument, not a new one)",
                        "expected_identifiability": min(1.0, abs(r["reference"]["d"] or 0) * ATTENUATION[fb["kind"]] * 1.4 / 1.2)})
            continue
        reason = r["reason"]
        if reason == "measurement-impossible":
            out.append({**base, "changes": [], "why": "no observation signal in the inventory can carry this quantity; "
                        "it exists only as model-internal state, so no change of configuration is proposed",
                        "expected_identifiability": 0.0})
            continue
        direct = [a for a in d["alternatives"] if not a["proxy"]] or d["alternatives"]
        if reason in ("unmeasured", "device-mismatch"):
            alt = direct[0]
            ch = [_new_model_for(alt)]
            why = f"deploy a {alt['kind']} model ({'a different aspect is observed now' if reason == 'device-mismatch' else 'none of this kind is deployed'})"
        elif reason == "scale-mismatch":
            alt = min((a for a in d["alternatives"] if any(m["kind"] == a["kind"] for m in obs["models"])), key=lambda a: a["proxy"], default=direct[0])
            m = next(m for m in obs["models"] if m["kind"] == alt["kind"])
            target = next((k for k, v in SCALE[alt["kind"]].items() if v >= alt["min_scale"]), None)
            ch = [{"op": "set", "model": m["id"], "field": "spatial", "value": target}] if target else []
            why = f"raise the spatial resolution of {m['id']} to '{target}' (the quantity needs at least that)"
        elif reason == "time-window-mismatch":
            alt = min((a for a in d["alternatives"] if any(m["kind"] == a["kind"] for m in obs["models"])), key=lambda a: a["proxy"], default=direct[0])
            m = next(m for m in obs["models"] if m["kind"] == alt["kind"])
            ch = [{"op": "set", "model": m["id"], "field": "sample_hz", "value": float(min(1000.0, max(2.0 / alt["max_period_s"], m["sample_hz"] * 2)))}]
            why = f"sample {m['id']} at least every {alt['max_period_s'] / 2:.3f} s (the quantity lasts about {d['timescale_s']} s)"
        else:  # boundary-invisible
            alt = min((a for a in d["alternatives"] if any(m["kind"] == a["kind"] for m in obs["models"])), key=lambda a: a["proxy"], default=direct[0])
            m = next((m for m in obs["models"] if m["kind"] == alt["kind"]), None)
            if m is None:
                ch = [_new_model_for(alt)]
                why = f"place a {alt['kind']} model (none reaches the region)"
            else:
                ch = [{"op": "set", "model": m["id"], "field": "blind_windows", "value": []}, {"op": "set", "model": m["id"], "field": "blind_regions", "value": []}]
                if alt["kind"] in ("posture", "emg"):
                    ch.append({"op": "set", "model": m["id"], "field": "joints", "value": "all"})
                if alt["kind"] == "imu":
                    ch.append({"op": "set", "model": m["id"], "field": "segments", "value": list(range(len(cfg["links"])))})
                why = f"extend {m['id']} to cover the region and remove its blind windows / regions"
        atten = ATTENUATION[alt["kind"]] * (0.8 if alt["proxy"] else 1.0)
        out.append({**base, "changes": ch, "why": why, "expected_identifiability": min(1.0, abs(r["reference"]["d"] or 0) * atten / 1.2),
                    "uses_proxy": alt["proxy"], "feature": alt["feature"]})
    return out
