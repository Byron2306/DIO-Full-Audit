from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from products.ai_trust.core import build_trust_envelope
from products.ai_trust.runner import PRODUCTS, run_ai_trust
from products.ai_trust.seraph_telemetry import EVENT_GENESIS, AUDIT_GENESIS
from products.ai_trust_gauntlet import ACCEPTANCE_TOKEN, run_gauntlet
from products.compiler import compile_manifest

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-16T12:00:00+00:00"


def _fixture(slug: str) -> dict:
    return json.loads((ROOT / "config/products/golden" / slug / "reference_case.json").read_text())


@pytest.mark.parametrize("product_id,definition", sorted(PRODUCTS.items()))
def test_three_ai_trust_incarnations_compile_with_six_profile_axes(product_id: str, definition: dict) -> None:
    compiled = compile_manifest(ROOT, ROOT / "config/products/manifests" / f"{definition['slug']}.json")
    assert compiled["product_id"] == product_id
    assert {row["profile_class"] for row in compiled["profile_bindings"]} == {
        "domain", "framework", "authority", "connector", "output", "commercial"
    }
    assert all(row["resolution_state"] == "RESOLVED" for row in compiled["capability_plan"] if row["required"])
    assert compiled["gates"]["execution"]["state"] == "NEEDS_YOU"
    assert compiled["gates"]["external_release"]["state"] == "REFUSE"


def test_agentauthority_refuses_poisoned_send_but_preserves_draft_candidate() -> None:
    envelope = build_trust_envelope("dio_agentauthority", _fixture("agentauthority"), now=NOW)
    states = {row["dimension"]: row["state"] for row in envelope["dimensions"]}
    decisions = {row["effect"]: row["decision"] for row in envelope["action_decisions"]}
    assert states["tool_safety"] == "REFUSE"
    assert decisions == {"draft": "REFUSE", "external_send": "REFUSE"}
    assert len(envelope["prompt_injection_signals"]) >= 2
    assert envelope["authority_created"] is False
    assert envelope["external_effects"] is False


def test_untrusted_content_never_grants_a_capability() -> None:
    payload = _fixture("agentauthority")
    payload["allowed_capabilities"].append({"tool": "outlook", "target": "customer@example.invalid", "effect": "external_send"})
    envelope = build_trust_envelope("dio_agentauthority", payload, now=NOW)
    assert all(row["decision"] == "REFUSE" for row in envelope["action_decisions"])


def test_model_change_keeps_stale_drift_and_tamper_states_independent() -> None:
    envelope = build_trust_envelope("dio_modelchangeproof", _fixture("modelchangeproof"), now=NOW)
    states = {row["dimension"]: row["state"] for row in envelope["dimensions"]}
    assert states["identity"] == "SUPPORTED"
    assert states["evaluation"] == "STALE"
    assert states["freshness"] == "STALE"
    assert states["drift"] == "CONTESTED"
    assert states["integrity"] == "CONTESTED"
    assert states["release"] == "REFUSE"


