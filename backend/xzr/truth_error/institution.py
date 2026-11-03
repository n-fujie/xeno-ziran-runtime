"""The virtual institution of TRUTH-ERROR: synthetic subjects, a sensor, a classifier, a warrant, an acceptance rule, a score, a gate, resources, a correction and a second institution.

Every stage is a SEPARATE record, never reduced to one right/wrong variable:

  reference state z (the evaluator's: the subject's actual operating condition)         -> declared verification label y = (z > 0)
  measurement           what a sensor returned about the reference (value, confidence, missing, reason)
  classification        the label a declared rule assigned (+1 favourable, -1 adverse, 0 abstained)
  classification correct  agreement of that label with y, only where one was assigned
  warrant               what the signal evidence supports about "z > 0": SUPPORTED, REFUTED or UNDECIDED (never forced into two values)
  acceptance            whether the institution ADOPTED the classification (an institutional act: independent of correctness)
  score                 an institutional quantity updated from adopted classifications; it is a prediction used to allocate access ahead of time, not a capacity, a virtue or a truth
  gate / access         the decision the score is read into (at the institution's reading times, with a binding constraint that can outlast the score)
  resources, opportunities, the subject's real state   what access changes in the subject (so that a decision alters what is later observed and what is later true)
  correction            a retraction at a chosen time: it restores the score, not the resources or the opportunities that were lost, and it need not release a binding constraint
  transfer              a snapshot of the score sent to a second institution, with its evidential weight, whose gate then applies it with its own force

SYNTHETIC ONLY (see the package docstring): no real person is assessed and none of this is a test of a real institution. The pose channel's classifier (``pose_rule``) is invalid by construction.

Random numbers come from independent streams (population, pose sensor, signal sensor, classifier, dynamics), so that changing the classifier, the threshold, the correction time or the observation conditions
changes only that, and a control arm shares every other draw with its comparison arm."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from math import erf, sqrt

import numpy as np

from .pose import SensorConfig, SensorState, measure_period, reference_pose, tolerance

CLASSIFIERS = ("signal_rule", "pose_rule", "random_rule", "none")
WARRANT = ("SUPPORTED", "REFUTED", "UNDECIDED")  # about the proposition "z > 0"
SAMPLE_SUBJECTS = 12  # subjects whose every stage is kept in the output (the timeline); everything else is a rate


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    seed: int = 1
    n: int = 120
    periods: int = 40
    # observation: a pose channel (independent of z unless ``pose_z_coupling``) and a signal channel (informative about z)
    pose_sensor: SensorConfig = field(default_factory=SensorConfig)
    signal_sensor: SensorConfig = field(default_factory=lambda: SensorConfig(noise_sigma=0.8))
    pose_z_coupling: float = 0.0  # degrees of yaw per unit of z: 0 = the pose carries nothing about z (the usual case)
    # classification
    classifier: str = "signal_rule"
    window: int = 4
    signal_threshold: float = 0.0
    yaw_threshold: float = 15.0
    # warrant and acceptance
    warrant_level: float = 0.9
    confidence_floor: float = 0.3
    requires_warrant: bool = False  # an institution that adopts only what the signal evidence supports
    # score and gate (institution A)
    use_score: bool = True
    rho: float = 0.25
    tau_a: float = 0.0
    read_every_a: int = 1
    baseline_access: float = 0.5  # the share served by lottery when the score is not used
    score_expiry: int | None = None  # the score is extinguished (reset) every this many periods
    # what access changes
    gain: float = 0.12
    loss: float = 0.12
    beta: float = 0.0  # how much resources change the subject's real state z
    gamma: float = 0.0  # how much a denial worsens how the subject is observed (noise and loss of tracking)
    lock_after: int | None = None  # consecutive denied periods after which a binding constraint is set
    release_after: int = 3  # consecutive periods with a score at or above the threshold that release it
    # correction
    correct_at: int | None = None
    correction_scope: str = "wrongful"  # wrongful (adverse adoptions about subjects whose y is favourable) or all_adverse
    correction_score_target: float = 0.6
    correction_clears_lock: bool = False
    reentry_support: float = 0.0  # the share of lost resources returned per period after a correction (0 = none)
    # transfer to institution B
    transfer_at: int | None = None
    transfer_weight: float = 1.0  # the evidential weight B gives the transferred score
    tau_b: float = 0.0
    propagate_correction: bool = False
    propagation_delay: int = 0

    def asdict(self) -> dict:
        return asdict(self)


def _phi(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(erf)(x / sqrt(2.0)))


def _nanmean_window(buf: list[np.ndarray], window: int) -> np.ndarray:
    """The mean over the last ``window`` periods, ignoring missing values; NaN where all were missing."""
    stack = np.stack(buf[-window:], axis=0)
    with np.errstate(all="ignore"):
        cnt = np.sum(~np.isnan(stack), axis=0)
        return np.where(cnt > 0, np.nansum(stack, axis=0) / np.maximum(cnt, 1), np.nan)


def run(cfg: Config) -> dict:
    """Run the virtual institution. Deterministic in the configuration (the seed included). Returns the config, per-period rates, the full records of ``SAMPLE_SUBJECTS`` subjects, a summary and digests."""
    if cfg.classifier not in CLASSIFIERS:
        raise ValueError(f"classifier must be one of {CLASSIFIERS}")
    n, T = cfg.n, cfg.periods
    ss = np.random.SeedSequence(cfg.seed).spawn(6)
    r_pop, r_pose, r_sig, r_cls, r_dyn, r_lot = (np.random.default_rng(s) for s in ss)
    z = r_pop.normal(size=n)  # the subjects' real operating condition (the evaluator's reference)
    z0 = z.copy()
    pose_ref = reference_pose(r_pop, n, T)
    pose_ref[:, :, 0] += cfg.pose_z_coupling * z0[:, None]  # normally 0: the pose says nothing about z
    lottery_u = r_lot.uniform(size=n)  # a fixed draw per subject: the lottery used when the score is not used
    eps_pose, eps_sig = r_pose.normal(size=(T, n, 3)), r_sig.normal(size=(T, n, 1))
    uo_pose, ud_pose = r_pose.uniform(size=(T, n)), r_pose.uniform(size=(T, n))
    uo_sig, ud_sig = r_sig.uniform(size=(T, n)), r_sig.uniform(size=(T, n))
    rand_label = np.where(r_cls.uniform(size=(T, n)) < 0.5, 1, -1)
    eps_z = r_dyn.normal(size=(T, n))
    st_pose, st_sig = SensorState(n, 3), SensorState(n, 1)

    score = np.zeros(n)  # institution A's score
    resources = np.full(n, 0.5)
    access_score = lottery_u < cfg.baseline_access  # before the first reading
    access = access_score.copy()
    denied_run = np.zeros(n, dtype=int)
    ok_run = np.zeros(n, dtype=int)
    locked = np.zeros(n, dtype=bool)
    opp_lost = np.zeros(n)
    opp_gained = np.zeros(n)
    denied_prev = np.zeros(n, dtype=bool)
    snap_b: np.ndarray | None = None
    score_b = np.zeros(n)
    access_b = np.where(lottery_u < cfg.baseline_access, True, False)
    pose_buf: list[np.ndarray] = []
    sig_buf: list[np.ndarray] = []
    conf_buf: list[np.ndarray] = []
    sig_sum = np.zeros(n)
    sig_cnt = np.zeros(n)
    sigma_declared = cfg.signal_sensor.noise_sigma
    rows: dict[str, list] = {
        k: []
        for k in (
            "t",
            "z_mean",
            "meas_correct",
            "cls_correct",
            "abstain",
            "warrant_supported",
            "warrant_refuted",
            "warrant_undecided",
            "accepted",
            "wrongful_adverse",
            "access",
            "access_fav",
            "access_unfav",
            "score_mean",
            "resources_mean",
            "lost_fav_cum",
            "locked",
            "released",
            "b_access",
            "b_force",
            "score_exists",
            "score_read",
            "score_transferred",
            "access_altered",
            "score_extinguished",
            "constraint_extinguished",
            "wrongly_denied_now",
        )
    }
    sample_idx = np.arange(min(SAMPLE_SUBJECTS, n))
    records: list[list[dict]] = [[] for _ in sample_idx]
    z_series = np.zeros((T, n))
    access_hist: list[np.ndarray] = []
    cum_released = 0
    lost_fav = 0.0
    corrected_total = np.zeros(n, dtype=bool)
    extinguished_total = 0

    for t in range(T):
        z_series[t] = z
        y = z > 0  # the declared verification label at this period
        denied_mult = 1.0 + cfg.gamma * denied_prev  # a denied subject is observed worse (TE06)
        # ---- observation
        pose_meas = measure_period(
            pose_ref[:, t, :], cfg.pose_sensor, t, eps_pose[t], uo_pose[t], ud_pose[t], st_pose, denied_mult
        )
        sig_meas = measure_period(z[:, None], cfg.signal_sensor, t, eps_sig[t], uo_sig[t], ud_sig[t], st_sig, denied_mult)
        pose_buf.append(np.abs(pose_meas["values"][:, 0]))
        sig_buf.append(sig_meas["values"][:, 0])
        conf_buf.append(np.where(np.isnan(sig_meas["values"][:, 0]), np.nan, sig_meas["confidence"]))
        # measurement correctness: within tolerance of the reference, among the periods that produced a value
        pose_err = np.abs(pose_meas["values"] - pose_ref[:, t, :])
        pose_ok = np.all(pose_err <= np.array([tolerance(a) for a in range(3)]), axis=1)
        has_pose = ~np.isnan(pose_meas["values"][:, 0])
        meas_correct = float(np.mean(pose_ok[has_pose])) if has_pose.any() else float("nan")
        # ---- warrant about "z > 0" from the signal evidence, with the DECLARED noise (a miscalibrated sensor misleads it)
        v = sig_meas["values"][:, 0]
        got = ~np.isnan(v)
        sig_sum += np.where(got, v, 0.0)
        sig_cnt += got
        prec = 1.0 + sig_cnt / sigma_declared**2
        post_mean = (sig_sum / sigma_declared**2) / prec
        p_pos = _phi(post_mean * np.sqrt(prec))
        warrant = np.where(p_pos >= cfg.warrant_level, 0, np.where(p_pos <= 1.0 - cfg.warrant_level, 1, 2))  # index into WARRANT
        # ---- classification
        cls = np.zeros(n, dtype=int)
        conf_cls = np.zeros(n)
        if cfg.classifier == "signal_rule":
            m = _nanmean_window(sig_buf, cfg.window)
            cls = np.where(np.isnan(m), 0, np.where(m > cfg.signal_threshold, 1, -1))
            conf_cls = np.nan_to_num(_nanmean_window(conf_buf, cfg.window))
        elif cfg.classifier == "pose_rule":  # INVALID BY CONSTRUCTION: head yaw says nothing about the verification label
            m = _nanmean_window(pose_buf, cfg.window)
            cls = np.where(np.isnan(m), 0, np.where(m > cfg.yaw_threshold, -1, 1))
            conf_cls = np.where(np.isnan(m), 0.0, _conf_pose(cfg))
        elif cfg.classifier == "random_rule":
            cls = rand_label[t]
            conf_cls = np.full(n, _conf_pose(cfg))
        classified = cls != 0
        cls_correct = classified & (cls == np.where(y, 1, -1))
        wrongful_adverse_cls = classified & (cls == -1) & y
        # ---- acceptance (an institutional act)
        consistent = ((cls == -1) & (warrant == 1)) | ((cls == 1) & (warrant == 0))
        accepted = classified & (conf_cls >= cfg.confidence_floor) & (consistent if cfg.requires_warrant else True)
        # ---- score
        if cfg.use_score:
            if cfg.score_expiry and t > 0 and t % cfg.score_expiry == 0:
                score = np.zeros(n)
                extinguished_total += 1
            score = np.where(accepted, (1 - cfg.rho) * score + cfg.rho * cls, score)
        # ---- correction at t
        if cfg.correct_at is not None and t == cfg.correct_at:
            # wrongful: favourable by the verification label (an oracle retraction) and denied at the moment, whether by the score or by a binding constraint; all_adverse: everyone denied at the moment
            target = (y & ~access) if cfg.correction_scope == "wrongful" else ~access
            corrected_total |= target
            score = np.where(target, np.maximum(score, cfg.correction_score_target), score)
            if cfg.correction_clears_lock:
                locked = locked & ~target
                denied_run = np.where(
                    target, 0, denied_run
                )  # the denials that set the constraint are retracted: the count of consecutive denials starts again
        # ---- gate A (read at its reading times; a binding constraint overrides the score)
        read_now = cfg.use_score and (t % max(1, cfg.read_every_a) == 0)
        if cfg.use_score:
            if read_now:
                access_score = score >= cfg.tau_a
            ok_run = np.where(score >= cfg.tau_a, ok_run + 1, 0)
        else:
            access_score = lottery_u < cfg.baseline_access
        released_now = np.zeros(n, dtype=bool)
        if cfg.lock_after is not None and cfg.use_score:
            locked = locked | ((~locked) & (denied_run >= cfg.lock_after))
            released_now = locked & (ok_run >= cfg.release_after)
            locked = locked & ~released_now
            cum_released += int(released_now.sum())
        access = access_score & ~locked
        # ---- transfer and institution B
        if cfg.transfer_at is not None and t == cfg.transfer_at:
            snap_b = score.copy()
            score_b = cfg.transfer_weight * snap_b
        if (
            snap_b is not None
            and cfg.propagate_correction
            and cfg.correct_at is not None
            and t == cfg.correct_at + cfg.propagation_delay
        ):
            snap_b = np.where(
                corrected_total, np.maximum(snap_b, cfg.correction_score_target), snap_b
            )  # the correction reaches B (late if delayed)
            score_b = cfg.transfer_weight * snap_b
        if snap_b is not None:
            access_b = score_b >= cfg.tau_b
        b_baseline = lottery_u < cfg.baseline_access
        # ---- what access changes
        denied = ~access
        denied_run = np.where(denied, denied_run + 1, 0)
        resources = np.clip(resources + cfg.gain * access - cfg.loss * denied, 0.0, 1.0)
        if cfg.correct_at is not None and t > cfg.correct_at and cfg.reentry_support > 0:
            resources = np.clip(resources + cfg.reentry_support * (1.0 - resources) * corrected_total, 0.0, 1.0)
        opp_lost += denied
        opp_gained += access
        wrongly_denied = denied & y
        lost_fav += float(wrongly_denied.sum())
        if cfg.beta:
            z = z + cfg.beta * (resources - 0.5) + 0.02 * eps_z[t]
        else:
            z = z + 0.02 * eps_z[t]
        # ---- Address Domain states of the score at institution A
        altered = access != (lottery_u < cfg.baseline_access) if cfg.use_score else np.zeros(n, dtype=bool)
        # ---- series
        rows["t"].append(t)
        rows["z_mean"].append(float(z.mean()))
        rows["meas_correct"].append(meas_correct)
        rows["cls_correct"].append(float(cls_correct.sum() / max(1, classified.sum())))
        rows["abstain"].append(float((~classified).mean()))
        for name, k in zip(("warrant_supported", "warrant_refuted", "warrant_undecided"), range(3), strict=True):
            rows[name].append(float((warrant == k).mean()))
        rows["accepted"].append(float(accepted.mean()))
        rows["wrongful_adverse"].append(float((accepted & wrongful_adverse_cls).sum() / max(1, int(y.sum()))))
        rows["access"].append(float(access.mean()))
        rows["access_fav"].append(float(access[y].mean()) if y.any() else float("nan"))
        rows["access_unfav"].append(float(access[~y].mean()) if (~y).any() else float("nan"))
        rows["score_mean"].append(float(score.mean()))
        rows["resources_mean"].append(float(resources.mean()))
        rows["lost_fav_cum"].append(lost_fav / max(1, n))
        rows["locked"].append(float(locked.mean()))
        rows["released"].append(float(released_now.sum()))
        rows["b_access"].append(float(access_b.mean()) if snap_b is not None else float("nan"))
        rows["b_force"].append(float((access_b != b_baseline).mean()) if snap_b is not None else float("nan"))
        rows["score_exists"].append(float(((score != 0) if cfg.use_score else np.zeros(n, bool)).mean()))
        rows["score_read"].append(float(1.0 if read_now else 0.0))
        rows["score_transferred"].append(float(1.0 if snap_b is not None else 0.0))
        rows["access_altered"].append(float(altered.mean()))
        rows["score_extinguished"].append(float(extinguished_total))
        rows["constraint_extinguished"].append(float(cum_released))
        rows["wrongly_denied_now"].append(float(wrongly_denied.mean()))
        for k, i in enumerate(sample_idx):
            records[k].append(
                {
                    "t": t,
                    "reference_z": round(float(z_series[t, i]), 4),
                    "verification_label": bool(y[i]),
                    "pose_reference": [round(float(x), 2) for x in pose_ref[i, t]],
                    "pose_measured": [None if np.isnan(x) else round(float(x), 2) for x in pose_meas["values"][i]],
                    "pose_confidence": round(float(pose_meas["confidence"][i]), 3),
                    "pose_missing": int(pose_meas["reason"][i]),
                    "signal_measured": None if np.isnan(sig_meas["values"][i, 0]) else round(float(sig_meas["values"][i, 0]), 3),
                    "signal_missing": int(sig_meas["reason"][i]),
                    "classification": int(cls[i]),
                    "classification_correct": bool(cls_correct[i]) if classified[i] else None,
                    "warrant": WARRANT[int(warrant[i])],
                    "p_positive": round(float(p_pos[i]), 3),
                    "accepted": bool(accepted[i]),
                    "score": round(float(score[i]), 4),
                    "access": bool(access[i]),
                    "locked": bool(locked[i]),
                    "resources": round(float(resources[i]), 3),
                    "opportunities_lost": float(opp_lost[i]),
                    "corrected": bool(corrected_total[i]),
                    "score_b": round(float(score_b[i]), 4) if snap_b is not None else None,
                    "access_b": bool(access_b[i]) if snap_b is not None else None,
                }
            )
        denied_prev = denied.copy()
        access_hist.append(access.copy())

    y_end = z > 0
    summary = _summary(
        cfg,
        rows,
        y_end,
        access,
        resources,
        opp_lost,
        opp_gained,
        locked,
        corrected_total,
        score,
        snap_b,
        score_b,
        access_b,
        lottery_u,
        z0,
        z,
    )
    # state dependence of a denial and its self-fulfilment (for subjects favourable at the start)
    ah = np.array(access_hist)
    early, late = ah[4:11].mean(axis=0) < 0.5, ah[-8:].mean(axis=0) < 0.5
    fav0 = z0 > 0
    e, ne = early & fav0, (~early) & fav0
    summary["denial_persistence_favourable"] = float(late[e].mean()) if e.any() else None  # P(still denied late | denied early)
    summary["denial_late_if_not_denied_early_favourable"] = float(late[ne].mean()) if ne.any() else None
    summary["self_fulfilled_share_of_early_denied_favourable"] = (
        float((z[e] <= 0).mean()) if e.any() else None
    )  # they were favourable, were denied, and ended unfavourable
    decided = warrant != 2
    summary["warrant_decided"] = float(decided.mean())
    summary["warrant_support_wrong"] = float(
        (decided & ((warrant == 0) != y_end)).sum() / max(1, int(decided.sum()))
    )  # a SUPPORTED or REFUTED that contradicts the verification label
    # a period with nothing to average is None (JSON has no NaN): the series and the summary are cleaned before they leave the engine
    rows = {k: [None if (isinstance(v, float) and v != v) else v for v in vs] for k, vs in rows.items()}
    summary = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in summary.items()}
    out = {"config": cfg.asdict(), "series": rows, "records": records, "summary": summary}
    out["target_state_digest"] = digest([[round(float(v), 9) for v in row] for row in z_series])
    out["result_digest"] = digest({k: out[k] for k in ("series", "summary")})
    return out


def _conf_pose(cfg: Config) -> float:
    from .pose import base_confidence

    return base_confidence(cfg.pose_sensor)


def _fin(x: list[float]) -> list[float]:
    return [v for v in x if v == v]


def _summary(
    cfg,
    rows,
    y_end,
    access,
    resources,
    opp_lost,
    opp_gained,
    locked,
    corrected_total,
    score,
    snap_b,
    score_b,
    access_b,
    lottery_u,
    z0,
    z,
) -> dict:
    T = cfg.periods
    last = slice(max(0, T - 8), T)
    mean = lambda k, s=last: float(np.nanmean(rows[k][s])) if len(_fin(rows[k][s])) else None  # noqa: E731
    y0 = z0 > 0
    wrong0 = y0 & (score < cfg.tau_a)  # subjects whose reference was favourable at the start and who ended below the threshold
    af, au = mean("access_fav"), mean("access_unfav")
    gap = (af - au) if af is not None and au is not None else None
    b_ev = None
    if snap_b is not None:
        pred = np.where(score_b >= cfg.tau_b, 1, -1)
        b_ev = float(np.mean(pred == np.where(y_end, 1, -1)))
    return {
        "measurement_correct": mean("meas_correct"),
        "classification_correct": mean("cls_correct"),
        "abstain": mean("abstain"),
        "accepted": mean("accepted"),
        "warrant_supported": mean("warrant_supported"),
        "warrant_undecided": mean("warrant_undecided"),
        "wrongful_adverse_adopted": mean("wrongful_adverse"),
        "access": mean("access"),
        "access_favourable": mean("access_fav"),
        "access_unfavourable": mean("access_unfav"),
        "score_mean": mean("score_mean"),
        "resources_mean": mean("resources_mean"),
        "lost_opportunities_favourable_per_subject": float(rows["lost_fav_cum"][-1]),
        "locked_fraction": mean("locked"),
        "wrongly_denied_at_end": mean("wrongly_denied_now"),
        "opportunities_lost_mean": float(opp_lost.mean()),
        "opportunities_gained_mean": float(opp_gained.mean()),
        "access_gap_favourable_minus_unfavourable": gap,
        "ended_below_threshold_though_favourable_at_start": float(wrong0.mean()),
        "corrected_share": float(corrected_total.mean()),
        "score_recovered_share_of_corrected": float((score[corrected_total] >= cfg.tau_a).mean())
        if corrected_total.any()
        else None,
        "still_denied_after_correction_share_of_corrected": float((~access[corrected_total]).mean())
        if corrected_total.any()
        else None,
        "resources_of_corrected_mean": float(resources[corrected_total].mean()) if corrected_total.any() else None,
        "b_access": mean("b_access"),
        "b_institutional_force": mean("b_force"),
        "b_evidential_accuracy_of_transferred_score": b_ev,
        "b_denied_though_favourable": (float((~access_b[y_end]).mean()) if snap_b is not None and y_end.any() else None),
        "initial_real_state_mean": float(z0.mean()),
        "final_real_state_mean": float(z.mean()),
    }
