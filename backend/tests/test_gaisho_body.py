"""GAISHO domain 004 (Body, B1): the XB-TRO planar body reached through the optional link of bodylink.py. These tests need the XB-TRO package (branch feat/xb-tro, not merged here): they run when XZR_XBTRO_PATH, or the
default checkout path below, names it, and are SKIPPED otherwise (a skip is not a pass). The link and the registry behaviour without it are tested unconditionally."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from xzr.gaisho import bodylink
from xzr.gaisho.domains import BODY_STATUS, STATUS, domain_registry, status_of
from xzr.gaisho.export import run_experiment
from xzr.gaisho.lab import FULL, Observation

XB = Path(os.environ.get("XZR_XBTRO_TEST_PATH", "/Users/user/Desktop/BIM/xeno-ziran-runtime-xb-tro/backend/xzr/xbtro"))
needs_body = pytest.mark.skipif(not (XB / "engine.py").is_file(), reason="the XB-TRO package is not on this machine (it is not part of this branch)")
HUMAN, MACHINE = "human-like planar body", "machine-like planar body"
SEEDS = [1, 2, 3, 4]


@pytest.fixture
def linked(monkeypatch):
    monkeypatch.setenv(bodylink.ENV, str(XB))
    bodylink._CACHE.clear()
    yield
    bodylink._CACHE.clear()


@needs_body
def test_the_two_bodies_are_two_presets_that_differ_in_control_sensing_and_time_step_not_in_morphology_alone(linked):
    """Dictionary 060 asks for matched morphology, control and environment. The statement in docs/GAISHO.md and dictionary.D8 (33 of 73 entries differ) is held here: if XB-TRO's presets change, this fails and the statement must be re-made."""
    link = bodylink.load()
    a, b = link.config.build("human-like-planar"), link.config.build("machine-like-planar")

    def flat(d, p=""):
        out = {}
        for k, v in d.items():
            out.update(flat(v, p + k + ".") if isinstance(v, dict) else {p + k: v})
        return out

    fa, fb = flat(a), flat(b)
    differ = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
    assert (len(set(fa) | set(fb)), len(differ)) == (73, 33)
    for k in ("neural.strategy", "neural.visual_weight", "neural.vestibular_weight", "sensors.visual.gain", "internal.fatigue_rate", "task.dt", "links", "joints"):
        assert k in differ, k  # control, sensing, the internal model, the integration step and the links all differ
    assert fa["task.dt"] == 0.01 and fb["task.dt"] == 0.005


def test_the_matched_comparison_uses_the_t_value_of_its_own_number_of_seeds_and_is_not_registered():
    from xzr.gaisho.bodymatched import condition_name, t_interval
    from xzr.gaisho.lab import T975

    iv = t_interval([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])  # 6 seeds: 5 degrees of freedom
    assert iv["t"] == T975[5] == 2.571 and iv["ci95"][0] < 0.5 < iv["ci95"][1] and t_interval([0.5])["ci95"] is None
    import statistics


    assert abs((iv["ci95"][1] - iv["ci95"][0]) / 2 - 2.571 * statistics.stdev([0.0, 0.2, 0.4, 0.6, 0.8, 1.0]) / 6**0.5) < 1e-12  # not the 2.093 of 20 seeds
    assert condition_name("human", "control") == "human-like planar body with the control of the machine-like one"
    assert set(STATUS) == {"001-knowledge", "002-bias", "003-freedom", "004-body", "005-credit"}  # the matched domain is not a domain of the laboratory


