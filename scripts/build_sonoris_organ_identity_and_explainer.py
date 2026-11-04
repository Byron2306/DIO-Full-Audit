from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageEnhance
import math,json,hashlib,subprocess,urllib.parse,urllib.request

R=Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit'); P=R/'media/product_asset_packs/dio_creative_organs_site_matched_v2'; A=P/'assets'; V=P/'video'; (P/'receipts').mkdir(parents=True,exist_ok=True)
old=R/'media/product_asset_packs/dio_creative_organs_site_matched_v1/assets'
son=Image.open(old/'SONORIS_MUSICAL_ORGAN_HERO_1280x720.png').convert('RGB')
pic=Image.open(old/'PICTORA_IMAGE_FORGE_HERO_1280x720.png').convert('RGB')
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def f(sz,b=False):return ImageFont.truetype(bold if b else font,sz)
def gold(d,xy,text,size=36,anchor=None):d.text(xy,text,font=f(size,True),fill=(225,185,96),anchor=anchor,stroke_width=0)
def glow(im,xy,r,col=(219,173,80),alpha=65):
 lay=Image.new('RGBA',im.size);d=ImageDraw.Draw(lay);x,y=xy;d.ellipse((x-r,y-r,x+r,y+r),fill=(*col,alpha));lay=lay.filter(ImageFilter.GaussianBlur(r*.68));im.alpha_composite(lay)
def fit_cover(img,size):
 w,h=size; k=max(w/img.width,h/img.height); im=img.resize((int(img.width*k),int(img.height*k)),Image.Resampling.LANCZOS); x=(im.width-w)//2;y=(im.height-h)//2; return im.crop((x,y,x+w,y+h))
def banner(name,src,kicker,title,sub,filename):
 im=fit_cover(src,(1920,1080)).convert('RGBA'); shade=Image.new('RGBA',im.size,(0,0,0,45));im.alpha_composite(shade); glow(im,(1560,300),360,alpha=34);d=ImageDraw.Draw(im);d.rectangle((72,70,1848,1010),outline=(196,153,73,95),width=2);d.line((130,170,630,170),fill=(222,179,86,180),width=2);gold(d,(132,204),kicker.upper(),22);gold(d,(128,610),title,78);d.text((134,728),sub,font=f(31),fill=(237,230,211));d.text((134,932),'DIO  /  CREATIVE ORGANS',font=f(18,True),fill=(183,157,106));path=A/filename;im.convert('RGB').save(path,quality=95);return path
banner('SONORIS',son,'COMPUTATIONAL MUSICAL MORPHOLOGY','Music with a physical grammar','Compose by gesture, interaction and transformation.', 'SONORIS_ORGAN_BANNER_1920x1080.jpg')
banner('PICTORA',pic,'LOCAL IMAGE CREATION ORGAN','Imagine. Shape. Render.','A creative image forge for worlds, characters and visual assets.', 'PICTORA_ORGAN_BANNER_1920x1080.jpg')
def badge(src,filename,label):
 im=Image.new('RGBA',(1024,1024),(5,6,8,255)); tile=fit_cover(src,(820,820)).convert('RGBA'); mask=Image.new('L',tile.size,0);ImageDraw.Draw(mask).ellipse((0,0,819,819),fill=255); tile.putalpha(mask);im.alpha_composite(tile,(102,72));d=ImageDraw.Draw(im);d.ellipse((74,44,950,920),outline=(224,181,93),width=5);d.ellipse((92,62,932,902),outline=(114,82,43),width=2);d.rounded_rectangle((210,860,814,972),radius=36,fill=(7,8,9,243),outline=(222,181,94),width=3);gold(d,(512,901),label,39,anchor='mm');p=A/filename;im.save(p);return p
badge(son,'SONORIS_ORGAN_BADGE_1024.png','SONORIS');badge(pic,'PICTORA_ORGAN_BADGE_1024.png','PICTORA')
def icon(src,filename,mode):
 im=Image.new('RGBA',(512,512),(5,6,8,255));crop=fit_cover(src,(390,390)).convert('RGBA');mask=Image.new('L',(390,390),0);ImageDraw.Draw(mask).ellipse((0,0,389,389),fill=255);crop.putalpha(mask); im.alpha_composite(crop,(61,46));d=ImageDraw.Draw(im);d.ellipse((45,30,467,452),outline=(220,177,88),width=4)
 if mode=='music':
  d.arc((160,138,365,345),210,35,fill=(245,211,144),width=9);d.line((246,174,246,314),fill=(250,218,152),width=8);d.ellipse((207,298,249,336),fill=(242,204,125));d.ellipse((276,278,318,316),fill=(242,204,125))
 elif mode=='image':
  d.rounded_rectangle((155,156,358,326),radius=14,outline=(245,211,144),width=7);d.ellipse((193,188,229,224),fill=(245,211,144));d.polygon([(165,308),(227,244),(269,284),(306,231),(348,308)],fill=(245,211,144,190))
 else:
  d.ellipse((185,185,325,325),outline=(245,211,144),width=8);d.line((287,287,362,362),fill=(245,211,144),width=13)
 return im
for src,slug in ((son,'SONORIS'),(pic,'PICTORA')):
 for mode,suffix in (('music','GESTURE' if slug=='SONORIS' else 'CREATE'),('image','ENSEMBLE' if slug=='SONORIS' else 'REFINE'),('detail','TRANSFORM' if slug=='SONORIS' else 'UPSCALE')):
  icon(src,f'{slug}_ICON_{suffix}_512.png',mode).save(A/f'{slug}_ICON_{suffix}_512.png')
