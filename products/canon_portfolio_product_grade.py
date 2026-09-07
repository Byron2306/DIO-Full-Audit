from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HISTORICAL_53_ANCHOR_SCHEMA = "dio.historical_evidence_anchor.v1"
HISTORICAL_53_RECEIPT_SCHEMA = "dio.professional_evidence.multitier_53_receipt.v1"
HISTORICAL_53_ACCEPTANCE_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED"
HISTORICAL_53_SOURCE_REPOSITORY = "Byron2306/DIO-Workflows"
HISTORICAL_53_SOURCE_COMMIT = "3119e290efd62cdeccd3f4f5938cc5be85014464"
HISTORICAL_53_SOURCE_PATH = "products/proof/receipts/PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json"
HISTORICAL_53_SOURCE_BLOB = "7ffeb400a4ec0ffd51d0a10c3035d3303fd24c4e"
HISTORICAL_53_VARIANTS = ["normal", "messy", "adversarial"]


def load_historical_53_anchor(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("historical 53 anchor must be a JSON object")
    return value


def validate_historical_53_anchor(anchor: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if anchor.get("schema") != HISTORICAL_53_ANCHOR_SCHEMA:
        blockers.append("historical_53_anchor_schema_invalid")
    if anchor.get("source_repository") != HISTORICAL_53_SOURCE_REPOSITORY:
        blockers.append("historical_53_source_repository_mismatch")
    if anchor.get("source_commit") != HISTORICAL_53_SOURCE_COMMIT:
        blockers.append("historical_53_source_commit_mismatch")
    if anchor.get("source_path") != HISTORICAL_53_SOURCE_PATH:
        blockers.append("historical_53_source_path_mismatch")
    if anchor.get("source_git_blob_sha") != HISTORICAL_53_SOURCE_BLOB:
        blockers.append("historical_53_blob_identity_mismatch")
    if anchor.get("acceptance_token") != HISTORICAL_53_ACCEPTANCE_TOKEN:
        blockers.append("historical_53_acceptance_token_invalid")
    if anchor.get("receipt_schema") != HISTORICAL_53_RECEIPT_SCHEMA:
        blockers.append("historical_53_receipt_schema_invalid")
    if anchor.get("canonical_incarnation_count") != 53:
        blockers.append("historical_53_product_count_mismatch")
    if anchor.get("variant_count") != 3 or anchor.get("variants") != HISTORICAL_53_VARIANTS:
        blockers.append("historical_53_variant_contract_mismatch")
    if anchor.get("journey_count") != 159 or anchor.get("verified_journey_count") != 159:
        blockers.append("historical_53_journey_count_mismatch")
    if anchor.get("refused_journey_count") != 0:
        blockers.append("historical_53_refused_journeys_present")
    if anchor.get("authority_created") is not False or anchor.get("external_effects") is not False:
        blockers.append("historical_53_authority_boundary_drift")
    if anchor.get("commercial_validation") != "UNPROVED":
        blockers.append("historical_53_commercial_boundary_drift")
    return sorted(set(blockers))
