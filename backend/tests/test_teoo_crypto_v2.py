"""TEOO Phase 4: the vetted AEAD (format 2), the migration of legacy (format 1) data, key rotation, and a safe stop on any failed decryption."""

from __future__ import annotations

import json
import shutil

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305  # noqa: E402

from xzr.teoo import crypto as C  # noqa: E402
from xzr.teoo import provenance as P  # noqa: E402
from xzr.teoo.access import AccessDenied, AuthService  # noqa: E402
from xzr.teoo.vault import Vault, VaultError  # noqa: E402

N = 2**10
PASS_S, PASS_R, PASS_V = "steward-password-001", "researcher-pass-002", "vault passphrase 003!"
CANARY = "CANARY-DATA-9917"


# ------------------------------------------------------------------------------------------------ the AEAD
@pytest.mark.parametrize("alg", [1, 2])
def test_both_algorithms_roundtrip_and_the_blob_is_what_the_vetted_library_reads(alg):
    k, pt = bytes(range(32)), b"observation bytes" * 20
    blob = C.seal_bytes(k, pt, b"aad", key_id=7, alg=alg)
    assert C.open_bytes(k, blob, b"aad") == pt and C.blob_info(blob) == {"format": 2, "algorithm": C.ALGORITHMS[alg], "key_id": 7, "legacy": False}
    head, nonce, body = blob[:6], blob[6:18], blob[18:]
    lib = (AESGCM if alg == 1 else ChaCha20Poly1305)(k)  # an independent decryption with the library itself, following the documented layout
    assert lib.decrypt(nonce, body, head + len(b"aad").to_bytes(8, "big") + b"aad") == pt and len(body) == len(pt) + 16
    assert pt[:16] not in blob and blob != C.seal_bytes(k, pt, b"aad", key_id=7, alg=alg)  # a fresh random nonce each time


def test_nonces_do_not_repeat_over_many_messages():
    k = b"n" * 32
    seen = {C.seal_bytes(k, b"x")[6:18] for _ in range(5000)}
    assert len(seen) == 5000


def test_every_changed_byte_of_the_header_the_nonce_the_ciphertext_and_the_tag_is_refused_without_detail():
    k = b"k" * 32
    blob = C.seal_bytes(k, b"payload" * 9, b"aad", key_id=3)
    for i in range(len(blob)):
        t = bytearray(blob)
        t[i] ^= 1
        with pytest.raises(C.AuthError) as ei:
            C.open_bytes(k, bytes(t), b"aad")
        assert "payload" not in str(ei.value)
    swapped = bytearray(blob)
    swapped[1] = 2  # a downgrade or switch of the algorithm is a failed authentication, not another algorithm
    with pytest.raises(C.AuthError):
        C.open_bytes(k, bytes(swapped), b"aad")
    for bad in (blob[:-1], blob[:10], b"", b"\x02"):
        with pytest.raises(C.AuthError):
            C.open_bytes(k, bad, b"aad")
    with pytest.raises(C.AuthError):
        C.open_bytes(b"j" * 32, blob, b"aad")
    with pytest.raises(C.AuthError):
        C.open_bytes(k, blob, b"other-aad")


def test_a_key_ring_selects_by_the_authenticated_key_id_and_an_unknown_id_fails():
    k1, k2 = b"1" * 32, b"2" * 32
    b1, b2 = C.seal_bytes(k1, b"a", b"x", key_id=1), C.seal_bytes(k2, b"b", b"x", key_id=2)
    ring = {1: k1, 2: k2}
    assert C.open_bytes(ring, b1, b"x") == b"a" and C.open_bytes(ring, b2, b"x") == b"b"
    with pytest.raises(C.AuthError):
        C.open_bytes({1: k1}, b2, b"x")
    relabelled = bytearray(b2)
    relabelled[5] = 1  # claim key 1 for a blob made with key 2
    with pytest.raises(C.AuthError):
        C.open_bytes(ring, bytes(relabelled), b"x")


