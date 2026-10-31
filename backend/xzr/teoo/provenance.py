"""Provenance Registry: sealed records, derivation, the append-only ledger, the raw store.

Every record carries a provenance class and a kind, and both are inside the record's digest. A record is never changed: a conversion is a *new* record
whose ``derived_from`` names the parents (id and digest) and whose ``lineage_classes`` is the union of everything upstream, so a SYNTHETIC ancestry cannot be
dropped by a derivation. The rules for which class a derived record may have are in :func:`check_class_rules`; there is no function that changes the class of an
existing record, and :func:`verify_record` fails when a stored record's class or content differs from its digest.

What this protects, and what it does not (``PROTECTIONS``): digests, the hash chain and an exported checkpoint detect a change; they do not prevent one by someone
who can rewrite the whole ledger and recompute every hash, and they say nothing about whether a MEASURED record was measured: that is a declaration of its source.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .schema import Issue, validate_schema


class Provenance(StrEnum):
    MEASURED = "MEASURED"
    SYNTHETIC = "SYNTHETIC"
    RECONSTRUCTED_ESTIMATE = "RECONSTRUCTED_ESTIMATE"
    CONCEPTUAL = "CONCEPTUAL"


class Kind(StrEnum):  # a separate axis: what the record is, not where it comes from
    REFERENCE_STATE = "REFERENCE_STATE"
    OBSERVATION = "OBSERVATION"
    ESTIMATE = "ESTIMATE"
    RECONSTRUCTION = "RECONSTRUCTION"


KINDS_FOR = {  # which kinds a provenance class may carry (a measured reference state does not exist: a reference state is a model's state)
    Provenance.MEASURED: {Kind.OBSERVATION},
    Provenance.SYNTHETIC: {Kind.OBSERVATION, Kind.REFERENCE_STATE, Kind.ESTIMATE, Kind.RECONSTRUCTION},
    Provenance.RECONSTRUCTED_ESTIMATE: {Kind.ESTIMATE, Kind.RECONSTRUCTION},
    Provenance.CONCEPTUAL: {Kind.REFERENCE_STATE},
}
MEASURED_SOURCE_KINDS = ("device", "instrument", "manual-entry", "file-import")
PROCESSING_THAT_KEEPS_MEASURED = ("unit-conversion", "filtering", "resampling-without-interpolation", "segmentation", "relabelling")

PROTECTIONS = {
    "implemented": [
        "content digest of every record, covering its provenance class, kind, payload, parents and history",
        "digest of the raw original (content-addressed, write-once raw store)",
        "append-only ledger with a hash chain (any change of an earlier entry breaks the later hashes)",
        "exportable checkpoint (sequence number and head hash) to be kept outside the ledger",
        "class rules for derivation, lineage classes propagated from the parents",
        "ingestion without a declared provenance is quarantined, never registered as MEASURED",
    ],
    "not_implemented": [
        "digital signatures (nobody vouches for a record; a digest is not a signature)",
        "access control and authentication of who may write or read a record",
        "consent records, deletion on request, separation of personal identifiers from measurements",
        "encryption at rest",
        "a trusted external timestamp or a transparency log (the checkpoint must be stored elsewhere by the researcher)",
        "verification that a MEASURED record was really measured by the declared device",
    ],
}


class ProvenanceError(ValueError):
    def __init__(self, issues: list[Issue]):
        super().__init__("; ".join(f"{i.field}: {i.message}" for i in issues))
        self.issues = issues


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def digest_of(obj: Any) -> str:
    return sha256(canonical(obj))


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _body(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in ("record_digest", "record_id")}


def record_digest(rec: dict) -> str:
    return digest_of(_body(rec))


def _enum(cls: Any, v: Any, field: str) -> Any:
    try:
        return cls(v)
    except ValueError:
        raise ProvenanceError([Issue(field, "UNDECLARED" if v in (None, "", "UNKNOWN") else "BAD_VALUE", f"{field} must be one of {[e.value for e in cls]} (got {v!r}); a record without a declared {field} is not registered")]) from None


def check_class_rules(new: Provenance, kind: Kind, parents: list[dict], transformations: list[dict], source: dict) -> list[Issue]:
    out: list[Issue] = []
    if kind not in KINDS_FOR[new]:
        out.append(Issue("kind", "KIND_NOT_ALLOWED", f"a {new.value} record cannot be of kind {kind.value} (allowed: {sorted(k.value for k in KINDS_FOR[new])})"))
    lineage = {p for par in parents for p in par.get("lineage_classes", [])}
    if new is Provenance.MEASURED:
        if parents:
            if not all(p["provenance"] == "MEASURED" for p in parents):
                out.append(Issue("provenance", "CLASS_CHANGE_FORBIDDEN", "a record derived from non-MEASURED parents cannot be MEASURED"))
            if lineage - {"MEASURED"}:
                out.append(Issue("lineage_classes", "TAINTED_LINEAGE", f"upstream classes {sorted(lineage - {'MEASURED'})} cannot be dropped into MEASURED"))
            bad = [t for t in transformations if t.get("method") not in PROCESSING_THAT_KEEPS_MEASURED or t.get("preserves_provenance") is not True]
            if bad or not transformations:
                out.append(Issue("transformations", "PROCESSING_NOT_ALLOWED", f"a derived MEASURED record needs transformations among {PROCESSING_THAT_KEEPS_MEASURED}, each declared preserves_provenance=true"))
        elif source.get("kind") not in MEASURED_SOURCE_KINDS or not source.get("declared_by"):
            out.append(Issue("source", "MEASURED_SOURCE_UNDECLARED", f"a MEASURED record declares its source: source.kind in {MEASURED_SOURCE_KINDS} and source.declared_by (who vouches for it)"))
    elif new is Provenance.SYNTHETIC:
        if any(p["provenance"] != "SYNTHETIC" for p in parents):
            out.append(Issue("provenance", "SYNTHETIC_PARENTS_ONLY", "a SYNTHETIC record is derived only from SYNTHETIC records"))
    elif new is Provenance.CONCEPTUAL and parents and any(p["provenance"] != "CONCEPTUAL" for p in parents):
        out.append(Issue("provenance", "CONCEPTUAL_PARENTS_ONLY", "a CONCEPTUAL record is derived only from CONCEPTUAL records"))
    return out


def seal(payload: dict, *, provenance: Any, kind: Any, creator: dict, source: dict, raw_bytes: bytes | None = None, raw_media_type: str = "application/json", parents: list[dict] | None = None,
         transformations: list[dict] | None = None, created_at: str | None = None, schema: str = "teoo.observation/1", validation: dict | None = None, extra: dict | None = None) -> dict:
    """Make a sealed record. Raises :class:`ProvenanceError` (with the issues) when the provenance or kind is missing or the class rules are broken: nothing is registered by default."""
    prov, kd = _enum(Provenance, provenance, "provenance"), _enum(Kind, kind, "kind")
    parents = parents or []
    transformations = transformations or []
    issues = check_class_rules(prov, kd, parents, transformations, source)
    if not creator.get("name"):
        issues.append(Issue("creator", "CREATOR_MISSING", "the creator or generating source is named"))
    if not source.get("description"):
        issues.append(Issue("source", "SOURCE_MISSING", "the source (device, file, generator, researcher) is described"))
    if issues:
        raise ProvenanceError(issues)
    raw = raw_bytes if raw_bytes is not None else canonical(payload)
    rec = {"schema": schema, "provenance": prov.value, "kind": kd.value, "creator": creator, "source": source, "created_at": created_at or now_iso(),
           "raw": {"digest": sha256(raw), "bytes": len(raw), "media_type": raw_media_type, "origin": "supplied" if raw_bytes is not None else "generated-from-payload"},
           "payload": payload, "derived_from": [{"record_id": p["record_id"], "record_digest": p["record_digest"]} for p in parents],
           "lineage_classes": sorted({prov.value} | {p for par in parents for p in par.get("lineage_classes", [par["provenance"]])}), "transformations": transformations,
           "validation": validation or {"ok": True, "issues": []}}
    if extra:
        rec.update(extra)
    rec["record_digest"] = record_digest(rec)
    rec["record_id"] = "rec-" + rec["record_digest"][:24]
    return rec


def derive(parents: list[dict], *, payload: dict, provenance: Any, kind: Any, creator: dict, source: dict, transformations: list[dict], created_at: str | None = None, extra: dict | None = None) -> dict:
    """A conversion is a new record that names its parents; the parents are not touched. The class rules of :func:`check_class_rules` apply."""
    if not parents:
        raise ProvenanceError([Issue("derived_from", "NO_PARENT", "a derived record names at least one parent")])
    return seal(payload, provenance=provenance, kind=kind, creator=creator, source=source, parents=parents, transformations=transformations, created_at=created_at, extra=extra)


def verify_record(rec: Any, lookup: dict[str, dict] | None = None, raw: RawStore | None = None) -> list[Issue]:
    """Integrity and rules of one stored record. ``lookup`` maps record ids to the parents (when given, parents and lineage are checked)."""
    issues = validate_schema(rec)
    if issues:
        return issues
    out: list[Issue] = []
    if record_digest(rec) != rec["record_digest"]:
        out.append(Issue("record_digest", "DIGEST_MISMATCH", "the record's content (including its provenance class) does not match its digest: it was changed after sealing"))
    if rec["record_id"] != "rec-" + rec["record_digest"][:24]:
        out.append(Issue("record_id", "ID_MISMATCH", "the record id is not derived from its digest"))
    try:
        prov, kd = Provenance(rec["provenance"]), Kind(rec["kind"])
    except ValueError:
        return [*out, Issue("provenance", "BAD_VALUE", "unknown provenance class or kind")]
    if prov.value not in rec["lineage_classes"]:
        out.append(Issue("lineage_classes", "LINEAGE_INCONSISTENT", "the record's own class is not in its lineage"))
    parents: list[dict] = []
    if lookup is not None:
        for ref in rec["derived_from"]:
            p = lookup.get(ref["record_id"])
            if p is None:
                out.append(Issue("derived_from", "PARENT_MISSING", f"parent {ref['record_id']} is not in the ledger"))
            elif p["record_digest"] != ref["record_digest"]:
                out.append(Issue("derived_from", "PARENT_DIGEST_MISMATCH", f"parent {ref['record_id']} differs from the one that was derived from"))
            else:
                parents.append(p)
        if len(parents) == len(rec["derived_from"]):
            want = sorted({prov.value} | {c for p in parents for c in p["lineage_classes"]})
            if want != rec["lineage_classes"]:
                out.append(Issue("lineage_classes", "LINEAGE_INCONSISTENT", f"lineage_classes should be {want} given the parents"))
            out += [i for i in check_class_rules(prov, kd, parents, rec["transformations"], rec["source"])]
    else:
        out += [i for i in check_class_rules(prov, kd, [], rec["transformations"], rec["source"]) if i.code == "KIND_NOT_ALLOWED"]
    if raw is not None and rec["raw"].get("origin") == "supplied":
        if not raw.has(rec["raw"]["digest"]):
            out.append(Issue("raw", "RAW_MISSING", "the raw original is not in the raw store"))
        elif not raw.verify(rec["raw"]["digest"]):
            out.append(Issue("raw", "RAW_CORRUPT", "the stored raw original does not match its digest"))
    return out


class RawStore:
    """Content-addressed, write-once store of raw originals (a file per sha256). Stores bytes exactly as received; nothing here parses or edits them."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else None
        self._mem: dict[str, bytes] = {}
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        d = sha256(data)
        if self.root:
            p = self.root / d
            if p.exists():
                if sha256(p.read_bytes()) != d:
                    raise ValueError("the stored raw file does not match its digest")
            else:
                p.write_bytes(data)
                p.chmod(0o444)
        else:
            self._mem.setdefault(d, data)
        return d

    def has(self, d: str) -> bool:
        return (self.root / d).exists() if self.root else d in self._mem

    def get(self, d: str) -> bytes:
        return (self.root / d).read_bytes() if self.root else self._mem[d]

    def verify(self, d: str) -> bool:
        return self.has(d) and sha256(self.get(d)) == d


