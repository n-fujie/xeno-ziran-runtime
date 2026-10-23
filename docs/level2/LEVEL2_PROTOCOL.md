# Level 2 protocol (draft) — revision of the observation configuration and of its rules

`PROTOCOL_L2_DRAFT.json` is a **draft**. It is not frozen, has not been run, and nothing about its outcome is known or assumed. It is a *new* protocol,
independent of the functional studies (reserved seeds 7000–7999, ARDS test replicates 3980–3989), which are not evidence.

**Central question.** Under moderately scarce measurement resources, does result-driven revision of the observation configuration, and revision of the controller's
own rules, change what the operations do afterwards (fired samples), compared with no revision, with matched random revision and with revision without rule
revision? No direction is assumed; equivalence inside the margin is an equally valid result.

| item | content |
|---|---|
| arms | fixed, recursive, recursive-meta, random-matched (same number of changes per epoch as recursive); same world, seeds, warm-up, horizon (600 steps = 10 epochs), scarcity (0.5 per step) |
| independent seeds | 200 per arm, generator 20000–20199, engine 200000–200199 (disjoint from every development, published, functional and exploratory range) |
| primary metric | fired samples; secondary: unobservable samples, controller changes / rejections, meta-revisions, exhausted rules, measurement cost, early stops, ceased share |
| contrasts | C1 meta vs recursive (primary, ±5% of the control mean); C2 recursive vs fixed (primary, ±20%); C3 recursive vs random-matched (secondary, **underpowered**: ~762 pairs needed, 200 planned — reported with its interval, never as a test) |
| falsification | the 95% interval of C1 (resp. C2) lies inside its equivalence margin; any contrast whose interval includes zero and the margin is "unresolved" |
| analysis | paired by seed; bootstrap 95% interval; dz; sign-flip permutation p; Holm over every declared contrast × metric; sensitivity (leave-one-out, sign agreement, Wilcoxon, outliers); small-sample rules of `analysis.paired_safe` |
| power assumptions | upper 95% bound of each SD from a 6-seed functional study (chi-square, df 5), minimal effects 5% / 20% of the control mean, α 0.05, power 0.8 (`xzr/study/power.py`); source file `exploration_inputs/scarcity_functional_summary.json` |
| stopping | per-run timeout 300 s, wall-clock budget 6 h, at most 20 failed runs; no optional stopping — a stopped study is resumed, never re-planned from partial results |
| compute budget | 800 runs, ~512,000 step-runs: **high-cost; `approval.high_cost` is not granted** — the protocol cannot be frozen or created until the researcher approves |
| data storage | every run record, log, manifest and the registered protocol under the experiment directory; failed and timed-out runs kept and counted |
| exploration / confirmation | exploratory seeds listed; confirmatory seeds disjoint (checked); **provenance** of every non-default condition (scarcity 0.5, stop rule, horizon) is recorded as *derived from exploration* — chosen after looking at functional runs |
| reproduction | registered digest, seeds, git commit and environment in the manifest; `reproduce` re-runs the registered protocol and compares every run record |

What this protocol cannot decide: whether the effect, if any, is a property of P/A rather than of any adaptive controller (see `docs/NONREDUNDANCY.md`: the comparison with
ARDS's arms and with other adaptive methods is a separate, comparable-axis question); anything outside the HPO world and the defined scarcity; any theoretical claim.
