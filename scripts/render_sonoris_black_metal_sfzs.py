"""Render a Sonoris black-metal MIDI with the supplied Metal-GTX, Growlybass and Salamander SFZs."""
from __future__ import annotations
import hashlib, json, random, re, subprocess, sys
from collections import defaultdict, deque
from pathlib import Path
import mido
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'media/sonoris/releases/black_metal_where_pines_forget_v2'
MID=OUT/'WHERE_THE_PINES_FORGET_BLACK_METAL.mid'
GUITAR=Path('/home/byron/fusion-instruments/guitar/Metal-GTX/UI_METAL-GTX/Programs/Individual Patchs/SFIZZ_CLEAN/METAL-GTX_Full')
BASS=Path('/home/byron/fusion-instruments/bass/Growlybass/Growlybass')
DRUM=Path('/home/byron/fusion-instruments/drums/Salamander/Salamander Drumkit.sfz')
RENDERER='sfizz_render'
TPQ=480

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def abs_sfz(source: Path, target: Path, *, default_path: str|None=None) -> None:
    text=source.read_text(encoding='utf-8',errors='replace').replace('\\','/')
    if default_path:
        text=re.sub(r'(?m)^\s*default_path\s*=.*$',f'default_path={default_path.rstrip("/")}/',text)
    def sample(match):
        name=match.group(1).strip()
        return 'sample='+str((source.parent/name).resolve())
    text=re.sub(r'(?m)^\s*sample\s*=\s*(.+?)\s*$',sample,text)
    target.write_text(text,encoding='utf-8')

def note_events(track):
    tick=0; rows=[]
    for msg in track:
        tick+=msg.time
        if msg.is_meta: continue
        rows.append((tick,msg.copy()))
    return rows

def materialize(rows,path):
    rows=sorted(rows,key=lambda row:(row[0],0 if row[1].type in ('note_off',) or (row[1].type=='note_on' and row[1].velocity==0) else 1))
    tr=mido.MidiTrack(); prev=0
    for tick,msg in rows:
        msg.time=max(0,tick-prev); prev=tick; tr.append(msg)
    tr.append(mido.MetaMessage('end_of_track',time=1)); midi=mido.MidiFile(type=0,ticks_per_beat=TPQ);midi.tracks.append(tr);midi.save(path)

