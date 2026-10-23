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
        "metrics": {
            "primary": ["requests"],
            "secondary": ["completed", "failed", "denied", "contention_rate", "distinct_conditions"],
        },
        "contrasts": [
            {"id": "C1", "a": f"systems-{sizes[-1]}", "b": f"systems-{sizes[0]}", "varies": ["compute"], "role": "primary"}
        ],
        "criteria": {"success": [], "failure": []},
        "stop": {"max_wall_seconds": 1800, "timeout_per_run_s": 300, "max_failures": 3},
        "budget": {"max_runs": 1000, "procs": 2},
    }


def ards_comparison(n_seeds: int = 2, ards_env: str = "env2") -> dict:
    """ARDS's own arms on its own environment, as a functional check of the integration (ARDS software-test replicates only)."""

    def arm(name: str, ards_arm: str, description: str) -> dict:
        return {"name": name, "description": description, "ards": {"arm": ards_arm}}

    arms = [
        arm(
            "existing-blind",
            "EXISTING-blind",
            "ARDS's independent re-implementation of the existing procedure with observer-side information "
            "only: revises the observation configuration from data, no memory, no history. Same information and permissions as the PA arms.",
        ),
        arm(
            "pa-validated",
            "V2-PA",
            "ARDS's PA arm with validated adoption: reads the observer view, keeps and re-injects its own history, may "
            "revise the same five observation operations (each validated on disjoint seeds).",
        ),
        arm(
            "pa-no-reinjection",
            "V2-PA-no-reinjection",
            "As pa-validated, but the memory is stored and never read (history ablation).",
        ),
        arm(
            "fixed-noise",
            "FIXED-noise",
            "Always halve sensor noise at the start; reads nothing (a fixed strategy; software-test parameter).",
        ),
        arm("control-v1-a", "V1-A", "Phase 3 A-fixed (frozen code, unchanged): fixed observation, no memory."),
    ]
    reps = [[3980 + i, 3980 + i] for i in range(n_seeds)]
    return {
        "schema": SCHEMA,
        "title": "ARDS arms through the study workflow",
        "question": "Do ARDS's arms run, verify and produce comparable records when driven from a study protocol? (integration check; "
        "ARDS software-test replicates, no exploration or study data)",
        "mode": "functional",
        "environment": {"kind": "ards", "ards_env": ards_env},
        "arms": arms,
        "seeds": {"list": reps},
        "metrics": {
            "primary": ["unseen_coverage"],
            "secondary": [
                "seen_coverage",
                "all_coverage",
                "unseen_fdr",
                "body_runs",
                "setup_seconds",
                "adopted",
                "changes_applied",
                "verification_failed",
            ],
        },
        "contrasts": [
            {
                "id": "C1",
                "a": "pa-validated",
                "b": "existing-blind",
                "varies": ["history_reinsertion", "proposal_policy"],
                "role": "primary",
            },
            {"id": "C2", "a": "pa-validated", "b": "pa-no-reinjection", "varies": ["history_reinsertion"], "role": "secondary"},
            {
                "id": "C3",
                "a": "pa-validated",
                "b": "fixed-noise",
                "varies": ["controller", "information", "revision_authority", "history_reinsertion", "proposal_policy"],
                "role": "secondary",
            },
        ],
        "criteria": {"success": [], "failure": []},
        "stop": {"max_wall_seconds": 3600, "timeout_per_run_s": 900, "max_failures": 2},
        "budget": {"max_runs": 100, "procs": 2},
        "notes": "ARDS's own gate accepts only replicates 3980-3989 in test mode; this study cannot be exploratory or confirmatory. The "
        "ARDS Phase 3 frozen assets and Phase 4 records are not read for results and are not written.",
    }


