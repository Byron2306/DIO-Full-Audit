from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CROSSWALK = ROOT / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
STATE_PATH = ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"
EXTENSION_RECEIPT_PATH = (
    ROOT
    / "state"
    / "product_grade"
    / "canon_extension_aggregate"
    / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
)
LEGACY_EXTENSION_RECEIPT_PATH = (
    ROOT
    / "state"
    / "product_grade"
    / "canon_extensions"
    / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
)

EXTENSION_SCHEMA = "dio.product_grade.canon_extension_gauntlet_receipt.v1"
EXTENSION_SCHEMA_V2 = "dio.product_grade.canon_extension_gauntlet_receipt.v2"
EXTENSION_PRODUCT_GRADE_TOKEN = "DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED"
EXTENSION_PRODUCT_GRADE_TOKEN_V2 = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"
EXTENSION_PROOF_TOKEN = "DIO_CANON_EXTENSION_PROOF_VERIFIED"
EXTENSION_PRODUCT_GRADE_STATUS = "PRODUCT_GRADE_VERIFIED"
EXTENSION_PROOF_STATUS = "CANON_EXTENSION_PROOF_VERIFIED"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _fingerprint(parts: dict[str, str]) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _lane(primary_family: str) -> dict[str, Any]:
    text = primary_family.casefold()
    if "evidex" in text:
        return {"lane": "EVIDEX", "job_api": "/api/control/product/action", "fresh_intake": "product_job_required"}
    if "homs" in text:
        return {"lane": "HOMS", "job_api": "/api/control/product/action", "fresh_intake": "product_job_required"}
    if "sophia" in text:
        return {"lane": "SOPHIA", "job_api": "/api/control/sophia/action", "fresh_intake": "sophia_job_required"}
    if "vamp" in text:
        return {"lane": "VAMP", "job_api": "/api/control/vamp/action", "fresh_intake": "vamp_job_required"}
    if "document studio" in text or "format core" in text:
        return {"lane": "DOCUMENT_STUDIO", "job_api": "/api/control/document-studio/action", "fresh_intake": "document_job_required"}
    if "nichefoundry" in text or "hivenance" in text:
        return {"lane": "MARKET_FACTORY", "job_api": "/api/control/creative-factory/action", "fresh_intake": "campaign_or_creative_brief_required"}
    return {"lane": "PACKAGE_GATE_ONLY", "job_api": None, "fresh_intake": "verified_output_required"}


def _active_extension_receipt_path() -> Path:
    if EXTENSION_RECEIPT_PATH.is_file():
        return EXTENSION_RECEIPT_PATH
    if LEGACY_EXTENSION_RECEIPT_PATH.is_file():
        return LEGACY_EXTENSION_RECEIPT_PATH
    return EXTENSION_RECEIPT_PATH


def _load_extension_summary() -> tuple[str, dict[str, Any] | None, str]:
    receipt_path = _active_extension_receipt_path()
    if not receipt_path.is_file():
        return "MISSING", None, "missing"
    receipt_sha = _sha256(receipt_path)
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "INVALID", None, receipt_sha
    if not isinstance(value, dict):
        return "INVALID", None, receipt_sha

    extensions = value.get("extensions")
    schema_contract_verified = (
        (
            value.get("schema") == EXTENSION_SCHEMA
            and value.get("acceptance_token") == EXTENSION_PRODUCT_GRADE_TOKEN
        )
        or (
            value.get("schema") == EXTENSION_SCHEMA_V2
            and value.get("acceptance_token") == EXTENSION_PRODUCT_GRADE_TOKEN_V2
            and value.get("controlled_journey_count") == 45
            and value.get("verified_journey_count") == 45
            and value.get("refused_journey_count") == 0
        )
    )
    verified = (
        schema_contract_verified
        and value.get("proof_acceptance_token") == EXTENSION_PROOF_TOKEN
        and value.get("extension_count") == 15
        and value.get("product_grade_verified_count") == 15
        and value.get("canon_extension_proof_verified_count") == 15
        and value.get("all_product_grade_verified") is True
        and value.get("all_canon_extension_proof_verified") is True
        and value.get("commercial_validation") == "UNPROVED"
        and value.get("authority_created") is False
        and value.get("external_effects") is False
        and isinstance(extensions, dict)
        and len(extensions) == 15
    )
    if not verified:
        return "NOT_VERIFIED", value, receipt_sha

    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for slug, row in extensions.items():
        if not isinstance(row, dict):
            return "NOT_VERIFIED", value, receipt_sha
        canon_id = str(row.get("canon_id") or "").strip()
        row_slug = str(row.get("slug") or slug).strip()
        blockers = row.get("critical_blockers") or []
        if (
            not canon_id
            or not row_slug
            or canon_id in seen_ids
            or row_slug in seen_slugs
            or row.get("status") != EXTENSION_PRODUCT_GRADE_STATUS
            or row.get("proof_status") != EXTENSION_PROOF_STATUS
            or blockers
            or row.get("customers_will_pay") != "UNPROVED"
            or row.get("verified_payment") != "UNPROVED"
        ):
            return "NOT_VERIFIED", value, receipt_sha
        seen_ids.add(canon_id)
        seen_slugs.add(row_slug)
    return "VERIFIED", value, receipt_sha


