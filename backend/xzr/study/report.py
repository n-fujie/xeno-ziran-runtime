"""Paper outputs of a study: Methods and Results text, tables (CSV / Markdown / JSON), figures (SVG, PNG when a converter
is installed) with captions that name the experiment, and a reproducibility package with checksums.

The text states measurements. It never states a philosophical interpretation or a theoretical proposition; where the
protocol is a functional check the text says so at the top of every output.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from .runner import Study

FUNCTIONAL_BANNER = (
    "FUNCTIONAL CHECK — a software verification on a reserved seed range with a small sample. These numbers "
    "are not evidence and must not be reported as results."
)
INTERPRETATION_BOUNDARY = (
    "Interpretation boundary: the figures and statements here are measurements of a simulated system "
    "under the stated protocol. They support no philosophical or theoretical proposition by themselves; "
    "any such reading is a separate argument and is not generated here."
)


def _f(x: Any, d: int = 3) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    if isinstance(x, int):
        return str(x)
    return f"{x:.{d}g}" if abs(x) < 1e4 else f"{x:.0f}"


# ----------------------------------------------------------------------------------------------- text
def methods(study: Study, an: dict) -> str:
    doc, man = study.protocol(), study.manifest()
    env, info = doc["environment"], man["environment"]
    lines = [f"# Methods — {doc['title']}", ""]
    if doc["mode"] == "functional":
        lines += [f"> {FUNCTIONAL_BANNER}", ""]
    lines += [
        f"Experiment ID `{study.id}`; protocol digest `{man['protocol_digest']}`; mode **{doc['mode']}**.",
        "",
        "## Question and hypotheses",
        doc["question"],
        "",
    ]
    for h in doc.get("hypotheses", []):
        lines.append(f"- **{h['id']}** {h['text']} (contrasts {', '.join(h.get('contrasts', []))})")
    lines += ["", "## Environment"]
    if env["kind"] == "hpo-world":
        w = env.get("world", {})
        lines.append(
            f"The runtime world (xzr.runtime) with {w.get('n', 800)} configurations, regime `{w.get('regime', 'intermittent')}`, "
            f"warm-up {env.get('warmup', 40)} steps and a horizon of {env.get('horizon', 240)} steps, observed and acted on by "
            f"a heterogeneous-operations field (xzr.hpo) whose configuration is reconfigured between epochs of "
            f"{60} steps. All effects are internal to the simulation."
        )
        if env.get("detect_shapes"):
            lines.append(
                "A shape detector (xzr.shapes) read the engine's step deltas; its output is a structural measurement "
                "and no interpretation is produced."
            )
    else:
        lines.append(
            f"The shared physical laboratory (xzr.lab) with populations of scientific systems, {env.get('horizon')} steps."
        )
    lines += ["", "## Arms (methods compared)"]
    prof = an["fairness"]["profiles"]
    for a in doc["arms"]:
        p = prof[a["name"]]
        lines += [
            f"### {a['name']}",
            a["description"],
            "",
            f"- controller: {p['controller']}; meta-revision: {p['meta_revision']}; history re-entry: {p['history_reinsertion']}",
            f"- revision authority: {p['revision_authority'] if isinstance(p['revision_authority'], str) else ', '.join(p['revision_authority'])}",
            f"- change budget per epoch: {p['max_changes_per_epoch'] if p['max_changes_per_epoch'] is not None else 'none'}; "
            f"protocol interventions: {p['interventions']}; initial changes: {len(a.get('initial_changes', []))}",
            "",
        ]
    lines += [
        "## Fairness controls",
        an["fairness"]["controls"]["initial_condition"] + ". " + an["fairness"]["controls"]["evaluation"] + ".",
        "Differences between the arms of each contrast:",
    ]
    for c in an["fairness"]["contrasts"]:
        lines.append(
            f"- {c['contrast']} ({c['a']} vs {c['b']}): differs in {', '.join(c['declared']) or 'nothing'}; "
            f"undeclared differences: {', '.join(c['undeclared']) or 'none'}; equal in {', '.join(c['equal_on'])}."
        )
    seeds = an["seeds"]
    lines += [
        "",
        "## Seeds and sample",
        f"{len(seeds)} independent seeds per arm (generator seed, engine seed): "
        + ", ".join(f"({g}, {e})" for g, e in seeds[:40])
        + (" …" if len(seeds) > 40 else "")
        + ". Arms share each seed's "
        "initial world, warm-up and exogenous input stream, so contrasts are paired by seed.",
        "",
        "## Measures",
        "Primary: "
        + ", ".join(doc["metrics"]["primary"])
        + ". Secondary: "
        + ", ".join(doc["metrics"].get("secondary", []))
        + ".",
        "",
        "## Statistical analysis",
        "Per arm: n, mean, median, SD, variance, range, quartiles and a bootstrap 95% interval of the mean (2000 resamples). "
        "Per declared contrast and metric: paired mean difference with a bootstrap 95% interval, Cohen's dz, a paired sign-flip "
        "permutation p, a Wilcoxon signed-rank p and leave-one-out sensitivity; an independent-trials comparison (Welch, "
        "Mann-Whitney, Hedges' g) is given alongside. Multiplicity: Holm (family-wise) and Benjamini-Hochberg over every "
        "contrast x metric reported. A metric undefined for a run is counted as undefined. Outliers are listed and kept. "
        "Criteria are evaluated on the declared effect size and interval, not on a p-value alone.",
        "",
        "## Stop conditions and budget",
        f"Per-run timeout {doc['stop']['timeout_per_run_s']} s; wall-clock budget {doc['stop']['max_wall_seconds']} s; at most "
        f"{doc['stop'].get('max_failures', 3)} failures before a safe stop; run budget {doc.get('budget', {}).get('max_runs')}.",
        "",
        "## Software and environment",
        f"Git commit `{info['git_commit']}` (branch `{info['git_branch']}`, working tree {'dirty' if info['git_dirty'] else 'clean'}); "
        f"Python {info['python']}; "
        + ", ".join(f"{k} {v}" for k, v in info["dependencies"].items() if v)
        + f"; {info['platform']}. "
        + info["determinism_note"],
        "",
    ]
    if an["amendments"]:
        lines += (
            ["## Amendments after registration"]
            + [
                f"- {a['at']} `{a['path']}` ({a['status']}; runs started: {a['runs_started']}): {a['reason']}"
                for a in an["amendments"]
            ]
            + [""]
        )
    else:
        lines += ["## Amendments after registration", "None.", ""]
    return "\n".join(lines)


def results(study: Study, an: dict) -> str:
    doc = study.protocol()
    lines = [f"# Results — {doc['title']}", ""]
    if doc["mode"] == "functional":
        lines += [f"> {FUNCTIONAL_BANNER}", ""]
    acc = an["accounting"]
    tot_ok = sum(a["ok"] for a in acc.values())
    tot = sum(a["planned"] for a in acc.values())
    lines += [
        f"{tot_ok} of {tot} planned runs completed; failures: "
        + (", ".join(f"{k} {v['failed'] + v['timeout']}" for k, v in acc.items() if v["failed"] + v["timeout"]) or "none")
        + ".",
        "",
        "## Criteria",
        f"Verdict: **{an['criteria']['verdict']}**. {an['criteria']['scope']}",
    ]
    for c in an["criteria"]["success"] + an["criteria"]["failure"]:
        kind = "success" if c in an["criteria"]["success"] else "failure"
        lines.append(
            f"- {kind} criterion on {c['contrast']} / {c['metric']} ({c['direction']}, ≥ {c.get('min_relative_effect', 0):.0%} relative): "
            f"**{c['result']}**"
            + (
                f" (relative effect {_f(c.get('observed_relative_effect'))}, CI {_f(c['ci95'][0])} to {_f(c['ci95'][1])}, "
                f"{c['n_pairs']} pairs)"
                if "ci95" in c
                else ""
            )
        )
    lines += ["", "## Contrasts (every declared contrast and metric, including null and reversed effects)"]
    for c in an["contrasts"]:
        lines += [
            "",
            f"### {c['id']}: {c['a']} − {c['b']}  [{c['evidence']}]",
            f"Varies: {', '.join(c['varies']) or '—'}.",
            "",
            "| metric | n | mean diff | 95% CI | dz | p (perm.) | p Holm | p BH | status |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for m, r in c["metrics"].items():
            if not r.get("n"):
                lines.append(f"| {m} | 0 | n/a | n/a | n/a | n/a | n/a | n/a | NOT MEASURED |")
                continue
            lines.append(
                f"| {m} | {r['n']} | {_f(r['mean'])} | [{_f(r['ci95'][0])}, {_f(r['ci95'][1])}] | {_f(r['dz'])} | {_f(r['p'])} | "
                f"{_f(r['p_holm'])} | {_f(r['p_bh'])} | {r['status']} |"
            )
    lines += [
        "",
        "## Arms",
        "| arm | metric | n | mean | median | SD | 95% CI of mean | undefined |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for a in an["arms"]:
        for m in an["metrics"]:
            d = an["descriptives"][a][m]
            if d.get("n"):
                lines.append(
                    f"| {a} | {m} | {d['n']} | {_f(d['mean'])} | {_f(d['median'])} | {_f(d['sd'])} | "
                    f"[{_f(d['ci95_mean'][0])}, {_f(d['ci95_mean'][1])}] | {d['undefined']} |"
                )
    z = an["ziran"]
    lines += ["", "## Ziran records"]
    for a, e in z.items():
        bits = []
        if "reachability" in e:
            r = e["reachability"]
            bits.append(
                f"reachability: {r['opened_predictions']} operations predicted runnable after a change, {r['opened_then_acted']} acted in the next "
                f"epoch (opened but not used: {r['opened_not_used']}); {r['closed_predictions']} predicted blocked, "
                f"{r['closed_consistent']} silent"
            )
        oc = e["observation_changes"]
        bits.append(
            f"observation changes: {oc['controller']} by the controller, {oc['protocol']} by the protocol, {oc['rejected_by_authority_or_budget']} "
            f"rejected (authority or budget); channels gained {oc['channels_gained']}, lost {oc['channels_lost']}"
        )
        if "meta_revision" in e:
            m = e["meta_revision"]
            bits.append(
                f"meta-revision: {m['revisions']} revisions in {m['runs_with_a_revision']} of {m['runs_with_meta']} runs "
                f"({m['exhausted_rules']} rules exhausted)"
            )
        if "history_reentry" in e:
            h = e["history_reentry"]
            bits.append(
                f"history re-entry: {h['reinsertions']} reinsertions, {h['with_downstream_event']} with a downstream event"
            )
        lines.append(f"- **{a}**: " + "; ".join(bits) + ".")
    lines += [
        "",
        "## Execution constraints",
        "Runs are reproducible bit-for-bit only on the same machine and software versions. Outliers (listed in analysis.json) "
        "were kept. `first_ignition_mean` is censored at the horizon for kinds that never ignite. " + INTERPRETATION_BOUNDARY,
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------- tables
def _csv(rows: list[dict], cols: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
    return buf.getvalue()


def tables(study: Study, an: dict) -> dict[str, str]:
    runs = study.runs()
    mets = an["metrics"]
    out = {
        "runs.csv": _csv(
            [
                {
                    "experiment_id": study.id,
                    "arm": r["arm"],
                    "index": r["index"],
                    "gen": r["gen"],
                    "seed": r["seed"],
                    "status": r["status"],
                    "wall_s": r.get("wall_s"),
                    **(r.get("metrics") or {}),
                }
                for r in runs
            ],
            ["experiment_id", "arm", "index", "gen", "seed", "status", "wall_s", *mets],
        )
    }
    out["descriptives.csv"] = _csv(
        [
            {
                "experiment_id": study.id,
                "arm": a,
                "metric": m,
                **an["descriptives"][a][m],
                "ci95_lo": (an["descriptives"][a][m].get("ci95_mean") or [None, None])[0],
                "ci95_hi": (an["descriptives"][a][m].get("ci95_mean") or [None, None])[1],
            }
            for a in an["arms"]
            for m in mets
        ],
        [
            "experiment_id",
            "arm",
            "metric",
            "n",
            "undefined",
            "mean",
            "median",
            "sd",
            "var",
            "min",
            "max",
            "q1",
            "q3",
            "ci95_lo",
            "ci95_hi",
        ],
    )
    rows = []
    for c in an["contrasts"]:
        for m, r in c["metrics"].items():
            rows.append(
                {
                    "experiment_id": study.id,
                    "contrast": c["id"],
                    "a": c["a"],
                    "b": c["b"],
                    "evidence": c["evidence"],
                    "metric": m,
                    "n": r.get("n"),
                    "mean_diff": r.get("mean"),
                    "ci95_lo": (r.get("ci95") or [None, None])[0],
                    "ci95_hi": (r.get("ci95") or [None, None])[1],
                    "dz": r.get("dz"),
                    "p_perm": r.get("p"),
                    "p_holm": r.get("p_holm"),
                    "p_bh": r.get("p_bh"),
                    "status": r.get("status"),
                }
            )
    out["contrasts.csv"] = _csv(
        rows,
        [
            "experiment_id",
            "contrast",
            "a",
            "b",
            "evidence",
            "metric",
            "n",
            "mean_diff",
            "ci95_lo",
            "ci95_hi",
            "dz",
            "p_perm",
            "p_holm",
            "p_bh",
            "status",
        ],
    )
    out["accounting.csv"] = _csv(
        [{"experiment_id": study.id, "arm": a, **v, "errors": "; ".join(v["errors"])} for a, v in an["accounting"].items()],
        ["experiment_id", "arm", "planned", "ok", "failed", "timeout", "not_run", "failure_rate", "errors"],
    )
    zrows = []
    for a, e in an["ziran"].items():
        r = e.get("reachability") or {}
        zrows.append(
            {
                "experiment_id": study.id,
                "arm": a,
                **{f"reach_{k}": v for k, v in r.items() if k != "note"},
                **e["observation_changes"],
                **{f"meta_{k}": v for k, v in (e.get("meta_revision") or {}).items() if k not in ("note", "final_rules")},
                **{f"history_{k}": v for k, v in (e.get("history_reentry") or {}).items()},
            }
        )
    out["ziran.csv"] = _csv(zrows, sorted({k for r in zrows for k in r}, key=lambda k: (k != "experiment_id", k != "arm", k)))
    return out


# ----------------------------------------------------------------------------------------------- figures (SVG)
PAL = ["#1b6ca8", "#c8553d", "#3b8b5a", "#8a5fbf", "#b08a00", "#5f6b73", "#a8325e", "#2a9d8f", "#6d597a"]


def _svg(w: int, h: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{html.escape(title)}" '
        f'font-family="Helvetica, Arial, sans-serif" font-size="11"><rect width="{w}" height="{h}" fill="#ffffff"/>{body}</svg>'
    )


def _text(x: float, y: float, s: str, anchor: str = "start", size: int = 11, fill: str = "#222", rot: int = 0) -> str:
    t = f' transform="rotate({rot} {x} {y})"' if rot else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{size}" fill="{fill}"{t}>{html.escape(str(s))}</text>'
    )


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi <= lo:
        return [lo]
    step = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(step))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= step), default=step)
    t = math.ceil(lo / step) * step
    out = []
    while t <= hi + 1e-9:
        out.append(round(t, 10))
        t += step
    return out


def fig_arms(study: Study, an: dict, metric: str) -> tuple[str, str]:
    runs = study.runs()
    arms = an["arms"]
    W, H, L, R, T, B = 760, 360, 70, 20, 30, 80
    vals = {
        a: [
            r["metrics"][metric]
            for r in runs
            if r["arm"] == a and r["status"] == "ok" and r.get("metrics") and r["metrics"].get(metric) is not None
        ]
        for a in arms
    }
    allv = [v for x in vals.values() for v in x]
    if not allv:
        return "", "no data"
    lo, hi = min(allv), max(allv)
    pad = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - pad, hi + pad
    X = lambda i: L + (i + 0.5) * (W - L - R) / len(arms)  # noqa: E731
    Y = lambda v: T + (hi - v) * (H - T - B) / (hi - lo)  # noqa: E731
    body = [
        f'<line x1="{L}" y1="{T}" x2="{L}" y2="{H - B}" stroke="#555"/><line x1="{L}" y1="{H - B}" x2="{W - R}" y2="{H - B}" stroke="#555"/>'
    ]
    for t in _ticks(lo, hi):
        body.append(
            f'<line x1="{L - 4}" y1="{Y(t):.1f}" x2="{W - R}" y2="{Y(t):.1f}" stroke="#e5e5e5"/>'
            + _text(L - 8, Y(t) + 4, _f(t), "end")
        )
    for i, a in enumerate(arms):
        c = PAL[i % len(PAL)]
        for j, v in enumerate(vals[a]):
            jx = (j % 7 - 3) * 4
            body.append(f'<circle cx="{X(i) + jx:.1f}" cy="{Y(v):.1f}" r="3" fill="{c}" fill-opacity="0.55"/>')
        d = an["descriptives"][a][metric]
        if d.get("n"):
            lo_ci, hi_ci = d["ci95_mean"]
            if lo_ci is not None and hi_ci is not None and math.isfinite(lo_ci) and math.isfinite(hi_ci):
                body.append(
                    f'<line x1="{X(i):.1f}" y1="{Y(lo_ci):.1f}" x2="{X(i):.1f}" y2="{Y(hi_ci):.1f}" stroke="#111" stroke-width="2"/>'
                )
            body.append(
                f'<line x1="{X(i) - 14:.1f}" y1="{Y(d["mean"]):.1f}" x2="{X(i) + 14:.1f}" y2="{Y(d["mean"]):.1f}" stroke="#111" stroke-width="2.5"/>'
            )
        body.append(_text(X(i), H - B + 14, a, "end", 10, rot=-30))
    body.append(_text(16, (T + H - B) / 2, metric, "middle", 11, rot=-90))
    body.append(_text(L, 16, f"{metric} by arm (points: seeds; bar: mean with bootstrap 95% CI)  —  {study.id}", "start", 11))
    cap = (
        f"Figure: {metric} for each arm, one point per seed; black bar = mean with bootstrap 95% interval. Experiment {study.id} "
        f"(mode {an['mode']}, n = {an['n_seeds']} seeds per arm)."
    )
    return _svg(W, H, "".join(body), f"{metric} by arm"), cap


def fig_forest(study: Study, an: dict, metric: str) -> tuple[str, str]:
    rows = [(c["id"], f"{c['a']} − {c['b']}", c["metrics"].get(metric)) for c in an["contrasts"]]
    rows = [(i, lab, r) for i, lab, r in rows if r and r.get("n") and all(v is not None and math.isfinite(v) for v in r["ci95"])]
    if not rows:
        return "", "no data"
    W, H0 = 760, 70 + 26 * len(rows)
    L, R, T = 250, 30, 36
    lo = min(r["ci95"][0] for _, _, r in rows)
    hi = max(r["ci95"][1] for _, _, r in rows)
    lo, hi = min(lo, 0), max(hi, 0)
    pad = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - pad, hi + pad
    X = lambda v: L + (v - lo) * (W - L - R) / (hi - lo)  # noqa: E731
    body = [f'<line x1="{X(0):.1f}" y1="{T - 8}" x2="{X(0):.1f}" y2="{H0 - 28}" stroke="#999" stroke-dasharray="4 3"/>']
    for t in _ticks(lo, hi):
        body.append(
            f'<line x1="{X(t):.1f}" y1="{H0 - 28}" x2="{X(t):.1f}" y2="{H0 - 24}" stroke="#555"/>'
            + _text(X(t), H0 - 12, _f(t), "middle", 10)
        )
    for k, (cid, lab, r) in enumerate(rows):
        y = T + 26 * k + 10
        body.append(_text(L - 10, y + 4, f"{cid}  {lab}", "end", 11))
        body.append(
            f'<line x1="{X(r["ci95"][0]):.1f}" y1="{y}" x2="{X(r["ci95"][1]):.1f}" y2="{y}" stroke="{PAL[k % len(PAL)]}" stroke-width="2"/>'
            f'<circle cx="{X(r["mean"]):.1f}" cy="{y}" r="4" fill="{PAL[k % len(PAL)]}"/>'
        )
    body.append(_text(L, 18, f"Paired difference in {metric} (a − b) with bootstrap 95% CI  —  {study.id}", "start", 11))
    cap = (
        f"Figure: paired difference in {metric} for each declared contrast (point: mean over seeds; line: bootstrap 95% interval; dashed "
        f"line: zero). Experiment {study.id}, n = {an['n_seeds']} paired seeds; mode {an['mode']}."
    )
    return _svg(W, H0, "".join(body), f"forest {metric}"), cap


def fig_reachability(study: Study, an: dict) -> tuple[str, str]:
    items = [
        (a, e["reachability"])
        for a, e in an["ziran"].items()
        if e.get("reachability") and (e["reachability"]["opened_predictions"] or e["reachability"]["closed_predictions"])
    ]
    if not items:
        return "", "no reachability predictions recorded"
    W, H, L, T = 760, 70 + 44 * len(items), 190, 40
    body = []
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        x = L + t * (W - L - 30)
        body.append(
            f'<line x1="{x:.1f}" y1="{T - 6}" x2="{x:.1f}" y2="{H - 24}" stroke="#e5e5e5"/>'
            + _text(x, H - 10, f"{t:.0%}", "middle", 10)
        )
    for k, (a, r) in enumerate(items):
        y = T + 44 * k
        body.append(_text(L - 10, y + 16, a, "end", 11))
        for j, (key, n_key, col, lab) in enumerate(
            (
                ("opened_success_rate", "opened_predictions", "#1b6ca8", "opened → acted"),
                ("closed_consistency_rate", "closed_predictions", "#c8553d", "closed → silent"),
            )
        ):
            v = r[key]
            w = (v or 0) * (W - L - 30)
            body.append(
                f'<rect x="{L}" y="{y + j * 16}" width="{w:.1f}" height="12" fill="{col}"/>'
                + _text(L + w + 6, y + j * 16 + 10, f"{lab}: {_f(v) if v is not None else 'n/a'} (n={r[n_key]})", "start", 10)
            )
    body.append(_text(L, 20, f"Reachability predictions versus what the operations did next epoch  —  {study.id}", "start", 11))
    cap = (
        f"Figure: share of predicted openings after which the operation acted in the next epoch, and of predicted closings after which it "
        f"stayed silent, per arm. The gap from 100% is the estimation error of the reachability record. Experiment {study.id}."
    )
    return _svg(W, H, "".join(body), "reachability predictions"), cap


def png_available() -> str | None:
    for tool in ("rsvg-convert", "inkscape", "magick", "convert"):
        if shutil.which(tool):
            return tool
    return None


def to_png(svg_path: Path) -> Path | None:
    tool = png_available()
    if tool is None:
        return None
    png = svg_path.with_suffix(".png")
    cmd = {
        "rsvg-convert": ["rsvg-convert", "-o", str(png), str(svg_path)],
        "inkscape": ["inkscape", str(svg_path), "-o", str(png)],
        "magick": ["magick", str(svg_path), str(png)],
        "convert": ["convert", str(svg_path), str(png)],
    }[tool]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return png if png.exists() else None


# ----------------------------------------------------------------------------------------------- bundle
def build(study: Study, an: dict) -> dict:
    """Write report/ (methods.md, results.md, tables, figures, figures.json) and return its index."""
    rep = study.path / "report"
    rep.mkdir(exist_ok=True)
    files: dict[str, str] = {"methods.md": methods(study, an), "results.md": results(study, an)}
    files.update(tables(study, an))
    figs = []
    for i, m in enumerate(an["metrics"][:6]):
        svg, cap = fig_arms(study, an, m)
        if svg:
            figs.append((f"fig{len(figs) + 1}_arms_{m}.svg", svg, cap, "descriptives.csv"))
        if i == 0:
            svg, cap = fig_forest(study, an, m)
            if svg:
                figs.append((f"fig{len(figs) + 1}_forest_{m}.svg", svg, cap, "contrasts.csv"))
    svg, cap = fig_reachability(study, an)
    if svg:
        figs.append((f"fig{len(figs) + 1}_reachability.svg", svg, cap, "ziran.csv"))
    index = []
    for name, svg, cap, src in figs:
        files[name] = svg
        index.append({"file": name, "experiment_id": study.id, "caption": cap, "data": src, "png": None})
    for name, text in files.items():
        (rep / name).write_text(text)
    for f in index:
        png = to_png(rep / f["file"])
        f["png"] = png.name if png else None
    (rep / "figures.json").write_text(
        json.dumps(
            {
                "figures": index,
                "png": "written" if png_available() else "skipped: no SVG converter (rsvg-convert, inkscape, magick) installed",
                "pdf": "not produced (no PDF toolchain; SVG and CSV are the portable formats)",
            },
            indent=1,
        )
    )
    (rep / "tables.md").write_text(
        "# Tables — " + study.id + "\n\nSee results.md for the formatted tables; the CSV files in this directory "
        "hold the same numbers (runs.csv: every run; descriptives.csv; contrasts.csv; accounting.csv; ziran.csv).\n"
    )
    study.log("report_built", figures=len(index))
    return {"dir": str(rep), "files": sorted(p.name for p in rep.iterdir()), "figures": index}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


REPRODUCE_MD = """# Reproducing experiment {id}

