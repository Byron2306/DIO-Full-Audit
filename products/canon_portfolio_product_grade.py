from __future__ import annotations

import hashlib
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

EXTENSION_RECEIPT_SCHEMA = "dio.product_grade.canon_extension_gauntlet_receipt.v2"
EXTENSION_ACCEPTANCE_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"

PORTFOLIO_SCHEMA = "dio.product_grade.canon_portfolio_68_x3_receipt.v1"
PORTFOLIO_BASELINE_TOKEN = "DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_BASELINE_MEASURED"
PORTFOLIO_VERIFIED_TOKEN = "DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED"
PORTFOLIO_RECEIPT_FILENAME = "CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_RECEIPT.json"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def validate_extension_15x3_receipt(receipt: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if receipt.get("schema") != EXTENSION_RECEIPT_SCHEMA:
        blockers.append("canon_extension_receipt_schema_invalid")
    if receipt.get("acceptance_token") != EXTENSION_ACCEPTANCE_TOKEN:
        blockers.append("canon_extension_acceptance_token_invalid")
    if receipt.get("extension_count") != 15:
        blockers.append("canon_extension_product_count_mismatch")
    if receipt.get("variants_per_extension") != 3:
        blockers.append("canon_extension_variant_contract_mismatch")
    if receipt.get("controlled_journey_count") != 45 or receipt.get("verified_journey_count") != 45:
        blockers.append("canon_extension_journey_count_mismatch")
    if receipt.get("refused_journey_count") != 0:
        blockers.append("canon_extension_refused_journeys_present")
    if receipt.get("product_grade_verified_count") != 15 or receipt.get("product_grade_refuse_count") != 0:
        blockers.append("canon_extension_productgrade_count_mismatch")
    if receipt.get("all_product_grade_verified") is not True:
        blockers.append("canon_extension_productgrade_not_all_verified")
    if receipt.get("external_effects") is not False or receipt.get("authority_created") is not False:
        blockers.append("canon_extension_authority_boundary_drift")
    if receipt.get("commercial_validation") != "UNPROVED":
        blockers.append("canon_extension_commercial_boundary_drift")
    fingerprint = str(receipt.get("portfolio_fingerprint") or "")
    if not fingerprint.startswith("sha256:") or len(fingerprint) != 71:
        blockers.append("canon_extension_fingerprint_missing")
    return sorted(set(blockers))


def run_canon_portfolio_product_grade(
    *,
    historical_anchor_path: Path,
    extension_receipt: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    historical_anchor_path = Path(historical_anchor_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    historical_before = historical_anchor_path.read_bytes()
    anchor = load_historical_53_anchor(historical_anchor_path)
    historical_blockers = validate_historical_53_anchor(anchor)
    extension_blockers = validate_extension_15x3_receipt(extension_receipt)
    blockers = sorted(set(historical_blockers + extension_blockers))

    historical_verified_products = 53 if not historical_blockers else 0
    historical_verified_journeys = 159 if not historical_blockers else 0
    extension_verified_products = (
        int(extension_receipt.get("product_grade_verified_count") or 0)
        if not extension_blockers
        else 0
    )
    extension_verified_journeys = (
        int(extension_receipt.get("verified_journey_count") or 0)
        if not extension_blockers
        else 0
    )

    all_verified = (
        not blockers
        and historical_verified_products == 53
        and extension_verified_products == 15
        and historical_verified_journeys == 159
        and extension_verified_journeys == 45
    )

    historical_after = historical_anchor_path.read_bytes()
    historical_mutated = historical_after != historical_before
    if historical_mutated:
        blockers.append("historical_53_anchor_mutated")
        all_verified = False

    receipt: dict[str, Any] = {
        "schema": PORTFOLIO_SCHEMA,
        "acceptance_token": PORTFOLIO_VERIFIED_TOKEN if all_verified else PORTFOLIO_BASELINE_TOKEN,
        "critical_blockers": sorted(set(blockers)),
        "canon_product_count": 68,
        "base_canon_product_count": 53,
        "canon_extension_count": 15,
        "variants_per_product": 3,
        "base_canon_journey_count": 159,
        "canon_extension_journey_count": 45,
        "controlled_journey_count": 204,
        "verified_journey_count": historical_verified_journeys + extension_verified_journeys,
        "refused_journey_count": 204 - (historical_verified_journeys + extension_verified_journeys),
        "product_grade_verified_count": historical_verified_products + extension_verified_products,
        "product_grade_refuse_count": 68 - (historical_verified_products + extension_verified_products),
        "all_product_grade_verified": all_verified,
        "historical_53_receipt_mutated": historical_mutated,
        "historical_53": {
            "source_repository": anchor.get("source_repository"),
            "source_commit": anchor.get("source_commit"),
            "source_path": anchor.get("source_path"),
            "source_git_blob_sha": anchor.get("source_git_blob_sha"),
            "acceptance_token": anchor.get("acceptance_token"),
            "anchor_sha256": _sha256_bytes(historical_before),
            "anchor_fingerprint": _fingerprint(anchor),
            "product_count": anchor.get("canonical_incarnation_count"),
            "journey_count": anchor.get("journey_count"),
        },
        "canon_extensions_15x3": {
            "schema": extension_receipt.get("schema"),
            "acceptance_token": extension_receipt.get("acceptance_token"),
            "portfolio_fingerprint": extension_receipt.get("portfolio_fingerprint"),
            "product_count": extension_receipt.get("extension_count"),
            "journey_count": extension_receipt.get("controlled_journey_count"),
            "verified_journey_count": extension_receipt.get("verified_journey_count"),
        },
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "This portfolio receipt binds two distinct immutable evidence families: the historical 53-product, "
            "159-journey base-canon corpus and the independently verified 15-product, 45-journey canon-extension "
            "ProductGrade corpus. The combined 68-product / 204-journey statement is an aggregation of those "
            "verified families, not a claim that all 204 journeys were produced in one historical run. Capability "
            "proof remains distinct from market validation, willingness to pay, payment, and external authority."
        ),
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    (output_dir / PORTFOLIO_RECEIPT_FILENAME).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt
