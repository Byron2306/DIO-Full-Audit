#!/usr/bin/env python3
"""RealESRGAN upscale the site-matched, inpaint-refined organ image candidates."""
from __future__ import annotations
import hashlib,json,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from products.pictora_organ import collect,discover,submit,upload_image
PACK=ROOT/'media/product_asset_packs/dio_creative_organs_site_matched_v1';ASSETS=PACK/'assets';JOBS=PACK/'refinement_upscale_jobs';WF=PACK/'workflows'
MODEL='RealESRGAN_x4plus.safetensors'
ROWS=[('sonoris','SONORIS_ORBITAL_MUSIC_ENGINE_DETAIL_V2.png','SONORIS_MUSICAL_ORGAN_HERO_1280x720.png'),('pictora','PICTORA_ORBITAL_IMAGE_FORGE_CANVAS_V2.png','PICTORA_IMAGE_FORGE_HERO_1280x720.png')]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 snap=discover(); nodes=set(snap.get('available_nodes',[])); need={'LoadImage','UpscaleModelLoader','ImageUpscaleWithModel','ImageScale','SaveImage'}
 if not need<=nodes:raise SystemExit('missing local upscale nodes')
 if MODEL not in json.loads(urllib.request.urlopen(snap['endpoint']+'/models/upscale_models').read()):raise SystemExit('local RealESRGAN model not found')
 JOBS.mkdir(parents=True,exist_ok=True);WF.mkdir(parents=True,exist_ok=True);results=[]
 for organ,source_name,target_name in ROWS:
  src=ASSETS/source_name;out=ASSETS/target_name;key=organ+'_refined';job=JOBS/key;wf=WF/(key+'_upscale_api.json')
  if any(p.exists() for p in (out,job,wf)):raise SystemExit(f'refusing to overwrite: {key}')
  uploaded=upload_image(src,subfolder='dio-pictora-refined-inputs');it=uploaded['input'];name=(it.get('subfolder','')+'/' if it.get('subfolder') else '')+it['name']
  graph={'1':{'class_type':'LoadImage','inputs':{'image':name}},'2':{'class_type':'UpscaleModelLoader','inputs':{'model_name':MODEL}},'3':{'class_type':'ImageUpscaleWithModel','inputs':{'upscale_model':['2',0],'image':['1',0]}},'4':{'class_type':'ImageScale','inputs':{'image':['3',0],'upscale_method':'lanczos','width':1280,'height':720,'crop':'disabled'}},'5':{'class_type':'SaveImage','inputs':{'images':['4',0],'filename_prefix':f'DIO_{organ.upper()}_REFINED_UPSCALED'}}}
  wf.write_text(json.dumps(graph,indent=2)+'\n');receipt=submit(graph,output_dir=job,owner_authorized=True,source_receipts=[{'source_asset':str(src.relative_to(ROOT)),'source_sha256':sha(src),'uploaded_copy_sha256':uploaded['source_sha256'],'upscale_model':MODEL,'execution_location':'local_comfyui'}])
  done=collect(receipt['job_id'],output_dir=job,timeout_seconds=1800,poll_interval=2)
  if done.get('state')!='COMPLETE':raise SystemExit(f'upscale failed: {organ}')
  imgs=[job/x['path'] for x in done.get('artifacts',[]) if Path(x['path']).suffix.lower()=='.png']
  if not imgs:raise SystemExit(f'upscale returned no output: {organ}')
  out.write_bytes(imgs[0].read_bytes());results.append({'organ':organ,'source':str(src.relative_to(ROOT)),'source_sha256':sha(src),'path':str(out.relative_to(ROOT)),'sha256':sha(out),'bytes':out.stat().st_size,'dimensions':[1280,720],'job_receipt':str((job/'PICTORA_JOB_RECEIPT.json').relative_to(ROOT)),'workflow':str(wf.relative_to(ROOT))})
 report={'schema':'dio.pictora.refined_upscale_receipt.v1','model':MODEL,'local_processing':True,'human_visual_review':'PENDING','release_authorized':False,'assets':results}
 (PACK/'PICTORA_REFINED_UPSCALE_RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
