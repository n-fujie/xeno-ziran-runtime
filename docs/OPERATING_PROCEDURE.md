# Operating procedure — starting the simulator and running a study

Every command below was executed during the final certification on macOS, Python 3.12.13, scipy 1.18.1, numpy 2.5.3, node 24. Paths are written as placeholders:

* `<REPO>` — the checkout of `xeno-ziran-runtime-zrs` (branch `feat/zrs-integration`)
* `<PYTHON>` — an interpreter that has the backend dependencies (`backend/pyproject.toml`); the system python on the certification machine has none
* `<NODE_BIN>` — the directory of the node binary (needed for the UI build and for the ARDS bridge)

The study API and the UI are **local only**: `XZR_PUBLIC=1` makes every study route answer 403, and a request made from another site's page is refused.

```bash
export PATH=<NODE_BIN>:$PATH
cd <REPO>
```

## 1. Environment and start

```bash
(cd frontend && npx vite build)                                                    # writes frontend/dist (git-ignored)
<PYTHON> -m uvicorn xzr.service.app:app --app-dir backend --host 127.0.0.1 --port 3021
```

Open `http://localhost:3021/?view=study` (Experiments). Tabs: New protocol · Studies · Run · Observation & Ziran · Total observation · Research lines · Statistics · Paper outputs.
The ARDS environments additionally need the sibling `pa-simulation-environment` checkout (its own `node_modules`); the bridge runs ARDS in test mode only, on replicates 3980–3989.

## 2. Running a study from the UI

1. **New protocol** — choose a template: `revision-study` (HPO / Ziran), `total-observation`, `planetary-observation`, `sss-axes`, `autonomous-loop`, `ards-comparison`, `shared-comparison`.
   Mode `functional` uses the reserved seeds (generator 7000–7999, engine 70000–79999; ARDS: 3980–3989). For the total-observation line set the observing layout, the planetary model and the Scale / Size / Speed fields,
   and the **rules version (`v2` for every new study; `v1` only to replay earlier studies)**. Uncheck arms to leave them out; contrasts naming a left-out arm are dropped.
2. **Validate** shows the cost gate, the fairness table (every difference between compared arms and whether it is declared) and the arm profiles. **Create study** registers the protocol: its SHA-256 digest is its identity
   (*Studies → Identity*: registered digest IDENTICAL).
3. **Run → Start**. *Stop* asks a running study to stop gracefully; *Resume* continues from the stored runs. Failed and timed-out runs are kept and counted.
4. **Statistics → Run analysis** (descriptives, paired contrasts with intervals, multiplicity, criteria verdict, non-redundancy assessment — which is *not evaluated* for functional studies).
   **Observation & Ziran** and **Total observation** show the stored records (per-generation items, reachability, hypothesis tests against the verifier, silence audit, rule conflicts, metric definitions, the eight-layer ledger).
5. **Paper outputs → Build paper outputs** (Methods, Results, CSV tables, SVG figures) → **Package for reproduction** → **Verify** (checksums) → **Replay** (re-executes one stored run from the protocol alone and compares it with the stored record) → **Reproduce** (re-executes the registered protocol into a new study and compares every run).

## 3. The same from the command line

```bash
export PYTHONPATH=backend
<PYTHON> -m xzr.study templates
<PYTHON> -m xzr.study new --out p.json --seeds 6 autonomous-loop      # a protocol from a template
<PYTHON> -m xzr.study validate p.json                                 # schema, seed discipline, fairness, cost gate; prints the digest and the number of runs
<PYTHON> -m xzr.study create --root backend/experiments/studies p.json   # registers the digest; prints the study directory
<PYTHON> -m xzr.study run --procs 2 <study-dir>                       # run; the same command resumes a stopped study (stored runs are kept)
<PYTHON> -m xzr.study status <study-dir>                              # state, n_ok, n_failed, remaining, elapsed
<PYTHON> -m xzr.study stop <study-dir>                                # graceful stop of a running study
<PYTHON> -m xzr.study analyse <study-dir>                             # statistics (analysis.json)
<PYTHON> -m xzr.study report <study-dir>                              # Methods, Results, tables, figures under <study-dir>/report/
<PYTHON> -m xzr.study package <study-dir>                             # REPRODUCE.md, checksums.json and a .zip next to the directory
<PYTHON> -m xzr.study verify <study-dir>                              # every file against checksums.json
<PYTHON> -m xzr.study reproduce --out <new-root> --procs 2 <study-dir>   # whole-study re-execution; prints identical_share
<PYTHON> -m xzr.study amend --path stop.timeout_per_run_s --value 300 --reason "..." <study-dir>   # a change after registration
```

An amendment is recorded in `amendments.jsonl` with its reason and phase; one made after runs started is labelled `exploratory` and the affected contrast is no longer reported as confirmatory. The registered protocol is never overwritten.
Replaying **every** stored run and collecting the evidence of finished studies:

```bash
cd backend && PYTHONPATH=. <PYTHON> scripts/certify_studies.py <spec.json> ../docs/certification/certification_record.json
PYTHONPATH=. <PYTHON> scripts/protocol_audit.py ../docs/certification/protocol_audit.json     # the sixteen-item audit of the confirmatory drafts
```
(`spec.json` is a list of `{"label", "sid", "repro"}` entries naming study ids under `backend/experiments/studies/` and their re-execution studies.)

## 4. Where the data are

`backend/experiments/studies/<study-id>/` (git-ignored): `protocol.json`, `protocol.registered.json`, `manifest.json` (git commit and dirty flag, interpreter, dependencies, platform), `log.jsonl`, `amendments.jsonl`,
`runs/` (one JSON record per arm × seed, including failed and timed-out runs), `analysis.json`, `report/` (Methods, Results, tables, figures), `checksums.json`, `REPRODUCE.md`, `status.json`.
A re-execution is a separate study directory whose `reproduction.json` states what it reproduces and the identical share.

## 5. The test suites (the backend takes about 14 minutes: run it in the background)

```bash
(cd backend && <PYTHON> -m pytest -q --no-header -p no:cacheprovider)     # expect exactly two known failures: test_compat[desktop-scipy], test_published_records_replay
(cd frontend && npx tsc -b && npx eslint . && npx vitest run)
(cd <ZIRAN_XENO_SIMULATOR> && node --test "test/*.test.ts")
(cd <PA_SIMULATION_ENVIRONMENT> && python3 -I scripts/ardsFreeze.py verify artifacts/ards/phase3/FREEZE_MANIFEST_phase3.json)
```
Never deselect a test to raise the pass rate. The two known failures are an owner decision (`RELIABILITY_REPAIR.md`).

## 6. Confirmatory studies: the approval gate (not released by this procedure)

`total-observation-confirmatory` and `docs/level2/PROTOCOL_L2_DRAFT.json` are drafts: not frozen, not run. A protocol that declares `approval.confirmatory_run` cannot be created until the owner records **who** and **when**;
a protocol above the cost gate (200,000 step-runs) cannot be created without `approval.high_cost` (who, when). Both drafts are blocked by exactly these approvals and by nothing else (`docs/certification/protocol_audit.json`).
The ARDS bridge cannot run a confirmatory study at all (test replicates only), and ARDS Phase 4 stays stopped. Nothing in this procedure starts a confirmatory run.
