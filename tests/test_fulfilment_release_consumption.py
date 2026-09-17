from pathlib import Path
import hashlib

import presence_core.fulfilment_release as release
from presence_core.customer_cases import create_or_attach_case
from presence_core.needs_you import resolve_needs_you
from presence_core.state import create_needs_you


def test_release_authority_is_consumed_once_after_delivery(tmp_path: Path):
    root = tmp_path / "state" / "presence"
    root.mkdir(parents=True)

    case = create_or_attach_case(
        root,
        conversation_id="CONV-CONSUME-TEST",
        channel="telegram",
        external_user_id="TEST-USER",
        product_id="Sophia Integrity",
        contact_email=None,
    )

    artifact_dir = (
        root
        / "customer_cases"
        / "artifacts"
        / case["case_id"]
    )
    artifact_dir.mkdir(parents=True)

    pdf = artifact_dir / "review.pdf"
    pdf.write_bytes(b"%PDF-1.4\nDIO RELEASE CONSUME TEST\n%%EOF\n")

    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()

    item = create_needs_you(
        root,
        reason="fulfilment_release_review",
        conversation_id="CONV-CONSUME-TEST",
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

    authority = release.create_release_authority(
        root,
        case_id=case["case_id"],
        job_id="JOB-CONSUME-TEST",
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

    consume = getattr(
        release,
        "consume_release_authority",
        None,
    )

    assert callable(consume), (
        "consume_release_authority is not implemented"
    )

    consumed = consume(
        root,
        authority["authority_id"],
        delivery_receipt={
            "channel": "telegram",
            "message_id": "TG-TEST-91",
            "artifact_sha256": sha,
        },
    )

    assert consumed["consumed"] is True
    assert consumed["consumed_at"]
    assert consumed["delivery_receipt"]["message_id"] == "TG-TEST-91"

    try:
        consume(
            root,
            authority["authority_id"],
            delivery_receipt={
                "channel": "telegram",
                "message_id": "TG-TEST-92",
                "artifact_sha256": sha,
            },
        )
    except ValueError as exc:
        assert "already consumed" in str(exc)
    else:
        raise AssertionError(
            "release authority was reusable after consumption"
        )
