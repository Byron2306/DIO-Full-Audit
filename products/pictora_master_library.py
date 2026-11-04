"""Read-only registry for local Pictora master renders. No image generation."""
from __future__ import annotations
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
STORE = HERE / 'deliverables/pictora_image_editor/master_library'
CATALOG = STORE / 'catalog.json'
HEX_ID = re.compile(r'^[a-f0-9]{16}$')


def catalog() -> dict:
    if not CATALOG.is_file():
        return {'schema': 'dio.pictora.master_library.v1', 'assets': [], 'error': 'MASTER_LIBRARY_NOT_INSTALLED'}
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if data.get('schema') != 'dio.pictora.master_library.v1' or not isinstance(data.get('assets'), list):
        raise ValueError('Invalid master-library catalog')
    # No absolute filesystem paths in browser JSON.
    return data


def thumbnail(asset_id: str) -> bytes | None:
    if not HEX_ID.fullmatch(asset_id):
        return None
    data = catalog()
    if not any(a.get('id') == asset_id for a in data['assets']):
        return None
    path = STORE / 'thumbs' / (asset_id + '.jpg')
    return path.read_bytes() if path.is_file() else None
