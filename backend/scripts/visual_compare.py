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

and, added in the second stage (each a stated proxy for the quality named; none is a perceptual judgement and none establishes a match):

  luminance histogram    share of pixels in eight equal luminance bins (tonal distribution, compared by total-variation distance)
  edge density           share of pixels whose Sobel gradient magnitude exceeds 0.15 (linework and boundaries, as against the 0.06 threshold of "detail density")
  spatial frequency      share of the image's (mean-removed) spectral power above a quarter of the Nyquist radius, and above half of it (fine structure against large shapes)
  occupied-area ratio    share of pixels that are not background (luminance above 0.08 after removing the 5th-percentile floor): how much of the frame the structure fills
  depth proxy            normalised entropy of the 1/16-resolution luminance (tonal layers: distinct atmospheric or occlusion bands), 0 = one tone, 1 = all tones equally used
  silhouette density     length of the boundary of the occupied mask per occupied pixel, at 1/2 resolution (how broken or complicated the outline is: a solid blob is low)
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


def sobel(lum: np.ndarray) -> np.ndarray:
    p = np.pad(lum, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.hypot(gx, gy) / 4.0


def extra_metrics(lum: np.ndarray) -> dict:
    h, w = lum.shape
    hist = np.histogram(lum, bins=8, range=(0.0, 1.0))[0] / lum.size
    edge = float((sobel(lum) > 0.15).mean())
    # spatial frequency: power spectrum of the mean-removed luminance, share beyond a quarter and a half of the Nyquist radius
    f = np.fft.fftshift(np.abs(np.fft.fft2(lum - lum.mean())) ** 2)
    yy, xx = np.indices(f.shape)
    rr = np.hypot((yy - h // 2) / (h / 2), (xx - w // 2) / (w / 2))
    tot = float(f.sum()) or 1.0
    hi, vhi = float(f[rr > 0.25].sum() / tot), float(f[rr > 0.5].sum() / tot)
    floor = np.percentile(lum, 5)
    occ = (lum - floor) > 0.08
    occupied = float(occ.mean())
    # depth proxy: entropy of the 1/16-resolution tones
    hh, ww = h - h % 16, w - w % 16
    low = lum[:hh, :ww].reshape(hh // 16, 16, ww // 16, 16).mean(axis=(1, 3))
    lh = np.histogram(low, bins=16, range=(0.0, 1.0))[0].astype(float)
    pr = lh[lh > 0] / lh.sum()
    depth = float(-(pr * np.log(pr)).sum() / np.log(16))
    # silhouette density: boundary pixels of the occupied mask per occupied pixel at 1/2 resolution
    m = occ[: h - h % 2, : w - w % 2].reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3)) > 0.5
    b = (m[1:, :] != m[:-1, :]).sum() + (m[:, 1:] != m[:, :-1]).sum()
    sil = float(b / max(1, m.sum()))
    return {
        "luminance_histogram": [round(float(x), 4) for x in hist],
        "edge_density": round(edge, 4),
        "spatial_frequency_hi": round(hi, 5),
        "spatial_frequency_vhi": round(vhi, 5),
        "occupied_area_ratio": round(occupied, 4),
        "depth_proxy": round(depth, 4),
        "silhouette_density": round(sil, 4),
    }


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
        **extra_metrics(lum),
    }


KEYS = ["luminance_mean", "luminance_std", "chroma", "detail_density", "uniformity", "dark_share"]
KEYS2 = ["edge_density", "occupied_area_ratio", "depth_proxy", "silhouette_density"]


def distance(a: dict, b: dict) -> float:
    """The first-stage distance: root of summed squared differences of the six first-stage statistics (kept so the two stages stay comparable)."""
    return float(np.sqrt(sum((a[k] - b[k]) ** 2 for k in KEYS)))


def distance2(a: dict, b: dict) -> dict:
    """Second-stage distances, kept separate: tone (total variation of the luminance histograms), structure (the four scalar statistics), frequency."""
    tv = 0.5 * float(np.abs(np.array(a["luminance_histogram"]) - np.array(b["luminance_histogram"])).sum())
    st = float(np.sqrt(sum((a[k] - b[k]) ** 2 for k in KEYS2)))
    fr = float(np.sqrt((a["spatial_frequency_hi"] - b["spatial_frequency_hi"]) ** 2 + (a["spatial_frequency_vhi"] - b["spatial_frequency_vhi"]) ** 2))
    return {"tone_tv": round(tv, 4), "structure": round(st, 4), "frequency": round(fr, 5)}


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
        rows[name] = {"metrics": m, "distance_to_reference": d, "nearest_reference": min(d, key=d.get), "distance2_to_reference": {r: distance2(m, rm) for r, rm in refs.items()}}
    out = {"statistics": KEYS, "statistics_stage2": KEYS2 + ["luminance_histogram", "spatial_frequency_hi", "spatial_frequency_vhi"], "references": refs, "captures": rows, "note": "crude image statistics, not a perceptual judgement; see the module docstring"}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {"nearest": v["nearest_reference"], "d": min(v["distance_to_reference"].values()), **v["metrics"]} for k, v in rows.items()}, indent=0)[:2500])
    print("references", json.dumps(refs, indent=0)[:1500])


if __name__ == "__main__":
    main()
