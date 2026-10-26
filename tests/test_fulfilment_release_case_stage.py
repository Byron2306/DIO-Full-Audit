from pathlib import Path
import hashlib

from presence_core.customer_cases import (
    create_or_attach_case,
    load_case,
    update_case,
)
from presence_core.fulfilment_release import (
    create_release_authority,
)
from presence_core.needs_you import resolve_needs_you
from presence_core.state import create_needs_you


def test_release_authority_advances_case_to_release_approval(
    tmp_path: Path,
):
    root = tmp_path / "state" / "presence"
    root.mkdir(parents=True)

    case = create_or_attach_case(
        root,
        conversation_id="CONV-RELEASE-STAGE",
        channel="telegram",
        external_user_id="TEST-USER",
        product_id="Sophia Integrity",
        contact_email=None,
    )

    case = update_case(
        root,
        case,
        stage="REVIEW_READY",
    )

    artifact_dir = (
        root
        / "customer_cases"
        / "artifacts"
        / case["case_id"]
    )
    artifact_dir.mkdir(parents=True)

    pdf = artifact_dir / "review.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\nDIO RELEASE STAGE TEST\n%%EOF\n"
    )

    sha = hashlib.sha256(
        pdf.read_bytes()
    ).hexdigest()

    item = create_needs_you(
        root,
        reason="fulfilment_release_review",
        conversation_id="CONV-RELEASE-STAGE",
        product="Sophia Integrity",
        summary=f"Approve exact artifact SHA-256 {sha}",
    )

    approval = resolve_needs_you(
        root,
        item["needs_you_id"],
        decision="APPROVE",
        resolved_by="human:test-operator",
        evidence_ref=f"sha256:{sha}",
    )

    authority = create_release_authority(
        root,
        case_id=case["case_id"],
        job_id="JOB-RELEASE-STAGE",
        needs_you_id=approval["needs_you_id"],
        artifact={
            "kind": "document",
            "path": str(pdf),
            "file_name": "review.pdf",
            "mime_type": "application/pdf",
            "sha256": sha,
            "release_state": "HELD",
        },
    )

    stored = load_case(
        root,
        case["case_id"],
    )

    assert stored is not None
    assert stored["stage"] == "RELEASE_APPROVAL"
    assert (
        stored["fulfilment"]["release_authority_id"]
        == authority["authority_id"]
    )
    assert stored["fulfilment"]["release_authority"] is True
    assert stored["fulfilment"]["external_send_authority"] is True
