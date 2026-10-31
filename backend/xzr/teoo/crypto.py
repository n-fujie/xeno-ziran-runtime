"""Cryptographic parts for the local vault.

* ``kdf``            scrypt (hashlib.scrypt) for passphrases and passwords.
* ``hkdf``           HKDF-SHA256 (RFC 5869) to derive independent keys from one key.
* ``seal_bytes`` / ``open_bytes``
                     authenticated encryption with a **vetted AEAD**: AES-256-GCM (default) or ChaCha20-Poly1305, from the ``cryptography`` package (OpenSSL). Format 2:
                     ``0x02 | algorithm id | key id (4 bytes) | 96-bit random nonce | ciphertext || 128-bit tag``. The whole header is authenticated together with the caller's associated data, so a changed
                     algorithm or key id is a failed authentication, never a silent downgrade. Nonces are random; a per-key invocation count refuses to seal more than 2**32 messages under one key (NIST SP 800-38D) so
                     that the key has to be rotated (the count lives in this process: a restarted process starts again, a limit stated in docs/TEOO.md). If the library is missing, sealing **fails closed**
                     (``CryptoUnavailable``): the old construction is never used for new data.
                     Format 1 (the earlier stdlib encrypt-then-MAC construction, **not vetted**) can still be *opened* so that existing data can be migrated; it is never written (``legacy_seal_v1`` exists only so that tests can
                     make old data).
* ``Lamport``        a hash-based one-time signature (Lamport, SHA-256): a real public-key signature property (verification needs no secret) from a hash function alone, with the limits of
                     one-time keys. ``CheckpointAuthority`` chains the keys (each signed checkpoint commits to the hash of the next public key) so that a trust anchor (the hash of the first public key)
                     published outside the vault is enough to verify a whole series of checkpoints. Key storage, anchor distribution and revocation are not solved here.

Still open: key custody (no KMS or hardware module), review of the integration by a cryptographer, and the persistence of the invocation count.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

CIPHER_NAME = "AES-256-GCM / ChaCha20-Poly1305 (cryptography package), format 2"
FORMAT = 2
ALGORITHMS = {1: "AES-256-GCM", 2: "ChaCha20-Poly1305"}
MAX_MESSAGES_PER_KEY = 2**32
HEADER_LEN = 6  # format, algorithm, key id (4)
AEAD_NONCE_LEN = 12
# format 1 (legacy, open only)
VERSION = b"\x01"
NONCE_LEN, TAG_LEN = 16, 32


class AuthError(Exception):
    """Authentication failed (wrong key, tampered ciphertext, header or associated data). Carries no data about the content."""


class CryptoUnavailable(Exception):
    """The AEAD library is not installed: nothing is sealed (there is no fallback)."""


class KeyExhausted(Exception):
    """A key has sealed the maximum number of messages: rotate it."""


def _aead(alg: int, key: bytes):  # type: ignore[no-untyped-def]
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
    except ImportError:
        raise CryptoUnavailable("the 'cryptography' package is required to seal data") from None
    return AESGCM(key) if alg == 1 else ChaCha20Poly1305(key)


def have_aead() -> bool:
    try:
        _aead(1, b"\x00" * 32)
    except CryptoUnavailable:
        return False
    return True


_COUNTS: dict[bytes, int] = {}


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


def _legacy_tag(k_mac: bytes, nonce: bytes, aad: bytes, ct: bytes) -> bytes:
    return hmac.digest(k_mac, VERSION + nonce + len(aad).to_bytes(8, "big") + aad + len(ct).to_bytes(8, "big") + ct, "sha256")


def legacy_seal_v1(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Format 1, for tests that need old data. Never used by the vault."""
    k_enc, k_mac = hkdf(key, b"teoo/enc"), hkdf(key, b"teoo/mac")
    nonce = secrets.token_bytes(NONCE_LEN)
    ct = _xor(plaintext, _keystream(k_enc, nonce, len(plaintext)))
    return VERSION + nonce + ct + _legacy_tag(k_mac, nonce, aad, ct)


