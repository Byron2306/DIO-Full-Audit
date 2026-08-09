from pathlib import Path
import tempfile

from market_command.core import MarketStore

CONFIG={"default_experiment_window_days":14,"max_experiment_budget_minor":0,"promotion_min_qualified_leads":5,"promotion_min_paid_orders":2,"promotion_min_roas":1.5,"kill_min_spend_minor":50000,"revise_min_clicks":50}

def make_store(tmp): return MarketStore(Path(tmp)/"market.sqlite",Path(tmp)/"events.jsonl",CONFIG)

def test_campaign_is_fail_closed_for_paid_budget():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        try:
            s.create_campaign({"product_line_id":"HOMS_ASSESS","name":"Paid","audience":"schools","channel_id":"META_ADS","objective":"lead","budget_cap_minor":10000})
            assert False
        except ValueError as e:
            assert "globally locked" in str(e)

def test_organic_campaign_requires_approval_and_release():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        c=s.create_campaign({"product_line_id":"HOMS_ASSESS","name":"Organic","audience":"schools","channel_id":"LINKEDIN_ORGANIC","objective":"lead"})
        assert c["approval_state"]=="pending"
        c=s.approve_campaign(c["campaign_id"],True)
        assert c["state"]=="approved"
        c=s.activate_campaign(c["campaign_id"],True)
        assert c["state"]=="active"

def test_settlement_does_not_promote_one_lucky_order():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        c=s.create_campaign({"product_line_id":"EVIDEX_PACK","name":"Proof","audience":"NGOs","channel_id":"LINKEDIN_ORGANIC","objective":"lead"})
        s.approve_campaign(c["campaign_id"],True); s.activate_campaign(c["campaign_id"],True)
        s.record_measurement(c["campaign_id"],{"qualified_leads":1,"paid_orders":1,"revenue_minor":95000})
        result=s.settle_campaign(c["campaign_id"],True)
        assert result["decision"]=="continue"

def test_revise_when_clicks_do_not_convert():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        c=s.create_campaign({"product_line_id":"SOPHIA_REVIEW","name":"Click test","audience":"researchers","channel_id":"LINKEDIN_ORGANIC","objective":"lead"})
        s.approve_campaign(c["campaign_id"],True); s.activate_campaign(c["campaign_id"],True)
        s.record_measurement(c["campaign_id"],{"clicks":55,"enquiries":0})
        result=s.settle_campaign(c["campaign_id"],True)
        assert result["decision"]=="revise"


def test_content_authority_can_gate_activation():
    with tempfile.TemporaryDirectory() as d:
        config = {**CONFIG, "require_approved_content_for_activation": True}
        s = MarketStore(Path(d)/"market.sqlite", Path(d)/"events.jsonl", config)
        c = s.create_campaign({"product_line_id":"HOMS_ASSESS","name":"Proof","audience":"schools","channel_id":"LINKEDIN_ORGANIC","objective":"lead"})
        content = s.add_content(c["campaign_id"], {"content_id":"CNT-TEST","hook":"One bounded proof","body":"Review the evidence."})
        s.approve_campaign(c["campaign_id"], True)
        try:
            s.activate_campaign(c["campaign_id"], True)
            assert False
        except ValueError as exc:
            assert "content must be approved" in str(exc)
        s.approve_content(content["content_id"], True)
        assert s.activate_campaign(c["campaign_id"], True)["state"] == "active"