def test_legacy_blobs_open_only_when_allowed_and_are_never_written(monkeypatch):
    k = b"l" * 32
    old = C.legacy_seal_v1(k, b"old data", b"a")
    assert C.blob_info(old)["legacy"] and C.open_bytes(k, old, b"a") == b"old data"
    with pytest.raises(C.AuthError):
        C.open_bytes(k, old, b"a", allow_legacy=False)
    with pytest.raises(C.AuthError):
        C.open_bytes({0: k}, old, b"a")
    assert not C.blob_info(C.seal_bytes(k, b"new", b"a"))["legacy"]


def test_a_key_that_has_sealed_the_maximum_number_of_messages_must_be_rotated(monkeypatch):
    monkeypatch.setattr(C, "MAX_MESSAGES_PER_KEY", 3)
    k = b"m" * 32
    for _ in range(3):
        C.seal_bytes(k, b"x")
    with pytest.raises(C.KeyExhausted):
        C.seal_bytes(k, b"x")
    C.seal_bytes(b"o" * 32, b"x")  # another key is unaffected


def test_without_the_library_nothing_is_sealed_and_there_is_no_fallback(monkeypatch):
    def gone(alg, key):
        raise C.CryptoUnavailable("missing")
    monkeypatch.setattr(C, "_aead", gone)
    assert not C.have_aead()
    with pytest.raises(C.CryptoUnavailable):
        C.seal_bytes(b"k" * 32, b"x")
    legacy = C.legacy_seal_v1(b"k" * 32, b"x")
    assert C.open_bytes(b"k" * 32, legacy) == b"x"  # old data can still be read (to be migrated once the library is back)


# ------------------------------------------------------------------------------------------------ the vault
class Clock:
    t = 1_000_000.0

    def __call__(self) -> float:
        return self.t


def make_env(tmp_path, legacy=False, monkeypatch=None):
    clock = Clock()
    auth = AuthService(tmp_path / "auth", clock=clock, scrypt_n=N, token_ttl=600, lock_s=300)
    auth.add_user("stew", PASS_S, "steward")
    steward = auth.login("stew", PASS_S)
    auth.add_user("res", PASS_R, "researcher", by=auth.authenticate(steward))
    if legacy:
        monkeypatch.setattr(C, "seal_bytes", lambda key, data, aad=b"", **kw: C.legacy_seal_v1(key, data, aad))
    v = Vault(tmp_path / "vault", auth, PASS_V, clock=clock, scrypt_n=N)
    res = auth.login("res", PASS_R)
    sub = v.enroll_subject(steward, {"name": "Test Person"})
    v.record_consent(steward, sub, ["protocol-execution", "analysis"], ["observation"])
    recs = []
    for n in (1, 2, 3):
        rec = P.seal({"series": [1.5, n], "note": CANARY}, provenance="SYNTHETIC", kind="OBSERVATION", creator={"name": "g"}, source={"kind": "generator", "description": "t", "declared_by": "x"}, raw_bytes=f"raw-{n}".encode(), created_at="2026-01-01T00:00:00.000000Z")
        v.store_record(res, sub, rec, f"raw-{n}".encode())
        recs.append(rec)
    if legacy:
        monkeypatch.undo()
        meta = tmp_path / "vault" / "vault.json"
        m = json.loads(meta.read_text())
        meta.write_text(json.dumps({**m, "cipher": "teoo.crypto/1", "key_id": 0}))
        v = Vault(tmp_path / "vault", auth, PASS_V, clock=clock, scrypt_n=N)  # reopened: a vault written by the earlier version
    return {"auth": auth, "vault": v, "steward": steward, "res": res, "sub": sub, "recs": recs, "dir": tmp_path, "clock": clock}


def test_a_new_vault_writes_only_the_vetted_format_and_says_so(tmp_path):
    e = make_env(tmp_path)
    st = e["vault"].crypto_status(e["steward"])
    assert st["legacy_objects"] == 0 and st["aead_available"] and all("format 2 AES-256-GCM" in k for k in st["objects"]) and "format 1" not in json.dumps(st)
    assert sum(st["objects"].values()) == 1 + 3 + 1 + 1  # wrapped key, three blobs, identity store, passphrase check


