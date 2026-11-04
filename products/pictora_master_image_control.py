"""Verified, read-only access to an original asset already in Pictora's master catalog.

This module makes a visual nomination available as an IMAGE input; it does not
approve the image or enable a ControlNet. The source hash is checked on every read.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
STORE = HERE / 'deliverables/pictora_image_editor/master_library/catalog.json'
DEFAULT_ROOT = Path('/data/byron/lilith-local/atelier-reconstruction/evidence/runtime-data/lilith-master-renders')
HEX_ID = re.compile(r'^[a-f0-9]{16}$')
MIME = {'.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp'}
MAX_BYTES = 20 * 1024 * 1024  # Matches Pictora's existing upload limit.

class MasterImageRefusal(ValueError):
    pass

def verified_image(asset_id: str) -> tuple[bytes,str,str,str]:
    """Returns (content,mime,sha256,filename); raises on any provenance failure."""
    if not HEX_ID.fullmatch(asset_id):
        raise MasterImageRefusal('INVALID_MASTER_ID')
    data = json.loads(STORE.read_text(encoding='utf-8'))
    if data.get('schema') != 'dio.pictora.master_library.v1':
        raise MasterImageRefusal('INVALID_CATALOG')
    matches = [a for a in data.get('assets',[]) if a.get('id') == asset_id]
    if len(matches) != 1:
        raise MasterImageRefusal('MASTER_NOT_FOUND_OR_DUPLICATED')
    asset = matches[0]
    digest = asset.get('sha256','')
    if not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest) or not digest.startswith(asset_id):
        raise MasterImageRefusal('INVALID_MASTER_HASH')
    rel = Path(asset.get('relative_path',''))
    if rel.is_absolute() or not rel.parts or '..' in rel.parts or rel.suffix.lower() not in MIME:
        raise MasterImageRefusal('INVALID_MASTER_PATH')
    root = Path(os.environ.get('PICTORA_MASTER_SOURCE_ROOT',str(DEFAULT_ROOT))).resolve(strict=True)
    original = (root/rel).resolve(strict=True)
    if not original.is_relative_to(root) or not original.is_file():
        raise MasterImageRefusal('SOURCE_OUTSIDE_VERIFIED_ROOT')
    if original.stat().st_size > MAX_BYTES:
        raise MasterImageRefusal('MASTER_EXCEEDS_UPLOAD_LIMIT')
    image = original.read_bytes()
    if hashlib.sha256(image).hexdigest()!=digest:
        raise MasterImageRefusal('SOURCE_HASH_MISMATCH')
    return image,MIME[rel.suffix.lower()],digest,rel.name
