"""Multiple interacting reasoning clusters.

Worlds with several reasoning clusters (each cluster's items bind to its own regions: region r belongs to cluster
r mod k). The structural comparisons (D, E, F, G, I, K, A against C) are repeated under eleven interaction
settings, to test whether structural differences become more visible in interacting systems than in an isolated
single-cluster world (the matrix reference and ``structure:multiple_clusters`` conditions).
"""

from __future__ import annotations

from .harness import RESULTS, condition
from .runner import run_conditions

VARIANTS = ("A", "C", "D", "E", "F", "G", "I", "K")
SETTINGS: dict[str, dict] = {
    "independent": {"topology": "weakly_connected", "structure": "multiple_clusters"},
    "weakly_connected": {"topology": "modular", "p_in": 0.95, "structure": "multiple_clusters"},
    "strongly_interacting": {"topology": "modular", "p_in": 0.6, "structure": "multiple_clusters"},
    "competing": {"topology": "modular", "structure": "competing_clusters"},
    "different_fixpoints": {"topology": "modular", "structure": "mixed_fixpoint_regions"},
    "different_memory_persistence": {"topology": "modular", "structure": "multiple_clusters", "cluster_memory": True},
    "merging": {"topology": "modular", "structure": "multiple_clusters",
                "world_schedule": ({"t": 0.5, "op": "open"},)},
    "splitting": {"topology": "modular", "structure": "multiple_clusters",
                  "world_schedule": ({"t": 0.5, "op": "close"},)},
    "losing_shared_addressability": {"topology": "modular", "structure": "multiple_clusters",
                                     "world_schedule": ({"t": 0.5, "op": "unstable"},)},
    "sharing_records": {"topology": "modular", "structure": "partially_incompatible_rules"},
    "overwriting_records": {"topology": "modular", "structure": "multiple_clusters",
                            "triggers": ("memory_level", "mismatch", "failed_intervention", "overwrite")},
}


def conditions() -> list[dict]:
    out = []
    for name, over in SETTINGS.items():
        c = condition(id=f"clusters:{name}", variants=VARIANTS, **over)
        c["factor"], c["level"] = "cluster interaction", name
        out.append(c)
    return out


def main(procs: int = 7) -> dict:
    return run_conditions(conditions(), RESULTS / "clusters.json", procs, meta={"settings": {
        k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in SETTINGS.items()}})
