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
AUDIT_PATH = ROOT / "state" / "product_portfolio" / "DIO_PRODUCT_CLASS_READINESS_AUDIT.json"
REPORT_PATH = ROOT / "docs" / "DIO_PRODUCT_CLASS_READINESS_2026-08-16.md"
PACKAGE_ROOT = ROOT / "state" / "product_class_packages"
DELIVERABLE_ROOT = ROOT / "deliverables" / "product_class_packages"
PRODUCT_CLASS_SITE_ROOT = ROOT / "sites" / "product-classes"


READY_TO_SELL_CONTROLLED_PILOT = {
    "Evidex EvidenceOps": {
        "score": 86,
        "confidence": "high",
        "evidence": [
            "sites/evidex/index.html",
            "sites/evidex/golden-case/index.html",
            "docs/EVIDEX_TRANSACTION_LOOP_PROOF.md",
            "deliverables/evidex_golden_transaction_loop/evidex/evidex-488c40b13ce3498ed076/CLOSEOUT_RECEIPT.json",
        ],
        "next": "Use as the first paid controlled pilot wedge.",
    },
    "HOMS Assess": {
        "score": 78,
        "confidence": "medium",
        "evidence": [
            "sites/homs/index.html",
            "docs/HOMS_SELLING_KIT.md",
            "state/production_engines/ENGINE_AUDIT_RECEIPT.json",
            "scripts/run_homs_hymark_batch.py",
        ],
        "next": "Sell only with a complete batch/rubric/memo intake and educator review.",
    },
    "HOMS Exam": {
        "score": 78,
        "confidence": "medium",
        "evidence": [
            "sites/homs/index.html",
            "sites/homs/assets/homs-exam-studio.png",
            "deliverables/homs_tight8_term_contextual_packs/HOMS_TIGHT8_TERM_CONTEXTUAL_BATCH.json",
            "docs/HOMS_CAPS_ONTOLOGY_CLOSING_PROOF.md",
        ],
        "next": "Offer as scoped exam-studio pilots by grade, subject and term; require educator approval.",
    },
    "HOMS Learning Studio": {
        "score": 74,
        "confidence": "medium",
        "evidence": [
            "sites/homs/learning-studio/index.html",
            "docs/HOMS_LEARNING_STUDIO_GOLDEN_PROOF.md",
            "deliverables/homs_learning_studio/grade_10_physical_sciences_term_3_motion/HOMS_G10_T3_MOTION_ONE_TOPIC_COMPANION.zip",
            "deliverables/homs_learning_studio/grade_10_physical_sciences_term_3_motion/video/HOMS_G10_T3_MOTION_VIDEO_LESSON.mp4",
        ],
        "next": "Sell as one-topic companion pilots; do not claim broad catalogue coverage yet.",
    },
    "Sophia Review": {
        "score": 82,
        "confidence": "high",
        "evidence": [
            "sites/sophia/index.html",
            "deliverables/sophia_academic_reviews/SOPHIA-COMMERCIAL-DEMO-001/SOPHIA-COMMERCIAL-DEMO-001_SOPHIA_REVIEW_PACK.zip",
            "state/sophia_jobs/SOPHIA-COMMERCIAL-DEMO-001/JOB.json",
            "scripts/manage_sophia_commercial.py",
        ],
        "next": "Run invite-only manuscript/section reviews with explicit no-ghostwriting language.",
    },
    "VAMP Performance": {
        "score": 76,
        "confidence": "medium",
        "evidence": [
            "sites/vamp/index.html",
            "deliverables/vamp_snapshots/VAMP-GENERIC-UNIVERSITY-PROOF-001/VAMP-GENERIC-UNIVERSITY-PROOF-001_VAMP_EVIDENCE_SNAPSHOT.zip",
            "state/vamp_jobs/VAMP-GENERIC-UNIVERSITY-PROOF-001/JOB.json",
            "docs/VAMP_PROFILED_EVIDENCE_ARCHITECTURE.md",
        ],
        "next": "Invite-only pilots until non-NWU onboarding and privacy economics are proven.",
    },
    "Document Studio Edit": {
        "score": 82,
        "confidence": "high",
        "evidence": [
            "sites/document-studio/index.html",
            "docs/DOCUMENT_STUDIO_GOLDEN_PROOF.md",
            "deliverables/document_studio/DIO-DOC-GOLDEN-001/DIO-DOC-GOLDEN-001_DOCUMENT_STUDIO_REVIEW_PACK.zip",
            "scripts/manage_document_studio_commercial.py",
        ],
        "next": "Sell one-document technical edit pilots with redline/change-ledger review.",
    },
    "Document Studio Localize": {
        "score": 78,
        "confidence": "medium",
        "evidence": [
            "sites/document-studio/index.html",
            "docs/DOCUMENT_STUDIO_MULTILINGUAL_ROUTES.md",
            "deliverables/document_studio/DIO-DOC-ISIZULU-001/DIO-DOC-ISIZULU-001_DOCUMENT_STUDIO_REVIEW_PACK.zip",
            "deliverables/document_studio/DIO-DOC-SESOTHO-001/DIO-DOC-SESOTHO-001_DOCUMENT_STUDIO_REVIEW_PACK.zip",
            "deliverables/document_studio/DIO-DOC-SETSWANA-001/DIO-DOC-SETSWANA-001_DOCUMENT_STUDIO_REVIEW_PACK.zip",
        ],
        "next": "Sell reviewed translation packs only with human language approval boundaries.",
    },
    "Document Studio Publish": {
        "score": 80,
        "confidence": "high",
        "evidence": [
            "sites/document-studio/index.html",
            "docs/DIO_FORMAT_CORE.md",
            "deliverables/document_studio/DIO-DOC-GOLDEN-001/pdf/CLEAN_EDITED_COPY.pdf",
            "deliverables/document_studio/DIO-DOC-GOLDEN-001/pdf/BILINGUAL_REVIEW_COPY.pdf",
        ],
        "next": "Offer as document-output packaging inside Document Studio, not as a separate headline yet.",
    },
}


