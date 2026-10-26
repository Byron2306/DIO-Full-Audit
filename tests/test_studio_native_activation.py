from pathlib import Path

from products.studio_native_activation import activate_studio_case, verify_native_execution_proof
from products.studio_native_activation_gauntlet import run_gauntlet


def _engines(result):
    return {row["engine_id"]: row for row in result["ledger"]["organs"]}


def test_site_studio_executes_multiple_native_organs_without_claim_inflation(tmp_path: Path):
    result = activate_studio_case(
        manifest_path=Path("config/studio_harvest/site_studio.json"),
        output_dir=tmp_path / "site",
    )
    verify_native_execution_proof(Path(result["output_dir"]), result["proof_manifest"])
    assert result["receipt"]["native_multi_organ_execution"] == "PASS"
    assert result["receipt"]["organ_execution_truth"] == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED_WITH_AUXILIARY_GAPS"
    engines = _engines(result)
    assert engines["lingua"]["execution_state"] == "NATIVE_EXECUTED"
    assert engines["market_command"]["execution_state"] == "NATIVE_EXECUTED"
    assert engines["vesper"]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert engines["nichefoundry"]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert engines["document_studio"]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert engines["evidex"]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert engines["commercial_truth"]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert "presence.release.prepare" in engines["vesper"]["missing_capabilities"]
    assert "document.sales_assets" in engines["document_studio"]["missing_capabilities"]
    assert "market.position" in engines["nichefoundry"]["missing_capabilities"]
    assert "evidence.campaign.proof" in engines["evidex"]["missing_capabilities"]
    assert "commercial.measurement.contract" in engines["commercial_truth"]["missing_capabilities"]
    assert result["receipt"]["external_publication"] == "REFUSE"
    assert result["receipt"]["external_send"] == "REFUSE"
    assert result["receipt"]["payment"] == "REFUSE"


def test_correspondence_studio_executes_lingua_format_outlook_and_commercial_truth(tmp_path: Path):
    result = activate_studio_case(
        manifest_path=Path("config/studio_harvest/professional_correspondence_studio.json"),
        output_dir=tmp_path / "correspondence",
    )
    verify_native_execution_proof(Path(result["output_dir"]), result["proof_manifest"])
    engines = _engines(result)
    assert engines["lingua"]["execution_state"] == "NATIVE_EXECUTED"
    assert engines["document_studio"]["execution_state"] == "NATIVE_EXECUTED"
    assert engines["outlook_mail_core"]["execution_state"] == "NATIVE_EXECUTED"
    assert engines["commercial_truth"]["execution_state"] == "NATIVE_EXECUTED"
    assert engines["vesper"]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert engines["evidex"]["execution_state"] == "SOURCE_BOUND_ONLY"
    outlook = Path(result["output_dir"]) / "native" / "outlook_mail_core" / "OUTLOOK_NATIVE_DRAFT_RECEIPT.json"
    payload = __import__("json").loads(outlook.read_text(encoding="utf-8"))
    assert payload["send_state"] == "draft"
    assert payload["approval"] == {"required": True, "state": "pending"}
    assert payload["external_send_executed"] is False


def test_finance_readiness_executes_nichefoundry_sophia_vamp_and_lingua(tmp_path: Path):
    result = activate_studio_case(
        manifest_path=Path("config/studio_harvest/finance_readiness_studio.json"),
        output_dir=tmp_path / "finance",
    )
    verify_native_execution_proof(Path(result["output_dir"]), result["proof_manifest"])
    engines = _engines(result)
    assert result["receipt"]["organ_execution_truth"] == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED_WITH_AUXILIARY_GAPS"
    assert result["receipt"]["native_organ_count"] == 4
    assert result["receipt"]["partial_organ_count"] == 4
    assert result["receipt"]["source_bound_only_count"] == 0
    for engine_id in ("lingua", "nichefoundry", "sophia", "vamp"):
        assert engines[engine_id]["execution_state"] == "NATIVE_EXECUTED"
    for engine_id in ("vesper", "document_studio", "evidex", "commercial_truth"):
        assert engines[engine_id]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert "evidence.readiness.gap_map" in engines["evidex"]["missing_capabilities"]
    assert "document.finance_readiness_pack" in engines["document_studio"]["missing_capabilities"]
    assert "commercial.measurement.contract" in engines["commercial_truth"]["missing_capabilities"]
    assert "presence.release.prepare" in engines["vesper"]["missing_capabilities"]
    sophia_path = Path(result["output_dir"]) / "native" / "sophia" / "SOPHIA_FINANCE_AUDIT.json"
    sophia = __import__("json").loads(sophia_path.read_text(encoding="utf-8"))
    assert sophia["lender_decision"] == "NOT_MADE"
    assert all(row["epistemic_state"] == "ASSUMPTION_NOT_ESTABLISHED_FACT" for row in sophia["assumptions"])


