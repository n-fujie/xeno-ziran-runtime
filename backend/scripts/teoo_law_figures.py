"""Research figures of the AI-law ledger integration (R16). Run: PYTHONPATH=. python scripts/teoo_law_figures.py [OUT_DIR]

Concept figures draw the specification (CONCEPTUAL: a drawing, not data); result figures plot the saved results of the LAW experiments (SYNTHETIC; experiment id, protocol version, seeds and conditions are in the metadata). None is a photograph or a screenshot
of the application (the screenshots are separate files), and none reproduces the wording of the unpublished sources. The twelve duties and the fifteen guarantees are drawn in mheg_fig1..4 and legal_fig1; this set adds the governance principles,
the receipt-evidence-review sequence, the measurement history, the evidence scopes, the model against the sensor, closure against restoration, the comparators and the negative results."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from xzr.teoo import export as EX
from xzr.teoo import lawworld as W_
from xzr.teoo import mheg as M
from xzr.teoo.provenance import Kind, Provenance, seal

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lf", HERE / "teoo_legal_figures.py")
lf = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(lf)  # type: ignore[union-attr]
AT, EVD, CREATOR = lf.AT, lf.EV, {"name": "teoo.law-figures/1", "role": "generator"}


def concept(what: str) -> list[dict]:
    return [seal({"concept": what, "note": "the manuscripts R5-R16 and the historical code were not available; this is the specification of this implementation"}, provenance=Provenance.CONCEPTUAL, kind=Kind.REFERENCE_STATE, creator=CREATOR,
                 source={"kind": "researcher", "description": "a drawing of the specification of the AI-law ledger of this implementation", "declared_by": "teoo.law-figures"}, created_at=AT)]


def demo_record(what: str) -> list[dict]:
    return [seal({"demonstration": what, "seed": 3}, provenance=Provenance.SYNTHETIC, kind=Kind.OBSERVATION, creator=CREATOR, source={"kind": "generator", "description": "the deterministic demonstration run of the AI-law ledger on a synthetic case (xzr.teoo.lawbundle.demo)",
                                                                                                                        "declared_by": "teoo.law-figures"}, created_at=AT)]


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else EVD / "law_figures")
    out.mkdir(parents=True, exist_ok=True)

    def fig(name: str, kind: str, title: str, data: dict, recs: list[dict], protocol: dict | None, observation: str) -> None:
        obs = {"version": None, "t": None, "summary": {"conditions": observation}, "claim_note": "A synthetic ledger or a drawing: what lies outside what is stated here is unknown, not absent."}
        f = EX.build_figure(kind, title, data, recs, generated_at=AT, protocol=protocol, observation=obs)
        assert EX.verify_svg(f["svg"]) == [], name
        (out / f"{name}.svg").write_text(f["svg"])
        (out / f"{name}.metadata.json").write_text(f["metadata_json"])
        print(name, len(f["svg"]) // 1024, "KB")

    def proto(d: dict) -> dict:
        p = d["protocol"]
        return {"experiment_id": p["experiment_id"], "version": d["protocol_version"], "seeds": [p["seeds"][0], p["seeds"][-1]], "conditions": p["conditions"], "trials_per_condition": p["trials_per_condition"]}

    D = lambda k: lf.doc(k, "law")  # noqa: E731
    gp = M.GOVERNANCE_PRINCIPLES
    # ---- 3 governance principles (R16 section 7) and the August version
    it = gp["items"]

    def wrap(t: str, n: int = 27) -> list[str]:
        lines, cur = [], ""
        for w in t.split():
            if cur and len(cur) + 1 + len(w) > n:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        return (lines + [cur])[:4]

    boxes = [{"id": f"p{i}", "x": 10 + (i % 5) * 158, "y": 40 + (i // 5) * 64, "w": 150, "h": 58, "label": x["id"] + " " + wrap(x["name"])[0], "sub": wrap(x["name"])[1:], "fill": "#3f3a26" if x["ordinal_similarity"] < 1 else "#1c2230"} for i, x in enumerate(it)]
    boxes.append({"id": "n", "x": 10, "y": 240, "w": 790, "h": 60, "label": "R16 section 7: fifteen principles as supplied (amber: functionally different from the ordinal guarantee: P5, P10, P15). Kept apart from the guarantees by function, never by number.", "sub": ["The August Recursive Double Audit version has a different fifteenth (audit of the auditor); kept as a separate historical version, not merged.", "Titles as supplied; R16 itself was not available; verification against the source: not done."], "fill": "#2a2208"})
    fig("law_fig3_governance_principles", "diagram", "Fig R3 · Fifteen governance principles (R16 section 7), as supplied",
        {"title": "a separate series: functional comparison with the guarantees and the duties is in law_fig11", "boxes": boxes, "arrows": [], "note": f"CONCEPTUAL; status {gp['status']}; source not available"}, concept("governance principles registry"), None, "specification")
    # ---- 4 receipt-evidence-review sequence
    seq = [("submission receipt", "claim id, sequence, SHA-256", "R"), ("evidence finding", "container validated; E state", "E"), ("human review", "reviewer role; evidence version", "P"), ("proposed measure", "plan on an evidence version", "plan"),
           ("approval", "current evidence; reviews done", "plan"), ("execution", "another actor; world revision", "plan"), ("downstream observation", "model vs sensor; immutable", "M"), ("closure", "administrative only", "C"), ("material restoration", "never verified here", "X")]
    boxes = [{"id": f"s{i}", "x": 8 + (i % 5) * 158, "y": 44 + (i // 5) * 92, "w": 150, "h": 78, "label": f"{i + 1}. {a}", "sub": [b], "fill": "#3a2a26" if k == "X" else "#1c2230"} for i, (a, b, k) in enumerate(seq)]
    boxes.append({"id": "r", "x": 8, "y": 240, "w": 790, "h": 54, "label": "Receipt first: the claim is recorded before its evidence is validated. Each box is a separate record; none implies the next. A corrupt container, a resend or an overflow never removes the receipt (I9-I11).", "sub": [], "fill": "#2a2208"})
    fig("law_fig4_receipt_evidence_review_sequence", "diagram", "Fig R4 · Receipt, evidence, review, plan, execution, observation, closure, restoration",
        {"title": "the independent records of one case (R10-R13, R16)", "boxes": boxes, "arrows": [{"from": f"s{i}", "to": f"s{i + 1}"} for i in range(8) if (i + 1) % 5], "note": "CONCEPTUAL drawing; the ledger's tables are append-only"}, concept("receipt to restoration sequence"), None, "specification")
    # ---- 5 immutable measurement history (a result of the demo run)
    from xzr.teoo import lawbundle as LB
    dm = LB.demo(3)["case"]
    rows = []
    for m in dm["measurements"]:
        rows.append([m["measure_id"].split("/")[1], m["mode"], f"{m['model']}/{m['sensor']}", "DISAGREE" if m["mismatch"] else "match", " → ".join(h["status"] for h in m["status_history"])])
    fig("law_fig5_immutable_measurement_history", "table", "Fig R5 · Immutable measurements and their status events (a demonstration run)",
        {"title": "payloads are never edited; validity changes only by appended status events (STALE_EVIDENCE, STALE_WORLD, HISTORICAL)", "header": ["measure", "mode", "model/sensor", "result", "status events"], "xs": [14, 80, 190, 300, 400], "rows": rows, "colors": [(i, 3, "#ff8a70") for i, r in enumerate(rows) if r[3] == "DISAGREE"]},
        demo_record("measurement history of the demonstration"), None, "deterministic demonstration on a synthetic case")
    # ---- 6 evidence scope revision (LAW-L3)
    d3, u3 = D("LAW-L3"), lf.units("LAW-L3", "law")
    rs = [r for x in u3 for r in x["rows"]]
    sc = ("ACCESS", "METADATA", "UNKNOWN")
    fig("law_fig6_evidence_scope_revision", "bars", "Fig R6 · Scope of an evidence revision against what happens to an earlier observation (LAW-L3)",
        {"title": "share of earlier observations invalidated, by scope of the later revision (30 worlds); the scenario stipulates whether access is truly affected", "ylabel": "share of cases", "groups": list(sc),
         "series": [{"name": "invalidated by the ledger", "values": [float(sum(r["ledger_invalid"] for r in rs if r["scope"] == s)) / max(1, sum(r["scope"] == s for r in rs)) for s in sc]},
                    {"name": "access truly affected (stipulated)", "values": [float(sum(r["affects"] for r in rs if r["scope"] == s)) / max(1, sum(r["scope"] == s for r in rs)) for s in sc]}],
         "note": f"scope-aware: 0 missed, {d3['results']['L303']['scope_aware_needless_total']} needless (UNKNOWN is conservative); always invalidate: {d3['results']['L303']['always_needless_total']} needless; never invalidate: {d3['results']['L303']['never_missed_total']} missed"},
        lf.result_record("law", ["LAW-L3"]), proto(d3), "synthetic ledger; scopes are set by the experimenter")
    # ---- 7 model against sensor (LAW-L4)
    d4 = D("LAW-L4")
    pc = d4["results"]["L401"]["per_condition"]
    conds = list(pc)
    fig("law_fig7_model_vs_sensor", "bars", "Fig R7 · Model against synthetic sensor over 256 states and 6 conditions (LAW-L4; this implementation's world)",
        {"title": "access granted (of 256) by the model and by the sensor, and the disagreements (cause seen by EXPANDED shown in the note)", "ylabel": "states of 256", "groups": conds,
         "series": [{"name": "model", "values": [float(pc[c]["model_access"]) for c in conds]}, {"name": "sensor", "values": [float(pc[c]["sensor_access"]) for c in conds]}, {"name": "disagreements", "values": [float(pc[c]["disagreements"]) for c in conds]}],
         "note": f"EXPANDED sees q in {pc['EXEC_GATE']['cause_identified_expanded']} of {pc['EXEC_GATE']['disagreements']} (gate) and {pc['EXEC_LINKED']['cause_identified_expanded']} of {pc['EXEC_LINKED']['disagreements']} (linked); the manuscript's counts are not reproduced"},
        lf.result_record("law", ["LAW-L4"]), proto(d4), "256 states x 6 conditions = 1,536 comparisons")
    # ---- 8 administrative closure against legal restoration (LAW-L5, L6)
    d5, d6 = D("LAW-L5"), D("LAW-L6")
    r5, r6 = d5["results"]["L501"], d6["results"]["L601"]
    fig("law_fig8_closure_vs_restoration", "bars", "Fig R8 · Administrative closure against legal determination and restoration (LAW-L5, LAW-L6)",
        {"title": "720 scenarios: closures reached, and what no closure produced", "ylabel": "scenarios", "groups": ["closed: conflict kept", "closed: model match (not verified)", "access changed (synthetic)", "legal determination by software", "restoration verified", "positive law verified"],
         "series": [{"name": "scenarios", "values": [float(r5["closed_with_conflict"]), float(r5["closed_with_match"]), float(r6["access_changed_in_the_synthetic_world"]), float(r6["determination_by_software"]), float(r6["restoration_verified"]), float(r6["positive_law_verified"])]}],
         "note": f"a single SUCCESS state would hide {r5['conflicts_hidden_by_success_variant']} conflicts and call {r6['relief_misclassified_by_collapse']} unverified outcomes relief; the six records stay separate"},
        lf.result_record("law", ["LAW-L5", "LAW-L6"]), proto(d5), "720 scenarios (30 worlds x 24)")
    # ---- 9 equal-information comparators (LAW-L7)
    d7 = D("LAW-L7")
    allag = json.loads(json.dumps(lf.units("LAW-L7", "law")))
    DES = ("A_boolean_state_machine", "B_event_sourcing", "C_causal_model", "D_fixed_policy", "E_adaptive_policy")
    Q = ("access", "mismatch", "cause_identified", "current_valid", "history_answerable", "open_proceedings", "closure")
    rows7 = [r for u in allag for r in u["rows"]]
    nr = []
    for d in DES:
        row = [d.split("_", 1)[0] + " " + d.split("_", 1)[1].replace("_", " ")]
        for q in Q:
            ans = [r[d][q] for r in rows7 if not (d in DES[2:] and q in ("current_valid", "open_proceedings", "closure"))]
            row.append("n/a" if not ans else f"{sum(a == r['F'][q] for a, r in zip(ans, [r for r in rows7 if not (d in DES[2:] and q in ('current_valid', 'open_proceedings', 'closure'))], strict=True)) / len(ans):.2f}")
        nr.append(row)
    fig("law_fig9_equal_information_comparators", "table", "Fig R9 · Equal-information comparators: agreement with the ledger on seven queries (LAW-L7)",
        {"title": "agreement with the ledger per query (1.00 = identical in every scenario; n/a = cannot answer)", "header": ["design"] + [q.replace("_", " ").replace("identified", "ident.").replace("answerable", "answ.").replace("proceedings", "procs") for q in Q], "xs": [14, 160, 215, 270, 345, 410, 515, 625], "rows": nr, "colors": []},
        lf.result_record("law", ["LAW-L7"]), proto(d7), "348 scenarios (30 worlds); the same inputs and the same policy")
    # ---- 10 negative results
    neg = []
    for k, a, why in (("LAW-L4", "L403", "an ordinary Boolean model with the same information agrees on 1,536 / 1,536: no predictive advantage"), ("LAW-L7", "L701", "event sourcing with the same fields agrees with the ledger on every query"),
                      ("LAW-L7", "L704", "the causal model with the same policy agrees on access, disagreement and cause"), ("LAW-L6", "L603", "only two presence patterns in the scenario suite (criterion of three not met)"),
                      ("LAW-L4", "L402", "EXPANDED leaves some disagreements unexplained (q is not their cause)")):
        d = D(k)
        r = d["results"][a]
        neg.append([a, k, d["evidence_class"].replace(" Result", ""), r.get("registered_class", "").split(" (")[0], why[:70]])
    fig("law_fig10_negative_results", "table", "Fig R10 · Negative and unmet results kept (AI-law ledger)",
        {"title": "the ledger improves traceability, not prediction; nothing here is removed or re-labelled; earlier negative results stay in legal_fig7 and mheg_fig7", "header": ["analysis", "experiment", "class", "registered", "what was found"], "xs": [14, 70, 150, 255, 345], "rows": neg, "colors": []},
        lf.result_record("law", ["LAW-L4", "LAW-L6", "LAW-L7"]), None, "see each experiment")
    # ---- 11 principle crosswalk by function (EXP-R16-09)
    d9 = lf.doc("EXP-R16-09", "r16")
    cwx = M.PRINCIPLE_CROSSWALK
    rows9 = []
    for pid, v in cwx.items():
        diff = v["differences_from_ordinal"]
        why = ", ".join(diff["only_in_first"] + diff["only_in_second"]) or ("near: " + "; ".join(n["principle"] for n in diff["near"]) if diff["near"] else "identical functions")
        rows9.append([pid, v["ordinal_counterpart"], f"{v['ordinal_similarity']:.2f}", "same" if v["ordinal_title_identical"] else "differs", ", ".join(v["close_duties"]) or "none", why[:40]])
    fig("law_fig11_principles_crosswalk_by_function", "table", "Fig R11 · Fifteen principles against the guarantees and the twelve duties, by protected function (EXP-R16-09)",
        {"title": "function against the ordinal guarantee, title, covering duties, difference (analytic reading; unverified)", "header": ["principle", "guarantee", "function", "title", "duties", "difference"],
         "xs": [14, 80, 150, 215, 280, 400], "rows": rows9, "colors": [(i, 2, "#c9a227") for i, r in enumerate(rows9) if r[2] != "1.00"]}, lf.result_record("r16", ["EXP-R16-09"]), proto(d9), "specification analysis; profiles are an analytic reading")
    # ---- 12 the world built to the stated aggregates (EXP-R16-04)
    d4b = lf.doc("EXP-R16-04", "r16")
    pc2 = d4b["results"]["R401"]
    conds2 = list(W_.CONDITIONS)
    fig("law_fig12_stated_aggregates_world", "bars", "Fig R12 · The independent verification model built to the stated R16 aggregates (EXP-R16-04)",
        {"title": "model and sensor access of 256 states and the disagreements under six conditions; equal to the stated numbers by construction", "ylabel": "states of 256", "groups": conds2,
         "series": [{"name": "model", "values": [float(x) for x in pc2["model_access"]]}, {"name": "sensor", "values": [float(x) for x in pc2["sensor_access"]]}, {"name": "disagreements", "values": [float(pc2["disagreements"][c]) for c in conds2]}],
         "note": "not a reproduction: the manuscript's world was not available; an ordinary Boolean model agrees on 1,536 / 1,536 here too"}, lf.result_record("r16", ["EXP-R16-04"]), proto(d4b), "256 states x 6 conditions = 1,536 comparisons")
    # ---- 13 comparators on both worlds incl. the evidence-scoped revision model (EXP-R16-08)
    d8 = lf.doc("EXP-R16-08", "r16")
    u8 = lf.units("EXP-R16-08", "r16")
    DES8 = ("A_boolean_state_machine", "B_event_sourcing", "R_evidence_scoped_revision", "C_causal_model", "D_fixed_policy", "E_adaptive_policy")
    Q8 = ("access", "mismatch", "cause_identified", "current_valid", "history_answerable", "open_proceedings", "closure")
    nr8 = []
    for world in ("own", "r16_stated_aggregates"):
        rws = [r for u in u8 for r in u["worlds"][world]]
        for d in DES8:
            row = [("own" if world == "own" else "stated") + " " + d.split("_", 1)[0]]
            for q in Q8:
                if d in DES8[3:] and q in ("current_valid", "open_proceedings", "closure"):
                    row.append("n/a")
                else:
                    row.append(f"{sum(r[d][q] == r['F'][q] for r in rws) / len(rws):.2f}")
            nr8.append(row)
    fig("law_fig13_comparators_on_both_worlds", "table", "Fig R13 · Equal-information comparators on both worlds, with the evidence-scoped revision model (EXP-R16-08)",
        {"title": "agreement with the ledger per query (A B R C D E: see EXP-R16-08)", "header": ["design"] + [q.replace("_", " ").replace("identified", "ident.").replace("answerable", "answ.").replace("proceedings", "procs") for q in Q8],
         "xs": [14, 150, 205, 260, 335, 400, 505, 615], "rows": nr8, "colors": []}, lf.result_record("r16", ["EXP-R16-08"]), proto(d8), "the same events, scope, policy and world")
    (out / "law_figures_index.json").write_text(json.dumps({"figures": sorted(p.name for p in out.glob("law_fig*.svg")), "concept_figures": ["law_fig3", "law_fig4", "law_fig5"], "result_figures": ["law_fig6", "law_fig7", "law_fig8", "law_fig9", "law_fig10", "law_fig11", "law_fig12", "law_fig13"],
                                                           "earlier_figures_kept": ["mheg_fig1 twelve-duty architecture", "mheg_fig2 guarantees seen from the duties", "mheg_fig3 twelve-to-fifteen crosswalk", "legal_fig1 fifteen guarantees", "legal_fig2 legal translation chain", "legal_fig7 and mheg_fig7 negative results"]}, indent=1))


if __name__ == "__main__":
    main()
