#!/usr/bin/env python3
"""Generate and validate one CAPS-grounded grade-level exam and marking memo."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
GRADE_LADDER = ROOT / "config/homs_grade_ladder.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.resolve_caps_source import extract_text, load_manifest, resolve as resolve_caps
from scripts.run_hymark_exam_builder import load_grade_profile, load_subject_profile, select_caps_excerpt


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def target_marks(grade: int) -> tuple[int, int, int]:
    if grade <= 3:
        return 20, 45, 1200
    if grade <= 6:
        return 30, 60, 1700
    if grade <= 9:
        return 40, 90, 2200
    return 50, 120, 2700


def mark_distribution(grade: int, total: int) -> list[int]:
    return {
        20: [4, 4, 4, 4, 4],
        30: [5, 5, 6, 7, 7],
        40: [6, 7, 8, 9, 10],
        50: [8, 9, 10, 11, 12],
    }[total]


def call_local_model(model: str, prompt: str, max_tokens: int) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a careful CAPS assessment writer. Return one valid JSON object only. Do not use markdown fences."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"num_ctx": 4096, "num_predict": max_tokens, "temperature": 0.15, "top_p": 0.85},
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.load(response)
    content = str((result.get("message") or {}).get("content") or "")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Local model returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Local model output must be a JSON object")
    return value


def validate_pack(pack: dict[str, Any], grade: int, subject: str, total_marks: int) -> list[str]:
    errors = []
    if int(pack.get("grade") or 0) != grade:
        errors.append("grade does not match requested grade")
    if str(pack.get("subject") or "").strip().casefold() != subject.casefold():
        errors.append("subject does not match requested subject")
    sections = pack.get("sections")
    if not isinstance(sections, list) or not sections:
        return errors + ["exam must contain sections"]
    if len(sections) != 1:
        errors.append("exam must use one section containing five ordered questions")
    questions = []
    expected_marks = mark_distribution(grade, total_marks)
    learner_text = " ".join(str(x) for x in pack.get("student_instructions") or [])
    for section_number, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            errors.append(f"section {section_number} is not an object")
            continue
        learner_text += " " + str(section.get("instructions") or "") + " " + str(section.get("stimulus") or "")
        for question_number, question in enumerate(section.get("questions") or [], 1):
            if not isinstance(question, dict):
                errors.append(f"section {section_number} question {question_number} is not an object")
                continue
            questions.append(question)
            learner_text += " " + str(question.get("prompt") or "")
            if not str(question.get("prompt") or "").strip():
                errors.append(f"section {section_number} question {question_number} has no prompt")
            try:
                marks = int(question.get("marks"))
                if marks < 1:
                    errors.append(f"section {section_number} question {question_number} has invalid marks")
            except (TypeError, ValueError):
                errors.append(f"section {section_number} question {question_number} has invalid marks")
            if not isinstance(question.get("memo"), list) or not question.get("memo"):
                errors.append(f"section {section_number} question {question_number} has no memo points")
            else:
                memo_marks = 0
                for point in question["memo"]:
                    if not isinstance(point, dict) or not str(point.get("point") or "").strip():
                        errors.append(f"section {section_number} question {question_number} has an invalid memo point")
                        continue
                    try:
                        memo_marks += int(point.get("marks"))
                    except (TypeError, ValueError):
                        errors.append(f"section {section_number} question {question_number} has an unmarked memo point")
                if memo_marks != int(question.get("marks") or 0):
                    errors.append(f"section {section_number} question {question_number} memo marks do not reconcile")
                if len(question["memo"]) != int(question.get("marks") or 0) or any(int(point.get("marks") or 0) != 1 for point in question["memo"] if isinstance(point, dict)):
                    errors.append(f"section {section_number} question {question_number} needs one explicit one-mark memo point per mark")
            if question_number <= len(expected_marks) and int(question.get("marks") or 0) != expected_marks[question_number - 1]:
                errors.append(f"section {section_number} question {question_number} has the wrong mark value")
    actual_marks = sum(int(question.get("marks") or 0) for question in questions)
    if actual_marks != total_marks or int(pack.get("total_marks") or 0) != total_marks:
        errors.append(f"mark total must equal {total_marks}; question total is {actual_marks}")
    if len(questions) != 5:
        errors.append("exam must contain exactly five questions")
    if re.search(r"\b(picture|drawing|diagram|map|tekening|prent)\b", learner_text, re.IGNORECASE):
        errors.append("paper refers to an unembedded visual; use only printed text or data")
    bloom_levels = {
        str(question.get("bloom_level") or "").strip().casefold()
        for question in questions
    }
    if len(bloom_levels) < 3:
        errors.append("questions must cover at least three distinct grade-appropriate cognitive levels")
    if re.search(r"\b(uses simple language|shows understanding|demonstrates awareness)\b", " ".join(
        str(point.get("point") or "")
        for question in questions if isinstance(question, dict)
        for point in question.get("memo") or [] if isinstance(point, dict)
    ), re.IGNORECASE):
        errors.append("memo contains non-observable generic criteria; use specific answer evidence")
    return errors


def style_doc(document: Document, *, compact_memo: bool = False) -> None:
    section = document.sections[0]
    section.top_margin = Inches(0.45 if compact_memo else 0.65)
    section.bottom_margin = Inches(0.45 if compact_memo else 0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9.5 if compact_memo else 10.5)
    normal.font.color.rgb = RGBColor(35, 39, 45)
    normal.paragraph_format.space_after = Pt(2.5 if compact_memo else 6)
    if compact_memo:
        bullet = document.styles["List Bullet"]
        bullet.font.size = Pt(9.5)
        bullet.paragraph_format.space_after = Pt(1)
        for style_name in ("Heading 1", "Heading 2"):
            document.styles[style_name].paragraph_format.space_before = Pt(5)
            document.styles[style_name].paragraph_format.space_after = Pt(2)
    for style_name in ("Title", "Heading 1", "Heading 2"):
        style = document.styles[style_name]
        style.font.name = "Aptos Display"
        style.font.color.rgb = RGBColor(106, 77, 23)


def normalize_question_prompts(pack: dict[str, Any]) -> None:
    """Keep numbering and mark totals in the layout, not repeated in prompt text."""
    for section in pack.get("sections") or []:
        for index, question in enumerate(section.get("questions") or [], 1):
            label = str(question.get("number") or f"1.{index}")
            prompt = str(question.get("prompt") or "").strip()
            prompt = re.sub(r"^\s*" + re.escape(label) + r"\s*[.)]?\s*", "", prompt, count=1)
            try:
                marks = int(question.get("marks"))
            except (TypeError, ValueError):
                marks = -1
            if marks >= 0:
                prompt = re.sub(r"\s*\[\s*" + str(marks) + r"\s*\]\s*$", "", prompt, count=1)
                prompt = re.sub(r"\s*\(\s*" + str(marks) + r"\s+marks?\s*\)\s*$", "", prompt, count=1, flags=re.IGNORECASE)
            question["prompt"] = prompt.strip()


def render_docx(pack: dict[str, Any], path: Path, memo: bool, source_label: str) -> None:
    # Keep source data unchanged while ensuring the rendered page owns its
    # numbering and mark labels. Curated packs may already include both in
    # their prompt strings, while the renderer adds them around the prompt.
    pack = copy.deepcopy(pack)
    normalize_question_prompts(pack)
    document = Document()
    style_doc(document, compact_memo=memo and pack.get("compact_memo_layout") is True)
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(str(pack.get("exam_title") or f"{pack['subject']} Grade {pack['grade']} Assessment"))
    run.bold = True
    run.font.size = Pt(19)
    run.font.color.rgb = RGBColor(106, 77, 23)
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run(f"{pack['subject']} · Grade {pack['grade']} · {pack['total_marks']} marks · {pack['duration_minutes']} minutes").bold = True
    scope_note = str(pack.get("scope_note") or "").strip()
    if scope_note:
        note = document.add_paragraph()
        note.alignment = WD_ALIGN_PARAGRAPH.CENTER
        note_run = note.add_run(scope_note)
        note_run.italic = True
        note_run.font.size = Pt(9)
    if memo:
        document.add_heading("Educator marking memo", level=1)
        document.add_paragraph("Suggested answers and marking points. Accept equivalent correct responses appropriate to the grade.")
    else:
        document.add_paragraph("Learner name: ____________________________________     Date: __________________")
        document.add_paragraph(f"Time: {pack['duration_minutes']} minutes     Total: {pack['total_marks']} marks")
        document.add_heading("Instructions", level=1)
        for instruction in pack.get("student_instructions") or []:
            document.add_paragraph(str(instruction), style="List Bullet")
    for section_number, section in enumerate(pack.get("sections") or [], 1):
        document.add_heading(f"{section.get('title') or f'Section {section_number}'}", level=1)
        if section.get("instructions"):
            document.add_paragraph(str(section["instructions"]))
        if section.get("stimulus"):
            stimulus = document.add_paragraph()
            stimulus.paragraph_format.left_indent = Inches(0.2)
            stimulus.paragraph_format.right_indent = Inches(0.2)
            for index, line in enumerate(str(section["stimulus"]).splitlines()):
                if index:
                    stimulus.add_run().add_break()
                run = stimulus.add_run(line)
                run.italic = True
        data_table = section.get("data_table")
        if isinstance(data_table, dict):
            columns = data_table.get("columns") or []
            rows = data_table.get("rows") or []
            if columns and rows:
                caption = document.add_paragraph()
                caption.add_run(str(data_table.get("caption") or "Data table")).bold = True
                table = document.add_table(rows=1, cols=len(columns))
                try:
                    table.style = "Light Shading Accent 1"
                except KeyError:
                    table.style = "Table Grid"
                header = table.rows[0]
                header_properties = header._tr.get_or_add_trPr()
                header_marker = OxmlElement("w:tblHeader")
                header_marker.set(qn("w:val"), "true")
                header_properties.append(header_marker)
                for index, value in enumerate(columns):
                    header.cells[index].text = str(value)
                    for run in header.cells[index].paragraphs[0].runs:
                        run.bold = True
                for values in rows:
                    cells = table.add_row().cells
                    for index, value in enumerate(values):
                        cells[index].text = str(value)
        for index, question in enumerate(section.get("questions") or [], 1):
            label = str(question.get("number") or f"{section_number}.{index}")
            if memo:
                prompt = document.add_paragraph()
                prompt.add_run(f"{label} ({question.get('marks')} marks) ").bold = True
                prompt.add_run(str(question.get("prompt") or ""))
                for point in question.get("memo") or []:
                    point_marks = int(point.get("marks") or 0)
                    document.add_paragraph(f"{point.get('point')} ({point_marks} mark{'s' if point_marks != 1 else ''})", style="List Bullet")
            else:
                prompt = document.add_paragraph()
                prompt.add_run(f"{label}  ").bold = True
                prompt.add_run(str(question.get("prompt") or ""))
                prompt.add_run(f"  [{question.get('marks')}]").bold = True
    if memo:
        document.add_heading("Marking checks", level=1)
        document.add_paragraph("Confirm section totals equal the stated total. Apply the grade-appropriate memo style in the Grade Profile and moderate open-ended answers before use.")
        alignment = pack.get("caps_scope_alignment")
        if isinstance(alignment, dict):
            document.add_heading("Proposed CAPS scope trace", level=1)
            document.add_paragraph(str(alignment.get("source_scope") or alignment.get("scope_reference") or "Grade and subject scope mapping"))
            for item in alignment.get("question_mappings") or []:
                paragraph = document.add_paragraph(style="List Bullet")
                pages = item.get("caps_pdf_pages") or ([item["caps_pdf_page"]] if item.get("caps_pdf_page") else [])
                page_label = f" (CAPS PDF p. {pages[0]})" if len(pages) == 1 else (f" (CAPS PDF pp. {pages[0]}–{pages[-1]})" if pages else "")
                paragraph.add_run(f"{item.get('question')} — {item.get('caps_topic')}{page_label}: ").bold = True
                paragraph.add_run(str(item.get("coverage_link") or ""))
            document.add_paragraph(str(alignment.get("review_boundary") or "Proposed mapping; educator verification required."))
    compact_source = re.split(r"\s+·\s+SHA-256\s+", source_label, maxsplit=1)[0]
    source_note = document.add_paragraph(
        f"Source basis: {compact_source}. See the grade receipt for the official PDF URL and SHA-256."
    )
    source_note.paragraph_format.keep_together = True
    source_note.paragraph_format.space_before = Pt(3)
    source_note.paragraph_format.space_after = Pt(2)
    for source_run in source_note.runs:
        source_run.font.size = Pt(8.5)
    draft_note = document.add_paragraph("DRAFT — Qualified educator review required before classroom use.")
    draft_note.paragraph_format.keep_together = True
    draft_note.paragraph_format.space_before = Pt(0)
    draft_note.paragraph_format.space_after = Pt(0)
    for draft_run in draft_note.runs:
        draft_run.font.size = Pt(8.5)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grade", type=int, required=True)
    parser.add_argument("--subject-profile", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--caps-manifest", type=Path, required=True)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.grade <= 12:
        parser.error("grade must be between 1 and 12")
    grade = load_grade_profile(args.grade, GRADE_LADDER)
    subject_profile = load_subject_profile(args.subject_profile)
    language = "Afrikaans" if subject_profile.get("subject_id") == "afrikaans_language" else "English"
    manifest = load_manifest(args.caps_manifest)
    candidates = resolve_caps(manifest, subject_profile["subject_id"], args.grade, language, False)
    if not candidates:
        raise SystemExit(f"No hash-verified CAPS document matches {subject_profile['display_name']} in Grade {args.grade}.")
    selected = candidates[0]
    source_path = Path(str(selected["path"]))
    if not source_path.is_file() or sha256(source_path) != str(selected.get("sha256") or ""):
        raise SystemExit(f"Selected CAPS source is missing or its hash differs: {source_path}")
    source_text = extract_text(source_path, max_chars=12000)
    excerpt = select_caps_excerpt(source_text, subject_profile, grade, 2200)
    total_marks, duration_minutes, max_tokens = target_marks(args.grade)
    distribution = mark_distribution(args.grade, total_marks)
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    profile_constraints = "; ".join(str(x) for x in grade.get("question_style") or [])
    memo_style = str(grade.get("memo_style") or "Award only the marks supported by observable answer evidence.")
    question_slots = [
        {"number": f"1.{index}", "prompt": "question text", "marks": marks, "memo": [{"point": "specific one-mark criterion", "marks": 1} for _ in range(marks)], "bloom_level": "remember", "question_family": "recall"}
        for index, marks in enumerate(distribution, 1)
    ]
    prompt = f"""Write a new, CAPS-aligned {language}-language {subject_profile['display_name']} assessment and marking memo for South African Grade {args.grade}.

