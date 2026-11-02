"""Add the figure metadata (ASCII JSON) to the PNGs that the browser made from the SVGs, check them, and remove the raw files. Run: PYTHONPATH=. python scripts/teoo_phase4_png.py FIG_DIR
The pixels are the browser's rasterisation of the SVG; they are not examined here (inspect_png reads the chunk and its digest)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from xzr.teoo import export as EX


def main() -> None:
    d = Path(sys.argv[1])
    for raw in sorted(d.glob("*.raw.png")):
        name = raw.name.replace(".raw.png", "")
        md = json.loads((d / f"{name}.metadata.json").read_text())
        png = EX.png_add_text(raw.read_bytes(), EX.TEXT_KEY, EX.metadata_ascii(md))
        info = EX.inspect_png(png)
        assert info["ok"] and info["metadata"] == md, (name, info["issues"])
        (d / f"{name}.png").write_bytes(png)
        raw.unlink()
        print(name, info["width"], info["height"], info["metadata"]["evidence"]["classes"])


if __name__ == "__main__":
    main()
