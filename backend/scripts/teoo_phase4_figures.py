"""Research figures of Phase 4, generated from the saved results of the confirmatory run (docs/teoo_evidence/phase4/confirmatory_v2). Run: PYTHONPATH=. python scripts/teoo_phase4_figures.py [RESULTS_DIR [OUT_DIR]]

Each figure is an SVG with the evidence band and the class watermarks built in, and its metadata (experiment id and version, seeds, conditions, observation conditions and their limits, source digest, generation time) embedded; the
JSON metadata is written next to it. The PNG files are made by rasterising the SVG in a browser (frontend/scripts/... see docs/TEOO.md) and adding the same metadata to a tEXt chunk (backend/scripts/teoo_phase4_png.py).
These are plots of synthetic-world results, not photographs and not screenshots of the application; the screenshots of the application are separate files with their own source records."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from xzr.teoo import experiments as X
from xzr.teoo import export as EX
from xzr.teoo.provenance import Kind, Provenance, digest_of, seal

AT = "2026-10-31T00:00:00.000000Z"  # the date of the confirmatory run (a fixed value, so that the same results give the same bytes)


def main() -> None:
    res = Path(sys.argv[1] if len(sys.argv) > 1 else "../docs/teoo_evidence/phase4/confirmatory_v2")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "../docs/teoo_evidence/phase4/figures")
    out.mkdir(parents=True, exist_ok=True)
    docs = {k: json.loads((res / f"EXP-{k}.json").read_text()) for k in "ABCDE"}
    obs_rec = json.loads((res / "total_observation_records.json").read_text())

    def record(key: str) -> dict:
        d = docs[key]
        return seal({"experiment": d["experiment_id"], "protocol_version": d["protocol_version"], "protocol_digest": d["protocol_digest"], "results_digest": digest_of(d["results"]), "units": d["units"]},
                    provenance=Provenance.SYNTHETIC, kind=Kind.OBSERVATION, creator={"name": "teoo.phase4/1", "role": "generator"},
                    source={"kind": "generator", "description": f"{d['experiment_id']} results on the synthetic world (xzr.teoo.experiments)", "declared_by": "teoo.phase4"}, created_at=AT)

    def obs_note(text: str) -> dict:
        return {"version": None, "t": None, "summary": {"observation conditions": text}, "claim_note": "These are measurements by a simulated sensor of a synthetic world: the limits are those of the sensor conditions stated here; what lies outside them is unknown, not absent."}

    def fig(name: str, kind: str, title: str, data: dict, keys: str, observation: str) -> None:
        recs = [record(k) for k in keys]
        d0 = docs[keys[0]]
        proto = {"experiment_id": d0["experiment_id"], "version": d0["protocol_version"], "seeds": [d0["seeds"][0], d0["seeds"][-1]], "conditions": d0["protocol"]["conditions"], "trials_per_condition": d0["protocol"]["trials_per_condition"]}
        f = EX.build_figure(kind, title, data, recs, generated_at=AT, protocol=proto, observation=obs_note(observation))
        assert EX.verify_svg(f["svg"]) == [], name
        (out / f"{name}.svg").write_text(f["svg"])
        (out / f"{name}.metadata.json").write_text(f["metadata_json"])
        print(name, len(f["svg"]) // 1024, "KB")

    # 1 Total Relational Observation: of the true couplings, how many are read, by sensor and body configuration
    b = docs["B"]["results"]["descriptive"]
    fig("fig1_total_relational_observation", "bars", "Fig 1 · Total relational observation: true couplings that stay invisible to the reader (mean per world, 10 components)",
        {"title": "true couplings NOT read, by sensor and body configuration (SYNTHETIC worlds, n = 30; fine / medium / limited sensors)", "ylabel": "mean number of true couplings not read", "groups": list(b),
         "series": [{"name": s, "values": [b[c][s]["invisible_true_edges_mean"] for c in b]} for s in ("fine", "medium", "limited")], "note": "a coupling that is not read is unobserved, not absent; the reader also reports false couplings (indirect paths)"},
        "B", "three simulated sensors: fine (0.02 s, resolution 0.5, limit 0.05, penetration 0.9), medium (0.2 s, 2.0, 0.3, 0.6), limited (0.2 s, 4.0, 0.8, 0.4); window 20 s")
    # 2 Observation resolution comparison
    a = docs["A"]["results"]["secondary"]["identification_rate_by_factor_and_feature"]
    fig("fig2_observation_resolution", "bars", "Fig 2 · Observation resolution: share of true differences identified by sampling period",
        {"title": "identification rate of true differences by feature type and sampling period (30 worlds, all other parameters pooled)", "ylabel": "share identified (undetermined counts as not identified)", "groups": list(X.TYPES),
         "series": [{"name": f"sampling period {ts} s", "values": [a["ts"][str(ts)][k] for k in X.TYPES]} for ts in X.GRID["ts"]], "ymax": 1.0, "note": "frequency differences survive aliasing as differences (see the text); burst and amplitude differences do not survive coarse sampling"},
        "A", "grid: sampling period 0.02/0.2/1.0 s × resolution 0.5/4.0 × detection limit 0.05/0.8 × window 20/4 s; penetration 0.6")
    # 3 Open body reconfiguration
    sh = docs["B"]["results"]["B1"]["share_cut_pairs_read"]
    fig("fig3_open_body_reconfiguration", "bars", "Fig 3 · Open body reconfiguration: share of the cut pairs that are read as coupled",
        {"title": "share of the cut pairs read as coupled, by body configuration (fine sensor, 30 worlds)", "ylabel": "share read as coupled", "groups": list(sh), "series": [{"name": "cut pairs", "values": list(sh.values())}], "ymax": 1.0,
         "note": "the graph changed and the generated signal changed with it (a property of this synthetic world); nothing here is a physical effect"}, "B", "fine simulated sensor: 0.02 s, resolution 0.5, limit 0.05, penetration 0.9, window 20 s")
    # 4 Open revision
    arms = docs["C"]["results"]["arms"]
    names = list(arms)
    fig("fig4_open_revision", "bars", "Fig 4 · Open revision: true differences identified (of 12) by way of arriving at the sensor",
        {"title": "differences identified (mean ± sd over 30 worlds) and cost over the initial sensor (budget 6.0)", "ylabel": "identified (of 12) / cost units", "groups": names,
         "series": [{"name": "identified", "values": [arms[n]["identified_mean"] for n in names], "err": [arms[n]["identified_sd"] for n in names]}, {"name": "cost over initial", "values": [arms[n]["cost_over_initial_mean"] for n in names]}],
         "note": "adaptive revision does not beat the cost-matched static sensor (see Fig 7); no event shows autonomous revision"}, "C", "initial sensor: 1.0 s, resolution 4.0, limit 0.8, window 4 s, penetration 0.3; revisions are offline, before the final measurement")
    # 5 Disconnection
    dd = docs["D"]["results"]["D1"]
    fig("fig5_disconnection", "bars", "Fig 5 · Disconnection: observed dependency against simulated operability",
        {"title": f"source-sink dependency read by the fine sensor and the world's own operability (30 worlds; Spearman rho = {docs['D']['results']['D3']['rho']:.2f})", "ylabel": "dependency (best-lag correlation) / operability (variance share)",
         "groups": list(dd["mean_dependency"]), "series": [{"name": "observed dependency", "values": list(dd["mean_dependency"].values())}, {"name": "operability (truth)", "values": list(dd["mean_operability"].values())}],
         "note": "observed dependency tracks operability, and also exceeds it: correlation along indirect paths is read as dependency"}, "D", "fine simulated sensor, 0.02 s, window 20 s")
    # 6 Reconstruction limits
    t = docs["E"]["results"]["table"]
    conds = list(t)
    fig("fig6_reconstruction_limits", "bars", "Fig 6 · Reconstruction limits: what is rebuilt, and what is declared unidentifiable",
        {"title": "interpolation: normalised error of identifiable cells, and the share declared unidentifiable (30 worlds × 10 components)", "ylabel": "normalised RMSE / share unidentifiable", "groups": conds,
         "series": [{"name": "nrmse (identifiable cells)", "values": [t[c]["interp"]["nrmse"] for c in conds]}, {"name": "share unidentifiable", "values": [t[c]["interp"]["unidentifiable_share"] for c in conds]}, {"name": "zero predictor nrmse", "values": [t[c]["zero"]["nrmse"] for c in conds]}],
         "note": "unidentifiable cells are kept as gaps (no error is computed for them); 90% intervals cover 0.96-0.99: conservative"}, "E", "degradations of one fine sensor: partial reach, 40% gaps, 1.0 s sampling, penetration 0.3, 3x noise, 0.12 s desynchronisation")
    # 7 Non-redundancy comparison: paired differences with intervals
    def row(label: str, r: dict, note: str) -> dict:
        ci, sd = r.get("ci95") or r.get("ci90"), r.get("sd_diff")
        if not ci or not sd:  # a standardised paired difference needs the sd of the differences; the equivalence results carry only their interval
            return {"label": label, "mean": 0.0, "lo": None, "hi": None, "note": note, "supported": None}
        return {"label": label, "mean": r["mean_diff"] / sd, "lo": ci[0] / sd, "hi": ci[1] / sd, "note": note, "supported": (r["p_holm"] < 0.05 if r.get("p_holm") is not None else r["p"] < 0.05)}
    A, B, C = docs["A"]["results"], docs["B"]["results"], docs["C"]["results"]
    fig("fig7_non_redundancy", "forest", "Fig 7 · Non-redundancy: the new component against a simple comparator (paired differences, 95% intervals)",
        {"title": "positive = the new component is better than its comparator at equal information and cost", "xlabel": "mean / sd of the paired differences, 95% interval; green = p < 0.05 (Holm for confirmatory)",
         "rows": [row("C3  adaptive revision − cost-matched static sensor (identified of 12)", C["C3"], f"confirmatory · p {C['C3']['p']:.2f}"), row("C5  adaptive revision − random order (identified)", C["C5"], "exploratory"),
                  row("C2  adaptive revision − pre-specified schedule (identified)", C["C2"], "confirmatory"), row("B3  status-aware reading − naive reading (precision)", B["B3"], f"confirmatory · p {B['B3']['p']:.2f}"),
                  row("A6  status model − detection-limit rule (accuracy)", A["A6"], "exploratory; weak comparator")]}, "ABC", "see Figs 2-4")
    # 8 Experimental evidence summary
    rows: list[list[str]] = []
    colors: list[list] = []
    order = [("A", ["A1", "A2", "A3", "A4", "A5", "A6"]), ("B", ["B1", "B2", "B3"]), ("C", ["C1", "C2", "C3", "C4", "C5"]), ("D", ["D1", "D2", "D3"]), ("E", ["E1", "E2", "E3"])]
    for k, ids in order:
        for aid in ids:
            r = docs[k]["results"][aid]
            ph = r.get("p_holm")
            verdict = ("supported" if (ph is not None and ph < 0.05) else "not supported") if r.get("supported") is None and "criterion_met" not in r else ("equivalence supported" if r.get("supported") else "equivalence NOT supported") if "supported" in r and r.get("supported") is not None else ("criterion met" if r["criterion_met"] else "criterion NOT met")
            if aid == "A6":
                verdict = "exploratory: " + ("favours status model" if r["p"] < 0.05 else "no difference")
            if aid in ("C5", "C4"):
                verdict = "exploratory: " + verdict
            effect = r.get("mean_diff") if r.get("mean_diff") is not None else r.get("rho", r.get("max_rate"))
            rows.append([aid, docs[k]["protocol"]["experiment_id"].replace("TEOO4-", ""), r["registered_class"].split(" (")[0], f"{effect:.3f}" if effect is not None else "-", f"{ph:.4f}" if ph is not None else "-", verdict])
            colors.append([len(rows) - 1, 5, "#78e696" if verdict.startswith(("supported", "equivalence supported", "criterion met")) else "#ff8a70" if "NOT" in verdict or verdict == "not supported" else "#9bb0d0"])
    fig("fig8_evidence_summary", "table", "Fig 8 · Experimental evidence summary (protocol version 2, 30 synthetic worlds per experiment)",
        {"title": "registered analyses, their class (decided by the registry) and their result; Synthetic-world results only", "header": ["analysis", "experiment", "class", "effect", "p (Holm)", "result"], "xs": [20, 80, 160, 260, 340, 420], "rows": rows, "colors": colors}, "ABCDE",
        "see each experiment")
    (out / "figures_index.json").write_text(json.dumps({"results_dir": str(res), "total_observation_record": obs_rec["unit_seed"], "figures": sorted(p.name for p in out.glob("fig*.svg"))}, indent=1))


if __name__ == "__main__":
    main()
