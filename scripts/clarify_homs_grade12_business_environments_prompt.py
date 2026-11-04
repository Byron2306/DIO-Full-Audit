#!/usr/bin/env python3
"""Clarify the Grade 12 macro-environment source boundary without changing marks."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from build_homs_grade_exam_candidate import render_docx, validate_pack
PACK = ROOT / 'deliverables/homs_random_grade_exam_set_20261101'
GRADE = PACK / 'grades/grade-12-business_studies'
ALIGNMENT = PACK / 'CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json'
OUTPUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_GRADE12_BUSINESS_ENVIRONMENTS_PROMPT_CLARIFICATION_20261101.json'
OLD = '1.1 Identify one factor in each business environment: micro, market and macro. Classify and justify each. [8]'
NEW = '1.1 Identify one micro and one market factor from the case. Then name a plausible macro-environment factor businesses may face; the case does not specify one. Classify each factor and justify your classifications. [8]'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assessment_path = GRADE / 'HOMS_GRADE_ASSESSMENT.json'
    exam_path = GRADE / 'GRADE_EXAM.docx'
    memo_path = GRADE / 'GRADE_MEMO.docx'
    receipt_path = GRADE / 'HOMS_GRADE_EXAM_RECEIPT.json'
    assessment = json.loads(assessment_path.read_text(encoding='utf-8'))
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    q = next(q for section in assessment['sections'] for q in section['questions'] if q.get('number') == '1.1')
    if q['prompt'] not in {OLD, NEW}:
        raise ValueError('Grade 12 question 1.1 changed unexpectedly')
    prior_prompt = q['prompt']
    memo_before = json.dumps(q['memo'], sort_keys=True, ensure_ascii=False)
    q['prompt'] = NEW
    if validate_pack(assessment, 12, 'Business Studies', 50):
        raise ValueError('Clarified Grade 12 Business Studies pack failed its structural validation')
    if json.dumps(q['memo'], sort_keys=True, ensure_ascii=False) != memo_before:
        raise ValueError('Prompt clarification unexpectedly changed memo points')
    assessment_path.write_text(json.dumps(assessment, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    source = receipt['caps_source']
    source_label = f"DBE CAPS {source['title']} · fet_grade_10_12 · SHA-256 {source['sha256']} · {source['source_url']}"
    render_docx(assessment, exam_path, False, source_label)
    render_docx(assessment, memo_path, True, source_label)
    receipt['created_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    receipt['assessment']['exam']['sha256'] = sha(exam_path)
    receipt['assessment']['memo']['sha256'] = sha(memo_path)
    receipt['assessment']['json']['sha256'] = sha(assessment_path)
    receipt['validation']['question_marks_match'] = True
    receipt['validation']['one_mark_memo_points_reconcile'] = True
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    alignment = json.loads(ALIGNMENT.read_text(encoding='utf-8'))
    grade = next(row for row in alignment['grades'] if row.get('grade') == 12)
    mapping = next(row for row in grade['question_mappings'] if row.get('question_id') == '1.1')
    mapping['prompt'] = NEW
    for key, role in (('exam_sha256', 'exam'), ('memo_sha256', 'memo'), ('assessment_json_sha256', 'json')):
        grade[key] = receipt['assessment'][role]['sha256']
    grade['json_sha256'] = receipt['assessment']['json']['sha256']
    alignment['grade12_business_studies_question_prompt_clarified'] = True
    ALIGNMENT.write_text(json.dumps(alignment, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    evidence = {
        'schema': 'dio.homs.grade12_business_studies_prompt_clarification.v1',
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'grade': 12, 'subject': 'Business Studies', 'question_id': '1.1',
        'previous_prompt': prior_prompt, 'current_prompt': NEW,
        'reason': 'The original case supplied micro and market factors but no macro factor; the prompt now explicitly distinguishes case evidence from grade-level macro knowledge.',
        'question_marks': 8, 'total_paper_marks': 50,
        'memo_points_changed': False, 'random_subject_assignment_changed': False,
        'exam_sha256': sha(exam_path), 'memo_sha256': sha(memo_path),
        'assessment_sha256': sha(assessment_path), 'grade_receipt_sha256': sha(receipt_path),
        'human_educator_review_required': True, 'classroom_release_authorized': False,
        'claim_boundary': 'This improves prompt evidence clarity and verifies unchanged mark allocation. It is not educator moderation or a full assessment-validity finding.',
    }
    OUTPUT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'grade': 12, 'question_id': '1.1', 'marks_unchanged': True, 'random_assignment_unchanged': True, 'evidence': OUTPUT.relative_to(ROOT).as_posix()}, indent=2))


if __name__ == '__main__':
    main()
