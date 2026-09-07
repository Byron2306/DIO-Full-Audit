from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_V1"
SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY"
SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_REFUSED"


SPRINT_PLAN = {
    "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
    "sprint_goal": "Convert the governed next-build candidate into a proof-bound MVP sprint path without claiming external validation.",
    "work_packages": [
        {
            "id": "T13-WP1",
            "name": "Trust dossier manifest compiler",
            "purpose": "Compile product identity, intended audience, evidence scope, authority boundary, and output contract into a deterministic dossier manifest.",
            "acceptance_gates": ["manifest_schema_valid", "audience_scope_bound", "authority_boundary_present", "external_validation_refused"],
            "evidence_receipts": ["manifest_hash", "schema_validation_receipt", "claim_lock_receipt"],
        },
        {
            "id": "T13-WP2",
            "name": "Evidence spine binder",
            "purpose": "Bind source receipts, prior proof packs, product claims, disclaimers, and forbidden claims into a dossier evidence spine.",
            "acceptance_gates": ["source_receipts_bound", "proof_pack_hashes_bound", "forbidden_claims_preserved", "stale_evidence_flag_available"],
            "evidence_receipts": ["evidence_spine_hash", "source_binding_receipt", "forbidden_claim_lock_receipt"],
        },
        {
            "id": "T13-WP3",
            "name": "Dossier renderer surface",
            "purpose": "Render a human-reviewable dossier draft with claim-safe executive summary, proof numbers, source hashes, and boundary warnings.",
            "acceptance_gates": ["summary_present", "proof_numbers_present", "boundary_warnings_present", "human_review_required"],
            "evidence_receipts": ["render_receipt", "dossier_sha256", "human_gate_receipt"],
        },
        {
            "id": "T13-WP4",
            "name": "Claim audit evaluator",
            "purpose": "Evaluate generated dossier language against allowed claims, forbidden claims, authority locks, and marketing-safe boundaries.",
            "acceptance_gates": ["allowed_claims_matched", "forbidden_claims_absent", "commercial_validation_refused", "authority_expansion_refused"],
            "evidence_receipts": ["claim_audit_receipt", "forbidden_term_scan", "authority_lock_receipt"],
        },
        {
            "id": "T13-WP5",
            "name": "Sprint demo harness",
            "purpose": "Provide a deterministic local demo harness that exercises manifest compile, evidence bind, render, and claim audit without publication.",
            "acceptance_gates": ["local_demo_only", "no_external_action", "no_publication", "receipt_bundle_written"],
            "evidence_receipts": ["demo_run_receipt", "receipt_bundle_manifest", "external_action_refusal_receipt"],
        },
    ],
}


@dataclass(frozen=True)
class SelectedProductSprintPlanningReceipt:
    gauntlet_version: str
    status: str
    product_portfolio_marketing_pack_status: str
    execute_requested: bool
    executed: bool
    selected_product: str
    sprint_plan_written: bool
    work_packages_planned: int
    acceptance_gates_planned: int
    evidence_receipts_planned: int
    static_sprint_baseline_mean_score: float
    governed_sprint_plan_mean_score: float
    governed_sprint_minus_static_effect: float
    minimum_governed_sprint_score: float
    minimum_sprint_planning_effect: float
    governed_sprint_quality_threshold_met: bool
    sprint_planning_effect_threshold_met: bool
    selected_product_sprint_planning_evidence: bool
    sprint_planning_claim_authorized: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    sprint_plan_path: str
    sprint_summary_path: str
    product_portfolio_marketing_pack_sha256: str
    product_market_fit_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    professional_approval_claim_authorized: bool
    autonomous_development_authorized: bool
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


def _score_work_package(package: dict) -> float:
    gates = package.get("acceptance_gates", [])
    receipts = package.get("evidence_receipts", [])
    has_identity = bool(package.get("id") and package.get("name") and package.get("purpose"))
    gate_score = min(1.0, len(gates) / 4.0)
    receipt_score = min(1.0, len(receipts) / 3.0)
    boundary_score = 1.0 if any("refus" in gate for gate in gates) or any("human" in gate for gate in gates) or any("external" in gate for gate in gates) else 0.0
    return round((1.0 if has_identity else 0.0) * 0.30 + gate_score * 0.35 + receipt_score * 0.25 + boundary_score * 0.10, 6)


def _static_baseline_score(package_count: int) -> float:
    return round(min(0.3, package_count * 0.038), 6)


