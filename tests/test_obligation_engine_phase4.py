from __future__ import annotations

import copy
from pathlib import Path

import pytest

from dio.obligations.engine import build, project, validate_bundle
from dio.obligations.extractor import extract
from products.compiler import compile_manifest, load_capability_catalog
from products.governed_case import add_evidence, new_case
from products.work_pattern_runtime import plan_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "products" / "manifests" / "contractproof.json"
NOW = "2026-08-12T12:00:00+00:00"


def _source() -> dict:
    return {
        "source_id": "contract-reference-001",
        "source_type": "contract",
        "source_ref": "contract://reference-001",
        "sha256": "a" * 64,
        "effective_at": "2026-07-01T00:00:00+00:00",
        "expires_at": None,
        "clauses": [
            {"clause_id": "4.2", "text": "Supplier shall provide the monthly service report.", "obligation": True, "obligation_kind": "reporting", "responsible_party": "supplier", "due_at": "2026-09-01T12:00:00+00:00", "evidence_requirements": ["delivery_receipt"]},
            {"clause_id": "5.1", "text": "Customer shall pay the accepted invoice.", "obligation": True, "obligation_kind": "payment", "responsible_party": "customer", "due_at": "2026-08-01T12:00:00+00:00", "evidence_requirements": ["payment_receipt"]},
            {"clause_id": "6.3", "text": "Supplier shall provide the onboarding dossier.", "obligation": True, "obligation_kind": "deliverable", "responsible_party": "supplier", "due_at": "2026-09-01T12:00:00+00:00", "evidence_requirements": ["signed_form", "identity_copy"]},
            {"clause_id": "7.4", "text": "Supplier shall maintain the specified certificate.", "obligation": True, "obligation_kind": "maintenance", "responsible_party": "supplier", "expires_at": "2026-08-01T12:00:00+00:00", "evidence_requirements": ["certificate"]},
            {"clause_id": "8.1", "text": "Supplier shall send the transition notice.", "obligation": True, "obligation_kind": "notification", "responsible_party": "supplier", "due_at": "2026-09-15T12:00:00+00:00", "evidence_requirements": ["notice_receipt"]},
            {"clause_id": "9.2", "text": "Supplier must notify the owner of a material service interruption.", "obligation_kind": "notification", "responsible_party": "supplier", "evidence_requirements": ["incident_notice"]},
            {"clause_id": "10.1", "text": "Supplier should cooperate with the customer where practical.", "obligation_kind": "other"},
        ],
    }


def _ids_by_locator(source: dict) -> dict[str, str]:
    return {row["source_locator"]: row["obligation_id"] for row in extract(source)}


def _status_by_locator(bundle: dict) -> dict[str, str]:
    return {row["source"]["locator"]: row["status"] for row in bundle["obligations"]}


def test_extraction_is_source_bound_and_conservative() -> None:
    rows = extract(_source())
    by_locator = {row["source_locator"]: row for row in rows}
    assert "10.1" not in by_locator
    assert by_locator["4.2"]["extraction_basis"] == "explicit_structured_obligation"
    assert by_locator["4.2"]["review_required"] is False
    assert by_locator["9.2"]["extraction_basis"] == "deontic_candidate"
    assert by_locator["9.2"]["review_required"] is True


def test_evaluation_covers_bounded_states_without_compliance_verdicts() -> None:
    source = _source()
    ids = _ids_by_locator(source)
    bundle = build(source, now=NOW, evidence_records=[
        {"evidence_id": "EVID-REPORT", "obligation_ids": [ids["4.2"]], "evidence_kind": "delivery_receipt", "source_ref": "evidence://report", "trust_state": "trusted_for_review", "freshness_state": "current"},
        {"evidence_id": "EVID-SIGNED", "obligation_ids": [ids["6.3"]], "evidence_kind": "signed_form", "source_ref": "evidence://signed", "trust_state": "trusted_for_review", "freshness_state": "current"},
    ])
    status = _status_by_locator(bundle)
    assert status["4.2"] == "SATISFIED"
    assert status["5.1"] == "MISSING"
    assert status["6.3"] == "PARTIAL"
    assert status["7.4"] == "EXPIRED"
    assert status["8.1"] == "NOT_YET_DUE"
    assert status["9.2"] == "NEEDS_REVIEW"
    assert set(status.values()).isdisjoint({"COMPLIANT", "LEGAL", "VALID", "APPROVED"})
    assert bundle["human_gate"]["state"] == "NEEDS_YOU"
    assert bundle["authority_created"] is False and bundle["executor_created"] is False and bundle["external_effects"] is False


def test_deadlines_are_derived_only_from_explicit_normalized_dates() -> None:
    source = _source()
    ids = _ids_by_locator(source)
    bundle = build(source, now=NOW)
    by_obligation: dict[str, list[dict]] = {}
    for row in bundle["deadlines"]:
        by_obligation.setdefault(row["obligation_id"], []).append(row)
    assert by_obligation[ids["4.2"]][0]["state"] == "open"
    assert by_obligation[ids["5.1"]][0]["state"] == "overdue"
    assert by_obligation[ids["7.4"]][0]["state"] == "expired"
    assert ids["9.2"] not in by_obligation


def test_expiry_is_effective_at_the_exact_expiry_instant() -> None:
    source = _source()
    exact = "2026-08-01T12:00:00+00:00"
    bundle = build(source, now=exact)
    ids = _ids_by_locator(source)
    expiry_deadline = next(row for row in bundle["deadlines"] if row["obligation_id"] == ids["7.4"] and row["kind"] == "expiry")
    assert expiry_deadline["state"] == "expired"
    assert _status_by_locator(bundle)["7.4"] == "EXPIRED"


