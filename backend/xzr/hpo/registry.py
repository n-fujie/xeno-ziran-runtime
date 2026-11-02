"""Philosophical Operational Registry.

One entry per operational series. An entry records where the series comes from (primary sources and whether they
were consulted), what the implementation does instead (minimal operational shape, conditions, rules, observables),
and when the proxy is to be judged a failure or revised. The *kind* identifiers used by the code are operational
(``withdrawal``, ``transduction`` …); the philosopher names appear only here, as provenance.

Source status vocabulary (field ``sources[].status``):

    bibliographic   the work is cited from the implementer's bibliographic knowledge; its text was NOT consulted while
                    implementing this proxy (no copy of the text was available in the implementation environment)
    consulted       the text was read for this implementation (none so far)

``central_claim`` is a paraphrase written by the implementer, not a quotation, and has not been checked against the
text. Every entry states ``fidelity: "engineering proxy"``: running it says nothing about whether the doctrine is true,
coherent or adequately represented.

The registry is data, and it is not closed: the field can create kinds at run time (couplings produce composite kinds
such as ``assemblage∘closure``; reclassification moves an operation to another kind), and those kinds are recorded in
the run's own registry snapshot with their lineage — they are not added here.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

FIDELITY = "engineering proxy"
SOURCE_NOTE = ("Primary texts were not available in the implementation environment; works are cited bibliographically "
               "and central claims are implementer paraphrases, unchecked against the texts.")

ENTRIES: list[dict[str, Any]] = [
    {
        "kind": "withdrawal",
        "series": "Graham Harman — Object-Oriented Ontology (OOO)",
        "sources": [
            {"work": "Tool-Being: Heidegger and the Metaphysics of Objects", "year": 2002, "status": "bibliographic"},
            {"work": "Guerrilla Metaphysics", "year": 2005, "status": "bibliographic"},
            {"work": "The Quadruple Object", "year": 2011, "status": "bibliographic"},
        ],
        "central_claim": "Objects are never exhausted by their relations: their reality withdraws from every access, and "
                         "objects affect one another only indirectly (vicariously), through sensual profiles.",
        "minimal_shape": "a cluster whose boundary permeability is reduced (withdrawal) and whose interior becomes "
                         "unobservable to other operations' instruments, plus one mediated connection (vicar)",
        "configuration_conditions": ["a cluster with a boundary (region at the hierarchy's local level)",
                                     "an instrument with the boundary_flow channel at the region's resolution"],
        "ignition": "observed flow across the region boundary (contact) above a threshold for `persist` samples",
        "rule": "gate the region's boundary connections by `depth`; veil the region (opacity 1 − depth) for every "
                "instrument outside it; once per activation open one vicarious connection from the most active "
                "outside neighbour cluster to the region",
        "coupling": "a veil is a change of everyone's observation conditions; any operation whose instrument loses "
                    "its target behind the veil records `boundary_invisible`",
        "split": "none (an object does not divide in this proxy)",
        "cessation": "observed contact below half the threshold for `cease_after` samples, or the region's boundary "
                     "can no longer be observed by its own instrument",
        "reignition": "contact rises again, possibly under another configuration (e.g. after a veil elsewhere lifts)",
        "observables": ["boundary gate factor", "veil opacity", "vicarious connections", "ignition/cessation times"],
        "history_reinsertion": "its veil history (when and where) is written to the external memory and can be "
                               "re-inserted as a veil at a later step",
        "real_effects": "runtime gates on boundary connections; new connections (vicars)",
        "approximation": "'withdrawal' is reduced to permeability and observability; real vs sensual qualities are "
                         "reduced to true state vs instrument output. The ontological claim (inexhaustibility) has no "
                         "counterpart that a simulation could exhibit.",
        "failure": "the veil has no downstream effect (others' observations/ignitions unchanged) — the proxy then "
                   "does nothing a plain gate does not do",
        "revision": "if withdrawal is better modelled as a property of every relation rather than a regional operation, "
                    "the proxy must be replaced (not tuned)",
    },
    {
        "kind": "transduction",
        "series": "Gilbert Simondon — Individuation / Transduction",
        "sources": [
            {"work": "L'individuation à la lumière des notions de forme et d'information (thesis 1958; complete ed. "
                     "2005; Eng. tr. 2020)", "year": 1958, "status": "bibliographic"},
            {"work": "Du mode d'existence des objets techniques", "year": 1958, "status": "bibliographic"},
        ],
        "central_claim": "Individuals result from the individuation of a metastable pre-individual field; transduction "
                         "is the operation by which a structure propagates domain by domain, each structured region "
                         "serving as the principle of structuring the next; the individual comes with an associated "
                         "milieu.",
        "minimal_shape": "a growing domain inside a metastable field: frontier clusters adjacent to the domain are "
                         "structured (thresholds scaled) step by step; the rest of the parent cluster is the milieu",
        "configuration_conditions": ["metastability: share of configurations near threshold (tension channel)",
                                     "connections from the domain to its frontier"],
        "ignition": "observed tension in the milieu above a threshold while activity is present",
        "rule": "structure up to `step_clusters` frontier clusters per act (threshold factor `factor`); the domain is "
                "the union of structured clusters",
        "coupling": "a large individuated domain can be adopted as a system region by a closure operation, or "
                    "plugged into an assemblage",
        "split": "when the domain exceeds `split_size` configurations the operation divides into two, each with half "
                 "of the domain (by address) and a perturbed factor",
        "cessation": "tension in the milieu below half the threshold for `cease_after` samples (metastability "
                     "exhausted); the structuring already done persists",
        "reignition": "tension rebuilds, or an archived datum re-seeds a domain elsewhere",
        "observables": ["domain size", "splits", "threshold factors", "milieu tension"],
        "history_reinsertion": "reads archived data (if shared): a re-seed at the archived location",
        "real_effects": "runtime threshold scaling over the domain",
        "approximation": "metastability is reduced to closeness to an ignition threshold; information as "
                         "'disparation' and the pre-individual are not represented",
        "failure": "domains grow regardless of tension (ignition condition not doing work) or never split",
        "revision": "replace the frontier rule if propagation is better modelled as change of the milieu itself",
    },
    {
        "kind": "concrescence",
        "series": "Alfred North Whitehead — Process / Concrescence",
        "sources": [
            {"work": "Process and Reality", "year": 1929, "status": "bibliographic"},
            {"work": "Science and the Modern World", "year": 1925, "status": "bibliographic"},
            {"work": "Adventures of Ideas", "year": 1933, "status": "bibliographic"},
        ],
        "central_claim": "The actual world is a process of actual occasions; each occasion concresces by prehending "
                         "prior occasions into one satisfaction, then perishes and becomes a datum for later occasions "
                         "(objective immortality).",
        "minimal_shape": "an occasion collects observations of several clusters (prehensions) for `span` samples, "
                         "integrates them into one datum (satisfaction), perishes, and deposits the datum in the "
                         "external memory and as retained history (memory) in the most prehended clusters",
        "configuration_conditions": ["an activity channel over several clusters (nexus)", "an external memory"],
        "ignition": "contrast: the spread of observed activity across the nexus above a threshold",
        "rule": "after `span` samples: datum = weighted activity profile; deposit `alpha`·datum as memory into the "
                "top `deposit_clusters` clusters; archive the datum",
        "coupling": "its archived data can be read by operations that share history (prehension by others)",
        "split": "none; each occasion is new (the operation is a series of occasions)",
        "cessation": "no contrast for `cease_after` samples",
        "reignition": "new contrast (creative advance) — or a re-inserted datum that restores contrast",
        "observables": ["occasions completed", "deposits", "archive entries"],
        "history_reinsertion": "its deposits are history reinsertion by construction",
        "real_effects": "runtime memory (lowers effective thresholds)",
        "approximation": "prehension is reduced to sampling observations; subjective form, eternal objects and "
                         "God's role are absent",
        "failure": "deposits never change later ignitions (data not re-entering)",
        "revision": "replace the occasion/series model if occasions should overlap or nest",
    },
    {
        "kind": "picturing",
        "series": "Wilfrid Sellars — Picturing / Scientific Revision",
        "sources": [
            {"work": "Empiricism and the Philosophy of Mind", "year": 1956, "status": "bibliographic"},
            {"work": "Philosophy and the Scientific Image of Man", "year": 1962, "status": "bibliographic"},
            {"work": "Science and Metaphysics: Variations on Kantian Themes (ch. V)", "year": 1968,
             "status": "bibliographic"},
        ],
        "central_claim": "Representational systems can picture the world as a matter of natural-order correspondence, "
                         "distinct from semantic truth; pictures are improvable, and the scientific image can revise "
                         "the categories of the manifest image.",
        "minimal_shape": "a per-cluster predictive picture of observed activity, corrected by its error, revised "
                         "(finer categories = finer instrument resolution) when error persists, and used to act "
                         "(thresholds raised where overload is predicted)",
        "configuration_conditions": ["an activity channel", "a representational store (the picture)",
                                     "optional: a symbol channel — only when the configuration flag "
                                     "`picturing_requires_symbol_channel` is set (language-like layer as an "
                                     "experimental condition, not a general requirement)"],
        "ignition": "prediction error above `tolerance` for `persist` samples",
        "rule": "correct the picture (rate `rate`); after `revise_after` erroneous samples revise categories (instrument "
                "resolution one level finer, if any); raise thresholds by `damp` where predicted activity is high",
        "coupling": "a revision propagates to operations that share its instrument (shared observation conditions)",
        "split": "none",
        "cessation": "its channel unobservable for `cease_after` samples (it cannot picture what it cannot observe)",
        "reignition": "the channel becomes observable again (e.g. a veil lifts, a channel is restored)",
        "observables": ["prediction error", "revisions", "correction latency", "damping acts"],
        "history_reinsertion": "reads archived data (if shared) as prior for the picture",
        "real_effects": "runtime threshold scaling where overload is predicted",
        "approximation": "picturing is reduced to predictive tracking; its normative/semantic distinction and the "
                         "manifest/scientific images are reduced to resolution levels. Prediction error is NOT a "
                         "measure of the doctrine's adequacy.",
        "failure": "revision never reduces error, or acts are independent of the picture",
        "revision": "replace if picturing should be second-order (pictures of picturing) or non-predictive",
    },
    {
        "kind": "assemblage",
        "series": "Gilles Deleuze & Félix Guattari — Machinic Assemblages",
        "sources": [
            {"work": "Anti-Oedipus (Capitalism and Schizophrenia I)", "year": 1972, "status": "bibliographic"},
            {"work": "A Thousand Plateaus (Capitalism and Schizophrenia II)", "year": 1980, "status": "bibliographic"},
        ],
        "central_claim": "Assemblages connect heterogeneous components through couplings of flows and cuts; they are "
                         "stabilised (territorialised) and destabilised (deterritorialised) along lines of flight.",
        "minimal_shape": "components in two or more macro clusters; territorialisation adds connections among them "
                         "and opens their gates; when flow is observed blocked, a line of flight severs internal "
                         "connections and connects to a further macro cluster",
        "configuration_conditions": ["flows observable across macro clusters (boundary_flow at macro level)",
                                     "a connection budget (institution)"],
        "ignition": "observed cross-cluster flow among its components above a threshold",
        "rule": "territorialise: up to `links` new connections between components, gate ×`open`; deterritorialise "
                "when observed flow drops below `blocked`·previous: sever up to `links` internal connections, connect "
                "to the most active macro cluster not yet a component",
        "coupling": "plugs into another operation whose region it reaches (composite kind)",
        "split": "a composite it formed splits when co-activation stops",
        "cessation": "component activity below `low` for `cease_after` samples",
        "reignition": "flows return",
        "observables": ["components", "territorialisations", "lines of flight", "couplings"],
        "history_reinsertion": "none of its own; affected by re-inserted veils (blocked flows)",
        "real_effects": "runtime connections created/severed, gates",
        "approximation": "desire, coding/decoding and the abstract machine are absent; flows are runtime "
                         "penetrations",
        "failure": "lines of flight never triggered by blocked flows, or couplings never change the coupled partner",
        "revision": "replace if assemblage should be the field's default (everything an assemblage) rather than a "
                    "series among others",
    },
    {
        "kind": "closure",
        "series": "Niklas Luhmann — Operational Closure / Autopoiesis",
        "sources": [
            {"work": "Soziale Systeme (Social Systems)", "year": 1984, "status": "bibliographic"},
            {"work": "Die Gesellschaft der Gesellschaft (Theory of Society)", "year": 1997, "status": "bibliographic"},
            {"work": "Maturana & Varela, Autopoiesis and Cognition", "year": 1980, "status": "bibliographic"},
        ],
        "central_claim": "Systems reproduce their elements through their own operations (operational closure, "
                         "autopoiesis); the environment does not instruct but only irritates them through structural "
                         "couplings, and they draw their own system/environment distinction.",
        "minimal_shape": "a cluster whose incoming boundary is closed except for a few coupling connections, which "
                         "re-injects difference into itself when its own activity falls, and which changes its own "
                         "thresholds when irritation accumulates",
        "configuration_conditions": ["internal recursion observable (recursion channel)",
                                     "a resource budget (self-reproduction costs)"],
        "ignition": "observed share of region ignitions caused by internal connections above `recursion`",
        "rule": "close incoming boundary (gate `closure`) except the `coupling` strongest observed channels; veil the "
                "region; re-inject `reproduce` when internal activity < `low`; on irritation > `irritation`, scale "
                "own thresholds by `adapt` (self-adjustment)",
        "coupling": "its veil changes others' observations; actions of other operations into its region are "
                    "filtered to its coupling connections (others' execution rules change); it can adopt an "
                    "individuated domain as its system",
        "split": "none",
        "cessation": "autopoiesis fails: internal activity zero for `cease_after` samples (closure is dissolved)",
        "reignition": "internal recursion rises again",
        "observables": ["closure gates", "re-injections", "irritations", "self-adjustments"],
        "history_reinsertion": "none of its own",
        "real_effects": "runtime gates, injections, threshold scaling",
        "approximation": "communication/meaning and the system's own observation of its distinction are reduced to "
                         "connection recursion and gates",
        "failure": "closure never filters others' acts, or irritation never triggers self-adjustment",
        "revision": "replace if closure must be defined by operation type rather than by region",
    },
]

CANDIDATES = [
    {"series": n, "status": "not implemented (extension candidate)"} for n in (
        "G. W. F. Hegel", "G. W. Leibniz", "B. Spinoza", "I. Kant", "C. S. Peirce", "K. Marx", "H. Bergson",
        "M. Foucault", "R. Brandom", "R. Brassier", "P. Sacilotto", "K. Barad", "R. Negarestani", "B. Latour",
        "F. Varela", "K. Friston")
]

KINDS = tuple(e["kind"] for e in ENTRIES)


def entry(kind: str) -> dict:
    for e in ENTRIES:
        if e["kind"] == kind:
            return e
    raise KeyError(kind)


def snapshot() -> dict:
    """The registry as published with results (entries + candidates + notes)."""
    return {"fidelity": FIDELITY, "source_note": SOURCE_NOTE,
            "entries": [{**deepcopy(e), "fidelity": FIDELITY} for e in ENTRIES], "candidates": deepcopy(CANDIDATES)}
