from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from products.commercial_pricing_registry import build_commercial_pricing_registry

from .fulfilment_contract import EXECUTION_PROFILE_SCHEMA
from .intake_scope_quote import build_intake_requirement
from .organ_adapter_gauntlet import ORGAN_FAMILIES


BINDING_SCHEMA = "dio.customer_journey.phase8_product_binding.v1"
REGISTRY_SCHEMA = "dio.customer_journey.phase8_binding_registry.v1"
BINDING_VERSION = "1.0.0"

PHASE7_ACCEPTANCE = {
    "token": "DIO_CUSTOMER_JOURNEY_PHASE7_ORGAN_ADAPTER_GAUNTLET_VERIFIED",
    "run_id": "35290677179",
    "head_sha": "78eb700cd13977351510a28f13ca4959bcbf949b",
}


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


ARCHETYPE_PROFILES: dict[str, dict[str, Any]] = {
    "A": {
        "name": "Assessment & learning",
        "human_gates": [
            "educator_or_content_owner_review",
            "consequential_mark_or_feedback_requires_human_authority",
        ],
        "deliverable_types": [
            "assessment_support",
            "learning_pack",
            "teaching_asset",
        ],
        "release_conditions": [
            "content_or_educator_review",
            "exact_manifest_approval",
        ],
        "delivery_channels": ["web", "email", "telegram", "api"],
    },
    "B": {
        "name": "Scholarly review & research",
        "human_gates": [
            "authorship_preservation",
            "remote_processing_authority_when_required",
            "human_release_review",
        ],
        "deliverable_types": [
            "anchored_review",
            "research_pack",
            "claim_or_citation_audit",
        ],
        "release_conditions": [
            "source_custody_verified",
            "human_release_review",
            "exact_manifest_approval",
        ],
        "delivery_channels": ["web", "email", "telegram", "api"],
    },
    "C": {
        "name": "Evidence & performance",
        "human_gates": [
            "provenance_review",
            "human_judgement_boundary",
        ],
        "deliverable_types": [
            "evidence_pack",
            "coverage_snapshot",
            "readiness_pack",
        ],
        "release_conditions": [
            "provenance_verified",
            "exact_manifest_approval",
        ],
        "delivery_channels": ["web", "email", "telegram", "api"],
    },
    "D": {
        "name": "Obligation, assurance & regulated trust",
        "human_gates": [
            "professional_or_legal_review_as_profiled",
            "typed_authority_review",
            "human_release_review",
        ],
        "deliverable_types": [
            "proof_pack",
            "readiness_pack",
            "assurance_pack",
            "evidence_room",
        ],
        "release_conditions": [
            "evidence_and_requirement_lineage_verified",
            "professional_or_authority_gate_as_profiled",
            "exact_manifest_approval",
        ],
        "delivery_channels": ["web", "email", "api"],
    },
    "E": {
        "name": "Document, publication & professional output",
        "human_gates": [
            "semantic_and_visual_qa",
            "human_language_review_when_required",
            "human_release_review",
        ],
        "deliverable_types": [
            "document_bundle",
            "publication_bundle",
            "site_or_correspondence_bundle",
        ],
        "release_conditions": [
            "semantic_completeness",
            "format_qa",
            "language_review_when_required",
            "exact_manifest_approval",
        ],
        "delivery_channels": ["web", "email", "telegram", "api"],
    },
    "F": {
        "name": "Market & opportunity intelligence",
        "human_gates": [
            "evidence_grade_review",
            "no_autonomous_outreach",
            "no_autonomous_spend",
        ],
        "deliverable_types": [
            "market_research_pack",
            "opportunity_pack",
            "offer_research_pack",
        ],
        "release_conditions": [
            "source_and_evidence_grade_recorded",
            "no_outreach_authority_created",
            "exact_manifest_approval",
        ],
        "delivery_channels": ["web", "email", "api"],
    },
    "G": {
        "name": "Campaign, launch & media",
        "human_gates": [
            "editorial_approval",
            "publication_approval",
            "separate_spend_release_when_paid",
        ],
        "deliverable_types": [
            "campaign_pack",
            "media_pack",
            "launch_pack",
        ],
        "release_conditions": [
            "editorial_review",
            "publication_authority",
            "spend_authority_when_applicable",
            "exact_manifest_approval",
        ],
        "delivery_channels": ["web", "email", "api"],
    },
    "H": {
        "name": "Presence & case service",
        "human_gates": [
            "journey_core_action_authority_only",
            "actor_must_be_permitted_for_current_action",
        ],
        "deliverable_types": [
            "case_service_response",
            "journey_state_projection",
            "operator_handoff",
        ],
        "release_conditions": [
            "canonical_journey_state",
            "current_action_ref",
            "no_presence_created_authority",
        ],
        "delivery_channels": [
            "web",
            "telegram",
            "email",
            "voice",
            "operator",
        ],
    },
}


