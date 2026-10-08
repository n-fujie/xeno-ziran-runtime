"""Primitive catalog: definition, implementation location and dependent tests for each candidate primitive.

The *status* and *evidence* are not written here: they are read from the reduction study's result file, so the
inspector can only show what the experiments established.
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "experiments" / "results"

CATALOG: list[dict] = [
    {"primitive": "Ignition (as a separate operation)", "name": "Ignition",
     "definition": "A configuration whose difference reaches its effective threshold emits (and becomes refractory).",
     "implementation": ["runtime/ops.py:ignite", "runtime/ops.py:thresholded_transition (reduced, flag fused_transition)"],
     "flags": ["fused_transition"],
     "tests": ["test_fused_transition_is_bit_identical", "test_ignition_threshold_and_refractory"]},
    {"primitive": "Threshold gating (ignition condition)", "name": "Threshold gating",
     "definition": "The nonlinearity deciding which configurations transition this step.",
     "implementation": ["runtime/ops.py:ignite (threshold=True)", "runtime/state.py:State.theta_eff"],
     "flags": ["threshold"], "tests": ["test_ablations_that_matter_do_change_the_trajectory"]},
    {"primitive": "Transition", "name": "Transition",
     "definition": "Emission of difference along reachable connections, normalized, with gain and load-dependent conduction.",
     "implementation": ["runtime/ops.py:propagate"], "flags": ["transition"],
     "tests": ["test_penetration_carries_wave_origin_and_depth", "test_ablations_that_matter_do_change_the_trajectory"]},
    {"primitive": "Retention", "name": "Retention",
     "definition": "The fraction of non-emitted difference a configuration keeps between steps (ignition keeps less).",
     "implementation": ["runtime/ops.py:retain_and_decay"], "flags": ["retention"],
     "tests": ["test_retention_and_decay_event", "test_trajectory_distances_detect_structural_change"]},
    {"primitive": "Memory", "name": "Memory",
     "definition": "A decaying trace of past ignitions; shifts the effective threshold and gates connection closure.",
     "implementation": ["runtime/ops.py:remember", "runtime/state.py:State.theta_eff", "runtime/ops.py:connect"],
     "flags": ["memory"], "tests": ["test_memory_lowers_effective_threshold_and_is_counted"]},
    {"primitive": "Transformation", "name": "Transformation",
     "definition": "A dominant flow through a form-rewriting connection changes the receiver's form label.",
     "implementation": ["runtime/ops.py:transform"], "flags": ["transform"],
     "tests": ["test_transformation_rewrites_form", "test_transformation_has_no_downstream_effect"]},
    {"primitive": "Penetration", "name": "Penetration",
     "definition": "An ignition caused through a connection: the dominant incoming connection of a configuration that "
                   "passed its threshold, annotated with wave origin and depth.",
     "implementation": ["runtime/ops.py:ignite / propagate (cause_edge)", "shapes/waves.py:WaveObserver (reconstruction)"],
     "flags": ["wave_state", "adapt_source"], "tests": ["test_wave_state_is_reconstructed_exactly_outside_the_runtime"]},
    {"primitive": "Return", "name": "Return",
     "definition": "An ignition whose causal wave originated at the same configuration.",
     "implementation": ["runtime/ops.py:ignite", "shapes/waves.py:WaveObserver"], "flags": ["return_events"],
     "tests": ["test_return_on_a_loop", "test_return_detection_has_no_downstream_effect"]},
    {"primitive": "Reconfiguration", "name": "Reconfiguration",
     "definition": "An overloaded configuration redirects its strongest connection to a second-order neighbour.",
     "implementation": ["runtime/ops.py:reconfigure", "runtime/ops.py:reconfigure_by_mutation (reduced)"],
     "flags": ["reconfigure"], "tests": ["test_reconfiguration_redirects_strongest_connection",
                                        "test_reconfiguration_as_mutation_retires_and_creates"]},
    {"primitive": "Difference", "name": "Difference",
     "definition": "The magnitude a configuration currently holds; what ignites, is emitted and is retained.",
     "implementation": ["runtime/state.py:State.diff", "runtime/relational.py (difference on connections, reduced)"],
     "flags": ["difference"], "tests": ["test_relational_difference_tracks_node_difference"]},
    {"primitive": "Reachability", "name": "Reachability",
     "definition": "Which transitions are currently usable: alive ∧ permeable ∧ target not frozen.",
     "implementation": ["runtime/state.py:State.reachable_mask (computed)", "shapes/metrics.py (reach metrics)"],
     "flags": [], "tests": ["test_reachability_horizon_and_closure_respect_gates"]},
    {"primitive": "Cut", "name": "Cut", "definition": "An overloaded connection breaks.",
     "implementation": ["runtime/ops.py:cut"], "flags": ["cut"], "tests": ["test_overload_cuts_connection"]},
    {"primitive": "Disconnection", "name": "Disconnection", "definition": "A connection whose weight dissolved is removed.",
     "implementation": ["runtime/ops.py:disconnect"], "flags": ["disconnect"], "tests": ["test_weak_connection_disconnects"]},
    {"primitive": "Connection (closure)", "name": "Connection",
     "definition": "Co-igniting, memory-bearing configurations form a connection to a second-order neighbour.",
     "implementation": ["runtime/ops.py:connect", "runtime/ops.py:add_connection"], "flags": ["connect"],
     "tests": ["test_triadic_connect_creates_new_connection"]},
    {"primitive": "Weight adaptation", "name": "Weight adaptation",
     "definition": "Connections that caused an ignition strengthen; carriers that did not, weaken.",
     "implementation": ["runtime/ops.py:adapt_weights", "runtime/ops.py:successful_carriers (variant)"],
     "flags": ["adapt_source"], "tests": []},
    {"primitive": "Decay", "name": "Decay", "definition": "A difference falling below a small threshold (an event label).",
     "implementation": ["runtime/ops.py:retain_and_decay (event only)"], "flags": [],
     "tests": ["test_retention_and_decay_event"]},
]


def primitives() -> list[dict]:
    """Catalog entries joined with the latest reduction classification (if the study has been run)."""
    p = RESULTS / "reduction.json"
    rows = {}
    if p.exists():
        rows = {r["primitive"]: r for r in json.loads(p.read_text()).get("classification", [])}
    out = []
    for c in CATALOG:
        r = rows.get(c["primitive"], {})
        out.append({**c, "status": r.get("status", "NOT RUN"), "question": r.get("question"), "rule": r.get("rule"),
                    "reduced_to": r.get("reduced_to"), "diverges_in": r.get("diverges_in"),
                    "why_unresolved": r.get("why_unresolved"), "evidence": r.get("evidence", [])})
    return out
