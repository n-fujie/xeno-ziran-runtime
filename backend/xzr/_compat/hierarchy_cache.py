"""Reference hierarchies computed on the desktop (scipy ARPACK), for runtimes without scipy.

The hierarchy depends only on the initial world graph, and it resolves address-based sets (drivers, frozen sets,
boundaries, practice targets), so it must be identical to the desktop's for the dynamics to match. ARPACK stops at
tol=1e-4 and a dense eigensolver does not reproduce its splits, so the desktop exports each bundled scenario's leaf
paths and order (``backend/scripts/export_hierarchy_cache.py``), keyed by the adjacency's identity. A runtime without
scipy uses the cached hierarchy when the key matches and only otherwise computes its own (and says so).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

DIR = Path(__file__).resolve().parent / "hierarchies"


def load(key: str) -> tuple[np.ndarray, np.ndarray] | None:
    f = DIR / f"{key}.npz"
    if not f.is_file():
        return None
    with np.load(f, allow_pickle=False) as z:
        return z["path"], z["order"]


def save(key: str, path: np.ndarray, order: np.ndarray) -> Path:
    DIR.mkdir(exist_ok=True)
    f = DIR / f"{key}.npz"
    np.savez_compressed(f, path=np.asarray(path, dtype=np.int32), order=np.asarray(order, dtype=np.int32))
    return f
