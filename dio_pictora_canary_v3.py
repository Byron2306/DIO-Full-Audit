#!/usr/bin/env python3
"""DIO Pictora ControlDrift V3: one reference-conditioned canary; no production writes."""
import argparse, hashlib, json, sys, time, urllib.request, urllib.parse, urllib.error, uuid
from datetime import datetime, timezone
from pathlib import Path
from io import BytesIO
from PIL import Image

PROMPT = (
    "DIO Gilded House visual canon, cinematic dark premium intelligence visualization, "
    "a CONTROL EXCEPTION DISCOVERY portrayed as an immense floating precision instrument, "
    "one unmistakable small crimson fault node interrupting a dense connected constellation "
    "of many verified champagne-gold control nodes and delicate lines, black obsidian negative space, "
    "volumetric warm gold point lights, precise concentric calibrated mechanical rings, "
    "fine etched filigree, graph-like governance circuitry, scientific dashboard concept art, "
    "staggered dimensional data layers, deliberate asymmetric hierarchy, restrained luxury, "
    "deep black backdrop, no human, no architecture, no typography, no brand lettering"
)
NEGATIVE = (
    "building, exterior, facade, office tower, windows, sky, trees, grass, building interior, "
    "hallway, cathedral, palace, temple, baroque room, rococo decorations, gold room, "
    "paper, notebook, envelope, desk, meeting room, portrait, person, stock photography, "
    "text, lettering, numbers, words, watermark, logo, giant eye, blurry, flat lighting"
)

