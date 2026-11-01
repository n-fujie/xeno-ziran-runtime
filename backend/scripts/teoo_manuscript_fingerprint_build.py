"""Build xzr/teoo/manuscript_fingerprint.json from the private sources: python scripts/teoo_manuscript_fingerprint_build.py SOURCE.docx|.py|.txt ...

Reads the files (kept outside the repository), writes only the sampled SHA-256 prefixes of their eight-word runs (see xzr.teoo.manuscript_guard) and the SHA-256 of each source file.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

from xzr.teoo import manuscript_guard as G


def text_of(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        z = zipfile.ZipFile(path)
        parts = [re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", z.read(n).decode("utf8", "ignore"))) for n in z.namelist() if n.startswith("word/") and n.endswith(".xml") and any(k in n for k in ("document", "footnotes", "endnotes", "header", "footer"))]
        return "\n".join(parts)
    return path.read_text()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    digests: set[str] = set()
    sources = {}
    for a in sys.argv[1:]:
        p = Path(a).expanduser()
        digests |= set(G.sampled(G.words(text_of(p))).values())
        sources[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    G.FILE.write_text(json.dumps({"note": "sampled SHA-256 prefixes of eight-word runs of the unpublished sources; they cannot be turned back into text (xzr.teoo.manuscript_guard)",
                                  "n": G.N, "sample": G.SAMPLE, "sources_sha256": sources, "digests": sorted(digests)}, separators=(",", ":")) + "\n")
    print("wrote", G.FILE, len(digests), "digests from", len(sources), "sources")


if __name__ == "__main__":
    main()
