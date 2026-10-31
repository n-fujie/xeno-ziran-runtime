"""TEOO Phase 3: observation / intervention / counterfactual model are three different things; no causal claim from a before/after difference; figures keep their evidence band and class watermarks; no generated image is a photograph; the session bundle is one consistent set of records."""

from __future__ import annotations

import base64
import re

import pytest
from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.teoo import causal as CA
from xzr.teoo import export as EX
from xzr.teoo import media as MD
from xzr.teoo import session as SE
from xzr.teoo.provenance import Kind, Provenance, ProvenanceError, seal, verify_record

client = TestClient(app_mod.app)
S = SE.build_session()
BY_ID = {r["record_id"]: r for r in S["records"]}


# ------------------------------------------------------------------------------------------------ causal
def test_intervention_and_counterfactual_are_their_own_kinds_and_the_counterfactual_is_never_measured():
    iv, cf = BY_ID[S["intervention"]["record_id"]], BY_ID[S["intervention"]["counterfactual"]]
    assert iv["kind"] == Kind.INTERVENTION.value and cf["kind"] == Kind.COUNTERFACTUAL_MODEL.value and cf["provenance"] != "MEASURED"
    assert BY_ID[S["intervention"]["pre"]]["kind"] == Kind.OBSERVATION.value
    for r in (iv, cf):
        assert verify_record(r) == []
    with pytest.raises(ProvenanceError):  # a measurement cannot be a counterfactual model
        seal({"x": 1}, provenance=Provenance.MEASURED, kind=Kind.COUNTERFACTUAL_MODEL, creator=SE.CREATOR, source={"kind": "device", "description": "d", "declared_by": "x"}, created_at=SE.AT)


def test_a_before_after_difference_is_reported_as_an_observed_difference_with_no_causal_claim():
    d = S["intervention"]["observed_difference"]
    assert d["observed_difference"] < -3 and d["causal_claim"] is None and "not a causal effect" in d["reading"] and d["n_pre"] == d["n_post"] == 500
    idn = S["intervention"]["identification"]
    assert idn["status"] == "association" and len(idn["why_not_causal"]) == 3  # not randomised, exploratory, an unaddressed confounder


def test_identification_needs_randomisation_a_confirmatory_analysis_and_no_open_confounder_and_even_then_is_conditional():
    ok = CA.identify({"assignment": "randomized", "protocol_analysis_class": "confirmatory", "confounders_unaddressed": [], "n": 48})
    assert ok["status"].startswith("causal effect supported under the stated assumptions") and "not established" in ok["statement"] and ok["assumptions"]
    for bad in ({"assignment": "natural"}, {"protocol_analysis_class": "exploratory (the protocol was not frozen)"}, {"confounders_unaddressed": ["c"]}, {"n": 1}):
        assert CA.identify({"assignment": "randomized", "protocol_analysis_class": "confirmatory", "confounders_unaddressed": [], "n": 48, **bad})["status"] == "association"
    with pytest.raises(ValueError):
        CA.intervention_record(description="d", kind_of_action="a", target="t", applied_at_s=0, assignment="because", body_version_before=1, body_version_after=1, config_version_before=1, config_version_after=1,
                               provenance="SYNTHETIC", creator=SE.CREATOR, source=SE.SOURCE)


def test_a_change_of_the_observation_configuration_is_named_as_such_in_the_comparison():
    iv = CA.intervention_record(description="move the sensor", kind_of_action="move-sensor", target="knee_l", applied_at_s=1.0, assignment="researcher-chosen", body_version_before=1, body_version_after=1, config_version_before=1,
                                config_version_after=2, provenance="SYNTHETIC", creator=SE.CREATOR, source=SE.SOURCE, created_at=SE.AT)
    pre, post = BY_ID[S["intervention"]["pre"]], BY_ID[S["intervention"]["post"]]
    c = CA.compare_pre_post(pre, post, "joint.angle.knee_l", iv)
    assert c["observation_configuration_changed"] and "not even the same observation" in c["reading"]


