"""Sophia R3: bounded artifact custody, not constitutional authorization."""

import hashlib
from typing import Any, Mapping


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_custody(
    *,
    manuscript: bytes,
    rubric: bytes,
    zpd_guidance: bytes,
    prompt: str,
    response: str,
    requested_model: str,
    actual_model: str,
    receipt: Mapping[str, Any],
    expected_digests: Mapping[str, str],
) -> dict:
    """Verify supplied artifacts against independently supplied expectations."""

    findings = []

    def check(name, condition):
        findings.append({
            "check": name,
            "passed": bool(condition),
        })

    artifacts = {
        "manuscript": hashlib.sha256(manuscript).hexdigest(),
        "rubric": hashlib.sha256(rubric).hexdigest(),
        "zpd_guidance": hashlib.sha256(zpd_guidance).hexdigest(),
        "prompt": sha256_text(prompt),
        "response": sha256_text(response),
    }

    for name, actual in artifacts.items():
        check(
            f"{name}_digest",
            bool(expected_digests.get(name))
            and expected_digests.get(name) == actual,
        )

    check(
        "model_identity",
        bool(requested_model)
        and requested_model == actual_model
        and receipt.get("model") == actual_model,
    )

    check(
        "r2_prompt_binding",
        receipt.get("prompt_sha256") == artifacts["prompt"],
    )

    check(
        "r2_response_binding",
        receipt.get("response_sha256") == artifacts["response"],
    )

    academic = receipt.get("academic_evidence") or {}
    check(
        "r2_academic_diagnostic",
        academic.get("passed") is True,
    )

    check(
        "r2_authority_bounded",
        receipt.get("authority")
        == "DIAGNOSTIC_ONLY_NOT_CONSTITUTIONAL_APPROVAL",
    )

    check(
        "r2_schema",
        receipt.get("schema")
        == "dio.sophia.response-evidence.v1",
    )

    # R2's nested judgments are negative evidence, not approval.
    mandos = receipt.get("mandos_judgment") or {}
    genesis = receipt.get("article_conformity") or {}

    check(
        "mandos_response_binding",
        mandos.get("response_sha256") == artifacts["response"]
        and mandos.get("passed") is False,
    )

    check(
        "genesis_response_binding",
        genesis.get("response_sha256") == artifacts["response"]
        and (genesis.get("summary") or {}).get("all_passed") is False,
    )

    passed = all(item["passed"] for item in findings)

    return {
        "schema": "dio.sophia.custody.v1",
        "status": "PASS" if passed else "REFUSE",
        "passed": passed,
        "authority": "ARTIFACT_INTEGRITY_ONLY",
        "artifact_sha256": artifacts,
        "requested_model": requested_model,
        "actual_model": actual_model,
        "findings": findings,
        "constitutional_release_authorized": False,
    }
