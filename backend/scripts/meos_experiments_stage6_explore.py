"""Stage 6, exploration: every applicable repair action on every stress over its magnitudes, durations and action ticks, on the exploration seeds 1-5.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_explore.py

Writes the raw rows (one per run) to docs/ecosystem/experiments_stage6_raw.jsonl.gz. About 8 minutes on 8 cores."""

from __future__ import annotations

import time

from xzr.meos import stage6_experiments as S6


def main() -> None:
    t0 = time.time()
    rows = S6.explore()
    S6.save_raw(rows)
    print(f"{len(rows)} runs in {time.time() - t0:.0f} s -> {S6.RAW}")


if __name__ == "__main__":
    main()
