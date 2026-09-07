from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_GATE_V1"
)
T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_READY"
)
T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_REFUSED_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_REFUSED"
)
T24_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_T24_CANONICAL_CONTINUITY_DIGEST_READY"
T25_CLAIM_TIER = "T25_INTERNAL_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER"

STAGE_LABELS: dict[str, str] = {
    "T1": "fixture mechanics proven, no adaptive claim",
    "T2": "real pilot compatibility and blind pipeline only",
    "T3": "full native compatibility blind factorial pipeline only",
    "T4": "real task-quality pipeline exercised, no adaptive claim",
    "T5": "bounded ecosystem adaptive evidence",
    "T6": "retained ecosystem adaptation candidate evidence",
    "T7": "market-command sensorium pivoting",
    "T8": "adaptive linguistic market recomposition",
    "T9": "audience morphology semantic recomposition",
    "T10": "ATLAS-guided domain product composition",
    "T11": "governed product-incarnation development",
    "T12": "governed product portfolio prioritization",
    "T13": "selected-product sprint planning",
    "T14": "controlled local implementation rehearsal",
    "T15": "capability execution readiness mapping",
    "T16": "controlled local starter-code generation",
    "T17": "local starter-code acceptance verification",
    "T18": "human-gated product capability dry run",
    "T19": "human-gated local release-candidate packaging",
    "T20": "human approval decision packet",
    "T21": "human decision application",
    "T22": "HTML proof surface generation",
    "T23": "HTML proof surface dossier linking",
}

PRIMARY_SOURCE_HINTS: dict[str, list[str]] = {
    "T1": ["fixture_experiment_digest.json", "transfer_claim_gate.json"],
    "T2": ["real_pilot_digest.json", "real_pilot_claim_gate.json"],
    "T3": ["full_controlled_transfer_digest.json", "full_controlled_transfer_claim_gate.json"],
    "T4": ["real_task_quality_digest.json", "adaptive_evidence_verdict.json"],
    "T5": ["ecosystem_adaptive_evidence_verdict.json", "ecosystem_evidence_rehydration_receipt.json"],
    "T6": ["sequential_retained_ecosystem_gauntlet_receipt.json"],
    "T7": [
        "market_command_marketing_proof_pack_receipt.json",
        "market_command_sensorium_pivot_gauntlet_receipt.json",
        "market_command_sensorium_pivot_outputs.jsonl",
    ],
    "T8": ["adaptive_linguistic_marketing_proof_pack_receipt.json", "adaptive_linguistic_pivot_gauntlet_receipt.json"],
    "T9": ["audience_morphology_recomposition_gauntlet_receipt.json"],
    "T10": ["atlas_product_marketing_proof_pack_receipt.json", "atlas_guided_product_composition_gauntlet_receipt.json"],
    "T11": ["PRODUCT_INCARNATION_STUDIO_GAUNTLET_RECEIPT.json", "INCARNATION_STUDIO_RECEIPT.json"],
    "T12": ["product_portfolio_marketing_proof_pack_receipt.json", "product_portfolio_prioritization_gauntlet_receipt.json"],
    "T13": ["selected_product_sprint_planning_gauntlet_receipt.json", "selected_product_sprint_marketing_proof_pack_receipt.json"],
    "T14": ["controlled_local_implementation_rehearsal_receipt.json"],
    "T15": ["capability_execution_readiness_map_receipt.json"],
    "T16": ["controlled_starter_code_generation_receipt.json"],
    "T17": ["local_starter_code_acceptance_verification_receipt.json"],
    "T18": ["human_gated_product_capability_dry_run_receipt.json"],
    "T19": ["t19_human_gated_local_release_candidate_receipt.json"],
    "T20": ["t20_human_approval_decision_packet_receipt.json"],
    "T21": ["t21_human_decision_application_receipt.json"],
    "T22": ["t22_html_proof_surface_generation_receipt.json"],
    "T23": ["t23_html_proof_surface_dossier_linking_receipt.json"],
}

STAGE_SOURCE_BLOCKLIST: dict[str, list[str]] = {
    "T7": ["adaptive_linguistic", "audience_morphology", "atlas_guided", "product_incarnation"],
    "T8": ["market_command", "audience_morphology", "atlas_guided", "product_incarnation"],
    "T9": ["market_command", "adaptive_linguistic", "atlas_guided", "product_incarnation"],
}

