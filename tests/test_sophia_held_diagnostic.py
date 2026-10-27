"""A useful diagnostic draft never becomes constitutional or delivery approval."""
import hashlib
import json

import pytest

from adapters.sophia import review_pipeline as pipeline
from adapters.sophia.canonical_sources import load_service


def candidate():
    report = {
        "assessment": "The supplied working note identifies an unresolved claim boundary.",
        "comments": [{"anchor": "P1", "quote": "The source reports an association.",
                      "issue": "The note needs its underlying evidence checked.",
                      "action": "Inspect the source and revise the claim in your own words.",
                      "limit": "The full study was not supplied."}],
        "evidence_limits": "Only the supplied note was inspected; scholarly support remains unverified.",
        "author_next_steps": ["Locate the underlying source."]}
    text = json.dumps(report)
    prompt = 'Review [P1] The source reports an association.'
    evidence = load_service('response_evidence').examine(prompt=prompt, response=text, model='granite3.2:2b', evidence_anchors=['[P1]'])
    # The JSON uses a plain anchor field; the fixture keeps the same evidence
    # semantics as the native prompt by making the returned anchor bracketed.
    report['comments'][0]['anchor'] = '[P1]'
    text = json.dumps(report)
    evidence = load_service('response_evidence').examine(prompt=prompt, response=text, model='granite3.2:2b', evidence_anchors=['[P1]'])
    result = {'response': text, 'model': 'granite3.2:2b', 'source': 'reasoned_integrity_lane',
              'reasoned_provider': 'ollama', 'reasoned_provider_status': 'ok',
              'response_evidence': evidence, 'mandos_judgment': evidence['mandos_judgment'],
              'article_conformity': evidence['article_conformity']}
    strict = pipeline.validate_reasoned_commentary(text, result, {'P1'}, set(), set(), 'ollama')
    return text, prompt, result, strict


def examine(text, prompt, result, strict):
    assert hasattr(pipeline, 'validate_held_diagnostic'), 'Missing honest held diagnostic review path'
    return pipeline.validate_held_diagnostic(text, result, strict, prompt=prompt,
        model='granite3.2:2b', anchor_quotes={'P1': 'The source reports an association.'},
        source_text='The source reports an association.')


def test_grounded_diagnostic_is_usable_while_constitutional_checks_stay_false():
    text, prompt, result, strict = candidate()
    held = examine(text, prompt, result, strict)
    assert held['passed'] is True
    assert strict['passed'] is False
    assert strict['checks']['mandos_passed'] is False
    assert strict['checks']['genesis_articles_passed'] is False
    assert held['constitutional_release_authorized'] is False
    assert held['delivery_released'] is False
    assert held['response_evidence_status'] == 'NOT_EVALUATED'
    assert held['comments'][0]['source_quote_verified'] is True


@pytest.mark.parametrize('field,value', [
    ('quote', 'A fabricated source quote.'), ('action', ''),
    ('anchor', '[P9]'), ('issue', 'The study proves a 73% causal improvement.')])
def test_untraceable_comment_or_unsupported_numeral_is_held_out(field, value):
    text, prompt, result, strict = candidate()
    report = json.loads(text); report['comments'][0][field] = value
    text = json.dumps(report); result['response'] = text
    result['response_evidence'] = load_service('response_evidence').examine(
        prompt=prompt,response=text,model='granite3.2:2b',evidence_anchors=['[P1]'])
    held = examine(text, prompt, result, strict)
    assert held['passed'] is False
    assert held['constitutional_release_authorized'] is False


def test_response_custody_mismatch_cannot_make_a_diagnostic_draft():
    text, prompt, result, strict = candidate()
    result['response_evidence']['response_sha256'] = '0' * 64
    assert examine(text, prompt, result, strict)['passed'] is False


def test_authoritative_looking_flags_cannot_enter_non_authoritative_mode():
    text, prompt, result, strict = candidate()
    result['response_evidence']['mandos_judgment']['passed'] = True
    assert examine(text, prompt, result, strict)['passed'] is False


