from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.canon_extension_proof_seal import SEAL_FILENAME, SEAL_SCHEMA

BASELINE_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_BASELINE_MEASURED"
VERIFIED_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"
PROOF_BASELINE_TOKEN = "DIO_CANON_EXTENSION_PROOF_BASELINE_MEASURED"
PROOF_VERIFIED_TOKEN = "DIO_CANON_EXTENSION_PROOF_VERIFIED"
PRODUCT_GRADE_VERIFIED = "PRODUCT_GRADE_VERIFIED"
PRODUCT_GRADE_REFUSE = "PRODUCT_GRADE_REFUSE"
PROOF_VERIFIED = "CANON_EXTENSION_PROOF_VERIFIED"
PROOF_REFUSE = "CANON_EXTENSION_PROOF_REFUSE"
NATIVE_V2_SCHEMA = "dio.product_grade.canon_extension_native.v2"
NATIVE_V3_SCHEMA = "dio.product_grade.canon_extension_native.v3"
VARIANT_NAMES = ("normal", "messy", "adversarial")

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


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _v3_variant_checks(receipt: dict[str, Any], *, root: Path | None = None) -> list[str]:
    blockers: list[str] = []
    variants = receipt.get("variants")
    if receipt.get("variant_count") != 3 or receipt.get("verified_variant_count") != 3 or receipt.get("refused_variant_count") != 0:
        blockers.append("native_product_grade_3x_not_verified")
    if not isinstance(variants, dict) or set(variants) != set(VARIANT_NAMES):
        blockers.append("native_product_grade_variant_set_invalid")
        return blockers

    for name in VARIANT_NAMES:
        row = variants.get(name)
        if not isinstance(row, dict):
            blockers.append(f"native_variant_{name}_missing")
            continue
        if row.get("passed") is not True or row.get("critical_blockers"):
            blockers.append(f"native_variant_{name}_refused")
        if row.get("external_effects") is not False:
            blockers.append(f"native_variant_{name}_external_effects")
        if row.get("authority_created") is not False:
            blockers.append(f"native_variant_{name}_authority_created")
        if not str(row.get("receipt_fingerprint") or "").startswith("sha256:"):
            blockers.append(f"native_variant_{name}_fingerprint_missing")

        if root is not None and row.get("customer_artifact"):
            artifact = (root / str(row["customer_artifact"])).resolve()
            if not artifact.is_relative_to(root) or not artifact.is_file():
                blockers.append(f"native_variant_{name}_artifact_missing")
            else:
                declared = str(row.get("customer_artifact_sha256") or "").removeprefix("sha256:")
                if declared != _sha(artifact):
                    blockers.append(f"native_variant_{name}_artifact_mismatch")
    return blockers


def _v3_common_checks(receipt: dict[str, Any], *, root: Path | None = None) -> list[str]:
    blockers: list[str] = []
    if receipt.get("schema") != NATIVE_V3_SCHEMA:
        blockers.append("native_product_grade_v3_required")
        return blockers
    if receipt.get("status") != PRODUCT_GRADE_VERIFIED:
        blockers.append("native_product_grade_not_verified")
    blockers.extend(_v3_variant_checks(receipt, root=root))
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
    if receipt.get("commercial_validation") != "UNPROVED":
        blockers.append("commercial_claim_boundary_changed")
    return blockers


