from pathlib import Path
import tempfile

from market_command.intelligence import IntelligenceStore


def make_store(tmp):
    return IntelligenceStore(Path(tmp)/"market.sqlite", Path(tmp)/"events.jsonl")


def test_role_binding_separates_identity_from_permission():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        row=s.bind_role({
            "organisation":"Example University",
            "product_line_id":"VAMP_ACADEMIC",
            "role_title":"HR Director",
            "person_name":"Person",
            "source":"linkedin",
            "confidence":"high",
        })
        assert row["confidence"]=="high"
        assert row["outreach_permission"]=="not_recorded"


def test_attribution_requires_causal_entity():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        try:
            s.record_attribution({"event_type":"payment.succeeded","value_minor":10000,"source":"test"})
            assert False
        except ValueError as exc:
            assert "causal entity" in str(exc)


def test_scoreboard_uses_verified_revenue_not_platform_conversion_value():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        s.record_snapshot({
            "channel_id":"META_ADS","impressions":1000,"clicks":20,"spend_minor":10000,
            "conversion_value_minor":999999,"source_mode":"manual_import","evidence_grade":"operator_import"
        })
        s.record_attribution({
            "campaign_id":"MKT-1","channel_id":"META_ADS","payment_id":"PAY-1",
            "event_type":"payment.succeeded","value_minor":25000,"source":"commerce_ledger"
        })
        row=s.portfolio_scoreboard()[0]
        assert row["platform_value_minor"]==999999
        assert row["verified_revenue_minor"]==25000
        assert row["verified_roas"]==2.5


def test_external_link_binds_platform_to_dio_campaign():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        row=s.bind_external_campaign({"campaign_id":"MKT-1","channel_id":"REDDIT_ADS","external_campaign_id":"abc"})
        assert row["campaign_id"]=="MKT-1"
        assert row["external_campaign_id"]=="abc"


def test_snapshot_windows_are_idempotent_and_late_binding_reconciles():
    with tempfile.TemporaryDirectory() as d:
        s=make_store(d)
        spec={"channel_id":"YOUTUBE_ORGANIC","external_campaign_id":"video-1","window_start":"2026-08-01","window_end":"2026-08-09","views":10,"source_mode":"api","evidence_grade":"platform_api"}
        first=s.record_snapshot(spec)
        second=s.record_snapshot({**spec,"views":12})
        assert first["snapshot_id"]==second["snapshot_id"]
        assert second["views"]==12
        s.bind_external_campaign({"campaign_id":"MKT-1","channel_id":"YOUTUBE_ORGANIC","external_campaign_id":"video-1"})
        assert s.get_snapshot(first["snapshot_id"])["campaign_id"]=="MKT-1"
        assert len(s.state()["snapshots"])==1
