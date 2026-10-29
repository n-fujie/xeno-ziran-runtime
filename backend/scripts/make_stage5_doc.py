"""Writes docs/ECOSYSTEM_MEOS_STAGE5.md: the prose is here, every number in a table is copied from the saved results (docs/ecosystem/experiments_stage5.json) or from the evidence files.

    python backend/scripts/make_stage5_doc.py            # writes the document
    python backend/scripts/make_stage5_doc.py --check    # fails if the document on disk differs from what the data produce

Raw data and interpretation are kept apart: the tables are the data, the words under them are the interpretation and its limits."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "ECOSYSTEM_MEOS_STAGE5.md"
RAW = json.loads((ROOT / "docs/ecosystem/experiments_stage5.json").read_text())
EX, FIN = RAW["experiments"], RAW["final"]
FRAG = ROOT / "docs/ecosystem/stage5_fragments"  # prose that depends on measurements taken after the data (performance, regression, git state)


def frag(name: str) -> str:
    p = FRAG / f"{name}.md"
    return p.read_text().strip() if p.exists() else f"*(fragment {name}.md has not been written)*"


def tbl(head: list[str], rows: list[list]) -> str:
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|", *("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows)]) + "\n"


def prop(p: dict) -> str:
    return f"{p['k']}/{p['n']}"


def f_table() -> str:
    rows = []
    for r in FIN["F_table"]:
        rows.append([r["condition_id"], r["description"], f"{r['search_seeds'][0]}-{r['search_seeds'][-1]}", f"{r['validation_seeds'][0]}-{r['validation_seeds'][-1]}", r["candidate_retaining_sets"], r["validated_mfs"],
                     ", ".join(r["mfs_ids"]) or "—", ", ".join(map(str, r["cardinality"])) or "—", r["history_role"], r["m2_role"], r["address_role"], r["coupling_role"], r["resource_role"], r["renewal_role"], ", ".join(r["sss_region_default_setting"]) or "—",
                     ", ".join("—" if v is None else f"{v:.2f}" for v in r["observational_robustness"]) or "—", f"**{r['classification']}**"])
    return tbl(["condition", "description", "search seeds", "validation seeds", "candidate sets", "validated MFS", "MFS ids", "cardinality", "history", "M2", "Address", "coupling", "resource", "renewal", "SSS region (default setting)", "observational robustness", "class"], rows)


def candidates_table() -> str:
    rows = []
    for cid, c in FIN["candidates"].items():
        for i, x in enumerate(c["candidates"], 1):
            rows.append([cid, f"{cid}-set{i}", f"{x['cardinality']}: " + ", ".join(x["retained"]), f"{x['persists_in_search_seeds']}/{len(x['search_seeds'])}", f"{x['persists_in_validation_seeds']}/{len(x['validation_seeds'])}", "discovered" if x["discovered_in_search"] else "not discovered",
                         "survived" if x["survived_validation"] else "did not survive", f"**{x['status']}**"])
    return tbl(["condition", "set", "retained components", "persists on search seeds 1-5", "persists on validation seeds 6-10", "discovery", "validation", "status"], rows)


def f14_table() -> str:
    c = FIN["F14_comparison"]
    a, b = c["mfs_a"]["id"], c["mfs_b"]["id"]
    rows = []
    for r in c["rows"]:
        fmt = lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)  # noqa: E731
        rows.append([r["measure"], fmt(r[a]), fmt(r[b]), "differs" if r["differs"] else "same"])
    return tbl(["measure", a, b, ""], rows)


def equivalence_table() -> str:
    return tbl(["MFS a", "MFS b", "level reached", "class", "differences / verdict"], [[e["a"], e["b"], e["level"], f"**{e['class']}**", e["verdict"]] for e in FIN["route_equivalence"]])


def role_table() -> str:
    return tbl(["condition", "history role", "class"], [[r["condition"], r["role"], r["classification"]] for r in FIN["history_role"]])


def g_table() -> str:
    g = EX["G"]["G1_scope_of_substitution"]
    rows = [[k, f"{v['cells_where_M2_substitutes']}/{v['cells_where_history_is_needed']}", f"{v['proportion']['p']:.2f} [{v['proportion']['wilson95'][0]:.2f}, {v['proportion']['wilson95'][1]:.2f}]"] for k, v in g.items()]
    return tbl(["M2 variant", "cells where history is needed and M2 substitutes", "proportion (Wilson 95 %)"], rows)


def h_tables() -> str:
    h = EX["H"]
    s = h["summary_by_class"]
    persisting = [r for r in h["arrangements_screened"] if r["active_seeds"] == 5]
    return (f"{len(h['arrangements_screened'])} arrangements were screened (A2 start cell, A2 speed, sensing radii); **{len(persisting)} persisted in all 5 seeds**; none of them kept the two configurations apart.\n\n"
            + tbl(["persisting arrangement", "separation after tick 60 (cells)", "A2 moves after tick 60", "separated", "moving late"], [[r["id"], r["mean_separation_after_60"], r["a2_moves_after_60"], r["separated"], r["moving_late"]] for r in persisting])
            + f"\nOutcome of the {sum(s.values())} fault cells on those arrangements: collapse {s['collapse']}, dynamics changed without collapse {s['dynamics changed']}, null (dynamics identical to the control) {s['null']}.\n")


def reconf_table() -> str:
    rows = []
    for v in FIN["reconfiguration"]["verdicts"]:
        rows.append([v["scenario"], v["controller"], f"{v['persisted_k_of_n'][0]}/{v['persisted_k_of_n'][1]}", f"{v['control_k_of_n'][0]}/{v['control_k_of_n'][1]}", v["difference_in_seeds"], v["cohens_h"], v["fisher_p_unadjusted"], v["holm_p_over_all_comparisons"],
                     v["switches_per_run"], v["false_switches"], v["unnecessary_switches"], v["mean_switching_cost"], v["energy_cost_vs_none"], f"**{v['verdict']}**"])
    return tbl(["scenario", "controller", "persisted", "no reconfiguration", "difference (seeds)", "Cohen's h", "Fisher p", "Holm p (30)", "switches / run", "false switches", "unnecessary", "switching cost", "energy vs none", "verdict"], rows)


def controllers_table() -> str:
    rows = []
    for r in EX["I"]["rows"]:
        if r["scenario"].startswith("no stress"):
            continue
        rows.append([r["scenario"], r["controller"], prop(r["persisted"]), prop(r["collapsed"]), r["median_time_to_recovery"] if r["median_time_to_recovery"] is not None else "—", r["mean_switches"], r["false_switches"], r["mean_switching_cost"], r["mean_energy"]])
    return tbl(["scenario", "controller", "persisted", "collapsed", "median recovery (ticks)", "switches / run", "false switches", "switching cost", "mean energy"], rows)


def ff_table() -> str:
    ff = FIN["fixed_fallback_confirmation"]
    rows = [[k, f"{v['k']}/{v['n']}", f"[{v['wilson95'][0]:.2f}, {v['wilson95'][1]:.2f}]"] for k, v in ff["persisted"].items()]
    return tbl(["controller", f"persisted on fresh seeds {ff['seeds'][0]}-{ff['seeds'][-1]} ('history lost')", "Wilson 95 %"], rows) + (
        f"\nfixed against none: Cohen's h {ff['fixed_vs_none']['cohens_h']}, Fisher exact p {ff['fixed_vs_none']['fisher_exact_p']}; adaptive against none: p {ff['adaptive_vs_none']['fisher_exact_p']}; adaptive_shed against none: p {ff['adaptive_shed_vs_none']['fisher_exact_p']}.\n")


def diagnosis_table() -> str:
    d = json.loads((ROOT / "docs/ecosystem/experiments_stage5_adaptive_diagnosis.json").read_text())
    rows = [[r["scenario"], ", ".join(f"{k}: {v}" for k, v in r["first_decision"].items()), ", ".join(f"{k}: {v}" for k, v in r["decisions"].items()), r["switches"]] for r in d["rows"]]
    return tbl(["scenario", "first decision (10 seeds)", "all decisions (10 seeds, several per run)", "switches"], rows) + f"\n{d['reading']}\n\n*Limit:* {d['limit']}\n"


def sss_table() -> str:
    rows = []
    for isl in FIN["sss_x_mfs"]["islands"]:
        rg = isl["operationally_active_ranges_along_the_axes"]
        rows.append([", ".join(isl["mfs"]), f"{rg['scale'][0]}-{rg['scale'][1]}", f"{rg['size'][0]}-{rg['size'][1]}", f"{rg['speed'][0]}-{rg['speed'][1]}"])
    return tbl(["MFS (same operationally active region)", "scale", "size", "speed"], rows)


def k_table() -> str:
    return tbl(["MFS", "operational robustness", "observational robustness", "addressability", "recoverability", "first observation setting that disagrees"], [[r["mfs"], r["operational_robustness"], r["observational_robustness"], r["addressability"], r["recoverability"], json.dumps(r["first_observation_value_that_disagrees"])] for r in EX["K"]["rows"]])


def listing(key: str, exp: str, limit: int = 12) -> str:
    items = EX[exp][key]
    shown = items[:limit]
    return "\n".join(f"- {x}" for x in shown) + (f"\n- … and {len(items) - limit} more of the same kind (all are in `experiments_stage5.json`, `{exp}.{key}`)" if len(items) > limit else "")


def adaptive_summary() -> str:
    v = [x for x in FIN["reconfiguration"]["verdicts"] if x["controller"] == "adaptive"]
    equal = sum(1 for x in v if x["difference_in_seeds"] == 0)
    sw = [x["scenario"] for x in v if x["switches_per_run"] > 0]
    return (f"Its persistence equalled that of no reconfiguration in {equal} of {len(v)} scenarios and was never better. It never switched in {len(v) - len(sw)} of them (no library MFS matched what it sensed); where it switched ({', '.join(sw) or 'none'}) the run still collapsed.")


def shed_summary() -> str:
    v = [x for x in FIN["reconfiguration"]["verdicts"] if x["controller"] == "adaptive_shed"]
    ad = {x["scenario"]: x for x in FIN["reconfiguration"]["verdicts"] if x["controller"] == "adaptive"}
    more = sum(1 for x in v if x["switches_per_run"] > ad[x["scenario"]]["switches_per_run"])
    ff = FIN["fixed_fallback_confirmation"]["persisted"]["adaptive_shed"]
    return (f"Shedding switched more often than the original adaptive controller in {more} of {len(v)} scenarios, but its persistence equalled the control in {sum(1 for x in v if x['difference_in_seeds'] == 0)} of {len(v)} and it was never better; on fresh seeds in 'history lost' it persisted {ff['k']}/{ff['n']}.")


def build() -> str:
    cc, ca = FIN["class_counts"], FIN["F9_no_mfs"]
    thesis = "複数の作動的実現可能性は一般則ではなく、特定条件に局在する。多くの条件では単一MFSまたはMFS不成立へ収束する。"
    return f"""# XENO ECOSYSTEM — Stage 5 (MEOS-0.4): multiple MFS, alternative routes, reconfiguration

