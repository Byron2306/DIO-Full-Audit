#!/usr/bin/env python3
"""Replace broad Grade 12 Business Studies summary citations with checked topic pages."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'deliverables/homs_random_grade_exam_set_20261101'
GRADE = PACK / 'grades/grade-12-business_studies'
ALIGNMENT = PACK / 'CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json'
SOURCE = ROOT / 'corpora/caps/pdf/fet_grade_10_12/caps_fet_business_studies_gr_10-12_web_0ca7.pdf'
OUTPUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_GRADE12_BUSINESS_CAPS_MAPPING_CORRECTION_20261101.json'
EXPECTED_SOURCE_SHA256 = 'e6f0a21b96fa87ccfccb732a9240a579bf0157916b86a1cdd98a2876cf76db27'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def page_text(page: int) -> str:
    result = subprocess.run(
        ['pdftotext', '-layout', '-f', str(page), '-l', str(page), str(SOURCE), '-'],
        check=True, capture_output=True, text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise ValueError(f'CAPS page {page} produced no text')
    return value


def main() -> None:
    if sha(SOURCE.read_bytes()) != EXPECTED_SOURCE_SHA256:
        raise ValueError('Official CAPS Business Studies source hash changed')
    alignment = json.loads(ALIGNMENT.read_text(encoding='utf-8'))
    assessment = json.loads((GRADE / 'HOMS_GRADE_ASSESSMENT.json').read_text(encoding='utf-8'))
    receipt = json.loads((GRADE / 'HOMS_GRADE_EXAM_RECEIPT.json').read_text(encoding='utf-8'))
    if receipt.get('caps_source', {}).get('sha256') != EXPECTED_SOURCE_SHA256:
        raise ValueError('Grade 12 exam source receipt does not identify the verified Business Studies CAPS PDF')
    grade = next(row for row in alignment['grades'] if row.get('grade') == 12)
    if grade.get('caps_source_sha256') != EXPECTED_SOURCE_SHA256:
        raise ValueError('Grade 12 question map has a different CAPS source')
    question_prompts = {
        str(question['number']): question['prompt']
        for section in assessment.get('sections') or []
        for question in section.get('questions') or []
    }
    old_mappings = {str(row['question_id']): row for row in grade.get('question_mappings') or []}
    if set(question_prompts) != {f'1.{n}' for n in range(1, 6)} or set(old_mappings) != set(question_prompts):
        raise ValueError('Grade 12 paper and CAPS map must contain the same five question IDs')

    specifications = {
        '1.1': {
            'caps_topic': 'Micro, market and macro business environments (prior-year CAPS knowledge)',
            'coverage_link': 'Uses the CAPS environmental-category framework to classify an internal factor, a market factor and a broad external factor; the stimulus supplies owners/workers, farmers and shops, while a macro factor is drawn from grade-level knowledge.',
            'pages': [(19, ['micro', 'market', 'macro'])],
        },
        '1.2': {
            'caps_topic': 'Human Resources function; quality of performance within business functions',
            'coverage_link': 'Connects employee skills development and safe practice with the investment, production-capacity and product-consistency considerations in the case.',
            'pages': [(39, ['function: recruitment and selection', 'skills development']),
                      (45, ['quality of performance', 'business functions'])],
        },
        '1.3': {
            'caps_topic': 'Corporate social responsibility; Human Rights, inclusivity and environmental issues',
            'coverage_link': 'Examines accurate product information, fair treatment of suppliers and workers, and responsible business conduct using the case context.',
            'pages': [(43, ['corporate social responsibility']),
                      (44, ['human rights', 'environmental issues'])],
        },
        '1.4': {
            'caps_topic': 'Macro-environment business strategies',
            'coverage_link': 'Evaluates an external sales-channel opportunity and risks, identifying information the business should investigate before choosing a response.',
            'pages': [(41, ['macro business environment', 'evaluate', 'recommendations'])],
        },
        '1.5': {
            'caps_topic': 'Formulation, implementation and evaluation of business strategies',
            'coverage_link': 'Recommends whether and under what conditions the business should respond to a larger-order opportunity, using case evidence and risk controls.',
            'pages': [(41, ['formulation', 'implementation', 'evaluation', 'recommendations'])],
        },
    }
    source_page_texts = {page: page_text(page) for spec in specifications.values() for page, _ in spec['pages']}
    new_mappings = []
    for question_id in sorted(specifications, key=lambda value: int(value.split('.')[1])):
        spec = specifications[question_id]
        citations = []
        for page, terms in spec['pages']:
            text = source_page_texts[page]
            folded = re.sub(r'\s+', ' ', text.casefold())
            absent = [term for term in terms if re.sub(r'\s+', ' ', term.casefold()) not in folded]
            if absent:
                raise ValueError(f'CAPS page {page} is missing expected topic terms: {absent}')
            citations.append({
                'physical_pdf_page': page,
                'page_text_sha256': sha(text.encode('utf-8')),
                'topic_terms_found': terms,
            })
        mapping = old_mappings[question_id]
        mapping.update({
            'prompt': question_prompts[question_id],
            'caps_topic': spec['caps_topic'],
            'coverage_link': spec['coverage_link'],
            'caps_pages': citations,
        })
        new_mappings.append(mapping)
    grade['question_mappings'] = new_mappings
    alignment['grade12_business_studies_question_topic_mapping_refreshed'] = True
    alignment['grade12_business_studies_mapping_claim_boundary'] = (
        'Question-to-topic citations are checked against exact extracted official CAPS page text. '
        'They do not establish full curriculum coverage, assessment validity, grade/term fit, or educator approval.'
    )
    ALIGNMENT.write_text(json.dumps(alignment, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    evidence = {
        'schema': 'dio.homs.grade12_business_studies_caps_mapping_correction.v1',
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'product': 'HOMS Exam', 'grade': 12, 'subject': 'Business Studies',
        'source_pdf': SOURCE.relative_to(ROOT).as_posix(), 'source_pdf_sha256': EXPECTED_SOURCE_SHA256,
        'previous_citation_page': 16,
        'new_question_mappings': [
            {'question_id': row['question_id'], 'caps_topic': row['caps_topic'],
             'coverage_link': row['coverage_link'], 'caps_pages': row['caps_pages']}
            for row in new_mappings
        ],
        'page_text_hash_basis': 'SHA-256 of stripped UTF-8 text extracted from the one-based physical PDF page using pdftotext -layout -f N -l N.',
        'question_prompts_and_memo_marks_changed': False,
        'random_subject_assignment_changed': False,
        'educator_review_required': True,
        'classroom_release_authorized': False,
        'claim_boundary': 'This repairs source-page/topic traceability. It does not establish full CAPS coverage, item validity, term fit or educator approval.',
    }
    OUTPUT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'grade': 12, 'question_count': len(new_mappings), 'topic_pages': len({p['physical_pdf_page'] for m in new_mappings for p in m['caps_pages']}), 'alignment': ALIGNMENT.relative_to(ROOT).as_posix(), 'evidence': OUTPUT.relative_to(ROOT).as_posix()}, indent=2))


if __name__ == '__main__':
    main()
