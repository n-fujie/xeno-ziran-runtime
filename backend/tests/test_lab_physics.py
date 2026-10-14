"""Physical laboratory (xzr/lab/physics.py, MuJoCo): validation within the declared approximation limits, coupling to
the runtime, determinism and replay. Skipped only where the optional `physics` dependency (mujoco) is not installed."""

from __future__ import annotations

import math

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from xzr.hpo.world import build_world  # noqa: E402
from xzr.lab import apparatus  # noqa: E402
from xzr.lab import physics as P  # noqa: E402
from xzr.lab.record import DEFAULT_CONFIG, run  # noqa: E402
from xzr.lab.replay import replay  # noqa: E402
from xzr.runtime.intervention import Connect  # noqa: E402


@pytest.fixture(scope="module")
def chambers():
    w = build_world(800, 9100, 91000)
    cs = apparatus.chambers(w.h)
    return [{"cid": c.cid, "position": list(c.position)} for c in cs], {int(n): c.cid for c in cs for n in c.nodes}, cs


def _free_joint(lab, sid):
    b = lab._body[f"sample_{sid.replace('.', '_')}"]
    return lab.model.jnt_qposadr[lab.model.body_jntadr[b]], lab.model.jnt_dofadr[lab.model.body_jntadr[b]]


def test_free_fall_time_matches_analytic_gravity(chambers):
    lab = P.PhysicalLab(chambers[0])
    q, v = _free_joint(lab, "0.0")
    h = 2.0
    lab.data.qpos[q + 2] = 0.05 + P.HALF + h
    lab.data.qvel[v:v + 6] = 0
    mujoco.mj_forward(lab.model, lab.data)
    t = 0.0
    while lab.sample_xyz("0.0")[2] > 0.05 + P.HALF + 0.002:
        mujoco.mj_step(lab.model, lab.data)
        t += P.DT
    assert t == pytest.approx(math.sqrt(2 * h / 9.81), rel=0.02)  # no drag in the model


def test_resting_contact_has_millimetre_penetration(chambers):
    lab = P.PhysicalLab(chambers[0])
    for _ in range(500):
        mujoco.mj_step(lab.model, lab.data)
    z = np.array([lab.sample_xyz(c["cid"])[2] for c in chambers[0]])
    assert np.all(np.abs(z - (0.05 + P.HALF)) < 0.002)


def test_a_wall_stops_a_sample_carried_too_low(chambers):
    """Collision is physical: a carried sample cannot pass through a chamber wall."""
    lab = P.PhysicalLab(chambers[0])
    x, y = lab.pos["0.0"]
    q, v = _free_joint(lab, "0.0")
    lab.data.qpos[q:q + 3] = (x, y, 0.05 + P.HALF + 0.001)
    for _ in range(40):  # push the sample sideways along the floor towards the +x wall
        lab.data.qvel[v] = 3.0
        mujoco.mj_step(lab.model, lab.data)
    for _ in range(300):
        mujoco.mj_step(lab.model, lab.data)
    assert lab.sample_xyz("0.0")[0] < x + P.CH - P.HALF + 0.02


def _transfer_steps(ch, owner, cs, health: float) -> tuple[int | None, list[dict]]:
    lab = P.PhysicalLab(ch)
    lab.gantries[cs[0].cid.split(".")[0]].health = health
    lab.request(Connect(int(cs[0].nodes[0]), int(cs[1].nodes[0])), owner.get, 0)
    evs: list[dict] = []
    for t in range(300):
        e, d = lab.step(t)
        evs += e
        if d:
            return t, evs
    return None, evs


def test_wear_slows_the_servo_and_failure_follows_the_declared_threshold(chambers):
    """Physically, lower health = lower servo gain and force limit: the same transfer takes longer. Below FAIL_H the
    declared failure rule applies (an approximation, not a physical fracture model)."""
    ch, owner, cs = chambers
    healthy, _ = _transfer_steps(ch, owner, cs, 1.0)
    worn, _ = _transfer_steps(ch, owner, cs, 0.4)
    assert healthy is not None and worn is not None and worn > healthy
    lab = P.PhysicalLab(ch)
    g = lab.gantries[cs[0].cid.split(".")[0]]
    g.health = P.FAIL_H + 0.01  # one completed leg wears it below the threshold
    lab.request(Connect(int(cs[0].nodes[0]), int(cs[1].nodes[0])), owner.get, 0)
    evs = []
    for t in range(200):
        evs += lab.step(t)[0]
    kinds = [e["type"] for e in evs]
    assert "gantry_failed" in kinds and "gantry_repaired" in kinds and kinds.index("gantry_failed") < kinds.index(
        "gantry_repaired")
    assert g.resources == pytest.approx(3.0 - P.REPAIR_COST) and g.health == 1.0


def test_transfer_succeeds_when_healthy_and_is_impossible_with_a_failed_gantry(chambers):
    ch, owner, cs = chambers
    lab = P.PhysicalLab(ch)
    lab.request(Connect(int(cs[0].nodes[0]), int(cs[1].nodes[0])), owner.get, 0)
    done = []
    for t in range(120):
        _, d = lab.step(t)
        done += d
    assert len(done) == 1 and lab.contents[cs[1].cid] == [cs[1].cid, cs[0].cid]
    failed = P.PhysicalLab(ch)
    failed.gantries[cs[0].cid.split(".")[0]].failed = True  # failed, no repair scheduled
    ev = failed.request(Connect(int(cs[0].nodes[0]), int(cs[1].nodes[0])), owner.get, 0)
    assert ev["type"] == "transfer_impossible"


def test_physics_is_deterministic(chambers):
    ch, owner, cs = chambers
    fps = []
    for _ in range(2):
        lab = P.PhysicalLab(ch)
        lab.request(Connect(int(cs[0].nodes[0]), int(cs[2].nodes[0])), owner.get, 0)
        for t in range(60):
            lab.step(t)
        fps.append(lab.fingerprint())
    assert fps[0] == fps[1]


def test_physical_run_couples_to_the_runtime_and_replays():
    rec = run({**DEFAULT_CONFIG, "physics": True, "horizon": 120})
    kinds = {e["type"] for e in rec["physical_events"]}
    assert "transfer_queued" in kinds
    assert all("physics" in s and s["physics"]["fingerprint"] for s in rec["steps"])
    plain = run({**DEFAULT_CONFIG, "physics": False, "horizon": 120})
    # requested connections wait for (or never get) their material: the runtime diverges from the instantaneous run
    assert rec["steps"][-1]["fingerprint"] != plain["steps"][-1]["fingerprint"]
    r = replay(rec)
    assert r["agreement"], r
