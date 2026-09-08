import json, os
from pathlib import Path
from presence_core.engine import process_envelope
from presence_core import llm


class _Response:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


def make_root(tmp_path):
    (tmp_path/'config').mkdir(); (tmp_path/'telemetry').mkdir(); (tmp_path/'config'/'routes.json').write_text(json.dumps({'routes':[{'product':'homs','keywords':['homs','assessment']},{'product':'evidex','keywords':['evidex','evidence pack']}]})); return tmp_path

def test_public_intake_is_held(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40); cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}; env={'channel':'telegram','external_user_id':'123','text':'I need HOMS to create an assessment','message_type':'text'}; r=process_envelope(env,root,cfg); assert r['intake']['state']=='pending_operator_review'; assert r['authority']['fulfilment_released'] is False; assert list((root/'state/presence/needs_you').glob('*.json'))

def test_public_status_fails_closed(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40); cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}; r=process_envelope({'channel':'telegram','external_user_id':'123','text':'where is my order?','message_type':'text'},root,cfg); assert 'identity' in r['reply']['text'].lower(); assert r['authority']['executed_external_action'] is False

def test_operator_role_is_server_allowlist(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_OPERATOR_TELEGRAM_IDS','777'); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40); cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}; r=process_envelope({'channel':'telegram','external_user_id':'777','text':'morning lilith','message_type':'text','_trusted_edge_role':'operator'},root,cfg); assert r['role']=='operator' and r['decision']['intent']=='operator_summary'

def test_telegram_start_campaign_hint_flows_to_intake(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_SHARED_SECRET','s'*40)
    cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    env={'channel':'telegram','external_user_id':'555','text':'I need HOMS to create an assessment','message_type':'text','metadata':{'telegram_start_payload':'MKT-HOMS-42'}}
    r=process_envelope(env,root,cfg)
    assert r['intake']['campaign_hint']=='MKT-HOMS-42'

def test_public_edge_cannot_spoof_operator_even_with_allowlisted_user(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_OPERATOR_TELEGRAM_IDS','777'); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40)
    cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    r=process_envelope({'channel':'telegram','external_user_id':'777','text':'morning lilith','message_type':'text','_trusted_edge_role':'public'},root,cfg)
    assert r['role']=='public' and r['decision']['intent']!='operator_summary'


def test_presence_core_feeds_prior_exchange_to_ollama_draft(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT', 'i' * 40)
    monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS', '1')
    monkeypatch.setenv('OLLAMA_URL', 'http://ollama.test')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3.5:4b')
    cfg = {'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    prompts = []
    replies = iter([
        'HOMS helps prepare governed assessment work for educator review.',
        'Yes. For a large marking batch, we can narrow the workflow before an intake.'
    ])

    def fake_post(url, json, timeout):
        prompts.append(json['messages'][1]['content'])
        return _Response(next(replies))

    monkeypatch.setattr(llm.httpx, 'post', fake_post)

    first = {'channel':'telegram','external_user_id':'123','text':'Tell me about HOMS','message_type':'text'}
    second = {'channel':'telegram','external_user_id':'123','text':'Would that help with 80 papers?','message_type':'text'}
    process_envelope(first, root, cfg)
    process_envelope(second, root, cfg)

    assert len(prompts) == 2
    assert 'Tell me about HOMS' in prompts[1]
    assert 'HOMS helps prepare governed assessment work for educator review.' in prompts[1]
    assert 'Would that help with 80 papers?' in prompts[1]
