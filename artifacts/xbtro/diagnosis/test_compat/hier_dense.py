import sys, numpy as np, scipy, scipy.linalg as sl, scipy.sparse as sp
sys.dont_write_bytecode = True
sys.path.insert(0, '/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend')
from xzr.lod import hierarchy as H
from xzr._compat import hierarchy_cache as hc
from xzr.scenario.build import build_world
from xzr.scenario.io import load_sample
print("numpy", np.__version__, "scipy", scipy.__version__)
rng = np.random.default_rng(0)
for name in ["small-600", "reason-lab", "demo-3k"]:
    world = build_world(load_sample(name)); st = world.state; m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n)
    ref, _ = hc.load(H.adjacency_key(a)); cur = H._build_hierarchy(a).path
    d0 = next(d for d in range(1, H.DEPTH+1) if ((ref >> (H.DEPTH-d)) != (cur >> (H.DEPTH-d))).any())
    sh = H.DEPTH - (d0 - 1)
    groups = np.unique((ref >> sh)[(ref >> (H.DEPTH-d0)) != (cur >> (H.DEPTH-d0))])
    print(f"\n== {name}: first differing depth {d0}")
    for g in groups:
        idx = np.flatnonzero((ref >> sh) == g)
        sub = a[idx][:, idx]
        mm = sub.shape[0]
        deg = np.asarray(sub.sum(1)).ravel() + 1.0; dinv = 1/np.sqrt(deg)
        norm = (sp.diags(dinv) @ (sub + sp.identity(mm)) @ sp.diags(dinv)).toarray()
        ev = np.linalg.eigvalsh(norm)[::-1]
        refbit = ((ref[idx] >> (H.DEPTH-d0)) & 1).astype(int)
        def split(vec):
            v = vec * dinv
            if np.dot(v, np.arange(mm) - mm/2) < 0: v = -v
            o = np.argsort(v, kind="stable"); lab = np.zeros(mm, int); lab[o[mm//2:]] = 1
            return lab
        def mism(lab): return int(min((lab != refbit).sum(), (lab == refbit).sum()))  # label-flip invariant
        print(f" sub-graph {mm} nodes; top eigenvalues {ev[:4].round(8)}; gap l2-l3 = {ev[1]-ev[2]:.2e}, l1-l2 = {ev[0]-ev[1]:.2e}")
        res = {}
        res["numpy eigh (current)"] = split(np.linalg.eigh(norm)[1][:, -2])
        for drv in ("ev", "evd", "evr", "evx"):
            res[f"scipy eigh driver={drv}"] = split(sl.eigh(norm, driver=drv)[1][:, -2])
        # exactness reference: extended-precision-free check = eigenvector residual of each
        perm = rng.permutation(mm); inv = np.argsort(perm)
        vp = np.linalg.eigh(norm[np.ix_(perm, perm)])[1][:, -2][inv]
        res["numpy eigh, nodes permuted"] = split(vp)
        res["numpy eigh, float32 input"] = split(np.linalg.eigh(norm.astype(np.float32))[1][:, -2].astype(float))
        for k, lab in res.items(): print(f"   {k:34} nodes disagreeing with the stored reference split: {mism(lab)}")
        # do the variants agree with each other?
        labs = list(res.values())
        print("   variants disagree with 'numpy eigh (current)' by:", [int(min((l != labs[0]).sum(), (l == labs[0]).sum())) for l in labs[1:]])
