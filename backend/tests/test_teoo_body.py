"""TEOO Open Body Graph: declared, versioned, not human-fixed; severing, rejoining and reconfiguration are new versions; an association is never a cause."""

from __future__ import annotations

import copy

import pytest

from xzr.teoo import body as B

AT = "2026-01-01T00:00:00.000000Z"


def test_a_body_is_declared_as_a_graph_and_validates():
    b = B.new_body("b1", "toy", "unknown", components=[B.component("a", "part"), B.component("b", "part")], relations=[B.relation("r", "a", "b", "joint")],
                   constraints=[B.constraint("c", ["r"], "range", "an angle range", lo=-1, hi=1)], boundaries=[B.boundary("bd", ["a", "b"], "everything")], targets=[B.target("t", "r", ["v"])], at=AT)
    assert B.validate_body(b) == [] and b.current["version"] == 1 and b.current["change"] == {"op": "declare"}
    broken = B.new_body("b2", "x", "unknown", components=[B.component("a", "part")], relations=[B.relation("r", "a", "ghost", "joint")], at=AT)
    assert "DANGLING" in {i.code for i in B.validate_body(broken)}
    dup = B.new_body("b3", "x", "unknown", components=[B.component("a", "part"), B.component("a", "part")], at=AT)
    assert "DUPLICATE_ID" in {i.code for i in B.validate_body(dup)}
    assert "BAD_FAMILY" in {i.code for i in B.validate_body(B.new_body("b4", "x", "martian", at=AT))}


def test_the_human_skeleton_is_one_preset_and_the_schema_does_not_depend_on_it():
    h = B.human_simplified_skeleton(at=AT)
    assert h.family == "human" and h.meta["preset"] == "human-simplified-skeleton/1" and h.meta["concept_only"] is True
    assert len(h.current["components"]) == 14 and len(h.current["relations"]) == 13 and B.validate_body(h) == []
    assert all(c["attrs"]["concept_only"] for c in h.current["components"])  # the coordinates are a drawing, not an anatomical measurement
    import inspect

    src = inspect.getsource(B).lower()
    assert "mediapipe" not in src and "landmark" not in src  # the body module has no landmark schema: a skeleton is a preset


def test_non_human_bodies_are_registered_by_the_same_schema():
    for name, f, family in (("distributed-array", B.distributed_array, "distributed"), ("articulated-artificial", B.articulated_artificial, "artificial"), ("radial-non-human", B.radial_non_human, "non-human")):
        b = f(at=AT)
        assert b.family == family and B.validate_body(b) == [] and name in B.PRESETS
    rad = B.radial_non_human(arms=7, at=AT)
    assert len([c for c in rad.current["components"] if c["kind"] == "limb"]) == 7  # no fixed number of limbs, no spine, no bilateral symmetry
    dist = B.distributed_array(n=9, at=AT)
    assert all(r["kind"] == "coupling" for r in dist.current["relations"]) and not any(c["kind"] == "segment" for c in dist.current["components"])
    assert dist.current["boundaries"][0]["defined_by"] == "observer" and dist.current["boundaries"][0]["observer"]  # a boundary can depend on who observes


def test_every_change_of_the_structure_is_a_new_version_and_the_history_is_kept():
    b0 = B.articulated_artificial(at=AT)
    b1 = B.sever(b0, "j2", at=AT, note="cable cut")
    b2 = B.rejoin(b1, "j2", at=AT, note="reconnected")
    b3 = B.add_component(b2, B.component("camera", "sensor"), at=AT)
    b4 = B.connect(b3, B.relation("cam", "camera", "base", "mount"), at=AT)
    assert [v["version"] for v in b4.versions] == [1, 2, 3, 4, 5] and [c["change"]["op"] for c in B.configuration_changes(b4)] == ["declare", "sever", "rejoin", "add_component", "connect"]
    assert b0.current["version"] == 1 and len(b0.versions) == 1  # the earlier body object was not changed
    assert b4.at(2)["relations"][1]["state"] == "severed" and b4.at(3)["relations"][1]["state"] == "active" and b4.at(1)["relations"][1]["state"] == "active"
    assert all(v["parent"] == v["version"] - 1 for v in b4.versions[1:]) and B.validate_body(b4) == []


