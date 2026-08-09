#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_homs_design_law import DEFAULT_DESIGN_LAW, build_assets, load_json  # noqa: E402
from resolve_caps_source import PHASE_BY_GRADE, extract_text, load_manifest, resolve as resolve_caps  # noqa: E402
from run_hymark_exam_builder import (  # noqa: E402
    DEFAULT_CAPS_ASSESSMENT_DESIGN,
    DEFAULT_CAPS_MATRIX,
    DEFAULT_CAPS_MANIFEST,
    DEFAULT_GRADE_LADDER,
    build_visual_blueprint,
    extract_term_theme_lines,
    load_grade_profile,
    normalized_name,
    synthesize_subject_profile,
)

DEFAULT_OUT = ROOT / "deliverables" / "homs_caps_visual_asset_packs"

GRADES_BY_PHASE = {
    "foundation_grade_r_3": [1, 2, 3],
    "intermediate_grade_4_6": [4, 5, 6],
    "senior_grade_7_9": [7, 8, 9],
    "fet_grade_10_12": [10, 11, 12],
}

ADMIN_THEME_TERMS = {
    "assessment",
    "programme of assessment",
    "formal assessment",
    "informal assessment",
    "formal and informal",
    "recording and reporting",
    "moderation",
    "curriculum and assessment",
    "time allocation",
    "contents",
    "section",
    "overview",
    "policy statement",
    "caps ",
}

