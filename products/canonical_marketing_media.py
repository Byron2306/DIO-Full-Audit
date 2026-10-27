"""Verified local marketing inputs; branding never substitutes customer sources."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_golden_pack(root: Path = ROOT) -> dict[str, Any]:
    from scripts.dio_gilded_media_proof import verify
    profile = json.loads((root / 'config/media/dio_gilded_house_style.json').read_text())
    manifest = root / profile['source_manifest']
    if not manifest.is_file():
        raise ValueError('DIO Gilded asset-pack manifest is unavailable')
    if digest(manifest) != profile.get('source_manifest_sha256'):
        raise ValueError('DIO golden source manifest hash mismatch')
    result = verify(root)
    if not result['verified_assets']:
        raise ValueError('DIO golden source pack is empty')
    return {**result, 'manifest': str(manifest.resolve())}


def apply_golden_identity(source: Image.Image, *, brand_owner: str = 'customer', root: Path = ROOT) -> tuple[Image.Image, dict[str, Any]]:
    if brand_owner != 'dio':
        return source.copy(), {'brand_owner': 'customer', 'customer_source_preserved': True}
    verification = verified_golden_pack(root)
    manifest_path = Path(verification['manifest'])
    manifest = json.loads(manifest_path.read_text())
    asset = next(row for row in manifest['assets'] if row['asset_id'] == 'DIO_EYE_PREMIUM')
    with Image.open(manifest_path.parent / asset['path']) as image:
        eye = image.convert('RGBA')
    width, height = source.size
    side = max(32, round(min(width, height) * .14))
    eye = eye.resize((side, side), Image.Resampling.LANCZOS)
    canvas = source.convert('RGBA')
    margin = max(12, round(min(width, height) * .025))
    canvas.alpha_composite(eye, (width - side - margin, margin))
    return canvas.convert('RGB'), {'brand_owner': 'dio', 'asset_id': asset['asset_id'], 'source_sha256': asset['sha256'], 'manifest_sha256': verification['manifest_sha256'], 'profile_id': verification['profile_id']}


def approved_music(spec: dict[str, Any] | None = None, *, root: Path = ROOT) -> dict[str, Any]:
    """Resolve a pinned local track and check rights against its actual receipt."""
    catalog = json.loads((root / 'config/media/music_catalog.json').read_text())
    candidates = catalog.get('tracks') or []
    if spec is not None:
        requested = Path(str(spec.get('path') or '')).expanduser().resolve()
        candidates = [row for row in candidates if (root / row['path']).resolve() == requested]
    if not candidates:
        raise ValueError('Select a canonical music catalog track with verified rights')
    track = candidates[0]
    paths = {key: (root / track[key]).resolve() for key in ('path', 'attribution', 'rights_receipt')}
    if any(not path.is_relative_to(root.resolve()) or not path.is_file() for path in paths.values()):
        raise ValueError('Canonical music or rights evidence is missing or escaped')
    receipt = json.loads(paths['rights_receipt'].read_text())
    rights = receipt.get('rights') or {}
    if any(rights.get(key) is not True for key in ('commercial_use', 'adaptation_allowed', 'attribution_required', 'passed')):
        raise ValueError('Canonical music rights receipt does not permit commercial adaptation')
    actual = digest(paths['path'])
    if actual != track['sha256'] or actual != receipt.get('sha256'):
        raise ValueError('Canonical music rights are not bound to these audio bytes')
    if any(receipt.get(key) != track.get(key) for key in ('licence_name', 'licence_url', 'source_url')):
        raise ValueError('Canonical music licence evidence mismatch')
    attribution = paths['attribution'].read_text()
    if not attribution.strip() or track['artist'] not in attribution or track['licence_url'] not in attribution:
        raise ValueError('Canonical music attribution evidence is incomplete')
    for key in ('attribution', 'rights_receipt'):
        if digest(paths[key]) != track.get(key + '_sha256'):
            raise ValueError('Canonical music rights/attribution evidence hash mismatch')
    if spec:
        for key in ('attribution', 'rights_receipt'):
            if Path(str(spec.get(key) or '')).expanduser().resolve() != paths[key]:
                raise ValueError('Canonical music rights/attribution path mismatch')
    volume = float((spec or {}).get('volume') or .10)
    if not math.isfinite(volume) or not .01 <= volume <= .15:
        raise ValueError('Canonical music volume must keep Vera narration intelligible')
    return {**(spec or {}), 'mode': 'rights_recorded', **{key: str(path) for key, path in paths.items()}, 'track_id': track['id'], 'sha256': actual, 'title': track['title'], 'artist': track['artist'], 'licence': track['licence_name'], 'licence_url': track['licence_url'], 'attribution_sha256': digest(paths['attribution']), 'rights_receipt_sha256': digest(paths['rights_receipt']), 'volume': volume, 'selection_basis': 'canonical_byte_verified_local_catalog', 'human_music_review_required': True}


def verify_voice_receipt(receipt: dict[str, Any], audio: Path) -> None:
    if (receipt.get('backend') != 'pocket_tts' or receipt.get('voice_url') != 'vera' or receipt.get('profile_id') != 'vera_pocket_public' or receipt.get('audio_sha256') != digest(audio)):
        raise ValueError('Vera voice receipt integrity mismatch')
    provenance = receipt.get('model_provenance') or {}
    if provenance.get('voice_id') != 'vera' or not provenance.get('model_id'):
        raise ValueError('Vera model provenance evidence is missing')
