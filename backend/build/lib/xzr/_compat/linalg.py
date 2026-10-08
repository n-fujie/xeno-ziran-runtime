"""``scipy.sparse.linalg.eigsh(…, k=2, which="LA")`` for the hierarchy's Fiedler vector, by a dense symmetric
eigensolve (numpy LAPACK). ARPACK stops at tol=1e-4, so components can differ at that level; the hierarchy only uses
the vector to order and split configurations, and test_compat.py checks that the resulting hierarchy is identical for
every bundled scenario."""

from __future__ import annotations

import numpy as np


class ArpackNoConvergence(RuntimeError):
    def __init__(self, msg: str = "", eigenvalues=None, eigenvectors=None):
        super().__init__(msg)
        self.eigenvalues = eigenvalues
        self.eigenvectors = eigenvectors if eigenvectors is not None else np.zeros((0, 0))


def eigsh(a, k: int = 2, which: str = "LA", tol: float = 0, v0=None, maxiter=None):
    if which != "LA":
        raise NotImplementedError(which)
    m = a.toarray() if hasattr(a, "toarray") else np.asarray(a)
    vals, vecs = np.linalg.eigh(m)
    return vals[-k:], vecs[:, -k:]
