"""Customer-facing delivery of randomized, CAPS-source-mapped draft exams."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
SET_RECEIPT = PACK / "GRADE_EXAM_SET_RECEIPT.json"
ASSIGNMENTS = PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json"
CAPS_ALIGNMENT = PACK / "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"
PDF_MANIFEST = PACK / "PRINT_READY_PDF_MANIFEST.json"
CAPS_CORPUS = ROOT / "corpora/caps/caps_corpus_manifest.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _caps_page_text(pdf: Path, page: int) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
        check=True, capture_output=True, text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise ValueError(f"CAPS source page {page} contains no extractable text")
    return value


def _memo_point_rows(question: Mapping[str, Any]) -> list[dict[str, Any]]:
    memo = question.get("memo") or []
    rows = []
    for item in memo:
        if isinstance(item, Mapping):
            rows.append({"point": str(item.get("point") or ""), "marks": float(item.get("marks") or 0)})
        else:
            rows.append({"point": str(item), "marks": None})
    return rows


def _cognitive_label(raw_value: Any) -> tuple[str, str]:
    raw = str(raw_value or "").strip().casefold()
    if raw == "analyse":
        return "analyze", "RECOGNIZED_BRITISH_SPELLING"
    if raw == "explain":
        return "understand", "VERB_EQUIVALENT_REQUIRES_EDUCATOR_CONFIRMATION"
    if raw in {"remember", "understand", "apply", "analyze", "evaluate", "create"}:
        return raw, "RECOGNIZED_CANONICAL"
    return "REVIEW_UNCLASSIFIED", "NEEDS_EDUCATOR_CLASSIFICATION"


def validate_item_quality_review_csv(
    csv_path: str | Path,
    expected_rows: list[dict[str, Any]],
    *,
    source_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Validate a returned educator matrix against bound exam/CAPS/memo rows."""
    path = Path(csv_path).resolve()
    required = {
        "grade", "subject", "question_id", "caps_topic", "caps_physical_pdf_pages", "question_prompt",
        "draft_cognitive_level", "draft_cognitive_level_normalized", "draft_cognitive_level_label_state",
        "draft_question_family", "question_marks", "memo_point_count", "memo_points_and_marks",
        "educator_confirmed_cognitive_level", "educator_reasoning_demand", "educator_grade_term_fit",
        "educator_caps_alignment", "educator_memo_alignment", "educator_mark_allocation_fit",
        "educator_language_accessibility", "required_revision", "educator_decision", "educator_rationale",
        "educator_reviewer", "reviewed_at",
    }
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if not required.issubset(fields):
            return {"schema": "dio.homs.exam.item_quality_review_validation.v1", "state": "INVALID_REVIEW_TEMPLATE",
                    "issues": [{"code": "REQUIRED_FIELDS_MISSING", "fields": sorted(required - fields)}],
                    "source_hashes": dict(source_hashes), "independent_moderation_decision": "NOT_ISSUED",
                    "classroom_release_authorized": False}
        observed = list(reader)
    expected = {str(row["question_id"]): row for row in expected_rows}
    issues: list[dict[str, Any]] = []
    missing_fields: list[dict[str, str]] = []
    duplicate_ids: set[str] = set()
    observed_by_id: dict[str, dict[str, str]] = {}
    source_fields = ("grade", "subject", "caps_topic", "caps_physical_pdf_pages", "question_prompt",
                     "draft_cognitive_level", "draft_cognitive_level_normalized", "draft_cognitive_level_label_state",
                     "draft_question_family", "question_marks", "memo_point_count", "memo_points_and_marks")
    educator_fields = ("educator_confirmed_cognitive_level", "educator_reasoning_demand", "educator_grade_term_fit",
                       "educator_caps_alignment", "educator_memo_alignment", "educator_mark_allocation_fit",
                       "educator_language_accessibility", "educator_decision", "educator_rationale", "educator_reviewer", "reviewed_at")
    allowed_levels = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
    categorical = ("educator_grade_term_fit", "educator_caps_alignment", "educator_memo_alignment",
                   "educator_mark_allocation_fit", "educator_language_accessibility")
    decisions = set()
    for line, row in enumerate(observed, 2):
        question_id = str(row.get("question_id") or "").strip()
        if question_id not in expected:
            issues.append({"line": line, "code": "UNKNOWN_QUESTION_ID", "question_id": question_id})
            continue
        if question_id in observed_by_id:
            duplicate_ids.add(question_id)
            issues.append({"line": line, "code": "DUPLICATE_QUESTION_ID", "question_id": question_id})
            continue
        observed_by_id[question_id] = row
        for field in source_fields:
            if str(row.get(field) or "").strip() != str(expected[question_id].get(field) or "").strip():
                issues.append({"line": line, "code": "SOURCE_BOUND_QUESTION_FIELD_CHANGED", "question_id": question_id, "field": field})
        normalized, label_state = _cognitive_label(row.get("draft_cognitive_level"))
        if row.get("draft_cognitive_level_normalized") != normalized or row.get("draft_cognitive_level_label_state") != label_state:
            issues.append({"line": line, "code": "COGNITIVE_LABEL_NORMALIZATION_MISMATCH", "question_id": question_id})
        for field in educator_fields:
            if not str(row.get(field) or "").strip():
                missing_fields.append({"question_id": question_id, "field": field})
        level = str(row.get("educator_confirmed_cognitive_level") or "").strip().casefold()
        if level and level not in allowed_levels:
            issues.append({"line": line, "code": "INVALID_CONFIRMED_COGNITIVE_LEVEL", "question_id": question_id})
        for field in categorical:
            value = str(row.get(field) or "").strip().upper()
            if value and value not in {"FIT", "REVISE", "UNRESOLVED"}:
                issues.append({"line": line, "code": "INVALID_REVIEW_CATEGORY", "question_id": question_id, "field": field})
        decision = str(row.get("educator_decision") or "").strip().upper()
        if decision:
            decisions.add(decision)
            if decision not in {"APPROVE_FOR_MODERATION", "REVISE", "UNRESOLVED"}:
                issues.append({"line": line, "code": "INVALID_EDUCATOR_DECISION", "question_id": question_id})
            if decision == "REVISE" and not str(row.get("required_revision") or "").strip():
                issues.append({"line": line, "code": "REVISION_DECISION_REQUIRES_ACTION", "question_id": question_id})
            if decision == "APPROVE_FOR_MODERATION" and any(str(row.get(field) or "").strip().upper() != "FIT" for field in categorical):
                issues.append({"line": line, "code": "APPROVAL_REQUIRES_FIT_FOR_ALL_REVIEW_CATEGORIES", "question_id": question_id})
        if row.get("reviewed_at"):
            try:
                parsed = datetime.fromisoformat(str(row["reviewed_at"]).strip().replace("Z", "+00:00"))
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise ValueError("timestamp must include a timezone")
            except ValueError:
                issues.append({"line": line, "code": "REVIEW_TIMESTAMP_MUST_BE_ISO_WITH_TIMEZONE", "question_id": question_id})
    missing_questions = sorted(set(expected) - set(observed_by_id))
    issues.extend({"code": "SOURCE_QUESTION_ROW_MISSING", "question_id": value} for value in missing_questions)
    if issues:
        state = "INVALID_REVIEW_REQUIRES_CORRECTION"
    elif missing_questions or missing_fields:
        state = "NEEDS_EDUCATOR_COMPLETION"
    elif "UNRESOLVED" in decisions:
        state = "NEEDS_EDUCATOR_RESOLUTION"
    elif "REVISE" in decisions:
        state = "REVISION_REQUIRED"
    elif decisions == {"APPROVE_FOR_MODERATION"}:
        state = "READY_FOR_INDEPENDENT_MODERATION"
    else:
        state = "NEEDS_EDUCATOR_COMPLETION"
    return {
        "schema": "dio.homs.exam.item_quality_review_validation.v1", "source_csv": str(path),
        "source_csv_sha256": _sha(path), "source_hashes": dict(source_hashes),
        "source_question_count": len(expected), "observed_question_count": len(observed),
        "matched_question_count": len(observed_by_id), "duplicate_question_ids": sorted(duplicate_ids),
        "missing_question_ids": missing_questions, "incomplete_educator_field_count": len(missing_fields),
        "incomplete_educator_fields": missing_fields, "issues": issues, "state": state,
        "review_decision_states": sorted(decisions), "independent_moderation_decision": "NOT_ISSUED",
        "classroom_release_authorized": False, "external_effects": False,
    }


