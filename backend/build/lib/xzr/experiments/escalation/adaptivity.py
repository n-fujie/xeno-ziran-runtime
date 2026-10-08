"""World-responsive revision: does it create real adaptivity?

All ten revision triggers are active in the reference world at three noise levels (no extra noise; high state
noise; mixed topology + state noise). Per engine seed:

    C   closed loop: persistent reasoning state + triggers (reference)
    S   static: the same structure without triggers
    M   memoryless: triggers act on a freshly built structure at every check (revisions do not persist)
    R   open loop: the intervention schedule recorded by C in *another* world seed, replayed without reasoning
    A   no reasoning layer
    C~  noise replicate of C (other random stream)

Measured: schedule divergence across world seeds (adaptivity), response of the triggering metric after a firing
versus after random checks of the same region (responsiveness), in-band share of bound regions' activity
(|z| ≤ 1 against the pre-reasoning baseline; control precision), multi-resolution world effects of C against each
control, and whether adaptivity is harmful under noise (in-band share C − R).
"""

from __future__ import annotations

import time

import numpy as np

from ...reasonlab.structures import build_variant
from ...reasonlab.triggers import KINDS
from ...shapes.multiscale import GLOBAL_KEYS, scale_values, window_distance
from .analysis import analyse
from .harness import RESULTS, _strip, calibrations, compare, condition, run
from .runner import SEED0, _jsonable, provenance

NOISE = {"none": "low", "state": "high_state", "mixed": "mixed"}
SCHEDULE_OFFSET = 500


def conditions() -> list[dict]:
    out = []
    for name, mut in NOISE.items():
        c = condition(id=f"adaptivity:{name}", mutation=mut, triggers=KINDS, variants=("C", "S", "M", "R", "A"))
        c["factor"], c["level"] = "noise", name
        out.append(c)
    return out


class _Recorder:
    """Per-check activity of the bound regions (read from the loop's probe) for in-band control measures."""

    def __init__(self, regions: list[str]):
        self.regions = regions
        self.rows: list[tuple[int, list[float]]] = []

    def __call__(self, loop, spec) -> None:
        t = loop.world.state.t
        if t % 10 == 9:  # the next step is a check step: record the probe as the check will see it
            self.rows.append((t + 1, [loop.probe.value("activity", r) for r in self.regions]))


def _bound_regions(spec: dict) -> list[str]:
    regs = sorted({e["target"].replace("BZ", "Z") for it in spec["items"] for e in it["effects"]
                   if e["target"].startswith(("Z", "BZ"))}, key=lambda x: int(x[1:]))
    return regs


def _in_band(rows: list, reasoning_from: int) -> tuple[float, float]:
    a = np.array([r[1] for r in rows])
    t = np.array([r[0] for r in rows])
    pre = a[t < reasoning_from]
    mu, sd = pre.mean(0), pre.std(0) + 1e-9 + 0.05 * np.abs(pre.mean(0))
    z = (a[t >= reasoning_from] - mu) / sd
    return float((np.abs(z) <= 1).mean()), float(np.abs(z).mean())


def _response(trace: list, fired: list, rng: np.random.Generator, horizon_checks: int = 5) -> dict:
    """Share of firings after which the region's |activity z| decreased by ≥ 0.5 within 5 checks, versus the same
    share at random checks of the same regions (control)."""
    if not trace or not fired:
        return {"firings": len(fired), "responded": None, "control": None}
    by_t = {t: z for _, t, z in trace}
    ts = sorted(by_t)
    idx = {t: k for k, t in enumerate(ts)}

    def moved(t: int, r: str) -> bool | None:
        k = idx.get(t)
        if k is None or k + horizon_checks >= len(ts) or r not in by_t[t]:
            return None
        z0 = abs(by_t[t][r])
        z1 = min(abs(by_t[ts[k + j]][r]) for j in range(1, horizon_checks + 1))
        return z1 <= z0 - 0.5

    got = [g for g in (moved(t, r) for t, _k, r, _op in fired) if g is not None]
    ctrl = []
    for _t, _k, r, _op in fired:
        tt = ts[int(rng.integers(0, max(len(ts) - horizon_checks - 1, 1)))]
        m = moved(tt, r)
        if m is not None:
            ctrl.append(m)
    return {"firings": len(fired), "responded": float(np.mean(got)) if got else None,
            "control": float(np.mean(ctrl)) if ctrl else None}


