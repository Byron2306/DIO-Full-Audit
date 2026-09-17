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

import os
import subprocess
import sys
import zipfile


def _external_root(env_name: str) -> Path:
    value = os.environ.get(env_name)
    if not value:
        pytest.skip(f"{env_name} is not configured for this runner")
    root = Path(value).resolve()
    assert root.is_dir()
    return root


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"command failed: {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result


def test_real_evidex_main_repo_generates_and_seals_current_evidence_pack(tmp_path: Path) -> None:
    root = _external_root("PHASE7_EVIDEX_ROOT")
    output = tmp_path / "evidex-output"
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(root / "src"),
        "LLM_DISABLED": "1",
        "SUMMARY_USE_LLM": "0",
        "NARRATIVE_USE_LLM": "0",
    })
    result = _run(
        [
            sys.executable,
            "-m",
            "evidence_pack_engine.cli",
            "generate",
            "--intake",
            str(root / "samples" / "grant_reporting" / "intake.yaml"),
            "--uploads",
            str(root / "samples" / "grant_reporting" / "uploads"),
            "--out",
            str(output),
        ],
        cwd=root,
        env=env,
    )
    zip_path = Path(result.stdout.strip().splitlines()[-1]).resolve()
    assert zip_path.is_file()
    assert zip_path.stat().st_size > 0
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert any("00_EXEC_SUMMARY/" in name for name in names)
    assert any("01_EVIDENCE_TABLE/" in name for name in names)
    assert any("03_SOURCES/" in name for name in names)

    evidence = seal_native_execution(
        "evidex_evidence",
        fulfilment_request_sha256="7" * 64,
        execution_profile_sha256="8" * 64,
        artifacts=[
            {
                "artifact_id": "evidex-evidence-pack",
                "kind": "application/zip",
                "path": zip_path,
            }
        ],
        evidence_refs=[
            "external-repo:Byron2306/Evidex@c2754b37ca32e803d84e733b5d59207fdcb17841",
            "entrypoint:evidence_pack_engine.cli generate",
        ],
    )
    verdict = validate_execution_evidence(
        "evidex_evidence",
        evidence,
        expected_request_sha256="7" * 64,
        expected_profile_sha256="8" * 64,
    )
    assert verdict["verdict"] == VERIFIED_NATIVE
    assert evidence["artifacts"][0]["size_bytes"] > 0


def test_real_homs_main_repo_proves_assessment_and_learning_outputs() -> None:
    root = _external_root("PHASE7_HOMS_ROOT")
    marker = root / "Marker"
    _run([sys.executable, "scripts/create_demo_reference.py"], cwd=marker)
    result = _run([sys.executable, "scripts/run_demo_assessment.py"], cwd=marker)
    assert "Workflow complete" in result.stdout

    output = marker / "output"
    summary_path = output / "workflow_summary.json"
    detailed_path = output / "detailed_report.json"
    csv_path = output / "results.csv"
    html_path = output / "summary_report.html"
    knowledge_path = output / "knowledge_base.pkl"
    for path in (summary_path, detailed_path, csv_path, html_path, knowledge_path):
        assert path.is_file()
        assert path.stat().st_size > 0

    summary = __import__("json").loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    steps = {row["step"]: row["status"] for row in summary["steps"]}
    assert steps["assessment"] == "success"
    assert steps["moderation"] == "success"
    assert steps["learning"] == "success"
    assert steps["reporting"] == "success"
    assert steps["data_save"] == "success"

    assessment_evidence = seal_native_execution(
        "homs_assessment",
        fulfilment_request_sha256="9" * 64,
        execution_profile_sha256="a" * 64,
        artifacts=[
            {"artifact_id": "homs-summary", "kind": "text/html", "path": html_path},
            {"artifact_id": "homs-detailed", "kind": "application/json", "path": detailed_path},
            {"artifact_id": "homs-results", "kind": "text/csv", "path": csv_path},
            {"artifact_id": "homs-workflow", "kind": "application/json", "path": summary_path},
        ],
        evidence_refs=[
            "external-repo:Byron2306/NoEdge-Multi-Hymark@a3ea3f627d860fc7b13e2d95f6632f914938c8de",
            "entrypoint:Marker/scripts/run_demo_assessment.py",
        ],
    )
    assessment_verdict = validate_execution_evidence(
        "homs_assessment",
        assessment_evidence,
        expected_request_sha256="9" * 64,
        expected_profile_sha256="a" * 64,
    )
    assert assessment_verdict["verdict"] == VERIFIED_NATIVE

    learning_evidence = seal_native_execution(
        "homs_learning",
        fulfilment_request_sha256="b" * 64,
        execution_profile_sha256="c" * 64,
        artifacts=[
            {"artifact_id": "homs-learning-kb", "kind": "application/octet-stream", "path": knowledge_path},
            {"artifact_id": "homs-learning-workflow", "kind": "application/json", "path": summary_path},
        ],
        evidence_refs=[
            "external-repo:Byron2306/NoEdge-Multi-Hymark@a3ea3f627d860fc7b13e2d95f6632f914938c8de",
            "workflow-step:learning:success",
        ],
    )
    learning_verdict = validate_execution_evidence(
        "homs_learning",
        learning_evidence,
        expected_request_sha256="b" * 64,
        expected_profile_sha256="c" * 64,
    )
    assert learning_verdict["verdict"] == VERIFIED_NATIVE
