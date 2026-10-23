"""The HPO arm of the shared environment: the HPO-003 reconfiguration policy, applied to the observation configuration.

What it is. A research system whose revision rules are the HPO controller's: read *why* the instruments were blind (the capability
reasons of the configuration in force: device-mismatch / unmeasured, scale-mismatch, time-window-mismatch, boundary-invisible, and
"capable but unidentified"), and change the instrument accordingly (add a channel, raise the resolution, raise the sampling rate, restore
the window, lower the noise). It keeps a record of what each change opened or closed (reachability) and, optionally, revises its own rule
parameters when a rule's change did not remove the blindness it targeted twice in a row (hpo.metarevision). It is NOT the HPO field of
operations (xzr.hpo.Field): it is the controller's *policy*, on the observation-identifiability task.

What it shares with the ARDS arms (so that the comparison is fair): the environment, the start configuration, the alteration order, the
seed blocks (loop seeds 1,000,000 + 1000 r + 100 k, disjoint from the held-out and truth seeds), the budgets (72 body runs: 8 selection + 4
validation seeds per cycle for 3 cycles; the set-up budget 480 s minus the start configuration's cost, with the environment's own cost
table), the five revision operations, the adoption discipline (a change is tried against the configuration in force on the same data and
adopted only on a gain without loss, then confirmed on fresh seeds), what it may read (the observer's view: capability model and
observations, never the ground truth) and the evaluation (ARDS's own held-out code, run on the final configuration).

What differs by design: how candidates are proposed (the HPO rule table below, not ARDS's R1–R4 / EXISTING-blind procedure), the reachability
record, and the optional meta-revision. The two rule families are close in structure (both map blindness reasons to instrument changes); the
comparison therefore measures the differences between these policies, not between "ARDS" and "HPO" as whole systems.
"""

from __future__ import annotations

import copy
from typing import Any

from ...hpo.metarevision import MetaReviser, RuleSpec, RuleTable
from . import oi_world as O
from .ops import REVISION_OPS

LOOP_SEED_BASE = 1_000_000
CYCLES = 3
SEEDS_SELECTION, SEEDS_VALIDATION = 8, 4
BODY_RUN_BUDGET = 72
SETUP_TOTAL = 480
MAX_CANDIDATES = 3
# rule parameters of this policy (revisable by meta-revision): the noise multiplier a noise rule applies, and how many hierarchy levels a
# resolution rule raises at least; the blindness reason each parameter answers
OI_SPEC = RuleSpec(
    defaults={"noise_factor": 0.5, "resolution_levels": 1.0},
    bounds={"noise_factor": (0.15, 1.0), "resolution_levels": (1.0, 3.0)},
    steps={"noise_factor": -0.15, "resolution_levels": 1.0},
    param_of_reason={"unidentified": "noise_factor", "scale-mismatch": "resolution_levels"},
)
PRIORITY = {"add-device": 0, "spatial-resolution": 1, "sample-rate": 1, "sensor-noise": 2, "temporal-window": 3}


def setup_cost(changes: list[dict], cat: dict) -> int:
    s, touched = 0, set()
    for ch in changes:
        if ch["op"] == "add-device":
            s += cat["setupSeconds"].get(ch["kind"], 10)
        elif ch["op"] == "temporal-window":
            s += cat["setupSeconds"].get("window", 5)
        elif ch["kind"] not in touched:
            touched.add(ch["kind"])
            s += cat["setupSeconds"].get("set", 10)
    return s


def config_setup(cfg: dict, cat: dict) -> int:
    return sum(cat["setupSeconds"].get(k, 10) for k in cfg["kinds"])


def apply_change(cfg: dict, ch: dict) -> dict:
    out = copy.deepcopy(cfg)
    op = ch["op"]
    if op == "add-device":
        if ch["kind"] not in out["kinds"]:
            out["kinds"].append(ch["kind"])
    elif op == "temporal-window":
        out["window"] = None
    else:
        field = {"sensor-noise": "noise", "sample-rate": "sample_hz", "spatial-resolution": "spatial"}[op]
        out.setdefault("overrides", {}).setdefault(ch["kind"], {})[field] = ch["value"]
    return out


