"""Customer route for mechanical, explicitly non-decisional HOMS pre-moderation."""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Mapping
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
CAPS_ALIGNMENT_PATH = PACK / "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"
CAPS_IDENTITY_PATH = PACK / "RANDOM_SUBJECT_CAPS_DOCUMENT_IDENTITY_AUDIT_20261101.json"
CAPS_PDF_ROOT = ROOT / "corpora/caps/pdf"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "\n".join("".join(node.itertext()) for node in root.findall(".//w:p", ns))


def _verified_caps_question_alignment(grade: int, subject: str, source_hash: str) -> dict[str, Any]:
    alignment = json.loads(CAPS_ALIGNMENT_PATH.read_text(encoding="utf-8"))
    identity = json.loads(CAPS_IDENTITY_PATH.read_text(encoding="utf-8"))
    row = next((item for item in alignment.get("grades", []) if item.get("grade") == grade), None)
    identity_row = next((item for item in identity.get("grades", []) if item.get("grade") == grade), None)
    if (not row or not identity_row
            or str(row.get("subject") or "").strip().casefold() != subject.strip().casefold()
            or row.get("caps_source_sha256") != source_hash
            or identity_row.get("caps_source_sha256") != source_hash
            or identity_row.get("source_identity_check") != "PASS_SUBJECT_FILENAME_AND_HASH_MATCH"
            or alignment.get("all_exam_question_ids_mapped_exactly_once") is not True
            or alignment.get("all_current_caps_source_hashes_verified") is not True
            or alignment.get("all_cited_physical_pdf_pages_have_text") is not True):
        raise ValueError("HOMS Moderate could not verify the grade's current question-level CAPS alignment")
    candidates = list(CAPS_PDF_ROOT.rglob(identity_row["caps_document_filename"]))
    if len(candidates) != 1 or _sha(candidates[0]) != source_hash:
        raise ValueError("HOMS Moderate CAPS PDF bytes do not match the question-alignment source hash")
    mappings = row.get("question_mappings") or []
    return {
        "grade": grade,
        "subject": subject,
        "caps_source_sha256": source_hash,
        "caps_pdf_path": candidates[0].relative_to(ROOT).as_posix(),
        "caps_alignment_path": CAPS_ALIGNMENT_PATH.relative_to(ROOT).as_posix(),
        "caps_alignment_sha256": _sha(CAPS_ALIGNMENT_PATH),
        "caps_identity_audit_sha256": _sha(CAPS_IDENTITY_PATH),
        "alignment_review_state": alignment.get("alignment_review_state"),
        "question_mappings": mappings,
        "current_caps_source_hashes_verified": True,
        "cited_physical_pdf_pages_have_text": True,
    }


