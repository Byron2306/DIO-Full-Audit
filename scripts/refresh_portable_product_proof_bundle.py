#!/usr/bin/env python3
"""Refresh HOMS Grade 12 proof and independent verdicts in the portable archive."""
from __future__ import annotations
import csv,hashlib,json,shutil,tempfile,zipfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_product_readiness_verdicts import verdict
ARCHIVE=ROOT/'deliverables/product_proof_portfolio_20261104.zip'
HOMS=ROOT/'deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip'
VERDICTS=ROOT/'deliverables/product_readiness_verdicts_20261104'
PREFIX='product_proof_portfolio_20261104/'
NEW_REL='proofs/homs_exam/payload/deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip'

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
index['selection_policy']=index['selection_policy'].replace('HOMS Exam selects the saved Grades 1-12 candidate ZIP.','HOMS Exam selects Grades 1-11 candidates plus the complete two-paper Grade 12 candidate ZIP.')
files[index_path]=json.dumps(index,indent=2,ensure_ascii=False).encode()+b'\n'
html_path=PREFIX+'index.html'
if html_path in files:
    page=files[html_path].decode('utf-8')
    page=page.replace('deliverables/homs_best_randomized_exam_candidates_20261104_v2/HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12.zip','deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip')
    page=page.replace('</div><div class="toolbar"><input id="search"', '</div><p class="notice"><a href="PRODUCT_READINESS_VERDICTS.csv">Open the independent five-dimension readiness verdicts (CSV)</a> · <a href="PRODUCT_READINESS_VERDICTS.json">JSON</a>. Execution, output quality, evidence validity, customer acceptance and release are separate verdicts.</p><div class="toolbar"><input id="search"')
    files[html_path]=page.encode()
csv_path=PREFIX+'PRODUCT_PROOF_INDEX.csv'
rows=list(csv.DictReader(files[csv_path].decode('utf-8-sig').splitlines()))
for r in rows:
 if r.get('product_id')=='homs_exam':
  r.update({'artifact_source_class':row['artifact_source_class'],'primary_artifact':row['primary_artifact'],'source_artifact':row['source_artifact'],'artifact_sha256':digest,'artifact_bytes':str(len(homs_bytes)),'quality_limits':' | '.join(row['quality_limits'])})
import io
out=io.StringIO(newline=''); w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
files[csv_path]=('\ufeff'+out.getvalue()).encode('utf-8')
files[PREFIX+NEW_REL]=homs_bytes
readme_path=PREFIX+'README.md'
readme=files[readme_path].decode('utf-8')
readme=readme.replace('- HOMS Exam links to the saved randomized Grades 1–12 exam and memo candidate bundle. Those exams remain drafts requiring educator moderation; Grade 12 is a 50-mark focused assessment, not a full Grade 12 CAPS examination.','HOMS Exam links to the Grades 1–11 candidate bundle and the complete two-paper Grade 12 Business Studies candidate. Each Grade 12 paper is 150 marks / 120 minutes with a separate draft marking guideline. The educator validity matrix remains blank/PENDING; all candidates need educator moderation and release authorization.')
readme=readme.replace('HOMS Exam uses the saved Grades 1–12 candidate ZIP.','HOMS Exam uses Grades 1–11 candidates plus the full Grade 12 two-paper candidate.')
readme += '\nIndependent readiness verdicts are in `PRODUCT_READINESS_VERDICTS.csv` and `.json`. Execution, output quality, evidence validity, customer acceptance and release are separate dimensions; source traceability is not semantic correctness.\n'
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
buf=io.StringIO(newline=''); w=csv.DictWriter(buf,fieldnames=columns);w.writeheader()
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
