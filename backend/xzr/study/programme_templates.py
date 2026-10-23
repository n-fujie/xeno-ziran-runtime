"""Protocol templates of the four research programmes (docs/research/RESEARCH_PROGRAMS.md), registered into ``study.templates.TEMPLATES``.

Each is an ordinary Study Engine protocol: functional by default (the reserved seed range; the UI switches the seeds when the mode is changed to exploratory), never
pre-registered, never confirmatory. They compose arms and metrics that already exist; no comparator is named that has no implementation here (see
``scripts/comparators_audit.py``). Every contrast declares everything in which its two arms differ."""

from __future__ import annotations

import itertools

from ..totalobs import sss
from ..totalobs.agent import STRONG
from . import totalobs_templates as TT

# metrics the programmes ask for, each from data a run already holds (definitions: docs/research/RESEARCH_PROGRAMS.md)
EXT = [
    "coverage_final",
    "identification_count_error",
    "change_failure_rate",
    "ops_cost_spent",
    "cycles_completed",
    "observation_loss_share",
    "expiry_rate",
    "reachable_regions_final",
    "recall_post_change",
    "metric_definition_breaks",
]
SECONDARY = (
    [m for m in TT.SECONDARY if m != "recall_final"]
    + [m for m in EXT if m not in TT.SECONDARY]
    + [
        "ident_lost_object_still_present",
        "ident_lost_object_absent",
        "scale_reversals",
        "conflict_events",
        "infeasible_events",
    ]
)
FULL3 = {"policy": "adaptive", "history": "own", "meta": True, "strong": list(STRONG)}


def drift(modulus: int) -> list[dict]:
    """The sources move at generations 3-7 (regions valid in a world of at least ``modulus`` regions): a world that changes, so that information can go out of date."""
    return [
        {"gen": g, "do": "move_source", "k": k, "region": (17 * k + 31 * g) % modulus} for g in (3, 4, 5, 6, 7) for k in (0, 1, 2)
    ]


def _arm(name: str, description: str, design: dict, environment: dict | None = None, **kw) -> dict:
    return TT._arm(name, description, design, environment, **kw)


def _programme(title: str, question: str, env: dict, arms: list[dict], contrasts: list[dict], n_seeds: int, notes: str) -> dict:
    d = TT._doc(title, question, {"measures": "extended", **env}, arms, contrasts, n_seeds, notes)
    d["metrics"] = {"primary": list(TT.PRIMARY), "secondary": list(SECONDARY)}
    return d


def _c(i: int, a: str, b: str, varies: list[str]) -> dict:
    return {"id": f"C{i}", "a": a, "b": b, "varies": varies, "role": "secondary"}


# ---------------------------------------------------------------------------------------------------- Research Programme 1 - Ziran operational self-revision (HPO world)
def rp1_ziran_self_revision(n_seeds: int = 6) -> dict:
    """RP1: does revising the observation configuration, its variables, boundary, scale and time window (and the revision rules, and with / without history
    re-entry) change what later operations can do, compared with a fixed configuration and a matched random revision? The HPO world's own arms
    (``revision-study``); the metrics are the ones the HPO runs hold. The confirmatory path is docs/level2/PROTOCOL_L2_DRAFT.json."""
    from .templates import revision_study

    d = revision_study(n_seeds=n_seeds, horizon=240, mode="functional")
    d["title"] = (
        "RP1 - Ziran operational self-revision: observation, variable, boundary, scale and time-window revision, rule revision and history re-entry"
    )
    d["metrics"] = {
        "primary": ["fired_samples"],
        "secondary": [
            "unobservable_samples",
            "reachable_share",
            "controller_changes",
            "controller_rejected",
            "meta_revisions",
            "meta_exhausted",
            "measure_cost",
            "stopped_early",
            "ceased_share",
            "reinsertions",
            "ignitions",
        ],
    }
    d["notes"] = (
        "A functional check of programme RP1. A change of the configuration is a record, not evidence of improvement. The comparator with the same change authority from "
        "an existing method is not available in the HPO world: it exists only in the ARDS-HPO shared environment (shared-comparison, test replicates). "
        "Numerical environment: the address hierarchy of this world is a spectral split (method 1); state the solver build in the preregistration of any confirmatory study."
    )
    return d