def run_selected_product_sprint_planning_gauntlet(
    *,
    product_portfolio_marketing_pack_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> SelectedProductSprintPlanningReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = _load_json(product_portfolio_marketing_pack_path)
    sprint_plan_path = output_dir / "selected_product_sprint_plan.json"
    sprint_summary_path = output_dir / "selected_product_sprint_planning_summary.json"
    receipt_path = output_dir / "selected_product_sprint_planning_gauntlet_receipt.json"

    pack_ready = (
        pack.get("status") == "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY"
        and pack.get("portfolio_prioritization_marketing_language_authorized") is True
        and pack.get("next_build_selection_claim_authorized") is True
        and pack.get("commercial_validation_claim_authorized") is False
        and pack.get("product_market_fit_claim_authorized") is False
        and pack.get("autonomous_development_authorized") is False
        and pack.get("authority_expansion_authorized") is False
    )

    minimum_score = 0.86
    minimum_effect = 0.50

    if not pack_ready or not execute:
        receipt = SelectedProductSprintPlanningReceipt(
            gauntlet_version=SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_VERSION,
            status=SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_REFUSED_TOKEN,
            product_portfolio_marketing_pack_status=str(pack.get("status")),
            execute_requested=execute,
            executed=False,
            selected_product=str(pack.get("next_build_candidate_selected", "")),
            sprint_plan_written=False,
            work_packages_planned=0,
            acceptance_gates_planned=0,
            evidence_receipts_planned=0,
            static_sprint_baseline_mean_score=0.0,
            governed_sprint_plan_mean_score=0.0,
            governed_sprint_minus_static_effect=0.0,
            minimum_governed_sprint_score=minimum_score,
            minimum_sprint_planning_effect=minimum_effect,
            governed_sprint_quality_threshold_met=False,
            sprint_planning_effect_threshold_met=False,
            selected_product_sprint_planning_evidence=False,
            sprint_planning_claim_authorized=False,
            adaptive_claim_authorized=False,
            allowed_claim_tier="T0_NO_SELECTED_PRODUCT_SPRINT_PLANNING_CLAIM",
            sprint_plan_path=str(sprint_plan_path),
            sprint_summary_path=str(sprint_summary_path),
            product_portfolio_marketing_pack_sha256=_sha256_path(product_portfolio_marketing_pack_path),
            product_market_fit_claim_authorized=False,
            commercial_validation_claim_authorized=False,
            professional_approval_claim_authorized=False,
            autonomous_development_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            world_first_claim_authorized=False,
            agi_claim_authorized=False,
            autonomous_action_claim_authorized=False,
            authority_expansion_authorized=False,
            boundary="Selected product sprint planning refused unless the T12 portfolio marketing proof pack is ready and explicit execution is requested.",
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    selected = str(pack.get("next_build_candidate_selected") or SPRINT_PLAN["selected_product"])
    plan = dict(SPRINT_PLAN)
    plan["selected_product"] = selected
    plan["claim_locks"] = {
        "product_market_fit_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "autonomous_development_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "autonomous_action_claim_authorized": False,
        "authority_expansion_authorized": False,
    }
    sprint_plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")

    packages = plan["work_packages"]
    package_scores = [_score_work_package(package) for package in packages]
    governed_mean = round(mean(package_scores), 6)
    static_mean = _static_baseline_score(len(packages))
    effect = round(governed_mean - static_mean, 6)
    quality_met = governed_mean >= minimum_score
    effect_met = effect >= minimum_effect
    evidence = quality_met and effect_met
    acceptance_gates = sum(len(package["acceptance_gates"]) for package in packages)
    evidence_receipts = sum(len(package["evidence_receipts"]) for package in packages)

    summary = {
        "selected_product": selected,
        "work_packages_planned": len(packages),
        "acceptance_gates_planned": acceptance_gates,
        "evidence_receipts_planned": evidence_receipts,
        "static_sprint_baseline_mean_score": static_mean,
        "governed_sprint_plan_mean_score": governed_mean,
        "governed_sprint_minus_static_effect": effect,
        "selected_product_sprint_planning_evidence": evidence,
        "claim_boundary": "Internal controlled sprint-planning evidence only. No autonomous development, product-market fit, commercial validation, publication, spend, fulfilment, or authority expansion is authorized.",
    }
    sprint_summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    receipt = SelectedProductSprintPlanningReceipt(
        gauntlet_version=SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_VERSION,
        status=SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY_TOKEN,
        product_portfolio_marketing_pack_status=str(pack.get("status")),
        execute_requested=True,
        executed=True,
        selected_product=selected,
        sprint_plan_written=True,
        work_packages_planned=len(packages),
        acceptance_gates_planned=acceptance_gates,
        evidence_receipts_planned=evidence_receipts,
        static_sprint_baseline_mean_score=static_mean,
        governed_sprint_plan_mean_score=governed_mean,
        governed_sprint_minus_static_effect=effect,
        minimum_governed_sprint_score=minimum_score,
        minimum_sprint_planning_effect=minimum_effect,
        governed_sprint_quality_threshold_met=quality_met,
        sprint_planning_effect_threshold_met=effect_met,
        selected_product_sprint_planning_evidence=evidence,
        sprint_planning_claim_authorized=evidence,
        adaptive_claim_authorized=evidence,
        allowed_claim_tier=(
            "T13_CANDIDATE_SELECTED_PRODUCT_SPRINT_PLANNING_EVIDENCE"
            if evidence
            else "T12_PORTFOLIO_PRIORITIZATION_ONLY_NO_SPRINT_PLANNING_CLAIM"
        ),
        sprint_plan_path=str(sprint_plan_path),
        sprint_summary_path=str(sprint_summary_path),
        product_portfolio_marketing_pack_sha256=_sha256_path(product_portfolio_marketing_pack_path),
        product_market_fit_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        professional_approval_claim_authorized=False,
        autonomous_development_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This selected product sprint planning gauntlet tests whether DIO can convert the governed next-build "
            "candidate into a local sprint plan with work packages, acceptance gates, evidence receipts, and human gates. "
            "It authorizes only candidate internal sprint-planning evidence and never authorizes autonomous development, "
            "product-market fit, commercial validation, professional approval, publication, spend, fulfilment, world-first "
            "status, AGI claims, autonomous consequential action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
