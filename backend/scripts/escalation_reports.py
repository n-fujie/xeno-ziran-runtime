"""Generated tables for the resolution-escalation docs. Every number comes from
backend/experiments/results/resolution/summary.json (built from the result files by
``python -m xzr.experiments.escalation.summary``). Prose stays outside the GENERATED markers."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "backend" / "experiments" / "results" / "resolution" / "summary.json"
RES = ("node", "local", "meso", "macro", "global")
ABBR = {"NON-REDUNDANT": "NR", "HIDDEN AT COARSE RESOLUTION": "HID", "UNRESOLVED": "UNR", "REDUNDANT": "RED"}
ORDER = ["A", "B", "D", "E", "F", "G", "H", "I", "J", "K", "C~"]


def pct(x, d=1) -> str:
    return "—" if x is None else f"{100 * float(x):.{d}f}%"


def replace_block(path: Path, body: str, tag: str = "GENERATED") -> None:
    begin, end = f"<!-- {tag}:BEGIN -->", f"<!-- {tag}:END -->"
    text = path.read_text() if path.exists() else f"{begin}\n{end}\n"
    if begin not in text:
        text += f"\n{begin}\n{end}\n"
    a, b = text.index(begin) + len(begin), text.index(end)
    path.write_text(text[:a] + "\n" + body.rstrip() + "\n" + text[b:])


def _matrix_table(rows: list[dict]) -> list[str]:
    conds: dict[str, dict] = {}
    for r in rows:
        conds.setdefault(r["condition"], {})[r["comparison"]] = r
    cols = [k for k in ORDER if any(k in v for v in conds.values())]
    out = ["| condition | n | steps | " + " | ".join(cols) + " |", "|---|---|---|" + "---|" * len(cols)]
    for cid, v in conds.items():
        any_r = next(iter(v.values()))
        out.append(f"| {cid} | {any_r['n']:,} | {any_r['horizon']:,} | " +
                   " | ".join(ABBR.get(v[k]["primary"], v[k]["primary"]) if k in v else "·" for k in cols) + " |")
    return out


def escalation_section(s: dict) -> str:
    m = s["matrix"]
    rows = m["rows"]
    L = [f"Result files: `backend/experiments/results/resolution/*.json` → `summary.json`. Rules: family-wise α = "
         f"{s['rules']['alpha_family']} per comparison, split over 5 resolutions × 2 time families "
         f"(α = {s['rules']['alpha_per_resolution_family']:.4f} each); practical threshold {pct(s['rules']['practical'], 0)}; "
         f"equivalence bound (smallest effect of interest) {pct(s['rules']['sesoi'], 0)}.", ""]
    nc = s["noise_control"]
    L += [f"Noise control (reference C vs C under another random stream, analysed identically): detections in "
          f"{len(nc['false_positive_conditions'])} of {nc['comparisons']} conditions "
          f"({', '.join(nc['false_positive_conditions']) or 'none'}).", ""]
    L += ["### Classification per condition (vs reference structure C)", "",
          "NR = systematic difference at meso, macro or global resolution · HID = trajectories differ, macro and global "
          "equivalent · UNR = coarse equivalence not established · RED = bit-identical", ""]
    L += _matrix_table(rows)
    L += ["", "### Per structural difference", "",
          "| vs C | difference | conditions | visible (meso+) | visible at macro/global | local only | hidden | "
          "unresolved | bit-identical | labels |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in s["structures"].items():
        L.append(f"| {k} | {v['description']} | {v['conditions']} | {len(v['visible'])} | {len(v['visible_coarse'])} | "
                 f"{len(v['locally_only'])} | {len(v['hidden'])} | {len(v['unresolved'])} | {len(v['redundant'])} | "
                 f"{', '.join(v['labels'])} |")
    L += ["", "### Resolution floor (noise control: median 90 % CI half-width of time-aggregated summaries)", "",
          "| design | " + " | ".join(RES) + " | conditions |", "|---|" + "---|" * (len(RES) + 1)]
    for k, v in s["floor"].items():
        L.append(f"| {k} | " + " | ".join(pct(v[r]) for r in RES) + f" | {v['conditions']} |")
    L += ["", "### Regime calibration (transmission gain for a common sustained activity of 0.04)", "",
          "| family | n | gain | activity reached | reached |", "|---|---|---|---|---|"]
    for k, v in sorted(m.get("calibration", {}).items()):
        fam, n = k.split("|")
        L.append(f"| {fam} | {int(n):,} | {v['gain']} | {v['activity']} | {v.get('reached', True)} |")
    L += reversibility_section(s)
    L += ["", "### Omitted from the design", ""]
    for k, v in m.get("meta", {}).get("omitted", {}).items():
        L.append(f"- **{k}**: {v}")
    return "\n".join(L)


def configuration_section(s: dict) -> str:
    L = []
    for k, v in s["structures"].items():
        if k == "C~":
            continue
        L += [f"### {k} — {v['description']}", "", f"Labels: {', '.join(v['labels']) or '—'}", "",
              "| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |", "|---|---|---|---|---|"]
        for f, d in v["factor_dependence"].items():
            L.append(f"| {f} | {'yes' if d['dependent'] else 'no'} | {', '.join(d['visible_at']) or '—'} | "
                     f"{', '.join(d['absent_at']) or '—'} | {', '.join(d['unresolved_at']) or '—'} |")
        if v["effects"]:
            L += ["", "Largest systematic effects where visible: " + "; ".join(
                f"{e['condition']}: {e.get('resolution', '?')} {e.get('feature', '')} {pct(e.get('relative'))}"
                for e in v["effects"][:12])]
        L.append("")
    if "clusters" in s:
        L += ["### Interacting reasoning clusters", ""] + _matrix_table(s["clusters"]["rows"]) + [""]
    if "adaptivity" in s:
        L += ["### World-responsive revision (all ten triggers)", "",
              "| noise | adaptivity C / M / S / R | in-band C / S / M / R / A | C − S (t) | C − R (t) | C − A (t) | "
              "responded vs control | firings |", "|---|---|---|---|---|---|---|---|"]
        for cid, a in s["adaptivity"].items():
            ib, pp = a["in_band"], a["in_band_paired"]
            L.append(f"| {cid.split(':')[-1]} | {' / '.join(str(a['adaptivity'][x]) for x in 'CMSR')} | "
                     f"{' / '.join(pct(ib[x]['share_mean']) for x in 'CSMRA')} | "
                     f"{pct(pp['C-S']['mean'])} ({pp['C-S']['t']}) | {pct(pp['C-R']['mean'])} ({pp['C-R']['t']}) | "
                     f"{pct(pp['C-A']['mean'])} ({pp['C-A']['t']}) | {pct(a['response']['responded'], 0)} vs "
                     f"{pct(a['response']['control'], 0)} | {a['response']['firings_mean']} |")
        L += ["", "| noise | vs C | classification | resolutions (node · local · meso · macro · global) |",
              "|---|---|---|---|"]
        for cid, a in s["adaptivity"].items():
            for key, r in a["comparisons"].items():
                L.append(f"| {cid.split(':')[-1]} | {key} | {r['primary']} | " +
                         " · ".join(r["status"][x] for x in RES) + " |")
    L += ["", "### Reasoning structures: descriptors (size 32)", "",
          "| structure | depth | cycles | branching | conflict density | centralization | record locality | "
          "redundancy | fixpoint sensitivity | clusters | inter-cluster coupling | unsupported backed | "
          "active / bindings (reference rule) |", "|" + "---|" * 13]
    for k, v in s["descriptors"].items():
        d = v["32"]
        L.append(f"| {k} | {d['dependency_depth']} | {d['cycle_count']} | {d['support_branching']} | "
                 f"{d['incompatibility_density']} | {d['dependency_centralization']} | {d['record_locality']} | "
                 f"{d['support_redundancy']} | {d['fixpoint_sensitivity']} | {d['cluster_count']} | "
                 f"{d['inter_cluster_coupling']} | {d['unsupported_backed']} | "
                 f"{d.get('active_bindings_reference', '—')} / {d.get('bindings', '—')} |")
    return "\n".join(L)


def _study_table(rows: list[dict], variants: list[str]) -> list[str]:
    conds = list(dict.fromkeys(r["condition"] for r in rows))
    out = ["| structure | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
    for c in conds:
        cells = []
        for v in variants:
            r = next((x for x in rows if x["condition"] == c and x["comparison"] == v), None)
            if r is None:
                cells.append("·")
                continue
            lg = r.get("largest")
            eff = f" ({lg['resolution']} {lg['feature']} {pct(lg['relative'], 0)})" if lg else ""
            cells.append(f"{ABBR.get(r['primary'], r['primary'])}{eff}")
        out.append(f"| {c.split(':')[-1]} | " + " | ".join(cells) + " |")
    return out


def disconnection_section(s: dict) -> str:
    L = []
    if "disconnection" in s:
        d = s["disconnection"]
        v = d["verdict"]
        L += [f"**Status: {v['status']}**", "",
              f"- removal detectable (downstream, systematic) in: {', '.join(v['removal_detected_in']) or 'none'}",
              f"- removal equivalent (macro and global within 5 %, no systematic difference) in: "
              f"{', '.join(v['removal_equivalent_in']) or 'none'}",
              f"- removal unresolved in: {', '.join(v['removal_unresolved_in']) or 'none'}",
              f"- replacements equivalent in every structure: {', '.join(v['equivalent_replacements']) or 'none'}",
              f"- replacements bit-identical in every structure: "
              f"{', '.join(k for k, x in v['replacements'].items() if x['identical_everywhere']) or 'none'}",
              f"- noise control detections: {len(d['noise_control']['false_positive_conditions'])} of "
              f"{d['noise_control']['comparisons']}", "",
              "Own outputs excluded: " + ", ".join(d["meta"].get("own_outputs_excluded", [])), ""]
        L += _study_table(d["rows"], ["off", "weight_zero", "as_cut", "as_mutation", "redirect", "C~"])
    if "topology_triggers" in s:
        t = s["topology_triggers"]
        v = t["verdict"]
        L += ["", "### Cut / reconfiguration triggers", "", f"**Status: {v['status']}**", "",
              f"- removing the reconfiguration trigger (cut only) detectable in: "
              f"{', '.join(v['removal_detected_in']['cut_only']) or 'none'}",
              f"- removing the cut trigger (reconfiguration only) detectable in: "
              f"{', '.join(v['removal_detected_in']['reconfigure_only']) or 'none'}",
              f"- unified trigger detectable in: {', '.join(v['merged_detected_in']['unified']) or 'none'}",
              f"- merged condition detectable in: {', '.join(v['merged_detected_in']['merged']) or 'none'}",
              f"- shared generic operation with separate conditions bit-identical everywhere: "
              f"{v['generic_conditions_identical_everywhere']}",
              f"- **A. is the connection-mutation operation shared?** {v['operation_shared']}",
              f"- **B. are the trigger conditions operationally distinct?** {v['conditions_distinct']}", ""]
        L += _study_table(t["rows"], ["cut_only", "reconfigure_only", "unified", "generic_conditions", "merged", "C~"])
    return "\n".join(L)


def penetration_section(s: dict) -> str:
    rows = [r for r in s["penetration"]["rows"] if r["scales_crossed"] > 0]
    rows.sort(key=lambda r: (-r["scales_crossed"], r["condition"]))
    L = [f"Comparisons with a systematic difference at ≥ 1 resolution: {len(rows)} of "
         f"{len(s['penetration']['rows'])} with a trajectory difference.", "",
         "| vs C | condition | levels | interventions | world | targets | first macro | systematic at | depth | "
         "local/node | meso/local | macro/meso | global/macro | return |", "|" + "---|" * 14]
    def st(x):
        return "—" if x is None else f"{int(x)}"
    for r in rows[:80]:
        c, a = r["chain_steps"], r["amplification"]
        L.append(f"| {r['comparison']} | {r['condition']} | {st(c['level'])} | {st(c['intervention'])} | "
                 f"{st(c['world'])} | {st(c['target'])} | {st(c['macro_exact'])} | "
                 f"{', '.join(r['detected_resolutions'])} | {r['depth']} | "
                 f"{a['local/node']} | {a['meso/local']} | {a['macro/meso']} | {a['global/macro']} | "
                 f"{r['return_into_local']} |")
    return "\n".join(L)


def reversibility_section(s: dict) -> list[str]:
    rows = s.get("reversibility", [])
    if not rows:
        return []
    L = ["", "### Reversibility (variant reverted to the reference rule at mid-run)", "",
         "| condition | variant | unreverted | reverted | systematic difference after the revert (node · local · meso · "
         "macro · global) | irreversible |", "|---|---|---|---|---|---|"]
    for r in rows:
        a = r["systematic_after_revert"]
        L.append(f"| {r['condition']} | {r['variant']} | {r['unreverted_primary']} | {r['reverted_primary']} | "
                 + " · ".join("yes" if a[x] else "no" for x in RES) + f" | {r['irreversible']} |")
    return L


def compression_section(s: dict) -> str:
    L = []

    def f(x, d=3):
        return "—" if x is None or x.get("mean") is None else f"{x['mean']:.{d}f} ± {x['sd']:.{d}f}"
    for h, r in s["compression"]["horizons"].items():
        L += [f"### {int(h):,} steps ({r['seeds']} seeds, {r['symbols']} shapes, summary every {r['every']} steps)", "",
              "| run | compression ratio | phrases | replay R² | path dependence raw | compressed |", "|---|---|---|---|---|---|"]
        for k, v in r["per_variant"].items():
            L.append(f"| {k} | {f(v['compression_ratio'], 2)} | {f(v['phrases'], 0)} | {f(v['replay_r2'])} | "
                     f"{f(v['path_dependence_raw'])} | {f(v['path_dependence_compressed'])} |")
        L += ["", "| pair vs C | distance ÷ noise raw | compressed | systematic raw | compressed | onset delay "
                  "(windows) | onset lost | local difference corr. | local magnitude kept |", "|" + "---|" * 9]
        for k, v in r["pairs"].items():
            L.append(f"| {k} | {f(v['raw_distance_ratio'])} | {f(v['compressed_distance_ratio'])} | "
                     f"{v['systematic_raw']['detected']} | {v['systematic_compressed']['detected']} | "
                     f"{f(v['onset_delay_windows'], 1)} | {v['onset_missing_compressed']} | "
                     f"{f(v['local_difference_correlation'])} | {f(v['local_magnitude_ratio'])} |")
        L += ["", f"Compression cost per seed: codebook {f(r['timing']['codebook_s'])} s, encoding "
                  f"{f(r['timing']['encode_s'])} s.", ""]
    return "\n".join(L)


def _ev_table(evs: list[dict], k: int = 12) -> list[str]:
    out = ["| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) "
           "| classification |", "|---|---|---|---|---|---|---|---|---|---|"]
    for e in evs[:k]:
        eff = e["effect"]
        es = (f"{eff['resolution']} {eff['feature']} {pct(eff['relative'])}" if "resolution" in eff else
              f"median |Δ| global {pct(eff.get('median_abs_relative_global'))}; divergence ratio "
              f"{float(eff.get('divergence_ratio_global') or 0):.2f}")
        nc = e["noise_comparison"]["noise_ci_half"]
        ns = f"{pct(nc['macro'])} / {pct(nc['global'])}" if nc else "—"
        u = e["uncertainty"]["ci_half"]
        out.append(f"| {e['experiment_id']} | {e['comparison']} | {es} | {ns} | {e['topology']} | {e['configurations']:,} | "
                   f"{e['horizon']:,} | {e['seeds']} | {pct(u['macro'])} / {pct(u['global'])} | "
                   f"{', '.join(e['classification'])} |")
    if len(evs) > k:
        out.append(f"| … {len(evs) - k} more rows in summary.json | | | | | | | | | |")
    return out


def answers_section(s: dict) -> str:
    a = s.get("answers", {})
    L = []
    for q in sorted(a, key=int):
        x = a[q]
        L += [f"### {q}. {x['question']}", ""]
        if "structures" in x:
            L.append(f"Structures: **{', '.join(x['structures']) or 'none'}**")
        for key in ("smallest_n", "smallest_horizon", "smallest_structure_size", "bit_identical_in_all_conditions",
                    "conditions", "comparisons_with_trajectory_difference", "finest_systematic_resolution",
                    "coarsest_systematic_resolution", "exact_divergence_share"):
            if key in x:
                L.append(f"- {key.replace('_', ' ')}: {x[key]}")
        if "counts" in x:
            L.append("- per structure (unresolved / hidden / conditions): " + "; ".join(
                f"{k} {v['unresolved']}/{v['hidden']}/{v['conditions']}" for k, v in x["counts"].items()))
        if "verdict" in x and isinstance(x["verdict"], dict):
            v = x["verdict"]
            if "status" in v:
                L.append(f"- verdict: **{v['status']}**")
                for kk in ("operation_shared", "conditions_distinct", "removal_detected_in", "equivalent_replacements"):
                    if kk in v:
                        L.append(f"- {kk.replace('_', ' ')}: {v[kk]}")
            else:
                for cid, vv in v.items():
                    L.append(f"- {cid}: " + "; ".join(f"{kk.replace('_', ' ')} {vv2}" for kk, vv2 in vv.items()
                                                      if not isinstance(vv2, dict)))
                    for kk, vv2 in vv.items():
                        if isinstance(vv2, dict):
                            L.append(f"  - {kk.replace('_', ' ')}: {vv2}")
        if "collapsed_share_by_condition" in x:
            L += ["", f"Rule: {x.get('rule', '')}", "",
                  "| experiment | reasoning active | collapsed | never enabled | topology | memory | mutation | address "
                  "| n | steps |", "|---|---|---|---|---|---|---|---|---|---|"]
            for c in x["collapsed_share_by_condition"][:30]:
                L.append(f"| {c['experiment_id']} | {pct(c['reasoning_share'])} | {pct(c['collapsed_share'])} | "
                         f"{pct(c['never_enabled_share'])} | "
                         f"{c.get('topology')} | {c.get('memory')} | {c.get('mutation')} | {c.get('address')} | "
                         f"{c.get('n')} | {c.get('horizon')} |")
        evs = x.get("evidence")
        if isinstance(evs, list) and evs:
            L += [""] + _ev_table(evs)
        for key in ("reasoning_vs_none", "structure_differences"):
            if x.get(key):
                L += ["", f"{key.replace('_', ' ')}:", ""] + _ev_table(x[key])
        L.append("")
    return "\n".join(L)


BENCH = ROOT / "backend" / "experiments" / "results" / "resolution" / "bench.json"


def benchmark_section(b: dict, s: dict | None) -> str:
    c = b["core"]
    L = [f"Measured {b['date']} ({b['machine']['platform']}, Python {b['machine']['python']}, NumPy "
         f"{b['machine']['numpy']}); `make bench-escalation`; raw: `backend/experiments/results/resolution/bench.json`.",
         "", "### 1. Core runtime (engine step only)", "",
         "| configurations | runtime | steps/s | ms/step p50 | p95 | runtime arrays (MiB) |", "|---|---|---|---|---|---|"]
    for k, v in c.items():
        if ":" in k and k.split(":")[1] in ("full", "minimal"):
            L.append(f"| {int(v['n']):,} | {k.split(':')[1]} | {v['steps_per_second']} | {v['ms_p50']} | {v['ms_p95']} | "
                     f"{v['array_mib']} |")
    sd = c.get("10000:with_shape_detection", {})
    dm = c.get("10000:delta_and_memory", {}).get("runtime_only", {})
    ws = c.get("websocket_full", {})
    L += ["", f"Shape detection at 10,000: {sd.get('steps_per_second')} steps/s (p95 {sd.get('step_ms_p95')} ms). "
              f"Delta: {dm.get('delta_bytes_per_step_mean')} bytes/step mean. WebSocket (full runtime): " +
          "; ".join(f"{k}: {v['steps_streamed_per_second']} steps/s, {v['delta_frames_per_second']} frames/s, "
                    f"{v['kib_per_second']} KiB/s" for k, v in ws.items()),
          "", "### 2. Reasoning runtime (closed loop with the reference structure and triggers vs no reasoning layer)", "",
          "| configurations | structure size | no reasoning (ms/step) | closed loop (ms/step) | overhead (ms/step) | "
          "relative |", "|---|---|---|---|---|---|"]
    for r in b["reasoning"]:
        L.append(f"| {r['n']:,} | {r['size']} | {r['none_ms_per_step']} | {r['closed_loop_ms_per_step']} | "
                 f"{r['reasoning_overhead_ms_per_step']} | {pct(r['reasoning_overhead_relative'])} |")
    L += ["", "### 3. Diagnostic instrumentation (research only; never part of product runtime cost)", "",
          "| configurations | multi-scale observer (ms/step) | realized-coupling probe (ms/step) |", "|---|---|---|"]
    for o in b["instrumentation"]["observer"]:
        L.append(f"| {o['n']:,} | {o['observer_ms_per_step']} | {o['coupling_probe_ms_per_step']} |")
    L += ["", "Per-condition statistics (sign-flip max-T, 12 seeds): " + "; ".join(
        f"{k}: {v} s" for k, v in b["instrumentation"]["statistics_s"].items())]
    if s and "matrix" in s:
        import statistics
        refs = s["matrix"]["references"]
        L += ["", "### 4. Experiment harness overhead (measured inside the matrix runs, 7 parallel workers)", "",
              "| configurations | harness run (ms/step, median) | loop only (ms/step) | observer + probes + bookkeeping |",
              "|---|---|---|---|"]
        by_n: dict = {}
        for v in refs.values():
            by_n.setdefault(v["condition"]["n"], []).append((v["ms_per_step"], v["loop_ms_per_step"]))
        for n, xs in sorted(by_n.items()):
            a = statistics.median(x[0] for x in xs)
            lo = statistics.median(x[1] for x in xs)
            L.append(f"| {int(n):,} | {a:.2f} | {lo:.2f} | {a - lo:.2f} |")
    L += ["", "### 5. Compression overhead (codebook + encoding + phrase factorisation, one run)", "",
          "| steps | seconds |", "|---|---|"]
    for k, v in b["compression_s"].items():
        L.append(f"| {int(k):,} | {v} |")
    L += ["", f"Peak RSS of the benchmark process: {b['peak_rss_mib']} MiB."]
    return "\n".join(L)


def main() -> None:
    if not SUMMARY.exists():
        return
    s = json.loads(SUMMARY.read_text())
    docs = ROOT / "docs"
    if "matrix" in s:
        replace_block(docs / "RESOLUTION_ESCALATION.md", escalation_section(s))
        replace_block(docs / "REASONING_CONFIGURATION_MAP.md", configuration_section(s))
        replace_block(docs / "SCALE_PENETRATION.md", penetration_section(s))
    if "disconnection" in s or "topology_triggers" in s:
        replace_block(docs / "DISCONNECTION.md", disconnection_section(s))
    if "compression" in s:
        replace_block(docs / "LONG_RUN_COMPRESSION.md", compression_section(s))
    if BENCH.exists():
        replace_block(docs / "BENCHMARK.md", benchmark_section(json.loads(BENCH.read_text()), s),
                      tag="GENERATED:ESCALATION")
    if s.get("answers"):
        replace_block(docs / "EXPERIMENT_RESULTS.md", answers_section(s), tag="GENERATED:ESCALATION")


if __name__ == "__main__":
    main()
