from __future__ import annotations

import json
from pathlib import Path

from products.registry import bootstrap_generic_job, load_portfolio, product_profiles
from scripts.reconcile_product_portfolio import reconcile_once
from scripts.route_intake import load_routes, normalize_record, route_record


EXPECTED_PRODUCTS = {
    "dio_assurance",
    "dio_agent_authority",
    "dio_vendorproof",
    "dio_accreditation",
    "dio_tenderproof",
    "dio_grantproof",
    "dio_research_integrity",
    "dio_regops",
    "dio_capitalroom",
}


def test_portfolio_registers_all_wave1_products() -> None:
    portfolio = load_portfolio()
    assert portfolio["schema"] == "dio.product_portfolio.v1"
    assert set(product_profiles()) == EXPECTED_PRODUCTS


def test_every_product_preserves_human_authority_and_truth_boundary() -> None:
    for profile in product_profiles().values():
        assert profile["required_authorities"]
        assert profile["activation_gates"]
        assert profile["risk_boundary"]
        assert profile["status"]
        assert "proof_asset" in profile


def test_capitalroom_is_internal_and_not_public_campaignable() -> None:
    capitalroom = product_profiles()["dio_capitalroom"]
    assert capitalroom["runtime_mode"] == "internal_only"
    assert capitalroom["customer_facing"] is False
    assert capitalroom["campaign_enabled"] is False


def _route(text: str) -> str:
    record = normalize_record({"subject": text, "body": text, "sender": "operator@example.org"})
    return str(route_record(record, load_routes())["product"])


def test_specific_new_routes_beat_broad_legacy_keywords() -> None:
    assert _route("AI governance inventory and ISO 42001 assurance review") == "dio_assurance"
    assert _route("Please review this grant agreement and donor obligations") == "dio_grantproof"
    assert _route("We need regulatory readiness for a compliance obligation") == "dio_regops"
    assert _route("Vendor due diligence questionnaire for third-party risk") == "dio_vendorproof"
    assert _route("Tender compliance mandatory requirements review") == "dio_tenderproof"


def _write_routed_job(runs_root: Path, product: str, job_id: str) -> Path:
    path = runs_root / "mailbox-auto-test" / product / f"{job_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": job_id,
        "created_at": "2026-08-11T00:00:00+00:00",
        "route": {"product": product, "confidence": 0.95, "reason": "test"},
        "source": {
            "kind": "outlook_triage",
            "message_id": "MSG-001",
            "thread_ref": "THREAD-001",
            "lead_id": "LEAD-001",
            "conversation_id": "CONV-001"
        },
        "approval": {"required": True, "state": "pending"},
        "evidence": [{"evidence_id": "EVID-001"}],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_generic_bootstrap_is_idempotent_and_non_executing(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    state_root = tmp_path / "state" / "product_jobs"
    source = _write_routed_job(runs_root, "dio_assurance", "dio_assurance-test-job")

    first = bootstrap_generic_job(source, state_root, runs_root)
    second = bootstrap_generic_job(source, state_root, runs_root)

    assert first == second
    assert first["schema"] == "dio.generic_product_workflow.v1"
    assert first["product"] == "dio_assurance"
    assert first["capability"]["classification"] == "registered"
    assert first["capability"]["execution"] == "not_implemented"
    assert first["capability"]["external_release"] == "held"
    assert first["processing"]["state"] == "not_started"
    assert first["processing"]["profile_state"] == "registered"
    assert first["delivery"]["state"] == "held"
    assert first["output_review"]["required"] is True
    assert (state_root / "dio_assurance-test-job" / "JOB.json").is_file()


def test_reconciler_promotes_mailbox_jobs_into_canonical_product_state(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    state_root = tmp_path / "state" / "product_jobs"
    _write_routed_job(runs_root, "dio_vendorproof", "dio_vendorproof-test-job")

    first = reconcile_once(runs_root, state_root)
    second = reconcile_once(runs_root, state_root)

    assert first["seen"] == 1
    assert first["created"] == 1
    assert first["failed"] == []
    assert second["seen"] == 1
    assert second["created"] == 0
    assert second["unchanged"] == 1
    workflow = json.loads((state_root / "dio_vendorproof-test-job" / "JOB.json").read_text(encoding="utf-8"))
    assert workflow["product"] == "dio_vendorproof"
    assert workflow["capability"]["execution"] == "not_implemented"
