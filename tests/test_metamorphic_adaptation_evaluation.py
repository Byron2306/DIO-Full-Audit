from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.metamorphic_adaptation.evaluation import (
    EvaluationError,
    QUALITY_WEIGHTS,
    blind_artifacts,
    quality_score,
    repair_burden,
    validate_score_sheet,
)


def _artifact_run(tmp_path: Path, run_id: str, arm_id: str, task_id: str) -> dict:
    source = tmp_path / "runs" / arm_id / run_id
    source.mkdir(parents=True, exist_ok=True)
    (source / "artifact.txt").write_text(f"artifact for {run_id}", encoding="utf-8")
    return {
        "run_id": run_id,
        "arm_id": arm_id,
        "task_id": task_id,
        "encounter_id": f"transfer-{task_id}",
        "replicate": 1,
        "output_dir": str(source),
    }


def _scores(value: float = 80.0) -> dict[str, float]:
    return {dimension: value for dimension in QUALITY_WEIGHTS}


def test_primary_quality_weights_are_exact_and_sum_to_100() -> None:
    assert QUALITY_WEIGHTS == {
        "task_satisfaction": 25,
        "semantic_fidelity": 20,
        "audience_domain_appropriateness": 15,
        "professional_usability": 15,
        "specificity": 10,
        "provenance_claim_discipline": 10,
        "authority_boundary_discipline": 5,
    }
    assert sum(QUALITY_WEIGHTS.values()) == 100


def test_quality_score_is_weighted_and_refuses_missing_or_out_of_range_dimensions() -> None:
    row = _scores(100.0)
    row["specificity"] = 0.0
    assert quality_score({"scores": row}) == 90.0

    missing = _scores()
    missing.pop("semantic_fidelity")
    with pytest.raises(EvaluationError, match="missing"):
        quality_score({"scores": missing})

    bad = _scores()
    bad["specificity"] = 101
    with pytest.raises(EvaluationError, match="0..100"):
        quality_score({"scores": bad})


def test_blind_export_uses_opaque_ids_and_contains_no_arm_task_or_sequence_metadata(tmp_path: Path) -> None:
    runs = [
        _artifact_run(tmp_path, "run-alpha", "000", "task-one"),
        _artifact_run(tmp_path, "run-beta", "111", "task-two"),
    ]
    result = blind_artifacts(runs, tmp_path / "evaluation", salt=b"blind-salt")

    blind_manifest = json.loads(Path(result["blind_manifest_path"]).read_text(encoding="utf-8"))
    private_map = json.loads(Path(result["private_map_path"]).read_text(encoding="utf-8"))
    rendered_blind = json.dumps(blind_manifest, sort_keys=True)

    assert "000" not in rendered_blind
    assert "111" not in rendered_blind
    assert "task-one" not in rendered_blind
    assert "task-two" not in rendered_blind
    assert "transfer-" not in rendered_blind
    assert blind_manifest["scores_locked"] is False
    assert len(blind_manifest["artifacts"]) == 2
    assert all(row["blind_id"].startswith("blind_") for row in blind_manifest["artifacts"])
    assert {row["arm_id"] for row in private_map["mapping"]} == {"000", "111"}

    for row in blind_manifest["artifacts"]:
        blind_dir = Path(result["blind_root"]) / row["blind_id"]
        assert (blind_dir / "artifact.txt").is_file()


def test_blind_ids_are_deterministic_for_same_salt_but_change_with_new_salt(tmp_path: Path) -> None:
    run = _artifact_run(tmp_path, "run-alpha", "111", "task-one")
    first = blind_artifacts([run], tmp_path / "eval-a", salt=b"same")
    second = blind_artifacts([run], tmp_path / "eval-b", salt=b"same")
    third = blind_artifacts([run], tmp_path / "eval-c", salt=b"different")

    assert first["blind_records"][0]["blind_id"] == second["blind_records"][0]["blind_id"]
    assert first["blind_records"][0]["blind_id"] != third["blind_records"][0]["blind_id"]


def test_confirmatory_score_sheet_requires_two_independent_human_raters_per_artifact(tmp_path: Path) -> None:
    run = _artifact_run(tmp_path, "run-alpha", "111", "task-one")
    result = blind_artifacts([run], tmp_path / "evaluation", salt=b"salt")
    manifest = json.loads(Path(result["blind_manifest_path"]).read_text(encoding="utf-8"))
    blind_id = manifest["artifacts"][0]["blind_id"]

    one_rater = [{"blind_id": blind_id, "rater_id": "human-a", "scores": _scores()}]
    with pytest.raises(EvaluationError, match="two independent"):
        validate_score_sheet(one_rater, {**manifest, "confirmatory": True})

    two_raters = [
        {"blind_id": blind_id, "rater_id": "human-a", "scores": _scores(80)},
        {"blind_id": blind_id, "rater_id": "human-b", "scores": _scores(90)},
    ]
    validated = validate_score_sheet(two_raters, {**manifest, "confirmatory": True})
    assert [row["quality_score"] for row in validated] == [80.0, 90.0]


def test_duplicate_rater_does_not_count_as_independent_confirmatory_review(tmp_path: Path) -> None:
    run = _artifact_run(tmp_path, "run-alpha", "111", "task-one")
    result = blind_artifacts([run], tmp_path / "evaluation", salt=b"salt")
    manifest = json.loads(Path(result["blind_manifest_path"]).read_text(encoding="utf-8"))
    blind_id = manifest["artifacts"][0]["blind_id"]
    rows = [
        {"blind_id": blind_id, "rater_id": "same-human", "scores": _scores()},
        {"blind_id": blind_id, "rater_id": "same-human", "scores": _scores()},
    ]
    with pytest.raises(EvaluationError, match="two independent"):
        validate_score_sheet(rows, {**manifest, "confirmatory": True})


def test_score_sheet_refuses_unknown_blind_id_or_arm_metadata(tmp_path: Path) -> None:
    run = _artifact_run(tmp_path, "run-alpha", "111", "task-one")
    result = blind_artifacts([run], tmp_path / "evaluation", salt=b"salt")
    manifest = json.loads(Path(result["blind_manifest_path"]).read_text(encoding="utf-8"))
    blind_id = manifest["artifacts"][0]["blind_id"]

    with pytest.raises(EvaluationError, match="unknown blind_id"):
        validate_score_sheet([{"blind_id": "blind_fake", "rater_id": "h", "scores": _scores()}], manifest)

    with pytest.raises(EvaluationError, match="arm metadata"):
        validate_score_sheet(
            [{"blind_id": blind_id, "rater_id": "h", "arm_id": "111", "scores": _scores()}],
            manifest,
        )


def test_repair_burden_uses_frozen_weights_deterministically() -> None:
    row = {
        "repair": {
            "human_interventions": 2,
            "prompt_reruns": 1,
            "layout_corrections": 3,
            "semantic_corrections": 2,
            "factual_provenance_corrections": 1,
            "edit_distance": 10,
            "human_minutes": 5,
        }
    }
    weights = {
        "human_interventions": 2.0,
        "prompt_reruns": 3.0,
        "layout_corrections": 1.0,
        "semantic_corrections": 2.0,
        "factual_provenance_corrections": 4.0,
        "edit_distance": 0.1,
        "human_minutes": 0.5,
    }
    assert repair_burden(row, weights) == 21.5
    assert repair_burden(row, weights) == 21.5
