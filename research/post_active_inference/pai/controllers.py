"""Controllers acting on the benchmark world through the same sensors and the same actuator interface.

* ``AIFController`` — discrete Active Inference using the vendored math (posterior, VFE, EFE with pragmatic and
  epistemic terms, softmax policy selection). Generative model: N_LEVELS hidden levels of the target region's
  activity, N_LEVELS observation levels (quantiles of the aggregate sensor reading in calibration), five
  one-step policies (the actions). A (likelihood) and B (policy-conditioned transitions) are Dirichlet counts from
  the calibration phase, where the true level is available — the way a designer specifies a model. C prefers the
  current goal level (setpoint schedule, world.setpoint); D and E are uniform.

  ``fixed``     A, B frozen after calibration (a stationary generative model).
  ``adaptive``  online Dirichlet learning of A and B from inferred states, with forgetting, plus a
                surprise-triggered structural rebuild: when mean surprise over 5 decisions exceeds the
                pre-onset mean + 3 standard errors, the observation partition is re-estimated from recent
                readings, A is reset to its designer prior and B counts are shrunk. This is structure-learning-lite;
                conditions it handles are reported as overlap, not as novelty.

  Ablations (non-redundancy tests), applied to the adaptive variant:
      no_latent           q = one-hot(o): no latent-state inference
      no_model            B uniform and never learned: no transition model
      no_prediction_error no learning from prediction errors after calibration (rebuild still active)
      no_free_energy      no surprise (free-energy) triggered rebuild (learning still active)
      no_efe_epistemic    policies scored by the pragmatic term only
      no_policy           uniformly random action (no policy selection)
      no_agent            no persisting controller state: prior = D at every decision, no learning, no rebuild
      (no_boundary is a world option: channels and actuator sample the whole field; see world.BenchWorld)

* ``MeasuredEffectController`` — model-light: works on the raw aggregate reading, keeps a recency-weighted
  measured effect (reading change) per action, and picks the action whose measured effect moves the reading
  closest to the goal's target reading (calibration quantile at the centre of the goal level). No levels,
  latent states, transition model or policy evaluation.
* ``NoControl`` (always noop), ``RandomControl``.
"""
from __future__ import annotations

import numpy as np

from .aif_vendor import posterior, select, vfe
from .world import ACTIONS, N_LEVELS, PREFERRED_LEVEL, aggregate, level_of

NA = len(ACTIONS)
GAMMA = 4.0
DIRICHLET = 0.5
FORGET = 0.98
SURPRISE_WINDOW = 5
BASELINE_DECISIONS = 15
REBUILD_Z = 3.0
COOLDOWN = 10


def _edges(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return np.linspace(0, 1, N_LEVELS + 1)[1:-1]
    e = np.quantile(x, np.linspace(0, 1, N_LEVELS + 1)[1:-1])
    for i in range(1, len(e)):  # strictly increasing edges
        if e[i] <= e[i - 1]:
            e[i] = e[i - 1] + 1e-9
    return e


class _Model:
    def __init__(self):
        self.nP = NA
        self.a_counts = np.full((N_LEVELS, N_LEVELS), DIRICHLET)
        self.b_counts = np.full((NA, N_LEVELS, N_LEVELS), DIRICHLET)
        self.E = np.full(NA, 1.0 / NA)
        self.D = np.full(N_LEVELS, 1.0 / N_LEVELS)
        self.set_goal(PREFERRED_LEVEL)
        self.uniform_B = False

    def set_goal(self, level: int) -> None:
        """C: log-preferences over observation levels, peaked at the goal level."""
        c = -2.0 * np.abs(np.arange(N_LEVELS) - level).astype(float)
        self.C = c - np.log(np.exp(c).sum())

    @property
    def A(self):
        return self.a_counts / self.a_counts.sum(0, keepdims=True)

    @property
    def B(self):
        if self.uniform_B:
            return np.full((NA, N_LEVELS, N_LEVELS), 1.0 / N_LEVELS)
        return self.b_counts / self.b_counts.sum(1, keepdims=True)


class Controller:
    name = "base"
    has_model = False

    def calibrate(self, calib: dict) -> None: ...

    def decide(self, x: np.ndarray, s_true: int | None, t: int, goal: int = PREFERRED_LEVEL) -> int:
        raise NotImplementedError

    def summary(self) -> dict:
        return {}


class NoControl(Controller):
    name = "none"

    def decide(self, x, s_true, t, goal=PREFERRED_LEVEL):
        return 0


class RandomControl(Controller):
    name = "random"

    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed * 31 + 7)

    def decide(self, x, s_true, t, goal=PREFERRED_LEVEL):
        return int(self.rng.integers(NA))


