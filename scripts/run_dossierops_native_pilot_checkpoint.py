#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.dossierops_native_pilot import ENGINE_IDENTITY, run_dossierops_native_pilot  # noqa: E402
from products.dossierops_native_quality import audit_dossierops  # noqa: E402
from products.native_product_quality import ACCEPTANCE_TOKEN  # noqa: E402
from products.professional_evidence_executor import _blind_review, _trace_customer_records  # noqa: E402
from products.professional_evidence_projection import load_packet, sha256, slug, write_json  # noqa: E402
from products.professional_evidence_vesper_gate import _prepare_vesper_front_door  # noqa: E402


SCHEMA = "dio.dossierops.native_pilot_checkpoint.v1"
PASS_TOKEN = "DIO_DOSSIEROPS_NATIVE_PILOT_VERIFIED"
REFUSE_TOKEN = "DIO_DOSSIEROPS_NATIVE_PILOT_REFUSED"
PRODUCT = "DossierOps"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _normalize_preferred_terms(request: dict[str, Any]) -> dict[str, Any]:
    """Map DossierOps wording controls onto the correct Document Studio rail.

    Document Studio's ``preferred_terms`` contract is translation-specific: each
    row describes a source-to-target terminology choice and release validation
    expects the target term to appear in translation output. DossierOps currently
    invokes ``technical_edit`` only, so its legacy wording list is not a
    translation glossary. For that service we preserve the phrases as protected
    source tokens and deliberately leave ``preferred_terms`` empty.

    If this adapter is later reused for translation, structured terminology rows
    are retained and legacy strings are normalized into source/target objects.
    """
    normalized = dict(request)
    service = str(normalized.get("service") or "").strip().casefold()
    raw_terms = list(request.get("preferred_terms") or [])

    if service == "technical_edit":
        protected = [str(value).strip() for value in request.get("protected_tokens") or [] if str(value).strip()]
        seen = set(protected)
        for item in raw_terms:
            if isinstance(item, dict):
                term = str(item.get("source") or item.get("source_term") or item.get("target") or item.get("target_term") or "").strip()
            else:
                term = str(item or "").strip()
            if term and term not in seen:
                protected.append(term)
                seen.add(term)
        normalized["protected_tokens"] = protected
        normalized["preferred_terms"] = []
        return normalized

    rows: list[dict[str, Any]] = []
    for item in raw_terms:
        if isinstance(item, dict):
            row = dict(item)
            source = str(row.get("source") or row.get("source_term") or "").strip()
            target = str(row.get("target") or row.get("target_term") or source).strip()
            if source:
                row["source"] = source
                row["target"] = target or source
                rows.append(row)
            continue
        term = str(item or "").strip()
        if term:
            rows.append(
                {
                    "source": term,
                    "target": term,
                    "note": "DossierOps controlled terminology; preserve wording unless human review changes it.",
                }
            )
    normalized["preferred_terms"] = rows
    return normalized


def _document_studio_contract_runner(request: dict[str, Any], request_path: Path, output_root: Path) -> Path:
    """Repair the DossierOps-to-Document-Studio request seam before real execution."""
    from adapters.document_studio.pipeline import run_document_studio

    normalized = _normalize_preferred_terms(request)
    malformed = [row for row in normalized.get("preferred_terms") or [] if not isinstance(row, dict)]
    if malformed:
        raise RuntimeError("DossierOps Document Studio preferred_terms contract remained malformed after normalization")
    if str(normalized.get("service") or "").strip().casefold() == "technical_edit" and normalized.get("preferred_terms"):
        raise RuntimeError("DossierOps technical-edit request must not carry translation preferred_terms")
    write_json(request_path, normalized)
    return run_document_studio(normalized, request_path, output_root)


