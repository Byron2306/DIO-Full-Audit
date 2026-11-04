#!/usr/bin/env python3
"""Non-destructive Vesper blink+talk and illustrated Dicere debut builder.

Stage five ORIGINAL Dicere-appropriate Pictora backgrounds named scene_01..05
in --backgrounds. The program never silently rebrands Sonoris or HOMS assets.

GPU-free: OpenCV, NumPy, Pillow and FFmpeg. It refuses to overwrite outputs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE = Path('/data/byron/lilith-local/vesper-github-lipsync')
DIO = Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit')
SPEECH = BASE / 'results/dicere/v15/DICERE_DEBUT_VERA_MUSETALK.mp4'
EYES = BASE / 'motion-tests/VESPER_CANONICAL_RGB--vesper_two_blinks_8s.mp4'
MUSIC = DIO / 'media/product_asset_packs/dio_creative_organs_site_matched_v2/receipts/SONORIS_DARKSYNTH_AMBIENT_V2_45S.wav'
NARRATION = DIO / 'media/dicere/debut/dicere_vera_narration.wav'
CAPTIONS = DIO / 'media/dicere/debut/DICERE_DEBUT_EXPLAINER_V42.ass'
SCENES = [
    ('DICERE', 'A story with a voice, a face, and a score', 'DIO CREATIVE ORGANS / LOCAL AV PRODUCTION'),
    ('01   SHAPE THE MESSAGE', 'Begin with a script. Give every scene a purpose.', 'Narration, pacing, captions, and visual direction'),
    ('02   SONORIS', 'An original score for every scene', 'Composition in service of the story'),
    ('03   VESPER, IN MOTION', 'Natural speech. Living presence.', 'Matched lips and natural blinking'),
    ('DICERE / READY FOR REVIEW', 'Voice. Motion. Music. Visual design.', 'Local production / Human review required'),
]
FPS = 25
FULL_SECONDS = 45
BLINK_CENTERS = (2.2, 5.9)
# Irregular event timestamps; the source's blink behavior is sampled in a narrow
# window around its measured blink centers rather than looping an 8-second clip.
EVENTS = (2.2, 5.9, 10.1, 14.3, 17.6, 22.4, 26.0, 30.8, 34.9, 40.0, 43.3)


def refuse(message: str):
    raise SystemExit('REFUSE: ' + message)


def require_file(p: Path):
    if not p.is_file() or p.stat().st_size == 0:
        refuse(f'MISSING_SOURCE: {p}')


def sha(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def ffprobe(path: Path):
    result = subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)], text=True)
    return json.loads(result)


def eye_mask(width, height):
    if (width, height) != (1254, 1254):
        refuse(f'EYE_MASK_COORDS_UNCALIBRATED_FOR_{width}x{height}')
    mask = np.zeros((height, width), dtype=np.float32)
    for cx,cy,rx,ry in ((510,430,80,46),(667,410,83,46)):
        layer = np.zeros_like(mask)
        cv2.ellipse(layer, (cx,cy), (rx,ry),0,0,360,1.0,-1)
        layer = cv2.GaussianBlur(layer,(0,0),15,15)
        mask = np.maximum(mask,layer)
    return mask[:,:,None]


def open_video(path):
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): refuse('VIDEO_OPEN_FAILED: '+str(path))
    return cap


def read_source_frame(cap, idx, name):
    cap.set(cv2.CAP_PROP_POS_FRAMES,idx)
    ok,frame=cap.read()
    if not ok: refuse(f'{name}_FRAME_READ_FAILED_{idx}')
    return frame


def build_face(out: Path, seconds: float):
    speech=open_video(SPEECH)
    eyes=open_video(EYES)
    face_path=out/'VESPER_V3_FACE_SILENT.mp4'
    if face_path.exists(): refuse(f'OUTPUT_EXISTS: {face_path}')
    try:
        dims=[]
        for name,cap in (('SPEECH',speech),('EYES',eyes)):
            w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps=cap.get(cv2.CAP_PROP_FPS); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if (w,h)!=(1254,1254) or abs(fps-FPS)>0.01: refuse(f'{name}_FORMAT_MISMATCH: {w}x{h}@{fps}')
            dims.append(count)
        total=min(int(round(seconds*FPS)), int(FULL_SECONDS*FPS))
        if dims[0] < 900 or dims[1] < 195: refuse(f'SOURCE_TOO_SHORT: {dims}')
        mask=eye_mask(1254,1254)
        # Preload 0.36 seconds each side of both blink centers, with short
        # temporal fades at their edges. The rest remains original MuseTalk.
        half=0.36
        windows=[]
        for source_t in BLINK_CENTERS:
            start=max(0,round((source_t-half)*FPS))
            end=min(dims[1]-1,round((source_t+half)*FPS))
            windows.append([read_source_frame(eyes,j,'EYES') for j in range(start,end+1)])
        writer=cv2.VideoWriter(str(face_path),cv2.VideoWriter_fourcc(*'mp4v'),FPS,(1254,1254))
        if not writer.isOpened(): refuse('FACE_VIDEO_WRITER_FAILED')
        count=0
        last_speech=None
        try:
            for i in range(total):
                if i<dims[0]:
                    ok,frame=speech.read()
                    if not ok: refuse(f'SPEECH_FRAME_READ_FAILED_{i}')
                    last_speech=frame
                else:
                    if last_speech is None: refuse('NO_SPEECH_FRAMES')
                    frame=last_speech.copy()  # Closing segment: silent held face + occasional blinks
                t=i/FPS
                nearest=min(EVENTS,key=lambda e:abs(t-e))
                dt=t-nearest
                if abs(dt)<=half:
                    src_i=0 if EVENTS.index(nearest)%2==0 else 1
                    frames=windows[src_i]
                    k=min(len(frames)-1,max(0,round((dt+half)*FPS)))
                    # Ease spatial blend in/out over 0.1s, avoiding flicker at boundaries.
                    edge=(half-abs(dt))/0.10
                    alpha=max(0.0,min(1.0,edge))
                    effective_mask=mask*alpha
                    frame=np.clip(frame.astype(np.float32)*(1-effective_mask)+frames[k].astype(np.float32)*effective_mask,0,255).astype(np.uint8)
                writer.write(frame)
                count+=1
        finally:
            writer.release()
        if count!=total: refuse('FACE_FRAME_COUNT_MISMATCH')
        return face_path, count
    finally:
        speech.release(); eyes.release()


def get_font(size, bold=False):
    path=('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
          else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    return ImageFont.truetype(path,size)


def find_background(folder: Path, index: int):
    for ext in ('.png','.jpg','.jpeg','.webp'):
        p=folder/f'scene_{index:02d}{ext}'
        if p.is_file(): return p
    refuse(f'MISSING_PICTORA_BACKGROUND_scene_{index:02d} IN {folder}')


def draw_wrapped(d, text, origin, font, max_width, fill, spacing=12):
    lines=[]; current=''
    for word in text.split():
        candidate=(current+' '+word).strip()
        if current and d.textbbox((0,0),candidate,font=font)[2]>max_width:
            lines.append(current); current=word
        else: current=candidate
    if current: lines.append(current)
    x,y=origin
    for line in lines:
        d.text((x,y),line,font=font,fill=fill,stroke_width=1,stroke_fill='#090909')
        y+=font.size+spacing


def build_scenes(out, folder):
    files=[]
    for i,(heading,title,copy) in enumerate(SCENES,1):
        src=find_background(folder,i)
        files.append(src)
        image=ImageOps.fit(Image.open(src).convert('RGB'),(1920,1080),method=Image.Resampling.LANCZOS)
        # Keep imported artwork visible. Darken left typography panel only.
        veil=Image.new('RGBA',(1920,1080),(0,0,0,0))
        vd=ImageDraw.Draw(veil)
        vd.rounded_rectangle((60,65,1160,555),radius=28,fill=(7,8,11,185),outline=(195,151,51,190),width=2)
        image=Image.alpha_composite(image.convert('RGBA'),veil)
        d=ImageDraw.Draw(image)
        d.text((112,113),heading,font=get_font(35,True),fill='#FFD700')
        draw_wrapped(d,title,(112,215),get_font(49,True),990,'#FFE082',18)
        draw_wrapped(d,copy,(112,405),get_font(24),970,'#FFF0C2',8)
        dst=out/f'DICERE_SCENE_{i:02d}.png'
        if dst.exists(): refuse(f'OUTPUT_EXISTS: {dst}')
        image.convert('RGB').save(dst)
    return files


def build_final(out, face, duration, captions):
    final=out/'DICERE_DEBUT_V3_REVIEW.mp4'
    if final.exists(): refuse('OUTPUT_EXISTS: '+str(final))
    if duration<44.99: refuse('FINAL_REQUIRES_45S_FACE')
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n']
    for i in range(1,6):
        cmd+=['-loop','1','-framerate','25','-t','9','-i',str(out/f'DICERE_SCENE_{i:02d}.png')]
    cmd+=['-i',str(face),'-i',str(NARRATION),'-i',str(MUSIC)]
    graph=(
        ''.join(f'[{i}:v]fps=25,scale=1920:1080,setsar=1[v{i}];' for i in range(5))+
        '[v0][v1][v2][v3][v4]concat=n=5:v=1:a=0[bg];'
        '[5:v]scale=480:480:flags=lanczos,setsar=1[face];'
        '[bg][face]overlay=1320:535:shortest=1:format=auto[video];'
        '[7:a]aresample=48000,volume=0.32,afade=t=out:st=43:d=2[music];'
        '[6:a]aresample=48000,volume=1.0,afade=t=out:st=36.5:d=0.7[voice];'
        '[music][voice]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]'
    )
    # Existing V42 ASS was designed for an entirely different layout.
    # Deliberately omit it rather than silently putting text over the face.
    cmd+=['-filter_complex',graph,'-map','[video]','-map','[a]','-t','45',
          '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
          '-c:a','aac','-b:a','192k','-movflags','+faststart',str(final)]
    subprocess.run(cmd,check=True)
    return final


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--backgrounds',type=Path,help='Directory with scene_01..05 original Pictora images')
    p.add_argument('--output',type=Path,default=DIO/'media/dicere/debut/v3-repair')
    p.add_argument('--proof-only',action='store_true',help='5-second eye+speech proof, no backgrounds')
    a=p.parse_args()
    out=a.output.resolve()
    if out.exists() and any(out.iterdir()): refuse(f'OUTPUT_DIRECTORY_NOT_EMPTY: {out}')
    require_file(SPEECH); require_file(EYES)
    if not a.proof_only:
        require_file(MUSIC); require_file(NARRATION)
        if not a.backgrounds: refuse('--backgrounds REQUIRED FOR FULL DEBUT')
        for i in range(1,6): require_file(find_background(a.backgrounds,i))
    # Avoid creating anything until source preflight succeeds.
    out.mkdir(parents=True,exist_ok=True)
    seconds=5 if a.proof_only else 45
    face, frames=build_face(out,seconds)
    output=face
    backgrounds=[]
    if a.proof_only:
        proof=out/'VESPER_V3_5S_BLINK_TALK.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
                        '-i',str(face),'-i',str(SPEECH),'-map','0:v:0','-map','1:a:0',
                        '-t','5','-c:v','libx264','-preset','fast','-crf','20',
                        '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(proof)],
                       check=True)
        output=proof
    if not a.proof_only:
        backgrounds=build_scenes(out,a.backgrounds)
        output=build_final(out,face,seconds,CAPTIONS)
    receipt={
      'schema':'dio.dicere.v3_repair.v1', 'state':'AWAITING_HUMAN_VISUAL_REVIEW',
      'publication_authorized':False,'output':str(output),'sha256':sha(output),
      'frames':frames,'fps':FPS,'duration_target_seconds':seconds,
      'speech':{'path':str(SPEECH),'sha256':sha(SPEECH)},
      'eyes':{'path':str(EYES),'sha256':sha(EYES)},
      'blink_events_s':[x for x in EVENTS if x<=seconds],
      'backgrounds':[{'path':str(b),'sha256':sha(b)} for b in backgrounds],
      'music':str(MUSIC) if backgrounds else None,
      'notes':['Original MuseTalk drives all non-eye pixels and preserves timing',
               'LivePortrait eye-only windows blend around irregular blink events',
               'Closing segment holds the final speaking face with additional eye motion',
               'Opaque presenter viewport is intentional; source has no alpha matting',
               'Scene image backgrounds must be supplied and visually approved',
               'Text captions intentionally omitted pending safe-area redesign']}
    (out/'V3_REPAIR_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'state':receipt['state'],'output':str(output),'receipt':str(out/'V3_REPAIR_RECEIPT.json')},indent=2))

if __name__=='__main__': main()
