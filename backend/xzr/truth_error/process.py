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


def process_outputs(cfg, ev, ap, ap_blocked, ap_outcome, false_detect, ah, fav0, fav_end, locked_end, denied_at_approval, access_b_end) -> dict:
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
        "appeal": app,
        "recoverability": {
            "favourable_at_start": recoverability(ah[:, fav0], cfg.opportunity_window),
            "declared_window": cfg.opportunity_window,
        },
        "access_history_favourable": [[int(v) for v in row] for row in ah[:, fav0]],
    }
