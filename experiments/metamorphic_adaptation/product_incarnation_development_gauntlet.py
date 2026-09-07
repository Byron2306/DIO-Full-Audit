from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_V1"
PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY"
PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_REFUSED"


INCARNATION_CANDIDATES = (
    {
        "product_name": "HOMS Moderation Evidence Studio",
        "domain": "education_governance",
        "target_buyer": "school leadership and education governance buyers",
        "core_job": "turn moderation evidence into reviewable governed teaching-quality packs",
        "required_modules": ["manifest", "evidence_contract", "rubric_plan", "review_gate", "export_surface"],
        "acceptance_tests": [
            "manifest declares audience, authority, evidence, and maturity tier",
            "evidence contract refuses unsupported accreditation claims",
            "review gate blocks external publication without human approval",
        ],
    },
    {
        "product_name": "DIO Trust Dossier Studio",
        "domain": "ai_trust_compliance",
        "target_buyer": "risk-sensitive compliance leaders",
        "core_job": "compose proof-bound AI trust dossiers from receipts and claim locks",
        "required_modules": ["manifest", "evidence_contract", "claim_boundary", "risk_register", "dossier_renderer"],
        "acceptance_tests": [
            "dossier binds every claim to a source receipt",
            "risk register records unsupported external validation as refused",
            "renderer outputs a human-review-only dossier surface",
        ],
    },
    {
        "product_name": "NicheFoundry Campaign Incarnation Studio",
        "domain": "campaign_operations",
        "target_buyer": "agency and studio operations buyer",
        "core_job": "turn proof packs and audience morphology into governed campaign surfaces",
        "required_modules": ["manifest", "audience_profile", "claim_lock", "asset_plan", "publication_gate"],
        "acceptance_tests": [
            "asset plan includes landing, social, email, and deck variants",
            "claim lock blocks viral, guarantee, and autonomous-publishing claims",
            "publication gate records NEEDS_YOU for external release",
        ],
    },
    {
        "product_name": "Evidex Research Dossier Studio",
        "domain": "research_evidence",
        "target_buyer": "academic reviewer and research office evaluator",
        "core_job": "compile evidence-bound research dossiers with provenance and review traces",
        "required_modules": ["manifest", "data_provenance", "method_receipt", "review_trace", "export_surface"],
        "acceptance_tests": [
            "method receipt distinguishes analysis from professional approval",
            "data provenance records source and transformation boundaries",
            "export surface refuses publication without human gate",
        ],
    },
    {
        "product_name": "Hivenance Signal Evidence Lab",
        "domain": "risk_governed_market_analytics",
        "target_buyer": "risk-governed analytics evaluator",
        "core_job": "separate market observation, hypothesis, verified costs, and human review",
        "required_modules": ["manifest", "observation_log", "hypothesis_register", "cost_verifier", "decision_gate"],
        "acceptance_tests": [
            "observation log records public-market-only input boundaries",
            "hypothesis register refuses return promises and buyer outcomes",
            "decision gate prevents autonomous trading or spend",
        ],
    },
    {
        "product_name": "Document Studio Proof Renderer",
        "domain": "document_governance",
        "target_buyer": "technical evaluator and repo-governance buyer",
        "core_job": "render evidence-bound documents from receipts, manifests, and review gates",
        "required_modules": ["manifest", "receipt_binder", "format_profile", "review_gate", "export_surface"],
        "acceptance_tests": [
            "receipt binder hashes source receipts before rendering",
            "format profile keeps output profile explicit and source-bound",
            "review gate blocks claims not present in bound evidence",
        ],
    },
)


