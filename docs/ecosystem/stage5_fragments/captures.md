### Stage 5 captures (`docs/ecosystem/visual/stage5/`; the Stage 3 and Stage 4 images are kept where they are)

Each capture is a URL (see `frontend/scripts/ecosystem_capture.mjs`, entries 45-59); the exact camera, viewport and tier are in `visual/stage5/cameras-balanced.json`. They are all pictures of model records, not evidence.

| image | what it shows | deep link (after `?view=ecosystem&`) |
|---|---|---|
| `45-f14-history-mfs.png` | F14, history-mediated MFS: research map with current MFS and the validated alternative | `mfs=MFS-F14-1` |
| `46-f14-m2-mfs.png` | F14, M2-mediated MFS | `mfs=MFS-F14-2` |
| `47-f9-no-mfs.png` | F9 (NO_MFS) in the F1-F16 table, with the row marked | `experiment=F9` |
| `48-adaptive-failure.png` | adaptive controller, 'renewal disabled': the switch and the failed outcome (preserved: no) | `route=adaptive:renewal disabled` |
| `49-fixed-fallback-success.png` | fixed M2 fallback, 'history lost' (seed 1): preserved: yes (5 of 10 seeds in the experiment) | `route=fixed:history lost` |
| `50-sss-map-mfs-a.png`, `51-sss-map-mfs-b.png` | SSS map of the two F14 MFS | `sssmap=MFS-F14-1`, `sssmap=MFS-F14-2` |
| `52-observation-sensitive-active.png` | observation boundary and lattice over an operationally active run | `obs=interval:3,stride:2` |
| `53-dynamic-address-attempt.png` | an Address reassignment (A2 to 11,6 at tick 100) on the research map | `address=reassign@100:A2:11,6` |
| `54-route-topology.png` | route topology of the M2-mediated MFS run | `mfs=MFS-F14-2&tech=ncb` |
| `55-mfs-comparison.png` | the two F14 MFS side by side | `mfs=MFS-F14-1` (research tab) |
| `56-replay-transition-inspection.png` | the research tab at a controlled run: markers and the inspection at the transition | `route=adaptive:renewal disabled` |
| `57-technical-view-alternate-route.png` | technical view with the fixed fallback route, the failed history path and the MFS lines | `route=fixed:history lost&tech=ncb` |
| `58-rejected-candidate-route.png` | route topology of MFS-F8-1 with the **rejected candidate** (dotted, "not MFS") | `mfs=MFS-F8-1&tech=ncb` |
| `59-current-alternative-mfs-map.png` | the research map with current MFS, validated alternative and the rejected-candidate row | `mfs=MFS-F14-1&layer=mfs.current,...` |

Limits of these images: (a) the replay-marker click inspection (tick, source/target MFS, trigger, cost, states) is a click and cannot be written in a URL; the capture shows the research pane at that tick, and the click behaviour is covered by tests; (b) the route graph reads enable/disable operations,
so a parameter stress such as 'renewal disabled' shows as an intervention marker, not as a failed component.