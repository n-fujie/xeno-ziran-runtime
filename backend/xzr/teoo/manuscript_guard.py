"""A guard that detects sentences of the unpublished manuscripts in the public tree, without holding them.

``manuscript_fingerprint.json`` holds only SHA-256 prefixes of a sample (one in eight) of the eight-word runs of the sources. The prefixes cannot be turned back into text, but a passage of the sources that is
copied into any file produces several of them in a short stretch of words, which is what ``find_passages`` reports (word positions only, never the text). Titles, citations and short phrases produce at most one or
two hits and are allowed; the rule is ``MIN_HITS`` hits within ``WINDOW`` words. It is a tripwire against copying passages, not a proof that no wording of the sources is present.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

N = 8
SAMPLE = 8
WINDOW = 64
MIN_HITS = 3
FILE = Path(__file__).with_name("manuscript_fingerprint.json")
_WORD = re.compile(r"[a-z0-9぀-ヿ一-鿿][a-z0-9'぀-ヿ一-鿿-]*")


def words(text: str) -> list[str]:
    t = unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("‘", "'")
    return _WORD.findall(t)


def digest(shingle: str) -> str:
    return hashlib.sha256(shingle.encode()).hexdigest()[:10]


def sampled(ws: list[str]) -> dict[int, str]:
    """word position -> digest, for the sampled eight-word runs of a word list."""
    out = {}
    for i in range(len(ws) - N + 1):
        d = digest(" ".join(ws[i:i + N]))
        if int(d, 16) % SAMPLE == 0:
            out[i] = d
    return out


@lru_cache(maxsize=1)
def fingerprint() -> frozenset[str]:
    return frozenset(json.loads(FILE.read_text())["digests"])


def find_passages(text: str, fp: frozenset[str] | None = None) -> list[dict]:
    """Stretches of ``text`` that carry at least MIN_HITS sampled runs of the sources within WINDOW words: [{'word_start', 'hits'}]. Never returns text."""
    fp = fingerprint() if fp is None else fp
    pos = [i for i, d in sampled(words(text)).items() if d in fp]
    out, i = [], 0
    while i < len(pos):
        j = i
        while j + 1 < len(pos) and pos[j + 1] - pos[i] < WINDOW:
            j += 1
        if j - i + 1 >= MIN_HITS:
            out.append({"word_start": pos[i], "hits": j - i + 1})
            i = j + 1
        else:
            i += 1
    return out
