"""Non-authoritative, fail-closed Sophia response evidence receipt.

This module does not implement Mandos approval or complete Genesis Article adjudication.
"""
from __future__ import annotations
import hashlib
import re
from typing import Any


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def examine(*, prompt: str, response: str, model: str, evidence_anchors: list[str] | None = None) -> dict[str, Any]:
    """Record evidence-bound checks, never elevate heuristic checks to constitutional approval."""
    prompt = prompt if isinstance(prompt, str) else ''
    response = response if isinstance(response, str) else ''
    model = model if isinstance(model, str) else ''
    if evidence_anchors is None:
        anchors = sorted(set(re.findall(r'\[(?:P|C)\d+\]', prompt)))
    else:
        if not isinstance(evidence_anchors, list) or any(
            not isinstance(a, str) or
            not re.fullmatch(r'\[(?:P|C)[1-9]\d*\]', a)
            for a in evidence_anchors
        ):
            raise ValueError("invalid_explicit_evidence_anchors")
        anchors = sorted(set(evidence_anchors))
    used = sorted(set(re.findall(r'\[(?:P|C)\d+\]', response)))
    unsupported = sorted(set(used) - set(anchors))
    missing = sorted(set(anchors) - set(used))
    reasoning_leak = bool(re.search(r'</?think>|\bthe user is asking\b|\blet me think\b', response, flags=re.I))
    evidence_checks = {
        'nonempty_response': bool(response.strip()),
        'model_bound': bool(model.strip()),
        'no_unsupported_anchors': not unsupported,
        'uses_provided_anchors': bool(set(anchors) & set(used)),
        'no_thinking_leak': not reasoning_leak,
    }
    return {
        'schema': 'dio.sophia.response-evidence.v1',
        'authority': 'DIAGNOSTIC_ONLY_NOT_CONSTITUTIONAL_APPROVAL',
        'prompt_sha256': _digest(prompt),
        'response_sha256': _digest(response),
        'model': model,
        'academic_evidence': {
            'checks': evidence_checks,
            'passed': all(evidence_checks.values()),
            'provided_anchors': anchors,
            'used_anchors': used,
            'unsupported_anchors': unsupported,
            'missing_anchors': missing,
            'limitations': [
                'Checks only excerpt/prompt-visible anchors, not a full attached manuscript.',
                'Does not verify external citations, rubric scoring, human authorship, or academic merit.',
            ],
        },
        'mandos_judgment': {
            'passed': False,
            'status': 'NOT_EVALUATED',
            'reason': 'Existing MandosInspector audits substrate absence, not academic output.',
            'response_sha256': _digest(response),
        },
        'article_conformity': {
            'summary': {'all_passed': False, 'status': 'NOT_EVALUATED'},
            'reason': 'No complete, response-bound Genesis Article evaluator established.',
            'response_sha256': _digest(response),
            'articles': [],
        },
    }


def verify(receipt: dict, *, prompt: str, response: str, model: str) -> bool:
    """Receipt integrity check; digest equality alone is not authentication/signature."""
    return (
        isinstance(receipt, dict)
        and receipt.get('schema') == 'dio.sophia.response-evidence.v1'
        and receipt.get('prompt_sha256') == _digest(prompt)
        and receipt.get('response_sha256') == _digest(response)
        and receipt.get('model') == model
        and receipt.get('mandos_judgment', {}).get('passed') is False
        and receipt.get('article_conformity', {}).get('summary', {}).get('all_passed') is False
    )
