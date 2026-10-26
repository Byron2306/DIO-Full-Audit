import json
from pathlib import Path

from products.studio_launch_artifact_upgrade import close_studio_case
from products.studio_native_closure import verify_native_closure_proof


def test_article_customer_artifact_is_sophia_governed(tmp_path: Path):
    result = close_studio_case(
        manifest_path=Path("config/studio_harvest/article_publication_studio.json"),
        output_dir=tmp_path / "article",
    )
    verify_native_closure_proof(Path(result["output_dir"]), result["proof_manifest"])
    assert result["receipt"]["customer_artifact_gate"] == "PASS"
    target = Path(result["output_dir"]) / result["receipt"]["customer_artifact_entrypoint"]
    text = target.read_text(encoding="utf-8")
    assert "SOPHIA-GOVERNED REVIEW" in text
    assert "Claims Sophia refuses to promote" in text
    assert "controlled fixture records" in text
    governance = json.loads((Path(result["output_dir"]) / "closure/customer/SOPHIA_PUBLICATION_GOVERNANCE.json").read_text(encoding="utf-8"))
    assert governance["source_reference_audit"] == "PASS"
    assert governance["claim_lineage_audit"] == "PASS"
    assert governance["proof_input_truth"] == "CONTROLLED_FIXTURE_NOT_EXTERNAL_SOURCE_VERIFICATION"
    assert governance["publication"] == "REFUSE"


def test_correspondence_customer_artifact_is_document_studio_rendered(tmp_path: Path):
    result = close_studio_case(
        manifest_path=Path("config/studio_harvest/professional_correspondence_studio.json"),
        output_dir=tmp_path / "correspondence",
    )
    verify_native_closure_proof(Path(result["output_dir"]), result["proof_manifest"])
    assert result["receipt"]["customer_artifact_gate"] == "PASS"
    target = Path(result["output_dir"]) / result["receipt"]["customer_artifact_entrypoint"]
    assert target.is_file()
    route = json.loads((Path(result["output_dir"]) / "closure/customer/DOCUMENT_STUDIO_CORRESPONDENCE_ROUTE.json").read_text(encoding="utf-8"))
    assert route["technical_formatting"]["state"] == "EXECUTED"
    assert route["translation"]["state"] == "AVAILABLE_ON_AUTHORISED_REQUEST_NOT_EXECUTED_IN_THIS_ENGLISH_FIXTURE"
    assert route["outlook"]["external_send"] == "REFUSE"
    receipt = json.loads((Path(result["output_dir"]) / "closure/customer/DOCUMENT_STUDIO_CORRESPONDENCE_PRODUCT_RECEIPT.json").read_text(encoding="utf-8"))
    assert receipt["document_studio_formatting_executed"] is True
    assert receipt["translation_executed_in_this_fixture"] is False
    assert receipt["translation_route_available"] is True
