"""The research agent of the total-observation line: findings from records, a research condition, and the rules that change the condition.

Information boundary (tested): this module imports nothing of the world's state or of the verifier. Its inputs are the hub's records (through
``identify``), its own sensor configuration, the grid geometry (the map of the instrument, not a state) and its own history. The orchestrator
(``loop.py``) holds the world and gives the agent ``Findings`` only.

The research condition ``RC`` is what the loop revises: the question, the hypothesis, the observing configuration (``IdentParams``, integration,
variable), the evaluation rule, the operation grammar and (through ``metarevision``) the parameters of the revision rules. Every change is made by an
*operation* from a closed grammar, costs budget, and is recorded with the reason that fired it. Nothing generates or loads code.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field

import numpy as np

from ..hpo.metarevision import RuleSpec, RuleTable
from .identify import INTEGRATIONS, IdentParams

# ---------------------------------------------------------------------------------------------------- the operation grammar
OP_COST = {
    "add-sensor": 8.0,
    "move-sensor": 3.0,
    "set-scale": 2.0,
    "set-period": 1.0,
    "set-integration": 1.0,
    "set-threshold": 0.5,
    "set-connect": 0.5,
    "set-offset": 1.0,
    "derive-variable": 2.0,
    "set-evaluation": 0.5,
    "perturb": 4.0,
}
GRAMMAR_0 = (
    "add-sensor",
    "move-sensor",
    "set-scale",
    "set-period",
    "set-integration",
)  # what every adaptive arm may do at the start
STRONG = ("classification", "boundary", "variable", "evaluation", "grammar")
UNLOCKS = {
    "classification": ("set-threshold", "set-connect"),
    "boundary": ("set-offset",),
    "variable": ("derive-variable",),
    "evaluation": ("set-evaluation",),
    "grammar": (),  # extends the grammar by `perturb` when a hypothesis cannot be tested without an intervention (reversible)
}
ALL_OPS = tuple(OP_COST)
QUESTIONS = ("survey", "resolve", "trace")
EVAL_RULES = ("E0", "E1", "E2")

# parameters of the agent's revision rules (revisable by meta-revision): how many scale steps a resolution rule moves, the factor by which a period
# rule shortens the period, how many sensors a coverage rule adds; and the blindness reason each answers
OBS_SPEC = RuleSpec(
    defaults={"scale_step": 1.0, "period_factor": 0.5, "sensor_step": 1.0},
    bounds={"scale_step": (1.0, 3.0), "period_factor": (0.2, 1.0), "sensor_step": (1.0, 3.0)},
    steps={"scale_step": 1.0, "period_factor": -0.15, "sensor_step": 1.0},
    param_of_reason={
        "scale-mismatch": "scale_step",
        "denied": "scale_step",
        "period-too-slow": "period_factor",
        "uncovered": "sensor_step",
    },
)


@dataclass
class Design:
    """An arm's research design: what the agent may do and which of its own components it may revise."""

    policy: str = "adaptive"  # fixed | random | adaptive
    history: str | bool = False  # False | "own" | "shuffled" (a control that reads outcomes permuted across stored conditions)
    meta: bool = False
    strong: tuple[str, ...] = ()
    max_ops: int = 2
    budget: float = 60.0
    authority: tuple[str, ...] | None = None  # explicit allow-list (ablations); None = grammar rules decide

    @staticmethod
    def from_dict(d: dict | None) -> Design:
        d = d or {}
        out = Design(
            **{
                k: (tuple(v) if k in ("strong", "authority") and v is not None else v)
                for k, v in d.items()
                if k in Design.__dataclass_fields__
            }
        )
        bad = [s for s in out.strong if s not in STRONG]
        if bad or out.policy not in ("fixed", "random", "adaptive"):
            raise ValueError(f"design: unknown policy or strong revision {bad or out.policy!r}")
        return out

    def to_dict(self) -> dict:
        return {
            "policy": self.policy,
            "history": self.history,
            "meta": self.meta,
            "strong": list(self.strong),
            "max_ops": self.max_ops,
            "budget": self.budget,
            "authority": list(self.authority) if self.authority is not None else None,
        }


@dataclass
class RC:
    """The research condition in force."""

    question: str = "survey"
    cycle: int = 0  # returns to the first question after a completed hypothesis test
    hyp: dict = field(
        default_factory=lambda: {"c_hat": 2.0, "status": "untested", "tests": 0, "supported": 0, "refuted": 0, "inconclusive": 0}
    )
    ident: IdentParams = field(default_factory=IdentParams)
    eval_rule: str = "E0"
    grammar: set[str] = field(default_factory=lambda: set(GRAMMAR_0))
    cov_target: float = 0.5

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "cycle": self.cycle,
            "hypothesis": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.hyp.items()},
            "ident": self.ident.to_dict(),
            "eval_rule": self.eval_rule,
            "grammar": sorted(self.grammar),
            "cov_target": round(self.cov_target, 4),
        }


