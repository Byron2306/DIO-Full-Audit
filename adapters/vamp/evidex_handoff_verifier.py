"""Fail-closed verification of VAMP-to-Evidex snapshot handoffs."""

import hashlib
import hmac
import json
from pathlib import Path


class HandoffVerificationError(ValueError):
    pass


def verify_handoff(snapshot_path: Path, handoff_path: Path) -> dict:
    snapshot_bytes = Path(snapshot_path).read_bytes()
    handoff_bytes = Path(handoff_path).read_bytes()

    snapshot = json.loads(snapshot_bytes)
    handoff = json.loads(handoff_bytes)

    if snapshot.get("schema") != "dio.vamp_snapshot.v1":
        raise HandoffVerificationError("REFUSE: unknown snapshot schema")

    if handoff.get("schema") != "dio.vamp_evidex_handoff.v1":
        raise HandoffVerificationError("REFUSE: unknown handoff schema")

    actual_digest = hashlib.sha256(snapshot_bytes).hexdigest()
    declared_digest = handoff.get("snapshot_sha256")

    if not isinstance(declared_digest, str) or not hmac.compare_digest(
        actual_digest, declared_digest
    ):
        raise HandoffVerificationError("REFUSE: snapshot digest mismatch")

    from adapters.vamp.snapshot_pipeline import _build_vamp_evidex_handoff

    expected = _build_vamp_evidex_handoff(snapshot)
    expected["snapshot_sha256"] = actual_digest

    if handoff != expected:
        raise HandoffVerificationError(
            "REFUSE: handoff content differs from originating snapshot"
        )

    if handoff.get("delivery_authorized") is not False:
        raise HandoffVerificationError("REFUSE: delivery authority")

    if handoff.get("human_review_required") is not True:
        raise HandoffVerificationError("REFUSE: human review gate")

    return {
        "schema": "dio.vamp_evidex_handoff_verification.v1",
        "status": "PASS",
        "job_id": snapshot["job_id"],
        "snapshot_sha256": actual_digest,
        "source_mappings": len(handoff["source_mappings"]),
        "authority_scope": "vamp_calibration_only",
        "customer_claim_independently_verified": False,
        "delivery_authorized": False,
    }
