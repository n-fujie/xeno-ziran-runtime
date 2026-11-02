"""The subset of ``scipy.sparse`` used by ``shapes/metrics.py`` and ``lod/hierarchy.py``: CSR matrices built from
COO triplets (duplicates summed), transpose, sum, matrix-vector product, addition, block stacking, ``diags``,
``identity`` and ``toarray``."""

from __future__ import annotations

import numpy as np


class csr_matrix:  # noqa: N801 — mirrors scipy's name
    def __init__(self, arg, shape: tuple[int, int] | None = None):
        if isinstance(arg, tuple) and len(arg) == 2 and isinstance(arg[0], int | np.integer):
            shape, data, row, col = (int(arg[0]), int(arg[1])), np.zeros(0), np.zeros(0, np.intp), np.zeros(0, np.intp)
        else:
            data, (row, col) = arg
            data = np.asarray(data, dtype=np.float64)
            row = np.asarray(row, dtype=np.intp)
            col = np.asarray(col, dtype=np.intp)
        assert shape is not None
        self.shape = (int(shape[0]), int(shape[1]))
        order = np.lexsort((col, row))
        row, col, data = row[order], col[order], data[order]
        if len(row):  # sum duplicates, as scipy's csr construction does
            key = row * self.shape[1] + col
            uniq, start = np.unique(key, return_index=True)
            data = np.add.reduceat(data, start)
            row, col = uniq // self.shape[1], uniq % self.shape[1]
        self.indices = col.astype(np.intp)
        self.data = data
        self.indptr = np.concatenate([[0], np.cumsum(np.bincount(row, minlength=self.shape[0]))]).astype(np.intp)

    def _coo(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        row = np.repeat(np.arange(self.shape[0]), np.diff(self.indptr))
        return row, self.indices, self.data

    def __getitem__(self, key) -> csr_matrix:
        """Row selection ``a[idx]`` or column selection ``a[:, idx]``, in the order of ``idx`` (as scipy)."""
        r, c, d = self._coo()
        if isinstance(key, tuple):
            rows, cols = key
            if not (isinstance(rows, slice) and rows == slice(None)):
                return self[rows][:, cols]
            idx = np.asarray(cols, dtype=np.intp)
            pos = np.full(self.shape[1], -1, dtype=np.intp)
            pos[idx] = np.arange(len(idx))
            keep = pos[c] >= 0
            return csr_matrix((d[keep], (r[keep], pos[c[keep]])), shape=(self.shape[0], len(idx)))
        idx = np.asarray(key, dtype=np.intp)
        pos = np.full(self.shape[0], -1, dtype=np.intp)
        pos[idx] = np.arange(len(idx))
        keep = pos[r] >= 0
        return csr_matrix((d[keep], (pos[r[keep]], c[keep])), shape=(len(idx), self.shape[1]))

    @property
    def T(self) -> csr_matrix:  # noqa: N802
        r, c, d = self._coo()
        return csr_matrix((d, (c, r)), shape=(self.shape[1], self.shape[0]))

    def tocsr(self) -> csr_matrix:
        return self

    def toarray(self) -> np.ndarray:
        out = np.zeros(self.shape)
        r, c, d = self._coo()
        np.add.at(out, (r, c), d)
        return out

    def sum(self, axis: int | None = None):
        r, c, d = self._coo()
        if axis == 1:
            return np.bincount(r, weights=d, minlength=self.shape[0]).reshape(-1, 1)
        if axis == 0:
            return np.bincount(c, weights=d, minlength=self.shape[1]).reshape(1, -1)
        return float(d.sum())

    def __matmul__(self, other):
        if isinstance(other, csr_matrix):
            r1, c1, d1 = self._coo()
            r2, c2, d2 = other._coo()
            if np.array_equal(r1, c1) and len(r1) == self.shape[0]:  # diagonal @ M: scale M's rows
                return csr_matrix((d2 * d1[r2], (r2, c2)), shape=(self.shape[0], other.shape[1]))
            if np.array_equal(r2, c2) and len(r2) == other.shape[0]:  # M @ diagonal: scale M's columns
                return csr_matrix((d1 * d2[c1], (r1, c1)), shape=(self.shape[0], other.shape[1]))
            return csr_matrix(_dense_to_coo(self.toarray() @ other.toarray()), shape=(self.shape[0], other.shape[1]))
        v = np.asarray(other)
        r, c, d = self._coo()
        if v.ndim == 1:
            return np.bincount(r, weights=d * v[c], minlength=self.shape[0])
        return np.stack([np.bincount(r, weights=d * v[c, j], minlength=self.shape[0]) for j in range(v.shape[1])], 1)

    def __add__(self, other: csr_matrix) -> csr_matrix:
        r1, c1, d1 = self._coo()
        r2, c2, d2 = other._coo()
        return csr_matrix((np.concatenate([d1, d2]), (np.concatenate([r1, r2]), np.concatenate([c1, c2]))),
                          shape=self.shape)


def _dense_to_coo(a: np.ndarray):
    r, c = np.nonzero(a)
    return a[r, c], (r, c)


def vstack(blocks: list[csr_matrix]) -> csr_matrix:
    rows, cols, data, off = [], [], [], 0
    for b in blocks:
        r, c, d = b._coo()
        rows.append(r + off); cols.append(c); data.append(d)  # noqa: E702
        off += b.shape[0]
    return csr_matrix((np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))), shape=(off, blocks[0].shape[1]))


def hstack(blocks: list[csr_matrix]) -> csr_matrix:
    rows, cols, data, off = [], [], [], 0
    for b in blocks:
        r, c, d = b._coo()
        rows.append(r); cols.append(c + off); data.append(d)  # noqa: E702
        off += b.shape[1]
    return csr_matrix((np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))), shape=(blocks[0].shape[0], off))


def diags(v) -> csr_matrix:
    v = np.asarray(v, dtype=np.float64)
    i = np.arange(len(v))
    return csr_matrix((v, (i, i)), shape=(len(v), len(v)))


def identity(m: int) -> csr_matrix:
    return diags(np.ones(m))