> {thesis}
> (Multiple operational realisations are not a general rule: they are local to particular conditions. In most conditions the result is a single MFS or no MFS.)

Everything below is a statement about a **formal model** (MEOS-0): how this engine's specified operation responds to the manipulations listed. It is not evidence about any physical, biological or ecological system. The visual representation (bodies, map, graph) presents the
model's records; it is never used as evidence. Raw data and interpretation are kept apart: tables are copied from `docs/ecosystem/experiments_stage5.json` by `backend/scripts/make_stage5_doc.py`; the words under them are interpretation and its limits.

## 1. Scope

Stage 5 asks **where** a single MFS, several non-isomorphic MFS, or no MFS holds, and how far alternative routes and reconfiguration help. It does not try to confirm an expected theory. In the finalisation no theory feature was added; the work was to finalise results, the frontend
integration, reproducible captures, performance, regression and this document. Not changed: the baseline result digest, the 264 saved runs, the Stage 4 results and strict nulls.

## 2. Repository state

{frag("git")}

## 3. Stage 4 acceptance

{frag("stage4_acceptance")}

## 4. MEOS-0.4 changes (all opt-in; absent by default, so the baseline digest is unchanged)

- Settable `coupling.gain` (0-2), `environment.renew_delay` (0-40 ticks), `history.lag` (0-40; it matters only while the delayed trace is lower than the current one, i.e. when set from tick 0).
- New operation `ROUTE` (an `m2` block and/or `history` on/off); a controller records `why`, `from`, `to`, `cost`, `trigger` in it. `Run.inject` schedules an intervention for the next tick and keeps the canonical order, so the recorded schedule replays the same run **without** the controller.
- `engine.finalize` adds the digests; the `m2_sensed` trace is back-filled with zeros when M2 is switched on mid-run.
- Backend modules: `mfs5` (exhaustive search and validation), `routes5` (profiles, equivalence levels, topology), `reconf` (controllers), `stats5`, `stage5_experiments` (F-K), `stage5_final` (derived classification). Service routes: `/api/meos/mfs-library`, `/route-topology`, `/reconfigure`, `/mfs-run`.

