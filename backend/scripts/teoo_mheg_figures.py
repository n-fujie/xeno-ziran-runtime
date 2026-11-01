"""Research figures of the MHEG duties x fifteen guarantees integration. Run: PYTHONPATH=. python scripts/teoo_mheg_figures.py [OUT_DIR]

Concept figures draw the specification (the registry of the twelve duties, the crosswalk as reported, the nine-stage chain: CONCEPTUAL, a drawing, not data); result figures plot the saved results of MH-EXP-01..04 (SYNTHETIC). Neither is a
photograph or a screenshot of the application. The guarantees' wording is not reproduced: the figures carry names, structure and this implementation's own words only. The earlier figures (legal_fig1 fifteen guarantees, legal_fig2 legal
translation chain, legal_fig4/5 contestation and restoration, legal_fig6 governance comparison, legal_fig7 negative results) stay as they are."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from xzr.teoo import export as EX
from xzr.teoo import mheg as M
from xzr.teoo.provenance import Kind, Provenance, seal

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lf", HERE / "teoo_legal_figures.py")
lf = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(lf)  # type: ignore[union-attr]
AT, EVD, CREATOR = lf.AT, lf.EV, {"name": "teoo.mheg-figures/1", "role": "generator"}


def concept(what: str) -> list[dict]:
    return [seal({"concept": what, "crosswalk": "as reported from the later correspondence table (R16); not available to this implementation", "duties": "functional summaries, not definitions"}, provenance=Provenance.CONCEPTUAL, kind=Kind.REFERENCE_STATE,
                 creator=CREATOR, source={"kind": "researcher", "description": "a drawing of the specification of this implementation (duty registry, crosswalk as reported, nine-stage chain)", "declared_by": "teoo.mheg-figures"}, created_at=AT)]


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else EVD / "mheg_figures")
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

    cw = M.crosswalk_matrix()
    # ---- concept 1: the twelve duties, grouped by what they give the person, with the kind of their mapping
    groups = [("what the person can see", ["M1", "M2", "M5", "M8"]), ("legitimacy and translation", ["M3", "M4", "M7"]), ("return and contest", ["M6", "M9", "M10", "M11"]), ("restoration", ["M12"])]
    fillc = {"direct": "#26402f", "composite": "#3f3a26", "broad": "#44302a"}
    d_by = {d["id"]: d for d in M.DUTIES}
    boxes = []
    for r, (gname, ids) in enumerate(groups):
        boxes.append({"id": f"g{r}", "x": 10, "y": 40 + r * 62, "w": 120, "h": 54, "label": gname, "sub": [], "fill": "#1c2230"})
        for c, i in enumerate(ids):
            d = d_by[i]
            boxes.append({"id": i, "x": 140 + c * 162, "y": 40 + r * 62, "w": 156, "h": 54, "label": f"{i} {d['name']}"[:30], "sub": [f"→ {d['crosswalk_as_reported']} ({d['mapping_kind']})"[:36]], "fill": fillc[d["mapping_kind"]]})
    boxes.append({"id": "n", "x": 10, "y": 272, "w": 780, "h": 34, "label": "The twelve duties are a registry of their own: not retired, not replaced by the fifteen guarantees; the correspondence is functional (green: one guarantee; amber: 2-4; red: broad).", "sub": [], "fill": "#2a2208"})
    fig("mheg_fig1_twelve_duty_architecture", "diagram", "Fig M1 · MHEG twelve duties: registry and the kind of each mapping",
        {"title": "M1-M12 grouped by what they give the person; each box shows its reported crosswalk and whether it maps one, a few or many guarantees", "boxes": boxes, "arrows": [], "note": "CONCEPTUAL drawing; grouping is this figure's, the names and crosswalk are as reported; definitions are functional summaries"},
        concept("twelve-duty architecture"), None, "specification")
    # ---- concept 2: how many duties name each finding (the fifteen guarantees seen from the duties)
    fig("mheg_fig2_guarantees_seen_from_the_duties", "bars", "Fig M2 · The fifteen guarantees (19 findings) seen from the twelve duties: how many duties name each",
        {"title": "G1 is named by no duty; G2, G3, G4, G5, G10 and G13 by one; G8 and G12B by four", "ylabel": "duties naming the finding", "groups": cw["findings"], "series": [{"name": "duties naming it", "values": [float(cw["duties_per_finding"][f]) for f in cw["findings"]]}],
         "note": "from the crosswalk as reported; the guarantees reformulate the protected functions and add a principle of recognition (G1), so a finding no duty names is not an error of the table"}, concept("duties per finding"), None, "specification")
    # ---- concept 3: the crosswalk matrix
    hdr = ["duty"] + cw["findings"]
    xs = [14] + [66 + 37 * j for j in range(len(cw["findings"]))]
    rows, colors = [], []
    for i, dd in enumerate(M.DUTIES):
        rows.append([dd["id"]] + ["●" if cw["matrix"][dd["id"]][j] else "·" for j in range(len(cw["findings"]))])
        colors += [(i, 1 + j, {"direct": "#78e696", "composite": "#c9a227", "broad": "#ff8a70"}[dd["mapping_kind"]]) for j in range(len(cw["findings"])) if cw["matrix"][dd["id"]][j]]
    rows.append(["#"] + [str(cw["duties_per_finding"][f]) for f in cw["findings"]])
    fig("mheg_fig3_twelve_to_fifteen_crosswalk", "table", "Fig M3 · Twelve-to-fifteen functional crosswalk (as reported)",
        {"title": "duties (rows) x findings (columns); ● maps; colour = the duty's mapping kind (green one finding, amber 2-4, red broad); last row: duties naming each finding", "header": hdr, "xs": xs, "rows": rows, "colors": colors},
        concept("crosswalk matrix"), None, "specification")
    # ---- concept 4: the nine-stage legal transformation chain
    boxes = [{"id": c[0], "x": 8 + (i % 5) * 158, "y": 44 + (i // 5) * 110, "w": 150, "h": 92, "label": f"{i + 1}. {c[1]}", "sub": [", ".join(c[4]), c[2][:36], c[2][36:72]], "fill": "#1c2230"} for i, c in enumerate(M.CHAIN)]
    boxes.append({"id": "r", "x": 8, "y": 262, "w": 782, "h": 52, "label": "A stage is read from its findings; a prediction that succeeds does not establish a stage; a failed stage is not offset by a later one; information lost in translation is kept.", "sub": ["Which finding sits in which stage is this implementation's assignment (each of the 19 findings in exactly one stage)."], "fill": "#2a2208"})
    fig("mheg_fig4_legal_transformation_chain", "diagram", "Fig M4 · Legal transformation chain: nine stages from legal source to material restoration",
        {"title": "Legal Source → Translation → Data Representation → Classification → Institutional Treatment → Effective Access → Contestation → Revision → Material Restoration", "boxes": boxes, "arrows": [{"from": M.CHAIN[i][0], "to": M.CHAIN[i + 1][0]} for i in range(8) if (i + 1) % 5],
         "note": "CONCEPTUAL drawing of the specification; the assignment of findings to stages is this implementation's"}, concept("nine-stage transformation chain"), None, "specification")
    # ---- result 5: MH-EXP-01 information lost in the projection
    d1, u1 = lf.doc("MH-EXP-01", "mheg"), lf.units("MH-EXP-01", "mheg")
    sing = u1[0]["single"]
    r1 = d1["results"]["M101"]
    fig("mheg_fig5_information_lost_in_the_duty_view", "bars", "Fig M5 · What the duty view cannot tell apart (MH-EXP-01)",
        {"title": "190 removal patterns (19 single + 171 pair) are all distinct as findings; as duty signatures they collapse", "ylabel": "distinct patterns", "groups": ["19 single removals", "190 single + pair removals"],
         "series": [{"name": "as findings", "values": [19.0, 190.0]}, {"name": "as duty signatures", "values": [float(len({tuple(v) for v in sing.values()})), float(r1["distinct_duty_signatures_among_190"])]}],
         "note": "not told apart: " + "; ".join("/".join(g) for g in r1["single_collision_groups"]) + "; G1 changes no duty; 0 non-compensation violations"},
        lf.result_record("mheg", ["MH-EXP-01"]), proto(d1), "specification and projection code; no simulation")
    # ---- result 6: MH-EXP-02 itemising
    d2 = lf.doc("MH-EXP-02", "mheg")
    r2 = d2["results"]["M202"]["itemised_states"]
    fig("mheg_fig6_itemised_provisions", "bars", "Fig M6 · One yes/no provision against itemised components (MH-EXP-02)",
        {"title": "fully provisioned worlds, each component present with probability 0.85 (240 configurations): states of the itemised finding; the single provision reports SECURED for all", "ylabel": "configurations", "groups": list(r2),
         "series": [{"name": "SECURED (itemised)", "values": [float(r2[f]["SECURED"]) for f in r2]}, {"name": "PARTIAL (itemised)", "values": [float(r2[f]["PARTIAL"]) for f in r2]}, {"name": "single provision: SECURED", "values": [240.0] * len(r2)}],
         "note": f"itemising never raised a finding (0 of {d2['results']['M201']['comparisons']}); {d2['results']['M203']['mean_diff']:.1f} of 8 configurations per world lose the advice 'continue with monitored compliance' (p_Holm {d2['results']['M203']['p_holm']:.4f})"},
        lf.result_record("mheg", ["MH-EXP-02"]), proto(d2), "synthetic institution; components are random")
    # ---- result 7: MH-EXP-04 chain break, with the negative result
    d4 = lf.doc("MH-EXP-04", "mheg")
    rows4 = []
    labels = {"M402a": "classification", "M402b": "institutional treatment", "M402c": "effective access", "M402d": "contestation", "M402e": "revision", "M402f": "material restoration"}
    for k, st in labels.items():
        r = d4["results"][k]
        rows4.append([st, r["outcome"], f"{r['mean_diff']:+.3f}", f"[{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]", f"{r['p_holm']:.4f}", "supported" if r["supported"] else "NOT supported"])
    r41 = d4["results"]["M401"]
    rows4.append(["legal source / translation / data repr.", "all outcomes", "identical", f"{min(r41['outcomes_identical_to_intact'].values())}/{r41['worlds']} worlds", "—", "outcome-blind; audit finds all"])
    fig("mheg_fig7_chain_stage_failures", "table", "Fig M7 · One stage of the chain broken at a time (MH-EXP-04, 30 worlds)",
        {"title": "intact minus broken on each stage's registered outcome (paired sign-flip, Holm over six)", "header": ["stage", "outcome", "intact - broken", "95% CI", "p (Holm)", "result"],
         "xs": [14, 190, 330, 410, 540, 600], "rows": rows4, "colors": [(i, 5, "#78e696" if row[5] == "supported" else "#ff8a70") for i, row in enumerate(rows4)]},
        lf.result_record("mheg", ["MH-EXP-04"]), proto(d4), "synthetic institution; 300 people, 24 periods")
    (out / "mheg_figures_index.json").write_text(json.dumps({"figures": sorted(p.name for p in out.glob("mheg_fig*.svg")), "concept_figures": ["mheg_fig1", "mheg_fig2", "mheg_fig3", "mheg_fig4"], "result_figures": ["mheg_fig5", "mheg_fig6", "mheg_fig7"],
                                                            "earlier_figures_kept": ["legal_fig1 fifteen guarantees", "legal_fig2 legal translation chain", "legal_fig4 contestation", "legal_fig5 material restoration", "legal_fig6 governance comparison", "legal_fig7 negative results"]}, indent=1))
    _ = np


if __name__ == "__main__":
    main()