ARCHETYPE_PRODUCTS: dict[str, tuple[str, ...]] = {
    "A": (
        "HOMS Assess",
        "HOMS Exam",
        "HOMS Moderate",
        "HOMS Curriculum",
        "HOMS Learning Studio",
        "Sophia Tutor",
    ),
    "B": (
        "Sophia Review",
        "Sophia Research",
        "Sophia Supervisor",
        "Sophia Integrity",
    ),
    "C": (
        "VAMP Performance",
        "PromotionProof",
        "CPDProof",
        "ProjectProof",
        "ImpactProof",
        "Evidex EvidenceOps",
        "EntrepreneurProof",
        "InvestorProof",
    ),
    "D": (
        "HOMS Accreditation",
        "AuditProof",
        "VendorProof",
        "TenderProof",
        "GrantProof",
        "DonorProof",
        "ProgrammeProof",
        "QualityProof",
        "CertificationProof",
        "PolicyProof",
        "ContractProof",
        "DiligenceRoom",
        "AssuranceRoom",
        "DIO AI Assurance",
        "ModelProof",
        "Agent Authority",
        "ReleaseProof",
        "ChangeProof",
        "AI IncidentRoom",
        "CriticalAI Assurance",
        "CyberAssurance",
        "ControlDrift",
        "SupplierCyberProof",
        "IncidentProof",
        "DORA Vendor Assurance",
        "DIO RegOps",
        "PermitProof",
        "Contract Desk",
        "Corporate Readiness",
        "Finance Readiness",
        "Finance Readiness Studio",
        "POPIA Readiness",
    ),
    "E": (
        "Document Studio Edit",
        "Document Studio Localize",
        "Document Studio Publish",
        "Accessible Publish",
        "DossierOps",
        "Article Publication",
        "Article Publication Studio",
        "Professional Correspondence",
        "Professional Correspondence Studio",
        "Report & Pitch Studio",
        "Site Studio",
    ),
    "F": (
        "Market Radar",
        "Opportunity Foundry",
        "Offer Lab",
        "FundingFinder",
    ),
    "G": (
        "Campaign Lab",
        "Launch Studio",
    ),
    "H": ("Vesper Desk",),
}


ROUTE_PRODUCTS: dict[str, tuple[str, ...]] = {
    "homs_assessment": (
        "HOMS Assess",
        "HOMS Exam",
        "HOMS Moderate",
    ),
    "homs_learning": (
        "HOMS Curriculum",
        "HOMS Learning Studio",
    ),
    "sophia_review": (
        "Sophia Tutor",
        "Sophia Review",
        "Sophia Research",
        "Sophia Supervisor",
        "Sophia Integrity",
    ),
    "vamp_snapshot": (
        "VAMP Performance",
        "PromotionProof",
        "CPDProof",
        "ProjectProof",
        "ImpactProof",
    ),
    "evidex_evidence": (
        "Evidex EvidenceOps",
        "EntrepreneurProof",
        "InvestorProof",
    ),
    "obligation_assurance": ARCHETYPE_PRODUCTS["D"],
    "document_studio": ARCHETYPE_PRODUCTS["E"],
    "market_intelligence": ARCHETYPE_PRODUCTS["F"],
    "nichefoundry_campaign": ARCHETYPE_PRODUCTS["G"],
    "vesper_case_service": ARCHETYPE_PRODUCTS["H"],
}


ROUTE_COMPOSITIONS: dict[str, list[str]] = {
    "homs_assessment": ["HOMS", "Evidex", "Format Core"],
    "homs_learning": [
        "HOMS Learning",
        "Document Studio",
        "Format Core",
        "NicheFoundry when media is requested",
    ],
    "sophia_review": ["Sophia", "Evidex", "Format Core", "Lingua when required"],
    "vamp_snapshot": ["VAMP", "Evidex"],
    "evidex_evidence": ["Evidex", "VAMP when evidence mapping is requested"],
    "obligation_assurance": [
        "Obligation Core",
        "Evidex",
        "Assurance stack",
        "Legalis / BEAST / Seraph / authority organs when profiled",
    ],
    "document_studio": ["Document Studio", "Lingua", "Format Core"],
    "market_intelligence": [
        "Market Command intelligence",
        "Hivenance / Sensorium evidence when available",
        "NicheFoundry opportunity context",
    ],
    "nichefoundry_campaign": [
        "NicheFoundry",
        "Market Command",
        "Hivenance",
        "Format Core",
    ],
    "vesper_case_service": ["Vesper", "Lingua", "Journey Core"],
}


