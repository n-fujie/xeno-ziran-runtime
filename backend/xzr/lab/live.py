"""Live laboratory runs: the runtime advances in its own thread and streams to viewers (WebSocket, service/app.py).

* The run never waits for a viewer: it steps at its own rate (``rate`` steps/s) whether zero or many viewers are
  connected. Viewers only receive copies of what the run produced; nothing they do reaches the run except the
  explicit controls pause / resume / stop / rate.
* Ordering and completeness: every step has a sequence number. A subscriber accumulates every event of every step in
  order. When the socket is slower than the run, intermediate *visual frames* are coalesced (the message carries the
  latest step and ``seq_from``–``seq_to``), but no event is dropped. A subscriber that falls further behind than
  MAX_PENDING_EVENTS is disconnected with an explicit message rather than silently losing events.
* The finished (or stopped) run is written as an ordinary record (xzr.labrun/1 or /2) that ``xzr lab replay`` checks.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .record import LabRun

MAX_PENDING_EVENTS = 20000
MAX_LIVE = 2
MAX_KEPT = 16  # ended runs kept in memory for status queries (their records stay on disk)
PRESETS: dict[str, dict[str, Any]] = {
    "systems": {"settings": None, "physics": True, "horizon": 960,
                "systems": [{"sid": "A", "kind": "local", "home": "0.0"},
                            {"sid": "B", "kind": "distributed", "home": "1.0", "sensors": ["0.1", "2.0", "7.0", "1.2"],
                             "isolate_above": 0.12},
                            {"sid": "C", "kind": "history", "home": "1.1", "memory": "ordinary", "store": "1.3"}]},
    "physical": {"physics": True, "horizon": 240},
    "apparatus": {"physics": False, "horizon": 240},
}
EVENT_KEYS = ("events", "physical_events", "science_events")


class Subscriber:
    """A viewer's mailbox (filled by the run thread, drained by the socket task)."""

    def __init__(self, notify):
        self.notify = notify  # thread-safe callable that wakes the socket task
        self.lock = threading.Lock()
        self.pending: dict[str, list] = {k: [] for k in EVENT_KEYS}
        self.latest: dict | None = None
        self.first_seq: int | None = None
        self.overflow = False

    def offer(self, seq: int, out: dict) -> None:
        with self.lock:
            for k in EVENT_KEYS:
                self.pending[k] += out[k]
            self.latest = {"seq": seq, "step": out["step"]}
            if self.first_seq is None:
                self.first_seq = seq
            if sum(len(v) for v in self.pending.values()) > MAX_PENDING_EVENTS:
                self.overflow = True
        self.notify()

    def take(self) -> dict | None:
        with self.lock:
            if self.latest is None:
                return None
            msg = {"type": "frame", "seq_from": self.first_seq, "seq_to": self.latest["seq"], "step": self.latest["step"],
                   **self.pending, "coalesced_frames": self.latest["seq"] - (self.first_seq or 0)}
            self.pending = {k: [] for k in EVENT_KEYS}
            self.latest, self.first_seq = None, None
            return msg