def test_article_publication_executes_source_lineage_and_creative_organs(tmp_path: Path):
    result = activate_studio_case(
        manifest_path=Path("config/studio_harvest/article_publication_studio.json"),
        output_dir=tmp_path / "article",
    )
    verify_native_execution_proof(Path(result["output_dir"]), result["proof_manifest"])
    engines = _engines(result)
    assert result["receipt"]["organ_execution_truth"] == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED_WITH_AUXILIARY_GAPS"
    assert result["receipt"]["native_organ_count"] == 3
    assert result["receipt"]["partial_organ_count"] == 4
    assert result["receipt"]["source_bound_only_count"] == 0
    for engine_id in ("lingua", "nichefoundry", "sophia"):
        assert engines[engine_id]["execution_state"] == "NATIVE_EXECUTED"
    for engine_id in ("vesper", "document_studio", "evidex", "commercial_truth"):
        assert engines[engine_id]["execution_state"] == "PARTIAL_NATIVE_EXECUTION"
    assert "evidence.editorial.proof" in engines["evidex"]["missing_capabilities"]
    assert "document.publication_pack" in engines["document_studio"]["missing_capabilities"]
    sophia_path = Path(result["output_dir"]) / "native" / "sophia" / "SOPHIA_ARTICLE_LINEAGE.json"
    sophia = __import__("json").loads(sophia_path.read_text(encoding="utf-8"))
    assert sophia["source_reference_audit"] == "PASS"
    assert sophia["claim_lineage_audit"] == "PASS"
    assert sophia["publication_authority"] == "REFUSE"


def test_native_execution_is_deterministic(tmp_path: Path):
    a = activate_studio_case(
        manifest_path=Path("config/studio_harvest/site_studio.json"),
        output_dir=tmp_path / "a",
    )
    b = activate_studio_case(
        manifest_path=Path("config/studio_harvest/site_studio.json"),
        output_dir=tmp_path / "b",
    )
    assert a["receipt"]["native_execution_fingerprint"] == b["receipt"]["native_execution_fingerprint"]
    assert a["proof_manifest"]["proof_fingerprint"] == b["proof_manifest"]["proof_fingerprint"]
    assert [(row["path"], row["sha256"]) for row in a["proof_manifest"]["artifacts"]] == [
        (row["path"], row["sha256"]) for row in b["proof_manifest"]["artifacts"]
    ]


def test_native_activation_gauntlet(tmp_path: Path):
    receipt = run_gauntlet(output_dir=tmp_path / "gauntlet")
    assert receipt["acceptance_token"] == "DIO_STUDIO_NATIVE_EXECUTION_READY"
    assert receipt["composition_regression"] == "PASS"
    assert receipt["studio_count"] == 4
    assert receipt["new_engine_created"] is False
    assert receipt["external_effects"] is False
    for studio in receipt["studios"].values():
        assert studio["native_multi_organ_execution"] == "PASS"
        assert studio["deterministic_native_execution"] == "PASS"
        assert studio["native_tamper_detection"] == "PASS"
        assert studio["truthful_capability_accounting"] == "PASS"
        assert studio["authority_boundary"] == "PASS"
        assert studio["organ_execution_truth"] == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED_WITH_AUXILIARY_GAPS"
