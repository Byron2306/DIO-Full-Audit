#!/usr/bin/env python3
"""Local ComfyUI generation of held Dicere visual candidates. Never overwrites."""
import argparse, hashlib, io, json, time, urllib.request, urllib.parse
from pathlib import Path
from PIL import Image

ROOT=Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit')
DEST=ROOT/'media/dicere/backgrounds-v3'
SCENES=[
 'an immense circular black and gold broadcast chamber, luminous suspended architectural rings, distant soaring arches',
 'futuristic story design workshop, abstract floating blank pages and flowing narrative pathways, elegant workstations',
 'cinematic music scoring suite, glowing synthesizers, strings, sound wave sculptures, gold acoustic architecture',
 'empty high-end motion capture presentation stage, concentric illuminated arcs and abstract audio waves',
 'luxury production finishing gallery, five streams of golden light converging at one luminous projection aperture',
]
POS='Cinematic photorealistic widescreen environment, monumental black and antique gold architecture, richly layered depth, dramatic film lighting, luxurious fine-detail materials, no person, no text, no logo, dark uncluttered lower left for separately overlaid presenter, visual interest on right: '
NEG='people, person, woman, man, face, portrait, human, text, letters, numbers, words, watermark, logo, caption, cartoon, blurry, low quality'

def api(base,route,payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(base+route,data=data,headers={'Content-Type':'application/json'} if data else {})
    with urllib.request.urlopen(req,timeout=40) as res: return json.loads(res.read())

def workflow(checkpoint,prompt,seed,prefix):
    return {
      '1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':checkpoint}},
      '2':{'class_type':'CLIPTextEncode','inputs':{'clip':['1',1],'text':prompt}},
      '3':{'class_type':'CLIPTextEncode','inputs':{'clip':['1',1],'text':NEG}},
      '4':{'class_type':'EmptyLatentImage','inputs':{'width':640,'height':360,'batch_size':1}},
      '5':{'class_type':'KSampler','inputs':{'model':['1',0],'positive':['2',0],'negative':['3',0],'latent_image':['4',0],'seed':seed,'steps':24,'cfg':7.0,'sampler_name':'euler','scheduler':'normal','denoise':1.0}},
      '6':{'class_type':'VAEDecode','inputs':{'samples':['5',0],'vae':['1',2]}},
      '7':{'class_type':'SaveImage','inputs':{'images':['6',0],'filename_prefix':prefix}},
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--checkpoint')
    args=parser.parse_args(); base='http://127.0.0.1:8188'
    q=api(base,'/queue')
    if q['queue_running'] or q['queue_pending']: raise SystemExit('REFUSE: COMFYUI_QUEUE_BUSY')
    choices=api(base,'/object_info/CheckpointLoaderSimple')['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    ckpt=args.checkpoint or next((c for c in ['v1-5-pruned-emaonly.safetensors','meinamix_meinaV11.safetensors'] if c in choices),None)
    if ckpt not in choices: raise SystemExit('REFUSE: No preferred checkpoint installed. Available: '+repr(choices))
    print('CHECKPOINT=',ckpt,'OUTPUT=',DEST,'EXECUTE=',args.execute,flush=True)
    print('SIZE=640x360 native; 1920x1080 resized review candidates')
    if not args.execute:
        print('DRY_RUN=PASS; run again with --execute'); return
    DEST.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,scene in enumerate(SCENES,1):
        name=f'scene_{i:02d}'; dest=DEST/(name+'.png'); recpath=DEST/(name+'.candidate.json')
        if dest.exists() or recpath.exists():
            print('PRESERVE_EXISTING=',dest)
            continue
        q=api(base,'/queue')
        if q['queue_running'] or q['queue_pending']: raise SystemExit('REFUSE: COMFYUI_QUEUE_BUSY')
        prompt=POS+scene; seed=2026110300+i
        request=api(base,'/prompt',{'prompt':workflow(ckpt,prompt,seed,'dicere_bg_'+name),'client_id':'dio-dicere-v3-backgrounds'})
        pid=request.get('prompt_id')
        if not pid: raise SystemExit('REFUSE: NOT_ACCEPTED '+repr(request))
        print('SUBMITTED=',name,pid,flush=True)
        started=time.monotonic()
        while True:
            if time.monotonic()-started>900: raise SystemExit('REFUSE: JOB_TIMEOUT '+pid)
            hist=api(base,'/history/'+pid).get(pid,{})
            if hist.get('status',{}).get('status_str')=='error': raise SystemExit('REFUSE: JOB_ERROR '+repr(hist['status']))
            if hist.get('outputs'): break
            time.sleep(2)
        images=hist['outputs'].get('7',{}).get('images',[])
        if len(images)!=1: raise SystemExit('REFUSE: INVALID_IMAGES '+repr(images))
        info=images[0]
        params=urllib.parse.urlencode({'filename':info['filename'],'subfolder':info.get('subfolder',''),'type':info.get('type','output')})
        with urllib.request.urlopen(base+'/view?'+params,timeout=60) as r: raw=r.read()
        with Image.open(io.BytesIO(raw)) as im:
            if im.size!=(640,360): raise SystemExit('REFUSE: INVALID_IMAGE_DIMENSIONS')
            out=im.convert('RGB').resize((1920,1080),Image.Resampling.LANCZOS)
            temp=dest.with_suffix('.tmp.png'); out.save(temp)
        temp.rename(dest)
        rec={'schema':'dio.pictora.dicere_background_candidate.v1','state':'AWAITING_HUMAN_VISUAL_REVIEW','release_authorized':False,'generator':'local_comfyui_api','checkpoint':ckpt,'checkpoint_terms':'NOT_VERIFIED_BY_THIS_SCRIPT','prompt_id':pid,'seed':seed,'prompt':prompt,'negative_prompt':NEG,'original_dimensions':[640,360],'output_dimensions':[1920,1080],'resizing':'Lanczos_3x','source_sha256':hashlib.sha256(raw).hexdigest(),'output_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
        recpath.write_text(json.dumps(rec,indent=2)+'\n')
        records.append(rec); print('CREATED=',dest,flush=True)
    print('STAGED_IMAGES=',len(list(DEST.glob('scene_0[1-5].png'))))
    print('STATE=AWAITING_HUMAN_VISUAL_REVIEW')

if __name__=='__main__': main()
