"""EXP-TE01 .. TE06: the pre-registered comparisons of TRUTH-ERROR. Each experiment fixes its arms, its seeds, its outcomes and its failure conditions HERE, before any run; a run only fills in the results.

Every arm is the control with exactly the listed changes (checked: the changes are computed from the configurations and must equal the declared ones), and every arm shares all random draws with the control
(independent streams, ``institution.run``), so the paired difference is the effect of the change and of nothing else. Results are descriptive over a fixed list of seeds: a mean, a standard error, and in how many seeds
the arm differs from the control in each direction. An effect is called detected when the paired mean differs from zero by more than two standard errors; a not-detected effect is a result and is kept.
SYNTHETIC ONLY: nothing here says how a real institution behaves."""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from .institution import Config, digest, run
from .pose import SensorConfig

SEEDS = tuple(range(1, 21))
BASE = Config(n=120, periods=40)
OUTCOMES = (
    "measurement_correct",
    "classification_correct",
    "warrant_supported",
    "wrongful_adverse_adopted",
    "access",
    "access_favourable",
    "access_unfavourable",
    "lost_opportunities_favourable_per_subject",
    "resources_mean",
    "locked_fraction",
    "score_mean",
    "warrant_support_wrong",
    "denial_persistence_favourable",
    "self_fulfilled_share_of_early_denied_favourable",
)
DEFAULT_PRIMARY = ("classification_correct", "access", "lost_opportunities_favourable_per_subject")
LIMITS = "Synthetic subjects and institutions; constants are this implementation's declared assumptions; descriptive over 20 seeds; a result holds for these assumptions only and says nothing about a real institution, person or law."


def _diff(a: Config, b: Config) -> dict[str, Any]:
    da, db = dataclasses.asdict(a), dataclasses.asdict(b)
    return {k: db[k] for k in db if da[k] != db[k]}


def _stat(x: list[float]) -> dict:
    v = np.array([e for e in x if e is not None and e == e], dtype=float)
    if v.size == 0:
        return {"mean": None, "sd": None, "se": None, "n": 0}
    sd = float(v.std(ddof=1)) if v.size > 1 else 0.0
    return {"mean": float(v.mean()), "sd": sd, "se": sd / float(np.sqrt(v.size)), "n": int(v.size)}


def _paired(arm: list[float | None], ctl: list[float | None]) -> dict:
    d = np.array(
        [a - c for a, c in zip(arm, ctl, strict=True) if a is not None and c is not None and a == a and c == c], dtype=float
    )
    if d.size == 0:
        return {"mean": None, "se": None, "up": 0, "down": 0, "same": 0, "detected": None}
    se = float(d.std(ddof=1) / np.sqrt(d.size)) if d.size > 1 else 0.0
    m = float(d.mean())
    return {
        "mean": m,
        "se": se,
        "up": int((d > 1e-12).sum()),
        "down": int((d < -1e-12).sum()),
        "same": int((np.abs(d) <= 1e-12).sum()),
        "detected": bool(abs(m) > 2 * se and abs(m) > 1e-9),
    }


def _early_late(r: dict, key: str) -> tuple[float | None, float | None]:
    s = [v for v in r["series"][key] if v is not None]
    if len(s) < 14:
        return None, None
    return float(np.mean(s[4:11])), float(np.mean(s[-8:]))


def _arm_results(cfgs: dict[str, Config], seeds: tuple[int, ...], extra) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, cfg in cfgs.items():
        runs = [run(dataclasses.replace(cfg, seed=s)) for s in seeds]
        res = {k: [r["summary"].get(k) for r in runs] for k in OUTCOMES}
        for k, fn in extra.items():
            res[k] = [fn(r) for r in runs]
        out[name] = {"runs": runs, "values": res, "target_digests": [r["target_state_digest"] for r in runs]}
    return out


