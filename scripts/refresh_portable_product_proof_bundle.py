#!/usr/bin/env python3
"""Refresh HOMS Grade 12 proof and independent verdicts in the portable archive."""
from __future__ import annotations
import csv,hashlib,json,shutil,tempfile,zipfile,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_product_readiness_verdicts import verdict
ARCHIVE=ROOT/'deliverables/product_proof_portfolio_20261104.zip'
HOMS=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_20261101.zip'
HOMS_PACKAGE_MANIFEST=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/PACKAGE_MANIFEST.json'
HOMS_CONTENT_AUDIT=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/HOMS_RANDOM_GRADE_EXAM_SET_CONTENT_AUDIT_20261104.json'
HOMS_SUBJECT_AUDIT=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json'
HOMS_VISUAL_DIR=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/visual_review'
HOMS_PRODUCT_EVIDENCE=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/HOMS_PRODUCT_BATCH_EVIDENCE.json'
HOMS_WORKFLOW=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/homs_randomized_candidate_workflow.svg'
HOMS_WORKFLOW_RECEIPT=ROOT/'deliverables/homs_randomized_exam_candidates_20261104/media/homs_randomized_candidate_workflow.receipt.json'
HOMS_ADVERSARIAL_DIR=ROOT/'deliverables/homs_randomized_exam_candidates_20261104'
VERDICTS=ROOT/'deliverables/product_readiness_verdicts_20261104'
PREFIX='product_proof_portfolio_20261104/'
NEW_REL='proofs/homs_exam/payload/deliverables/homs_randomized_exam_candidates_20261104/HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_20261101.zip'
HOMS_PRIMARY_REL='payload/deliverables/homs_randomized_exam_candidates_20261104/HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_20261101.zip'
EVIDEX_DIR=ROOT/'deliverables/evidex_claim_truth_benchmark_20261104_v2'
DOCSTUDIO_ZIP=ROOT/'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3/DOCUMENT_STUDIO_CURRENT_REVIEW_CANDIDATE.zip'
DOCSTUDIO_RECEIPT=ROOT/'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3/DOCUMENT_STUDIO_RECEIPT.json'
FUNDING_RUN=ROOT/'acceptance_runs/68-product-sellability-20261027/funding-finder/reviewed/official-refresh-20261104-v3'
FUNDING_RECEIPT=ROOT/'deliverables/fundingfinder_live_refresh_20261104/FUNDINGFINDER_LIVE_REFRESH_RECEIPT_20261104_V3.json'

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

with zipfile.ZipFile(ARCHIVE) as src:
    files={n:src.read(n) for n in src.namelist() if not n.endswith('/') and not n.endswith('/PACKAGE_SHA256SUMS.txt')}
for name in list(files):
    if (re.search(r'homs_best_randomized_exam_candidates_20261104_v[2345]/HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12\.zip', name)
            or 'homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip' in name):
        del files[name]
