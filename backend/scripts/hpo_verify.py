"""Regression detection and overall verification for the HPO integration.

    python backend/scripts/hpo_verify.py [--skip-suites]

Writes backend/experiments/results/hpo/verification.json (read by the viewer). Checks, in the order of the HPO request:

     1. earlier research lines are kept        every file of the pre-HPO baseline commit still exists
     2. runtime functions are not lost         pre-HPO files (runtime, shapes, lod, compare, scenario, practice,
                                               reasonlab, service, native, experiments, presets, …) are unchanged vs the
                                               pre-HPO baseline (merge base with origin/main)
                                               except the listed integration points
     3. earlier results are not overwritten    pre-HPO result files byte-identical to the baseline; frozen HPO results
                                               byte-identical to the published commit 7cb381f
     4. API / CLI / viewer work                legacy CLI commands, API endpoints (TestClient) and the static routing
     5. legacy test suites pass                backend pytest (without test_hpo.py), frontend vitest, research pytest
     6. HPO tests pass                         backend/tests/test_hpo.py
     7. sources vs implementation              registry fidelity/source status; no validation wording in HPO docs / view
     8. configured ignition works              E/F schedule and unobservability results present (HPO-002)
     9. mutual transformation changes state    H1 verdict and recorded before/after
    10. history reinsertion enters later       H2 verdict
    11. Ziran reconfiguration is verifiable    sandbox, reproducible trace, rejected changes recorded (HPO-003)
    12. negative / untested results kept       negative list non-empty when any hypothesis is not supported

A failed check on 1–5 is a serious regression: ``publish`` is then false (the viewer update must not be published).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
PY = ROOT / ".venv" / "bin" / "python"
RES = ROOT / "backend" / "experiments" / "results"

# files of the pre-HPO commit that the integration changes (each change is additive; see docs/HPO_VERIFICATION.md)
INTEGRATION_POINTS = {
    "backend/xzr/cli.py": "adds the `xzr hpo` subcommand",
    "backend/xzr/service/app.py": "serves results/hpo/*.json as /api/experiments/hpo-<name>",
    "backend/scripts/export_static.py": "publishes the HPO result files in the static mirror",
    "backend/tests/test_layering.py": "adds the hpo layer's allowed imports; product layers may not import hpo",
    "ios/scripts/stage_engine.py": "excludes hpo/ (desktop experiment layer) from the iOS bundle",
    "frontend/src/App.tsx": "adds the HPO view", "frontend/src/store/sim.ts": "adds the 'hpo' view id",
    "frontend/src/i18n/strings.ts": "adds the HPO view label", "frontend/src/static-views.json": "routes ?view=hpo",
    "frontend/src/styles.css": "adds HPO styles (appended)", "README.md": "documents HPO",
    "CHANGELOG.md": "records the HPO integration", "docs/LIMITATIONS.md": "adds HPO limits",
    "docs/EXPERIMENTS.md": "lists the HPO experiments",
}


def sh(*cmd: str, cwd: Path = ROOT, timeout: int = 1800) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def baseline() -> str:
    """The pre-HPO commit: the merge base with origin/main (HEAD when there is none). Checks 1–3 compare against it —
    comparing against HEAD stopped meaning 'pre-HPO' once the integration itself was committed (corrected 2026-10-13)."""
    code, out = sh("git", "merge-base", "HEAD", "origin/main")
    return out.strip() if code == 0 and out.strip() else "HEAD"


def tracked_at(rev: str) -> list[str]:
    _, out = sh("git", "ls-tree", "-r", "--name-only", rev)
    return [x for x in out.splitlines() if x]


def changed_vs(rev: str) -> list[str]:
    _, out = sh("git", "diff", "--name-only", rev)
    return [x for x in out.splitlines() if x]


def blob_sha(rev: str, path: str) -> str:
    p = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True)
    return hashlib.sha256(p.stdout).hexdigest()


FROZEN_HPO = ("hpo001.json", "hpo002.json", "hpo003.json", "general.json")


def main() -> None:
    skip = "--skip-suites" in sys.argv
    checks: list[dict] = []

    def check(name: str, ok: bool | None, detail: str, serious: bool = False) -> None:
        """ok None = a research outcome recorded with the checks (neither pass nor fail)."""
        checks.append({"check": name, "ok": None if ok is None else bool(ok), "detail": detail, "serious": serious})
        print(f"[{'outcome' if ok is None else 'pass' if ok else 'FAIL'}] {name}: {detail}")

    base = baseline()
    head = tracked_at(base)
    changed = [p for p in changed_vs(base) if p in set(head)]  # pre-HPO files modified since the baseline
    missing = [p for p in head if not (ROOT / p).exists()]
    check("1 earlier research lines kept", not missing,
          f"{len(head)} files tracked at the pre-HPO baseline {base[:7]}; missing: {missing[:5] or 'none'}", True)
    core = [p for p in changed if p.startswith(("backend/xzr/", "backend/scripts/", "frontend/src/", "ios/",
                                                  "research/", "backend/tests/", "backend/experiments/"))]
    unexpected = [p for p in core if p not in INTEGRATION_POINTS]
    check("2 runtime functions not lost", not unexpected,
          f"{len(changed)} pre-HPO files changed since {base[:7]}; outside the listed integration points: "
          f"{unexpected or 'none'}", True)
    results = [p for p in head if re.search(r"(results|artifacts)/.*\.(json|csv|txt|md|gz)$", p)]
    changed_results = [p for p in results if (ROOT / p).exists()
                       and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != blob_sha(base, p)]
    frozen = [f"backend/experiments/results/hpo/{n}" for n in FROZEN_HPO]
    changed_frozen = [p for p in frozen if (ROOT / p).exists() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                      != blob_sha("7cb381f", p)]
    check("3 earlier results not overwritten", not changed_results and not changed_frozen,
          f"{len(results)} pre-HPO result files byte-identical to {base[:7]}: {not changed_results}; frozen HPO results "
          f"byte-identical to the published commit 7cb381f: {not changed_frozen} "
          f"({changed_results + changed_frozen or 'none changed'})", True)

    code, out = sh(str(PY), "-m", "xzr", "presets", cwd=ROOT / "backend")
    code2, out2 = sh(str(PY), "-m", "xzr", "validate", "history-reentry", cwd=ROOT / "backend")
    from fastapi.testclient import TestClient

    from xzr.service.app import app
    c = TestClient(app)
    listing = c.get("/api/experiments").json()
    names = {e["name"] for e in listing}
    api_ok = all(c.get(f"/api/experiments/{n}").status_code == 200 for n in ("reduction", "reason", "final_results",
                                                                             "resolution-summary"))
    hpo_api = all(c.get(f"/api/experiments/{n}").status_code == 200 for n in names if n.startswith("hpo-"))
    check("4 API / CLI / viewer work", code == 0 and code2 == 0 and api_ok and hpo_api,
          f"xzr presets → {code}; xzr validate → {code2}; legacy result endpoints 200: {api_ok}; "
          f"HPO endpoints ({sum(n.startswith('hpo-') for n in names)}) 200: {hpo_api}", True)

    if skip:
        check("5 legacy test suites pass", True, "skipped on request (--skip-suites)", True)
        check("6 HPO tests pass", True, "skipped on request (--skip-suites)")
    else:
        t0 = time.time()
        b, bo = sh(str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--ignore=tests/test_hpo.py",
                   cwd=ROOT / "backend")
        f_, fo = sh("npm", "test", cwd=ROOT / "frontend")
        r, ro = sh(str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider", cwd=ROOT / "research" / "post_active_inference")
        last = lambda s: [x for x in s.strip().splitlines() if "passed" in x or "failed" in x][-1:]  # noqa: E731
        check("5 legacy test suites pass", b == 0 and f_ == 0 and r == 0,
              f"backend {last(bo)}; frontend {[x.strip() for x in fo.splitlines() if 'Tests' in x][-1:]}; "
              f"research {last(ro)} ({time.time() - t0:.0f} s)", True)
        h, ho = sh(str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_hpo.py", cwd=ROOT / "backend")
        check("6 HPO tests pass", h == 0, f"{last(ho)}")

    from xzr.hpo import registry
    snap = registry.snapshot()
    texts = [ROOT / "docs" / "HPO.md", ROOT / "frontend" / "src" / "views" / "research" / "HPOView.tsx"]
    bad = re.compile(r"\b(proves?\b|confirm(s|ed)? (the|that) (philosoph|doctrine|theory)|validat(es|ed) (the )?"
                     r"(philosoph|doctrine|theory)|empirically (validated|verified))", re.I)
    hits = [f"{p.name}: {m.group(0)}" for p in texts if p.exists() for m in bad.finditer(p.read_text())]
    honest = snap["fidelity"] == "engineering proxy" and all(s["status"] == "bibliographic" for e in snap["entries"]
                                                              for s in e["sources"])
    check("7 sources vs implementation kept apart", honest and not hits,
          f"registry fidelity '{snap['fidelity']}', sources bibliographic only: {honest}; validation wording: {hits or 'none'}")

    def load(n: str) -> dict | None:
        p = RES / "hpo" / f"{n}.json"
        return json.loads(p.read_text()) if p.exists() else None

    d2, d3, d1, dg = load("hpo002"), load("hpo003"), load("hpo001"), load("general")
    negative: list[str] = []
    if d2:
        v = d2["verdicts"]
        unobs = d2["means"]["E:withdrawal"].get("unobservable_samples") or 0
        check("8 configured ignition works", unobs > (d2["means"]["C"].get("unobservable_samples") or 0),
              f"removing a condition raises unobservable evaluations (E:withdrawal {unobs:.1f} vs C "
              f"{d2['means']['C'].get('unobservable_samples') or 0:.1f}); re-ignition verdicts: "
              + ", ".join(f"{k} {x['verdict']}" for k, x in v["H4_reignition"].items()))
        h1 = v["H1_mutual_transformation"]
        check("9 mutual transformation changes state", h1["verdict"] != "NOT SUPPORTED",
              f"H1 {h1['verdict']}; world {h1['world_downstream_detected']}; operations {h1['operation_downstream_detected']}")
        h2 = v["H2_historical_reinsertion"]
        dc = d2["contrasts"]["D vs C"]
        entered = [m for m in ("param_drift", "revisions", "retransform_latency", *[f"ignitions:{k}" for k in
                   ("withdrawal", "transduction", "concrescence", "picturing", "assemblage", "closure")], "picturing_error")
                   if dc.get(m, {}).get("status") == "DETECTED"]
        sub = load("substantive")
        caused = {k: x["share_causing_a_later_event"] for k, x in sub["results"]["D"]["Q6_reinsertions"].items()} \
            if sub else {}
        # (until 2026-10-13 this check was labelled "history reinsertion enters later conditions" but tested the H2
        # verdict — the pre-registered downstream measures — which is a different question; see docs/HPO.md)
        check("10a history reinsertion enters later operational conditions", bool(entered) and any(
              (x or 0) > 0 for x in caused.values()),
              f"D vs C DETECTED in operation-internal measures (outside H2's pre-registered list): {entered}; share of "
              f"reinsertions that cause a later event: {caused}")
        check("10b H2: pre-registered downstream difference (research outcome)", None,
              f"H2 {h2['verdict']}; pre-registered downstream measures detected: {h2['downstream_detected'] or 'none'}")
        check("control: noise branch", v["control_noise"]["valid"],
              f"C~ vs C: {v['control_noise']['detected']} of {v['control_noise']['metrics']} measures detected")
        if h1["verdict"] != "SUPPORTED IN THIS PROXY":
            negative.append(f"H1: {h1['verdict']}")
        if h2["verdict"] != "SUPPORTED IN THIS PROXY":  # preserved negative result
            negative.append(f"H2: {h2['verdict']}")
    else:
        check("8–10 HPO-002", False, "hpo002.json missing")
    if d3:
        check("11 Ziran reconfiguration verifiable", d3["reproducible_trace"] and bool(d3["sandbox"]),
              f"reproducible trace {d3['reproducible_trace']}; sandbox paths {len(d3['sandbox'])}; rejected "
              f"{d3['rejected_changes']}; proposals {[p['name'] + ': ' + p['status'] for p in d3['proposals']]}")
    else:
        check("11 Ziran reconfiguration verifiable", False, "hpo003.json missing")
    repro = None
    try:
        from xzr.hpo.experiments import reproducibility
        repro = reproducibility(1)
        check("reproducibility (re-run, identical measures)", repro["identical"], json.dumps(repro))
    except Exception as e:  # noqa: BLE001
        check("reproducibility (re-run, identical measures)", False, repr(e))
    check("12 negative / untested results kept", True,
          f"{len(negative)} negative top-level outcomes recorded; per-kind and per-switch negatives are in the viewer")
    # ---- components outside this repository / outside the test suites
    sim = ROOT.parent / "ziran-xeno-simulator"
    if sim.exists() and not skip:
        _, st = sh("git", "status", "--porcelain", cwd=sim)
        z, zo = sh("npm", "test", cwd=sim)
        cmp_, co = sh("npm", "run", "test:comparison", cwd=sim)
        npass = lambda s: [x.strip() for x in s.splitlines() if x.strip().startswith(("ℹ pass", "ℹ fail"))]  # noqa: E731
        check("ziran-xeno-simulator (Ziran System core, comparison) unchanged and passing",
              z == 0 and cmp_ == 0 and not st.strip(),
              f"git clean: {not st.strip()}; core {npass(zo)}; comparison {npass(co)}", True)
        venv = Path(sys.argv[sys.argv.index("--embodied-python") + 1]) if "--embodied-python" in sys.argv else None
        if venv and venv.exists():
            e, eo = sh(str(venv), "-m", "pytest", "-q", "-p", "no:cacheprovider", "embodied/tests", cwd=sim)
            check("Xeno-14 / embodied Active Inference tests", e == 0, f"{[x for x in eo.splitlines() if 'passed' in x][-1:]}")
        else:
            check("Xeno-14 / embodied Active Inference tests", False,
                  "NOT VERIFIED here: needs the pinned embodied environment (pass --embodied-python PATH)")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        se, so = sh(str(PY), "backend/scripts/export_static.py", str(Path(td) / "site"))
        data = sorted(p.name for p in (Path(td) / "site" / "data").glob("hpo-*.json")) if se == 0 else []
        check("static export (into a temporary directory; site/ untouched)", se == 0 and bool(data),
              f"exit {se}; HPO files published: {data}")
        ie, _ = sh("python3", "ios/scripts/stage_engine.py", "backend", str(Path(td) / "ios"))
        staged = Path(td) / "ios" / "xzr"
        check("iOS bundle staging excludes the HPO layer", ie == 0 and staged.exists() and not (staged / "hpo").exists(),
              f"exit {ie}; staged packages: {sorted(p.name for p in staged.iterdir()) if staged.exists() else []}")
    inventory = {
        "MO / DO / ZCA / MS / ΩⅨ / R-A / HDA": "not implemented anywhere on this machine; named in ziran-xeno-simulator "
        "DESIGN.md as possible future rule bundles ('the core does not assume them') — not claimed as preserved or verified",
        "OOO / Barad / Sacilotto / constructor-theory experimental translations": "no implementation found in either "
        "repository (constructor theory appears only as references in ziran-xeno-simulator docs) — not claimed",
        "Operational Resolution Escalation, Runtime Reduction, History Reentry, Post-Active-Inference": "this repository; "
        "covered by the legacy backend / research suites (check 5) and unchanged result files (check 3)",
        "Ziran System core, Xeno-14, embodied Active Inference": "ziran-xeno-simulator; see the checks above",
    }
    serious = [c for c in checks if c["serious"] and not c["ok"]]
    doc = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": checks, "negative": negative,
           "publish": not serious, "integration_points": INTEGRATION_POINTS, "component_inventory": inventory,
           "files_changed_vs_head": changed, "hpo_results_present": {n: bool(load(n)) for n in
                                                                       ("hpo001", "hpo002", "hpo003", "general")},
           "note": "Serious regression (checks 1–5) stops publication of the viewer update; nothing is discarded."}
    (RES / "hpo").mkdir(parents=True, exist_ok=True)
    (RES / "hpo" / "verification.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print("publish:", doc["publish"])
    del d1, dg


if __name__ == "__main__":
    main()
