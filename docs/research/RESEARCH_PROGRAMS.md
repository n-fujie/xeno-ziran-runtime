# Research programmes — protocols registered as Study Engine templates

Status: **protocols, not results.** The four templates below are in the Study Engine (`rp1-ziran-self-revision`, `rp2-total-observation`, `rp3-planetary-placement`, `rp4-sss-self-revision`). They are functional by default (reserved seeds; the UI
switches the seeds when the mode is changed to exploratory), none is pre-registered, none is confirmatory, none has produced evidence. Their pre-execution audit (`docs/research/programme_audit.json`, produced by `backend/scripts/programme_audit.py`) found: all four
validate, pass the fairness check (every difference between compared arms is declared), and run to completion on one reserved seed per arm (48/48 smoke runs); every metric a programme asks for is measured, except one that is *derived* (below).
Nothing here assumes a P/A method is better than any alternative. Equivalence, worsening and unresolved results are kept as results.

Common rules: same world, seeds, start layout, budget, information (what the observers record) and verifier in every arm; contrasts that differ in several components list all of them under `varies`, so none is a single-mechanism effect;
an arm never reads the verifier; rules `v2` and `measures: extended` for the observation programmes (`v1` results are never compared with `v2`); a metric whose definition changes inside a run is compared only inside its version segment.
A confirmatory study of any programme requires a protocol frozen **before** its first run, fresh independent seeds, a power plan from exploration, a computational budget, the owner's recorded approvals (`docs/research/EVIDENCE_MANAGEMENT.md`), and — where the address hierarchy matters — the solver build and the hierarchy method written into the protocol.

## Metric definitions added for the programmes (`measures: extended`, rules v2; each from data the run already holds)

| metric | definition |
|---|---|
| `coverage_final` | share of the world's regions inside the footprint of a sensor whose reports reached the hub, in the last generation |
| `identification_count_error` | mean over checkpoints of \|identified objects − the world's objects\| / max(1, the world's objects) (verifier side) |
| `change_failure_rate` | (operations denied by the budget + rejected) / (operations executed + denied + rejected) |
| `ops_cost_spent` | operation budget spent (observation cost is `obs_cost`) |
| `cycles_completed` | how many times a supported hypothesis returned the loop to the first question |
| `observation_loss_share` | (records lost at the hub + reports lost in transit) / (observations + reports lost in transit) |
| `expiry_rate` | sensors whose health reached zero / sensors at the end |
| `reachable_regions_final` | regions inside footprints that can reach the hub, last generation |
| `recall_post_change` | mean recall at checkpoints from the first generation in which a source moved (undefined when no source moves) |
| `metric_definition_breaks` | number of cuts in metric series because a definition changed (no number is formed across a cut) |

## RP1 — Ziran operational self-revision (HPO world; confirmatory path: `docs/level2/PROTOCOL_L2_DRAFT.json`)

* **Question.** How does revising observation, variable, boundary, scale, time window and evaluation conditions change what later operations can reach, identify and complete?
* **Arms** (template `rp1-ziran-self-revision`, 9 arms): fixed, recursive, recursive-meta, random-matched (same number of random valid changes per epoch), no-history, observation-narrowed, boundary-veiled, variable-added, scale-window-shifted. The comparator "an existing method with the same change authority" **does not exist in the HPO world**; it exists only in the ARDS–HPO shared environment (`shared-comparison`, existing-blind vs hpo-rules, test replicates only).
* **Central hypothesis (two-sided).** Result-driven revision (and revision of the revision rules; history re-entry on / off) changes later fired samples relative to the stated controls. No direction is assumed.
* **Falsification.** The 95 % interval of a declared contrast lies inside its equivalence margin; or the contrast is UNRESOLVED (reported as such, never as support). A revision having occurred is never evidence of improvement.
* **Metrics.** Primary `fired_samples`. Requested → stored: executable operations and reachable states → `reachable_share`; completion → `stopped_early`, `ceased_share`; identifiability → `fired_samples`, `unobservable_samples`; resource use → `measure_cost`; later conditions → `controller_changes`, `reinsertions`, `meta_revisions`; **change failure rate → DERIVED** from `controller_rejected / (controller_changes + controller_rejected)` (not analysed as a metric in itself; making it one would change the record of HPO runs and is a new rules version).
* **Power / effect.** Sized only by the Level 2 draft from a 6-seed functional study: C1 25 pairs, C2 174, **C3 762 needed against 200 planned: a declared underpowered secondary, reported with its interval only.** The other contrasts of this template have no power plan.
* **Cost.** 15,120 step-runs at 6 seeds (functional); the Level 2 draft is 512,000 step-runs (> the 200,000 gate: approval required).
* **Not testable here.** Whether self-revision is "a research act" in any sense beyond the model's operations.

## RP2 — Total Observation (synthetic regional world)

