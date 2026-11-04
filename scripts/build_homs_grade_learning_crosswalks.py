#!/usr/bin/env python3
"""Build source-bound educator crosswalks from the randomized HOMS grade set."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from products.homs_curriculum_spine import educator_crosswalk_markdown, learning_map_markdown

PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
ASSIGNMENTS = json.loads((PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json").read_text(encoding="utf-8"))
SET_RECEIPT = json.loads((PACK / "GRADE_EXAM_SET_RECEIPT.json").read_text(encoding="utf-8"))
OUT = PACK / "learning_crosswalks"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    rows = []
    for entry in SET_RECEIPT["results"]:
        grade = int(entry["grade"])
        grade_folder = Path(entry["job_dir"])
        receipt_path = grade_folder / "HOMS_GRADE_EXAM_RECEIPT.json"
        pack_path = grade_folder / "HOMS_GRADE_ASSESSMENT.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assessment = json.loads(pack_path.read_text(encoding="utf-8"))
        caps_path = Path(receipt["caps_source"]["path"])
        if digest(caps_path) != receipt["caps_source"]["sha256"]:
            raise ValueError(f"Grade {grade}: CAPS source hash changed")
        for key in ("exam", "memo", "json"):
            target = ROOT / receipt["assessment"][key]["path"]
            if digest(target) != receipt["assessment"][key]["sha256"]:
                raise ValueError(f"Grade {grade}: {key} hash changed")

        questions = []
        for section in assessment["sections"]:
            for item in section["questions"]:
                memo = item.get("memo") or []
                if sum(int(point["marks"]) for point in memo) != int(item["marks"]):
                    raise ValueError(f"Grade {grade} question {item.get('number')}: memo marks do not reconcile")
                questions.append({
                    "number": item.get("number"), "section": section.get("title"),
                    "question": item.get("prompt"), "marks": int(item["marks"]),
                    "bloom_level": item.get("bloom_level"),
                    "question_family": item.get("question_family"),
                    "memo": [point["point"] for point in memo],
                })
        assignment = next(row for row in ASSIGNMENTS["assignments"] if int(row["grade"]) == grade)
        if receipt["randomization_seed"] != ASSIGNMENTS["random_seed"] or assignment["subject_profile"] not in grade_folder.name:
            raise ValueError(f"Grade {grade}: subject assignment is not bound to this grade pack")
        marker = "/corpora/caps/pdf/"
        if marker not in caps_path.as_posix():
            raise ValueError(f"Grade {grade}: CAPS receipt path is outside the verified CAPS corpus")
        local_caps_path = ROOT / "corpora/caps/pdf" / caps_path.as_posix().split(marker, 1)[1]
        if not local_caps_path.is_file() or digest(local_caps_path) != receipt["caps_source"]["sha256"]:
            raise ValueError(f"Grade {grade}: no matching in-workspace CAPS source bytes")
        source_ref = local_caps_path.relative_to(ROOT).as_posix()
        spine = {
            "schema": "dio.homs.curriculum_spine.v1",
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "job_id": f"HOMS-RANDOM-GRADE-{grade:02d}-{ASSIGNMENTS['random_seed']}",
            "status": "educator_review_required",
            "authority": {"educator_approval_required": True, "classroom_release": "blocked_pending_approval", "authority_created": False},
            "curriculum": {"subject": assessment["subject"], "grade": grade, "phase": assignment["phase"], "topics": [assessment["exam_title"]], "language": "English"},
            "learning_design": {"bloom_targets": sorted({str(q["bloom_level"]) for q in questions if q.get("bloom_level")}), "memo_style": "Use the paired original marking memo; educator review required."},
            "curriculum_sources": [{"title": receipt["caps_source"]["title"], "path": source_ref, "url": receipt["caps_source"]["source_url"], "sha256": receipt["caps_source"]["sha256"], "phase": assignment["phase"], "term_focus": []}],
            "curriculum_source_status": "resolved_and_hash_recorded",
            "opportunities": {"first": {"label": assessment["exam_title"], "status": "draft_exam_and_memo", "total_marks": assessment["total_marks"], "questions": questions, "paper_path": receipt["assessment"]["exam"]["path"], "paper_sha256": receipt["assessment"]["exam"]["sha256"], "memo_path": receipt["assessment"]["memo"]["path"], "memo_sha256": receipt["assessment"]["memo"]["sha256"]}},
            "handoffs": {"learning_studio": {"enabled": True, "input_contract": "dio.homs.curriculum_spine.v1"}, "homs_assess": {"enabled": True, "paper": receipt["assessment"]["exam"]["path"], "memo": receipt["assessment"]["memo"]["path"]}},
            "alignment_boundary": "Source-bound educator planning crosswalk only. It does not claim question-level CAPS clause mapping, full curriculum coverage, or educator approval.",
        }
        folder = OUT / f"grade-{grade:02d}-{assignment['subject_profile']}"
        folder.mkdir(parents=True, exist_ok=True)
        spine_path = folder / "HOMS_CURRICULUM_SPINE.json"
        map_path = folder / "ASSESSMENT_LINKED_TEACHING_MAP.md"
        crosswalk_path = folder / "EDUCATOR_ASSESSMENT_CROSSWALK.md"
        spine_path.write_text(json.dumps(spine, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        map_text = learning_map_markdown(spine).replace(
            "> Generated from the same reviewed curriculum spine as the exam. Draft support only; educator approval remains required.",
            "> Generated from the same source-bound, educator-review-required spine as the exam. Draft planning aid only; question-level CAPS clause mapping is not asserted.",
        )
        map_path.write_text(map_text, encoding="utf-8")
        crosswalk_text = educator_crosswalk_markdown(spine)
        crosswalk_text = "> Draft educator aid: verify every suggested teaching use and CAPS scope before classroom use.\n\n" + crosswalk_text
        crosswalk_path.write_text(crosswalk_text, encoding="utf-8")
        outputs = [spine_path, map_path, crosswalk_path]
        rows.append({
            "grade": grade, "subject": assessment["subject"], "phase": assignment["phase"],
            "question_count": len(questions), "marks": assessment["total_marks"],
            "caps_source_sha256": receipt["caps_source"]["sha256"],
            "exam_sha256": receipt["assessment"]["exam"]["sha256"], "memo_sha256": receipt["assessment"]["memo"]["sha256"],
            "crosswalk_files": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in outputs],
            "alignment_boundary": spine["alignment_boundary"],
        })

    batch = {
        "schema": "dio.homs.random_grade_learning_crosswalk_batch.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "random_seed": ASSIGNMENTS["random_seed"], "grade_count": len(rows),
        "all_grade_crosswalks_created": len(rows) == 12,
        "educator_review_required": True, "classroom_release_authorized": False,
        "claim_boundary": "Twelve hash-bound educator planning crosswalks use the verified randomized exams and memos. They do not claim full CAPS coverage or approved instruction.",
        "grades": rows,
    }
    batch_path = OUT / "HOMS_GRADE_LEARNING_CROSSWALK_BATCH_RECEIPT.json"
    batch_path.write_text(json.dumps(batch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"grade_count": len(rows), "all_created": batch["all_grade_crosswalks_created"], "receipt": str(batch_path.relative_to(ROOT))}, indent=2))
    return 0 if batch["all_grade_crosswalks_created"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