@dataclass
class Findings:
    """Everything the agent knows after a generation: derived from the records it holds and from its own configuration. No world state."""

    gen: int
    objects: list[dict]
    coverage: float
    silent: list[str]
    denied_blocks: int
    n_records: int
    sensors: dict[str, dict]
    reasons: list[str] = field(default_factory=list)
    reason_args: dict[str, dict] = field(default_factory=dict)
    hyp_test: dict | None = None
    integration_sets: dict[str, list[str]] = field(default_factory=dict)

    def keys(self) -> set[str]:
        return {o["key"] for o in self.objects}

    def persists_from(self, prev: Findings | None) -> bool:
        """An object here shares regions with an object of the previous generation (objects drift a little: identity is by overlap, not by label)."""
        if prev is None:
            return False
        before = {c for o in prev.objects for c in o["cells"]}
        return any(set(o["cells"]) & before for o in self.objects)


# ---------------------------------------------------------------------------------------------------- reasons (what the agent can tell about its own blindness)
def diagnose(f: Findings, rc: RC, geometry: dict, prev: Findings | None) -> None:
    """Fill ``f.reasons`` from the findings. Reasons are the agent's statements about why its observing configuration is limited; each
    can be wrong (that is a result, checked against the verifier by the orchestrator)."""
    r: list[str] = []
    args: dict[str, dict] = {}
    if f.coverage < rc.cov_target:
        r.append("uncovered")
    if f.denied_blocks > 0:
        r.append("denied")
        args["denied"] = {"costly": max(f.sensors, key=lambda s: (f.sensors[s]["cost_blocks"], s))}
    if f.silent:
        r.append("silent")
        args["silent"] = {"sids": list(f.silent)}
    if not f.objects and f.n_records:
        r.append("no-object")
    cells_per_block = {s: f.sensors[s]["scale"] ** 2 for s in f.sensors}
    small = [o for o in f.objects if o["n_cells"] <= 2]
    if f.objects and len(small) >= 3 and len(small) == len(f.objects):
        r.append("fragmented")
    coarse = [o for o in f.objects if any(o["n_cells"] <= cells_per_block[s] for s in f.sensors if f.sensors[s]["scale"] > 1)]
    if coarse and any(f.sensors[s]["scale"] > 1 for s in f.sensors):
        r.append("scale-mismatch")
        args["scale-mismatch"] = {"sid": max(f.sensors, key=lambda s: (f.sensors[s]["scale"], s))}
    if f.hyp_test and f.hyp_test.get("outcome") in ("no-arrival", "coarse"):
        r.append("period-too-slow")
    if f.hyp_test and f.hyp_test.get("outcome") == "untestable":
        r.append("untestable")
    sus = [o for o in f.objects if o.get("edge_suspect")]
    if sus:
        r.append("split-by-boundary")
    f.reasons, f.reason_args = r, args


# ---------------------------------------------------------------------------------------------------- evaluation rules (agent-side success)
def eval_ok(rule: str, f: Findings, prev: Findings | None, rc: RC) -> bool:
    e0 = f.coverage >= rc.cov_target and len(f.objects) >= 1
    if rule == "E0":
        return e0
    persistent = f.persists_from(prev)
    if rule == "E1":
        return e0 and persistent
    return e0 and persistent and rc.hyp["status"] == "supported"


# ---------------------------------------------------------------------------------------------------- the external memory (history re-entry)
def signature(sensors: dict[str, dict], ident: IdentParams, variable: str, integrate: str) -> str:
    blob = json.dumps(
        {
            "s": {k: [v["region"], v["scale"], v["period"], v["radius"], list(v["offset"])] for k, v in sorted(sensors.items())},
            "i": ident.to_dict(),
            "v": variable,
            "g": integrate,
        },
        sort_keys=True,
    )
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


