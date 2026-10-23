# Prior methods and what a non-redundancy claim needs

Non-redundancy (axis D) is **not established** and nothing in the programmes assumes it. This document says which prior methods can be compared *today*, which cannot, and what would have to exist before a comparison could be called fair.
The table is produced by `backend/scripts/comparators_audit.py` (output: `docs/research/comparators_audit.json`): it searches the repositories on this machine for code identifiers of each method and for connections into the study layers. A name without an implementation, or an implementation that is not an arm, is **not compared**.
References are given for orientation and must be verified before use in a paper.

| prior method | reference to verify | implementation found | connected as an arm | compared |
|---|---|---|---|---|
| Active Inference | Friston et al. 2015 (expected free energy: pragmatic + epistemic) | yes, elsewhere: `research/post_active_inference/pai/aif_vendor.py` and `ziran-xeno-simulator/embodied/active_inference/` (discrete A/B/C/D/E model, EFE policy selection), written for the Post-Active-Inference benchmark and a MuJoCo body | **no**: nothing in `xzr/study`, `xzr/totalobs` or `xzr/hpo` imports it | **no** |
| Active Learning | Settles 2009 | no | — | **no** |
| Active Sensing / information-gain sensor selection | Chaloner & Verdinelli 1995 (Bayesian experimental design) | no (information-gain terms exist only inside the Active Inference code) | — | **no** |
| Bayesian Optimization | Shahriari et al. 2016 | no | — | **no** |
| Adaptive control (self-tuning, model-reference) | Åström & Wittenmark | no | — | **no** |
| The project's own prior adaptive observation procedure (ARDS *existing-blind*) | broader family: King et al. 2009 (Adam), Williams et al. 2015 (Eve), Kitano 2021 | yes: `pa-simulation-environment/src/ards/loop2/existingBlind.ts` | **yes**, in the ARDS–HPO shared environment (test replicates 3980–3989 only) | policy-level only (see below) |

Facts that limit even the one comparator that exists:

* ARDS *EXISTING-E* (`loop/existing.ts`) is **oracle-informed**: it reads the simulator's truth and is not information-matched; it cannot support a non-redundancy claim. The observer-side re-implementation (*existing-blind*) is what the shared environment compares.
* ARDS's rule family (R1–R4) and the HPO rule table are structurally close (both map blindness reasons to instrument changes), so that comparison is between *policies* in one environment, not between whole systems.
* The HPO `random-matched` arm is a control (same number of random valid changes), not a prior method.
* The shared environment accepts test replicates only: it cannot carry a confirmatory comparison.

## Conditions for calling a comparison fair (all required)

1. **Formal definition and implementation.** The method's published definition is stated, the implementation is reviewed against it, and it is not a weak control given the method's name.
2. **Same information.** It reads only what the P/A arm reads (the hub's records; never the verifier, never the truth).
3. **Same intervention authority and the same change authority.** The same closed list of operations, the same permissions (e.g. `perturb` only if both may).
4. **Same computational and resource budget.** The same pool, operation budget, generations and `max_ops` per generation.
5. **Same environment, seeds, start layout, stop rules and verifier.**
6. **A declared contrast on a comparable indicator**, an equivalence margin, a power plan and a frozen protocol (docs/research/EVIDENCE_MANAGEMENT.md).
7. **Results kept as found.** Equivalent, worse and unresolved outcomes are reported with the same prominence as better ones.

## Conceptual difference is not experimental non-redundancy

That the total-observation loop revises the observing configuration, the question, the hypothesis and the evaluation rule, while (for example) a standard Active Inference agent selects policies under a fixed generative model, is a **conceptual** statement about how the methods are specified. It is not evidence that the revision loop does anything the other methods do not: extensions of Active Inference with structure learning, and automated-science systems that revise hypotheses and experiments, exist in the literature (`docs/NONREDUNDANCY.md`).
Only an experiment satisfying the seven conditions above can bear on the second question, and none has been run. To add a comparator, the work is: implement it as an arm over the same world and record interface, write its definition and its parity conditions into the protocol, show by test that it never reads the verifier, and run the programme's contrast. That is new development and is not started.
