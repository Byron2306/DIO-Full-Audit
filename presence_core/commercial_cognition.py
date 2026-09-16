from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from portfolio_runtime import load_portfolio
from products.commercial_pricing_registry import (
    build_commercial_pricing_registry,
)
from products.vesper_web_chat import resolve_incarnation
from semantic_marketing import semantic_marketing_brief



# Deterministic sibling-product disambiguation.
#
# Semantic similarity answers "what family of work is this?"
# Job morphology answers "what operation is the customer asking for?"
#
# These rules never create products or authority. They only distinguish
# already-canonical products when semantic routing produces close siblings.
JOB_MORPHOLOGY_RULES = {
    "HOMS Assess": {
        "positive": (
            r"\b(mark|marking|grading|score|scoring)\b",
            r"\bgrade\b(?!\s+(?:level\b|[1-9]\b|1[0-2]\b|one\b|two\b|three\b|four\b|five\b|six\b|seven\b|eight\b|nine\b|ten\b|eleven\b|twelve\b))",
            r"\b(student|learner|script|scripts|essay|essays|submission|submissions|assignment|assignments)\b",
            r"\b(papers?)\s+(to\s+)?(mark|grade|score)\b",
        ),
        "negative": (
            r"\b(create|generate|design|write|draft|build|prepare)\b.{0,40}\b(exam|test|question\s*paper|assessment\s*paper|memo|memorandum)\b",
            r"\b(moderate|moderation|second[- ]mark|second[- ]marker)\b",
        ),
    },
    "HOMS Exam": {
        "positive": (
            r"\b(create|generate|design|write|draft|build|prepare)\b.{0,40}\b(exam|test|question\s*paper|assessment\s*paper|memo|memorandum)\b",
            r"\b(exam|test|question\s*paper)\b.{0,40}\b(create|generate|design|write|draft|build|prepare)\b",
            r"\b(exam(?:ination)?|test|question\s*paper|assessment\s*paper)\b.{0,50}\b(memo|memorandum|answer\s*key|marking\s*(?:memo|guide))\b",
            r"\b(memo|memorandum|answer\s*key|marking\s*(?:memo|guide))\b.{0,50}\b(exam(?:ination)?|test|question\s*paper|assessment\s*paper)\b",
        ),
        "negative": (
            r"\b(papers?|scripts?|essays?|submissions?)\s+(to\s+)?(mark|grade|score)\b",
            r"\b(mark|marking|grading)\b.{0,30}\b(student|learner|script|essay|submission)\b",
        ),
    },
    "HOMS Moderate": {
        "positive": (
            r"\b(moderate|moderation|second[- ]mark|second[- ]marker)\b",
            r"\b(review|check|verify|audit)\b.{0,35}\b(marking|marks|grades|grading|assessment\s*decisions?)\b",
            r"\b(inter[- ]?rater|marker\s+agreement|moderation\s+sample)\b",
        ),
        "negative": (
            r"\b(papers?|scripts?|essays?|submissions?)\s+(to\s+)?(mark|grade|score)\b",
            r"\b(create|generate|design|write|draft|build)\b.{0,30}\b(exam|test|question\s*paper)\b",
        ),
    },

    "Professional Correspondence": {
        "positive": (
            r"\b(reply|email|letter|message|memo|correspondence)\b",
            r"\b(write|draft|rewrite|compose|respond|reply)\b.{0,45}\b(client|customer|recipient|supplier|vendor|colleague|stakeholder)\b",
            r"\b(client|customer|recipient|supplier|vendor|colleague|stakeholder)\b.{0,45}\b(reply|email|letter|message|response)\b",
        ),
        "negative": (
            r"\b(pack|batch|series|library|templates?|campaign|sequence|multiple|bulk)\b",
            r"\b(contract\s+clause|legal\s+obligation|terms\s+and\s+conditions)\b",
        ),
    },
    "Professional Correspondence Studio": {
        "positive": (
            r"\b(pack|batch|series|library|templates?|campaign|sequence|multiple|bulk)\b.{0,45}\b(correspondence|emails?|letters?|messages?|replies|responses)\b",
            r"\b(correspondence|emails?|letters?|messages?|replies|responses)\b.{0,45}\b(pack|batch|series|library|templates?|campaign|sequence|multiple|bulk)\b",
            r"\b(standardise|standardize|systematise|systematize)\b.{0,45}\b(customer|client|professional)\s+(communication|correspondence)\b",
        ),
        "negative": (
            r"\b(a|one|single)\b.{0,45}\b(reply|email|letter|message|response)\b",
            r"\b(reply|respond)\b.{0,45}\b(invoice|client|customer)\b",
        ),
    },
    "Document Studio Edit": {
        "positive": (
            r"\b(edit|revise|proofread|polish|format)\b.{0,45}\b(document|report|file|manuscript|proposal)\b",
        ),
        "negative": (
            r"\b(reply|email|letter|message|correspondence)\b",
        ),
    },

    "GrantProof": {
        "positive": (
            r"\b(grant|funding)\b.{0,60}\b(application|submission|requirements?|eligibility|deadline|mandatory)\b",
            r"\b(application|submission|requirements?|eligibility|deadline|mandatory)\b.{0,60}\b(grant|funding)\b",
            r"\bgrant\s+(requirement|requirements|obligation|obligations)\b",
        ),
        "negative": (
            r"\b(tender|rfp|bid|procurement)\b",
        ),
    },

    "TenderProof": {
        "positive": (
            r"\b(tender|rfp|bid|procurement)\b.{0,60}\b(requirements?|submission|deadline|mandatory|documents?)\b",
            r"\b(requirements?|submission|deadline|mandatory)\b.{0,60}\b(tender|rfp|bid|procurement)\b",
        ),
        "negative": (
            r"\bgrant\b.{0,40}\b(application|submission|requirements?)\b",
        ),
    },

    "DonorProof": {
        "positive": (
            r"\b(donor|funder)\b.{0,60}\b(report|reporting|quarterly|annual|indicator|evidence|obligation)\b",
            r"\b(report|reporting|quarterly|annual)\b.{0,60}\b(donor|funder)\b",
        ),
        "negative": (
            r"\bprogramme[- ]level\b",
            r"\bprogram[- ]level\b",
        ),
    },

    "ProgrammeProof": {
        "positive": (
            r"\b(programme|program)[- ]level\b",
            r"\b(workstream|workstreams)\b.{0,60}\b(indicator|indicators|evidence|reporting)\b",
            r"\b(indicator|indicators|evidence|reporting)\b.{0,60}\b(workstream|workstreams)\b",
        ),
        "negative": (
            r"\bgrant\b.{0,40}\b(application|submission)\b",
        ),
    },

    "ImpactProof": {
        "positive": (
            r"\b(impact|outcome|outcomes|beneficiary|beneficiaries)\b.{0,60}\b(indicator|indicators|evidence|measurement|results?)\b",
            r"\b(measure|measurement|evaluate|evaluation)\b.{0,60}\b(impact|outcome|beneficiary)\b",
        ),
        "negative": (
            r"\b(workstream|workstreams|programme[- ]level|program[- ]level)\b",
        ),
    },

    "Report & Pitch Studio": {
        "positive": (
            r"\b(create|draft|write|design|prepare|produce)\b.{0,60}\b(report|pitch|deck|presentation)\b",
            r"\b(report|pitch|deck|presentation)\b.{0,60}\b(page|pages|slide|slides|visual|narrative)\b",
        ),
        "negative": (
            r"\b(donor|funder)\b.{0,60}\b(reporting|indicator|evidence|obligation)\b",
            r"\bgrant\b.{0,50}\b(requirement|requirements|submission|deadline)\b",
        ),
    },
}