CONTENT_THEME_TERMS = {
    "accounting": ["ledger", "journal", "cash", "assets", "liabilities", "accounts", "vat", "inventory", "budget"],
    "business": ["business", "market", "entrepreneur", "management", "consumer", "stakeholder", "strategy", "legislation"],
    "economics": ["economy", "market", "demand", "supply", "inflation", "cycle", "growth", "sector"],
    "geography": ["atmosphere", "weather", "climate", "synoptic", "geomorphology", "settlement", "population", "water", "earth", "rock", "plate", "tectonic", "volcano", "earthquake", "folding", "faulting", "map", "gis", "river", "urban", "rural", "economic geography"],
    "history": ["revolution", "colonial", "apartheid", "war", "resistance", "nationalism", "source", "civil", "cold war"],
    "life sciences": ["cells", "plant", "animal", "photosynthesis", "genetics", "evolution", "biodiversity", "human", "ecosystem"],
    "natural sciences": ["matter", "energy", "planet", "life", "earth", "systems", "investigation", "forces", "electric"],
    "physical sciences": ["matter", "chemical", "electric", "motion", "force", "energy", "waves", "reaction"],
    "mathematics": ["number", "pattern", "function", "algebra", "geometry", "measurement", "data", "probability", "graph"],
    "mathematical literacy": ["finance", "measurement", "maps", "plans", "data", "tariff", "tax", "interest"],
    "language": ["listening", "speaking", "reading", "viewing", "writing", "presenting", "language structures", "comprehension"],
    "coding": ["algorithm", "pattern", "robot", "sensor", "input", "output", "code", "debug", "sequence"],
    "technology": ["design", "materials", "structures", "systems", "control", "processing", "mechanical", "electrical"],
    "arts": ["performance", "composition", "improvisation", "portfolio", "design", "visual", "music", "dance", "drama"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "unknown"


def resolver_subject_id(profile: dict[str, Any]) -> str:
    profile_id = str(profile.get("profile_id") or "")
    subject_part = profile_id.split(".", 1)[-1] if "." in profile_id else profile_id
    subject_part = subject_part.replace("_language", "")
    if subject_part:
        return subject_part
    return slug(str(profile.get("subject") or "")).replace("_language", "")


def is_real_subject_profile(profile: dict[str, Any]) -> bool:
    subject = str(profile.get("subject") or "").lower()
    profile_id = str(profile.get("profile_id") or "").lower()
    return "guidelines to strengthen caps" not in subject and "guidelines_to_strengthen" not in profile_id


def phase_grades(profile: dict[str, Any]) -> list[int]:
    phase = str(profile.get("phase") or "")
    return GRADES_BY_PHASE.get(phase, [])


def row_key(profile_id: object, grade: object, term: object) -> tuple[str, int, int]:
    return (str(profile_id or ""), int(grade or 0), int(term or 0))


def load_stable_keys(path: Path | None) -> set[tuple[str, int, int]]:
    if not path:
        return set()
    payload = load_json(path)
    return {
        row_key(row.get("profile_id"), row.get("grade"), row.get("term"))
        for row in payload.get("stable_rows") or []
        if row.get("stable") is True
    }


def resolve_context(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    grade: int,
    preferred_language: str,
    text_cache: dict[str, str],
    matrix_by_sha: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    subject_profile = synthesize_subject_profile(str(profile.get("subject") or "Subject"))
    subject_profile["subject_id"] = resolver_subject_id(profile)
    candidates = resolve_caps(manifest, subject_profile["subject_id"], grade, preferred_language, include_policy=False)
    selected = candidates[0] if candidates else None
    full_text = ""
    extraction_error = None
    if selected and selected.get("path"):
        path = str(selected["path"])
        if path not in text_cache:
            try:
                text_cache[path] = extract_text(Path(path), 180000)
            except Exception as exc:
                text_cache[path] = ""
                extraction_error = str(exc)
        full_text = text_cache[path]
    return {
        "schema": "knowedge.homs_caps_context.v1",
        "created_at": utc_now(),
        "enabled": True,
        "subject_id": subject_profile["subject_id"],
        "subject": subject_profile["display_name"],
        "grade": grade,
        "phase": PHASE_BY_GRADE[grade],
        "preferred_language": preferred_language,
        "candidate_count": len(candidates),
        "candidates": candidates[:5],
        "selected": selected,
        "assessment_ontology_profile": {
            "profile_id": profile.get("profile_id"),
            "subject": profile.get("subject"),
            "phase": profile.get("phase"),
            "assessment_family": profile.get("assessment_family"),
        },
        "assessment_design_profile": profile,
        "assessment_matrix_row": source_matrix_context(selected, matrix_by_sha or {}),
        "extracted_excerpt": full_text[:3500],
        "full_text": full_text,
        "extraction_error": extraction_error,
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


def topic_from_theme_lines(subject: str, grade: int, term: int, term_lines: list[str]) -> list[str]:
    quality = theme_quality(subject, "", term_lines)
    useful = sorted(
        list(quality["content_lines"]),
        key=lambda line: theme_line_score(subject, line),
        reverse=True,
    )
    banned = ["curriculum and assessment", "geography grades", "caps ", "section ", "formal assessment"]
    for line in term_lines:
        lowered = line.lower()
        if line_is_admin(line):
            continue
        if any(item in lowered for item in banned) and len(line) > 80:
            continue
        if line not in useful:
            useful.append(line)
        if len(useful) >= 2:
            break
    if useful:
        return useful
    return [f"{subject} Grade {grade} Term {term} CAPS content", f"{subject} assessment theme and skills"]


def theme_line_score(subject: str, line: str) -> int:
    lowered = line.lower()
    subject_l = subject.lower()
    score = 0
    priority_terms = ["synoptic", "weather map", "map", "graph", "table", "investigation", "practical", "project", "case", "source", "writing", "reading", "algebra", "geometry", "data"]
    for term in priority_terms:
        if term in lowered:
            score += 8
    for term in subject_content_terms(subject, ""):
        if term in lowered:
            score += 3
    if subject_l.split()[0] in lowered:
        score += 1
    if line_is_admin(line):
        score -= 30
    if len(line) > 140:
        score -= 4
    return score


def subject_content_terms(subject: str, family: str) -> list[str]:
    text = f"{subject} {family}".lower()
    terms: list[str] = []
    for key, values in CONTENT_THEME_TERMS.items():
        if key in text:
            terms.extend(values)
    if "language" in text:
        terms.extend(CONTENT_THEME_TERMS["language"])
    if any(token in text for token in ["dance", "dramatic", "music", "visual arts"]):
        terms.extend(CONTENT_THEME_TERMS["arts"])
    if not terms:
        terms.extend(["topic", "content", "skills", "practical", "source", "data", "case", "project"])
    return sorted(set(terms))


def line_is_admin(line: str) -> bool:
    lowered = line.lower()
    if "...." in lowered:
        return True
    if re.fullmatch(r"[a-z\s:/&-]+grades?\s+(r-)?\d+(-\d+)?", lowered):
        return True
    if re.fullmatch(r"[a-z\s:/&-]+grade\s+\d+", lowered):
        return True
    if "http://" in lowered or "https://" in lowered or "www." in lowered or ".org" in lowered or ".html" in lowered:
        return True
    if lowered in {"topic: time: additional resources:", "geographical knowledge", "additional resources:"}:
        return True
    return any(term in lowered for term in ADMIN_THEME_TERMS)


def theme_quality(subject: str, family: str, term_lines: list[str]) -> dict[str, Any]:
    terms = subject_content_terms(subject, family)
    content_lines = []
    admin_lines = []
    for line in term_lines:
        lowered = line.lower()
        is_content = any(term in lowered for term in terms)
        is_admin = line_is_admin(line)
        if is_content and not is_admin:
            content_lines.append(line)
        elif is_admin:
            admin_lines.append(line)
    if len(content_lines) >= 2:
        confidence = "high"
    elif len(content_lines) == 1:
        confidence = "medium"
    else:
        confidence = "low"
    return {
        "confidence": confidence,
        "render_allowed": confidence in {"high", "medium"},
        "content_lines": content_lines[:8],
        "admin_lines": admin_lines[:8],
        "content_terms": terms[:20],
    }


def pack_questions_for_family(family: str, subject: str) -> list[dict[str, Any]]:
    family = str(family or "")
    if family == "calculation_problem_solving":
        return [
            {"number": "1.1", "question": "Complete the calculation or pattern task. Show all working.", "marks": 10, "memo": ["Credit method and final answer."]},
            {"number": "1.2", "question": "Use the visual workspace to explain or justify the result.", "marks": 15, "memo": ["Credit visible reasoning and correct interpretation."]},
        ]
    if family == "data_diagram_practical_investigation":
        return [
            {"number": "1.1", "question": "Record the method, variables and observations in the investigation sheet.", "marks": 10, "memo": ["Credit correct method and observations."]},
            {"number": "1.2", "question": "Use the data to write a supported conclusion.", "marks": 15, "memo": ["Credit conclusion linked to evidence."]},
        ]
    if family == "case_study_structured_questions":
        return [
            {"number": "1.1", "question": "Identify the key problem or decision in the case.", "marks": 10, "memo": ["Credit relevant case facts."]},
            {"number": "1.2", "question": "Recommend an action and justify it using case evidence.", "marks": 15, "memo": ["Credit justified, evidence-based recommendation."]},
        ]
    if family == "language_integrated_assessment":
        return [
            {"number": "1.1", "question": "Use the text panel to identify the main idea and supporting evidence.", "marks": 10, "memo": ["Credit accurate reading/viewing evidence."]},
            {"number": "1.2", "question": "Plan, draft and edit a response using the planner.", "marks": 15, "memo": ["Credit planning, language control and editing."]},
        ]
    if family == "practical_project_design_task":
        return [
            {"number": "1.1", "question": "Complete the design plan and constraints section.", "marks": 10, "memo": ["Credit clear problem and constraints."]},
            {"number": "1.2", "question": "Record testing evidence and one improvement.", "marks": 15, "memo": ["Credit test evidence and justified improvement."]},
        ]
    if family == "practical_performance_or_portfolio":
        return [
            {"number": "1.1", "question": "Prepare the performance or portfolio evidence using the planning map.", "marks": 10, "memo": ["Credit complete planning evidence."]},
            {"number": "1.2", "question": "Perform, present or submit the final work for observation against the instrument.", "marks": 15, "memo": ["Credit observable evidence against criteria."]},
        ]
    return [
        {"number": "1.1", "question": f"Use the supplied {subject} visual evidence to answer the structured task.", "marks": 10, "memo": ["Credit accurate subject knowledge."]},
        {"number": "1.2", "question": "Explain your answer using evidence from the visual or source.", "marks": 15, "memo": ["Credit evidence-linked reasoning."]},
    ]


def demo_pack(profile: dict[str, Any], grade: int, term: int, request: dict[str, Any]) -> dict[str, Any]:
    subject = str(profile.get("subject") or "Subject")
    family = str(profile.get("assessment_family") or "structured_test_or_task")
    render_shell = str(profile.get("render_shell") or "question_paper")
    focus = request["topics"][0] if request.get("topics") else f"Term {term} CAPS content"
    return {
        "schema": "knowedge.homs_assessment_pack.v1",
        "assessment_title": f"Grade {grade} {subject} Term {term} Visual Asset Pack: {focus[:70]}",
        "subject": subject,
        "grade": grade,
        "phase": PHASE_BY_GRADE[grade],
        "canonical_profile_id": profile.get("profile_id"),
        "blueprint": family,
        "render_shell": render_shell,
        "visual_blueprint": request["visual_blueprint"],
        "duration": "visual preflight",
        "total_marks": 25,
        "sections": [
            {
                "title": "Visual Evidence Preflight",
                "mode": render_shell,
                "instructions": "Use this pre-made visual pack as the visual contract before generating the final assessment.",
                "stimulus": f"{subject} Grade {grade} Term {term}: {focus}",
                "questions": pack_questions_for_family(family, subject),
            }
        ],
        "rubric": [
            {"criterion": "Visual evidence use", "marks": 10, "descriptor": "Learner uses the supplied visual evidence accurately."},
            {"criterion": "Subject reasoning", "marks": 10, "descriptor": "Response shows CAPS-aligned reasoning for the subject and grade."},
            {"criterion": "Communication or process evidence", "marks": 5, "descriptor": "Working, planning, observation or response is clear enough to mark."},
        ],
        "teacher_review_checklist": [
            "Confirm CAPS subject, grade and term fit.",
            "Confirm the final assessment questions use the planned visuals as evidence.",
            "Confirm visual labels, units and mark expectations before classroom use.",
        ],
    }


def build_pack(
    out_root: Path,
    manifest: dict[str, Any],
    design_law: dict[str, Any],
    profile: dict[str, Any],
    grade: int,
    term: int,
    preferred_language: str,
    grade_ladder: Path,
    text_cache: dict[str, str],
    render: bool,
    matrix_by_sha: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    context = resolve_context(manifest, profile, grade, preferred_language, text_cache, matrix_by_sha)
    full_text = str(context.get("full_text") or "")
    term_lines = extract_term_theme_lines(full_text or str(context.get("extracted_excerpt") or ""), grade, term)
    quality = theme_quality(str(profile.get("subject") or ""), str(profile.get("assessment_family") or ""), term_lines)
    subject = str(profile.get("subject") or "Subject")
    topics = topic_from_theme_lines(subject, grade, term, term_lines)
    subject_profile = synthesize_subject_profile(subject)
    subject_profile["subject_id"] = resolver_subject_id(profile)
    grade_profile = load_grade_profile(grade, grade_ladder)
    request = {
        "module_code": slug(subject).upper()[:8] or "CAPS",
        "module_name": f"{subject} Grade {grade} Term {term}",
        "topics": topics,
        "methodology_topic": topics[0],
        "essay_topic": topics[-1],
        "total_marks": 25,
        "duration_hours": 1,
        "term": str(term),
        "subject_profile": {key: value for key, value in subject_profile.items() if not key.startswith("_")},
        "grade_profile": {key: value for key, value in grade_profile.items() if not key.startswith("_")},
        "caps_context": context,
    }
    request["visual_blueprint"] = build_visual_blueprint(request)
    request["visual_blueprint"]["theme_quality"] = quality
    if not quality["render_allowed"]:
        request["visual_blueprint"]["render_gate"] = {
            "status": "blocked",
            "reason": "CAPS term/theme extraction did not produce a confident content theme.",
            "action": "Curate or improve the CAPS term map before rendering subject visuals.",
        }
    else:
        request["visual_blueprint"]["render_gate"] = {
            "status": "passed",
            "reason": "CAPS term/theme extraction produced content-bearing theme lines.",
        }
    pack = demo_pack(profile, grade, term, request)
    pack_dir = out_root / slug(str(profile.get("profile_id"))) / f"grade_{grade}" / f"term_{term}"
    pack_dir.mkdir(parents=True, exist_ok=True)
    context_to_write = dict(context)
    context_to_write.pop("full_text", None)
    (pack_dir / "caps_context.json").write_text(json.dumps(context_to_write, indent=2), encoding="utf-8")
    (pack_dir / "HOMS_VISUAL_BLUEPRINT.json").write_text(json.dumps(request["visual_blueprint"], indent=2), encoding="utf-8")
    (pack_dir / "assessment_pack.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")
    assets: list[dict[str, Any]] = []
    render_allowed = render and quality["render_allowed"]
    if render_allowed:
        assets = build_assets(pack_dir, pack, design_law, profile)
        (pack_dir / "assets.json").write_text(json.dumps(assets, indent=2), encoding="utf-8")
    else:
        (pack_dir / "RENDER_BLOCKED.md").write_text(
            "\n".join(
                [
                    "# Visual Render Blocked",
                    "",
                    f"Subject: {subject}",
                    f"Grade: {grade}",
                    f"Term: {term}",
                    f"Confidence: {quality['confidence']}",
                    "",
                    "The builder wrote the blueprint and assessment-pack stub, but did not render visuals because the CAPS term/theme extraction was not content-confident.",
                    "",
                    "## Extracted Content Lines",
                    *(f"- {line}" for line in quality["content_lines"]),
                    "",
                    "## Admin / Noisy Lines",
                    *(f"- {line}" for line in quality["admin_lines"]),
                ]
            ).strip()
            + "\n",
            encoding="utf-8",
        )
    return {
        "profile_id": profile.get("profile_id"),
        "subject": subject,
        "grade": grade,
        "term": term,
        "phase": PHASE_BY_GRADE[grade],
        "assessment_family": profile.get("assessment_family"),
        "render_shell": profile.get("render_shell"),
        "candidate_count": context.get("candidate_count", 0),
        "caps_source": (context.get("selected") or {}).get("title"),
        "alignment_notes": request["visual_blueprint"].get("content_alignment_notes", []),
        "theme_quality": quality,
        "render_status": "rendered" if render_allowed else "blocked",
        "required_visuals": request["visual_blueprint"].get("required_visuals", []),
        "source_type_contract": request["visual_blueprint"].get("source_type_contract", {}),
        "source_types": (request["visual_blueprint"].get("source_type_contract") or {}).get("source_types", []),
        "assets": assets,
        "folder": str(pack_dir),
    }


def write_index(out_root: Path, rows: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> Path:
    counts = Counter(str(row.get("assessment_family") or "unknown") for row in rows)
    render_counts = Counter(str(row.get("render_status") or "unknown") for row in rows)
    confidence_counts = Counter(str((row.get("theme_quality") or {}).get("confidence") or "unknown") for row in rows)
    payload = {
        "schema": "knowedge.homs_caps_visual_asset_pack_index.v1",
        "created_at": utc_now(),
        "pack_count": len(rows),
        "skipped_count": len(skipped),
        "assessment_family_counts": dict(sorted(counts.items())),
        "render_status_counts": dict(sorted(render_counts.items())),
        "theme_confidence_counts": dict(sorted(confidence_counts.items())),
        "rows": rows,
        "skipped": skipped,
    }
    path = out_root / "VISUAL_ASSET_PACK_INDEX.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# HOMS CAPS Visual Asset Packs",
        "",
        f"Created: {payload['created_at']}",
        f"Packs: {len(rows)}",
        f"Skipped: {len(skipped)}",
        f"Rendered: {render_counts.get('rendered', 0)}",
        f"Blocked: {render_counts.get('blocked', 0)}",
        "",
        "## Assessment Families",
    ]
    for family, count in sorted(counts.items()):
        lines.append(f"- {family}: {count}")
    lines.extend(["", "## First 40 Packs"])
    for row in rows[:40]:
        titles = ", ".join(item.get("title", "") for item in row.get("required_visuals", []))
        lines.append(f"- {row['profile_id']} / Grade {row['grade']} / Term {row['term']} / {row.get('render_status')}: {titles}")
    (out_root / "VISUAL_ASSET_PACK_INDEX.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build pre-made CAPS term/theme-aware HOMS visual asset packs.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--caps-manifest", default=str(DEFAULT_CAPS_MANIFEST))
    parser.add_argument("--caps-matrix", default=str(DEFAULT_CAPS_MATRIX))
    parser.add_argument("--caps-assessment-design", default=str(DEFAULT_CAPS_ASSESSMENT_DESIGN))
    parser.add_argument("--grade-ladder", default=str(DEFAULT_GRADE_LADDER))
    parser.add_argument("--design-law", default=str(DEFAULT_DESIGN_LAW))
    parser.add_argument("--preferred-language", default="English")
    parser.add_argument("--profile", default="", help="Optional profile_id filter.")
    parser.add_argument("--phase", default="", help="Optional phase filter, for example fet_grade_10_12.")
    parser.add_argument("--fet-only", action="store_true", help="Shortcut for --phase fet_grade_10_12.")
    parser.add_argument("--grade", type=int, default=0, help="Optional grade filter.")
    parser.add_argument("--term", type=int, default=0, help="Optional term filter, 1-4.")
    parser.add_argument("--limit", type=int, default=0, help="Optional pack limit for smoke tests.")
    parser.add_argument("--stable-audit", default="", help="Only build rows approved by a FET_STABLE_PACK_AUDIT.json file.")
    parser.add_argument("--render", action="store_true", help="Render SVG/PNG assets for rows that pass the content gate.")
    parser.add_argument("--no-render", action="store_true", help="Deprecated compatibility flag; blueprint-only is now the default.")
    args = parser.parse_args()

    out_root = Path(args.out).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(Path(args.caps_manifest).expanduser().resolve())
    caps_matrix_path = Path(args.caps_matrix).expanduser().resolve()
    caps_matrix = load_json(caps_matrix_path) if caps_matrix_path.exists() else {}
    matrix_by_sha = {str(row.get("sha256") or ""): row for row in caps_matrix.get("rows") or [] if row.get("sha256")}
    design_payload = load_json(Path(args.caps_assessment_design).expanduser().resolve())
    design_law = load_json(Path(args.design_law).expanduser().resolve())
    grade_ladder = Path(args.grade_ladder).expanduser().resolve()
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    text_cache: dict[str, str] = {}
    phase_filter = "fet_grade_10_12" if args.fet_only else str(args.phase or "")
    stable_filter_active = bool(args.stable_audit)
    stable_keys = load_stable_keys(Path(args.stable_audit).expanduser().resolve()) if args.stable_audit else set()

    for profile in design_payload.get("profiles") or []:
        if args.profile and profile.get("profile_id") != args.profile:
            continue
        if phase_filter and profile.get("phase") != phase_filter:
            continue
        if not is_real_subject_profile(profile):
            skipped.append({"profile_id": profile.get("profile_id"), "reason": "support_or_guideline_profile"})
            continue
        grades = phase_grades(profile)
        if args.grade:
            grades = [grade for grade in grades if grade == args.grade]
        terms = [args.term] if args.term else [1, 2, 3, 4]
        for grade in grades:
            for term in terms:
                if args.limit and len(rows) >= args.limit:
                    break
                if stable_filter_active and row_key(profile.get("profile_id"), grade, term) not in stable_keys:
                    skipped.append({"profile_id": profile.get("profile_id"), "grade": grade, "term": term, "reason": "stable_audit_not_approved"})
                    continue
                try:
                    rows.append(
                        build_pack(
                            out_root,
                            manifest,
                            design_law,
                            profile,
                            grade,
                            term,
                            args.preferred_language,
                            grade_ladder,
                            text_cache,
                            render=args.render and not args.no_render,
                            matrix_by_sha=matrix_by_sha,
                        )
                    )
                except Exception as exc:
                    skipped.append({"profile_id": profile.get("profile_id"), "grade": grade, "term": term, "reason": str(exc)})
            if args.limit and len(rows) >= args.limit:
                break
        if args.limit and len(rows) >= args.limit:
            break

    index_path = write_index(out_root, rows, skipped)
    print(
        json.dumps(
            {
                "status": "completed",
                "packs": len(rows),
                "skipped": len(skipped),
                "index": str(index_path),
                "out": str(out_root),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
