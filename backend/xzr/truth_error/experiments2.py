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
from collections.abc import Callable
from typing import Any

import numpy as np

from .experiments import BASE, SEEDS, _diff, _paired, _run_experiment
from .institution import Config, digest, run
from .process import METRICS, OBS_LATE, recoverability

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
}


def run_all2() -> dict:
    return {"engine": "truth_error/2", "experiments": {k: f() for k, f in REGISTRY2.items()}}


__all__ = ["REGISTRY2", "run_all2", "P0", "NO_PROCESS", "PRIMARY2", "PARAMETER_RANGES", "SEEDS2", "_diff"]
