"""The research figure, regenerated from the record: white ground, black and grey lines, one limited institutional blue, the variables, the comparison conditions, the executed intervention results, the limits and the
correspondence to the source data (the digest). One small multiple per condition: the response surface of the operation to the two interventions, in an oblique projection the researcher can change. Nothing is drawn that the
record does not contain, and the figure states what kind of figure it is."""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

BLUE = "#0B3D91"
GREY = "#8a8a8a"
INK = "#111111"


def _iso(x: float, y: float, z: float, nx: int, ny: int, sx: float, sy: float, sz: float, x0: float, y0: float) -> tuple[float, float]:
    u, v = x / max(1, nx - 1), y / max(1, ny - 1)
    px = x0 + (u - v) * math.cos(math.pi / 6) * sx
    py = y0 + (u + v) * math.sin(math.pi / 6) * sy - z * sz
    return px, py


def figure_svg(bundle: dict, snapshot: str = "end") -> str:
    res, shapes = bundle["result"], bundle["shapes"]
    conds = list(res["conditions"])
    cols, cw, ch = 3, 330, 330
    rows = math.ceil(len(conds) / cols)
    W, H = cols * cw + 60, rows * ch + 240
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Helvetica, Arial, sans-serif" role="img" aria-label="GAISHO figure">', f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    out.append(f'<text x="30" y="40" font-size="20" font-weight="700" fill="{INK}">GAISHO / {escape(res["title"])}</text>')
    out.append(f'<line x1="30" y1="52" x2="{W - 30}" y2="52" stroke="{BLUE}" stroke-width="2"/>')
    out.append(f'<text x="30" y="74" font-size="12" fill="{INK}">{escape(bundle["figure_kind"])} · domain {escape(res["domain"])} · model {escape(bundle["model_version"])} · seeds {len(res["seeds"])} (one run per seed is the unit) · observation: {escape(_obs(res["observation"]))}</text>')
    out.append(f'<text x="30" y="92" font-size="12" fill="{GREY}">axes: x = {escape(bundle["axes"]["x"])} · y = {escape(bundle["axes"]["y"])} · height = outcome (share of trials), recorded cells only; moment: {escape(snapshot)}</text>')
    for k, cond in enumerate(conds):
        c0, r0 = k % cols, k // cols
        ox, oy = 30 + c0 * cw, 110 + r0 * ch
        sh = shapes[cond].get(snapshot) or {}
        out.append(f'<text x="{ox}" y="{oy + 14}" font-size="12" font-weight="700" fill="{INK}">{escape(cond[:48])}</text>')
        if not sh.get("recorded"):
            out.append(f'<text x="{ox}" y="{oy + 60}" font-size="12" fill="{GREY}">not recorded: {escape(str(sh.get("reason", "UNMEASURED")))}</text>')
            continue
        nx, ny = sh["nx"], sh["ny"]
        vs = {v["id"]: v for v in sh["vertices"]}
        pos = {}
        for vid, v in vs.items():
            i, j = v["cell"]
            pos[vid] = _iso(i, j, v["z"], nx, ny, 150, 150, 70, ox + 150, oy + 70)
        for e in sh["edges"] + sh["cuts"]:
            if e["a"] in pos and e["b"] in pos:
                cut = e["difference"] >= 0.5
                out.append(f'<line x1="{pos[e["a"]][0]:.1f}" y1="{pos[e["a"]][1]:.1f}" x2="{pos[e["b"]][0]:.1f}" y2="{pos[e["b"]][1]:.1f}" stroke="{INK if cut else GREY}" stroke-width="{1.1 if cut else 0.6}"/>')
        for b in sh["branch"]:
            i = (b["x"] - sh["vertices"][0]["x"]) / max(1e-9, (sh["vertices"][-1]["x"] - sh["vertices"][0]["x"]))
            bx, by = _iso(i * (nx - 1), (b["y"] - min(v["y"] for v in sh["vertices"])) / max(1e-9, max(v["y"] for v in sh["vertices"]) - min(v["y"] for v in sh["vertices"])) * (ny - 1), 0.5, nx, ny, 150, 150, 70, ox + 150, oy + 70)
            out.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="2.2" fill="{BLUE}"/>')
        if sh["unresolved"]:
            out.append(f'<text x="{ox + 4}" y="{oy + 300}" font-size="10" fill="{GREY}">unresolved cells: {len(sh["unresolved"])} ({escape(sorted({x["reason"] for x in sh["unresolved"]})[0])}…)</text>')
        v = res["conditions"][cond]
        fmt = lambda n, v=v: ("n/a" if v["relations"][n]["status"] != "IDENTIFIED" else f'{v["relations"][n]["value"]:+.2f}')  # noqa: E731
        names = list(v["relations"])
        out.append(f'<text x="{ox}" y="{oy + 316}" font-size="10" fill="{INK}">{escape(" · ".join(f"{n} {fmt(n)}" for n in names[:4]))}</text>')
    y = H - 100
    out.append(f'<line x1="30" y1="{y}" x2="{W - 30}" y2="{y}" stroke="{GREY}" stroke-width="0.6"/>')
    for t, line in enumerate((f'Limits: {bundle["limits"]}', "Blue points: where the response crosses 0.5 (reconstructed from the recorded cells). Black segments: neighbouring cells whose responses differ by at least 0.5 (a cut). Grey: other neighbours. Not drawn: unrecorded cells (listed).", f'Source: record digest {bundle["digest"][:16]} · result digest {res["digest"][:16]} · regenerate with xzr.gaisho.figure.figure_svg(record). Negative results kept in the record: {len(bundle["negative_results"])}.')):
        out.append(f'<text x="30" y="{y + 20 + t * 18}" font-size="10" fill="{INK}">{escape(line[:230])}</text>')
    out.append("</svg>")
    return "\n".join(out)


def _obs(o: dict) -> str:
    diff = {k: v for k, v in o.items() if v not in ((), [], 0, 0.0, 1, "default", "intervened", True, 40, 10000, ("x", "y", "memory")) and k != "sensor_channels"}
    return ", ".join(f"{k}={v}" for k, v in diff.items()) or "full (defaults)"
