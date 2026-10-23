"""Collect the evidence of finished studies into one record: ids, digests, seeds, run counts, time, stored files, package checksum, replay agreement over EVERY
run, whole-study re-execution agreement, analysis / figures / Methods / Results, and the interpretation limit of the environment. Reads stored studies only; it
changes nothing in them (replay re-executes runs in memory and compares)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

NODE = Path.home() / ".nvm/versions/node/v24.14.1/bin"
if NODE.is_dir():
    os.environ["PATH"] = f"{NODE}:{os.environ['PATH']}"

from xzr.study import protocol as P  # noqa: E402
from xzr.study import report, runner  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "experiments" / "studies"
LIMITS = {
    "hpo-world": "functional sample; same-machine bit-reproducibility; address-based results are not guaranteed cross-platform (the two known failures)",
    "ards": "ARDS test mode only (replicates 3980-3989): a functional check by construction; not a confirmatory path",
    "shared-oi": "ARDS test mode only; ARDS and HPO policies are structurally close, so the comparison is policy-level",
    "total-observation": "synthetic regional model; not the Earth; recall = what the system observed (not reproducibility); stationary sources hide the cost of delay",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def collect(label: str, sid: str, repro: str | None, replay_all: bool = True) -> dict:
    st = runner.Study(ROOT / sid)
    doc, man = st.protocol(), st.manifest()
    runs = st.runs()
    t0 = time.time()
    rp = [runner.replay_run(st, r["arm"], r["index"])["agreement"] for r in runs] if replay_all else []
    files = [p for p in st.path.rglob("*") if p.is_file()]
    rep = st.path / "report"
    out = {
        "environment": label,
        "experiment_id": sid,
        "protocol_digest": man["protocol_digest"],
        "registered_digest_identical": P.digest(st.registered()) == man["protocol_digest"],
        "kind": doc["environment"]["kind"],
        "rules_version": doc["environment"].get("rules_version", "v1 (absent)"),
        "mode": doc["mode"],
        "seeds": {"n": len(P.seed_list(doc)), "first": P.seed_list(doc)[0], "last": P.seed_list(doc)[-1]},
        "arms": len(doc["arms"]),
        "runs": len(runs),
        "ok": sum(r["status"] == "ok" for r in runs),
        "failed": sum(r["status"] != "ok" for r in runs),
        "run_seconds_sum": round(sum(r.get("wall_s") or 0 for r in runs), 1),
        "stored_files": len(files),
        "package_checksums_sha256": sha(st.path / "checksums.json") if (st.path / "checksums.json").exists() else None,
        "package_verified": report.verify(st.path)["ok"] if (st.path / "checksums.json").exists() else None,
        "analysis": (st.path / "analysis.json").exists(),
        "figures": len(list(rep.glob("*.svg"))) if rep.exists() else 0,
        "methods_results": [(rep / n).exists() for n in ("methods.md", "results.md")],
        "replay_runs": len(rp),
        "replay_agreement": (sum(rp) / len(rp)) if rp else None,
        "git": {"commit": man["environment"]["git_commit"][:12], "dirty": man["environment"]["git_dirty"]},
        "limit": LIMITS.get(doc["environment"]["kind"], ""),
    }
    if repro:
        r2 = json.loads((ROOT / repro / "reproduction.json").read_text())
        out["reproduction"] = {"study": repro, "identical_share": r2["identical_share"], "runs_compared": r2["runs_compared"]}
    out["replay_seconds"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    res = [collect(**s) for s in spec]
    Path(sys.argv[2]).write_text(json.dumps(res, indent=1, default=str))
    for r in res:
        print(
            r["environment"],
            r["experiment_id"],
            f"{r['ok']}/{r['runs']} ok",
            "replay",
            r["replay_agreement"],
            "repro",
            r.get("reproduction", {}).get("identical_share"),
        )
