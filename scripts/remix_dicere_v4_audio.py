#!/usr/bin/env python3
"""Non-destructive Dicere V4 audio-only remix: reuse video, source Vera narration, new Sonoris music.
Requires local ffmpeg/ffprobe. No generative audio or model downloads.
"""
import argparse, json, subprocess, hashlib
from pathlib import Path
ROOT=Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit')
DEFAULT_VIDEO=ROOT/'media/dicere/debut/v4-full/DICERE_V4_FULL_REVIEW.mp4'
DEFAULT_VOICE=ROOT/'media/dicere/debut/dicere_vera_narration.wav'

def probe(path):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],text=True))
def duration(path):return float(probe(path)['format']['duration'])
def hash_file(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1<<20),b''):h.update(block)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--video',type=Path,default=DEFAULT_VIDEO)
 p.add_argument('--narration',type=Path,default=DEFAULT_VOICE)
 p.add_argument('--music',type=Path,help='Approved original Sonoris audio, preferably actual recorded/sampled instruments')
 p.add_argument('--output',type=Path,default=ROOT/'media/dicere/debut/v4-audio-fix/DICERE_V4_AUDIO_REVIEW.mp4')
 p.add_argument('--music-gain',type=float,default=.20)
 p.add_argument('--voice-gain',type=float,default=1.0)
 p.add_argument('--voice-only',action='store_true',help='Diagnostic cut: original Vera narration with no music')
 a=p.parse_args()
 if a.music and a.voice_only:p.error('--music and --voice-only are mutually exclusive')
 if not a.voice_only and not a.music:p.error('Provide --music with new Sonoris score, or use --voice-only for diagnostic')
 for source in (a.video,a.narration,*([a.music] if a.music else [])):
  if not source.is_file() or source.stat().st_size<1000:raise SystemExit(f'REFUSE_MISSING_INPUT: {source}')
 if a.output.exists():raise SystemExit(f'REFUSE_OUTPUT_EXISTS: {a.output}')
 if not 0<a.music_gain<=1 or not 0<a.voice_gain<=2:raise SystemExit('REFUSE_INVALID_GAINS')
 video_dur=duration(a.video); voice_dur=duration(a.narration)
 if video_dur<40 or voice_dur<20:raise SystemExit('REFUSE_UNEXPECTED_DURATIONS')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n','-i',str(a.video),'-i',str(a.narration)]
 if a.music:
  cmd+=['-stream_loop','-1','-i',str(a.music)]
  # Music is ducked whenever Vera speaks, then recovers for the final end-card.
  graph=(f'[1:a]aresample=48000,volume={a.voice_gain},asplit=2[voice][side];'
         f'[2:a]aresample=48000,volume={a.music_gain},afade=t=in:st=0:d=0.8,afade=t=out:st={max(0,video_dur-2):.3f}:d=2[bed];'
         '[bed][side]sidechaincompress=threshold=0.025:ratio=5:attack=35:release=420[ducked];'
         '[voice][ducked]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]')
 else:
  graph=f'[1:a]aresample=48000,volume={a.voice_gain},apad,alimiter=limit=0.95[a]'
 cmd+=['-filter_complex',graph,'-map','0:v:0','-map','[a]','-t',f'{video_dur:.3f}',
       '-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(a.output)]
 subprocess.run(cmd,check=True)
 result={'state':'AWAITING_AUDIO_REVIEW','source_video':str(a.video),'source_video_sha256':hash_file(a.video),'original_narration':str(a.narration),'narration_sha256':hash_file(a.narration),'narration_duration_seconds':voice_dur,'video_duration_seconds':video_dur,'music':str(a.music) if a.music else None,'music_sha256':hash_file(a.music) if a.music else None,'mode':'voice_only' if a.voice_only else 'new_music_ducked','output':str(a.output),'output_sha256':hash_file(a.output),'video_stream_copied':True,'voice_cutoff_fade_removed':True,'release_authorized':False}
 receipt=a.output.with_suffix('.receipt.json');receipt.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'output':str(a.output),'receipt':str(receipt),'narration_seconds':voice_dur,'video_seconds':video_dur,'status':result['state']},indent=2))
if __name__=='__main__':main()
