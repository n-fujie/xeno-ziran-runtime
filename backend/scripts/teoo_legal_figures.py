"""Research figures of the AI legal governance work. Run: PYTHONPATH=. python scripts/teoo_legal_figures.py [OUT_DIR]

Two kinds, kept apart in the file name, the metadata and the watermark: *concept* figures draw a structure stated in the sources (V3.0, R2) or in the specification of this implementation (evidence class CONCEPTUAL: a drawing, not data);
*result* figures plot saved results (evidence class SYNTHETIC: results about a synthetic institution; the experiment id, the protocol version, the seeds and the implementation version are in the metadata). Neither is a photograph or a
screenshot of the application; the screenshots are separate files."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np

from xzr.teoo import export as EX
from xzr.teoo import legal as L
from xzr.teoo.provenance import Kind, Provenance, digest_of, seal

AT = "2026-11-01T00:00:00.000000Z"
ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "docs" / "teoo_evidence"
CREATOR = {"name": "teoo.legal-figures/1", "role": "generator"}


def units(name: str, d: str = "legal_source_v1") -> list[dict]:
    with gzip.open(EV / d / f"{name}_units.json.gz", "rt") as f:
        return json.load(f)


def doc(name: str, d: str = "legal_source_v1") -> dict:
    return json.loads((EV / d / f"{name}.json").read_text())


def result_record(dirname: str, ids: list[str]) -> list[dict]:
    recs = []
    for i in ids:
        d = doc(i, dirname)
        recs.append(seal({"experiment": d["experiment_id"], "protocol_version": d["protocol_version"], "protocol_digest": d["protocol_digest"], "results_digest": digest_of(d["results"]), "units": d["units"]}, provenance=Provenance.SYNTHETIC, kind=Kind.OBSERVATION,
                         creator=CREATOR, source={"kind": "generator", "description": f"{d['experiment_id']} on the synthetic institution (xzr.teoo.legal{'' if dirname == 'legal_source_v1' else '_v1'})", "declared_by": "teoo.legal-figures"}, created_at=AT))
    return recs


def concept_record(what: str) -> list[dict]:
    return [seal({"concept": what, "sources": {k: v["sha256"] for k, v in L.CANON["sources"].items()}}, provenance=Provenance.CONCEPTUAL, kind=Kind.REFERENCE_STATE, creator=CREATOR,
                 source={"kind": "researcher", "description": "a drawing of a structure stated in the sources V3.0, 100_POINT_EDITION and R2 (positions cited in legal_guarantees.json)", "declared_by": "teoo.legal-figures"}, created_at=AT)]


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else EV / "legal_figures")
    out.mkdir(parents=True, exist_ok=True)

    def fig(name: str, kind: str, title: str, data: dict, recs: list[dict], protocol: dict | None, observation: str) -> None:
        obs = {"version": None, "t": None, "summary": {"conditions": observation}, "claim_note": "A synthetic institution or a drawing: what lies outside what is stated here is unknown, not absent."}
        f = EX.build_figure(kind, title, data, recs, generated_at=AT, protocol=protocol, observation=obs)
        assert EX.verify_svg(f["svg"]) == [], name
        (out / f"{name}.svg").write_text(f["svg"])
        (out / f"{name}.metadata.json").write_text(f["metadata_json"])
        print(name, len(f["svg"]) // 1024, "KB")

    def proto(d: dict) -> dict:
        p = d["protocol"]
        return {"experiment_id": p["experiment_id"], "version": d["protocol_version"], "seeds": [p["seeds"][0], p["seeds"][-1]], "conditions": p["conditions"], "trials_per_condition": p["trials_per_condition"]}

    # ---- concept 1: the fifteen guarantees, in the five stages of V3.0 7.1, with the transversal principle and the sub-findings
    stages = [("status", "G1–G2", ["G1 subject recognition", "G2 non-degradation"]), ("visibility", "G3–G5", ["G3 notice", "G4 current score", "G5 history, scope, recipients"]),
              ("authority, translation", "G6–G9", ["G6 legal source", "G7 variable translation", "G8 fact · inference · score", "G9 individual reasons"]),
              ("operational return", "G10–G13", ["G10 correction", "G11 contestation", "G12A burden · G12B reviewer", "G13 suspension"]), ("openness and re-entry", "G14–G15", ["G14 reversible treatment", "G15A resources", "G15B correction, restoration", "G15C re-entry", "G15D mutual audit"])]
    boxes = [{"id": f"s{i}", "x": 14 + i * 156, "y": 40, "w": 150, "h": 84, "label": f"{n} ({r})", "sub": subs, "fill": "#1c2230"} for i, (n, r, subs) in enumerate(stages)]
    boxes.append({"id": "u", "x": 14, "y": 136, "w": 770, "h": 34, "label": "U — Low-Score Subject Guarantee Principle: transversal over all fifteen; a separate finding (V3.0 §6.1, §7.3, A.9)", "sub": [], "fill": "#2a2208"})
    boxes.append({"id": "n", "x": 14, "y": 180, "w": 770, "h": 34, "label": "Conjunctive and non-fungible: one finding each; no total, average, rank or weighted score (V3.0 §8, A.3)", "sub": [], "fill": "#1c2230"})
    fig("legal_fig1_fifteen_guarantees_architecture", "diagram", "Fig L1 · The fifteen guarantees: architecture as the source states it (V3.0 §7.1)",
        {"title": "five stages of institutional translation, one transversal rule, one finding per guarantee", "boxes": boxes, "arrows": [{"from": f"s{i}", "to": f"s{i + 1}"} for i in range(4)], "note": "a drawing of the source structure (CONCEPTUAL), not data; titles abbreviated"}, concept_record("fifteen guarantees architecture"), None, "source structure")
    # ---- concept 2: the legal translation chain (R2 §15, §24) with its layers and the two examples
    chain = L.example_chain(True)
    layers = {"technical": "#2b3550", "asserted": "#3a3550", "legal": "#35503a", "authorised decision": "#50453a", "review": "#503a45", "remedy": "#3a5050"}
    boxes = [{"id": f"c{i}", "x": 10 + (i % 6) * 130, "y": 40 + (i // 6) * 100, "w": 122, "h": 62, "label": s["stage"].replace("_", " "), "sub": [s["layer"], "basis · jurisdiction · version", "actor · uncertainty · route"], "fill": layers[s["layer"]]} for i, s in enumerate(chain)]
    boxes.append({"id": "v", "x": 10, "y": 250, "w": 780, "h": 44, "label": "A machine prediction is neither a legal fact nor an authorised decision (R2 §15).", "sub": ["A stage without legal basis, jurisdiction and rule version is not a valid legal step; an AI output is not a decision;", "unclear law is an unresolved legal question for a competent reviewer, not a silent assumption."], "fill": "#2a2208"})
    fig("legal_fig2_legal_translation_chain", "diagram", "Fig L2 · Legal translation chain: eleven typed stages in six layers (R2 §15, §24)",
        {"title": "technical event → data representation → asserted fact → classification → norm → exception → attribution → burden → decision → review → remedy", "boxes": boxes,
         "arrows": [{"from": f"c{i}", "to": f"c{i + 1}"} for i in range(10) if (i + 1) % 6], "note": "layers are never merged; the engine recommends and records, it does not authorise (CONCEPTUAL drawing of the specification)"}, concept_record("legal translation chain"), None, "specification")
    # ---- result 3: Low-Score Subject Guarantee (LG2-EXP-02)
    u2 = units("LG2-EXP-02")
    d2 = doc("LG2-EXP-02")
    fig("legal_fig3_low_score_subject_guarantee", "bars", "Fig L3 · Low-score subject guarantee: review rates, the conventional fairness gap, and the finding U (LG2-EXP-02)",
        {"title": "wrongfully denied qualified people: share reviewed, by score group; and the true-positive-rate gap (30 worlds)", "ylabel": "share / gap", "groups": ["control", "score-conditioned review"],
         "series": [{"name": "reviewed, high-score", "values": [float(np.mean([x["arms"][a]["review_rate_high"] for x in u2])) for a in ("control", "degraded")]}, {"name": "reviewed, low-score", "values": [float(np.mean([x["arms"][a]["review_rate_low"] for x in u2])) for a in ("control", "degraded")]},
                    {"name": "true-positive-rate gap", "values": [float(np.mean([x["arms"][a]["tpr_gap"] for x in u2])) for a in ("control", "degraded")]}],
         "note": f"U raised in {d2['results']['L202a']['detection']:.0%} of degraded worlds, {d2['results']['L202a']['false_rate']:.0%} of controls; the true-positive gap does not register it (equivalence within 0.03)"},
        result_record("legal_source_v1", ["LG2-EXP-02"]), proto(d2), "synthetic institution; 300 people, 24 periods; review reach of low-score people ×0.4 in the degraded arm")
    # ---- result 4: contestability (LG2-EXP-03)
    u3, d3 = units("LG2-EXP-03"), doc("LG2-EXP-03")
    combos = [(a, i, c) for a in (False, True) for i in (False, True) for c in (False, True)]
    lab = lambda a, i, c: ("authority " if a else "no authority ") + ("· independent " if i else "· not independent ") + ("· high capacity" if c else "· low capacity")  # noqa: E731
    fig("legal_fig4_contestability_and_institutional_return", "bars", "Fig L4 · Contestability: the formal route against the effective one (LG2-EXP-03)",
        {"title": "share of wrongful denials appealed and overturned, by authority, independence and capacity of the review (30 worlds; burden pooled)", "ylabel": "share of wrongful denials", "groups": [lab(*c).replace(" · ", "\n").split("\n")[0] + "/" + ("ind" if c[1] else "dep") + "/" + ("cap" if c[2] else "low") for c in combos],
         "series": [{"name": "appealed", "values": [float(np.mean([a["formal_appeal_rate"] for x in u3 for a in x["arms"].values() if (a["authority"], a["independent"], a["capacity"]) == c])) for c in combos]},
                    {"name": "overturned", "values": [float(np.mean([a["overturn_rate_of_wrongful"] for x in u3 for a in x["arms"].values() if (a["authority"], a["independent"], a["capacity"]) == c])) for c in combos]}],
         "note": "without authority nothing is overturned however many appeals are filed: G11 is ABSENT (hard failure) in all 240 such arms with appeals filed"}, result_record("legal_source_v1", ["LG2-EXP-03"]), proto(d3), "16 configurations per world; 300 people, 24 periods")
    # ---- result 5: material restoration (LG2-EXP-04)
    u4, d4 = units("LG2-EXP-04"), doc("LG2-EXP-04")
    arms4 = ["appeal_only", "plus_propagation", "plus_material_relief", "plus_reentry_support", "plus_resources_support"]
    fig("legal_fig5_material_restoration", "bars", "Fig L5 · Material restoration: correction, propagation, relief, re-entry, resources (LG2-EXP-04)",
        {"title": "downstream access of the qualified, and their mean resources (30 worlds); G15B state under each arm: " + " / ".join(sorted({u4[0]["arms"][a]["G15B"] for a in arms4})), "ylabel": "downstream access / resources", "groups": [a.replace("plus_", "+ ") for a in arms4],
         "series": [{"name": "downstream access", "values": [float(np.mean([x["arms"][a]["downstream_access_qualified"] for x in u4])) for a in arms4]}, {"name": "mean resources", "values": [float(np.mean([x["arms"][a]["mean_resources_qualified"] for x in u4])) for a in arms4]}],
         "note": f"re-entry support did not add re-entering persons significantly (p_Holm {d4['results']['L204c']['p_holm']:.2f}); G15B is SECURED only with propagation and relief"}, result_record("legal_source_v1", ["LG2-EXP-04"]), proto(d4), "review delay 3 periods; 300 people, 24 periods")
    # ---- result 6: governance intervention comparison (first implementation, EXP-10 and CMP-01)
    d10, dc = doc("EXP-10", "legal"), doc("CMP-01", "legal")
    arms10 = list(json.loads(json.dumps(d10["protocol"]["conditions"])))
    u10 = units("EXP-10", "legal")
    fig("legal_fig6_governance_intervention_comparison", "bars", "Fig L6 · Governance reconfiguration and planners (EXP-10, CMP-01; first implementation)",
        {"title": "EXP-10: exclusion of the qualified and burden on the subject by review arrangement; CMP-01: exclusion after the plan of each planner (below)", "ylabel": "exclusion / burden", "groups": [a.replace("_", " ")[:34] for a in arms10],
         "series": [{"name": "exclusion of the qualified", "values": [float(np.mean([x["arms"][a]["exclusion_qualified"] for x in u10])) for a in arms10]}, {"name": "burden on the subject", "values": [float(np.mean([x["arms"][a]["burden_subject"] for x in u10])) for a in arms10]}],
         "note": "CMP-01 planners, exclusion: " + ", ".join(f"{k.split('_')[0]} {v['exclusion_mean']:.3f}" for k, v in dc["arms"].items() if k != "oracle_best_executable") + f"; baseline {dc['base_exclusion_mean']:.3f}"[:200]},
        result_record("legal", ["EXP-10", "CMP-01"]), proto(d10), "first implementation (legal_v1): provisional catalogue; kept as run")
    # ---- result 7: negative results
    neg = []
    for ev, k, label in (("legal_source_v1", "LG2-EXP-01", "L201e"), ("legal_source_v1", "LG2-EXP-04", "L204c"), ("legal_source_v1", "LG2-EXP-07", "L207a"), ("legal_source_v1", "LG2-EXP-07", "L207b"), ("legal", "CMP-01", "L11a"), ("legal", "CMP-01", "L11e"), ("legal", "CMP-01", "L11f"),
                         ("legal", "EXP-07", "L07b"), ("legal", "EXP-07", "L07c"), ("legal", "EXP-08", "L08c"), ("legal", "EXP-05", "L05a")):
        r = doc(k, ev)["results"][label]
        neg.append([label, k, doc(k, ev)["evidence_class"].replace(" Result", ""), r.get("registered_class", "").split(" (")[0],
                    {"L201e": f"U sensitivity {r.get('sensitivity', 0):.2f} among degraded: the test is blind where reviews are few", "L204c": f"re-entry support: p_Holm {r.get('p_holm', 0):.2f}", "L207a": "25 of 121 degraded still reported SECURED with min_cases = 30",
                     "L207b": f"detection when performed {r.get('detection_when_performed', 0):.2f} (< 0.95)", "L11a": f"revision rule vs random field: p {r.get('p', 0):.2f}", "L11e": "vs constrained planning on the initial observation: not significant", "L11f": "greedy model-based planner nominally better",
                     "L07b": "outcome-responsive revision vs equal-cost static: p = 1.0", "L07c": "vs pre-specified revision: p = 1.0", "L08c": f"how convincing vs what it does: rho {r.get('mean_rho', 0):.2f}", "L05a": f"correction without propagation: change {r.get('mean_diff', 0):.3f} (negligible)"}[label]])
    fig("legal_fig7_negative_results", "table", "Fig L7 · Negative and weak results kept (legal governance experiments)",
        {"title": "results that did not support the expectation, or whose effect is negligible; none removed or re-labelled", "header": ["analysis", "experiment", "class", "registered", "what was found"], "xs": [14, 70, 150, 255, 345], "rows": neg, "colors": []},
        result_record("legal_source_v1", ["LG2-EXP-01", "LG2-EXP-04", "LG2-EXP-07"]) + result_record("legal", ["CMP-01", "EXP-07", "EXP-08", "EXP-05"]), None, "see each experiment")
    # ---- concept 8: operational-shape legal architecture: R2's six modules and what exists in this repository
    mods = [("legal-source registry", "Translation Register (legal.RegisterEntry): variable, authority, purpose, proxy, threshold, loss", "partial"), ("transformation ledger", "assess_chain: eleven typed stages, six layers", "implemented"),
            ("guarantee evaluator", "legal.audit: G1–G15, G12/G15 sub-findings, U, taxonomy", "implemented"), ("contestation and burden manager", "simulate: appeal, authority, independence, burden; G11, G12A/B", "model only"),
            ("correction and restoration tracker", "simulate: propagation, relief, re-entry; G10, G15B/C", "model only"), ("intervention simulator with time-indexed observation", "TEOO observation, revision, protocols + legal.simulate", "implemented (synthetic)")]
    colors = {"implemented": "#2f4a3a", "implemented (synthetic)": "#2f4a3a", "partial": "#4a432f", "model only": "#4a3a2f"}
    boxes = [{"id": f"m{i}", "x": 10 + (i % 3) * 262, "y": 40 + (i // 3) * 92, "w": 254, "h": 78, "label": f"{n} — {st}", "sub": [t[:58], t[58:116]], "fill": colors[st]} for i, (n, t, st) in enumerate(mods)]
    boxes.append({"id": "x", "x": 10, "y": 232, "w": 774, "h": 58, "label": "Not implemented: authorisation by a competent actor; jurisdiction-specific legal sources; real data; independent evaluation (R2 §26).", "sub": ["The software recommends and records; it cannot self-authorise a legal remedy (R2 §18)."], "fill": "#2a2208"})
    fig("legal_fig8_operational_shape_legal_architecture", "diagram", "Fig L8 · Operational-shape legal architecture: R2's six modules and what this repository implements",
        {"title": "R2 §5 specification mapped to code (green: implemented on a synthetic institution; amber: partial or a model of the function only)", "boxes": boxes, "arrows": [], "note": "CONCEPTUAL drawing of a specification against the code, not data"}, concept_record("operational-shape legal architecture"), None, "specification against code")
    (out / "legal_figures_index.json").write_text(json.dumps({"figures": sorted(p.name for p in out.glob("legal_fig*.svg")), "concept_figures": ["legal_fig1", "legal_fig2", "legal_fig8"], "result_figures": ["legal_fig3", "legal_fig4", "legal_fig5", "legal_fig6", "legal_fig7"]}, indent=1))


if __name__ == "__main__":
    main()
