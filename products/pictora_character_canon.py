"""Read-only, hash-pinned Pictora character recipes. No ComfyUI execution."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'deliverables/pictora_image_editor/character_canons/lilith-candidate-v1.json'
EXPECTED_SHA256 = 'ac0bb724cc3dde6ac0fb8d1be1654a46f4998a60e7b9aef7def1384b9dcf76b9'

def catalog() -> dict:
    raw = RECIPE.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != EXPECTED_SHA256:
        raise ValueError('REFUSE_CHARACTER_CANON_HASH_DRIFT')
    recipe = json.loads(raw)
    if recipe.get('schema') != 'dio.pictora.character_canon_recipe.v1':
        raise ValueError('REFUSE_CHARACTER_CANON_SCHEMA')
    if recipe.get('id') != 'lilith_candidate_v1' or recipe.get('approval') != 'candidate_unapproved':
        raise ValueError('REFUSE_CHARACTER_CANON_STATUS')
    return {
        'schema': 'dio.pictora.character_canon_catalog.v1',
        'policy': 'text-only; candidate unapproved; no reference image conditioning; review and license gates unchanged',
        'recipes': [{**recipe, 'sha256': actual}],
    }