@needs_body
def test_each_swap_changes_only_the_named_block_and_the_blocks_cover_every_difference_between_the_presets(linked):
    from xzr.gaisho.bodymatched import (
        BLOCKS,
        HUMAN,
        MACHINE,
        PRESETS,
        MatchedBodyDomain,
        covered_keys,
        flat,
        uncovered_differences,
    )

    dom = MatchedBodyDomain()
    assert uncovered_differences(dom) == []  # nothing that differs between the presets is left out of the five blocks (name and family are labels)
    plain = {HUMAN: flat(dom.link.config.build(PRESETS["human"])), MACHINE: flat(dom.link.config.build(PRESETS["machine"]))}
    assert flat(dom.base_config(HUMAN)) == plain[HUMAN] and flat(dom.base_config(MACHINE)) == plain[MACHINE]  # the controls are the presets themselves
    for cond, spec in dom.conditions.items():
        if spec["donor"] is None:
            continue
        base = plain[HUMAN if spec["preset"] == PRESETS["human"] else MACHINE]
        got = flat(dom.base_config(cond))
        changed = {k for k in set(got) | set(base) if got.get(k) != base.get(k)}
        cov = covered_keys(spec["block"])
        assert changed and all(any(k == c or k.startswith(c + ".") for c in cov) for k in changed), cond  # only entries of the swapped block moved
    assert len(dom.conditions) == 2 + 2 * len(BLOCKS)


def test_the_saved_matched_comparison_keeps_the_controls_equal_to_the_saved_body_record_and_states_what_it_cannot_say():
    root = Path(__file__).resolve().parents[2] / "docs" / "gaisho"
    m = json.loads((root / "experiments_body_matched.json").read_text())
    body = json.loads((root / "experiments_body.json").read_text())["domain"]["result"]["conditions"]
    assert m["seeds"] == [1, 2, 3, 4, 5, 6] and m["uncovered_differences"] == [] and set(m["blocks"]) == {"structure", "control", "sensors", "internal", "time step"}
    for cond in (HUMAN, MACHINE):  # the same seeds, grid and definitions: the plain presets reproduce the earlier record
        for n in ("effect_x", "effect_y", "baseline_fall"):
            assert abs(m["conditions"][cond]["relations"][n]["mean"] - body[cond]["relations"][n]["value"]) < 1e-9, (cond, n)
    for cond, o in m["conditions"].items():
        for n, r in o["relations"].items():
            assert r["status"] != "IDENTIFIED" or r["n"] == 6 and (r["ci95"] is None or r["t"] == 2.571), (cond, n)  # the interval of 6 seeds uses t(5)


@needs_body
def test_a_saved_swap_is_reproduced_by_running_it_again(linked):
    from xzr.gaisho.bodymatched import MatchedBodyDomain, condition_name
    from xzr.gaisho.lab import run_domain

    root = Path(__file__).resolve().parents[2] / "docs" / "gaisho"
    m = json.loads((root / "experiments_body_matched.json").read_text())
    cond = condition_name("human", "time step")
    res = run_domain(MatchedBodyDomain(), FULL, tuple(m["seeds"]), [cond])
    cells = res["conditions"][cond]["snapshots"]["end"]["cells"]
    grid = [[next(c["p"] for c in cells if c["i"] == i and c["j"] == j) for i in range(5)] for j in range(5)]
    assert grid == m["conditions"][cond]["fell_share_grid"]  # the saved cell values are what the specification gives


def test_without_the_link_the_body_domain_is_not_executed_and_nothing_is_substituted(monkeypatch):
    monkeypatch.delenv(bodylink.ENV, raising=False)
    bodylink._CACHE.clear()
    assert domain_registry()["004-body"] is None and status_of("004-body") is STATUS["004-body"] and STATUS["004-body"]["executed"] is False
    out = run_experiment({"domain": "004-body"})
    assert out["executed"] is False and "no substitute computation" in out["note"]
    for bad in ("", "/nonexistent/path", "/tmp"):  # a path that is not the package is refused, not imported
        monkeypatch.setenv(bodylink.ENV, bad)
        bodylink._CACHE.clear()
        assert bodylink.load() is None and domain_registry()["004-body"] is None
    bodylink._CACHE.clear()


