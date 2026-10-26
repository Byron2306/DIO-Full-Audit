import copy
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'cross_folder_variants/Integritas-Mechanicus/A_CODE/arda_os/backend/services'


def load_boundary():
    path = SERVICES / 'canonical_product_review.py'
    assert path.is_file(), 'canonical producer response boundary is missing'
    spec = importlib.util.spec_from_file_location('canonical_review_boundary_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def request():
    return {'reasoned_provider': 'ollama', 'reasoned_model': 'granite3.3:2b',
        'reasoned_max_predict': 1400, 'verified_review_anchors': ['P1', 'C1'],
        'verified_review_manuscript_sha256': 'a' * 64}


def response():
    return {'response': 'The causal claim in [P1] needs support; verify [C1].',
        'model': 'granite3.3:2b', 'reasoned_provider': 'ollama', 'reasoned_provider_status': 'ok',
        'mandos_judgment': {'passed': True}, 'article_conformity': {'summary': {'all_passed': True}},
        'response_release_ledger': {'release_authorized': True},
        'release_stage_trace': {'final': {'passed': True}}}


def test_exact_producer_response_reaches_canonical_custody_without_authority():
    boundary = load_boundary(); body = request(); original = response()
    output = boundary.attach_evidence(body, 'Review [P1] and [C1].', original)
    receipt = output['response_evidence']
    assert receipt['response_sha256'] == hashlib.sha256(original['response'].encode()).hexdigest()
    assert receipt['academic_evidence']['passed'] is True
    assert output['mandos_judgment']['passed'] is False
    assert output['article_conformity']['summary']['all_passed'] is False
    assert output['response_release_ledger']['release_authorized'] is False
    assert 'release_stage_trace' not in output
    assert output['legacy_unverified_diagnostics']['mandos_judgment']['passed'] is True
    assert original == response(), 'do not mutate shared producer diagnostic state'
    from adapters.sophia.canonical_sources import load_service
    custody = load_service('sophia_custody')
    raw = dict(manuscript=b'document', rubric=b'rubric', zpd_guidance=b'guidance')
    expected = {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()}
    expected.update(prompt=receipt['prompt_sha256'], response=receipt['response_sha256'])
    result = custody.verify_custody(**raw, prompt='Review [P1] and [C1].', response=output['response'],
        requested_model=body['reasoned_model'], actual_model=output['model'], receipt=receipt, expected_digests=expected)
    assert result['passed'] is True
    assert result['constitutional_release_authorized'] is False
    result2 = custody.verify_custody(**raw, prompt='Review [P1] and [C1].', response='changed',
        requested_model=body['reasoned_model'], actual_model=output['model'], receipt=receipt, expected_digests=expected)
    assert result2['passed'] is False


@pytest.mark.parametrize('mutation', [
    {'reasoned_provider': 'gemini'}, {'reasoned_model': ''},
    {'verified_review_anchors': ['P1', 'P1']}, {'verified_review_anchors': ['P0']},
    {'verified_review_anchors': ['P99']}, {'verified_review_manuscript_sha256': 'missing'},
    {'inject_provider_response': 'pretend provider'}, {'provider_timeout_ms': 0},
    {'reasoned_max_predict': True}, {'reasoned_max_predict': 50000},
])
def test_invalid_product_request_refuses_before_provider(mutation):
    boundary = load_boundary(); body = request(); body.update(mutation)
    with pytest.raises(ValueError):
        boundary.validate_request(body, 'Review [P1] and [C1].')


@pytest.mark.parametrize('mutation', [
    {'response': 'No anchors.'}, {'model': 'wrong-model'},
    {'reasoned_provider_status': 'unavailable'}, {'reasoned_provider': 'remote'},
])
def test_bad_provider_or_response_is_retained_as_failed_diagnostic(mutation):
    boundary = load_boundary(); result = response(); result.update(mutation)
    output = boundary.attach_evidence(request(), 'Review [P1] and [C1].', result)
    assert output['response_evidence']['academic_evidence']['passed'] is False
    assert output['response_release_ledger']['release_authorized'] is False


def test_evidence_source_tampering_or_missing_source_has_no_donor_fallback(tmp_path):
    boundary = load_boundary()
    path = tmp_path / 'canonical_product_review.py'; path.write_text('stand-in location')
    boundary.__file__ = str(path)
    with pytest.raises((ValueError, FileNotFoundError)):
        boundary.attach_evidence(request(), 'Review [P1] and [C1].', response())
    path.with_name('response_evidence.py').write_text('raise RuntimeError("must never execute")')
    with pytest.raises(ValueError, match='source_digest_mismatch'):
        boundary.attach_evidence(request(), 'Review [P1] and [C1].', response())


def load_server():
    spec = importlib.util.spec_from_file_location('canonical_producer_server_test', SERVICES / 'presence_server.py')
    server = importlib.util.module_from_spec(spec); spec.loader.exec_module(server)
    assert hasattr(server, '_canonical_product_review_boundary'), 'producer is not wired to the canonical boundary'
    return server


def test_actual_handler_rejects_remote_product_before_any_provider(monkeypatch):
    server = load_server()
    monkeypatch.setattr(server, '_get_covenant_manifest', lambda: {'state': 'sealed'})
    monkeypatch.setattr(server, '_get_session_token', lambda: 'fixture-session')
    def forbid(*args, **kwargs):
        raise AssertionError('provider must not run for an invalid product request')
    monkeypatch.setattr(server, 'remote_chat_generate', forbid)
    monkeypatch.setattr(server, 'ollama_generate', forbid)
    handler = object.__new__(server.PresenceHandler); output = []
    handler._json_response = lambda payload, code=200, **kwargs: output.append((code, payload))
    body = request(); body.update(text='Review [P1] and [C1].', session_token='fixture-session',
        reasoned_provider='gemini', dio_product_review_lane=True, reasoned_integrity_lane=True,
        document_evidence_task='dio_sophia_academic_review',
        document_evidence={'documents': [{'source_name': 'fixture'}]},
        client_context={'ui_surface': 'dio_sophia_review'})
    handler._handle_speak(body)
    assert output[-1][0] == 422
    assert output[-1][1]['reason'] == 'canonical_product_review_requires_local_ollama'


def test_producer_boundary_source_tamper_refuses_before_execution(tmp_path):
    server = load_server()
    fake = tmp_path / 'presence_server.py'; fake.write_text('location fixture')
    server.__file__ = str(fake)
    fake.with_name('canonical_product_review.py').write_text('raise RuntimeError("must not run")')
    with pytest.raises(ValueError, match='source_digest_mismatch'):
        server._canonical_product_review_boundary()


@pytest.mark.parametrize('passthrough', [False, True])
def test_actual_producer_handler_emits_response_bound_evidence(monkeypatch, passthrough):
    server = load_server()
    monkeypatch.setattr(server, '_get_covenant_manifest', lambda: {'state': 'sealed'})
    monkeypatch.setattr(server, '_get_session_token', lambda: 'fixture-session')
    monkeypatch.setattr(server, '_get_mandos', lambda: None)
    monkeypatch.setattr(server, '_presence_choir_sweep', lambda *a, **kw: {'spectrum': {'global': 1}, 'status': 'test_fixture'})
    monkeypatch.setattr(server, '_triune_check', lambda *a, **kw: {'final_verdict': 'ALLOW', 'status': 'test_fixture_not_live_proof'})
    monkeypatch.setattr(server, '_assessment_ecology', None)
    for name in ['_log_encounter', '_persist_developmental_encounter', '_persist_relational_memory', '_update_session_source_pool']:
        monkeypatch.setattr(server, name, lambda *a, **kw: None)
    monkeypatch.setattr(server, '_auto_integrity_check', lambda *a, **kw: {})
    monkeypatch.setattr(server, 'FEATURE_PASSTHROUGH_MODE', passthrough)
    calls = []
    def local_provider(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return {'response': 'The causal claim [P1] needs stronger support; verify [C1].',
                'provider': 'ollama', 'model': 'granite3.3:2b', 'status': 'ok'}
    monkeypatch.setattr(server, 'ollama_generate', local_provider)
    handler = object.__new__(server.PresenceHandler); output = []
    handler._json_response = lambda payload, code=200, **kwargs: output.append((code, payload))
    body = request(); body.update(text='Examine the causal claim [P1] and its evidence [C1].',
        session_token='fixture-session', dio_product_review_lane=True, reasoned_integrity_lane=True,
        document_evidence_task='dio_sophia_academic_review',
        document_evidence={'documents': [{'source_name': 'fixture', 'extracted_text': 'A causal claim.'}]},
        client_context={'ui_surface': 'dio_sophia_review'},
        disable_continuity_memory=True, disable_world_events=True, disable_reentry_behavior=True)
    handler._handle_speak(body)
    assert len(calls) == 1
    assert calls[0][0] == body['text']
    assert calls[0][1]['model'] == 'granite3.3:2b'
    result = output[-1][1]
    assert output[-1][0] == 200
    assert result['response_evidence']['response_sha256'] == hashlib.sha256(result['response'].encode()).hexdigest()
    assert result['response_evidence']['prompt_sha256'] == hashlib.sha256(body['text'].encode()).hexdigest()
    assert result['mandos_judgment']['passed'] is False
