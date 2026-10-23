"""Three things a "boundary change" can be, told apart by what they touch and how a difference reaches the world.

1. display range        which cells a record shows (``reachability.levels`` computes the observable cells without feeding anything back): the world
                        is untouched by construction; checked, not assumed.
2. observation boundary what an operation can see (instrument scale / penetration): the world changes only *through* the operations' acts, so
                        a difference in acts precedes any difference in the world.
3. interaction structure the gates and veils the engine applies (``settings.boundary``): the world's own dynamics change, and the world can
                        differ before any operation has acted differently.

For each: the first step at which the world's state differs from the control, the first step at which the operations' acts differ, and which came
first. Changing the state space or the operation grammar would change what a stored record means; none of the three does (the settings keys are the
existing ones, validated by the field), and that is recorded.
"""

from __future__ import annotations

import numpy as np

from ..hpo import experiments as X
from ..hpo import reconfig
from ..hpo.field import DEFAULTS, Field
from ..hpo.reachability import levels


def _run(
    settings: dict, base, seed: int, steps: int, changes: list[dict] | None = None, probe_levels: bool = False
) -> tuple[list[str], list[tuple]]:
    f = Field(base.fork(), settings, seed, keep_states=False)
    for ch in changes or []:
        reconfig.apply(f, ch, [])
    fps, acts = [], []
    seen = 0
    for t in range(steps):
        f.step()
        if probe_levels and t % 10 == 0:
            levels(f)  # a display: reads, never writes
        fps.append(f.world.engine.fingerprint())
        ev = [e for e in f.history.events[seen:] if e["type"] == "act"]
        seen = len(f.history.events)
        acts.append(tuple(sorted((e["source"], tuple(e.get("detail", {}).get("requests", []))) for e in ev)))
    return fps, acts


def _first(a: list, b: list) -> int | None:
    return next((i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y), None)


def classify(steps: int = 120, gen: int = 7600, seed: int = 76000) -> dict:
    base = X._warm({"n": 800, "regime": "intermittent"}, gen, seed, 40)
    s = X.settings_for("D", {"warmup": 40, "horizon": steps})
    ctl_fp, ctl_acts = _run(s, base, seed, steps)
    variants = {
        "display range": {
            "settings": s,
            "changes": [],
            "probe": True,
            "touches": "the record only (observable cells computed, nothing fed back)",
        },
        "observation boundary": {
            "settings": s,
            "probe": False,
            "touches": "instrument scale of the closure operation (level 2, window 6)",
            "changes": [{"path": "instruments.closure.level", "value": 2}, {"path": "instruments.closure.window", "value": 6}],
        },
        "interaction structure": {
            "settings": {**s, "boundary": {"veil_scale": 1.0, "gate_scale": 1.8}},
            "changes": [],
            "probe": False,
            "touches": "engine gates (settings.boundary.gate_scale 1.8)",
        },
    }
    out = {}
    for name, v in variants.items():
        fp, acts = _run(v["settings"], base, seed, steps, v["changes"], v["probe"])
        w, a = _first(ctl_fp, fp), _first(ctl_acts, acts)
        order = (
            "the world and the acts agree throughout"
            if w is None and a is None
            else "the acts differ first (mediated by the operations)"
            if a is not None and (w is None or a <= w)
            else "the world differs first (direct change of the dynamics)"
        )
        out[name] = {
            "touches": v["touches"],
            "first_world_difference_step": w,
            "first_act_difference_step": a,
            "order": order,
            "world_differs_at_end": bool(fp[-1] != ctl_fp[-1]),
        }
    out["state_space_and_grammar"] = {
        "settings_keys_changed": [],
        "boundary_keys": sorted(DEFAULTS["boundary"]),
        "note": "no setting, state array or operation rule was added or altered: stored records keep their meaning; each variant is an existing, validated setting or a sandboxed change",
        "numpy": np.__version__,
    }
    return out
