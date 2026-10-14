"""Build the cumulative English research manuscript (DOCX) of the XENO-ZIRAN 3D laboratory from the repository.

Every number in the text is read from a result file at build time; figures come from scripts/m9_figures.py; source
listings, protocols and results are copied verbatim from the repository. Needs python-docx and matplotlib (not
runtime dependencies):

    python backend/scripts/m9_figures.py backend/experiments/results/lab9 <figdir>
    python backend/scripts/build_m9_manuscript.py <figdir> docs/publication/XENO-ZIRAN-3D-research-record.docx
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "backend" / "experiments" / "results"
L9, LX = RES / "lab9", RES / "labx"


def load(p: Path) -> dict:
    return json.loads(p.read_text())


A9 = load(L9 / "m9ab.json")
C9 = load(L9 / "m9c.json")
D9 = load(L9 / "m9d.json")
E9 = load(L9 / "m9e.json")
F9 = load(L9 / "m9f.json")
W9 = load(L9 / "m9w.json")
ALT = load(L9 / "m9alt.json")
M4, M5, M6, M7 = (load(LX / f"m{i}.json") for i in (4, 5, 6, 7))
LEVA = load(LX / "verification" / "level_a_reproduction.json")
EXP = L9 / "exploratory"
SENS = load(EXP / "latency_sensitivity.json") if (EXP / "latency_sensitivity.json").exists() else None
SUBS = load(EXP / "substitutes.json") if (EXP / "substitutes.json").exists() else None
VER = L9 / "verification"
IND = load(VER / "independent_checks.json") if (VER / "independent_checks.json").exists() else None


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:+.0f} %"


def st(c: dict, m: str) -> str:
    v = c[m]
    return f"{v['status']} ({pct(v.get('relative'))})" if "relative" in v else v["status"]


class Doc:
    def __init__(self) -> None:
        self.d = Document()
        s = self.d.styles["Normal"]
        s.font.name = "Times New Roman"
        s.font.size = Pt(11)
        for name in ("Heading 1", "Heading 2", "Heading 3"):
            self.d.styles[name].font.color.rgb = RGBColor(0x20, 0x21, 0x24)

    def h(self, text: str, level: int = 1) -> None:
        self.d.add_heading(text, level=level)

    def p(self, text: str, italic: bool = False, size: int | None = None) -> None:
        para = self.d.add_paragraph()
        run = para.add_run(text)
        run.italic = italic
        if size:
            run.font.size = Pt(size)
        para.paragraph_format.space_after = Pt(6)

    def bullets(self, items: list[str]) -> None:
        for it in items:
            self.d.add_paragraph(it, style="List Bullet")

    def table(self, rows: list[list[str]], header: bool = True, size: int = 8) -> None:
        t = self.d.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Light Grid Accent 1" if "Light Grid Accent 1" in [s.name for s in self.d.styles] else "Table Grid"
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                c = t.cell(i, j)
                c.text = ""
                r = c.paragraphs[0].add_run(str(cell))
                r.font.size = Pt(size)
                r.bold = header and i == 0
        self.d.add_paragraph()

    def figure(self, path: Path, caption: str) -> None:
        if path.exists():
            self.d.add_picture(str(path), width=Pt(460))
            self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.p(caption, italic=True, size=9)

    def code(self, text: str, size: float = 6.5) -> None:
        for chunk in text.split("\n\n"):
            para = self.d.add_paragraph()
            para.paragraph_format.space_after = Pt(2)
            run = para.add_run(chunk)
            run.font.name = "Courier New"
            run.font.size = Pt(size)

    def page(self) -> None:
        self.d.add_page_break()

    def save(self, p: Path) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        self.d.save(str(p))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ====================================================================================================== front matter
def front(D: Doc) -> None:
    t = D.d.add_heading("Material Pathways, Revision and Extinction in Heterogeneous Simulated Scientific Operations", 0)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    D.p("The XENO–ZIRAN 3D laboratory: research record M1–M9", italic=True)
    D.p("Research record of the XENO ZIRAN SIMULATOR project (software: XENO ZIRAN SIMULATOR runtime, version 0.2.0, "
        "MIT licence; software author as listed in its CITATION.cff: Naoto Fujie). Repository branch lab-m9.", size=9)
    D.p("Status of the claims in this document. Every experimental result reported here is a result inside a "
        "computational simulation: a deterministic network runtime coupled to a rigid-body physics model (MuJoCo). No "
        "result is an empirical observation of a physical laboratory, and no result has been validated against any "
        "physical system. Philosophical terms are used as operational definitions stated in the text; the "
        "computational results do not verify the philosophical framework from which the terms are inherited.",
        italic=True, size=9)
    D.h("Abstract", 1)
    c = A9["contrasts"]
    dep = c["dependence LS: B with A vs without A"]
    D.p(
        "Three simulated scientific systems — a local system (A), a distributed system (B) and a history-keeping system "
        "(C) — select experiments, move material physically between chambers of a simulated laboratory, intervene in "
        "an authoritative runtime and learn from what they can observe. This record asks through which pathways one "
        "such operation changes the conditions of another, when an operation ceases and returns, and whether revising "
        "observation, generating variables or reinserting history changes later inquiry. All experiments were run "
        "under protocols frozen before their confirmatory seeds (SHA-256 recorded), with paired seeds, noise "
        "replicates, Holm-adjusted sign-flip tests and bootstrap intervals. "
        f"In 456 runs of a communication × resource factorial, B's dependence on A (completed transfers "
        f"{pct(dep['completed']['relative'])}, distinct experiments {pct(dep['pairs']['relative'])}, latency "
        f"{pct(dep['latency_mean']['relative'])}) was carried by shared physical resources — gantries, actuator wear and "
        "material — and not by runtime communication; an inert A doing only physical work reproduced the whole "
        "dependence, and with every pathway cut the runs were bit-identical to runs without A. Apparatus failure "
        "without a usable substitute extinguished operation; a repaired failure did not; substitutes that the system "
        "could observe went unused because its selection rule does not represent failure. Sensor relocation changed "
        "what could subsequently be done (more distinct observations, more reachable experiments, also on held-out "
        "worlds) without a detectable change in how effective the interventions were. Variable generation and "
        "contextual historical reinsertion changed decisions but produced no detectable benefit, replicating earlier "
        "negative results. The physical-resource dependence persisted, strengthened or weakened across five "
        "operationally different laboratories and under another physical integration arrangement. An independent "
        "recount found a measurement-definition defect in the latency endpoint. Under the frozen criteria, Level 2 "
        "(demonstrated heterogeneous autonomous scientific operations) is not established; strong Xenoscience (Level "
        "3) is outside what a simulation can establish.")


# ====================================================================================================== Part I
def part1(D: Doc) -> None:
    D.page()
    D.h("Part I — Scientific operational constitution", 1)
    D.h("1. The question", 2)
    D.p("Under which configurations do scientific operations generate, transform, extinguish, restore or replace the "
        "conditions of subsequent scientific inquiry? The question is asked here of operations that can be executed and "
        "measured: a system selects an experiment, the experiment requires material to be moved, the move changes a "
        "runtime that other systems also observe and act on, and the consequences — for the system itself and for "
        "others — are recorded and compared against matched counterfactual runs. The research does not ask what "
        "science is in general. It asks which differences between operations make a difference to what can later be "
        "observed, reached, done and learned, and through which pathways those differences travel.")
    D.h("2. Inherited commitments and their sources", 2)
    D.p("The research sits inside an existing programme whose ordering the project documentation states as: "
        "Operational-Shape Dynamics (theory) › Xenoscience (scientific regime) › Ziran System (architecture family) › "
        "XENO ZIRAN SIMULATOR (application). The following commitments are inherited from the project's own "
        "documentation (docs/THEORY.md, docs/HPO.md, README.md, ziran-xeno-simulator/docs/claims.md) and are used "
        "in the operational form given there:")
    D.bullets([
        "Configurations, connections and operations are modelling units; which units exist is a modelling choice, not "
        "a claim that the world comes in these units.",
        "An effect counts only when it is downstream and systematic: detected by a family-wise paired test, larger "
        "than a practical threshold and than the difference ordinary trajectory divergence produces (noise "
        "replicate), and not explained by the transformation's own bookkeeping.",
        "Non-closure: every status is relative to a configuration, resolution, horizon and seed set; 'not detected' "
        "never means 'absent'; EQUIVALENT (shown within ±5 %) and UNRESOLVED (neither shown) are kept apart; "
        "bit-identical means no difference in the represented and measured state.",
        "Claim-status discipline: implementation properties, synthetic-world results, reconstruction inferences and "
        "empirical observations are distinct; synthetic evidence is not promoted to empirical generalisation.",
        "Layer separation: verified claims from primary sources, operational reconstruction, engineering proxy, "
        "experimental result, the programme's own operational vocabulary and unverified interpretation are kept "
        "apart, and nothing in a lower layer is evidence for an upper one."])
    D.p("The programme also names works that bear directly on this record — Operational Shape Realism, Scientific "
        "Operational Shapes, Critical Points of Science and Nonscience, the Ziran System, Xenoscience and Philosophical "
        "AI. Their texts were not available in the material from which this record was prepared. They are therefore "
        "named here only as the sources of inherited commitments; no argument, definition or conclusion is attributed "
        "to them beyond what the project documentation states, and the operational definitions below are this "
        "record's own. Where a distinction below has the same name as a distinction in those works (for example "
        "operational extinction versus apparatus failure, or scientific classification versus persisting effects), "
        "the computational form here is an implementation of the distinction as stated in this text, not a test of "
        "the original argument.")
    D.h("3. Minimal operational distinctions", 2)
    D.table([
        ["distinction", "operational definition in this record"],
        ["scientific operation", "a system's selection of an experiment (source, target), the physical transfer it "
                                 "requires, the runtime intervention on delivery, and the observation of the outcome"],
        ["consequential intervention", "a delivery whose counterfactual effect on the target (ignitions over 20 steps, "
                                       "computed by forking the runtime) is non-zero; never visible to the systems"],
        ["observation / reachability / effectiveness", "what a system can see (coverage, distinct observed pairs); "
                                                       "what it can subsequently do (executable experiments it knows, "
                                                       "'paths'); how much its interventions change (true gain)"],
        ["pathway", "a channel through which one system's operation can change another's conditions: runtime "
                    "communication (readings along connections), shared physical resources (gantries, queues, wear, "
                    "material, occupancy), and the shared runtime environment"],
        ["operational extinction", "an operation that was active (a delivery in the 160 steps before an intervention "
                                   "at T) completes nothing in [T+30, T+190)"],
        ["apparatus failure", "a gantry failure; it counts as extinction only if the operation stops"],
        ["evidence loss", "the system's memory store is unreadable (closed containment); operation may continue"],
        ["re-ignition: restored / new", "operation resumes after extinction; the share of later experiments on pairs "
                                        "used before T distinguishes restoration of the earlier dependency from a new one"],
        ["substitute path", "available (executable in the laboratory), detectable (observed by the system), "
                            "selectable (detectable and executable), selected, executed"],
    ])
    D.h("4. Four kinds of claim", 2)
    D.p("Four kinds of claim are kept apart throughout: philosophical reconstruction (the distinctions above and their "
        "interpretation); computational simulation (results of the runs); independent computational verification "
        "(re-execution from frozen code, recounts from raw event logs, independently written statistics, a separate "
        "queue model, another physical integration arrangement); and empirical physical validation, of which this "
        "record contains none.")


# ====================================================================================================== Part II
def part2(D: Doc) -> None:
    D.page()
    D.h("Part II — The executable Xeno–Ziran environment", 1)
    D.h("5. Runtime authority", 2)
    D.p("The runtime (backend/xzr/runtime) is the only source of scientific state transitions. It is a deterministic "
        "excitable network of configurations (n = 800 in every experiment here, regime 'intermittent', 40 warm-up "
        "steps, 960-step horizon) with exogenous and endogenous random streams fixed by seeds. A laboratory of 32 "
        "chambers in eight bays is derived from the runtime's address hierarchy; chamber states (containment, "
        "activity, memory, conduits) are computed from runtime state and never set independently.")
    D.h("6. The physical laboratory (MuJoCo 3.14)", 2)
    D.p("A runtime connection that a system requests exists only after material has been moved. Each bay has a "
        "three-axis gantry driven by position servos with force limits; each chamber starts with one 0.8 kg sample; "
        "samples collide with floors, walls (0.7 m), ports and each other; transfers between bays are relayed through "
        "handoff ports. Rigid-body dynamics use a 4 ms timestep with 50 sub-steps per runtime step. Declared "
        "approximations: grasping is a weld constraint; wear lowers health by 0.035·(1 + mass) per completed leg and "
        "0.035 per failed leg after motion; below 0.35 a gantry fails; repair takes 30 steps and one resource unit; "
        "routing takes the short way round the ring. On delivery the sample's load (a fraction of the source "
        "chamber's differences, extracted on grasp) is injected into the target and the connection is made; a "
        "delivery into a closed containment is blocked. The physical model has not been validated against any real "
        "apparatus.")
    D.h("7. Systems", 2)
    D.table([["system", "observation", "reach", "memory", "isolation"],
             ["A local", "sensor at 0.0, radius 3.6", "own bay", "none", "no"],
             ["B distributed", "hub 1.0 + sensors 0.1, 2.0, 7.0, 1.2; readings along runtime connections (≤ 3 hops)",
              "anywhere (relay)", "none", "closes chambers with observed activity > 0.12 for 40 steps"],
             ["C history", "own bay", "own and adjacent bays", "store chamber 1.3 (unreadable when closed)", "no"]])
    D.p("All three use the same decision rule — a ridge model of their own observed outcomes with an exploration bonus "
        "— and a budget of 24 units (a transfer request costs 1, also when the transfer is refused). The true effect of "
        "a delivery is computed by the harness through a runtime fork and is never read by a system (tested by "
        "inspection of the decision code).")
    D.h("8. Recording, replay, live streaming and rendering", 2)
    D.p("Runs are recorded step by step (schemas xzr.labrun/1–3): runtime fingerprint (SHA-256 over every state array "
        "and the random-generator state), apparatus state and digest, physics state, system state and every event with "
        "its provenance. Replay re-executes a record from its configuration alone and requires agreement at every step "
        "and on every event list. Live runs step in their own thread and stream to viewers with backpressure that "
        "coalesces visual frames but never drops events; a stopped live run is written as an ordinary record. The "
        "Three.js viewer draws only recorded or streamed values; the laboratory layer imports no rendering code. "
        "Rendering frame rate has no access to the run.")
    D.h("9. Statistics and protocols", 2)
    D.p("Conditions are paired by seed (same world, warm-up and streams). A contrast reports the paired mean, a "
        "two-sided sign-flip test (exact up to 16 pairs, otherwise 20,000 Monte Carlo patterns), a percentile "
        "bootstrap 95 % interval and a Holm adjustment within each family of measures. DETECTED requires p_holm < 0.01, "
        "|mean| ≥ 2 % of scale and |mean| above the noise floor from a noise replicate (another endogenous stream). "
        "Each experiment's hypotheses, endpoints, seeds and criteria were fixed in a protocol whose SHA-256 is pinned "
        "in code; the runners refuse to start if the protocol differs.")


# ====================================================================================================== Part III
def part3(D: Doc) -> None:
    D.page()
    D.h("Part III — Heterogeneous experimental systems (M4–M7)", 1)
    D.p("The M4–M7 experiments were run under docs/LAB_PROTOCOL.md (SHA-256 ce00c75f…), 24 paired seeds, 736 runs. "
        f"All 736 were later re-executed from the frozen code (tag m7-verified): "
        f"{sum(v['fingerprints_identical'] for v in LEVA['experiments'].values())} of "
        f"{sum(v['runs'] for v in LEVA['experiments'].values())} run fingerprints, and every contrast, verdict and mean, "
        "are identical (verification Level A).")
    m = M4["means"]
    D.h("10. M4 — heterogeneity, and what it consists in", 2)
    D.table([["per run (mean)", "A", "B", "C"]] + [
        [lab, *[f"{m[f'solo_{s}/{s}'][k]:.3g}" for s in "ABC"]] for lab, k in
        (("connection paths observed", "paths"), ("coverage", "coverage"), ("distinct experiments", "pairs"),
         ("completed transfers", "completed"), ("true gain", "true_gain"))])
    D.p(f"Every pair of systems differs (verdict {M4['verdicts']['M4_heterogeneity']}). When observation, reach, memory "
        "and isolation are equalised, the three systems are bit-identical. The heterogeneity demonstrated is therefore "
        "configuration-dependent operational heterogeneity: differences in what a system can observe, reach, remember "
        "and close. It is not a diversity of scientific decision procedures — the decision rule is shared — and this "
        "record does not claim one.")
    v5 = M5["verdicts"]
    o = M5["contrasts"]["O vs F"]
    D.h("11. M5 — revision", 2)
    D.p(f"Observation revision was consequential by the M5 criterion ({v5['M5A_observation_revision']}): distinct "
        f"experiments {st(o, 'pairs')}, completed {st(o, 'completed')}, true gain {st(o, 'true_gain')}. Variable "
        f"generation was {v5['M5B_variable_generation']}: {v5['candidates_adopted']} of {v5['candidates_evaluated']:,} "
        "candidates adopted, with no change in prediction error or gain.")
    D.h("12. M6 — historical reinsertion", 2)
    h = M6["contrasts"]["H2 vs H1"]
    D.p(f"Contextual memory against ordinary memory on post-change true gain: {st(h, 'true_gain_post')} — "
        f"{M6['verdicts']['primary_H2_vs_H1']}. An inherited, untraceable negative record on history dependence is "
        "kept as such; it was neither reconstructed nor overwritten.")
    v7 = M7["verdicts"]
    D.h("13. M7 — cross-system effects", 2)
    D.table([["test", "result"],
             ["T2 interference", "holds: " + "; ".join(f"{k.split(': ')[1]}: {', '.join(x)}"
                                                       for k, x in v7["T2_interference"].items() if x)],
             ["T3 extinction (≥ 6/24)", f"not met: {v7['T3_extinction']['A_blocked_by_isolation_seeds']}/24"],
             ["T4 substitution", f"holds: {v7['T4_substitution']['A_completed_status_vs_noIso']}"],
             ["T5 re-ignition (≥ 6/24)", f"holds: {v7['T5_reignition']['seeds_with_experiments_on_reopened_chambers']}/24"],
             ["T6 cross-system history", "not met: " + (", ".join(v7["T6_cross_system_history"]) or "no detected measure")],
             ["T7 counterfactual removal", "not met: B's dependence on A persists when its readings no longer depend on "
                                           "connections (" + ", ".join(v7["T7_counterfactual_removal"]
                                                                       ["B_dependence_on_A_with_comm_free"]) + ")"]])
    D.p("T7 is the reason the M4–M7 Level 2 criterion was not met, and it remains not met: the M7 test asked whether "
        "B's dependence on A is carried by communication, and it is not. M9 asks the next question — what does carry "
        "it — under its own frozen protocol. Its answer does not re-score T7.")



# ====================================================================================================== Part IV
def part4(D: Doc, figs: Path) -> None:
    D.page()
    D.h("Part IV — Independent causal verification: communication and physical resources (M9-A/B)", 1)
    c, v = A9["contrasts"], A9["verdicts"]
    D.h("14. Design", 2)
    D.p("M7's T7 left open what carries B's dependence on A. M9-A crosses communication (B's readings along live "
        "runtime connections, L, or along the connection graph as it was when the systems started, F) with physical "
        "resources (shared, S, or separated, P: A has its own carriage in every bay and its own sample in every chamber, "
        "which collide with nothing of the other group). In every cell B's dependence on A is the per-seed difference "
        "between the run with A and the run without A. Separation gives each group what it has alone; the laboratory's "
        "total capacity is then larger, and that is the contention removed. Private material shifts the baseline "
        "numerically (extra idle bodies change the physics integration) even without A, so effects are estimated from "
        "dependences within cells, never from B's raw outcomes across cells. M9-B separates one resource at a time "
        "with communication live: carriages (G), queue capacity (Q), A's wear (W), priority for B and C (P), material (M).")
    D.p("Two identity checks validate the instrument. An idle A (budget 0) must leave every run bit-identical to the "
        "run without A, and an inert A — doing all its physical work but changing nothing in the runtime — must, with "
        "resources separated and communication frozen, leave every run bit-identical to the run without A. Both hold: "
        + "; ".join(f"{x['pair']}: {x['identical_seeds']}/{x['seeds']} seeds" for x in v["identity_checks"])
        + ". No noise contrast was flagged. There is therefore no hidden coupling through the shared physics model, "
        "the caches or the decision scheduling.")
    D.h("15. Results", 2)
    rows = [["contrast (24 paired seeds)", "completed", "distinct experiments", "latency"]]
    for k in c:
        if k.startswith("noise") or "Q-separated" in k or "P-separated" in k:
            continue
        rows.append([k, st(c[k], "completed"), st(c[k], "pairs"), st(c[k], "latency_mean")])
    D.table(rows, size=7)
    D.p(f"B depends on A with shared resources ({', '.join(v['dependence_shared_live_detected'])} DETECTED) and equally "
        "with communication frozen. Resource mediation (H-A1) holds; communication mediation (H-A2) does not; no "
        "interaction; no residual dependence with both pathways cut (H-A3 not supported). An inert A, which only "
        "occupies gantries, wears them and moves material, reproduces the whole dependence; A's runtime effects alone "
        "(real versus inert A with every physical and communication pathway cut) change nothing detectable.")
    D.p("Separating carriages removes the dependence on distinct experiments and latency. Exempting A's legs from wear "
        "removes about half of the latency effect: wear is a temporal pathway through which A's past work slows B's "
        "later transfers. Separating material removes the loss of distinct experiments — A and B compete for the "
        "sample in the chamber both observe — but increases B's latency dependence, because an A that never runs out of "
        "material keeps the shared gantry busier. Private queue capacity and priority are bit-identical to the shared "
        "laboratory, as stated before confirmation: each system has at most one pending transfer, so queues never fill. "
        "Shared transport ports are not a pathway here because A never relays.")
    D.figure(figs / "fig1_factorial.png", "Figure 1. B's dependence on A by pathway: relative paired effect of A's "
             "presence on B (bars), bootstrap 95 % intervals (red), DETECTED in dark.")
    D.h("16. The latency endpoint: a measurement-definition defect", 2)
    D.p("The frozen protocol states the latency endpoint as the mean request-to-delivery latency. The harness computed "
        "it over every physically completed transfer of the system — including transfers whose sample reached the "
        "target chamber but whose delivery was then refused because the target's containment was closed. These are "
        "different operational quantities: physical transport completion (the last leg releases the sample in the "
        "target chamber) and successful delivery (the runtime accepts the material and the connection is made). The "
        "independent recount (verification B1) counted successful deliveries and disagreed with the harness on 5 of 12 "
        "re-executed runs. This is a measurement-definition defect of the frozen analysis. The frozen results are not "
        "changed; the original endpoint is to be read as physical-completion latency, and a separately labelled "
        "exploratory sensitivity analysis recomputes every latency contrast under the delivery definition.")
    if SENS:
        D.p(f"The sensitivity analysis re-executed {SENS['runs']} runs (fingerprints equal to the published runs: "
            f"{SENS['all_fingerprints_match_published']}; harness metric equal to physical-completion latency in every "
            f"run: {SENS['harness_metric_is_physical_completion_latency']}). Blocked deliveries by cause: "
            + ", ".join(f"{k}: {n}" for k, n in SENS["blocked_by_cause"].items())
            + f"; runs in which the two definitions differ: {len(SENS['discrepant_runs'])}.")
        rows = [["contrast (latency)", "physical completion (frozen)", "successful delivery (sensitivity)"]]
        for k in SENS["contrasts"]["physical"]:
            a, b = SENS["contrasts"]["physical"][k], SENS["contrasts"]["delivered"][k]
            rows.append([k, f"{a['status']} ({pct(a['relative'])})", f"{b['status']} ({pct(b['relative'])})"])
        D.table(rows, size=7)
        D.p(SENS_TEXT)
        D.table(sens_distribution(), size=7)
        D.figure(figs / "fig9_latency_sensitivity.png", "Figure 9. Latency contrasts under the frozen (physical "
                 "completion) and the delivery definitions (exploratory).")
    D.h("17. Independent verification", 2)
    if IND:
        s = IND["summary"]
        D.bullets([
            f"Event recount from raw records (B1, {len(IND['B1_recount'])} runs): completed and failed transfers agree in "
            f"every run; latency disagrees in {len(s['B1_disagreements'])} runs (the definition defect above).",
            f"Extended event recount ({len(IND['B1_events'])} runs: attempted, physically completed and delivered "
            f"transfers, blocked deliveries, gantry failures, repairs, budget): agreement with the harness "
            f"{s['B1_events_all_agree']}; re-executed runs equal the published runs {s['fingerprints_match_published']}.",
            f"Extinction and re-ignition recounted from the protocol text ({len(IND.get('B1_extinction', []))} M9-C runs): "
            f"agreement {s['B1_extinction_all_agree']}.",
            f"Independently written statistics (B2): the five primary M9-A verdicts agree: {s['B2_all_agree']}.",
            f"Wear (C2): recorded gantry health values inconsistent with the declared wear rules: "
            f"{s['C2_wear_inconsistencies']}. Attributed from the event log, A caused "
            f"{100 * min(w.get('A', 0) / sum(w.values()) for w in IND['wear_on_bay0_by_system']):.0f}–"
            f"{100 * max(w.get('A', 0) / sum(w.values()) for w in IND['wear_on_bay0_by_system']):.0f} % of the wear on "
            "the bay-0 gantry that B also uses (re-run seeds with A present).",
            f"Material (C3): B's 'no material' transfer failures in the re-run seeds — with A: "
            f"{s['C3_B_no_material_failures']['LS+']}, without A: {s['C3_B_no_material_failures']['LS0']}.",
            "Queue model (C1): a first-in-first-out model fed with the recorded bay-0 gantry legs predicts B's waiting "
            f"at {IND['C1_queue_model']['B_wait_predicted_with_A']:.1f} steps with A's legs and "
            f"{IND['C1_queue_model']['B_wait_predicted_A_legs_removed']:.1f} without them; B's waiting in the runs "
            f"without A is {IND['C1_queue_model']['B_wait_observed_without_A_runs']:.2f} steps. Queueing behind A's legs "
            "accounts for B's added wait on that gantry. (The model takes service durations from the runs; it checks "
            "the queueing mechanism, not the physics.)"])
    alt = ALT["verdicts"]
    D.p("Alternative physical arrangement (verification E; 2 ms timestep, 100 sub-steps, 12 seeds): dependence "
        f"{alt['dependence (shared, live)']}; physical-only pathway {alt['physical-only pathway']}; residual "
        f"{alt['residual dependence (separated, frozen)']}. The dependence keeps its direction and detection; the "
        "physical-only pathway is detected on latency, and with half the seeds its effects on completed transfers and "
        "distinct experiments are not resolved. This is a different integration arrangement of the same model, not an "
        "independent implementation.")
    D.h("18. Material mediation", 2)
    D.p("The pathway identified is ordinary and concrete. Two systems that share a manipulator, its wear and the "
        "material in a chamber both observe change each other's conditions of inquiry: one system's past and present "
        "physical work delays the other's transfers and removes experiments it could otherwise perform. That shared "
        "material and apparatus mediate dependence between experimenters is not a new philosophical principle; what "
        "this record adds is a controlled computational separation of that pathway from communication and from the "
        "shared runtime environment, with identity checks that exclude hidden coupling. The communication-specific "
        "test of M7 (T7) remains failed: the dependence was never communication-borne, and that is now explained, "
        "not overturned.")


SENS_TEXT = (
    "Every one of the 85 blocked deliveries in the re-executed runs was blocked by B's own isolation: B closes a chamber "
    "whose observed activity is high and, in a slow transfer already under way, later delivers material into that same "
    "chamber. These are long transfers, so including them raises the physical-completion mean. Under the delivery "
    "definition every latency verdict keeps its status and direction except one: the mediation of B's latency "
    "dependence by A's wear is DETECTED under the frozen definition and UNRESOLVED under the delivery definition, with "
    "a similar estimate. The conclusions that physical resources carry the dependence, that communication does not, "
    "that no residual dependence remains and that carriages and material mediate it do not depend on the definition; "
    "the wear finding on latency does, and is reported as definition-sensitive. The two definitions also differ in "
    "what they say about B: physical-completion latency includes the time B's own containment decision wasted.")


def sens_distribution() -> list[list[str]]:
    import numpy as np  # noqa: PLC0415
    rows = [["condition", "transfers (physical)", "deliveries", "mean latency physical", "mean latency delivered",
             "median physical", "median delivered"]]
    for cond in ("LS+", "LS0", "FS+", "FS0", "LP+", "LP0", "FP+", "FP0", "LSi"):
        rs = [x for x in SENS["runs_detail"] if x["cond"] == cond]
        ph = [x["physical_latency_mean"] for x in rs if x["physical_latency_mean"] is not None]
        de = [x["delivered_latency_mean"] for x in rs if x["delivered_latency_mean"] is not None]
        rows.append([cond, str(sum(x["physical_n"] for x in rs)), str(sum(x["delivered_n"] for x in rs)),
                     f"{np.mean(ph):.1f}", f"{np.mean(de):.1f}", f"{np.median(ph):.1f}", f"{np.median(de):.1f}"])
    return rows


# ====================================================================================================== Part V
def part5(D: Doc, figs: Path) -> None:
    D.page()
    D.h("Part V — Extinction and re-ignition (M9-C)", 1)
    D.h("19. Cessation, failure, evidence and return", 2)
    k, v, c = C9["counts"], C9["verdicts"], C9["contrasts"]
    D.p("An intervention at step 320 (closures reopened at 640) removes one condition of an active operation; the "
        "definitions are those of Part I. Conditions: X0 none; X1 bay-0 gantry failure without repair resources; X2 the "
        "same with a repair resource; X3 X1 then one resource moved to bay 0 at 480; X4 X1 with reach into adjacent "
        "bays; X4b X1 with reach and sensing of adjacent bays; X5 A's observed chambers closed; X6 the same with sensor "
        "relocation; X7 B's hub and sensor chambers severed from every connection; X7f the same with B's communication "
        "frozen; X8 C's memory store closed; X10 / X10n C's whole bay closed, with and without memory.")
    rows = [["condition", "active before", "extinct", "re-ignited", "same dependency", "new dependency",
             "apparatus failure"]]
    for cond, x in k.items():
        rows.append([cond, f"{x['active_before']['count']}/24", f"{x['extinct']['count']}/{x['extinct']['eligible']}",
                     f"{x['reignited']['count']}/{x['reignited']['eligible']}",
                     f"{x['restored_same']['count']}", f"{x['new_dependency']['count']}",
                     f"{x['apparatus_failed']['count']}/24"])
    D.table(rows, size=7)
    D.table([["criterion", "met"]] + [[a, str(b)] for a, b in v.items()], size=7)
    D.table([["contrast", "measures"]] + [[a, "; ".join(f"{m}: {x['status']}" for m, x in b.items()
                                                        if m in ("extinct", "completed_after", "outage_paths",
                                                                 "reuse_share", "reignition_step"))]
                                          for a, b in c.items()], size=7)
    D.p("Apparatus failure is not operational extinction. Gantries failed naturally in every seed of X0 and were "
        "repaired, and no operation ceased; a failure with a repair resource (X2) left operation intact in 22 of 24 "
        "seeds. A failure without repair (X1) extinguished A's operation in every seed. Loss of observation (X5) also "
        "extinguished it in every seed, and reopening re-ignited it in every seed — in 15 of 24 seeds on the pairs used "
        "before, so that re-ignition restored the earlier dependency. With sensor relocation (X6) re-ignition happened "
        "as often and as early, but in 23 of 24 seeds as a new dependency (reuse of earlier pairs 0.49 against 0.92): "
        "observation revision did not prevent the cessation but changed what returned. Loss of evidence (X8: memory "
        "store closed) is not loss of operation: C continued in 23 of 24 seeds (the one remaining seed never needed "
        "its memory while the store was closed, so C8 is not met as written). Cutting B's connections (X7) collapsed "
        "the experiments B could know of to almost none and cut its later deliveries by three quarters, but one "
        "transfer already under way landed in the window in most seeds, so the frozen definition of extinction is not "
        "met (C7). History did not change what returned after C's bay was reopened (C9).")
    D.h("20. Substitute paths", 2)
    D.p("Redundant reach (X4) and redundant reach with observation (X4b) did not prevent extinction (C4, C4b not met), "
        "and redistributing a repair resource 160 steps after the failure (X3) did not re-ignite it (C3 not met). The "
        "reason is visible in the budgets: after the failure A keeps requesting transfers from bay-0 sources, each "
        "refused request costs a unit, and the budget is gone within about 60 steps (Figure 7). An exploratory "
        "analysis distinguishes five states of a substitute path during the outage.")
    if SUBS:
        sm = SUBS["summary"]
        D.table([["", "X4 (reach)", "X4b (reach + observation)"]] + [
            [lab, f"{sm['X4'][key]:.2f}", f"{sm['X4b'][key]:.2f}"] for lab, key in (
                ("available experiments per decision (executable, observation ignored)", "available_mean"),
                ("detectable (known to A)", "detectable_mean"), ("selectable (known and executable)", "selectable_mean"),
                ("share of A's choices that were executable", "selected_executable_share"),
                ("decisions with a selectable substitute", "decisions_with_a_selectable_substitute"),
                ("executed substitute transfers", "executed_substitutes"))] + [
            ["seeds with a selectable substitute", str(sm["X4"]["seeds_with_a_selectable_substitute"]),
             str(sm["X4b"]["seeds_with_a_selectable_substitute"])],
            ["seeds with an executed substitute", str(sm["X4"]["seeds_with_an_executed_substitute"]),
             str(sm["X4b"]["seeds_with_an_executed_substitute"])]], size=7)
        D.p(SUBS_TEXT)
        D.figure(figs / "fig10_substitutes.png", "Figure 10. Substitute paths during the outage (exploratory).")
    D.figure(figs / "fig6_extinction.png", "Figure 6. Extinction, re-ignition and restoration by condition.")
    D.figure(figs / "fig7_budget.png", "Figure 7. Budget spent by the target system per condition.")
    D.p("The distinctions the results support are these: operational cessation is distinct from apparatus failure and "
        "from loss of evidence; a substitute can be physically available without being detectable as executable; re-ignition can "
        "restore an earlier dependency or create another; and runtime effects of earlier deliveries persist after an "
        "operation ceases (connections made before the intervention remain in the runtime). None of this yields a "
        "boundary between science and non-science; it shows, inside one simulation, that these are separable "
        "conditions.")


SUBS_TEXT = (
    "Executability is checked over every gantry on the transfer's route. (A first version of this analysis checked only "
    "the source's gantry and over-counted substitutes whose last leg needs the failed bay-0 gantry; it is kept in the "
    "repository, labelled superseded.) The result is unambiguous. Executable substitutes were physically available "
    "throughout the outage — hundreds of experiments in the laboratory within A's reach rule. With extended reach "
    "alone, A detected only the experiments of its own bay. With extended reach and observation, it detected about "
    "ten experiments per decision, but not one of them was executable: each had its source or its target in bay 0 "
    "and therefore needed the failed gantry, while the executable experiments in adjacent bays were not among the "
    "pairs it could observe within its reach. No substitute was selectable, none was selected and none was executed. "
    "The failure to substitute therefore arose from the geometry of observation and reach — the alternatives that "
    "existed were not accessible to the system as executable experiments — compounded by resource exhaustion: every "
    "refused request still cost budget, so the system spent its whole budget on experiments that could not run. The "
    "selection rule's blindness to apparatus failure is real but was not decisive here, because no executable "
    "alternative was ever among its options.")

# ====================================================================================================== Part VI
def part6(D: Doc, figs: Path) -> None:
    D.page()
    D.h("Part VI — Observation revision and variable generation", 1)
    c, h = D9["contrasts"], D9["heldout"]
    D.h("21. What revising observation changes (M9-D)", 2)
    D.p("System A alone; 24 seeds and 16 held-out worlds. Conditions: fixed observation (F), parameter adaptation (R), "
        "the M5 revision (O: sensor relocation toward material and untried targets, plus window revision), relocation "
        "only (Oloc), window only (Owin), outcome-guided relocation (Oout) and Oout with adaptation (OoutR).")
    rows = [["contrast", "true gain", "gain / transfer", "distinct observed pairs", "redundant observations",
             "reachable experiments", "completed"]]
    for k in ("O vs F", "Oloc vs F", "Owin vs F", "Oout vs F", "OoutR vs F", "R vs F", "F~ vs F"):
        x = c[k]
        rows.append([k, st(x, "true_gain"), st(x, "gain_per_completed"), st(x, "distinct_observed_pairs"),
                     st(x, "redundant_observations"), st(x, "paths"), st(x, "completed")])
    for k in ("O vs F", "Oout vs F"):
        x = h[k]
        rows.append([k + " (held-out)", st(x, "true_gain"), st(x, "gain_per_completed"), st(x, "distinct_observed_pairs"),
                     st(x, "redundant_observations"), st(x, "paths"), st(x, "completed")])
    D.table(rows, size=7)
    v = D9["verdicts"]
    D.p(f"D1 (outcome-guided revision improves true gain, main and held-out): {v['D1_outcome_guided_revision_improves_gain']}. "
        f"D2 (the M5 direction — revision lowers effectiveness — replicates): "
        f"{v['D2_M5_revision_lowers_effectiveness_replicated']}. On these new seeds the M5 revision is "
        f"{pct(c['O vs F']['true_gain']['relative'])} on true gain (UNRESOLVED), where M5 had found "
        f"{pct(M5['contrasts']['O vs F']['true_gain']['relative'])} (also UNRESOLVED); the two directions are within the "
        "noise of the endpoint, and the M5 record stands as published.")
    D.p("The decomposition is unambiguous. Sensor relocation produces the whole change and window revision produces "
        "none (Owin is EQUIVALENT to F). Relocation generates new observable differences (more distinct observed "
        "pairs, far fewer redundant observations) and enlarges what the system can subsequently do (more executable "
        "experiments known to it, on the main and on held-out worlds), at the cost of slightly fewer completed "
        "transfers. Effectiveness — what the interventions change — is not detectably different. Three consequences "
        "that are often run together therefore come apart in this configuration: changing what can be observed, "
        "changing which experiments can subsequently be performed, and changing how effective those experiments are. "
        "The first two occurred; the third was not shown. This is a result for one world class and one laboratory "
        "layout, and the cross-world results (Part VIII) qualify it further.")
    D.figure(figs / "fig2_revision.png", "Figure 2. Relative effects of the revision conditions against fixed "
             "observation (bars: paired mean / scale; red: bootstrap 95 % interval; dark: DETECTED).")
    D.figure(figs / "fig3_reachability.png", "Figure 3. Reachable experiments versus true gain for the M5 revision and "
             "outcome-guided revision, main and held-out worlds.")
    D.h("22. Variable generation (M9-E)", 2)
    e, dg = E9["contrasts"], E9["diagnostics"]
    D.p("Candidate variables (products of features, trends, a relational connection count) are adopted only if they "
        "lower the leave-one-out error of the system's own observed outcomes by ≥ 5 % and beat the same candidate "
        "with permuted values. M9-E compares this with no generation (F), with random adoption at the same times (Vr), "
        "and repeats the three at low exploration (Flo, Vlo, Vrlo), where the model rather than the exploration bonus "
        "drives choices. Decision diagnostics recompute each choice without the variables and without the predictions.")
    D.table([["contrast", "|prediction − true effect|", "|prediction − observed|", "true gain"]] +
            [[k, st(e[k], "abs_pred_error"), st(e[k], "obs_error_mean"), st(e[k], "true_gain")] for k in e])
    D.table([["condition", "variables adopted / run", "decisions changed without variables",
              "decisions changed without predictions", "corr(observed outcome, true effect)"]] +
            [[k, f"{x['variables_adopted']:.2f}", "—" if x["changed_without_variables"] is None
              else f"{x['changed_without_variables']:.2f}", f"{x['changed_without_prediction']:.2f}",
              f"{x['obs_true_corr']:.2f}"] for k, x in dg.items()])
    ve = E9["verdicts"]
    D.p(f"E0 (the M5 negative result replicates): {ve['E0_M5_negative_replicated']}. E1 (variables are consequential "
        f"when the model drives choice): {ve['E1_variables_consequential_when_model_drives_choice']}. E2 (the "
        f"criterion beats random adoption): {ve['E2_criterion_beats_random_adoption']}.")
    D.p("The distinctions the result requires are these. Candidate generation and selection occurred (thousands of "
        "candidates in M5, about one adoption per run here). Adoption changed intervention selection: roughly a tenth "
        "of decisions would have been different without the adopted variables. It did not change prediction error, "
        "experimental effectiveness or later accessibility detectably, and the adoption criterion chose no better than "
        "chance. The diagnostic that explains this best is the weakness of the systems' own measurement: their observed "
        "outcome correlates with the true effect of what they did at about 0.1–0.2. A variable selected because it "
        "predicts the observed outcome cannot be expected to sharpen discrimination of an effect the observation "
        "barely registers. Nothing here is a scientific discovery; numerical novelty in the feature set is not "
        "scientific novelty.")
    D.figure(figs / "fig4_variables.png", "Figure 4. Variable generation: share of decisions that adopted variables "
             "change, and the correlation between the systems' observed outcome and the true effect.")


# ====================================================================================================== Part VII
def part7(D: Doc, figs: Path) -> None:
    D.page()
    D.h("Part VII — Historical reinsertion", 1)
    D.h("23. Contextual history against its controls (M9-F)", 2)
    c, dg, v = F9["contrasts"], F9["diagnostics"], F9["verdicts"]
    D.p("System C alone, with the M6 configuration change (two chambers of its bay partly closed at step 480). "
        "Conditions: no memory (H0), ordinary (H1), contextual (H2), shuffled (H3), write-only (H4: reinsertion "
        "disabled), delayed by 120 steps (H6), contextual with a wrong context (H7), H1 and H2 at low exploration, and a "
        "noise replicate of H2. No condition gives C access to the true environmental state: contexts are computed "
        "from what C can observe, and the true effect is never read.")
    D.table([["contrast", "true gain after the change", "true gain", "distinct experiments", "prediction error"]] +
            [[k, st(x, "true_gain_post"), st(x, "true_gain"), st(x, "pairs"), st(x, "abs_pred_error")]
             for k, x in c.items()])
    D.table([["condition", "decisions changed without memory", "decisions changed without predictions"]] +
            [[k, "—" if x["changed_without_memory"] is None else f"{x['changed_without_memory']:.2f}",
              f"{x['changed_without_prediction']:.2f}"] for k, x in dg.items()])
    D.p("Verdicts: " + "; ".join(f"{k}: {x}" for k, x in v.items() if k != "noise_detected") + ".")
    D.p("History is reinserted — memory changes between a third and a half of C's choices — and it steers the system "
        "without any detectable benefit after the change, and without any detectable difference from shuffled, "
        "delayed, disabled or deliberately wrong-context memory. The M6 negative result is replicated on new seeds; "
        "M6's one detected memory effect (fewer distinct experiments with memory than without) is not. The record "
        "does not show that contextual history creates non-redundant operational differences in this configuration. "
        "Of the questions the protocol asked, history changes experimental selection (yes, by the diagnostics); it does "
        "not change apparatus configuration (C has no apparatus action other than transfers); its effect on "
        "intervention outcomes, reachability and stability against stochastic variation is not shown. Recovery after "
        "failure was examined in M9-C: closing C's whole bay and reopening it produced the same re-ignition timing and "
        "the same reuse of earlier pairs with and without memory.")
    D.figure(figs / "fig5_history.png", "Figure 5. Historical reinsertion: post-change true gain contrasts (left) and "
             "the share of decisions memory changes (right).")


# ====================================================================================================== Part VIII
def part8(D: Doc, figs: Path) -> None:
    D.page()
    D.h("Part VIII — Cross-world scientific operations", 1)
    D.h("24. Persistence, attenuation, amplification and disappearance", 2)
    D.p("Five laboratories, each changing a runtime or physical dependency rather than appearance, were fixed before "
        "confirmation; 16 seeds each, 560 runs:")
    D.bullets([f"{k}: {v}" for k, v in W9["worlds"].items()])
    base = A9["contrasts"]
    rows = [["laboratory", "dependence: completed", "pairs", "latency", "residual (all cut)", "physical-only (latency)",
             "outcome-guided revision: distinct experiments"]]
    rows.append(["base (24 seeds)", st(base["dependence LS: B with A vs without A"], "completed"),
                 st(base["dependence LS: B with A vs without A"], "pairs"),
                 st(base["dependence LS: B with A vs without A"], "latency_mean"),
                 "not detected", st(base["physical-only pathway: inert A (shared) vs no A"], "latency_mean"),
                 st(D9["contrasts"]["Oout vs F"], "pairs")])
    for w, cs in W9["contrasts"].items():
        dep, res, phys, rev = (cs["dependence (shared, live)"], cs["residual dependence (separated, frozen)"],
                               cs["physical-only pathway"], cs["outcome-guided revision vs fixed (A)"])
        rows.append([w, st(dep, "completed"), st(dep, "pairs"), st(dep, "latency_mean"),
                     ", ".join(f"{m}: {res[m]['status']}" for m in ("completed", "pairs", "latency_mean")),
                     st(phys, "latency_mean"), st(rev, "pairs")])
    D.table(rows, size=7)
    D.p("Classification against the base laboratory (protocol §7): the physical-resource dependence persists in the "
        "transport and dynamic laboratories; it is amplified where repair resources are absent (scarce: completed "
        "transfers −45 %); it persists in part where B's connections are repeatedly severed (fractured: detected on "
        "distinct experiments and latency, not on completed transfers); and it is not detected where observation is "
        "restricted (sensor) — which, with 16 seeds and a smaller point estimate, is inconclusive rather than evidence "
        "of absence. Residual dependence with every pathway cut is detected in no laboratory. The gain in distinct "
        "experiments from outcome-guided relocation, DETECTED in the base laboratory, is detected in three of the five "
        "(sensor, fractured, dynamic) and unresolved in two (transport, scarce); reachable experiments were not among "
        "the frozen cross-world measures. These are results across operational variants of one world model and one "
        "laboratory geometry; they do "
        "not establish generality beyond them.")
    alt = ALT["verdicts"]
    D.p("Under another physical integration arrangement (2 ms timestep, 100 sub-steps; 12 seeds) the dependence "
        f"remains: {alt['dependence (shared, live)']}. The physical-only pathway: {alt['physical-only pathway']}. "
        f"Residual: {alt['residual dependence (separated, frozen)']}.")
    D.figure(figs / "fig8_worlds.png", "Figure 8. B's dependence on A across the base laboratory and five operationally "
             "different laboratories.")


# ====================================================================================================== Level 2
def level2() -> list[tuple[str, bool, str]]:
    """The seven conditions of LAB_PROTOCOL_M9.md §9, evaluated from the result files."""
    va, vc = A9["verdicts"], C9["verdicts"]
    held_paths = D9["heldout"]["O vs F"]["paths"]
    c3 = (M5["verdicts"]["M5A_observation_revision"] == "CONSEQUENTIAL"
          and (D9["verdicts"]["D1_outcome_guided_revision_improves_gain"]
               or (held_paths["status"] == "DETECTED" and held_paths["mean"] > 0)))
    c4n = sum(bool(vc[k]) for k in ("C1_failure_without_substitutes_extinguishes",
                                    "C3_redistribution_reignites_same_dependency",
                                    "C5_observation_loss_extinguishes", "C7_communication_loss_extinguishes_B"))
    altdep = ALT["contrasts"]["dependence (shared, live)"]
    basedep = A9["contrasts"]["dependence LS: B with A vs without A"]
    same_dir = all(altdep[m]["status"] == "DETECTED" and (altdep[m]["mean"] > 0) == (basedep[m]["mean"] > 0)
                   for m in ("completed", "pairs", "latency_mean") if basedep[m]["status"] == "DETECTED")
    c5 = ((va["H_A1_resource_mediation"] or bool(va["H_A3_residual_dependence"]))
          and all(x["holds"] for x in va["identity_checks"]) and not va["noise_flagged"] and same_dir)
    leva = all(v["fingerprints_identical"] == v["runs"] and v["verdicts_identical"] for v in LEVA["experiments"].values())
    b1 = bool(IND and IND["summary"]["B1_all_agree"])
    persists = [w for w, cs in W9["contrasts"].items()
                if any(cs["dependence (shared, live)"][m]["status"] == "DETECTED" for m in ("completed", "pairs",
                                                                                           "latency_mean"))]
    others = [w for w in W9["contrasts"] if w not in persists]
    m4 = M4["verdicts"]["M4_heterogeneity"] == "DEMONSTRATED"
    gains = all(M4["means"][f"solo_{s}/{s}"]["true_gain"] != 0 for s in "ABC")
    return [
        ("1. Systems select and execute every experiment without per-action human selection", True,
         "by construction: every experiment_selected event is produced by a system's decision rule; the harness only "
         "applies interventions declared in the frozen configuration"),
        ("2. Consequential results (M4 DEMONSTRATED; non-zero true gain for each system)", m4 and gains,
         f"M4 {M4['verdicts']['M4_heterogeneity']}; mean true gain A {M4['means']['solo_A/A']['true_gain']:.1f}, "
         f"B {M4['means']['solo_B/B']['true_gain']:.1f}, C {M4['means']['solo_C/C']['true_gain']:.1f}"),
        ("3. Later observation or conditions change (M5-A stands; D1, or revision changes reachability on held-out "
         "worlds)", c3, f"M5-A {M5['verdicts']['M5A_observation_revision']}; held-out reachable experiments "
                        f"{held_paths['status']} ({pct(held_paths['relative'])})"),
        ("4. Identifiable changes in future accessibility (≥ 2 of C1, C3, C5, C7)", c4n >= 2, f"{c4n} of 4 hold"),
        ("5. A cross-system pathway survives matched controls (H-A1 or H-A3; identity checks; noise; same direction "
         "under the alternative arrangement)", c5,
         f"H-A1 {va['H_A1_resource_mediation']}; identity checks "
         f"{all(x['holds'] for x in va['identity_checks'])}; noise flagged {va['noise_flagged'] or 'none'}; "
         f"alternative arrangement same direction {same_dir}"),
        ("6. Reproducible (Level A holds and independent check B1 agrees on every re-run seed)", leva and b1,
         f"Level A {leva}; B1 recount agrees on every re-run seed: {b1}" + (
             "" if b1 or not IND else f" (disagreements: {IND['summary']['B1_disagreements']})")),
        ("7. Configuration dependence (a laboratory where the pathway persists and ones where it does not)",
         bool(persists) and bool(others), f"persists: {', '.join(persists)}; not detected: {', '.join(others) or '—'}"),
    ]


# ====================================================================================================== Part IX
def part9(D: Doc) -> None:
    D.page()
    D.h("Part IX — Autonomous scientific operations and Xenoscience", 1)
    D.h("25. Levels", 2)
    D.p("Level 1 is an executable real-time 3D scientific simulation driven by an authoritative runtime with verified "
        "replay. Level 2 is demonstrated heterogeneous autonomous scientific operations that consequentially change "
        "later experimental possibilities, under the criteria frozen in LAB_PROTOCOL_M9.md §9 (the M4–M7 criterion, "
        "which requires T7, remains unmet and is not re-scored). Level 3 is strong Xenoscience.")
    D.p("Level 1 is reached: recorded runs replay with full agreement, live runs stream with complete ordered events, "
        "and the renderer draws recorded values only.")
    rows = [["condition (frozen §9)", "met", "evidence"]]
    res = level2()
    for name, ok, ev in res:
        rows.append([name, "yes" if ok else "NO", ev])
    D.table(rows, size=7)
    met = sum(ok for _, ok, _ in res)
    if met == len(res):
        D.p("Every condition holds: Level 2 is reached under the frozen criteria.")
    else:
        missing = [n.split(".")[0] for n, ok, _ in res if not ok]
        which = f"condition {missing[0]} does not" if len(missing) == 1 else f"conditions {', '.join(missing)} do not"
        D.p(f"{met} of {len(res)} conditions hold; {which}. Under the frozen criteria "
            "Level 2 is therefore not established. Several consequential autonomous operations are demonstrated — "
            "systems select and execute their own experiments, their interventions are consequential, a revision "
            "changes later reachability on held-out worlds, the loss and restoration of identified operations change "
            "what can later be done, and a material pathway between systems survives matched controls and another "
            "physical arrangement — so the appropriate summary is: Level 2 partially demonstrated, not achieved. The "
            "unmet condition is not reinterpreted.")
    D.h("26. Strong Xenoscience", 2)
    D.table([["condition (jointly necessary)", "status"],
             ["human-energy independence", "not satisfied: the simulation runs on mains-powered hardware"],
             ["human-readability independence", "not assessed: runs execute without human-readable output, but nothing "
                                                "tests independence from human-readable form"],
             ["material and organisational self-reproduction of scientific inquiry", "not satisfied: repair restores a "
              "modelled actuator from a finite counter; nothing reproduces material or organisation"],
             ["autonomous consequential revision of scientific conditions", "not shown: revision rules are fixed "
              "programs; relocation changes later reachability, but no revision improved effectiveness, and no "
              "generated variable was consequential"]])
    D.p("A software simulation cannot by itself satisfy these conditions, and no claim to Level 3 is made.")


# ====================================================================================================== Part X
def part10(D: Doc) -> None:
    D.page()
    D.h("Part X — Conclusion", 1)
    D.h("What the research demonstrates (in simulation)", 2)
    D.bullets([
        "Cross-system dependence in this laboratory travels through shared physical resources. Separating resources "
        "removes it; separating communication does not; an operation that does only physical work, with no runtime "
        "effect, reproduces it; with every pathway cut the runs are bit-identical to runs without the other system.",
        "Two physical sub-pathways act in opposite directions on different measures: shared gantries (and their wear) "
        "delay transfers; competition for material removes experiments, and removing that competition makes the other "
        "system busier on the shared gantry.",
        "Apparatus failure and operational extinction are distinct: failures with repair and natural failures did not "
        "extinguish operation; a failure without a usable substitute did.",
        "Substitute paths can be physically available without being accessible to the system: during the outage none "
        "of the experiments the system could detect was executable, and it spent its budget on refused requests.",
        "Re-ignition can restore the earlier dependency or generate a new one; sensor relocation shifts it toward new "
        "dependencies.",
        "Revising observation changes what can be observed and what can subsequently be done without a detectable "
        "change in effectiveness.",
        "These results reproduce exactly from frozen code, and the main dependence persists across several "
        "operationally different laboratories and another physical integration arrangement."])
    D.h("What it fails to demonstrate", 2)
    D.bullets([
        "That communication through the runtime carries cross-system dependence (M7 T7; M9-A).",
        "That any revision improves the effectiveness of interventions (M5, M9-D).",
        "That generated variables are consequential, or that the adoption criterion beats chance (M5, M9-E).",
        "That contextual historical reinsertion creates non-redundant differences beyond ordinary, shuffled, delayed "
        "or wrong-context memory (M6, M9-F).",
        "Several extinction criteria (C3, C4, C4b, C6, C7, C8, C9) and M7's T3 and T6.",
        "A diversity of scientific decision procedures: heterogeneity here is configuration-dependent.",
        "Level 2 under its frozen criteria; Level 3."])
    D.h("What remains outside its scope", 2)
    D.bullets([
        "Any physical laboratory: the physics is a rigid-body simulation with declared approximations, never validated "
        "against apparatus.",
        "Generality beyond one runtime, one world generator and one laboratory geometry.",
        "The philosophical works named in Part I, whose arguments were not consulted; the distinctions implemented here "
        "are operational versions stated in this text, and their implementation is not a philosophical discovery.",
        "A universal boundary between science and non-science: the record distinguishes operational cessation, "
        "evidential loss and persisting effects inside one simulation, and derives no boundary from them."])


# ====================================================================================================== appendices
SOURCES = ["backend/xzr/lab/science.py", "backend/xzr/lab/physics.py", "backend/xzr/lab/record.py",
           "backend/xzr/lab/replay.py", "backend/xzr/lab/causal.py", "backend/xzr/lab/m9.py", "backend/xzr/lab/labexp.py",
           "backend/xzr/lab/live.py", "backend/xzr/lab/apparatus.py", "backend/xzr/hpo/stats.py",
           "backend/scripts/run_m9.py", "backend/scripts/m9_independent.py", "backend/scripts/m9_latency_sensitivity.py",
           "backend/scripts/m9_substitutes.py", "backend/scripts/m9_figures.py", "backend/scripts/build_m9_manuscript.py"]


def negative_register() -> list[list[str]]:
    rows = [["experiment", "test", "result"]]
    rows += [["M5", "M5-B variable generation", M5["verdicts"]["M5B_variable_generation"]],
             ["M6", "H2 > H1 (contextual memory)", M6["verdicts"]["primary_H2_vs_H1"]],
             ["M7", "T3 extinction (≥ 6/24)", f"{M7['verdicts']['T3_extinction']['A_blocked_by_isolation_seeds']}/24"],
             ["M7", "T6 cross-system history", "not met"], ["M7", "T7 counterfactual removal", "not met"],
             ["M9-A", "H-A2 communication mediation", str(A9["verdicts"]["H_A2_communication_mediation"])],
             ["M9-A", "H-A3 residual dependence", "not detected"]]
    for k, v in C9["verdicts"].items():
        if v is False:
            rows.append(["M9-C", k, "not met"])
    for name, doc in (("M9-D", D9), ("M9-E", E9), ("M9-F", F9)):
        for k, v in doc["verdicts"].items():
            if v is False:
                rows.append([name, k, "not met"])
    rows.append(["M9 verification", "B1 latency recount", "measurement-definition defect (Part IV)"])
    return rows


def appendices(D: Doc) -> None:
    D.page()
    D.h("Appendix A — Frozen protocols", 1)
    for p in ("docs/LAB_PROTOCOL.md", "docs/LAB_PROTOCOL_M9.md"):
        f = ROOT / p
        D.h(f"{p} (SHA-256 {sha(f)})", 2)
        D.code(f.read_text(), 7)
    D.page()
    D.h("Appendix B — Negative-results register", 1)
    D.table(negative_register(), size=7)
    D.page()
    D.h("Appendix C — Reproduction", 1)
    D.code("""git clone <repository> && cd xeno-ziran-runtime && git checkout lab-m9
