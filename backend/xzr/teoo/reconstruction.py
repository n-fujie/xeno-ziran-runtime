"""Reconstruction Records: estimates and reconstructed body states, with their inputs, method, time, uncertainty and interpolation.

A reconstruction is a *derived* record (``derived_from`` names every input, id and digest), always RECONSTRUCTED_ESTIMATE, kind ESTIMATE or RECONSTRUCTION; it can never be
MEASURED. Its time is a Reconstruction Time (the time the state is *about*) with its uncertainty; if its inputs are not synchronised the uncertainty is None and the record
says so. Interpolation is recorded (method and interval). The relation claims of the body graph follow the same rule: an association is never recorded as a cause here.
"""

from __future__ import annotations

from .provenance import Kind, Provenance, derive
from .timebase import Interpolation, TimeKind


def make_reconstruction(inputs: list[dict], *, method: str, creator: dict, reconstruction_time_s: float, time_uncertainty_s: float | None, value: dict, uncertainty: dict | None = None,
                        assumptions: list[str] | None = None, interpolation: list[Interpolation] | None = None, kind: Kind = Kind.RECONSTRUCTION, synchronised_inputs: bool | None = None,
                        created_at: str | None = None) -> dict:
    if not method:
        raise ValueError("a reconstruction names its method")
    interp = [i.to_dict() for i in (interpolation or [])]
    payload = {"reconstruction": {"method": method, "assumptions": list(assumptions or []), "value": value, "uncertainty": uncertainty, "interpolation": interp,
                                  "time": {"kind": TimeKind.RECONSTRUCTION.value, "t_s": reconstruction_time_s, "uncertainty_s": time_uncertainty_s,
                                           "inputs_synchronised": synchronised_inputs, "note": "the time the state is about; unsynchronised inputs leave the uncertainty unknown (None), not zero"}},
               "inputs": [{"record_id": r["record_id"], "provenance": r["provenance"], "kind": r["kind"]} for r in inputs]}
    return derive(inputs, payload=payload, provenance=Provenance.RECONSTRUCTED_ESTIMATE, kind=kind, creator=creator, source={"kind": "computation", "description": f"reconstruction by {method}"},
                  transformations=[{"method": method, "preserves_provenance": False, "interpolated": bool(interp)}], created_at=created_at)


def edge_claim(relation: dict) -> str:
    """What a relation of the body graph is allowed to be called: 'structural', 'association' or 'causal' (the last only with support)."""
    return relation["claim"]
