"""Local product-review response custody. Diagnostics never authorize release."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import re
import types

EVIDENCE_SHA256 = 'ed986339db9db4b8d64d29fb835d4c6a6c27ed62fe0e7a5da673c651bd87cf31'


def validate_request(body: dict, prompt: str) -> list[str]:
    if str(body.get('reasoned_provider') or '').strip().lower() != 'ollama':
        raise ValueError('canonical_product_review_requires_local_ollama')
    if not isinstance(body.get('reasoned_model'), str) or not body['reasoned_model'].strip():
        raise ValueError('canonical_product_review_requires_explicit_model')
    if any(key in body for key in ('inject_provider_response', 'provider_timeout_ms')):
        raise ValueError('provider_injection_refused_in_product_review')
    limit = body.get('reasoned_max_predict', 1400)
    if type(limit) is not int or not 32 <= limit <= 4096:
        raise ValueError('invalid_product_review_prediction_bound')
    anchors = body.get('verified_review_anchors')
    if (not isinstance(anchors, list) or not 1 <= len(anchors) <= 1000
        or any(not isinstance(a, str) or re.fullmatch(r'[PC][1-9]\d*', a) is None for a in anchors)
        or len(set(anchors)) != len(anchors)):
        raise ValueError('invalid_review_anchor_registry')
    if any('[' + anchor + ']' not in prompt for anchor in anchors):
        raise ValueError('declared_review_anchor_absent_from_prompt')
    digest = body.get('verified_review_manuscript_sha256')
    if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise ValueError('invalid_review_manuscript_digest')
    return ['[' + anchor + ']' for anchor in anchors]


def _evidence_module():
    path = Path(__file__).resolve().with_name('response_evidence.py')
    if path.is_symlink() or path.resolve() != path:
        raise ValueError('canonical_response_evidence_source_escape')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EVIDENCE_SHA256:
        raise ValueError('canonical_response_evidence_source_digest_mismatch')
    module = types.ModuleType('_dio_product_response_evidence')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def attach_evidence(body: dict, prompt: str, payload: dict) -> dict:
    anchors = validate_request(body, prompt)
    result = copy.deepcopy(payload)
    if not isinstance(result.get('response'), str):
        raise ValueError('product_review_response_must_be_text')
    model = result.get('model') if isinstance(result.get('model'), str) else ''
    receipt = _evidence_module().examine(prompt=prompt, response=result['response'],
                                        model=model, evidence_anchors=anchors)
    checks = receipt['academic_evidence']['checks']
    checks['local_provider_completed'] = (result.get('reasoned_provider') == 'ollama'
        and result.get('reasoned_provider_status') == 'ok')
    checks['requested_model_matches'] = model == body['reasoned_model'].strip()
    receipt['academic_evidence']['passed'] = all(checks.values())
    receipt['declared_manuscript_sha256'] = body['verified_review_manuscript_sha256']
    receipt['manuscript_authority'] = 'CALLER_DECLARATION_R3_ARTIFACT_CHECK_REQUIRED'
    receipt['producer_source_owner'] = 'DIO-Full-Audit'
    receipt['producer_boundary_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    # The producer's existing heuristic judgments remain inspectable, but are
    # moved away from the response fields consumed as current release decisions.
    previous = {}
    for key in ('mandos_judgment', 'article_conformity', 'response_release_ledger',
                'raw_release_ledger', 'raw_mandos_judgment', 'raw_article_conformity', 'release_stage_trace'):
        if key in result:
            previous[key] = result.pop(key)
    result['legacy_unverified_diagnostics'] = previous
    result['legacy_diagnostics_authority'] = 'UNVERIFIED_HEURISTICS_NOT_RELEASE_AUTHORITY'
    result.update(response_evidence=receipt, mandos_judgment=receipt['mandos_judgment'],
                  article_conformity=receipt['article_conformity'])
    result['response_release_ledger'] = {
        'schema': 'dio.sophia.product_review_release.v1', 'status': 'HOLD',
        'release_authorized': False, 'constitutional_release_authorized': False,
        'reason': 'R2 diagnostics and R3 artifact integrity do not establish Mandos or Genesis approval.'}
    result['response_source'] = 'model_with_diagnostic_evidence'
    return result
