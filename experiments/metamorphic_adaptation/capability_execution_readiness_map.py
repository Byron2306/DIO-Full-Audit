from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MAP_READY"
REQUIRED_REHEARSAL_STATUS = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_READY"
CLAIM_TIER = "T15_CANDIDATE_CAPABILITY_EXECUTION_READINESS_MAP_EVIDENCE"
VERSION = "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MAP_V1"

CAN_EXECUTE_NOW = "CAN_EXECUTE_NOW"
COULD_EXECUTE_WITH_LOCAL_DEPENDENCY = "COULD_EXECUTE_WITH_LOCAL_DEPENDENCY"
COULD_EXECUTE_WITH_CONFIG = "COULD_EXECUTE_WITH_CONFIG"
HUMAN_GATE_REQUIRED = "HUMAN_GATE_REQUIRED"
AUTHORITY_REFUSED = "AUTHORITY_REFUSED"
NOT_IMPLEMENTED_YET = "NOT_IMPLEMENTED_YET"


@dataclass(frozen=True)
class CapabilityReadiness:
    capability_id: str
    capability_name: str
    organ_or_surface: str
    execution_readiness: str
    could_execute: bool
    may_execute_without_human: bool
    required_local_condition: str
    required_config_condition: str
    required_human_gate: str
    authority_boundary: str
    evidence_required_before_execution: list[str]


