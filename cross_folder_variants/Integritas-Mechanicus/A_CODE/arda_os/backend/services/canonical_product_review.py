"""Local product-review response custody. Diagnostics never authorize release."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import re
import types

EVIDENCE_SHA256 = 'ed986339db9db4b8d64d29fb835d4c6a6c27ed62fe0e7a5da673c651bd87cf31'


def diagnostic_output_schema(body: dict) -> dict:
    """Constrain representation and source quoting; never grant approval."""
    registry = body.get('review_quote_registry')
    anchors = set(body.get('verified_review_anchors') or [])
    if (not isinstance(registry, dict) or not registry or len(registry) > 1000
        or any(key not in anchors or not isinstance(value, str) or not 1 <= len(value) <= 1800
               for key, value in registry.items())):
        raise ValueError('invalid_diagnostic_quote_registry')
    choices = []
    for anchor, quote in registry.items():
        if len(quote.strip()) < 12:
            continue
        choices.append({'type': 'object', 'properties': {
            'anchor': {'const': '[' + anchor + ']'}, 'quote': {'const': quote},
            'issue': {'type': 'string'}, 'action': {'type': 'string'}, 'limit': {'type': 'string'}},
            'required': ['anchor', 'quote', 'issue', 'action', 'limit'], 'additionalProperties': False})
    if not choices:
        raise ValueError('diagnostic_quote_registry_has_no_readable_span')
    return {'type': 'object', 'properties': {
        'assessment': {'type': 'string'},
        'comments': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {'oneOf': choices}},
        'evidence_limits': {'type': 'string'},
        'author_next_steps': {'type': 'array', 'minItems': 1, 'items': {'type': 'string'}}},
        'required': ['assessment', 'comments', 'evidence_limits', 'author_next_steps'], 'additionalProperties': False}


def validate_request(body: dict, prompt: str) -> list[str]:
    if body.get('dio_review_preparation_mode') not in (None, 'held_diagnostic_draft'):
        raise ValueError('unsupported_diagnostic_preparation_mode')
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
    if body.get('dio_review_preparation_mode') == 'held_diagnostic_draft':
        candidate = result.get('model_response_after_thinking')
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError('native_diagnostic_candidate_missing')
        # Chat expression shaping may truncate a structured model draft. Preserve
        # that shaped response for inspection and bind the complete native draft
        # as diagnostic evidence only. All constitutional/release holds below
        # remain in force; downstream source checks still decide draft usability.
        result['chat_shaped_response'] = result.get('response')
        result['response'] = candidate.strip()
        result['diagnostic_candidate_source'] = 'native_model_response_after_thinking'
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
