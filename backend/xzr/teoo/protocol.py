"""Pre-registered experimental protocols for TEOO: versioned, frozen before data, replayable.

A protocol names the hypotheses, the measured targets, the instrument conditions (an observation configuration version), the control condition, the seeds, the number of trials, the stopping rule, the outcome
measures, the analyses with their statistical method and the multiplicity correction, the failure conditions and the reproduction procedure. ``freeze`` fixes a version by its digest; **any later change is a new
version** (``amend``), and the frozen one stays as it was. An analysis is *confirmatory* only if it is declared in a version frozen before the first data of that experiment; otherwise it is *exploratory*, and is
labelled so. The registry is a hash-chained log: an edit of an earlier entry is detected. (The logic of the confirmatory / exploratory distinction follows ``study.analysis.evidence_class``; this module imports nothing of ``study``.)
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import stats as S
from .chainlog import ChainLog
from .provenance import digest_of, now_iso

REQUIRED = ("experiment_id", "hypotheses", "targets", "instrument_conditions", "control_condition", "conditions", "seeds", "trials_per_condition", "stopping_rule", "outcomes", "analyses", "multiplicity",
            "failure_conditions", "reproduction")
METHODS = ("randomization-test", "paired-sign-flip", "equivalence", "exact-upper-bound", "descriptive")


def new_protocol(**kw: Any) -> dict:
    p = {k: kw.get(k) for k in REQUIRED}
    p.update({"schema": "teoo.protocol/1", "version": 1, "parent_version": None, "change_reason": None})
    return p


def validate(p: dict) -> list[str]:
    out = [f"{k} is required" for k in REQUIRED if p.get(k) in (None, [], {}, "")]
    if out:
        return out
    if len(p["conditions"]) < 2 or p["control_condition"] not in p["conditions"]:
        out.append("two or more conditions, one of them the control condition")
    if not isinstance(p["seeds"], list) or len(set(p["seeds"])) != len(p["seeds"]):
        out.append("seeds are a list without repeats")
    ids = [a.get("id") for a in p["analyses"]]
    if len(set(ids)) != len(ids) or any(a.get("method") not in METHODS or not a.get("hypothesis") or not a.get("outcome") for a in p["analyses"]):
        out.append(f"each analysis has a unique id, a hypothesis, an outcome and a method in {METHODS}")
    if {a.get("hypothesis") for a in p["analyses"]} - {h.get("id") for h in p["hypotheses"]}:
        out.append("an analysis refers to a hypothesis that is not declared")
    if p["multiplicity"] not in ("holm", "none-declared-single-test"):
        out.append("multiplicity is holm, or none-declared-single-test for a single confirmatory test")
    if p["multiplicity"] != "holm" and sum(a.get("confirmatory", False) for a in p["analyses"]) > 1:
        out.append("more than one confirmatory analysis needs a multiplicity correction")
    return out


def body_digest(p: dict) -> str:
    return digest_of({k: v for k, v in p.items() if k not in ("digest", "frozen_at")})


class ProtocolRegistry:
    def __init__(self, path: Path | None = None):
        self.log = ChainLog(path)

    def _events(self, pid: str) -> list[dict]:
        return [b for b in self.log.bodies() if b["protocol_id"] == pid]

    def register(self, p: dict) -> dict:
        issues = validate(p)
        if issues:
            raise ValueError("; ".join(issues))
        pid, ver = p["experiment_id"], p["version"]
        if any(b["event"] == "register" and b["protocol_id"] == pid and b["version"] == ver for b in self.log.bodies()):
            raise ValueError("this version is already registered; amend makes a new one")
        self.log.append({"event": "register", "protocol_id": pid, "version": ver, "digest": body_digest(p), "protocol": copy.deepcopy(p), "at": now_iso()})
        return p

    def freeze(self, pid: str, version: int, at: float) -> str:
        reg = next(b for b in self._events(pid) if b["event"] == "register" and b["version"] == version)
        if any(b["event"] == "freeze" and b["version"] == version for b in self._events(pid)):
            raise ValueError("already frozen")
        self.log.append({"event": "freeze", "protocol_id": pid, "version": version, "digest": reg["digest"], "frozen_at": at})
        return reg["digest"]

    def amend(self, pid: str, version: int, changes: dict, reason: str) -> dict:
        """A change is a new version that names its parent; the earlier version, frozen or not, is untouched."""
        base = copy.deepcopy(next(b for b in self._events(pid) if b["event"] == "register" and b["version"] == version)["protocol"])
        base.update(copy.deepcopy(changes))
        base.update({"version": max(b["version"] for b in self._events(pid) if b["event"] == "register") + 1, "parent_version": version, "change_reason": reason})
        if not reason:
            raise ValueError("an amendment states its reason")
        return self.register(base)

    def note_first_data(self, pid: str, version: int, at: float) -> None:
        if not any(b["event"] == "first_data" and b["version"] == version for b in self._events(pid)):
            self.log.append({"event": "first_data", "protocol_id": pid, "version": version, "at_data": at})

    def get(self, pid: str, version: int) -> dict:
        return copy.deepcopy(next(b for b in self._events(pid) if b["event"] == "register" and b["version"] == version)["protocol"])

    def verify(self) -> list[str]:
        out = self.log.verify()
        for b in self.log.bodies():
            if b["event"] == "register" and body_digest(b["protocol"]) != b["digest"]:
                out.append(f"{b['protocol_id']} v{b['version']}: the stored protocol does not match its digest")
        return out

    def analysis_class(self, pid: str, version: int, analysis_id: str) -> str:
        """'confirmatory' only if the analysis is declared in this version, the version was frozen, and it was frozen before the first data."""
        ev = self._events(pid)
        reg = next(b for b in ev if b["event"] == "register" and b["version"] == version)
        a = next((x for x in reg["protocol"]["analyses"] if x["id"] == analysis_id), None)
        frozen = next((b for b in ev if b["event"] == "freeze" and b["version"] == version), None)
        data = next((b for b in ev if b["event"] == "first_data" and b["version"] == version), None)
        if a is None:
            return "exploratory (not declared in this version)"
        if frozen is None:
            return "exploratory (the protocol was not frozen)"
        if data is not None and data["at_data"] < frozen["frozen_at"]:
            return "exploratory (declared after the first data)"
        return "confirmatory" if a.get("confirmatory") else "exploratory (declared but not marked confirmatory)"


GENERATORS: dict[str, Any] = {}


def generator(name: str):
    def deco(fn):
        GENERATORS[name] = fn
        return fn
    return deco


@generator("synthetic-two-condition/1")
def _synthetic_two_condition(condition: str, seed: int, trial: int, params: dict) -> float:
    """SYNTHETIC trial values: a baseline level, an optional condition shift, noise and a slow drift. Artificial functional-test data with no physiological meaning."""
    import numpy as np
    rng = np.random.default_rng(seed * 1000 + trial)
    return float(params.get("baseline", 10.0) + params.get("shifts", {}).get(condition, 0.0) + params.get("drift", 0.0) * trial + rng.normal(0, params.get("noise", 1.0)))


def run_protocol(p: dict, *, params: dict, created_at: str = "2026-01-01T00:00:00.000000Z") -> dict:
    """Run the protocol's generator over its seeds and conditions (SYNTHETIC trials), allocate conditions by a seeded randomisation, and return the trials and the pre-declared analyses. Replays exactly."""
    import numpy as np
    gen = GENERATORS[p["reproduction"]["generator"]]
    trials = []
    for seed in p["seeds"]:
        rng = np.random.default_rng(seed)
        labels = [c for c in p["conditions"] for _ in range(p["trials_per_condition"])]
        rng.shuffle(labels)
        for i, c in enumerate(labels):
            trials.append({"seed": seed, "trial": i, "condition": c, "value": gen(c, seed, i, params), "assignment": "randomized (seeded shuffle)"})
    ctrl = p["control_condition"]
    results, pvals = {}, {}
    for a in p["analyses"]:
        other = a.get("compare", [c for c in p["conditions"] if c != ctrl][0])
        r = S.randomization_test([t["value"] for t in trials], [t["condition"] for t in trials], a=ctrl, b=other, randomized=True, n_perm=a.get("n_perm", 2000), seed=a.get("seed", 0),
                                 blocks=[t["seed"] for t in trials])
        results[a["id"]], pvals[a["id"]] = r, r["p"]
    adj = S.holm(pvals) if p["multiplicity"] == "holm" else {k: {"p": v, "p_holm": v} for k, v in pvals.items()}
    return {"experiment_id": p["experiment_id"], "version": p["version"], "n_trials": len(trials), "trials": trials, "results": results, "adjusted": adj, "created_at": created_at, "generator_note": "SYNTHETIC trials (artificial test data)"}


def reproduce(p: dict, run: dict, *, params: dict) -> dict:
    again = run_protocol(p, params=params, created_at=run["created_at"])
    return {"identical": digest_of(again["trials"]) == digest_of(run["trials"]) and digest_of(again["results"]) == digest_of(run["results"]), "trials_digest": digest_of(again["trials"]), "results_digest": digest_of(again["results"])}
