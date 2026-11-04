"""EXP-TE07 .. TE14 (TRUTH-ERROR phase 2): is the correction of a judgement the same as the release of an institutional constraint, and under what conditions is it not?

As in ``experiments``: arms, seeds, outcomes, ranges and failure conditions are fixed HERE before any run, every arm is the control with exactly the declared changes (checked), and every arm shares all random draws with the
control, so a paired difference is the effect of the change alone. Phase 2 adds, for every experiment, a REPLICATION on a second, disjoint list of seeds (21..40): a difference is called ``replicated`` only if it is detected
in both lists with the same sign; detected in one list only (or with opposite signs) is ``set-dependent``; detected in neither is ``not detected``. A point estimate on one list is never a conclusion.

The primary metrics are fixed in ``process.METRICS`` (denominator, observation period, aggregation unit, virtual-population composition). The virtual population is the same in every arm: n=120 synthetic subjects whose real
operating condition z is drawn standard normal; "favourable at the start" is z0>0 (about half).

The two things kept apart here: the CORRECTION of a judgement (the approval and the update of the score) and the RELEASE of a binding constraint (the end of the lock that earlier denials set). That one can occur
without the other is a property of this model's two mechanisms, tested below, not an assumption: where the mechanism is absent (no binding constraint; a score that never binds) the two are not distinct, and that is a result too.
SYNTHETIC ONLY: nothing here says how a real institution behaves."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from .experiments import BASE, SEEDS, _diff, _paired, _run_experiment
from .institution import Config, digest, run
from .process import COMPLEMENT_METRICS, GUARANTEE_METRICS, LABEL_METRICS, METRICS, OBS_LATE, recoverability

SEEDS2 = tuple(range(21, 41))
PRIMARY2 = (
    "access_rate_late_fav",
    "denial_rate_late_fav",
    "lost_opportunities_per_fav",
    "recovery_time",
    "persistent_constraint",
    "propagation_b_denied_fav",
)
# the one institution all of phase 2 starts from (changed only by the declared factors of each experiment)
P0 = dataclasses.replace(
    BASE,
    lock_after=4,
    release_after=3,
    beta=0.06,
    audit_every=2,
    request_delay=1,
    approval_delay=2,
    score_delay=0,
    release_mode="after_approval",
    release_delay=0,
    opportunity_window=4,
    transfer_at=12,
    propagate_correction=True,
    propagation_delay=2,
)
NO_PROCESS = dataclasses.replace(P0, audit_every=None, release_mode="by_score")  # no audit, no correction: a binding constraint ends only by the phase-1 rule (release_after periods at or above the threshold)
# the ranges of the one-factor sensitivity (TE13) fixed before the runs: each continuous setting at a low, the base and a high value
PARAMETER_RANGES: dict[str, tuple] = {
    "rho": (0.1, 0.25, 0.5),
    "tau_a": (-0.2, 0.0, 0.2),
    "signal_sensor.noise_sigma": (0.4, 0.8, 1.6),
    "lock_after": (2, 4, 8),
    # release_after is omitted: P0 releases with the approval (release_mode after_approval), so it is inoperative there; the by_score rule is varied in TE07
    "gain": (0.06, 0.12, 0.24),
    "loss": (0.06, 0.12, 0.24),
    "beta": (0.0, 0.06, 0.12),
    "audit_every": (1, 2, 4),
    "audit_sensitivity": (0.3, 0.6, 0.9),
    "approval_delay": (0, 2, 8),
    "release_delay": (0, 4, 8),
    "propagation_delay": (2, 8, 16),
}
LIMITS2 = (
    "Synthetic subjects and a synthetic institution; every constant is this implementation's declared assumption; descriptive over 20 seeds plus a replication on 20 other seeds; "
    "a result holds for these assumptions only and says nothing about a real institution, person or law. An intervention here is an intervention in the model, not a statement of causal necessity in the world."
)


def _pm(k: str) -> Callable[[dict], Any]:
    return lambda r: r["process"]["metrics"][k]


def _share(ev: str) -> Callable[[dict], Any]:
    return lambda r: r["process"]["events"][ev]["n"] / r["config"]["n"]


def _mean_time(ev: str) -> Callable[[dict], Any]:
    return lambda r: r["process"]["events"][ev]["mean_time"]


EXTRA: dict[str, Callable[[dict], Any]] = {k: _pm(k) for k in (*PRIMARY2, "recovery_censored_share")}
EXTRA.update({f"share_{e}": _share(e) for e in ("misclassified", "detected", "approved", "score_updated", "released", "restored")})
EXTRA.update({f"time_{e}": _mean_time(e) for e in ("detected", "approved", "score_updated", "released", "restored")})
EXTRA["reimposed_share"] = lambda r: r["process"]["reimposed_after_release"] / r["config"]["n"]
def _cm(k: str) -> Callable[[dict], Any]:
    return lambda r: (r["process"]["complement"] or {}).get(k)


EXTRA.update({k: _cm(k) for k in COMPLEMENT_METRICS})


def _gm(k: str) -> Callable[[dict], Any]:
    return lambda r: (r["process"]["guarantee"] or {}).get(k)


EXTRA.update({k: _gm(k) for k in GUARANTEE_METRICS})


def _lm(k: str) -> Callable[[dict], Any]:
    return lambda r: (r["process"].get("labels") or {}).get("metrics", {}).get(k)


_BIN_KEYS = [f"bin{b}_{x}" for b in range(5) for x in ("share", "accuracy")]
EXTRA.update({k: _lm(k) for k in (*LABEL_METRICS, *_BIN_KEYS)})
# the same decisions evaluated against two labels: the difference is a difference of the label, not of the classifier or of the population
EXTRA["label_gap_current_minus_counterfactual"] = lambda r: _gap(r, "accuracy_current", "accuracy_counterfactual")
EXTRA["label_gap_current_minus_initial"] = lambda r: _gap(r, "accuracy_current", "accuracy_initial")
EXTRA["label_gap_next_minus_current"] = lambda r: _gap(r, "accuracy_next", "accuracy_current")


def _gap(r: dict, a: str, b: str) -> float | None:
    m = (r["process"].get("labels") or {}).get("metrics", {})
    return None if m.get(a) is None or m.get(b) is None else m[a] - m[b]


# runs are cached by configuration so that an experiment that re-reads the arms of another (EXP-TE20 reads those of EXP-TE19) does not run them again
_RUN_CACHE: dict[str, dict] = {}


def _cached_run(cfg: Config) -> dict:
    key = json.dumps(cfg.asdict(), sort_keys=True, default=str)
    if key not in _RUN_CACHE:
        _RUN_CACHE[key] = run(cfg)
    return _RUN_CACHE[key]


def clear_run_cache() -> None:
    _RUN_CACHE.clear()
EXTRA["false_detection_share"] = lambda r: r["process"]["false_detections"] / r["config"]["n"]


def _with(cfg: Config, **kw) -> Config:
    """replace, allowing the nested signal-sensor noise as ``signal_sensor__noise_sigma``"""
    nested = {k: kw.pop(k) for k in list(kw) if "__" in k}
    for k, v in nested.items():
        parent, child = k.split("__")
        kw[parent] = dataclasses.replace(getattr(cfg, parent), **{child: v})
    return dataclasses.replace(cfg, **kw)


def _declared(base: Config, named: dict[str, dict[str, Any]], control: str) -> dict[str, list[str]]:
    """the declared change of each arm: the settings whose value differs from the control arm's (a setting an arm does not name keeps the base's value)"""

    def val(f: dict[str, Any], k: str) -> Any:
        if k in f:
            return f[k]
        parent, _, child = k.partition("__")
        return getattr(getattr(base, parent), child) if child else getattr(base, parent)

    keys = {k for f in named.values() for k in f}
    return {n: sorted({k.partition("__")[0] for k in keys if val(f, k) != val(named[control], k)}) for n, f in named.items()}


def _grid(ctl: Config, named: dict[str, dict[str, Any]], control: str | None = None) -> tuple[dict[str, Config], dict[str, list[str]]]:
    arms = {name: _with(ctl, **dict(f)) for name, f in named.items()}
    return arms, _declared(ctl, named, control or next(iter(named)))


def _combo(res: dict, terms: list[tuple[float, str]], outcome: str) -> dict:
    """a signed combination of arms, per seed (a contrast; an interaction is the combination +,-,-,+), tested as a paired difference from zero"""
    vals = {r["arm"]: r["values"][outcome] for r in res["arms"]}
    n = len(next(iter(vals.values())))
    per_seed = []
    for i in range(n):
        xs = [vals[a][i] for _, a in terms]
        per_seed.append(None if any(x is None or x != x for x in xs) else sum(c * x for (c, _), x in zip(terms, xs, strict=True)))
    return _paired(per_seed, [0.0 if v is not None else None for v in per_seed])


def _contrasts(res: dict, spec: list[tuple[str, list[tuple[float, str]]]], outcomes: tuple[str, ...]) -> list[dict]:
    return [{"label": lab, "terms": [[c, a] for c, a in terms], "outcome": o, "paired": _combo(res, terms, o)} for lab, terms in spec for o in outcomes]


def _classify(pa: dict, pb: dict) -> str:
    da, db = pa.get("detected"), pb.get("detected")
    if da is None or db is None:
        return "no data"
    if da and db and (pa["mean"] > 0) == (pb["mean"] > 0):
        return "replicated"
    if da or db:
        return "set-dependent"
    return "not detected"


def _run2(spec: dict) -> dict:
    spec = {**spec, "keep_values": True, "extra": {**EXTRA, **spec.get("extra", {})}}
    a = _run_experiment(spec, SEEDS)
    b = _run_experiment(spec, SEEDS2)
    primary = list(spec.get("primary", PRIMARY2))
    rep = []
    for ra, rb in zip(a["arms"], b["arms"], strict=True):
        if ra["arm"] == a["control"]:
            continue
        for k in primary:
            rep.append({"arm": ra["arm"], "outcome": k, "seeds_1_20": ra["paired_vs_control"][k], "seeds_21_40": rb["paired_vs_control"][k], "class": _classify(ra["paired_vs_control"][k], rb["paired_vs_control"][k])})
    ctlvals = next(r for r in a["arms"] if r["arm"] == a["control"])["values"]
    for r in a["arms"]:
        r["identical_outcomes_to_control_in_every_seed"] = r["arm"] != a["control"] and all(r["values"][k] == ctlvals[k] for k in r["values"])
    a["replication"] = {"seeds": list(SEEDS2), "rows": rep, "counts": {c: sum(1 for r in rep if r["class"] == c) for c in ("replicated", "set-dependent", "not detected", "no data")}}
    cs = spec.get("contrasts")
    if cs:
        outs = tuple(spec.get("contrast_outcomes", PRIMARY2[:2] + ("persistent_constraint",)))
        a["contrasts"] = _contrasts(a, cs, outs)
        b2 = _contrasts(b, cs, outs)
        for c1, c2 in zip(a["contrasts"], b2, strict=True):
            c1["paired_seeds_21_40"] = c2["paired"]
            c1["class"] = _classify(c1["paired"], c2["paired"])
    held_all = sorted(f.name for f in dataclasses.fields(Config) if f.name != "seed")
    a["intervention_records"] = [
        {
            "arm": r["arm"],
            "variables_changed": r["changed_vs_control"],
            "variables_held": [k for k in held_all if k not in r["changed_vs_control"]],
            "random_draws": "shared with the control in every seed (independent streams)",
            "observation": {"periods": a["periods"], "late_window_periods": OBS_LATE, "subjects": a["n_subjects"], "seeds": a["seeds"], "replication_seeds": list(SEEDS2)},
        }
        for r in a["arms"]
        if r["arm"] != a["control"]
    ]
    post = spec.get("post")
    if post:
        a["analysis"] = {"seeds_1_20": post(a), "seeds_21_40": post(b)}
    a["questions"] = spec.get("questions", [])
    a["limits"] = LIMITS2
    a["metric_definitions"] = {k: METRICS[k] for k in PRIMARY2 if k in METRICS}
    a["primary_outcomes"] = primary
    a["protocol"] = {**spec["protocol"], "replication_seeds": list(SEEDS2), "metrics": "process.METRICS"}
    a["protocol_digest"] = digest(a["protocol"])
    return a


def _no_idle_arm(a: dict, control: str) -> bool:
    """an arm whose every outcome equals the control's in every seed changed nothing: the factor was not operative (a construction defect, unless the experiment expects it)"""
    return any(all(v == a[control]["values"][k] for k, v in a[n]["values"].items()) for n in a if n != control)