python3.12 -m venv .venv && .venv/bin/pip install -e "backend[dev,physics]"

# M4-M7 (frozen protocol docs/LAB_PROTOCOL.md); results are never overwritten: write elsewhere
cd backend && ../.venv/bin/python -c "from pathlib import Path; from xzr.lab import labexp as L; \\
  print(L.write('m7', L.run_experiment('m7', 7), Path('../xzr-results/labx-rerun')))"

# M9 confirmatory experiments (frozen protocol docs/LAB_PROTOCOL_M9.md; refuses to run if the protocol differs)
cd backend && PYTHONPATH=. ../.venv/bin/python scripts/run_m9.py 7

# verification and exploratory analyses
PYTHONPATH=. ../.venv/bin/python scripts/m9_independent.py experiments/results/lab9/m9ab.json out.json 6 \\
  experiments/results/lab9/m9c.json
PYTHONPATH=. ../.venv/bin/python scripts/m9_latency_sensitivity.py experiments/results/lab9/m9ab.json out.json 7
PYTHONPATH=. ../.venv/bin/python scripts/m9_substitutes.py experiments/results/lab9/m9c.json out.json 7

# replay a published record
PYTHONPATH=. ../.venv/bin/python -m xzr lab replay experiments/results/lab/m9-separated-resources-7000.json""", 7.5)
    D.p("Reproducibility condition: same machine class and software versions (Python 3.12.13, numpy 2.5.3, scipy 1.18.1, "
        "MuJoCo 3.14.0; Apple M1). Across platforms the runtime's address hierarchy can differ and bit agreement is not "
        "expected.")
    D.h("Result files (SHA-256)", 2)
    D.table([["file", "SHA-256"]] + [[str(p.relative_to(ROOT)), sha(p)] for p in
                                     sorted(list(L9.glob("*.json")) + list(LX.glob("m*.json")))], size=6)
    D.page()
    D.h("Appendix D — References", 1)
    D.bullets([
        "Todorov, E., Erez, T., Tassa, Y. (2012). MuJoCo: A physics engine for model-based control. IEEE/RSJ "
        "International Conference on Intelligent Robots and Systems, 5026–5033.",
        "Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics "
        "6(2), 65–70.",
        "Efron, B. (1979). Bootstrap methods: another look at the jackknife. The Annals of Statistics 7(1), 1–26.",
        "Good, P. (2005). Permutation, Parametric and Bootstrap Tests of Hypotheses. 3rd ed. Springer.",
        "three.js (JavaScript 3D library), version 0.169.0. https://threejs.org.",
        "XENO ZIRAN SIMULATOR runtime, version 0.2.0, MIT licence (CITATION.cff in the repository).",
        "Project documentation used as sources: README.md, docs/THEORY.md, docs/HPO.md, docs/LAB.md, docs/LIMITATIONS.md, "
        "docs/REPRODUCIBILITY.md; ziran-xeno-simulator/docs/claims.md and DESIGN.md.",
        "Named but not consulted (texts unavailable to this record): Operational Shape Realism; Scientific Operational "
        "Shapes; Critical Points of Science and Nonscience; Ziran System; Xenoscience; Philosophical AI."])
    D.page()
    D.h("Appendix E — Executable source code", 1)
    D.p("Complete listings of the laboratory modules and M9 scripts as committed. Executable files remain in the "
        "repository; these listings are documentary.", italic=True)
    for p in SOURCES:
        f = ROOT / p
        D.h(f"{p} (SHA-256 {sha(f)[:16]}…)", 2)
        D.code(f.read_text(), 6)
    D.page()
    D.h("Appendix F — Experimental configurations", 1)
    from xzr.lab import m9  # noqa: PLC0415
    D.code(json.dumps({"base": m9.BASE, "ranges": m9.RANGES, "experiments": m9.EXPERIMENTS}, indent=1), 6)
    D.page()
    D.h("Appendix G — Original machine-readable results", 1)
    D.p("Each result file is reproduced in full (compact JSON). Order: M9 confirmatory results, M9 verification and "
        "exploratory analyses, M4–M7 results.", italic=True)
    files = sorted(L9.glob("*.json")) + sorted((L9 / "verification").glob("*.json")) + sorted(EXP.glob("*.json")) + \
        [LX / f"m{i}.json" for i in (4, 5, 6, 7)] + [LX / "verification" / "level_a_reproduction.json"]
    for f in files:
        if not f.exists():
            continue
        D.h(f"{f.relative_to(ROOT)} (SHA-256 {sha(f)[:16]}…)", 2)
        D.code(json.dumps(json.loads(f.read_text()), separators=(",", ":")), 5)


def main() -> None:
    figs, out = Path(sys.argv[1]), Path(sys.argv[2])
    sys.path.insert(0, str(ROOT / "backend"))
    D = Doc()
    front(D)
    part1(D)
    part2(D)
    part3(D)
    part4(D, figs)
    part5(D, figs)
    part6(D, figs)
    part7(D, figs)
    part8(D, figs)
    part9(D)
    part10(D)
    appendices(D)
    D.save(out)
    print("written", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