def _index(groups: dict[str, tuple[str, ...]], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, names in groups.items():
        for name in names:
            if name in result:
                raise ValueError(f"duplicate {label} assignment: {name}")
            result[name] = key
    return result


def _native_route(
    route_id: str,
    *,
    archetypes: list[str],
    adapter_id: str,
    source_path: str,
    organ_composition: list[str],
    proof_state: str,
    proof_ref: str,
) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "archetypes": list(archetypes),
        "adapter_id": adapter_id,
        "adapter_version": "1",
        "execution_class": "native",
        "source_path": source_path,
        "repository": None,
        "repository_commit": None,
        "organ_composition": list(organ_composition),
        "proof_state": proof_state,
        "proof_ref": proof_ref,
        "authority_created": False,
        "external_send_authority": False,
    }


def _route_registry(root: Path) -> dict[str, dict[str, Any]]:
    root = Path(root).resolve()
    routes: dict[str, dict[str, Any]] = {}

    for route_id in (
        "homs_assessment",
        "homs_learning",
        "sophia_review",
        "vamp_snapshot",
        "evidex_evidence",
        "obligation_assurance",
        "document_studio",
        "nichefoundry_campaign",
    ):
        source = deepcopy(ORGAN_FAMILIES[route_id])
        source["route_id"] = route_id
        source["archetypes"] = sorted(
            {
                archetype
                for product, archetype in _index(
                    ARCHETYPE_PRODUCTS,
                    "archetype",
                ).items()
                if product in set(ROUTE_PRODUCTS[route_id])
            }
        )
        source["organ_composition"] = list(ROUTE_COMPOSITIONS[route_id])
        source["proof_state"] = "PHASE7_VERIFIED"
        source["proof_ref"] = deepcopy(PHASE7_ACCEPTANCE)
        routes[route_id] = source

    routes["market_intelligence"] = _native_route(
        "market_intelligence",
        archetypes=["F"],
        adapter_id="dio.organ.market_intelligence",
        source_path="market_command/intelligence.py",
        organ_composition=ROUTE_COMPOSITIONS["market_intelligence"],
        proof_state="PHASE8_FRESH_PROOF_REQUIRED",
        proof_ref="tests/test_customer_journey_phase8_archetypes.py::market_intelligence",
    )
    routes["vesper_case_service"] = _native_route(
        "vesper_case_service",
        archetypes=["H"],
        adapter_id="dio.organ.vesper_case_service",
        source_path="presence_core/vesper_journey_runtime.py",
        organ_composition=ROUTE_COMPOSITIONS["vesper_case_service"],
        proof_state="PHASE8_FRESH_PROOF_REQUIRED",
        proof_ref="tests/test_customer_journey_phase8_archetypes.py::vesper_case_service",
    )

    for route_id, route in routes.items():
        if route["execution_class"] == "native":
            path = root / str(route["source_path"])
            if not path.is_file():
                raise ValueError(
                    f"native Phase 8 fulfilment route source is missing: {route_id}"
                )
            route["source_sha256"] = _file_sha256(path)
        else:
            if not str(route.get("repository") or "").strip():
                raise ValueError(
                    f"external Phase 8 route lacks repository: {route_id}"
                )
            commit = str(route.get("repository_commit") or "")
            if len(commit) != 40:
                raise ValueError(
                    f"external Phase 8 route lacks pinned commit: {route_id}"
                )
            route["source_sha256"] = None

        route_basis = deepcopy(route)
        route_basis.pop("route_fingerprint", None)
        route["route_fingerprint"] = _canonical_hash(route_basis)

    return routes