def test_the_link_module_is_the_only_one_that_reads_files_and_it_does_nothing_else():
    src = (Path(bodylink.__file__)).read_text()
    code = re.sub(r'""".*?"""', "", "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#")), flags=re.S)
    assert not re.search(r"\b(subprocess|socket|urllib|requests|httpx|shutil|tempfile|os\.system|os\.popen|eval|exec)\b\(?", code.replace("exec_module", "")), "the link must use no process, network or dynamic code"
    assert not re.search(r"\.(write_text|write_bytes|unlink|mkdir|touch)\(|open\([^)]*[\"']w", code)  # it reads, it never writes
    assert "sys.path" not in code.replace("sys.modules", "")  # the path is never added to sys.path
    assert code.count("os.environ.get(ENV") == 1  # the path comes from the environment only, never from a request


@needs_body
def test_the_link_loads_the_leaf_package_and_names_the_body_it_ran_on(linked):
    link = bodylink.load()
    assert link is not None and link.model_version == "xb-tro/1.0" and len(link.source_sha256) == 64 and link.n_files > 10
    again = bodylink._load(XB)
    assert again is not None and again.source_sha256 == link.source_sha256  # the hash is of the files, so a changed body gives a different record
    reg = domain_registry()
    assert reg["004-body"] is not None and status_of("004-body") is BODY_STATUS and BODY_STATUS["executed"] is True


@needs_body
def test_the_body_experiment_runs_gives_continuation_classes_and_keeps_every_layer_apart(linked):
    out = run_experiment({"domain": "004-body", "seeds": SEEDS, "conditions": [HUMAN]})
    assert out["executed"] is True and out["body"]["body"] == "XB-TRO" and out["figure_kind"] == "EXECUTED_COMPUTATIONAL_EXPERIMENT"
    c = out["result"]["conditions"][HUMAN]
    assert c["relations"]["baseline_fall"]["value"] == 0.0  # the undisturbed, undelayed body stays up
    assert c["relations"]["effect_x"]["status"] == "IDENTIFIED" and c["relations"]["effect_x"]["value"] > 0.3  # a sensory delay turns continuation into a fall
    sh = out["shapes"][HUMAN]["end"]
    assert len(sh["vertices"]) == 25 and {v["z"] for v in sh["vertices"]} <= {i / len(SEEDS) for i in range(len(SEEDS) + 1)}  # a cell is the share of seeds that fall
    assert {v["source"]["provenance"] for v in sh["vertices"]} == {"RECORDED_OBSERVATION"} and len(sh["cuts"]) > 0  # the body has real steps, unlike the logistic ridge of the knowledge domain
    # the attribution is untouched by any of it: a body that falls less is an operational difference, a prereflective operation (R37 P), not a Gaisho
    lv = out["levels"][HUMAN]
    assert lv["gaisho_attribution"]["state"] == "UNRESOLVED" and lv["gaisho_attribution"]["applicability_gate"].startswith("NOT_PASSED") and lv["gaisho_operational_shape"]["state"] == "NOT_ESTABLISHED"
    reg = out["r37"]["registers"]
    assert reg["P"]["lab"] == "EXECUTED_IN_MODEL" and "not a thinker" in reg["P"]["note"] and reg["A_G"]["lab"] == "UNRESOLVED" and reg["Occ_G"]["lab"] == "NOT_ASSESSED" and reg["C"]["lab"] == "NOT_MODELLED"
    assert not any("spike" in json.dumps(v).lower() for v in (out["result"], out["shapes"]))  # there are no spikes in this body


@needs_body
def test_the_body_record_is_reproducible_and_restorable(linked):
    from xzr.gaisho.export import restore

    a = run_experiment({"domain": "004-body", "seeds": SEEDS, "conditions": [MACHINE]})
    b = run_experiment({"domain": "004-body", "seeds": SEEDS, "conditions": [MACHINE]})
    assert a["digest"] == b["digest"] and restore({"spec": a["spec"], "digest": a["digest"]})["same_digest"] is True
    assert run_experiment({"domain": "004-body", "seeds": [5, 6, 7, 8], "conditions": [MACHINE]})["digest"] != a["digest"]  # seeds are independent replications