def shared_comparison(n_seeds: int = 2) -> dict:
    """ARDS arms and the HPO arm in one environment (env3: the runtime world observed through the HPO instruments), same budgets and
    evaluation. Functional check on ARDS software-test replicates."""

    def a(name: str, arm_id: str, description: str) -> dict:
        return {"name": name, "description": description, "ards": {"arm": arm_id}}

    def h(name: str, description: str, **hpo) -> dict:
        return {"name": name, "description": description, "hpo": hpo}

    arms = [
        a(
            "existing-blind",
            "EXISTING-blind",
            "ARDS's re-implementation of the existing procedure with observer-side information only (no memory).",
        ),
        a("ards-pa", "V2-PA", "ARDS's PA arm: observer view, own history re-injected, rules R1-R4, validated adoption."),
        a("ards-pa-no-history", "V2-PA-no-reinjection", "As ards-pa with the memory stored and never read."),
        a("fixed-noise", "FIXED-noise", "Always halve the sensor noise at the start; reads nothing."),
        a("control-v1-a", "V1-A", "Phase 3 A-fixed (frozen code): fixed observation configuration, no memory."),
        h(
            "hpo-rules",
            "The HPO-003 reconfiguration policy on the observation configuration: reads the capability reasons of the configuration in force, "
            "keeps the previous cycle's unidentified differences (history), tries a bundle and single rules against the control, adopts on a gain without loss "
            "and confirms on fresh seeds.",
            history=True,
            meta=False,
        ),
        h(
            "hpo-rules-no-history",
            "As hpo-rules without the history of earlier cycles (no noise rule; the memory is not kept).",
            history=False,
            meta=False,
        ),
        h(
            "hpo-rules-meta",
            "As hpo-rules, and the policy's own rule parameters (noise multiplier, resolution step) are revised when a rule's change did "
            "not remove the blindness it targeted twice in a row (hpo.metarevision).",
            history=True,
            meta=True,
        ),
        h(
            "hpo-rules-select",
            "As hpo-rules, and the arm chooses which alteration the next experiment tests (operation: intervention): the same one again on fresh seeds when "
            "the last cycle left at least 3 differences capable but not identified, else a new one from the three loop alterations.",
            history=True,
            meta=False,
            select=True,
        ),
    ]
    return {
        "schema": SCHEMA,
        "title": "ARDS and HPO policies in the shared environment",
        "question": "In one environment, with the same information, permissions, budgets and evaluation, how do ARDS's arms and the HPO reconfiguration "
        "policy differ in what their final observation configurations identify? (functional check on ARDS software-test replicates)",
        "mode": "functional",
        "environment": {"kind": "shared-oi"},
        "arms": arms,
        "seeds": {"list": [[3980 + i, 3980 + i] for i in range(n_seeds)]},
        "metrics": {
            "primary": ["unseen_coverage"],
            "secondary": [
                "seen_coverage",
                "all_coverage",
                "unseen_fdr",
                "body_runs",
                "setup_seconds",
                "adopted",
                "changes_applied",
                "capable_gained",
                "verification_failed",
                "reach_opened",
                "reach_opened_identified",
                "reach_opened_not_identified",
                "meta_revisions",
            ],
        },
        "contrasts": [
            {
                "id": "C1",
                "a": "hpo-rules",
                "b": "existing-blind",
                "varies": ["proposal_policy", "history_reinsertion"],
                "role": "primary",
            },
            {"id": "C2", "a": "hpo-rules", "b": "ards-pa", "varies": ["proposal_policy"], "role": "secondary"},
            {"id": "C3", "a": "hpo-rules", "b": "hpo-rules-no-history", "varies": ["history_reinsertion"], "role": "secondary"},
            {"id": "C4", "a": "hpo-rules-meta", "b": "hpo-rules", "varies": ["meta_revision"], "role": "secondary"},
            {"id": "C5", "a": "ards-pa", "b": "ards-pa-no-history", "varies": ["history_reinsertion"], "role": "secondary"},
            {
                "id": "C6",
                "a": "ards-pa",
                "b": "existing-blind",
                "varies": ["proposal_policy", "history_reinsertion"],
                "role": "secondary",
            },
        ],
        "criteria": {"success": [], "failure": []},
        "stop": {"max_wall_seconds": 7200, "timeout_per_run_s": 900, "max_failures": 3},
        "budget": {"max_runs": 200, "procs": 2},
        "notes": "New environment defined in this repository (study/shared); ARDS's environments and frozen assets are untouched. ARDS's gate accepts only "
        "replicates 3980-3989 in test mode, so the study is a functional check by construction.",
    }


