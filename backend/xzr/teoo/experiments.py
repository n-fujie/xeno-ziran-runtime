"""Phase 4 experiments A-E on the SYNTHETIC world of ``world.py``. Each ``run_*`` function runs one independent unit (a world, identified by its seed) and returns plain data; ``phase4_run.py`` pre-registers, runs
all units, analyses and saves. Nothing here is a statement about a real body: the truth of every unit is its generator, the results are results about this synthetic world and about the implementation, and say so.

A  observation resolution   what an observation condition identifies, loses and cannot decide (truth known by construction)
B  body reconfiguration     cutting, rejoining and rewiring couplings: recoverable structure and which relations become invisible
C  open revision            fixed / pre-specified / random / outcome-adaptive revision of the sensor, against a cost-matched static condition
D  disconnection            connected / disconnected / reconnected / reconfigured: observed dependency against the simulated operability
E  reconstruction limits    what can be rebuilt from degraded observations, with calibrated uncertainty and refusal
"""

from __future__ import annotations

import itertools
import zlib
from typing import Any

import numpy as np

from . import observation as OB
from . import revision as RV
from . import world as W

T20 = np.arange(0, 20.0, W.DT)
TYPES = ("amplitude", "frequency", "burst", "coupling")
GRID = {"ts": (0.02, 0.2, 1.0), "r": (0.5, 4.0), "lim": (0.05, 0.8), "win": (20.0, 4.0)}
PEN = 0.6


def sens(ts: float, r: float, lim: float, win: float, pen: float = PEN) -> dict:
    return W.sensor_of(r, ts, win, lim, pen)


def cfg_of(sensor: dict, at: float = 0.0) -> dict:
    return OB.new_configuration([sensor], at=at, body_version=1)


def _valid(a: dict) -> bool:
    return a["status"] == "MEASURED_VALID"


# ================================================================================================ A
def _modify(w: W.World, kind: str, c: int, partner: int | None) -> W.World:
    w1 = w.copy()
    if kind == "amplitude":
        w1.comps[c].amp *= 1.6
    elif kind == "frequency":
        w1.comps[c].f *= 1.25
    elif kind == "burst":
        w1.comps[c].burst_rate, w1.comps[c].burst_amp = 0.3, 2.0 * w.comps[c].amp
    elif kind == "coupling":
        a, b = sorted((c, partner if partner is not None else (c + 1) % w.n()))
        w1.edges[(a, b)] = 0.8
    return w1


def _target_spec(w: W.World, kind: str, c: int) -> dict:
    s = W.spec_of(w, c)
    if kind == "burst":  # the declared feature is the burst: its period is a third of the carrier's, its amplitude the burst amplitude
        return {**s, "phenomenon_period_s": s["phenomenon_period_s"] / 3.0, "amplitude": 2.0 * w.comps[c].amp}
    if kind == "frequency":
        return {**s, "phenomenon_period_s": s["phenomenon_period_s"] / 1.25}
    return s