def run_checkpoint(output_root: Path) -> dict[str, Any]:
    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    case_root = output_root / slug(PRODUCT)
    created_at = utc_now()

    try:
        vesper, case_root = _prepare_vesper_front_door(PRODUCT, output_root, now=created_at)
        packet = load_packet(case_root / "CUSTOMER_PACKET")
        projection_dir = case_root / "PROJECTION"
        execution_dir = case_root / "EXECUTION"
        for directory in (projection_dir, execution_dir):
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True, exist_ok=False)

        trace = _trace_customer_records(packet, projection_dir / "CUSTOMER_FACT_TRACE.json")
        result = run_dossierops_native_pilot(
            packet,
            execution_dir,
            operator_id="dossierops-native-pilot-checkpoint",
            now=created_at,
            document_studio_runner=_document_studio_contract_runner,
        )
        blind = _blind_review(case_root, result, trace)
        binding_path = execution_dir / "DOSSIEROPS_NATIVE_ROUTE_BINDING.json"
        if not binding_path.is_file():
            raise RuntimeError("DossierOps pilot did not persist its native binding")
        quality = audit_dossierops(binding_path)
        quality_path = case_root / "DIO_NATIVE_PRODUCT_QUALITY_RECEIPT.json"
        write_json(quality_path, quality)

        source_bindings = list(vesper.get("source_bindings") or [])
        checks = {
            "vesper_web_chat_front_door": vesper.get("channel") == "web_chat" and vesper.get("handoff_state") == "READY_FOR_PRODUCT_EXECUTION",
            "vesper_resolved_dossierops": vesper.get("resolved_incarnation") == PRODUCT,
            "vesper_examiner_truth_absent": vesper.get("examiner_data_used") is False,
            "vesper_quarantine_source_bindings_present": len(source_bindings) >= 5,
            "all_product_sources_rehydrated_from_quarantine": bool(source_bindings) and all(row.get("rehydrated_into_product_packet") is True for row in source_bindings),
            "packet_fingerprint_preserved": result.get("receipt", {}).get("packet_fingerprint") == packet.get("packet_fingerprint"),
            "native_engine_identity": result.get("native_engine_identity") == ENGINE_IDENTITY,
            "native_capability_preserved": result.get("native_capability_preserved") is True,
            "surrogate_fallback_unused": result.get("surrogate_fallback_used") is False,
            "product_pipeline_executed": result.get("product_pipeline_executed") is True,
            "blind_customer_fact_review": blind.get("passed") is True,
            "artifact_quality_verified": quality.get("acceptance_token") == ACCEPTANCE_TOKEN and quality.get("artifact_quality_verified") is True,
            "identity_remains_controlled_pilot_unpromoted": quality.get("identity_state") == "controlled_pilot_unpromoted",
            "canonical_portfolio_registration_not_claimed": quality.get("canonical_portfolio_registration") is False,
            "human_review_required": result.get("receipt", {}).get("human_review_gate") == "NEEDS_YOU",
            "external_release_refused": result.get("receipt", {}).get("external_release_gate") == "REFUSE",
            "authority_not_created": result.get("receipt", {}).get("authority_created") is False,
            "external_effects_absent": result.get("receipt", {}).get("external_effects") is False,
        }
        passed = all(checks.values())
        receipt = {
            "schema": SCHEMA,
            "acceptance_token": PASS_TOKEN if passed else REFUSE_TOKEN,
            "passed": passed,
            "created_at": created_at,
            "product": PRODUCT,
            "checks": checks,
            "vesper_binding": str(case_root / "VESPER_WEB_CHAT" / "VESPER_WEB_CHAT_BINDING.json"),
            "vesper_source_binding_count": len(source_bindings),
            "native_engine_identity": result.get("native_engine_identity"),
            "terminal_artifact_kind": result.get("terminal_artifact_kind"),
            "native_binding": str(binding_path),
            "quality_receipt": str(quality_path),
            "artifact_quality_verified": quality.get("artifact_quality_verified") is True,
            "failed_quality_checks": [name for name, ok in (quality.get("checks") or {}).items() if not ok],
            "blind_review": str(case_root / "BLIND_REVIEW.json"),
            "identity_state": quality.get("identity_state"),
            "canonical_portfolio_registration": quality.get("canonical_portfolio_registration"),
            "promotion_performed": False,
            "commercial_validation": "UNPROVED",
            "human_review": "NEEDS_YOU",
            "external_release": "REFUSE",
            "authority_created": False,
            "external_effects": False,
            "artifacts": _inventory(case_root),
        }
    except Exception as exc:
        case_root.mkdir(parents=True, exist_ok=True)
        error_path = case_root / "DOSSIEROPS_NATIVE_PILOT_ERROR.txt"
        error_path.write_text(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")
        receipt = {
            "schema": SCHEMA,
            "acceptance_token": REFUSE_TOKEN,
            "passed": False,
            "created_at": created_at,
            "product": PRODUCT,
            "error": f"{type(exc).__name__}: {exc}",
            "error_artifact": str(error_path),
            "promotion_performed": False,
            "commercial_validation": "UNPROVED",
            "human_review": "NEEDS_YOU",
            "external_release": "REFUSE",
            "authority_created": False,
            "external_effects": False,
            "artifacts": _inventory(case_root),
        }

    receipt["receipt_fingerprint"] = _fingerprint({key: value for key, value in receipt.items() if key != "receipt_fingerprint"})
    receipt_path = case_root / "DOSSIEROPS_NATIVE_PILOT_CHECKPOINT_RECEIPT.json"
    write_json(receipt_path, receipt)
    receipt["receipt"] = str(receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DossierOps through Vesper custody, the native controlled pilot, Document Studio and the artifact-quality gate without promoting canonical identity.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_checkpoint(args.output)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
