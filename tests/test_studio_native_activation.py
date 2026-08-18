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
    assert receipt["studio_count"] == 2
    assert receipt["new_engine_created"] is False
    assert receipt["external_effects"] is False
    for studio in receipt["studios"].values():
        assert studio["native_multi_organ_execution"] == "PASS"
        assert studio["deterministic_native_execution"] == "PASS"
        assert studio["native_tamper_detection"] == "PASS"
        assert studio["truthful_capability_accounting"] == "PASS"
        assert studio["authority_boundary"] == "PASS"
