"""Per-step deltas and their compact binary transport encoding.

A StepDelta is the complete semantic record of one step. Transport may *merge* several deltas into
one frame, and may quantize continuous values, but it never drops an event.

Binary layout (little-endian, every section padded to 4 bytes so the client can view arrays in place):

    step   := u32 t, u32 n_sections, section*
    section:= u32 kind, u32 count, payload (column arrays, each padded to 4 bytes)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

import numpy as np

I32 = np.int32
EMPTY_I = np.zeros(0, dtype=I32)
EMPTY_F = np.zeros(0, dtype=np.float32)
EMPTY_U8 = np.zeros(0, dtype=np.uint8)

# section kinds — keep in sync with frontend/src/proto/decode.ts
K_DIFF, K_FORM, K_IGNITE, K_PENETRATE, K_TRANSFORM, K_RETURN, K_DECAY = 1, 2, 3, 4, 5, 6, 7
K_CUT, K_NEW, K_REMOVED, K_RECONF, K_WEIGHT, K_MEMORY, K_GATE = 8, 9, 10, 11, 12, 13, 14
K_DIFF_DENSE, K_MEMORY_DENSE = 15, 16  # full u8[N] arrays, used when that is smaller than index/value pairs

EVENT_KINDS = ("ignitions", "penetrations", "transformations", "returns", "decays", "cuts", "new_connections",
               "removed_connections", "reconfigurations")


@dataclass
class StepDelta:
    t: int
    # state delta (quantized, only changed entries)
    diff_idx: np.ndarray = field(default_factory=lambda: EMPTY_I)
    diff_q: np.ndarray = field(default_factory=lambda: EMPTY_U8)
    mem_idx: np.ndarray = field(default_factory=lambda: EMPTY_I)
    mem_q: np.ndarray = field(default_factory=lambda: EMPTY_U8)
    diff_dense: np.ndarray | None = None
    mem_dense: np.ndarray | None = None
    weight_edge: np.ndarray = field(default_factory=lambda: EMPTY_I)
    weight_val: np.ndarray = field(default_factory=lambda: EMPTY_F)
    gate_edge: np.ndarray = field(default_factory=lambda: EMPTY_I)
    gate_val: np.ndarray = field(default_factory=lambda: EMPTY_F)
    # events
    ignitions: np.ndarray = field(default_factory=lambda: EMPTY_I)
    penetrations: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=I32))  # edge, origin, depth
    transformations: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), dtype=I32))  # node, new form
    returns: np.ndarray = field(default_factory=lambda: EMPTY_I)
    decays: np.ndarray = field(default_factory=lambda: EMPTY_I)
    cuts: np.ndarray = field(default_factory=lambda: EMPTY_I)
    new_connections: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=I32))  # edge, src, dst
    new_weights: np.ndarray = field(default_factory=lambda: EMPTY_F)
    removed_connections: np.ndarray = field(default_factory=lambda: EMPTY_I)
    reconfigurations: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=I32))  # edge, old, new
    retired: np.ndarray = field(default_factory=lambda: EMPTY_I)  # connections retired by a composite operation
    penetration_receivers: np.ndarray = field(default_factory=lambda: EMPTY_I)  # row-aligned with penetrations
    # per-step scalars used by shape detection
    total_diff: float = 0.0
    memory_dependent_ignitions: int = 0
    carried_flow: float = 0.0

    def counts(self) -> dict[str, int]:
        return {k: int(len(getattr(self, k))) for k in EVENT_KINDS}

    def to_json(self) -> dict:
        return {
            "t": self.t,
            "ignitions": self.ignitions.tolist(),
            "penetrations": self.penetrations.tolist(),
            "transformations": self.transformations.tolist(),
            "returns": self.returns.tolist(),
            "decays": self.decays.tolist(),
            "cuts": self.cuts.tolist(),
            "new_connections": self.new_connections.tolist(),
            "removed_connections": self.removed_connections.tolist(),
            "reconfigurations": self.reconfigurations.tolist(),
        }


def _pad(b: bytes) -> bytes:
    r = len(b) % 4
    return b if r == 0 else b + b"\0" * (4 - r)


def _col(a: np.ndarray, dt: type) -> bytes:
    return _pad(np.ascontiguousarray(a, dtype=dt).tobytes())


def _section(kind: int, count: int, *cols: bytes) -> bytes:
    return struct.pack("<II", kind, count) + b"".join(cols)


def encode_step(d: StepDelta, node_filter: np.ndarray | None = None) -> bytes:
    """Encode one delta. ``node_filter`` (bool mask) restricts *state* sections (not events) to a subscription."""
    secs: list[bytes] = []
    u32, u8, f32 = np.uint32, np.uint8, np.float32

    def filt(idx: np.ndarray, *vals: np.ndarray) -> tuple[np.ndarray, ...]:
        if node_filter is None or len(idx) == 0:
            return (idx, *vals)
        m = node_filter[idx]
        return (idx[m], *(v[m] for v in vals))

    if d.diff_dense is not None:
        secs.append(_section(K_DIFF_DENSE, len(d.diff_dense), _col(d.diff_dense, u8)))
    if d.mem_dense is not None:
        secs.append(_section(K_MEMORY_DENSE, len(d.mem_dense), _col(d.mem_dense, u8)))
    di, dq = filt(d.diff_idx, d.diff_q)
    if len(di):
        secs.append(_section(K_DIFF, len(di), _col(di, u32), _col(dq, u8)))
    mi, mq = filt(d.mem_idx, d.mem_q)
    if len(mi):
        secs.append(_section(K_MEMORY, len(mi), _col(mi, u32), _col(mq, u8)))
    if len(d.weight_edge):
        secs.append(_section(K_WEIGHT, len(d.weight_edge), _col(d.weight_edge, u32), _col(d.weight_val, f32)))
    if len(d.gate_edge):
        secs.append(_section(K_GATE, len(d.gate_edge), _col(d.gate_edge, u32), _col(d.gate_val, f32)))
    if len(d.ignitions):
        secs.append(_section(K_IGNITE, len(d.ignitions), _col(d.ignitions, u32)))
    if len(d.penetrations):
        p = d.penetrations
        secs.append(_section(K_PENETRATE, len(p), _col(p[:, 0], u32), _col(p[:, 1], u32), _col(p[:, 2], u32)))
    if len(d.transformations):
        tr = d.transformations
        secs.append(_section(K_TRANSFORM, len(tr), _col(tr[:, 0], u32), _col(tr[:, 1], u32)))
    if len(d.returns):
        secs.append(_section(K_RETURN, len(d.returns), _col(d.returns, u32)))
    if len(d.decays):
        secs.append(_section(K_DECAY, len(d.decays), _col(d.decays, u32)))
    if len(d.cuts):
        secs.append(_section(K_CUT, len(d.cuts), _col(d.cuts, u32)))
    removed = np.concatenate([d.removed_connections, d.retired]) if len(d.retired) else d.removed_connections
    if len(removed):
        secs.append(_section(K_REMOVED, len(removed), _col(removed, u32)))
    if len(d.new_connections):
        nc = d.new_connections
        secs.append(_section(K_NEW, len(nc), _col(nc[:, 0], u32), _col(nc[:, 1], u32), _col(nc[:, 2], u32),
                             _col(d.new_weights, f32)))
    if len(d.reconfigurations):
        rc = d.reconfigurations
        secs.append(_section(K_RECONF, len(rc), _col(rc[:, 0], u32), _col(rc[:, 1], u32), _col(rc[:, 2], u32)))
    # order matters for the client: removals are applied before slots are reused by new connections
    return struct.pack("<II", d.t, len(secs)) + b"".join(secs)


def decode_step(buf: bytes | memoryview, off: int = 0) -> tuple[dict, int]:
    """Reference decoder (used by tests; the browser has its own in TypeScript)."""
    mv = memoryview(buf)
    t, ns = struct.unpack_from("<II", mv, off)
    off += 8
    out: dict = {"t": t}
    spec = {
        K_DIFF: ("diff", ("u4", "u1")), K_DIFF_DENSE: ("diff_dense", ("u1",)), K_MEMORY_DENSE: ("memory_dense", ("u1",)),
        K_MEMORY: ("memory", ("u4", "u1")), K_WEIGHT: ("weight", ("u4", "f4")),
        K_GATE: ("gate", ("u4", "f4")), K_IGNITE: ("ignitions", ("u4",)), K_PENETRATE: ("penetrations", ("u4",) * 3),
        K_TRANSFORM: ("transformations", ("u4", "u4")), K_RETURN: ("returns", ("u4",)), K_DECAY: ("decays", ("u4",)),
        K_CUT: ("cuts", ("u4",)), K_NEW: ("new_connections", ("u4", "u4", "u4", "f4")),
        K_REMOVED: ("removed_connections", ("u4",)), K_RECONF: ("reconfigurations", ("u4",) * 3),
    }
    for _ in range(ns):
        kind, count = struct.unpack_from("<II", mv, off)
        off += 8
        name, cols = spec[kind]
        arrs = []
        for c in cols:
            size = count * np.dtype(c).itemsize
            arrs.append(np.frombuffer(mv[off:off + size], dtype="<" + c).copy())
            off += size + ((4 - size % 4) % 4)
        out[name] = arrs
    return out, off


def quantize(values: np.ndarray, vmax: float) -> np.ndarray:
    """Log quantization of non-negative magnitudes into 0..255."""
    q = np.log1p(np.maximum(values, 0.0)) * (255.0 / np.log1p(vmax))
    return np.clip(np.rint(q), 0, 255).astype(np.uint8)


def dequantize(q: np.ndarray, vmax: float) -> np.ndarray:
    return np.expm1(q.astype(np.float64) * (np.log1p(vmax) / 255.0))
