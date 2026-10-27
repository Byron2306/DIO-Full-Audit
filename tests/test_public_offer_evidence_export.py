from __future__ import annotations

import json
from pathlib import Path

from scripts.export_public_offer_evidence import export_public_offer_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_exports_stable_public_safe_evidence_for_exactly_68_offers(tmp_path: Path) -> None:
    output = tmp_path / "public-offer-evidence.json"
    receipt = export_public_offer_evidence(ROOT, ROOT, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert receipt["offer_count"] == 68
    assert payload["schema"] == "dio.public_offer_evidence.v1"
    assert len(payload["offers"]) == 68
    assert len({row["product_id"] for row in payload["offers"]}) == 68
    assert payload["offers"] == sorted(payload["offers"], key=lambda row: row["product_name"].casefold())
    assert len(payload["artifact_sha256"]) == 64
    assert payload["artifact_id"].startswith("PUBLIC-OFFER-EVIDENCE-")
    assert payload["source_commit"]
    for offer in payload["offers"]:
        assert offer["buyer_job"]
        assert offer["bounded_outcome"]
        assert offer["primary_deliverable"]
        assert offer["acceptance_criteria"]
        assert offer["route_proof"]["label"] == "Route-family execution proof"
        assert offer["named_product_proof"]["state"] == "UNPROVED"
        assert offer["cta"]["action"] == "BEGIN_GOVERNED_INTAKE"
        assert offer["cta"]["href"].startswith("/vesper-intake.html")


def test_export_has_no_private_paths_or_operational_identifiers(tmp_path: Path) -> None:
    output = tmp_path / "public-offer-evidence.json"
    export_public_offer_evidence(ROOT, ROOT, output)
    rendered = output.read_text(encoding="utf-8")
    assert "/workspace/" not in rendered
    assert '"source_path"' not in rendered
    assert '"repository_commit"' not in rendered
    assert '"customer_id"' not in rendered