def _job_morphology_score(product_name: str, message: str) -> int:
    rule = JOB_MORPHOLOGY_RULES.get(product_name)
    if not rule:
        return 0

    text = str(message or "").casefold()

    positive_hits = sum(
        1 for pattern in rule.get("positive", ())
        if re.search(pattern, text)
    )
    negative_hits = sum(
        1 for pattern in rule.get("negative", ())
        if re.search(pattern, text)
    )

    # Direct job evidence should dominate incidental semantic overlap.
    return (positive_hits * 12) - (negative_hits * 10)


TOKEN_ALIASES = {
    "mark": {"marking", "assessment", "learner_script"},
    "marks": {"marking", "assessment", "learner_script"},
    "marking": {"assessment", "learner_script"},
    "grade": {"assessment", "learner_script"},
    "grading": {"assessment", "learner_script"},
    "paper": {"assessment", "learner_script"},
    "papers": {"assessment", "learner_script"},
    "script": {"assessment", "learner_script"},
    "scripts": {"assessment", "learner_script"},
    "consistency": {"standardise", "quality", "review"},
    "consistent": {"standardise", "quality"},
    "challenged": {"review", "evidence"},
    "appeal": {"review", "evidence"},
    "vendor": {"supplier", "vendor"},
    "vendors": {"supplier", "vendor"},
    "supplier": {"supplier", "vendor"},
    "grant": {"grant", "donor", "obligation"},
    "donor": {"donor", "grant", "obligation"},
    "rfp": {"tender", "requirement"},
    "bid": {"tender", "requirement"},
    "tender": {"tender", "requirement"},
    "privacy": {"popia", "privacy"},
    "invoice": {"correspondence", "invoice"},
    "reply": {"correspondence"},
    "letter": {"correspondence"},
    "email": {"correspondence"},
    "launch": {"launch", "campaign"},
    "funding": {"funding", "opportunity"},
}


