from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from products.dossierops_native_pilot import (
    _record_state,
    build_open_questions,
    inventory_customer_sources,
    run_dossierops_native_pilot,
)
from products.dossierops_native_quality import audit_dossierops


NOW = "2026-08-22T06:00:00+00:00"


def _write_packet(root: Path) -> dict:
    packet_dir = root / "CUSTOMER_PACKET"
    sources = packet_dir / "SOURCES"
    sources.mkdir(parents=True)
    (sources / "01_customer_context.md").write_text(
        "# Customer context\n\nOrganisation: Stonebridge Professional Services\nBuyer: Legal operations manager\nMixed case folder for counsel review.\n",
        encoding="utf-8",
    )
    with (sources / "02_evidence_register.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record_id", "customer_supplied_record"])
        writer.writerow(["R-01", "Signed agreement is dated 3 February 2026."])
        writer.writerow(["R-02", "Amendment draft dated 18 April 2026 is unsigned."])
        writer.writerow(["R-03", "Payment spreadsheet lists R426,000 outstanding."])
        writer.writerow(["R-04", "An email says the amendment was agreed in principle but no signed amendment is supplied."])
    (sources / "03_exception_note.md").write_text(
        "# Exception / ambiguity supplied with the job\n\nDossierOps must distinguish signed records from drafts and cannot give legal conclusions about enforceability.\n",
        encoding="utf-8",
    )
    (sources / "agreement_extract.md").write_text(
        "# Signed agreement extract supplied by customer\n\nAgreement date: 3 February 2026. The signed agreement is authoritative only for the terms contained in the signed record. A later amendment dated 18 April 2026 is supplied as an unsigned draft.\n",
        encoding="utf-8",
    )
    with (sources / "case_file_index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item", "record_type", "state"])
        writer.writerow(["Agreement", "contract", "signed"])
        writer.writerow(["Amendment 18 April", "amendment", "unsigned_draft"])
        writer.writerow(["Payment schedule", "spreadsheet", "customer_supplied"])
        writer.writerow(["Agreement-in-principle email", "correspondence", "customer_supplied"])
    return {
        "packet_dir": packet_dir,
        "packet_fingerprint": "sha256:test-dossierops-packet",
        "intake": {
            "request": "Turn this mixed case folder into an indexed dossier with provenance, document classes, gaps and an open-question register for counsel review.",
            "customer": {
                "organisation": "Stonebridge Professional Services",
                "buyer_role": "Legal operations manager",
            },
        },
    }


def _noise(size: int, seed: str) -> bytes:
    chunks = []
    i = 0
    while sum(len(chunk) for chunk in chunks) < size:
        chunks.append(hashlib.sha256(f"{seed}:{i}".encode()).digest())
        i += 1
    return b"".join(chunks)[:size]


def _fake_document_studio(request: dict, request_path: Path, output_root: Path) -> Path:
    job = output_root / "PRO-DOSSIEROPS-PILOT-DOC"
    formatted = job / "formatted" / "source"
    formatted.mkdir(parents=True)
    (formatted / "DOSSIER_REVIEW.docx").write_bytes(_noise(26000, "docx"))
    (formatted / "DOSSIER_REVIEW.pdf").write_bytes(_noise(26000, "pdf"))
    (formatted / "DOSSIER_REVIEW.html").write_bytes(_noise(26000, "html"))
    receipt = {
        "schema": "dio.document_studio.receipt.v1",
        "job_id": "PRO-DOSSIEROPS-PILOT-DOC",
        "status": "human_review_required",
        "release": {
            "delivery_released": False,
            "human_approval_required": True,
            "release_readiness": "blocked_pending_human_approval",
        },
    }
    (job / "DOCUMENT_STUDIO_RECEIPT.json").write_text(json.dumps(receipt), encoding="utf-8")
    return job


def test_record_state_preserves_mixed_signed_and_unsigned_source() -> None:
    text = "The signed agreement is dated 3 February 2026. A later amendment is an unsigned draft."
    assert _record_state(Path("agreement_extract.md"), text) == "mixed_state_source_preserved"


def test_open_questions_preserve_stonebridge_ambiguities(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path)
    inventory, texts = inventory_customer_sources(packet)
    agreement = next(row for row in inventory if row["filename"] == "agreement_extract.md")
    assert agreement["record_state"] == "mixed_state_source_preserved"
    assert agreement["explicit_dates"] == ["3 February 2026", "18 April 2026"]

    from products.dossierops_native_pilot import _cross_reference

    cross_reference = _cross_reference(packet, inventory, texts)
    questions = build_open_questions(packet, inventory, cross_reference)
    blob = json.dumps(questions, ensure_ascii=False).casefold()
    assert "signed amendment" in blob
    assert "agreement-in-principle" in blob
    assert "r426,000" in blob
    assert all(row["state"] == "OPEN_HUMAN_REVIEW" for row in questions)


def test_native_pilot_builds_substantive_controlled_pack_without_promoting_identity(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path)
    result = run_dossierops_native_pilot(
        packet,
        tmp_path / "EXECUTION",
        operator_id="test.dossierops.native",
        now=NOW,
        document_studio_runner=_fake_document_studio,
    )
    binding = result["receipt"]
    assert binding["native_engine"] == "products.dossierops_native_pilot.run_dossierops_native_pilot"
    assert binding["signed_and_unsigned_states_kept_distinct"] is True
    assert binding["unsigned_amendment_promoted_to_executed"] is False
    assert binding["identity_state"] == "controlled_pilot_unpromoted"
    assert binding["canonical_portfolio_registration"] is False
    assert binding["document_studio_execution_performed"] is True
    assert len(binding["document_studio_rendered_artifacts"]) == 3
    assert binding["open_question_count"] >= 3
    assert binding["review_brief_words"] >= 700
    assert Path(binding["controlled_dossier_bundle"]).is_file()

    quality = audit_dossierops(Path(result["binding_path"]))
    assert quality["artifact_quality_verified"] is True, [
        name for name, passed in quality["checks"].items() if not passed
    ]
    assert quality["site_promotion_allowed"] is True
    assert quality["identity_state"] == "controlled_pilot_unpromoted"
    assert quality["canonical_portfolio_registration"] is False


def test_quality_refuses_authority_drift(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path)
    result = run_dossierops_native_pilot(
        packet,
        tmp_path / "EXECUTION",
        operator_id="test.dossierops.native",
        now=NOW,
        document_studio_runner=_fake_document_studio,
    )
    binding_path = Path(result["binding_path"])
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["legal_sufficiency_determined"] = True
    binding_path.write_text(json.dumps(binding, indent=2), encoding="utf-8")

    quality = audit_dossierops(binding_path)
    assert quality["artifact_quality_verified"] is False
    assert quality["checks"]["forbidden_legal_sufficiency_determined_false"] is False
