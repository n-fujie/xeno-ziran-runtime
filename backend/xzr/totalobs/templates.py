"""Protocol templates of the total-observation line (registered into ``study.templates.TEMPLATES``). All are functional protocols: they check that the
machinery runs and records what it is meant to record. None of them is a confirmatory study and none is pre-registered."""

from __future__ import annotations

import copy
import itertools

from ..study.protocol import FUNCTIONAL_ENGINE, FUNCTIONAL_GEN, SCHEMA
from . import sss
from .agent import STRONG

PRIMARY = ["recall_final"]
SECONDARY = [
    "recall_mean",
    "precision_mean",
    "spurious_rate",
    "config_born_rate",
    "merged_total",
    "info_age_mean",
    "generations_run",
    "stopped_early",
    "ops_executed",
    "ops_denied",
    "opportunity_cost",
    "question_changes",
    "eval_changes",
    "grammar_changes",
    "rollbacks",
    "variables_adopted",
    "variables_rejected",
    "history_changes",
    "history_reads",
    "history_hits",
    "meta_revisions",
    "meta_exhausted",
    "hyp_tests",
    "hyp_supported",
    "hyp_refuted",
    "hyp_inconclusive",
    "hyp_error_true",
    "reach_expanded",
    "reach_contracted",
    "reach_mixed",
    "reach_equivalent",
    "ident_lost",
    "ident_gained",
    "integration_loss_events",
    "obs_cost",
    "denied_blocks",
    "expired_sensors",
    "records_lost",
    "lost_in_transit",
    "interference",
    "budget_left",
    "planetary_conditions_met",
]
FULL = {"policy": "adaptive", "history": "own", "meta": True, "strong": list(STRONG)}
STRESS_ENV = {
    "generations": 10,
    "net": {"pool": 16.0, "n_sensors": 3},
    "events": [
        {"gen": 3, "do": "fail_sensor", "sensor": "S0"},
        {"gen": 5, "do": "cut_zone", "center": 40, "radius": 3},
        {"gen": 6, "do": "lose_records", "t0": 0},
    ],
}


def _arm(name: str, description: str, design: dict, environment: dict | None = None, **kw) -> dict:
    return {
        "name": name,
        "description": description,
        "design": design,
        **({"environment": environment} if environment else {}),
        **kw,
    }


def _doc(title: str, question: str, environment: dict, arms: list[dict], contrasts: list[dict], n_seeds: int, notes: str) -> dict:
    return {
        "schema": SCHEMA,
        "title": title,
        "question": question,
        "mode": "functional",
        "environment": {"kind": "total-observation", **environment},
        "arms": arms,
        "seeds": {"gen_base": FUNCTIONAL_GEN[0], "engine_base": FUNCTIONAL_ENGINE[0], "n": n_seeds},
        "metrics": {"primary": list(PRIMARY), "secondary": list(SECONDARY)},
        "contrasts": contrasts,
        "criteria": {"success": [], "failure": []},
        "stop": {"max_wall_seconds": 1800, "timeout_per_run_s": 120, "max_failures": 5},
        "budget": {"max_runs": 400, "procs": 2},
        "notes": notes,
    }