def test_legacy_data_is_found_readable_and_migrated_with_everything_verified_afterwards(tmp_path, monkeypatch):
    e = make_env(tmp_path, legacy=True, monkeypatch=monkeypatch)
    v, steward, res, sub = e["vault"], e["steward"], e["res"], e["sub"]
    before = v.crypto_status(steward)
    assert before["legacy_objects"] == 6 and before["vault_format"] == 1
    assert v.read_record(res, sub, e["recs"][0]["record_id"])["record"] == e["recs"][0]  # still readable before migration
    with pytest.raises(AccessDenied):
        v.migrate(res, PASS_V)  # the researcher role cannot rotate or migrate
    with pytest.raises(VaultError):
        v.migrate(steward, "not the passphrase")
    out = v.migrate(steward, PASS_V)
    assert out["legacy_objects_left"] == 0 and out["converted"] == {"wrapped_keys": 1, "record_blobs": 3, "identity_store": 1, "passphrase_check": 1}
    after = v.crypto_status(steward)
    assert after["legacy_objects"] == 0 and after["vault_format"] == 2 and "format 1" not in json.dumps(after)
    for r in e["recs"]:
        got = v.read_record(res, sub, r["record_id"])
        assert got["record"] == r
    assert v.verify_integrity(steward) == []  # the ledger holds the re-encryptions as entries; the blob digests still agree
    reseals = [b for b in v.ledger.bodies() if b["type"] == "reseal"]
    assert len(reseals) == 3 and all(b["old_blob_digest"] != b["new_blob_digest"] for b in reseals)
    assert v.migrate(steward, PASS_V)["converted"] == {"wrapped_keys": 0, "record_blobs": 0, "identity_store": 0, "passphrase_check": 0}  # idempotent
    reopened = Vault(tmp_path / "vault", e["auth"], PASS_V, clock=e["clock"], scrypt_n=N)
    assert reopened.read_record(res, sub, e["recs"][1]["record_id"])["record"] == e["recs"][1]  # a restart reads the converted vault


def test_a_blob_that_fails_authentication_stops_the_migration_and_is_left_untouched(tmp_path, monkeypatch):
    e = make_env(tmp_path, legacy=True, monkeypatch=monkeypatch)
    v, steward = e["vault"], e["steward"]
    files = sorted((tmp_path / "vault" / "blobs" / e["sub"]).glob("*.enc"))
    bad = bytearray(files[1].read_bytes())
    bad[30] ^= 1
    files[1].write_bytes(bytes(bad))
    with pytest.raises(C.AuthError):
        v.migrate(steward, PASS_V)
    assert files[1].read_bytes() == bytes(bad)  # the damaged blob was not rewritten
    assert any(C.blob_info(f.read_bytes())["legacy"] for f in files)  # and what had not been reached stays as it was
    assert v.verify_integrity(steward)  # the damage is reported, not hidden by the conversion


def test_a_failed_decryption_stops_with_a_code_and_discloses_nothing(tmp_path):
    e = make_env(tmp_path)
    v, res = e["vault"], e["res"]
    f = next((tmp_path / "vault" / "blobs" / e["sub"]).glob("*.enc"))
    b = bytearray(f.read_bytes())
    b[40] ^= 1
    f.write_bytes(bytes(b))
    rid = f.stem
    with pytest.raises(VaultError) as ei:
        v.read_record(res, e["sub"], rid)
    assert ei.value.code == "INTEGRITY" and CANARY not in str(ei.value)
    log = (tmp_path / "auth").rglob("*")
    assert not any(CANARY in p.read_text(errors="ignore") for p in log if p.is_file())
    assert any(b.get("code") == "INTEGRITY" for b in e["auth"].audit.bodies())  # the refusal is audited by code


