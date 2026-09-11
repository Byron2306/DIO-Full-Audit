from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .models import validate_opportunity_type


DOMAIN_RULES: tuple[dict[str, Any], ...] = (
    {
        "keywords": {"education", "oer", "teacher", "teacher development", "digital learning", "sdg4", "learning", "edtech"},
        "primary_products": ["HOMS Learning Studio", "HOMS Curriculum", "Sophia Tutor"],
        "secondary_products": ["ImpactProof", "GrantProof", "ProgrammeProof"],
        "proof_bundle": ["Prosper", "GREAT", "OER outputs", "published education/game-based-learning outputs"],
        "pitch_family": "EDUCATION_OER_PUBLIC_GOOD",
        "funding_modes": ["GRANT", "DONOR", "SPONSOR", "PATRONAGE", "ACCELERATOR", "PRIZE"],
        "search_archetypes": [
            "education foundations",
            "SDG4 programmes",
            "teacher-development donors",
            "edtech philanthropy",
            "African education innovation funds",
            "corporate education sponsors",
        ],
    },
    {
        "keywords": {"ai governance", "enterprise ai", "regtech", "governed ai", "responsible ai", "ai assurance", "agent governance", "ai infrastructure"},
        "primary_products": ["DIO AI Assurance", "Agent Authority", "ModelProof", "ReleaseProof"],
        "secondary_products": ["CriticalAI Assurance", "AI IncidentRoom", "DIO RegOps"],
        "proof_bundle": ["T1-T25 governed-engineering proof stack", "ProductGrade receipts", "GoldenEye/Sensorium authority-wall evidence"],
        "pitch_family": "GOVERNED_AI_INFRASTRUCTURE",
        "funding_modes": ["INVESTOR", "SPONSOR", "ACCELERATOR", "PRIZE"],
        "search_archetypes": [
            "responsible AI investors",
            "AI governance venture funds",
            "enterprise AI infrastructure investors",
            "regtech investors",
            "AI safety accelerators",
            "governed AI innovation prizes",
        ],
    },
    {
        "keywords": {"compliance", "audit", "assurance", "trust", "evidence", "governance", "regulatory"},
        "primary_products": ["Evidex EvidenceOps", "AuditProof", "DIO AI Assurance", "DIO RegOps"],
        "secondary_products": ["AssuranceRoom", "DiligenceRoom", "PolicyProof"],
        "proof_bundle": ["Evidex proof receipts", "ProductGrade evidence", "authority-bound workflow demonstrations"],
        "pitch_family": "EVIDENCE_FIRST_TRUST_REGTECH",
        "funding_modes": ["INVESTOR", "SPONSOR", "ACCELERATOR", "PRIZE"],
        "search_archetypes": [
            "regtech funds",
            "digital trust investors",
            "compliance technology accelerators",
            "enterprise assurance sponsors",
        ],
    },
    {
        "keywords": {"open source", "open research", "public resource", "creator", "community", "open education"},
        "primary_products": ["Vesper Desk", "Article Publication Studio", "Site Studio"],
        "secondary_products": ["HOMS Learning Studio", "Report & Pitch Studio", "ImpactProof"],
        "proof_bundle": ["public DIO build record", "open educational resources", "research and publication outputs"],
        "pitch_family": "OPEN_RESEARCH_AND_PUBLIC_RESOURCE",
        "funding_modes": ["PATRONAGE", "DONOR", "SPONSOR", "GRANT"],
        "search_archetypes": [
            "open-source patrons",
            "open research foundations",
            "creator technology patrons",
            "community-supported AI projects",
        ],
    },
)