def _native_receipt_checks(
    receipt: dict[str, Any],
    artifact_sha: str,
    *,
    root: Path | None = None,
    spec: dict[str, Any] | None = None,
) -> list[str]:
    blockers: list[str] = []
    schema = receipt.get("schema")

    if schema == NATIVE_V3_SCHEMA:
        blockers.extend(_v3_common_checks(receipt, root=root))
        if root is None or spec is None:
            blockers.append("native_product_grade_v3_context_missing")
            return sorted(set(blockers))
        root = Path(root).resolve()
        canon_sha = str(receipt.get("canon_artifact_sha256") or "").removeprefix("sha256:")
        if canon_sha != artifact_sha:
            blockers.append("native_product_grade_canon_artifact_mismatch")
        if str(receipt.get("canon_artifact") or "") != str(spec["primary_artifact"]):
            blockers.append("native_product_grade_canon_artifact_path_mismatch")
        primary_sha = str(receipt.get("primary_artifact_sha256") or "").removeprefix("sha256:")
        if primary_sha != artifact_sha:
            blockers.append("native_product_grade_primary_canon_mismatch")

        seal_path = ((root / spec["proof_receipt"]).resolve().parent / SEAL_FILENAME).resolve()
        if not seal_path.is_relative_to(root) or not seal_path.is_file():
            blockers.append("native_product_grade_canon_proof_missing")
        else:
            if str(receipt.get("canon_proof_receipt") or "") != str(seal_path.relative_to(root)):
                blockers.append("native_product_grade_canon_proof_path_mismatch")
            if str(receipt.get("canon_proof_receipt_sha256") or "").removeprefix("sha256:") != _sha(seal_path):
                blockers.append("native_product_grade_canon_proof_mismatch")
        return sorted(set(blockers))

    if receipt.get("status") != PRODUCT_GRADE_VERIFIED:
        blockers.append("native_product_grade_not_verified")

    if schema == NATIVE_V2_SCHEMA:
        if root is None or spec is None:
            blockers.append("native_product_grade_v2_context_missing")
        else:
            root = Path(root).resolve()
            canon_sha = str(receipt.get("canon_artifact_sha256") or "").removeprefix("sha256:")
            if canon_sha != artifact_sha:
                blockers.append("native_product_grade_canon_artifact_mismatch")
            if str(receipt.get("canon_artifact") or "") != str(spec["primary_artifact"]):
                blockers.append("native_product_grade_canon_artifact_path_mismatch")

            seal_path = ((root / spec["proof_receipt"]).resolve().parent / SEAL_FILENAME).resolve()
            if not seal_path.is_relative_to(root) or not seal_path.is_file():
                blockers.append("native_product_grade_canon_proof_missing")
            else:
                expected_seal_rel = str(seal_path.relative_to(root))
                if str(receipt.get("canon_proof_receipt") or "") != expected_seal_rel:
                    blockers.append("native_product_grade_canon_proof_path_mismatch")
                seal_sha = str(receipt.get("canon_proof_receipt_sha256") or "").removeprefix("sha256:")
                if seal_sha != _sha(seal_path):
                    blockers.append("native_product_grade_canon_proof_mismatch")

            customer_rel = str(receipt.get("customer_artifact") or "")
            if not customer_rel:
                blockers.append("native_product_grade_customer_artifact_missing")
            else:
                customer = (root / customer_rel).resolve()
                canon = (root / spec["primary_artifact"]).resolve()
                if not customer.is_relative_to(root):
                    blockers.append("native_product_grade_customer_artifact_unsafe")
                elif customer == canon:
                    blockers.append("native_product_grade_customer_artifact_not_separate")
                elif not customer.is_file():
                    blockers.append("native_product_grade_customer_artifact_missing")
                else:
                    declared_customer_sha = str(receipt.get("customer_artifact_sha256") or "").removeprefix("sha256:")
                    live_customer_sha = _sha(customer)
                    if declared_customer_sha != live_customer_sha:
                        blockers.append("native_product_grade_customer_artifact_mismatch")
                    primary_sha = str(receipt.get("primary_artifact_sha256") or "").removeprefix("sha256:")
                    if primary_sha != declared_customer_sha:
                        blockers.append("native_product_grade_primary_customer_mismatch")

            if receipt.get("commercial_validation") != "UNPROVED":
                blockers.append("commercial_claim_boundary_changed")
    else:
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
    return sorted(set(blockers))


