"""Per-run metrics (one controller in one perturbed world). Cell-level metrics that need the paired control and
noise replicate (stability scores, collateral change, staleness) live in ``regime_classifier.py`` and
``pai/analysis.py``.

Phases: pre = [calib_end, t_p), pert = [t_p, t_r), rec = [t_r, horizon). A decision at step t reads the interval
before t, so it is assigned to the phase that contains t.

Predictive     one_step_acc (predicted observation level = realised level), multi_step_acc (k = 3), pred_mae
               (reading units), log_loss and calibration_gap (comparator only), inferred_state_acc (comparator only),
               support_coverage (realised level has predicted probability ≥ 0.05: reachable-state estimation)
Intervention   success (true level of T = goal level of the setpoint schedule), abs_error (|true − goal centre| /
               20–80 % range of calibration),
               time_to_effect (decisions from leaving the preferred level to re-entering it), reach_rate (share of
               5-decision blocks in which the preferred level was reached)
Recovery       adaptation_time (after t_p) and recovery_time (after t_r): decisions until the rolling-5 success
               returns to pre − 0.1 (None = not within the phase; censored), recovered (bool), rec_level_sd
Structural     model_validity_duration (decisions after t_p until rolling-5 one-step accuracy < half of pre),
               rebuilds, invalidations, failed_inference, numerical, missing_observations, policy_switch_rate,
               policy_entropy
Speed          decision_interval (mean dt), env_change_period (drift), adaptation lag (= adaptation_time × dt)
Detection      comparator surprise detection (z > 4 against pre-onset decisions) at t_p and t_r; localisation
               AUC from per-channel prediction error (channels → their configurations)
"""
from __future__ import annotations

import numpy as np

from pai.tracker import Z_DETECT, auc
from pai.world import N_LEVELS, level_of

PHASE_NAMES = ("pre", "pert", "rec")


def _phase(t: int, ph: dict) -> str | None:
    if ph["calib_end"] <= t < ph["t_p"]:
        return "pre"
    if ph["t_p"] <= t < ph["t_r"]:
        return "pert"
    if t >= ph["t_r"]:
        return "rec"
    return None


def _m(x) -> float | None:
    x = [v for v in x if v is not None and np.isfinite(v)]
    return float(np.mean(x)) if x else None


def _rolling_return(ok: list[float], target: float, start: int, w: int = 5) -> int | None:
    for i in range(start, len(ok)):
        lo = max(start, i - w + 1)
        if i - lo + 1 >= min(w, 3) and np.mean(ok[lo:i + 1]) >= target:
            return i - start
    return None


