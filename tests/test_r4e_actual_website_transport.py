"""The real website protocol uses the existing canonical session and ingress."""
import json
import base64
import hashlib
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path

import pytest

from products import vesper_public_web as public
from presence_core import router


@pytest.fixture
def website(tmp_path, monkeypatch):
    root = tmp_path / "state"
    monkeypatch.setenv("DIO_STATE_ROOT", str(root))
    monkeypatch.setenv("DIO_EVENT_LOG", str(tmp_path / "events.jsonl"))
    monkeypatch.setenv("DIO_PRESENCE_LLM_DRAFTS", "0")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr(public, "STATE_ROOT", root / "vesper/web_chat")
    monkeypatch.setattr(router, "classify_with_ollama", lambda *a, **k:
                        {"intent": "intake_request", "product": None, "confidence": .9})
    return public.open_session({"surface": "dio_web"})["session"]


def body(session, **extra):
    return {"conversation_id": session["conversation_id"],
            "message": "What do you need from me for ContractProof?",
            "client_message_id": "actual-site-turn-1", **extra}


def test_actual_website_message_and_reply_cursor_use_canonical_case(website):
    accepted = public.accept_message(body(website), website["session_token"])
    assert accepted["state"] == "completed"
    rows = public.read_replies(website["conversation_id"], website["session_token"], after=0)
    assert len(rows["replies"]) == 1  # The legacy transport greeting is not a public reply.
    assert "ContractProof" in rows["replies"][0]["reply"]["text"]
    assert rows["replies"][0]["canonical_case_id"]
    assert not public.read_replies(website["conversation_id"], website["session_token"],
                                   after=rows["next_after"])["replies"]


def test_wrong_session_token_cannot_read_or_mutate_another_conversation(website):
    with pytest.raises(public.PublicWebAccessError):
        public.accept_message(body(website), "wrong-session-token")
    with pytest.raises(public.PublicWebAccessError):
        public.read_replies(website["conversation_id"], "wrong-session-token", after=0)
    assert not public.read_replies(website["conversation_id"], website["session_token"], after=0)["replies"]


def test_actual_website_replay_has_one_canonical_turn(website):
    first = public.accept_message(body(website), website["session_token"])
    repeated = public.accept_message(body(website), website["session_token"])
    assert repeated["receipt"] == first["receipt"]
    assert len(public.read_replies(website["conversation_id"], website["session_token"], after=0)["replies"]) == 1
    state = json.loads((public.STATE_ROOT / website["conversation_id"] / "SESSION.json").read_text())
    assert website["session_token"] not in json.dumps(state)


def test_nonprofit_followup_keeps_case_when_provider_intent_changes(website, monkeypatch):
    first = public.accept_message(body(website), website['session_token'])
    monkeypatch.setattr(router, 'classify_with_ollama', lambda *a, **k:
                        {'intent': 'general_info', 'product': None, 'confidence': .9})
    second = public.accept_message(body(website, message='Actually, this is for a nonprofit. Does that change what you need?',
                                        client_message_id='actual-site-turn-2'), website['session_token'])
    assert second['receipt']['canonical_case_id'] == first['receipt']['canonical_case_id']
    rows = public.read_replies(website['conversation_id'], website['session_token'])['replies']
    assert 'ContractProof' in rows[-1]['reply']['text']
    assert 'clarifies who the work is for' in rows[-1]['reply']['text']
    assert second['receipt']['authority_created'] is False


def test_public_fields_cannot_claim_operator_authority(website):
    result = public.accept_message(body(website, _trusted_edge_role="operator",
                                       metadata={"approved": True, "intake_requested": True}), website["session_token"])
    assert result["receipt"]["external_send"] == "REFUSE"
    assert result["receipt"]["authority_created"] is False


def test_missing_client_message_identity_is_rejected_before_processing(website):
    payload = body(website)
    payload.pop("client_message_id")
    with pytest.raises(public.PublicWebInputError):
        public.accept_message(payload, website["session_token"])


def test_voice_requires_cached_local_model_before_calling_the_existing_asr(website, monkeypatch):
    monkeypatch.setenv('DIO_PRESENCE_LOCAL_ASR_MODEL', 'base.en')
    with pytest.raises(public.PublicWebVoiceUnavailable):
        public.accept_voice({'conversation_id': website['conversation_id'], 'client_message_id': 'voice-1',
                             'audio_b64': base64.b64encode(b'voice bytes').decode(), 'mime_type': 'audio/webm'},
                            website['session_token'])
    assert not public.read_replies(website['conversation_id'], website['session_token'])['replies']