def _failures_none_constraint(arm: str) -> Callable[[dict], bool]:
    return lambda a: float(np.nanmean([v for v in a[arm]["values"]["locked_fraction"] if v is not None])) <= 0.0


# ------------------------------------------------------------------------------------------------ TE07: correction without release, release without correction
def te07_release() -> dict:
    """N1: the correction is approved early; is the binding constraint released with it? Over the strength of the constraint mechanism and the release rule."""
    named: dict[str, dict[str, Any]] = {}
    for lock in (None, 2, 4, 8):
        for mode in ("never", "by_score", "after_approval"):
            named[f"lock_after={lock} / release={mode}"] = {"lock_after": lock, "release_mode": mode}
    ctl_name = "lock_after=4 / release=after_approval"
    arms, declared = _grid(P0, named, ctl_name)
    contrasts = []
    for lock in (None, 2, 4, 8):
        contrasts.append((f"N1 lock_after={lock}: withholding the release (never) minus releasing with the approval", [(1.0, f"lock_after={lock} / release=never"), (-1.0, f"lock_after={lock} / release=after_approval")]))
        contrasts.append((f"lock_after={lock}: release by the score alone minus release with the approval", [(1.0, f"lock_after={lock} / release=by_score"), (-1.0, f"lock_after={lock} / release=after_approval")]))
    return _run2(
        {
            "id": "EXP-TE07-release",
            "title": "Correction without release: is the constraint released when the judgement is corrected?",
            "question": "The correction (approval, score update) happens early for everyone the audit finds. Does a binding constraint set by earlier denials end with it, or only if a release is made, and how does that depend on whether a constraint mechanism exists at all?",
            "control": ctl_name,
            "arms": arms,
            "declared": declared,
            "primary": ("denial_rate_late_fav", "persistent_constraint", "lost_opportunities_per_fav", "access_rate_late_fav"),
            "contrasts": contrasts,
            "contrast_outcomes": ("denial_rate_late_fav", "persistent_constraint", "lost_opportunities_per_fav"),
            "failure_conditions": {"no constraint is set in the control (nothing to release)": _failures_none_constraint(ctl_name)},
            "protocol": {
                "changed": "lock_after (None, 2, 4, 8 denied periods before a constraint binds) x release_mode (never / by_score / after_approval)",
                "unchanged": "P0: audit every 2, request delay 1, approval delay 2, score updated at approval, release_delay 0, window 4, transfer at 12 with propagation delay 2",
                "seeds": list(SEEDS),
                "failure": "no constraint in the control",
                "criterion_N1": "non-identity (release not implied by correction) holds where 'never' minus 'after_approval' differs from 0 by more than 2 SE in both seed lists with persistent_constraint above; it does not hold where no constraint mechanism exists (lock_after=None: the two arms are the same run)",
            },
        }
    )


