from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


BUYER_CLASS_LABELS = {
    "C0": "personal",
    "C1": "professional",
    "C2": "small_business",
    "C3": "departmental",
    "C4": "enterprise_institutional",
    "C5": "industrial_regulated_programme",
}

COMMERCIAL_TIER_POLICY: tuple[dict[str, Any], ...] = (
    {
        "tier_id": "individual_professional",
        "label": "Individual / Professional",
        "buyer_classes": ("C0", "C1"),
        "reference_position": 0.0,
    },
    {
        "tier_id": "team_department",
        "label": "Team / Department",
        "buyer_classes": ("C2", "C3"),
        "reference_position": 0.5,
    },
    {
        "tier_id": "enterprise_programme",
        "label": "Enterprise / Programme",
        "buyer_classes": ("C4", "C5"),
        "reference_position": 1.0,
    },
)


def _tier_reference_amount(low: int, high: int, position: float) -> int:
    if position <= 0:
        return int(low)
    if position >= 1:
        return int(high)
    value = low + ((high - low) * position)
    rounded = int(round(value / 50.0) * 50)
    return max(int(low), min(int(high), rounded))


def _commercial_tiers(rule: dict[str, Any]) -> list[dict[str, Any]]:
    buyer_classes = set(rule["buyer_classes"])
    band = dict(rule["reference_band_zar"])
    low = int(band["min"])
    high = int(band["max"])
    tiers: list[dict[str, Any]] = []
    for definition in COMMERCIAL_TIER_POLICY:
        tier_classes = list(definition["buyer_classes"])
        eligible = [code for code in tier_classes if code in buyer_classes]
        available = bool(eligible)
        tiers.append({
            "tier_id": definition["tier_id"],
            "label": definition["label"],
            "buyer_classes": tier_classes,
            "eligible_buyer_classes": eligible,
            "buyer_class_labels": [BUYER_CLASS_LABELS[code] for code in eligible],
            "available": available,
            "reference_amount_zar": (
                _tier_reference_amount(low, high, float(definition["reference_position"]))
                if available
                else None
            ),
            "pricing_truth": "GOVERNED_REFERENCE_POINT",
            "market_validation": "UNPROVED",
            "quote_issue_authority": False,
            "invoice_issue_authority": False,
            "band_mutation_authority": False,
            "external_effects": False,
        })
    return tiers


def _rule(
    buyer_classes: str,
    primary_scope_unit: str,
    secondary_scope_units: str,
    pricing_model: str,
    low: int,
    high: int,
    enterprise_mode: str,
    autonomous_ceiling: int,
    industrial: bool = False,
) -> dict[str, Any]:
    return {
        "buyer_classes": buyer_classes.split(),
        "primary_scope_unit": primary_scope_unit,
        "secondary_scope_units": [x for x in secondary_scope_units.split() if x],
        "pricing_model": pricing_model,
        "reference_band_zar": {"min": int(low), "max": int(high)},
        "enterprise_pricing": {"mode": enterprise_mode, "naive_unit_multiplication": False},
        "autonomous_quote_ceiling_zar": int(autonomous_ceiling),
        "industrial_scale_supported": bool(industrial),
    }


