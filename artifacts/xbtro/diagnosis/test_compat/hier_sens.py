import sys, numpy as np
sys.path.insert(0, '/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend')
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh
from xzr.lod import hierarchy as H
from xzr._compat import hierarchy_cache as hc
from xzr.scenario.build import build_world
from xzr.scenario.io import load_sample
for name in ["demo-3k", "reason-lab"]:
    world = build_world(load_sample(name)); st = world.state; m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n); n = a.shape[0]
    ref_path, _ = hc.load(H.adjacency_key(a))
    ref_top = (ref_path >> (H.DEPTH - 1)).astype(int)        # reference first split
    deg = np.asarray(a.sum(1)).ravel() + 1.0; dinv = 1/np.sqrt(deg)
    norm = sp.diags(dinv) @ (a + sp.identity(n)) @ sp.diags(dinv)
    def split(v):
        v = v*dinv
        if np.dot(v, np.arange(n)-n/2) < 0: v = -v
        o = np.argsort(v, kind="stable"); lab = np.zeros(n, int); lab[o[n//2:]] = 1; return lab
    def run(v0, tol): return split(eigsh(norm, k=2, which="LA", tol=tol, v0=v0, maxiter=3000)[1][:, 0])
    base_v0 = np.linspace(1.0, 2.0, n)
    now = run(base_v0, 1e-4); tight = run(base_v0, 1e-12)
    rng = np.random.default_rng(0)
    print(name, "n", n)
    print("  reference first split vs now(1e-4):", int((ref_top != now).sum()), " vs exact(1e-12):", int((ref_top != tight).sum()))
    for eps in (1e-14, 1e-10, 1e-6):
        diffs = [int((run(base_v0*(1+eps*rng.standard_normal(n)), 1e-4) != now).sum()) for _ in range(5)]
        print(f"  start-vector perturbation rel {eps:g}: first-split changes vs unperturbed (5 draws): {diffs}")
    print("  exact(1e-12) under perturbation 1e-10:", [int((run(base_v0*(1+1e-10*rng.standard_normal(n)), 1e-12) != tight).sum()) for _ in range(3)])
