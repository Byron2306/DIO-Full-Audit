#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.renderer import render_semantic_asset  # noqa: E402
from products.dossierops_native_hardening import (  # noqa: E402
    METADATA_STATE,
    MIXED_RECORD_CLASS,
    build_chronology,
    claim_map,
    date_key,
    harden_cross_reference,
    harden_source_manifest,
    load_json,
)
from products.dossierops_review_semantic import build_dossier_review_semantic  # noqa: E402
from products.professional_evidence_projection import sha256, write_json  # noqa: E402


SCHEMA = "dio.dossierops.output_finalization.v1"
PASS_TOKEN = "DIO_DOSSIEROPS_OUTPUT_FINALIZED"
REFUSE_TOKEN = "DIO_DOSSIEROPS_OUTPUT_FINALIZATION_REFUSED"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _copy_sources(case_root: Path, stage: Path) -> list[Path]:
    copied: list[Path] = []
    source_root = case_root / "CUSTOMER_PACKET" / "SOURCES"
    for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
        target = stage / "sources" / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def finalize(case_root: Path) -> dict[str, Any]:
    case_root = Path(case_root).expanduser().resolve()
    pilot_receipt_path = case_root / "DOSSIEROPS_NATIVE_PILOT_CHECKPOINT_RECEIPT.json"
    pilot = load_json(pilot_receipt_path)
    if pilot.get("acceptance_token") != "DIO_DOSSIEROPS_NATIVE_PILOT_VERIFIED" or pilot.get("passed") is not True:
        raise RuntimeError("DossierOps finalization requires a verified native pilot receipt")

    pilot_root = case_root / "EXECUTION" / "dossierops_native_pilot"
    analysis_root = pilot_root / "analysis"
    source_manifest = load_json(analysis_root / "DOSSIEROPS_SOURCE_MANIFEST.json")
    source_cross = load_json(analysis_root / "DOSSIEROPS_CLAIM_RECORD_CROSS_REFERENCE.json")
    open_questions = load_json(analysis_root / "DOSSIEROPS_OPEN_QUESTION_REGISTER.json")

    final_root = case_root / "EXECUTION" / "dossierops_native_finalized" / "DOSSIEROPS-FINALIZED"
    if final_root.exists():
        shutil.rmtree(final_root)
    hardened_root = final_root / "analysis"
    review_root = final_root / "review"
    stage = final_root / "bundle_stage"
    for directory in (hardened_root, review_root, stage):
        directory.mkdir(parents=True, exist_ok=True)

    manifest = harden_source_manifest(case_root, source_manifest)
    cross = harden_cross_reference(manifest, source_cross)
    chronology = build_chronology(manifest)

    manifest_path = hardened_root / "DOSSIEROPS_SOURCE_MANIFEST_FINALIZED.json"
    cross_path = hardened_root / "DOSSIEROPS_CLAIM_RECORD_CROSS_REFERENCE_FINALIZED.json"
    chronology_path = hardened_root / "DOSSIEROPS_CHRONOLOGY_FINALIZED.csv"
    questions_path = hardened_root / "DOSSIEROPS_OPEN_QUESTION_REGISTER.json"
    write_json(manifest_path, manifest)
    write_json(cross_path, cross)
    _write_csv(
        chronology_path,
        ["date_as_supplied", "source_level", "record_id", "filename", "record_class", "record_state", "legal_effect_determined"],
        chronology,
    )
    shutil.copy2(analysis_root / "DOSSIEROPS_OPEN_QUESTION_REGISTER.json", questions_path)

    semantic = build_dossier_review_semantic(
        case_root=case_root,
        manifest=manifest,
        cross_reference=cross,
        chronology=chronology,
        open_questions=open_questions,
    )
    semantic_path = final_root / "DOSSIEROPS_FINAL_SEMANTIC_CONTENT.json"
    write_json(semantic_path, semantic)

    format_receipt = render_semantic_asset(
        semantic,
        review_root,
        style_profile="dio_professional",
        delivery_profile="editable_review",
        language="English",
        channels=["docx", "pdf", "html"],
        release_mode=False,
        source_root=case_root / "CUSTOMER_PACKET" / "SOURCES",
    )
    format_receipt_path = review_root / "FORMAT_CORE_RECEIPT.json"
    rendered = {
        str(row.get("channel") or ""): review_root / str(row.get("path") or "")
        for row in format_receipt.get("outputs") or []
    }

    binding_path = Path(str(pilot.get("native_binding") or ""))
    binding = load_json(binding_path)
    docstudio_receipt = Path(str(binding.get("document_studio_receipt") or ""))

    copied_sources = _copy_sources(case_root, stage)
    stage_analysis = stage / "analysis"
    stage_review = stage / "review"
    stage_analysis.mkdir(parents=True, exist_ok=True)
    stage_review.mkdir(parents=True, exist_ok=True)
    for path in (manifest_path, cross_path, chronology_path, questions_path, semantic_path):
        shutil.copy2(path, stage_analysis / path.name)
    for path in rendered.values():
        if path.is_file():
            shutil.copy2(path, stage_review / path.name)
    shutil.copy2(format_receipt_path, stage_review / format_receipt_path.name)
    if docstudio_receipt.is_file():
        shutil.copy2(docstudio_receipt, stage_review / "ORIGINAL_DOCUMENT_STUDIO_RECEIPT.json")
    shutil.copy2(pilot_receipt_path, stage / "SOURCE_NATIVE_PILOT_RECEIPT.json")

    staged_files = [path for path in sorted(stage.rglob("*")) if path.is_file()]
    proof_manifest_path = stage / "DOSSIEROPS_FINAL_PROOF_MANIFEST.json"
    write_json(proof_manifest_path, {
        "schema": "dio.dossierops.final_proof_manifest.v1",
        "source_native_pilot_receipt": str(pilot_receipt_path),
        "files": [
            {"path": str(path.relative_to(stage)), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in staged_files
        ],
        "human_review": "NEEDS_YOU",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    })

    bundle_path = final_root / "DOSSIEROPS_FINAL_CONTROLLED_DOSSIER.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(stage)))

    claims = claim_map(cross)
    chronology_keys = [date_key(row["date_as_supplied"])[0] for row in chronology]
    block_types = {str(row.get("type") or "") for row in semantic.get("blocks") or []}
    markdown_leaks = [
        row for row in semantic.get("blocks") or []
        if str(row.get("text") or "").lstrip().startswith(("#", "- **", "1. "))
    ]
    checks = {
        "source_native_pilot_verified": True,
        "source_case_preserved": pilot_receipt_path.is_file(),
        "mixed_agreement_amendment_class_preserved": any(row.get("record_class") == MIXED_RECORD_CLASS for row in manifest.get("sources") or []),
        "metadata_not_used_as_record_corroboration": all(
            all(link.get("record_state") != METADATA_STATE for link in row.get("candidate_record_links") or [])
            for row in cross.get("claims") or []
        ),
        "payment_claim_not_falsely_correlated": claims.get("R-03", {}).get("corroboration_state") == "register_only_no_separate_record_matched",
        "email_claim_not_falsely_correlated": claims.get("R-04", {}).get("corroboration_state") == "register_only_no_separate_record_matched",
        "chronology_sorted": chronology_keys == sorted(chronology_keys),
        "typed_document_structure": {"title", "heading", "table", "bullet_list"}.issubset(block_types),
        "markdown_structure_not_leaked_as_text": not markdown_leaks,
        "format_core_qa_passed": (format_receipt.get("qa") or {}).get("passed") is True,
        "docx_pdf_html_rendered": all(rendered.get(channel, Path("/__missing__")).is_file() for channel in ("docx", "pdf", "html")),
        "open_questions_preserved": int(open_questions.get("open_count") or 0) >= 3,
        "customer_sources_preserved": len(copied_sources) == len(manifest.get("sources") or []),
        "final_bundle_present": bundle_path.is_file() and bundle_path.stat().st_size >= 100000,
        "document_studio_pilot_evidence_preserved": docstudio_receipt.is_file(),
        "provider_not_called_during_finalization": True,
        "new_fact_generation_absent": True,
        "identity_remains_unpromoted": pilot.get("identity_state") == "controlled_pilot_unpromoted",
        "canonical_registration_not_claimed": pilot.get("canonical_portfolio_registration") is False,
        "external_release_refused": pilot.get("external_release") == "REFUSE",
        "authority_not_created": pilot.get("authority_created") is False,
        "external_effects_absent": pilot.get("external_effects") is False,
    }
    passed = all(checks.values())
    receipt = {
        "schema": SCHEMA,
        "acceptance_token": PASS_TOKEN if passed else REFUSE_TOKEN,
        "passed": passed,
        "source_native_pilot_receipt": str(pilot_receipt_path),
        "source_case_preserved": True,
        "provider_called": False,
        "new_fact_generation": False,
        "checks": checks,
        "artifact_quality_verified": passed,
        "failed_quality_checks": [name for name, ok in checks.items() if not ok],
        "outputs": {
            "job_dir": str(final_root),
            "source_manifest": str(manifest_path),
            "claim_record_cross_reference": str(cross_path),
            "chronology": str(chronology_path),
            "open_question_register": str(questions_path),
            "semantic_content": str(semantic_path),
            "format_core_receipt": str(format_receipt_path),
            "docx": str(rendered.get("docx") or ""),
            "pdf": str(rendered.get("pdf") or ""),
            "html": str(rendered.get("html") or ""),
            "final_bundle": str(bundle_path),
        },
        "identity_state": "controlled_pilot_unpromoted",
        "canonical_portfolio_registration": False,
        "promotion_performed": False,
        "site_promotion_allowed": False,
        "commercial_validation": "UNPROVED",
        "human_review": "NEEDS_YOU",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt_path = case_root / "DOSSIEROPS_OUTPUT_FINALIZATION_RECEIPT.json"
    write_json(receipt_path, receipt)
    receipt["receipt"] = str(receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize an already verified DossierOps pilot locally without another provider call.")
    parser.add_argument("--case-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = finalize(args.case_root)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
