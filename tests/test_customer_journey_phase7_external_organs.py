from __future__ import annotations

from pathlib import Path

import pytest

from presence_core.organ_adapter_gauntlet import (
    ORGAN_FAMILIES,
    VERIFIED_NATIVE,
    seal_native_execution,
    validate_execution_evidence,
)


PINNED = {
    "evidex_evidence": (
        "Byron2306/Evidex",
        "c2754b37ca32e803d84e733b5d59207fdcb17841",
    ),
    "homs_assessment": (
        "Byron2306/NoEdge-Multi-Hymark",
        "a3ea3f627d860fc7b13e2d95f6632f914938c8de",
    ),
    "homs_learning": (
        "Byron2306/NoEdge-Multi-Hymark",
        "a3ea3f627d860fc7b13e2d95f6632f914938c8de",
    ),
    "nichefoundry_campaign": (
        "Byron2306/NicheFoundry",
        "25fef4bd5bfd1258758963b374ef192fc469c14f",
    ),
}


def test_external_organ_bindings_are_pinned_to_exact_main_repo_commits() -> None:
    for family_id, (repository, commit) in PINNED.items():
        binding = ORGAN_FAMILIES[family_id]
        assert binding["execution_class"] == "external_repo"
        assert binding["repository"] == repository
        assert binding["repository_commit"] == commit
        assert len(binding["repository_commit"]) == 40


@pytest.mark.parametrize("family_id", list(PINNED))
def test_external_repo_execution_can_be_sealed_only_from_current_artifact_bytes(
    tmp_path: Path,
    family_id: str,
) -> None:
    artifact = tmp_path / f"{family_id}.json"
    artifact.write_text('{"current":true}\n', encoding="utf-8")

    evidence = seal_native_execution(
        family_id,
        fulfilment_request_sha256="5" * 64,
        execution_profile_sha256="6" * 64,
        artifacts=[
            {
                "artifact_id": f"{family_id}-artifact",
                "kind": "application/json",
                "path": artifact,
            }
        ],
        evidence_refs=[
            f"external-repo:{ORGAN_FAMILIES[family_id]['repository']}@{ORGAN_FAMILIES[family_id]['repository_commit']}"
        ],
    )
    verdict = validate_execution_evidence(
        family_id,
        evidence,
        expected_request_sha256="5" * 64,
        expected_profile_sha256="6" * 64,
    )
    assert verdict["verdict"] == VERIFIED_NATIVE
    assert evidence["authority_created"] is False
