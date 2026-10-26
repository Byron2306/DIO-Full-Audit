#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"
PLAN_PATH = ROOT / "state" / "product_portfolio" / "DIO_PRODUCT_CLASS_ACTIVATION_PLAN.json"
CONFIG_PATH = ROOT / "config" / "product_class_activation_waves.json"
REPORT_PATH = ROOT / "docs" / "DIO_PRODUCT_CLASS_ACTIVATION_PLAN_2026-08-16.md"


PRIORITY_PRODUCTS = {
    "GrantProof": {
        "wave": "wave_1_fast_packaging",
        "priority": 1,
        "reason": "Evidex already handles evidence packs and VAMP handles outcome/indicator evidence; only the grant obligation profile and demo fixture are missing.",
        "first_buyer": "NGOs, university grant offices, research administrators",
        "pilot_offer": "One grant agreement or reporting period into an obligation ledger and evidence pack.",
        "demo_fixture": "Redacted grant agreement + two report periods + scattered evidence folder.",
    },
    "VendorProof": {
        "wave": "wave_1_fast_packaging",
        "priority": 2,
        "reason": "Vendor questionnaire work maps cleanly onto Evidex, VAMP and Sophia source review.",
        "first_buyer": "SME suppliers, procurement teams, security/risk offices",
        "pilot_offer": "One vendor questionnaire into a response evidence pack with gaps and provenance.",
        "demo_fixture": "Generic vendor security/procurement questionnaire + policy excerpts + proof files.",
    },
    "TenderProof": {
        "wave": "wave_1_fast_packaging",
        "priority": 3,
        "reason": "Tender/RFP compliance matrices are high-pain and reuse Sophia + Evidex + Document Studio; authority wording must be strict.",
        "first_buyer": "SMEs, bid writers, NGO proposal teams, university procurement respondents",
        "pilot_offer": "One tender pack into a compliance matrix, missing-items list and submission dossier draft.",
        "demo_fixture": "Public/sample RFP + company capability documents + certificate folder.",
    },
    "PromotionProof": {
        "wave": "wave_1_fast_packaging",
        "priority": 4,
        "reason": "This is almost a VAMP profile extension and can reuse the existing performance evidence snapshot.",
        "first_buyer": "Academics and professional staff preparing promotion/tenure or advancement portfolios",
        "pilot_offer": "One promotion framework into an evidence portfolio with gaps and review candidates.",
        "demo_fixture": "Generic promotion criteria + CV/activity log + publication/service evidence folder.",
    },
    "AuditProof": {
        "wave": "wave_1_fast_packaging",
        "priority": 5,
        "reason": "Audit/control evidence is the same Evidence + Assurance pattern as Evidex with a control-profile overlay.",
        "first_buyer": "Internal auditors, consultants, quality/risk managers",
        "pilot_offer": "One control area into an evidence matrix, gap list and review room.",
        "demo_fixture": "Small control checklist + SOP excerpts + three implementation records.",
    },
    "DossierOps": {
        "wave": "wave_1_fast_packaging",
        "priority": 6,
        "reason": "Document Studio and Format Core already produce clean, indexed, multi-format output packs.",
        "first_buyer": "Consultants, bid teams, programme offices, legal/admin support teams",
        "pilot_offer": "One messy multi-document folder into an indexed dossier with manifest and review copy.",
        "demo_fixture": "Mixed document set + desired index + output style brief.",
    },
    "Sophia Research": {
        "wave": "wave_2_research_integrity",
        "priority": 7,
        "reason": "Sophia already has the review pipeline; it needs a research-landscape product wrapper.",
        "first_buyer": "Postgraduate students, supervisors, research groups, R&D teams",
        "pilot_offer": "One research question into a literature/evidence map and contradiction ledger.",
        "demo_fixture": "Research question + seed papers + search boundaries + excluded-source policy.",
    },
    "Sophia Integrity": {
        "wave": "wave_2_research_integrity",
        "priority": 8,
        "reason": "Integrity cases can be composed from Sophia claim/source checks and Seraph-style challenge logic.",
        "first_buyer": "Research offices, supervisors, journals, ethics/support units",
        "pilot_offer": "One manuscript or claim set into an inspectable integrity review case.",
        "demo_fixture": "Controlled draft with known citation/source weaknesses and correction history.",
    },
    "HOMS Moderate": {
        "wave": "wave_2_education_extensions",
        "priority": 9,
        "reason": "HOMS Assess already exists; moderation needs marker-drift comparison and disagreement reporting.",
        "first_buyer": "Schools, departments, exam bodies, module coordinators",
        "pilot_offer": "One marked batch into moderation flags, drift report and review summary.",
        "demo_fixture": "Two marker sets + rubric + memo + sample learner scripts.",
    },
    "HOMS Accreditation": {
        "wave": "wave_2_education_extensions",
        "priority": 10,
        "reason": "Accreditation is HOMS + VAMP + Evidex over an accreditation criteria profile.",
        "first_buyer": "Programme coordinators, faculties, colleges, quality offices",
        "pilot_offer": "One programme criterion area into an accreditation evidence matrix and proof room.",
        "demo_fixture": "Programme outcomes + module guides + sample assessment/evidence folder.",
    },
    "DIO AI Assurance": {
        "wave": "wave_3_trust_and_authority",
        "priority": 11,
        "reason": "BEAST, Sophia, Evidex and receipts can process the case; validation burden is high, so it needs a narrow demo.",
        "first_buyer": "AI vendors, SaaS teams, internal AI governance teams",
        "pilot_offer": "One AI feature release into controls, eval evidence, limitations and approval receipt.",
        "demo_fixture": "Toy AI feature policy + eval logs + model card + release notes.",
    },
    "Agent Authority": {
        "wave": "wave_3_trust_and_authority",
        "priority": 12,
        "reason": "The approval/capability gates already exist; it needs buyer-readable lease/authority packaging.",
        "first_buyer": "Agent builders, enterprise automation teams, risk owners",
        "pilot_offer": "One agent action class into prerequisite checks, allowed action envelope and execution receipt.",
        "demo_fixture": "Agent action proposal + allowed tools + forbidden side effects + approval chain.",
    },
    "ControlDrift": {
        "wave": "wave_3_trust_and_authority",
        "priority": 13,
        "reason": "Hivenance observation, BEAST learning and DIO telemetry can already compare expected vs actual state.",
        "first_buyer": "Security, quality, compliance and operations teams",
        "pilot_offer": "One baseline control into a drift report and attention queue.",
        "demo_fixture": "Expected-state checklist + two snapshots + one deliberate drift case.",
    },
    "DIO RegOps": {
        "wave": "wave_4_boundary_heavy",
        "priority": 14,
        "reason": "The processing exists, but regulatory/legal positioning must remain readiness support only.",
        "first_buyer": "Programme offices, regulated SMEs, admin teams",
        "pilot_offer": "One regulation or policy obligation set into a readiness register and evidence pack.",
        "demo_fixture": "Public rule excerpt + internal policy + evidence/status folder.",
    },
}