def _moderator_review_context(
    assessment: Mapping[str, Any], *, grade: int, subject: str, seed: int,
    paper: Path, memo: Path, assessment_path: Path, caps_alignment: Mapping[str, Any],
    report_path: Path, caps_copy: Path,
) -> dict[str, Any]:
    mappings = {str(row.get("question_id") or ""): row for row in caps_alignment.get("question_mappings") or []}
    questions = [q for section in assessment.get("sections") or [] for q in section.get("questions") or []]
    if len(questions) != 5 or set(mappings) != {str(q.get("number") or "") for q in questions}:
        raise ValueError("moderator workspace requires a complete, exact question-to-CAPS map")
    rows = []
    for question in questions:
        question_id = str(question.get("number") or "")
        mapping = mappings[question_id]
        rows.append({
            "question_id": question_id,
            "prompt": str(question.get("prompt") or ""),
            "marks": int(question.get("marks") or 0),
            "caps_topic": str(mapping.get("caps_topic") or ""),
            "caps_pages": [dict(page) for page in mapping.get("caps_pages") or []],
            "memo_points": [{"point": str(point.get("point") or ""), "marks": int(point.get("marks") or 0)}
                            for point in question.get("memo") or []],
        })
    sources = {
        "exam_docx_sha256": _sha(paper), "memo_docx_sha256": _sha(memo),
        "assessment_json_sha256": _sha(assessment_path),
        "caps_source_sha256": str(caps_alignment.get("caps_source_sha256") or ""),
        "caps_alignment_sha256": str(caps_alignment.get("caps_alignment_sha256") or ""),
        "caps_identity_audit_sha256": str(caps_alignment.get("caps_identity_audit_sha256") or ""),
        "mechanical_report_sha256": _sha(report_path),
    }
    value = {
        "schema": "dio.homs.moderate.educator_review_context.v1", "grade": grade,
        "subject": subject, "random_seed": seed,
        "caps_source_path": caps_copy.relative_to(caps_copy.parents[1]).as_posix(),
        "source_hashes": sources, "question_rows": rows,
        "independent_moderation_decision": "NOT_ISSUED", "classroom_release_authorized": False,
    }
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    value["context_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def _render_moderator_review_page(context: Mapping[str, Any]) -> str:
    context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    context_json = context_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    options = "<option value=''>Not reviewed</option><option>FIT</option><option>REVISE</option><option>UNRESOLVED</option>"
    rows_html = []
    for index, row in enumerate(context.get("question_rows") or []):
        qid = html.escape(str(row.get("question_id") or ""))
        pages = " · ".join("p. " + html.escape(str(page.get("physical_pdf_page") or "")) for page in row.get("caps_pages") or [])
        citations = "".join("<details><summary>CAPS page " + html.escape(str(page.get("physical_pdf_page") or ""))
                            + " · text hash " + html.escape(str(page.get("page_text_sha256") or ""))
                            + "</summary><p>Review this location in the <a href='sources/CAPS_SOURCE.pdf'>official CAPS curriculum PDF</a>.</p></details>"
                            for page in row.get("caps_pages") or [])
        memo = "".join("<li>" + html.escape(str(point.get("point") or "")) + " ["
                       + html.escape(str(point.get("marks") or "")) + " mark(s)]</li>"
                       for point in row.get("memo_points") or [])
        fields = []
        for key, title in (
            ("content_accuracy", "Content accuracy"), ("caps_alignment", "CAPS topic and page fit"),
            ("grade_term_fit", "Grade and term fit"), ("memo_correctness", "Memo accuracy and alternatives"),
            ("mark_allocation", "Mark allocation"), ("language_accessibility", "Language and accessibility"),
        ):
            fields.append("<label>" + title + "<select data-field='" + key + "'>" + options + "</select></label>")
        fields.extend([
            "<label>Finding / rationale<textarea data-field='rationale' rows='3'></textarea></label>",
            "<label>Required revision, if any<textarea data-field='required_revision' rows='3'></textarea></label>",
        ])
        rows_html.append(
            "<section class='question' data-row='" + str(index) + "'><h2>Question " + qid + " · "
            + html.escape(str(row.get("marks") or "")) + " marks</h2><p class='caps'><strong>CAPS:</strong> "
            + html.escape(str(row.get("caps_topic") or "")) + " · " + pages + "</p>" + citations
            + "<p class='prompt'>" + html.escape(str(row.get("prompt") or "")) + "</p><details><summary>Source marking points</summary><ol>"
            + memo + "</ol></details><fieldset><legend>Moderator review · starts blank</legend>" + "".join(fields)
            + "</fieldset></section>"
        )
    return """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>HOMS Moderate · educator review</title><style>body{font:16px/1.55 system-ui,sans-serif;max-width:1120px;margin:28px auto;padding:0 18px;color:#20302f}h1,h2{line-height:1.2}a{color:#075d71}:focus-visible{outline:3px solid #a66a27;outline-offset:3px}.banner,.toolbar{padding:15px;border-left:4px solid #a66a27;background:#fff7e8;margin:16px 0}.toolbar{position:sticky;top:0;background:#f3f7f5;border:1px solid #b8c6bf;z-index:2}.toolbar button{font:600 15px system-ui;padding:10px 14px;margin:6px;color:white;background:#075d71;border:0;border-radius:5px;cursor:pointer}.question{border:1px solid #ccd5cf;border-radius:10px;padding:18px;margin:22px 0;background:#fff}.caps{color:#465e57}.prompt{font-weight:600}details{border:1px solid #ccd5cf;border-radius:6px;padding:9px;margin:10px 0}summary{cursor:pointer;font-weight:600}fieldset{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;border:1px solid #c4cec8;border-radius:8px;padding:15px}legend{font-weight:700}fieldset label{display:grid;gap:5px}fieldset textarea{grid-column:span 2}select,textarea,input{font:inherit;padding:8px;border:1px solid #98aaa2;border-radius:4px;max-width:100%}.note{font-size:.92rem;color:#465e57}#status{min-height:1.5em;font-weight:600}@media(max-width:680px){fieldset{grid-template-columns:1fr}fieldset textarea{grid-column:auto}.toolbar{position:static}}</style></head>
<body><main><p>HOMS MODERATE · EDUCATOR WORKSPACE</p><h1>Grade __GRADE__ · __SUBJECT__</h1>
<div class='banner'><strong>Review record only.</strong> The mechanical report checks structure and source binding; it does not verify subject correctness. This workspace does not issue an independent moderation decision or authorize classroom release. Read the complete exam, memo and official CAPS pages before entering a review.</div>
<p>Random subject assignment seed __SEED__. Mechanical pre-moderation: PASS. All moderator decisions start blank.</p>
<nav><a href='CUSTOMER_MODERATION_REVIEW.html'>Mechanical report</a> · <a href='sources/__EXAM_NAME__'>Exam DOCX</a> · <a href='sources/__MEMO_NAME__'>Memo DOCX</a> · <a href='sources/CAPS_SOURCE.pdf'>Official CAPS source PDF</a> · <a href='HOMS_MECHANICAL_PREMODERATION_REPORT.json'>Machine report</a></nav>
<section class='toolbar'><strong id='progress' aria-live='polite'></strong><br><label>Moderator name <input id='moderator-name' autocomplete='name'></label><label>Subject qualification / role <input id='moderator-qualification'></label><label>Independent of item author? <select id='independence'><option value=''>Not recorded</option><option>YES</option><option>NO</option><option>UNKNOWN</option></select></label><label>Review date and time <input id='reviewed-at' type='datetime-local'></label><br><label>Overall recommendation <select id='recommendation'><option value=''>Not reviewed</option><option>RECOMMEND_FOR_SECOND_REVIEW</option><option>REVISE</option><option>UNRESOLVED</option></select></label><label>Overall rationale <textarea id='overall-rationale' rows='2'></textarea></label><br><button id='save' type='button'>Save review draft</button><label>Resume matching draft <input id='load' type='file' accept='.json,application/json'></label><button id='export' type='button'>Export review record</button><p id='status' role='status' aria-live='polite'></p><p class='note'>This page uses no browser storage or network requests. Drafts are downloaded to this device and tied to the current exam, memo, assessment and CAPS hashes. Export creates a review record only; it cannot alter the exam, produce approval or release marks.</p></section>
__ROWS__
<footer><p>Packet context SHA-256: <code>__CONTEXT_HASH__</code>. Independent moderation decision: NOT ISSUED. Classroom release: NOT AUTHORIZED.</p></footer></main>
<script type='application/json' id='context'>__CONTEXT__</script><script>
(()=>{const context=JSON.parse(document.getElementById('context').textContent),rows=context.question_rows.map(r=>({question_id:r.question_id,content_accuracy:'',caps_alignment:'',grade_term_fit:'',memo_correctness:'',mark_allocation:'',language_accessibility:'',rationale:'',required_revision:''})),fields=['content_accuracy','caps_alignment','grade_term_fit','memo_correctness','mark_allocation','language_accessibility','rationale','required_revision'];const $=id=>document.getElementById(id);function collect(){document.querySelectorAll('[data-row]').forEach(card=>{const row=rows[Number(card.dataset.row)];card.querySelectorAll('[data-field]').forEach(input=>row[input.dataset.field]=input.value)})}function complete(row){return fields.every(f=>String(row[f]||'').trim()!=='')}function progress(){collect();const done=rows.filter(complete).length;$('progress').textContent='Question reviews recorded: '+done+' / '+rows.length+' · not an approval.'}function payload(){collect();return {schema:'dio.homs.moderate.educator_review_record.v1',grade:context.grade,subject:context.subject,random_seed:context.random_seed,context_sha256:context.context_sha256,source_hashes:context.source_hashes,reviewer:{name:$('moderator-name').value,qualification:$('moderator-qualification').value,independent_of_item_author:$('independence').value,reviewed_at:$('reviewed-at').value?new Date($('reviewed-at').value).toISOString():''},recommendation:$('recommendation').value,overall_rationale:$('overall-rationale').value,question_reviews:rows.map(r=>({...r})),independent_moderation_decision:'NOT_ISSUED',classroom_release_authorized:false}}function save(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}$('save').addEventListener('click',()=>{save('HOMS_MODERATE_REVIEW_DRAFT.json',JSON.stringify(payload(),null,2)+'\n','application/json');$('status').textContent='Draft downloaded; keep it with this source package.'});$('export').addEventListener('click',()=>{save('HOMS_MODERATE_EDUCATOR_REVIEW.json',JSON.stringify(payload(),null,2)+'\n','application/json');$('status').textContent='Review record exported. Validate it against this run directory before retaining it as source-bound educator evidence.'});$('load').addEventListener('change',async e=>{const f=e.target.files?.[0];if(!f)return;try{if(f.size>2000000)throw Error('Draft exceeds 2 MB.');const d=JSON.parse(await f.text());if(d.schema!=='dio.homs.moderate.educator_review_record.v1'||d.grade!==context.grade||d.subject!==context.subject||d.random_seed!==context.random_seed||d.context_sha256!==context.context_sha256||JSON.stringify(d.source_hashes)!==JSON.stringify(context.source_hashes)||!Array.isArray(d.question_reviews)||d.question_reviews.length!==rows.length)throw Error('Draft does not match this grade, exam, memo, assessment and CAPS source set.');const byId=new Map(d.question_reviews.map(r=>[r.question_id,r]));if(byId.size!==rows.length||rows.some(r=>!byId.has(r.question_id)))throw Error('Draft question IDs differ from current source.');for(let i=0;i<rows.length;i++){const values=byId.get(rows[i].question_id),card=document.querySelector('[data-row="'+i+'"]');card.querySelectorAll('[data-field]').forEach(input=>input.value=values[input.dataset.field]||'')}for(const [id,value] of [['moderator-name',d.reviewer?.name],['moderator-qualification',d.reviewer?.qualification],['independence',d.reviewer?.independent_of_item_author],['reviewed-at',d.reviewer?.reviewed_at?new Date(d.reviewer.reviewed_at).toISOString().slice(0,16):''],['recommendation',d.recommendation],['overall-rationale',d.overall_rationale]])$(id).value=value||'';progress();$('status').textContent='Matching draft loaded. Recheck source documents and each criterion before export.'}catch(err){$('status').textContent=err.message||'Could not load this review.'}finally{e.target.value=''}});document.querySelectorAll('[data-field],#moderator-name,#moderator-qualification,#independence,#reviewed-at,#recommendation,#overall-rationale').forEach(x=>{x.addEventListener('input',progress);x.addEventListener('change',progress)});progress()})();
</script></main></body></html>""".replace("__GRADE__", str(context.get("grade"))).replace("__SUBJECT__", html.escape(str(context.get("subject") or ""))).replace("__SEED__", str(context.get("random_seed"))).replace("__EXAM_NAME__", "GRADE_EXAM.docx").replace("__MEMO_NAME__", "GRADE_MEMO.docx").replace("__ROWS__", "".join(rows_html)).replace("__CONTEXT__", context_json).replace("__CONTEXT_HASH__", html.escape(str(context.get("context_sha256") or "")))


def build_homs_moderate_customer_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    grade = int(packet.get("grade") or 0)
    if grade not in range(1, 13):
        raise ValueError("grade must be an integer from 1 through 12")
    set_receipt = json.loads((PACK / "GRADE_EXAM_SET_RECEIPT.json").read_text(encoding="utf-8"))
    assignment_doc = json.loads((PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json").read_text(encoding="utf-8"))
    selected = next((row for row in set_receipt.get("results", []) if int(row.get("grade") or 0) == grade), None)
    assignment = next((row for row in assignment_doc.get("assignments", []) if int(row.get("grade") or 0) == grade), None)
    if not selected or not assignment or selected.get("state") != "DRAFT_PACK_CREATED":
        raise ValueError(f"Grade {grade} draft pack is unavailable")
    grade_dir = Path(str(selected["job_dir"])).resolve()
    if not grade_dir.is_relative_to(PACK.resolve()):
        raise ValueError("selected grade path escapes the registered exam set")
    receipt = json.loads((grade_dir / "HOMS_GRADE_EXAM_RECEIPT.json").read_text(encoding="utf-8"))
    assessment_path = grade_dir / "HOMS_GRADE_ASSESSMENT.json"
    assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    paper = grade_dir / "GRADE_EXAM.docx"
    memo = grade_dir / "GRADE_MEMO.docx"
    subject = str(assessment.get("subject") or "")
    if assignment.get("subject_profile") not in grade_dir.name or int(receipt.get("randomization_seed") or -1) != int(assignment_doc["random_seed"]):
        raise ValueError("selected paper is not bound to the randomized grade assignment")
    if packet.get("subject") and str(packet["subject"]).strip().casefold() != subject.casefold():
        raise ValueError(f"Grade {grade} is assigned to {subject}")
    recorded = receipt.get("assessment") or {}
    for role, path in (("exam", paper), ("memo", memo), ("json", assessment_path)):
        if not path.is_file() or _sha(path) != recorded.get(role, {}).get("sha256"):
            raise ValueError(f"Grade {grade} {role} does not match its signed-by-hash exam receipt")

    from products.homs_exam_moderation import moderate_assessment_sources

    source_hash = str(receipt.get("caps_source", {}).get("sha256") or "")
    caps_alignment = _verified_caps_question_alignment(grade, subject, source_hash)
    report = moderate_assessment_sources(
        assessment=assessment,
        paper_text=_docx_text(paper),
        memo_text=_docx_text(memo),
        expected_grade=grade,
        expected_subject=subject,
        expected_total_marks=int(assessment.get("total_marks") or 0),
        source_hash=source_hash,
        caps_alignment=caps_alignment,
    )
    out = Path(output_dir).resolve()
    sources = out / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    paper_copy, memo_copy = sources / paper.name, sources / memo.name
    shutil.copy2(paper, paper_copy)
    shutil.copy2(memo, memo_copy)
    assessment_copy = sources / "HOMS_GRADE_ASSESSMENT.json"
    shutil.copy2(assessment_path, assessment_copy)
    alignment_copy = sources / "CAPS_QUESTION_ALIGNMENT.json"
    shutil.copy2(CAPS_ALIGNMENT_PATH, alignment_copy)
    identity_copy = sources / "CAPS_DOCUMENT_IDENTITY_AUDIT.json"
    shutil.copy2(CAPS_IDENTITY_PATH, identity_copy)
    caps_source = Path(caps_alignment["caps_pdf_path"])
    caps_copy = sources / "CAPS_SOURCE.pdf"
    shutil.copy2(ROOT / caps_source, caps_copy)
    report_path = out / "HOMS_MECHANICAL_PREMODERATION_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    review_context = _moderator_review_context(
        assessment, grade=grade, subject=subject, seed=int(assignment_doc["random_seed"]),
        paper=paper, memo=memo, assessment_path=assessment_path, caps_alignment=caps_alignment,
        report_path=report_path, caps_copy=caps_copy,
    )
    review_page = out / "EDUCATOR_MODERATION_REVIEW.html"
    review_page.write_text(_render_moderator_review_page(review_context), encoding="utf-8")
    blocks = []
    for check in report["checks"]:
        blocks.append(f"<tr><th>{html.escape(check['check'])}</th><td>{html.escape(check['state'])}</td><td>{html.escape(check['detail'])}</td></tr>")
    preview = out / "CUSTOMER_MODERATION_REVIEW.html"
    preview.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>HOMS moderation · Grade {grade}</title><style>body{{font:16px/1.55 system-ui,sans-serif;max-width:1050px;margin:32px auto;padding:0 18px;color:#20302f}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #ccd5cf}}thead th{{background:#184b44;color:white}}.note{{background:#fff7e8;border-left:4px solid #a66a27;padding:12px}}</style><main><p>HOMS MODERATE · GRADE {grade} · {html.escape(subject)}</p><h1>Mechanical pre-moderation review</h1><p>State: <strong>{html.escape(report['mechanical_state'])}</strong></p><p><a href='EDUCATOR_MODERATION_REVIEW.html'>Open educator review workspace</a> · <a href='sources/{paper_copy.name}'>Source exam</a> · <a href='sources/{memo_copy.name}'>Source marking memo</a> · <a href='sources/CAPS_SOURCE.pdf'>Official CAPS source PDF</a> · <a href='{report_path.name}'>Machine-readable report</a></p><table><thead><tr><th>Check</th><th>State</th><th>Detail</th></tr></thead><tbody>{''.join(blocks)}</tbody></table><p class='note'>This checker covers structural consistency and rendered-document correspondence only. It is not an independent subject moderation, content-accuracy decision, curriculum approval, or classroom release.</p></main></html>\n",
        encoding="utf-8",
    )
    output_files = []
    for path in (paper_copy, memo_copy, assessment_copy, alignment_copy, identity_copy, caps_copy, report_path, preview, review_page):
        output_files.append({"path": path.relative_to(out).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)})
    package_receipt = {
        "schema": "dio.homs.moderate.customer_execution.v1", "grade": grade, "subject": subject,
        "random_seed": int(assignment_doc["random_seed"]), "subject_profile": assignment["subject_profile"],
        "mechanical_state": report["mechanical_state"], "check_count": len(report["checks"]),
        "passed_checks": sum(row["state"] == "PASS" for row in report["checks"]),
        "source_exam_sha256": _sha(paper), "source_memo_sha256": _sha(memo),
        "source_assessment_sha256": _sha(assessment_path), "source_caps_sha256": receipt["caps_source"]["sha256"],
        "source_caps_alignment_sha256": caps_alignment["caps_alignment_sha256"],
        "source_caps_pdf_path": caps_alignment["caps_pdf_path"],
        "independent_moderation_decision": "NOT_ISSUED", "educator_review_required": True,
        "classroom_release_authorized": False, "external_effects": False, "outputs": output_files,
    }
    package_path = out / "CUSTOMER_PACKAGE_RECEIPT.json"
    package_path.write_text(json.dumps(package_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package_receipt