def test_the_structural_model_distinguishes_do_from_conditioning_and_keeps_its_assumptions():
    m = CA.StructuralModel({"z": {"parents": {}, "intercept": 0.0, "noise_sd": 1.0}, "x": {"parents": {"z": 1.0}, "noise_sd": 0.1}, "y": {"parents": {"x": 2.0, "z": 3.0}, "noise_sd": 0.1}},
                           assumptions=["linear"], identification=["z is the only confounder"], scope="test")
    obs = m.simulate(1, 4000)
    import numpy as np

    naive = np.polyfit(obs["x"], obs["y"], 1)[0]  # confounded: about 2 + 3 = 5
    done = m.simulate(1, 4000, do={"x": 1.0})["y"], m.simulate(1, 4000, do={"x": 0.0})["y"]
    assert naive > 4.0 and float(np.mean(done[0]) - np.mean(done[1])) == pytest.approx(2.0, abs=0.2)  # the interventional contrast recovers the structural coefficient
    cf = m.counterfactual({"z": 0.5, "x": 0.5, "y": 2.5}, {"x": 1.5})
    assert cf["z"] == 0.5 and cf["x"] == 1.5 and cf["y"] == pytest.approx(2.5 + 2.0 * 1.0)  # the unit's own noise is kept
    with pytest.raises(ValueError):
        m.counterfactual({"z": 1.0}, {"x": 0.0})
    with pytest.raises(ValueError):
        CA.StructuralModel({"a": {"parents": {"b": 1.0}}, "b": {"parents": {"a": 1.0}}}, assumptions=["x"], identification=["x"], scope="x")
    with pytest.raises(ValueError):
        CA.StructuralModel({"a": {"parents": {}}}, assumptions=[], identification=["x"], scope="x")


def test_a_counterfactual_from_synthetic_input_is_synthetic_and_from_real_input_is_a_reconstructed_estimate():
    real = seal({"channels": []}, provenance=Provenance.MEASURED, kind=Kind.OBSERVATION, creator=SE.CREATOR, source={"kind": "device", "description": "d", "declared_by": "x"}, created_at=SE.AT)
    m = CA.StructuralModel({"a": {"parents": {}, "noise_sd": 0.0}}, assumptions=["x"], identification=["x"], scope="x")
    assert CA.counterfactual_record(m, {"a": 1.0}, {"a": 0.0}, parents=[real], creator=SE.CREATOR, created_at=SE.AT)["provenance"] == "RECONSTRUCTED_ESTIMATE"
    assert BY_ID[S["intervention"]["counterfactual"]]["provenance"] == "SYNTHETIC"
    assert CA.counterfactual_record(m, {"a": 1.0}, {"a": 0.0}, parents=[], creator=SE.CREATOR, created_at=SE.AT)["provenance"] == "SYNTHETIC"


# ------------------------------------------------------------------------------------------------ media
def test_a_generated_image_cannot_be_registered_as_a_photograph_and_is_labelled_as_what_it_is():
    png = EX.png_encode(2, 2, bytes(16))
    with pytest.raises(ProvenanceError):
        MD.register_media(png, "image/png", provenance="MEASURED", source={"kind": "generator", "description": "render", "declared_by": "x"}, creator=SE.CREATOR, created_at=SE.AT)
    with pytest.raises(ProvenanceError):
        MD.register_media(png, "image/png", provenance="MEASURED", source={"kind": "device", "device": "cam", "declared_by": "x"}, creator=SE.CREATOR, created_at=SE.AT)  # no capture time
    with pytest.raises(ProvenanceError):
        MD.register_media(b"x", "text/html", provenance="SYNTHETIC", source=SE.SOURCE, creator=SE.CREATOR)
    for prov, text in (("SYNTHETIC", "NOT a photograph"), ("RECONSTRUCTED_ESTIMATE", "NOT a photograph"), ("CONCEPTUAL", "NOT a photograph")):
        src = {"kind": "generator", "description": "g", "declared_by": "x"} if prov != "CONCEPTUAL" else {"kind": "researcher", "description": "c", "declared_by": "x"}
        rec = MD.register_media(png, "image/png", provenance=prov, source=src, creator=SE.CREATOR, created_at=SE.AT)
        assert text in MD.presentation_label(rec) and not MD.is_photograph(rec)
    cam = MD.register_media(png, "image/png", provenance="MEASURED", source={"kind": "device", "description": "a camera", "device": "cam-1", "captured_at": "2026-01-01T00:00:00Z", "declared_by": "operator"}, creator=SE.CREATOR, created_at=SE.AT)
    assert MD.is_photograph(cam) and "not verified" in MD.presentation_label(cam)  # even a declared photograph is only 'declared'


