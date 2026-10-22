"""Populations of scientific systems for the shared laboratory (20 to 300 systems, staged).

A population is a deterministic list of ``SystemSpec`` configurations over the laboratory's chambers: kinds are dealt
round-robin (local, distributed, history), homes and sensor chambers are spread over the macro bays, and the optional
capacities (observation revision, variable generation, parameter adaptation) are dealt in a fixed pattern so that a
population is heterogeneous without any randomness. The number of systems says how much the laboratory is loaded; it
says nothing about how autonomous any of them is (docs/ZRS_INTEGRATION_STATUS.md).
"""

from __future__ import annotations

KINDS = ("local", "distributed", "history")
MACROS, SUBS = 8, 4  # the laboratory has 8 bays of 4 chambers (apparatus.chambers)
STAGES = (3, 20, 50, 100, 300)  # staged load: each stage is run and checked before the next is attempted


def population(n: int, *, capacities: bool = True) -> list[dict]:
    """``n`` system configurations (dicts accepted by ``SystemSpec(**d)``), deterministic in ``n``."""
    if n < 1:
        raise ValueError("a population needs at least one system")
    out = []
    for i in range(n):
        m, s = (i // SUBS) % MACROS, i % SUBS
        home = f"{m}.{s}"
        kind = KINDS[i % len(KINDS)]
        d: dict = {"sid": f"S{i:03d}", "kind": kind, "home": home}
        if kind == "distributed":
            d["sensors"] = [home, f"{(m + 1) % MACROS}.{(s + 1) % SUBS}", f"{(m + 2) % MACROS}.{(s + 2) % SUBS}"]
        elif kind == "history":
            d.update(memory="ordinary", store=f"{m}.{(s + 1) % SUBS}")
        if capacities:
            d["revise_observation"] = i % 2 == 0
            d["generate_variables"] = i % 4 == 0
            d["adapt_parameters"] = i % 5 == 0
        out.append(d)
    return out
