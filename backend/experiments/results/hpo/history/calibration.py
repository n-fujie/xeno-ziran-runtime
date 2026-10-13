import numpy as np, sys
from xzr.hpo.world import build_world
from xzr.hpo.field import Field, ALL_OFF
from xzr.hpo import operations as O
vals = {}
orig = Field._sample
def hook(self, op, t, fair):
    orig(self, op, t, fair)
    for k,(out,reason,v) in op.mem.get("_last_ign",{}).items():
        if v is not None and reason not in ("picture initialised",): vals.setdefault(k,[]).append(v)
Field._sample = hook
# disable acting to see the unperturbed distribution: huge thresholds
big = {k: {O.ESSENTIAL and list(O.DEFAULT_IGN[k])[0]: 1e9} for k in O.DEFAULT_IGN}
big["picturing"]={"tolerance":1e9}
for regime in sys.argv[1:] or ["intermittent"]:
    vals.clear()
    for g in range(8):
        w = build_world(800, g, 1000+g, regime=regime)
        for _ in range(40): w.step()
        f = Field(w, {"interaction": ALL_OFF, "ign": big, "feedback": False}, 1000+g)
        f.run(240)
    print(regime)
    for k,v in vals.items():
        v=np.array(v); print(f"  {k:13s} n={len(v):4d} q10 {np.quantile(v,.1):.4f} q50 {np.quantile(v,.5):.4f} q75 {np.quantile(v,.75):.4f} q90 {np.quantile(v,.9):.4f} max {v.max():.4f}")
