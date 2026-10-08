# Theory — the minimum the software needs

Operational-shape tools are not an implementation of a final ontology. They are experimental instruments for
varying configurations, testing operational distinctions, comparing transformations, and measuring changes in
subsequent possibilities. This page defines only the terms the code uses, each by what the code computes. The
philosophical framework they come from is not reproduced here and is not validated by running the software.

**Configuration.** A unit of the simulated field holding numbers: a difference, a threshold, retention, memory,
capacity (`xzr/runtime/state.py`). Configurations are connected by weighted, gated connections. *Which* units
exist is a modelling choice of the scenario or generator — not a claim that the world comes in these units. The
same field can be read at five resolutions (single configurations, and clusters at local, meso and macro scale of
an intrinsic hierarchy, plus global aggregates), and results are reported per resolution because a distinction
can be visible at one and not at another.

**Operational shape.** A recurring pattern of operations — ignition, propagation, retention, return, cut,
reconfiguration — detected after the fact by the shape detector (`xzr/shapes/`). Shapes are summaries of what
happened; they never feed back into the runtime.

**Establishment / loss.** A difference is *established* when it is retained beyond the step that produced it
(retention, memory, a new connection) and *lost* when it decays, is cut, or its connection is removed or
redirected (disconnection, cut, reconfiguration). These are runtime operations with switchable implementations
(`xzr/runtime/flags.py`), which is what makes ablation possible.

**Transformation, comparison, compression.** A *transformation* is any change applied to a configuration —
an intervention, a structural variant, a history operation. *Comparison* runs the transformed and untransformed
world from the same state and random stream (paired, `Engine.fork()`) and tests the difference against a noise
replicate (same world, another random stream). *Compression* summarises a long trajectory into recurrent symbols
and phrases and measures what the summary preserves and loses (`docs/LONG_RUN_COMPRESSION.md`).

**Real effect / reconfiguration.** An effect counts only when it is downstream and systematic: detected by a
family-wise sign-flip test over paired seeds, larger than a practical threshold, and not explained by the
transformation's own bookkeeping (a variant's own event counts are excluded). *Reconfiguration* is a change of
connection structure (redirect, cut, creation) — measured as a change in later configuration, not assumed.

**Non-closure.** No result is final: every status is relative to a configuration, resolution, horizon and seed
set, and the software reports which of these it holds for. `EQUIVALENT` (shown within ±5 %) and `UNRESOLVED`
(neither shown) are kept distinct; *not detected* never means *absent*, and *bit-identical* means no difference
in the represented and measured state — not proof that no difference exists elsewhere.

**History re-entry (HRGI-style result).** The runtime's retained history is per-configuration memory. A result is
reported as history re-entry only when the experiment measures all four of: a retained prior difference; its
re-addressability (restoring it changes the effective thresholds again); actual re-entry (restored configurations
act differently than without it); and a downstream difference beyond the noise replicate. Otherwise the result is
reported as *history dependence* or as *no detected dependence* (`xzr/experiments/history.py`). (CICGI, the
human-civilizational special case, is not a runtime term and does not appear in the software.)

**Address-domain.** Configurations and clusters have addresses in the intrinsic hierarchy (e.g. `1.4.2`).
*Addressability* (a set can be named and resolved) is not *access* (an operation actually reaches it): the
escalation experiments vary addressability (`address` regimes) separately from what reasoning-derived
interventions do. Access selection / modification / construction are not separate runtime operations here; the
software does not use those terms.
