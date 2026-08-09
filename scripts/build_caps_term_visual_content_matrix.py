#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_caps_visual_asset_packs import (  # noqa: E402
    DEFAULT_OUT as DEFAULT_ASSET_OUT,
    GRADES_BY_PHASE,
    is_real_subject_profile,
    resolver_subject_id,
    slug,
    subject_content_terms,
    theme_line_score,
    theme_quality,
    topic_from_theme_lines,
)
from resolve_caps_source import PHASE_BY_GRADE, extract_text, load_manifest, resolve as resolve_caps  # noqa: E402
from run_hymark_exam_builder import (  # noqa: E402
    DEFAULT_CAPS_ASSESSMENT_DESIGN,
    DEFAULT_CAPS_MATRIX,
    DEFAULT_CAPS_MANIFEST,
    DEFAULT_GRADE_LADDER,
    build_visual_blueprint,
    extract_term_theme_lines,
    load_grade_profile,
    synthesize_subject_profile,
)

DEFAULT_OUT = ROOT / "deliverables" / "homs_caps_term_visual_content_matrix"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def profile_grades(profile: dict[str, Any], grade_filter: int) -> list[int]:
    grades = GRADES_BY_PHASE.get(str(profile.get("phase") or ""), [])
    if grade_filter:
        return [grade for grade in grades if grade == grade_filter]
    return grades


def resolve_and_extract(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    grade: int,
    preferred_language: str,
    text_cache: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str, str | None]:
    subject_id = resolver_subject_id(profile)
    candidates = resolve_caps(manifest, subject_id, grade, preferred_language, include_policy=False)
    selected = candidates[0] if candidates else None
    if not selected or not selected.get("path"):
        return candidates, selected, "", None
    path = str(selected["path"])
    if path not in text_cache:
        try:
            text_cache[path] = extract_text(Path(path), 220000)
        except Exception as exc:
            text_cache[path] = ""
            return candidates, selected, "", str(exc)
    return candidates, selected, text_cache[path], None