@dataclass
class Memory:
    """Outcomes of conditions that were in force: signature -> {score, objects, config}. Readable only for a design with history."""

    rows: dict[str, dict] = field(default_factory=dict)
    mode: str | bool = False
    reads: int = 0
    hits: int = 0
    cool: dict[str, int] = field(
        default_factory=dict
    )  # "sid:direction" -> generation of the last scale move (stops two opposed rules from flip-flopping one sensor)
    suppressed: list[dict] = field(default_factory=list)
    _perm: dict[str, str] | None = None

    def write(self, sig: str, score: float, config: dict) -> None:
        if self.mode:
            self.rows[sig] = {"score": score, "config": copy.deepcopy(config)}

    def _readable(self) -> dict[str, dict]:
        if self.mode == "shuffled":  # outcomes permuted across stored conditions: same form, no information
            ks = sorted(self.rows)
            if self._perm is None or set(self._perm) != set(ks):
                order = sorted(ks, key=lambda k: hashlib.sha1(("s" + k).encode()).hexdigest())
                self._perm = dict(zip(ks, order, strict=True))
            return {k: {**self.rows[k], "score": self.rows[self._perm[k]]["score"]} for k in ks}
        return self.rows

    def best_other(self, current_sig: str, current_score: float) -> tuple[str, dict] | None:
        """A stored condition, other than the one in force, whose recorded outcome beats the current one."""
        if not self.mode:
            return None
        self.reads += 1
        rows = self._readable()
        q = current_sig.rsplit("@", 1)[-1]
        cand = [
            (k, v)
            for k, v in rows.items()
            if k != current_sig and k.rsplit("@", 1)[-1] == q and v["score"] > current_score + 1e-9
        ]
        if not cand:
            return None
        self.hits += 1
        return max(cand, key=lambda kv: (kv[1]["score"], kv[0]))

    def seen_worse(self, sig: str, current_score: float) -> bool:
        if not self.mode:
            return False
        self.reads += 1
        row = self._readable().get(sig)
        if row is not None:
            self.hits += 1
        return row is not None and row["score"] < current_score - 1e-9


def outcome_score(f: Findings, ok: bool) -> float:
    """What the agent stores about a condition: it can compute this from its own findings only."""
    return round(0.5 * ok + 0.3 * min(f.coverage, 1.0) + 0.2 * min(len(f.objects), 3) / 3.0, 6)


# ---------------------------------------------------------------------------------------------------- geometry helper (the map of the instrument)
def best_new_center(d: np.ndarray, covered: set[int], radius: int, taken: set[int], hub: int) -> int:
    """The region whose footprint adds the most uncovered regions (ties: nearest the hub, then lowest index)."""
    n = d.shape[0]
    best, key = 0, (-1, 0, 0)
    for c in range(n):
        if c in taken:
            continue
        gain = int(((d[c] <= radius) & ~np.isin(np.arange(n), list(covered))).sum())
        k = (gain, -int(d[c, hub]), -c)
        if k > key:
            best, key = c, k
    return best


# ---------------------------------------------------------------------------------------------------- proposals
def _grammar_allows(op: str, rc: RC, design: Design) -> bool:
    if design.authority is not None and op not in design.authority:
        return False
    return op in rc.grammar


