"""The Brassier Machine as a verification mechanism of P/A SYSTEM.

What it is: a ledger that takes the evidence of a run (observations, interventions, model comparisons, with seeds and provenance) and manages what stands behind an ONTOLOGICAL CLAIM: SUPPORTED, WITHHELD or WITHDRAWN, each with the evidence for it and the conditions under which it would be withdrawn. It holds NO authority over what is real: no function here returns 'true', 'real' or 'exists', and every verdict record says ``authority: none``. It adds no ontological principle; the seven checks below implement the functions named in the integration directive, and their mapping onto the historical six filters and the S/W division of the earlier Brassier Machine work (R35, R37) is NOT verified, because those documents are not in this repository.

The seven checks (each returns a result of its own; none is a score and none is combined into one):

* independence                  is the claim supported by anything other than the model that states it? (a claim whose only evidence is the model's own output is flagged)
* source_fidelity               does the claim reproduce the stated source of an outside theory? (a registered claim-to-source mapping; without a source the check is NOT_APPLICABLE)
* world_warrant                 do observations or interventions made on the system support the claim? (counts supporting, contradicting and inconclusive evidence; negative results are kept, never dropped)
* interventional_identification can the competing mechanisms be told apart by an intervention, and which one? (``identify``)
* equivalence                   do different mechanisms produce the same observations under the protocol in force? (``identify``)
* revision                      what would change if an instrument, variable or state space were revised? (the conditions are recorded, not decided)
* withdrawal                    a claim that can no longer be supported is WITHDRAWN or WITHHELD with its reason; the record stays

World Model Verification (``identify``): two or more candidate mechanisms are run through the observation protocol in force; if their observations agree within a tolerance they are recorded as EQUIVALENT; then a list of discriminating protocols (more sensors, an intervention, a longer window) is tried, and if one of them separates them the result is IDENTIFIED BY that protocol, otherwise **OPEN**. The generating mechanism of a synthetic world is never given to the verifier: ``identify`` receives only functions from a protocol to observations (a test checks that its signature carries no mechanism label).

Acceptance conditions of the directive, as tested (``tests/test_verification.py``): (1) the existing results are not changed (``with_brassier`` returns the base results object untouched); (2) unresolved equivalence returns OPEN; (3) the ledger sits beside a standard model comparison (AIC and Bayesian information criterion on the same observations) and the two are reported side by side; (4) the ledger keeps negative results, seeds, intervention conditions and provenance in a digest-sealed record. Removing, disabling and reintroducing the machine is a call argument (``enabled``), so that the comparison with and without it is a function call.

No claim is made that carrying the machine improves on standard methods: the demonstration cases show only that it records an equivalence that the standard comparison does not."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

AUTHORITY = "none: this record is an evidence ledger, not a determination of what is real"
VERDICTS = ("SUPPORTED", "WITHHELD", "WITHDRAWN")
ENGINE = "brassier/1"

Protocol = dict[str, Any]  # {"name": str, "interventions": [..], "sensors": [..], "window": int, "seeds": [..]}
Observer = Callable[[Protocol], np.ndarray]  # a candidate mechanism seen only through what it produces under a protocol


@dataclass
class Evidence:
    """One item behind a claim. ``outcome`` is 'supports', 'contradicts' or 'inconclusive'; negative results are kept."""

    id: str
    outcome: str
    source: str  # 'model_output' | 'observation' | 'intervention' | 'comparison' | 'literature'
    protocol: Protocol | None = None
    seeds: list[int] = field(default_factory=list)
    provenance: str = ""  # a record path, a digest, a citation: where this can be re-found
    note: str = ""


@dataclass
class Claim:
    id: str
    text: str
    kind: str = "ontological"
    source_theory: str | None = None  # the outside theory the claim restates, if any
    source_passage: str | None = None  # the passage it is held to correspond to
    evidence: list[Evidence] = field(default_factory=list)
    revision_conditions: list[str] = field(default_factory=list)
    withdrawal_conditions: list[str] = field(default_factory=list)


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def check_independence(c: Claim) -> dict[str, Any]:
    kinds = {e.source for e in c.evidence}
    own = {"model_output"}
    independent = kinds - own
    return {"check": "independence", "result": "INDEPENDENT_EVIDENCE" if independent else ("MODEL_ONLY" if kinds else "NO_EVIDENCE"), "evidence_sources": sorted(kinds), "note": "a claim supported only by the output of the model that states it is flagged, not refuted"}


def check_source_fidelity(c: Claim) -> dict[str, Any]:
    if not c.source_theory:
        return {"check": "source_fidelity", "result": "NOT_APPLICABLE", "note": "no outside theory is registered for this claim"}
    ok = bool(c.source_passage)
    return {"check": "source_fidelity", "result": "MAPPED" if ok else "UNMAPPED", "source_theory": c.source_theory, "source_passage": c.source_passage, "note": "records that a passage is registered; it does not judge the reading"}


def check_world_warrant(c: Claim) -> dict[str, Any]:
    world = [e for e in c.evidence if e.source in ("observation", "intervention")]
    count = {o: sum(e.outcome == o for e in world) for o in ("supports", "contradicts", "inconclusive")}
    if not world:
        res = "NO_WORLD_EVIDENCE"
    elif count["contradicts"] and count["contradicts"] >= count["supports"]:
        res = "CONTRADICTED"
    elif count["supports"] > count["contradicts"]:
        res = "SUPPORTED_BY_WORLD_EVIDENCE"
    else:
        res = "INCONCLUSIVE"
    return {"check": "world_warrant", "result": res, "counts": count, "negative_results_kept": [e.id for e in world if e.outcome == "contradicts"]}


def check_revision(c: Claim) -> dict[str, Any]:
    return {"check": "revision", "result": "CONDITIONS_RECORDED" if c.revision_conditions else "NO_CONDITIONS_RECORDED", "conditions": list(c.revision_conditions), "note": "which revision of an instrument, variable or state space would reopen the claim; recorded, not decided"}


def check_withdrawal(c: Claim, world: dict[str, Any], independence: dict[str, Any], identification: dict[str, Any] | None) -> dict[str, Any]:
    reasons = []
    if world["result"] == "CONTRADICTED":
        reasons.append("world evidence contradicts the claim")
    if independence["result"] == "MODEL_ONLY":
        reasons.append("only the stating model's own output stands behind the claim")
    if identification and identification["result"] == "OPEN":
        reasons.append("equivalent mechanisms are not told apart by any protocol tried")
    return {"check": "withdrawal", "reasons": reasons, "withdrawal_conditions": list(c.withdrawal_conditions)}


def verdict_for(c: Claim, identification: dict[str, Any] | None = None) -> dict[str, Any]:
    """The ledger entry of one claim. SUPPORTED needs world evidence, independent of the stating model, with no unresolved equivalence;
    WITHDRAWN when the world evidence contradicts it; otherwise WITHHELD. Nothing here says the claim is true."""
    ind, src, world, rev = check_independence(c), check_source_fidelity(c), check_world_warrant(c), check_revision(c)
    wd = check_withdrawal(c, world, ind, identification)
    if world["result"] == "CONTRADICTED":
        v = "WITHDRAWN"
    elif world["result"] == "SUPPORTED_BY_WORLD_EVIDENCE" and ind["result"] == "INDEPENDENT_EVIDENCE" and not (identification and identification["result"] == "OPEN"):
        v = "SUPPORTED"
    else:
        v = "WITHHELD"
    entry = {"claim": c.id, "text": c.text, "verdict": v, "authority": AUTHORITY, "checks": {"independence": ind, "source_fidelity": src, "world_warrant": world, "revision": rev, "withdrawal": wd}, "identification": identification,
             "evidence": [{"id": e.id, "outcome": e.outcome, "source": e.source, "protocol": e.protocol, "seeds": e.seeds, "provenance": e.provenance, "note": e.note} for e in c.evidence]}
    entry["digest"] = _sha({k: v for k, v in entry.items() if k != "digest"})
    return entry


def identify(mechanisms: dict[str, Observer], base: Protocol, discriminating: Sequence[Protocol], tol: float = 1e-6) -> dict[str, Any]:
    """Equivalence and interventional identification among candidate mechanisms, seen only through ``Observer`` functions.

    The label of a mechanism is the verifier's own name for a candidate; it carries no information about which one generated the data (the observers are all that is passed). Returns EQUIVALENT_UNDER_BASE plus, for each discriminating protocol tried, whether it separates every pair by more than ``tol`` (RMS difference of the observations); the result is IDENTIFIED (by the first protocol that separates all pairs), PARTLY_IDENTIFIED, DISTINGUISHABLE_UNDER_BASE or OPEN."""
    names = sorted(mechanisms)

    def gaps(p: Protocol) -> dict[str, float]:
        obs = {n: np.asarray(mechanisms[n](p), dtype=float) for n in names}
        return {f"{a}|{b}": float(np.sqrt(np.mean((obs[a] - obs[b]) ** 2))) for i, a in enumerate(names) for b in names[i + 1:]}

    g0 = gaps(base)
    equivalent_pairs = [k for k, v in g0.items() if v <= tol]
    tried: list[dict[str, Any]] = []
    for p in discriminating:
        g = gaps(p)
        tried.append({"protocol": p, "gaps": g, "separates_all_equivalent_pairs": all(g[k] > tol for k in equivalent_pairs)})
    if not equivalent_pairs:
        res = "DISTINGUISHABLE_UNDER_BASE"
        by = None
    else:
        sep = next((t for t in tried if t["separates_all_equivalent_pairs"]), None)
        if sep:
            res, by = "IDENTIFIED", sep["protocol"].get("name")
        elif any(any(t["gaps"][k] > tol for k in equivalent_pairs) for t in tried):
            res, by = "PARTLY_IDENTIFIED", None
        else:
            res, by = "OPEN", None
    return {"check": "equivalence+interventional_identification", "result": res, "base_protocol": base, "gaps_under_base": g0, "equivalent_pairs_under_base": equivalent_pairs, "protocols_tried": tried, "identified_by": by, "tolerance": tol,
            "note": "OPEN means no protocol tried separated the equivalent mechanisms; it is not a statement that they are the same"}


