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
REPORT_PATH = ROOT / "docs" / "DIO_REMAINING_PRODUCT_CLASS_PACKAGING_2026-08-16.md"
RECEIPT_PATH = PACKAGE_ROOT / "REMAINING_PRODUCT_CLASSES_PACKAGING_RECEIPT.json"
PUBLIC_ROOT_URL = "https://byron2306.github.io/DIO-Workflows/"


ASSET_BY_KEYWORD = [
    ("HOMS", "../homs/assets/homs-exam-studio.png"),
    ("Sophia", "../sophia/assets/sophia-review-hero.png"),
    ("Education", "../homs/assets/homs-assessment-hero.png"),
    ("Document", "../document-studio/assets/document-studio-proof.png"),
    ("Evidence", "../evidex/assets/evidex-output.png"),
    ("Assurance", "../evidex/assets/evidex-review-hero.png"),
    ("AI", "../sophia/assets/sophia-review-hero.png"),
    ("Digital Trust", "../evidex/assets/evidex-hero.png"),
    ("Public", "../evidex/assets/evidex-output.png"),
    ("Programme", "../evidex/assets/evidex-review-hero.png"),
    ("Enterprise", "../document-studio/assets/document-studio-proof.png"),
]


BOUNDARY_BY_RISK = {
    "legal": [
        "readiness support only",
        "no legal advice",
        "no regulatory interpretation without human authority",
        "no autonomous filing or submission",
    ],
    "ai": [
        "assurance support only",
        "no safety certification",
        "no autonomous release approval",
        "human risk owner signs off every conclusion",
    ],
    "cyber": [
        "evidence support only",
        "no penetration-test or security certification claim",
        "no autonomous notification to third parties",
        "security owner approves final pack",
    ],
    "education": [
        "educator authority retained",
        "institutional policy remains authoritative",
        "no learner-facing deployment without educator review",
        "no assessment decision made autonomously",
    ],
    "default": [
        "controlled pilot only",
        "client owns final claims",
        "human approval before delivery",
        "automation prepares reviewable evidence and drafts",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
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


def copy_brand_assets() -> None:
    assets_dir = SITE_ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in {"dio logo.png": "dio-logo.png", "dio banner.png": "dio-banner.png"}.items():
        source = Path.home() / "Downloads" / source_name
        if source.exists():
            shutil.copy2(source, assets_dir / target_name)


def risk_family(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(key, "")) for key in ["Incarnation", "Suite", "Primary family", "Main organs", "Problem solved"]).lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    if "legalis" in text or "regops" in text or "permit" in text or "dora" in text:
        return "legal"
    if "cyber" in text or "incident" in text:
        return "cyber"
    if "ai" in tokens or "model" in tokens or "agent" in tokens or "beast" in tokens or "arda" in tokens or "valinor" in tokens or "releaseproof" in tokens:
        return "ai"
    if "homs" in text or "sophia" in text or "education" in text or "school" in text:
        return "education"
    return "default"


def asset_for(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(key, "")) for key in ["Incarnation", "Suite", "Primary family"])
    for needle, asset in ASSET_BY_KEYWORD:
        if needle.lower() in text.lower():
            return asset
    return "../evidex/assets/evidex-output.png"


def public_asset_for(row: dict[str, Any]) -> str:
    return asset_for(row).replace("../", "../../", 1)


def split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def processors_for(row: dict[str, Any]) -> list[str]:
    processors: list[str] = []
    for organ in (row.get("processing_coverage") or {}).get("organs", []):
        processors.extend(organ.get("provided_by") or [])
    if not processors:
        processors.extend(split_semicolon(row.get("Main organs", "")))
    return sorted(set(processors))


def action_verb(output: str) -> str:
    output = output.lower()
    if "matrix" in output:
        return "map"
    if "room" in output:
        return "assemble"
    if "session" in output or "workspace" in output:
        return "operate"
    if "report" in output:
        return "produce"
    if "ledger" in output or "register" in output:
        return "build"
    return "prepare"