DEFAULT_WAVES = {
    "wave_1_fast_packaging": "Package the quickest evidence/document extensions into controlled pilots.",
    "wave_2_research_integrity": "Package Sophia/HOMS domain extensions that need better domain-specific proof.",
    "wave_2_education_extensions": "Package education-adjacent extensions once HOMS typed lanes are in place.",
    "wave_3_trust_and_authority": "Package high-value AI/agent assurance products with stricter validation.",
    "wave_4_boundary_heavy": "Package legal/regulatory/permitting products only with strict no-advice boundaries.",
    "wave_5_later_catalogue": "Hold until a buyer asks or a reusable proof naturally falls out of another job.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def organ_providers(row: dict[str, Any]) -> list[str]:
    providers: list[str] = []
    for organ in (row.get("processing_coverage") or {}).get("organs", []):
        providers.extend(organ.get("provided_by") or [])
    return sorted(set(providers))


def activation_entry(row: dict[str, Any]) -> dict[str, Any]:
    name = row["Incarnation"]
    readiness = row.get("readiness") or {}
    processing = row.get("processing_coverage") or {}
    override = PRIORITY_PRODUCTS.get(name, {})
    if override:
        wave = override["wave"]
        priority = override["priority"]
    elif readiness.get("tier") == "near_ready_profile_extension":
        wave = "wave_3_trust_and_authority" if "AI & Digital Trust" in row.get("Suite", "") else "wave_2_education_extensions"
        priority = 50
    elif readiness.get("tier") == "not_ready":
        wave = "wave_5_later_catalogue"
        priority = 90
    else:
        wave = "already_packaged"
        priority = 0
    return {
        "product_class": name,
        "candidate_id": row.get("candidate_id"),
        "suite": row.get("Suite"),
        "commercial_readiness": readiness.get("label"),
        "processing_state": processing.get("state"),
        "processing_ready": processing.get("processing_ready", False),
        "processing_provided_by": organ_providers(row),
        "activation_wave": wave,
        "priority": priority,
        "why_this_wave": override.get("reason", "Lower-priority catalogue packaging; wait for demand signal or adjacent proof reuse."),
        "first_buyer": override.get("first_buyer", row.get("Buyer / market", "")),
        "pilot_offer": override.get("pilot_offer", f"One bounded {name} pilot using existing DIO processors."),
        "demo_fixture": override.get("demo_fixture", "A controlled, non-sensitive fixture matching the product profile."),
        "activation_checklist": [
            "create typed product profile",
            "create controlled demo fixture",
            "run existing processors through the profile",
            "generate golden proof pack and receipt",
            "add public offer block or product page",
            "add intake schema / lead projection",
            "add branded mail templates and delivery boundary",
            "add Market Command campaign family",
            "run controlled smoke test",
            "mark as launch_controlled_pilot only after review",
        ],
        "authority_boundary": "Human approval remains required for source interpretation, final claims, external delivery, public release and payment/spend actions.",
    }


def build_plan() -> dict[str, Any]:
    registry = load_registry()
    entries = [
        activation_entry(row)
        for row in registry["incarnations"]
        if (row.get("readiness") or {}).get("tier") not in {"launch_controlled_pilot", "internal_operational_capability"}
    ]
    entries.sort(key=lambda item: (item["priority"], item["product_class"]))
    wave_counts: dict[str, int] = {}
    for entry in entries:
        wave_counts[entry["activation_wave"]] = wave_counts.get(entry["activation_wave"], 0) + 1
    return {
        "schema": "dio.product_class_activation_plan.v1",
        "generated_at": utc_now(),
        "source_registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "summary": {
            "products_to_package": len(entries),
            "processing_ready": sum(1 for entry in entries if entry["processing_ready"]),
            "wave_counts": wave_counts,
        },
        "wave_meanings": DEFAULT_WAVES,
        "entries": entries,
    }


