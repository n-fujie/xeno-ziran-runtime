"""A matched comparison of the two XB-TRO presets of domain 004 (Dictionary entry 060: matched morphology, control and environment; dictionary.D8).

``human-like-planar`` and ``machine-like-planar`` differ in 33 of their 73 configuration entries, so a difference between their results is a difference between PRESETS. Here the configuration is split into five blocks and ONE block at
a time is taken from the other preset, in both directions:

* structure: ``foot``, ``joints``, ``lines``, ``links`` (the body's mechanical make-up and its operation lines)
* control: ``neural`` (gains, strategy, wind-up, gravity compensation, motor noise)
* sensors: ``sensors`` (noise levels, the visual gain)
* internal: ``internal`` (fatigue, breathing, activation cost, capacity floor)
* time step: ``task.dt`` (0.01 against 0.005 s)

(``name`` and ``family`` are labels.) The two plain presets are run as controls, with the same seeds and grid as ``experiments_body.json``, so that they must reproduce it. The class reuses ``BodyDomain`` and ``run_domain`` unchanged (same
grid, same seeds, same effect definitions); it is NOT registered in the domain registry, so no record, condition list or status of the laboratory changes.

What this can and cannot say. A swapped block is taken with its values tuned for the OTHER body: a combination can fall for reasons of coherence (control gains of one body on the links of another) and not because of the block's own nature,
and the effects of the blocks need not add up (interactions are not separated: only single swaps are run, not all combinations). A change of an effect is read against the interval over the seeds. The interval uses the Student t value of the
number of seeds (the ``aggregate`` of ``lab.py`` uses the value for 20 seeds, 2.093, whatever the number of seeds, which is too narrow for the 6 seeds of a body run: this module does not use it). Nothing here concerns a thinking subject,
knowledge or a Gaisho."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import MODEL_VERSION
from .domains import BodyDomain
from .lab import FULL, run_domain, t975
from .model import digest

BLOCKS: dict[str, dict[str, Any]] = {
    "structure": {"top": ("foot", "joints", "lines", "links")},
    "control": {"top": ("neural",)},
    "sensors": {"top": ("sensors",)},
    "internal": {"top": ("internal",)},
    "time step": {"step": True},
}
LABELS = ("name", "family")  # entries of the presets that are names, not parameters
PRESETS = {"human": "human-like-planar", "machine": "machine-like-planar"}
HUMAN, MACHINE = "human-like planar body", "machine-like planar body"


def condition_name(base: str, block: str) -> str:
    donor = "machine-like" if base == "human" else "human-like"
    return f"{base}-like planar body with the {block} of the {donor} one"


def _conditions() -> dict[str, dict[str, Any]]:
    conds: dict[str, dict[str, Any]] = {HUMAN: {"preset": PRESETS["human"], "donor": None, "block": None}, MACHINE: {"preset": PRESETS["machine"], "donor": None, "block": None}}
    for base, other in (("human", "machine"), ("machine", "human")):
        for block in BLOCKS:
            conds[condition_name(base, block)] = {"preset": PRESETS[base], "donor": PRESETS[other], "block": block}
    return conds


def t_interval(values: list[float]) -> dict[str, Any]:
    n = len(values)
    m = float(np.mean(values))
    if n < 2:
        return {"mean": m, "n": n, "ci95": None}
    se = float(np.std(values, ddof=1)) / np.sqrt(n)
    t = t975(n)
    return {"mean": m, "n": n, "ci95": [m - t * se, m + t * se], "t": t}


def flat(d: dict, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        out.update(flat(v, prefix + k + ".") if isinstance(v, dict) else {prefix + k: v})
    return out


def covered_keys(block: str) -> tuple[str, ...]:
    spec = BLOCKS[block]
    return ("task.dt",) if spec.get("step") else tuple(spec["top"])


class MatchedBodyDomain(BodyDomain):
    """BodyDomain whose conditions are single-block swaps between the two presets (not registered)."""

    conditions = _conditions()  # type: ignore[assignment]
    default_conditions = (HUMAN, MACHINE)

    def base_config(self, cond: str) -> dict:
        spec = self.conditions[cond]
        cfg = copy.deepcopy(self.link.config.build(spec["preset"]))
        if spec["donor"] is None:
            return cfg
        donor = self.link.config.build(spec["donor"])
        block = BLOCKS[spec["block"]]
        if block.get("step"):
            cfg["task"]["dt"] = donor["task"]["dt"]
        else:
            for top in block["top"]:
                cfg[top] = copy.deepcopy(donor[top])
        return cfg


def uncovered_differences(dom: MatchedBodyDomain) -> list[str]:
    """Configuration entries in which the presets differ and that no block swaps (labels excepted): must be empty for the blocks to cover the difference."""
    a, b = flat(dom.link.config.build(PRESETS["human"])), flat(dom.link.config.build(PRESETS["machine"]))
    keys = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k) and k not in LABELS]
    cov = [c for blk in BLOCKS for c in covered_keys(blk)]
    return [k for k in keys if not any(k == c or k.startswith(c + ".") for c in cov)]


def _summarize(dom: MatchedBodyDomain, res: dict[str, Any], seeds: list[int], describe: Any, controls: dict[str, str], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """``controls`` maps the preset name of each plain-preset control condition to that condition's name; every other condition is read against the control of its base preset."""
    out: dict[str, Any] = {}
    for cond, v in res["conditions"].items():
        rel = {n: ({"status": r["status"], **t_interval(r["per_seed"])} if r["status"] == "IDENTIFIED" else {"status": r["status"]}) for n, r in v["relations"].items()}
        cells = v["snapshots"]["end"]["cells"]
        grid = [[next(c["p"] for c in cells if c["i"] == i and c["j"] == j) for i in range(len(dom.x_values))] for j in range(len(dom.y_values))]
        out[cond] = {**describe(dom.conditions[cond]), "relations": rel, "fell_share_grid": grid, "mean_fell_share": float(np.mean(grid))}
    for cond, o in out.items():  # the change of each effect against its own base preset, and whether the base value lies inside the interval of the swap
        if cond in controls.values():
            continue
        base = out[controls[o["base"]]]
        d: dict[str, Any] = {}
        for n in ("effect_x", "effect_y"):
            if o["relations"][n]["status"] == "IDENTIFIED" and base["relations"][n]["status"] == "IDENTIFIED":
                ci = o["relations"][n]["ci95"]
                diff = o["relations"][n]["mean"] - base["relations"][n]["mean"]
                d[n] = {"change": diff, "swap_ci95": ci, "base_inside_swap_ci95": bool(ci is not None and ci[0] <= base["relations"][n]["mean"] <= ci[1])}
        o["change_against_base"] = d
    body = {"model_version": MODEL_VERSION, "seeds": list(seeds), "axes": {"x": dom.x_name, "y": dom.y_name}, "body": dom.provenance(), "blocks": {k: list(covered_keys(k)) for k in BLOCKS}, "uncovered_differences": uncovered_differences(dom), "result_digest": res["digest"], "conditions": out, **(extra or {})}
    return {**body, "digest": digest(body)}