def _render_item_quality_review_page(
    rows: list[dict[str, Any]], *, grade: int, subject: str, seed: int,
    source_hashes: Mapping[str, str], csv_fields: list[str],
) -> str:
    """Render an offline educator workspace; the browser only saves local draft files."""
    educator_fields = [
        "educator_confirmed_cognitive_level", "educator_reasoning_demand", "educator_grade_term_fit",
        "educator_caps_alignment", "educator_memo_alignment", "educator_mark_allocation_fit",
        "educator_language_accessibility", "required_revision", "educator_decision", "educator_rationale",
        "educator_reviewer", "reviewed_at",
    ]
    source_json = json.dumps(dict(source_hashes), sort_keys=True, separators=(",", ":"))
    context = {
        "schema": "dio.homs.exam.educator_review_workspace_context.v1",
        "grade": grade, "subject": subject, "random_seed": seed,
        "question_ids": [str(row["question_id"]) for row in rows],
        "source_hashes": dict(source_hashes),
        "context_sha256": hashlib.sha256(source_json.encode("utf-8")).hexdigest(),
    }
    context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    context_json = context_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    cards = []
    category_options = "<option value=''>Not reviewed</option><option>FIT</option><option>REVISE</option><option>UNRESOLVED</option>"
    level_options = "<option value=''>Confirm level</option>" + "".join(
        f"<option value='{level}'>{level.title()}</option>"
        for level in ("remember", "understand", "apply", "analyze", "evaluate", "create")
    )
    for index, row in enumerate(rows):
        qid = html.escape(str(row["question_id"]))
        caps_pages = html.escape(str(row.get("caps_physical_pdf_pages") or ""))
        memo_points = json.loads(str(row.get("memo_points_and_marks") or "[]"))
        memo_html = "".join(
            "<li>" + html.escape(str(point.get("point") or "")) + " <span class='marks'>["
            + html.escape(str(point.get("marks") or "")) + " mark(s)]</span></li>"
            for point in memo_points
        )
        caps_topic = html.escape(str(row.get("caps_topic") or ""))
        prompt = html.escape(str(row.get("question_prompt") or ""))
        label = html.escape(str(row.get("draft_cognitive_level_normalized") or ""))
        label_state = html.escape(str(row.get("draft_cognitive_level_label_state") or ""))
        label_fields = []
        label_fields.append("<label>Educator-confirmed cognitive level<select data-field='educator_confirmed_cognitive_level'>" + level_options + "</select></label>")
        label_fields.append("<label>Reasoning students must show<textarea data-field='educator_reasoning_demand' rows='2'></textarea></label>")
        for field, title in (
            ("educator_grade_term_fit", "Grade and term fit"), ("educator_caps_alignment", "CAPS alignment"),
            ("educator_memo_alignment", "Memo matches prompt"), ("educator_mark_allocation_fit", "Mark allocation"),
            ("educator_language_accessibility", "Language accessibility"),
        ):
            label_fields.append("<label>" + title + "<select data-field='" + field + "'>" + category_options + "</select></label>")
        label_fields.extend([
            "<label>Required revision<textarea data-field='required_revision' rows='2'></textarea></label>",
            "<label>Educator decision<select data-field='educator_decision'><option value=''>Not reviewed</option><option>APPROVE_FOR_MODERATION</option><option>REVISE</option><option>UNRESOLVED</option></select></label>",
            "<label>Rationale<textarea data-field='educator_rationale' rows='2'></textarea></label>",
            "<label>Educator name<input data-field='educator_reviewer' autocomplete='name'></label>",
            "<label>Review date and time<input data-field='reviewed_at' type='datetime-local'></label>",
        ])
        cards.append(
            "<section class='question' id='question-" + qid + "' data-question-index='" + str(index) + "'>"
            "<div class='question-head'><span class='qid'>" + qid + "</span><span>" + html.escape(str(row.get("question_marks") or "")) + " marks</span></div>"
            "<p class='caps'><strong>CAPS topic:</strong> " + caps_topic + " · physical PDF page(s): " + caps_pages + "</p>"
            "<p class='prompt'>" + prompt + "</p>"
            "<p><a href='CUSTOMER_EXAM_PACKAGE.html#question-" + qid + "'>Open the source excerpt and package context ↗</a></p>"
            "<p class='draft-label'><strong>Draft label:</strong> " + label + " · " + label_state + " · requires educator confirmation</p>"
            "<details><summary>Memo points and mark allocation</summary><ol>" + memo_html + "</ol></details>"
            "<fieldset><legend>Educator review · all fields start blank</legend>" + "".join(label_fields) + "</fieldset></section>"
        )
    source_fields = json.dumps(csv_fields)
    return """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>HOMS Exam · Educator quality review</title><style>
body{font:16px/1.55 system-ui,sans-serif;max-width:1160px;margin:28px auto;padding:0 18px;color:#20302f}h1,h2{line-height:1.2}a{color:#075d71}:focus-visible{outline:3px solid #a66a27;outline-offset:3px}.banner,.controls{padding:15px;border-left:4px solid #a66a27;background:#fff7e8;margin:16px 0}.controls{position:sticky;top:0;background:#f5f8f6;border:1px solid #b8c6bf;z-index:3}.controls button{font:600 15px system-ui;padding:10px 14px;margin:5px 6px 5px 0;color:white;background:#075d71;border:0;border-radius:5px;cursor:pointer}.controls label{display:inline-grid;gap:4px;margin:6px 12px 6px 0}.question{border:1px solid #ccd5cf;border-radius:10px;padding:18px;margin:22px 0;background:white}.question-head{display:flex;justify-content:space-between;font-weight:700}.qid{font-size:1.25rem}.caps,.draft-label{color:#465e57}.prompt{font-weight:600}.marks{color:#52655e}details{border:1px solid #d4ddd7;border-radius:6px;padding:9px;margin:10px 0}summary{cursor:pointer;font-weight:600}fieldset{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;border:1px solid #c4cec8;border-radius:8px;padding:15px}legend{font-weight:700}fieldset label{display:grid;gap:5px}fieldset label:nth-child(2){grid-column:span 2}textarea,input,select{font:inherit;padding:8px;border:1px solid #98aaa2;border-radius:4px;max-width:100%}#status{font-weight:600;min-height:1.5em}.note{font-size:.92rem;color:#465e57}@media(max-width:680px){fieldset{grid-template-columns:1fr}fieldset label:nth-child(2){grid-column:auto}.controls{position:static}}
</style></head><body><main><p>HOMS EXAM · EDUCATOR REVIEW</p><h1>Review Grade __GRADE__ · __SUBJECT__</h1>
<div class='banner'><strong>Draft review only.</strong> This workspace does not change the exam or memo, certify CAPS coverage, issue moderation approval, or authorize classroom use. Inspect the full question paper, marking memo and official CAPS page before recording each decision. A blank decision means review is pending.</div>
<p>Random subject assignment seed: <strong>__SEED__</strong>. Source-bound question count: __COUNT__. Use the exported CSV with the documented validator before treating the review as ready for independent moderation.</p>
<nav><a href='CUSTOMER_EXAM_PACKAGE.html'>Back to grade package</a> · <a href='documents/GRADE_0__DRAFT_EXAM.pdf'>Open exam PDF</a> · <a href='documents/GRADE_0__DRAFT_MARKING_MEMO.pdf'>Open memo PDF</a> · <a href='EDUCATOR_ITEM_QUALITY_REVIEW_GUIDE.md'>Review guide</a></nav>
<section class='controls' aria-label='Review controls'><strong id='progress' aria-live='polite'></strong><br><button id='save' type='button'>Save draft JSON</button><label>Resume matching draft <input id='load' type='file' accept='.json,application/json'></label><button id='export' type='button'>Export review CSV</button><p id='status' role='status' aria-live='polite'></p><p class='note'>Drafts download to this device. No browser storage or network requests are used by this page. Exported decisions are still unvalidated until the command-line validator runs.</p></section>
__CARDS__
<footer><p>Source hashes: exam __EXAM_SHA__; memo __MEMO_SHA__; assessment __ASSESSMENT_SHA__; CAPS map __MAP_SHA__. Classroom release remains disabled.</p></footer></main>
<script type='application/json' id='review-context'>__CONTEXT__</script><script type='application/json' id='source-rows'>__ROWS__</script><script type='application/json' id='source-fields'>__FIELDS__</script><script>
(()=>{const context=JSON.parse(document.getElementById('review-context').textContent),rows=JSON.parse(document.getElementById('source-rows').textContent),fields=JSON.parse(document.getElementById('source-fields').textContent),educator=__EDUCATOR_FIELDS__;
const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';function collect(){document.querySelectorAll('[data-question-index]').forEach(card=>{const row=rows[Number(card.dataset.questionIndex)];card.querySelectorAll('[data-field]').forEach(input=>row[input.dataset.field]=input.value)})}
function complete(row){return educator.every(key=>String(row[key]??'').trim()!=='')};function progress(){collect();const done=rows.filter(complete).length;document.getElementById('progress').textContent='Review fields completed: '+done+' / '+rows.length+' questions · this is progress only, not approval.'}
function download(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function csv(){collect();return '\ufeff'+[fields.map(cell).join(','),...rows.map(row=>fields.map(key=>cell(key==='reviewed_at'&&row[key]?new Date(row[key]).toISOString():row[key])).join(','))].join('\r\n')}
function draft(){collect();return {schema:'dio.homs.exam.educator_review_draft.v1',context_sha256:context.context_sha256,source_hashes:context.source_hashes,saved_at:new Date().toISOString(),rows:rows.map(row=>({question_id:row.question_id,values:Object.fromEntries(educator.map(key=>[key,row[key]??'']))}))}}
document.querySelectorAll('[data-field]').forEach(input=>{input.addEventListener('input',progress);input.addEventListener('change',progress)});
document.getElementById('save').addEventListener('click',()=>{download('HOMS_EXAM_EDUCATOR_REVIEW_DRAFT.json',JSON.stringify(draft(),null,2)+'\n','application/json');document.getElementById('status').textContent='Draft JSON saved to your downloads; keep it with this matching source package.'});
document.getElementById('export').addEventListener('click',()=>{download('EDUCATOR_ITEM_QUALITY_REVIEW_COMPLETED.csv',csv(),'text/csv;charset=utf-8');document.getElementById('status').textContent='Review CSV exported. Run the documented validator before independent moderation.'});
document.getElementById('load').addEventListener('change',async event=>{const file=event.target.files?.[0];if(!file)return;try{if(file.size>2000000)throw Error('Draft file exceeds the 2 MB limit.');const data=JSON.parse(await file.text());if(data.schema!=='dio.homs.exam.educator_review_draft.v1'||data.context_sha256!==context.context_sha256||JSON.stringify(data.source_hashes)!==JSON.stringify(context.source_hashes)||!Array.isArray(data.rows)||data.rows.length!==rows.length)throw Error('Draft does not match this grade, exam, memo and CAPS source set.');const byId=new Map(data.rows.map(row=>[row.question_id,row.values]));if(byId.size!==rows.length||rows.some(row=>!byId.has(row.question_id)))throw Error('Draft question IDs do not match the current review.');for(let i=0;i<rows.length;i++){const values=byId.get(rows[i].question_id);if(!values||Object.keys(values).some(key=>!educator.includes(key)))throw Error('Draft contains unexpected review fields.');const card=document.querySelector('[data-question-index="'+i+'"]');card.querySelectorAll('[data-field]').forEach(input=>input.value=values[input.dataset.field]??'')}progress();document.getElementById('status').textContent='Matching draft loaded. Recheck every response against the source material before export.'}catch(error){document.getElementById('status').textContent=error.message||'Could not load this review draft.'}finally{event.target.value=''}});
progress()})();
</script></body></html>""".replace("__GRADE__", str(grade)).replace("__SUBJECT__", html.escape(subject)).replace("__SEED__", str(seed)).replace("__COUNT__", str(len(rows))).replace("__CARDS__", "".join(cards)).replace("__CONTEXT__", context_json).replace("__ROWS__", json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")).replace("__FIELDS__", json.dumps(csv_fields)).replace("__EDUCATOR_FIELDS__", json.dumps(educator_fields)).replace("__EXAM_SHA__", html.escape(str(source_hashes.get("exam_docx_sha256") or ""))).replace("__MEMO_SHA__", html.escape(str(source_hashes.get("memo_docx_sha256") or ""))).replace("__ASSESSMENT_SHA__", html.escape(str(source_hashes.get("assessment_json_sha256") or ""))).replace("__MAP_SHA__", html.escape(str(source_hashes.get("caps_alignment_sha256") or ""))).replace("GRADE_0__", f"GRADE_{grade:02d}_")


def build_homs_exam_customer_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    grade = int(packet.get("grade") or 0)
    if grade not in range(1, 13):
        raise ValueError("grade must be an integer from 1 through 12")
    assignments = json.loads(ASSIGNMENTS.read_text(encoding="utf-8"))
    set_receipt = json.loads(SET_RECEIPT.read_text(encoding="utf-8"))
    alignment = json.loads(CAPS_ALIGNMENT.read_text(encoding="utf-8"))
    pdf_manifest = json.loads(PDF_MANIFEST.read_text(encoding="utf-8"))
    if pdf_manifest.get("source_set_receipt_sha256") != _sha(SET_RECEIPT) or int(pdf_manifest.get("grade_count") or 0) != 12 or int(pdf_manifest.get("pdf_count") or 0) != 24:
        raise ValueError("print PDF manifest is not bound to the current twelve-grade exam set")
    if assignments.get("release_authorized") is not False or alignment.get("classroom_release_authorized") is not False:
        raise ValueError("exam packet release boundary is missing or invalid")
    if assignments.get("random_seed") != set_receipt.get("random_seed"):
        raise ValueError("grade set and assignment randomization seeds differ")
    assignment = next((row for row in assignments.get("assignments", []) if int(row.get("grade") or 0) == grade), None)
    alignment_grade = next((row for row in alignment.get("grades", []) if int(row.get("grade") or 0) == grade), None)
    set_grade = next((row for row in set_receipt.get("results", []) if int(row.get("grade") or 0) == grade), None)
    if not assignment or not alignment_grade or not set_grade or set_grade.get("state") != "DRAFT_PACK_CREATED":
        raise ValueError(f"Grade {grade} does not have a complete randomized exam/CAPS source record")
    grade_dir = Path(str(set_grade.get("job_dir") or "")).resolve()
    if not grade_dir.is_relative_to(PACK.resolve()) or not grade_dir.is_dir():
        raise ValueError("grade source directory escapes the registered exam set")
    source_receipt_path = grade_dir / "HOMS_GRADE_EXAM_RECEIPT.json"
    assessment_path = grade_dir / "HOMS_GRADE_ASSESSMENT.json"
    source_receipt = json.loads(source_receipt_path.read_text(encoding="utf-8"))
    assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    if int(source_receipt.get("grade") or 0) != grade or int(source_receipt.get("randomization_seed") or -1) != assignments["random_seed"]:
        raise ValueError("exam receipt is not bound to the selected random grade assignment")
    if str(source_receipt.get("subject") or "").casefold() != str(assessment.get("subject") or "").casefold():
        raise ValueError("assessment subject differs from its grade receipt")
    if assignment.get("subject_profile") not in grade_dir.name:
        raise ValueError("selected grade folder does not match its randomized subject assignment")
    if str(packet.get("subject") or "").strip() and str(packet["subject"]).strip().casefold() != str(assessment["subject"]).casefold():
        raise ValueError(f"Grade {grade} is assigned to {assessment['subject']}, not {packet['subject']}")
    assessment_sha = _sha(assessment_path)
    paper = grade_dir / "GRADE_EXAM.docx"
    memo = grade_dir / "GRADE_MEMO.docx"
    pdf_row = next((row for row in pdf_manifest.get("grades", []) if int(row.get("grade") or 0) == grade), None)
    if not pdf_row:
        raise ValueError(f"Grade {grade} is missing from the print PDF manifest")
    exam_pdf = PACK / str(pdf_row.get("exam_pdf") or "")
    memo_pdf = PACK / str(pdf_row.get("memo_pdf") or "")
    expected_assessment = source_receipt.get("assessment") or {}
    if assessment_sha != expected_assessment.get("json", {}).get("sha256"):
        raise ValueError("assessment JSON hash differs from the grade receipt")
    for role, path in (("exam", paper), ("memo", memo)):
        if not path.is_file() or _sha(path) != expected_assessment.get(role, {}).get("sha256"):
            raise ValueError(f"Grade {grade} {role} file is missing or its hash changed")
    for role, path, docx_path in (("exam", exam_pdf, paper), ("memo", memo_pdf, memo)):
        if (not path.is_file() or _sha(path) != pdf_row.get(f"{role}_pdf_sha256")
                or pdf_row.get(f"{role}_docx_sha256") != _sha(docx_path)
                or int(pdf_row.get(f"{role}_pdf_pages") or 0) < 1):
            raise ValueError(f"Grade {grade} print {role} PDF is missing, stale, or unbound to its DOCX")
    if alignment_grade.get("assessment_json_sha256") != assessment_sha:
        raise ValueError("CAPS alignment record is not bound to the selected assessment JSON")
    if alignment_grade.get("exam_sha256") != _sha(paper) or alignment_grade.get("memo_sha256") != _sha(memo):
        raise ValueError("CAPS alignment record is not bound to the selected exam and memo")
    caps_sha = source_receipt.get("caps_source", {}).get("sha256")
    if not caps_sha or caps_sha != alignment_grade.get("caps_source_sha256"):
        raise ValueError("CAPS source hash differs between the grade receipt and question alignment record")

    question_by_number = {}
    for section in assessment.get("sections") or []:
        for question in section.get("questions") or []:
            number = str(question.get("number") or "")
            question_by_number[number] = str(question.get("prompt") or "")
    mappings = alignment_grade.get("question_mappings") or []
    mapped_by_number = {str(row.get("question_id") or ""): row for row in mappings}
    if len(mapped_by_number) != len(mappings) or set(mapped_by_number) != set(question_by_number):
        raise ValueError("CAPS question mapping must cover each selected grade question exactly once")
    for number, prompt in question_by_number.items():
        if mapped_by_number[number].get("prompt") != prompt or not mapped_by_number[number].get("caps_topic") or not mapped_by_number[number].get("caps_pages"):
            raise ValueError(f"Question {number} lacks an exact prompt/topic/page CAPS mapping")

    corpus = json.loads(CAPS_CORPUS.read_text(encoding="utf-8"))
    corpus_document = next((row for row in corpus.get("documents", []) if row.get("sha256") == caps_sha), None)
    if corpus_document is None:
        raise ValueError("official CAPS source hash is absent from the CAPS corpus manifest")
    source_candidates = [path for path in (ROOT / "corpora/caps/pdf").rglob(Path(corpus_document["path"]).name)
                         if _sha(path) == caps_sha]
    if len(source_candidates) != 1:
        raise ValueError(f"expected one byte-verified local CAPS source, found {len(source_candidates)}")
    caps_pdf = source_candidates[0]
    excerpt_by_question: dict[str, list[dict[str, Any]]] = {}
    for mapping in mappings:
        question_id = str(mapping["question_id"])
        excerpts = []
        for citation in mapping.get("caps_pages") or []:
            page_number = int(citation["physical_pdf_page"])
            page_text = _caps_page_text(caps_pdf, page_number)
            page_sha = hashlib.sha256(page_text.encode("utf-8")).hexdigest()
            if page_sha != citation.get("page_text_sha256"):
                raise ValueError(f"CAPS source page {page_number} hash differs from the question alignment map")
            excerpts.append({"physical_pdf_page": page_number, "page_text_sha256": page_sha, "text": page_text})
        if not excerpts:
            raise ValueError(f"Question {question_id} has no source-page excerpts")
        excerpt_by_question[question_id] = excerpts

    subject_value = str(assessment.get("subject") or "")
    quality_rows = []
    mark_balance = []
    for section in assessment.get("sections") or []:
        for question in section.get("questions") or []:
            number = str(question.get("number") or "")
            points = _memo_point_rows(question)
            raw_level = str(question.get("bloom_level") or "NOT_LABELLED")
            normalized_level, label_state = _cognitive_label(raw_level)
            allocated = sum(float(row["marks"]) for row in points if row["marks"] is not None)
            point_marks_declared = all(row["marks"] is not None for row in points)
            balanced = point_marks_declared and abs(allocated - float(question.get("marks") or 0)) < 0.001
            mark_balance.append({"question_id": number, "question_marks": question.get("marks"),
                                 "memo_point_marks": allocated if point_marks_declared else None, "balanced": balanced})
            mapping = mapped_by_number[number]
            quality_rows.append({
                "grade": grade, "subject": subject_value,
                "question_id": number, "caps_topic": str(mapping.get("caps_topic") or ""),
                "caps_physical_pdf_pages": ",".join(str(row.get("physical_pdf_page")) for row in mapping.get("caps_pages") or []),
                "question_prompt": str(question.get("prompt") or ""),
                "draft_cognitive_level": raw_level,
                "draft_cognitive_level_normalized": normalized_level,
                "draft_cognitive_level_label_state": label_state,
                "draft_question_family": str(question.get("question_family") or "NOT_LABELLED"),
                "question_marks": question.get("marks", ""),
                "memo_point_count": len(points),
                "memo_points_and_marks": json.dumps(points, ensure_ascii=False, separators=(",", ":")),
                "educator_confirmed_cognitive_level": "", "educator_reasoning_demand": "",
                "educator_grade_term_fit": "", "educator_caps_alignment": "",
                "educator_memo_alignment": "", "educator_mark_allocation_fit": "",
                "educator_language_accessibility": "", "required_revision": "",
                "educator_decision": "", "educator_rationale": "", "educator_reviewer": "", "reviewed_at": "",
            })
    if len(quality_rows) != len(question_by_number):
        raise ValueError("educator quality review row count does not match the selected grade question set")
    cognitive_counts: dict[str, int] = {}
    for row in quality_rows:
        level = row["draft_cognitive_level_normalized"]
        cognitive_counts[level] = cognitive_counts.get(level, 0) + 1
    unclassified_cognitive_labels = sum(row["draft_cognitive_level_label_state"] == "NEEDS_EDUCATOR_CLASSIFICATION" for row in quality_rows)
    quality_csv_fields = list(quality_rows[0]) if quality_rows else [
        "grade", "subject", "question_id", "caps_topic", "caps_physical_pdf_pages", "question_prompt",
        "draft_cognitive_level", "draft_cognitive_level_normalized", "draft_cognitive_level_label_state",
        "draft_question_family", "question_marks", "memo_point_count", "memo_points_and_marks",
        "educator_confirmed_cognitive_level", "educator_reasoning_demand", "educator_grade_term_fit", "educator_caps_alignment",
        "educator_memo_alignment", "educator_mark_allocation_fit", "educator_language_accessibility", "required_revision",
        "educator_decision", "educator_rationale", "educator_reviewer", "reviewed_at",
    ]

    out = Path(output_dir).resolve()
    documents = out / "documents"
    documents.mkdir(parents=True, exist_ok=True)
    exam_copy = documents / f"GRADE_{grade:02d}_DRAFT_EXAM.docx"
    memo_copy = documents / f"GRADE_{grade:02d}_DRAFT_MARKING_MEMO.docx"
    exam_pdf_copy = documents / f"GRADE_{grade:02d}_DRAFT_EXAM.pdf"
    memo_pdf_copy = documents / f"GRADE_{grade:02d}_DRAFT_MARKING_MEMO.pdf"
    shutil.copy2(paper, exam_copy)
    shutil.copy2(memo, memo_copy)
    shutil.copy2(exam_pdf, exam_pdf_copy)
    shutil.copy2(memo_pdf, memo_pdf_copy)
    quality_csv = out / "EDUCATOR_ITEM_QUALITY_REVIEW.csv"
    with quality_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=quality_csv_fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(quality_rows)
    quality_guide = out / "EDUCATOR_ITEM_QUALITY_REVIEW_GUIDE.md"
    quality_guide.write_text(
        "# HOMS Exam item-quality review\n\n"
        "This source-bound matrix is a blank educator moderation aid. Draft labels describe the current source record; they are not verified cognitive-demand judgments. The normalized field maps UK spelling `analyse` to `analyze` and maps the observed verb label `explain` to the candidate category `understand`; this verb mapping explicitly requires educator confirmation. Other unrecognized labels are marked `REVIEW_UNCLASSIFIED` and must be classified by the educator.\n\n"
        "For each question, read the complete examination stimulus, question, CAPS source pages, memo and allocated marks. Confirm or replace the cognitive-demand label; describe the reasoning students must show; check grade/term fit, CAPS alignment, memo coverage, mark allocation and language accessibility. Record any required revision and a disposition.\n\n"
        "Use `APPROVE_FOR_MODERATION`, `REVISE`, or `UNRESOLVED` only after review. Add a concise rationale, reviewer identity and date.\n\n"
        "Validate a completed copy with `python scripts/validate_homs_exam_item_quality_review.py --run-dir <grade-package-directory> --csv <completed-review.csv>`. The result may say READY_FOR_INDEPENDENT_MODERATION, but it never issues moderation or classroom-release approval.\n\n"
        "This worksheet does not certify curriculum coverage or authorize classroom release.\n",
        encoding="utf-8",
    )
    quality_source_hashes = {
        "assessment_json_sha256": assessment_sha,
        "exam_docx_sha256": _sha(paper), "memo_docx_sha256": _sha(memo),
        "caps_alignment_sha256": _sha(CAPS_ALIGNMENT), "caps_source_sha256": caps_sha,
    }
    quality_validation = validate_item_quality_review_csv(quality_csv, quality_rows, source_hashes=quality_source_hashes)
    quality_validation_path = out / "EDUCATOR_ITEM_QUALITY_REVIEW_VALIDATION.json"
    quality_validation_path.write_text(json.dumps(quality_validation, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    quality_workspace = out / "EDUCATOR_ITEM_QUALITY_REVIEW.html"
    quality_workspace.write_text(
        _render_item_quality_review_page(
            quality_rows, grade=grade, subject=str(assessment["subject"]),
            seed=int(assignments["random_seed"]), source_hashes=quality_source_hashes,
            csv_fields=quality_csv_fields,
        ),
        encoding="utf-8",
    )
    try:
        quality_csv.chmod(0o600)
        quality_guide.chmod(0o600)
        quality_validation_path.chmod(0o600)
    except OSError:
        pass
    subject = str(assessment["subject"])
    title = str(assessment.get("exam_title") or f"Grade {grade} {subject}")
    scope_note = str(assessment.get("scope_note") or "").strip()
    source = source_receipt["caps_source"]
    rows = []
    for number, prompt in question_by_number.items():
        mapping = mapped_by_number[number]
        pages = ", ".join(f"p. {item['physical_pdf_page']}" for item in mapping.get("caps_pages") or [])
        source_excerpts = "".join(
            "<details><summary>Official CAPS page " + str(item["physical_pdf_page"]) + " · text SHA-256 "
            + html.escape(item["page_text_sha256"]) + "</summary><pre>" + html.escape(item["text"]) + "</pre></details>"
            for item in excerpt_by_question[number]
        )
        rows.append(f"<tr id='question-{html.escape(number, quote=True)}'><th scope='row'>{html.escape(number)}</th><td>{html.escape(mapping['caps_topic'])}</td><td>{html.escape(pages)}{source_excerpts}</td><td>{html.escape(prompt)}</td></tr>")
    preview = out / "CUSTOMER_EXAM_PACKAGE.html"
    preview.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>body{{font:16px/1.55 system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 18px;color:#20302f}}h1{{line-height:1.15}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #ccd5cf}}thead th{{background:#184b44;color:white}}.note{{border-left:4px solid #a66a27;padding:12px;background:#fff7e8}}a{{color:#075d71}}pre{{white-space:pre-wrap;max-height:24rem;overflow:auto;background:#f3f5f2;padding:10px}}details{{margin:.4rem 0}}:focus-visible{{outline:3px solid #a66a27;outline-offset:2px}}</style>"
        f"<main><p>HOMS EXAM STUDIO · DRAFT</p><h1>{html.escape(title)}</h1><p>{grade} · {html.escape(subject)} · {int(assessment.get('total_marks') or 0)} marks · {int(assessment.get('duration_minutes') or 0)} minutes</p>"
        + (f"<p class='note'><strong>Assessment scope:</strong> {html.escape(scope_note)}</p>" if scope_note else "")
        + f"<p>Randomized subject assignment seed {int(assignments['random_seed'])}; subject profile {html.escape(str(assignment['subject_profile']))}.</p>"
        f"<ul><li><a href='documents/{exam_copy.name}'>Editable draft examination paper (DOCX)</a></li><li><a href='documents/{exam_pdf_copy.name}'>Print-ready draft examination paper (PDF, {int(pdf_row['exam_pdf_pages'])} pages)</a></li><li><a href='documents/{memo_copy.name}'>Editable draft marking memo (DOCX)</a></li><li><a href='documents/{memo_pdf_copy.name}'>Print-ready draft marking memo (PDF, {int(pdf_row['memo_pdf_pages'])} pages)</a></li><li><a href='{quality_workspace.name}'>Open guided educator quality review</a></li><li><a href='{quality_csv.name}'>Question-level educator quality review (CSV)</a></li><li><a href='{quality_guide.name}'>Educator review guide</a></li></ul>"
        f"<p>CAPS source: <a href='{html.escape(str(source.get('source_url') or ''), quote=True)}'>{html.escape(str(source.get('title') or 'Official CAPS source'))}</a>; SHA-256 <code>{html.escape(caps_sha)}</code>.</p>"
        "<table><thead><tr><th>Question</th><th>CAPS topic</th><th>Physical PDF page</th><th>Question prompt</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        "<p class='note'>Question-level CAPS topic/page mappings are source traces for educator review. They do not establish full curriculum coverage, content correctness, moderation approval, or classroom release. Confirm grade, term and subject fit before use.</p></main></html>\n",
        encoding="utf-8",
    )
    outputs = []
    for path in (exam_copy, memo_copy, exam_pdf_copy, memo_pdf_copy, quality_csv, quality_guide, quality_validation_path, quality_workspace, preview):
        outputs.append({"path": path.relative_to(out).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)})
    receipt = {
        "schema": "dio.homs.exam.customer_execution.v1", "grade": grade, "subject": subject,
        "exam_title": title, "random_seed": int(assignments["random_seed"]),
        "subject_profile": assignment["subject_profile"], "question_count": len(question_by_number),
        "total_marks": int(assessment.get("total_marks") or 0), "duration_minutes": int(assessment.get("duration_minutes") or 0),
        "assessment_json_sha256": assessment_sha, "exam_sha256": _sha(paper), "memo_sha256": _sha(memo),
        "print_pdf_manifest_sha256": _sha(PDF_MANIFEST),
        "exam_pdf_sha256": _sha(exam_pdf), "memo_pdf_sha256": _sha(memo_pdf),
        "exam_pdf_pages": int(pdf_row["exam_pdf_pages"]), "memo_pdf_pages": int(pdf_row["memo_pdf_pages"]),
        "caps_source_title": source.get("title"), "caps_source_url": source.get("source_url"), "caps_source_sha256": caps_sha,
        "caps_question_mapping_count": len(mapped_by_number),
        "caps_source_page_excerpt_count": sum(len(items) for items in excerpt_by_question.values()),
        "caps_source_page_excerpt_hashes_match_alignment": True,
        "caps_source_page_excerpts": [{"question_id": question_id, "physical_pdf_page": item["physical_pdf_page"],
                                       "page_text_sha256": item["page_text_sha256"]}
                                      for question_id, items in excerpt_by_question.items() for item in items],
        "classroom_release_authorized": False,
        "educator_item_quality_review": {
            "workspace_path": quality_workspace.name, "workspace_sha256": _sha(quality_workspace),
            "csv_path": quality_csv.name, "csv_sha256": _sha(quality_csv),
            "guide_path": quality_guide.name, "guide_sha256": _sha(quality_guide),
            "question_row_count": len(quality_rows), "blank_educator_decisions": True,
            "draft_cognitive_level_counts": cognitive_counts,
            "unclassified_draft_cognitive_label_count": unclassified_cognitive_labels,
            "all_draft_cognitive_labels_canonical": unclassified_cognitive_labels == 0,
            "source_hashes": quality_source_hashes,
            "blank_validation_state": quality_validation["state"],
            "validation_sha256": _sha(quality_validation_path),
            "validation_issue_count": len(quality_validation["issues"]),
            "automated_memo_mark_balance_all_pass": bool(mark_balance) and all(row["balanced"] for row in mark_balance),
            "memo_mark_balance": mark_balance,
            "independent_moderation_decision": "NOT_ISSUED",
        },
        "educator_review_required": True, "external_effects": False, "outputs": outputs,
    }
    (out / "CUSTOMER_PACKAGE_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
