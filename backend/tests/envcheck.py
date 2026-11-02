"""What this environment reproduces: the platform of the golden fixtures, and whether the hierarchy it computes is the reference one.

Bit-level identity of the address hierarchy (spectral bisection: ARPACK / LAPACK / Accelerate) is documented for the same machine and software only (docs/REPRODUCIBILITY.md; open item S11). The golden fixtures and the published
laboratory records were produced on macOS arm64. Tests of those artefacts are strict where this environment reproduces the reference hierarchy and otherwise check what holds on every platform and report the difference as a warning.
"""

from __future__ import annotations

import functools
import platform

import numpy as np

from xzr._compat import hierarchy_cache as reference_cache
from xzr.lod import hierarchy as H
from xzr.scenario.io import load_sample
from xzr.service.session import Session

REFERENCE_PLATFORM = ("Darwin", "arm64")


def on_reference_platform() -> bool:
    return (platform.system(), platform.machine()) == REFERENCE_PLATFORM


@functools.lru_cache(maxsize=1)
def hierarchy_reproduces_reference() -> bool:
    """True when the hierarchy computed here for the golden fixture's graph equals the exported reference."""
    s = Session(load_sample("demo-3k"))
    st = s.engine.state
    m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n)
    ref = reference_cache.load(H.adjacency_key(a))
    return ref is not None and bool(np.array_equal(np.asarray(ref[0]), s.h.path))
