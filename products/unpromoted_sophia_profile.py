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


SOPHIA_SOURCE_CONTRACT = "sophia_review_receipt_artifacts"
ALLOWED_PROFILE_IDS = {"sophia_integrity", "sophia_research"}
ALLOWED_REVIEW_ARTIFACTS = {
    "CLAIM_SOURCE_LEDGER.json",
    "CLAIM_SOURCE_LEDGER.md",
    "LITERATURE_MAP.json",
    "LITERATURE_MAP.md",
    "REFERENCE_AUDIT.json",
    "REFERENCE_AUDIT.md",
    "REVIEWER_COMMENTARY.json",
    "REVIEWER_COMMENTARY.md",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_receipt(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if receipt.get("schema") != "dio.sophia_review_receipt.v1":
        raise ValueError("Sophia profile composition requires schema=dio.sophia_review_receipt.v1.")
    if not str(receipt.get("job_id") or "").strip():
        raise ValueError("Sophia review receipt requires a non-empty job_id.")
    if receipt.get("status") != "needs_human_review":
        raise RuntimeError("Sophia profile composition requires status=needs_human_review.")
    if receipt.get("delivery_released") is not False:
        raise RuntimeError("Sophia profile composition refuses an already released delivery receipt.")

    source = receipt.get("source")
    if not isinstance(source, dict):
        raise ValueError("Sophia review receipt requires source provenance.")
    source_sha = str(source.get("sha256") or "").lower()
    if not SHA256_RE.fullmatch(source_sha):
        raise ValueError("Sophia review receipt source requires a canonical SHA-256 digest.")
    if source.get("full_text_copied_to_pack") is not False:
        raise RuntimeError("Sophia profile composition requires full_text_copied_to_pack=false.")

    remote = receipt.get("remote_processing")
    if not isinstance(remote, dict):
        raise ValueError("Sophia review receipt requires an explicit remote_processing boundary.")
    performed = remote.get("performed")
    approved = remote.get("gemini_review_approved")
    characters = int(remote.get("characters_transmitted") or 0)
    if performed not in {True, False} or approved not in {True, False}:
        raise ValueError("Sophia remote-processing state must be explicit booleans.")
    if characters < 0:
        raise ValueError("Sophia characters_transmitted cannot be negative.")
    if performed and not approved:
        raise RuntimeError("Sophia remote processing cannot be performed without explicit approval.")
    if performed and characters <= 0:
        raise ValueError("Performed Sophia remote processing requires a positive transmitted character count.")
    if not performed and characters != 0:
        raise ValueError("Sophia remote processing not performed must record zero transmitted characters.")

    outputs = receipt.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("Sophia review receipt requires hash-bound outputs.")

    output_map: dict[str, dict[str, Any]] = {}
    for row in outputs:
        if not isinstance(row, dict):
            raise ValueError("Sophia review receipt outputs must be objects.")
        name = str(row.get("name") or "").strip()
        digest = str(row.get("sha256") or "").lower()
        if not name or not SHA256_RE.fullmatch(digest):
            raise ValueError("Sophia review receipt outputs require name and canonical SHA-256 digest.")
        if name in output_map:
            raise ValueError(f"Sophia review receipt output name is duplicated: {name}")
        output_map[name] = row
    return output_map


def _selected_outputs(
    output_map: dict[str, dict[str, Any]],
    selected_output_names: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    selected = [str(value or "").strip() for value in selected_output_names]
    if not selected or any(not value for value in selected):
        raise ValueError("Sophia profile composition requires explicit non-empty selected_output_names.")
    if len(selected) != len(set(selected)):
        raise ValueError("Sophia selected_output_names must be unique.")
    disallowed = [value for value in selected if value not in ALLOWED_REVIEW_ARTIFACTS]
    if disallowed:
        raise ValueError(
            "Sophia selected outputs are not bounded review artifacts: " + ", ".join(disallowed)
        )
    unknown = [value for value in selected if value not in output_map]
    if unknown:
        raise ValueError(
            "Sophia selected_output_names are absent from the receipt: " + ", ".join(unknown)
        )
    return [(value, output_map[value]) for value in selected]


def run_unpromoted_sophia_artifact_review(
    case: dict[str, Any],
    *,
    profile_id: str,
    sophia_receipt: dict[str, Any],
    selected_output_names: list[str],
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    """Review explicit Sophia Review artifacts without promoting their conclusions.

    This bridge proves only that selected, hash-bound Sophia Review artifacts are present
    in a still-human-gated receipt. It does not treat artifact generation as scientific
    truth, academic-integrity judgment, product execution proof, authority or release.
    """

    if profile_id not in ALLOWED_PROFILE_IDS:
        raise ValueError(
            "Sophia receipt composition is currently bounded to sophia_integrity and sophia_research."
        )
    profile = load_unpromoted_evidence_profile(profile_id)
    if profile.get("source_contract") != SOPHIA_SOURCE_CONTRACT:
        raise RuntimeError(
            f"Evidence profile {profile_id} is not bound to the Sophia review receipt contract."
        )

    output_map = _validate_receipt(sophia_receipt)
    selected = _selected_outputs(output_map, selected_output_names)
    receipt_digest = _canonical_sha256(sophia_receipt)
    job_id = str(sophia_receipt["job_id"])

    requirements: list[dict[str, Any]] = []
    evidence_inputs: list[dict[str, Any]] = []
    for index, (name, row) in enumerate(selected, 1):
        requirement_key = f"SOPHIA-ARTIFACT-{index}"
        source_ref = f"sophia://review/{job_id}/artifact/{name}"
        requirements.append(
            {
                "requirement_key": requirement_key,
                "statement": (
                    f"Confirm that selected Sophia Review artifact {name} is present and hash-bound "
                    "for human review. This establishes artifact provenance only, not substantive correctness."
                ),
                "kind": "evidence_input",
                "source_ref": source_ref,
                "mandatory": True,
                "dependency_requirement_keys": [],
            }
        )
        evidence_inputs.append(
            {
                "evidence_kind": "sophia_review_artifact_receipt_binding",
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
        profile_id=profile_id,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=[],
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    result["sophia_source_binding"] = {
        "schema": "dio.sophia_profile_source_binding.v1",
        "profile_id": profile_id,
        "source_contract": SOPHIA_SOURCE_CONTRACT,
        "sophia_job_id": job_id,
        "receipt_sha256": receipt_digest,
        "source_sha256": str(sophia_receipt["source"]["sha256"]).lower(),
        "selected_output_names": [name for name, _ in selected],
        "substantive_conclusion_proved": False,
        "execution_proof_created": False,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
    }
    return result