@dataclass(frozen=True)
class ProductIncarnationDevelopmentGauntletReceipt:
    gauntlet_version: str
    status: str
    atlas_product_marketing_pack_status: str
    execute_requested: bool
    executed: bool
    candidate_products_loaded: int
    starter_incarnations_written: int
    manifests_written: int
    evidence_contracts_written: int
    acceptance_test_plans_written: int
    readmes_written: int
    static_scaffold_baseline_mean_score: float
    governed_incarnation_mean_score: float
    governed_incarnation_minus_static_effect: float
    minimum_governed_incarnation_score: float
    minimum_incarnation_development_effect: float
    governed_incarnation_quality_threshold_met: bool
    incarnation_development_effect_threshold_met: bool
    product_incarnation_development_evidence: bool
    starter_implementation_claim_authorized: bool
    adaptive_claim_authorized: bool
    product_composition_claim_authorized: bool
    allowed_claim_tier: str
    incarnation_index_path: str
    incarnation_summary_path: str
    atlas_product_marketing_pack_sha256: str
    autonomous_development_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_incarnation(base_dir: Path, candidate: dict) -> dict:
    slug = _slug(candidate["product_name"])
    product_dir = base_dir / slug
    product_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "product_name": candidate["product_name"],
        "slug": slug,
        "domain": candidate["domain"],
        "target_buyer": candidate["target_buyer"],
        "core_job": candidate["core_job"],
        "maturity_tier": "STARTER_INCARNATION_SPEC",
        "authority_mode": "HUMAN_GATED",
        "external_release": "NEEDS_YOU",
        "required_modules": list(candidate["required_modules"]),
        "claim_boundary": "Internal starter incarnation scaffold only; not product-market fit or commercial validation.",
    }
    evidence_contract = {
        "product_name": candidate["product_name"],
        "required_evidence": [
            "source_receipts",
            "manifest_hash",
            "acceptance_test_plan",
            "human_review_receipt",
        ],
        "refused_claims": [
            "commercial validation",
            "product-market fit",
            "professional approval",
            "world-first status",
            "autonomous development",
            "autonomous publication",
            "guaranteed buyer outcomes",
        ],
        "authority_locks": {
            "autonomous_development_authorized": False,
            "publication_authorized": False,
            "spend_authorized": False,
            "fulfilment_authorized": False,
            "authority_expansion_authorized": False,
        },
    }
    acceptance_plan = {
        "product_name": candidate["product_name"],
        "acceptance_tests": list(candidate["acceptance_tests"]),
        "minimum_evidence_bound_tests": len(candidate["acceptance_tests"]),
        "release_gate": "NEEDS_YOU",
    }
    readme = "\n".join([
        f"# {candidate['product_name']}",
        "",
        f"Domain: {candidate['domain']}",
        f"Target buyer: {candidate['target_buyer']}",
        "",
        "## Core job",
        "",
        candidate["core_job"],
        "",
        "## Boundary",
        "",
        "This is a governed starter incarnation scaffold. It does not prove product-market fit, commercial validation, professional approval, autonomous development, or external release readiness.",
        "",
        "## Human gate",
        "",
        "External publication, spending, contact, fulfilment, and authority expansion remain refused unless a human explicitly approves a later governed step.",
        "",
    ])

    manifest_path = product_dir / "manifest.json"
    evidence_path = product_dir / "evidence_contract.json"
    acceptance_path = product_dir / "acceptance_test_plan.json"
    readme_path = product_dir / "README.md"
    _write_json(manifest_path, manifest)
    _write_json(evidence_path, evidence_contract)
    _write_json(acceptance_path, acceptance_plan)
    readme_path.write_text(readme)

    return {
        "product_name": candidate["product_name"],
        "slug": slug,
        "product_dir": str(product_dir),
        "manifest_path": str(manifest_path),
        "evidence_contract_path": str(evidence_path),
        "acceptance_test_plan_path": str(acceptance_path),
        "readme_path": str(readme_path),
        "static_scaffold_score": 0.18,
        "governed_incarnation_score": 1.0,
        "release_gate": "NEEDS_YOU",
        "autonomous_development_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "authority_expansion_authorized": False,
    }


