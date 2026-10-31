"""Access control and authentication for the local vault.

* Passwords are stored as scrypt hashes with a random salt; a login against an unknown user costs the same as one against a known user; five failures lock the account for a period.
* A token is ``v1.<payload>.<mac>``: the payload (user, role, expiry, id) is signed with a server secret (HMAC-SHA256); it expires, can be revoked, and its verification is constant time.
* A role is a set of permissions; every vault operation names the permission it needs. The researcher role cannot read identities; only the steward can, and every such read is audited.
* The audit log is hash-chained and carries user names (staff), subject pseudonyms and codes; never identities, passwords, tokens or data values.

What this is: a local, verifiable mechanism. What it is not: an external identity provider, multi-factor authentication, session binding to a device, or protection against someone with the server
secret or access to the machine's memory."""

from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .chainlog import ChainLog
from .crypto import kdf

PERMISSIONS = ("user.manage", "subject.enroll", "consent.record", "consent.revoke", "data.write", "data.read", "identity.read", "subject.delete", "audit.read", "ledger.verify", "checkpoint.sign")
ROLES: dict[str, frozenset[str]] = {
    "steward": frozenset({"user.manage", "subject.enroll", "consent.record", "consent.revoke", "identity.read", "subject.delete", "audit.read", "ledger.verify", "checkpoint.sign"}),
    "researcher": frozenset({"data.write", "data.read", "ledger.verify"}),
    "reviewer": frozenset({"audit.read", "ledger.verify"}),
}
MIN_PASSWORD = 12


class AccessDenied(Exception):
    """Carries a code only (never the user's input)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Principal:
    user: str
    role: str
    jti: str
    exp: float

    def can(self, permission: str) -> bool:
        return permission in ROLES.get(self.role, frozenset())


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class AuthService:
    def __init__(self, root: Path | None = None, *, clock: Callable[[], float] = time.time, token_ttl: float = 3600.0, max_failures: int = 5, lock_s: float = 300.0, scrypt_n: int = 2**14):
        self.root, self.clock, self.token_ttl, self.max_failures, self.lock_s, self.n = (Path(root) if root else None), clock, token_ttl, max_failures, lock_s, scrypt_n
        self.users: dict[str, dict] = {}
        self.revoked: set[str] = set()
        self.audit = ChainLog(self.root / "audit.jsonl" if self.root else None)
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)
            kf = self.root / "auth.key"
            if not kf.exists():
                fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.write(fd, secrets.token_bytes(32))
                os.close(fd)
            self._secret = kf.read_bytes()
            uf = self.root / "users.json"
            if uf.exists():
                self.users = json.loads(uf.read_text())
        else:
            self._secret = secrets.token_bytes(32)
        self._dummy = kdf(b"dummy", b"\x00" * 16, n=self.n)

    def _save(self) -> None:
        if self.root:
            tmp = self.root / "users.json.tmp"
            tmp.write_text(json.dumps(self.users, sort_keys=True))
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.root / "users.json")

    def log(self, actor: str, action: str, outcome: str, object_id: str = "", code: str = "") -> None:
        self.audit.append({"at": self.clock(), "actor": actor, "action": action, "outcome": outcome, "object": object_id, "code": code})

    def add_user(self, name: str, password: str, role: str, by: Principal | None = None) -> None:
        if self.users and (by is None or not by.can("user.manage")):
            self.log(by.user if by else "-", "user.add", "denied", code="PERMISSION")
            raise AccessDenied("PERMISSION")
        if role not in ROLES:
            raise AccessDenied("UNKNOWN_ROLE")
        if len(password) < MIN_PASSWORD or name in self.users or not name:
            raise AccessDenied("WEAK_PASSWORD_OR_DUPLICATE_USER")
        salt = secrets.token_bytes(16)
        self.users[name] = {"salt": salt.hex(), "hash": kdf(password.encode(), salt, n=self.n).hex(), "role": role, "failures": 0, "locked_until": 0.0}
        self._save()
        self.log(by.user if by else "bootstrap", "user.add", "ok", object_id=name)

    def login(self, name: str, password: str) -> str:
        now = self.clock()
        u = self.users.get(name)
        if u is None:
            hmac.compare_digest(kdf(password.encode(), b"\x00" * 16, n=self.n), self._dummy)  # the same work as for a known user
            self.log("-", "login", "denied", code="CREDENTIALS")
            raise AccessDenied("CREDENTIALS")
        if u["locked_until"] > now:
            self.log(name, "login", "denied", code="LOCKED")
            raise AccessDenied("LOCKED")
        ok = hmac.compare_digest(kdf(password.encode(), bytes.fromhex(u["salt"]), n=self.n).hex(), u["hash"])
        if not ok:
            u["failures"] += 1
            if u["failures"] >= self.max_failures:
                u["locked_until"], u["failures"] = now + self.lock_s, 0
            self._save()
            self.log(name, "login", "denied", code="CREDENTIALS")
            raise AccessDenied("CREDENTIALS")
        u["failures"] = 0
        self._save()
        payload = {"sub": name, "role": u["role"], "exp": now + self.token_ttl, "jti": secrets.token_hex(8)}
        body = _b64(json.dumps(payload, sort_keys=True).encode())
        mac = _b64(hmac.digest(self._secret, body.encode(), "sha256"))
        self.log(name, "login", "ok", object_id=payload["jti"])
        return f"v1.{body}.{mac}"

    def authenticate(self, token: str) -> Principal:
        try:
            v, body, mac = token.split(".")
            if v != "v1" or not hmac.compare_digest(_b64(hmac.digest(self._secret, body.encode(), "sha256")), mac):
                raise ValueError
            p = json.loads(_unb64(body))
        except Exception:  # noqa: BLE001 - any failure to read a token is a denial, whatever its cause; the reason is not disclosed
            self.log("-", "authenticate", "denied", code="TOKEN_INVALID")
            raise AccessDenied("TOKEN_INVALID") from None
        if p["exp"] <= self.clock():
            self.log(p["sub"], "authenticate", "denied", object_id=p["jti"], code="TOKEN_EXPIRED")
            raise AccessDenied("TOKEN_EXPIRED")
        if p["jti"] in self.revoked or p["sub"] not in self.users:
            self.log(p["sub"], "authenticate", "denied", object_id=p["jti"], code="TOKEN_REVOKED")
            raise AccessDenied("TOKEN_REVOKED")
        return Principal(p["sub"], self.users[p["sub"]]["role"], p["jti"], p["exp"])

    def revoke(self, token: str) -> None:
        p = self.authenticate(token)
        self.revoked.add(p.jti)
        self.log(p.user, "logout", "ok", object_id=p.jti)

    def require(self, token: str, permission: str) -> Principal:
        p = self.authenticate(token)
        if not p.can(permission):
            self.log(p.user, permission, "denied", code="PERMISSION")
            raise AccessDenied("PERMISSION")
        return p