@needs_body
def test_the_two_bodies_differ_in_their_profile_under_the_same_interventions(linked):
    out = run_experiment({"domain": "004-body", "seeds": SEEDS})
    z = {c: [v["z"] for v in out["shapes"][c]["end"]["vertices"]] for c in out["shapes"]}
    assert z[HUMAN] != z[MACHINE]  # the same two interventions do not give one shape for every body


@needs_body
def test_observation_changes_the_record_of_the_body_not_the_body(linked):
    from xzr.gaisho.compare import compare_observations

    dom = domain_registry()["004-body"]
    c = compare_observations(dom, HUMAN, FULL, Observation(scale=2), (1, 2, 3, 4))
    assert c["same_realized_operation"] is True and c["observation_changed_the_operation"] is False


@needs_body
def test_the_api_runs_the_body_within_its_seed_cap(linked):
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    assert c.post("/api/gaisho/run", json={"domain": "004-body", "seeds": list(range(1, 10))}).status_code == 422  # the cap is 8 seeds
    r = c.post("/api/gaisho/run", json={"domain": "004-body", "seeds": [1, 2], "conditions": [HUMAN]})
    assert r.status_code == 200 and r.json()["executed"] is True
    sp = c.get("/api/gaisho/spec").json()["domains"]["004-body"]
    assert sp["status"]["executed"] is True and sp["max_seeds"] == 8 and sp["conditions"][:2] == [HUMAN, MACHINE] and len(sp["conditions"]) == 5


# ------------------------------------------------------------------------------------------------ B2: the open-loop replay through the real XenoSNN server (loopback), kept as separate records
import socket  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

from xzr.gaisho import snnlink  # noqa: E402

SNN_PY = Path(os.environ.get("XZR_XENOSNN_TEST_PYTHON", "/Users/user/Desktop/BIM/.venv-snn/bin/python"))
SNN_SERVER = Path(os.environ.get("XZR_XENOSNN_TEST_SERVER", "/Users/user/Desktop/BIM/pa-simulation-environment/python/ziran_pytorch_server.py"))
needs_snn = pytest.mark.skipif(not (SNN_PY.is_file() and SNN_SERVER.is_file()), reason="no Python with torch + snnTorch, or no XenoSNN server file, on this machine")


@pytest.fixture
def snn_server(monkeypatch):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([str(SNN_PY), str(SNN_SERVER), str(port)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env={"PATH": os.environ.get("PATH", ""), "PYTORCH_BACKEND_REQUIRE_TORCH": "true"})
    monkeypatch.setenv(snnlink.ENV, f"http://127.0.0.1:{port}")
    try:
        for _ in range(60):
            if snnlink.health(2.0):
                break
            time.sleep(0.5)
        else:
            pytest.fail("the XenoSNN server did not come up")
        yield port
    finally:
        proc.terminate()
        proc.wait(10)


def test_the_snn_link_contacts_a_loopback_http_address_with_a_port_and_nothing_else(monkeypatch):
    ok = {"http://127.0.0.1:4711": "http://127.0.0.1:4711", "http://localhost:4711/": "http://localhost:4711", "http://[::1]:4711": "http://[::1]:4711"}
    for raw, want in ok.items():
        monkeypatch.setenv(snnlink.ENV, raw)
        assert snnlink.base_url() == want
    for bad in ("", "https://127.0.0.1:4711", "http://127.0.0.1", "http://example.com:4711", "http://192.168.0.5:4711", "http://127.0.0.1:4711/run", "http://127.0.0.1:4711/?a=1", "http://user:pw@127.0.0.1:4711", "ftp://127.0.0.1:4711", "http://0.0.0.0:4711"):
        monkeypatch.setenv(snnlink.ENV, bad)
        assert snnlink.base_url() is None, bad
    monkeypatch.delenv(snnlink.ENV)
    assert snnlink.base_url() is None and snnlink.health() is None


def test_the_snn_link_refuses_a_bad_input_before_any_network_call_and_has_no_other_reach(monkeypatch):
    monkeypatch.setenv(snnlink.ENV, "http://127.0.0.1:9")  # nothing listens: any call would fail differently
    for bad in ([], [float("nan")], [float("inf")], [True], ["1"], [0.0] * (snnlink.MAX_INPUT + 1)):
        with pytest.raises(snnlink.SnnLinkError, match="finite numbers"):
            snnlink.replay(bad, "x")
    src = Path(snnlink.__file__).read_text()
    code = re.sub(r'""".*?"""', "", "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#")), flags=re.S)
    assert not re.search(r"\b(subprocess|socket|shutil|tempfile|eval|exec|importlib|pathlib)\b|(?<![\w.])open\(|\.write|sys\.path", code)
    assert set(re.findall(r'_call\("(/[a-z]+)"', code)) == {"/health", "/run"} and code.count("os.environ.get(ENV") == 1 and "_NoRedirect" in code  # fixed endpoints; the address from the environment only; redirects refused


