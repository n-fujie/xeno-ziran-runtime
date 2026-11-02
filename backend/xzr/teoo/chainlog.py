"""An append-only, hash-chained JSON-lines log (used for the audit log, the consent log, the vault ledger and the checkpoints). Each entry names the hash of the one before; a change of any earlier
entry breaks every later hash. There is no update or delete. A chain detects a change; it does not prevent a rewrite of the whole file (see the signed checkpoints for that)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ZERO = "0" * 64


def _h(seq: int, prev: str, body: dict) -> str:
    return hashlib.sha256(f"{seq}|{prev}|".encode() + json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class ChainLog:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.entries: list[dict] = []
        if self.path and self.path.exists():
            self.entries = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def head(self) -> str:
        return self.entries[-1]["hash"] if self.entries else ZERO

    def append(self, body: dict[str, Any]) -> dict:
        seq = len(self.entries)
        e = {"seq": seq, "prev": self.head(), "body": body, "hash": _h(seq, self.head(), body)}
        self.entries.append(e)
        if self.path:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, (json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n").encode())
            finally:
                os.close(fd)
        return e

    def verify(self) -> list[str]:
        out, prev = [], ZERO
        for i, e in enumerate(self.entries):
            if e.get("seq") != i or e.get("prev") != prev:
                out.append(f"entry {i}: the chain does not follow")
            if e.get("hash") != _h(i, prev, e.get("body", {})):
                out.append(f"entry {i}: the hash does not match the content")
            prev = e.get("hash", "")
        return out

    def bodies(self) -> list[dict]:
        return [e["body"] for e in self.entries]
