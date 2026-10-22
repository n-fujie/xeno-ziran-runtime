"""The research operations of the shared environment, and who may use which.

One table for ARDS arms and the HPO arm: each operation is either *shared* (available to every arm of the study, mapped to the same
observation-configuration vocabulary) or *arm-internal* (a capability one method has and another has not), or *not available* in this
environment (named, so that nothing is silently assumed). Access is declared per arm in the study protocol and checked from what the arm's
own record says it did.
"""

from __future__ import annotations

# operation → (description, status in environment env3, vocabulary entry or note)
OPERATIONS: dict[str, dict] = {
    "observe": {
        "description": "run experiments (paired baseline / altered worlds, n seeds) and read the instruments",
        "status": "shared",
        "via": "ObserveService.observe",
    },
    "sensor-change": {"description": "add an instrument channel (device)", "status": "shared", "via": "add-device"},
    "noise-change": {"description": "lower the instrument's noise", "status": "shared", "via": "sensor-noise"},
    "time-resolution-change": {
        "description": "raise the sampling rate (shorter period)",
        "status": "shared",
        "via": "sample-rate",
    },
    "scale-change": {
        "description": "raise the spatial resolution (hierarchy level)",
        "status": "shared",
        "via": "spatial-resolution",
    },
    "time-window-change": {"description": "narrow or widen the aggregation window", "status": "shared", "via": "temporal-window"},
    "capability-query": {
        "description": "ask which differences a configuration could carry (the observer's model of its own instruments)",
        "status": "shared",
        "via": "ObserveService.capability",
    },
    "external-memory": {
        "description": "keep and read the results of earlier experiments",
        "status": "arm-internal",
        "via": "ARDS memory (V2-PA, V1-B/PA); HPO arm: history of earlier cycles",
    },
    "history-reinjection": {
        "description": "use stored results to plan the next experiment",
        "status": "arm-internal",
        "via": "reinjection factor (own / none); HPO arm: history on / off",
    },
    "rule-revision": {
        "description": "revise the arm's own revision rules",
        "status": "arm-internal",
        "via": "V2-PA-meta; HPO arm: meta-revision",
    },
    "variable-generation": {
        "description": "create a new observable variable",
        "status": "not available",
        "via": "no new difference or channel can be defined by an arm in this environment (the catalog is fixed)",
    },
    "boundary-change": {
        "description": "change the boundary an instrument penetrates (veils)",
        "status": "not available",
        "via": "no veils in this environment; the 'boundary-invisible' reason is a too-short window",
    },
    "intervention": {
        "description": "act on the observed system",
        "status": "not available",
        "via": "arms observe paired worlds; alterations are fixed by the study, not chosen by an arm",
    },
    "evaluation-change": {
        "description": "change the evaluation conditions",
        "status": "not available",
        "via": "held-out evaluation is fixed by the study and run by ARDS's own code",
    },
}
SHARED = tuple(k for k, v in OPERATIONS.items() if v["status"] == "shared")
REVISION_OPS = (
    "add-device",
    "sensor-noise",
    "sample-rate",
    "spatial-resolution",
    "temporal-window",
)  # ARDS's REVISION_VOCABULARY


def access(arm_kind: str, spec: dict) -> dict:
    """Operations an arm may use. ARDS arms: from ARDS's registry (reads / mayRevise / factors). HPO arm: from its declaration."""
    if arm_kind == "ards":
        revise = set(spec.get("mayRevise", []))
        f = spec.get("factors", {})
        return {
            "observe": True,
            "capability-query": spec.get("reads") != "nothing",
            **{k: v["via"] in revise for k, v in OPERATIONS.items() if v["status"] == "shared" and v["via"] in REVISION_OPS},
            "external-memory": f.get("retention") == "memory",
            "history-reinjection": f.get("reinjection") in ("own", "shuffled", "uninformative"),
            "rule-revision": f.get("ruleRevision") == "meta",
        }
    return {
        "observe": True,
        "capability-query": True,
        **{k: True for k, v in OPERATIONS.items() if v["status"] == "shared" and v["via"] in REVISION_OPS},
        "external-memory": bool(spec.get("history", True)),
        "history-reinjection": bool(spec.get("history", True)),
        "rule-revision": bool(spec.get("meta", False)),
    }