def propose(
    f: Findings,
    rc: RC,
    rules: RuleTable,
    design: Design,
    geometry: dict,
    mem: Memory,
    rng: np.random.Generator,
    current_sig: str,
    current_score: float,
) -> list[dict]:
    """Operations the agent would perform, in priority order, each with the reason that fired it. The orchestrator executes as many as the budget
    and ``max_ops`` allow; the rest are the opportunity cost."""
    out: list[dict] = []
    p = rules.params
    ex = rules.exhausted

    def add(op: str, reason: str, **kw) -> None:
        if reason in ex and reason != "history":
            return
        if _grammar_allows(op, rc, design):
            out.append({"op": op, "reason": reason, **kw})

    if design.policy == "random":
        return _random_ops(f, rc, design, geometry, rng)
    if design.policy == "fixed":
        return []
    # history: after a loss, the stored condition with a better outcome is re-entered (a change of decision the memory caused)
    if mem.mode:
        better = mem.best_other(current_sig, current_score)
        if (
            better is not None and not f.objects
        ):  # re-entered only after identification was lost, never over a change made for the question in force
            out.append(
                {
                    "op": "reenter",
                    "reason": "history",
                    "signature": better[0],
                    "config": better[1]["config"],
                    "score": better[1]["score"],
                }
            )
    if "silent" in f.reasons and "silent" not in ex:
        for sid in f.reason_args["silent"]["sids"][:1]:
            add("move-sensor", "silent", sid=sid, region=geometry["hub"])
    if "denied" in f.reasons:
        sid = f.reason_args["denied"]["costly"]
        _scale_move(out, mem, f, "denied", sid, +1, int(min(4, f.sensors[sid]["scale"] + round(p["scale_step"]))), add)
    if "uncovered" in f.reasons:
        for _ in range(int(round(p["sensor_step"]))):
            add("add-sensor", "uncovered")
    if "scale-mismatch" in f.reasons:
        sid = f.reason_args["scale-mismatch"]["sid"]
        _scale_move(out, mem, f, "scale-mismatch", sid, -1, int(max(1, f.sensors[sid]["scale"] - round(p["scale_step"]))), add)
    if "period-too-slow" in f.reasons:
        sid = (f.hyp_test or {}).get("B") or sorted(f.sensors)[0]  # the detector of the test that could not time the arrival
        # the period must resolve the lag the hypothesis predicts: at most half of it, and no more than the rule's factor allows in one step
        pred = (f.hyp_test or {}).get("D", 3) / max(rc.hyp["c_hat"], 1e-9)
        add(
            "set-period",
            "period-too-slow",
            sid=sid,
            value=int(max(1, min(round(f.sensors[sid]["period"] * p["period_factor"]), int(pred // 2) or 1))),
        )
    if "no-object" in f.reasons:
        add("set-threshold", "no-object", value=round(max(0.04, rc.ident.theta * 0.6), 6))
        if rc.ident.variable == "level":
            add("derive-variable", "no-object", value="change")
    if "fragmented" in f.reasons:
        add("set-connect", "fragmented", value=min(3, rc.ident.connect + 1))
    if "split-by-boundary" in f.reasons:
        sid = max(f.sensors, key=lambda s: (f.sensors[s]["scale"], s))
        k = f.sensors[sid]["scale"]
        add("set-offset", "split-by-boundary", sid=sid, value=[k // 2, k // 2])
    if "untestable" in f.reasons and "perturb" not in rc.grammar and "grammar" in design.strong:
        out.append({"op": "extend-grammar", "reason": "untestable", "adds": "perturb"})
    # integration: the agent can compute its identification under every integration rule on its own records
    sets = f.integration_sets
    cur = geometry["integrate"]
    if sets:
        best = max(INTEGRATIONS, key=lambda m: (len(sets[m]), m == cur))
        if best != cur and len(sets[best]) > len(sets[cur]):
            add("set-integration", "integration-loss", value=best)
    return out


COOLDOWN = 3


def _scale_move(out: list, mem: Memory, f: Findings, reason: str, sid: str, direction: int, value: int, add) -> None:
    """A scale move is suppressed when the opposite move on the same sensor was made within ``COOLDOWN`` generations (recorded, not silent)."""
    opp = mem.cool.get(f"{sid}:{-direction}")
    if opp is not None and f.gen - opp < COOLDOWN:
        mem.suppressed.append(
            {
                "gen": f.gen,
                "op": "set-scale",
                "sid": sid,
                "reason": reason,
                "why": f"the opposite move on {sid} was made in generation {opp}",
            }
        )
        return
    add("set-scale", reason, sid=sid, value=value, direction=direction)


def _random_ops(f: Findings, rc: RC, design: Design, geometry: dict, rng: np.random.Generator) -> list[dict]:
    """The matched control: the same grammar and authority, arguments drawn at random, no reasons."""
    allowed = [o for o in ALL_OPS if _grammar_allows(o, rc, design) or (design.authority is not None and o in design.authority)]
    out: list[dict] = []
    sids = sorted(f.sensors)
    for _ in range(design.max_ops):
        if not allowed:
            break
        op = allowed[int(rng.integers(len(allowed)))]
        sid = sids[int(rng.integers(len(sids)))] if sids else None
        ops = {
            "add-sensor": {},
            "move-sensor": {"sid": sid, "region": int(rng.integers(geometry["n"]))},
            "set-scale": {"sid": sid, "value": int(rng.integers(1, 5))},
            "set-period": {"sid": sid, "value": int(rng.integers(1, 9))},
            "set-integration": {"value": INTEGRATIONS[int(rng.integers(3))]},
            "set-threshold": {"value": round(float(rng.uniform(0.05, 0.4)), 4)},
            "set-connect": {"value": int(rng.integers(1, 4))},
            "set-offset": {"sid": sid, "value": [int(rng.integers(0, 3)), int(rng.integers(0, 3))]},
            "derive-variable": {"value": ("change", "contrast")[int(rng.integers(2))]},
            "set-evaluation": {"value": EVAL_RULES[int(rng.integers(3))]},
            "perturb": {},
        }[op]
        if sid is None and op in ("move-sensor", "set-scale", "set-period", "set-offset"):
            continue
        out.append({"op": op, "reason": "random", **ops})
    return out
