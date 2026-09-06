from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASELINE_TOKEN = "DIO_CANON_EXTENSION_PRODUCT_GRADE_BASELINE_MEASURED"
VERIFIED_TOKEN = "DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED"
PROOF_BASELINE_TOKEN = "DIO_CANON_EXTENSION_PROOF_BASELINE_MEASURED"
PROOF_VERIFIED_TOKEN = "DIO_CANON_EXTENSION_PROOF_VERIFIED"
PRODUCT_GRADE_VERIFIED = "PRODUCT_GRADE_VERIFIED"
PRODUCT_GRADE_REFUSE = "PRODUCT_GRADE_REFUSE"
PROOF_VERIFIED = "CANON_EXTENSION_PROOF_VERIFIED"
PROOF_REFUSE = "CANON_EXTENSION_PROOF_REFUSE"

_BASE = "state/product_portfolio/canon_extensions"

CANON_EXTENSIONS: tuple[dict[str, Any], ...] = (
    {"canon_id": "CANON-EXT-ARTICLE_PUBLICATION", "name": "Article Publication", "slug": "article-publication", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/article-publication/site/index.html", "proof_receipt": f"{_BASE}/article-publication/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-ARTICLE_PUBLICATION_STUDIO", "name": "Article Publication Studio", "slug": "article-publication-studio", "proof_kind": "studio_product_grade", "studio_id": "article_publication_studio"},
    {"canon_id": "CANON-EXT-CONTRACT_DESK", "name": "Contract Desk", "slug": "contract-desk", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/contract-desk/site/index.html", "proof_receipt": f"{_BASE}/contract-desk/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-CORPORATE_READINESS", "name": "Corporate Readiness", "slug": "corporate-readiness", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/corporate-readiness/site/index.html", "proof_receipt": f"{_BASE}/corporate-readiness/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-ENTREPRENEURPROOF", "name": "EntrepreneurProof", "slug": "entrepreneurproof", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/entrepreneurproof/site/index.html", "proof_receipt": f"{_BASE}/entrepreneurproof/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-FINANCE_READINESS", "name": "Finance Readiness", "slug": "finance-readiness", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/finance-readiness/site/index.html", "proof_receipt": f"{_BASE}/finance-readiness/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-FINANCE_READINESS_STUDIO", "name": "Finance Readiness Studio", "slug": "finance-readiness-studio", "proof_kind": "studio_product_grade", "studio_id": "finance_readiness_studio"},
    {"canon_id": "CANON-EXT-FUNDINGFINDER", "name": "FundingFinder", "slug": "fundingfinder", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/fundingfinder/site/index.html", "proof_receipt": f"{_BASE}/fundingfinder/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-INVESTORPROOF", "name": "InvestorProof", "slug": "investorproof", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/investorproof/site/index.html", "proof_receipt": f"{_BASE}/investorproof/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-LAUNCH_STUDIO", "name": "Launch Studio", "slug": "launch-studio", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/launch-studio/site/index.html", "proof_receipt": f"{_BASE}/launch-studio/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-POPIA_READINESS", "name": "POPIA Readiness", "slug": "popia-readiness", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/popia-readiness/site/index.html", "proof_receipt": f"{_BASE}/popia-readiness/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-PROFESSIONAL_CORRESPONDENCE", "name": "Professional Correspondence", "slug": "professional-correspondence", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/professional-correspondence/site/index.html", "proof_receipt": f"{_BASE}/professional-correspondence/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-PROFESSIONAL_CORRESPONDENCE_STUDIO", "name": "Professional Correspondence Studio", "slug": "professional-correspondence-studio", "proof_kind": "studio_product_grade", "studio_id": "professional_correspondence_studio"},
    {"canon_id": "CANON-EXT-REPORT_PITCH_STUDIO", "name": "Report & Pitch Studio", "slug": "report-pitch-studio", "proof_kind": "receipt_bound", "primary_artifact": f"{_BASE}/report-pitch-studio/site/index.html", "proof_receipt": f"{_BASE}/report-pitch-studio/site/GAMMA_RECEIPT.json"},
    {"canon_id": "CANON-EXT-SITE_STUDIO", "name": "Site Studio", "slug": "site-studio", "proof_kind": "studio_product_grade", "studio_id": "site_studio"},
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            out.append(str(key))
            out.extend(_all_strings(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(_all_strings(child))
    elif value is not None:
        out.append(str(value))
    return out


def _receipt_binds_hash(receipt: dict[str, Any], digest: str) -> bool:
    expected = {digest.casefold(), f"sha256:{digest}".casefold()}
    return any(text.strip().casefold() in expected for text in _all_strings(receipt))


def _top_level_failure(receipt: dict[str, Any]) -> bool:
    for key in ("status", "result", "acceptance_token", "verification"):
        value = receipt.get(key)
        if isinstance(value, str) and any(token in value.upper() for token in ("REFUSE", "FAIL", "BLOCKED", "ERROR")):
            return True
    return False


def _native_receipt_checks(receipt: dict[str, Any], artifact_sha: str) -> list[str]:
    blockers: list[str] = []
    if receipt.get("status") != PRODUCT_GRADE_VERIFIED:
        blockers.append("native_product_grade_not_verified")
    native_sha = str(receipt.get("primary_artifact_sha256") or "").removeprefix("sha256:")
    if native_sha != artifact_sha:
        blockers.append("native_product_grade_artifact_mismatch")
    if receipt.get("beast_mechanical_pass") is not True:
        blockers.append("beast_mechanical_pass_missing")
    if receipt.get("lingua_semantic_custody") is not True:
        blockers.append("lingua_semantic_custody_missing")
    if receipt.get("unseen_input_generalisation") is not True:
        blockers.append("unseen_input_generalisation_missing")
    if receipt.get("external_effects") is not False:
        blockers.append("external_effects_not_held")
    if receipt.get("authority_created") is not False:
        blockers.append("authority_created_not_false")
    return blockers


def evaluate_receipt_bound_extension(
    *,
    spec: dict[str, Any],
    root: Path,
    native_product_grade_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = (root / spec["primary_artifact"]).resolve()
    proof = (root / spec["proof_receipt"]).resolve()
    row: dict[str, Any] = {
        "canon_id": spec["canon_id"],
        "name": spec["name"],
        "slug": spec["slug"],
        "proof_kind": "receipt_bound",
        "proof_status": PROOF_REFUSE,
        "status": PRODUCT_GRADE_REFUSE,
        "critical_blockers": [],
        "primary_artifact": spec["primary_artifact"],
        "proof_receipt": spec["proof_receipt"],
        "artifact_hash_bound": False,
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
    }
    if not artifact.is_relative_to(root) or not proof.is_relative_to(root):
        row["critical_blockers"].append("unsafe_evidence_path")
        return row
    if not artifact.is_file():
        row["critical_blockers"].append("primary_artifact_missing")
    if not proof.is_file():
        row["critical_blockers"].append("proof_receipt_missing")
    if row["critical_blockers"]:
        return row
    try:
        proof_data = json.loads(proof.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        row["critical_blockers"].append("proof_receipt_invalid_json")
        return row
    if not isinstance(proof_data, dict):
        row["critical_blockers"].append("proof_receipt_not_object")
        return row
    if _top_level_failure(proof_data):
        row["critical_blockers"].append("proof_receipt_reports_failure")
        return row
    artifact_sha = _sha(artifact)
    row["primary_artifact_sha256"] = artifact_sha
    row["proof_receipt_fingerprint"] = _fingerprint(proof_data)
    row["artifact_hash_bound"] = _receipt_binds_hash(proof_data, artifact_sha)
    if not row["artifact_hash_bound"]:
        row["critical_blockers"].append("artifact_not_hash_bound_to_receipt")
        return row
    row["proof_status"] = PROOF_VERIFIED
    if native_product_grade_receipt is None:
        row["critical_blockers"].append("native_product_grade_not_run")
        return row
    native_blockers = _native_receipt_checks(native_product_grade_receipt, artifact_sha)
    if native_blockers:
        row["critical_blockers"].extend(native_blockers)
        return row
    row["status"] = PRODUCT_GRADE_VERIFIED
    row["critical_blockers"] = []
    row["native_product_grade_receipt_fingerprint"] = _fingerprint(native_product_grade_receipt)
    return row


def _evaluate_studio_extension(spec: dict[str, Any], studio_rows: dict[str, Any]) -> dict[str, Any]:
    studio_id = spec["studio_id"]
    source = studio_rows.get(studio_id)
    blockers: list[str] = []
    if not isinstance(source, dict):
        blockers.append("source_studio_product_grade_missing")
        source = {}
    elif source.get("status") != PRODUCT_GRADE_VERIFIED:
        blockers.append("source_studio_product_grade_not_verified")
    elif source.get("customers_will_pay") != "UNPROVED" or source.get("verified_payment") != "UNPROVED":
        blockers.append("commercial_claim_boundary_changed")
    verified = not blockers
    return {
        "canon_id": spec["canon_id"],
        "name": spec["name"],
        "slug": spec["slug"],
        "proof_kind": "studio_product_grade",
        "source_studio_id": studio_id,
        "proof_status": PROOF_VERIFIED if verified else PROOF_REFUSE,
        "status": PRODUCT_GRADE_VERIFIED if verified else PRODUCT_GRADE_REFUSE,
        "critical_blockers": blockers,
        "source_product_grade": source,
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
    }


def _discover_native_receipt(root: Path, slug: str) -> dict[str, Any] | None:
    path = root / "state" / "product_grade" / "canon_extensions" / slug / "PRODUCT_GRADE_RECEIPT.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def run_canon_extension_product_grade_gauntlet(
    *,
    output_dir: Path,
    root: Path,
    studio_product_grade_receipt: dict[str, Any],
    native_product_grade_receipts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    studio_rows = studio_product_grade_receipt.get("studios") or {}
    explicit = native_product_grade_receipts or {}
    extensions: dict[str, Any] = {}
    for spec in CANON_EXTENSIONS:
        if spec["proof_kind"] == "studio_product_grade":
            row = _evaluate_studio_extension(spec, studio_rows)
        else:
            native = explicit.get(spec["slug"])
            if native is None:
                native = _discover_native_receipt(root, spec["slug"])
            row = evaluate_receipt_bound_extension(spec=spec, root=root, native_product_grade_receipt=native)
        extensions[spec["slug"]] = row
    proof_verified = sum(1 for row in extensions.values() if row["proof_status"] == PROOF_VERIFIED)
    pg_verified = sum(1 for row in extensions.values() if row["status"] == PRODUCT_GRADE_VERIFIED)
    all_proof = proof_verified == len(CANON_EXTENSIONS)
    all_pg = pg_verified == len(CANON_EXTENSIONS)
    receipt: dict[str, Any] = {
        "schema": "dio.product_grade.canon_extension_gauntlet_receipt.v1",
        "acceptance_token": VERIFIED_TOKEN if all_pg else BASELINE_TOKEN,
        "proof_acceptance_token": PROOF_VERIFIED_TOKEN if all_proof else PROOF_BASELINE_TOKEN,
        "extension_count": len(CANON_EXTENSIONS),
        "canon_extension_proof_verified_count": proof_verified,
        "canon_extension_proof_refuse_count": len(CANON_EXTENSIONS) - proof_verified,
        "all_canon_extension_proof_verified": all_proof,
        "product_grade_verified_count": pg_verified,
        "product_grade_refuse_count": len(CANON_EXTENSIONS) - pg_verified,
        "all_product_grade_verified": all_pg,
        "extensions": extensions,
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "Canon-extension ProductGrade separates receipt-bound product proof from full native ProductGrade. "
            "Only extensions with native execution integrity, BEAST mechanical checks, Lingua semantic custody, "
            "unseen-input generalisation, current-artifact hash binding and held external authority may reach "
            "PRODUCT_GRADE_VERIFIED. Real willingness to pay remains unproved until observed."
        ),
    }
    receipt["portfolio_fingerprint"] = _fingerprint(receipt)
    (output_dir / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt
