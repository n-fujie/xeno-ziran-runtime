"""Environments of a study: one function per environment kind that executes one (arm, seed) and returns a run record.

hpo-world        the runtime world observed and acted on by an HPO field (xzr.hpo), optionally reconfigured between
                 epochs by a controller (static, rule-based recursive with optional meta-revision, or random with a
                 matched change budget), with protocol-specified changes of observation, boundary, scale, time window
                 and variables at chosen epochs. Records every change with the reachability it opened or closed, checks
                 those predictions against what the operations then did, and records history re-entry.
lab-population   the shared physical laboratory with a population of scientific systems (xzr.lab).

Nothing here changes the world except through the HPO field and the sandboxed reconfiguration.
"""

from __future__ import annotations

import copy
import resource
import sys
import time
from typing import Any

from ..hpo import reconfig
from ..hpo.experiments import HORIZON, WARMUP, clean, settings_for, trace
from ..hpo.field import Field, validate
from ..hpo.metarevision import MetaReviser
from ..hpo.metrics import measure
from ..hpo.reachability import delta, reachability
from ..hpo.world import NOISE_OFFSET, World, build_world

EPOCH = reconfig.EPOCH
RUN_SCHEMA = "xzr.studyrun/1"
DETECTOR_LIMITS = (
    "The shape detector computes fixed structural descriptors (ignition, branching, loops, reach, fragmentation, "
    "recurrence, ...) from the engine's delta stream. It does not interpret them; hierarchy-dependent descriptors "
    "can differ across platforms where the address hierarchy is not unique (disconnected sub-graphs). Its output is a "
    "measurement of the simulated state, not a statement about any philosophical theory."
)


def _rss_mb() -> float:
    """Peak resident set of this process (macOS reports bytes, Linux kilobytes)."""
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / (1 << 20) if sys.platform == "darwin" else r / 1024, 1)


def _warm(env: dict, gen: int, seed: int) -> World:
    w = build_world(int(env.get("world", {}).get("n", 800)), gen, seed, regime=env.get("world", {}).get("regime", "intermittent"))
    for _ in range(int(env.get("warmup", WARMUP))):
        w.step()
    return w


def arm_settings(arm: dict, env: dict) -> dict | None:
    """The HPO settings of an arm: a named HPO-002 condition (``condition``) and/or explicit ``settings`` on top."""
    base = {"warmup": int(env.get("warmup", WARMUP)), "horizon": int(env.get("horizon", HORIZON))}
    s: dict | None
    if arm.get("condition"):
        s = settings_for(arm["condition"], base)
    else:
        s = dict(base)
    if s is None:
        return None
    explicit = copy.deepcopy(arm.get("settings") or {})
    for k, v in explicit.items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k] = {**s[k], **v}
        else:
            s[k] = v
    s["warmup"], s["horizon"] = base["warmup"], base["horizon"]
    validate(s)
    return s


def build_controller(arm: dict, seed: int, budget: list[int] | None = None) -> reconfig.Controller:
    c = arm.get("controller", {})
    mode = c.get("mode", "static")
    meta = MetaReviser() if c.get("meta") else None
    return reconfig.Controller(
        mode,
        seed,
        budget=budget,
        trace_reachability=bool(c.get("trace_reachability", mode != "static")),
        meta=meta,
        authority=c.get("authority"),
        max_changes_per_epoch=c.get("max_changes_per_epoch"),
    )


def _acts_per_epoch(f: Field, epochs: int) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for e in f.history.events:
        if e["type"] == "act":
            ep = (e["t"] - f.t0) // EPOCH
            if 0 <= ep < epochs:
                out.setdefault(e["source"], [0] * epochs)[ep] += 1
    return out


def reachability_check(changes: list[dict], acts: dict[str, list[int]], epochs: int) -> dict:
    """Compare each change's predicted opening / closing of an operation with what the operation did in the next epoch.

    ``opened`` predicted: the operation is able to observe what it needs. Success means it acted at least once in the next
    epoch; an opened operation that did not act is *opened, not used* (opening is not success). ``closed`` predicted: the
    operation cannot observe an essential channel; consistent means it did not act in the next epoch.
    """
    rows = {"opened": {"n": 0, "acted": 0}, "closed": {"n": 0, "silent": 0}, "skipped_last_epoch": 0}
    for ch in changes:
        r = ch.get("reachability")
        if not r:
            continue
        ep = ch["epoch"] + 1
        for kind, key in (("opened", "runnable_opened"), ("closed", "runnable_closed")):
            for oid in r[key]:
                if ep >= epochs:
                    rows["skipped_last_epoch"] += 1
                    continue
                n = acts.get(oid, [0] * epochs)[ep]
                rows[kind]["n"] += 1
                if kind == "opened":
                    rows["opened"]["acted"] += int(n > 0)
                else:
                    rows["closed"]["silent"] += int(n == 0)
    rows["opened"]["rate"] = rows["opened"]["acted"] / rows["opened"]["n"] if rows["opened"]["n"] else None
    rows["closed"]["rate"] = rows["closed"]["silent"] / rows["closed"]["n"] if rows["closed"]["n"] else None
    return rows


