"""The first stage of a Philosophical-AI connection to MEOS-0: five operations realised as operational couplings of the two existing configurations,
not as an abstract module apart from body, environment and history.

    expression             A1 asserts a claim about its environment ("the effect of renewal is weaker / stronger than expected")
    scorekeeping           both configurations keep a ledger of claims and of whether they were confirmed
    norm-sensitive update  an assertion is acted upon only if the claimant's record for that kind of claim meets a norm; an unreliable kind is withheld
    inferential transition from a claim and its own measurement, A2 infers the efficiency of its renewals and a compensating action
    correction             after a mismatch between a claim and the other configuration's measurement, A1 recalibrates its expectation

The closed path implemented is

    environmental event -> body detection -> expression -> other-system response -> score update -> subsequent operational change

  * environmental event: any change of ``environment.renew_efficiency`` (an intervention) or the like; nothing here knows about it;
  * body detection: A1 compares the differentiated stimulus of a firing attributed to A2's renewal with its own slowly adapting expectation;
  * expression: a mismatch beyond a margin becomes a claim sent through a channel with its own delay and noise, and it costs power from the finite reserve;
  * other-system response: A2 checks the claim against its own measurement of how much of a renewal reached the field and answers agree / disagree;
  * score update: both ledgers are updated from the response;
  * subsequent operational change: A2 raises its renewal amount by the inferred shortfall (when the norm is met), A1 withholds an unreliable kind of claim.

Modes, from nothing to everything: ``none`` · ``expression`` (claims are made and paid for; nobody answers) · ``scorekeeping`` (answers and ledgers; nothing is
acted upon) · ``revision`` (acts on them). The operation is not designed to help: it costs power, a noisy or slow channel makes it wrong or late, and whether it is
needed, becomes unnecessary or fires again is what the experiments measure. Nothing in this module is a language model.
"""

from __future__ import annotations

from typing import Any

import numpy as np

KINDS = ("scarcity", "abundance")


