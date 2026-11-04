#!/usr/bin/env python3
"""Refresh the Services SETA DG-03 review against its latest official page and notice."""
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
UPDATE_URL = "https://serviceseta.org.za/update-on-the-2026-27-funding-windows/"
AS_OF = "2026-11-04"
BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
PACKET_PATH = BASE / "FUNDINGFINDER_SERVICESETA_CUSTOMER_PACKET_20261104_V11.json"
OUTPUT = BASE / "FUNDINGFINDER_SERVICESETA_CUSTOMER_ROUTE_20261104_V11"
RECEIPT = BASE / "FUNDINGFINDER_SERVICESETA_CUSTOMER_ROUTE_20261104_V11.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    packet = {
        "title": "Moya SkillLab: Services SETA 2026/27 window review",
        "as_of": AS_OF,
        "fetch_public": True,
        "official_url_allowlist": [URL, UPDATE_URL, "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/DG_Grant_Advert_2026_27.pdf", "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/DG_Annexure_A_2026_27.pdf", "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Evaluation-Criteria-DG-3-16-Oct-2026.pdf"],
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
            "deadline": {"date": "2026-11-15", "quote": "The submission deadline has been extended to 15 November 2026."},
            "supporting_sources": [
                {"source_id": "DG03-UPDATE", "title": "Services SETA update on all three 2026/27 funding windows, 3 November 2026", "official_url": UPDATE_URL},
                {"source_id": "DG-ADVERT", "title": "Services SETA 2026/27 DG advert", "official_url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/DG_Grant_Advert_2026_27.pdf"},
                {"source_id": "ANNEXURE-A", "title": "Services SETA Annexure A: priority occupations and interventions", "official_url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/DG_Annexure_A_2026_27.pdf"},
                {"source_id": "EVALUATION", "title": "Services SETA DG-3 evaluation criteria", "official_url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Evaluation-Criteria-DG-3-16-Oct-2026.pdf"},
            ],
            "criteria": [
                {"criterion_id": "APPLICANT-ROLE", "field": "applicant_role", "operator": "equals", "expected": "eligible to apply", "quote": "The following entities operating within the services sector are eligible to apply", "source_id": "DG-ADVERT"},
                {"criterion_id": "LEARNING-PROGRAMME", "field": "proposed_learning_programme", "operator": "equals", "expected": "scarce and critical skills", "quote": "These Learning Programmes build scarce and critical skills and enable workplace-based learning with host employers.", "source_id": "DG-ADVERT"},
                {"criterion_id": "SPOIL-OR-HARD-TO-FILL", "field": "priority_occupation_or_intervention", "operator": "equals", "expected": "Sector Priority Occupations and Interventions List", "quote": "Applicants must prioritise Learning Programmes on the Sector Priority Occupations and Interventions List (SPOIL) and Hard-to-Fill vacancies (see annexure A). Proposals outside of these categories will not be considered.", "source_id": "DG-ADVERT"},
                {"criterion_id": "UNEMPLOYED-YOUTH-SHARE", "field": "unemployed_learners_age_18_35_share_percent", "operator": "minimum", "expected": 90, "quote": "At least 90% of the unemployed learners must be aged between 18 and 35 on the date of registration.", "source_id": "DG-ADVERT"},
                {"criterion_id": "PROGRAMME-CAP", "field": "number_of_learning_programmes", "operator": "maximum", "expected": 2, "quote": "Applicants can only apply for a maximum of 2 learning programmes.", "source_id": "DG-ADVERT"},
                {"criterion_id": "ONLINE-SUBMISSION", "field": "submission_channel", "operator": "equals", "expected": "online", "quote": "Applications must be submitted online.", "source_id": "DG-ADVERT"},
            ],
            "required_documents": [
                {"name": "COMPULSORY DOCUMENTS TO SUBMIT WITH APPLICATION", "quote": "COMPULSORY DOCUMENTS TO SUBMIT WITH APPLICATION", "source_id": "DG-ADVERT"},
                {"name": "STAGE 2 : TECHNICAL EVALUATION", "quote": "STAGE 2 : TECHNICAL EVALUATION", "source_id": "EVALUATION"},
                {"name": "Declaration of Interest (Form 1a)", "quote": "Declaration of Interest (Form 1a)", "source_id": "DG-ADVERT"},
                {"name": "application system for this window is currently unavailable", "quote": "The application system for this window is currently unavailable."},
                {"name": "confirmed working submission link and instructions", "quote": "The application system for this window is currently unavailable."},
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
    if row.get("opportunity_id") != "SERVICES-SETA-DG-2026-27-03" or row.get("fit_state") != "unknown_review_required" or row.get("timing_state") != "within_stated_deadline" or row.get("deadline") != "2026-11-15":
        raise ValueError("Services SETA source did not produce the expected unresolved-fit/updated-deadline states")
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
        "supporting_sources": json.loads((OUTPUT / "source_register.json").read_text()).get("supporting_sources", []),
        "opportunity": {"id": row["opportunity_id"], "fit_state": row["fit_state"], "timing_state": row["timing_state"], "deadline": row.get("deadline")},
        "criterion_states": {item["criterion_id"]: item["state"] for item in row.get("criteria") or []},
        "required_document_count": len(row.get("required_documents") or []),
        "supporting_source_count": len((OUTPUT / "source_register.json").exists() and json.loads((OUTPUT / "source_register.json").read_text()).get("supporting_sources", [])),
        "application_system_status_quote_bound": next((item["source_supported"] for item in row.get("required_documents") or []
                                                        if item.get("name") == "application system for this window is currently unavailable"), False),
        "all_route_outputs_hash_verified": True,
        "customer_is_synthetic": True,
        "eligibility_certified": False,
        "award_guaranteed": False,
        "application_submitted": False,
        "release_authorized": False,
        "product_qualification": "UNPROVED",
        "limitations": [
            "Applicant role and proposed qualifying learning programme were not evidenced; eligibility remains unresolved.",
            "Services SETA's 3 November update states that all three funding-window application systems are unavailable and extends the deadline to 15 November 2026. The DG-03 window page still has pending-link language; monitor official updates and confirm a working channel before relying on the deadline.",
            "The applicant has no source evidence for its eligible legal role, programme, Annexure A priority alignment, number of programmes, learner age composition, or submission readiness; all matching remains unresolved.",
            "Official advert, priority annexure, and evaluation criteria are captured with exact byte and extracted-text hashes; detailed policy/unit-cost files remain referenced but are not captured in this run.",
            "Synthetic acceptance evidence does not establish a real customer result or customer acceptance.",
        ],
    }
    RECEIPT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"route": evidence["route"], "receipt": RECEIPT.relative_to(ROOT).as_posix(), "fit_state": row["fit_state"], "timing_state": row["timing_state"], "source_sha256": row.get("source_sha256"), "outputs_verified": True, "qualification": "UNPROVED"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
