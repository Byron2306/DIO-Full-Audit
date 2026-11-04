#!/usr/bin/env python3
"""Create a source-bound current Document Studio edit proof package."""
from __future__ import annotations
import csv,hashlib,json,re,subprocess,zipfile
from datetime import datetime,timezone
from pathlib import Path
from docx import Document
ROOT=Path(__file__).resolve().parents[1]
REQUEST=ROOT/'samples/document_studio/current_truth_review_20261104/request.json'
SOURCE=ROOT/'samples/document_studio/current_truth_review_20261104/source.txt'
JOB=ROOT/'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3'
OUT=ROOT/'deliverables/document_studio_current_20261104'

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def docx_text(p:Path)->str:
 d=Document(p); return '\n'.join(x.text for x in d.paragraphs)
source=SOURCE.read_text();clean=docx_text(JOB/'CLEAN_EDITED_COPY.docx');ledger=list(csv.DictReader((JOB/'CHANGE_LEDGER.csv').open(encoding='utf-8')))
protected=['pH','NTU','QMS-07','2 minutes','2 and 8 degrees Celsius','6.5','9.5','1 NTU']
checks={f'protected_{re.sub("[^A-Za-z0-9]+","_",token).strip("_").lower()}':token in clean for token in protected}
source_numbers=set(re.findall(r'\b\d+(?:\.\d+)?\b',source)); output_numbers=set(re.findall(r'\b\d+(?:\.\d+)?\b',clean))
checks['all_source_numeric_values_preserved']=source_numbers <= output_numbers
checks['sterile_bottle_negation_preserved']='do not rinse a sterile microbiological bottle' in clean.casefold()
checks['community_safety_authority_gate_preserved']='do not communicate' in clean.casefold() and 'authorized official' in clean.casefold()
checks['tracked_redline_exists']=(JOB/'REDLINE_REVIEW_COPY.docx').is_file() and (JOB/'pdf/REDLINE_REVIEW_COPY.pdf').is_file()
checks['change_ledger_covers_all_source_paragraphs']=len(ledger)==7 and len({r['paragraph_id'] for r in ledger})==7
checks['human_editor_approval_remains_pending']=json.loads((JOB/'TECHNICAL_EDIT_REVIEW_VALIDATION.json').read_text())['state']=='NEEDS_TECHNICAL_EDITOR_COMPLETION'
checks['no_external_processing_used']=json.loads((JOB/'DOCUMENT_STUDIO_RECEIPT.json').read_text())['processing']['remote_inference_used'] is False
qa=json.loads((JOB/'DOCUMENT_STUDIO_QA.json').read_text())
report={'schema':'dio.document_studio.current_edit_review_scorecard.v1','created_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'job_id':'DIO-DOC-EDIT-20261104-V3','source_sha256':sha(SOURCE),'request_sha256':sha(REQUEST),'clean_docx_sha256':sha(JOB/'CLEAN_EDITED_COPY.docx'),'redline_docx_sha256':sha(JOB/'REDLINE_REVIEW_COPY.docx'),'change_ledger_sha256':sha(JOB/'CHANGE_LEDGER.csv'),'checks':checks,'passed_check_count':sum(checks.values()),'check_count':len(checks),'model_label_mismatch_count':len(qa.get('change_label_normalization_flags') or []),'automated_integrity':'PASS' if qa.get('passed') else 'FAIL','professional_quality':'UNVERIFIED','human_technical_review':'PENDING','client_approval':'PENDING','release_authorized':False,'source_case':'controlled synthetic procedure; not a real municipal client document','limitations':['Numeric/token preservation and formatting checks do not prove technical correctness.','A qualified technical editor must accept/reject all seven paragraph changes.','The content is a synthetic controlled example, not a consented customer case.']}
(JOB/'CURRENT_REVIEW_SCORECARD.json').write_text(json.dumps(report,indent=2)+'\n')
readme='''# Document Studio · current technical edit candidate\n\nThis is a current in-snapshot before/after technical edit demonstration generated locally on 2026-11-04. It includes the source procedure, clean editable DOCX, tracked redline DOCX/PDF, paragraph change ledger, terminology list, protected-number checks, and the blank technical-editor review form.\n\n## Review status\n\n- Automated integrity checks: %s (%s/%s checks).\n- Document Studio mechanical QA: %s.\n- The local model originally labelled changed paragraphs `no_change`; the pipeline now records the provider label, normalizes the displayed category against actual text, and flags those mismatches.\n- Human technical-editor review: pending for all seven paragraphs. Client approval and release authorization: pending / not granted.\n- The example is synthetic. It is not proof of customer acceptance or expert certification.\n\nOpen `CURRENT_REVIEW_SCORECARD.json`, `TECHNICAL_EDIT_REVIEW_TEMPLATE.csv`, and `TECHNICAL_EDIT_REVIEW_VALIDATION.json` before relying on the output.\n''' % ('PASS' if all(checks.values()) else 'REVIEW REQUIRED',sum(checks.values()),len(checks),'PASS' if qa.get('passed') else 'REVIEW REQUIRED')
(JOB/'README.md').write_text(readme)
archive=OUT/'DOCUMENT_STUDIO_CURRENT_TRANSFORMATION_CANDIDATE.zip'
include=['README.md','CURRENT_REVIEW_SCORECARD.json','DOCUMENT_STUDIO_RECEIPT.json','DOCUMENT_STUDIO_QA.json','CHANGE_LEDGER.csv','CLEAN_EDITED_COPY.docx','REDLINE_REVIEW_COPY.docx','TECHNICAL_EDIT_REVIEW_TEMPLATE.csv','TECHNICAL_EDIT_REVIEW_VALIDATION.json','TERMINOLOGY_GLOSSARY.csv','pdf/CLEAN_EDITED_COPY.pdf','pdf/REDLINE_REVIEW_COPY.pdf']
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for rel in include:z.write(JOB/rel,rel)
print(json.dumps({'archive':str(archive),'checks':sum(checks.values()),'total':len(checks),'model_label_mismatches':report['model_label_mismatch_count'],'human_review':'PENDING','release_authorized':False},indent=2))