class AIFController(Controller):
    has_model = True

    def __init__(self, variant: str = "adaptive", ablation: str | None = None, seed: int = 0):
        self.variant, self.ablation = variant, ablation
        self.name = f"aif_{variant}" + (f"-{ablation}" if ablation else "")
        self.rng = np.random.default_rng(seed * 131 + 11)
        self.m = _Model()
        self.q = self.m.D.copy()
        self.prev_a: int | None = None
        self.prev_o: int | None = None
        self.prev_q: np.ndarray | None = None
        self.hist: list[dict] = []       # per decision
        self.surprise: list[float] = []
        self.rebuilds: list[int] = []
        self.last_rebuild = -10**9
        self.readings: list[float] = []
        self.failed_inference = 0
        self.numerical = 0
        self.missing = 0
        self.invalidations = 0
        self.comparator_errors = 0
        self.qs: list[np.ndarray] = []
        self.actions: list[int] = []

    # ------------------------------------------------------------------ calibration
    def calibrate(self, calib: dict) -> None:
        self.obs_edges = _edges(calib["readings"])
        self.centers = self._centers(np.asarray(calib["readings"]), self.obs_edges)
        o = [level_of(x, self.obs_edges) for x in calib["readings"]]
        s = calib["levels"]
        a = calib["actions"]
        for i in range(len(o)):
            if o[i] is not None and s[i] is not None:
                self.m.a_counts[o[i], s[i]] += 1
        for i in range(len(s) - 1):
            if s[i] is not None and s[i + 1] is not None:
                self.m.b_counts[a[i], s[i + 1], s[i]] += 1
        self.a_prior = self.m.a_counts.copy()
        if self.ablation == "no_model":
            self.m.uniform_B = True

    @staticmethod
    def _centers(x: np.ndarray, edges: np.ndarray) -> np.ndarray:
        x = x[np.isfinite(x)]
        lv = np.searchsorted(edges, x, side="right")
        c = np.array([x[lv == k].mean() if np.any(lv == k) else np.nan for k in range(N_LEVELS)])
        idx = np.arange(N_LEVELS)
        ok = np.isfinite(c)
        return np.interp(idx, idx[ok], c[ok]) if ok.any() else idx.astype(float)

    # ------------------------------------------------------------------ one decision
    def decide(self, x: np.ndarray, s_true: int | None, t: int, goal: int = PREFERRED_LEVEL) -> int:
        try:
            self.m.set_goal(goal)
            return self._decide(x, s_true, t)
        except Exception as e:  # noqa: BLE001 - comparator failure: logged and counted, the run continues with noop
            self.comparator_errors += 1
            self.hist.append({"t": t, "error": repr(e)[:200]})
            return 0

    def _decide(self, x: np.ndarray, s_true: int | None, t: int) -> int:
        m = self.m
        agg = aggregate(x)
        self.readings.append(agg)
        o = level_of(agg, self.obs_edges)
        persist = self.ablation != "no_agent"
        if self.prev_a is not None and persist:
            prior = m.B[self.prev_a] @ self.q
        else:
            prior = m.D.copy()
        A = m.A
        rec: dict = {"t": t, "o": o, "s": s_true, "agg": agg}
        pred_o = A @ prior
        rec["pred_o"] = pred_o.tolist()
        rec["pred_reading"] = float(pred_o @ self.centers)
        rec["channel_pe"] = np.abs(np.where(np.isfinite(x), x, np.nan) - rec["pred_reading"]).tolist()
        if o is None:  # no observation available: belief propagates, no update
            self.missing += 1
            q = prior
            rec.update(F=None, surprise=None)
        else:
            if (A[o, :] * prior).sum() <= 0:
                self.failed_inference += 1
            q = np.eye(N_LEVELS)[o] if self.ablation == "no_latent" else posterior(A, prior, o)
            F = vfe(A, prior, q, o)
            sur = float(-np.log((A[o, :] * prior).sum() + 1e-16))
            rec.update(F=F, surprise=sur)
            if not (np.all(np.isfinite(q)) and np.isfinite(F)):
                self.numerical += 1
                q = m.D.copy()
            self.surprise.append(sur)
            # online learning (adaptive only)
            if self.variant == "adaptive" and self.ablation not in ("no_prediction_error", "no_agent", "no_model"):
                m.a_counts = DIRICHLET + FORGET * (m.a_counts - DIRICHLET)
                m.a_counts[o] += q
                if self.prev_a is not None and self.prev_q is not None:
                    b = m.b_counts[self.prev_a]
                    m.b_counts[self.prev_a] = DIRICHLET + FORGET * (b - DIRICHLET) + np.outer(q, self.prev_q)
            if self.variant == "adaptive" and self.ablation not in ("no_free_energy", "no_agent"):
                self._maybe_rebuild(t)
        # policy invalidation: expected direction of the previous action vs realised change
        if self.prev_o is not None and o is not None and self.hist and self.hist[-1].get("exp_shift") is not None:
            es = self.hist[-1]["exp_shift"]
            real = o - self.prev_o
            if abs(es) >= 0.5 and abs(real) >= 1 and np.sign(es) != np.sign(real):
                self.invalidations += 1
                rec["invalidation"] = True
        # policy selection
        if self.ablation == "no_policy":
            a = int(self.rng.integers(NA))
            rec.update(G=None, G_min=None, policy_entropy=float(np.log(NA)))
        else:
            sel = select(m, q, GAMMA)
            G = np.array([s["G"] for s in sel["scores"]])
            if self.ablation == "no_efe_epistemic":
                G = np.array([-s["pragmatic"] for s in sel["scores"]])
                lg = np.log(m.E) - GAMMA * G
                pp = np.exp(lg - lg.max())
                pp /= pp.sum()
                a = int(np.argmax(pp))
            else:
                pp = sel["policy_posterior"]
                a = int(sel["chosen"])
            if not np.all(np.isfinite(G)):
                self.numerical += 1
                a = 0
            rec.update(G=float(G[a]), G_min=float(G.min()), epistemic=float(sel["scores"][a]["epistemic"]),
                       policy_entropy=float(-(pp * np.log(pp + 1e-16)).sum()))
        po = m.A @ (m.B[a] @ q)
        rec["exp_shift"] = float(po @ np.arange(N_LEVELS) - (m.A @ q) @ np.arange(N_LEVELS))
        rec["a"] = a
        rec["q_argmax"] = int(np.argmax(q))
        self.hist.append(rec)
        self.prev_q, self.q = q, q
        self.prev_a, self.prev_o = a, o
        self.qs.append(q.copy())
        self.actions.append(a)
        return a

    def _maybe_rebuild(self, t: int) -> None:
        s = self.surprise
        if len(s) < BASELINE_DECISIONS + SURPRISE_WINDOW:
            return
        base = np.asarray(s[:BASELINE_DECISIONS])
        mu, sd = base.mean(), base.std(ddof=1) + 1e-6
        recent = np.mean(s[-SURPRISE_WINDOW:])
        if recent > mu + REBUILD_Z * sd / np.sqrt(SURPRISE_WINDOW) and t - self.last_rebuild >= COOLDOWN * 10:
            r = np.asarray(self.readings[-20:])
            r = r[np.isfinite(r)]
            if len(r) >= 10 and np.ptp(r) > 0:
                self.obs_edges = _edges(r)
                self.centers = self._centers(r, self.obs_edges)
            self.m.a_counts = self.a_prior.copy()
            self.m.b_counts = DIRICHLET + 0.1 * (self.m.b_counts - DIRICHLET)
            self.rebuilds.append(t)
            self.last_rebuild = t

    def multi_step_predictions(self, k: int = 3) -> list[tuple[int, list[float]]]:
        """(decision index i+k, predicted observation distribution) from the belief at i and the executed actions
        i … i+k−1, with the final model (documented approximation: B and A as at the end of the run)."""
        out = []
        A, B = self.m.A, self.m.B
        for i in range(len(self.qs) - k):
            qs = self.qs[i]
            for j in range(k):
                qs = B[self.actions[i + j]] @ qs
            out.append((i + k, (A @ qs).tolist()))
        return out

    def summary(self) -> dict:
        return {"rebuilds": self.rebuilds, "failed_inference": self.failed_inference, "numerical": self.numerical,
                "missing_observations": self.missing, "invalidations": self.invalidations,
                "comparator_errors": self.comparator_errors}


