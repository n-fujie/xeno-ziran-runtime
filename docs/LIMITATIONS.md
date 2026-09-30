# Limitations

Stated plainly so the tool is not read as more than it is.

## What the simulator is not

* **Not a prediction engine.** It explores counterfactual transitions in a generated or user-given operational
  field. No output is a forecast about any real system.
* **No probability claims.** Comparisons use common random numbers plus one noise-floor replicate (the baseline
  under a different random stream). "Exceeds noise" means |Δ| > 2·|baseline′ − baseline| — a heuristic guard
  against over-reading, not a significance test. In the demo, node-level reach changes after
  `remove concept human` are typically *within* noise; the UI says so.
* **Interpretation labels are analogies.** "credit-like", "institution-like" etc. are attached by an editable
  rule table to relative signature levels. They are not detected categories and never feed back into dynamics.
* **The practice layer is one explicit scorekeeping scheme**, inspired by inferential scorekeeping; it is not
  an implementation of any author's theory, and the sample claims are illustrative material, not assertions.

## Model limits

* Dynamics are a single generic excitable-network rule set (threshold ignition, normalized emission with gain,
  retention, memory-shifted thresholds, load-dependent conduction, overload cuts, triadic closure,
  reconfiguration). Default parameters were tuned so the benchmark field stays in a sustained, non-saturated,
  intermittent regime; other parameters can saturate or die out.
* Shape descriptors are operational proxies: e.g. "path dependency" is lagged pattern correlation, "bottleneck"
  is sampled shortest-path visitation, "attractor-like recurrence" is coarse pattern Jaccard ≥ 0.85.
* Signature levels are **relative** (tertiles across clusters at that moment).
* The multi-scale hierarchy is computed once from the initial topology; later connection changes do not
  re-partition it (rebuild by resetting).
* Boundaries defined by sets are resolved to connections when an intervention configuration is compiled;
  connections formed later across that boundary are gated only after the next apply/compare.
* The connection pool has fixed capacity (initial + ⅓); when it is full, new connections are not formed
  (dead slots are reused).

## Service limits

* Sessions live in memory in one process (default max 4, oldest evicted). Horizontal scaling needs session
  affinity or splitting the simulation worker out.
* Checkpoints: 24 kept per session, older ones thinned; rewind replays deterministically from the nearest one,
  including logged interventions.
* Event log keeps the last 1,500 steps in memory (exports cover that window); the metrics series keeps 20,000.
* Transport approximations (never affecting simulation state or events): quantized differences with
  hysteresis of 3 levels; memory afterimages every 5 steps; weight changes below 0.05 not streamed.
* When a client falls >600 steps behind it is resynced with a snapshot (events remain in the event log).
* Rendering FPS was measured in one Chromium-based browser on one machine.
* Japanese localization is a partial string table (`?lang=ja`).

## Environment note (this machine)

Launching the Homebrew Python server from the desktop app's preview helper stalls on macOS folder privacy
(`~/Desktop`); starting it from a terminal (`make dev`) works.
