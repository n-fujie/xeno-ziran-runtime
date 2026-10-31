"""Consent records and the purposes they allow.

A consent is granted by a subject (known here only by pseudonym) for a list of purposes and data classes, with an optional expiry. It is never edited or removed: a revocation is a new entry. A use of data is
allowed only if an active consent covers its purpose and data class at the time of use. Consent for ``external-transmission`` must be granted explicitly; nothing implies it."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from .chainlog import ChainLog

PURPOSES = ("protocol-execution", "analysis", "figure-export", "external-transmission", "reproduction-check")
DATA_CLASSES = ("observation", "media", "reconstruction")


class ConsentLog:
    def __init__(self, path: Path | None = None, clock: Callable[[], float] = time.time):
        self.log, self.clock = ChainLog(path), clock

    def grant(self, subject: str, purposes: list[str], data_classes: list[str], *, expires_at: float | None = None, version: str = "1", protocol_id: str | None = None) -> str:
        if not purposes or not set(purposes) <= set(PURPOSES) or not data_classes or not set(data_classes) <= set(DATA_CLASSES):
            raise ValueError(f"purposes must be a non-empty subset of {PURPOSES} and data classes of {DATA_CLASSES}")
        cid = f"cns-{len(self.log.entries) + 1:06d}"
        self.log.append({"type": "grant", "id": cid, "subject": subject, "purposes": sorted(purposes), "data_classes": sorted(data_classes), "expires_at": expires_at, "version": version, "protocol_id": protocol_id, "at": self.clock()})
        return cid

    def revoke(self, subject: str, consent_id: str, reason: str = "") -> None:
        if not any(b["type"] == "grant" and b["id"] == consent_id and b["subject"] == subject for b in self.log.bodies()):
            raise ValueError("no such consent for this subject")
        self.log.append({"type": "revoke", "id": consent_id, "subject": subject, "reason_code": reason[:40], "at": self.clock()})

    def active(self, subject: str, purpose: str, data_class: str, at: float | None = None) -> str | None:
        """The id of an active consent that covers the purpose and data class, or None."""
        t = self.clock() if at is None else at
        revoked = {b["id"] for b in self.log.bodies() if b["type"] == "revoke" and b["subject"] == subject and b["at"] <= t}
        for b in self.log.bodies():
            if b["type"] == "grant" and b["subject"] == subject and b["id"] not in revoked and purpose in b["purposes"] and data_class in b["data_classes"] and b["at"] <= t and (b["expires_at"] is None or b["expires_at"] > t):
                return b["id"]
        return None

    def history(self, subject: str) -> list[dict]:
        return [b for b in self.log.bodies() if b["subject"] == subject]
