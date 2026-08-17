#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"
CONFIG_PATH = ROOT / "config" / "dio_product_classes.json"
ROUTE_CONFIG_PATH = ROOT / "config" / "product_class_routes.json"
AUDIT_PATH = ROOT / "state" / "product_portfolio" / "DIO_PRODUCT_CLASS_READINESS_AUDIT.json"
REPORT_PATH = ROOT / "docs" / "DIO_PRODUCT_CLASS_READINESS_2026-08-16.md"
PACKAGE_ROOT = ROOT / "state" / "product_class_packages"
DELIVERABLE_ROOT = ROOT / "deliverables" / "product_class_packages"

DIRECT_PILOT_PRODUCTS: dict[str, dict[str, Any]] = {
    "Evidex EvidenceOps": {
        "confidence": "high",
        "evidence": ["sites/evidex/index.html", "sites/evidex/golden-case/index.html", "docs/EVIDEX_TRANSACTION_LOOP_PROOF.md"],
        "next": "Use as the first paid controlled pilot wedge.",
    },
    "HOMS Assess": {
        "confidence": "medium",
        "evidence": ["sites/homs/index.html", "docs/HOMS_SELLING_KIT.md", "scripts/run_homs_hymark_batch.py"],
        "next": "Sell only with complete source material and educator review.",
    },
    "HOMS Exam": {
        "confidence": "medium",
        "evidence": ["sites/homs/index.html", "sites/homs/assets/homs-exam-studio.png", "docs/HOMS_CAPS_ONTOLOGY_CLOSING_PROOF.md"],
        "next": "Offer scoped exam-studio pilots with educator approval.",
    },
    "HOMS Learning Studio": {
        "confidence": "medium",
        "evidence": ["sites/homs/learning-studio/index.html", "docs/HOMS_LEARNING_STUDIO_GOLDEN_PROOF.md"],
        "next": "Sell bounded one-topic companion pilots only.",
    },
    "Sophia Review": {
        "confidence": "high",
        "evidence": ["sites/sophia/index.html", "scripts/manage_sophia_commercial.py"],
        "next": "Run invite-only manuscript/section reviews with explicit no-ghostwriting language.",
    },
    "VAMP Performance": {
        "confidence": "medium",
        "evidence": ["sites/vamp/index.html", "docs/VAMP_PROFILED_EVIDENCE_ARCHITECTURE.md"],
        "next": "Keep invite-only until portability and privacy economics have repeated proof.",
    },
    "Document Studio Edit": {
        "confidence": "high",
        "evidence": ["sites/document-studio/index.html", "docs/DOCUMENT_STUDIO_GOLDEN_PROOF.md", "scripts/manage_document_studio_commercial.py"],
        "next": "Sell one-document technical edit pilots with human review.",
    },
    "Document Studio Localize": {
        "confidence": "medium",
        "evidence": ["sites/document-studio/index.html", "docs/DOCUMENT_STUDIO_MULTILINGUAL_ROUTES.md", "scripts/manage_document_studio_commercial.py"],
        "next": "Require proficient target-language authority before translation delivery.",
    },
    "Document Studio Publish": {
        "confidence": "high",
        "evidence": ["sites/document-studio/index.html", "docs/DIO_FORMAT_CORE.md", "scripts/manage_document_studio_commercial.py"],
        "next": "Keep this as a Document Studio output capability rather than a separate headline product.",
    },
}

INTERNAL_CAPABILITIES = {
    "Market Radar": "Use internally for campaign/product discovery.",
    "Opportunity Foundry": "Use internally to create product/opportunity hypotheses.",
    "Offer Lab": "Use internally to generate bounded offer experiments.",
    "Campaign Lab": "Use internally to prepare governed campaign drafts.",
    "Vesper Desk": "Keep as the DIO front door and routing layer.",
    "Accessible Publish": "Keep inside Document Studio until accessibility QA has its own execution proof.",
}

