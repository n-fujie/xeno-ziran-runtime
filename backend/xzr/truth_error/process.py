"""TRUTH-ERROR phase 2: the correction PROCESS, the recoverability of a lost opportunity, and the appeal, as records and as fixed metrics of a run.

Everything here is a reading of what the engine recorded for the synthetic subjects; nothing is estimated for a real person. Each time below is a period index (None: the event did not occur within the periods).

The nine events of a subject, kept as nine separate times (none is derived from another):
  misclassified    the first period at which the classifier gave an adverse label to a subject who is favourable by the verification label
  adopted          the first period at which such a label was adopted by the institution
  denied           the first period of an access denial
  detected         the first period at which an audit found the evidence to support "z > 0" against a judgement in force
  requested        the correction request
  approved         the correction approval
  score_updated    the update of the score
  released         the release of a binding constraint
  restored         the first period, from the approval on, at which a subject who was still denied when the correction was approved has access again (access implies no constraint in force)

Recoverability is an accounting of the access history under a DECLARED window: a lost opportunity is recoverable if access returns within the window, expired if the window closed first, unresolved if the observed periods ended first.
The window is a parameter, not a finding: 'irreversible' is the case window = 0 (or None); whether unrecoverability holds is read from the experiments, never assumed.
"""

from __future__ import annotations

import numpy as np

EVENTS = ("misclassified", "adopted", "denied", "detected", "requested", "approved", "score_updated", "released", "restored")
APPEAL_STAGES = ("appeal_filed", "evidence_submitted", "appeal_accepted", "rejudged")
OBS_LATE = 10  # the late observation window: the last periods

# The metrics fixed in advance, each with its denominator, observation period, aggregation unit and the virtual-population composition.
METRICS: dict[str, dict[str, str]] = {
    "access_rate_late_fav": {
        "denominator": "subjects favourable at the start (z0>0) x late periods",
        "period": f"the last {OBS_LATE} periods",
        "unit": "subject-period, averaged per subject, then per seed",
    },
    "denial_rate_late_fav": {
        "denominator": "subjects favourable at the start (z0>0) x late periods",
        "period": f"the last {OBS_LATE} periods",
        "unit": "subject-period (1 - access rate; kept apart so that its own paired difference is read)",
    },
    "lost_opportunities_per_fav": {
        "denominator": "subjects favourable at the start (z0>0)",
        "period": "all periods",
        "unit": "denied periods per subject (not netted for any recovery)",
    },
    "recovery_time": {
        "denominator": "favourable-at-start subjects still denied when a correction was approved",
        "period": "from the approval to the restoration, within all periods",
        "unit": "periods per subject (mean over those restored; the censored share is reported beside it)",
    },
    "recovery_censored_share": {
        "denominator": "favourable-at-start subjects still denied when a correction was approved",
        "period": "all periods",
        "unit": "share not restored before the periods ended",
    },
    "persistent_constraint": {
        "denominator": "subjects favourable at the start (z0>0)",
        "period": "the final period",
        "unit": "share under a binding constraint at the end",
    },
    "propagation_b_denied_fav": {
        "denominator": "subjects favourable at the start (z0>0); institution B only after the transfer",
        "period": "the final period",
        "unit": "share denied at institution B at the end",
    },
}


