#!/usr/bin/env python3
"""Run HOMS Moderate's source-bound pre-moderation path on the grade batch."""
from __future__ import annotations

import json
import hashlib
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from docx import Document
from products.customer_product_router import run_customer_product

BATCH = ROOT / 'deliverables/homs_random_grade_exam_set_20261101'
OUT = BATCH / 'moderation_renderer_20261109_v13'

CRITERIA = [
    ('R1', 'The learner paper and marking memo must state the same assessment total.'),
    ('R2', 'Every question mark must have a corresponding explicit marking point.'),
    ('R3', 'Question wording must appear consistently in the learner paper and marking memo.'),
    ('R4', 'The requested grade and subject must match the randomized subject assignment.'),
    ('R5', 'The official curriculum source must be identified by title and document hash.'),
]

def docx_text(path: Path) -> str:
    document = Document(path)
    lines = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            lines.append(' | '.join(cell.text for cell in row.cells))
    return '\n'.join(lines)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build_packet(grade: int, subject: str, assignment_json: str) -> dict[str, Any]:
    folder = BATCH / 'grades' / f'grade-{grade:02d}-{subject}'
    pack_path = folder / 'HOMS_GRADE_ASSESSMENT.json'
    receipt_path = folder / 'HOMS_GRADE_EXAM_RECEIPT.json'
    pack_text = pack_path.read_text(encoding='utf-8')
    receipt_text = receipt_path.read_text(encoding='utf-8')
    pack = json.loads(pack_text)
    receipt = json.loads(receipt_text)
    paper_text = docx_text(folder / 'GRADE_EXAM.docx')
    memo_text = docx_text(folder / 'GRADE_MEMO.docx')
    criteria_text = '\n'.join(f'{key}: {text}' for key, text in CRITERIA)
    sources = [
        {'source_id':'BRIEF','title':'HOMS moderation checklist','text':criteria_text},
        {'source_id':'ASSESSMENT','title':f"Grade {grade} structured assessment","text":pack_text},
        {'source_id':'PAPER','title':f"Grade {grade} rendered learner paper","text":paper_text},
        {'source_id':'MEMO','title':f"Grade {grade} rendered marking memo","text":memo_text},
        {'source_id':'RECEIPT','title':f"Grade {grade} source and release receipt","text":receipt_text},
        {'source_id':'ASSIGNMENTS','title':'Randomized subject assignment manifest','text':assignment_json},
    ]
    requirements = [{'requirement_id':key,'label':text,'source_id':'BRIEF','quote':f'{key}: {text}','mandatory':True} for key,text in CRITERIA]
    assignment = next(row for row in json.loads(assignment_json)['assignments'] if int(row['grade']) == grade)
    first_prompt = pack['sections'][0]['questions'][0]['prompt']
    first_memo = pack['sections'][0]['questions'][0]['memo'][0]['point']
    caps_hash = receipt['caps_source']['sha256']
    evidence = [
        {'evidence_id':'E1-PAPER-TOTAL','source_id':'PAPER','quote':f"{pack['total_marks']} marks",'supports':['R1']},
        {'evidence_id':'E1-MEMO-TOTAL','source_id':'MEMO','quote':f"{pack['total_marks']} marks",'supports':['R1']},
        {'evidence_id':'E2-ASSESSMENT','source_id':'ASSESSMENT','quote':f'"point": "{first_memo}"','supports':['R2']},
        {'evidence_id':'E3-PAPER-PROMPT','source_id':'PAPER','quote':first_prompt,'supports':['R3']},
        {'evidence_id':'E3-MEMO-PROMPT','source_id':'MEMO','quote':first_prompt,'supports':['R3']},
        {'evidence_id':'E4-ASSIGNMENT','source_id':'ASSIGNMENTS','quote':f'"subject_profile": "{assignment["subject_profile"]}"','supports':['R4']},
        {'evidence_id':'E5-CAPS-HASH','source_id':'RECEIPT','quote':caps_hash,'supports':['R5']},
    ]
    issue = {'requirement_id':'R5','source_id':'RECEIPT','quote':'"classroom_approval": "PENDING_QUALIFIED_EDUCATOR_REVIEW"'}
    return {
        'case_id':f'HOMS-MOD-GRADE-{grade:02d}-20261101',
        'title':f"HOMS Moderate pre-moderation · Grade {grade} {pack['subject']}",
        'owner_authorized':True,
        'grade':grade,
        'subject':pack['subject'],
        'synthetic_acceptance_not_customer_evidence':True,
        'review_at':'2026-11-01T07:30:00+00:00',
        'sources':sources,
        'requirements':requirements,
        'evidence':evidence,
        'issues':[issue],
        'assessment_review':{
            'assessment_source_id':'ASSESSMENT','paper_source_id':'PAPER','memo_source_id':'MEMO','receipt_source_id':'RECEIPT',
            'expected_grade':grade,'expected_subject':pack['subject'],'expected_total_marks':pack['total_marks'],
        },
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT, help='New or resumable moderation output directory.')
    args = parser.parse_args()
    output_root = args.out.expanduser().resolve()
    assignment_path=BATCH/'RANDOM_SUBJECT_ASSIGNMENTS.json'
    assignment_json=assignment_path.read_text(encoding='utf-8')
    assignments=json.loads(assignment_json)
    output_root.mkdir(parents=True,exist_ok=True)
    results=[]
    for row in assignments['assignments']:
        grade=int(row['grade']);subject=str(row['subject_profile'])
        target=output_root/f'grade-{grade:02d}-{subject}'
        finished=target/'CUSTOMER_EXECUTION_RECEIPT.json'
        findings_path=target/'HOMS_MECHANICAL_PREMODERATION_REPORT.json'
        if finished.is_file() and findings_path.is_file():
            native=json.loads(findings_path.read_text(encoding='utf-8'))
            results.append({'grade':grade,'subject':subject,'state':native['mechanical_state'],'output':str(target.relative_to(ROOT)),'customer_execution_receipt_sha256':sha256(finished),'moderation_findings_sha256':sha256(findings_path),'resumed_existing_receipt':True})
            print(f"grade {grade:02d}: HOMS Moderate {native['mechanical_state']} (already complete)",flush=True)
            continue
        if target.exists() and any(target.iterdir()):
            raise SystemExit(f'retain partial output for review; refusing to overwrite {target}')
        packet=build_packet(grade,subject,assignment_json)
        result=run_customer_product('HOMS Moderate',packet,target,render_pdf=False)
        native=json.loads((target/'HOMS_MECHANICAL_PREMODERATION_REPORT.json').read_text(encoding='utf-8'))
        results.append({'grade':grade,'subject':native.get('subject') or subject,'state':native['mechanical_state'],'output':str(target.relative_to(ROOT)),'customer_execution_receipt_sha256':sha256(finished),'moderation_findings_sha256':sha256(findings_path)})
        print(f"grade {grade:02d}: HOMS Moderate {native['mechanical_state']}",flush=True)
    summary={'schema':'dio.homs.moderation_batch_receipt.v1','created_at':datetime.now(timezone.utc).isoformat(),'product':'HOMS Moderate','synthetic_internal_review':True,'results':results,'grade_count':len(results),'mechanical_pass_count':sum(row['state']=='PASS' for row in results),'mechanical_correction_count':sum(row['state']!='PASS' for row in results),'independent_moderation_decision':'NOT_ISSUED','educator_review_required':True,'release_authorized':False}
    (output_root/'HOMS_MODERATION_BATCH_RECEIPT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return 0

if __name__=='__main__': raise SystemExit(main())
