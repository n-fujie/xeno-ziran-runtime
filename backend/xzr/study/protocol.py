"""Experiment protocols: a machine-readable, hashable specification of one study.

A protocol fixes the research question, the hypotheses, the environment, the arms (methods compared), the seeds, the
observation / boundary / scale / time-window conditions and interventions, who may revise what, the compute budget, the
metrics, the contrasts, the success and failure criteria and the stop conditions. It is JSON; its SHA-256 over a
canonical form is its identity.

Mode (what the results may be used for):

    functional     software check on small runs; the seeds come from a reserved range; never reported as evidence
    exploratory    looks for effects; nothing is pre-registered; results are labelled exploratory
    confirmatory   the protocol is frozen before the first run (``freeze``), its seeds are disjoint from every
                   development / earlier range, every contrast is declared, and the runner refuses to start if the
                   file differs from the frozen digest

Changes after registration are never overwritten: ``amend`` appends a record (what, old, new, why, when, and whether any
run had already started) and the registered digest stays the reference. A contrast or criterion added after the first
run is analysed as exploratory whatever the mode.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any

SCHEMA = "xzr.study/1"
MODES = ("functional", "exploratory", "confirmatory")
ENV_KINDS = ("hpo-world", "lab-population", "ards", "shared-oi")
CONTROLLER_MODES = ("static", "recursive", "random")
# seed ranges already used by the published experiments (hpo.experiments.RANGES and development seeds): (gen, engine)
USED_GEN = [(0, 8), (100, 600), (3000, 3600), (4000, 4600), (4500, 5100), (5000, 5600), (9000, 9100), (9500, 9600)]
USED_ENGINE = [
    (1000, 1008),
    (101, 104),
    (20000, 20600),
    (30000, 30600),
    (40000, 40600),
    (45000, 45600),
    (50000, 50600),
    (90000, 90100),
    (95000, 95100),
]
FUNCTIONAL_GEN = (7000, 8000)
FUNCTIONAL_ENGINE = (70000, 80000)
# ARDS (pa-simulation-environment) accepts only replicates 3980-3989 in its software-test mode (studyGuard.assertRunAllowed); the bridge never
# uses another mode, so an ARDS study is a functional check by construction
ARDS_TEST_REPLICATES = (3980, 3990)
HIGH_COST_STEP_RUNS = 200_000  # runs × (warm-up + horizon) beyond this need an explicit approval record
VOLATILE = ("amendments", "freeze", "approval_log")


class ProtocolInvalid(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


def canonical(doc: dict) -> str:
    d = {k: v for k, v in doc.items() if k not in VOLATILE}
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(doc: dict) -> str:
    return hashlib.sha256(canonical(doc).encode()).hexdigest()


def seed_list(doc: dict) -> list[tuple[int, int]]:
    """[(generator seed, engine seed)] — explicit ``list`` or ``gen_base`` / ``engine_base`` + ``n``."""
    s = doc["seeds"]
    if "list" in s:
        return [(int(g), int(e)) for g, e in s["list"]]
    return [(int(s["gen_base"]) + i, int(s["engine_base"]) + i) for i in range(int(s["n"]))]


def _overlaps(vals: list[int], ranges: list[tuple[int, int]]) -> bool:
    return any(a <= v < b for v in vals for a, b in ranges)


def n_runs(doc: dict) -> int:
    return len(doc.get("arms", [])) * len(seed_list(doc))


def step_runs(doc: dict) -> int:
    env = doc.get("environment", {})
    return n_runs(doc) * (int(env.get("warmup", 40)) + int(env.get("horizon", 240)))


def _validate_ards(doc: dict) -> list[str]:
    from . import ards

    return ards.validate(doc)


def _check_arm_settings(arm: dict, issues: list[str]) -> None:
    from ..hpo.field import SettingsError, validate
    from ..hpo.reconfig import SANDBOX, SandboxError, check

    s = arm.get("settings")
    if s is not None and not isinstance(s, dict):
        issues.append(f"arm {arm['name']}: settings must be an object")
    elif s is not None:
        try:
            validate({k: v for k, v in s.items() if k not in ("warmup", "horizon")})
        except SettingsError as e:
            issues.append(f"arm {arm['name']}: {e}")
    for where in ("initial_changes", "interventions"):
        for item in arm.get(where, []):
            ch = item.get("change", item) if where == "interventions" else item
            try:
                check(ch)
            except (SandboxError, KeyError, IndexError, TypeError) as e:
                issues.append(f"arm {arm['name']}: {where}: {e}")
            if where == "interventions" and not isinstance(item.get("epoch"), int):
                issues.append(f"arm {arm['name']}: interventions need an integer 'epoch'")
    c = arm.get("controller", {})
    if c.get("mode", "static") not in CONTROLLER_MODES:
        issues.append(f"arm {arm['name']}: controller.mode must be one of {CONTROLLER_MODES}")
    pats = c.get("authority")
    if pats is not None:
        known = set(SANDBOX)
        bad = [p for p in pats if p not in known]
        if bad:
            issues.append(f"arm {arm['name']}: authority patterns outside the sandbox: {bad}")


def validate(doc: dict) -> list[str]:
    """Issues that make the protocol unusable (empty = valid). Warnings are in ``fairness``."""
    issues: list[str] = []
    if doc.get("schema") != SCHEMA:
        issues.append(f"schema must be {SCHEMA!r}")
    for k in ("title", "question", "mode", "environment", "arms", "seeds", "metrics", "stop"):
        if k not in doc:
            issues.append(f"missing field: {k}")
    if issues:
        return issues
    if doc["mode"] not in MODES:
        issues.append(f"mode must be one of {MODES}")
    env = doc["environment"]
    if env.get("kind") not in ENV_KINDS:
        issues.append(f"environment.kind must be one of {ENV_KINDS}")
    arms = doc["arms"]
    if not isinstance(arms, list) or len(arms) < 1:
        issues.append("at least one arm is required")
        return issues
    names = [a.get("name") for a in arms]
    if len(set(names)) != len(names) or not all(isinstance(n, str) and n for n in names):
        issues.append("arm names must be unique non-empty strings")
        return issues
    for a in arms:
        if not a.get("description"):
            issues.append(f"arm {a['name']}: a description (algorithm, information used, what it may revise) is required")
        _check_arm_settings(a, issues)
    if env.get("kind") in ("ards", "shared-oi"):
        issues += _validate_ards(doc)
    try:
        seeds = seed_list(doc)
    except (KeyError, TypeError, ValueError) as e:
        issues.append(f"seeds: {e}")
        return issues
    if len(seeds) < 1 or len({s[0] for s in seeds}) != len(seeds):
        issues.append("seeds: at least one, generator seeds distinct")
    m = doc["metrics"]
    if not m.get("primary"):
        issues.append("metrics.primary: name at least one primary metric")
    arm_names = set(names)
    for c in doc.get("contrasts", []):
        if c.get("a") not in arm_names or c.get("b") not in arm_names:
            issues.append(f"contrast {c.get('id')}: arms must be arms of this protocol")
    cids = {c.get("id") for c in doc.get("contrasts", [])}
    for crit in doc.get("criteria", {}).get("success", []) + doc.get("criteria", {}).get("failure", []):
        if crit.get("contrast") not in cids:
            issues.append(f"criterion refers to an unknown contrast {crit.get('contrast')!r}")
        if crit.get("direction") not in ("greater", "less", "different", "equivalent"):
            issues.append("criterion.direction must be greater, less, different or equivalent")
    stop = doc["stop"]
    if not (stop.get("timeout_per_run_s", 0) > 0 and stop.get("max_wall_seconds", 0) > 0):
        issues.append("stop.timeout_per_run_s and stop.max_wall_seconds must be positive")
    # seed discipline
    gens = [g for g, _ in seeds]
    engs = [e for _, e in seeds]
    mode = doc.get("mode")
    in_functional = all(FUNCTIONAL_GEN[0] <= g < FUNCTIONAL_GEN[1] for g in gens) and all(
        FUNCTIONAL_ENGINE[0] <= e < FUNCTIONAL_ENGINE[1] for e in engs
    )
    if env.get("kind") in ("ards", "shared-oi"):  # the reserved range of this environment is ARDS's software-test block
        in_functional = all(ARDS_TEST_REPLICATES[0] <= g < ARDS_TEST_REPLICATES[1] and g == e for g, e in seeds)
    if mode == "functional" and not in_functional:
        issues.append(f"functional runs use the reserved seed range gen {FUNCTIONAL_GEN}, engine {FUNCTIONAL_ENGINE}")
    if mode in ("exploratory", "confirmatory"):
        if _overlaps(gens, [FUNCTIONAL_GEN]) or _overlaps(engs, [FUNCTIONAL_ENGINE]):
            issues.append("seeds in the reserved functional-check range cannot be used for exploratory or confirmatory runs")
        if _overlaps(gens, USED_GEN) or _overlaps(engs, USED_ENGINE):
            issues.append("seeds overlap development or published-experiment ranges (xzr.hpo.experiments); choose fresh seeds")
    if mode == "confirmatory":
        if not doc.get("contrasts"):
            issues.append("confirmatory: declare the contrasts before the run")
        if not doc.get("criteria", {}).get("success"):
            issues.append("confirmatory: declare the success criteria before the run")
    # cost gate
    if step_runs(doc) > HIGH_COST_STEP_RUNS and not doc.get("approval", {}).get("high_cost"):
        issues.append(
            f"estimated {step_runs(doc)} step-runs exceed {HIGH_COST_STEP_RUNS}: set approval.high_cost with an "
            "explicit approval record (who, when) before starting"
        )
    return issues


# ----------------------------------------------------------------------------------------------- fairness
def information_of(arm: dict, env: dict) -> dict:
    """What the arm's operations can observe at the start (instrument settings after the initial changes)."""
    from ..hpo.field import DEFAULTS
    from ..hpo.field import validate as v
    from ..hpo.observe import DEFAULT_CATALOG
    from ..hpo.operations import DEFAULT_INSTRUMENT

    s = copy.deepcopy(DEFAULTS)
    if env.get("kind") == "hpo-world":
        from .envs import arm_settings

        eff = arm_settings(arm, env)
        if eff is not None:
            s = v(eff)
    inst = {}
    for k, base in DEFAULT_INSTRUMENT.items():
        d = {**base.to_dict(), **s["instruments"].get(k, {})}
        inst[k] = d
    variables, catalog = set(s["variables"]), set(s["catalog"])
    for ch in arm.get("initial_changes", []):
        parts = ch["path"].split(".")
        if parts[0] == "variables":
            variables.add(ch["value"])
            catalog.add(ch["value"])
        elif parts[0] == "catalog":
            catalog = catalog | {ch["value"]} if ch.get("op", "set") != "remove" else catalog - {ch["value"]}
        if parts[0] == "instruments" and parts[1] in inst:
            if parts[2] == "channels":
                cur = set(inst[parts[1]]["channels"])
                cur = cur | {ch["value"]} if ch.get("op", "set") != "remove" else cur - {ch["value"]}
                inst[parts[1]]["channels"] = sorted(cur)
            else:
                inst[parts[1]][parts[2]] = ch["value"]
    return {
        "catalog": sorted(catalog),
        "instruments": inst,
        "variables": sorted(variables),
        "boundary": s["boundary"],
        "default_catalog": sorted(DEFAULT_CATALOG),
    }


