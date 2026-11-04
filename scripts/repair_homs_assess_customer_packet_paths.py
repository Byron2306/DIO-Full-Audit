#!/usr/bin/env python3
"""Copy and repair the synthetic HOMS Assess packet's rooted source paths."""
from __future__ import annotations
import hashlib, json, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'acceptance_runs/68-product-sellability-20261027/homs-assess-bound-source-chain-20261101/homs-assess/homs-assess/CUSTOMER_PACKET'
OUT=ROOT/'acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_SOURCE_PACKET_REPAIRED_20261102/CUSTOMER_PACKET'

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def main()->int:
 if OUT.exists() and any(OUT.iterdir()): raise ValueError(f'output must be empty: {OUT}')
 OUT.parent.mkdir(parents=True,exist_ok=True)
 shutil.copytree(SOURCE,OUT,dirs_exist_ok=True)
 binding_path=OUT/'SOURCES/hymark_input/assessment_binding.json'
 binding=json.loads(binding_path.read_text(encoding='utf-8'))
 remapped=[]
 for artifact in binding.get('source_artifacts') or []:
  path=str(artifact.get('path') or '')
  if path.startswith('CUSTOMER_PACKET/'):
   artifact['path']=path.removeprefix('CUSTOMER_PACKET/')
   remapped.append({'role':artifact.get('role'),'from':path,'to':artifact['path']})
 if len(remapped)!=len(binding.get('source_artifacts') or []):
  raise ValueError('expected every bound HOMS source artifact to carry the same spurious packet-root prefix')
 binding_path.write_text(json.dumps(binding,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
 manifest_path=OUT/'CUSTOMER_PACKET_MANIFEST.json'
 manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 files=[]
 for row in manifest.get('files') or []:
  path=OUT/row['path']
  if not path.is_file(): raise ValueError(f'manifest source missing during repair: {row["path"]}')
  files.append({'path':row['path'],'sha256':sha(path),'bytes':path.stat().st_size})
 manifest['files']=files
 manifest.pop('packet_fingerprint',None)
 basis=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
 manifest['packet_fingerprint']='sha256:'+hashlib.sha256(basis).hexdigest()
 manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
 from products.professional_evidence_projection import load_packet
 loaded=load_packet(OUT)
 if loaded['packet_fingerprint']!=manifest['packet_fingerprint']:
  raise ValueError('repaired packet fingerprint did not load consistently')
 for artifact in binding['source_artifacts']:
  path=OUT/artifact['path']
  declared=next((row for row in manifest['files'] if row['path']==artifact['path']),None)
  if not path.is_file() or not declared or sha(path)!=artifact['sha256'] or sha(path)!=declared['sha256']:
   raise ValueError(f'bound source artifact failed exact repaired-path/hash verification: {artifact["path"]}')
 receipt={'schema':'dio.homs.assess.customer_packet_path_repair.v1','source_packet_manifest_sha256':sha(SOURCE/'CUSTOMER_PACKET_MANIFEST.json'),'source_binding_sha256':sha(SOURCE/'SOURCES/hymark_input/assessment_binding.json'),'repaired_packet_manifest_sha256':sha(manifest_path),'repaired_binding_sha256':sha(binding_path),'repaired_packet_fingerprint':manifest['packet_fingerprint'],'remapped_artifacts':remapped,'all_bound_sources_exist_and_hash_match':True,'examiner_material_included':any('EXAMINER' in part.upper() for part in OUT.parts),'release_authorized':False,'fixture_boundary':'Synthetic customer packet copy; source statements and scoring quality remain unverified.'}
 evidence=OUT.parent/'PACKET_PATH_REPAIR_EVIDENCE.json'
 evidence.write_text(json.dumps(receipt,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps(receipt,indent=2,ensure_ascii=False))
 return 0
if __name__=='__main__':raise SystemExit(main())
