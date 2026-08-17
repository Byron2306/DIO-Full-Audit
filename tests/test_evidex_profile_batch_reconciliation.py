from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATED = {
    "assuranceroom": ("dio_assuranceroom", "config/products/profiles/assuranceroom.json", "products/assuranceroom/runner.py"),
    "impactproof": ("dio_impactproof", "config/products/profiles/impactproof.json", "products/unpromoted_evidence_profile.py"),
    "projectproof": ("dio_projectproof", "config/products/profiles/projectproof.json", "products/unpromoted_evidence_profile.py"),
    "certificationproof": ("dio_certificationproof", "config/products/profiles/certificationproof.json", "products/unpromoted_evidence_profile.py"),
    "diligenceroom": ("dio_diligenceroom", "config/products/profiles/diligenceroom.json", "products/unpromoted_evidence_profile.py"),
    "donorproof": ("dio_donorproof", "config/products/profiles/donorproof.json", "products/unpromoted_evidence_profile.py"),
}


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_validated_evidex_batch_records_processing_without_promotion_authority() -> None:
    reconciliation = _load("config/product_class_reconciliation.json")
    routes = _load("config/product_class_routes.json")

    for profile_id, (product_id, typed_profile, processor) in VALIDATED.items():
        row = reconciliation["genuine_profile_extensions"][profile_id]
        assert row["suggested_engine"] == "evidex"
        assert row["profile_product_id"] == product_id
        assert row["canonical_portfolio_registration"] is False
        assert row["typed_profile"] == typed_profile
        assert row["controlled_processor"] == processor
        assert row["processing_state"] == "controlled_internal_processing_validated"
        assert row["processing_receipt_kind"] == "controlled_processing_not_execution_proof"
        assert row["product_execution_proved"] is False
        assert row["external_release_authorized"] is False

        route = routes["product_classes"][profile_id]
        assert route["route_kind"] == "profile_extension"
        assert route["suggested_engine"] == "evidex"
        assert route["auto_promotable"] is False

        assert profile_id not in reconciliation["exact_canonical_incarnations"]
        assert profile_id not in reconciliation["equivalence_candidates"]
        assert profile_id not in reconciliation["resolved_composition_bindings"]


def test_unvalidated_remaining_evidex_profiles_are_not_prematurely_stamped() -> None:
    reconciliation = _load("config/product_class_reconciliation.json")
    for profile_id in ("programmeproof", "qualityproof"):
        row = reconciliation["genuine_profile_extensions"][profile_id]
        assert row == {"suggested_engine": "evidex"}
