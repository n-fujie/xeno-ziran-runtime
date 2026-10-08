"""Observer-side reconstruction of wave origin, depth and returns.

Input per step: the ignitions and, for every ignition caused through a connection, that dominant incoming
connection and its receiver (``penetrations[:, 0]`` and ``penetration_receivers``; the runtime needs the
dominant connection anyway, for adaptation). Output: the same (connection, origin, depth) triples and return
events that the runtime computes when its ``wave_state`` flag is on — reconstructed outside the runtime.
If they agree exactly, origin/depth bookkeeping and return detection are derivable, not runtime state.
"""

from __future__ import annotations

import numpy as np

from ..runtime.delta import StepDelta
from ..runtime.state import NO_INDEX, State


class WaveObserver:
    """Keeps its own record of connection sources, updated from delta events (a slot freed earlier may be
    reused with a different source later in a step, after that step's ignitions)."""

    def __init__(self, state: State):
        n = state.n
        self.origin = np.full(n, NO_INDEX, dtype=np.int32)
        self.depth = np.zeros(n, dtype=np.int32)
        self.src = state.src.copy()

    def observe(self, d: StepDelta, state: State) -> tuple[np.ndarray, np.ndarray]:
        """Returns (penetrations (k, 3) as (connection, origin, depth), returns) for this step."""
        fired = d.ignitions.astype(np.int64)
        recv = d.penetration_receivers.astype(np.int64)
        pe = d.penetrations[:, 0].astype(np.int64) if len(d.penetrations) else np.zeros(0, np.int64)
        src = self.src[pe]
        new_origin = self.origin[src]  # values from the source's own ignition one step earlier
        new_depth = self.depth[src] + 1
        caused = np.zeros(state.n, dtype=bool)
        caused[recv] = True
        spont = fired[~caused[fired]]
        pens = (np.stack([pe, new_origin, new_depth], axis=1).astype(np.int32) if len(pe)
                else np.zeros((0, 3), np.int32))
        returns = recv[new_origin == recv].astype(np.int32)
        self.origin[recv] = new_origin
        self.depth[recv] = new_depth
        self.origin[spont] = spont
        self.depth[spont] = 0
        if len(d.new_connections):  # created after this step's ignitions
            self.src[d.new_connections[:, 0]] = d.new_connections[:, 1]
        if len(d.retired):  # composite reconfiguration: new connections are reported as reconfigurations
            self.src[d.reconfigurations[:, 0]] = state.src[d.reconfigurations[:, 0]]
        return pens, returns
