from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_only_business_and_market_are_deployed_operator_dashboards():
    assert (ROOT / "dashboard" / "business.html").is_file()
    assert (ROOT / "dashboard" / "market.html").is_file()
    assert not (ROOT / "deploy" / "systemd" / "dio-goldeneye-portfolio.service").exists()


def test_business_root_routes_to_business_workbench():
    source = text("scripts/serve_control_deck_ms10.py")
    assert 'self.path = "/dashboard/business.html"' in source
    assert "DIO BUSINESS" in source
    assert "/api/business/artifact" in source
    assert "/api/business/lead/update" in source


def test_market_root_routes_to_market_workbench():
    source = text("scripts/serve_market_command_ms10.py")
    assert 'self.path = "/dashboard/market.html"' in source
    assert "DIO MARKET" in source
    assert "/api/market/products" in source


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
    ):
        assert marker in page
