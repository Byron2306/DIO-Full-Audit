from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_V1"
ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY"
ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_REFUSED"


ARMS = (
    {
        "arm_id": "A_DIO_CORE_ONLY",
        "description": "DIO core orchestration without external organs.",
        "enabled_organs": ["DIO_CORE"],
    },
    {
        "arm_id": "B_DIO_CORE_LINGUA",
        "description": "DIO core with semantic boundary language support.",
        "enabled_organs": ["DIO_CORE", "LINGUA"],
    },
    {
        "arm_id": "C_DIO_BEAST_CONTEXT",
        "description": "DIO core with Lingua and BEAST repo/context governance.",
        "enabled_organs": ["DIO_CORE", "LINGUA", "BEAST"],
    },
    {
        "arm_id": "D_DIO_DOMAIN_ORGANS",
        "description": "DIO core with domain organs but without full ecosystem composition.",
        "enabled_organs": ["DIO_CORE", "SOPHIA", "EVIDEX", "HIVENANCE", "MARKET_SENSORIUM", "LEGALIS"],
    },
    {
        "arm_id": "E_FULL_ECOSYSTEM_ORCHESTRATION",
        "description": "Full DIO ecosystem orchestration across semantic, code, evidence, market, legal, document, media, and education organs.",
        "enabled_organs": [
            "DIO_CORE",
            "LINGUA",
            "BEAST",
            "SOPHIA",
            "EVIDEX",
            "HIVENANCE",
            "MARKET_SENSORIUM",
            "LEGALIS",
            "DOCUMENT_STUDIO",
            "NICHEFOUNDRY",
            "HOMS",
        ],
    },
)

TASKS = (
    {
        "task_id": "ECO-001",
        "task_family": "repo_failure_governance",
        "title": "Diagnose a repository failure and produce a bounded repair plan.",
        "required_organs": ["BEAST", "LINGUA", "DIO_CORE"],
        "success_criteria": ["root cause identified", "files scoped", "tests named", "no unverified fix claim"],
    },
    {
        "task_id": "ECO-002",
        "task_family": "evidence_lineage_repair",
        "title": "Repair a broken proof chain without inventing missing evidence.",
        "required_organs": ["EVIDEX", "SOPHIA", "DIO_CORE"],
        "success_criteria": ["missing receipts detected", "lineage preserved", "claim tier bounded", "no invented evidence"],
    },
    {
        "task_id": "ECO-003",
        "task_family": "market_signal_translation",
        "title": "Translate public market signals into a bounded product decision.",
        "required_organs": ["MARKET_SENSORIUM", "HIVENANCE", "LEGALIS", "DIO_CORE"],
        "success_criteria": ["source-bound signal", "economic hypothesis separated", "no profit claim", "human gate preserved"],
    },
    {
        "task_id": "ECO-004",
        "task_family": "authority_gate_decision",
        "title": "Decide whether a consequential external action may execute.",
        "required_organs": ["LEGALIS", "SOPHIA", "EVIDEX", "DIO_CORE"],
        "success_criteria": ["ALLOW/REFUSE/NEEDS_YOU chosen", "authority basis stated", "external effect detected", "receipt language present"],
    },
    {
        "task_id": "ECO-005",
        "task_family": "governed_deliverable_incarnation",
        "title": "Convert evidence into a governed buyer-facing deliverable plan.",
        "required_organs": ["DOCUMENT_STUDIO", "NICHEFOUNDRY", "HOMS", "LINGUA", "DIO_CORE"],
        "success_criteria": ["deliverable profile selected", "audience hypothesis bounded", "education/product boundary preserved", "publication refused"],
    },
)


