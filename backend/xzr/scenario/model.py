"""Scenario schema. One shared operational structure — no per-domain schemas.

Sets, boundaries and drivers are named *opaque* selections of configurations/connections. Any
interpretation of what they are belongs to the practice layer or to the reader, never to the runtime.
"""

from __future__ import annotations

from typing import Literal

from .._compat import FORCE as _COMPAT

try:  # the iOS app has no pydantic (compiled core): a pure-Python subset stands in (see _compat/pmodel.py)
    if _COMPAT:
        raise ImportError
    from pydantic import BaseModel, ConfigDict, Field, model_validator
except ImportError:
    from .._compat.pmodel import BaseModel, ConfigDict, Field, model_validator  # type: ignore[assignment,no-redef]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeneratorSpec(_M):
    kind: Literal["latent-geometric"] = "latent-geometric"
    n: int = Field(ge=10, le=500_000)
    mean_degree: float = Field(6.0, gt=0, le=64)
    long_range: float = Field(0.08, ge=0, le=1)
    reciprocity: float = Field(0.35, ge=0, le=1)
    groups: int = Field(6, ge=1, le=64)
    geo_fraction: float = Field(0.7, ge=0, le=1)
    transform_fraction: float = Field(0.08, ge=0, le=1)
    capacity: float = Field(3.0, gt=0)
    heterogeneity: float = Field(0.35, ge=0, le=2)
    cap_ratio: float = Field(1.8, gt=1)


class NodeSpec(_M):
    theta: float = Field(1.0, gt=0)
    retention: float = Field(0.85, ge=0, le=1)
    mem_decay: float = Field(0.9, ge=0, le=1)
    mem_coupling: float = 0.0
    cap: float | None = None
    form: int = Field(0, ge=0)
    diff: float = Field(0.0, ge=0)
    geo: tuple[float, float] | None = None


class EdgeSpec(_M):
    src: int = Field(ge=0)
    dst: int = Field(ge=0)
    weight: float = Field(0.5, gt=0)
    transform: int = Field(0, ge=0)
    capacity: float = Field(3.0, gt=0)


class ExplicitSpec(_M):
    nodes: list[NodeSpec]
    edges: list[EdgeSpec]
    latent: list[tuple[float, float]] | None = None

    @model_validator(mode="after")
    def _check(self) -> ExplicitSpec:
        n = len(self.nodes)
        for e in self.edges:
            if e.src >= n or e.dst >= n:
                raise ValueError(f"edge {e.src}->{e.dst} refers to a missing configuration")
        if self.latent is not None and len(self.latent) != n:
            raise ValueError("latent must have one entry per configuration")
        return self


class SetSpec(_M):
    nodes: list[int] | None = None
    address: str | None = None
    addresses: list[str] | None = None
    edges: list[int] | None = None
    boundary_of: str | None = None
    between: tuple[str, str] | None = None
    random: dict | None = None  # {"fraction": 0.05, "seed": 3}


class DriverSpec(_M):
    set: str
    period: int = Field(ge=1)
    amount: float
    phase: int = 0


class BoundarySpec(_M):
    set: str
    permeability: float = Field(0.1, ge=0)


class Scenario(_M):
    name: str
    description: str = ""
    seed: int = 1
    params: dict[str, float] = Field(default_factory=dict)
    generator: GeneratorSpec | None = None
    explicit: ExplicitSpec | None = None
    sets: dict[str, SetSpec] = Field(default_factory=dict)
    boundaries: dict[str, BoundarySpec] = Field(default_factory=dict)
    frozen: list[str] = Field(default_factory=list)
    drivers: list[DriverSpec] = Field(default_factory=list)
    practice: dict | None = None
    interpretation_rules: list[dict] | None = None
    checkpoint_every: int = Field(50, ge=1)
    warmup: int = Field(0, ge=0)

    @model_validator(mode="after")
    def _check(self) -> Scenario:
        if (self.generator is None) == (self.explicit is None):
            raise ValueError("exactly one of 'generator' or 'explicit' is required")
        names = set(self.sets)
        for b in self.boundaries.values():
            if b.set not in names:
                raise ValueError(f"boundary refers to unknown set {b.set}")
        for d in self.drivers:
            if d.set not in names:
                raise ValueError(f"driver refers to unknown set {d.set}")
        for f in self.frozen:
            if f not in names:
                raise ValueError(f"frozen refers to unknown set {f}")
        for name, s in self.sets.items():
            for ref in [s.boundary_of, *(s.between or ())]:
                if ref is not None and ref not in names:
                    raise ValueError(f"set {name} refers to unknown set {ref}")
        return self
