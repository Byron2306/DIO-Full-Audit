"""Regenerate the Sonoris ad's original dark ambient score and audible Vera/music mix."""
from __future__ import annotations
from pathlib import Path
import hashlib,json,subprocess,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'media/product_asset_packs/dio_creative_organs_site_matched_v2'
REC=PACK/'receipts'; VIDEO=PACK/'video'
VOICE_TEXT=("Meet Sonoris, the DIO music organ. It does not begin with a pile of notes or a copied song template. "
"It begins with behavior: a sprint, a stomp, a trance, a collapse, a release. Each genre sets its own laws. "
"Black metal can spiral through cold chromatic riffs and blast beats. Synthwave drives a pulse beneath glowing arpeggios. "
"Jazz fusion lets motifs pass between instruments. Ambient can make slow change and open space carry the form. "
"The compiler assigns every instrument a role, then turns the grammar into performance, articulation, and sound. "
"Sonoris. Music with a physical grammar.")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
voice=REC/'SONORIS_EXPLAINER_VERA_V2.wav'
req=urllib.request.Request('http://127.0.0.1:8000/tts',data=urllib.parse.urlencode({'text':VOICE_TEXT,'voice_url':'vera'}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
with urllib.request.urlopen(req,timeout=240) as response: voice.write_bytes(response.read())
music=REC/'SONORIS_DARKSYNTH_AMBIENT_V2_45S.wav'
subprocess.run(['node',str(ROOT/'scripts/generate_sonoris_ambient_synth.js'),str(music)],check=True)
# Start with 2.5s score-only to establish the music; duck it under Vera, then let it ring after the tag.
audio=VIDEO/'SONORIS_EXPLAINER_AUDIO_V2.wav'
graph='[0:a]aresample=48000,adelay=2500|2500,apad,atrim=0:45,asplit=2[voice][side];[1:a]volume=0.55,apad,atrim=0:45[music];[music][side]sidechaincompress=threshold=0.035:ratio=5:attack=25:release=800:makeup=1[duck];[voice][duck]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.94[out]'
subprocess.run(['ffmpeg','-y','-i',str(voice),'-i',str(music),'-filter_complex',graph,'-map','[out]','-c:a','pcm_s16le',str(audio),'-loglevel','error'],check=True)
concat=VIDEO/'scenes_v2.txt'; scenes=[VIDEO/f'SONORIS_EXPLAINER_SCENE_{i:02}.png' for i in range(1,6)]
concat.write_text(''.join(f"file '{p}'\nduration 9\n" for p in scenes)+f"file '{scenes[-1]}'\n")
mp4=VIDEO/'SONORIS_GOLDEN_ORGAN_EXPLAINER_REVIEW_V2.mp4'
subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(concat),'-i',str(audio),'-vf','scale=1920:1080,zoompan=z=1.0+0.00025*on:d=270:s=1920x1080:fps=30,format=yuv420p','-t','45','-r','30','-c:v','libx264','-crf','20','-preset','medium','-c:a','aac','-b:a','192k','-shortest',str(mp4),'-loglevel','error'],check=True)
inv=json.loads((ROOT/'state/presence/voice_verification/vera_runtime_inventory.json').read_text())
voice_receipt={'schema':'dio.pocket_tts.narration_receipt.v1','backend':'pocket_tts','profile_id':'vera_pocket_public','voice_url':'vera','endpoint':'http://127.0.0.1:8000/tts','audio_path':str(voice.relative_to(ROOT)),'audio_sha256':sha(voice),'model_provenance':inv['model_provenance'],'runtime_inventory_path':'state/presence/voice_verification/vera_runtime_inventory.json','runtime_inventory_sha256':sha(ROOT/'state/presence/voice_verification/vera_runtime_inventory.json'),'narration_text':VOICE_TEXT,'remote_processing':False,'release_authorized':False}
(REC/'POCKET_TTS_NARRATION_RECEIPT_V2.json').write_text(json.dumps(voice_receipt,indent=2)+'\n')
receipt={'schema':'dio.sonoris.explainer_media_receipt.v2','video':{'path':str(mp4.relative_to(ROOT)),'sha256':sha(mp4),'bytes':mp4.stat().st_size,'seconds':45,'format':'H.264 1920x1080 30fps; AAC'},'mix':{'path':str(audio.relative_to(ROOT)),'sha256':sha(audio),'bytes':audio.stat().st_size,'music_starts_at_seconds':0,'vera_starts_at_seconds':2.5,'mix_method':'Sidechain-ducked generated music under Vera; score-only intro and audible score outro'},'music':{'path':str(music.relative_to(ROOT)),'sha256':sha(music),'generator':'DIO Darksynth v3 native-PCM oscillator approach, adapted as a 85BPM F-minor ambient arpeggio and pad score','generator_script':'scripts/generate_sonoris_ambient_synth.js','generator_script_sha256':sha(ROOT/'scripts/generate_sonoris_ambient_synth.js'),'external_samples':False,'catalog_music':False},'voice_receipt':str((REC/'POCKET_TTS_NARRATION_RECEIPT_V2.json').relative_to(ROOT)),'human_review':'PENDING','release_authorized':False}
(REC/'SONORIS_EXPLAINER_MEDIA_RECEIPT_V2.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
