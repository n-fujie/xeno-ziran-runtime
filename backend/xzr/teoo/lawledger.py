"""A persistent, append-only ledger for the AI-law line R9-R16: receipt first, evidence and proceedings kept apart, plans linked to evidence versions, immutable measurements with their own status events, and administrative closure
kept apart from legal determination and material restoration.

Written from the operational description in the request; the historical code (Appendix J-O) and the manuscripts R5-R16 were not available, so the names of the states and events are **this implementation's**, and nothing is claimed to be
the original enumeration. The ledger is a research specification on SQLite for a SYNTHETIC world: a row, a hash or a closure here creates no judicial or administrative authority and no legal or material relief (I12).

Independent records (never one status string): E guarantee evidence (the evaluator's states), A applicability (the person's or institution's claim that a guarantee does not apply), R the receipt log, P concurrent proceedings, plans,
executions, measurements (immutable) and their status events, closures. Every table is append-only (triggers refuse UPDATE and DELETE) unless a feature is switched off to measure what it was for (``features``).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any

from . import lawworld as W
from . import legal as L

MAX_PAYLOAD_BYTES = 65_536
ACTIVE_CAPACITY = 12
R10_LOCAL_LIMIT = 64
SCOPES = ("ACCESS", "METADATA", "UNKNOWN")
RECEIPT_STATES = ("ACTIVE", "QUEUED", "QUARANTINED", "REVIEWED")
CORE_GUARANTEES = ("G1", "G2")  # not nullified by a general exception
MEASURE_STATUSES = ("CURRENT", "STALE_EVIDENCE", "STALE_WORLD", "HISTORICAL")
CLOSURES = ("CLOSED_ADMIN_CONFLICT", "CLOSED_ADMIN_MODEL_MATCH")
FLAGS = {"CLOSED_ADMIN_CONFLICT": "UNRESOLVED_CONFLICT", "CLOSED_ADMIN_MODEL_MATCH": "MODEL_MATCH_NOT_LEGALLY_VERIFIED"}
FEATURES = ("versions", "immutable", "concurrent", "observation_revision", "closure_separation", "transaction_linked")
GUARANTEE_IDS = tuple(f"G{i}" for i in range(1, 16)) + ("G12A", "G12B", "G15A", "G15B", "G15C", "G15D")

_APPEND_ONLY = ("cases", "receipts", "receipt_status_events", "evidence_events", "applicability_events", "proceedings", "proceeding_events", "reviews", "plans", "plan_events", "executions", "measurements",
                "measurement_status_events", "closures", "determinations", "declarations", "refusals", "roles", "restoration_claims")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY, guarantee TEXT NOT NULL, initial_bits INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS roles(actor TEXT NOT NULL, role TEXT NOT NULL, PRIMARY KEY(actor, role));
CREATE TABLE IF NOT EXISTS receipts(seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, claim_id TEXT, payload BLOB NOT NULL, sha256 TEXT NOT NULL, received_tick INTEGER NOT NULL,
  source_version TEXT NOT NULL, jurisdiction TEXT NOT NULL, initial_state TEXT NOT NULL, reason TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS receipts_claim ON receipts(case_id, claim_id) WHERE claim_id IS NOT NULL AND initial_state != 'QUARANTINED';
CREATE TABLE IF NOT EXISTS receipt_status_events(id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_seq INTEGER NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS refusals(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, n_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, reason TEXT NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_events(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, guarantee TEXT NOT NULL, version INTEGER NOT NULL, scope TEXT NOT NULL, container TEXT NOT NULL,
  valid INTEGER NOT NULL, e_state TEXT NOT NULL, tier INTEGER, receipt_seq INTEGER, source TEXT NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS applicability_events(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, guarantee TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL, receipt_seq INTEGER, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS proceedings(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, guarantee TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT, evidence_event_id INTEGER, receipt_seq INTEGER, opened_tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS proceeding_events(id INTEGER PRIMARY KEY AUTOINCREMENT, proceeding_id INTEGER NOT NULL, state TEXT NOT NULL, actor TEXT, note TEXT, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, proceeding_id INTEGER, reviewer TEXT NOT NULL, outcome TEXT NOT NULL, evidence_version INTEGER, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS declarations(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, actor TEXT NOT NULL, text TEXT NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, guarantee TEXT NOT NULL, measure TEXT NOT NULL, evidence_version INTEGER NOT NULL, planner TEXT NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS plan_events(id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, status TEXT NOT NULL, actor TEXT, note TEXT, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS executions(id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, case_id TEXT NOT NULL, executor TEXT NOT NULL, linked INTEGER NOT NULL, world_revision INTEGER NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS measurements(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, measure_id TEXT NOT NULL, tick INTEGER NOT NULL, model_obs_id TEXT NOT NULL, world_revision INTEGER NOT NULL,
  evidence_event_id INTEGER, execution_id INTEGER, mode TEXT NOT NULL, condition_name TEXT NOT NULL, model_output INTEGER NOT NULL, sensor_output INTEGER NOT NULL, hidden_q INTEGER, mismatch INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS measurement_status_events(id INTEGER PRIMARY KEY AUTOINCREMENT, measurement_id INTEGER NOT NULL, status TEXT NOT NULL, cause TEXT NOT NULL, cause_ref INTEGER, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS closures(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, proceeding_id INTEGER NOT NULL, kind TEXT NOT NULL, flag TEXT, measurement_id INTEGER, evidence_event_id INTEGER,
  officer TEXT NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS determinations(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, proceeding_id INTEGER, authority TEXT NOT NULL, text TEXT NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS restoration_claims(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, claimed_by TEXT NOT NULL, text TEXT NOT NULL, tick INTEGER NOT NULL);
"""


def _canon(x: Any) -> bytes:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _safe_json(x: Any) -> str:
    try:
        return _canon(x).decode()
    except (TypeError, ValueError):
        return json.dumps({"unserialisable": type(x).__name__})