def build_report(plan: dict[str, Any]) -> str:
    lines = [
        "# DIO Product Class Activation Plan",
        "",
        f"Generated: `{plan['generated_at']}`",
        f"Source registry: `{plan['source_registry']}`",
        "",
        "## Core Move",
        "",
        "Do not build new engines first. Build typed product profiles and golden proof wrappers over the processors DIO already has: Sophia, Evidex, VAMP, Document Studio, Lingua, Format Core, NicheFoundry, Hivenance, Market Command, BEAST and the Control Deck.",
        "",
        f"Products needing packaging: `{plan['summary']['products_to_package']}`",
        f"Already processing-ready among them: `{plan['summary']['processing_ready']}`",
        "",
        "## Activation Factory",
        "",
        "Every class graduates through the same checklist:",
        "",
        "1. Typed product profile",
        "2. Controlled demo fixture",
        "3. Existing processor route",
        "4. Golden proof pack and receipt",
        "5. Public offer block or product page",
        "6. Intake schema / lead projection",
        "7. Branded mail and delivery boundary",
        "8. Market Command campaign family",
        "9. Controlled smoke test",
        "10. Operator promotion to controlled-pilot launch",
        "",
        "## Waves",
        "",
        "| Wave | Count | Meaning |",
        "| --- | ---: | --- |",
    ]
    for wave, meaning in plan["wave_meanings"].items():
        lines.append(f"| {wave} | {plan['summary']['wave_counts'].get(wave, 0)} | {meaning} |")
    lines.extend(["", "## Product Backlog", "", "| Priority | Product | Wave | Processing | First buyer | Pilot offer | Demo fixture |", "| ---: | --- | --- | --- | --- | --- | --- |"])
    for entry in plan["entries"]:
        lines.append(
            f"| {entry['priority']} | {entry['product_class']} | {entry['activation_wave']} | {entry['processing_state']} | {entry['first_buyer']} | {entry['pilot_offer']} | {entry['demo_fixture']} |"
        )
    lines.extend(["", "## Immediate Recommendation", ""])
    if plan["entries"]:
        first_wave = plan["entries"][0]["activation_wave"]
        first_wave_products = [entry["product_class"] for entry in plan["entries"] if entry["activation_wave"] == first_wave][:8]
        lines.extend([
            f"Build `{first_wave}` next: {', '.join(first_wave_products)}.",
            "",
        ])
    else:
        lines.extend([
            "All currently buyer-facing atlas product classes have controlled-pilot packaging artifacts. The next move is not more packaging; it is controlled buyer pilots, campaign release, telemetry and proof-of-sale learning.",
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    plan = build_plan()
    write_json(PLAN_PATH, plan)
    write_json(CONFIG_PATH, plan)
    write_text(REPORT_PATH, build_report(plan))
    print(json.dumps({
        "schema": plan["schema"],
        "generated_at": plan["generated_at"],
        "summary": plan["summary"],
        "report_path": str(REPORT_PATH.relative_to(ROOT)),
    }, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
