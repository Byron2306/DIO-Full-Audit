#!/usr/bin/env python3
"""Inpaint clear organ-specific subjects into site-matched Pictora compositions."""
from __future__ import annotations
import hashlib,json,sys,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from products.pictora_organ import collect,discover,submit,upload_image

PACK=ROOT/'media/product_asset_packs/dio_creative_organs_site_matched_v1'
ASSETS=PACK/'assets';JOBS=PACK/'refinement_jobs';WF=PACK/'workflows'
CHECKPOINT='epicrealism_naturalSinRC1VAE.safetensors'
TASKS=[
 {'id':'sonoris','source':'SONORIS_ORBITAL_MUSIC_ENGINE.png','output':'SONORIS_ORBITAL_MUSIC_ENGINE_DETAIL_V2.png','maskbox':(145,175,490,320),
  'prompt':'Inside the edited central stage, create one unmistakable polished black-and-gold jazz fusion instrument sculpture: a small electric piano keyboard with visible ivory and black keys as the foreground base, one clearly shaped curved brass tenor saxophone and a slender silver flute crossing above it, delicate strings extending outward into a gold sound wave. Keep it a refined miniature placed on the stage, realistic instrument silhouettes, clean and legible; preserve the surrounding concentric orbital architecture, black negative space, champagne-gold highlights. No people, no faces, no hands, no lettering, no extra instruments.'},
 {'id':'pictora','source':'PICTORA_ORBITAL_IMAGE_FORGE.png','output':'PICTORA_ORBITAL_IMAGE_FORGE_CANVAS_V2.png','maskbox':(205,80,435,276),
  'prompt':'Inside the edited central opening, create one unmistakable floating landscape image canvas, a clean horizontal rectangular artwork with a narrow fine gold edge: vivid midnight-blue mountain ridges, an emerald leaf in the foreground, and one small amber sun, beautifully rendered as a coherent miniature scene. The image is visibly contained inside the canvas; keep the surrounding concentric black-and-gold orbital machine and dark negative space unchanged. No people, no faces, no hands, no lettering, no frame collage.'}
]

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def graph(task,image_name,mask_name):
 return {
  '1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':CHECKPOINT}},
  '2':{'class_type':'LoadImage','inputs':{'image':image_name}},
  '3':{'class_type':'ImageScale','inputs':{'image':['2',0],'upscale_method':'lanczos','width':640,'height':360,'crop':'disabled'}},
  '4':{'class_type':'LoadImageMask','inputs':{'image':mask_name,'channel':'red'}},
  '5':{'class_type':'VAEEncodeForInpaint','inputs':{'pixels':['3',0],'vae':['1',2],'mask':['4',0],'grow_mask_by':8}},
  '6':{'class_type':'CLIPTextEncode','inputs':{'text':task['prompt'],'clip':['1',1]}},
  '7':{'class_type':'CLIPTextEncode','inputs':{'text':'human, person, portrait, face, hands, text, letters, logo, watermark, blur, clutter, unrelated object','clip':['1',1]}},
  '8':{'class_type':'KSampler','inputs':{'model':['1',0],'seed':2026102841 if task['id']=='sonoris' else 2026102842,'steps':25,'cfg':6.6,'sampler_name':'dpmpp_2m','scheduler':'karras','positive':['6',0],'negative':['7',0],'latent_image':['5',0],'denoise':0.82}},
  '9':{'class_type':'VAEDecode','inputs':{'samples':['8',0],'vae':['1',2]}},
  '10':{'class_type':'SaveImage','inputs':{'images':['9',0],'filename_prefix':f"DIO_{task['id'].upper()}_DETAIL_V2"}}
 }

def main():
 snap=discover();nodes=set(snap.get('available_nodes',[]));need={'CheckpointLoaderSimple','LoadImage','LoadImageMask','ImageScale','VAEEncodeForInpaint','CLIPTextEncode','KSampler','VAEDecode','SaveImage'}
 if not need<=nodes:raise SystemExit('Pictora missing inpaint nodes: '+', '.join(sorted(need-nodes)))
 JOBS.mkdir(parents=True,exist_ok=True);WF.mkdir(parents=True,exist_ok=True)
 records=[]
 for task in TASKS:
  src=ASSETS/task['source'];out=ASSETS/task['output'];job=JOBS/task['id'];wf=WF/f"{task['id']}_detail_inpaint_api.json";mask_path=JOBS/f"{task['id']}_detail_mask.png"
  if any(p.exists() for p in (out,job,wf,mask_path)):raise SystemExit(f"refusing to overwrite existing refinement: {task['id']}")
  with Image.open(src) as im:
   w,h=im.size;mask=Image.new('RGB',(w,h),(0,0,0));d=ImageDraw.Draw(mask);d.rounded_rectangle(task['maskbox'],radius=14,fill=(255,255,255));mask.save(mask_path)
  image_upload=upload_image(src,subfolder='dio-pictora-generated-inputs')
  mask_upload=upload_image(mask_path,subfolder='dio-pictora-refinement-masks')
  def imgref(row):
   val=row['input'];return (val.get('subfolder','')+'/' if val.get('subfolder') else '')+val['name']
  graph_data=graph(task,imgref(image_upload),imgref(mask_upload));wf.write_text(json.dumps(graph_data,indent=2)+'\n')
  receipt=submit(graph_data,output_dir=job,owner_authorized=True,source_receipts=[
   {'source_asset':str(src.relative_to(ROOT)),'source_sha256':sha(src),'source_upload_sha256':image_upload['source_sha256'],'purpose':'local inpaint input'},
   {'source_asset':str(mask_path.relative_to(ROOT)),'source_sha256':sha(mask_path),'mask_upload_sha256':mask_upload['source_sha256'],'purpose':'inpaint region control'}])
  result=collect(receipt['job_id'],output_dir=job,timeout_seconds=1800,poll_interval=2)
  if result.get('state')!='COMPLETE':raise SystemExit(f"Pictora refinement {task['id']} ended {result.get('state')}")
  images=[job/r['path'] for r in result.get('artifacts',[]) if Path(r['path']).suffix.lower()=='.png']
  if not images:raise SystemExit(f"no Pictora image from refinement: {task['id']}")
  out.write_bytes(images[0].read_bytes())
  records.append({'organ':task['id'],'source':str(src.relative_to(ROOT)),'mask':str(mask_path.relative_to(ROOT)),'mask_sha256':sha(mask_path),'output':str(out.relative_to(ROOT)),'output_sha256':sha(out),'dimensions':list(Image.open(out).size),'workflow':str(wf.relative_to(ROOT)),'job_receipt':str((job/'PICTORA_JOB_RECEIPT.json').relative_to(ROOT))})
 pack={'schema':'dio.pictora.inpaint_refinement_pack.v1','pack_id':'dio-creative-organs-site-matched-refinements-v2','checkpoint':CHECKPOINT,'local_only':True,'human_review':'PENDING','release_authorized':False,'assets':records}
 (PACK/'PICTORA_SITE_MATCHED_REFINEMENT_RECEIPT.json').write_text(json.dumps(pack,indent=2)+'\n')
 print(json.dumps(pack,indent=2))
if __name__=='__main__':main()