@needs_snn
def test_the_real_xenosnn_neuron_follows_its_stated_dynamics(snn_server):
    """The server is the real snnTorch one: the trace obeys mem_t = beta mem_{t-1} + input_t - threshold spike_{t-1} with beta 0.9 and threshold 1.0 (its source constants), and a spike is a membrane above the threshold."""
    x = [0.0, 0.5, 0.5, 0.5, 0.2, 0.0, 0.7, 0.7, 0.7, 0.0]
    tr = snnlink.replay(x, "dynamics")
    assert tr["runtime"]["library"] == "snntorch" and tr["runtime"]["beta"] == 0.9 and tr["runtime"]["threshold"] == 1.0
    mem, spk = [s["membrane"] for s in tr["timesteps"]], [s["spike"] for s in tr["timesteps"]]
    for t in range(1, len(x)):
        assert mem[t] == pytest.approx(0.9 * mem[t - 1] + x[t] - 1.0 * spk[t - 1], abs=1e-5), t
    assert all(spk[t] == int(mem[t] > 1.0) for t in range(len(x))) and sum(spk) >= 2
    assert snnlink.replay(x, "dynamics")["timesteps"] == tr["timesteps"]  # deterministic


@needs_snn
@needs_body
def test_the_open_loop_replay_keeps_the_records_apart_and_attributes_nothing(linked, snn_server):
    from xzr.gaisho.bodysnn import ENCODING, replay_cell

    dom = domain_registry()["004-body"]
    a = replay_cell(dom, HUMAN, 2, 2, [1, 2, 3, 4])
    assert a["kind"] == "B2_OPEN_LOOP_REPLAY" and a["figure_kind"] == "EXECUTED_COMPUTATIONAL_EXPERIMENT" and a["body"]["body"] == "XB-TRO" and ENCODING["status"].startswith("STIPULATED")
    for rec in a["records"]:
        assert {"sensor_input", "spikes", "internal_state", "bodily_output", "environment_return"} <= set(rec)  # separate records, not one number
        assert len(rec["sensor_input"]["current"]) == len(rec["internal_state"]["membrane"]) == 800 and rec["spikes"]["count"] == len(rec["spikes"]["steps"])
        assert all(c >= 0 for c in rec["sensor_input"]["current"])  # the stipulated encoding is an unsigned magnitude
    assert a["weights"].startswith("NONE") and a["plasticity"].startswith("NONE") and a["memory"].startswith("NONE") and a["coupling"].startswith("OPEN LOOP")
    assert a["attribution"] == "UNRESOLVED" and a["applicability_gate"].startswith("NOT_PASSED") and "Det_D, not Occ_G" in a["applicability_gate"]
    assert "not a Gaisho" in a["operational_summary"]["reading"] and "bodily_output" in a["records"][0]
    b = replay_cell(dom, HUMAN, 2, 2, [1, 2, 3, 4])
    assert a["digest"] == b["digest"]  # reproducible
    with pytest.raises(ValueError):
        replay_cell(dom, HUMAN, 9, 9, [1])