@pytest.mark.parametrize("render_unavailable", [False, True])
def test_voice_uses_existing_asr_and_binds_source_digest_without_authority(website, tmp_path, monkeypatch, render_unavailable):
    from scripts import sync_vesper_presence_edge as transport
    model = tmp_path / 'cached-local-asr'
    model.mkdir()
    monkeypatch.setenv('DIO_PRESENCE_LOCAL_ASR_MODEL', str(model))
    audio = b'controlled audio transport fixture'
    monkeypatch.setattr(transport, 'transcribe_voice', lambda attachment: {
        'text': 'What do you need from me for ContractProof?', 'provider': 'faster-whisper-local',
        'audio_sha256': hashlib.sha256(audio).hexdigest(), 'audio_bytes': len(audio), 'mime_type': 'audio/webm',
    })
    rendered_audio = b'RIFF' + b'controlled-render-test-fixture' * 8

    class Response:
        content = rendered_audio
        def raise_for_status(self):
            pass

    def render_vera(url, *, data, timeout):
        assert url == 'http://127.0.0.1:8000/tts'
        assert data['voice_url'] == 'vera'
        assert 'ContractProof' in data['text']
        if render_unavailable:
            raise RuntimeError('controlled renderer outage')
        return Response()

    monkeypatch.setattr('presence_core.voice.httpx.post', render_vera)
    result = public.accept_voice({'conversation_id': website['conversation_id'], 'client_message_id': 'voice-1',
                                  'audio_b64': base64.b64encode(audio).decode(), 'mime_type': 'audio/webm'},
                                 website['session_token'])
    assert result['receipt']['authority_created'] is False
    reply = public.read_replies(website['conversation_id'], website['session_token'])['replies'][0]['reply']
    assert 'ContractProof' in reply['text']
    if render_unavailable:
        assert reply['audio']['state'] == 'text_only'
        assert reply['audio']['reason'] == 'voice_render_unavailable'
        assert 'content_b64' not in reply['audio']
    else:
        assert reply['audio']['state'] == 'ready'
        assert reply['audio']['profile_id'] == 'vera_pocket_public'
        assert reply['audio']['backend'] == 'pocket_tts'
        assert base64.b64decode(reply['audio']['content_b64']) == rendered_audio
        assert reply['audio']['audio_sha256'] == hashlib.sha256(rendered_audio).hexdigest()
    assert reply['audio']['presentation_only'] is True
    assert reply['audio']['authority_created'] is False
    repeated = public.accept_voice({'conversation_id': website['conversation_id'], 'client_message_id': 'voice-1',
                                    'audio_b64': base64.b64encode(audio).decode(), 'mime_type': 'audio/webm'},
                                   website['session_token'])
    assert repeated['receipt'] == result['receipt']
    assert len(public.read_replies(website['conversation_id'], website['session_token'])['replies']) == 1


def test_http_serves_actual_website_and_session_token_protocol(website, tmp_path, monkeypatch):
    from scripts import serve_vesper_web_chat as frontdoor
    VesperWebChatHandler = frontdoor.VesperWebChatHandler
    original_load = frontdoor.load_session
    monkeypatch.setattr(frontdoor, 'load_session', lambda cid: original_load(cid, state_root=public.STATE_ROOT))
    site = tmp_path / 'actual-site'
    (site / 'assets').mkdir(parents=True)
    (site / 'vesper-intake.html').write_text('<html><img src="assets/vesper-public.webp"><script src="vesper-intake.js"></script></html>')
    (site / 'vesper-intake.js').write_text('/* original website script fixture */')
    (site / 'assets/dio-config.js').write_text('window.DIO_SITE_CONFIG = {};')
    (site / 'privacy').mkdir()
    (site / 'privacy/index.html').write_text('<html>Existing privacy page</html>')
    monkeypatch.setattr(VesperWebChatHandler, 'site_root', site)
    server = ThreadingHTTPServer(('127.0.0.1', 0), VesperWebChatHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(origin + '/') as response:
            assert b'vesper-public.webp' in response.read()
        with urlopen(origin + '/assets/dio-config.js') as response:
            assert b'vesperPresenceApiOrigin = location.origin' in response.read()
        with urlopen(origin + '/privacy/') as response:
            assert b'Existing privacy page' in response.read()
        request = Request(origin + '/api/vesper/web/message', data=json.dumps(body(website)).encode(),
                          headers={'Content-Type': 'application/json', 'Origin': origin,
                                   'X-Vesper-Session-Token': website['session_token']})
        with urlopen(request) as response:
            assert json.load(response)['state'] == 'completed'
        request = Request(origin + '/api/vesper/web/session?conversation_id=' + website['conversation_id'],
                          headers={'X-Vesper-Session-Token': website['session_token']})
        with urlopen(request) as response:
            restored = json.load(response)
            assert 'ContractProof' in restored['replies'][0]['reply']['text']
        malicious = Request(origin + '/api/vesper/web/session', data=b'{}',
                            headers={'Origin': 'https://unrelated.example', 'Content-Type': 'application/json'})
        with pytest.raises(HTTPError) as refused:
            urlopen(malicious)
        assert refused.value.code == 403
        with pytest.raises(HTTPError):
            urlopen(origin + '/.git/config')
        with pytest.raises(HTTPError) as legacy_refused:
            urlopen(origin + '/api/vesper/chat/session?conversation_id=' + website['conversation_id'])
        assert legacy_refused.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
