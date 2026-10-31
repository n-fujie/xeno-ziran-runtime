"""Cryptographic parts for the local vault, from the Python standard library only (no third-party crypto library is installed in this environment).

* ``kdf``            scrypt (hashlib.scrypt) for passphrases and passwords.
* ``hkdf``           HKDF-SHA256 (RFC 5869) to derive independent keys from one key.
* ``seal_bytes`` / ``open_bytes``
                     authenticated encryption: encrypt-then-MAC with an HMAC-SHA256 counter-mode keystream and an HMAC-SHA256 tag, random 128-bit nonce, associated data bound into the tag.
                     This is a standard construction (HMAC as a PRF in counter mode, then a MAC over nonce, associated data and ciphertext), built from vetted primitives, and it is tested here; it
                     is **not a vetted AEAD implementation** (no AES-GCM or ChaCha20-Poly1305), has not been reviewed by a cryptographer and is slow. For production use a vetted library and a KMS.
* ``Lamport``        a hash-based one-time signature (Lamport, SHA-256): a real public-key signature property (verification needs no secret) from a hash function alone, with the limits of
                     one-time keys. ``CheckpointAuthority`` chains the keys (each signed checkpoint commits to the hash of the next public key) so that a trust anchor (the hash of the first public key)
                     published outside the vault is enough to verify a whole series of checkpoints. Key storage, anchor distribution and revocation are not solved here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

CIPHER_NAME = "HMAC-SHA256-CTR + HMAC-SHA256 (encrypt-then-MAC), stdlib; not a vetted AEAD"
VERSION = b"\x01"
NONCE_LEN, TAG_LEN = 16, 32


class AuthError(Exception):
    """Authentication failed (wrong key, tampered ciphertext or associated data). Carries no data about the content."""


def kdf(secret: bytes, salt: bytes, *, n: int = 2**14, r: int = 8, p: int = 1, length: int = 32) -> bytes:
    return hashlib.scrypt(secret, salt=salt, n=n, r=r, p=p, dklen=length, maxmem=64 * 1024 * 1024)


def hkdf(key: bytes, info: bytes, length: int = 32, salt: bytes = b"") -> bytes:
    prk = hmac.new(salt or b"\x00" * 32, key, hashlib.sha256).digest()
    out, t, i = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        out += t
        i += 1
    return out[:length]


def _keystream(k: bytes, nonce: bytes, n: int) -> bytes:
    blocks = (n + 31) // 32
    return b"".join(hmac.digest(k, nonce + i.to_bytes(8, "big"), "sha256") for i in range(blocks))[:n]


def _xor(a: bytes, b: bytes) -> bytes:
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(len(a), "big") if a else b""


def _tag(k_mac: bytes, nonce: bytes, aad: bytes, ct: bytes) -> bytes:
    return hmac.digest(k_mac, VERSION + nonce + len(aad).to_bytes(8, "big") + aad + len(ct).to_bytes(8, "big") + ct, "sha256")


def seal_bytes(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    if len(key) != 32:
        raise ValueError("the key is 32 bytes")
    k_enc, k_mac = hkdf(key, b"teoo/enc"), hkdf(key, b"teoo/mac")
    nonce = secrets.token_bytes(NONCE_LEN)
    ct = _xor(plaintext, _keystream(k_enc, nonce, len(plaintext)))
    return VERSION + nonce + ct + _tag(k_mac, nonce, aad, ct)


def open_bytes(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    if len(blob) < 1 + NONCE_LEN + TAG_LEN or blob[:1] != VERSION:
        raise AuthError("malformed ciphertext")
    nonce, ct, tag = blob[1:1 + NONCE_LEN], blob[1 + NONCE_LEN:-TAG_LEN], blob[-TAG_LEN:]
    k_enc, k_mac = hkdf(key, b"teoo/enc"), hkdf(key, b"teoo/mac")
    if not hmac.compare_digest(tag, _tag(k_mac, nonce, aad, ct)):
        raise AuthError("authentication failed")
    return _xor(ct, _keystream(k_enc, nonce, len(ct)))


def seal_json(key: bytes, obj: Any, aad: bytes = b"") -> bytes:
    return seal_bytes(key, json.dumps(obj, sort_keys=True, separators=(",", ":")).encode(), aad)


def open_json(key: bytes, blob: bytes, aad: bytes = b"") -> Any:
    return json.loads(open_bytes(key, blob, aad))


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


# ------------------------------------------------------------------------------------------------ Lamport one-time signature (SHA-256)
class Lamport:
    BITS = 256

    @staticmethod
    def generate(seed: bytes | None = None) -> tuple[list[list[bytes]], list[list[bytes]]]:
        """(secret, public): secret[i][b] are random 32-byte values, public[i][b] their SHA-256. ``seed`` (32 bytes) makes the keys reproducible (tests); omit it for random keys."""
        sec = [[hkdf(seed, b"lamport/%d/%d" % (i, b)) if seed else secrets.token_bytes(32) for b in (0, 1)] for i in range(Lamport.BITS)]
        return sec, [[sha256(x) for x in pair] for pair in sec]

    @staticmethod
    def _bits(msg: bytes) -> list[int]:
        d = sha256(msg)
        return [(d[i // 8] >> (7 - i % 8)) & 1 for i in range(Lamport.BITS)]

    @staticmethod
    def sign(secret: list[list[bytes]], msg: bytes) -> list[bytes]:
        return [secret[i][b] for i, b in enumerate(Lamport._bits(msg))]

    @staticmethod
    def verify(public: list[list[bytes]], msg: bytes, sig: list[bytes]) -> bool:
        if len(sig) != Lamport.BITS:
            return False
        return all(hmac.compare_digest(sha256(s), public[i][b]) for i, (s, b) in enumerate(zip(sig, Lamport._bits(msg), strict=True)))

    @staticmethod
    def pub_hash(public: list[list[bytes]]) -> str:
        return hashlib.sha256(b"".join(x for pair in public for x in pair)).hexdigest()


def _hexify(pub: list[list[bytes]]) -> list[list[str]]:
    return [[x.hex() for x in pair] for pair in pub]


def _unhex(pub: list[list[str]]) -> list[list[bytes]]:
    return [[bytes.fromhex(x) for x in pair] for pair in pub]


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class CheckpointAuthority:
    """Signs checkpoints of a ledger with one-time keys, each checkpoint committing to the next public key. The holder keeps ``secrets``; ``anchor`` (the hash of the first public key)
    is what a verifier must obtain from somewhere the vault's holder does not control."""

    def __init__(self, seed: bytes | None = None):
        self._seed = seed
        self._index = 0
        self._cur = Lamport.generate(self._derive(0))
        self.anchor = Lamport.pub_hash(self._cur[1])

    def _derive(self, i: int) -> bytes | None:
        return hkdf(self._seed, b"ca/%d" % i) if self._seed else None

    def sign(self, checkpoint: dict) -> dict:
        nxt = Lamport.generate(self._derive(self._index + 1))
        body = {**checkpoint, "key_index": self._index, "next_pub_hash": Lamport.pub_hash(nxt[1])}
        sig = Lamport.sign(self._cur[0], canonical(body))
        out = {**body, "public_key": _hexify(self._cur[1]), "signature": [s.hex() for s in sig]}
        self._index, self._cur = self._index + 1, nxt
        return out


def verify_checkpoints(cps: list[dict], anchor: str) -> list[str]:
    """Problems found in a series of signed checkpoints, given the trust anchor. An empty list means: every signature is valid, the keys chain from the anchor, no key was used twice and
    the ledger positions only grow. (It does not say that the signer was honest or that the anchor is the right one.)"""
    problems: list[str] = []
    expect, used, last_seq = anchor, set(), -1
    for n, cp in enumerate(cps):
        pub = _unhex(cp["public_key"])
        if Lamport.pub_hash(pub) != expect:
            problems.append(f"checkpoint {n}: the public key does not chain from the anchor or the previous checkpoint")
        body = {k: v for k, v in cp.items() if k not in ("public_key", "signature")}
        if not Lamport.verify(pub, canonical(body), [bytes.fromhex(s) for s in cp["signature"]]):
            problems.append(f"checkpoint {n}: the signature is not valid")
        if cp["key_index"] in used:
            problems.append(f"checkpoint {n}: a one-time key was used twice (the key may be compromised)")
        used.add(cp["key_index"])
        if cp["seq"] < last_seq:
            problems.append(f"checkpoint {n}: the ledger position went backwards")
        last_seq, expect = cp["seq"], cp["next_pub_hash"]
    return problems
