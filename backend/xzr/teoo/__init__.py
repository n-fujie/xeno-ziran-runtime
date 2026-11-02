"""TEOO (Total Embodied Operational Observation): an implementation label for an open body-observation architecture, not a theory.

What this package is: a way to hold *records about bodies* (any bodies: human, artificial, non-human, distributed) so that what was measured, what was
generated, what was estimated and what was only drawn are never confused; so that what was not observed is told apart from what does not exist; and so that
a body is a declared, versioned graph and not a fixed skeleton. Layers kept apart in every record:

    provenance   MEASURED / SYNTHETIC / RECONSTRUCTED_ESTIMATE / CONCEPTUAL        (where the data come from; sealed, digest-protected, never rewritten)
    kind         REFERENCE_STATE / OBSERVATION / ESTIMATE / RECONSTRUCTION         (what the record is; a separate axis from provenance)
    status       MEASURED_VALID / UNMEASURED / ... / UNKNOWN_CAUSE                  (per sample: why a value is or is not there)

What it is not: a physiological model, a medical device, a claim about any real body, or a confirmation of any philosophical theory. SYNTHETIC records are
functional-test data. The digests protect integrity (a change is detected); they do not prevent an adversary who can rewrite everything from recomputing them
(see ``provenance.PROTECTIONS`` for what is and is not implemented).

Layering: this package imports nothing else from ``xzr`` (checked by tests/test_teoo_layering.py); only the service imports it.
"""

TEOO_VERSION = "teoo/0.1"
