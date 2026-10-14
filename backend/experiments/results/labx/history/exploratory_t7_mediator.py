import collections, json, numpy as np
from xzr.lab.record import LabRun
from xzr.lab import labexp as L
from xzr.hpo.experiments import run_pool
def job(args):
    cond, i = args
    gen, seed = L.RANGES["dev"][0] + i, L.RANGES["dev"][1] + i
    r = LabRun(L.config(L.M7[cond], gen, seed)); 
    while not r.done: r.step()
    sci = r.science
    reasons = collections.Counter(e.get("reason","") .split(":")[0] for e in sci.events if e["type"]=="experiment_failed" and e["system"]=="B")
    # transfer latency (request -> delivery) for B
    req = {}; lat = []
    for e in sci.events:
        if e["system"] != "B" if "system" in e else True: continue
        if e["type"]=="experiment_selected": req[(e["src"],e["dst"])] = e["t"]
        if e["type"]=="material_delivered": lat.append(e["t"] - req.get((e["src"],e["dst"]), e["t"]))
    src = collections.Counter(e["src"] for e in sci.events if e["type"]=="experiment_selected" and e["system"]=="B")
    return {"cond": cond, "i": i, "B": sci.summary()["B"]["completed"], "reasons": dict(reasons), "lat": float(np.mean(lat)) if lat else None, "src": dict(src)}
if __name__ == "__main__":
    res = run_pool(job, [(c, i) for c in ("noComm", "noComm_noA") for i in range(8)], 7)
    for c in ("noComm", "noComm_noA"):
        rows = [r for r in res if r["cond"] == c]
        rs = collections.Counter(); srcs = collections.Counter()
        for r in rows: rs.update(r["reasons"]); srcs.update(r["src"])
        print(c, "B completed mean", np.mean([r["B"] for r in rows]), "latency", np.nanmean([r["lat"] for r in rows if r["lat"] is not None]), "fail reasons", dict(rs), "B sources", dict(srcs.most_common(5)))
