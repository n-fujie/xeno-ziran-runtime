"""M4–M7 laboratory experiments: conditions, paired seed jobs, analysis (protocol: docs/LAB_PROTOCOL.md).

Every condition of one seed shares the world (generator seed), warm-up, exogenous and endogenous streams and the
physical laboratory; conditions differ only in the systems present and their specifications. Noise replicates use
another endogenous stream. Statistics: xzr.hpo.stats (paired sign-flip, bootstrap 95 % interval, Holm, noise floor).
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
from .record import LabRun

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "LAB_PROTOCOL.md"
PROTOCOL_SHA256 = "ce00c75f8edb8a66b766b090e7a6cd3bff771d57403c142e0e54465ab2cbacf9"
RESULTS = ROOT / "backend" / "experiments" / "results" / "labx"
NOISE_OFFSET = 7919

BASE: dict[str, Any] = {"n": 800, "regime": "intermittent", "warmup": 40, "horizon": 960, "settings": None, "physics": True,
        "resources": 3.0}
RANGES: dict[str, tuple[int, int]] = {"confirm": (6000, 60000), "heldout": (6500, 65000), "dev": (8000, 80000)}

A = {"sid": "A", "kind": "local", "home": "0.0"}
B = {"sid": "B", "kind": "distributed", "home": "1.0", "sensors": ["0.1", "2.0", "7.0", "1.2"], "isolate_above": 0.12}
C = {"sid": "C", "kind": "history", "home": "1.1", "memory": "ordinary", "store": "1.3"}
EQUAL = {"see_all": True, "reach": "any", "memory": "none", "isolate_above": None}

M4: dict[str, list[dict]] = {"solo_A": [A], "solo_B": [B], "solo_C": [C],
      "eq_A": [{**A, **EQUAL}], "eq_B": [{**B, **EQUAL}], "eq_C": [{**C, **EQUAL}]}
M5: dict[str, list[dict]] = {"F": [A], "R": [{**A, "adapt_parameters": True}], "O": [{**A, "revise_observation": True}],
      "V": [{**A, "generate_variables": True}], "OV": [{**A, "revise_observation": True, "generate_variables": True}],
      "F~": [A]}
M5_HELDOUT = ("F", "O", "V", "OV")
CHANGE = {"at": 480, "close": ["1.0", "1.2"], "factor": 0.6}
M6: dict[str, list[dict]] = {"H0": [{**C, "memory": "none"}], "H1": [C], "H2": [{**C, "memory": "contextual"}],
      "H3": [{**C, "memory": "shuffled"}], "H4": [{**C, "memory": "write_only"}], "H5": [{**C, "policy": "random"}],
      "H2~": [{**C, "memory": "contextual"}]}
M7: dict[str, list[dict]] = {"ALL": [A, B, C], "noA": [B, C], "noB": [A, C], "noC": [A, B],
                             "noIso": [A, {**B, "isolate_above": None}, C],
      "noComm": [A, {**B, "comm_free": True}, C], "noComm_noA": [{**B, "comm_free": True}, C],
      "memShare": [{**A, "shared_memory_from": "C"}, B, C], "ALL~": [A, B, C]}
EXPERIMENTS: dict[str, dict[str, list[dict]]] = {"m4": M4, "m5": M5, "m6": M6, "m7": M7}
SEEDS: dict[str, int] = {"m4": 24, "m5": 24, "m6": 24, "m7": 24, "m5_heldout": 16}
METRICS = ("requests", "completed", "failed", "denied", "true_gain", "true_gain_post", "observed_outcomes",
           "unobserved_outcomes", "relocations", "window_changes", "isolations", "memory_reads", "memory_unavailable",
           "abs_pred_error", "coverage", "paths", "pairs", "spent", "variables_rejected", "first_request")


class ProtocolError(RuntimeError):
    pass


def protocol_hash() -> str:
    return hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() if PROTOCOL.exists() else "missing"


def check_protocol() -> None:
    if PROTOCOL_SHA256 == "UNFROZEN" or protocol_hash() != PROTOCOL_SHA256:
        raise ProtocolError("docs/LAB_PROTOCOL.md is not frozen at the pinned hash; confirmatory runs refuse to start")


def config(systems: list[dict], gen: int, seed: int, noise: bool = False, change: dict | None = None) -> dict:
    return {**BASE, "gen_seed": gen, "seed": seed + (NOISE_OFFSET if noise else 0), "systems": systems,
            **({"config_change": change} if change else {})}


def _extra(sci, events: list[dict]) -> dict[str, dict[str, float]]:
    """Per-system counts read from the science events (cross-system effects)."""
    out: dict[str, dict[str, float]] = {sid: {"blocked_deliveries": 0, "isolated_by_other": 0,
                                              "after_reopen_experiments": 0, "experiments_selected": 0}
                                        for sid in sci.systems}
    iso: dict[str, list[tuple[int, int, str]]] = {}
    for e in events:
        if e["type"] == "isolation":
            iso.setdefault(e["chamber"], []).append((e["t"], e["until"], e["system"]))
    for e in events:
        sid = e.get("system")
        if sid not in out:
            continue
        if e["type"] == "delivery_blocked":
            out[sid]["blocked_deliveries"] += 1
            if any(s != sid and t0 <= e["t"] < t1 for t0, t1, s in iso.get(e["dst"], [])):
                out[sid]["isolated_by_other"] += 1
        if e["type"] == "experiment_selected":
            out[sid]["experiments_selected"] += 1
            if any(s != sid and t1 <= e["t"] for _, t1, s in iso.get(e["dst"], [])):
                out[sid]["after_reopen_experiments"] += 1
    return out


def job(args: tuple) -> dict:
    exp, cond, i, range_name = args
    gen0, seed0 = RANGES[range_name]
    systems = EXPERIMENTS[exp][cond]
    cfg = config(systems, gen0 + i, seed0 + i, noise=cond.endswith("~"), change=CHANGE if exp == "m6" else None)
    t0 = time.time()
    r = LabRun(cfg)
    while not r.done:
        r.step()
    sci = r.science
    assert sci is not None
    summ = sci.summary()
    extra = _extra(sci, sci.events)
    m: dict[str, dict[str, Any]] = {}
    for sid, s in summ.items():
        m[sid] = {k: (float(s[k]) if s.get(k) is not None and not (isinstance(s[k], float) and math.isnan(s[k]))
                      else math.nan) for k in METRICS if k in s and not isinstance(s[k], list)}
        m[sid].update(extra[sid])
        m[sid]["variables_adopted"] = float(len(s["variables_adopted"]))
        m[sid]["adopted_names"] = list(s["variables_adopted"])  # type: ignore[assignment]
    phys = {"gantry_failed": sum(e["type"] == "gantry_failed" for e in r.physical),
            "transfer_failed": sum(e["type"] == "transfer_failed" for e in r.physical),
            "transfer_complete": sum(e["type"] == "transfer_complete" for e in r.physical)}
    return {"exp": exp, "cond": cond, "i": i, "range": range_name, "systems": m, "physical": phys,
            "fingerprint": r.w.engine.fingerprint(), "seconds": round(time.time() - t0, 2),
            "variable_events": [e for e in sci.events if e["type"] == "variable_candidate"] if exp == "m5" else []}


def _rows(jobs: list[dict], cond: str, sid: str) -> list[dict]:
    return [j["systems"][sid] for j in sorted((j for j in jobs if j["cond"] == cond), key=lambda j: j["i"])]


NUMERIC = [m for m in METRICS if m != "first_request"] + ["blocked_deliveries", "isolated_by_other",
                                                          "after_reopen_experiments", "experiments_selected",
                                                          "variables_adopted"]


def _c(jobs, x: tuple[str, str], y: tuple[str, str], metrics: list[str], seed: int, noise=None) -> dict:
    rx, ry = _rows(jobs, *x), _rows(jobs, *y)
    rx = [{k: v for k, v in r.items() if k in metrics} for r in rx]
    ry = [{k: v for k, v in r.items() if k in metrics} for r in ry]
    return contrast(rx, ry, [m for m in metrics if m in (rx[0] if rx else {})], noise, seed)


def _noise(jobs, cond: str, ref: str, sid: str, metrics: list[str]) -> dict[str, np.ndarray]:
    a, b = _rows(jobs, cond, sid), _rows(jobs, ref, sid)
    return {m: np.array([x.get(m, math.nan) - y.get(m, math.nan) for x, y in zip(a, b, strict=True)], float)
            for m in metrics}


def det(c: dict, m: str) -> bool:
    return c.get(m, {}).get("status") == "DETECTED"


def analyse_m4(jobs: list[dict]) -> dict:
    ms = ["paths", "coverage", "pairs", "completed", "true_gain", "observed_outcomes", "spent", "failed"]
    out: dict[str, Any] = {"contrasts": {}}
    for pre in ("solo", "eq"):
        for x, y in (("A", "B"), ("A", "C"), ("B", "C")):
            key = f"{pre}: {x} vs {y}"
            rx = [{k: v for k, v in r.items() if k in ms} for r in _rows(jobs, f"{pre}_{x}", x)]
            ry = [{k: v for k, v in r.items() if k in ms} for r in _rows(jobs, f"{pre}_{y}", y)]
            out["contrasts"][key] = contrast(rx, ry, ms, None, 4000 + len(out["contrasts"]))
    core = ("paths", "coverage", "pairs", "completed", "true_gain")
    native = {k: [m for m in core if det(v, m)] for k, v in out["contrasts"].items() if k.startswith("solo")}
    eq = {k: [m for m in core if det(v, m)] for k, v in out["contrasts"].items() if k.startswith("eq")}
    ign = {sid: {"seeds_with_requests": sum(1 for r in _rows(jobs, f"solo_{sid}", sid) if r["requests"] > 0),
                 "seeds_with_completed": sum(1 for r in _rows(jobs, f"solo_{sid}", sid) if r["completed"] > 0),
                 "seeds": len(_rows(jobs, f"solo_{sid}", sid))} for sid in "ABC"}
    out["verdicts"] = {
        "native_differences": native, "equalized_differences": eq,
        "M4_heterogeneity": "DEMONSTRATED" if all(native[k] for k in native) else
        "PARTIAL" if any(native[k] for k in native) else "NOT DEMONSTRATED",
        "differences_vanish_under_equalization": {k.replace("eq: ", ""): not v for k, v in eq.items()},
        "T1_independent_ignition": ign}
    return out


def analyse_m5(jobs: list[dict], held: list[dict]) -> dict:
    ms = ["true_gain", "abs_pred_error", "completed", "pairs", "observed_outcomes", "relocations", "window_changes",
          "variables_adopted", "spent", "coverage"]
    noise = _noise(jobs, "F~", "F", "A", ms)
    out: dict[str, Any] = {"contrasts": {}, "heldout": {}}
    for x in ("R", "O", "V", "OV"):
        out["contrasts"][f"{x} vs F"] = _c(jobs, (x, "A"), ("F", "A"), ms, 5000 + len(out["contrasts"]), noise)
    out["contrasts"]["OV vs O"] = _c(jobs, ("OV", "A"), ("O", "A"), ms, 5100, noise)
    out["contrasts"]["OV vs V"] = _c(jobs, ("OV", "A"), ("V", "A"), ms, 5101, noise)
    out["contrasts"]["F~ vs F"] = _c(jobs, ("F~", "A"), ("F", "A"), ms, 5102, None)
    for x in ("O", "V", "OV"):
        out["heldout"][f"{x} vs F"] = _c(held, (x, "A"), ("F", "A"), ms, 5200 + len(out["heldout"]), None)
    adopted: dict[str, int] = {}
    for j in jobs:
        for v in j["systems"]["A"].get("adopted_names", []):
            adopted[v] = adopted.get(v, 0) + 1
    cand = [e for j in jobs for e in j["variable_events"]]
    c = out["contrasts"]
    out["verdicts"] = {
        "M5A_observation_revision": "CONSEQUENTIAL" if det(c["O vs F"], "true_gain") or det(c["O vs F"], "pairs")
        else "NOT DEMONSTRATED",
        "M5A_detected": [m for m in ms if det(c["O vs F"], m)],
        "M5B_variable_generation": "CONSEQUENTIAL" if det(c["V vs F"], "abs_pred_error") and
        c["V vs F"]["abs_pred_error"]["mean"] < 0 or det(c["V vs F"], "true_gain") and c["V vs F"]["true_gain"]["mean"] > 0
        else "NOT DEMONSTRATED",
        "M5B_detected": [m for m in ms if det(c["V vs F"], m)],
        "R_parameter_adaptation_detected": [m for m in ms if det(c["R vs F"], m)],
        "OV_detected_vs_F": [m for m in ms if det(c["OV vs F"], m)],
        "heldout_detected": {k: [m for m in ms if det(v, m)] for k, v in out["heldout"].items()},
        "adopted_variables": dict(sorted(adopted.items(), key=lambda kv: -kv[1])),
        "candidates_evaluated": len(cand), "candidates_adopted": sum(1 for e in cand if e["adopted"]),
        "noise_detected": [m for m in ms if det(c["F~ vs F"], m)]}
    return out


def analyse_m6(jobs: list[dict]) -> dict:
    ms = ["true_gain_post", "true_gain", "completed", "pairs", "memory_reads", "memory_unavailable", "abs_pred_error",
          "failed"]
    noise = _noise(jobs, "H2~", "H2", "C", ms)
    out: dict[str, Any] = {"contrasts": {}}
    for x, y in (("H2", "H1"), ("H2", "H0"), ("H2", "H3"), ("H2", "H4"), ("H2", "H5"), ("H1", "H0"), ("H3", "H1"),
                 ("H4", "H0"), ("H5", "H0")):
        out["contrasts"][f"{x} vs {y}"] = _c(jobs, (x, "C"), (y, "C"), ms, 6000 + len(out["contrasts"]), noise)
    out["contrasts"]["H2~ vs H2"] = _c(jobs, ("H2~", "C"), ("H2", "C"), ms, 6100, None)
    c = out["contrasts"]
    pos = lambda k: det(c[k], "true_gain_post") and c[k]["true_gain_post"]["mean"] > 0  # noqa: E731
    out["verdicts"] = {
        "primary_H2_vs_H1": "SUPPORTED" if pos("H2 vs H1") else "NOT SUPPORTED",
        "H2_beyond_shuffled": pos("H2 vs H3"), "H2_beyond_stochastic": pos("H2 vs H5"),
        "H2_beyond_disabled": pos("H2 vs H4"), "memory_vs_none": pos("H1 vs H0"),
        "detected": {k: [m for m in ms if det(v, m)] for k, v in c.items()},
        "inherited_negative_record": "unverified on this machine; not overwritten (docs/LAB.md)"}
    return out


def analyse_m7(jobs: list[dict]) -> dict:
    ms = ["coverage", "paths", "completed", "true_gain", "pairs", "failed", "blocked_deliveries", "isolated_by_other",
          "after_reopen_experiments", "isolations", "observed_outcomes"]
    out: dict[str, Any] = {"contrasts": {}}
    pairs = {"T2: B in ALL vs noA": (("ALL", "B"), ("noA", "B")), "T2: A in ALL vs noB": (("ALL", "A"), ("noB", "A")),
             "T2: C in ALL vs noA": (("ALL", "C"), ("noA", "C")), "T2: A in ALL vs noC": (("ALL", "A"), ("noC", "A")),
             "T3/T4: A in ALL vs noIso": (("ALL", "A"), ("noIso", "A")),
             "T3/T4: C in ALL vs noIso": (("ALL", "C"), ("noIso", "C")),
             "T6: A in memShare vs ALL": (("memShare", "A"), ("ALL", "A")),
             "T7: B in noComm vs noComm_noA": (("noComm", "B"), ("noComm_noA", "B")),
             "noise: ALL~ vs ALL (A)": (("ALL~", "A"), ("ALL", "A")),
             "noise: ALL~ vs ALL (B)": (("ALL~", "B"), ("ALL", "B"))}
    for k, (x, y) in pairs.items():
        out["contrasts"][k] = _c(jobs, x, y, ms, 7000 + len(out["contrasts"]), None)
    c = out["contrasts"]
    allA = _rows(jobs, "ALL", "A")
    out["counts"] = {
        "A_blocked_by_B_isolation_total": sum(r["isolated_by_other"] for r in allA),
        "A_experiments_on_reopened_chambers_total": sum(r["after_reopen_experiments"] for r in allA),
        "seeds_with_blocking": sum(1 for r in allA if r["isolated_by_other"] > 0),
        "seeds_with_reignition": sum(1 for r in allA if r["after_reopen_experiments"] > 0),
        "A_blocked_in_noIso_total": sum(r["isolated_by_other"] for r in _rows(jobs, "noIso", "A"))}
    d = lambda k: [m for m in ms if det(c[k], m)]  # noqa: E731
    out["verdicts"] = {
        "T2_interference": {k: d(k) for k in c if k.startswith("T2")},
        "T3_extinction": {"A_blocked_by_isolation_seeds": out["counts"]["seeds_with_blocking"],
                          "detected_vs_noIso": d("T3/T4: A in ALL vs noIso")},
        "T4_substitution": {"A_completed_status_vs_noIso": c["T3/T4: A in ALL vs noIso"].get("completed", {}).get("status"),
                            "A_true_gain_status_vs_noIso": c["T3/T4: A in ALL vs noIso"].get("true_gain", {}).get("status")},
        "T5_reignition": {"seeds_with_experiments_on_reopened_chambers": out["counts"]["seeds_with_reignition"]},
        "T6_cross_system_history": d("T6: A in memShare vs ALL"),
        "T7_counterfactual_removal": {
            "B_dependence_on_A_with_conduit_comm": d("T2: B in ALL vs noA"),
            "B_dependence_on_A_with_comm_free": d("T7: B in noComm vs noComm_noA"),
            "A_blocked_without_isolation": out["counts"]["A_blocked_in_noIso_total"]},
        "noise_detected": {k: d(k) for k in c if k.startswith("noise")}}
    return out


def run_experiment(name: str, procs: int, confirmatory: bool = True, range_name: str = "confirm",
                   seeds: int | None = None) -> dict:
    if confirmatory:
        check_protocol()
    exp = EXPERIMENTS[name]
    n = seeds or SEEDS[name]
    t0 = time.time()
    jobs = run_pool(job, [(name, c, i, range_name) for c in exp for i in range(n)], procs)
    doc: dict[str, Any] = {"experiment": name, "seeds": n, "range": range_name, "conditions": {k: v for k, v in exp.items()},
                           "base": BASE, "seed_ranges": RANGES[range_name]}
    if name == "m4":
        doc.update(analyse_m4(jobs))
    elif name == "m5":
        held_n = seeds or SEEDS["m5_heldout"]
        held = run_pool(job, [(name, c, i, "heldout" if range_name == "confirm" else range_name)
                              for c in M5_HELDOUT for i in range(held_n)], procs)
        doc["heldout_seeds"] = held_n
        doc.update(analyse_m5(jobs, held))
        jobs += held
    elif name == "m6":
        doc["config_change"] = CHANGE
        doc.update(analyse_m6(jobs))
    else:
        doc.update(analyse_m7(jobs))
    doc["means"] = {f"{j_c}/{sid}": {m: _mean([r[m] for r in _rows(jobs, j_c, sid)]) for m in NUMERIC}
                    for j_c in exp for sid in [s["sid"] for s in exp[j_c]]}
    doc["runs"] = len(jobs)
    doc["simulated_steps"] = len(jobs) * BASE["horizon"]
    doc["seconds_per_run_mean"] = round(float(np.mean([j["seconds"] for j in jobs])), 2)
    doc["elapsed_s"] = round(time.time() - t0, 1)
    from ..experiments.escalation.runner import provenance
    doc["provenance"] = provenance()
    doc["protocol_sha256"] = protocol_hash()
    doc["pinned_protocol_sha256"] = PROTOCOL_SHA256
    doc["fingerprints"] = {f"{j['cond']}/{j['range']}/{j['i']}": j["fingerprint"] for j in jobs}
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