BREAKTHROUGH_LEDGER: list[dict[str, str]] = [
    {"stage": "T5", "finding": "bounded ecosystem adaptation", "summary": "Full ecosystem orchestration outperformed DIO core-only on organ-dependent tasks in the controlled harness."},
    {"stage": "T6", "finding": "retained sequential adaptation", "summary": "DIO produced candidate retained-adaptation evidence across sequential encounters without code-change authorization between encounters."},
    {"stage": "T7", "finding": "market-command sensorium pivoting", "summary": "DIO detected market and friction signal pressure, abandoned weaker static routes, and issued bounded pivot commands while preserving proof locks."},
    {"stage": "T8", "finding": "adaptive linguistic market recomposition", "summary": "DIO recomposed audience language, proof emphasis, risk posture, and permitted vocabulary after market and friction shifts."},
    {"stage": "T9", "finding": "audience morphology recomposition", "summary": "DIO adapted messaging to distinct audience morphologies while preserving forbidden-claim, human-gate, and authority boundaries."},
    {"stage": "T10", "finding": "ATLAS-guided product composition", "summary": "DIO converted market signals and work maps into governed domain product compositions with evidence spines and authority boundaries."},
    {"stage": "T11", "finding": "governed product incarnation", "summary": "DIO incarnated product compositions into governed starter scaffolds with manifests, evidence contracts, acceptance paths, and READMEs."},
    {"stage": "T12", "finding": "portfolio prioritization", "summary": "DIO prioritized governed product opportunities without treating internal prioritization as external demand proof."},
    {"stage": "T16", "finding": "controlled starter-code generation", "summary": "DIO generated a receipt-bound local starter-code scaffold for DIO_TRUST_DOSSIER_STUDIO while blocking execution and deployment claims."},
    {"stage": "T18", "finding": "human-gated capability dry run", "summary": "DIO ran synthetic internal inputs through the product candidate and produced draft trust dossier artifacts with human gate checks."},
    {"stage": "T22", "finding": "HTML proof surface generation", "summary": "DIO generated a local static HTML proof surface for human inspection of the receipt-bound product candidate."},
    {"stage": "T23", "finding": "linked dossier inspection", "summary": "DIO linked the draft dossiers into the local proof surface, turning the receipt chain into an inspectable product proof interface."},
]