def _compact(obs: dict) -> dict:
    return {
        "name": obs["name"],
        "rows": [
            {
                "id": r["id"],
                "capable": r["capability"]["capable"],
                "reason": r["capability"]["reason"],
                "identified": r["identified"],
                "d": None if not r["observed"] else r["observed"]["d"],
                "p": None if not r["observed"] else r["observed"]["p"],
            }
            for r in obs["rows"]
        ],
    }


def _ident(rows: list[dict]) -> set[str]:
    return {r["id"] for r in rows if r["identified"]}


def _capable(rows: list[dict]) -> set[str]:
    return {r["id"] for r in rows if r["capability"]["capable"]}


def propose(
    cfg: dict, cap_rows: list[dict], unidentified_kinds: dict[str, int], cat: dict, rules: RuleTable, history: bool
) -> list[dict]:
    """HPO rule table → candidate change sets, from the blindness reasons of the configuration in force. Candidates are single-rule changes in
    priority order (add channel; raise resolution or rate; lower noise; restore window)."""
    out: list[dict] = []
    exhausted = rules.exhausted
    need_kind: dict[str, int] = {}
    need_scale: dict[str, int] = {}
    need_rate: dict[str, int] = {}
    window_blind = 0
    diffs = O.DIFF_BY_ID
    for r in cap_rows:
        reason = r["capability"]["reason"]
        if reason is None:
            continue
        a = diffs[r["id"]].alt
        if reason in ("device-mismatch", "unmeasured") and reason not in exhausted:
            need_kind[a.kind] = need_kind.get(a.kind, 0) + 1
        elif reason == "scale-mismatch" and reason not in exhausted:
            need_scale[a.kind] = max(need_scale.get(a.kind, 0), a.min_scale)
        elif reason == "time-window-mismatch" and reason not in exhausted:
            need_rate[a.kind] = need_rate.get(a.kind, 0) + 1
        elif reason == "boundary-invisible" and reason not in exhausted:
            window_blind += 1
    for kind in sorted(need_kind, key=lambda k: (-need_kind[k], k))[:1]:
        # a new channel is added together with the resolution and sampling rate its blind differences need (the HPO controller makes all the
        # changes it derives in one epoch; a channel at the default macro scale would still be blind)
        blind_alts = [
            diffs[r["id"]].alt
            for r in cap_rows
            if r["capability"]["reason"] in ("device-mismatch", "unmeasured") and diffs[r["id"]].alt.kind == kind
        ]
        level = min(len(O.SPATIAL_CHOICES[kind]) - 1, max(a.min_scale for a in blind_alts))
        changes = [{"op": "add-device", "kind": kind}]
        if level > 0:
            changes.append({"op": "spatial-resolution", "kind": kind, "value": O.SPATIAL_CHOICES[kind][level]})
        if any(round(10 / O.DEFAULTS[kind]["sample_hz"]) > a.max_period for a in blind_alts):
            changes.append({"op": "sample-rate", "kind": kind, "value": 10})
        out.append(
            {"rule": "add-channel", "reason": "device-mismatch", "kind": kind, "changes": changes, "targets": need_kind[kind]}
        )
    for kind in sorted(need_scale):
        if kind in cfg["kinds"]:
            cur = O.SCALE[kind].get(O._settings(cfg, kind)["spatial"], 0)
            level = min(len(O.SPATIAL_CHOICES[kind]) - 1, max(need_scale[kind], cur + int(rules.params["resolution_levels"])))
            out.append(
                {
                    "rule": "raise-resolution",
                    "reason": "scale-mismatch",
                    "kind": kind,
                    "changes": [{"op": "spatial-resolution", "kind": kind, "value": O.SPATIAL_CHOICES[kind][level]}],
                    "targets": 1,
                }
            )
    for kind in sorted(need_rate):
        if kind in cfg["kinds"]:
            out.append(
                {
                    "rule": "raise-rate",
                    "reason": "time-window-mismatch",
                    "kind": kind,
                    "changes": [{"op": "sample-rate", "kind": kind, "value": 10}],
                    "targets": need_rate[kind],
                }
            )
    if history and unidentified_kinds and "unidentified" not in exhausted:
        for kind in sorted(unidentified_kinds, key=lambda k: (-unidentified_kinds[k], k))[:1]:
            cur = O._settings(cfg, kind)["noise"]
            if kind in cfg["kinds"]:
                out.append(
                    {
                        "rule": "lower-noise",
                        "reason": "unidentified",
                        "kind": kind,
                        "changes": [{"op": "sensor-noise", "kind": kind, "value": round(cur * rules.params["noise_factor"], 6)}],
                        "targets": unidentified_kinds[kind],
                    }
                )
    if window_blind and cfg.get("window") is not None:
        out.append(
            {
                "rule": "restore-window",
                "reason": "boundary-invisible",
                "kind": "window",
                "changes": [{"op": "temporal-window", "value": None}],
                "targets": window_blind,
            }
        )
    out.sort(key=lambda c: (PRIORITY[c["changes"][0]["op"]], -c["targets"], c["rule"], c["kind"]))
    if (
        len(out) > 1
    ):  # the bundle: everything the rules derive from this diagnosis, made at once as the HPO controller does in one epoch
        seen, merged = set(), []
        for c in out:
            for ch in c["changes"]:
                key = (ch["op"], ch.get("kind"))
                if key not in seen:
                    seen.add(key)
                    merged.append(ch)
        out.insert(
            0, {"rule": "bundle", "reason": "all", "kind": "*", "changes": merged, "targets": sum(c["targets"] for c in out)}
        )
    return out


