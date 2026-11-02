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

from . import crypto as C
from . import provenance as P
from .access import AccessDenied, AuthService, Principal
from .chainlog import ChainLog
from .consent import ConsentLog
from .crypto import AuthError, CheckpointAuthority, CryptoUnavailable, hkdf, kdf, open_bytes, verify_checkpoints


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
        self.n = scrypt_n
        if meta.exists():
            m = json.loads(meta.read_text())
            self.n, self.key_id, self.format = m["n"], m.get("key_id", 0), 1 if m.get("cipher") == "teoo.crypto/1" else 2
            master = kdf(passphrase.encode(), bytes.fromhex(m["salt"]), n=m["n"])
            try:
                open_bytes(master, bytes.fromhex(m["check"]), b"teoo-vault-check")
            except AuthError:
                raise VaultError("WRONG_PASSPHRASE") from None
        else:
            salt = secrets.token_bytes(16)
            master = kdf(passphrase.encode(), salt, n=scrypt_n)
            self.key_id, self.format = 1, 2
            try:
                check = C.seal_bytes(master, b"ok", b"teoo-vault-check", key_id=self.key_id)
            except CryptoUnavailable:
                raise VaultError("CRYPTO_UNAVAILABLE") from None
            meta.write_text(json.dumps({"salt": salt.hex(), "n": scrypt_n, "check": check.hex(), "cipher": "teoo.crypto/2", "key_id": self.key_id}))
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

    def _seal(self, key: bytes, data: bytes, aad: bytes, key_id: int) -> bytes:
        try:
            return C.seal_bytes(key, data, aad, key_id=key_id)
        except CryptoUnavailable:
            raise VaultError("CRYPTO_UNAVAILABLE") from None
        except C.KeyExhausted:
            raise VaultError("KEY_EXHAUSTED") from None

    def _open(self, key: bytes, blob: bytes, aad: bytes) -> bytes:
        try:
            return open_bytes(key, blob, aad)
        except CryptoUnavailable:
            raise VaultError("CRYPTO_UNAVAILABLE") from None

    def _open_json(self, key: bytes, blob: bytes, aad: bytes) -> Any:
        return json.loads(self._open(key, blob, aad))

    def _seal_json(self, key: bytes, obj: Any, aad: bytes, key_id: int) -> bytes:
        return self._seal(key, json.dumps(obj, sort_keys=True, separators=(",", ":")).encode(), aad, key_id)

    def _identities(self) -> dict[str, dict]:
        f = self.root / "identity.enc"
        return self._open_json(self._idkey, f.read_bytes(), b"identity") if f.exists() else {}

    def _save_identities(self, d: dict[str, dict]) -> None:
        self._atomic("identity.enc", self._seal_json(self._idkey, d, b"identity", self.key_id))

    def _dek(self, subject: str) -> bytes:
        e = self.keystore.get(subject)
        if e is None:
            raise VaultError("UNKNOWN_SUBJECT")
        if e["state"] != "active":
            raise VaultError("KEY_DESTROYED")
        return self._open(self._wrap, bytes.fromhex(e["wrapped"]), subject.encode())

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
        self.keystore[pseudo] = {"state": "active", "wrapped": self._seal(self._wrap, secrets.token_bytes(32), pseudo.encode(), self.key_id).hex(), "gen": 1, "created_at": self.clock()}
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
        blob = self._seal_json(self._dek(subject), {"record": record, "raw_b64": base64.b64encode(raw).decode() if raw is not None else None}, f"{subject}|{record['record_id']}".encode(), self.keystore[subject].get("gen", 0))
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
            full = self._open_json(self._dek(subject), blob, f"{subject}|{record_id}".encode())
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

    def _digest_of(self, sk: dict) -> str:
        """The digest of a record's blob now: the one in its skeleton, or the newest re-encryption recorded in the ledger (the ledger is append-only, so a re-encryption is an entry, not an edit)."""
        d = sk["blob_digest"]
        for b in self.ledger.bodies():
            if b["type"] == "reseal" and b["record_id"] == sk["record_id"] and b["old_blob_digest"] == d:
                d = b["new_blob_digest"]
        return d

    # ------------------------------------------------------------------------------------------------ cryptographic status, migration and rotation
    def crypto_status(self, token: str) -> dict:
        """Every encrypted object of the vault by format, algorithm and key id: what is actually stored, not what was intended."""
        self.auth.require(token, "ledger.verify")
        counts: dict[str, int] = {}

        def note(kind: str, blob: bytes) -> None:
            i = C.blob_info(blob)
            k = f"{kind}: format {i['format']} {i['algorithm']} key {i['key_id']}"
            counts[k] = counts.get(k, 0) + 1
        for sub, e in sorted(self.keystore.items()):
            if e.get("wrapped"):
                note("wrapped subject key", bytes.fromhex(e["wrapped"]))
            for f in sorted(self._blob_dir(sub).glob("*.enc")) if self._blob_dir(sub).exists() else []:
                note("record blob", f.read_bytes())
        if (self.root / "identity.enc").exists():
            note("identity store", (self.root / "identity.enc").read_bytes())
        note("passphrase check", bytes.fromhex(json.loads((self.root / "vault.json").read_text())["check"]))
        return {"cipher": C.CIPHER_NAME, "vault_format": self.format, "master_key_id": self.key_id, "objects": counts, "legacy_objects": sum(v for k, v in counts.items() if "format 1" in k), "aead_available": C.have_aead()}

    def _reseal_blob(self, subject: str, record_id: str, old_dek: bytes, new_dek: bytes, new_gen: int) -> None:
        f = self._blob_dir(subject) / f"{record_id}.enc"
        old = f.read_bytes()
        aad = f"{subject}|{record_id}".encode()
        plain = self._open(old_dek, old, aad)  # an AuthError stops the whole operation: nothing is half-converted silently
        new = self._seal(new_dek, plain, aad, new_gen)
        if self._open(new_dek, new, aad) != plain:
            raise VaultError("RESEAL_VERIFY")
        tmp = f.with_suffix(".enc.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, new)
        finally:
            os.close(fd)
        os.replace(tmp, f)
        self.ledger.append({"type": "reseal", "subject": subject, "record_id": record_id, "old_blob_digest": hashlib.sha256(old).hexdigest(), "new_blob_digest": hashlib.sha256(new).hexdigest(), "at": self.clock()})

    def _rewrap(self, subject: str, new_wrap: bytes, new_key_id: int, dek: bytes, gen: int | None = None) -> None:
        e = self.keystore[subject]
        e["wrapped"] = self._seal(new_wrap, dek, subject.encode(), new_key_id).hex()
        if gen is not None:
            e["gen"] = gen

    def migrate(self, token: str, passphrase: str) -> dict:
        """Convert every legacy (format 1, not vetted) object to the vetted AEAD (format 2) under the same keys: the passphrase check, the identity store, the wrapped subject keys and the record blobs. Verified at the end
        by reading what is stored. A failed authentication stops the operation and leaves everything it had not yet converted as it was."""
        p = self.auth.require(token, "key.rotate")
        if not C.have_aead():
            raise self._deny(p, "key.migrate", "CRYPTO_UNAVAILABLE")
        m = json.loads((self.root / "vault.json").read_text())
        master = kdf(passphrase.encode(), bytes.fromhex(m["salt"]), n=m["n"])
        try:
            open_bytes(master, bytes.fromhex(m["check"]), b"teoo-vault-check")
        except AuthError:
            raise self._deny(p, "key.migrate", "WRONG_PASSPHRASE") from None
        done = {"wrapped_keys": 0, "record_blobs": 0, "identity_store": 0, "passphrase_check": 0}
        for sub, e in sorted(self.keystore.items()):
            if e.get("state") != "active":
                continue
            dek = self._open(self._wrap, bytes.fromhex(e["wrapped"]), sub.encode())
            if C.blob_info(bytes.fromhex(e["wrapped"]))["legacy"]:
                self._rewrap(sub, self._wrap, self.key_id, dek, e.get("gen", 1))
                self._save_keys()
                done["wrapped_keys"] += 1
            gen = e.get("gen", 1)
            for rid in sorted(self._present(sub)):
                f = self._blob_dir(sub) / f"{rid}.enc"
                if C.blob_info(f.read_bytes())["legacy"]:
                    self._reseal_blob(sub, rid, dek, dek, gen)
                    done["record_blobs"] += 1
        idf = self.root / "identity.enc"
        if idf.exists() and C.blob_info(idf.read_bytes())["legacy"]:
            self._save_identities(self._identities())
            done["identity_store"] = 1
        if m.get("cipher") != "teoo.crypto/2" or C.blob_info(bytes.fromhex(m["check"]))["legacy"]:
            self.key_id = self.key_id or 1
            m.update({"check": self._seal(master, b"ok", b"teoo-vault-check", self.key_id).hex(), "cipher": "teoo.crypto/2", "key_id": self.key_id})
            self._atomic("vault.json", json.dumps(m).encode())
            self.format = 2
            done["passphrase_check"] = 1
        left = self.crypto_status(token)["legacy_objects"]
        self.auth.log(p.user, "key.migrate", "ok" if not left else "partial", code=f"converted-{sum(done.values())}-left-{left}")
        return {"converted": done, "legacy_objects_left": left}

    def rotate_subject_key(self, token: str, subject: str) -> dict:
        """A new subject key; every blob of the subject re-encrypted under it; the old wrapped key removed from the key store (copies of the old key store elsewhere still hold it)."""
        p = self.auth.require(token, "key.rotate")
        e = self.keystore.get(subject)
        if e is None or e["state"] != "active":
            raise self._deny(p, "key.rotate", "UNKNOWN_SUBJECT", subject)
        old = self._dek(subject)
        new = secrets.token_bytes(32)
        gen = e.get("gen", 1) + 1
        rids = sorted(self._present(subject))
        for rid in rids:
            self._reseal_blob(subject, rid, old, new, gen)
        self._rewrap(subject, self._wrap, self.key_id, new, gen)
        self._save_keys()
        self.auth.log(p.user, "key.rotate", "ok", object_id=subject, code=f"gen-{gen}")
        return {"subject": subject, "generation": gen, "blobs_reencrypted": len(rids), "residual": "a copy of the key store or of the blobs taken before the rotation still holds the old key or the old ciphertext"}

    def rotate_master(self, token: str, passphrase: str, new_passphrase: str) -> dict:
        """A new passphrase salt and master key (key id + 1); the passphrase check, the identity store and every wrapped subject key re-encrypted under it. The operation is not atomic across files: it converts in an order
        that keeps the old key usable until the last step, and stops on any failure."""
        p = self.auth.require(token, "key.rotate")
        m = json.loads((self.root / "vault.json").read_text())
        old_master = kdf(passphrase.encode(), bytes.fromhex(m["salt"]), n=m["n"])
        try:
            open_bytes(old_master, bytes.fromhex(m["check"]), b"teoo-vault-check")
        except AuthError:
            raise self._deny(p, "key.rotate", "WRONG_PASSPHRASE") from None
        salt = secrets.token_bytes(16)
        new_master = kdf(new_passphrase.encode(), salt, n=m["n"])
        nw, ni, kid = hkdf(new_master, b"teoo/wrap"), hkdf(new_master, b"teoo/identity"), self.key_id + 1
        ids = self._identities()
        deks = {sub: self._dek(sub) for sub, e in self.keystore.items() if e["state"] == "active"}
        new_ids = self._seal_json(ni, ids, b"identity", kid) if ids or (self.root / "identity.enc").exists() else None
        wraps = {sub: self._seal(nw, dek, sub.encode(), kid).hex() for sub, dek in deks.items()}
        check = self._seal(new_master, b"ok", b"teoo-vault-check", kid)
        for sub, w in wraps.items():
            self.keystore[sub]["wrapped"] = w
        self._save_keys()
        if new_ids is not None:
            self._atomic("identity.enc", new_ids)
        self._atomic("vault.json", json.dumps({**m, "salt": salt.hex(), "check": check.hex(), "cipher": "teoo.crypto/2", "key_id": kid}).encode())
        self._wrap, self._idkey, self.key_id, self.format = nw, ni, kid, 2
        self.auth.log(p.user, "key.rotate", "ok", code=f"master-key-id-{kid}")
        return {"master_key_id": kid, "wrapped_keys": len(wraps), "identity_store": new_ids is not None}

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
            elif hashlib.sha256(f.read_bytes()).hexdigest() != self._digest_of(b):
                out.append(f"{b['record_id']}: the encrypted blob does not match its digest")
            else:
                try:
                    full = self._open_json(self._dek(b["subject"]), f.read_bytes(), f"{b['subject']}|{b['record_id']}".encode())
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
