from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.sufficiency import assess_sufficiency
from products.compiler import compile_manifest, load_capability_catalog
from products.contractproof.proof import REQUIRED_ARTIFACT_TYPES, verify_integrity
from products.contractproof.runner import EXECUTOR_ID, run_contractproof
from products.governed_case import new_case
from products.work_pattern_runtime import plan_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "products" / "manifests" / "contractproof.json"
GOLDEN_ROOT = ROOT / "config" / "products" / "golden" / "contractproof"
NOW = "2026-08-12T12:00:00+00:00"


def _load(name: str):
    return json.loads((GOLDEN_ROOT / name).read_text(encoding="utf-8"))


def _run(tmp_path: Path):
    source = _load("reference_contract.json")
    evidence = _load("reference_evidence.json")["evidence_records"]
    return run_contractproof(source, evidence, output_dir=tmp_path / "contractproof", operator_id="human.phase5_test_operator", now=NOW, job_id="phase5-test")


def test_compiler_resolves_complete_contractproof_composition_but_keeps_human_and_release_gates() -> None:
    compiled = compile_manifest(ROOT, MANIFEST)
    assert compiled["maturity"]["state"] == "internal_proof"
    assert compiled["maturity"]["operational_flags"]["routable"] is True
    assert compiled["maturity"]["operational_flags"]["governable"] is True
    assert compiled["maturity"]["operational_flags"]["executable"] is True
    assert compiled["maturity"]["operational_flags"]["campaign_enabled"] is False
    assert all(row["resolution_state"] == "RESOLVED" for row in compiled["capability_plan"] if row["required"])
    assert compiled["gates"]["planning"]["state"] == "ALLOW"
    assert compiled["gates"]["execution"]["state"] == "NEEDS_YOU"
    assert compiled["gates"]["human_review"]["state"] == "NEEDS_YOU"
    assert compiled["gates"]["external_release"]["state"] == "REFUSE"


def test_all_contractproof_work_patterns_are_ready_while_runtime_itself_remains_nonexecuting() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    states = {row["work_pattern_id"]: row["runtime_state"] for row in plan["patterns"]}
    assert states == {"WP01": "READY", "WP05": "READY", "WP11": "READY"}
    assert plan["planning_gate"]["state"] == "ALLOW"
    assert plan["execution_gate"]["state"] == "REFUSE"
    assert plan["compiler_execution_gate"]["state"] == "NEEDS_YOU"
    assert plan["authority_created"] is False
    assert plan["executor_created"] is False
    assert all(row["human_gate"]["state"] == "NEEDS_YOU" for row in plan["patterns"])


def test_contractproof_proof_provider_is_product_scoped_without_broadening_capitalroom() -> None:
    catalog, _ = load_capability_catalog(ROOT)
    room = catalog["proof.room.compile"]
    capitalroom = next(row for row in room["providers"] if row["provider_id"] == "capitalroom_proof_room")
    contractproof = next(row for row in room["providers"] if row["provider_id"] == "contractproof_proof_pack_v1")
    assert "dio_contractproof" not in capitalroom["product_scope"]
    assert contractproof["product_scope"] == ["dio_contractproof"]
    compiled = compile_manifest(ROOT, MANIFEST)
    selected = {row["capability_id"]: row for row in compiled["capability_plan"]}["proof.room.compile"]["provider"]
    assert selected["provider_id"] == "contractproof_proof_pack_v1"


def test_evidence_sufficiency_is_review_readiness_not_authority() -> None:
    case = new_case(product="dio_contractproof", job_id="phase5-sufficiency", source={"source": {}}, source_path=MANIFEST, evidence_inputs=[], expected_outputs=[], required_authorities=["contract_owner"], intake_state="approved", now=NOW)
    result = assess_sufficiency(case)
    assert result["state"] == "READY_FOR_HUMAN_REVIEW"
    assert result["human_gate"]["state"] == "NEEDS_YOU"
    assert result["authority_created"] is False
    assert result["fulfilment_adjudicated"] is False
    assert result["external_release"] is False