def _history_reentry(f: Field) -> dict:
    ev = f.history.events
    rein = [e["id"] for e in ev if e["type"] == "reinsert"]
    caused = {c for e in ev for c in e["causes"]}
    down = [i for i in rein if i in caused]
    return {
        "reinsertions": len(rein),
        "with_downstream_event": len(down),
        "downstream_share": len(down) / len(rein) if rein else None,
        "enabled": bool(f.s["history"]["reinsert"]),
    }


def _tap_detector(w: World, every: int = 10):
    from ..shapes.detector import ShapeDetector

    det = ShapeDetector(w.h, graph_every=every)
    step = w.engine.step
    count = [0]

    def tapped():
        d = step()
        det.observe(d, w.state)
        count[0] += 1
        if count[0] % every == 0:
            det.graph_pass(w.state, w.t)
        return d

    w.engine.step = tapped  # type: ignore[method-assign]
    return det


def run_hpo_world(doc: dict, arm: dict, gen: int, seed: int) -> dict:
    env = doc["environment"]
    horizon = int(env.get("horizon", HORIZON))
    t_wall, t_cpu = time.time(), time.process_time()
    base = _warm(env, gen, seed)
    ref = base.fork().track_rng()
    for _ in range(horizon):
        ref.step()
    settings = arm_settings(arm, env)
    rec: dict[str, Any] = {"schema": RUN_SCHEMA, "arm": arm["name"], "gen": gen, "seed": seed, "status": "ok"}
    if settings is None:  # the no-HPO reference arm (R0): world measures only
        from ..hpo.metrics import world_measure

        rec["metrics"] = world_measure(ref)
        rec.update(controller=None, protocol_changes=[], reachability_check=None, history_reentry=None)
    else:
        w = base.fork(endogenous_seed=seed + NOISE_OFFSET if arm.get("noise_branch") else None).track_rng()
        det = _tap_detector(w) if env.get("detect_shapes") else None
        f = Field(w, settings, seed, keep_states=False)
        budget = arm.get("controller", {}).get("random_budget")
        match = arm.get("controller", {}).get("match_budget_of")
        if arm.get("controller", {}).get("mode") == "random" and match:
            other = next(a for a in doc["arms"] if a["name"] == match)
            if other.get("controller", {}).get("match_budget_of"):
                raise ValueError("match_budget_of must name an arm that does not itself match another")
            budget = run_hpo_world(doc, other, gen, seed)["controller"]["counts"]  # same number of changes per epoch
        ctl = build_controller(arm, seed, budget=budget)
        trace_reach = bool(arm.get("controller", {}).get("trace_reachability", ctl.mode != "static"))
        changes: list[dict] = []

        def protocol_change(ch: dict, epoch: int) -> None:
            before = reachability(f) if trace_reach else None
            try:
                eid = reconfig.apply(f, ch, [])
            except reconfig.SandboxError as e:  # impossible after validation, but a failure is recorded, never hidden
                changes.append({**ch, "epoch": epoch, "t": w.t, "source": "protocol", "rejected": str(e)})
                return
            r = {**ch, "event": eid, "t": w.t, "epoch": epoch, "source": "protocol"}
            if before is not None:
                r["reachability"] = delta(before, reachability(f))
            changes.append(r)

        for ch in arm.get("initial_changes", []):
            protocol_change(ch, -1)
        ctl.start(f)
        epochs = horizon // EPOCH
        by_epoch: dict[int, list[dict]] = {}
        for iv in arm.get("interventions", []):
            by_epoch.setdefault(int(iv["epoch"]), []).append(iv["change"])
        ran = 0
        for ep in range(epochs):
            f.run(EPOCH)
            ran = ep + 1
            if f.stopped_at is not None:
                break
            for ch in by_epoch.get(ep, []):
                protocol_change(ch, ep)
            if ep < epochs - 1:
                for r in ctl.end_epoch(f, ep):
                    changes.append({**r, "source": "controller"})
        rec["metrics"] = measure(f, ref)
        acts = _acts_per_epoch(f, epochs)
        rec["controller"] = {
            "mode": ctl.mode,
            "counts": ctl.counts,
            "trace": ctl.trace,
            "proposals": ctl.proposals,
            "rejected": ctl.rejected,
            "meta_trace": ctl.meta.trace if ctl.meta else [],
            "rules": ctl.rules.snapshot() if ctl.meta else None,
            "authority": sorted(ctl.authority) if ctl.authority is not None else None,
            "max_changes_per_epoch": ctl.max_changes_per_epoch,
        }
        rec["protocol_changes"] = [c for c in changes if c["source"] == "protocol"]
        rec["controller_changes"] = [c for c in changes if c["source"] == "controller"]
        rec["reachability_check"] = reachability_check(changes, acts, epochs) if trace_reach else None
        rec["history_reentry"] = _history_reentry(f)
        rec["epochs_run"] = ran
        rec["stopped_at"] = f.stopped_at
        rec["final_settings"] = {
            k: f.s[k] for k in ("catalog", "instruments", "order", "allocation", "history", "stop", "variables")
        }
        rec["causal_summary"] = f.history.summary()
        if env.get("keep_trace"):
            rec["trace"] = trace(f, 300)
        if det is not None:
            rec["shape_detection"] = {
                "transition_record": {"source": "engine step deltas", "steps": int(w.t - base.t)},
                "detector_output": det.summary(),
                "detector_limits": DETECTOR_LIMITS,
                "interpretation": None,
            }
    rec["wall_s"] = round(time.time() - t_wall, 4)
    rec["cpu_s"] = round(time.process_time() - t_cpu, 4)
    rec["peak_rss_mb"] = _rss_mb()
    return clean(rec)