def te07_correction() -> dict:
    """N2: the constraint is released immediately; is access restored if the score is not updated? Over how often the score binds (tau_a) and over a delayed update."""
    base = _with(P0, approval_delay=0, request_delay=0, release_delay=0)
    named: dict[str, dict[str, Any]] = {}
    for tau in (-5.0, -0.2, 0.0):
        for sd in (0, 99):
            named[f"tau_a={tau:+.1f} / score update {'at approval' if sd == 0 else 'never (released only)'}"] = {"tau_a": tau, "score_delay": sd}
    ctl_name = "tau_a=+0.0 / score update at approval"
    arms, declared = _grid(base, named, ctl_name)
    contrasts = []
    for tau in (-5.0, -0.2, 0.0):
        contrasts.append((f"N2 tau_a={tau:+.1f}: released without a score update minus released with it", [(1.0, f"tau_a={tau:+.1f} / score update never (released only)"), (-1.0, f"tau_a={tau:+.1f} / score update at approval")]))
    return _run2(
        {
            "id": "EXP-TE07-correction",
            "title": "Release without correction: is access restored when the constraint is released but the score is not updated?",
            "question": "The binding constraint is released at the approval, immediately. If the score is not updated, does access come back, and how does that depend on whether the score ever binds?",
            "control": ctl_name,
            "arms": arms,
            "declared": declared,
            "primary": ("denial_rate_late_fav", "access_rate_late_fav", "persistent_constraint", "lost_opportunities_per_fav"),
            "contrasts": contrasts,
            "contrast_outcomes": ("denial_rate_late_fav", "access_rate_late_fav", "persistent_constraint"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl_name), "no constraint is set in the control": _failures_none_constraint(ctl_name)},
            "protocol": {
                "changed": "tau_a (the score's threshold: -5.0 means the score never binds) x score_delay (0, or 99 = the score is never updated within the periods)",
                "unchanged": "P0 with request delay 0, approval delay 0 and the release at the approval",
                "seeds": list(SEEDS),
                "failure": "no constraint in the control",
                "criterion_N2": "non-identity (correction not implied by release) holds where the score is never updated and the denial rate is higher than with the update by more than 2 SE in both seed lists; it does not hold where tau_a=-5.0 (the score cannot deny)",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE08: independent timing of correction and release
def te08_timing() -> dict:
    A, R = (0, 6, 16), (0, 6, 16)
    ctl = "no correction process (a constraint ends by the score: the phase-1 rule)"
    named: dict[str, dict[str, Any]] = {ctl: {"audit_every": None, "release_mode": "by_score"}, "no correction process and no release (a constraint stays)": {"audit_every": None, "release_mode": "never"}}
    for a in A:
        for r in R:
            named[f"approval delay {a} / release delay {r}"] = {"audit_every": 2, "release_mode": "after_approval", "approval_delay": a, "release_delay": r}
    arms, declared = _grid(P0, named, ctl)
    nm = lambda a, r: f"approval delay {a} / release delay {r}"  # noqa: E731
    inter = [
        ("interaction of correction time (0 vs 16) and release time (0 vs 16)", [(1.0, nm(16, 16)), (-1.0, nm(0, 16)), (-1.0, nm(16, 0)), (1.0, nm(0, 0))]),
        ("interaction of correction time (0 vs 6) and release time (0 vs 6)", [(1.0, nm(6, 6)), (-1.0, nm(0, 6)), (-1.0, nm(6, 0)), (1.0, nm(0, 0))]),
        ("correction time alone, release immediate: 16 minus 0", [(1.0, nm(16, 0)), (-1.0, nm(0, 0))]),
        ("release time alone, correction immediate: 16 minus 0", [(1.0, nm(0, 16)), (-1.0, nm(0, 0))]),
        ("immediate correction and release minus no process (score release)", [(1.0, nm(0, 0)), (-1.0, ctl)]),
        ("immediate correction and release minus no process and no release", [(1.0, nm(0, 0)), (-1.0, "no correction process and no release (a constraint stays)")]),
    ]
    return _run2(
        {
            "id": "EXP-TE08",
            "title": "Timing of correction and timing of release as independent variables",
            "question": "The approval delay (correction time) and the release delay (release time) are varied independently. What does each alone do, and do they interact?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": PRIMARY2,
            "contrasts": inter,
            "contrast_outcomes": ("denial_rate_late_fav", "lost_opportunities_per_fav", "persistent_constraint", "recovery_time"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl), "no constraint is set in the control": _failures_none_constraint(ctl)},
            "protocol": {
                "changed": "approval_delay (0, 6, 16) x release_delay (0, 6, 16) periods (with release_mode after_approval), against a control without any audit/correction whose constraint ends by the score (phase-1 rule), and a second reference where it never ends",
                "unchanged": "P0 otherwise (audit every 2, request delay 1, window 4)",
                "seeds": list(SEEDS),
                "failure": "no constraint in the control",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE09: baselines and single-factor removal
def te09_ablation() -> dict:
    named: dict[str, dict[str, Any]] = {
        "full institution (P0)": {},
        "no score (lottery)": {"use_score": False},
        "classification never adopted (confidence_floor 2)": {"confidence_floor": 2.0},
        "random classification": {"classifier": "random_rule"},
        "invalid rule (head pose)": {"classifier": "pose_rule"},
        "no binding constraint": {"lock_after": None},
        "no resource feedback to the real state (beta 0)": {"beta": 0.0},
        "no correction process (release by the score)": {"audit_every": None, "release_mode": "by_score"},
        "no correction process and no release": {"audit_every": None, "release_mode": "never"},
        "no transfer to institution B": {"transfer_at": None},
        "immediate correction and release": {"audit_every": 1, "request_delay": 0, "approval_delay": 0, "release_delay": 0},
        "immediate release only (by score after 1 period)": {"audit_every": None, "release_mode": "by_score", "release_after": 1},
        "accurate signal sensor, no release": {"signal_sensor__noise_sigma": 0.1, "audit_every": None, "release_mode": "never"},
        "accurate signal sensor (noise 0.1)": {"signal_sensor__noise_sigma": 0.1},
    }
    arms, declared = _grid(P0, named, "full institution (P0)")
    return _run2(
        {
            "id": "EXP-TE09",
            "title": "Single-factor removal and baselines",
            "question": "Remove one element of the institution at a time (the score, the adoption of the classification, the constraint, the resource feedback, the correction, the transfer), and compare random classification, an invalid rule, immediate correction and immediate release. Which elements does each metric depend on?",
            "control": "full institution (P0)",
            "arms": arms,
            "declared": declared,
            "primary": PRIMARY2,
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, "full institution (P0)"), "no wrongful denial in the full institution (nothing to correct)": lambda a: float(np.nanmean(a["full institution (P0)"]["values"]["lost_opportunities_favourable_per_subject"])) < 0.5},
            "protocol": {
                "changed": "one element at a time (the arms' names)",
                "unchanged": "P0 otherwise",
                "seeds": list(SEEDS),
                "failure": "no wrongful denial in the full institution",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE10: causal questions
def te10_causal() -> dict:
    named: dict[str, dict[str, Any]] = {
        "full institution (P0), no correction process": {"audit_every": None, "release_mode": "by_score"},
        "Q1 accurate classification (signal noise 0.05)": {"audit_every": None, "release_mode": "by_score", "signal_sensor__noise_sigma": 0.05},
        "Q2 adoption removed (confidence_floor 2)": {"audit_every": None, "release_mode": "by_score", "confidence_floor": 2.0},
        "Q3 resource allocation fixed (gain = loss = 0)": {"audit_every": None, "release_mode": "by_score", "gain": 0.0, "loss": 0.0},
        "Q3 resource feedback to the state removed (beta 0)": {"audit_every": None, "release_mode": "by_score", "beta": 0.0},
        "Q4 only the observation changes (view angle 40, occlusion 0.25)": {"audit_every": None, "release_mode": "by_score", "signal_sensor__view_angle": 40.0, "signal_sensor__occlusion_prob": 0.25},
        "Q4 only the observation changes, real state held (beta 0)": {"audit_every": None, "release_mode": "by_score", "beta": 0.0, "signal_sensor__view_angle": 40.0, "signal_sensor__occlusion_prob": 0.25},
        "Q5 corrected early (approval at the first audit)": {"audit_every": 1, "release_mode": "after_approval", "request_delay": 0, "approval_delay": 0, "release_delay": 0},
        "Q5 oracle classification and no constraint (nothing to correct)": {"audit_every": None, "release_mode": "by_score", "signal_sensor__noise_sigma": 0.05, "lock_after": None},
        "Q6 accurate classification, a constraint that never ends": {"audit_every": None, "signal_sensor__noise_sigma": 0.05, "release_mode": "never"},
    }
    ctl = "full institution (P0), no correction process"
    arms, declared = _grid(NO_PROCESS, named, ctl)
    questions = [
        {"id": "Q1", "question": "Does classification error alone create a constraint?", "arm": "Q1 accurate classification (signal noise 0.05)", "reads": "persistent_constraint, lost_opportunities_per_fav", "variable_changed": "signal_sensor.noise_sigma 0.8 -> 0.05", "held": "everything else, including the adoption, the score, the constraint rule and every random draw"},
        {"id": "Q2", "question": "Does removing institutional adoption remove the effect?", "arm": "Q2 adoption removed (confidence_floor 2)", "reads": "persistent_constraint, lost_opportunities_per_fav", "variable_changed": "confidence_floor 0.3 -> 2 (no classification is adopted)", "held": "the sensors, the classifier (it still classifies), the score rule, the constraint rule"},
        {"id": "Q3", "question": "Does fixing the allocation of resources remove the self-reinforcement?", "arm": "Q3 resource allocation fixed (gain = loss = 0)", "reads": "self_fulfilled_share_of_early_denied_favourable, denial_persistence_favourable", "variable_changed": "gain and loss 0.12 -> 0 (access no longer changes the resources)", "held": "the sensors, classification, adoption, score, constraint; the subject's state still moves by beta*(resources-0.5), which is constant"},
        {"id": "Q4", "question": "Which differences remain when only the observation conditions change?", "arm": "Q4 only the observation changes (view angle 40, occlusion 0.25)", "reads": "classification_correct, persistent_constraint, lost_opportunities_per_fav", "variable_changed": "the signal sensor's view angle and occlusion", "held": "the sensors' other conditions and every random draw; NOTE the subjects' real states are NOT held here (resources feed back, beta 0.06, so a different access changes them: the arm's target-state flag is False); the Q4 arm with beta 0 holds them (read against the Q3 beta-0 arm)"},
        {"id": "Q6", "question": "Does an accurate classification make the constraint end (is accuracy return capacity)?", "arm": "Q6 accurate classification, a constraint that never ends", "reads": "persistent_constraint, lost_opportunities_per_fav, against the accurate-classification arm Q1 (whose constraint ends by the score)", "variable_changed": "release_mode by_score -> never, with the classification accurate", "held": "the sensors, classification, adoption and score; every random draw"},
        {"id": "Q5", "question": "Which history dependence remains after correction?", "arm": "Q5 corrected early (approval at the first audit)", "reads": "lost_opportunities_per_fav, persistent_constraint, denial_rate_late_fav, against the oracle/no-constraint arm", "variable_changed": "the audit and the correction/release times", "held": "the sensors and the classification: the history of denials before the correction is the same in both arms"},
    ]
    contrasts = [
        ("Q1 accurate classification minus the control", [(1.0, "Q1 accurate classification (signal noise 0.05)"), (-1.0, ctl)]),
        ("Q2 adoption removed minus the control", [(1.0, "Q2 adoption removed (confidence_floor 2)"), (-1.0, ctl)]),
        ("Q3 fixed allocation minus the control", [(1.0, "Q3 resource allocation fixed (gain = loss = 0)"), (-1.0, ctl)]),
        ("Q3 no resource feedback to the state minus the control", [(1.0, "Q3 resource feedback to the state removed (beta 0)"), (-1.0, ctl)]),
        ("Q4 observation-only change minus the control", [(1.0, "Q4 only the observation changes (view angle 40, occlusion 0.25)"), (-1.0, ctl)]),
        ("Q4 observation-only change with the real state held (beta 0) minus the beta-0 arm", [(1.0, "Q4 only the observation changes, real state held (beta 0)"), (-1.0, "Q3 resource feedback to the state removed (beta 0)")]),
        ("Q5 early correction minus the control", [(1.0, "Q5 corrected early (approval at the first audit)"), (-1.0, ctl)]),
        ("Q6 accurate classification with a constraint that never ends minus accurate classification whose constraint ends by the score", [(1.0, "Q6 accurate classification, a constraint that never ends"), (-1.0, "Q1 accurate classification (signal noise 0.05)")]),
        ("Q5 what remains after early correction: corrected minus the oracle with no constraint", [(1.0, "Q5 corrected early (approval at the first audit)"), (-1.0, "Q5 oracle classification and no constraint (nothing to correct)")]),
    ]
    return _run2(
        {
            "id": "EXP-TE10",
            "title": "Causal decomposition under shared initial conditions and common random numbers",
            "question": "Five intervention questions on the model. Each arm changes one declared variable and holds the rest; every arm shares all random draws with the control.",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": PRIMARY2 + ("classification_correct", "self_fulfilled_share_of_early_denied_favourable", "denial_persistence_favourable"),
            "questions": questions,
            "contrasts": contrasts,
            "contrast_outcomes": ("lost_opportunities_per_fav", "persistent_constraint", "denial_rate_late_fav", "self_fulfilled_share_of_early_denied_favourable"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl), "no constraint is set in the control": _failures_none_constraint(ctl)},
            "protocol": {
                "changed": "one declared variable per arm (see the questions)",
                "unchanged": "NO_PROCESS (P0 without audit; a constraint ends by the score) otherwise",
                "seeds": list(SEEDS),
                "failure": "no constraint in the control",
                "note": "an intervention in the model, with the other variables held, is not an inference of causal necessity from observed correlation",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE11: recoverability of a lost opportunity
WINDOWS = (0, 2, 6, 12)


def _rec(kind: str, key: str, w: int, per_fav: bool = False) -> Callable[[dict], Any]:
    """a count from the recoverability accounting of one run: ``kind`` periods or episodes, ``key`` the class, ``w`` the declared window; as a share of the class totals, or per subject favourable at the start"""

    def f(r: dict) -> Any:
        hist = np.array(r["process"]["access_history_favourable"], dtype=bool)
        x = recoverability(hist, w)[kind]
        if per_fav:
            return x[key] / max(1, hist.shape[1])
        tot = sum(x.values())
        return x[key] / tot if tot else None

    return f


def te11_recoverability() -> dict:
    named: dict[str, dict[str, Any]] = {
        "no correction process": {"audit_every": None, "release_mode": "by_score"},
        "correction approved early (delay 0)": {"approval_delay": 0, "request_delay": 0},
        "correction approved late (delay 8)": {"approval_delay": 8},
        "correction approved very late (delay 20)": {"approval_delay": 20, "request_delay": 4},
    }
    ctl = "no correction process"
    arms, declared = _grid(P0, named, ctl)
    extra: dict[str, Callable[[dict], Any]] = {}
    for w in WINDOWS[1:]:
        for key in ("recoverable", "expired", "unresolved"):
            extra[f"periods_{key}_per_fav_W{w}"] = _rec("periods", key, w, per_fav=True)
        extra[f"periods_recoverable_share_W{w}"] = _rec("periods", "recoverable", w)
    for key in ("recoverable", "partially_recoverable", "unrecoverable", "unresolved"):
        extra[f"episodes_{key}_share_W6"] = _rec("episodes", key, 6)
    return _run2(
        {
            "id": "EXP-TE11",
            "title": "Recoverability of a lost opportunity: when does unrecoverability hold?",
            "question": "A lost opportunity (a denied period of a subject favourable at the start) is recoverable if access returns within a declared window of the denial. As the window and the timing of the correction vary, how many lost opportunities are recoverable, expired or unresolved, and where does the irreversible reading (window 0) stop describing the model?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "extra": extra,
            "primary": tuple(f"periods_{k}_per_fav_W6" for k in ("recoverable", "expired", "unresolved")) + ("periods_recoverable_per_fav_W12", "periods_recoverable_per_fav_W2", "episodes_unrecoverable_share_W6", "episodes_unresolved_share_W6"),
            "failure_conditions": {
                "an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl),
                "no wrongful denial in the control": lambda a: float(np.nanmean(a["no correction process"]["values"]["lost_opportunities_favourable_per_subject"])) < 0.5,
            },
            "protocol": {
                "changed": "the correction process (none, with the constraint ending by the score; or approval delay 0 / 8 / 20 with the release at the approval)",
                "windows": list(WINDOWS),
                "unchanged": "P0 otherwise; the window changes only the accounting of the same access history, not the dynamics",
                "seeds": list(SEEDS),
                "failure": "no wrongful denial in the control",
                "note": "window 0 is the irreversible reading by definition (nothing is recoverable, every closed episode unrecoverable); whether lost opportunities in fact return is read from the windows above 0, never assumed. Counts per subject favourable at the start are given beside shares because a share can rise when its denominator falls",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE12: appeals
def _app(k: str) -> Callable[[dict], Any]:
    return lambda r: r["process"]["appeal"][k] / r["config"]["n"] if k in ("blocked_subjects", "relief_effective", "rejudged_corrected", "rejudged_upheld", "filed_but_not_relieved") else r["process"]["appeal"]["stages"][k] / r["config"]["n"]


def te12_appeal() -> dict:
    appeal_base = _with(NO_PROCESS, appeal=True, request_delay=0, approval_delay=1)
    named: dict[str, dict[str, Any]] = {
        "no appeal": {"appeal": False},
        "appeal open to every denied subject": {},
        "appeal gated by the score (only subjects at or above the threshold may file)": {"appeal_access": "score_gated", "appeal_min_score": 0.0},
        "appeal open, little evidence (0.2)": {"evidence_available_prob": 0.2},
        "appeal open, low acceptance capacity (0.2)": {"appeal_acceptance_prob": 0.2},
        "appeal open, slow review (10 periods)": {"review_delay": 10},
        "appeal open, filing is costly (0.1)": {"appeal_filing_prob": 0.1},
    }
    ctl = "no appeal"
    arms, declared = _grid(appeal_base, named, ctl)
    extra = {
        **{f"appeal_{k}_share": _app(k) for k in ("appeal_filed", "evidence_submitted", "appeal_accepted", "rejudged")},
        "appeal_blocked_share": _app("blocked_subjects"),
        "appeal_relief_effective_share": _app("relief_effective"),
        "appeal_filed_but_not_relieved_share": _app("filed_but_not_relieved"),
        "appeal_rejudged_corrected_share": _app("rejudged_corrected"),
        "appeal_rejudged_upheld_share": _app("rejudged_upheld"),
    }
    contrasts = [
        ("an open appeal minus no appeal", [(1.0, "appeal open to every denied subject"), (-1.0, "no appeal")]),
        ("a score-gated appeal minus an open appeal (the design danger)", [(1.0, "appeal gated by the score (only subjects at or above the threshold may file)"), (-1.0, "appeal open to every denied subject")]),
    ]
    return _run2(
        {
            "id": "EXP-TE12",
            "title": "Appeals: the existence of an appeal is not relief",
            "question": "A synthetic institution lets a denied subject appeal: file, submit evidence, have it accepted, be re-judged, and (if the re-judgement follows the evidence) be corrected and released. How far does an appeal that exists give relief, and what changes when the appeal itself is gated by the score that the appeal is meant to challenge?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "extra": extra,
            "primary": PRIMARY2 + ("appeal_relief_effective_share", "appeal_filed_but_not_relieved_share"),
            "contrasts": contrasts,
            "contrast_outcomes": ("denial_rate_late_fav", "lost_opportunities_per_fav", "persistent_constraint", "appeal_relief_effective_share"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl), "no wrongful denial without an appeal": lambda a: float(np.nanmean(a["no appeal"]["values"]["lost_opportunities_favourable_per_subject"])) < 0.5},
            "protocol": {
                "changed": "the appeal's existence, its access rule, the evidence, the capacity, the review time, the filing effort",
                "unchanged": "NO_PROCESS (a constraint ends by the score) with request delay 0 and approval delay 1; no audit",
                "seeds": list(SEEDS),
                "failure": "no wrongful denial without an appeal",
                "scope": "the score-gated appeal is a hypothetical control to study institutional design danger; it is not a procedure for evaluating any real person",
            },
        }
    )


def te12_release() -> dict:
    """Added AFTER the null result of TE12 (an exploratory arm set, kept apart so TE12's pre-registered content is unchanged): the appeal is connected to the correction in TE12, but the constraint ends there only by the score. Here the same appeal is combined with the release at the approval; no rule of the model is changed, a declared setting is."""
    base = _with(NO_PROCESS, appeal=True, request_delay=0, approval_delay=1)
    ctl = "no appeal, a constraint ends by the score (the TE12 control)"
    named: dict[str, dict[str, Any]] = {
        ctl: {"appeal": False},
        "appeal open, a constraint ends by the score (the TE12 arm)": {},
        "appeal open, the constraint is released at the approval": {"release_mode": "after_approval", "release_delay": 0},
        "no appeal, the constraint is released only at an approval (none is made)": {"appeal": False, "release_mode": "after_approval", "release_delay": 0},
        "appeal gated by the score, the constraint is released at the approval": {"release_mode": "after_approval", "release_delay": 0, "appeal_access": "score_gated", "appeal_min_score": 0.0},
        "appeal open, evidence always available and always accepted, released at the approval": {"release_mode": "after_approval", "release_delay": 0, "evidence_available_prob": 1.0, "appeal_acceptance_prob": 1.0, "appeal_filing_prob": 1.0},
    }
    arms, declared = _grid(base, named, ctl)
    contrasts = [
        ("MATCHED: the appeal minus no appeal, both with the constraint released only at an approval", [(1.0, "appeal open, the constraint is released at the approval"), (-1.0, "no appeal, the constraint is released only at an approval (none is made)")]),
        ("CONFOUNDED, shown for what it is: switching the release from the score to the approval (appeal present) loses the release by the score for everyone the appeal does not reach", [(1.0, "appeal open, the constraint is released at the approval"), (-1.0, "appeal open, a constraint ends by the score (the TE12 arm)")]),
        ("a fully resourced appeal (always filed, with evidence, accepted) minus an ordinary one, both released at the approval", [(1.0, "appeal open, evidence always available and always accepted, released at the approval"), (-1.0, "appeal open, the constraint is released at the approval")]),
    ]
    return _run2(
        {
            "id": "EXP-TE12-release",
            "title": "Appeals connected to the release (exploratory, added after the null result of TE12)",
            "question": "TE12 found no effect of an appeal on the outcomes. The trace of the transitions (appeal_trace) shows the appeal reaches the correction and the score update but not the release of a constraint, which ends there by the score. Does the appeal change the outcomes when the release is made at the approval, a setting the model already has? The matched comparison is within that release rule: the model has no rule that releases by the score OR at an approval, and adding one after seeing the null would be a post-hoc change of the model, so it is not done.",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": PRIMARY2 + ("share_approved", "share_released"),
            "contrasts": contrasts,
            "contrast_outcomes": ("denial_rate_late_fav", "lost_opportunities_per_fav", "persistent_constraint"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl), "no wrongful denial without an appeal": lambda a: float(np.nanmean(a[ctl]["values"]["lost_opportunities_favourable_per_subject"])) < 0.5},
            "protocol": {
                "changed": "release_mode / release_delay (the release at the approval), the appeal's access rule, and for the last arm the evidence, acceptance and filing probabilities",
                "unchanged": "NO_PROCESS with request delay 0, approval delay 1; no audit",
                "seeds": list(SEEDS),
                "failure": "no wrongful denial without an appeal",
                "status": "exploratory: the arms were chosen after TE12's result was known, to test a diagnosis; no model rule was changed",
            },
        }
    )


def te15_separation() -> dict:
    """The four things a correction is made of, manipulated one at a time: the time of the correction (approval), the update of the score, the release of the constraint, and (as the outcome) the restoration of access."""
    ctl = "no correction process (a constraint ends by the score: the phase-1 rule)"
    named: dict[str, dict[str, Any]] = {ctl: {"audit_every": None, "release_mode": "by_score"}}
    for a in (0, 8):
        for u in (0, 8):
            for r in (0, 8):
                named[f"approval {a} / score update +{u} / release +{r}"] = {"audit_every": 2, "release_mode": "after_approval", "approval_delay": a, "score_delay": u, "release_delay": r}
    arms, declared = _grid(P0, named, ctl)
    nm = lambda a, u, r: f"approval {a} / score update +{u} / release +{r}"  # noqa: E731

    def eff(axis: int) -> list[tuple[float, str]]:
        return [((0.25 if (i >> (2 - axis)) & 1 else -0.25), nm(*[(0, 8)[(i >> (2 - j)) & 1] for j in range(3)])) for i in range(8)]

    def prod(ax: tuple[int, ...]) -> list[tuple[float, str]]:
        return [(0.25 * float(np.prod([(1.0 if (i >> (2 - a)) & 1 else -1.0) for a in ax])), nm(*[(0, 8)[(i >> (2 - j)) & 1] for j in range(3)])) for i in range(8)]

    contrasts = [
        ("main effect of the time of the correction (approval 8 minus 0)", eff(0)),
        ("main effect of the score update (+8 minus +0)", eff(1)),
        ("main effect of the release (+8 minus +0)", eff(2)),
        ("interaction correction time x score update", prod((0, 1))),
        ("interaction correction time x release", prod((0, 2))),
        ("interaction score update x release", prod((1, 2))),
        ("three-way interaction", prod((0, 1, 2))),
    ]
    return _run2(
        {
            "id": "EXP-TE15",
            "title": "Separating the correction, the score update, the release and the restoration",
            "question": "The time of the correction (the approval), the update of the score and the release of the constraint are each delayed independently (2x2x2). Which of them does the restoration of access, the denial rate and the lost opportunities depend on, and do the dependences add?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": PRIMARY2 + ("time_approved", "time_score_updated", "time_released", "time_restored", "share_restored"),
            "contrasts": contrasts,
            "contrast_outcomes": ("denial_rate_late_fav", "lost_opportunities_per_fav", "persistent_constraint", "time_restored"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl), "no constraint is set in the control": _failures_none_constraint(ctl)},
            "protocol": {
                "changed": "approval_delay (0, 8) x score_delay (0, 8) x release_delay (0, 8)",
                "unchanged": "P0 otherwise (audit every 2, request delay 1, window 4, transfer at 12); the control has no audit",
                "seeds": list(SEEDS),
                "failure": "no constraint in the control",
                "observation_period": "40 periods; the late window is the last 10",
            },
        }
    )


# guarantees of the transition rules: a difference of these kinds is built in (it follows from the code of one period), so an experiment cannot "find" it; each is checked by a test of the rule itself
BY_CONSTRUCTION = {
    "release_mode never": "no release event can occur (the release block is not reached)",
    "lock_after none": "no constraint is ever set, so release and correction of a constraint are not distinct and the arms are identical runs",
    "tau_a far below the scores": "the score cannot deny access, so updating it changes nothing",
    "approval_delay / request_delay / score_delay / release_delay": "each shifts its own event by exactly that many periods (the times are stored, not estimated)",
    "classifier adopts nothing (confidence_floor above 1)": "the score stays at its initial value, which meets the threshold: nobody is denied",
    "appeal off": "no appeal event occurs and the run is the run without the procedure (same digest)",
    "the audit and the appeal cannot see the subject's score": "the audit reads the verification label; the appeal reads the evidence at re-judgement (a rule of the model)",
}


def appeal_trace(seeds: tuple[int, ...] = SEEDS) -> dict:
    """The connections of the appeal in the implemented transitions, counted over the seeds for the TE12 open-appeal configuration against the same configuration without the appeal. No rule is changed: this reads the runs."""
    base = _with(NO_PROCESS, appeal=True, request_delay=0, approval_delay=1)
    noap = dataclasses.replace(base, appeal=False)
    t = dict.fromkeys(("subjects", "filed", "evidence", "accepted", "rejudged", "corrected_by_rejudgement", "upheld", "correction_requested_at_rejudgement", "approved_after_request_delay", "score_updated_at_approval", "released_at_or_after_approval", "corrected_and_favourable", "corrected_and_unfavourable", "favourable_subjects", "favourable_with_any_access_difference", "late_denied_periods_with_appeal", "late_denied_periods_without", "needing_relief_still_denied_at_end", "needing_relief_never_filed", "needing_relief_filed_no_evidence", "needing_relief_filed_not_accepted", "needing_relief_upheld", "needing_relief_corrected_yet_denied"), 0)
    for seed in seeds:
        a, b = run(dataclasses.replace(base, seed=seed)), run(dataclasses.replace(noap, seed=seed))
        P = a["process"]
        st = {k: np.array([-1 if x is None else x for x in v]) for k, v in P["appeal"]["stage_times"].items()}
        ev = {k: np.array([-1 if x is None else x for x in P["events"][k]["times"]]) for k in P["events"]}
        fav = np.array(P["favourable_at_start"])
        rj = st["rejudged"] >= 0
        corr = rj & (ev["requested"] >= 0) & (ev["requested"] == st["rejudged"] + base.request_delay)
        t["subjects"] += base.n
        t["filed"] += int((st["appeal_filed"] >= 0).sum())
        t["evidence"] += int((st["evidence_submitted"] >= 0).sum())
        t["accepted"] += int((st["appeal_accepted"] >= 0).sum())
        t["rejudged"] += int(rj.sum())
        t["corrected_by_rejudgement"] += int(corr.sum())
        t["upheld"] += int((rj & ~corr).sum())
        t["correction_requested_at_rejudgement"] += int(corr.sum())
        t["approved_after_request_delay"] += int((corr & (ev["approved"] == ev["requested"] + base.approval_delay)).sum())
        t["score_updated_at_approval"] += int((corr & (ev["score_updated"] == ev["approved"])).sum())
        t["released_at_or_after_approval"] += int((corr & (ev["released"] >= ev["approved"])).sum())
        t["corrected_and_favourable"] += int((corr & fav).sum())
        t["corrected_and_unfavourable"] += int((corr & ~fav).sum())
        ha, hb = np.array(P["access_history_favourable"], dtype=bool), np.array(b["process"]["access_history_favourable"], dtype=bool)
        t["favourable_subjects"] += int(ha.shape[1])
        t["favourable_with_any_access_difference"] += int((ha != hb).any(axis=0).sum())
        t["late_denied_periods_with_appeal"] += int((~ha[-OBS_LATE:]).sum())
        denied_end = np.zeros(base.n, dtype=bool)
        denied_end[np.where(fav)[0]] = ~ha[-1]  # favourable at the start and still denied at the last period: the subjects an appeal would have to relieve
        flt = st["appeal_filed"] >= 0
        t["needing_relief_still_denied_at_end"] += int(denied_end.sum())
        t["needing_relief_never_filed"] += int((denied_end & ~flt).sum())
        t["needing_relief_filed_no_evidence"] += int((denied_end & flt & (st["evidence_submitted"] < 0)).sum())
        t["needing_relief_filed_not_accepted"] += int((denied_end & (st["evidence_submitted"] >= 0) & (st["appeal_accepted"] < 0)).sum())
        t["needing_relief_upheld"] += int((denied_end & rj & ~corr).sum())
        t["needing_relief_corrected_yet_denied"] += int((denied_end & corr).sum())
        t["late_denied_periods_without"] += int((~hb[-OBS_LATE:]).sum())
    return {"configuration": "TE12 open appeal (NO_PROCESS, request delay 0, approval delay 1, constraint ends by the score) against the same without the appeal", "seeds": list(seeds), "counts": t, "by_construction": BY_CONSTRUCTION}


def te16_complement() -> dict:
    """Added in the verification of section 12.3 (a complement, nothing is removed): what the institution does to the subjects NOT favourable at the start, among them the subjects it denies correctly. One run is one unit, the comparison is paired over seeds, and the references are stated: a lottery (access for half at random) and full access."""
    ctl = "lottery: no score, access for half at random"
    named: dict[str, dict[str, Any]] = {
        ctl: {"use_score": False},
        "full access: no score, access for everyone": {"use_score": False, "baseline_access": 1.0},
        "score, sensor noise 0.8 (the base sensor)": {},
        "score, accurate sensor (noise 0.05)": {"signal_sensor__noise_sigma": 0.05},
        "score, accurate sensor, no feedback of resources to the state (beta 0)": {"signal_sensor__noise_sigma": 0.05, "beta": 0.0},
        "score, accurate sensor, beta 0.03": {"signal_sensor__noise_sigma": 0.05, "beta": 0.03},
        "score, accurate sensor, beta 0.12": {"signal_sensor__noise_sigma": 0.05, "beta": 0.12},
        "score, accurate sensor, no binding constraint": {"signal_sensor__noise_sigma": 0.05, "lock_after": None},
    }
    arms, declared = _grid(NO_PROCESS, named, ctl)
    a, lo = "score, accurate sensor (noise 0.05)", ctl
    contrasts = [
        ("accurate score minus lottery", [(1.0, a), (-1.0, lo)]),
        ("accurate score minus full access", [(1.0, a), (-1.0, "full access: no score, access for everyone")]),
        ("base-sensor score minus lottery", [(1.0, "score, sensor noise 0.8 (the base sensor)"), (-1.0, lo)]),
        ("accurate score without the feedback (beta 0) minus lottery", [(1.0, "score, accurate sensor, no feedback of resources to the state (beta 0)"), (-1.0, lo)]),
        ("beta 0.12 minus beta 0.03 (accurate score)", [(1.0, "score, accurate sensor, beta 0.12"), (-1.0, "score, accurate sensor, beta 0.03")]),
    ]
    keys = tuple(COMPLEMENT_METRICS)
    return _run2(
        {
            "id": "EXP-TE16",
            "title": "Complementary metrics: what the score does to the subjects who were not favourable at the start",
            "question": "The primary metrics count the lost opportunities of the subjects favourable at the start. What does a correct classification do to the others, in particular to those it correctly denies, measured against a lottery and against full access, and through which declared setting?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": keys + ("denial_rate_late_fav", "lost_opportunities_per_fav"),
            "contrasts": contrasts,
            "contrast_outcomes": ("state_change_unfav", "state_change_unfav_denied", "state_change_fav", "state_gap_change", "denial_rate_late_unfav"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "the use of the score, the base access, the signal-sensor noise, beta (0, 0.03, 0.12) and the binding constraint",
                "unchanged": "NO_PROCESS otherwise: 120 subjects, 40 periods, beta 0.06 where not varied",
                "unit": "one run = one unit (the mean over its subjects); the paired difference and its standard error are over the 20 seeds, replicated on 20 others",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
                "status": "a complement added after a finding of the verification; the primary metrics are unchanged",
            },
        }
    )


# PHASE 4 (fixed before the runs). The metrics of TE17 and TE18 are: classification_correct (the summary), the complementary metrics (process.COMPLEMENT_METRICS) and, for the guarantees, process.GUARANTEE_METRICS; one run is one
# unit and every difference is paired over seeds 1-20 and replicated on 21-40. Initial conditions and random draws are shared by every arm. Each factor is varied alone unless an arm is named as a combination (the reason is in its name).
# The guarantee and support conditions are HYPOTHETICAL conditions of the synthetic institution. The manuscripts' guarantees (G2, G13, G14, G15) are functions without numeric levels; none of the numbers below is theirs.
SENS_NOISY, SENS_ACCURATE = 0.8, 0.05
P4_PRIMARY = ("classification_correct", "denial_rate_late_fav", "denial_rate_late_unfav", "state_change_unfav", "state_change_fav", "state_gap_change", "lost_opportunities_per_fav", "resources_end_unfav")


def te17_decomposition() -> dict:
    """P1, P2 and P3 of the phase-4 directive, each with its own arms. P1: the accuracy of the classification does not guarantee the legitimacy of the institutional effect (the model measures consequences; it does not measure legitimacy). P2: a disadvantage arises without classification error (the feedback of resources present and absent, with the error at about zero). P3: improving the accuracy changes the distribution of the disadvantage (the classifier, the allocation of resources, the denial rule and the initial state, separately)."""
    nz = "signal_sensor__noise_sigma"
    ctl = "noisy classifier (noise 0.8), the base"
    named: dict[str, dict[str, Any]] = {ctl: {}}
    named["lottery: no score, access for half at random"] = {"use_score": False}
    named["full access: no score, access for everyone"] = {"use_score": False, "baseline_access": 1.0}
    for noise in (1.6, 0.4, SENS_ACCURATE):
        named[f"classifier noise {noise}"] = {nz: noise}
    for noise, tag in ((SENS_NOISY, "noisy"), (SENS_ACCURATE, "accurate")):
        for beta in (0.0, 0.12):
            named[f"{tag}, beta {beta}"] = {nz: noise, "beta": beta}
        for label, kw in (
            ("allocation gain = loss = 0.06", {"gain": 0.06, "loss": 0.06}),
            ("allocation gain = loss = 0.24", {"gain": 0.24, "loss": 0.24}),
            ("threshold -0.2", {"tau_a": -0.2}),
            ("threshold +0.2", {"tau_a": 0.2}),
            ("no binding constraint", {"lock_after": None}),
            ("initial state shifted -0.5", {"z_shift": -0.5}),
            ("initial state shifted +0.5", {"z_shift": 0.5}),
            ("initial resources 0.8", {"resources_start": 0.8}),
        ):
            named[f"{tag}, {label}"] = {nz: noise, **kw}
    arms, declared = _grid(NO_PROCESS, named, ctl)
    acc, noi = "classifier noise 0.05", ctl
    contrasts = [
        ("P1: accurate classifier minus full access (the consequence of a classification that is correct)", [(1.0, acc), (-1.0, "full access: no score, access for everyone")]),
        ("P1: accurate classifier minus lottery", [(1.0, acc), (-1.0, "lottery: no score, access for half at random")]),
        ("P3: improving the accuracy (noise 0.8 -> 0.05)", [(1.0, acc), (-1.0, noi)]),
        ("P2: accurate, no feedback (beta 0) minus accurate with feedback (beta 0.06)", [(1.0, "accurate, beta 0.0"), (-1.0, acc)]),
        ("P2: accurate, no feedback minus lottery", [(1.0, "accurate, beta 0.0"), (-1.0, "lottery: no score, access for half at random")]),
        ("interaction: accuracy x feedback (beta 0 vs 0.06)", [(1.0, acc), (-1.0, noi), (-1.0, "accurate, beta 0.0"), (1.0, "noisy, beta 0.0")]),
        ("interaction: accuracy x threshold (0 vs +0.2)", [(1.0, "accurate, threshold +0.2"), (-1.0, "noisy, threshold +0.2"), (-1.0, acc), (1.0, noi)]),
        ("interaction: accuracy x binding constraint (present vs none)", [(1.0, acc), (-1.0, noi), (-1.0, "accurate, no binding constraint"), (1.0, "noisy, no binding constraint")]),
        ("interaction: accuracy x allocation (0.12 vs 0.24)", [(1.0, "accurate, allocation gain = loss = 0.24"), (-1.0, "noisy, allocation gain = loss = 0.24"), (-1.0, acc), (1.0, noi)]),
    ]
    questions = [
        {"id": "P1", "question": "Does the accuracy of a classification guarantee the legitimacy of its institutional effect?", "reads": "the consequences the model measures (state change, denial, resources) of an accurate classifier against full access and a lottery", "limit": "the model measures consequences; a normative judgement of legitimacy is NOT measured and is not made here"},
        {"id": "P2", "question": "Can an institutional disadvantage arise without classification error?", "reads": "denial rate, resources and state change of the accurate classifier with and without the feedback of resources to the state", "limit": "the error is about zero, not exactly zero (noise 0.05, classification_correct is reported); the disadvantage in access and resources needs no feedback, the disadvantage in state needs it by construction"},
        {"id": "P3", "question": "Does improving the accuracy change the distribution of the disadvantage?", "reads": "denial and state change of the favourable and not favourable groups, and the gap, while the classifier, the allocation, the denial rule and the initial state are varied separately", "limit": "interactions are read from the contrasts, not assumed to be additive"},
    ]
    return _run2(
        {
            "id": "EXP-TE17",
            "title": "P1-P3: accuracy, feedback and the distribution of the disadvantage",
            "question": "Three propositions about the relation of the correctness of a classification to institutional consequences, each tested by interventions on separate mechanisms of the model under shared initial conditions and random draws.",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": P4_PRIMARY,
            "questions": questions,
            "contrasts": contrasts,
            "contrast_outcomes": ("classification_correct", "denial_rate_late_fav", "denial_rate_late_unfav", "state_change_unfav", "state_change_fav", "state_gap_change"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "the classifier noise, the feedback beta, the allocation (gain, loss), the threshold, the binding constraint, the initial state (z_shift, resources_start), each alone, on a noisy and on an accurate classifier",
                "unchanged": "NO_PROCESS otherwise (120 subjects, 40 periods, beta 0.06 unless varied)",
                "unit": "one run = one unit; paired over seeds",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
            },
        }
    )


def te18_guarantees() -> dict:
    """Hypothetical minimum-guarantee and support conditions of the synthetic institution, on a noisy and on an accurate classifier. Whether a condition improves anything is the question, not an assumption: each arm is read against its own control and its cost, its precision and its effect on the other group are reported."""
    nz = "signal_sensor__noise_sigma"
    proc = {"audit_every": 2, "request_delay": 1, "approval_delay": 6, "release_mode": "after_approval", "release_delay": 0}
    named: dict[str, dict[str, Any]] = {}
    conds: dict[str, dict[str, Any]] = {
        "no guarantee": {},
        "resource floor 0.3": {"resource_floor": 0.3},
        "denial cap 3": {"denial_cap": 3},
        "denial cap 6": {"denial_cap": 6},
        "support to the denied 0.06": {"support_rule": "denied", "support_amount": 0.06},
        "support to the denied 0.12": {"support_rule": "denied", "support_amount": 0.12},
        "support to the low score 0.12": {"support_rule": "low_score", "support_amount": 0.12},
        "support to the low score 0.12, capacity 10%": {"support_rule": "low_score", "support_amount": 0.12, "support_capacity": 0.1},
        "support to the low score 0.12, capacity 25%": {"support_rule": "low_score", "support_amount": 0.12, "support_capacity": 0.25},
        "floor 0.3 + cap 6 + support to the low score 0.06 (a combination, to read the interaction)": {"resource_floor": 0.3, "denial_cap": 6, "support_rule": "low_score", "support_amount": 0.06},
    }
    proc_conds: dict[str, dict[str, Any]] = {
        "process, no guarantee": {**proc},
        "process + access kept pending the correction": {**proc, "interim_access": True},
        "process + recovery support after the release 0.3": {**proc, "release_support": 0.3},
        "process + both (a combination, to read the interaction)": {**proc, "interim_access": True, "release_support": 0.3},
    }
    for noise, tag in ((SENS_NOISY, "noisy"), (SENS_ACCURATE, "accurate")):
        for lab, kw in conds.items():
            named[f"{tag}: {lab}"] = {nz: noise, **kw}
        for lab, kw in proc_conds.items():
            named[f"{tag}: {lab}"] = {nz: noise, **kw}
    ctl = "noisy: no guarantee"
    arms, declared = _grid(NO_PROCESS, named, ctl)
    contrasts: list[tuple[str, list[tuple[float, str]]]] = []
    for tag in ("noisy", "accurate"):
        for lab in list(conds)[1:]:
            contrasts.append((f"{tag}: {lab} minus no guarantee", [(1.0, f"{tag}: {lab}"), (-1.0, f"{tag}: no guarantee")]))
        for lab in list(proc_conds)[1:]:
            contrasts.append((f"{tag}: {lab} minus the process alone", [(1.0, f"{tag}: {lab}"), (-1.0, f"{tag}: process, no guarantee")]))
        contrasts.append((f"{tag}: interaction of access-kept and recovery support", [(1.0, f"{tag}: process + both (a combination, to read the interaction)"), (-1.0, f"{tag}: process + access kept pending the correction"), (-1.0, f"{tag}: process + recovery support after the release 0.3"), (1.0, f"{tag}: process, no guarantee")]))
    contrasts.append(("accurate classification as the identifier of the recipients: share of the support reaching the not favourable, accurate minus noisy (support to the low score 0.12)", [(1.0, "accurate: support to the low score 0.12"), (-1.0, "noisy: support to the low score 0.12")]))
    return _run2(
        {
            "id": "EXP-TE18",
            "title": "Hypothetical minimum guarantees and support: what changes, what does not, what it costs",
            "question": "A minimum resource allocation, a cap on the accumulation of a denial, access kept while a correction is pending, a recovery measure after a release, and support to the denied or to the low-score subjects (with and without a capacity), each on a noisy and on an accurate classifier. Do they change the state of the not favourable group, the gap and the denial, at what cost, and where do they not improve anything?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": P4_PRIMARY + ("support_units_per_subject", "support_share_to_unfav", "guarantee_access_periods_per_subject", "recovery_time"),
            "contrasts": contrasts,
            "contrast_outcomes": ("state_change_unfav", "state_change_fav", "state_gap_change", "denial_rate_late_unfav", "denial_rate_late_fav", "support_units_per_subject", "support_share_to_unfav", "classification_correct"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "one guarantee or support condition per arm (see the names; the two combinations are named as such), on the noisy (0.8) and the accurate (0.05) classifier; the process arms add an audit every 2 periods, request delay 1, approval delay 6 and the release at the approval",
                "unchanged": "NO_PROCESS otherwise",
                "unit": "one run = one unit; paired over seeds; the cost is the resources given (support_units_per_subject)",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
                "status": "hypothetical conditions of a synthetic institution; not for any real person's credit review or eligibility",
            },
        }
    )


def paired_summary(a: Sequence[float | None], b: Sequence[float | None]) -> dict:
    """The paired difference a - b over seeds, one run per seed as the unit: n, mean, standard deviation, standard error and the 95 % confidence interval from the t distribution (n - 1 degrees of freedom). Subjects are never counted as units."""
    from scipy import stats

    d = np.array([x - y for x, y in zip(a, b, strict=True) if x is not None and y is not None], dtype=float)
    n = int(d.size)
    if n < 2:
        return {"n": n, "mean": float(d.mean()) if n else None, "sd": None, "se": None, "ci95": None}
    sd = float(d.std(ddof=1))
    se = sd / float(np.sqrt(n))
    t = float(stats.t.ppf(0.975, n - 1))
    return {"n": n, "mean": float(d.mean()), "sd": sd, "se": se, "ci95": [float(d.mean()) - t * se, float(d.mean()) + t * se]}


def resource_path_change(cfg: Config, denied: bool) -> float:
    """The change of the real state of a subject who is denied in every period (or granted in every period), from the declared constants alone: beta x the sum of (resources - 0.5) over the periods, with the resources moved by gain / loss and clipped at the floor and at 1 (the noise has mean zero). This is what the model fixes by construction; an experiment cannot discover it."""
    r, z = cfg.resources_start, 0.0
    for _ in range(cfg.periods):
        r = min(1.0, max(cfg.resource_floor, r + (-cfg.loss if denied else cfg.gain)))
        z += cfg.beta * (r - 0.5)
    return z


# ------------------------------------------------------------------------------------------------ PHASE 5 (the factors, arms, metrics and decomposition are fixed here, before the runs)
# One set of classifications is evaluated against four labels (process.LABELS) so that a change of the measured accuracy can be attributed: to the INPUT DISTRIBUTION (the share of subject-periods near the boundary), to the LABEL
# (the evaluation condition), to the TARGET (the state the institution moved), to the OBSERVATION (the sensor's conditions) or to the CLASSIFIER (its own parameters). What the data cannot separate is reported as the
# remainder, UNRESOLVED. The statistical unit is one run; every difference is paired over the seeds, 1-20 and replicated on 21-40. TE20 reads the arms of TE19 from the cached runs and runs nothing new.
FIXED = "classifier: signal rule, window 4, threshold 0; observation: signal noise 0.8"


def accuracy_decomposition(values_x: dict[str, list], values_c: dict[str, list]) -> dict:
    """The change of the pooled accuracy against the current label between an arm x and the control c, per seed, divided exactly (the midpoint form of the Oaxaca-Blinder identity) into
    COMPOSITION: sum over the distance-to-boundary bins of (the change of the bin's share of classified subject-periods) x (the mean accuracy of the bin): the change of the INPUT DISTRIBUTION, and
    WITHIN: sum of (the change of the accuracy within the bin) x (the mean share): the classifier, the observation and the label evaluated at the same distance from the boundary.
    The two sum to the change of the pooled accuracy (the identity is checked in a test)."""
    n = len(values_x["bin0_share"])
    comp, within, delta = [], [], []
    for i in range(n):
        c = w = d = 0.0
        ok = True
        for b in range(5):
            wx, wc = values_x[f"bin{b}_share"][i], values_c[f"bin{b}_share"][i]
            ax, ac = values_x[f"bin{b}_accuracy"][i], values_c[f"bin{b}_accuracy"][i]
            if wx is None or wc is None:
                ok = False
                break
            ax = ac if ax is None else ax
            ac = ax if ac is None else ac
            if ax is None:
                continue
            c += (wx - wc) * (ax + ac) / 2
            w += (ax - ac) * (wx + wc) / 2
            d += wx * ax - wc * ac
        comp.append(c if ok else None)
        within.append(w if ok else None)
        delta.append(d if ok else None)
    zero = [0.0] * n
    return {"change_of_pooled_accuracy": paired_summary(delta, zero), "composition_input_distribution": paired_summary(comp, zero), "within_distance": paired_summary(within, zero), "per_seed": {"delta": delta, "composition": comp, "within": within}}


def _decomposition_post(control: str, arms_of_interest: list[str] | None = None) -> Callable[[dict], dict]:
    def post(res: dict) -> dict:
        vals = {r["arm"]: r["values"] for r in res["arms"]}
        out = {}
        for name, v in vals.items():
            if name == control or (arms_of_interest and name not in arms_of_interest):
                continue
            d = accuracy_decomposition(v, vals[control])
            d.pop("per_seed")
            d["accuracy_change_by_label"] = {lab: paired_summary(v[f"accuracy_{lab}"], vals[control][f"accuracy_{lab}"]) for lab in ("initial", "current", "next", "counterfactual")}
            out[name] = d
        return {"control": control, "decomposition": out, "unresolved": "the within-distance part mixes the classifier's lag over its window, the observation and the label timing; the data do not separate them further"}

    return post


def te19_fixed_classifier() -> dict:
    ctl = "intervention with no feedback to the state (beta 0)"
    nz, vw, oc = "signal_sensor__noise_sigma", "signal_sensor__view_angle", "signal_sensor__occlusion_prob"
    named: dict[str, dict[str, Any]] = {
        "no institutional action on the resources (score off, allocation inert)": {"use_score": False, "gain": 0.0, "loss": 0.0},
        ctl: {"beta": 0.0},
        "feedback beta 0.03": {"beta": 0.03},
        "feedback beta 0.06 (the base)": {},
        "feedback beta 0.12": {"beta": 0.12},
        "feedback beta 0.24": {"beta": 0.24},
        "beta 0.06, observation view angle 40": {vw: 40.0},
        "beta 0.06, observation occlusion 0.25": {oc: 0.25},
        "beta 0, observation view angle 40": {"beta": 0.0, vw: 40.0},
        "beta 0.06, a different classifier (window 8)": {"window": 8},
        "beta 0, a different classifier (window 8)": {"beta": 0.0, "window": 8},
        "beta 0.06, a more precise observation (noise 0.4)": {nz: 0.4},
        "beta 0, a more precise observation (noise 0.4)": {"beta": 0.0, nz: 0.4},
    }
    arms, declared = _grid(NO_PROCESS, named, ctl)
    base = "feedback beta 0.06 (the base)"
    contrasts = [
        ("feedback 0.06 minus none: the accuracy against the label of the state at the start of the period (the model's own)", [(1.0, base), (-1.0, ctl)]),
        ("feedback 0.12 minus none", [(1.0, "feedback beta 0.12"), (-1.0, ctl)]),
        ("a more precise observation at beta 0 minus the control (a change of the observation, the target unchanged)", [(1.0, "beta 0, a more precise observation (noise 0.4)"), (-1.0, ctl)]),
        ("a different classifier at beta 0 minus the control (a change of the classifier, the target unchanged)", [(1.0, "beta 0, a different classifier (window 8)"), (-1.0, ctl)]),
        ("a change of the observation conditions at beta 0 (view angle 40) minus the control", [(1.0, "beta 0, observation view angle 40"), (-1.0, ctl)]),
    ]
    questions = [
        {"id": "H1", "question": "Can the institution's allocation change the state of the evaluated subjects?", "reads": "target_change_abs, state change, boundary mass, favourable share, with the classifier and the observation fixed", "model": "by construction through beta; the experiment measures how far, and how the distribution of the state changes"},
        {"id": "H2", "question": "Can the accuracy measured after the institution acts change without any change of the classifier?", "reads": "accuracy_current across beta with the classifier and the observation fixed; the decomposition into the input distribution and the within-distance part", "model": "the classifier is the same function; its inputs and its evaluation label depend on the state"},
    ]
    return _run2(
        {
            "id": "EXP-TE19",
            "title": "Fixed classifier, changing target",
            "question": f"With the classifier and the observation fixed ({FIXED}), only the feedback of resources to the state is changed. What happens to the state of the subjects, to the input the classifier reads, and to the accuracy measured against four labels, and how does that compare with changing the classifier or the observation instead?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "runner": _cached_run,
            "primary": ("accuracy_initial", "accuracy_current", "accuracy_next", "accuracy_counterfactual", "label_gap_current_minus_counterfactual", "target_change_abs", "boundary_mass_actual", "signal_abs_mean", "favourable_share_current", "state_gap_change"),
            "questions": questions,
            "contrasts": contrasts,
            "contrast_outcomes": ("accuracy_current", "accuracy_initial", "accuracy_counterfactual", "label_gap_current_minus_counterfactual", "target_change_abs", "boundary_mass_actual", "signal_abs_mean"),
            "post": _decomposition_post(ctl),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "beta (0, 0.03, 0.06, 0.12, 0.24); the observation (view angle, occlusion, noise); the classifier's window; no institutional action (score off and allocation inert)",
                "unchanged": f"NO_PROCESS otherwise; {FIXED}",
                "unit": "one run = one unit; paired over seeds; the accuracy is the mean over the last 8 periods of the per-period share correct among the classified (the summary's classification_correct)",
                "labels": "initial (z0>0, fixed), current (z at the start of the period, the model's), next (z after the period's own decision), counterfactual (the matched beta 0 state)",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
                "note": "the arms 'feedback beta 0.06' and 'beta 0.06 with the allocation active' are the same arm: in this model an institutional intervention changes the state only through beta",
            },
        }
    )


def te20_label_endogeneity() -> dict:
    """Reads the arms of TE19 that bear on the label question (the same configurations, taken from the cached runs: nothing is run again) and compares the labels of one set of decisions."""
    ctl = "intervention with no feedback to the state (beta 0)"
    nz, vw, oc = "signal_sensor__noise_sigma", "signal_sensor__view_angle", "signal_sensor__occlusion_prob"
    named: dict[str, dict[str, Any]] = {
        ctl: {"beta": 0.0},
        "feedback beta 0.03": {"beta": 0.03},
        "feedback beta 0.06 (the base)": {},
        "feedback beta 0.12": {"beta": 0.12},
        "feedback beta 0.24": {"beta": 0.24},
        "beta 0.06, observation view angle 40": {vw: 40.0},
        "beta 0.06, observation occlusion 0.25": {oc: 0.25},
        "beta 0.06, a more precise observation (noise 0.4)": {nz: 0.4},
    }
    arms, declared = _grid(NO_PROCESS, named, ctl)
    base = "feedback beta 0.06 (the base)"
    contrasts = [
        ("within the base run: accuracy against the current label minus against the counterfactual label (the same decisions)", [(1.0, base)]),
    ]
    return _run2(
        {
            "id": "EXP-TE20",
            "title": "Label endogeneity: the same decisions, four evaluation labels",
            "question": "When the label is generated from the state after the institution has acted, does the institution influence the condition under which its own classifications are called correct? The decisions are made once; they are evaluated against the label of the initial state (fixed), of the state at the start of the period (current), of the state after the period's own decision (next) and of the state without institutional effect (counterfactual).",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "runner": _cached_run,
            "primary": ("accuracy_initial", "accuracy_current", "accuracy_next", "accuracy_counterfactual", "label_gap_current_minus_counterfactual", "label_gap_current_minus_initial", "label_gap_next_minus_current", "label_shift_current_vs_initial", "label_shift_current_vs_counterfactual", "label_shift_next_vs_current", "favourable_share_current"),
            "contrasts": contrasts,
            "contrast_outcomes": ("label_gap_current_minus_counterfactual", "label_gap_current_minus_initial", "label_gap_next_minus_current"),
            "post": _decomposition_post(ctl),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "as the TE19 arms that vary beta and the observation; the labels are evaluation conditions applied to the same runs",
                "unchanged": f"NO_PROCESS otherwise; {FIXED}",
                "unit": "one run = one unit; paired over seeds; the label gaps are differences between two accuracies of the SAME decisions, so the classifier, the inputs and the population are identical in them",
                "reuse": "the runs of EXP-TE19 (cached): the contrasts and the arms duplicate none of its results",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
            },
        }
    )


def _matched_pairs_post(margin: float = 0.01) -> Callable[[dict], dict]:
    """Pairs of arms whose mean accuracy is EQUIVALENT (the 95 % interval of the paired difference lies inside +/- margin) and the differences of the concentration of the disadvantage between them. A pair whose accuracy is not shown equivalent is not listed: not detecting a difference of accuracy is not equivalence."""
    metrics = ("denial_rate_late_unfav", "denial_rate_late_fav", "state_change_unfav", "state_change_fav", "state_gap_change", "resources_end_unfav", "lost_opportunities_per_unfav", "lost_opportunities_per_fav")

    def post(res: dict) -> dict:
        vals = {r["arm"]: r["values"] for r in res["arms"]}
        names = list(vals)
        pairs = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                acc = paired_summary(vals[a]["accuracy_current"], vals[b]["accuracy_current"])
                if acc["ci95"] is None:
                    continue
                equivalent = acc["ci95"][0] > -margin and acc["ci95"][1] < margin
                if not equivalent:
                    continue
                diffs = {m: paired_summary(vals[a][m], vals[b][m]) for m in metrics}
                differ = [m for m, d in diffs.items() if d["ci95"] is not None and (d["ci95"][0] > 0 or d["ci95"][1] < 0)]
                pairs.append({"a": a, "b": b, "accuracy_difference": acc, "metrics_that_differ": differ, "differences": diffs})
        return {"equivalence_margin": margin, "rule": "equivalent if the 95% CI of the paired difference of accuracy_current lies inside +/- margin; a difference is listed as present if its 95% CI excludes 0", "pairs": pairs, "n_pairs_compared": len(names) * (len(names) - 1) // 2, "n_equivalent_pairs": len(pairs)}

    return post


def te21_concentration() -> dict:
    nz = "signal_sensor__noise_sigma"
    ctl = "noisy classifier, the base"
    named: dict[str, dict[str, Any]] = {
        ctl: {},
        "threshold +0.2": {"tau_a": 0.2},
        "threshold -0.2": {"tau_a": -0.2},
        "no binding constraint": {"lock_after": None},
        "allocation gain = loss = 0.24": {"gain": 0.24, "loss": 0.24},
        "initial state shifted +0.5": {"z_shift": 0.5},
        "initial state shifted -0.5": {"z_shift": -0.5},
        "resource floor 0.3": {"resource_floor": 0.3},
        "denial cap 6": {"denial_cap": 6},
        "support to the denied 0.06": {"support_rule": "denied", "support_amount": 0.06},
        "support to the low score 0.12, capacity 25%": {"support_rule": "low_score", "support_amount": 0.12, "support_capacity": 0.25},
        "accurate classifier, no feedback (beta 0)": {nz: 0.05, "beta": 0.0},
        "accurate classifier": {nz: 0.05},
        "feedback beta 0.12": {"beta": 0.12},
        "feedback beta 0.03": {"beta": 0.03},
    }
    arms, declared = _grid(NO_PROCESS, named, ctl)
    return _run2(
        {
            "id": "EXP-TE21",
            "title": "Distributional concentration at the same mean accuracy",
            "question": "Which institutional conditions have the same mean classification accuracy (shown equivalent within +/-0.01, not merely not different) and yet distribute the disadvantage differently between the groups favourable and not favourable at the start, in denial, resources, change of state and lost opportunities?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "runner": _cached_run,
            "primary": ("accuracy_current", "accuracy_current_unfav", "accuracy_current_fav", "denial_rate_late_unfav", "denial_rate_late_fav", "state_change_unfav", "state_change_fav", "state_gap_change", "resources_end_unfav", "resources_end_fav", "lost_opportunities_per_unfav", "lost_opportunities_per_fav"),
            "post": _matched_pairs_post(),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "the threshold, the constraint, the allocation, the initial state, the feedback, a floor, a cap, support, the observation; each alone, so that the pairs are conditions that differ in one respect",
                "unchanged": "NO_PROCESS otherwise",
                "unit": "one run = one unit; paired over seeds; the group metrics are means over the subjects of the group within a run",
                "matching": "accuracy_current equivalent within +/-0.01 (95% CI of the paired difference inside the margin), fixed before the run",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
            },
        }
    )


def te22_reachability() -> dict:
    nz = "signal_sensor__noise_sigma"
    ctl = "no support"
    sup = {"support_amount": 0.12}
    named: dict[str, dict[str, Any]] = {
        ctl: {},
        "formal guarantee, delivered automatically to the low score": {"support_rule": "low_score", **sup},
        "formal guarantee, on request (everyone eligible applies)": {"support_rule": "on_request", "support_apply_prob": 1.0, **sup},
        "formal guarantee, on request (half of the eligible apply each period)": {"support_rule": "on_request", "support_apply_prob": 0.5, **sup},
        "formal guarantee, on request (one in five apply)": {"support_rule": "on_request", "support_apply_prob": 0.2, **sup},
        "formal guarantee, on request, applicants need resources 0.1": {"support_rule": "on_request", "support_apply_prob": 1.0, "apply_min_resources": 0.1, **sup},
        "formal guarantee, on request, applicants need resources 0.3": {"support_rule": "on_request", "support_apply_prob": 1.0, "apply_min_resources": 0.3, **sup},
        "on request (half apply), capacity 25%": {"support_rule": "on_request", "support_apply_prob": 0.5, "support_capacity": 0.25, **sup},
        "resource floor 0.3 (no application)": {"resource_floor": 0.3},
        "denial cap 3 (no application)": {"denial_cap": 3},
        "access kept pending a correction (the process on)": {"audit_every": 2, "request_delay": 1, "approval_delay": 6, "release_mode": "after_approval", "release_delay": 0, "interim_access": True},
        "the process alone, without it": {"audit_every": 2, "request_delay": 1, "approval_delay": 6, "release_mode": "after_approval", "release_delay": 0},
        "accurate classifier, delivered automatically": {nz: 0.05, "support_rule": "low_score", **sup},
        "accurate classifier, on request (half apply)": {nz: 0.05, "support_rule": "on_request", "support_apply_prob": 0.5, **sup},
    }
    arms, declared = _grid(NO_PROCESS, named, ctl)
    contrasts = [
        ("on request (everyone applies) minus delivered automatically: the same formal guarantee", [(1.0, "formal guarantee, on request (everyone eligible applies)"), (-1.0, "formal guarantee, delivered automatically to the low score")]),
        ("on request (half apply) minus delivered automatically", [(1.0, "formal guarantee, on request (half of the eligible apply each period)"), (-1.0, "formal guarantee, delivered automatically to the low score")]),
        ("applicants need resources 0.3 minus applicants need none (everyone applies)", [(1.0, "formal guarantee, on request, applicants need resources 0.3"), (-1.0, "formal guarantee, on request (everyone eligible applies)")]),
        ("access kept pending a correction minus the process alone", [(1.0, "access kept pending a correction (the process on)"), (-1.0, "the process alone, without it")]),
    ]
    return _run2(
        {
            "id": "EXP-TE22",
            "title": "A formal guarantee and the reach of it",
            "question": "The same formal support guarantee (the amount and the eligibility are the same) is delivered automatically, or has to be applied for with different chances of applying and with a requirement of resources for applying, or is limited by a capacity. How much of the guarantee reaches the subjects, and what does the reach change in their state? Floor, cap and access pending a correction are varied separately.",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "runner": _cached_run,
            "primary": ("support_utilisation", "unfav_ever_eligible", "unfav_eligible_never_served", "time_to_first_support", "support_units_per_subject", "state_change_unfav", "state_change_fav", "state_gap_change", "denial_rate_late_unfav", "resources_end_unfav", "accuracy_current"),
            "contrasts": contrasts,
            "contrast_outcomes": ("support_utilisation", "unfav_eligible_never_served", "state_change_unfav", "state_gap_change", "support_units_per_subject"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "the way the same support is delivered (automatically; on request with a chance of applying; with a resource requirement for applying; with a capacity), and, separately, a floor, a cap and access pending a correction",
                "unchanged": "NO_PROCESS otherwise (the process arms add an audit every 2, request delay 1, approval delay 6 and the release at the approval)",
                "unit": "one run = one unit; paired over seeds",
                "unresolved": "the effective reachability of a real guarantee (information, trust, language, representation) is NOT measured. The model gives the use of the guarantee (support_utilisation, never served, time to first support): a proxy, kept apart from reachability",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
            },
        }
    )


def te23_ablation() -> dict:
    ctl = "the base institution"
    named: dict[str, dict[str, Any]] = {
        ctl: {},
        "no feedback to the state (beta 0)": {"beta": 0.0},
        "allocation inert: access does not change the resources (gain = loss = 0)": {"gain": 0.0, "loss": 0.0},
        "no score gate: access by lottery": {"use_score": False},
        "nothing adopted: the score never moves": {"confidence_floor": 2.0},
        "no binding constraint": {"lock_after": None},
        "observation feedback on (a denied subject is observed worse, gamma 0.5)": {"gamma": 0.5},
        "beta 0 and allocation inert together (to read the interaction)": {"beta": 0.0, "gain": 0.0, "loss": 0.0},
        "allocation inert with a stronger feedback (beta 0.12)": {"gain": 0.0, "loss": 0.0, "beta": 0.12},
    }
    arms, declared = _grid(NO_PROCESS, named, ctl)
    contrasts = [
        ("the score changes and the allocation does not: allocation inert minus the base", [(1.0, "allocation inert: access does not change the resources (gain = loss = 0)"), (-1.0, ctl)]),
        ("the allocation changes the state: the base minus beta 0", [(1.0, ctl), (-1.0, "no feedback to the state (beta 0)")]),
        ("interaction of the feedback and the allocation", [(1.0, "beta 0 and allocation inert together (to read the interaction)"), (-1.0, "no feedback to the state (beta 0)"), (-1.0, "allocation inert: access does not change the resources (gain = loss = 0)"), (1.0, ctl)]),
    ]
    return _run2(
        {
            "id": "EXP-TE23",
            "title": "Feedback ablation: which mechanism returns the institution's action to the evaluated state",
            "question": "Each mechanism that returns an institutional action to the state, the score or the observation is disabled alone: the feedback of resources to the state, the allocation, the score gate, the adoption, the constraint, and the observation feedback is enabled. What changes in the state, in the accuracy against the four labels, in the gap between the groups and in the resources?",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "runner": _cached_run,
            "primary": ("accuracy_current", "accuracy_counterfactual", "label_gap_current_minus_counterfactual", "target_change_abs", "state_change_unfav", "state_change_fav", "state_gap_change", "resources_end_unfav", "denial_rate_late_unfav", "boundary_mass_actual"),
            "contrasts": contrasts,
            "contrast_outcomes": ("accuracy_current", "label_gap_current_minus_counterfactual", "target_change_abs", "state_gap_change", "resources_end_unfav"),
            "post": _decomposition_post(ctl),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda x: _no_idle_arm(x, ctl)},
            "protocol": {
                "changed": "one mechanism per arm (the two double arms are named as such and are there to read an interaction)",
                "unchanged": "NO_PROCESS otherwise",
                "unit": "one run = one unit; paired over seeds",
                "reuse": "several of these arms have the configuration of arms of EXP-TE16 and EXP-TE17; they are cached runs where the same process computes both, and their earlier results are not changed",
                "seeds": list(SEEDS),
                "failure": "an arm identical to the control",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE13: parameter sensitivity (one factor at a time, ranges fixed above)
def te13_sensitivity() -> dict:
    named: dict[str, dict[str, Any]] = {"base (P0)": {}}
    for k, vals in PARAMETER_RANGES.items():
        key = k.replace(".", "__")
        base_v = getattr(getattr(P0, k.split(".")[0]), k.split(".")[1]) if "." in k else getattr(P0, k)
        for v in vals:
            if v == base_v:
                continue
            named[f"{k}={v}"] = {key: v}
    arms, declared = _grid(P0, named, "base (P0)")
    return _run2(
        {
            "id": "EXP-TE13",
            "title": "Parameter sensitivity, one factor at a time over fixed ranges",
            "question": "How far do the primary metrics move when each setting of the institution is changed alone across the range fixed in advance? Which are insensitive?",
            "control": "base (P0)",
            "arms": arms,
            "declared": declared,
            "primary": PRIMARY2,
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, "base (P0)"), "no wrongful denial in the base": lambda a: float(np.nanmean(a["base (P0)"]["values"]["lost_opportunities_favourable_per_subject"])) < 0.5},
            "protocol": {
                "changed": "one setting at a time within PARAMETER_RANGES",
                "ranges": {k: list(v) for k, v in PARAMETER_RANGES.items()},
                "unchanged": "P0 otherwise",
                "seeds": list(SEEDS),
                "failure": "no wrongful denial in the base",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE14: three-factor interaction
def te14_interaction() -> dict:
    lv = {"noise": ("signal_sensor__noise_sigma", 0.4, 1.6), "tau": ("tau_a", -0.2, 0.2), "lock": ("lock_after", 2, 8)}
    named: dict[str, dict[str, Any]] = {}
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                named[f"noise {lv['noise'][1 + a]} / tau {lv['tau'][1 + b]} / lock {lv['lock'][1 + c]}"] = {lv["noise"][0]: lv["noise"][1 + a], lv["tau"][0]: lv["tau"][1 + b], lv["lock"][0]: lv["lock"][1 + c]}
    names = list(named)
    ctl = names[0]
    arms, declared = _grid(P0, named, ctl)

    def eff(axis: int) -> list[tuple[float, str]]:
        return [((0.25 if (i >> (2 - axis)) & 1 else -0.25), names[i]) for i in range(8)]

    prod = lambda ax: [(0.25 * float(np.prod([(1.0 if (i >> (2 - a)) & 1 else -1.0) for a in ax])), names[i]) for i in range(8)]  # noqa: E731
    contrasts = [
        ("main effect of signal noise (high minus low, averaged over the other two)", eff(0)),
        ("main effect of the threshold tau_a (high minus low)", eff(1)),
        ("main effect of lock_after (high minus low)", eff(2)),
        ("interaction noise x tau_a", prod((0, 1))),
        ("interaction noise x lock_after", prod((0, 2))),
        ("interaction tau_a x lock_after", prod((1, 2))),
        ("three-way interaction", prod((0, 1, 2))),
    ]
    return _run2(
        {
            "id": "EXP-TE14",
            "title": "Three-factor interaction: sensor noise, the score's threshold, the strength of the constraint",
            "question": "In a 2x2x2 factorial, do the effects of the factors on persistent constraint and on the denial rate add, or do they interact? (Each contrast is the signed sum over the eight cells divided by 4: a main effect is the mean difference high minus low, an interaction the corresponding mean of the signed cells.)",
            "control": ctl,
            "arms": arms,
            "declared": declared,
            "primary": ("denial_rate_late_fav", "persistent_constraint", "lost_opportunities_per_fav"),
            "contrasts": contrasts,
            "contrast_outcomes": ("denial_rate_late_fav", "persistent_constraint", "lost_opportunities_per_fav"),
            "failure_conditions": {"an arm changed nothing in any seed (its factor was not operative)": lambda a: _no_idle_arm(a, ctl), "no wrongful denial in the first cell": lambda a: False},
            "protocol": {"changed": "signal noise (0.4, 1.6) x tau_a (-0.2, 0.2) x lock_after (2, 8)", "unchanged": "P0 otherwise", "seeds": list(SEEDS), "failure": "none declared"},
        }
    )


REGISTRY2: dict[str, Callable[[], dict]] = {
    "EXP-TE07-release": te07_release,
    "EXP-TE07-correction": te07_correction,
    "EXP-TE08": te08_timing,
    "EXP-TE09": te09_ablation,
    "EXP-TE10": te10_causal,
    "EXP-TE11": te11_recoverability,
    "EXP-TE12": te12_appeal,
    "EXP-TE12-release": te12_release,
    "EXP-TE13": te13_sensitivity,
    "EXP-TE14": te14_interaction,
    "EXP-TE15": te15_separation,
    "EXP-TE16": te16_complement,
    "EXP-TE17": te17_decomposition,
    "EXP-TE18": te18_guarantees,
    "EXP-TE19": te19_fixed_classifier,
    "EXP-TE20": te20_label_endogeneity,
    "EXP-TE21": te21_concentration,
    "EXP-TE22": te22_reachability,
    "EXP-TE23": te23_ablation,
}


def run_all2() -> dict:
    clear_run_cache()
    try:
        return {"engine": "truth_error/2", "experiments": {k: f() for k, f in REGISTRY2.items()}}
    finally:
        clear_run_cache()


__all__ = ["REGISTRY2", "run_all2", "P0", "NO_PROCESS", "PRIMARY2", "PARAMETER_RANGES", "SEEDS2", "_diff"]
