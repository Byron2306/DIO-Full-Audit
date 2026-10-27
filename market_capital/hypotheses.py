from __future__ import annotations

import hashlib
from typing import Any

from .models import HYPOTHESIS_STATES, validate_opportunity_type


TYPE_ANGLES: dict[str, tuple[tuple[str, str], ...]] = {
    "INVESTOR": (
        ("PRODUCT_FACTORY_VENTURE_OS", "The governed product-factory and portfolio operating system may fit the target's venture thesis."),
        ("GOVERNED_AI_INFRASTRUCTURE", "DIO's governed AI infrastructure and evidence-first authority model may fit enterprise AI investment priorities."),
        ("VERTICAL_SAAS_PORTFOLIO", "A narrow portfolio wedge may fit a vertical SaaS thesis better than pitching the full organism."),
    ),
    "GRANT": (
        ("EDUCATION_OER_PUBLIC_GOOD", "The opportunity may fit DIO's education, OER, research, and measurable public-good work."),
        ("OPEN_RESEARCH_AND_PUBLIC_RESOURCE", "The funder may value open research and reusable public resources with evidence-bound reporting."),
        ("AFRICAN_EDTECH_IMPACT", "The programme may fit African education innovation and demonstrable learning-impact work."),
    ),
    "DONOR": (
        ("EDUCATION_OER_PUBLIC_GOOD", "The donor may value public-benefit education, OER, and measurable impact rather than a commercial product pitch."),
        ("AFRICAN_EDTECH_IMPACT", "The donor may respond to an African education-impact proposition backed by concrete proof and stewardship."),
        ("OPEN_RESEARCH_AND_PUBLIC_RESOURCE", "The donor may support open research or public resources where impact and stewardship are explicit."),
    ),
    "SPONSOR": (
        ("STRATEGIC_ECOSYSTEM_SPONSORSHIP", "The sponsor may value strategic ecosystem association, credible visibility, and a narrow activation wedge."),
        ("EDUCATION_OER_PUBLIC_GOOD", "The sponsor may prefer an education/public-good activation with measurable outcomes."),
        ("GOVERNED_AI_INFRASTRUCTURE", "The sponsor may value association with governed AI innovation and enterprise trust."),
    ),
    "PATRONAGE": (
        ("CREATOR_BUILD_JOURNEY", "Supporters may value the public DIO build journey, early access, and recurring behind-the-scenes proof."),
        ("OPEN_RESEARCH_AND_PUBLIC_RESOURCE", "Supporters may value keeping open research, demos, and public resources available."),
        ("EDUCATION_OER_PUBLIC_GOOD", "Supporters may value open educational tools and learning resources as a recurring public benefit."),
    ),
    "ACCELERATOR": (
        ("PRODUCT_FACTORY_VENTURE_OS", "The programme may fit DIO as a governed product-factory venture rather than a single-product startup."),
        ("GOVERNED_AI_INFRASTRUCTURE", "The programme may value DIO's governed AI infrastructure and authority controls."),
        ("EMERGING_MARKET_AI_INFRASTRUCTURE", "The accelerator may value an emerging-market AI infrastructure thesis with South African roots."),
    ),
    "PRIZE": (
        ("INNOVATION_PROOF", "The prize may fit DIO's demonstrated engineering novelty, evidence discipline, and product-factory breadth."),
        ("EDUCATION_OER_PUBLIC_GOOD", "The prize may fit education/OER impact backed by published and programme evidence."),
        ("GOVERNED_AI_INFRASTRUCTURE", "The prize may fit responsible or governed AI innovation backed by authority-wall proof."),
    ),
}


def _id(opportunity_id: str, family: str) -> str:
    digest = hashlib.sha256(f"{opportunity_id}|{family}".encode("utf-8")).hexdigest()[:16]
    return f"hyp_{digest}"


def generate_hypotheses(opportunity: dict[str, Any], atlas_fit: dict[str, Any]) -> list[dict[str, Any]]:
    opportunity_type = validate_opportunity_type(str(opportunity.get("opportunity_type") or ""))
    opportunity_id = str(opportunity.get("opportunity_id") or "").strip()
    if not opportunity_id:
        raise ValueError("opportunity_id is required for hypothesis generation")

    lead_family = str(atlas_fit.get("recommended_pitch_family") or "").strip()
    angles = list(TYPE_ANGLES[opportunity_type])
    if lead_family and lead_family not in {family for family, _ in angles}:
        angles.insert(0, (lead_family, f"Atlas strategic fit suggests testing the {lead_family.replace('_', ' ').lower()} proposition for this target."))
    else:
        angles.sort(key=lambda item: item[0] != lead_family if lead_family else False)

    rows: list[dict[str, Any]] = []
    for family, statement in angles[:4]:
        rows.append({
            "schema": "dio.market_capital.hypothesis.v1",
            "hypothesis_id": _id(opportunity_id, family),
            "opportunity_id": opportunity_id,
            "opportunity_type": opportunity_type,
            "family": family,
            "statement": statement,
            "state": "TEST",
            "evidence_refs": [],
            "atlas_primary_products": list(atlas_fit.get("primary_products") or [])[:6],
            "atlas_proof_bundle": list(atlas_fit.get("proof_bundle") or [])[:8],
            "truth_class": "HYPOTHESIS",
            "willingness_to_fund": "UNPROVED",
            "authority_created": False,
            "external_effects": False,
        })
    return rows


def update_hypothesis_state(record: dict[str, Any], new_state: str, evidence_refs: list[str] | None = None) -> dict[str, Any]:
    state = str(new_state or "").strip().upper()
    if state not in HYPOTHESIS_STATES:
        raise ValueError(f"unsupported hypothesis state: {new_state}")
    refs = [str(ref).strip() for ref in (evidence_refs if evidence_refs is not None else record.get("evidence_refs") or []) if str(ref).strip()]
    if state == "PROMOTE" and not refs:
        raise ValueError("PROMOTE requires evidence refs from real observed outcomes")
    updated = dict(record)
    updated["state"] = state
    updated["evidence_refs"] = refs
    updated["truth_class"] = "HYPOTHESIS"
    updated["authority_created"] = False
    updated["external_effects"] = False
    return updated
