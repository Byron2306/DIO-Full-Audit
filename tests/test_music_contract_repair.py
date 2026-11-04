"""The canonical ID lookup and caller-provided paths must both remain safe."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / 'products/canonical_marketing_media.py'
spec = importlib.util.spec_from_file_location('music_custody_under_test', SOURCE)
assert spec and spec.loader
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)

PROJECTION_SOURCE = Path(__file__).resolve().parents[1] / 'scripts/lingua_music_projection.py'
projection_spec = importlib.util.spec_from_file_location('music_selector_under_test', PROJECTION_SOURCE)
assert projection_spec and projection_spec.loader
projection = importlib.util.module_from_spec(projection_spec)
projection_spec.loader.exec_module(projection)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def catalog_root(tmp_path: Path) -> Path:
    (tmp_path / 'config/media').mkdir(parents=True)
    media_dir = tmp_path / 'media/music_catalog'
    media_dir.mkdir(parents=True)
    audio = media_dir / 'track.ogg'
    audio.write_bytes(b'OggS synthetic fixture only')
    attribution = media_dir / 'ATTRIBUTION.md'
    attribution.write_text('Artist Name is licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/')
    receipt = media_dir / 'RIGHTS.json'
    receipt.write_text(json.dumps({
        'sha256': _sha(audio),
        'source_url': 'https://example.invalid/source',
        'licence_name': 'CC BY 4.0',
        'licence_url': 'https://creativecommons.org/licenses/by/4.0/',
        'rights': {'commercial_use': True, 'adaptation_allowed': True, 'attribution_required': True, 'passed': True},
    }))
    (tmp_path / 'config/media/music_catalog.json').write_text(json.dumps({'tracks': [{
        'id': 'track-1', 'title': 'Test Track', 'artist': 'Artist Name',
        'path': 'media/music_catalog/track.ogg',
        'attribution': 'media/music_catalog/ATTRIBUTION.md',
        'rights_receipt': 'media/music_catalog/RIGHTS.json',
        'sha256': _sha(audio), 'attribution_sha256': _sha(attribution),
        'rights_receipt_sha256': _sha(receipt),
        'source_url': 'https://example.invalid/source',
        'licence_name': 'CC BY 4.0',
        'licence_url': 'https://creativecommons.org/licenses/by/4.0/',
    }]}))
    return tmp_path


def test_id_only_lookup_resolves_attested_paths(catalog_root):
    result = music.approved_music({'track_id': 'track-1'}, root=catalog_root)
    assert result['track_id'] == 'track-1'
    assert result['path'] == str((catalog_root / 'media/music_catalog/track.ogg').resolve())
    assert result['rights_receipt_sha256'] == _sha(catalog_root / 'media/music_catalog/RIGHTS.json')


def test_id_and_mismatching_audio_path_refuses(catalog_root):
    with pytest.raises(ValueError, match='path mismatch'):
        music.approved_music({
            'track_id': 'track-1', 'path': str(catalog_root / 'other.ogg'),
            'attribution': str((catalog_root / 'media/music_catalog/ATTRIBUTION.md').resolve()),
            'rights_receipt': str((catalog_root / 'media/music_catalog/RIGHTS.json').resolve()),
        }, root=catalog_root)


def test_id_and_mismatching_rights_path_refuses(catalog_root):
    with pytest.raises(ValueError, match='path mismatch'):
        music.approved_music({'track_id': 'track-1', 'rights_receipt': str(catalog_root / 'forged.json')}, root=catalog_root)


def test_modified_rights_receipt_refuses_even_with_id_only(catalog_root):
    receipt = catalog_root / 'media/music_catalog/RIGHTS.json'
    data = json.loads(receipt.read_text())
    data['rights']['commercial_use'] = False
    receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='rights'):
        music.approved_music({'track_id': 'track-1'}, root=catalog_root)


def test_marketing_selector_uses_verified_canonical_id_only(catalog_root, monkeypatch):
    package = types.ModuleType('products')
    package.__path__ = []
    package.canonical_marketing_media = music
    monkeypatch.setitem(sys.modules, 'products', package)
    monkeypatch.setitem(sys.modules, 'products.canonical_marketing_media', music)
    monkeypatch.setattr(projection, 'ROOT', catalog_root)
    monkeypatch.delenv('DIO_CAMPAIGN_MUSIC', raising=False)
    selected = projection.select_projection_music(
        {'music': {'family': 'warm_upbeat', 'keywords': ['warm', 'community']}},
        {'name': 'HOMS'}, {'name': 'Educators'}, 'HOMS-educators',
    )
    assert selected['track_id'] == 'track-1'
    assert selected['selection_basis'] == 'canonical_byte_verified_local_catalog'
    assert selected['selection_method'] == 'sonoris_editorial_fit'
    assert selected['catalog_candidate_count'] == 1
