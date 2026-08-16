from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.attachment_intake import AttachmentIntakeError, quarantine_attachments
from products.contractproof.runner import run_contractproof
from products.evidence_reconciliation import reconcile_evidence
from products.paid_reference import _contract_source, run_paid_reference_journey, validate_intake


SCHEMA = "dio.phase11_1.attachment_delivery_journey.v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_attachment_delivery_journey(payload: dict[str, Any], *, output_dir: Path, root: Path) -> dict[str, Any]:
    channel = str(payload.get("channel") or "web").lower()
    if channel not in {"web", "outlook"}:
        raise AttachmentIntakeError("channel must be web or outlook")
    seed = {key: payload.get(key) for key in ("email", "review_title", "message")}
    seed["attachments"] = [{"filename": row.get("filename"), "role": row.get("role"), "sha256": hashlib.sha256(__import__("base64").b64decode(row.get("content_base64") or "")).hexdigest()} for row in payload.get("attachments") or []]
    intake_id = "VIN-" + hashlib.sha256(_canonical(seed).encode()).hexdigest()[:16].upper()
    manifest = quarantine_attachments(list(payload.get("attachments") or []), output_dir=output_dir, intake_id=intake_id)
    contracts = [row for row in manifest["attachments"] if row["role"] == "authoritative_contract"]
    if len(contracts) != 1 or contracts[0]["extraction_state"] != "EXTRACTED" or not contracts[0]["extracted_text"].strip():
        raise AttachmentIntakeError("exactly one extractable authoritative_contract attachment is required")
    paid_payload = dict(payload)
    paid_payload["contract_text"] = contracts[0]["extracted_text"]
    paid_payload.pop("attachments", None)
    intake = validate_intake(paid_payload)
    journey = run_paid_reference_journey(paid_payload, output_dir=output_dir, root=root)
    source = _contract_source(intake, journey["journey_id"])
    reconciliation = reconcile_evidence(
        manifest, source, now="2026-08-16T12:00:00+00:00",
        output_path=output_dir / "fulfilment" / "proof" / "EVIDENCE_RECONCILIATION.json",
    )
    evidence = []
    by_id = {row["attachment_id"]: row for row in manifest["attachments"]}
    for mapping in reconciliation["mappings"]:
        if not mapping["target_locators"]:
            continue
        row = by_id[mapping["attachment_id"]]
        evidence.append({
            "target_locators": mapping["target_locators"], "evidence_kind": "attachment", "source_ref": row["source_ref"], "sha256": row["sha256"],
            "authority_grade": "source_backed", "trust_state": "captured_untrusted", "freshness_state": mapping["freshness_state"], "relation": mapping["relation"],
        })
    proof = run_contractproof(source, evidence, output_dir=output_dir / "fulfilment" / "proof", operator_id="human.phase11_1.vesper_intake", now="2026-08-16T12:00:00+00:00", job_id=journey["journey_id"])
    vesper = {
        "schema": "dio.vesper.intake_receipt.v1", "identity": "Vesper, DIO Presence Core", "intake_id": intake_id, "channel": channel,
        "case_id": proof["case"]["case_id"], "thread_ref": payload.get("thread_ref"), "attachment_manifest_ref": f"vesper://{intake_id}/ATTACHMENT_INTAKE.json",
        "public_status": "verified_binding_only", "automatic_external_actions": False, "external_reply": "REFUSE", "human_gate": "NEEDS_YOU",
    }
    _write(output_dir / "state" / "vesper" / "intakes" / intake_id / "VESPER_INTAKE_RECEIPT.json", vesper)
    artifacts = []
    for name in ("EVIDENCE_PACK.pdf", "EVIDENCE_PACK.docx", "EVIDENCE_PACK.html", "PROOF_MANIFEST.json", "EVIDENCE_RECONCILIATION.json", "EVIDENCE_RECONCILIATION.html"):
        path = output_dir / "fulfilment" / "proof" / name
        artifacts.append({"filename": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "path": str(path)})
    draft = {
        "schema": "dio.outlook_smart_bot.delivery_draft.v1", "draft_id": "ODR-" + intake_id[4:], "channel": "outlook",
        "to": intake["email"], "subject": f"Draft: {intake['review_title']}", "body": "Your ContractProof review pack is prepared for human approval.",
        "attachments": artifacts, "state": "DRAFT_ONLY", "human_approval": "NEEDS_YOU", "send_authorized": False, "sent": False,
        "message_id": None, "external_effects": False,
    }
    _write(output_dir / "state" / "outlook_smart_bot" / "drafts" / f"{draft['draft_id']}.json", draft)
    result = {
        "schema": SCHEMA, "intake_id": intake_id, "journey_id": journey["journey_id"], "case_id": proof["case"]["case_id"],
        "channel": channel, "attachment_count": len(manifest["attachments"]), "evidence_attachment_count": len(evidence),
        "reconciled_attachment_count": len(reconciliation["mappings"]), "unresolved_attachment_count": len(reconciliation["unresolved_attachment_ids"]),
        "evidence_fanout_guard": reconciliation["fanout_guard"],
        "source_binding": "PASS", "proof_integrity": "PASS", "vesper_intake": "PASS", "outlook_draft": "PASS",
        "attachment_policy": "quarantine_only", "external_delivery": "REFUSE", "human_release": "NEEDS_YOU", "sent": False,
        "proof_output_dir": "fulfilment/proof", "outlook_draft_ref": f"state/outlook_smart_bot/drafts/{draft['draft_id']}.json",
    }
    result["fingerprint"] = "sha256:" + hashlib.sha256(_canonical(result).encode()).hexdigest()
    _write(output_dir / "state" / "phase11_1" / "PHASE11_1_JOURNEY.json", result)
    return result