@dataclass(frozen=True)
class T25StageSourcePurificationBreakthroughLedgerReceipt:
    gate_version: str
    status: str
    allowed_claim_tier: str
    t24_status: str
    t24_receipt_sha256: str
    source_bound: bool
    stages_expected: int
    stages_source_bound: int
    gaps_pending: list[str]
    stage_sources_purified: bool
    primary_stage_sources: dict[str, str]
    stage_labels: dict[str, str]
    breakthrough_count: int
    breakthrough_ledger: list[dict[str, str]]
    breakthrough_ledger_written: bool
    markdown_output_path: str
    marketing_safe_breakthrough_summary_authorized: bool
    actual_product_execution_authorized: bool
    product_capability_execution_authorized: bool
    external_use_authorized: bool
    external_deployment_authorized: bool
    autonomous_development_authorized: bool
    autonomous_action_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    agi_claim_authorized: bool
    world_first_claim_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_bool_map(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {str(k): v is True for k, v in value.items()}


def _flatten_sources(tier_sources: object) -> list[str]:
    if not isinstance(tier_sources, dict):
        return []
    flattened: list[str] = []
    for raw_sources in tier_sources.values():
        if isinstance(raw_sources, list):
            flattened.extend(str(source) for source in raw_sources)
    return flattened


def _allowed_for_stage(stage: str, source: str) -> bool:
    lowered = source.lower()
    return not any(blocked in lowered for blocked in STAGE_SOURCE_BLOCKLIST.get(stage, []))


def _pick_primary_source(stage: str, sources: list[str], all_sources: list[str] | None = None) -> str:
    hints = PRIMARY_SOURCE_HINTS.get(stage, [])
    normalized = [str(source) for source in sources if _allowed_for_stage(stage, str(source))]
    global_normalized = [str(source) for source in (all_sources or []) if _allowed_for_stage(stage, str(source))]

    for candidate_pool in [normalized, global_normalized]:
        for hint in hints:
            for source in candidate_pool:
                if source.endswith(hint):
                    return source

    non_manifest = [source for source in normalized if not source.endswith("RECEIPT_PACK_MANIFEST.json")]
    receipt_like = [source for source in non_manifest if source.endswith("_receipt.json") or source.endswith("RECEIPT.json")]
    if receipt_like:
        return sorted(receipt_like, key=lambda s: (len(s), s))[0]
    if non_manifest:
        return sorted(non_manifest, key=lambda s: (len(s), s))[0]
    return sorted(normalized)[0] if normalized else ""


def _purify_sources(tier_sources: object) -> dict[str, str]:
    purified: dict[str, str] = {f"T{i}": "" for i in range(1, 24)}
    if not isinstance(tier_sources, dict):
        return purified
    all_sources = _flatten_sources(tier_sources)
    for i in range(1, 24):
        stage = f"T{i}"
        raw_sources = tier_sources.get(stage, [])
        if isinstance(raw_sources, list):
            purified[stage] = _pick_primary_source(stage, [str(source) for source in raw_sources], all_sources)
    return purified


def _render_markdown(primary_sources: dict[str, str]) -> str:
    lines = [
        "# DIO Metamorphic Adaptation Breakthrough Ledger",
        "",
        "This ledger purifies the T1-T23 continuity map into one primary source per stage and records the marketing-safe breakthrough findings. It is internal controlled evidence only.",
        "",
        "## Canonical stage map",
        "",
    ]
    for i in range(1, 24):
        stage = f"T{i}"
        label = STAGE_LABELS[stage]
        source = primary_sources.get(stage, "")
        lines.append(f"- {stage}: {label}")
        lines.append(f"  - Primary source: `{source}`")
    lines.extend(["", "## Major breakthrough ledger", ""])
    for item in BREAKTHROUGH_LEDGER:
        lines.append(f"### {item['stage']}: {item['finding']}")
        lines.append("")
        lines.append(item["summary"])
        lines.append("")
    lines.extend([
        "## Boundary locks",
        "",
        "- Not commercial validation.",
        "- Not product-market fit.",
        "- Not AGI.",
        "- Not world-first status.",
        "- No autonomous external action, publication, spending, fulfilment, contact, professional approval, or authority expansion.",
        "",
    ])
    return "\n".join(lines)


def build_t25_stage_source_purification_breakthrough_ledger(
    *,
    t24_receipt_path: Path,
    receipt_output_path: Path,
    markdown_output_path: Path,
) -> T25StageSourcePurificationBreakthroughLedgerReceipt:
    t24 = _load_json(t24_receipt_path)
    receipt_output_path.parent.mkdir(parents=True, exist_ok=True)

    source_bound = t24_receipt_path.exists() and t24_receipt_path.is_file()
    t24_status = str(t24.get("status", ""))
    tiers_present = _as_bool_map(t24.get("tiers_present", {}))
    gaps_pending = [str(item) for item in t24.get("gaps_pending", [])]
    stages_expected = int(t24.get("stages_expected", 0) or 0)
    stages_source_bound = int(t24.get("stages_source_bound", 0) or 0)

    all_expected_present = all(tiers_present.get(f"T{i}") is True for i in range(1, 24))
    boundary_locks_preserved = all(
        t24.get(key) is False
        for key in [
            "actual_product_execution_authorized",
            "product_capability_execution_authorized",
            "external_use_authorized",
            "external_deployment_authorized",
            "autonomous_development_authorized",
            "autonomous_action_claim_authorized",
            "commercial_validation_claim_authorized",
            "product_market_fit_claim_authorized",
            "professional_approval_claim_authorized",
            "publication_authorized",
            "spend_authorized",
            "fulfilment_authorized",
            "agi_claim_authorized",
            "world_first_claim_authorized",
            "authority_expansion_authorized",
        ]
    )

    primary_sources = _purify_sources(t24.get("tier_sources", {}))

    ready = (
        source_bound
        and t24_status == T24_READY_TOKEN
        and t24.get("continuity_digest_authorized") is True
        and stages_expected == 23
        and stages_source_bound == 23
        and gaps_pending == []
        and all_expected_present
        and boundary_locks_preserved
    )

    if ready:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(_render_markdown(primary_sources))

    receipt = T25StageSourcePurificationBreakthroughLedgerReceipt(
        gate_version=T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_VERSION,
        status=T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_READY_TOKEN if ready else T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_REFUSED_TOKEN,
        allowed_claim_tier=T25_CLAIM_TIER if ready else "T25_REFUSED_UNPURIFIED_OR_INCOMPLETE_STAGE_CHAIN",
        t24_status=t24_status,
        t24_receipt_sha256=_sha256_path(t24_receipt_path),
        source_bound=source_bound,
        stages_expected=stages_expected,
        stages_source_bound=stages_source_bound,
        gaps_pending=gaps_pending,
        stage_sources_purified=ready,
        primary_stage_sources=primary_sources if ready else {},
        stage_labels=STAGE_LABELS if ready else {},
        breakthrough_count=len(BREAKTHROUGH_LEDGER) if ready else 0,
        breakthrough_ledger=BREAKTHROUGH_LEDGER if ready else [],
        breakthrough_ledger_written=ready,
        markdown_output_path=str(markdown_output_path) if ready else "",
        marketing_safe_breakthrough_summary_authorized=ready,
        actual_product_execution_authorized=False,
        product_capability_execution_authorized=False,
        external_use_authorized=False,
        external_deployment_authorized=False,
        autonomous_development_authorized=False,
        autonomous_action_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        agi_claim_authorized=False,
        world_first_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "T25 purifies the source-bound T1-T23 continuity digest into one primary stage source per stage and writes a marketing-safe breakthrough ledger. It authorizes only internal controlled summary language. It does not authorize product execution, external use, deployment, commercial validation, product-market fit, professional approval, publication, spend, fulfilment, AGI, world-first status, autonomous external action, or authority expansion."
            if ready
            else "T25 refused because the T24 continuity digest was incomplete, unbound, or missing preserved boundary locks. No breakthrough summary, release, execution, deployment, commercial, professional, publication, spend, fulfilment, AGI, world-first, autonomous-action, or authority-expansion claims are authorized."
        ),
    )

    receipt_output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
