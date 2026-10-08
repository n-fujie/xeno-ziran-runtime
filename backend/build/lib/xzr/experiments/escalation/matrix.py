"""The resolution matrix: one-factor-at-a-time sweeps around a reference condition, targeted crossings, larger
worlds, longer horizons and a statistical-power escalation.

The full factorial (3 sizes × 3 horizons × 10 topologies × 7 memory regimes × 3 couplings × 5 mutation regimes
× 5 return structures × 4 addressability regimes × 15 structures × 5 graph sizes) is not run; what is run, and what
is omitted, is listed by ``design()`` and written into the result file.
"""

from __future__ import annotations

from ...reasonlab.structures import SIZES, STRUCTURES
from ...scenario.topologies import MEMORY_REGIMES, RETURN_STRUCTURES, TOPOLOGIES
from .harness import MUTATION, REFERENCE, condition

CORE = ("A", "C", "D", "E", "F", "G", "H", "I", "K")  # + the noise replicate C~ in every job
WITH_J = (*CORE, "J")
WITH_B = (*CORE, "J", "B")
REVERT = ("D", "E", "F", "G", "H")
ADDRESS = ("stable", "partially_unstable", "highly_unstable", "locally_stable_globally_unstable")
COUPLINGS = ("weak", "medium", "strong")
# where persistent records can differ from the reference: record dynamics or collapse
J_STRUCTURES = {"record_fragmentation", "record_loss_reconstruction", "local_external_memory",
                "distributed_external_memory"}
B_STRUCTURES = {"strongly_cyclic", "dense_conflicts", "unsupported_addressable", "multi_cycles"}


def _c(cid: str, factor: str, level, **over) -> dict:
    c = condition(id=cid, **over)
    c["factor"], c["level"] = factor, level
    return c


def design() -> tuple[list[dict], dict]:
    ref = REFERENCE
    conds: list[dict] = [_c("reference", "reference", "reference", variants=WITH_B, revert=REVERT)]
    for t in TOPOLOGIES:
        if t != ref["topology"]:
            conds.append(_c(f"topology:{t}", "topology", t, topology=t, variants=CORE))
    for m in MEMORY_REGIMES:
        if m != ref["memory"]:
            conds.append(_c(f"memory:{m}", "memory", m, memory=m, variants=WITH_J))
    for k in COUPLINGS:
        if k != ref["coupling"]:
            conds.append(_c(f"coupling:{k}", "coupling", k, coupling=k, variants=CORE))
    for x in MUTATION:
        if x != ref["mutation"]:
            conds.append(_c(f"mutation:{x}", "mutation", x, mutation=x, variants=WITH_J))
    for r in RETURN_STRUCTURES:
        conds.append(_c(f"return:{r}", "return", r, **{"return": r}, variants=CORE))
    for a in ADDRESS:
        if a != ref["address"]:
            conds.append(_c(f"address:{a}", "address", a, address=a, variants=WITH_J))
    for s in STRUCTURES:
        v: tuple[str, ...]
        if s != ref["structure"]:
            v = WITH_B if s in B_STRUCTURES else WITH_J if s in J_STRUCTURES else CORE
            conds.append(_c(f"structure:{s}", "structure", s, structure=s, variants=v))
    for z in SIZES:
        if z != ref["size"]:
            v = WITH_B if z in (9, 128) else ("A", "C", "E", "F", "H")  # 512 / 2048: compilation cost
            conds.append(_c(f"size:{z}", "size", z, size=z, variants=v))
    conds.append(_c("horizon:400", "horizon", 400, horizon=400, variants=WITH_B, revert=REVERT))
    conds.append(_c("horizon:40000", "horizon", 40000, horizon=40000, variants=("A", "C", "D", "E", "F", "G", "H"),
                    revert=("E",)))
    conds.append(_c("n:10000", "n", 10000, n=10000, variants=CORE))
    conds.append(_c("n:100000:h400", "n", "100000 (400 steps)", n=100000, horizon=400, variants=CORE))
    conds.append(_c("n:100000", "n", 100000, n=100000, variants=("A", "C", "E", "F", "H")))
    # crossing: strong coupling with every topology (does stronger coupling expose topology-dependent visibility?)
    for t in TOPOLOGIES:
        if t != ref["topology"]:
            conds.append(_c(f"strong×topology:{t}", "strong×topology", t, topology=t, coupling="strong",
                            variants=("A", "C", "D", "E", "F", "H")))
    # statistical-power escalation at the reference condition: 48 seeds
    conds.append(_c("power:48seeds", "power", "48 seeds", seeds=48, variants=("A", "C", "D", "E", "F", "G", "H")))
    omitted = {
        "full_factorial": "not run; one-factor-at-a-time around the reference plus the listed crossings",
        "n=10000": "only at the reference condition (4,000 steps); no factor sweeps at 10,000",
        "n=100000": "reference condition only, at 400 steps (9 variants) and 4,000 steps (variants A, C, E, F, H); "
                    "no 40,000-step run",
        "horizon=40000": "reference condition only, n = 1,500, variants A, C, D, E, F, G, H",
        "variant J": "run only where records can behave differently (record dynamics, collapse regimes, reference)",
        "variant B": "vocabulary control run in the reference and in 8 structural conditions",
        "crossings": "only strong coupling × topology",
        "graph sizes 512 / 2048": "variants A, C, E, F, H only (compiling 512–2048 bindings per check makes the "
                                  "other variants ~2 h each)",
    }
    return conds, omitted
