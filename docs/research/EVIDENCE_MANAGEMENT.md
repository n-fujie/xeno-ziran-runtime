# Evidence, reproducibility and statistics management for paper experiments

This fixes how results are tied to evidence from now on. It describes what the Study Engine records and what the checks below verify; it adds no research claim.

## 1. What every experiment carries (all written by the Study Engine into the study directory)

| item | where |
|---|---|
| Experiment ID, Protocol digest (SHA-256 of the canonical protocol; the identity) | study directory name, `manifest.json` |
| Registered protocol and every later change | `protocol.registered.json`, `amendments.jsonl` (a change after the first run is labelled *exploratory* and the affected contrast is no longer reported as confirmatory) |
| Git commit, branch, dirty flag **and the names of the dirty files** (up to 50) | `manifest.json → environment` |
| Interpreter, platform, dependencies, **numerical build (BLAS/LAPACK) and hierarchy method** (new studies) | `manifest.json → environment` |
| Seeds (generator, engine) | the protocol; each run record |
| Arms, metrics (with definitions and versions), contrasts, criteria | the protocol; `analysis.json` |
| Raw data: one record per arm × seed, including failed and timed-out runs | `runs/` |
| Execution log | `log.jsonl` |
| Statistics: descriptives, paired contrasts with bootstrap intervals, effect sizes, Holm and Benjamini–Hochberg, sensitivity, outliers, censoring, non-redundancy assessment (default *not evaluated*) | `analysis.json` |
| Methods, Results, tables, figures | `report/` |
| Checksums of every file | `checksums.json` (verified by `verify`) |
| Re-run instructions | `REPRODUCE.md`; whole-study re-execution writes `reproduction.json` in a new study |

## 2. Rules

1. **Exploratory and confirmatory are separate.** Functional runs use the reserved seeds (7000–7999 / 70000–79999; ARDS 3980–3989) and are never evidence. An exploratory study is labelled as such. A confirmatory study uses fresh seeds, disjoint from every exploratory and functional seed, and its protocol is frozen **before** its first run. A design change made after seeing exploratory data is written into `condition_provenance` (`derived_from: exploration`); it is never presented as pre-registered.
2. **A confirmatory study is created from a clean working tree**, at a recorded commit. `scripts/evidence_check.py` grades a finished study: `COMPLETE` (every item, clean tree), `COMPLETE-WITH-LIMITS` (every item, but the tree was dirty or the numerical build is not recorded — the limit is listed) or `INCOMPLETE`. Only `COMPLETE` is eligible as a confirmatory record.
3. **Numerical environment.** A protocol whose results depend on the address hierarchy (the HPO and laboratory worlds) states the hierarchy method (the default method 1, or the opt-in method 2, never mixed) and the solver build it was made with. The manifest records `numeric_build` and `hierarchy_method`. The synthetic observation world does not use the hierarchy.
4. **Rules versions are never mixed.** `rules_version` v1 and v2 results are not compared; the metric registry of v2 carries the freshness rule in its basis. A metric whose definition changes inside a run is compared only inside its version segment.
5. **Negative, equivalent and unresolved results are kept** and reported as prominently as any other; a revision having occurred, a method having been implemented, or a number having improved after a repair is never evidence of superiority.
6. **Undefined statistics stay undefined.** Fewer than two complete pairs gives the mean only; sd, effect size, interval, p, Holm and BH are `null` and the status is INSUFFICIENT DATA — never 0, 1 or infinity.
7. **Reproducibility is stated by tier** and only for what was done: (1) same machine, same software; (2) same machine, changed dependencies; (3) another machine; (4) an independent third party. At present tiers 1 and 2 are done for the certified studies; tiers 3 and 4 are not.
8. **Stored results are never rewritten to make anything agree.** A stored analysis made by older code stays as it is (one such file is documented in `docs/ZRS_INTEGRATION_STATUS.md`); the current code's recomputation is reported beside it.
9. **Gates.** No confirmatory run, ARDS Phase 4 run, high-cost computation, freeze of a pre-registration, push, deployment or publication without the owner's explicit, recorded approval (`approval.high_cost`, `approval.confirmatory_run`: who, when).

## 3. The checks (all read-only)

```bash
cd backend
PYTHONPATH=. <PYTHON> scripts/evidence_check.py experiments/studies <ids.json> ../docs/certification/evidence_check.json   # the policy above, per study
PYTHONPATH=. <PYTHON> scripts/audit_statistics.py <ids.json> ../docs/certification/statistics_audit.json                  # independent recomputation of the statistics
PYTHONPATH=. <PYTHON> scripts/certify_studies.py <spec.json> <out.json>                                                    # replay of every run, with the replay environment
PYTHONPATH=. <PYTHON> scripts/protocol_audit.py ../docs/certification/protocol_audit.json                                  # the audit rows of a confirmatory draft
PYTHONPATH=. <PYTHON> scripts/programme_audit.py ../docs/research/programme_audit.json                                     # pre-execution audit of the four programmes
PYTHONPATH=. <PYTHON> scripts/comparators_audit.py ../docs/research/comparators_audit.json                                 # which prior methods exist as arms
```

## 4. Traceability limit of the certified studies (stated, not hidden)

The seven certified studies were created from working trees with uncommitted changes. Their manifests list the dirty files (names only, not content): for six of them only frontend UI files and `node_modules`; for the seventh (`shared-comparison`, created last) also
`backend/xzr/study/protocol.py` (an approval gate that applies only to protocols that declare it), `backend/xzr/study/totalobs_templates.py` (a template not used by that study), tests and documents. No backend code that those runs execute differed from the committed code in a way a run uses; the **clean committed code reproduces every stored run** (tiers 1 and 2), which is the stronger statement.
Their numerical build and hierarchy method were not recorded (the record was added afterwards): `evidence_check.py` grades all seven `COMPLETE-WITH-LIMITS` for these two reasons (`docs/certification/evidence_check.json`). New studies record both.
