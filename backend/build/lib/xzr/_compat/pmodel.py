"""A minimal pure-Python stand-in for the subset of pydantic v2 used by ``scenario/model.py``.

Used only where pydantic (whose core is a compiled Rust extension) is unavailable — the iOS app. On the desktop and
server pydantic itself is used. ``backend/tests/test_compat.py`` checks that both accept and reject the same
scenarios and produce identical ``model_dump`` output for every bundled and saved scenario.

Supported: annotated fields with defaults / ``Field(default | default_factory, ge, le, gt)``; the types ``int``,
``float``, ``str``, ``bool``, ``Literal``, ``X | None``, ``list[X]``, ``tuple[X, Y]``, ``dict[str, X]``, ``dict``,
nested models; ``model_config = ConfigDict(extra="forbid")``; ``@model_validator(mode="after")``;
``model_validate``, ``model_validate_json``, ``model_dump(mode="json", exclude_none=...)``, ``model_copy(update=)``.
Lax-mode coercions follow pydantic: int → float; integral float or numeric string → int; numeric string → float.
"""

from __future__ import annotations

import json
import math
import sys
import types
import typing
from typing import Any

_MISSING = object()


class ValidationError(ValueError):
    """Raised for invalid input; ``errors()`` / ``json()`` mirror pydantic's shape closely enough for callers."""

    def __init__(self, errors: list[dict]):
        self._errors = errors
        super().__init__("; ".join(f"{'.'.join(map(str, e['loc'])) or '<root>'}: {e['msg']}" for e in errors))

    def errors(self) -> list[dict]:
        return self._errors

    def json(self) -> str:
        return json.dumps(self._errors)


class _FieldInfo:
    def __init__(self, default: Any = _MISSING, *, default_factory: Any = None, ge: float | None = None,
                 le: float | None = None, gt: float | None = None):
        self.default, self.default_factory, self.ge, self.le, self.gt = default, default_factory, ge, le, gt


def Field(default: Any = _MISSING, *, default_factory: Any = None, ge: float | None = None,  # noqa: N802
          le: float | None = None, gt: float | None = None) -> Any:
    return _FieldInfo(default, default_factory=default_factory, ge=ge, le=le, gt=gt)


def ConfigDict(**kw: Any) -> dict:  # noqa: N802
    return dict(kw)


def model_validator(*, mode: str):
    if mode != "after":
        raise NotImplementedError("only mode='after' is supported")

    def deco(fn):
        fn.__xzr_after_validator__ = True
        return fn
    return deco


class _Err(Exception):
    def __init__(self, loc: tuple, msg: str):
        self.loc, self.msg = loc, msg


def _coerce(tp: Any, v: Any, loc: tuple) -> Any:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp is Any:
        return v
    if origin in (typing.Union, types.UnionType):
        if v is None and type(None) in args:
            return None
        errs = []
        for a in args:
            if a is type(None):
                continue
            try:
                return _coerce(a, v, loc)
            except _Err as e:
                errs.append(e)
        raise errs[0] if errs else _Err(loc, "invalid value")
    if origin is typing.Literal:
        if v in args:
            return v
        raise _Err(loc, f"Input should be {' or '.join(repr(a) for a in args)}")
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        if isinstance(v, tp):
            return v
        if not isinstance(v, dict):
            raise _Err(loc, f"Input should be a valid dictionary or instance of {tp.__name__}")
        return tp._validate(v, loc)
    if tp is bool:
        if isinstance(v, bool):
            return v
        raise _Err(loc, "Input should be a valid boolean")
    if tp is int:
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v
        if isinstance(v, float) and math.isfinite(v) and v == int(v):
            return int(v)
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                pass
        raise _Err(loc, "Input should be a valid integer")
    if tp is float:
        if isinstance(v, bool | int | float):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v.strip())
            except ValueError:
                pass
        raise _Err(loc, "Input should be a valid number")
    if tp is str:
        if isinstance(v, str):
            return v
        raise _Err(loc, "Input should be a valid string")
    if tp is dict or origin is dict:
        if not isinstance(v, dict):
            raise _Err(loc, "Input should be a valid dictionary")
        if not args:
            return dict(v)
        kt, vt = args
        return {_coerce(kt, k, (*loc, k)): _coerce(vt, x, (*loc, k)) for k, x in v.items()}
    if tp is list or origin is list:
        if not isinstance(v, list | tuple):
            raise _Err(loc, "Input should be a valid list")
        if not args:
            return list(v)
        return [_coerce(args[0], x, (*loc, i)) for i, x in enumerate(v)]
    if origin is tuple:
        if not isinstance(v, list | tuple) or len(v) != len(args):
            raise _Err(loc, f"Input should be a valid tuple of {len(args)} items")
        return tuple(_coerce(a, x, (*loc, i)) for i, (a, x) in enumerate(zip(args, v, strict=True)))
    raise _Err(loc, f"unsupported type {tp!r}")