## 5. What "multiple MFS" means here

An **MFS** is an inclusion-minimal set of components that, with everything else removed at tick 0, still preserves the specified operation (status ACTIVE at horizon 160) under a given condition. **Multiple MFS** means at least two validated inclusion-minimal sets of *different composition* under the same condition
(equal cardinality is not required and not sufficient). The universe is nine components plus, where the condition has one, the M2 tap; all 2^n retained subsets are enumerated. Component roles: necessary, sufficient (completes the core), substitutable (by X in a context), redundant, null, compensatory
(needed only because another condition degrades something), destabilizing.

## 6. Search and validation protocol (fixed in code before the final reading)

- **Search seeds 1-5.** A set *persists* only if it persists in every one of them; the inclusion-minimal persisting sets are the discovered MFS.
- **Validation seeds 6-10.** Every discovered MFS is run again on seeds the search never saw; it is *validated* only if it persists in all five.
- **Candidate** = an inclusion-minimal set under the relaxed criterion (>= 3 of 5 search seeds) or a minimal set of the first 3-seed search; its status says why it is or is not an MFS: validated / failed the search criterion / failed validation / near miss (4 of 5 on both seed sets).
- **Classes:** NO_MFS, SINGLE_MFS, MULTIPLE_MFS (>= 2 validated sets of different composition), UNSTABLE_CANDIDATE (no validated set, candidates exist), INCONCLUSIVE (a near-miss candidate exists).
- Search seeds and validation seeds are **never mixed**: the tables show them in separate columns.

