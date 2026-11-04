#!/usr/bin/env python3
"""Non-destructive Dicere V3 background removal proof and full review render.

Uses existing V3 face and scene artifacts; runs FFmpeg only. Does not modify originals.
"""
import argparse
import json
import subprocess
from pathlib import Path

DIO=Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit')
SRC=DIO/'media/dicere/debut/v3-repair'
NARRATION=DIO/'media/dicere/debut/dicere_vera_narration.wav'
MUSIC=DIO/'media/product_asset_packs/dio_creative_organs_site_matched_v2/receipts/SONORIS_DARKSYNTH_AMBIENT_V2_45S.wav'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=SRC)
    p.add_argument('--output',type=Path,default=DIO/'media/dicere/debut/v3-polish')
    p.add_argument('--full',action='store_true',help='Render 45s after reviewing 5s preview')
    p.add_argument('--similarity',type=float,default=0.065,help='Color key strength, default 0.065')
    p.add_argument('--blend',type=float,default=0.045,help='Softness, default 0.045')
    a=p.parse_args()
    if not 0.01<=a.similarity<=0.2 or not 0<=a.blend<=0.2:
        p.error('similarity and blend outside safe review ranges')
    face=a.source/'VESPER_V3_FACE_SILENT.mp4'
    scenes=[a.source/f'DICERE_SCENE_{i:02d}.png' for i in range(1,6 if a.full else 2)]
    need=[face,*scenes,NARRATION,MUSIC]
    missing=[str(x) for x in need if not x.is_file() or x.stat().st_size==0]
    if missing: p.error('Missing input:\n'+'\n'.join(missing))
    a.output.mkdir(parents=True,exist_ok=True)
    target=a.output/('DICERE_V3_POLISH_FULL_REVIEW.mp4' if a.full else 'DICERE_V3_KEY_PREVIEW_5S.mp4')
    if target.exists(): p.error(f'Output exists: {target}. Refusing overwrite.')
    duration=45 if a.full else 5
    cmd=['ffmpeg','-hide_banner','-loglevel','warning','-nostdin','-n']
    for scene in scenes:
        cmd+=['-loop','1','-framerate','25','-t',str(9 if a.full else 5),'-i',str(scene)]
    face_idx=len(scenes); voice_idx=face_idx+1; music_idx=face_idx+2
    cmd+=['-i',str(face),'-i',str(NARRATION),'-i',str(MUSIC)]
    if a.full:
        bg=''.join(f'[{i}:v]fps=25,scale=1920:1080,setsar=1[v{i}];' for i in range(5))+'[v0][v1][v2][v3][v4]concat=n=5:v=1:a=0[bg];'
    else:
        bg='[0:v]fps=25,scale=1920:1080,setsar=1[bg];'
    # RGB charcoal background of the face source is approximately #26252A.
    # We key only the *face layer*, not the whole composed film.
    graph=(bg+
        f'[{face_idx}:v]scale=480:480:flags=lanczos,format=rgba,'
        f'colorkey=0x26252a:{a.similarity:.3f}:{a.blend:.3f}[presenter];'
        '[bg][presenter]overlay=1320:535:shortest=1:format=auto,format=yuv420p[video];'
        f'[{music_idx}:a]aresample=48000,volume=0.32,afade=t=out:st=43:d=2[music];'
        f'[{voice_idx}:a]aresample=48000,volume=1.0,afade=t=out:st=36.5:d=0.7[voice];'
        '[music][voice]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]')
    cmd+=['-filter_complex',graph,'-map','[video]','-map','[a]','-t',str(duration),'-c:v','libx264',
          '-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
          '-movflags','+faststart',str(target)]
    print('SOURCE=',a.source,'\nTARGET=',target,'\nMODE=', 'FULL REVIEW' if a.full else '5 SECOND PREVIEW',flush=True)
    subprocess.run(cmd,check=True)
    data={'output':str(target),'status':'AWAITING_HUMAN_VISUAL_REVIEW',
          'key_color':'#26252A','similarity':a.similarity,'blend':a.blend,
          'source_face':str(face),'source_scenes':[str(x) for x in scenes],
          'release_authorized':False,'notes':'Potential dark hair or clothing erosion must be checked visually'}
    receipt=target.with_suffix('.receipt.json')
    if receipt.exists(): p.error(f'Receipt exists: {receipt}')
    receipt.write_text(json.dumps(data,indent=2)+'\n')
    print('RECEIPT=',receipt)

if __name__=='__main__':main()
