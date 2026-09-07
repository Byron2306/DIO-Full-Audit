from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


T24_CANONICAL_CONTINUITY_DIGEST_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_T24_CANONICAL_CONTINUITY_DIGEST_GATE_V1"
)
T24_CANONICAL_CONTINUITY_DIGEST_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T24_CANONICAL_CONTINUITY_DIGEST_READY"
)
T24_CANONICAL_CONTINUITY_DIGEST_GAP_PENDING_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T24_CANONICAL_CONTINUITY_DIGEST_GAP_PENDING"
)
T24_CLAIM_TIER = "T24_INTERNAL_CANONICAL_T1_T23_CONTINUITY_DIGEST"

EXPECTED_TIERS = [f"T{i}" for i in range(1, 24)]

TIER_PATTERNS = {
    "T1": ["T1_", "FIXTURE_MECHANICS_PROVEN"],
    "T2": ["T2_", "REAL_PILOT_COMPATIBILITY"],
    "T3": ["T3_", "FULL_NATIVE_COMPATIBILITY"],
    "T4": ["T4_", "REAL_TASK_QUALITY_PIPELINE"],
    "T5": ["T5_", "ECOSYSTEM_ADAPTIVE_EVIDENCE"],
    "T6": ["T6_", "SEQUENTIAL_RETAINED_ECOSYSTEM", "RETAINED_ECOSYSTEM_ADAPTATION"],
    "T7": ["T7_", "MARKET_COMMAND", "SENSORIUM_PIVOT"],
    "T8": ["T8_", "ADAPTIVE_LINGUISTIC"],
    "T9": ["T9_", "AUDIENCE_MORPHOLOGY"],
    "T10": ["T10_", "ATLAS_GUIDED_PRODUCT_COMPOSITION"],
    "T11": ["T11_", "PRODUCT_INCARNATION"],
    "T12": ["T12_", "PRODUCT_PORTFOLIO"],
    "T13": ["T13_", "SELECTED_PRODUCT_SPRINT"],
    "T14": ["T14_", "CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL"],
    "T15": ["T15_", "CAPABILITY_EXECUTION_READINESS"],
    "T16": ["T16_", "CONTROLLED_STARTER_CODE"],
    "T17": ["T17_", "LOCAL_STARTER_CODE_ACCEPTANCE"],
    "T18": ["T18_", "HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN"],
    "T19": ["T19_", "HUMAN_GATED_LOCAL_RELEASE_CANDIDATE"],
    "T20": ["T20_", "HUMAN_APPROVAL_DECISION_PACKET"],
    "T21": ["T21_", "HUMAN_DECISION_APPLICATION"],
    "T22": ["T22_", "HTML_PROOF_SURFACE"],
    "T23": ["T23_", "DOSSIER_LINKING", "HTML_PROOF_SURFACE_DOSSIER"],
}

TEXT_EXTENSIONS = {".json", ".jsonl", ".md", ".txt", ".html"}


@dataclass(frozen=True)
class T24CanonicalContinuityDigestReceipt:
    gate_version: str
    status: str
    allowed_claim_tier: str
    receipt_pack_dir: str
    extra_receipt_dirs: list[str]
    stages_expected: int
    stages_source_bound: int
    gaps_pending: list[str]
    tiers_present: dict[str, bool]
    tier_sources: dict[str, list[str]]
    canonical_sequence: list[str]
    continuity_digest_authorized: bool
    source_bound: bool
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


def _iter_text_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in paths:
        if root.exists() and root.is_file() and root.suffix.lower() in TEXT_EXTENSIONS:
            files.append(root)
        elif root.exists() and root.is_dir():
            files.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS
            )
    return sorted(files)


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except UnicodeDecodeError:
        return ""


def _normalise_tier_mentions(text: str) -> set[str]:
    mentions: set[str] = set()
    for match in re.finditer(r"\bT([1-9]|1[0-9]|2[0-3])(?:_|\b)", text):
        mentions.add(f"T{match.group(1)}")
    upper = text.upper()
    for tier, patterns in TIER_PATTERNS.items():
        if any(pattern in upper for pattern in patterns):
            mentions.add(tier)
    return mentions


def build_t24_canonical_continuity_digest(
    *,
    receipt_pack_dir: Path,
    extra_receipt_dirs: list[Path],
    output_path: Path,
) -> T24CanonicalContinuityDigestReceipt:
    scan_roots = [receipt_pack_dir, *extra_receipt_dirs]
    source_bound = receipt_pack_dir.exists() and receipt_pack_dir.is_dir()
    tier_sources: dict[str, list[str]] = {tier: [] for tier in EXPECTED_TIERS}

    for file_path in _iter_text_files(scan_roots):
        text = _safe_read(file_path)
        for tier in _normalise_tier_mentions(text):
            if tier in tier_sources:
                tier_sources[tier].append(str(file_path))

    tier_sources = {
        tier: sorted(set(paths))[:20]
        for tier, paths in tier_sources.items()
    }
    tiers_present = {tier: bool(paths) for tier, paths in tier_sources.items()}
    gaps_pending = [tier for tier in EXPECTED_TIERS if not tiers_present[tier]]
    stages_source_bound = sum(1 for present in tiers_present.values() if present)
    ready = source_bound and not gaps_pending

    receipt = T24CanonicalContinuityDigestReceipt(
        gate_version=T24_CANONICAL_CONTINUITY_DIGEST_VERSION,
        status=(
            T24_CANONICAL_CONTINUITY_DIGEST_READY_TOKEN
            if ready
            else T24_CANONICAL_CONTINUITY_DIGEST_GAP_PENDING_TOKEN
        ),
        allowed_claim_tier=T24_CLAIM_TIER if ready else "T24_GAP_PENDING_NO_CANONICAL_CONTINUITY_CLAIM",
        receipt_pack_dir=str(receipt_pack_dir),
        extra_receipt_dirs=[str(path) for path in extra_receipt_dirs],
        stages_expected=len(EXPECTED_TIERS),
        stages_source_bound=stages_source_bound,
        gaps_pending=gaps_pending,
        tiers_present=tiers_present,
        tier_sources=tier_sources,
        canonical_sequence=EXPECTED_TIERS,
        continuity_digest_authorized=ready,
        source_bound=source_bound,
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
            "This T24 gate builds a canonical T1 through T23 continuity digest from source-bound receipt evidence. "
            "It authorizes only a continuity map of internal controlled evidence stages. It does not authorize actual "
            "product execution, product capability execution, external use, external deployment, autonomous development, "
            "commercial validation, product-market fit, professional approval, publication, spend, fulfilment, AGI, "
            "world-first status, autonomous consequential action, or authority expansion."
            if ready
            else "T24 canonical continuity digest remains gap-pending because one or more expected T1 through T23 stages "
            "were not source-bound in the scanned receipt roots. No execution, deployment, commercial, professional, "
            "publication, spend, fulfilment, AGI, world-first, autonomous-action, or authority-expansion claims are authorized."
        ),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
