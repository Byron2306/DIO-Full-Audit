from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_V1"
ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY"
ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_REFUSED"


ORGANS = (
    {
        "organ_id": "DIO_CORE",
        "role": "governed_orchestration_kernel",
        "capabilities": ["plan", "route", "bind_receipts", "refuse_overclaim"],
        "required_receipts": ["lineage", "claim_boundary", "execution_gate"],
        "forbidden_claims": ["authority_expansion", "world_first", "commercial_validation"],
    },
    {
        "organ_id": "LINGUA",
        "role": "semantic_cortex_and_boundary_language",
        "capabilities": ["semantic_normalization", "claim_language_repair", "rubric_alignment"],
        "required_receipts": ["semantic_trace", "boundary_terms"],
        "forbidden_claims": ["new_authority", "professional_approval"],
    },
    {
        "organ_id": "BEAST",
        "role": "repo_context_and_quality_governor",
        "capabilities": ["codebase_scoping", "root_cause_analysis", "bounded_patch_plan"],
        "required_receipts": ["file_scope", "test_scope", "patch_boundary"],
        "forbidden_claims": ["unverified_fix", "production_readiness"],
    },
    {
        "organ_id": "SOPHIA",
        "role": "reflective_evidence_and_claim_reviewer",
        "capabilities": ["claim_critique", "evidence_gap_detection", "boundary_review"],
        "required_receipts": ["critique", "gap_list", "claim_tier"],
        "forbidden_claims": ["final_approval", "professional_opinion"],
    },
    {
        "organ_id": "EVIDEX",
        "role": "proof_lineage_and_receipt_engine",
        "capabilities": ["receipt_chain", "evidence_repair", "provenance_binding"],
        "required_receipts": ["source_hash", "lineage_hash", "missing_evidence"],
        "forbidden_claims": ["invented_evidence", "external_validation"],
    },
    {
        "organ_id": "HIVENANCE",
        "role": "market_observation_and_economic_hypothesis_engine",
        "capabilities": ["market_observation", "cost_boundary", "hypothesis_scoring"],
        "required_receipts": ["market_snapshot", "fee_boundary", "no_trade_claim"],
        "forbidden_claims": ["profit_guarantee", "investment_advice", "execution_authority"],
    },
    {
        "organ_id": "MARKET_SENSORIUM",
        "role": "public_world_signal_binder",
        "capabilities": ["source_bound_signal", "market_rank_context", "staleness_detection"],
        "required_receipts": ["source_url_or_hash", "timestamp", "staleness_boundary"],
        "forbidden_claims": ["current_world_truth_without_source", "buyer_validation"],
    },
    {
        "organ_id": "LEGALIS",
        "role": "authority_and_obligation_gate",
        "capabilities": ["allow_refuse_needs_you", "obligation_mapping", "external_effect_detection"],
        "required_receipts": ["authority_basis", "human_gate", "external_effect_boundary"],
        "forbidden_claims": ["legal_advice", "regulatory_clearance"],
    },
    {
        "organ_id": "DOCUMENT_STUDIO",
        "role": "governed_deliverable_composer",
        "capabilities": ["document_transform", "evidence_packaging", "format_control"],
        "required_receipts": ["input_hash", "render_profile", "output_hash"],
        "forbidden_claims": ["content_truth_without_source", "publication_authority"],
    },
    {
        "organ_id": "NICHEFOUNDRY",
        "role": "marketfront_and_media_incarnation_composer",
        "capabilities": ["buyer_facing_translation", "asset_plan", "audience_hypothesis"],
        "required_receipts": ["audience_hypothesis", "claim_boundary", "asset_receipt"],
        "forbidden_claims": ["sales_validation", "ad_platform_approval"],
    },
    {
        "organ_id": "HOMS",
        "role": "education_and_learning_product_context",
        "capabilities": ["curriculum_context", "assessment_context", "learner_support_pattern"],
        "required_receipts": ["education_context", "assessment_boundary", "human_moderation_gate"],
        "forbidden_claims": ["institutional_approval", "learner_outcome_guarantee"],
    },
)


@dataclass(frozen=True)
class EcosystemOrganCapabilityRegistryReceipt:
    registry_version: str
    status: str
    organs_registered: int
    registry_path: str
    organ_ids: list[str]
    ecosystem_adaptation_hypothesis: str
    real_ecosystem_execution_authorized: bool
    execute_by_default: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    registry_sha256: str
    boundary: str


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_ecosystem_organ_capability_registry(*, output_dir: Path) -> EcosystemOrganCapabilityRegistryReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    registry_path = output_dir / "ecosystem_organ_capability_registry.json"
    receipt_path = output_dir / "ecosystem_organ_capability_registry_receipt.json"

    registry = {
        "registry_version": ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_VERSION,
        "hypothesis": (
            "DIO ecosystem adaptability should be tested as organ-mediated orchestration across "
            "BEAST, Sophia, Evidex, Hivenance, Market Sensorium, Lingua, Legalis, Document Studio, "
            "NicheFoundry, HOMS, and DIO Core, not as isolated synthetic DIO output generation."
        ),
        "organs": list(ORGANS),
        "claims": {
            "adaptive_claim_authorized": False,
            "commercial_or_world_first_claim_authorized": False,
            "professional_approval_claim_authorized": False,
            "publication_authorized": False,
            "spend_authorized": False,
            "fulfilment_authorized": False,
            "authority_expansion_authorized": False,
        },
    }
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    organ_ids = [organ["organ_id"] for organ in ORGANS]
    duplicate_ids = len(organ_ids) != len(set(organ_ids))
    valid = len(ORGANS) >= 10 and not duplicate_ids and all(organ.get("capabilities") for organ in ORGANS)

    receipt = EcosystemOrganCapabilityRegistryReceipt(
        registry_version=ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_VERSION,
        status=(
            ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY_TOKEN
            if valid
            else ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_REFUSED_TOKEN
        ),
        organs_registered=len(ORGANS) if valid else 0,
        registry_path=str(registry_path),
        organ_ids=organ_ids if valid else [],
        ecosystem_adaptation_hypothesis=str(registry["hypothesis"]),
        real_ecosystem_execution_authorized=valid,
        execute_by_default=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        registry_sha256=_sha256_path(registry_path),
        boundary=(
            "This registry declares organ capabilities and forbidden claims for an ecosystem-level "
            "metamorphic adaptation gauntlet. It authorizes planning and bounded execution design only. "
            "It does not execute work by default and does not authorize adaptive, commercial, professional, "
            "publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