INTERNAL_READY_NOT_STANDALONE = {
    "Market Radar": "Use internally for campaign/product discovery; package later only after repeatable external outcomes.",
    "Opportunity Foundry": "Use internally to create product/opportunity hypotheses.",
    "Offer Lab": "Use internally to generate bounded offer experiments and copy.",
    "Campaign Lab": "Use internally to produce governed campaigns; external campaign service needs measured outcomes first.",
    "Vesper Desk": "Keep as the DIO front door and routing layer, not a public product name yet.",
    "Accessible Publish": "Use as a capability inside Document Studio until accessibility QA gets its own proof pack.",
}


NEAR_READY_PROFILE_EXTENSION = {
    "HOMS Moderate": "Needs typed HOMS moderation lane and one controlled moderation proof.",
    "HOMS Accreditation": "Needs accreditation-profile source pack and criterion proof room.",
    "Sophia Research": "Needs a research-landscape golden pack with source retrieval receipts.",
    "Sophia Integrity": "Needs integrity policy profile and professional review boundary.",
    "PromotionProof": "Can be built from VAMP; needs one promotion-profile proof pack.",
    "CPDProof": "Can be built from VAMP; needs CPD framework profile.",
    "ProjectProof": "Can be built from VAMP/Evidex; needs project contract fixture.",
    "ImpactProof": "Can be built from VAMP/Evidex; needs M&E indicator fixture.",
    "VendorProof": "Can be built from Evidex/VAMP/Sophia; needs vendor questionnaire golden case.",
    "TenderProof": "Needs RFP/tender fixture and Legalis/human authority boundary.",
    "GrantProof": "Needs grant agreement fixture and obligation ledger demo.",
    "AssuranceRoom": "Needs portable room packaging as a reusable output product.",
    "DIO AI Assurance": "Needs AI-governance golden case and stricter validation burden.",
    "Agent Authority": "Needs Valinor/ARDA lease demo tied to a buyer-readable case.",
    "ControlDrift": "Needs a control-baseline watcher demo and drift receipt.",
    "DIO RegOps": "Needs jurisdiction/framework profile and explicit no-legal-advice positioning.",
}

