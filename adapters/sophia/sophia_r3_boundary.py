"""Bounded Sophia -> Metatron R3 custody bridge. No constitutional authority."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def capture(request: dict, document_path: Path, prompt: str, model: str) -> dict:
    """Capture the actual in-process request boundary BEFORE /api/speak."""
    manuscript = Path(document_path).read_bytes()
    rubric = ((request.get('homs_context') or {}).get('rubric'))
    zpd_path = request.get('zpd_guidance_path')
    if not manuscript or rubric is None or not zpd_path or not model or not prompt:
        raise ValueError('REFUSE: manuscript/rubric/ZPD/model/prompt evidence incomplete')
    zpd = Path(zpd_path).expanduser().resolve(strict=True).read_bytes()
    if not zpd:
        raise ValueError('REFUSE: empty ZPD guidance')
    expected = {
        'manuscript': sha(manuscript), 'rubric': sha(canonical(rubric)),
        'zpd_guidance': sha(zpd), 'prompt': sha(prompt.strip().encode('utf-8')),
    }
    return {'schema': 'dio.sophia.r3-preflight.v1',
            'authority': 'LOCAL_REQUEST_SNAPSHOT_NOT_INDEPENDENT_ATTESTATION',
            'expected_sha256': expected, 'requested_model': model,
            'document_path': str(Path(document_path).resolve()),
            'zpd_path': str(Path(zpd_path).expanduser().resolve()),
            'prompt': prompt.strip(), 'rubric': rubric,
            'outbound_prompt_sha256': sha(prompt.encode('utf-8'))}


def verify(pin: dict, request: dict, response: dict, *, metatron_root: str | None = None) -> dict:
    """Read supplied original files again; bind to exact Seraph API response."""
    model = pin['requested_model']
    text = str(response.get('response') or '')
    receipt = response.get('response_evidence')
    if not isinstance(receipt, dict):
        raise ValueError('REFUSE: R2 response_evidence absent')
    manuscript = Path(pin['document_path']).read_bytes()
    zpd = Path(pin['zpd_path']).read_bytes()
    rubric = (request.get('homs_context') or {}).get('rubric')
    if rubric is None:
        raise ValueError('REFUSE: rubric removed after preflight')
    if metatron_root is not None:
        raise ValueError('REFUSE: external_metatron_root_override_removed')
    from adapters.sophia.canonical_sources import load_service
    module = load_service('sophia_custody')
    expected = dict(pin['expected_sha256'])
    expected['response'] = sha(text.encode('utf-8'))
    result = module.verify_custody(
        manuscript=manuscript, rubric=canonical(rubric), zpd_guidance=zpd,
        prompt=pin['prompt'], response=text, requested_model=model,
        actual_model=str(response.get('model') or ''),
        receipt=receipt, expected_digests=expected)
    # Separate trust check: the R2 provider receipt must equal actual response digest.
    # The response expectation here is NOT independently attested; never claim it is.
    result['authority'] = 'IN_PROCESS_CUSTODY_CONSISTENCY_ONLY'
    result['preflight'] = {
        'schema': pin['schema'], 'requested_model': model,
        'expected_sha256': pin['expected_sha256'],
        'outbound_prompt_sha256': pin['outbound_prompt_sha256'],
        'authority': pin['authority'],
    }
    result['verifier_source_path'] = module.__file__
    result['verifier_source_sha256'] = sha(Path(module.__file__).read_bytes())
    result['source_owner'] = 'DIO-Full-Audit'
    result['response_sha256'] = expected['response']
    result['constitutional_release_authorized'] = False
    result['mandos_authority'] = 'NOT_EVALUATED'
    result['genesis_authority'] = 'NOT_EVALUATED'
    return result


def guarded_verify(pin: dict, request: dict, response: dict) -> dict:
    try:
        return verify(pin, request, response)
    except Exception as exc:
        return {'schema':'dio.sophia.custody.v1', 'status':'REFUSE', 'passed':False,
                'authority':'IN_PROCESS_CUSTODY_CONSISTENCY_ONLY',
                'error_type':type(exc).__name__, 'reason':str(exc),
                'constitutional_release_authorized':False,
                'mandos_authority':'NOT_EVALUATED', 'genesis_authority':'NOT_EVALUATED'}
