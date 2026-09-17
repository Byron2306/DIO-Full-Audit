from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


VERIFIED_NATIVE = "VERIFIED_NATIVE"
NEEDS_HOST = "NEEDS_HOST"
NEEDS_BINDING = "NEEDS_BINDING"
REFUSE = "REFUSE"

EVIDENCE_SCHEMA = "dio.organ_adapter_execution_evidence.v1"
PREFLIGHT_SCHEMA = "dio.customer_journey.phase7_preflight.v1"


def _binding(
    family_id: str,
    archetype: str,
    representative_product: str,
    adapter_id: str,
    source_path: str,
    execution_class: str,
    verdict: str,
    *,
    host_capability: str | None = None,
    note: str,
) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "archetype": archetype,
        "representative_product": representative_product,
        "adapter_id": adapter_id,
        "adapter_version": "1",
        "source_path": source_path,
        "execution_class": execution_class,
        "host_capability": host_capability,
        "verdict": verdict,
        "note": note,
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
    }


# This registry is intentionally conservative. Source code or historical
# output is not execution evidence. VERIFIED_NATIVE is awarded only by
# validate_execution_evidence() for a fresh, hash-bound run.
ORGAN_FAMILIES: dict[str, dict[str, Any]] = {
    "sophia_review": _binding(
        "sophia_review", "B", "Sophia Academic Review Desk",
        "dio.organ.sophia_review",
        "cross_folder_variants/Integritas-Mechanicus/A_CODE/scripts/sophia_writing_desk_phase1_smoke.py",
        "host_bound", NEEDS_HOST,
        host_capability="sophia_7070_reviewer",
        note="Reviewer-oriented code exists, but the live 7070 reviewer route must be proven on its configured host before universal activation.",
    ),
    "evidex_evidence": _binding(
        "evidex_evidence", "C", "Evidex Evidence Pack",
        "dio.organ.evidex_evidence", "scripts/run_evidex_jobs.py",
        "host_bound", NEEDS_HOST,
        host_capability="evidex_runtime",
        note="The repository adapter invokes the external /home/byron/Evidex runtime; GitHub-hosted CI cannot counterfeit that execution.",
    ),
    "vamp_snapshot": _binding(
        "vamp_snapshot", "C", "VAMP Performance Evidence Snapshot",
        "dio.organ.vamp_snapshot", "adapters/vamp/snapshot_pipeline.py",
        "native", NEEDS_BINDING,
        note="A real repository-native snapshot pipeline exists. It still needs a current Journey fulfilment execution receipt before the family becomes VERIFIED_NATIVE.",
    ),
    "homs_assessment": _binding(
        "homs_assessment", "A", "HOMS Assess",
        "dio.organ.homs_assessment", "scripts/run_homs_jobs.py",
        "unbound", NEEDS_BINDING,
        note="Current repository path prepares HOMS request/marking packs and explicitly stops before the HOMS backend.",
    ),
    "homs_learning": _binding(
        "homs_learning", "A", "HOMS Learning Studio",
        "dio.organ.homs_learning", "adapters/homs/README.md",
        "unbound", NEEDS_BINDING,
        note="No current Journey-bound learning-organ execution entrypoint has been proven.",
    ),
    "document_studio": _binding(
        "document_studio", "E", "DIO Document Studio",
        "dio.organ.document_studio", "adapters/document_studio/pipeline.py",
        "host_bound", NEEDS_HOST,
        host_capability="document_studio_provider_runtime",
        note="The pipeline is substantive, but provider execution depends on configured Sophia/Gemini or NIM host/runtime services.",
    ),
    "nichefoundry_campaign": _binding(
        "nichefoundry_campaign", "G", "NicheFoundry Campaign Pack",
        "dio.organ.nichefoundry_campaign", "scripts/run_nichefoundry_jobs.py",
        "unbound", NEEDS_BINDING,
        note="The current runner records prepared_request_only and does not execute the NicheFoundry production pipeline.",
    ),
    "obligation_assurance": _binding(
        "obligation_assurance", "D", "Obligation / Assurance Core",
        "dio.organ.obligation_assurance", "products/obligationfamily/runner.py",
        "native", NEEDS_BINDING,
        note="The deterministic obligation-family runner is repository-native and writes hash-bound multi-format proof packs while preserving NEEDS_YOU fulfilment and REFUSE release gates. It still requires a fresh Journey-bound execution receipt.",
    ),
}


