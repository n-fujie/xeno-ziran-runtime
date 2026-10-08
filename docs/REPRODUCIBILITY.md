# Reproducibility

## Install

```bash
git clone <repository-url> xeno-ziran-runtime
cd xeno-ziran-runtime
python3 -m venv .venv
.venv/bin/pip install -e "backend[dev]"
```

Python ≥ 3.11. No network access, account or credential is needed to run experiments. (`make setup` also installs
the frontend for the interactive simulator; the experiments do not need it.)

## Reproduce the representative experiments

Each command writes a new directory `xzr-results/<preset>/<run-id>/` (never overwriting) containing the effective
configuration, the result, a summary and the raw per-seed outputs.

```bash
.venv/bin/xzr run history-reentry
.venv/bin/xzr run resolution-escalation
.venv/bin/xzr run boundary-scale-window
.venv/bin/xzr run ablation
```

Check that a rerun reproduces a run exactly (every status cell identical):

```bash
.venv/bin/xzr run history-reentry --out rerun
.venv/bin/xzr compare xzr-results/history-reentry/<run-id> rerun/history-reentry/<run-id>
```

Change one thing and see what the change does:

```bash
.venv/bin/xzr run history-reentry --seed0 500          # another seed set
.venv/bin/xzr validate history-reentry > my.json        # then edit my.json (e.g. "region": "3"), and:
.venv/bin/xzr run my.json
.venv/bin/xzr compare xzr-results/history-reentry/<run-id> xzr-results/<id-in-my.json>/<run-id>
```

`xzr validate` prints the *effective* configuration (every condition fully expanded); a file in that form can be
run directly after editing. Unknown or misspelt settings are refused, never ignored.

## Reproduce the published long studies

```bash
.venv/bin/xzr study reduction        # backend/experiments/results/reduction.json
.venv/bin/xzr study reason           # backend/experiments/results/reason.json
.venv/bin/xzr study matrix           # backend/experiments/results/resolution/matrix.json (≈ 10 h on 7 workers)
.venv/bin/xzr study disconnection    # … and topology_triggers, adaptivity, clusters, compression
cd backend && ../.venv/bin/python -m xzr.experiments.escalation.summary   # results/resolution/summary.json
```

The committed result files are what the documentation and the research-results site report. The long studies
are resumable (conditions already in the output file are skipped), so delete or move an output file to rerun it.

## What is and is not reproducible

* **Determinism.** Every random choice comes from a seeded generator: the world from the generator seed, each run
  from its engine seed (numpy `Generator`, PCG64). No global or time-based randomness is used; worker processes
  run self-contained seed jobs, so the number of processes does not change results. A rerun with the same
  configuration, seeds, code and numpy version gives identical state fingerprints (tested:
  `tests/test_cli.py`, `tests/test_compat.py`).
* **Bit-level reproducibility** has been verified on the same machine and software versions, and between the
  desktop (macOS, scipy) and the iOS stand-in path against a golden fixture (`backend/tests/fixtures/`).
  On other platforms or numpy versions, floating-point summation order or generator changes can alter
  trajectories; the runtime is chaotic, so any such change makes runs diverge. Expect *statistical*
  reproducibility of statuses there, not bit-identical runs — this has not been verified across platforms.
* **Statistics** hold for the stated configuration and seed set. A status can change with more seeds (more power)
  or other seeds near a threshold; `xzr compare` shows exactly which cells change.
* **Provenance.** Every result records the package version, code hash, git commit and whether the tree had
  uncommitted changes (when run from a source checkout), Python and numpy versions, the seed list and the
  effective configuration.
