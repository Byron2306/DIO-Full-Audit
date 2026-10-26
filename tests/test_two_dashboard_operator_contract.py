from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_only_business_and_market_are_deployed_operator_dashboards():
    assert (ROOT / "dashboard" / "business.html").is_file()
    assert (ROOT / "dashboard" / "market.html").is_file()


def test_goldeneye_is_deployed_as_a_read_only_local_projection():
    service = text("deploy/systemd/dio-goldeneye-portfolio.service")
    assert "scripts/serve_goldeneye_portfolio.py" in service
    assert "--host 127.0.0.1 --port 8766" in service


def test_business_root_routes_to_business_workbench():
    source = text("scripts/serve_control_deck_ms10.py")
    assert 'if route in {"/", "/dashboard/business.html"}:' in source
    assert "self._serve_business_page()" in source
    assert "DIO BUSINESS" in source
    assert "/api/business/artifact" in source
    assert "/api/business/lead/update" in source
    assert "/api/business/secrets" in source


def test_market_root_routes_to_market_workbench():
    source = text("scripts/serve_market_command_ms10.py")
    assert 'if route in {"/", "/dashboard/market.html"}:' in source
    assert "self._serve_market_page()" in source
    assert 'parser.add_argument("--business-port"' in source
    assert "DIO MARKET" in source
    assert "/api/market/products" in source
    assert "load_secret_env(overwrite=False)" in source


def test_business_exposes_human_authority_full_portfolio_and_public_links():
    page = text("dashboard/business.html")
    for marker in (
        "My operating authority",
        "What needs me now?",
        "Jobs and actual work",
        "Full product portfolio",
        "Leads / CRM",
        "Email command",
        "Invoices, payments & transactions",
        "Sites & channels",
        "facebook.com/profile.php?id=61593271043069",
        "linkedin.com/company/139354569/admin/dashboard/",
        "youtube.com/@DIOworkflows",
        "product_portfolio",
        "incarnations",
        "/api/control/policy",
        "/api/control/lead/action",
        "/api/control/mail/action",
        "/api/business/lead/update",
        "/api/business/artifact",
    ):
        assert marker in page


def test_dashboard_cross_links_follow_configured_ports():
    business = text("scripts/serve_control_deck_ms10.py")
    market = text("scripts/serve_market_command_ms10.py")
    assert 'parser.add_argument("--market-port"' in business
    assert 'page.replace("http://127.0.0.1:8770", market_url)' in business
    assert 'page.replace("http://127.0.0.1:8765", business_url)' in market
    assert "'<div class=\"links\"><button id=\"newCampaign\"'" in market
    assert 'href="{business_url}/dashboard/production.html"' in market
    assert 'href="{business_url}/dashboard/connections.html"' in market


def test_market_exposes_guided_campaign_lifecycle_and_sensorium():
    page = text("dashboard/market.html")
    for marker in (
        "The campaign journey",
        "WHAT NOW?",
        "Market authority",
        "Campaign content",
        "Sensorium + Hivenance",
        "Channels & adapters",
        "/api/market/campaigns",
        "/approve",
        "/activate",
        "/measure",
        "/settle",
        "/api/market/content/",
        "/api/market/policy",
        "/state/market_sensorium/COMMERCIAL_COCKPIT.json",
        "Hivenance and Sensorium recommendations unavailable:",
        "if(!mr.ok)throw new Error(`market ${mr.status}`)",
        "cockpit request failed with HTTP",
    ):
        assert marker in page
