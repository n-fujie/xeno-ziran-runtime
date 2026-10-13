"""The iOS stand-ins for scipy / pydantic (xzr/_compat) against the real libraries, and the engine's behavioural
conformance on both paths against the golden fixture (tests/fixtures/conformance_reference.json, generated natively)."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pydantic
import pytest
import scipy.sparse as ssp
from scipy.sparse import csgraph as scg
from scipy.spatial import cKDTree as RealKDTree
from scipy.stats import wasserstein_distance as real_w1

from xzr._compat import csgraph as ccg
from xzr._compat import pmodel
from xzr._compat import sparse as csp
from xzr._compat.spatial import cKDTree as CompatKDTree
from xzr._compat.stats import wasserstein_distance as compat_w1
from xzr.native.conformance import compare
from xzr.scenario import model as real_model
from xzr.scenario.io import SCENARIO_DIR

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads((ROOT / "tests" / "fixtures" / "conformance_reference.json").read_text())
# the only observation that may differ: the sampled shortest-path bottleneck metric (BFS vs scipy's Dijkstra
# tie-breaking among equally short paths); it never feeds back into the dynamics
OBSERVATION_TOLERANCE = 0.05
# The golden fixture was generated natively on macOS arm64 (Accelerate BLAS, Apple libm) — the platform the iOS app
# shares. Bit-level identity is documented for the same machine and software only (docs/REPRODUCIBILITY.md): on other
# platforms the vectorised exp() of the world generator and ARPACK on another BLAS give other last bits (observed on
# Linux x86_64 CI with the same numpy / scipy versions: every fingerprint differs from t0 on, graph structure is
# identical, rewind and save/load stay bit-identical within the run). There the platform-independent guarantees are
# checked instead of the golden values; the golden comparison runs on macOS arm64 (locally and in the macOS CI job).
REFERENCE_PLATFORM = ("Darwin", "arm64")


def on_reference_platform() -> bool:
    return (platform.system(), platform.machine()) == REFERENCE_PLATFORM


def platform_independent_differences(reference: dict, candidate: dict, compat: bool) -> list[str]:
    """What must hold on every platform: the same graph (size, live connections, start step), bit-identical rewind and
    save/load within the run, and — on the stand-in path — the cached desktop reference hierarchy."""
    out = []
    for name, ref in reference.items():
        c = candidate[name]
        for k in ("n", "edges", "t0"):
            if c.get(k) != ref.get(k):
                out.append(f"{name}.{k}: {ref.get(k)} != {c.get(k)}")
        for a, b in (("fp_load_t0", "fp_t0"), ("fp_rewind_60", "fp_60"), ("fp_load_50", "fp_50")):
            if c.get(a) != c.get(b):
                out.append(f"{name}: {a} != {b} within the run")
        if compat and c.get("hierarchy") != ref.get("hierarchy"):
            out.append(f"{name}.hierarchy: the stand-in path did not use the cached reference hierarchy")
    return out


def _graph(seed: int, n: int = 300, m: int = 1500):
    rng = np.random.default_rng(seed)
    r, c = rng.integers(0, n, m), rng.integers(0, n, m)
    return n, r, c, ssp.csr_matrix((np.ones(m), (r, c)), shape=(n, n)), csp.csr_matrix((np.ones(m), (r, c)), shape=(n, n))


@pytest.mark.parametrize("seed", range(5))
def test_sparse_and_graph_operations_match_scipy(seed):
    n, r, c, real, mine = _graph(seed)
    assert np.array_equal(real.toarray(), mine.toarray())
    assert np.array_equal(real.T.toarray(), mine.T.toarray())
    assert np.array_equal(np.asarray(real.sum(1)), mine.sum(1))
    v = np.random.default_rng(seed).random(n)
    assert np.allclose(real @ v, mine @ v, rtol=0, atol=1e-12)
    idx = np.random.default_rng(seed + 9).permutation(n)[: n // 2]
    assert np.array_equal(real[idx][:, idx].toarray(), mine[idx][:, idx].toarray())
    d = np.random.default_rng(seed).random(n)
    assert np.array_equal((ssp.diags(d) @ (real + ssp.identity(n)) @ ssp.diags(d)).toarray(),
                          (csp.diags(d) @ (mine + csp.identity(n)) @ csp.diags(d)).toarray())
    for conn in ("weak", "strong"):
        k1, l1 = scg.connected_components(real, directed=True, connection=conn)
        k2, l2 = ccg.connected_components(mine, directed=True, connection=conn)
        assert k1 == k2 and sorted(np.bincount(l1)) == sorted(np.bincount(l2))
        assert len({(a, b) for a, b in zip(l1, l2, strict=True)}) == k1  # the same partition
    for s in range(0, n, 37):
        o1 = scg.breadth_first_order(real, s, directed=True, return_predecessors=False)
        assert set(o1) == set(ccg.breadth_first_order(mine, s, directed=True, return_predecessors=False))
    src = np.arange(0, n, 41)
    d1, p1 = scg.shortest_path(real, method="D", directed=True, unweighted=True, indices=src, return_predecessors=True)
    d2, p2 = ccg.shortest_path(mine, method="D", directed=True, unweighted=True, indices=src, return_predecessors=True)
    assert np.array_equal(d1, d2)  # distances exact; predecessors valid shortest-path parents
    for row in range(len(src)):
        for v in np.flatnonzero(p2[row] >= 0):
            assert d2[row, p2[row, v]] == d2[row, v] - 1 and mine[[p2[row, v]]][:, [v]].toarray()[0, 0] > 0


@pytest.mark.parametrize("seed", range(3))
def test_nearest_neighbours_match_ckdtree(seed):
    pts = np.random.default_rng(seed).normal(size=(1200, 2))
    d1, i1 = RealKDTree(pts).query(pts, k=40)
    d2, i2 = CompatKDTree(pts).query(pts, k=40)
    assert np.array_equal(i1, i2) and np.allclose(d1, d2, rtol=0, atol=1e-12)


def test_wasserstein_matches_scipy():
    rng = np.random.default_rng(3)
    for _ in range(20):
        x, y = rng.normal(size=rng.integers(1, 300)), rng.exponential(size=rng.integers(1, 300))
        assert compat_w1(x, y) == real_w1(x, y)


def _compat_model_module():
    """scenario/model.py executed against the pure-Python model layer (as on iOS)."""
    src = (ROOT / "xzr" / "scenario" / "model.py").read_text()
    ns = {"__name__": "xzr.scenario._model_compat_test"}
    sys.modules[ns["__name__"]] = type(sys)(ns["__name__"])
    mod = sys.modules[ns["__name__"]]
    mod.__dict__["__package__"] = "xzr.scenario"
    os.environ["XZR_FORCE_COMPAT"] = "1"
    try:
        import xzr._compat as compat_pkg
        old = compat_pkg.FORCE
        compat_pkg.FORCE = True
        exec(compile(src, "model.py", "exec"), mod.__dict__)  # noqa: S102 — the module's own source
    finally:
        compat_pkg.FORCE = old
        os.environ.pop("XZR_FORCE_COMPAT", None)
    assert mod.BaseModel is pmodel.BaseModel
    return mod


def test_model_layer_matches_pydantic_on_every_scenario_and_rejects_the_same_inputs():
    cm = _compat_model_module()
    saved = [p for p in (ROOT / "tests" / "fixtures").glob("*.json") if "scenario" in p.read_text()[:2000]]
    docs = [json.loads(p.read_text()) for p in sorted(SCENARIO_DIR.glob("*.json"))]
    docs += [d["scenario"] for p in saved if isinstance(d := json.loads(p.read_text()), dict) and "scenario" in d
             and isinstance(d["scenario"], dict)]
    assert len(docs) >= 5
    for d in docs:
        a = real_model.Scenario.model_validate(d)
        b = cm.Scenario.model_validate(d)
        assert a.model_dump(mode="json", exclude_none=True) == b.model_dump(mode="json", exclude_none=True)
        assert a.model_dump() == b.model_dump()
    base = docs[0]
    invalid = [
        {**base, "unknown_field": 1},
        {**base, "generator": {**base["generator"], "n": 5}},
        {**base, "generator": {**base["generator"], "mean_degree": 0}},
        {**base, "generator": {**base["generator"], "n": "many"}},
        {**base, "name": 3},
        {**base, "warmup": -1},
        {**base, "frozen": ["no-such-set"]},
        {**base, "explicit": {"nodes": [], "edges": []}},
        {"name": "x"},
    ]
    for d in invalid:
        with pytest.raises(pydantic.ValidationError):
            real_model.Scenario.model_validate(d)
        with pytest.raises(pmodel.ValidationError):
            cm.Scenario.model_validate(d)
    # lax coercions pydantic applies are applied identically
    lax = {**base, "seed": "7", "generator": {**base["generator"], "n": 600.0, "mean_degree": 6}}
    assert (real_model.Scenario.model_validate(lax).model_dump() == cm.Scenario.model_validate(lax).model_dump())


def _snapshot(names: list[str], compat: bool) -> dict:
    env = {**os.environ, "OMP_NUM_THREADS": "1", **({"XZR_FORCE_COMPAT": "1"} if compat else {})}
    code = ("import json,sys; from xzr.native.conformance import snapshot; "
            f"print(json.dumps(snapshot({names!r})))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                         check=True, timeout=900).stdout
    return json.loads(out.strip().splitlines()[-1])


@pytest.mark.parametrize("compat", [False, True], ids=["desktop-scipy", "ios-standins"])
def test_engine_conformance_against_the_golden_fixture(compat):
    names = ["small-600", "reason-lab", "demo-3k"]
    ref = {k: REFERENCE[k] for k in names}
    snap = _snapshot(names, compat)
    assert platform_independent_differences(ref, snap, compat) == []
    if not on_reference_platform():
        return  # golden bit-level values are defined for REFERENCE_PLATFORM only (see the comment there)
    r = compare(ref, snap, tol=OBSERVATION_TOLERANCE)
    assert r["exact_differences"] == []  # dynamics, hierarchy, rewind, save/load: bit-identical
    assert r["observation_differences"] == []


def test_platform_independent_checks_catch_broken_guarantees():
    ref = {"s": {"n": 10, "edges": 20, "t0": 0, "hierarchy": "h"}}
    ok = {"s": {"n": 10, "edges": 20, "t0": 0, "hierarchy": "h", "fp_t0": "a", "fp_load_t0": "a", "fp_50": "b",
                "fp_load_50": "b", "fp_60": "c", "fp_rewind_60": "c"}}
    assert platform_independent_differences(ref, ok, compat=True) == []
    for key, val in (("edges", 21), ("fp_rewind_60", "x"), ("fp_load_t0", "x"), ("hierarchy", "other")):
        bad = {"s": {**ok["s"], key: val}}
        assert platform_independent_differences(ref, bad, compat=True), key
    # a hierarchy computed by scipy may differ by platform; only the stand-in path must use the cached one
    assert platform_independent_differences(ref, {"s": {**ok["s"], "hierarchy": "other"}}, compat=False) == []


def test_a_hierarchy_without_a_reference_is_labelled_as_computed_on_device():
    code = ("import json; from xzr.scenario.io import load_sample; from xzr.service.session import Session; "
            "a = Session(load_sample('small-600')); "
            "b = Session(load_sample('small-600').model_copy(update={'seed': 12345})); "
            "print(json.dumps([a.info()['hierarchy_source'], b.info()['hierarchy_source']])); a.close(); b.close()")
    env = {**os.environ, "XZR_FORCE_COMPAT": "1", "OMP_NUM_THREADS": "1"}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True,
                         timeout=600).stdout.strip().splitlines()[-1]
    bundled, custom = json.loads(out)
    assert bundled == "reference"  # the bundled scenario uses the desktop reference hierarchy
    assert custom.startswith("on-device")  # a new topology says it was computed on the device
