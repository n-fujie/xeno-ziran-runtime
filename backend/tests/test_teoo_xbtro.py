"""TEOO <-> XB-TRO: an adapter over XB-TRO's plain JSON outputs (fixtures taken from feat/xb-tro at 94c2e8e); the Xeno-14 definitions agree with both authoritative files; the negative results are kept."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from xzr.teoo import body as B
from xzr.teoo import provenance as P
from xzr.teoo import xbtro_adapter as XA

FIX = Path(__file__).parent / "fixtures" / "teoo"
PRESETS = json.loads((FIX / "xbtro_presets.json").read_text())
STEP = json.loads((FIX / "xbtro_live_step.json").read_text())["step"]
REF = json.loads((FIX / "xeno14_reference.json").read_text())
BIM = Path(__file__).resolve().parents[3]


def test_xbtro_presets_become_open_body_graphs_without_importing_xbtro():
    for name, cfg in PRESETS["presets"].items():
        b = XA.body_from_config(cfg, preset=name, at="2026-01-01T00:00:00.000000Z")
        assert B.validate_body(b) == [] and b.meta["source"]["commit"] == "94c2e8e" and "nothing here is measured physiology" in b.meta["source"]["claims"]
        links, joints, lines = cfg["links"], cfg["joints"], cfg["lines"]
        assert len([c for c in b.current["components"] if c["kind"] == "segment"]) == len(links) and len([r for r in b.current["relations"] if r["kind"] == "joint"]) == len(joints)
        assert len([c for c in b.current["components"] if c["kind"] == "operation-line"]) == len(lines) and len(b.current["targets"]) == len(lines)
    human, machine = (XA.body_from_config(PRESETS["presets"][k], preset=k) for k in ("human-like-planar", "machine-like-planar"))
    assert human.family == "human" and machine.family == "artificial"
    first = next(r for r in human.current["relations"] if r["kind"] == "joint")
    assert first["source"] == "ground" and first["attrs"]["convention"] == "xbtro-chain-order"  # the chain convention of xbtro/engine.py, declared as a convention


def test_the_operation_lines_keep_what_xbtro_says_can_observe_them():
    cfg = PRESETS["presets"]["human-like-planar"]
    b = XA.body_from_config(cfg, preset="human-like-planar")
    lines = {f"line:{ln['id']}": ln for ln in cfg["lines"]}
    for c in b.current["components"]:
        if c["kind"] == "operation-line":
            assert c["attrs"]["observable_by"] == lines[c["id"]]["observable_by"] and c["attrs"]["timescale_s"] == lines[c["id"]]["timescale_s"]
    assert b.meta["xeno14_conditions"] == cfg["xeno14"]


def test_a_live_step_becomes_three_kinds_of_record_never_merged_and_all_synthetic():
    reference, estimate, observation = XA.records_from_live_step(STEP, creator={"name": "adapter-test"}, created_at="2026-01-01T00:00:00.000000Z")
    assert (reference["kind"], estimate["kind"], observation["kind"]) == ("REFERENCE_STATE", "ESTIMATE", "OBSERVATION")
    assert {reference["provenance"], estimate["provenance"], observation["provenance"]} == {"SYNTHETIC"}  # a simulated planar body is never MEASURED
    assert len({reference["record_id"], estimate["record_id"], observation["record_id"]}) == 3
    ledger = P.Ledger()
    for r in (reference, estimate, observation):
        ledger.append(r)
    assert ledger.verify() == []
    names = {c["variable"] for c in observation["payload"]["channels"]}
    assert {"xbtro.posture.q:ankle", "xbtro.emg.emg:knee", "xbtro.contact.cop"} <= names
    ch = next(c for c in observation["payload"]["channels"] if c["variable"] == "xbtro.posture.q:ankle")
    assert ch["times"] == STEP["observation"]["posture"]["t"] and "available_at" in ch and len(ch["samples"]) == len(ch["times"])  # the model time and the time it became available are both kept
    assert "reference" in reference["payload"]["xbtro"] and "estimates" in estimate["payload"]["xbtro"] and "estimates" not in reference["payload"]["xbtro"]  # reference and estimate are not in one record
    assert "simulated planar body" in observation["source"]["description"]


def test_the_xeno14_ids_agree_with_the_authoritative_files_as_extracted_into_the_fixture():
    assert tuple(REF["body_ts"]["XENO14"]) == XA.XENO14_IDS == tuple(REF["xbtro_py"]["PRINCIPLES_ids"]) and len(XA.XENO14_IDS) == 14
    assert REF["body_ts"]["path"].endswith("src/domains/body.ts") and "XENO14" in XA.XENO14_SOURCE["definition"]


def test_the_xeno14_ids_agree_with_the_live_files_when_they_are_on_this_machine():
    ts = BIM / "ziran-xeno-simulator" / "src" / "domains" / "body.ts"
    py = BIM / "xeno-ziran-runtime-xb-tro" / "backend" / "xzr" / "xbtro" / "xeno14.py"
    if not (ts.exists() and py.exists()):
        pytest.skip("the sibling repositories are not on this machine; the fixture comparison above still ran")
    m = re.search(r"export const XENO14 = \[(.*?)\] as const", ts.read_text(), re.S)
    assert tuple(re.findall(r"'([^']+)'", m.group(1))) == XA.XENO14_IDS
    assert tuple(re.findall(r'^\s{8}"id":\s*"([^"]+)"', py.read_text(), re.M)) == XA.XENO14_IDS


def test_the_negative_and_limited_results_are_kept_verbatim():
    by = {r["id"]: r for r in XA.RETAINED_RESULTS}
    assert by["X14-1"]["status"] == "STOP" and by["X14-1b"]["status"].startswith("CONDITIONAL GO") and "no non-redundant control advantage demonstrated" in by["X14-1b"]["status"]
    assert "not accepted" in by["BS-1"]["status"] and all("simulated" in r["scope"] for r in by.values())
    readme = BIM / "ziran-xeno-simulator" / "embodied" / "README.md"
    if readme.exists():
        t = readme.read_text()
        assert "X14-1 STOP" in t and "X14-1b CONDITIONAL GO" in t and "no non-redundant control advantage demonstrated" in t  # the source still says it
