"""Export the desktop's reference hierarchies (scipy ARPACK) for runtimes without scipy (the iOS app).

    python backend/scripts/export_hierarchy_cache.py [max_nodes]     # default 3000, the mobile limit

For every bundled scenario up to ``max_nodes`` configurations, the world's hierarchy is built here, natively, and
its leaf paths and order are written to xzr/_compat/hierarchies/<adjacency key>.npz (see _compat/hierarchy_cache.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xzr._compat import FORCE, hierarchy_cache  # noqa: E402
from xzr.lod.hierarchy import _COMPAT_PATH, adjacency_key, symmetric_adjacency  # noqa: E402
from xzr.scenario.build import build_world  # noqa: E402
from xzr.scenario.io import list_samples, load_sample  # noqa: E402


def main() -> None:
    if FORCE or _COMPAT_PATH:
        raise SystemExit("run with scipy available (the reference is the desktop's ARPACK hierarchy)")
    max_nodes = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    for s in list_samples():
        if s["configurations"] > max_nodes:
            print(f"skip {s['id']} ({s['configurations']} configurations > {max_nodes})")
            continue
        world = build_world(load_sample(s["id"]))
        st = world.state
        m = st.alive
        key = adjacency_key(symmetric_adjacency(st.src[m], st.dst[m], st.n))
        f = hierarchy_cache.save(key, world.hierarchy.path, world.hierarchy.order)
        print(f"{s['id']}: {key[:16]}… → {f.name} ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
