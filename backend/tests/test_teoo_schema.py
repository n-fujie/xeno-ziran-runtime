"""TEOO Schema Registry: records name a versioned schema; an unknown or missing schema is an error, never a guess; the variable registry is extensible, versioned and has the 16 domains."""

from __future__ import annotations

import copy

import pytest

from xzr.teoo import provenance as P
from xzr.teoo import schema as SC
from xzr.teoo import synthetic as SY
from xzr.teoo.body import human_simplified_skeleton


def _rec():
    return SY.make_demo()["records"][0]


def test_a_valid_record_and_a_valid_body_pass_their_schemas():
    assert SC.validate_schema(_rec()) == []
    assert SC.validate_schema(human_simplified_skeleton().to_dict()) == []
    assert SC.schema_of(_rec()) == "teoo.observation/1" and set(SC.REQUIRED) <= set(SC.SCHEMA_IDS)


def test_a_record_without_a_schema_or_with_an_unknown_one_is_refused_without_a_guess():
    r = _rec()
    no = {k: v for k, v in r.items() if k != "schema"}
    assert [i.code for i in SC.validate_schema(no)] == ["SCHEMA_MISSING"]
    for bad in ("teoo.observation/9", "other.thing/1", "teoo.observation", ""):
        assert [i.code for i in SC.validate_schema({**r, "schema": bad})] == ["SCHEMA_UNKNOWN"], bad
    assert [i.code for i in SC.validate_schema("not a record")] == ["SCHEMA_MISSING"]
    assert P.verify_record({**r, "schema": "teoo.observation/9"})[0].code == "SCHEMA_UNKNOWN"  # verification does not go on with a record it cannot interpret


def test_missing_and_mistyped_required_fields_are_reported_one_by_one():
    r = copy.deepcopy(_rec())
    del r["provenance"]
    r["raw"] = "x"
    r["derived_from"] = {}
    codes = {(i.field, i.code) for i in SC.validate_schema(r)}
    assert codes == {("provenance", "FIELD_MISSING"), ("raw", "FIELD_TYPE"), ("derived_from", "FIELD_TYPE")}
    assert {(i.field, i.code) for i in SC.validate_schema({**_rec(), "seq": 1}) if i.code != "x"} == set()  # an extra field is not an error: schemas are open to additions


def test_the_schema_version_is_identified_from_the_id_and_a_version_less_id_is_not_a_schema_id():
    assert SC.schema_version("teoo.observation/1") == 1 and SC.schema_version("teoo.body/12") == 12
    for bad in ("teoo.observation", "teoo.observation/", "/1", "teoo.observation/x"):
        with pytest.raises(ValueError):
            SC.schema_version(bad)
    assert all(SC.schema_version(s) >= 1 for s in SC.SCHEMA_IDS)


def test_the_registry_has_sixteen_domains_and_the_declared_set_covers_all_of_them_without_implying_measurement():
    assert len(SC.DOMAINS) == 16 == len(set(SC.DOMAIN_IDS))
    reg = SC.default_registry()
    by = reg.by_domain()
    assert set(by) == set(SC.DOMAIN_IDS) and all(by[d] for d in SC.DOMAIN_IDS)
    assert all("no measurement is implied" in v.provenance_note for v in (reg.get(i) for i in reg._vars))


def test_every_registered_variable_carries_the_required_metadata():
    reg = SC.default_registry()
    d = reg.get("joint.angle.knee_l").to_dict()
    assert set(SC.VARIABLE_FIELDS) <= set(d), sorted(set(SC.VARIABLE_FIELDS) - set(d))
    assert d["unit"] == "deg" and d["privacy"] and d["missing_class"] == "never-recorded-as-zero" and d["anatomical_ref"] == "knee_l"


def test_a_bad_variable_is_refused_with_the_reason_and_a_custom_variable_is_accepted():
    reg = SC.VariableRegistry()
    bad = SC.Variable("x y", "nonsense", "d", None, dtype="matrix", privacy="secret", missing_class="zero", valid_interval=(5.0, 1.0), sampling_hz=-1.0)
    assert {i.code for i in reg.register(bad)} == {"BAD_ID", "UNKNOWN_DOMAIN", "BAD_DTYPE", "BAD_PRIVACY", "BAD_MISSING_CLASS", "BAD_INTERVAL", "BAD_RATE"}
    assert len(reg) == 0  # nothing half-registered
    assert [i.code for i in reg.register(SC.Variable("v.nounit", "kinematics", "a float without a declared unit", None))] == ["UNIT_UNDECLARED"]  # dimensionless is stated ('1'), not assumed
    assert reg.register(SC.Variable("custom.wing_angle", "kinematics", "wing angle of a non-human body", "deg")) == [] and "custom.wing_angle" in reg


def test_a_changed_definition_is_a_new_version_and_the_history_keeps_the_old_one():
    reg = SC.VariableRegistry()
    assert reg.register(SC.Variable("v.a", "kinematics", "first", "deg")) == []
    assert reg.register(SC.Variable("v.a", "kinematics", "first", "deg")) == [] and reg.get("v.a").version == 1  # the same definition is not a new version
    assert reg.register(SC.Variable("v.a", "kinematics", "second wording", "deg", resolution=0.5)) == []
    assert reg.get("v.a").version == 2 and [(h["id"], h["version"]) for h in reg.history] == [("v.a", 1), ("v.a", 2)] and reg.history[0]["definition"]["description"] == "first"
    assert reg.to_dict()["schema"] == "teoo.variable/1"