Grade profile: phase={grade.get('phase')}; Bloom targets={', '.join(grade.get('bloom_targets') or [])}; reading load={grade.get('reading_load')}; writing load={grade.get('writing_load')}; assessment forms={profile_constraints}.
Subject profile question families: {', '.join(subject_profile.get('question_families') or [])}.
CAPS excerpt (curriculum design authority; do not quote it verbatim):
{excerpt[:2200]}

Rules:
- Create original questions grounded in the grade/subject CAPS scope above. Do not claim this is an official DBE examination.
- Use age-appropriate language and task forms. Grades 1-3 must be concrete, short, oral/matching/short-response friendly; later grades must use the listed grade profile complexity.
- Write exactly five separate questions numbered 1.1 to 1.5. Do not combine the five into one question. Use these exact marks in order: {distribution}. Their sum and the paper total must be exactly {total_marks} marks. The assessment takes {duration_minutes} minutes.
- Each memo array contains exactly one specific marking-point object per question mark; every object is worth one mark. The question's total memo points must equal its mark value.
- Use only printed text/data stimuli in this pack. Do not refer to a picture, drawing, diagram, map or other visual because none is embedded. Each question and memo must be answerable from the printed stimulus or clearly specified grade-level subject knowledge; never ask for details absent from the stimulus.
- Use at least three distinct cognitive levels appropriate to this grade. Every mark must assess a specific, observable answer; never award marks for vague criteria such as "shows understanding" or sentence length unless that is the stated language objective.
- Do not include unsupported factual claims or fabricated source quotations.
- Do not use generic placeholders such as “CAPS core knowledge”; use a specific grade-level topic supported by the excerpt.
- {memo_style}