# ---------------------------------------------------------------------------------------------------- Research Programme 2 - Total Observation
def rp2_total_observation(n_seeds: int = 6) -> dict:
    """RP2: single vs distributed observation; fixed vs adaptive integration; observer interference on / off; record loss on / off; self-revision of the observing
    conditions on / off. Factor arms that isolate an environmental factor use a fixed research policy, so that the factor and not the agent is what differs."""
    fixed = {"policy": "fixed"}
    adaptive = {"policy": "adaptive"}
    arms = [
        _arm(
            "adaptive-base",
            "Three sensors, the base adaptive loop (add / move sensor, scale, period, integration): the baseline for observer count and for self-revision.",
            adaptive,
        ),
        _arm("obs-single", "As adaptive-base with ONE sensor: single observation.", adaptive, {"net": {"n_sensors": 1}}),
        _arm(
            "fixed-base",
            "Three sensors, layout and integration never changed (integration 'separate'): the baseline for integration and interference.",
            fixed,
        ),
        _arm(
            "int-mean",
            "As fixed-base with the integration rule 'mean' (reports of overlapping sensors averaged).",
            fixed,
            {"integration": "mean"},
        ),
        _arm(
            "int-finest",
            "As fixed-base with the integration rule 'finest' (the finest-scale report wins).",
            fixed,
            {"integration": "finest"},
        ),
        _arm(
            "int-adaptive",
            "As fixed-base, but the agent may change the integration rule, and nothing else, from what it can compute on its own records.",
            {"policy": "adaptive", "authority": ["set-integration"]},
        ),
        _arm(
            "intf-none",
            "As fixed-base without absorption by observation (backaction 0): observers do not disturb what they read.",
            fixed,
            {"net": {"backaction": 0.0}},
        ),
        _arm("intf-strong", "As fixed-base with strong absorption (backaction 0.4).", fixed, {"net": {"backaction": 0.4}}),
        _arm(
            "loss-none", "The adaptive loop with history re-entry, no loss of records.", {"policy": "adaptive", "history": "own"}
        ),
        _arm(
            "loss-events",
            "As loss-none; the hub loses all its records at generations 3 and 5 (the material state is untouched).",
            {"policy": "adaptive", "history": "own"},
            {"events": [{"gen": 3, "do": "lose_records", "t0": 0}, {"gen": 5, "do": "lose_records", "t0": 0}]},
        ),
        _arm(
            "selfrev-on",
            "As adaptive-base, plus self-revision of the observing conditions: classification threshold and connectivity, observation boundary, derived variable.",
            {"policy": "adaptive", "strong": ["classification", "boundary", "variable"]},
        ),
    ]
    contrasts = [
        _c(1, "adaptive-base", "obs-single", ["environment", "resources"]),
        _c(2, "int-mean", "fixed-base", ["environment"]),
        _c(3, "int-finest", "fixed-base", ["environment"]),
        _c(4, "int-adaptive", "fixed-base", ["policy", "revision_authority"]),
        _c(5, "intf-strong", "fixed-base", ["environment"]),
        _c(6, "intf-none", "fixed-base", ["environment"]),
        _c(7, "loss-events", "loss-none", ["environment"]),
        _c(8, "selfrev-on", "adaptive-base", ["strong_revision", "revision_authority"]),
    ]
    return _programme(
        "RP2 - Total Observation: observers, integration, interference, record loss and self-revision of observing conditions",
        "When several local observing systems exist, integrate, interfere with the observed and with each other, lose their records and revise their own conditions, how do "
        "identification, observational loss, disturbance, later reachability and the material consequences change? (a synthetic model; the state of the model is not reality as a whole)",
        {"rules_version": "v2", "generations": 10, "net": {"n_sensors": 3}},
        arms,
        contrasts,
        n_seeds,
        "Functional check. Identification is measured against the model's own state by the verifier; no arm reads it. Complete information is not a goal: the observing systems "
        "see only what they record.",
    )


