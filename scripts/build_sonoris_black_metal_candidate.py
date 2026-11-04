from pathlib import Path
import mido, json, random, hashlib, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from products.sonoris_genre_compiler import compile_composition_request
out=ROOT/'media/sonoris/releases/black_metal_where_pines_forget_v2'; out.mkdir(parents=True,exist_ok=True)
TPQ=480; bpm=168; rng=random.Random(661028)
composition_plan=compile_composition_request({'genre':'black_metal','title':'Where the Pines Forget','mood':'icy, eerie, relentless, then dissolving','tempo_bpm':bpm,'meter':'4/4','bars':52,'tonal_center':'D-minor'})
(out/'SONORIS_GOVERNED_COMPOSITION_PLAN.json').write_text(json.dumps(composition_plan,indent=2,ensure_ascii=False)+'\n')
m=mido.MidiFile(type=1,ticks_per_beat=TPQ)
meta=mido.MidiTrack(); meta.append(mido.MetaMessage('track_name',name='Where the Pines Forget | BLACK_METAL_CLASSIC morphology',time=0)); meta.append(mido.MetaMessage('set_tempo',tempo=mido.bpm2tempo(bpm),time=0)); meta.append(mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0))
form=[(section['section'].upper().replace(' ','_'),section['start_bar'],section['bars'],section['gesture']) for section in composition_plan['sections']]
for name,bars,g in [(n,s,c) for n,s,c,g in form]: meta.append(mido.MetaMessage('marker',text=f'{name} | {next(g for nn,ss,cc,g in form if nn==name)}',time=0))
# replace zero marker times with absolute deltas
meta=mido.MidiTrack(); meta.append(mido.MetaMessage('track_name',name='Where the Pines Forget | genre grammar arrangement',time=0)); meta.append(mido.MetaMessage('set_tempo',tempo=mido.bpm2tempo(bpm),time=0)); meta.append(mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0)); prev=0
for name,start,count,gesture in form:
 t=start*TPQ*4; meta.append(mido.MetaMessage('marker',text=f'{name} | {gesture}',time=t-prev)); prev=t
m.tracks.append(meta)
def make_track(name,ch,prog,events):
 tr=mido.MidiTrack(); tr.append(mido.MetaMessage('track_name',name=name,time=0))
 if prog is not None: tr.append(mido.Message('program_change',channel=ch,program=prog,time=0))
 rows=[]
 for t,p,d,v in events:
  rows.extend([(max(0,t),1,mido.Message('note_on',channel=ch,note=p,velocity=v)),(max(0,t)+d,0,mido.Message('note_off',channel=ch,note=p,velocity=0))])
 rows.sort(key=lambda r:(r[0],r[1])); prev=0
 for t,_,msg in rows: msg.time=t-prev; prev=t; tr.append(msg)
 tr.append(mido.MetaMessage('end_of_track',time=1)); m.tracks.append(tr)
