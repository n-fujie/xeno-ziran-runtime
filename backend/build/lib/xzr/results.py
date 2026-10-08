"""Running an experiment configuration and the result schema (``xzr.result/1``).

A run writes one directory and never touches anything outside it:

    <out>/<experiment-id>/<run-id>/
        config.json     the effective configuration (every condition fully expanded) — what actually ran
        result.json     schema xzr.result/1 (below)
        summary.txt     the human-readable summary printed at the end of the run
        raw.json        the harness's own analysis file (kind "conditions"), as written by the published studies
        jobs/           per-seed raw outputs (gzip pickles, kind "conditions"; re-analysable)

``run-id`` = UTC time + a hash of the effective configuration. An existing run directory is never overwritten.

result.json:
    schema, run_id, experiment_id, kind, timestamp, seeds, provenance (version, git commit + dirty flag when run
    from a source checkout, hash of the package code, Python / numpy versions), effective_configuration,
    baseline_configuration, conditions[] (id, changed settings, result or failure), warnings[], failures[],
    artifacts[] — plus ``statistics_note`` stating what the seed count can and cannot support.

Comparison of two results (``compare``) labels every (condition, comparison, resolution) cell as same, changed,
newly detectable, extinguished or missing; within one result, a comparison detected in some conditions and not in
others is configuration-sensitive. A residual difference is only a difference: interpreting it (e.g. as novelty) is
outside this code.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

RESULT_SCHEMA = "xzr.result/1"
RESOLUTIONS = ("node", "local", "meso", "macro", "global")
MIN_SEEDS_FOR_TEST = 8  # the exact sign-flip test needs 2/2^S below the per-resolution level (0.002 ⇒ S ≥ 10)


class RunExistsError(FileExistsError):
    pass


def run_id_for(eff: dict) -> str:
    h = hashlib.sha256(json.dumps(eff, sort_keys=True).encode()).hexdigest()[:8]
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + h


def _history_job(args: tuple) -> dict:
    from .experiments.history import seed_job
    p, seed = args
    return seed_job(p, seed)


def execute(eff: dict, out_root: Path, procs: int = 4, run_id: str | None = None) -> Path:
    """Run an effective configuration into a new run directory; returns the directory."""
    from .experiments.escalation.runner import provenance

    run_id = run_id or run_id_for(eff)
    run_dir = Path(out_root) / eff["id"] / run_id
    if run_dir.exists():
        raise RunExistsError(f"{run_dir} already exists; results are never overwritten")
    run_dir.mkdir(parents=True)
    (run_dir / "config.json").write_text(json.dumps(eff, indent=1))
    t0 = time.time()
    prov = provenance()
    warnings: list[str] = []
    failures: list[dict] = []
    seeds = list(range(eff["seed0"], eff["seed0"] + eff["seeds"]))
    if eff["seeds"] < MIN_SEEDS_FOR_TEST:
        warnings.append(f"{eff['seeds']} seed(s): the sign-flip tests cannot reach significance with fewer than "
                        f"{MIN_SEEDS_FOR_TEST} seeds (10 for the five-resolution analysis); no statistical claim "
                        "is supported by this run")
    conditions: list[dict] = []
    if eff["kind"] == "conditions":
        from .experiments.escalation.runner import run_conditions
        conds = []
        for c in eff["conditions"]:
            c = dict(c)
            for k in ("variants", "triggers", "revert", "world_schedule"):
                if isinstance(c.get(k), list):
                    c[k] = tuple(c[k])
            conds.append(c)
        doc = run_conditions(conds, run_dir / "raw.json", procs, meta={"experiment": eff["id"]}, seed0=eff["seed0"])
        for c in eff["conditions"]:
            r = doc["conditions"].get(c["id"])
            entry: dict[str, Any] = {"id": c["id"], "changed": {k: c[k] for k in c["changed"]}}
            if r is None or "analysis_error" in r:
                failures.append({"condition": c["id"], "error": (r or {}).get("analysis_error", "no result")})
                entry["failed"] = True
            else:
                entry["comparisons"] = {
                    k: {"status": v["classification"]["status"], "labels": v["classification"]["labels"],
                        "primary": v["classification"].get("primary"), "evidence": v["classification"].get("evidence"),
                        "exact_identical_share": v.get("exact_identical_share")}
                    for k, v in r["comparisons"].items()}
                entry["reference_metrics"] = {k: r["reference"].get(k) for k in ("reasoning_share", "revisions_mean")
                                              if k in r["reference"]}
            conditions.append(entry)
        artifacts = ["config.json", "result.json", "summary.txt", "raw.json", "jobs/"]
    else:
        from .experiments.history import analyse
        p = eff["history"]
        with ProcessPoolExecutor(max(1, min(procs, len(seeds)))) as ex:
            jobs: list[dict] = list(ex.map(_history_job, [(p, s) for s in seeds]))
        (run_dir / "jobs.json").write_text(json.dumps(jobs))
        a = analyse(p, jobs)
        conditions.append({"id": "history", "changed": {"region": p["region"], "operations": p["operations"]},
                           "comparisons": a["comparisons"], "history_reentry": a["history_reentry"]})
        if any(not j["branches"].get("fork", {}).get("bit_identical_to_intact", True) for j in jobs):
            failures.append({"condition": "history", "error": "fork was not bit-identical to the intact branch"})
        artifacts = ["config.json", "result.json", "summary.txt", "jobs.json"]
    result = {
        "schema": RESULT_SCHEMA, "run_id": run_id, "experiment_id": eff["id"], "kind": eff["kind"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elapsed_s": round(time.time() - t0, 1),
        "seeds": seeds, "provenance": prov, "effective_configuration": eff,
        "baseline_configuration": eff.get("baseline") or eff.get("history"),
        "conditions": conditions, "warnings": warnings, "failures": failures, "artifacts": artifacts,
        "statistics_note": statistics_note(eff),
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=1, default=_default))
    (run_dir / "summary.txt").write_text(summary(result))
    return run_dir


def _default(x: Any) -> Any:
    import numpy as np
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    raise TypeError(type(x).__name__)


def statistics_note(eff: dict) -> str:
    s = eff["seeds"]
    if eff["kind"] == "conditions":
        if s < 10:
            return (f"{s} seeds: below the 10 needed for the five-resolution sign-flip test (α = 0.002 per resolution); "
                    "DETECTED here can only come from deterministic (identical-in-every-seed) differences.")
        return (f"{s} paired seeds; family-wise sign-flip max-T test per resolution (α = 0.01 / 5), practical threshold "
                "2 % of baseline, equivalence ±5 %; the noise replicate C~ is the false-positive control. Statistical "
                "statements hold for this configuration and seed set only.")
    if s < MIN_SEEDS_FOR_TEST:
        return f"{s} seeds: below {MIN_SEEDS_FOR_TEST}; all non-identical differences are reported UNRESOLVED."
    return (f"{s} paired seeds; exact two-sided sign-flip test per metric (α = 0.01), practical threshold 2 %, larger "
            "than every noise-branch difference; equivalence ±5 %. Not corrected across metrics.")


# ------------------------------------------------------------------------------------------------ summaries
def configuration_sensitivity(result: dict) -> dict[str, dict]:
    """Per comparison: conditions where it is detected at a coarse (macro/global) resolution, and where not."""
    out: dict[str, dict] = {}
    for c in result["conditions"]:
        for name, cmp_ in (c.get("comparisons") or {}).items():
            st = cmp_.get("status") if isinstance(cmp_.get("status"), dict) else None
            if st is None:
                continue
            row = out.setdefault(name, {"detected_in": [], "not_detected_in": []})
            hit = any(st.get(r) == "DETECTED" for r in ("macro", "global"))
            row["detected_in" if hit else "not_detected_in"].append(c["id"])
    for row in out.values():
        row["pattern"] = ("detected in every condition" if not row["not_detected_in"] else
                          "not detected in any condition" if not row["detected_in"] else "configuration-sensitive")
    return out


def summary(result: dict) -> str:
    lines = [f"{result['experiment_id']}  run {result['run_id']}  ({result['elapsed_s']} s)",
             f"seeds {result['seeds'][0]}…{result['seeds'][-1]} ({len(result['seeds'])}); "
             f"version {result['provenance'].get('version')}, commit {result['provenance'].get('git_head') or 'n/a'}"
             f"{' (uncommitted changes)' if result['provenance'].get('dirty') else ''}", ""]
    if result["kind"] == "conditions":
        if len(result["seeds"]) < 10:
            lines += [f"NOTE: {len(result['seeds'])} seeds — the statuses below are NOT statistically interpretable "
                      "(even the noise replicate C~ can show DETECTED); use ≥ 10 seeds for any claim.", ""]
        lines.append("status per resolution (node local meso macro global) of each comparison against the reference C:")
        for c in result["conditions"]:
            if c.get("failed"):
                lines.append(f"  {c['id']}: FAILED (see result.json failures)")
                continue
            lines.append(f"  {c['id']}" + (f"  [changed: {', '.join(f'{k}={v}' for k, v in c['changed'].items())}]"
                                           if c["changed"] else ""))
            for name, cmp_ in c["comparisons"].items():
                st = " ".join(f"{cmp_['status'][r][:4]:4s}" for r in RESOLUTIONS)
                lines.append(f"    {name:>16s}  {st}   {', '.join(cmp_['labels'])}")
        lines += ["", "across conditions (detected at macro or global resolution):"]
        for name, row in configuration_sensitivity(result).items():
            lines.append(f"  {name:>16s}  {row['pattern']}" + (f" — detected in: {', '.join(row['detected_in'])}"
                                                                if row["pattern"] == "configuration-sensitive" else ""))
        lines += ["", "DETE = DETECTED (systematic), EQUI = EQUIVALENT (within ±5 %), UNRE = UNRESOLVED (neither shown), "
                  "REDUNDANT = bit-identical. C~ is the noise replicate: anything it shows is a false positive."]
    else:
        c = result["conditions"][0]
        lines.append("paired difference against the intact branch (status; relative mean difference):")
        metrics = [m for m in next(iter(c["comparisons"].values())) if m != "bit_identical_share"]
        for kind, rows in c["comparisons"].items():
            cells = ", ".join(f"{m} {rows[m]['status']} ({rows[m]['relative']:+.1%})" for m in metrics)
            tag = "  (control: other random stream — ordinary trajectory divergence)" if kind == "noise" else ""
            lines.append(f"  {kind:>10s}  bit-identical share {rows['bit_identical_share']:.2f}; {cells}{tag}")
        h = c["history_reentry"]
        lines += ["", f"history re-entry verdict: {h['verdict']}"]
        for k, v in h.get("criteria", {}).items():
            lines.append(f"  {k}: {v}")
        lines.append(f"  note: {h.get('note', '')}")
    lines += ["", f"statistics: {result['statistics_note']}"]
    if result["warnings"]:
        lines += ["", "warnings:"] + [f"  - {w}" for w in result["warnings"]]
    if result["failures"]:
        lines += ["", "FAILURES:"] + [f"  - {f['condition']}: {str(f['error'])[:300]}" for f in result["failures"]]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------ load / compare
def load(path: str | Path) -> dict:
    p = Path(path)
    if p.is_dir():
        p = p / "result.json"
    r = json.loads(p.read_text())
    if r.get("schema") != RESULT_SCHEMA:
        raise ValueError(f"{p}: not an {RESULT_SCHEMA} file")
    return r


def _cells(result: dict) -> dict[tuple[str, str, str], str]:
    cells = {}
    for c in result["conditions"]:
        for name, cmp_ in (c.get("comparisons") or {}).items():
            st = cmp_.get("status")
            if isinstance(st, dict):  # kind "conditions": per resolution
                for r in RESOLUTIONS:
                    cells[(c["id"], name, r)] = st[r]
            else:  # kind "history": per metric
                for m, v in cmp_.items():
                    if isinstance(v, dict) and "status" in v:
                        cells[(c["id"], name, m)] = v["status"]
    return cells


def compare(a: dict, b: dict) -> dict:
    """Cell-by-cell comparison of two results (same experiment structure expected)."""
    ca, cb = _cells(a), _cells(b)
    rows = []
    for key in sorted(set(ca) | set(cb)):
        x, y = ca.get(key), cb.get(key)
        if x is None or y is None:
            label = "missing in A" if x is None else "missing in B"
        elif x == y:
            label = "same"
        elif y == "DETECTED":
            label = "newly detectable"
        elif x == "DETECTED":
            label = "extinguished"
        else:
            label = "changed"
        rows.append({"condition": key[0], "comparison": key[1], "measure": key[2], "a": x, "b": y, "label": label})
    counts: dict[str, int] = {}
    for r in rows:
        label_ = str(r["label"])
        counts[label_] = counts.get(label_, 0) + 1
    return {"a": a["run_id"], "b": b["run_id"], "counts": counts, "cells": rows,
            "note": "Labels describe changes in detection status only. Whether a newly detectable difference is "
                    "theoretically novel is an interpretation outside this comparison."}


def export_csv(result: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["run_id", "experiment_id", "condition", "comparison", "measure", "status"])
    for (cond, cmp_, m), st in sorted(_cells(result).items()):
        w.writerow([result["run_id"], result["experiment_id"], cond, cmp_, m, st])
    return buf.getvalue()
