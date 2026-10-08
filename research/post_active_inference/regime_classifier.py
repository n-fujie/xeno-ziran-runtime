"""Empirical regime classifier. Labels come only from measured stability scores; nothing is assigned by
perturbation name or family.

For one perturbation cell (subtype × severity) and one seed, five continuous stability scores in [0, 1] compare the
perturbation phase with the same phase of the paired unperturbed runs. The paired runs are the control (same seed,
severity 0) and the noise replicate (engine seed + 1000, severity 0); "ref" is their mean.

    S_sensor    sensor-map stability    |corr(aggregate reading, true level of T)|, cell / ref
    S_model     model validity          one-step predictive accuracy of the fixed generative model, cell / ref
    S_variable  latent-variable adequacy min( PC1 share of T's quarter activities, cell / ref ;
                                              (1 − |corr(T, N)|), cell / ref )
                                         (T stops being one variable when it splits; stops being separable from
                                         its neighbour when it merges)
    S_boundary  boundary stability      share of the damp+excite response mass that lands inside T, cell / ref
                                         (exact forked probes at three points of the perturbation phase, averaged)
    S_policy    policy-identity stability mean over the three probes of corr(action→effect vector, cell vs control)
                                         / the same for the noise replicate vs control

Noise tolerance (revised after the smoke stage, before the development run): a drop counts only beyond the largest
|control − noise replicate| difference of that raw quantity over seeds (``tolerance``); the same convention as
``xzr.experiments.history.assess``. Similarity scores (boundary, policy) are already normalised by the noise
replicate. The primary label is per cell (``cell_label``: scores averaged over seeds, then the minimum); per-seed
labels are kept.

Scores are clipped to [0, 1]. A score is None when its reference is too weak to normalise by: reference correlation,
accuracy or Jaccard < 0.2, or PC1 share < 0.05.

    C_AIF = min(available scores)        (one unstable primitive is enough to stop presupposing it)

Decision rule (documented, fixed before the development run):

    C_AIF ≥ 0.8           → ACTIVE_INFERENCE_COMPATIBLE
    0.5 ≤ C_AIF < 0.8     → TRANSITION
    C_AIF < 0.5           → POST_ACTIVE_INFERENCE

The rule is about Active-Inference primitives only. Whether operational tracking survives is measured separately
(``tracking_preserved``) and never feeds the label. Otherwise "post-AIF" would be defined as "where the tracker
wins". Sensitivity to the thresholds is reported for (0.7, 0.4) and (0.9, 0.6). ``null_scores`` classifies the
noise replicate against the control, using only the scores defined for a single pair (sensor, model, variable),
to estimate how often an unperturbed run is mislabelled.
"""
from __future__ import annotations

import numpy as np

HI, LO = 0.8, 0.5
SENSITIVITY = ((0.7, 0.4), (0.9, 0.6))
LABELS = ("ACTIVE_INFERENCE_COMPATIBLE", "TRANSITION", "POST_ACTIVE_INFERENCE")
SCORES = ("S_sensor", "S_model", "S_variable", "S_boundary", "S_policy")
MIN_REF = 0.2


def _get(rec: dict | None, key: str):
    if rec is None or rec.get("status") != "ok":
        return None
    v = rec["metrics"].get(key)
    return None if v is None or not np.isfinite(v) else float(v)


def _ratio(v, ref, floor=MIN_REF, tol=0.0):
    """1 − max(0, ref − v − tol) / ref, clipped to [0, 1]: a drop counts only beyond the noise tolerance."""
    if v is None or ref is None or ref < floor:
        return None
    return float(np.clip((v + tol) / ref, 0.0, 1.0))


RAW = ("acc", "acc_adaptive", "sensor", "pc1", "sep", "bshare")
PHASE_PROBES = ("p1", "mid", "p3")