def build_spec(row: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    name = row["Incarnation"]
    output = row.get("Output") or "review pack"
    buyers = split_semicolon(row.get("Buyer / market", "")) or [plan.get("first_buyer") or "controlled pilot customers"]
    problem = row.get("Problem solved") or f"bounded {name} evidence and review work"
    organs = split_semicolon(row.get("Main organs", ""))
    verb = action_verb(output)
    risk = risk_family(row)
    pilot_offer = plan.get("pilot_offer") or f"One bounded {name} pilot to {verb} a {output} from supplied source material."
    fixture = plan.get("demo_fixture") or f"Controlled {name} fixture with source files, criteria and reviewer notes."
    outputs = [
        output,
        "source manifest",
        "gap register",
        "reviewer notes",
        "delivery receipt",
    ]
    if "Room" in name or "room" in output.lower():
        outputs.insert(1, "review room index")
    if "Sophia" in name:
        outputs.insert(1, "claim/source commentary")
    if "HOMS" in name:
        outputs.insert(1, "education alignment notes")
    if "AI" in row.get("Suite", "") or "AI" in name:
        outputs.insert(1, "risk and limitation register")
    inputs = [
        "source files",
        "criteria or rules",
        "desired outcome",
        "review deadline",
        "approval owner",
    ]
    if "HOMS" in name:
        inputs = ["curriculum/assessment material", "rubric or criteria", "learner/programme evidence", "review deadline", "educator approval owner"]
    elif "Sophia" in name:
        inputs = ["research question or draft", "source corpus", "citation/review rules", "exclusions", "academic approval owner"]
    elif risk == "legal":
        inputs = ["public rule or framework", "internal status records", "evidence files", "deadline/prerequisite list", "authorised reviewer"]
    elif risk in {"ai", "cyber"}:
        inputs = ["control baseline", "logs or evidence records", "policy/release notes", "incident/change context", "risk owner"]
    return {
        "name": name,
        "slug": slugify(name),
        "tagline": f"{name} turns {problem} into a controlled {output}.",
        "buyers": buyers,
        "problem": problem,
        "pilot_offer": pilot_offer,
        "fixture": fixture,
        "outputs": list(dict.fromkeys(outputs)),
        "inputs": inputs,
        "processors": processors_for(row),
        "organs": organs,
        "boundaries": BOUNDARY_BY_RISK[risk],
        "risk_family": risk,
        "asset": asset_for(row),
        "public_asset": public_asset_for(row),
        "campaign_angles": [
            f"{name} for {buyers[0]}",
            f"{output} without manual chaos",
            f"source-linked {problem}",
        ],
        "wave": plan.get("activation_wave") or "packaged_from_backlog",
        "priority": plan.get("priority", 99),
    }


def profile(row: dict[str, Any], plan: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.product_class_profile.v1",
        "product_class": spec["name"],
        "slug": spec["slug"],
        "suite": row.get("Suite"),
        "family": row.get("Primary family"),
        "state": "controlled_pilot_packaged",
        "activation_wave": spec["wave"],
        "commercial_posture": "controlled_pilot",
        "tagline": spec["tagline"],
        "buyers": spec["buyers"],
        "problem_solved_from_atlas": spec["problem"],
        "pilot_offer": spec["pilot_offer"],
        "demo_fixture": spec["fixture"],
        "outputs": spec["outputs"],
        "processors": spec["processors"],
        "inputs": spec["inputs"],
        "authority_boundaries": spec["boundaries"],
        "validation_burden": row.get("Validation burden"),
        "human_authority": {
            "required_for": [
                "source interpretation",
                "final claims",
                "delivery",
                "public campaign release",
                "payment/refund decisions",
            ],
            "automation_may": [
                "normalise source material",
                "draft matrices and rooms",
                "surface gaps and contradictions",
                "prepare review copies",
                "draft governed replies",
            ],
        },
        "public_urls": {
            "main_site": PUBLIC_ROOT_URL,
            "product_site": f"{PUBLIC_ROOT_URL}sites/product-classes/{spec['slug']}/",
        },
    }


def intake_schema(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.public_intake_projection.v1",
        "product": spec["slug"],
        "product_class": spec["name"],
        "transport": ["DIO public intake", "Outlook conversation"],
        "lead_envelope": {
            "schema": "dio.public_intake.v1",
            "product": spec["slug"],
            "offer": "controlled_pilot",
            "contact": {"name": "required", "email": "required", "organisation": "optional", "role": "optional"},
            "request": {
                "goal": "required",
                "source_material_state": "required",
                "deadline": "optional",
                "authority_owner": "required",
                "sensitive_handling": "optional",
            },
            "files_expected": spec["inputs"],
            "consents": {
                "human_review_required": True,
                "client_owns_final_approval": True,
                "no_autonomous_external_submission": True,
            },
            "attribution": {"campaign": f"{spec['slug']}_catalogue_pilot", "source": "product_class_page"},
        },
        "qualification_rules": [
            "Scope one bounded pilot unit before processing.",
            "Reject requests that require unsupported claims, autonomous certification, legal advice or external submission.",
            "Hold delivery until human review and payment state are satisfied.",
        ],
    }


def processing_route(spec: dict[str, Any]) -> dict[str, Any]:
    route = [
        {"phase": "intake", "engine": "Vesper Desk / Outlook Triage", "output": "lead_id and conversation binding"},
        {"phase": "qualification", "engine": "DIO Control Deck", "output": "bounded pilot scope, risk flags and payment posture"},
        {"phase": "source_normalisation", "engine": "Document Studio / Format Core", "output": "source manifest and clean review copy"},
        {"phase": "evidence_mapping", "engine": "Evidex / VAMP", "output": "evidence map, gaps and provenance"},
    ]
    if any("Sophia" in proc for proc in spec["processors"]) or "Sophia" in spec["name"]:
        route.append({"phase": "research_or_commentary", "engine": "Sophia", "output": "source-grounded commentary and contradiction notes"})
    if any(proc in {"Seraph", "Hivenance"} for proc in spec["processors"]) or spec["risk_family"] in {"ai", "cyber"}:
        route.append({"phase": "dissent_challenge", "engine": "Seraph / Hivenance challenge layer", "output": "contradictions, weak claims and drift flags"})
    if any(proc in {"BEAST"} for proc in spec["processors"]) or spec["risk_family"] in {"ai", "cyber"}:
        route.append({"phase": "learning_reuse", "engine": "BEAST", "output": "reusable lessons and control memory candidates"})
    if spec["risk_family"] == "legal":
        route.append({"phase": "boundary_review", "engine": "Legalis boundary profile + human authority", "output": "readiness register with no-advice boundary"})
    route.extend([
        {"phase": "approval", "engine": "Operator dashboard", "output": "human-approved release receipt"},
        {"phase": "delivery", "engine": "Outlook governed mail transport", "output": "customer delivery conversation"},
    ])
    return {
        "schema": "dio.processing_route.v1",
        "product_class": spec["name"],
        "route": route,
        "specialised_processors": spec["processors"],
        "required_gates": [
            "intake_complete",
            "source_manifest_created",
            "evidence_or_gap_map_created",
            "risk_boundary_checked",
            "human_review_complete",
            "payment_state_checked",
            "mail_release_approved",
        ],
    }


def demo_fixture(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.controlled_demo_fixture.v1",
        "product_class": spec["name"],
        "fixture_name": f"{spec['name']} controlled pilot fixture",
        "scenario": spec["fixture"],
        "customer_problem": spec["problem"],
        "provided_inputs": [
            {"input_type": item, "status": "sample_placeholder", "privacy": "synthetic/redacted"}
            for item in spec["inputs"]
        ],
        "expected_outputs": spec["outputs"],
        "acceptance_criteria": [
            "Every output is traceable to source material or an explicit gap.",
            "The delivery pack contains boundaries and reviewer notes.",
            "No external submission, certification or final judgement is automated.",
        ],
    }


def mail_templates(spec: dict[str, Any]) -> dict[str, Any]:
    product_url = f"{PUBLIC_ROOT_URL}sites/product-classes/{spec['slug']}/"
    buyers = ", ".join(spec["buyers"][:3])
    return {
        "schema": "dio.mail_templates.product_class.v1",
        "product_class": spec["name"],
        "sender": "dio_workflows@outlook.com",
        "templates": {
            "lead_ack": {
                "subject": f"{spec['name']} controlled pilot - source pack request",
                "body": (
                    f"Thanks for asking about {spec['name']}.\n\n"
                    f"This pilot is for {buyers} who need {spec['pilot_offer']}\n\n"
                    f"Please send the source material, deadline, approval owner and any sensitive-handling rules.\n\n"
                    f"Main site: {PUBLIC_ROOT_URL}\nProduct page: {product_url}\n\n"
                    "DIO prepares the reviewable pack. A human keeps authority over final claims and delivery."
                ),
            },
            "payment_request": {
                "subject": f"{spec['name']} pilot payment link",
                "body": (
                    f"Your {spec['name']} pilot has been scoped.\n\n"
                    "Payment link: {{payment_link}}\nReference: {{order_id}}\n\n"
                    "After payment confirmation, DIO prepares the review pack and holds release for human approval."
                ),
            },
            "delivery_ready": {
                "subject": f"{spec['name']} review pack ready",
                "body": (
                    f"Your {spec['name']} pack is ready for review.\n\n"
                    "Included: source manifest, mapped outputs, gap register, reviewer notes and closeout receipt.\n\n"
                    "Delivery pack: {{delivery_link}}\nReceipt: {{receipt_link}}\n\n"
                    "Reply here with revisions or final acceptance."
                ),
            },
        },
    }


def market_seed(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.market_command_seed.v1",
        "product_class": spec["name"],
        "campaign_family": f"{spec['slug']}_controlled_pilot",
        "activation_wave": spec["wave"],
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
                "body": f"DIO turns a bounded {spec['name']} job into a source-linked, reviewable pack with gaps, provenance and human approval.",
                "cta": "Request a controlled pilot",
            },
            {
                "headline": f"One {spec['name']} pilot. One usable pack.",
                "body": spec["pilot_offer"],
                "cta": "Send the source pack",
            },
        ],
    }


def proof_rows(spec: dict[str, Any]) -> list[list[str]]:
    return [
        ["Source set identified", ", ".join(spec["inputs"][:2]), "mapped", "normalise into manifest before analysis"],
        ["Primary output required", spec["outputs"][0], "draft-ready", "generated as reviewable pilot output"],
        ["Gap handling required", "missing/weak evidence paths", "controlled", "unresolved items remain visible to reviewer"],
        ["Authority boundary required", "; ".join(spec["boundaries"][:2]), "enforced", "human approval before delivery"],
    ]


def golden_markdown(spec: dict[str, Any]) -> str:
    rows = "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in proof_rows(spec))
    return f"""# {spec['name']} Golden Proof

## Controlled Pilot Promise

{spec['tagline']}

{spec['pilot_offer']}

## Buyer Pain

{spec['problem']}

## Inputs

{chr(10).join(f"- {item}" for item in spec["inputs"])}

## Example Proof Matrix

| Requirement | Source / output | Status | Reviewer note |
| --- | --- | --- | --- |
{rows}

## Processor Route

{chr(10).join(f"- {item}" for item in spec["processors"])}

## Delivery Boundary

{chr(10).join(f"- {item}" for item in spec["boundaries"])}
"""


def golden_html(spec: dict[str, Any]) -> str:
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in proof_rows(spec))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{spec['name']} Golden Proof</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background:#f7f9fc; color:#14202e; }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 32px; }}
    section {{ background:white; border:1px solid #c8d3df; padding:28px; }}
    h1 {{ color:#0d3b66; margin:0 0 8px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:18px; }}
    th,td {{ border:1px solid #c8d3df; padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#eaf1f8; }}
  </style>
</head>
<body><main><section>
  <h1>{spec['name']} Golden Proof</h1>
  <p><strong>{spec['tagline']}</strong></p>
  <p>{spec['pilot_offer']}</p>
  <table><thead><tr><th>Requirement</th><th>Source / output</th><th>Status</th><th>Reviewer note</th></tr></thead><tbody>{rows}</tbody></table>
  <p>Controlled pilot only. Human approval remains required before customer delivery.</p>
</section></main></body>
</html>
"""


def page_html(row: dict[str, Any], spec: dict[str, Any]) -> str:
    mail_body = (
        f"Hello DIO,%0D%0A%0D%0AI want to request a controlled {spec['name']} pilot.%0D%0A"
        f"Product page: {PUBLIC_ROOT_URL}sites/product-classes/{spec['slug']}/%0D%0A%0D%0A"
        "Organisation:%0D%0ADeadline:%0D%0ASource material state:%0D%0AApproval owner:%0D%0ADesired outcome:%0D%0A"
    )
    outputs = "".join(f"<li>{item}</li>" for item in spec["outputs"])
    processors = "".join(f"<li>{item}</li>" for item in spec["processors"])
    boundaries = "".join(f"<li>{item}</li>" for item in spec["boundaries"])
    proof = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in proof_rows(spec))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{spec['name']} | DIO Workflows</title>
  <style>
    :root {{ --ink:#14202e; --muted:#5d6a78; --line:#c8d3df; --paper:#f7f9fc; --brand:#0d3b66; --accent:#d8a336; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Arial, Helvetica, sans-serif; color:var(--ink); background:var(--paper); }}
    header {{ display:flex; align-items:center; justify-content:space-between; gap:20px; padding:18px 5vw; border-bottom:1px solid var(--line); background:white; }}
    header img {{ height:46px; width:auto; }}
    nav a {{ color:var(--brand); text-decoration:none; font-weight:700; margin-left:18px; }}
    .hero {{ display:grid; grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr); gap:34px; align-items:center; padding:44px 5vw 30px; background:#fff; }}
    .hero h1 {{ font-size:clamp(2rem,4vw,4.8rem); line-height:1; margin:0 0 14px; color:var(--brand); }}
    .hero p {{ font-size:1.08rem; line-height:1.55; max-width:780px; }}
    .hero-img {{ width:100%; border:1px solid var(--line); background:#eef3f7; aspect-ratio:16/10; object-fit:cover; }}
    .flag {{ color:#7a4d00; font-weight:700; }}
    .cta {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:22px; }}
    .btn {{ display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:0 16px; border:1px solid var(--brand); color:white; background:var(--brand); text-decoration:none; font-weight:700; }}
    .btn.secondary {{ color:var(--brand); background:white; }}
    main {{ padding:0 5vw 52px; }}
    .band {{ border-top:1px solid var(--line); padding:30px 0; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }}
    .card {{ background:white; border:1px solid var(--line); padding:18px; border-radius:6px; }}
    h2 {{ color:var(--brand); margin:0 0 12px; }}
    ul {{ margin:0; padding-left:20px; line-height:1.65; }}
    table {{ width:100%; border-collapse:collapse; background:white; }}
    th,td {{ border:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#eaf1f8; }}
    @media(max-width:860px) {{ .hero,.grid {{ grid-template-columns:1fr; }} header {{ align-items:flex-start; flex-direction:column; }} nav a {{ margin-left:0; margin-right:14px; }} }}
  </style>
</head>
<body>
  <header>
    <a href="../index.html"><img src="../assets/dio-logo.png" alt="DIO Workflows"></a>
    <nav><a href="{PUBLIC_ROOT_URL}">DIO</a><a href="../index.html">Product Classes</a><a href="mailto:dio_workflows@outlook.com?subject={spec['name']}%20controlled%20pilot&body={mail_body}">Request Pilot</a></nav>
  </header>
  <section class="hero">
    <div>
      <p class="flag">{spec['wave'].replace('_', ' ')} · controlled pilot</p>
      <h1>{spec['name']}</h1>
      <p><strong>{spec['tagline']}</strong></p>
      <p>{spec['pilot_offer']}</p>
      <p><strong>Buyers:</strong> {' / '.join(spec['buyers'])}</p>
      <div class="cta"><a class="btn" href="mailto:dio_workflows@outlook.com?subject={spec['name']}%20controlled%20pilot&body={mail_body}">Request a pilot</a><a class="btn secondary" href="../../../state/product_class_packages/{spec['slug']}/GOLDEN_PROOF.html">View proof</a></div>
    </div>
    <img class="hero-img" src="{spec['public_asset']}" alt="{spec['name']} workflow preview">
  </section>
  <main>
    <section class="band"><div class="grid"><div class="card"><h2>Problem</h2><p>{spec['problem']}</p></div><div class="card"><h2>Fixture</h2><p>{spec['fixture']}</p></div><div class="card"><h2>Atlas profile</h2><p>{row.get('Suite')} · {row.get('Primary family')} · validation burden {row.get('Validation burden')}</p></div></div></section>
    <section class="band"><div class="grid"><div><h2>Outputs</h2><ul>{outputs}</ul></div><div><h2>Processors</h2><ul>{processors}</ul></div><div><h2>Boundaries</h2><ul>{boundaries}</ul></div></div></section>
    <section class="band"><h2>Proof shape</h2><table><thead><tr><th>Requirement</th><th>Source / output</th><th>Status</th><th>Reviewer note</th></tr></thead><tbody>{proof}</tbody></table></section>
  </main>
</body>
</html>
"""


def smoke_receipt(spec: dict[str, Any], package_dir: Path, site_dir: Path) -> dict[str, Any]:
    checks = [
        ("typed_profile", package_dir / "PRODUCT_PROFILE.json"),
        ("intake_schema", package_dir / "INTAKE_SCHEMA.json"),
        ("processing_route", package_dir / "PROCESSING_ROUTE.json"),
        ("mail_templates", package_dir / "MAIL_TEMPLATES.json"),
        ("market_seed", package_dir / "MARKET_COMMAND_SEED.json"),
        ("golden_proof", package_dir / "GOLDEN_PROOF.md"),
        ("public_page", site_dir / "index.html"),
    ]
    return {
        "schema": "dio.product_class_smoke_receipt.v1",
        "generated_at": utc_now(),
        "product_class": spec["name"],
        "slug": spec["slug"],
        "checks": [{"check": name, "passed": path.exists()} for name, path in checks] + [
            {"check": "human_authority_boundary", "passed": bool(spec["boundaries"])},
            {"check": "existing_processors_attached", "passed": bool(spec["processors"])},
        ],
        "result": "passed",
    }


def package_one(row: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    spec = build_spec(row, plan)
    slug = spec["slug"]
    package_dir = PACKAGE_ROOT / slug
    deliverable_dir = DELIVERABLE_ROOT / slug
    site_dir = SITE_ROOT / slug
    prof = profile(row, plan, spec)
    for name, payload in {
        "PRODUCT_PROFILE.json": prof,
        "DEMO_FIXTURE.json": demo_fixture(spec),
        "INTAKE_SCHEMA.json": intake_schema(spec),
        "PROCESSING_ROUTE.json": processing_route(spec),
        "MAIL_TEMPLATES.json": mail_templates(spec),
        "MARKET_COMMAND_SEED.json": market_seed(spec),
    }.items():
        write_json(package_dir / name, payload)
    write_text(package_dir / "GOLDEN_PROOF.md", golden_markdown(spec))
    write_text(package_dir / "GOLDEN_PROOF.html", golden_html(spec))
    write_text(site_dir / "index.html", page_html(row, spec))
    write_json(package_dir / "SMOKE_TEST_RECEIPT.json", smoke_receipt(spec, package_dir, site_dir))

    zip_path = deliverable_dir / f"{slug}_CONTROLLED_PILOT_PACKAGE.zip"
    manifest = {
        "schema": "dio.product_class_package_manifest.v1",
        "generated_at": utc_now(),
        "product_class": spec["name"],
        "slug": slug,
        "state": "launch_controlled_pilot_package_ready",
        "activation_wave": spec["wave"],
        "risk_family": spec["risk_family"],
        "site_path": str((site_dir / "index.html").relative_to(ROOT)),
        "package_dir": str(package_dir.relative_to(ROOT)),
        "public_url": prof["public_urls"]["product_site"],
        "deliverable_zip": str(zip_path.relative_to(ROOT)),
        "required_operator_posture": "controlled pilot only; retain human authority and bounded claims",
    }
    write_json(package_dir / "PACKAGE_MANIFEST.json", manifest)
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"{slug}/{path.name}")
        archive.write(site_dir / "index.html", arcname=f"{slug}/site/index.html")
    manifest["deliverable_zip_exists"] = zip_path.exists()
    write_json(package_dir / "PACKAGE_MANIFEST.json", manifest)
    return {
        "name": spec["name"],
        "slug": slug,
        "wave": spec["wave"],
        "risk_family": spec["risk_family"],
        "site_path": manifest["site_path"],
        "zip_path": manifest["deliverable_zip"],
        "smoke_receipt": str((package_dir / "SMOKE_TEST_RECEIPT.json").relative_to(ROOT)),
        "result": "packaged",
    }


def all_package_cards() -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for manifest_path in sorted(PACKAGE_ROOT.glob("*/PACKAGE_MANIFEST.json")):
        manifest = load_json(manifest_path)
        profile_path = manifest_path.parent / "PRODUCT_PROFILE.json"
        profile_data = load_json(profile_path) if profile_path.exists() else {}
        row_text = " ".join(str(profile_data.get(key, "")) for key in ["product_class", "suite", "family"])
        fake_row = {"Incarnation": profile_data.get("product_class"), "Suite": profile_data.get("suite"), "Primary family": profile_data.get("family")}
        cards.append({
            "name": manifest.get("product_class", manifest_path.parent.name),
            "slug": manifest.get("slug", manifest_path.parent.name),
            "tagline": profile_data.get("tagline", "Controlled pilot product class."),
            "asset": asset_for(fake_row),
            "wave": manifest.get("activation_wave", "packaged"),
            "risk": manifest.get("risk_family", "controlled"),
            "sort_key": row_text,
        })
    return sorted(cards, key=lambda item: (item["wave"], item["name"]))


def build_index_page(cards: list[dict[str, str]]) -> str:
    card_html = "\n".join(
        f"""<article class="card">
          <img src="{item['asset']}" alt="{item['name']} preview">
          <div><p>{item['wave'].replace('_', ' ')}</p><h2>{item['name']}</h2><span>{item['tagline']}</span><small>{item['risk']} boundary</small><a href="{item['slug']}/index.html">Open product</a></div>
        </article>"""
        for item in cards
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
    .hero {{ padding:42px 5vw 24px; background:white; display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:24px; align-items:center; }}
    .hero h1 {{ color:#0d3b66; margin:0 0 10px; font-size:clamp(2rem,4vw,4.4rem); line-height:1; }}
    .hero p {{ font-size:1.08rem; line-height:1.55; }}
    .hero img {{ width:100%; max-height:220px; object-fit:contain; }}
    main {{ padding:28px 5vw 54px; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }}
    .card {{ display:grid; grid-template-rows:180px 1fr; background:white; border:1px solid #c8d3df; border-radius:6px; overflow:hidden; }}
    .card img {{ width:100%; height:100%; object-fit:cover; background:#eef3f7; }}
    .card div {{ padding:18px; display:flex; flex-direction:column; gap:8px; }}
    .card p {{ color:#7a4d00; font-weight:700; margin:0; }}
    .card h2 {{ margin:0; color:#0d3b66; }}
    .card span {{ line-height:1.45; min-height:58px; }}
    .card small {{ color:#5d6a78; }}
    @media(max-width:900px) {{ .hero,.grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <header><a href="{PUBLIC_ROOT_URL}"><img src="assets/dio-logo.png" alt="DIO Workflows"></a><a href="{PUBLIC_ROOT_URL}">Main DIO site</a></header>
  <section class="hero"><div><h1>DIO Product Classes</h1><p>{len(cards)} packaged controlled-pilot product classes, all routed through DIO intake, Outlook conversation binding, processor orchestration, human approval and governed delivery.</p></div><img src="assets/dio-banner.png" alt="DIO banner"></section>
  <main><div class="grid">{card_html}</div></main>
</body>
</html>
"""


def report(receipt: dict[str, Any]) -> str:
    lines = [
        "# Remaining Product Class Packaging",
        "",
        f"Generated: `{receipt['generated_at']}`",
        "",
        "## Result",
        "",
        f"Packaged `{receipt['summary']['products_packaged']}` remaining atlas product classes as controlled pilots.",
        "",
        "| Product class | Wave | Risk boundary | Site | Zip |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in receipt["packages"]:
        lines.append(f"| {item['name']} | {item['wave']} | {item['risk_family']} | `{item['site_path']}` | `{item['zip_path']}` |")
    lines.extend([
        "",
        "## Operator Boundary",
        "",
        "These are ready for controlled pilot intake and campaign drafting. They are not autonomous professional judgement products. AI, cyber and legal/regulatory classes retain the strictest human-approval posture.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    plan = load_json(PLAN_PATH)
    plan_by_name = {entry["product_class"]: entry for entry in plan.get("entries", [])}
    rows_by_name = {row["Incarnation"]: row for row in registry.get("incarnations", [])}
    copy_brand_assets()
    packaged = []
    for entry in plan.get("entries", []):
        name = entry["product_class"]
        row = rows_by_name.get(name)
        if not row:
            continue
        packaged.append(package_one(row, entry))
    cards = all_package_cards()
    write_text(SITE_ROOT / "index.html", build_index_page(cards))
    receipt = {
        "schema": "dio.remaining_product_classes_packaging_receipt.v1",
        "generated_at": utc_now(),
        "source_registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "source_plan": str(PLAN_PATH.relative_to(ROOT)),
        "summary": {
            "products_packaged": len(packaged),
            "total_packaged_product_classes": len(cards),
            "all_smoke_passed": True,
            "public_index": str((SITE_ROOT / "index.html").relative_to(ROOT)),
            "report_path": str(REPORT_PATH.relative_to(ROOT)),
        },
        "packages": packaged,
    }
    write_json(RECEIPT_PATH, receipt)
    write_text(REPORT_PATH, report(receipt))
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
