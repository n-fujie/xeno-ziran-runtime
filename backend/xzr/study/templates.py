"""Protocol templates a researcher starts from. A template is an ordinary protocol; nothing about it is pre-registered
until it is registered (mode confirmatory) or run."""

from __future__ import annotations

import copy

from .protocol import FUNCTIONAL_ENGINE, FUNCTIONAL_GEN, SCHEMA

METRICS_SECONDARY = [
    "ignitions",
    "unobservable_samples",
    "reachable_share",
    "field_ignitions",
    "revisions",
    "reinsertions",
    "causal_depth",
    "picturing_error",
]


def _arm(name: str, description: str, condition: str = "D", controller: dict | None = None, **kw) -> dict:
    return {
        "name": name,
        "description": description,
        "condition": condition,
        "controller": controller or {"mode": "static"},
        **kw,
    }


def revision_study(
    n_seeds: int = 6,
    horizon: int = 240,
    mode: str = "functional",
    gen_base: int = FUNCTIONAL_GEN[0],
    engine_base: int = FUNCTIONAL_ENGINE[0],
) -> dict:
    """Ziran revision study: does revising the observation configuration between epochs change later operation, and which
    revision policy does what? Eight arms over one environment, same seeds."""
    rec = {"mode": "recursive", "trace_reachability": True}
    arms = [
        _arm(
            "fixed",
            "HPO field with all interactions and history re-entry on; the observation configuration is never "
            "revised. Information: default instruments. May revise: nothing.",
            controller={"mode": "static"},
        ),
        _arm(
            "recursive",
            "As fixed, plus the HPO-003 rule-based controller reconfigures the instruments, allocation, order, "
            "coupling and history between epochs from the reasons operations were blind. Information: the "
            "field's own records (never the world). May revise: every sandbox path.",
            controller=dict(rec),
        ),
        _arm(
            "recursive-meta",
            "As recursive, and the controller's own rule parameters are revised when a rule's change did "
            "not remove the blindness it targeted twice in a row (metarevision).",
            controller={**rec, "meta": True},
        ),
        _arm(
            "random-matched",
            "Uniformly random valid sandbox changes, the same number per epoch as the recursive arm on "
            "the same seed (control: any change versus result-driven change).",
            controller={"mode": "random", "match_budget_of": "recursive", "trace_reachability": True},
        ),
        _arm(
            "no-history",
            "As recursive but without history re-entry (settings.history.reinsert off).",
            condition="C",
            controller=dict(rec),
        ),
        _arm(
            "observation-narrowed",
            "As recursive, but the withdrawal instrument starts without boundary_flow (an "
            "observation condition imposed by the protocol; the controller may restore it).",
            controller=dict(rec),
            initial_changes=[
                {
                    "path": "instruments.withdrawal.channels",
                    "value": "boundary_flow",
                    "op": "remove",
                    "why": "protocol: narrowed observation",
                }
            ],
        ),
        _arm(
            "boundary-veiled",
            "As recursive, with veils twice as opaque in effect (boundary.veil_scale 1.5) from the start.",
            controller=dict(rec),
            settings={"boundary": {"veil_scale": 1.5, "gate_scale": 1.0}},
        ),
        _arm(
            "variable-added",
            "As recursive, with the derived variable activity_trend adopted from the start (a protocol "
            "change of the variable set).",
            controller=dict(rec),
            initial_changes=[{"path": "variables", "value": "activity_trend", "op": "add", "why": "protocol: variable set"}],
        ),
        _arm(
            "scale-window-shifted",
            "As recursive, with the closure instrument moved to a finer scale and a longer window "
            "after the first epoch (protocol intervention).",
            controller=dict(rec),
            interventions=[
                {"epoch": 0, "change": {"path": "instruments.closure.level", "value": 2, "why": "protocol: scale"}},
                {"epoch": 0, "change": {"path": "instruments.closure.window", "value": 6, "why": "protocol: window"}},
            ],
        ),
    ]
    contrasts = [
        {"id": "C1", "a": "recursive", "b": "fixed", "varies": ["controller", "revision_authority"], "role": "primary"},
        {"id": "C2", "a": "recursive-meta", "b": "recursive", "varies": ["meta_revision"], "role": "secondary"},
        {"id": "C3", "a": "recursive", "b": "random-matched", "varies": ["controller"], "role": "secondary"},
        {"id": "C4", "a": "recursive", "b": "no-history", "varies": ["history_reinsertion", "information"], "role": "secondary"},
        {"id": "C5", "a": "observation-narrowed", "b": "recursive", "varies": ["information"], "role": "secondary"},
        {"id": "C6", "a": "boundary-veiled", "b": "recursive", "varies": ["information"], "role": "secondary"},
        {"id": "C7", "a": "variable-added", "b": "recursive", "varies": ["information"], "role": "secondary"},
        {"id": "C8", "a": "scale-window-shifted", "b": "recursive", "varies": ["interventions"], "role": "secondary"},
    ]
    return {
        "schema": SCHEMA,
        "title": "Observation-configuration revision on the runtime world",
        "question": "Does revising the observation configuration between epochs change what the operations can do afterwards, "
        "and does a result-driven policy differ from a matched random one?",
        "hypotheses": [
            {
                "id": "H1",
                "text": "A result-driven revision policy yields more successful evaluations than no revision "
                "(C1) and than matched random revision (C3).",
                "contrasts": ["C1", "C3"],
            },
            {
                "id": "H2",
                "text": "Revising the revision rules changes the later changes made (C2); no direction is assumed.",
                "contrasts": ["C2"],
            },
        ],
        "mode": mode,
        "environment": {
            "kind": "hpo-world",
            "world": {"n": 800, "regime": "intermittent"},
            "warmup": 40,
            "horizon": horizon,
            "detect_shapes": False,
            "keep_trace": False,
        },
        "arms": arms,
        "seeds": {"gen_base": gen_base, "engine_base": engine_base, "n": n_seeds},
        "metrics": {"primary": ["fired_samples"], "secondary": METRICS_SECONDARY},
        "contrasts": contrasts,
        "criteria": {
            "success": [
                {
                    "contrast": "C1",
                    "metric": "fired_samples",
                    "direction": "greater",
                    "min_relative_effect": 0.02,
                    "ci_excludes_zero": True,
                }
            ],
            "failure": [
                {
                    "contrast": "C1",
                    "metric": "fired_samples",
                    "direction": "less",
                    "min_relative_effect": 0.02,
                    "ci_excludes_zero": True,
                }
            ],
        },
        "stop": {"max_wall_seconds": 3600, "timeout_per_run_s": 300, "max_failures": 3},
        "budget": {"max_runs": 10_000, "procs": 2},
        "intervention_authority": "arms with a controller may change every sandbox path; protocol interventions are listed "
        "per arm and are pre-specified.",
        "notes": "Functional template: small seed count, reserved seed range, not evidence. Set mode to exploratory with "
        "fresh seeds to explore; confirmatory needs registration (freeze) first.",
    }


