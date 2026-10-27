"""Compare the XENO ECOSYSTEM captures with the supplied reference images on simple, stated image statistics.

    python backend/scripts/visual_compare.py --captures docs/ecosystem/visual --refs ref1.webp ref2.webp ... --out docs/ecosystem/visual/metrics.json

Images are decoded by the system tool ``sips`` (to uncompressed BMP) so that nothing beyond numpy is needed. The statistics are crude proxies, not a perceptual
judgement, and the reference images themselves are not stored in the repository:

  luminance mean / std   overall tone and contrast
  chroma                 mean (max(R,G,B) - min(R,G,B)) / 255: 0 is strictly monochrome
  detail density         share of pixels whose luminance gradient exceeds 0.06 (fine structure per area)
  fine/coarse            detail density at full resolution over that at 1/4 resolution (large = micro-structure, small = large smooth shapes)
  uniformity             1 - (std/mean) of the detail density over a 3x3 grid (1 = detail everywhere, as in a dense lattice; low = detail concentrated)
  dark share             share of pixels below 0.08 luminance (the black ground of the reference imagery)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np


def load(path: Path) -> np.ndarray:
    """Decode any image the system can read to an (h, w, 3) float array in 0..1."""
    with tempfile.TemporaryDirectory() as d:
        bmp = Path(d) / "x.bmp"
        subprocess.run(["sips", "-s", "format", "bmp", str(path), "--out", str(bmp)], check=True, capture_output=True)
        b = bmp.read_bytes()
    off = int.from_bytes(b[10:14], "little")
    w = int.from_bytes(b[18:22], "little", signed=True)
    h = int.from_bytes(b[22:26], "little", signed=True)
    bpp = int.from_bytes(b[28:30], "little")
    bytes_pp = bpp // 8
    stride = ((w * bpp + 31) // 32) * 4
    rows = np.frombuffer(b, dtype=np.uint8, count=stride * abs(h), offset=off).reshape(abs(h), stride)[:, : w * bytes_pp].reshape(abs(h), w, bytes_pp)
    img = rows[:, :, [2, 1, 0]].astype(np.float64) / 255.0  # BGR(A) -> RGB
    return img[::-1] if h > 0 else img


def grad(lum: np.ndarray) -> np.ndarray:
    gx = np.abs(np.diff(lum, axis=1))[:-1, :]
    gy = np.abs(np.diff(lum, axis=0))[:, :-1]
    return np.maximum(gx, gy)


def metrics(img: np.ndarray) -> dict:
    lum = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
    chroma = float((img.max(axis=2) - img.min(axis=2)).mean())
    dens = float((grad(lum) > 0.06).mean())
    h, w = lum.shape
    small = lum[: h - h % 4, : w - w % 4].reshape(h // 4, 4, w // 4, 4).mean(axis=(1, 3))
    dens_small = float((grad(small) > 0.06).mean())
    g = grad(lum) > 0.06
    cells = [g[i * g.shape[0] // 3 : (i + 1) * g.shape[0] // 3, j * g.shape[1] // 3 : (j + 1) * g.shape[1] // 3].mean() for i in range(3) for j in range(3)]
    return {
        "size": [w, h],
        "luminance_mean": round(float(lum.mean()), 4),
        "luminance_std": round(float(lum.std()), 4),
        "chroma": round(chroma, 4),
        "detail_density": round(dens, 4),
        "fine_over_coarse": round(dens / max(dens_small, 1e-6), 3),
        "uniformity": round(1 - float(np.std(cells) / max(np.mean(cells), 1e-6)), 4),
        "dark_share": round(float((lum < 0.08).mean()), 4),
    }


KEYS = ["luminance_mean", "luminance_std", "chroma", "detail_density", "uniformity", "dark_share"]


def distance(a: dict, b: dict) -> float:
    return float(np.sqrt(sum((a[k] - b[k]) ** 2 for k in KEYS)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", required=True)
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    refs = {Path(r).stem: metrics(load(Path(r))) for r in a.refs}
    caps = {p.stem: metrics(load(p)) for p in sorted(Path(a.captures).glob("*.png"))}
    rows = {}
    for name, m in caps.items():
        d = {r: round(distance(m, rm), 4) for r, rm in refs.items()}
        rows[name] = {"metrics": m, "distance_to_reference": d, "nearest_reference": min(d, key=d.get)}
    out = {"statistics": KEYS, "references": refs, "captures": rows, "note": "crude image statistics, not a perceptual judgement; see the module docstring"}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {"nearest": v["nearest_reference"], "d": min(v["distance_to_reference"].values()), **v["metrics"]} for k, v in rows.items()}, indent=0)[:2500])
    print("references", json.dumps(refs, indent=0)[:1500])


if __name__ == "__main__":
    main()
