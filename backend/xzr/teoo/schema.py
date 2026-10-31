"""Schema Registry: the versioned schemas of TEOO records, the 16 variable domains, and the variable registry.

A record names its schema (``schema: "teoo.observation/1"``); an unknown or missing schema is an error, never a guess. Validation returns a list of
:class:`Issue` (field, code, message, fixable) and never repairs anything. The variable registry is extensible (custom variables, versioned): the initial
content is a small *declared* set (no measurement is implied by a variable being registered)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_IDS = ("teoo.observation/1", "teoo.body/1", "teoo.variable/1", "teoo.ledger-entry/1")


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    message: str
    fixable: bool = False
    suggestion: str = ""
    severity: str = "error"  # "error" blocks registration; "warning" is kept in the record's validation and never silently dropped

    def to_dict(self) -> dict:
        return {"field": self.field, "code": self.code, "message": self.message, "fixable": self.fixable, "suggestion": self.suggestion, "severity": self.severity}


DOMAINS = (
    ("thermoregulation", "Thermoregulation"), ("cardiovascular", "Cardiovascular dynamics"), ("respiratory", "Respiratory dynamics"), ("kinematics", "Kinematics"),
    ("posture_balance", "Posture and balance"), ("muscular_contact", "Muscular activity and physical contact"), ("sensorimotor", "Sensorimotor coordination"),
    ("sleep_recovery", "Sleep and recovery"), ("cognition_attention", "Cognition and attention"), ("command_autonomy", "Command dependence and operational autonomy"),
    ("environment", "Environmental conditions"), ("social", "Social connectivity"), ("institutional_material", "Institutional and material access"),
    ("learning_retention", "Bodily learning and historical retention"), ("observation_apparatus", "Observation apparatus and measurement limitations"),
    ("cross_domain", "Cross-domain operational dependencies"),
)
DOMAIN_IDS = tuple(d for d, _ in DOMAINS)
PRIVACY = ("public", "pseudonymous", "personal", "sensitive-personal")
MISSING_CLASSES = ("never-recorded-as-zero", "dropout-null", "not-applicable", "undeclared")
DTYPES = ("float", "int", "bool", "category", "text", "vector")

VARIABLE_FIELDS = ("id", "domain", "description", "unit", "dtype", "method", "source", "sampling_hz", "resolution", "calibration", "uncertainty", "valid_interval",
                   "anatomical_ref", "privacy", "missing_class", "provenance_note", "transformations")


@dataclass
class Variable:
    id: str
    domain: str
    description: str
    unit: str | None  # None = dimensionless / not applicable, stated, never assumed
    dtype: str = "float"
    method: str = "undeclared"
    source: str = "undeclared"
    sampling_hz: float | None = None
    resolution: float | None = None
    calibration: str = "undeclared"
    uncertainty: float | None = None
    valid_interval: tuple[float, float] | None = None
    anatomical_ref: str | None = None
    privacy: str = "personal"
    missing_class: str = "never-recorded-as-zero"
    provenance_note: str = "declared in the registry; no measurement is implied"
    transformations: tuple[str, ...] = ()
    schema: str = "teoo.variable/1"
    version: int = 1

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["valid_interval"] = list(self.valid_interval) if self.valid_interval else None
        d["transformations"] = list(self.transformations)
        return d


def validate_variable(v: Variable) -> list[Issue]:
    out: list[Issue] = []
    if not v.id or not all(c.isalnum() or c in "._-" for c in v.id):
        out.append(Issue("id", "BAD_ID", "a variable id is a non-empty stable identifier of letters, digits and . _ -"))
    if v.domain not in DOMAIN_IDS:
        out.append(Issue("domain", "UNKNOWN_DOMAIN", f"domain must be one of {DOMAIN_IDS}"))
    if v.dtype not in DTYPES:
        out.append(Issue("dtype", "BAD_DTYPE", f"dtype must be one of {DTYPES}"))
    if v.privacy not in PRIVACY:
        out.append(Issue("privacy", "BAD_PRIVACY", f"privacy classification must be one of {PRIVACY}"))
    if v.missing_class not in MISSING_CLASSES:
        out.append(Issue("missing_class", "BAD_MISSING_CLASS", f"missing-data classification must be one of {MISSING_CLASSES}"))
    if v.valid_interval is not None and not (len(v.valid_interval) == 2 and v.valid_interval[0] <= v.valid_interval[1]):
        out.append(Issue("valid_interval", "BAD_INTERVAL", "valid_interval is (low, high) with low <= high"))
    if v.sampling_hz is not None and not v.sampling_hz > 0:
        out.append(Issue("sampling_hz", "BAD_RATE", "sampling_hz must be positive"))
    if v.dtype == "float" and v.unit is None:
        out.append(Issue("unit", "UNIT_UNDECLARED", "a float variable names its unit, or states explicitly that it is dimensionless (unit '1')", fixable=True, suggestion="use '1' for dimensionless"))
    return out


class VariableRegistry:
    """A versioned, extensible registry. Registering a variable declares it; it does not say that anything was measured."""

    def __init__(self) -> None:
        self._vars: dict[str, Variable] = {}
        self.history: list[dict] = []

    def register(self, v: Variable) -> list[Issue]:
        issues = validate_variable(v)
        if issues:
            return issues
        old = self._vars.get(v.id)
        if old is not None:
            if old.to_dict() == v.to_dict():
                return []
            v.version = old.version + 1  # a changed definition is a new version; the old one stays in the history
        self._vars[v.id] = v
        self.history.append({"id": v.id, "version": v.version, "definition": v.to_dict()})
        return []

    def get(self, vid: str) -> Variable | None:
        return self._vars.get(vid)

    def __contains__(self, vid: str) -> bool:
        return vid in self._vars

    def __len__(self) -> int:
        return len(self._vars)

    def by_domain(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {d: [] for d in DOMAIN_IDS}
        for v in self._vars.values():
            out[v.domain].append(v.id)
        return out

    def to_dict(self) -> dict:
        return {"schema": "teoo.variable/1", "variables": [v.to_dict() for v in self._vars.values()], "history": self.history}


_SEED = (  # (id, domain, description, unit, dtype, resolution, anatomical_ref, privacy, sampling_hz): a small declared set; nothing is measured by declaring it
    ("temp.skin.forehead", "thermoregulation", "skin temperature at the forehead", "degC", "float", 0.1, "head", "personal", 1.0),
    ("temp.core.estimate", "thermoregulation", "core temperature estimated from a model", "degC", "float", 0.1, "trunk", "personal", 0.2),
    ("hr.beat", "cardiovascular", "heart rate", "1/min", "float", 1.0, "trunk", "sensitive-personal", 1.0),
    ("bp.systolic", "cardiovascular", "systolic blood pressure", "mmHg", "float", 1.0, "upper_arm_l", "sensitive-personal", None),
    ("resp.rate", "respiratory", "respiratory rate", "1/min", "float", 0.5, "trunk", "personal", 1.0),
    ("resp.chest_motion", "respiratory", "chest wall displacement", "mm", "float", 0.1, "trunk", "personal", 25.0),
    ("joint.angle.knee_l", "kinematics", "left knee flexion angle", "deg", "float", 0.1, "knee_l", "personal", 50.0),
    ("joint.angle.hip_l", "kinematics", "left hip flexion angle", "deg", "float", 0.1, "hip_l", "personal", 50.0),
    ("joint.angle.elbow_r", "kinematics", "right elbow flexion angle", "deg", "float", 0.1, "elbow_r", "personal", 50.0),
    ("joint.angle.ankle_l", "kinematics", "left ankle angle", "deg", "float", 0.1, "ankle_l", "personal", 50.0),
    ("posture.trunk.lean", "posture_balance", "trunk lean from vertical", "deg", "float", 0.1, "trunk", "personal", 25.0),
    ("balance.cop.x", "posture_balance", "centre of pressure, mediolateral", "mm", "float", 1.0, "foot_l", "personal", 100.0),
    ("emg.rms.quadriceps_l", "muscular_contact", "surface EMG RMS, left quadriceps", "mV", "float", 0.001, "thigh_l", "personal", 1000.0),
    ("contact.force.foot_l", "muscular_contact", "ground contact force, left foot", "N", "float", 1.0, "foot_l", "personal", 200.0),
    ("senso.reaction_time", "sensorimotor", "reaction time to a cue", "s", "float", 0.001, None, "personal", None),
    ("sleep.duration", "sleep_recovery", "sleep duration", "h", "float", 0.1, None, "sensitive-personal", None),
    ("cog.attention.score", "cognition_attention", "attention task score", "1", "float", 1.0, "head", "sensitive-personal", None),
    ("cmd.instruction.active", "command_autonomy", "an external instruction is active", None, "bool", None, None, "personal", None),
    ("env.temp.air", "environment", "air temperature", "degC", "float", 0.1, None, "public", 1.0),
    ("env.light.lux", "environment", "illuminance", "lx", "float", 1.0, None, "public", 1.0),
    ("social.contact.count", "social", "number of social contacts in the window", "1", "int", 1.0, None, "sensitive-personal", None),
    ("inst.access.device", "institutional_material", "a technical device is available", None, "bool", None, None, "personal", None),
    ("learn.retention.delay", "learning_retention", "delay between instruction and retention test", "s", "float", 1.0, None, "personal", None),
    ("obs.sensor.dropout", "observation_apparatus", "sensor dropout fraction in the window", "1", "float", 0.001, None, "public", 1.0),
    ("obs.sync.uncertainty", "observation_apparatus", "synchronisation uncertainty between clocks", "s", "float", 1e-6, None, "public", None),
    ("xdep.support.load", "cross_domain", "dependence of a function on a support (declared by the researcher)", "1", "float", 0.01, None, "personal", None),
)


def default_registry() -> VariableRegistry:
    r = VariableRegistry()
    for vid, dom, desc, unit, dt, res, ref, priv, hz in _SEED:
        issues = r.register(Variable(vid, dom, desc, unit, dt, method="undeclared (registry seed)", source="undeclared", sampling_hz=hz, resolution=res, anatomical_ref=ref, privacy=priv))
        assert not issues, (vid, issues)
    return r


# ------------------------------------------------------------------------------------------------ record schemas (required fields and types)
_T: dict[str, Any] = {"str": str, "int": int, "float": (int, float), "bool": bool, "list": list, "dict": dict, "str|None": (str, type(None))}
OBSERVATION_REQUIRED = {"schema": "str", "record_id": "str", "provenance": "str", "kind": "str", "creator": "dict", "source": "dict", "created_at": "str", "raw": "dict",
                        "payload": "dict", "derived_from": "list", "lineage_classes": "list", "transformations": "list", "validation": "dict", "record_digest": "str"}
BODY_REQUIRED = {"schema": "str", "id": "str", "name": "str", "family": "str", "versions": "list"}
LEDGER_REQUIRED = {"schema": "str", "seq": "int", "prev_hash": "str", "record": "dict", "entry_hash": "str"}
REQUIRED = {"teoo.observation/1": OBSERVATION_REQUIRED, "teoo.body/1": BODY_REQUIRED, "teoo.ledger-entry/1": LEDGER_REQUIRED}


def schema_of(record: Any) -> str | None:
    s = record.get("schema") if isinstance(record, dict) else None
    return s if isinstance(s, str) else None


def validate_schema(record: Any) -> list[Issue]:
    """Structure only (presence and type of the required fields, and a known schema id). Never repairs."""
    sid = schema_of(record)
    if sid is None:
        return [Issue("schema", "SCHEMA_MISSING", "the record names no schema; it is not interpreted by guessing", fixable=False)]
    if sid not in SCHEMA_IDS:
        return [Issue("schema", "SCHEMA_UNKNOWN", f"unknown schema {sid!r}; known: {SCHEMA_IDS}")]
    if sid not in REQUIRED:
        return []
    out: list[Issue] = []
    for k, t in REQUIRED[sid].items():
        if k not in record:
            out.append(Issue(k, "FIELD_MISSING", f"required field {k!r} is missing"))
        elif not isinstance(record[k], _T[t]) or (t == "int" and isinstance(record[k], bool)):
            out.append(Issue(k, "FIELD_TYPE", f"field {k!r} must be {t}"))
    return out


@dataclass
class SchemaInfo:
    id: str
    version: int
    required: tuple[str, ...] = field(default_factory=tuple)


def schema_version(sid: str) -> int:
    """The integer after the slash: 'teoo.observation/1' -> 1. A schema id without a version is not a schema id."""
    name, _, ver = sid.partition("/")
    if not name or not ver.isdigit():
        raise ValueError(f"not a versioned schema id: {sid!r}")
    return int(ver)
