"""SYNTHETIC example data for the interface and the data-processing tests.

These are artificial series that exercise every observation limit: a periodic joint angle, an artificial gap, a series sampled too slowly for a fast joint (TIME_WINDOW_MISMATCH),
a variable whose instrument does not carry it (INSTRUMENT_MISMATCH), a hand behind an observation boundary (BOUNDARY_INVISIBLE), a weak signal under the detection limit
(SIGNAL_BELOW_THRESHOLD), a rate with a small slow drift. **They are not a physiological or physical model and say nothing about any body.** Every record is sealed SYNTHETIC; the
generator is deterministic given the seed.
"""

from __future__ import annotations

import math
import random

from . import status as ST
from .body import Body, human_simplified_skeleton
from .mapping import coverage
from .provenance import Kind, Ledger, Provenance, seal
from .schema import VariableRegistry, default_registry

CREATOR = {"name": "teoo.synthetic/1", "role": "generator", "seed_declared": True}
SOURCE = {"kind": "generator", "description": "TEOO synthetic example generator (functional-test data, not a body model)", "declared_by": "teoo.synthetic"}
BANNER = "SYNTHETIC — artificial functional-test data. Not a measurement, not a physiological model."


def _channel(variable: str, target: str, unit: str, times: list[float], samples: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for s in samples:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    return {"variable": variable, "target": target, "unit": unit, "times": times, "samples": samples, "counts": counts}


def make_demo(seed: int = 7, duration_s: float = 20.0, created_at: str = "2026-01-01T00:00:00.000000Z") -> dict:
    rng = random.Random(seed)
    registry: VariableRegistry = default_registry()
    body: Body = human_simplified_skeleton(at=created_at)
    hz = 50.0
    t50 = [round(i / hz, 6) for i in range(int(duration_s * hz))]
    valid = ST.ObsStatus.MEASURED_VALID

    def periodic(amp: float, freq: float, phase: float, noise: float, mean: float = 0.0) -> list[float]:
        return [round(mean + amp * math.sin(2 * math.pi * freq * t + phase) + rng.gauss(0, noise), 3) for t in t50]

    knee = periodic(35, 0.5, 0.0, 0.4, 30)
    knee_s = [ST.sample(v, valid) for v in knee]
    for i in range(300, 340):  # an artificial dropout of 0.8 s: MISSING, cause unknown (never 0)
        knee_s[i] = ST.sample(None, ST.ObsStatus.MISSING, cause_known=False)
    hip = periodic(25, 0.5, 0.6, 0.3, 15)
    hip_s = [ST.sample(v, valid) for v in hip]
    elbow_s = [ST.sample(None, ST.ObsStatus.BOUNDARY_INVISIBLE, causes=["BOUNDARY_INVISIBLE"]) for _ in t50]  # behind an observation boundary: not observed, not absent
    ankle_slow_t = [float(i) for i in range(int(duration_s))]  # 1 Hz for a fast joint
    ankle_s = [ST.sample(None, ST.ObsStatus.TIME_WINDOW_MISMATCH, causes=["TIME_WINDOW_MISMATCH"]) for _ in ankle_slow_t]
    lean_s = [ST.sample(None, ST.ObsStatus.INSTRUMENT_MISMATCH, causes=["INSTRUMENT_MISMATCH"]) for _ in t50]
    hr_t = [float(i) for i in range(int(duration_s))]
    hr = [round(72 + 3 * math.sin(2 * math.pi * 0.05 * t) + rng.gauss(0, 0.6), 2) for t in hr_t]
    hr_s = [ST.sample(v, valid) for v in hr]
    temp_t = hr_t
    temp_s = [ST.sample(None, ST.ObsStatus.SIGNAL_BELOW_THRESHOLD, causes=["SIGNAL_BELOW_THRESHOLD"], detection_limit=0.1) for _ in temp_t]
    time_meta = {"device_clock": "synthetic-clock", "sampling_period_s": 1 / hz, "window_s": duration_s, "acquisition_start": None, "sync": None, "note": "unsynchronised on purpose: no reference clock is declared"}
    payload = {"body": {"id": body.id, "version": body.current["version"]}, "banner": BANNER, "time": time_meta, "generator": {"seed": seed, "duration_s": duration_s},
               "channels": [_channel("joint.angle.knee_l", "tgt.knee_l", "deg", t50, knee_s), _channel("joint.angle.hip_l", "tgt.hip_l", "deg", t50, hip_s),
                            _channel("joint.angle.elbow_r", "tgt.elbow_r", "deg", t50, elbow_s), _channel("joint.angle.ankle_l", "tgt.ankle_l", "deg", ankle_slow_t, ankle_s),
                            _channel("posture.trunk.lean", "tgt.trunk", "deg", t50, lean_s), _channel("hr.beat", "tgt.trunk", "1/min", hr_t, hr_s), _channel("temp.skin.forehead", "tgt.head", "degC", temp_t, temp_s)]}
    rec = seal(payload, provenance=Provenance.SYNTHETIC, kind=Kind.OBSERVATION, creator=CREATOR, source=SOURCE, created_at=created_at)
    ledger = Ledger()
    ledger.append(rec)
    return {"banner": BANNER, "registry": registry, "body": body, "records": [rec], "ledger": ledger, "coverage": coverage(body, [rec])}