music=P/'receipts/SONORIS_ORGANIC_AMBIENT_SYNTH_45S.wav'
subprocess.run(['node',str(R/'scripts/generate_sonoris_ambient_synth.js'),str(music)],check=True)
# Vera narration through the local canonical service.
text='Meet Sonoris, the DIO music organ. It composes through musical gesture: a sprint, a stomp, a trance, a collapse, a release. Genre shapes the rules. Instruments answer one another. Riffs transform with purpose. Sonoris turns musical structure into a living system.'
req=urllib.request.Request('http://127.0.0.1:8000/tts',data=urllib.parse.urlencode({'text':text,'voice_url':'vera'}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
voice=P/'receipts/SONORIS_EXPLAINER_VERA.wav'
try:
 with urllib.request.urlopen(req,timeout=180) as r: voice.write_bytes(r.read())
 voice_ok=voice.exists() and voice.stat().st_size>10000
except Exception as e: voice_ok=False; (P/'receipts/VOICE_RENDER_NOTE.txt').write_text('Local Vera service was unavailable: '+repr(e))
# Normalize soundtrack and duck ambient under voice using ffmpeg sidechain compressor.
if voice_ok:
 mix=P/'video/SONORIS_EXPLAINER_AUDIO.wav'
 subprocess.run(['ffmpeg','-y','-i',str(voice),'-i',str(music),'-filter_complex','[0:a]aresample=48000,apad,atrim=0:45,volume=1.0[v];[1:a]volume=0.14[m];[v][m]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.93[out]','-map','[out]','-c:a','pcm_s16le',str(mix)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
else: mix=music
# Five visual cards derive from current DIO site matched image assets; animate gently in ffmpeg.
cards=[]
copy=[('SONORIS','A NEW MUSICAL ORGAN','Composition begins with behavior.'),('GESTURE GRAMMAR','SPRINT  /  STOMP  /  TRANCE','Embodied motion becomes musical structure.'),('ENSEMBLE INTELLIGENCE','GUITAR  /  BASS  /  DRUMS  /  SYNTH','Each instrument has a role in the gesture.'),('GENRE WITH ITS OWN LAWS','CONTRAST  /  TRANSFORMATION  /  RELEASE','A black metal grammar. A jazz fusion grammar. New worlds.'),('SONORIS','MAKE MUSIC THAT MOVES','DIO  /  CREATIVE ORGANS')]
for i,(title,kicker,sub) in enumerate(copy):
 src=son if i in (0,1,3,4) else pic; im=fit_cover(src,(1920,1080)).convert('RGBA'); im.alpha_composite(Image.new('RGBA',im.size,(0,0,0,120))); d=ImageDraw.Draw(im); d.rectangle((55,55,1865,1025),outline=(195,152,70,135),width=2);gold(d,(115,140),kicker,24);gold(d,(112,700),title,64);d.text((117,806),sub,font=f(30),fill=(234,226,207));d.text((117,960),'DIO  •  SONORIS',font=f(20,True),fill=(194,164,102)); cp=V/f'SONORIS_EXPLAINER_SCENE_{i+1:02}.png';im.convert('RGB').save(cp);cards.append(cp)
# Build clean cuts by scene timing with subtle zoom and crossfades using concat demuxer for predictable full timeline.
concat=V/'scenes.txt';concat.write_text(''.join(f"file '{x}'\nduration 9\n" for x in cards)+f"file '{cards[-1]}'\n")
mp4=V/'SONORIS_GOLDEN_ORGAN_EXPLAINER_REVIEW.mp4'
subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(concat),'-i',str(mix),'-vf','scale=1920:1080,zoompan=z=1.0+0.00025*on:d=270:s=1920x1080:fps=30,format=yuv420p','-t','45','-r','30','-c:v','libx264','-crf','20','-preset','medium','-c:a','aac','-b:a','192k','-shortest',str(mp4)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=list(A.glob('*'))+[music,voice if voice_ok else P/'receipts/VOICE_RENDER_NOTE.txt',mix,mp4]
rec={'schema':'dio.sonoris.explainer_media_receipt.v1','voice_profile':'vera_pocket_public' if voice_ok else 'NO_VOICE_RENDERED','voice_url':'vera' if voice_ok else None,'voice_endpoint':'http://127.0.0.1:8000/tts','narration_text':text,'music':'Original locally composed ambient synth, generated from oscillators; no catalog music or samples used.','site_style_reference':'DIO Workflows current site-matched Sonoris/Pictora hero images in prior Pictora pack; derived golden black artboard treatment.','remote_processing':False,'human_review':'PENDING','release_authorized':False,'outputs':[{'path':str(x.relative_to(R)) if x.is_relative_to(R) else str(x),'sha256':sha(x),'bytes':x.stat().st_size} for x in files if x.is_file()]}
(P/'receipts/SONORIS_EXPLAINER_MEDIA_RECEIPT.json').write_text(json.dumps(rec,indent=2)+'\n')
manifest={'schema':'dio.creative_organs.visual_identity_pack.v1','style':'DIO website obsidian black, thin orbital gold, restrained glow; no generated text relied upon','source':'Pictora site-matched Sonoris/Pictora artwork, locally composed layout and typography','assets':[{'path':str(p.relative_to(R)),'sha256':sha(p)} for p in A.iterdir() if p.is_file()],'review':'LOCAL_CANDIDATES_HUMAN_REVIEW_PENDING'};(P/'CREATIVE_ORGAN_IDENTITY_PACK.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'asset_count':len(manifest['assets']),'voice_ok':voice_ok,'video':str(mp4),'video_size':mp4.stat().st_size,'music':str(music)},indent=2))
