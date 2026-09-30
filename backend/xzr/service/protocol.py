"""WebSocket binary frames. Keep in sync with frontend/src/proto/decode.ts.

    frame  := u32 type, ...
    type 1 (deltas):     u32 n_steps, step*                       (see runtime/delta.py)
    type 2 (snapshot):   u32 t, u32 n, u8 diff_q[n]ᵖ, u8 mem_q[n]ᵖ, u8 form[n]ᵖ, u8 frozen[n]ᵖ, f32 theta_eff[n], f32 age[n]
    type 3 (aggregates): u32 level, u32 k, u32 t, f32 ignitions[k], f32 mean_difference[k]
ᵖ = padded to 4 bytes.
"""

from __future__ import annotations

import struct

import numpy as np

from ..runtime.delta import StepDelta, encode_step, quantize
from ..runtime.engine import MEM_QMAX, Engine

FRAME_DELTAS, FRAME_SNAPSHOT, FRAME_AGGREGATES = 1, 2, 3


def _pad(b: bytes) -> bytes:
    return b + b"\0" * ((4 - len(b) % 4) % 4)


def encode_deltas(steps: list[StepDelta], node_filter: np.ndarray | None = None) -> bytes:
    return struct.pack("<II", FRAME_DELTAS, len(steps)) + b"".join(encode_step(d, node_filter) for d in steps)


def encode_snapshot(engine: Engine) -> bytes:
    s = engine.state
    age = np.minimum(s.t - s.last_ignite, 10**6).astype("<f4")
    return b"".join([
        struct.pack("<III", FRAME_SNAPSHOT, s.t, s.n),
        _pad(quantize(s.diff, s.params.quant_max).tobytes()),
        _pad(quantize(s.memory, MEM_QMAX).tobytes()),
        _pad(s.form.astype(np.uint8).tobytes()),
        _pad(s.frozen.astype(np.uint8).tobytes()),
        s.theta_eff().astype("<f4").tobytes(),
        age.tobytes(),
    ])


def encode_aggregates(level: int, labels: np.ndarray, k: int, steps: list[StepDelta], diff: np.ndarray, t: int) -> bytes:
    ign = np.zeros(k)
    for d in steps:
        if len(d.ignitions):
            ign += np.bincount(labels[d.ignitions], minlength=k)
    cnt = np.maximum(np.bincount(labels, minlength=k), 1)
    mean = np.bincount(labels, diff, minlength=k) / cnt
    return struct.pack("<IIII", FRAME_AGGREGATES, level, k, t) + ign.astype("<f4").tobytes() + mean.astype("<f4").tobytes()