def _verify_seal(
    *,
    seal_data: dict[str, Any],
    spec: dict[str, Any],
    artifact_sha: str,
    generation_receipt_sha: str,
) -> list[str]:
    blockers: list[str] = []
    if seal_data.get("schema") != SEAL_SCHEMA:
        blockers.append("canon_proof_seal_schema_invalid")
    if seal_data.get("status") != "PASS":
        blockers.append("canon_proof_seal_not_pass")
    if seal_data.get("canon_id") != spec["canon_id"] or seal_data.get("slug") != spec["slug"]:
        blockers.append("canon_proof_seal_identity_mismatch")
    if str(seal_data.get("primary_artifact") or "") != str(spec["primary_artifact"]):
        blockers.append("canon_proof_seal_artifact_path_mismatch")
    if str(seal_data.get("current_artifact_sha256") or "").removeprefix("sha256:") != artifact_sha:
        blockers.append("canon_proof_seal_artifact_hash_mismatch")
    if str(seal_data.get("source_generation_receipt") or "") != str(spec["proof_receipt"]):
        blockers.append("canon_proof_seal_generation_receipt_path_mismatch")
    if str(seal_data.get("source_generation_receipt_sha256") or "").removeprefix("sha256:") != generation_receipt_sha:
        blockers.append("canon_proof_seal_generation_receipt_hash_mismatch")
    if seal_data.get("authority_created") is not False:
        blockers.append("canon_proof_seal_authority_created")
    if seal_data.get("external_effects") is not False:
        blockers.append("canon_proof_seal_external_effects")
    return blockers


