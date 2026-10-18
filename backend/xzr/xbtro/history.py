"""Historical re-entry, repeat and re-analysis of stored experiment records.

Three operations, each recorded as a new record whose ``history.parent`` names the record it came from:

* ``rerun``       repeat an experiment from its stored settings. The digest of a repeat on the same platform is identical.
* ``reanalyse``   observe the stored *simulated* trajectories again under another observation configuration (same bodies, same
                  seeds). This is re-observation of a simulation, not re-measurement of a body: nothing new about a real body is learned.
* ``reenter``     hand the retained slow state at the end of a stored run (fatigue, energy, adaptation gain, tensions, sediment) to a
                  later experiment as its starting state, so that what happened before changes how the later operations ignite and
                  what they can reach. The carried state is stored in the new record so that it can be repeated.
"""

from __future__ import annotations

import copy
from typing import Any

from . import MODEL_VERSION, engine, experiments, observation, records, tro


class HistoryError(ValueError):
    pass


def rerun(rec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if rec["rerun"]["experiment"] not in experiments.EXPERIMENTS:
        raise HistoryError(
            f"record {rec['id']} ({rec['rerun']['experiment']}) is a derived record and has no experiment to repeat; repeat its parent instead"
        )
    new, slow = experiments.run_to_end(rec["rerun"]["experiment"], copy.deepcopy(rec["rerun"]["parameters"]))
    new["history"] = {**new.get("history", {}), "parent": rec["id"], "operation": "rerun"}
    new["history"]["same_digest_as_parent"] = new["digest"] == rec["digest"]
    return new, slow


def reanalyse_steps(rec: dict[str, Any], obs: dict[str, Any]):
    """Generator form of ``reanalyse`` (yields progress between the two simulations, for hosts that run jobs in time slices)."""
    pair = (rec.get("results") or {}).get("pair")
    if not pair:
        raise HistoryError(
            f"record {rec['id']} does not store a pair of body conditions; only A, E and M records can be re-analysed"
        )
    obs = observation.validate(obs)
    ra = yield from _sim(pair["a"], rec["seeds"], 0.0, 0.5)
    rb = yield from _sim(pair["b"], rec["seeds"], 0.5, 0.95)
    rows = tro.assess(ra, rb, obs)
    summ = tro.summarize(rows)
    from .experiments import STATUS_COLUMNS, status_rows, table, unobserved_entries

    res = {
        "tables": [
            table(
                "reanalysis",
                "Identifiability under the new observation configuration (same simulated bodies, same seeds)",
                STATUS_COLUMNS,
                status_rows(rows, obs["name"]),
            )
        ],
        "summary": summ,
        "pair": pair,
        "re_observation_of_a_simulation": True,
        "reading": "The stored bodies are simulated; observing them again is not a new measurement of any real body.",
    }
    out = records.make_record(
        "RE",
        {"parent": rec["id"], "observation": obs["name"]},
        rec["seeds"],
        pair["a"],
        [obs],
        rec.get("interventions", []),
        res,
        [],
        unobserved_entries(rows, obs["name"]),
        {"reentry": [{"from": rec["id"], "kind": "re-observation"}], "parent": rec["id"], "operation": "reanalyse"},
        pair["a"]["task"]["dt"],
    )
    return out, {}


def _sim(cfg: dict[str, Any], seeds: list[int], lo: float, hi: float):
    gen = engine.simulate(cfg, seeds, chunk=100)
    while True:
        try:
            f = next(gen)
        except StopIteration as st:
            return st.value
        yield {"stage": "re-observing the stored bodies", "progress": lo + (hi - lo) * f}


def reanalyse(rec: dict[str, Any], obs: dict[str, Any]) -> dict[str, Any]:
    gen = reanalyse_steps(rec, obs)
    while True:
        try:
            next(gen)
        except StopIteration as st:
            return st.value[0]


def carried_state(store: records.HistoryStore, rid: str) -> dict[str, list[float]]:
    st = store.carry_over(rid)
    if not st:
        raise HistoryError(f"record {rid} has no stored slow state")
    return {k: list(v) for k, v in st.items()}


def reenter(
    store: records.HistoryStore, from_id: str, experiment: str, params: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run ``experiment`` with the slow state of record ``from_id`` as its starting state."""
    state = carried_state(store, from_id)
    p = {**(params or {}), "carry_over": state}
    rec, slow = experiments.run_to_end(experiment, p)
    rec["history"] = {
        **rec.get("history", {}),
        "parent": from_id,
        "operation": "reenter",
        "reentry": [{"from": from_id, "kind": "slow-state", "fields": sorted(state), "model_version": MODEL_VERSION}],
    }
    return rec, slow
