#!/usr/bin/env python3
"""DIO Gilded house-style smoke renderer. Representation only; never proof of claims."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'config/media/dio_gilded_house_style.json'


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify(root: Path = ROOT) -> dict:
    profile = json.loads((root / 'config/media/dio_gilded_house_style.json').read_text())
    manifest_path = root / profile['source_manifest']
    manifest = json.loads(manifest_path.read_text())
    if profile['source_pack_id'] != manifest['pack_id'] or manifest['generated_as_proof'] != 'REFUSE':
        raise ValueError('asset manifest authority mismatch')
    if manifest.get('remote_runtime_fetch') != 'REFUSE' or manifest.get('rights') != {'commercial_use': True, 'status': 'INTERNAL_ORIGINAL'}:
        raise ValueError('asset rights/remote provenance mismatch')
    base = manifest_path.parent.resolve()
    records = []
    for asset in manifest['assets']:
        path = (base / asset['path']).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError(f'missing or escaped asset: {asset["asset_id"]}')
        actual = 'sha256:' + digest(path)
        if actual != asset['sha256']:
            raise ValueError(f'asset hash mismatch: {asset["asset_id"]}')
        with Image.open(path) as im:
            if im.size != (asset['width'], asset['height']):
                raise ValueError(f'asset dimensions mismatch: {asset["asset_id"]}')
            alpha = ('A' in im.getbands() or 'transparency' in im.info)
            if alpha != asset['alpha']:
                raise ValueError(f'asset alpha mismatch: {asset["asset_id"]}')
        records.append({'asset_id': asset['asset_id'], 'sha256': actual})
    return {'profile_id': profile['profile_id'], 'source_pack_id': manifest['pack_id'], 'manifest_sha256': digest(manifest_path), 'verified_assets': len(records), 'assets': records, 'voice': profile['voice'], 'authority': profile['authority']}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'):
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def poster(root: Path, path: Path, verification: dict, title: str) -> dict:
    manifest = json.loads((root / 'media/product_asset_packs/homs_corpo_cult_v1/pack.json').read_text())
    source = next(a for a in manifest['assets'] if a['asset_id'] == 'HOMS_COMMAND_HALL')
    base = root / 'media/product_asset_packs/homs_corpo_cult_v1'
    with Image.open(base / source['path']) as im:
        canvas = im.convert('RGB').resize((1600, 900), Image.Resampling.LANCZOS)
    wash = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(wash)
    d.rectangle((0, 460, 1600, 900), fill=(5, 7, 10, 205))
    d.rectangle((98, 485, 107, 830), fill=(178, 139, 66, 255))
    canvas = Image.alpha_composite(canvas.convert('RGBA'), wash)
    d = ImageDraw.Draw(canvas)
    d.text((145, 505), 'DIO  /  SOVEREIGN SYSTEMS', fill='#D5B878', font=font(34))
    d.text((145, 575), title[:35], fill='#F1E4CE', font=font(72))
    d.text((145, 708), 'EVIDENCE BEFORE AUTHORITY', fill='#DBC79D', font=font(29))
    d.text((145, 774), 'Visual demonstration  •  Human release required', fill='#B9B4AB', font=font(23))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(path, quality=93, optimize=True)
    return {'path': str(path), 'sha256': digest(path), 'width': 1600, 'height': 900, 'source_asset_id': source['asset_id'], 'source_sha256': source['sha256']}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=Path.home() / 'dio-gilded-proof')
    parser.add_argument('--title', default='Intelligence, Governed')
    args = parser.parse_args()
    verification = verify()
    if not args.verify_only:
        verification['poster'] = poster(ROOT, args.output_dir / 'DIO_GILDED_POSTER_PROOF.jpg', verification, args.title)
    verification['external_action_executed'] = False
    verification['commercial_release_authorized'] = False
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'DIO_GILDED_PROOF_RECEIPT.json').write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps({'verified_assets': verification['verified_assets'], 'poster': verification.get('poster', {}).get('path'), 'voice_default': verification['voice']['voice_url'], 'release': verification['authority']['publication']}))


if __name__ == '__main__':
    main()
