import json
from pathlib import Path

from presence_core.commercial_pricing import recommend_quote
from presence_core.llm import _draft_messages, draft_claims_authorized


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _research_integrity_root(tmp_path: Path) -> Path:
    _write(tmp_path / "config" / "commercial_campaigns.json", {"products": {}})
    _write(
        tmp_path / "config" / "dio_product_portfolio.json",
        {
            "schema": "dio.product_portfolio.v1",
            "products": [
                {
                    "id": "dio_research_integrity",
                    "name": "DIO Research Integrity",
                    "customer_facing": True,
                    "offer": "One-Section Claim Lineage Pilot",
                    "cta": "Choose one bounded manuscript section or policy analysis and preserve its claim-to-source and revision lineage.",
                }
            ],
        },
    )
    return tmp_path


def test_operator_side_of_live_transcript_uses_owner_contract_not_customer_sales_contract():
    messages = _draft_messages(
        {"intent": "product_info", "product": "sophia"},
        "product=sophia; authority_created=false",
        "Sophia is available for governed research workflows.",
        None,
        None,
        {},
        [{"role": "user", "text": "What exactly is Sophia?"}],
        {"role": "operator", "audience": "operator"},
    )
    text = "\n".join(row["content"] for row in messages).lower()
    assert "owner/operator" in text
    assert "operational chief-of-staff" in text
    assert "write one concise, natural customer-facing reply" not in text
    assert "ask sales-closing questions" in text


def test_twenty_page_whole_article_cannot_expand_one_section_integrity_offer(tmp_path: Path):
    root = _research_integrity_root(tmp_path)
    result = recommend_quote(
        root,
        product_id="dio_research_integrity",
        scope={"page_count": 20, "section_count": 8, "requested_depth": "full_document"},
    )
    assert result["mode"] == "needs_operator"
    assert result["reason"] == "scope_exceeds_governed_offer"
    assert result["governed_offer"] == "One-Section Claim Lineage Pilot"
    assert result["authority_created"] is False


def test_quarantine_cannot_be_drafted_as_processing_or_future_results_delivery():
    facts = "attachment=ATT-1; state=quarantined; attachment_processed=false; delivery_state=not_started"
    assert draft_claims_authorized(
        "I have received your file and will now process it through Research Integrity.",
        facts,
    ) is False
    assert draft_claims_authorized(
        "Once the analysis is complete, I will provide the claim lineage ledger and source-fit map.",
        facts,
    ) is False
    assert draft_claims_authorized(
        "I will share the completed results with you when they are ready.",
        facts,
    ) is False


def test_drafted_invoice_and_unverified_payment_cannot_be_described_as_sent_or_paid():
    facts = "invoice_state=drafted; payment_state=unverified; send_state=not_sent"
    assert draft_claims_authorized(
        "I have sent your invoice and payment is confirmed.",
        facts,
    ) is False


def test_unregistered_account_portal_and_billing_team_cannot_be_invented_as_escape_hatches():
    facts = "account_portal=unavailable; billing_team=unavailable; invoice_state=not_created"
    assert draft_claims_authorized(
        "Please check your DIO account portal or contact our billing team directly.",
        facts,
    ) is False


def test_verified_contact_surface_may_be_described_when_governed_facts_supply_it():
    facts = "billing_contact=verified:dio_workflows@outlook.com; billing_team=unavailable; account_portal=unavailable"
    assert draft_claims_authorized(
        "For billing questions, email dio_workflows@outlook.com.",
        facts,
    ) is True
