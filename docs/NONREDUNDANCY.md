# Operational non-redundancy — what is and is not claimed

**Status: not established.** Nothing in this repository shows that a P/A method does something that a fairly equipped alternative does not. The software
for finding out exists (`xzr/study/nonredundancy.py`, attached to every analysis and printed in every Results text); its default verdict is *not
evaluated* for functional and exploratory studies and *not established* unless an independent confirmatory comparison detects a difference on a comparable axis.
The existence of a revision mechanism, a reachability record or a meta-revision is not evidence of non-redundancy.

## Axes, and what is comparable

| axis | indicators | comparable across ARDS and HPO arms? |
|---|---|---|
| prediction | ARDS hypotheses (verifiable / falsifiable / supported / refuted) | no — only ARDS arms state predictions |
| intervention | experiment (alteration) selection; protocol interventions | no — arm-internal (HPO arm with `select`; ARDS fixed / permuted order) |
| reachability | `capable_gained` (held-out differences observable beyond the default); HPO opened / identified records | **yes** for `capable_gained` (one ARDS evaluation for every arm); records HPO-only |
| observability | `unseen_coverage` (primary), seen / all coverage, `unseen_fdr` | **yes** (one evaluation, one service) |
| action on reality | — | no — every effect is internal to the simulation |
| temporal continuity | stop step, ceased share (HPO world); three cycles (shared environment) | no — the shared environment's horizon is three cycles |
| reorganisation of later structure | adopted / changes / meta-revisions | no — counts mean different things in the two families |

Not evaluable by this environment: differences outside the catalog; alterations other than the four; variable generation and boundary change as *shared*
operations (reasons in `shared/ops.py`); human-readability and human-energy independence; any effect outside the simulation.

## Equal footing, and where it is not

Same environment, replicate, start configuration, seed blocks, budgets (72 body runs, set-up 480 s minus the start configuration), the five revision operations,
the observer-only information and the evaluation code. Asymmetries that remain and are declared in every study's fairness record: the proposal policy (ARDS rules R1–R4
or the existing procedure vs the HPO rule table — structurally close, so the comparison is between policies), history on / off, meta-revision, alteration selection,
and who has which operation (operations matrix). ARDS arms are executed unchanged; the HPO arm is not weakened (it gets the same budget and permissions and its own
rules in full).

## Overlap with existing work (bibliographic orientation — not a systematic review; verify every citation before it is used in a paper)

* **Experimental practice and concept formation.** Changing experimental conditions to see what becomes observable, and forming concepts inside the experiment,
  is the subject of the literature on exploratory experimentation: Steinle (1997, *Entering new fields: exploratory uses of experimentation*, Philosophy of Science 64;
  2016, *Exploratory Experiments*, Pittsburgh), Burian (1997), Feest (2010, 2012: exploratory experiments, concept formation, theory construction), Rheinberger (1997,
  *Toward a History of Epistemic Things*: experimental systems and epistemic things), Rouse (2002, *How Scientific Practices Matter*), Chang (2004 *Inventing Temperature*,
  2012 *Is Water H₂O?*: epistemic iteration), Schickore (2017, *About Method*). **No claim is made that revising conditions, or generating variables or concepts inside
  research, is a discovery of this project.** Whatever P/A adds would have to be a *specific, measurable operational difference* on the axes above.
* **Methods that already select, revise and adapt.** Active inference / expected free energy (Friston et al. 2015), active learning (Settles 2009), Bayesian
  experimental design (Chaloner & Verdinelli 1995), adaptive control (Åström & Wittenmark), automated science with closed hypothesis–experiment loops (Langley et al. 1987;
  King et al. 2009, *Adam*; Williams et al. 2015, *Eve*; Kitano 2021, Nobel Turing Challenge). The HPO reason→change rules are a rule-based adaptive instrument
  configuration; ARDS's EXISTING-blind arm is an independent re-implementation of an existing adaptive procedure with observer-side information only. Overlap with these
  families is expected until a comparable axis shows otherwise; none of them has been implemented here as an arm beyond the ones named.

* **Observation, apparatus and reality.** That measurement apparatuses take part in what they measure, and that what counts as an object is made in an observing arrangement, is argued by Barad (2007,
  *Meeting the Universe Halfway*: agential realism, apparatus, intra-action); that a naturalist account of nature does not guarantee that it is for us, and what that implies for thought, by Brassier
  (2007, *Nihil Unbound*). The total-observation line implements *operational analogues* (absorption by observation, wear of the observer, objects that depend on the configuration) in a synthetic
  model; it does not adopt or test those positions, and the one reference named as "Capps" in the project brief has not been identified to a specific work here: it is listed for the owner to supply
  and verify. **Nothing in this repository shows that these operational analogues are new**; distributed sensing, adaptive sampling and sensor-network placement are long-standing engineering topics, and
  closed-loop automated science (Langley; King; Williams; Kitano, above) already revises hypotheses and experiments from results.

## What would count

A confirmatory, pre-registered comparison on fresh seeds (not the functional replicates 3980–3989) in which a method with the P/A operation is compared with
alternatives given the same information, authority and budget, with a declared contrast on a comparable indicator, an equivalence margin, a power plan and the stop rules of
`docs/level2/PROTOCOL_L2_DRAFT.json`. A detected difference is *operational*, specific to the environment and the alterations defined, and says nothing about theory.
Equivalence inside the margin is an equally valid, equally reportable outcome and would be kept as such.
