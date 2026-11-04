"""GAISHO - Operational Shape Laboratory (a research function of the existing XENO ZIRAN runtime, not a separate application).

What this package does: it runs SYNTHETIC computational experiments on candidate operations, intervenes on their conditions, records what differs, and builds shapes only from the differences that were identified.
What it does not do: it does not decide that a Gaisho exists. The five levels (real operation, operational shape, conceptual operational shape, Gaisho operational shape, Gaisho attribution) are kept as separate records with
their own evidence states; the attribution is never computed from the operational results (``model.attribute``), and the inferences the research forbids are refused by ``model.refuse``.

Source of the definitions: the distinctions of the five levels, the twelve questions about a candidate and the verdict classes are those of the development brief of this laboratory. The manuscript "GAISHO R37" was searched for
(file names and text, every repository and folder on this machine) and **was not found**; nothing in this package is taken from it, and no part of it is completed from memory.
SYNTHETIC only: no human neural activity, no real institution and no real person is represented.
"""

MODEL_VERSION = "gaisho-lab/1"
