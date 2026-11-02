"""Causal-pathway measurements of one laboratory run (M9). Read-only: computed after the run from the science events,
the physical events and the physical laboratory's trace; nothing here feeds back into a run.

Per system:

    completed, failed, requests, denied, coverage, paths, pairs, true_gain, observed_outcomes, isolations
                         as in M4–M7 (xzr/lab/science.py summary)
    latency_mean         steps from a transfer's request to its delivery (completed transfers)
    queue_wait_mean      steps a leg waited in its gantry queue before its gantry started it
    contended_legs       legs that had another system's legs ahead of them when queued
    waits_behind_other   number of other systems' legs ahead, summed over the system's legs
    fail_gantry / fail_material / fail_spot / fail_motion / fail_relay / fail_blocked
                         failed transfers by cause (gantry failed, no material, no free spot, motion timeout or grasp,
                         relay stopped, delivery blocked at a closed containment)
    gantry_failures_hit  gantry failures while the system had legs queued on that gantry
    other_wear_share     share of the failed gantries' wear caused by other systems (mean over those failures)
    recovery_steps       steps from such a failure to the system's next completed transfer (horizon if none)
    completed_late       completed transfers in the last third of the horizon (persistence)
    iso_after_other_delivery
                         the system's isolations of a chamber that another system delivered material to within the
                         preceding 40 steps (an environmental pathway: the other system's delivery raised the activity
                         the isolation responds to)
    distinct_observed_pairs / redundant_observations
                         experiments whose outcome the system observed, on new / already observed (source, target) pairs
    gain_per_spent / gain_per_completed
                         true gain per budget unit spent / per completed transfer (effectiveness, not activity)
    obs_error_mean       mean |prediction − own observed outcome| (the error the system can see)
    obs_true_corr        correlation between the system's observed outcome and the harness's true effect over its
                         observed experiments (how much the system's measurement says about what it did)
    changed_without_prediction / _memory / _variables
                         share of decisions that would differ with the model ignored / without memory / without the
                         generated variables (spec.diagnose)

Operational extinction (M9-C; declared here because the "Scientific Operational Extinction Point" exists in this
repository only as a name). For a target system and an intervention at step T:

    active_before        completed transfers in [T − 160, T)
    extinct              active before, and no completed transfer in [T + 30, T + 190) (30 steps allow transfers already
                         under way to end)
    extinction_point     the step after T from which no transfer completes for at least 160 steps (if any)
    reignited            extinct, and a transfer completes later (≥ T + 190)
    reignition_step      first completion after the extinct interval
    restored_same        re-ignited, and every (source, target) pair and gantry bay after re-ignition was already used
                         before T (the same operational dependency); otherwise the re-ignition is a new dependency
    reuse_share          re-ignited: share of the later completed experiments on pairs already used before T (graded)
    outage_paths         mean executable experiments the system saw during [T + 30, T + 190) (substitute paths known
                         to the system)
    apparatus_failed     a gantry failure at or after T (an apparatus failure is not counted as extinction by itself)
    evidence_unavailable memory reads refused because the store was closed (loss of recorded evidence)
    persisting_conduits  chamber pairs the system experimented on before T that are still connected at the horizon
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

BASIC = ("completed", "failed", "requests", "denied", "true_gain", "true_gain_post", "observed_outcomes", "isolations",
         "coverage", "paths", "pairs", "abs_pred_error", "relocations", "window_changes", "memory_reads",
         "memory_unavailable", "spent")


def _reason(r: str) -> str:
    r = r or ""
    if "gantry" in r and "failed" in r:
        return "fail_gantry"
    if r.startswith("no material"):
        return "fail_material"
    if r.startswith("no free spot"):
        return "fail_spot"
    if r.startswith("relay"):
        return "fail_relay"
    return "fail_motion"


def measures(run) -> dict[str, dict[str, Any]]:
    sci, lab = run.science, run.lab
    assert sci is not None and lab is not None
    H = run.cfg["horizon"]
    summ = sci.summary()
    owner_of = {tid: exp["system"] for tid, exp in sci.transfers.items()}
    out: dict[str, dict[str, Any]] = {}
    for sid in sci.systems:
        s = summ[sid]
        m: dict[str, Any] = {}
        for k in BASIC:
            v = s.get(k)
            m[k] = float(v) if isinstance(v, int | float) and not (isinstance(v, float) and math.isnan(v)) else math.nan
        m.update({k: 0.0 for k in ("fail_gantry", "fail_material", "fail_spot", "fail_motion", "fail_relay")})
        out[sid] = m
    lat: dict[str, list[int]] = {sid: [] for sid in sci.systems}
    done_t: dict[str, list[int]] = {sid: [] for sid in sci.systems}
    for e in run.physical:
        sid = owner_of.get(e.get("transfer", -1))
        if sid is None:
            continue
        if e["type"] == "transfer_complete":
            lat[sid].append(e["t"] - e["requested_at"])
        elif e["type"] == "transfer_failed":
            out[sid][_reason(e.get("reason", ""))] += 1
    for e in sci.events:
        if e["type"] == "material_delivered":
            done_t[e["system"]].append(e["t"])
        elif e["type"] == "delivery_blocked":
            out[e["system"]]["fail_blocked"] = out[e["system"]].get("fail_blocked", 0.0) + 1
    legs = lab.trace["legs"]
    for sid in sci.systems:
        m = out[sid]
        m.setdefault("fail_blocked", 0.0)
        mine = [lg for lg in legs if lg["owner"] == sid]
        waits = [lg["start"] - lg["queued"] for lg in mine if lg["start"] is not None]
        m["latency_mean"] = float(np.mean(lat[sid])) if lat[sid] else math.nan
        m["queue_wait_mean"] = float(np.mean(waits)) if waits else math.nan
        m["contended_legs"] = float(sum(1 for lg in mine if any(o != sid for o in lg["ahead"])))
        m["waits_behind_other"] = float(sum(sum(1 for o in lg["ahead"] if o != sid) for lg in mine))
        hits = [f for f in lab.trace["failures"] if sid in f["queued_owners"]]
        m["gantry_failures_hit"] = float(len(hits))
        shares = [sum(v for k, v in f["wear_by"].items() if k != sid) / max(sum(f["wear_by"].values()), 1e-9) for f in hits]
        m["other_wear_share"] = float(np.mean(shares)) if shares else math.nan
        rec = []
        for f in hits:
            nxt = [t for t in done_t[sid] if t > f["t"]]
            rec.append((min(nxt) if nxt else H) - f["t"])
        m["recovery_steps"] = float(np.mean(rec)) if rec else math.nan
        m["completed_late"] = float(sum(1 for t in done_t[sid] if t >= 2 * H // 3))
    deliveries = [(e["t"], e["dst"], e["system"]) for e in sci.events if e["type"] == "material_delivered"]
    for sid in sci.systems:
        n = sum(1 for e in sci.events if e["type"] == "isolation" and e["system"] == sid
                and any(s2 != sid and d == e["chamber"] and 0 <= e["t"] - t < 40 for t, d, s2 in deliveries))
        out[sid]["iso_after_other_delivery"] = float(n)
    true_of: dict[tuple[str, str, str], list[float]] = {}
    for e in sci.events:
        if e["type"] == "material_delivered":
            true_of.setdefault((e["system"], e["src"], e["dst"]), []).append(e["true_effect"])
    for sid, st in sci.systems.items():
        m = out[sid]
        seen: set = set()
        new = red = 0
        obs_v, true_v = [], []
        nth: dict[tuple[str, str], int] = {}
        for a, b, o in st.observed:
            if (a, b) in seen:
                red += 1
            else:
                new += 1
                seen.add((a, b))
            i = nth.get((a, b), 0)
            tv = true_of.get((sid, a, b), [])
            if i < len(tv):
                obs_v.append(o)
                true_v.append(tv[i])
            nth[(a, b)] = i + 1
        m["distinct_observed_pairs"], m["redundant_observations"] = float(new), float(red)
        m["gain_per_spent"] = m["true_gain"] / m["spent"] if m["spent"] else math.nan
        m["gain_per_completed"] = m["true_gain"] / m["completed"] if m["completed"] else math.nan
        m["obs_error_mean"] = float(np.mean(st.obs_error)) if st.obs_error else math.nan
        m["obs_true_corr"] = (float(np.corrcoef(obs_v, true_v)[0, 1])
                              if len(obs_v) > 2 and np.std(obs_v) > 0 and np.std(true_v) > 0 else math.nan)
        d = st.diag
        for key, den in (("changed_without_prediction", "model_decisions"), ("changed_without_memory", "decisions"),
                         ("changed_without_variables", "decisions_with_variables")):
            m[key] = d[key] / d[den] if d.get(den) and key in d else math.nan
        m["variables_adopted"] = float(len(st.stats["variables_adopted"]))
    ext = run.cfg.get("extinction")
    if ext:
        out[ext["system"]].update(extinction(run, ext["system"], int(ext["t"])))
    return out


def extinction(run, sid: str, T: int) -> dict[str, float]:
    sci, lab = run.science, run.lab
    H = run.cfg["horizon"]
    dl = [e for e in sci.events if e["type"] == "material_delivered" and e["system"] == sid]
    times = [e["t"] for e in dl]
    before = [e for e in dl if T - 160 <= e["t"] < T]
    outage = [e for e in dl if T + 30 <= e["t"] < T + 190]
    active = bool(before)
    extinct = active and not outage
    point = math.nan
    for t0 in range(T, H - 160 + 1):
        if not any(t0 <= t < t0 + 160 for t in times):
            point = float(t0)
            break
    later = [e for e in dl if e["t"] >= T + 190]
    reign = extinct and bool(later)
    bay_of = lab.bay_of
    pre_pairs = {(e["src"], e["dst"]) for e in dl if e["t"] < T}
    pre_bays = {bay_of[e["src"]] for e in dl if e["t"] < T}
    restored = (reign and all((e["src"], e["dst"]) in pre_pairs and bay_of[e["src"]] in pre_bays for e in later))
    period = sci.systems[sid].spec.period
    # one paths entry per decision step t = period, 2·period, … (decide runs at steps 1..H where t % period == 0)
    win = [p for k, p in enumerate(sci.systems[sid].stats["paths"]) if T + 30 <= (k + 1) * period < T + 190]
    g = sci.conduit_graph()
    return {"active_before": float(active), "extinct": float(extinct), "extinction_point": point,
            "reignited": float(reign), "reignition_step": float(min(e["t"] for e in later)) if reign else math.nan,
            "restored_same": float(restored) if reign else math.nan,
            "reuse_share": (float(np.mean([(e["src"], e["dst"]) in pre_pairs for e in later])) if reign else math.nan),
            "new_dependency": float(reign and not restored) if reign else math.nan,
            "outage_paths": float(np.mean(win)) if win else math.nan,
            "apparatus_failed": float(any(e["type"] == "gantry_failed" and e["t"] >= T for e in run.physical)),
            "evidence_unavailable": float(sci.systems[sid].stats["memory_unavailable"]),
            "persisting_conduits": float(sum(1 for a, b in pre_pairs if b in g.get(a, set()))),
            "completed_after": float(len([e for e in dl if e["t"] >= T]))}
