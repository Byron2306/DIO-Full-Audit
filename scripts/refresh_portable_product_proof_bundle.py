#!/usr/bin/env python3
"""Refresh HOMS Grade 12 proof and independent verdicts in the portable archive."""
from __future__ import annotations
import csv,hashlib,json,shutil,tempfile,zipfile,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_product_readiness_verdicts import verdict
ARCHIVE=ROOT/'deliverables/product_proof_portfolio_20261104.zip'
HOMS=ROOT/'deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip'
VERDICTS=ROOT/'deliverables/product_readiness_verdicts_20261104'
PREFIX='product_proof_portfolio_20261104/'
NEW_REL='proofs/homs_exam/payload/deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip'
EVIDEX_DIR=ROOT/'deliverables/evidex_claim_truth_benchmark_20261104'
DOCSTUDIO_ZIP=ROOT/'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3/DOCUMENT_STUDIO_CURRENT_REVIEW_CANDIDATE.zip'
DOCSTUDIO_RECEIPT=ROOT/'deliverables/document_studio_current_20261104/DIO-DOC-EDIT-20261104-V3/DOCUMENT_STUDIO_RECEIPT.json'
FUNDING_RUN=ROOT/'acceptance_runs/68-product-sellability-20261027/funding-finder/reviewed/official-refresh-20261104-v3'
FUNDING_RECEIPT=ROOT/'deliverables/fundingfinder_live_refresh_20261104/FUNDINGFINDER_LIVE_REFRESH_RECEIPT_20261104_V3.json'

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

with zipfile.ZipFile(ARCHIVE) as src:
    files={n:src.read(n) for n in src.namelist() if not n.endswith('/') and not n.endswith('/PACKAGE_SHA256SUMS.txt')}
for name in list(files):
    if 'homs_best_randomized_exam_candidates_20261104_v2/HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12.zip' in name:
        del files[name]
index_path=PREFIX+'PRODUCT_PROOF_INDEX.json'; index=json.loads(files[index_path])
row=next(r for r in index['products'] if r['product_id']=='homs_exam')
homs_bytes=HOMS.read_bytes(); digest=sha(homs_bytes)
row.update({'primary_artifact':'payload/'+NEW_REL,'source_artifact':'deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip','artifact_source_class':'full_grade12_two_paper_candidate_plus_saved_grade_01_11_candidate_bundle','artifact_sha256':digest,'artifact_bytes':len(homs_bytes)})
row['payload_files']=[{'path':'payload/'+NEW_REL,'source_path':row['source_artifact'],'bytes':len(homs_bytes),'sha256':digest,'media_type':'application/zip'}]
row['quality_limits']=[
 'Grades 1–11 remain randomized, CAPS-source-mapped draft candidates. Grade 12 now includes two original 150-mark / 120-minute Business Studies papers, each with a marking guideline and item-level educator validity review matrix.',
 'The Grade 12 item matrix is intentionally blank/PENDING. No independent educator scoring, semantic memo validation, moderation, customer acceptance or release authorization is claimed.',
 'CAPS source mapping and hash binding do not prove full-year curriculum coverage, item correctness, classroom suitability or DBE endorsement.'
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
index['selection_policy']=index['selection_policy'].replace('HOMS Exam selects the saved Grades 1-12 candidate ZIP.','HOMS Exam selects Grades 1-11 candidates plus the complete two-paper Grade 12 candidate ZIP.')
files[index_path]=json.dumps(index,indent=2,ensure_ascii=False).encode()+b'\n'
html_path=PREFIX+'index.html'
if html_path in files:
    page=files[html_path].decode('utf-8')
    page=page.replace('deliverables/homs_best_randomized_exam_candidates_20261104_v2/HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12.zip','deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip')
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
  r.update({'artifact_source_class':row['artifact_source_class'],'primary_artifact':row['primary_artifact'],'source_artifact':row['source_artifact'],'artifact_sha256':digest,'artifact_bytes':str(len(homs_bytes)),'quality_limits':' | '.join(row['quality_limits'])})
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
readme=readme.replace('- HOMS Exam links to the saved randomized Grades 1–12 exam and memo candidate bundle. Those exams remain drafts requiring educator moderation; Grade 12 is a 50-mark focused assessment, not a full Grade 12 CAPS examination.','HOMS Exam links to the Grades 1–11 candidate bundle and the complete two-paper Grade 12 Business Studies candidate. Each Grade 12 paper is 150 marks / 120 minutes with a separate draft marking guideline. The educator validity matrix remains blank/PENDING; all candidates need educator moderation and release authorization.')
readme=readme.replace('HOMS Exam uses the saved Grades 1–12 candidate ZIP.','HOMS Exam uses Grades 1–11 candidates plus the full Grade 12 two-paper candidate.')
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