def run_a(seed: int, trials: int = 8, cases_per_type: int = 3) -> dict:
    """One world: ``cases_per_type`` true-difference cases and as many null cases per feature type, observed under every configuration of GRID."""
    rng = np.random.default_rng(seed)
    w = W.make_world(seed)
    cases: list[dict[str, Any]] = []
    for kind in TYPES:
        for truth in (True, False):
            for _ in range(cases_per_type):
                c = int(rng.integers(0, w.n()))
                partner = None
                if kind == "coupling":  # a pair that has no coupling in the world
                    free = [(a, b) for a in range(w.n()) for b in range(a + 1, w.n()) if (a, b) not in w.edges]
                    c, partner = free[int(rng.integers(0, len(free)))]
                w1 = _modify(w, kind, c, partner) if truth else w.copy()
                lat0 = [W.latent(w, T20, rng) for _ in range(trials)]
                lat1 = [W.latent(w1, T20, rng) for _ in range(trials)]
                cases.append({"kind": kind, "truth": truth, "c": c, "partner": partner, "w1": w1, "lat0": lat0, "lat1": lat1})
    rows = []
    for ts, r, lim, win in itertools.product(GRID["ts"], GRID["r"], GRID["lim"], GRID["win"]):
        sn = sens(ts, r, lim, win)
        cfg = cfg_of(sn)
        for ci, cs in enumerate(cases):
            comps = [cs["c"]] if cs["kind"] != "coupling" else [cs["c"], cs["partner"]]
            specs = [_target_spec(w, cs["kind"], i) for i in comps]
            sts = [OB.assess_target(cfg, sp, 0.0) for sp in specs]
            valid = all(_valid(a) for a in sts)
            orng = np.random.default_rng((seed, ci, int(ts * 1000), int(r * 10), int(lim * 100), int(win)))
            tr0 = [W.observe(w, x, T20, sn, orng, comps) for x in cs["lat0"]]
            tr1 = [W.observe(cs["w1"], x, T20, sn, orng, comps) for x in cs["lat1"]]
            if cs["kind"] == "coupling":
                a0, a1 = [(t[comps[0]], t[comps[1]]) for t in tr0], [(t[comps[0]], t[comps[1]]) for t in tr1]
            else:
                a0, a1 = [t[comps[0]] for t in tr0], [t[comps[0]] for t in tr1]
            d = W.detect(cs["kind"], a0, a1, orng)
            rows.append({"ts": ts, "r": r, "lim": lim, "win": win, "kind": cs["kind"], "truth": cs["truth"], "status_valid": valid, "statuses": [a["status"] for a in sts],
                         "result": d["result"], "p": d["p"], "amp": float(min(sp["amplitude"] for sp in specs)), "scale_ok": all(sp["scale"] >= r for sp in specs)})
    return {"seed": seed, "rows": rows}


# ================================================================================================ B and D
def _cuts(w: W.World, rng: np.random.Generator) -> set[tuple[int, int]]:
    """Cut every coupling that joins a set of three components to the rest (the set is disconnected)."""
    s = set(int(v) for v in rng.choice(w.n(), 3, replace=False))
    return {e for e in w.edges if (e[0] in s) != (e[1] in s)}


def _reconfigure(w: W.World, cut: set[tuple[int, int]], rng: np.random.Generator) -> dict[tuple[int, int], float]:
    """The cut couplings are replaced by the same number of couplings between other pairs (kept acyclic)."""
    edges = {e: k for e, k in w.edges.items() if e not in cut}
    pairs = [(a, b) for a in range(w.n()) for b in range(a + 1, w.n()) if (a, b) not in w.edges]
    rng.shuffle(pairs)  # type: ignore[arg-type]
    for e, p in zip(sorted(cut), pairs, strict=False):
        edges[p] = w.edges[e]
    return edges


def components(n: int, edges: dict) -> int:
    p = list(range(n))

    def f(x: int) -> int:
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x
    for a, b in edges:
        p[f(a)] = f(b)
    return len({f(i) for i in range(n)})


def _edge_stat(obs: list[dict[int, Any]], a: int, b: int) -> float | None:
    vals = [W.feature("coupling", t[a], t[b]) for t in obs]
    vals = [v for v in vals if v is not None]
    return float(np.mean(vals)) if len(vals) >= 4 else None