@dataclass(frozen=True)
class CapabilityExecutionReadinessReceipt:
    status: str
    gauntlet_version: str
    selected_product: str
    implementation_rehearsal_status: str
    implementation_rehearsal_sha256: str
    execute_requested: bool
    executed: bool
    capabilities_mapped: int
    can_execute_now_count: int
    could_execute_with_local_dependency_count: int
    could_execute_with_config_count: int
    human_gate_required_count: int
    authority_refused_count: int
    not_implemented_yet_count: int
    could_execute_total_count: int
    execution_readiness_map_written: bool
    execution_readiness_summary_written: bool
    execution_readiness_map_path: str
    execution_readiness_summary_path: str
    capability_execution_readiness_evidence: bool
    could_execute_claim_authorized: bool
    actual_execution_authorized: bool
    starter_code_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    autonomous_development_authorized: bool
    authority_expansion_authorized: bool
    product_market_fit_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    allowed_claim_tier: str
    boundary: str


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _capabilities() -> list[CapabilityReadiness]:
    return [
        CapabilityReadiness(
            capability_id="manifest_writer",
            capability_name="Write governed product manifests",
            organ_or_surface="Product Incarnation Studio",
            execution_readiness=CAN_EXECUTE_NOW,
            could_execute=True,
            may_execute_without_human=True,
            required_local_condition="Writable local output directory",
            required_config_condition="Selected product identifier bound",
            required_human_gate="Human reviews before promotion beyond scaffold",
            authority_boundary="May write local manifest artifacts only",
            evidence_required_before_execution=["selected_product", "rehearsal_receipt_sha256"],
        ),
        CapabilityReadiness(
            capability_id="evidence_contract_writer",
            capability_name="Write evidence contract skeletons",
            organ_or_surface="Evidex",
            execution_readiness=CAN_EXECUTE_NOW,
            could_execute=True,
            may_execute_without_human=True,
            required_local_condition="Writable local output directory",
            required_config_condition="Evidence receipt schema bound",
            required_human_gate="Human approves evidence claims before external use",
            authority_boundary="May write local evidence contracts, not certify evidence externally",
            evidence_required_before_execution=["receipt_schema_plan", "acceptance_gate_map"],
        ),
        CapabilityReadiness(
            capability_id="acceptance_plan_writer",
            capability_name="Write acceptance test plans",
            organ_or_surface="BEAST",
            execution_readiness=CAN_EXECUTE_NOW,
            could_execute=True,
            may_execute_without_human=True,
            required_local_condition="Writable local output directory",
            required_config_condition="Sprint work packages bound",
            required_human_gate="Human approves tests before treating them as release gates",
            authority_boundary="May write local acceptance plans only",
            evidence_required_before_execution=["work_packages", "gate_ids"],
        ),
        CapabilityReadiness(
            capability_id="readme_writer",
            capability_name="Write local README scaffold",
            organ_or_surface="Document Studio",
            execution_readiness=CAN_EXECUTE_NOW,
            could_execute=True,
            may_execute_without_human=True,
            required_local_condition="Writable local output directory",
            required_config_condition="Marketing-safe claim pack bound",
            required_human_gate="Human reviews public wording before publication",
            authority_boundary="May write local README drafts, not publish them",
            evidence_required_before_execution=["claim_locks", "safe_positioning_line"],
        ),
        CapabilityReadiness(
            capability_id="local_pytest_runner",
            capability_name="Run local pytest verification",
            organ_or_surface="BEAST",
            execution_readiness=COULD_EXECUTE_WITH_LOCAL_DEPENDENCY,
            could_execute=True,
            may_execute_without_human=False,
            required_local_condition="Python environment with pytest installed and user execution approval",
            required_config_condition="Test paths selected",
            required_human_gate="Human explicitly runs or approves local test execution",
            authority_boundary="May report local test output, not infer commercial readiness",
            evidence_required_before_execution=["test_plan", "local_environment"],
        ),
        CapabilityReadiness(
            capability_id="starter_module_writer",
            capability_name="Write starter Python module skeletons",
            organ_or_surface="Product Incarnation Studio",
            execution_readiness=COULD_EXECUTE_WITH_LOCAL_DEPENDENCY,
            could_execute=True,
            may_execute_without_human=False,
            required_local_condition="Writable repository path and explicit human approval to create code files",
            required_config_condition="Module names and public APIs bound",
            required_human_gate="Human approves transition from rehearsal to starter code generation",
            authority_boundary="May write local starter code only after gate approval",
            evidence_required_before_execution=["implementation_rehearsal_plan", "human_gate"],
        ),
        CapabilityReadiness(
            capability_id="starter_test_writer",
            capability_name="Write starter test skeletons",
            organ_or_surface="BEAST",
            execution_readiness=COULD_EXECUTE_WITH_LOCAL_DEPENDENCY,
            could_execute=True,
            may_execute_without_human=False,
            required_local_condition="Writable repository test path and explicit human approval",
            required_config_condition="Acceptance gate identifiers bound",
            required_human_gate="Human approves starter test generation",
            authority_boundary="May write local test skeletons only after gate approval",
            evidence_required_before_execution=["acceptance_test_plan", "human_gate"],
        ),
        CapabilityReadiness(
            capability_id="outlook_draft_surface",
            capability_name="Prepare outbound email draft surface",
            organ_or_surface="Vesper / Outlook Smart Bot",
            execution_readiness=COULD_EXECUTE_WITH_CONFIG,
            could_execute=True,
            may_execute_without_human=False,
            required_local_condition="Draft-only mail connector available",
            required_config_condition="Recipient, purpose, consent, and draft-only mode configured",
            required_human_gate="Human reviews and sends manually",
            authority_boundary="May draft only, never send autonomously",
            evidence_required_before_execution=["recipient_source", "draft_only_receipt", "human_review_required"],
        ),
        CapabilityReadiness(
            capability_id="market_signal_refresh",
            capability_name="Refresh public market/friction signals",
            organ_or_surface="Market Sensorium",
            execution_readiness=COULD_EXECUTE_WITH_CONFIG,
            could_execute=True,
            may_execute_without_human=False,
            required_local_condition="Configured public signal sources",
            required_config_condition="Source allowlist and recency policy configured",
            required_human_gate="Human reviews signal interpretation before build commitment",
            authority_boundary="May observe and summarize public signals, not claim demand proof",
            evidence_required_before_execution=["source_allowlist", "timestamp", "signal_receipts"],
        ),
        CapabilityReadiness(
            capability_id="external_publication",
            capability_name="Publish public product page or campaign",
            organ_or_surface="Document Studio / NicheFoundry",
            execution_readiness=HUMAN_GATE_REQUIRED,
            could_execute=True,
            may_execute_without_human=False,
            required_local_condition="Publication surface available",
            required_config_condition="Human-approved copy and destination configured",
            required_human_gate="Human explicitly publishes after review",
            authority_boundary="DIO may prepare assets, not publish autonomously",
            evidence_required_before_execution=["human_publication_approval", "safe_claim_pack"],
        ),
        CapabilityReadiness(
            capability_id="commercial_checkout_probe",
            capability_name="Prepare controlled checkout validation probe",
            organ_or_surface="Commercial Truth Layer",
            execution_readiness=HUMAN_GATE_REQUIRED,
            could_execute=True,
            may_execute_without_human=False,
            required_local_condition="Sandbox payment/test mode available",
            required_config_condition="No real charge, no fulfilment, no customer promise configured",
            required_human_gate="Human approves any sandbox checkout test",
            authority_boundary="May prepare sandbox probe only, not claim revenue or validation",
            evidence_required_before_execution=["sandbox_mode_receipt", "no_real_customer_claim"],
        ),
        CapabilityReadiness(
            capability_id="publish_campaign",
            capability_name="Autonomously publish, spend, contact, or fulfil campaign",
            organ_or_surface="NicheFoundry / External surfaces",
            execution_readiness=AUTHORITY_REFUSED,
            could_execute=False,
            may_execute_without_human=False,
            required_local_condition="Not applicable",
            required_config_condition="Not permitted by authority boundary",
            required_human_gate="Human authority cannot be bypassed",
            authority_boundary="REFUSE autonomous external action, spending, publication, contact, and fulfilment",
            evidence_required_before_execution=["refusal_receipt"],
        ),
    ]


