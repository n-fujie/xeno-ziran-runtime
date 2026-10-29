# Performance evidence of stage 4

Measured on the machine the work was done on, in a session in which **the host was loaded by other applications** (WindowServer and other helper processes at 20–45 % CPU each; load average about 8). Frame times in this session are therefore
higher than those of `../perf_stage3/` (quiet conditions) *for the unchanged Stage 3 build as well*. Nothing in this folder is compared with the Stage 3 folder; builds are compared only with each other, interleaved in time, in the same session.
GPU time is not available in this headless browser (`EXT_disjoint_timer_query_webgl2` is not exposed): every figure is wall time with a GPU sync (`window.__meos.benchmark`).

| folder / file | what it is |
|---|---|
| `orbit_decomposition_balanced.json` | `ecosystem_orbit_decompose.mjs`, balanced tier, cameras habitat / overview / body, 300 orbit frames each: per-frame series (draw calls, triangles, geometries, textures, programs, LOD switches, visibility flips), their correlation with the frame time, and each switchable part turned off in turn (under load: indicative only). Taken before the fixes of section 12. |
| `ab_three_builds/` | three builds interleaved, 3 repetitions (`ecosystem_perf.mjs`, balanced, 120 frames): `3032` Stage 3 (`93119a0`), `3033` Stage 4 before any performance change, `3031` Stage 4 with a startup compile that made every LOD level visible (an ineffective change that was later removed; its build is labelled `stage4_precompile` in `summary.json`). |
| `habitat_ab/` | habitat only, Stage 3 (`3032`) against Stage 4 as in `3031` above, 5 interleaved repetitions. |
| `orbit_fix_ab/` | the orbit decomposition (series only) of the Stage 4 build before (`3033`) and after (`3031`) the fix of section 12 (compile with the composer's render target bound; the reflection rendered once at start), 3 interleaved repetitions, cameras overview / habitat / body, and `programs_built_during_orbit.mjs` (names the programs the renderer builds during an orbit: 22 before, none after). |
| `final_tiers/` | the final build against Stage 3, all three tiers, cameras overview / habitat / body / observer, 2 interleaved repetitions. |
