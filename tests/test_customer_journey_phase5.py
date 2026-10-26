from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from presence_core.customer_cases import load_case, update_case
from presence_core.journey_core import create_journey_case
from presence_core.needs_you import resolve_needs_you
from presence_core.state import create_needs_you
from presence_core.deliverable_release_v2 import build_deliverable_manifest, create_manifest_release_authority, deliver_manifest


def _canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _seed_review_ready_case(tmp_path: Path):
    root = tmp_path / "state" / "presence"
    root.mkdir(parents=True)
    case = create_journey_case(root, product_id="Professional Correspondence")
    artifact_dir = root / "customer_cases" / "artifacts" / case["case_id"]
    artifact_dir.mkdir(parents=True)
    pdf = artifact_dir / "letter.pdf"
    pdf.write_bytes(b"%PDF-1.4\nphase5 letter\n%%EOF\n")
    bundle = artifact_dir / "evidence.zip"
    bundle.write_bytes(b"PK\x03\x04phase5 evidence bundle")
    artifacts = [
        {"artifact_id":"ART-LETTER","kind":"document","path":str(pdf),"file_name":"letter.pdf","mime_type":"application/pdf","sha256":hashlib.sha256(pdf.read_bytes()).hexdigest(),"purpose":"primary_customer_output","customer_visibility":"VISIBLE","provenance":{"organ":"Document Studio","proof_ref":"proof:letter"},"release_conditions":["human_manifest_approval"],"source_lineage":["scope:1","fulfilment:1"],"release_state":"HELD","release_authority":False,"external_send_authority":False,"authority_created":False},
        {"artifact_id":"ART-PROOF","kind":"archive","path":str(bundle),"file_name":"evidence.zip","mime_type":"application/zip","sha256":hashlib.sha256(bundle.read_bytes()).hexdigest(),"purpose":"supporting_evidence","customer_visibility":"VISIBLE","provenance":{"organ":"Evidex","proof_ref":"proof:bundle"},"release_conditions":["human_manifest_approval"],"source_lineage":["scope:1","fulfilment:1"],"release_state":"HELD","release_authority":False,"external_send_authority":False,"authority_created":False},
    ]
    result = {"schema":"dio.fulfilment_result.v1","case_id":case["case_id"],"journey_product_id":case["product_id"],"fulfilment_request_sha256":"a"*64,"execution_profile_sha256":"b"*64,"adapter_id":"document-pack-adapter","adapter_version":"1","status":"COMPLETED","artifacts":artifacts,"evidence_refs":["proof:letter","proof:bundle"],"organ_steps":["Document Studio","Evidex"],"release_authority_created":False,"external_send_authority":False,"authority_created":False}
    result["fulfilment_result_sha256"] = _canonical_hash(result)
    case = update_case(root, case, stage="REVIEW_READY", patch={"fulfilment":{"state":"review_ready","result":result,"release_authority":False,"external_send_authority":False},"authority_created":False}, evidence_ref=f"fulfilment-result:{result['fulfilment_result_sha256']}")
    return root, case, pdf, bundle, result


def _approve_manifest(root: Path, case: dict, manifest: dict):
    item = create_needs_you(root, reason="fulfilment_release_review", conversation_id=f"phase5:{case['case_id']}", product=case["product_id"], summary=f"Approve exact manifest SHA-256 {manifest['manifest_sha256']}")
    return resolve_needs_you(root, item["needs_you_id"], decision="APPROVE", resolved_by="human:test-operator", evidence_ref=f"manifest-sha256:{manifest['manifest_sha256']}")


def test_manifest_supports_multiple_formats_and_creates_no_authority(tmp_path: Path):
    root, case, _, _, result = _seed_review_ready_case(tmp_path)
    manifest = build_deliverable_manifest(root, case["case_id"])
    assert manifest["schema"] == "dio.deliverable_manifest.v2"
    assert manifest["fulfilment_result_sha256"] == result["fulfilment_result_sha256"]
    assert [a["mime_type"] for a in manifest["artifacts"]] == ["application/pdf", "application/zip"]
    assert all(a["release_state"] == "HELD" for a in manifest["artifacts"])
    assert manifest["release_authority_created"] is False
    assert manifest["external_send_authority"] is False
    assert manifest["authority_created"] is False
    basis = dict(manifest); expected = basis.pop("manifest_sha256")
    assert _canonical_hash(basis) == expected
    stored = load_case(root, case["case_id"])
    assert stored["stage"] == "REVIEW_READY"
    assert stored["fulfilment"]["deliverable_manifest"]["manifest_sha256"] == expected


def test_manifest_refuses_artifact_whose_bytes_do_not_match_phase4_sha(tmp_path: Path):
    root, case, pdf, _, _ = _seed_review_ready_case(tmp_path)
    pdf.write_bytes(b"changed before manifest")
    with pytest.raises(ValueError, match="artifact SHA-256 mismatch"):
        build_deliverable_manifest(root, case["case_id"])


