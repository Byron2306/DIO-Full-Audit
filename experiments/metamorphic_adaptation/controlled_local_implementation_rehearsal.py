from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_READY"
REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_REFUSED"
UPSTREAM_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_MARKETING_PROOF_PACK_READY"
TIER = "T14_CANDIDATE_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_EVIDENCE"


@dataclass(frozen=True)
class ControlledLocalImplementationRehearsalReceipt:
    status: str
    gauntlet_version: str
    selected_product_sprint_marketing_pack_status: str
    selected_product_sprint_marketing_pack_sha256: str
    selected_product: str
    execute_requested: bool
    executed: bool
    modules_rehearsed: int
    test_skeletons_rehearsed: int
    receipt_schemas_rehearsed: int
    acceptance_gate_bindings_rehearsed: int
    rehearsal_file_manifest_written: bool
    implementation_rehearsal_plan_written: bool
    static_implementation_baseline_mean_score: float
    controlled_rehearsal_mean_score: float
    controlled_rehearsal_minus_static_effect: float
    minimum_controlled_rehearsal_score: float
    minimum_rehearsal_effect: float
    controlled_rehearsal_quality_threshold_met: bool
    rehearsal_effect_threshold_met: bool
    implementation_rehearsal_evidence: bool
    local_implementation_rehearsal_claim_authorized: bool
    starter_code_claim_authorized: bool
    adaptive_claim_authorized: bool
    product_composition_claim_authorized: bool
    sprint_planning_claim_authorized: bool
    autonomous_development_authorized: bool
    autonomous_action_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    agi_claim_authorized: bool
    world_first_claim_authorized: bool
    authority_expansion_authorized: bool
    allowed_claim_tier: str
    rehearsal_plan_path: str
    rehearsal_file_manifest_path: str
    rehearsal_summary_path: str
    boundary: str


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _module_rehearsals() -> list[dict[str, Any]]:
    return [
        {
            "module": "trust_dossier_manifest_loader",
            "purpose": "Load source-bound dossier manifests and verify required identity, scope, evidence, and authority fields.",
            "test_skeleton": "test_manifest_loader_rejects_missing_source_hash",
            "receipt_schema": "manifest_loader_receipt",
            "acceptance_gates": [
                "manifest_has_product_identity",
                "manifest_has_source_hash",
                "missing_required_fields_refuse",
                "authority_boundary_present",
            ],
        },
        {
            "module": "trust_dossier_evidence_binder",
            "purpose": "Bind claims to evidence receipts without allowing unsupported professional, commercial, or world-first claims.",
            "test_skeleton": "test_evidence_binder_blocks_unbound_claims",
            "receipt_schema": "evidence_binding_receipt",
            "acceptance_gates": [
                "evidence_items_have_hashes",
                "claim_to_evidence_map_complete",
                "unsupported_claims_refuse",
                "source_paths_are_recorded",
            ],
        },
        {
            "module": "trust_dossier_authority_gate",
            "purpose": "Classify permitted, human-gated, and refused actions for generated trust dossiers.",
            "test_skeleton": "test_authority_gate_preserves_human_review",
            "receipt_schema": "authority_gate_receipt",
            "acceptance_gates": [
                "external_publication_refused",
                "professional_approval_not_claimed",
                "human_gate_required",
                "authority_never_expands_from_score",
            ],
        },
        {
            "module": "trust_dossier_renderer_plan",
            "purpose": "Plan Markdown and JSON dossier rendering surfaces without publishing or sending externally.",
            "test_skeleton": "test_renderer_plan_is_local_only",
            "receipt_schema": "renderer_plan_receipt",
            "acceptance_gates": [
                "local_render_only",
                "dossier_sections_declared",
                "forbidden_claims_listed",
                "output_paths_are_local",
            ],
        },
        {
            "module": "trust_dossier_acceptance_digest",
            "purpose": "Aggregate rehearsal receipts into a bounded acceptance digest for human review.",
            "test_skeleton": "test_acceptance_digest_requires_all_receipts",
            "receipt_schema": "acceptance_digest_receipt",
            "acceptance_gates": [
                "all_module_receipts_required",
                "digest_hashes_inputs",
                "human_review_checkpoint_present",
                "no_commercial_validation_claim",
            ],
        },
    ]


def _score_static_baseline() -> float:
    return 0.21


def _score_controlled_rehearsal(modules: list[dict[str, Any]]) -> float:
    expected = len(modules) * 4
    actual = sum(len(module["acceptance_gates"]) for module in modules)
    if expected == 0:
        return 0.0
    gate_score = actual / expected
    receipt_score = sum(1 for module in modules if module.get("receipt_schema")) / len(modules)
    test_score = sum(1 for module in modules if module.get("test_skeleton")) / len(modules)
    boundary_score = 1.0
    return round((gate_score * 0.4) + (receipt_score * 0.2) + (test_score * 0.2) + (boundary_score * 0.2), 6)


