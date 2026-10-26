import hashlib
import json
from pathlib import Path

import pytest

from metamorphic.registry import build_reference_registry
from metamorphic.semantic_law import (
    DEFAULT_CONFIG,
    PHASE3_EXIT_TOKEN,
    SemanticLawError,
    build_reference_semantic_laws,
    evaluate_claim,
    phase3_semantic_receipt,
    project_semantics,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase3_receipt_proves_exact_three_semantic_laws():
    receipt = phase3_semantic_receipt(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE3_EXIT_TOKEN
    assert receipt["unit_count"] == 3
    assert receipt["semantic_law_promoted"] is True
    assert receipt["four_layer_semantic_model"] == ["DENOTATION", "AFFORDANCE", "PROHIBITION", "PROJECTION"]
    assert receipt["site_studio_reference_excluded"] is True


def test_phase3_each_law_has_all_four_semantic_layers():
    laws = build_reference_semantic_laws(REPO_ROOT)
    assert set(laws) == {
        "article_publication_studio",
        "finance_readiness_studio",
        "professional_correspondence_studio",
    }
    for law in laws.values():
        assert law.denotation
        assert law.affordances
        assert law.prohibitions
        assert set(law.projections) == {"direct_product", "nested_capability", "technical_proof"}


def test_phase3_lingua_anchors_are_bound_to_current_repo_bytes():
    config = json.loads((REPO_ROOT / DEFAULT_CONFIG).read_text(encoding="utf-8"))
    laws = build_reference_semantic_laws(REPO_ROOT)
    for law in laws.values():
        assert set(law.lingua_anchor_digests) == set(config["lingua_anchors"])
        for relative, digest in law.lingua_anchor_digests.items():
            assert digest == _sha(REPO_ROOT / relative)


def test_phase3_semantic_law_preserves_phase2_unit_identity():
    registry = build_reference_registry(REPO_ROOT)
    laws = build_reference_semantic_laws(REPO_ROOT)
    for unit in registry.units():
        law = laws[unit.unit_id]
        assert law.unit_id == unit.unit_id
        assert law.unit_digest == unit.unit_digest
        assert law.source_digest == unit.source_digest
        assert law.authority_ceiling == unit.authority_ceiling


def test_phase3_every_refused_manifest_authority_is_a_semantic_prohibition():
    laws = build_reference_semantic_laws(REPO_ROOT)
    expected = {
        "authority.external_publication",
        "authority.external_send",
        "authority.media_spend",
        "authority.payment",
    }
    for law in laws.values():
        ids = {row["id"] for row in law.prohibitions}
        assert expected.issubset(ids)
        for claim_id in expected:
            verdict = evaluate_claim(law, claim_id)
            assert verdict["verdict"] == "REFUSE"
            assert verdict["authority_created"] is False


def test_phase3_professional_quality_does_not_become_commercial_claims():
    laws = build_reference_semantic_laws(REPO_ROOT)
    expected = {
        "proof.verified_payment",
        "proof.customers_will_pay",
        "proof.customer_acceptance",
        "proof.commercial_validation",
    }
    for law in laws.values():
        ids = {row["id"] for row in law.prohibitions}
        assert expected.issubset(ids)
        assert all(evaluate_claim(law, claim_id)["verdict"] == "REFUSE" for claim_id in expected)


def test_phase3_source_forbidden_claims_are_preserved_not_sanitized():
    laws = build_reference_semantic_laws(REPO_ROOT)
    correspondence = " ".join(str(row["rule"]) for row in laws["professional_correspondence_studio"].prohibitions).casefold()
    finance = " ".join(str(row["rule"]) for row in laws["finance_readiness_studio"].prohibitions).casefold()
    article = " ".join(str(row["rule"]) for row in laws["article_publication_studio"].prohibitions).casefold()
    assert "settlement agreement" in correspondence
    assert "guaranteed finance approval" in finance
    assert "automatic publication" in article


def test_phase3_direct_and_nested_projection_change_role_language_not_identity():
    law = build_reference_semantic_laws(REPO_ROOT)["finance_readiness_studio"]
    direct = project_semantics(law, "direct_product")
    nested = project_semantics(law, "nested_capability")
    assert direct["unit_id"] == nested["unit_id"] == law.unit_id
    assert direct["unit_digest"] == nested["unit_digest"] == law.unit_digest
    assert direct["authority_ceiling"] == nested["authority_ceiling"] == "controlled_artifact_only"
    assert direct["title"] != nested["title"]
    assert nested["external_authority_created"] is False


def test_phase3_exported_capability_claim_is_supported_without_authority_creation():
    law = build_reference_semantic_laws(REPO_ROOT)["article_publication_studio"]
    verdict = evaluate_claim(law, "export.article_publication")
    assert verdict["verdict"] == "SUPPORTED"
    assert verdict["unit_digest"] == law.unit_digest
    assert verdict["authority_created"] is False


def test_phase3_unknown_claim_stays_unresolved():
    law = build_reference_semantic_laws(REPO_ROOT)["professional_correspondence_studio"]
    verdict = evaluate_claim(law, "export.autonomous_legal_settlement")
    assert verdict["verdict"] == "UNRESOLVED"
    assert verdict["authority_created"] is False


def test_phase3_projection_context_fails_closed_when_unknown():
    law = build_reference_semantic_laws(REPO_ROOT)["professional_correspondence_studio"]
    with pytest.raises(SemanticLawError):
        project_semantics(law, "secret_autonomous_mode")


def test_phase3_learning_contract_declares_learning_without_direct_execution():
    laws = build_reference_semantic_laws(REPO_ROOT)
    for law in laws.values():
        assert law.learning_contract["semantic_observations_may_be_recorded"] is True
        assert law.learning_contract["learning_outputs_are_candidates_only"] is True
        assert law.learning_contract["direct_learning_to_execution"] is False
        assert law.learning_contract["crystallization_authority"] == "BEAST"
        assert law.learning_contract["human_approval_required_for_promoted_meaning"] is True
        assert law.learning_contract["market_feedback_learning_deferred"] is True


def test_phase3_does_not_pretend_resolver_beast_or_market_learning_already_ran():
    receipt = phase3_semantic_receipt(REPO_ROOT)
    assert receipt["resolver_policy_implemented"] is False
    assert receipt["composition_dag_implemented"] is False
    assert receipt["beast_crystallization_executed"] is False
    assert receipt["market_feedback_learning_executed"] is False
    assert receipt["new_engine_created"] is False
    assert receipt["authority_widened"] is False


def test_phase3_semantic_law_digest_is_deterministic():
    first = build_reference_semantic_laws(REPO_ROOT)
    second = build_reference_semantic_laws(REPO_ROOT)
    assert {key: law.law_digest for key, law in first.items()} == {key: law.law_digest for key, law in second.items()}
