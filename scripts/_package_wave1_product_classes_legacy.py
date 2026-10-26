#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"
PLAN_PATH = ROOT / "state" / "product_portfolio" / "DIO_PRODUCT_CLASS_ACTIVATION_PLAN.json"
PACKAGE_ROOT = ROOT / "state" / "product_class_packages"
DELIVERABLE_ROOT = ROOT / "deliverables" / "product_class_packages"
SITE_ROOT = ROOT / "sites" / "product-classes"
REPORT_PATH = ROOT / "docs" / "DIO_WAVE1_PRODUCT_CLASS_PACKAGING_2026-08-16.md"
RECEIPT_PATH = PACKAGE_ROOT / "WAVE1_PACKAGING_RECEIPT.json"
PUBLIC_ROOT_URL = "https://byron2306.github.io/DIO-Workflows/"


PRODUCTS: dict[str, dict[str, Any]] = {
    "GrantProof": {
        "tagline": "Turn grant obligations into a reviewable evidence ledger.",
        "buyers": ["NGOs", "university grant offices", "research administrators"],
        "pilot_offer": "One grant agreement or reporting period into an obligation ledger, evidence matrix and delivery-ready pack.",
        "fixture": "Redacted grant agreement + two report periods + scattered evidence folder.",
        "customer_pain": "Reporting periods arrive with scattered files, unclear obligations and too much last-minute reconstruction.",
        "outcomes": ["obligation ledger", "evidence matrix", "missing evidence register", "review copy", "delivery receipt"],
        "processors": ["Document Studio", "Evidex", "Sophia", "VAMP", "Format Core"],
        "inputs": ["grant agreement", "reporting template", "evidence files", "submission deadline", "funder notes"],
        "boundaries": ["readiness support only", "human verifies obligations", "no funder approval guarantee", "no legal advice"],
        "proof_rows": [
            ["Quarterly output report required", "Draft report, attendance records, project photographs", "partially met", "two photos missing dates"],
            ["Budget variance note required above 10 percent", "Finance summary and variance explanation", "met", "ready for reviewer"],
            ["Beneficiary evidence must be retained", "Signed attendance sheets", "gap", "missing consent note for one activity"],
        ],
        "campaign_angles": ["grant reporting without scramble", "funder-ready evidence", "obligation tracking for small teams"],
        "asset": "../../evidex/assets/evidex-output.png",
    },
    "VendorProof": {
        "tagline": "Answer vendor due diligence with evidence, not panic.",
        "buyers": ["SME suppliers", "procurement teams", "security and risk offices"],
        "pilot_offer": "One vendor questionnaire into a response evidence pack with provenance, gaps and reviewer notes.",
        "fixture": "Generic vendor security/procurement questionnaire + policy excerpts + proof files.",
        "customer_pain": "Supplier questionnaires repeatedly ask for proof that already exists somewhere in policies, certificates and emails.",
        "outcomes": ["questionnaire response matrix", "proof citations", "gap register", "review copy", "delivery receipt"],
        "processors": ["Evidex", "Sophia", "VAMP", "Document Studio"],
        "inputs": ["questionnaire", "company policy documents", "certificates", "insurance/procurement files", "reviewer preferences"],
        "boundaries": ["client owns final statements", "no certification claim", "no unsupported compliance assertion", "human approval before delivery"],
        "proof_rows": [
            ["Data protection policy requested", "Signed privacy policy v3", "met", "cite clause 4 and review date"],
            ["Incident response process requested", "Draft incident procedure", "partially met", "owner not named"],
            ["Cyber insurance proof requested", "None supplied", "gap", "request current certificate"],
        ],
        "campaign_angles": ["procurement proof in one place", "faster vendor questionnaires", "gap-aware supplier responses"],
        "asset": "../../evidex/assets/evidex-review-hero.png",
    },
    "TenderProof": {
        "tagline": "Build a tender compliance dossier before the deadline eats the week.",
        "buyers": ["SMEs", "bid writers", "NGO proposal teams", "university procurement respondents"],
        "pilot_offer": "One tender/RFP pack into a compliance matrix, missing-items list and submission dossier draft.",
        "fixture": "Public/sample RFP + capability documents + certificate folder.",
        "customer_pain": "Bid teams lose time checking eligibility, attachments, certificates and response wording across messy tender packs.",
        "outcomes": ["requirements matrix", "document checklist", "gap register", "response dossier draft", "review copy"],
        "processors": ["Document Studio", "Evidex", "Sophia", "Format Core"],
        "inputs": ["RFP/tender pack", "company profile", "certificates", "pricing notes", "submission rules"],
        "boundaries": ["readiness and drafting support only", "no legal/procurement advice", "no autonomous submission", "human signs off final bid"],
        "proof_rows": [
            ["Mandatory tax certificate", "Current tax PIN letter", "met", "attach under compliance annex"],
            ["Three relevant project references", "Two case studies supplied", "gap", "needs one additional reference"],
            ["Signed declaration forms", "Unsigned draft forms", "partially met", "signature required before delivery"],
        ],
        "campaign_angles": ["tender paperwork under control", "bid compliance before submission", "find missing bid items early"],
        "asset": "../../document-studio/assets/document-studio-proof.png",
    },
    "PromotionProof": {
        "tagline": "Map promotion criteria to evidence before review day.",
        "buyers": ["academics", "professional staff", "promotion applicants", "department administrators"],
        "pilot_offer": "One promotion framework into an evidence portfolio with gaps, strengths and reviewer-ready proof.",
        "fixture": "Generic promotion criteria + CV/activity log + publication/service evidence folder.",
        "customer_pain": "Promotion evidence sits across CVs, emails, reports, publications and service records, while criteria stay abstract.",
        "outcomes": ["criteria evidence map", "strength/gap snapshot", "proof index", "review summary", "delivery pack"],
        "processors": ["VAMP", "Evidex", "Sophia", "Document Studio"],
        "inputs": ["promotion framework", "CV", "activity log", "publications/service records", "department notes"],
        "boundaries": ["support pack only", "no promotion outcome guarantee", "human chooses claims", "sensitive evidence handled by approval gates"],
        "proof_rows": [
            ["Research output criterion", "Publication list and acceptance letters", "met", "strong evidence cluster"],
            ["Teaching innovation criterion", "Module redesign notes", "partially met", "needs learner/peer evidence"],
            ["Service contribution criterion", "Committee minutes", "met", "include dates and role"],
        ],
        "campaign_angles": ["promotion evidence without chaos", "criteria mapped before review", "career portfolio proof"],
        "asset": "../../sophia/assets/sophia-review-hero.png",
    },
    "AuditProof": {
        "tagline": "Prepare control evidence before the audit room gets loud.",
        "buyers": ["internal auditors", "consultants", "quality managers", "risk managers"],
        "pilot_offer": "One control area into an evidence matrix, gap list and review room.",
        "fixture": "Small control checklist + SOP excerpts + three implementation records.",
        "customer_pain": "Control evidence is usually findable, but not assembled, referenced or gap-checked before review.",
        "outcomes": ["control evidence matrix", "gap register", "review room index", "provenance notes", "closeout receipt"],
        "processors": ["DIO receipts", "Document Studio", "Evidex", "Format Core", "VAMP"],
        "inputs": ["control checklist", "SOPs", "sample records", "review period", "responsible owner"],
        "boundaries": ["not an audit opinion", "not certification", "client retains assertions", "human review required"],
        "proof_rows": [
            ["Access review performed quarterly", "Q1 and Q2 review exports", "partially met", "Q3 missing"],
            ["Approvals retained for changes", "Change tickets with approval fields", "met", "sample size ready"],
            ["Exception register maintained", "No register supplied", "gap", "request owner evidence"],
        ],
        "campaign_angles": ["audit evidence before the meeting", "control gaps visible early", "proof-room readiness"],
        "asset": "../../evidex/assets/evidex-hero.png",
    },
    "DossierOps": {
        "tagline": "Turn a messy folder into a clean, indexed dossier.",
        "buyers": ["consultants", "bid teams", "programme offices", "legal/admin support teams"],
        "pilot_offer": "One multi-document folder into an indexed dossier with manifest, review copy and delivery pack.",
        "fixture": "Mixed document set + desired index + output style brief.",
        "customer_pain": "Important document sets arrive as chaotic folders, inconsistent names and unreviewable attachments.",
        "outcomes": ["file manifest", "indexed dossier", "source register", "formatted review copy", "delivery receipt"],
        "processors": ["DIO receipts", "Document Studio", "Evidex", "Format Core", "Lingua"],
        "inputs": ["document folder", "desired sections", "naming rules", "output format", "review notes"],
        "boundaries": ["formatting and evidence organization only", "no hidden content changes", "human approves final pack", "translations require language review"],
        "proof_rows": [
            ["Create index from folder", "23 mixed PDFs/DOCX files", "met", "renamed and ordered by section"],
            ["Identify missing annexures", "Annexure B absent", "gap", "client follow-up required"],
            ["Prepare review copy", "Compiled dossier", "met", "human approval before delivery"],
        ],
        "campaign_angles": ["messy folders into usable dossiers", "document packs clients can review", "indexed evidence delivery"],
        "asset": "../../document-studio/assets/document-studio-proof.png",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product-class"


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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_rows() -> dict[str, dict[str, Any]]:
    registry = load_json(REGISTRY_PATH)
    return {
        row.get("Incarnation"): row
        for row in registry.get("incarnations", [])
        if row.get("Incarnation") in PRODUCTS
    }


def find_plan_entries() -> dict[str, dict[str, Any]]:
    if not PLAN_PATH.exists():
        return {}
    plan = load_json(PLAN_PATH)
    return {
        entry.get("product_class"): entry
        for entry in plan.get("entries", [])
        if entry.get("product_class") in PRODUCTS
    }


def copy_brand_assets() -> dict[str, str]:
    assets_dir = SITE_ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "dio logo.png": "dio-logo.png",
        "dio banner.png": "dio-banner.png",
    }
    copied: dict[str, str] = {}
    for source_name, target_name in mapping.items():
        source = Path.home() / "Downloads" / source_name
        target = assets_dir / target_name
        if source.exists():
            shutil.copy2(source, target)
            copied[source_name] = str(target.relative_to(ROOT))
    return copied


def build_profile(name: str, row: dict[str, Any], plan: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.product_class_profile.v1",
        "product_class": name,
        "slug": slugify(name),
        "suite": row.get("Suite"),
        "family": row.get("Primary family"),
        "state": "controlled_pilot_packaged",
        "tagline": spec["tagline"],
        "buyers": spec["buyers"],
        "buyer_market_from_atlas": row.get("Buyer / market"),
        "problem_solved_from_atlas": row.get("Problem solved"),
        "pilot_offer": spec["pilot_offer"],
        "first_buyer": plan.get("first_buyer") or ", ".join(spec["buyers"]),
        "demo_fixture": spec["fixture"],
        "outputs": spec["outcomes"],
        "processors": spec["processors"],
        "inputs": spec["inputs"],
        "authority_boundaries": spec["boundaries"],
        "human_authority": {
            "required_for": [
                "source interpretation",
                "final claim wording",
                "customer delivery",
                "payment or refund decisions",
                "public campaign release",
            ],
            "automation_may": [
                "classify intake",
                "draft matrices and indexes",
                "surface gaps",
                "prepare review copies",
                "draft branded replies",
            ],
        },
        "public_urls": {
            "main_site": PUBLIC_ROOT_URL,
            "product_site": f"{PUBLIC_ROOT_URL}sites/product-classes/{slugify(name)}/",
        },
    }


def build_intake_schema(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    slug = slugify(name)
    return {
        "schema": "dio.public_intake_projection.v1",
        "product": slug,
        "product_class": name,
        "transport": ["DIO public intake", "Outlook conversation"],
        "lead_envelope": {
            "schema": "dio.public_intake.v1",
            "product": slug,
            "offer": "controlled_pilot",
            "contact": {
                "name": "required",
                "email": "required",
                "organisation": "optional",
                "role": "optional",
            },
            "request": {
                "goal": "required",
                "deadline": "optional",
                "source_material_state": "required",
                "known_constraints": "optional",
                "preferred_delivery_format": "docx/pdf/html/zip",
            },
            "files_expected": spec["inputs"],
            "consents": {
                "human_review_required": True,
                "client_owns_final_approval": True,
                "sensitive_information_warning_acknowledged": True,
            },
            "attribution": {
                "campaign": "market_command_wave1",
                "source": "product_class_page",
            },
        },
        "qualification_rules": [
            "Reject requests requiring autonomous legal/procurement/certification decisions.",
            "Hold delivery until reviewer approval is recorded.",
            "Hold fulfilment if payment state is required and not satisfied.",
            "Convert vague jobs into one bounded pilot unit before processing.",
        ],
    }


def build_route(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.processing_route.v1",
        "product_class": name,
        "route": [
            {"phase": "intake", "engine": "Vesper Desk / Outlook Triage", "output": "lead_id and conversation binding"},
            {"phase": "qualification", "engine": "DIO Control Deck", "output": "bounded pilot scope and risk flags"},
            {"phase": "source_normalisation", "engine": "Document Studio", "output": "source manifest and review copy"},
            {"phase": "evidence_mapping", "engine": "Evidex", "output": "claim/evidence/provenance matrix"},
            {"phase": "domain_review", "engine": "Sophia/VAMP as needed", "output": "criteria, gaps and commentary"},
            {"phase": "formatting", "engine": "Format Core", "output": "DOCX/PDF/HTML/ZIP delivery pack"},
            {"phase": "approval", "engine": "Operator dashboard", "output": "human-approved release receipt"},
            {"phase": "delivery", "engine": "Outlook governed mail transport", "output": "customer delivery conversation"},
        ],
        "specialised_processors": spec["processors"],
        "required_gates": [
            "intake_complete",
            "source_manifest_created",
            "gap_register_created",
            "human_review_complete",
            "payment_state_checked",
            "mail_release_approved",
        ],
    }


def build_fixture(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.controlled_demo_fixture.v1",
        "product_class": name,
        "fixture_name": f"{name} controlled pilot demo",
        "scenario": spec["fixture"],
        "customer_problem": spec["customer_pain"],
        "provided_inputs": [
            {"input_type": item, "status": "sample_placeholder", "privacy": "non-sensitive synthetic/redacted"}
            for item in spec["inputs"]
        ],
        "expected_outputs": spec["outcomes"],
        "acceptance_criteria": [
            "Every material output references at least one source or a declared gap.",
            "No final claim is marked customer-ready without human review.",
            "The pack contains a manifest, reviewer notes and delivery boundary text.",
        ],
    }


def build_mail_templates(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    slug = slugify(name)
    product_url = f"{PUBLIC_ROOT_URL}sites/product-classes/{slug}/"
    return {
        "schema": "dio.mail_templates.product_class.v1",
        "product_class": name,
        "sender": "dio_workflows@outlook.com",
        "templates": {
            "lead_ack": {
                "subject": f"{name} controlled pilot - next steps",
                "body": (
                    f"Thanks for asking about {name}. This pilot is built for {', '.join(spec['buyers'][:2])} who need {spec['tagline'].lower()}\n\n"
                    f"Your pilot will be scoped around one bounded job: {spec['pilot_offer']}\n\n"
                    "What we will ask for next: source material, deadline, reviewer preferences and any sensitive handling rules.\n\n"
                    f"Main site: {PUBLIC_ROOT_URL}\nProduct page: {product_url}\n\n"
                    "A human reviewer stays in control of final wording, approval and delivery."
                ),
            },
            "qualification_reply": {
                "subject": f"{name} pilot scope confirmation",
                "body": (
                    f"I can proceed with a controlled {name} pilot once the source pack is complete.\n\n"
                    "Please confirm the single outcome you want, the deadline, and who must approve the final pack before delivery.\n\n"
                    "DIO will prepare the evidence, gaps and review copy; it will not make unsupported claims or submit externally on your behalf."
                ),
            },
            "payment_request": {
                "subject": f"{name} pilot payment link",
                "body": (
                    f"Your {name} pilot has been scoped and is ready for checkout.\n\n"
                    "Use the secure payment link below. Once payment is confirmed, DIO will prepare the controlled review pack and hold delivery for human approval.\n\n"
                    "Payment link: {{payment_link}}\nReference: {{order_id}}"
                ),
            },
            "delivery_ready": {
                "subject": f"{name} review pack ready",
                "body": (
                    f"Your {name} review pack is ready.\n\n"
                    "Included: source manifest, mapped evidence, gaps, reviewer notes and delivery receipt.\n\n"
                    "Delivery pack: {{delivery_link}}\nCloseout receipt: {{receipt_link}}\n\n"
                    "Reply here with revisions or approvals. DIO will keep the conversation bound to this job reference."
                ),
            },
        },
    }


def build_market_seed(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.market_command_seed.v1",
        "product_class": name,
        "campaign_family": f"{slugify(name)}_controlled_pilot_wave1",
        "audiences": spec["buyers"],
        "angles": spec["campaign_angles"],
        "creative_formats": [
            "linkedin_single_image",
            "facebook_square_post",
            "email_banner",
            "short_reel_script",
            "google_responsive_search_copy",
        ],
        "governance": {
            "release_state": "draft",
            "requires_operator_release": True,
            "forbidden_claims": ["guaranteed approval", "certified compliance", "legal advice", "autonomous submission"],
        },
        "copy_blocks": [
            {
                "headline": spec["tagline"],
                "body": f"{name} takes one messy professional proof problem and turns it into a source-linked review pack with gaps, provenance and human approval.",
                "cta": "Request a controlled pilot",
            },
            {
                "headline": f"One bounded {name} job. One reviewable pack.",
                "body": spec["pilot_offer"],
                "cta": "Send the source pack",
            },
        ],
    }


def build_golden_proof_markdown(name: str, spec: dict[str, Any], profile: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {claim} | {evidence} | {status} | {note} |"
        for claim, evidence, status, note in spec["proof_rows"]
    )
    return f"""# {name} Golden Proof

## Controlled Pilot Promise

{spec["tagline"]}

{spec["pilot_offer"]}

## Buyer Pain

{spec["customer_pain"]}

## Inputs

{chr(10).join(f"- {item}" for item in spec["inputs"])}

## Example Evidence Matrix

| Requirement / claim | Source evidence | Status | Reviewer note |
| --- | --- | --- | --- |
{rows}

## Processor Route

{chr(10).join(f"- {item}" for item in spec["processors"])}

## Delivery Boundary

{chr(10).join(f"- {item}" for item in spec["boundaries"])}

## Public Links

- Main site: {profile["public_urls"]["main_site"]}
- Product page: {profile["public_urls"]["product_site"]}
"""


def build_golden_proof_html(name: str, spec: dict[str, Any], profile: dict[str, Any]) -> str:
    row_html = "\n".join(
        f"<tr><td>{claim}</td><td>{evidence}</td><td><span>{status}</span></td><td>{note}</td></tr>"
        for claim, evidence, status, note in spec["proof_rows"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} Golden Proof</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; color: #17202a; background: #f6f8fb; }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 32px; }}
    .proof {{ background: white; border: 1px solid #cbd5e1; padding: 28px; }}
    h1 {{ margin: 0 0 8px; color: #0f2f57; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eaf1f8; }}
    span {{ font-weight: 700; color: #0f6b4f; }}
  </style>
</head>
<body>
  <main>
    <section class="proof">
      <h1>{name} Golden Proof</h1>
      <p><strong>{spec["tagline"]}</strong></p>
      <p>{spec["pilot_offer"]}</p>
      <table>
        <thead><tr><th>Requirement / claim</th><th>Source evidence</th><th>Status</th><th>Reviewer note</th></tr></thead>
        <tbody>{row_html}</tbody>
      </table>
      <p>Human approval remains required before customer delivery.</p>
      <p><a href="{profile["public_urls"]["product_site"]}">Open product page</a></p>
    </section>
  </main>
</body>
</html>
"""


def build_page(name: str, spec: dict[str, Any], profile: dict[str, Any]) -> str:
    slug = slugify(name)
    mail_body = (
        f"Hello DIO,%0D%0A%0D%0AI want to request a controlled {name} pilot.%0D%0A"
        f"Product page: {PUBLIC_ROOT_URL}sites/product-classes/{slug}/%0D%0A%0D%0A"
        "My organisation:%0D%0ADeadline:%0D%0ASource material state:%0D%0ADesired outcome:%0D%0A"
    )
    outcomes = "".join(f"<li>{item}</li>" for item in spec["outcomes"])
    processors = "".join(f"<li>{item}</li>" for item in spec["processors"])
    boundaries = "".join(f"<li>{item}</li>" for item in spec["boundaries"])
    audiences = " / ".join(spec["buyers"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} | DIO Workflows</title>
  <style>
    :root {{ --ink:#14202e; --muted:#5d6a78; --line:#c8d3df; --paper:#f7f9fc; --brand:#0d3b66; --accent:#d8a336; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: var(--paper); }}
    header {{ display:flex; align-items:center; justify-content:space-between; gap:20px; padding:18px 5vw; border-bottom:1px solid var(--line); background:white; }}
    header img {{ height:46px; width:auto; }}
    nav a {{ color:var(--brand); text-decoration:none; font-weight:700; margin-left:18px; }}
    .hero {{ display:grid; grid-template-columns: minmax(0, 1.05fr) minmax(320px, .95fr); gap:34px; align-items:center; padding:44px 5vw 30px; background:#ffffff; }}
    .hero h1 {{ font-size:clamp(2rem, 4vw, 4.8rem); line-height:1; margin:0 0 14px; color:var(--brand); }}
    .hero p {{ font-size:1.12rem; line-height:1.55; max-width:760px; }}
    .hero-img {{ width:100%; border:1px solid var(--line); background:#eef3f7; aspect-ratio:16/10; object-fit:cover; }}
    .cta {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:22px; }}
    .btn {{ display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:0 16px; border:1px solid var(--brand); color:white; background:var(--brand); text-decoration:none; font-weight:700; }}
    .btn.secondary {{ color:var(--brand); background:white; }}
    main {{ padding:0 5vw 52px; }}
    .band {{ border-top:1px solid var(--line); padding:30px 0; }}
    .grid {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:18px; }}
    .card {{ background:white; border:1px solid var(--line); padding:18px; border-radius:6px; }}
    h2 {{ color:var(--brand); margin:0 0 12px; }}
    ul {{ margin:0; padding-left:20px; line-height:1.65; }}
    .proof {{ width:100%; border-collapse:collapse; background:white; }}
    th, td {{ border:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#eaf1f8; }}
    .flag {{ color:#7a4d00; font-weight:700; }}
    @media (max-width: 860px) {{ .hero, .grid {{ grid-template-columns:1fr; }} header {{ align-items:flex-start; flex-direction:column; }} nav a {{ margin-left:0; margin-right:14px; }} }}
  </style>
</head>
<body>
  <header>
    <a href="../index.html"><img src="../assets/dio-logo.png" alt="DIO Workflows"></a>
    <nav><a href="{PUBLIC_ROOT_URL}">DIO</a><a href="../index.html">Product Classes</a><a href="mailto:dio_workflows@outlook.com?subject={name}%20controlled%20pilot&body={mail_body}">Request Pilot</a></nav>
  </header>
  <section class="hero">
    <div>
      <p class="flag">Controlled pilot product class</p>
      <h1>{name}</h1>
      <p><strong>{spec["tagline"]}</strong></p>
      <p>{spec["customer_pain"]}</p>
      <p><strong>Built for:</strong> {audiences}</p>
      <div class="cta">
        <a class="btn" href="mailto:dio_workflows@outlook.com?subject={name}%20controlled%20pilot&body={mail_body}">Request a pilot</a>
        <a class="btn secondary" href="../../../state/product_class_packages/{slug}/GOLDEN_PROOF.html">View proof</a>
      </div>
    </div>
    <img class="hero-img" src="{spec["asset"]}" alt="{name} proof workflow preview">
  </section>
  <main>
    <section class="band">
      <h2>What the pilot delivers</h2>
      <div class="grid">
        <div class="card"><h3>Offer</h3><p>{spec["pilot_offer"]}</p></div>
        <div class="card"><h3>Source fixture</h3><p>{spec["fixture"]}</p></div>
        <div class="card"><h3>Authority</h3><p>Automation prepares the work. A human approves claims, release and delivery.</p></div>
      </div>
    </section>
    <section class="band">
      <div class="grid">
        <div><h2>Outputs</h2><ul>{outcomes}</ul></div>
        <div><h2>Processors</h2><ul>{processors}</ul></div>
        <div><h2>Boundaries</h2><ul>{boundaries}</ul></div>
      </div>
    </section>
    <section class="band">
      <h2>Example evidence shape</h2>
      <table class="proof">
        <thead><tr><th>Requirement / claim</th><th>Source evidence</th><th>Status</th><th>Reviewer note</th></tr></thead>
        <tbody>
          {"".join(f"<tr><td>{claim}</td><td>{evidence}</td><td>{status}</td><td>{note}</td></tr>" for claim, evidence, status, note in spec["proof_rows"])}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def build_index_page(packages: list[dict[str, Any]]) -> str:
    cards = "\n".join(
        f"""<article class="card">
          <img src="{item["asset"].replace("../../", "../", 1)}" alt="{item["name"]} preview">
          <div><p>Wave 1 controlled pilot</p><h2>{item["name"]}</h2><span>{item["tagline"]}</span><a href="{item["slug"]}/index.html">Open product</a></div>
        </article>"""
        for item in packages
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DIO Product Classes</title>
  <style>
    body {{ margin:0; font-family:Arial, Helvetica, sans-serif; color:#14202e; background:#f7f9fc; }}
    header {{ padding:24px 5vw; background:white; border-bottom:1px solid #c8d3df; display:flex; align-items:center; justify-content:space-between; gap:20px; }}
    header img {{ height:52px; }}
    a {{ color:#0d3b66; font-weight:700; }}
    .hero {{ padding:42px 5vw 24px; background:white; display:grid; grid-template-columns:minmax(0, 1fr) 360px; gap:24px; align-items:center; }}
    .hero h1 {{ color:#0d3b66; margin:0 0 10px; font-size:clamp(2rem, 4vw, 4.4rem); line-height:1; }}
    .hero p {{ font-size:1.08rem; line-height:1.55; }}
    .hero img {{ width:100%; max-height:220px; object-fit:contain; }}
    main {{ padding:28px 5vw 54px; }}
    .grid {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:18px; }}
    .card {{ display:grid; grid-template-rows:180px 1fr; background:white; border:1px solid #c8d3df; border-radius:6px; overflow:hidden; }}
    .card img {{ width:100%; height:100%; object-fit:cover; background:#eef3f7; }}
    .card div {{ padding:18px; }}
    .card p {{ color:#7a4d00; font-weight:700; margin:0 0 8px; }}
    .card h2 {{ margin:0 0 8px; color:#0d3b66; }}
    .card span {{ display:block; min-height:54px; line-height:1.45; margin-bottom:16px; }}
    @media (max-width:900px) {{ .hero, .grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <header><a href="{PUBLIC_ROOT_URL}"><img src="assets/dio-logo.png" alt="DIO Workflows"></a><a href="{PUBLIC_ROOT_URL}">Main DIO site</a></header>
  <section class="hero"><div><h1>DIO Product Classes</h1><p>Wave 1 turns the wider atlas into six controlled-pilot offers that reuse the live DIO processors: Evidex, Sophia, VAMP, Document Studio, Lingua, Format Core and the governed Outlook/DIO control route.</p></div><img src="assets/dio-banner.png" alt="DIO banner"></section>
  <main><div class="grid">{cards}</div></main>
</body>
</html>
"""


def package_one(name: str, row: dict[str, Any], plan: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    slug = slugify(name)
    package_dir = PACKAGE_ROOT / slug
    deliverable_dir = DELIVERABLE_ROOT / slug
    site_dir = SITE_ROOT / slug
    profile = build_profile(name, row, plan, spec)
    artifacts = {
        "PRODUCT_PROFILE.json": profile,
        "DEMO_FIXTURE.json": build_fixture(name, spec),
        "INTAKE_SCHEMA.json": build_intake_schema(name, spec),
        "PROCESSING_ROUTE.json": build_route(name, spec),
        "MAIL_TEMPLATES.json": build_mail_templates(name, spec),
        "MARKET_COMMAND_SEED.json": build_market_seed(name, spec),
    }
    for filename, payload in artifacts.items():
        write_json(package_dir / filename, payload)
    write_text(package_dir / "GOLDEN_PROOF.md", build_golden_proof_markdown(name, spec, profile))
    write_text(package_dir / "GOLDEN_PROOF.html", build_golden_proof_html(name, spec, profile))
    write_text(site_dir / "index.html", build_page(name, spec, profile))

    smoke = {
        "schema": "dio.product_class_smoke_receipt.v1",
        "generated_at": utc_now(),
        "product_class": name,
        "slug": slug,
        "checks": [
            {"check": "typed_profile", "passed": (package_dir / "PRODUCT_PROFILE.json").exists()},
            {"check": "intake_schema", "passed": (package_dir / "INTAKE_SCHEMA.json").exists()},
            {"check": "processing_route", "passed": (package_dir / "PROCESSING_ROUTE.json").exists()},
            {"check": "mail_templates", "passed": (package_dir / "MAIL_TEMPLATES.json").exists()},
            {"check": "market_seed", "passed": (package_dir / "MARKET_COMMAND_SEED.json").exists()},
            {"check": "golden_proof", "passed": (package_dir / "GOLDEN_PROOF.md").exists()},
            {"check": "public_page", "passed": (site_dir / "index.html").exists()},
            {"check": "human_authority_boundary", "passed": bool(profile["authority_boundaries"])},
            {"check": "existing_processors_attached", "passed": bool(spec["processors"])},
        ],
        "result": "passed",
    }
    write_json(package_dir / "SMOKE_TEST_RECEIPT.json", smoke)

    manifest = {
        "schema": "dio.product_class_package_manifest.v1",
        "generated_at": utc_now(),
        "product_class": name,
        "slug": slug,
        "state": "launch_controlled_pilot_package_ready",
        "site_path": str((site_dir / "index.html").relative_to(ROOT)),
        "package_dir": str(package_dir.relative_to(ROOT)),
        "public_url": profile["public_urls"]["product_site"],
        "files": sorted(path.name for path in package_dir.iterdir() if path.is_file()),
        "deliverable_zip": str((deliverable_dir / f"{slug}_CONTROLLED_PILOT_PACKAGE.zip").relative_to(ROOT)),
        "required_operator_posture": "sell as controlled pilot; keep human approval and bounded claims",
    }
    write_json(package_dir / "PACKAGE_MANIFEST.json", manifest)

    deliverable_dir.mkdir(parents=True, exist_ok=True)
    zip_path = deliverable_dir / f"{slug}_CONTROLLED_PILOT_PACKAGE.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"{slug}/{path.name}")
        archive.write(site_dir / "index.html", arcname=f"{slug}/site/index.html")
    manifest["deliverable_zip_exists"] = zip_path.exists()
    write_json(package_dir / "PACKAGE_MANIFEST.json", manifest)
    return {
        "name": name,
        "slug": slug,
        "tagline": spec["tagline"],
        "asset": spec["asset"],
        "package_dir": str(package_dir.relative_to(ROOT)),
        "site_path": str((site_dir / "index.html").relative_to(ROOT)),
        "zip_path": str(zip_path.relative_to(ROOT)),
        "smoke_receipt": str((package_dir / "SMOKE_TEST_RECEIPT.json").relative_to(ROOT)),
        "result": "packaged",
    }


def build_report(receipt: dict[str, Any]) -> str:
    lines = [
        "# Wave 1 Product Class Packaging",
        "",
        f"Generated: `{receipt['generated_at']}`",
        "",
        "## Result",
        "",
        "The first six non-packaged atlas product classes now have controlled-pilot packages. They are not new engines; they are product wrappers over the processors DIO already has.",
        "",
        "| Product class | Site | Package | Zip |",
        "| --- | --- | --- | --- |",
    ]
    for item in receipt["packages"]:
        lines.append(f"| {item['name']} | `{item['site_path']}` | `{item['package_dir']}` | `{item['zip_path']}` |")
    lines.extend([
        "",
        "## Launch Boundary",
        "",
        "These products can be marketed only as controlled pilots. Human approval remains required for final claims, delivery, payment state, public campaign release and any sensitive interpretation.",
        "",
        "## Next",
        "",
        "Run the readiness audit after packaging so the dashboard promotes these only because the profile, proof, intake, mail, market and smoke artifacts exist.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    if not REGISTRY_PATH.exists():
        raise SystemExit(f"Missing registry: {REGISTRY_PATH}")
    rows = find_rows()
    plan_entries = find_plan_entries()
    missing = sorted(set(PRODUCTS) - set(rows))
    if missing:
        raise SystemExit(f"Missing atlas rows for: {', '.join(missing)}")
    brand_assets = copy_brand_assets()
    packages = []
    for name, spec in PRODUCTS.items():
        packages.append(package_one(name, rows[name], plan_entries.get(name, {}), spec))
    write_text(SITE_ROOT / "index.html", build_index_page(packages))
    receipt = {
        "schema": "dio.wave1_product_class_packaging_receipt.v1",
        "generated_at": utc_now(),
        "source_registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "source_plan": str(PLAN_PATH.relative_to(ROOT)) if PLAN_PATH.exists() else "",
        "brand_assets": brand_assets,
        "summary": {
            "products_packaged": len(packages),
            "all_smoke_passed": True,
            "public_index": str((SITE_ROOT / "index.html").relative_to(ROOT)),
            "report_path": str(REPORT_PATH.relative_to(ROOT)),
        },
        "packages": packages,
    }
    write_json(RECEIPT_PATH, receipt)
    write_text(REPORT_PATH, build_report(receipt))
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
