from pathlib import Path

from products.studio_native_closure import close_studio_case, verify_native_closure_proof
from products.studio_native_closure_gauntlet import run_gauntlet


def _engines(result):
    return {row["engine_id"]: row for row in result["ledger"]["organs"]}


def test_site_studio_closes_every_declared_native_capability(tmp_path: Path):
    result = close_studio_case(
        manifest_path=Path("config/studio_harvest/site_studio.json"),
        output_dir=tmp_path / "site",
    )
    verify_native_closure_proof(Path(result["output_dir"]), result["proof_manifest"])
    assert result["receipt"]["organ_execution_truth"] == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED"
    assert result["receipt"]["all_declared_capabilities_executed"] is True
    assert result["receipt"]["partial_organ_count"] == 0
    assert result["receipt"]["source_bound_only_count"] == 0
    engines = _engines(result)
    assert all(row["execution_state"] == "NATIVE_EXECUTED" for row in engines.values())
    assert all(not row["missing_capabilities"] for row in engines.values())
    assert "presence.release.prepare" in engines["vesper"]["executed_capabilities"]
    assert "market.position" in engines["nichefoundry"]["executed_capabilities"]
    assert "document.sales_assets" in engines["document_studio"]["executed_capabilities"]
    assert "evidence.campaign.proof" in engines["evidex"]["executed_capabilities"]
    assert "commercial.measurement.contract" in engines["commercial_truth"]["executed_capabilities"]


def test_correspondence_studio_closes_vesper_and_evidex(tmp_path: Path):
    result = close_studio_case(
        manifest_path=Path("config/studio_harvest/professional_correspondence_studio.json"),
        output_dir=tmp_path / "correspondence",
    )
    engines = _engines(result)
    assert result["receipt"]["organ_execution_truth"] == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED"
    assert all(row["execution_state"] == "NATIVE_EXECUTED" for row in engines.values())
    assert "presence.release.prepare" in engines["vesper"]["executed_capabilities"]
    assert engines["evidex"]["executed_capabilities"] == ["evidence.intake.structure"]
    assert result["receipt"]["external_send"] == "REFUSE"
    assert result["receipt"]["human_gate"] == "NEEDS_YOU"


def test_native_closure_is_deterministic(tmp_path: Path):
    a = close_studio_case(
        manifest_path=Path("config/studio_harvest/site_studio.json"),
        output_dir=tmp_path / "a",
    )
    b = close_studio_case(
        manifest_path=Path("config/studio_harvest/site_studio.json"),
        output_dir=tmp_path / "b",
    )
    assert a["receipt"]["native_closure_fingerprint"] == b["receipt"]["native_closure_fingerprint"]
    assert a["proof_manifest"]["proof_fingerprint"] == b["proof_manifest"]["proof_fingerprint"]
    assert [(row["path"], row["sha256"]) for row in a["proof_manifest"]["artifacts"]] == [
        (row["path"], row["sha256"]) for row in b["proof_manifest"]["artifacts"]
    ]


def test_native_closure_gauntlet(tmp_path: Path):
    receipt = run_gauntlet(output_dir=tmp_path / "gauntlet")
    assert receipt["acceptance_token"] == "DIO_STUDIO_NATIVE_CLOSURE_READY"
    assert receipt["studio_count"] == 2
    assert receipt["unqualified_native_multi_organ_execution"] == "PASS"
    assert receipt["new_engine_created"] is False
    assert receipt["external_effects"] is False
    for studio in receipt["studios"].values():
        assert studio["native_capability_closure"] == "PASS"
        assert studio["deterministic_native_closure"] == "PASS"
        assert studio["native_closure_tamper_detection"] == "PASS"
        assert studio["truthful_capability_accounting"] == "PASS"
        assert studio["organ_execution_truth"] == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED"
        assert studio["partial_organ_count"] == 0
        assert studio["source_bound_only_count"] == 0
        assert studio["all_declared_capabilities_executed"] is True
