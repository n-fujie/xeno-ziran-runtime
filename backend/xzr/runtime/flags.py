"""Runtime feature flags for primitive ablation and reduction.

Every flag names one candidate reduction or ablation of an operation. ``Flags()`` (all defaults) is the full
runtime and is bit-identical to the unflagged implementation. Reduced implementations live alongside the
original ones; nothing is deleted.

Values
------
threshold         "on" | "off"            off: every configuration with difference > 0 emits every step (continuous
                                           transition; no threshold, no refractory period)
fused_transition  bool                     ignition + propagation computed as one thresholded-transition operation
retention         "on" | "off"            off: non-emitted difference is not kept between steps
memory            "on" | "off"            off: the ignition trace is not recorded (no threshold shift, no
                                           memory-gated connection)
transform         "on" | "off"            off: form rewriting is not performed
wave_state        "on" | "off"            off: the runtime keeps only the dominant incoming connection; wave origin,
                                           depth and returns are not tracked (an observer can reconstruct them)
return_events     "on" | "off"            off: return events are not emitted
adapt_source      "dominant" | "all_carriers" | "off"
                                           which connections are strengthened by a successful transition
reconfigure       "redirect" | "mutation" | "off"
                                           mutation: implemented as removal + creation of connections
cut, connect      "on" | "off"
disconnect        "on" | "off" | "weight_zero" | "as_cut" | "as_mutation" | "redirect"
                                           replacements of disconnection (same trigger, weight < w_min):
                                           weight_zero  the connection stays, with weight and base weight set to 0
                                           as_cut       executed by the cut operation (reported as a cut)
                                           as_mutation  removal through the generic mutation path (retired slot)
                                           redirect     generic connection mutation: redirected to a uniformly
                                                        random configuration, weight reset to its base value
topology_trigger  "separate" | "unified" | "generic_conditions" | "merged"
                                           separate            cut (connection load > capacity → remove) and
                                                               reconfiguration (overload streak → redirect)
                                           unified             one trigger (connection load > capacity), one
                                                               operation: redirect that connection past its target
                                           generic_conditions  both conditions kept; both executed as generic
                                                               connection mutation (remove; remove + create)
                                           merged              one condition per configuration (an overloaded
                                                               outgoing connection, or an overload streak) → remove
                                                               its most loaded connection and create one to a
                                                               second-order neighbour
difference        "node" | "relational"   relational: difference is held on connections (plus one self-held term per
                                           configuration); the per-configuration value is recomputed as their sum
transition        "on" | "off"            off: no emission along connections at all
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace


@dataclass(frozen=True)
class Flags:
    threshold: str = "on"
    fused_transition: bool = False
    retention: str = "on"
    memory: str = "on"
    transform: str = "on"
    wave_state: str = "on"
    return_events: str = "on"
    adapt_source: str = "dominant"
    reconfigure: str = "redirect"
    cut: str = "on"
    disconnect: str = "on"
    connect: str = "on"
    difference: str = "node"
    transition: str = "on"
    topology_trigger: str = "separate"

    _CHOICES = {
        "threshold": ("on", "off"), "retention": ("on", "off"), "memory": ("on", "off"),
        "transform": ("on", "off"), "wave_state": ("on", "off"), "return_events": ("on", "off"),
        "adapt_source": ("dominant", "all_carriers", "off"), "reconfigure": ("redirect", "mutation", "off"),
        "cut": ("on", "off"), "connect": ("on", "off"),
        "disconnect": ("on", "off", "weight_zero", "as_cut", "as_mutation", "redirect"),
        "difference": ("node", "relational"), "transition": ("on", "off"),
        "topology_trigger": ("separate", "unified", "generic_conditions", "merged"),
    }

    def __post_init__(self) -> None:
        for f in fields(self):
            if f.name.startswith("_") or f.name == "fused_transition":
                continue
            v = getattr(self, f.name)
            if v not in self._CHOICES[f.name]:
                raise ValueError(f"flag {f.name}={v!r}; expected one of {self._CHOICES[f.name]}")

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    def with_(self, **kw) -> Flags:
        return replace(self, **kw)

    def is_full(self) -> bool:
        return self == Flags()

    @classmethod
    def from_dict(cls, d: dict | None) -> Flags:
        return cls(**(d or {}))


FULL = Flags()

# Minimal runtime (candidate until verified by the reduction study's full-vs-minimal comparison; see
# docs/MINIMAL_RUNTIME.md). Only reductions the study supports:
#   fused_transition   ignition is the gate of transition (bit-identical)
#   transform off      transformation is read by nothing (bit-identical apart from its own label)
#   wave_state off     origin/depth/returns reconstructed exactly by shapes/waves.py (observer-side)
#   return_events off  return is observer-side (reconstructed by the same observer)
#   reconfigure        reconfiguration expressed as connection mutation (remove + create)
MINIMAL = Flags(fused_transition=True, transform="off", wave_state="off", return_events="off", reconfigure="mutation")
