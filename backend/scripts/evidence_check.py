"""Check a finished study directory against the evidence policy (docs/research/EVIDENCE_MANAGEMENT.md): every item a paper result must be tied to is present, the
stored files match their checksums, and the traceability limits are named (a dirty working tree at creation, a missing numerical-build record). Reads only.

Grades: COMPLETE (every item, clean tree) · COMPLETE-WITH-LIMITS (every item, but the tree was dirty or the numerical build is not recorded: the limit is listed) ·
INCOMPLETE (an item is missing or a checksum fails). A confirmatory study must be COMPLETE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from xzr.study import protocol as P
from xzr.study import report, runner

REQUIRED_MANIFEST = ("git_commit", "git_branch", "git_dirty", "python", "platform", "dependencies")


def check(study_dir: Path) -> dict:
    st = runner.Study(study_dir)
    doc, man = st.protocol(), st.manifest()
    env = man["environment"]
    runs = st.runs()
    seeds = P.seed_list(doc)
    items, limits = {}, []
    items["protocol digest equals the registered digest"] = P.digest(st.registered()) == man["protocol_digest"]
    items["manifest carries commit, branch, dirty flag, interpreter, platform, dependencies"] = all(
        k in env for k in REQUIRED_MANIFEST
    )
    items["seeds recorded in the protocol"] = len(seeds) >= 1
    items["one record per arm x seed (failed and timed-out runs kept)"] = len(runs) == len(doc["arms"]) * len(seeds)
    items["raw run records present"] = (study_dir / "runs").is_dir() and len(list((study_dir / "runs").glob("*.json"))) == len(
        runs
    )
    items["checksums.json present and every file matches"] = (study_dir / "checksums.json").exists() and report.verify(study_dir)[
        "ok"
    ]
    items["analysis, Methods, Results present"] = (study_dir / "analysis.json").exists() and all(
        (study_dir / "report" / n).exists() for n in ("methods.md", "results.md")
    )
    items["REPRODUCE.md present"] = (study_dir / "REPRODUCE.md").exists()
    if env.get("git_dirty"):
        limits.append(
            f"the working tree was dirty at creation ({len(env.get('git_dirty_files', []))} files listed in the manifest: names only, not content)"
        )
    if "numeric_build" not in env:
        limits.append(
            "the numerical build (BLAS/LAPACK) and the hierarchy method are not recorded (study made before that record existed)"
        )
    failed = sum(r.get("status") != "ok" for r in runs)
    grade = "INCOMPLETE" if not all(items.values()) else ("COMPLETE-WITH-LIMITS" if limits else "COMPLETE")
    return {
        "study": study_dir.name,
        "mode": doc["mode"],
        "environment_kind": doc["environment"]["kind"],
        "git_commit": env["git_commit"][:12],
        "protocol_digest": man["protocol_digest"][:12],
        "runs": len(runs),
        "failed_or_timed_out": failed,
        "items": items,
        "limits": limits,
        "grade": grade,
        "confirmatory_eligible": grade == "COMPLETE" and doc["mode"] == "confirmatory",
    }


if __name__ == "__main__":
    root = Path(sys.argv[1])
    ids = json.loads(Path(sys.argv[2]).read_text())
    res = [check(root / s) for s in ids]
    Path(sys.argv[3]).write_text(json.dumps(res, indent=1))
    for r in res:
        print(f"{r['study']}  {r['environment_kind']:18s} {r['grade']:21s} {'; '.join(r['limits'])[:110]}")
