"""Verified local marketing inputs; branding never substitutes customer sources."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
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
    if spec and spec.get("mode") == "sonoris_review_candidate":
        return sonoris_review_music(spec, root=root)
    catalog = json.loads((root / 'config/media/music_catalog.json').read_text())
    candidates = catalog.get('tracks') or []
    if spec is not None:
        requested_id = str(spec.get('track_id') or '').strip()
        requested_path = str(spec.get('path') or '').strip()
        if requested_id:
            candidates = [row for row in candidates if str(row.get('id') or '') == requested_id]
        elif requested_path:
            requested = Path(requested_path).expanduser().resolve()
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
        for key in ('path', 'attribution', 'rights_receipt'):
            if key in spec and Path(str(spec[key] or '')).expanduser().resolve() != paths[key]:
                raise ValueError('Canonical music path mismatch: ' + key)
    volume = float((spec or {}).get('volume') or .10)
    if not math.isfinite(volume) or not .01 <= volume <= .15:
        raise ValueError('Canonical music volume must keep Vera narration intelligible')
    return {**(spec or {}), 'mode': 'rights_recorded', **{key: str(path) for key, path in paths.items()}, 'track_id': track['id'], 'sha256': actual, 'title': track['title'], 'artist': track['artist'], 'licence': track['licence_name'], 'licence_url': track['licence_url'], 'attribution_sha256': digest(paths['attribution']), 'rights_receipt_sha256': digest(paths['rights_receipt']), 'volume': volume, 'selection_basis': 'canonical_byte_verified_local_catalog', 'human_music_review_required': True}


def sonoris_review_music(spec: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    """Resolve one rendered Sonoris track as a held media-review candidate.

    This path intentionally does not confer a license or release authority. It
    exists so the campaign renderers can audition a Sonoris score in context.
    """
    lane = str(spec.get("lane") or "jobs")
    job_id = str(spec.get("job_id") or "")
    if lane not in {"jobs", "seeds"} or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", job_id):
        raise ValueError("Sonoris review music requires a valid rendered job ID and lane.")
    root = root.resolve()
    media_root = root / "media" / "sonoris" / ("studio_jobs" if lane == "jobs" else "genre_seed_library_v2")
    job_dir = (media_root / job_id).resolve()
    if not job_dir.is_relative_to(media_root.resolve()):
        raise ValueError("Sonoris review job path escaped its local media store.")
    receipt_path = job_dir / "SONORIS_STUDIO_RECEIPT.json"
    if not receipt_path.is_file():
        raise ValueError("Sonoris review job has no local composition receipt.")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("job_id") != job_id or receipt.get("audio_state") != "RENDERED":
        raise ValueError("Sonoris review candidate must be a rendered job with a matching receipt.")
    audio_meta = receipt.get("audio") or {}
    audio_name = str(audio_meta.get("mp3") or "")
    if Path(audio_name).name != audio_name or not audio_name.lower().endswith(".mp3"):
        raise ValueError("Sonoris review receipt does not name a safe MP3 output.")
    audio_path = (job_dir / audio_name).resolve()
    if not audio_path.is_relative_to(job_dir) or not audio_path.is_file():
        raise ValueError("Sonoris review audio is missing from its job directory.")
    actual = digest(audio_path)
    if actual != audio_meta.get("mp3_sha256"):
        raise ValueError("Sonoris review audio hash does not match its composition receipt.")
    if receipt.get("release_authorized") is not False or receipt.get("commercial_rights_verified") is not False:
        raise ValueError("Sonoris review receipt does not preserve its release and rights hold.")
    volume = float(spec.get("volume") or .10)
    if not math.isfinite(volume) or not .01 <= volume <= .15:
        raise ValueError("Sonoris review music volume must be between 0.01 and 0.15.")

    handoff_dir = root / "deliverables" / "sonoris_studio" / "media_handoffs" / f"{lane}-{job_id}"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    rights_path = handoff_dir / "SONORIS_MEDIA_REVIEW_RECEIPT.json"
    attribution_path = handoff_dir / "SONORIS_MEDIA_ATTRIBUTION.md"
    handoff = {
        "schema": "dio.sonoris.media_review_handoff.v1",
        "state": "LOCAL_MEDIA_REVIEW_ONLY",
        "source_job_id": job_id,
        "source_lane": lane,
        "source_receipt": str(receipt_path),
        "source_receipt_sha256": digest(receipt_path),
        "audio_path": str(audio_path),
        "audio_sha256": actual,
        "title": str(receipt.get("title") or job_id),
        "genre": receipt.get("genre"),
        "song_type": receipt.get("song_type"),
        "rights": {"commercial_use": False, "verified": False, "statement": "Source instrument/model licensing has not been cleared for this composition."},
        "human_sonic_review_required": True,
        "human_rights_review_required": True,
        "release_authorized": False,
        "publication_authorized": False,
        "authority_created": False,
    }
    if rights_path.is_file():
        existing = json.loads(rights_path.read_text(encoding="utf-8"))
        if existing.get("audio_sha256") != actual or existing.get("source_receipt_sha256") != handoff["source_receipt_sha256"]:
            raise ValueError("Existing Sonoris media handoff no longer matches the source render.")
    else:
        rights_path.write_text(json.dumps(handoff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    attribution = (
        f"# Sonoris composition candidate: {handoff['title']}\n\n"
        f"- Source job: `{job_id}` ({lane})\n- Genre: `{receipt.get('genre')}` / `{receipt.get('song_type')}`\n"
        f"- Audio SHA-256: `{actual}`\n- Source receipt: `{receipt_path}`\n\n"
        "This is an original local Sonoris review candidate. Instrument and model licensing has not been verified. "
        "For internal media preview and human review only; commercial use, publication, and release are not authorized.\n"
    )
    if attribution_path.is_file() and attribution_path.read_text(encoding="utf-8") != attribution:
        raise ValueError("Existing Sonoris attribution note differs from the current source render.")
    if not attribution_path.exists():
        attribution_path.write_text(attribution, encoding="utf-8")
    return {
        **spec,
        "mode": "sonoris_review_candidate",
        "path": str(audio_path),
        "attribution": str(attribution_path),
        "rights_receipt": str(rights_path),
        "track_id": f"sonoris_{lane}_{job_id}",
        "sha256": actual,
        "title": handoff["title"],
        "artist": "DIO Sonoris",
        "licence": "Internal review only · rights unverified",
        "volume": volume,
        "selection_basis": "explicit_operator_selected_sonoris_review_candidate",
        "commercial_use": False,
        "commercial_rights_verified": False,
        "human_music_review_required": True,
        "release_authorized": False,
        "publication_authorized": False,
        "sonoris_handoff": handoff,
    }


def directed_music(*, family: str, pacing: str, volume: float, context: str) -> dict[str, Any]:
    """Use Sonoris editorial direction for standalone narrated video pipelines."""
    from scripts.lingua_music_projection import select_projection_music
    return select_projection_music(
        {'pacing': pacing, 'voice': {'required': True},
         'music': {'family': family, 'keywords': [], 'volume': volume}},
        {'name': context}, {'name': context}, context,
    )


def verify_voice_receipt(receipt: dict[str, Any], audio: Path) -> None:
    if (receipt.get('backend') != 'pocket_tts' or receipt.get('voice_url') != 'vera' or receipt.get('profile_id') != 'vera_pocket_public' or receipt.get('audio_sha256') != digest(audio)):
        raise ValueError('Vera voice receipt integrity mismatch')
    provenance = receipt.get('model_provenance') or {}
    if provenance.get('voice_id') != 'vera' or not provenance.get('model_id'):
        raise ValueError('Vera model provenance evidence is missing')
