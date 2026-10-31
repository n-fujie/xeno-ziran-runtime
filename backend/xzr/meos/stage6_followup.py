"""MEOS-0, sixth stage, follow-up: the three actions the main Stage 6 experiments could not build (coupling.bypass, resource.rerouting, address.temporary_local; engine meos-0.5).

Same protocol as Pipeline A and B, with the same criterion (``stage6_experiments.row_ok``), on the same stresses, tick grid and seed sets (exploration 1-5, validation 6-10, evaluation 11-30; a setting is validated only if it is effective on all five
validation seeds; 3-4 of 5 is a near miss and is kept). Nothing of the frozen Stage 6 results is changed: this adds rows to the tested action space and the classification is reported twice, with the original action space and with the extended one.
A combined repair counts as a combined recovery only where neither of its two parts is effective alone (the Stage 6 rule), the new action being one part.
"""

from __future__ import annotations

import itertools
from collections import defaultdict

from . import repair6 as R
from . import stage5_experiments as X5
from . import stage6_experiments as S6

NEW = R.FOLLOWUP_IDS
FOLLOW_SECONDARY: tuple[tuple[str, float, int], ...] = tuple((a.id, m, d) for a in R.FOLLOWUP_LIST for m, d in itertools.product(a.magnitudes or (0.0,), a.durations) if a.id != "address.temporary_local")


def applicable(action_id: str, stress_id: str) -> bool:
    if action_id == "address.temporary_local":
        return R.STRESSES[stress_id].family == "address"  # like address.restore: a repair of a parameter the stress did not damage would damage it
    return True


def settings(action_id: str) -> list[tuple[float, int]]:
    a = R.FOLLOWUP[action_id]
    return list(itertools.product(a.magnitudes or (0.0,), a.durations))


def explore(stress_ids: tuple[str, ...] = R.STRESS_ORDER, seeds: tuple[int, ...] = R.SEARCH_SEEDS, processes: int | None = None) -> list[dict]:
    jobs = [(sid, aid, m, d, t, sd) for sid in stress_ids for aid in NEW if applicable(aid, sid) for (m, d) in settings(aid) for t in S6.TIMINGS for sd in seeds]
    return X5.pmap(S6._job, jobs, processes, chunksize=8)


def combos(stress_id: str) -> list[tuple[tuple[str, float, int], ...]]:
    """(a primary of Stage 6, a setting of a new action) and, for the new actions together with the pulse, (new, resource.pulse): the pairs a single new action could not do alone."""
    out: list[tuple[tuple[str, float, int], ...]] = [(p, s) for p in S6.primaries(stress_id) for s in FOLLOW_SECONDARY if applicable(s[0], stress_id)]
    out += [(p, ("address.temporary_local", 0.0, d)) for p in S6.primaries(stress_id) if applicable("address.temporary_local", stress_id) and p[0] != "address.restore" for d in R.FOLLOWUP["address.temporary_local"].durations]
    return out


def explore_combined(stress_ids: tuple[str, ...], seeds: tuple[int, ...] = R.SEARCH_SEEDS, processes: int | None = None) -> list[dict]:
    jobs = [(sid, parts, t, sd) for sid in stress_ids for parts in combos(sid) for t in S6.COMBO_TICKS for sd in seeds]
    return X5.pmap(S6._cjob, jobs, processes, chunksize=8)


def by_cell(rows: list[dict]) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        out[(r["stress"], tuple(map(tuple, r["parts"])), r["t"])].append(r)
    return dict(out)
