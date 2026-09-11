from market_capital.recommendations import build_action_recommendation


def _investor(**overrides):
    row = {
        "opportunity_id": "OPP-INV-1",
        "opportunity_type": "INVESTOR",
        "organisation_name": "Example Ventures",
        "priority_score": 90,
        "timing_score": 88,
        "route_state": "PUBLIC_ROUTE_VERIFIED",
        "route_quality": 90,
        "evidence_freshness": 90,
        "do_not_contact": False,
        "atlas_fit": {
            "primary_products": ["dio-platform"],
            "proof_bundle": ["proof:governed-ai"],
            "recommended_pitch_family": "GOVERNED_AI_INFRASTRUCTURE",
        },
        "leading_hypothesis": {
            "family": "GOVERNED_AI_INFRASTRUCTURE",
            "statement": "The published thesis may fit governed AI infrastructure.",
        },
    }
    row.update(overrides)
    return row


def test_high_fit_verified_investor_can_be_recommended_for_reviewed_outreach():
    rec = build_action_recommendation(_investor())
    assert rec["recommendation"] == "APPROACH_NOW"
    assert rec["draft_available"] is True
    assert rec["operator_question"].startswith("Consider")
    assert rec["truth_class"] == "ACTION_RECOMMENDATION_MODEL_OUTPUT"
    assert rec["authority_created"] is False
    assert rec["external_effects"] is False
    assert rec["outreach_bundle"]["send_authority"] is False


def test_high_fit_without_route_is_research_first_not_approach_now():
    rec = build_action_recommendation(
        _investor(route_state="NO_PUBLIC_ROUTE", route_quality=0)
    )
    assert rec["recommendation"] == "RESEARCH_FIRST"
    assert rec["draft_available"] is False
    assert rec["outreach_bundle"] is None


def test_do_not_contact_always_wins():
    rec = build_action_recommendation(
        _investor(priority_score=100, timing_score=100, do_not_contact=True)
    )
    assert rec["recommendation"] == "DO_NOT_CONTACT"
    assert rec["draft_available"] is False
    assert rec["outreach_bundle"] is None


def test_grant_with_unresolved_eligibility_cannot_be_apply_now():
    row = {
        "opportunity_id": "OPP-GRANT-1",
        "opportunity_type": "GRANT",
        "priority_score": 94,
        "timing_score": 95,
        "route_state": "APPLICATION_ROUTE_VERIFIED",
        "route_quality": 95,
        "evidence_freshness": 95,
        "eligibility_state": "UNRESOLVED",
        "do_not_contact": False,
    }
    rec = build_action_recommendation(row)
    assert rec["recommendation"] == "RESEARCH_FIRST"


def test_verified_grant_can_be_apply_now_without_submission_authority():
    row = {
        "opportunity_id": "OPP-GRANT-2",
        "opportunity_type": "GRANT",
        "organisation_name": "Example Foundation",
        "priority_score": 91,
        "timing_score": 92,
        "route_state": "APPLICATION_ROUTE_VERIFIED",
        "route_quality": 95,
        "evidence_freshness": 90,
        "eligibility_state": "VERIFIED_ELIGIBLE",
        "do_not_contact": False,
        "atlas_fit": {
            "primary_products": ["education-product"],
            "proof_bundle": ["proof:education"],
            "recommended_pitch_family": "EDUCATION_OER_PUBLIC_GOOD",
        },
        "leading_hypothesis": {
            "family": "EDUCATION_OER_PUBLIC_GOOD",
            "statement": "The programme may fit education and OER public-good work.",
        },
    }
    rec = build_action_recommendation(row)
    assert rec["recommendation"] == "APPLY_NOW"
    assert rec["draft_available"] is True
    assert rec["outreach_bundle"]["submission_authority"] is False
    assert rec["authority_created"] is False
