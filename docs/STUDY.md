# Running a paper experiment (xzr.study)

The study layer turns the runtime's experimental machinery (HPO operations, recursive reconfiguration, the laboratory, ARDS's arms)
into one workflow: **protocol → seeded runs of several arms → records → analysis → figures / tables / Methods / Results → package →
replay and reproduction.** It is available from the command line, the HTTP API (local runtime only) and the **Experiments** view.

## Modes — what a result may be used for

| mode | seeds | use |
|---|---|---|
| `functional` | reserved range (hpo-world: generator 7000–7999, engine 70000–79999; ARDS: its software-test replicates 3980–3989) | software verification. Every output carries "FUNCTIONAL CHECK — not evidence" |
| `exploratory` | fresh seeds (not in any development or published range) | look for effects; labelled exploratory |
| `confirmatory` | fresh seeds; the protocol is **registered** (SHA-256 frozen) before the first run | the runner refuses if the registered file differs; contrasts must be declared in advance; a change after the first run is recorded and the affected contrast is reported as exploratory |

Runs above 200,000 step-runs need an explicit approval record in the protocol (`approval.high_cost`). Nothing in this layer starts the
ARDS Phase 4 study; ARDS's own gates (owner go-ahead file, frozen protocol) are not bypassed (see "ARDS" below).

## A protocol (JSON, `xzr.study/1`)

Question, hypotheses, environment (`hpo-world`, `lab-population`, `ards`), **arms**, seeds, metrics, contrasts, criteria, stop conditions,
budget. Each arm declares what it is: `condition` / `settings` (the HPO field), `controller` (`static`, `recursive`, `random` with
`match_budget_of`), `meta` (revision of the controller's own rules), `authority` (sandbox paths it may change) and
`max_changes_per_epoch`, `initial_changes` and `interventions` (protocol-specified changes of observation channels, scale, time window,
penetration / boundary, variables at chosen epochs). Templates: `revision-study` (nine arms), `quick`, `lab-population`, `ards-comparison`.

**Fairness.** For every declared contrast the protocol computes, per arm, the information (instruments after the initial changes),
revision authority, controller, meta-revision, history re-entry, change budget, interventions and compute, and lists the dimensions in
which the two arms differ. A difference that the contrast does not declare (`varies`) is an error in confirmatory mode. The seeds are
shared, so each arm of a seed has the same initial world, warm-up and exogenous input.

## Records

One directory per experiment under `backend/experiments/studies/<id>/` (git-ignored; override with `XZR_STUDY_ROOT`):
`protocol.json`, `protocol.registered.json`, `amendments.jsonl`, `manifest.json` (git commit and dirty flag, interpreter, dependencies,
platform, seeds), `status.json`, `log.jsonl`, `runs/<arm>__<k>.json` (metrics, controller trace, every change with the reachability it
opened or closed, the reachability check, history re-entry, meta-revision trace, timings), then `analysis.json`, `report/`, `checksums.json`.
Runs execute in worker processes; a timeout, crash or exception is stored as a failed run and counted, never dropped. `stop` requests
end the study safely; `run` again resumes from the stored runs.

## Ziran-specific records

* **Reachability.** For each change: operations that became runnable / blocked, channels opened / closed, with reasons. The analysis
  compares each prediction with what the operation did in the next epoch: *opened* is not *success* (opened-but-not-used is counted),
  *closed* is checked against silence.
* **Meta-revision.** The controller's rule parameters are revised when a rule's change did not remove its blindness twice; rules at their
  bound are marked exhausted. Whether later changes were better is a contrast, not assumed.
* **History re-entry.** Reinsertions and how many had a downstream event; arms without re-entry are the controls.
* **Shape detection** (`environment.detect_shapes`): the transition record (engine deltas), the detector's output and the detector's
  limits are stored separately; no interpretation is produced.

## Commands

```bash
python -m xzr.study new revision-study --out p.json --seeds 6
python -m xzr.study validate p.json
python -m xzr.study create p.json            # prints the study directory
python -m xzr.study run <dir> --procs 3      # resumable
python -m xzr.study analyse <dir> && python -m xzr.study report <dir> && python -m xzr.study package <dir>
python -m xzr.study verify <dir>             # checksums
python -m xzr.study reproduce <dir> --out <new root>   # re-run the registered protocol and compare run for run
python -m xzr.study perf --out <dir>         # performance and load measurements of the workflow itself
```

## Third-party reproduction

Unpack the package, read `REPRODUCE.md` (versions, commit, protocol digest), `verify` the checksums, then `reproduce`. Agreement is exact
on the same machine and software versions; across platforms the address hierarchy can differ and agreement is not expected
(`docs/REPRODUCIBILITY.md`; the two baseline failures of this branch are of that kind). Only same-machine reproduction has been
exercised so far.

## ARDS

`environment.kind = "ards"` runs ARDS's own arms (EXISTING-blind, V1 / V2 PA, history and rule-revision ablations, fixed strategies,
the oracle reference) on ARDS's environments (`env1` the XB-TRO planar body on the Ziran runtime variant, `env2` the oscillator
network) through `vite-node`, unchanged, **in ARDS's software-test mode only** (replicates 3980–3989). Consequences: such studies are
functional checks, exploratory / confirmatory ARDS studies cannot be created, the 1,526 frozen Phase 3 files and the Phase 4 records are
neither read for results nor written (a test compares the ARDS git status before and after a run), and ARDS arms do **not** run on the HPO
world — no specification of such an environment exists. Set `XZR_ARDS_ROOT` if the ARDS repository is not `../pa-simulation-environment`.

## Outputs

Methods and Results as Markdown, tables as CSV (+ `tables.md`), figures as SVG with captions naming the experiment (PNG only when an SVG
converter — `rsvg-convert`, `inkscape` or ImageMagick — is installed; **no PDF is produced**). Results state measurements; no
theoretical proposition is generated.
