"""Physical laboratory (MuJoCo 3.14): a runtime connection that an operation requests exists only after material moves.

Physically modelled (rigid-body dynamics, MuJoCo, dt 4 ms, 50 sub-steps = 0.2 s per runtime step):

    * one 3-axis gantry per bay (slide x / y / z), driven by position servos with force limits; the gantry's own weight
      is gravity-compensated, a carried sample is not (the z servo must hold it)
    * one material sample per chamber at start (free rigid box, 0.8 kg) with contact and collision against chamber
      floors, chamber walls (0.7 m: a carried sample must be lifted over them), handoff ports and other samples
    * handoff ports: open tables halfway between adjacent bays; a sample travels between non-adjacent bays as a relay
      of legs (one gantry carries it to a port, the next takes it on)

Computational approximations (declared; not physical models):

    * grasping is a weld constraint activated when the tool is within GRASP_TOL of the sample (no friction grasp)
    * wear: each leg lowers the gantry's health h by WEAR·(1 + carried mass); servo gain and force limit scale with h;
      below FAIL_H the gantry fails (force 0; a carried sample is released wherever it is)
    * repair restores h = 1 after REPAIR_STEPS runtime steps and costs REPAIR_COST of the bay's resources; without
      resources the gantry stays failed (that bay's transfers cease)
    * routing: shortest way round the ring of bays; a gantry works its queue in order (at most QUEUE legs)

Coupling to the runtime: a runtime Connect action requested by an operation is executed only by moving a material
sample from the source configuration's chamber into a free spot of the target configuration's chamber. When the last
leg releases the sample inside the target chamber, the connection is applied to the runtime; if any leg fails, it
never exists. Rendering plays no part: this runs headless.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import mujoco
import numpy as np

from ..runtime.intervention import Connect

DT = 0.004
SUBSTEPS = 50
SAFE_Z = 1.4  # tool-tip height for travel (above the 0.7 m walls with a sample hanging below)
TIP_OFFSET = 0.3  # tool tip below the carriage origin
GRASP_TOL = 0.08
PHASE_TOL = 0.03
PHASE_TIMEOUT = 40  # runtime steps per motion phase
WEAR = 0.035
FAIL_H = 0.35
REPAIR_STEPS = 30
REPAIR_COST = 1.0
KP = 900.0
FORCE = 120.0
SAMPLE_MASS = 0.8
HALF = 0.15  # sample half size
WALL_H = 0.7
CH = 1.3  # chamber floor half size
PORT = 0.75  # port table half size
REACH = 7.5  # gantry travel from its bay centre
QUEUE = 4


def _xy(pos3: list[float]) -> tuple[float, float]:
    """3D-view position (x, height, z) → physics plane (x, y)."""
    return float(pos3[0]), float(pos3[2])


def _bays(chambers: list[dict]) -> dict[str, tuple[float, float]]:
    by: dict[str, list[tuple[float, float]]] = {}
    for c in chambers:
        by.setdefault(c["cid"].split(".")[0], []).append(_xy(c["position"]))
    return {b: (float(np.mean([p[0] for p in ps])), float(np.mean([p[1] for p in ps]))) for b, ps in sorted(by.items())}


def ring(bays: dict[str, tuple[float, float]]) -> list[str]:
    """Bays ordered by angle around the laboratory centre (the transport ring)."""
    return sorted(bays, key=lambda b: float(np.arctan2(bays[b][1], bays[b][0])))


def ports(bays: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    r = ring(bays)
    out = {}
    for i, a in enumerate(r):
        b = r[(i + 1) % len(r)]
        key = "port:" + "-".join(sorted((a, b)))
        out[key] = ((bays[a][0] + bays[b][0]) / 2, (bays[a][1] + bays[b][1]) / 2)
    return out


def mjcf(chambers: list[dict]) -> str:
    bays = _bays(chambers)
    world = ['<geom name="ground" type="plane" size="60 60 0.1" pos="0 0 -0.05" rgba=".1 .1 .1 1"/>']
    samples = [c["cid"].replace(".", "_") for c in chambers]
    for c in chambers:
        x, y = _xy(c["position"])
        n = c["cid"].replace(".", "_")
        world.append(f'<geom name="floor_{n}" type="box" pos="{x} {y} 0" size="{CH} {CH} 0.05"/>')
        for k, (dx, dy, sx, sy) in enumerate(((CH, 0, 0.03, CH), (-CH, 0, 0.03, CH), (0, CH, CH, 0.03), (0, -CH, CH, 0.03))):
            world.append(f'<geom name="wall_{n}_{k}" type="box" pos="{x + dx} {y + dy} {WALL_H / 2}" '
                         f'size="{sx} {sy} {WALL_H / 2}"/>')
        world.append(f'<body name="sample_{n}" pos="{x} {y} {0.05 + HALF + 0.001}"><freejoint/>'
                     f'<geom type="box" size="{HALF} {HALF} {HALF}" mass="{SAMPLE_MASS}" friction="0.9 0.01 0.001"/></body>')
    for key, (x, y) in ports(bays).items():
        world.append(f'<geom name="{key.replace(":", "_").replace("-", "_")}" type="box" pos="{x} {y} 0" '
                     f'size="{PORT} {PORT} 0.05"/>')
    acts, eqs = [], []
    for b, (cx, cy) in bays.items():
        world.append(
            f'<body name="carriage_{b}" pos="{cx} {cy} {SAFE_Z + TIP_OFFSET}" gravcomp="1">'
            f'<joint name="gx_{b}" type="slide" axis="1 0 0" range="-{REACH} {REACH}" damping="40"/>'
            f'<joint name="gy_{b}" type="slide" axis="0 1 0" range="-{REACH} {REACH}" damping="40"/>'
            f'<joint name="gz_{b}" type="slide" axis="0 0 1" range="-1.5 0.6" damping="40"/>'
            f'<geom type="box" size="0.12 0.12 0.08" mass="2" contype="0" conaffinity="0"/>'
            f'<body name="tool_{b}" pos="0 0 -0.2" gravcomp="1"><geom type="box" size="0.05 0.05 0.1" mass="0.5" '
            f'contype="0" conaffinity="0"/><site name="tip_{b}" pos="0 0 -0.1"/></body></body>')
        for ax in "xyz":
            acts.append(f'<position name="a{ax}_{b}" joint="g{ax}_{b}" kp="{KP}" kv="60" forcelimited="true" '
                        f'forcerange="-{FORCE} {FORCE}"/>')
        for n in samples:
            eqs.append(f'<weld name="grip_{b}_{n}" body1="tool_{b}" body2="sample_{n}" active="false"/>')
    return (f'<mujoco><option timestep="{DT}" gravity="0 0 -9.81"/><worldbody>{"".join(world)}</worldbody>'
            f'<actuator>{"".join(acts)}</actuator><equality>{"".join(eqs)}</equality></mujoco>')


@dataclass
class Transfer:
    tid: int
    action: Connect  # the runtime action this transfer executes
    src: str
    dst: str
    legs: list[tuple[str, str, str]]  # (bay, from container, to container)
    requested_at: int
    leg: int = 0
    sample: str | None = None


@dataclass
class Leg:
    transfer: Transfer
    phase: int = 0
    phase_steps: int = 0
    spot: tuple[float, float] | None = None


@dataclass
class Gantry:
    bay: str
    health: float = 1.0
    failed: bool = False
    repair_left: int = 0
    resources: float = 3.0
    queue: list[Leg] = field(default_factory=list)
    carrying: str | None = None
    legs_done: int = 0


class PhysicalLab:
    def __init__(self, chambers: list[dict], resources: float = 3.0):
        self.chambers = chambers
        self.model = mujoco.MjModel.from_xml_string(mjcf(chambers))
        self.data = mujoco.MjData(self.model)
        bays = _bays(chambers)
        self.ring = ring(bays)
        self.pos = {c["cid"]: _xy(c["position"]) for c in chambers} | ports(bays)
        self.half = {c["cid"]: CH for c in chambers} | dict.fromkeys(ports(bays), PORT)
        self.bay_of = {c["cid"]: c["cid"].split(".")[0] for c in chambers}
        self.gantries = {b: Gantry(b, resources=resources) for b in bays}
        self.contents: dict[str, list[str]] = {c["cid"]: [c["cid"]] for c in chambers} | {p: [] for p in ports(bays)}
        self.transfers = 0
        m = self.model
        self._eq = {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY, i): i for i in range(m.neq)}
        self._act = {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i): i for i in range(m.nu)}
        self._body = {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i): i for i in range(m.nbody)}
        self._site = {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_SITE, i): i for i in range(m.nsite)}
        mujoco.mj_forward(m, self.data)
        self._base = {b: self.data.xpos[self._body[f"carriage_{b}"]].copy() for b in self.gantries}
        for _ in range(100):  # settle the samples on their floors
            mujoco.mj_step(m, self.data)

    # ------------------------------------------------------------------ geometry
    def sample_xyz(self, sid: str) -> np.ndarray:
        return self.data.xpos[self._body[f"sample_{sid.replace('.', '_')}"]].copy()

    def tip_xyz(self, b: str) -> np.ndarray:
        return self.data.site_xpos[self._site[f"tip_{b}"]].copy()

    def _inside(self, cont: str, p: np.ndarray) -> bool:
        x, y = self.pos[cont]
        h = self.half[cont]
        return abs(p[0] - x) < h - 0.05 and abs(p[1] - y) < h - 0.05 and p[2] < 0.05 + 2 * HALF + 0.15

    def _free_spot(self, cont: str) -> tuple[float, float] | None:
        x, y = self.pos[cont]
        taken = [self.sample_xyz(s)[:2] for s in self.contents[cont]]
        offs = ((0.0, 0.0), (0.65, 0.65), (-0.65, 0.65), (0.65, -0.65), (-0.65, -0.65)) if cont in self.bay_of else \
            ((0.0, 0.0), (0.4, 0.4), (-0.4, -0.4))
        for ox, oy in offs:
            spot = np.array([x + ox, y + oy])
            if all(np.linalg.norm(spot - q) > 2.2 * HALF + 0.2 for q in taken):
                return float(spot[0]), float(spot[1])
        return None

    def _route(self, a: str, b: str) -> list[str]:
        """Bays from a to b the short way round the ring."""
        i, j, n = self.ring.index(a), self.ring.index(b), len(self.ring)
        fwd, back = (j - i) % n, (i - j) % n
        step = 1 if fwd <= back else -1
        return [self.ring[(i + step * k) % n] for k in range(min(fwd, back) + 1)]

    def _set_target(self, b: str, xyz: tuple[float, float, float]) -> None:
        base = self._base[b]
        for ax, v in zip("xyz", (xyz[0] - base[0], xyz[1] - base[1], xyz[2] + TIP_OFFSET - base[2]), strict=True):
            self.data.ctrl[self._act[f"a{ax}_{b}"]] = v

    def _apply_health(self, g: Gantry) -> None:
        h = 0.0 if g.failed else g.health
        for ax in "xyz":
            a = self._act[f"a{ax}_{g.bay}"]
            self.model.actuator_gainprm[a, 0] = KP * max(h, 1e-3)
            self.model.actuator_biasprm[a, 1] = -KP * max(h, 1e-3)
            self.model.actuator_forcerange[a] = (-FORCE * h, FORCE * h)

    # ------------------------------------------------------------------ requests from the runtime
    def request(self, action: Connect, chamber_of_node, t: int) -> dict:
        a, b = chamber_of_node(action.src), chamber_of_node(action.dst)
        ev = {"t": t, "src": a, "dst": b}
        if a is None or b is None or a == b:
            return {**ev, "type": "transfer_not_needed"}
        bays = self._route(self.bay_of[a], self.bay_of[b])
        legs = []
        here = a
        for k, bay in enumerate(bays):
            nxt = b if k == len(bays) - 1 else "port:" + "-".join(sorted((bay, bays[k + 1])))
            legs.append((bay, here, nxt))
            here = nxt
        g = self.gantries[bays[0]]
        if g.failed and g.repair_left == 0:
            return {**ev, "type": "transfer_impossible", "reason": f"gantry of bay {g.bay} failed without repair"}
        if len(g.queue) >= QUEUE:
            return {**ev, "type": "transfer_rejected", "reason": "queue full"}
        self.transfers += 1
        tr = Transfer(self.transfers, action, a, b, legs, t)
        g.queue.append(Leg(tr))
        return {**ev, "type": "transfer_queued", "transfer": tr.tid, "legs": len(legs), "via": [x[2] for x in legs[:-1]]}

    # ------------------------------------------------------------------ one runtime step of physics
    def step(self, t: int) -> tuple[list[dict], list[tuple[Connect, str]]]:
        events: list[dict] = []
        done: list[tuple[Connect, str]] = []
        for g in self.gantries.values():
            if g.failed and g.repair_left > 0:
                g.repair_left -= 1
                if g.repair_left == 0:
                    g.failed, g.health = False, 1.0
                    events.append({"t": t, "type": "gantry_repaired", "bay": g.bay, "resources": round(g.resources, 3)})
            self._apply_health(g)
            if not g.failed and g.queue:
                self._advance(g, g.queue[0], t, events, done)
        for _ in range(SUBSTEPS):
            mujoco.mj_step(self.model, self.data)
        return events, done

    def _advance(self, g: Gantry, lg: Leg, t: int, events: list[dict], done: list) -> None:
        tr = lg.transfer
        bay, frm, to = tr.legs[tr.leg]
        if lg.phase == 0 and lg.phase_steps == 0:
            pick = tr.sample if tr.leg > 0 else (self.contents[frm][0] if self.contents[frm] else None)
            if pick is None or pick not in self.contents[frm]:
                return self._fail(g, lg, t, events, f"no material in {frm}")
            tr.sample = pick
            lg.spot = self._free_spot(to)
            if lg.spot is None:
                return self._fail(g, lg, t, events, f"no free spot in {to}")
        assert tr.sample is not None and lg.spot is not None
        sx, sy = (float(v) for v in (self.sample_xyz(tr.sample)[:2] if g.carrying is None else self.pos[frm]))
        dx, dy = lg.spot
        top = 0.05 + 2 * HALF + 0.1
        targets = [(sx, sy, SAFE_Z), (sx, sy, top), None, (sx, sy, SAFE_Z), (dx, dy, SAFE_Z), (dx, dy, top + 0.02), None,
                   (dx, dy, SAFE_Z)]
        lg.phase_steps += 1
        tip = self.tip_xyz(g.bay)
        if lg.phase == 2:  # grasp
            p = self.sample_xyz(tr.sample)
            if np.linalg.norm(p[:2] - tip[:2]) > GRASP_TOL * 3 or abs(p[2] + HALF - tip[2]) > GRASP_TOL * 2:
                return self._fail(g, lg, t, events, "grasp failed: tool not at the sample")
            self._weld(g.bay, tr.sample, True)
            g.carrying = tr.sample
            self.contents[frm].remove(tr.sample)
            events.append({"t": t, "type": "sample_grasped", "bay": g.bay, "sample": tr.sample, "at": frm, "transfer": tr.tid})
            lg.phase, lg.phase_steps = 3, 0
            return
        if lg.phase == 6:  # release
            s = g.carrying
            assert s is not None
            self._weld(g.bay, s, False)
            g.carrying = None
            if not self._inside(to, self.sample_xyz(s)):
                self._settle_lost(s, g, t, events)
                return self._fail(g, lg, t, events, f"sample not inside {to} after release")
            self.contents[to].append(s)
            lg.phase, lg.phase_steps = 7, 0
            return
        if lg.phase >= len(targets):
            g.queue.pop(0)
            g.legs_done += 1
            g.health = round(g.health - WEAR * (1 + SAMPLE_MASS), 6)
            events.append({"t": t, "type": "leg_complete", "bay": g.bay, "from": frm, "to": to, "transfer": tr.tid,
                           "health": round(g.health, 4)})
            if tr.leg + 1 < len(tr.legs):
                tr.leg += 1
                nb = self.gantries[tr.legs[tr.leg][0]]
                if nb.failed and nb.repair_left == 0 or len(nb.queue) >= QUEUE:
                    events.append({"t": t, "type": "transfer_failed", "transfer": tr.tid, "src": tr.src, "dst": tr.dst,
                                   "reason": f"relay stopped at {to}: bay {nb.bay} unavailable"})
                else:
                    nb.queue.append(Leg(tr))
            else:
                events.append({"t": t, "type": "transfer_complete", "transfer": tr.tid, "src": tr.src, "dst": tr.dst,
                               "legs": len(tr.legs), "requested_at": tr.requested_at})
                done.append((tr.action, g.bay))
            if g.health < FAIL_H:
                self._fail_gantry(g, t, events)
            return
        tgt = targets[lg.phase]
        assert tgt is not None
        self._set_target(g.bay, tgt)
        if np.linalg.norm(tip - np.array(tgt)) < PHASE_TOL + (0.08 if lg.phase in (1, 5) else 0):
            lg.phase += 1
            lg.phase_steps = 0
        elif lg.phase_steps > PHASE_TIMEOUT:
            self._fail(g, lg, t, events, f"phase {lg.phase} timeout (servo could not reach {tuple(round(x, 2) for x in tgt)})")

    def _settle_lost(self, s: str, g: Gantry, t: int, events: list[dict]) -> None:
        """A released or dropped sample becomes material of the container it lies in, or is recorded as outside."""
        p = self.sample_xyz(s)
        home = next((c for c in self.pos if self._inside(c, p)), None)
        if home is not None:
            self.contents[home].append(s)
        events.append({"t": t, "type": "sample_dropped", "bay": g.bay, "sample": s, "container": home,
                       "where": [round(float(v), 3) for v in p]})

    def _fail(self, g: Gantry, lg: Leg, t: int, events: list[dict], reason: str) -> None:
        g.queue.pop(0)
        if g.carrying is not None:
            self._weld(g.bay, g.carrying, False)
            s, g.carrying = g.carrying, None
            self._settle_lost(s, g, t, events)
        if lg.phase > 0:  # wear only if the gantry moved
            g.health = round(g.health - WEAR, 6)
        tr = lg.transfer
        events.append({"t": t, "type": "transfer_failed", "transfer": tr.tid, "bay": g.bay, "src": tr.src, "dst": tr.dst,
                       "leg": tr.leg, "reason": reason, "health": round(g.health, 4)})
        if g.health < FAIL_H:
            self._fail_gantry(g, t, events)

    def _fail_gantry(self, g: Gantry, t: int, events: list[dict]) -> None:
        g.failed = True
        if g.carrying is not None:
            self._weld(g.bay, g.carrying, False)
            s, g.carrying = g.carrying, None
            self._settle_lost(s, g, t, events)
        for lg in g.queue:
            events.append({"t": t, "type": "transfer_failed", "transfer": lg.transfer.tid, "src": lg.transfer.src,
                           "dst": lg.transfer.dst, "reason": f"gantry of bay {g.bay} failed"})
        g.queue.clear()
        if g.resources >= REPAIR_COST:
            g.resources -= REPAIR_COST
            g.repair_left = REPAIR_STEPS
            events.append({"t": t, "type": "gantry_failed", "bay": g.bay, "repair_in": REPAIR_STEPS,
                           "resources_left": round(g.resources, 3)})
        else:
            g.repair_left = 0
            events.append({"t": t, "type": "gantry_failed", "bay": g.bay, "repair_in": None,
                           "reason": "no resources for repair", "resources_left": round(g.resources, 3)})

    def _weld(self, bay: str, sample: str, on: bool) -> None:
        i = self._eq[f"grip_{bay}_{sample.replace('.', '_')}"]
        if on:  # keep the current relative pose (no snap)
            tb, sb = self._body[f"tool_{bay}"], self._body[f"sample_{sample.replace('.', '_')}"]
            rel = self.data.xpos[sb] - self.data.xpos[tb]
            rot = self.data.xmat[tb].reshape(3, 3)
            self.model.eq_data[i, 3:6] = rot.T @ rel
            self.model.eq_data[i, 6:10] = (1, 0, 0, 0)
            self.model.eq_data[i, 10] = 1.0
        self.data.eq_active[i] = 1 if on else 0

    # ------------------------------------------------------------------ record
    def state(self) -> dict:
        return {"gantries": {b: {"tip": [round(float(v), 3) for v in self.tip_xyz(b)], "health": round(g.health, 4),
                                 "failed": g.failed, "carrying": g.carrying, "resources": round(g.resources, 3),
                                 "queue": len(g.queue)} for b, g in self.gantries.items()},
                "samples": {c["cid"]: [round(float(v), 3) for v in self.sample_xyz(c["cid"])] for c in self.chambers},
                "contents": {k: list(v) for k, v in sorted(self.contents.items())}}

    def layout(self) -> dict:
        return {"bays": {b: list(p) for b, p in _bays(self.chambers).items()},
                "ports": {k: list(p) for k, p in ports(_bays(self.chambers)).items()}, "chamber_half": CH,
                "wall_height": WALL_H, "sample_half": HALF, "port_half": PORT, "safe_z": SAFE_Z}

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for arr in (self.data.qpos, self.data.qvel, self.data.ctrl, self.data.eq_active):
            h.update(np.ascontiguousarray(arr).tobytes())
        return h.hexdigest()[:16]
