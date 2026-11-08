"""A live body: the simulator advanced in small steps, with three kinds of values kept strictly apart in every frame.

* ``reference``   the model's own state (joint angles, torques, muscle drive, centre of pressure, energy, which operation lines are
                  active). Simulator-internal: it is not something any observation device sees.
* ``observation`` the outputs of the deployed observation models only: sampled at their own rate, delayed, noisy, with dropouts and
                  blind windows (missing samples are ``None``). Stored apart from the reference; changing the observation never changes
                  the body.
* ``estimates``   what the simulated controller itself believes (``controller``: the fused COM position / velocity from its delayed,
                  noisy senses) — a model estimate, neither the reference nor an observation.

Changing the observation configuration while running does not rewrite the past: a model that is added starts blind until now, a model
that is removed is retired from now on, and a model whose settings change is retired and replaced by a new one. Interventions edit the
configuration values only (they do not touch the random streams). Nothing here is measured physiology.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import config, engine, metrics, observation

MAX_HORIZON_S = 60.0
INF_T = 1e9


def _list(x: np.ndarray, nd: int = 6) -> Any:
    """Rounded nested lists for JSON; a value that is not a finite number (a diverged run) is None, never NaN."""
    a = np.asarray(x, dtype=float)
    if a.ndim == 0:
        return None if not np.isfinite(a) else round(float(a), nd)
    return _nan_to_none(np.where(np.isfinite(a), np.round(a, nd), np.nan).tolist())


def _nan_to_none(v: Any) -> Any:
    if isinstance(v, list):
        return [_nan_to_none(x) for x in v]
    if isinstance(v, float) and v != v:
        return None
    return v


class BodySession:
    def __init__(
        self,
        preset: str = "human-like-planar",
        overrides: dict[str, Any] | None = None,
        seeds: list[int] | None = None,
        obs: dict[str, Any] | None = None,
        horizon_s: float = 30.0,
        xeno14_ids: list[str] | None = None,
    ) -> None:
        if not 1.0 <= horizon_s <= MAX_HORIZON_S:
            raise config.ConfigError(f"horizon_s must be within 1..{MAX_HORIZON_S:g}")
        over = copy.deepcopy(overrides or {})
        over.setdefault("task", {})["horizon"] = horizon_s
        self.preset = preset
        self.cfg = config.build(preset, over)
        if xeno14_ids:
            from . import xeno14

            self.cfg = config.validate(xeno14.apply(self.cfg, xeno14_ids))
        self.seeds = list(seeds or [1])
        self.obs = observation.validate(obs or observation.config("motion+emg+contact"), len(self.cfg["links"]))
        self.sim = engine.Sim(self.cfg, self.seeds)
        self.log: list[dict[str, Any]] = [{"t": 0.0, "event": "created", "preset": preset, "seeds": self.seeds}]
        self._sent: dict[str, int] = {}  # per observation model: samples already delivered
        self._retired: dict[str, float] = {}
        self._deployed: dict[str, float] = {}  # models added while running: nothing before this time was observed by them

    # ------------------------------------------------------------------------------------------ description
    def info(self) -> dict[str, Any]:
        cfg = self.cfg
        P = self.sim.p
        up = np.concatenate([[0.0], np.cumsum(P.length)[:-1]])
        return {
            "preset": self.preset,
            "family": cfg["family"],
            "name": cfg["name"],
            "seeds": self.seeds,
            "dt": P.dt,
            "horizon_s": cfg["task"]["horizon"],
            "links": [
                {
                    "id": ln["id"],
                    "label": ln["label"],
                    "region": ln["region"],
                    "length": ln["length"],
                    "mass": ln["mass"],
                    "com_frac": ln["com_frac"],
                }
                for ln in cfg["links"]
            ],
            "joints": [
                {"id": j["id"], "label": j["label"], "tau_max": j["tau_max"], "q_range": j["q_range"]} for j in cfg["joints"]
            ],
            "foot": cfg["foot"],
            "base_of_support_m": [-cfg["foot"]["heel"], cfg["foot"]["toe"]],
            "link_base_height": up.tolist(),
            "lines": [
                {
                    "id": ln["id"],
                    "label": ln["label"],
                    "kind": ln["kind"],
                    "enabled": ln["enabled"],
                    "timescale_s": ln["timescale_s"],
                    "ignition": ln["ignition"],
                    "resource": ln.get("resource"),
                    "observable_by": ln.get("observable_by", []),
                }
                for ln in cfg["lines"]
            ],
            "task": cfg["task"],
            "xeno14": cfg.get("xeno14", []),
            "observation": self.obs,
            "coverage": observation.coverage(cfg, self.obs),
            "numeric_stability": P.numeric_stability(),
            "tolerance_band_m": metrics.band(cfg),
            "labels": {
                "reference": "model state (simulator-internal; not an observation)",
                "observation": "output of a simulated observation model (separate from the reference)",
                "estimates": "what the simulated controller believes (a model estimate)",
            },
        }

    @property
    def t(self) -> float:
        return self.sim.step_i * self.sim.p.dt

    @property
    def finished(self) -> bool:
        return self.sim.step_i >= self.sim.T or not self.sim.alive.any()

    # ------------------------------------------------------------------------------------------ stepping
    def step(self, n: int = 5) -> dict[str, Any]:
        if n < 1:
            raise config.ConfigError("n must be at least 1")
        i0 = self.sim.step_i
        taken = self.sim.advance(int(n))
        i1 = self.sim.step_i
        run = self.sim.finish()
        frames = self._frames(run, i0, i1)
        obs_out = self._observation_delta(run)
        return {
            "t0": i0 * run.dt,
            "t1": i1 * run.dt,
            "steps": taken,
            "frames": frames,
            "observation": obs_out,
            "status": self.status(run),
            "finished": self.finished,
        }

    def status(self, run: engine.Run | None = None) -> dict[str, Any]:
        run = run or self.sim.finish()
        return {
            "t": self.t,
            "alive": self.sim.alive.tolist(),
            "fell": np.isfinite(self.sim.fall_t).tolist(),
            "diverged": self.sim.diverged.tolist(),
            "fall_time": [None if not np.isfinite(x) else float(x) for x in self.sim.fall_t],
            "energy": self.sim.energy.tolist(),
            "fatigue": self.sim.fatigue.tolist(),
        }

    def _frames(self, run: engine.Run, i0: int, i1: int) -> list[dict[str, Any]]:
        out = []
        for k in range(i0, i1):
            net = run["act"][:, k, :, 0] - run["act"][:, k, :, 1]
            out.append(
                {
                    "t": k * run.dt,
                    "reference": {
                        "theta": _list(run["theta"][:, k]),
                        "omega": _list(run["omega"][:, k]),
                        "q": _list(run["q"][:, k]),
                        "tau": _list(run["tau"][:, k], 3),
                        "drive": _list(net, 4),
                        "cocontraction": _list(run["cc"][:, k], 4),
                        "com": _list(run["com"][:, k]),
                        "vcom": _list(run["vcom"][:, k]),
                        "cop": _list(run["cop"][:, k]),
                        "normal_force": _list(run["fn"][:, k], 2),
                        "energy": _list(run["energy"][:, k], 5),
                        "fatigue": _list(run["fatigue"][:, k], 5),
                        "capacity": _list(run["cap"][:, k], 4),
                        "xref": _list(run["xref_true"][:, k]),
                        "adaptation_gain": _list(run["kc"][:, k], 4),
                        "push_force": _list(run["push_force"][:, k], 2),
                        "slip": run["slip"][:, k].astype(int).tolist(),
                        "alive": run["alive"][:, k].astype(int).tolist(),
                        "lines_active": run["line_active"][:, k].astype(int).tolist(),
                        "line_command": _list(np.abs(run["line_u"][:, k]).sum(axis=2), 4),
                    },
                    "estimates": {
                        "controller": {
                            "com": _list(run["xhat"][:, k]),
                            "com_velocity": _list(run["vhat"][:, k]),
                            "reference_it_works_towards": _list(run["xref_ctrl"][:, k]),
                        }
                    },
                }
            )
        return out

    def _observation_delta(self, run: engine.Run) -> dict[str, Any]:
        outs = observation.observe(run, self.obs)
        res: dict[str, Any] = {}
        for mid, o in outs.items():
            if mid not in self._sent:  # a model added while running starts from its deployment time
                self._sent[mid] = int(np.searchsorted(o["t"], self._deployed.get(mid, 0.0), side="left"))
            sent = self._sent[mid]
            ns = len(o["t"])
            if ns <= sent:
                continue
            x = o["x"][:, sent:ns, :]
            res[mid] = {
                "kind": o["kind"],
                "channels": o["channels"],
                "t": _list(o["t"][sent:ns]),
                "available_at": _list(o["t"][sent:ns] + o["delay_s"]),
                "x": _nan_to_none(np.where(np.isfinite(x), np.round(x, 6), np.nan).tolist()),
                "sample_hz": o["sample_hz"],
                "spatial": o["spatial"],
                "retired_from_t": self._retired.get(mid),
                "label": "observation",
            }
            self._sent[mid] = ns
        return res

    # ------------------------------------------------------------------------------------------ interventions
    def _set_config(self, cfg: dict[str, Any], event: dict[str, Any]) -> None:
        cfg = config.validate(cfg)
        self.sim.set_config(cfg)  # raises ConfigError if the new configuration is numerically unstable; nothing is changed then
        self.cfg = cfg
        self.log.append({"t": self.t, **event})

    def apply(self, intervention: str, magnitude: float | None = None) -> dict[str, Any]:
        """Apply one of the seven interventions from now on. (Edits to configuration values; the body's history is kept.)"""
        new = config.apply_intervention(self.cfg, intervention, magnitude)
        if intervention == "perturbation":
            # a live push acts now, not at the protocol's time
            new = copy.deepcopy(self.cfg)
            f = float(magnitude if magnitude is not None else config.INTERVENTIONS["perturbation"]["default"])
            new["environment"]["pushes"] = [
                *new["environment"]["pushes"],
                {"t": round(self.t + 0.02, 3), "dur": 0.12, "force": f, "link": 2, "point_frac": 0.8, "role": "intervention"},
            ]
        elif intervention == "posture_change":
            new = copy.deepcopy(self.cfg)  # a live posture change displaces the body now
            d = float(magnitude if magnitude is not None else config.INTERVENTIONS["posture_change"]["default"])
            self.sim.theta = self.sim.theta + d
            self.log.append({"t": self.t, "event": "posture displaced", "lean_rad": d})
        elif intervention == "visual_block":
            new = copy.deepcopy(self.cfg)
            end = float(magnitude) if magnitude else INF_T
            new["sensors"]["visual"]["blocked_windows"] = [
                *new["sensors"]["visual"].get("blocked_windows", []),
                [self.t, max(end, self.t)],
            ]
        self._set_config(new, {"event": "intervention", "id": intervention, "magnitude": magnitude})
        return {"t": self.t, "applied": intervention, "magnitude": magnitude}

    def set_line(self, line_id: str, enabled: bool) -> dict[str, Any]:
        new = copy.deepcopy(self.cfg)
        ln = config.line_by_id(new, line_id)
        ln["enabled"] = bool(enabled)
        self._set_config(new, {"event": "line", "id": line_id, "enabled": bool(enabled)})
        return {"t": self.t, "line": line_id, "enabled": bool(enabled)}

    def set_xeno14(self, ids: list[str]) -> dict[str, Any]:
        from . import xeno14

        new = xeno14.apply(self.cfg, ids)
        # the arrays have a fixed number of lines: only a set of principles that adds no new line can be switched on in a running body
        if [ln["id"] for ln in new["lines"]] != [ln["id"] for ln in self.cfg["lines"]]:
            raise config.ConfigError(
                "changing the Xeno-14 set adds or removes operation lines; start a new body with that set (a running body keeps its lines)"
            )
        self._set_config(new, {"event": "xeno14", "ids": ids})
        return {"t": self.t, "xeno14": ids}

    def set_observation(self, new_obs: dict[str, Any]) -> dict[str, Any]:
        """Replace the observation configuration from now on, keeping the history of what the earlier models delivered."""
        new_obs = observation.validate(new_obs, len(self.cfg["links"]))
        t = self.t
        old = {m["id"]: m for m in self.obs["models"]}
        models = []
        for m in new_obs["models"]:
            o = old.get(m["id"])
            if o is None:  # added: blind until now
                m = copy.deepcopy(m)
                self._deployed[m["id"]] = t
                m["blind_windows"] = [*m.get("blind_windows", []), [0.0, t]] if t > 0 else m.get("blind_windows", [])
                models.append(m)
            elif {k: v for k, v in o.items() if k not in ("blind_windows", "effects_on")} == {
                k: v for k, v in m.items() if k not in ("blind_windows", "effects_on")
            }:
                models.append(o)  # unchanged: keep as it is (and its history)
            else:  # settings changed: retire the old one, deploy a new one from now
                r = copy.deepcopy(o)
                r["blind_windows"] = [*r.get("blind_windows", []), [t, INF_T]]
                self._retired[r["id"]] = t
                models.append(r)
                nm = copy.deepcopy(m)
                nm["id"] = f"{m['id']}@{t:.2f}"
                self._deployed[nm["id"]] = t
                nm["blind_windows"] = [*nm.get("blind_windows", []), [0.0, t]]
                models.append(nm)
        for mid, o in old.items():
            if mid not in {m["id"] for m in new_obs["models"]}:  # removed: retired from now on, its past output stays
                r = copy.deepcopy(o)
                r["blind_windows"] = [*r.get("blind_windows", []), [t, INF_T]]
                self._retired[mid] = t
                models.append(r)
        merged = {**new_obs, "models": models}
        self.obs = observation.validate(merged, len(self.cfg["links"]))
        # a different apparatus changes the body only through its declared effects; those apply from the next step on
        self.log.append(
            {
                "t": t,
                "event": "observation reconfigured",
                "models": [m["id"] for m in self.obs["models"]],
                "retired": dict(self._retired),
            }
        )
        return {"t": t, "models": [m["id"] for m in self.obs["models"]], "coverage": observation.coverage(self.cfg, self.obs)}

    # ------------------------------------------------------------------------------------------ inspection
    def inspect(self, part: str, seconds: float = 5.0, seed_index: int = 0) -> dict[str, Any]:
        """What the model says about one part: its reference values, the operation lines that drive it, the observation models that
        cover it (and whether anything is observed there), and its recent history. Parts: link:<id>, joint:<id>, ground, neural, internal."""
        run = self.sim.finish()
        cfg = self.cfg
        kind, _, pid = part.partition(":")
        cov = observation.coverage(cfg, self.obs)
        k1 = run["com"].shape[1]
        k0 = max(0, k1 - int(round(seconds / run.dt)))
        t = (np.arange(k0, k1) * run.dt).tolist()
        if kind == "link":
            idx = next((i for i, ln in enumerate(cfg["links"]) if ln["id"] == pid), None)
            if idx is None:
                raise config.ConfigError(f"no link {pid!r}")
            region = cfg["links"][idx]["region"]
            series = {
                "angle_rad": _list(run["theta"][seed_index, k0:k1, idx]),
                "angular_rate": _list(run["omega"][seed_index, k0:k1, idx]),
            }
            now: dict[str, Any] = {k: (v[-1] if v else None) for k, v in series.items()}  # nothing recorded yet: no value
            cols = [idx]
        elif kind == "joint":
            idx = next((i for i, j in enumerate(cfg["joints"]) if j["id"] == pid), None)
            if idx is None:
                raise config.ConfigError(f"no joint {pid!r}")
            region = cfg["links"][idx]["region"]
            series = {
                "joint_angle_rad": _list(run["q"][seed_index, k0:k1, idx]),
                "torque_Nm": _list(run["tau"][seed_index, k0:k1, idx], 3),
                "muscle_drive": _list(run["act"][seed_index, k0:k1, idx, 0] - run["act"][seed_index, k0:k1, idx, 1], 4),
                "cocontraction": _list(run["cc"][seed_index, k0:k1, idx], 4),
            }
            now = {k: (v[-1] if v else None) for k, v in series.items()}  # nothing recorded yet: no value, not an error
            cols = [idx]
        elif kind in ("ground", "neural", "internal"):
            region = kind
            idx = None
            if kind == "ground":
                series = {
                    "centre_of_pressure_m": _list(run["cop"][seed_index, k0:k1]),
                    "normal_force_N": _list(run["fn"][seed_index, k0:k1], 2),
                    "push_force_N": _list(run["push_force"][seed_index, k0:k1], 2),
                }
            elif kind == "internal":
                series = {
                    "energy": _list(run["energy"][seed_index, k0:k1], 5),
                    "fatigue": _list(run["fatigue"][seed_index, k0:k1], 5),
                    "adaptation_gain": _list(run["kc"][seed_index, k0:k1], 4),
                }
            else:
                series = {
                    "controller_com_estimate_m": _list(run["xhat"][seed_index, k0:k1]),
                    "controller_reference_m": _list(run["xref_ctrl"][seed_index, k0:k1]),
                }
            now = {k: (v[-1] if v else None) for k, v in series.items()}  # nothing recorded yet: no value, not an error
            cols = []
        else:
            raise config.ConfigError("part must be link:<id>, joint:<id>, ground, neural or internal")
        lines = []
        for j, lid in enumerate(run.line_ids):
            ln = next(x for x in cfg["lines"] if x["id"] == lid)
            have = k1 > k0  # nothing recorded yet: the fractions are 0, not NaN
            drive = float(np.abs(run["line_u"][seed_index, k0:k1, j][:, cols]).mean()) if cols and have else 0.0
            frac = float(run["line_active"][seed_index, k0:k1, j].mean()) if have else 0.0
            touches = drive > 1e-6 or (
                kind in ("ground", "neural", "internal")
                and ln["kind"] in {"ground": ("environment",), "neural": ("neural", "sensory"), "internal": ("internal",)}[kind]
            )
            if touches:
                lines.append(
                    {
                        "id": lid,
                        "label": ln["label"],
                        "enabled": ln["enabled"],
                        "active_fraction": frac,
                        "mean_command_here": drive,
                        "timescale_s": ln["timescale_s"],
                        "ignition": ln["ignition"],
                        "resource": ln.get("resource"),
                    }
                )
        covering = [
            m
            for m in self.obs["models"]
            if m["id"] in cov["regions"].get(region, []) or any(mid == m["id"] for mid in cov["regions"].get(region, []))
        ]
        return {
            "part": part,
            "region": region,
            "kind": "reference values (model state)",
            "now": now,
            "t": t,
            "series": series,
            "lines": lines,
            "observation": {
                "covered": bool(covering),
                "models": [
                    {
                        "id": m["id"],
                        "kind": m["kind"],
                        "sample_hz": m["sample_hz"],
                        "noise": m["noise"],
                        "delay_s": m["delay_s"],
                        "dropout": m["dropout"],
                        "spatial": m.get("spatial"),
                        "blind_windows": m.get("blind_windows", []),
                    }
                    for m in covering
                ],
                "unobserved": region in cov["unobserved_regions"],
            },
            "note": "Reference values are the model's own state; an observation model sees them only through its own rate, delay, noise, dropouts and boundary.",
        }

    def snapshot(self) -> dict[str, Any]:
        return {"info": self.info(), "status": self.status(), "log": self.log}

    def record(self) -> engine.Run:
        return self.sim.finish()
