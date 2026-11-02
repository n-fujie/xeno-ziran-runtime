"""TEOO safety: access control, consent, encryption, deletion, integrity, signed checkpoints, separation of identity, no leakage. Each threat of ``safety.THREATS`` has tests here."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest

from xzr.teoo import crypto as C
from xzr.teoo import provenance as P
from xzr.teoo import redact as RD
from xzr.teoo import safety as SF
from xzr.teoo.access import ROLES, AccessDenied, AuthService
from xzr.teoo.consent import ConsentLog
from xzr.teoo.vault import Vault, VaultError

N = 2**10  # a small scrypt cost for the tests (the production default is 2**14)
CANARY_NAME, CANARY_MAIL, CANARY_DATA = "Zzyzx Canarius-Quill", "zzyzx.canary@example.invalid", "CANARY-DATA-7731"
PASS_S, PASS_R, PASS_V = "steward-password-001", "researcher-pass-002", "vault passphrase 003!"


class Clock:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture()
def env(tmp_path):
    clock = Clock()
    auth = AuthService(tmp_path / "auth", clock=clock, scrypt_n=N, token_ttl=600, lock_s=300)
    auth.add_user("stew", PASS_S, "steward")
    steward = auth.login("stew", PASS_S)
    auth.add_user("res", PASS_R, "researcher", by=auth.authenticate(steward))
    auth.add_user("rev", "reviewer-pass-004", "reviewer", by=auth.authenticate(steward))
    vault = Vault(tmp_path / "vault", auth, PASS_V, clock=clock, scrypt_n=N)
    return {"dir": tmp_path, "clock": clock, "auth": auth, "vault": vault, "steward": steward, "res": auth.login("res", PASS_R), "rev": auth.login("rev", "reviewer-pass-004")}


def record(n: int = 1, canary: str = CANARY_DATA):
    return P.seal({"series": [1.5, 2.5, n], "note_for_test": canary}, provenance="SYNTHETIC", kind="OBSERVATION", creator={"name": "gen"}, source={"kind": "generator", "description": "test generator", "declared_by": "t"}, raw_bytes=f"raw-{n}-{canary}".encode(),
                  created_at="2026-01-01T00:00:00.000000Z")


def enrolled(env, purposes=("protocol-execution", "analysis")):
    v = env["vault"]
    sub = v.enroll_subject(env["steward"], {"name": CANARY_NAME, "email": CANARY_MAIL})
    cid = v.record_consent(env["steward"], sub, list(purposes), ["observation"])
    return sub, cid


def store(env, sub, n=1):
    rec = record(n)
    env["vault"].store_record(env["res"], sub, rec, rec_raw(n))
    return rec


def rec_raw(n: int, canary: str = CANARY_DATA) -> bytes:
    return f"raw-{n}-{canary}".encode()


def all_files_text(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


# ---------------------------------------------------------------------------------------------------- crypto parts
def test_the_key_derivation_matches_the_rfc_5869_test_vector():
    out = C.hkdf(bytes.fromhex("0b" * 22), bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"), 42, bytes.fromhex("000102030405060708090a0b0c"))
    assert out.hex() == "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"


def test_authenticated_encryption_roundtrips_and_detects_any_change():
    k, pt = b"k" * 32, b"the quick brown fox" * 50
    blob = C.seal_bytes(k, pt, b"aad")
    assert C.open_bytes(k, blob, b"aad") == pt and blob != C.seal_bytes(k, pt, b"aad")  # a fresh nonce each time
    assert pt[:16] not in blob  # the plaintext is not in the ciphertext
    for i in (1, 20, len(blob) // 2, len(blob) - 1):
        t = bytearray(blob)
        t[i] ^= 1
        with pytest.raises(C.AuthError):
            C.open_bytes(k, bytes(t), b"aad")
    for bad in (dict(key=b"j" * 32, aad=b"aad"), dict(key=k, aad=b"other")):
        with pytest.raises(C.AuthError):
            C.open_bytes(bad["key"], blob, bad["aad"])
    with pytest.raises(C.AuthError):
        C.open_bytes(k, blob[:-1], b"aad")
    assert C.open_bytes(k, C.seal_bytes(k, b"", b""), b"") == b""


def test_a_lamport_signature_verifies_without_the_secret_and_fails_for_any_other_message():
    sec, pub = C.Lamport.generate(b"s" * 32)
    sig = C.Lamport.sign(sec, b"message")
    assert C.Lamport.verify(pub, b"message", sig) and not C.Lamport.verify(pub, b"messagE", sig) and not C.Lamport.verify(pub, b"message", sig[:-1])
    bad = list(sig)
    bad[3] = b"\x00" * 32
    assert not C.Lamport.verify(pub, b"message", bad)


def test_checkpoints_chain_from_a_trust_anchor_and_a_forgery_a_rewrite_or_a_reused_key_is_caught():
    auth = C.CheckpointAuthority(seed=b"a" * 32)
    cps = [auth.sign({"seq": i, "ledger_head": f"h{i}", "at": 1.0}) for i in (1, 2, 3)]
    assert C.verify_checkpoints(cps, auth.anchor) == []
    assert C.verify_checkpoints(cps, "0" * 64)  # the wrong anchor
    forged = json.loads(json.dumps(cps))
    forged[1]["ledger_head"] = "evil"
    assert any("signature" in x for x in C.verify_checkpoints(forged, auth.anchor))
    assert any("chain" in x for x in C.verify_checkpoints([cps[0], cps[2]], auth.anchor))  # a checkpoint removed from the series
    other = C.CheckpointAuthority(seed=b"b" * 32).sign({"seq": 9, "ledger_head": "x", "at": 1.0})
    assert C.verify_checkpoints([cps[0], other], auth.anchor)  # signed by another authority
    twice = [cps[0], {**cps[0]}]
    assert any("twice" in x or "chain" in x for x in C.verify_checkpoints(twice, auth.anchor))


# ---------------------------------------------------------------------------------------------------- T1, T2, T4, T5: access
def test_t1_no_operation_works_without_a_valid_token_and_a_role_cannot_exceed_its_permissions(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    rec = store(env, sub)
    for tok in ("", "garbage", "v1.a.b", env["steward"][:-2] + "xx"):
        with pytest.raises(AccessDenied):
            v.read_record(tok, sub, rec["record_id"])
    with pytest.raises(AccessDenied):
        v.read_identity(env["res"], sub)  # a researcher cannot read identities
    with pytest.raises(AccessDenied):
        v.read_record(env["rev"], sub, rec["record_id"])  # a reviewer cannot read data
    with pytest.raises(AccessDenied):
        v.enroll_subject(env["res"], {"name": "x"})
    with pytest.raises(AccessDenied):
        v.delete_subject(env["res"], sub)
    assert v.read_identity(env["steward"], sub)["name"] == CANARY_NAME
    assert "identity.read" not in ROLES["researcher"] and "data.read" not in ROLES["steward"]  # the steward manages subjects but does not read data


def test_t2_writing_needs_the_permission_and_a_consent_for_the_purpose(env):
    v = env["vault"]
    sub, cid = enrolled(env, purposes=("analysis",))
    rec = record(1)
    with pytest.raises(AccessDenied):
        v.store_record(env["rev"], sub, rec, rec_raw(1))
    with pytest.raises(VaultError) as e:
        v.store_record(env["res"], sub, rec, rec_raw(1), purpose="protocol-execution")  # consent covers analysis only
    assert e.value.code == "NO_CONSENT"
    with pytest.raises(VaultError) as e:
        v.store_record(env["res"], "sub-unknown", rec, rec_raw(1), purpose="analysis")
    assert e.value.code == "UNKNOWN_SUBJECT"
    v.store_record(env["res"], sub, rec, rec_raw(1), purpose="analysis")
    broken = dict(record(2))
    broken["provenance"] = "MEASURED"  # a record whose class does not match its digest is not stored
    with pytest.raises(VaultError) as e:
        v.store_record(env["res"], sub, broken, rec_raw(2), purpose="analysis")
    assert e.value.code == "RECORD_INVALID"
    with pytest.raises(VaultError) as e:
        v.store_record(env["res"], sub, record(3), b"not the raw original", purpose="analysis")
    assert e.value.code == "RAW_MISMATCH"


def test_t4_tokens_cannot_be_forged_extended_replayed_after_logout_or_used_after_expiry(env):
    auth, clock = env["auth"], env["clock"]
    tok = env["res"]
    v, body, mac = tok.split(".")
    import base64

    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    payload["role"] = "steward"
    forged_body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).rstrip(b"=").decode()
    with pytest.raises(AccessDenied) as e:
        auth.authenticate(f"{v}.{forged_body}.{mac}")  # a changed role does not match the signature
    assert e.value.code == "TOKEN_INVALID"
    other = AuthService(None, clock=clock, scrypt_n=N)  # another server secret
    with pytest.raises(AccessDenied):
        other.authenticate(tok)
    auth.revoke(tok)
    with pytest.raises(AccessDenied) as e:
        auth.authenticate(tok)
    assert e.value.code == "TOKEN_REVOKED"
    fresh = auth.login("res", PASS_R)
    clock.t += 601
    with pytest.raises(AccessDenied) as e:
        auth.authenticate(fresh)
    assert e.value.code == "TOKEN_EXPIRED"


def test_t5_passwords_are_hashed_weak_ones_refused_and_repeated_failures_lock_the_account(env):
    auth, clock = env["auth"], env["clock"]
    users_file = (env["dir"] / "auth" / "users.json").read_text()
    assert PASS_S not in users_file and PASS_R not in users_file and "scrypt" not in users_file and len(json.loads(users_file)["stew"]["hash"]) == 64  # only salted hashes are stored
    with pytest.raises(AccessDenied):
        auth.add_user("weak", "short", "researcher", by=auth.authenticate(env["steward"]))
    with pytest.raises(AccessDenied):
        auth.add_user("x", "a-long-enough-password", "researcher")  # users are added by a steward once the first user exists
    for _ in range(5):
        with pytest.raises(AccessDenied):
            auth.login("res", "wrong-password-xxx")
    with pytest.raises(AccessDenied) as e:
        auth.login("res", PASS_R)  # the right password is refused while locked
    assert e.value.code == "LOCKED"
    clock.t += 301
    assert auth.login("res", PASS_R)
    with pytest.raises(AccessDenied) as e:
        auth.login("nobody", "whatever-password-1")
    assert e.value.code == "CREDENTIALS"  # an unknown user is not told apart from a wrong password


def test_t11_the_vault_does_not_open_with_a_wrong_passphrase_and_the_passphrase_is_not_stored(env):
    with pytest.raises(VaultError) as e:
        Vault(env["dir"] / "vault", env["auth"], "wrong passphrase", clock=env["clock"], scrypt_n=N)
    assert e.value.code == "WRONG_PASSPHRASE"
    assert Vault(env["dir"] / "vault", env["auth"], PASS_V, clock=env["clock"], scrypt_n=N)
    assert all(PASS_V.encode() not in b for b in all_files_text(env["dir"]).values())


# ---------------------------------------------------------------------------------------------------- T3: tampering and integrity
def test_t3_a_tampered_blob_is_not_decrypted_and_integrity_verification_reports_it(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    rec = store(env, sub)
    assert v.verify_integrity(env["steward"]) == []
    blob = next((env["dir"] / "vault" / "blobs" / sub).glob("*.enc"))
    data = bytearray(blob.read_bytes())
    data[40] ^= 1
    blob.write_bytes(bytes(data))
    with pytest.raises(VaultError) as e:
        v.read_record(env["res"], sub, rec["record_id"])
    assert e.value.code == "INTEGRITY"
    assert any("does not match its digest" in x for x in v.verify_integrity(env["steward"]))
    blob.unlink()
    assert any("missing" in x for x in v.verify_integrity(env["steward"]))


def test_t3_a_changed_ledger_skeleton_or_audit_entry_breaks_the_chain(env):
    sub, _ = enrolled(env)
    store(env, sub, 1)
    store(env, sub, 2)
    lp = env["dir"] / "vault" / "ledger.jsonl"
    lines = lp.read_text().splitlines()
    first = json.loads(lines[0])
    first["body"]["provenance"] = "MEASURED"  # a SYNTHETIC record re-labelled in the ledger
    lines[0] = json.dumps(first, sort_keys=True)
    lp.write_text("\n".join(lines) + "\n")
    v2 = Vault(env["dir"] / "vault", env["auth"], PASS_V, clock=env["clock"], scrypt_n=N)
    assert any("hash does not match" in x for x in v2.verify_integrity(env["steward"]))
    ap = env["dir"] / "auth" / "audit.jsonl"
    audit_lines = ap.read_text().splitlines()
    a0 = json.loads(audit_lines[0])
    a0["body"]["actor"] = "someone-else"
    audit_lines[0] = json.dumps(a0, sort_keys=True)
    ap.write_text("\n".join(audit_lines) + "\n")
    assert any(x.startswith("audit:") for x in Vault(env["dir"] / "vault", AuthService(env["dir"] / "auth", clock=env["clock"], scrypt_n=N), PASS_V, clock=env["clock"], scrypt_n=N).verify_integrity(env["steward"]))


def test_t10_signed_checkpoints_catch_a_rewritten_or_shortened_history(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    store(env, sub, 1)
    authority = C.CheckpointAuthority()
    v.checkpoint(env["steward"], authority)
    store(env, sub, 2)
    v.checkpoint(env["steward"], authority)
    assert v.verify_checkpoints(env["steward"], authority.anchor) == [] and v.verify_checkpoints(env["steward"], "0" * 64)
    lp = env["dir"] / "vault" / "ledger.jsonl"
    lines = lp.read_text().splitlines()
    lp.write_text("\n".join(lines[:-1]) + "\n")  # the last record's entry is removed
    v2 = Vault(env["dir"] / "vault", env["auth"], PASS_V, clock=env["clock"], scrypt_n=N)
    assert any("ledger no longer matches" in x for x in v2.verify_checkpoints(env["steward"], authority.anchor))
    with pytest.raises(AccessDenied):
        v.checkpoint(env["res"], authority)  # only the steward signs


# ---------------------------------------------------------------------------------------------------- T6: separation of identity
def test_t6_identity_is_in_one_encrypted_store_and_no_other_store_carries_it(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    store(env, sub)
    v.checkpoint(env["steward"], C.CheckpointAuthority())
    files = all_files_text(env["dir"])
    for name, data in files.items():
        for canary in (CANARY_NAME, CANARY_MAIL):
            assert canary.encode() not in data, f"{canary!r} found in {name}"  # not even in the identity store (it is encrypted)
    assert (env["dir"] / "vault" / "identity.enc").exists() and sub.startswith("sub-") and sub not in CANARY_NAME
    assert all(CANARY_DATA.encode() not in d for d in files.values())  # the data are encrypted at rest too
    ledger_bodies = [json.loads(line)["body"] for line in (env["dir"] / "vault" / "ledger.jsonl").read_text().splitlines()]
    assert all("payload" not in b and "creator" not in b and "source" not in b for b in ledger_bodies)  # the skeleton keeps no payload, no creator, no source description


# ---------------------------------------------------------------------------------------------------- T7: logs
def test_t7_nothing_sensitive_reaches_the_audit_log_the_logging_output_or_an_error_message(env, caplog):
    caplog.set_level(logging.DEBUG)
    v, auth = env["vault"], env["auth"]
    sub, _ = enrolled(env)
    rec = store(env, sub)
    errors = []
    for fn in (lambda: auth.login("stew", "wrong-password-xxx"), lambda: auth.authenticate(env["res"] + "x"), lambda: v.read_identity(env["res"], sub), lambda: v.store_record(env["res"], sub, record(9), b"x"),
               lambda: v.read_record(env["res"], sub, "rec-nonexistent"), lambda: v.read_record(env["res"], sub, rec["record_id"], purpose="external-transmission")):
        try:
            fn()
        except (AccessDenied, VaultError) as e:
            errors.append(str(e) + repr(e))
    v.read_identity(env["steward"], sub)
    v.delete_subject(env["steward"], sub)
    audit_text = (env["dir"] / "auth" / "audit.jsonl").read_text()
    haystack = audit_text + "\n".join(errors) + caplog.text
    for secret in (CANARY_NAME, CANARY_MAIL, CANARY_DATA, PASS_S, PASS_R, PASS_V, env["steward"], env["res"], "wrong-password-xxx"):
        assert secret not in haystack, secret[:12]
    assert "identity.read" in audit_text and sub in audit_text  # the access is audited by pseudonym and by who, not by what was read


def test_t7_redaction_removes_sensitive_keys_addresses_numbers_and_tokens():
    out = RD.redact({"name": "A B", "note": "call +81 90 1234 5678 or a.b@example.org", "nested": {"password": "p", "ok": "fine", "tok": "v1.abcdefghijklmnop.qrstuvwxyz012345"}, "items": ["mail me: x@y.zz"]})
    s = json.dumps(out)
    assert out["name"] == out["nested"]["password"] == RD.MASK and out["nested"]["ok"] == "fine"
    for leak in ("A B", "1234 5678", "a.b@example.org", "v1.abcdefghijklmnop", "x@y.zz"):
        assert leak not in s
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "user a@b.org logged in with %s", ("v1.abcdefghijklmnop.qrstuvwxyz012345",), None)
    assert RD.RedactingFilter().filter(rec) and "a@b.org" not in rec.getMessage() and "abcdefghijklmnop" not in rec.getMessage()
    assert RD.safe_error(AccessDenied("PERMISSION")) == "AccessDenied:PERMISSION" and RD.safe_error(ValueError("secret text")) == "ValueError"


# ---------------------------------------------------------------------------------------------------- T9: consent
def test_t9_use_is_limited_to_the_consented_purpose_and_ends_with_a_revocation_or_an_expiry(env):
    v, clock = env["vault"], env["clock"]
    sub, cid = enrolled(env, purposes=("analysis",))
    rec = record(1)
    v.store_record(env["res"], sub, rec, rec_raw(1), purpose="analysis")
    assert v.read_record(env["res"], sub, rec["record_id"], purpose="analysis")["record"]["record_id"] == rec["record_id"]
    with pytest.raises(VaultError) as e:
        v.read_record(env["res"], sub, rec["record_id"], purpose="external-transmission")  # never implied
    assert e.value.code == "NO_CONSENT"
    v.revoke_consent(env["steward"], sub, cid, "withdrawn")
    with pytest.raises(VaultError) as e:
        v.read_record(env["res"], sub, rec["record_id"], purpose="analysis")
    assert e.value.code == "NO_CONSENT"
    hist = v.consents.history(sub)
    assert [b["type"] for b in hist] == ["grant", "revoke"]  # the grant is still there: a revocation is a new entry
    cid2 = v.record_consent(env["steward"], sub, ["analysis"], ["observation"], expires_at=clock.t + 100)
    assert v.consents.active(sub, "analysis", "observation") == cid2
    clock.t += 101
    assert v.consents.active(sub, "analysis", "observation") is None
    with pytest.raises(ValueError):
        v.consents.grant(sub, ["anything"], ["observation"])
    assert v.consents.active(sub, "analysis", "observation", at=clock.t - 50) == cid2  # consent as it stood at an earlier time


# ---------------------------------------------------------------------------------------------------- T8: deletion
def test_t8_deletion_removes_the_blobs_the_key_and_the_identity_and_keeps_only_non_identifying_verification_data(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    recs = [store(env, sub, i) for i in (1, 2, 3)]
    files_before = all_files_text(env["dir"])
    res = v.delete_subject(env["steward"], sub)
    assert res["records"] == sorted(r["record_id"] for r in recs) and res["blobs_removed"] == 3 and res["key_destroyed"] and res["identity_removed"]
    assert res["verification"]["all_passed"] and all(res["verification"]["checks"].values())
    files_after = all_files_text(env["dir"])
    assert not any(k.startswith("blobs/") or "/blobs/" in k for k in files_after if k.endswith(".enc") and "identity" not in k)  # no blob file remains
    ks = json.loads((env["dir"] / "vault" / "keystore.json").read_text())[sub]
    assert ks["state"] == "destroyed" and ks["wrapped"] is None  # no key material remains for the subject
    with pytest.raises(VaultError) as e:
        v.read_record(env["res"], sub, recs[0]["record_id"])
    assert e.value.code in ("NO_CONSENT", "NOT_FOUND", "KEY_DESTROYED")
    with pytest.raises(AccessDenied if False else VaultError):
        v.read_identity(env["steward"], sub)
    assert v.verify_integrity(env["steward"]) == []  # the ledger, the audit and the consent chains are intact after the deletion
    tomb = [json.loads(line)["body"] for line in (env["dir"] / "vault" / "ledger.jsonl").read_text().splitlines() if '"tombstone"' in line][0]
    assert tomb["subject"] == sub and set(tomb["record_ids"]) == set(res["records"]) and "name" not in tomb and tomb["key_destroyed"]
    assert any(b["type"] == "record" for b in map(lambda line: json.loads(line)["body"], (env["dir"] / "vault" / "ledger.jsonl").read_text().splitlines()))  # the non-identifying skeletons stay
    assert any(CANARY_DATA.encode() in d for d in files_before.values()) is False  # the data were never in the clear


def test_t8_a_backup_of_the_key_store_taken_before_the_deletion_defeats_it_and_the_check_says_so(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    rec = store(env, sub)
    backup = env["dir"] / "backup_keystore.json"
    shutil.copy(env["dir"] / "vault" / "keystore.json", backup)
    blob_copy = env["dir"] / "blob_copy.enc"
    shutil.copy(next((env["dir"] / "vault" / "blobs" / sub).glob("*.enc")), blob_copy)
    res = v.delete_subject(env["steward"], sub, known_backups=(backup,))
    assert not res["verification"]["all_passed"] and any("known backup" in r for r in res["verification"]["residual_risks"])
    # the demonstration: with the old wrapped key, the passphrase and the copied ciphertext the data come back. Deletion is only as good as the backups' deletion.
    meta = json.loads((env["dir"] / "vault" / "vault.json").read_text())
    master = C.kdf(PASS_V.encode(), bytes.fromhex(meta["salt"]), n=meta["n"])
    dek = C.open_bytes(C.hkdf(master, b"teoo/wrap"), bytes.fromhex(json.loads(backup.read_text())[sub]["wrapped"]), sub.encode())
    full = C.open_json(dek, blob_copy.read_bytes(), f"{sub}|{rec['record_id']}".encode())
    assert full["record"]["record_id"] == rec["record_id"]
    backup.write_text(json.dumps({sub: {"state": "destroyed", "wrapped": None}}))  # once the backup is cleaned the check passes
    assert v.verify_deletion(env["steward"], sub, (backup,))["all_passed"]


def test_t8_no_trace_of_the_data_or_the_identity_is_left_in_any_file_after_deletion(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    store(env, sub, 1)
    v.read_identity(env["steward"], sub)
    v.delete_subject(env["steward"], sub)
    for name, data in all_files_text(env["dir"]).items():
        for s in (CANARY_NAME, CANARY_MAIL, CANARY_DATA, "raw-1-"):
            assert s.encode() not in data, f"{s!r} in {name}"
    other, _ = enrolled(env)  # another subject is not affected
    store(env, other, 5)
    assert v.verify_integrity(env["steward"]) == []


def test_t8_deleting_an_unknown_or_already_deleted_subject_is_refused(env):
    v = env["vault"]
    sub, _ = enrolled(env)
    v.delete_subject(env["steward"], sub)
    for s in (sub, "sub-unknown"):
        with pytest.raises(VaultError) as e:
            v.delete_subject(env["steward"], s)
        assert e.value.code == "UNKNOWN_SUBJECT"


def test_consent_records_are_appended_never_edited(tmp_path):
    log = ConsentLog(tmp_path / "c.jsonl", clock=Clock())
    log.grant("sub-1", ["analysis"], ["observation"])
    lines = (tmp_path / "c.jsonl").read_text().splitlines()
    e = json.loads(lines[0])
    e["body"]["purposes"] = ["analysis", "external-transmission"]  # an edit that widens the consent
    (tmp_path / "c.jsonl").write_text(json.dumps(e) + "\n")
    assert ConsentLog(tmp_path / "c.jsonl").log.verify()


# ---------------------------------------------------------------------------------------------------- the gate
def test_the_production_gate_is_closed_until_every_requirement_is_attested_and_an_attestation_is_not_verification():
    g = SF.production_gate()
    assert g["production_ready"] is False and g["human_measurement_ingestion_allowed"] is False and {m["id"] for m in g["missing"]} == {i for i, _ in SF.PRODUCTION_REQUIREMENTS}
    partial = SF.production_gate({"ethics_approval_id": "ERB-2026-001"})
    assert partial["production_ready"] is False and len(partial["missing"]) == len(SF.PRODUCTION_REQUIREMENTS) - 1
    full = SF.production_gate({i: "ref-1" for i, _ in SF.PRODUCTION_REQUIREMENTS})
    assert full["production_ready"] is True and "not thereby true" in full["note"]  # the code reports the presence of references; it cannot check them
    assert len(SF.CAPABILITIES) == 8 and all(c["implemented"] and c["limits"] for c in SF.CAPABILITIES)
    assert [t["id"] for t in SF.THREATS] == [f"T{i}" for i in range(1, 12)]
