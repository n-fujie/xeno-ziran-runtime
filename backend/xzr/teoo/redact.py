"""Keeping sensitive information out of logs and error messages.

Two defences: (1) nothing sensitive is passed to a log in the first place (the audit log and the errors of the vault carry identifiers and codes only), and (2) ``redact`` and
``RedactingFilter`` remove what still gets through: values under sensitive keys, e-mail addresses, long digit strings that look like phone numbers, and tokens. Redaction is a safety net,
not a guarantee: the tests plant canary strings and look for them in every log, file and exception message the vault produces."""

from __future__ import annotations

import logging
import re
from typing import Any

SENSITIVE_KEYS = {"name", "full_name", "email", "phone", "address", "birthdate", "dob", "identity", "password", "passphrase", "secret", "token", "key", "api_key", "note", "contact", "id_number"}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,}\d(?!\w)")
_TOKEN = re.compile(r"\bv1\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b")
MASK = "[REDACTED]"


def redact_text(s: str) -> str:
    return _TOKEN.sub(MASK, _EMAIL.sub(MASK, _PHONE.sub(MASK, s)))


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: (MASK if str(k).lower() in SENSITIVE_KEYS else redact(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


class RedactingFilter(logging.Filter):
    """Attach to a logger or handler: the message and its arguments are redacted before they are formatted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg))
        if record.args:
            record.args = tuple(redact(a) if isinstance(a, (dict, list, tuple, str)) else a for a in (record.args if isinstance(record.args, tuple) else (record.args,)))
        return True


def safe_error(e: BaseException) -> str:
    """What may be shown or logged about an error: its class and, for the vault's own errors, their code. Never the message of an arbitrary exception (it may carry data)."""
    code = getattr(e, "code", None)
    return f"{type(e).__name__}:{code}" if code else type(e).__name__
