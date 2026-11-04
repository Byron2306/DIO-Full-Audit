#!/usr/bin/env python3
"""Build a local, review-ready Dicere debut film from owned creative assets.

The renderer stays local: no publishing, account access, or external calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "media/dicere/debut"
PACK = ROOT / "media/product_asset_packs/dio_creative_organs_site_matched_v2"
VESPER = Path("/data/byron/lilith-local/vesper-github-lipsync")
PRESENCE = VESPER / "motion-tests/VESPER_CANONICAL_RGB--vesper_living_presence_v2_12s.mp4"
BLINKS = VESPER / "motion-tests/VESPER_CANONICAL_RGB--vesper_two_blinks_8s.mp4"
MUSETALK = VESPER / "results/dicere/v15/DICERE_DEBUT_VERA_MUSETALK.mp4"
GOLD_PANEL = ROOT / "media/product_asset_packs/homs_corpo_cult_v1/vesper/DIO_VESPER_MARKET_PANEL.png"
MUSIC = PACK / "receipts/SONORIS_DARKSYNTH_AMBIENT_V2_45S.wav"
NARRATION = OUT / "dicere_vera_narration.wav"
NARRATION_TEXT = ("Welcome to DIO. I'm Vesper, your guide to the creative organs. "
    "Dicere brings voice, motion, music and visual design together in one audiovisual story. "
    "Start with a script. Shape the scene around your message. I appear on screen with natural speech and subtle movement, "
    "while Sonoris composes an original score for the mood and pace. Gold visual assets frame the story, and the final cut "
    "carries its own captions, timing and production receipt. Every element stays local, editable and ready for your review. "
    "This is Dicere: give your idea a voice, a face and a score.")
SCENES = [
    ("DICERE", "A story with a voice, a face, and a score", "DIO CREATIVE ORGANS  /  LOCAL AV PRODUCTION"),
    ("01   SHAPE THE MESSAGE", "Begin with a script. Give every scene a purpose.", "Narration, pacing, captions, and visual direction in one timeline."),
    ("02   A SCORE THAT SERVES THE STORY", "Sonoris composes for mood,\nmovement, and pace.", "Original 45-second darksynth score from Sonoris."),
    ("03   VESPER, IN MOTION", "Natural speech and\nliving presence.", "Matched MuseTalk lip-sync.\nVesper’s blink performance."),
    ("DICERE  /  READY FOR REVIEW", "Voice. Motion. Music. Visual design.", "A local, editable audiovisual story  •  Human review required"),
]

# A unified, high-contrast gold palette: saturated gold for labels, lighter gold
# for display text, and a warm readable gold for supporting copy.
GOLD = (255, 215, 0)        # #FFD700
GOLD_LIGHT = (255, 224, 130) # #FFE082
GOLD_BODY = (255, 213, 79)   # #FFD54F

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()

def font(size: int, bold=False, serif=False):
    if serif:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
    else:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)

def draw_headline(draw, xy, text, font_obj, fill, tracking=0.8, line_gap=23):
    x0, y0 = xy
    for line in text.splitlines():
        x = x0
        for character in line:
            draw.text((x, y0), character, font=font_obj, fill=fill, stroke_width=0)
            x += draw.textlength(character, font=font_obj) + tracking
        y0 += font_obj.size + line_gap

def make_cards():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = [p for p in sorted((PACK/"assets").glob("*")) if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    for i,(title,headline,sub) in enumerate(SCENES):
        im=Image.new("RGB",(1920,1080),(7,8,11)); d=ImageDraw.Draw(im)
        # Black and gold framing, with gentle motion supplied by live video and scene cuts.
        for x in range(1920):
            fade=max(0,1-abs(x-1500)/1100)
            c=int(8+13*fade); im.paste((c,c,int(c*1.05)),(x,0,x+1,1080))
        d=ImageDraw.Draw(im)
        d.rectangle((70,68,1850,1010),outline=(184,135,38),width=2)
        d.rectangle((91,89,1829,989),outline=(69,55,27),width=1)
        d.text((135,140),"DIO   /   CREATIVE ORGANS",font=font(25,True),fill=GOLD)
        d.line((135,190,1780,190),fill=(145,105,28),width=2)
        d.text((135,260),title,font=font(32,True),fill=GOLD_LIGHT)
        headline_font = font(44,True,serif=True)
        headline_y = 340
        draw_headline(d,(135,headline_y),headline,headline_font,fill=GOLD_LIGHT,tracking=0.25,line_gap=21)
        # Keep a consistent, deliberate gap after one or multiple headline lines.
        headline_bottom = headline_y + len(headline.splitlines()) * (headline_font.size + 21)
        sub_y = headline_bottom + 38
        sub_position=(1240,625) if i==3 else (135,sub_y)
        d.multiline_text(sub_position,sub,font=font(26 if i==3 else 30),fill=GOLD_BODY,spacing=12)
        # The asset gallery scene uses the supplied gold identity marks, not approximations.
        if i==2:
            thumbs=assets
            for j,p in enumerate(thumbs):
                try:
                    a=Image.open(p).convert("RGBA"); a.thumbnail((118,118))
                    x=1120+(j%5)*132; y=240+(j//5)*128
                    im.paste(a,(x,y),a)
                except Exception: pass
        if i==3 and GOLD_PANEL.is_file():
            a=Image.open(GOLD_PANEL).convert("RGB"); a.thumbnail((540,304))
            im.paste(a,(1240,255))
            d=ImageDraw.Draw(im); d.rectangle((1238,253,1784,561),outline=(197,160,91),width=2)
        # Reserve the lower third for subtitles and keep the scene marker clear.
        marker=f"DICERE  /  {i+1:02d}"
        marker_font=font(20,True)
        d.text((1780-d.textlength(marker,font=marker_font),140),marker,font=marker_font,fill=GOLD)
        im.save(OUT/f"scene_{i+1:02d}.png",quality=95)

def make_captions(caption_path: Path):
    cues=[
        (0.8,4.2,"Welcome to DIO. I'm Vesper,\nyour guide to the creative organs."),
        (4.3,9.0,"Dicere brings voice, motion, music\nand visual design in one story."),
        (9.1,12.3,"Start with a script. Shape the scene\naround your message."),
        (12.4,18.4,"I speak with natural movement, while\nSonoris composes an original score\nfor the mood and pace."),
        (18.5,25.2,"Gold visual assets frame the story.\nThe final cut includes captions, timing,\nand its own production receipt."),
        (25.3,31.7,"Every element stays local, editable and\nready for your review."),
        (31.8,37.5,"This is Dicere: give your idea a voice,\na face and a score."),
    ]
    def stamp(s):
        ms=round(s*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); sec,ms=divmod(ms,1000)
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"
    caption_path.write_text("\n\n".join(f"{n}\n{stamp(a)} --> {stamp(b)}\n{t}" for n,(a,b,t) in enumerate(cues,1))+"\n",encoding="utf-8")

def make_ass_captions(caption_path: Path, ass_path: Path):
    blocks=caption_path.read_text(encoding="utf-8").strip().split("\n\n")
    # ASS colors are AABBGGRR. Keep captions in the same saturated gold as
    # scene labels, with more breathing room and a left edge just beyond Vesper.
    lines=["[Script Info]","ScriptType: v4.00+","WrapStyle: 2","ScaledBorderAndShadow: yes","PlayResX: 1920","PlayResY: 1080","","[V4+ Styles]","Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding","Style: GoldCaptions,Nimbus Sans,38,&H0000D7FF,&H0000D7FF,&H00100A02,&H80080808,-1,0,0,0,100,100,0.8,0,1,3.4,1.4,1,590,110,145,1","","[Events]","Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for block in blocks:
        parts=block.splitlines()
        if len(parts)<3: continue
        start,end=(x.strip().replace(",",".") for x in parts[1].split("-->"))
        start=start[:8]+"."+start[9:12][:2]
        end=end[:8]+"."+end[9:12][:2]
        text="\\N".join(part.replace("{","\\{").replace("}","\\}") for part in parts[2:])
        lines.append(f"Dialogue: 0,{start},{end},GoldCaptions,,0,0,0,,{text}")
    ass_path.write_text("\n".join(lines)+"\n",encoding="utf-8")

def make_narration():
    if NARRATION.exists() and NARRATION.stat().st_size:
        return
    req=urllib.request.Request("http://127.0.0.1:8000/tts",data=urllib.parse.urlencode({"text":NARRATION_TEXT,"voice_url":"vera"}).encode(),headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req,timeout=300) as response:
        NARRATION.write_bytes(response.read())

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,default=OUT/"DICERE_DEBUT_EXPLAINER_V1.mp4"); args=parser.parse_args()
    output=args.output.resolve()
    if output.exists(): raise SystemExit(f"Output exists; choose a new filename: {output}")
    required=[PRESENCE,BLINKS,MUSIC,GOLD_PANEL,MUSETALK]
    missing=[str(p) for p in required if not p.is_file()]
    if missing: raise SystemExit("Missing required local media: "+", ".join(missing))
    caption_path=output.with_suffix(".srt")
    ass_caption_path=output.with_suffix(".ass")
    make_narration(); make_cards(); make_captions(caption_path); make_ass_captions(caption_path,ass_caption_path)
    # Build five nine-second scenes; overlay continuous presence, then the dedicated blink performance.
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y"]
    for i in range(1,6): cmd += ["-loop","1","-t","9","-i",str(OUT/f"scene_{i:02d}.png")]
    cmd += ["-stream_loop","-1","-i",str(PRESENCE),"-stream_loop","-1","-i",str(BLINKS),"-i",str(NARRATION),"-i",str(MUSIC),"-i",str(MUSETALK)]
    filt=("[0:v]scale=1920:1080,setsar=1,fps=30[v0];[1:v]scale=1920:1080,setsar=1,fps=30[v1];"
          "[2:v]scale=1920:1080,setsar=1,fps=30[v2];[3:v]scale=1920:1080,setsar=1,fps=30[v3];"
          "[4:v]scale=1920:1080,setsar=1,fps=30[v4];[v0][v1][v2][v3][v4]concat=n=5:v=1:a=0[bg];"
          "[6:v]scale=400:400:force_original_aspect_ratio=decrease,pad=400:400:(ow-iw)/2:(oh-ih)/2:color=0x07080b,fps=30,trim=duration=8,setpts=PTS-STARTPTS+37.32/TB[blink];"
          "[9:v]scale=400:400:force_original_aspect_ratio=decrease,pad=400:400:(ow-iw)/2:(oh-ih)/2:color=0x07080b,fps=30,trim=duration=37.8,setpts=PTS-STARTPTS[lip];"
          "[bg][lip]overlay=145:590:enable='lt(t,37)':eof_action=pass[base];"
          "[base][blink]overlay=145:590:eof_action=pass,subtitles='"+str(ass_caption_path.resolve())+"'[v];"
          "[8:a]aresample=48000,volume=1.0,afade=t=out:st=43:d=2[m];"
          "[7:a]aresample=48000,volume=1.0,afade=t=in:st=0:d=0.25,afade=t=out:st=37:d=0.8[voice];"
          "[m][voice]amix=inputs=2:duration=longest:weights='0.34 1.0':normalize=0,alimiter=limit=0.95[a]")
    cmd += ["-filter_complex",filt,"-map","[v]","-map","[a]","-t","45","-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart",str(output)]
    output.parent.mkdir(parents=True,exist_ok=True); subprocess.run(cmd,check=True,timeout=1200)
    old_musetalk = VESPER / "results/v15/VESPER_VERA_V15_SPEECH.mp4"
    source_files=[PRESENCE,BLINKS,MUSIC,NARRATION,GOLD_PANEL,MUSETALK,old_musetalk,*sorted((PACK/"assets").glob("*"))]
    manifest={"schema":"dio.dicere.debut.production_receipt.v1","created_utc":datetime.now(timezone.utc).isoformat(),"organ_id":"dicere","state":"LOCAL_REVIEW_CANDIDATE","publication_authorized":False,"human_review_required":True,"release_authorized":False,"output":{"path":str(output),"sha256":digest(output),"bytes":output.stat().st_size,"duration_seconds":45,"resolution":"1920x1080","video_codec":"h264","audio_codec":"aac"},"narration":{"path":str(NARRATION),"sha256":digest(NARRATION),"text":NARRATION_TEXT,"caption_file":str(caption_path),"styled_caption_file":str(ass_caption_path),"caption_style":{"font":"Nimbus Sans Bold","font_size":38,"primary_color":"#FFD700 (saturated visible gold)","letter_spacing":0.8,"line_spacing":"expanded caption leading","outline_width":3.4,"shadow_width":1.4,"bottom_margin":145,"safe_area_left":590,"safe_area_right":110,"alignment":"left"}},"music":{"path":str(MUSIC),"sha256":digest(MUSIC),"source_organ":"sonoris"},"vesper":{"musetalk_speech_source":{"path":str(MUSETALK),"sha256":digest(MUSETALK),"used_in_cut":True,"matched_narration_sha256":digest(NARRATION),"role":"lip-synced presenter for narrated section"},"prior_musetalk_reference":{"path":str(old_musetalk),"sha256":digest(old_musetalk) if old_musetalk.is_file() else None,"used_in_cut":False,"reason":"Earlier 7.88-second speech source has different, unverified dialogue."},"continuous_presence_source":str(PRESENCE),"blink_performance_source":str(BLINKS),"blink_overlay_window_seconds":[37.32,45]},"gold_assets":[{"path":str(p),"sha256":digest(p)} for p in source_files if p.is_file()],"revision_notes":["Unified headings, supporting copy, and captions into a high-contrast gold palette (#FFD700, #FFE082, #FFD54F).","Expanded caption size and tracking, adjusted the subtitle safe area to sit closer to Vesper without overlap, and added clearer line separation.","Kept the display type scale and deliberate headline-to-supporting-copy gap consistent across scenes."],"execution_scope":"local rendering only; no external transmission"}
    receipt_path=output.with_suffix(".receipt.json")
    receipt_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    provenance_path=PACK/"receipts/POCKET_TTS_NARRATION_RECEIPT_V2.json"
    provenance=json.loads(provenance_path.read_text(encoding="utf-8"))
    voice_receipt={"schema":"dio.pocket_tts.narration_receipt.v1","backend":"pocket_tts","profile_id":"vera_pocket_public","voice_url":"vera","endpoint":"http://127.0.0.1:8000/tts","audio_path":str(NARRATION),"audio_sha256":digest(NARRATION),"narration_text":NARRATION_TEXT,"model_provenance":provenance.get("model_provenance"),"provenance_reference":str(provenance_path),"provenance_reference_sha256":digest(provenance_path),"remote_processing":False,"release_authorized":False}
    (OUT/"DICERE_NARRATION_RECEIPT.json").write_text(json.dumps(voice_receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(output),"bytes":output.stat().st_size,"sha256":manifest["output"]["sha256"],"receipt":str(receipt_path)}))

if __name__=="__main__": main()
