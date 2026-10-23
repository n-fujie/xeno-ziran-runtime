# Total observation, planetary-scale observation, Scale / Size / Speed, and the autonomous research loop

Code: `backend/xzr/totalobs/`. Study Engine environment kind: `total-observation`. Templates: `total-observation`, `autonomous-loop`, `planetary-observation`, `sss-axes`.
UI: Experiments → *New protocol* (conditions form), *Total observation*, *Research lines*. API: `/api/studies/lineage`, `/api/studies/totalobs/conditions`.

**Status (see `ZRS_INTEGRATION_STATUS.md`, "Final integration"):** implemented and operationally verified; scientifically **not** evaluated; non-redundancy **not** established.
Everything below describes a *synthetic model*. It is not the Earth, not reality as a whole, and no result from it is evidence about either.

## 1. What the model is

`world.py` — `rows × cols` regions (latitude bands, longitude periodic). Each carries an activity `u` and a persistent mark `m`. Activity spreads between regions within an
interaction `span` with an integer delay `ceil(distance / c)` (`c`: propagation speed, regions per step), decays, is fed by a few pulsed sources, and decays more slowly where a
mark sits. The world advances whether or not anything observes it. Sources are fixed by the *generator* seed; process noise by the *engine* seed.

`observers.py` — sensors with a position, footprint radius, **scale** (block size), observation boundary (grid offset), period, noise, absorption (`backaction`), wear and health.
An observation (i) reads block means, (ii) costs one resource unit per block from a pool shared by all sensors (a block with no resources left is not read), (iii) *absorbs* a
fraction of the activity it read (so observers interfere and the order of observing and intervening matters), (iv) wears the sensor by the activity it saw (at zero health the
observing condition expires), (v) reports to the hub after `hops × latency` steps, and not at all from inside a communication-outage zone. The hub keeps a bounded store; records can be lost.
Losing a record never undoes what the observation or an intervention did: the marks stay.

`identify.py` — *identified objects* are connected sets of regions above a threshold, under the observing configuration in force (scale, boundary, integration rule `separate | mean | finest`,
variable `level | change | contrast`, threshold, connectivity). Change any of these and the objects change although the world did not.

`verifier.py` — the only place where the world's state is compared with what was identified (recall, precision, spurious, merged, split; and whether an identified object is `world`- or
`configuration`-made). It is never given to an agent.

## 2. Reality as a whole — what is and is not claimed

`ontology.py` keeps eight things apart in every run's ledger: object transitions that go on without observation; the observing system's own transitions; their interaction; interventions;
the recording mechanism; material consequences that outlive the records of their cause; what the agent can obtain (the hub's records only); what has been constructed from that (identified
objects, hypotheses, derived variables, evaluation outcomes — flagged `constructed`). Layers 1–6 are read by the verifier only. `scope_audit` fails a record whose agent layers carry
world-state fields, whose layers are missing, or whose claims `model_state_is_reality`, `reality_as_whole_represented`, `earth_claim`, `local_observation_generalised_to_whole` are not false.
Structural guard (tested): `agent.py` imports nothing from the world, the observers or the verifier, and `Findings` has no world-state field.
Reality as a whole is **not a module** here and the model state is not equated with it.

## 3. Total observation (A–G)

| | where |
|---|---|
| A generation / expiry of observed objects | identified objects depend on configuration; `verifier.classify_identified` marks `configuration`-made ones; `config_born_rate` |
| B mutual transformation of observer and object | absorption by observation; wear → expiry (`observers.py`) |
| C observation integration | `separate / mean / finest`; the agent computes its identification under every rule each generation and records `invariant` or `lost` (`integration`) |
| D order dependence | `test_order_of_observation_and_intervention_matters…` (non-commuting in *this model*; not a quantum claim) |
| E expiry of observing conditions | `fail_sensor`, `cut_zone`, `set_pool`, `lose_records` events; sensors silent in the agent's findings |
| F consequence after record loss | marks persist after `lose_records` (tested) |
| G self-revision of observing conditions | operations `set-scale`, `set-period`, `set-offset`, `set-threshold`, `set-connect`, `set-integration`, `derive-variable`, … (closed grammar) |

## 4. Planetary-scale observation, as conditions

`planetary.conditions(env)` evaluates, for the declared parameters: spatial extent, inter-regional interaction span, propagation time across the extent in observation periods,
observation period, communication delay in periods, observation density, resource allocation (demand / pool) and the local–global time gap, each with a threshold, and lists the model's
limits and what a real-world claim would require (measured data, an existing earth-system model, a mapping to a real geometry). The count of regions or sensors alone does not satisfy them
(tested). `scaling_law` fits a power law over a sweep and reports no exponent from fewer than three points. `earth_claim` is always false.