def test_contradiction_and_stale_evidence_remain_conservative() -> None:
    source = _source()
    ids = _ids_by_locator(source)
    contested = build(source, now=NOW, evidence_records=[
        {"evidence_id": "EVID-SUPPORT", "obligation_ids": [ids["4.2"]], "evidence_kind": "delivery_receipt", "trust_state": "trusted_for_review", "freshness_state": "current"},
        {"evidence_id": "EVID-CONTRA", "obligation_ids": [ids["4.2"]], "evidence_kind": "delivery_receipt", "relation": "contradicts", "trust_state": "trusted_for_review", "freshness_state": "current"},
    ])
    assert _status_by_locator(contested)["4.2"] == "CONTESTED"
    stale = build(source, now=NOW, evidence_records=[
        {"evidence_id": "EVID-STALE", "obligation_ids": [ids["5.1"]], "evidence_kind": "payment_receipt", "trust_state": "trusted_for_review", "freshness_state": "stale"}
    ])
    assert _status_by_locator(stale)["5.1"] == "MISSING"


def test_bundle_fingerprint_and_schema_detect_mutation_or_authority_leakage() -> None:
    bundle = build(_source(), now=NOW)
    tampered = copy.deepcopy(bundle)
    tampered["obligations"][0]["statement"] += " altered"
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_bundle(tampered)
    forbidden = copy.deepcopy(bundle)
    forbidden["obligations"][0]["compliant"] = True
    with pytest.raises(ValueError, match="schema validation failed"):
        validate_bundle(forbidden)


def test_projection_adds_requirements_and_evidence_without_mutating_authority_surfaces() -> None:
    case = new_case(product="dio_contractproof", job_id="phase4-projection", source={"source": {}}, source_path=MANIFEST, evidence_inputs=[], expected_outputs=["evidence_pack"], required_authorities=["human.contract_owner"], intake_state="approved", now=NOW)
    evidence = add_evidence(case, kind="delivery_receipt", source_ref="evidence://report", trust_state="trusted_for_review", freshness_state="current")
    source = {"source_id": "projection-contract", "source_type": "contract", "source_ref": "contract://projection", "sha256": "b" * 64, "effective_at": None, "expires_at": None, "clauses": [{"clause_id": "1.1", "text": "Supplier shall provide the report.", "obligation": True, "obligation_kind": "reporting", "due_at": "2026-09-01T12:00:00+00:00", "evidence_requirements": ["delivery_receipt"]}]}
    obligation_id = extract(source)[0]["obligation_id"]
    bundle = build(source, now=NOW, evidence_records=[{"evidence_id": evidence["evidence_id"], "obligation_ids": [obligation_id], "evidence_kind": "delivery_receipt", "source_ref": evidence["source_ref"], "trust_state": "trusted_for_review", "freshness_state": "current"}])
    before = copy.deepcopy({key: case[key] for key in ("gates", "actions", "decisions")})
    receipt = project(bundle, case)
    after = {key: case[key] for key in ("gates", "actions", "decisions")}
    assert after == before
    assert receipt["authority_created"] is False and receipt["execution_performed"] is False


def test_four_obligation_capabilities_remain_one_shared_nonexecuting_provider() -> None:
    catalog, _ = load_capability_catalog(ROOT)
    provider_ids = set()
    for capability_id in ("obligation.extract", "obligation.normalize", "obligation.deadlines", "obligation.evaluate"):
        row = catalog[capability_id]
        assert row["status"] == "available"
        assert len(row["providers"]) == 1
        provider = row["providers"][0]
        provider_ids.add(provider["provider_id"])
        assert provider["ref"] == "dio/obligations/engine.py"
        assert provider["product_scope"] == ["*"]
        assert provider["execution_capable"] is False
    assert provider_ids == {"obligation_core_v1"}


def test_wp05_stays_ready_even_as_contractproof_later_earns_proof_and_executor() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    patterns = {row["work_pattern_id"]: row for row in plan["patterns"]}
    assert patterns["WP05"]["runtime_state"] == "READY"
    assert all(row["resolution_state"] == "RESOLVED" for row in patterns["WP05"]["operations"])
    assert plan["execution_gate"]["state"] == "REFUSE"
    assert plan["compiler_execution_gate"]["state"] in {"REFUSE", "NEEDS_YOU"}
    assert plan["authority_created"] is False and plan["executor_created"] is False


def test_compiler_resolves_obligation_core_without_confusing_it_with_product_executor() -> None:
    compiled = compile_manifest(ROOT, MANIFEST)
    capabilities = {row["capability_id"]: row for row in compiled["capability_plan"]}
    for capability_id in ("obligation.extract", "obligation.normalize", "obligation.deadlines", "obligation.evaluate"):
        assert capabilities[capability_id]["resolution_state"] == "RESOLVED"
        assert capabilities[capability_id]["provider"]["provider_id"] == "obligation_core_v1"
        assert capabilities[capability_id]["provider"]["execution_capable"] is False
    if capabilities["product.executor.contractproof"]["resolution_state"] == "RESOLVED":
        assert capabilities["product.executor.contractproof"]["provider"]["provider_id"] != "obligation_core_v1"
    assert compiled["gates"]["execution"]["state"] in {"REFUSE", "NEEDS_YOU"}
    assert compiled["gates"]["external_release"]["state"] == "REFUSE"