class Ledger:
    """Append-only ledger of sealed records with a hash chain. There is no update or delete. ``path=None`` keeps it in memory."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.entries: list[dict] = []
        if self.path and self.path.exists():
            self.entries = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    @staticmethod
    def _entry_hash(seq: int, prev: str, rec_digest: str) -> str:
        return sha256(f"{seq}|{prev}|{rec_digest}".encode())

    def head(self) -> str:
        return self.entries[-1]["entry_hash"] if self.entries else "0" * 64

    def index(self) -> dict[str, dict]:
        return {e["record"]["record_id"]: e["record"] for e in self.entries}

    def append(self, rec: dict, raw: RawStore | None = None) -> dict:
        issues = verify_record(rec, self.index(), raw)
        if issues:
            raise ProvenanceError(issues)
        if rec["record_id"] in self.index():
            raise ProvenanceError([Issue("record_id", "ALREADY_RECORDED", "a record is never rewritten; derive a new record instead")])
        seq = len(self.entries)
        e = {"schema": "teoo.ledger-entry/1", "seq": seq, "prev_hash": self.head(), "record": rec, "entry_hash": self._entry_hash(seq, self.head(), rec["record_digest"])}
        self.entries.append(e)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n")
        return e

    def verify(self, raw: RawStore | None = None) -> list[Issue]:
        out: list[Issue] = []
        seen: dict[str, dict] = {}
        prev = "0" * 64
        for i, e in enumerate(self.entries):
            if e.get("seq") != i or e.get("prev_hash") != prev:
                out.append(Issue(f"entry[{i}]", "CHAIN_BROKEN", "sequence or previous hash does not follow"))
            if e.get("entry_hash") != self._entry_hash(i, prev, e["record"].get("record_digest", "")):
                out.append(Issue(f"entry[{i}]", "ENTRY_HASH_MISMATCH", "the entry hash does not match the record digest it chains"))
            out += [Issue(f"entry[{i}].{x.field}", x.code, x.message) for x in verify_record(e["record"], seen, raw)]
            seen[e["record"]["record_id"]] = e["record"]
            prev = e.get("entry_hash", "")
        return out

    def checkpoint(self) -> dict:
        return {"seq": len(self.entries), "head_hash": self.head(), "at": now_iso(), "note": "store this outside the ledger; without an external copy a rewritten ledger cannot be told from the original"}

    def verify_checkpoint(self, cp: dict) -> list[Issue]:
        if cp["seq"] > len(self.entries):
            return [Issue("checkpoint", "LEDGER_SHORTER", "the ledger is shorter than the checkpoint: entries were removed")]
        head = self.entries[cp["seq"] - 1]["entry_hash"] if cp["seq"] else "0" * 64
        return [] if head == cp["head_hash"] else [Issue("checkpoint", "CHECKPOINT_MISMATCH", "the ledger's entry at the checkpoint differs from the checkpoint: the history was rewritten")]


class Quarantine:
    """What could not be registered (undeclared provenance, blocking errors): kept with its raw digest and the issues. It is not part of the ledger and is never evidence."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, raw_bytes: bytes, issues: list[Issue], note: str = "") -> dict:
        item = {"raw_digest": sha256(raw_bytes), "bytes": len(raw_bytes), "issues": [i.to_dict() for i in issues], "note": note, "at": now_iso()}
        self.items.append(item)
        return item