def evaluate_receipt_bound_extension(
    *,
    spec: dict[str, Any],
    root: Path,
    native_product_grade_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = (root / spec["primary_artifact"]).resolve()
    generation_receipt = (root / spec["proof_receipt"]).resolve()
    seal_path = generation_receipt.parent / SEAL_FILENAME
    row: dict[str, Any] = {
        "canon_id": spec["canon_id"],
        "name": spec["name"],
        "slug": spec["slug"],
        "proof_kind": "receipt_bound",
        "proof_status": PROOF_REFUSE,
        "status": PRODUCT_GRADE_REFUSE,
        "critical_blockers": [],
        "primary_artifact": spec["primary_artifact"],
        "generation_receipt": spec["proof_receipt"],
        "proof_receipt": spec["proof_receipt"],
        "artifact_hash_bound": False,
        "generation_receipt_bound": False,
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
    }
    if not artifact.is_relative_to(root) or not generation_receipt.is_relative_to(root) or not seal_path.is_relative_to(root):
        row["critical_blockers"].append("unsafe_evidence_path")
        return row
    if not artifact.is_file():
        row["critical_blockers"].append("primary_artifact_missing")
    if not generation_receipt.is_file():
        row["critical_blockers"].append("proof_receipt_missing")
    if row["critical_blockers"]:
        return row

    generation_data = _load_json(generation_receipt)
    if generation_data is None:
        row["critical_blockers"].append("proof_receipt_invalid_json")
        return row
    if _top_level_failure(generation_data):
        row["critical_blockers"].append("proof_receipt_reports_failure")
        return row

    artifact_sha = _sha(artifact)
    generation_sha = _sha(generation_receipt)
    row["primary_artifact_sha256"] = artifact_sha
    row["generation_receipt_sha256"] = generation_sha
    row["generation_receipt_fingerprint"] = _fingerprint(generation_data)

    if seal_path.is_file():
        seal_data = _load_json(seal_path)
        if seal_data is None:
            row["critical_blockers"].append("canon_proof_seal_invalid_json")
            return row
        seal_blockers = _verify_seal(
            seal_data=seal_data,
            spec=spec,
            artifact_sha=artifact_sha,
            generation_receipt_sha=generation_sha,
        )
        if seal_blockers:
            row["critical_blockers"].extend(seal_blockers)
            return row
        row["proof_receipt"] = str(seal_path.relative_to(root))
        row["proof_receipt_fingerprint"] = _fingerprint(seal_data)
        row["artifact_hash_bound"] = True
        row["generation_receipt_bound"] = True
    else:
        row["proof_receipt_fingerprint"] = _fingerprint(generation_data)
        row["artifact_hash_bound"] = _receipt_binds_hash(generation_data, artifact_sha)
        row["generation_receipt_bound"] = row["artifact_hash_bound"]
        if not row["artifact_hash_bound"]:
            row["critical_blockers"].append("artifact_not_hash_bound_to_receipt")
            return row

    row["proof_status"] = PROOF_VERIFIED
    if native_product_grade_receipt is None:
        row["critical_blockers"].append("native_product_grade_not_run")
        return row
    native_blockers = _native_receipt_checks(
        native_product_grade_receipt,
        artifact_sha,
        root=root,
        spec=spec,
    )
    if native_blockers:
        row["critical_blockers"].extend(native_blockers)
        return row

    row["status"] = PRODUCT_GRADE_VERIFIED
    row["critical_blockers"] = []
    row["native_product_grade_receipt_fingerprint"] = _fingerprint(native_product_grade_receipt)
    schema = native_product_grade_receipt.get("schema")
    if schema in {NATIVE_V2_SCHEMA, NATIVE_V3_SCHEMA}:
        row["customer_artifact"] = native_product_grade_receipt.get("customer_artifact")
        row["customer_artifact_sha256"] = native_product_grade_receipt.get("customer_artifact_sha256")
        row["native_product_grade_schema"] = schema
    if schema == NATIVE_V3_SCHEMA:
        row["variant_count"] = native_product_grade_receipt.get("variant_count")
        row["verified_variant_count"] = native_product_grade_receipt.get("verified_variant_count")
        row["variant_receipt_fingerprints"] = {
            name: (native_product_grade_receipt.get("variants") or {}).get(name, {}).get("receipt_fingerprint")
            for name in VARIANT_NAMES
        }
    return row


def _evaluate_studio_extension(
    spec: dict[str, Any],
    studio_rows: dict[str, Any],
    native_product_grade_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    studio_id = spec["studio_id"]
    source = studio_rows.get(studio_id)
    blockers: list[str] = []
    proof_blockers: list[str] = []

    if not isinstance(source, dict):
        proof_blockers.append("source_studio_product_grade_missing")
        source = {}
    else:
        if source.get("status") != PRODUCT_GRADE_VERIFIED:
            proof_blockers.append("source_studio_product_grade_not_verified")
        if source.get("critical_blockers"):
            proof_blockers.append("source_studio_product_grade_blocked")
        if source.get("customers_will_pay") != "UNPROVED" or source.get("verified_payment") != "UNPROVED":
            proof_blockers.append("commercial_claim_boundary_changed")

    proof_verified = not proof_blockers
    blockers.extend(proof_blockers)
    row: dict[str, Any] = {
        "canon_id": spec["canon_id"],
        "name": spec["name"],
        "slug": spec["slug"],
        "proof_kind": "studio_product_grade",
        "source_studio_id": studio_id,
        "proof_status": PROOF_VERIFIED if proof_verified else PROOF_REFUSE,
        "status": PRODUCT_GRADE_REFUSE,
        "critical_blockers": blockers,
        "source_product_grade": source,
        "source_studio_product_grade_fingerprint": source.get("receipt_fingerprint"),
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
    }

    if not proof_verified:
        return row
    if native_product_grade_receipt is None:
        row["critical_blockers"].append("native_product_grade_not_run")
        return row

    native_blockers = _v3_common_checks(native_product_grade_receipt)
    if native_product_grade_receipt.get("slug") != spec["slug"]:
        native_blockers.append("native_product_grade_identity_mismatch")
    if native_product_grade_receipt.get("upstream_studio_id") != studio_id:
        native_blockers.append("native_studio_id_mismatch")
    expected_fingerprint = str(source.get("receipt_fingerprint") or "")
    if str(native_product_grade_receipt.get("upstream_studio_product_grade_fingerprint") or "") != expected_fingerprint:
        native_blockers.append("native_studio_provenance_fingerprint_mismatch")
    if str(native_product_grade_receipt.get("upstream_studio_artifact") or "") != str(source.get("primary_artifact") or ""):
        native_blockers.append("native_studio_artifact_path_mismatch")
    native_source_sha = str(native_product_grade_receipt.get("upstream_studio_artifact_sha256") or "").removeprefix("sha256:")
    source_sha = str(source.get("primary_artifact_sha256") or "").removeprefix("sha256:")
    if native_source_sha != source_sha:
        native_blockers.append("native_studio_artifact_hash_mismatch")

    if native_blockers:
        row["critical_blockers"].extend(sorted(set(native_blockers)))
        return row

    row.update(
        {
            "status": PRODUCT_GRADE_VERIFIED,
            "critical_blockers": [],
            "native_product_grade_schema": NATIVE_V3_SCHEMA,
            "native_product_grade_receipt_fingerprint": _fingerprint(native_product_grade_receipt),
            "variant_count": 3,
            "verified_variant_count": 3,
            "variant_receipt_fingerprints": {
                name: (native_product_grade_receipt.get("variants") or {}).get(name, {}).get("receipt_fingerprint")
                for name in VARIANT_NAMES
            },
        }
    )
    return row


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
        native = explicit.get(spec["slug"])
        if native is None:
            native = _discover_native_receipt(root, spec["slug"])
        if spec["proof_kind"] == "studio_product_grade":
            row = _evaluate_studio_extension(spec, studio_rows, native)
        else:
            row = evaluate_receipt_bound_extension(
                spec=spec,
                root=root,
                native_product_grade_receipt=native,
            )
        extensions[spec["slug"]] = row

    proof_verified = sum(1 for row in extensions.values() if row["proof_status"] == PROOF_VERIFIED)
    pg_verified = sum(1 for row in extensions.values() if row["status"] == PRODUCT_GRADE_VERIFIED)
    all_proof = proof_verified == len(CANON_EXTENSIONS)
    all_pg = pg_verified == len(CANON_EXTENSIONS)
    verified_journeys = sum(int(row.get("verified_variant_count") or 0) for row in extensions.values())
    controlled_journeys = len(CANON_EXTENSIONS) * 3
    refused_journeys = controlled_journeys - verified_journeys

    receipt: dict[str, Any] = {
        "schema": "dio.product_grade.canon_extension_gauntlet_receipt.v2",
        "acceptance_token": VERIFIED_TOKEN if all_pg and verified_journeys == 45 else BASELINE_TOKEN,
        "proof_acceptance_token": PROOF_VERIFIED_TOKEN if all_proof else PROOF_BASELINE_TOKEN,
        "extension_count": len(CANON_EXTENSIONS),
        "variants_per_extension": 3,
        "controlled_journey_count": controlled_journeys,
        "verified_journey_count": verified_journeys,
        "refused_journey_count": refused_journeys,
        "canon_extension_proof_verified_count": proof_verified,
        "canon_extension_proof_refuse_count": len(CANON_EXTENSIONS) - proof_verified,
        "all_canon_extension_proof_verified": all_proof,
        "product_grade_verified_count": pg_verified,
        "product_grade_refuse_count": len(CANON_EXTENSIONS) - pg_verified,
        "all_product_grade_verified": all_pg and verified_journeys == 45,
        "extensions": extensions,
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "Canon-extension ProductGrade requires all fifteen canon extensions to carry their current proof provenance "
            "and an independent native normal, messy, and adversarial ProductGrade receipt. The four Studio extensions "
            "retain their existing Studio ProductGrade evidence as upstream provenance but are not exempt from native "
            "3/3 execution. Capability proof remains distinct from willingness to pay, verified payment, and external authority."
        ),
    }
    receipt["portfolio_fingerprint"] = _fingerprint(receipt)
    (output_dir / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt
