"""Stage 6: run-level rows of the validation (seeds 6-10) and evaluation (seeds 11-30) runs, and the check that they give the saved summaries.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_run_rows.py     # about 8 minutes on 8 cores

The exploration rows (seeds 1-5) of every setting were saved when they were run (experiments_stage6_raw*.jsonl.gz, experiments_stage6_followup_raw.jsonl.gz); for the validation and evaluation seeds only the summaries were saved (counts, Wilson rates, outcome counts).
This script runs again every setting that has such a summary, with the fixed settings, seeds and criterion of Pipeline A and of the follow-up, and saves **every run** (not the summary) to experiments_stage6_validation_evaluation_rows.jsonl.gz. These rows were regenerated
after the original runs, on the engine version and the source commit recorded in the file's first line; they are not the original run records. Each setting's regenerated counts are compared with the saved summary: the comparison is saved in evidence/run_rows_verification.json
(a mismatch would be a finding, not something to fix)."""

from __future__ import annotations

import gzip
import json
import subprocess
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import repair6 as R
from xzr.meos import stage5_experiments as X5
from xzr.meos import stage6_experiments as S6

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"


def _single(a: tuple) -> dict:
    return S6._job(a)


def _comb(a: tuple) -> dict:
    return S6._cjob(a)


def main() -> None:
    t0 = time.time()
    src = {"A": json.loads((DOCS / "experiments_stage6.json").read_text()), "follow-up": json.loads((DOCS / "experiments_stage6_followup.json").read_text())}
    jobs_s: list[tuple] = []
    jobs_c: list[tuple] = []
    meta: list[dict] = []
    for origin, d in src.items():
        for r in d["single_settings"]:
            seeds = [*(R.VALIDATION_SEEDS if r["validation_effective"] is not None else ()), *(R.EVAL_SEEDS if r["evaluation"] is not None else ())]
            meta.append({"origin": origin, "kind": "single", "key": [r["stress"], r["action"], r["magnitude"], r["duration"], r["t"]], "row": r, "n": len(seeds)})
            jobs_s += [(r["stress"], r["action"], r["magnitude"], r["duration"], r["t"], sd) for sd in seeds]
        for r in d["combined_settings"]:
            seeds = [*(R.VALIDATION_SEEDS if r["validation_effective"] is not None else ()), *(R.EVAL_SEEDS if r["evaluation"] is not None else ())]
            meta.append({"origin": origin, "kind": "combined", "key": [r["stress"], r["parts"], r["t"]], "row": r, "n": len(seeds)})
            jobs_c += [(r["stress"], tuple(map(tuple, r["parts"])), r["t"], sd) for sd in seeds]
    rs, rc = X5.pmap(_single, jobs_s, None, chunksize=8), X5.pmap(_comb, jobs_c, None, chunksize=8)
    out_rows, it_s, it_c = [], iter(rs), iter(rc)
    results: list[dict] = []
    for m in meta:
        rows = [next(it_s if m["kind"] == "single" else it_c) for _ in range(m["n"])]
        val = [r for r in rows if r["seed"] in R.VALIDATION_SEEDS]
        ev = [r for r in rows if r["seed"] in R.EVAL_SEEDS]
        for r in rows:
            out_rows.append({"origin": m["origin"], "kind": m["kind"], **r})
        row = m["row"]
        ok_v = f"{sum(S6.row_ok(r) for r in val)}/{len(val)}" if val else None
        ok_e = (sum(S6.row_ok(r) for r in ev), len(ev)) if ev else None
        match_v = ok_v == row["validation_effective"]
        match_e = (ok_e is None and row["evaluation"] is None) or (ok_e == (row["evaluation"]["k"], row["evaluation"]["n"]) and S6._count([r["outcome"][2] for r in ev]) == row["evaluation_outcomes_long"])
        results.append({"origin": m["origin"], "kind": m["kind"], "key": m["key"], "validation_saved": row["validation_effective"], "validation_rerun": ok_v, "evaluation_saved": None if row["evaluation"] is None else [row["evaluation"]["k"], row["evaluation"]["n"]], "evaluation_rerun": ok_e, "match": bool(match_v and match_e)})
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=DOCS).stdout.strip()
    with gzip.open(DOCS / "experiments_stage6_validation_evaluation_rows.jsonl.gz", "wt") as f:
        f.write(json.dumps({"regenerated": time.strftime("%Y-%m-%d"), "engine": E.ENGINE_VERSION, "source_commit_of_the_working_tree": commit, "note": "regenerated run-level rows of the validation (seeds 6-10) and evaluation (11-30) runs; not the original run records"}) + "\n")
        for r in out_rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    summary = {"engine": E.ENGINE_VERSION, "settings": len(results), "runs": len(out_rows), "settings_matching_the_saved_summary": sum(r["match"] for r in results), "mismatches": [r for r in results if not r["match"]], "seconds": round(time.time() - t0, 1), "results": results}
    (DOCS / "evidence" / "run_rows_verification.json").write_text(json.dumps(summary, indent=1))
    print({k: v for k, v in summary.items() if k not in ("results", "mismatches")}, "mismatches:", len(summary["mismatches"]))


if __name__ == "__main__":
    main()
