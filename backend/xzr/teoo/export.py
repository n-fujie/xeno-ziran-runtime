"""Figures and research records: SVG, PNG and JSON metadata, with the evidence class built into the figure.

Every figure carries (1) a visible evidence band (the classes of the records behind it, whether any real-world experiment is recorded, the body configuration version, the record ids, the time of generation) and (2) a
diagonal watermark for each class that is not MEASURED (SYNTHETIC, RECONSTRUCTED_ESTIMATE, CONCEPTUAL). Both are produced by the renderer unconditionally and are part of the SVG, so they cannot be switched off by an option; ``verify_svg`` checks that
they are present and that the metadata embedded in the SVG matches its digest. The same metadata (as JSON) is embedded in the SVG and, by the browser's PNG export, in a PNG text chunk (``inspect_png`` reads and checks it).
A figure is reproducible from its source data: the same data, records, body and ``generated_at`` give the same bytes; ``source_digest`` identifies the data independently of when the figure was made.

What a check can and cannot tell: the SVG band and watermark are verified as text in the SVG; the pixels of a PNG made from it are not examined (the PNG check reads its metadata chunk and its digest).
A photograph is never produced here: images in a figure are shown only with ``media.presentation_label``.
"""

from __future__ import annotations

import json
import re
import struct
import zlib
from typing import Any
from xml.sax.saxutils import escape

from . import TEOO_VERSION
from .provenance import digest_of

WATERMARK_CLASSES = ("SYNTHETIC", "RECONSTRUCTED_ESTIMATE", "CONCEPTUAL")
W, H, BAND = 800, 420, 78
STATUS_FILL = {"MEASURED_VALID": "#cfd6e4", "MISSING": "#ff8a70", "INVALID": "#ff5a4a", "BOUNDARY_INVISIBLE": "#c9a227", "TIME_WINDOW_MISMATCH": "#9bb0d0", "INSTRUMENT_MISMATCH": "#b07acc",
               "SIGNAL_BELOW_THRESHOLD": "#78e696", "SCALE_MISMATCH": "#7ad0d0", "UNMEASURED": "#555", "UNMEASURABLE": "#777", "UNKNOWN_CAUSE": "#fff"}
CLASS_FILL = {"measured": "#e8e8ec", "synthetic": "#5a6b86", "estimated": "#c9a227", "conceptual": "#8a8a92", "unmeasured": "#222", "limited": "#ff8a70"}


def classes_of(records: list[dict], extra: tuple[str, ...] = ()) -> list[str]:
    return sorted({c for r in records for c in r["lineage_classes"]} | set(extra))


def figure_metadata(kind: str, title: str, data: Any, records: list[dict], *, body: dict | None = None, observation: dict | None = None, protocol: dict | None = None, generated_at: str,
                    extra_classes: tuple[str, ...] = (), units: dict | None = None) -> dict:
    cls = classes_of(records, extra_classes)
    real = any(r["provenance"] == "MEASURED" for r in records)
    ver = None if body is None else body["versions"][-1]
    src = digest_of({"kind": kind, "data": data, "records": [(r["record_id"], r["record_digest"]) for r in records], "body": ver and ver["digest"], "protocol": protocol and (protocol["experiment_id"], protocol["version"])})
    band = [f"EVIDENCE: {' + '.join(cls) or 'none'}" + ("  ·  " + {"SYNTHETIC": "artificial functional-test data, not a measurement", "RECONSTRUCTED_ESTIMATE": "an estimate, not an observation", "CONCEPTUAL": "a drawing, not data"}.get(cls[0], "") if len(cls) == 1 and cls else ""),
            "REAL-WORLD EXPERIMENT: " + ("MEASURED records are present (declared by their source; not verified here)" if real else "none recorded (no measurement exists behind this figure)"),
            f"BODY: {body['id']} v{ver['version']} ({ver['digest'][:10]})" if body and ver else "BODY: none",
            f"RECORDS: {', '.join(r['record_id'] for r in records)[:96]}  ·  generated {generated_at}  ·  TEOO {TEOO_VERSION}"]
    md = {"schema": "teoo.figure/1", "figure_id": "fig-" + src[:16], "kind": kind, "title": title, "generated_at": generated_at, "teoo_version": TEOO_VERSION,
          "evidence": {"classes": cls, "watermarks": [c for c in WATERMARK_CLASSES if c in cls], "real_world_experiment_recorded": real, "band": band},
          "experiment": None if protocol is None else {"protocol_id": protocol["experiment_id"], "version": protocol["version"], "seeds": protocol["seeds"], "conditions": protocol["conditions"], "trials_per_condition": protocol["trials_per_condition"]},
          "provenance": {"records": [{"record_id": r["record_id"], "provenance": r["provenance"], "kind": r["kind"], "lineage_classes": r["lineage_classes"], "record_digest": r["record_digest"]} for r in records], "source_digest": src},
          "observation_limits": None if observation is None else {"config_version": observation.get("version"), "t": observation.get("t"), "summary": observation.get("summary"), "note": observation.get("claim_note")},
          "body": None if body is None or ver is None else {"id": body["id"], "version": ver["version"], "digest": ver["digest"], "preset": body.get("meta", {}).get("preset")}, "units": units or {},
          "claim": "an illustration of the stated data under the stated conditions; no claim beyond them"}
    md["metadata_digest"] = digest_of({k: v for k, v in md.items() if k != "metadata_digest"})
    return md


