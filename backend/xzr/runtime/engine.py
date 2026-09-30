"""The deterministic, seeded step loop.

``Engine.step()`` applies the operations in a fixed order and returns a complete :class:`StepDelta`.
Identical (initial state, seed, overlay, actions at identical steps) ⇒ bit-identical runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import ops, relational
from .delta import EMPTY_I, I32, StepDelta, quantize
from .flags import Flags
from .intervention import (
    Action,
    Connect,
    Inject,
    OverlayItem,
    SetThreshold,
    Sever,
    apply_overlay,
    is_overlay,
)
from .state import State, fingerprint

WEIGHT_EPS = 0.05  # transport threshold for streaming weight changes (state array stays exact)
MEM_QMAX = 12.0
MEM_EVERY = 5  # memory afterimages are streamed every MEM_EVERY steps
QUANT_HYST = 3  # transport hysteresis in quantization levels (state arrays stay exact; events are unaffected)


@dataclass
class Driver:
    """A periodic source of difference at a set of configurations (scenario input, opaque)."""

    nodes: np.ndarray
    period: int
    amount: float
    phase: int = 0


@dataclass
class Checkpoint:
    t: int
    state: State
    rng_state: dict
    overlay: list
    carried_prev: np.ndarray
    q_diff: np.ndarray
    q_mem: np.ndarray
    sent_w: np.ndarray


@dataclass
class _Pending:
    cuts: list = field(default_factory=list)
    new: list = field(default_factory=list)
    gates: list = field(default_factory=list)


class Engine:
    def __init__(self, state: State, seed: int, drivers: list[Driver] | None = None,
                 base_overlay: list[OverlayItem] | None = None, checkpoint_every: int = 50,
                 max_checkpoints: int = 24, flags: Flags | None = None):
        self.state = state
        self.flags = flags or Flags()
        if self.flags.difference == "relational":
            relational.adopt(state)
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.drivers = drivers or []
        self.base_overlay: list[OverlayItem] = list(base_overlay or [])
        self.overlay: list[OverlayItem] = []
        self.checkpoint_every = checkpoint_every
        self.max_checkpoints = max_checkpoints
        self.checkpoints: dict[int, Checkpoint] = {}
        self._pending = _Pending()
        self._carried_prev = EMPTY_I
        # interventions as applied (step at which they were applied, kind, items) — replayed on rewind
        self.log: list[tuple[int, str, list]] = []
        self._replaying = False
        apply_overlay(state, self.base_overlay, self.overlay)
        self._reset_transport()
        self._save_checkpoint()

    # ------------------------------------------------------------------ transport mirrors
    def _reset_transport(self) -> None:
        s = self.state
        self._q_diff = quantize(s.diff, s.params.quant_max)
        self._q_mem = quantize(s.memory, MEM_QMAX)
        self._sent_w = s.weight.astype(np.float32)

    # ------------------------------------------------------------------ interventions
    def set_overlay(self, items: list[OverlayItem]) -> None:
        assert all(is_overlay(i) for i in items)
        if not self._replaying:
            self.log.append((self.state.t, "overlay", list(items)))
        self.overlay = list(items)
        changed = apply_overlay(self.state, self.base_overlay, self.overlay)
        if len(changed):
            self._pending.gates.append(changed)

    def apply(self, actions: list[Action]) -> None:
        s = self.state
        if not self._replaying:
            self.log.append((self.state.t, "actions", list(actions)))
        rel = self.flags.difference == "relational"
        for a in actions:
            if isinstance(a, Sever):
                self._pending.cuts.append(ops.sever(s, np.array(a.edges, dtype=I32)))
                if rel:
                    relational.fold_dead(s)
            elif isinstance(a, Connect):
                e = ops.add_connection(s, a.src, a.dst, a.weight)
                if e >= 0:
                    self._pending.new.append((e, a.src, a.dst))
            elif isinstance(a, SetThreshold):
                s.theta[list(a.nodes)] = a.value
            elif isinstance(a, Inject):
                np.add.at(s.diff, np.array(a.nodes, dtype=I32), a.amount)
                if rel:
                    np.add.at(s.xbuf, np.array(a.nodes, dtype=I32), a.amount)
            else:
                raise TypeError(f"not an action: {a!r}")

    # ------------------------------------------------------------------ step
    def step(self) -> StepDelta:
        s = self.state
        p = s.params
        s.t += 1
        t = s.t
        fx = self.flags
        rel = fx.difference == "relational"
        if rel:
            relational.fold_dead(s)
            before = s.diff.copy()
        ops.inject(s, self.rng)
        for dr in self.drivers:
            if dr.period > 0 and (t - dr.phase) % dr.period == 0:
                s.diff[dr.nodes] += dr.amount
        if rel:
            relational.absorb_external(s, before)
        total_before = float(s.diff.sum())

        wave = fx.wave_state == "on"
        if fx.fused_transition:
            if fx.threshold != "on" or fx.transition != "on":
                raise ValueError("fused_transition requires threshold='on' and transition='on'")
            ign, fl = ops.thresholded_transition(s, wave=wave, return_events=fx.return_events == "on")
        else:
            ign = ops.ignite(s, threshold=fx.threshold == "on", wave=wave, return_events=fx.return_events == "on")
            fl = ops.propagate(s, ign, wave=wave, enabled=fx.transition == "on")
        transforms = ops.transform(s, fl) if fx.transform == "on" else np.zeros((0, 2), I32)
        if rel:
            decays = relational.retain_and_decay(s, fl, retention=fx.retention == "on")
        else:
            decays = ops.retain_and_decay(s, fl, retention=fx.retention == "on")
        if fx.memory == "on":
            ops.remember(s, ign)
        if fx.adapt_source == "dominant":
            ops.adapt_weights(s, ign.penetrations[:, 0], self._carried_prev)
        elif fx.adapt_source == "all_carriers":
            ops.adapt_weights(s, ops.successful_carriers(s, self._carried_prev, ign.mask), self._carried_prev)
        self._carried_prev = fl.edges
        cuts = ops.cut(s) if fx.cut == "on" else EMPTY_I
        removed = ops.disconnect(s) if fx.disconnect == "on" else EMPTY_I
        freed = np.concatenate([cuts, removed])
        new = ops.connect(s, self.rng, ign, freed) if fx.connect == "on" else np.zeros((0, 3), I32)
        retired = EMPTY_I
        if fx.reconfigure == "redirect":
            reconf = ops.reconfigure(s, self.rng)
        elif fx.reconfigure == "mutation":
            reconf, retired = ops.reconfigure_by_mutation(s, self.rng)
        else:
            reconf = np.zeros((0, 3), I32)
        mutated = ops.mutate(s, self.rng)
        if rel:
            if fx.reconfigure == "redirect":
                relational.fold_redirected(s, reconf)
            relational.fold_redirected(s, mutated)
        if len(mutated):
            reconf = np.concatenate([reconf, mutated]) if len(reconf) else mutated

        # merge queued intervention events into this step's record
        pend = self._pending
        if pend.cuts:
            cuts = np.unique(np.concatenate([cuts, *pend.cuts])).astype(I32)
        new_w = s.weight[new[:, 0]].astype(np.float32) if len(new) else np.zeros(0, np.float32)
        if pend.new:
            pn = np.array(pend.new, dtype=I32).reshape(-1, 3)
            new = np.concatenate([pn, new])
            new_w = np.concatenate([s.weight[pn[:, 0]].astype(np.float32), new_w])
        gate_edge = np.unique(np.concatenate(pend.gates)).astype(I32) if pend.gates else EMPTY_I
        self._pending = _Pending()

        # quantized state delta
        qd = quantize(s.diff, p.quant_max)
        di = self._changed(qd, self._q_diff)
        self._q_diff[di] = qd[di]
        n = s.n
        diff_dense = None
        if len(di) * 5 > n:
            diff_dense, di = self._q_diff.copy(), EMPTY_I
        mi, mem_dense = EMPTY_I, None
        if t % MEM_EVERY == 0:
            qm = quantize(s.memory, MEM_QMAX)
            mi = self._changed(qm, self._q_mem)
            self._q_mem[mi] = qm[mi]
            if len(mi) * 5 > n:
                mem_dense, mi = self._q_mem.copy(), EMPTY_I
        w32 = s.weight.astype(np.float32)
        wi = np.flatnonzero(s.alive & (np.abs(w32 - self._sent_w) > WEIGHT_EPS)).astype(I32)
        self._sent_w[wi] = w32[wi]
        if len(new):
            self._sent_w[new[:, 0]] = w32[new[:, 0]]

        delta = StepDelta(
            t=t, diff_idx=di, diff_q=qd[di], mem_idx=mi, mem_q=self._q_mem[mi],
            diff_dense=diff_dense, mem_dense=mem_dense, weight_edge=wi, weight_val=w32[wi],
            gate_edge=gate_edge, gate_val=s.gate[gate_edge].astype(np.float32),
            ignitions=ign.fired, penetrations=ign.penetrations, transformations=transforms, returns=ign.returns,
            decays=decays, cuts=cuts, new_connections=new, new_weights=new_w, removed_connections=removed,
            retired=retired, penetration_receivers=ign.receivers,
            reconfigurations=reconf, total_diff=total_before, memory_dependent_ignitions=ign.memory_dependent,
            carried_flow=float(fl.flow.sum()),
        )
        if self.checkpoint_every and t % self.checkpoint_every == 0:
            self._save_checkpoint()
        return delta

    @staticmethod
    def _changed(q: np.ndarray, sent: np.ndarray) -> np.ndarray:
        """Indices whose quantized value moved by ≥ QUANT_HYST levels, or reached/left zero."""
        d = np.abs(q.astype(np.int16) - sent.astype(np.int16))
        return np.flatnonzero((d >= QUANT_HYST) | ((d > 0) & ((q == 0) | (sent == 0)))).astype(I32)

    def run(self, steps: int, collect: bool = False) -> list[StepDelta]:
        out = []
        for _ in range(steps):
            d = self.step()
            if collect:
                out.append(d)
        return out

    # ------------------------------------------------------------------ checkpoints / replay
    def snapshot(self) -> Checkpoint:
        return Checkpoint(self.state.t, self.state.copy(), dict(self.rng.bit_generator.state), list(self.overlay),
                          self._carried_prev.copy(), self._q_diff.copy(), self._q_mem.copy(), self._sent_w.copy())

    def _save_checkpoint(self) -> None:
        self.checkpoints[self.state.t] = self.snapshot()
        if len(self.checkpoints) > self.max_checkpoints:
            # thin: keep the initial checkpoint, drop every other one of the older half
            keys = sorted(self.checkpoints)
            older = keys[1:len(keys) // 2]
            for k in older[::2]:
                del self.checkpoints[k]

    def restore(self, cp: Checkpoint) -> None:
        self.state = cp.state.copy()
        self.rng = np.random.default_rng()
        self.rng.bit_generator.state = cp.rng_state
        self.overlay = list(cp.overlay)
        self._carried_prev = cp.carried_prev.copy()
        self._q_diff, self._q_mem, self._sent_w = cp.q_diff.copy(), cp.q_mem.copy(), cp.sent_w.copy()
        self._pending = _Pending()

    def rewind(self, t: int) -> int:
        """Restore the nearest checkpoint ≤ t and replay deterministically to t. Returns the reached step.

        Interventions logged after the checkpoint are re-applied at the same steps, so the replayed
        trajectory is bit-identical to the original one. Interventions at or after ``t`` are discarded.
        """
        keys = [k for k in self.checkpoints if k <= t]
        if not keys:
            raise ValueError("no checkpoint at or before requested step")
        self.restore(self.checkpoints[max(keys)])
        for k in [k for k in self.checkpoints if k > self.state.t]:
            del self.checkpoints[k]
        replay = [x for x in self.log if self.state.t <= x[0] < t]
        self.log = [x for x in self.log if x[0] < t]
        self._replaying = True
        try:
            while self.state.t < t:
                for at, kind, items in replay:
                    if at == self.state.t:
                        self.set_overlay(items) if kind == "overlay" else self.apply(items)
                self.step()
        finally:
            self._replaying = False
        self._reset_transport()
        return self.state.t

    def fork(self) -> Engine:
        """An independent engine continuing from exactly this point (same state and RNG state)."""
        e = Engine.__new__(Engine)
        e.seed = self.seed
        e.drivers = self.drivers
        e.base_overlay = list(self.base_overlay)
        e.flags = self.flags
        e.checkpoint_every = 0
        e.max_checkpoints = 0
        e.checkpoints = {}
        e.log = []
        e._replaying = False
        e.restore(self.snapshot())
        return e

    def fingerprint(self) -> str:
        return fingerprint(self.state, self.rng)
