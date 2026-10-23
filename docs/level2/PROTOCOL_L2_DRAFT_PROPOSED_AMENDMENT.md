# Proposed amendment of the Level 2 (HPO) draft — known incomparabilities

**This is a proposal.** `PROTOCOL_L2_DRAFT.json` is unchanged, not frozen, not run, and not adopted. The proposed text is a separate file, `PROTOCOL_L2_DRAFT.proposed.json`, identical to the draft except for three additions
under `preregistration` (and the `status` line). Only the owner can adopt it, and only before freezing; adopting it after the first run would make it an amendment recorded as exploratory. The cost approval (`approval.high_cost`) stays closed: the proposed file still has exactly the one blocking issue the draft has.

## Why

The 19-row audit (`docs/certification/protocol_audit.json`) found the draft complete on 18 rows. The missing one is *known incomparabilities declared in the protocol*; the draft also says nothing about the numerical environment, although the HPO world's address hierarchy depends on the eigen-solver build.

## Added: `preregistration.known_incomparabilities` (from the stored records and the code, not from new runs)

1. **C2 compares policies that also create their own information.** The recursive arm reconfigures the instruments, so `fired_samples` are read through different instruments than the fixed arm's: the contrast measures the policy together with the information it creates for itself, not the policy at equal information (already declared as `varies: controller, revision_authority`).
2. **random-matched matches the number of changes, not their content or cost.** `measure_cost` can differ between arms; it is reported beside every contrast and is not a control.
3. **Censoring by stopping.** `stop.all_ceased` ends a run when every operation has ceased for an epoch; a stopped run accumulates `fired_samples` over fewer steps. `stopped_early` and `ceased_share` are reported with every contrast, and a sensitivity analysis excludes stopped runs.
4. **C3 is a declared underpowered secondary** (762 pairs needed, 200 planned): its interval is reported; it is not claimed as powered or as supporting anything.
5. **The scarcity level was chosen after seeing functional runs** (already in the provenance as *exploration*): the contrasts are conditional on pool 0.5 and horizon 600; the severe / none / abundant arms of the scarcity template remain exploratory.
6. **Numerical build.** The address hierarchy (method 1) depends on the eigen-solver build (`docs/RELIABILITY_REPAIR.md` §9; the two known test failures). Results are tied to the recorded build and are not claimed to reproduce bit-for-bit on another build.
7. **The sizing inputs are functional.** The stored input gives C1 −4.83 (interval −14.5 to 0.0, 6 seeds). An earlier status record quotes −26 for "the first scarcity study"; the stored files available now do not reproduce that figure and the two are not reconciled here. Both are functional results, not evidence.

## Added: `preregistration.numerical_environment` and one sensitivity analysis

`numerical_environment` states the hierarchy method (1, the default; the opt-in method 2 is not used and never mixed in) and what is recorded at registration (the study manifest now carries `numeric_build` and `hierarchy_method`). `analysis_plan.sensitivity` gains *excluding runs that stopped early*.

## What the amendment does not do

It does not change a hypothesis, an arm, a seed, a metric, a threshold or a power calculation; it does not grant any approval; it does not freeze anything. If the owner wants any of those changed, that is a different, visible edit made before freezing.