def _manifest_index(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    manifest_root = Path(root) / "config" / "products" / "manifests"
    if not manifest_root.is_dir():
        return result
    for path in sorted(manifest_root.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        name = str(value.get("name") or "").strip()
        if not name:
            continue
        result[name] = {
            "state": "CANONICAL_MANIFEST_PRESENT",
            "path": str(path.relative_to(root)),
            "manifest_product_id": str(value.get("product_id") or ""),
            "sha256": _file_sha256(path),
        }
    return result


def _assert_exact_68(
    commercial_names: set[str],
    archetype_index: dict[str, str],
    route_index: dict[str, str],
) -> None:
    if len(commercial_names) != 68:
        raise ValueError(
            f"Phase 8 requires exactly 68 commercial products, got {len(commercial_names)}"
        )
    if set(archetype_index) != commercial_names:
        missing = sorted(commercial_names - set(archetype_index))
        extra = sorted(set(archetype_index) - commercial_names)
        raise ValueError(
            f"Phase 8 archetype drift: missing={missing}; extra={extra}"
        )
    if set(route_index) != commercial_names:
        missing = sorted(commercial_names - set(route_index))
        extra = sorted(set(route_index) - commercial_names)
        raise ValueError(
            f"Phase 8 route drift: missing={missing}; extra={extra}"
        )


def compile_product_journey_binding(
    root: Path,
    product_name: str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    registry = build_commercial_pricing_registry(root)
    products = {
        str(row["name"]): row
        for row in registry.get("products") or []
    }
    archetype_index = _index(ARCHETYPE_PRODUCTS, "archetype")
    route_index = _index(ROUTE_PRODUCTS, "route")
    _assert_exact_68(set(products), archetype_index, route_index)

    if product_name not in products:
        raise ValueError(
            f"product is not a canonical 68-product commercial incarnation: {product_name}"
        )

    product = deepcopy(products[product_name])
    archetype_id = archetype_index[product_name]
    archetype = deepcopy(ARCHETYPE_PROFILES[archetype_id])
    route_id = route_index[product_name]
    route = deepcopy(_route_registry(root)[route_id])
    intake = build_intake_requirement(root, product_name)
    manifest = _manifest_index(root).get(
        product_name,
        {
            "state": "NO_CANONICAL_PRODUCT_MANIFEST",
            "path": None,
            "manifest_product_id": None,
            "sha256": None,
        },
    )

    pricing_basis = {
        "product_id": product["product_id"],
        "pricing_model": product["pricing_model"],
        "reference_band_zar": deepcopy(product["reference_band_zar"]),
        "commercial_tiers": deepcopy(product["commercial_tiers"]),
        "pricing_state": product["pricing_state"],
        "commercial_validation": product["commercial_validation"],
    }

    binding = {
        "schema": BINDING_SCHEMA,
        "binding_version": BINDING_VERSION,
        "product_id": product["product_id"],
        "product_name": product_name,
        "canon_source": product["canon_source"],
        "suite": product["suite"],
        "source_maturity": product.get("source_maturity"),
        "journey_archetype": {
            "id": archetype_id,
            "name": archetype["name"],
        },
        "journey_lifecycle": {
            "owner": "presence_core.journey_core",
            "product_specific_lifecycle_code": False,
            "surface_neutral": True,
            "presence_authority": False,
        },
        "intake_profile": {
            "required_inputs": deepcopy(intake["required_inputs"]),
            "optional_inputs": deepcopy(intake["optional_inputs"]),
            "accepted_input_classes": deepcopy(
                intake["accepted_input_classes"]
            ),
        },
        "scope_profile": deepcopy(intake["scope"]),
        "pricing_profile": {
            **pricing_basis,
            "pricing_profile_sha256": _canonical_hash(pricing_basis),
        },
        "quote_authority": deepcopy(product["quote_authority"]),
        "settlement_profile": {
            "allowed_classes": [
                "REAL_SETTLEMENT",
                "CONTROLLED_TEST_SETTLEMENT",
                "WAIVED",
            ],
            "real_settlement_requires_verified_external_funds": True,
            "controlled_test_revenue_recognised": False,
            "controlled_test_market_validation_eligible": False,
            "waived_requires_explicit_operator_authority": True,
            "settlement_never_creates_release_authority": True,
        },
        "fulfilment_profile": {
            "route_id": route_id,
            "adapter_id": route["adapter_id"],
            "adapter_version": route["adapter_version"],
            "execution_class": route["execution_class"],
            "source_path": route["source_path"],
            "source_sha256": route["source_sha256"],
            "repository": route.get("repository"),
            "repository_commit": route.get("repository_commit"),
            "route_fingerprint": route["route_fingerprint"],
            "organ_composition": deepcopy(route["organ_composition"]),
            "proof_state": route["proof_state"],
            "proof_ref": deepcopy(route["proof_ref"]),
        },
        "human_authority_gates": deepcopy(archetype["human_gates"]),
        "deliverable_profile": {
            "artifact_families": deepcopy(archetype["deliverable_types"]),
            "manifest_schema": "dio.deliverable_manifest.v2",
            "multi_artifact": True,
        },
        "release_profile": {
            "conditions": deepcopy(archetype["release_conditions"]),
            "exact_manifest_human_approval": True,
            "one_use_release_authority": True,
            "fulfilment_success_is_not_release_authority": True,
        },
        "delivery_profile": {
            "channels": deepcopy(archetype["delivery_channels"]),
            "delivery_receipt_required": True,
            "close_requires_delivery_receipt": True,
        },
        "product_compiler_manifest": manifest,
        "truth_boundary": (
            "This binding compiles the commercial product into the Customer "
            "Journey Spine. It does not manufacture product maturity, market "
            "validation, professional clearance, or a missing canonical "
            "Product Compiler manifest."
        ),
        "authority_created": False,
        "external_send_authority": False,
        "external_effects": False,
    }
    binding["binding_sha256"] = _canonical_hash(binding)
    return binding


def build_phase8_binding_registry(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    commercial = build_commercial_pricing_registry(root)
    products = list(commercial.get("products") or [])
    archetype_index = _index(ARCHETYPE_PRODUCTS, "archetype")
    route_index = _index(ROUTE_PRODUCTS, "route")
    commercial_names = {str(row["name"]) for row in products}
    _assert_exact_68(commercial_names, archetype_index, route_index)

    bindings = [
        compile_product_journey_binding(root, str(row["name"]))
        for row in products
    ]
    bindings.sort(key=lambda row: str(row["product_name"]).casefold())
    routes = _route_registry(root)

    route_counts: dict[str, int] = {}
    archetype_counts: dict[str, int] = {}
    for binding in bindings:
        route_id = str(binding["fulfilment_profile"]["route_id"])
        route_counts[route_id] = route_counts.get(route_id, 0) + 1
        archetype_id = str(binding["journey_archetype"]["id"])
        archetype_counts[archetype_id] = (
            archetype_counts.get(archetype_id, 0) + 1
        )

    result = {
        "schema": REGISTRY_SCHEMA,
        "binding_version": BINDING_VERSION,
        "product_count": len(bindings),
        "historical_53_count": int(commercial["historical_53_count"]),
        "canon_extension_count": int(commercial["canon_extension_count"]),
        "archetype_count": len(ARCHETYPE_PROFILES),
        "route_count": len(routes),
        "archetype_counts": archetype_counts,
        "route_counts": route_counts,
        "routes": [deepcopy(routes[key]) for key in sorted(routes)],
        "bindings": bindings,
        "unknown_archetypes": [],
        "unknown_fulfilment_routes": [],
        "bespoke_commerce_pipelines": [],
        "authority_leaks": [],
        "authority_created": False,
        "external_effects": False,
    }
    result["registry_sha256"] = _canonical_hash(result)
    return result


def build_phase8_execution_profile(
    root: Path,
    product_name: str,
) -> dict[str, Any]:
    binding = compile_product_journey_binding(Path(root), product_name)
    fulfilment = binding["fulfilment_profile"]

    profile = {
        "schema": EXECUTION_PROFILE_SCHEMA,
        "compiled_product_id": binding["product_id"],
        "journey_product_id": binding["product_name"],
        "phase8_binding_sha256": binding["binding_sha256"],
        "composition_fingerprint": "sha256:" + str(
            fulfilment["route_fingerprint"]
        ),
        "compilation_fingerprint": "sha256:" + str(
            binding["binding_sha256"]
        ),
        "adapter_id": fulfilment["adapter_id"],
        "adapter_version": fulfilment["adapter_version"],
        "execution_gate": {
            "state": "NEEDS_YOU",
            "reason": (
                "Phase 8 binding resolves the execution route but creates no "
                "autonomous execution authority."
            ),
        },
        "executor_capabilities": [
            {
                "capability_id": (
                    "customer_journey.fulfilment."
                    + str(fulfilment["route_id"])
                ),
                "resolution_state": "RESOLVED",
                "provider": {
                    "provider_id": fulfilment["adapter_id"],
                    "provider_kind": fulfilment["execution_class"],
                    "ref": fulfilment["source_path"],
                    "execution_capable": True,
                    "product_scope": [binding["product_id"]],
                    "repository": fulfilment.get("repository"),
                    "repository_commit": fulfilment.get(
                        "repository_commit"
                    ),
                    "route_fingerprint": fulfilment[
                        "route_fingerprint"
                    ],
                },
            }
        ],
        "output_plan": {
            "schema": "dio.compiled_output_plan.v1",
            "outputs": [
                {
                    "artifact_families": deepcopy(
                        binding["deliverable_profile"][
                            "artifact_families"
                        ]
                    ),
                    "release_conditions": deepcopy(
                        binding["release_profile"]["conditions"]
                    ),
                    "delivery_channels": deepcopy(
                        binding["delivery_profile"]["channels"]
                    ),
                }
            ],
        },
        "release_authority_created": False,
        "external_send_authority": False,
        "authority_created": False,
    }
    profile["execution_profile_sha256"] = _canonical_hash(profile)
    return profile