guit=[]; bass=[]; drums=[]; drone=[]
# Root D with chromatic Eb and tritone Ab; each family has its own contour and bodily role.
for bar in range(52):
 start=bar*TPQ*4; sec=next((x for x in form if x[1]<=bar<x[1]+x[2]),form[-1]); gesture=sec[3]; guitar_bar_start=len(guit)
 if gesture=='TRANCE':
  # sustained tremolo texture gradually transforming across long cycle
  base=[38,39,38,33][(bar//2)%4]
  for beat in range(4):
   for sub in range(4):
    if bar<4 and (beat>1 or sub%2): continue
    guit.append((start+beat*TPQ+sub*TPQ//4,base+(12 if bar%4==3 else 0),TPQ//4-18,73+rng.randrange(0,13)))
 elif gesture=='SPRINT':
  base=[38,38,39,45,38,36,39,33][(bar-4)%8]
  for beat in range(4):
   # gallop then held chromatic answer, two identities within family
   offsets=[0,TPQ//3,2*TPQ//3] if beat in (0,2) else [0,TPQ//2]
   for j,o in enumerate(offsets): guit.append((start+beat*TPQ+o,base,TPQ//3-15,95 if j==0 else 77))
 elif gesture=='PANIC':
  seq=[38,39,38,41,38,39,45,41,38,37,38,41,33,34,38,39]
  for i,n in enumerate(seq): guit.append((start+i*TPQ//4,n,TPQ//4-12,96 if i%4==0 else 79))
 elif gesture=='STOMP':
  base=[38,38,41,38,46,45,41,39][(bar-20)%8]
  for beat in range(4):
   dur=TPQ*3//4 if beat in (0,2) else TPQ//3
   guit.append((start+beat*TPQ,base,dur,108 if beat in (0,2) else 83))
 elif gesture=='COLLAPSE':
  if bar%2==0: guit.append((start,38,TPQ*3,103)); guit.append((start+TPQ*3,39,TPQ,78))
 elif gesture=='HOOK':
  riff=[38,41,43,41,38,39,33,36][(bar-40)%8]
  for beat,n in enumerate([riff,riff,39 if bar%2 else 41,38]): guit.append((start+beat*TPQ,n,TPQ*2//3,99 if beat==0 else 80))
 elif gesture=='RELEASE':
  if bar%4==0: guit.append((start,38,TPQ*4,75))
 # Diminished fifths and augmented fifths make the ice field dissonant, with minor-third anchors.
 # Harmony is voiced into each active gesture rather than pasted on as a guitar-chord loop.
 base_events=list(guit[guitar_bar_start:])
 for gi,(gtick,gnote,gdur,gvel) in enumerate(base_events):
  if gi % 3 == 0:
   interval = 8 if (bar + gi) % 4 == 2 else 6  # augmented fifth or diminished fifth
   guit.append((gtick, gnote + interval, gdur, max(48, gvel - 14)))
  if gi % 8 == 0 and gesture in ('TRANCE','PANIC','HOOK'):
   guit.append((gtick, gnote + 3, gdur, max(45, gvel - 20)))
 # Bass follows the audible D-minor pedal in the Growlybass instrument's sampled range.
 root={ 'TRANCE':38,'SPRINT':38,'PANIC':38,'STOMP':38,'COLLAPSE':38,'HOOK':38,'RELEASE':38}[gesture]
 if gesture=='PANIC':
  for b in range(4): bass.append((start+b*TPQ, [root,root+1,root+6,root+13][b], TPQ//2, 93))
 elif gesture=='COLLAPSE': bass.append((start,root,TPQ*3,88))
 elif gesture=='TRANCE':
  if bar%2==0: bass.append((start,root,TPQ*4-30,68))
 elif gesture=='RELEASE':
  if bar%4==0: bass.append((start,root,TPQ*4,58))
 else:
  for b in range(4): bass.append((start+b*TPQ,root+(1 if (bar%4==3 and b==3) else 0),TPQ*3//4,89 if b in (0,2) else 73))
 # drummer's physical gesture: early tom/cymbal bloom, blasts, double-kick, then half-time stomp.
 if bar<4:
  for b in (0,2): drums.append((start+b*TPQ,36,TPQ//5,70))
  if bar in (0,3): drums.append((start,49,TPQ//2,76))
 elif gesture in ('SPRINT','PANIC'):
  for b in range(4):
   drums.append((start+b*TPQ,36,TPQ//5,108 if b==0 else 95))
   drums.append((start+b*TPQ+TPQ//2,36,TPQ//5,88))
   for sub in range(4): drums.append((start+b*TPQ+sub*TPQ//4,42,TPQ//10,65 if sub%2 else 78))
  for b in (1,3): drums.append((start+b*TPQ,38,TPQ//5,100))
 elif gesture=='STOMP':
  for b in (0,2): drums.append((start+b*TPQ,36,TPQ//4,116))
  for b in (1,3): drums.append((start+b*TPQ,38,TPQ//4,105))
  for b in range(4): drums.append((start+b*TPQ+TPQ//2,49 if b==3 else 51,TPQ//6,84))
 elif gesture=='COLLAPSE':
  if bar in (28,31): drums.append((start,49,TPQ,72))
 elif gesture=='HOOK':
  for b in range(4): drums.append((start+b*TPQ,36 if b in (0,2) else 38,TPQ//4,104))
  for b in range(4): drums.append((start+b*TPQ+TPQ//2,51,TPQ//6,78))
 elif gesture=='RELEASE':
  if bar%4==0: drums.append((start,49,TPQ*2,65))
make_track('Metal GTX inspired tremolo and riff families (FluidR3 preview rendering)',0,30,guit)
make_track('Growlybass lock and escape',1,34,bass)
make_track('Salamander groove gestures',9,None,drums)
mp=out/'WHERE_THE_PINES_FORGET_BLACK_METAL.mid'; m.save(mp)
sf='/usr/share/sounds/sf2/FluidR3_GM.sf2'; wav=out/'WHERE_THE_PINES_FORGET_PREVIEW_FLUIDR3.wav'
subprocess.run(['fluidsynth','-ni','-F',str(wav),'-r','44100',sf,str(mp)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=180)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
report={'schema':'dio.sonoris.black_metal_release_candidate.v1','title':'Where the Pines Forget','profile':'BLACK_METAL_CLASSIC','genre_reading':{'tempo_profile_bpm':[150,170,220,240],'selected_bpm':168,'meter':'4/4','structural_law':'through-composed morphology, no conventional chorus requirement','gesture_families':['TRANCE','SPRINT','PANIC','STOMP','COLLAPSE','HOOK','RELEASE'],'design':'8 sections / 52 bars; 16th-note tremolo, D-minor pedal and chromatic minor progression with voiced diminished/augmented fifths, blast-beat/double-kick passages, long collapse/release and transformed hook','track_roles':'guitar gesture carries morphology; bass locks/pushes/breaks away at collapse; drums shadow physical gesture'},'instrument_sources':{'guitar':'Metal-GTX Sus_Up/Sus_Down tremolo alternation and Mute_Up/Mute_Down accents, rendered through sfizz then amp-saturated; local license not found','bass':'Growlybass Dirty sustain and Vicious staccato SFZ alternation; bundled readme states royalty-free for commercial and non-commercial use','drums':'Salamander Drumkit SFZ; CC BY-SA 3.0 in bundled REAMDE'},'renders':{'midi':{'path':str(mp),'sha256':sha(mp)},'preview_wav':{'path':str(wav),'sha256':sha(wav)}},'rights':'Original composition. Instrument module notes recorded; audio preview uses FluidR3 GM soundfont; commercial clearance of complete mix and soundfont remains unverified. Human listening review pending.','release':'LOCAL_REVIEW_CANDIDATE_NOT_PUBLISHED'}
(out/'SONORIS_BLACK_METAL_RELEASE_RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'midi':str(mp),'wav':str(wav),'seconds':mido.tick2second(max(sum(msg.time for msg in tr) for tr in m.tracks),TPQ,mido.bpm2tempo(bpm)),'sha256':sha(wav)}))
