"""Storage and execution of studies.

One directory per experiment (``<root>/<experiment id>/``):

    protocol.json            the current protocol (after amendments)
    protocol.registered.json the protocol as registered (frozen) — the reference for "pre-registered"
    amendments.jsonl         every change after registration (what, old, new, why, whether runs had started)
    manifest.json            experiment id, protocol digest, git commit / dirty flag, interpreter and dependency versions,
                             platform, CPU count, seeds, start/finish times
    status.json              state, counts, timing (updated while running)
    log.jsonl                one line per event (job started / finished / failed / timed out / stop requested)
    runs/<arm>__<k>.json     one run record per (arm, seed index): metrics, controller trace, changes, checks, timings
    stop.flag                present = stop requested (safe: running jobs finish or time out, no new job starts)

Runs execute in worker processes (one per slot, restarted after a timeout), so a hung or crashed run is recorded as a
failure and never takes the study down. Resuming skips every run whose record exists with status ``ok``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import multiprocessing as mp
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from ..hpo.experiments import clean
from . import envs
from . import protocol as P

DEFAULT_ROOT = Path(os.environ.get("XZR_STUDY_ROOT", Path(__file__).resolve().parents[2] / "experiments" / "studies"))
REPO = Path(__file__).resolve().parents[3]
VOLATILE_RUN_KEYS = ("wall_s", "cpu_s", "peak_rss_mb")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write(p: Path, doc: Any) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(clean(doc), indent=1, ensure_ascii=False, allow_nan=False))
    os.replace(tmp, p)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=20, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def environment_info() -> dict:
    import numpy
    import scipy

    deps = {"numpy": numpy.__version__, "scipy": scipy.__version__}
    for m in ("mujoco", "fastapi", "pydantic"):
        try:
            deps[m] = __import__(m).__version__
        except Exception:  # noqa: BLE001 - an optional dependency that is missing or has no __version__
            deps[m] = None
    status = _git("status", "--porcelain")
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(status),
        "git_dirty_files": status.splitlines()[:50],
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "dependencies": deps,
        "xzr_force_compat": os.environ.get("XZR_FORCE_COMPAT", ""),
        "determinism_note": "Results are reproducible bit-for-bit only on the same machine and software versions "
        "(docs/REPRODUCIBILITY.md); across platforms the address hierarchy can differ.",
    }


class Study:
    """A study directory."""

    def __init__(self, path: Path):
        self.path = Path(path)

    # ---------------------------------------------------------------------------------------- creation
    @classmethod
    def create(cls, doc: dict, root: Path | None = None, reproduces: str | None = None) -> Study:
        root = Path(root or DEFAULT_ROOT)
        issues = P.validate(doc)
        if doc.get("mode") == "confirmatory":
            issues += P.fairness_issues(doc)
        if doc["environment"].get("kind") == "hpo-world" and int(doc["environment"].get("horizon", 240)) % envs.EPOCH:
            issues.append(f"hpo-world: horizon must be a multiple of the epoch ({envs.EPOCH} steps)")
        if issues:
            raise P.ProtocolInvalid(issues)
        d = P.digest(doc)
        exp_id = f"S{time.strftime('%Y%m%d', time.gmtime())}-{d[:8]}-{secrets.token_hex(2)}"
        path = root / exp_id
        (path / "runs").mkdir(parents=True)
        reg = doc if doc.get("freeze") else P.freeze(doc, _git("rev-parse", "HEAD")) if doc["mode"] == "confirmatory" else doc
        _write(path / "protocol.json", reg)
        _write(path / "protocol.registered.json", reg)
        (path / "amendments.jsonl").write_text("")
        info = environment_info()
        _write(
            path / "manifest.json",
            {
                "schema": "xzr.studymanifest/1",
                "experiment_id": exp_id,
                "protocol_digest": d,
                "created": _now(),
                "mode": doc["mode"],
                "reproduces": reproduces,
                "seeds": P.seed_list(doc),
                "n_runs": P.n_runs(doc),
                "environment": info,
                "not_evidence": doc["mode"] == "functional",
            },
        )
        _write(path / "status.json", {"state": "created", "n_total": P.n_runs(doc), "n_ok": 0, "n_failed": 0, "updated": _now()})
        st = cls(path)
        st.log("created", digest=d)
        return st

    # ---------------------------------------------------------------------------------------- reading
    @property
    def id(self) -> str:
        return self.path.name

    def protocol(self) -> dict:
        return json.loads((self.path / "protocol.json").read_text())

    def registered(self) -> dict:
        return json.loads((self.path / "protocol.registered.json").read_text())

    def manifest(self) -> dict:
        return json.loads((self.path / "manifest.json").read_text())

    def status(self) -> dict:
        return json.loads((self.path / "status.json").read_text())

    def amendments(self) -> list[dict]:
        t = (self.path / "amendments.jsonl").read_text().strip()
        return [json.loads(x) for x in t.splitlines()] if t else []

    def run_files(self) -> list[Path]:
        return sorted((self.path / "runs").glob("*.json"))

    def runs(self) -> list[dict]:
        return [json.loads(p.read_text()) for p in self.run_files()]

    def log_lines(self, limit: int = 500) -> list[dict]:
        p = self.path / "log.jsonl"
        lines = p.read_text().splitlines() if p.exists() else []
        return [json.loads(x) for x in lines[-limit:]]

    def log(self, event: str, **kw: Any) -> None:
        with (self.path / "log.jsonl").open("a") as fh:
            fh.write(json.dumps(clean({"at": _now(), "event": event, **kw}), ensure_ascii=False) + "\n")

    def _set_status(self, **kw: Any) -> None:
        st = self.status()
        st.update(kw, updated=_now())
        _write(self.path / "status.json", st)

    # ---------------------------------------------------------------------------------------- changes
    def runs_started(self) -> bool:
        return bool(self.run_files())

    def amend(self, path: str, new: Any, reason: str) -> dict:
        doc = self.protocol()
        out = P.amend(doc, path, new, reason, self.runs_started())
        _write(self.path / "protocol.json", out)
        rec = out["amendments"][-1]
        with (self.path / "amendments.jsonl").open("a") as fh:
            fh.write(json.dumps(clean(rec), ensure_ascii=False) + "\n")
        self.log("amended", path=path, status=rec["status"])
        return rec

    def stop(self) -> None:
        (self.path / "stop.flag").write_text(_now())
        self.log("stop_requested")

    def _stopping(self) -> bool:
        return (self.path / "stop.flag").exists()

    # ---------------------------------------------------------------------------------------- execution
    def jobs(self) -> list[tuple[str, int, int, int]]:
        doc = self.protocol()
        return [(a["name"], k, g, e) for k, (g, e) in enumerate(P.seed_list(doc)) for a in doc["arms"]]

    def _run_path(self, arm: str, k: int) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in arm)
        return self.path / "runs" / f"{safe}__{k:04d}.json"

    def pending(self, retry_failed: bool = True) -> list[tuple[str, int, int, int]]:
        out = []
        for arm, k, g, e in self.jobs():
            p = self._run_path(arm, k)
            if p.exists() and (json.loads(p.read_text()).get("status") == "ok" or not retry_failed):
                continue
            out.append((arm, k, g, e))
        return out

    def execute(self, procs: int = 1, inline: bool = False, retry_failed: bool = True) -> dict:
        """Run every pending (arm, seed) job. ``inline`` runs in this process (no timeouts; for tests and debugging)."""
        doc = self.protocol()
        reg = self.registered()
        if doc["mode"] == "confirmatory":
            if not reg.get("freeze"):
                raise P.ProtocolInvalid(["confirmatory: the protocol was never registered"])
            if self.amendments() and any(a["runs_started"] for a in self.amendments()):
                self.log("warning", note="amendments after the first run: affected contrasts are analysed as exploratory")
            if P.digest(reg) != reg["freeze"]["digest"]:
                raise P.ProtocolInvalid(["the registered protocol differs from its frozen digest"])
        stop = doc["stop"]
        max_fail = int(stop.get("max_failures", 3))
        wall = float(stop["max_wall_seconds"])
        timeout = float(stop["timeout_per_run_s"])
        budget_runs = int(doc.get("budget", {}).get("max_runs", 10**9))
        if (self.path / "stop.flag").exists():
            (self.path / "stop.flag").unlink()
        todo = self.pending(retry_failed)
        t0 = time.time()
        self._set_status(state="running", started=_now(), n_total=P.n_runs(doc))
        self.log("started", pending=len(todo), procs=procs, inline=inline)
        counts = {"ok": 0, "failed": 0}
        reason = "finished"

        def record(arm: str, k: int, g: int, e: int, res: dict) -> None:
            res = {
                **res,
                "index": k,
                "experiment_id": self.id,
                "protocol_digest": self.manifest()["protocol_digest"],
                "finished": _now(),
            }
            _write(self._run_path(arm, k), res)
            counts["ok" if res["status"] == "ok" else "failed"] += 1
            self.log("run_" + res["status"], arm=arm, index=k, gen=g, seed=e, wall_s=res.get("wall_s"), error=res.get("error"))
            done = len([1 for p in self.run_files() if json.loads(p.read_text()).get("status") == "ok"])
            self._set_status(n_ok=done, n_failed=counts["failed"], elapsed_s=round(time.time() - t0, 1))

        def should_stop() -> str | None:
            if self._stopping():
                return "stopped: stop requested"
            if time.time() - t0 > wall:
                return "stopped: wall-clock budget"
            if counts["failed"] >= max_fail:
                return "stopped: too many failures"
            if counts["ok"] + counts["failed"] >= budget_runs:
                return "stopped: run budget"
            return None

        try:
            if inline:
                for arm, k, g, e in todo:
                    why = should_stop()
                    if why:
                        reason = why
                        break
                    record(arm, k, g, e, _run_safely(doc, arm, g, e))
            else:
                reason = _pool(self, doc, todo, max(1, procs), timeout, should_stop, record)
        except KeyboardInterrupt:
            reason = "stopped: interrupted"
        left = len(self.pending(retry_failed=True))
        state = "finished" if left == 0 else "stopped"
        self._set_status(state=state, ended=_now(), stop_reason=reason if state == "stopped" else None, remaining=left)
        self.log(state, reason=reason, ok=counts["ok"], failed=counts["failed"], remaining=left)
        return self.status()


def _run_safely(doc: dict, arm: str, g: int, e: int) -> dict:
    try:
        return envs.run_one(doc, arm, g, e)
    except Exception as exc:  # noqa: BLE001 - any failure of a run is recorded as such
        return {
            "schema": envs.RUN_SCHEMA,
            "arm": arm,
            "gen": g,
            "seed": e,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-2000:],
        }


def _worker(conn, doc: dict) -> None:  # runs in a child process
    while True:
        job = conn.recv()
        if job is None:
            return
        arm, g, e = job
        conn.send(_run_safely(doc, arm, g, e))


@contextlib.contextmanager
def _spawnable_main():
    """Spawned workers re-import ``__main__`` from its file; when the parent is ``python -`` or ``-c`` that file does not
    exist (``<stdin>``). Hide the attribute while workers start so they import only this package."""
    main = sys.modules.get("__main__")
    f = getattr(main, "__file__", None)
    hide = f is not None and not os.path.exists(f)
    if hide:
        del main.__file__
    try:
        yield
    finally:
        if hide:
            main.__file__ = f


def _pool(study: Study, doc: dict, todo: list, procs: int, timeout: float, should_stop, record) -> str:
    ctx = mp.get_context("spawn")
    slots: list[dict | None] = [None] * procs
    queue = list(todo)
    reason = "finished"

    def spawn() -> dict:
        parent, child = ctx.Pipe()
        p = ctx.Process(target=_worker, args=(child, doc), daemon=True)
        with _spawnable_main():
            p.start()
        return {"proc": p, "conn": parent, "job": None, "deadline": None}

    def reap(s: dict) -> None:
        with contextlib.suppress(OSError, BrokenPipeError):
            s["conn"].send(None)
        s["proc"].join(2)
        if s["proc"].is_alive():
            s["proc"].terminate()

    try:
        while queue or any(s and s["job"] for s in slots):
            why = should_stop()
            if why and not reason.startswith("stopped"):
                reason = why
                queue.clear()  # running jobs finish (or time out); nothing new starts
            for i in range(procs):
                s = slots[i]
                if s is None and queue:
                    s = slots[i] = spawn()
                if s is not None and s["job"] is None and queue:
                    arm, k, g, e = queue.pop(0)
                    s["job"], s["deadline"] = (arm, k, g, e), time.time() + timeout
                    s["conn"].send((arm, g, e))
                    study.log("run_started", arm=arm, index=k)
            for i, s in enumerate(slots):
                if s is None or s["job"] is None:
                    continue
                arm, k, g, e = s["job"]
                if s["conn"].poll(0.05):
                    try:
                        res = s["conn"].recv()
                    except (EOFError, OSError):
                        res = {
                            "schema": envs.RUN_SCHEMA,
                            "arm": arm,
                            "gen": g,
                            "seed": e,
                            "status": "failed",
                            "error": "worker process died",
                        }
                        reap(s)
                        slots[i] = None
                    else:
                        s["job"] = None
                    record(arm, k, g, e, res)
                elif time.time() > s["deadline"] or not s["proc"].is_alive():
                    dead = not s["proc"].is_alive()
                    s["proc"].terminate()
                    s["proc"].join(2)
                    slots[i] = None
                    record(
                        arm,
                        k,
                        g,
                        e,
                        {
                            "schema": envs.RUN_SCHEMA,
                            "arm": arm,
                            "gen": g,
                            "seed": e,
                            "status": "failed" if dead else "timeout",
                            "error": "worker process died" if dead else f"exceeded {timeout:g} s",
                        },
                    )
    finally:
        for s in slots:
            if s is not None:
                reap(s)
    return reason


# ------------------------------------------------------------------------------------------------ reproduction
def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _strip(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in VOLATILE_RUN_KEYS + ("finished", "experiment_id")}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def compare_runs(a: Study, b: Study) -> dict:
    """How far two executions of the same protocol agree. Wall time / CPU / memory are excluded; everything else in a run
    record (metrics, controller traces, changes, checks) is compared exactly."""
    ra = {(r["arm"], r["index"]): r for r in a.runs()}
    rb = {(r["arm"], r["index"]): r for r in b.runs()}
    keys = sorted(set(ra) | set(rb))
    same, diff, missing = 0, [], []
    for k in keys:
        if k not in ra or k not in rb:
            missing.append(list(k))
            continue
        x, y = _strip(ra[k]), _strip(rb[k])
        x.pop("protocol_digest", None)
        y.pop("protocol_digest", None)
        if json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True):
            same += 1
        else:
            mx, my = x.get("metrics") or {}, y.get("metrics") or {}
            diff.append(
                {"run": list(k), "metrics_differing": sorted(m for m in set(mx) | set(my) if mx.get(m) != my.get(m))[:20]}
            )
    return {
        "runs_compared": len(keys),
        "identical": same,
        "differing": diff,
        "missing": missing,
        "identical_share": same / len(keys) if keys else None,
        "condition": "same machine and software versions"
        if a.manifest()["environment"]["python"] == b.manifest()["environment"]["python"]
        else "software versions differ: "
        + json.dumps({"a": a.manifest()["environment"]["dependencies"], "b": b.manifest()["environment"]["dependencies"]}),
    }


def reproduce(src: Study, root: Path, procs: int = 1, inline: bool = False) -> tuple[Study, dict]:
    """Re-execute a study's registered protocol into a new experiment directory and compare."""
    doc = src.registered()
    new = Study.create(
        {k: v for k, v in doc.items() if k != "freeze"} if doc["mode"] != "confirmatory" else doc, root, reproduces=src.id
    )
    new.execute(procs=procs, inline=inline)
    cmp = compare_runs(src, new)
    _write(new.path / "reproduction.json", {"of": src.id, "at": _now(), **cmp})
    return new, cmp


def replay_run(study: Study, arm: str, k: int) -> dict:
    """Re-execute one stored run from the protocol alone and compare it with the stored record (volatile fields excluded)."""
    stored = json.loads(study._run_path(arm, k).read_text())
    gen, seed = P.seed_list(study.protocol())[k]
    fresh = envs.run_one(study.protocol(), arm, gen, seed)
    a, b = _strip(stored), _strip(fresh)
    for d in (a, b):
        for key in ("index", "protocol_digest", "status", "error", "traceback"):
            d.pop(key, None)
    same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    mx, my = stored.get("metrics") or {}, fresh.get("metrics") or {}
    return {"arm": arm, "index": k, "agreement": same, "metrics_differing": sorted(m for m in set(mx) | set(my) if mx.get(m) != my.get(m)),
            "condition": "same machine and software versions"}


def copy_study(src: Study, dst: Path) -> Study:
    shutil.copytree(src.path, dst)
    return Study(dst)