1. Environment: Python {python}, {deps}. Results are reproducible bit-for-bit on the same machine and software versions;
   on other platforms the address hierarchy can differ and agreement is not expected (see docs/REPRODUCIBILITY.md).
2. Code: git commit `{commit}` (working tree {dirty} at run time). Source digest of `backend/xzr`: `{source}`.
3. Verify this package: `python -m xzr.study verify <this directory>` (checks every file against checksums.json).
4. Re-execute: `python -m xzr.study reproduce <this directory> --out <new root> [--procs N]` runs the registered protocol
   (`protocol.registered.json`, digest `{digest}`) again with the same seeds and compares every run record (wall time, CPU and
   memory excluded). The comparison is written to `reproduction.json` in the new experiment directory.
5. Re-analyse without re-running: `python -m xzr.study analyse <this directory>`; `python -m xzr.study report <this directory>`.
"""


def source_digest() -> str:
    from .runner import REPO

    h = hashlib.sha256()
    for p in sorted((REPO / "backend" / "xzr").rglob("*.py")):
        h.update(str(p.relative_to(REPO)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def package(study: Study, out_zip: Path | None = None) -> Path:
    study.log("packaged")  # logged first: the checksums below must cover the final log
    man = study.manifest()
    info = man["environment"]
    (study.path / "REPRODUCE.md").write_text(
        REPRODUCE_MD.format(
            id=study.id,
            python=info["python"],
            deps=", ".join(f"{k} {v}" for k, v in info["dependencies"].items() if v),
            commit=info["git_commit"],
            dirty="dirty" if info["git_dirty"] else "clean",
            source=source_digest(),
            digest=man["protocol_digest"],
        )
    )
    files = sorted(
        p
        for p in study.path.rglob("*")
        if p.is_file() and p.name not in ("checksums.json", "stop.flag") and not p.name.endswith(".tmp")
    )
    (study.path / "checksums.json").write_text(
        json.dumps(
            {
                "schema": "xzr.checksums/1",
                "experiment_id": study.id,
                "source_digest": source_digest(),
                "files": {str(p.relative_to(study.path)): _sha(p) for p in files},
            },
            indent=1,
        )
    )
    out_zip = out_zip or study.path.with_suffix(".zip")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(study.path.rglob("*")):
            if p.is_file() and not p.name.endswith(".tmp"):
                z.write(p, f"{study.id}/{p.relative_to(study.path)}")
    return out_zip


def verify(path: Path) -> dict:
    """Check a study directory against its checksums.json."""
    ck = json.loads((Path(path) / "checksums.json").read_text())
    bad, missing = [], []
    for rel, h in ck["files"].items():
        p = Path(path) / rel
        if not p.exists():
            missing.append(rel)
        elif _sha(p) != h:
            bad.append(rel)
    extra = sorted(
        str(p.relative_to(path))
        for p in Path(path).rglob("*")
        if p.is_file()
        and str(p.relative_to(path)) not in ck["files"]
        and p.name not in ("checksums.json", "stop.flag", "REPRODUCE.md", "reproduction.json")
        and not p.name.endswith(".tmp")
        and p.suffix != ".zip"
    )
    return {"ok": not bad and not missing, "files": len(ck["files"]), "mismatched": bad, "missing": missing, "unlisted": extra}