def episode_metrics(rows, ctrl, tr, ph, calib, P, sev, ctx) -> dict:
    ctl = [r for r in rows if r["s"] is not None]
    t = np.array([r["t"] for r in ctl])
    phase = [_phase(int(x), ph) for x in t]
    true_edges = np.asarray(calib["true_edges"])
    iqr = float(true_edges[-1] - true_edges[0]) or 1e-9  # 20–80 % inter-quantile range of calibration
    succ = [1.0 if r["s"] == r["goal"] else 0.0 for r in ctl]
    err = [abs(r["true"] - calib["true_centres"][r["goal"]]) / iqr for r in ctl]
    out: dict = {}
    hist = {h["t"]: h for h in getattr(ctrl, "hist", [])}
    obs_edges = getattr(ctrl, "obs_edges", None)
    for name in PHASE_NAMES:
        idx = [i for i, p in enumerate(phase) if p == name]
        out[f"success_{name}"] = _m([succ[i] for i in idx])
        out[f"abs_error_{name}"] = _m([err[i] for i in idx])
        out[f"level_sd_{name}"] = float(np.std([ctl[i]["true"] for i in idx])) if idx else None
        out[f"sensor_corr_{name}"] = _sensor_corr([ctl[i]["agg"] for i in idx], [ctl[i]["true"] for i in idx])
        out[f"halves_corr_{name}"] = _corr([ctl[i]["halves"][0] for i in idx], [ctl[i]["halves"][1] for i in idx])
        out[f"T_N_corr_{name}"] = _corr([ctl[i]["true"] for i in idx], [ctl[i]["N"] for i in idx])
        out[f"pc1_share_{name}"] = _pc1([ctl[i]["quarters"] for i in idx])
        out[f"N_activity_{name}"] = _m([ctl[i]["N"] for i in idx])
        blocks = [idx[j:j + 5] for j in range(0, len(idx), 5)]
        out[f"reach_rate_{name}"] = _m([1.0 if any(succ[i] for i in b) else 0.0 for b in blocks if b])
        out[f"time_to_effect_{name}"] = _tte([succ[i] for i in idx])
        out[f"dt_{name}"] = _m([ctl[i]["dt"] for i in idx])
        # prediction (both controllers expose a predicted reading; the comparator also a distribution)
        acc, mae, ll, conf, inf, cov = [], [], [], [], [], []
        for i in idx:
            h = hist.get(ctl[i]["t"])
            if h is None or obs_edges is None:
                continue
            o = level_of(ctl[i]["agg"], obs_edges) if "o" not in h else h["o"]
            if "pred_o" in h:  # comparator
                po = np.asarray(h["pred_o"])
                if o is not None:
                    acc.append(float(np.argmax(po) == o))
                    ll.append(float(-np.log(po[o] + 1e-12)))
                    conf.append(float(po.max()))
                    cov.append(float(po[o] >= 0.05))
                mae.append(abs(h["pred_reading"] - ctl[i]["agg"]) if np.isfinite(ctl[i]["agg"]) else None)
                if ctl[i]["s"] is not None and "q_argmax" in h:
                    inf.append(float(h["q_argmax"] == ctl[i]["s"]))
            elif h.get("pred_prev") is not None and np.isfinite(ctl[i]["agg"]):
                acc.append(float(level_of(h["pred_prev"], obs_edges) == o))
                mae.append(abs(h["pred_prev"] - ctl[i]["agg"]))
        out[f"one_step_acc_{name}"] = _m(acc)
        out[f"pred_mae_{name}"] = _m(mae)
        out[f"log_loss_{name}"] = _m(ll)
        out[f"calibration_gap_{name}"] = (_m(conf) - _m(acc)) if conf and acc else None
        out[f"inferred_state_acc_{name}"] = _m(inf)
        out[f"support_coverage_{name}"] = _m(cov)  # reachable-state estimation: realised level inside predicted support
        a = [ctl[i]["a"] for i in idx]
        out[f"policy_switch_rate_{name}"] = _m([float(a[j] != a[j - 1]) for j in range(1, len(a))])
        ent = [hist[ctl[i]["t"]].get("policy_entropy") for i in idx if ctl[i]["t"] in hist]
        out[f"policy_entropy_{name}"] = _m(ent)
        out[f"F_{name}"] = _m([hist[ctl[i]["t"]].get("F") for i in idx if ctl[i]["t"] in hist])
        out[f"G_{name}"] = _m([hist[ctl[i]["t"]].get("G") for i in idx if ctl[i]["t"] in hist])
        out[f"surprise_{name}"] = _m([hist[ctl[i]["t"]].get("surprise") for i in idx if ctl[i]["t"] in hist])
    # multi-step prediction (comparator: from beliefs; model-light: reading + measured effects)
    out.update(_multi_step(ctrl, ctl, phase, obs_edges))
    # recovery
    i_p = next((i for i, p in enumerate(phase) if p == "pert"), None)
    i_r = next((i for i, p in enumerate(phase) if p == "rec"), None)
    pre_s = out["success_pre"] or 0.0
    if i_p is not None:
        out["adaptation_time"] = _rolling_return(succ[: i_r if i_r else len(succ)], pre_s - 0.1, i_p)
    if i_r is not None:
        out["recovery_time"] = _rolling_return(succ, pre_s - 0.1, i_r)
        out["recovered"] = out["recovery_time"] is not None
    # model validity (comparator and model-light alike, via one-step accuracy)
    if i_p is not None and out.get("one_step_acc_pre"):
        okv = []
        for i in range(i_p, i_r or len(ctl)):
            h = hist.get(ctl[i]["t"])
            if h and "pred_o" in h and h["o"] is not None:
                okv.append(float(np.argmax(h["pred_o"]) == h["o"]))
            elif h and h.get("pred_prev") is not None and obs_edges is not None and np.isfinite(ctl[i]["agg"]):
                okv.append(float(level_of(h["pred_prev"], obs_edges) == level_of(ctl[i]["agg"], obs_edges)))
        out["model_validity_duration"] = _validity(okv, 0.5 * out["one_step_acc_pre"])
        out["model_validity_censored"] = out["model_validity_duration"] is None
    # comparator structure and failures
    s = ctrl.summary() if hasattr(ctrl, "summary") else {}
    out["rebuilds"] = len(s.get("rebuilds", []))
    out["rebuilds_pert"] = sum(1 for x in s.get("rebuilds", []) if ph["t_p"] <= x < ph["t_r"])
    out["rebuilds_pre"] = sum(1 for x in s.get("rebuilds", []) if x < ph["t_p"])
    for k in ("failed_inference", "numerical", "missing_observations", "invalidations", "comparator_errors"):
        out[k] = s.get(k)
    # comparator change detection from surprise; localisation from per-channel prediction error
    out.update(_surprise_detection(hist, ph))
    out.update(_channel_localisation(hist, ph, ctx, ctrl))
    if P is not None and ctx is not None and "period" in ctx:
        out["env_change_period"] = ctx["period"]
    out["adaptation_lag_steps"] = (out["adaptation_time"] * (out["dt_pert"] or 10)) if out.get("adaptation_time") is not None else None
    return out


