#!/usr/bin/env python3
"""Isolated ControlDrift Pictora canary. No production-code writes."""
import argparse, hashlib, json, math, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageStat

STYLE = ("DIO Gilded House visual identity, monumental sovereign corporate intelligence architecture, "
         "near-black obsidian and aged champagne-gold palette, engraved metallic filigree, "
         "precise luminous circuit pathways, deep cinematic architectural shadows, "
         "awe-inspiring ceremonial governance technology, premium dark science-fiction concept art, "
         "highly designed institutional environment, volumetric shafts of amber light, "
         "microdetail, restrained controlled highlights, luxurious depth and scale, "
         "complex architectural geometry, no readable interface text, no people")
SCENES = [
    ("01_exception_discovery", STYLE + ", WIDE ESTABLISHING COMPOSITION: vast black-gold control tribunal chamber, "
     "one conspicuous crimson anomaly illuminated inside a majestic three dimensional floating grid of otherwise gold verified evidence nodes, "
     "anomaly is the unequivocal focal point, vertical ribbed obsidian walls, layered gold frame architecture, "
     "dramatic asymmetrical light, technical governance apparatus, distinct anomaly discovery narrative"),
    ("02_conflicting_evidence", STYLE + ", MEDIUM ANGLED COMPOSITION: twin towering black glass evidence monoliths "
     "opposite one another in a gilded arbitration hall, conflicting gold and crimson light paths crossing and breaking between the two structures, "
     "one conspicuous empty approval socket in the center, fractured symmetrical data bridge, "
     "a clear state of unresolved contradiction and absent authorization, no paper objects"),
    ("03_review_pending", STYLE + ", LONG CENTRAL PERSPECTIVE COMPOSITION: a luminous ordered chain of "
     "three connected evidence vaults receding toward a monumental closed gold threshold, "
     "evidence paths converge into an unlit human authorization dais whose final aperture remains visibly dark, "
     "balanced ceremonial architecture, resolved organization but visibly pending approval, no paper objects"),
]
NEGATIVE = ("white paper, blank sheets, office stationery, folders, ledgers, books, pens, table, cups, coffee, "
            "minimalist office interior, flat lay, tabletop product photography, mundane desk, stock photograph, "
            "plain grey backdrop, empty room, excessive white background, generic business documents, "
            "photographic paperwork, text, illegible writing, letterforms, captions, watermark, branding, "
            "faces, humans, hands, logos, gold eyeball logo, centered concentric circular wallpaper, "
            "single repeated golden emblem, messy composition, blurry, low quality")

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def sha256_file(p): return sha256_bytes(Path(p).read_bytes())
def api(base, path, data=None, timeout=30):
    url=base.rstrip('/')+path
    req=urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type':'application/json'} if data is not None else {}, method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