def _effective_history(arm: dict, doc: dict) -> bool:
    if doc["environment"].get("kind") != "hpo-world":
        return False
    from .envs import arm_settings

    eff = arm_settings(arm, doc["environment"])
    return bool(eff and (eff.get("history") or {}).get("reinsert"))


def arm_profile(arm: dict, doc: dict) -> dict:
    if doc["environment"].get("kind") == "ards":
        from . import ards

        return ards.profile(arm, doc["environment"])
    if doc["environment"].get("kind") == "shared-oi":
        from .shared import profiles

        return profiles.profile(arm, doc["environment"])
    c = arm.get("controller", {})
    env = doc["environment"]
    return {
        "information": information_of(arm, env),
        "revision_authority": sorted(c["authority"])
        if c.get("authority") is not None
        else "all sandbox paths"
        if c.get("mode", "static") != "static"
        else "none (static)",
        "controller": c.get("mode", "static"),
        "meta_revision": bool(c.get("meta")),
        "history_reinsertion": bool(_effective_history(arm, doc)),
        "max_changes_per_epoch": c.get("max_changes_per_epoch"),
        "interventions": len(arm.get("interventions", [])),
        "scenario": arm.get("scenario"),
        "compute": {
            "warmup": int(env.get("warmup", 40)),
            "horizon": int(env.get("horizon", 240)),
            "epoch": 60,
            "systems": (arm.get("population") or {}).get("n"),
        },
    }