def raw(runs: dict) -> dict:
    """The raw quantities behind the single-run scores (perturbation phase)."""
    f, a = runs.get("aif_fixed"), runs.get("aif_adaptive")
    sc, tn = _get(f, "sensor_corr_pert"), _get(f, "T_N_corr_pert")
    n = runs.get("none")
    bs = [p.get("response_share_T") for p in (_probe(n, k) for k in PHASE_PROBES) if p and p.get("response_share_T") is not None]
    return {"acc": _get(f, "one_step_acc_pert"), "acc_adaptive": _get(a, "one_step_acc_pert"),
            "sensor": None if sc is None else abs(sc), "pc1": _get(f, "pc1_share_pert"),
            "sep": None if tn is None else 1 - abs(tn), "bshare": float(np.mean(bs)) if bs else None}


def tolerance(controls: dict, exclude=None) -> dict:
    """Noise tolerance per raw quantity: the largest |control − noise replicate| over seeds (the repository's
    convention: an effect must exceed the largest noise difference). ``exclude`` leaves one seed out (for the
    out-of-sample null check)."""
    out = {}
    for q in RAW:
        d = []
        for seed, v in controls.items():
            if seed == exclude:
                continue
            x, y = raw(v["control"]).get(q), raw(v["noise"]).get(q)
            if x is not None and y is not None:
                d.append(abs(x - y))
        out[q] = float(max(d)) if d else 0.0
    return out


def _ref(*vals):
    v = [x for x in vals if x is not None]
    return float(np.mean(v)) if v else None


def _jac(a, b):
    a, b = set(a or []), set(b or [])
    return len(a & b) / len(a | b) if (a | b) else None


def _pcorr(a, b):
    if a is None or b is None:
        return None
    a, b = np.asarray(a, float), np.asarray(b, float)
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _probe(rec, at="mid"):
    if rec is None or rec.get("status") != "ok":
        return None
    return rec.get("probes", {}).get(at)


def label(c: float | None, hi: float = HI, lo: float = LO) -> str | None:
    if c is None:
        return None
    return LABELS[0] if c >= hi else (LABELS[2] if c < lo else LABELS[1])


def scores(cell: dict, control: dict, noise: dict, tol: dict | None = None) -> dict:
    """cell / control / noise: {controller: run record} for one seed; tol: noise tolerance per raw quantity."""
    tol = tol or {}
    rc, r0, rn = raw(cell), raw(control), raw(noise)
    ref = {q: _ref(r0[q], rn[q]) for q in RAW}
    out: dict = {}
    out["S_sensor"] = _ratio(rc["sensor"], ref["sensor"], tol=tol.get("sensor", 0.0))
    out["S_model"] = _ratio(rc["acc"], ref["acc"], tol=tol.get("acc", 0.0))
    pc = _ratio(rc["pc1"], ref["pc1"], 0.05, tol=tol.get("pc1", 0.0))
    sep = _ratio(rc["sep"], ref["sep"], tol=tol.get("sep", 0.0))
    out["S_variable"] = min([x for x in (pc, sep) if x is not None], default=None)
    out["S_variable_parts"] = {"coherence": pc, "separability": sep}
    out["S_boundary"] = _ratio(rc["bshare"], ref["bshare"], tol=tol.get("bshare", 0.0))
    rn_, rz_ = [], []
    for k in PHASE_PROBES:
        pn, pc_, pz = _probe(cell.get("none"), k), _probe(control.get("none"), k), _probe(noise.get("none"), k)
        if pn and pc_ and pz:
            r1, r2 = _pcorr(pn["effect"], pc_["effect"]), _pcorr(pz["effect"], pc_["effect"])
            if r1 is not None and r2 is not None:
                rn_.append(max(r1, 0.0))
                rz_.append(r2)
    out["S_policy"] = _ratio(float(np.mean(rn_)), float(np.mean(rz_))) if rn_ else None
    avail = {k: out[k] for k in SCORES if out.get(k) is not None}
    out["C_AIF"] = min(avail.values()) if avail else None
    out["first_unstable"] = min(avail, key=avail.get) if avail and out["C_AIF"] < HI else None
    out["label"] = label(out["C_AIF"])
    out["label_sensitivity"] = {f"{h}/{lo}": label(out["C_AIF"], h, lo) for h, lo in SENSITIVITY}
    # structure-learning overlap: the fixed model fails, the adaptive model keeps predicting
    out["S_model_adaptive"] = _ratio(rc["acc_adaptive"], ref["acc_adaptive"], tol=tol.get("acc_adaptive", 0.0))
    out["overlap_structure_learning"] = bool(out["S_model"] is not None and out["S_model"] < LO
                                             and out["S_model_adaptive"] is not None and out["S_model_adaptive"] >= HI)
    out.update(tracking(cell))
    return out


