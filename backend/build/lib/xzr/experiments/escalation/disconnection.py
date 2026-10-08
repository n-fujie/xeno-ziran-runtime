"""Targeted disconnection study.

Eight structures in which disconnection should matter if it is operationally non-redundant (the connections that
carry flow between parts are weak, so they dissolve when they carry flow without penetrating). No reasoning layer.

Variants (runtime flags): C = disconnection active (reference); off = removed; weight_zero = the dissolved
connection stays with weight 0; as_cut = executed by the cut operation; as_mutation = removal through the generic
mutation path; redirect = generic connection mutation (redirect to a random configuration, weight reset).

Only downstream effects count: the disconnection events themselves, removal/cut/reconfiguration counts, connection
counts, out-degree and the reachable-connection share are excluded (they differ by construction between variants
that keep, remove or relabel a connection).
"""

from __future__ import annotations

from ...scenario.topologies import DISCONNECTION_STRUCTURES
from .harness import RESULTS, condition
from .runner import run_conditions

VARIANTS = {"C": {}, "off": {"disconnect": "off"}, "weight_zero": {"disconnect": "weight_zero"},
            "as_cut": {"disconnect": "as_cut"}, "as_mutation": {"disconnect": "as_mutation"},
            "redirect": {"disconnect": "redirect"}}
OWN = {"removed", "cuts", "reconfigurations", "alive_connections", "reachable_share", "degree"}


def conditions() -> list[dict]:
    out = []
    for k in DISCONNECTION_STRUCTURES:
        c = condition(id=f"disconnection:{k}", disconnection=k, flag_variants=VARIANTS, variants=tuple(VARIANTS),
                      enabling=False, triggers=(), reasoning_from=0)
        c["factor"], c["level"] = "disconnection structure", k
        out.append(c)
    return out


def main(procs: int = 7) -> dict:
    return run_conditions(conditions(), RESULTS / "disconnection.json", procs,
                          meta={"variants": VARIANTS, "own_outputs_excluded": sorted(OWN)},
                          exclude=lambda c: OWN)