def standard_comparison(data: np.ndarray, predictions: dict[str, np.ndarray], n_params: dict[str, int]) -> dict[str, Any]:
    """The ordinary model comparison on the same observations: Gaussian AIC and BIC per model (lower is better). It is reported beside the ledger, not replaced by it."""
    y = np.asarray(data, dtype=float)
    n = len(y)
    out: dict[str, Any] = {}
    for m, pred in predictions.items():
        rss = float(np.sum((y - np.asarray(pred, dtype=float)) ** 2))
        s2 = max(rss / n, 1e-12)
        k = n_params.get(m, 1)
        ll = -0.5 * n * (np.log(2 * np.pi * s2) + 1)
        out[m] = {"AIC": float(2 * k - 2 * ll), "BIC": float(k * np.log(n) - 2 * ll), "rss": rss, "k": k}
    best = min(out, key=lambda m: out[m]["AIC"])
    return {"criterion": "Gaussian AIC / BIC", "models": out, "preferred_by_AIC": best}


def with_brassier(base_results: Any, claims: Sequence[Claim], identifications: dict[str, dict[str, Any]] | None = None, enabled: bool = True) -> dict[str, Any]:
    """Run the machine beside an existing result. ``base_results`` is returned as the SAME object, unread and unmodified (condition 1); with ``enabled=False`` the ledger is empty, which is the comparison without the machine."""
    ledger = [verdict_for(c, (identifications or {}).get(c.id)) for c in claims] if enabled else []
    rec = {"engine": ENGINE, "enabled": enabled, "authority": AUTHORITY, "ledger": ledger}
    rec["digest"] = _sha(rec)
    return {"results": base_results, "brassier": rec}


def verify_record(rec: dict[str, Any]) -> bool:
    """True when the record's digest, and the digest of every ledger entry, match their content (the seal has not been broken)."""
    body = {k: v for k, v in rec.items() if k != "digest"}
    if _sha(body) != rec.get("digest"):
        return False
    return all(_sha({k: v for k, v in e.items() if k != "digest"}) == e.get("digest") for e in rec.get("ledger", []))