PROFILE_RULES: dict[str, dict[str, Any]] = {
    "HOMS Assess": _rule("C0 C1 C2 C3 C4", "learner_script", "assessment rubric learner", "batch", 350, 1800, "license_plus_usage", 1800),
    "HOMS Exam": _rule("C0 C1 C2 C3 C4", "assessment_package", "grade subject source_item", "package", 900, 3500, "license_plus_usage", 3500),
    "HOMS Moderate": _rule("C1 C2 C3 C4", "assessment_batch", "learner reviewer", "batch_review", 750, 2500, "setup_plus_usage", 2500),
    "HOMS Curriculum": _rule("C1 C2 C3 C4 C5", "curriculum_unit", "grade subject outcome", "project", 1500, 7500, "programme", 3500, True),
    "HOMS Learning Studio": _rule("C0 C1 C2 C3 C4", "topic_pack", "grade asset assessment", "package", 950, 4500, "license_plus_usage", 3000),
    "HOMS Accreditation": _rule("C2 C3 C4 C5", "accreditation_requirement", "evidence_item programme standard", "setup_plus_volume", 5000, 30000, "programme", 7500, True),
    "Sophia Review": _rule("C0 C1 C2 C3 C4", "manuscript_page", "reference claim source", "document_scope", 450, 1500, "setup_plus_usage", 1500),
    "Sophia Research": _rule("C0 C1 C2 C3 C4", "source_item", "claim reference research_question", "research_scope", 750, 3000, "setup_plus_usage", 2500),
    "Sophia Supervisor": _rule("C0 C1 C2 C3", "research_milestone", "document feedback_cycle", "milestone", 500, 2000, "retainer_plus_volume", 2000),
    "Sophia Integrity": _rule("C0 C1 C2 C3 C4 C5", "manuscript_page", "reference claim section", "document_scope", 750, 3500, "setup_plus_volume", 3500, True),
    "Sophia Tutor": _rule("C0 C1 C2 C3", "learning_topic", "session activity", "session_pack", 250, 1200, "retainer_plus_volume", 1200),
    "VAMP Performance": _rule("C0 C1 C2 C3 C4 C5", "performance_evidence_item", "employee objective review_cycle", "evidence_pack", 500, 2500, "license_plus_usage", 2500, True),
    "PromotionProof": _rule("C0 C1 C2 C3 C4", "promotion_evidence_item", "employee criterion", "evidence_pack", 500, 2200, "setup_plus_usage", 2200),
    "CPDProof": _rule("C0 C1 C2 C3 C4", "cpd_record", "activity evidence_item", "evidence_pack", 350, 1800, "license_plus_usage", 1800),
    "ProjectProof": _rule("C1 C2 C3 C4", "project_evidence_item", "milestone obligation", "evidence_pack", 750, 3500, "retainer_plus_volume", 3000),
    "ImpactProof": _rule("C1 C2 C3 C4 C5", "outcome_evidence_item", "indicator beneficiary reporting_period", "setup_plus_volume", 950, 5000, "retainer_plus_volume", 3500, True),
    "Evidex EvidenceOps": _rule("C0 C1 C2 C3 C4 C5", "evidence_item", "document claim source", "setup_plus_volume", 350, 5000, "setup_plus_volume", 5000, True),
    "AuditProof": _rule("C1 C2 C3 C4 C5", "control_evidence_item", "control finding period", "setup_plus_volume", 1500, 7500, "retainer_plus_volume", 3500, True),
    "VendorProof": _rule("C1 C2 C3 C4 C5", "vendor_record", "evidence_item requirement", "per_vendor_plus_setup", 1500, 7500, "setup_plus_volume", 3500, True),
    "TenderProof": _rule("C1 C2 C3 C4", "tender_requirement", "document deadline mandatory_gate", "package", 1200, 6000, "programme", 3500),
    "GrantProof": _rule("C0 C1 C2 C3 C4", "grant_requirement", "indicator evidence_item reporting_period", "package", 900, 4500, "retainer_plus_volume", 3500),
    "DonorProof": _rule("C1 C2 C3 C4 C5", "donor_evidence_item", "indicator reporting_period obligation", "setup_plus_volume", 1500, 7500, "retainer_plus_volume", 3500, True),
    "ProgrammeProof": _rule("C2 C3 C4 C5", "programme_indicator", "evidence_item reporting_period workstream", "programme", 3500, 15000, "retainer_plus_volume", 5000, True),
    "QualityProof": _rule("C2 C3 C4 C5", "quality_control", "evidence_item criterion", "setup_plus_volume", 3000, 15000, "programme", 5000, True),
    "CertificationProof": _rule("C2 C3 C4 C5", "certification_requirement", "evidence_item criterion", "setup_plus_volume", 4000, 20000, "programme", 5000, True),
    "PolicyProof": _rule("C1 C2 C3 C4", "policy_clause", "control requirement evidence_item", "document_scope", 1200, 5000, "programme", 3000),
    "ContractProof": _rule("C0 C1 C2 C3 C4", "contract_clause", "obligation evidence_item counterparty", "per_contract", 750, 3500, "setup_plus_usage", 3000),
    "DiligenceRoom": _rule("C2 C3 C4 C5", "diligence_document", "evidence_item question workstream", "setup_plus_volume", 5000, 30000, "programme", 7500, True),
    "AssuranceRoom": _rule("C2 C3 C4 C5", "assurance_control", "evidence_item finding review_cycle", "setup_plus_volume", 5000, 30000, "retainer_plus_volume", 7500, True),
    "DIO AI Assurance": _rule("C2 C3 C4 C5", "ai_system", "control evidence_item model", "assurance_programme", 7500, 40000, "programme", 7500, True),
    "ModelProof": _rule("C2 C3 C4 C5", "model", "evaluation evidence_item release", "per_model", 5000, 25000, "retainer_plus_volume", 7500, True),
    "Agent Authority": _rule("C2 C3 C4 C5", "agent", "authority_rule action_class capability", "governance_setup", 7500, 50000, "license_plus_usage", 7500, True),
    "ReleaseProof": _rule("C2 C3 C4 C5", "release", "control evidence_item model", "per_release", 4000, 20000, "retainer_plus_volume", 5000, True),
    "ChangeProof": _rule("C2 C3 C4 C5", "change_record", "evidence_item control", "per_change", 2500, 15000, "retainer_plus_volume", 5000, True),
    "AI IncidentRoom": _rule("C2 C3 C4 C5", "incident", "event evidence_item actor", "incident_case", 7500, 50000, "retainer_plus_volume", 7500, True),
    "CriticalAI Assurance": _rule("C3 C4 C5", "critical_ai_system", "control evidence_item authority", "assurance_programme", 15000, 100000, "programme", 10000, True),
    "CyberAssurance": _rule("C2 C3 C4 C5", "cyber_control", "evidence_item asset finding", "assurance_programme", 7500, 50000, "programme", 7500, True),
    "ControlDrift": _rule("C2 C3 C4 C5", "control_monitoring_cycle", "control evidence_item exception", "subscription", 5000, 30000, "retainer_plus_volume", 7500, True),
    "SupplierCyberProof": _rule("C2 C3 C4 C5", "supplier", "control evidence_item", "per_supplier_plus_setup", 5000, 30000, "setup_plus_volume", 7500, True),
    "IncidentProof": _rule("C2 C3 C4 C5", "incident", "evidence_item event finding", "incident_case", 5000, 30000, "retainer_plus_volume", 7500, True),
    "DORA Vendor Assurance": _rule("C3 C4 C5", "regulated_vendor", "control evidence_item service", "assurance_programme", 15000, 100000, "programme", 10000, True),
    "DIO RegOps": _rule("C2 C3 C4 C5", "regulatory_obligation", "control evidence_item jurisdiction", "regops_programme", 10000, 75000, "programme", 10000, True),
    "PermitProof": _rule("C1 C2 C3 C4 C5", "permit_requirement", "document evidence_item authority", "case_scope", 2000, 10000, "programme", 5000, True),
    "Document Studio Edit": _rule("C0 C1 C2 C3", "page", "document revision", "per_document", 150, 1200, "setup_plus_usage", 1200),
    "Document Studio Localize": _rule("C0 C1 C2 C3 C4", "word", "page language review", "usage", 350, 2500, "setup_plus_usage", 2500),
    "Document Studio Publish": _rule("C0 C1 C2 C3 C4", "output_document", "page format", "package", 250, 1800, "setup_plus_usage", 1800),
    "Accessible Publish": _rule("C1 C2 C3 C4", "page", "document accessibility_check", "document_scope", 500, 3000, "setup_plus_usage", 2500),
    "DossierOps": _rule("C1 C2 C3 C4", "dossier_item", "document evidence_item", "package", 1000, 5000, "setup_plus_volume", 3500),
    "Market Radar": _rule("C1 C2 C3 C4", "market_segment", "signal source competitor", "research_cycle", 500, 3000, "retainer_plus_volume", 2500),
    "Opportunity Foundry": _rule("C1 C2 C3 C4", "opportunity_scan", "market_segment source", "research_cycle", 750, 4000, "retainer_plus_volume", 3000),
    "Offer Lab": _rule("C1 C2 C3 C4", "offer_variant", "segment experiment", "experiment", 750, 3500, "retainer_plus_volume", 3000),
    "Campaign Lab": _rule("C1 C2 C3 C4", "campaign", "channel asset experiment", "experiment", 1000, 5000, "retainer_plus_volume", 3500),
    "Vesper Desk": _rule("C1 C2 C3 C4 C5", "customer_case", "conversation channel operator", "platform_service", 1000, 7500, "license_plus_usage", 3500, True),
    "Article Publication": _rule("C0 C1 C2 C3", "article_page", "source claim asset", "publication_package", 750, 3500, "setup_plus_usage", 3000),
    "Article Publication Studio": _rule("C1 C2 C3 C4", "publication_package", "article asset channel", "studio_project", 1500, 7500, "programme", 3500),
    "Contract Desk": _rule("C0 C1 C2 C3", "contract_clause", "obligation question", "per_contract", 750, 3500, "setup_plus_usage", 3000),
    "Corporate Readiness": _rule("C1 C2 C3 C4", "readiness_requirement", "document evidence_item", "readiness_pack", 1500, 7500, "programme", 3500),
    "EntrepreneurProof": _rule("C0 C1 C2 C3", "venture_claim", "evidence_item buyer_question", "readiness_pack", 500, 2500, "setup_plus_usage", 2500),
    "Finance Readiness": _rule("C0 C1 C2 C3", "finance_requirement", "document evidence_item", "readiness_pack", 750, 3500, "setup_plus_usage", 3000),
    "Finance Readiness Studio": _rule("C1 C2 C3 C4", "finance_pack", "requirement document scenario", "studio_project", 1500, 7500, "programme", 3500),
    "FundingFinder": _rule("C0 C1 C2 C3", "funding_opportunity", "eligibility criterion source", "research_pack", 350, 1800, "retainer_plus_volume", 1800),
    "InvestorProof": _rule("C0 C1 C2 C3", "investor_readiness_item", "claim evidence_item metric", "readiness_pack", 750, 3500, "setup_plus_usage", 3000),
    "Launch Studio": _rule("C1 C2 C3 C4", "launch_channel", "asset campaign audience", "studio_project", 1500, 7500, "programme", 3500),
    "POPIA Readiness": _rule("C1 C2 C3 C4 C5", "privacy_requirement", "control evidence_item data_process", "readiness_programme", 2500, 15000, "programme", 5000, True),
    "Professional Correspondence": _rule("C0 C1 C2", "correspondence_item", "fact attachment recipient", "per_item", 150, 750, "setup_plus_usage", 750),
    "Professional Correspondence Studio": _rule("C1 C2 C3 C4", "correspondence_pack", "correspondence_item attachment", "studio_project", 750, 3500, "setup_plus_usage", 3000),
    "Report & Pitch Studio": _rule("C0 C1 C2 C3 C4", "report_page", "claim evidence_item slide", "studio_project", 750, 5000, "programme", 3500),
    "Site Studio": _rule("C0 C1 C2 C3 C4", "site_page", "asset accessibility_check", "studio_project", 1500, 7500, "setup_plus_usage", 3500),
}