def run_matched(seeds: list[int]) -> dict[str, Any]:
    dom = MatchedBodyDomain()
    res = run_domain(dom, FULL, tuple(seeds), list(dom.conditions))
    return _summarize(dom, res, seeds, lambda spec: {"base": spec["preset"], "donor": spec["donor"], "block": spec["block"]}, {PRESETS["human"]: HUMAN, PRESETS["machine"]: MACHINE})


# ---------------------------------------------------------------------------------------------------------- the extension: combinations of swaps, other integration steps, 8 seeds
DTS = (0.0025, 0.005, 0.01, 0.02)  # the two presets use 0.01 (human-like) and 0.005 s (machine-like)
COMBINATIONS: dict[str, tuple[str, ...]] = {
    "structure and control": ("structure", "control"),
    "structure and sensors": ("structure", "sensors"),
    "structure and internal model": ("structure", "internal"),
    "everything but the time step": ("structure", "control", "sensors", "internal"),
}


def _dt_name(base: str, dt: float) -> str:
    return f"{base}-like planar body at the integration step {dt} s"


def _combo_name(base: str, label: str) -> str:
    return f"{base}-like planar body with the {label} of the {'machine' if base == 'human' else 'human'}-like one"


def _extended_conditions() -> dict[str, dict[str, Any]]:
    conds: dict[str, dict[str, Any]] = {HUMAN: {"preset": PRESETS["human"], "donor": None, "blocks": (), "dt": None}, MACHINE: {"preset": PRESETS["machine"], "donor": None, "blocks": (), "dt": None}}
    own = {"human": 0.01, "machine": 0.005}
    for base, other in (("human", "machine"), ("machine", "human")):
        for dt in DTS:
            if dt != own[base]:
                conds[_dt_name(base, dt)] = {"preset": PRESETS[base], "donor": None, "blocks": (), "dt": dt}
        for label, blocks in COMBINATIONS.items():
            conds[_combo_name(base, label)] = {"preset": PRESETS[base], "donor": PRESETS[other], "blocks": blocks, "dt": None}
    return conds


class ExtendedMatchedDomain(MatchedBodyDomain):
    """BodyDomain whose conditions are combinations of block swaps and other integration steps (not registered)."""

    conditions = _extended_conditions()  # type: ignore[assignment]

    def base_config(self, cond: str) -> dict:
        spec = self.conditions[cond]
        cfg = copy.deepcopy(self.link.config.build(spec["preset"]))
        if spec["donor"] is not None:
            donor = self.link.config.build(spec["donor"])
            for blk in spec["blocks"]:
                for top in BLOCKS[blk]["top"]:
                    cfg[top] = copy.deepcopy(donor[top])
        if spec["dt"] is not None:
            cfg["task"]["dt"] = spec["dt"]
        return cfg


def run_extended(seeds: list[int]) -> dict[str, Any]:
    """Combinations of block swaps, other integration steps and 8 seeds, with the two plain presets as controls (same grid and effect definitions as ``run_matched``).

    XB-TRO REFUSES to run a configuration whose explicit integration step is numerically unstable for its passive joint dynamics ("must not be read as a falling body"). Such a condition is not run and is not counted as a fall: it is listed under ``refused_by_xbtro`` with the amplification the check found."""
    dom = ExtendedMatchedDomain()
    refused, runnable = {}, []
    for cond in dom.conditions:
        ns = dom.link.engine.Params(dom.base_config(cond)).numeric_stability()
        if ns["stable"]:
            runnable.append(cond)
        else:
            refused[cond] = {"largest_step_amplification": float(ns["margin"]), "fastest_mode_hz": float(ns["fastest_mode_hz"]), "meaning": "not run; XB-TRO's stability check refuses it. This is neither a fall nor a result about the body"}
    res = run_domain(dom, FULL, tuple(seeds), runnable)
    return _summarize(dom, res, seeds, lambda spec: {"base": spec["preset"], "donor": spec["donor"], "blocks": list(spec["blocks"]), "dt": spec["dt"]}, {PRESETS["human"]: HUMAN, PRESETS["machine"]: MACHINE}, {"refused_by_xbtro": refused})