# ------------------------------------------------------------------------------------------------ export
@pytest.mark.parametrize("kind", ["timeseries", "body", "limits", "evidence"])
def test_every_figure_carries_its_band_watermark_metadata_and_verifies(kind):
    f = SE.figure_for(S, kind)
    md = f["metadata"]
    assert EX.verify_svg(f["svg"]) == [] and md["evidence"]["classes"] and "SYNTHETIC" in md["evidence"]["classes"] and "SYNTHETIC" in md["evidence"]["watermarks"]
    assert md["evidence"]["real_world_experiment_recorded"] is False and any("none recorded" in b for b in md["evidence"]["band"])
    assert md["generated_at"] and md["body"]["version"] == 1 and md["provenance"]["records"] and md["claim"]
    assert "<script" not in f["svg"] and "<image" not in f["svg"] and "http://" not in f["svg"].replace("http://www.w3.org/2000/svg", "")
    if kind == "body":
        assert "CONCEPTUAL" in md["evidence"]["watermarks"]
    if kind == "limits":
        assert md["observation_limits"]["summary"] and "not an acquisition" in md["observation_limits"]["note"]
    if kind == "evidence":
        assert md["experiment"]["protocol_id"] == "exp-demo-brace" and md["experiment"]["seeds"] == [1, 2, 3, 4, 5]


def test_the_same_inputs_give_the_same_figure_and_a_different_input_a_different_one():
    a, b = SE.figure_for(S, "timeseries"), SE.figure_for(SE.build_session(7), "timeseries")
    assert a["svg"] == b["svg"] and a["metadata"]["metadata_digest"] == b["metadata"]["metadata_digest"]
    assert SE.figure_for(SE.build_session(8), "timeseries")["metadata"]["figure_id"] != a["metadata"]["figure_id"]
    assert SE.figure_for(S, "timeseries", generated_at="2027-01-01T00:00:00Z")["metadata"]["metadata_digest"] != a["metadata"]["metadata_digest"]


def test_removing_the_band_or_a_watermark_or_editing_the_metadata_is_detected():
    svg = SE.figure_for(S, "timeseries")["svg"]
    no_band = svg.replace('class="teoo-band-bg"', 'class="x"')
    no_mark = re.sub(r'<text[^>]*class="teoo-watermark" data-class="SYNTHETIC">.*?</text>', "", svg)
    no_text = re.sub(r'<text[^>]*class="teoo-band"[^>]*>EVIDENCE.*?</text>', "", svg)
    no_meta = re.sub(r"<metadata.*?</metadata>", "", svg, flags=re.S)
    edited = svg.replace('"real_world_experiment_recorded":false', '"real_world_experiment_recorded":true')
    relabelled = svg.replace('"SYNTHETIC"', '"MEASURED"', 1)
    for bad, hint in ((no_band, "band"), (no_mark, "watermark"), (no_text, "band"), (no_meta, "metadata"), (edited, "digest"), (relabelled, "")):
        issues = EX.verify_svg(bad)
        assert issues and (not hint or any(hint in i for i in issues)), (hint, issues)


def test_the_png_carries_the_same_metadata_and_a_png_without_it_or_with_a_damaged_chunk_is_flagged():
    f = SE.figure_for(S, "evidence")
    png = EX.png_add_text(EX.png_encode(4, 3, bytes(48)), EX.TEXT_KEY, EX.metadata_ascii(f["metadata"]))
    r = EX.inspect_png(png)
    assert r["ok"] and r["metadata"] == f["metadata"] and (r["width"], r["height"]) == (4, 3) and "pixels were not examined" in r["note"]
    assert not EX.inspect_png(EX.png_encode(2, 2, bytes(16)))["ok"] and not EX.inspect_png(b"nope")["ok"]
    broken = bytearray(png)
    broken[png.index(b"teoo-metadata") + 20] ^= 1
    assert not EX.inspect_png(bytes(broken))["ok"]
    md = dict(f["metadata"], title="changed")
    assert "digest" in " ".join(EX.inspect_png(EX.png_add_text(EX.png_encode(2, 2, bytes(16)), EX.TEXT_KEY, EX.metadata_ascii(md)))["issues"])
    uni = dict(f["metadata"], title="脚 ‘x’")  # a non-ASCII title survives the Latin-1 text chunk by escaping
    assert '\\u811a' in EX.metadata_ascii(uni) and EX.metadata_ascii(uni).isascii()