def seed_job(args: tuple) -> dict:
    c, seed, gains = args
    t0 = time.time()
    trace_holder: dict = {}

    def cfg_trace(loop, spec):
        loop.cfg.triggers.trace = []
        trace_holder["loop"] = loop

    spec_regions: dict = {}

    def recorder_for(loop, spec):
        if "rec" not in spec_regions:
            spec_regions["regions"] = _bound_regions(spec)
        return _Recorder(spec_regions["regions"])

    recs: dict[str, _Recorder] = {}

    def with_rec(key, extra=None):
        def configure(loop, spec):
            recs[key] = recorder_for(loop, spec)
            if extra:
                extra(loop, spec)

        def per_step(loop, spec):
            recs[key](loop, spec)
        return configure, per_step

    conf, ps = with_rec("C", cfg_trace)
    ref = run(c, "C", seed, gains, keep_frames=True, configure=conf, per_step=ps)
    frames, labels = ref.pop("frames"), ref.pop("labels")
    loop_c = ref.pop("loop")
    trace = loop_c.cfg.triggers.trace
    fired = list(loop_c.cfg.triggers.fired)

    # the schedule another world seed produced (for the open-loop control)
    def cfg_full(loop, spec):
        loop.cfg.light = False
    other = run(c, "C", seed + SCHEDULE_OFFSET, gains, configure=cfg_full)
    schedule = [(t, list(items)) for t, items in other.pop("loop").overlay_changes]

    def cfg_replay(loop, spec):
        loop.rep = None
        loop.cfg.triggers = None
        loop.cfg.representation = "replay"
        loop.cfg.replay = schedule
        for at, items in schedule:
            if at == loop.world.state.t:
                loop._replay_apply(items)

    def cfg_static(loop, spec):
        loop.cfg.triggers = None

    def ps_memoryless(loop, spec):
        s = loop.world.state
        if (s.t + 1) % 10 == 0 and s.t + 1 >= c["reasoning_from"]:
            loop.rep = build_variant("C", spec)

    variants = {"C~": ("C", seed + 1000, None, None), "S": ("C", seed, cfg_static, None),
                "M": ("C", seed, None, ps_memoryless), "R": ("C", seed, cfg_replay, None), "A": ("A", seed, None, None)}
    out = {"seed": seed, "runs": {"C": _strip(ref)}, "extra": {}}
    rng = np.random.default_rng(seed)
    out["extra"]["C"] = {"in_band": _in_band(recs["C"].rows, c["reasoning_from"]),
                         "response": _response(trace, fired, rng), "fired_kinds": ref["fired_kinds"]}
    for key, (letter, s, cfg_fn, step_fn) in variants.items():
        store: dict[str, list] = {r: [] for r in ("node", "local", "meso", "macro", "global")}

        def cb(w, fr, store=store):
            rf = frames[w]
            for r in ("node", "local", "meso", "macro"):
                a = fr.node if r == "node" else scale_values(fr.node, labels, r)
                b = rf.node if r == "node" else scale_values(rf.node, labels, r)
                store[r].append(window_distance(a, b))
            ga = np.array([fr.glob[k] for k in GLOBAL_KEYS])
            gb = np.array([rf.glob[k] for k in GLOBAL_KEYS])
            store["global"].append(np.abs(ga - gb) / ((np.abs(ga) + np.abs(gb)) / 2 + 1e-12))

        conf, ps0 = with_rec(key, cfg_fn)

        def per_step(loop, spec, ps0=ps0, step_fn=step_fn):
            ps0(loop, spec)
            if step_fn is not None:
                step_fn(loop, spec)

        x = run(c, letter, s, gains, on_frame=cb, configure=conf, per_step=per_step)
        lp = x.pop("loop")
        cm = compare(x, {**ref, "exact": ref["exact"]}, store)
        out["runs"][key] = _strip(x) | {"cmp": cm}
        ex: dict = {"in_band": _in_band(recs[key].rows, c["reasoning_from"])}
        if key == "M" and lp.cfg.triggers is not None:
            ex["fired"] = len(lp.cfg.triggers.fired)
        out["extra"][key] = ex
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def main(procs: int = 7) -> dict:
    import json
    from concurrent.futures import ProcessPoolExecutor
    conds = conditions()
    gains = calibrations(conds, procs)
    path = RESULTS / "adaptivity.json"
    doc = json.loads(path.read_text()) if path.exists() else {"conditions": {}}
    for c in conds:
        if c["id"] in doc["conditions"]:
            continue
        with ProcessPoolExecutor(procs) as ex:
            jobs = list(ex.map(seed_job, [(c, SEED0 + k, gains) for k in range(c["seeds"])]))
        a = analyse(c, jobs)
        keys = ("C", "S", "M", "R", "A")
        a["adaptivity"] = {k: _adapt([j["runs"][k]["effects"] for j in jobs]) for k in keys}
        a["in_band"] = {k: {"share_mean": round(float(np.mean([j["extra"][k]["in_band"][0] for j in jobs])), 4),
                            "mean_abs_z": round(float(np.mean([j["extra"][k]["in_band"][1] for j in jobs])), 4),
                            "by_seed": [round(j["extra"][k]["in_band"][0], 4) for j in jobs]} for k in keys}
        diffs = {k: np.array([j["extra"]["C"]["in_band"][0] - j["extra"][k]["in_band"][0] for j in jobs])
                 for k in ("S", "M", "R", "A")}
        a["in_band_paired"] = {f"C-{k}": {"mean": round(float(d.mean()), 4),
                                          "t": round(float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)) + 1e-12)), 2)}
                               for k, d in diffs.items()}
        resp = [j["extra"]["C"]["response"] for j in jobs]
        pairs = np.array([r["responded"] - r["control"] for r in resp
                          if r["responded"] is not None and r["control"] is not None])
        a["response"] = {"firings_mean": round(float(np.mean([r["firings"] for r in resp])), 2),
                         "responded": _mean([r["responded"] for r in resp]),
                         "control": _mean([r["control"] for r in resp]),
                         "paired_seeds": int(len(pairs)),
                         "paired_t": round(float(pairs.mean() / (pairs.std(ddof=1) / np.sqrt(len(pairs)) + 1e-12)), 2)
                         if len(pairs) > 2 else None}
        a["fired_kinds"] = _merge([j["extra"]["C"]["fired_kinds"] for j in jobs])
        a["provenance"] = {**provenance(), "experiment": "adaptivity", "condition": c["id"],
                           "engine_seeds": [j["seed"] for j in jobs]}
        doc["conditions"][c["id"]] = _jsonable(a)
        path.write_text(json.dumps(doc))
        print(c["id"], "done", flush=True)
    return doc


def _adapt(schedules: list[list[str]]) -> float:
    vals = [np.mean([a != b for a, b in zip(schedules[i], schedules[j], strict=False)])
            for i in range(len(schedules)) for j in range(i + 1, len(schedules))]
    return round(float(np.mean(vals)), 4) if vals else 0.0


def _mean(xs: list) -> float | None:
    v = [x for x in xs if x is not None]
    return round(float(np.mean(v)), 4) if v else None


def _merge(ds: list[dict]) -> dict:
    out: dict[str, float] = {}
    for d in ds:
        for k, v in d.items():
            out[k] = out.get(k, 0) + v / len(ds)
    return {k: round(v, 2) for k, v in out.items()}
