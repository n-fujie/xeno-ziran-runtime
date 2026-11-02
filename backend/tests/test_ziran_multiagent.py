"""Staged load of the shared laboratory with many scientific systems. This checks that the software scales and stays
deterministic and replayable; it makes no statement about how autonomous any system is."""

from __future__ import annotations

import pytest

pytest.importorskip("mujoco")

from xzr.lab.population import KINDS, STAGES, population  # noqa: E402
from xzr.lab.record import LabRun  # noqa: E402
from xzr.lab.replay import replay  # noqa: E402


def _cfg(n: int, steps: int = 40) -> dict:
    return {"gen_seed": 8000, "seed": 80000, "settings": None, "physics": True, "horizon": steps,
            "systems": population(n)}


def test_population_is_deterministic_heterogeneous_and_unique():
    a, b = population(300), population(300)
    assert a == b
    assert len({d["sid"] for d in a}) == 300 and {d["kind"] for d in a} == set(KINDS)
    assert any(d["revise_observation"] for d in a) and any(not d["revise_observation"] for d in a)
    assert population(20) == a[:20]  # stages are prefixes: a smaller stage is the start of a larger one
    with pytest.raises(ValueError):
        population(0)


@pytest.mark.parametrize("n", STAGES)
def test_stage_runs_every_system_and_is_deterministic(n):
    fingerprints = []
    for _ in range(2):
        r = LabRun(_cfg(n))
        for _ in range(40):
            r.step()
        assert len(r.science.systems) == n
        rec = r.record()
        fingerprints.append([s["fingerprint"] for s in rec["steps"]])
        assert all(st.budget >= -1e-9 for st in r.science.systems.values())  # no system spends beyond its budget
    assert fingerprints[0] == fingerprints[1]


@pytest.mark.parametrize("n", (20, 100))
def test_stage_record_replays_in_this_environment(n):
    r = LabRun(_cfg(n, 30))
    for _ in range(30):
        r.step()
    out = replay(r.record())
    assert out["agreement"], out["first_mismatches"]
