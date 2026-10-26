from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.studio_harvest import ROOT, StudioHarvestError, build_studio_case, validate_studio_manifest, verify_studio_proof
from products.studio_harvest_gauntlet import run_gauntlet

SITE = Path("config/studio_harvest/site_studio.json")
CORR = Path("config/studio_harvest/professional_correspondence_studio.json")
FINANCE = Path("config/studio_harvest/finance_readiness_studio.json")
ARTICLE = Path("config/studio_harvest/article_publication_studio.json")


def test_studio_harvest_gauntlet(tmp_path: Path) -> None:
    result = run_gauntlet(output_dir=tmp_path / "harvest")
    assert result["acceptance_token"] == "DIO_STUDIO_HARVEST_READY"
    assert result["studio_count"] == 4
    assert result["unsafe_promotion_refusal"] == "PASS"
    assert result["new_engine_created"] is False
    for row in result["studios"].values():
        assert row["job_resolution"] == "PASS"
        assert row["vesper_routing"] == "PASS"
        assert row["controlled_artifact_generation"] == "PASS"
        assert row["deterministic_generation"] == "PASS"
        assert row["tamper_detection"] == "PASS"
        assert row["external_send"] == "REFUSE"
        assert row["external_publication"] == "REFUSE"
        assert row["payment"] == "REFUSE"


def test_site_studio_artifact_contract(tmp_path: Path) -> None:
    result = build_studio_case(manifest_path=SITE, output_dir=tmp_path / "site")
    out = Path(result["output_dir"])
    page = (out / "marketfront/index.html").read_text(encoding="utf-8")
    css = (out / "marketfront/styles.css").read_text(encoding="utf-8")
    js = (out / "marketfront/app.js").read_text(encoding="utf-8")
    assert "research consultancy" in result["manifest"]["job"]["request"].lower()
    assert "CONTROLLED COMPOSITION PROOF" in page
    assert "@media" in css and "grid-template-columns" in css
    assert "fetch(" not in js and "XMLHttpRequest" not in js
    assert "external_send:'REFUSE'" in js
    assert result["route"]["product"] == "site_studio"
    assert result["route"]["intent"] == "intake_request"
    verify_studio_proof(out, result["proof_manifest"])


def test_correspondence_studio_preserves_send_and_commitment_boundary(tmp_path: Path) -> None:
    result = build_studio_case(manifest_path=CORR, output_dir=tmp_path / "corr")
    out = Path(result["output_dir"])
    draft = (out / "correspondence/DRAFT_EMAIL.txt").read_text(encoding="utf-8")
    boundary = json.loads((out / "correspondence/COMMITMENT_BOUNDARY.json").read_text(encoding="utf-8"))
    outlook = json.loads((out / "operations/OUTLOOK_DRAFT.json").read_text(encoding="utf-8"))
    assert "does not amend the invoice" in draft
    assert boundary["admission_authority"] == "REFUSE"
    assert boundary["settlement_authority"] == "REFUSE"
    assert boundary["send_authority"] == "REFUSE"
    assert outlook["state"] == "DRAFT_ONLY"
    assert outlook["external_send"] == "REFUSE"
    assert result["route"]["product"] == "professional_correspondence_studio"
    verify_studio_proof(out, result["proof_manifest"])


def test_finance_readiness_studio_exposes_gaps_without_lender_decision(tmp_path: Path) -> None:
    result = build_studio_case(manifest_path=FINANCE, output_dir=tmp_path / "finance")
    out = Path(result["output_dir"])
    readiness = json.loads((out / "finance/FINANCE_READINESS_OBJECT.json").read_text(encoding="utf-8"))
    boundary = json.loads((out / "finance/FINANCIAL_AUTHORITY_BOUNDARY.json").read_text(encoding="utf-8"))
    report = (out / "finance/READINESS_REPORT.html").read_text(encoding="utf-8")
    presence = json.loads((out / "operations/PRESENCE_RELEASE.json").read_text(encoding="utf-8"))
    assert readiness["evidence_needed_count"] == 2
    states = {row["requirement_id"]: row["state"] for row in readiness["requirement_gap_map"]}
    assert states["FR-03"] == "EVIDENCE_NEEDED"
    assert states["FR-05"] == "EVIDENCE_NEEDED"
    assert readiness["lender_decision"] == "NOT_MADE"
    assert readiness["financial_advice"] == "NOT_PROVIDED"
    assert boundary["lending_decision"] == "REFUSE"
    assert boundary["credit_decision"] == "REFUSE"
    assert "No lender approval" in report
    assert presence["entrypoint"] == "finance/READINESS_REPORT.html"
    assert presence["publication"] == "REFUSE"
    assert result["route"]["product"] == "finance_readiness_studio"
    verify_studio_proof(out, result["proof_manifest"])


def test_article_publication_studio_preserves_source_and_publication_boundaries(tmp_path: Path) -> None:
    result = build_studio_case(manifest_path=ARTICLE, output_dir=tmp_path / "article")
    out = Path(result["output_dir"])
    lineage = json.loads((out / "publication/ARTICLE_LINEAGE_OBJECT.json").read_text(encoding="utf-8"))
    boundary = json.loads((out / "publication/PUBLICATION_BOUNDARY.json").read_text(encoding="utf-8"))
    draft = (out / "publication/ARTICLE_DRAFT.html").read_text(encoding="utf-8")
    source_map = (out / "publication/CLAIM_SOURCE_MAP.txt").read_text(encoding="utf-8")
    presence = json.loads((out / "operations/PRESENCE_RELEASE.json").read_text(encoding="utf-8"))
    assert lineage["supported_claim_count"] == 3
    assert lineage["refused_claim_count"] == 1
    assert "CL-04 | REFUSE | NO_EVIDENCE" in source_map
    assert "Mokoena" in draft and "Naidoo" in draft
    assert boundary["fabricated_sources"] == "REFUSE"
    assert boundary["fabricated_quotations"] == "REFUSE"
    assert boundary["automatic_publication"] == "REFUSE"
    assert presence["entrypoint"] == "publication/ARTICLE_DRAFT.html"
    assert presence["publication"] == "REFUSE"
    assert result["route"]["product"] == "article_publication_studio"
    verify_studio_proof(out, result["proof_manifest"])


def test_missing_organ_refuses(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / SITE).read_text(encoding="utf-8"))
    manifest["required_organs"][0]["source_ref"] = "missing/organ.py"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(StudioHarvestError, match="required organ source missing"):
        build_studio_case(manifest_path=path, output_dir=tmp_path / "bad-out")


def test_unsafe_authority_refuses() -> None:
    manifest = json.loads((ROOT / CORR).read_text(encoding="utf-8"))
    bad = copy.deepcopy(manifest)
    bad["authority"]["external_send"] = "ALLOW"
    with pytest.raises(StudioHarvestError, match="unsafe Studio Harvest authority"):
        validate_studio_manifest(bad)
