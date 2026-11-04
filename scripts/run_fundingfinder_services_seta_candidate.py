#!/usr/bin/env python3
"""Screen one live Services SETA window against the held synthetic Moya profile."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

URL = "https://serviceseta.org.za/discretionary-grant-funding-window-2026-27-now-open/"
AS_OF = "2026-11-02"
BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
PACKET_PATH = BASE / "FUNDINGFINDER_SERVICESETA_CUSTOMER_PACKET_20261102_V5.json"
OUTPUT = BASE / "FUNDINGFINDER_SERVICESETA_CUSTOMER_ROUTE_20261102_V5"
RECEIPT = BASE / "FUNDINGFINDER_SERVICESETA_CUSTOMER_ROUTE_20261102_V5.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    packet = {
        "title": "Moya SkillLab: Services SETA 2026/27 window review",
        "as_of": AS_OF,
        "fetch_public": True,
        "official_url_allowlist": [URL],
        "owner_authorized": True,
        "synthetic_acceptance_not_customer_evidence": True,
        "applicant": {
            "name": "Moya SkillLab — synthetic applicant context",
            "sources": [{
                "source_id": "DECLARATION",
                "text": "Moya SkillLab is a synthetic proposed enterprise in Limpopo, South Africa. The entity type is SMME. The request type is workshop equipment. The proprietor's age, citizenship and youth ownership evidence were not supplied.",
            }],
            "facts": [
                {"field": "country", "value": "South Africa", "source_id": "DECLARATION", "quote": "Moya SkillLab is a synthetic proposed enterprise in Limpopo, South Africa."},
                {"field": "entity_type", "value": "SMME", "source_id": "DECLARATION", "quote": "The entity type is SMME."},
                {"field": "request_type", "value": "workshop equipment", "source_id": "DECLARATION", "quote": "The request type is workshop equipment."},
            ],
        },
        "opportunities": [{
            "opportunity_id": "SERVICES-SETA-DG-2026-27-03",
            "title": "Services SETA Discretionary Grant Funding Window 2026/27 (2026/27-DG-03)",
            "funder": "Services SETA",
            "official_url": URL,
            "deadline": {"date": "2026-11-06", "quote": "Closing deadline: 6 November 2026"},
            "criteria": [
                {"criterion_id": "APPLICANT-ROLE", "field": "applicant_role", "operator": "equals", "expected": "eligible employers, sectoral associations, professional bodies, trade unions or federations, or accredited Skills Development Providers within scope", "quote": "eligible employers, sectoral associations, professional bodies, trade unions and federations, and accredited Skills Development Providers within its scope"},
                {"criterion_id": "LEARNING-PROGRAMME", "field": "proposed_learning_programme", "operator": "equals", "expected": "eligible learning programme for scarce or critical skills and workplace-based learning", "quote": "The window supports learning programmes that build scarce and critical skills and enable workplace-based learning. Available grant types include learnerships, apprenticeships, Recognition of Prior Learning, Adult Education and Training, skills programmes and candidacy. Eligibility differs by learning programme."},
                {"criterion_id": "SPOIL-OR-HARD-TO-FILL", "field": "priority_occupation_or_intervention", "operator": "equals", "expected": "a Sector Priority Occupation and Intervention or hard-to-fill vacancy specified in Annexure A", "quote": "Applications must align with the Sector Priority Occupations and Interventions List and hard-to-fill vacancies specified in Annexure A."},
                {"criterion_id": "PROGRAMME-CAP", "field": "number_of_learning_programmes", "operator": "maximum", "expected": 2, "quote": "Applicants may apply for a maximum of two learning programmes."},
                {"criterion_id": "ONLINE-SUBMISSION", "field": "submission_channel", "operator": "equals", "expected": "online", "quote": "Applications must be submitted online."},
            ],
            "required_documents": [
                {"name": "full advert, Annexure A, the Discretionary Grant Policy and applicable unit costs", "quote": "Before applying, read the full advert, Annexure A, the Discretionary Grant Policy and applicable unit costs for detailed eligibility requirements, grant priorities and supporting documents. Consult the evaluation criteria when preparing your application."},
                {"name": "evaluation criteria", "quote": "Before applying, read the full advert, Annexure A, the Discretionary Grant Policy and applicable unit costs for detailed eligibility requirements, grant priorities and supporting documents. Consult the evaluation criteria when preparing your application."},
                {"name": "required declarations", "quote": "Applicants must complete and sign the required declarations and upload all compulsory supporting documents, which must be valid at submission. Incomplete applications will be disqualified."},
                {"name": "application link and submission instructions", "quote": "The application link and submission instructions will be published on this page shortly."},
            ],
        }],
    }
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUTPUT}")
    PACKET_PATH.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    from products.customer_product_router import run_customer_product

    result = run_customer_product("FundingFinder", packet, OUTPUT, render_pdf=True)
    receipt = result.get("receipt") or {}
    if (result.get("requested_product") != "FundingFinder"
            or result.get("human_review_required") is not True
            or result.get("release_authorized") is not False
            or result.get("external_effects") is not False
            or result.get("commercial_validation") != "UNPROVED"):
        raise ValueError("FundingFinder route crossed its human-review, external-effects or qualification boundary")
    if (receipt.get("as_of") != AS_OF
            or receipt.get("processing", {}).get("public_fetch_enabled") is not True
            or receipt.get("release", {}).get("eligibility_certified") is not False
            or receipt.get("release", {}).get("award_guaranteed") is not False
            or receipt.get("release", {}).get("application_submitted") is not False
            or receipt.get("release", {}).get("externally_sent") is not False):
        raise ValueError("FundingFinder route did not preserve live-source review-only contract")
    rows = receipt.get("shortlist") or []
    if len(rows) != 1:
        raise ValueError("Expected one Services SETA opportunity in this bounded customer review")
    row = rows[0]
    if row.get("opportunity_id") != "SERVICES-SETA-DG-2026-27-03" or row.get("fit_state") != "unknown_review_required" or row.get("timing_state") != "within_stated_deadline":
        raise ValueError("Services SETA source did not produce the expected unresolved-fit/current-window states")
    source = next((item for item in receipt.get("artifacts", []) if item.get("path") == "sources/SERVICES-SETA-DG-2026-27-03.raw"), None)
    if not source or not (OUTPUT / source["path"]).is_file():
        raise ValueError("Captured official source bytes are absent from the customer output")
    inventory = result.get("artifacts") or []
    for item in inventory:
        path = OUTPUT / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            raise ValueError(f"Customer output failed size/hash inventory: {item['path']}")

    evidence = {
        "schema": "dio.fundingfinder.services_seta_customer_route_evidence.v1",
        "product": "FundingFinder",
        "as_of": AS_OF,
        "retrieved_at": row.get("retrieved_at"),
        "route": OUTPUT.relative_to(ROOT).as_posix(),
        "packet": PACKET_PATH.relative_to(ROOT).as_posix(),
        "packet_sha256": sha(PACKET_PATH),
        "official_source": {"url": URL, "sha256": row.get("source_sha256"), "bytes": source["bytes"]},
        "opportunity": {"id": row["opportunity_id"], "fit_state": row["fit_state"], "timing_state": row["timing_state"], "deadline": row.get("deadline")},
        "criterion_states": {item["criterion_id"]: item["state"] for item in row.get("criteria") or []},
        "required_document_count": len(row.get("required_documents") or []),
        "portal_instructions_quote_bound": next((item["source_supported"] for item in row.get("required_documents") or []
                                                  if item.get("name", "").startswith("application link")), False),
        "all_route_outputs_hash_verified": True,
        "customer_is_synthetic": True,
        "eligibility_certified": False,
        "award_guaranteed": False,
        "application_submitted": False,
        "release_authorized": False,
        "product_qualification": "UNPROVED",
        "limitations": [
            "Applicant role and proposed qualifying learning programme were not evidenced; eligibility remains unresolved.",
            "The official page says the application link and submission instructions will be published shortly. The date is source-stated; live submission availability and all detailed rules require confirmation from Services SETA.",
            "The applicant has no source evidence for its eligible legal role, programme, Annexure A priority alignment, number of programmes, or submission readiness; all matching remains unresolved.",
            "Synthetic acceptance evidence does not establish a real customer result or customer acceptance.",
        ],
    }
    RECEIPT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"route": evidence["route"], "receipt": RECEIPT.relative_to(ROOT).as_posix(), "fit_state": row["fit_state"], "timing_state": row["timing_state"], "source_sha256": row.get("source_sha256"), "outputs_verified": True, "qualification": "UNPROVED"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
