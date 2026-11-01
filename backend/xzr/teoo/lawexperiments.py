"""Experiments on the AI-law ledger (LAW-L1 .. LAW-L7 and the ablation LAW-A1). New experiment ids: nothing earlier is re-labelled, and the historical R5-R16 results of the manuscripts are not registered here as TEOO results.

Each ``run_xx(seed)`` is a deterministic function of its seed and returns one unit. Evidence classes: LAW-L1/L2/L5/L6 and A1 are Implementation Properties (about the specification and the code), LAW-L3/L4/L7 compare designs on synthetic scenarios
(Synthetic-world Results). Everything is SYNTHETIC; none of it says anything about a real institution, law or person, and a closure, a measurement or a match here is not a legal judgment or a restoration.

Comparators (LAW-L7): A a Boolean state machine (flags, no history); B conventional event sourcing (events and a fold, given the same information, scope included); C an equal-information causal model (the world's function, no history);
D = C with a fixed ACCESS_ONLY policy; E = C with an adaptive policy; F the ledger with the adaptive policy. Each gets the same inputs and the same scenario; none is handicapped to make another look better.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Any

import numpy as np

from . import lawledger as LG
from . import lawworld as W

EV_OK = {"tier": 1, "exists": True, "usable": True, "score_conditioned": False}
ROLES = (("planner1", "planner"), ("approver1", "approver"), ("executor1", "executor"), ("reviewer1", "reviewer"), ("officer1", "officer"))


def ledger(features: dict[str, bool] | None = None, path: str = ":memory:") -> LG.Ledger:
    lg = LG.Ledger(path, features)
    for a, r in ROLES:
        lg.set_role(a, r)
    return lg


def claim(i: int, guarantee: str = "G3", **kw: Any) -> dict[str, Any]:
    return {"claim_id": f"claim-{i}", "guarantee": guarantee, "evidence": dict(EV_OK), **kw}


# ------------------------------------------------------------------------------------------------ LAW-L1: receipt non-erasure
def _stream(rng: np.random.Generator, n: int) -> list[tuple[str, Any]]:
    """A stream of submissions to one case: valid claims, claims whose evidence container is corrupt, resends, a conflicting body for an used claim id, malformed input, and one oversize input."""
    items: list[tuple[str, Any]] = []
    sent: list[int] = []
    for i in range(n):
        u = rng.uniform()
        if u < 0.55:
            items.append(("valid", claim(i)))
            sent.append(i)
        elif u < 0.72:
            items.append(("corrupt_evidence", {**claim(i), "evidence": {"tier": 9, "exists": "maybe"}}))
        elif u < 0.84 and sent:
            j = sent[int(rng.integers(0, len(sent)))]
            items.append(("resend", claim(j)))
        elif u < 0.92 and sent:
            j = sent[int(rng.integers(0, len(sent)))]
            items.append(("conflict", {**claim(j), "note": "a different body under the same claim id"}))
        elif u < 0.99:
            items.append(("malformed", b"{not json" + bytes(int(rng.integers(0, 9)) for _ in range(3))))
        else:
            items.append(("oversize", b"x" * (LG.MAX_PAYLOAD_BYTES + 1)))
    return items


def run_l1(seed: int) -> dict:
    """Receipt-first against evidence-first (the earlier behaviour: validate the evidence container first and drop a submission whose container is bad) against the in-memory R10 batch (valid submissions beyond 64 are UNACKNOWLEDGED);
    then 65 submissions to one case, four connections submitting 24 at once, a reopened database, resends and conflicts."""
    rng = np.random.default_rng(81_000 + seed)
    items = _stream(rng, 80)
    lg = ledger()
    kept = {"valid_with_corrupt_evidence": 0, "duplicates_collapsed": 0, "conflicts_quarantined": 0, "malformed_quarantined": 0, "oversize_refused": 0, "valid_receipts": 0}
    seen: set[str] = set()
    for kind, p in items:
        r = lg.receive("case", p)
        if kind == "valid" and r["received"] and not r["duplicate"]:
            kept["valid_receipts"] += 1
        if kind == "corrupt_evidence":
            kept["valid_with_corrupt_evidence"] += int(r["received"] and r["state"] in ("ACTIVE", "QUEUED") and r["evidence"] is not None and not r["evidence"]["valid"])
        kept["duplicates_collapsed"] += int(kind == "resend" and r["duplicate"])
        kept["conflicts_quarantined"] += int(kind == "conflict" and r["state"] == "QUARANTINED")
        kept["malformed_quarantined"] += int(kind == "malformed" and r["state"] == "QUARANTINED")
        kept["oversize_refused"] += int(kind == "oversize" and not r["received"])
        seen.add(r.get("claim_id") or "")
    n_valid_claims = len({p["claim_id"] for k, p in items if k in ("valid", "corrupt_evidence")})
    # the earlier behaviour: a submission whose evidence container is invalid is dropped before it is recorded
    evidence_first_erased = sum(1 for k, _ in items if k == "corrupt_evidence")
    receipt_first_erased = sum(1 for k, p in items if k in ("valid", "corrupt_evidence") and lg.db.execute("SELECT 1 FROM receipts WHERE case_id='case' AND claim_id = ?", (p["claim_id"],)).fetchone() is None)
    # R10 in memory: 65 valid submissions and more
    big = [claim(i) for i in range(70)]
    r10 = LG.r10_batch(big)
    states = {s: sum(x["state"] == s for x in r10) for s in ("ACTIVE", "QUEUED", "UNACKNOWLEDGED", "QUARANTINED")}
    lg65 = ledger()
    for i in range(65):
        lg65.receive("c65", claim(i))
    c65 = lg65.counts("c65")
    # four connections, 24 submissions at once, on one file; then reopen
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "intake.sqlite")
        conns = [ledger(path=path) for _ in range(4)]
        errs: list[str] = []

        def work(k: int) -> None:
            try:
                for i in range(6):
                    conns[k].receive("cc", claim(k * 100 + i))
            except Exception as e:  # noqa: BLE001
                errs.append(repr(e))

        ts = [threading.Thread(target=work, args=(k,)) for k in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        for c in conns:
            c.close()
        again = ledger(path=path)
        rc = again.receipts("cc")
        persisted = {"receipts": len(rc), "distinct_sequences": len({r["receipt_seq"] for r in rc}), "errors": len(errs), "active": again.counts("cc")["ACTIVE"], "queued": again.counts("cc")["QUEUED"]}
        again.close()
    # different cases may use the same claim id without sharing a sequence
    lg2 = ledger()
    a, b = lg2.receive("A", claim(1)), lg2.receive("B", claim(1))
    # an invalid submission first does not refuse the valid one that follows
    lg3 = ledger()
    lg3.receive("D", b"{broken")
    after_invalid = lg3.receive("D", claim(7))["state"]
    expected = {k: sum(1 for kk, _ in items if kk == name) for k, name in (("valid_with_corrupt_evidence", "corrupt_evidence"), ("duplicates_collapsed", "resend"), ("conflicts_quarantined", "conflict"), ("malformed_quarantined", "malformed"), ("oversize_refused", "oversize"))}
    return {"seed": seed, "expected": expected, "kept": kept, "receipt_first_erased": receipt_first_erased, "evidence_first_erased": evidence_first_erased, "n_corrupt": evidence_first_erased, "n_claims": n_valid_claims, "r10_states": states,
            "persistent_65": {"ACTIVE": c65["ACTIVE"], "QUEUED": c65["QUEUED"], "UNACKNOWLEDGED": 0, "total": c65["ACTIVE"] + c65["QUEUED"]}, "persisted": persisted, "same_claim_other_case": a["state"] == b["state"] and a["receipt_seq"] != b["receipt_seq"],
            "after_invalid_first": after_invalid, "refusals": lg.counts("case")["refused"]}


# ------------------------------------------------------------------------------------------------ LAW-L2: concurrent proceedings and the R8 / R9 case
def run_l2(seed: int) -> dict:
    """(a) The R8 problem: G1 SECURED, then an improper exception for G1. The ledger keeps E, records A = REJECTED and opens the exception proceeding; the overwriting variant (one state string, the earlier behaviour) turns E into
    INDETERMINATE. (b) Several proceedings of different kinds opened in random order: the ledger keeps all of them; the single-state variant keeps one."""
    rng = np.random.default_rng(82_000 + seed)
    res: dict[str, Any] = {"seed": seed}
    lg = ledger()
    lg.create_case("c", "G1", 7)
    lg.receive("c", claim(0, "G1"))
    before = lg.effective_state("c", "G1")
    r = lg.receive("c", {**claim(1, "G1"), "exception": {"reason": "improper request that G1 does not apply"}})
    after = lg.effective_state("c", "G1")
    res["r9"] = {"E_before": before["E"], "E_after": after["E"], "A": after["A"], "W": after["W"], "evidence_unchanged": r["exception"]["evidence_unchanged"]["e_state"] == before["E"], "exception_accepted": lg.decide_exception("c", "G1", True, "reviewer1")["ok"]}
    res["r8_overwrite_variant_E_after"] = "INDETERMINATE"  # the earlier single-state behaviour, stated as the specification of the comparator: an exception request replaces the evidence state
    kinds = ["EXCEPTION_REVIEW_REQUIRED", "EVIDENCE_REVIEW", "REASSESS_OUTCOME", "HUMAN_REVIEW", "SUSPENSION_REVIEW"]
    k = int(rng.integers(3, 6))
    order = list(rng.permutation(kinds)[:k])
    out = {}
    for name, feat in (("ledger", {}), ("single_state", {"concurrent": False})):
        lg = ledger(feat)
        lg.create_case("c", "G3", 7)
        for kind in order:
            lg.open_proceeding("c", "G3", str(kind))
        out[name] = len(lg.proceedings("c", open_only=True))
    res["opened"] = k
    res["open_after"] = out
    # two independent reviews of different kinds complete without erasing the other
    lg = ledger()
    lg.create_case("c", "G3", 7)
    a = lg.open_proceeding("c", "G3", "EVIDENCE_REVIEW")
    lg.open_proceeding("c", "G3", "HUMAN_REVIEW")
    lg.complete_review(a["id"], "reviewer1", "done")
    res["independent_completion"] = [p["state"] for p in lg.proceedings("c")] == ["REVIEWED", "OPEN"]
    return res


# ------------------------------------------------------------------------------------------------ the scenario shared by LAW-L3, L5, L6, L7 and A1
def scenario(seed: int, k: int) -> dict[str, Any]:
    rng = np.random.default_rng(83_000 + seed * 100 + k)
    s2 = ("ACCESS", "METADATA", "UNKNOWN")[int(rng.integers(0, 3))]
    return {"bits": int(rng.integers(0, 256)), "s1": ("ACCESS", "METADATA", "UNKNOWN")[int(rng.integers(0, 3))], "s2": s2, "mode1": W.MODES[int(rng.integers(0, 2))], "declare": bool(rng.integers(0, 2)),
            "rev_before_exec": bool(rng.integers(0, 2)), "affects2": s2 == "ACCESS" or (s2 == "UNKNOWN" and bool(rng.uniform() < 0.5)), "has_rev2": bool(rng.uniform() < 0.85), "open_review": bool(rng.uniform() < 0.5)}


def run_ledger(sc: dict[str, Any], features: dict[str, bool] | None = None, policy: str = "own") -> dict[str, Any]:
    """Drive the ledger through one scenario and read the answers off it. Policies: ``own`` (the first observation in the scenario's mode, EXPANDED when it has gone stale), ``fixed`` (one observation, never repeated),
    ``adaptive_equal`` (ACCESS_ONLY first, EXPANDED after a disagreement, EXPANDED again when stale: the policy that the comparators of LAW-L7 share)."""
    lg = ledger(features)
    lg.create_case("c", "G3", sc["bits"] & W.pack(a=1, b=1, c=1, h=1))
    lg.receive("c", {**claim(1), "scope": sc["s1"]})
    if sc.get("open_review"):  # a review of another kind is open and completed before the plan: it stays a proceeding of the case
        pr = lg.open_proceeding("c", "G3", "HUMAN_REVIEW")
        lg.complete_review(pr["id"], "reviewer1", "reviewed")
    if sc["declare"]:
        lg.declare("c", "executor1", "correction declared")
    p1 = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(p1, "approver1")
    plan_id, stale_plan_seen = p1, False
    if sc["rev_before_exec"] and sc["has_rev2"]:
        lg.register_evidence("c", "G3", EV_OK, scope=sc["s2"], source="revision")
        stale_plan_seen = lg.plan_status(p1) == "STALE_EVIDENCE"
        plan_id = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
        lg.approve(plan_id, "approver1")
        if features and not features.get("versions", True):
            plan_id = p1  # without versions the stale plan is just executed
    ex = lg.execute(plan_id, "executor1")
    ex_stale = False
    if ex["ok"]:
        pv = lg.db.execute("SELECT evidence_version FROM plans WHERE id = ?", (plan_id,)).fetchone()[0]
        ex_stale = pv < (lg.evidence_state("c", "G3") or {"version": 0})["version"]
    m1 = lg.observe("c", "ACCESS_ONLY" if policy == "adaptive_equal" else sc["mode1"], "mo1")
    t1 = lg.now()
    last = m1
    if policy == "adaptive_equal" and m1["mismatch"]:
        last = lg.observe("c", "EXPANDED", "mo1x")
    if (not sc["rev_before_exec"]) and sc["has_rev2"]:
        lg.register_evidence("c", "G3", EV_OK, scope=sc["s2"], source="revision")
    ms = {m["id"]: m for m in lg.measurements("c")}
    status_m1, status_last = ms[m1["measurement_id"]]["status"], ms[last["measurement_id"]]["status"]
    reobserved = None
    if policy != "fixed" and status_last != "CURRENT":
        reobserved = lg.observe("c", "EXPANDED", "mo2")
    cur_m = [m for m in lg.measurements("c") if m["status"] == "CURRENT"]
    for p in lg.proceedings("c", open_only=True):
        if p["state"] == "OPEN":
            lg.complete_review(p["id"], "reviewer1", "reviewed")
    closes = [lg.close_review("c", p["id"], "officer1") for p in lg.proceedings("c", open_only=True)]
    ok_closes = [c for c in closes if c["ok"]]
    snap = lg.snapshot("c")
    return {"M1": m1, "last": last, "status_m1": status_m1, "status_m1_at_creation": lg.status_at(m1["measurement_id"], t1), "reobserved": reobserved, "n_current": len(cur_m), "open_proceedings_before_close": len(closes),
            "closes": [{k: c.get(k) for k in ("ok", "kind", "flag", "missing")} for c in closes], "closure_kinds": sorted({c["kind"] for c in ok_closes}), "unresolved_flag": any(c["flag"] == "UNRESOLVED_CONFLICT" for c in ok_closes),
            "stale_plan_seen": stale_plan_seen, "executed_on_stale_evidence": ex_stale, "restoration": snap["restoration"], "condition": snap["world"]["condition"], "proceeding_kinds": [p["kind"] for p in snap["proceedings"]], "ledger": lg}


def _public(r: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in r.items() if k != "ledger"}


# ------------------------------------------------------------------------------------------------ LAW-L3: evidence revision and the scope of its effect
def run_l3(seed: int) -> dict:
    """The effect of a later evidence revision on an earlier observation, for scope ACCESS, METADATA and UNKNOWN. The ground truth of whether access is affected is set by the scenario (the experimenter's stipulation: the ledger does not
    find legal relevance by itself). Policies: scope-aware (the ledger), always invalidate, never invalidate."""
    rows = []
    for k in range(24):
        sc = scenario(seed, k)
        if not sc["has_rev2"] or sc["rev_before_exec"]:
            continue  # the observation must exist before the revision
        r = run_ledger(sc, policy="fixed")
        invalid = r["status_m1"] != "CURRENT"
        rows.append({"scope": sc["s2"], "affects": sc["affects2"], "ledger_invalid": invalid, "always_invalid": True, "never_invalid": False, "status": r["status_m1"],
                     "plan_stale_all_scopes": None})
    plan_stale = {}
    for scope in LG.SCOPES:  # the conservative rule for unexecuted plans holds for every scope
        lg = ledger()
        lg.create_case("c", "G3", 7)
        lg.receive("c", claim(1))
        pid = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
        lg.register_evidence("c", "G3", EV_OK, scope=scope)
        plan_stale[scope] = lg.plan_status(pid) == "STALE_EVIDENCE"
    return {"seed": seed, "rows": rows, "plan_stale": plan_stale}


# ------------------------------------------------------------------------------------------------ LAW-L4: the finite world, and the ledger as its realisation
def run_l4(seed: int) -> dict:
    """The whole finite world (256 states x 6 conditions = 1,536 comparisons) with the model against the synthetic sensor, the cause seen or not seen by the observation mode, and the equal-information Boolean comparator; and a
    sample of 96 (state, condition) pairs driven through the ledger to check that it realises the world (the ledger's measurement equals the world's function)."""
    en = W.enumerate_world()
    rng = np.random.default_rng(84_000 + seed)
    agree = n = 0
    for i in range(96):
        s, cond = int(rng.integers(0, 256)), W.CONDITIONS[i % 6]
        lg = ledger()
        # exogenous bits a, b, c, h come from the state; d, e, f, g come from the history that reaches the condition
        lg.create_case("c", "G3", s & W.pack(a=1, b=1, c=1, h=1))
        _drive(lg, cond)
        w = lg.world("c")
        o = lg.observe("c", "EXPANDED", "m")
        direct = W.observe(w["bits"], w["condition"], "EXPANDED")
        agree += int(o["model"] == direct["model"] and o["sensor"] == direct["sensor"] and w["condition"] == cond)
        n += 1
    return {"seed": seed, "enumeration": en, "ledger_realisation": {"checked": n, "agree": agree}}


def _drive(lg: LG.Ledger, cond: str) -> None:
    if cond == "BASE":
        return
    lg.receive("c", claim(1))
    if cond == "RECEIPT_ONLY":
        return
    if cond == "DECLARATION_ONLY":
        lg.declare("c", "executor1", "declared")
        return
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    if cond == "PLAN_ONLY":
        return
    if cond == "EXEC_GATE":  # the unlinked path
        lg.f["transaction_linked"] = False
        lg.execute(p, "executor1")
        lg.f["transaction_linked"] = True
        return
    lg.approve(p, "approver1")
    lg.execute(p, "executor1")


# ------------------------------------------------------------------------------------------------ LAW-L5: administrative closure
def run_l5(seed: int) -> dict:
    """Closure after a disagreement and after a match. The ledger requires the evidence revision, a newer model observation, a current sensor comparison and an officer; it ends CLOSED_ADMIN_CONFLICT with UNRESOLVED_CONFLICT kept, or
    CLOSED_ADMIN_MODEL_MATCH with MODEL_MATCH_NOT_LEGALLY_VERIFIED kept; the variant with a single SUCCESS state hides the conflict. A closure is attempted too early (no observation, stale observation) and must be refused."""
    rows = []
    for k in range(24):
        sc = scenario(seed, k)
        a = run_ledger(sc)
        b = run_ledger(sc, {"closure_separation": False})
        kinds = a["closure_kinds"]
        cur = [m for m in a["ledger"].measurements("c") if m["status"] == "CURRENT"]
        final_conflict = bool(cur and cur[-1]["mismatch"])
        rows.append({"final_conflict": final_conflict, "closure_kinds": kinds, "unresolved_flag": a["unresolved_flag"], "success_variant_kinds": b["closure_kinds"], "success_variant_flag": b["unresolved_flag"],
                     "legal_determination": a["restoration"]["legal_determination_by_this_software"], "restoration_verified": a["restoration"]["material_restoration_verified"], "positive_law_verified": a["restoration"]["positive_law_verified"],
                     "conflict_hidden_by_success": bool(final_conflict and "CLOSED_SUCCESS" in b["closure_kinds"]), "any_closure": bool(kinds)})
    early = ledger()
    early.create_case("c", "G3", 7)
    early.receive("c", claim(1))
    p = early.proceedings("c")
    pid = p[0]["id"] if p else early.open_proceeding("c", "G3", "EVIDENCE_REVIEW")["id"]
    early.complete_review(pid, "reviewer1", "done")
    refused_no_obs = not early.close_review("c", pid, "officer1")["ok"]
    return {"seed": seed, "rows": rows, "refused_without_observation": refused_no_obs}


# ------------------------------------------------------------------------------------------------ LAW-L6: the restoration gap
def run_l6(seed: int) -> dict:
    """The six records (receipt, evidence finding, human review, proposed measure, downstream observation, material restoration) are independent: for each scenario, which are present, whether access changed in the synthetic world,
    and that a changed access, a closure or a model match never becomes material restoration or a legal determination. A comparator that collapses the chain into one SUCCESS is counted."""
    rows = []
    for k in range(24):
        sc = scenario(seed, k)
        r = run_ledger(sc)
        st = r["restoration"]
        present = [s["present"] for s in st["stages"]]
        collapsed_success = bool(st["access_changed_in_the_synthetic_world"] or st["administrative_closures"])
        rows.append({"present": present, "access_changed": st["access_changed_in_the_synthetic_world"], "closures": len(st["administrative_closures"]), "restoration_verified": st["material_restoration_verified"], "positive_law_verified": st["positive_law_verified"],
                     "determination_by_software": st["legal_determination_by_this_software"], "collapsed_success": collapsed_success, "relief_misclassified_by_collapse": bool(collapsed_success and not st["material_restoration_verified"])})
    return {"seed": seed, "rows": rows}


# ------------------------------------------------------------------------------------------------ comparators for LAW-L7
def _flow(sc: dict[str, Any], expand_on_mismatch: bool, reobserve_when_stale: bool) -> list[dict[str, Any]]:
    """The observations of the shared adaptive policy on the sequence receipt -> plan -> execute -> observe -> (revision): ACCESS_ONLY first; EXPANDED after a disagreement; EXPANDED again when the revision made the observation stale."""
    bits = _bits(sc)
    obs = [W.observe(bits, "EXEC_LINKED", "ACCESS_ONLY")]
    if expand_on_mismatch and obs[-1]["mismatch"]:
        obs.append(W.observe(bits, "EXEC_LINKED", "EXPANDED"))
    stale = sc["has_rev2"] and not sc["rev_before_exec"] and sc["s2"] in ("ACCESS", "UNKNOWN")
    if reobserve_when_stale and stale:
        obs.append(W.observe(bits, "EXEC_LINKED", "EXPANDED"))
    return obs


def _closable(sc: dict[str, Any]) -> bool:
    """The closure rule that every design that closes must implement: the last observation is newer than the last evidence revision. After a METADATA revision the earlier observation stays valid but is not newer, so no closure until it is repeated."""
    return not (sc["has_rev2"] and not sc["rev_before_exec"] and sc["s2"] == "METADATA")


def _answer(obs: list[dict[str, Any]], opens: int | None, history: bool, valid: bool | None, closable: bool = True) -> dict[str, Any]:
    fin = obs[-1]
    closure = None if (not opens or not closable) else ("CLOSED_ADMIN_CONFLICT" if fin["mismatch"] else "CLOSED_ADMIN_MODEL_MATCH")
    return {"access": fin["sensor"], "mismatch": fin["mismatch"], "cause_identified": fin["cause_identified"], "current_valid": valid, "history_answerable": history, "open_proceedings": opens, "closure": closure}


def comparator_a(sc: dict[str, Any]) -> dict[str, Any]:
    """A: a Boolean state machine, flags only and no history. It gets the same events and scope. A proceeding is one flag per kind (two flags), so a second disagreement does not add a proceeding."""
    obs = _flow(sc, True, True)
    flags = {"EVIDENCE_REVIEW": False, "REASSESS_OUTCOME": False}
    for o in obs:
        if o["mismatch"]:
            flags = {k: True for k in flags}
    return _answer(obs, sum(flags.values()), False, True, _closable(sc))


def comparator_b(sc: dict[str, Any]) -> dict[str, Any]:
    """B: conventional event sourcing with the same information: an event list, folded; it keeps history and a list of proceedings; its fold implements the same rules."""
    obs = _flow(sc, True, True)
    events = [("measure", o) for o in obs] + [("open", k) for o in obs if o["mismatch"] for k in ("EVIDENCE_REVIEW", "REASSESS_OUTCOME")]
    return _answer(obs, sum(1 for k, _ in events if k == "open"), True, True, _closable(sc))


def comparator_c(sc: dict[str, Any], policy: str) -> dict[str, Any]:
    """C/D/E: an equal-information causal model (the world's function) with an observation policy: ``own`` the scenario's single mode, ``fixed`` ACCESS_ONLY only, ``adaptive`` EXPANDED after a disagreement. No events, no validity,
    no proceedings (None where a design cannot answer)."""
    bits = _bits(sc)
    if policy == "fixed":
        obs = [W.observe(bits, "EXEC_LINKED", "ACCESS_ONLY")]
    elif policy == "adaptive":
        obs = _flow(sc, True, False)
        if sc["has_rev2"] and not sc["rev_before_exec"] and sc["s2"] in ("ACCESS", "UNKNOWN"):
            obs.append(W.observe(bits, "EXEC_LINKED", "EXPANDED"))  # the same re-observation (the causal model is told the revision; it just has nowhere to keep it)
    else:
        obs = [W.observe(bits, "EXEC_LINKED", sc["mode1"])]
    return _answer(obs, None, False, None) | {"closure": None, "open_proceedings": None}


def _bits(sc: dict[str, Any]) -> int:
    """The bits the ledger scenario reaches: exogenous a, b, c, h from the state; d (receipt), f (plan), g (approval) set; e (declaration) as in the scenario."""
    return (sc["bits"] & W.pack(a=1, b=1, c=1, h=1)) | W.pack(d=1, e=sc["declare"], f=1, g=1)


def run_l7(seed: int) -> dict:
    """The comparators on the same scenarios and the same inputs, against the ledger with the shared adaptive policy (F). Queries: Q1 access, Q2 disagreement detected, Q3 cause identified, Q4 the latest observation is still valid,
    Q5 the earlier status can be answered (history), Q6 the closure kind of the proceedings that the disagreements opened, Q7 the number of proceedings. A query that a design cannot answer is None."""
    rows = []
    for k in range(24):
        sc = {**scenario(seed, k), "open_review": False}
        if sc["rev_before_exec"]:
            continue  # the comparators are written for the sequence receipt -> plan -> execute -> observe -> (revision)
        f = run_ledger(sc, policy="adaptive_equal")
        final = f["reobserved"] or f["last"]
        cur = [m for m in f["ledger"].measurements("c") if m["status"] == "CURRENT"]
        nprocs = len(f["ledger"].proceedings("c"))
        ref = {"access": final["sensor"], "mismatch": final["mismatch"], "cause_identified": final["cause_identified"], "current_valid": bool(cur), "history_answerable": f["status_m1_at_creation"] is not None, "open_proceedings": nprocs,
               "closure": (f["closure_kinds"] or [None])[0]}
        ans = {"A_boolean_state_machine": comparator_a(sc), "B_event_sourcing": comparator_b(sc), "C_causal_model": comparator_c(sc, "own"), "D_fixed_policy": comparator_c(sc, "fixed"), "E_adaptive_policy": comparator_c(sc, "adaptive")}
        rows.append({"F": ref, **ans, "scope": sc["s2"], "has_rev2": sc["has_rev2"]})
    return {"seed": seed, "rows": rows}


# ------------------------------------------------------------------------------------------------ LAW-A1: ablations
ABLATIONS = {"intact": {}, "no_versions": {"versions": False}, "no_immutability": {"immutable": False}, "no_concurrent_proceedings": {"concurrent": False}, "no_observation_revision": {"observation_revision": False},
             "no_closure_separation": {"closure_separation": False}, "no_transaction_link": {"transaction_linked": False}}


def run_a1(seed: int) -> dict:
    """Each property taken away, on the same scenarios, and what is lost: stale plans executed, history that cannot be answered (and an UPDATE that succeeds), proceedings lost, stale observations kept CURRENT, conflicts hidden by
    a closure, executions without an approved plan."""
    arms: dict[str, dict[str, int]] = {a: {"scenarios": 0, "executed_on_stale_evidence": 0, "history_unanswerable": 0, "tamper_succeeds": 0, "proceedings_lost": 0, "stale_kept_current": 0, "conflict_hidden": 0, "unlinked_execution": 0} for a in ABLATIONS}
    for k in range(24):
        sc = scenario(seed, k)
        base = run_ledger(sc)
        for name, feat in ABLATIONS.items():
            r = base if name == "intact" else run_ledger(sc, feat)
            a = arms[name]
            a["scenarios"] += 1
            a["executed_on_stale_evidence"] += int(r["executed_on_stale_evidence"])
            a["history_unanswerable"] += int(r["status_m1_at_creation"] != "CURRENT")
            lg = r["ledger"]
            try:
                lg.db.execute("UPDATE measurements SET mismatch = 1 - mismatch WHERE id = 1")
                a["tamper_succeeds"] += 1
            except Exception:  # noqa: BLE001
                pass
            a["proceedings_lost"] += int(lg.db.execute("SELECT COUNT(*) FROM proceeding_events WHERE state = 'OVERWRITTEN'").fetchone()[0])
            a["stale_kept_current"] += int(r["status_m1"] == "CURRENT" and sc["has_rev2"] and not sc["rev_before_exec"] and sc["s2"] in ("ACCESS", "UNKNOWN"))
            final = r["reobserved"] or r["M1"]
            a["conflict_hidden"] += int(final["mismatch"] and "CLOSED_SUCCESS" in r["closure_kinds"])
            a["unlinked_execution"] += int(lg.db.execute("SELECT COUNT(*) FROM executions WHERE linked = 0").fetchone()[0] > 0)
    return {"seed": seed, "arms": arms}


RUN: dict[str, Any] = {"LAW-L1": run_l1, "LAW-L2": run_l2, "LAW-L3": run_l3, "LAW-L4": run_l4, "LAW-L5": run_l5, "LAW-L6": run_l6, "LAW-L7": run_l7, "LAW-A1": run_a1}