REPEAT_ABOVE = 3  # capable-but-unidentified differences that make the arm test the same alteration again (more evidence) instead of a new one


def choose_alteration(pool: list[str], done: list[dict], last_unidentified: int) -> tuple[str, str]:
    """The operation "intervention": which alteration the next experiment tests. First cycle: the first of the pool. Then: if the last cycle left at least
    REPEAT_ABOVE differences capable but not identified, repeat that alteration on fresh seeds; otherwise take the first alteration not tested yet."""
    if not done:
        return pool[0], "first of the pool"
    if last_unidentified >= REPEAT_ABOVE:
        return done[-1][
            "alteration"
        ], f"{last_unidentified} differences capable but not identified: more evidence on the same alteration"
    tested = {d["alteration"] for d in done}
    return next(
        (a for a in pool if a not in tested), done[-1]["alteration"]
    ), "last cycle left few capable-unidentified differences: a new alteration"


def run(replicate: int, *, history: bool = True, meta: bool = False, select: bool = False, preset: str | None = None) -> dict:
    """One replicate of the HPO arm. Reads only the observer's view (capability model, observations); never the ground truth."""
    cat = O.catalog()
    preset = preset or "intermittent"
    pool = [
        "input-shift",
        "coupling-shift",
        "retention-shift",
    ]  # the alterations the loops may observe (the held-out "unseen" ones stay unseen)
    alterations = list(pool)  # replaced by the chosen sequence when the arm may select experiments (operation: intervention)
    interventions: list[dict] = []
    last_unidentified = 0
    cfg = copy.deepcopy(O.START_CONFIG)
    setup_budget = SETUP_TOTAL - config_setup(cfg, cat)
    setup_spent = 0
    body_runs = 0
    rules = RuleTable(OI_SPEC)
    reviser = MetaReviser(rules) if meta else None
    cycles: list[dict] = []
    memory_unidentified: dict[
        str, int
    ] = {}  # history: capable-but-unidentified kinds seen in the previous cycle's control observation
    prev_blind: dict[str, dict[str, list[int]]] | None = None
    ops_used: set[str] = set()
    design = {
        "history": history,
        "meta": meta,
        "select": select,
        "preset": preset,
        "alterations": alterations,
        "bodyRunBudget": BODY_RUN_BUDGET,
        "setupBudget": setup_budget,
        "seedBlocks": [LOOP_SEED_BASE + 1000 * replicate + 100 * k for k in range(CYCLES)],
        "rules": copy.deepcopy(OI_SPEC.defaults),
    }
    for k in range(CYCLES):
        alt, why = choose_alteration(pool, interventions, last_unidentified) if select else (pool[k], "fixed order")
        interventions.append({"cycle": k + 1, "alteration": alt, "reason": why})
        alterations[k] = alt
        base = LOOP_SEED_BASE + 1000 * replicate + 100 * k
        control = {**copy.deepcopy(cfg), "name": "control"}
        cap_rows = [
            {"id": d.id, "capability": O.capability_of(control, d)} for d in O.DIFFS
        ]  # free: the observer's model of its own instruments
        revisions: list[dict] = []
        if reviser is not None and prev_blind is not None:
            # blindness that the previous cycle's changes targeted, as it stands in the configuration now in force
            blind: dict[str, dict[str, list[int]]] = {}
            for r in cap_rows:
                if r["capability"]["reason"]:
                    blind.setdefault(O.DIFF_BY_ID[r["id"]].alt.kind, {}).setdefault(r["capability"]["reason"], []).append(0)
            for kind in memory_unidentified:
                blind.setdefault(kind, {}).setdefault("unidentified", []).append(0)
            revisions = reviser.judge(blind, k)
        candidates = propose(control, cap_rows, memory_unidentified if history else {}, cat, rules, history)
        remaining = setup_budget - setup_spent
        chosen: list[dict] = []
        for c in candidates:
            cost = setup_cost(c["changes"], cat)
            if cost <= remaining and len(chosen) < MAX_CANDIDATES:
                chosen.append({**c, "cost": cost})
        cand_cfgs = []
        for i, c in enumerate(chosen):
            cc = copy.deepcopy(control)
            for ch in c["changes"]:
                cc = apply_change(cc, ch)
            cc["name"] = f"T{i + 1}"
            cand_cfgs.append(cc)
        sel_req = {
            "alteration": alt,
            "preset": preset,
            "seedBase": base,
            "nSeeds": SEEDS_SELECTION,
            "configs": [control, *cand_cfgs],
        }
        sel = O.observe(sel_req)
        body_runs += sel["bodyRuns"]
        ctl_obs = sel["configs"][0]
        decisions = []
        best: tuple[Any, ...] | None = None
        for i, c in enumerate(chosen):
            newly = sorted(_ident(sel["configs"][i + 1]["rows"]) - _ident(ctl_obs["rows"]))
            lost = sorted(_ident(ctl_obs["rows"]) - _ident(sel["configs"][i + 1]["rows"]))
            decisions.append(
                {
                    "name": f"T{i + 1}",
                    "rule": c["rule"],
                    "newly": newly,
                    "lost": lost,
                    "net": len(newly) - len(lost),
                    "cost": c["cost"],
                }
            )
            if len(newly) - len(lost) > 0 and not lost:
                key = (-(len(newly) - len(lost)), c["cost"], PRIORITY[c["changes"][0]["op"]], i)
                if best is None or key < best[0]:
                    best = (key, i)
        adopted = None
        validation = None
        reach = None
        if best is not None:
            i = best[1]
            val_req = {
                "alteration": alt,
                "preset": preset,
                "seedBase": base + 50,
                "nSeeds": SEEDS_VALIDATION,
                "configs": [control, cand_cfgs[i]],
            }
            val = O.observe(val_req)
            body_runs += val["bodyRuns"]
            cap_lost = sorted(_capable(val["configs"][0]["rows"]) - _capable(val["configs"][1]["rows"]))
            gain = len(_ident(val["configs"][1]["rows"])) - len(_ident(val["configs"][0]["rows"]))
            validation = {
                "candidate": f"T{i + 1}",
                "capabilityLost": cap_lost,
                "gain": gain,
                "control": _compact(val["configs"][0]),
                "treatment": _compact(val["configs"][1]),
                "request": {k2: v for k2, v in val_req.items() if k2 != "configs"},
            }
            decisions[i]["validated"] = not cap_lost and gain >= 0
            if not cap_lost and gain >= 0:
                adopted = i
        if (
            best is None
        ):  # no candidate to confirm: the validation seeds are still spent, on the configuration in force (budget parity with the ARDS arms)
            val_req = {
                "alteration": alt,
                "preset": preset,
                "seedBase": base + 50,
                "nSeeds": SEEDS_VALIDATION,
                "configs": [control],
            }
            body_runs += O.observe(val_req)["bodyRuns"]
            idle_validation = {"request": {k2: v for k2, v in val_req.items() if k2 != "configs"}}
        else:
            idle_validation = None
        if adopted is not None:
            c = chosen[adopted]
            before_cap = _capable(ctl_obs["rows"])
            cfg = apply_change_all(control, c["changes"])
            cfg["name"] = "control"
            setup_spent += c["cost"]
            ops_used |= {ch["op"] for ch in c["changes"]}
            after_cap = _capable(sel["configs"][adopted + 1]["rows"])
            ident_after = _ident(validation["treatment"]["rows"]) if validation else set()  # type: ignore[index]
            opened = sorted(after_cap - before_cap)
            reach = {
                "rule": c["rule"],
                "opened": opened,
                "closed": sorted(before_cap - after_cap),
                "opened_and_identified": sorted(set(opened) & ident_after),
                "opened_not_identified": sorted(set(opened) - ident_after),
                "setupSeconds": c["cost"],
                "capableBefore": len(before_cap),
                "capableAfter": len(after_cap),
                "note": "predicted from the capability model (opened) and compared with what the fresh validation seeds identified",
            }
            if reviser is not None:
                reviser.register(c["kind"], c["reason"], k, k, [])
        prev_blind = {} if reviser is not None else None
        last_unidentified = sum(1 for r in ctl_obs["rows"] if r["capability"]["capable"] and not r["identified"])
        if history:  # memory of this cycle's control observation: capable differences that the data did not identify
            memory_unidentified = {}
            for r in ctl_obs["rows"]:
                if r["capability"]["capable"] and not r["identified"]:
                    kd = O.DIFF_BY_ID[r["id"]].alt.kind
                    memory_unidentified[kd] = memory_unidentified.get(kd, 0) + 1
        cycles.append(
            {
                "cycle": k + 1,
                "alteration": alt,
                "request": {k2: v for k2, v in sel_req.items() if k2 != "configs"},
                "control": _compact(ctl_obs),
                "treatments": [_compact(o) for o in sel["configs"][1:]],
                "proposals": [{kk: v for kk, v in c.items() if kk != "changes"} | {"changes": c["changes"]} for c in chosen],
                "decisions": decisions,
                "validation": validation,
                "idleValidation": idle_validation,
                "adopted": None if adopted is None else chosen[adopted]["rule"],
                "reachability": reach,
                "meta_revisions": revisions,
                "rules": rules.snapshot() if meta else None,
                "setupSpent": setup_spent,
                "configAfter": copy.deepcopy(cfg),
            }
        )
    final = {**copy.deepcopy(cfg), "name": "evaluated"}
    return {
        "armId": "HPO-rules" + ("-meta" if meta else "") + ("" if history else "-no-history") + ("-select" if select else ""),
        "interventions": interventions,
        "replicate": replicate,
        "design": design,
        "cycles": cycles,
        "finalConfig": final,
        "bodyRuns": body_runs,
        "setupSecondsSpent": setup_spent,
        "setupBudget": setup_budget,
        "opsUsed": sorted(ops_used),
        "metaTrace": reviser.trace if reviser else [],
        "rules": rules.snapshot() if meta else None,
    }


