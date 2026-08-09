import os

from adapters.marketing.base import HttpResponse
from adapters.marketing import facebook_page, linkedin_organic, meta_ads, reddit_ads, tiktok_ads, youtube_organic


def test_meta_adapter_is_read_only_and_normalizes(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN","x")
    monkeypatch.setenv("META_AD_ACCOUNT_ID","123")
    monkeypatch.setenv("META_GRAPH_VERSION","vTEST")
    def fake(method,url,headers,params,body):
        assert method=="GET"
        assert "/act_123/insights" in url
        return HttpResponse(200,{"data":[{"campaign_id":"m1","impressions":"100","reach":"80","clicks":"7","spend":"12.50","actions":[{"action_type":"lead","value":"2"}]}]}, {})
    rows=meta_ads.sync("2026-08-01","2026-08-07",fake)
    assert rows[0]["external_campaign_id"]=="m1"
    assert rows[0]["spend_minor"]==1250
    assert rows[0]["conversions"]==2


def test_tiktok_adapter_uses_reporting_endpoint(monkeypatch):
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN","x")
    monkeypatch.setenv("TIKTOK_ADVERTISER_ID","adv")
    def fake(method,url,headers,params,body):
        assert method=="GET"
        assert url.endswith("/report/integrated/get/")
        return HttpResponse(200,{"code":0,"data":{"list":[{"dimensions":{"campaign_id":"t1"},"metrics":{"spend":"5.25","impressions":"500","clicks":"25","conversion":"1"}}]}}, {})
    rows=tiktok_ads.sync("2026-08-01","2026-08-07",fake)
    assert rows[0]["spend_minor"]==525
    assert rows[0]["clicks"]==25


def test_reddit_adapter_reporting_post_is_not_mutation(monkeypatch):
    monkeypatch.setenv("REDDIT_ADS_ACCESS_TOKEN","x")
    monkeypatch.setenv("REDDIT_AD_ACCOUNT_ID","a2_demo")
    monkeypatch.setenv("REDDIT_USER_AGENT","dio-market-command-test/1.0")
    def fake(method,url,headers,params,body):
        assert method=="POST"
        assert url.endswith("/ad_accounts/a2_demo/reports")
        assert body["breakdowns"]==["campaign_id"]
        return HttpResponse(200,{"data":[{"campaign_id":"r1","IMPRESSIONS":1000,"CLICKS":30,"SPEND":25000000}]}, {})
    rows=reddit_ads.sync("2026-08-01","2026-08-07",fake)
    assert rows[0]["external_campaign_id"]=="r1"
    assert rows[0]["impressions"]==1000
    assert rows[0]["spend_minor"]==2500


def test_youtube_adapter_uses_existing_nichefoundry_channel(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "key")
    monkeypatch.setenv("YOUTUBE_CHANNEL_ID", "UC_EXPECTED")
    def fake(method, url, headers, params, body):
        assert method == "GET"
        if url.endswith("/channels"):
            return HttpResponse(200, {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "PL_UPLOADS"}}}]}, {})
        if url.endswith("/playlistItems"):
            return HttpResponse(200, {"items": [{"contentDetails": {"videoId": "VID-1"}}]}, {})
        return HttpResponse(200, {"items": [{"id": "VID-1", "snippet": {"title": "Proof", "publishedAt": "2026-08-08T10:00:00Z"}, "statistics": {"viewCount": "321", "likeCount": "7"}, "status": {"privacyStatus": "public"}}]}, {})
    rows = youtube_organic.sync("2026-08-01", "2026-08-09", fake)
    assert rows[0]["external_campaign_id"] == "VID-1"
    assert rows[0]["views"] == 321
    assert rows[0]["impressions"] == 0


def test_facebook_page_adapter_reads_but_never_publishes(monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("META_GRAPH_VERSION", "vTEST")
    def fake(method, url, headers, params, body):
        assert method == "GET"
        assert url.endswith("/vTEST/page/published_posts")
        return HttpResponse(200, {"data": [{"id": "POST-1", "insights": {"data": [{"name": "post_impressions", "values": [{"value": 120}]}, {"name": "post_clicks", "values": [{"value": 9}]}]}}]}, {})
    rows = facebook_page.sync("2026-08-01", "2026-08-09", fake)
    assert rows[0]["impressions"] == 120
    assert rows[0]["clicks"] == 9
    assert facebook_page.readiness()["write_authority"] == "human_business_suite_publish"


def test_linkedin_adapter_separates_analytics_from_publication(monkeypatch):
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "token")
    monkeypatch.setenv("LINKEDIN_ORGANIZATION_URN", "urn:li:organization:1")
    monkeypatch.setenv("LINKEDIN_VERSION", "202608")
    def fake(method, url, headers, params, body):
        assert method == "GET"
        assert headers["LinkedIn-Version"] == "202608"
        return HttpResponse(200, {"elements": [{"totalShareStatistics": {"impressionCount": 500, "uniqueImpressionsCount": 400, "clickCount": 20}}]}, {})
    rows = linkedin_organic.sync("2026-08-01", "2026-08-09", fake)
    assert rows[0]["impressions"] == 500
    assert rows[0]["clicks"] == 20
    assert linkedin_organic.readiness()["write_authority"] == "human_publish_only"