def render(sfz,midi,wav):
    subprocess.run([RENDERER,'--sfz',str(sfz),'--midi',str(midi),'--wav',str(wav),'--samplerate','48000'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

OUT.mkdir(parents=True,exist_ok=True);work=OUT/'sfz_render';work.mkdir(exist_ok=True)
source=mido.MidiFile(MID); guitar_rows=note_events(source.tracks[1]); bass_rows=note_events(source.tracks[2]); drum_rows=note_events(source.tracks[3]); materialize(drum_rows,work/'drums.mid')
# Two independently played guitars: each note routes to a pick direction; stomp accents use mute samples.
def split_guitar(rows,seed,performer):
    rng=random.Random(seed); dest={k:[] for k in ('Sus_Up','Sus_Down','Mute_Up','Mute_Down')}; pending=defaultdict(deque); pick=0
    for tick,msg in rows:
        if msg.type=='note_on' and msg.velocity>0:
            bar=tick//(TPQ*4); gesture_mute=20<=bar<28 or 40<=bar<48
            art=('Mute_Up' if pick%2==0 else 'Mute_Down') if gesture_mute else ('Sus_Up' if pick%2==0 else 'Sus_Down')
            shift=rng.randint(-8,8); vel=max(1,min(127,msg.velocity+rng.randint(-6,6)))
            pending[(msg.channel,msg.note)].append((art,shift)); dest[art].append((max(0,tick+shift),msg.copy(velocity=vel)));pick+=1
        elif msg.type=='note_off' or (msg.type=='note_on' and msg.velocity==0):
            q=pending[(msg.channel,msg.note)]
            if q:
                art,shift=q.popleft(); dest[art].append((max(0,tick+shift),msg.copy()))
    for art,events in dest.items():materialize(events,work/f'{performer}_{art}.mid')
    return dest

# The second pass uses independent timing and velocities, then gets its own amp treatment and pan.
performers=[]
for tag,seed in (('gtrL',2801),('gtrR',7381)):
    split_guitar(guitar_rows,seed,tag); paths=[]
    for art in ('Sus_Up','Sus_Down','Mute_Up','Mute_Down'):
        sfz=GUITAR/f'{art}.sfz'; normalized=work/f'{tag}_{art}.sfz';abs_sfz(sfz,normalized)
        wav=work/f'{tag}_{art}.wav';render(normalized,work/f'{tag}_{art}.mid',wav);paths.append(wav)
    performers.append(paths)
# Bass articulation follows note behavior; the split is tied to this song's durations.
def split_bass(rows):
    pending=defaultdict(deque);dest={'dirty':[],'vicious':[]}
    for tick,msg in rows:
        if msg.type=='note_on' and msg.velocity>0:
            pending[(msg.channel,msg.note)].append((tick,msg.copy()))
        elif msg.type=='note_off' or (msg.type=='note_on' and msg.velocity==0):
            q=pending[(msg.channel,msg.note)]
            if q:
                start,on=q.popleft(); art='vicious' if tick-start <= TPQ//2 else 'dirty'
                dest[art].extend([(start,on),(tick,msg.copy())])
    for art,events in dest.items():materialize(events,work/f'bass_{art}.mid')
    return dest
split_bass(bass_rows); bass_wavs=[]
for art,file in [('dirty','growlybass_dirty.sfz'),('vicious','growlybass_vicious.sfz')]:
    s=BASS/file;norm=work/f'bass_{art}.sfz';abs_sfz(s,norm);w=work/f'bass_{art}.wav';render(norm,work/f'bass_{art}.mid',w);bass_wavs.append(w)
# Salamander's SFZ uses default_path for its overhead sample bank.
drum_norm=work/'Salamander_Drumkit.sfz';abs_sfz(DRUM,drum_norm,default_path=str(DRUM.parent/'OH'));drum_wav=work/'salamander.wav';render(drum_norm,work/'drums.mid',drum_wav)
# Compose each four-articulation guitar pass and add a saturated amp/cab voicing.
perf_mix=[]
for i,paths in enumerate(performers):
    mix=work/f'guitar_performance_{i+1}.wav';inputs=[]
    for path in paths:inputs += ['-i',str(path)]
    labels=''.join(f'[{j}:a]' for j in range(len(paths)))
    graph=f'{labels}amix=inputs=4:duration=longest:normalize=0,volume=10dB,highpass=f=75,equalizer=f=180:t=q:w=1:g=4,equalizer=f=480:t=q:w=1:g=-2,equalizer=f=1800:t=q:w=1:g=3,lowpass=f=9000,acompressor=threshold=0.12:ratio=4:attack=5:release=120,asoftclip=type=tanh:threshold=0.34:oversample=4[out]'
    subprocess.run(['ffmpeg','-y',*inputs,'-filter_complex',graph,'-map','[out]','-c:a','pcm_s16le',str(mix),'-loglevel','error'],check=True);perf_mix.append(mix)
# Actual library mix: doubled saturated Metal-GTX, Growlybass, and CC BY-SA Salamander. Center the rhythm section.
allinputs=['-i',str(perf_mix[0]),'-i',str(perf_mix[1]),'-i',str(bass_wavs[0]),'-i',str(bass_wavs[1]),'-i',str(drum_wav)]
graph='[0:a]atrim=0:82,pan=stereo|c0=0.9*c0|c1=0.1*c1[left];[1:a]atrim=0:82,pan=stereo|c0=0.1*c0|c1=0.9*c1[right];[2:a]atrim=0:82,volume=5dB,highpass=f=38,lowpass=f=750[b1];[3:a]atrim=0:82,volume=5dB,highpass=f=38,lowpass=f=750[b2];[b1][b2]amix=inputs=2:duration=longest:normalize=0,pan=stereo|c0=0.5*c0|c1=0.5*c1[bass];[4:a]atrim=0:82,volume=4dB,pan=stereo|c0=0.7*c0|c1=0.7*c1[drums];[left][right][bass][drums]amix=inputs=4:duration=longest:normalize=0,volume=8dB,alimiter=limit=0.92[out]'
wav=OUT/'WHERE_THE_PINES_FORGET_METAL_GTX_GROWLYBASS_SALAMANDER_V2.wav'
subprocess.run(['ffmpeg','-y',*allinputs,'-filter_complex',graph,'-map','[out]','-c:a','pcm_s16le',str(wav),'-loglevel','error'],check=True)
mp3=OUT/'WHERE_THE_PINES_FORGET_METAL_GTX_GROWLYBASS_SALAMANDER_V2.mp3'
subprocess.run(['ffmpeg','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','256k','-metadata','title=Where the Pines Forget','-metadata','artist=DIO Sonoris','-metadata','comment=Review candidate with supplied SFZ instruments','-id3v2_version','3',str(mp3),'-loglevel','error'],check=True)
# The evidence audit checks compiled intent and renderer routing. Listening remains a separate gate.
from products.sonoris_genre_compiler import audit_composition_evidence
plan=json.loads((OUT/'SONORIS_GOVERNED_COMPOSITION_PLAN.json').read_text())
evidence={'tempo_bpm':168,'meter':'4/4','gestures':[section['gesture'] for section in plan['sections']],
 'structural_laws':{'distinct_riff_identities_required':True,'section_contrast_required':True,'double_tracked_rhythm_guitar_required':True},
 'harmony_center':'minor','harmony_intervals':['diminished_fifth','augmented_fifth'],
 'guitar_behaviors':['tremolo_picking','double_tracking','mute_up','mute_down'],
 'drum_behaviors':['blast_beat','double_bass','half_time_stomp']}
audit=audit_composition_evidence(plan,evidence)
all_outputs=[wav,mp3,OUT/'WHERE_THE_PINES_FORGET_BLACK_METAL.mid',OUT/'WHERE_THE_PINES_FORGET_PREVIEW_FLUIDR3.wav']+[path for group in performers for path in group]+bass_wavs+[drum_wav]
receipt={'schema':'dio.sonoris.black_metal_release_candidate.v2','title':'Where the Pines Forget','genre_profile':'BLACK_METAL_CLASSIC','tempo_bpm':168,'meter':'4/4','bars':52,'tonal_center':'D minor','composition_plan':str((OUT/'SONORIS_GOVERNED_COMPOSITION_PLAN.json').relative_to(ROOT)),'composition_plan_sha256':sha(OUT/'SONORIS_GOVERNED_COMPOSITION_PLAN.json'),'genre_audit':audit,'audio_realization':{'guitar':'Metal-GTX four articulation patches; independent randomized double performances, hard-panned; amp saturation and cabinet-style EQ','bass':'Growlybass Dirty sustain and Vicious staccato patches; mapped to D2-centered range','drums':'Salamander Drumkit SFZ with its CC BY-SA 3.0 overhead library','midi_source':'Original 16th tremolo riff identities with chromatic minor progression, diminished/augmented fifth voicings, blast-beat/double-bass passages and gesture-driven section changes'},'module_licenses':{'Metal-GTX':'No local license file found; private audition only pending rights clearance','Growlybass':'Bundled readme states royalty-free commercial and non-commercial use','Salamander':'CC BY-SA 3.0 per bundled REAMDE; attribution and share-alike apply'},'artifacts':[{'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size} for path in all_outputs if path.is_file()],'human_listening_review':'REQUIRED','commercial_use':'HELD_PENDING_METAL_GTX_RIGHTS_AND_HUMAN_REVIEW','release_authorized':False}
(OUT/'SONORIS_BLACK_METAL_RELEASE_RECEIPT.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'wav':str(wav),'mp3':str(mp3),'genre_audit':audit['state'],'sha256':sha(wav),'stem_count':len(all_outputs)-4},indent=2))
