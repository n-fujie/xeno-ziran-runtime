"""M9 causal-pathway switches (xzr/lab/physics.py partition, xzr/lab/science.py comm / inert, record.py harness):
defaults unchanged, no hidden coupling when every pathway is cut, each switch does what it declares."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("mujoco")

from xzr.lab import physics as P  # noqa: E402
from xzr.lab.record import SCHEMA_V3, LabRun  # noqa: E402
from xzr.lab.replay import replay  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
A = {"sid": "A", "kind": "local", "home": "0.0"}
B = {"sid": "B", "kind": "distributed", "home": "1.0", "sensors": ["0.1", "2.0", "7.0", "1.2"], "isolate_above": 0.12}
C = {"sid": "C", "kind": "history", "home": "1.1", "memory": "ordinary", "store": "1.3"}
G = {"A": "a", "B": "s", "C": "s"}
SEP = {"groups": G, "gantries": "private", "material": "private"}
# SHA-256 of the default MJCF for the M3 chambers, equal to the frozen m7-verified code (checked when written)
DEFAULT_MJCF_SHA256 = "31ccfccbe6071d2083e1d97d6377a207a5fb3c1204f99de9ba3410ef7e96aaf4"


def run(systems, horizon=120, **kw) -> LabRun:
    cfg = {"n": 800, "regime": "intermittent", "warmup": 40, "horizon": horizon, "settings": None, "physics": True,
           "resources": 3.0, "gen_seed": 8000, "seed": 80000, "systems": systems, **kw}
    r = LabRun(cfg)
    while not r.done:
        r.step()
    return r


def b_events(r: LabRun) -> list[dict]:
    assert r.science is not None
    return [e for e in r.science.events if e.get("system") == "B"]


def test_default_laboratory_is_unchanged():
    ch = json.loads((ROOT / "experiments/results/lab/m3-physical-9100.json").read_text())["chambers"]
    assert hashlib.sha256(P.mjcf(ch).encode()).hexdigest() == DEFAULT_MJCF_SHA256
    assert P.mjcf(ch) == P.mjcf(ch, None)


def test_an_idle_system_changes_nothing():
    """Presence alone (decisions read the runtime, caches, scheduling) is not a pathway."""
    idle = run([{**A, "budget": 0.0}, B, C])
    none = run([B, C])
    assert idle.w.engine.fingerprint() == none.w.engine.fingerprint()
    assert b_events(idle) == b_events(none)


def test_every_pathway_cut_leaves_no_hidden_coupling():
    """A inert (no runtime effect), resources private, B's communication frozen: the run equals the run without A,
    bit for bit, although A does physical work in the same MuJoCo model."""
    cut = run([{**A, "inert": True}, {**B, "comm": "frozen"}, C], partition=SEP)
    ref = run([{**B, "comm": "frozen"}, C], partition=SEP)
    assert cut.science is not None and cut.science.summary()["A"]["requests"] > 0
    assert cut.w.engine.fingerprint() == ref.w.engine.fingerprint()
    assert b_events(cut) == b_events(ref)


def test_private_gantries_and_material_are_never_shared():
    r = run([A, B, C], partition=SEP)
    lab = r.lab
    assert lab is not None
    for leg in lab.trace["legs"]:
        grp = G[leg["owner"]]
        assert leg["gantry"].endswith("#" + grp)
        assert all(G[o] == grp for o in leg["ahead"])  # nobody else's legs ever wait on this carriage
    for cont, items in lab.contents.items():
        for s in items:
            assert "#" in s, (cont, s)
    assert lab.material("0.1", "A") == [s for s in lab.contents["0.1"] if s.endswith("#a")]


def test_frozen_communication_ignores_later_connections():
    from xzr.lab.science import Science  # noqa: F401  (frozen graph lives on the Science instance)
    r = run([{**B, "comm": "frozen"}], horizon=8)
    r2 = run([B], horizon=8)
    sci, sci2 = r.science, r2.science
    assert sci is not None and sci2 is not None
    before = dict(sci.coverage(sci.systems["B"]))
    st = r.w.state
    st.alive[:] = False  # every connection gone: a live (conduit) reading would collapse to the hub
    sci.invalidate()
    assert sci.coverage(sci.systems["B"]) == before
    st2 = r2.w.state
    st2.alive[:] = False
    sci2.invalidate()
    assert set(sci2.coverage(sci2.systems["B"])) <= {"1.0"}


def test_priority_serves_a_group_first_without_displacing_the_leg_in_progress():
    ch = json.loads((ROOT / "experiments/results/lab/m3-physical-9100.json").read_text())["chambers"]
    lab = P.PhysicalLab(ch, partition={"groups": G, "priority": "s"})
    g = lab.gantries["0"]
    legs = []
    for owner in ("A", "A", "B"):
        tr = P.Transfer(len(legs) + 1, None, "0.0", "0.1", [("0", "0.0", "0.1")], 0, owner=owner,  # type: ignore[arg-type]
                        group=G[owner])
        legs.append(P.Leg(tr))
        lab._enqueue(g, legs[-1], 0)
    assert [lg.transfer.owner for lg in g.queue] == ["A", "B", "A"]


def test_wear_exemption_and_trace():
    ch = json.loads((ROOT / "experiments/results/lab/m3-physical-9100.json").read_text())["chambers"]
    lab = P.PhysicalLab(ch, partition={"groups": G, "wear_exempt": ["a"]})
    g = lab.gantries["0"]
    ta = P.Transfer(1, None, "0.0", "0.1", [], 0, owner="A", group="a")  # type: ignore[arg-type]
    tb = P.Transfer(2, None, "0.0", "0.1", [], 0, owner="B", group="s")  # type: ignore[arg-type]
    lab._wear(g, ta, 0.1)
    assert g.health == 1.0
    lab._wear(g, tb, 0.1)
    assert g.health == pytest.approx(0.9) and g.wear_by == {"B": pytest.approx(0.1)}


def test_harness_interventions_are_applied_recorded_and_replay():
    h = [{"at": 5, "do": "fail_gantry", "gantry": "0"}, {"at": 6, "do": "set_resources", "gantry": "0", "value": 0.0},
         {"at": 8, "do": "sever", "chambers": ["1.0"]}, {"at": 10, "do": "close", "chambers": ["0.1"]},
         {"at": 30, "do": "open", "chambers": ["0.1"]}]
    r = run([A, B], horizon=40, harness=h)
    rec = json.loads(json.dumps(r.record()))
    assert rec["schema"] == SCHEMA_V3
    kinds = [(e["t"], e["do"]) for e in rec["science_events"] if e["type"] == "harness"]
    assert kinds == [(5, "fail_gantry"), (6, "set_resources"), (8, "sever"), (10, "close"), (30, "open")]
    assert any(e["type"] == "gantry_failed" and e["t"] == 5 for e in rec["physical_events"])
    sev = next(e for e in rec["science_events"] if e["type"] == "harness" and e["do"] == "sever")
    assert sev["severed"] > 0
    assert replay(rec)["agreement"]


def test_resource_redistribution_starts_a_repair():
    ch = json.loads((ROOT / "experiments/results/lab/m3-physical-9100.json").read_text())["chambers"]
    lab = P.PhysicalLab(ch, resources=0.0)
    ev: list[dict] = []
    lab.force_failure("0", 1, ev)
    assert lab.gantries["0"].failed and lab.gantries["0"].repair_left == 0
    lab.set_resources("0", 1.0, 2, ev)
    assert lab.gantries["0"].repair_left == P.REPAIR_STEPS and ev[-1]["type"] == "repair_started"


def test_private_carriages_on_shared_material_cannot_take_the_same_sample():
    """Two carriages in one bay racing for one sample: the second grasp fails as a recorded transfer failure."""
    r = run([A, B, C], horizon=250, partition={"groups": G, "gantries": "private"}, gen_seed=8100, seed=81000)
    taken = [e for e in r.physical if e["type"] == "transfer_failed" and "taken by another gantry" in e.get("reason", "")]
    assert [(e["t"], e["src"]) for e in taken] == [(246, "0.1")]  # found by the M9 pilot (it crashed the run before)


def test_legs_are_attributed_to_their_system_in_the_shared_laboratory():
    r = run([A, B], horizon=160)
    assert r.lab is not None and r.lab.trace["legs"]
    assert {lg["owner"] for lg in r.lab.trace["legs"]} <= {"A", "B"}
    assert None not in {lg["owner"] for lg in r.lab.trace["legs"]}


def test_a_forced_failure_ends_the_pending_experiment_it_destroys():
    """Harness physical events reach the systems like physics events (found by the M9 pilot: a transfer lost to a
    forced gantry failure stayed pending forever and the system never requested again)."""
    r = run([A], horizon=200, harness=[{"at": 60, "do": "fail_gantry", "gantry": "0"}])
    sci = r.science
    assert sci is not None
    lost = [e for e in r.physical if e["type"] == "transfer_failed" and e["t"] == 60]
    assert lost, "the forced failure must destroy a queued transfer for this test to say anything"
    assert any(e["type"] == "experiment_failed" and e["t"] == 60 for e in sci.events)
    assert sci.systems["A"].stats["requests"] > sum(1 for e in sci.events if e["type"] == "experiment_selected" and e["t"] <= 60)