# COMPLEMENTARY metrics, added after the verification of section 12.3: the primary metrics above look only at the subjects favourable at the start and so are blind to what the institution does to the others, among them the
# subjects it denies CORRECTLY. They are additions: no primary metric is changed or removed. Subjects "not favourable at the start" are those with z0 <= 0 (about half of the population).
COMPLEMENT_METRICS: dict[str, dict[str, str]] = {
    "denial_rate_late_unfav": {
        "denominator": "subjects not favourable at the start (z0<=0) x late periods",
        "period": f"the last {OBS_LATE} periods",
        "unit": "subject-period, averaged per subject within a run; the comparison is paired over seeds (one run = one unit)",
    },
    "lost_opportunities_per_unfav": {"denominator": "subjects not favourable at the start (z0<=0)", "period": "all periods", "unit": "denied periods per subject"},
    "share_unfav_ever_denied": {"denominator": "subjects not favourable at the start (z0<=0)", "period": "all periods", "unit": "share denied in at least one period"},
    "state_change_unfav": {
        "denominator": "subjects not favourable at the start (z0<=0)",
        "period": "from the start to the end of the 40 periods (z after the last update minus z0, so 40 updates)",
        "unit": "change of the real reference state z, in the units of z (standard normal at the start); mean per run, paired over seeds. It moves through the resource feedback beta only",
    },
    "state_change_unfav_denied": {"denominator": "subjects not favourable at the start (z0<=0) and denied in at least one period (the correctly denied, by the start label)", "period": "first to last period", "unit": "as state_change_unfav"},
    "state_change_fav": {"denominator": "subjects favourable at the start (z0>0)", "period": "first to last period", "unit": "as state_change_unfav"},
    "state_gap_change": {"denominator": "both groups", "period": "first to last period", "unit": "state_change_fav minus state_change_unfav: the change of the distance between the two groups"},
    "resources_end_fav": {"denominator": "subjects favourable at the start (z0>0)", "period": "the last period", "unit": "resources in [0, 1]; mean per run"},
    "resources_end_unfav": {"denominator": "subjects not favourable at the start (z0<=0)", "period": "the last period", "unit": "resources in [0, 1]; mean per run"},
}


def complement_outputs(ah, ev, z0, z_end, resources_end) -> dict:
    ah = np.asarray(ah, dtype=bool)
    un, fv = z0 <= 0, z0 > 0
    nu = max(1, int(un.sum()))
    late = ah[-OBS_LATE:][:, un]
    den = ev["denied"] >= 0
    dz = z_end - z0

    def mean(x, mask):
        return float(x[mask].mean()) if mask.any() else None

    sc_un, sc_fv = mean(dz, un), mean(dz, fv)
    return {
        "denial_rate_late_unfav": float(1.0 - late.mean()) if late.size else None,
        "lost_opportunities_per_unfav": float((~ah[:, un]).sum() / nu),
        "share_unfav_ever_denied": float(den[un].mean()) if un.any() else None,
        "state_change_unfav": sc_un,
        "state_change_unfav_denied": mean(dz, un & den),
        "state_change_fav": sc_fv,
        "state_gap_change": (sc_fv - sc_un) if sc_un is not None and sc_fv is not None else None,
        "resources_end_unfav": mean(resources_end, un),
        "resources_end_fav": mean(resources_end, fv),
    }


# metrics of the HYPOTHETICAL guarantee and support conditions (phase 4)
GUARANTEE_METRICS: dict[str, dict[str, str]] = {
    "guarantee_access_periods_per_subject": {"denominator": "all subjects", "period": "all periods", "unit": "periods in which a hypothetical guarantee granted access the gate had denied; mean per run"},
    "support_units_per_subject": {"denominator": "all subjects", "period": "all periods", "unit": "resources the support rule gave, summed over periods; mean per run: the COST of the support in the units of resources"},
    "support_share_to_unfav": {"denominator": "the support given", "period": "all periods", "unit": "share of the support units that went to subjects not favourable at the start (z0<=0): the precision of the recipients' identification; None if no support was given"},
    "support_per_unfav": {"denominator": "subjects not favourable at the start (z0<=0)", "period": "all periods", "unit": "support units per subject"},
    "support_per_fav": {"denominator": "subjects favourable at the start (z0>0)", "period": "all periods", "unit": "support units per subject (support that reached the favourable)"},
    "capacity_binding_periods": {"denominator": "the periods", "period": "all periods", "unit": "number of periods in which the support capacity left targeted subjects unserved"},
    "support_utilisation": {"denominator": "subject-periods in which a subject was eligible for the support", "period": "all periods", "unit": "share of them in which the subject was served: a PROXY of the reach of the guarantee (use of it), not the effective reachability, which the model does not measure"},
    "unfav_ever_eligible": {"denominator": "subjects not favourable at the start (z0<=0)", "period": "all periods", "unit": "share eligible for the support in at least one period"},
    "unfav_eligible_never_served": {"denominator": "subjects not favourable at the start (z0<=0) that were eligible in at least one period", "period": "all periods", "unit": "share never served: the guarantee existed for them and did not reach them"},
    "time_to_first_support": {"denominator": "subjects eligible and served at least once", "period": "all periods", "unit": "mean period of the first support"},
}


