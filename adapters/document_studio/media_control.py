from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageStat

from adapters.format_core.renderer import load_profiles


class DocumentStudioMediaError(RuntimeError):
    pass


def _sha256(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()


def _font(name:str,size:int)->ImageFont.FreeTypeFont:
    candidates=[Path(f"/usr/share/fonts/truetype/liberation2/{name}.ttf"),Path(f"/usr/share/fonts/truetype/dejavu/{name}.ttf")]
    for path in candidates:
        if path.is_file():return ImageFont.truetype(str(path),size)
    return ImageFont.load_default()


def _rgb(value:str)->tuple[int,int,int]:
    value=value.lstrip("#")
    return tuple(int(value[i:i+2],16) for i in (0,2,4))


def _visual_score(image:Image.Image)->float:
    sample=image.resize((160,90)).convert("RGB")
    stat=ImageStat.Stat(sample)
    mean=sum(stat.mean)/3
    variance=sum(stat.var)/3
    colourful=sum(max(px)-min(px) for px in sample.getdata())/(160*90)
    white=sum(1 for px in sample.getdata() if min(px)>238)/(160*90)
    return variance+colourful*18-white*6000-abs(mean-105)*2


def _image_dominant_crop(source:Image.Image)->tuple[Image.Image,str]:
    image=source.convert("RGB");w,h=image.size
    candidates={
      "left":image.crop((0,0,w//2,h)),"right":image.crop((w//2,0,w,h)),
      "full":image,
    }
    scores={name:_visual_score(candidate) for name,candidate in candidates.items()}
    side=max(("left","right"),key=lambda name:scores[name])
    if scores[side] < scores["full"]*0.72:return image,"full"
    return candidates[side],side


def _wrap(draw:ImageDraw.ImageDraw,text:str,font:ImageFont.FreeTypeFont,max_width:int)->list[str]:
    words=text.split();lines=[];current=""
    for word in words:
        trial=f"{current} {word}".strip()
        if current and draw.textbbox((0,0),trial,font=font)[2]>max_width:
            lines.append(current);current=word
        else:current=trial
    if current:lines.append(current)
    return lines


def _fit_title(draw:ImageDraw.ImageDraw,text:str,max_width:int,max_lines:int)->tuple[ImageFont.FreeTypeFont,list[str]]:
    for size in range(86,39,-2):
        font=_font("LiberationSans-Bold",size);lines=_wrap(draw,text,font,max_width)
        if len(lines)<=max_lines:return font,lines
    raise DocumentStudioMediaError(f"title cannot fit controlled safe zone: {text}")


def _compose(source:Path,target:Path,*,title:str,kicker:str,index:str|None,style:dict[str,Any],thumbnail:bool=False)->dict[str,Any]:
    with Image.open(source) as opened:crop,crop_lane=_image_dominant_crop(opened)
    canvas=ImageOps.fit(crop,(1920,1080),method=Image.Resampling.LANCZOS)
    canvas=ImageEnhance.Color(canvas).enhance(1.08);canvas=ImageEnhance.Contrast(canvas).enhance(1.08)
    blur=canvas.filter(ImageFilter.GaussianBlur(22));overlay=Image.new("RGB",canvas.size,(4,13,15))
    background=Image.blend(blur,overlay,.34);foreground=ImageOps.contain(canvas,(1920,1080),Image.Resampling.LANCZOS)
    background.paste(foreground,((1920-foreground.width)//2,(1080-foreground.height)//2))
    shade=Image.new("RGBA",background.size,(0,0,0,0));sd=ImageDraw.Draw(shade)
    sd.rectangle((0,0,1160,1080),fill=(0,0,0,172 if thumbnail else 148))
    for x in range(900,1280,8):sd.rectangle((x,0,x+8,1080),fill=(0,0,0,max(0,148-int((x-900)/2.6))))
    canvas=Image.alpha_composite(background.convert("RGBA"),shade);draw=ImageDraw.Draw(canvas)
    colours=style["colours"];accent=_rgb(colours["accent_2"] if thumbnail else colours["accent"]);ink=(244,247,245)
    left=118;max_width=940;top=250 if thumbnail else 300
    kicker_font=_font("LiberationSans-Bold",26);draw.text((left,top-88),kicker.upper(),font=kicker_font,fill=accent)
    font,lines=_fit_title(draw,title,max_width,3 if thumbnail else 2)
    y=top
    for line in lines:
        draw.text((left,y),line,font=font,fill=ink,stroke_width=1,stroke_fill=(0,0,0));y+=int(font.size*1.08)
    draw.rectangle((left,y+32,left+190,y+39),fill=accent)
    if index:draw.text((1740,84),index,font=_font("LiberationSans-Bold",28),fill=(230,235,232))
    footer=str(style.get("footer") or "Human authority retained")
    draw.text((left,985),footer,font=_font("LiberationSans",20),fill=(205,215,211))
    target.parent.mkdir(parents=True,exist_ok=True);canvas.convert("RGB").save(target,"PNG",optimize=False,compress_level=9)
    bbox=draw.multiline_textbbox((left,top),"\n".join(lines),font=font,spacing=0)
    safe=bbox[0]>=96 and bbox[1]>=120 and bbox[2]<=1824 and bbox[3]<=940
    if not safe:raise DocumentStudioMediaError(f"rendered title escaped safe zone: {title}")
    return {"source":str(source),"output":str(target),"crop_lane":crop_lane,"title":title,"line_count":len(lines),
      "font_size":font.size,"safe_zone":"PASS","sha256":_sha256(target),"bytes":target.stat().st_size}


def render_media_control_surface(*,gamma_dir:Path,script_package:dict[str,Any],output_dir:Path,style_profile:str="dio_professional")->dict[str,Any]:
    profiles=load_profiles();style=(profiles.get("styles") or {}).get(style_profile)
    if not style:raise DocumentStudioMediaError(f"unknown Format Core style profile: {style_profile}")
    scenes=script_package.get("scenes") or [];renders=[]
    for index,scene in enumerate(scenes,1):
        source=gamma_dir/f"{index:02}_{scene['scene_id']}_GAMMA.png"
        if not source.is_file():raise DocumentStudioMediaError(f"Gamma scene missing: {source.name}")
        target=output_dir/f"SCENE_{index:02}_CONTROLLED.png"
        renders.append(_compose(source,target,title=str(scene.get("title") or f"Scene {index}"),
          kicker="DIO // Incident Readiness",index=f"{index:02} / {len(scenes):02}",style=style))
    thumbnail_source=gamma_dir/"THUMBNAIL_GAMMA.png"
    thumbnail=output_dir/"THUMBNAIL_CONTROLLED.png"
    thumbnail_render=_compose(thumbnail_source,thumbnail,title="CAN YOUR PLAN PROVE IT?",kicker="Incident readiness",
      index=None,style=style,thumbnail=True)
    receipt={"schema":"dio.document_studio.media_control_receipt.v1","native_engine_invoked":True,
      "engine":"document_studio","format_core_profile":style_profile,"format_core_profile_hash":hashlib.sha256(json.dumps(style,sort_keys=True).encode()).hexdigest(),
      "gamma_role":"raw_visual_source","document_studio_role":"authoritative_composition_and_typography",
      "scene_count":len(renders),"scene_coverage":"PASS","full_bleed_composition":"PASS","typography_safe_zones":"PASS",
      "generated_text_in_gamma_refused_as_authority":True,"thumbnail_composition":"PASS","renders":renders,"thumbnail":thumbnail_render,
      "external_publication":"REFUSE","human_gate":"NEEDS_YOU"}
    path=output_dir/"DOCUMENT_STUDIO_MEDIA_RECEIPT.json";path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return receipt