PROCESSING_ORGAN_MAP = {
    "HOMS": {
        "coverage": "native",
        "provided_by": ["HOMS", "Sophia", "Format Core"],
        "note": "Assessment, curriculum and learning-material generation are already present; typed service lanes still improve routing.",
    },
    "Sophia": {
        "coverage": "native",
        "provided_by": ["Sophia"],
        "note": "Research, claim/source mapping, citation checking and reviewer commentary are available.",
    },
    "Evidex": {
        "coverage": "native",
        "provided_by": ["Evidex"],
        "note": "Evidence table, claim mapping, provenance, pack generation and closeout processing are available.",
    },
    "VAMP": {
        "coverage": "native",
        "provided_by": ["VAMP", "Evidex"],
        "note": "Framework/objective-to-evidence coverage and snapshot generation are available.",
    },
    "Document Studio": {
        "coverage": "native",
        "provided_by": ["Document Studio", "Format Core", "Lingua"],
        "note": "Technical edit, redline, translation, glossary, QA and packaged outputs are available.",
    },
    "Lingua": {
        "coverage": "native",
        "provided_by": ["Lingua", "BEAST", "Document Studio"],
        "note": "Semantic object lifecycle, language QA and BEAST reuse/learning are available.",
    },
    "Format Core": {
        "coverage": "native",
        "provided_by": ["Format Core", "Document Studio"],
        "note": "DOCX/PDF/HTML-style output projection is available.",
    },
    "NicheFoundry": {
        "coverage": "native",
        "provided_by": ["NicheFoundry", "Market Command"],
        "note": "Campaign copy, creative families, short-form media and episode scaffolding are available.",
    },
    "Hivenance": {
        "coverage": "native",
        "provided_by": ["Hivenance", "Market Command"],
        "note": "Market observation, hypothesis, dissent/challenge and settlement signals are available.",
    },
    "Commerce": {
        "coverage": "native",
        "provided_by": ["Commerce", "PayPal", "DIO Edge"],
        "note": "Order/payment state and fulfilment release gates are available.",
    },
    "Vesper": {
        "coverage": "native",
        "provided_by": ["Vesper Desk", "Outlook/Graph", "DIO Control Deck"],
        "note": "Intake, conversation binding, routing and mail drafting are available.",
    },
    "Outlook/Graph": {
        "coverage": "native",
        "provided_by": ["Microsoft Graph", "Outlook Triage"],
        "note": "Mailbox intake and draft/send-governance path is available.",
    },
    "BEAST": {
        "coverage": "native",
        "provided_by": ["BEAST", "Lingua", "Control Deck"],
        "note": "Learning, crystallization and control-plane support exist locally; product-specific golden cases are still needed.",
    },
    "Room": {
        "coverage": "composed",
        "provided_by": ["Evidex", "Document Studio", "Format Core", "DIO receipts"],
        "note": "A proof-room can be composed from manifests, evidence packs, hashes and publication bundles; reusable room packaging is not yet a polished product.",
    },
    "Seraph": {
        "coverage": "composed",
        "provided_by": ["Sophia", "BEAST", "Hivenance dissent", "Evidex"],
        "note": "Challenge, contradiction and integrity-style processing can be composed; the old Seraph engine is not yet a first-class adapter here.",
    },
    "Legalis": {
        "coverage": "composed_boundary",
        "provided_by": ["Sophia", "Evidex", "Document Studio", "human authority"],
        "note": "Rule, obligation and prerequisite extraction can be processed, but the output must be positioned as readiness support, not legal advice.",
    },
    "Valinor": {
        "coverage": "composed_boundary",
        "provided_by": ["Control Deck", "product_genesis_policy", "mail/send approval gates"],
        "note": "Capability lease semantics are present as DIO approval gates; sovereign Valinor packaging is not yet a product adapter.",
    },
    "ARDA": {
        "coverage": "composed_boundary",
        "provided_by": ["Control Deck", "receipts", "operator approval"],
        "note": "Execution identity/receipt processing can be represented by current receipts; ARDA-grade attestation is not yet integrated as a product adapter.",
    },
    "Twin": {
        "coverage": "composed",
        "provided_by": ["Hivenance", "BEAST", "Market Command", "DIO telemetry"],
        "note": "Expected-vs-actual drift can be composed from observations and receipts; a dedicated digital-twin adapter is still absent.",
    },
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


def evidence_state(paths: list[str]) -> list[dict[str, Any]]:
    evidence = []
    for item in paths:
        path = ROOT / item
        evidence.append({"path": item, "exists": path.exists()})
    return evidence


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product-class"


def packaged_controlled_pilot(name: str) -> dict[str, Any] | None:
    slug = slugify(name)
    paths = [
        f"state/product_class_packages/{slug}/PRODUCT_PROFILE.json",
        f"state/product_class_packages/{slug}/INTAKE_SCHEMA.json",
        f"state/product_class_packages/{slug}/PROCESSING_ROUTE.json",
        f"state/product_class_packages/{slug}/MAIL_TEMPLATES.json",
        f"state/product_class_packages/{slug}/MARKET_COMMAND_SEED.json",
        f"state/product_class_packages/{slug}/GOLDEN_PROOF.md",
        f"state/product_class_packages/{slug}/SMOKE_TEST_RECEIPT.json",
        f"state/product_class_packages/{slug}/PACKAGE_MANIFEST.json",
        f"sites/product-classes/{slug}/index.html",
        f"deliverables/product_class_packages/{slug}/{slug}_CONTROLLED_PILOT_PACKAGE.zip",
    ]
    evidence = evidence_state(paths)
    missing = [item["path"] for item in evidence if not item["exists"]]
    smoke_path = PACKAGE_ROOT / slug / "SMOKE_TEST_RECEIPT.json"
    smoke_passed = False
    if smoke_path.exists():
        try:
            smoke = load_json(smoke_path)
            smoke_passed = smoke.get("result") == "passed" and all(check.get("passed") for check in smoke.get("checks", []))
        except (json.JSONDecodeError, OSError):
            smoke_passed = False
    if missing or not smoke_passed:
        return None
    return {
        "tier": "launch_controlled_pilot",
        "label": "ready now",
        "score": 76,
        "confidence": "medium",
        "evidence": evidence,
        "missing_evidence": [],
        "next_step": "Run the first buyer-shaped controlled pilot and measure time, revisions, payment state and delivery quality.",
        "promotion_basis": "typed package, product page, golden proof, smoke receipt and deliverable zip exist",
    }


def classify(row: dict[str, Any]) -> dict[str, Any]:
    name = row["Incarnation"]
    if name in READY_TO_SELL_CONTROLLED_PILOT:
        record = READY_TO_SELL_CONTROLLED_PILOT[name]
        evidence = evidence_state(record["evidence"])
        missing = [item["path"] for item in evidence if not item["exists"]]
        return {
            "tier": "launch_controlled_pilot",
            "label": "ready now",
            "score": record["score"] - (8 if missing else 0),
            "confidence": "medium" if missing and record["confidence"] == "high" else record["confidence"],
            "evidence": evidence,
            "missing_evidence": missing,
            "next_step": record["next"],
        }
    packaged = packaged_controlled_pilot(name)
    if packaged:
        return packaged
    if name in INTERNAL_READY_NOT_STANDALONE:
        return {
            "tier": "internal_operational_capability",
            "label": "ready internally",
            "score": 72,
            "confidence": "medium",
            "evidence": evidence_state(["state/market_command/market_command.sqlite", "state/marketing_factory/CREATIVE_FAMILY_REGISTRY.json"]),
            "missing_evidence": [],
            "next_step": INTERNAL_READY_NOT_STANDALONE[name],
        }
    if name in NEAR_READY_PROFILE_EXTENSION:
        return {
            "tier": "near_ready_profile_extension",
            "label": "near ready",
            "score": 60 if row.get("state") == "incarnated" else 54,
            "confidence": "medium",
            "evidence": evidence_state(["state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_IMPORT.json"]),
            "missing_evidence": [],
            "next_step": NEAR_READY_PROFILE_EXTENSION[name],
        }
    return {
        "tier": "not_ready",
        "label": "not ready yet",
        "score": 40 if row.get("state") == "candidate" else 48,
        "confidence": "medium",
        "evidence": evidence_state(["state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_IMPORT.json"]),
        "missing_evidence": [],
        "next_step": "Needs a typed profile, golden proof artifact, public/lead route and smoke-run receipt before marketing.",
    }


def split_organs(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def processing_coverage(row: dict[str, Any]) -> dict[str, Any]:
    organs = split_organs(row.get("Main organs", ""))
    mapped = []
    missing = []
    coverage_rank = {"native": 3, "composed": 2, "composed_boundary": 1}
    weakest = 3
    for organ in organs:
        info = PROCESSING_ORGAN_MAP.get(organ)
        if not info:
            missing.append(organ)
            weakest = 0
            mapped.append({
                "organ": organ,
                "coverage": "missing",
                "provided_by": [],
                "note": "No mapped processing organ found in DIO yet.",
            })
            continue
        weakest = min(weakest, coverage_rank.get(info["coverage"], 0))
        mapped.append({"organ": organ, **info})
    if missing:
        state = "processing_gap"
    elif weakest >= 3:
        state = "native_processing_ready"
    elif weakest == 2:
        state = "composed_processing_ready"
    else:
        state = "boundary_processing_ready"
    return {
        "state": state,
        "organs": mapped,
        "missing_organs": missing,
        "processing_ready": not missing,
        "summary": "All required processing organs are mapped to existing DIO processors." if not missing else "One or more processing organs are not mapped.",
    }


def build_report(registry: dict[str, Any], audit: dict[str, Any]) -> str:
    def section(title: str, tier: str) -> list[str]:
        rows = [row for row in registry["incarnations"] if row["readiness"]["tier"] == tier]
        lines = [f"## {title}", "", "| Product class | Suite | Readiness | Score | Confidence | Next step |", "| --- | --- | --- | ---: | --- | --- |"]
        for row in rows:
            readiness = row["readiness"]
            lines.append(
                f"| {row['Incarnation']} | {row['Suite']} | {readiness['label']} | {readiness['score']} | {readiness['confidence']} | {readiness['next_step']} |"
            )
        if not rows:
            lines.append("| None | - | - | - | - | - |")
        lines.append("")
        return lines

    ready_count = audit["summary"].get("launch_controlled_pilot", 0)
    internal_count = audit["summary"].get("internal_operational_capability", 0)
    near_count = audit["summary"].get("near_ready_profile_extension", 0)
    not_ready_count = audit["summary"].get("not_ready", 0)
    lines = [
        "# DIO Product Class Readiness",
        "",
        f"Generated: `{audit['generated_at']}`",
        f"Atlas registry: `{REGISTRY_PATH.relative_to(ROOT)}`",
        "",
        "## Verdict",
        "",
        f"The atlas contains 53 product classes. {ready_count} are ready to put in front of controlled pilot leads now. {internal_count} are operationally ready as internal DIO capabilities or bundled service features. {near_count} are near-ready profile extensions. {not_ready_count} should stay out of public marketing until they have typed profiles, golden proofs and smoke receipts.",
        "",
        "Important correction: commercial readiness and processing readiness are not the same thing. The deeper atlas read shows that every product class can be staged through existing DIO processing organs. The missing layer for many classes is packaging: typed profile, golden proof, public offer, smoke receipt and sometimes stricter authority language.",
        "",
        "## Summary",
        "",
        "| Tier | Count | Meaning |",
        "| --- | ---: | --- |",
    ]
    for tier, label in [
        ("launch_controlled_pilot", "Ready now"),
        ("internal_operational_capability", "Ready internally"),
        ("near_ready_profile_extension", "Near ready"),
        ("not_ready", "Not ready yet"),
    ]:
        lines.append(f"| {label} | {audit['summary'].get(tier, 0)} | {audit['tier_meanings'][tier]} |")
    lines.extend([
        "",
        "## Processing Coverage",
        "",
        "| Processing state | Count | Meaning |",
        "| --- | ---: | --- |",
    ])
    for state, meaning in [
        ("native_processing_ready", "All required organs have native attached processors."),
        ("composed_processing_ready", "Processing is covered by composition over existing organs."),
        ("boundary_processing_ready", "Processing is covered, but authority/legal/attestation wording must be strict."),
        ("processing_gap", "A required organ is genuinely missing."),
    ]:
        lines.append(f"| {state} | {audit['processing_summary'].get(state, 0)} | {meaning} |")
    lines.extend([
        "",
        "In plain English: the platform can process these classes. What it cannot honestly do yet is sell every one as a polished, proven public product.",
        "",
    ])
    lines.extend(["", *section("Ready To Sell As Controlled Pilots", "launch_controlled_pilot")])
    lines.extend(section("Ready Internally, Not As Standalone Public Products", "internal_operational_capability"))
    lines.extend(section("Near-Ready Profile Extensions", "near_ready_profile_extension"))
    lines.extend(section("Not Ready Yet", "not_ready"))
    return "\n".join(lines)


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    generated_at = utc_now()
    counts: dict[str, int] = {}
    processing_counts: dict[str, int] = {}
    for row in registry["incarnations"]:
        readiness = classify(row)
        processing = processing_coverage(row)
        row["readiness"] = readiness
        row["processing_coverage"] = processing
        counts[readiness["tier"]] = counts.get(readiness["tier"], 0) + 1
        processing_counts[processing["state"]] = processing_counts.get(processing["state"], 0) + 1
    audit = {
        "schema": "dio.product_class_readiness_audit.v1",
        "generated_at": generated_at,
        "source_registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "summary": counts,
        "processing_summary": processing_counts,
        "processing_ready_total": sum(1 for row in registry["incarnations"] if row["processing_coverage"]["processing_ready"]),
        "tier_meanings": {
            "launch_controlled_pilot": "Buyer-facing controlled pilot can be offered now with human approval and bounded claims.",
            "internal_operational_capability": "Operationally useful and wired, but better used as internal machinery or bundled capability.",
            "near_ready_profile_extension": "Architecture/profile is credible; needs a typed profile, golden proof and smoke receipt.",
            "not_ready": "Do not market yet as its own product class.",
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
