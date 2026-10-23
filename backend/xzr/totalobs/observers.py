"""Observers: sensors that read the world, disturb it, wear out, report through a delayed and cuttable channel to a hub, and a record store that can lose records.

An observation is an operation inside the world, not a window on it:
  * it reads block means at the sensor's *scale* (block size ``k``, grid offset ``(oy, ox)``) from the regions within its radius;
  * it costs resources (one unit per block measured; a shared pool per step: sensors compete, an unserved block is not read);
  * it disturbs what it reads (``backaction``: a fraction of the activity in the footprint is absorbed), so two sensors with overlapping footprints
    interfere and the order of observation and intervention matters;
  * the world wears the sensor (``wear`` x mean activity in the footprint lowers its health; at zero it fails: the observing condition expires);
  * the report reaches the hub after ``hops x latency`` steps, and not at all when the sensor sits in a communication outage zone;
  * the hub keeps a bounded store; records can be lost. Losing a record never undoes what the observation or intervention did to the world.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .world import World, WorldConfig


@dataclass
class Sensor:
    sid: str
    region: int
    radius: int = 2
    scale: int = 1  # block size (regions); 1 = the finest scale
    period: int = 4  # observation period in steps
    phase: int = 0
    noise: float = 0.02
    backaction: float = 0.05
    wear: float = 0.08
    health: float = 10.0
    offset: tuple[int, int] = (0, 0)  # the block grid's origin: the observation boundary
    alive: bool = True

    def spec(self) -> dict:
        return {
            "sid": self.sid,
            "region": self.region,
            "radius": self.radius,
            "scale": self.scale,
            "period": self.period,
            "phase": self.phase,
            "noise": self.noise,
            "backaction": self.backaction,
            "offset": list(self.offset),
        }


def block_of(cfg: WorldConfig, region: int, scale: int, offset: tuple[int, int]) -> tuple[int, int]:
    r, c = divmod(region, cfg.cols)
    return ((r + offset[0]) // scale, (c + offset[1]) // scale)


@dataclass
class Record:
    sid: str
    t_obs: int
    t_arrive: int
    scale: int
    offset: tuple[int, int]
    blocks: dict[tuple[int, int], tuple[float, tuple[int, ...]]]  # block -> (mean reading, regions measured)


@dataclass
class ObserverNet:
    cfg: WorldConfig
    sensors: dict[str, Sensor] = field(default_factory=dict)
    hub: int = 0
    latency: int = 1  # steps per grid hop between a sensor and the hub
    pool: float = 40.0  # resource units per step, shared
    capacity: int = 400  # records the hub keeps
    store: list[Record] = field(default_factory=list)
    stats: dict[str, float] = field(
        default_factory=lambda: {
            "observations": 0,
            "blocks_read": 0,
            "denied_blocks": 0,
            "cost": 0.0,
            "lost_in_transit": 0,
            "records_lost": 0,
            "expired": 0,
            "interference": 0.0,
        }
    )
    # freshness rule of the hub's view: "observation" (v1: a record is usable while its age since OBSERVATION is within the window, so a record delayed in transit
    # longer than the window is discarded on arrival) or "arrival" (v2: the window counts from the record's ARRIVAL)
    freshness: str = "observation"
    received: int = 0  # the hub's own accounting: records received, and evicted by capacity (a gap against len(store) means records were lost)
    evicted: int = 0
    per: dict[str, dict] = field(default_factory=dict)  # per-sensor counts of what happened to its observations (verifier-side audit)
    cut_zone: set[int] = field(default_factory=set)  # regions where the link to the hub is down (a regional communication outage)
    _rng: np.random.Generator | None = None

    def seed(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed * 104729 + 7)

    def add(self, s: Sensor) -> None:
        self.sensors[s.sid] = s

    # ------------------------------------------------------------------------------------------------- one step of observation
    def observe(self, w: World, priority: list[str] | None = None) -> list[Record]:
        cfg = self.cfg
        assert self._rng is not None, "call seed()"
        budget = self.pool
        out: list[Record] = []
        order = priority or sorted(self.sensors)
        for sid in order:
            s = self.sensors[sid]
            if not s.alive or (w.t - s.phase) % s.period != 0:
                continue
            foot = np.flatnonzero(w.d[s.region] <= s.radius)
            groups: dict[tuple[int, int], list[int]] = {}
            for i in foot:
                groups.setdefault(block_of(cfg, int(i), s.scale, s.offset), []).append(int(i))
            blocks: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {}
            for b in sorted(groups):
                if budget < 1.0:
                    self.stats["denied_blocks"] += 1
                    continue
                budget -= 1.0
                self.stats["cost"] += 1.0
                idx = groups[b]
                val = float(np.mean(w.u[idx])) + float(self._rng.normal(0.0, s.noise / np.sqrt(len(idx))))
                blocks[b] = (max(val, 0.0), tuple(idx))
                self.stats["blocks_read"] += 1
            slot = self.per.setdefault(sid, {"observed": 0, "denied_blocks": 0, "lost_in_transit": 0, "expected_blocks": 0})
            slot["expected_blocks"] += len(groups)
            slot["denied_blocks"] += len(groups) - len(blocks)
            if not blocks:
                continue
            slot["observed"] += 1
            self.stats["observations"] += 1
            served = np.array([i for _, (_, idx) in blocks.items() for i in idx])
            before = float(w.u[served].sum())
            w.absorb(served, s.backaction)  # observation disturbs what it reads
            self.stats["interference"] += before * s.backaction
            s.health -= s.wear * float(np.mean(w.u[served]))  # the object wears the observer
            if s.health <= 0:
                s.alive = False
                self.stats["expired"] += 1
            delay = max(0, int(w.d[s.region, self.hub])) * self.latency
            rec = Record(sid, w.t, w.t + delay, s.scale, s.offset, blocks)
            if s.region in self.cut_zone:
                self.stats["lost_in_transit"] += 1
                slot["lost_in_transit"] += 1
                continue
            self.store.append(rec)
            self.received += 1
            out.append(rec)
            if len(self.store) > self.capacity:
                self.store.pop(0)
                self.evicted += 1
        return out

    # ------------------------------------------------------------------------------------------------- the hub's view (what an agent may read)
    def view(self, t: int, staleness: int) -> list[Record]:
        """The records that have arrived by ``t`` and are not older than ``staleness`` steps (the only access an agent has to the world)."""
        if self.freshness == "arrival":
            return [r for r in self.store if r.t_arrive <= t and t - r.t_arrive <= staleness]
        return [r for r in self.store if r.t_arrive <= t and t - r.t_obs <= staleness]

    # ------------------------------------------------------------------------------------------------- losses (harness operations)
    def lose_records(self, t0: int, t1: int, sids: set[str] | None = None) -> int:
        keep = [r for r in self.store if not (t0 <= r.t_obs < t1 and (sids is None or r.sid in sids))]
        n = len(self.store) - len(keep)
        self.store = keep
        self.stats["records_lost"] += n
        return n

    def fail(self, sid: str) -> None:
        if self.sensors[sid].alive:
            self.sensors[sid].alive = False
            self.stats["expired"] += 1

    def cut(self, w: World, center: int, radius: int) -> None:
        """A communication outage over the regions within ``radius`` of ``center``: a sensor inside it observes but its reports do not arrive."""
        self.cut_zone |= {int(i) for i in np.flatnonzero(w.d[center] <= radius)}

    def restore_links(self) -> None:
        self.cut_zone = set()