def test_golden_runner_completes_internal_processing_and_preserves_mixed_contract_truth(tmp_path: Path) -> None:
    result = _run(tmp_path)
    receipt = result["receipt"]
    counts = receipt["obligation_status_counts"]
    assert receipt["executor_id"] == EXECUTOR_ID
    assert receipt["internal_processing"] == "COMPLETE"
    assert counts == {"SATISFIED": 1, "MISSING": 1, "PARTIAL": 1, "EXPIRED": 1, "NOT_YET_DUE": 1, "NEEDS_REVIEW": 1}
    assert receipt["evidence_sufficiency_state"] == "GAPS_PRESENT"
    assert receipt["proof_integrity_verified"] is True
    assert receipt["external_effects"] is False


def test_golden_pack_matches_exact_profile_artifact_types_and_required_sections(tmp_path: Path) -> None:
    result = _run(tmp_path)
    output_dir = Path(result["output_dir"])
    manifest = result["proof_manifest"]
    observed_types = {row["artifact_type"] for row in manifest["artifacts"]} | {manifest["artifact_type"]}
    assert observed_types == set(REQUIRED_ARTIFACT_TYPES)
    assert set(result["receipt"]["required_artifact_types"]) == set(REQUIRED_ARTIFACT_TYPES)
    compiled = compile_manifest(ROOT, MANIFEST)
    required_sections = {item for output in compiled["output_plan"]["outputs"] for item in output["required_sections"]}
    assert set(manifest["required_sections"]) == required_sections
    evidence_pack = json.loads((output_dir / "EVIDENCE_PACK.json").read_text(encoding="utf-8"))
    assert required_sections.issubset(evidence_pack.keys())
    assert (output_dir / "EVIDENCE_PACK.docx").is_file()
    assert (output_dir / "EVIDENCE_PACK.pdf").is_file()
    assert (output_dir / "EVIDENCE_PACK.html").is_file()
    assert (output_dir / "PROOF_MANIFEST.json").is_file()
    assert verify_integrity(output_dir)["verified"] is True


def test_tampered_proof_artifact_is_detected(tmp_path: Path) -> None:
    result = _run(tmp_path)
    output_dir = Path(result["output_dir"])
    path = output_dir / "EVIDENCE_PACK.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tampered"] = True
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verification = verify_integrity(output_dir)
    assert verification["verified"] is False
    assert "hash:JSON" in verification["failures"]


def test_tampered_proof_manifest_authority_boundary_is_detected(tmp_path: Path) -> None:
    result = _run(tmp_path)
    output_dir = Path(result["output_dir"])
    path = output_dir / "PROOF_MANIFEST.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["external_release"] = True
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verification = verify_integrity(output_dir)
    assert verification["verified"] is False
    assert "manifest:authority_boundary" in verification["failures"]
    assert "manifest:fingerprint" in verification["failures"]


def test_golden_runner_requires_explicit_human_operator(tmp_path: Path) -> None:
    source = _load("reference_contract.json")
    evidence = _load("reference_evidence.json")["evidence_records"]
    with pytest.raises(ValueError, match="operator_id"):
        run_contractproof(source, evidence, output_dir=tmp_path, operator_id="", now=NOW)


def test_contractproof_executor_is_bounded_and_product_scoped() -> None:
    catalog, _ = load_capability_catalog(ROOT)
    row = catalog["product.executor.contractproof"]
    assert row["status"] == "available"
    assert len(row["providers"]) == 1
    provider = row["providers"][0]
    assert provider["provider_id"] == EXECUTOR_ID
    assert provider["product_scope"] == ["dio_contractproof"]
    assert provider["execution_capable"] is True
    assert provider["ref"] == "products/contractproof/runner.py"


def test_internal_proof_never_becomes_external_release_or_fulfilment_authority(tmp_path: Path) -> None:
    result = _run(tmp_path)
    receipt = result["receipt"]
    disclosure = result["disclosure"]
    assert receipt["human_fulfilment_gate"] == "NEEDS_YOU"
    assert receipt["human_disclosure_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["waiver_created"] is False
    assert receipt["legal_opinion_created"] is False
    assert receipt["external_release"] is False
    assert disclosure["external_release_gate"] == "REFUSE"
    assert disclosure["release_authority_created"] is False