def multi_system(n_seeds: int = 4, n: int = 20, horizon: int = 120) -> dict:
    """Several research systems in the shared laboratory under different conditions: does a population behave as several research systems?
    Measures ten properties (lab/multisystem.py); load alone is not capability."""

    def arm(name: str, description: str, scenario: dict | None = None, n_systems: int = n) -> dict:
        return {
            "name": name,
            "description": description,
            "population": {"n": n_systems, "capacities": True, "diverse": True},
            **({"scenario": scenario} if scenario else {}),
        }

    arms = [
        arm(
            "baseline",
            f"{n} heterogeneous systems (local / distributed / history), different sampling periods and windows, no intervention.",
        ),
        arm(
            "many",
            f"{5 * n} systems: the same population scaled up (resource competition for the laboratory's gantries).",
            n_systems=5 * n,
        ),
        arm(
            "stop-30pct",
            "30% of the systems stop acting at the middle of the run; their histories are kept.",
            {"stop": {"fraction": 0.3, "at": horizon // 2}},
        ),
        arm(
            "exchange",
            "60% of the history systems read another system's stored results (shared_memory_from).",
            {"exchange": {"fraction": 0.6}},
        ),
        arm(
            "exchange-colocated",
            "As exchange, readers chosen nearest to the writer's bay first.",
            {"exchange": {"fraction": 0.6, "placement": "colocated"}},
        ),
        arm(
            "exchange-stale",
            "As exchange, entries readable only 30 steps after they were written (old information).",
            {"exchange": {"fraction": 0.6, "quality": "stale", "delay": 30}},
        ),
        arm(
            "exchange-wrong",
            "As exchange, the writer's stored outcomes are permuted across entries at every read (wrong information).",
            {"exchange": {"fraction": 0.6, "quality": "wrong"}},
        ),
        arm(
            "inherit",
            "A history system starts late (middle of the run) and reads its predecessor's stored results.",
            {"inherit": {"start_at": horizon // 2}},
        ),
        arm(
            "views-closed",
            "One system's observed chambers are closed at 1/4 of the run and reopened at 3/4 (shrinking and expanding what it can investigate).",
            {
                "harness": [
                    {"at": horizon // 4, "do": "close_view", "system": "S000"},
                    {"at": 3 * horizon // 4, "do": "open_view", "system": "S000"},
                ]
            },
        ),
    ]
    return {
        "schema": SCHEMA,
        "title": "Research-system population: ten properties",
        "question": "Which of: independent histories, different observation conditions and boundaries, asynchronous activity, exchange of results, mutual "
        "change of conditions, resource competition, partial stop, inheritance, expansion and shrinking of what can be investigated, "
        "are present in a population of simulated research systems, and how do they change under each intervention?",
        "mode": "functional",
        "environment": {"kind": "lab-population", "horizon": horizon},
        "arms": arms,
        "seeds": {"gen_base": FUNCTIONAL_GEN[0], "engine_base": FUNCTIONAL_ENGINE[0], "n": n_seeds},
        "metrics": {
            "primary": ["requests"],
            "secondary": [
                "completed",
                "contention_rate",
                "history_overlap_mean",
                "distinct_conditions",
                "distinct_boundaries",
                "first_request_spread",
                "simultaneity",
                "exchange_reads",
                "external_coverage_drops",
                "isolations",
                "rate_ratio_after_before",
                "coverage_shrinks",
                "coverage_expansions",
                "variables_adopted",
                "reader_memory_hits",
                "reader_decisions_changed_by_memory",
                "reader_hit_rate",
                "store_entries_read",
                "messages",
            ],
        },
        "contrasts": [
            {"id": "C1", "a": "many", "b": "baseline", "varies": ["compute", "scenario"], "role": "secondary"},
            {"id": "C2", "a": "stop-30pct", "b": "baseline", "varies": ["scenario"], "role": "secondary"},
            {"id": "C3", "a": "exchange", "b": "baseline", "varies": ["scenario"], "role": "secondary"},
            {"id": "C4", "a": "inherit", "b": "baseline", "varies": ["scenario"], "role": "secondary"},
            {"id": "C6", "a": "exchange-stale", "b": "exchange", "varies": ["scenario"], "role": "secondary"},
            {"id": "C7", "a": "exchange-wrong", "b": "exchange", "varies": ["scenario"], "role": "secondary"},
            {"id": "C8", "a": "exchange-colocated", "b": "exchange", "varies": ["scenario"], "role": "secondary"},
            {"id": "C5", "a": "views-closed", "b": "baseline", "varies": ["scenario"], "role": "secondary"},
        ],
        "criteria": {"success": [], "failure": []},
        "stop": {"max_wall_seconds": 3600, "timeout_per_run_s": 600, "max_failures": 3},
        "budget": {"max_runs": 500, "procs": 2},
        "notes": "A functional check. The number of systems is a load, not a measure of autonomy; each property is a number computed from what the systems did.",
    }


def scarcity_study(
    n_seeds: int = 6,
    horizon: int = 600,
    mode: str = "functional",
    gen_base: int = FUNCTIONAL_GEN[0],
    engine_base: int = FUNCTIONAL_ENGINE[0],
) -> dict:
    """Failure, exhaustion, stop and revision of the revision rules under scarce measurement resources (functional template).

    Operations stay blind for lack of resources, the controller's rules keep failing to remove the blindness, meta-revision revises and finally
    exhausts them, and when every operation has ceased for an epoch the study of that run stops. Every outcome is recorded; none is presumed good."""

    def scarce(pool: float) -> dict:
        return {"resources": {"pool_per_step": pool}, "stop": {"all_ceased": True}}

    rec = {"mode": "recursive", "trace_reachability": True}
    meta = {**rec, "meta": True}
    arms = [
        _arm(
            "fixed-moderate",
            "History re-entry on, observation configuration never revised; moderately scarce measurement resources (0.5 per step).",
            settings=scarce(0.5),
        ),
        _arm(
            "recursive-moderate",
            "The HPO-003 controller reconfigures the instruments from the reasons for blindness; moderate scarcity.",
            controller=dict(rec),
            settings=scarce(0.5),
        ),
        _arm(
            "recursive-meta-moderate",
            "As recursive-moderate; the controller's own rule parameters are revised (and rules exhausted) when a rule's change did not remove its blindness twice in a row.",
            controller=meta,
            settings=scarce(0.5),
        ),
        _arm(
            "random-matched-moderate",
            "Random valid changes, the same number per epoch as recursive-moderate on the same seed.",
            controller={"mode": "random", "match_budget_of": "recursive-moderate", "trace_reachability": True},
            settings=scarce(0.5),
        ),
        _arm(
            "recursive-meta-severe",
            "As recursive-meta-moderate with severe scarcity (0.05 per step).",
            controller=meta,
            settings=scarce(0.05),
        ),
        _arm(
            "recursive-meta-none",
            "As recursive-meta-moderate with no measurement resources at all (0 per step): every measurement fails.",
            controller=meta,
            settings=scarce(0.0),
        ),
        _arm(
            "recursive-meta-abundant",
            "As recursive-meta-moderate with the default resources (2.4 per step): the reference for what scarcity does.",
            controller=meta,
            settings={"stop": {"all_ceased": True}},
        ),
    ]
    contrasts = [
        {"id": "C1", "a": "recursive-meta-moderate", "b": "recursive-moderate", "varies": ["meta_revision"], "role": "primary"},
        {
            "id": "C2",
            "a": "recursive-moderate",
            "b": "fixed-moderate",
            "varies": ["controller", "revision_authority"],
            "role": "secondary",
        },
        {"id": "C3", "a": "recursive-moderate", "b": "random-matched-moderate", "varies": ["controller"], "role": "secondary"},
        {"id": "C4", "a": "recursive-meta-severe", "b": "recursive-meta-moderate", "varies": ["compute"], "role": "secondary"},
        {"id": "C5", "a": "recursive-meta-none", "b": "recursive-meta-severe", "varies": ["compute"], "role": "secondary"},
        {"id": "C6", "a": "recursive-meta-moderate", "b": "recursive-meta-abundant", "varies": ["compute"], "role": "secondary"},
    ]
    return {
        "schema": SCHEMA,
        "title": "Revision failure, rule exhaustion, stop and meta-revision under scarce resources",
        "question": "When measurement resources are scarce and the controller's rules keep failing to remove blindness, what do rule revision, rule exhaustion and "
        "stopping do to what the operations can do afterwards?",
        "hypotheses": [
            {
                "id": "H1",
                "text": "Meta-revision of the rule parameters changes the controller's later changes (C1); no direction is assumed.",
                "contrasts": ["C1"],
            }
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
        "metrics": {
            "primary": ["fired_samples"],
            "secondary": [
                "unobservable_samples",
                "controller_changes",
                "controller_rejected",
                "meta_revisions",
                "meta_exhausted",
                "stopped_early",
                "stop_step",
                "ceased_share",
                "ignitions",
            ],
        },
        "contrasts": contrasts,
        "criteria": {"success": [], "failure": []},
        "stop": {"max_wall_seconds": 3600, "timeout_per_run_s": 300, "max_failures": 3},
        "budget": {"max_runs": 1000, "procs": 2},
        "notes": "Functional template. Scarcity is imposed by settings.resources.pool_per_step; a revision of the rules, an exhausted rule or a stop is a record, not evidence "
        "of improvement or failure of any theory.",
    }


def preregistration(
    doc: dict,
    *,
    hypothesis: str,
    falsification: list[str],
    assumed_sd: dict,
    min_effect: dict,
    source: str,
    provenance: list[dict] | None = None,
    exploratory_seeds: list | None = None,
    multiplicity: str = "Holm",
    equivalence_margin: float = 0.05,
    alpha: float = 0.05,
    power: float = 0.8,
) -> dict:
    """A preregistration block from explicit inputs (nothing is invented: the hypothesis, the falsification conditions, the assumed spreads and
    minimal effects and their source are the researcher's). Stopping rules and storage are taken from the protocol itself."""
    from .protocol import seed_list

    return {
        "central_hypothesis": hypothesis,
        "falsification": falsification,
        "power": {
            "n_per_arm": len(seed_list(doc)),
            "assumed_sd": assumed_sd,
            "min_effect": min_effect,
            "alpha": alpha,
            "power": power,
            "source": source,
        },
        "analysis_plan": {
            "primary": list(doc["metrics"]["primary"]),
            "secondary": list(doc["metrics"].get("secondary", [])),
            "multiplicity": multiplicity,
            "equivalence_margin": equivalence_margin,
            "sensitivity": [
                "leave-one-seed-out range of the mean difference",
                "sign agreement",
                "Wilcoxon signed-rank",
                "with / without Tukey outliers",
            ],
            "estimation": "paired differences by seed; bootstrap 95% interval; Cohen's dz; sign-flip permutation p; Holm / BH over every declared contrast x metric",
        },
        "stopping_rules": [
            f"per-run timeout {doc['stop']['timeout_per_run_s']} s, wall-clock budget {doc['stop']['max_wall_seconds']} s, at most {doc['stop'].get('max_failures', 3)} failed runs",
            "no optional stopping: the number of seeds is fixed; a stopped study is resumed, never re-planned from partial results",
        ],
        "data_storage": "every run record, the log, the manifest and the registered protocol are kept under the experiment directory; failed and timed-out runs are kept and counted",
        "separation": {
            "exploratory_seeds": exploratory_seeds or [],
            "confirmatory": "the seeds of this protocol; disjoint from every exploratory and functional seed",
        },
        "condition_provenance": provenance or [],
    }


def level2_confirmatory(n_seeds: int = 200) -> dict:
    """DRAFT protocol for the Level 2 question — NOT frozen and NOT run. Does result-driven revision of the observation configuration, and revision of
    its own rules, change what the operations do afterwards, under moderately scarce measurement resources? Sized from the spreads of a functional study
    (docs/level2/exploration_inputs), distrusting its small sample (upper 95% bound of each standard deviation).

    The run is a high-cost computation (about half a million step-runs): approval.high_cost is NOT granted here; the protocol must be frozen (registered)
    and approved before any run. Conditions that were chosen after looking at exploratory data say so in preregistration.condition_provenance."""
    from . import power as W

    mean_ctl = 293.0  # mean fired samples of the control arm in the functional scarcity study
    sd = {
        "C1 meta vs recursive": W.sd_upper(11.84, 5),
        "C2 recursive vs fixed": W.sd_upper(131.1, 5),
        "C3 recursive vs random-matched": W.sd_upper(275.9, 5),
    }
    eff = {
        "C1 meta vs recursive": 0.05 * mean_ctl,
        "C2 recursive vs fixed": 0.20 * mean_ctl,
        "C3 recursive vs random-matched": 0.20 * mean_ctl,
    }
    need = {k: W.sample_size_paired(sd[k], eff[k]) for k in sd}
    base = scarcity_study(n_seeds, 600, "confirmatory", 20000, 200000)
    keep = {"fixed-moderate", "recursive-moderate", "recursive-meta-moderate", "random-matched-moderate"}
    base["arms"] = [a for a in base["arms"] if a["name"] in keep]
    base["contrasts"] = [c for c in base["contrasts"] if c["id"] in ("C1", "C2", "C3")]
    base["title"] = (
        "Level 2: revision of the observation configuration and of its rules under scarce resources (confirmatory, DRAFT)"
    )
    base["question"] = (
        "Does result-driven revision of the observation configuration (and revision of the revision rules) change what operations do afterwards, compared with no "
        "revision, with matched random revision and with revision without rule revision, under moderate scarcity of measurement resources?"
    )
    base["hypotheses"] = [
        {
            "id": "H1",
            "text": "Revising the controller's own rules changes later fired samples (C1; two-sided).",
            "contrasts": ["C1"],
        },
        {
            "id": "H2",
            "text": "Result-driven revision changes later fired samples relative to no revision (C2; two-sided).",
            "contrasts": ["C2"],
        },
        {
            "id": "H3",
            "text": "Result-driven revision differs from matched random revision (C3; secondary, underpowered: reported with its interval only).",
            "contrasts": ["C3"],
        },
    ]
    base["metrics"] = {
        "primary": ["fired_samples"],
        "secondary": [
            "unobservable_samples",
            "controller_changes",
            "controller_rejected",
            "meta_revisions",
            "meta_exhausted",
            "measure_cost",
            "stopped_early",
            "ceased_share",
        ],
    }
    base["criteria"] = {
        "success": [
            {
                "contrast": "C1",
                "metric": "fired_samples",
                "direction": "different",
                "min_relative_effect": 0.05,
                "ci_excludes_zero": True,
            },
            {
                "contrast": "C2",
                "metric": "fired_samples",
                "direction": "different",
                "min_relative_effect": 0.20,
                "ci_excludes_zero": True,
            },
        ],
        "failure": [
            {
                "contrast": "C1",
                "metric": "fired_samples",
                "direction": "equivalent",
                "min_relative_effect": 0.0,
                "ci_excludes_zero": False,
            },
            {
                "contrast": "C2",
                "metric": "fired_samples",
                "direction": "equivalent",
                "min_relative_effect": 0.0,
                "ci_excludes_zero": False,
            },
        ],
    }
    base["stop"] = {"max_wall_seconds": 21600, "timeout_per_run_s": 300, "max_failures": 20}
    base["budget"] = {"max_runs": 1000, "procs": 4}
    base["approval"] = {
        "high_cost": False,
        "note": "REQUIRED and NOT GRANTED: about half a million step-runs; the researcher must approve before the protocol is created for running",
    }
    base["status"] = "DRAFT: not frozen, not run, nothing about its outcome is known or assumed"
    base["planning"] = {
        "assumed_sd_upper95": sd,
        "min_effect": eff,
        "pairs_needed_for_80pct_power": need,
        "n_per_arm": n_seeds,
        "underpowered": [k for k in need if need[k] > n_seeds],
        "source": "docs/level2/exploration_inputs/scarcity_functional_summary.json (functional run, 6 seeds, reserved range)",
    }
    prov = [
        {
            "condition": f"arm {a['name']}: settings.resources.pool_per_step 0.5, stop.all_ceased true, horizon 600",
            "derived_from": "exploration",
            "source": "scarcity-study (functional, seeds 7000-7005): 0.5 per step is where blindness persisted enough for rules to fail and be revised without total blindness; "
            "the value was chosen after looking at those runs",
        }
        for a in base["arms"]
    ]
    base["preregistration"] = preregistration(
        base,
        hypothesis="Under moderate scarcity, revising the observation configuration from the reasons operations were blind, and revising the controller's rules when they "
        "keep failing, changes the number of fired samples relative to the stated controls. No direction is assumed; equivalence is an equally valid result.",
        falsification=[
            "C1: the 95% interval of the paired difference in fired samples (recursive-meta vs recursive) lies inside +/-5% of the control mean: no detectable effect of rule revision",
            "C2: the interval (recursive vs fixed) lies inside +/-20%: no detectable effect of result-driven revision of that size",
            "any registered contrast whose interval includes zero and the margin is reported as unresolved, never as support",
        ],
        assumed_sd=sd,
        min_effect=eff,
        source=base["planning"]["source"] + "; upper 95% bound of each SD (chi-square, df 5)",
        provenance=prov,
        exploratory_seeds=[[7000 + i, 70000 + i] for i in range(6)],
        multiplicity="Holm",
        equivalence_margin=0.05,
    )
    return base


TEMPLATES = {
    "revision-study": revision_study,
    "quick": quick,
    "lab-population": lab_population_study,
    "ards-comparison": ards_comparison,
    "shared-comparison": shared_comparison,
    "multi-system": multi_system,
    "scarcity-study": scarcity_study,
    "level2-confirmatory": level2_confirmatory,
}


def template(name: str, **kw) -> dict:
    return copy.deepcopy(TEMPLATES[name](**kw))