The ten conditions of the `planetary-observation` template: distributed observation, finite propagation, asynchrony, interference, mutual transformation, expiry, record loss,
communication delay, resource contention, reorganisation (+ a world that meets every declared condition).

## 5. Scale / Size / Speed

Three groups of declared parameters: **Scale** (sensor block size), **Size** (rows × cols), **Speed** (propagation `c`, source period, sensor period). `sss.vary` changes one axis only
(`independent` checks which parameters differ); `effects` / `factorial` give main effects and 2- and 3-way interaction contrasts from a full 2³ design (an undefined cell makes the effects that
use it undefined — never 0). Metrics carry a definition, domain, unit, method, version, history, basis keys and expiry conditions (`sss.METRICS`). `comparable` refuses to compare two measurements
whose version or basis differs and says why; `MetricLog.revise` bumps a version and `segments / compare` return no number across the break. The research loop revises its own evaluation rule
(E0 → E1 → E2 and back), which is a metric revision and is logged as such (`comparable_with_before: false`).

## 6. The autonomous research loop

`loop.py` runs several generations: observing layout → local observation → identification and failure → change of **question** (`survey → resolve → trace`, back to `survey` after a supported
hypothesis, or after identification is lost) → change of **hypothesis** (an estimated propagation speed, tested by an intervention and revised when refuted) → change of experimental condition
→ **intervention** (`perturb`, available only after a reversible grammar extension and withdrawn after two tests with no arrival) → change in the object system → reorganised later observing
conditions (reachability levels by `hpo.reachability.compare_levels`, static and dynamic) → **history re-entry** (an external memory of outcomes scoped by question; control: `shuffled`).
Each generation records the ten items: condition before; the event that fired the change; the changes; what became possible; what was executed; the object-system change (verifier side);
the new observation; the next decision; failure / stop / expiry; revision of the rules themselves (`hpo.metarevision` — before, evidence, after).

Reused, not re-implemented: `hpo.metarevision` (`RuleSpec`, `RuleTable`, `MetaReviser`), `hpo.reachability` (`compare_levels`, `SET_KEYS`). The HPO controller (`hpo.reconfig`) is bound to the HPO
field and the laboratory populations to the laboratory; they are run in their own environments (HPO-world, lab-population, shared-oi), not inside this loop.

Bounded self-revision: operations come from a closed list with costs; a budget and `max_ops` per generation limit them; the grammar extension is reversible; a variable is adopted only if it identifies
more objects than the variable in force and more than the same derivation on time-shuffled records; opposite scale moves on one sensor are suppressed within a cooldown (recorded); a stopped
research (no observer and no budget to add one, or three generations with nothing to try) is recorded, and the world keeps being scored.

The hypothesis test is a design, not a given: the detector is a sensor whose last two reports agree, the site is outside its footprint, the detection threshold is four times the detector's own
report-to-report variation; the true arrival comes from two forks of the world on the verifier side. A test the agent calls *supported* can still be far from the verifier's value; the count is reported.

## 7. Arms and ablations (`total-observation`)

fixed · random-matched (same grammar, random arguments) · adaptive · adaptive-history · adaptive-history-shuffled · adaptive-meta · full · full without each of: variable generation,
classification, boundary, evaluation rule, grammar extension, history, rule revision. Same world, seeds, start layout, budget, information (the hub's records), stop rules and verifier in every arm;
contrasts that differ in several components declare all of them (`varies`). No arm is Active Inference or Active Learning: neither is implemented as an arm here.

## 7a. Rules v1 and v2

`environment.rules_version` selects the rule set. `v1` (the default when the key is absent) is the first release and is kept so that earlier stored studies replay identically; `v2` is the reliability repair
(`docs/RELIABILITY_REPAIR.md`): the hub's freshness window counts from arrival, a missing report is classified without asserting a cause and probed, `denied` / `scale-mismatch` conflicts are arbitrated and infeasibility is declared,
a hypothesis is `supported` only after two consistent tests and can be withdrawn, and the verifier audits every one of these. The templates use v2. v1 and v2 results are not compared.

## 8. What is not done

No confirmatory study, no power analysis for this line, no cross-machine reproduction. No claim of non-redundancy (axes in `NONREDUNDANCY.md`). The model is one family of dynamics with a scalar activity.
The hypothesis test is confounded by the world's own pulses unless the detector is steady; many tests are deferred or inconclusive. Under rules v1 the `silent` reason conflated an outage with a delay longer than the freshness window and `denied` vs `scale-mismatch` was handled by a cooldown only; v2 repairs both (see 7a).
