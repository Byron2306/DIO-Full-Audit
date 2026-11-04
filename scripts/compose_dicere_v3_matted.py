#!/usr/bin/env python3
"""Non-destructive masked-presenter Dicere V3 review compositor.

Uses the human-reviewed RMBG matte (static starting point) against the original
V3 full-length face source, not the failed color-key film. No GPU inference.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

DIO = Path('/data/byron/dio-wsl-restored-20261015/home/byron/DIO-Full-Audit')
VESPER = Path('/data/byron/lilith-local/vesper-github-lipsync')
SCENE_DIR = DIO / 'media/dicere/debut/v3-repair'
FACE = SCENE_DIR / 'VESPER_V3_FACE_SILENT.mp4'
MASK = VESPER / 'presence/v3-segmentation-lab/vesper_rmbg_mask.png'
NARRATION = DIO / 'media/dicere/debut/dicere_vera_narration.wav'
MUSIC = DIO / 'media/product_asset_packs/dio_creative_organs_site_matched_v2/receipts/SONORIS_DARKSYNTH_AMBIENT_V2_45S.wav'
OUTPUT_ROOT = DIO / 'media/dicere/debut/v3-matted'


def check(path):
    if not path.is_file() or not path.stat().st_size:
        raise SystemExit(f'REFUSE_MISSING_SOURCE: {path}')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def ffprobe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries',
        'stream=codec_type,width,height,r_frame_rate:format=duration',
        '-of', 'json', str(path)], text=True))


def run(preview):
    scenes = [SCENE_DIR / f'DICERE_SCENE_{i:02}.png' for i in range(1, 6)]
    sources = [scenes[0], FACE, MASK, NARRATION, MUSIC] if preview else scenes + [FACE, MASK, NARRATION, MUSIC]
    for path in sources:
        check(path)
    # Verify source dimensions before ffmpeg interprets the mask.
    from PIL import Image
    with Image.open(MASK) as img:
        if img.size != (1254, 1254):
            raise SystemExit(f'REFUSE_MASK_SIZE: {img.size}')
    face_meta = ffprobe(FACE)
    video = next((s for s in face_meta['streams'] if s['codec_type'] == 'video'), {})
    if (video.get('width'), video.get('height'), video.get('r_frame_rate')) != (1254, 1254, '25/1'):
        raise SystemExit('REFUSE_FACE_FORMAT_MISMATCH')
    if float(face_meta['format']['duration']) < (4.99 if preview else 44.99):
        raise SystemExit('REFUSE_FACE_DURATION')
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_ROOT / ('DICERE_V3_MATTE_PREVIEW_5S.mp4' if preview else 'DICERE_V3_MATTE_FULL_REVIEW.mp4')
    receipt = output.with_suffix('.receipt.json')
    if output.exists() or receipt.exists():
        raise SystemExit(f'REFUSE_OUTPUT_EXISTS: {output}')
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n']
    if preview:
        cmd += ['-loop', '1', '-framerate', '25', '-t', '5', '-i', str(scenes[0])]
        face_idx, mask_idx, nar_idx, music_idx = 1, 2, 3, 4
    else:
        for scene in scenes:
            cmd += ['-loop', '1', '-framerate', '25', '-t', '9', '-i', str(scene)]
        face_idx, mask_idx, nar_idx, music_idx = 5, 6, 7, 8
    cmd += [
        '-i', str(FACE), '-loop', '1', '-framerate', '25', '-i', str(MASK),
        '-i', str(NARRATION), '-i', str(MUSIC)
    ]
    background = '[0:v]fps=25,scale=1920:1080,setsar=1[bg];' if preview else (
        ''.join(f'[{i}:v]fps=25,scale=1920:1080,setsar=1[s{i}];' for i in range(5))
        + '[s0][s1][s2][s3][s4]concat=n=5:v=1:a=0[bg];'
    )
    # Gray mask is the alpha channel, independently resized to the face overlay.
    # The background's rectangle is never chroma-keyed or subtracted by color.
    graph = (
        background
        + f'[{face_idx}:v]scale=480:480:flags=lanczos,setsar=1,format=rgb24[person];'
        + f'[{mask_idx}:v]scale=480:480:flags=lanczos,format=gray[alpha];'
        + '[person][alpha]alphamerge,format=rgba[cutout];'
        + '[bg][cutout]overlay=1320:535:shortest=1:format=auto,format=yuv420p[video];'
        + f'[{music_idx}:a]aresample=48000,volume=0.32,afade=t=out:st=43:d=2[music];'
        + f'[{nar_idx}:a]aresample=48000,volume=1.0,afade=t=out:st=36.5:d=0.7[voice];'
        + '[music][voice]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]'
    )
    cmd += [
        '-filter_complex', graph, '-map', '[video]', '-map', '[a]',
        '-t', '5' if preview else '45', '-c:v', 'libx264',
        '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(output)
    ]
    subprocess.run(cmd, check=True)
    output_info = ffprobe(output)
    seconds = float(output_info['format']['duration'])
    if abs(seconds - (5 if preview else 45)) > 0.10:
        raise SystemExit(f'REFUSE_OUTPUT_DURATION: {seconds}')
    data = {
        'schema': 'dio.dicere.v3_matted_review.v1',
        'state': 'AWAITING_HUMAN_VISUAL_REVIEW',
        'publication_authorized': False,
        'mask_method': 'static_human_reviewed_RMBG_1.4_mask',
        'temporal_edge_stability': 'UNVERIFIED',
        'face': str(FACE), 'face_sha256': sha(FACE),
        'mask': str(MASK), 'mask_sha256': sha(MASK),
        'scenes': [{'path': str(s), 'sha256': sha(s)} for s in (scenes[:1] if preview else scenes)],
        'output': str(output), 'output_sha256': sha(output),
        'duration_seconds': seconds,
        'notes': ['No color-key', 'Original rendered V3 facial video preserved',
                  'Existing narration and soundtrack preserved',
                  'Review hair and shoulder edges throughout; static matte may need motion tracking']
    }
    receipt.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'state': data['state'], 'output': str(output), 'receipt': str(receipt)}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--preview', action='store_true')
    group.add_argument('--full', action='store_true')
    args = p.parse_args()
    run(args.preview)
