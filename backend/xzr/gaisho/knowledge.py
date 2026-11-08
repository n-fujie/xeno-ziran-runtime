"""001 Knowledge-Gaisho: the candidate is the NON-ACCIDENTALITY of a judgement, studied as operations of a synthetic judging agent. Knowledge, a knowledge Gaisho, the accuracy of a judgement, epistemic justification and
counterfactual stability are not the same thing; this module measures operations and reconstructs relations between them, and it computes no attribution.

The world: a hidden binary state w (+1 with probability pi); an evidence channel E = w + sigma x noise (downstream of w); a coincidental cue S that equals w with probability q in this environment (it is NOT downstream of w).
The agent judges J in {-1,+1} with probability sigmoid(a E + b S + c); an agent may learn from feedback on the true state (a delta rule). The conditions are the four of the brief (accidental correct, ground-responsive,
misjudgement, correction and reconfiguration) with two kinds of accidental correctness (a base-rate guess; a coincidental cue) and a correction condition with and without the feedback. The environment is set so that the agents
that are CORRECT BY COINCIDENCE have the same accuracy as the ground-responsive agent: accuracy is what the conditions share and the interventions are what tells them apart.

Interventions on the agent: do(E) and do(S) over a grid (the response surface P(J=+1 | E, S)); do(W) (a balanced world with the cue decoupled: the counterfactual stability of correctness); a shift of the environment (the cue
decouples at the middle of the run); the feedback (the correction); the memory (the agent's weights at three moments). Nothing here says what the 'non-accidental core' is: the relations that differ between conditions are
reported as candidates and the question whether a core exists is left to the comparison.
"""

from __future__ import annotations

import numpy as np

from .lab import Domain, Observation, classify_unobserved, record_surface, surface_effects
from .model import digest

