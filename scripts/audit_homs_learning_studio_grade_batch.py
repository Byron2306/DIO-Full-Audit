#!/usr/bin/env python3
"""Audit source and rendered artifact bindings for HOMS Learning Studio grades."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
BATCH_ROOT = ROOT / "deliverables/homs_learning_studio_grade_batch_20261104_V31"
BATCH_PATH = BATCH_ROOT / "HOMS_LEARNING_STUDIO_GRADE_BATCH_RECEIPT.json"
CROSSWALK_PATH = PACK / "learning_crosswalks/HOMS_GRADE_LEARNING_CROSSWALK_BATCH_RECEIPT.json"
ASSIGNMENTS_PATH = PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_LEARNING_STUDIO_GRADE_BATCH_AUDIT_20261104_V31.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    crosswalks = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    assignment_doc = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    assignments = {int(row["grade"]): row for row in assignment_doc["assignments"]}
    crosswalks_by_grade = {int(row["grade"]): row for row in crosswalks["grades"]}
    if len(batch.get("grades", [])) != 12 or len(assignments) != 12 or len(crosswalks_by_grade) != 12:
        raise ValueError("batch, assignment or source crosswalk coverage is not 12 grades")
    grades = []
    all_checks = True
    for row in sorted(batch["grades"], key=lambda value: int(value["grade"])):
        grade = int(row["grade"])
        grade_dir = BATCH_ROOT / f"grade-{grade:02d}"
        crosswalk = crosswalks_by_grade[grade]
        assignment = assignments[grade]
        spine_path = ROOT / crosswalk["crosswalk_files"][0]["path"]
        spine_candidates = [x for x in crosswalk["crosswalk_files"] if x["path"].endswith("HOMS_CURRICULUM_SPINE.json")]
        if len(spine_candidates) != 1:
            raise ValueError(f"Grade {grade}: source crosswalk must name exactly one spine")
        spine_path = ROOT / spine_candidates[0]["path"]
        spine = json.loads(spine_path.read_text(encoding="utf-8"))
        first = spine["opportunities"]["first"]
        curriculum = spine["curriculum"]
        receipt_path = PACK / "grades" / spine_path.parent.name.replace("grade-", "grade-") / "HOMS_GRADE_EXAM_RECEIPT.json"
        # The crosswalk spine binds the exact original paper/memo paths; source
        # grade receipts are located by their declared assessment path instead.
        exam_path, memo_path = ROOT / first["paper_path"], ROOT / first["memo_path"]
        grade_receipt_path = exam_path.parent / "HOMS_GRADE_EXAM_RECEIPT.json"
        grade_receipt = json.loads(grade_receipt_path.read_text(encoding="utf-8"))
        caps_ok = True
        caps_checks = []
        for source in spine.get("curriculum_sources") or []:
            source_path = ROOT / str(source.get("path") or "")
            ok = source_path.is_file() and sha(source_path) == source.get("sha256")
            caps_checks.append({"path": source.get("path"), "expected_sha256": source.get("sha256"), "actual_sha256": sha(source_path) if source_path.is_file() else None, "passed": ok})
            caps_ok = caps_ok and ok
        crosswalk_checks = []
        for source_file in crosswalk.get("crosswalk_files") or []:
            path = ROOT / source_file["path"]
            ok = path.is_file() and sha(path) == source_file.get("sha256")
            crosswalk_checks.append({"path": source_file["path"], "passed": ok})
        output_checks = []
        for file_row in row.get("files") or []:
            path = BATCH_ROOT / file_row["path"]
            output_checks.append({"path": file_row["path"], "expected_sha256": file_row["sha256"], "actual_sha256": sha(path) if path.is_file() else None, "passed": path.is_file() and sha(path) == file_row["sha256"]})
        manifest_path = grade_dir / "HOMS_LEARNING_STUDIO_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validation = json.loads((grade_dir / "HOMS_LEARNING_STUDIO_VALIDATION.json").read_text(encoding="utf-8"))
        planner = manifest.get("educator_planner") or {}
        planner_path = grade_dir / str(planner.get("path") or "")
        planner_receipt_matches = (
            planner_path.is_file()
            and sha(planner_path) == planner.get("sha256")
            and planner.get("source_spine_sha256") == sha(spine_path)
            and planner.get("question_count") == len(first.get("questions") or [])
            and planner.get("planning_fields_per_question") == 7
            and planner.get("local_draft_storage") is True
            and planner.get("external_processing") is False
            and planner.get("approval_recorded") is False
            and planner.get("classroom_release_authorized") is False
            and validation.get("interactive_educator_planner", {}).get("all_fields_initially_blank") is True
        )
        pictora = manifest.get("pictora_visual") or {}
        pictora_asset = Path(str(pictora.get("asset") or ""))
        pictora_receipt = Path(str(pictora.get("receipt") or ""))
        pictora_ok = (pictora.get("state") == "ATTACHED_FOR_REVIEW" and pictora_asset.is_file() and pictora_receipt.is_file())
        actual_visual_paths = {
            str(asset.get("path") or asset.get("asset") or "")
            for asset in manifest.get("visual_assets") or [] if isinstance(asset, dict)
        }
        if pictora_ok:
            actual_visual_paths.add(str(pictora_asset))
        checks = {
            "crosswalk_receipt_matches_randomization_seed": crosswalks.get("random_seed") == assignment_doc.get("random_seed"),
            "grade_subject_matches_random_assignment": assignment.get("subject_profile") in exam_path.parent.name and int(curriculum.get("grade")) == grade and str(curriculum.get("subject")) == str(row.get("subject")),
            "source_spine_hash_matches_both_receipts": sha(spine_path) == spine_candidates[0].get("sha256") == row.get("source_spine_sha256"),
            "source_exam_hash_matches_spine_and_exam_receipt": exam_path.is_file() and sha(exam_path) == first.get("paper_sha256") == row.get("source_exam_sha256") and sha(exam_path) == (grade_receipt.get("assessment", {}).get("exam", {}).get("sha256")),
            "source_memo_hash_matches_spine_and_exam_receipt": memo_path.is_file() and sha(memo_path) == first.get("memo_sha256") == row.get("source_memo_sha256") and sha(memo_path) == (grade_receipt.get("assessment", {}).get("memo", {}).get("sha256")),
            "source_caps_hashes_verified": caps_ok,
            "source_crosswalk_artifacts_verified": all(x["passed"] for x in crosswalk_checks),
            "rendered_file_inventory_verified": len(output_checks) > 0 and all(x["passed"] for x in output_checks),
            "review_gate_and_pictora_visual_present": validation.get("educator_approval_required") is True and validation.get("classroom_release") == "blocked_pending_approval" and pictora_ok,
            "visual_count_matches_attached_assets": row.get("visual_count") == len(actual_visual_paths) and len(actual_visual_paths) >= 1,
            "exam_and_memo_copied_without_change": (grade_dir / "documents/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_PAPER.docx").is_file() and sha(grade_dir / "documents/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_PAPER.docx") == sha(exam_path) and (grade_dir / "documents/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_MEMO.docx").is_file() and sha(grade_dir / "documents/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_MEMO.docx") == sha(memo_path),
            "interactive_educator_planner_source_bound_and_held": planner_receipt_matches,
        }
        passed = all(checks.values())
        all_checks = all_checks and passed
        grades.append({"grade": grade, "subject": row["subject"], "checks": checks, "passed": passed, "caps_sources": caps_checks, "crosswalk_files": crosswalk_checks, "rendered_outputs": output_checks})
    result = {
        "schema": "dio.homs.learning_studio.grade_batch_audit.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_batch_receipt_sha256": sha(BATCH_PATH),
        "random_subject_assignments_sha256": sha(ASSIGNMENTS_PATH),
        "grade_count": len(grades), "passed_grade_count": sum(row["passed"] for row in grades),
        "all_grade_sources_and_outputs_verified": all_checks,
        "educator_approval_required": True, "classroom_release_authorized": False,
        "grades": grades,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed_grade_count": result["passed_grade_count"], "grade_count": result["grade_count"], "all_verified": all_checks, "audit": OUT.relative_to(ROOT).as_posix()}, indent=2))
    return 0 if all_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