## 7. F1-F16

Result: **{cc.get('NO_MFS', 0)} NO_MFS, {cc.get('SINGLE_MFS', 0)} SINGLE_MFS, {cc.get('MULTIPLE_MFS', 0)} MULTIPLE_MFS, {cc.get('UNSTABLE_CANDIDATE', 0)} UNSTABLE_CANDIDATE, {cc.get('INCONCLUSIVE', 0)} INCONCLUSIVE** of 16 conditions. {FIN['headline']}

{f_table()}
Search seeds 1-5, validation seeds 6-10 in every row. Roles: *history* is the role of the history component in the condition's MFS (necessary / compensatory / substitutable / redundant / null / contributes in some contexts only); *Address* is not a removable component, the entry gives the collapse
share under the Address fault battery. SSS region and observational robustness are those of the default setting.

### 7.1 Candidate sets, with search and validation seeds apart

Every candidate retaining set that was searched is listed with how it fared on the two seed sets. A candidate is **not** an MFS unless its status says *validated*.

{candidates_table()}
**F8:** the first search (3 seeds) found two inclusion-minimal sets. Under the five-seed search and the independent validation the history-free set persisted on 4 of 5 search seeds and on 1 of 5 validation seeds; it did not survive, and **F8 is not counted as a condition with multiple MFS** (class SINGLE_MFS).
The first, 3-seed result files are kept (`experiments_stage5_F_preliminary_3seeds.json`, `experiments_stage5_first_full_run.json`). **F16:** a near-miss candidate (4 of 5 on both seed sets): the data cannot separate it, the class is INCONCLUSIVE and it is not counted as a second MFS.

