from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from .customer_cases import load_case, update_case
from .journey_core import transition_case


EXECUTION_PROFILE_SCHEMA = "dio.fulfilment_execution_profile.v1"
FULFILMENT_REQUEST_SCHEMA = "dio.fulfilment_request.v1"
FULFILMENT_RESULT_SCHEMA = "dio.fulfilment_result.v1"


Adapter = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _sha256_ref(value: Any, field_name: str) -> str:
    text = _required(value, field_name)
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{field_name} must be a sha256 reference")
    try:
        int(text[7:], 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a sha256 reference") from exc
    return text


def _plain_sha256(value: Any, field_name: str) -> str:
    text = _required(value, field_name)
    if len(text) != 64:
        raise ValueError(f"{field_name} must be a sha256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a sha256 digest") from exc
    return text


def project_execution_profile(
    compiled: dict[str, Any],
    *,
    adapter_id: str,
    adapter_version: str,
) -> dict[str, Any]:
    """Project canonical compiler truth into the universal fulfilment seam.

    This projection deliberately does not modify the product compiler schema. It binds
    the compiled product to a fulfilment adapter while retaining compiler composition,
    capability and provider lineage. The projection itself creates no authority.
    """

    if not isinstance(compiled, dict) or compiled.get("schema") != "dio.compiled_product.v1":
        raise ValueError("canonical compiled product truth is required")

    product_id = _required(compiled.get("product_id"), "compiled product_id")
    product_name = _required(compiled.get("name"), "compiled product name")
    composition_fingerprint = _sha256_ref(
        compiled.get("composition_fingerprint"),
        "composition_fingerprint",
    )
    compilation_fingerprint = _sha256_ref(
        compiled.get("compilation_fingerprint"),
        "compilation_fingerprint",
    )
    adapter_id = _required(adapter_id, "adapter_id")
    adapter_version = _required(adapter_version, "adapter_version")

    execution_gate = deepcopy((compiled.get("gates") or {}).get("execution") or {})
    execution_state = str(execution_gate.get("state") or "").strip().upper()
    if execution_state not in {"ALLOW", "NEEDS_YOU"}:
        raise ValueError("compiled product does not permit bounded fulfilment execution")

    executor_capabilities: list[dict[str, Any]] = []
    for row in compiled.get("capability_plan") or []:
        if not bool(row.get("execution_required")):
            continue
        provider = deepcopy(row.get("provider") or {})
        if (
            row.get("resolution_state") != "RESOLVED"
            or not provider
            or provider.get("execution_capable") is not True
        ):
            raise ValueError("compiled execution capability is unresolved")
        executor_capabilities.append(
            {
                "capability_id": row.get("capability_id"),
                "resolution_state": row.get("resolution_state"),
                "provider": provider,
            }
        )

    if not executor_capabilities:
        raise ValueError("compiled product has no resolved execution capability")

    profile = {
        "schema": EXECUTION_PROFILE_SCHEMA,
        "compiled_product_id": product_id,
        # Compatibility projection: commercial JourneyCase product identity is still
        # the human-readable canonical product name in the current spine. Phase 8
        # owns the final explicit 68-product identity binding.
        "journey_product_id": product_name,
        "composition_fingerprint": composition_fingerprint,
        "compilation_fingerprint": compilation_fingerprint,
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "execution_gate": execution_gate,
        "executor_capabilities": executor_capabilities,
        "output_plan": deepcopy(compiled.get("output_plan") or {}),
        "release_authority_created": False,
        "external_send_authority": False,
        "authority_created": False,
    }
    profile["execution_profile_sha256"] = _canonical_hash(profile)
    return profile


def _canonical_scope(case: dict[str, Any]) -> dict[str, Any]:
    receipt = deepcopy(case.get("scope_receipt") or {})
    if (
        receipt.get("schema") != "dio.scope_receipt.v1"
        or receipt.get("state") != "SUFFICIENT"
        or str(receipt.get("case_id") or "") != str(case.get("case_id") or "")
        or str(receipt.get("product_name") or receipt.get("product_id") or "")
        != str(case.get("product_id") or "")
    ):
        raise ValueError("canonical sufficient scope truth is required")
    _plain_sha256(receipt.get("scope_receipt_sha256"), "scope_receipt_sha256")
    return receipt


def _canonical_quote(case: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy((case.get("commercial") or {}).get("quote_result") or {})
    quote = deepcopy(result.get("quote") or {})
    if (
        result.get("decision") != "ALLOW_PRESENTATION"
        or quote.get("schema") != "dio.customer_quote.v2"
        or str(quote.get("case_id") or "") != str(case.get("case_id") or "")
        or str(quote.get("product_name") or "") != str(case.get("product_id") or "")
        or str(quote.get("scope_receipt_sha256") or "")
        != str(scope.get("scope_receipt_sha256") or "")
    ):
        raise ValueError("canonical quote truth is required")
    _required(quote.get("quote_id"), "quote_id")
    _plain_sha256(quote.get("quote_truth_sha256"), "quote_truth_sha256")
    return quote


def _canonical_settlement(case: dict[str, Any], quote: dict[str, Any]) -> dict[str, Any]:
    receipt = deepcopy(case.get("settlement") or {})
    if (
        receipt.get("schema") != "dio.settlement_receipt.v1"
        or receipt.get("fulfilment_eligible") is not True
        or str(receipt.get("case_id") or "") != str(case.get("case_id") or "")
        or str(receipt.get("quote_id") or "") != str(quote.get("quote_id") or "")
        or str(receipt.get("quote_truth_sha256") or "")
        != str(quote.get("quote_truth_sha256") or "")
        or str(receipt.get("product_name") or "") != str(case.get("product_id") or "")
    ):
        raise ValueError("fulfilment-eligible settlement truth is required")
    _plain_sha256(
        receipt.get("settlement_receipt_sha256"),
        "settlement_receipt_sha256",
    )
    return receipt


def _validate_execution_profile(
    profile: dict[str, Any],
    *,
    journey_product_id: str,
) -> dict[str, Any]:
    if not isinstance(profile, dict) or profile.get("schema") != EXECUTION_PROFILE_SCHEMA:
        raise ValueError("canonical fulfilment execution profile is required")
    if str(profile.get("journey_product_id") or "") != str(journey_product_id):
        raise ValueError("execution profile product does not match customer case")
    _required(profile.get("adapter_id"), "adapter_id")
    _required(profile.get("adapter_version"), "adapter_version")
    _plain_sha256(profile.get("execution_profile_sha256"), "execution_profile_sha256")

    basis = deepcopy(profile)
    expected = basis.pop("execution_profile_sha256")
    if _canonical_hash(basis) != expected:
        raise ValueError("execution profile hash mismatch")
    if (
        profile.get("release_authority_created") is not False
        or profile.get("external_send_authority") is not False
        or profile.get("authority_created") is not False
    ):
        raise ValueError("execution profile may not create release, send, or generic authority")
    return deepcopy(profile)


def build_fulfilment_request(
    state_root: Path,
    case_id: str,
    execution_profile: dict[str, Any],
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    if str(case.get("stage") or "") != "PAYMENT_VERIFIED":
        raise ValueError("fulfilment-eligible settlement truth is required")

    scope = _canonical_scope(case)
    quote = _canonical_quote(case, scope)
    settlement = _canonical_settlement(case, quote)
    profile = _validate_execution_profile(
        execution_profile,
        journey_product_id=str(case.get("product_id") or ""),
    )

    existing = deepcopy((case.get("fulfilment") or {}).get("request") or {})
    if existing.get("schema") == FULFILMENT_REQUEST_SCHEMA:
        if existing.get("execution_profile_sha256") == profile.get("execution_profile_sha256"):
            return existing
        raise ValueError("customer case already has a different fulfilment request")

    request = {
        "schema": FULFILMENT_REQUEST_SCHEMA,
        "case_id": str(case["case_id"]),
        "journey_product_id": str(case.get("product_id") or ""),
        "scope_receipt_sha256": str(scope["scope_receipt_sha256"]),
        "quote_id": str(quote["quote_id"]),
        "quote_truth_sha256": str(quote["quote_truth_sha256"]),
        "settlement_class": str(settlement.get("settlement_class") or ""),
        "settlement_receipt_sha256": str(settlement["settlement_receipt_sha256"]),
        "execution_profile_sha256": str(profile["execution_profile_sha256"]),
        "adapter_id": str(profile["adapter_id"]),
        "adapter_version": str(profile["adapter_version"]),
        "execution_profile": profile,
        "release_authority_created": False,
        "external_send_authority": False,
        "authority_created": False,
    }
    request["fulfilment_request_sha256"] = _canonical_hash(request)

    queued = transition_case(
        state_root,
        str(case_id),
        "WORK_QUEUED",
        evidence_ref=f"fulfilment-request:{request['fulfilment_request_sha256']}",
    )
    update_case(
        state_root,
        queued,
        patch={
            "fulfilment": {
                "state": "queued",
                "request": deepcopy(request),
                "release_authority": False,
                "external_send_authority": False,
            },
            "authority_created": False,
        },
        evidence_ref=f"fulfilment-request:{request['fulfilment_request_sha256']}",
    )
    return request


def _validate_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict) or request.get("schema") != FULFILMENT_REQUEST_SCHEMA:
        raise ValueError("canonical fulfilment request is required")
    expected = _plain_sha256(
        request.get("fulfilment_request_sha256"),
        "fulfilment_request_sha256",
    )
    basis = deepcopy(request)
    basis.pop("fulfilment_request_sha256")
    if _canonical_hash(basis) != expected:
        raise ValueError("fulfilment request hash mismatch")
    _validate_execution_profile(
        deepcopy(request.get("execution_profile") or {}),
        journey_product_id=str(request.get("journey_product_id") or ""),
    )
    if (
        request.get("release_authority_created") is not False
        or request.get("external_send_authority") is not False
        or request.get("authority_created") is not False
    ):
        raise ValueError("fulfilment request may not create release, send, or generic authority")
    return deepcopy(request)


def _normalise_artifacts(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("adapter artifacts must be a list")
    artifacts: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("adapter artifact must be an object")
        artifact = deepcopy(row)
        _required(artifact.get("artifact_id"), "artifact_id")
        _required(artifact.get("kind"), "artifact kind")
        _plain_sha256(artifact.get("sha256"), "artifact sha256")
        if artifact.get("release_state") != "HELD":
            raise ValueError("Phase 4 artifacts must remain HELD")
        if any(
            bool(artifact.get(field))
            for field in (
                "release_authority",
                "external_send_authority",
                "authority_created",
            )
        ):
            raise ValueError("artifact may not create release, send, or generic authority")
        artifacts.append(artifact)
    return artifacts


def dispatch_fulfilment(
    state_root: Path,
    request: dict[str, Any],
    adapters: Mapping[str, Adapter],
) -> dict[str, Any]:
    state_root = Path(state_root)
    request = _validate_request(request)
    case_id = str(request["case_id"])
    case = load_case(state_root, case_id)
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    if str(case.get("stage") or "") != "WORK_QUEUED":
        raise ValueError("customer case is not queued for fulfilment")

    stored_request = deepcopy((case.get("fulfilment") or {}).get("request") or {})
    if stored_request.get("fulfilment_request_sha256") != request.get(
        "fulfilment_request_sha256"
    ):
        raise ValueError("fulfilment request does not match canonical customer case")

    adapter_id = str(request["adapter_id"])
    adapter = adapters.get(adapter_id)
    if not callable(adapter):
        raise ValueError(f"fulfilment adapter not registered: {adapter_id}")

    processing = transition_case(
        state_root,
        case_id,
        "PROCESSING",
        evidence_ref=f"fulfilment-start:{request['fulfilment_request_sha256']}",
    )

    raw = adapter(
        deepcopy(request),
        deepcopy(request["execution_profile"]),
    )
    if not isinstance(raw, dict):
        raise ValueError("fulfilment adapter must return an object")
    if any(
        bool(raw.get(field))
        for field in (
            "release_authority",
            "external_send_authority",
            "authority_created",
        )
    ):
        raise ValueError("adapter may not create release, send, or generic authority")
    if str(raw.get("status") or "").upper() != "COMPLETED":
        raise ValueError("Phase 4 adapter must return COMPLETED for review-ready fulfilment")

    artifacts = _normalise_artifacts(raw.get("artifacts") or [])
    evidence_refs = deepcopy(raw.get("evidence_refs") or [])
    organ_steps = deepcopy(raw.get("organ_steps") or [])
    if not isinstance(evidence_refs, list) or not isinstance(organ_steps, list):
        raise ValueError("adapter evidence_refs and organ_steps must be lists")

    result = {
        "schema": FULFILMENT_RESULT_SCHEMA,
        "case_id": case_id,
        "journey_product_id": str(request["journey_product_id"]),
        "fulfilment_request_sha256": str(request["fulfilment_request_sha256"]),
        "execution_profile_sha256": str(request["execution_profile_sha256"]),
        "adapter_id": adapter_id,
        "adapter_version": str(request["adapter_version"]),
        "status": "COMPLETED",
        "artifacts": artifacts,
        "evidence_refs": evidence_refs,
        "organ_steps": organ_steps,
        "release_authority_created": False,
        "external_send_authority": False,
        "authority_created": False,
    }
    result["fulfilment_result_sha256"] = _canonical_hash(result)

    review_ready = transition_case(
        state_root,
        case_id,
        "REVIEW_READY",
        evidence_ref=f"fulfilment-result:{result['fulfilment_result_sha256']}",
    )
    update_case(
        state_root,
        review_ready,
        patch={
            "fulfilment": {
                "state": "review_ready",
                "request": deepcopy(request),
                "result": deepcopy(result),
                "release_authority": False,
                "external_send_authority": False,
            },
            "authority_created": False,
        },
        evidence_ref=f"fulfilment-result:{result['fulfilment_result_sha256']}",
    )
    return result
