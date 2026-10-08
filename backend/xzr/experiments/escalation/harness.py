"""World assembly and paired multi-resolution runs for the resolution-escalation experiments.

A *condition* fixes everything except the structural variant and the engine random stream: world size, horizon,
topology, memory regime, coupling, mutation regime, return structure, addressability, reasoning structure and
size, triggers. One job = one engine seed: the reference variant C, a noise replicate of C (other random stream)
and every other variant are run with the same world; each variant is compared with C window by window at every
resolution, and per-segment summaries are returned for the across-seed tests.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import numpy as np

from ...lod.hierarchy import build_hierarchy, symmetric_adjacency
from ...reasonlab.loop import LoopConfig, ReasonLoop
from ...reasonlab.representations import Edit
from ...reasonlab.structures import VARIANT_NAMES, build_variant, generate, revert_to_reference
from ...reasonlab.triggers import trigger_set
from ...runtime.engine import Engine
from ...runtime.flags import Flags
from ...runtime.intervention import Gate, MemoryCondition, Mutation
from ...runtime.state import Params
from ...scenario.build import World
from ...scenario.model import Scenario, SetSpec
from ...scenario.topologies import (
    apply_memory_regime,
    apply_return_structure,
    calibrate_gain,
    disconnection_structure,
    topology,
)
from ...shapes.multiscale import GLOBAL_KEYS, MultiScaleObserver, labels_for, scale_values, window_distance

RESULTS = Path(__file__).resolve().parents[3] / "experiments" / "results" / "resolution"
SEGMENTS = 8
WINDOWS = 40
NODE_SAMPLE = 4000
NOISE_OFFSET = 1000
REFERENCE: dict = {
    "n": 1500, "horizon": 4000, "topology": "multi_region", "memory": "medium", "coupling": "medium",
    "mutation": "low", "return": None, "address": "stable", "structure": "competing_clusters", "size": 32,
    "triggers": ("memory_level", "mismatch", "failed_intervention"), "enabling": True, "reasoning_from": 200,
    "gen_seed": 3, "seeds": 12, "variants": ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"),
    "revert": (), "flags": {}, "disconnection": None, "p_in": None, "cluster_memory": None,
    "world_schedule": (),  # ({"t": frac of horizon, "op": "open"|"close"|"unstable", "between": "clusters"},)
    "flag_variants": None,  # {name: flags}: runtime-variant studies (no reasoning layer; "C" = reference flags)
}
ENABLING = [  # calibrated on the checks before reasoning is allowed (rel × baseline mean)
    {"name": "record memory", "metric": "memory", "target": "R", "op": ">=", "rel": 0.5},
    {"name": "record activity", "metric": "activity", "target": "R", "op": ">=", "rel": 0.25},
    {"name": "stable addressability", "metric": "stability", "target": "R", "op": ">=", "value": 0.9},
]
MUTATION = {"low": (0.0, 1.0), "medium_topology": (0.0005, 1.0), "high_topology": (0.005, 1.0),
            "high_state": (0.0, 8.0), "mixed": (0.002, 4.0)}  # (connection mutation rate, input-rate factor)


def condition(**over) -> dict:
    c = {**REFERENCE, **over}
    c["id"] = over.get("id") or "reference"
    return c


# ------------------------------------------------------------------------------------------------ calibration
def _family(c: dict) -> tuple[str, int]:
    if c["disconnection"]:
        return f"D:{c['disconnection']}", c["n"]
    if c["return"]:
        return "modular", c["n"]
    if c.get("p_in") is not None:
        return f"{c['topology']}@{c['p_in']}", c["n"]
    return c["topology"], c["n"]


def _builder(c: dict, fam: str):
    n, gs = c["n"], c["gen_seed"]
    if fam.startswith("D:"):
        return lambda p: disconnection_structure(fam[2:], n, gs, p)
    if "@" in fam:
        name, pin = fam.split("@")
        return lambda p: topology(name, n, gs, p, p_in=float(pin))
    return lambda p: topology(fam, n, gs, p)


def calibrations(conds: list[dict], procs: int = 7, path: Path | None = None, base: Path | None = None) -> dict:
    """Calibrated transmission gain per (family, n). The calibration is deterministic (only its recorded wall time
    varies). Cached in ``path`` (default results/resolution/calibration.json, the published studies' cache);
    ``base`` is an additional cache read but never written (``xzr run`` reads the published cache and keeps the
    entries it computes in its own run directory)."""
    from concurrent.futures import ProcessPoolExecutor
    path = path or RESULTS / "calibration.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(base.read_text()) if base is not None and base.exists() else {}
    cache.update(json.loads(path.read_text()) if path.exists() else {})
    need = sorted(f for f in {_family(c) for c in conds} if f"{f[0]}|{f[1]}" not in cache)
    if need:
        with ProcessPoolExecutor(min(procs, len(need))) as ex:
            for f, r in zip(need, ex.map(_calibrate_job, need), strict=True):
                cache[f"{f[0]}|{f[1]}"] = r
    if need or (base is not None and not path.exists()):  # a run directory always records what it used
        path.write_text(json.dumps(cache, indent=1, sort_keys=True))
    return cache


def _calibrate_job(fam: tuple[str, int]) -> dict:
    name, n = fam
    c = condition(n=n, topology=name if not name.startswith("D:") else "modular")
    steps = 500 if n <= 10000 else 300
    t0 = time.time()
    r = calibrate_gain(_builder(c, name), steps=steps, iters=9 if n <= 10000 else 6)
    r["seconds"] = round(time.time() - t0, 1)
    return r


# ------------------------------------------------------------------------------------------------ world
def _sets(h) -> dict[str, SetSpec]:
    sets: dict[str, SetSpec] = {}
    nz = h.n_clusters(1)
    for r in range(nz):
        sets[f"Z{r}"] = SetSpec(address=h.address(1, r))
        sets[f"BZ{r}"] = SetSpec(boundary_of=f"Z{r}")
    kids2 = {r: [k for k in range(h.n_clusters(2)) if h.parents[2][k] == r] for r in range(nz)}
    anc3 = h.parents[2][h.parents[3]]
    kids3 = {r: [k for k in range(h.n_clusters(3)) if anc3[k] == r] for r in range(nz)}
    for r in range(32):
        rr = r % nz
        for j in range(4):
            if kids2[rr]:
                sets[f"Q{r * 4 + j}"] = SetSpec(address=h.address(2, kids2[rr][j % len(kids2[rr])]))
        for j in range(16):
            if kids3[rr]:
                sets[f"L{r * 16 + j}"] = SetSpec(address=h.address(3, kids3[rr][j % len(kids3[rr])]))
        if r >= nz:
            sets[f"Z{r}"] = sets[f"Z{rr}"]
            sets[f"BZ{r}"] = SetSpec(boundary_of=f"Z{rr}")
    sets["R"] = SetSpec(address=h.address(1, 0))
    return sets


def build(c: dict, engine_seed: int, gains: dict, letter: str = "C", revert_at: int | None = None):
    """World + reasoning loop for one run. Returns (loop, world, spec, info)."""
    fam = _family(c)
    cal = gains[f"{fam[0]}|{fam[1]}"]
    fv = c.get("flag_variants")
    run_flags = dict(c.get("flags") or {})
    if fv is not None:  # runtime-variant study: the letter names a flag set; no reasoning layer
        run_flags = {**run_flags, **fv.get(letter, {})}
    rate, input_factor = MUTATION[c["mutation"]]
    base = Params()
    params = Params(gain=cal["gain"], input_rate=base.input_rate * input_factor)
    if c["disconnection"]:
        asm = disconnection_structure(c["disconnection"], c["n"], c["gen_seed"], params)
    elif c["return"]:
        asm = apply_return_structure(topology("modular", c["n"], c["gen_seed"], params), c["return"], c["gen_seed"])
    else:
        asm = topology(c["topology"], c["n"], c["gen_seed"], params, p_in=c.get("p_in"))
    st = asm.state
    h = _hierarchy(st, c)
    region = np.flatnonzero(h.labels[1] == 0).astype(np.int32)
    target1 = np.flatnonzero(h.labels[1] == 1).astype(np.int32)
    apply_memory_regime(asm, c["memory"], c["gen_seed"], region, h.labels[3], target1)
    spec = generate(c["structure"], c["size"], c["gen_seed"], c["coupling"], regions=32)
    if c.get("cluster_memory"):  # clusters with different memory persistence (cluster k owns regions r % nc == k)
        nc = spec["clusters"]
        per = [0.99 if k % 2 == 0 else 0.3 for k in range(nc)]
        z = h.labels[1] % nc
        st.base_mem_decay[:] = st.mem_decay[:] = np.asarray(per)[z]
    # the world skeleton is built here, not from a generator/explicit spec, so the scenario is constructed directly
    sc = Scenario.model_construct(name=c["id"], description="", seed=engine_seed, params={}, generator=None,
                                  explicit=None, sets=_sets(h), boundaries={}, frozen=[], drivers=[], practice=None)
    eng = Engine(st, engine_seed, checkpoint_every=0, flags=Flags.from_dict(run_flags))
    world = World(sc, eng, h, {})
    targets = sorted({e["target"] for it in spec["items"] for e in it["effects"]})
    target_nodes = np.unique(np.concatenate([world.resolve(t.replace("BZ", "Z"), "nodes") for t in targets])) \
        if targets else np.zeros(0, np.int32)
    items: list = []
    for wi in asm.world_items:
        items.append(MemoryCondition(tuple(int(i) for i in wi["nodes"]), wi.get("decay"), wi.get("coupling")))
    if rate:
        items.append(Mutation(tuple(range(st.n)), rate))
    addr = c["address"]
    if addr != "stable":
        tz = sorted({t.replace("BZ", "Z") for t in targets if t.startswith(("Z", "BZ"))})
        tn = [world.resolve(t, "nodes") for t in tz]
        if addr == "partially_unstable" and tn:
            items.append(Mutation(tuple(np.unique(np.concatenate(tn[::2])).tolist()), 0.002))
        elif addr == "highly_unstable" and tn:
            items.append(Mutation(tuple(np.unique(np.concatenate(tn)).tolist()), 0.01))
        elif addr == "locally_stable_globally_unstable":
            rest = np.setdiff1d(np.arange(st.n), target_nodes)
            items.append(Mutation(tuple(rest.tolist()), 0.01))
    eng.base_overlay = items
    eng.set_overlay([])
    eng.log.clear()
    H = c["horizon"]
    dyn = spec["dynamic"]
    edits = []
    if dyn["record_loss"]:
        edits = [(int(0.4 * H), Edit("lose_records")), (int(0.7 * H), Edit("restore_records"))]
    cfg = LoopConfig(representation="none" if letter == "A" else VARIANT_NAMES.get(letter, letter), check_every=10,
                     enabling=copy.deepcopy(ENABLING) if c["enabling"] else [], reasoning_from=c["reasoning_from"],
                     groundings=[], light=True, edits=edits,
                     interface_churn={"from": c["reasoning_from"], "every": 3, "seed": engine_seed}
                     if dyn["record_fragmentation"] else None,
                     triggers=trigger_set(tuple(c["triggers"]), spec, record_region="R")
                     if (letter != "A" and (c["triggers"] or dyn["memory_grounding"])) else None)
    if fv is not None:
        cfg.representation, cfg.triggers, cfg.enabling, cfg.edits, cfg.interface_churn = "none", None, [], [], None
        rep = None
    else:
        rep = build_variant(letter, spec)
    loop = ReasonLoop(world, {}, cfg, rep=rep)
    lab3 = h.labels[3]
    tmask = np.zeros(st.n)
    tmask[target_nodes] = 1.0
    local_target_share = np.bincount(lab3, tmask, minlength=h.n_clusters(3)) / np.maximum(
        np.bincount(lab3, minlength=h.n_clusters(3)), 1)
    info = {"gain": cal["gain"], "calibrated_activity": cal["activity"], "reached": cal.get("reached", True),
            "connections": int(st.alive.sum()), "target_nodes": int(len(target_nodes)),
            "world_items": [type(i).__name__ for i in items], "revert_at": revert_at,
            "local_target_share": np.round(local_target_share, 3).tolist(), "clusters": spec["clusters"],
            "flags": run_flags}
    return loop, world, spec, info, target_nodes


_HCACHE: dict[str, object] = {}


def _hierarchy(st, c: dict):
    """The hierarchy depends only on the initial connections: cached per world (process-local)."""
    import hashlib
    m = st.alive
    key = hashlib.sha1(np.ascontiguousarray(st.src[m]).tobytes() + np.ascontiguousarray(st.dst[m]).tobytes()).hexdigest()
    if key not in _HCACHE:
        if len(_HCACHE) > 4:
            _HCACHE.clear()
        _HCACHE[key] = build_hierarchy(symmetric_adjacency(st.src[m], st.dst[m], st.n))
    return _HCACHE[key]


def realized_coupling(s) -> dict:
    a = s.alive
    return {"threshold_shift": float(np.abs(np.log(np.maximum(s.theta_mod, 1e-9))).mean()),
            "gated_share": float((s.gate_mod[a] != 1.0).mean()) if a.any() else 0.0,
            "frozen_share": float(s.frozen.mean()),
            "memory_modified_share": float((s.mem_decay != s.base_mem_decay).mean()),
            "mutation_rate": float(s.mutation.mean())}


# ------------------------------------------------------------------------------------------------ one run
def run(c: dict, letter: str, engine_seed: int, gains: dict, revert_at: int | None = None, on_frame=None,
        keep_frames: bool = False, configure=None, per_step=None) -> dict:
    """``configure(loop, spec)`` may adjust the loop after it is built; ``per_step(loop, spec)`` runs before every
    step (both optional; used by control conditions such as open-loop replay and memoryless revision)."""
    t_build = time.perf_counter()
    loop, world, spec, info, target = build(c, engine_seed, gains, letter, revert_at)
    if configure is not None:
        configure(loop, spec)
    t_build = time.perf_counter() - t_build
    s = world.state
    H = c["horizon"]
    win = max(1, H // WINDOWS)
    obs = MultiScaleObserver(s.n, win, sample_every=max(1, min(5, win // 2)), target=target if len(target) else None,
                             keep_frames=keep_frames, macro_labels=world.hierarchy.labels[0])
    labels = labels_for(world.hierarchy)
    seg_len = H // SEGMENTS
    per_seg = WINDOWS // SEGMENTS
    rng = np.random.default_rng(c["gen_seed"])
    sample = np.sort(rng.permutation(s.n)[:NODE_SAMPLE])
    seg: dict[str, list[np.ndarray]] = {r: [] for r in ("node", "local", "meso", "macro")}
    gseg: list[np.ndarray] = []
    acc: dict[str, np.ndarray] = {}
    gacc: list[np.ndarray] = []
    coupling: list[dict] = []
    loop_time = 0.0
    t0 = time.perf_counter()
    w = 0
    sched = _world_schedule(c, world, spec, H)
    for _ in range(H):
        if revert_at is not None and s.t == revert_at and loop.rep is not None:
            revert_to_reference(loop.rep)
        if s.t in sched:
            _apply_world_event(world, sched[s.t])
        if per_step is not None:
            per_step(loop, spec)
        a = time.perf_counter()
        d = loop.step()
        b = time.perf_counter()
        loop_time += b - a
        fr = obs.observe(d, s)
        if s.t % 10 == 0 and s.t >= c["reasoning_from"]:
            coupling.append(realized_coupling(s))
        if fr is None:
            continue
        for r in ("node", "local", "meso", "macro"):
            v = fr.node[:, sample] if r == "node" else scale_values(fr.node, labels, r)
            acc[r] = acc.get(r, 0) + v
        gacc.append(np.array([fr.glob[k] for k in GLOBAL_KEYS]))
        if on_frame is not None:
            on_frame(w, fr)
        w += 1
        if w % per_seg == 0:
            for r in acc:
                seg[r].append((acc[r] / per_seg).astype(np.float32))
            gseg.append(np.mean(gacc, axis=0))
            acc, gacc = {}, []
    total = time.perf_counter() - t0
    del seg_len
    tl = loop.timeline
    out = {
        "letter": letter, "seed": engine_seed, "info": info,
        "seg": {r: np.stack(v) for r, v in seg.items()}, "gseg": np.stack(gseg),
        "exact": np.array(obs.exact), "exact_macro": np.array(obs.exact_macro),
        "exact_target": np.array(obs.exact_target) if obs.exact_target else None,
        "fps": [f.fingerprint for f in obs.frames] if keep_frames else None,
        "final_fp": world.engine.fingerprint(),
        "effects": [r["effects"] for r in tl], "levels": [r.get("levels", "") for r in tl],
        "check_t": [r["t"] for r in tl], "phases": [r["phase"] for r in tl],
        "revisions": loop.revisions, "effect_changes": loop.effect_changes[:200],
        "fired": len(loop.cfg.triggers.fired) if loop.cfg.triggers is not None else 0,
        "fired_kinds": _count([f[1] for f in loop.cfg.triggers.fired]) if loop.cfg.triggers is not None else {},
        "coupling": {k: float(np.mean([x[k] for x in coupling])) for k in coupling[0]} if coupling else {},
        "ms_per_step": 1000 * total / H, "loop_ms_per_step": 1000 * loop_time / H, "build_s": t_build,
        "frames": obs.frames if keep_frames else None,
        "labels": labels if keep_frames else None,
        "loop": loop if configure is not None else None,
    }
    return out


def _world_schedule(c: dict, world, spec: dict, H: int) -> dict[int, dict]:
    out = {}
    for ev in c.get("world_schedule") or ():
        out[int(ev["t"] * H)] = {**ev, "nc": spec["clusters"]}
    if any(ev["op"] == "open" for ev in c.get("world_schedule") or ()):  # merge: start closed
        _apply_world_event(world, {"op": "close", "nc": spec["clusters"]})
    return out


def _between_clusters(world, nc: int) -> np.ndarray:
    s = world.state
    z = world.hierarchy.labels[1] % max(nc, 1)
    return np.flatnonzero(s.alive & (z[s.src] != z[s.dst])).astype(np.int32)


def _apply_world_event(world, ev: dict) -> None:
    """World-side structural change between the regions of different reasoning clusters (not a reasoning edit):
    close (permeability 0.02), open (remove that gate), unstable (connection mutation 0.01 at the borders)."""
    eng = world.engine
    base = [i for i in eng.base_overlay if not getattr(i, "_cluster_border", False)]
    e = _between_clusters(world, ev["nc"])
    if ev["op"] == "close":
        g = Gate(tuple(e.tolist()), 0.02)
        object.__setattr__(g, "_cluster_border", True)
        base.append(g)
    elif ev["op"] == "unstable":
        nodes = np.unique(np.concatenate([world.state.src[e], world.state.dst[e]]))
        mu = Mutation(tuple(nodes.tolist()), 0.01)
        object.__setattr__(mu, "_cluster_border", True)
        base.append(mu)
    eng.base_overlay = base
    eng.set_overlay(list(eng.overlay))


def _count(xs: list[str]) -> dict:
    out: dict[str, int] = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


# ------------------------------------------------------------------------------------------------ pair comparison
def _first_diff(a: np.ndarray, b: np.ndarray) -> int | None:
    if a is None or b is None:
        return None
    m = min(len(a), len(b))
    ne: np.ndarray | list = np.flatnonzero(np.any(np.atleast_2d(a[:m] != b[:m]).reshape(m, -1), axis=1)) if m else []
    return int(ne[0]) + 1 if len(ne) else None


def compare(x: dict, ref: dict, dist: dict) -> dict:
    """Exact and schedule-level comparison of one run with the reference run of the same seed."""
    em, rm = x["exact_macro"], ref["exact_macro"]
    macro_onsets = []
    if len(em) and len(rm):
        for k in range(em.shape[1]):
            macro_onsets.append(_first_diff(em[:, k], rm[:, k]))
    eff_a, eff_b = x["effects"], ref["effects"]
    lv_a, lv_b = x["levels"], ref["levels"]
    n = min(len(eff_a), len(eff_b))
    diff_checks = [eff_a[i] != eff_b[i] for i in range(n)]
    lvl_checks = [lv_a[i] != lv_b[i] for i in range(n)]
    t = ref["check_t"]
    return {
        "identical": x["final_fp"] == ref["final_fp"] and _first_diff(x["exact"], ref["exact"]) is None,
        "first_step": _first_diff(x["exact"], ref["exact"]),
        "first_step_target": _first_diff(x["exact_target"], ref["exact_target"]),
        "macro_onsets": macro_onsets,
        "intervention_checks_differing": float(np.mean(diff_checks)) if n else 0.0,
        "first_intervention_difference": next((t[i] for i in range(n) if diff_checks[i]), None),
        "first_level_difference": next((t[i] for i in range(n) if lvl_checks[i]), None),
        "dist": {r: np.asarray(v, dtype=np.float32) for r, v in dist.items()},
    }


def seed_job(args: tuple) -> dict:
    """All runs of one condition for one engine seed. Returns per-variant summaries + comparisons with C."""
    c, seed, gains = args
    ref_frames: list = []
    ref = run(c, "C", seed, gains, keep_frames=True)
    ref_frames = ref.pop("frames")
    labels = ref.pop("labels")

    def dist_collector():
        store: dict[str, list] = {r: [] for r in ("node", "local", "meso", "macro", "global")}

        def cb(w: int, fr) -> None:
            rf = ref_frames[w]
            for r in ("node", "local", "meso", "macro"):
                a = fr.node if r == "node" else scale_values(fr.node, labels, r)
                b = rf.node if r == "node" else scale_values(rf.node, labels, r)
                store[r].append(window_distance(a, b))
            ga = np.array([fr.glob[k] for k in GLOBAL_KEYS])
            gb = np.array([rf.glob[k] for k in GLOBAL_KEYS])
            store["global"].append(np.abs(ga - gb) / ((np.abs(ga) + np.abs(gb)) / 2 + 1e-12))
        return store, cb

    out: dict = {"seed": seed, "runs": {}, "timing": {}}
    jobs = [("C~", "C", seed + NOISE_OFFSET, None)] + [(v, v, seed, None) for v in c["variants"] if v != "C"]
    jobs += [(f"{v}@rev", v, seed, int(0.5 * c["horizon"])) for v in c.get("revert", ())]
    ref_small = {k: v for k, v in ref.items() if k not in ("fps",)}
    out["runs"]["C"] = _strip(ref_small)
    for key, letter, s, rev in jobs:
        store, cb = dist_collector()
        x = run(c, letter, s, gains, revert_at=rev, on_frame=cb)
        cmp_ = compare(x, ref, store)
        out["runs"][key] = _strip(x) | {"cmp": cmp_}
    return out


def _strip(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in ("frames", "exact", "exact_macro", "exact_target", "fps", "loop")}
