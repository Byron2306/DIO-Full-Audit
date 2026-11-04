"""Shared, provenance-carrying curriculum spine for HOMS assessment workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json


SCHEMA = "dio.homs.curriculum_spine.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_file_ref(path: Path, root: Path) -> tuple[str, str | None]:
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return "", None
    return (relative, _sha256(path) if path.is_file() else None)


def _safe_source_ref(value: Any, *, root: Path, fallback: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    path = Path(raw).expanduser()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name or fallback


def _memo_points(question: dict[str, Any]) -> list[str]:
    value = question.get("memo") or question.get("marking_points") or []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items()]
    if not isinstance(value, (list, tuple)):
        return [str(value)] if value else []
    return [str(item) for item in value if str(item).strip()]


def _question_rows(pack: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in pack.get("sections") or []:
        for question in section.get("questions") or []:
            rows.append({
                "number": str(question.get("number") or ""),
                "section": str(section.get("title") or ""),
                "question": str(question.get("question") or ""),
                "marks": int(question.get("marks") or 0),
                "bloom_level": question.get("bloom_level") or question.get("cognitive_level"),
                "question_family": question.get("question_family") or question.get("type"),
                "source_reference": question.get("source_reference") or question.get("source_id"),
                "visual_reference": question.get("visual_reference") or question.get("visual_id"),
                "memo": _memo_points(question),
            })
    for item in pack.get("source_questions") or []:
        question = item.get("question") if isinstance(item.get("question"), dict) else item
        rows.append({
            "number": str(question.get("number") or ""),
            "section": str(item.get("title") or "Source question"),
            "question": str(question.get("question") or question.get("prompt") or ""),
            "marks": int(question.get("marks") or 0),
            "bloom_level": question.get("bloom_level") or question.get("cognitive_level"),
            "question_family": question.get("question_family") or question.get("type"),
            "source_reference": question.get("source_reference") or question.get("source_id"),
            "visual_reference": question.get("visual_reference") or question.get("visual_id"),
            "memo": _memo_points(question),
        })
    for key in ("methodology_question", "essay_question"):
        question = pack.get(key)
        if isinstance(question, dict):
            rows.append({
                "number": str(question.get("number") or key),
                "section": key.replace("_", " ").title(),
                "question": str(question.get("question") or question.get("prompt") or ""),
                "marks": int(question.get("marks") or 0),
                "bloom_level": question.get("bloom_level") or question.get("cognitive_level"),
                "question_family": question.get("question_family") or question.get("type"),
                "source_reference": question.get("source_reference") or question.get("source_id"),
                "visual_reference": question.get("visual_reference") or question.get("visual_id"),
                "memo": _memo_points(question),
            })
    return rows


def _visual_assets(opportunity_dir: Path, root: Path) -> list[dict[str, Any]]:
    manifest_path = opportunity_dir / "HOMS_VISUAL_MANIFEST.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    assets: list[dict[str, Any]] = []
    for row in manifest.get("assets") or []:
        for kind in ("png", "svg"):
            raw = row.get(kind)
            if not raw:
                continue
            path = Path(str(raw)).expanduser().resolve()
            try:
                relative = path.relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            if path.is_file():
                assets.append({"title": str(row.get("title") or path.stem), "kind": kind, "path": relative, "sha256": _sha256(path)})
    return assets


def build_curriculum_spine(
    *, request: dict[str, Any], exam_set: dict[str, Any], job_id: str,
    job_dir: Path, root: Path,
) -> dict[str, Any]:
    subject = request.get("subject_profile") or {}
    grade = request.get("grade_profile") or {}
    caps = request.get("caps_context") or {}
    selected = caps.get("selected") or {}
    source_path = _safe_source_ref(selected.get("path"), root=root)
    preferences = request.get("assessment_preferences") or {}
    opportunities: dict[str, Any] = {}
    marking_assets: dict[str, Any] = {}
    for label, opportunity_key in (("first", "first_opportunity"), ("second", "second_opportunity")):
        result = exam_set.get(opportunity_key)
        if not isinstance(result, dict):
            continue
        pack = result.get("assessment_pack") if isinstance(result.get("assessment_pack"), dict) else result
        questions = _question_rows(pack)
        opportunity_dir = Path(str(result.get("opportunity_dir") or job_dir))
        pack_path = opportunity_dir / "assessment_pack.json"
        paper_path, paper_hash = _workspace_file_ref(job_dir / str(result.get("filename") or ""), root)
        memo_path, memo_hash = _workspace_file_ref(job_dir / str(result.get("memo_filename") or ""), root)
        assessment_path, assessment_hash = _workspace_file_ref(pack_path, root)
        opportunities[label] = {
            "label": result.get("opportunity_label") or label,
            "status": result.get("status") or "generated",
            "total_marks": int(result.get("total_marks") or pack.get("total_marks") or 0),
            "bloom_mark_distribution": pack.get("bloom_mark_distribution") or {},
            "duration": result.get("duration_hours") or pack.get("duration") or "",
            "questions": questions,
            "evidence_cards": [
                {key: card.get(key) for key in ("label", "type", "title", "content", "provenance", "sha256", "visual_role") if card.get(key) is not None}
                for card in pack.get("evidence_cards") or []
            ],
            "visual_assets": _visual_assets(opportunity_dir, root),
            "pack_path": assessment_path,
            "pack_sha256": assessment_hash,
            "paper_path": paper_path,
            "paper_sha256": paper_hash,
            "memo_path": memo_path,
            "memo_sha256": memo_hash,
            "visual_manifest_path": _safe_source_ref(Path(str(result.get("opportunity_dir") or job_dir)) / "HOMS_VISUAL_MANIFEST.json", root=root),
        }
        if label == "first":
            marking_assets = {
                "paper": opportunities[label]["paper_path"],
                "memo": opportunities[label]["memo_path"],
                "assessment_pack": opportunities[label]["pack_path"],
            }
    evidence_cards = list((opportunities.get("first") or {}).get("evidence_cards") or [])
    visual_blueprint = request.get("visual_blueprint") or {}
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "job_id": job_id,
        "status": "educator_review_required",
        "authority": {"educator_approval_required": True, "classroom_release": "blocked_pending_approval", "authority_created": False},
        "curriculum": {
            "subject_id": subject.get("subject_id"),
            "subject": subject.get("display_name") or request.get("subject"),
            "grade": grade.get("grade") or request.get("grade"),
            "phase": caps.get("phase") or grade.get("phase"),
            "term": request.get("term"),
            "topics": list(request.get("topics") or []),
            "topic": request.get("topic") or request.get("module_name"),
            "language": request.get("preferred_language") or request.get("language_of_assessment") or "English",
        },
        "learning_design": {
            "bloom_targets": list(preferences.get("bloom_targets") or grade.get("bloom_targets") or []),
            "caps_assessment_form_distribution": (caps.get("assessment_design_profile") or {}).get("cognitive_distribution") or {},
            "actual_bloom_mark_distribution": (opportunities.get("first") or {}).get("bloom_mark_distribution") or {},
            "question_styles": list(grade.get("question_style") or []),
            "question_families": list(subject.get("question_families") or []),
            "requested_question_types": list(preferences.get("question_types") or []),
            "reading_load": grade.get("reading_load"),
            "writing_load": grade.get("writing_load"),
            "memo_style": grade.get("memo_style"),
        },
        "curriculum_sources": [{
            "title": selected.get("title") or "CAPS curriculum source",
            "path": source_path,
            "url": selected.get("url"),
            "sha256": selected.get("sha256"),
            "phase": caps.get("phase"),
            "term_focus": caps.get("term_focus") or [],
        }] if selected else [],
        "curriculum_source_status": (
            "resolved_and_hash_recorded" if selected.get("path") and selected.get("sha256")
            else "missing_or_unbound_caps_source_requires_educator_resolution"
        ),
        "visual_blueprint": visual_blueprint,
        "visual_assets": list((opportunities.get("first") or {}).get("visual_assets") or []),
        "source_cards": evidence_cards,
        "opportunities": opportunities,
        "handoffs": {
            "learning_studio": {
                "enabled": bool(preferences.get("include_learning_studio", True)),
                "input_contract": "dio.homs.curriculum_spine.v1",
                "build_command": "python3 scripts/build_homs_learning_pack.py --request <matching-learning-request.json> --curriculum-spine HOMS_CURRICULUM_SPINE.json",
            },
            "homs_assess": {
                "enabled": True,
                "use": "Use the exact generated learner paper and memo as the assessment and marking reference.",
                **marking_assets,
            },
        },
    }


def learning_map_markdown(spine: dict[str, Any]) -> str:
    curriculum = spine.get("curriculum") or {}
    design = spine.get("learning_design") or {}
    first = (spine.get("opportunities") or {}).get("first") or {}
    lines = [
        "# HOMS Learning Studio · Exam-linked teaching map", "",
        "> Generated from the same reviewed curriculum spine as the exam. Draft support only; educator approval remains required.", "",
        f"**Subject:** {curriculum.get('subject') or 'Unspecified'}  ",
        f"**Grade / phase:** {curriculum.get('grade') or 'Unspecified'} / {curriculum.get('phase') or 'Unspecified'}  ",
        f"**Term:** {curriculum.get('term') or 'Unspecified'}  ",
        f"**Bloom targets:** {', '.join(design.get('bloom_targets') or []) or 'Not recorded'}", "",
        "## Learning sequence anchored to the assessment", "",
        "| Exam item | Prompt | Marks | Bloom / question type | Teaching use |", "|---|---|---:|---|---|",
    ]
    for question in first.get("questions") or []:
        prompt = " ".join(str(question.get("question") or "").split()).replace("|", "\\|")
        lines.append(
            f"| {question.get('number') or '—'} | {prompt[:320]} | {question.get('marks') or 0} | "
            f"{question.get('bloom_level') or 'not item-tagged'} / {question.get('question_family') or 'not item-tagged'} | "
            "Use as a retrieval check; teach prerequisite concepts before re-attempt. |"
        )
    if not first.get("questions"):
        lines.append("| No structured item metadata | Review the generated paper and attach question-level teaching objectives before use. | — | — | Human completion required. |")
    lines.extend(["", "## Sources and visuals", ""])
    for source in spine.get("curriculum_sources") or []:
        lines.append(f"- CAPS: {source.get('title') or 'source'} · SHA-256 `{source.get('sha256') or 'not recorded'}`")
    for visual in (spine.get("visual_blueprint") or {}).get("required_visuals") or []:
        lines.append(f"- {visual.get('title') or visual.get('type') or 'Visual'} — role: {visual.get('role') or 'review required'}")
    unsupported_sources = (spine.get("visual_blueprint") or {}).get("source_type_contract", {}).get("unsupported_requested_source_types") or []
    if unsupported_sources:
        lines.extend(["", "## Requested source types needing a decision", "", "These were requested but are not supported by the selected subject/assessment contract. They were not represented as included materials:", ""])
        lines.extend(f"- {item}" for item in unsupported_sources)
        lines.append("Choose a curriculum-appropriate replacement or remove the request before educator approval.")
    if spine.get("curriculum_source_status") != "resolved_and_hash_recorded":
        lines.extend(["", "**CAPS source status:** unresolved. Confirm the applicable official source and scope before approving this assessment."])
    lines.extend(["", "## Educator-only memo bridge", "", "The matching memo remains a separate teacher artifact. Use it to build worked examples and misconception checks; do not place the memo in the learner-facing exam copy.", "", "## Release gate", "", "Subject expert verifies curriculum fit, source rights, answer accuracy, visual legibility, accessibility and classroom suitability before release.", ""])
    return "\n".join(lines)


def educator_crosswalk_markdown(spine: dict[str, Any]) -> str:
    curriculum = spine.get("curriculum") or {}
    first = (spine.get("opportunities") or {}).get("first") or {}
    lines = [
        "# HOMS Educator · Exam to Learning Crosswalk", "",
        f"**{curriculum.get('subject') or 'Subject'} · Grade {curriculum.get('grade') or 'unspecified'} · Term {curriculum.get('term') or 'unspecified'}**", "",
        "This educator-only file maps the generated memo to teach-back and misconception checks. The learner guide receives prompts only; keep this file and the memorandum with educators.", "",
    ]
    for question in first.get("questions") or []:
        lines.extend([
            f"## {question.get('number') or 'Item'} · {question.get('marks') or 0} marks", "",
            f"**Question:** {question.get('question') or 'Prompt not captured in structured metadata.'}", "",
            f"**Bloom / family:** {question.get('bloom_level') or 'not item-tagged'} / {question.get('question_family') or 'not item-tagged'}", "",
            "**Memo points (educator use):**",
        ])
        lines.extend([f"- {item}" for item in question.get("memo") or []] or ["- See the separate signed-off memo; no item-level memo points were captured."])
        lines.append("")
    lines.extend(["## Review", "", "Confirm that the teaching sequence prepares learners for the assessment without teaching to a leaked answer key. Recheck memo accuracy and source permissions before classroom use.", ""])
    return "\n".join(lines)