def total_observation(n_seeds: int = 6, generations: int = 10) -> dict:
    """The autonomous research loop and its ablations in the synthetic regional world: fixed, random, adaptive, with history (own / shuffled), with
    rule revision, with strong revision (variables, classification, boundary, evaluation rule, operation grammar), and each strong revision removed."""
    no = lambda x: {**FULL, "strong": [s for s in STRONG if s != x]}  # noqa: E731
    arms = [
        _arm("fixed", "The initial observing layout, never changed. May revise: nothing.", {"policy": "fixed"}),
        _arm(
            "random-matched",
            "Same grammar as adaptive; the arguments of its (up to two) operations per generation are drawn at random, with no reasons.",
            {"policy": "random"},
        ),
        _arm(
            "adaptive",
            "Reasons found in the hub's records -> operations (add / move sensor, scale, period, integration). Question, hypothesis and evaluation rule advance by their rules. No history, no rule revision.",
            {"policy": "adaptive"},
        ),
        _arm(
            "adaptive-history",
            "As adaptive, with an external memory of outcomes of earlier conditions, re-entered after identification is lost.",
            {"policy": "adaptive", "history": "own"},
        ),
        _arm(
            "adaptive-history-shuffled",
            "As adaptive-history, the stored outcomes permuted across conditions at every read (a memory with no information).",
            {"policy": "adaptive", "history": "shuffled"},
        ),
        _arm(
            "adaptive-meta",
            "As adaptive, with meta-revision of the revision rules' parameters (the HPO-003 judging: a rule whose change did not remove its blindness twice is revised or exhausted).",
            {"policy": "adaptive", "meta": True},
        ),
        _arm(
            "full",
            "History, meta-revision and all five strong revisions (derived variable, classification, boundary, evaluation rule, operation grammar).",
            dict(FULL),
        ),
        _arm("full-no-variable", "full without variable generation.", no("variable")),
        _arm("full-no-classification", "full without revision of the classification scheme.", no("classification")),
        _arm("full-no-boundary", "full without redefinition of the observation boundary.", no("boundary")),
        _arm("full-no-evaluation", "full without revision of the evaluation rule.", no("evaluation")),
        _arm(
            "full-no-grammar",
            "full without extension of the operation grammar (so no intervention is ever permitted).",
            no("grammar"),
        ),
        _arm("full-no-history", "full without the external memory.", {**FULL, "history": False}),
        _arm("full-no-meta", "full without rule revision.", {**FULL, "meta": False}),
    ]
    c = lambda i, a, b, v: {"id": f"C{i}", "a": a, "b": b, "varies": v, "role": "secondary"}  # noqa: E731
    contrasts = [
        c(1, "adaptive", "fixed", ["policy", "revision_authority"]),
        c(2, "adaptive", "random-matched", ["policy"]),
        c(3, "adaptive-history", "adaptive", ["history"]),
        c(4, "adaptive-history", "adaptive-history-shuffled", ["history"]),
        c(5, "adaptive-meta", "adaptive", ["meta_revision"]),
        c(6, "full", "adaptive", ["history", "meta_revision", "strong_revision", "revision_authority"]),
        c(7, "full", "full-no-variable", ["strong_revision", "revision_authority"]),
        c(8, "full", "full-no-classification", ["strong_revision", "revision_authority"]),
        c(9, "full", "full-no-boundary", ["strong_revision", "revision_authority"]),
        c(10, "full", "full-no-evaluation", ["strong_revision", "revision_authority"]),
        c(11, "full", "full-no-grammar", ["strong_revision", "revision_authority"]),
        c(12, "full", "full-no-history", ["history"]),
        c(13, "full", "full-no-meta", ["meta_revision"]),
    ]
    return _doc(
        "Autonomous research loop over a synthetic observation world",
        "Does a loop that turns observation failures into changes of question, hypothesis, experiment, intervention and evaluation rule, and re-enters its history, "
        "identify more of the world's objects than a fixed layout, a matched random revision and its own ablations? (functional check of the machinery, not a test)",
        {"generations": generations},
        arms,
        contrasts,
        n_seeds,
        "A functional check. Contrasts differing in several components say so in `varies`; none is a single-mechanism effect. The verifier's scores are never given to an arm.",
    )


def autonomous_loop(n_seeds: int = 6) -> dict:
    """The same arms under disturbance: a sensor fails, a communication outage covers part of the net, the hub loses its records, the resource pool is small."""
    d = total_observation(n_seeds, 10)
    keep = {"fixed", "random-matched", "adaptive", "adaptive-history", "adaptive-meta", "full"}
    d["arms"] = [a for a in d["arms"] if a["name"] in keep]
    d["contrasts"] = [c for c in d["contrasts"] if c["a"] in keep and c["b"] in keep]
    d["environment"] = {"kind": "total-observation", **copy.deepcopy(STRESS_ENV)}
    d["title"] = "Autonomous research loop under failure, outage, record loss and scarcity"
    d["question"] = (
        "When an observer fails, communication is cut over a region, the hub loses records and measurement resources are scarce, which of the loop's "
        "components change what is identified afterwards, and which make it worse? (functional; worsening is reported as plainly as improvement)"
    )
    return d