index_path=PREFIX+'PRODUCT_PROOF_INDEX.json'; index=json.loads(files[index_path])
row=next(r for r in index['products'] if r['product_id']=='homs_exam')
homs_bytes=HOMS.read_bytes(); digest=sha(homs_bytes)
row.update({'primary_artifact':HOMS_PRIMARY_REL,'source_artifact':'deliverables/homs_randomized_exam_candidates_20261104/HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_20261101.zip','artifact_source_class':'one_randomized_caps_mapped_draft_exam_and_memo_per_grade_1_to_12_seed_20261101','artifact_sha256':digest,'artifact_bytes':len(homs_bytes)})
row['payload_files']=[{'path':HOMS_PRIMARY_REL,'source_path':row['source_artifact'],'bytes':len(homs_bytes),'sha256':digest,'media_type':'application/zip'}]
proof_assets=[]
for label,path,archive_rel in [
    ('package_manifest',HOMS_PACKAGE_MANIFEST,'package/PACKAGE_MANIFEST.json'),
    ('content_audit',HOMS_CONTENT_AUDIT,'content_audit/HOMS_RANDOM_GRADE_EXAM_SET_CONTENT_AUDIT_20261104.json'),
    ('subject_draw_audit',HOMS_SUBJECT_AUDIT,'subject_draw/RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json'),
    ('product_batch_evidence',HOMS_PRODUCT_EVIDENCE,'product_evidence/HOMS_PRODUCT_BATCH_EVIDENCE.json'),
    ('workflow_diagram',HOMS_WORKFLOW,'media/homs_randomized_candidate_workflow.svg'),
    ('workflow_diagram_receipt',HOMS_WORKFLOW_RECEIPT,'media/homs_randomized_candidate_workflow.receipt.json'),
]:
    data=path.read_bytes(); archive_path='proofs/homs_exam/'+archive_rel
    files[PREFIX+archive_path]=data
    proof_assets.append({'kind':label,'path':archive_rel,'source_path':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
for path in sorted(HOMS_VISUAL_DIR.glob('*')):
    if path.is_file():
        archive_rel='visual_review/'+path.name; archive_path='proofs/homs_exam/'+archive_rel
        data=path.read_bytes();files[PREFIX+archive_path]=data
        proof_assets.append({'kind':'visual_review','path':archive_rel,'source_path':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
for name,archive_rel in [
    ('ADVERSARIAL_CASES.json','adversarial_qa/ADVERSARIAL_CASES.json'),
    ('EDUCATOR_SCORING_RUBRIC.md','adversarial_qa/EDUCATOR_SCORING_RUBRIC.md'),
    ('EDUCATOR_RESPONSE.csv','adversarial_qa/EDUCATOR_RESPONSE.csv'),
]:
    path=HOMS_ADVERSARIAL_DIR/name; data=path.read_bytes(); archive_path='proofs/homs_exam/'+archive_rel
    files[PREFIX+archive_path]=data
    proof_assets.append({'kind':'unscored_adversarial_fixture','path':archive_rel,'source_path':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
row['proof_assets']=proof_assets
row['item_validity_benchmark']={'case_count':11,'source_class':'synthetic_defect_injection','state':'REFERENCE_PREPARED_NOT_SCORED_AGAINST_CANONICAL_CANDIDATE','educator_scoring':'PENDING'}
batch_evidence_bytes=HOMS_PRODUCT_EVIDENCE.read_bytes(); batch_evidence_hash=sha(batch_evidence_bytes)
batch_evidence_path='proofs/homs_exam/product_evidence/HOMS_PRODUCT_BATCH_EVIDENCE.json'
files[PREFIX+batch_evidence_path]=batch_evidence_bytes
row['product_evidence']={'path':'product_evidence/HOMS_PRODUCT_BATCH_EVIDENCE.json','source_path':HOMS_PRODUCT_EVIDENCE.relative_to(ROOT).as_posix(),'kind':'batch_evidence','bytes':len(batch_evidence_bytes),'sha256':batch_evidence_hash}
row['quality_limits']=[
 'The canonical bundle contains one reproducibly assigned, CAPS-source-mapped draft exam and matching memo for each grade, 1–12, using seed 20261101; it includes editable DOCX and 24 print PDFs.',
 'The current mechanical content audit passes all 12 grade packs; independent subject-educator review and moderation remain pending. No classroom release, customer acceptance, or DBE endorsement is claimed.',
 'The current visual audit verifies 24 PDF hashes and visually reviews 33 rendered pages. Source mapping and hash binding do not prove full-year CAPS coverage, item correctness, classroom suitability, or academic validity.'
 ,'An 11-case synthetic defect-injection benchmark and educator rubric are packaged for a future scoring pass; they have not been scored against the canonical 60 questions, so no detector or candidate benchmark performance is claimed.'
]
evidex=next(r for r in index['products'] if r['product_id']=='evidex_evidenceops')
truth_prefix=PREFIX+'proofs/evidex_evidenceops/truth_benchmark/'
truth_files=[]
for path in sorted(EVIDEX_DIR.rglob('*')):
    if path.is_file():
        relative=path.relative_to(EVIDEX_DIR).as_posix(); archive_path=truth_prefix+relative
        data=path.read_bytes(); files[archive_path]=data
        truth_files.append({'path':'truth_benchmark/'+relative,'source_path':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
evidex['truth_benchmark']={'case_id':'SYNTHETIC-EVIDEX-1','state':'STRUCTURED_REFERENCE_MATCH_9_OF_9; INDEPENDENT_EXPERT_REVIEW_PENDING','files':truth_files,'customer_acceptance':'NOT_ESTABLISHED','release_authorized':False}
evidex.setdefault('quality_limits',[]).append('A synthetic 14-claim / 12-attendance reconciliation is checked against an explicit reference answer and adversarial rubric. The structured comparison is not an independent expert opinion or real-customer validation.')
funding=next(r for r in index['products'] if r['product_id']=='fundingfinder')
funding_files=[]
for path in sorted(FUNDING_RUN.rglob('*')):
    if path.is_file():
        relative=path.relative_to(FUNDING_RUN).as_posix(); archive_path=PREFIX+'proofs/fundingfinder/live_refresh_20261104_v3/'+relative
        data=path.read_bytes();files[archive_path]=data
        funding_files.append({'path':'live_refresh_20261104_v3/'+relative,'source_path':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
funding_receipt_bytes=FUNDING_RECEIPT.read_bytes();funding_receipt_hash=sha(funding_receipt_bytes)
funding_receipt_path='proofs/fundingfinder/product_evidence_receipt/FUNDINGFINDER_LIVE_REFRESH_RECEIPT_20261104_V3.json'
files[PREFIX+funding_receipt_path]=funding_receipt_bytes
funding['live_source_refresh']={'as_of':'2026-11-04','state':'THREE_OFFICIAL_SOURCE_CASES_CAPTURED; SYNTHETIC_APPLICANTS; NO_QUALIFICATION','files':funding_files,
    'receipt':{'path':'product_evidence_receipt/FUNDINGFINDER_LIVE_REFRESH_RECEIPT_20261104_V3.json','source_path':FUNDING_RECEIPT.relative_to(ROOT).as_posix(),'sha256':funding_receipt_hash,'bytes':len(funding_receipt_bytes)},
    'customer_acceptance':'NOT_ESTABLISHED','release_authorized':False}
funding.setdefault('quality_limits',[]).append('A 2026-11-04 refresh captures three official-source cases (NYDA, TIA and England-only Lottery) and five source responses. Applicant profiles are synthetic. Timing remains unknown for NYDA/TIA, and every result includes applicant evidence preparation or verification actions; this does not prove customer eligibility, live availability or an award.')
files[index_path]=json.dumps(index,indent=2,ensure_ascii=False).encode()+b'\n'
document=next(r for r in index['products'] if r['product_id']=='document_studio_edit')
doc_rel='proofs/document_studio_edit/payload/deliverables/document_studio_current_20261104/DOCUMENT_STUDIO_CURRENT_REVIEW_CANDIDATE.zip'
doc_product_path='payload/deliverables/document_studio_current_20261104/DOCUMENT_STUDIO_CURRENT_REVIEW_CANDIDATE.zip'
doc_bytes=DOCSTUDIO_ZIP.read_bytes();doc_hash=sha(doc_bytes);files[PREFIX+doc_rel]=doc_bytes
receipt_bytes=DOCSTUDIO_RECEIPT.read_bytes();receipt_hash=sha(receipt_bytes)
receipt_path='proofs/document_studio_edit/product_evidence_receipt/DOCUMENT_STUDIO_RECEIPT.json'
files[PREFIX+receipt_path]=receipt_bytes
document.update({'primary_artifact':doc_product_path,'source_artifact':'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3/DOCUMENT_STUDIO_CURRENT_REVIEW_CANDIDATE.zip','artifact_source_class':'current_in_window_before_after_transformation_candidate','artifact_sha256':doc_hash,'artifact_bytes':len(doc_bytes),'payload_files':[{'path':doc_product_path,'source_path':document['source_artifact'],'bytes':len(doc_bytes),'sha256':doc_hash,'media_type':'application/zip'}],'product_evidence':{'path':'product_evidence_receipt/DOCUMENT_STUDIO_RECEIPT.json','source_path':'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3/DOCUMENT_STUDIO_RECEIPT.json','kind':'receipt','bytes':len(receipt_bytes),'sha256':receipt_hash},'quality_limits':['Current synthetic technical-edit pair includes source, editable clean copy, tracked redline, change ledger, protected numeric/token checks and blank technical-editor decisions.','One model-generated sterile-bottle instruction was found ambiguous during semantic review and corrected in an unapproved review revision; a qualified technical editor must still accept or amend it.','Professional quality, customer acceptance and release authorization remain unverified / held.']})
files[index_path]=json.dumps(index,indent=2,ensure_ascii=False).encode()+b'\n'
index['selection_policy']=index['selection_policy'].replace('HOMS Exam selects Grades 1-11 candidates plus the complete two-paper Grade 12 candidate ZIP.','HOMS Exam selects the current randomized CAPS-linked set with one draft exam and matching memo for every grade, 1–12, seed 20261101.')
index['selection_policy']=index['selection_policy'].replace('HOMS Exam selects the saved Grades 1-12 candidate ZIP.','HOMS Exam selects the current randomized CAPS-linked set with one draft exam and matching memo for every grade, 1–12, seed 20261101.')
files[index_path]=json.dumps(index,indent=2,ensure_ascii=False).encode()+b'\n'
html_path=PREFIX+'index.html'
if html_path in files:
    page=files[html_path].decode('utf-8')
    homs_marker='data-name="HOMS Exam"'
    homs_pos=page.find(homs_marker)
    if homs_pos>=0:
        homs_start=page.rfind('<article',0,homs_pos); homs_end=page.find('</article>',homs_pos)+len('</article>')
        homs_card=(
            '<article class="card" data-suite="Education &amp; Research" data-name="HOMS Exam">'
            '<div class="eyebrow">Education &amp; Research</div><h2>HOMS Exam</h2>'
            '<div class="badge">Held execution · educator review pending</div>'
            '<p class="limit">One randomized CAPS-source-mapped draft exam and matching memo for each grade, 1–12. Mechanical checks pass; source mapping and mark reconciliation do not establish academic validity or full-year coverage. Educator moderation and classroom release remain pending.</p>'
            '<div class="links"><a href="proofs/homs_exam/'+row['primary_artifact']+'">Open Grades 1–12 set</a>'
            '<a class="secondary" href="proofs/homs_exam/product_evidence/HOMS_PRODUCT_BATCH_EVIDENCE.json">Product batch evidence</a>'
            '<a class="secondary" href="proofs/homs_exam/content_audit/HOMS_RANDOM_GRADE_EXAM_SET_CONTENT_AUDIT_20261104.json">12-grade content audit</a>'
            '<a class="secondary" href="proofs/homs_exam/subject_draw/RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json">Subject-draw audit</a>'
            '<a class="secondary" href="proofs/homs_exam/visual_review/HOMS_RANDOM_GRADE_EXAM_VISUAL_RENDER_AUDIT_20261104_V15.json">Current visual audit</a>'
            '<a class="secondary" href="proofs/homs_exam/adversarial_qa/ADVERSARIAL_CASES.json">Unscored adversarial QA cases</a>'
            '<a class="secondary" href="proofs/homs_exam/media/homs_randomized_candidate_workflow.svg">Workflow diagram</a></div></article>'
        )
        page=page[:homs_start]+homs_card+page[homs_end:]
    funding_marker='<a class="secondary" href="proofs/fundingfinder/product_evidence_receipt/CUSTOMER_EXECUTION_RECEIPT.json">Product evidence</a>'
    page=page.replace(funding_marker, funding_marker+'<a class="secondary" href="proofs/fundingfinder/product_evidence_receipt/FUNDINGFINDER_LIVE_REFRESH_RECEIPT_20261104_V3.json">Nov 4 official-source refresh</a>', 1)
    marker='data-name="Document Studio Edit"'
    pos=page.find(marker)
    if pos>=0:
        start=page.rfind('<article',0,pos); end=page.find('</article>',pos)+len('</article>')
        card=(
            '<article class="card" data-suite="Demand &amp; Presence" data-name="Document Studio Edit">'
            '<div class="eyebrow">Demand &amp; Presence</div><h2>Document Studio Edit</h2>'
            '<div class="badge">Held execution · current review candidate</div>'
            '<p class="limit">Fresh synthetic before/after technical edit with clean copy, tracked redline, source-bound ledger and proposed correction of an ambiguous negation. Technical editor review is pending.</p>'
            '<div class="links"><a href="proofs/document_studio_edit/'+document['primary_artifact']+'">Open current review candidate</a>'
            '<a class="secondary" href="proofs/document_studio_edit/'+document['product_evidence']['path']+'">Current product receipt</a></div></article>'
        )
        page=page[:start]+card+page[end:]
    if 'Open current Document Studio review candidate' not in page:
        page=page.replace('<a href="PRODUCT_READINESS_VERDICTS.csv">', '<a href="proofs/document_studio_edit/'+document['primary_artifact']+'">Open current Document Studio review candidate</a> · <a href="PRODUCT_READINESS_VERDICTS.csv">')
    page=re.sub(r'<a href="[^"]+">Open current Document Studio review candidate</a>', '<a href="proofs/document_studio_edit/'+document['primary_artifact']+'">Open current Document Studio review candidate</a>', page, count=1)
    files[html_path]=page.encode()
csv_path=PREFIX+'PRODUCT_PROOF_INDEX.csv'
rows=list(csv.DictReader(files[csv_path].decode('utf-8-sig').splitlines()))
for r in rows:
 if r.get('product_id')=='homs_exam':
  r.update({'artifact_source_class':row['artifact_source_class'],'primary_artifact':row['primary_artifact'],'source_artifact':row['source_artifact'],'artifact_sha256':digest,'artifact_bytes':str(len(homs_bytes)),'product_evidence_path':row['product_evidence']['path'],'product_evidence_sha256':batch_evidence_hash,'quality_limits':' | '.join(row['quality_limits'])})
 elif r.get('product_id')=='document_studio_edit':
  r.update({'artifact_source_class':document['artifact_source_class'],'primary_artifact':document['primary_artifact'],'source_artifact':document['source_artifact'],'artifact_sha256':doc_hash,'artifact_bytes':str(len(doc_bytes)),'product_evidence_path':receipt_path,'product_evidence_sha256':receipt_hash,'quality_limits':' | '.join(document['quality_limits'])})
 elif r.get('product_id')=='evidex_evidenceops':
  r['quality_limits']=' | '.join(evidex['quality_limits'])
 elif r.get('product_id')=='fundingfinder':
  r['quality_limits']=' | '.join(funding['quality_limits'])
  r['live_refresh_receipt_path']=funding_receipt_path
  r['live_refresh_receipt_sha256']=funding_receipt_hash
import io
fieldnames=list(rows[0])
for field in ('live_refresh_receipt_path','live_refresh_receipt_sha256'):
 if field not in fieldnames: fieldnames.append(field)
out=io.StringIO(newline=''); w=csv.DictWriter(out,fieldnames=fieldnames,lineterminator='\n');w.writeheader();w.writerows(rows)
files[csv_path]=('\ufeff'+out.getvalue()).encode('utf-8')
index['summary']['product_evidence_records_included']=sum(bool(r.get('product_evidence')) for r in index['products'])
index['summary']['product_receipts_included']=sum(bool(r.get('product_evidence') and r['product_evidence'].get('kind')=='receipt') for r in index['products'])
files[index_path]=json.dumps(index,indent=2,ensure_ascii=False).encode()+b'\n'
files[PREFIX+NEW_REL]=homs_bytes
readme_path=PREFIX+'README.md'
readme=files[readme_path].decode('utf-8')
readme=readme.replace('HOMS Exam links to the saved randomized Grades 1-12 exam and memo candidate bundle. Those exams remain drafts requiring educator moderation; Grade 12 is a 50-mark focused assessment, not a full Grade 12 CAPS examination.','HOMS Exam links to the canonical randomized CAPS-linked candidate set: one draft exam and matching memo for every grade, 1–12, seed 20261101. The current content audit passes all 12 grade packs and the visual audit binds all 24 PDFs across 33 rendered pages. Educator moderation remains pending and classroom release is unauthorized.')
readme=readme.replace('HOMS Exam uses the saved Grades 1–12 candidate ZIP.','HOMS Exam uses the canonical one-exam-and-memo-per-grade set, Grades 1–12, seed 20261101.')
readme=readme.replace('Document Studio Edit had no in-window deliverable reference, so its card is explicitly labeled as a historical-baseline fallback and has no current product-specific receipt in this package.','The original qualification snapshot still lacks a current Document Studio Edit reference; this package therefore adds a separate 2026-11-04 before/after technical-edit candidate with its current source-bound receipt. The technical-editor review remains pending.')
readme += '\nIndependent readiness verdicts are in `PRODUCT_READINESS_VERDICTS.csv` and `.json`. Execution, output quality, evidence validity, customer acceptance and release are separate dimensions; source traceability is not semantic correctness.\n\nDocument Studio Edit includes a fresh synthetic before/after technical edit with a clean copy, tracked redline, source-bound change ledger and unapproved correction to a model-generated ambiguous negation. The corrected candidate passes its structural/token checks, but the technical editor must complete the blank decision sheet; no client approval or release is recorded.\n'
readme += '\nFundingFinder includes a fresh 2026-11-04 source refresh with three official-source scenarios, five retrieved official source responses, source-bound eligibility matrices and opportunity-specific preparation actions. All applicant data is synthetic; NYDA/TIA timing remains unknown and results are not eligibility or award decisions.\n'
files[readme_path]=readme.encode()

# Recompute independent verdicts from all 68 product records.
products=index['products']; vrows=[verdict(r) for r in products]
counts={k:{} for k in ('execution','output_quality','evidence_validity','customer_acceptance','release','professional_readiness')}
for r in vrows:
 for k in counts:
  val=r[k] if k=='professional_readiness' else r[k]['verdict']; counts[k][val]=counts[k].get(val,0)+1
report={'schema':'dio.product_readiness_verdicts.v1','generated_at':index.get('source_snapshot_generated_at'),'qualification_snapshot_sha256':index.get('qualification_snapshot_sha256'),'method':'Execution, output quality, evidence validity, customer acceptance and release are independent verdicts. A route PASS never promotes another dimension. TRACEABLE_UNVALIDATED means byte lineage exists, not that the interpretation is correct.','summary':counts,'products':vrows}
json_bytes=(json.dumps(report,indent=2,ensure_ascii=False)+'\n').encode(); files[PREFIX+'PRODUCT_READINESS_VERDICTS.json']=json_bytes
columns=['product_id','name','execution','output_quality','evidence_validity','customer_acceptance','release','professional_readiness','source_artifact','artifact_sha256']
buf=io.StringIO(newline=''); w=csv.DictWriter(buf,fieldnames=columns,lineterminator='\n');w.writeheader()
for r in vrows:w.writerow({**{k:r[k] for k in ('product_id','name','professional_readiness','source_artifact','artifact_sha256')},**{k:r[k]['verdict'] for k in ('execution','output_quality','evidence_validity','customer_acceptance','release')}})
files[PREFIX+'PRODUCT_READINESS_VERDICTS.csv']=('\ufeff'+buf.getvalue()).encode()
files[PREFIX+'PRODUCT_READINESS_VERDICTS_README.md']=b'# Independent product readiness verdicts\n\nExecution, output quality, evidence validity, customer acceptance, and release are separate verdicts. A successful pipeline does not imply readiness. `TRACEABLE_UNVALIDATED` means byte lineage exists; semantic correctness is not independently validated. `UNVERIFIED` and `HELD` are not passes.\n'

sum_name=PREFIX+'PACKAGE_SHA256SUMS.txt'
sum_bytes=''.join(f'{sha(data)}  {name[len(PREFIX):]}\n' for name,data in sorted(files.items()) if name.startswith(PREFIX)).encode()
tmp=ARCHIVE.with_suffix('.zip.tmp')
with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as dst:
 for name,data in sorted(files.items()):dst.writestr(name,data)
 dst.writestr(sum_name,sum_bytes)
tmp.replace(ARCHIVE)
print(json.dumps({'archive':str(ARCHIVE),'bytes':ARCHIVE.stat().st_size,'homs_sha256':digest,'summary':counts},indent=2))