## 8. F14: two validated MFS (a local result, not a general one)

F14 (SSS scale 1.5 with a delayed M2 tap) has two validated inclusion-minimal sets of equal cardinality and different composition: a **history-mediated** set and an **M2-mediated** set. Both preserve the operation in all five validation seeds.

{f14_table()}
Equivalence reached: through level {FIN['F14_comparison']['equivalence']['equivalent_through_level']}; {FIN['F14_comparison']['equivalence']['verdict']}.

**Claim, limited to what is justified:** {FIN['F14_comparison']['claim']}. Both sets preserve the same specified operation with the same energy use and the same stability across the validation seeds; they differ in resource throughput, recovery latency, perturbation sensitivity, collapse modes, history/M2 dependence and the active range along size and speed.
This is shown for F14 only; it is **not generalised** to other conditions (13 of 16 conditions have a single MFS). The M2 substitution for history here is conditional on this combination of conditions (see section 11).

## 9. F9: a negative result, kept

{ca['statement']}

The search evaluated {ca['subsets_evaluated']} subsets; {ca['persisting_subsets_in_search']} persisted on every search seed, so there is no candidate and no near miss. Class NO_MFS. This is a result about this condition (regrow 0.01, charge 0.2), these reductions and these seeds; it is not universalised, and F9 is not hidden or merged into another class.

## 10. Role of history

{role_table()}
History is necessary in F12, F13 and F15 (scale 1.5), compensatory in F8, F10 and F16 (needed only because the condition degrades coupling or renewal), substitutable by the M2 tap in F3, F11 and F14, redundant in F2 and F4 (unlimited power), null in F9 (no retaining set), and not available in F7. No single role holds across conditions.

## 11. M2 as a substitute for history (experiment G)

{g_table()}
M2 substitutes for history in a minority of the cells where history is needed, and the proportion depends on the M2 variant and on scale, speed, resource and coupling (per-factor proportions are in `experiments_stage5.json`, `G.G1_scope_of_substitution`). The result is a **conditional** substitution, not a general one.

## 12. Dynamic Address (experiment H)

{FIN['address']['statement']}

{FIN['address']['not_concluded']}

{h_tables()}
Stage 4 strict nulls (collision, stale) are kept and are **fixed-configuration** results; Stage 5 H is the dynamic attempt. In the dynamic screen the collision, stale and crossing faults are again null on the persisting arrangements (listed in section 22), and loss, reassignment and partial addressability collapsed the run.

## 13. Reconfiguration (experiment I)

Success is defined by **pre-defined metrics, not by a switch occurring**: persistence better than the no-reconfiguration control by >= 3 of 10 seeds, Fisher exact p < 0.05 (unadjusted), mean switching cost <= 3. Holm correction over the 30 comparisons is reported next to the unadjusted p.

{reconf_table()}
**Adaptive reconfiguration did not beat the controls.** {adaptive_summary()} This is a formal negative result and is kept as such.

**Fixed M2 fallback (kept separate):** the fixed fallback was 'effective' only for 'history lost' (5/10 against 0/10); this does not survive Holm correction over the original 10-seed family. It was therefore re-tested on fresh seeds:

