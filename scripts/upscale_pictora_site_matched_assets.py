#!/usr/bin/env python3
"""Locally upscale the site-matched Pictora organ artwork with installed RealESRGAN."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from products.pictora_organ import collect,discover,submit,upload_image

PACK=ROOT/'media/product_asset_packs/dio_creative_organs_site_matched_v1'
ASSETS=PACK/'assets'; JOBS=PACK/'upscale_jobs'; WF=PACK/'workflows'
MODEL='RealESRGAN_x4plus.safetensors'
SOURCES=[('sonoris','SONORIS_ORBITAL_MUSIC_ENGINE.png'),('pictora','PICTORA_ORBITAL_IMAGE_FORGE.png')]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 snapshot=discover()
 nodes=set(snapshot.get('available_nodes',[]))
 need={'LoadImage','UpscaleModelLoader','ImageUpscaleWithModel','ImageScale','SaveImage'}
 if not need<=nodes: raise SystemExit('Pictora lacks local upscale nodes: '+', '.join(sorted(need-nodes)))
 import urllib.request
 installed=json.loads(urllib.request.urlopen(snapshot['endpoint']+'/models/upscale_models',timeout=20).read())
 if MODEL not in installed:raise SystemExit(f'Pictora upscaler unavailable: {MODEL}')
 jobs=JOBS; jobs.mkdir(parents=True,exist_ok=True)
 results=[]
 for organ,filename in SOURCES:
  src=ASSETS/filename; out=ASSETS/(src.stem+'_UPSCALED_1280x720.png')
  name=f'{organ}_upscale'; job=jobs/name; wf=WF/f'{name}_api.json'
  if not src.is_file():raise SystemExit(f'missing Pictora source candidate: {src}')
  if out.exists() or job.exists() or wf.exists():raise SystemExit(f'refusing to overwrite prior upscaler output: {name}')
  source=upload_image(src,subfolder='dio-pictora-generated-inputs')
  item=source['input']; img=(item.get('subfolder','')+'/' if item.get('subfolder') else '')+item['name']
  graph={
   '1':{'class_type':'LoadImage','inputs':{'image':img}},
   '2':{'class_type':'UpscaleModelLoader','inputs':{'model_name':MODEL}},
   '3':{'class_type':'ImageUpscaleWithModel','inputs':{'upscale_model':['2',0],'image':['1',0]}},
   '4':{'class_type':'ImageScale','inputs':{'image':['3',0],'upscale_method':'lanczos','width':1280,'height':720,'crop':'disabled'}},
   '5':{'class_type':'SaveImage','inputs':{'images':['4',0],'filename_prefix':f'DIO_{organ.upper()}_ORGAN_UPSCALED'}}
  }
  wf.write_text(json.dumps(graph,indent=2)+'\n')
  receipt=submit(graph,output_dir=job,owner_authorized=True,source_receipts=[{'source_asset':str(src.relative_to(ROOT)),'source_sha256':sha(src),'uploaded_copy_sha256':source['source_sha256'],'upscale_model':MODEL,'upscale_model_local':True}])
  result=collect(receipt['job_id'],output_dir=job,timeout_seconds=1800,poll_interval=2)
  if result.get('state')!='COMPLETE':raise SystemExit(f'Pictora upscale {organ} failed: {result.get("state")}')
  pngs=[job/r['path'] for r in result.get('artifacts',[]) if Path(r['path']).suffix.lower()=='.png']
  if not pngs:raise SystemExit(f'Pictora upscale returned no image for {organ}')
  out.write_bytes(pngs[0].read_bytes())
  results.append({'organ':organ,'source':str(src.relative_to(ROOT)),'source_sha256':sha(src),'path':str(out.relative_to(ROOT)),'sha256':sha(out),'bytes':out.stat().st_size,'dimensions':[1280,720],'workflow':str(wf.relative_to(ROOT)),'job_receipt':str((job/'PICTORA_JOB_RECEIPT.json').relative_to(ROOT))})
 payload={'schema':'dio.pictora.site_matched_upscale_pack.v1','model':MODEL,'local_processing':True,'human_review':'PENDING','release_authorized':False,'assets':results}
 (PACK/'PICTORA_SITE_MATCHED_UPSCALE_RECEIPT.json').write_text(json.dumps(payload,indent=2)+'\n')
 print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
