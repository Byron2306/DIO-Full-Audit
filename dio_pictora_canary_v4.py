#!/usr/bin/env python3
"""DIO Pictora V4: three ControlDrift scenes conditioned on accepted V3 artwork.

No production writes. Workflow/outputs/receipts remain within --out.
Human review is necessary before any PICTORA_PASS or downstream use.
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

STYLE = (
    'DIO Gilded House visual canon, abstract governance instrumentation, ceremonial '
    'precision-engineered intelligence interface, obsidian black void, fine champagne-gold '
    'concentric mechanisms, intricate radial circuit paths, fine concentric calibration marks, '
    'luminous gold nodes and delicate connecting traces, warm volumetric glows, intricate '
    'sharp graphic detail, monumental dimensional layering, visual editorial concept art, '
    'premium technology art direction, coherent materiality, deep shadows, asymmetric '
    'visual storytelling with intentional negative space, no visible words'
)
NEGATIVE = (
    'real estate, headquarters, building, skyscraper, facade, windows, architectural exterior, '
    'architecture photography, sky, tree, grass, office, hallway, cathedral, palace, baroque '
    'interior, rococo, golden room, paper, stationery, desk, folders, documents, book, stamps, '
    'people, faces, hands, stock photography, literal screens, fake user interface, typography, '
    'text, letters, numbers, symbols resembling language, watermark, logos, giant eyeball, '
    'photorealistic landscape, overexposed haze, clutter, illegible data'
)
SCENES = [
    {
        'id':'01_exception_detected', 'seed_offset':101,
        'meaning':'A single control exception is detected in an otherwise coherent verified register.',
        'prompt': (
            'Central dramatic story: ONE tiny vivid crimson-red anomaly node has broken an otherwise '
            'orderly circular perimeter of twenty verified warm gold control nodes. The anomalous node '
            'sits off-axis at lower right, with one severed luminous connection visibly interrupting '
            'the gold circuit. Fine gold lines connect unaffected nodes, and a faint crimson ripple '
            'propagates from exactly one point. Obvious red-versus-gold contrast, clearly localized '
            'single exception, large dark negative-space area on left for later typography. '
        ),
        'must_show':['one localized crimson exception','normal gold network visibly distinct','broken/interrupting control path']
    },
    {
        'id':'02_conflicting_evidence', 'seed_offset':202,
        'meaning':'Two evidence branches disagree; reconciliation and sign-off are unresolved.',
        'prompt': (
            'Central dramatic story: TWO DISTINCT elegantly engineered gold evidence rings, separated '
            'left and right, each connected to its own gold node chains. Their outgoing light traces '
            'converge near center but terminate in an unmistakable fractured bridge of alternating '
            'gold and restrained crimson light. Between them a SMALL dark empty authorization '
            'receptacle stays unlit. Two opposing systems in tension, a visible unresolved '
            'contradiction, not one single circular emblem. Reserve a dark upper-left zone for '
            'later composited typography. '
        ),
        'must_show':['two opposing evidence branches','visible contradiction at their meeting','unlit approval receptacle']
    },
    {
        'id':'03_human_approval_pending', 'seed_offset':303,
        'meaning':'The reconciled evidence trail is review-ready; human approval has not been granted.',
        'prompt': (
            'Central dramatic story: a SERIES of distinct small gold evidence nodes now linked in '
            'a clear converging, orderly path from foreground bottom toward an elevated focal '
            'authorization mechanism. All lines of evidence are coherent, but the FINAL terminal '
            'at center-top remains CLOSED and visibly DARK, with a restrained thin crimson '
            'lock indicator. Clearly depict authorization as pending, not approved. Show measured '
            'progress toward a guarded decision threshold, abstract graphical apparatus rather '
            'than architecture. Reserve a dark left margin for later text. '
        ),
        'must_show':['coherent traceable evidence path','visibly closed approval point','no granted approval']
    },
]

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

def call(base, route, data=None, timeout=30, headers=None):
    request=urllib.request.Request(base.rstrip('/')+route,data=data,headers=headers or {},method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(request,timeout=timeout) as response:
        return response.read()

def get_json(base,route):return json.loads(call(base,route))
def post_json(base,route,value):return json.loads(call(base,route,json.dumps(value).encode(),headers={'Content-Type':'application/json'},timeout=90))

def choices(info,node,field):
    raw=info[node]['input']['required'][field][0]
    return raw if isinstance(raw,list) else []

def set_inputs(info,node,values):
    spec=info[node]['input'];required=spec.get('required',{});optional=spec.get('optional',{})
    result={}
    for key,definition in required.items():
        if key in values:result[key]=values[key]
        elif len(definition)>1 and isinstance(definition[1],dict) and 'default' in definition[1]:result[key]=definition[1]['default']
        elif isinstance(definition[0],list) and definition[0]:result[key]=definition[0][0]
        else:raise RuntimeError(f'REFUSE_UNSUPPORTED_REQUIRED_INPUT: {node}.{key}')
    for key,val in values.items():
        if key in optional:result[key]=val
        elif key not in required:raise RuntimeError(f'REFUSE_MISSING_NODE_INPUT: {node}.{key}')
    for key,val in result.items():
        definition=required.get(key,optional.get(key))
        if definition and isinstance(definition[0],list) and val not in definition[0]:
            raise RuntimeError(f'REFUSE_INVALID_NODE_CHOICE: {node}.{key}={val!r}; choices={definition[0]}')
    return result

def upload(base,reference):
    boundary='----dio-v4-'+uuid.uuid4().hex
    filename='DIO_V3_APPROVED_CANON_'+uuid.uuid4().hex[:12]+'.png'
    data=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode()+reference.read_bytes()+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n--{boundary}--\r\n'.encode())
    res=json.loads(call(base,'/upload/image',data,90,{'Content-Type':'multipart/form-data; boundary='+boundary}))
    if not res.get('name'):raise RuntimeError('REFUSE_UPLOAD_NOT_CONFIRMED: '+str(res))
    return res

def graph_for(info,a,scene,uploaded,checkpoint,preset):
    pos=STYLE+'. '+scene['prompt']
    model_loader=set_inputs(info,'IPAdapterUnifiedLoader',{'model':['1',0],'preset':preset})
    adapter=set_inputs(info,'IPAdapterAdvanced',{
        'model':['6',0],'ipadapter':['6',1],'image':['5',0],
        'weight':a.weight,'weight_type':'linear','combine_embeds':'concat',
        'start_at':0.0,'end_at':1.0,'embeds_scaling':'V only'})
    seed=a.seed+scene['seed_offset']
    graph={
        '1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':checkpoint}},
        '2':{'class_type':'CLIPTextEncode','inputs':{'text':pos,'clip':['1',1]}},
        '3':{'class_type':'CLIPTextEncode','inputs':{'text':NEGATIVE,'clip':['1',1]}},
        '4':{'class_type':'EmptyLatentImage','inputs':{'width':a.width,'height':a.height,'batch_size':1}},
        '5':{'class_type':'LoadImage','inputs':{'image':uploaded['name']}},
        '6':{'class_type':'IPAdapterUnifiedLoader','inputs':model_loader},
        '7':{'class_type':'IPAdapterAdvanced','inputs':adapter},
        '8':{'class_type':'KSampler','inputs':{'seed':seed,'steps':a.steps,'cfg':a.cfg,'sampler_name':'dpmpp_2m','scheduler':'karras','denoise':1.0,'model':['7',0],'positive':['2',0],'negative':['3',0],'latent_image':['4',0]}},
        '9':{'class_type':'VAEDecode','inputs':{'samples':['8',0],'vae':['1',2]}},
        '10':{'class_type':'SaveImage','inputs':{'images':['9',0],'filename_prefix':'DIO_ControlDrift_V4_'+scene['id']}},
    }
    return graph,pos,seed

def save_json(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')

def visual_signature(path):
    with Image.open(path) as img:
        im=ImageOps.grayscale(img).resize((9,8),Image.Resampling.LANCZOS)
        vals=list(im.getdata()); w=9
        bits=''.join('1' if vals[y*w+x]>vals[y*w+x+1] else '0' for y in range(8) for x in range(8))
        return int(bits,2)

def contact_sheet(images,output):
    thumbs=[]
    for sid,path in images:
        with Image.open(path) as im:
            thumb=im.convert('RGB'); thumb.thumbnail((768,512))
        thumbs.append((sid,thumb))
    sheet=Image.new('RGB',(768,3*560),'#090909');draw=ImageDraw.Draw(sheet)
    for i,(sid,thumb) in enumerate(thumbs):
        draw.text((20,i*560+10),sid,fill='#e5c476')
        sheet.paste(thumb,((768-thumb.width)//2,i*560+36))
    sheet.save(output,quality=93)

def run(a):
    out=Path(a.out).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    ref=Path(a.reference).expanduser().resolve()
    receipt=out/'receipt.json'
    rec={'contract':'DIO_PICTORA_CONTROLDRIFT_REFERENCE_CONDITIONED_V4',
         'product':'ControlDrift','status':'REFUSE_PRECHECK','pictora_pass':False,
         'production_replacement':False,'semantic_review':'NOT_PERFORMED',
         'created_utc':datetime.now(timezone.utc).isoformat(),'reference_path':str(ref),
         'conditioning':'IPAdapterUnifiedLoader -> IPAdapterAdvanced -> KSampler',
         'scenes':[]}
    save_json(out/'scene_contract.json',{'contract':rec['contract'],'visual_canon_reference':ref.name,
                'requirements':['three separately generated scenes','actual IPAdapter in model execution path',
                    'one product-specific visual metaphor per scene','human semantic and style review'],
                'forbidden':['production writes','PICTORA_PASS from hash difference alone'],
                'scenes':SCENES})
    try:
        if not ref.is_file():raise RuntimeError('REFUSE_REFERENCE_MISSING: '+str(ref))
        with Image.open(ref) as im:im.verify()
        rec['reference_sha256']=sha256(ref)
        info=get_json(a.url,'/object_info')
        required=('CheckpointLoaderSimple','CLIPTextEncode','EmptyLatentImage','KSampler','VAEDecode','SaveImage','LoadImage','IPAdapterUnifiedLoader','IPAdapterAdvanced')
        missing=[name for name in required if name not in info]
        if missing:raise RuntimeError('REFUSE_MISSING_NODES: '+', '.join(missing))
        checkpoints=choices(info,'CheckpointLoaderSimple','ckpt_name')
        checkpoint=a.checkpoint or next((x for part in ('v1-5-pruned-emaonly','meinamix_meinaV11') for x in checkpoints if part in x),None)
        if not checkpoint or checkpoint not in checkpoints:raise RuntimeError('REFUSE_CHECKPOINT_UNAVAILABLE: '+str(checkpoint)+'; available='+str(checkpoints))
        presets=choices(info,'IPAdapterUnifiedLoader','preset')
        preset=a.preset or next((x for x in presets if 'PLUS' in x.upper() and 'FACE' not in x.upper()),None) or next((x for x in presets if 'STANDARD' in x.upper() or 'LIGHT' in x.upper()),None)
        if not preset or preset not in presets:raise RuntimeError('REFUSE_GENERAL_IPADAPTER_PRESET_UNAVAILABLE: '+str(presets))
        rec.update({'checkpoint':checkpoint,'preset':preset,'parameters':{'weight':a.weight,'cfg':a.cfg,'steps':a.steps,'seed_base':a.seed,'width':a.width,'height':a.height},'status':'PREFLIGHT_PASSED'})
        save_json(receipt,rec)
        uploaded=upload(a.url,ref);rec['reference_upload']=uploaded
        print('V4_PREFLIGHT=PASS CHECKPOINT='+checkpoint+' PRESET='+preset+' REFERENCE_SHA256='+rec['reference_sha256'],flush=True)
        images=[]
        for scene in SCENES:
            sid=scene['id'];entry={'scene_id':sid,'meaning':scene['meaning'],'must_show':scene['must_show'],'status':'PREPARING'}
            rec['scenes'].append(entry);save_json(receipt,rec)
            graph,prompt,seed=graph_for(info,a,scene,uploaded,checkpoint,preset)
            wf=out/(sid+'_workflow.json');save_json(wf,graph)
            entry.update({'workflow_path':str(wf),'workflow_sha256':sha256(wf),'seed':seed,'prompt':prompt,'negative_prompt':NEGATIVE})
            rec['status']='DISPATCHING';save_json(receipt,rec)
            result=post_json(a.url,'/prompt',{'prompt':graph,'client_id':'dio-control-drift-v4-'+uuid.uuid4().hex[:12]})
            if result.get('node_errors'):raise RuntimeError('REFUSE_COMFY_NODE_ERRORS: '+json.dumps(result['node_errors'])[:2000])
            pid=result.get('prompt_id')
            if not pid:raise RuntimeError('REFUSE_NO_COMFY_PROMPT_ID: '+str(result))
            entry.update({'prompt_id':pid,'status':'QUEUED'});rec['status']='GENERATING';save_json(receipt,rec)
            print('SCENE='+sid+' SUBMITTED_PROMPT_ID='+pid,flush=True)
            deadline=time.monotonic()+a.timeout
            while time.monotonic()<deadline:
                history=get_json(a.url,'/history/'+urllib.parse.quote(pid))
                if pid not in history:
                    time.sleep(2);continue
                h=history[pid];status=h.get('status',{})
                if status.get('status_str')=='error' or status.get('completed') is False:
                    raise RuntimeError('REFUSE_COMFY_EXECUTION_ERROR: '+json.dumps(status)[:1800])
                artifacts=h.get('outputs',{}).get('10',{}).get('images',[])
                if not artifacts:raise RuntimeError('REFUSE_NO_SAVEIMAGE_OUTPUT: '+sid)
                artifact=artifacts[0]
                qs=urllib.parse.urlencode({k:artifact.get(k,'') for k in ('filename','subfolder','type')})
                blob=call(a.url,'/view?'+qs,timeout=90)
                target=out/(sid+'.png');target.write_bytes(blob)
                with Image.open(BytesIO(blob)) as im:im.verify()
                entry.update({'status':'GENERATED','image_path':str(target),'image_sha256':sha256(target),
                              'comfy_output':artifact,'comfy_status':status,'reference_conditioning_graph_verified':True})
                images.append((sid,target));save_json(receipt,rec)
                print('SCENE='+sid+' GENERATED='+str(target)+' SHA256='+entry['image_sha256'],flush=True)
                break
            else:raise TimeoutError('REFUSE_COMFY_PROMPT_TIMEOUT: '+pid)
        sig=[visual_signature(path) for _,path in images]
        distances={f'{SCENES[i]["id"]} vs {SCENES[j]["id"]}':(sig[i]^sig[j]).bit_count()
                   for i in range(3) for j in range(i+1,3)}
        rec['visual_dhash_distances']=distances
        rec['all_distinct_byte_hashes']=len({entry['image_sha256'] for entry in rec['scenes']})==3
        rec['minimum_dhash_distance']=min(distances.values())
        contact=out/'three_scene_contact_sheet.jpg';contact_sheet(images,contact)
        rec['contact_sheet_path']=str(contact);rec['contact_sheet_sha256']=sha256(contact)
        # Quantitative distinctness is diagnostic, NOT proof of semantic correctness.
        rec['status']='AWAITING_HUMAN_SEMANTIC_REVIEW' if rec['all_distinct_byte_hashes'] and rec['minimum_dhash_distance']>=8 else 'REFUSE_INSUFFICIENT_VISUAL_DIFFERENTIATION'
        print('VISUAL_DHASH_DISTANCES='+json.dumps(distances),flush=True)
        print('FINAL_STATUS='+rec['status']+' CONTACT_SHEET='+str(contact),flush=True)
        return 0 if rec['status']=='AWAITING_HUMAN_SEMANTIC_REVIEW' else 3
    except (urllib.error.HTTPError,Exception) as error:
        detail=str(error)
        if isinstance(error,urllib.error.HTTPError):detail=f'HTTP {error.code}: '+error.read().decode('utf-8','replace')[:2000]
        rec.update({'status':'REFUSE_EXECUTION_ERROR','error':detail});print('REFUSE='+detail,file=sys.stderr,flush=True)
        return 2
    finally:
        save_json(receipt,rec)
        print('RECEIPT='+str(receipt)+' STATUS='+rec['status'],flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default='http://127.0.0.1:8188')
    p.add_argument('--reference',default=str(Path(__file__).with_name('DIO_ControlDrift_Gilded_V3_00001_.png')))
    p.add_argument('--out',default='/data/byron/dio-pictora-control-drift-canary-v4')
    p.add_argument('--checkpoint',default='');p.add_argument('--preset',default='')
    p.add_argument('--weight',type=float,default=0.65)
    p.add_argument('--seed',type=int,default=552280)
    p.add_argument('--steps',type=int,default=32)
    p.add_argument('--cfg',type=float,default=7)
    p.add_argument('--width',type=int,default=768)
    p.add_argument('--height',type=int,default=512)
    p.add_argument('--timeout',type=int,default=420)
    a=p.parse_args()
    if a.width%8 or a.height%8 or a.width<=0 or a.height<=0:p.error('dimensions must be positive multiples of 8')
    if not 0<a.weight<=1.5:p.error('weight must be >0 and <=1.5')
    if a.steps<1:p.error('steps must be positive')
    return run(a)

if __name__=='__main__':sys.exit(main())
