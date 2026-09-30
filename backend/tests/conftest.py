from __future__ import annotations

import numpy as np
import pytest

from xzr.runtime.engine import Engine
from xzr.runtime.generator import latent_geometric
from xzr.runtime.state import Params, State, allocate


def make_state(n: int, edges: list[tuple[int, int]], **params) -> State:
    """A tiny explicit field without external input: thresholds 1, cap 1.8, retention 0.8."""
    p = Params(**{"input_rate": 0.0, "connect_per_step": 0, "reconfigure_per_step": 0, **params})
    st = allocate(n, len(edges) + 8, p)
    st.theta[:] = 1.0
    st.cap[:] = 1.8
    st.retention[:] = 0.8
    st.mem_coupling[:] = st.base_mem_coupling[:] = 0.0
    for j, (a, b) in enumerate(edges):
        st.src[j], st.dst[j] = a, b
        st.weight[j] = st.base_weight[j] = 1.0
        st.alive[j] = True
        st.capacity[j] = 100.0
    return st


@pytest.fixture
def small_world():
    def build(seed: int = 5, n: int = 500) -> Engine:
        g = latent_geometric(n, seed)
        return Engine(g.state, seed)
    return build


@pytest.fixture
def rng():
    return np.random.default_rng(0)
