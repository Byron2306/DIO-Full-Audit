"""Build a hash-checked Grade 1–12 HOMS Moderate review index."""
from __future__ import annotations
import hashlib
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_MODERATE_CUSTOMER_GRADE_BATCH_20261104_V23"
ASSIGNMENT = ROOT / "deliverables/homs_random_grade_exam_set_20261101/RANDOM_SUBJECT_ASSIGNMENTS.json"
OUTPUT = BATCH / "index.html"
MANIFEST = BATCH / "HOMS_MODERATE_MASTER_INDEX_MANIFEST.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    receipt_path = BATCH / "HOMS_MODERATE_CUSTOMER_GRADE_BATCH_RECEIPT.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assignments = json.loads(ASSIGNMENT.read_text(encoding="utf-8"))
    assignment_rows = {int(row["grade"]): row for row in assignments["assignments"]}
    if (receipt.get("schema") != "dio.homs.moderate.customer_grade_batch.v1"
            or receipt.get("grade_count") != 12
            or receipt.get("random_seed") != assignments.get("random_seed")
            or receipt.get("independent_moderation_decision") != "NOT_ISSUED"
            or receipt.get("classroom_release_authorized") is not False
            or len(receipt.get("results", [])) != 12):
        raise ValueError("Current batch must contain 12 held grades with independent moderation unissued")
    rows = []
    for result in sorted(receipt["results"], key=lambda row: row["grade"]):
        grade = int(result["grade"])
        if grade not in range(1, 13) or grade in {row["grade"] for row in rows}:
            raise ValueError(f"Invalid or duplicate grade: {grade}")
        assigned = assignment_rows.get(grade, {})
        if (result.get("random_seed") != assignments["random_seed"]
                or result.get("subject_profile") != assigned.get("subject_profile")
                or result.get("mechanical_state") != "PASS"
                or result.get("check_count") != 8
                or result.get("passed_checks") != 8):
            raise ValueError(f"Grade {grade} does not match the randomized assignment or 8/8 checks")
        review = BATCH / f"grade-{grade:02d}/EDUCATOR_MODERATION_REVIEW.html"
        report = BATCH / f"grade-{grade:02d}/HOMS_MECHANICAL_PREMODERATION_REPORT.json"
        for output in result.get("outputs", []):
            path = BATCH / f"grade-{grade:02d}" / output["path"]
            if not path.is_file() or sha(path) != output.get("sha256"):
                raise ValueError(f"Grade {grade} output hash mismatch: {output.get('path')}")
        if not review.is_file() or not report.is_file():
            raise FileNotFoundError(f"Grade {grade} moderation review/report is missing")
        paper_dir = ROOT / "deliverables/homs_random_grade_exam_set_20261101/grades" / f"grade-{grade:02d}-{assigned['subject_profile']}"
        paper = paper_dir / "GRADE_EXAM.pdf"
        memo = paper_dir / "GRADE_MEMO.pdf"
        for path, expected in ((paper_dir / "GRADE_EXAM.docx", result["source_exam_sha256"]),
                               (paper_dir / "GRADE_MEMO.docx", result["source_memo_sha256"])):
            if not path.is_file() or sha(path) != expected:
                raise ValueError(f"Grade {grade} randomized exam/memo source binding failed: {path}")
        if not paper.is_file() or not memo.is_file():
            raise FileNotFoundError(f"Grade {grade} print exam/memo PDF is missing")
        rows.append({"grade": grade, "subject": result["subject"], "profile": assigned["subject_profile"],
                     "check_count": result["check_count"], "passed_checks": result["passed_checks"],
                     "review": str(review.relative_to(BATCH)), "review_sha256": sha(review),
                     "report": str(report.relative_to(BATCH)), "report_sha256": sha(report),
                     "exam_pdf": os.path.relpath(paper, BATCH), "exam_pdf_sha256": sha(paper),
                     "memo_pdf": os.path.relpath(memo, BATCH), "memo_pdf_sha256": sha(memo),
                     "exam_docx_sha256": result["source_exam_sha256"], "memo_docx_sha256": result["source_memo_sha256"],
                     "caps_sha256": result["source_caps_sha256"]})
    if [r["grade"] for r in rows] != list(range(1, 13)):
        raise ValueError("Grade batch is incomplete")
    body = []
    for row in rows:
        links = (f'<a href="{html.escape(row["review"])}">Educator moderation review</a> · '
                 f'<a href="{html.escape(row["report"])}">8-check report</a> · '
                 f'<a href="{html.escape(row["exam_pdf"])}">Exam PDF</a> · '
                 f'<a href="{html.escape(row["memo_pdf"])}">Memo PDF</a>')
        body.append(f'<tr><th scope="row">Grade {row["grade"]:02}</th><td>{html.escape(row["subject"])}</td>'
                    f'<td>{row["passed_checks"]}/{row["check_count"]} passed</td><td>{links}</td></tr>')
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOMS Moderate · Grade 1–12 review index</title>
<style>body{margin:0;background:#f4f5f1;color:#18302c;font:16px/1.55 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:clamp(1.2rem,4vw,3rem)}h1{font-size:clamp(2rem,5vw,3.3rem);line-height:1.08;max-width:900px}.notice{padding:1rem 1.25rem;background:#fff7e8;border-left:5px solid #bd8740;margin:1.4rem 0}.table{overflow:auto;background:white}table{border-collapse:collapse;min-width:850px;width:100%}th,td{text-align:left;vertical-align:top;padding:.85rem;border-bottom:1px solid #ccd7d2}thead th{background:#194b46;color:white}a{color:#075e70}a:focus-visible{outline:3px solid #bd8740;outline-offset:3px}small{color:#455c55}</style></head><body><main><p><strong>HOMS · CAPS-linked assessment review</strong></p><h1>Grade 1–12 moderation review</h1>
<p class="notice">Each randomized grade pack passed 8 mechanical pre-moderation checks against its current exam, memo and CAPS alignment sources. This is a structural check only. Independent subject moderation has not been issued, educator approval is still required, and classroom release is not authorized.</p>
<p>Random seed: <strong>20261101</strong>. Subject assignments follow the reproducibility audit and approved subject pool for each CAPS phase. Use the grade-specific review to inspect source bindings and record educator feedback.</p><div class="table"><table><thead><tr><th>Grade</th><th>Randomized subject</th><th>Mechanical checks</th><th>Review materials</th></tr></thead><tbody>''' + ''.join(body) + '''</tbody></table></div>
<p><a href="../../../deliverables/homs_random_grade_exam_set_20261101/index.html">Open the complete exam and memo collection</a> · <a href="HOMS_MODERATE_CUSTOMER_GRADE_BATCH_RECEIPT.json">Open batch receipt</a></p><footer>All review rows link to the source-bound current batch. Mechanical checks do not establish subject accuracy, fairness, curriculum completeness or memo correctness.</footer></main></body></html>'''
    OUTPUT.write_text(page, encoding="utf-8")
    manifest = {"schema": "dio.homs.moderate.master_index.v1", "batch_receipt_sha256": sha(receipt_path),
                "assignment_manifest_sha256": sha(ASSIGNMENT), "random_seed": assignments["random_seed"],
                "grade_count": len(rows), "independent_moderation_decision": "NOT_ISSUED",
                "classroom_release_authorized": False, "index": str(OUTPUT.relative_to(ROOT)),
                "index_sha256": sha(OUTPUT), "grades": rows}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"index": str(OUTPUT.relative_to(ROOT)), "grades": len(rows),
                      "checks_passed": sum(row["passed_checks"] for row in rows),
                      "independent_moderation_decision": manifest["independent_moderation_decision"]}, indent=2))

if __name__ == "__main__":
    main()
