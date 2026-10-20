import sys, numpy as np
sys.path.insert(0, '/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend')
from xzr.lod import hierarchy as H
from xzr._compat import hierarchy_cache as hc
from xzr.scenario.build import build_world
from xzr.scenario.io import load_sample
for name in ["small-600", "reason-lab", "demo-3k"]:
    world = build_world(load_sample(name)); st = world.state; m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n)
    ref, _ = hc.load(H.adjacency_key(a)); cur = H._build_hierarchy(a).path
    row = []
    for d in range(1, H.DEPTH+1):
        sh = H.DEPTH - d
        row.append(int(((ref >> sh) != (cur >> sh)).sum()))
    # sizes of the sub-problems at the first depth where they differ
    d0 = next((i+1 for i, x in enumerate(row) if x), None)
    sizes = None
    if d0:
        sh = H.DEPTH - (d0-1)
        pref_ref = ref >> sh
        bad = np.unique(pref_ref[(ref >> (H.DEPTH-d0)) != (cur >> (H.DEPTH-d0))])
        sizes = [int((pref_ref == b).sum()) for b in bad]
    print(name, "nodes differing in the first d bits, d=1..9:", row, "| first differing depth", d0, "| size of the sub-graph(s) split there:", sizes)
