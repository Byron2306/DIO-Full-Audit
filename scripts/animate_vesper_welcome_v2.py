from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,ImageOps
import zipfile,io,json,hashlib,subprocess
root=Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit'); download=Path('/home/byron/Downloads'); out=root/'media/product_asset_packs/homs_corpo_cult_v1/vesper/visemes/welcome_v2'; frames=out/'frames';frames.mkdir(parents=True,exist_ok=True)
zipf=zipfile.ZipFile(download/'grok-group.zip'); names=zipf.namelist();
imgs={i:Image.open(io.BytesIO(zipf.read(names[i-1]))).convert('RGB').resize((704,704),Image.Resampling.LANCZOS) for i in [3,6,7,8,9,14]}
# Static face and hair reference; only a feathered lower-face patch is animated.
base=imgs[7].copy(); mask=Image.new('L',(704,704),0);d=ImageDraw.Draw(mask);d.ellipse((260,333,454,421),fill=255);mask=mask.filter(ImageFilter.GaussianBlur(12))
# use provisional storyboard editorial timings exactly; viseme approximation explicit
segs=[(0,.25,7),(0.25,.37,9),(.37,.55,3),(.55,.63,7),(.63,.73,7),(.73,.91,8),(.91,1.06,7),(1.06,1.65,7),(1.65,1.78,7),(1.78,2.00,9),(2,2.18,7),(2.18,2.30,7),(2.30,2.55,3),(2.55,2.86,8),(2.86,3.17,6),(3.17,3.60,7)]
# interpolate in/out around phoneme boundaries to avoid hard pose changes
fps=30; N=108
for fi in range(N):
 t=fi/fps; row=next((s for s in segs if s[0]<=t<s[1]),segs[-1]); img=imgs[row[2]]; frame=base.copy();frame.paste(img,(0,0),mask); frame.save(frames/f'frame_{fi:04d}.png')
mp4=out/'VESPER_021_WELCOME_TO_DIO_SILENT_V2.mp4'
subprocess.run(['ffmpeg','-y','-framerate','30','-i',str(frames/'frame_%04d.png'),'-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(mp4)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
# review contact sheet
sheets=[]
for t in [0,.4,.8,1.3,1.8,2.4,2.7,3.0,3.4]: sheets.append(Image.open(frames/f'frame_{int(t*fps):04d}.png').resize((224,224)))
canvas=Image.new('RGB',(224*3,244*3),(8,8,8));d=ImageDraw.Draw(canvas)
for i,im in enumerate(sheets): x=(i%3)*224;y=(i//3)*244;canvas.paste(im,(x,y));d.text((x+8,y+224),f'{i+1}: { [0,.4,.8,1.3,1.8,2.4,2.7,3.0,3.4][i]:.1f}s',fill=(225,185,96))
contact=out/'VESPER_021_V2_CONTACT_SHEET.jpg';canvas.save(contact,quality=92)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt={'schema':'dio.vesper.visual_animation_review.v1','source_clip':str(download/'VESPER_021_WELCOME_TO_DIO_SILENT.mp4'),'source_clip_sha256':sha(download/'VESPER_021_WELCOME_TO_DIO_SILENT.mp4'),'reference_archive':str(download/'grok-group.zip'),'reference_pose_indices':{'REST':7,'UW':9,'OH':6,'AA':8,'EE':3,'small_round_transition':14},'storyboard':str(download/'welcome_to_dio_storyboard_v1.json'),'storyboard_status':'PROVISIONAL_UNALIGNED_NO_AUDIO','method':'Fixed face/hair reference, mouth-only feathered pose compositing from the 19-image atlas. Uses storyboard editorial timings. Excludes unrelated Grok reference artifacts from pose set.','limitations':'No source speech audio; this is not audio-aligned lip sync. Poses are nearest visual equivalents, not a registered phoneme atlas; some facial expression variation from source clip is intentionally held static to reduce identity drift.','outputs':[{'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size} for p in (mp4,contact)]}
(out/'VESPER_021_V2_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'mp4':str(mp4),'contact_sheet':str(contact),'size':mp4.stat().st_size}))
