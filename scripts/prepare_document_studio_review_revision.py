#!/usr/bin/env python3
"""Prepare an explicit, unapproved correction revision for the Document Studio demo."""
from __future__ import annotations
import csv,hashlib,json,subprocess,zipfile
from datetime import datetime,timezone
from pathlib import Path
from docx import Document
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT))
from adapters.document_studio.pipeline import create_clean_docx,create_redline_docx,paragraphs_from_text
JOB=ROOT/'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3'
SRC=ROOT/'samples/document_studio/current_truth_review_20261104/source.txt'
source_text=SRC.read_text(encoding='utf-8'); paras=paragraphs_from_text(source_text)
original=json.loads((JOB/'PROVIDER_OUTPUT.json').read_text()); edits={r['paragraph_id']:dict(r) for r in original['edits']}
corrections={
'P5':('Procedure: Before sampling, allow the tap to run for 2 minutes. Rinse the probe with clean water. Do not rinse a sterile microbiological bottle. Record pH and turbidity in NTU at the site. Samples must be kept in a cooler between 2 and 8 degrees Celsius.','The previous draft removed the verb after “but not,” making the sterile-bottle instruction ambiguous. Restore an explicit prohibition; numeric limits remain unchanged.'),
'P7':('Escalation: If pH is below 6.5 or above 9.5, or turbidity is higher than 1 NTU, notify the team leader immediately. Do not tell the community that the water is safe or unsafe until the authorised official has reviewed the result.','Retain the source-authority gate and exact threshold language in this proposed review revision.')}
proposal={'schema':'dio.document_studio.editorial_correction_proposal.v1','job_id':'DIO-DOC-EDIT-20261104-V3','revision_id':'REVISION-2','created_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'status':'UNAPPROVED_REVIEW_CANDIDATE','editor_identity':'AI-assisted operator preparation; no independent qualification asserted','changes':[],'human_technical_review':'PENDING','client_approval':'PENDING','release_authorized':False}
for pid,(text,reason) in corrections.items():
 row=edits[pid];proposal['changes'].append({'paragraph_id':pid,'model_candidate':row['revised'],'review_revision_candidate':text,'reason':reason,'decision':'PROPOSED_NOT_APPROVED'})
 row['revised']=text;row['provider_category']=row.get('provider_category') or row.get('category');row['category']='clarity';row['rationale']='Proposed explicit correction to the model draft; technical editor decision still required.';row['confidence']='low'
OUT=JOB/'revision_2';OUT.mkdir(exist_ok=True)
(OUT/'EDITORIAL_CORRECTION_PROPOSAL.json').write_text(json.dumps(proposal,indent=2)+'\n')
rows=[{'paragraph_id':p['paragraph_id'],'text':edits.get(p['paragraph_id'],{}).get('revised',p['text'])} for p in paras]
create_clean_docx(OUT/'REVISION_2_CANDIDATE.docx','Community Water Quality Monitoring Procedure','Revision 2 proposed candidate. Technical-editor and client approval required.',rows,'text')
create_redline_docx(OUT/'REVISION_2_REDLINE.docx','Community Water Quality Monitoring Procedure',paras,edits)
# Render the two corrected editable candidates to print-review PDFs.
subprocess.run(['libreoffice','-env:UserInstallation=file:///tmp/lo-document-studio-r2','--headless','--convert-to','pdf','--outdir',str(OUT),str(OUT/'REVISION_2_CANDIDATE.docx'),str(OUT/'REVISION_2_REDLINE.docx')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
text='\n'.join(p.text for p in Document(OUT/'REVISION_2_CANDIDATE.docx').paragraphs)
protected=['pH','NTU','QMS-07','2 minutes','2 and 8 degrees Celsius','6.5','9.5','1 NTU']
nums=set(__import__('re').findall(r'\b\d+(?:\.\d+)?\b',source_text)); outnums=set(__import__('re').findall(r'\b\d+(?:\.\d+)?\b',text))
checks={f'preserved_{i+1}_{token}':token in text for i,token in enumerate(protected)}
checks.update({'all_source_numbers_preserved':nums<=outnums,'sterile_bottle_negation_explicit':'do not rinse a sterile microbiological bottle' in text.casefold(),'community_authority_gate_preserved':'do not tell the community that the water is safe or unsafe until the authorised official has reviewed' in text.casefold(),'revision2_editable_file_exists':(OUT/'REVISION_2_CANDIDATE.docx').is_file(),'revision2_tracked_redline_exists':(OUT/'REVISION_2_REDLINE.docx').is_file()})
score={'schema':'dio.document_studio.semantic_review_scorecard.v1','checks':checks,'passed_count':sum(checks.values()),'check_count':len(checks),'model_draft_semantic_issue_count':1,'model_issue':'P5 weakened/ambiguous sterile-bottle negation; explicit correction proposed in Revision 2.','automated_integrity':'PASS' if all(checks.values()) else 'FAIL','professional_quality':'UNVERIFIED','technical_editor_review':'PENDING','client_approval':'PENDING','release_authorized':False,'case':'synthetic controlled technical procedure; no customer acceptance implied'}
(OUT/'REVISION_2_SCORECARD.json').write_text(json.dumps(score,indent=2)+'\n')
with (OUT/'TECHNICAL_EDITOR_DECISIONS.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=['paragraph_id','source_text','revision_2_text','decision_accept_reject_amend','reviewer_name','qualification','review_date','reason']);w.writeheader()
 for p in paras:w.writerow({'paragraph_id':p['paragraph_id'],'source_text':p['text'],'revision_2_text':edits.get(p['paragraph_id'],{}).get('revised',p['text']),'decision_accept_reject_amend':'PENDING'})
# Package current source, provider draft, revision pair, ledgers, receipts and decision gate.
model_score=json.loads((JOB/'CURRENT_REVIEW_SCORECARD.json').read_text())
(JOB/'README.md').write_text(f'''# Document Studio · current technical edit review candidate

Generated on 2026-11-04 with local inference. The package contains the source, original model draft, clean editable copy, tracked redline, revision 2 correction proposal, revision 2 clean/redline DOCX and PDF, change ledger, source-bound receipt, protected-token checks, and a blank technical-editor decision sheet.

## Quality and approval state

- The first model draft scored {model_score['passed_check_count']}/{model_score['check_count']} semantic/integrity checks; it weakened the sterile-bottle instruction in paragraph P5. This defect is preserved in the package as a finding.
- Revision 2 explicitly restores the negation and preserves all numeric thresholds and identifiers; its structural/token scorecard is {score['passed_count']}/{score['check_count']}.
- Both review revisions are proposed, not technically approved. A qualified technical editor must accept/reject/amend each paragraph; client approval and release authorization remain pending.
- This is a synthetic controlled manuscript, not a real customer case or professional certification.
''')
archive=JOB/'DOCUMENT_STUDIO_CURRENT_REVIEW_CANDIDATE.zip'
include=[JOB/'README.md',JOB/'PROVIDER_OUTPUT.json',JOB/'CHANGE_LEDGER.csv',JOB/'DOCUMENT_STUDIO_RECEIPT.json',JOB/'DOCUMENT_STUDIO_QA.json',JOB/'TECHNICAL_EDIT_REVIEW_TEMPLATE.csv',JOB/'TECHNICAL_EDIT_REVIEW_VALIDATION.json',SRC,ROOT/'samples/document_studio/current_truth_review_20261104/request.json']
include += sorted(OUT.glob('*'))
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for f in include:
  if f.is_file(): z.write(f,f.name if f.parent==OUT else f'{f.parent.name}/{f.name}')
print(json.dumps({'archive':str(archive),'revision_checks':score['passed_count'],'checks':score['check_count'],'technical_review':'PENDING','release_authorized':False},indent=2))