def test_ai_trust_dossier_is_human_readable_and_hash_bound(tmp_path: Path) -> None:
    result = run_ai_trust("dio_aitrustproof", _fixture("aitrustproof"), output_dir=tmp_path,
                          operator_id="human.phase13_test", now=NOW)
    output = Path(result["output_dir"])
    assert (output / "AI_TRUST_DOSSIER.pdf").read_bytes().startswith(b"%PDF")
    assert (output / "AI_TRUST_DOSSIER.docx").read_bytes().startswith(b"PK")
    html = (output / "AI_TRUST_DOSSIER.html").read_text()
    assert "Trust dimensions" in html
    assert "HUMAN DECISION REQUIRED" in html
    dossier = json.loads((output / "AI_TRUST_DOSSIER.json").read_text())
    assert set(dossier) == {"system_identity", "trust_dimensions", "evaluation_registry", "drift_register",
                            "untrusted_content_register", "tool_decisions", "human_review", "provenance_manifest"}
    for artifact in result["proof_manifest"]["artifacts"]:
        assert hashlib.sha256((output / artifact["filename"]).read_bytes()).hexdigest() == artifact["sha256"]
    seraph = json.loads((output / "SERAPH_CHALLENGE_RECEIPT.json").read_text())
    assert seraph["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert seraph["coverage_state"] == "partial"
    assert seraph["execution_authorized"] is False
    assert result["proof_manifest"]["seraph_challenge_sha256"] == seraph["receipt_sha256"]
    assert result["receipt"]["seraph_challenge_sha256"] == seraph["receipt_sha256"]


@pytest.mark.parametrize("slug,verdict,expected_finding", [
    ("aitrustproof", "INSUFFICIENT_EVIDENCE", "AI-SOURCE-OBSERVATION-GAP"),
    ("agentauthority", "HOSTILE", "AI-UNTRUSTED-INSTRUCTIONS"),
    ("modelchangeproof", "CONTESTED", "AI-DRIFT"),
])
def test_seraph_challenges_each_ai_proof_without_granting_authority(
    tmp_path: Path, slug: str, verdict: str, expected_finding: str,
) -> None:
    product_id = next(pid for pid, definition in PRODUCTS.items() if definition["slug"] == slug)
    result = run_ai_trust(product_id, _fixture(slug), output_dir=tmp_path / slug,
                          operator_id="human.seraph_test", now=NOW)
    seraph = result["seraph_challenge"]
    assert seraph["verdict"] == verdict
    assert expected_finding in {row["finding_id"] for row in seraph["findings"]}
    assert seraph["target_id"] == result["envelope"]["envelope_fingerprint"]
    assert seraph["external_action_executed"] is False
    assert seraph["execution_authorized"] is False


def test_customer_required_seraph_telemetry_is_case_bound_and_tamper_evident(tmp_path: Path) -> None:
    payload = _fixture("aitrustproof")
    case_id = payload["case_id"]
    event = {
        "event_id": "evt-customer-1", "event_type": "model_access", "timestamp": NOW,
        "data": {"case_id": case_id, "result": "denied"}, "prev_hash": EVENT_GENESIS,
    }
    event["event_hash"] = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    audit = {
        "record_id": "aud-customer-1", "timestamp": NOW, "principal": "operator:customer",
        "action": "review", "targets": ["ai-system"], "prev_hash": AUDIT_GENESIS,
        "case_id": case_id, "result": "denied",
    }
    audit_basis = {key: audit[key] for key in ("record_id", "timestamp", "principal", "action", "targets", "prev_hash")}
    audit["record_hash"] = hashlib.sha256(json.dumps(audit_basis, sort_keys=True).encode()).hexdigest()
    payload["seraph_telemetry"] = {
        "required": True, "event_chain": [event], "audit_chain": [audit],
        "event_head": event["event_hash"], "audit_head": audit["record_hash"],
    }
    valid = run_ai_trust("dio_aitrustproof", payload, output_dir=tmp_path / "valid",
                         operator_id="human.telemetry_test", now=NOW)["seraph_challenge"]
    assert valid["evidence_context"]["seraph_telemetry"]["state"] == "HASH_CHAIN_VERIFIED"
    assert valid["evidence_context"]["seraph_telemetry"]["signature_state"] == "UNVERIFIED"
    assert "audit.result" in valid["evidence_context"]["seraph_telemetry"]["unhashed_fields"]
    assert valid["coverage_state"] == "partial"

    tampered = copy.deepcopy(payload)
    tampered["seraph_telemetry"]["event_chain"][0]["data"]["result"] = "allowed"
    contested = run_ai_trust("dio_aitrustproof", tampered, output_dir=tmp_path / "tampered",
                             operator_id="human.telemetry_test", now=NOW)["seraph_challenge"]
    assert contested["evidence_context"]["seraph_telemetry"]["state"] == "INVALID_CHAIN"
    assert contested["verdict"] == "CONTESTED"

    missing = copy.deepcopy(payload)
    missing["seraph_telemetry"]["event_chain"] = []
    missing["seraph_telemetry"]["audit_chain"] = []
    missing["seraph_telemetry"]["event_head"] = EVENT_GENESIS
    missing["seraph_telemetry"]["audit_head"] = AUDIT_GENESIS
    missing_result = run_ai_trust("dio_aitrustproof", missing, output_dir=tmp_path / "missing",
                                  operator_id="human.telemetry_test", now=NOW)["seraph_challenge"]
    assert missing_result["evidence_context"]["seraph_telemetry"]["state"] == "MISSING"
    assert missing_result["verdict"] == "CONTESTED"


def test_cross_incarnation_source_type_and_missing_operator_refuse(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source_type=ai_agent"):
        run_ai_trust("dio_agentauthority", _fixture("aitrustproof"), output_dir=tmp_path / "wrong",
                     operator_id="human.test", now=NOW)
    with pytest.raises(ValueError, match="operator_id"):
        run_ai_trust("dio_aitrustproof", _fixture("aitrustproof"), output_dir=tmp_path / "no-human",
                     operator_id="", now=NOW)


def test_phase13_adversarial_gauntlet(tmp_path: Path) -> None:
    receipt = run_gauntlet(output_dir=tmp_path / "phase13")
    assert receipt["acceptance_token"] == ACCEPTANCE_TOKEN
    assert receipt["incarnation_count"] == 3
    assert receipt["phase12_regression"] == "PASS"
    assert receipt["deterministic_execution"] == "PASS"
    assert receipt["prompt_injection_boundary"] == "PASS"
    assert receipt["model_drift_detection"] == "PASS"
    assert receipt["stale_evaluation_detection"] == "PASS"
    assert receipt["artifact_integrity"] == "PASS"
    assert receipt["external_release"] == "REFUSE"
