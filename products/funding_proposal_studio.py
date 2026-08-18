from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from metamorphic.contracts import MetamorphicRole, MetamorphicUnit
from metamorphic.native_execution import execute_resolution
from metamorphic.resolver import build_reference_intent, resolve_intent
from metamorphic.world_lease import acquire_world_lease, build_controlled_world_snapshot


COMPOSITE_UNIT_ID = "funding_proposal_studio"
COMPOSITE_CAPABILITY = "funding_proposal_pack"


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_funding_proposal_studio(
    repo_root: str | Path,
    *,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Execute the existing metamorphic resolver/DAG as a reusable product wrapper.

    This wrapper is not a new execution engine. It delegates selection and native
    work to the already-proved resolver and Studio native executor path.
    """
    root = Path(repo_root).resolve()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    intent, source_text, config = build_reference_intent(root)
    snapshot = build_controlled_world_snapshot(root, now=now)
    lease = acquire_world_lease(root, snapshot=snapshot, composition_id=intent.intent_id)
    resolution = resolve_intent(
        root,
        intent=intent,
        live_buyer_job_text=source_text,
        world_lease=lease,
        live_snapshot=snapshot,
        now=now,
        config=config,
    )
    return execute_resolution(
        root,
        resolution=resolution,
        world_lease=lease,
        live_snapshot=snapshot,
        output_dir=Path(output_dir).resolve(),
        now=None,
    )


def build_funding_proposal_metamorphic_unit(repo_root: str | Path) -> MetamorphicUnit:
    """Return the stable composite unit definition eligible for Phase 9 re-entry."""
    root = Path(repo_root).resolve()
    source_path = Path(__file__).resolve()
    try:
        source_rel = source_path.relative_to(root).as_posix()
    except ValueError:
        source_rel = "products/funding_proposal_studio.py"
        source_path = root / source_rel
    source_digest = _file_digest(source_path)

    return MetamorphicUnit(
        unit_id=COMPOSITE_UNIT_ID,
        version="1.0.0",
        source_digest=source_digest,
        roles=(MetamorphicRole.PRODUCT, MetamorphicRole.CAPABILITY),
        provides=(COMPOSITE_CAPABILITY,),
        requires=(
            "finance_readiness",
            "article_publication",
            "professional_correspondence",
        ),
        executor_id="products.funding_proposal_studio.run_funding_proposal_studio",
        executor_version="1.0.0",
        executor_digest=source_digest,
        input_contract={
            "buyer_job": "prepare a controlled funding proposal pack from messy source material",
            "source_materials": [
                "company information",
                "financial notes",
                "funding opportunity",
                "founder material",
                "supporting documents",
                "constraints",
            ],
        },
        output_contract={
            "artifact_kind": "funding_proposal_pack",
            "controlled_artifact_only": True,
            "components": [
                "finance_readiness",
                "proposal_narrative",
                "submission_correspondence",
            ],
            "content_transform_dataflow_proved": False,
        },
        evidence_contract={
            "world_settlement_required_before_crystallisation": True,
            "beast_crystal_chain_required": True,
            "required_witnesses": ["sensorium", "harmonics", "vns", "seraph", "arda"],
            "native_child_receipts_preserved": True,
            "phase9_reentry_receipt_required_for_verified_use": True,
        },
        quality_contract={
            "all_child_native_executions_must_pass": True,
            "child_quality_contracts_must_be_preserved": True,
            "content_transform_dataflow_claim_must_remain_false_until_separately_proved": True,
        },
        semantic_contract={
            "denotation": [
                "A controlled funding proposal pack composed from existing governed DIO Studios."
            ],
            "affordances": [
                "funding_proposal_pack",
                "finance_readiness",
                "proposal_narrative",
                "submission_correspondence",
            ],
            "prohibitions": [
                "does_not_send_or_submit",
                "does_not_publish",
                "does_not_spend",
                "does_not_process_payment",
                "does_not_claim_customer_acceptance",
                "does_not_claim_commercial_validation",
                "does_not_claim_content_transform_dataflow_until_separately_proved",
                "crystallisation_does_not_mint_authority",
            ],
            "projections": {
                "direct_product": "Funding Proposal Studio",
                "nested_capability": "funding proposal pack capability",
                "technical_proof": "settlement-gated metamorphic composition",
            },
        },
        buyer_projection={
            "default": "Funding Proposal Studio",
            "promise": "Prepare a controlled funding proposal pack from messy source material while preserving evidence and authority boundaries.",
        },
        maturity_state="metamorphic_reference_requires_phase9_receipt",
        authority_ceiling="controlled_artifact_only",
        applicability_fingerprints={
            "policy": (),
            "audience": (),
            "curriculum": (),
            "privacy": (),
            "market": (),
            "runtime": (),
        },
        promotion_rules={
            "world_settlement_required": True,
            "beast_crystallisation_required": True,
            "human_authority_preserved": True,
            "external_effects_remain_refused": True,
            "crystal_never_mints_authority": True,
            "reuse_requires_current_world_lease": True,
        },
        negative_capability_refs=(),
        crystal_refs=("beast:crystal_chain:metamorphic_composition",),
    )