Return exactly this JSON shape, with no extra fields. Replace every placeholder and include all five question objects:
{{"exam_title":"...","subject":"{subject_profile['display_name']}","grade":{args.grade},"duration_minutes":{duration_minutes},"total_marks":{total_marks},"student_instructions":["..."],"sections":[{{"title":"...","instructions":"...","stimulus":"... or empty string","questions":{json.dumps(question_slots, ensure_ascii=False)}}}]}}
"""
    errors = []
    pack: dict[str, Any] | None = None
    for attempt in range(2):
        retry_prompt = prompt
        if errors and pack:
            retry_prompt += "\nThe previous pack had these structural errors; repair the full pack while preserving valid subject content: " + "; ".join(errors) + "\nPrevious pack: " + json.dumps(pack, ensure_ascii=False)
        pack = call_local_model(args.model, retry_prompt, max_tokens)
        normalize_question_prompts(pack)
        (out / f"MODEL_PACK_ATTEMPT_{attempt + 1}.json").write_text(
            json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        errors = validate_pack(pack, args.grade, subject_profile["display_name"], total_marks)
        if not errors:
            break
    if errors or not pack:
        raise SystemExit("Assessment failed exact-mark/structure validation: " + "; ".join(errors))

    pack_path = out / "HOMS_GRADE_ASSESSMENT.json"
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    exam_path = out / "GRADE_EXAM.docx"
    memo_path = out / "GRADE_MEMO.docx"
    source_label = f"DBE CAPS {selected.get('title')} · {selected.get('phase')}"
    render_docx(pack, exam_path, False, source_label)
    render_docx(pack, memo_path, True, source_label)
    receipt = {
        "schema": "dio.homs.grade_exam_candidate_receipt.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "grade": args.grade,
        "subject": subject_profile["display_name"],
        "subject_profile": subject_profile["subject_id"],
        "randomization_seed": args.seed,
        "model": args.model,
        "local_generation": True,
        "caps_source": {"title": selected.get("title"), "phase": selected.get("phase"), "path": str(source_path), "source_url": selected.get("source_url"), "sha256": sha256(source_path)},
        "assessment": {"total_marks": total_marks, "validated_question_marks": sum(int(q["marks"]) for section in pack["sections"] for q in section["questions"]), "question_count": sum(len(section["questions"]) for section in pack["sections"]), "exam": {"path": str(exam_path), "sha256": sha256(exam_path)}, "memo": {"path": str(memo_path), "sha256": sha256(memo_path)}, "json": {"path": str(pack_path), "sha256": sha256(pack_path)}},
        "validation": {"exact_mark_total": True, "question_memos_present": True, "age_profile_bound": True, "educator_review_required": True},
        "release_authorized": False,
        "classroom_approval": "PENDING_QUALIFIED_EDUCATOR_REVIEW",
    }
    receipt_path = out / "HOMS_GRADE_EXAM_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": "DRAFT_PACK_CREATED", "grade": args.grade, "subject": subject_profile["display_name"], "out": str(out), "marks": total_marks, "exam_sha256": sha256(exam_path), "memo_sha256": sha256(memo_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
