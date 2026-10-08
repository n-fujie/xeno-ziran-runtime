"""Cut / reconfiguration trigger distinction.

Variants (runtime flags; no reasoning layer): C = separate triggers (reference); cut_only (reconfiguration off);
reconfigure_only (cut off); unified (one connection-level trigger, one redirect operation); generic_conditions
(both conditions, both executed as generic connection mutation); merged (one configuration-level condition, one
remove-and-create operation). Regimes: the default field, a churn regime, long memory, and four topologies.
Own outputs excluded: cut, removal and reconfiguration event counts.
"""

from __future__ import annotations

from .harness import RESULTS, condition
from .runner import run_conditions

VARIANTS = {"C": {}, "cut_only": {"reconfigure": "off"}, "reconfigure_only": {"cut": "off"},
            "unified": {"topology_trigger": "unified"}, "generic_conditions": {"topology_trigger": "generic_conditions"},
            "merged": {"topology_trigger": "merged"}}
OWN = {"removed", "cuts", "reconfigurations"}
REGIMES = {"default": {}, "long_memory": {"memory": "long"}, "high_mutation": {"mutation": "high_topology"},
           "bottlenecked": {"topology": "bottlenecked"}, "modular": {"topology": "modular"},
           "small_world": {"topology": "small_world"}, "dense_random": {"topology": "dense_random"}}


def conditions() -> list[dict]:
    out = []
    for name, over in REGIMES.items():
        c = condition(id=f"topology_trigger:{name}", flag_variants=VARIANTS, variants=tuple(VARIANTS),
                      enabling=False, triggers=(), reasoning_from=0, **over)
        c["factor"], c["level"] = "regime", name
        out.append(c)
    return out


def main(procs: int = 7) -> dict:
    return run_conditions(conditions(), RESULTS / "topology_triggers.json", procs,
                          meta={"variants": VARIANTS, "own_outputs_excluded": sorted(OWN)}, exclude=lambda c: OWN)