def inspect_family(
    family_id: str,
    *,
    repo_root: Path,
    host_capabilities: set[str],
) -> dict[str, Any]:
    if family_id not in ORGAN_FAMILIES:
        raise ValueError(f"unknown Phase 7 organ family: {family_id}")
    row = deepcopy(ORGAN_FAMILIES[family_id])
    source = repo_root / row["source_path"]
    row["source_present"] = source.exists()

    if row["execution_class"] == "host_bound":
        capability = row.get("host_capability")
        row["host_available"] = bool(capability and capability in host_capabilities)
        row["verdict"] = NEEDS_BINDING if row["host_available"] else NEEDS_HOST
    elif row["execution_class"] == "unbound":
        row["host_available"] = False
        row["verdict"] = NEEDS_BINDING
    else:
        row["host_available"] = True
        # Presence is prerequisite only. It is not proof of execution.
        row["verdict"] = NEEDS_BINDING if row["source_present"] else REFUSE
    return row


def phase7_preflight(*, repo_root: Path, host_capabilities: set[str]) -> dict[str, Any]:
    families = [
        inspect_family(family_id, repo_root=repo_root, host_capabilities=host_capabilities)
        for family_id in ORGAN_FAMILIES
    ]
    verified_count = sum(1 for row in families if row["verdict"] == VERIFIED_NATIVE)
    return {
        "schema": PREFLIGHT_SCHEMA,
        "family_count": len(families),
        "verified_count": verified_count,
        "families": families,
        "phase8_unblocked": verified_count == len(families),
        "authority_created": False,
        "external_send_authority": False,
    }


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value.lower())


def validate_execution_evidence(
    family_id: str,
    evidence: Mapping[str, Any],
    *,
    expected_request_sha256: str,
    expected_profile_sha256: str,
) -> dict[str, Any]:
    if family_id not in ORGAN_FAMILIES:
        raise ValueError(f"unknown Phase 7 organ family: {family_id}")

    binding = ORGAN_FAMILIES[family_id]
    reasons: list[str] = []
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        reasons.append("wrong_schema")
    if evidence.get("family_id") != family_id:
        reasons.append("wrong_family")
    if evidence.get("adapter_id") != binding["adapter_id"]:
        reasons.append("wrong_adapter")
    if str(evidence.get("adapter_version")) != binding["adapter_version"]:
        reasons.append("wrong_adapter_version")
    if evidence.get("fulfilment_request_sha256") != expected_request_sha256:
        reasons.append("request_hash_mismatch")
    if evidence.get("execution_profile_sha256") != expected_profile_sha256:
        reasons.append("profile_hash_mismatch")
    if not evidence.get("fresh_execution") or evidence.get("historical_specimen"):
        reasons.append("not_fresh_execution")
    if evidence.get("status") != "COMPLETED":
        reasons.append("not_completed")
    if any(bool(evidence.get(key)) for key in ("authority_created", "release_authority", "external_send_authority")):
        reasons.append("authority_leak")

    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        reasons.append("missing_artifacts")
    else:
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                reasons.append("invalid_artifact")
                continue
            if not artifact.get("artifact_id") or not artifact.get("kind"):
                reasons.append("invalid_artifact_identity")
            if not _is_sha256(artifact.get("sha256")):
                reasons.append("invalid_artifact_hash")
            if artifact.get("release_state") != "HELD":
                reasons.append("artifact_not_held")

    refs = evidence.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        reasons.append("missing_execution_evidence_refs")

    verdict = VERIFIED_NATIVE if not reasons else REFUSE
    return {
        "schema": "dio.organ_adapter_gauntlet_verdict.v1",
        "family_id": family_id,
        "adapter_id": binding["adapter_id"],
        "adapter_version": binding["adapter_version"],
        "verdict": verdict,
        "reasons": sorted(set(reasons)),
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
    }