def json_api(base,path,data=None,timeout=30): return json.loads(api(base,path,data,timeout))
def pick_checkpoint(base, preferred):
    info=json_api(base, '/object_info/CheckpointLoaderSimple')
    options=info['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    if not options: raise RuntimeError('No checkpoint registered in ComfyUI')
    if preferred:
        if preferred not in options: raise RuntimeError('Requested checkpoint unavailable: '+preferred+'; installed='+str(options))
        return preferred
    for prefix in ('v1-5-pruned-emaonly','meinamix_meinaV11'):
        for name in options:
            if prefix.lower() in name.lower(): return name
    return options[0]
def workflow(prompt,seed,checkpoint,width,height,steps,cfg):
    return {
        '1': {'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':checkpoint}},
        '2': {'class_type':'CLIPTextEncode','inputs':{'text':prompt,'clip':['1',1]}},
        '3': {'class_type':'CLIPTextEncode','inputs':{'text':NEGATIVE,'clip':['1',1]}},
        '4': {'class_type':'EmptyLatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
        '5': {'class_type':'KSampler','inputs':{'seed':seed,'steps':steps,'cfg':cfg,'sampler_name':'dpmpp_2m','scheduler':'karras','denoise':1,'model':['1',0],'positive':['2',0],'negative':['3',0],'latent_image':['4',0]}},
        '6': {'class_type':'VAEDecode','inputs':{'samples':['5',0],'vae':['1',2]}},
        '7': {'class_type':'SaveImage','inputs':{'images':['6',0],'filename_prefix':'DIO_ControlDrift_Gilded_V2'}},
    }
def ahash(im, size=16):
    vals=list(im.convert('L').resize((size,size)).getdata()); avg=sum(vals)/len(vals)
    return [v>=avg for v in vals]
def distance(a,b): return sum(x!=y for x,y in zip(a,b))
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--url',default='http://127.0.0.1:8188')
    ap.add_argument('--out',default='/data/byron/dio-pictora-control-drift-canary-v2')
    ap.add_argument('--checkpoint',default='')
    ap.add_argument('--width',type=int,default=768)
    ap.add_argument('--height',type=int,default=512)
    ap.add_argument('--steps',type=int,default=32)
    ap.add_argument('--cfg',type=float,default=7.5)
    ap.add_argument('--timeout',type=int,default=420)
    args=ap.parse_args()
    out=Path(args.out).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    if args.width%8 or args.height%8: ap.error('Dimensions must be multiples of 8')
    checkpoint=pick_checkpoint(args.url,args.checkpoint)
    # Hash the model file when this canary runs beside the known local ComfyUI installation.
    model_root=Path('/data/byron/lilith-local/runtime/ComfyUI/models/checkpoints')
    checkpoint_path=(model_root/checkpoint).resolve()
    checkpoint_hash=(sha256_file(checkpoint_path) if checkpoint_path.is_file() and checkpoint_path.is_relative_to(model_root.resolve()) else None)
    obj=json_api(args.url,'/object_info')
    for name in ['CheckpointLoaderSimple','CLIPTextEncode','EmptyLatentImage','KSampler','VAEDecode','SaveImage']:
        if name not in obj: raise RuntimeError('Missing actual ComfyUI node '+name)
    record={'contract':'PICTORA_SCENE_ASSET_CANARY_V2_PROMPT_ONLY','product':'ControlDrift','style_conditioning':'TEXT_ONLY_NO_REFERENCE_IMAGE_BINDING','comfy_url':args.url,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'checkpoint':checkpoint,'checkpoint_sha256':checkpoint_hash,'checkpoint_hash_status':('VERIFIED' if checkpoint_hash else 'UNAVAILABLE'),'status':'IN_PROGRESS','scenes':[],'pairwise':[]}
    ledger=out/'receipt.json'
    try:
        for i,(key,prompt) in enumerate(SCENES):
            seed=552280+i*101
            graph=workflow(prompt,seed,checkpoint,args.width,args.height,args.steps,args.cfg)
            graph_path=out/f'{key}_workflow.json'; graph_path.write_text(json.dumps(graph,indent=2))
            entry={'scene':key,'meaning':('exception discovery','contradictory evidence and missing sign-off','evidence trail with human approval pending')[i], 'seed':seed,'prompt':prompt,'negative_prompt':NEGATIVE,'workflow_path':str(graph_path),'workflow_sha256':sha256_file(graph_path),'checkpoint':checkpoint,'steps':args.steps,'cfg':args.cfg,'width':args.width,'height':args.height}
            record['scenes'].append(entry); ledger.write_text(json.dumps(record,indent=2))
            queued=json_api(args.url,'/prompt',{'prompt':graph,'client_id':'dio-pictora-control-drift-canary'})
            pid=queued.get('prompt_id')
            if not pid: raise RuntimeError('ComfyUI did not return prompt_id: '+str(queued))
            entry['comfy_prompt_id']=pid
            deadline=time.monotonic()+args.timeout
            while time.monotonic()<deadline:
                hist=json_api(args.url,'/history/'+urllib.parse.quote(pid))
                if pid in hist:
                    run=hist[pid]
                    status=run.get('status',{})
                    if status.get('status_str')=='error' or status.get('completed') is False:
                        raise RuntimeError('ComfyUI generation failed: '+json.dumps(status)[:1200])
                    imgs=[im for node in run.get('outputs',{}).values() for im in node.get('images',[])]
                    if imgs:
                        src=imgs[0]
                        qs=urllib.parse.urlencode({k:src.get(k,'') for k in ('filename','subfolder','type')})
                        blob=api(args.url,'/view?'+qs,timeout=60)
                        p=out/f'{key}.png'; p.write_bytes(blob)
                        with Image.open(BytesIO(blob)) as im:
                            im.verify()
                        entry.update({'source':'COMFYUI_HISTORY_OUTPUT','comfy_output':src,'image_path':str(p),'image_sha256':sha256_bytes(blob),'bytes':len(blob)})
                        print('GENERATED',key,p.name,entry['image_sha256'][:16],flush=True)
                        ledger.write_text(json.dumps(record,indent=2))
                        break
                    raise RuntimeError('ComfyUI history has no output images: '+pid)
                time.sleep(2)
            else: raise TimeoutError('Timed out waiting for '+key+' prompt '+pid)
        ims=[Image.open(s['image_path']).convert('RGB') for s in record['scenes']]
        try:
            hashes=[ahash(im) for im in ims]
            for i in range(len(ims)):
                for j in range(i+1,len(ims)):
                    d=distance(hashes[i],hashes[j]); different_pixels=ImageChops.difference(ims[i].resize((256,256)),ims[j].resize((256,256))).getbbox() is not None
                    record['pairwise'].append({'a':SCENES[i][0],'b':SCENES[j][0],'average_hash_hamming_256':d,'different_pixels':different_pixels})
            tile_w,tile_h=512,380
            sheet=Image.new('RGB',(tile_w*3,tile_h),'#101010'); dr=ImageDraw.Draw(sheet)
            for idx,im in enumerate(ims):
                t=im.copy(); t.thumbnail((tile_w-20,tile_h-65)); sheet.paste(t,(idx*tile_w+(tile_w-t.width)//2,28))
                dr.text((idx*tile_w+12,8),SCENES[idx][0],fill='#efc46c')
                dr.text((idx*tile_w+12,tile_h-23),record['scenes'][idx]['image_sha256'][:24],fill='#ddd')
            preview=out/'three_scene_contact_sheet.jpg'; sheet.save(preview,quality=92)
            record['contact_sheet_path']=str(preview);record['contact_sheet_sha256']=sha256_file(preview)
            distinct_sha=len({s['image_sha256'] for s in record['scenes']})==3
            distinct_visual=all(r['different_pixels'] and r['average_hash_hamming_256']>=12 for r in record['pairwise'])
            record['automated_checks']={'three_real_comfy_outputs':all(s['source']=='COMFYUI_HISTORY_OUTPUT' for s in record['scenes']),'unique_image_sha256':distinct_sha,'visual_difference_ahash_hamming_at_least_12':distinct_visual,'hash_bound_workflows':all(s['workflow_sha256']==sha256_file(s['workflow_path']) for s in record['scenes'])}
            record['status']='AWAITING_HUMAN_SEMANTIC_REVIEW' if all(record['automated_checks'].values()) else 'REFUSE_AUTOMATED_CHECKS'
        finally:
            for im in ims: im.close()
    except Exception as exc:
        record['status']='REFUSE_EXECUTION_ERROR';record['error']=repr(exc)
        raise
    finally:
        ledger.write_text(json.dumps(record,indent=2))
        print('RECEIPT',ledger,'STATUS',record['status'],flush=True)
    if record['status']!='AWAITING_HUMAN_SEMANTIC_REVIEW': sys.exit(2)
    print('CONTACT_SHEET',record['contact_sheet_path'])
    print('NOTE: image difference is automatic; product relevance requires HUMAN review. No PICTORA_PASS or production replacement issued.')

if __name__=='__main__': main()
