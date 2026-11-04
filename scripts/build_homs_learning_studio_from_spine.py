#!/usr/bin/env python3
"""Build a subject-specific Learning Studio companion from an Exam Studio spine."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from products.homs_curriculum_spine import SCHEMA
from scripts.build_homs_learning_pack import GOLDEN_VIDEO_DIR, GOLDEN_VIDEO_FILES, convert_pdfs

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "deliverables" / "homs_learning_studio" / "exam_linked"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_spine(path: Path) -> dict[str, Any]:
    spine = json.loads(path.read_text(encoding="utf-8"))
    if spine.get("schema") != SCHEMA:
        raise ValueError(f"Unsupported curriculum spine schema: {spine.get('schema')}")
    if (spine.get("authority") or {}).get("educator_approval_required") is not True:
        raise ValueError("Curriculum spine is missing the human educator approval gate")
    if spine.get("status") != "educator_review_required":
        raise ValueError("Curriculum spine status is not eligible for educator review")
    curriculum = spine.get("curriculum") or {}
    if not curriculum.get("subject") or not curriculum.get("grade"):
        raise ValueError("Curriculum spine must identify a subject and grade")
    if not (spine.get("opportunities") or {}).get("first", {}).get("questions"):
        raise ValueError("Curriculum spine has no first-opportunity questions")
    return spine


def safe_source(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Curriculum spine path escapes workspace: {relative}") from exc
    return path


def add_header(doc: Document, title: str, spine: dict[str, Any], subtitle: str) -> None:
    course = spine["curriculum"]
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(31, 43, 50)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("HOMS  /  LEARNING STUDIO")
    run.bold = True
    run.font.color.rgb = RGBColor(7, 95, 91)
    doc.add_heading(title, 0)
    p = doc.add_paragraph(subtitle)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph(
        f"{course.get('subject')}  ·  Grade {course.get('grade')}  ·  {course.get('phase') or 'Phase not recorded'}  ·  Term {course.get('term') or 'not specified'}"
    )
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].bold = True
    doc.add_paragraph(f"Topics: {'; '.join(course.get('topics') or []) or course.get('topic') or 'See linked assessment'}")
    doc.add_paragraph("Draft for educator and subject-expert review. Not approved for classroom use.")
    doc.add_paragraph(f"Bound to Exam Studio job: {spine.get('job_id')}")


def add_visuals(doc: Document, visual_assets: list[dict[str, Any]], copied_assets: dict[str, Path]) -> None:
    for row in visual_assets:
        if row.get("kind") != "png":
            continue
        image = copied_assets.get(str(row.get("path") or ""))
        if image and image.is_file():
            doc.add_heading(str(row.get("title") or "Assessment visual"), level=2)
            doc.add_picture(str(image), width=Inches(6.1))


def build_student_guide(spine: dict[str, Any], out: Path, copied_assets: dict[str, Path]) -> None:
    doc = Document()
    add_header(doc, "Your subject revision route", spine, "Understand the idea. Read the evidence. Try the question. Explain your reasoning.")
    doc.add_heading("How to use this pack", level=1)
    doc.add_paragraph("Work through one section at a time. First attempt each prompt without the memorandum. Mark any words, diagrams, data or steps you do not understand; your educator can use those to plan the next lesson.")
    design = spine.get("learning_design") or {}
    doc.add_heading("Thinking skills in this assessment", level=1)
    doc.add_paragraph("Grade-level Bloom targets: " + ", ".join(design.get("bloom_targets") or ["not recorded"]) + ".")
    distribution = design.get("actual_bloom_mark_distribution") or {}
    if distribution:
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light Shading Accent 1"
        for i, value in enumerate(("Bloom level", "Marks", "Share of marks")):
            table.rows[0].cells[i].text = value
        for level, row in distribution.items():
            cells = table.add_row().cells
            cells[0].text, cells[1].text, cells[2].text = str(level), str(row.get("marks", 0)), f"{row.get('percent', 0)}%"
    for card in (spine.get("opportunities") or {}).get("first", {}).get("evidence_cards") or []:
        if card.get("content"):
            doc.add_heading(f"{card.get('label') or 'Source'} · {card.get('title') or card.get('type') or 'Read this source'}", level=1)
            doc.add_paragraph(str(card["content"]))
            if card.get("provenance"):
                p = doc.add_paragraph("Source note: " + str(card["provenance"]))
                p.runs[0].italic = True
    first = (spine.get("opportunities") or {}).get("first") or {}
    for question in first.get("questions") or []:
        doc.add_page_break()
        doc.add_heading(f"Practice {question.get('number') or ''} · {question.get('marks') or 0} marks", level=1)
        labels = [str(question.get("bloom_level") or "Bloom level not tagged"), str(question.get("question_family") or "question form not tagged")]
        doc.add_paragraph("Skill focus: " + " · ".join(labels))
        if question.get("source_reference"):
            doc.add_paragraph("Source: " + str(question["source_reference"]))
        if question.get("visual_reference"):
            doc.add_paragraph("Use visual/source reference: " + str(question["visual_reference"]))
        doc.add_paragraph(str(question.get("question") or "Review the linked exam paper."))
        for _ in range(min(8, max(3, int(question.get("marks") or 3) // 2))):
            doc.add_paragraph("________________________________________________________________________________")
        doc.add_paragraph("After trying it: Which concept or piece of evidence helped you most?")
    doc.add_page_break()
    doc.add_heading("Review the diagrams and source material", level=1)
    doc.add_paragraph("Use the matching paper and referenced visual assets. Ask your educator for a larger or accessible version if a label is difficult to read.")
    add_visuals(doc, spine.get("visual_assets") or [], copied_assets)
    doc.save(out)


def build_educator_guide(spine: dict[str, Any], out: Path, copied_assets: dict[str, Path]) -> None:
    doc = Document()
    add_header(doc, "Educator lesson and marking map", spine, "Teach the same curriculum spine that produced the assessment.")
    doc.add_heading("Curriculum and assessment design", level=1)
    design = spine.get("learning_design") or {}
    for key, label in (("bloom_targets", "Grade Bloom targets"), ("question_styles", "Grade question styles"), ("question_families", "Subject question families")):
        doc.add_paragraph(f"{label}: " + ", ".join(design.get(key) or ["not recorded"]))
    for source in spine.get("curriculum_sources") or []:
        doc.add_paragraph(f"Curriculum source: {source.get('title')} · SHA-256 {source.get('sha256') or 'not recorded'}")
    if spine.get("curriculum_source_status") != "resolved_and_hash_recorded":
        p = doc.add_paragraph("BLOCKER: no resolved, hash-recorded CAPS source is attached. Confirm official subject, grade and term scope before approval.")
        p.runs[0].bold = True
    unsupported = (spine.get("visual_blueprint") or {}).get("source_type_contract", {}).get("unsupported_requested_source_types") or []
    if unsupported:
        doc.add_paragraph("Requested evidence types not included because they fall outside the selected subject/assessment contract: " + ", ".join(str(item) for item in unsupported))
    doc.add_heading("Teach, practise, check", level=1)
    first = (spine.get("opportunities") or {}).get("first") or {}
    for question in first.get("questions") or []:
        doc.add_heading(f"{question.get('number') or 'Item'} · {question.get('marks') or 0} marks", level=2)
        doc.add_paragraph(f"Bloom: {question.get('bloom_level') or 'not item-tagged'} · Family: {question.get('question_family') or 'not item-tagged'}")
        doc.add_paragraph("Learner prompt: " + str(question.get("question") or "See linked paper."))
        p = doc.add_paragraph("DRAFT TEACHING-SEQUENCE PLANNER · educator completes and approves")
        p.runs[0].bold = True
        sequence = doc.add_table(rows=1, cols=3)
        sequence.style = "Light Shading Accent 1"
        for cell, label in zip(sequence.rows[0].cells, ("Stage", "Educator planning prompt", "Notes / source reference"), strict=True):
            cell.text = label
        sequence_rows = [
            ("1 · Connect", "What prior knowledge should learners retrieve? Record an opening question or short diagnostic.", ""),
            ("2 · Teach", "Name the concept and use an approved curriculum source. Record the relevant CAPS section and page.", ""),
            ("3 · Model", "Work a parallel example aloud; explain the steps and the evidence used.", ""),
            ("4 · Guided practice", "Set one new, similar example. Note the expected response and feedback cue.", ""),
            ("5 · Check", "Use a short formative check. Record the success criterion and likely misconception.", ""),
            ("6 · Support / extend", "Plan an accessible support and a suitable extension for different learner needs.", ""),
            ("7 · Independent practice", "Use the bound assessment prompt only after teaching; plan how responses will inform reteaching.", ""),
        ]
        for stage, prompt, notes in sequence_rows:
            cells = sequence.add_row().cells
            cells[0].text, cells[1].text, cells[2].text = stage, prompt, notes
        doc.add_paragraph("Sequence completeness: [ ] source and page confirmed  [ ] example checked  [ ] accessible support planned  [ ] formative check prepared  [ ] educator approval recorded")
        if question.get("memo"):
            doc.add_paragraph("Memo points (educator only):")
            for point in question["memo"]:
                doc.add_paragraph(str(point), style="List Bullet")
    doc.add_heading("Visuals and sources", level=1)
    add_visuals(doc, spine.get("visual_assets") or [], copied_assets)
    doc.add_heading("Subject-expert approval", level=1)
    for point in [
        "Verify subject accuracy, curriculum scope and grade appropriateness.",
        "Recalculate every answer and confirm the memo accepts valid alternative reasoning.",
        "Confirm source permission, context, accessibility and visual legibility.",
        "Approve language, teaching sequence, exam equivalence and classroom use.",
    ]:
        doc.add_paragraph(point, style="List Bullet")
    doc.save(out)


def build_storyboard(spine: dict[str, Any]) -> dict[str, Any]:
    course = spine.get("curriculum") or {}
    first = (spine.get("opportunities") or {}).get("first") or {}
    visuals = spine.get("visual_blueprint") or {}
    return {
        "schema": "dio.homs.learning_video_storyboard.v1",
        "status": "script_draft_requires_subject_expert_review",
        "subject": course.get("subject"), "grade": course.get("grade"), "term": course.get("term"),
        "source_curriculum_spine": spine.get("job_id"),
        "no_model_generation_used": True,
        "release_gate": "human_subject_expert_approval_required",
        "visual_source_plan": visuals.get("required_visuals") or [],
        "scenes": [
            {
                "scene_id": f"scene_{index:02d}",
                "assessment_item": question.get("number"),
                "title": question.get("question_family") or question.get("section") or "Subject skill",
                "bloom_level": question.get("bloom_level"),
                "visual_reference": question.get("visual_reference") or question.get("source_reference"),
                "learner_prompt": question.get("question"),
                "educator_narration_seed": " ".join(question.get("memo") or []),
                "check_for_understanding": question.get("question"),
                "review_required": True,
            }
            for index, question in enumerate(first.get("questions") or [], start=1)
        ],
    }


def copy_matching_golden_video(spine: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    course = spine.get("curriculum") or {}
    subject = str(course.get("subject") or "").casefold()
    grade = str(course.get("grade") or "")
    term = str(course.get("term") or "")
    topic_text = " ".join([str(course.get("topic") or ""), *(str(item) for item in course.get("topics") or [])]).casefold()
    motion_scope = "motion" in topic_text and ("dimension" in topic_text or "1d" in topic_text or "one d" in topic_text)
    if subject != "physical sciences" or grade != "10" or term != "3" or not motion_scope:
        return {"status": "no_exact_golden_video_match", "assets": [], "release_gate": "human_subject_expert_approval_required"}
    missing = [name for name in GOLDEN_VIDEO_FILES if not (GOLDEN_VIDEO_DIR / name).is_file()]
    if missing:
        return {"status": "matching_video_bundle_incomplete", "assets": [], "missing_assets": missing, "release_gate": "blocked_pending_asset_recovery"}
    target_dir = out_dir / "video"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in (*GOLDEN_VIDEO_FILES, "metadata_package.json", "render_manifest.json", "script_manifest.json"):
        source = GOLDEN_VIDEO_DIR / name
        if not source.is_file():
            continue
        target = target_dir / name
        shutil.copy2(source, target)
        copied.append({"path": str(target.relative_to(out_dir)), "sha256": sha256(target), "bytes": target.stat().st_size})
    return {
        "status": "exact_subject_grade_term_video_attached_for_review",
        "assets": copied,
        "release_gate": "human_subject_expert_approval_required",
        "rights_and_attribution_included": True,
    }


def build_educator_planning_surface(spine: dict[str, Any], out_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Create an offline educator planning worksheet with resumable local drafts."""
    course = spine.get("curriculum") or {}
    first = (spine.get("opportunities") or {}).get("first") or {}
    questions = first.get("questions") or []
    spine_path = Path(str(spine.get("_spine_path") or ""))
    source_hash = sha256(spine_path) if spine_path.is_file() else ""
    course_record = {
        "grade": course.get("grade"), "subject": course.get("subject"),
        "phase": course.get("phase"), "term": course.get("term"),
        "topics": course.get("topics") or [],
    }
    planning_fields = [
        ("prior_knowledge", "Prior knowledge to check", "What should learners already know? What evidence will show it?"),
        ("teacher_model", "Teacher model or worked example", "Write the example or explanation you will teach and verify."),
        ("guided_practice", "Guided practice", "Describe the supported practice and prompts learners will use."),
        ("formative_check", "Formative check", "What will learners do, and what response will show understanding?"),
        ("differentiation", "Access and differentiation", "Note language, accessibility, support, and extension needs."),
        ("independent_practice", "Independent practice", "Describe practice learners can complete without prompts."),
        ("pacing", "Pacing and lesson sequence", "Record order, estimated time, and any prerequisite lesson."),
    ]
    items = []
    for index, question in enumerate(questions):
        qid = str(question.get("number") or f"Q{index + 1}")
        prompt = str(question.get("question") or "Review the linked assessment prompt.")
        item = {
            "question_id": qid,
            "question_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "question": prompt,
            "mark_allocation": question.get("marks"),
            "fields": {key: "" for key, _, _ in planning_fields},
        }
        items.append(item)
    fingerprint_source = json.dumps({"source_spine_sha256": source_hash, "course": course_record,
                                     "questions": [{"question_id": row["question_id"], "question_sha256": row["question_sha256"]} for row in items]},
                                    ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    question_markup = []
    for row in items:
        controls = []
        for key, label, help_text in planning_fields:
            controls.append(
                "<label class='field'><span>" + html.escape(label) + "</span><small>" + html.escape(help_text) + "</small>"
                + "<textarea data-question='" + html.escape(row["question_id"], quote=True)
                + "' data-field='" + html.escape(key, quote=True) + "' rows='3'></textarea></label>"
            )
        question_markup.append(
            "<section class='question'><p class='eyebrow'>QUESTION " + html.escape(row["question_id"]) + " · "
            + html.escape(str(row["mark_allocation"] or "—")) + " MARKS</p><h2>" + html.escape(row["question"])
            + "</h2><code>Prompt SHA-256 " + row["question_sha256"] + "</code><div class='grid'>"
            + "".join(controls) + "</div></section>"
        )
    field_template = json.dumps({"schema": "dio.homs.learning_studio.educator_lesson_plan_draft.v1",
                                 "course": course_record, "source_spine_sha256": source_hash,
                                 "planning_questions": items,
                                 "draft_state": "INCOMPLETE", "educator_approval_recorded": False,
                                 "classroom_release_authorized": False}, ensure_ascii=False).replace("<", "\\u003c")
    filename = f"HOMS_G{int(course.get('grade') or 0):02d}_{re.sub(r'[^a-z0-9]+', '_', str(course.get('subject') or '').casefold()).strip('_')}_EDUCATOR_LESSON_PLAN.json"
    page = out_dir / "EDUCATOR_LESSON_PLANNER.html"
    page.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>HOMS Learning Studio · educator lesson planner</title><style>"
        "body{margin:0;background:#f4f6f5;color:#20302f;font:16px/1.55 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:30px 20px 70px}h1{line-height:1.2}h2{font-size:1.2rem;line-height:1.4}.eyebrow{font:700 12px system-ui;letter-spacing:.09em;color:#176b68}.banner,.notice{padding:15px 18px;background:#fff7e8;border-left:4px solid #a66a27;margin:18px 0}.question{background:#fff;border:1px solid #ccd5cf;border-radius:10px;margin:22px 0;padding:20px}.question code{font-size:11px;color:#596a66;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}.field{display:grid;gap:5px}.field span{font-weight:650}.field small{color:#566963;min-height:2.5em}.field textarea{box-sizing:border-box;width:100%;min-height:82px;font:inherit;padding:9px;border:1px solid #839b95;border-radius:5px}.field textarea:focus-visible,button:focus-visible{outline:3px solid #a66a27;outline-offset:2px}.actions{position:sticky;bottom:0;background:#f4f6f5ed;border-top:1px solid #cbd4ce;padding:14px;display:flex;gap:10px;flex-wrap:wrap}button{font:600 14px system-ui;padding:11px 15px;border:1px solid #176b68;border-radius:5px;background:#176b68;color:white;cursor:pointer}button.secondary{background:white;color:#176b68}.status{margin-left:auto;align-self:center;color:#36534c;font-size:13px}footer{margin-top:30px;color:#566963;font-size:13px;overflow-wrap:anywhere}@media(max-width:700px){.grid{grid-template-columns:1fr}.actions{position:static}.status{width:100%;margin:0}}</style></head><body><main>"
        "<p class='eyebrow'>HOMS LEARNING STUDIO · EDUCATOR PLANNING</p><h1>" + html.escape(str(course.get("subject") or "Learning"))
        + " · Grade " + html.escape(str(course.get("grade") or "—")) + "</h1><p>" + html.escape(" · ".join(str(x) for x in [course.get("phase"), ("Term " + str(course.get("term"))) if course.get("term") else "Term not specified"]))
        + "</p><div class='banner'><strong>Plan draft only.</strong> This page does not write lesson content for you. Complete each educator field, then save a private draft in this browser or download a JSON plan. A completed plan is not educator approval and does not authorize classroom release.</div>"
        + "<p>Course topic: " + html.escape("; ".join(str(value) for value in course.get("topics") or []) or str(course.get("topic") or "See linked curriculum spine"))
        + "</p><p>CAPS source: " + html.escape(str((spine.get("curriculum_sources") or [{}])[0].get("title") or "Source in curriculum spine"))
        + " · SHA-256 <code>" + source_hash + "</code></p>"
        + "<p class='notice'>Use the linked educator guide, exact question, source spine, and CAPS excerpts together. Verify curriculum coverage, term fit, examples, memo accuracy, access needs, and any learner-facing adaptations before use.</p>"
        + "".join(question_markup) + "<div class='actions'><button id='save-local' type='button'>Save draft in this browser</button>"
        + "<button id='download' class='secondary' type='button'>Download lesson-plan JSON</button>"
        + "<button id='clear-local' class='secondary' type='button'>Clear local draft</button><span id='status' class='status' role='status'>No local draft saved</span></div>"
        + "<footer>Source-spine fingerprint: <code>" + fingerprint + "</code><br>Local browser storage only. The download remains an educator planning draft; approval and release controls stay outside this file.</footer></main>"
        + "<script type='application/json' id='plan-template'>" + field_template + "</script><script>(function(){"
        + "const key='dio-homs-learning-plan-" + fingerprint + "';const template=JSON.parse(document.getElementById('plan-template').textContent);"
        + "const controls=[...document.querySelectorAll('textarea[data-question]')];const status=document.getElementById('status');"
        + "function values(){const result=JSON.parse(JSON.stringify(template));for(const q of result.planning_questions){for(const el of controls){if(el.dataset.question===q.question_id)q.fields[el.dataset.field]=el.value}}"
        + "result.draft_state=result.planning_questions.length&&result.planning_questions.every(q=>Object.values(q.fields).every(v=>v.trim()))?'EDUCATOR_PLANNING_FIELDS_COMPLETE':'INCOMPLETE';"
        + "result.educator_approval_recorded=false;result.classroom_release_authorized=false;return result}"
        + "function restore(){try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(!saved)return;for(const q of saved.planning_questions||[])for(const el of controls)if(el.dataset.question===q.question_id)el.value=(q.fields||{})[el.dataset.field]||'';status.textContent='Local draft restored'}catch(e){status.textContent='Local draft could not be read'}}"
        + "document.getElementById('save-local').addEventListener('click',()=>{try{localStorage.setItem(key,JSON.stringify(values()));status.textContent='Saved in this browser only'}catch(e){status.textContent='Browser storage unavailable; download the JSON draft instead'}});"
        + "document.getElementById('clear-local').addEventListener('click',()=>{localStorage.removeItem(key);controls.forEach(el=>el.value='');status.textContent='Local draft cleared'});"
        + "document.getElementById('download').addEventListener('click',()=>{const data=values();data.exported_at_utc=new Date().toISOString();const blob=new Blob([JSON.stringify(data,null,2)+'\\n'],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='" + filename + "';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);status.textContent='Downloaded educator planning draft'});"
        + "restore();})();</script></body></html>\n", encoding="utf-8")
    try:
        page.chmod(0o600)
    except OSError:
        pass
    manifest = {
        "path": str(page.relative_to(out_dir)), "sha256": sha256(page),
        "question_count": len(items), "planning_fields_per_question": len(planning_fields),
        "local_draft_storage": True, "external_processing": False,
        "approval_recorded": False, "classroom_release_authorized": False,
        "source_spine_sha256": source_hash, "source_fingerprint": fingerprint,
    }
    return page, manifest