def fairness(doc: dict) -> dict:
    """For each declared contrast, the dimensions in which the two arms differ and whether each is declared.

    Dimensions: information, revision_authority, compute, change budget, interventions, initial conditions (the seeds are
    shared by construction), metrics and stop conditions (shared by construction: one protocol). A difference is the
    contrast itself when it is the declared subject of the comparison (``contrast.varies``); anything else is listed as
    undeclared and is an error in confirmatory mode.
    """
    arms = {a["name"]: a for a in doc["arms"]}
    prof = {n: arm_profile(a, doc) for n, a in arms.items()}
    out = []
    for c in doc.get("contrasts", []):
        a, b = prof[c["a"]], prof[c["b"]]
        varies = set(c.get("varies", []))
        diffs = {k: {"a": a[k], "b": b[k]} for k in a if a[k] != b[k]}
        undeclared = sorted(k for k in diffs if k not in varies)
        out.append(
            {
                "contrast": c["id"],
                "a": c["a"],
                "b": c["b"],
                "differences": diffs,
                "declared": sorted(varies & set(diffs)),
                "undeclared": undeclared,
                "equal_on": sorted(k for k in a if k not in diffs),
            }
        )
    extra = {}
    if doc["environment"].get("kind") == "shared-oi":
        from .shared import profiles

        extra["operations"] = profiles.access_matrix(doc)
    return {
        **extra,
        "profiles": prof,
        "contrasts": out,
        "controls": (
            {
                "initial_condition": "same environment definition, replicate, start configuration, alteration order and loop seed blocks in every arm",
                "evaluation": "same body-run and set-up budgets, same held-out cases scored by ARDS's own code on the same service, same metrics",
            }
            if doc["environment"].get("kind") in ("ards", "shared-oi")
            else {
                "initial_condition": "same generator seed, warm-up and exogenous stream in every arm",
                "evaluation": "same metrics, same horizon, same stop conditions in every arm",
            }
        ),
    }


