"""The autonomous research loop over the total-observation world, for several generations.

    observing layout -> local observation -> identification / failure -> change of question -> change of hypothesis -> change of experimental condition
    -> new intervention -> change in the object system -> reorganised later observing conditions -> re-entry of history

One generation = ``gen_steps`` steps of the world with the observers working. At its end the agent (``agent.py``, records only) builds its findings,
tests its hypothesis, evaluates itself, and proposes operations for the next generation; the orchestrator executes as many as the budget and ``max_ops``
allow. The orchestrator also holds the world and the verifier: it scores what the agent identified against the world's own state, records what an
operation did to the observable sets (``hpo.reachability.compare_levels``), and keeps the ledger. None of that goes back to the agent.

Re-used, not re-implemented: ``hpo.metarevision`` (RuleSpec / RuleTable / MetaReviser: the same judging of a rule by whether the blindness it targeted
persisted, the same bounded steps, the same exhaustion), ``hpo.reachability.compare_levels`` (the same level sets and verdicts). The HPO controller itself
(``hpo.reconfig``) is bound to the HPO field and is not used here; the research line has its own operation grammar over its own world.
"""

from __future__ import annotations

import copy
import time

import numpy as np

from ..hpo.metarevision import MetaReviser, RuleTable
from ..hpo.reachability import compare_levels
from . import agent as A
from . import ontology, planetary, sss
from . import verifier as V
from .identify import INTEGRATIONS, IdentParams, identify
from .observers import ObserverNet, Record, Sensor
from .world import World, WorldConfig

SCHEMA = "xzr.totalobs.run/1"
DEFAULT_ENV: dict = {
    "world": {},
    "net": {
        "n_sensors": 2,
        "radius": 3,
        "scale": 1,
        "period": 4,
        "pool": 30.0,
        "latency": 1,
        "capacity": 300,
        "staleness": 12,
        "noise": 0.02,
        "backaction": 0.05,
        "wear": 0.08,
    },
    "generations": 8,
    "gen_steps": 40,
    "warmup": 12,
    "checkpoint": 8,
    "events": [],
}


