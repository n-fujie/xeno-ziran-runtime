"""Data Ingestion: CSV and JSON into sealed OBSERVATION records, with validation that returns errors and never repairs.

A document is a *manifest* (what the data are: schema version, declared provenance, who vouches, the clock, the columns -> registered variables -> body targets, the units
the file uses) plus the data. Ten things are checked: schema version, units, time, provenance, observation target, missing values, invalid values, duplicates, the body
configuration the data refer to, and the integrity of the original (its digest). Every problem is returned as an issue (field, code, message, fixable?, suggestion). A
blocking error means *nothing is registered*: the raw bytes go to quarantine with their issues. Nothing is converted or corrected silently: a unit that differs from the
registered one is an error (convert upstream), a blank cell is a MISSING sample (never 0), a value outside the registered valid interval is an INVALID sample whose raw text
is kept, a file without a declared provenance is quarantined and is never registered as MEASURED.
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, field
from typing import Any

from . import status as ST
from .body import Body
from .provenance import Ledger, Provenance, ProvenanceError, Quarantine, RawStore, canonical, now_iso, seal, sha256
from .schema import SCHEMA_IDS, Issue, VariableRegistry

MISSING_TOKENS = ("", "na", "n/a", "nan", "null", "none", "-")


@dataclass
class IngestResult:
    ok: bool
    record: dict | None
    issues: list[Issue] = field(default_factory=list)
    raw_digest: str = ""
    quarantined: bool = False

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    def to_dict(self) -> dict:
        return {"ok": self.ok, "record_id": self.record["record_id"] if self.record else None, "issues": [i.to_dict() for i in self.issues], "raw_digest": self.raw_digest, "quarantined": self.quarantined,
                "summary": {"errors": len(self.errors), "warnings": len(self.warnings)}}


def _rows_csv(raw: bytes) -> tuple[list[str], list[dict]]:
    text = raw.decode("utf-8-sig")
    rd = csv.DictReader(io.StringIO(text))
    return list(rd.fieldnames or []), [dict(r) for r in rd]


def _rows_json(doc: dict) -> tuple[list[str], list[dict]]:
    rows = doc.get("rows")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError("a JSON document carries 'rows': a list of objects")
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    return cols, rows


def _num(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    try:
        v = float(str(x).strip())
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def _missing(x: Any) -> bool:
    return x is None or (isinstance(x, str) and x.strip().lower() in MISSING_TOKENS)


def ingest(raw: bytes, *, media_type: str, registry: VariableRegistry, body: Body | None = None, ledger: Ledger | None = None, raw_store: RawStore | None = None,
           quarantine: Quarantine | None = None, created_at: str | None = None, manifest: dict | None = None) -> IngestResult:
    """Validate and, if there is no blocking error, register. ``manifest`` is given for CSV; a JSON document carries its own under 'manifest'."""
    issues: list[Issue] = []
    raw_digest = sha256(raw)
    doc: dict | None = None
    try:
        if media_type == "application/json" or media_type.endswith("+json"):
            doc = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(doc, dict):
                raise ValueError("the JSON document is an object with 'manifest' and 'rows'")
            manifest = doc.get("manifest", manifest)
            cols, rows = _rows_json(doc)
        elif media_type in ("text/csv", "application/csv"):
            cols, rows = _rows_csv(raw)
        else:
            issues.append(Issue("media_type", "MEDIA_TYPE_UNSUPPORTED", f"{media_type!r} is not supported (text/csv, application/json)"))
            return _fail(issues, raw, raw_digest, quarantine)
    except (ValueError, UnicodeDecodeError, csv.Error) as e:
        issues.append(Issue("data", "UNPARSEABLE", f"the data could not be parsed: {e}"))
        return _fail(issues, raw, raw_digest, quarantine)
    if not isinstance(manifest, dict):
        issues.append(Issue("manifest", "MANIFEST_MISSING", "no manifest: the schema version, provenance, clock, columns and units are declared, not guessed"))
        return _fail(issues, raw, raw_digest, quarantine)

    # 1. schema version
    sid = manifest.get("schema_version")
    if sid is None:
        issues.append(Issue("manifest.schema_version", "SCHEMA_MISSING", "the manifest names no schema version"))
    elif sid not in SCHEMA_IDS:
        issues.append(Issue("manifest.schema_version", "SCHEMA_UNKNOWN", f"unknown schema {sid!r}; known: {SCHEMA_IDS}"))
    # 4. provenance (declared, never inferred)
    prov = manifest.get("provenance")
    try:
        Provenance(str(prov))
    except ValueError:
        issues.append(Issue("manifest.provenance", "PROVENANCE_UNDECLARED", f"provenance must be declared as one of {[p.value for p in Provenance]}; a file without it is quarantined and never registered as MEASURED"))
    # 10. integrity of the original
    exp = manifest.get("expected_raw_digest")
    if exp is not None and exp != raw_digest:
        issues.append(Issue("raw", "RAW_DIGEST_MISMATCH", f"the raw bytes' sha256 is {raw_digest}, the manifest expected {exp}: the original is not the one that was described"))
    # 9. body configuration
    bref = manifest.get("body") or {}
    bver = None
    if body is not None:
        if bref.get("id") not in (None, body.id):
            issues.append(Issue("manifest.body.id", "BODY_UNKNOWN", f"the data refer to body {bref.get('id')!r}, not {body.id!r}"))
        bver = bref.get("version")
        if bver is None:
            issues.append(Issue("manifest.body.version", "BODY_VERSION_MISSING", "the data name no body configuration version", fixable=True, suggestion=f"current version is {body.current['version']}"))
        elif all(v["version"] != bver for v in body.versions):
            issues.append(Issue("manifest.body.version", "BODY_VERSION_UNKNOWN", f"body {body.id} has no version {bver}"))
    else:
        issues.append(Issue("manifest.body", "BODY_NOT_CHECKED", "no body was supplied: the observation targets were not checked against a configuration", severity="warning"))
    # 3. time
    tc, tunit = manifest.get("time_column"), (manifest.get("time") or {}).get("unit", "s")
    if tc not in cols:
        issues.append(Issue("manifest.time_column", "TIME_COLUMN_MISSING", f"time column {tc!r} is not in the data columns {cols}"))
    if tunit != "s":
        issues.append(Issue("manifest.time.unit", "TIME_UNIT", f"time unit {tunit!r}: TEOO does not convert silently; give seconds ('s') or convert upstream"))
    chans = manifest.get("channels") or []
    if not chans:
        issues.append(Issue("manifest.channels", "NO_CHANNELS", "no channel is declared"))
    # 2. units and 5. observation target, per channel
    for i, c in enumerate(chans):
        w = f"manifest.channels[{i}]"
        v = registry.get(c.get("variable", ""))
        if c.get("column") not in cols:
            issues.append(Issue(w + ".column", "COLUMN_MISSING", f"column {c.get('column')!r} is not in the data"))
        if v is None:
            issues.append(Issue(w + ".variable", "VARIABLE_UNREGISTERED", f"variable {c.get('variable')!r} is not in the registry", fixable=True, suggestion="register it first (custom variables are supported)"))
        elif c.get("unit") != v.unit:
            issues.append(Issue(w + ".unit", "UNIT_MISMATCH", f"the file says {c.get('unit')!r}, the registry says {v.unit!r} for {v.id}: no conversion is applied", suggestion="convert upstream or register a variable with that unit"))
        if body is not None and bver is not None and any(x["version"] == bver for x in body.versions):
            tgts = {t["id"] for t in body.at(bver)["targets"]}
            if c.get("target") not in tgts:
                issues.append(Issue(w + ".target", "TARGET_UNKNOWN", f"observation target {c.get('target')!r} is not in body {body.id} version {bver}"))
        elif c.get("target") is None:
            issues.append(Issue(w + ".target", "TARGET_MISSING", "the channel names no observation target", severity="warning"))
    declared = {c.get("column") for c in chans} | {tc} | {c.get("status_column") for c in chans if c.get("status_column")}
    for col in cols:
        if col not in declared:
            issues.append(Issue("data.columns", "UNDECLARED_COLUMN", f"column {col!r} is not declared in the manifest and is not ingested", severity="warning"))
    if any(i.severity == "error" for i in issues):
        return _fail(issues, raw, raw_digest, quarantine)

    # time values: parse, monotonic, duplicates
    times: list[float] = []
    bad_time = False
    for n, r in enumerate(rows):
        t = _num(r.get(tc))
        if t is None:
            issues.append(Issue(f"data.row[{n}].{tc}", "TIME_INVALID", f"time {r.get(tc)!r} is not a finite number"))
            bad_time = True
        else:
            times.append(t)
    if not bad_time:
        for n in range(1, len(times)):
            if times[n] == times[n - 1]:
                issues.append(Issue(f"data.row[{n}]", "DUPLICATE_TIME", f"time {times[n]} appears twice", fixable=False, suggestion="decide which row is right; TEOO does not pick one"))
            elif times[n] < times[n - 1]:
                issues.append(Issue(f"data.row[{n}]", "TIME_NOT_MONOTONIC", f"time goes back from {times[n - 1]} to {times[n]}", fixable=True, suggestion="sort upstream if the order is a recording artefact"))
        seen: dict[tuple, int] = {}
        for n, r in enumerate(rows):
            key = tuple(sorted((k, str(v)) for k, v in r.items()))
            if key in seen:
                issues.append(Issue(f"data.row[{n}]", "DUPLICATE_ROW", f"row {n} is identical to row {seen[key]}"))
            seen.setdefault(key, n)
    if any(i.severity == "error" for i in issues):
        return _fail(issues, raw, raw_digest, quarantine)

    # channels: missing, invalid, explicit statuses
    out_channels = []
    for c in chans:
        v = registry.get(c["variable"])
        assert v is not None  # an unregistered variable is a blocking error above
        samples = []
        counts: dict[str, int] = {}
        for n, r in enumerate(rows):
            cell, st_cell = r.get(c["column"]), (r.get(c["status_column"]) if c.get("status_column") else None)
            explicit = None
            if isinstance(cell, dict):
                explicit, cell = cell.get("status"), cell.get("value")
            if st_cell not in (None, "") and not _missing(st_cell):
                explicit = str(st_cell).strip()
            if explicit is not None:
                try:
                    stv = ST.ObsStatus(explicit)
                except ValueError:
                    issues.append(Issue(f"data.row[{n}].{c['column']}", "STATUS_UNKNOWN", f"status {explicit!r} is not one of {ST.STATUS_IDS}"))
                    continue
                if stv is ST.ObsStatus.MEASURED_VALID:
                    explicit = None
                else:
                    cause = [stv.value] if stv in ST.LIMIT_CAUSES else []
                    samples.append(ST.sample(None, stv, causes=cause, cause_known=stv not in (ST.ObsStatus.MISSING, ST.ObsStatus.INVALID, ST.ObsStatus.UNKNOWN_CAUSE) or bool(cause), detection_limit=c.get("detection_limit")))
                    counts[stv.value] = counts.get(stv.value, 0) + 1
                    continue
            if _missing(cell):
                samples.append(ST.sample(None, ST.ObsStatus.MISSING, cause_known=False))
                counts["MISSING"] = counts.get("MISSING", 0) + 1
                continue
            x = _num(cell) if v.dtype in ("float", "int") else cell
            lo_hi: tuple[float, float] | None = v.valid_interval
            if x is None or (isinstance(x, float) and lo_hi and not (lo_hi[0] <= x <= lo_hi[1])):
                samples.append(ST.sample(None, ST.ObsStatus.INVALID, cause_known=False, detail={"raw_text": str(cell), "reason": "not a finite number" if x is None else f"outside the valid interval {list(lo_hi or ())}"}))
                counts["INVALID"] = counts.get("INVALID", 0) + 1
                continue
            samples.append(ST.sample(x, ST.ObsStatus.MEASURED_VALID))
            counts["MEASURED_VALID"] = counts.get("MEASURED_VALID", 0) + 1
        for k, label in (("MISSING", "MISSING_VALUES"), ("INVALID", "INVALID_VALUES")):
            if counts.get(k):
                issues.append(Issue(f"data.{c['column']}", label, f"{counts[k]} {k.lower()} sample(s) kept as {k} (never as 0)", severity="warning"))
        out_channels.append({"variable": c["variable"], "target": c.get("target"), "unit": c["unit"], "times": times, "samples": samples, "counts": counts})
    if any(i.severity == "error" for i in issues):
        return _fail(issues, raw, raw_digest, quarantine)

    payload = {"body": {"id": bref.get("id") or (body.id if body else None), "version": bver}, "time": {**(manifest.get("time") or {}), "unit": "s", "ingested_at": created_at or now_iso()}, "channels": out_channels,
               "ingestion": {"media_type": media_type, "rows": len(rows), "columns": cols, "manifest_digest": sha256(canonical(manifest))}}
    try:
        rec = seal(payload, provenance=prov, kind=manifest.get("kind", "OBSERVATION"), creator=manifest.get("creator") or {}, source=manifest.get("source") or {}, raw_bytes=raw,
                   raw_media_type=media_type, created_at=created_at, validation={"ok": True, "issues": [i.to_dict() for i in issues]})
    except ProvenanceError as e:
        issues += e.issues
        return _fail(issues, raw, raw_digest, quarantine)
    if raw_store is not None:
        raw_store.put(raw)
    if ledger is not None:
        try:
            ledger.append(rec, raw_store)
        except ProvenanceError as e:
            issues += e.issues
            return _fail(issues, raw, raw_digest, quarantine)
    return IngestResult(True, rec, issues, raw_digest)


def _fail(issues: list[Issue], raw: bytes, raw_digest: str, quarantine: Quarantine | None) -> IngestResult:
    q = False
    if quarantine is not None:
        quarantine.add(raw, [i for i in issues if i.severity == "error"], "not registered")
        q = True
    return IngestResult(False, None, issues, raw_digest, q)