def _reach(z0, eligible_periods, served_periods, first_support) -> dict:
    if eligible_periods is None:
        return {"support_utilisation": None, "unfav_ever_eligible": None, "unfav_eligible_never_served": None, "time_to_first_support": None}
    un = z0 <= 0
    el = eligible_periods > 0
    served_ever = served_periods > 0
    tot = int(eligible_periods.sum())
    return {
        "support_utilisation": float(served_periods.sum() / tot) if tot else None,
        "unfav_ever_eligible": float(el[un].mean()) if un.any() else None,
        "unfav_eligible_never_served": float((~served_ever[un & el]).mean()) if (un & el).any() else None,
        "time_to_first_support": float(first_support[served_ever].mean()) if served_ever.any() else None,
    }


def guarantee_outputs(z0, guard_periods, support_units, capacity_binding, eligible_periods=None, served_periods=None, first_support=None) -> dict:
    un, fv = z0 <= 0, z0 > 0
    tot = float(support_units.sum())
    return {
        "guarantee_access_periods_per_subject": float(guard_periods.mean()),
        "support_units_per_subject": float(support_units.mean()),
        "support_share_to_unfav": float(support_units[un].sum() / tot) if tot > 0 else None,
        "support_per_unfav": float(support_units[un].mean()) if un.any() else None,
        "support_per_fav": float(support_units[fv].mean()) if fv.any() else None,
        "capacity_binding_periods": float(capacity_binding),
        **_reach(z0, eligible_periods, served_periods, first_support),
    }


