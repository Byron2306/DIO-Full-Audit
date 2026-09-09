import json
from pathlib import Path

from presence_core.commercial_pricing import recommend_quote, reference_offers


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_root(tmp_path: Path) -> Path:
    _write(
        tmp_path / "config" / "commercial_campaigns.json",
        {
            "schema": "knowedge.commercial_campaigns.v2",
            "products": {
                "evidex": {
                    "name": "Evidex Evidence Pack",
                    "offers": [
                        {
                            "id": "starter",
                            "name": "Starter Evidence Pack",
                            "promise": "A small bounded evidence set mapped for human review.",
                            "price": "R350-R750",
                        },
                        {
                            "id": "standard",
                            "name": "Standard Evidence Pack",
                            "promise": "A broader reporting pack with evidence mapping and gaps.",
                            "price": "R950-R1,500",
                        },
                        {
                            "id": "complex",
                            "name": "Complex Evidence Pack",
                            "promise": "A larger multi-source pack scoped after intake.",
                            "price": "R2,500-R5,000",
                        },
                    ],
                }
            },
        },
    )
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
                    "risk_boundary": "Research Integrity does not ghostwrite or replace publication authority.",
                }
            ],
        },
    )
    return tmp_path


def test_reference_offers_parse_governed_zar_ranges(tmp_path: Path):
    root = make_root(tmp_path)
    offers = reference_offers(root, "evidex")
    assert [(row["offer_id"], row["min_amount"], row["max_amount"]) for row in offers] == [
        ("starter", 350, 750),
        ("standard", 950, 1500),
        ("complex", 2500, 5000),
    ]
    assert all(row["currency"] == "ZAR" for row in offers)
    assert all(row["authority_created"] is False for row in offers)


def test_evidex_tiny_pack_uses_governed_starter_band(tmp_path: Path):
    root = make_root(tmp_path)
    result = recommend_quote(
        root,
        product_id="evidex",
        scope={"file_count": 3, "complexity": "low"},
    )
    assert result["mode"] == "known_band"
    assert result["offer_id"] == "starter"
    assert result["currency"] == "ZAR"
    assert result["min_amount"] == 350
    assert result["max_amount"] == 750
    assert result["authority_created"] is False


def test_evidex_broader_pack_selects_standard_band_deterministically(tmp_path: Path):
    root = make_root(tmp_path)
    result = recommend_quote(
        root,
        product_id="evidex",
        scope={"file_count": 12, "complexity": "normal"},
    )
    assert result["mode"] == "scope_sensitive"
    assert result["offer_id"] == "standard"
    assert result["min_amount"] == 950
    assert result["max_amount"] == 1500
    assert "file_count" in result["reasoning"]


def test_research_integrity_full_article_requires_operator_when_public_offer_is_one_section(tmp_path: Path):
    root = make_root(tmp_path)
    result = recommend_quote(
        root,
        product_id="dio_research_integrity",
        scope={"page_count": 20, "requested_depth": "full_document"},
    )
    assert result["mode"] == "needs_operator"
    assert result["reason"] == "scope_exceeds_governed_offer"
    assert result["governed_offer"] == "One-Section Claim Lineage Pilot"
    assert result["authority_created"] is False
    assert "min_amount" not in result
    assert "max_amount" not in result


def test_unknown_product_without_governed_price_never_gets_invented_number(tmp_path: Path):
    root = make_root(tmp_path)
    result = recommend_quote(root, product_id="unknown_product", scope={"page_count": 5})
    assert result["mode"] == "needs_operator"
    assert result["reason"] == "no_governed_price"
    assert "min_amount" not in result
    assert "max_amount" not in result


def test_structured_history_may_narrow_inside_governed_band_but_not_escape_it(tmp_path: Path):
    root = make_root(tmp_path)
    result = recommend_quote(
        root,
        product_id="evidex",
        scope={"file_count": 3, "complexity": "low"},
        historical_rows=[
            {
                "product_id": "evidex",
                "offer_id": "starter",
                "final_invoice_amount": 600,
                "payment_outcome": "paid",
                "file_count": 3,
                "complexity": "low",
            },
            {
                "product_id": "evidex",
                "offer_id": "starter",
                "final_invoice_amount": 650,
                "payment_outcome": "paid",
                "file_count": 4,
                "complexity": "low",
            },
        ],
    )
    assert result["mode"] == "scope_sensitive"
    assert 350 <= result["recommended_amount"] <= 750
    assert result["recommended_amount"] in {600, 625, 650}
    assert result["comparables_used"] == 2
    assert result["authority_created"] is False
