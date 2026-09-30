"""Binary delta / tile / snapshot encodings and JSON schemas round-trip."""

from __future__ import annotations

import struct

import numpy as np
import pytest
from pydantic import ValidationError

from xzr.lod.hierarchy import build_hierarchy, symmetric_adjacency
from xzr.lod.tiles import edges_for, encode_tile
from xzr.practice.graph import Practice
from xzr.runtime.delta import decode_step, dequantize, encode_step, quantize
from xzr.runtime.intervention import Gate, Sever, from_dict, to_dict
from xzr.scenario.io import load_sample
from xzr.scenario.model import Scenario
from xzr.service.protocol import encode_deltas, encode_snapshot


def test_step_roundtrip_all_sections(small_world):
    e = small_world()
    e.run(60)
    e.set_overlay([Gate(tuple(range(10)), 0.5)])
    e.apply([Sever((11, 12))])
    for _ in range(40):
        d = e.step()
        buf = encode_step(d)
        out, off = decode_step(buf)
        assert off == len(buf) and out["t"] == d.t
        if len(d.ignitions):
            assert np.array_equal(out["ignitions"][0], d.ignitions)
        if len(d.diff_idx):
            assert np.array_equal(out["diff"][0], d.diff_idx) and np.array_equal(out["diff"][1], d.diff_q)
        if len(d.penetrations):
            for k in range(3):
                assert np.array_equal(out["penetrations"][k], d.penetrations[:, k])
        if len(d.new_connections):
            assert np.array_equal(out["new_connections"][0], d.new_connections[:, 0])
            assert np.allclose(out["new_connections"][3], d.new_weights)
        if len(d.cuts):
            assert np.array_equal(out["cuts"][0], d.cuts)


def test_dense_state_sections(small_world):
    e = small_world()
    e.state.diff[:] = 3.0  # every configuration changes → dense section
    d = e.step()
    assert d.diff_dense is not None and len(d.diff_idx) == 0
    out, _ = decode_step(encode_step(d))
    assert np.array_equal(out["diff_dense"][0], d.diff_dense)


def test_gate_and_sever_reach_the_delta(small_world):
    e = small_world()
    e.set_overlay([Gate((3, 4), 0.25)])
    alive = np.flatnonzero(e.state.alive)[:2]
    e.apply([Sever(tuple(alive.tolist()))])
    d = e.step()
    out, _ = decode_step(encode_step(d))
    assert set(out["gate"][0].tolist()) >= {3, 4}
    assert set(alive.tolist()) <= set(out["cuts"][0].tolist())


def test_quantization_monotone_and_bounded():
    v = np.linspace(0, 10, 1000)
    q = quantize(v, 10.0)
    assert np.all(np.diff(q.astype(int)) >= 0) and q[0] == 0 and q[-1] == 255
    back = dequantize(q, 10.0)
    assert np.max(np.abs(back - v) / (1 + v)) < 0.02


def test_frame_and_snapshot_layout(small_world):
    e = small_world()
    ds = e.run(5, collect=True)
    f = encode_deltas(ds)
    assert struct.unpack_from("<II", f) == (1, 5)
    snap = encode_snapshot(e)
    kind, t, n = struct.unpack_from("<III", snap)
    assert (kind, t, n) == (2, 5, e.state.n)
    pad = lambda k: k + (-k) % 4  # noqa: E731
    assert len(snap) == 12 + 4 * pad(n) + 8 * n


def test_tile_encoding(small_world):
    e = small_world()
    s = e.state
    nodes = np.arange(40, dtype=np.int32)
    edges, trunc = edges_for(s, nodes, 30, both_ends=False)
    xy = np.random.default_rng(0).random((s.n, 2)).astype(np.float32)
    buf = encode_tile(s, xy, nodes, edges, trunc)
    nn, ne, tr = struct.unpack_from("<III", buf)
    assert ne == len(edges) <= 30 and tr == int(trunc) and nn >= 40
    idx = np.frombuffer(buf, "<u4", nn, 12)
    assert set(nodes.tolist()) <= set(idx.tolist())


def test_intervention_dict_roundtrip():
    for it in (Gate((1, 2), 0.3), Sever((4,))):
        assert from_dict(to_dict(it)) == it


def test_scenario_roundtrip_and_validation():
    sc = load_sample("demo-3k")
    again = Scenario.model_validate_json(sc.model_dump_json())
    assert again == sc
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "x"})  # neither generator nor explicit
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "x", "generator": {"n": 50}, "drivers": [{"set": "nope", "period": 3,
                                                                                    "amount": 1}]})
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "x", "explicit": {"nodes": [{}], "edges": [{"src": 0, "dst": 3}]}})


def test_practice_roundtrip():
    p = Practice.from_json(load_sample("demo-3k").practice)
    p.remove_concept("human")
    p.withdraw("K4")
    q = Practice.from_json(p.to_json())
    assert q.to_json() == p.to_json()
    assert q.score().to_json() == p.score().to_json()


def test_hierarchy_addresses_resolve(small_world):
    e = small_world()
    s = e.state
    h = build_hierarchy(symmetric_adjacency(s.src[s.alive], s.dst[s.alive], s.n))
    for lv in range(4):
        for k in range(0, h.n_clusters(lv), max(1, h.n_clusters(lv) // 5)):
            members = h.resolve(h.address(lv, k))
            assert np.all(h.labels[lv][members] == k)
    assert sum(len(h.resolve(str(m))) for m in range(8)) == s.n
