# Ziran System — Heterogeneous Philosophical Operations (HPO)

HPO is an experiment layer in this runtime (`backend/xzr/hpo/`). It runs *heterogeneous philosophical operational
series*: engineering proxies named after six philosophical operations. They run together inside one simulated
world, and the layer makes it possible to experiment on how they:

* ignite, compete, couple, split, mutate, cease and re-ignite;
* act on the world (real effects inside the simulation);
* have their history re-inserted;
* reconfigure the Ziran System's own experiment settings.

HPO adds to the runtime. It replaces nothing: the runtime, the published studies and their results are unchanged
(see [HPO_VERIFICATION.md](HPO_VERIFICATION.md)).

> **What HPO is not.** It is not a set of fixed algorithms per philosopher, nor an encyclopedia of the history of
> philosophy. It is not a formalisation of any philosophical system. **No result of it is evidence for or against a
> philosophical doctrine.** The series are proxies named after their sources so that the correspondence, and its
> limits, can be inspected (see the [Source correspondence](#source-correspondence) section).

## Architecture

```
xzr/hpo/
  registry.py     Philosophical Operational Registry: sources and their status, central claim (paraphrase), minimal
                  operational shape, configuration / ignition / rule / coupling / split / cessation / re-ignition
                  conditions, observables, history reinsertion, real effects, approximation, failure, revision
  world.py        the world: runtime engine + exogenous input stream (identical in every paired branch) + endogenous
                  stream; true state is read only by instruments and by the harness
  observe.py      instruments: what an operation can observe, at which resolution / window / period, through which
                  veils, at what cost — every unobserved value carries its reason and is never zero
  operations.py   the six series: ignition conditions (FIRED / NOT_FIRED / UNOBSERVABLE) and rules returning
                  requests; they never see the world
  field.py        Configuration and Ignition Engine + Interaction Engine: settings, sampling, ignition, status
                  (ignite / cease / re-ignite), requests → runtime intervention records, closure filter, resources,
                  interaction rules (RULES), competition, coupling / decoupling / splitting, reclassification,
                  history reinsertion, scheduled configuration changes
  causal.py       causal execution history (a DAG of state changes with before / after and causes)
  metrics.py      measures of a run (ignition, transformation, reachability, cessation, re-ignition, history,
                  latencies, real effects, unobservability, causal structure)
  stats.py        paired statistics (sign-flip, bootstrap, Holm, noise floor)
  reconfig.py     HPO-003: sandboxed reconfiguration of the experiment's own settings; proposals vs validation
  experiments.py  HPO-001 / HPO-002 / HPO-003 / generalization protocols and analysis
```

Layering: `hpo` imports `runtime`, `lod` and `experiments` (world regimes, provenance). No product layer imports
`hpo` (`tests/test_layering.py`). The iOS bundle excludes it, as it excludes every desktop experiment harness.

### Separating what is true from what an operation can know

Operations receive `Observation` objects only, and they act through requests. The field compiles those requests into
runtime intervention records (gates, threshold scaling, connections, severing, injection) plus direct memory deposits
(history), in the same way that `experiments/history.py` writes memory. The true state is read by:

* instruments, which apply channels, resolution, window, period, veils and cost;
* the harness's metrics.

An `oracle` instrument exists only as the HPO-001 truth-leak control. A test checks that `operations.py` references no
world, engine or state.

### Configuration-dependent ignition

An ignition is evaluated on observed values and has three outcomes: FIRED, NOT_FIRED or UNOBSERVABLE. UNOBSERVABLE
records one of six reasons:

* unmeasurable;
* instrument mismatch;
* scale mismatch;
* time-window mismatch;
* boundary invisibility (a veil);
* unmeasured (the operation could not pay for the measurement).

These are kept apart. A difference that could not be observed is never turned into "no difference". The conditions
that can change are the world, the instruments (channels, resolution, window, period, noise, veil penetration), the
channel catalog, the boundary (veil and gate scale), time (act delay), resources, institution (forbidden requests,
limits), external memory, history reinsertion, feedback, reachability horizon, evaluation order, scheduled changes
and stopping conditions (`field.DEFAULTS`).

Series do not need a human subject, language, concepts or inferential commitments. The configuration where these
apply is kept as an experimental condition: `symbol_layer` and `picturing_requires_symbol_channel`, both off by default.

### Interaction Engine

These switches can each be turned off (`Settings.interaction`):

* `share_info`
* `share_resources`
* `share_history`
* `transform` (the explicit rule table `field.RULES`)
* `observation_change` (veils hide regions from other operations; a revision refines overlapping instruments)
* `competition_adapt` (conflicting threshold factors attenuate the weaker rule and amplify the stronger)
* `partition` (coupling into composite kinds such as `transduction∘closure`, decoupling, splitting)
* `reclassify` (an operation whose executed actions match another kind's prototype changes kind)
* `action_filter` (an active closure filters other operations' acts on its region: irritation)

Every change is a causal-history event with the target's state before and after, and the events that caused it.

## Running and reproducing

```bash
.venv/bin/xzr hpo registry
.venv/bin/xzr hpo run hpo-002 --pilot --seeds 8 --procs 4
.venv/bin/xzr hpo run hpo-002 --procs 7
.venv/bin/xzr hpo verify
.venv/bin/python backend/scripts/hpo_verify.py
```

* `--pilot` uses the smoke seed range and writes to `xzr-results/hpo-pilot/`.
* Without `--pilot`, the run is confirmatory: it needs the frozen protocol and writes the published
  `backend/experiments/results/hpo/*.json`. It refuses to overwrite.
* `xzr hpo verify` re-runs seeds and expects identical measures.
* `hpo_verify.py` is the regression and overall verification report.

The plan, seeds, measures, hypotheses and stopping conditions are frozen in [HPO_PROTOCOL.md](HPO_PROTOCOL.md). Its
SHA-256 is pinned in `experiments.py`, and every result records it. On 8 cores, HPO-002 (360 seeds × 28 branches)
takes about 10 min; HPO-001, HPO-003 and the generalization runs take a few minutes each.

## Experiments

* **HPO-001 (re-specified).** The pilot archive (`HPO_001_Pilot.zip`) was not available in the implementation
  environment. No pilot code or result was inherited, reconstructed or estimated. HPO-001 here implements the three
  corrections the pilot was meant to receive:
  * true state is separated from what an operation can observe, with an explicit truth-leak control;
  * exogenously matched comparison is distinguished from the intervention-branched continuation (the first
    divergence of the endogenous stream is reported);
  * no "accuracy" is read as a ranking of theories.
* **HPO-002 Cross-Operational Transformation.** Conditions A–G as in the request (independent, coupled, mutual
  transformation, historical reinsertion, cessation, re-ignition, ablation), plus R0 (no HPO) and C~ (noise).
  There are 10,440 paired comparisons, plus generalization to six settings not used in development.
* **HPO-003 Recursive Reconfiguration.** A static, a result-driven (recursive) and a random-change controller run on
  the same seeds. Proposals of new variables are kept apart from their held-out validation.

## Results

Results are generated from the result files by `backend/scripts/hpo_report.py` (nothing is typed by hand):
[HPO_RESULTS.md](HPO_RESULTS.md). Regression and verification: [HPO_VERIFICATION.md](HPO_VERIFICATION.md). The
viewer shows the same files (`?view=hpo`). The protocol history, the failed first run and its traceback, the
calibration on development seeds and the robustness sweep are kept in `backend/experiments/results/hpo/history/`.

```bash
.venv/bin/python backend/scripts/hpo_substantive.py --seeds 48
.venv/bin/python backend/scripts/hpo_verify.py --embodied-python PATH
.venv/bin/python backend/scripts/hpo_report.py
```

* `hpo_substantive.py` is the post-hoc descriptive analysis.
* `hpo_verify.py` is the regression and verification report. PATH is a Python with `embodied/requirements-lock.txt`
  installed, from ziran-xeno-simulator.
* `hpo_report.py` regenerates the docs.

## Source correspondence

| kind | series | sources (status) | implemented as | main approximation |
|---|---|---|---|---|
| withdrawal | Harman, OOO | Tool-Being 2002; Guerrilla Metaphysics 2005; The Quadruple Object 2011 (bibliographic) | boundary gating + veil (others cannot observe) + one vicarious connection | withdrawal reduced to permeability and observability |
| transduction | Simondon, individuation | L'individuation… 1958/2005; Du mode d'existence des objets techniques 1958 (bibliographic) | domain grows cluster by cluster through a metastable milieu; splits | metastability = closeness to threshold |
| concrescence | Whitehead, process | Process and Reality 1929; Science and the Modern World 1925; Adventures of Ideas 1933 (bibliographic) | occasions prehend observations, reach satisfaction, deposit data (memory, archive) | prehension = sampling; no subjective form or eternal objects |
| picturing | Sellars, picturing / revision | EPM 1956; PSIM 1962; Science and Metaphysics 1968 (bibliographic) | predictive picture, corrected and revised (finer categories), used to damp | picturing = predictive tracking; images = resolution levels |
| assemblage | Deleuze & Guattari | Anti-Oedipus 1972; A Thousand Plateaus 1980 (bibliographic) | territorialising connections; lines of flight when flow is blocked; plugs into others | flows = penetrations; no coding or abstract machine |
| closure | Luhmann, operational closure | Soziale Systeme 1984; Die Gesellschaft der Gesellschaft 1997; Maturana & Varela 1980 (bibliographic) | closed incoming boundary except coupling channels, self-reproduction, self-adjustment on irritation, filters others | communication and meaning reduced to connection recursion |

"Bibliographic" means the work is cited from bibliographic knowledge. Its text was not consulted while implementing
the proxy. Central claims in the registry are the implementer's paraphrases, not checked against the texts.
Extension candidates are listed in the registry: Hegel, Leibniz, Spinoza, Kant, Peirce, Marx, Bergson, Foucault,
Brandom, Brassier, Sacilotto, Barad, Negarestani, Latour, Varela and Friston. None is implemented.

The HPO request also names research lines that are not implemented anywhere on this machine: OOO Machine Operations,
Barad / Agential Realism, Sacilotto / Structural Mapping, Constructor Theory, Scientific Operational Shapes and the
Scientific Operational Extinction Point. They exist as concepts in documents only (see `ziran-xeno-simulator`). HPO
does not claim them, and the registry lists them only where a series is an extension candidate.

## Publication, deployment and reproduction

**Source ↔ deployment.** The production site https://ziran-xeno-simulator.vercel.app was built from a clean working tree at
commit `7cb381f` on branch `hpo-integration`, with `backend/scripts/export_static.py`. On 2026-10-13 the production files
were compared with that commit:

* the JavaScript and CSS bundle names are identical;
* the six published HPO result files (`/api/experiments/hpo-*`) are byte-identical to the files at `7cb381f` (SHA-256);
* the earlier result files are byte-identical to the local copies.

A later commit that changes only documentation does not change the deployed site.

**Reproduction** (Python ≥ 3.11, Node ≥ 20; about 45 min of compute on 8 cores in total):

```bash
git clone https://github.com/n-fujie/xeno-ziran-runtime.git && cd xeno-ziran-runtime
git checkout hpo-integration
make setup
.venv/bin/xzr hpo verify
.venv/bin/xzr hpo run hpo-002 --pilot --seeds 8
mv backend/experiments/results/hpo backend/experiments/results/hpo.published
mkdir backend/experiments/results/hpo
.venv/bin/xzr hpo run hpo-001 --procs 7
.venv/bin/xzr hpo run hpo-002 --procs 7
.venv/bin/xzr hpo run generalization --procs 7
.venv/bin/xzr hpo run hpo-003 --procs 7
```

* `make setup` creates the venv and installs the backend and frontend.
* `xzr hpo verify` re-runs seeds and checks the measures are identical.
* The pilot run uses the smoke seed range and writes to `xzr-results/hpo-pilot/`, never to the published results.
* The `mv` and `mkdir` lines are needed because confirmatory runs refuse to overwrite published results: the published
  results move aside first.
* Each confirmatory run checks that docs/HPO_PROTOCOL.md matches the pinned hash before it starts.

Then compare `contrasts` and `verdicts` in each new file with the file in `hpo.published/`:

```bash
for f in hpo001 hpo002 general hpo003; do .venv/bin/python -c "import json,sys; a,b=(json.load(open(p)) for p in sys.argv[1:]); \
  k=[x for x in ('contrasts','verdicts','results','proposals') if x in a]; print(sys.argv[1], all(a[x]==b[x] for x in k))" \
  backend/experiments/results/hpo/$f.json backend/experiments/results/hpo.published/$f.json; done
```

Timings, timestamps and the commit / dirty flags in `provenance` differ by design. Platform note: runs are
bit-identical on the same machine and numpy version (`xzr hpo verify`, and the seed-0 trace check in
`hpo_substantive.py`). A full confirmatory re-run on another platform has not been carried out.

For the post-hoc analysis, regression report and generated docs, run in order:

```bash
.venv/bin/python backend/scripts/hpo_substantive.py
.venv/bin/python backend/scripts/hpo_verify.py
.venv/bin/python backend/scripts/hpo_report.py
```

`hpo_verify.py` needs the sibling repository `ziran-xeno-simulator` next to this one. Pass `--embodied-python PATH`
for the embodied suites.

## Philosophical correspondence, by layer

For every series the layers below are kept apart. Nothing in a lower layer is evidence for an upper one, and a
proxy's behaviour is not read back into the philosophy.

1. **Verified claims from primary sources.** None. No primary text was consulted in this implementation, so no
   claim in the registry is verified against a source. This holds for all six series.
2. **Operational reconstruction.** The registry's `central_claim` (an implementer paraphrase) and `minimal_shape`
   (what was taken to be the operation's minimal form).
3. **Engineering proxy.** The code: the conditions in `operations.py` and the interaction rules in `field.RULES`.
   The rules are the implementer's hypotheses about how the series act on one another. None of them is derived
   from the texts.
4. **Experimental results.** Properties of the proxies in this runtime (docs/HPO_RESULTS.md).
5. **Independent Ziran / Xenoscience developments.** Situated ignition conditions, unobservability reasons, real
   effects as runtime records, history reinsertion, recursive reconfiguration and operational cessation. These are
   this project's own operational vocabulary, applied to every series. They are not attributed to the six authors.
6. **Unverified interpretations.** Any reading of a result as saying something about the philosophy.

| series | proxy result (layer 4) | unverified interpretation it must not be taken as (layer 6) |
|---|---|---|
| Harman (withdrawal) | Veils blind other operations: boundary invisibility occurs only when observation change is on. Removing its condition removes most of its downstream transformations. Under C it ignites in fewer seeds than under B. | that objects "withdraw", or that vicarious causation was modelled |
| Simondon (transduction) | It is the main target of transformations. Picturing's damping and competition attenuate its structuring factor, and it splits on its own. | that individuation was simulated, or that metastability is closeness to threshold |
| Whitehead (concrescence) | Its deposits re-enter as memory, and about 77 % of archived data reinsertions cause a later event. Removing its channel is compensated by information sharing. | that process / objective immortality was shown |
| Sellars (picturing) | It ignites in every C seed versus 52 % under B. Its revisions refine other instruments. The proposed trend variable worsened its error. | that picturing is predictive tracking, or anything about the manifest / scientific image |
| Deleuze & Guattari (assemblage) | It forms most composite kinds, and removing its condition removes about 80 % of its transformations. | that assemblages, desire or lines of flight were modelled |
| Luhmann (closure) | It filters other operations' acts (irritation). Removing it changes field ignitions and memory. | that operational closure of communication was modelled |

No new philosophical category was introduced to explain a result. Composite kinds (for example
`transduction∘closure`) are run-time records of coupling. They are not philosophical positions.

## Implementation limits

* Every series is a proxy. The interaction rules, thresholds and rule parameters are design choices, calibrated on
  development seeds. Other choices can give other results.
* It covers one runtime and one world generator, with 800 configurations (1,200 in one generalization setting) and
  240 steps per run.
* Effects are simulation-internal. The runs have no physical, institutional or networked effect.
* Recursive reconfiguration changes settings inside a whitelisted sandbox. It never changes code.
* The number of trials is not philosophical validity.
