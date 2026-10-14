"""Figures of the M9 results, drawn only from the result files (backend/experiments/results/lab9/).

Every bar is a value read from a published result file; error bars are the published bootstrap 95 % intervals of the
paired mean difference, divided by the contrast's scale (the larger of the two condition means) to give relative
effects. Nothing is simulated here.

Usage (needs matplotlib; not a runtime dependency):
    python backend/scripts/m9_figures.py <results/lab9 dir> <output dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150,
                     "savefig.bbox": "tight"})
DARK, MID, LIGHT, ACCENT = "#202124", "#6b6f76", "#b9bcc2", "#9a3412"


def rel(c: dict, m: str) -> tuple[float, float, float, str]:
    v = c[m]
    s = v.get("scale") or 1.0
    lo, hi = v.get("ci95") or [v.get("mean", 0.0), v.get("mean", 0.0)]
    return v.get("mean", 0.0) / s, (lo if lo is not None else 0.0) / s, (hi if hi is not None else 0.0) / s, v["status"]


def bars(ax, labels, vals, title, ylabel="relative effect (paired mean / scale)"):
    xs = range(len(labels))
    for x, (m, lo, hi, st) in zip(xs, vals, strict=True):
        col = DARK if st == "DETECTED" else LIGHT if st in ("IDENTICAL", "EQUIVALENT") else MID
        ax.bar(x, m, color=col, width=0.65)
        ax.plot([x, x], [lo, hi], color=ACCENT, lw=1.2)
        ax.text(x, (hi if m >= 0 else lo) + (0.03 if m >= 0 else -0.03), st[:4], ha="center",
                va="bottom" if m >= 0 else "top", fontsize=6.5, color=DARK)
    ax.axhline(0, color=DARK, lw=0.6)
    lo_all = min(v[1] for v in vals)
    hi_all = max(v[2] for v in vals)
    pad = 0.15 * max(hi_all - lo_all, 1e-6)
    ax.set_ylim(min(lo_all, 0) - pad, max(hi_all, 0) + pad)
    ax.set_xticks(list(xs), labels, rotation=30, ha="right")
    ax.set_title(title, fontsize=9, pad=10)
    ax.set_ylabel(ylabel, fontsize=8)


def fig_factorial(R: Path, out: Path) -> str:
    d = json.loads((R / "m9ab.json").read_text())
    c = d["contrasts"]
    keys = [("dependence LS: B with A vs without A", "LS shared/live"),
            ("dependence FS: B with A vs without A", "FS shared/frozen"),
            ("dependence LP: B with A vs without A", "LP separated/live"),
            ("dependence FP: B with A vs without A", "FP separated/frozen"),
            ("physical-only pathway: inert A (shared) vs no A", "inert A (shared)"),
            ("dependence G-separated: B with A vs without A", "gantries private"),
            ("dependence W-separated: B with A vs without A", "A's wear exempt"),
            ("dependence M-separated: B with A vs without A", "material private"),
            ("dependence Q-separated: B with A vs without A", "queues private"),
            ("dependence P-separated: B with A vs without A", "priority to B/C")]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.4))
    for ax, m, t in zip(axs, ("completed", "pairs", "latency_mean"),
                        ("B completed transfers", "B distinct experiments", "B request-to-completion latency"), strict=True):
        bars(ax, [k[1] for k in keys], [rel(c[k[0]], m) for k in keys], t)
    fig.suptitle("Fig. 1  M9-A/B: B's dependence on A by pathway (24 paired seeds; dark = DETECTED)", fontsize=10)
    p = out / "fig1_factorial.png"
    fig.savefig(p)
    plt.close(fig)
    return p.name


def fig_revision(R: Path, out: Path) -> str:
    d = json.loads((R / "m9d.json").read_text())
    ms = [("distinct_observed_pairs", "distinct observed pairs"), ("redundant_observations", "redundant observations"),
          ("paths", "reachable experiments"), ("completed", "completed transfers"), ("true_gain", "true gain"),
          ("gain_per_completed", "gain per transfer")]
    fig, axs = plt.subplots(1, 4, figsize=(13, 3.4), sharey=True)
    for ax, (k, t) in zip(axs, (("O vs F", "O (M5 revision)"), ("Oloc vs F", "relocation only"),
                                ("Owin vs F", "window only"), ("Oout vs F", "outcome-guided")), strict=True):
        bars(ax, [x[1] for x in ms], [rel(d["contrasts"][k], x[0]) for x in ms], t + " vs fixed")
    fig.suptitle("Fig. 2  M9-D: what observation revision changes (system A, 24 seeds)", fontsize=10)
    p = out / "fig2_revision.png"
    fig.savefig(p)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 3.2))
    labels, vals = [], []
    for src, k in (("main", "O vs F"), ("held-out", "O vs F"), ("main", "Oout vs F"), ("held-out", "Oout vs F")):
        c = d["contrasts"][k] if src == "main" else d["heldout"][k]
        for m in ("paths", "true_gain"):
            labels.append(f"{k.split()[0]} {src}: {'reachable' if m == 'paths' else 'true gain'}")
            vals.append(rel(c, m))
    bars(ax, labels, vals, "Fig. 3  Reachability vs effectiveness, main and held-out worlds")
    p2 = out / "fig3_reachability.png"
    fig.savefig(p2)
    plt.close(fig)
    return p.name + "," + p2.name


def fig_variables(R: Path, out: Path) -> str:
    d = json.loads((R / "m9e.json").read_text())
    dg = d["diagnostics"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.3))
    conds = ["F", "V", "Vr", "Flo", "Vlo", "Vrlo"]
    for ax, m, t in ((axs[0], "changed_without_variables", "share of decisions changed without the variables"),
                     (axs[1], "obs_true_corr", "corr(observed outcome, true effect)")):
        vals = [dg[c].get(m) or 0.0 for c in conds]
        ax.bar(conds, vals, color=MID)
        ax.set_title(t, fontsize=9)
        ax.axhline(0, color=DARK, lw=0.6)
    fig.suptitle("Fig. 4  M9-E: variables are used in decisions, but the measurement says little about the true effect",
                 fontsize=10)
    p = out / "fig4_variables.png"
    fig.savefig(p)
    plt.close(fig)
    return p.name


def fig_history(R: Path, out: Path) -> str:
    d = json.loads((R / "m9f.json").read_text())
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.4))
    pairs = ["H2 vs H1", "H1 vs H0", "H2 vs H3", "H2 vs H4", "H1 vs H6", "H2 vs H7", "H2lo vs H1lo", "H2~ vs H2"]
    bars(axs[0], pairs, [rel(d["contrasts"][k], "true_gain_post") for k in pairs], "true gain after the change")
    conds = ["H1", "H2", "H3", "H6", "H7", "H1lo", "H2lo"]
    axs[1].bar(conds, [d["diagnostics"][c]["changed_without_memory"] or 0 for c in conds], color=MID)
    axs[1].set_title("share of decisions changed without memory", fontsize=9)
    fig.suptitle("Fig. 5  M9-F: history steers choices without a detectable benefit (system C, 24 seeds)", fontsize=10)
    p = out / "fig5_history.png"
    fig.savefig(p)
    plt.close(fig)
    return p.name


def fig_extinction(R: Path, out: Path) -> str:
    d = json.loads((R / "m9c.json").read_text())
    conds = list(d["counts"])
    k = d["counts"]
    ext = [k[c]["extinct"]["count"] for c in conds]
    rei = [k[c]["reignited"]["count"] for c in conds]
    same = [k[c]["restored_same"]["count"] for c in conds]
    fig, ax = plt.subplots(figsize=(10, 3.4))
    x = range(len(conds))
    ax.bar([i - 0.27 for i in x], ext, width=0.27, color=DARK, label="extinct")
    ax.bar(x, rei, width=0.27, color=MID, label="re-ignited")
    ax.bar([i + 0.27 for i in x], same, width=0.27, color=LIGHT, label="re-ignited, same dependency")
    ax.set_xticks(list(x), conds)
    ax.set_ylabel("seeds (of 24)")
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("Fig. 6  M9-C: extinction and re-ignition by condition", fontsize=10)
    p = out / "fig6_extinction.png"
    fig.savefig(p)
    plt.close(fig)
    spent = {c: [r["systems"][d["conditions"][c]["extinction"]["system"]]["spent"] for r in d["per_run"] if r["cond"] == c]
             for c in conds}
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.boxplot([spent[c] for c in conds], tick_labels=conds)
    ax.set_ylabel("budget spent (of 24)")
    ax.set_title("Fig. 7  Resource consumption: refused requests exhaust the budget after an unrepaired failure",
                 fontsize=10)
    p2 = out / "fig7_budget.png"
    fig.savefig(p2)
    plt.close(fig)
    return p.name + "," + p2.name


def fig_worlds(R: Path, out: Path) -> str:
    d = json.loads((R / "m9w.json").read_text())
    base = json.loads((R / "m9ab.json").read_text())["contrasts"]
    worlds = ["base"] + list(d["contrasts"])
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
    for ax, m, t in zip(axs, ("completed", "pairs", "latency_mean"), ("completed", "distinct experiments", "latency"),
                        strict=True):
        vals = [rel(base["dependence LS: B with A vs without A"], m)] + [
            rel(d["contrasts"][w]["dependence (shared, live)"], m) for w in worlds[1:]]
        bars(ax, worlds, vals, "B's dependence on A: " + t)
    fig.suptitle("Fig. 8  Cross-world: the physical-resource dependence across six laboratories", fontsize=10)
    p = out / "fig8_worlds.png"
    fig.savefig(p)
    plt.close(fig)
    return p.name


def fig_sensitivity(S: Path, out: Path) -> str:
    d = json.loads(S.read_text())
    keys = ["dependence LS", "dependence FP", "communication effect on dependence", "resource effect on dependence",
            "residual dependence (F, P) vs zero", "physical-only pathway", "mediation G", "mediation W", "mediation M"]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.4), sharey=True)
    for ax, lab in zip(axs, ("physical", "delivered"), strict=True):
        vals = []
        for k in keys:
            v = d["contrasts"][lab][k]
            s = max(abs(v["mean_x"] or 0), abs(v["mean_y"] or 0), 1e-9)
            lo, hi = v["ci95"] or [v["mean"], v["mean"]]
            vals.append((v["mean"] / s, lo / s, hi / s, v["status"]))
        bars(ax, keys, vals, f"latency, {lab} definition")
    fig.suptitle("Fig. 9  Latency sensitivity (exploratory): physical completion vs successful delivery", fontsize=10)
    p = out / "fig9_latency_sensitivity.png"
    fig.savefig(p)
    plt.close(fig)
    return p.name


def fig_substitutes(S: Path, out: Path) -> str:
    d = json.loads(S.read_text())["summary"]
    states = [("available", "available_mean"), ("detectable", "detectable_mean"), ("selectable", "selectable_mean"),
              ("selected and\nexecutable", "selected_executable_share"), ("executed", "executed_substitutes")]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for i, c in enumerate(("X4", "X4b")):
        xs = [j + 0.38 * i for j in range(len(states))]
        vals = [d[c][k] for _, k in states]
        ax.bar(xs, vals, width=0.38, color=(MID, DARK)[i], label=c)
        for x, v in zip(xs, vals, strict=True):
            ax.text(x, max(v, 0) * 1.15 + 0.05, f"{v:.3g}", ha="center", va="bottom", fontsize=7)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xticks([j + 0.19 for j in range(len(states))], [n for n, _ in states])
    ax.set_ylabel("mean per decision (executed: per run)\n(symmetric log scale)", fontsize=8)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("Fig. 10  Substitute paths during the outage (exploratory): available in the laboratory, "
                 "but none detectable as executable", fontsize=10)
    p = out / "fig10_substitutes.png"
    fig.savefig(p)
    plt.close(fig)
    return p.name


def main() -> None:
    R, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    made = [fig_factorial(R, out), fig_revision(R, out), fig_variables(R, out), fig_history(R, out),
            fig_extinction(R, out), fig_worlds(R, out)]
    ex = R / "exploratory"
    if (ex / "latency_sensitivity.json").exists():
        made.append(fig_sensitivity(ex / "latency_sensitivity.json", out))
    if (ex / "substitutes.json").exists():
        made.append(fig_substitutes(ex / "substitutes.json", out))
    print("\n".join(made))


if __name__ == "__main__":
    main()
