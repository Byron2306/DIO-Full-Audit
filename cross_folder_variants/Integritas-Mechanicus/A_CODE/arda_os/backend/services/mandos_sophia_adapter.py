"""Mandos M1.1: bounded response-bound behavioral evaluation."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

SOURCE_JUDGE = Path(__file__).resolve().with_name("mandos_protocol_judge.py")

SOURCE_SHA256 = "9e0d96220f91f0be713fb33a157143794ee02ed92d55ca9352cc3b3ba649776c"

REQUIRED_R3_CHECKS = {
    "manuscript_digest",
    "rubric_digest",
    "zpd_guidance_digest",
    "prompt_digest",
    "response_digest",
    "model_identity",
    "r2_prompt_binding",
    "r2_response_binding",
    "r2_academic_diagnostic",
    "r2_authority_bounded",
    "r2_schema",
    "mandos_response_binding",
    "genesis_response_binding",
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def assess(
    *,
    directive: str,
    response: str,
    model: str,
    r2_receipt: dict[str, Any],
    r3_receipt: dict[str, Any],
    academic_grounding_passed: bool,
    document_provenance_verified: bool = False,
    source_path: Path = SOURCE_JUDGE,
) -> dict[str, Any]:

    outcome = {
        "schema": "dio.mandos.sophia_response_m1.1.v1",
        "status": "REFUSE",
        "authority": "BEHAVIORAL_DIAGNOSTIC_ONLY",
        "behavioral_passed": False,
        "constitutional_release_authorized": False,
        "model": model,
        "response_sha256": digest(response) if isinstance(response, str) else None,
        "source_sha256_expected": SOURCE_SHA256,
        "checks": {},
        "reason": "prerequisites_not_established",
    }

    def refuse(reason):
        outcome["reason"] = reason
        return outcome

    if not isinstance(response, str) or not response.strip():
        return refuse("empty_response")

    if not isinstance(r2_receipt, dict):
        return refuse("missing_r2_receipt")

    if r2_receipt.get("schema") != "dio.sophia.response-evidence.v1":
        return refuse("invalid_r2_schema")

    if r2_receipt.get("authority") != "DIAGNOSTIC_ONLY_NOT_CONSTITUTIONAL_APPROVAL":
        return refuse("invalid_r2_authority")

    if r2_receipt.get("response_sha256") != digest(response):
        return refuse("r2_response_digest_mismatch")

    if r2_receipt.get("model") != model:
        return refuse("r2_model_mismatch")

    if (r2_receipt.get("academic_evidence") or {}).get("passed") is not True:
        return refuse("r2_academic_diagnostic_failed")

    if not isinstance(r3_receipt, dict):
        return refuse("missing_r3_receipt")

    if (
        r3_receipt.get("schema") != "dio.sophia.custody.v1"
        or r3_receipt.get("status") != "PASS"
        or r3_receipt.get("passed") is not True
        or r3_receipt.get("constitutional_release_authorized") is not False
    ):
        return refuse("r3_custody_not_passed")

    if r3_receipt.get("authority") not in {
        "ARTIFACT_INTEGRITY_ONLY",
        "IN_PROCESS_CUSTODY_CONSISTENCY_ONLY",
    }:
        return refuse("invalid_r3_authority")

    artifacts = r3_receipt.get("artifact_sha256") or {}
    if artifacts.get("response") != digest(response):
        return refuse("r3_response_digest_mismatch")

    if (
        r3_receipt.get("requested_model") != model
        or r3_receipt.get("actual_model") != model
    ):
        return refuse("r3_model_mismatch")

    findings = r3_receipt.get("findings")
    if not isinstance(findings, list):
        return refuse("r3_findings_missing")

    if any(
        not isinstance(item, dict)
        or item.get("passed") is not True
        or not isinstance(item.get("check"), str)
        for item in findings
    ):
        return refuse("r3_failed_finding")

    names = [item["check"] for item in findings]
    if len(names) != len(set(names)):
        return refuse("r3_duplicate_findings")

    if not REQUIRED_R3_CHECKS.issubset(set(names)):
        return refuse("r3_required_findings_missing")

    if academic_grounding_passed is not True:
        return refuse("academic_grounding_failed")

    try:
        source_bytes = Path(source_path).read_bytes()
    except OSError:
        return refuse("mandos_source_missing")

    if Path(source_path).resolve() != SOURCE_JUDGE:
        return refuse("mandos_source_outside_canonical")

    actual_source_digest = hashlib.sha256(source_bytes).hexdigest()
    outcome["source_sha256_actual"] = actual_source_digest

    if actual_source_digest != SOURCE_SHA256:
        return refuse("mandos_source_identity_mismatch")

    if document_provenance_verified is not True:
        outcome["status"] = "INSUFFICIENT_EVIDENCE"
        return refuse("document_provenance_not_independently_verified")

    try:
        spec = importlib.util.spec_from_file_location(
            "mandos_m11_source", source_path
        )
        if spec is None or spec.loader is None:
            return refuse("mandos_source_unavailable")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        judgment = module.MandosProtocolJudge().judge(
            directive=directive,
            response=response,
            source="reasoned_integrity_lane",
            release_ledger={
                "provenance_status": "document_evidence",
            },
        )

        if (
            not isinstance(judgment, dict)
            or judgment.get("schema_version") != "mandos.protocol_judge.v1"
        ):
            return refuse("invalid_mandos_judgment")

        outcome["checks"] = judgment.get("checks") or {}
        outcome["failed_checks"] = judgment.get("failed_checks") or []
        outcome["behavioral_verdict"] = judgment.get("verdict")
        outcome["behavioral_passed"] = judgment.get("passed") is True

        if outcome["behavioral_passed"]:
            outcome["status"] = "BEHAVIORAL_PASS"
            outcome["reason"] = "behavioral_checks_passed_release_withheld"
        else:
            outcome["reason"] = "mandos_behavioral_checks_failed"

    except Exception as error:
        outcome["status"] = "REFUSE"
        outcome["reason"] = "mandos_evaluation_error"
        outcome["error_type"] = type(error).__name__

    return outcome