def build(spine_path: Path, out_dir: Path) -> dict[str, Any]:
    spine_path = spine_path.expanduser().resolve()
    spine = load_spine(spine_path)
    spine["_spine_path"] = str(spine_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    document_dir = out_dir / "documents"
    visual_dir = out_dir / "visuals"
    document_dir.mkdir(exist_ok=True)
    visual_dir.mkdir(exist_ok=True)
    copied_assets: dict[str, Path] = {}
    visual_manifest = []
    for index, row in enumerate(spine.get("visual_assets") or [], start=1):
        source = safe_source(str(row.get("path") or ""))
        if not source.is_file() or sha256(source) != str(row.get("sha256") or ""):
            raise ValueError(f"Visual asset missing or hash mismatch: {row.get('path')}")
        name = f"{index:02d}_{source.name}"
        target = visual_dir / name
        shutil.copy2(source, target)
        copied_assets[str(row.get("path"))] = target
        visual_manifest.append({"title": row.get("title"), "path": str(target.relative_to(out_dir)), "sha256": sha256(target), "kind": row.get("kind")})
    spine_copy = out_dir / "HOMS_CURRICULUM_SPINE.json"
    shutil.copy2(spine_path, spine_copy)
    student = document_dir / "HOMS_LEARNER_REVISION_ROUTE.docx"
    educator = document_dir / "HOMS_EDUCATOR_LESSON_AND_MARKING_MAP.docx"
    build_student_guide(spine, student, copied_assets)
    build_educator_guide(spine, educator, copied_assets)
    generated_docs = [student, educator]
    first_opportunity = (spine.get("opportunities") or {}).get("first") or {}
    if not first_opportunity.get("questions"):
        raise ValueError("Exam-linked Learning Studio requires question-level metadata")
    for role, key in (("PAPER", "paper_path"), ("MEMO", "memo_path")):
        relative = str(first_opportunity.get(key) or "").strip()
        if not relative:
            raise ValueError(f"Exam-linked Learning Studio requires the first-opportunity {role.lower()} path")
        source = safe_source(relative)
        if not source.is_file() or source.suffix.casefold() != ".docx":
            raise ValueError(f"Exam-linked Learning Studio cannot find the first-opportunity {role.lower()}: {relative}")
        expected_hash = str(first_opportunity.get(f"{role.lower()}_sha256") or "")
        if not expected_hash or sha256(source) != expected_hash:
            raise ValueError(f"Exam-linked Learning Studio {role.lower()} hash does not match the curriculum spine")
        target = document_dir / f"HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_{role}.docx"
        shutil.copy2(source, target)
        generated_docs.append(target)
    pdfs = convert_pdfs(generated_docs, out_dir / "pdf")
    storyboard = out_dir / "HOMS_LEARNING_VIDEO_STORYBOARD.json"
    storyboard_data = build_storyboard(spine)
    storyboard.write_text(json.dumps(storyboard_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    video_status = copy_matching_golden_video(spine, out_dir)
    educator_planner_path, educator_planner = build_educator_planning_surface(spine, out_dir)
    validation = {
        "schema": "dio.homs.learning_studio_from_spine.validation.v1",
        "passed": True,
        "spine_sha256": sha256(spine_path),
        "question_count": len((spine.get("opportunities") or {}).get("first", {}).get("questions") or []),
        "lesson_sequence_planner_count": len((spine.get("opportunities") or {}).get("first", {}).get("questions") or []),
        "interactive_educator_planner": {
            "path": educator_planner["path"], "sha256": educator_planner["sha256"],
            "question_count": educator_planner["question_count"],
            "planning_fields_per_question": educator_planner["planning_fields_per_question"],
            "all_fields_initially_blank": True,
            "local_draft_storage": True, "external_processing": False,
            "educator_approval_recorded": False, "classroom_release_authorized": False,
        },
        "instructional_content_fabricated": False,
        "visual_asset_count": len(visual_manifest),
        "source_hashes_verified": True,
        "educator_approval_required": True,
        "classroom_release": "blocked_pending_approval",
        "authority_created": False,
        "external_effects": False,
    }
    manifest = {
        "schema": "dio.homs.learning_studio_bundle.v1",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "educator_review_required",
        "source_curriculum_spine": spine.get("job_id"),
        "curriculum": spine.get("curriculum"),
        "learning_design": spine.get("learning_design"),
        "documents": [{"path": str(path.relative_to(out_dir)), "sha256": sha256(path)} for path in generated_docs + pdfs],
        "visual_assets": visual_manifest,
        "video_storyboard": {"path": str(storyboard.relative_to(out_dir)), "sha256": sha256(storyboard)},
        "educator_planner": educator_planner,
        "video_bundle": video_status,
        "validation": validation,
    }
    validation_path = out_dir / "HOMS_LEARNING_STUDIO_VALIDATION.json"
    manifest_path = out_dir / "HOMS_LEARNING_STUDIO_MANIFEST.json"
    validation_path.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    preview = out_dir / "index.html"
    preview_html = "".join([
        "<!doctype html><meta charset='utf-8'><title>HOMS Learning Studio</title>",
        "<main style='font:16px/1.5 system-ui;max-width:900px;margin:40px auto'>",
        f"<h1>{html.escape(str((spine.get('curriculum') or {}).get('subject') or 'HOMS Learning Studio'))} learning companion</h1>",
        f"<p>Grade {html.escape(str((spine.get('curriculum') or {}).get('grade') or ''))} · {html.escape(str((spine.get('curriculum') or {}).get('term') or ''))} · Educator review required.</p>",
        "<h2>Open the pack</h2><ul>",
        "".join(f"<li><a href='{html.escape(str(path.relative_to(out_dir)))}'>{html.escape(path.name)}</a></li>" for path in generated_docs + pdfs),
        "</ul>",
        f"<p><a href='{html.escape(educator_planner_path.name)}'>Interactive educator lesson planner · source-bound draft</a></p>",
        f"<p><a href='{html.escape(storyboard.name)}'>Video storyboard · script draft</a></p>",
        "<h2>Reviewed matching video</h2><video controls preload='metadata' style='width:100%;max-width:760px' src='video/HOMS_G10_T3_MOTION_VIDEO_LESSON.mp4'></video><p>Includes captions, rights receipt and music attribution; educator approval is still required.</p>" if video_status.get("status") == "exact_subject_grade_term_video_attached_for_review" else "",
        f"<p><a href='{html.escape(manifest_path.name)}'>Bundle manifest</a></p><p>{validation['question_count']} assessment-linked prompts · {len(visual_manifest)} visuals · no external effects.</p></main>",
    ])
    preview.write_text(preview_html, encoding="utf-8")
    # Pictora imagery adds a subject-matched visual layer to the HTML review
    # surface. It remains decorative and separately gated from learning evidence.
    from products.pictora_visual_studio import attach_html_visual
    pictora_visual = attach_html_visual(
        preview, product="homs_learning_studio",
        context=str((spine.get("curriculum") or {}).get("subject") or ""),
    )
    manifest["pictora_visual"] = pictora_visual
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bundle = out_dir / "HOMS_LEARNING_STUDIO_ASSESSMENT_LINKED_BUNDLE.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        video_files = [out_dir / str(item.get("path") or "") for item in video_status.get("assets") or []]
        archive_paths = [*generated_docs, *pdfs, *[visual_dir / Path(item["path"]).name for item in visual_manifest], *video_files, spine_copy, storyboard, educator_planner_path, validation_path, manifest_path, preview]
        if pictora_visual.get("asset"):
            archive_paths.append(Path(pictora_visual["asset"]))
        if pictora_visual.get("receipt"):
            archive_paths.append(Path(pictora_visual["receipt"]))
        for path in archive_paths:
            if path.is_file():
                archive.write(path, path.relative_to(out_dir))
    return {"status": "educator_review_required", "out_dir": str(out_dir), "bundle": str(bundle), "documents": len(generated_docs), "pdfs": len(pdfs), "visuals": len(visual_manifest), "questions": validation["question_count"], "provider_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curriculum-spine", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.curriculum_spine, args.out.resolve())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