def planetary_observation(n_seeds: int = 6) -> dict:
    """The ten conditions of the minimal planetary-scale model, one arm each, plus a larger world that meets the declared structural conditions."""
    basic = {"policy": "adaptive", "history": "own", "meta": True}
    conds = [
        ("local", "One sensor: local observation only.", {"net": {"n_sensors": 1}}),
        ("distributed", "Three sensors spread over the regions (baseline).", {}),
        (
            "propagation-slow",
            "Slow propagation (c 0.5) over a wider interaction span (3): states take longer to reach other regions.",
            {"world": {"c": 0.5, "span": 3}},
        ),
        ("asynchronous", "Sensors observe with different periods (3, 5, 8).", {"net": {"periods": [3, 5, 8]}}),
        (
            "interference",
            "Strong absorption by observation (0.4): sensors disturb each other's readings.",
            {"net": {"backaction": 0.4}},
        ),
        ("mutual-transformation", "Fast wear of the observer by the observed activity (0.8).", {"net": {"wear": 0.8}}),
        (
            "expiry",
            "Two sensors fail (generations 3 and 5): observing conditions disappear.",
            {"events": [{"gen": 3, "do": "fail_sensor", "sensor": "S0"}, {"gen": 5, "do": "fail_sensor", "sensor": "S1"}]},
        ),
        (
            "record-loss",
            "The hub loses its records (generations 4 and 6); the material state is untouched.",
            {"events": [{"gen": 4, "do": "lose_records", "t0": 0}, {"gen": 6, "do": "lose_records", "t0": 0}]},
        ),
        ("comm-delay", "Four steps of delay per hop to the hub.", {"net": {"latency": 4}}),
        ("resource-contention", "A pool of 12 blocks per step shared by all sensors.", {"net": {"pool": 12.0}}),
        (
            "reorganisation",
            "A communication outage over a region at generation 3 (restored at 7): the layout has to be reorganised to be heard.",
            {"events": [{"gen": 3, "do": "cut_zone", "center": 40, "radius": 4}, {"gen": 7, "do": "restore_links"}]},
        ),
        (
            "planetary-form",
            "A 12 x 24 world, span 3, four sensors, two steps per hop: meets every declared structural condition (planetary.conditions).",
            {"world": {"rows": 12, "cols": 24, "span": 3}, "net": {"n_sensors": 4, "latency": 2, "pool": 24.0}},
        ),
    ]
    arms = [_arm(n, desc, dict(basic), env or None) for n, desc, env in conds]
    contrasts = [
        {
            "id": f"C{i}",
            "a": n,
            "b": "distributed",
            "varies": ["resources", "environment"]
            if n in ("local", "resource-contention", "planetary-form")
            else ["environment"],
            "role": "secondary",
        }
        for i, (n, _, _) in enumerate(conds, 1)
        if n != "distributed"
    ]
    return _doc(
        "Minimal planetary-scale observation model: ten conditions",
        "How do distributed observation, finite propagation, asynchrony, interference, mutual transformation, expiry, record loss, delay, contention and "
        "reorganisation change what a research loop can identify in a synthetic regional world? (a synthetic model: no claim about the Earth)",
        {"generations": 8, "net": {"n_sensors": 3}},
        arms,
        contrasts,
        n_seeds,
        "Every arm records planetary.conditions(env): the declared structural conditions under which the model has the form of a planetary-scale observation problem. "
        "The number of regions or sensors alone does not satisfy them. earth_claim is false.",
    )


def sss_axes(n_seeds: int = 6, design: dict | None = None) -> dict:
    """A full 2^3 design over Scale, Size and Speed (each changed through its declared parameters only)."""
    design = design or {"policy": "adaptive"}
    arms, tags = [], {}
    for combo in itertools.product(("low", "high"), repeat=3):
        tag = dict(zip(sss.AXES, combo, strict=True))
        env: dict = {}
        base: dict = {}
        for ax, lv in tag.items():
            base = sss.vary(base, ax, lv)
        env = {k: v for k, v in base.items() if k in ("world", "net")}
        name = "sss-" + "".join(c[0] for c in combo)
        arms.append(_arm(name, f"Scale {combo[0]}, Size {combo[1]}, Speed {combo[2]}.", dict(design), env, sss=tag))
        tags[name] = tag
    contrasts = [
        {"id": f"C{i}", "a": a["name"], "b": "sss-lll", "varies": ["environment"], "role": "secondary"}
        for i, a in enumerate(arms[1:], 1)
    ]
    return _doc(
        "Scale, Size and Speed: a full two-level design",
        "How do Scale, Size and Speed, changed separately and together, change identification, object formation, intervention, communication, recording and what "
        "follows? Interaction contrasts are reported; metrics whose definition depends on an axis are not compared across it.",
        {"generations": 8},
        arms,
        contrasts,
        n_seeds,
        "Scale: sensor block size. Size: rows x cols. Speed: propagation c, source period, sensor period. The number of sensors, the pool and the number of "
        "generations are held fixed, so coverage and contention change with Size by design (declared, not corrected).",
    )


TEMPLATES = {
    "total-observation": total_observation,
    "autonomous-loop": autonomous_loop,
    "planetary-observation": planetary_observation,
    "sss-axes": sss_axes,
}
