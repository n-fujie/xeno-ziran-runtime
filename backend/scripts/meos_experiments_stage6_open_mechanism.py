"""Stage 6 follow-up: what happens at the closure of the three windows that were open at tick 330 (coupling 389, renewal stopped 384, Address 384).

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_open_mechanism.py     # about 6 minutes on 8 cores

Writes docs/ecosystem/experiments_stage6_open_mechanism.json with
  boundary        for each window, the ticks around its last effective tick and a sample of later ticks, seeds 1-10: the repaired run's A1 energy when the intervention is applied, the first tick A1 fires after it, the number of A1 fires in the
                  following 60 ticks, the latency of the first sustained ACTIVE stretch, whether the run is sustained-ACTIVE (W ticks) within 2W = 60 ticks of the intervention (a post-intervention period that is the same for every
                  intervention tick), and the outcome at the end of the run (tick 1200). ``tracked_ticks`` = 1200 - intervention tick.
  energy          the unrepaired coupling run: A1's energy (not rounded) around the tick it falls below A1's firing cost.
  upkeep_branch   a control that changes the *model* after a common history: the run is the same up to tick 300 (the damaged, collapsed state), then A1's upkeep is set to 0 and the same intervention is applied later;
                  and, for comparison, the control of the first version (upkeep 0 in the initial configuration, a different history).
The tick convention of the engine: an intervention scheduled at tick t is applied at the start of step t; A1's firing check in step t uses the energy at the end of step t-1; A1's upkeep is taken at the end of a step."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import repair6 as R
from xzr.meos import stage5_experiments as X5

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
H = 1200
W = R.W
SEEDS = tuple(range(1, 11))
WINDOWS = {  # the three windows that were open at tick 330 (stress, parts) and their last effective tick (from experiments_stage6_open_windows.json)
    "coupling": ("coupling gain 0.5", (("resource.pulse", 1.0, 0),)),
    "renewal stopped": ("renewal stopped", (("renewal.restart", 0.0, 0), ("resource.pulse", 1.0, 0))),
    "Address": ("Address partial 0.5", (("address.restore", 0.0, 0), ("resource.pulse", 1.0, 0))),
}
LATER = (400, 450, 500, 600, 800, 1000, 1100, 1140)


def _run(stress_id: str, parts: tuple, t: int, seed: int, branch_tick: int | None = None, initial_upkeep: float | None = None) -> dict:
    st = R.STRESSES[stress_id]
    reps: list[dict] = []
    for aid, mag, dur in parts:
        reps += R.build_action(aid, st, mag, t, dur)
    cfg = R.config(seed, H)
    if initial_upkeep is not None:
        cfg["entities"]["A1"]["upkeep"] = initial_upkeep
    r = E.Run(cfg, R.schedule(st, sorted(reps, key=lambda i: i["tick"])))
    energy_end: list[float] = [r.ent["A1"]["energy"]]
    fired: list[bool] = [False]
    status = [r.status["label"]]
    while True:
        if branch_tick is not None and r.t == branch_tick:
            r.cfg["entities"]["A1"]["upkeep"] = 0.0  # from the next step on (a change of the model after a common history)
        more = r.step()  # the step that reaches the horizon returns False after it has been taken: it is recorded too
        energy_end.append(r.ent["A1"]["energy"])
        fired.append(bool(r.ent["A1"]["fired_now"]))
        status.append(r.status["label"])
        if not more:
            break
    s = [f for f in status]
    out = R.outcome_at(s, H, t)
    ref = R.reference(seed, H)
    exhausted = r.traces["resource_total"][H - 1] < 0.25 * (ref["traces"]["resource_total"][H - 1] or 1.0)
    stretches = [(a, b) for a, b in R._runs(s, t, min(H, t + 2 * W), "ACTIVE") if b - a >= W]
    first_fire = next((k for k in range(t, len(fired)) if fired[k]), None)
    return {"t": t, "seed": seed, "tracked_ticks": H - t, "a1_energy_at_start_of_t": round(energy_end[t - 1], 4), "first_a1_fire": first_fire, "a1_fires_in_60": sum(fired[t:t + 60]), "a1_energy_after_first_fire": round(energy_end[first_fire], 4) if first_fire is not None else None,
            "sustained_within_60": bool(stretches), "latency": out["latency"], "recovered_at_1200": bool(out["success"]) and not exhausted, "final_status": s[-1]}


def _job(a: tuple) -> dict:
    name, stress_id, parts, t, seed, branch, init = a
    return {"window": name, "branch_tick": branch, "initial_upkeep": init, **_run(stress_id, parts, t, seed, branch, init)}


def _summ(rows: list[dict]) -> dict:
    lat = [r["latency"] for r in rows if r["latency"] is not None]
    en = [r["a1_energy_at_start_of_t"] for r in rows]
    return {"seeds": len(rows), "sustained_within_60": sum(r["sustained_within_60"] for r in rows), "recovered_at_1200": sum(r["recovered_at_1200"] for r in rows), "tracked_ticks": rows[0]["tracked_ticks"],
            "a1_energy_at_start_of_t": [min(en), max(en)], "median_latency": statistics.median(lat) if lat else None, "max_latency": max(lat) if lat else None, "first_a1_fire_median": statistics.median([r["first_a1_fire"] for r in rows if r["first_a1_fire"] is not None]) if any(r["first_a1_fire"] is not None for r in rows) else None,
            "a1_fires_in_60_median": statistics.median(r["a1_fires_in_60"] for r in rows), "final_status": sorted({r["final_status"] for r in rows})}


def main() -> None:
    op = json.loads((DOCS / "experiments_stage6_open_windows.json").read_text())
    last = {w["stress"]: w["latest_effective_tick"] for w in op["windows"]}
    jobs = []
    for name, (sid, parts) in WINDOWS.items():
        ticks = sorted({*range(last[sid] - 4, last[sid] + 18), *LATER})
        jobs += [(name, sid, parts, t, sd, None, None) for t in ticks for sd in SEEDS]
    rows = X5.pmap(_job, jobs, None, chunksize=4)
    boundary: dict = {}
    for name in WINDOWS:
        by: dict[int, list[dict]] = {}
        for r in rows:
            if r["window"] == name:
                by.setdefault(r["t"], []).append(r)
        boundary[name] = {"stress": WINDOWS[name][0], "last_effective_tick": last[WINDOWS[name][0]], "by_tick": {str(t): _summ(v) for t, v in sorted(by.items())}}
    # the unrepaired coupling run: A1's energy, not rounded, around the tick it falls below its firing cost
    cost = E.default_config()["entities"]["A1"]["cost"]
    st = R.STRESSES["coupling gain 0.5"]
    en: dict[int, list[float]] = {}
    below = []
    for sd in SEEDS:
        r = E.Run(R.config(sd, 500), R.schedule(st, []))
        series = [r.ent["A1"]["energy"]]
        more = True
        while more:
            more = r.step()
            series.append(r.ent["A1"]["energy"])
        below.append(next(k for k in range(150, len(series)) if series[k] < cost))
        for k in range(384, 392):
            en.setdefault(k, []).append(series[k])
    energy = {"a1_firing_cost": cost, "first_tick_end_of_step_energy_below_cost": [min(below), max(below)], "end_of_step_energy_by_tick": {str(k): [round(min(v), 4), round(max(v), 4)] for k, v in en.items()}}
    # the controls
    ctl: list[dict] = []
    jobs2 = []
    for name, (sid, parts) in WINDOWS.items():
        for t in sorted({last[sid] - 1, last[sid], last[sid] + 1, last[sid] + 6, 500, 800, 1140}):
            for sd in SEEDS:
                jobs2.append((name, sid, parts, t, sd, 300, None))  # a common history to tick 300, then A1's upkeep is 0
                jobs2.append((name, sid, parts, t, sd, None, 0.0))  # the first version: upkeep 0 from the initial configuration (another history)
    for r in X5.pmap(_job, jobs2, None, chunksize=4):
        ctl.append(r)
    control: dict = {}
    for name in WINDOWS:
        for kind, sel in (("branch_at_300", lambda r: r["branch_tick"] == 300), ("upkeep_0_from_start", lambda r: r["initial_upkeep"] == 0.0)):
            by: dict[int, list[dict]] = {}
            for r in ctl:
                if r["window"] == name and sel(r):
                    by.setdefault(r["t"], []).append(r)
            control.setdefault(name, {})[kind] = {str(t): {"recovered_at_1200": sum(x["recovered_at_1200"] for x in v), "of": len(v), "a1_energy_at_start_of_t": [min(x["a1_energy_at_start_of_t"] for x in v), max(x["a1_energy_at_start_of_t"] for x in v)]} for t, v in sorted(by.items())}
    out = {"stress_of_energy": st.id, "a1_firing_cost": cost, "a1_upkeep_per_tick": E.default_config()["entities"]["A1"]["upkeep"], "horizon": H, "recovery_window": W, "post_intervention_criterion": f"sustained ACTIVE for {W} ticks within 2W = {2 * W} ticks of the intervention (the same for every intervention tick)",
           "boundary": boundary, "energy": energy, "upkeep_control": control, "note": "the controls change the model (A1's upkeep), they are not repair actions; branch_at_300 keeps the history identical to the unrepaired run up to tick 300"}
    (DOCS / "experiments_stage6_open_mechanism.json").write_text(json.dumps(out, indent=1))
    for name, b in boundary.items():
        print(name, "last", b["last_effective_tick"])
        for t, v in b["by_tick"].items():
            print("  ", t, v["recovered_at_1200"], "/", v["seeds"], "sust60", v["sustained_within_60"], "E0", v["a1_energy_at_start_of_t"], "lat", v["median_latency"], v["max_latency"], "fire", v["first_a1_fire_median"], v["a1_fires_in_60_median"])
    print(json.dumps(energy))
    print(json.dumps(control))


if __name__ == "__main__":
    main()