# ------------------------------------------------------------------------------------------------ drawings (inside the 800 x (420 - band) area)
def _timeseries(d: dict) -> str:
    ch = d["channel"]
    t, s = ch["times"], ch["samples"]
    vals = [x["value"] for x in s if x["status"] == "MEASURED_VALID" and x["value"] is not None]
    est = d.get("estimate")
    allv = vals + (est["values"] if est else [])
    lo, hi = (min(allv), max(allv)) if allv else (0.0, 1.0)
    hi = hi if hi > lo else lo + 1
    x0, x1, y0, y1 = 60, W - 20, 30, H - BAND - 70
    tx = lambda v: x0 + (v - t[0]) / ((t[-1] - t[0]) or 1) * (x1 - x0)  # noqa: E731
    vy = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)  # noqa: E731
    out = [f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="#45454c"/>', f'<text x="{x0}" y="18" fill="#d8d8dc" font-size="12">{escape(d.get("label", ch["variable"]))} [{escape(str(ch.get("unit")))}]  ·  device time (s)</text>']
    seg: list[str] = []
    for i, x in enumerate(s):
        if x["status"] == "MEASURED_VALID" and x["value"] is not None:
            seg.append(f"{tx(t[i]):.1f},{vy(x['value']):.1f}")
        elif seg:
            out.append(f'<polyline points="{" ".join(seg)}" fill="none" stroke="#e8e8ec" stroke-width="1.2"/>')
            seg = []
    if seg:
        out.append(f'<polyline points="{" ".join(seg)}" fill="none" stroke="#e8e8ec" stroke-width="1.2"/>')
    if est:
        et = est["times"]
        up = " ".join(f"{tx(a):.1f},{vy(v + sd):.1f}" for a, v, sd in zip(et, est["values"], est["sd"], strict=True))
        dn = " ".join(f"{tx(a):.1f},{vy(v - sd):.1f}" for a, v, sd in zip(reversed(et), reversed(est["values"]), reversed(est["sd"]), strict=True))
        out.append(f'<polygon points="{up} {dn}" fill="#c9a227" opacity="0.22"/><polyline points="{" ".join(f"{tx(a):.1f},{vy(v):.1f}" for a, v in zip(et, est["values"], strict=True))}" fill="none" stroke="#c9a227" stroke-dasharray="5 3"/>')
    run_start = 0
    for i in range(1, len(s) + 1):  # the status ribbon: runs of equal status, so a gap is shown as a gap and named
        if i == len(s) or s[i]["status"] != s[run_start]["status"]:
            xa, xb = tx(t[run_start]), tx(t[min(i, len(t) - 1)])
            out.append(f'<rect x="{xa:.1f}" y="{y1 + 8}" width="{max(1.0, xb - xa):.1f}" height="14" fill="{STATUS_FILL.get(s[run_start]["status"], "#999")}"><title>{escape(s[run_start]["status"])}</title></rect>')
            run_start = i
    out.append(f'<text x="{x0}" y="{y1 + 38}" fill="#9a9aa2" font-size="10">ribbon: ' + ", ".join(f"{k}" for k in sorted({x["status"] for x in s})) + "  ·  a gap is not a zero</text>")
    return "".join(out)


def _body(d: dict) -> str:
    v = d["body"]["versions"][-1]
    cov = d.get("by_ref", {})
    lay = {c["id"]: c["attrs"].get("concept_layout") for c in v["components"]}
    if all(lay.values()):
        pos = {k: (120 + p["x"] * 2.2, 20 + p["y"] * 1.4) for k, p in lay.items()}
    else:
        import math
        n = max(1, len(v["components"]))
        pos = {c["id"]: (200 + 130 * math.cos(2 * math.pi * i / n - math.pi / 2), 150 + 110 * math.sin(2 * math.pi * i / n - math.pi / 2)) for i, c in enumerate(v["components"])}
    out = []
    for r in v["relations"]:
        a, b = pos[r["source"]], pos[r["target"]]
        out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="#45454c" stroke-width="1.5"/>')
        cls = cov.get(r["id"], "unmeasured")
        out.append(f'<circle cx="{(a[0] + b[0]) / 2:.1f}" cy="{(a[1] + b[1]) / 2:.1f}" r="5" fill="{CLASS_FILL[cls]}" stroke="#fff" stroke-width="0.6"><title>{escape(r["id"])}: {cls}</title></circle>')
    for c in v["components"]:
        cls = cov.get(c["id"], "unmeasured")
        out.append(f'<circle cx="{pos[c["id"]][0]:.1f}" cy="{pos[c["id"]][1]:.1f}" r="9" fill="{CLASS_FILL[cls]}" stroke="#fff" stroke-width="0.8"><title>{escape(c["id"])}: {cls}</title></circle>')
    out.append('<text x="440" y="40" fill="#d8d8dc" font-size="12">CONCEPTUAL ILLUSTRATION — not a photograph, not an anatomical measurement</text>')
    for i, (k, f) in enumerate(CLASS_FILL.items()):
        out.append(f'<circle cx="450" cy="{70 + i * 22}" r="7" fill="{f}" stroke="#fff" stroke-width="0.6"/><text x="465" y="{74 + i * 22}" fill="#cfcfd4" font-size="11">{k}</text>')
    return "".join(out)


def _limits(d: dict) -> str:
    out = [f'<text x="20" y="22" fill="#d8d8dc" font-size="12">observation state at t = {d["t"]} s · configuration version {d["version"]} · {d["observed"]} of {d["declared_targets"]} declared targets observed (the denominator is the declaration, not the world)</text>']
    for i, (tid, a) in enumerate(d["targets"].items()):
        y = 44 + i * 22
        out.append(f'<rect x="20" y="{y - 12}" width="14" height="14" fill="{STATUS_FILL.get(a["status"], "#999")}"/><text x="42" y="{y}" fill="#e8e8ec" font-size="11">{escape(tid)}  ·  {escape(a["status"])}  ·  causes: {escape(", ".join(a["causes"]) or "none")}  ·  {escape("; ".join(a.get("detail", [])) or "")[:80]}</text>')
    return "".join(out)


def _evidence(d: dict) -> str:
    out = [f'<text x="20" y="22" fill="#d8d8dc" font-size="12">experiment {escape(d["experiment_id"])} v{d["version"]} · {d["n_trials"]} trials · {escape(d.get("generator_note", ""))}</text>']
    for i, (aid, r) in enumerate(d["results"].items()):
        y = 52 + i * 22
        adj = d["adjusted"][aid]
        out.append(f'<text x="20" y="{y}" fill="#e8e8ec" font-size="11">{escape(aid)} · {escape(d["classes"].get(aid, "?"))} · effect {r["effect"]:.3f} · p {r["p"]:.4f} · p(holm) {adj["p_holm"]:.4f} · inferential {r["inferential"]} · lag-1 r {r["lag1_autocorrelation"]:.2f}</text>')
    return "".join(out)


DRAW = {"timeseries": _timeseries, "body": _body, "limits": _limits, "evidence": _evidence}


def render_svg(kind: str, data: dict, metadata: dict) -> str:
    md = json.dumps(metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    band = "".join(f'<text x="14" y="{H - BAND + 16 + i * 17}" fill="#ffe9b0" font-size="11" class="teoo-band" font-family="monospace">{escape(line)}</text>' for i, line in enumerate(metadata["evidence"]["band"]))
    marks = "".join(f'<text x="{W / 2}" y="{(H - BAND) / 2 + i * 70}" text-anchor="middle" font-size="64" font-weight="700" fill="#ffd479" opacity="0.16" transform="rotate(-18 {W / 2} {(H - BAND) / 2})" class="teoo-watermark" data-class="{c}">{c.replace("_", " ")}</text>'
                    for i, c in enumerate(metadata["evidence"]["watermarks"]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(metadata["title"])}" data-figure-id="{metadata["figure_id"]}">'
            f'<title>{escape(metadata["title"])}</title><desc>{escape(metadata["claim"])}</desc><metadata id="teoo-metadata"><![CDATA[{md}]]></metadata>'
            f'<rect width="{W}" height="{H}" fill="#07070a"/><g class="teoo-figure">{DRAW[kind](data)}</g>{marks}'
            f'<rect x="0" y="{H - BAND}" width="{W}" height="{BAND}" fill="#2a2208" class="teoo-band-bg"/>{band}</svg>')


def build_figure(kind: str, title: str, data: dict, records: list[dict], *, generated_at: str, **kw: Any) -> dict:
    extra = ("CONCEPTUAL",) if kind == "body" else ()
    md = figure_metadata(kind, title, data, records, generated_at=generated_at, extra_classes=extra, **kw)
    svg = render_svg(kind, data, md)
    return {"svg": svg, "metadata": md, "metadata_json": json.dumps(md, sort_keys=True, ensure_ascii=False, indent=1)}


def verify_svg(svg: str) -> list[str]:
    """Checks that the SVG still carries what makes it a legitimate figure: its metadata (matching its digest), the evidence band, and a watermark for every non-MEASURED class."""
    m = re.search(r'<metadata id="teoo-metadata"><!\[CDATA\[(.*?)\]\]></metadata>', svg, re.S)
    if not m:
        return ["the metadata is missing"]
    out: list[str] = []
    try:
        md = json.loads(m.group(1))
    except ValueError:
        return ["the metadata is not valid JSON"]
    if digest_of({k: v for k, v in md.items() if k != "metadata_digest"}) != md.get("metadata_digest"):
        out.append("the metadata does not match its digest")
    drawn = svg.replace(m.group(0), "")  # the band and the watermarks must be drawn, not merely quoted in the metadata
    if 'class="teoo-band-bg"' not in drawn or any(escape(line) not in drawn for line in md["evidence"]["band"]):
        out.append("the evidence band is missing or differs from the metadata")
    for c in md["evidence"]["watermarks"]:
        if f'data-class="{c}"' not in drawn:
            out.append(f"the {c} watermark is missing")
    needed = [c for c in WATERMARK_CLASSES if c in md["evidence"]["classes"]]
    if needed != md["evidence"]["watermarks"]:
        out.append("the metadata's watermark list does not match its evidence classes")
    if f'data-figure-id="{md["figure_id"]}"' not in svg:
        out.append("the figure id of the SVG differs from its metadata")
    return out


# ------------------------------------------------------------------------------------------------ PNG: text chunk with the metadata (a PNG is made by the browser from the SVG; here we read, check and, for tests, write)
PNG_SIG = b"\x89PNG\r\n\x1a\n"
TEXT_KEY = "teoo-metadata"


def png_encode(width: int, height: int, rgba: bytes) -> bytes:
    raw = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def metadata_ascii(md: dict) -> str:
    """The metadata as JSON with every non-ASCII character escaped: what a PNG text chunk (Latin-1) can carry without loss. The browser writes the same form."""
    return json.dumps(md, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def png_add_text(png: bytes, key: str, value: str) -> bytes:
    if png[:8] != PNG_SIG:
        raise ValueError("not a PNG")
    d = key.encode("latin-1") + b"\x00" + value.encode("latin-1", "backslashreplace")
    chunk = struct.pack(">I", len(d)) + b"tEXt" + d + struct.pack(">I", zlib.crc32(b"tEXt" + d) & 0xFFFFFFFF)
    iend = png.rfind(b"\x00\x00\x00\x00IEND")
    return png[:iend] + chunk + png[iend:]


def png_text_chunks(png: bytes) -> dict[str, str]:
    if png[:8] != PNG_SIG:
        raise ValueError("not a PNG")
    out, i = {}, 8
    while i < len(png):
        n = struct.unpack(">I", png[i:i + 4])[0]
        t, d = png[i + 4:i + 8], png[i + 8:i + 8 + n]
        if struct.unpack(">I", png[i + 8 + n:i + 12 + n])[0] != zlib.crc32(t + d) & 0xFFFFFFFF:
            raise ValueError("a chunk's CRC does not match")
        if t == b"tEXt":
            k, _, v = d.partition(b"\x00")
            out[k.decode("latin-1")] = v.decode("latin-1")
        i += 12 + n
    return out


def inspect_png(png: bytes) -> dict:
    """The metadata chunk of a figure PNG and what can be checked of it: that it exists, matches its digest and names the evidence classes. The pixels are not examined."""
    try:
        t = png_text_chunks(png)
    except ValueError as e:
        return {"ok": False, "issues": [str(e)], "metadata": None}
    if TEXT_KEY not in t:
        return {"ok": False, "issues": ["the PNG carries no teoo-metadata chunk"], "metadata": None}
    md = json.loads(t[TEXT_KEY])
    issues = []
    if digest_of({k: v for k, v in md.items() if k != "metadata_digest"}) != md.get("metadata_digest"):
        issues.append("the metadata does not match its digest")
    w, h = struct.unpack(">II", png[16:24])
    return {"ok": not issues, "issues": issues, "metadata": md, "width": w, "height": h, "note": "the pixels were not examined"}