# PHASE 5: the evaluation label under four conditions, kept apart. One set of classifications (made once, by the same classifier on the same inputs) is evaluated against:
#   initial          the label of the state BEFORE any institutional action (z0 > 0), fixed for the whole run: the FIXED REFERENCE LABEL
#   current          the label of the state at the start of the period (z_t > 0): the state after all the earlier institutional effects, before this period's decision. This is the label the model has always used
#   next             the label of the state AFTER this period's own decision (z_(t+1) > 0): the POST-INTERVENTION label of that decision
#   counterfactual   the label of the state the subject would have had with no institutional effect on the state (the matched run with beta = 0 and the same noise): the COUNTERFACTUAL REFERENCE
# The bins split the subject-periods by the distance of the actual state from the boundary (|z|), so that a change of the accuracy can be divided into a change of the INPUT DISTRIBUTION (how many subject-periods lie where classification is easy) and a change WITHIN each distance (the classifier, the observation, the label).
LATE_PERIODS = 8  # the window of the summary's classification_correct
BIN_EDGES = (0.0, 0.25, 0.5, 1.0, 2.0)
LABELS = ("initial", "current", "next", "counterfactual")
LABEL_METRICS: dict[str, dict[str, str]] = {
    "accuracy_initial": {"denominator": "classified subject-periods", "period": "the last 8 periods (the window of the summary)", "unit": "mean over periods of the share correct against the FIXED label z0>0"},
    "accuracy_current": {"denominator": "classified subject-periods", "period": "the last 8 periods (the window of the summary)", "unit": "mean over periods of the share correct against the label of the state at the start of the period (the model's own metric, `classification_correct`)"},
    "accuracy_next": {"denominator": "classified subject-periods", "period": "the last 8 periods", "unit": "mean per-period share correct against the label of the state after the period's own decision"},
    "accuracy_counterfactual": {"denominator": "classified subject-periods", "period": "the last 8 periods", "unit": "mean per-period share correct against the label of the state with no institutional effect on the state (the matched run at beta 0 with the same noise)"},
    "accuracy_current_all": {"denominator": "classified subject-periods", "period": "all periods", "unit": "as accuracy_current over the whole run"},
    "accuracy_counterfactual_all": {"denominator": "classified subject-periods", "period": "all periods", "unit": "as accuracy_counterfactual over the whole run"},
    "label_shift_current_vs_initial": {"denominator": "subject-periods", "period": "all periods", "unit": "share whose current label differs from the fixed label"},
    "label_shift_current_vs_counterfactual": {"denominator": "subject-periods", "period": "all periods", "unit": "share whose current label differs from the counterfactual label: the labels the institution changed"},
    "label_shift_next_vs_current": {"denominator": "subject-periods", "period": "all periods", "unit": "share whose label changes across the period's own decision"},
    "target_change_abs": {"denominator": "subject-periods", "period": "all periods", "unit": "mean |z - z counterfactual|: how far the institution moved the evaluated state"},
    "boundary_mass_actual": {"denominator": "subject-periods", "period": "all periods", "unit": "share with |z|<0.5 (near the boundary, where classification is hard), actual state"},
    "boundary_mass_counterfactual": {"denominator": "subject-periods", "period": "all periods", "unit": "the same for the counterfactual state"},
    "signal_abs_mean": {"denominator": "observed signal values", "period": "all periods", "unit": "mean |signal|: the input the classifier reads"},
    "favourable_share_current": {"denominator": "subject-periods", "period": "all periods", "unit": "share favourable by the current label (the composition of the evaluated population)"},
    "favourable_share_initial": {"denominator": "subjects", "period": "the start", "unit": "share favourable at the start"},
    "accuracy_current_unfav": {"denominator": "classified subject-periods of subjects not favourable at the start", "period": "all periods", "unit": "pooled share correct against the current label"},
    "accuracy_current_fav": {"denominator": "classified subject-periods of subjects favourable at the start", "period": "all periods", "unit": "pooled share correct against the current label"},
    "accuracy_pooled_current": {"denominator": "classified subject-periods", "period": "all periods", "unit": "pooled share correct against the current label (the sum over the bins of share x accuracy: the quantity the decomposition divides)"},
}