def hashfile(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
    return h.hexdigest()

def request(base,route,data=None,timeout=25,headers=None):
    url=base.rstrip('/')+route
    req=urllib.request.Request(url,data=data,headers=headers or {},method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req,timeout=timeout) as resp: return resp.read()

def jget(base,route): return json.loads(request(base,route))
def jpost(base,route,obj):
    return json.loads(request(base,route,json.dumps(obj).encode(),headers={'Content-Type':'application/json'}))

def node_inputs(info,node):
    return info[node]['input']

def option(info,node,key):
    raw=node_inputs(info,node)['required'][key][0]
    return raw if isinstance(raw,list) else []

def pick(items,preferred,context):
    if preferred:
        if preferred not in items: raise RuntimeError(context+' requested '+repr(preferred)+' not present: '+str(items))
        return preferred
    if not items: raise RuntimeError(context+' has no available models/presets')
    return items[0]

def set_inputs(info,node,values,overrides=None):
    """Constrain inputs to runtime schema; fail on unknown required attributes."""
    spec=node_inputs(info,node)
    required=spec.get('required',{})
    optional=spec.get('optional',{})
    result={}
    for k,definition in required.items():
        if k in values: result[k]=values[k]
        elif overrides and k in overrides: result[k]=overrides[k]
        elif len(definition)>1 and isinstance(definition[1],dict) and 'default' in definition[1]: result[k]=definition[1]['default']
        elif isinstance(definition[0],list) and definition[0]: result[k]=definition[0][0]
        else: raise RuntimeError(f'Unsupported required input {node}.{k}; schema={definition}')
    for k,v in values.items():
        if k not in required and k in optional: result[k]=v
    return result

def upload_reference(base,path):
    boundary='----dio-canary-'+uuid.uuid4().hex
    fn='DIO_GILDED_CANON_V3_'+uuid.uuid4().hex[:10]+'.png'
    blob=path.read_bytes()
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{fn}"\r\nContent-Type: image/png\r\n\r\n'.encode()
          +blob+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n--{boundary}--\r\n'.encode())
    result=json.loads(request(base,'/upload/image',body,headers={'Content-Type':'multipart/form-data; boundary='+boundary},timeout=90))
    if not result.get('name'): raise RuntimeError('ComfyUI did not confirm reference upload: '+str(result))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default='http://127.0.0.1:8188')
    p.add_argument('--reference',default=str(Path(__file__).with_name('dio_gilded_canon_reference.png')))
    p.add_argument('--out',default='/data/byron/dio-pictora-control-drift-canary-v3')
    p.add_argument('--checkpoint',default='')
    p.add_argument('--preset',default='')
    p.add_argument('--weight',type=float,default=0.65)
    p.add_argument('--seed',type=int,default=552280)
    p.add_argument('--steps',type=int,default=32)
    p.add_argument('--cfg',type=float,default=7.0)
    p.add_argument('--width',type=int,default=768)
    p.add_argument('--height',type=int,default=512)
    p.add_argument('--timeout',type=int,default=420)
    a=p.parse_args()
    if a.width%8 or a.height%8: p.error('dimensions must be multiples of eight')
    if not 0<a.weight<=1.5: p.error('weight must be > 0 and <= 1.5')
    out=Path(a.out).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    ref=Path(a.reference).expanduser().resolve()
    receipt=out/'receipt.json'
    rec={'contract':'DIO_PICTORA_REFERENCE_CONDITIONED_SINGLE_SCENE_V3',
         'product':'ControlDrift','scene':'exception_discovery',
         'status':'REFUSE_PRECHECK','production_replacement':False,
         'created_utc':datetime.now(timezone.utc).isoformat(),
         'reference_path':str(ref),'conditioning':'IPAdapterUnifiedLoader+IPAdapterAdvanced',
         'url':a.url}
    try:
        if not ref.is_file(): raise RuntimeError('Missing visual canon reference: '+str(ref))
        with Image.open(ref) as im: im.verify()
        rec['reference_sha256']=hashfile(ref)
        info=jget(a.url,'/object_info')
        required=['CheckpointLoaderSimple','CLIPTextEncode','EmptyLatentImage','KSampler','VAEDecode','SaveImage','LoadImage','IPAdapterUnifiedLoader','IPAdapterAdvanced']
        missing=[n for n in required if n not in info]
        rec['available_ipadapter_nodes']=sorted(n for n in info if 'IPAdapter' in n)[:50]
        if missing: raise RuntimeError('REFUSE_MISSING_COMFY_NODES: '+', '.join(missing)+'. Available IPAdapter nodes: '+str(rec['available_ipadapter_nodes']))
        checkpoints=option(info,'CheckpointLoaderSimple','ckpt_name')
        checkpoint=a.checkpoint or next((x for k in ('v1-5-pruned-emaonly','meinamix_meinaV11') for x in checkpoints if k in x),None)
        checkpoint=pick(checkpoints,checkpoint,'Checkpoint')
        presets=option(info,'IPAdapterUnifiedLoader','preset')
        if not presets: raise RuntimeError('Cannot inspect IPAdapterUnifiedLoader preset list')
        # Prefer SD1.5 general image-style preset. Avoid FaceID/Portrait-only presets.
        preset=a.preset or next((x for x in presets if 'PLUS' in x.upper() and 'FACE' not in x.upper()),None) or next((x for x in presets if 'STANDARD' in x.upper() or 'LIGHT' in x.upper()),None)
        if not preset: raise RuntimeError('No suitable general-purpose IPAdapter preset; available='+str(presets))
        preset=pick(presets,preset,'IPAdapter preset')
        rec.update({'checkpoint':checkpoint,'ipadapter_preset':preset,'seed':a.seed,'steps':a.steps,'cfg':a.cfg,'weight':a.weight,'dimensions':[a.width,a.height],'prompt':PROMPT,'negative_prompt':NEGATIVE})
        print('PREFLIGHT=PASS','CHECKPOINT='+checkpoint,'IPADAPTER_PRESET='+preset,flush=True)
        remote=upload_reference(a.url,ref)
        rec['reference_upload']=remote
        graph={
            '1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':checkpoint}},
            '2':{'class_type':'CLIPTextEncode','inputs':{'text':PROMPT,'clip':['1',1]}},
            '3':{'class_type':'CLIPTextEncode','inputs':{'text':NEGATIVE,'clip':['1',1]}},
            '4':{'class_type':'EmptyLatentImage','inputs':{'width':a.width,'height':a.height,'batch_size':1}},
            '5':{'class_type':'LoadImage','inputs':{'image':remote['name']}},
            '6':{'class_type':'IPAdapterUnifiedLoader','inputs':set_inputs(info,'IPAdapterUnifiedLoader',{'model':['1',0],'preset':preset})},
            '7':{'class_type':'IPAdapterAdvanced','inputs':set_inputs(info,'IPAdapterAdvanced',{
                'model':['6',0],'ipadapter':['6',1],'image':['5',0],
                'weight':a.weight,'weight_type':'linear','combine_embeds':'concat',
                'start_at':0.0,'end_at':1.0,'embeds_scaling':'V only'})},
            '8':{'class_type':'KSampler','inputs':{'seed':a.seed,'steps':a.steps,'cfg':a.cfg,'sampler_name':'dpmpp_2m','scheduler':'karras','denoise':1.0,'model':['7',0],'positive':['2',0],'negative':['3',0],'latent_image':['4',0]}},
            '9':{'class_type':'VAEDecode','inputs':{'samples':['8',0],'vae':['1',2]}},
            '10':{'class_type':'SaveImage','inputs':{'images':['9',0],'filename_prefix':'DIO_ControlDrift_Gilded_V3'}},
        }
        # Reject incompatible dropdown values rather than silently ignoring image conditioning.
        for key in ('weight_type','combine_embeds','embeds_scaling'):
            raw=node_inputs(info,'IPAdapterAdvanced').get('required',{}).get(key) or node_inputs(info,'IPAdapterAdvanced').get('optional',{}).get(key)
            if raw and isinstance(raw[0],list) and graph['7']['inputs'].get(key) not in raw[0]:
                raise RuntimeError(f'IPAdapterAdvanced.{key} incompatible: chosen {graph["7"]["inputs"].get(key)!r}; options={raw[0]}')
        gp=out/'workflow.json'; gp.write_text(json.dumps(graph,indent=2));rec['workflow_path']=str(gp);rec['workflow_sha256']=hashfile(gp)
        rec['status']='SUBMITTING';receipt.write_text(json.dumps(rec,indent=2))
        result=jpost(a.url,'/prompt',{'prompt':graph,'client_id':'dio-pictora-canary-v3'})
        if result.get('node_errors'): raise RuntimeError('COMFY_NODE_ERRORS: '+json.dumps(result['node_errors'])[:1800])
        pid=result.get('prompt_id')
        if not pid: raise RuntimeError('No ComfyUI prompt_id: '+str(result))
        rec['comfy_prompt_id']=pid;rec['status']='GENERATING';receipt.write_text(json.dumps(rec,indent=2))
        print('SUBMITTED_COMFY_PROMPT_ID='+pid,flush=True)
        deadline=time.monotonic()+a.timeout
        while time.monotonic()<deadline:
            history=jget(a.url,'/history/'+urllib.parse.quote(pid))
            if pid in history:
                item=history[pid];status=item.get('status',{})
                rec['comfy_history_status']=status
                if status.get('status_str')=='error' or status.get('completed') is False:
                    raise RuntimeError('COMFY_EXECUTION_ERROR: '+json.dumps(status)[:2500])
                outputs=item.get('outputs',{}).get('10',{}).get('images',[])
                if not outputs: raise RuntimeError('SaveImage node 10 produced no image')
                img=outputs[0]
                q=urllib.parse.urlencode({k:img.get(k,'') for k in ('filename','subfolder','type')})
                blob=request(a.url,'/view?'+q,timeout=90)
                target=out/'exception_discovery_reference_conditioned.png';target.write_bytes(blob)
                with Image.open(BytesIO(blob)) as generated: generated.verify()
                rec.update({'status':'AWAITING_HUMAN_VISUAL_REVIEW','output_path':str(target),'output_sha256':hashfile(target),'comfy_output':img,'comfy_history_present':True,'semantic_acceptance':'NOT_YET_VERIFIED','reference_conditioning_graph_verified':True,'pictora_pass':False})
                print('GENERATED='+str(target),'OUTPUT_SHA256='+rec['output_sha256'],flush=True)
                break
            time.sleep(2)
        else: raise TimeoutError('COMFY_PROMPT_TIMEOUT '+pid)
    except urllib.error.HTTPError as ex:
        body=ex.read().decode('utf-8','replace')[:2000]
        rec.update({'status':'REFUSE_EXECUTION_ERROR','error':f'HTTP {ex.code}: {body}'})
        print('REFUSE:',rec['error'],file=sys.stderr)
        sys.exit(2)
    except Exception as ex:
        rec.update({'status':'REFUSE_EXECUTION_ERROR','error':str(ex)})
        print('REFUSE:',ex,file=sys.stderr)
        sys.exit(2)
    finally:
        receipt.write_text(json.dumps(rec,indent=2))
        print('RECEIPT='+str(receipt),'STATUS='+rec['status'],flush=True)
    print('NOTE: Reference-conditioning execution is verified, visual acceptance is not. No live production update.')

if __name__=='__main__': main()