def merge_env(env: dict | None) -> dict:
    out = copy.deepcopy(DEFAULT_ENV)
    for k, v in (env or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def new_sensor(i: int, region: int, net: dict, period: int) -> Sensor:
    """Sensor ``i``. ``net.periods`` (optional list) gives the sensors different periods (asynchronous observation); phases are staggered."""
    per = net.get("periods")
    p = int(per[i % len(per)]) if per else int(net["period"])
    return Sensor(
        f"S{i}",
        region,
        radius=int(net["radius"]),
        scale=int(net["scale"]),
        period=p,
        phase=i % max(1, p),
        noise=float(net["noise"]),
        backaction=float(net["backaction"]),
        wear=float(net["wear"]),
    )


def build(env: dict, gen: int, seed: int) -> tuple[WorldConfig, World, ObserverNet]:
    cfg = WorldConfig(**env["world"])
    w = World(cfg, gen, seed)
    n = env["net"]
    net = ObserverNet(cfg, hub=0, latency=int(n["latency"]), pool=float(n["pool"]), capacity=int(n["capacity"]))
    net.seed(seed)
    k = int(n["n_sensors"])
    for i in range(k):
        net.add(new_sensor(i, int((i + 0.5) * cfg.n / k), n, int(n["period"])))
    for _ in range(int(env.get("warmup", 12))):
        w.step()
    return cfg, w, net


# ---------------------------------------------------------------------------------------------------- the agent's findings (records + own configuration only)
def sensor_info(net: ObserverNet, recs: list[Record]) -> dict[str, dict]:
    last: dict[str, Record] = {}
    for r in sorted(recs, key=lambda r: r.t_obs):
        last[r.sid] = r
    return {
        sid: {**s.spec(), "cost_blocks": len(last[sid].blocks) if sid in last else 0} for sid, s in sorted(net.sensors.items())
    }


def edge_suspects(records: list[Record], theta: float) -> set[int]:
    """Regions of blocks that lie next to a block just under the threshold (an object that the block boundary may have cut)."""
    out: set[int] = set()
    last: dict[str, Record] = {}
    for r in sorted(records, key=lambda r: r.t_obs):
        last[r.sid] = r
    for r in last.values():
        if r.scale <= 1:
            continue
        for (by, bx), (v, idx) in r.blocks.items():
            if v <= theta:
                continue
            for nb in ((by + 1, bx), (by - 1, bx), (by, bx + 1), (by, bx - 1)):
                if nb in r.blocks and 0.4 * theta < r.blocks[nb][0] <= theta:
                    out |= set(idx)
    return out


def make_findings(
    g: int,
    cfg: WorldConfig,
    net: ObserverNet,
    t: int,
    t_gen0: int,
    ident: IdentParams,
    denied: int,
    d: np.ndarray,
    staleness: int,
) -> A.Findings:
    recs = net.view(t, staleness)
    objs = identify(cfg, recs, ident, d)
    sus = edge_suspects(recs, ident.theta)
    objects = [
        {
            "key": o["key"],
            "n_cells": len(o["cells"]),
            "peak": o["peak"],
            "cells": o["cells"],
            "edge_suspect": bool(set(o["cells"]) & sus),
        }
        for o in objs
    ]
    covered = {
        i
        for r in {x.sid: x for x in sorted(recs, key=lambda r: r.t_obs)}.values()
        for _, (_, idx) in r.blocks.items()
        for i in idx
    }
    reported = {r.sid for r in recs if r.t_obs >= t_gen0}
    silent = [sid for sid in sorted(net.sensors) if sid not in reported]
    sets = {
        m: sorted(
            o["key"] for o in identify(cfg, recs, IdentParams(ident.theta, ident.connect, m, ident.variable, ident.min_cells), d)
        )
        for m in INTEGRATIONS
    }
    return A.Findings(g, objects, len(covered) / cfg.n, silent, denied, len(recs), sensor_info(net, recs), integration_sets=sets)


def nominal_blocks(w_d: np.ndarray, cfg: WorldConfig, s: Sensor) -> int:
    """Blocks one full observation by ``s`` would read (what the agent can compute from its own configuration)."""
    from .observers import block_of

    return len({block_of(cfg, int(i), s.scale, s.offset) for i in np.flatnonzero(w_d[s.region] <= s.radius)})


def v2_status(cfg: WorldConfig, net: ObserverNet, d: np.ndarray, t: int, t0: int, lost_prev: int) -> tuple[dict, int, float, int]:
    """Rules v2. For every sensor, what the hub's own bookkeeping says about its reports in this generation: ``ok``, ``partial`` (fewer blocks than the footprint:
    cost denied), ``delayed`` (reports arrive later than one period), ``no-arrival`` (reports were due and none arrived) or ``not-due`` (none could have arrived
    yet). The expected arrivals use only the agent's own layout, the grid and the declared latency. The cause of a missing report (outage, stopped sensor, lost
    records) is NOT decided here. Also: records the hub received but no longer holds (its own accounting), and the demand of the configuration on the pool."""
    status: dict[str, dict] = {}
    demand = 0.0
    for sid, s in sorted(net.sensors.items()):
        delay = int(d[s.region, net.hub]) * net.latency
        nb = nominal_blocks(d, cfg, s)
        due = sum(1 for to in range(max(1, t0 + 1 - delay), t - delay + 1) if (to - s.phase) % s.period == 0)
        got = [r for r in net.store if r.sid == sid and t0 < r.t_arrive <= t]
        if due == 0:
            state = "not-due"
        elif not got:
            state = "no-arrival"
        else:
            lag = float(np.mean([r.t_arrive - r.t_obs for r in got]))
            blocks = float(np.mean([len(r.blocks) for r in got]))
            state = "delayed" if lag > s.period else ("partial" if blocks < 0.8 * nb else "ok")
        status[sid] = {"state": state, "due": due, "arrived": len(got), "expected_delay": delay, "nominal_blocks": nb}
        demand += nb / s.period
    lost = net.received - net.evicted - len(net.store)
    return status, max(0, lost - lost_prev), demand, lost


def truth_cause(net: ObserverNet, sid: str, delay: int, denied_delta: int, record_loss_event: bool, state: str) -> str:
    """Verifier side: the true cause of a sensor's missing, late or partial reports, in a fixed order of precedence (a stopped sensor, an outage over its
    position, a loss of records at the hub, denial of cost, transit delay longer than one period). Never given to the agent."""
    s = net.sensors[sid]
    if not s.alive:
        return "failed"
    if s.region in net.cut_zone:
        return "outage"
    if record_loss_event and state == "no-arrival":
        return "record-loss"
    if denied_delta > 0 and state in ("partial", "no-arrival"):
        return "pool-denied"
    if delay > s.period:
        return "delay"
    return "none-found"


# ---------------------------------------------------------------------------------------------------- levels of reachability (sets over the observing net)
def _bin(cfg: WorldConfig, i: int) -> str:
    r, c = divmod(i, cfg.cols)
    return f"{r // 2}:{c // 3}"


def levels(
    cfg: WorldConfig,
    w: World,
    net: ObserverNet,
    rc: A.RC,
    design: A.Design,
    budget: float,
    ident: IdentParams,
    t: int,
    last_reporters: set[str],
    staleness: int,
) -> dict:
    """The sets compare_levels works on. available: operations the grammar, the authority and the budget permit, and the sensors that are alive;
    executable: sensors that reported in the last generation; identified: identified objects; reachable_clusters: region bins inside footprints whose
    reports can reach the hub; observable_cells: (sensor, block) cells in the hub's current view."""
    ops = [o for o in sorted(rc.grammar) if (design.authority is None or o in design.authority) and A.OP_COST[o] <= budget + 1e-9]
    alive = [f"sensor:{sid}" for sid, s in sorted(net.sensors.items()) if s.alive]
    reach: set[int] = set()
    for s in net.sensors.values():
        if s.alive and s.region not in net.cut_zone:
            reach |= {int(i) for i in np.flatnonzero(w.d[s.region] <= s.radius)}
    recs = net.view(t, staleness)
    cells = sorted({f"{r.sid}:{b[0]},{b[1]}" for r in recs for b in r.blocks})
    ids = sorted(o["key"] for o in identify(cfg, recs, ident, w.d))
    return {
        "t": int(t),
        "available": sorted(ops + alive),
        "executable": sorted(f"sensor:{s}" for s in last_reporters),
        "identified": ids,
        "reachable_clusters": sorted({_bin(cfg, i) for i in reach}),
        "observable_cells": cells,
        "reachable_configurations": len(reach),
    }


# ---------------------------------------------------------------------------------------------------- variable adoption (with a matched control)
def adopt_variable(cfg: WorldConfig, recs: list[Record], rc: A.RC, cand: str, d: np.ndarray, seed: int) -> dict:
    """A derived variable is adopted only if it identifies more objects than the variable in force and more than the same derivation applied to
    time-shuffled records (a capacity-matched control). Adoption is a proposal about the observing configuration, not a finding."""
    base = rc.ident
    p_c = IdentParams(base.theta * 0.5, base.connect, base.integrate, cand, base.min_cells)
    n_base = len(identify(cfg, recs, base, d))
    n_cand = len(identify(cfg, recs, p_c, d))
    rng = np.random.default_rng(seed)
    by: dict[str, list[int]] = {}
    for i, r in enumerate(recs):
        by.setdefault(r.sid, []).append(i)
    shuffled = list(recs)
    for idx in by.values():
        order = sorted(idx, key=lambda i: recs[i].t_obs)
        perm = rng.permutation(len(order))
        for k, j in enumerate(order):
            src = recs[order[int(perm[k])]]
            shuffled[j] = Record(recs[j].sid, recs[j].t_obs, recs[j].t_arrive, src.scale, src.offset, src.blocks)
    n_ctl = len(identify(cfg, shuffled, p_c, d))
    adopted = n_cand > n_base and n_cand > n_ctl
    classes = ["transformation"]  # derived from the existing variable: not a new name, not a new instrument
    if n_cand > n_base:
        classes.append("new identification ability")
    return {
        "candidate": cand,
        "theta": round(p_c.theta, 6),
        "objects_level": n_base,
        "objects_candidate": n_cand,
        "objects_control": n_ctl,
        "adopted": adopted,
        "classes": classes if adopted else ["not adopted"],
    }


# ---------------------------------------------------------------------------------------------------- the hypothesis test (an intervention and its observed arrival)
def evaluate_experiment(exp: dict, net: ObserverNet, hyp: dict, noise: float) -> dict:
    """Agent side: arrival of the perturbation's effect in sensor B's records. Verifier side: arrival in the world at B's centre (``true_lag``)."""
    B = net.sensors[exp["B"]]
    recs = sorted((r for r in net.store if r.sid == B.sid), key=lambda r: r.t_obs)
    pre = [max(v for v, _ in r.blocks.values()) for r in recs if r.t_obs <= exp["t0"] and r.blocks][-2:]
    base = float(np.mean(pre)) if pre else 0.0
    delta = max(exp["delta"], 3 * noise)
    arrive = next(
        (r.t_obs for r in recs if r.t_obs > exp["t0"] and r.blocks and max(v for v, _ in r.blocks.values()) > base + delta), None
    )
    D = exp["D"]
    out = {
        "B": exp["B"],
        "site": exp["site"],
        "D": D,
        "t0": exp["t0"],
        "c_hat_before": hyp["c_hat"],
        "baseline": round(base, 4),
        "delta": round(delta, 4),
    }
    if arrive is None:
        out["outcome"] = "no-arrival"
    else:
        lag = arrive - exp["t0"]
        pred = D / hyp["c_hat"]
        err = abs(lag - pred) / max(pred, 1e-9)
        out.update(lag=lag, predicted_lag=round(pred, 4), error=round(err, 4), c_obs=round(D / max(lag, 1), 4))
        out["outcome"] = "coarse" if lag <= B.period else ("supported" if err <= 0.35 else "refuted")
    out["true_lag"] = exp["true_lag"]  # verifier side (counterfactual forks); the agent never reads it
    return out


PERTURB_AMOUNT, PERTURB_RADIUS, TEST_DISTANCE, QUIET, DELTA, MAX_DELTA = 30.0, 1, 3, 0.04, 0.15, 0.4


def plan_test(net: ObserverNet, w: World) -> dict | None:
    """The agent's test design: the first sensor whose reports reach the hub is the detector (B); the intervention site is the lowest-numbered
    region at grid distance ``TEST_DISTANCE`` from B's centre. The intervention may be made anywhere (it is not limited by a footprint)."""
    ok = [
        s for s in sorted(net.sensors.values(), key=lambda s: (s.period, s.sid)) if s.alive and s.region not in net.cut_zone
    ]  # the fastest sensor first: a period fix stays with the detector

    def quiet(
        sn: Sensor,
    ) -> bool:  # records only: the detector's last two reports agree (it is not in the middle of a natural rise), so a rise afterwards can be attributed to the test
        last = [
            max(v for v, _ in r.blocks.values())
            for r in sorted(net.store, key=lambda r: r.t_obs)
            if r.sid == sn.sid and r.blocks and r.t_obs > w.t - 12
        ][-2:]
        return len(last) >= 2 and max(last) - min(last) < QUIET

    def natural_delta(
        sn: Sensor,
    ) -> float:  # the detection threshold: four times the detector's own report-to-report variation, from its records
        ser = [
            max(v for v, _ in r.blocks.values())
            for r in sorted(net.store, key=lambda r: r.t_obs)
            if r.sid == sn.sid and r.blocks and r.t_obs > w.t - 48
        ]
        return max(DELTA, 4 * float(np.std(np.diff(ser)))) if len(ser) >= 4 else DELTA

    ok = [(s, natural_delta(s)) for s in ok if quiet(s)]
    ok = [
        (s, dl) for s, dl in ok if dl <= MAX_DELTA
    ]  # a detector noisier than a fraction of the injected effect cannot attribute a rise to the test
    if not ok:
        return None
    b, delta = ok[0]
    # the site lies TEST_DISTANCE regions outside the detector's footprint, so the detector cannot see the injection itself, only what propagates to it
    site = next((int(i) for i in range(w.cfg.n) if w.d[b.region, i] == b.radius + TEST_DISTANCE), None)
    return None if site is None else {"B": b.sid, "site": site, "D": TEST_DISTANCE, "delta": round(delta, 4)}


def true_arrival(w: World, site: int, foot: np.ndarray, delta: float, horizon: int) -> int | None:
    """Verifier side: steps until the perturbation changes the activity anywhere in B's footprint (at full resolution) by more than the detection step, from two forks of the world
    without observers (with / without the perturbation)."""
    f0, f1 = copy.deepcopy(w), copy.deepcopy(w)
    f1.perturb(site, PERTURB_AMOUNT, PERTURB_RADIUS)
    for k in range(1, horizon + 1):
        f0.step()
        f1.step()
        if float(np.max(f1.u[foot] - f0.u[foot])) > delta:
            return k
    return None


def start_test(w: World, net: ObserverNet, plan: dict, noise: float, horizon: int) -> dict:
    exp = {**plan, "t0": int(w.t), "region": plan["site"]}
    b = net.sensors[plan["B"]]
    exp["true_lag"] = true_arrival(w, plan["site"], np.flatnonzero(w.d[b.region] <= b.radius), plan["delta"], horizon)
    exp["regions"] = w.perturb(plan["site"], PERTURB_AMOUNT, PERTURB_RADIUS)
    return exp


# ---------------------------------------------------------------------------------------------------- the run
def run(env_in: dict, arm: dict, gen: int, seed: int) -> dict:
    t_wall = time.time()
    env = merge_env(env_in)
    design = A.Design.from_dict(arm.get("design"))
    cfg, w, net = build(env, gen, seed)
    d = w.d
    G, T = int(env["generations"]), int(env["gen_steps"])
    cp = int(env["checkpoint"])
    stale = int(env["net"]["staleness"])
    ev_by_gen: dict[int, list[dict]] = {}
    for e in env["events"]:
        ev_by_gen.setdefault(int(e["gen"]), []).append(e)

    rc = A.RC()
    rc.grammar |= {op for s in design.strong for op in A.UNLOCKS[s]}
    if design.policy == "random" and "grammar" in design.strong:
        rc.grammar.add("perturb")
    reviser = MetaReviser(rules=RuleTable(A.OBS_SPEC)) if design.meta else None
    rules = reviser.rules if reviser else RuleTable(A.OBS_SPEC)
    mem = A.Memory(mode=design.history)
    rng = np.random.default_rng(seed * 31 + gen)
    version = env.get("rules_version", "v1")
    if version not in ("v1", "v2"):
        raise ValueError("rules_version must be 'v1' or 'v2'")
    v2 = version == "v2"
    if v2:
        net.freshness = "arrival"  # the freshness window counts from arrival: a record delayed in transit is not thrown away for having been in transit
    metlog = sss.MetricLog("v2" if v2 else "v1")
    budget = float(design.budget)
    silence_audit: list[dict] = []
    scale_dir: dict[str, int] = {}
    reversals = ident_lost_present = ident_lost_absent = 0
    lost_prev = 0
    denied_snap: dict[str, int] = {}
    conflicts_seen = 0

    gens: list[dict] = []
    scores: list[dict] = []
    pending: list[dict] = []
    prev_f: A.Findings | None = None
    prev_lv: dict | None = None
    last_reporters: set[str] = set()
    stopped: dict | None = None
    no_obj_streak = eval_true = eval_false = stagnant = 0
    perturb_noarrival = 0
    perturb_since_extend = False
    counters = {
        "ops_executed": 0,
        "ops_denied": 0,
        "ops_rejected": 0,
        "opportunity_cost": 0,
        "question_changes": 0,
        "eval_changes": 0,
        "grammar_changes": 0,
        "rollbacks": 0,
        "variables_adopted": 0,
        "variables_rejected": 0,
        "history_changes": 0,
        "reach_expanded": 0,
        "reach_contracted": 0,
        "reach_mixed": 0,
        "reach_equivalent": 0,
        "ident_lost": 0,
        "ident_gained": 0,
        "integration_loss_events": 0,
        "hyp_tests": 0,
        "hyp_supported": 0,
        "hyp_refuted": 0,
        "hyp_inconclusive": 0,
        "meta_revisions": 0,
        "meta_exhausted": 0,
    }
    if v2:
        counters["hyp_withdrawn"] = 0
    ages: list[float] = []
    hyp_true_err: float | None = None

    for g in range(G):
        t_gen0 = w.t
        rec_g: dict = {
            "gen": g,
            "t0": int(t_gen0),
            "before": {
                **rc.to_dict(),
                "sensors": {k: s.spec() for k, s in sorted(net.sensors.items())},
                "budget": round(budget, 3),
            },
        }
        # --- harness events (changes of the world and of the net that the agent did not choose)
        applied_events = []
        for e in ev_by_gen.get(g, []):
            do = e["do"]
            if do == "fail_sensor":
                net.fail(e["sensor"])
            elif do == "cut_zone":
                net.cut(w, int(e["center"]), int(e.get("radius", 3)))
            elif do == "restore_links":
                net.restore_links()
            elif do == "lose_records":
                net.lose_records(int(e.get("t0", 0)), int(e.get("t1", w.t + 1)), set(e["sensors"]) if e.get("sensors") else None)
            elif do == "move_source":
                w.move_source(int(e["k"]), int(e["region"]))
            elif do == "add_source":
                w.add_source(int(e["region"]))
            elif do == "set_pool":
                net.pool = float(e["pool"])
            else:
                raise ValueError(f"unknown event {do!r}")
            applied_events.append(e)
        rec_g["events"] = applied_events
        n_true_before = len(V.true_objects(w))
        marks_before = float(w.m.sum())
        # --- execute the operations decided at the end of the previous generation
        ops_done: list[dict] = []
        exp: dict | None = None
        for op in pending:
            c = 3.0 if op["op"] == "reenter" else A.OP_COST.get(op["op"], 1.0)
            row = {
                **{k: v for k, v in op.items() if k != "config"},
                "cost": c,
                "rules_in_force": dict(rules.params) if op["reason"] in A.OBS_SPEC.param_of_reason else None,
            }
            if c > budget + 1e-9:
                row["status"] = "denied (budget)"
                counters["ops_denied"] += 1
                ops_done.append(row)
                continue
            before = {k: s.spec() for k, s in sorted(net.sensors.items())}
            before_id = rc.ident.to_dict()
            status = "executed"
            o = op["op"]
            if o == "add-sensor":
                taken = {s.region for s in net.sensors.values()}
                covered = {int(i) for s in net.sensors.values() if s.alive for i in np.flatnonzero(d[s.region] <= s.radius)}
                region = A.best_new_center(d, covered, int(env["net"]["radius"]), taken, net.hub)
                sid = f"S{len(net.sensors)}"
                net.add(new_sensor(len(net.sensors), region, env["net"], int(env["net"]["period"])))
                row.update(sid=sid, region=region)
            elif o == "move-sensor":
                net.sensors[op["sid"]].region = int(op["region"])
            elif o == "set-scale":
                _dir = 1 if int(op["value"]) > net.sensors[op["sid"]].scale else -1
                if scale_dir.get(op["sid"], _dir) != _dir:
                    reversals += 1
                scale_dir[op["sid"]] = _dir
                mem.cool[f"{op['sid']}:{op.get('direction', 1 if int(op['value']) > net.sensors[op['sid']].scale else -1)}"] = g
                net.sensors[op["sid"]].scale = int(op["value"])
            elif o == "set-period":
                net.sensors[op["sid"]].period = int(op["value"])
            elif o == "set-offset":
                net.sensors[op["sid"]].offset = (int(op["value"][0]), int(op["value"][1]))
            elif o == "set-integration":
                rc.ident = IdentParams(rc.ident.theta, rc.ident.connect, op["value"], rc.ident.variable, rc.ident.min_cells)
            elif o == "set-threshold":
                rc.ident = IdentParams(
                    float(op["value"]), rc.ident.connect, rc.ident.integrate, rc.ident.variable, rc.ident.min_cells
                )
            elif o == "set-connect":
                rc.ident = IdentParams(
                    rc.ident.theta, int(op["value"]), rc.ident.integrate, rc.ident.variable, rc.ident.min_cells
                )
            elif o == "set-evaluation":
                rc.eval_rule = op["value"]
            elif o == "derive-variable":
                res = adopt_variable(cfg, net.view(w.t, stale), rc, op["value"], d, seed + g)
                row["result"] = res
                if res["adopted"]:
                    rc.ident = IdentParams(res["theta"], rc.ident.connect, rc.ident.integrate, op["value"], rc.ident.min_cells)
                    counters["variables_adopted"] += 1
                else:
                    status = "rejected"
                    counters["variables_rejected"] += 1
            elif o == "extend-grammar":
                rc.grammar.add(op["adds"])
                perturb_since_extend, perturb_noarrival = True, 0
                counters["grammar_changes"] += 1
            elif o == "perturb":
                plan = plan_test(net, w)
                if plan is None:
                    status = "rejected"
                else:
                    exp = start_test(w, net, plan, float(env["net"]["noise"]), T)
                    row.update(B=plan["B"], site=plan["site"], D=plan["D"])
            elif o == "reenter":
                cfgd = op["config"]
                for sid, spec in cfgd["sensors"].items():
                    if sid in net.sensors:
                        s = net.sensors[sid]
                        s.region, s.scale, s.period, s.radius = spec["region"], spec["scale"], spec["period"], spec["radius"]
                        s.offset = tuple(spec["offset"])
                rc.ident = IdentParams(**cfgd["ident"])
                counters["history_changes"] += 1
            if status == "executed":
                budget -= c
                counters["ops_executed"] += 1
                if reviser is not None and op["reason"] in A.OBS_SPEC.param_of_reason:
                    reviser.register("net", op["reason"], len(ops_done), g, [])
            row["status"] = status
            row["effect"] = {
                "sensors_before": before,
                "sensors_after": {k: s.spec() for k, s in sorted(net.sensors.items())},
                "ident_before": before_id,
                "ident_after": rc.ident.to_dict(),
            }
            ops_done.append(row)
        # an extension of the grammar needs the hypothesis test to be run in this generation if possible
        if (
            rc.question == "trace"
            and exp is None
            and "perturb" in rc.grammar
            and (design.authority is None or "perturb" in design.authority)
            and design.policy == "adaptive"
        ):
            plan = plan_test(net, w)
            if plan is not None and not any(o["op"] == "perturb" for o in ops_done) and budget >= A.OP_COST["perturb"]:
                budget -= A.OP_COST["perturb"]
                counters["ops_executed"] += 1
                exp = start_test(w, net, plan, float(env["net"]["noise"]), T)
                ops_done.append(
                    {
                        "op": "perturb",
                        "reason": "hypothesis-test",
                        "status": "executed",
                        "cost": A.OP_COST["perturb"],
                        "B": plan["B"],
                        "site": plan["site"],
                        "D": plan["D"],
                        "rules_in_force": None,
                    }
                )
        rec_g["ops"] = ops_done
        rc_changes: list[dict] = []
        # --- levels right after the change (static): same records, new configuration
        lv_static = levels(cfg, w, net, rc, design, budget, rc.ident, w.t, last_reporters, stale)
        if prev_lv is None:
            prev_lv = lv_static
        # --- the generation
        stats0 = dict(net.stats)
        for k in range(T):
            w.step()
            net.observe(w)
            if (k + 1) % cp == 0:
                recs = net.view(w.t, stale)
                ids = identify(cfg, recs, rc.ident, d)
                sc = V.score(w, ids)
                cls = V.classify_identified(w, ids)
                age = float(np.mean([w.t - r.t_obs for r in recs])) if recs else None
                scores.append(
                    {
                        "t": int(w.t),
                        "gen": g,
                        **sc,
                        "config_born": sum(1 for v in cls.values() if v == "configuration"),
                        "age": age,
                    }
                )
                if age is not None:
                    ages.append(age)
                metlog.measure("recall_region", sc["recall"], {"freshness": net.freshness}, w.t)
                metlog.measure(
                    "identified_count",
                    len(ids),
                    {
                        "rows": cfg.rows,
                        "cols": cfg.cols,
                        "theta": rc.ident.theta,
                        "connect": rc.ident.connect,
                        "scale_profile": tuple(sorted(s.scale for s in net.sensors.values())),
                        "variable": rc.ident.variable,
                        "integrate": rc.ident.integrate,
                        "freshness": net.freshness,
                    },
                    w.t,
                )
                metlog.measure("info_age", age, {"staleness": stale, "freshness": net.freshness}, w.t)
        denied = int(net.stats["denied_blocks"] - stats0["denied_blocks"])
        # --- findings, tests, evaluation
        f = make_findings(g, cfg, net, w.t, t_gen0, rc.ident, denied, d, stale)
        if v2:
            f.sensor_status, f.records_lost, f.demand, lost_prev = v2_status(cfg, net, d, w.t, t_gen0, lost_prev)
            for sid_, info_ in f.sensors.items():
                info_["nominal_blocks"] = f.sensor_status[sid_]["nominal_blocks"]
            # verifier-side audit of the agent's per-sensor states against the true causes (never given to the agent)
            loss_event = any(e["do"] == "lose_records" for e in applied_events)
            for sid_, st_ in f.sensor_status.items():
                dd = net.per.get(sid_, {}).get("denied_blocks", 0) - denied_snap.get(sid_, 0)
                denied_snap[sid_] = net.per.get(sid_, {}).get("denied_blocks", 0)
                if st_["state"] in ("no-arrival", "delayed", "partial"):
                    silence_audit.append(
                        {
                            "gen": g,
                            "sid": sid_,
                            "agent_state": st_["state"],
                            "true_cause": truth_cause(net, sid_, st_["expected_delay"], dd, loss_event, st_["state"]),
                        }
                    )
        hyp_test = None
        if exp is not None:
            hyp_test = evaluate_experiment(exp, net, rc.hyp, float(env["net"]["noise"]))
            counters["hyp_tests"] += 1
            rc.hyp["tests"] += 1
            o = hyp_test["outcome"]
            if o == "supported":
                rc.hyp["status"] = "supported"
                rc.hyp["supported"] += 1
                counters["hyp_supported"] += 1
            elif o == "refuted":
                rc.hyp["status"] = "refuted"
                rc.hyp["refuted"] += 1
                counters["hyp_refuted"] += 1
                rc.hyp["c_hat"] = hyp_test["c_obs"]
                rc_changes.append(
                    {
                        "what": "hypothesis",
                        "from": hyp_test["c_hat_before"],
                        "to": rc.hyp["c_hat"],
                        "why": "refuted by the perturbation test",
                    }
                )
            else:
                rc.hyp["inconclusive"] += 1
                counters["hyp_inconclusive"] += 1
                if o == "coarse":
                    rc.hyp["c_hat"] = hyp_test["c_obs"]
                if o == "no-arrival" and perturb_since_extend:
                    perturb_noarrival += 1
            if hyp_test.get("true_lag"):
                true_speed = exp["D"] / hyp_test["true_lag"]
                hyp_true_err = abs(rc.hyp["c_hat"] - true_speed) / true_speed
                hyp_test["true_speed"] = round(true_speed, 4)
            if v2:
                # observational support and the model's own state are kept apart (agent.update_hypothesis); agreement with the verifier is recorded and never used
                # by the agent
                h = rc.hyp
                if A.update_hypothesis(h, o, hyp_test.get("c_obs")) == "withdrawn":
                    counters["hyp_withdrawn"] += 1
                if hyp_test.get("true_lag") is None:
                    agree = "unobservable"
                elif "c_obs" in hyp_test:
                    agree = "agree" if abs(hyp_test["c_obs"] / hyp_test["true_speed"] - 1) <= 0.5 else "disagree"
                else:
                    agree = None
                hyp_test.update(
                    observational_support=o,
                    status_after=h["status"],
                    model_agreement=agree,
                    withdrawal="a refuting test after two consistent supports withdraws the support; model_agreement is the verifier's and is not used by the agent",
                )
        elif rc.question == "trace" and design.policy == "adaptive":
            if "perturb" in rc.grammar and (design.authority is None or "perturb" in design.authority):
                hyp_test = {
                    "outcome": "deferred",
                    "why": "no detector was steady enough to attribute a rise to the test, or too little budget",
                }
            else:
                hyp_test = {"outcome": "untestable", "why": "no intervention permitted this generation"}
        f.hyp_test = hyp_test
        A.diagnose(f, rc, {"hub": net.hub, "n": cfg.n, **({"v2": True, "pool": net.pool} if v2 else {})}, prev_f)
        ok = A.eval_ok(rc.eval_rule, f, prev_f, rc)
        metlog.measure("eval_success", bool(ok), {"eval_rule": rc.eval_rule}, w.t)
        last_reporters = {r.sid for r in net.view(w.t, stale) if r.t_obs >= t_gen0}
        # --- meta-revision: did the blindness that earlier changes targeted persist?
        meta_revs: list[dict] = []
        if reviser is not None:
            blind = {"net": {r: [g] for r in f.reasons if r in A.OBS_SPEC.param_of_reason}}
            meta_revs = reviser.judge(blind, g)
            counters["meta_revisions"] += sum(1 for m in meta_revs if m["revision"] == "parameter")
            counters["meta_exhausted"] += sum(1 for m in meta_revs if m["revision"] == "exhausted")
        # --- the integration rule: what each rule would have identified
        sets = f.integration_sets
        cur = sets[rc.ident.integrate]
        best = max(sets.values(), key=len)
        integ = {"in_force": rc.ident.integrate, "sets": sets, "effect": "lost" if len(best) > len(cur) else "invariant"}
        if len(best) > len(cur):
            counters["integration_loss_events"] += 1
            f.reasons.append("integration-loss")
        # --- change of question, evaluation, grammar (adaptive designs only)
        if design.policy == "adaptive":
            persistent = f.persists_from(prev_f)
            no_obj_streak = no_obj_streak + 1 if not f.objects else 0
            q0 = rc.question
            if rc.question == "survey" and ok:
                rc.question = "resolve"
            elif rc.question == "resolve" and persistent and "scale-mismatch" not in f.reasons:
                rc.question = "trace"
            elif rc.question == "trace" and (
                rc.hyp["status"] == "supported" if v2 else (hyp_test and hyp_test.get("outcome") == "supported")
            ):
                rc.question, rc.cycle = "survey", rc.cycle + 1
                rc.cov_target = min(0.9, rc.cov_target + 0.15)
                rc.hyp["status"] = "untested"
                if v2:
                    rc.hyp["consistent"], rc.hyp["last_c_obs"] = 0, None
            elif rc.question != "survey" and no_obj_streak >= 2:
                rc.question = "survey"
            if rc.question != q0:
                counters["question_changes"] += 1
                rc_changes.append(
                    {
                        "what": "question",
                        "from": q0,
                        "to": rc.question,
                        "why": "evaluation satisfied"
                        if ok
                        else "objects lost"
                        if no_obj_streak >= 2
                        else "hypothesis supported"
                        if q0 == "trace"
                        else "persistent objects",
                    }
                )
            if "evaluation" in design.strong:
                eval_true, eval_false = (eval_true + 1, 0) if ok else (0, eval_false + 1)
                nxt = {"E0": "E1", "E1": "E2"}.get(rc.eval_rule)
                if eval_true >= 2 and nxt:
                    metlog.revise("eval_success", f"rule {rc.eval_rule} -> {nxt} (satisfied twice in a row)", w.t)
                    rc_changes.append(
                        {
                            "what": "evaluation-rule",
                            "from": rc.eval_rule,
                            "to": nxt,
                            "why": "satisfied twice in a row: tightened",
                            "comparable_with_before": False,
                        }
                    )
                    rc.eval_rule, eval_true = nxt, 0
                    counters["eval_changes"] += 1
                elif eval_false >= 3 and rc.eval_rule != "E0":
                    prv = {"E1": "E0", "E2": "E1"}[rc.eval_rule]
                    metlog.revise("eval_success", f"rule {rc.eval_rule} -> {prv} (unsatisfied three generations)", w.t)
                    rc_changes.append(
                        {
                            "what": "evaluation-rule",
                            "from": rc.eval_rule,
                            "to": prv,
                            "why": "unsatisfied for three generations: relaxed",
                            "comparable_with_before": False,
                        }
                    )
                    rc.eval_rule, eval_false = prv, 0
                    counters["eval_changes"] += 1
            if perturb_since_extend and perturb_noarrival >= 2 and "perturb" in rc.grammar:
                rc.grammar.discard("perturb")
                perturb_since_extend = False
                counters["rollbacks"] += 1
                counters["grammar_changes"] += 1
                rc_changes.append(
                    {
                        "what": "grammar",
                        "from": "perturb allowed",
                        "to": "perturb withdrawn",
                        "why": "restore: two tests with no arrival",
                    }
                )
        # --- memory (history) and next proposals
        sig = (
            A.signature(f.sensors, rc.ident, rc.ident.variable, rc.ident.integrate) + "@" + rc.question
        )  # a condition is remembered under the question it served
        score_now = A.outcome_score(f, ok)
        proposals: list[dict] = []
        if design.policy != "fixed" and stopped is None:
            proposals = A.propose(
                f,
                rc,
                rules,
                design,
                {"hub": net.hub, "n": cfg.n, "integrate": rc.ident.integrate, **({"v2": True, "pool": net.pool} if v2 else {})},
                mem,
                rng,
                sig,
                score_now,
            )
        mem.write(sig, score_now, {"sensors": {k: v for k, v in f.sensors.items()}, "ident": rc.ident.to_dict()})
        chosen: list[dict] = []
        spend = 0.0
        for p in proposals:
            c = 3.0 if p["op"] == "reenter" else A.OP_COST.get(p["op"], 1.0)
            if len(chosen) < design.max_ops and spend + c <= budget + 1e-9:
                chosen.append(p)
                spend += c
        counters["opportunity_cost"] += len(proposals) - len(chosen)
        pending = chosen
        # --- levels (dynamic), verdicts
        lv_dyn = levels(cfg, w, net, rc, design, budget, rc.ident, w.t, last_reporters, stale)
        eff_static = compare_levels(prev_lv, lv_static)
        eff_dyn = compare_levels(prev_lv, lv_dyn)
        counters[f"reach_{eff_dyn['effect']}"] += 1
        lost_ids = set(prev_lv["identified"]) - set(lv_dyn["identified"])
        gained_ids = set(lv_dyn["identified"]) - set(prev_lv["identified"])
        if v2 and lost_ids and prev_f is not None:
            truth_now = V.true_objects(w)
            for o_ in prev_f.objects:
                if o_["key"] in lost_ids:
                    if any(set(o_["cells"]) & t_ for t_ in truth_now):
                        ident_lost_present += (
                            1  # identification lost while the world's object is still there: unobserved, not gone
                        )
                    else:
                        ident_lost_absent += 1
        counters["ident_lost"] += int(bool(lost_ids))
        counters["ident_gained"] += int(bool(gained_ids))
        sc_g = [s for s in scores if s["gen"] == g]
        rec_g.update(
            {
                "trigger": {
                    "reasons": list(f.reasons),
                    "events": applied_events,
                    **(
                        {"no_arrival": [sid for sid, v in sorted(f.sensor_status.items()) if v["state"] == "no-arrival"]}
                        if v2
                        else {"silent": f.silent}
                    ),
                    "denied_blocks": denied,
                },
                "changes": rc_changes,
                "levels": {
                    "before": prev_lv,
                    "static": lv_static,
                    "dynamic": lv_dyn,
                    "static_effect": eff_static["effect"],
                    "dynamic_effect": eff_dyn["effect"],
                    "dynamic_compare": eff_dyn,
                },
                "observation": {
                    "n_records": f.n_records,
                    "objects": [{k: v for k, v in o.items() if k != "cells"} for o in f.objects],
                    "coverage": round(f.coverage, 4),
                    **({"sensor_status": f.sensor_status, "records_lost_detected": f.records_lost} if v2 else {}),
                },
                "hypothesis_test": hyp_test,
                "evaluation": {"rule": rc.eval_rule, "satisfied": bool(ok)},
                "integration": integ,
                "decision": {
                    "question_next": rc.question,
                    "proposed": [{k: v for k, v in p.items() if k != "config"} for p in proposals],
                    "chosen": [{k: v for k, v in p.items() if k != "config"} for p in chosen],
                    "deferred": len(proposals) - len(chosen),
                    **({"conflicts": mem.conflict_log[conflicts_seen:]} if v2 else {}),
                },
                "rule_revision": meta_revs,
                "rules": rules.snapshot(),
                "world_delta": {
                    "verifier": True,
                    "true_objects": [n_true_before, len(V.true_objects(w))],
                    "marks_added": round(float(w.m.sum()) - marks_before, 4),
                    "activity_total": round(float(w.u.sum()), 4),
                },
                "verifier": {
                    "recall": _mean([s["recall"] for s in sc_g]),
                    "precision": _mean([s["precision"] for s in sc_g]),
                    "n_true": _mean([s["n_true"] for s in sc_g]),
                },
                "failure": {
                    "expired": [sid for sid, s in sorted(net.sensors.items()) if not s.alive],
                    "outage_regions": len(net.cut_zone),
                },
            }
        )
        # --- stop
        executed_any = any(o["status"] == "executed" for o in ops_done)
        stagnant = 0 if (executed_any or rc_changes or f.keys() != (prev_f.keys() if prev_f else set())) else stagnant + 1
        if design.policy == "adaptive" and stopped is None:
            if v2 and all(v["state"] == "no-arrival" for v in f.sensor_status.values()) and budget < A.OP_COST["add-sensor"]:
                stopped = {
                    "gen": g,
                    "reason": "no-arrival: records arrive from no sensor (cause undetermined) and the budget cannot add one",
                }
            elif not v2 and len(f.silent) == len(net.sensors) and budget < A.OP_COST["add-sensor"]:
                stopped = {"gen": g, "reason": "no-observer: every sensor silent and the budget cannot add one"}
            elif stagnant >= 3 and not chosen:
                stopped = {"gen": g, "reason": "stagnation: three generations without a change and nothing left to try"}
        conflicts_seen = len(mem.conflict_log)
        rec_g["stopped"] = stopped if stopped and stopped["gen"] == g else None
        gens.append(rec_g)
        prev_f, prev_lv = f, lv_dyn
        if stopped is not None:
            pending = []
    # --- run-level metrics
    last = [s for s in scores if s["gen"] == len(gens) - 1 and s["recall"] is not None]
    allr = [s["recall"] for s in scores if s["recall"] is not None]
    allp = [s["precision"] for s in scores if s["precision"] is not None]
    n_ident = sum(s["n_identified"] for s in scores)
    metrics = {
        "recall_final": _mean([s["recall"] for s in last]),
        "recall_mean": _mean(allr),
        "precision_mean": _mean(allp),
        "spurious_rate": (sum(s["spurious"] for s in scores) / n_ident) if n_ident else None,
        "config_born_rate": (sum(s["config_born"] for s in scores) / n_ident) if n_ident else None,
        "merged_total": sum(s["merged"] for s in scores),
        "info_age_mean": _mean(ages),
        "generations_run": len(gens),
        "stopped_early": float(stopped is not None),
        "budget_left": round(budget, 3),
        "obs_cost": net.stats["cost"],
        "denied_blocks": net.stats["denied_blocks"],
        "expired_sensors": net.stats["expired"],
        "records_lost": net.stats["records_lost"],
        "lost_in_transit": net.stats["lost_in_transit"],
        "interference": round(net.stats["interference"], 4),
        "n_sensors_final": len(net.sensors),
        "marks_total": round(float(w.m.sum()), 4),
        "history_reads": mem.reads,
        "history_hits": mem.hits,
        "hyp_error_true": hyp_true_err,
        **{k: float(v) for k, v in counters.items()},
    }
    ledger = ontology.ledger(
        w,
        net,
        len(net.view(w.t, stale)),
        {
            "objects": len(prev_f.objects) if prev_f else 0,
            "hypothesis": rc.hyp["status"],
            "eval_rule": rc.eval_rule,
            "variable": rc.ident.variable,
        },
    )
    pl = planetary.conditions(env)
    metrics["planetary_conditions_met"] = pl["n_met"] / pl["n"]
    metrics["planetary_all_met"] = float(pl["all_met"])
    if v2:
        na = [a for a in silence_audit if a["agent_state"] == "no-arrival"]
        metrics.update(
            {
                "scale_reversals": reversals,
                "conflict_events": len(mem.conflict_log),
                "infeasible_events": sum(1 for c in mem.conflict_log if c["resolution"] == "infeasible" or c.get("note")),
                "cooldown_suppressions": len(mem.suppressed),
                "abandoned_sensors": len(mem.abandoned),
                "no_arrival_events": len(na),
                "no_arrival_cause_failed_or_outage": sum(1 for a in na if a["true_cause"] in ("failed", "outage")),
                "ident_lost_object_still_present": ident_lost_present,
                "ident_lost_object_absent": ident_lost_absent,
                "hyp_withdrawn": counters.get("hyp_withdrawn", 0),
            }
        )
    rec = {
        "schema": SCHEMA,
        "arm": arm["name"],
        "gen": gen,
        "seed": seed,
        "status": "ok",
        "metrics": {k: (None if v is None else (float(v) if not isinstance(v, bool) else float(v))) for k, v in metrics.items()},
        "controller": None,
        "protocol_changes": [],
        "reachability_check": None,
        "history_reentry": None,
        "totalobs": {
            "design": design.to_dict(),
            "generations": gens,
            "stopped": stopped,
            "checkpoints": scores,
            "final_rc": rc.to_dict(),
            "metric_log": metlog.report(),
            "ledger": ledger,
            "scope_audit": ontology.scope_audit({"ledger": ledger}),
            "memory": {"mode": design.history, "rows": len(mem.rows), "reads": mem.reads, "hits": mem.hits},
            "suppressed": mem.suppressed,
            "rules": rules.snapshot(),
            "meta_trace": reviser.trace if reviser else [],
            "world_events": w.events,
            "counters": counters,
            "planetary": pl,
            "env": env,
            **(
                {
                    "rules_version": "v2",
                    "freshness": {
                        "rule": net.freshness,
                        "window": stale,
                        "meaning": "a record is usable while the time since its ARRIVAL is within the window; the transit delay is not deducted from its usefulness",
                    },
                    "silence_log": [
                        {
                            **e_,
                            "true_causes_seen_for_this_sensor": sorted(
                                {a["true_cause"] for a in silence_audit if a["sid"] == e_["sid"] and a["gen"] <= e_["gen"]}
                            ),
                        }
                        for e_ in mem.silence_log
                    ],
                    "silence_audit": silence_audit,
                    "conflicts": mem.conflict_log,
                    "hub_accounting": {"received": net.received, "evicted": net.evicted, "held": len(net.store)},
                    "recall_definition": "fraction of the world's objects (verifier, full resolution) overlapped by an object identified from the records the hub's freshness rule lets the agent use; it is "
                    "a measure of what the research system observed, not of the software's reproducibility",
                }
                if v2
                else {}
            ),
        },
        "wall_s": round(time.time() - t_wall, 4),
    }
    return rec


def _mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 6) if xs else None