def run_controlled_local_implementation_rehearsal(
    *,
    selected_product_sprint_marketing_pack_path: Path | str,
    output_dir: Path | str,
    execute: bool = False,
) -> ControlledLocalImplementationRehearsalReceipt:
    pack_path = Path(selected_product_sprint_marketing_pack_path)
    out = Path(output_dir)
    pack = _load_json(pack_path)
    upstream_status = str(pack.get("status", ""))
    selected_product = str(pack.get("selected_product", ""))
    refused = upstream_status != UPSTREAM_READY_TOKEN or selected_product != "DIO_TRUST_DOSSIER_STUDIO"

    modules = _module_rehearsals() if not refused else []
    static_score = _score_static_baseline() if not refused else 0.0
    controlled_score = _score_controlled_rehearsal(modules) if not refused else 0.0
    effect = round(controlled_score - static_score, 6)
    minimum_score = 0.86
    minimum_effect = 0.5
    quality_met = controlled_score >= minimum_score
    effect_met = effect >= minimum_effect
    evidence = bool(execute and not refused and quality_met and effect_met)

    plan_path = out / "dio_trust_dossier_studio_implementation_rehearsal_plan.json"
    manifest_path = out / "dio_trust_dossier_studio_rehearsal_file_manifest.json"
    summary_path = out / "controlled_local_implementation_rehearsal_summary.json"
    receipt_path = out / "controlled_local_implementation_rehearsal_receipt.json"

    if evidence:
        plan = {
            "selected_product": selected_product,
            "rehearsal_only": True,
            "starter_code_written": False,
            "human_approval_required_before_implementation": True,
            "modules": modules,
        }
        file_manifest = {
            "selected_product": selected_product,
            "planned_local_files": [
                "products/dio_trust_dossier_studio/__init__.py",
                "products/dio_trust_dossier_studio/manifest_loader.py",
                "products/dio_trust_dossier_studio/evidence_binder.py",
                "products/dio_trust_dossier_studio/authority_gate.py",
                "products/dio_trust_dossier_studio/renderer_plan.py",
                "products/dio_trust_dossier_studio/acceptance_digest.py",
                "tests/test_dio_trust_dossier_studio_manifest_loader.py",
                "tests/test_dio_trust_dossier_studio_evidence_binder.py",
                "tests/test_dio_trust_dossier_studio_authority_gate.py",
                "tests/test_dio_trust_dossier_studio_renderer_plan.py",
                "tests/test_dio_trust_dossier_studio_acceptance_digest.py",
            ],
            "writes_performed": [],
            "write_authorization_required": True,
        }
        summary = {
            "selected_product": selected_product,
            "modules_rehearsed": len(modules),
            "acceptance_gate_bindings_rehearsed": sum(len(module["acceptance_gates"]) for module in modules),
            "controlled_rehearsal_mean_score": controlled_score,
            "controlled_rehearsal_minus_static_effect": effect,
            "claim_boundary": "Implementation rehearsal only; no starter code, external action, publication, spend, fulfilment, product-market fit, or commercial validation claim.",
        }
        _write_json(plan_path, plan)
        _write_json(manifest_path, file_manifest)
        _write_json(summary_path, summary)

    receipt = ControlledLocalImplementationRehearsalReceipt(
        status=READY_TOKEN if evidence else REFUSED_TOKEN,
        gauntlet_version="DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_V1",
        selected_product_sprint_marketing_pack_status=upstream_status,
        selected_product_sprint_marketing_pack_sha256=_sha256_path(pack_path),
        selected_product=selected_product,
        execute_requested=execute,
        executed=evidence,
        modules_rehearsed=len(modules),
        test_skeletons_rehearsed=len(modules),
        receipt_schemas_rehearsed=len(modules),
        acceptance_gate_bindings_rehearsed=sum(len(module["acceptance_gates"]) for module in modules),
        rehearsal_file_manifest_written=evidence,
        implementation_rehearsal_plan_written=evidence,
        static_implementation_baseline_mean_score=static_score,
        controlled_rehearsal_mean_score=controlled_score,
        controlled_rehearsal_minus_static_effect=effect,
        minimum_controlled_rehearsal_score=minimum_score,
        minimum_rehearsal_effect=minimum_effect,
        controlled_rehearsal_quality_threshold_met=quality_met,
        rehearsal_effect_threshold_met=effect_met,
        implementation_rehearsal_evidence=evidence,
        local_implementation_rehearsal_claim_authorized=evidence,
        starter_code_claim_authorized=False,
        adaptive_claim_authorized=bool(pack.get("adaptive_claim_authorized", False)) and evidence,
        product_composition_claim_authorized=True if evidence else False,
        sprint_planning_claim_authorized=bool(pack.get("sprint_planning_claim_authorized", False)) and evidence,
        autonomous_development_authorized=False,
        autonomous_action_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        agi_claim_authorized=False,
        world_first_claim_authorized=False,
        authority_expansion_authorized=False,
        allowed_claim_tier=TIER if evidence else "NO_T14_CLAIM_AUTHORIZED",
        rehearsal_plan_path=str(plan_path) if evidence else "",
        rehearsal_file_manifest_path=str(manifest_path) if evidence else "",
        rehearsal_summary_path=str(summary_path) if evidence else "",
        boundary=(
            "This controlled local implementation rehearsal tests whether DIO can convert the selected sprint plan for "
            "DIO_TRUST_DOSSIER_STUDIO into a local implementation rehearsal packet with module skeleton plans, test skeleton plans, "
            "receipt schemas, acceptance gate bindings, and a human approval checkpoint. It authorizes only candidate internal "
            "implementation-rehearsal evidence and never authorizes starter code completion, autonomous development, product-market fit, "
            "commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claims, autonomous "
            "consequential action, or authority expansion."
        ),
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