def fairness_issues(doc: dict) -> list[str]:
    f = fairness(doc)
    bad = [f"contrast {c['contrast']}: undeclared differences {c['undeclared']}" for c in f["contrasts"] if c["undeclared"]]
    return bad


# ----------------------------------------------------------------------------------------------- registration & change
def freeze(doc: dict, git: str = "") -> dict:
    """Register the protocol: after this its digest is the reference; ``amend`` records any later change."""
    issues = validate(doc)
    if doc.get("mode") == "confirmatory":
        issues += fairness_issues(doc)
    if issues:
        raise ProtocolInvalid(issues)
    out = copy.deepcopy(doc)
    out["freeze"] = {"digest": digest(doc), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git": git}
    out.setdefault("amendments", [])
    return out


def amend(doc: dict, path: str, new: Any, reason: str, runs_started: bool, phase: str = "") -> dict:
    """Return a copy of ``doc`` with the field at ``path`` (dotted, ``arms.2.name`` style) replaced, and an amendment
    record. The registered digest in ``freeze`` is untouched; ``current`` differs from it from now on."""
    if not reason.strip():
        raise ProtocolInvalid(["an amendment needs a reason"])
    out = copy.deepcopy(doc)
    node: Any = out
    parts = path.split(".")
    for p in parts[:-1]:
        node = node[int(p)] if isinstance(node, list) else node[p]
    last = parts[-1]
    old = node[int(last)] if isinstance(node, list) else node.get(last)
    if isinstance(node, list):
        node[int(last)] = new
    else:
        node[last] = new
    out.setdefault("amendments", []).append(
        {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "path": path,
            "old": old,
            "new": new,
            "reason": reason,
            "runs_started": bool(runs_started),
            "phase": phase or ("post-start" if runs_started else "pre-start"),
            "status": "exploratory" if runs_started else "pre-registered change",
        }
    )
    issues = validate(out)
    if issues:
        raise ProtocolInvalid(issues)
    return out


def is_registered_unchanged(doc: dict) -> bool:
    fr = doc.get("freeze")
    return bool(fr) and fr["digest"] == digest(doc)