class PhilOps:
    def __init__(self, run: Any):
        cfg = run.cfg.get("phil") or {}
        self.mode: str = cfg.get("mode", "none")
        self.cost = float(cfg.get("cost", 0.05))  # power per expression and per response
        self.margin = float(
            cfg.get("margin", 0.25)
        )  # a firing's stimulus must differ from the expectation by this share to be a mismatch
        self.delay = int(cfg.get("delay", 1))
        self.channel_noise = float(cfg.get("noise", 0.0))
        self.meas_noise = float(cfg.get("measurement_noise", 0.02))
        self.verify = float(
            cfg.get("verify_margin", 0.03)
        )  # A2 confirms a claim if its own measurement departs from nominal by at least this share
        self.norm = float(
            cfg.get("norm_threshold", 0.6)
        )  # a claim is acted upon if the claimant's reliability for its kind is at least this
        self.withhold_below = float(cfg.get("withhold_below", 0.4))
        self.quiet = int(cfg.get("quiet", 20))
        self.boost = 1.0
        self.exp_d: float | None = None
        self.window = int(cfg.get("window", 4))
        self.recent: list[float] = []
        self.queue: list[dict] = []
        self.a1_ledger = {k: [0, 0] for k in KINDS}  # [confirmed, contradicted]
        self.a2_trust = {k: [0, 0] for k in KINDS}
        self.meas_eff = 1.0
        self.withheld_until = {k: -1 for k in KINDS}
        self.counts = {
            "expression": 0,
            "response": 0,
            "score": 0,
            "inference": 0,
            "revision": 0,
            "correction": 0,
            "withheld": 0,
            "power": 0.0,
        }
        self.rng = np.random.default_rng(int(run.cfg["seed"]) + 15485863)
        self.last_expression_tick: int | None = None

    # ------------------------------------------------------------------------------------------------ helpers
    @staticmethod
    def reliability(ledger: list[int]) -> float:
        return (ledger[0] + 1) / (ledger[0] + ledger[1] + 2)

    def _pay(self, run: Any, amount: float) -> None:
        self.counts["power"] += amount
        if not run.cfg["power"]["infinite"]:
            run.power = max(0.0, run.power - amount)
        run._acc("power_phil", amount)

    # ------------------------------------------------------------------------------------------------ hooks called by the engine
    def on_renewal(self, run: Any, requested: float, eff: float) -> None:
        """A2's own measurement of how much of a renewal reached the field (it does not read the environment's efficiency parameter: it measures its effect)."""
        if requested <= 0:
            return
        m = eff * (1.0 + float(self.rng.normal(0.0, self.meas_noise)))
        self.meas_eff += 0.35 * (m - self.meas_eff)

    def on_a1_fire(self, run: Any, fe: dict) -> None:
        """Body detection: a firing of A1 that is attributed to A2's renewal is compared with A1's expectation, the mean of its last firings of that kind
        (so that a gradual change is absorbed and only an abrupt departure is a mismatch)."""
        if fe["source"] is None:
            return
        d = float(fe["differentiated"])
        recent = self.recent
        expected = float(np.mean(recent)) if len(recent) >= 3 else None
        recent.append(d)
        del recent[: -self.window]
        if expected is None:
            return
        self.exp_d = expected
        m = d / max(expected, 1e-9)
        kind = "scarcity" if m < 1.0 - self.margin else "abundance" if m > 1.0 + self.margin else None
        if kind is None:
            return
        if run.t <= self.withheld_until[kind]:  # the norm: an unreliable kind of claim is not asserted
            self.counts["withheld"] += 1
            return
        self._express(run, kind, m, fe)

    def _express(self, run: Any, kind: str, m: float, fe: dict) -> None:
        self._pay(run, self.cost)
        value = m + float(self.rng.normal(0.0, self.channel_noise)) if self.channel_noise > 0 else m
        ev = run._event(
            "expression",
            "A1",
            claim=kind,
            value=round(m, 4),
            sent_value=round(value, 4),
            fire=fe["id"],
            expected=round(float(self.exp_d or 0.0), 4),
        )
        self.counts["expression"] += 1
        self.last_expression_tick = run.t
        self.queue.append({"deliver": run.t + self.delay, "to": "A2", "kind": kind, "value": value, "expression": ev["id"]})

    # ------------------------------------------------------------------------------------------------ per tick
    def step(self, run: Any) -> None:
        due = [q for q in self.queue if q["deliver"] <= run.t]
        self.queue = [q for q in self.queue if q["deliver"] > run.t]
        for q in due:
            if q["to"] == "A2":
                self._receive(run, q)
            else:
                self._answer(run, q)

    def _receive(self, run: Any, q: dict) -> None:
        if not run.ent["A2"]["present"]:
            return
        kind = q["kind"]
        confirmed = self.meas_eff < 1.0 - self.verify if kind == "scarcity" else self.meas_eff > 1.0 + self.verify
        if self.mode == "expression":  # claims are made and paid for; nobody answers
            return
        self._pay(run, self.cost)
        resp = run._event(
            "response",
            "A2",
            answer="agree" if confirmed else "disagree",
            claim=kind,
            measured_efficiency=round(self.meas_eff, 4),
            expression=q["expression"],
        )
        self.counts["response"] += 1
        self.a2_trust[kind][0 if confirmed else 1] += 1
        self.queue.append(
            {
                "deliver": run.t + self.delay,
                "to": "A1",
                "kind": kind,
                "confirmed": confirmed,
                "response": resp["id"],
                "expression": q["expression"],
            }
        )
        if self.mode == "revision":
            self._infer_and_revise(run, kind, confirmed, resp)

    def _infer_and_revise(self, run: Any, kind: str, confirmed: bool, resp: dict) -> None:
        """Norm-sensitive update and inferential transition on A2's side: from the claim and its own measurement it infers the shortfall; it acts only if the
        claimant's record for that kind of claim meets the norm."""
        trust = self.reliability(self.a2_trust[kind])
        inf = run._event(
            "inference",
            "A2",
            premises=["claim:" + kind, f"measured efficiency {self.meas_eff:.3f}"],
            conclusion="renewals reach the field at that efficiency",
            response=resp["id"],
        )
        self.counts["inference"] += 1
        if kind != "scarcity" or not confirmed or trust < self.norm:
            return
        new = float(np.clip(1.0 / max(self.meas_eff, 0.2), 1.0, 2.5))
        if abs(new - self.boost) > 1e-6:
            run._event(
                "revision",
                "A2",
                action="raise renewal amount",
                boost_from=round(self.boost, 4),
                boost_to=round(new, 4),
                trust=round(trust, 4),
                inference=inf["id"],
            )
            self.counts["revision"] += 1
            self.boost = new

    def _answer(self, run: Any, q: dict) -> None:
        """Score update (A1's ledger) and, in revision mode, correction after a mismatch and withholding of an unreliable kind."""
        kind = q["kind"]
        self.a1_ledger[kind][0 if q["confirmed"] else 1] += 1
        rel = self.reliability(self.a1_ledger[kind])
        sc = run._event(
            "score",
            "A1",
            claim=kind,
            confirmed=q["confirmed"],
            reliability=round(rel, 4),
            ledger=list(self.a1_ledger[kind]),
            response=q["response"],
        )
        self.counts["score"] += 1
        if self.mode != "revision":
            return
        if not q["confirmed"]:
            d = float(run.ent["A1"]["d"])
            run._event(
                "correction",
                "A1",
                action="recalibrate expectation",
                expected_from=round(float(self.exp_d or 0.0), 4),
                expected_to=round(d, 4),
                score=sc["id"],
            )
            self.counts["correction"] += 1
            self.recent[:] = [d] * min(len(self.recent), 3)  # the expectation is rebuilt from what was actually observed
        if rel < self.withhold_below:
            self.withheld_until[kind] = run.t + self.quiet
            run._event("withhold", "A1", claim=kind, until=run.t + self.quiet, reliability=round(rel, 4), score=sc["id"])

    def trace_columns(self) -> dict[str, float]:
        return {
            "phil_expressions": float(self.counts["expression"]),
            "phil_power_spent": float(self.counts["power"]),
            "phil_boost": float(self.boost),
            "phil_reliability_scarcity": self.reliability(self.a1_ledger["scarcity"]),
            "phil_trust_scarcity": self.reliability(self.a2_trust["scarcity"]),
            "phil_measured_efficiency": float(self.meas_eff),
        }