def _corr(a, b) -> float | None:
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 4 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return None
    return float(np.corrcoef(a[m], b[m])[0, 1])


def _sensor_corr(agg, true) -> float | None:
    """|corr(reading, true level)|; a reading that is missing (< 4 finite values) or constant carries no information
    about the true level and scores 0 (a dead sensor map), unless the true level itself is constant (None)."""
    a, b = np.asarray(agg, float), np.asarray(true, float)
    if len(a) < 4 or np.std(b) == 0:
        return None
    m = np.isfinite(a)
    if m.sum() < 4 or np.std(a[m]) == 0:
        return 0.0
    return _corr(a, b)


def _pc1(Q) -> float | None:
    """Chance-normalised variance share of the first principal component of T's four quarter activities: 1 = one
    variable summarises T, 0 = the quarters vary independently."""
    Q = np.asarray(Q, float)
    if len(Q) < 5:
        return None
    Q = Q - Q.mean(0)
    sd = Q.std(0)
    if np.any(sd == 0):
        return None
    ev = np.linalg.eigvalsh(np.cov((Q / sd).T))
    share = ev[-1] / ev.sum()
    k = Q.shape[1]
    return float((share - 1 / k) / (1 - 1 / k))


def _tte(ok: list[float]) -> float | None:
    gaps, cur = [], None
    for v in ok:
        if v == 0:
            cur = 1 if cur is None else cur + 1
        elif cur is not None:
            gaps.append(cur)
            cur = None
    return float(np.mean(gaps)) if gaps else None


def _validity(ok: list[float], floor: float, w: int = 5) -> int | None:
    for i in range(w - 1, len(ok)):
        if np.mean(ok[i - w + 1:i + 1]) < floor:
            return i - w + 1
    return None


