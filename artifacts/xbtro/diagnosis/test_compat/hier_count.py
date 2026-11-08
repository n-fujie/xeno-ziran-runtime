import sys, numpy as np, scipy.sparse as sp
sys.dont_write_bytecode = True
sys.path.insert(0, '/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend')
from xzr.lod import hierarchy as H
from xzr._compat import hierarchy_cache as hc
from xzr.scenario.build import build_world
from xzr.scenario.io import load_sample
orig = H._fiedler
log = []
def probe(a):
    m = a.shape[0]
    deg = np.asarray(a.sum(1)).ravel() + 1.0; dinv = 1/np.sqrt(deg)
    norm = sp.diags(dinv) @ (a + sp.identity(m)) @ sp.diags(dinv)
    if m <= 400:
        ev = np.linalg.eigvalsh(norm.toarray())[::-1]
        ncomp = sp.csgraph.connected_components(a, directed=False)[0]
        log.append((m, "dense", float(ev[0]-ev[1]), int(ncomp)))
    else:
        log.append((m, "arpack", None, int(sp.csgraph.connected_components(a, directed=False)[0])))
    return orig(a)
H._fiedler = probe
for name in ["small-600", "reason-lab", "demo-3k"]:
    log.clear()
    world = build_world(load_sample(name)); st = world.state; m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n)
    H._build_hierarchy(a)
    dense = [x for x in log if x[1] == "dense" and x[0] > 2]
    degenerate = [x for x in dense if x[3] > 1]
    arp = [x for x in log if x[1] == "arpack"]
    print(f"{name}: {len(log)} Fiedler solves = {len(arp)} ARPACK (>400 nodes, disconnected: {sum(1 for x in arp if x[3] > 1)}) + {len(dense)} dense (<=400 nodes); "
          f"dense solves on a DISCONNECTED sub-graph (eigenvalue 1 repeated): {len(degenerate)}; "
          f"min (l1-l2) over those: {min((x[2] for x in degenerate), default=None)}; sizes: {sorted({x[0] for x in degenerate})[:8]}")
    conn = [x for x in dense if x[3] == 1]
    print(f"    dense solves on CONNECTED sub-graphs: {len(conn)}; smallest l1-l2 gap there: {min((x[2] for x in conn), default=None):.2e}")