def _relative_summary_path() -> str:
    receipt_path = _active_extension_receipt_path()
    try:
        return str(receipt_path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(receipt_path)


def _extension_rows(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    proof_summary_path = _relative_summary_path()
    for slug, source in (receipt.get("extensions") or {}).items():
        name = str(source.get("name") or slug).strip()
        canon_id = str(source.get("canon_id") or "").strip()
        proof_kind = str(source.get("proof_kind") or "canon_extension").strip()
        customer_artifact = str(source.get("customer_artifact") or "").strip()
        primary_artifact = str(source.get("primary_artifact") or "").strip()
        package: dict[str, Any] = {
            "state": "PRODUCT_GRADE_VERIFIED · COMMERCIAL UNPROVED",
            "golden_proof_path": proof_summary_path,
        }
        if primary_artifact:
            package["site_path"] = primary_artifact
        if customer_artifact:
            package["package_dir"] = str(Path(customer_artifact).parent)
        rows.append(
            {
                "Incarnation": name,
                "Suite": "Canon Extensions",
                "Product Family": "Canon Extension",
                "Maturity": "ProductGrade verified",
                "Readiness": "ProductGrade verified",
                "execution_truth_class": "CANON_EXTENSION_PRODUCT_GRADE_VERIFIED",
                "production_lane": _lane("Canon Extension"),
                "portfolio_identity": "canon_extension",
                "candidate_product": False,
                "canon_id": canon_id,
                "slug": str(source.get("slug") or slug),
                "proof_kind": proof_kind,
                "proof_status": source.get("proof_status"),
                "product_grade_status": source.get("status"),
                "commercial_validation": "UNPROVED",
                "customers_will_pay": "UNPROVED",
                "verified_payment": "UNPROVED",
                "authority_created": False,
                "external_effects": False,
                "product_package": package,
            }
        )
    return rows


def import_portfolio(*, force: bool = False) -> dict[str, Any]:
    if not CROSSWALK.is_file():
        raise FileNotFoundError(f"Canonical portfolio crosswalk not found: {CROSSWALK}")
    source_sha = _sha256(CROSSWALK)
    extension_state, extension_receipt, extension_sha = _load_extension_summary()
    extension_path = _active_extension_receipt_path()
    source_fingerprint = _fingerprint(
        {
            "base_crosswalk": source_sha,
            "extension_summary": extension_sha,
            "extension_state": extension_state,
        }
    )
    if STATE_PATH.is_file() and not force:
        try:
            current = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if current.get("source_fingerprint") == source_fingerprint:
                return current
        except (OSError, json.JSONDecodeError):
            pass

    rows: list[dict[str, Any]] = []
    with CROSSWALK.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            incarnation = str(raw.get("incarnation") or "").strip()
            if not incarnation:
                continue
            suite = str(raw.get("suite") or "").strip()
            family = str(raw.get("primary_family") or "").strip()
            maturity = str(raw.get("source_maturity") or "").strip()
            truth = str(raw.get("execution_truth_class") or "").strip()
            row = {key: (value or "") for key, value in raw.items()}
            row.update(
                {
                    "Incarnation": incarnation,
                    "Suite": suite,
                    "Product Family": family,
                    "Maturity": maturity,
                    "Readiness": maturity,
                    "execution_truth_class": truth,
                    "production_lane": _lane(family),
                    "portfolio_identity": "canonical_incarnation",
                    "candidate_product": False,
                    "authority_created": False,
                }
            )
            rows.append(row)

    base_count = len(rows)
    extension_rows: list[dict[str, Any]] = []
    if extension_state == "VERIFIED" and extension_receipt is not None:
        extension_rows = _extension_rows(extension_receipt)
        rows.extend(extension_rows)

    payload = {
        "schema": "dio.meta_portfolio.atlas_import.v3",
        "generated_at": utc_now(),
        "source": {"path": str(CROSSWALK), "sha256": source_sha, "kind": "canonical_incarnation_crosswalk"},
        "extension_source": {
            "path": str(extension_path),
            "sha256": extension_sha if extension_sha != "missing" else None,
            "state": extension_state,
            "kind": "canon_extension_product_grade_summary",
        },
        "source_fingerprint": source_fingerprint,
        "base_canonical_incarnation_count": base_count,
        "canon_extension_count": len(extension_rows),
        "canonical_incarnation_count": len(rows),
        "candidate_incarnations_imported": 0,
        "candidate_boundary": "ATLAS governed candidate incarnations are not imported into this executable portfolio registry.",
        "extension_summary_state": extension_state,
        "extension_claim_boundary": (
            "Verified canon extensions are surfaced from the frozen 15/15 ProductGrade summary. "
            "This does not retroactively add them to the historical 53x3 controlled-journey corpus, "
            "and it does not prove commercial validation."
        ),
        "incarnations": rows,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
    _atomic_json(STATE_PATH, payload)
    return payload


def load_portfolio(*, auto_import: bool = True) -> dict[str, Any]:
    if auto_import:
        return import_portfolio(force=False)
    if not STATE_PATH.is_file():
        return {
            "schema": "dio.meta_portfolio.atlas_import.v3",
            "incarnations": [],
            "canonical_incarnation_count": 0,
            "base_canonical_incarnation_count": 0,
            "canon_extension_count": 0,
        }
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))
