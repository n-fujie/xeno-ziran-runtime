"""Media records: photographs and other files. A photograph is a MEASURED record whose source is a device that captured it; a generated or drawn image is SYNTHETIC or CONCEPTUAL and can never be presented as one.

The registry does not look at pixels: it cannot tell a photograph from a render. It refuses to register an image as a photograph unless the declaration names a capture device and time (a declaration is not a proof), and
``presentation_label`` is the only text a figure may use for an image: it is derived from the sealed class."""

from __future__ import annotations

from .provenance import Kind, Provenance, ProvenanceError, seal
from .schema import Issue

MEDIA_TYPES = ("image/png", "image/jpeg", "video/mp4", "image/svg+xml")


def register_media(data: bytes, media_type: str, *, provenance: Provenance | str, source: dict, creator: dict, original_name: str = "", created_at: str | None = None) -> dict:
    if media_type not in MEDIA_TYPES:
        raise ProvenanceError([Issue("media_type", "MEDIA_TYPE_UNSUPPORTED", f"media type must be one of {MEDIA_TYPES}")])
    prov = Provenance(provenance)
    if prov is Provenance.MEASURED:
        need = [k for k in ("device", "captured_at", "declared_by") if not source.get(k)]
        if need or source.get("kind") not in ("device", "instrument"):
            raise ProvenanceError([Issue("source", "NOT_A_PHOTOGRAPH", f"a photograph (MEASURED) declares source.kind 'device' or 'instrument' and {['device', 'captured_at', 'declared_by']}; missing: {need}; a generated image is SYNTHETIC")])
    payload = {"media": {"media_type": media_type, "bytes": len(data), "original_name": original_name, "is_photograph_declared": prov is Provenance.MEASURED}}
    return seal(payload, provenance=prov, kind={Provenance.MEASURED: Kind.OBSERVATION, Provenance.SYNTHETIC: Kind.OBSERVATION, Provenance.RECONSTRUCTED_ESTIMATE: Kind.ESTIMATE}.get(prov, Kind.REFERENCE_STATE), creator=creator, source=source, raw_bytes=data, raw_media_type=media_type, created_at=created_at)


def presentation_label(rec: dict) -> str:
    m = rec["payload"]["media"]
    if rec["provenance"] == "MEASURED":
        return "photograph / recording (declared by its source; not verified)"
    if rec["provenance"] == "SYNTHETIC":
        return "SYNTHETIC rendering — NOT a photograph"
    if rec["provenance"] == "RECONSTRUCTED_ESTIMATE":
        return "reconstruction — NOT a photograph"
    return f"conceptual illustration — NOT a photograph ({m['media_type']})"


def is_photograph(rec: dict) -> bool:
    return rec["provenance"] == "MEASURED" and rec["payload"].get("media", {}).get("is_photograph_declared") is True