@needs_snn
@needs_body
def test_the_body_snn_route_needs_both_links_and_is_bounded(linked, snn_server):
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    sp = c.get("/api/gaisho/spec").json()["links"]
    assert sp["xbtro"] is True and sp["xenosnn"] is True and sp["snn_encoding"]["status"].startswith("STIPULATED")
    ok = c.post("/api/gaisho/body-snn", json={"condition": HUMAN, "i": 2, "j": 2, "seeds": [1, 2]})
    assert ok.status_code == 200 and ok.json()["records"][0]["spikes"]["count"] >= 0 and ok.json()["attribution"] == "UNRESOLVED"
    for bad in ({"condition": "nope", "i": 2, "j": 2}, {"condition": HUMAN, "i": 9, "j": 2}, {"condition": HUMAN, "i": True, "j": 2}, {"condition": HUMAN, "i": 2, "j": 2, "seeds": [1, 2, 3, 4, 5]}, {"condition": HUMAN, "i": 2, "j": 2, "seeds": []}):
        assert c.post("/api/gaisho/body-snn", json=bad).status_code == 422, bad


def test_the_body_snn_route_refuses_without_the_links_and_computes_nothing(monkeypatch):
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    monkeypatch.delenv(bodylink.ENV, raising=False)
    monkeypatch.delenv(snnlink.ENV, raising=False)
    bodylink._CACHE.clear()
    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    r = c.post("/api/gaisho/body-snn", json={"condition": HUMAN, "i": 0, "j": 0})
    assert r.status_code == 422 and "not linked" in r.json()["detail"]
    assert c.get("/api/gaisho/spec").json()["links"]["xenosnn"] is False


def test_the_saved_extended_comparison_keeps_the_refusal_apart_from_the_falls_and_its_controls_are_the_presets():
    root = Path(__file__).resolve().parents[2] / "docs" / "gaisho"
    m = json.loads((root / "experiments_body_matched_extended.json").read_text())
    assert m["seeds"] == list(range(1, 9)) and m["uncovered_differences"] == []
    refused = m["refused_by_xbtro"]
    assert list(refused) == ["human-like planar body at the integration step 0.02 s"] and refused[next(iter(refused))]["largest_step_amplification"] > 1
    assert not set(refused) & set(m["conditions"])  # a refused configuration is not run and is not counted as a fall
    assert len(m["conditions"]) == 15 and {HUMAN, MACHINE} <= set(m["conditions"])
    mean = lambda c, n: m["conditions"][c]["relations"][n]["mean"]  # noqa: E731
    assert mean(HUMAN, "effect_x") == 0.6 and all(mean(f"human-like planar body at the integration step {dt} s", "effect_x") == 0.6 for dt in ("0.0025", "0.005"))  # the human-like preset does not move with the step
    mach = [mean(f"machine-like planar body at the integration step {dt} s", "effect_x") for dt in ("0.0025", "0.01", "0.02")]
    assert mach == [0.2, 0.4, -0.375] and mean(MACHINE, "effect_x") == 0.25  # the machine-like preset does


@needs_body
def test_a_saved_extended_condition_is_reproduced_and_an_unstable_step_is_refused_not_run(linked):
    from xzr.gaisho.bodymatched import ExtendedMatchedDomain
    from xzr.gaisho.lab import run_domain

    root = Path(__file__).resolve().parents[2] / "docs" / "gaisho"
    m = json.loads((root / "experiments_body_matched_extended.json").read_text())
    dom = ExtendedMatchedDomain()
    cond = "machine-like planar body at the integration step 0.0025 s"
    res = run_domain(dom, FULL, tuple(m["seeds"]), [cond])
    cells = res["conditions"][cond]["snapshots"]["end"]["cells"]
    grid = [[next(c["p"] for c in cells if c["i"] == i and c["j"] == j) for i in range(5)] for j in range(5)]
    assert grid == m["conditions"][cond]["fell_share_grid"]
    refused = "human-like planar body at the integration step 0.02 s"
    assert dom.link.engine.Params(dom.base_config(refused)).numeric_stability()["stable"] is False