def test_only_explicit_diagnostic_mode_exposes_the_held_candidate(tmp_path, monkeypatch):
    text, _, _, _ = candidate()
    monkeypatch.setattr(pipeline, 'fetch_json', lambda url: {'session_token': 'test-only'})

    def native_response(url, payload, timeout):
        evidence = load_service('response_evidence').examine(prompt=payload['text'], response=text,
            model='granite3.2:2b', evidence_anchors=['[P1]'])
        return {'response': text, 'source': 'reasoned_integrity_lane', 'reasoned_provider': 'ollama',
                'reasoned_provider_status': 'ok', 'model': 'granite3.2:2b', 'response_evidence': evidence,
                'mandos_judgment': evidence['mandos_judgment'], 'article_conformity': evidence['article_conformity']}

    monkeypatch.setattr(pipeline, 'post_json', native_response)
    request = {'reasoned_review_approved': True, 'reasoned_provider': 'ollama', 'reasoned_model': 'granite3.2:2b'}
    (tmp_path / 'source.md').write_text('The source reports an association.')
    args = ('Review', tmp_path / 'source.md', 'The source reports an association.', 'plain_text', {}, [], [])
    strict = pipeline.reviewer_commentary('http://127.0.0.1:7070', dict(request), *args)
    assert strict['status'] == 'rejected'
    held = pipeline.reviewer_commentary('http://127.0.0.1:7070', {**request, 'review_mode': 'held_diagnostic_draft'}, *args)
    assert held['status'] == 'held_diagnostic_draft'
    assert held['diagnostic_validation']['passed'] is True
    assert held['validation']['passed'] is False
    assert held['constitutional_release_authorized'] is False
    assert 'The source reports an association.' in held['commentary']


def test_source_boundary_is_attached_even_when_model_omits_optional_limit():
    text, prompt, result, strict = candidate();report=json.loads(text)
    del report['comments'][0]['limit'];text=json.dumps(report);result['response']=text
    result['response_evidence']=load_service('response_evidence').examine(prompt=prompt,response=text,
        model='granite3.2:2b',evidence_anchors=['[P1]'])
    held=examine(text,prompt,result,strict)
    assert held['passed'] is True
    assert held['comments'][0]['limit_source'] == 'system_source_boundary'
    assert 'not independently verified' in held['comments'][0]['limit']


def test_a_document_heading_is_not_substantive_source_support():
    text,prompt,result,strict=candidate();report=json.loads(text)
    report['comments'][0]['quote']='# Controlled alternate-topic source notes';text=json.dumps(report)
    result['response_evidence']=load_service('response_evidence').examine(prompt=prompt,response=text,
        model='granite3.2:2b',evidence_anchors=['[P1]'])
    assert hasattr(pipeline,'validate_held_diagnostic')
    held=pipeline.validate_held_diagnostic(text,result,strict,prompt=prompt,model='granite3.2:2b',
        anchor_quotes={'P1':'# Controlled alternate-topic source notes'},source_text='# Controlled alternate-topic source notes')
    assert held['passed'] is False


def test_held_source_failure_gets_one_bound_repair_and_retains_rejected_candidate(tmp_path, monkeypatch):
    valid, _, _, _ = candidate()
    report=json.loads(valid);report['comments'][0]['issue']='The intervention improved outcomes by 73%.'
    invalid=json.dumps(report)
    calls=[]
    monkeypatch.setattr(pipeline,'fetch_json',lambda url:{'session_token':'test'})
    def native(url,payload,timeout):
        text=invalid if not calls else valid
        calls.append(dict(payload))
        evidence=load_service('response_evidence').examine(prompt=payload['text'],response=text,model='granite3.2:2b',evidence_anchors=['[P1]'])
        return {'response':text,'model':'granite3.2:2b','source':'reasoned_integrity_lane','reasoned_provider':'ollama','reasoned_provider_status':'ok',
                'response_evidence':evidence,'mandos_judgment':evidence['mandos_judgment'],'article_conformity':evidence['article_conformity']}
    monkeypatch.setattr(pipeline,'post_json',native)
    source=tmp_path/'source.md';source.write_text('The source reports an association.')
    request={'reasoned_review_approved':True,'reasoned_provider':'ollama','reasoned_model':'granite3.2:2b','review_mode':'held_diagnostic_draft'}
    result=pipeline.reviewer_commentary('http://127.0.0.1:7070',request,'Review',source,source.read_text(),'plain_text',{},[],[])
    assert len(calls)==2
    assert result['status']=='held_diagnostic_draft'
    assert result['attempt_diagnostics'][0]['candidate']==invalid
    assert result['attempt_diagnostics'][0]['diagnostic_validation']['unknown_numerals']==['73%']
    assert result['constitutional_release_authorized'] is False
    assert result['validation']['passed'] is False