def apply_change_all(cfg: dict, changes: list[dict]) -> dict:
    out = copy.deepcopy(cfg)
    for ch in changes:
        out = apply_change(out, ch)
    return out


def verify(run_: dict) -> list[dict]:
    """Independent re-derivation of what the stored record says: budgets, every decision from the stored rows, the final configuration, the
    permissions, and the seeds. Returns checks ``{"check", "pass", "detail"}``; none may fail."""
    cat = O.catalog()
    checks: list[dict] = []

    def ck(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "pass": bool(ok), **({"detail": detail} if detail and not ok else {})})

    cycles = run_["cycles"]
    spent_runs = sum(2 * (c["request"]["nSeeds"] + (c["validation"] or c["idleValidation"])["request"]["nSeeds"]) for c in cycles)
    ck(
        "body runs: the record's total equals the requests it lists, and is within the budget",
        spent_runs == run_["bodyRuns"] <= BODY_RUN_BUDGET,
        f"{spent_runs} vs {run_['bodyRuns']}",
    )
    adopted_costs = sum(next(p["cost"] for p in c["proposals"] if p["rule"] == c["adopted"]) for c in cycles if c["adopted"])
    ck(
        "set-up: spent equals the cost of the adopted changes, within the budget",
        adopted_costs == run_["setupSecondsSpent"] <= run_["setupBudget"],
        f"{adopted_costs} vs {run_['setupSecondsSpent']}",
    )
    cfg = copy.deepcopy(O.START_CONFIG)
    bad_dec = []
    for c in cycles:
        ctl = {r["id"]: r for r in c["control"]["rows"]}
        ident_c = {i for i, r in ctl.items() if r["identified"]}
        for i, t in enumerate(c["treatments"]):
            ident_t = {r["id"] for r in t["rows"] if r["identified"]}
            d = c["decisions"][i]
            if d["newly"] != sorted(ident_t - ident_c) or d["lost"] != sorted(ident_c - ident_t):
                bad_dec.append(f"cycle {c['cycle']} {d['name']}")
        want = None
        best = None
        for i, d in enumerate(c["decisions"]):
            if d["net"] > 0 and not d["lost"]:
                key = (-d["net"], d["cost"], PRIORITY[c["proposals"][i]["changes"][0]["op"]], i)
                if best is None or key < best[0]:
                    best = (key, i)
        if best is not None and c["validation"] is not None:
            v = c["validation"]
            ok = not v["capabilityLost"] and v["gain"] >= 0
            want = c["proposals"][best[1]]["rule"] if ok else None
        if want != c["adopted"]:
            bad_dec.append(f"cycle {c['cycle']} adoption")
        if c["adopted"]:
            cfg = apply_change_all(cfg, next(p["changes"] for p in c["proposals"] if p["rule"] == c["adopted"]))
    ck("decisions: every newly / lost set and every adoption re-derives from the stored rows", not bad_dec, ", ".join(bad_dec))
    final = {k: v for k, v in run_["finalConfig"].items() if k != "name"}
    ck(
        "final configuration equals the start configuration with the adopted changes applied in order",
        final == {k: v for k, v in cfg.items() if k != "name"},
    )
    seq_ok = True
    done: list[dict] = []
    pool = ["input-shift", "coupling-shift", "retention-shift"]
    last_unid = 0
    for c in cycles:
        want = choose_alteration(pool, done, last_unid)[0] if run_["design"].get("select") else pool[len(done)]
        seq_ok &= c["alteration"] == want
        done.append({"alteration": c["alteration"]})
        last_unid = sum(1 for r in c["control"]["rows"] if r["capable"] and not r["identified"])
    ck("intervention: the sequence of alterations re-derives from the stated rule and the stored rows", seq_ok)
    ck("permissions: only the five revision operations were used", set(run_["opsUsed"]) <= set(REVISION_OPS))
    seeds_ok = all(c["request"]["seedBase"] >= LOOP_SEED_BASE and c["request"]["seedBase"] + 60 < 5_000_000 for c in cycles)
    ck("seeds: loop seeds only, disjoint from the held-out (5,000,000+) and truth (90,000,000+) seeds", seeds_ok)
    ck(
        "setup budget is the environment's: 480 s minus the start configuration's cost",
        run_["setupBudget"] == SETUP_TOTAL - config_setup(O.START_CONFIG, cat),
    )
    return checks
