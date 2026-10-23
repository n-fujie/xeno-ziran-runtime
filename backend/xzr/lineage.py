"""Which research lines the runtime can actually run, replay, reach through an adapter, or only point to.

The existence of a name in a document is not a capability. Each line carries a list of *evidence* (paths and modules, probed on this machine each time the
map is asked for) for each mode it might be available in; the status is the strongest mode whose evidence all exists:

    Native       runs directly from this runtime (an importable module with a runner)
    Adapter      runs through a bridge to an implementation that lives elsewhere (the bridge and the implementation both exist)
    Replay       a stored result can be replayed and compared (the stored records and a replay path exist)
    Reference    documents or records only; nothing can be run
    Unavailable  no implementation and no record found

The classification is recomputed from the file system, so moving or deleting an asset changes it. It is a statement about availability, not about whether a
line's scientific claims hold; ``scientific_state`` is a short statement by the owner of this repository's own records and is not computed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ORDER = ("Native", "Adapter", "Replay", "Reference", "Unavailable")
REPO = Path(__file__).resolve().parents[2]
BIM = REPO.parent


def _p(rel: str, base: str = "repo") -> dict:
    root = REPO if base == "repo" else BIM
    return {"kind": "path", "target": rel, "base": base, "exists": (root / rel).exists()}


def _m(mod: str) -> dict:
    try:
        ok = importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        ok = False
    return {"kind": "module", "target": mod, "exists": ok}


def _lines() -> list[dict]:
    return [
        {
            "line": "ARDS (autonomous R&D system)",
            "modes": {
                "Adapter": [_p("pa-simulation-environment/src/ards", "bim"), _p("backend/xzr/study/ards.py"), _p("backend/xzr/study/ards_bridge/ards_job.ts")],
                "Replay": [_p("pa-simulation-environment/artifacts/ards", "bim")],
                "Reference": [_p("pa-ards-design", "bim")],
            },
            "input": "an ARDS arm name, an environment (env1 / env2 / env3), a replicate in the reserved software-test block 3980-3989",
            "output": "ARDS's own run records and held-out scores, re-read by the bridge",
            "storage": "study run records (backend/experiments/studies); ARDS artifacts are read-only",
            "reproduction": "re-run through the bridge; the bridge equals ARDS-direct on five arms (env1, env3)",
            "connection": "vite-node bridge (study/ards_bridge), test mode only",
            "unsupported": "any non-test replicate; ARDS Phase 4 main experiment (not started, not permitted here)",
            "scientific_state": "Phase 3 frozen (1,526 files, verified); Phase 4 exploration records kept; no confirmatory run",
        },
        {
            "line": "HPO (heterogeneous-operations field, HPO-003 controller)",
            "modes": {"Native": [_m("xzr.hpo"), _m("xzr.hpo.reconfig"), _m("xzr.hpo.metarevision"), _m("xzr.hpo.reachability")]},
            "input": "a study protocol with environment kind hpo-world",
            "output": "run records with changes, reachability levels, meta-revision trace, history re-entry",
            "storage": "study run records",
            "reproduction": "same-machine bit-for-bit (36/36 verified earlier); not cross-platform",
            "connection": "direct",
            "unsupported": "—",
            "scientific_state": "functional studies only; the first scarcity study's -26 fired samples under meta-revision is UNRESOLVED",
        },
        {
            "line": "Operational-Shape Dynamics",
            "modes": {"Native": [_m("xzr.runtime"), _m("xzr.shapes")]},
            "input": "a world seed and generator; scenarios",
            "output": "engine step deltas and the shape detector's structural descriptors (no interpretation)",
            "storage": "run records; scenarios under backend/scenarios",
            "reproduction": "same machine; hierarchy-dependent descriptors can differ across platforms (the two known failures)",
            "connection": "direct",
            "unsupported": "cross-platform bit-reproducibility of address-based results",
            "scientific_state": "engine and detector verified; two environment-caused test failures kept and diagnosed",
        },
        {
            "line": "XenoBody (XB-TRO)",
            "modes": {
                "Adapter": [_p("pa-simulation-environment/src/ards", "bim"), _p("backend/xzr/study/ards_bridge/zrs_oi.ts")],
                "Reference": [_p("xeno-ziran-runtime-xb-tro/backend/xzr/xbtro", "bim"), _p("xenobody-public-build", "bim")],
            },
            "input": "through ARDS environment env1 (the XB-TRO observation task)",
            "output": "ARDS's held-out scores on env1",
            "storage": "study run records",
            "reproduction": "bridge equals ARDS-direct on env1",
            "connection": "ARDS bridge; the xbtro module in the sibling worktree is not callable from this runtime",
            "unsupported": "running xbtro itself from this runtime; the public build is a presentation, not a runner",
            "scientific_state": "Research Beta on a local branch; not pushed or deployed",
        },
        {
            "line": "XenoSNN",
            "modes": {
                "Replay": [_p("pa-simulation-environment/src/ards/replay/targets.ts", "bim")],
                "Reference": [_p("pa-simulation-environment/src/ards/backends/snnServer.ts", "bim")],
            },
            "input": "a stored snn-minimal result fixture",
            "output": "comparison of the membrane / spike trace with the stored result",
            "storage": "ARDS replay targets",
            "reproduction": "replay of the stored fixture; the live snnTorch server was not started here",
            "connection": "ARDS replay target snn-fixture; no live adapter exercised",
            "unsupported": "live SNN runs (needs the snnTorch server); anything beyond the minimal neuron",
            "scientific_state": "fixture-level; no scientific evaluation",
        },
        {
            "line": "Robotics",
            "modes": {"Native": [_m("xzr.lab"), _p("backend/xzr/lab/physics.py")]},
            "input": "laboratory populations and scenarios (gantries, material transfer)",
            "output": "laboratory run records",
            "storage": "study run records",
            "reproduction": "same machine",
            "connection": "direct (the laboratory's mechanical transfer physics)",
            "unsupported": "robot control, embodied learning, real hardware",
            "scientific_state": "a physical-laboratory mechanism for the multi-system studies; not a robotics research line",
        },
        {
            "line": "Active Inference",
            "modes": {
                "Native": [_p("research/post_active_inference/pai/aif_vendor.py")],
                "Reference": [_p("research/post_active_inference/IMPLEMENTATION_GAP.md"), _p("ziran-xeno-simulator/embodied/active_inference", "bim")],
            },
            "input": "the Post-Active-Inference benchmark's comparator (discrete A/B/C/D/E model, EFE policy selection)",
            "output": "benchmark cell scores",
            "storage": "research/post_active_inference/results",
            "reproduction": "run_benchmark.py",
            "connection": "separate research package; NOT an arm of the total-observation line or of the shared ARDS-HPO environment",
            "unsupported": "Active Inference as a comparison arm in the total-observation line (not implemented; not named as one)",
            "scientific_state": "benchmark research stage done; its non-redundancy analysis is separate",
        },
        {
            "line": "Post-Active-Inference",
            "modes": {
                "Native": [_p("research/post_active_inference/run_benchmark.py"), _p("research/post_active_inference/pai/controllers.py")],
                "Replay": [_p("research/post_active_inference/results")],
            },
            "input": "benchmark configs",
            "output": "cell scores, failures, regime classification",
            "storage": "research/post_active_inference/results",
            "reproduction": "run_benchmark.py with the preregistered configs",
            "connection": "separate research package using the runtime as its world",
            "unsupported": "—",
            "scientific_state": "see its REPORT.md and PREREGISTRATION.md; not re-evaluated here",
        },
        {
            "line": "ANESCIRE",
            "modes": {},
            "input": "—",
            "output": "—",
            "storage": "—",
            "reproduction": "—",
            "connection": "none",
            "unsupported": "everything: no implementation and no record was found in any repository on this machine",
            "scientific_state": "not assessable",
        },
        {
            "line": "Xenoscience",
            "modes": {"Reference": [_p("docs/THEORY.md"), _p("docs/SIMULATOR_CAPABILITY_REPORT.md"), _p("docs/LIMITATIONS.md")]},
            "input": "—",
            "output": "documents",
            "storage": "docs/",
            "reproduction": "—",
            "connection": "the theory is not an executable module; the simulator's operational lines are the executable part",
            "unsupported": "any claim that the simulator establishes the theory",
            "scientific_state": "Level 3 (strong xenoscience) is not claimed",
        },
        {
            "line": "Total Observation",
            "modes": {"Native": [_m("xzr.totalobs.loop"), _m("xzr.totalobs.observers"), _m("xzr.totalobs.agent")]},
            "input": "a total-observation study protocol (environment kind total-observation)",
            "output": "per-generation records of the ten items of the research loop, reachability levels, verifier scores, ledger",
            "storage": "study run records",
            "reproduction": "same machine, deterministic per (generator seed, engine seed)",
            "connection": "direct; reuses hpo.metarevision and hpo.reachability.compare_levels",
            "unsupported": "complete information; a real observing network",
            "scientific_state": "implemented and operationally verified; scientific evaluation (C) and non-redundancy (D) not done",
        },
        {
            "line": "Planetary-Scale Observation",
            "modes": {"Native": [_m("xzr.totalobs.planetary"), _m("xzr.totalobs.world")]},
            "input": "world and net parameters (extent, span, speed, period, latency, pool, sensors)",
            "output": "the declared structural conditions, met or not; a scaling-law fit from sweeps",
            "storage": "run records (planetary block)",
            "reproduction": "same machine",
            "connection": "direct; synthetic model",
            "unsupported": "any claim about the Earth: needs measured data and an earth-system model (neither present)",
            "scientific_state": "synthetic structure only; earth_claim is false",
        },
        {
            "line": "SSS (Scale / Size / Speed)",
            "modes": {"Native": [_m("xzr.totalobs.sss")]},
            "input": "axis levels or explicit parameter values",
            "output": "main and interaction effects; metric comparability decisions",
            "storage": "study analysis (totalobs.sss)",
            "reproduction": "same machine",
            "connection": "direct",
            "unsupported": "automatic conversion between metric definitions (none is made)",
            "scientific_state": "mechanism verified; effects reported are from functional studies",
        },
    ]


def capability_map() -> dict:
    rows = []
    for ln in _lines():
        got = [m for m in ORDER[:-1] if ln["modes"].get(m) and all(e["exists"] for e in ln["modes"][m])]
        status = got[0] if got else "Unavailable"
        # evidence that exists for a mode that is not complete is still shown: availability is not all-or-nothing
        partial = {m: [e for e in ev if e["exists"]] for m, ev in ln["modes"].items() if m not in got and any(e["exists"] for e in ev)}
        rows.append(
            {
                **{k: v for k, v in ln.items() if k != "modes"},
                "status": status,
                "also": [m for m in got[1:]],
                "evidence": {m: ev for m, ev in ln["modes"].items()},
                "partial_evidence_for_modes_not_met": {m: [e["target"] for e in ev] for m, ev in partial.items()},
            }
        )
    return {
        "statuses": list(ORDER),
        "rule": "status = the strongest mode whose evidence all exists on this machine; a name in a document is not a capability",
        "lines": rows,
        "counts": {s: sum(1 for r in rows if r["status"] == s) for s in ORDER},
        "reality_as_a_whole": (
            "Not a module and not a line: an ontological scope. The runtime keeps the world's state, the observer's state, their interaction, interventions, "
            "the recording mechanism, residual consequences, the agent's access and the agent's constructions apart (totalobs.ontology), and does not equate any "
            "model state with reality as a whole."
        ),
    }
