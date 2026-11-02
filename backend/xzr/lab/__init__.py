"""XENO–ZIRAN 3D laboratory layer: runtime-driven apparatus state, recording and independent replay.

The scientific runtime (xzr/runtime, operated by the HPO field) stays the only source of scientific state
transitions. This layer:

    apparatus.py  derives the state of 3D apparatuses (chambers, containment shutters, inter-chamber conduits) as a
                  pure function of the runtime state — the renderer draws these values and nothing else
    record.py     runs an experiment headless, records per-step runtime fingerprints, apparatus states and
                  apparatus events with their runtime provenance (schema xzr.labrun/1)
    replay.py     re-executes a record from its configuration alone and checks agreement step by step

Rendering never feeds back: a run with rendering disabled is the run.
"""
