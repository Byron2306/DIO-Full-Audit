"""Exercise the actual public HTTP boundary over the canonical website protocol."""
import importlib.util
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from products import vesper_public_web as public
from presence_core import router

ORIGIN = 'https://dioworkflows.co.za'


@pytest.fixture
def api(tmp_path, monkeypatch):
    assert importlib.util.find_spec('scripts.serve_vesper_public_api'), 'restricted public API is missing'
    from scripts.serve_vesper_public_api import PublicVesperHandler
    root = tmp_path / 'state'
    monkeypatch.setenv('DIO_STATE_ROOT', str(root))
    monkeypatch.setenv('DIO_EVENT_LOG', str(root / 'events.jsonl'))
    monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS', '0')
    monkeypatch.setattr(public, 'STATE_ROOT', root / 'vesper/web_chat')
    monkeypatch.setattr(router, 'classify_with_ollama', lambda *a, **k:
                        {'intent': 'intake_request', 'product': None, 'confidence': .9})
    server = ThreadingHTTPServer(('127.0.0.1', 0), PublicVesperHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def request(path, *, method='GET', body=None, origin=ORIGIN, token=None,
                extra_headers=None, raw_body=None):
        headers = {'Host': 'api.dioworkflows.co.za'}
        if origin is not None:
            headers['Origin'] = origin
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if token:
            headers['X-Vesper-Session-Token'] = token
        if extra_headers:
            headers.update(extra_headers)
        data = raw_body if raw_body is not None else (
            json.dumps(body).encode() if body is not None else None
        )
        req = Request(f'http://127.0.0.1:{server.server_port}' + path,
                      data=data,
                      method=method, headers=headers)
        try:
            response = urlopen(req, timeout=20)
        except HTTPError as exc:
            response = exc
        with response:
            data = response.read()
            return response.code, dict(response.headers), json.loads(data) if data else None
    yield request
    server.shutdown()
    server.server_close()
    worker.join(timeout=5)


def test_public_session_accepts_exact_website_origin_and_preflight(api):
    status, headers, _ = api('/api/vesper/web/session', method='OPTIONS')
    assert status == 204
    assert headers['Access-Control-Allow-Origin'] == ORIGIN
    assert 'X-Vesper-Session-Token' in headers['Access-Control-Allow-Headers']
    status, headers, value = api('/api/vesper/web/session', method='POST', body={'surface': 'dio_web'})
    assert status == 201
    assert headers['Access-Control-Allow-Origin'] == ORIGIN
    assert value['session']['session_token']


@pytest.mark.parametrize('origin', [None, 'null', 'https://unrelated.example',
    'https://dioworkflows.co.za.evil.example', 'http://dioworkflows.co.za', 'http://127.0.0.1:8770'])
def test_public_session_refuses_unapproved_origins(api, origin):
    status, headers, _ = api('/api/vesper/web/session', method='POST', body={}, origin=origin)
    assert status == 403
    assert 'Access-Control-Allow-Origin' not in headers


@pytest.mark.parametrize('path,method', [('/', 'GET'), ('/.git/config', 'GET'),
    ('/api/control/state', 'GET'), ('/api/vesper/chat/session', 'POST'),
    ('/api/vesper/chat/session?conversation_id=someone', 'GET'),
    ('/api/vesper/chat/message', 'POST'), ('/api/vesper/web/replies/', 'GET'),
    ('/api/vesper/web/unknown', 'OPTIONS'), ('/api/vesper/web/replies', 'POST')])
def test_public_boundary_never_dispatches_noncustomer_routes(api, path, method):
    status, _, _ = api(path, method=method, body={} if method == 'POST' else None)
    assert status == 404


def test_public_health_contains_no_local_paths_or_customer_data(api):
    status, _, value = api('/api/vesper/health', origin=None)
    assert status == 200
    assert value == {'ok': True, 'service': 'vesper-public-api',
                     'canonical_presence_engine': True, 'external_send': 'REFUSE',
                     'external_release': 'REFUSE', 'authority_created': False}


def test_public_two_turn_journey_and_session_ownership(api, monkeypatch):
    _, _, opened = api('/api/vesper/web/session', method='POST', body={'surface': 'dio_web'})
    session = opened['session']
    cid, token = session['conversation_id'], session['session_token']
    for sequence, text in enumerate(['What do you need from me for ContractProof?',
            'Actually, this is for a nonprofit. Does that change what you need?']):
        if sequence:
            monkeypatch.setattr(router, 'classify_with_ollama', lambda *a, **k:
                                {'intent': 'general_info', 'product': None, 'confidence': .9})
        status, _, accepted = api('/api/vesper/web/message', method='POST', token=token,
            body={'conversation_id': cid, 'message': text, 'client_message_id': f'public-{sequence}'})
        assert status == 200
        assert accepted['receipt']['authority_created'] is False
    query = '/api/vesper/web/replies?conversation_id=' + cid
    status, _, value = api(query, token=token)
    assert status == 200
    assert len(value['replies']) == 2
    assert 'ContractProof' in value['replies'][-1]['reply']['text']
    assert 'clarifies who the work is for' in value['replies'][-1]['reply']['text']
    assert value['replies'][0]['canonical_case_id'] == value['replies'][1]['canonical_case_id']
    status, _, restored = api('/api/vesper/web/session?conversation_id=' + cid, token=token)
    assert status == 200
    assert restored['session']['conversation_id'] == cid
    assert 'session_token' not in restored['session']
    assert 'public_web_token_sha256' not in restored['session']
    assert len(restored['replies']) == 2
    assert api(query, token='wrong-token')[0] == 403
    assert api(query)[0] == 403


def test_public_boundary_does_not_change_existing_local_origin_policy(api):
    from scripts.serve_vesper_web_chat import LOCAL_CORS_ORIGINS
    assert ORIGIN not in LOCAL_CORS_ORIGINS


def test_voice_unavailable_uses_existing_protocol_marker_and_redacts_host_details(api, monkeypatch):
    def unavailable(*args):
        raise public.PublicWebVoiceUnavailable('missing /private/host/model-cache')
    monkeypatch.setattr(public, 'accept_voice', unavailable)
    status, _, value = api('/api/vesper/web/voice', method='POST', body={})
    assert status == 503
    assert value['processing_state'] == 'REJECTED_NO_CANONICAL_EFFECT'
    assert '/private' not in json.dumps(value)


def test_unapproved_preflight_origin_is_refused(api):
    status, headers, _ = api('/api/vesper/web/session', method='OPTIONS', origin='https://unrelated.example')
    assert status == 403
    assert 'Access-Control-Allow-Origin' not in headers


def test_restricted_public_api_has_separate_loopback_systemd_unit():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    unit = (root / 'deploy/systemd/dio-vesper-public-api.service').read_text()
    assert 'scripts/serve_vesper_public_api.py --host 127.0.0.1 --port 8772' in unit
    assert 'scripts/verify_integrated_runtime.py' in unit
    assert 'DIO_STATE_ROOT=/home/byron/.local/share/dio' in unit
    assert 'ConditionPathIsMountPoint=/data' in unit
    # Keep the operator/local chat service distinct from the public allowlisted API.
    local_unit = (root / 'deploy/systemd/dio-vesper-web-chat.service').read_text()
    assert 'scripts/serve_vesper_web_chat.py --host 127.0.0.1 --port 8770' in local_unit


def test_public_session_token_expiry_is_persisted_and_enforced(api, monkeypatch):
    from types import SimpleNamespace
    import time as time_module

    status, _, opened = api('/api/vesper/web/session', method='POST', body={'surface': 'dio_web'})
    assert status == 201
    cid, token = opened['session']['conversation_id'], opened['session']['session_token']
    session = public.web.load_session(cid, state_root=public.STATE_ROOT)
    expiry = session.get('public_web_token_expires_at')
    assert isinstance(expiry, int) and expiry > time_module.time()

    monkeypatch.setattr(public, 'time', SimpleNamespace(time=lambda: expiry + 1))
    status, _, value = api('/api/vesper/web/replies?conversation_id=' + cid, token=token)
    assert status == 403
    assert value['message'] == 'Request refused.'


def test_public_session_without_expiry_is_refused(api):
    status, _, opened = api('/api/vesper/web/session', method='POST', body={'surface': 'dio_web'})
    assert status == 201
    cid, token = opened['session']['conversation_id'], opened['session']['session_token']
    with public.web._session_lock(public.STATE_ROOT, cid):
        session = public.web.load_session(cid, state_root=public.STATE_ROOT)
        session.pop('public_web_token_expires_at', None)
        session['session_fingerprint'] = public.web._fingerprint(
            {k: v for k, v in session.items() if k != 'session_fingerprint'}
        )
        public.web._write_json(public.web._session_path(public.STATE_ROOT, cid), session)
    status, _, _ = api('/api/vesper/web/replies?conversation_id=' + cid, token=token)
    assert status == 403


def test_public_api_rejects_oversized_post_before_processing(api):
    # Advertise an oversized body without sending it: the guard must reject
    # from headers alone, before attempting to read or parse the body.
    status, _, value = api(
        '/api/vesper/web/session', method='POST',
        extra_headers={'Content-Length': str(4 * 1024 * 1024 + 1)},
    )
    assert status == 413
    assert value['error'] == 'invalid_request_size'


def test_public_api_rejects_transfer_encoded_post(api):
    status, _, value = api('/api/vesper/web/session', method='POST',
                           extra_headers={'Transfer-Encoding': 'chunked'})
    assert status == 413
    assert value['error'] == 'invalid_request_size'