def run_lab_population(doc: dict, arm: dict, gen: int, seed: int) -> dict:
    from ..lab.population import population
    from ..lab.record import LabRun

    env = doc["environment"]
    t_wall = time.time()
    pop = arm.get("population", {})
    systems = population(int(pop.get("n", 3)), capacities=bool(pop.get("capacities", True)))
    for s in systems:
        s.update({k: v for k, v in (pop.get("system_overrides") or {}).items()})
    steps = int(env.get("horizon", 120))
    r = LabRun({"gen_seed": gen, "seed": seed, "settings": None, "physics": True, "horizon": steps, "systems": systems})
    for _ in range(steps):
        r.step()
    rec = r.record()
    st = r.science.systems
    n = max(1, len(st))
    tot = lambda key: float(sum(s.stats[key] for s in st.values()))  # noqa: E731
    metrics = {
        "requests": tot("requests"),
        "completed": tot("completed"),
        "failed": tot("failed"),
        "denied": tot("denied"),
        "observed_outcomes": tot("observed_outcomes"),
        "unobserved_outcomes": tot("unobserved_outcomes"),
        "variables_adopted": float(sum(len(s.stats["variables_adopted"]) for s in st.values())),
        "window_changes": tot("window_changes"),
        "relocations": tot("relocations"),
        "isolations": tot("isolations"),
        "spent_per_system": tot("spent") / n,
        "true_gain_per_system": tot("true_gain") / n,
        "events": float(len(rec["events"])),
    }
    out = {
        "schema": RUN_SCHEMA,
        "arm": arm["name"],
        "gen": gen,
        "seed": seed,
        "status": "ok",
        "metrics": metrics,
        "controller": None,
        "protocol_changes": [],
        "reachability_check": None,
        "history_reentry": None,
        "population": {"n": len(st), "kinds": sorted({s.spec.kind for s in st.values()})},
        "fingerprint_last": rec["steps"][-1]["fingerprint"],
        "wall_s": round(time.time() - t_wall, 4),
        "peak_rss_mb": _rss_mb(),
    }
    return clean(out)


RUNNERS = {"hpo-world": run_hpo_world, "lab-population": run_lab_population}


def run_one(doc: dict, arm_name: str, gen: int, seed: int) -> dict:
    arm = next(a for a in doc["arms"] if a["name"] == arm_name)
    return RUNNERS[doc["environment"]["kind"]](doc, arm, gen, seed)