# ------------------------------------------------------------------------------------------------ session bundle and routes
def test_the_session_is_one_consistent_set_of_records_for_all_views():
    ids = set(S["record_index"])
    assert ids == {r["record_id"] for r in S["records"]} and S["ledger"]["issues"] == [] and S["synthetic"] and S["banner"]
    assert all(verify_record(r) == [] for r in S["records"]) and {e["record_id"] for e in S["evidence"]} == ids
    assert {S["reconstruction"]["record_id"], S["reconstruction"]["input_record_id"], S["intervention"]["record_id"], S["intervention"]["pre"], S["intervention"]["post"], S["intervention"]["counterfactual"]} <= ids
    assert {r["provenance"] for r in S["records"]} == {"SYNTHETIC", "RECONSTRUCTED_ESTIMATE"} and not any(r["provenance"] == "MEASURED" for r in S["records"])
    assert S["bodies"]["1"]["versions"][-1]["version"] == 1 and S["bodies"]["3"]["versions"][-1]["version"] == 3 and S["body_versions"] == {"before": 1, "after": 3}
    assert S["observation"]["history"][0]["body_version"] == 1 and all(x["version_ok"] for x in S["observation"]["replay_check"])
    p = S["protocol"]
    assert p["reproduction"]["identical"] and p["registry_ok"] and p["analysis_classes"]["AN1"] == "confirmatory" and p["amended"]["version"] == 2
    assert S["reconstruction"]["lost"]["n_samples"] == 40 and "not an observation" in S["reconstruction"]["lost"]["statement"]
    assert S["relation_field"]["epistemically_open"] and S["relation_field"]["completeness_claim"] is None


def test_the_session_is_deterministic_and_seed_dependent():
    assert SE.build_session(7)["records"][0]["record_id"] == S["records"][0]["record_id"] and SE.build_session(8)["records"][0]["record_id"] != S["records"][0]["record_id"]


def test_the_new_routes_return_the_session_the_observation_state_figures_and_the_safety_gate():
    s = client.get("/api/teoo/session").json()
    assert s["records"][0]["record_id"] == S["records"][0]["record_id"] and s["synthetic"]
    o = client.get("/api/teoo/observation", params={"t": 12}).json()
    assert o["version"] == 3 and o["declared_targets"] == 7 and o["observed"] == 5
    assert client.get("/api/teoo/observation", params={"t": -1}).status_code == 422 and client.get("/api/teoo/observation", params={"t": 1e9}).status_code == 422
    f = client.post("/api/teoo/figure", json={"kind": "timeseries"}).json()
    assert f["issues"] == [] and EX.verify_svg(f["svg"]) == [] and f["metadata_ascii"].isascii()
    assert client.post("/api/teoo/figure", json={"kind": "photo"}).status_code == 422
    assert client.post("/api/teoo/figure/verify", json={"svg": f["svg"]}).json()["issues"] == []
    assert client.post("/api/teoo/figure/verify", json={"svg": f["svg"].replace('class="teoo-band-bg"', "")}).json()["issues"]
    png = EX.png_add_text(EX.png_encode(2, 2, bytes(16)), EX.TEXT_KEY, f["metadata_ascii"])
    assert client.post("/api/teoo/figure/verify", json={"png_base64": base64.b64encode(png).decode()}).json()["ok"] is True
    assert client.post("/api/teoo/figure/verify", json={}).status_code == 422
    g = client.get("/api/teoo/safety").json()
    assert g["stored_on_server"] is False and g["human_measurement_ingestion_allowed"] is False and g["production_ready"] is False


def test_the_new_routes_are_local_only_and_the_figure_routes_are_listed_as_mutating(monkeypatch):
    import dataclasses

    from xzr.service import studies
    from xzr.service.limits import LIMITS

    routes = (("get", "/api/teoo/session", {}), ("get", "/api/teoo/observation", {}), ("post", "/api/teoo/figure", {"json": {"kind": "body"}}), ("post", "/api/teoo/figure/verify", {"json": {"svg": "<svg/>"}}), ("get", "/api/teoo/safety", {}))
    assert all(getattr(client, m)(p, **kw).status_code == 200 for m, p, kw in routes)
    monkeypatch.setattr(studies, "LIMITS", dataclasses.replace(LIMITS, public=True))
    assert all(getattr(client, m)(p, **kw).status_code == 403 for m, p, kw in routes)
    monkeypatch.setattr(studies, "LIMITS", LIMITS)
    foreign = TestClient(app_mod.app, headers={"origin": "https://elsewhere.example"})
    assert foreign.post("/api/teoo/figure", json={"kind": "body"}).status_code == 403