def test_without_the_library_the_vault_stores_nothing(tmp_path, monkeypatch):
    e = make_env(tmp_path)
    v, res, sub = e["vault"], e["res"], e["sub"]
    n_before = len(list((tmp_path / "vault" / "blobs" / sub).glob("*.enc")))
    monkeypatch.setattr(C, "_aead", lambda alg, key: (_ for _ in ()).throw(C.CryptoUnavailable("x")))
    rec = P.seal({"series": [9]}, provenance="SYNTHETIC", kind="OBSERVATION", creator={"name": "g"}, source={"kind": "generator", "description": "t", "declared_by": "x"}, raw_bytes=b"raw-9", created_at="2026-01-01T00:00:00.000000Z")
    with pytest.raises(VaultError) as ei:
        v.store_record(res, sub, rec, b"raw-9")
    assert ei.value.code == "CRYPTO_UNAVAILABLE"
    assert len(list((tmp_path / "vault" / "blobs" / sub).glob("*.enc"))) == n_before and rec["record_id"] not in [b["record_id"] for b in v.ledger.bodies() if b["type"] == "record"]
    with pytest.raises(VaultError):
        v.enroll_subject(e["steward"], {"name": "Another"})


def test_a_subject_key_rotation_re_encrypts_the_blobs_and_the_old_key_no_longer_opens_them(tmp_path):
    e = make_env(tmp_path)
    v, steward, res, sub = e["vault"], e["steward"], e["res"], e["sub"]
    old_dek = v._dek(sub)
    old_blobs = {f.name: f.read_bytes() for f in (tmp_path / "vault" / "blobs" / sub).glob("*.enc")}
    with pytest.raises(AccessDenied):
        v.rotate_subject_key(res, sub)
    out = v.rotate_subject_key(steward, sub)
    assert out["generation"] == 2 and out["blobs_reencrypted"] == 3
    for f in (tmp_path / "vault" / "blobs" / sub).glob("*.enc"):
        assert C.blob_info(f.read_bytes())["key_id"] == 2 and f.read_bytes() != old_blobs[f.name]
        with pytest.raises(C.AuthError):
            C.open_bytes(old_dek, f.read_bytes(), f"{sub}|{f.stem}".encode())  # the old key does not open the new blob
    for r in e["recs"]:
        assert v.read_record(res, sub, r["record_id"])["record"] == r
    assert v.verify_integrity(steward) == [] and "still holds the old key" in out["residual"]
    shutil.rmtree(tmp_path / "vault" / "blobs" / sub)  # then deletion still works on a rotated subject
    assert v.delete_subject(steward, sub)["verification"]["checks"]["decryption_impossible"]


def test_a_master_key_rotation_moves_every_wrapped_key_and_the_identity_store_to_the_new_passphrase(tmp_path):
    e = make_env(tmp_path)
    v, steward, res, sub = e["vault"], e["steward"], e["res"], e["sub"]
    with pytest.raises(VaultError) as ei:
        v.rotate_master(steward, "wrong old passphrase", "a brand new passphrase 77")
    assert ei.value.code == "WRONG_PASSPHRASE"
    out = v.rotate_master(steward, PASS_V, "a brand new passphrase 77")
    assert out["master_key_id"] == 2 and out["wrapped_keys"] == 1 and out["identity_store"]
    st = v.crypto_status(steward)
    assert all("key 2" in k or "blob" in k for k in st["objects"]) and st["legacy_objects"] == 0
    assert v.read_identity(steward, sub) == {"name": "Test Person"} and v.read_record(res, sub, e["recs"][0]["record_id"])["record"] == e["recs"][0]
    with pytest.raises(VaultError) as e2:
        Vault(tmp_path / "vault", e["auth"], PASS_V, clock=e["clock"], scrypt_n=N)  # the old passphrase no longer opens the vault
    assert e2.value.code == "WRONG_PASSPHRASE"
    again = Vault(tmp_path / "vault", e["auth"], "a brand new passphrase 77", clock=e["clock"], scrypt_n=N)
    assert again.read_record(res, sub, e["recs"][2]["record_id"])["record"] == e["recs"][2] and again.verify_integrity(steward) == []