def _legacy_open(key: bytes, blob: bytes, aad: bytes) -> bytes:
    if len(blob) < 1 + NONCE_LEN + TAG_LEN:
        raise AuthError("malformed ciphertext")
    nonce, ct, tag = blob[1:1 + NONCE_LEN], blob[1 + NONCE_LEN:-TAG_LEN], blob[-TAG_LEN:]
    k_enc, k_mac = hkdf(key, b"teoo/enc"), hkdf(key, b"teoo/mac")
    if not hmac.compare_digest(tag, _legacy_tag(k_mac, nonce, aad, ct)):
        raise AuthError("authentication failed")
    return _xor(ct, _keystream(k_enc, nonce, len(ct)))


def blob_info(blob: bytes) -> dict:
    """What a blob says about itself (not authenticated until it is opened): its format, algorithm and key id."""
    if blob[:1] == VERSION:
        return {"format": 1, "algorithm": "HMAC-SHA256-CTR + HMAC-SHA256 (legacy, not vetted)", "key_id": None, "legacy": True}
    if len(blob) >= HEADER_LEN and blob[0] == FORMAT and blob[1] in ALGORITHMS:
        return {"format": 2, "algorithm": ALGORITHMS[blob[1]], "key_id": int.from_bytes(blob[2:6], "big"), "legacy": False}
    return {"format": None, "algorithm": None, "key_id": None, "legacy": False}


def seal_bytes(key: bytes, plaintext: bytes, aad: bytes = b"", *, key_id: int = 0, alg: int = 1) -> bytes:
    if len(key) != 32:
        raise ValueError("the key is 32 bytes")
    if alg not in ALGORITHMS or not 0 <= key_id < 2**32:
        raise ValueError("unknown algorithm or key id")
    fp = hashlib.sha256(b"teoo/count" + key).digest()[:8]
    if _COUNTS.get(fp, 0) >= MAX_MESSAGES_PER_KEY:
        raise KeyExhausted("this key has sealed the maximum number of messages; rotate it")
    cipher = _aead(alg, key)
    _COUNTS[fp] = _COUNTS.get(fp, 0) + 1
    head = bytes([FORMAT, alg]) + key_id.to_bytes(4, "big")
    nonce = secrets.token_bytes(AEAD_NONCE_LEN)
    return head + nonce + cipher.encrypt(nonce, plaintext, head + len(aad).to_bytes(8, "big") + aad)


def open_bytes(key: bytes | dict[int, bytes], blob: bytes, aad: bytes = b"", *, allow_legacy: bool = True) -> bytes:
    """Open a blob. ``key`` is one key, or a ring {key id: key} from which the blob's header selects (an id that is not in the ring fails). Every failure is an ``AuthError`` with no detail about the content."""
    if blob[:1] == VERSION:
        if not allow_legacy or isinstance(key, dict):
            raise AuthError("legacy format refused")
        return _legacy_open(key, blob, aad)
    if len(blob) < HEADER_LEN + AEAD_NONCE_LEN + 16 or blob[0] != FORMAT or blob[1] not in ALGORITHMS:
        raise AuthError("malformed ciphertext")
    head, nonce, body = blob[:HEADER_LEN], blob[HEADER_LEN:HEADER_LEN + AEAD_NONCE_LEN], blob[HEADER_LEN + AEAD_NONCE_LEN:]
    k = key.get(int.from_bytes(head[2:6], "big")) if isinstance(key, dict) else key
    if k is None or len(k) != 32:
        raise AuthError("authentication failed")
    try:
        return _aead(blob[1], k).decrypt(nonce, body, head + len(aad).to_bytes(8, "big") + aad)
    except CryptoUnavailable:
        raise
    except Exception:  # noqa: BLE001 - any failure of the AEAD is an authentication failure; nothing about the cause is disclosed
        raise AuthError("authentication failed") from None


def seal_json(key: bytes, obj: Any, aad: bytes = b"", *, key_id: int = 0, alg: int = 1) -> bytes:
    return seal_bytes(key, json.dumps(obj, sort_keys=True, separators=(",", ":")).encode(), aad, key_id=key_id, alg=alg)


def open_json(key: bytes | dict[int, bytes], blob: bytes, aad: bytes = b"", *, allow_legacy: bool = True) -> Any:
    return json.loads(open_bytes(key, blob, aad, allow_legacy=allow_legacy))


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
