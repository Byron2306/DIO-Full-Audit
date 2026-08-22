from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from products.native_product_quality import (
    ACCEPTANCE_TOKEN,
    REFUSE_TOKEN,
    SCHEMA,
    _artifact_row,
    _base_receipt,
    _extract_text,
    _load_json,
    _signal_groups,
    _word_count,
    load_contract,
)


def audit_dossierops(native_binding_path: Path, *, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    spec = dict((contract.get("products") or {}).get("DossierOps") or {})
    if not spec:
        raise RuntimeError("DossierOps native quality contract missing")

    native_binding_path = Path(native_binding_path).expanduser().resolve()
    binding = _load_json(native_binding_path)
    source_manifest_path = Path(str(binding.get("source_manifest") or ""))
    review_brief_path = Path(str(binding.get("review_brief") or ""))
    open_questions_path = Path(str(binding.get("open_question_register") or ""))
    doc_receipt_path = Path(str(binding.get("document_studio_receipt") or ""))
    bundle_path = Path(str(binding.get("controlled_dossier_bundle") or ""))
    status_matrix_path = Path(str(binding.get("record_status_matrix") or ""))
    chronology_path = Path(str(binding.get("chronology") or ""))
    cross_path = Path(str(binding.get("claim_record_cross_reference") or ""))

    manifest = _load_json(source_manifest_path) if source_manifest_path.is_file() else {}
    sources = [dict(row) for row in manifest.get("sources") or [] if isinstance(row, dict)]
    questions_payload = _load_json(open_questions_path) if open_questions_path.is_file() else {}
    questions = [dict(row) for row in questions_payload.get("questions") or [] if isinstance(row, dict)]
    doc_receipt = _load_json(doc_receipt_path) if doc_receipt_path.is_file() else {}
    review_text = _extract_text(review_brief_path)
    rendered = [Path(str(path)) for path in binding.get("document_studio_rendered_artifacts") or []]
    rendered_existing = [path for path in rendered if path.is_file()]
    native_rows = [dict(row) for row in binding.get("native_output_files") or [] if isinstance(row, dict)]
    native_total_bytes = sum(int(row.get("bytes") or 0) for row in native_rows)

    checks: dict[str, bool] = {
        "native_binding_schema": binding.get("schema") == spec.get("native_binding_schema"),
        "native_engine_identity": binding.get("native_engine") == spec.get("native_engine"),
        "surrogate_fallback_forbidden": binding.get("surrogate_fallback_allowed") is False,
        "surrogate_fallback_unused": binding.get("surrogate_fallback_used") is False,
        "source_manifest_present": source_manifest_path.is_file(),
        "minimum_customer_sources": len(sources) >= int(spec.get("minimum_customer_source_count") or 1),
        "source_hashes_present": bool(sources) and all(str(row.get("sha256") or "") for row in sources),
        "source_custody_preserved": bool(sources) and all(row.get("custody") == "vesper_quarantined_customer_bytes" for row in sources),
        "review_brief_present": review_brief_path.is_file(),
        "review_brief_minimum_words": _word_count(review_text) >= int(spec.get("minimum_review_brief_words") or 1),
        "open_question_register_present": open_questions_path.is_file(),
        "minimum_open_questions": len(questions) >= int(spec.get("minimum_open_question_count") or 1),
        "record_status_matrix_present": status_matrix_path.is_file(),
        "chronology_present": chronology_path.is_file(),
        "claim_record_cross_reference_present": cross_path.is_file(),
        "document_studio_receipt_present": doc_receipt_path.is_file(),
        "document_studio_receipt_schema": doc_receipt.get("schema") == "dio.document_studio.receipt.v1",
        "document_studio_human_review_state": doc_receipt.get("status") == "human_review_required",
        "document_studio_not_released": (doc_receipt.get("release") or {}).get("delivery_released") is False,
        "document_studio_execution_performed": binding.get("document_studio_execution_performed") is True,
        "minimum_document_studio_rendered_artifacts": len(rendered_existing) >= int(spec.get("minimum_document_studio_rendered_artifacts") or 1),
        "controlled_dossier_bundle_present": bundle_path.is_file(),
        "controlled_dossier_bundle_minimum_bytes": bundle_path.is_file() and bundle_path.stat().st_size >= int(spec.get("minimum_bundle_bytes") or 1),
        "minimum_native_output_total_bytes": native_total_bytes >= int(spec.get("minimum_native_output_total_bytes") or 1),
        "identity_remains_unpromoted": binding.get("identity_state") == spec.get("identity_state_required"),
        "canonical_registration_not_claimed": binding.get("canonical_portfolio_registration") is spec.get("canonical_portfolio_registration_required"),
        "human_review_gate_preserved": binding.get("human_review_gate") == "NEEDS_YOU",
        "external_release_refused": binding.get("external_release_gate") == "REFUSE",
        "authority_not_created": binding.get("authority_created") is False,
        "external_effects_absent": binding.get("external_effects") is False,
    }

    if spec.get("signed_unsigned_distinction_required") is True:
        lower = review_text.casefold()
        checks["signed_unsigned_distinction_preserved"] = (
            "signed agreement" in lower
            and ("unsigned amendment" in lower or "unsigned draft" in lower)
            and "agreed in principle" in lower
        )

    for field in spec.get("forbidden_authority_outcomes") or []:
        checks[f"forbidden_{field}_false"] = binding.get(str(field)) is False

    signals = _signal_groups(review_text, [list(group) for group in spec.get("review_brief_signal_groups") or []])
    checks["review_brief_domain_signals"] = all(signals.values())

    bundle_members: list[str] = []
    if bundle_path.is_file():
        try:
            with zipfile.ZipFile(bundle_path) as zf:
                bundle_members = zf.namelist()
        except zipfile.BadZipFile:
            bundle_members = []
    checks["bundle_contains_multiple_records"] = len(bundle_members) >= len(sources) + 6
    checks["bundle_contains_index"] = any(name.endswith("DOSSIER_INDEX.json") for name in bundle_members)
    checks["bundle_contains_review_brief"] = any("DOSSIER-REVIEW-BRIEF" in name.upper() or "COUNSEL_REVIEW_BRIEF" in name.upper() for name in bundle_members)

    artifacts = {
        "source_manifest": _artifact_row(source_manifest_path, _extract_text(source_manifest_path), role="source_manifest", showcase=False),
        "review_brief": _artifact_row(review_brief_path, review_text, role="counsel_review_brief"),
        "open_question_register": _artifact_row(open_questions_path, _extract_text(open_questions_path), role="open_question_register"),
        "record_status_matrix": _artifact_row(status_matrix_path, _extract_text(status_matrix_path), role="record_status_matrix"),
        "chronology": _artifact_row(chronology_path, _extract_text(chronology_path), role="chronology"),
        "claim_record_cross_reference": _artifact_row(cross_path, _extract_text(cross_path), role="claim_record_cross_reference"),
        "document_studio_receipt": _artifact_row(doc_receipt_path, _extract_text(doc_receipt_path), role="document_studio_receipt", showcase=False),
        "controlled_dossier_bundle": _artifact_row(bundle_path, role="controlled_dossier_bundle"),
    }
    for index, path in enumerate(rendered_existing, 1):
        artifacts[f"document_studio_render_{index:02d}"] = _artifact_row(path, _extract_text(path), role="document_studio_review_artifact")

    return _base_receipt(
        product="DossierOps",
        spec=spec,
        source_path=native_binding_path,
        source_payload=binding,
        checks=checks,
        artifacts=artifacts,
        extra={
            "customer_source_count": len(sources),
            "open_question_count": len(questions),
            "review_brief_words": _word_count(review_text),
            "document_studio_rendered_artifact_count": len(rendered_existing),
            "native_output_total_bytes": native_total_bytes,
            "bundle_member_count": len(bundle_members),
            "signal_evidence": {"review_brief": signals},
            "identity_state": binding.get("identity_state"),
            "canonical_portfolio_registration": binding.get("canonical_portfolio_registration"),
        },
        contract=contract,
    )


__all__ = ["audit_dossierops", "ACCEPTANCE_TOKEN", "REFUSE_TOKEN", "SCHEMA"]
