"""Writes docs/ECOSYSTEM_MEOS_STAGE6.md. The prose is here; every number in a table is copied from the saved results (docs/ecosystem/experiments_stage6*.json) or from the evidence fragments (docs/ecosystem/stage6_fragments/*.md).

    python backend/scripts/make_stage6_doc.py            # writes the document
    python backend/scripts/make_stage6_doc.py --check    # fails if the document on disk differs from what the data produce

Raw data and interpretation are kept apart: the tables are the data, the words under them are the interpretation and its limits."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "ecosystem"
DOC = ROOT / "docs" / "ECOSYSTEM_MEOS_STAGE6.md"
FRAG = DOCS / "stage6_fragments"


def load(name: str) -> dict:
    return json.loads((DOCS / f"experiments_stage6{name}.json").read_text())


A, B, C, CT, F = load(""), load("_refine"), load("_cross"), load("_controllers"), load("_final")
A0, F0 = load("_all_horizons_criterion"), load("_final_all_horizons_criterion")
S5 = json.loads((DOCS / "experiments_stage5_midrun.json").read_text())
OPEN = json.loads((DOCS / "experiments_stage6_open_windows.json").read_text())
MECH = json.loads((DOCS / "experiments_stage6_open_mechanism.json").read_text())
FU = json.loads((DOCS / "experiments_stage6_followup.json").read_text())
REPRO5 = json.loads((DOCS / "evidence" / "stage5_reproduction_stage6.json").read_text())
REPRO6 = json.loads((DOCS / "evidence" / "stage6_reproduction.json").read_text())


def frag(name: str) -> str:
    p = FRAG / f"{name}.md"
    return p.read_text().strip() if p.exists() else f"*(fragment {name}.md has not been written)*"


def tbl(head: list[str], rows: list[list]) -> str:
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|", *("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows)]) + "\n"


def wtext(w: list[list[int]]) -> str:
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in w) if w else "none"


def part_text(parts: list) -> str:
    return " + ".join(f"{a}" + (f" {m}" if m else "") + (f" (for {d})" if d else "") for a, m, d in parts)


ST = F["stress_table"]
SID = [r["stress"] for r in ST]
LABEL = {r["stress"]: r["label"] for r in ST}


def actions_table() -> str:
    return tbl(["action", "class", "family", "status", "magnitudes", "durations", "latency", "side effect", "reversibility", "declared cost"],
               [[a["id"], a["class"], a["family"], a["status"], ", ".join(map(str, a["magnitudes"])) or "-", ", ".join(map(str, a["durations"])) if len(a["durations"]) > 1 else "-", a["latency"] or "-", a["side_effect"] or "-", a["reversibility"] or "-",
                  "; ".join(f"{k}: {v}" for k, v in a["declared_cost"].items()) or "-"] for a in A["actions"] if a["status"] != "not implemented"])


def not_impl() -> str:
    return "\n".join(f"- `{a['id']}` ({a['status']}{'; built afterwards, section 30' if a['id'] in ('coupling.bypass', 'resource.rerouting', 'address.temporary_local') else ''}): {a['note']}" for a in A["actions"] if a["status"] in ("not implemented", "proxy"))


def stress_table() -> str:
    rows = []
    for r in ST:
        ref = r["reference_repair"]
        hz = r["horizons_of_reference_repair"]
        hzt = "-" if not hz else (f"{hz['short']}/{hz['n']}, {hz['medium']}/{hz['n']}, {hz['long']}/{hz['n']}" if "short" in hz else "combined: see section 14")
        rows.append([r["label"], wtext(r["internal_reconfiguration"]["windows"]), wtext(r["world_single"]["windows"]), wtext(r["combined"]["windows"]),
                     "; ".join(f"{m['action']} {m['magnitude']}" for m in r["minimum_effective"]) or "-", wtext(r["timing_window_fragments"]), (f"OPEN_THROUGH_TESTED_LIMIT: effective at every tested tick to {r['tested_range_end']}" if r["irreversibility"] == "OPEN_THROUGH_TESTED_LIMIT" else r["latest_successful_repair_tick"] if r["latest_successful_repair_tick"] is not None else "-"),
                     ("null (OPEN_THROUGH_TESTED_LIMIT: no closure found up to tick " + str(r["tested_range_end"]) + ")" if r["irreversibility"] == "OPEN_THROUGH_TESTED_LIMIT" else r["irreversible_tick"] if r["irreversible_tick"] is not None else "from the first tested tick (101): NO_EFFECTIVE_TICK"), hzt,
                     (f"{ref['normalised_cost_equal_weights']} ({part_text(ref['parts'])} @{ref['t']})" if ref else "-"), r["unrepaired_collapse_tick"], f"**{r['classification_at_decision_tick_113']}** / **{r['classification_at_any_tested_tick']}**"])
    return tbl(["stress", "internal reconfiguration: effective ticks", "world-state repair (single): effective ticks", "combined repair: effective ticks", "minimum effective action", "all effective ticks", "latest successful repair tick", "earliest irreversible tick",
                "reference repair, exploration seeds ok at short / medium / long", "cost of the reference repair (equal-weight normalised) and its setting", "unrepaired collapse tick", "classification: at the decision tick 113 / at any tested tick"], rows)


def flags_table() -> str:
    return tbl(["stress", "flags", "failure ids over the tested grid (cells not effective)"], [[r["label"], "; ".join(r["flags"]) or "-", ", ".join(f"{k} {v}" for k, v in sorted(r["failure_reasons_in_the_tested_grid"].items(), key=lambda kv: -kv[1])[:6])] for r in ST])


def windows_table() -> str:
    rows = []
    for w in B["B1_windows"]:
        rows.append([LABEL[w["stress"]], part_text(w["parts"]), wtext(w["effective_intervals"]), w["earliest_effective_tick"] or "-", w["latest_effective_tick"] or "-", ", ".join(map(str, w["near_miss_ticks"][:10])) + (" …" if len(w["near_miss_ticks"]) > 10 else "") or "-"])
    return tbl(["stress", "setting", "effective ticks (exploration and validation seeds all effective)", "earliest", "latest", "near-miss ticks (3-4 of 5)"], rows)


def pulse_table() -> str:
    rows = []
    for s in B["B2_pulse_sweeps"]:
        ph: list[list] = []
        for r in s["rows"]:
            if ph and ph[-1][0] == r["phase"]:
                ph[-1][2] = r["magnitude"]
            else:
                ph.append([r["phase"], r["magnitude"], r["magnitude"]])
        rows.append([LABEL[s["stress"]], "none" if s["effective_band"][0] is None else f"{s['effective_band'][0]} - {s['effective_band'][1]}", "; ".join(f"{p} {a}-{b}" for p, a, b in ph)])
    return tbl(["stress", "effective pulse band (tick 113)", "phase by pulse size"], rows)


def min_table() -> str:
    rows = []
    for name, v in B["B3_minimum_intervention"].items():
        by = {t: m for t, m in v["minimum_effective_magnitude_by_tick"].items() if m is not None}
        rows.append([name, LABEL[v["stress"]], v["minimum_effective_magnitude_overall"] if v["minimum_effective_magnitude_overall"] is not None else "none effective", "; ".join(f"@{t}: {m}" for t, m in by.items()) or "-", wtext([[a, a] for a in v["effective_ticks"]]) if v["effective_ticks"] else "-"])
    return tbl(["intervention", "stress", "minimum effective magnitude (any tick)", "minimum by action tick", "ticks with an effective magnitude"], rows)


def single_rows(family: str | None = None, stress: str | None = None) -> str:
    rows = []
    for r in A["single_settings"]:
        if stress and r["stress"] != stress:
            continue
        if family and not r["action"].startswith(family):
            continue
        ev = r["evaluation"]
        rows.append([LABEL[r["stress"]], r["action"], r["magnitude"], r["duration"] or "-", r["t"], r["exploration_effective"], r["validation_effective"] or "-", f"**{r['status']}**", f"{ev['k']}/{ev['n']}" if ev else "-", ", ".join(f"{k} {v}" for k, v in (r["evaluation_outcomes_long"] or {}).items()) or "-", "costly" if r["costly"] else "-"])
    return tbl(["stress", "action", "magnitude", "duration", "tick", "exploration seeds 1-5 effective", "validation seeds 6-10 effective", "status", "evaluation seeds 11-30", "outcomes at the long horizon", "cost class"], rows) if rows else "*(none)*\n"


def tested_summary(stress: str, prefix: str | None = None) -> str:
    """Every action tried on a stress (all magnitudes, durations and ticks of the exploration grid), including those that never worked: how many settings, how many effective on all five exploration seeds, the best any setting did, and why the others failed."""
    import collections
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for r in A["table"]:
        if r["stress"] == stress and r["action"] != "no action" and (prefix is None or r["action"].startswith(prefix)):
            by[r["action"]].append(r)
    val = {(r["action"]) for r in A["single_settings"] if r["stress"] == stress and r["status"] == "validated"}
    rows = []
    for a, rs in sorted(by.items()):
        best = max(rs, key=lambda r: r["effective_seeds"])
        fails = collections.Counter(R_ID(r["failure"]) for r in rs if r["failure"] != "effective")
        rows.append([a, len(rs), sum(1 for r in rs if r["effective_seeds"] == r["n"]), "validated" if a in val else "none validated", f"{best['effective_seeds']}/{best['n']} (magnitude {best['magnitude']}, duration {best['duration'] or '-'}, tick {best['t']})", ", ".join(f"{k} {v}" for k, v in fails.most_common(3)) or "-"])
    return tbl(["action tried", "settings tried (magnitude x duration x tick)", "effective on all 5 exploration seeds", "validation (seeds 6-10)", "best any setting did on the exploration seeds", "main failure ids of the others"], rows)


def R_ID(text: str | None) -> str:
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from xzr.meos import repair6 as R6
    return R6.failure_id(text) or "effective"


def combined_table() -> str:
    rows = []
    for r in A["combined_settings"]:
        ev = r["evaluation"]
        rows.append([LABEL[r["stress"]], part_text(r["parts"]), r["t"], r["exploration_effective"], r["validation_effective"] or "-", f"**{r['status']}**", "yes" if r["synergistic"] else "no (a part is effective alone at this tick)", f"{ev['k']}/{ev['n']}" if ev else "-"])
    return tbl(["stress", "pair", "tick", "exploration", "validation", "status", "synergy (neither part effective alone)", "evaluation seeds 11-30"], rows)


def controller_table() -> str:
    idx = {(s["stress"], s["controller"]): s for s in CT["summary"]}
    kinds = CT["controllers"]
    known = [r["stress"] for r in ST] + ["no stress"]
    rows = [[LABEL.get(sid, sid)] + [f"{idx[(sid, k)]['success_long']['k']}/{idx[(sid, k)]['n']}" for k in kinds] for sid in known]
    return tbl(["stress (known, library built for it)"] + kinds, rows)


def unknown_table() -> str:
    idx = {(s["stress"], s["controller"]): s for s in CT["summary"]}
    kinds = CT["controllers"]
    rows = [[u["id"], u["varies"], u["onset"]] + [f"{idx[(u['id'], k)]['success_long']['k']}/{idx[(u['id'], k)]['n']}" for k in kinds] for u in CT["unknown_stresses"]]
    return tbl(["held-out variation", "what varies", "onset"] + kinds, rows)


def verdict_table(key: str) -> str:
    return tbl(["stress", "controller", "success", "no repair", "difference", "Fisher p", "Holm p", "verdict"], [[LABEL.get(v["stress"], v["stress"]), v["controller"], v["success"], v["none"], v["difference"], v["fisher_p"], v["holm_p"], f"**{v['verdict']}**" + ("" if v["survives_holm"] or v["verdict"] != "effective" else " (not after Holm)")] for v in CT[key] if v["verdict"] != "no effect"])


def fp_table() -> str:
    return tbl(["controller", "runs", "success", "mean attempts (false interventions) per run", "mean interventions", "mean energy use"], [[s["controller"], s["n"], f"{s['success_long']['k']}/{s['n']}", s["mean_attempts"], s["mean_interventions"], s["mean_energy_use"]] for s in CT["false_positives"]])


def library_table() -> str:
    return tbl(["plan", "class", "stresses it was validated for", "expected recovery", "cost (equal-weight normalised)", "cost components"], [[p["id"], p["klass"], ", ".join(LABEL.get(s, s) for s in sorted(set(p["stresses"]))), p["expected"], p["cost"], json.dumps(p["cost_components"])] for p in CT["library"]])


def failure_table() -> str:
    rows = [[k.split(" | ")[0], k.split(" | ")[1], ", ".join(f"{a} {b}" for a, b in v.items())] for k, v in F["controller_failure_ids"].items() if not k.startswith("no stress")]
    return tbl(["stress", "controller", "failure ids of the 20 runs"], rows[:60])


def mfs_table() -> str:
    names = ["coupling", "resource", "renewal efficiency", "renewal stopped", "Address", "history lost"]
    rows = []
    for m, p in C["C1_mfs"]["profile"].items():
        rows.append([m] + list(p.values()))
    return tbl(["MFS"] + names, rows)


def sss_table() -> str:
    import collections
    rows = []
    for m in sorted({x["mfs"] for x in C["C2_sss"]["cells"]}):
        cells = [x for x in C["C2_sss"]["cells"] if x["mfs"] == m]
        isl = [x for x in cells if x["unstressed_persists"]]
        cls = collections.Counter(v["class"] for x in isl for v in x["stress"].values())
        rows.append([m, f"{len(isl)}/{len(cells)}", "; ".join(f"{k} {v}" for k, v in sorted(cls.items(), key=lambda kv: -kv[1]))])
    return tbl(["MFS", "points of the 3 x 3 SSS grid where the unstressed MFS persists (its island)", "classes over (island point x stress), one repair per stress"], rows)


def obs_table() -> str:
    rows = [[r["run"], r["observation"], r["operational_state"], r["observed_state"], r["observability_status"], "yes" if r["operational_recovery"] else "no", "yes" if r["observed_recovery"] else "no"] for r in C["C3_observation"]["rows"] if r["run"].startswith(("coupling stress, resource pulse", "coupling stress, no repair"))]
    return tbl(["run", "observation", "operational state", "observed state", "observability status", "operational recovery", "observed recovery"], rows)


def address_table() -> str:
    return tbl(["case", "operational restoration (5 seeds)", "Address restoration", "observability restoration (Address resolution 0.5)", "mean Address integrity, last 30 ticks"], [[r["case"], r["operational_restoration"], r["address_restoration"], r["observability_restoration"], r["mean_address_integrity"]] for r in C["C4_address_three_restorations"]["rows"]])


def consistency_table() -> str:
    c = F["stage5_consistency"]
    keys = ["stage5_style_active_at_300", "stage5_style_active_at_end_of_480", "stage6_short", "stage6_medium", "stage6_long"]
    return tbl(["seed set"] + ["Stage 5 criterion: ACTIVE at tick 300", "ACTIVE at the end of 480", "Stage 6 short", "Stage 6 medium", "Stage 6 long"], [[k] + [v[x] for x in keys] for k, v in c["by_seed_set"].items()])


def strips_text() -> str:
    out = []
    for r in ST:
        runs: list[str] = []
        cur, start = None, 101
        for t in range(101, 421):
            cls = ("internal" if any(a <= t <= b for a, b in r["internal_reconfiguration"]["windows"]) else "world-state" if any(a <= t <= b for a, b in r["world_single"]["windows"]) else "combined" if any(a <= t <= b for a, b in r["combined"]["windows"]) else "none")
            if cls != cur:
                if cur is not None:
                    runs.append(f"{start}-{t - 1} {cur}")
                cur, start = cls, t
        runs.append(f"{start}-420 {cur}")
        out.append(f"- **{r['label']}** (unrepaired collapse at {r['unrepaired_collapse_tick']}): " + "; ".join(runs))
    return "\n".join(out)


def delayed_text() -> str:
    lines = []
    for r in ST:
        late = [w for w in r["timing_window_fragments"] if w[1] >= (r["unrepaired_collapse_tick"] or 999)]
        lines.append(f"- {r['label']}: " + (f"effective ticks at or after the unrepaired collapse ({r['unrepaired_collapse_tick']}): {wtext(late)}" if late else f"no tested setting is effective at any tick from the unrepaired collapse ({r['unrepaired_collapse_tick']}) to {r.get('tested_range_end', 330)}"))
    return "\n".join(lines)


def orig_vs_new() -> str:
    old = {r["stress"]: r for r in F0["stress_table"]}
    return tbl(["stress", "original criterion (all three horizons at every tick): effective ticks", "latest / earliest irreversible", "corrected criterion (applicable horizons): effective ticks", "latest / earliest irreversible"],
               [[r["label"], wtext(old[r["stress"]]["timing_window_fragments"]), f"{old[r['stress']]['latest_successful_repair_tick']} / {old[r['stress']].get('earliest_irreversible_tick', old[r['stress']].get('irreversible_tick'))}", wtext(r["timing_window_fragments"]), f"{r['latest_successful_repair_tick']} / {r['irreversible_tick']} ({r['irreversibility']})"] for r in ST])


def open_windows_text() -> str:
    rows = []
    for w in OPEN["windows"]:
        pt = w["per_tick"]
        last = w["latest_effective_tick"]
        nxt = pt.get(str(last + 1)) if last is not None else None
        rows.append([LABEL[w["stress"]], part_text(w["parts"]), f"{w['ticks_tested'][0]}-{w['ticks_tested'][1]}", wtext(w["effective_intervals"]), last, last + 1 if last is not None else "-",
                     f"{nxt['exploration']} / {nxt['validation']}" if nxt else "-", len(w["near_miss_ticks"])])
    return tbl(["stress", "setting (the window that was open at 330)", "action ticks tested", "effective ticks", "latest effective tick", "first tick not effective", "exploration / validation at that tick", "near-miss ticks"], rows)


def mechanism_text() -> str:
    cf = MECH["counterfactual_resource_pulse_1.0_horizon_1200"]
    rows = [[c["pulse_tick"]] + [f"{b['recovered_of_10']}/10" for b in c["by_upkeep"]] for c in cf]
    return (f"In the unrepaired coupling run A1's energy is {MECH['a1_energy_at_tick_300_unrepaired']['min']} at tick 300 on every seed and falls by A1's upkeep ({MECH['a1_upkeep_per_tick']} per tick) while the run is collapsed; it is below A1's firing cost ({MECH['a1_firing_cost']}) from tick "
            f"{MECH['tick_a1_energy_below_firing_cost_unrepaired']['min']} (the same tick on all ten seeds). A resource pulse cannot restart a configuration that cannot fire. As a counterfactual (a change of the *model*, not an action of the tested space), the same pulse with A1's upkeep set to 0 in the initial configuration:\n\n"
            + tbl(["pulse tick", f"recovered, upkeep {MECH['a1_upkeep_per_tick']} (the model)", "recovered, upkeep 0 (counterfactual)"], rows))


def followup_text() -> str:
    cnt = FU["counts"]
    acts = tbl(["action", "what it does in the engine", "magnitude", "durations", "declared cost", "note"], [[a["id"], a["label"], f"{a['magnitude_meaning']}: {a['magnitudes']}" if a["magnitudes"] else "-", a["durations"] if a["durations"] != [0] else "-",
                                                                                                     "; ".join(f"{k}: {v}" for k, v in a["declared_cost"].items()) or "-", a["note"]] for a in FU["actions"]])
    from collections import Counter
    c = Counter((r["stress"], r["action"], r["status"]) for r in FU["single_settings"])
    singles = tbl(["stress", "action", "validated settings", "near misses", "minimum validated magnitude (ticks)"], [[LABEL.get(sid, sid), aid, c.get((sid, aid, "validated"), 0), c.get((sid, aid, "near miss"), 0),
                  next((f"{m['minimum_effective_magnitude']} (ticks {m['effective_ticks']}; durations {m['durations_at_that_magnitude']})" for m in FU["minimum_effective"] if m["stress"] == sid and m["action"] == aid), "-")] for sid, aid in sorted({(r["stress"], r["action"]) for r in FU["single_settings"]})])
    wins = tbl(["stress", "setting", "ticks tested", "effective ticks", "near-miss ticks"], [[LABEL[w["stress"]], part_text(w["parts"]), f"{w['ticks_tested'][0]}-{w['ticks_tested'][1]}", wtext(w["effective_intervals"]), wtext([[a, a] for a in w["near_miss_ticks"]]) if len(w["near_miss_ticks"]) < 8 else f"{len(w['near_miss_ticks'])} ticks"] for w in FU["windows"]])
    cc = Counter((r["stress"], r["status"], r["synergistic"]) for r in FU["combined_settings"])
    comb = tbl(["stress", "validated and synergistic", "validated, not synergistic (one part alone is effective)", "near miss", "failed validation"], [[LABEL[sid], cc.get((sid, "validated", True), 0), cc.get((sid, "validated", False), 0), cc.get((sid, "near miss", False), 0), cc.get((sid, "failed validation", False), 0)] for sid in SID])
    cls = tbl(["stress", "at tick 113: Stage 6 action space", "at tick 113: extended", "any tested tick: Stage 6 action space", "any tested tick: extended"], [[LABEL[sid], c_["original_at_decision_tick_113"], c_["extended_at_decision_tick_113"], c_["original_at_any_tested_tick"], c_["extended_at_any_tested_tick"]] for sid, c_ in FU["classification"].items()])
    return f"""Engine `meos-0.5` adds three opt-in mechanisms (absent from every earlier configuration, so every earlier run is the same run: section 31). The frozen Stage 6 registry still records the three actions as not implemented; they are in their own registry (`repair6.FOLLOWUP_LIST`) and every Stage 6 result above is the result in the original action space.