CANON_EXTENSION_META: tuple[tuple[str, str, str], ...] = (
    ("Article Publication", "Canon Extensions", "publication_professional"),
    ("Article Publication Studio", "Canon Extensions", "publication_professional"),
    ("Contract Desk", "Canon Extensions", "publication_professional"),
    ("Corporate Readiness", "Canon Extensions", "readiness_assurance"),
    ("EntrepreneurProof", "Canon Extensions", "opportunity_venture"),
    ("Finance Readiness", "Canon Extensions", "readiness_assurance"),
    ("Finance Readiness Studio", "Canon Extensions", "readiness_assurance"),
    ("FundingFinder", "Canon Extensions", "opportunity_venture"),
    ("InvestorProof", "Canon Extensions", "opportunity_venture"),
    ("Launch Studio", "Canon Extensions", "launch_orchestration"),
    ("POPIA Readiness", "Canon Extensions", "readiness_assurance"),
    ("Professional Correspondence", "Canon Extensions", "publication_professional"),
    ("Professional Correspondence Studio", "Canon Extensions", "publication_professional"),
    ("Report & Pitch Studio", "Canon Extensions", "publication_professional"),
    ("Site Studio", "Canon Extensions", "publication_professional"),
)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _historical_rows(root: Path) -> list[dict[str, str]]:
    path = Path(root) / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
    if not path.is_file():
        raise FileNotFoundError(f"commercial pricing census requires historical crosswalk: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 53:
        raise ValueError(f"historical portfolio count must remain 53 for pricing census, got {len(rows)}")
    return rows


def _quote_authority(rule: dict[str, Any]) -> dict[str, Any]:
    classes = set(rule["buyer_classes"])
    low_risk = classes.issubset({"C0", "C1", "C2", "C3"}) and rule["reference_band_zar"]["max"] <= 5000
    return {
        "mode": "bounded_estimate" if low_risk else "operator_review",
        "autonomous_ceiling_zar": rule["autonomous_quote_ceiling_zar"],
        "invoice_issue_authority": False,
        "external_send_authority": False,
        "pricing_hypothesis_may_mutate_quote_authority": False,
    }


def _product_row(*, name: str, canon_source: str, suite: str, family: str, source_maturity: str | None = None, capability_cost_score: float | None = None) -> dict[str, Any]:
    if name not in PROFILE_RULES:
        raise ValueError(f"explicit commercial profile missing for canon product: {name}")
    rule = PROFILE_RULES[name]
    return {
        "product_id": _slug(name),
        "name": name,
        "canon_source": canon_source,
        "suite": suite,
        "primary_family": family,
        "source_maturity": source_maturity,
        "capability_cost_score": capability_cost_score,
        **rule,
        "buyer_class_labels": [BUYER_CLASS_LABELS[x] for x in rule["buyer_classes"]],
        "quote_authority": _quote_authority(rule),
        "commercial_tiers": _commercial_tiers(rule),
        "pricing_state": "HYPOTHESIS",
        "commercial_validation": "UNPROVED",
        "customers_will_pay": "UNPROVED",
        "market_hypothesis_allowed": True,
        "profile_source": "explicit_68_product_census",
        "authority_created": False,
        "external_effects": False,
    }


def build_commercial_pricing_registry(root: Path) -> dict[str, Any]:
    historical = _historical_rows(Path(root))
    rows: list[dict[str, Any]] = []
    for source in historical:
        name = str(source.get("incarnation") or "").strip()
        raw_cost = str(source.get("capability_cost_score") or "").strip()
        try:
            cost_score = float(raw_cost) if raw_cost else None
        except ValueError:
            cost_score = None
        rows.append(_product_row(name=name, canon_source="historical_53", suite=str(source.get("suite") or ""), family=str(source.get("primary_family") or ""), source_maturity=str(source.get("source_maturity") or "") or None, capability_cost_score=cost_score))

    if len(CANON_EXTENSION_META) != 15:
        raise ValueError("canon extension commercial census must contain exactly 15 products")
    for name, suite, family in CANON_EXTENSION_META:
        rows.append(_product_row(name=name, canon_source="canon_extension_15", suite=suite, family=family, source_maturity="ProductGrade verified engineering; commercial validation unproved"))

    if len(PROFILE_RULES) != 68:
        raise ValueError(f"explicit commercial pricing rule count must be 68, got {len(PROFILE_RULES)}")
    names = [row["name"] for row in rows]
    if len(rows) != 68 or len(set(names)) != 68:
        raise ValueError("commercial pricing census must resolve exactly 68 unique canon products")
    if set(names) != set(PROFILE_RULES):
        missing = sorted(set(names) - set(PROFILE_RULES))
        extra = sorted(set(PROFILE_RULES) - set(names))
        raise ValueError(f"commercial census drift: missing_rules={missing}; extra_rules={extra}")

    rows.sort(key=lambda row: row["name"].lower())
    return {
        "schema": "dio.commercial_pricing_registry.v1",
        "product_count": 68,
        "historical_53_count": 53,
        "canon_extension_count": 15,
        "buyer_classes": BUYER_CLASS_LABELS,
        "tier_policy": {
            "tier_ids": [tier["tier_id"] for tier in COMMERCIAL_TIER_POLICY],
            "tiers": [
                {
                    "tier_id": tier["tier_id"],
                    "label": tier["label"],
                    "buyer_classes": list(tier["buyer_classes"]),
                    "reference_position": tier["reference_position"],
                }
                for tier in COMMERCIAL_TIER_POLICY
            ],
            "truth_boundary": "Tier prices are governed reference points within each product band, not validated willingness-to-pay claims.",
        },
        "products": rows,
        "pricing_truth_boundary": "Reference bands are governed commercial hypotheses. They do not prove market fit or willingness to pay. HiveNance may propose refinements from settled outcomes, but no direct learning-to-quote-authority path exists.",
        "authority_created": False,
        "external_effects": False,
    }