TIER_SCORES = {
    "launch_controlled_pilot": 82,
    "internal_operational_capability": 72,
    "structural_proof_packaged": 64,
    "near_ready_profile_extension": 54,
    "not_ready": 35,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "product-class"


def route_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def evidence_state(paths: list[str]) -> list[dict[str, Any]]:
    return [{"path": item, "exists": (ROOT / item).exists()} for item in paths]


def route_contract(name: str, routes: dict[str, Any]) -> dict[str, Any] | None:
    key = route_key(name)
    key = str((routes.get("aliases") or {}).get(key, key))
    direct = (routes.get("direct_products") or {}).get(key)
    if direct:
        return {"key": key, "registered_as": "direct_product", **direct}
    product_class = (routes.get("product_classes") or {}).get(key)
    if product_class:
        return {"key": key, "registered_as": "product_class", **product_class}
    return None


def packaged_structural_proof(name: str) -> dict[str, Any] | None:
    slug = slugify(name)
    package_dir = PACKAGE_ROOT / slug
    structural_paths = [
        package_dir / "PRODUCT_PROFILE.json",
        package_dir / "INTAKE_SCHEMA.json",
        package_dir / "PROCESSING_ROUTE.json",
        package_dir / "MAIL_TEMPLATES.json",
        package_dir / "MARKET_COMMAND_SEED.json",
        package_dir / "GOLDEN_PROOF.md",
        package_dir / "SMOKE_TEST_RECEIPT.json",
        package_dir / "PACKAGE_MANIFEST.json",
        DELIVERABLE_ROOT / slug / f"{slug}_STRUCTURAL_PROOF_PACKAGE.zip",
    ]
    if not all(path.exists() for path in structural_paths):
        return None
    try:
        smoke = load_json(package_dir / "SMOKE_TEST_RECEIPT.json")
        manifest = load_json(package_dir / "PACKAGE_MANIFEST.json")
        structural_checks = [item for item in smoke.get("checks", []) if str(item.get("check", "")).startswith("structural:")]
        smoke_ok = (
            smoke.get("result") == "structural_passed"
            and smoke.get("execution_proof") is False
            and bool(structural_checks)
            and all(item.get("passed") for item in structural_checks)
        )
        manifest_ok = (
            manifest.get("state") == "structural_proof_packaged"
            and manifest.get("execution_proof") is False
            and manifest.get("public_launch_ready") is False
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not smoke_ok or not manifest_ok:
        return None
    return {
        "tier": "structural_proof_packaged",
        "label": "packaged structural proof",
        "score": TIER_SCORES["structural_proof_packaged"],
        "score_kind": "heuristic_display_only",
        "confidence": "medium",
        "evidence": [{"path": str(path.relative_to(ROOT)), "exists": True} for path in structural_paths],
        "missing_evidence": ["controlled execution receipt", "public-safe proof", "operator launch approval"],
        "next_step": "Run the approved typed route against a controlled fixture and retain execution proof before public launch.",
        "promotion_basis": "internal structural package exists; execution proof remains separate",
    }


def classify(row: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any]:
    name = row["Incarnation"]
    if name in DIRECT_PILOT_PRODUCTS:
        record = DIRECT_PILOT_PRODUCTS[name]
        evidence = evidence_state(record["evidence"])
        missing = [item["path"] for item in evidence if not item["exists"]]
        if not missing:
            return {
                "tier": "launch_controlled_pilot",
                "label": "controlled pilot ready",
                "score": TIER_SCORES["launch_controlled_pilot"],
                "score_kind": "heuristic_display_only",
                "confidence": record["confidence"],
                "evidence": evidence,
                "missing_evidence": [],
                "next_step": record["next"],
                "promotion_basis": "named direct product with tracked route/proof artifacts",
            }
    if name in INTERNAL_CAPABILITIES:
        return {
            "tier": "internal_operational_capability",
            "label": "ready internally",
            "score": TIER_SCORES["internal_operational_capability"],
            "score_kind": "heuristic_display_only",
            "confidence": "medium",
            "evidence": [],
            "missing_evidence": [],
            "next_step": INTERNAL_CAPABILITIES[name],
        }
    packaged = packaged_structural_proof(name)
    if packaged:
        return packaged
    contract = route_contract(name, routes)
    if contract and contract.get("registered_as") == "product_class":
        return {
            "tier": "near_ready_profile_extension",
            "label": "typed route required",
            "score": TIER_SCORES["near_ready_profile_extension"],
            "score_kind": "heuristic_display_only",
            "confidence": "medium",
            "evidence": [],
            "missing_evidence": ["typed route execution receipt", "reviewed output", "public-safe proof"],
            "next_step": "Approve and execute the typed product route before public launch promotion.",
        }
    return {
        "tier": "not_ready",
        "label": "not ready yet",
        "score": TIER_SCORES["not_ready"],
        "score_kind": "heuristic_display_only",
        "confidence": "medium",
        "evidence": [],
        "missing_evidence": ["route contract", "execution proof"],
        "next_step": "Register a route contract before packaging or marketing this class.",
    }


def processing_coverage(row: dict[str, Any], routes: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    name = row["Incarnation"]
    contract = route_contract(name, routes)
    if readiness["tier"] == "internal_operational_capability":
        return {"state": "internal_operational_route", "processing_ready": True, "lead_promotion_ready": False, "route_contract": None, "summary": "Operational inside DIO; not a standalone public route."}
    if not contract:
        return {"state": "route_contract_missing", "processing_ready": False, "lead_promotion_ready": False, "route_contract": None, "summary": "No explicit product route contract is registered."}
    if contract.get("registered_as") == "product_class":
        return {"state": "typed_route_required", "processing_ready": False, "lead_promotion_ready": False, "route_contract": contract, "summary": "A processor may be suggested, but the product-class route is not automatically executable."}
    auto = contract.get("auto_promotable") is True
    return {
        "state": "direct_route_available" if auto else "specialist_route_available",
        "processing_ready": True,
        "lead_promotion_ready": auto,
        "route_contract": contract,
        "summary": "Direct executable route is registered." if auto else "Existing processor is available, but specialist/operator routing is still required.",
    }


def build_report(registry: dict[str, Any], audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        "# DIO Product Class Readiness",
        "",
        f"Generated: `{audit['generated_at']}`",
        "",
        "## Verdict",
        "",
        "Readiness is evidence-bound. Structural packaging is not execution proof, and a named processor is not an executable route contract.",
        "",
        f"- Controlled-pilot ready direct products: `{summary.get('launch_controlled_pilot', 0)}`",
        f"- Internal operational capabilities: `{summary.get('internal_operational_capability', 0)}`",
        f"- Packaged structural proofs: `{summary.get('structural_proof_packaged', 0)}`",
        f"- Profile extensions still requiring execution proof: `{summary.get('near_ready_profile_extension', 0)}`",
        f"- Not ready / route contract missing: `{summary.get('not_ready', 0)}`",
        "",
        "The score field is heuristic display metadata only. It cannot promote a product.",
        "",
        "## Product Classes",
        "",
        "| Product class | Readiness | Processing route | Next gate |",
        "| --- | --- | --- | --- |",
    ]
    for row in registry["incarnations"]:
        readiness = row["readiness"]
        processing = row["processing_coverage"]
        lines.append(f"| {row['Incarnation']} | {readiness['label']} | {processing['state']} | {readiness['next_step']} |")
    lines.extend([
        "",
        "## Operating Boundary",
        "",
        "Qualification does not create source authority, remote-processing consent, professional judgement, payment authority, public release authority or final delivery authority.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    routes = load_json(ROUTE_CONFIG_PATH)
    counts: dict[str, int] = {}
    processing_counts: dict[str, int] = {}
    for row in registry["incarnations"]:
        readiness = classify(row, routes)
        processing = processing_coverage(row, routes, readiness)
        row["readiness"] = readiness
        row["processing_coverage"] = processing
        counts[readiness["tier"]] = counts.get(readiness["tier"], 0) + 1
        processing_counts[processing["state"]] = processing_counts.get(processing["state"], 0) + 1
    audit = {
        "schema": "dio.product_class_readiness_audit.v2",
        "generated_at": utc_now(),
        "source_registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "route_contract": str(ROUTE_CONFIG_PATH.relative_to(ROOT)),
        "summary": counts,
        "processing_summary": processing_counts,
        "processing_ready_total": sum(1 for row in registry["incarnations"] if row["processing_coverage"]["processing_ready"]),
        "lead_promotion_ready_total": sum(1 for row in registry["incarnations"] if row["processing_coverage"]["lead_promotion_ready"]),
        "tier_meanings": {
            "launch_controlled_pilot": "Named direct product with tracked route/proof artifacts and bounded launch language.",
            "internal_operational_capability": "Operationally useful inside DIO, but not a standalone public product route.",
            "structural_proof_packaged": "Internal profile/package artifacts exist. This is not execution proof.",
            "near_ready_profile_extension": "Registered product class still needs a typed execution receipt and reviewed output.",
            "not_ready": "Route contract or fundamental proof is missing; do not market as ready.",
        },
        "report_path": str(REPORT_PATH.relative_to(ROOT)),
    }
    registry["readiness_audit"] = audit
    write_json(REGISTRY_PATH, registry)
    write_json(CONFIG_PATH, registry)
    write_json(AUDIT_PATH, audit)
    write_text(REPORT_PATH, build_report(registry, audit))
    print(json.dumps(audit, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