TYPE_DEFAULTS: dict[str, dict[str, Any]] = {
    "INVESTOR": {
        "primary_products": ["DIO AI Assurance", "Agent Authority", "Evidex EvidenceOps", "Opportunity Foundry"],
        "secondary_products": ["Market Radar", "DiligenceRoom"],
        "pitch_family": "PRODUCT_FACTORY_VENTURE_OS",
        "funding_modes": ["INVESTOR"],
        "proof_bundle": ["68-product governed portfolio census", "ProductGrade engineering receipts", "T1-T25 proof stack"],
    },
    "GRANT": {
        "primary_products": ["GrantProof", "ImpactProof", "ProgrammeProof"],
        "secondary_products": ["Report & Pitch Studio"],
        "pitch_family": "OPEN_RESEARCH_AND_PUBLIC_RESOURCE",
        "funding_modes": ["GRANT"],
        "proof_bundle": ["governed evidence workflows", "research/public-benefit outputs"],
    },
    "DONOR": {
        "primary_products": ["ImpactProof", "ProgrammeProof", "GrantProof"],
        "secondary_products": ["DonorProof"],
        "pitch_family": "EDUCATION_OER_PUBLIC_GOOD",
        "funding_modes": ["DONOR"],
        "proof_bundle": ["impact evidence", "public-benefit outputs"],
    },
    "SPONSOR": {
        "primary_products": ["Launch Studio", "Report & Pitch Studio", "ImpactProof"],
        "secondary_products": ["Campaign Lab"],
        "pitch_family": "STRATEGIC_ECOSYSTEM_SPONSORSHIP",
        "funding_modes": ["SPONSOR"],
        "proof_bundle": ["portfolio demonstrations", "audience-facing public outputs"],
    },
    "PATRONAGE": {
        "primary_products": ["Vesper Desk", "Site Studio", "Article Publication Studio"],
        "secondary_products": ["HOMS Learning Studio"],
        "pitch_family": "CREATOR_BUILD_JOURNEY",
        "funding_modes": ["PATRONAGE"],
        "proof_bundle": ["public DIO build journey", "open resources", "research/demo outputs"],
    },
    "ACCELERATOR": {
        "primary_products": ["EntrepreneurProof", "Corporate Readiness", "InvestorProof"],
        "secondary_products": ["Report & Pitch Studio"],
        "pitch_family": "PRODUCT_FACTORY_VENTURE_OS",
        "funding_modes": ["ACCELERATOR"],
        "proof_bundle": ["68-product portfolio", "ProductGrade receipts", "commercial spine"],
    },
    "PRIZE": {
        "primary_products": ["ImpactProof", "EntrepreneurProof", "Report & Pitch Studio"],
        "secondary_products": ["Launch Studio"],
        "pitch_family": "INNOVATION_PROOF",
        "funding_modes": ["PRIZE"],
        "proof_bundle": ["ProductGrade receipts", "published/research outputs", "innovation awards/proof where evidenced"],
    },
}


def _terms(opportunity: dict[str, Any]) -> set[str]:
    values: list[str] = []
    for field in ("domains", "criteria", "themes", "sector_tags"):
        raw = opportunity.get(field) or []
        if isinstance(raw, str):
            raw = [raw]
        values.extend(str(item or "") for item in raw)
    # Live public sources often expose domain evidence in prose rather than
    # pre-normalized tags. Treat observed descriptive text as evidence input,
    # not as a claim of fit or funding intent.
    for field in ("title", "description", "objective", "programme", "program"):
        text = str(opportunity.get(field) or "").strip()
        if text:
            values.append(text)
    joined = " ".join(values).casefold()
    terms = {item.strip().casefold() for item in values if str(item or "").strip()}
    terms.update(token for token in joined.replace("/", " ").replace("-", " ").split() if token)
    return terms


def _rule_score(rule: dict[str, Any], terms: set[str]) -> int:
    haystack = " ".join(sorted(terms))
    return sum(1 for keyword in rule["keywords"] if keyword in terms or keyword in haystack)


def _canonical_atlas_domain_matches(root: Path, terms: set[str], limit: int = 8) -> list[dict[str, str]]:
    path = Path(root) / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
    if not path.is_file() or not terms:
        return []
    haystack = " ".join(sorted(terms))
    matches: list[dict[str, str]] = []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                name = str(row.get("domain_name") or "").strip()
                if not name:
                    continue
                words = [w for w in name.casefold().replace("and", " ").split() if len(w) > 3]
                if any(word in haystack for word in words):
                    matches.append({"domain_id": str(row.get("domain_id") or ""), "domain_name": name})
                    if len(matches) >= limit:
                        break
    except OSError:
        return []
    return matches