def _run_experiment(spec: dict, seeds: tuple[int, ...] | None = None) -> dict:
    seeds = seeds or SEEDS
    cfgs: dict[str, Config] = spec["arms"]
    control = spec["control"]
    extra = spec.get("extra", {})
    arms = _arm_results(cfgs, seeds, extra)
    outcomes = list(OUTCOMES) + list(extra)
    rows = []
    for name, cfg in cfgs.items():
        changed = _diff(cfgs[control], cfg)
        declared = spec["declared"][name]
        assert set(changed) == set(declared), (
            f"{spec['id']} arm {name}: changed {sorted(changed)} but declared {sorted(declared)}"
        )
        vals = arms[name]["values"]
        row = {
            "arm": name,
            "changed_vs_control": {k: _plain(v) for k, v in changed.items()},
            "mean": {k: _stat(vals[k]) for k in outcomes},
            "result_digest_seed1": arms[name]["runs"][0]["result_digest"],
            "target_state_identical_to_control_in_every_seed": arms[name]["target_digests"] == arms[control]["target_digests"],
        }
        if name != control:
            row["paired_vs_control"] = {k: _paired(vals[k], arms[control]["values"][k]) for k in outcomes}
        if spec.get("keep_values"):
            row["values"] = {k: vals[k] for k in outcomes}  # per seed, for contrasts between any two arms (phase 2)
        rows.append(row)
    primary = list(spec.get("primary", DEFAULT_PRIMARY))
    negatives = [
        f"{r['arm']}: {k} not detected (paired mean {r['paired_vs_control'][k]['mean']:+.3f} +/- {r['paired_vs_control'][k]['se']:.3f})"
        for r in rows
        if r["arm"] != control
        for k in primary
        if k in r["paired_vs_control"]
        and r["paired_vs_control"][k]["mean"] is not None
        and not r["paired_vs_control"][k]["detected"]
    ]
    failures = {}
    for label, fn in spec["failure_conditions"].items():
        failures[label] = bool(fn(arms))
    return {
        "id": spec["id"],
        "title": spec["title"],
        "question": spec["question"],
        "control": control,
        "control_config": cfgs[control].asdict(),
        "arm_configs": {k: c.asdict() for k, c in cfgs.items()},
        "arms": rows,
        "seeds": list(seeds),
        "periods": BASE.periods,
        "n_subjects": BASE.n,
        "observation_range": {
            "periods": BASE.periods,
            "classification_window": BASE.window,
            "sensors": ["pose (yaw, pitch, roll)", "signal (informative about the reference state)"],
        },
        "outcomes": outcomes,
        "primary_outcomes": primary,
        "negative_results": negatives,
        "failure_conditions": failures,
        "invalid_if_any_failure_condition": any(failures.values()),
        "limits": LIMITS,
        "protocol_digest": digest(spec["protocol"]),
        "protocol": spec["protocol"],
    }


def _plain(v: Any) -> Any:
    return dataclasses.asdict(v) if dataclasses.is_dataclass(v) and not isinstance(v, type) else v


def _mean(arms: dict, name: str, key: str) -> float:
    return float(np.nanmean([v for v in arms[name]["values"][key] if v is not None]))


def _sensor(view: float = 0.0, noise: float = 1.5, bias=(0.0, 0.0, 0.0), occ: float = 0.0) -> SensorConfig:
    return SensorConfig(view_angle=view, noise_sigma=noise, bias=bias, occlusion_prob=occ, occlusion_length=2)


# ------------------------------------------------------------------------------------------------ TE01: sensor error
def te01(use_score: bool, beta: float = 0.0) -> dict:
    ctl = dataclasses.replace(BASE, use_score=use_score, beta=beta)
    mk = lambda pose, sig: dataclasses.replace(ctl, pose_sensor=pose, signal_sensor=sig)  # noqa: E731
    arms = {
        "reference (no error)": ctl,
        "viewing angle 40": mk(_sensor(view=40), SensorConfig(view_angle=40, noise_sigma=0.8)),
        "occlusion 0.25": mk(_sensor(occ=0.25), SensorConfig(noise_sigma=0.8, occlusion_prob=0.25)),
        "noise x4": mk(_sensor(noise=6.0), SensorConfig(noise_sigma=3.2)),
        "calibration bias": mk(_sensor(bias=(8.0, 4.0, 3.0)), SensorConfig(noise_sigma=0.8, bias=(0.7, 0.0, 0.0))),
    }
    ps, ss = "pose_sensor", "signal_sensor"
    declared = {
        "reference (no error)": [],
        "viewing angle 40": [ps, ss],
        "occlusion 0.25": [ps, ss],
        "noise x4": [ps, ss],
        "calibration bias": [ps, ss],
    }
    return _run_experiment(
        {
            "id": "EXP-TE01" + ("-scored" if use_score else "-unscored") + ("-transforming" if beta else ""),
            "title": "Sensor Error"
            + (
                " (the score is used" + (", and resources change the subject's real state)" if beta else ")")
                if use_score
                else " (the score is not used: the sensor's effect alone)"
            ),
            "question": "When only the observation conditions change (angle, occlusion, noise, calibration), what changes in the correctness of the measurement, of the classification and of the warrant, and does the subject's real state change?",
            "control": "reference (no error)",
            "arms": arms,
            "declared": declared,
            "failure_conditions": {
                "the reference sensor is not accurate (measurement correct < 0.95)": lambda a: (
                    _mean(a, "reference (no error)", "measurement_correct") < 0.95
                )
            },
            "protocol": {
                "changed": "observation conditions only (pose and signal sensors)",
                "unchanged": "population, classifier (signal_rule), threshold, score use="
                + str(use_score)
                + ", beta="
                + str(beta),
                "seeds": list(SEEDS),
                "failure": "reference sensor accuracy",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE02: false classification
def te02() -> dict:
    ctl = dataclasses.replace(BASE, classifier="signal_rule")
    arms = {
        "valid rule (signal)": ctl,
        "invalid rule (head pose)": dataclasses.replace(ctl, classifier="pose_rule"),
        "chance rule (random)": dataclasses.replace(ctl, classifier="random_rule"),
        "no score (lottery)": dataclasses.replace(ctl, use_score=False),
    }
    declared = {
        "valid rule (signal)": [],
        "invalid rule (head pose)": ["classifier"],
        "chance rule (random)": ["classifier"],
        "no score (lottery)": ["use_score"],
    }
    return _run_experiment(
        {
            "id": "EXP-TE02",
            "title": "False Classification",
            "question": "A classification rule that is invalid by construction (head yaw has no link to the verification label) is adopted: how far is its error separated from what the institution then does to subjects?",
            "control": "valid rule (signal)",
            "arms": arms,
            "declared": declared,
            "failure_conditions": {
                "the valid rule is not better than chance (classification correct < 0.7)": lambda a: (
                    _mean(a, "valid rule (signal)", "classification_correct") < 0.7
                )
            },
            "protocol": {
                "changed": "the classification rule (and, for the last arm, whether a score is used)",
                "unchanged": "sensors, threshold 0, acceptance, resources",
                "seeds": list(SEEDS),
                "failure": "valid rule not above chance",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE03: score threshold
def te03() -> dict:
    ctl = dataclasses.replace(BASE, tau_a=0.0)
    arms = {"threshold 0.0": ctl}
    for tau in (-0.4, -0.15, 0.15, 0.4):
        arms[f"threshold {tau:+.2f}"] = dataclasses.replace(ctl, tau_a=tau)
    arms["no score (lottery)"] = dataclasses.replace(ctl, use_score=False)
    declared = {k: ([] if k == "threshold 0.0" else ["use_score"] if k.startswith("no score") else ["tau_a"]) for k in arms}
    return _run_experiment(
        {
            "id": "EXP-TE03",
            "title": "Score Threshold",
            "question": "For the SAME classification results, how does the threshold alone change who can act (access), and what is lost?",
            "control": "threshold 0.0",
            "arms": arms,
            "declared": declared,
            "failure_conditions": {
                "the classification is not identical across thresholds": lambda a: (
                    len({round(_mean(a, k, "classification_correct"), 9) for k in a if not k.startswith("no score")}) != 1
                )
            },
            "protocol": {
                "changed": "the threshold of the gate (tau_a)",
                "unchanged": "sensors, classifier, acceptance, score update",
                "seeds": list(SEEDS),
                "failure": "classification differs between thresholds",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE04: correction delay
def te04(reentry: float = 0.0) -> dict:
    ctl = dataclasses.replace(BASE, lock_after=4, release_after=3, reentry_support=reentry)
    arms = {"no correction": ctl}
    for label, at in (("correction at 10 (immediate)", 10), ("correction at 20 (delayed)", 20), ("correction at 30 (late)", 30)):
        arms[label] = dataclasses.replace(ctl, correct_at=at)
    arms["correction at 10, constraint cleared"] = dataclasses.replace(ctl, correct_at=10, correction_clears_lock=True)
    declared = {
        k: ([] if k == "no correction" else ["correct_at", "correction_clears_lock"] if "cleared" in k else ["correct_at"])
        for k in arms
    }
    extra = {
        "opportunities_lost_all_periods_mean": lambda r: r["summary"]["opportunities_lost_mean"],
        "still_denied_after_correction": lambda r: r["summary"]["still_denied_after_correction_share_of_corrected"],
        "score_recovered_of_corrected": lambda r: r["summary"]["score_recovered_share_of_corrected"],
        "resources_of_corrected": lambda r: r["summary"]["resources_of_corrected_mean"],
    }
    return _run_experiment(
        {
            "id": "EXP-TE04" + ("-support" if reentry else ""),
            "title": "Correction Delay" + (" (with re-entry support)" if reentry else ""),
            "question": "A wrongful adverse judgement is retracted at different times: how far does the score recover, and how far do the resources and opportunities that were lost, and a binding constraint, recover?",
            "control": "no correction",
            "arms": arms,
            "declared": declared,
            "extra": extra,
            "primary": (
                "lost_opportunities_favourable_per_subject",
                "still_denied_after_correction",
                "score_recovered_of_corrected",
                "resources_of_corrected",
            ),
            "failure_conditions": {
                "no wrongful denial occurs in the control (nothing to correct)": lambda a: (
                    _mean(a, "no correction", "lost_opportunities_favourable_per_subject") < 0.5
                )
            },
            "protocol": {
                "changed": "the period of the correction (none, 10, 20, 30)",
                "unchanged": "everything else, a binding constraint after 4 denied periods released after 3 periods at or above the threshold, reentry_support="
                + str(reentry),
                "seeds": list(SEEDS),
                "failure": "no wrongful denial in the control",
            },
        }
    )


def te04_release() -> dict:
    ctl = dataclasses.replace(BASE, lock_after=4, release_after=3, correct_at=10)
    arms = {"released after 3 periods at or above the threshold": ctl}
    for r in (1, 8, 999):
        arms[f"released after {r} periods" if r < 999 else "never released (by score alone)"] = dataclasses.replace(
            ctl, release_after=r
        )
    declared = {k: ([] if k.startswith("released after 3") else ["release_after"]) for k in arms}
    extra = {
        "still_denied_after_correction": lambda r: r["summary"]["still_denied_after_correction_share_of_corrected"],
        "score_recovered_of_corrected": lambda r: r["summary"]["score_recovered_share_of_corrected"],
    }
    return _run_experiment(
        {
            "id": "EXP-TE04-release",
            "title": "Release condition of a binding constraint (the correction is at period 10)",
            "question": "After a correction restores the score, how long does a constraint that was set by earlier denials last, as a function of its release condition?",
            "control": "released after 3 periods at or above the threshold",
            "arms": arms,
            "declared": declared,
            "extra": extra,
            "primary": ("locked_fraction", "still_denied_after_correction"),
            "failure_conditions": {
                "no constraint is set in the control": lambda a: (
                    _mean(a, "released after 3 periods at or above the threshold", "locked_fraction") <= 0.0
                )
            },
            "protocol": {
                "changed": "release_after, the number of consecutive periods at or above the threshold that release a binding constraint",
                "unchanged": "everything else; correction at 10",
                "seeds": list(SEEDS),
                "failure": "no constraint in the control",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE05: cross-domain transfer
def te05(tau_b: float) -> dict:
    ctl = dataclasses.replace(BASE, tau_b=tau_b, correct_at=20)
    inv = dataclasses.replace(ctl, classifier="pose_rule")
    arms = {
        "valid rule, no transfer": ctl,
        "valid rule, transfer, correction not propagated": dataclasses.replace(ctl, transfer_at=15),
        "valid rule, transfer, correction propagated": dataclasses.replace(ctl, transfer_at=15, propagate_correction=True),
        "invalid rule, transfer, correction not propagated": dataclasses.replace(inv, transfer_at=15),
        "invalid rule, transfer, correction propagated": dataclasses.replace(inv, transfer_at=15, propagate_correction=True),
        "invalid rule, transfer, correction propagated 8 periods late": dataclasses.replace(
            inv, transfer_at=15, propagate_correction=True, propagation_delay=8
        ),
        "invalid rule, transfer at weight 0.3, correction not propagated": dataclasses.replace(
            inv, transfer_at=15, transfer_weight=0.3
        ),
    }
    declared = {
        "valid rule, no transfer": [],
        "valid rule, transfer, correction not propagated": ["transfer_at"],
        "valid rule, transfer, correction propagated": ["transfer_at", "propagate_correction"],
        "invalid rule, transfer, correction not propagated": ["classifier", "transfer_at"],
        "invalid rule, transfer, correction propagated": ["classifier", "transfer_at", "propagate_correction"],
        "invalid rule, transfer, correction propagated 8 periods late": [
            "classifier",
            "transfer_at",
            "propagate_correction",
            "propagation_delay",
        ],
        "invalid rule, transfer at weight 0.3, correction not propagated": ["classifier", "transfer_at", "transfer_weight"],
    }
    extra = {
        "b_evidential_accuracy": lambda r: r["summary"]["b_evidential_accuracy_of_transferred_score"],
        "b_denied_though_favourable": lambda r: r["summary"]["b_denied_though_favourable"],
        "b_access": lambda r: r["summary"]["b_access"],
    }
    return _run_experiment(
        {
            "id": f"EXP-TE05-tauB{tau_b:+.2f}",
            "title": f"Cross-Domain Transfer (institution B threshold {tau_b:+.2f})",
            "question": "A score is sent to a second institution whose gate applies it: is the evidence the original judgement carried separate from the force it has at B? Compared for a valid and an invalid original rule, with and without the correction reaching B.",
            "control": "valid rule, no transfer",
            "arms": arms,
            "declared": declared,
            "extra": extra,
            "primary": ("b_evidential_accuracy", "b_denied_though_favourable", "b_access"),
            "failure_conditions": {
                "the valid rule's transferred score carries no information (evidential accuracy <= 0.5)": lambda a: (
                    _mean(a, "valid rule, transfer, correction not propagated", "b_evidential_accuracy") <= 0.5
                )
            },
            "protocol": {
                "changed": "the original rule (valid or invalid), transfer of the score to B (time, weight, correction propagation and its delay)",
                "unchanged": "institution A's other settings, sensors, the correction at period 20",
                "seeds": list(SEEDS),
                "failure": "no evidence in the valid rule's transferred score",
            },
        }
    )


# ------------------------------------------------------------------------------------------------ TE06: self-reinforcing scoring
def te06() -> dict:
    ctl = dataclasses.replace(BASE, gamma=0.0, beta=0.0, lock_after=None)
    arms = {"no feedback": ctl}
    for g, b, lk in (
        (1.5, 0.0, None),
        (4.0, 0.0, None),
        (0.0, 0.03, None),
        (0.0, 0.06, None),
        (0.0, 0.12, None),
        (0.0, 0.4, None),
        (4.0, 0.06, None),
        (1.5, 0.4, 4),
        (0.0, 0.0, 4),
    ):
        arms[f"gamma {g}, beta {b}, lock {lk}"] = dataclasses.replace(ctl, gamma=g, beta=b, lock_after=lk)
    declared: dict[str, list[str]] = {"no feedback": []}
    for name, c in arms.items():
        if name != "no feedback":
            declared[name] = [k for k in ("gamma", "beta", "lock_after") if getattr(c, k) != getattr(ctl, k)]
    extra = {
        "denial_persistence_of_early_denied": lambda r: r["summary"]["denial_persistence_favourable"],
        "denial_late_if_not_denied_early": lambda r: r["summary"]["denial_late_if_not_denied_early_favourable"],
        "access_fav_early": lambda r: _early_late(r, "access_fav")[0],
        "access_fav_late": lambda r: _early_late(r, "access_fav")[1],
        "cls_correct_early": lambda r: _early_late(r, "cls_correct")[0],
        "cls_correct_late": lambda r: _early_late(r, "cls_correct")[1],
        "real_state_change": lambda r: r["summary"]["final_real_state_mean"] - r["summary"]["initial_real_state_mean"],
    }
    return _run_experiment(
        {
            "id": "EXP-TE06",
            "title": "Self-Reinforcing Scoring",
            "question": "When an access limit feeds back into what is observed next (gamma), into the subject's real state (beta) or sets a binding constraint (lock), does the favourable subjects' access fall over time, and under which of these does it not?",
            "control": "no feedback",
            "arms": arms,
            "declared": declared,
            "extra": extra,
            "primary": (
                "denial_persistence_of_early_denied",
                "self_fulfilled_share_of_early_denied_favourable",
                "locked_fraction",
            ),
            "failure_conditions": {
                "the control already drifts (access of favourable subjects falls by more than 0.1)": lambda a: (
                    _mean(a, "no feedback", "access_fav_early") - _mean(a, "no feedback", "access_fav_late") > 0.1
                )
            },
            "protocol": {
                "changed": "gamma (denial worsens observation), beta (resources change the real state), lock (binding constraint) singly and together",
                "unchanged": "sensors, classifier, threshold",
                "seeds": list(SEEDS),
                "failure": "the control drifts",
            },
        }
    )


REGISTRY = {
    "EXP-TE01-unscored": lambda: te01(False),
    "EXP-TE01-scored": lambda: te01(True),
    "EXP-TE01-scored-transforming": lambda: te01(True, 0.06),
    "EXP-TE02": te02,
    "EXP-TE03": te03,
    "EXP-TE04": te04,
    "EXP-TE04-support": lambda: te04(0.1),
    "EXP-TE04-release": te04_release,
    "EXP-TE05-tauB+0.00": lambda: te05(0.0),
    "EXP-TE05-tauB+0.12": lambda: te05(0.12),
    "EXP-TE06": te06,
}


def run_all() -> dict:
    return {"engine": "truth_error/1", "experiments": {k: f() for k, f in REGISTRY.items()}}
