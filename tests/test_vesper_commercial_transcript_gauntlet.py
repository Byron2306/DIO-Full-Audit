from presence_core.llm import draft_claims_authorized


def test_quarantine_cannot_be_drafted_as_processing_or_future_results_delivery():
    facts = "attachment=ATT-1; state=quarantined; attachment_processed=false; delivery_state=not_started"
    assert draft_claims_authorized("I have received your file and will now process it through Research Integrity.", facts) is False
    assert draft_claims_authorized("Once the analysis is complete, I will provide the claim lineage ledger and source-fit map.", facts) is False
    assert draft_claims_authorized("I will share the completed results with you when they are ready.", facts) is False


def test_drafted_invoice_and_unverified_payment_cannot_be_described_as_sent_or_paid():
    facts = "invoice_state=drafted; payment_state=unverified; send_state=not_sent"
    assert draft_claims_authorized("I have sent your invoice and payment is confirmed.", facts) is False


def test_unregistered_account_portal_and_billing_team_cannot_be_invented_as_escape_hatches():
    facts = "account_portal=unavailable; billing_team=unavailable; invoice_state=not_created"
    assert draft_claims_authorized("Please check your DIO account portal or contact our billing team directly.", facts) is False


def test_verified_contact_surface_may_be_described_when_governed_facts_supply_it():
    facts = "billing_contact=verified:dio_workflows@outlook.com; billing_team=unavailable; account_portal=unavailable"
    assert draft_claims_authorized("For billing questions, email dio_workflows@outlook.com.", facts) is True