{ff_table()}
The fixed fallback helped in one scenario ('history lost') and in no other; that success is kept separate, does not overwrite the adaptive failure, and is not evidence that adaptive reconfiguration works.

### 13.1 Why the adaptive controller did not act (diagnosis from its own log)

`backend/scripts/diagnose_adaptive_stage5.py` tallies the outcome of every decision of the adaptive controller (`docs/ecosystem/experiments_stage5_adaptive_diagnosis.json`; the main results file is unchanged):

{diagnosis_table()}
So the negative result of section 13 is mostly **structural**: the library lists sets that suffice when everything else is removed at tick 0; in the full arrangement they are already enabled, the cost of "switching" is 0, and the controller does nothing while the run collapses. This separates two questions the F-K experiments had run together: *which configurations can be sustained from the start of a condition* (answered by F: mostly one, sometimes none)
and *whether a run can pass through a stress that arrives in mid-run* (not answered: the library does not prescribe an action for it). It also explains why only the fixed fallback ever helped: it adds a component that is in no MFS of the condition (the M2 tap). This is a statement about this controller and this library, not about reconfiguration in general.

## 14. Shedding controller

`adaptive_shed` (the adaptive controller that may also shed components) is reported separately from the original adaptive controller, the fixed fallback and no reconfiguration (survival, collapse, time to recovery, switches, false and unnecessary switches, switching cost, energy cost):

{controllers_table()}
{shed_summary()} It is a **null result**.

## 15. SSS x MFS (experiment J)

{FIN['sss_x_mfs']['statement']}

Operationally active ranges along the axes (two seeds per point; a range is a statement about the scanned values, not between them), grouped by MFS that share the same region:

{sss_table()}
The ranges differ between some MFS (the M2-mediated set of F14 is operationally active for speed 0.5-1.1 against 0.75-2.0 for the history-mediated set), so the SSS region is MFS-dependent on this grid. The observation-sensitive set coincided with the operationally active set ({FIN['sss_x_mfs']['observation_sensitive_points']} points); **no independent observation-sensitive island is claimed.**
Per-MFS maps are in the research pane (`sssmap=<MFS>`).

## 16. Observation robustness (experiment K)

Four measures are kept independent: operational (does the operation persist under perturbations), observational (does the observer agree with it across observation settings), recoverability and addressability. A set that is unobservable is not thereby a set that failed.

{k_table()}
Observational robustness was 0.00 for **every** MFS: in every one the operation persisted in all confirmation seeds while the observer agreed with it in none of the observation settings of the battery (the first disagreement is listed per MFS). Hence the observer's view does not separate the MFS from each other (a null result), and 'unobservable, not failed' applies to all of them.

## 17. Route equivalence among validated MFS

Levels L1 (preserved operation) - L4 (collapse modes, observational robustness, SSS region); classes: equivalent at the tested preservation level / partially equivalent / non-equivalent / insufficient evidence. ACTIVE alone is never taken as equivalence.

{equivalence_table()}
Only distinct retaining sets are compared (each under the id of its first MFS; the F14 history-mediated set has the same components as MFS-F8-1). 'Equivalent' means: at the levels tested, not that the routes are identical.

## 18. Frontend integration

- **Research pane** (`MfsResults`): the F1-F16 table (compact; all columns behind a fold), the candidate list (validated MFS and rejected candidates, search and validation seeds apart), the comparison of two MFS with the saved equivalence verdict (or the statement that the pair was not compared), the SSS map of an MFS, the reconfiguration group (controller, scenario, outcome table).
- **Research map** layers: active / dormant / failed route, fixed fallback route, adaptive route, current MFS, alternative (validated) MFS, rejected candidate. Validated and candidate are distinguished by line type and mark (solid rule for the current MFS, dashed for validated alternatives, dotted for rejected candidates), not by colour alone.
- **Technical view**: route topology generated from the run record and the saved library only (components with state, path edges, MFS nodes, transitions with tick and cost, dotted candidate nodes); toggles for each route kind; no figure is drawn from anything but run data.
- **Replay markers**: route switch, MFS change, fixed fallback activation, adaptive switch, successful / failed reconfiguration, M2 takeover, history loss, Address reassignment, Address recovery; clicking one shows tick, source/target MFS, trigger, cost and the operational / observed / observability state. (Candidate discovery and validation are properties of the *search*, not of a run, so they are shown in the candidate table and not as timeline events.)
- **Deep links** (`deeplink.ts`): `seed, tick, mfs, route (controller:scenario), experiment, sssmap, sss, address, obs, layer, routelayers, cam, quality`; parse/format round-trips are tested and the same link always gives the same plan.