T_TRIALS = 400
SHIFT_AT = 200
SNAP_TRIALS = {"start": 0, "before shift": SHIFT_AT - 10, "end": T_TRIALS}
ENVIRONMENTS = {
    "default": {"pi": 0.9, "sigma": 0.78, "q": 0.9, "q_after": 0.5},
    "cue decoupled from the start": {"pi": 0.9, "sigma": 0.78, "q": 0.5, "q_after": 0.5},
    "harder evidence (sigma 1.2)": {"pi": 0.9, "sigma": 1.2, "q": 0.9, "q_after": 0.5},
    "balanced world (pi 0.5)": {"pi": 0.5, "sigma": 0.78, "q": 0.9, "q_after": 0.5},
}


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class KnowledgeDomain(Domain):
    id = "001-knowledge"
    title = "KNOWLEDGE — NON-ACCIDENTAL SUCCESS AS AN OPERATIONAL DIFFERENCE"
    x_name, y_name = "evidence E (do)", "coincidental cue S (do)"
    outcome_meaning = "the agent judges +1: P(J = +1 | do(E = x), do(S = y)) = sigmoid(a x + b y + c) with the agent's weights (a, b, c) at the moment of the snapshot, estimated by the share of n trials per cell. It is the response of the agent's decision rule to the two interventions, not the correctness of its judgement."
    x_values = np.linspace(-3.0, 3.0, 13)
    y_values = np.linspace(-1.5, 1.5, 7)
    snapshots = ("start", "before shift", "end")
    relation_names = ("effect_E", "effect_S", "stability_do_W", "shift_drop", "revision_E", "revision_S")
    conditions = {
        "accidental correct: base-rate guess": {"a": 0.0, "b": 0.0, "c": 2.5, "lr": 0.0},
        "accidental correct: coincidental cue": {"a": 0.0, "b": 2.5, "c": 0.0, "lr": 0.0},
        "ground-responsive judgement": {"a": 2.5, "b": 0.0, "c": 0.0, "lr": 0.0},
        "misjudgement: miscalibrated reading": {"a": 2.5, "b": 0.0, "c": -2.25, "lr": 0.0},
        "correction and reconfiguration (feedback on)": {"a": 0.3, "b": 2.5, "c": 0.0, "lr": 0.08},
        "no correction (feedback off)": {"a": 0.3, "b": 2.5, "c": 0.0, "lr": 0.0},
    }

    def _streams(self, seed: int) -> dict[str, np.random.Generator]:
        names = ("world", "evidence", "cue", "decision", "surface", "stability", "recording", "probe")
        return dict(zip(names, (np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(len(names))), strict=True))

    def simulate(self, cond: str, seed: int, obs: Observation) -> dict:
        p = self.conditions[cond]
        env = ENVIRONMENTS[obs.environment]
        rg = self._streams(seed)
        T = T_TRIALS
        w = np.where(rg["world"].uniform(size=T) < env["pi"], 1, -1)
        sig = float(np.hypot(env["sigma"], obs.probe))  # an observer that probes adds to the noise of the evidence the agent reads: a change of the operation, not of the record
        E = w + sig * rg["evidence"].normal(size=T)
        flip = rg["cue"].uniform(size=(2, T))
        cue_ok = np.where(np.arange(T) < SHIFT_AT, flip[0] < env["q"], flip[1] < env["q_after"])
        S = np.where(cue_ok, w, -w)
        u = rg["decision"].uniform(size=T)
        a, b, c, lr = p["a"], p["b"], p["c"], p["lr"]
        J = np.zeros(T, dtype=int)
        snaps_w: dict[str, dict] = {"start": {"a": a, "b": b, "c": c}}
        for t in range(T):
            z = a * E[t] + b * S[t] + c
            pj = float(sigmoid(z))
            J[t] = 1 if u[t] < pj else -1
            if lr > 0:
                err = (1.0 if w[t] == 1 else 0.0) - pj
                a, b, c = a + lr * err * E[t], b + lr * err * S[t], c + lr * err
            if obs.probe > 0:
                dw = rg["probe"].normal(size=3) * 0.05 * obs.probe
                a, b, c = a + dw[0], b + dw[1], c + dw[2]
            if t + 1 == SNAP_TRIALS["before shift"]:
                snaps_w["before shift"] = {"a": a, "b": b, "c": c}
        snaps_w["end"] = {"a": a, "b": b, "c": c}
        correct = w == J
        acc = float(correct.mean())
        win = max(1, min(obs.temporal_window, 100))
        pre, post = float(correct[SHIFT_AT - win:SHIFT_AT].mean()), float(correct[SHIFT_AT:SHIFT_AT + win].mean())
        kept = {nm: i for i, nm in enumerate(self.snapshots) if i % max(1, obs.speed) == 0}
        n = max(1, obs.temporal_window)
        snaps: dict[str, dict] = {}
        true_effects: dict[str, dict] = {}
        for nm in self.snapshots:
            wt = snaps_w[nm]
            pz = sigmoid(wt["a"] * self.x_values[None, :] + wt["b"] * self.y_values[:, None] + wt["c"])
            raw = rg["surface"].binomial(n, pz) / n
            full = surface_effects(record_surface(self, pz, Observation(temporal_window=10_000), rg["recording"]), 12, 0, 6, 0)
            true_effects[nm] = full
            stab = self._stability(wt, sig, env, 10 * n, rg["stability"])
            if nm not in kept:
                continue
            rec = record_surface(self, raw, obs, rg["recording"])
            snaps[nm] = {"surface": rec, "weights": ({k: float(v) for k, v in wt.items()} if obs.memory else None), "stability": stab}
        step = float((self.x_values[1] - self.x_values[0]) * obs.scale)
        width = self._width(np.asarray(sigmoid(snaps_w["end"]["a"] * self.x_values + snaps_w["end"]["c"])))
        rels = self._relations(snaps, true_effects, pre, post, obs, step, width, T)
        return {"accuracy": acc, "accuracy_pre_shift": float(correct[:SHIFT_AT].mean()), "snapshots": snaps, "relations": rels, "operation_digest": digest({"J": J.tolist(), "w": w.tolist(), "weights": snaps_w}), "series": {"correct": correct.astype(int).tolist()}}

    @staticmethod
    def _width(p: np.ndarray) -> float | None:
        """The width (in units of E) over which the response goes from 10 % to 90 % of its range; None where there is no transition."""
        if p.max() - p.min() < 0.3:
            return None
        xs = np.linspace(-3, 3, 13)
        lo, hi = p.min() + 0.1 * (p.max() - p.min()), p.min() + 0.9 * (p.max() - p.min())
        inside = xs[(p > lo) & (p < hi)]
        return float(max(inside.max() - inside.min(), 0.25)) if inside.size else 0.25

    def _stability(self, wt: dict, sigma: float, env: dict, m: int, rng: np.random.Generator) -> float:
        """do(W): a balanced world, the evidence regenerated from it, the cue decoupled from it. The share of correct judgements: the counterfactual stability of the correctness."""
        w = np.where(rng.uniform(size=m) < 0.5, 1, -1)
        E = w + sigma * rng.normal(size=m)
        S = np.where(rng.uniform(size=m) < 0.5, 1, -1)
        pj = sigmoid(wt["a"] * E + wt["b"] * S + wt["c"])
        J = np.where(rng.uniform(size=m) < pj, 1, -1)
        return float((w == J).mean())

    def _relations(self, snaps: dict, true_effects: dict, pre: float, post: float, obs: Observation, step: float, width: float | None, T: int) -> dict:
        rel: dict[str, dict] = {}

        def one(name: str, value, needs: dict, true_mag: float | None, feature_width=None) -> None:
            detectable = true_mag is None or (1 - 2 * obs.sensor_noise) * abs(true_mag) >= 0.1
            why = classify_unobserved(name, needs, obs, detectable, feature_width, step)
            rel[name] = {"status": why or "IDENTIFIED", "value": None if why else value}

        end = snaps.get("end")
        eff = surface_effects(end["surface"], 12, 0, 6, 0) if end else {"effect_x": None, "effect_y": None}
        # the surface is read at the recorded grid points: with a coarser scale the high and the low end may not be recorded
        if end:
            nx, ny = end["surface"]["nx"], end["surface"]["ny"]
            hi_x, lo_x = max(i for i in range(nx) if i % max(1, obs.scale) == 0), 0
            hi_y, lo_y = max(j for j in range(ny) if j % max(1, obs.scale) == 0), 0
            eff = surface_effects(end["surface"], hi_x, lo_x, hi_y, lo_y)
        one("effect_E", eff["effect_x"], {"axes": ("x",), "separate_axes": True, "min_window": 20}, true_effects["end"]["effect_x"], width)
        one("effect_S", eff["effect_y"], {"axes": ("y",), "separate_axes": True, "min_window": 20}, true_effects["end"]["effect_y"])
        one("stability_do_W", (snaps["end"]["stability"] if end else None), {"axes": (), "min_window": 20}, None)
        one("shift_drop", pre - post, {"axes": (), "min_window": 20}, None)
        need_s = {"axes": ("x",), "snapshots": True, "separate_axes": True, "min_window": 20, "time_constant_snapshots": 3}
        st = snaps.get("start")
        if st and end:
            es = surface_effects(st["surface"], 12, 0, 6, 0)
            one("revision_E", (eff["effect_x"] - es["effect_x"]) if eff["effect_x"] is not None and es["effect_x"] is not None else None, need_s, true_effects["end"]["effect_x"] - true_effects["start"]["effect_x"], width)
            one("revision_S", (eff["effect_y"] - es["effect_y"]) if eff["effect_y"] is not None and es["effect_y"] is not None else None, {**need_s, "axes": ("y",)}, true_effects["end"]["effect_y"] - true_effects["start"]["effect_y"])
        else:
            for nm in ("revision_E", "revision_S"):
                rel[nm] = {"status": "UNMEASURED" if not obs.memory else "TEMPORAL_MISFIT", "value": None}
        return rel
