"""M9 laboratory experiments: causal pathways between scientific systems (protocol: docs/LAB_PROTOCOL_M9.md).

The frozen M4–M7 code (xzr/lab/labexp.py) is not modified. Every condition of one seed shares the world, warm-up,
streams and physical laboratory layout; conditions differ only in the declared pathway switches (xzr/lab/causal.py,
physics partition, science comm / inert, harness interventions). Statistics: xzr.hpo.stats.contrast (paired sign-flip,
bootstrap 95 % interval, Holm, noise floor), unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..hpo.experiments import clean, run_pool
from ..hpo.stats import contrast
from .causal import measures
from .labexp import BASE, NOISE_OFFSET, A, B, C
from .record import LabRun

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "LAB_PROTOCOL_M9.md"
PROTOCOL_SHA256 = "4757ee7dc7dfbc9be25759a6491d65070b14fe6001cbf1faddfa24105bf1afbd"
RESULTS = ROOT / "backend" / "experiments" / "results" / "lab9"
# confirmatory seeds are new (never used in M4–M7, pilots or the exploratory T7 diagnostic)
RANGES: dict[str, tuple[int, int]] = {"confirm": (7000, 70000), "heldout": (7500, 75000), "worlds": (7700, 77000),
                                      "pilot": (8100, 81000)}

GROUPS = {"A": "a", "B": "s", "C": "s"}  # A against the other systems
SEP = {"groups": GROUPS, "gantries": "private", "material": "private"}
Bf = {**B, "comm": "frozen"}
Ai = {**A, "inert": True}

# M9-A: communication (L live conduits / F frozen) x resources (S shared / P separated) x A (+ present / 0 absent)
M9A: dict[str, dict[str, Any]] = {
    "LS+": {"systems": [A, B, C]}, "LS0": {"systems": [B, C]},
    "FS+": {"systems": [A, Bf, C]}, "FS0": {"systems": [Bf, C]},
    "LP+": {"systems": [A, B, C], "partition": SEP}, "LP0": {"systems": [B, C], "partition": SEP},
    "FP+": {"systems": [A, Bf, C], "partition": SEP}, "FP0": {"systems": [Bf, C], "partition": SEP},
    "LS+~": {"systems": [A, B, C], "noise": True}, "LS0~": {"systems": [B, C], "noise": True},
    # identity checks (must equal their reference bit for bit) and the physical-only pathway
    "LSz": {"systems": [{**A, "budget": 0.0}, B, C]},  # idle A == LS0
    "FPi": {"systems": [Ai, Bf, C], "partition": SEP},  # inert A, every pathway cut == FP0
    "LSi": {"systems": [Ai, B, C]},  # inert A, shared resources: A's physical pathway only
}
# M9-B: one physical resource separated at a time (live communication, real A); r0 = r without A where it differs
M9B: dict[str, dict[str, Any]] = {
    "G+": {"systems": [A, B, C], "partition": {"groups": GROUPS, "gantries": "private"}},
    "Q+": {"systems": [A, B, C], "partition": {"groups": GROUPS, "queues": "private"}},
    "W+": {"systems": [A, B, C], "partition": {"groups": GROUPS, "wear_exempt": ["a"]}},
    "P+": {"systems": [A, B, C], "partition": {"groups": GROUPS, "priority": "s"}},
    "M+": {"systems": [A, B, C], "partition": {"groups": GROUPS, "material": "private"}},
    "M0": {"systems": [B, C], "partition": {"groups": GROUPS, "material": "private"}},
}
# without A, separating gantries / queues / exempting A's wear / prioritising the others changes nothing (no A legs):
# their reference is LS0 (tested: an idle private carriage does not change the run)
B_REF0 = {"G+": "LS0", "Q+": "LS0", "W+": "LS0", "P+": "LS0", "M+": "M0"}

# M9-C: operational extinction and re-ignition (intervention at T = 320; closures reopened at 640)
T_EXT = 320
FAIL0 = [{"at": T_EXT - 1, "do": "set_resources", "gantry": "0", "value": 0.0}, {"at": T_EXT, "do": "fail_gantry", "gantry": "0"}]
VIEW = [{"at": T_EXT, "do": "close_view", "system": "A"}, {"at": 640, "do": "open_view", "system": "A"}]
BAY1 = ["1.0", "1.1", "1.2", "1.3"]
SENSE_B = ["1.0", "0.1", "2.0", "7.0", "1.2"]


def ext(sid: str, systems: list[dict], harness: list[dict] | None = None) -> dict[str, Any]:
    return {"systems": systems, "harness": harness or [], "extinction": {"system": sid, "t": T_EXT}}


M9C: dict[str, dict[str, Any]] = {
    "X0": ext("A", [A]),  # no intervention: how often the operation stops by itself
    "X1": ext("A", [A], FAIL0),  # apparatus failure, no repair resources, no substitute path
    "X2": ext("A", [A], [{"at": T_EXT - 1, "do": "set_resources", "gantry": "0", "value": 1.0},
                         {"at": T_EXT, "do": "fail_gantry", "gantry": "0"}]),  # failure with repair
    "X3": ext("A", [A], [*FAIL0, {"at": 480, "do": "set_resources", "gantry": "0", "value": 1.0}]),  # redistribution
    "X4": ext("A", [{**A, "reach": "adjacent"}], FAIL0),  # failure with redundant reach (adjacent bays' gantries)
    "X4b": ext("A", [{**A, "reach": "adjacent", "sensor_range": 7.0}], FAIL0),  # redundant reach and observation
    "X5": ext("A", [A], VIEW),  # loss of observation (A's observed chambers closed 320-640)
    "X6": ext("A", [{**A, "revise_observation": True}], VIEW),  # the same, with sensor relocation
    "X7": ext("B", [B], [{"at": T_EXT, "do": "sever", "chambers": SENSE_B}]),  # communication loss (conduits cut)
    "X7f": ext("B", [{**B, "comm": "frozen"}], [{"at": T_EXT, "do": "sever", "chambers": SENSE_B}]),  # control
    "X8": ext("C", [C], [{"at": T_EXT, "do": "close", "chambers": ["1.3"]}, {"at": 640, "do": "open", "chambers": ["1.3"]}]),
    "X10": ext("C", [C], [{"at": T_EXT, "do": "close", "chambers": BAY1}, {"at": 640, "do": "open", "chambers": BAY1}]),
    "X10n": ext("C", [{**C, "memory": "none"}], [{"at": T_EXT, "do": "close", "chambers": BAY1},
                                                  {"at": 640, "do": "open", "chambers": BAY1}]),
}
# M9-D: observation revision and effectiveness (system A alone)
M9D: dict[str, dict[str, Any]] = {
    "F": {"systems": [A]}, "R": {"systems": [{**A, "adapt_parameters": True}]},
    "O": {"systems": [{**A, "revise_observation": True}]},  # M5: novelty relocation + window
    "Oloc": {"systems": [{**A, "revise_observation": True, "revise_window": False}]},
    "Owin": {"systems": [{**A, "revise_observation": True, "relocation": "none"}]},
    "Oout": {"systems": [{**A, "revise_observation": True, "relocation": "outcome"}]},
    "OoutR": {"systems": [{**A, "revise_observation": True, "relocation": "outcome", "adapt_parameters": True}]},
    "F~": {"systems": [A], "noise": True},
}
M9D_HELDOUT = ("F", "O", "Oout")
# M9-E: variable generation (system A alone; diagnostics on)
Ad = {**A, "diagnose": True}
LO = {"explore": 0.3}
M9E: dict[str, dict[str, Any]] = {
    "F": {"systems": [Ad]}, "V": {"systems": [{**Ad, "generate_variables": True}]},
    "Vr": {"systems": [{**Ad, "generate_variables": True, "variable_rule": "random"}]},
    "Flo": {"systems": [{**Ad, **LO}]}, "Vlo": {"systems": [{**Ad, **LO, "generate_variables": True}]},
    "Vrlo": {"systems": [{**Ad, **LO, "generate_variables": True, "variable_rule": "random"}]},
    "Vlo~": {"systems": [{**Ad, **LO, "generate_variables": True}], "noise": True},
}
# M9-F: historical reinsertion (system C alone; configuration change at 480 as in M6; diagnostics on)
CHANGE = {"at": 480, "close": ["1.0", "1.2"], "factor": 0.6}
Cd = {**C, "diagnose": True}


def hist(spec: dict, noise: bool = False) -> dict[str, Any]:
    return {"systems": [spec], "config_change": CHANGE, **({"noise": True} if noise else {})}


M9F: dict[str, dict[str, Any]] = {
    "H0": hist({**Cd, "memory": "none"}), "H1": hist(Cd), "H2": hist({**Cd, "memory": "contextual"}),
    "H3": hist({**Cd, "memory": "shuffled"}), "H4": hist({**Cd, "memory": "write_only"}),
    "H6": hist({**Cd, "memory_delay": 120}), "H7": hist({**Cd, "memory": "contextual", "context_error": True}),
    "H1lo": hist({**Cd, **LO}), "H2lo": hist({**Cd, **LO, "memory": "contextual"}),
    "H2~": hist({**Cd, "memory": "contextual"}, noise=True),
}
# cross-world validation: five operationally different laboratories (16 seeds each)
EVERY = [{"at": t, "do": "sever", "chambers": SENSE_B} for t in range(120, 960, 120)]
ROTATE = [{"at": 160, "do": "close", "chambers": ["0.2", "1.2"]}, {"at": 320, "do": "open", "chambers": ["0.2", "1.2"]},
          {"at": 320, "do": "close", "chambers": ["0.3", "1.3"]}, {"at": 480, "do": "open", "chambers": ["0.3", "1.3"]},
          {"at": 480, "do": "close", "chambers": ["2.0", "0.1"]}, {"at": 640, "do": "open", "chambers": ["2.0", "0.1"]},
          {"at": 640, "do": "close", "chambers": ["1.1", "0.0"]}, {"at": 800, "do": "open", "chambers": ["1.1", "0.0"]}]
WORLDS: dict[str, dict[str, Any]] = {
    "transport": {"doc": "more experiments per system (budget 48, decisions every 2 steps): transport and contention dominate",
                  "spec": {"budget": 48.0, "period": 2}},
    "sensor": {"doc": "restricted observation: observation window 4 steps for every system, distributed readings 1 hop "
                      "(a local radius below the 3.4 chamber spacing would leave A no experiment at all: pilot)",
               "spec": {"window": 4}, "spec_by": {"distributed": {"comm_hops": 1}}},
    "fractured": {"doc": "communication fractured: the distributed system's connections are severed every 120 steps",
                  "harness": EVERY},
    "scarce": {"doc": "scarce resources: no repair resources, budgets 12", "spec": {"budget": 12.0}, "resources": 0.0},
    "dynamic": {"doc": "dynamically reconfiguring: pairs of chambers closed and reopened every 160 steps",
                "harness": ROTATE},
}
WORLD_CONDS = {"LS+": M9A["LS+"], "LS0": M9A["LS0"], "LSi": M9A["LSi"], "FP+": M9A["FP+"], "FP0": M9A["FP0"],
               "F": M9D["F"], "Oout": M9D["Oout"]}


def in_world(cond: dict[str, Any], w: dict[str, Any]) -> dict[str, Any]:
    systems = [{**s, **w.get("spec", {}), **w.get("spec_by", {}).get(s["kind"], {})} for s in cond["systems"]]
    out = {**cond, "systems": systems}
    if "harness" in w:
        has_b = any(s["sid"] == "B" for s in systems)
        out["harness"] = [h for h in w["harness"] if has_b or h["do"] != "sever"]
    if "resources" in w:
        out["resources"] = w["resources"]
    return out


M9W = {f"{wn}/{cn}": in_world(c, w) for wn, w in WORLDS.items() for cn, c in WORLD_CONDS.items()}

# Level C verification: the M9-A pathway cells under another physical integration arrangement (same 0.2 s per step)
ALT = {"dt": 0.002, "substeps": 100}
M9ALT = {k: {**M9A[k], "physics_params": ALT} for k in ("LS+", "LS0", "LSi", "FP+", "FP0")}

EXPERIMENTS: dict[str, dict[str, dict[str, Any]]] = {"m9ab": {**M9A, **M9B}, "m9c": M9C, "m9d": M9D, "m9e": M9E,
                                                     "m9f": M9F, "m9w": M9W, "m9alt": M9ALT}
SEEDS: dict[str, int] = {"m9ab": 24, "m9c": 24, "m9d": 24, "m9e": 24, "m9f": 24, "m9w": 16, "m9d_heldout": 16,
                         "m9alt": 12}
PRIMARY_B = ("completed", "pairs", "latency_mean")
SECONDARY_B = ("failed", "coverage", "paths", "true_gain", "queue_wait_mean", "contended_legs", "waits_behind_other",
               "fail_gantry", "fail_material", "fail_spot", "gantry_failures_hit", "recovery_steps", "completed_late",
               "iso_after_other_delivery", "observed_outcomes")


class ProtocolError(RuntimeError):
    pass


def protocol_hash() -> str:
    return hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() if PROTOCOL.exists() else "missing"


def check_protocol() -> None:
    if PROTOCOL_SHA256 == "UNFROZEN" or protocol_hash() != PROTOCOL_SHA256:
        raise ProtocolError("docs/LAB_PROTOCOL_M9.md is not frozen at the pinned hash; confirmatory runs refuse to start")


def config(cond: dict[str, Any], gen: int, seed: int) -> dict[str, Any]:
    cfg = {**BASE, "gen_seed": gen, "seed": seed + (NOISE_OFFSET if cond.get("noise") else 0),
           "systems": cond["systems"]}
    for k in ("partition", "harness", "physics_params", "config_change", "resources", "n", "regime", "horizon",
              "extinction"):
        if k in cond:
            cfg[k] = cond[k]
    return cfg


def job(args: tuple) -> dict:
    exp, cond, i, range_name = args
    gen0, seed0 = RANGES[range_name]
    cfg = config(EXPERIMENTS[exp][cond], gen0 + i, seed0 + i)
    t0 = time.time()
    r = LabRun(cfg)
    while not r.done:
        r.step()
    return {"exp": exp, "cond": cond, "i": i, "range": range_name, "systems": measures(r),
            "fingerprint": r.w.engine.fingerprint(), "seconds": round(time.time() - t0, 2)}


# ------------------------------------------------------------------ analysis helpers
def rows(jobs: list[dict], cond: str, sid: str) -> list[dict]:
    return [j["systems"][sid] for j in sorted((j for j in jobs if j["cond"] == cond), key=lambda j: j["i"])]


def diff(a: list[dict], b: list[dict], ms) -> list[dict]:
    return [{m: x.get(m, math.nan) - y.get(m, math.nan) for m in ms} for x, y in zip(a, b, strict=True)]


def avg(a: list[dict], b: list[dict], ms) -> list[dict]:
    return [{m: (x[m] + y[m]) / 2 for m in ms} for x, y in zip(a, b, strict=True)]


def noise_of(a: list[dict], b: list[dict], ms) -> dict[str, np.ndarray]:
    return {m: np.array([x[m] - y[m] for x, y in zip(a, b, strict=True)], float) for m in ms}


def con(x: list[dict], y: list[dict], primary, secondary, noise, seed: int) -> dict:
    """Holm adjustment within the primary family and, separately, within the secondary (descriptive) family."""
    nz = None if noise is None else {m: noise[m] for m in noise}
    return {**contrast(x, y, list(primary), nz, seed), **contrast(x, y, list(secondary), nz, seed + 50000)}


def det(c: dict, m: str) -> bool:
    return c.get(m, {}).get("status") == "DETECTED"


def status(c: dict, ms) -> dict[str, str]:
    return {m: c[m]["status"] for m in ms if m in c}


def identical(jobs: list[dict], x: str, y: str) -> dict[str, Any]:
    fx = {j["i"]: j["fingerprint"] for j in jobs if j["cond"] == x}
    fy = {j["i"]: j["fingerprint"] for j in jobs if j["cond"] == y}
    same = sum(1 for i in fx if fx[i] == fy.get(i))
    return {"pair": f"{x} == {y}", "identical_seeds": same, "seeds": len(fx), "holds": same == len(fx)}


def analyse_m9ab(jobs: list[dict]) -> dict[str, Any]:
    ms = list(PRIMARY_B + SECONDARY_B)
    R = {c: rows(jobs, c, "B") for c in {j["cond"] for j in jobs}}
    D = {cell: diff(R[f"{cell}+"], R[f"{cell}0"], ms) for cell in ("LS", "FS", "LP", "FP")}
    Dn = diff(R["LS+~"], R["LS0~"], ms)
    nf = noise_of(Dn, D["LS"], ms)  # noise floor for contrasts of dependences
    out: dict[str, Any] = {"contrasts": {}, "identity_checks": [identical(jobs, "LSz", "LS0"), identical(jobs, "FPi", "FP0")]}
    c = out["contrasts"]
    k = 9000
    for cell in ("LS", "FS", "LP", "FP"):
        c[f"dependence {cell}: B with A vs without A"] = con(R[f"{cell}+"], R[f"{cell}0"], PRIMARY_B, SECONDARY_B, None, k)
        k += 1
    zero = [{m: 0.0 for m in ms} for _ in D["LS"]]
    c["communication effect on dependence (L vs F, averaged over resources)"] = con(
        avg(D["LS"], D["LP"], ms), avg(D["FS"], D["FP"], ms), PRIMARY_B, SECONDARY_B, nf, k)
    c["resource effect on dependence (S vs P, averaged over communication)"] = con(
        avg(D["LS"], D["FS"], ms), avg(D["LP"], D["FP"], ms), PRIMARY_B, SECONDARY_B, nf, k + 1)
    c["interaction (comm effect under S minus under P)"] = con(
        diff(D["LS"], D["FS"], ms), diff(D["LP"], D["FP"], ms), PRIMARY_B, SECONDARY_B, nf, k + 2)
    c["residual dependence (F, P) vs zero"] = con(D["FP"], zero, PRIMARY_B, SECONDARY_B, nf, k + 3)
    c["physical-only pathway: inert A (shared) vs no A"] = con(R["LSi"], R["LS0"], PRIMARY_B, SECONDARY_B, None, k + 4)
    c["runtime-only pathway: real A vs inert A (frozen, separated)"] = con(R["FP+"], R["FPi"], PRIMARY_B, SECONDARY_B,
                                                                          None, k + 5)
    c["noise: LS+~ vs LS+"] = con(R["LS+~"], R["LS+"], PRIMARY_B, SECONDARY_B, None, k + 6)
    c["noise: LS0~ vs LS0"] = con(R["LS0~"], R["LS0"], PRIMARY_B, SECONDARY_B, None, k + 7)
    for r, ref in B_REF0.items():  # M9-B: dependence with one resource separated vs fully shared
        Dr = diff(R[r], R[ref], ms)
        c[f"mediation {r[0]}: dependence shared vs {r[0]} separated"] = con(D["LS"], Dr, PRIMARY_B, SECONDARY_B, nf,
                                                                            k + 10 + len(c))
        c[f"dependence {r[0]}-separated: B with A vs without A"] = con(R[r], R[ref], PRIMARY_B, SECONDARY_B, None,
                                                                      k + 40 + len(c))
    out["dependence_means"] = {cell: {m: float(np.nanmean([x[m] for x in D[cell]])) for m in ms} for cell in D}
    out["verdicts"] = verdicts_m9ab(out)
    return out


def verdicts_m9ab(out: dict) -> dict[str, Any]:
    c = out["contrasts"]
    P = PRIMARY_B
    dets = {k: [m for m in PRIMARY_B + SECONDARY_B if det(v, m)] for k, v in c.items()}
    valid = all(x["holds"] for x in out["identity_checks"])
    noise_bad = [k for k in c if k.startswith("noise") and len(dets[k]) > 0.05 * len(PRIMARY_B + SECONDARY_B)]
    v: dict[str, Any] = {
        "instrument_valid": valid and not noise_bad, "identity_checks": out["identity_checks"], "noise_flagged": noise_bad,
        "dependence_shared_live_detected": [m for m in P if det(c["dependence LS: B with A vs without A"], m)],
        "H_A1_resource_mediation": any(det(c["resource effect on dependence (S vs P, averaged over communication)"], m)
                                       for m in P),
        "H_A2_communication_mediation": any(det(c["communication effect on dependence (L vs F, averaged over resources)"], m)
                                            for m in P),
        "interaction_detected": [m for m in P if det(c["interaction (comm effect under S minus under P)"], m)],
        "H_A3_residual_dependence": [m for m in P if det(c["residual dependence (F, P) vs zero"], m)],
        "physical_only_pathway": [m for m in P if det(c["physical-only pathway: inert A (shared) vs no A"], m)],
        "runtime_only_pathway": [m for m in P if det(c["runtime-only pathway: real A vs inert A (frozen, separated)"], m)],
        "M9B_mediators": {r: [m for m in P if det(c[f"mediation {r}: dependence shared vs {r} separated"], m)]
                          for r in "GQWPM"},
        "detected": dets,
    }
    return v


def _sys(cond: dict[str, Any]) -> str:
    return cond.get("extinction", {}).get("system") or cond["systems"][0]["sid"]


def _count(rs: list[dict], key: str, cond_key: str | None = None) -> dict[str, int]:
    base = [r for r in rs if cond_key is None or r.get(cond_key) == 1.0]
    return {"seeds": len(rs), "eligible": len(base), "count": sum(1 for r in base if r.get(key) == 1.0)}


def analyse_m9c(jobs: list[dict]) -> dict[str, Any]:
    ks = ("active_before", "extinct", "reignited", "restored_same", "new_dependency", "apparatus_failed")
    ms = ("completed_after", "outage_paths", "extinction_point", "reignition_step", "reuse_share", "evidence_unavailable",
          "persisting_conduits", "completed", "true_gain", "relocations")
    R = {c: rows(jobs, c, _sys(M9C[c])) for c in M9C}
    counts = {c: {k: _count(R[c], k, None if k in ("active_before", "apparatus_failed") else
                            "active_before" if k == "extinct" else "extinct") for k in ks} for c in M9C}
    out: dict[str, Any] = {"counts": counts, "contrasts": {}}
    c = out["contrasts"]
    for i, (x, y) in enumerate((("X1", "X0"), ("X2", "X1"), ("X3", "X1"), ("X4", "X1"), ("X5", "X0"), ("X6", "X5"),
                                ("X7", "X7f"), ("X10", "X10n"), ("X4b", "X1"))):
        prim = ("reuse_share", "reignition_step") if x == "X10" else ("extinct", "completed_after")
        c[f"{x} vs {y}"] = con(R[x], R[y], prim, [m for m in ms if m not in prim], None, 9500 + i)
    n = lambda cond, k: counts[cond][k]["count"]  # noqa: E731
    e = lambda cond: counts[cond]["extinct"]["eligible"]  # noqa: E731
    out["verdicts"] = {
        "C1_failure_without_substitutes_extinguishes": n("X1", "extinct") >= 0.8 * max(e("X1"), 1),
        "C2_repaired_failure_is_not_extinction": n("X2", "extinct") <= 0.2 * max(e("X2"), 1),
        "C3_redistribution_reignites_same_dependency": n("X3", "reignited") >= 0.8 * max(n("X3", "extinct"), 1)
        and n("X3", "restored_same") >= 0.8 * max(n("X3", "reignited"), 1),
        "C4_redundant_paths_prevent_extinction": det(c["X4 vs X1"], "extinct") and c["X4 vs X1"]["extinct"]["mean"] < 0,
        "C4b_redundant_reach_and_observation_prevent_extinction": det(c["X4b vs X1"], "extinct")
        and c["X4b vs X1"]["extinct"]["mean"] < 0,
        "C5_observation_loss_extinguishes": n("X5", "extinct") >= 0.8 * max(e("X5"), 1),
        "C6_sensor_relocation_prevents_or_shortens": det(c["X6 vs X5"], "extinct") and c["X6 vs X5"]["extinct"]["mean"] < 0,
        "C7_communication_loss_extinguishes_B": det(c["X7 vs X7f"], "extinct") and c["X7 vs X7f"]["extinct"]["mean"] > 0,
        "C8_evidence_loss_is_not_extinction": n("X8", "extinct") <= 0.2 * max(e("X8"), 1)
        and all(r["evidence_unavailable"] > 0 for r in R["X8"]),
        "C9_history_restores_the_same_dependency": det(c["X10 vs X10n"], "reuse_share")
        and c["X10 vs X10n"]["reuse_share"]["mean"] > 0,
        "X0_natural_extinction": n("X0", "extinct"),
    }
    return out


def analyse_m9d(jobs: list[dict], held: list[dict]) -> dict[str, Any]:
    P_ = ("true_gain",)
    S_ = ("gain_per_completed", "gain_per_spent", "pairs", "completed", "distinct_observed_pairs", "redundant_observations",
          "observed_outcomes", "abs_pred_error", "obs_error_mean", "paths", "relocations", "window_changes", "coverage")
    R = {x: rows(jobs, x, "A") for x in M9D}
    nf = noise_of(R["F~"], R["F"], P_ + S_)
    out: dict[str, Any] = {"contrasts": {}, "heldout": {}}
    for i, x in enumerate(("R", "O", "Oloc", "Owin", "Oout", "OoutR", "F~")):
        out["contrasts"][f"{x} vs F"] = con(R[x], R["F"], P_, S_, None if x == "F~" else nf, 9600 + i)
    out["contrasts"]["Oout vs O"] = con(R["Oout"], R["O"], P_, S_, nf, 9610)
    H = {x: rows(held, x, "A") for x in M9D_HELDOUT}
    for i, x in enumerate(("O", "Oout")):
        out["heldout"][f"{x} vs F"] = con(H[x], H["F"], P_, S_, None, 9620 + i)
    c, h = out["contrasts"], out["heldout"]
    up = lambda cc, m: det(cc, m) and cc[m]["mean"] > 0  # noqa: E731
    out["verdicts"] = {
        "D1_outcome_guided_revision_improves_gain": up(c["Oout vs F"], "true_gain") and up(h["Oout vs F"], "true_gain"),
        "D1_main_only": up(c["Oout vs F"], "true_gain"),
        "D2_M5_revision_lowers_effectiveness_replicated": det(c["O vs F"], "gain_per_completed")
        and c["O vs F"]["gain_per_completed"]["mean"] < 0,
        "decomposition": {x: [m for m in P_ + S_ if det(c[f"{x} vs F"], m)] for x in ("O", "Oloc", "Owin", "Oout", "OoutR", "R")},
        "noise_detected": [m for m in P_ + S_ if det(c["F~ vs F"], m)],
    }
    return out


def analyse_m9e(jobs: list[dict]) -> dict[str, Any]:
    P_ = ("abs_pred_error", "obs_error_mean", "true_gain")
    S_ = ("changed_without_variables", "changed_without_prediction", "variables_adopted", "obs_true_corr", "pairs",
          "completed", "gain_per_completed")
    R = {x: rows(jobs, x, "A") for x in M9E}
    nf = noise_of(R["Vlo~"], R["Vlo"], P_ + S_)
    pairs = (("V", "F"), ("V", "Vr"), ("Vlo", "Flo"), ("Vlo", "Vrlo"), ("Flo", "F"), ("Vlo~", "Vlo"))
    out: dict[str, Any] = {"contrasts": {f"{x} vs {y}": con(R[x], R[y], P_, S_, None if x.endswith("~") else nf, 9700 + i)
                                         for i, (x, y) in enumerate(pairs)}}
    c = out["contrasts"]
    down = lambda cc, m: det(cc, m) and cc[m]["mean"] < 0  # noqa: E731
    diag = {x: {m: _mean([r.get(m) for r in R[x]]) for m in S_} for x in M9E}
    out["diagnostics"] = diag
    out["verdicts"] = {
        "E1_variables_consequential_when_model_drives_choice": down(c["Vlo vs Flo"], "obs_error_mean")
        or down(c["Vlo vs Flo"], "abs_pred_error")
        or (det(c["Vlo vs Flo"], "true_gain") and c["Vlo vs Flo"]["true_gain"]["mean"] > 0),
        "E2_criterion_beats_random_adoption": down(c["Vlo vs Vrlo"], "obs_error_mean"),
        "E0_M5_negative_replicated": not any(det(c["V vs F"], m) for m in P_),
        "noise_detected": [m for m in P_ + S_ if det(c["Vlo~ vs Vlo"], m)],
    }
    return out


def analyse_m9f(jobs: list[dict]) -> dict[str, Any]:
    P_ = ("true_gain_post",)
    S_ = ("true_gain", "changed_without_memory", "changed_without_prediction", "memory_reads", "pairs", "completed",
          "abs_pred_error")
    R = {x: rows(jobs, x, "C") for x in M9F}
    nf = noise_of(R["H2~"], R["H2"], P_ + S_)
    pairs = (("H2", "H1"), ("H1", "H0"), ("H2", "H3"), ("H2", "H4"), ("H1", "H6"), ("H2", "H7"), ("H2lo", "H1lo"),
             ("H1lo", "H0"), ("H2~", "H2"))
    out: dict[str, Any] = {"contrasts": {f"{x} vs {y}": con(R[x], R[y], P_, S_, None if x.endswith("~") else nf, 9800 + i)
                                         for i, (x, y) in enumerate(pairs)}}
    c = out["contrasts"]
    up = lambda k: det(c[k], "true_gain_post") and c[k]["true_gain_post"]["mean"] > 0  # noqa: E731
    out["diagnostics"] = {x: {m: _mean([r.get(m) for r in R[x]]) for m in S_} for x in M9F}
    out["verdicts"] = {"F1_contextual_over_ordinary_replicated": up("H2 vs H1"),
                       "F2_contextual_over_ordinary_low_exploration": up("H2lo vs H1lo"),
                       "F3_memory_over_none": up("H1 vs H0"), "F4_beyond_shuffled": up("H2 vs H3"),
                       "F5_beyond_wrong_context": up("H2 vs H7"), "F6_timely_over_delayed": up("H1 vs H6"),
                       "noise_detected": [m for m in P_ + S_ if det(c["H2~ vs H2"], m)]}
    return out


def analyse_m9w(jobs: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {"worlds": {k: v["doc"] for k, v in WORLDS.items()}, "contrasts": {}, "verdicts": {}}
    for wi, wn in enumerate(WORLDS):
        R = {cn: rows(jobs, f"{wn}/{cn}", "A" if cn in ("F", "Oout") else "B") for cn in WORLD_CONDS}
        cs = {"dependence (shared, live)": con(R["LS+"], R["LS0"], PRIMARY_B, SECONDARY_B, None, 9900 + 10 * wi),
              "residual dependence (separated, frozen)": con(R["FP+"], R["FP0"], PRIMARY_B, SECONDARY_B, None, 9901 + 10 * wi),
              "physical-only pathway": con(R["LSi"], R["LS0"], PRIMARY_B, SECONDARY_B, None, 9902 + 10 * wi),
              "outcome-guided revision vs fixed (A)": con(R["Oout"], R["F"], ("true_gain",),
                                                         ("gain_per_completed", "pairs", "completed"), None, 9903 + 10 * wi)}
        out["contrasts"][wn] = cs
        out["verdicts"][wn] = {k: {m: v[m]["status"] + (f" ({v[m]['relative']:+.2f})" if "relative" in v[m] else "")
                                   for m in v} for k, v in cs.items()}
    return out


def analyse_m9alt(jobs: list[dict]) -> dict[str, Any]:
    R = {c: rows(jobs, c, "B") for c in M9ALT}
    c = {"dependence (shared, live)": con(R["LS+"], R["LS0"], PRIMARY_B, SECONDARY_B, None, 9950),
         "residual dependence (separated, frozen)": con(R["FP+"], R["FP0"], PRIMARY_B, SECONDARY_B, None, 9951),
         "physical-only pathway": con(R["LSi"], R["LS0"], PRIMARY_B, SECONDARY_B, None, 9952)}
    return {"contrasts": c, "arrangement": ALT,
            "verdicts": {k: {m: v[m]["status"] + (f" ({v[m]['relative']:+.2f})" if "relative" in v[m] else "")
                             for m in PRIMARY_B} for k, v in c.items()}}


ANALYSES = {"m9alt": analyse_m9alt, "m9ab": analyse_m9ab, "m9c": analyse_m9c, "m9e": analyse_m9e, "m9f": analyse_m9f,
            "m9w": analyse_m9w}


def run_experiment(name: str, procs: int, confirmatory: bool = True, range_name: str = "confirm",
                   seeds: int | None = None) -> dict:
    if confirmatory:
        check_protocol()
    exp = EXPERIMENTS[name]
    n = seeds or SEEDS[name]
    t0 = time.time()
    jobs = run_pool(job, [(name, c, i, range_name) for c in exp for i in range(n)], procs)
    doc: dict[str, Any] = {"experiment": name, "seeds": n, "range": range_name, "seed_ranges": RANGES[range_name],
                           "conditions": exp, "base": BASE, "confirmatory": confirmatory}
    if name == "m9d":
        held_n = seeds or SEEDS["m9d_heldout"]
        held = run_pool(job, [(name, c, i, "heldout" if range_name == "confirm" else range_name)
                              for c in M9D_HELDOUT for i in range(held_n)], procs)
        doc["heldout_seeds"] = held_n
        doc.update(analyse_m9d(jobs, held))
        jobs += held
    else:
        doc.update(ANALYSES[name](jobs))
    sids = sorted({s for j in jobs for s in j["systems"]})
    doc["means"] = {f"{c}/{sid}": {m: _mean([r.get(m) for r in rows(jobs, c, sid)])
                                    for m in (jobs[0]["systems"].get(sid) or next(iter(jobs[0]["systems"].values())))}
                    for c in exp for sid in sids if any(sid in j["systems"] for j in jobs if j["cond"] == c)}
    doc["runs"] = len(jobs)
    doc["simulated_steps"] = int(sum(config(exp[j["cond"]], 0, 0)["horizon"] for j in jobs))
    doc["seconds_per_run_mean"] = round(float(np.mean([j["seconds"] for j in jobs])), 2)
    doc["elapsed_s"] = round(time.time() - t0, 1)
    from ..experiments.escalation.runner import provenance
    doc["provenance"] = provenance()
    doc["protocol_sha256"] = protocol_hash()
    doc["pinned_protocol_sha256"] = PROTOCOL_SHA256
    doc["fingerprints"] = {f"{j['cond']}/{j['range']}/{j['i']}": j["fingerprint"] for j in jobs}
    doc["per_run"] = [{k: j[k] for k in ("cond", "i", "range", "systems", "seconds")} for j in jobs]
    return doc


def _mean(xs: list) -> float | None:
    v = [x for x in xs if isinstance(x, int | float) and math.isfinite(x)]
    return float(np.mean(v)) if v else None


def write(name: str, doc: dict, root: Path | None = None) -> Path:
    out = root or RESULTS
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.json"
    if p.exists() and root is None:
        raise FileExistsError(f"{p} exists; published results are never overwritten")
    p.write_text(json.dumps(clean(doc), indent=1, ensure_ascii=False, allow_nan=False))
    return p
