from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


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
    repository: str | None = None,
    repository_commit: str | None = None,
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
        "repository": repository,
        "repository_commit": repository_commit,
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
        "arda_os/backend/services/presence_server.py",
        "external_repo", NEEDS_BINDING,
        repository="Byron2306/Sophia-AI",
        repository_commit="c1aa915560599f7d6cef0ff41e6a7b0787334376",
        note="The canonical Sophia repository is pinned to the isolated DIO review-lane repair. A clean runner proved live 7070 execution through Ollama qwen2.5:0.5b; Phase 7 still requires DIO-sealed execution evidence.",
    ),
    "evidex_evidence": _binding(
        "evidex_evidence", "C", "Evidex Evidence Pack",
        "dio.organ.evidex_evidence", "src/evidence_pack_engine/cli.py",
        "external_repo", NEEDS_BINDING,
        repository="Byron2306/Evidex",
        repository_commit="c2754b37ca32e803d84e733b5d59207fdcb17841",
        note="The canonical Evidex repository exposes a deterministic evidence_pack_engine CLI and is pinned for fresh Phase 7 execution proof.",
    ),
    "vamp_snapshot": _binding(
        "vamp_snapshot", "C", "VAMP Performance Evidence Snapshot",
        "dio.organ.vamp_snapshot", "adapters/vamp/snapshot_pipeline.py",
        "native", NEEDS_BINDING,
        note="A real repository-native snapshot pipeline exists. It still needs a current Journey fulfilment execution receipt before the family becomes VERIFIED_NATIVE.",
    ),
    "homs_assessment": _binding(
        "homs_assessment", "A", "HOMS Assess",
        "dio.organ.homs_assessment", "main.py",
        "external_repo", NEEDS_BINDING,
        repository="Byron2306/NoEdge-Multi-Hymark",
        repository_commit="a3ea3f627d860fc7b13e2d95f6632f914938c8de",
        note="The canonical HOMS repository exposes the real WorkflowEngine and CLI; the commit is pinned for current Phase 7 execution proof.",
    ),
    "homs_learning": _binding(
        "homs_learning", "A", "HOMS Learning Studio",
        "dio.organ.homs_learning", "Marker/homs/core/learning_agent.py",
        "external_repo", NEEDS_BINDING,
        repository="Byron2306/NoEdge-Multi-Hymark",
        repository_commit="a3ea3f627d860fc7b13e2d95f6632f914938c8de",
        note="HOMS Learning is implemented inside the canonical WorkflowEngine; the same pinned run must prove persisted learning artifacts separately from assessment output.",
    ),
    "document_studio": _binding(
        "document_studio", "E", "DIO Document Studio",
        "dio.organ.document_studio", "adapters/document_studio/pipeline.py",
        "native", NEEDS_BINDING,
        note="The repository-native Document Studio pipeline has a governed local Ollama bridge. Clean-run execution must still produce fresh held artifacts and pass deterministic fact-preservation validation before VERIFIED_NATIVE.",
    ),
    "nichefoundry_campaign": _binding(
        "nichefoundry_campaign", "G", "NicheFoundry Campaign Pack",
        "dio.organ.nichefoundry_campaign", "scripts/backend_autopilot.js",
        "external_repo", NEEDS_BINDING,
        repository="Byron2306/NicheFoundry",
        repository_commit="7528d8cdee17c5b6fbe35236b71b8e2191bb108a",
        note="The canonical NicheFoundry repository exposes backend_autopilot.js for real episode/campaign package generation and is pinned for Phase 7 proof.",
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
    elif row["execution_class"] in {"unbound", "external_repo"}:
        row["host_available"] = False
        row["external_repository_required"] = row["execution_class"] == "external_repo"
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


def seal_native_execution(
    family_id: str,
    *,
    fulfilment_request_sha256: str,
    execution_profile_sha256: str,
    artifacts: Sequence[Mapping[str, Any]],
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    if family_id not in ORGAN_FAMILIES:
        raise ValueError(f"unknown Phase 7 organ family: {family_id}")
    binding = ORGAN_FAMILIES[family_id]
    if binding["execution_class"] not in {"native", "external_repo"}:
        raise ValueError(f"Phase 7 family {family_id} is not a permitted native execution binding")
    if not _is_sha256(fulfilment_request_sha256):
        raise ValueError("fulfilment_request_sha256 must be a SHA-256 digest")
    if not _is_sha256(execution_profile_sha256):
        raise ValueError("execution_profile_sha256 must be a SHA-256 digest")
    if not artifacts:
        raise ValueError("native execution must produce at least one artifact")
    if not evidence_refs or not all(isinstance(ref, str) and ref.strip() for ref in evidence_refs):
        raise ValueError("native execution must provide evidence references")

    sealed_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        kind = str(artifact.get("kind") or "").strip()
        raw_path = artifact.get("path")
        if not artifact_id or not kind or raw_path is None:
            raise ValueError("artifact_id, kind and path are required")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = path.read_bytes()
        sealed_artifacts.append(
            {
                "artifact_id": artifact_id,
                "kind": kind,
                "path": str(path),
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "release_state": "HELD",
                "authority_created": False,
                "release_authority": False,
                "external_send_authority": False,
            }
        )

    return {
        "schema": EVIDENCE_SCHEMA,
        "family_id": family_id,
        "adapter_id": binding["adapter_id"],
        "adapter_version": binding["adapter_version"],
        "fulfilment_request_sha256": fulfilment_request_sha256,
        "execution_profile_sha256": execution_profile_sha256,
        "fresh_execution": True,
        "historical_specimen": False,
        "status": "COMPLETED",
        "artifacts": sealed_artifacts,
        "evidence_refs": list(evidence_refs),
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
    }


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
            if any(bool(artifact.get(key)) for key in ("authority_created", "release_authority", "external_send_authority")):
                reasons.append("artifact_authority_leak")

    refs = evidence.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        reasons.append("missing_execution_evidence_refs")
    elif binding.get("execution_class") == "external_repo":
        expected_ref = f"external-repo:{binding.get('repository')}@{binding.get('repository_commit')}"
        if expected_ref not in refs:
            reasons.append("external_repository_pin_mismatch")

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


ExecutionRunner = Callable[..., Mapping[str, Any]]


def execute_verified_family(
    family_id: str,
    *,
    request: Mapping[str, Any],
    execution_profile: Mapping[str, Any],
    runner: ExecutionRunner,
) -> dict[str, Any]:
    """Execute one Phase 7 family behind the universal Phase 4 adapter seam.

    The runner is not trusted. Its output becomes a Phase 4 adapter result only
    after fresh execution evidence is bound to the exact canonical fulfilment
    request and execution-profile hashes and passes the Phase 7 authority and
    artifact-custody checks.
    """

    if family_id not in ORGAN_FAMILIES:
        raise ValueError(f"unknown Phase 7 organ family: {family_id}")
    binding = ORGAN_FAMILIES[family_id]
    if binding["execution_class"] not in {"native", "external_repo"}:
        raise ValueError(f"Phase 7 family {family_id} is not executable in this environment")
    if not callable(runner):
        raise ValueError("Phase 7 family runner must be callable")

    if request.get("schema") != "dio.fulfilment_request.v1":
        raise ValueError("canonical Phase 4 fulfilment request is required")
    if execution_profile.get("schema") != "dio.fulfilment_execution_profile.v1":
        raise ValueError("canonical Phase 4 execution profile is required")

    request_hash = str(request.get("fulfilment_request_sha256") or "")
    profile_hash = str(execution_profile.get("execution_profile_sha256") or "")
    if not _is_sha256(request_hash):
        raise ValueError("canonical fulfilment_request_sha256 is required")
    if not _is_sha256(profile_hash):
        raise ValueError("canonical execution_profile_sha256 is required")
    if str(request.get("execution_profile_sha256") or "") != profile_hash:
        raise ValueError("fulfilment request and execution profile are not bound")
    if str(request.get("adapter_id") or "") != str(binding["adapter_id"]):
        raise ValueError("fulfilment request adapter does not match Phase 7 family")
    if str(request.get("adapter_version") or "") != str(binding["adapter_version"]):
        raise ValueError("fulfilment request adapter version does not match Phase 7 family")
    if str(execution_profile.get("adapter_id") or "") != str(binding["adapter_id"]):
        raise ValueError("execution profile adapter does not match Phase 7 family")
    if str(execution_profile.get("adapter_version") or "") != str(binding["adapter_version"]):
        raise ValueError("execution profile adapter version does not match Phase 7 family")

    evidence = runner(
        family=family_id,
        binding=deepcopy(binding),
        request=deepcopy(dict(request)),
        execution_profile=deepcopy(dict(execution_profile)),
    )
    if not isinstance(evidence, Mapping):
        raise ValueError("Phase 7 family runner must return execution evidence")

    verdict = validate_execution_evidence(
        family_id,
        evidence,
        expected_request_sha256=request_hash,
        expected_profile_sha256=profile_hash,
    )
    if verdict["verdict"] != VERIFIED_NATIVE:
        reasons = ",".join(verdict.get("reasons") or ["unverified_execution"])
        raise ValueError(f"Phase 7 execution evidence refused: {reasons}")

    artifacts: list[dict[str, Any]] = []
    for row in evidence.get("artifacts") or []:
        artifact = dict(row)
        path = Path(str(artifact.get("path") or "")).expanduser()
        file_name = str(artifact.get("file_name") or path.name or artifact["artifact_id"])
        kind = str(artifact["kind"])
        mime_type = str(
            artifact.get("mime_type")
            or (kind if "/" in kind else "application/octet-stream")
        )
        artifacts.append(
            {
                **artifact,
                "file_name": file_name,
                "mime_type": mime_type,
                "purpose": str(artifact.get("purpose") or "primary_customer_output"),
                "customer_visibility": str(artifact.get("customer_visibility") or "VISIBLE"),
                "provenance": deepcopy(
                    artifact.get("provenance")
                    or {
                        "organ_family": family_id,
                        "adapter_id": binding["adapter_id"],
                        "adapter_version": binding["adapter_version"],
                        "evidence_refs": list(evidence.get("evidence_refs") or []),
                    }
                ),
                "release_conditions": list(
                    artifact.get("release_conditions")
                    or ["exact_manifest_human_approval", "one_use_release_authority"]
                ),
                "source_lineage": list(
                    artifact.get("source_lineage")
                    or [
                        f"fulfilment-request:{request_hash}",
                        f"execution-profile:{profile_hash}",
                    ]
                ),
                "release_state": "HELD",
                "release_authority": False,
                "external_send_authority": False,
                "authority_created": False,
            }
        )

    return {
        "status": "COMPLETED",
        "artifacts": artifacts,
        "evidence_refs": list(evidence.get("evidence_refs") or [])
        + [f"phase7-verdict:{family_id}:VERIFIED_NATIVE"],
        "organ_steps": [
            {
                "organ_family": family_id,
                "adapter_id": binding["adapter_id"],
                "adapter_version": binding["adapter_version"],
                "state": VERIFIED_NATIVE,
            }
        ],
        "release_authority": False,
        "external_send_authority": False,
        "authority_created": False,
    }