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


def test_market_root_routes_to_market_workbench():
    source = text("scripts/serve_market_command_ms10.py")
    assert 'self.path = "/dashboard/market.html"' in source
    assert "DIO MARKET" in source


def test_business_exposes_required_operator_domains_and_public_links():
    page = text("dashboard/business.html")
    for marker in (
        "My approvals",
        "Products & jobs",
        "Leads / CRM",
        "Email command",
        "Invoices, payments & transactions",
        "Sites & channels",
        "Full operator console",
        "facebook.com/profile.php?id=61593271043069",
        "linkedin.com/company/139354569/admin/dashboard/",
        "youtube.com/@DIOworkflows",
        "sites/evidex/",
        "sites/homs/",
        "sites/sophia/",
        "sites/vamp/",
        "sites/document-studio/",
    ):
        assert marker in page


def test_market_keeps_market_command_and_sensorium_in_one_surface():
    page = text("dashboard/market.html")
    for marker in (
        "Campaign operations",
        "Market Sensorium",
        "Channel & adapter readiness",
        "Full Market Command",
        "/market_dashboard/index.html",
        "/state/market_sensorium/COMMERCIAL_COCKPIT.json",
    ):
        assert marker in page
