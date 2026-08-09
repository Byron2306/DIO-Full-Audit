#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from openai import OpenAI  # noqa: E402
from apply_homs_design_law import DEFAULT_ASSESSMENT_DESIGN, DEFAULT_DESIGN_LAW, apply_design_law  # noqa: E402
from build_caps_assessment_ontology import build_profiles  # noqa: E402
from resolve_caps_source import extract_text  # noqa: E402


DEFAULT_SECRET_FILE = Path("/home/byron/EdgeK-BEAST/.beast/provider_secrets.env")
DEFAULT_CAPS_MATRIX = ROOT / "deliverables" / "caps_matrix_analysis" / "caps_matrix_analysis.json"
DEFAULT_CAPS_ONTOLOGY = ROOT / "deliverables" / "caps_assessment_ontology" / "caps_assessment_ontology.json"
DEFAULT_OUT = ROOT / "campaigns" / "phase3" / "homs" / "exam_builder" / "caps_closing_proofs"


GRADE_CHOICES = {
    "foundation_grade_r_3": [1, 2, 3],
    "intermediate_grade_4_6": [4, 5, 6],
    "senior_grade_7_9": [7, 8, 9],
    "fet_grade_10_12": [10, 11, 12],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", " ", value or "")
    value = re.sub(r"\s+", " ", value).strip().lower().replace(" ", "_")
    return re.sub(r"_+", "_", value).strip("._-")[:120] or "assessment"


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.replace("export ", "").strip()] = value.strip().strip('"').strip("'")
    return values


def configure_provider(secret_file: Path, provider_name: str, model: str) -> dict[str, Any]:
    values = parse_env_file(secret_file)
    for key, value in values.items():
        os.environ.setdefault(key, value)
    if provider_name in {"nim", "nvidia", "nvidia_nim"}:
        api_key = values.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY was not found.")
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
        selected_model = model or os.environ.get("HOMS_NIM_MODEL") or os.environ.get("BEAST_NIM_MODEL") or "nvidia/nemotron-3-super-120b-a12b"
        selected_provider = "nvidia_nim"
    else:
        api_key = values.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY was not found.")
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ.pop("OPENAI_BASE_URL", None)
        selected_model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o"
        selected_provider = "openai"
    return {
        "selected_provider": selected_provider,
        "selected_model": selected_model,
        "base_url": os.environ.get("OPENAI_BASE_URL") or None,
        "values_redacted": True,
    }


def load_matrix(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_or_build_ontology(ontology_path: Path, matrix_path: Path) -> dict[str, Any]:
    if ontology_path.exists():
        return json.loads(ontology_path.read_text(encoding="utf-8"))
    matrix = load_matrix(matrix_path)
    profiles = build_profiles(matrix.get("rows", []))
    return {
        "schema": "knowedge.caps_assessment_ontology.v1",
        "created_at": utc_now(),
        "source_matrix": str(matrix_path),
        "source_document_count": len(matrix.get("rows", [])),
        "profile_count": len(profiles),
        "profiles": profiles,
    }


def load_assessment_design(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def design_for_row(row: dict[str, Any], assessment_design: dict[str, Any]) -> dict[str, Any]:
    profile_id = (row.get("canonical_profile") or {}).get("profile_id")
    return (assessment_design.get("profiles_by_id") or {}).get(profile_id, {})


def group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    usable = [
        row for row in rows
        if row.get("phase") != "policy_and_support"
        and row.get("path")
        and row.get("recommended_blueprint")
    ]
    return {
        "fet_senior": [row for row in usable if row.get("phase") in {"fet_grade_10_12", "senior_grade_7_9"}],
        "intermediate": [row for row in usable if row.get("phase") == "intermediate_grade_4_6"],
        "foundation": [row for row in usable if row.get("phase") == "foundation_grade_r_3"],
    }


def choose_rows(matrix: dict[str, Any], seed: int | None) -> tuple[int, list[dict[str, Any]]]:
    seed_value = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    rng = random.Random(seed_value)
    groups = group_rows(matrix.get("rows", []))
    selected = []
    for group_name in ["fet_senior", "intermediate", "foundation"]:
        rows = groups[group_name]
        if not rows:
            raise RuntimeError(f"No CAPS rows available for group {group_name}")
        preferred = [row for row in rows if row.get("subject_family") != "language"]
        row = dict(rng.choice(preferred or rows))
        row["proof_group"] = group_name
        row["selected_grade"] = rng.choice(GRADE_CHOICES.get(row["phase"], [12]))
        selected.append(row)
    return seed_value, selected


def choose_profile_rows(ontology: dict[str, Any], seed: int | None) -> tuple[int, list[dict[str, Any]]]:
    seed_value = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    rng = random.Random(seed_value)
    profiles = [
        profile for profile in ontology.get("profiles", [])
        if profile.get("phase_group") in {"foundation", "intermediate", "senior", "fet"}
        and profile.get("supporting_caps_evidence")
    ]
    groups = {
        "fet_senior": [profile for profile in profiles if profile.get("phase_group") in {"senior", "fet"}],
        "intermediate": [profile for profile in profiles if profile.get("phase_group") == "intermediate"],
        "foundation": [profile for profile in profiles if profile.get("phase_group") == "foundation"],
    }
    selected = []
    used_subjects: set[str] = set()
    for group_name in ["fet_senior", "intermediate", "foundation"]:
        group_profiles = groups[group_name]
        if not group_profiles:
            raise RuntimeError(f"No CAPS ontology profiles available for group {group_name}")
        preferred = [
            profile for profile in group_profiles
            if profile.get("subject_family") != "language"
            and profile.get("subject") not in {"Unclassified CAPS Subject"}
            and profile.get("subject") not in used_subjects
        ]
        profile = dict(rng.choice(preferred or group_profiles))
        used_subjects.add(str(profile.get("subject")))
        evidence = list(profile.get("supporting_caps_evidence") or [])
        english = [
            doc for doc in evidence
            if doc.get("language") == "English" or "english" in str(doc.get("path") or "").lower()
        ]
        unknown = [doc for doc in evidence if doc.get("language") == "Unknown"]
        doc = rng.choice(english or unknown or evidence)
        row = {
            "proof_group": group_name,
            "selected_grade": rng.choice(profile.get("grades") or GRADE_CHOICES.get(profile["phase"], [12])),
            "title": profile["subject"],
            "phase": profile["phase"],
            "subject_family": profile["subject_family"],
            "language_guess": doc.get("language") or "Unknown",
            "path": doc["path"],
            "sha256": doc["sha256"],
            "recommended_blueprint": profile["assessment_family"],
            "signals_source_based": doc.get("signals", {}).get("signals_source_based", False),
            "signals_essay_or_extended_response": doc.get("signals", {}).get("signals_essay_or_extended_response", False),
            "signals_case_study": doc.get("signals", {}).get("signals_case_study", False),
            "signals_data_graph_diagram": doc.get("signals", {}).get("signals_data_graph_diagram", False),
            "signals_practical_investigation": doc.get("signals", {}).get("signals_practical_investigation", False),
            "signals_project_or_sba": doc.get("signals", {}).get("signals_project_or_sba", False),
            "signals_oral_or_performance": doc.get("signals", {}).get("signals_oral_or_performance", False),
            "signals_calculation_problem": doc.get("signals", {}).get("signals_calculation_problem", False),
            "signals_formal_test_or_exam": doc.get("signals", {}).get("signals_formal_test_or_exam", False),
            "canonical_profile": profile,
            "source_document_title": doc.get("title"),
            "output_language": "English",
        }
        selected.append(row)
    return seed_value, selected


def clean_excerpt(text: str, max_chars: int = 2500) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    anchors = ["assessment", "programme of assessment", "content", "formal assessment", "examination", "cognitive"]
    lower = text.lower()
    for anchor in anchors:
        idx = lower.find(anchor)
        if idx >= 0:
            return text[max(0, idx - 500) : max(0, idx - 500) + max_chars].strip()
    return text[:max_chars].strip()


def pack_requirements(blueprint: str) -> str:
    return {
        "language_integrated_assessment": "Use reading/viewing, writing, language structures, and oral/listening where appropriate. Do not force a business/science case study.",
        "case_study_structured_questions": "Build around one or more realistic scenarios/case studies with structured questions, memo alternatives, and justified recommendations.",
        "data_diagram_practical_investigation": "Use data, diagrams, observations, or investigation-style stimuli. Include interpretation and method/evidence reasoning.",
        "calculation_problem_solving": "Use graded calculation/problem-solving items with worked memo steps. Avoid essay sections unless the CAPS matrix clearly justifies them.",
        "practical_project_design_task": "Use a design/practical/project task with constraints, deliverables, rubric, and safety/review notes.",
        "practical_performance_or_portfolio": "Use performance/portfolio-style tasks with observable criteria and rubric levels.",
        "source_based_plus_essay": "Use source-based work and an extended/essay response only where age and CAPS scope justify it.",
        "source_based_plus_extended_response": "Use source/stimulus analysis plus a shorter extended response. Keep structure grade-appropriate.",
        "foundation_activity_assessment": "Use concrete activities, pictures/teacher prompts, simple learner responses, and a teacher-facing memo.",
        "structured_test_or_task": "Use a balanced structured task/test with short and medium responses. Match the grade band.",
    }.get(blueprint, "Use the CAPS matrix row to choose a grade-appropriate structure.")


def profile_requirements(row: dict[str, Any]) -> str:
    profile = row.get("canonical_profile") or {}
    if not profile:
        return ""
    distribution = profile.get("required_distribution") or {}
    return "\n".join(
        [
            "Canonical CAPS ontology profile:",
            f"- Profile ID: {profile.get('profile_id')}",
            f"- Subject: {profile.get('subject')}",
            f"- Assessment family: {profile.get('assessment_family')}",
            f"- Allowed modes: {', '.join(profile.get('allowed', []))}",
            f"- Default-off modes: {', '.join(profile.get('default_off', []))}",
            f"- Required distribution guide: {', '.join(f'{k}={v}%' for k, v in distribution.items())}",
            f"- Generation constraints: {'; '.join(profile.get('generation_constraints', []))}",
            f"- Validation rules: {'; '.join(profile.get('validation_rules', []))}",
        ]
    )


def assessment_design_requirements(row: dict[str, Any]) -> str:
    design = row.get("assessment_design_profile") or {}
    if not design:
        return ""
    weightings = design.get("annual_weightings") or {}
    cognitive = design.get("cognitive_distribution") or {}
    return "\n".join(
        [
            "CAPS assessment-design profile:",
            f"- Render shell: {design.get('render_shell')}",
            f"- Assessment forms: {', '.join(design.get('assessment_forms') or [])}",
            f"- Annual weightings: {', '.join(f'{k}={v}%' for k, v in weightings.items()) or 'not extracted'}",
            f"- Cognitive / skill distribution: {', '.join(f'{k}={v}%' for k, v in cognitive.items()) or 'not extracted'}",
            f"- Marking instruments: {', '.join(design.get('marking_instruments') or [])}",
            f"- Assessment-design constraints: {'; '.join(design.get('generation_constraints') or [])}",
        ]
    )


def model_json(client: OpenAI, model: str, prompt: str) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a South African CAPS assessment designer. Return only valid JSON for a review-ready educator draft. Do not invent official CAPS quotations.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.55,
        max_tokens=4500,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("provider returned empty content")
    return json.loads(content)


def fallback_pack(row: dict[str, Any], excerpt: str) -> dict[str, Any]:
    blueprint = row["recommended_blueprint"]
    grade = row["selected_grade"]
    title = row["title"]
    return {
        "assessment_title": f"Grade {grade} {title}: CAPS-Aligned {blueprint.replace('_', ' ').title()}",
        "subject": title,
        "grade": grade,
        "phase": row["phase"],
        "canonical_profile_id": (row.get("canonical_profile") or {}).get("profile_id"),
        "blueprint": blueprint,
        "duration": "Educator to set",
        "total_marks": 40 if grade <= 6 else 50,
        "sections": [
            {
                "title": blueprint.replace("_", " ").title(),
                "mode": blueprint,
                "instructions": pack_requirements(blueprint),
                "stimulus": excerpt[:1200],
                "questions": [
                    {
                        "number": "1",
                        "question": "Complete the CAPS-aligned task using the stimulus and teacher instructions.",
                        "marks": 20,
                        "memo": ["Credit accurate, grade-appropriate responses aligned with the CAPS source and educator rubric."],
                    }
                ],
            }
        ],
        "rubric": [
            {"criterion": "CAPS alignment", "marks": 10, "descriptor": "Task matches grade, phase, and subject expectations."},
            {"criterion": "Content accuracy", "marks": 10, "descriptor": "Responses use correct subject knowledge."},
            {"criterion": "Reasoning or skill demonstration", "marks": 10, "descriptor": "Learner demonstrates the expected skill for this blueprint."},
            {"criterion": "Communication", "marks": 10, "descriptor": "Response is clear for the grade level."},
        ],
        "teacher_review_checklist": [
            "Verify CAPS scope and grade appropriateness.",
            "Adjust marks to local school policy.",
            "Replace any placeholder stimulus if needed.",
            "Confirm learner language/load is appropriate.",
        ],
    }


def build_prompt(row: dict[str, Any], excerpt: str) -> str:
    blueprint = row["recommended_blueprint"]
    signals = [
        key.replace("signals_", "").replace("_", " ")
        for key, value in row.items()
        if key.startswith("signals_") and value
    ]
    return f"""Build one complete CAPS-aligned assessment demo pack.

Selected CAPS document:
- Title: {row['title']}
- Phase: {row['phase']}
- Grade to target: {row['selected_grade']}
- Subject family: {row['subject_family']}
- Language guess: {row['language_guess']}
- Output language: {row.get('output_language', 'English')}
- SHA-256: {row['sha256']}
- Local path: {row['path']}

CAPS matrix result:
- Recommended blueprint: {blueprint}
- Format signals: {', '.join(signals) if signals else 'none'}
- Instruction: {pack_requirements(blueprint)}

{profile_requirements(row)}

{assessment_design_requirements(row)}

CAPS excerpt for grounding:
{excerpt}

Write the learner instructions, teacher memo, rubric, and review checklist in English unless the selected canonical subject is explicitly a language-learning assessment that requires target-language examples.

Return JSON with this exact top-level shape:
{{
  "assessment_title": "...",
  "subject": "{row['title']}",
  "grade": {row['selected_grade']},
  "phase": "{row['phase']}",
  "canonical_profile_id": "{(row.get('canonical_profile') or {}).get('profile_id', '')}",
  "blueprint": "{blueprint}",
  "duration": "...",
  "total_marks": 0,
  "sections": [
    {{
      "title": "...",
      "mode": "{blueprint}",
      "instructions": "...",
      "stimulus": "...",
      "questions": [
        {{"number": "1.1", "question": "...", "marks": 0, "memo": ["..."]}}
      ]
    }}
  ],
  "rubric": [
    {{"criterion": "...", "marks": 0, "descriptor": "..."}}
  ],
  "teacher_review_checklist": ["..."]
}}

Do not force source-based sections or essay assessment unless the canonical profile explicitly justifies them. If the render shell is performance_task_sheet, write observable tasks and assessment criteria rather than answer-line questions. If the render shell is project_task_sheet, write deliverables, constraints, test evidence, and rubric criteria. Make it usable as a controlled demo, not final authorized school material. Include enough teacher-facing memo detail for educator approval."""


def render_markdown(pack: dict[str, Any], row: dict[str, Any]) -> str:
    lines = [
        f"# {pack.get('assessment_title', 'CAPS Assessment Demo')}",
        "",
        f"Subject: {pack.get('subject', row['title'])}",
        f"Grade: {pack.get('grade', row['selected_grade'])}",
        f"Phase: {pack.get('phase', row['phase'])}",
        f"Blueprint: {pack.get('blueprint', row['recommended_blueprint'])}",
        f"Duration: {pack.get('duration', 'Educator to set')}",
        f"Total Marks: {pack.get('total_marks', 'Educator to set')}",
        "",
        "## CAPS Source",
        "",
        f"- Title: {row['title']}",
        f"- Path: `{row['path']}`",
        f"- SHA-256: `{row['sha256']}`",
        "",
    ]
    for section in pack.get("sections", []):
        lines.extend(["", f"## {section.get('title', 'Section')}", "", section.get("instructions", "")])
        if section.get("stimulus"):
            lines.extend(["", "### Stimulus", "", str(section["stimulus"])])
        if section.get("questions"):
            lines.extend(["", "### Questions", ""])
            for question in section["questions"]:
                lines.append(f"{question.get('number', '')}. {question.get('question', '')} [{question.get('marks', 0)}]")
                memo = question.get("memo") or []
                if memo:
                    lines.append(f"   Memo: {'; '.join(str(item) for item in memo)}")
    if pack.get("rubric"):
        lines.extend(["", "## Rubric", ""])
        for item in pack["rubric"]:
            lines.append(f"- {item.get('criterion')}: {item.get('marks')} marks - {item.get('descriptor')}")
    if pack.get("teacher_review_checklist"):
        lines.extend(["", "## Teacher Review Checklist", ""])
        for item in pack["teacher_review_checklist"]:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def render_docx(pack: dict[str, Any], row: dict[str, Any], path: Path) -> None:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)
    doc.add_heading(pack.get("assessment_title", "CAPS Assessment Demo"), level=1)
    for label, value in [
        ("Subject", pack.get("subject", row["title"])),
        ("Grade", pack.get("grade", row["selected_grade"])),
        ("Phase", pack.get("phase", row["phase"])),
        ("Blueprint", pack.get("blueprint", row["recommended_blueprint"])),
        ("Total Marks", pack.get("total_marks", "Educator to set")),
    ]:
        p = doc.add_paragraph()
        p.add_run(f"{label}: ").bold = True
        p.add_run(str(value))
    doc.add_heading("CAPS Source", level=2)
    doc.add_paragraph(f"{row['title']} | {row['sha256']}")
    for section in pack.get("sections", []):
        doc.add_heading(section.get("title", "Section"), level=2)
        if section.get("instructions"):
            doc.add_paragraph(section["instructions"])
        if section.get("stimulus"):
            doc.add_heading("Stimulus", level=3)
            doc.add_paragraph(str(section["stimulus"]))
        for question in section.get("questions", []):
            p = doc.add_paragraph()
            p.add_run(f"{question.get('number', '')}. ").bold = True
            p.add_run(str(question.get("question", "")))
            p.add_run(f" [{question.get('marks', 0)}]").bold = True
            memo = question.get("memo") or []
            if memo:
                doc.add_paragraph("Memo: " + "; ".join(str(item) for item in memo))
    if pack.get("rubric"):
        doc.add_heading("Rubric", level=2)
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        for i, header in enumerate(["Criterion", "Marks", "Descriptor"]):
            table.rows[0].cells[i].text = header
        for item in pack["rubric"]:
            cells = table.add_row().cells
            cells[0].text = str(item.get("criterion", ""))
            cells[1].text = str(item.get("marks", ""))
            cells[2].text = str(item.get("descriptor", ""))
    doc.save(path)


def zip_dir(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file() and path.resolve() != target.resolve():
                zf.write(path, path.relative_to(source))


def build_one(client: OpenAI, model: str, row: dict[str, Any], out_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    text = extract_text(Path(row["path"]), 20000)
    excerpt = clean_excerpt(text)
    prompt = build_prompt(row, excerpt)
    status = "generated"
    try:
        pack = model_json(client, model, prompt)
    except Exception as exc:
        status = "fallback"
        pack = fallback_pack(row, excerpt)
        pack["generation_error"] = str(exc)
    job_id = f"{row['proof_group']}_{safe_slug(row['title'])}_grade{row['selected_grade']}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    job_dir = out_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    md = render_markdown(pack, row)
    (job_dir / "assessment_pack.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")
    (job_dir / "ASSESSMENT_PACK.md").write_text(md, encoding="utf-8")
    render_docx(pack, row, job_dir / "ASSESSMENT_PACK.docx")
    receipt = {
        "schema": "knowedge.caps_assessment_demo_receipt.v1",
        "created_at": utc_now(),
        "status": status,
        "job_id": job_id,
        "proof_group": row["proof_group"],
        "selected_grade": row["selected_grade"],
        "caps": {
            "title": row["title"],
            "phase": row["phase"],
            "path": row["path"],
            "sha256": row["sha256"],
            "recommended_blueprint": row["recommended_blueprint"],
            "source_document_title": row.get("source_document_title"),
            "signals": {key: row.get(key) for key in row if key.startswith("signals_")},
        },
        "canonical_profile": {
            "profile_id": (row.get("canonical_profile") or {}).get("profile_id"),
            "subject": (row.get("canonical_profile") or {}).get("subject"),
            "subject_family": (row.get("canonical_profile") or {}).get("subject_family"),
            "assessment_family": (row.get("canonical_profile") or {}).get("assessment_family"),
            "allowed": (row.get("canonical_profile") or {}).get("allowed"),
            "default_off": (row.get("canonical_profile") or {}).get("default_off"),
            "required_distribution": (row.get("canonical_profile") or {}).get("required_distribution"),
        },
        "assessment_design": {
            "render_shell": (row.get("assessment_design_profile") or {}).get("render_shell"),
            "assessment_forms": (row.get("assessment_design_profile") or {}).get("assessment_forms"),
            "annual_weightings": (row.get("assessment_design_profile") or {}).get("annual_weightings"),
            "cognitive_distribution": (row.get("assessment_design_profile") or {}).get("cognitive_distribution"),
            "marking_instruments": (row.get("assessment_design_profile") or {}).get("marking_instruments"),
        },
        "duration_seconds": round(time.perf_counter() - started, 3),
        "outputs": {
            "job_dir": str(job_dir),
            "json": str(job_dir / "assessment_pack.json"),
            "markdown": str(job_dir / "ASSESSMENT_PACK.md"),
            "docx": str(job_dir / "ASSESSMENT_PACK.docx"),
        },
    }
    (job_dir / "CAPS_ASSESSMENT_DEMO_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    zip_path = job_dir / "CAPS_ASSESSMENT_DEMO_PACK.zip"
    zip_dir(job_dir, zip_path)
    receipt["outputs"]["zip"] = str(zip_path)
    (job_dir / "CAPS_ASSESSMENT_DEMO_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Randomly build three CAPS-backed assessment demos across school bands.")
    parser.add_argument("--matrix", default=str(DEFAULT_CAPS_MATRIX))
    parser.add_argument("--ontology", default=str(DEFAULT_CAPS_ONTOLOGY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--secret-file", default=str(DEFAULT_SECRET_FILE))
    parser.add_argument("--provider", default="nim", choices=["nim", "nvidia", "nvidia_nim", "openai"])
    parser.add_argument("--model", default="")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--design-law", default=str(DEFAULT_DESIGN_LAW))
    parser.add_argument("--assessment-design", default=str(DEFAULT_ASSESSMENT_DESIGN))
    parser.add_argument("--skip-design-law", action="store_true")
    args = parser.parse_args()

    provider = configure_provider(Path(args.secret_file).expanduser().resolve(), args.provider, args.model)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL") or None)
    matrix_path = Path(args.matrix).expanduser().resolve()
    ontology = load_or_build_ontology(Path(args.ontology).expanduser().resolve(), matrix_path)
    assessment_design_path = Path(args.assessment_design).expanduser().resolve()
    assessment_design = load_assessment_design(assessment_design_path)
    seed, rows = choose_profile_rows(ontology, args.seed or None)
    for row in rows:
        row["assessment_design_profile"] = design_for_row(row, assessment_design)
    out_root = Path(args.out).expanduser().resolve() / f"caps_closing_seed_{seed}"
    out_root.mkdir(parents=True, exist_ok=True)
    receipts = [build_one(client, provider["selected_model"], row, out_root) for row in rows]
    design_receipts = []
    if not args.skip_design_law:
        design_law_path = Path(args.design_law).expanduser().resolve()
        for receipt in receipts:
            design_receipts.append(apply_design_law(Path(receipt["outputs"]["job_dir"]), design_law_path, assessment_design_path))
    summary = {
        "schema": "knowedge.caps_closing_proof_run.v1",
        "created_at": utc_now(),
        "seed": seed,
        "provider": provider,
        "ontology": str(Path(args.ontology).expanduser().resolve()),
        "assessment_design": str(assessment_design_path),
        "design_law": None if args.skip_design_law else str(Path(args.design_law).expanduser().resolve()),
        "receipts": receipts,
        "design_receipts": design_receipts,
    }
    (out_root / "CAPS_CLOSING_PROOF_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# CAPS Closing Proof Summary", "", f"Seed: `{seed}`", ""]
    for receipt in receipts:
        caps = receipt["caps"]
        profile = receipt.get("canonical_profile") or {}
        lines.append(f"- {receipt['proof_group']}: Grade {receipt['selected_grade']} {profile.get('subject') or caps['title']} -> `{profile.get('assessment_family') or caps['recommended_blueprint']}` ({receipt['status']})")
        lines.append(f"  - {receipt['outputs']['job_dir']}")
    (out_root / "CAPS_CLOSING_PROOF_SUMMARY.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "seed": seed, "out": str(out_root), "count": len(receipts)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