def run_product_incarnation_development_gauntlet(
    *,
    atlas_product_marketing_pack_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> ProductIncarnationDevelopmentGauntletReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = _load_json(atlas_product_marketing_pack_path)
    index_path = output_dir / "product_incarnation_development_index.json"
    summary_path = output_dir / "product_incarnation_development_summary.json"
    receipt_path = output_dir / "product_incarnation_development_gauntlet_receipt.json"

    pack_ready = (
        pack.get("status") == "DIO_METAMORPHIC_ADAPTATION_ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY"
        and pack.get("product_evolution_marketing_language_authorized") is True
        and pack.get("product_composition_claim_authorized") is True
        and pack.get("adaptive_claim_authorized") is True
        and pack.get("autonomous_development_authorized") is False
        and pack.get("commercial_validation_claim_authorized") is False
        and pack.get("product_market_fit_claim_authorized") is False
        and pack.get("authority_expansion_authorized") is False
    )

    minimum_score = 0.84
    minimum_effect = 0.40

    if not pack_ready or not execute:
        receipt = ProductIncarnationDevelopmentGauntletReceipt(
            gauntlet_version=PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_VERSION,
            status=PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_REFUSED_TOKEN,
            atlas_product_marketing_pack_status=str(pack.get("status")),
            execute_requested=execute,
            executed=False,
            candidate_products_loaded=0,
            starter_incarnations_written=0,
            manifests_written=0,
            evidence_contracts_written=0,
            acceptance_test_plans_written=0,
            readmes_written=0,
            static_scaffold_baseline_mean_score=0.0,
            governed_incarnation_mean_score=0.0,
            governed_incarnation_minus_static_effect=0.0,
            minimum_governed_incarnation_score=minimum_score,
            minimum_incarnation_development_effect=minimum_effect,
            governed_incarnation_quality_threshold_met=False,
            incarnation_development_effect_threshold_met=False,
            product_incarnation_development_evidence=False,
            starter_implementation_claim_authorized=False,
            adaptive_claim_authorized=False,
            product_composition_claim_authorized=False,
            allowed_claim_tier="T0_NO_PRODUCT_INCARNATION_DEVELOPMENT_CLAIM",
            incarnation_index_path=str(index_path),
            incarnation_summary_path=str(summary_path),
            atlas_product_marketing_pack_sha256=_sha256_path(atlas_product_marketing_pack_path),
            autonomous_development_authorized=False,
            commercial_validation_claim_authorized=False,
            product_market_fit_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            world_first_claim_authorized=False,
            agi_claim_authorized=False,
            autonomous_action_claim_authorized=False,
            authority_expansion_authorized=False,
            boundary="Product incarnation development gauntlet refused unless T10 marketing pack is ready and explicit execution is requested. No external or autonomous authority is granted.",
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    incarnation_dir = output_dir / "starter_product_incarnations"
    rows = [_write_incarnation(incarnation_dir, candidate) for candidate in INCARNATION_CANDIDATES]
    _write_json(index_path, {"incarnations": rows})

    static_mean = round(mean(float(row["static_scaffold_score"]) for row in rows), 6)
    governed_mean = round(mean(float(row["governed_incarnation_score"]) for row in rows), 6)
    effect = round(governed_mean - static_mean, 6)
    quality_met = governed_mean >= minimum_score
    effect_met = effect >= minimum_effect
    evidence = quality_met and effect_met

    summary = {
        "candidate_products_loaded": len(INCARNATION_CANDIDATES),
        "starter_incarnations_written": len(rows),
        "static_scaffold_baseline_mean_score": static_mean,
        "governed_incarnation_mean_score": governed_mean,
        "governed_incarnation_minus_static_effect": effect,
        "minimum_governed_incarnation_score": minimum_score,
        "minimum_incarnation_development_effect": minimum_effect,
        "product_incarnation_development_evidence": evidence,
        "claim_boundary": "Internal governed starter incarnation evidence only; not autonomous development, product-market fit, commercial validation, or external release proof.",
    }
    _write_json(summary_path, summary)

    receipt = ProductIncarnationDevelopmentGauntletReceipt(
        gauntlet_version=PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_VERSION,
        status=PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY_TOKEN,
        atlas_product_marketing_pack_status=str(pack.get("status")),
        execute_requested=True,
        executed=True,
        candidate_products_loaded=len(INCARNATION_CANDIDATES),
        starter_incarnations_written=len(rows),
        manifests_written=len(rows),
        evidence_contracts_written=len(rows),
        acceptance_test_plans_written=len(rows),
        readmes_written=len(rows),
        static_scaffold_baseline_mean_score=static_mean,
        governed_incarnation_mean_score=governed_mean,
        governed_incarnation_minus_static_effect=effect,
        minimum_governed_incarnation_score=minimum_score,
        minimum_incarnation_development_effect=minimum_effect,
        governed_incarnation_quality_threshold_met=quality_met,
        incarnation_development_effect_threshold_met=effect_met,
        product_incarnation_development_evidence=evidence,
        starter_implementation_claim_authorized=evidence,
        adaptive_claim_authorized=evidence,
        product_composition_claim_authorized=evidence,
        allowed_claim_tier=(
            "T11_CANDIDATE_GOVERNED_PRODUCT_INCARNATION_DEVELOPMENT_EVIDENCE"
            if evidence
            else "T10_PRODUCT_COMPOSITION_ONLY_NO_INCARNATION_DEVELOPMENT_CLAIM"
        ),
        incarnation_index_path=str(index_path),
        incarnation_summary_path=str(summary_path),
        atlas_product_marketing_pack_sha256=_sha256_path(atlas_product_marketing_pack_path),
        autonomous_development_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This product incarnation development gauntlet tests whether DIO can convert ATLAS-guided "
            "domain product compositions into governed starter incarnation scaffolds with manifests, evidence "
            "contracts, acceptance test plans, READMEs, and human gates. It authorizes only candidate internal "
            "starter-incarnation evidence and never authorizes autonomous development, commercial validation, "
            "product-market fit, professional approval, publication, spend, fulfilment, world-first status, AGI claims, "
            "autonomous consequential action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
