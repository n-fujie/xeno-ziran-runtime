"""Experiment configurations: bundled presets and validation of user configuration files.

An experiment configuration (``schema: xzr.experiment/1``) is JSON with:

    id, kind ("conditions" | "history"), description, question, manipulated, fixed, measured, does_not_show
    seeds                 number of engine seeds (seed0, seed0 + 1, …)
    seed0                 first engine seed (optional, default 100)
    kind "conditions":    baseline  — overrides of the escalation reference condition (xzr.experiments.escalation)
                          conditions — [{"id": ..., "changed": {overrides}}]; each condition = baseline + changed
    kind "history":       history   — overrides of xzr.experiments.history.DEFAULTS

``effective()`` expands a configuration into exactly what runs (every condition fully specified); that expansion is
what a result records. Unknown keys are errors, so a misspelt setting can never be ignored silently.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

SCHEMA = "xzr.experiment/1"
TOP_KEYS = {"schema", "id", "kind", "description", "question", "manipulated", "fixed", "measured", "does_not_show",
            "seeds", "seed0", "baseline", "conditions", "history"}
DOC_KEYS = ("description", "question", "manipulated", "fixed", "measured", "does_not_show")
MAX_SEEDS = 16  # the exact sign-flip test enumerates 2^seeds sign patterns


class ConfigError(ValueError):
    """An experiment configuration that cannot run; the message names the offending field."""


def names() -> list[str]:
    return sorted(p.name[:-5] for p in resources.files(__package__).iterdir() if p.name.endswith(".json"))


def load(name_or_path: str) -> dict:
    """A preset by name, or a configuration file by path."""
    path = Path(name_or_path)
    if path.suffix == ".json" or path.exists():
        if not path.exists():
            raise ConfigError(f"configuration file not found: {path}")
        text = path.read_text()
    else:
        if name_or_path not in names():
            raise ConfigError(f"unknown preset {name_or_path!r}; presets: {', '.join(names())}")
        text = resources.files(__package__).joinpath(f"{name_or_path}.json").read_text()
    try:
        cfg = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"not valid JSON: {e}") from e
    validate(cfg)
    return cfg


def validate(cfg: Any) -> None:
    from ..experiments.escalation.harness import REFERENCE
    from ..experiments.history import DEFAULTS

    if not isinstance(cfg, dict):
        raise ConfigError("a configuration is a JSON object")
    unknown = set(cfg) - TOP_KEYS
    if unknown:
        raise ConfigError(f"unknown field(s): {', '.join(sorted(unknown))}")
    if cfg.get("schema") != SCHEMA:
        raise ConfigError(f"schema must be {SCHEMA!r}")
    if not isinstance(cfg.get("id"), str) or not cfg["id"].strip():
        raise ConfigError("id must be a non-empty string")
    if cfg.get("kind") not in ("conditions", "history"):
        raise ConfigError("kind must be 'conditions' or 'history'")
    seeds = cfg.get("seeds")
    if not isinstance(seeds, int) or isinstance(seeds, bool) or not 1 <= seeds <= MAX_SEEDS:
        raise ConfigError(f"seeds must be an integer between 1 and {MAX_SEEDS}")
    if "seed0" in cfg and (not isinstance(cfg["seed0"], int) or cfg["seed0"] < 0):
        raise ConfigError("seed0 must be a non-negative integer")
    if cfg["kind"] == "conditions":
        base = cfg.get("baseline", {})
        if not isinstance(base, dict):
            raise ConfigError("baseline must be an object")
        bad = set(base) - set(REFERENCE)
        if bad:
            raise ConfigError(f"baseline: unknown setting(s) {', '.join(sorted(bad))}")
        conds = cfg.get("conditions")
        if not isinstance(conds, list) or not conds:
            raise ConfigError("conditions must be a non-empty list")
        seen = set()
        for i, c in enumerate(conds):
            if not isinstance(c, dict) or not isinstance(c.get("id"), str):
                raise ConfigError(f"conditions[{i}] must be an object with an 'id'")
            if c["id"] in seen:
                raise ConfigError(f"conditions[{i}]: duplicate id {c['id']!r}")
            seen.add(c["id"])
            if _is_full(c):  # the expanded form printed by `xzr validate`, possibly edited
                bad = set(c) - set(REFERENCE) - {"id", "changed", "seeds"}
                if bad:
                    raise ConfigError(f"conditions[{i}] ({c['id']}): unknown setting(s) {', '.join(sorted(bad))}")
                continue
            if set(c) - {"id", "changed"}:
                raise ConfigError(f"conditions[{i}] must be {{'id': str, 'changed': {{...}}}} or a full condition")
            ch = c.get("changed", {})
            if not isinstance(ch, dict) or set(ch) - set(REFERENCE):
                raise ConfigError(f"conditions[{i}] ({c['id']}): unknown setting(s) "
                                  f"{', '.join(sorted(set(ch) - set(REFERENCE))) if isinstance(ch, dict) else ch}")
        for c in effective(cfg)["conditions"]:
            _check_condition(c)
    else:
        h = cfg.get("history", {})
        if not isinstance(h, dict) or set(h) - set(DEFAULTS):
            raise ConfigError(f"history: unknown setting(s) {', '.join(sorted(set(h) - set(DEFAULTS)))}")
        e = effective(cfg)["history"]
        if not e["operation_at"] < e["reactivate_at"] < e["horizon"] or not e["operation_at"] < e["probe_at"] < e["horizon"]:
            raise ConfigError("history: need operation_at < reactivate_at < horizon and operation_at < probe_at < horizon")
        if not set(e["operations"]) <= {"fork", "remove", "reactivate", "migrate"}:
            raise ConfigError("history.operations ⊆ {fork, remove, reactivate, migrate}")
        if not 100 <= e["n"] <= 100_000:
            raise ConfigError("history.n must be between 100 and 100,000")


def _check_condition(c: dict) -> None:
    from ..runtime.flags import Flags
    from ..scenario.topologies import MEMORY_REGIMES, TOPOLOGIES

    where = f"condition {c['id']!r}"
    if not isinstance(c["n"], int) or not 100 <= c["n"] <= 100_000:
        raise ConfigError(f"{where}: n must be an integer between 100 and 100,000")
    if not isinstance(c["horizon"], int) or not 50 <= c["horizon"] <= 100_000:
        raise ConfigError(f"{where}: horizon must be an integer between 50 and 100,000")
    if c["topology"] not in TOPOLOGIES and c["topology"] != "multi_region":
        raise ConfigError(f"{where}: topology must be one of multi_region, {', '.join(TOPOLOGIES)}")
    if c["memory"] not in MEMORY_REGIMES:
        raise ConfigError(f"{where}: memory must be one of {', '.join(MEMORY_REGIMES)}")
    if c["coupling"] not in ("weak", "medium", "strong"):
        raise ConfigError(f"{where}: coupling must be weak, medium or strong")
    variants = c["variants"]
    if not isinstance(variants, list | tuple) or "C" not in variants:
        raise ConfigError(f"{where}: variants must be a list that includes the reference 'C'")
    fv = c.get("flag_variants")
    if fv:
        missing = set(variants) - set(fv)
        if missing:
            raise ConfigError(f"{where}: variants without flags: {', '.join(sorted(missing))}")
        for name, flags in fv.items():
            try:
                Flags.from_dict(flags)
            except (TypeError, ValueError) as e:
                raise ConfigError(f"{where}: flag variant {name!r}: {e}") from e
    elif set(variants) - set("ABCDEFGHIJK"):
        raise ConfigError(f"{where}: variants are letters A–K (see docs/EXPERIMENTS.md) unless flag_variants is set")


def effective(cfg: dict, seeds: int | None = None, seed0: int | None = None) -> dict:
    """The configuration exactly as it runs: every condition fully expanded; overrides applied."""
    from ..experiments.escalation.harness import REFERENCE, condition
    from ..experiments.history import DEFAULTS

    out = {k: cfg[k] for k in ("schema", "id", "kind", *DOC_KEYS) if k in cfg}
    out["seeds"] = seeds if seeds is not None else cfg["seeds"]
    out["seed0"] = seed0 if seed0 is not None else cfg.get("seed0", 100)
    if cfg["kind"] == "conditions":
        base = {**REFERENCE, **cfg.get("baseline", {})}
        out["baseline"] = _plain(base)
        conds = []
        for c in cfg["conditions"]:
            if _is_full(c):
                over = {k: v for k, v in c.items() if k in REFERENCE}
                full = condition(**{**over, "id": c["id"]})
                full["changed"] = sorted(k for k in over if k not in ("seeds", "id") and _plain(over[k]) != _plain(base.get(k)))
            else:
                ch = c.get("changed", {})
                full = condition(**{**cfg.get("baseline", {}), **ch, "id": c["id"]})
                full["changed"] = sorted(ch)
            full["seeds"] = out["seeds"]
            conds.append(_plain(full))
        out["conditions"] = conds
    else:
        out["history"] = {**DEFAULTS, **cfg.get("history", {}), "seeds": out["seeds"], "seed0": out["seed0"]}
    return out


def _is_full(c: dict) -> bool:
    """A fully specified condition (as printed by ``effective``) rather than {"id", "changed"}."""
    return "n" in c and "horizon" in c


def _plain(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_plain(v) for v in x]
    return x
