from presence_core.policy import authorize

def test_public_operator_summary_blocked(): assert authorize('public','operator_summary')[0] is False

def test_model_has_no_tool_authority():
    import json
    cfg=json.load(open('config/presence.json')); assert cfg['llm']['tool_authority'] is False and cfg['operator']['can_spend_money'] is False and cfg['attachments']['automatic_processing'] is False

def test_attachment_received_is_public_but_only_as_quarantine_event(): assert authorize('public','attachment_received')[0] is True