def tracking(cell: dict) -> dict:
    """Is operational tracking preserved? From the uncontrolled run's tracker, against the ground truth of what changed.

    world-side perturbations        the tracker detects the onset (z > 4 within 100 steps)
    observation-side perturbations  the tracker reports no world change (correct: the world is untouched)
    interface-side perturbations    n/a (the world changes only through actions; no uncontrolled ground truth)
    The comparator's surprise-based detection, and the sensor-only tracker, are scored by the same rule."""
    n, f = cell.get("none"), cell.get("aif_fixed")
    if n is None or n.get("status") != "ok":
        return {"tracking_preserved": None}
    side = n.get("side")
    hit = n["tracker"]["detect_onset"]["hit"]
    so = n["tracker_sensor_only"]["detect_onset"]["hit"]
    sur = (f or {}).get("metrics", {}).get("surprise_detect_onset", {}).get("hit") if f and f.get("status") == "ok" else None
    if side == "world":
        ok = hit
        ok_so = so
        ok_sur = sur
    elif side == "observation":
        ok = not hit
        ok_so = None  # the sensor-only tracker cannot tell an observation change from a world change
        ok_sur = None
    else:
        ok = ok_so = ok_sur = None
    return {"tracking_preserved": ok, "tracking_sensor_only": ok_so, "comparator_detection": ok_sur,
            "tracker_detect": hit, "sensor_only_detect": so, "surprise_detect": sur,
            "localisation_auc": n["tracker"].get("localisation_auc"),
            "channel_localisation_auc": (f or {}).get("metrics", {}).get("channel_localisation_auc") if f else None}


def null_scores(control: dict, noise: dict, tol: dict | None = None) -> dict:
    """Noise replicate classified against the control (single-pair scores only). ``tol`` must exclude this seed
    (leave-one-seed-out), so that the null check is out-of-sample."""
    tol = tol or {}
    r0, rn = raw(control), raw(noise)
    s = {"S_sensor": _ratio(rn["sensor"], r0["sensor"], tol=tol.get("sensor", 0.0)),
         "S_model": _ratio(rn["acc"], r0["acc"], tol=tol.get("acc", 0.0))}
    parts = [x for x in (_ratio(rn["pc1"], r0["pc1"], 0.05, tol=tol.get("pc1", 0.0)),
                         _ratio(rn["sep"], r0["sep"], tol=tol.get("sep", 0.0))) if x is not None]
    s["S_variable"] = min(parts) if parts else None
    avail = [v for v in s.values() if v is not None]
    s["C_AIF"] = min(avail) if avail else None
    s["label"] = label(s["C_AIF"])
    return s


def cell_label(rows: list[dict]) -> dict:
    """Primary (cell-level) classification: each score averaged over seeds, then C_AIF = min of the means."""
    means = {}
    for k in SCORES:
        v = [r[k] for r in rows if r.get(k) is not None]
        if v:
            means[k] = float(np.mean(v))
    c = min(means.values()) if means else None
    return {"scores": means, "C_AIF": c, "label": label(c), "first_unstable": min(means, key=means.get) if means and c < HI else None,
            "n_seeds": len(rows), "seed_labels": {lab: sum(r["label"] == lab for r in rows) for lab in LABELS}}
