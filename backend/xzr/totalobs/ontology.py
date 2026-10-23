"""Layers of what exists in a run, and what the record is allowed to claim.

The model state is not reality as a whole. A run's ledger keeps eight things apart, so that no later reading can quietly merge them:

    1 object transitions that go on whether or not anything observes (the world's own dynamics: sources, spreading, decay)
    2 the observing system's own transitions (health, failure, outage)
    3 the interaction of observer and object (absorption by observation, wear by activity)
    4 changes made by intervention (injected activity and the marks it leaves)
    5 the state of the recording mechanism (stored, in transit, lost)
    6 material consequences that remain after the records of their cause are gone
    7 what the research agent can obtain (the hub's records)
    8 what has been constructed from 7 (identified objects, hypotheses, derived variables, evaluation outcomes)

Layers 1-6 are read by the verifier only. Layer 7 is the agent's whole access. Layer 8 consists of constructions of a configuration and is flagged as
such. ``scope_audit`` checks a run record for the claims it must not make.
"""

from __future__ import annotations

LAYERS = (
    ("object_transitions", "verifier", "world dynamics that proceed without observation"),
    ("observer_transitions", "verifier", "sensor health, failure, communication outage"),
    ("interaction", "verifier", "absorption by observation and wear of the observer by the object"),
    ("interventions", "verifier", "injected activity and the marks it leaves"),
    ("recording", "verifier", "records stored, in transit, lost"),
    ("residual_consequences", "verifier", "material state that outlives the records of its cause"),
    ("agent_access", "agent", "the hub's records: the only access of the research agent"),
    (
        "constructions",
        "agent",
        "identified objects, hypotheses, derived variables, evaluation outcomes: constructs of a configuration",
    ),
)
FORBIDDEN_AGENT_KEYS = {"u", "m", "true_objects", "truth", "world_state", "marks"}
CLAIMS = {
    "model_state_is_reality": False,
    "reality_as_whole_represented": False,
    "earth_claim": False,
    "local_observation_generalised_to_whole": False,
    "statement": (
        "The state read by the verifier is the state of a finite synthetic model. It is not reality as a whole, and what the agent identifies is a construction "
        "of its observing configuration, not the model's state and not a fact about the world beyond the model."
    ),
}


def ledger(world, net, view_n: int, agent_summary: dict) -> dict:
    """The eight layers at one moment. ``world`` and ``net`` are read here (verifier side); ``agent_summary`` is what the agent holds."""
    import numpy as np

    marks = float(np.sum(world.m))
    return {
        "t": int(world.t),
        "layers": {
            "object_transitions": {
                "reader": "verifier",
                "sources": int(len(world.src_region)),
                "world_events": len(world.events),
                "activity_total": round(float(world.u.sum()), 4),
            },
            "observer_transitions": {
                "reader": "verifier",
                "sensors": len(net.sensors),
                "alive": sum(s.alive for s in net.sensors.values()),
                "outage_regions": len(net.cut_zone),
                "expired": int(net.stats["expired"]),
            },
            "interaction": {
                "reader": "verifier",
                "absorbed_activity": round(net.stats["interference"], 4),
                "health": {k: round(s.health, 3) for k, s in sorted(net.sensors.items())},
            },
            "interventions": {
                "reader": "verifier",
                "marks_total": round(marks, 4),
                "marked_regions": int((world.m > 1e-3).sum()),
            },
            "recording": {
                "reader": "verifier",
                "stored": len(net.store),
                "lost_in_transit": int(net.stats["lost_in_transit"]),
                "records_lost": int(net.stats["records_lost"]),
            },
            "residual_consequences": {"reader": "verifier", "marks_total": round(marks, 4), "records_of_cause_present": None},
            "agent_access": {"reader": "agent", "records_in_view": view_n},
            "constructions": {"reader": "agent", "constructed": True, **agent_summary},
        },
        "claims": dict(CLAIMS),
    }


def scope_audit(record: dict) -> list[str]:
    """Problems with a run record's ontological scope (empty = none found): missing layers, truth fields in the agent's layers, a claim that must be false."""
    out: list[str] = []
    led = record.get("ledger")
    if not led:
        return ["no ledger in the record"]
    names = [n for n, _, _ in LAYERS]
    missing = [n for n in names if n not in led.get("layers", {})]
    if missing:
        out.append(f"layers missing: {missing}")
    for n, reader, _ in LAYERS:
        layer = led.get("layers", {}).get(n, {})
        if layer.get("reader") != reader:
            out.append(f"layer {n}: reader should be {reader}")
        if reader == "agent" and FORBIDDEN_AGENT_KEYS & set(layer):
            out.append(f"layer {n}: carries world-state fields {sorted(FORBIDDEN_AGENT_KEYS & set(layer))}")
    if not led.get("layers", {}).get("constructions", {}).get("constructed"):
        out.append("constructions are not flagged as constructed")
    cl = led.get("claims", {})
    for k in ("model_state_is_reality", "reality_as_whole_represented", "earth_claim", "local_observation_generalised_to_whole"):
        if cl.get(k) is not False:
            out.append(f"claim {k} must be false")
    return out
