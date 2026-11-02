"""Cooperative mode (xzr.service.session.COOPERATIVE): where there are no threads (WebAssembly / Pyodide, the browser
build) the host drives a session with pump() and comparison jobs with run_deferred(), through bridge.tick().

This runs on the desktop by switching the flag on. It must reproduce the threaded results exactly: same stepping,
same fingerprints, same comparison summary, and no thread is ever started."""

from __future__ import annotations

import json
import threading
import time

import pytest

from xzr.native import bridge
from xzr.scenario.io import load_sample
from xzr.service import session as session_mod
from xzr.service.session import Session

SAMPLE = "small-600"


@pytest.fixture
def cooperative(monkeypatch):
    monkeypatch.setattr(session_mod, "COOPERATIVE", True)
    monkeypatch.setattr(bridge, "COOPERATIVE", True)
    yield
    for sid in list(bridge.SESSIONS):
        bridge._close(sid)
    session_mod.DEFERRED.clear()


def test_no_thread_is_started(cooperative):
    before = {t.name for t in threading.enumerate()}
    s = Session(load_sample(SAMPLE))
    try:
        assert s.thread is None
        assert {t.name for t in threading.enumerate()} == before
    finally:
        s.close()


def test_pump_steps_match_the_threaded_engine(cooperative, monkeypatch):
    s = Session(load_sample(SAMPLE))
    try:
        t0 = s.engine.state.t
        s.control("step", steps=40)
        more = True
        while more:
            more = s.pump(0.05)
        assert s.engine.state.t == t0 + 40 and s.pending_steps == 0 and not s.running
        coop = s.engine.fingerprint()
    finally:
        s.close()
    monkeypatch.setattr(session_mod, "COOPERATIVE", False)
    t = Session(load_sample(SAMPLE))
    try:
        t.control("step", steps=40)
        for _ in range(4000):
            with t.lock:
                if t.engine.state.t >= t0 + 40 and t.pending_steps == 0:
                    break
            time.sleep(0.005)
        with t.lock:
            assert t.engine.fingerprint() == coop  # bit-identical: pump() uses the same step as the simulation thread
    finally:
        t.close()


def test_running_session_is_paced_and_pausable(cooperative):
    s = Session(load_sample(SAMPLE))
    try:
        s.control("speed", speed=50.0)
        s.control("run")
        t0 = s.engine.state.t
        start = time.perf_counter()
        while time.perf_counter() - start < 0.5:
            s.pump(0.01)
        done = s.engine.state.t - t0
        assert 10 <= done <= 35, f"paced to ~50 steps/s, did {done} in 0.5 s"  # not unpaced, not stalled
        s.control("pause")
        t1 = s.engine.state.t
        assert s.pump(0.05) is False and s.engine.state.t == t1  # nothing runs while paused
    finally:
        s.close()


def test_backpressure_waits_for_the_client_to_drain(cooperative):
    s = Session(load_sample(SAMPLE))
    try:
        s.streaming = True
        s.control("step", steps=500)
        while s.pump(0.02) and len(s.outbox) < session_mod.BACKPRESSURE:
            pass
        n = len(s.outbox)
        assert n >= session_mod.BACKPRESSURE and s.pump(0.02) is True and len(s.outbox) == n  # waits, work remains
        s.take_outbox()
        assert s.pump(0.02) is True and len(s.outbox) > 0  # continues once drained
    finally:
        s.close()


def test_bridge_tick_runs_sessions_streams_and_comparisons(cooperative):
    def call(method, path, body=None):
        r = json.loads(bridge.handle(json.dumps({"method": method, "path": path, "body": body})))
        return r["status"], r["body"]

    st, info = call("POST", "/api/sessions", {"sample": SAMPLE})
    assert st == 200
    sid = info["id"]
    assert bridge.SESSIONS[sid].thread is None
    st, stream = call("POST", f"/native/stream/{sid}")
    assert st == 200
    assert call("POST", f"/api/sessions/{sid}/control", {"action": "step", "steps": 30})[0] == 200
    items = 0
    for _ in range(400):
        items += sum(len(b["items"]) for b in json.loads(bridge.tick(20)))
        if bridge.SESSIONS[sid].pending_steps == 0 and items:
            break
    assert bridge.SESSIONS[sid].pending_steps == 0 and items > 0
    # a branch comparison is queued, then run by tick() (one job per tick), and finishes with a summary
    st, body = call("POST", f"/api/sessions/{sid}/practice/command", {"text": "remove concept inside", "auto_compare": True})
    assert st == 200
    jobs = [j for j in session_mod.JOBS.values() if j["session"] == sid]
    assert jobs, "the command queued a comparison"
    for _ in range(100):
        bridge.tick(20)
        if all(j["status"] in session_mod.FINISHED for j in jobs):
            break
    assert [j["status"] for j in jobs] == ["done"] and jobs[0].get("summary")
    assert not session_mod.DEFERRED and not session_mod.FUTURES


