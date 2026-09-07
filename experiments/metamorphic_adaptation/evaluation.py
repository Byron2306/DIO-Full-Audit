from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


QUALITY_WEIGHTS: dict[str, int] = {
    "task_satisfaction": 25,
    "semantic_fidelity": 20,
    "audience_domain_appropriateness": 15,
    "professional_usability": 15,
    "specificity": 10,
    "provenance_claim_discipline": 10,
    "authority_boundary_discipline": 5,
}


class EvaluationError(RuntimeError):
    """Raised when blindness or evaluator custody would be compromised."""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _blind_id(run_id: str, salt: bytes) -> str:
    if not salt:
        raise EvaluationError("blind salt must be non-empty")
    digest = hashlib.sha256(bytes(salt) + b"\x00" + run_id.encode("utf-8")).hexdigest()
    return "blind_" + digest[:24]


def _declared_artifact_paths(run: dict[str, Any], source: Path) -> list[Path]:
    command = run.get("command")
    if isinstance(command, dict) and isinstance(command.get("artifacts"), list):
        paths: list[Path] = []
        for row in command["artifacts"]:
            if not isinstance(row, dict):
                continue
            rel = str(row.get("path") or "")
            if not rel:
                continue
            target = (source / rel).resolve()
            try:
                target.relative_to(source.resolve())
            except ValueError as exc:
                raise EvaluationError(f"declared artifact escapes output directory: {rel}") from exc
            if target.is_file():
                paths.append(target)
        return sorted(set(paths))

    # Fixture/pilot fallback. Internal experiment custody files are never exposed.
    excluded_names = {"encounter_receipt.json", "prepare_receipt.json"}
    return sorted(
        path for path in source.rglob("*")
        if path.is_file() and path.name not in excluded_names and not path.name.startswith("seal_")
    )


def blind_artifacts(
    run_records: list[dict[str, Any]],
    output_dir: Path,
    salt: bytes,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    blind_root = output_dir / "blind"
    private_root = output_dir / "private"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    blind_root.mkdir(parents=True, exist_ok=True)
    private_root.mkdir(parents=True, exist_ok=True)

    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for run in run_records:
        run_id = str(run.get("run_id") or "")
        if not run_id:
            # Encounter receipts predate an explicit run_id. Construct a custody-only identity.
            run_id = "|".join(
                str(run.get(key) or "")
                for key in ("experiment_id", "encounter_id", "arm_id", "replicate")
            )
        if not run_id.strip("|"):
            raise EvaluationError("run record lacks a stable identity")
        blind_id = _blind_id(run_id, salt)
        if blind_id in seen_ids:
            raise EvaluationError(f"duplicate blind identity: {blind_id}")
        seen_ids.add(blind_id)

        source = Path(str(run.get("output_dir") or "")).resolve()
        if not source.is_dir():
            raise EvaluationError(f"run output directory missing: {source}")
        target_root = blind_root / blind_id
        target_root.mkdir(parents=True, exist_ok=True)

        files: list[dict[str, Any]] = []
        for artifact in _declared_artifact_paths(run, source):
            rel = artifact.relative_to(source)
            destination = target_root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact, destination)
            files.append(
                {
                    "path": rel.as_posix(),
                    "sha256": _sha256_file(destination),
                    "size": destination.stat().st_size,
                }
            )

        public_rows.append({"blind_id": blind_id, "files": files})
        private_rows.append(
            {
                "blind_id": blind_id,
                "run_id": run_id,
                "arm_id": run.get("arm_id"),
                "task_id": run.get("task_id"),
                "encounter_id": run.get("encounter_id"),
                "replicate": run.get("replicate"),
            }
        )

    public_rows.sort(key=lambda row: row["blind_id"])
    private_rows.sort(key=lambda row: row["blind_id"])
    public_manifest = {
        "schema": "dio.metamorphic_adaptation.blind_manifest.v1",
        "scores_locked": False,
        "artifacts": public_rows,
    }
    private_map = {
        "schema": "dio.metamorphic_adaptation.private_blind_map.v1",
        "mapping": private_rows,
    }
    blind_manifest_path = output_dir / "blind_manifest.json"
    private_map_path = private_root / "blind_map.json"
    _write_json(blind_manifest_path, public_manifest)
    _write_json(private_map_path, private_map)
    return {
        "blind_root": str(blind_root),
        "blind_manifest_path": str(blind_manifest_path),
        "private_map_path": str(private_map_path),
        "blind_records": public_rows,
    }


def quality_score(row: dict[str, Any]) -> float:
    scores = row.get("scores")
    if not isinstance(scores, dict):
        raise EvaluationError("score row missing scores object")
    missing = set(QUALITY_WEIGHTS).difference(scores)
    extra = set(scores).difference(QUALITY_WEIGHTS)
    if missing:
        raise EvaluationError(f"score row missing dimensions: {sorted(missing)}")
    if extra:
        raise EvaluationError(f"score row contains unknown dimensions: {sorted(extra)}")

    total = 0.0
    for dimension, weight in QUALITY_WEIGHTS.items():
        value = scores[dimension]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 100:
            raise EvaluationError(f"score dimension {dimension} must be within 0..100")
        total += float(value) * weight
    return round(total / 100.0, 6)


def validate_score_sheet(
    score_rows: list[dict[str, Any]],
    blind_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    allowed_ids = {
        str(row.get("blind_id") or "")
        for row in blind_manifest.get("artifacts") or []
        if isinstance(row, dict)
    }
    if not allowed_ids:
        raise EvaluationError("blind manifest contains no artifact identities")

    prohibited_metadata = {
        "arm_id",
        "condition",
        "state_classes",
        "encounter_id",
        "generation_order",
        "baseline_or_adapted",
    }
    validated: list[dict[str, Any]] = []
    raters_by_blind_id: dict[str, set[str]] = {blind_id: set() for blind_id in allowed_ids}

    for raw in score_rows:
        if not isinstance(raw, dict):
            raise EvaluationError("score sheet rows must be objects")
        exposed = prohibited_metadata.intersection(raw)
        if exposed:
            raise EvaluationError(f"score sheet contains forbidden arm metadata: {sorted(exposed)}")
        blind_id = str(raw.get("blind_id") or "")
        if blind_id not in allowed_ids:
            raise EvaluationError(f"unknown blind_id: {blind_id}")
        rater_id = str(raw.get("rater_id") or "")
        if not rater_id:
            raise EvaluationError("score row missing rater_id")
        raters_by_blind_id[blind_id].add(rater_id)
        row = dict(raw)
        row["quality_score"] = quality_score(row)
        validated.append(row)

    if bool(blind_manifest.get("confirmatory")):
        for blind_id in sorted(allowed_ids):
            if len(raters_by_blind_id.get(blind_id, set())) < 2:
                raise EvaluationError(f"confirmatory evaluation requires two independent human raters for {blind_id}")
    return validated


def repair_burden(row: dict[str, Any], weights: dict[str, float]) -> float:
    repair = row.get("repair")
    if not isinstance(repair, dict):
        raise EvaluationError("repair row missing repair object")
    total = 0.0
    for key, weight in weights.items():
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or float(weight) < 0:
            raise EvaluationError(f"repair weight must be non-negative: {key}")
        value = repair.get(key, 0)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0:
            raise EvaluationError(f"repair value must be non-negative: {key}")
        total += float(value) * float(weight)
    return round(total, 6)