* **Question.** When several local observing systems exist, integrate, interfere, lose records and revise their conditions, how do identification, observational loss, disturbance, later reachability and material consequences change?
* **Arms** (template `rp2-total-observation`, 11 arms): single (`obs-single`) vs distributed (`adaptive-base`) observation; fixed integration `separate` (`fixed-base`) / `mean` / `finest` vs adaptive integration (`int-adaptive`, authority to change the integration rule only); interference none / default / strong (fixed policy, so the factor and not the agent differs); record loss none / at generations 3 and 5 (`loss-none`, `loss-events`); self-revision of observing conditions off / on (`adaptive-base`, `selfrev-on`: classification, boundary, derived variable). 8 contrasts.
* **Central hypothesis (two-sided).** Each factor changes the verifier's recall of the world's objects, the loss of observational information, and the later reachable set; no direction is assumed.
* **Falsification.** Interval inside the equivalence margin, or unresolved.
* **Metrics.** Primary `recall_final`. Identifiability → `recall_final`, `precision_mean`, `identification_count_error`; information loss → `observation_loss_share`, `records_lost`, `ident_lost_object_still_present` (the world's object was still there: unobserved, not absent); disturbance → `interference`, `marks_total`; later reachability → `reachable_regions_final`, `reach_expanded`, `reach_contracted`; changed observing conditions → `ops_executed`, `eval_changes`, `metric_definition_breaks`; state after record loss → `marks_total` and the ledger's residual-consequence layer.
* **Power / effect.** None for this template. The existing confirmatory draft (`total-observation-confirmatory`: adaptive vs fixed, full vs adaptive; 189 fresh seeds from a 12-seed exploration) covers a different pair of contrasts; an RP2 confirmatory draft needs an exploratory study of this template first.
* **Cost.** 27,192 step-runs at 6 seeds.
* **Not testable here.** Complete information about "reality as a whole"; the model's state is not reality as a whole, and the verifier knows only the model.

## RP3 — Planetary-scale observation (synthetic world that meets the declared structural conditions)

* **Question.** How far can spatially distributed observers with different speeds, communication conditions and resource layouts identify changes of a wide synthetic world?
* **Arms** (template `rp3-planetary-placement`, 12 arms): placement fixed / random (seeded) / adaptive / self-revising, at latency 1 and 4, low interference; and strong interference at latency 1. The sources move at generations 3–7 (otherwise delay is invisible to recall). 14 contrasts (placement vs fixed at both latencies, delay, interference).
* **Central hypothesis (two-sided).** Placement policy, delay and interference change the identification of a changing world; no direction is assumed.
* **Falsification.** Interval inside the margin, or unresolved.
* **Metrics.** Primary `recall_final`. Observed extent → `coverage_final`, `reachable_regions_final`; identification error → `identification_count_error`, `precision_mean`, `spurious_rate`; delay → `info_age_mean`; expiry → `expiry_rate`; resource cost → `obs_cost`, `ops_cost_spent`; tracking → `recall_post_change`.
* **Power / effect.** None. **Cost.** 23,904 step-runs at 6 seeds.
* **Limits that stay.** `earth_claim` is false: no conclusion about the Earth follows. The scaling law (`planetary.scaling_law`) is an empirical fit of this model and asserts nothing.

## RP4 — Scale, Size and Speed (SSS)

* **Question.** How do Scale, Size and Speed, alone and together, change identification, tracking, comparability, resource use and later research, and what does revising the success measure's own definition do to what can be compared?
* **Arms** (template `rp4-sss-self-revision`, 16 arms): the complete 2³ design with the evaluation-rule revision off and on (8 contrasts, on vs off per cell). The effects of the three axes and their 2- and 3-way interactions are computed on the 8 `off` arms (tagged `sss`).
* **Central hypothesis (two-sided).** Each axis and their interactions change identification and tracking; revising the evaluation rule changes what can be compared.
* **Falsification.** Interval inside the margin, or unresolved.
* **Metrics.** Primary `recall_final`. Tracking → `recall_post_change`; comparability → `metric_definition_breaks` (and `comparable()` refusing to compare across a version break); transitions → `question_changes`, `reach_*`; resources → `obs_cost`, `ops_cost_spent`; later research → `cycles_completed`, `ops_executed`.
* **Power / effect.** None. **Cost.** 39,552 step-runs at 6 seeds.
* **Limit.** Number of sensors, pool and generations are held fixed, so coverage and contention change with Size by design.

## Order of work from here (nothing below is started)

1. Exploratory studies of RP2–RP4 on fresh seeds (small, owner-approved), recording every design change made after seeing them. 2. Sizing of each confirmatory draft from those spreads (upper bounds). 3. Registration (freeze) of a draft only by the owner, with the approvals recorded. 4. Run, analyse, report, package, replay, re-execute. 5. Independent re-execution on another machine or by another person for any cross-platform claim.
