import sys, numpy as np
sys.path.insert(0, '/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend')
import scipy, numpy
from scipy.sparse.linalg import eigsh
from xzr.lod import hierarchy as H
from xzr._compat import hierarchy_cache as hc
from xzr.scenario.build import build_world
from xzr.scenario.io import list_samples, load_sample
print("numpy", numpy.__version__, "scipy", scipy.__version__, "compat", H._COMPAT_PATH)
for s in list_samples():
    if s["configurations"] > 3000: continue
    world = build_world(load_sample(s["id"]))
    st = world.state; m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n)
    key = H.adjacency_key(a)
    ref = hc.load(key)
    cur = H._build_hierarchy(a)
    # first split only: current ARPACK(1e-4) vs tight tol vs dense
    f = H._fiedler(a)
    n = a.shape[0]
    deg = np.asarray(a.sum(1)).ravel() + 1.0; dinv = 1/np.sqrt(deg)
    import scipy.sparse as sp
    norm = sp.diags(dinv) @ (a + sp.identity(n)) @ sp.diags(dinv)
    def split(v):
        v = v*dinv
        if np.dot(v, np.arange(n)-n/2) < 0: v = -v
        o = np.argsort(v, kind="stable"); lab = np.zeros(n, int); lab[o[n//2:]] = 1; return lab
    v0 = np.linspace(1.0, 2.0, n)
    tight = split(eigsh(norm, k=2, which="LA", tol=1e-12, v0=v0, maxiter=20000)[1][:, 0])
    dense = split(np.linalg.eigh(norm.toarray())[1][:, -2])
    now = split(eigsh(norm, k=2, which="LA", tol=1e-4, v0=v0, maxiter=3000)[1][:, 0])
    w, _ = eigsh(norm, k=3, which="LA", tol=1e-12, v0=v0, maxiter=20000)
    print(f"{s['id']:>12} n={n} ref={'yes' if ref else 'NO '} "
          f"path!=ref: {int((cur.path != ref[0]).sum()) if ref else '-'}  "
          f"split diff now-vs-tight {int((now!=tight).sum())}, now-vs-dense {int((now!=dense).sum())}, tight-vs-dense {int((tight!=dense).sum())}; "
          f"top eigenvalues {np.sort(w)[::-1].round(8)}")