def _tokens(value: Any) -> set[str]:
    result: set[str] = set()

    for raw in re.findall(r"[a-z0-9]+", str(value or "").casefold()):
        if len(raw) < 3:
            continue

        result.add(raw)

        if raw.endswith("ing") and len(raw) > 5:
            result.add(raw[:-3])
        elif raw.endswith("ed") and len(raw) > 4:
            result.add(raw[:-2])
        elif raw.endswith("s") and len(raw) > 4:
            result.add(raw[:-1])

        result.update(TOKEN_ALIASES.get(raw, set()))

    return result


def _pricing_rows(root: Path) -> dict[str, dict[str, Any]]:
    registry = build_commercial_pricing_registry(root)
    if registry.get("product_count") != 68:
        raise ValueError("commercial cognition requires exact 68-product pricing truth")

    return {
        str(row["name"]): row
        for row in registry["products"]
    }


def _semantic_surface(
    incarnation: dict[str, Any],
    pricing: dict[str, Any],
) -> str:
    name = str(incarnation.get("Incarnation") or "")
    try:
        brief = semantic_marketing_brief(name).get("brief") or {}
    except Exception:
        brief = {}

    return " ".join(
        [
            name,
            str(incarnation.get("Suite") or ""),
            str(incarnation.get("Product Family") or ""),
            str(incarnation.get("source_work_patterns") or ""),
            str(incarnation.get("atlas_domain_ids") or ""),
            str(brief.get("audience_name") or ""),
            str(brief.get("pain") or ""),
            str(brief.get("outcome") or ""),
            str(brief.get("marketing_statement") or ""),
            str(pricing.get("primary_scope_unit") or ""),
            " ".join(pricing.get("secondary_scope_units") or []),
            str(pricing.get("pricing_model") or ""),
        ]
    )


def _spoken_canonical_name(name: str) -> str:
    value = re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])",
        " ",
        str(name or ""),
    )
    value = value.replace("_", " ").replace("-", " ")
    return " ".join(value.casefold().split())


