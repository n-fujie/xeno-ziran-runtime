"""Experiments EXP-R16-02, 04, 08 and 09, added once the fifteen governance principles of R16 section 7 and the stated aggregates of the R16 finite experiment were supplied. New ids; nothing earlier is re-labelled.

The other experiments of the R16 list are covered by the LAW series and are not repeated under a second id: EXP-R16-01 receipt first against evidence first = LAW-L1; EXP-R16-03 scope of an evidence revision = LAW-L3; EXP-R16-05 immutable measurements
and status events = LAW-A1 (with LAW-L3); EXP-R16-06 administrative closure and restoration = LAW-L5 and LAW-L6; EXP-R16-07 the equal-information Boolean model = LAW-L4 (own world) and EXP-R16-04 (the stated-aggregates world).

Everything is SYNTHETIC and says nothing about a real institution, law or person. The stated-aggregates world is an independent verification model built from the aggregates in the request; it is not the original world, and its match with the
stated numbers holds by construction: it is not a reproduction of the manuscript's experiment.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Any

import numpy as np

from . import lawexperiments as X
from . import lawledger as LG
from . import lawworld as W
from . import mheg as M

STATED = {"model_access": [32, 32, 32, 32, 40, 60], "sensor_access": [32, 32, 32, 32, 32, 42], "disagreements": {"EXEC_GATE": 8, "EXEC_LINKED": 18}}


def signature(lg: LG.Ledger, case: str) -> dict[str, Any]:
    """What a case holds, without the global numbers (receipt sequence, ids, ticks) that depend on how cases interleave."""
    s = lg.snapshot(case)
    return {"receipts": sorted((r["claim_id"] or "-", r["state"]) for r in s["receipts"]), "evidence": [(e["version"], e["scope"], e["valid"], e["e_state"]) for e in s["evidence"]], "proceedings": sorted((p["kind"], p["state"]) for p in s["proceedings"]),
            "measurements": [(m["mode"], m["model"], m["sensor"], m["mismatch"], tuple(h["status"] for h in m["status_history"])) for m in s["measurements"]], "closures": [(c["kind"], c["flag"]) for c in s["closures"]],
            "restoration": [(x["stage"], x["present"], x["n"]) for x in s["restoration"]["stages"]], "condition": s["world"]["condition"], "effective": s["effective"]}


def lifecycle(lg: LG.Ledger, case: str, k: int, rng_seed: int) -> None:
    """One case from the first submission to a closure (resend, a conflicting body, malformed input, a revision of each scope in turn)."""
    rng = np.random.default_rng(rng_seed)
    bits = int(rng.integers(0, 256)) & W.pack(a=1, b=1, c=1, h=1)
    lg.create_case(case, "G3", bits)
    c1 = X.claim(k * 10 + 1)
    lg.receive(case, c1)
    lg.receive(case, c1)
    lg.receive(case, {**c1, "note": "another body"})
    lg.receive(case, b"{broken")
    lg.receive(case, {**X.claim(k * 10 + 2), "evidence": {"tier": 9}})
    for p in lg.proceedings(case, open_only=True):
        lg.complete_review(p["id"], "reviewer1", "reviewed")
    pl = lg.plan(case, "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(pl, "approver1")
    lg.execute(pl, "executor1")
    lg.observe(case, "ACCESS_ONLY", "mo1")
    lg.register_evidence(case, "G3", X.EV_OK, scope=("ACCESS", "METADATA", "UNKNOWN")[k % 3])
    lg.observe(case, "EXPANDED", "mo2")
    for p in lg.proceedings(case, open_only=True):
        if p["state"] == "OPEN":
            lg.complete_review(p["id"], "reviewer1", "reviewed")
    for p in lg.proceedings(case, open_only=True):
        lg.close_review(case, p["id"], "officer1")


# ------------------------------------------------------------------------------------------------ EXP-R16-02
def run_02(seed: int) -> dict:
    """Four cases at once on one SQLite file (four connections, one thread each) against the same four cases one after another; the database reopened; every submission sent again; contamination between cases."""
    cases = [f"case-{k}" for k in range(4)]
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "conc.sqlite")
        conns = [X.ledger(path=path) for _ in range(4)]
        errs: list[str] = []

        def work(k: int) -> None:
            try:
                lifecycle(conns[k], cases[k], k, seed * 10 + k)
            except Exception as e:  # noqa: BLE001
                errs.append(repr(e))

        ts = [threading.Thread(target=work, args=(k,)) for k in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        for conn in conns:
            conn.close()
        again = X.ledger(path=path)
        conc = {cs: signature(again, cs) for cs in cases}
        n_before = {t: again.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("receipts", "evidence_events", "measurements", "closures")}
        for k, cs in enumerate(cases):  # every submission sent again: a resend changes nothing
            again.receive(cs, X.claim(k * 10 + 1))
        n_after = {t: again.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in n_before}
        contamination = sum(again.db.execute("SELECT COUNT(*) FROM measurements m JOIN evidence_events e ON e.id = m.evidence_event_id WHERE m.case_id != e.case_id").fetchone()[0] for _ in [0])
        again.close()
    seq_lg = X.ledger()
    for k, cs in enumerate(cases):
        lifecycle(seq_lg, cs, k, seed * 10 + k)
    seq = {cs: signature(seq_lg, cs) for cs in cases}
    return {"seed": seed, "errors": len(errs), "cases_equal_to_sequential": sum(conc[cs] == seq[cs] for cs in cases), "cases": len(cases), "resend_changes": {t: n_after[t] - n_before[t] for t in n_before}, "cross_case_contamination": int(contamination),
            "closures": sum(len(conc[cs]["closures"]) for cs in cases), "closures_keep_a_flag": all(f is not None for cs in cases for _, f in conc[cs]["closures"])}


# ------------------------------------------------------------------------------------------------ EXP-R16-04
def run_04(seed: int) -> dict:
    """The independent verification model built from the stated aggregates: its enumeration against the stated numbers (a match by construction, not a reproduction), that the sensor's extra access is contained in the model's, which
    disagreements EXPANDED explains, the equal-information Boolean comparator, and the ledger realising the world (96 pairs through SQLite)."""
    w = "r16_stated_aggregates"
    e = W.enumerate_world(w)
    pc = e["per_condition"]
    model = [pc[c]["model_access"] for c in W.CONDITIONS]
    sensor = [pc[c]["sensor_access"] for c in W.CONDITIONS]
    nested = all((not W.sensor_access(s, c, w)) or W.model_access(s, c, w) or W.baseline_access(s) for s in range(256) for c in W.CONDITIONS)
    sensor_extra_in_model = all(W.model_access(s, c, w) for s in range(256) for c in W.CONDITIONS if W.sensor_access(s, c, w))
    rng = np.random.default_rng(91_000 + seed)
    agree = 0
    for i in range(96):
        s, cond = int(rng.integers(0, 256)), W.CONDITIONS[i % 6]
        lg = X.ledger(world=w)
        lg.create_case("c", "G3", s & W.pack(a=1, b=1, c=1, h=1))
        X._drive(lg, cond)  # noqa: SLF001
        wd = lg.world("c")
        o = lg.observe("c", "EXPANDED", "m")
        d = W.observe(wd["bits"], wd["condition"], "EXPANDED", w)
        agree += int(o["model"] == d["model"] and o["sensor"] == d["sensor"] and wd["condition"] == cond)
    return {"seed": seed, "enumeration": e, "model_access": model, "sensor_access": sensor, "disagreements": {c: pc[c]["disagreements"] for c in W.CONDITIONS}, "nested": bool(nested), "sensor_access_contained_in_model": bool(sensor_extra_in_model),
            "ledger_realisation": {"checked": 96, "agree": agree}, "unexplained_by_q": {c: pc[c]["disagreements"] - pc[c]["cause_identified_expanded"] for c in ("EXEC_GATE", "EXEC_LINKED")}}


# ------------------------------------------------------------------------------------------------ EXP-R16-08
def run_08(seed: int) -> dict:
    """The comparators of LAW-L7 plus the evidence-scoped revision model R, on both worlds."""
    return {"seed": seed, "worlds": {w: X.run_l7(seed, w, True)["rows"] for w in W.WORLDS}}


# ------------------------------------------------------------------------------------------------ EXP-R16-09
def run_09(seed: int) -> dict:
    """The correspondence between the twelve duties, the fifteen guarantees and the fifteen R16 governance principles by protected function, never by number."""
    cw = M.PRINCIPLE_CROSSWALK
    items = {it["id"]: it for it in M.GOVERNANCE_PRINCIPLES["items"]}
    ordinal_best = {p: v["best_guarantee"] == v["ordinal_counterpart"] for p, v in cw.items()}
    identical_titles = [p for p, v in cw.items() if v["ordinal_title_identical"]]
    exact = [p for p, v in cw.items() if v["ordinal_similarity"] == 1.0]
    differing = {p: cw[p]["differences_from_ordinal"] for p in cw if cw[p]["ordinal_similarity"] < 1.0}
    no_duty = [p for p, v in cw.items() if not v["close_duties"]]
    duty_cover = {m["id"]: [p for p, v in cw.items() if m["id"] in v["close_duties"]] for m in M.DUTIES}
    n_g_close = {p: len(v["close_guarantees"]) for p, v in cw.items()}
    return {"seed": seed, "ordinal_counterpart_is_best_match": ordinal_best, "titles_identical_to_the_ordinal_guarantee": identical_titles, "functionally_identical": exact, "differs": differing, "principles_without_a_duty": no_duty,
            "duties_covered_by_principles": duty_cover, "close_guarantees_per_principle": n_g_close, "close_guarantees_are_the_ordinal_only": all(v["close_guarantees"] == [v["ordinal_counterpart"]] for v in cw.values()),
            "august_version_kept": [v["id"] for v in M.GOVERNANCE_PRINCIPLES["versions"]], "verification": {p: items[p]["verification"] for p in items}, "method": M.GOVERNANCE_PRINCIPLES["crosswalk_method"]}


RUN: dict[str, Any] = {"EXP-R16-02": run_02, "EXP-R16-04": run_04, "EXP-R16-08": run_08, "EXP-R16-09": run_09}
