from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from products.unpromoted_evidence_profile import (
    load_unpromoted_evidence_profile,
    run_unpromoted_evidence_review,
)


HOMS_CURRICULUM_SOURCE_CONTRACT = "homs_learning_pack_receipt_artifacts"
ALLOWED_PROFILE_ID = "homs_curriculum"
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_pack_contract(
    manifest: dict[str, Any],
    validation: dict[str, Any],
    build_receipt: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if manifest.get("schema") != "homs.learning_pack.manifest.v1":
        raise ValueError(
            "HOMS Curriculum composition requires schema=homs.learning_pack.manifest.v1."
        )
    pack_id = str(manifest.get("pack_id") or "").strip()
    if not pack_id:
        raise ValueError("HOMS learning-pack manifest requires a non-empty pack_id.")
    if manifest.get("status") != "educator_review_required":
        raise RuntimeError(
            "HOMS Curriculum composition requires manifest status=educator_review_required."
        )

    request = manifest.get("request")
    if not isinstance(request, dict):
        raise ValueError("HOMS learning-pack manifest requires a request object.")
    if request.get("educator_approval_required") is not True:
        raise RuntimeError(
            "HOMS Curriculum composition requires educator_approval_required=true."
        )

    curriculum = manifest.get("curriculum_evidence")
    if not isinstance(curriculum, dict):
        raise ValueError("HOMS learning-pack manifest requires curriculum evidence provenance.")
    curriculum_sha = str(curriculum.get("source_sha256") or "").lower()
    if not SHA256_RE.fullmatch(curriculum_sha):
        raise ValueError(
            "HOMS curriculum evidence requires a canonical SHA-256 source digest."
        )

    authority = manifest.get("authority")
    if not isinstance(authority, dict):
        raise ValueError("HOMS learning-pack manifest requires an explicit authority boundary.")
    if authority.get("generation") != "completed":
        raise RuntimeError("HOMS learning-pack generation must be completed.")
    if authority.get("educator_approval") != "required":
        raise RuntimeError("HOMS Curriculum composition requires educator approval.")
    if authority.get("classroom_release") != "blocked_pending_approval":
        raise RuntimeError(
            "HOMS Curriculum composition refuses a manifest without blocked classroom release."
        )
    if authority.get("video_publication") not in {
        "blocked_pending_review",
        "blocked_pending_educator_approval",
    }:
        raise RuntimeError(
            "HOMS Curriculum composition refuses a manifest without blocked video publication."
        )

    if validation.get("schema") != "homs.learning_pack.validation.v1":
        raise ValueError(
            "HOMS Curriculum composition requires schema=homs.learning_pack.validation.v1."
        )
    if str(validation.get("pack_id") or "") != pack_id:
        raise ValueError("HOMS validation pack_id does not match the manifest.")
    if validation.get("passed") is not True:
        raise RuntimeError("HOMS Curriculum composition requires passed pack validation.")
    if list(validation.get("errors") or []):
        raise RuntimeError("HOMS Curriculum composition refuses validation errors.")
    checks = validation.get("checks")
    if not isinstance(checks, dict) or checks.get("educator_approval_gate_present") is not True:
        raise RuntimeError(
            "HOMS Curriculum composition requires the educator approval gate validation check."
        )

    if str(build_receipt.get("pack_id") or "") != pack_id:
        raise ValueError("HOMS build-receipt pack_id does not match the manifest.")
    if build_receipt.get("status") != "passed":
        raise RuntimeError("HOMS Curriculum composition requires a passed build receipt.")
    if list(build_receipt.get("validation_errors") or []):
        raise RuntimeError("HOMS Curriculum composition refuses build validation errors.")
    if build_receipt.get("next_gate") != "educator_subject_expert_review":
        raise RuntimeError(
            "HOMS Curriculum composition requires next_gate=educator_subject_expert_review."
        )

    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("HOMS learning-pack manifest requires hash-bound documents.")

    document_map: dict[str, dict[str, Any]] = {}
    for row in documents:
        if not isinstance(row, dict):
            raise ValueError("HOMS learning-pack documents must be objects.")
        path = str(row.get("path") or "").strip()
        digest = str(row.get("sha256") or "").lower()
        if not path or not SHA256_RE.fullmatch(digest):
            raise ValueError(
                "HOMS learning-pack documents require path and canonical SHA-256 digest."
            )
        if path in document_map:
            raise ValueError(f"HOMS learning-pack document path is duplicated: {path}")
        document_map[path] = row

    return document_map


def _selected_documents(
    document_map: dict[str, dict[str, Any]],
    selected_document_paths: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    selected = [str(value or "").strip() for value in selected_document_paths]
    if not selected or any(not value for value in selected):
        raise ValueError(
            "HOMS Curriculum composition requires explicit non-empty selected_document_paths."
        )
    if len(selected) != len(set(selected)):
        raise ValueError("HOMS selected_document_paths must be unique.")
    unknown = [value for value in selected if value not in document_map]
    if unknown:
        raise ValueError(
            "HOMS selected_document_paths are absent from the manifest: "
            + ", ".join(unknown)
        )
    return [(value, document_map[value]) for value in selected]


def run_unpromoted_homs_curriculum_artifact_review(
    case: dict[str, Any],
    *,
    manifest: dict[str, Any],
    validation: dict[str, Any],
    build_receipt: dict[str, Any],
    selected_document_paths: list[str],
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    """Review bounded HOMS Learning Studio artifacts as Curriculum provenance evidence.

    The upstream Learning Studio receipt may prove that a specific learning pack was
    generated and validated. This bridge does not promote that fact into HOMS Curriculum
    execution proof, curriculum approval, programme-quality certification, accreditation,
    academic-policy authority, institutional sign-off or release authority.
    """

    profile = load_unpromoted_evidence_profile(ALLOWED_PROFILE_ID)
    if profile.get("source_contract") != HOMS_CURRICULUM_SOURCE_CONTRACT:
        raise RuntimeError(
            "HOMS Curriculum profile is not bound to the Learning Studio source contract."
        )

    document_map = _validate_pack_contract(manifest, validation, build_receipt)
    selected = _selected_documents(document_map, selected_document_paths)

    pack_id = str(manifest["pack_id"])
    curriculum = manifest["curriculum_evidence"]

    requirements: list[dict[str, Any]] = [
        {
            "requirement_key": "HOMS-CURRICULUM-SOURCE",
            "statement": (
                "Confirm that the HOMS Learning Studio pack contains hash-bound curriculum "
                "source provenance for human curriculum review. This establishes provenance "
                "only, not curriculum correctness or approval."
            ),
            "kind": "evidence_input",
            "source_ref": f"homs://learning-pack/{pack_id}/curriculum-source",
            "mandatory": True,
            "dependency_requirement_keys": [],
        }
    ]
    evidence_inputs: list[dict[str, Any]] = [
        {
            "evidence_kind": "homs_curriculum_source_binding",
            "source_ref": f"homs://learning-pack/{pack_id}/curriculum-source",
            "sha256": str(curriculum["source_sha256"]).lower(),
            "target_requirement_keys": ["HOMS-CURRICULUM-SOURCE"],
            "relation": "supports",
            "authority_grade": "source_backed",
            "trust_state": "trusted_for_review",
            "freshness_state": "current",
        }
    ]

    for index, (path, row) in enumerate(selected, 1):
        requirement_key = f"HOMS-ARTIFACT-{index}"
        source_ref = f"homs://learning-pack/{pack_id}/artifact/{path}"
        requirements.append(
            {
                "requirement_key": requirement_key,
                "statement": (
                    f"Confirm that selected HOMS Learning Studio artifact {path} is present "
                    "and hash-bound for human curriculum review. This establishes artifact "
                    "provenance only, not curriculum quality, approval or institutional fitness."
                ),
                "kind": "evidence_input",
                "source_ref": source_ref,
                "mandatory": True,
                "dependency_requirement_keys": ["HOMS-CURRICULUM-SOURCE"],
            }
        )
        evidence_inputs.append(
            {
                "evidence_kind": "homs_learning_pack_artifact_receipt_binding",
                "source_ref": source_ref,
                "sha256": str(row["sha256"]).lower(),
                "target_requirement_keys": [requirement_key],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        )

    result = run_unpromoted_evidence_review(
        case,
        profile_id=ALLOWED_PROFILE_ID,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=[],
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    result["homs_source_binding"] = {
        "schema": "dio.homs_curriculum_source_binding.v1",
        "profile_id": ALLOWED_PROFILE_ID,
        "source_contract": HOMS_CURRICULUM_SOURCE_CONTRACT,
        "homs_pack_id": pack_id,
        "manifest_sha256": _canonical_sha256(manifest),
        "validation_sha256": _canonical_sha256(validation),
        "build_receipt_sha256": _canonical_sha256(build_receipt),
        "curriculum_source_sha256": str(curriculum["source_sha256"]).lower(),
        "selected_document_paths": [path for path, _ in selected],
        "upstream_learning_pack_generation_proved": True,
        "upstream_learning_pack_validation_proved": True,
        "curriculum_correctness_proved": False,
        "curriculum_approval_created": False,
        "programme_quality_certification_created": False,
        "execution_proof_created": False,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
    }
    return result