def _fallback_route(
    message: str,
    root: Path,
) -> dict[str, Any]:
    message_tokens = _tokens(message)
    pricing_by_name = _pricing_rows(root)

    scored: list[dict[str, Any]] = []

    for incarnation in load_portfolio()["incarnations"]:
        name = str(incarnation.get("Incarnation") or "").strip()
        if not name or name not in pricing_by_name:
            continue

        surface = _semantic_surface(
            incarnation,
            pricing_by_name[name],
        )

        surface_tokens = _tokens(surface)

        spoken_name = _spoken_canonical_name(name)
        spoken_message = " ".join(
            str(message or "").casefold().split()
        )

        name_tokens = _tokens(spoken_name)

        exact = (
            100
            if (
                name.casefold() in message.casefold()
                or spoken_name in spoken_message
            )
            else 0
        )

        name_overlap = (
            len(message_tokens & name_tokens)
            * 14
        )
        semantic_overlap = len(message_tokens & surface_tokens) * 4

        morphology = _job_morphology_score(name, message)
        score = exact + name_overlap + semantic_overlap + morphology

        if score:
            scored.append({
                "incarnation": name,
                "score": score,
            })

    scored.sort(
        key=lambda row: (
            -int(row["score"]),
            str(row["incarnation"]),
        )
    )

    candidates = scored[:3]

    if not candidates:
        return {
            "state": "NEEDS_YOU",
            "incarnation": None,
            "basis": "no_commercial_semantic_route",
            "candidates": [],
            "authority_created": False,
        }

    top = int(candidates[0]["score"])
    second = (
        int(candidates[1]["score"])
        if len(candidates) > 1
        else -999
    )

    if top < 8:
        return {
            "state": "NEEDS_YOU",
            "incarnation": None,
            "basis": "ambiguous_commercial_semantic_route",
            "candidates": candidates,
            "authority_created": False,
        }

    if top - second < 3:
        # A semantic near-tie may be resolved only when exactly one
        # candidate has direct positive job-morphology evidence.
        #
        # This lets "create an examination paper" beat a broad sibling
        # such as HOMS Learning Studio without allowing morphology to
        # collapse genuine ambiguity where several products match the
        # customer's requested operation.
        ambiguity_band = [
            row
            for row in candidates
            if top - int(row["score"]) < 3
        ]

        morphology_supported = [
            row
            for row in ambiguity_band
            if _job_morphology_score(
                str(row["incarnation"]),
                message,
            ) > 0
        ]

        if len(morphology_supported) == 1:
            winner = morphology_supported[0]
            return {
                "state": "RESOLVED",
                "incarnation": winner["incarnation"],
                "basis": "direct_job_morphology_tiebreak",
                "candidates": candidates,
                "authority_created": False,
            }

        return {
            "state": "NEEDS_YOU",
            "incarnation": None,
            "basis": "ambiguous_commercial_semantic_route",
            "candidates": candidates,
            "authority_created": False,
        }

    return {
        "state": "RESOLVED",
        "incarnation": candidates[0]["incarnation"],
        "basis": "commercial_semantic_fallback",
        "candidates": candidates,
        "authority_created": False,
    }


def _tier_hint(message: str) -> str | None:
    text = str(message or "").casefold()

    # Negative scope statements must not become positive buyer-class
    # evidence merely because they contain words such as "department"
    # or "team".
    negated_scope_phrases = (
        "not a department",
        "not the department",
        "not my department",
        "not our department",
        "not for a department",
        "not for the department",
        "not a team",
        "not the team",
        "not my team",
        "not our team",
        "not for a team",
        "not for the team",
        "not a school",
        "not the school",
        "not my school",
        "not our school",
        "not for a school",
        "not for the school",
        "not a company",
        "not the company",
        "not my company",
        "not our company",
        "not for a company",
        "not for the company",
        "not an organisation",
        "not an organization",
        "not for an organisation",
        "not for an organization",
        "not an enterprise",
        "not enterprise",
        "not for an enterprise",
    )

    positive_text = text
    for phrase in negated_scope_phrases:
        positive_text = positive_text.replace(phrase, " ")

    enterprise = (
        "enterprise",
        "institution-wide",
        "company-wide",
        "programme",
        "program-wide",
        "regulated organisation",
        "regulated organization",
    )
    team = (
        "team",
        "department",
        "small business",
        "organisation",
        "organization",
        "school",
        "company",
    )
    individual = (
        "individual",
        "freelancer",
        "solo",
        "myself",
        "personal",
        "just me",
        "only me",
        "for myself",
        "by myself",
        "on my own",
    )

    # Organisation scope still outranks incidental personal wording when
    # the customer explicitly says the work is for a team or institution.
    if any(x in positive_text for x in enterprise):
        return "enterprise_programme"
    if any(x in positive_text for x in team):
        return "team_department"
    if any(x in text for x in individual):
        return "individual_professional"

    return None


