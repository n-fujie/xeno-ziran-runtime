"""Generate cross-language protocol fixtures (binary frames + expected decoded JSON) for the frontend tests.

    python backend/scripts/make_fixtures.py          # writes frontend/src/proto/__fixtures__/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xzr.runtime.engine import Engine  # noqa: E402
from xzr.runtime.generator import latent_geometric  # noqa: E402
from xzr.runtime.intervention import Gate, Sever  # noqa: E402
from xzr.service.protocol import encode_aggregates, encode_deltas, encode_snapshot  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "proto" / "__fixtures__"


def build() -> dict[str, bytes | str]:
    g = latent_geometric(300, seed=21)
    e = Engine(g.state, seed=21)
    e.run(40)
    e.set_overlay([Gate((1, 2, 3), 0.5)])
    e.apply([Sever(tuple(np.flatnonzero(e.state.alive)[:3].tolist()))])
    steps = e.run(6, collect=True)
    e.state.diff[:] += 2.0  # force one dense state section into the fixture
    steps.append(e.step())
    frame = encode_deltas(steps)
    snap = encode_snapshot(e)
    labels = np.arange(e.state.n) % 8
    agg = encode_aggregates(0, labels, 8, steps, e.state.diff, e.state.t)
    expected = {
        "steps": [
            {"t": d.t, "diffIdx": d.diff_idx.tolist(), "diffQ": d.diff_q.tolist(),
             "diffDense": None if d.diff_dense is None else d.diff_dense.tolist(), "ignitions": d.ignitions.tolist(),
             "penetrationEdges": d.penetrations[:, 0].tolist(), "cuts": d.cuts.tolist(),
             "newEdges": d.new_connections[:, 0].tolist(), "gateEdge": d.gate_edge.tolist(),
             "returns": d.returns.tolist(), "reconfEdges": d.reconfigurations[:, 0].tolist()}
            for d in steps],
        "snapshot": {"t": e.state.t, "n": e.state.n, "form": e.state.form.astype(int).tolist()[:20]},
        "aggregates": {"level": 0, "k": 8, "t": e.state.t},
    }
    return {"frame.bin": frame, "snapshot.bin": snap, "aggregates.bin": agg,
            "expected.json": json.dumps(expected, indent=1)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in build().items():
        p = OUT / name
        if isinstance(data, bytes):
            p.write_bytes(data)
        else:
            p.write_text(data)
    print(f"wrote fixtures to {OUT}")


if __name__ == "__main__":
    main()
