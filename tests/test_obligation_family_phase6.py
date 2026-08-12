from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from products.compiler import compile_manifest, load_capability_catalog
from products.obligationfamily.runner import EXECUTOR_ID, FAMILY_DEFINITIONS, REQUIRED_ARTIFACT_TYPES, run_family_proof
from products.work_pattern_runtime import plan_manifest


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-12T12:00:00+00:00"


def _manifest(slug: str) -> Path:
    return ROOT / "config" / "products" / "manifests" / f"{slug}.json"


def _run(product_id: str, tmp_path: Path):
    definition = FAMILY_DEFINITIONS[product_id]
    fixture = ROOT / "config" / "products" / "golden" / definition["slug"]
    source = json.loads((fixture / "reference_source.json").read_text(encoding="utf-8"))
    evidence = json.loads((fixture / "reference_evidence.json").read_text(encoding="utf-8"))["evidence_records"]
    return run_family_proof(product_id, source, evidence, output_dir=tmp_path / definition["slug"], operator_id="human.phase6_test_operator", now=NOW)


@pytest.mark.parametrize("product_id", sorted(FAMILY_DEFINITIONS))
def test_family_manifests_compile_complete_but_preserve_human_and_release_gates(product_id: str) -> None:
    definition = FAMILY_DEFINITIONS[product_id]
    manifest = _manifest(definition["slug"])
    compiled = compile_manifest(ROOT, manifest)
    assert compiled["maturity"]["state"] == "internal_proof"
    assert all(row["resolution_state"] == "RESOLVED" for row in compiled["capability_plan"] if row["required"])
    assert compiled["gates"]["planning"]["state"] == "ALLOW"
    assert compiled["gates"]["execution"]["state"] == "NEEDS_YOU"
    assert compiled["gates"]["human_review"]["state"] == "NEEDS_YOU"
    assert compiled["gates"]["external_release"]["state"] == "REFUSE"
    plan = plan_manifest(ROOT, manifest)
    assert {row["work_pattern_id"]: row["runtime_state"] for row in plan["patterns"]} == {"WP01": "READY", "WP05": "READY", "WP11": "READY"}
    assert plan["execution_gate"]["state"] == "REFUSE"


def test_family_providers_are_bounded_to_exactly_three_products() -> None:
    catalog, _ = load_capability_catalog(ROOT)
    expected = sorted(FAMILY_DEFINITIONS)
    for capability_id in ("proof.room.compile", "proof.integrity.verify", "proof.disclosure.prepare"):
        provider = next(row for row in catalog[capability_id]["providers"] if row["provider_id"] == "obligation_family_proof_pack_v1")
        assert sorted(provider["product_scope"]) == expected
        assert provider["execution_capable"] is False
    for product_id, definition in FAMILY_DEFINITIONS.items():
        provider = catalog[f"product.executor.{definition['slug']}"]["providers"][0]
        assert provider["provider_id"] == EXECUTOR_ID
        assert provider["product_scope"] == [product_id]
        assert provider["execution_capable"] is True


@pytest.mark.parametrize("product_id", sorted(FAMILY_DEFINITIONS))
def test_each_family_golden_case_runs_and_preserves_inconvenient_truth(product_id: str, tmp_path: Path) -> None:
    result = _run(product_id, tmp_path)
    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["obligation_status_counts"] == {"SATISFIED": 1, "MISSING": 1, "EXPIRED": 1}
    assert receipt["evidence_sufficiency_state"] == "GAPS_PRESENT"
    assert receipt["human_fulfilment_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["award_or_permit_decision_created"] is False
    output = Path(result["output_dir"])
    manifest = result["proof_manifest"]
    observed = {row["artifact_type"] for row in manifest["artifacts"]} | {manifest["artifact_type"]}
    assert observed == set(REQUIRED_ARTIFACT_TYPES)
    for artifact in manifest["artifacts"]:
        assert hashlib.sha256((output / artifact["filename"]).read_bytes()).hexdigest() == artifact["sha256"]


def test_family_rejects_cross_product_source_type_and_missing_operator(tmp_path: Path) -> None:
    fixture = ROOT / "config" / "products" / "golden" / "tenderproof"
    source = json.loads((fixture / "reference_source.json").read_text(encoding="utf-8"))
    evidence = json.loads((fixture / "reference_evidence.json").read_text(encoding="utf-8"))["evidence_records"]
    with pytest.raises(ValueError, match="source_type=grant"):
        run_family_proof("dio_grantproof", source, evidence, output_dir=tmp_path / "wrong", operator_id="human.test", now=NOW)
    with pytest.raises(ValueError, match="operator_id"):
        run_family_proof("dio_tenderproof", source, evidence, output_dir=tmp_path / "no-human", operator_id="", now=NOW)


def test_phase6_does_not_create_a_second_obligation_core() -> None:
    family_source = (ROOT / "products" / "obligationfamily" / "runner.py").read_text(encoding="utf-8")
    assert "from dio.obligations.engine import build" in family_source
    assert not (ROOT / "products" / "obligationfamily" / "obligations.py").exists()
