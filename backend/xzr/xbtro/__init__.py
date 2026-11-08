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

RELEASE = {
    "name": "XenoBody — Operational-Shape Robotics Simulator",
    "channel": "Research Beta",
    # What was checked on which platform. A platform that was not checked says so; nothing is implied for it.
    "platforms": {
        "local_server_http": "checked (same-condition runs identical to the browser edition at the recorded resolution)",
        "browser_pyodide": "checked (WebAssembly, no threads; same-condition runs identical to the local server at the recorded resolution)",
        "ios_device": "NOT checked: the embedded engine is the same code as the native bridge, but no iOS device was available; no behaviour is guaranteed on iOS",
    },
    "statements": [
        (
            "purpose",
            "A research environment for running, observing, intervening on and re-entering the operations of a simplified planar body model "
            "(a human-like and a machine-like preset), and for studying how the observation configuration changes what can be identified.",
        ),
        (
            "scope",
            "The body is a limited planar model with nominal parameters. Values are not measured physiology and not the properties of any particular robot. "
            "Results describe these simulated models under the stated protocols only.",
        ),
        (
            "real-world validation",
            "None. No physical robot and no human participant was used; nothing here has been validated against a real body.",
        ),
        (
            "Xeno-14",
            "The fourteen principles are experimental conditions taken from the existing specification. Each is marked translated, partly translated or "
            "proxy-only for this planar body; a proxy-only condition says nothing about the principle itself. No effect is assumed in advance.",
        ),
        (
            "Ziran System",
            "MO, DO, ZCA and MS appear as limited instances over this body model, with their definitions quoted from the specification. In the "
            "specification's own status MO and MS are NOT IMPLEMENTED and DO and ZCA are PARTIAL; nothing here completes them.",
        ),
        (
            "results",
            "Positive, negative and null results are kept. 'Not detected' is not 'absent', and a statistical difference is not a philosophical conclusion.",
        ),
    ],
}