{frag("captures")}

## 19. Replay

{frag("replay")}

## 20. Performance

{frag("performance")}

## 21. Regression

{frag("regression")}

## 22. Null results (kept)

- F: {len(EX['F']['null_results'])} entries — no second route under 13 conditions, and F9 has no retaining set (section 9).
- G: M2 does not substitute for history in most cells (section 11).
- H: collision, stale and crossing faults are null on persisting arrangements ({len(EX['H']['null_results'])} entries, all identical to the control):
{listing('null_results', 'H', 4)}
- I: persistence equal to no reconfiguration in {len(EX['I']['null_results'])} controller x scenario cells.
- K: observational robustness equal for every MFS.
{frag("null_extra")}

## 23. Failed hypotheses

1. **Multiple MFS is not widespread.** One condition of 16 (F14) has two validated MFS; 13 have one, one has none, one is inconclusive.
2. **The F8 second candidate failed validation** (persisted on 4/5 search and 1/5 validation seeds) and is not counted.
3. **Adaptive reconfiguration did not beat the controls**, nor did the shedding variant; only the fixed M2 fallback helped, in one scenario. The diagnosis (section 13.1) shows the adaptive controller mostly never acted (its matched MFS was already wholly enabled), so the result is about this controller and library, not about reconfiguration in general.
4. **Persistent spatial separation was not sustained:** A2 walked to A1 in every persisting arrangement, so persistent Address dependence could not be tested independently.
5. **The observation-sensitive region did not separate from ACTIVE** on the tested grid.
6. **Cable visual complexity is far below the reference** (measured in Stage 4: close-cable contour complexity 0.47 against 1.59 for the reference; not re-measured in Stage 5, whose changes did not touch the cable geometry): the visual representation does not reach the reference and says nothing about the model.

## 24. Limitations

- The model is a formal one; MFS are relative to the specified operation, the allowed reductions, the preservation criterion, the seeds and the 14 x 14 grid. "No MFS" or "single MFS" means this, not that no other realisation exists.
- Five search and five validation seeds: proportions with wide intervals; near-misses are reported as INCONCLUSIVE, not resolved.
- Experiments G and H do no hypothesis test across cells; the reconfiguration verdicts use Holm over 30 comparisons and several effective results do not survive it.
- The controller senses five features and can only enable components of library MFS; the library holds from-start sufficiency sets, so in mid-run stress the matched MFS is usually already enabled and the controller does not act (section 13.1). A negative result is about this controller.
- Only the removal of components at tick 0 is explored for MFS search; mid-run removal and re-entry are covered in other experiments only.
- The route topology reads enable/disable operations; a parameter stress (e.g. renewal disabled by efficiency) does not appear as a failed component.
- Performance measurements are in a headless browser on one machine that was not idle (see section 20).

## 25. Remaining work

{frag("remaining")}
"""


def main() -> None:
    out = build()
    if "--check" in sys.argv:
        if not DOC.exists() or DOC.read_text() != out:
            sys.exit("docs/ECOSYSTEM_MEOS_STAGE5.md is not what the data produce: run backend/scripts/make_stage5_doc.py")
        print("document matches the data")
        return
    DOC.write_text(out)
    print(f"wrote {DOC} ({len(out.splitlines())} lines)")


if __name__ == "__main__":
    main()
