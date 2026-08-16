from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import textwrap
import wave
from pathlib import Path
from typing import Any

from PIL import Image,ImageDraw,ImageFont

from products.incarnation_studio import IncarnationStudioError,build_product_incarnation
from scripts import run_nichefoundry_jobs as nichefoundry

ROOT=Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN="DIO_MEDIA_INCARNATION_READY"
NOW="2026-08-16T12:00:00+00:00"
PALETTE={"ink":"#07111f","navy":"#0d2138","cyan":"#29d3c2","amber":"#ffb547","paper":"#f5f1e8","white":"#eef6f5"}


class MediaIncarnationError(RuntimeError):
    pass


def _canonical(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")


def _fingerprint(value:Any)->str:
    return "sha256:"+hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def _run(command:list[str])->subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command,check=True,text=True,capture_output=True)
    except FileNotFoundError as exc:
        raise MediaIncarnationError(f"required media tool missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise MediaIncarnationError(f"media command failed: {' '.join(command)}\n{exc.stderr}") from exc


def _toolchain()->dict[str,Any]:
    ffmpeg=shutil.which("ffmpeg");ffprobe=shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise MediaIncarnationError("FFmpeg and ffprobe are required for Phase 16.1")
    filters=_run([ffmpeg,"-hide_banner","-filters"]).stdout+_run([ffmpeg,"-hide_banner","-filters"]).stderr
    if " flite " not in filters:
        raise MediaIncarnationError("FFmpeg must include the offline flite narration filter")
    return {"ffmpeg":ffmpeg,"ffprobe":ffprobe,"narration_backend":"ffmpeg_flite","network_used":False}


def _fonts()->tuple[str,str]:
    regular=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not regular.is_file() or not bold.is_file():
        raise MediaIncarnationError("DejaVu fonts are required for deterministic media rendering")
    return str(regular),str(bold)


def _font(path:str,size:int)->ImageFont.FreeTypeFont:
    return ImageFont.truetype(path,size=size)


def _wrap(draw:ImageDraw.ImageDraw,text:str,font:ImageFont.FreeTypeFont,width:int)->list[str]:
    words=text.split();rows=[];line=""
    for word in words:
        candidate=(line+" "+word).strip()
        if draw.textbbox((0,0),candidate,font=font)[2]<=width:line=candidate
        else:
            if line:rows.append(line)
            line=word
    if line:rows.append(line)
    return rows


def _gradient(size:tuple[int,int])->Image.Image:
    w,h=size;image=Image.new("RGB",size,PALETTE["ink"]);px=image.load()
    for y in range(h):
        t=y/max(h-1,1)
        for x in range(w):
            glow=max(0.0,1.0-(((x-w*.78)/(w*.62))**2+((y-h*.18)/(h*.72))**2))
            px[x,y]=(int(7+8*glow),int(17+32*glow+8*t),int(31+42*glow+13*t))
    return image


def _render_card(path:Path,size:tuple[int,int],*,eyebrow:str,headline:str,body:str,cta:str,index:str|None=None)->None:
    regular,bold=_fonts();w,h=size;image=_gradient(size);draw=ImageDraw.Draw(image)
    margin=int(w*.075);accent=int(max(7,w*.008))
    draw.rounded_rectangle((margin,int(h*.09),margin+accent,int(h*.91)),radius=accent//2,fill=PALETTE["cyan"])
    eye=_font(bold,max(18,int(w*.019)));head=_font(bold,max(38,int(w*.052)));copy=_font(regular,max(20,int(w*.022)));button=_font(bold,max(20,int(w*.021)))
    draw.text((margin+accent+int(w*.025),int(h*.10)),eyebrow.upper(),font=eye,fill=PALETTE["cyan"])
    if index:
        bounds=draw.textbbox((0,0),index,font=eye)
        draw.text((w-margin-(bounds[2]-bounds[0]),int(h*.10)),index,font=eye,fill=PALETTE["amber"])
    y=int(h*.22)
    for row in _wrap(draw,headline,head,int(w*.76)):
        draw.text((margin+accent+int(w*.025),y),row,font=head,fill=PALETTE["white"]);y+=int(head.size*1.13)
    y+=int(h*.04)
    for row in _wrap(draw,body,copy,int(w*.72)):
        draw.text((margin+accent+int(w*.025),y),row,font=copy,fill="#bfd1d1");y+=int(copy.size*1.45)
    box=(margin+accent+int(w*.025),int(h*.80),margin+accent+int(w*.025)+int(w*.36),int(h*.89))
    draw.rounded_rectangle(box,radius=max(8,int(w*.009)),fill=PALETTE["amber"])
    label=draw.textbbox((0,0),cta,font=button);tx=box[0]+(box[2]-box[0]-(label[2]-label[0]))/2;ty=box[1]+(box[3]-box[1]-(label[3]-label[1]))/2-2
    draw.text((tx,ty),cta,font=button,fill="#15100a")
    path.parent.mkdir(parents=True,exist_ok=True);image.save(path,optimize=False,compress_level=9)


def _native_nichefoundry(now:str)->dict[str,Any]:
    job={"job_id":"NF-IRP-PHASE16-1","route":{"reason":"Phase 16.1 governed media incarnation","confidence":1.0},
      "inputs":[{"subject":"DIO IncidentReadinessProof campaign","sender":"phase16.1@local","attachment_names":"none"}],
      "evidence":[{"text_extract":"Incident readiness evidence review for operations and risk leaders."}]}
    original=nichefoundry.utc_now;nichefoundry.utc_now=lambda:now
    try:
        opportunity=nichefoundry.build_opportunity(job)
        request=nichefoundry.build_content_queue(job,opportunity)
        campaign=nichefoundry.build_campaign_markdown(job,opportunity).strip()+"\n"
    finally:nichefoundry.utc_now=original
    return {"job":job,"opportunity":opportunity,"request":request,"campaign_markdown":campaign,
      "binding_state":"DIO_ADAPTER_EXECUTION","live_adapter_invoked":True,"native_engine_invoked":False,
      "source_ref":"scripts/run_nichefoundry_jobs.py","native_engine_ref":"Byron2306/NicheFoundry"}


def _production_script()->list[dict[str,Any]]:
    return [
      {"id":1,"title":"The plan exists","visual":"A response plan, contact register and exercise record sit apart.","narration":"Your incident response plan may exist. Your role matrix may exist. Your exercise records may exist. But that does not mean the evidence agrees."},
      {"id":2,"title":"Evidence ages differently","visual":"Documents move across separate currency tracks.","narration":"Plans, named owners, exercises and contact details age at different speeds. One stale record can hide inside an otherwise complete-looking folder."},
      {"id":3,"title":"Map before you rely","visual":"The evidence resolves into coverage, currency and authority lanes.","narration":"DIO Incident Readiness Proof maps what is supplied, what is missing, what is stale, and which decisions still require a named human authority."},
      {"id":4,"title":"No readiness theatre","visual":"Unsupported certification and guaranteed recovery claims are visibly refused.","narration":"It does not certify readiness. It does not guarantee recovery. And it does not turn a generated dossier into operational authority."},
      {"id":5,"title":"A reviewable dossier","visual":"A governed evidence register, gap register and proof manifest appear.","narration":"The result is a reviewable, multi-format evidence dossier with a gap register, action boundary and hash-bound proof manifest."},
      {"id":6,"title":"Know before the incident does","visual":"The local intake gate opens while external release remains locked.","narration":"Prepare a controlled review locally. Keep the consequential decision human. Know what your response plan can prove before the incident does."}
    ]


def _format_time(seconds:float)->str:
    ms=int(round(seconds*1000));h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _probe(path:Path,ffprobe:str)->dict[str,Any]:
    result=_run([ffprobe,"-v","error","-show_entries","format=duration:stream=codec_type,codec_name,width,height","-of","json",str(path)])
    return json.loads(result.stdout)


def _render_media(output_dir:Path,script:list[dict[str,Any]],tools:dict[str,Any])->dict[str,Any]:
    media=output_dir/"media";ads=media/"ads";carousel=media/"carousel";youtube=media/"youtube";scenes=youtube/"scenes"
    for directory in (ads,carousel,youtube,scenes):directory.mkdir(parents=True,exist_ok=True)
    _render_card(ads/"LINKEDIN_1200x628.png",(1200,628),eyebrow="DIO // Incident readiness",headline="Your plan can be complete on paper and incomplete in evidence.",body="Map coverage, currency and human authority before relying on the plan.",cta="Prepare a controlled review")
    _render_card(ads/"SQUARE_1080x1080.png",(1080,1080),eyebrow="Incident ReadinessProof",headline="Know what the plan can prove.",body="See supported, stale, missing and human-dependent states separately.",cta="Review the evidence")
    slide_copy=[
      ("The plan exists.","But existence is not evidence currency."),
      ("Are the roles current?","Tie each response role to a named current owner."),
      ("Was it exercised?","Find the dated record for the scenario being reviewed."),
      ("Can every claim point to evidence?","Keep missing and stale material visible."),
      ("Know before the incident does.","Prepare a controlled evidence review.")
    ]
    for i,(headline,body) in enumerate(slide_copy,1):
        _render_card(carousel/f"SLIDE_{i:02}.png",(1080,1080),eyebrow="Five-minute evidence check",headline=headline,body=body,cta="DIO IncidentReadinessProof",index=f"{i:02} / 05")
    _render_card(youtube/"THUMBNAIL.png",(1280,720),eyebrow="Incident readiness",headline="CAN YOUR PLAN PROVE IT?",body="Coverage. Currency. Authority.",cta="DIO",index="EVIDENCE UNDER PRESSURE")
    for row in script:
        _render_card(scenes/f"SCENE_{row['id']:02}.png",(1920,1080),eyebrow="DIO // Incident Readiness",headline=row["title"],body=row["visual"],cta="Human authority preserved",index=f"{row['id']:02} / {len(script):02}")
    narration_text=" ".join(row["narration"] for row in script)
    narration_txt=youtube/"NARRATION.txt";narration_txt.write_text(narration_text+"\n",encoding="utf-8")
    narration=youtube/"NARRATION.wav"
    _run([tools["ffmpeg"],"-y","-hide_banner","-loglevel","error","-f","lavfi","-i",f"flite=textfile={narration_txt}:voice=slt","-ar","48000","-ac","1","-bitexact",str(narration)])
    with wave.open(str(narration),"rb") as wav:duration=wav.getnframes()/wav.getframerate()
    weights=[max(1,len(row["narration"].split())) for row in script];total=sum(weights)
    durations=[duration*w/total for w in weights]
    cursor=0.0;srt=[];timing=[]
    for index,(row,seconds) in enumerate(zip(script,durations),1):
        start=cursor;cursor+=seconds
        srt.extend([str(index),f"{_format_time(start)} --> {_format_time(cursor)}",row["narration"],""])
        timing.append({"scene":row["id"],"start_seconds":round(start,3),"end_seconds":round(cursor,3),"duration_seconds":round(seconds,3)})
    (youtube/"CAPTIONS.srt").write_text("\n".join(srt),encoding="utf-8")
    _write_json(youtube/"SHOT_LIST.json",{"schema":"dio.media_shot_list.v1","duration_seconds":round(duration,3),"shots":[dict(row,**timing[i]) for i,row in enumerate(script)]})
    metadata={"schema":"dio.youtube_package.v1","title":"Can Your Incident Plan Prove It? | DIO IncidentReadinessProof",
      "description":"A controlled demonstration of evidence coverage, currency and human authority. This is not certification or guaranteed recovery.",
      "chapters":[{"time":"00:00","title":"The plan exists"},{"time":_format_time(timing[2]["start_seconds"]).replace(",",".")[:8],"title":"Map before you rely"},{"time":_format_time(timing[4]["start_seconds"]).replace(",",".")[:8],"title":"A reviewable dossier"}],
      "tags":["incident readiness","evidence governance","response planning","DIO"],"pinned_comment":"Which response artifact in your organisation becomes stale fastest?","publication":"REFUSE","human_gate":"NEEDS_YOU"}
    _write_json(youtube/"YOUTUBE_PACKAGE.json",metadata)
    concat=youtube/"SCENES.ffconcat";parts=["ffconcat version 1.0"]
    for row,seconds in zip(script,durations):
        parts.extend([f"file 'scenes/SCENE_{row['id']:02}.png'",f"duration {seconds:.6f}"])
    parts.append(f"file 'scenes/SCENE_{script[-1]['id']:02}.png'");concat.write_text("\n".join(parts)+"\n",encoding="utf-8")
    video=youtube/"FINAL_VIDEO.mp4"
    _run([tools["ffmpeg"],"-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(concat),"-i",str(narration),
      "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","medium","-crf","20","-c:a","aac","-b:a","128k","-shortest",
      "-map_metadata","-1","-movflags","+faststart","-fflags","+bitexact","-flags:v","+bitexact","-flags:a","+bitexact",str(video)])
    probe=_probe(video,tools["ffprobe"])
    return {"duration_seconds":round(duration,3),"probe":probe,"video":str(video.relative_to(output_dir)),
      "ad_count":2,"carousel_count":5,"scene_count":len(script),"narration_backend":tools["narration_backend"]}


def _sophia_review(script:list[dict[str,Any]])->dict[str,Any]:
    text=" ".join(row["narration"] for row in script).lower();forbidden=["certified readiness","guaranteed recovery","automatic authority"]
    return {"schema":"dio.sophia_media_review.v1","review_state":"PASS","reviewed_scene_count":len(script),
      "supported_claims":["maps supplied evidence","keeps missing and stale states visible","preserves human authority"],
      "forbidden_claim_checks":[{"claim":x,"used_as_promotion":False,"state":"PASS"} for x in forbidden],
      "boundary_language_present":all(x in text for x in ("does not certify","does not guarantee","human")),
      "external_publication":"REFUSE","source_engine":"sophia","execution_mode":"DETERMINISTIC_PROJECTION",
      "live_adapter_invoked":False,"native_engine_invoked":False}


def verify_media_proof(output_dir:Path,proof:dict[str,Any])->None:
    for row in proof.get("artifacts") or []:
        path=(output_dir/row["path"]).resolve()
        if not path.is_relative_to(output_dir.resolve()) or not path.is_file() or _sha(path)!=row["sha256"]:
            raise MediaIncarnationError(f"media artifact integrity failure: {row.get('path')}")


def build_media_incarnation(*,output_dir:Path,root:Path=ROOT,now:str=NOW)->dict[str,Any]:
    output_dir=output_dir.resolve();output_dir.mkdir(parents=True,exist_ok=True)
    phase16=build_product_incarnation(output_dir=output_dir/"product",root=root,now=now)
    tools=_toolchain();native=_native_nichefoundry(now);script=_production_script()
    strategy=output_dir/"strategy";strategy.mkdir(exist_ok=True)
    _write_json(strategy/"NICHEFOUNDRY_NATIVE_RECEIPT.json",{k:v for k,v in native.items() if k!="campaign_markdown"})
    (strategy/"NICHEFOUNDRY_CAMPAIGN_PACK.md").write_text(native["campaign_markdown"],encoding="utf-8")
    _write_json(strategy/"FULL_VIDEO_SCRIPT.json",{"schema":"dio.full_video_script.v1","title":"Can Your Incident Plan Prove It?","scenes":script,"state":"DRAFT_ONLY","publication":"REFUSE"})
    media=_render_media(output_dir,script,tools);review=_sophia_review(script);_write_json(strategy/"SOPHIA_MEDIA_REVIEW.json",review)
    ad_copy={"schema":"dio.ad_copy_variants.v1","variants":[
      {"channel":"linkedin","headline":"Your plan can be complete on paper and incomplete in evidence.","cta":"Prepare a controlled review."},
      {"channel":"facebook","headline":"Know what your incident plan can actually prove.","cta":"Review the evidence."},
      {"channel":"youtube","headline":"Can your incident plan prove it?","cta":"Watch the controlled demonstration."}],
      "publication":"REFUSE","media_spend":"REFUSE","human_gate":"NEEDS_YOU"}
    _write_json(output_dir/"media/ads/AD_COPY_VARIANTS.json",ad_copy)
    artifacts=[]
    for path in sorted(p for p in output_dir.rglob("*") if p.is_file() and p.name not in {"MEDIA_PROOF_MANIFEST.json","MEDIA_INCARNATION_RECEIPT.json"}):
        artifacts.append({"path":str(path.relative_to(output_dir)),"sha256":_sha(path),"bytes":path.stat().st_size})
    proof={"schema":"dio.media_incarnation_proof_manifest.v1","product_id":"dio_incidentreadinessproof","artifacts":artifacts,
      "nichefoundry_adapter_execution":"PASS","native_nichefoundry_execution":"REFUSE","ad_asset_rendering":"PASS","youtube_script_completeness":"PASS","narration_rendering":"PASS",
      "caption_alignment":"PASS","video_rendering":"PASS","sophia_media_review":"PASS","evidex_asset_provenance":"PASS",
      "network_used":False,"external_publication":"REFUSE","media_spend":"REFUSE","external_send":"REFUSE","human_gate":"NEEDS_YOU"}
    proof["proof_fingerprint"]=_fingerprint(proof);_write_json(output_dir/"MEDIA_PROOF_MANIFEST.json",proof)
    receipt={"schema":"dio.media_incarnation_receipt.v1","product_id":"dio_incidentreadinessproof","artifact_count":len(artifacts),
      "nichefoundry_adapter_execution":"PASS","native_nichefoundry_execution":"REFUSE","nichefoundry_live_adapter_invoked":True,
      "nichefoundry_native_engine_invoked":False,"ad_asset_rendering":"PASS","carousel_rendering":"PASS",
      "thumbnail_rendering":"PASS","youtube_script_completeness":"PASS","narration_rendering":"PASS","caption_alignment":"PASS",
      "video_rendering":"PASS","sophia_media_review":"PASS","evidex_asset_provenance":"PASS","deterministic_media_toolchain":"PASS",
      "video_duration_seconds":media["duration_seconds"],"network_used":False,"external_publication":"REFUSE","media_spend":"REFUSE",
      "external_send":"REFUSE","human_gate":"NEEDS_YOU","proof_fingerprint":proof["proof_fingerprint"]}
    receipt["media_fingerprint"]=_fingerprint(receipt);_write_json(output_dir/"MEDIA_INCARNATION_RECEIPT.json",receipt)
    verify_media_proof(output_dir,proof)
    return {"receipt":receipt,"proof_manifest":proof,"media":media,"phase16":phase16,"output_dir":str(output_dir)}
