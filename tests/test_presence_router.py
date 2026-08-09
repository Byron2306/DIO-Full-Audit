from pathlib import Path
from presence_core.router import route_message

def test_homs_lesson_intake(tmp_path):
    p=tmp_path/'routes.json'; p.write_text('{"routes":[{"product":"homs","keywords":["homs","assessment"]}]}')
    d=route_message('I need HOMS to create a Grade 8 lesson plan and worksheet','public',p); assert d.intent=='intake_request' and d.product=='homs'
def test_operator_summary(tmp_path):
    p=tmp_path/'routes.json'; p.write_text('{"routes":[]}'); assert route_message('morning lilith','operator',p).intent=='operator_summary'
def test_public_cannot_trigger_operator_phrase(tmp_path):
    p=tmp_path/'routes.json'; p.write_text('{"routes":[]}'); assert route_message('morning lilith','public',p).intent!='operator_summary'

def test_multilingual_product_request_stays_intake(tmp_path):
    p=tmp_path/'routes.json'; p.write_text('{"routes":[{"product":"homs","keywords":["homs","assessment"]}]}')
    d=route_message('I need HOMS to create a Grade 8 lesson plan in Afrikaans','public',p)
    assert d.intent=='intake_request' and d.product=='homs'