def _multi_step(ctrl, ctl, phase, obs_edges, k: int = 3) -> dict:
    out = {}
    if obs_edges is None:
        return out
    hist = {h["t"]: h for h in getattr(ctrl, "hist", [])}
    res: dict[str, list[float]] = {p: [] for p in PHASE_NAMES}
    if hasattr(ctrl, "multi_step_predictions"):
        ts = [h["t"] for h in ctrl.hist if "error" not in h]
        for j, po in ctrl.multi_step_predictions(k):
            if j >= len(ts):
                continue
            h = hist[ts[j]]
            p = _phase_of(ts[j], ctl, phase)
            if h["o"] is not None and p:
                res[p].append(float(np.argmax(po) == h["o"]))
    elif hasattr(ctrl, "effect"):
        hs = [h for h in ctrl.hist]
        for i in range(len(hs) - k):
            if hs[i].get("pred_reading") is None or not np.isfinite(hs[i + k]["agg"]):
                continue
            # x_i + measured effects of the k executed actions (effects as at the end of the run; documented)
            pred = hs[i]["agg"] + sum(ctrl.effect[hs[i + j]["a"]] for j in range(k))
            p = _phase_of(hs[i + k]["t"], ctl, phase)
            if p:
                res[p].append(float(level_of(pred, obs_edges) == level_of(hs[i + k]["agg"], obs_edges)))
    for p in PHASE_NAMES:
        out[f"multi_step_acc_{p}"] = _m(res[p])
    return out


def _phase_of(t, ctl, phase):
    for r, p in zip(ctl, phase, strict=True):
        if r["t"] == t:
            return p
    return None


def _surprise_detection(hist: dict, ph: dict) -> dict:
    ts = sorted(t for t, h in hist.items() if h.get("surprise") is not None)
    if len(ts) < 8:
        return {}
    s = np.array([hist[t]["surprise"] for t in ts])
    t = np.array(ts)
    pre = (t >= ph["calib_end"]) & (t < ph["t_p"])
    if pre.sum() < 5:
        return {}
    mu, sd = s[pre].mean(), s[pre].std(ddof=1) + 1e-9
    # 3-decision mean against the standard error of a 3-mean, as for the rebuild trigger
    sm = np.convolve(s, np.ones(3) / 3, mode="full")[: len(s)]
    z = (sm - mu) / (sd / np.sqrt(3))

    def first(lo, hi):
        hit = np.flatnonzero((t > lo) & (t <= hi) & (z > Z_DETECT))
        return {"hit": bool(len(hit)), "delay": int(t[hit[0]] - lo) if len(hit) else None}
    return {"surprise_detect_onset": first(ph["t_p"], ph["t_p"] + 100),
            "surprise_detect_revert": first(ph["t_r"], ph["t_r"] + 100),
            "surprise_false_alarms_pre": int((z[pre] > Z_DETECT).sum())}


def _channel_localisation(hist: dict, ph: dict, ctx, ctrl) -> dict:
    if ctx is None or not ctx.get("footprint") or not hist:
        return {}
    ts = sorted(t for t, h in hist.items() if "channel_pe" in h)
    if not ts:
        return {}
    pe = np.array([hist[t]["channel_pe"] for t in ts], float)
    t = np.array(ts)
    pre = (t >= ph["calib_end"]) & (t < ph["t_p"])
    post = np.flatnonzero((t >= ph["t_p"]) & (t < ph["t_r"]))[:10]
    if pre.sum() < 3 or len(post) == 0:
        return {}
    with np.errstate(invalid="ignore"):
        score_c = np.nan_to_num(np.nanmean(pe[post], 0) - np.nanmean(pe[pre], 0), nan=0.0)
    return {"_channel_score": score_c.tolist()}


def channel_auc(channel_score: list[float], channels: list[np.ndarray], n: int, footprint: list[int]) -> float | None:
    """Node scores from channel scores (each configuration takes the max score of the channels reading it; others 0)."""
    node = np.zeros(n)
    for c, s in zip(channels, channel_score, strict=True):
        node[c] = np.maximum(node[c], s)
    fp = np.zeros(n, bool)
    fp[np.asarray(footprint, int)] = True
    return auc(node, fp) if 0 < fp.sum() < n else None


__all__ = ["episode_metrics", "channel_auc", "N_LEVELS"]