def label_outputs(cfg, cls_hist, z0, z_series, z_end, eps_z, sig_abs_sum, sig_abs_n) -> dict:
    """All the metrics are over the LATE window (the last 8 periods), as the summary's ``classification_correct`` is; ``accuracy_*_all`` and the series give the whole run."""
    T, n = z_series.shape
    cl = np.asarray(cls_hist)  # (T, n)
    classified = cl != 0
    z_cf = z0[None, :] + 0.02 * np.vstack([np.zeros((1, n)), np.cumsum(eps_z, axis=0)[:-1]])  # beta = 0, same noise (pose coupling does not enter the state)
    z_next = np.vstack([z_series[1:], z_end[None, :]])
    lab = {"initial": np.broadcast_to((z0 > 0)[None, :], (T, n)), "current": z_series > 0, "next": z_next > 0, "counterfactual": z_cf > 0}
    pred = cl == 1
    win = slice(max(0, T - LATE_PERIODS), T)
    un, fv = z0 <= 0, z0 > 0

    def rates(name: str) -> np.ndarray:
        ok = classified & (pred == lab[name])
        return ok.sum(axis=1) / np.maximum(1, classified.sum(axis=1))

    def late(name: str) -> float | None:
        return float(rates(name)[win].mean()) if classified[win].any() else None

    def pooled(name: str, mask: np.ndarray) -> float | None:
        c = classified[win][:, mask]
        return float((c & (pred[win][:, mask] == lab[name][win][:, mask])).sum() / c.sum()) if c.sum() else None

    az = np.abs(z_series)
    edges = np.array(BIN_EDGES + (np.inf,))
    idx = np.clip(np.searchsorted(edges, az, side="right") - 1, 0, len(edges) - 2)
    ok_cur = classified & (pred == lab["current"])
    nb = len(edges) - 1
    cls_n = np.array([int((classified[win] & (idx[win] == b)).sum()) for b in range(nb)])
    cor_n = np.array([int((ok_cur[win] & (idx[win] == b)).sum()) for b in range(nb)])
    tot = max(1, int(cls_n.sum()))
    m = {
        "accuracy_initial": late("initial"),
        "accuracy_current": late("current"),
        "accuracy_next": late("next"),
        "accuracy_counterfactual": late("counterfactual"),
        "accuracy_current_all": float(rates("current").mean()),
        "accuracy_counterfactual_all": float(rates("counterfactual").mean()),
        "label_shift_current_vs_initial": float((lab["current"][win] != lab["initial"][win]).mean()),
        "label_shift_current_vs_counterfactual": float((lab["current"][win] != lab["counterfactual"][win]).mean()),
        "label_shift_next_vs_current": float((lab["next"][win] != lab["current"][win]).mean()),
        "target_change_abs": float(np.abs(z_series - z_cf)[win].mean()),
        "boundary_mass_actual": float((az[win] < 0.5).mean()),
        "boundary_mass_counterfactual": float((np.abs(z_cf[win]) < 0.5).mean()),
        "signal_abs_mean": float(sig_abs_sum / sig_abs_n) if sig_abs_n else None,
        "favourable_share_current": float(lab["current"][win].mean()),
        "favourable_share_initial": float(fv.mean()),
        "accuracy_current_unfav": pooled("current", un),
        "accuracy_current_fav": pooled("current", fv),
        "accuracy_pooled_current": float(cor_n.sum() / tot),
    }
    for b in range(nb):
        m[f"bin{b}_share"] = float(cls_n[b] / tot)
        m[f"bin{b}_accuracy"] = float(cor_n[b] / cls_n[b]) if cls_n[b] else None
    series = {name: [float(x) for x in rates(name)] for name in LABELS}
    return {"metrics": m, "series": series, "definitions": LABEL_METRICS, "bin_edges": [float(e) if np.isfinite(e) else None for e in edges], "late_periods": LATE_PERIODS, "_z_cf": z_cf, "_z_next": z_next}


def _events_block(ev: dict[str, np.ndarray]) -> dict:
    out: dict[str, dict] = {}
    for k in EVENTS:
        a = ev[k]
        got = a >= 0
        out[k] = {"times": [int(v) if v >= 0 else None for v in a], "n": int(got.sum()), "mean_time": float(a[got].mean()) if got.any() else None}
    return out


def recoverability(access: np.ndarray, window: int | None) -> dict:
    """``access``: (periods, subjects) booleans. Classify every lost opportunity (a denied period) and every episode (a maximal run of denied periods) under the declared window.

    A denied period d is recoverable if access returns by d+window; expired if the window closed without a return; unresolved if the observed periods ended inside the window with no return.
    window None is read as 0 (nothing lost is ever regained: the irreversible case, stated rather than assumed elsewhere).
    """
    w = 0 if window is None else int(window)
    T, n = access.shape
    periods = {"recoverable": 0, "expired": 0, "unresolved": 0}
    episodes = {"recoverable": 0, "partially_recoverable": 0, "unrecoverable": 0, "unresolved": 0}
    for i in range(n):
        d = 0
        while d < T:
            if access[d, i]:
                d += 1
                continue
            e = d
            while e + 1 < T and not access[e + 1, i]:
                e += 1
            returns = e + 1 < T
            kinds = []
            for p in range(d, e + 1):
                if returns and (e + 1) - p <= w:
                    kinds.append("recoverable")
                elif not returns and p + w >= T:
                    kinds.append("unresolved")
                else:
                    kinds.append("expired")
            for k in kinds:
                periods[k] += 1
            if "unresolved" in kinds:
                episodes["unresolved"] += 1
            elif all(k == "recoverable" for k in kinds):
                episodes["recoverable"] += 1
            elif all(k == "expired" for k in kinds):
                episodes["unrecoverable"] += 1
            else:
                episodes["partially_recoverable"] += 1
            d = e + 1
    return {"window": window, "periods": periods, "episodes": episodes}