def test_a_queued_comparison_can_be_cancelled_before_it_runs(cooperative):
    s = Session(load_sample(SAMPLE))
    try:
        s.control("step", steps=5)
        while s.pump(0.05):
            pass
        s.command("remove concept inside", auto_compare=False)
        jid = s.start_compare(30)
        assert session_mod.cancel_job(jid) is True  # still queued: nothing has run it yet
        assert session_mod.run_deferred(0.5) is False  # a cancelled job is skipped, never run
        assert session_mod.JOBS[jid]["status"] == "cancelled"
    finally:
        s.close()


def test_a_long_comparison_is_time_sliced_while_the_session_keeps_running(cooperative):
    """The browser build: a comparison advances in small slices, interleaved with the live session's own steps."""
    s = Session(load_sample(SAMPLE))
    try:
        s.control("step", steps=5)
        while s.pump(0.05):
            pass
        s.command("remove concept inside", auto_compare=False)
        jid = s.start_compare(60)
        s.control("run")
        t_start = s.engine.state.t
        slices = 0
        while session_mod.JOBS[jid]["status"] not in session_mod.FINISHED and slices < 5000:
            s.pump(0.002)  # the live session steps (paced), then
            session_mod.run_deferred(0.001)  # the comparison gets a slice: far shorter than the whole job
            slices += 1
        assert session_mod.JOBS[jid]["status"] == "done"
        assert slices > 3, "the job needed several slices (it was not run to completion in one call)"
        assert s.engine.state.t > t_start, "the live session advanced while the comparison was running"
        assert not session_mod.DEFERRED and jid not in session_mod.FUTURES
    finally:
        s.close()


def test_sliced_comparison_equals_the_direct_comparison(cooperative, monkeypatch):
    """Slicing never changes a result: the summary of a sliced job equals the desktop thread's."""
    def summary(coop: bool):
        monkeypatch.setattr(session_mod, "COOPERATIVE", coop)
        s = Session(load_sample(SAMPLE))
        try:
            s.control("step", steps=8)
            while s.pump(0.05) if coop else s.pending_steps:
                if not coop:
                    time.sleep(0.005)
            s.command("remove concept inside", auto_compare=False)
            jid = s.start_compare(40)
            while session_mod.JOBS[jid]["status"] not in session_mod.FINISHED:
                if coop:
                    session_mod.run_deferred(0.002)
                else:
                    time.sleep(0.01)
            return session_mod.JOBS[jid]["summary"]
        finally:
            s.close()
    sliced = summary(True)
    direct = summary(False)
    assert sliced == direct


def test_closing_a_session_leaves_no_job_behind(cooperative):
    s = Session(load_sample(SAMPLE))
    s.control("step", steps=3)
    while s.pump(0.05):
        pass
    s.command("remove concept inside", auto_compare=False)
    jid = s.start_compare(30)
    s.close()  # a queued comparison of a closed session is cancelled
    assert session_mod.JOBS[jid]["status"] == "cancelled"
    assert session_mod.run_deferred(0.5) is False and not session_mod.DEFERRED and jid not in session_mod.FUTURES


def test_uncached_hierarchy_limit_refuses_up_front_on_the_no_scipy_path():
    """Browser build: a graph without an exported reference hierarchy above XZR_MAX_NODES_COMPUTED_HIERARCHY is refused with
    the named limit before the (cubic-cost) eigensolve; a bundled scenario with a reference is not affected. On the scipy
    path the limit does not apply (it is about the dense fallback only)."""
    import os
    import subprocess
    import sys
    code = r"""
import json, os, sys
from xzr.scenario.io import load_sample
from xzr.scenario.model import Scenario
from xzr.scenario.build import build_world
from xzr.lod.hierarchy import HierarchyTooLarge
d = load_sample('small-600').model_dump(mode='json', exclude_none=True)
d['generator']['n'] = 700   # not the bundled graph: no exported hierarchy
out = {}
try:
    build_world(Scenario.model_validate(d)); out['uncached'] = 'built'
except HierarchyTooLarge as e:
    out['uncached'] = e.limit
out['bundled'] = 'built' if build_world(load_sample('small-600')) else 'none'
print(json.dumps(out))
"""
    for force, expected in (("1", "max_nodes_computed_hierarchy"), ("", "built")):
        env = {**os.environ, "XZR_MAX_NODES_COMPUTED_HIERARCHY": "600", "XZR_FORCE_COMPAT": force}
        if not force:
            env.pop("XZR_FORCE_COMPAT")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=300)
        assert r.returncode == 0, r.stderr[-800:]
        got = json.loads(r.stdout.strip().splitlines()[-1])
        assert got == {"uncached": expected, "bundled": "built"}, (force, got)