# ---------------------------------------------------------------------------------------------------- Research Programme 3 - Planetary-scale observation
def rp3_planetary_placement(n_seeds: int = 6) -> dict:
    """RP3: fixed, random, adaptive and self-revising placement of observers, with and without communication delay and observer interference, in a synthetic world that
    meets the declared structural conditions and whose sources move (so that delayed information can go out of date)."""
    base_env = {
        "rules_version": "v2",
        "generations": 8,
        "world": {"rows": 12, "cols": 24, "span": 3},
        "net": {"n_sensors": 4, "latency": 1, "pool": 24.0, "backaction": 0.05},
        "events": drift(96),
    }
    placements = {
        "fixed": ({"policy": "fixed"}, {}),
        "random": ({"policy": "fixed"}, {"net": {"placement": "random"}}),
        "adaptive": ({"policy": "adaptive"}, {}),
        "selfrev": (FULL3, {}),
    }
    arms, contrasts = [], []

    def name(p: str, lat: int, hi: bool) -> str:
        return f"{p}-lat{lat}" + ("-intf" if hi else "")

    for lat in (1, 4):
        for p, (design, env) in placements.items():
            e = {**env, "net": {**env.get("net", {}), "latency": lat}}
            arms.append(
                _arm(name(p, lat, False), f"{p} placement, {lat} step(s) per hop to the hub, low interference.", dict(design), e)
            )
    for p, (design, env) in placements.items():
        e = {**env, "net": {**env.get("net", {}), "latency": 1, "backaction": 0.4}}
        arms.append(
            _arm(name(p, 1, True), f"{p} placement, 1 step per hop, strong absorption by observation (0.4).", dict(design), e)
        )
    i = 1
    for lat in (1, 4):
        for p in ("random", "adaptive", "selfrev"):
            vary = (
                ["environment"]
                if p == "random"
                else ["policy", "revision_authority"]
                if p == "adaptive"
                else ["policy", "revision_authority", "history", "meta_revision", "strong_revision"]
            )
            contrasts.append(_c(i, name(p, lat, False), name("fixed", lat, False), vary))
            i += 1
    for p in placements:
        contrasts.append(_c(i, name(p, 4, False), name(p, 1, False), ["environment"]))
        i += 1
    for p in placements:
        contrasts.append(_c(i, name(p, 1, True), name(p, 1, False), ["environment"]))
        i += 1
    return _programme(
        "RP3 - Planetary-scale observation: placement, delay and interference in a synthetic world",
        "How far can spatially distributed observing systems with different speeds, communication conditions and resource layouts identify changes of a wide synthetic world, "
        "and what do fixed, random, adaptive and self-revising placement do to that? (a synthetic model: no conclusion about the Earth follows)",
        base_env,
        arms,
        contrasts,
        n_seeds,
        "The world meets every declared structural condition (planetary.conditions) and its sources move at generations 3-7. earth_claim is false.",
    )


# ---------------------------------------------------------------------------------------------------- Research Programme 4 - SSS
def rp4_sss_self_revision(n_seeds: int = 6) -> dict:
    """RP4: a full 2^3 design over Scale, Size and Speed, each cell with the SSS metric self-revision (the evaluation rule, hence the definition of the success measure,
    may be revised) off and on. A measurement made under a changed definition is not compared across the break."""
    arms, contrasts = [], []
    for combo in itertools.product(("low", "high"), repeat=3):
        tag = dict(zip(sss.AXES, combo, strict=True))
        base: dict = {}
        for ax, lv in tag.items():
            base = sss.vary(base, ax, lv)
        env = {k: v for k, v in base.items() if k in ("world", "net")}
        code = "".join(c[0] for c in combo)
        arms.append(
            _arm(
                f"sss-{code}-off",
                f"Scale {combo[0]}, Size {combo[1]}, Speed {combo[2]}; the evaluation rule is never revised.",
                {"policy": "adaptive"},
                env,
                sss=tag,
            )
        )
        arms.append(
            _arm(
                f"sss-{code}-on",
                f"As sss-{code}-off; the evaluation rule (the success measure's definition) may be revised.",
                {"policy": "adaptive", "strong": ["evaluation"]},
                env,
            )
        )
    for i, combo in enumerate(itertools.product(("low", "high"), repeat=3), 1):
        code = "".join(c[0] for c in combo)
        contrasts.append(_c(i, f"sss-{code}-on", f"sss-{code}-off", ["strong_revision", "revision_authority"]))
    return _programme(
        "RP4 - Scale, Size and Speed with and without self-revision of the SSS metric",
        "How do Scale, Size and Speed, changed alone and together, change identification, tracking of a changing world, comparability of measurements, resource use and later "
        "research, and what does revising the success measure's own definition do to what can be compared?",
        {"rules_version": "v2", "generations": 10, "events": drift(48)},
        arms,
        contrasts,
        n_seeds,
        "Scale: sensor block size. Size: rows x cols. Speed: propagation, source period, sensor period. The off arms form the complete 2^3 design whose effects the analysis computes; "
        "metric_definition_breaks counts where a series is cut because its definition changed (no number is formed across a break).",
    )


TEMPLATES = {
    "rp1-ziran-self-revision": rp1_ziran_self_revision,
    "rp2-total-observation": rp2_total_observation,
    "rp3-planetary-placement": rp3_planetary_placement,
    "rp4-sss-self-revision": rp4_sss_self_revision,
}