def build_capability_execution_readiness_map(
    implementation_rehearsal_path: Path | str,
    output_dir: Path | str,
    execute: bool = False,
) -> CapabilityExecutionReadinessReceipt:
    rehearsal_path = Path(implementation_rehearsal_path)
    out_dir = Path(output_dir)
    rehearsal = _load_json(rehearsal_path)

    rehearsal_status = str(rehearsal.get("status", ""))
    if rehearsal_status != REQUIRED_REHEARSAL_STATUS:
        raise ValueError(
            "Capability execution readiness map requires a controlled local implementation rehearsal receipt. "
            f"Got {rehearsal_status!r}."
        )
    if rehearsal.get("starter_code_claim_authorized") is not False:
        raise ValueError("Input rehearsal must not claim starter code completion.")
    if rehearsal.get("authority_expansion_authorized") is not False:
        raise ValueError("Input rehearsal must preserve authority-expansion lock.")

    capabilities = _capabilities()
    readiness_counts = {
        CAN_EXECUTE_NOW: 0,
        COULD_EXECUTE_WITH_LOCAL_DEPENDENCY: 0,
        COULD_EXECUTE_WITH_CONFIG: 0,
        HUMAN_GATE_REQUIRED: 0,
        AUTHORITY_REFUSED: 0,
        NOT_IMPLEMENTED_YET: 0,
    }
    for capability in capabilities:
        readiness_counts[capability.execution_readiness] += 1

    map_path = out_dir / "capability_execution_readiness_map.json"
    summary_path = out_dir / "capability_execution_readiness_summary.json"
    receipt_path = out_dir / "capability_execution_readiness_map_receipt.json"

    readiness_payload = {
        "status": READY_TOKEN,
        "selected_product": rehearsal.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"),
        "readiness_statuses": list(readiness_counts.keys()),
        "capabilities": [asdict(capability) for capability in capabilities],
        "boundary": "Could-execute classification is not execution authorization. Human gates and authority locks remain binding.",
    }
    summary_payload = {
        "status": READY_TOKEN,
        "selected_product": readiness_payload["selected_product"],
        "capabilities_mapped": len(capabilities),
        "readiness_counts": readiness_counts,
        "could_execute_total_count": sum(1 for capability in capabilities if capability.could_execute),
        "actual_execution_authorized": False,
        "authority_expansion_authorized": False,
    }

    if execute:
        _write_json(map_path, readiness_payload)
        _write_json(summary_path, summary_payload)

    receipt = CapabilityExecutionReadinessReceipt(
        status=READY_TOKEN,
        gauntlet_version=VERSION,
        selected_product=str(readiness_payload["selected_product"]),
        implementation_rehearsal_status=rehearsal_status,
        implementation_rehearsal_sha256=_sha256_path(rehearsal_path),
        execute_requested=execute,
        executed=execute,
        capabilities_mapped=len(capabilities),
        can_execute_now_count=readiness_counts[CAN_EXECUTE_NOW],
        could_execute_with_local_dependency_count=readiness_counts[COULD_EXECUTE_WITH_LOCAL_DEPENDENCY],
        could_execute_with_config_count=readiness_counts[COULD_EXECUTE_WITH_CONFIG],
        human_gate_required_count=readiness_counts[HUMAN_GATE_REQUIRED],
        authority_refused_count=readiness_counts[AUTHORITY_REFUSED],
        not_implemented_yet_count=readiness_counts[NOT_IMPLEMENTED_YET],
        could_execute_total_count=sum(1 for capability in capabilities if capability.could_execute),
        execution_readiness_map_written=execute,
        execution_readiness_summary_written=execute,
        execution_readiness_map_path=str(map_path),
        execution_readiness_summary_path=str(summary_path),
        capability_execution_readiness_evidence=True,
        could_execute_claim_authorized=True,
        actual_execution_authorized=False,
        starter_code_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        autonomous_development_authorized=False,
        authority_expansion_authorized=False,
        product_market_fit_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        allowed_claim_tier=CLAIM_TIER,
        boundary=(
            "This capability execution readiness map tests whether DIO can classify which selected-product "
            "capabilities can execute now, could execute with local dependencies or configuration, require human "
            "gates, or are authority-refused. It authorizes only candidate internal could-execute readiness evidence "
            "and never authorizes actual execution, starter code completion, autonomous development, product-market fit, "
            "commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claims, "
            "autonomous consequential action, or authority expansion."
        ),
    )

    if execute:
        _write_json(receipt_path, asdict(receipt))

    return receipt
