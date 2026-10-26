from __future__ import annotations

from typing import Any

from lingua.semantic_law import PROJECTION_INVARIANTS, build_semantic_law


APPROACH_BY_TYPE = {
    "INVESTOR": "thesis_first",
    "GRANT": "mandate_first",
    "DONOR": "mission_first",
    "SPONSOR": "activation_first",
    "PATRONAGE": "community_first",
    "ACCELERATOR": "programme_fit_first",
    "PRIZE": "eligibility_proof_first",
}

HOOK_FAMILY_BY_APPROACH = {
    "thesis_first": "bounded_thesis",
    "mandate_first": "published_mandate",
    "mission_first": "mission_intersection",
    "activation_first": "value_activation",
    "community_first": "community_value",
    "programme_fit_first": "programme_fit",
    "eligibility_proof_first": "eligibility_evidence",
}

APPROACH_VARIANTS = (
    {
        "approach": "thesis_first",
        "tone": "concise_strategic",
        "hook_family": "bounded_thesis",
        "cta_style": "test_the_thesis",
    },
    {
        "approach": "proof_first",
        "tone": "evidence_forward",
        "hook_family": "proof_signal",
        "cta_style": "inspect_the_evidence",
    },
    {
        "approach": "wedge_first",
        "tone": "focused_practical",
        "hook_family": "narrow_wedge",
        "cta_style": "test_one_wedge",
    },
    {
        "approach": "mandate_first",
        "tone": "programme_literate",
        "hook_family": "published_mandate",
        "cta_style": "confirm_programme_fit",
    },
    {
        "approach": "mission_first",
        "tone": "mission_credible",
        "hook_family": "mission_intersection",
        "cta_style": "explore_mission_fit",
    },
    {
        "approach": "activation_first",
        "tone": "commercial_partnership",
        "hook_family": "value_activation",
        "cta_style": "scope_an_activation",
    },
    {
        "approach": "community_first",
        "tone": "human_direct",
        "hook_family": "community_value",
        "cta_style": "test_supporter_value",
    },
    {
        "approach": "programme_fit_first",
        "tone": "programme_specific",
        "hook_family": "programme_fit",
        "cta_style": "confirm_eligibility_and_fit",
    },
    {
        "approach": "eligibility_proof_first",
        "tone": "precise_evidence",
        "hook_family": "eligibility_evidence",
        "cta_style": "confirm_eligibility",
    },
)


