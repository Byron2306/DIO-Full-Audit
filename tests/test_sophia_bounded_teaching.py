import json
from pathlib import Path

import pytest

from products import professional_evidence_final_compat as compat


def packet(tmp_path):
    folder=tmp_path/'packet';(folder/'SOURCES').mkdir(parents=True)
    (folder/'SOURCES/manuscript.md').write_text('The supplied lesson states that evaporation is liquid water changing to vapour. ' * 5)
    (folder/'SOURCES/03_exception_note.md').write_text('The learner must write their own graded assignment answer.')
    return {'packet_dir':folder,'packet_fingerprint':'test-packet','intake':{'customer_authorised_processing':True,'request':'Help me understand evaporation.','reasoned_provider':'ollama','reasoned_model':'granite3.2:2b'}}


def run(packet, output):
    assert hasattr(compat,'_run_sophia_tutor_source_grounded'), 'Missing bounded source-grounded teaching path'
    return compat._run_sophia_tutor_source_grounded(packet,output,operator_id='test',now='2026-10-27',profile_review=lambda *a,**k:{'receipt':{},'product_id':'sophia_tutor'})


@pytest.mark.parametrize('field,value',[('customer_authorised_processing',False),('reasoned_provider','gemini')])
def test_unapproved_or_remote_teaching_is_refused_before_inference(tmp_path,field,value):
    p=packet(tmp_path);p['intake'][field]=value
    with pytest.raises(ValueError,match='authorization|local Ollama'):
        run(p,tmp_path/'out')


def test_prepared_teaching_keeps_source_questions_and_refuses_approval(tmp_path,monkeypatch):
    from adapters.sophia import review_pipeline
    p=packet(tmp_path)

    def local(request,request_path,out_root,base_url,sophia_root):
        assert request['review_mode']=='held_diagnostic_draft'
        assert request['review_focus']=='bounded_source_grounded_teaching'
        assert request['reasoned_provider']=='ollama'
        out=out_root/'job';out.mkdir(parents=True)
        report={'assessment':'A source-based evaporation practice task.', 'comments':[{
            'anchor':'P1','quote':'evaporation is liquid water changing to vapour',
            'issue':'What changes state during evaporation?',
            'action':'Draw liquid water and water vapour; label what has changed.',
            'limit':'A learner answer is required before feedback.'}],
            'evidence_limits':'No learner answer supplied.','author_next_steps':['Write your own explanation.']}
        (out/'REVIEWER_COMMENTARY.json').write_text(json.dumps({'status':'held_diagnostic_draft','constitutional_release_authorized':False,'delivery_released':False,'validation':{'passed':False},'diagnostic_validation':{'passed':True,'report':report,'comments':report['comments']},'candidate_sha256':'a'*64}))
        (out/'SOPHIA_REVIEW_RECEIPT.json').write_text(json.dumps({'preparation_state':'engineering_draft_prepared','constitutional_release_authorized':False,'delivery_released':False,'metrics':{'diagnostic_source_checks_passed':True}}))
        return out

    monkeypatch.setattr(review_pipeline,'run_review',local)
    result=run(p,tmp_path/'out');receipt=result['receipt']
    assert receipt['learning_support_draft_prepared'] is True
    assert receipt['native_dialogic_tutoring'] is False
    assert receipt['teaching_turn_completed'] is False
    assert receipt['constitutional_release_authorized'] is False
    assert receipt['external_release_gate']=='REFUSE'
    text=(tmp_path/'out/SOPHIA_TUTOR_STUDY_RECORD.md').read_text()
    assert 'What changes state during evaporation?' in text
    assert 'Draw liquid water' in text
    assert 'submission-ready' in text