def resolve_commercial_cognition(
    root: Path,
    message: str,
    *,
    incarnation_hint: str | None = None,
    context_tier_hint: str | None = None,
) -> dict[str, Any]:
    root = Path(root)

    # Commercial cognition owns free-text product diagnosis.
    #
    # The legacy web router remains authoritative only when the caller
    # supplies an explicit canonical product/site context. For ordinary
    # customer language, the richer commercial resolver must decide,
    # because it includes pricing semantics and job morphology.
    if incarnation_hint:
        route = resolve_incarnation(
            message,
            incarnation_hint=incarnation_hint,
        )
    else:
        route = _fallback_route(message, root)

    if route.get("state") != "RESOLVED":
        return {
            "schema": "dio.vesper.commercial_cognition.v1",
            "state": "NEEDS_CLARIFICATION",
            "route": route,
            "product": None,
            "pricing": None,
            "authority_created": False,
            "external_effects": False,
        }

    name = str(route["incarnation"])
    pricing_by_name = _pricing_rows(root)

    if name not in pricing_by_name:
        raise ValueError(
            f"resolved canonical product lacks pricing truth: {name}"
        )

    price = pricing_by_name[name]
    marketing = semantic_marketing_brief(name)

    tiers = [
        dict(row)
        for row in price.get("commercial_tiers") or []
        if row.get("available") is True
    ]

    explicit_tier_hint = _tier_hint(message)

    context_tier_hint = (
        str(context_tier_hint or "").strip()
        or None
    )

    requested_tier = (
        explicit_tier_hint
        or context_tier_hint
    )

    selected_tier = next(
        (
            row for row in tiers
            if row.get("tier_id") == requested_tier
        ),
        None,
    )

    if explicit_tier_hint and selected_tier:
        tier_basis = "EXPLICIT_MESSAGE"
    elif context_tier_hint and selected_tier:
        tier_basis = "CONVERSATION_CONTEXT"
    else:
        tier_basis = "NONE"

    tier_state = (
        "SELECTED"
        if selected_tier
        else "NEEDS_CONTEXT"
    )

    return {
        "schema": "dio.vesper.commercial_cognition.v1",
        "state": "RESOLVED",
        "route": route,
        "product": {
            "product_id": price["product_id"],
            "name": name,
            "suite": price.get("suite"),
            "primary_family": price.get("primary_family"),
            "primary_scope_unit": price.get("primary_scope_unit"),
            "marketing_brief": marketing.get("brief") or {},
        },
        "pricing": {
            "currency": "ZAR",
            "reference_band_zar": dict(
                price["reference_band_zar"]
            ),
            "pricing_model": price.get("pricing_model"),
            "pricing_state": price.get("pricing_state"),
            "commercial_validation": price.get(
                "commercial_validation"
            ),
            "tiers": tiers,
            "tier_state": tier_state,
            "requested_tier": requested_tier,
            "tier_basis": tier_basis,
            "selected_tier": selected_tier,
            "quote_authority": dict(
                price.get("quote_authority") or {}
            ),
            "truth_boundary": (
                "Governed reference pricing, not proven "
                "willingness to pay or an issued quote."
            ),
        },
        "authority_created": False,
        "external_effects": False,
    }
