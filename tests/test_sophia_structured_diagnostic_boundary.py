import importlib.util
import json
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / 'cross_folder_variants/Integritas-Mechanicus/A_CODE/arda_os/backend/services/canonical_product_review.py'


def boundary():
    spec = importlib.util.spec_from_file_location('structured_product_review', PATH)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def inputs():
    return ({'reasoned_provider': 'ollama', 'reasoned_model': 'granite3.2:2b',
             'verified_review_anchors': ['P1'], 'verified_review_manuscript_sha256': 'a' * 64},
            'Review [P1]', {'response': '{"comments": [{"anchor": "[P1]", "quote": "broken...',
                            'model_response_after_thinking': '{"comments": [{"anchor": "[P1]", "quote": "real source quote"}]}',
                            'model': 'granite3.2:2b', 'reasoned_provider': 'ollama', 'reasoned_provider_status': 'ok'})


def test_explicit_diagnostic_preparation_binds_complete_native_candidate():
    body, prompt, payload = inputs();body['dio_review_preparation_mode'] = 'held_diagnostic_draft'
    result = boundary().attach_evidence(body, prompt, payload)
    assert result['response'] == payload['model_response_after_thinking']
    assert result['diagnostic_candidate_source'] == 'native_model_response_after_thinking'
    assert result['mandos_judgment']['passed'] is False
    assert result['article_conformity']['summary']['status'] == 'NOT_EVALUATED'
    assert result['response_release_ledger']['release_authorized'] is False
    assert result['response_release_ledger']['constitutional_release_authorized'] is False


def test_default_boundary_preserves_existing_final_response():
    body, prompt, payload = inputs()
    assert boundary().attach_evidence(body, prompt, payload)['response'] == payload['response']


def test_diagnostic_mode_refuses_missing_native_candidate():
    body, prompt, payload = inputs();body['dio_review_preparation_mode'] = 'held_diagnostic_draft'
    payload.pop('model_response_after_thinking')
    with pytest.raises(ValueError, match='native.*candidate'):
        boundary().attach_evidence(body, prompt, payload)


def test_structured_report_schema_binds_each_anchor_to_its_real_quote():
    module=boundary();assert hasattr(module,'diagnostic_output_schema'), 'Missing constrained native diagnostic contract'
    body, _, _=inputs();body['review_quote_registry']={'P1':'The source reports an association.'}
    schema=module.diagnostic_output_schema(body)
    assert set(schema['required'])=={'assessment','comments','evidence_limits','author_next_steps'}
    pair=schema['properties']['comments']['items']['oneOf'][0]
    assert pair['properties']['anchor']['const']=='[P1]'
    assert pair['properties']['quote']['const']=='The source reports an association.'
    assert set(pair['required'])=={'anchor','quote','issue','action','limit'}


def test_native_ollama_receives_structured_format_only_when_requested(monkeypatch):
    from tests.test_sophia_product_review_routing import _load_presence_server
    server=_load_presence_server();calls=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return b'{"response":"{}","model":"granite3.2:2b"}'
    def opener(request,timeout):
        calls.append(json.loads(request.data));return Response()
    monkeypatch.setattr(server.urllib.request,'urlopen',opener)
    contract={'type':'object','properties':{'assessment':{'type':'string'}}}
    server.ollama_generate('source task',model='granite3.2:2b',response_format=contract)
    assert calls[-1]['format']==contract
    assert 'calibration mode' not in str(calls[-1]).lower()
    server.ollama_generate('plain chat',model='granite3.2:2b')
    assert 'format' not in calls[-1]
