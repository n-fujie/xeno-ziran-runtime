"""Independent audit of the Study Engine's statistics: recompute the deterministic quantities of stored studies from their raw run records with separate code
(numpy / scipy, not the engine's analysis functions) and compare them with analysis.json. Bootstrap intervals and permutation p-values depend on the engine's seeded
resampling and are only checked for consistency (the interval contains the mean difference; p within [0, 1]); everything else must agree to 1e-9.
Reads stored studies; changes nothing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1] / "experiments" / "studies"
TOL = 1e-9


def metric_vec(runs: dict, arm: str, m: str, n: int) -> np.ndarray:
    out = []
    for k in range(n):
        r = runs.get((arm, k))
        v = (r.get("metrics") or {}).get(m) if r and r["status"] == "ok" else None
        out.append(np.nan if v is None else float(v))
    return np.array(out)


def close(a, b) -> bool:
    return (a is None and b is None) or (
        a is not None and b is not None and abs(float(a) - float(b)) <= TOL * max(1.0, abs(float(b)))
    )


def audit(sid: str) -> dict:
    d = ROOT / sid
    an = json.loads((d / "analysis.json").read_text())
    runs = {}
    for p in (d / "runs").glob("*.json"):
        r = json.loads(p.read_text())
        runs[(r["arm"], r["index"])] = r
    n = len(an["seeds"])
    checks, bad = 0, []

    def check(label: str, got, want) -> None:
        nonlocal checks
        checks += 1
        if not close(got, want):
            bad.append({"what": label, "engine": want, "independent": got})

    for arm, per in an["descriptives"].items():
        for m, ds in per.items():
            x = metric_vec(runs, arm, m, n)
            x = x[~np.isnan(x)]
            if not ds.get("n"):
                continue
            check(f"{arm}/{m} n", len(x), ds["n"])
            check(f"{arm}/{m} mean", float(x.mean()), ds["mean"])
            check(f"{arm}/{m} median", float(np.median(x)), ds["median"])
            check(f"{arm}/{m} min", float(x.min()), ds["min"])
            check(f"{arm}/{m} max", float(x.max()), ds["max"])
            if len(x) > 1:
                check(f"{arm}/{m} sd", float(x.std(ddof=1)), ds["sd"])
                check(f"{arm}/{m} var", float(x.var(ddof=1)), ds["var"])
    for c in an["contrasts"]:
        for m, r in c["metrics"].items():
            x, y = metric_vec(runs, c["a"], m, n), metric_vec(runs, c["b"], m, n)
            ok = ~np.isnan(x) & ~np.isnan(y)
            x, y = x[ok], y[ok]
            tag = f"{c['id']}/{m}"
            if r.get("n") != len(x):
                bad.append({"what": f"{tag} n", "engine": r.get("n"), "independent": int(len(x))})
                continue
            if len(x) < 2:
                checks += 1
                if r.get("p") is not None or r.get("dz") is not None:
                    bad.append(
                        {
                            "what": f"{tag} undefined statistics replaced by numbers",
                            "engine": [r.get("p"), r.get("dz")],
                            "independent": None,
                        }
                    )
                continue
            diff = x - y
            check(f"{tag} mean_x", float(x.mean()), r["mean_x"])
            check(f"{tag} mean_y", float(y.mean()), r["mean_y"])
            check(f"{tag} mean diff", float(diff.mean()), r["mean"])
            check(f"{tag} sd of diff", float(diff.std(ddof=1)), r["sd"])
            if diff.std(ddof=1) > 0:
                check(f"{tag} dz", float(diff.mean() / diff.std(ddof=1)), r["dz"])
            ind = r.get("independent") or {}
            xa, ya = metric_vec(runs, c["a"], m, n), metric_vec(runs, c["b"], m, n)
            xa, ya = xa[~np.isnan(xa)], ya[~np.isnan(ya)]  # the independent-trials comparison uses each arm's own values
            if ind.get("welch_p") is not None and len(xa) > 1 and len(ya) > 1 and (xa.std() > 0 or ya.std() > 0):
                check(f"{tag} welch p", float(stats.ttest_ind(xa, ya, equal_var=False).pvalue), ind["welch_p"])
            if ind.get("mann_whitney_p") is not None:
                check(
                    f"{tag} mann-whitney p",
                    float(stats.mannwhitneyu(xa, ya, alternative="two-sided").pvalue),
                    ind["mann_whitney_p"],
                )
            sens = r.get("sensitivity") or {}
            if sens.get("wilcoxon_p") is not None and np.any(diff != 0):
                check(f"{tag} wilcoxon p", float(stats.wilcoxon(diff).pvalue), sens["wilcoxon_p"])
            if len(diff) > 1 and sens.get("leave_one_out_mean_range"):
                loo = [float(np.delete(diff, i).mean()) for i in range(len(diff))]
                check(f"{tag} leave-one-out min", min(loo), sens["leave_one_out_mean_range"][0])
                check(f"{tag} leave-one-out max", max(loo), sens["leave_one_out_mean_range"][1])
            ci = r.get("ci95")
            checks += 1
            if ci and not (ci[0] - 1e-9 <= float(diff.mean()) <= ci[1] + 1e-9):
                bad.append(
                    {
                        "what": f"{tag} bootstrap interval does not contain the mean difference",
                        "engine": ci,
                        "independent": float(diff.mean()),
                    }
                )
            checks += 1
            if r.get("p") is not None and not 0 <= r["p"] <= 1:
                bad.append({"what": f"{tag} p outside [0,1]", "engine": r["p"], "independent": None})
    stale = [b for b in bad if "undefined statistics replaced" in b["what"]]
    note = None
    if stale:
        from xzr.study import analysis as engine
        from xzr.study import runner

        now = engine.analyse(runner.Study(d), write=False)  # recomputed with the current code; the stored file is not touched
        still = sum(
            1
            for c in now["contrasts"]
            for r in c["metrics"].values()
            if (r.get("n") or 0) < 2 and (r.get("p") is not None or r.get("dz") is not None)
        )
        note = {
            "stored_analysis_predates_the_small_sample_fix": len(stale),
            "current_code_rows_with_numbers_for_n_below_2": still,
        }
        if still == 0:
            bad = [b for b in bad if b not in stale]
    return {
        "study": sid,
        "environment": an.get("experiment_id"),
        "checks": checks,
        "disagreements": bad,
        "stale_stored_analysis": note,
    }


if __name__ == "__main__":
    ids = json.loads(Path(sys.argv[1]).read_text())
    res = [audit(s) for s in ids]
    Path(sys.argv[2]).write_text(json.dumps(res, indent=1, default=float))
    for r in res:
        print(
            r["study"],
            f"{r['checks']} checks,",
            f"{len(r['disagreements'])} disagreements",
            r["disagreements"][:2],
            r["stale_stored_analysis"] or "",
        )