def test_release_authority_requires_exact_manifest_bound_human_approval(tmp_path: Path):
    root, case, _, _, _ = _seed_review_ready_case(tmp_path)
    manifest = build_deliverable_manifest(root, case["case_id"])
    item = create_needs_you(root, reason="fulfilment_release_review", conversation_id=f"phase5:{case['case_id']}", product=case["product_id"], summary="Approve deliverables")
    bad = resolve_needs_you(root, item["needs_you_id"], decision="APPROVE", resolved_by="human:test-operator", evidence_ref="reviewed visually")
    with pytest.raises(ValueError, match="manifest SHA-256"):
        create_manifest_release_authority(root, case_id=case["case_id"], needs_you_id=bad["needs_you_id"], delivery_channels=["telegram"])
    assert load_case(root, case["case_id"])["stage"] == "REVIEW_READY"


def test_exact_manifest_approval_creates_channel_scoped_one_use_authority(tmp_path: Path):
    root, case, _, _, _ = _seed_review_ready_case(tmp_path)
    manifest = build_deliverable_manifest(root, case["case_id"])
    approval = _approve_manifest(root, case, manifest)
    authority = create_manifest_release_authority(root, case_id=case["case_id"], needs_you_id=approval["needs_you_id"], delivery_channels=["telegram", "email"])
    assert authority["schema"] == "dio.release_authority.v2"
    assert authority["manifest_sha256"] == manifest["manifest_sha256"]
    assert authority["scope"]["delivery_channels"] == ["email", "telegram"]
    assert authority["scope"]["one_use"] is True
    assert authority["consumed"] is False
    assert load_case(root, case["case_id"])["stage"] == "RELEASE_APPROVAL"


def test_artifact_change_after_approval_invalidates_release_before_transport(tmp_path: Path):
    root, case, pdf, _, _ = _seed_review_ready_case(tmp_path)
    manifest = build_deliverable_manifest(root, case["case_id"])
    approval = _approve_manifest(root, case, manifest)
    authority = create_manifest_release_authority(root, case_id=case["case_id"], needs_you_id=approval["needs_you_id"], delivery_channels=["telegram"])
    pdf.write_bytes(b"mutated after human approval")
    called = False
    def transport(_package):
        nonlocal called; called = True
        return {"sent": True, "provider_receipt": {"message_id": "SHOULD-NOT-SEND"}}
    with pytest.raises(ValueError, match="changed after approval"):
        deliver_manifest(root, authority["authority_id"], channel="telegram", destination="user:123", transport=transport)
    assert called is False


def test_failed_transport_does_not_consume_authority_or_mark_delivered(tmp_path: Path):
    root, case, _, _, _ = _seed_review_ready_case(tmp_path)
    manifest = build_deliverable_manifest(root, case["case_id"])
    approval = _approve_manifest(root, case, manifest)
    authority = create_manifest_release_authority(root, case_id=case["case_id"], needs_you_id=approval["needs_you_id"], delivery_channels=["telegram"])
    result = deliver_manifest(root, authority["authority_id"], channel="telegram", destination="user:123", transport=lambda package:{"sent":False,"error":"telegram unavailable","provider_receipt":{"attempt_id":"ATT-1"}})
    assert result["delivered"] is False
    assert result["delivery_receipt"] is None
    stored = load_case(root, case["case_id"])
    assert stored["stage"] == "RELEASE_APPROVAL"
    assert stored["fulfilment"]["last_delivery_attempt"]["sent"] is False


def test_successful_multi_artifact_delivery_records_exact_receipt_and_refuses_replay(tmp_path: Path):
    root, case, _, _, _ = _seed_review_ready_case(tmp_path)
    manifest = build_deliverable_manifest(root, case["case_id"])
    approval = _approve_manifest(root, case, manifest)
    authority = create_manifest_release_authority(root, case_id=case["case_id"], needs_you_id=approval["needs_you_id"], delivery_channels=["telegram"])
    observed = {}
    def transport(package):
        observed.update(package)
        return {"sent":True,"provider_receipt":{"message_id":"TG-500","attachment_ids":["TG-A","TG-B"]}}
    result = deliver_manifest(root, authority["authority_id"], channel="telegram", destination="user:123", transport=transport)
    receipt = result["delivery_receipt"]
    assert result["delivered"] is True
    assert receipt["schema"] == "dio.delivery_receipt.v2"
    assert receipt["manifest_sha256"] == manifest["manifest_sha256"]
    assert [(a["artifact_id"],a["sha256"]) for a in receipt["artifacts"]] == [(a["artifact_id"],a["sha256"]) for a in manifest["artifacts"]]
    assert len(observed["artifacts"]) == 2
    assert load_case(root, case["case_id"])["stage"] == "DELIVERED"
    with pytest.raises(ValueError, match="already consumed"):
        deliver_manifest(root, authority["authority_id"], channel="telegram", destination="user:123", transport=transport)


def test_release_authority_refuses_channel_outside_approved_scope(tmp_path: Path):
    root, case, _, _, _ = _seed_review_ready_case(tmp_path)
    manifest = build_deliverable_manifest(root, case["case_id"])
    approval = _approve_manifest(root, case, manifest)
    authority = create_manifest_release_authority(root, case_id=case["case_id"], needs_you_id=approval["needs_you_id"], delivery_channels=["email"])
    with pytest.raises(ValueError, match="delivery channel is not authorized"):
        deliver_manifest(root, authority["authority_id"], channel="telegram", destination="user:123", transport=lambda package:{"sent":True,"provider_receipt":{"message_id":"NO"}})
