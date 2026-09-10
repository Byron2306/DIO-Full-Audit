from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .sources import CapitalSource


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def _split_pipe(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split("|") if item.strip()]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _stable_id(prefix: str, value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20].upper()}"


def _load_domain_rows(root: Path) -> dict[str, dict[str, str]]:
    path = Path(root) / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            domain_id = str(row.get("domain_id") or "").strip()
            if domain_id:
                rows[domain_id] = {key: str(value or "").strip() for key, value in row.items()}
    return rows


def _load_product_rows(root: Path) -> dict[str, dict[str, Any]]:
    path = Path(root) / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
    products: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            incarnation = str(raw.get("incarnation") or "").strip()
            if not incarnation:
                continue
            product_id = _slug(incarnation)
            products[product_id] = {
                "product_id": product_id,
                "incarnation": incarnation,
                "suite": str(raw.get("suite") or "").strip(),
                "primary_family": str(raw.get("primary_family") or "").strip(),
                "domain_ids": _split_pipe(raw.get("atlas_domain_ids")),
                "work_pattern_ids": _split_pipe(raw.get("canonical_work_pattern_ids")),
                "candidate_work_pattern_ids": _split_pipe(raw.get("candidate_work_pattern_ids")),
                "maturity": str(raw.get("source_maturity") or "").strip(),
                "execution_truth_class": str(raw.get("execution_truth_class") or "").strip(),
            }

    receipt_candidates = (
        Path(root) / "state" / "product_grade" / "canon_extension_aggregate" / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json",
        Path(root) / "state" / "product_grade" / "canon_extensions" / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json",
    )
    for receipt_path in receipt_candidates:
        if not receipt_path.is_file():
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        extensions = receipt.get("extensions") if isinstance(receipt, dict) else None
        if not isinstance(extensions, dict):
            continue
        for key, raw in extensions.items():
            if not isinstance(raw, dict):
                continue
            identity = str(raw.get("slug") or key or "").strip()
            canon_id = str(raw.get("canon_id") or "").strip()
            name = str(raw.get("name") or identity).strip()
            if not identity or not canon_id:
                continue
            product_id = _slug(identity)
            products.setdefault(product_id, {
                "product_id": product_id,
                "incarnation": name,
                "suite": "Canon Extensions",
                "primary_family": "Canon Extension",
                "domain_ids": [],
                "work_pattern_ids": [],
                "candidate_work_pattern_ids": [],
                "maturity": str(raw.get("status") or "ProductGrade verified"),
                "execution_truth_class": "CANON_EXTENSION_PRODUCT_GRADE_VERIFIED",
                "canon_id": canon_id,
            })
        break
    return products


def _ai_profile() -> dict[str, list[str]]:
    return {
        "capital_types": ["INVESTOR", "SPONSOR", "ACCELERATOR", "PRIZE"],
        "capital_archetypes": ["venture_capital", "corporate_venture", "responsible_ai_fund", "regtech_investor", "ai_accelerator"],
        "impact_themes": ["responsible_ai", "digital_trust", "governance", "enterprise_risk", "technology_infrastructure"],
        "query_families": ["FUND_THESIS", "PORTFOLIO_SIMILARITY", "RECENT_FUND_SIGNAL", "ACCELERATOR_CALL", "INNOVATION_PRIZE", "PUBLIC_ROUTE"],
        "source_class_preferences": ["INVESTOR_ECOSYSTEM", "FIRST_PARTY_PROGRAMME", "OPEN_FUNDING_DATA"],
    }


