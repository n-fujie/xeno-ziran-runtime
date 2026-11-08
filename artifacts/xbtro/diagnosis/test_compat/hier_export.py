import sys, numpy as np, scipy.sparse as sp
sys.dont_write_bytecode = True
sys.path.insert(0, '/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend')
from xzr.lod import hierarchy as H
from xzr._compat import hierarchy_cache as hc
from xzr.scenario.build import build_world
from xzr.scenario.io import load_sample
out = {}
for name in ["small-600", "reason-lab", "demo-3k"]:
    world = build_world(load_sample(name)); st = world.state; m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n)
    ref, _ = hc.load(H.adjacency_key(a)); cur = H._build_hierarchy(a).path
    d0 = next(d for d in range(1, H.DEPTH+1) if ((ref >> (H.DEPTH-d)) != (cur >> (H.DEPTH-d))).any())
    sh = H.DEPTH - (d0 - 1)
    g = np.unique((ref >> sh)[(ref >> (H.DEPTH-d0)) != (cur >> (H.DEPTH-d0))])[0]
    idx = np.flatnonzero((ref >> sh) == g); sub = a[idx][:, idx]; mm = sub.shape[0]
    deg = np.asarray(sub.sum(1)).ravel() + 1.0; dinv = 1/np.sqrt(deg)
    norm = (sp.diags(dinv) @ (sub + sp.identity(mm)) @ sp.diags(dinv)).toarray()
    out[f"{name}__norm"] = norm; out[f"{name}__dinv"] = dinv
    out[f"{name}__refbit"] = ((ref[idx] >> (H.DEPTH-d0)) & 1).astype(int)
np.savez('/private/tmp/claude-501/-Users-user-Desktop-BIM/c8087b50-1670-488b-afed-5830b085b01e/scratchpad/subgraphs.npz', **out)
print("exported", [k for k in out if k.endswith("norm")])
