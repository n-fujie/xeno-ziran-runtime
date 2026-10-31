"""The local vault: where records about people would be kept, if they were. Nothing here has stored a human measurement.

Design (what is separated, encrypted, retained and destroyed):

* **Identity is separated from observation.** ``identity.enc`` (encrypted with an identity key) maps a random subject pseudonym to the identity; everything else (blobs, ledger, consent, audit) refers to the pseudonym only.
* **Observation data are encrypted per subject.** A record and its raw original are sealed with a subject key (DEK); the DEK is wrapped by a key derived from the vault passphrase. The ledger holds a *skeleton* of each record
  (ids, digests, classes, kinds, lineage, no payload, no creator, no source description) so that it can stay after the data are gone.
* **Deletion is crypto-shredding plus removal.** ``delete_subject`` removes the encrypted blobs (overwritten, then unlinked), destroys the subject's wrapped DEK, removes the identity entry, revokes the consents and appends a
  tombstone with non-identifying verification data. ``verify_deletion`` checks each of these and reports what was retained and the residual risks (copies of the key store taken before deletion; the file system's own copies).
* **Every operation names the permission it needs, checks the consent for its purpose, and is audited** (identifiers and codes only).

Limits: a passphrase-derived master key held in this process's memory, no hardware protection, no secure deletion guarantee on SSDs or journalling file systems, backups outside the vault are not known to it unless listed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import provenance as P
from .access import AccessDenied, AuthService, Principal
from .chainlog import ChainLog
from .consent import ConsentLog
from .crypto import AuthError, CheckpointAuthority, hkdf, kdf, open_bytes, open_json, seal_bytes, seal_json, verify_checkpoints


class VaultError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def skeleton(rec: dict, subject: str, blob_digest: str, consent_id: str) -> dict:
    """What the ledger keeps of a record: nothing that identifies a person and nothing of the data themselves."""
    return {"type": "record", "subject": subject, "record_id": rec["record_id"], "record_digest": rec["record_digest"], "provenance": rec["provenance"], "kind": rec["kind"], "lineage_classes": rec["lineage_classes"],
            "derived_from": rec["derived_from"], "raw_digest": rec["raw"]["digest"], "blob_digest": blob_digest, "consent_id": consent_id, "created_at": rec["created_at"]}


class Vault:
    def __init__(self, root: Path, auth: AuthService, passphrase: str, *, clock: Callable[[], float] = time.time, scrypt_n: int = 2**14):
        self.root, self.auth, self.clock = Path(root), auth, clock
        self.root.mkdir(parents=True, exist_ok=True)
        meta = self.root / "vault.json"
        if meta.exists():
            m = json.loads(meta.read_text())
            master = kdf(passphrase.encode(), bytes.fromhex(m["salt"]), n=m["n"])
            try:
                open_bytes(master, bytes.fromhex(m["check"]), b"teoo-vault-check")
            except AuthError:
                raise VaultError("WRONG_PASSPHRASE") from None
        else:
            salt = secrets.token_bytes(16)
            master = kdf(passphrase.encode(), salt, n=scrypt_n)
            meta.write_text(json.dumps({"salt": salt.hex(), "n": scrypt_n, "check": seal_bytes(master, b"ok", b"teoo-vault-check").hex(), "cipher": "teoo.crypto/1"}))
            os.chmod(meta, 0o600)
        self._wrap, self._idkey = hkdf(master, b"teoo/wrap"), hkdf(master, b"teoo/identity")
        del master
        self.consents = ConsentLog(self.root / "consent.jsonl", clock)
        self.ledger = ChainLog(self.root / "ledger.jsonl")
        self.checkpoints = ChainLog(self.root / "checkpoints.jsonl")
        (self.root / "blobs").mkdir(exist_ok=True)
        self.keystore: dict[str, dict] = json.loads((self.root / "keystore.json").read_text()) if (self.root / "keystore.json").exists() else {}

    # ------------------------------------------------------------------------------------------------ storage helpers
    def _atomic(self, name: str, data: bytes) -> None:
        tmp = self.root / (name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        os.replace(tmp, self.root / name)

    def _save_keys(self) -> None:
        self._atomic("keystore.json", json.dumps(self.keystore, sort_keys=True).encode())

    def _identities(self) -> dict[str, dict]:
        f = self.root / "identity.enc"
        return open_json(self._idkey, f.read_bytes(), b"identity") if f.exists() else {}

    def _save_identities(self, d: dict[str, dict]) -> None:
        self._atomic("identity.enc", seal_json(self._idkey, d, b"identity"))

    def _dek(self, subject: str) -> bytes:
        e = self.keystore.get(subject)
        if e is None:
            raise VaultError("UNKNOWN_SUBJECT")
        if e["state"] != "active":
            raise VaultError("KEY_DESTROYED")
        return open_bytes(self._wrap, bytes.fromhex(e["wrapped"]), subject.encode())

    def _blob_dir(self, subject: str) -> Path:
        return self.root / "blobs" / subject

    def _deny(self, p: Principal, action: str, code: str, obj: str = "") -> VaultError:
        self.auth.log(p.user, action, "denied", object_id=obj, code=code)
        return VaultError(code)

    # ------------------------------------------------------------------------------------------------ subjects and consent
    def enroll_subject(self, token: str, identity: dict[str, Any]) -> str:
        p = self.auth.require(token, "subject.enroll")
        if not identity:
            raise self._deny(p, "subject.enroll", "NO_IDENTITY")
        pseudo = "sub-" + secrets.token_hex(8)
        ids = self._identities()
        ids[pseudo] = identity
        self._save_identities(ids)
        self.keystore[pseudo] = {"state": "active", "wrapped": seal_bytes(self._wrap, secrets.token_bytes(32), pseudo.encode()).hex(), "created_at": self.clock()}
        self._save_keys()
        self.auth.log(p.user, "subject.enroll", "ok", object_id=pseudo)
        return pseudo

    def record_consent(self, token: str, subject: str, purposes: list[str], data_classes: list[str], *, expires_at: float | None = None, protocol_id: str | None = None) -> str:
        p = self.auth.require(token, "consent.record")
        if subject not in self.keystore or self.keystore[subject]["state"] != "active":
            raise self._deny(p, "consent.record", "UNKNOWN_SUBJECT", subject)
        cid = self.consents.grant(subject, purposes, data_classes, expires_at=expires_at, protocol_id=protocol_id)
        self.auth.log(p.user, "consent.grant", "ok", object_id=cid)
        return cid

    def revoke_consent(self, token: str, subject: str, consent_id: str, reason: str = "") -> None:
        p = self.auth.require(token, "consent.revoke")
        self.consents.revoke(subject, consent_id, reason)
        self.auth.log(p.user, "consent.revoke", "ok", object_id=consent_id)

    def read_identity(self, token: str, subject: str) -> dict:
        p = self.auth.require(token, "identity.read")
        ids = self._identities()
        if subject not in ids:
            raise self._deny(p, "identity.read", "UNKNOWN_SUBJECT", subject)
        self.auth.log(p.user, "identity.read", "ok", object_id=subject)
        return ids[subject]

    # ------------------------------------------------------------------------------------------------ records
    def _present(self, subject: str) -> dict[str, dict]:
        deleted = {b["subject"] for b in self.ledger.bodies() if b["type"] == "tombstone"}
        return {b["record_id"]: b for b in self.ledger.bodies() if b["type"] == "record" and b["subject"] == subject and subject not in deleted}

    def store_record(self, token: str, subject: str, record: dict, raw: bytes | None = None, purpose: str = "protocol-execution") -> str:
        p = self.auth.require(token, "data.write")
        cons = self.consents.active(subject, purpose, "observation")
        if subject not in self.keystore or self.keystore[subject]["state"] != "active":
            raise self._deny(p, "data.write", "UNKNOWN_SUBJECT", subject)
        if cons is None:
            raise self._deny(p, "data.write", "NO_CONSENT", subject)
        if P.verify_record(record):
            raise self._deny(p, "data.write", "RECORD_INVALID", subject)
        if (record["raw"]["origin"] == "supplied") != (raw is not None) or (raw is not None and hashlib.sha256(raw).hexdigest() != record["raw"]["digest"]):
            raise self._deny(p, "data.write", "RAW_MISMATCH", subject)
        known = {b["record_id"]: b["record_digest"] for b in self.ledger.bodies() if b["type"] == "record"}
        if any(known.get(d["record_id"]) != d["record_digest"] for d in record["derived_from"]):
            raise self._deny(p, "data.write", "PARENT_UNKNOWN", subject)
        if record["record_id"] in known:
            raise self._deny(p, "data.write", "ALREADY_RECORDED", subject)
        blob = seal_json(self._dek(subject), {"record": record, "raw_b64": base64.b64encode(raw).decode() if raw is not None else None}, f"{subject}|{record['record_id']}".encode())
        d = self._blob_dir(subject)
        d.mkdir(parents=True, exist_ok=True)
        fd = os.open(d / f"{record['record_id']}.enc", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, blob)
        finally:
            os.close(fd)
        self.ledger.append(skeleton(record, subject, hashlib.sha256(blob).hexdigest(), cons))
        self.auth.log(p.user, "data.write", "ok", object_id=record["record_id"])
        return record["record_id"]

    def read_record(self, token: str, subject: str, record_id: str, purpose: str = "analysis") -> dict:
        p = self.auth.require(token, "data.read")
        if self.consents.active(subject, purpose, "observation") is None:
            raise self._deny(p, "data.read", "NO_CONSENT", subject)
        sk = self._present(subject).get(record_id)
        if sk is None:
            raise self._deny(p, "data.read", "NOT_FOUND", record_id)
        blob = (self._blob_dir(subject) / f"{record_id}.enc").read_bytes()
        try:
            full = open_json(self._dek(subject), blob, f"{subject}|{record_id}".encode())
        except AuthError:
            raise self._deny(p, "data.read", "INTEGRITY", record_id) from None
        if P.verify_record(full["record"]) or full["record"]["record_digest"] != sk["record_digest"]:
            raise self._deny(p, "data.read", "INTEGRITY", record_id)
        self.auth.log(p.user, "data.read", "ok", object_id=record_id)
        return {"record": full["record"], "raw": base64.b64decode(full["raw_b64"]) if full["raw_b64"] else None}

    # ------------------------------------------------------------------------------------------------ deletion
    def delete_subject(self, token: str, subject: str, reason_code: str = "subject-request", known_backups: tuple[Path, ...] = ()) -> dict:
        p = self.auth.require(token, "subject.delete")
        e = self.keystore.get(subject)
        if e is None or e["state"] != "active":
            raise self._deny(p, "subject.delete", "UNKNOWN_SUBJECT", subject)
        present = self._present(subject)
        removed = []
        d = self._blob_dir(subject)
        for f in sorted(d.glob("*.enc")) if d.exists() else []:
            size = f.stat().st_size
            with open(f, "r+b") as fh:  # overwrite, then unlink (best effort: the file system may keep copies)
                fh.write(secrets.token_bytes(size))
                fh.flush()
                os.fsync(fh.fileno())
            f.unlink()
            removed.append(f.stem)
        if d.exists():
            d.rmdir()
        wrapped_id = hashlib.sha256(bytes.fromhex(e["wrapped"])).hexdigest()[:16]
        self.keystore[subject] = {"state": "destroyed", "wrapped": None, "destroyed_at": self.clock(), "wrapped_id": wrapped_id}
        self._save_keys()
        ids = self._identities()
        had_identity = ids.pop(subject, None) is not None
        self._save_identities(ids)
        for b in self.consents.history(subject):
            if b["type"] == "grant" and self.consents.active(subject, b["purposes"][0], b["data_classes"][0]) == b["id"]:
                self.consents.revoke(subject, b["id"], "subject-deleted")
        deletion_id = "del-" + secrets.token_hex(6)
        self.ledger.append({"type": "tombstone", "deletion_id": deletion_id, "subject": subject, "record_ids": sorted(present), "blobs_removed": len(removed), "key_destroyed": True, "identity_removed": had_identity,
                            "reason_code": reason_code[:40], "at": self.clock()})
        self.auth.log(p.user, "subject.delete", "ok", object_id=deletion_id)
        res = {"deletion_id": deletion_id, "subject": subject, "records": sorted(present), "blobs_removed": len(removed), "key_destroyed": True, "identity_removed": had_identity,
               "retained": ["ledger skeleton entries of the deleted records (ids, digests, classes, kinds, lineage; no payload, no identity)", "a tombstone (non-identifying verification data)",
                            "audit entries (user names of staff, the subject's pseudonym, codes)", "consent entries (the pseudonym, purposes, revocations)", "the pseudonym itself (no longer linked to an identity in this vault)"]}
        res["verification"] = self.verify_deletion(token, subject, known_backups)
        return res

    def verify_deletion(self, token: str, subject: str, known_backups: tuple[Path, ...] = ()) -> dict:
        self.auth.require(token, "ledger.verify")
        e = self.keystore.get(subject, {})
        checks = {"blob_directory_absent": not self._blob_dir(subject).exists(),
                  "key_destroyed_in_keystore": e.get("state") == "destroyed" and e.get("wrapped") is None,
                  "identity_entry_absent": subject not in self._identities(),
                  "tombstone_present": any(b["type"] == "tombstone" and b["subject"] == subject for b in self.ledger.bodies()),
                  "no_active_consent": all(self.consents.active(subject, pu, dc) is None for pu in ("protocol-execution", "analysis", "figure-export", "external-transmission", "reproduction-check") for dc in ("observation", "media", "reconstruction")),
                  "decryption_impossible": self._cannot_decrypt(subject),
                  "ledger_chain_intact": not self.ledger.verify() and not self.auth.audit.verify() and not self.consents.log.verify()}
        residual = []
        wid = e.get("wrapped_id")
        for b in known_backups:
            if b.exists() and wid and any(wid == hashlib.sha256(bytes.fromhex(v["wrapped"])).hexdigest()[:16] for v in json.loads(b.read_text()).values() if v.get("wrapped")):
                residual.append(f"a known backup ({b.name}) still holds the wrapped key of this subject: the data are still decryptable from it together with the passphrase")
        residual.append("copies made by the file system, snapshots or backups that are not listed are not known to the vault")
        return {"checks": checks, "all_passed": all(checks.values()) and not [r for r in residual if r.startswith("a known backup")], "residual_risks": residual}

    def _cannot_decrypt(self, subject: str) -> bool:
        try:
            self._dek(subject)
        except VaultError:
            return True
        return False

    # ------------------------------------------------------------------------------------------------ integrity and checkpoints
    def verify_integrity(self, token: str) -> list[str]:
        self.auth.require(token, "ledger.verify")
        out = [f"ledger: {x}" for x in self.ledger.verify()] + [f"audit: {x}" for x in self.auth.audit.verify()] + [f"consent: {x}" for x in self.consents.log.verify()]
        deleted = {b["subject"] for b in self.ledger.bodies() if b["type"] == "tombstone"}
        for b in self.ledger.bodies():
            if b["type"] != "record":
                continue
            f = self._blob_dir(b["subject"]) / f"{b['record_id']}.enc"
            if b["subject"] in deleted:
                if f.exists():
                    out.append(f"{b['record_id']}: a blob remains after the subject's deletion")
                continue
            if not f.exists():
                out.append(f"{b['record_id']}: the encrypted blob is missing")
            elif hashlib.sha256(f.read_bytes()).hexdigest() != b["blob_digest"]:
                out.append(f"{b['record_id']}: the encrypted blob does not match its digest")
            else:
                try:
                    full = open_json(self._dek(b["subject"]), f.read_bytes(), f"{b['subject']}|{b['record_id']}".encode())
                    if P.verify_record(full["record"]) or full["record"]["record_digest"] != b["record_digest"]:
                        out.append(f"{b['record_id']}: the record does not match its skeleton or its own digest")
                    if full["raw_b64"] is not None and hashlib.sha256(base64.b64decode(full["raw_b64"])).hexdigest() != b["raw_digest"]:
                        out.append(f"{b['record_id']}: the raw original does not match its digest")
                except (AuthError, VaultError):
                    out.append(f"{b['record_id']}: the blob cannot be authenticated")
        return out

    def checkpoint(self, token: str, authority: CheckpointAuthority) -> dict:
        p = self.auth.require(token, "checkpoint.sign")
        cp = authority.sign({"seq": len(self.ledger.entries), "ledger_head": self.ledger.head(), "audit_seq": len(self.auth.audit.entries), "audit_head": self.auth.audit.head(),
                             "consent_seq": len(self.consents.log.entries), "consent_head": self.consents.log.head(), "at": self.clock()})
        self.checkpoints.append(cp)
        self.auth.log(p.user, "checkpoint.sign", "ok", object_id=f"seq-{cp['seq']}")
        return cp

    def verify_checkpoints(self, token: str, anchor: str) -> list[str]:
        self.auth.require(token, "ledger.verify")
        cps = self.checkpoints.bodies()
        out = verify_checkpoints(cps, anchor)
        for i, cp in enumerate(cps):
            if cp["seq"] > len(self.ledger.entries) or (cp["seq"] and self.ledger.entries[cp["seq"] - 1]["hash"] != cp["ledger_head"]):
                out.append(f"checkpoint {i}: the ledger no longer matches what was signed (history rewritten or shortened)")
            if cp["audit_seq"] > len(self.auth.audit.entries) or (cp["audit_seq"] and self.auth.audit.entries[cp["audit_seq"] - 1]["hash"] != cp["audit_head"]):
                out.append(f"checkpoint {i}: the audit log no longer matches what was signed")
        return out


__all__ = ["Vault", "VaultError", "AccessDenied", "skeleton"]