def _clean(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _pitch_text(pitch_family: str) -> str:
    return _clean(pitch_family, "the relevant DIO proposition").replace("_", " ").lower()


def _semantic_source(
    *,
    opportunity: dict[str, Any],
    organisation: str,
    products: list[str],
    proofs: list[str],
    pitch_family: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    wedge = ", ".join(products[:3]) or "a narrow DIO capability wedge"
    proof = ", ".join(proofs[:4]) or "verified proof assets where available"
    product = {
        "id": products[0] if products else "DIO_CAPITAL_WEDGE",
        "name": wedge,
        "offer": f"A focused evidence-backed DIO wedge around {wedge}.",
        "promise": "Explore strategic fit without assuming target demand, funding intent, commitment, or financial outcome.",
        "proof": proof,
        "cta": "Test whether there is genuine fit before any external commitment.",
    }
    audience = {
        "id": _clean(opportunity.get("opportunity_id"), "capital-opportunity"),
        "name": organisation,
        "pain": "Only publicly observed mandate, thesis, programme, or audience information may be used.",
        "outcome": f"Determine whether a bounded conversation about {_pitch_text(pitch_family)} is warranted.",
    }
    return product, audience


def _hook_variants(
    *,
    opportunity_type: str,
    organisation: str,
    pitch_family: str,
    products: list[str],
    proofs: list[str],
) -> list[dict[str, str]]:
    pitch = _pitch_text(pitch_family)
    wedge = ", ".join(products[:2]) or "a narrow DIO capability wedge"
    proof = proofs[0] if proofs else "the relevant verified proof"

    variants = [
        {
            "family": "bounded_thesis",
            "approach": "thesis_first",
            "text": f"I’m testing a narrow thesis: whether {organisation}'s published focus could intersect with {pitch}.",
        },
        {
            "family": "proof_signal",
            "approach": "proof_first",
            "text": f"I’d like to test whether {proof} is relevant to {organisation}'s published focus, rather than ask you to take a broad DIO claim on trust.",
        },
        {
            "family": "narrow_wedge",
            "approach": "wedge_first",
            "text": f"Rather than pitch the whole DIO portfolio, I’d like to test one focused wedge with {organisation}: {wedge}.",
        },
    ]

    type_specific = {
        "GRANT": {
            "family": "published_mandate",
            "approach": "mandate_first",
            "text": f"Your published programme information suggests a fit question worth testing around {pitch}, without assuming eligibility or funding intent.",
        },
        "DONOR": {
            "family": "mission_intersection",
            "approach": "mission_first",
            "text": f"I’m exploring whether {organisation}'s published mission could intersect with a focused DIO proposition around {pitch}.",
        },
        "SPONSOR": {
            "family": "value_activation",
            "approach": "activation_first",
            "text": f"I’d like to test whether a bounded activation around {wedge} could create credible value for {organisation}, without assuming sponsorship interest.",
        },
        "PATRONAGE": {
            "family": "community_value",
            "approach": "community_first",
            "text": f"I’m testing whether the community around {organisation} might value supporting a focused DIO build around {pitch}.",
        },
        "ACCELERATOR": {
            "family": "programme_fit",
            "approach": "programme_fit_first",
            "text": f"I’m checking whether {wedge} may fit {organisation}'s published programme criteria before treating an application as warranted.",
        },
        "PRIZE": {
            "family": "eligibility_evidence",
            "approach": "eligibility_proof_first",
            "text": f"I’m checking whether the evidence behind {wedge} may satisfy {organisation}'s published eligibility and proof criteria before any submission.",
        },
    }
    if opportunity_type in type_specific:
        variants.insert(0, type_specific[opportunity_type])
    return variants


def build_capital_outreach_projection(
    *,
    opportunity: dict[str, Any],
    organisation: str,
    products: list[str],
    proofs: list[str],
    pitch_family: str,
    recommended_channel: str,
) -> dict[str, Any]:
    """Project one truth-bound capital message into testable hook/style approaches.

    LINGUA may change the lawful linguistic skin, including hook, tone, pacing and CTA expression.
    It may not strengthen the source meaning, infer target psychology, claim demand, or authorize contact.
    """
    opportunity_type = _clean(opportunity.get("opportunity_type")).upper()
    selected_approach = APPROACH_BY_TYPE.get(opportunity_type, "thesis_first")
    product, audience = _semantic_source(
        opportunity=opportunity,
        organisation=organisation,
        products=products,
        proofs=proofs,
        pitch_family=pitch_family,
    )
    law = build_semantic_law(product, audience)
    hooks = _hook_variants(
        opportunity_type=opportunity_type,
        organisation=organisation,
        pitch_family=pitch_family,
        products=products,
        proofs=proofs,
    )
    selected = next((row for row in hooks if row["approach"] == selected_approach), hooks[0])

    return {
        "schema": "dio.lingua.capital_outreach_projection.v1",
        "semantic_law_hash": law["semantic_law_hash"],
        "source_hash": law["source_hash"],
        "selected_approach": selected["approach"],
        "selected_hook_family": selected["family"],
        "selected_hook": selected["text"],
        "recommended_channel": recommended_channel,
        "hook_variants": hooks,
        "approach_variants": [dict(row) for row in APPROACH_VARIANTS],
        "mutable_projection_fields": list(law["projection"]["mutable_fields"]),
        "preserves": list(PROJECTION_INVARIANTS),
        "meaning_preserved": True,
        "pivot_policy": {
            "allowed": ["hook_style", "tone", "pacing", "story_arc", "cta_expression", "approach"],
            "requires_observed_evidence_for_learning": True,
            "target_personality_inference_allowed": False,
            "target_emotion_inference_allowed": False,
            "automatic_external_action_allowed": False,
        },
        "market_validation_claimed": False,
        "send_authorized": False,
        "publication_authorized": False,
        "authority_created": False,
        "truth_boundary": "LINGUA can pivot hook, style and approach while preserving source-bound claims and authority boundaries. Creative adaptation is not evidence of demand or funding intent.",
    }