def build_row(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    grade: int,
    term: int,
    preferred_language: str,
    grade_ladder: Path,
    text_cache: dict[str, str],
    matrix_by_sha: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    subject = str(profile.get("subject") or "Subject")
    family = str(profile.get("assessment_family") or "structured_test_or_task")
    candidates, selected, full_text, extraction_error = resolve_and_extract(manifest, profile, grade, preferred_language, text_cache)
    term_lines = extract_term_theme_lines(full_text, grade, term)
    quality = theme_quality(subject, family, term_lines)
    topics = topic_from_theme_lines(subject, grade, term, term_lines)
    subject_profile = synthesize_subject_profile(subject)
    subject_profile["subject_id"] = resolver_subject_id(profile)
    grade_profile = load_grade_profile(grade, grade_ladder)
    caps_context = {
        "schema": "knowedge.homs_caps_context.v1",
        "enabled": True,
        "subject_id": subject_profile["subject_id"],
        "subject": subject,
        "grade": grade,
        "phase": PHASE_BY_GRADE[grade],
        "preferred_language": preferred_language,
        "candidate_count": len(candidates),
        "selected": selected,
        "assessment_ontology_profile": {
            "profile_id": profile.get("profile_id"),
            "subject": subject,
            "phase": profile.get("phase"),
            "assessment_family": family,
        },
        "assessment_design_profile": profile,
        "assessment_matrix_row": source_matrix_context(selected, matrix_by_sha),
        "extracted_excerpt": full_text[:3500],
        "full_text": full_text,
        "extraction_error": extraction_error,
    }
    request = {
        "module_code": slug(subject).upper()[:8] or "CAPS",
        "module_name": f"{subject} Grade {grade} Term {term}",
        "topics": topics,
        "methodology_topic": topics[0] if topics else "",
        "essay_topic": topics[-1] if topics else "",
        "term": str(term),
        "total_marks": 25,
        "duration_hours": 1,
        "subject_profile": {key: value for key, value in subject_profile.items() if not key.startswith("_")},
        "grade_profile": {key: value for key, value in grade_profile.items() if not key.startswith("_")},
        "caps_context": caps_context,
    }
    blueprint = build_visual_blueprint(request)
    blueprint["theme_quality"] = quality
    content_ready = bool(selected) and quality["render_allowed"] and bool(quality["content_lines"])
    status = "content_ready" if content_ready else "needs_curation"
    if not selected:
        status = "missing_caps_source"
    elif extraction_error:
        status = "extract_failed"
    return {
        "profile_id": profile.get("profile_id"),
        "subject": subject,
        "subject_id": resolver_subject_id(profile),
        "grade": grade,
        "term": term,
        "phase": PHASE_BY_GRADE[grade],
        "assessment_family": family,
        "render_shell": profile.get("render_shell"),
        "status": status,
        "render_eligible": status == "content_ready",
        "candidate_count": len(candidates),
        "caps_source": (selected or {}).get("title"),
        "caps_path": (selected or {}).get("path"),
        "extraction_error": extraction_error,
        "content_terms_used": subject_content_terms(subject, family),
        "caps_theme_candidates": term_lines,
        "content_lines": quality["content_lines"],
        "admin_or_noise_lines": quality["admin_lines"],
        "theme_confidence": quality["confidence"],
        "topic_focus": topics,
        "topic_scores": [{"line": line, "score": theme_line_score(subject, line)} for line in topics],
        "required_visuals": blueprint.get("required_visuals", []),
        "visual_kinds": [item.get("visual_kind") for item in blueprint.get("required_visuals", [])],
        "source_type_contract": blueprint.get("source_type_contract", {}),
        "source_types": (blueprint.get("source_type_contract") or {}).get("source_types", []),
    }


def source_matrix_context(selected: dict[str, Any] | None, matrix_by_sha: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not selected:
        return None
    row = matrix_by_sha.get(str(selected.get("sha256") or ""))
    if not row:
        return None
    return {
        "recommended_blueprint": row.get("recommended_blueprint"),
        "subject_family": row.get("subject_family"),
        "language_guess": row.get("language_guess"),
        "assessment_flags": row.get("assessment_flags"),
        "assessment_keyword_counts": row.get("assessment_keyword_counts"),
        "signals_source_based": row.get("signals_source_based"),
        "signals_essay_or_extended_response": row.get("signals_essay_or_extended_response"),
        "signals_case_study": row.get("signals_case_study"),
        "signals_data_graph_diagram": row.get("signals_data_graph_diagram"),
        "signals_practical_investigation": row.get("signals_practical_investigation"),
        "signals_project_or_sba": row.get("signals_project_or_sba"),
        "signals_oral_or_performance": row.get("signals_oral_or_performance"),
        "signals_calculation_problem": row.get("signals_calculation_problem"),
        "signals_formal_test_or_exam": row.get("signals_formal_test_or_exam"),
    }


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> Path:
    status_counts = Counter(row["status"] for row in rows)
    family_counts = Counter(row["assessment_family"] for row in rows)
    confidence_counts = Counter(row["theme_confidence"] for row in rows)
    payload = {
        "schema": "knowedge.homs_caps_term_visual_content_matrix.v1",
        "created_at": utc_now(),
        "row_count": len(rows),
        "skipped_count": len(skipped),
        "status_counts": dict(sorted(status_counts.items())),
        "assessment_family_counts": dict(sorted(family_counts.items())),
        "theme_confidence_counts": dict(sorted(confidence_counts.items())),
        "rows": rows,
        "skipped": skipped,
        "asset_pack_out": str(DEFAULT_ASSET_OUT),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "HOMS_CAPS_TERM_VISUAL_CONTENT_MATRIX.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    ready_path = out_dir / "render_eligible_rows.json"
    ready_path.write_text(json.dumps([row for row in rows if row["render_eligible"]], indent=2), encoding="utf-8")
    curation_path = out_dir / "needs_curation_rows.json"
    curation_path.write_text(json.dumps([row for row in rows if not row["render_eligible"]], indent=2), encoding="utf-8")
    lines = [
        "# HOMS CAPS Term Visual Content Matrix",
        "",
        f"Created: {payload['created_at']}",
        f"Rows: {len(rows)}",
        f"Render eligible: {status_counts.get('content_ready', 0)}",
        f"Needs curation: {len(rows) - status_counts.get('content_ready', 0)}",
        "",
        "## Status Counts",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## First Render-Eligible Rows"])
    for row in [item for item in rows if item["render_eligible"]][:30]:
        lines.append(f"- {row['profile_id']} / Grade {row['grade']} / Term {row['term']}: {row['topic_focus'][0] if row['topic_focus'] else 'no topic'}")
    lines.extend(["", "## First Curation Rows"])
    for row in [item for item in rows if not item["render_eligible"]][:30]:
        lines.append(f"- {row['profile_id']} / Grade {row['grade']} / Term {row['term']} / {row['status']}")
    (out_dir / "HOMS_CAPS_TERM_VISUAL_CONTENT_MATRIX.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CAPS term/theme content matrix before rendering HOMS visual packs.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--caps-manifest", default=str(DEFAULT_CAPS_MANIFEST))
    parser.add_argument("--caps-matrix", default=str(DEFAULT_CAPS_MATRIX))
    parser.add_argument("--caps-assessment-design", default=str(DEFAULT_CAPS_ASSESSMENT_DESIGN))
    parser.add_argument("--grade-ladder", default=str(DEFAULT_GRADE_LADDER))
    parser.add_argument("--preferred-language", default="English")
    parser.add_argument("--profile", default="")
    parser.add_argument("--grade", type=int, default=0)
    parser.add_argument("--term", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    manifest = load_manifest(Path(args.caps_manifest).expanduser().resolve())
    caps_matrix_path = Path(args.caps_matrix).expanduser().resolve()
    caps_matrix = json.loads(caps_matrix_path.read_text(encoding="utf-8")) if caps_matrix_path.exists() else {}
    matrix_by_sha = {str(row.get("sha256") or ""): row for row in caps_matrix.get("rows") or [] if row.get("sha256")}
    design_payload = json.loads(Path(args.caps_assessment_design).expanduser().resolve().read_text(encoding="utf-8"))
    grade_ladder = Path(args.grade_ladder).expanduser().resolve()
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    text_cache: dict[str, str] = {}

    for profile in design_payload.get("profiles") or []:
        if args.profile and profile.get("profile_id") != args.profile:
            continue
        if not is_real_subject_profile(profile):
            skipped.append({"profile_id": profile.get("profile_id"), "reason": "support_or_guideline_profile"})
            continue
        terms = [args.term] if args.term else [1, 2, 3, 4]
        for grade in profile_grades(profile, args.grade):
            for term in terms:
                if args.limit and len(rows) >= args.limit:
                    break
                rows.append(build_row(manifest, profile, grade, term, args.preferred_language, grade_ladder, text_cache, matrix_by_sha))
            if args.limit and len(rows) >= args.limit:
                break
        if args.limit and len(rows) >= args.limit:
            break

    index = write_outputs(Path(args.out).expanduser().resolve(), rows, skipped)
    print(
        json.dumps(
            {
                "status": "completed",
                "rows": len(rows),
                "render_eligible": sum(1 for row in rows if row["render_eligible"]),
                "needs_curation": sum(1 for row in rows if not row["render_eligible"]),
                "out": str(index),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