def _dedupe(values: list[str], limit: int | None = None) -> list[str]:
    out: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in out:
            out.append(item)
        if limit is not None and len(out) >= limit:
            break
    return out


def build_capital_support_fit(root: Path, opportunity: dict[str, Any]) -> dict[str, Any]:
    opportunity_type = validate_opportunity_type(str(opportunity.get("opportunity_type") or ""))
    terms = _terms(opportunity)
    scored = sorted(((_rule_score(rule, terms), rule) for rule in DOMAIN_RULES), key=lambda item: item[0], reverse=True)
    matching = [rule for score, rule in scored if score > 0]
    default = TYPE_DEFAULTS[opportunity_type]

    primary: list[str] = []
    secondary: list[str] = []
    proof: list[str] = []
    funding_modes: list[str] = []
    search_archetypes: list[str] = []
    pitch_family = str(default["pitch_family"])

    if matching:
        lead = matching[0]
        pitch_family = str(lead["pitch_family"])
        for rule in matching[:2]:
            primary.extend(rule["primary_products"])
            secondary.extend(rule["secondary_products"])
            proof.extend(rule["proof_bundle"])
            funding_modes.extend(rule["funding_modes"])
            search_archetypes.extend(rule["search_archetypes"])
    else:
        primary.extend(default["primary_products"])
        secondary.extend(default["secondary_products"])
        proof.extend(default["proof_bundle"])
        funding_modes.extend(default["funding_modes"])

    # Preserve the target's actual mechanism even when a domain rule suggests adjacent modes.
    funding_modes.insert(0, opportunity_type)
    primary = _dedupe(primary + list(default["primary_products"]), 6)
    secondary = _dedupe(secondary + list(default["secondary_products"]), 6)
    proof = _dedupe(proof + list(default["proof_bundle"]), 8)
    funding_modes = _dedupe(funding_modes, 7)

    return {
        "schema": "dio.atlas.capital_support_fit.v1",
        "opportunity_id": str(opportunity.get("opportunity_id") or ""),
        "target_type": opportunity_type,
        "domains": list(opportunity.get("domains") or []),
        "atlas_domain_matches": _canonical_atlas_domain_matches(Path(root), terms),
        "primary_products": primary,
        "secondary_products": secondary,
        "funding_modes": funding_modes,
        "proof_bundle": proof,
        "recommended_pitch_family": pitch_family,
        "search_expansion": _dedupe(search_archetypes, 12),
        "fit_score": min(100, 45 + (12 * len(matching)) + min(25, 3 * len(terms))),
        "truth_class": "STRATEGIC_FIT_MODEL_OUTPUT",
        "market_demand": False,
        "willingness_to_fund": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }


def adjacent_search_suggestions(fit: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    target_type = str(fit.get("target_type") or "")
    pitch = str(fit.get("recommended_pitch_family") or "")
    suggestions: list[dict[str, Any]] = []
    for query in list(fit.get("search_expansion") or [])[: max(0, int(limit))]:
        suggestions.append({
            "schema": "dio.atlas.capital_support_search_expansion.v1",
            "query": str(query),
            "source_opportunity_id": fit.get("opportunity_id"),
            "target_type_context": target_type,
            "pitch_family_context": pitch,
            "truth_class": "STRATEGIC_FIT_MODEL_OUTPUT",
            "contact_authority": False,
            "authority_created": False,
        })
    if not suggestions and target_type:
        suggestions.append({
            "schema": "dio.atlas.capital_support_search_expansion.v1",
            "query": f"{target_type.casefold()} opportunities {pitch.replace('_', ' ').casefold()}".strip(),
            "source_opportunity_id": fit.get("opportunity_id"),
            "target_type_context": target_type,
            "pitch_family_context": pitch,
            "truth_class": "STRATEGIC_FIT_MODEL_OUTPUT",
            "contact_authority": False,
            "authority_created": False,
        })
    return suggestions[: max(0, int(limit))]