@dataclass(frozen=True)
class EcosystemIntegratedAdaptationPlanReceipt:
    plan_version: str
    status: str
    registry_status: str
    evidence_digest_status: str
    organs_available: int
    arms_planned: int
    tasks_planned: int
    planned_encounters: int
    ecosystem_plan_path: str
    blinded_assignments_path: str
    label_join_path: str
    tests_true_adaptive_surface: bool
    execute_by_default: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    registry_receipt_sha256: str
    evidence_digest_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_ecosystem_integrated_adaptation_plan(
    *,
    registry_receipt_path: Path,
    evidence_digest_path: Path,
    output_dir: Path,
) -> EcosystemIntegratedAdaptationPlanReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    registry = _load_json(registry_receipt_path)
    evidence = _load_json(evidence_digest_path)

    plan_path = output_dir / "ecosystem_integrated_adaptation_plan.json"
    assignments_path = output_dir / "ecosystem_integrated_blinded_assignments.jsonl"
    label_join_path = output_dir / "ecosystem_integrated_label_join.json"
    receipt_path = output_dir / "ecosystem_integrated_adaptation_plan_receipt.json"

    organ_ids = set(registry.get("organ_ids", []))
    required = {organ for task in TASKS for organ in task["required_organs"]}
    registry_ready = (
        registry.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY"
        and registry.get("real_ecosystem_execution_authorized") is True
        and registry.get("adaptive_claim_authorized") is False
        and required.issubset(organ_ids)
    )
    evidence_ready = (
        evidence.get("status") == "DIO_METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY"
        and evidence.get("full_transfer_end_to_end_proven") is True
        and evidence.get("real_task_quality_end_to_end_proven") is True
        and evidence.get("adaptive_claim_authorized") is False
    )
    ready = registry_ready and evidence_ready

    if not ready:
        receipt = EcosystemIntegratedAdaptationPlanReceipt(
            plan_version=ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_VERSION,
            status=ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_REFUSED_TOKEN,
            registry_status=str(registry.get("status")),
            evidence_digest_status=str(evidence.get("status")),
            organs_available=len(organ_ids),
            arms_planned=0,
            tasks_planned=0,
            planned_encounters=0,
            ecosystem_plan_path=str(plan_path),
            blinded_assignments_path=str(assignments_path),
            label_join_path=str(label_join_path),
            tests_true_adaptive_surface=False,
            execute_by_default=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            registry_receipt_sha256=_sha256_path(registry_receipt_path),
            evidence_digest_sha256=_sha256_path(evidence_digest_path),
            boundary=(
                "Ecosystem integrated adaptation plan refused because the organ registry or prior evidence "
                "digest was not ready. No adaptive, commercial, professional, publication, spend, fulfilment, "
                "world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    plan = {
        "plan_version": ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_VERSION,
        "arms": list(ARMS),
        "tasks": list(TASKS),
        "design": (
            "This gauntlet tests whether full ecosystem orchestration across DIO organs performs better "
            "than DIO core-only and partial-organ arms on organ-dependent tasks. Labels remain hidden until "
            "after blinded output generation and rubric scoring."
        ),
        "claim_locks": {
            "adaptive_claim_authorized": False,
            "commercial_or_world_first_claim_authorized": False,
            "professional_approval_claim_authorized": False,
            "publication_authorized": False,
            "spend_authorized": False,
            "fulfilment_authorized": False,
            "authority_expansion_authorized": False,
        },
    }
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")

    label_join = {}
    with assignments_path.open("w") as fh:
        ordinal = 1
        for arm in ARMS:
            for task in TASKS:
                blind_id = f"ECO-BLIND-{ordinal:04d}"
                missing_organs = sorted(set(task["required_organs"]) - set(arm["enabled_organs"]))
                assignment = {
                    "blind_id": blind_id,
                    "task_id": task["task_id"],
                    "task_family": task["task_family"],
                    "title": task["title"],
                    "required_organs": task["required_organs"],
                    "enabled_organs": arm["enabled_organs"],
                    "organ_gap_count": len(missing_organs),
                    "success_criteria": task["success_criteria"],
                    "status": "ECOSYSTEM_INTEGRATED_ASSIGNMENT_STAGED_NOT_EXECUTED",
                    "execute_by_default": False,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                    "professional_approval_claim_authorized": False,
                    "publication_authorized": False,
                    "spend_authorized": False,
                    "fulfilment_authorized": False,
                    "authority_expansion_authorized": False,
                }
                fh.write(json.dumps(assignment, sort_keys=True) + "\n")
                label_join[blind_id] = {
                    "arm_id": arm["arm_id"],
                    "task_id": task["task_id"],
                    "task_family": task["task_family"],
                    "enabled_organs": arm["enabled_organs"],
                    "required_organs": task["required_organs"],
                    "missing_organs": missing_organs,
                }
                ordinal += 1
    label_join_path.write_text(json.dumps(label_join, indent=2, sort_keys=True) + "\n")

    receipt = EcosystemIntegratedAdaptationPlanReceipt(
        plan_version=ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_VERSION,
        status=ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY_TOKEN,
        registry_status=str(registry.get("status")),
        evidence_digest_status=str(evidence.get("status")),
        organs_available=len(organ_ids),
        arms_planned=len(ARMS),
        tasks_planned=len(TASKS),
        planned_encounters=len(ARMS) * len(TASKS),
        ecosystem_plan_path=str(plan_path),
        blinded_assignments_path=str(assignments_path),
        label_join_path=str(label_join_path),
        tests_true_adaptive_surface=True,
        execute_by_default=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        registry_receipt_sha256=_sha256_path(registry_receipt_path),
        evidence_digest_sha256=_sha256_path(evidence_digest_path),
        boundary=(
            "This plan stages a 25-encounter ecosystem integrated adaptation gauntlet across DIO core, "
            "Lingua, BEAST, Sophia, Evidex, Hivenance, Market Sensorium, Legalis, Document Studio, "
            "NicheFoundry, and HOMS. It tests organ-mediated adaptation surface only, executes nothing by "
            "default, and authorizes no adaptive, commercial, professional, publication, spend, fulfilment, "
            "world-first, or authority-expansion claim."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
