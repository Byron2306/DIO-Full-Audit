from __future__ import annotations

from typing import Any

from lingua.capital_outreach import build_capital_outreach_projection

from .models import validate_opportunity_type


CHANNEL_BY_TYPE = {
    "INVESTOR": "professional_email_or_warm_intro",
    "GRANT": "programme_application_or_funder_contact",
    "DONOR": "foundation_contact_or_programme_route",
    "SPONSOR": "corporate_partnership_route",
    "PATRONAGE": "patronage_platform_or_public_support_page",
    "ACCELERATOR": "programme_application_route",
    "PRIZE": "competition_application_route",
}

OBJECTIVE_BY_TYPE = {
    "INVESTOR": "Open a qualified investment conversation around the narrowest evidence-backed DIO wedge.",
    "GRANT": "Confirm programme fit and prepare an evidence-bound application conversation.",
    "DONOR": "Explore mission and public-benefit fit without implying donor intent.",
    "SPONSOR": "Explore a bounded sponsorship activation with explicit value and proof.",
    "PATRONAGE": "Test whether recurring supporters value the public DIO build, open resources, or early-access proposition.",
    "ACCELERATOR": "Test eligibility and strategic programme fit before any application commitment.",
    "PRIZE": "Test eligibility and evidence fit before any competition submission.",
}


def _name(opportunity: dict[str, Any]) -> str:
    return str(
        opportunity.get("organisation_name")
        or opportunity.get("organisation")
        or opportunity.get("title")
        or opportunity.get("opportunity_id")
        or "this opportunity"
    ).strip()


def build_outreach_bundle(opportunity: dict[str, Any], atlas_fit: dict[str, Any], hypothesis: dict[str, Any]) -> dict[str, Any]:
    opportunity_type = validate_opportunity_type(str(opportunity.get("opportunity_type") or ""))
    opportunity_id = str(opportunity.get("opportunity_id") or "").strip()
    if not opportunity_id:
        raise ValueError("opportunity_id is required")
    organisation = _name(opportunity)
    products = [str(x) for x in (atlas_fit.get("primary_products") or [])[:6] if str(x).strip()]
    proofs = [str(x) for x in (atlas_fit.get("proof_bundle") or [])[:8] if str(x).strip()]
    pitch_family = str(atlas_fit.get("recommended_pitch_family") or hypothesis.get("family") or "").strip()
    hypothesis_statement = str(hypothesis.get("statement") or "").strip()
    recommended_channel = CHANNEL_BY_TYPE[opportunity_type]

    safe_claims = [
        "DIO has a governed, evidence-bound product portfolio and documented engineering proof where cited.",
        "The proposed product/proof wedge is an Atlas strategic-fit model output, not evidence of target demand.",
        "Any cited proof asset must be attached or linked exactly as verified before external use.",
    ]
    claims_to_avoid = [
        "Do not claim the target is interested, committed, or willing to fund DIO.",
        "Do not claim investment, grant, sponsorship, donation, patronage, or prize success before evidence exists.",
        "Do not claim money is raised or settled without SETTLED_FUNDS_EVIDENCE.",
        "Do not imply a personal relationship or private contact route that was not publicly observed or operator-provided.",
    ]

    lingua_projection = build_capital_outreach_projection(
        opportunity=opportunity,
        organisation=organisation,
        products=products,
        proofs=proofs,
        pitch_family=pitch_family,
        recommended_channel=recommended_channel,
    )
    opening = str(lingua_projection["selected_hook"])

    subject = f"DIO | {pitch_family.replace('_', ' ').title() if pitch_family else 'evidence-backed fit'}"
    wedge = ", ".join(products[:3]) or "a narrow DIO capability wedge"
    proof_text = ", ".join(proofs[:3]) or "the relevant verified proof assets"
    draft = (
        f"{opening}\n\n"
        f"Rather than pitch the entire DIO portfolio, I’d like to show a focused wedge around {wedge}. "
        f"The current working hypothesis is: {hypothesis_statement or 'this proposition may fit the published mandate or audience.'}\n\n"
        f"The supporting evidence set would lead with {proof_text}. "
        "I’d value a short conversation to test whether there is genuine fit. No commitment is assumed."
    )

    return {
        "schema": "dio.market_capital.outreach_bundle.v1",
        "opportunity_id": opportunity_id,
        "opportunity_type": opportunity_type,
        "organisation": organisation,
        "campaign_objective": OBJECTIVE_BY_TYPE[opportunity_type],
        "recommended_channel": recommended_channel,
        "draft_subject": subject,
        "draft_opening": opening,
        "draft_outreach": draft,
        "pitch_angle": hypothesis_statement or pitch_family,
        "recommended_product_wedge": products,
        "recommended_proof_bundle": proofs,
        "lingua_projection": lingua_projection,
        "safe_claims": safe_claims,
        "claims_to_avoid": claims_to_avoid,
        "assets_to_prepare": proofs,
        "missing_research": [
            "Confirm route freshness and target role before any send.",
            "Confirm each external claim against current evidence.",
            "Confirm Legalis and operator approval for the intended channel/action.",
        ],
        "operator_state": "NEEDS_YOU",
        "legalis_state": "REQUIRED_BEFORE_EXTERNAL_ACTION",
        "truth_class": "DRAFT_RECOMMENDATION",
        "send_authority": False,
        "submission_authority": False,
        "financial_commitment_authority": False,
        "authority_created": False,
        "external_effects": False,
    }
