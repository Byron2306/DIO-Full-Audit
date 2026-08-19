from __future__ import annotations

import json
from pathlib import Path

import portfolio_runtime
from operator_production import DIRECT_EVIDENCE_INCARNATIONS, FACTORY_TESTS, production_state

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_portfolio_self_hydrates_without_promoting_atlas_candidates(tmp_path, monkeypatch):
    state_path = tmp_path / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"
    monkeypatch.setattr(portfolio_runtime, "STATE_PATH", state_path)
    receipt = portfolio_runtime.import_portfolio(force=True)
    assert receipt["canonical_incarnation_count"] == 53
    assert len(receipt["incarnations"]) == 53
    assert receipt["candidate_incarnations_imported"] == 0
    assert all(row["portfolio_identity"] == "canonical_incarnation" for row in receipt["incarnations"])
    assert all(row["candidate_product"] is False for row in receipt["incarnations"])
    assert state_path.is_file()
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["source"]["kind"] == "canonical_incarnation_crosswalk"


def test_production_state_exposes_real_marketing_profiles_evidence_lanes_and_test_bench():
    state = production_state()
    assert state["portfolio"]["count"] == 53
    assert state["portfolio"]["candidate_incarnations_imported"] == 0
    profiles = {row["id"] for row in state["marketing"]["profiles"]}
    assert {"EVIDEX_PACK", "HOMS_ASSESS", "HOMS_LEARNING", "SOPHIA_REVIEW", "VAMP_ACADEMIC", "DOCUMENT_STUDIO"}.issubset(profiles)
    outputs = set(next(row for row in state["marketing"]["profiles"] if row["id"] == "EVIDEX_PACK")["outputs"])
    assert {"square_1080", "landscape_1200x628", "portrait_1080x1350", "vertical_1080x1920", "youtube_1280x720", "channel_copy", "reel_scenes", "nichefoundry_reel"}.issubset(outputs)
    lane_ids = {row["id"] for row in state["evidence_lanes"]}
    assert {"HOMS_EVIDEX", "SOPHIA", "VAMP", "DOCUMENT_STUDIO", "EVIDENCE_PACKAGE_GATE"}.issubset(lane_ids)
    assert state["fresh_evidence_runs"]["direct_incarnations"] == DIRECT_EVIDENCE_INCARNATIONS
    assert len(state["factory_tests"]) == len(FACTORY_TESTS) == 5
    assert state["truth"]["marketing_asset_created_is_publication"] is False
    assert state["truth"]["marketing_asset_created_is_market_validation"] is False
    assert state["truth"]["controlled_evidence_run_is_customer_validation"] is False
    assert state["truth"]["factory_test_is_market_validation"] is False
    assert state["truth"]["authority_created"] is False


def test_fresh_evidence_run_is_limited_to_product_specific_direct_adapters():
    assert DIRECT_EVIDENCE_INCARNATIONS == {
        "Evidex EvidenceOps": "EVIDEX",
        "HOMS Assess": "HOMS",
        "Sophia Review": "SOPHIA",
        "VAMP Performance": "VAMP",
        "Document Studio Edit": "DOCUMENT_STUDIO",
        "Document Studio Localize": "DOCUMENT_STUDIO",
        "Document Studio Publish": "DOCUMENT_STUDIO",
    }
    source = (ROOT / "operator_production.py").read_text(encoding="utf-8")
    assert "has no product-specific fresh-intake adapter in Production Studio yet" in source
    assert '"controlled": True' in source
    assert '"payment_required": False' in source
    assert '"external_release_authorized": False' in source


def test_factory_test_bench_points_only_to_fixed_repo_scripts():
    for details in FACTORY_TESTS.values():
        script = ROOT / "scripts" / details["script"]
        assert script.is_file(), script
    assert FACTORY_TESTS["CONTRACTPROOF_PHASE5"]["persistent_product_output"] is False
    assert FACTORY_TESTS["OBLIGATION_FAMILY_PHASE6"]["persistent_product_output"] is False
    assert FACTORY_TESTS["REFERENCE_INCARNATION_PHASE7"]["output_arg"] is True
    assert FACTORY_TESTS["INCARNATION_STUDIO_PHASE16"]["output_arg"] is True
    assert FACTORY_TESTS["MEDIA_INCARNATION_PHASE16_1"]["output_arg"] is True


def test_business_deployment_uses_production_workbench_and_market_auto_imports():
    unit = (ROOT / "deploy" / "systemd" / "dio-control-deck.service").read_text(encoding="utf-8")
    business = (ROOT / "scripts" / "serve_business_workbench.py").read_text(encoding="utf-8")
    market = (ROOT / "scripts" / "serve_market_command_ms10.py").read_text(encoding="utf-8")
    assert "serve_business_workbench.py" in unit
    assert "import_portfolio(force=False)" in business
    for endpoint in (
        "/api/business/production/marketing",
        "/api/business/production/evidence-run",
        "/api/business/production/factory-test",
        "/api/business/production/evidence-gate",
    ):
        assert endpoint in business
    assert "PROFILE_COMPATIBILITY" in business
    assert "Marketing profile {profile_id} is not evidence-compatible" in business
    assert "load_portfolio(auto_import=True)" in market
    assert '"candidate_incarnations_imported": registry.get("candidate_incarnations_imported", 0)' in market


def test_production_studio_is_an_operator_workflow_not_a_claim_wall():
    page = (ROOT / "dashboard" / "production.html").read_text(encoding="utf-8")
    for marker in (
        "Marketing Asset Factory",
        "CREATE MARKETING PACK",
        "NEW EVIDENCE RUN",
        "CREATE CONTROLLED EVIDENCE JOB",
        "Live Product Evidence Pipelines",
        "Factory Test Bench",
        "RUN TEST / EXAMPLE",
        "RUN EVIDENCE GATE",
        "/api/business/production/marketing",
        "/api/business/production/evidence-run",
        "/api/business/production/factory-test",
        "/api/business/production/evidence-gate",
        "/api/control/product/action",
        "/api/control/sophia/action",
        "/api/control/vamp/action",
        "/api/control/document-studio/action",
        "Publication and spend remain held",
    ):
        assert marker in page


def test_custom_marketing_requires_operator_claim_and_real_proof_for_reel():
    source = (ROOT / "operator_production.py").read_text(encoding="utf-8")
    assert 'required = ("audience_name", "pain", "outcome", "cta", "marketing_statement")' in source
    assert "Rendered reel for a custom incarnation requires an actual product proof asset" in source
    assert '"publication_authorized": False' in source
    assert '"spend_authorized": False' in source
    assert '"market_validation_claimed": False' in source


def test_product_specific_fresh_intake_contracts_are_not_collapsed_into_generic_text():
    source = (ROOT / "operator_production.py").read_text(encoding="utf-8")
    for marker in (
        "manuscript_owner_authorized",
        "gemini_remote_processing_approved",
        "research_question",
        "vamp_sqlite",
        "profile_path",
        "database_path",
        "review",
        "document_owner_authorized",
        "certified_translation_not_requested",
        "hymark_input_dir",
        "rubric.json",
        "evidence_text",
    ):
        assert marker in source
