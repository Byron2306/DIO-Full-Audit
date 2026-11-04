#!/usr/bin/env python3
"""Build held Learning Studio packs from the twelve randomized grade spines."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_homs_learning_studio_from_spine import build, load_spine

PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
CROSSWALKS = PACK / "learning_crosswalks"
CROSSWALK_RECEIPT = CROSSWALKS / "HOMS_GRADE_LEARNING_CROSSWALK_BATCH_RECEIPT.json"
OUT = ROOT / "deliverables/homs_learning_studio_grade_batch_20261104_V31"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    batch = json.loads(CROSSWALK_RECEIPT.read_text(encoding="utf-8"))
    if batch.get("grade_count") != 12 or batch.get("all_grade_crosswalks_created") is not True:
        raise ValueError("Learning Studio requires the complete twelve-grade source crosswalk receipt")
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be empty: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    seen = set()
    for item in sorted(batch["grades"], key=lambda row: int(row["grade"])):
        grade = int(item["grade"])
        if grade in seen or not 1 <= grade <= 12:
            raise ValueError(f"invalid or duplicate grade in source crosswalk receipt: {grade}")
        seen.add(grade)
        spine_entry = next((file for file in item["crosswalk_files"] if file["path"].endswith("HOMS_CURRICULUM_SPINE.json")), None)
        if not spine_entry:
            raise ValueError(f"Grade {grade}: crosswalk receipt does not bind a curriculum spine")
        spine_path = ROOT / spine_entry["path"]
        if not spine_path.is_file() or sha(spine_path) != spine_entry["sha256"]:
            raise ValueError(f"Grade {grade}: curriculum spine hash mismatch")
        spine = load_spine(spine_path)
        curriculum = spine["curriculum"]
        first = spine["opportunities"]["first"]
        if int(curriculum["grade"]) != grade or str(curriculum["subject"]) != str(item["subject"]):
            raise ValueError(f"Grade {grade}: spine subject/grade does not match the batch receipt")
        for role in ("paper", "memo"):
            path = ROOT / str(first.get(f"{role}_path") or "")
            if not path.is_file() or sha(path) != first.get(f"{role}_sha256"):
                raise ValueError(f"Grade {grade}: source {role} missing or hash mismatch")
        grade_out = OUT / f"grade-{grade:02d}"
        result = build(spine_path, grade_out)
        manifest_path = grade_out / "HOMS_LEARNING_STUDIO_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validation_path = grade_out / "HOMS_LEARNING_STUDIO_VALIDATION.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "educator_review_required" or validation.get("classroom_release") != "blocked_pending_approval":
            raise ValueError(f"Grade {grade}: Learning Studio release gate drifted")
        if validation.get("spine_sha256") != sha(spine_path) or validation.get("source_hashes_verified") is not True:
            raise ValueError(f"Grade {grade}: output does not bind the verified source spine")
        planner = manifest.get("educator_planner") or {}
        planner_path = grade_out / str(planner.get("path") or "")
        planner_validation = validation.get("interactive_educator_planner") or {}
        if (not planner_path.is_file() or sha(planner_path) != planner.get("sha256")
                or planner.get("source_spine_sha256") != sha(spine_path)
                or planner.get("question_count") != len(first.get("questions") or [])
                or planner.get("planning_fields_per_question") != 7
                or planner.get("external_processing") is not False
                or planner.get("approval_recorded") is not False
                or planner.get("classroom_release_authorized") is not False
                or planner_validation.get("all_fields_initially_blank") is not True
                or planner_validation.get("classroom_release_authorized") is not False):
            raise ValueError(f"Grade {grade}: interactive educator planner is missing, unbound, or crossed its review gate")
        pictora = manifest.get("pictora_visual") or {}
        visual_paths = {
            str(asset.get("path") or asset.get("asset") or "")
            for asset in manifest.get("visual_assets") or [] if isinstance(asset, dict)
        }
        pictora_asset = Path(str(pictora.get("asset") or ""))
        if pictora.get("state") == "ATTACHED_FOR_REVIEW" and pictora_asset.is_file():
            visual_paths.add(str(pictora_asset))
        elif pictora.get("state") == "ATTACHED_FOR_REVIEW":
            raise ValueError(f"Grade {grade}: Pictora reports an attached visual but its asset is missing")
        files = []
        for path in sorted(grade_out.rglob("*")):
            if path.is_file():
                files.append({"path": path.relative_to(OUT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
        rows.append({
            "grade": grade, "subject": item["subject"], "phase": item["phase"],
            "source_spine_path": spine_entry["path"], "source_spine_sha256": sha(spine_path),
            "source_exam_sha256": first["paper_sha256"], "source_memo_sha256": first["memo_sha256"],
            "learning_studio_status": result["status"], "question_count": result["questions"],
            "generated_guide_count": 2, "source_exam_and_memo_copied": True, "pdf_count": result["pdfs"],
            "educator_planner_path": planner["path"], "educator_planner_sha256": planner["sha256"],
            "educator_planner_question_count": planner["question_count"],
            "educator_planner_fields_per_question": planner["planning_fields_per_question"],
            "video_bundle_status": manifest.get("video_bundle", {}).get("status"),
            "visual_count": len(visual_paths),
            "pictora_visual_status": pictora.get("state"),
            "educator_approval_required": validation["educator_approval_required"],
            "classroom_release": validation["classroom_release"],
            "files": files,
        })
    if seen != set(range(1, 13)):
        raise ValueError(f"incomplete grade coverage: {sorted(seen)}")
    receipt = {
        "schema": "dio.homs.learning_studio.random_grade_batch.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_crosswalk_receipt": {"path": CROSSWALK_RECEIPT.relative_to(ROOT).as_posix(), "sha256": sha(CROSSWALK_RECEIPT)},
        "grade_count": len(rows), "all_grades_built": len(rows) == 12,
        "educator_review_required": True, "classroom_release_authorized": False,
        "claim_boundary": "Twelve learner and educator draft packs are generated from the randomized exam/memo spines and source-bound CAPS receipts. This is not full curriculum coverage, educator approval, or classroom release. Video lessons attach only where an exact reviewed asset bundle exists.",
        "grades": rows,
    }
    target = OUT / "HOMS_LEARNING_STUDIO_GRADE_BATCH_RECEIPT.json"
    target.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"grade_count": len(rows), "all_grades_built": receipt["all_grades_built"], "output": target.relative_to(ROOT).as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