def _capital_profile(product: dict[str, Any], domain_rows: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    suite = str(product.get("suite") or "").casefold()
    family = str(product.get("primary_family") or "").casefold()
    domain_text = " ".join(
        str(domain_rows.get(domain_id, {}).get("domain_name") or "").casefold()
        for domain_id in product.get("domain_ids") or []
    )
    haystack = f"{suite} {family} {domain_text} {str(product.get('incarnation') or '').casefold()}"

    # Canonical suite identity has stronger semantic weight than incidental domain vocabulary.
    if "ai & digital trust" in suite:
        return _ai_profile()
    if any(token in haystack for token in ("education", "learning", "assessment", "teacher", "academic", "curriculum")):
        return {
            "capital_types": ["GRANT", "DONOR", "SPONSOR", "PATRONAGE", "ACCELERATOR", "PRIZE"],
            "capital_archetypes": ["education_foundation", "research_funder", "impact_grantmaker", "education_csr", "edtech_accelerator"],
            "impact_themes": ["education", "learning", "teacher_development", "digital_inclusion", "public_benefit"],
            "query_families": ["CURRENT_CALL", "FOUNDATION_MISSION", "HISTORICAL_AWARD", "PROGRAMME_ELIGIBILITY", "IMPACT_PORTFOLIO", "PUBLIC_ROUTE"],
            "source_class_preferences": ["PHILANTHROPY", "OPEN_FUNDING_DATA", "FIRST_PARTY_PROGRAMME", "PATRONAGE"],
        }
    if any(token in haystack for token in ("ai", "digital trust", "cyber", "authority", "assurance", "regops", "regulatory")):
        return _ai_profile()
    if any(token in haystack for token in ("evidence", "audit", "compliance", "quality", "proof")):
        return {
            "capital_types": ["INVESTOR", "SPONSOR", "ACCELERATOR", "PRIZE", "GRANT"],
            "capital_archetypes": ["regtech_investor", "enterprise_innovation_fund", "quality_infrastructure_programme", "technology_accelerator"],
            "impact_themes": ["evidence", "assurance", "compliance", "quality", "trust"],
            "query_families": ["FUND_THESIS", "INNOVATION_PROGRAMME", "HISTORICAL_AWARD", "PORTFOLIO_SIMILARITY", "PUBLIC_ROUTE"],
            "source_class_preferences": ["INVESTOR_ECOSYSTEM", "OPEN_FUNDING_DATA", "FIRST_PARTY_PROGRAMME"],
        }
    if any(token in haystack for token in ("document", "publish", "accessib", "presence", "media", "market")):
        return {
            "capital_types": ["INVESTOR", "SPONSOR", "PATRONAGE", "ACCELERATOR", "PRIZE", "GRANT"],
            "capital_archetypes": ["creator_technology_fund", "accessibility_funder", "media_innovation_programme", "open_technology_patron"],
            "impact_themes": ["accessibility", "publishing", "digital_inclusion", "market_access", "open_tools"],
            "query_families": ["INNOVATION_PROGRAMME", "PATRONAGE_PROGRAMME", "ACCESSIBILITY_GRANT", "PORTFOLIO_SIMILARITY", "PUBLIC_ROUTE"],
            "source_class_preferences": ["PATRONAGE", "OPEN_FUNDING_DATA", "FIRST_PARTY_PROGRAMME", "INVESTOR_ECOSYSTEM"],
        }
    if any(token in haystack for token in ("public", "programme", "grant", "donor", "government")):
        return {
            "capital_types": ["GRANT", "DONOR", "SPONSOR", "PRIZE", "ACCELERATOR"],
            "capital_archetypes": ["government_programme", "development_funder", "foundation", "challenge_fund"],
            "impact_themes": ["public_benefit", "programme_delivery", "governance", "development"],
            "query_families": ["CURRENT_CALL", "PROGRAMME_ELIGIBILITY", "HISTORICAL_AWARD", "FOUNDATION_MISSION", "PUBLIC_ROUTE"],
            "source_class_preferences": ["OPEN_FUNDING_DATA", "FIRST_PARTY_PROGRAMME", "PHILANTHROPY"],
        }
    return {
        "capital_types": ["INVESTOR", "GRANT", "SPONSOR", "ACCELERATOR", "PRIZE"],
        "capital_archetypes": ["sector_fund", "innovation_programme", "strategic_sponsor"],
        "impact_themes": ["innovation", "productivity"],
        "query_families": ["FUND_THESIS", "CURRENT_CALL", "HISTORICAL_AWARD", "PUBLIC_ROUTE"],
        "source_class_preferences": ["FIRST_PARTY_PROGRAMME", "OPEN_FUNDING_DATA", "INVESTOR_ECOSYSTEM"],
    }


def build_search_signature(root: Path, product_ids: list[str]) -> dict[str, Any]:
    root = Path(root)
    products = _load_product_rows(root)
    domains = _load_domain_rows(root)
    requested = [_slug(value) for value in product_ids if str(value or "").strip()]
    if not requested:
        raise ValueError("At least one canonical product id is required")

    records: list[dict[str, Any]] = []
    for product_id in requested:
        if product_id not in products:
            raise KeyError(f"Unknown canonical DIO product: {product_id}")
        records.append(products[product_id])

    domain_ids = _dedupe(domain_id for row in records for domain_id in row.get("domain_ids") or [])
    work_patterns = _dedupe(work for row in records for work in row.get("work_pattern_ids") or [])
    domain_families = _dedupe(domains.get(domain_id, {}).get("domain_family", "") for domain_id in domain_ids)
    domain_names = _dedupe(domains.get(domain_id, {}).get("domain_name", "") for domain_id in domain_ids)

    profiles = [_capital_profile(record, domains) for record in records]
    capital_types = _dedupe(item for profile in profiles for item in profile["capital_types"])
    capital_archetypes = _dedupe(item for profile in profiles for item in profile["capital_archetypes"])
    impact_themes = _dedupe(item for profile in profiles for item in profile["impact_themes"])
    query_families = _dedupe(item for profile in profiles for item in profile["query_families"])
    source_preferences = _dedupe(item for profile in profiles for item in profile["source_class_preferences"])

    proof_assets = _dedupe(
        f"portfolio:{record['product_id']}:{record['execution_truth_class']}"
        for record in records
        if record.get("execution_truth_class")
    )
    maturity = _dedupe(record.get("maturity", "") for record in records)
    funding_use_cases = _dedupe(
        ["product_development", "commercialisation", "research_and_validation"]
        + (["public_benefit_delivery"] if any(item in capital_types for item in ("GRANT", "DONOR")) else [])
    )
    signature_basis = {
        "products": requested,
        "domains": domain_ids,
        "work_patterns": work_patterns,
        "capital_types": capital_types,
        "query_families": query_families,
    }
    return {
        "schema": "dio.atlas.capital_search_signature.v1",
        "signature_id": _stable_id("CSS", signature_basis),
        "canonical_product_ids": requested,
        "canonical_proof_assets": proof_assets,
        "product_records": records,
        "domain_ids": domain_ids,
        "domain_families": domain_families,
        "domain_names": domain_names,
        "work_pattern_ids": work_patterns,
        "artifact_classes": _dedupe(
            value
            for domain_id in domain_ids
            for value in _split_pipe(domains.get(domain_id, {}).get("default_artifact_classes"))
        ),
        "impact_themes": impact_themes,
        "beneficiary_archetypes": impact_themes,
        "organisation_archetypes": capital_archetypes,
        "capital_types": capital_types,
        "capital_archetypes": capital_archetypes,
        "geography_weights": [
            {"region": "ZA", "weight": 1.0},
            {"region": "AFRICA", "weight": 0.9},
            {"region": "GLOBAL", "weight": 0.7},
        ],
        "maturity_stage": maturity,
        "funding_use_cases": funding_use_cases,
        "constraint_classes": _dedupe(
            value
            for domain_id in domain_ids
            for value in _split_pipe(domains.get(domain_id, {}).get("default_constraint_classes"))
        ),
        "professional_authority_required": any(
            domains.get(domain_id, {}).get("professional_authority_required", "").casefold() == "true"
            for domain_id in domain_ids
        ),
        "query_families": query_families,
        "source_class_preferences": source_preferences,
        "truth_class": "STRATEGIC_SEARCH_MODEL_OUTPUT",
        "market_demand": False,
        "authority_created": False,
        "external_effects": False,
    }


def compile_discovery_plan(
    signatures: list[dict[str, Any]],
    source_registry: dict[str, CapitalSource],
    cycle_budget: int,
) -> dict[str, Any]:
    budget = max(0, int(cycle_budget))
    novelty_budget = max(1, budget // 5) if budget else 0
    reverification_budget = max(1, budget // 5) if budget >= 2 else 0
    discovery_budget = max(0, budget - novelty_budget - reverification_budget)

    preferred_classes = _dedupe(
        source_class
        for signature in signatures
        for source_class in signature.get("source_class_preferences") or []
    )
    query_families = _dedupe(
        family for signature in signatures for family in signature.get("query_families") or []
    )
    capital_types = _dedupe(
        capital_type for signature in signatures for capital_type in signature.get("capital_types") or []
    )
    domain_targets = _dedupe(
        domain_id for signature in signatures for domain_id in signature.get("domain_ids") or []
    )

    candidates = [
        source
        for source in source_registry.values()
        if source.status == "READY" and source.source_class in preferred_classes
    ]
    candidates.sort(key=lambda source: (source.access_mode == "INTERNAL", preferred_classes.index(source.source_class), source.source_id))

    allocations: list[dict[str, Any]] = []
    remaining = discovery_budget
    while candidates and remaining > 0:
        progressed = False
        for source in candidates:
            if remaining <= 0:
                break
            existing = next((item for item in allocations if item["source_id"] == source.source_id), None)
            used = int(existing["budget"]) if existing else 0
            cap = source.rate_budget if source.rate_budget > 0 else remaining
            if used >= cap:
                continue
            if existing is None:
                existing = {
                    "source_id": source.source_id,
                    "source_class": source.source_class,
                    "access_mode": source.access_mode,
                    "budget": 0,
                    "reason": "ATLAS_SOURCE_CLASS_PREFERENCE",
                }
                allocations.append(existing)
            existing["budget"] += 1
            remaining -= 1
            progressed = True
        if not progressed:
            break

    plan_basis = {
        "signatures": [signature.get("signature_id") for signature in signatures],
        "cycle_budget": budget,
        "allocations": allocations,
        "queries": query_families,
    }
    return {
        "schema": "dio.atlas.capital_discovery_plan.v1",
        "cycle_id": _stable_id("CDP", plan_basis),
        "search_signature_ids": [str(signature.get("signature_id") or "") for signature in signatures],
        "query_families": query_families,
        "source_allocations": allocations,
        "capital_type_targets": capital_types,
        "geography_weights": [
            {"region": "ZA", "weight": 1.0},
            {"region": "AFRICA", "weight": 0.9},
            {"region": "GLOBAL", "weight": 0.7},
        ],
        "domain_coverage_targets": domain_targets,
        "cycle_budget": budget,
        "discovery_budget": discovery_budget,
        "novelty_budget": novelty_budget,
        "reverification_budget": reverification_budget,
        "unallocated_budget": remaining,
        "truth_class": "STRATEGIC_SEARCH_MODEL_OUTPUT",
        "authority_created": False,
        "external_effects": False,
    }