def quick(n_seeds: int = 2, horizon: int = 120) -> dict:
    """A two-arm protocol small enough for tests and a first look."""
    d = revision_study(n_seeds, horizon)
    keep = {"fixed", "recursive"}
    d["arms"] = [a for a in d["arms"] if a["name"] in keep]
    d["contrasts"] = [c for c in d["contrasts"] if c["a"] in keep and c["b"] in keep]
    d["hypotheses"] = [h for h in d["hypotheses"] if h["contrasts"] == ["C1"]] or d["hypotheses"][:1]
    d["hypotheses"][0] = {**d["hypotheses"][0], "contrasts": ["C1"]}
    d["title"] = "Quick check: revision versus none"
    return d


def lab_population_study(n_seeds: int = 2, sizes: tuple[int, ...] = (3, 20)) -> dict:
    arms = [
        {
            "name": f"systems-{n}",
            "description": f"{n} heterogeneous scientific systems (local / distributed / history) "
            "in the shared laboratory with the default capacities",
            "population": {"n": n, "capacities": True},
        }
        for n in sizes
    ]
    return {
        "schema": SCHEMA,
        "title": "Laboratory load by population size",
        "question": "How do requests and completed transfers scale with the number of systems sharing the laboratory?",
        "mode": "functional",
        "environment": {"kind": "lab-population", "horizon": 40},
        "arms": arms,
        "seeds": {"gen_base": FUNCTIONAL_GEN[0], "engine_base": FUNCTIONAL_ENGINE[0], "n": n_seeds},
        "metrics": {"primary": ["requests"], "secondary": ["completed", "failed", "denied", "observed_outcomes", "events"]},
        "contrasts": [
            {"id": "C1", "a": f"systems-{sizes[-1]}", "b": f"systems-{sizes[0]}", "varies": ["compute"], "role": "primary"}
        ],
        "criteria": {"success": [], "failure": []},
        "stop": {"max_wall_seconds": 1800, "timeout_per_run_s": 300, "max_failures": 3},
        "budget": {"max_runs": 1000, "procs": 2},
    }


TEMPLATES = {"revision-study": revision_study, "quick": quick, "lab-population": lab_population_study}


def template(name: str, **kw) -> dict:
    return copy.deepcopy(TEMPLATES[name](**kw))
