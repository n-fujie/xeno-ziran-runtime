"""Safety and data management: the capabilities, the threat model, and the production gate.

Two judgements are kept apart. **Local verification**: what the tests in this repository exercise (each capability below names the tests). **Production readiness**: whether human measurements may be
ingested for real; it needs things this code cannot supply or verify (an external identity provider, a key-management service, an ethics approval, an independent security review, a tested backup
deletion procedure, a published trust anchor). ``production_gate`` reports which of these are missing; an attestation that is *present* is not thereby *true*: the code cannot check it.
Until the gate says production-ready, no human measurement may be ingested for real (the service refuses to store anything at all)."""

from __future__ import annotations

CAPABILITIES = (
    {"id": 1, "name": "access control and authentication", "module": "access.py", "implemented": True, "limits": "local accounts, scrypt, signed expiring tokens, roles; no external identity provider, no multi-factor authentication, no device binding"},
    {"id": 2, "name": "consent records and purposes", "module": "consent.py", "implemented": True, "limits": "append-only hash-chained log; a consent is a record of what the subject agreed, not a legal instrument; its validity under the applicable law is not assessed"},
    {"id": 3, "name": "deletion requests and verification of the result", "module": "vault.py", "implemented": True, "limits": "crypto-shredding plus removal of blobs and identity; copies outside the vault (backups, snapshots, journalling file systems) are not known unless listed"},
    {"id": 4, "name": "encryption at rest", "module": "crypto.py, vault.py", "implemented": True, "limits": "AES-256-GCM or ChaCha20-Poly1305 from the cryptography package (vetted primitives; the integration has not been reviewed by a cryptographer); passphrase-derived master key in process memory; no hardware key protection"},
    {"id": 5, "name": "integrity of the originals", "module": "vault.py, provenance.py", "implemented": True, "limits": "digests and authenticated encryption detect a change; they do not say the original was measured"},
    {"id": 6, "name": "signatures or trusted checkpoints", "module": "crypto.py, vault.py", "implemented": True, "limits": "Lamport one-time signatures chained from a trust anchor; the anchor must be published where the vault's holder cannot change it (not done here); key custody is not solved"},
    {"id": 7, "name": "separation of identity from observation data", "module": "vault.py", "implemented": True, "limits": "separation by pseudonym and by file; a pseudonym plus outside knowledge can still identify (re-identification from the data themselves is not assessed)"},
    {"id": 8, "name": "no sensitive data in logs", "module": "redact.py, access.py, vault.py", "implemented": True, "limits": "identifiers and codes only in the audit log; redaction is a safety net; logs of other components (web server, proxies) are outside this layer"},
)

THREATS = (
    {"id": "T1", "threat": "reading data or identities without authority", "defence": "token required for every operation; a permission per operation; identities readable by the steward role only; every read audited"},
    {"id": "T2", "threat": "writing data without authority or without consent", "defence": "data.write permission, an active consent for the purpose and data class, record validation before storage"},
    {"id": "T3", "threat": "tampering with stored records, skeletons or the class of a record", "defence": "authenticated encryption (a tampered blob does not decrypt), record digests, a hash-chained ledger, integrity verification"},
    {"id": "T4", "threat": "forging, replaying or extending a token", "defence": "HMAC-signed payload, expiry, revocation, constant-time comparison"},
    {"id": "T5", "threat": "guessing passwords", "defence": "scrypt hashes, a minimum length, lockout after repeated failures, equal work for unknown users"},
    {"id": "T6", "threat": "linking observation data to a person through the stores", "defence": "identity kept only in an encrypted separate store; every other store carries the pseudonym only"},
    {"id": "T7", "threat": "sensitive information leaking through logs and error messages", "defence": "the audit log and the errors carry identifiers and codes only; redaction of messages; tested with planted canaries"},
    {"id": "T8", "threat": "data remaining after a deletion request", "defence": "blob removal with overwrite, destruction of the subject's wrapped key, removal of the identity, tombstone, verification with residual risks stated"},
    {"id": "T9", "threat": "use of data beyond the consented purpose, after revocation or expiry", "defence": "the purpose and data class are checked against the consent log at the time of each use"},
    {"id": "T10", "threat": "rewriting the history (ledger, audit) without detection", "defence": "hash chains, and signed checkpoints that commit to the heads (verified against a published anchor)"},
    {"id": "T11", "threat": "opening the vault without the passphrase", "defence": "the master key is derived from the passphrase with scrypt; a check value rejects a wrong one; the key is not stored"},
)

PRODUCTION_REQUIREMENTS = (
    ("external_identity_provider", "authentication through an external identity provider (the local accounts are for verification only)"),
    ("key_management_service", "keys held in a key-management service or hardware module (the local cipher is a vetted AEAD, but its keys come from a passphrase held in process memory)"),
    ("ethics_approval_id", "an ethics approval (and any legally required review) for the specific protocol"),
    ("independent_security_review", "an independent security review or penetration test of the deployed system"),
    ("backup_deletion_procedure", "a tested procedure that removes the data and keys from every backup and snapshot"),
    ("published_trust_anchor", "the checkpoint trust anchor published outside the vault holder's control"),
)


def production_gate(attestations: dict | None = None) -> dict:
    """What stands between this code and a real human measurement. ``attestations`` maps a requirement id to a non-empty reference (an approval number, a report id); a reference's presence is not verified."""
    att = attestations or {}
    missing = [{"id": i, "needed": why} for i, why in PRODUCTION_REQUIREMENTS if not att.get(i)]
    return {"local_verification": "see the tests named in docs/TEOO.md", "production_ready": not missing, "human_measurement_ingestion_allowed": not missing, "missing": missing,
            "note": "an attestation that is present is not thereby true; this code cannot verify an approval or a review", "capabilities": list(CAPABILITIES), "threats": list(THREATS)}
