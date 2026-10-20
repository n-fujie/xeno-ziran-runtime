"""For the two sub-graphs where the top eigenvalue of the normalised adjacency is repeated (disconnected induced sub-graph),
enumerate every split that `_fiedler` could return when the 2-D eigenspace is parametrised by an angle, and test whether the
stored reference split is one of them.

    cd backend && ../.venv/bin/python ../artifacts/xbtro/diagnosis/test_compat/hier_eigenspace.py   (needs hier_export.py to have written subgraphs.npz)

Reads:  <scratch>/subgraphs.npz  (written by hier_export.py).  Writes nothing.
"""
import os, sys, numpy as np
sys.dont_write_bytecode = True
z = np.load(os.environ.get("ARDS_SUBGRAPHS", "/private/tmp/claude-501/-Users-user-Desktop-BIM/c8087b50-1670-488b-afed-5830b085b01e/scratchpad/subgraphs.npz"))
for name in ["reason-lab", "demo-3k"]:
    norm, dinv, refbit = z[f"{name}__norm"], z[f"{name}__dinv"], z[f"{name}__refbit"]; mm = len(dinv)
    w, V = np.linalg.eigh(norm)
    top = np.flatnonzero(w > 1 - 1e-9)
    print(f"\n{name}: {mm} nodes; eigenvalues within 1e-9 of 1: {len(top)} (= number of connected components)")
    U = V[:, top]
    # connected components of the support graph
    import scipy.sparse as sp, scipy.sparse.csgraph as cg
    ncomp, lab = cg.connected_components(sp.csr_matrix(norm > 1e-12), directed=False)
    sizes = np.bincount(lab)
    print(f"  connected components of the sub-graph: {ncomp}, sizes {sizes.tolist()}")
    def split(v):
        v = v * dinv
        if np.dot(v, np.arange(mm) - mm / 2) < 0: v = -v
        o = np.argsort(v, kind="stable"); l = np.zeros(mm, int); l[o[mm // 2:]] = 1; return l
    mism = lambda l: int(min((l != refbit).sum(), (l == refbit).sum()))
    results = {}
    for deg in np.arange(0, 180, 0.25):
        t = np.deg2rad(deg)
        v = np.cos(t) * U[:, 0] + np.sin(t) * U[:, 1]
        l = split(v)
        key = l.tobytes()
        results.setdefault(key, [deg, mism(l)])
    print(f"  distinct splits over the eigenspace angle theta in [0, 180): {len(results)}")
    for i, (k, (deg, mm_)) in enumerate(sorted(results.items(), key=lambda kv: kv[1][0])):
        print(f"    split #{i + 1}: first reached at theta = {deg:6.2f} deg; nodes disagreeing with the stored reference: {mm_}")
    best = min(v[1] for v in results.values())
    # --- where does the arbitrariness come from? Mathematically v*dinv is CONSTANT on each component (exact tie of 362 / 185 nodes).
    t = np.deg2rad(37.0); v = (np.cos(t) * U[:, 0] + np.sin(t) * U[:, 1]) * dinv
    spread = [float(np.ptp(v[lab == c]) / max(abs(v[lab == c]).max(), 1e-300)) for c in range(ncomp)]
    print(f"  relative spread of v*dinv INSIDE each component (mathematically 0): {['%.1e' % x for x in spread]}  -> ordering inside the tie is decided by rounding noise")
    ideal = {}
    for deg in np.arange(0, 180, 0.25):
        t = np.deg2rad(deg); c1, c2 = np.cos(t), np.sin(t)
        val = np.zeros(mm)
        for c in range(ncomp):
            idx = lab == c
            val[idx] = (c1 * (U[idx, 0] * dinv[idx]) + c2 * (U[idx, 1] * dinv[idx])).mean()  # the exact constant for this component
        vv = val.copy()  # already v*dinv: exact constants, no further arithmetic
        if np.dot(vv, np.arange(mm) - mm / 2) < 0: vv = -vv
        o = np.argsort(vv, kind="stable"); l = np.zeros(mm, int); l[o[mm // 2:]] = 1
        ideal.setdefault(l.tobytes(), [deg, mism(l)])
    print(f"  with the EXACT (tie-preserving) vector instead of the rounded one: distinct splits = {len(ideal)}; best disagreement with the stored reference = {min(v[1] for v in ideal.values())} nodes (ties then broken by node index, a convention not by the data)")
    print(f"  => the stored reference {'IS' if best == 0 else 'is NOT'} one of the splits the algorithm can return for this eigenspace (best disagreement {best} nodes)")