class BaseModel:
    model_config: dict = {}
    __xzr_fields__: dict[str, tuple[Any, _FieldInfo]]
    __xzr_resolved__: bool = False

    def __init_subclass__(cls, **kw: Any):
        super().__init_subclass__(**kw)
        cls.__xzr_resolved__ = False

    @classmethod
    def _fields(cls) -> dict[str, tuple[Any, _FieldInfo]]:
        if not cls.__dict__.get("__xzr_resolved__"):
            hints: dict[str, Any] = {}
            for klass in reversed(cls.__mro__):  # each model's own annotations, in its own module's namespace
                if klass is BaseModel or not (isinstance(klass, type) and issubclass(klass, BaseModel)):
                    continue
                namespace = vars(sys.modules[klass.__module__])
                for name, ann in klass.__dict__.get("__annotations__", {}).items():
                    hints[name] = eval(ann, namespace) if isinstance(ann, str) else ann  # noqa: S307 — annotations
            fields: dict[str, tuple[Any, _FieldInfo]] = {}
            for name, tp in hints.items():
                if name.startswith("_") or name == "model_config" or typing.get_origin(tp) is typing.ClassVar:
                    continue
                raw = getattr(cls, name, _MISSING)
                info = raw if isinstance(raw, _FieldInfo) else _FieldInfo(raw)
                fields[name] = (tp, info)
            cls.__xzr_fields__ = fields
            cls.__xzr_resolved__ = True
        return cls.__xzr_fields__

    @classmethod
    def _validate(cls, data: dict, loc: tuple = ()) -> Any:
        fields = cls._fields()
        errors: list[dict] = []
        extra = set(data) - set(fields)
        if cls.model_config.get("extra") == "forbid":
            for k in sorted(extra, key=str):
                errors.append({"type": "extra_forbidden", "loc": [*loc, k], "msg": "Extra inputs are not permitted"})
        obj = object.__new__(cls)
        for name, (tp, info) in fields.items():
            if name in data:
                try:
                    v = _coerce(tp, data[name], (*loc, name))
                    for bound, ok, word in ((info.ge, lambda a, b: a >= b, "greater than or equal to"),
                                            (info.gt, lambda a, b: a > b, "greater than"),
                                            (info.le, lambda a, b: a <= b, "less than or equal to")):
                        if bound is not None and v is not None and not ok(v, bound):
                            raise _Err((*loc, name), f"Input should be {word} {bound}")
                except _Err as e:
                    errors.append({"type": "value_error", "loc": list(e.loc), "msg": e.msg})
                    continue
            elif info.default_factory is not None:
                v = info.default_factory()
            elif info.default is not _MISSING:
                v = info.default
            else:
                errors.append({"type": "missing", "loc": [*loc, name], "msg": "Field required"})
                continue
            object.__setattr__(obj, name, v)
        if errors:
            raise _Err(tuple(errors[0]["loc"]), errors[0]["msg"]) if loc else ValidationError(errors)
        for attr in dir(cls):
            fn = getattr(cls, attr, None)
            if callable(fn) and getattr(fn, "__xzr_after_validator__", False):
                try:
                    obj = fn(obj)
                except ValueError as e:
                    if loc:
                        raise _Err(loc, f"Value error, {e}") from e
                    raise ValidationError([{"type": "value_error", "loc": [], "msg": f"Value error, {e}"}]) from e
        return obj

    @classmethod
    def model_validate(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValidationError([{"type": "model_type", "loc": [], "msg": "Input should be a valid dictionary"}])
        try:
            return cls._validate(data)
        except _Err as e:
            raise ValidationError([{"type": "value_error", "loc": list(e.loc), "msg": e.msg}]) from e

    @classmethod
    def model_validate_json(cls, text: str | bytes) -> Any:
        try:
            data = json.loads(text)
        except ValueError as e:
            raise ValidationError([{"type": "json_invalid", "loc": [], "msg": f"Invalid JSON: {e}"}]) from e
        return cls.model_validate(data)

    def model_dump(self, *, mode: str = "python", exclude_none: bool = False) -> dict:
        def dump(v: Any) -> Any:
            if isinstance(v, BaseModel):
                return v.model_dump(mode=mode, exclude_none=exclude_none)
            if isinstance(v, dict):
                return {k: dump(x) for k, x in v.items() if not (exclude_none and x is None)}
            if isinstance(v, list):
                return [dump(x) for x in v]
            if isinstance(v, tuple):
                return [dump(x) for x in v] if mode == "json" else tuple(dump(x) for x in v)
            return v
        out = {}
        for name in self._fields():
            v = getattr(self, name)
            if exclude_none and v is None:
                continue
            out[name] = dump(v)
        return out

    def model_copy(self, *, update: dict | None = None) -> Any:
        new = object.__new__(type(self))
        for name in self._fields():
            object.__setattr__(new, name, getattr(self, name))
        for k, v in (update or {}).items():
            object.__setattr__(new, k, v)
        return new

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f'{k}={getattr(self, k)!r}' for k in self._fields())})"

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and self.model_dump() == other.model_dump()  # type: ignore[union-attr]