def evidence_container_valid(c: Any) -> tuple[bool, str]:
    """A guarantee-evidence container: an object with a tier 1-3 and the three Boolean-or-unknown facts the evaluator reads (exists, usable, score_conditioned). Anything else is not evidence; it is not a reason to forget the claim."""
    if not isinstance(c, dict):
        return False, "the evidence container is not an object"
    if c.get("tier") not in (1, 2, 3) or isinstance(c.get("tier"), bool):
        return False, "tier must be 1, 2 or 3"
    for k in ("exists", "usable", "score_conditioned"):
        if k not in c or c[k] not in (True, False, None):
            return False, f"{k} must be true, false or null"
    return True, ""


class Ledger:
    """One SQLite database, or ``:memory:``. ``features`` switches off a property to measure what it is for (all on by default): ``versions`` evidence versions bind plans and approvals; ``immutable`` triggers refuse UPDATE and
    DELETE; ``concurrent`` several proceedings of a case are kept side by side; ``observation_revision`` an observation is invalidated by new evidence or a changed world; ``closure_separation`` a closure keeps its unresolved
    conflict and its absence of legal verification; ``transaction_linked`` an execution needs an approved plan on the current evidence."""

    def __init__(self, path: str = ":memory:", features: dict[str, bool] | None = None) -> None:
        self.path = path
        self.f = {k: True for k in FEATURES} | (features or {})
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, timeout=60, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        if self.f["immutable"]:
            for t in _APPEND_ONLY:
                for op in ("UPDATE", "DELETE"):
                    self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t} BEGIN SELECT RAISE(ABORT, 'append-only: {t}'); END")
        self.db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES('tick', 0)")

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------------------------------------------------------ plumbing
    @contextmanager
    def _tx(self):  # noqa: ANN202
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.db.execute("COMMIT")

    def _tick(self) -> int:
        self.db.execute("UPDATE meta SET v = v + 1 WHERE k = 'tick'")
        return int(self.db.execute("SELECT v FROM meta WHERE k = 'tick'").fetchone()[0])

    def now(self) -> int:
        return int(self.db.execute("SELECT v FROM meta WHERE k = 'tick'").fetchone()[0])

    def set_role(self, actor: str, role: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO roles(actor, role) VALUES(?, ?)", (actor, role))

    def _has(self, actor: str, role: str) -> bool:
        return self.db.execute("SELECT 1 FROM roles WHERE actor = ? AND role = ?", (actor, role)).fetchone() is not None

    def create_case(self, case_id: str, guarantee: str, bits: int) -> None:
        if guarantee not in GUARANTEE_IDS:
            raise ValueError("unknown guarantee")
        self.db.execute("INSERT OR IGNORE INTO cases(case_id, guarantee, initial_bits) VALUES(?, ?, ?)", (case_id, guarantee, bits))

    def _case(self, case_id: str) -> sqlite3.Row:
        r = self.db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if r is None:
            raise KeyError(f"unknown case {case_id!r}")
        return r

    # ------------------------------------------------------------------------------------------------ R10 / R11: receipt first
    def receive(self, case_id: str, payload: bytes | str | dict, *, source_version: str = "v1", jurisdiction: str = "synthetic-jurisdiction") -> dict[str, Any]:
        """Record a submission. The order is the order of the request: the claim is received and its id and event are stored first, the evidence container is validated afterwards, and applicability and proceedings follow. A bad
        container, a duplicate or an overflow never removes the fact that the submission was made. Input above 65,536 bytes is outside the contract: it is refused and logged as a refusal, never as a receipt, and no durability is implied."""
        raw = payload if isinstance(payload, bytes) else payload.encode() if isinstance(payload, str) else _canon(payload)
        sha = hashlib.sha256(raw).hexdigest()
        with self._tx():
            tick = self._tick()
            if len(raw) > MAX_PAYLOAD_BYTES:
                self.db.execute("INSERT INTO refusals(case_id, n_bytes, sha256, reason, tick) VALUES(?, ?, ?, ?, ?)", (case_id, len(raw), sha, "above the 65,536-byte contract: not received", tick))
                return {"received": False, "state": "NOT_RECEIVED", "reason": "the input is above the 65,536-byte contract and is not a receipt; no durability is implied", "sha256": sha, "case_id": case_id}
            doc, why = None, ""
            try:
                doc = json.loads(raw)
                if not isinstance(doc, dict) or not isinstance(doc.get("claim_id"), str) or not doc["claim_id"]:
                    doc, why = None, "the submission is not an object with a claim_id"
                elif doc.get("guarantee") not in GUARANTEE_IDS:
                    why = "unknown guarantee"
                    doc = None
            except (ValueError, UnicodeDecodeError):
                why = "the payload is not valid JSON"
            claim = doc["claim_id"] if doc else None
            if doc is None:
                again = self.db.execute("SELECT seq FROM receipts WHERE case_id = ? AND claim_id IS NULL AND sha256 = ? ORDER BY seq LIMIT 1", (case_id, sha)).fetchone()
                if again is not None:
                    return {**self._receipt_row(again["seq"]), "received": True, "duplicate": True}
                seq = self._insert_receipt(case_id, None, raw, sha, tick, source_version, jurisdiction, "QUARANTINED", why)
                return {"received": True, "receipt_seq": seq, "case_id": case_id, "claim_id": None, "state": "QUARANTINED", "duplicate": False, "reason": why, "sha256": sha, "evidence": None, "proceedings": []}
            same = self.db.execute("SELECT seq, initial_state, reason FROM receipts WHERE case_id = ? AND claim_id = ? AND sha256 = ? ORDER BY seq LIMIT 1", (case_id, claim, sha)).fetchone()
            if same is not None:
                return {**self._receipt_row(same["seq"]), "received": True, "duplicate": True}
            holder = self.db.execute("SELECT seq FROM receipts WHERE case_id = ? AND claim_id = ? AND initial_state != 'QUARANTINED'", (case_id, claim)).fetchone()
            if holder is not None:
                seq = self._insert_receipt(case_id, claim, raw, sha, tick, source_version, jurisdiction, "QUARANTINED", f"claim_id conflict: receipt {holder['seq']} holds this id with a different body")
                return {**self._receipt_row(seq), "received": True, "duplicate": False, "conflict_with": holder["seq"]}
            n_active = self.db.execute("SELECT COUNT(*) FROM receipts r WHERE r.case_id = ? AND " + self._state_expr("r") + " = 'ACTIVE'", (case_id,)).fetchone()[0]
            state = "ACTIVE" if n_active < ACTIVE_CAPACITY else "QUEUED"
            seq = self._insert_receipt(case_id, claim, raw, sha, tick, source_version, jurisdiction, state, "received" if state == "ACTIVE" else f"queued: {ACTIVE_CAPACITY} receipts of this case are ACTIVE")
            out = {**self._receipt_row(seq), "received": True, "duplicate": False, "evidence": None, "proceedings": []}
            g = doc["guarantee"]
            if "evidence" in doc:
                out["evidence"] = self._register_evidence(case_id, g, doc["evidence"], doc.get("scope", "UNKNOWN"), seq, f"submission {claim}", tick)
                if not out["evidence"]["valid"]:
                    out["proceedings"].append(self._open(case_id, g, "EVIDENCE_REVIEW", claim, seq, "the evidence container is invalid: " + out["evidence"]["reason"], tick))
            if isinstance(doc.get("exception"), dict):
                out["exception"] = self._request_exception(case_id, g, str(doc["exception"].get("reason", "")), seq, tick)
                out["proceedings"].append(out["exception"]["proceeding"])
            return out

    def _insert_receipt(self, case_id: str, claim: str | None, raw: bytes, sha: str, tick: int, src: str, jur: str, state: str, reason: str) -> int:
        cur = self.db.execute("INSERT INTO receipts(case_id, claim_id, payload, sha256, received_tick, source_version, jurisdiction, initial_state, reason) VALUES(?,?,?,?,?,?,?,?,?)",
                              (case_id, claim, raw, sha, tick, src, jur, state, reason))
        return int(cur.lastrowid or 0)

    @staticmethod
    def _state_expr(alias: str) -> str:
        return f"COALESCE((SELECT e.state FROM receipt_status_events e WHERE e.receipt_seq = {alias}.seq ORDER BY e.id DESC LIMIT 1), {alias}.initial_state)"

    def _receipt_row(self, seq: int) -> dict[str, Any]:
        r = self.db.execute("SELECT r.seq, r.case_id, r.claim_id, r.sha256, r.received_tick, r.source_version, r.jurisdiction, r.reason, " + self._state_expr("r") + " AS state FROM receipts r WHERE r.seq = ?", (seq,)).fetchone()
        return {"receipt_seq": r["seq"], "case_id": r["case_id"], "claim_id": r["claim_id"], "sha256": r["sha256"], "received_tick": r["received_tick"], "source_version": r["source_version"], "jurisdiction": r["jurisdiction"],
                "reason": r["reason"], "state": r["state"]}

    def receipts(self, case_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT r.seq FROM receipts r" + (" WHERE r.case_id = ?" if case_id else "") + " ORDER BY r.seq"
        return [self._receipt_row(x[0]) for x in self.db.execute(q, (case_id,) if case_id else ())]

    def counts(self, case_id: str) -> dict[str, int]:
        out = {s: 0 for s in RECEIPT_STATES}
        for r in self.receipts(case_id):
            out[r["state"]] += 1
        return out | {"refused": self.db.execute("SELECT COUNT(*) FROM refusals WHERE case_id = ?", (case_id,)).fetchone()[0]}

    def mark_reviewed(self, seq: int, actor: str) -> dict[str, Any]:
        """The submission has been reviewed: a status event; the oldest QUEUED receipt of the case is promoted to ACTIVE (a second event). Nothing is overwritten."""
        with self._tx():
            row = self._receipt_row(seq)
            if row["state"] not in ("ACTIVE", "QUEUED"):
                return {"ok": False, "reason": f"a {row['state']} receipt cannot be marked reviewed"}
            tick = self._tick()
            self.db.execute("INSERT INTO receipt_status_events(receipt_seq, state, reason, tick) VALUES(?, 'REVIEWED', ?, ?)", (seq, f"reviewed by {actor}", tick))
            nxt = self.db.execute("SELECT r.seq FROM receipts r WHERE r.case_id = ? AND " + self._state_expr("r") + " = 'QUEUED' ORDER BY r.seq LIMIT 1", (row["case_id"],)).fetchone()
            promoted = None
            if nxt is not None and self.counts(row["case_id"])["ACTIVE"] < ACTIVE_CAPACITY:
                self.db.execute("INSERT INTO receipt_status_events(receipt_seq, state, reason, tick) VALUES(?, 'ACTIVE', ?, ?)", (nxt[0], "promoted from the queue", tick))
                promoted = nxt[0]
            return {"ok": True, "reviewed": seq, "promoted": promoted}

    # ------------------------------------------------------------------------------------------------ R9: evidence, applicability, proceedings
    def register_evidence(self, case_id: str, guarantee: str, container: Any, *, scope: str = "UNKNOWN", receipt_seq: int | None = None, source: str = "") -> dict[str, Any]:
        with self._tx():
            return self._register_evidence(case_id, guarantee, container, scope, receipt_seq, source, self._tick())

    def _register_evidence(self, case_id: str, guarantee: str, container: Any, scope: str, receipt_seq: int | None, source: str, tick: int) -> dict[str, Any]:
        scope = scope if scope in SCOPES else "UNKNOWN"
        ok, why = evidence_container_valid(container)
        ver = int(self.db.execute("SELECT COALESCE(MAX(version), 0) FROM evidence_events WHERE case_id = ? AND guarantee = ?", (case_id, guarantee)).fetchone()[0]) + 1
        if ok:
            ev = L.Evidence(exists=container["exists"], usable=container["usable"], score_conditioned=container["score_conditioned"], tier=container["tier"], shortfalls=tuple(container.get("shortfalls", ())))
            state = L.decide(ev)["state"]
        else:
            state = "INDETERMINATE"
        cur = self.db.execute("INSERT INTO evidence_events(case_id, guarantee, version, scope, container, valid, e_state, tier, receipt_seq, source, tick) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                              (case_id, guarantee, ver, scope, _safe_json(container), int(ok), state, container.get("tier") if ok else None, receipt_seq, source, tick))
        eid = int(cur.lastrowid or 0)
        invalidated, stale_plans = [], []
        if ok:  # a container that is not evidence is not an evidence revision: it invalidates nothing
            if scope in ("ACCESS", "UNKNOWN") and self.f["observation_revision"]:
                for m in self._measurements_rows(case_id):
                    if self._m_status(m["id"]) == "CURRENT":
                        self._set_m_status(m["id"], "STALE_EVIDENCE", f"evidence event {eid} (scope {scope})", eid, tick)
                        invalidated.append(m["id"])
            if self.f["versions"]:  # the conservative rule for unexecuted plans holds for every scope
                for p in self.db.execute("SELECT id FROM plans WHERE case_id = ? AND guarantee = ? AND evidence_version < ?", (case_id, guarantee, ver)):
                    if self._plan_status(p[0]) in ("PLANNED", "APPROVED"):
                        self._plan_event(p[0], "STALE_EVIDENCE", None, f"evidence version {ver} supersedes the plan's", tick)
                        stale_plans.append(p[0])
        return {"evidence_event_id": eid, "case_id": case_id, "guarantee": guarantee, "version": ver, "scope": scope, "valid": bool(ok), "reason": why, "e_state": state, "invalidated_measurements": invalidated, "stale_plans": stale_plans}

    def evidence_state(self, case_id: str, guarantee: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM evidence_events WHERE case_id = ? AND guarantee = ? AND valid = 1 ORDER BY id DESC LIMIT 1", (case_id, guarantee)).fetchone()
        return None if r is None else {"evidence_event_id": r["id"], "version": r["version"], "scope": r["scope"], "e_state": r["e_state"], "tier": r["tier"]}

    def evidence_events(self, case_id: str) -> list[dict[str, Any]]:
        return [{k: r[k] for k in ("id", "guarantee", "version", "scope", "valid", "e_state", "tier", "receipt_seq", "source", "tick")} for r in self.db.execute("SELECT * FROM evidence_events WHERE case_id = ? ORDER BY id", (case_id,))]

    def request_exception(self, case_id: str, guarantee: str, reason: str, receipt_seq: int | None = None) -> dict[str, Any]:
        with self._tx():
            return self._request_exception(case_id, guarantee, reason, receipt_seq, self._tick())

    def _request_exception(self, case_id: str, guarantee: str, reason: str, receipt_seq: int | None, tick: int) -> dict[str, Any]:
        """A request that a guarantee does not apply. It is an event of its own: the evidence stays as it was (E is never rewritten), the applicability claim is A, and a proceeding is opened. G1 and G2 are core conditions that a
        general exception cannot nullify: the claim is REJECTED at once and the proceeding records that an exception review is still required."""
        a = "REJECTED" if guarantee in CORE_GUARANTEES else "EXCEPTION_REQUESTED"
        self.db.execute("INSERT INTO applicability_events(case_id, guarantee, state, reason, receipt_seq, tick) VALUES(?,?,?,?,?,?)",
                        (case_id, guarantee, a, reason + (" (G1 and G2 cannot be nullified by a general exception)" if a == "REJECTED" else ""), receipt_seq, tick))
        proc = self._open(case_id, guarantee, "EXCEPTION_REVIEW_REQUIRED", None, receipt_seq, reason, tick)
        return {"guarantee": guarantee, "applicability": a, "proceeding": proc, "evidence_unchanged": self.evidence_state(case_id, guarantee)}

    def decide_exception(self, case_id: str, guarantee: str, accept: bool, reviewer: str, reason: str = "") -> dict[str, Any]:
        with self._tx():
            if guarantee in CORE_GUARANTEES and accept:
                return {"ok": False, "reason": "G1 and G2 cannot be nullified by a general exception"}
            if not self._has(reviewer, "reviewer"):
                return {"ok": False, "reason": "the actor has no reviewer role in this TEST environment"}
            tick = self._tick()
            self.db.execute("INSERT INTO applicability_events(case_id, guarantee, state, reason, receipt_seq, tick) VALUES(?,?,?,?,NULL,?)", (case_id, guarantee, "ACCEPTED" if accept else "REJECTED", reason or f"decided by {reviewer}", tick))
            for p in self.proceedings(case_id, open_only=True):
                if p["kind"] == "EXCEPTION_REVIEW_REQUIRED" and p["guarantee"] == guarantee:
                    self.db.execute("INSERT INTO reviews(case_id, proceeding_id, reviewer, outcome, evidence_version, tick) VALUES(?,?,?,?,?,?)",
                                    (case_id, p["id"], reviewer, "EXCEPTION_ACCEPTED" if accept else "EXCEPTION_REJECTED", (self.evidence_state(case_id, guarantee) or {}).get("version"), tick))
                    self.db.execute("INSERT INTO proceeding_events(proceeding_id, state, actor, note, tick) VALUES(?, 'REVIEWED', ?, ?, ?)", (p["id"], reviewer, "exception decided", tick))
            return {"ok": True, "applicability": "ACCEPTED" if accept else "REJECTED"}

    def applicability(self, case_id: str, guarantee: str) -> str:
        r = self.db.execute("SELECT state FROM applicability_events WHERE case_id = ? AND guarantee = ? ORDER BY id DESC LIMIT 1", (case_id, guarantee)).fetchone()
        return r[0] if r else "APPLICABLE"

    def effective_state(self, case_id: str, guarantee: str) -> dict[str, Any]:
        """E, A and the proceedings side by side, and the state they imply: INAPPLICABLE only once an exception has been ACCEPTED by a review; otherwise the evidence state stands, whatever was requested."""
        ev = self.evidence_state(case_id, guarantee)
        a = self.applicability(case_id, guarantee)
        e = ev["e_state"] if ev else "INDETERMINATE"
        open_p = [p["kind"] for p in self.proceedings(case_id, open_only=True) if p["guarantee"] == guarantee]
        return {"E": e, "A": a, "W": open_p, "effective": "INAPPLICABLE" if a == "ACCEPTED" else e, "evidence_version": ev["version"] if ev else None}

    def open_proceeding(self, case_id: str, guarantee: str, kind: str, ref: str | None = None) -> dict[str, Any]:
        with self._tx():
            return self._open(case_id, guarantee, kind, ref, None, "", self._tick())

    def _open(self, case_id: str, guarantee: str, kind: str, ref: str | None, receipt_seq: int | None, note: str, tick: int) -> dict[str, Any]:
        if not self.f["concurrent"]:  # the single-state-string variant: a new proceeding silently replaces the earlier ones
            for p in self.proceedings(case_id, open_only=True):
                self.db.execute("INSERT INTO proceeding_events(proceeding_id, state, actor, note, tick) VALUES(?, 'OVERWRITTEN', NULL, 'replaced by a newer state', ?)", (p["id"], tick))
        last = self.db.execute("SELECT id FROM evidence_events WHERE case_id = ? AND guarantee = ? AND valid = 1 ORDER BY id DESC LIMIT 1", (case_id, guarantee)).fetchone()
        cur = self.db.execute("INSERT INTO proceedings(case_id, guarantee, kind, ref, evidence_event_id, receipt_seq, opened_tick) VALUES(?,?,?,?,?,?,?)", (case_id, guarantee, kind, ref, last[0] if last else None, receipt_seq, tick))
        pid = int(cur.lastrowid or 0)
        self.db.execute("INSERT INTO proceeding_events(proceeding_id, state, actor, note, tick) VALUES(?, 'OPEN', NULL, ?, ?)", (pid, note, tick))
        return {"id": pid, "kind": kind, "guarantee": guarantee, "ref": ref}

    def _p_state(self, pid: int) -> str:
        return self.db.execute("SELECT state FROM proceeding_events WHERE proceeding_id = ? ORDER BY id DESC LIMIT 1", (pid,)).fetchone()[0]

    def proceedings(self, case_id: str, open_only: bool = False) -> list[dict[str, Any]]:
        out = []
        for p in self.db.execute("SELECT * FROM proceedings WHERE case_id = ? ORDER BY id", (case_id,)):
            st = self._p_state(p["id"])
            if open_only and st not in ("OPEN", "REVIEWED"):
                continue
            out.append({"id": p["id"], "guarantee": p["guarantee"], "kind": p["kind"], "ref": p["ref"], "evidence_event_id": p["evidence_event_id"], "state": st, "opened_tick": p["opened_tick"]})
        return out

    def complete_review(self, proceeding_id: int, reviewer: str, outcome: str) -> dict[str, Any]:
        with self._tx():
            p = self.db.execute("SELECT * FROM proceedings WHERE id = ?", (proceeding_id,)).fetchone()
            if p is None or not self._has(reviewer, "reviewer"):
                return {"ok": False, "reason": "no such proceeding, or the actor has no reviewer role in this TEST environment"}
            tick = self._tick()
            v = (self.evidence_state(p["case_id"], p["guarantee"]) or {}).get("version")
            self.db.execute("INSERT INTO reviews(case_id, proceeding_id, reviewer, outcome, evidence_version, tick) VALUES(?,?,?,?,?,?)", (p["case_id"], proceeding_id, reviewer, outcome, v, tick))
            self.db.execute("INSERT INTO proceeding_events(proceeding_id, state, actor, note, tick) VALUES(?, 'REVIEWED', ?, ?, ?)", (proceeding_id, reviewer, outcome, tick))
            return {"ok": True}

    # ------------------------------------------------------------------------------------------------ R13: plans, approval, execution
    def declare(self, case_id: str, actor: str, text: str) -> None:
        with self._tx():
            self.db.execute("INSERT INTO declarations(case_id, actor, text, tick) VALUES(?,?,?,?)", (case_id, actor, text, self._tick()))

    def _plan_event(self, plan_id: int, status: str, actor: str | None, note: str, tick: int) -> None:
        self.db.execute("INSERT INTO plan_events(plan_id, status, actor, note, tick) VALUES(?,?,?,?,?)", (plan_id, status, actor, note, tick))

    def _plan_status(self, plan_id: int) -> str:
        return self.db.execute("SELECT status FROM plan_events WHERE plan_id = ? ORDER BY id DESC LIMIT 1", (plan_id,)).fetchone()[0]

    def plan(self, case_id: str, measure: str, planner: str) -> dict[str, Any]:
        with self._tx():
            c = self._case(case_id)
            if not self._has(planner, "planner"):
                return {"ok": False, "reason": "the actor has no planner role in this TEST environment"}
            ev = self.evidence_state(case_id, c["guarantee"])
            if measure not in W.CONDITIONS or ev is None:
                return {"ok": False, "reason": "unknown measure, or no valid evidence is registered for the case"}
            tick = self._tick()
            cur = self.db.execute("INSERT INTO plans(case_id, guarantee, measure, evidence_version, planner, tick) VALUES(?,?,?,?,?,?)", (case_id, c["guarantee"], measure, ev["version"], planner, tick))
            pid = int(cur.lastrowid or 0)
            self._plan_event(pid, "PLANNED", planner, f"on evidence version {ev['version']}", tick)
            return {"ok": True, "plan_id": pid, "evidence_version": ev["version"]}

    def plan_status(self, plan_id: int) -> str:
        return self._plan_status(plan_id)

    def approve(self, plan_id: int, approver: str) -> dict[str, Any]:
        """Approval needs: the latest usable evidence (the plan's version is the current one and the container is valid and not INDETERMINATE), the required reviews completed, and an approver with the TEST authority. A stale plan is not approved."""
        with self._tx():
            p = self.db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            missing = []
            if p is None:
                return {"ok": False, "missing": ["no such plan"]}
            if not self._has(approver, "approver"):
                missing.append("the approver has no approver role in this TEST environment")
            if self._plan_status(plan_id) != "PLANNED":
                missing.append(f"the plan is {self._plan_status(plan_id)}, not PLANNED")
            ev = self.evidence_state(p["case_id"], p["guarantee"])
            if self.f["versions"]:
                if ev is None or ev["version"] != p["evidence_version"]:
                    missing.append("the plan refers to an evidence version that is not the current one")
                if ev is not None and ev["e_state"] == "INDETERMINATE":
                    missing.append("the current evidence does not permit a conclusion (INDETERMINATE)")
            for pr in self.proceedings(p["case_id"], open_only=True):
                if pr["kind"] in ("EVIDENCE_REVIEW", "HUMAN_REVIEW", "EXCEPTION_REVIEW_REQUIRED") and pr["guarantee"] == p["guarantee"] and pr["state"] != "REVIEWED":
                    missing.append(f"required review not completed: {pr['kind']} (proceeding {pr['id']})")
            if missing:
                return {"ok": False, "missing": missing}
            self._plan_event(plan_id, "APPROVED", approver, "approved on the current evidence", self._tick())
            return {"ok": True}

    def execute(self, plan_id: int, executor: str) -> dict[str, Any]:
        """An execution by an actor other than the approver. Linked (the default and the only path when ``transaction_linked``): the plan must be APPROVED and on the current evidence. The unlinked gate path exists to be measured
        (EXEC_GATE): it asks only for the executor's role. An executed event is never removed; a new world revision makes every current observation STALE_WORLD."""
        with self._tx():
            p = self.db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if p is None or not self._has(executor, "executor"):
                return {"ok": False, "missing": ["no such plan, or the executor has no executor role in this TEST environment"]}
            st = self._plan_status(plan_id)
            linked = self.f["transaction_linked"]
            missing = []
            if linked:
                if st != "APPROVED":
                    missing.append(f"the plan is {st}, not APPROVED")
                appr = self.db.execute("SELECT actor FROM plan_events WHERE plan_id = ? AND status = 'APPROVED' ORDER BY id DESC LIMIT 1", (plan_id,)).fetchone()
                if appr is not None and appr[0] == executor:
                    missing.append("the executor is the approver: execution is by a different actor")
                ev = self.evidence_state(p["case_id"], p["guarantee"])
                if self.f["versions"] and (ev is None or ev["version"] != p["evidence_version"]):
                    missing.append("the plan's evidence version is not the current one (STALE_EVIDENCE)")
            elif st in ("EXECUTED",):
                missing.append("already executed")
            if missing:
                return {"ok": False, "missing": missing}
            tick = self._tick()
            rev = int(self.db.execute("SELECT COUNT(*) FROM executions WHERE case_id = ?", (p["case_id"],)).fetchone()[0]) + 1
            cur = self.db.execute("INSERT INTO executions(plan_id, case_id, executor, linked, world_revision, tick) VALUES(?,?,?,?,?,?)", (plan_id, p["case_id"], executor, int(linked), rev, tick))
            self._plan_event(plan_id, "EXECUTED", executor, "executed" + ("" if linked else " through the unlinked gate"), tick)
            stale = []
            if self.f["observation_revision"]:
                for m in self._measurements_rows(p["case_id"]):
                    if self._m_status(m["id"]) == "CURRENT":
                        self._set_m_status(m["id"], "STALE_WORLD", f"execution {cur.lastrowid} changed the world to revision {rev}", int(cur.lastrowid or 0), tick)
                        stale.append(m["id"])
            return {"ok": True, "execution_id": int(cur.lastrowid or 0), "world_revision": rev, "stale_measurements": stale}

    def world(self, case_id: str) -> dict[str, Any]:
        """The state of the case's world: the exogenous bits a, b, c, h from creation, and d, e, f, g from the history (a valid receipt, a declaration, a plan, an approval), the intervention condition reached, the world revision."""
        c = self._case(case_id)
        bits = c["initial_bits"] & ~(W.pack(d=1, e=1, f=1, g=1))
        has_receipt = any(r["state"] in ("ACTIVE", "QUEUED", "REVIEWED") for r in self.receipts(case_id))
        has_decl = self.db.execute("SELECT 1 FROM declarations WHERE case_id = ? LIMIT 1", (case_id,)).fetchone() is not None
        plans = [r["id"] for r in self.db.execute("SELECT id FROM plans WHERE case_id = ?", (case_id,))]
        approved = any(self.db.execute("SELECT 1 FROM plan_events WHERE plan_id = ? AND status = 'APPROVED'", (p,)).fetchone() for p in plans)
        ex = self.db.execute("SELECT * FROM executions WHERE case_id = ? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
        bits |= W.pack(d=has_receipt, e=has_decl, f=bool(plans), g=approved or (ex is not None and not ex["linked"]))
        cond = ("EXEC_LINKED" if ex["linked"] else "EXEC_GATE") if ex is not None else "PLAN_ONLY" if plans else "DECLARATION_ONLY" if has_decl else "RECEIPT_ONLY" if has_receipt else "BASE"
        rev = int(self.db.execute("SELECT COUNT(*) FROM executions WHERE case_id = ?", (case_id,)).fetchone()[0])
        return {"bits": bits, "condition": cond, "world_revision": rev, "execution_id": ex["id"] if ex is not None else None}

    # ------------------------------------------------------------------------------------------------ R14 / R15 / R16: measurements
    def _measurements_rows(self, case_id: str) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM measurements WHERE case_id = ? ORDER BY id", (case_id,)))

    def _m_status(self, mid: int) -> str:
        return self.db.execute("SELECT status FROM measurement_status_events WHERE measurement_id = ? ORDER BY id DESC LIMIT 1", (mid,)).fetchone()[0]

    def _set_m_status(self, mid: int, status: str, cause: str, ref: int | None, tick: int) -> None:
        if not self.f["immutable"]:  # the variant that overwrites: the earlier status is gone
            self.db.execute("DELETE FROM measurement_status_events WHERE measurement_id = ?", (mid,))
        self.db.execute("INSERT INTO measurement_status_events(measurement_id, status, cause, cause_ref, tick) VALUES(?,?,?,?,?)", (mid, status, cause, ref, tick))

    def observe(self, case_id: str, mode: str, model_obs_id: str | None = None) -> dict[str, Any]:
        """A measurement: the model's output and the synthetic sensor's, with the evidence event, the execution and the world revision it was made on. The payload is never changed afterwards; its validity is carried by status events.
        The same evidence, the same model observation and the same mode are not compared twice."""
        with self._tx():
            c = self._case(case_id)
            w = self.world(case_id)
            ev = self.db.execute("SELECT id FROM evidence_events WHERE case_id = ? AND guarantee = ? AND valid = 1 ORDER BY id DESC LIMIT 1", (case_id, c["guarantee"])).fetchone()
            eid = ev[0] if ev else None
            n = int(self.db.execute("SELECT COUNT(*) FROM measurements WHERE case_id = ?", (case_id,)).fetchone()[0]) + 1
            mo = model_obs_id or f"model-obs-{n}"
            dup = self.db.execute("SELECT id FROM measurements WHERE case_id = ? AND model_obs_id = ? AND mode = ? AND evidence_event_id IS ?", (case_id, mo, mode, eid)).fetchone()
            if dup is not None:
                return {"ok": False, "duplicate_of": dup[0], "reason": "the same evidence, model observation and observation mode have already been compared"}
            o = W.observe(w["bits"], w["condition"], mode)
            tick = self._tick()
            cur = self.db.execute("INSERT INTO measurements(case_id, measure_id, tick, model_obs_id, world_revision, evidence_event_id, execution_id, mode, condition_name, model_output, sensor_output, hidden_q, mismatch) "
                                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (case_id, f"{case_id}/m{n}", tick, mo, w["world_revision"], eid, w["execution_id"], mode, w["condition"], int(o["model"]), int(o["sensor"]),
                                                                          None if o["q"] is None else int(o["q"]), int(o["mismatch"])))
            mid = int(cur.lastrowid or 0)
            if self.f["observation_revision"]:  # a newer current observation makes earlier current ones historical (their payloads are untouched)
                for m in self._measurements_rows(case_id):
                    if m["id"] != mid and self._m_status(m["id"]) == "CURRENT":
                        self._set_m_status(m["id"], "HISTORICAL", f"superseded by measurement {mid}", mid, tick)
            self.db.execute("INSERT INTO measurement_status_events(measurement_id, status, cause, cause_ref, tick) VALUES(?, 'CURRENT', 'MEASUREMENT_CREATED', ?, ?)", (mid, mid, tick))
            opened = []
            if o["mismatch"]:  # a disagreement opens its own proceedings; that it exists is not that its cause is found
                for kind in ("EVIDENCE_REVIEW", "REASSESS_OUTCOME"):
                    opened.append(self._open(case_id, c["guarantee"], kind, f"measurement {mid}", None, "model and synthetic sensor disagree", tick))
            return {"ok": True, "measurement_id": mid, "condition": w["condition"], "mode": mode, "model": bool(o["model"]), "sensor": bool(o["sensor"]), "mismatch": bool(o["mismatch"]), "q": o["q"],
                    "cause_identified": o["cause_identified"], "evidence_event_id": eid, "execution_id": w["execution_id"], "world_revision": w["world_revision"], "proceedings": opened}

    def measurements(self, case_id: str) -> list[dict[str, Any]]:
        out = []
        for m in self._measurements_rows(case_id):
            hist = [{"status": s["status"], "cause": s["cause"], "tick": s["tick"]} for s in self.db.execute("SELECT * FROM measurement_status_events WHERE measurement_id = ? ORDER BY id", (m["id"],))]
            out.append({"id": m["id"], "measure_id": m["measure_id"], "tick": m["tick"], "model_obs_id": m["model_obs_id"], "world_revision": m["world_revision"], "evidence_event_id": m["evidence_event_id"], "execution_id": m["execution_id"],
                        "mode": m["mode"], "condition": m["condition_name"], "model": bool(m["model_output"]), "sensor": bool(m["sensor_output"]), "q": None if m["hidden_q"] is None else bool(m["hidden_q"]),
                        "mismatch": bool(m["mismatch"]), "status": hist[-1]["status"], "status_history": hist})
        return out

    def status_at(self, measurement_id: int, tick: int) -> str | None:
        """The status the measurement had at a past tick: answerable only because status events are kept (an overwriting variant cannot say)."""
        r = self.db.execute("SELECT status FROM measurement_status_events WHERE measurement_id = ? AND tick <= ? ORDER BY id DESC LIMIT 1", (measurement_id, tick)).fetchone()
        return r[0] if r else None

    # ------------------------------------------------------------------------------------------------ R16: administrative closure
    def close_review(self, case_id: str, proceeding_id: int, officer: str) -> dict[str, Any]:
        """Administrative closure of a proceeding: the internal review work is over. It needs, in this order, the evidence revision the proceeding concerns, a model observation newer than it, a still-current sensor comparison after
        that, and the officer's record. It ends in CLOSED_ADMIN_CONFLICT (with UNRESOLVED_CONFLICT kept) or CLOSED_ADMIN_MODEL_MATCH (with MODEL_MATCH_NOT_LEGALLY_VERIFIED kept). It is not an evidential resolution, not a legal
        determination and not a restoration, and says so."""
        with self._tx():
            p = self.db.execute("SELECT * FROM proceedings WHERE id = ? AND case_id = ?", (proceeding_id, case_id)).fetchone()
            missing = []
            if p is None:
                return {"ok": False, "missing": ["no such proceeding in this case"]}
            if not self._has(officer, "officer"):
                missing.append("the actor has no officer role in this TEST environment")
            if self._p_state(proceeding_id) not in ("OPEN", "REVIEWED"):
                missing.append(f"the proceeding is {self._p_state(proceeding_id)}")
            target = p["evidence_event_id"]
            cur_ev = self.evidence_state(case_id, p["guarantee"])
            if target is None:
                missing.append("no evidence revision is registered for the proceeding")
            cur_m = [m for m in self._measurements_rows(case_id) if self._m_status(m["id"]) == "CURRENT"]
            newer = [m for m in cur_m if target is not None and cur_ev is not None and (m["evidence_event_id"] or 0) >= cur_ev["evidence_event_id"] >= target]
            if target is not None and not cur_m:
                missing.append("no current sensor comparison: the observations are stale or absent (reobservation required)")
            elif target is not None and not newer:
                missing.append("no model observation newer than the evidence revision with a current sensor comparison after it")
            reviewed = self.db.execute("SELECT 1 FROM reviews WHERE proceeding_id = ? LIMIT 1", (proceeding_id,)).fetchone() is not None or self._p_state(proceeding_id) == "REVIEWED"
            if not reviewed and p["kind"] != "EXCEPTION_REVIEW_REQUIRED":
                missing.append("no review has been recorded for the proceeding")
            if missing:
                return {"ok": False, "missing": missing}
            m = max(newer, key=lambda r: r["id"])
            tick = self._tick()
            if self.f["closure_separation"]:
                kind = "CLOSED_ADMIN_CONFLICT" if m["mismatch"] else "CLOSED_ADMIN_MODEL_MATCH"
                flag: str | None = FLAGS[kind]
            else:
                kind, flag = "CLOSED_SUCCESS", None
            cur = self.db.execute("INSERT INTO closures(case_id, proceeding_id, kind, flag, measurement_id, evidence_event_id, officer, tick) VALUES(?,?,?,?,?,?,?,?)", (case_id, proceeding_id, kind, flag, m["id"], cur_ev["evidence_event_id"] if cur_ev else None, officer, tick))
            self.db.execute("INSERT INTO proceeding_events(proceeding_id, state, actor, note, tick) VALUES(?, ?, ?, ?, ?)", (proceeding_id, kind, officer, flag or "", tick))
            return {"ok": True, "closure_id": int(cur.lastrowid or 0), "kind": kind, "flag": flag, "measurement_id": m["id"], "legal_determination": None, "evidential_resolution": False,
                    "material_restoration_verified": False, "positive_law_verified": False}

    def closures(self, case_id: str) -> list[dict[str, Any]]:
        return [{k: r[k] for k in ("id", "proceeding_id", "kind", "flag", "measurement_id", "evidence_event_id", "officer", "tick")} for r in self.db.execute("SELECT * FROM closures WHERE case_id = ? ORDER BY id", (case_id,))]

    def record_determination(self, case_id: str, proceeding_id: int | None, authority: str, text: str) -> dict[str, Any]:
        """A determination that a competent authority is reported to have made, recorded as an input. This synthetic environment cannot make one and creates none: the record changes no state and verifies no law."""
        with self._tx():
            self.db.execute("INSERT INTO determinations(case_id, proceeding_id, authority, text, tick) VALUES(?,?,?,?,?)", (case_id, proceeding_id, authority, text, self._tick()))
            return {"ok": True, "positive_law_verified": False, "material_restoration_verified": False}

    def restoration_sequence(self, case_id: str) -> dict[str, Any]:
        """The six independent records of R12 for a case: each present or absent on its own; none implies the next. Material restoration is never verified in this environment."""
        rc = [r for r in self.receipts(case_id) if r["state"] != "QUARANTINED"]
        ev = self.evidence_events(case_id)
        rv = self.db.execute("SELECT COUNT(*) FROM reviews WHERE case_id = ?", (case_id,)).fetchone()[0]
        pl = self.db.execute("SELECT COUNT(*) FROM plans WHERE case_id = ?", (case_id,)).fetchone()[0]
        ms = self.measurements(case_id)
        cl = self.closures(case_id)
        det = self.db.execute("SELECT COUNT(*) FROM determinations WHERE case_id = ?", (case_id,)).fetchone()[0]
        return {"stages": [{"stage": "submission_receipt", "present": bool(rc), "n": len(rc)}, {"stage": "evidence_finding", "present": any(e["valid"] for e in ev), "n": len(ev)},
                           {"stage": "human_review", "present": rv > 0, "n": rv}, {"stage": "proposed_measure", "present": pl > 0, "n": pl},
                           {"stage": "downstream_observation", "present": bool(ms), "n": len(ms), "current": sum(m["status"] == "CURRENT" for m in ms)}, {"stage": "material_restoration", "present": False, "n": 0}],
                "administrative_closures": [c["kind"] for c in cl], "unresolved_conflict": any(c["flag"] == "UNRESOLVED_CONFLICT" for c in cl), "determinations_recorded": det,
                "access_changed_in_the_synthetic_world": any(m["condition"] in ("EXEC_GATE", "EXEC_LINKED") and m["sensor"] for m in ms), "material_restoration_verified": False, "positive_law_verified": False,
                "legal_determination_by_this_software": None}

    def snapshot(self, case_id: str) -> dict[str, Any]:
        c = self._case(case_id)
        return {"case_id": case_id, "guarantee": c["guarantee"], "world": self.world(case_id), "receipts": self.receipts(case_id), "evidence": self.evidence_events(case_id), "effective": self.effective_state(case_id, c["guarantee"]),
                "proceedings": self.proceedings(case_id), "measurements": self.measurements(case_id), "closures": self.closures(case_id), "restoration": self.restoration_sequence(case_id)}


def r10_batch(submissions: list[dict[str, Any]], *, active: int = ACTIVE_CAPACITY, limit: int = R10_LOCAL_LIMIT) -> list[dict[str, Any]]:
    """The historical R10 condition on one case, in memory and within one evaluation call: ACTIVE up to 12, QUEUED up to the local limit of 64 valid submissions, the rest UNACKNOWLEDGED (a statement that they were not received,
    not a permanent record). The limit is a condition of that experiment, not a rule of this ledger (whose queue is not bounded at 64); the persistent version is ``Ledger``."""
    out, n_valid = [], 0
    for s in submissions:
        ok = isinstance(s, dict) and isinstance(s.get("claim_id"), str) and s.get("guarantee") in GUARANTEE_IDS
        if not ok:
            out.append({"claim_id": None, "state": "QUARANTINED"})
        elif n_valid < active:
            n_valid += 1
            out.append({"claim_id": s["claim_id"], "state": "ACTIVE"})
        elif n_valid < limit:
            n_valid += 1
            out.append({"claim_id": s["claim_id"], "state": "QUEUED"})
        else:
            out.append({"claim_id": s["claim_id"], "state": "UNACKNOWLEDGED"})
    return out