def _recover(obs: list[dict[int, Any]], n: int, rng: np.random.Generator, status_ok: list[bool], alpha: float = 0.005, n_null: int = 400) -> dict[str, Any]:
    """Recover the coupling structure from the observed traces: a pair is 'present' when its mean best-lag correlation exceeds the correlations of the same pair after the second trace is paired with another trial's
    (a null with no relation between the pair); the naive reader decides every pair, the status-aware reader leaves a pair undecided when an endpoint's TEOO status is not MEASURED_VALID."""
    present, undecided, stat = set(), set(), {}
    for a in range(n):
        for b in range(a + 1, n):
            s = _edge_stat(obs, a, b)
            if s is None:
                undecided.add((a, b))
                continue
            nulls = []
            for _ in range(n_null // 40):
                perm = rng.permutation(len(obs))
                v = [W.feature("coupling", obs[i][a], obs[perm[i]][b]) for i in range(len(obs))]
                v = [x for x in v if x is not None]
                if len(v) >= 4:
                    nulls.append(float(np.mean(v)))
            p = (sum(x >= s for x in nulls) + 1) / (len(nulls) + 1) if nulls else 1.0
            stat[(a, b)] = s
            if p < alpha * 40:  # the null has n_null/40 draws: the resolution of the p-value is 1/(draws+1); the threshold is the smallest the null can resolve
                present.add((a, b))
    aware_undecided = {(a, b) for a in range(n) for b in range(a + 1, n) if not (status_ok[a] and status_ok[b])}
    return {"naive": present, "aware": {e for e in present if e not in aware_undecided}, "aware_undecided": aware_undecided, "undecided_no_data": undecided}


def _prf(pred: set, truth: set, universe: set | None = None) -> dict[str, float | None]:
    tp, fp, fn = len(pred & truth), len(pred - truth), len(truth - pred)
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p is not None and r is not None and p + r else (0.0 if tp + fp + fn else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def operability(w: W.World, src: int, sink: int, rng: np.random.Generator, trials: int = 6) -> float:
    """The share of the sink's signal variance that comes from the source (the world's own definition of how much the sink operates through the source): 0 when no path joins them."""
    num = den = 0.0
    for _ in range(trials):
        seed = int(rng.integers(0, 2**31))
        full = W.latent(w, T20, np.random.default_rng(seed))[sink]
        only = W.latent(w, T20, np.random.default_rng(seed), only=src)[sink]
        num += float(np.var(only))
        den += float(np.var(full))
    return num / den if den else 0.0


def run_graph(seed: int, trials: int = 8) -> dict:
    """One world under four body configurations (connected, disconnected, reconnected, reconfigured), observed by a fine sensor that sees through every boundary and by a limited sensor."""
    rng = np.random.default_rng(seed)
    w = W.make_world(seed)
    cut = _cuts(w, rng)
    members = {int(v) for e in cut for v in e}
    conds: dict[str, W.World] = {"connected": w, "disconnected": W.World(w.comps, {e: k for e, k in w.edges.items() if e not in cut}, w.lag_s),
                                 "reconnected": w.copy(), "reconfigured": W.World(w.comps, _reconfigure(w, cut, rng), w.lag_s)}
    sensors = {"fine": sens(0.02, 0.5, 0.05, 20.0, pen=0.9), "medium": sens(0.2, 2.0, 0.3, 20.0, pen=0.6), "limited": sens(0.2, 4.0, 0.8, 20.0, pen=0.4)}
    # the pair used for the dependency and operability: a source and a sink joined by a path in the connected world and separated in the disconnected one
    src = min(members) if members else 0
    sink = max((j for (a, j) in cut if a == src), default=None) or max(members or {w.n() - 1})
    out: dict[str, Any] = {"seed": seed, "cut": sorted(cut), "pair": [src, sink], "n": w.n(), "conditions": {}}
    for cname, wc in conds.items():
        truth_edges = {tuple(sorted(e)) for e in wc.edges}
        entry: dict[str, Any] = {"edges": len(wc.edges), "components": components(w.n(), wc.edges), "truth_edges": sorted(truth_edges),
                                 "operability": operability(wc, src, sink, np.random.default_rng((seed, 99))), "sensors": {}}
        lat = [W.latent(wc, T20, np.random.default_rng((seed, zlib.crc32(cname.encode()), k))) for k in range(trials)]
        for sname, sn in sensors.items():
            cfg = cfg_of(sn)
            status_ok = [_valid(OB.assess_target(cfg, W.spec_of(wc, i), 0.0)) for i in range(w.n())]
            orng = np.random.default_rng((seed, zlib.crc32((cname + sname).encode())))
            obs = [W.observe(wc, x, T20, sn, orng) for x in lat]
            rec = _recover(obs, w.n(), orng, status_ok)
            universe = {(a, b) for a in range(w.n()) for b in range(a + 1, w.n())}
            dep = _edge_stat(obs, *sorted((src, sink)))
            entry["sensors"][sname] = {"status_valid_components": int(sum(status_ok)), "naive": _prf(rec["naive"], truth_edges), "aware": _prf(rec["aware"], {e for e in truth_edges if e not in rec["aware_undecided"]}),
                                       "aware_undecided_pairs": len(rec["aware_undecided"]), "recovered": sorted(rec["naive"]), "dependency_observed": dep,
                                       "invisible_true_edges": sorted(e for e in truth_edges if e not in rec["naive"]), "universe": len(universe)}
        out["conditions"][cname] = entry
    return out


# ================================================================================================ C
OPTIONS = ("ts", "r", "lim", "win", "pen")
CAUSE_OPTION = {"TIME_WINDOW_MISMATCH": "ts", "SCALE_MISMATCH": "r", "SIGNAL_BELOW_THRESHOLD": "lim", "BOUNDARY_INVISIBLE": "pen"}
INITIAL = {"ts": 1.0, "r": 4.0, "lim": 0.8, "win": 4.0, "pen": 0.3}
BUDGET = 6.0


def cost(p: dict) -> float:
    """The cost of a sensor: finer resolution, faster sampling, a lower detection limit, a longer window and a deeper penetration all cost more."""
    return 2.0 / p["r"] + 0.2 / p["ts"] + 0.3 / p["lim"] + 0.05 * p["win"] + 2.0 * p["pen"]


def step(p: dict, option: str) -> dict:
    q = dict(p)
    if option == "ts":
        q["ts"] = max(0.02, p["ts"] / 2)
    elif option == "r":
        q["r"] = max(0.5, p["r"] / 2)
    elif option == "lim":
        q["lim"] = max(0.05, p["lim"] / 2)
    elif option == "win":
        q["win"] = min(20.0, p["win"] * 2)
    elif option == "pen":
        q["pen"] = min(0.95, p["pen"] + 0.2)
    return q


def _sensor(p: dict) -> dict:
    return sens(p["ts"], p["r"], p["lim"], p["win"], p["pen"])


def _statuses(w: W.World, p: dict) -> list[dict]:
    cfg = cfg_of(_sensor(p))
    return [OB.assess_target(cfg, W.spec_of(w, i), 0.0) for i in range(w.n())]


def _revise_log(p0: dict, seq: list[str], w: W.World, who: str, rule: str) -> tuple[dict, list[dict]]:
    """Apply the options in sequence to a sensor, as Open Revision events (recorded, with what each gained and lost by the TEOO assessment)."""
    specs = [W.spec_of(w, i) for i in range(w.n())]
    hist = [cfg_of(_sensor(p0))]
    p, log = dict(p0), []
    for opt in seq:
        q = step(p, opt)
        rtype, params = {"ts": ("time_window_change", {"sensor": "s", "sampling_period_s": q["ts"]}), "win": ("time_window_change", {"sensor": "s", "window_s": q["win"]}),
                         "r": ("scale_change", {"sensor": "s", "resolution": q["r"]}), "pen": ("boundary_change", {"sensor": "s", "reach": None, "penetration": q["pen"]}),
                         "lim": ("sensor_change", {"op": "replace", "id": "s", "sensor": _sensor(q)})}[opt]
        hist, ev = RV.revise(hist, specs, rtype, params, reason=f"{rule}: {opt}", at=float(len(log) + 1), initiated_by=who, log=log)
        p = q
    return p, log


def run_c(seed: int, trials: int = 8) -> dict:
    """One world with a true amplitude difference in each component (one at a time); five ways to arrive at a sensor, all within the same revision budget."""
    rng = np.random.default_rng(seed)
    w = W.make_world(seed, n=12)
    c0 = cost(INITIAL)

    def fits(p: dict, extra: float) -> bool:
        return cost(p) + extra <= c0 + BUDGET + 1e-9
    arms: dict[str, dict] = {}
    # fixed
    arms["fixed"] = {"params": dict(INITIAL), "seq": [], "decider": "none", "log": []}
    # pre-specified schedule: the order is fixed in advance, before any status is looked at
    p, seq = dict(INITIAL), []
    for opt in ("ts", "r", "lim", "pen", "win"):
        q = step(p, opt)
        if q != p and fits(q, 0):
            p, seq = q, [*seq, opt]
    arms["prespecified"] = {"params": p, "seq": seq, "decider": "researcher-coded schedule (ts, r, lim, pen, win), fixed before the world was seen"}
    # random order, applied while the budget allows
    p, seq = dict(INITIAL), []
    for opt in rng.permutation(list(OPTIONS)):
        q = step(p, str(opt))
        if q != p and fits(q, 0):
            p, seq = q, [*seq, str(opt)]
    arms["random"] = {"params": p, "seq": seq, "decider": "seeded random order"}
    # outcome-adaptive: repeatedly fix the cause that most declared targets suffer from (TEOO statuses only; no ground truth)
    p, seq = dict(INITIAL), []
    for _ in range(12):
        sts = _statuses(w, p)
        counts: dict[str, int] = {}
        for a in sts:
            for c in a["causes"]:
                if c in CAUSE_OPTION:
                    counts[c] = counts.get(c, 0) + 1
        picked = None
        for cause, _n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            q = step(p, CAUSE_OPTION[cause])
            if q != p and fits(q, 0):
                picked = CAUSE_OPTION[cause]
                break
        if picked is None:
            break
        p, seq = step(p, picked), [*seq, picked]
    arms["adaptive"] = {"params": p, "seq": seq, "decider": "rule: fix the cause shared by most declared targets whose TEOO status is not MEASURED_VALID; evaluation information: the statuses only"}
    # cost-matched static: the best sensor on the grid within the same total cost, chosen by the number of valid statuses (the same information the adaptive rule had), ties by lower cost
    best, bestkey = None, None
    for ts, r, lim, win, pen in itertools.product((0.02, 0.1, 0.2, 0.5, 1.0), (0.5, 1.0, 2.0, 4.0), (0.05, 0.1, 0.2, 0.4, 0.8), (4.0, 8.0, 16.0, 20.0), (0.3, 0.5, 0.7, 0.9)):
        q = {"ts": ts, "r": r, "lim": lim, "win": win, "pen": pen}
        if cost(q) <= c0 + BUDGET + 1e-9:
            key = (sum(_valid(a) for a in _statuses(w, q)), -cost(q))
            if bestkey is None or key > bestkey:
                best, bestkey = q, key
    arms["static_costmatched"] = {"params": best, "seq": [], "decider": "grid search over static sensors with the same total cost, scored by valid statuses"}
    # the measurement: for each component a true amplitude difference, identified or not
    lat = []
    for i in range(w.n()):
        w1 = w.copy()
        w1.comps[i].amp *= 1.6
        lat.append(([W.latent(w, T20, rng) for _ in range(trials)], [W.latent(w1, T20, rng) for _ in range(trials)]))
    res = {}
    for name, arm in arms.items():
        p = arm["params"]
        sn = _sensor(p)
        sts = _statuses(w, p)
        ident = 0
        for i in range(w.n()):
            orng = np.random.default_rng((seed, i, len(name)))
            a0 = [W.observe(w, x, T20, sn, orng, [i])[i] for x in lat[i][0]]
            a1 = [W.observe(w, x, T20, sn, orng, [i])[i] for x in lat[i][1]]
            # the second condition has the changed component i: re-observe from its own world
            wi = w.copy()
            wi.comps[i].amp *= 1.6
            a1 = [W.observe(wi, x, T20, sn, orng, [i])[i] for x in lat[i][1]]
            ident += W.detect("amplitude", a0, a1, orng)["result"] == "identified"
        log = _revise_log(INITIAL, arm["seq"], w, "researcher" if name in ("prespecified", "random") else "system", name)[1] if arm["seq"] else []
        res[name] = {"params": p, "cost": cost(p), "cost_over_initial": cost(p) - c0, "valid_statuses": int(sum(_valid(a) for a in sts)), "identified": int(ident), "revisions": len(arm["seq"]), "sequence": arm["seq"],
                     "decider": arm["decider"], "events": [{k: e[k] for k in ("seq", "type", "status", "reason", "initiated_by", "autonomous_revision_demonstrated", "gained", "lost")} for e in log],
                     "capabilities_lost": int(sum(len(e["lost"]) for e in log))}
    return {"seed": seed, "targets": w.n(), "initial_cost": c0, "budget": BUDGET, "arms": res}


# ================================================================================================ E
DEGRADATIONS = ("reference", "partial", "gaps", "coarse", "hidden", "noisy", "desync")
Q_T = np.arange(1.0, 19.0, 0.1)


def _interp(t: np.ndarray, v: np.ndarray, q: np.ndarray) -> tuple[np.ndarray, float] | None:
    ok = ~np.isnan(v)
    if ok.sum() < W.MIN_VALID:
        return None
    order = np.argsort(t[ok], kind="stable")
    tt, vv = t[ok][order], v[ok][order]
    keep = np.concatenate([[True], np.diff(tt) > 1e-9])  # jittered sampling times can coincide: one value per time
    tt, vv = tt[keep], vv[keep]
    if len(tt) < 4:
        return None
    pred = np.interp(q, tt, vv)
    # leave-one-out residual of linear interpolation at the sampled points = the method's own uncertainty
    loo = vv[1:-1] - (vv[:-2] + (vv[2:] - vv[:-2]) * (tt[1:-1] - tt[:-2]) / (tt[2:] - tt[:-2]))
    return pred, float(np.sqrt(np.mean(loo**2)))


def run_e(seed: int) -> dict:
    """One world and one realisation, degraded in six ways; three reconstruction methods; truth is the noise-free latent signal at the query times."""
    rng = np.random.default_rng(seed)
    w = W.make_world(seed)
    x = W.latent(w, T20, rng)
    qi = np.round(Q_T / W.DT).astype(int)
    truth = x[:, qi]
    z = 1.645
    base = {"ts": 0.02, "r": 0.5, "lim": 0.05, "win": 20.0, "pen": 0.9}
    spec = {"reference": (base, None, 0.0, 0.0), "partial": (base, list(range(0, w.n(), 2)), 0.0, 0.0), "gaps": (base, None, 0.4, 0.0), "coarse": ({**base, "ts": 1.0}, None, 0.0, 0.0),
            "hidden": ({**base, "pen": 0.3}, None, 0.0, 0.0), "noisy": (base, None, 0.0, 0.0), "desync": (base, None, 0.0, 0.12)}
    out: dict[str, Any] = {"seed": seed, "conditions": {}}
    for name, (p, comps, gaps, jit) in spec.items():
        orng = np.random.default_rng((seed, len(name)))
        sn = _sensor(p)
        obs = W.observe(w, x, T20, sn, orng, comps, gaps=gaps, sync_jitter_s=jit)
        if name == "noisy":  # three times the sensor noise
            obs = {i: (t, v + orng.normal(0, 2 * W.NOISE_SD, len(v))) for i, (t, v) in obs.items()}
        cfg = cfg_of(sn)
        status_ok = [_valid(OB.assess_target(cfg, W.spec_of(w, i), 0.0)) for i in range(w.n())]
        prior_sd = float(np.sqrt(np.mean([c.amp**2 / 2 for c in w.comps])))
        per = {"zero": [], "interp": [], "graph": []}
        for i in range(w.n()):
            tr = truth[i]
            sd_i = float(tr.std()) or 1.0
            cell = {}
            cell["zero"] = (np.zeros_like(tr), prior_sd)
            r1 = _interp(*obs[i], Q_T) if i in obs and status_ok[i] else None
            cell["interp"] = r1
            # graph-informed: the known couplings give the coupled part of the signal from observed parents; the own part is unknown (its variance is the uncertainty)
            parents = [(a, k) for (a, b), k in w.edges.items() if b == i]
            part = np.zeros_like(tr)
            ok_par = 0
            for a, k in parents:
                ra = _interp(*obs[a], Q_T - w.lag_s) if a in obs and status_ok[a] else None
                if ra is not None:
                    part += k * ra[0]
                    ok_par += 1
            cell["graph"] = (part, float(np.sqrt(w.comps[i].amp**2 / 2 + 0.0))) if ok_par else None
            if r1 is not None:  # a component with its own samples: the interpolation, whose uncertainty is its own leave-one-out error (sensor noise is part of it)
                cell["graph"] = (r1[0], r1[1]) if cell["graph"] is None else cell["graph"]
            for m, v in cell.items():
                if v is None:
                    per[m].append({"c": i, "identifiable": False})
                else:
                    pred, sd = v
                    err = pred - tr
                    per[m].append({"c": i, "identifiable": True, "nrmse": float(np.sqrt(np.mean(err**2)) / sd_i), "cover": float(np.mean(np.abs(err) <= z * max(sd, 1e-9))), "sd_true": sd_i})
        out["conditions"][name] = {"status_valid": int(sum(status_ok)), "methods": per}
    return out