{acts}
Protocol: that of Pipeline A and B (exploration seeds 1-5, validation 6-10, evaluation 11-30, the same criterion, the same eight action ticks, a combined repair counts only where neither part is effective alone). {cnt['exploration_runs']} single runs; {cnt['combined_runs']} combined runs.

**Single actions** ({cnt['single_candidates']} candidates, {cnt['single_validated']} validated, {cnt['single_near_miss']} near misses):

{singles}
Windows (one tick, 101-170, on to 330 where open at 165 or later):

{wins}
**Combined repairs with a new action** (a primary of Stage 6 with one setting of a new action; {cnt['combined_candidates']} candidates, {cnt['combined_validated']} validated, {cnt['combined_synergistic']} synergistic, {cnt['combined_near_miss']} near misses):

{comb}
**Repairability, in the action space of Stage 6 and in the extended one** (grid classification of Pipeline A/follow-up at the tick named; the window-based classification of section 7 is unchanged):

{cls}
Reading. (1) Alone, only `resource.rerouting` and `coupling.bypass` recover anything, and only the coupling stress; rerouting works over a long range of ticks with a large rate and a long duration, the bypass only early. (2) On the other stresses the new actions recover the run only together with a restoration of the damaged parameter (the Address restoration, the renewal restart or restore, the M2 tap): a combined recovery, credited to the combination. (3) The temporary local Address alone does nothing, as the permanent restoration alone did nothing (section 13): the Address is not the only thing that has to be restored. (4) The extended action space changes the class of the renewal-efficiency, the renewal-stopped and the Address stresses **at tick 113**; it does not change the class of the coupling, the resource or the history-lost stresses, and it opens no window for the resource stress. (5) `resource.rerouting` moves resource, it does not add it; its effect on the source cell (0, 6) is a side effect that is not scored beyond the collateral cost in the saved rows. The mechanisms are minimal choices of this study (a peak-tap bypass, a point-to-point conduit, a bounded full addressability), not claims about a real system, and other realisations of the same names would be other actions.
"""


def repro_text() -> str:
    return f"""The engine version moved from `meos-0.4` to `meos-0.5` for the follow-up. The new mechanisms are absent from every earlier configuration; this was checked, not assumed, by running the earlier experiments again on `meos-0.5`:

- Stage 5 subset (`reproduce_stage5_subset.py`): all identical = {REPRO5.get('all_identical')} (experiment L on history lost, the F14, F8 and F9 searches with their digests, the first decisions of the adaptive controller, Stage 4's strict nulls, the two baseline digests).
- Stage 6 subset (`reproduce_stage6_subset.py`): all identical = {REPRO6.get('all_identical')}.
- The baseline result digest and trace digest are unchanged (section 24). The result files written by the engine before the change carry `meos-0.4` in their `engine` field; the runs they record are reproduced bit for bit by `meos-0.5`.
"""


def build() -> str:
    cnt = A["counts"]
    return f"""# XENO ECOSYSTEM — Stage 6 (MEOS-0.4, follow-up on MEOS-0.5): endogenous repair, world-state intervention, reachable recovery

> Which damage can internal reconfiguration handle, which needs an intervention on the state of the world, and which cannot be recovered in the action space tested here: by which action, how much of it, at which tick, at which cost, on which seeds, and to which horizon.

Everything below is a statement about a **formal model** (MEOS-0, engine `meos-0.4`, unchanged by this stage): how this engine's specified operation responds to the interventions tested. It is not evidence about any real ecosystem. A repair that works here is *conditional* on the model,
the action space, the tick grid, the horizons and the seeds. Raw data and interpretation are kept apart: the tables are copied from `docs/ecosystem/experiments_stage6*.json` by `backend/scripts/make_stage6_doc.py`; the words under them are interpretation and its limits.

## 1. Scope

Stage 5 searched **component enable/disable** (route reconfiguration) and found an action for one stress of six (history lost: the M2 tap). Stage 6 asks the question that left open: for the stresses internal reconfiguration cannot handle, **does an intervention on the world itself** (coupling, resource, renewal, Address)
recover a sustainable operation, and under what conditions? Recovery is not a flash of ACTIVE (section 6). Not changed: the baseline result digest, the 264 saved runs, every Stage 5 result.

## 2. Repository state

{frag("git")}

## 3. Stage 5 inheritance

Stage 5 (experiment L) found that for `history lost` exactly one action of 512 persists, the M2 tap at tick 113, and none for the other five stresses. Stage 6 repeats that stress on the **same engine, onset, action tick and M2 specification**, and differs in two evaluation conditions only: the horizon (Stage 5: 300; Stage 6: three horizons up to 480) and the criterion
(Stage 5: ACTIVE at the end; Stage 6: ACTIVE on the last 30 ticks, no secondary collapse, resource not exhausted). The result is the same under both:

{consistency_table()}
There is no model change and no disagreement to explain: a Stage 5 result stands under the stricter Stage 6 criterion. The Stage 5 result files are not modified.

## 4. Repair action space

Three kinds of recovery action are kept apart in the code, the experiments and this document and are never counted as one: **A** internal reconfiguration (a component switched on or off, a route switched: Stage 5), **B** world-state repair (new), **C** observation repair (a change of how the run is observed; it changes the observed state, never the run).
Every action is built from operations MEOS-0 already has (`RECONFIGURE`, `ALTER_RESOURCE`, `RECONNECT`, `ADDRESS`, `ROUTE`), so no run without a repair changes. Implemented and proxy actions:

{actions_table()}
Class C actions (sampling interval 1, whole arena, stride 1, Address resolution 1.0) are applied to the *observation of a recorded run* (section 20), not to a run. Actions that were **not** implemented, and actions that are only a proxy; none of them was run or simulated by something else:

{not_impl()}

## 5. Cost model

Each repair run records, over the window from the action to the long horizon, **raw costs** measured from the traces: energy use (the sum of the power drawn), resource mass present, switching (the number of interventions), persistence energy rate (the energy drawn per tick once the run is sustained), and collateral disturbance (the mean normalised deviation of the interaction strength, the resource total, the power reserve and the resource flow
from the undamaged run of the same seed). **Normalised costs** divide energy use, resource mass and the persistence rate by the undamaged run's. **No weighted total is used in any result**: where one number is needed to order repairs (the *reference repair* of a stress, the cost-aware controller) it is the mean of switching, collateral and persistence rate, each divided by its maximum over the settings compared
(equal weights: a stated convention, not a finding) and the raw values are printed beside it. A recovery is *costly* if its persistence energy rate exceeds 1.5 times the undamaged run's or its collateral disturbance exceeds 1.0 (fixed before the runs).
The repair cost model is synthetic: it is a measurement of this model's traces, not a cost in any real system.

## 6. Pipeline A: protocol, seeds, criterion

- **Exploration seeds 1-5**: every applicable action x magnitude x duration x action tick ({cnt['exploration_cells']} settings, {cnt['exploration_runs']} runs); a setting effective on all five is a *candidate*. **Validation seeds 6-10**: every candidate is run again; it is *validated* only if effective on all five. **Evaluation seeds 11-30**: validated settings and near misses are evaluated and reported, never used to choose. The three seed sets are never mixed.
- **Near miss**: effective on 3 or 4 of 5 exploration seeds, or on all exploration seeds and 3 or 4 of 5 validation seeds. A near miss is kept, makes a stress INCONCLUSIVE if nothing is validated, and is **never** counted as validated.
- **Recovery** is not a flash of ACTIVE. A run recovers at a horizon if it is ACTIVE on every tick of the last 30 ticks before it, has no collapse after a sustained ACTIVE stretch of at least 30 ticks that followed the action (*no secondary collapse*), and its resource field is not exhausted (>= 25 % of the undamaged run's). Outcomes: `prevented` (no collapse after the action), `recovered` (collapse, then sustained recovery), `secondary collapse`, `failed`.
- **Horizons**: short 180, medium 300, long 480. A horizon is *applicable* to an action at tick t only if it leaves at least 2 x 30 ticks after it (time to recover and to show a sustained stretch): short up to tick 120, medium and long always. A setting is *effective* if it succeeds at every applicable horizon.
- **A correction made after reading results, and its effect.** The first version required all three horizons at every tick. A repair after tick 120 cannot satisfy the short horizon by construction, which made every late repair look like a failure and the collapse look irreversible. Inspection of the one-tick results showed this (late repairs recovered on every seed at the medium and long horizons). The criterion was corrected as above; **the results of the first criterion are kept**
  (`experiments_stage6*_all_horizons_criterion.json`) and compared here:

{orig_vs_new()}
Counts: {cnt['single_candidates']} single candidates, {cnt['single_validated']} validated, {cnt['single_near_miss']} near misses; {cnt['combined_cells']} combined settings (pairs of different actions at ticks {A['combined_ticks']}), {cnt['combined_candidates']} candidates, {cnt['combined_validated']} validated, {cnt['combined_synergistic']} of them synergistic (neither part effective alone at that tick), {cnt['combined_near_miss']} near misses.
The unrepaired runs: {', '.join(f"{LABEL[r['stress']]}: {r['outcomes_long']}" for r in A['no_action'])} (all on exploration seeds; no seed recovers without a repair).

## 7. Stress-by-stress repairability

The stresses arrive at tick 100; the decision tick (the first decision of the stage 5 controllers) is 113. Classes: *internally reconfigurable*, *externally repairable* (world-state, single or combined), *both*, *neither (under the tested actions)*, *inconclusive*. "At the decision tick" asks whether a setting is effective **at tick 113**; "at any tested tick" asks whether one is effective at some tested tick (101-170 at one-tick resolution for every setting, to 330 for the windows still open at 170, and to 1140 with the extended horizon 1200 for the three still open at 330).
A *combined* recovery counts only at ticks where neither part is effective alone. Windows are in action ticks.

{stress_table()}
{flags_table()}
*Reference repair*: the validated setting with the lowest equal-weight normalised cost; its horizons are those of its exploration cell. Every validated setting is effective at all applicable horizons by definition, so a setting that recovers at the short horizon and not at the long one is never in this table: it is listed as *only transiently recoverable* (flags) or in the failure ids.
Interpretation: repairability is not a property of a stress but of a stress, an action, a magnitude, a tick and a horizon. Every stress has a **window that closes** in the tested action space, at tick {', '.join(f"{r['irreversible_tick']} ({LABEL[r['stress']]})" for r in ST)} (the irreversible tick; the latest successful tick is the one before). For the coupling, the renewal-stopped and the Address stresses a pulse-based repair stays effective long after the unrepaired collapse (to tick {', '.join(str(r['latest_successful_repair_tick']) for r in ST if r['latest_successful_repair_tick'] and r['latest_successful_repair_tick'] > 330)}); these windows were first still effective at the end of the first tested range (tick 330), and were measured on to tick 1140 with the extended horizon (section 8) before a closure was claimed. The classification "neither" at tick 113 and "internally reconfigurable / externally repairable / both" at another tick are both true and both are reported.

## 8. Timing windows

For every setting Pipeline A found effective or nearly, every action tick from 101 to 170 was run on seeds 1-10 (exploration and validation reported separately; a tick is *effective* only if both are all effective). The unrepaired run collapses at about tick 144-159 (section 7). A window that is still effective at the last tick tested (170, 330 after the first extension, 1140 after the second) **has not closed**: its end is the end of the range, and no latest successful or irreversible tick is claimed for it. Three windows were still effective at 330; they were measured on with the longest horizon the engine accepts (1200) and all three closed (below).

{windows_table()}
**Latest successful repair tick** = the last tick at which some tested setting is effective. **Earliest irreversible tick** = the next tick, after which no tested setting is effective at any later tested tick (ticks 101-170 at one-tick resolution for every setting, 171-330 for the three whose window was still open at 170, 331-1140 with the extended horizon for the three still open at 330, 200 on the coarse grid). They are not the same notion (a window may end and another open later: the effective ticks are often **fragmented**, a gap is recorded and not smoothed), and **both depend on the tested action space**:
a tick that is irreversible here may be recoverable by an action that was not tested. Fragmentation is not explained here (the gaps inside a window are several ticks long, longer than the operating cycle of {F['cycle_period']['median_interval']} ticks; no mechanism is claimed).

Reachable recovery by tick (tested action space, one-tick resolution):

{strips_text()}

**Delayed but recoverable** (effective at or after the unrepaired collapse):

{delayed_text()}

## 9. Minimum effective interventions

Pipeline A's coarse minimum, and Pipeline B's one-tick and fine-magnitude sweeps (a magnitude is effective at a tick only if all ten exploration and validation seeds are effective; no threshold rests on one seed):

{tbl(["stress", "action", "minimum effective magnitude (coarse grid, validated)", "effective ticks"], [[LABEL[m['stress']], m['action'], m['minimum_effective_magnitude'], ", ".join(map(str, m.get('effective_ticks') or []))] for m in A['minimum_effective'] if m['minimum_effective_magnitude'] is not None])}
{min_table()}
The minimum depends on the tick: it is not a constant of the repair. The restoration of the Address alone and the restart of the renewal alone have **no effective tick** at all (section 8), whatever their magnitude.

## 10. Coupling (Experiment M)

Stress: coupling gain 0.5 from tick 100. All coupling settings, then the other families on the same stress:

{tested_summary("coupling gain 0.5")}
Restoring the coupling gain **alone** is effective only very early (it needs the repair within a few ticks of the damage, and a partial restoration is enough at some ticks); a gradual restoration likewise. A temporary bridge (the gain strengthened for a while, then returned to the damaged value) is not effective: the damage remains after it. **A resource pulse works much later and over a long band**: the repair site
is not the damage site, and the original parameter restored alone does not restore the system once the damage has set in. The local bypass was not implemented in the main experiments (no spatial coupling path in the engine); it was built afterwards as a second sensing path (section 30).

## 11. Resource (Experiment N)

{pulse_table()}
For the coupling stress the pulse has three regimes: **insufficient** below the band, **effective** inside it, **overshoot** above it (a secondary collapse); the boundaries are located to 0.1. The non-monotonicity of Stage 3 (2.0 recovers, 4.0 re-collapses) is reproduced with its boundary. For the other stresses **no pulse size of 0.1-6.0 recovers the run**; where a larger pulse gives a transient recovery followed by a secondary collapse that phase is named (*transient recovery, then secondary collapse*) and is not a recovery.
The other resource actions (sustained inflow, redistribution by diffusion (a proxy), power reserve (a proxy)) and the resource stress itself:

{tested_summary("resource regrow 0.01 charge 0.2")}
## 12. Renewal (Experiment O)

Two stresses: efficiency 0.6, and renewal stopped (the feedback component removed).

Renewal efficiency 0.6:

{tested_summary("renewal efficiency 0.6")}
Renewal stopped:

{tested_summary("renewal stopped")}
Efficiency: a full restoration is effective only within a few ticks of the damage (the fine sweep finds that a restoration to 0.95 is the minimum at those ticks, so a partial restoration to 0.9 or less is **not** enough); the M2 tap is effective only slightly longer. A restart of a stopped renewal alone is never effective (section 8); a restart **together with** a pulse is (section 14).

## 13. Address (Experiment P)

Stage 4's strict nulls (collision, stale) were results of a *fixed* configuration and are **not** overwritten: this section is about a *dynamic degraded* condition (A2 partial 50 % from tick 100).

{tested_summary("Address partial 0.5")}
Three restorations are three measures (5 seeds each):

{address_table()}
Restoring the Address restores the Address integrity at once on every seed, **and does not restore the operation at tick 113 (0 of 5)**: Address restoration and operational restoration are different things. A restoration **together with** a pulse recovers the run in a time window (section 14), but its strict validation failed at tick 113 (a near miss: 4 of 5 validation seeds, one secondary collapse), so
it is reported as such. This does not show that the Address was the direct cause of the collapse: the Address repair alone is null, and the combination works through the resource.

## 14. Combined repair (Experiment Q)

Pairs of different actions, only for the stresses no single world-state action recovers at tick 113 (a restricted set: a primary restoration of the damaged family or the M2 tap, with a secondary additive action), at ticks {A['combined_ticks']}:

{combined_table()}
A pair is credited as a **combined recovery** only where neither part is effective alone at that tick. Where a pair is effective and one part is effective alone (the M2 tap with a pulse on history lost, at ticks up to 113), the pair adds nothing and is not credited with anything. Where it extends a window (history lost: the pair is effective to tick 120, the M2 tap alone to 113), that extension is the combined result.

## 15. Controllers

Six controllers (`repair_ctl.py`): **none**; **fixed** (one action chosen before any run was looked at: a pulse of 2.0, applied once); **rule_based** (each sensed damaged feature mapped to the action that undoes it: restore the gain, restore regrow and charge, restore the efficiency then reconnect the feedback, restore the Address, the M2 tap for a lost history; no knowledge of what worked);
**cost_aware** (the validated library below, highest expected recovery first, the cheapest among equals); **delayed** (cost_aware acting 15 ticks later); **noisy** (cost_aware on a detection that flips each sensed feature with probability 0.1, without debounce). All sense only the five features of the stage 5 sensor and the run's own status; a revision loop watches each attempt for 25 ticks and moves to the next candidate if the run has not recovered (at most 3).
Every decision is logged: what was detected, which plans were available and rejected (with the reason), the one selected, its estimated cost and expected recovery, and what actually happened. The library is built from seeds 1-10 only; the controllers are evaluated on seeds 11-30. Success is a recovery at the long horizon (not a switch, not an action fired). *Effective*: success rate above that of no repair by at least 0.30 and Fisher's p < 0.05 (fixed before the runs), Holm's correction over all comparisons reported.

Library ({len(CT['library'])} plans validated at the decision tick):

{library_table()}
Success at the long horizon, 20 seeds per cell:

{controller_table()}
Effective (unadjusted, with the Holm-adjusted p):

{verdict_table('verdicts_known')}
Failure ids of the controller runs (taxonomy: NO_EFFECTIVE_ACTION, ACTION_TOO_WEAK, ACTION_TOO_LATE, OVERSHOOT, SECONDARY_COLLAPSE, DETECTION_FAILURE, ADDRESS_UNRESOLVED, INSUFFICIENT_RESOURCE, EXCESSIVE_COST, DESTABILIZED_BY_ACTION, OUTSIDE_TESTED_ACTION_SPACE; SEED_DEPENDENT is an addition for a setting effective on some seeds only):

{failure_table()}
**Reading, as far as the data go.** On the coupling stress the *fixed* pulse (chosen beforehand) and the *cost-aware* controller are both 20/20: the adaptive controller did not do better than a known fixed repair, and that equality is **not** adaptive superiority. The *rule-based* controller, which restores the damaged parameter, recovers 0/20: **restoring the original parameter alone does not restore the system.**
On history lost the rule-based (M2) and cost-aware controllers are 9/20, the Stage 5 result (the M2 window closes at tick 113 and the controller acts at 114: it acts on the edge of the window). On the Address stress the **cost-aware controller (0/20) is worse than the simple rule (restore the Address)**: the strictly validated library holds no Address action, so the cost-aware controller finds nothing to apply
(`OUTSIDE_TESTED_ACTION_SPACE`) while the rule acts early and recovers on some seeds. For the renewal and resource stresses no controller recovers anything; the *noisy* controller's few recoveries are the accidental result of a false detection that acted early, inside the M2 window, not a skill.

## 16. False positives

The same controllers on a run with **no stress** (Stage 5's no-stress switch count was 0 and is the baseline):

{fp_table()}
No controller with a debounced detection acted without a stress; the controller with a noisy detection made false interventions (attempts per run above) and the run still recovered every time: false interventions were not harmful in this model. Unnecessary route switches: none (no controller of this stage switches routes except the M2 tap, which is an action in the library).

## 17. Unknown stress

Variations of the stresses the library was built for (a different severity, profile or onset), which the library never saw; 20 seeds each (11-30):

{unknown_table()}
{verdict_table('verdicts_unknown')}
**The controller generalized to the tested held-out variations of the coupling stress (a weaker drop, a later onset) and not to a stronger drop (gain 0.3), where every controller, including the fixed pulse, recovers 0 of 20.** For the Address variations only the rule-based controller acts and its success rises with milder severity (0.7: 17/20; 0.5: 8/20; 0.3: 4/20). For renewal and resource variations nothing recovers. Nothing here shows a general generalization.

## 18. MFS x repairability

The repairs Pipeline A validated (or nearly) on the full arrangement were tried unchanged on each distinct validated MFS (the components outside the MFS removed at tick 0, under the condition it was found for), on seeds 1-5 (not independently validated here):

{mfs_table()}
The repairability profile **differs between MFS**: a repair validated on the full arrangement does not carry over unchanged (the MFS-F14-2, the M2-mediated set, is the only one with an internal route for history lost and the one where the coupling and Address repairs are inconclusive). An MFS whose condition has no M2 tap has no internal route of that kind.

## 19. SSS x repairability

On a 3 x 3 grid of the SSS region (scale 0.75/1/1.25 x speed 0.9/1/1.1, size 1) the unstressed MFS persists on part of the grid (its island); on the island each stress was tried with no action and with its recommended repair (3 seeds):

{sss_table()}
Cells are *repairable* (the recommended repair recovers on every seed), *repairable on some seeds only*, *overshoot-sensitive / unstable recovery* (a secondary collapse), *costly recovery* (above the cost limit) or *unrecoverable*. The per-cell classes are in `experiments_stage6_cross.json` (`C2_sss`).

## 20. Observation x repairability

Operational recovery and observed recovery are separate fields (with the observability status): a run that recovered can be observed as collapsed. Observation repair (full observation) is a change of the observer; it never changes the run.

{obs_table()}
Of the runs that recovered operationally, {C['C3_observation']['operationally_recovered_but_not_observed']} (run, observation) pairs were **not** observed as recovered: coarse sampling (`INSUFFICIENT_TEMPORAL_RESOLUTION`), coarse spatial resolution (`INSUFFICIENT_SPATIAL_RESOLUTION`) and a region that excludes the bodies (`REGION_EXCLUDES_ACTIVITY`) all report COLLAPSED for an ACTIVE run; full observation (or Address resolution 0.5) restores agreement.

## 21. Reachable recovery regions

For each stress the tested action space divides the ticks into: recoverable by internal route change, by world-state repair, by a combined action, *unstable recovery* (a transient recovery followed by a secondary collapse: the overshoot and the near misses), *unrecoverable under the tested actions*. Section 8 gives the strip of every stress at one-tick resolution; the interface draws it. These are regions of the **tested action space**, not of the world.

## 22. Replay and interface

{frag("replay_ui")}

## 23. Performance

{frag("performance")}

## 24. Regression

{frag("regression")}

## 25. Failed hypotheses

{frag("failed")}

## 26. Null results (kept)

- No pulse of 0.1-6.0 recovers the resource, the renewal-efficiency or the renewal-stopped stress at tick 113 (section 11); a pulse alone on history lost gives a transient recovery and then a secondary collapse.
- The restoration of the Address alone, the restart of the renewal alone, the temporary bridge of the coupling, the temporary renewal boost: no effective tick (sections 9, 12, 13).
- The controllers on the renewal and resource stresses, and on the stronger coupling drop: 0 of 20 (section 15, 17).
- Stage 4's strict nulls are unchanged.
- The raw rows of every run are kept: `experiments_stage6_raw.jsonl.gz` ({cnt['exploration_runs']} rows), `experiments_stage6_raw_combined.jsonl.gz`, `experiments_stage6_controllers_raw.jsonl.gz`; the results of the first criterion are kept beside the corrected ones.

## 27. Limitations

- The action space is limited to what MEOS-0 can do: the local bypass, the transport rerouting and the temporary local Address were not implemented in the main experiments and were built afterwards (section 30), as minimal mechanisms of this study; redistribution and the reserve release are proxies (section 4).
- The tick grid is finite (one-tick resolution only for the settings measured at that resolution; ticks 101-170, a coarse grid to 200); the horizons are finite (180, 300, 480); the seeds are few (5 + 5 for each setting, 20 for evaluation) and the engine's seed-to-seed variation is small, so proportions are near 0 or 1.
- The repair cost model is synthetic (measured from the model's own traces, equal-weight only where an order is needed). The environment model is synthetic. No claim is made about real ecosystems.
- The controllers sense five features; four stresses give the same signature, so the controller cannot tell them apart and tries plans in turn.
- Unknown-stress coverage is limited to the variations listed; generalization is shown, where it is, only for those.
- The MFS and SSS readings use the repairs validated on the full arrangement, on 5 and 3 seeds, and an island of a 3 x 3 grid.
- Repairability is conditional on the tested model, version, action space, ticks and horizons: a stress called unrecoverable here is unrecoverable *under the tested actions*.

## 28. Remaining work

{frag("remaining")}

## 29. Windows open at tick 330, measured on (follow-up)

The first tested range ended at tick 330 because the long horizon (480) leaves room for 60 ticks only up to tick 420. Three windows were still effective there. They were run again with the longest horizon the engine accepts (1200), at every action tick from 331 to 1140, on seeds 1-10, with the same criterion plus success at the extended horizon (`experiments_stage6_open_windows.json`; ticks 300-330 of the extended run agree with the saved windows).

{open_windows_text()}
All three close; the closure is not the end of the range and not a property of the horizon. The reading of the state:

{mechanism_text()}
Interpretation. The irreversible ticks of these three stresses are now found, in the tested action space. The mechanism is the energy store of A1 during the collapse; no action of the tested space adds energy to A1 (there is no operation or settable parameter for it), so "closed" means closed **for these actions**: an action that restores A1's energy was not tested and is not in the engine. The closure of the Address and renewal-stopped windows comes five ticks earlier because the repaired run needs A1 to fire a few times before the pair recovers. At the first tick of the closure the seeds are not all alike on the Address pair (ticks 384-388 recover on 2-3 of 5 seeds: not effective, not a near miss by the rule of this study).

## 30. The three actions that were not built (follow-up, engine meos-0.5)

{followup_text()}
## 31. The earlier results on meos-0.5 (follow-up)

{repro_text()}"""


def main() -> None:
    out = build()
    if "--check" in sys.argv:
        if not DOC.exists() or DOC.read_text() != out:
            sys.exit("docs/ECOSYSTEM_MEOS_STAGE6.md is not what the data produce: run backend/scripts/make_stage6_doc.py")
        print("document matches the data")
        return
    DOC.write_text(out)
    print(f"wrote {DOC} ({len(out.splitlines())} lines)")


if __name__ == "__main__":
    main()
