"""The public research workflow: configuration, CLI, a complete experiment, history operations, result schema,
comparison and export."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from xzr import __version__, presets, results
from xzr.cli import main
from xzr.experiments import history

ROOT = Path(__file__).resolve().parents[1]


def cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "xzr", *args], cwd=cwd, capture_output=True, text=True,
                          env={"PYTHONPATH": str(ROOT), "OMP_NUM_THREADS": "1", "PATH": "/usr/bin:/bin"}, timeout=900)


# ------------------------------------------------------------------------------------------------ configuration
def test_every_bundled_preset_validates_and_expands():
    for name in presets.names():
        cfg = presets.load(name)
        eff = presets.effective(cfg)
        assert eff["id"] == name and eff["seeds"] == cfg["seeds"]
        for key in ("question", "manipulated", "fixed", "measured", "does_not_show"):
            assert cfg.get(key), f"{name}: preset must document {key}"
        if cfg["kind"] == "conditions":
            assert all(c["seeds"] == eff["seeds"] and "C" in c["variants"] for c in eff["conditions"])


@pytest.mark.parametrize("bad, message", [
    ({"kind": "conditions"}, "schema"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "magic", "seeds": 2}, "kind"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "conditions", "seeds": 0, "conditions": [{"id": "a"}]}, "seeds"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "conditions", "seeds": 2, "conditions": []}, "conditions"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "conditions", "seeds": 2,
      "conditions": [{"id": "a", "changed": {"topolgy": "modular"}}]}, "topolgy"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "conditions", "seeds": 2,
      "conditions": [{"id": "a", "changed": {"memory": "forever"}}]}, "memory"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "conditions", "seeds": 2, "baseline": {"variants": ["A"]},
      "conditions": [{"id": "a"}]}, "'C'"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "history", "seeds": 2, "history": {"reactivate_at": 10}},
     "operation_at"),
    ({"schema": "xzr.experiment/1", "id": "x", "kind": "history", "seeds": 2, "colour": "red"}, "colour"),
])
def test_malformed_configurations_are_refused_with_the_field_named(bad, message):
    with pytest.raises(presets.ConfigError, match=message):
        presets.validate(bad)


def test_cli_usage_errors_exit_2(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "missing.json")]) == 2
    (tmp_path / "broken.json").write_text("{not json")
    assert main(["validate", str(tmp_path / "broken.json")]) == 2
    assert main(["run", "no-such-preset"]) == 2
    with pytest.raises(SystemExit) as e:
        main(["frobnicate"])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ history operations
SMALL = {**history.DEFAULTS, "n": 400, "operation_at": 60, "reactivate_at": 80, "probe_at": 90, "horizon": 120}


def test_history_operations_are_deterministic_and_fork_is_exact():
    a = history.seed_job(SMALL, 7)
    b = history.seed_job(SMALL, 7)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)  # seeded: bit-for-bit repeatable
    assert a["branches"]["fork"]["bit_identical_to_intact"]  # a fork carries the complete history
    assert not a["branches"]["remove"]["bit_identical_to_intact"]  # removing history changes the continuation
    assert not a["branches"]["noise"]["bit_identical_to_intact"]
    assert a["branches"]["migrate"]["destination_generation"] >= 0
    assert a["theta_after_restore"]["share_changed"] > 0  # the restored record is read again


def test_history_verdict_never_claims_reentry_without_all_four_criteria():
    jobs = [history.seed_job(SMALL, s) for s in range(100, 103)]
    a = history.analyse(SMALL, jobs)
    h = a["history_reentry"]
    assert set(h["criteria"]) == {"retained_prior_difference", "re_addressability", "actual_re_entry",
                                  "downstream_difference"}
    if not all(h["criteria"].values()):
        assert not h["verdict"].startswith("HISTORY RE-ENTRY")
    # three seeds are below the minimum for the sign-flip test: nothing can be DETECTED
    assert all(v["status"] != "DETECTED" for cmp_ in a["comparisons"].values() for v in cmp_.values()
               if isinstance(v, dict))


def test_sign_flip_test():
    assert history.sign_flip_p(np.zeros(5)) == 1.0
    assert history.sign_flip_p(np.ones(10)) == pytest.approx(2 / 1024)
    assert history.sign_flip_p(np.array([1.0, -1.0, 1.0, -1.0])) == 1.0


# ------------------------------------------------------------------------------------------------ complete experiment
def test_complete_experiment_through_the_cli(tmp_path):
    """smoke preset end to end: run, result schema, provenance, never-overwrite, compare, export."""
    from xzr.experiments.escalation.harness import RESULTS
    published = {p: p.read_bytes() for p in RESULTS.parent.rglob("*.json") if "jobs" not in p.parts}
    r = cli("run", "smoke", "--out", "runs", "--procs", "2", cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]
    run_dir = next((tmp_path / "runs" / "smoke").iterdir())
    for name in ("config.json", "result.json", "summary.txt", "raw.json", "calibration.json"):
        assert (run_dir / name).exists(), name
    # a run writes only its own directory: the published result files are untouched
    assert {p: p.read_bytes() for p in RESULTS.parent.rglob("*.json") if "jobs" not in p.parts} == published
    res = results.load(run_dir)
    assert res["schema"] == "xzr.result/1" and res["experiment_id"] == "smoke"
    assert res["seeds"] == [100, 101]
    assert res["provenance"]["version"] == __version__ and res["provenance"]["code_sha1"]
    assert res["effective_configuration"] == json.loads((run_dir / "config.json").read_text())
    assert res["warnings"] and "no statistical claim" in res["warnings"][0]
    assert not res["failures"]
    cmp_ = res["conditions"][0]["comparisons"]
    assert set(cmp_) == {"A", "C~"} and set(cmp_["A"]["status"]) == set(results.RESOLUTIONS)
    assert "NOT statistically interpretable" in (run_dir / "summary.txt").read_text()

    # a second run with the same seeds reproduces every status
    r2 = cli("run", "smoke", "--out", "runs2", "--procs", "2", cwd=tmp_path)
    assert r2.returncode == 0
    res2 = results.load(next((tmp_path / "runs2" / "smoke").iterdir()))
    c = results.compare(res, res2)
    assert set(c["counts"]) == {"same"}

    # export
    e = cli("export", str(run_dir), cwd=tmp_path)
    assert e.returncode == 0 and e.stdout.splitlines()[0].startswith("run_id,experiment_id,condition")
    assert len(e.stdout.splitlines()) == 1 + 2 * len(results.RESOLUTIONS)
    out = tmp_path / "x.csv"
    assert cli("export", str(run_dir), "--output", str(out), cwd=tmp_path).returncode == 0
    assert cli("export", str(run_dir), "--output", str(out), cwd=tmp_path).returncode == 2  # never overwrites


def test_results_are_never_overwritten(tmp_path):
    eff = presets.effective(presets.load("smoke"))
    (tmp_path / "smoke" / "fixed").mkdir(parents=True)
    with pytest.raises(results.RunExistsError):
        results.execute(eff, tmp_path, procs=1, run_id="fixed")


def test_compare_labels():
    def res(run_id: str, status: str, extra: bool = False) -> dict:
        conds = [{"id": "c", "comparisons": {"E": {"status": dict.fromkeys(results.RESOLUTIONS, status)}}}]
        if extra:
            conds.append({"id": "d", "comparisons": {"E": {"status": dict.fromkeys(results.RESOLUTIONS, status)}}})
        return {"run_id": run_id, "conditions": conds}
    assert results.compare(res("a", "UNRESOLVED"), res("b", "DETECTED"))["counts"] == {"newly detectable": 5}
    assert results.compare(res("a", "DETECTED"), res("b", "EQUIVALENT"))["counts"] == {"extinguished": 5}
    assert results.compare(res("a", "UNRESOLVED"), res("b", "EQUIVALENT"))["counts"] == {"changed": 5}
    assert results.compare(res("a", "DETECTED"), res("b", "DETECTED", extra=True))["counts"] == {"same": 5,
                                                                                                "missing in A": 5}


def test_effective_configuration_round_trips_and_edits_are_recorded(tmp_path):
    """`xzr validate` output can be saved, edited and run; the edited setting is recorded as changed."""
    for name in presets.names():
        eff = presets.effective(presets.load(name))
        f = tmp_path / f"{name}.json"
        f.write_text(json.dumps(eff))
        assert presets.effective(presets.load(str(f))) == eff, name
    eff = presets.effective(presets.load("smoke"))
    eff["conditions"][0]["memory"] = "long"
    f = tmp_path / "edited.json"
    f.write_text(json.dumps(eff))
    again = presets.effective(presets.load(str(f)))
    assert again["conditions"][0]["changed"] == ["memory"] and again["conditions"][0]["memory"] == "long"