def test_severing_and_rejoining_are_recorded_and_the_history_cannot_be_rewritten_silently():
    b = B.sever(B.human_simplified_skeleton(at=AT), "knee_l", at=AT, note="amputation modelled as a cut")
    assert b.current["relations"][next(i for i, r in enumerate(b.current["relations"]) if r["id"] == "knee_l")]["state"] == "severed"
    d = b.to_dict()
    tampered = copy.deepcopy(d)
    tampered["versions"][0]["relations"][0]["state"] = "severed"  # an earlier version is edited
    assert "VERSION_DIGEST_MISMATCH" in {i.code for i in B.validate_body(tampered)}
    d2 = copy.deepcopy(d)
    d2["versions"][1]["change"]["note"] = "something else"
    assert "VERSION_DIGEST_MISMATCH" in {i.code for i in B.validate_body(d2)}
    assert B.Body.from_dict(d).current["digest"] == b.current["digest"]


def test_removing_a_component_records_which_relations_went_with_it():
    b = B.remove_component(B.human_simplified_skeleton(at=AT), "shank_l", at=AT)
    assert set(b.current["change"]["removed_relations"]) == {"knee_l", "ankle_l"} and B.validate_body(b) == []
    assert all(t["ref"] not in {"shank_l", "knee_l", "ankle_l"} for t in b.current["targets"]) and "shank_l" in {c["id"] for c in b.at(1)["components"]}  # the targets of the removed parts went too; the earlier version still has them
    assert any(t["ref"] == "knee_l" for t in b.at(1)["targets"])


def test_a_boundary_change_is_a_new_version_and_a_boundary_may_depend_on_the_observer():
    b = B.distributed_array(n=6, at=AT)
    wider = B.change_boundary(b, "bd.observer", ["node_0", "node_1", "node_2", "node_3"], at=AT, note="a second sensor extends the reach")
    assert wider.current["boundaries"][0]["members"] == ["node_0", "node_1", "node_2", "node_3"] and b.current["boundaries"][0]["members"] == ["node_0", "node_1", "node_2"]
    assert wider.current["change"]["op"] == "change_boundary" and wider.current["boundaries"][0]["observer"] == "observer-A"


def test_a_correlation_is_never_recorded_as_a_cause():
    b = B.new_body("b", "x", "unknown", components=[B.component("a", "part"), B.component("c", "part")], at=AT)
    corr = B.connect(b, B.relation("r1", "a", "c", "coupling", basis="observed", claim="association"), at=AT)
    assert B.validate_body(corr) == [] and corr.current["relations"][0]["claim"] == "association"
    unsupported = B.connect(b, B.relation("r2", "a", "c", "coupling", basis="observed", claim="causal"), at=AT)
    assert "CAUSAL_WITHOUT_SUPPORT" in {i.code for i in B.validate_body(unsupported)}
    bad_design = B.connect(b, B.relation("r3", "a", "c", "coupling", basis="estimated", claim="causal", support=["rec-1"], design="correlation-study"), at=AT)
    assert "CAUSAL_WITHOUT_SUPPORT" in {i.code for i in B.validate_body(bad_design)}
    structural_observed = B.connect(b, B.relation("r4", "a", "c", "joint", basis="observed", claim="structural"), at=AT)
    assert "STRUCTURAL_NOT_DECLARED" in {i.code for i in B.validate_body(structural_observed)}
    with pytest.raises(ValueError):
        B.promote_to_causal(corr, "r1", [], "intervention-comparison")
    with pytest.raises(ValueError):
        B.promote_to_causal(corr, "r1", ["rec-1"], "observational")
    promoted = B.promote_to_causal(corr, "r1", ["rec-1"], "intervention-comparison", at=AT)
    assert promoted.current["relations"][0]["claim"] == "causal" and promoted.at(2)["relations"][0]["claim"] == "association" and B.validate_body(promoted) == []  # the association stays in the history
