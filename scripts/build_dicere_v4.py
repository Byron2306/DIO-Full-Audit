#!/usr/bin/env python3
"""DICERE V4 / THE GILDED VOICE: offline, non-destructive review production.

Creates an original instrumental score candidate, distinct cinematic scene plates,
and composites the *existing* V3 blink-and-talk face through the human-reviewed
RMBG matte. Never invokes MuseTalk, LivePortrait, or remote services.

Python dependencies: Pillow, NumPy. External: ffmpeg, ffprobe.
All outputs are review-only; music does not assert provenance from Sonoris engine.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, subprocess, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

DIO=Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit')
VESPER=Path('/data/byron/lilith-local/vesper-github-lipsync')
DEFAULT_FACE=DIO/'media/dicere/debut/v3-repair/VESPER_V3_FACE_SILENT.mp4'
DEFAULT_MASK=VESPER/'presence/v3-segmentation-lab/vesper_rmbg_mask.png'
DEFAULT_NARRATION=DIO/'media/dicere/debut/dicere_vera_narration.wav'
DEFAULT_BG=DIO/'media/dicere/backgrounds-v3'
DEFAULT_OUT=DIO/'media/dicere/debut/v4-gilded-voice'
W,H=1920,1080
FPS=25
DURATION=45
PAL={'gold':(221,175,90),'ivory':(246,236,216),'body':(212,204,184),'muted':(143,130,111),'black':(8,10,15)}
SCENES=[
 ('THE GILDED VOICE','A STORY FINDS ITS VOICE','Dicere  /  The art of audiovisual performance','OPENING   •   00:00'),
 ('THE SCRIPT','EVERY WORD HAS A PURPOSE','From idea to rhythm, scene and meaning','STORY   •   00:09'),
 ('THE SCORE','MUSIC MOVES THE STORY','Original composition shaped to the message','SONORIS   •   00:18'),
 ('THE PRESENCE','A VOICE. A FACE. A PRESENCE.','Vesper gives the story a living performance','DICERE   •   00:27'),
 ('THE DEBUT','EVERY ELEMENT, IN HARMONY','Locally produced  /  Human review required','REVIEW   •   00:36')]

def require(path):
 if not path.is_file() or path.stat().st_size==0: raise SystemExit(f'REFUSE_MISSING_SOURCE: {path}')
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def probe(path):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height,r_frame_rate','-of','json',str(path)],text=True))
def font(size,bold=False):
 paths=['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
 return ImageFont.truetype(paths[0 if bold else 1],size)

def score(path):
 """Generate a wholly original, instrumental 45s cinematic-electronic score."""
 sr=32000
 length=45*sr
 rng=np.random.default_rng(1863)
 mix=np.zeros(length,dtype=np.float32)
 # Original harmonic cell in D minor; evolving chord bed, no sampled third-party audio.
 chords=[(50,57,62,65),(46,53,58,62),(43,50,55,58),(48,55,60,64),(50,57,60,65)]
 def add_wave(start,dur,notes,amp,attack=.14,release=.55,texture='pad'):
  n=min(int(sr*dur),length-int(start*sr)); off=int(start*sr)
  if n<=0:return
  t=np.arange(n,dtype=np.float64)/sr
  env=np.minimum(1,t/max(.01,attack))*np.minimum(1,(dur-t)/max(.01,release))
  env=np.maximum(0,env)
  z=np.zeros(n,dtype=np.float64)
  for midi in notes:
   f=440*2**((midi-69)/12)
   phase=2*np.pi*f*t
   if texture=='pad':
    z+=.56*np.sin(phase)+.22*np.sin(phase*1.003+.2)+.09*np.sin(2*phase)
   elif texture=='bell':
    z+=np.sin(phase)*np.exp(-t*3)+.24*np.sin(2.02*phase)*np.exp(-t*5)
   else: z+=np.sin(phase)+.19*np.sin(2*phase)
  z/=max(1,len(notes))
  mix[off:off+n]+=(amp*env*z).astype(np.float32)
 for i,ch in enumerate(chords):
  st=i*9
  add_wave(st,9.5,ch,.23,1.7,1.4)
  add_wave(st,8.5,(ch[0]-12,),.17,.4,1.2,'bass')
  # motif at varied positions and restrained melodic volume
  phrase=[ch[1]+12,ch[2]+12,ch[3]+12,ch[2]+12]
  for j,note in enumerate(phrase):
   add_wave(st+1.0+j*1.55,.7,(note,),.06,.025,.35,'bell')
 # Pulse, soft cinematic kick + airy metallic ticks, with no drum samples.
 for beat in np.arange(0,44.9,.75):
  p=int(sr*beat); n=min(int(.24*sr),length-p); t=np.arange(n)/sr
  kick=np.sin(2*np.pi*(69*t-46*t*t))*np.exp(-24*t)*.15
  mix[p:p+n]+=kick.astype(np.float32)
 for beat in np.arange(.375,44.9,1.5):
  p=int(sr*beat); n=min(int(.19*sr),length-p); t=np.arange(n)/sr
  hiss=rng.normal(0,1,n)*np.exp(-37*t)*.028
  mix[p:p+n]+=hiss.astype(np.float32)
 # opening/closing cinematic dynamics
 n=np.arange(length)/sr
 envelope=np.minimum(1,n/1.4)*np.minimum(1,(45-n)/2.0)
 mix*=np.maximum(0,envelope).astype(np.float32)
 # gentle stereo movement from delayed copies; attenuated for speech ducking later
 peak=float(np.max(np.abs(mix)))
 mix=mix/max(.40,peak/.77)
 l=mix
 r=.90*mix+ .10*np.concatenate([np.zeros(170,dtype=np.float32),mix[:-170]])
 stereo=np.stack([l,r],axis=1)
 with wave.open(str(path),'wb') as wav:
  wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(sr)
  wav.writeframes((np.clip(stereo,-1,1)*32767).astype('<i2').tobytes())
 return {'description':'Original algorithmically synthesized instrumental candidate, dark cinematic-electronic, D-minor tonal center','authoring':'local deterministic synthesis; Sonoris organ review required','seed':1863,'sample_rate':sr,'duration_seconds':45,'sha256':digest(path)}

def original_background(folder,idx):
 # Reviewed V3 scenes 02/03 had accidental split-panels; 05 was a daylight courtyard.
 # Reuse only coherent chamber/stage sources with fresh Format Core treatments.
 idx={1:1,2:1,3:4,4:4,5:1}[idx]
 for ext in ('.png','.jpg','.jpeg','.webp'):
  p=folder/f'scene_{idx:02d}{ext}'
  if p.is_file():return p
 return None

def draw_scene(path,index,background):
 im=Image.new('RGB',(W,H),PAL['black'])
 if background:
  with Image.open(background) as source:
   src=ImageOps.fit(source.convert('RGB'),(W,H),method=Image.Resampling.LANCZOS)
   # Restrained blur and dark overlay make existing Pictora architecture atmospheric, not dominant.
   src=src.filter(ImageFilter.GaussianBlur(3.0 if index in (2,3,5) else 1.5))
   im.paste(src)
 rgba=im.convert('RGBA')
 # Dark translucent gradient for typography; Vesper on right stays visually legible.
 shade=Image.new('RGBA',(W,H),(0,0,0,0));sp=shade.load()
 for x in range(W):
  alpha=int(235*max(0,(1-x/1500))**1.4+55)
  alpha=min(235,alpha)
  for y in range(H): sp[x,y]=(5,7,12,alpha)
 rgba=Image.alpha_composite(rgba,shade)
 d=ImageDraw.Draw(rgba)
 # Fine architectural orbit instrumentation at right; varies per scene.
 cx,cy=1545,485
 for r in (235,310,385):
  d.arc((cx-r,cy-r,cx+r,cy+r),start=16+index*17,end=304+index*5,fill=(168,119,54,140),width=2)
 for r in (70,150,220):
  d.arc((cx-r,cy-r,cx+r,cy+r),start=95+index*12,end=255+index*10,fill=(233,175,76,95),width=1)
 for k in range(15):
  theta=(k*2*math.pi/15)+(index*.21)
  x=cx+math.cos(theta)*340; y=cy+math.sin(theta)*340
  d.ellipse((x-2,y-2,x+2,y+2),fill=(196,151,78,170))
 # Indexed expressive detail, top/bottom lines
 d.line((80,90,1840,90),fill=(*PAL['gold'],150),width=2)
 d.line((80,991,1840,991),fill=(173,127,68,115),width=2)
 d.rectangle((80,90,86,152),fill=PAL['gold'])
 eyebrow,title,subtitle,meta=SCENES[index-1]
 d.text((112,134),'DIO  /  DICERE',font=font(24,True),fill=PAL['gold'])
 d.text((112,220),eyebrow,font=font(31),fill=PAL['ivory'])
 # large title in a reserved left-safe area, custom wrapping
 words=title.split(); lines=[];cur=''
 f=font(69,True)
 for word in words:
  test=(cur+' '+word).strip()
  if cur and d.textbbox((0,0),test,font=f)[2]>1050:lines.append(cur);cur=word
  else:cur=test
 if cur:lines.append(cur)
 y=308
 for line in lines:
  d.text((106,y),line,font=f,fill=PAL['ivory'],stroke_width=1,stroke_fill=(8,10,15));y+=91
 d.line((112,y+30,390,y+30),fill=PAL['gold'],width=4)
 d.text((112,y+70),subtitle,font=font(25),fill=PAL['body'])
 d.text((112,937),meta,font=font(21,True),fill=PAL['gold'])
 d.text((1632,937),f'{index:02d}  /  05',font=font(23,True),fill=PAL['body'])
 rgba.convert('RGB').save(path)

def run_ffmpeg(args):
 subprocess.run(args,check=True)

def build(args):
 out=args.output.resolve()
 if out.exists() and any(out.iterdir()):raise SystemExit(f'REFUSE_OUTPUT_DIRECTORY_NOT_EMPTY: {out}')
 if args.full:
  for p in (args.face,args.mask,args.narration):require(p)
  with Image.open(args.mask) as mask:
   if mask.size!=(1254,1254):raise SystemExit(f'REFUSE_MASK_SIZE: {mask.size}')
  meta=probe(args.face)
  vs=[s for s in meta['streams'] if s['codec_type']=='video']
  if not vs or (vs[0]['width'],vs[0]['height'],vs[0]['r_frame_rate'])!=(1254,1254,'25/1') or float(meta['format']['duration'])<44.99:
   raise SystemExit('REFUSE_FACE_MUST_BE_1254_SQUARE_25FPS_45S')
  if float(probe(args.narration)['format']['duration'])<30:raise SystemExit('REFUSE_NARRATION_TOO_SHORT')
 out.mkdir(parents=True,exist_ok=True)
 music=out/'DICERE_OVERTURE_ORIGINAL_CANDIDATE.wav'
 musical_receipt=score(music)
 plates=[]; source_records=[]
 for i in range(1,6):
  bg=original_background(args.backgrounds,i)
  target=out/f'DICERE_V4_SCENE_{i:02d}.png'
  draw_scene(target,i,bg)
  plates.append(target)
  source_records.append({'scene':i,'source':str(bg) if bg else None,'source_sha256':digest(bg) if bg else None,'plate':str(target),'plate_sha256':digest(target)})
 if args.design_only:
  contact=Image.new('RGB',(960,3*300),(8,10,15))
  for i,p in enumerate(plates):
   with Image.open(p) as img: small=img.resize((480,270))
   contact.paste(small,((i%2)*480,(i//2)*300))
  contact.save(out/'DICERE_V4_DESIGN_CONTACT.jpg',quality=92)
  video=None
 else:
  seconds=5 if args.preview else 45
  video=out/('DICERE_V4_PREVIEW_5S.mp4' if args.preview else 'DICERE_V4_FULL_REVIEW.mp4')
  cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n']
  if args.preview:
   cmd+=['-loop','1','-framerate','25','-t','5','-i',str(plates[0])]
   face_idx,mask_idx,nar_idx,music_idx=1,2,3,4
  else:
   for p in plates:cmd+=['-loop','1','-framerate','25','-t','9','-i',str(p)]
   face_idx,mask_idx,nar_idx,music_idx=5,6,7,8
  cmd+=['-i',str(args.face),'-loop','1','-framerate','25','-i',str(args.mask),'-i',str(args.narration),'-i',str(music)]
  bg='[0:v]scale=1920:1080,setsar=1,fps=25[bg];' if args.preview else ''.join(f'[{i}:v]scale=1920:1080,setsar=1,fps=25[s{i}];' for i in range(5))+'[s0][s1][s2][s3][s4]concat=n=5:v=1:a=0[bg];'
  # STATIC human-approved RMBG matte; no chromakey. Presenter slightly larger than V3.
  graph=(bg+f'[{face_idx}:v]scale=540:540:flags=lanczos,setsar=1,format=rgb24[person];'+f'[{mask_idx}:v]scale=540:540:flags=lanczos,format=gray[alpha];'+'[person][alpha]alphamerge,format=rgba[cutout];'+'[bg][cutout]overlay=1250:440:shortest=1:format=auto,format=yuv420p[video];'+f'[{music_idx}:a]aresample=48000,volume=0.36,afade=t=in:st=0:d=1,afade=t=out:st=43:d=2[score];'+f'[{nar_idx}:a]aresample=48000,volume=1,afade=t=out:st=36.5:d=0.7[voice];'+'[score][voice]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.93[a]')
  cmd+=['-filter_complex',graph,'-map','[video]','-map','[a]','-t',str(seconds),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(video)]
  run_ffmpeg(cmd)
  actual=float(probe(video)['format']['duration'])
  if abs(actual-seconds)>.11:raise SystemExit(f'REFUSE_WRONG_DURATION={actual}')
 receipt={'schema':'dio.dicere.gilded_voice_v4.review.v1','state':'AWAITING_HUMAN_REVIEW','publication_authorized':False,'scope':'offline non-destructive V4 review','mode':'design_only' if args.design_only else 'preview' if args.preview else 'full','music':{'path':str(music),**musical_receipt},'scene_sources':source_records,'face':{'path':str(args.face),'sha256':digest(args.face)} if args.full else {'path':str(args.face)},'mask':{'path':str(args.mask),'sha256':digest(args.mask)} if args.full else {'path':str(args.mask)},'audio_policy':'original song candidate mixed under unchanged Vera narration','matte':'static approved RMBG matte; motion edge stability still requires review','output':str(video) if video else None,'output_sha256':digest(video) if video else None,'notes':['No Sonoris debut soundtrack reused','Pictora source backgrounds retained only as atmospheric textures; procedural visual treatments are Format Core design candidates','Vesper face pixels and eye motion are not re-generated','Song requires Sonoris organ review for admission as canonical score']}
 rp=out/'DICERE_V4_RECEIPT.json';rp.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'status':receipt['state'],'video':str(video) if video else None,'music':str(music),'receipt':str(rp),'design_contact':str(out/'DICERE_V4_DESIGN_CONTACT.jpg') if args.design_only else None},indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 m=p.add_mutually_exclusive_group(required=True)
 m.add_argument('--design-only',action='store_true',help='Create scenes, original score and contact sheet only')
 m.add_argument('--preview',action='store_true',help='Render five-second presenter and music preview')
 m.add_argument('--full',action='store_true',help='Render full 45-second review')
 p.add_argument('--face',type=Path,default=DEFAULT_FACE)
 p.add_argument('--mask',type=Path,default=DEFAULT_MASK)
 p.add_argument('--narration',type=Path,default=DEFAULT_NARRATION)
 p.add_argument('--backgrounds',type=Path,default=DEFAULT_BG)
 p.add_argument('--output',type=Path,default=DEFAULT_OUT)
 build(p.parse_args())
if __name__=='__main__':main()