class MeasuredEffectController(Controller):
    name = "ost"

    def __init__(self, seed: int = 0, alpha: float = 0.25, eps: float = 0.05):
        self.rng = np.random.default_rng(seed * 137 + 13)
        self.alpha, self.eps = alpha, eps
        self.effect = np.zeros(NA)
        self.prev_x: float | None = None
        self.prev_a: int | None = None
        self.hist: list[dict] = []

    def calibrate(self, calib: dict) -> None:
        x = np.asarray(calib["readings"], float)
        a = np.asarray(calib["actions"])
        self.obs_edges = _edges(x)
        # target reading per goal level: the calibration reading quantile at the centre of that level
        self.targets = [float(np.nanquantile(x, (k + 0.5) / N_LEVELS)) for k in range(N_LEVELS)]
        for k in range(NA):
            d = [x[i + 1] - x[i] for i in range(len(x) - 1) if a[i] == k and np.isfinite(x[i]) and np.isfinite(x[i + 1])]
            self.effect[k] = float(np.mean(d)) if d else 0.0

    def decide(self, x: np.ndarray, s_true: int | None, t: int, goal: int = PREFERRED_LEVEL) -> int:
        agg = aggregate(x)
        target = self.targets[goal]
        rec: dict = {"t": t, "agg": agg, "s": s_true, "o": level_of(agg, self.obs_edges)}
        if self.prev_x is not None and self.prev_a is not None and np.isfinite(agg) and np.isfinite(self.prev_x):
            d = agg - self.prev_x
            self.effect[self.prev_a] += self.alpha * (d - self.effect[self.prev_a])
        if self.hist and self.hist[-1].get("pred_reading") is not None:
            rec["pred_prev"] = self.hist[-1]["pred_reading"]
        if not np.isfinite(agg):
            a = 0
            rec["pred_reading"] = None
        else:
            if self.rng.random() < self.eps:
                a = int(self.rng.integers(NA))
            else:
                a = int(np.argmin(np.abs(agg + self.effect - target)))
            rec["pred_reading"] = float(agg + self.effect[a])
        rec["channel_pe"] = (np.abs(x - rec["pred_prev"]).tolist() if rec.get("pred_prev") is not None
                             else [float("nan")] * len(x))
        rec["a"] = a
        self.hist.append(rec)
        self.prev_x, self.prev_a = (agg if np.isfinite(agg) else self.prev_x), a
        return a


def make(spec: str, seed: int) -> Controller:
    """``none`` | ``random`` | ``ost`` | ``aif_fixed`` | ``aif_adaptive`` | ``aif_adaptive-<ablation>``."""
    if spec == "none":
        return NoControl()
    if spec == "random":
        return RandomControl(seed)
    if spec in ("ost", "ost-no_boundary"):
        return MeasuredEffectController(seed)
    base, _, abl = spec.partition("-")
    if base in ("aif_fixed", "aif_adaptive"):
        if abl == "no_boundary":
            abl = ""
        return AIFController(base.split("_")[1], abl or None, seed)
    raise ValueError(spec)


ABLATIONS = ("no_latent", "no_model", "no_prediction_error", "no_free_energy", "no_efe_epistemic", "no_policy",
             "no_agent", "no_boundary")