def process_outputs(cfg, ev, ap, ap_blocked, ap_outcome, false_detect, ah, fav0, fav_end, locked_end, denied_at_approval, access_b_end, z0=None, z_end=None, resources_end=None, guard_periods=None, support_units=None, capacity_binding=0, eligible_periods=None, served_periods=None, first_support=None) -> dict:
    ah = np.asarray(ah, dtype=bool)  # (periods, subjects)
    T, n = ah.shape
    nf = max(1, int(fav0.sum()))
    late = ah[-OBS_LATE:][:, fav0]
    denied_fav = (~ah[:, fav0]).sum(axis=0)
    denied_all = (~ah).sum(axis=0)
    elig = fav0 & denied_at_approval
    rec_t = (ev["restored"] - ev["approved"])[elig & (ev["restored"] >= 0)]
    m = {
        "access_rate_late_fav": float(late.mean()) if late.size else None,
        "denial_rate_late_fav": float(1.0 - late.mean()) if late.size else None,
        "lost_opportunities_per_fav": float(denied_fav.sum() / nf),
        "recovery_time": float(rec_t.mean()) if rec_t.size else None,
        "recovery_censored_share": float(((ev["restored"] < 0) & elig).sum() / max(1, int(elig.sum()))) if elig.any() else None,
        "persistent_constraint": float(locked_end[fav0].mean()) if fav0.any() else None,
        "propagation_b_denied_fav": float((~access_b_end[fav0]).mean()) if access_b_end is not None and fav0.any() else None,
    }
    filed = ap["appeal_filed"] >= 0
    app = {
        "exists": bool(cfg.appeal),
        "access": cfg.appeal_access,
        "blocked_subjects": int(ap_blocked.sum()),
        "stages": {k: int((ap[k] >= 0).sum()) for k in APPEAL_STAGES},
        "stage_times": {k: [int(v) if v >= 0 else None for v in ap[k]] for k in APPEAL_STAGES},
        "rejudged_corrected": int((ap_outcome == 1).sum()),
        "rejudged_upheld": int((ap_outcome == 2).sum()),
        # an appeal EXISTING is not relief. relief_effective counts subjects favourable at the start who end with access and no constraint after a re-judgement in their favour: an ASSOCIATION, not an effect of the appeal (they may have regained access without it); the effect is the paired difference from the run without the appeal (EXP-TE12)
        "relief_effective": int(((ap_outcome == 1) & ah[-1] & ~locked_end & fav0).sum()),
        "filed_but_not_relieved": int((filed & ~((ap_outcome == 1) & ah[-1])).sum()),
        "filed_share_of_fav_denied_ever": float((filed & fav0).sum() / max(1, int((fav0 & (denied_all > 0)).sum()))),
    }
    return {
        "events": _events_block(ev),
        "favourable_at_start": [bool(v) for v in fav0],
        "false_detections": int(false_detect.sum()),
        # a constraint released and then bound again (the denials that follow a release can set it anew)
        "reimposed_after_release": int(((ev["released"] >= 0) & locked_end).sum()),
        "metrics": m,
        "metric_definitions": METRICS,
        "complement": complement_outputs(ah, ev, z0, z_end, resources_end) if z0 is not None else None,
        "complement_definitions": COMPLEMENT_METRICS,
        "guarantee": guarantee_outputs(z0, guard_periods, support_units, capacity_binding, eligible_periods, served_periods, first_support) if z0 is not None and guard_periods is not None else None,
        "guarantee_definitions": GUARANTEE_METRICS,
        "appeal": app,
        "recoverability": {
            "favourable_at_start": recoverability(ah[:, fav0], cfg.opportunity_window),
            "declared_window": cfg.opportunity_window,
        },
        "access_history_favourable": [[int(v) for v in row] for row in ah[:, fav0]],
    }