class LiveRun:
    def __init__(self, cfg: dict, rate: float = 10.0, out_dir: Path | None = None, preset: str = "custom"):
        self.id = uuid.uuid4().hex[:12]
        self.cfg, self.rate, self.preset = cfg, float(rate), preset
        self.out_dir = out_dir or Path("xzr-results") / "lab-live"
        self.state = "starting"
        self.seq = 0
        self.lock = threading.Lock()
        self.subs: list[Subscriber] = []
        self.history: dict[str, list] = {k: [] for k in EVENT_KEYS}
        self.latest: dict | None = None
        self.run: LabRun | None = None
        self.record_path: Path | None = None
        self.error: str | None = None
        self._paused = threading.Event()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, name=f"lab-live-{self.id}", daemon=True)
        self.thread.start()

    # ------------------------------------------------------------------ run thread
    def _loop(self) -> None:
        final = "failed"
        try:
            self.run = LabRun(self.cfg)
            self.state = "running"
            next_t = time.perf_counter()
            while not self.run.done and not self._stop.is_set():
                if self._paused.is_set():
                    time.sleep(0.05)
                    next_t = time.perf_counter()
                    continue
                out = self.run.step()
                with self.lock:
                    self.seq += 1
                    for k in EVENT_KEYS:
                        self.history[k] += out[k]
                    self.latest = {"seq": self.seq, "step": out["step"]}
                    subs = list(self.subs)
                for s in subs:
                    s.offer(self.seq, out)
                next_t += 1.0 / max(self.rate, 0.1)
                time.sleep(max(0.0, next_t - time.perf_counter()))
            final = "stopped" if self._stop.is_set() else "finished"
        except Exception as e:  # noqa: BLE001 — reported to viewers, never swallowed
            final, self.error = "failed", repr(e)
        finally:
            # the record is written before the terminal state is published, so a finished run always has its record
            self._write_record(final)
            self.state = final
            for s in list(self.subs):
                s.notify()

    def _write_record(self, state: str) -> None:
        if self.run is None or not self.run.steps:
            return
        rec = self.run.record()
        rec["live"] = {"id": self.id, "state": state, "preset": self.preset,
                       "note": "recorded from a live run; a stopped run is a prefix of the full horizon"}
        self.out_dir.mkdir(parents=True, exist_ok=True)
        p = self.out_dir / f"{self.id}.json"
        if not p.exists():
            p.write_text(json.dumps(rec, separators=(",", ":")))
            self.record_path = p

    # ------------------------------------------------------------------ controls and subscription
    def control(self, action: str, rate: float | None = None) -> None:
        if action == "pause":
            self._paused.set()
            self.state = "paused" if self.state == "running" else self.state
        elif action == "resume":
            self._paused.clear()
            self.state = "running" if self.state == "paused" else self.state
        elif action == "stop":
            self._stop.set()
            self._paused.clear()
        elif action == "rate" and rate is not None:
            self.rate = float(min(max(rate, 0.5), 200.0))
        else:
            raise ValueError(f"unknown action {action!r}")

    def subscribe(self, notify) -> tuple[Subscriber, dict]:
        """A new viewer gets every event so far, the latest step, and then all later steps through its mailbox."""
        s = Subscriber(notify)
        with self.lock:
            hello = {"type": "hello", **self.status(), "config": self.run.cfg if self.run else self.cfg,
                     "chambers": self.run.ch_records if self.run else [],
                     "layout": self.run.lab.layout() if self.run and self.run.lab else None,
                     "history": {k: list(v) for k, v in self.history.items()}, "latest": self.latest}
            self.subs.append(s)
        return s, hello

    def unsubscribe(self, s: Subscriber) -> None:
        with self.lock:
            if s in self.subs:
                self.subs.remove(s)

    def status(self) -> dict:
        return {"id": self.id, "state": self.state, "seq": self.seq, "t": self.latest["step"]["t"] if self.latest else 0,
                "horizon": self.cfg.get("horizon"), "rate": self.rate, "preset": self.preset, "viewers": len(self.subs),
                "record": str(self.record_path) if self.record_path else None, "error": self.error}


RUNS: dict[str, LiveRun] = {}


def start(preset: str, seed: int, rate: float, out_dir: Path | None = None) -> LiveRun:
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; one of {', '.join(PRESETS)}")
    active = [r for r in RUNS.values() if r.state in ("starting", "running", "paused")]
    if len(active) >= MAX_LIVE:
        raise RuntimeError(f"at most {MAX_LIVE} live laboratory runs at a time")
    ended = [k for k, r in RUNS.items() if r.state in ("finished", "stopped", "failed")]
    for k in ended[: max(0, len(ended) - MAX_KEPT + 1)]:
        del RUNS[k]
    cfg = {**PRESETS[preset], "gen_seed": int(seed), "seed": int(seed) * 10}
    r = LiveRun(cfg, float(min(max(rate, 0.5), 200.0)), out_dir, preset)
    RUNS[r.id] = r
    return r
