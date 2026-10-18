"""XenoBody / Total Relational Observation (XB-TRO).

A research module of the simulator: a simplified, dynamic, planar body configuration whose operations (musculoskeletal
mechanics, sensing, neural lines, internal coordination, environment) are separate *operation lines* with their own time
scale, ignition condition, resource dependence and observability; local observation models that cut the body differently;
and an engine that studies how changing the observation configuration changes what is identifiable, what stays unobserved,
which couplings and transitions can be reconstructed, how fast operations take hold, and how improving one operation can
weaken another (Fragility Transfer).

What this is not
* The body is a limited model (planar, four links, nominal parameters). Nothing here is measured human physiology and no
  value is presented as such.
* The simulator's internal state is the *model reference state*. It is not an observation of a real body, and nothing in
  this package treats it as one. Observation models produce separate outputs.
* "EEG-like", "EMG-like" and the other observation models are simple signal models of what the simulated lines do; they
  claim nothing about the physiology of EEG or EMG.
* Xeno-14 principles are experimental conditions, never universal laws; no sign of effect is assumed in advance.

Pure numpy, deterministic given seeds, no I/O: it runs unchanged on the desktop, in the server, in the iOS app and in the
browser (Pyodide). It imports nothing else from ``xzr`` (checked by tests/test_layering.py).
"""

MODEL_VERSION = "xb-tro/1.0"
