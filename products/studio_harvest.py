from __future__ import annotations

import hashlib
import html
import json
import csv
import io
import re
from pathlib import Path
from typing import Any

from presence_core.router import route_message
from products.incarnation_studio import IncarnationStudioError, verify_incarnation_proof

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN = "DIO_STUDIO_HARVEST_READY"
SUPPORTED_KINDS = {"site", "correspondence", "finance_readiness", "article"}


class StudioHarvestError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise StudioHarvestError(f"invalid or missing Studio Harvest JSON: {path}") from exc
    if not isinstance(value, dict):
        raise StudioHarvestError(f"expected object: {path}")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_studio_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != "dio.professional_intelligence_studio.v1":
        raise StudioHarvestError("unexpected Studio Harvest manifest schema")
    for key in ("studio_id", "name", "job", "required_organs", "authority", "artifact_contract"):
        if not manifest.get(key):
            raise StudioHarvestError(f"Studio Harvest manifest missing {key}")
    authority = manifest["authority"]
    if authority.get("human_gate") != "NEEDS_YOU":
        raise StudioHarvestError("Studio Harvest requires human gate")
    for key in ("external_publication", "external_send", "media_spend", "payment"):
        if authority.get(key) != "REFUSE":
            raise StudioHarvestError(f"unsafe Studio Harvest authority: {key}")
    organs = manifest["required_organs"]
    if not isinstance(organs, list) or not organs:
        raise StudioHarvestError("Studio Harvest requires at least one organ binding")
    ids = [str(row.get("engine_id") or "") for row in organs]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise StudioHarvestError("Studio Harvest organ bindings must have unique engine_id values")
    kind = manifest["artifact_contract"].get("kind")
    if kind not in SUPPORTED_KINDS:
        raise StudioHarvestError("unsupported Studio Harvest artifact contract")


def _source_bindings(root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = root.resolve()
    for organ in manifest["required_organs"]:
        source_ref = str(organ["source_ref"])
        path = (root / source_ref).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise StudioHarvestError(f"required organ source missing or unsafe: {organ['engine_id']}")
        rows.append({
            "engine_id": str(organ["engine_id"]),
            "source_ref": source_ref,
            "source_sha256": _sha(path),
            "capabilities": list(organ.get("capabilities") or []),
            "binding_state": "SOURCE_BOUND",
            "execution_claim": "BOUND_NOT_LIVE_INVOKED",
        })
    return rows


def _route_job(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    request = str(manifest["job"]["request"])
    decision = route_message(request, "public", root / "config/routes.json").as_dict()
    if decision.get("intent") != "intake_request" or decision.get("product") != manifest["studio_id"]:
        raise StudioHarvestError(
            f"Vesper route mismatch for {manifest['studio_id']}: {decision.get('intent')} / {decision.get('product')}"
        )
    return decision


def _authority_receipt(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.studio_authority_boundary.v1",
        "studio_id": manifest["studio_id"],
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "professional_judgment": "HUMAN_HELD",
        "authority_created": False,
        "external_effects": False,
    }


def _measurement(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.studio_commercial_measurement_contract.v1",
        "studio_id": manifest["studio_id"],
        "events": [
            {"event": "studio_job_routed", "claim_ceiling": "OBSERVED"},
            {"event": "controlled_artifact_generated", "claim_ceiling": "OBSERVED"},
            {"event": "human_review_requested", "claim_ceiling": "OBSERVED"},
        ],
        "unsupported_inferences": [
            "customer value",
            "qualified demand",
            "verified payment",
            "attributed revenue",
            "repeatability",
            "market validation",
        ],
        "payment_enabled": False,
        "revenue_claimed": False,
        "market_validation_claimed": False,
        "source_engine": "commercial_truth",
    }


def _render_site(manifest: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    contract = manifest["artifact_contract"]
    brand = contract["brand"]
    sections = contract["sections"]
    brand_title = str(brand["title"]).strip().removesuffix(".")
    cards = "".join(
        f"<article class='card'><div class='num' aria-hidden='true'>{idx:02d}</div><h3>{html.escape(str(row['title']))}</h3><p>{html.escape(str(row['body']))}</p></article>"
        for idx, row in enumerate(sections, 1)
    )
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(brand_title)}</title><meta name='description' content='{html.escape(str(brand['headline']), quote=True)}'>"
        "<link rel='stylesheet' href='styles.css'></head><body id='top'>"
        "<a class='skip-link' href='#main-content'>Skip to main content</a>"
        f"<header class='wrap'><nav aria-label='Main navigation'><a class='brand' href='#top'>{html.escape(brand_title)}</a>"
        "<div class='nav-links'><a href='#services'>Services</a></div>"
        "<span class='preview-label'>Private draft · owner review</span></nav>"
        "<section class='hero' aria-labelledby='page-title'><div>"
        f"<div class='kicker'>{html.escape(str(brand['eyebrow']))}</div><h1 id='page-title'>{html.escape(str(brand['headline']))}</h1>"
        "<p class='lead'>Independent South African research consultancy.</p><a class='cta' href='#services'>Explore services</a></div>"
        "<div class='signal' aria-hidden='true'></div></section></header>"
        "<main id='main-content'><section id='services' class='paper' aria-labelledby='services-title'><div class='wrap'>"
        "<div class='section-head'><div><div class='kicker'>RESEARCH AND ADVISORY</div><h2 id='services-title'>Services</h2></div>"
        "<p>Frame questions, organise supplied sources, and present research findings to decision-makers.</p></div>"
        f"<div class='grid'>{cards}</div></div></section></main>"
        f"<footer><div class='wrap'><span>{html.escape(brand_title)}</span><span>Private draft for owner review</span></div></footer></body></html>"
    )
    css = """*{box-sizing:border-box}:root{--ink:#12302d;--ink-soft:#34524e;--paper:#f5f2e9;--mint:#bdd7c9;--gold:#c9a467;--line:#d9dfd8;--white:#fff}html{scroll-behavior:smooth;scroll-padding-top:90px}body{margin:0;background:#fff;color:var(--ink);font:16px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}.wrap{width:min(1180px,calc(100% - 48px));margin:auto}.skip-link{position:absolute;left:16px;top:-72px;z-index:10;background:#fff;color:var(--ink);padding:12px 16px;border:2px solid var(--gold);border-radius:5px}.skip-link:focus{top:12px}.brand{font-family:Georgia,'Times New Roman',serif;font-size:1.12rem;font-weight:700;letter-spacing:.015em;color:var(--ink);text-decoration:none}.brand:focus-visible,.nav-links a:focus-visible,.cta:focus-visible,.skip-link:focus{outline:3px solid #a57635;outline-offset:4px}nav{min-height:86px;display:flex;align-items:center;gap:28px;border-bottom:1px solid #ffffff36}.nav-links{display:flex;gap:24px;margin-left:auto}.nav-links a{color:var(--ink-soft);text-decoration:none;font-size:.92rem}.preview-label{font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:#667773;border-left:1px solid var(--line);padding-left:22px}.hero{min-height:610px;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(260px,.75fr);gap:clamp(36px,8vw,112px);align-items:center;padding:84px 0}.kicker{color:#60796d;font-size:.72rem;font-weight:750;letter-spacing:.17em;text-transform:uppercase}h1,h2,h3,p{margin-top:0}h1{max-width:850px;font-family:Georgia,'Times New Roman',serif;font-size:clamp(3rem,6.3vw,6rem);font-weight:500;letter-spacing:-.045em;line-height:.99;margin:20px 0 22px}.lead{max-width:560px;font-size:1.12rem;color:#50655f;line-height:1.65;margin-bottom:26px}.cta{display:inline-flex;align-items:center;gap:18px;background:var(--ink);color:#fff;text-decoration:none;border-radius:2px;padding:13px 19px;font-weight:650;font-size:.9rem}.cta::after{content:'↗';color:var(--mint)}.signal{aspect-ratio:1;position:relative;max-width:450px;width:100%;border-radius:50%;background:radial-gradient(circle at 50% 50%,transparent 0 22%,#9ab8a420 22.4% 23%,transparent 23.4% 43%,#9ab8a44a 43.3% 43.8%,transparent 44.1% 63%,#9ab8a45a 63.3% 63.8%,transparent 64.1%),linear-gradient(135deg,#f7f5ee,#e7eee6);border:1px solid #cbd8cf;box-shadow:0 28px 70px #12302d14}.signal::before,.signal::after{content:'';position:absolute;background:var(--gold);border-radius:50%}.signal::before{width:13px;height:13px;top:22%;left:27%;box-shadow:194px 94px 0 #60796d,72px 233px 0 #c9a467}.signal::after{width:5px;height:5px;top:16%;left:51%;box-shadow:-130px 165px 0 #12302d,90px 64px 0 #9ab8a4}.paper{background:var(--paper);padding:88px 0 100px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:32px;margin-bottom:34px}h2{font-family:Georgia,'Times New Roman',serif;font-size:clamp(2.2rem,4vw,3.5rem);font-weight:500;letter-spacing:-.035em;line-height:1.08;margin:10px 0 0}.section-head p{max-width:370px;color:#61706b;margin:0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.card{min-height:240px;position:relative;background:#fff;border:1px solid var(--line);padding:28px 26px 30px;display:flex;flex-direction:column}.num{font-size:.72rem;letter-spacing:.12em;color:#8a7959;margin-bottom:auto}.card h3{font-family:Georgia,'Times New Roman',serif;font-weight:500;font-size:1.45rem;line-height:1.2;margin:42px 0 9px}.card p{color:#5b6a64;margin:0;max-width:32ch}.approach{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:end;padding:92px 0}.approach p{font-family:Georgia,'Times New Roman',serif;font-size:clamp(1.5rem,2.6vw,2.25rem);line-height:1.3;color:#536b60;margin:0;max-width:520px}footer{border-top:1px solid var(--line);padding:22px 0;color:#60716a;font-size:.82rem}footer .wrap{display:flex;justify-content:space-between;gap:20px}@media(max-width:820px){.wrap{width:min(100% - 36px,680px)}nav{flex-wrap:wrap;gap:12px;padding:18px 0}.nav-links{order:2;margin:0 auto 0 0;width:auto}.preview-label{padding-left:12px}.hero{min-height:auto;grid-template-columns:1fr;gap:42px;padding:70px 0 82px}.hero>div:first-child{order:1}.signal{order:2;max-width:340px}.grid{grid-template-columns:1fr}.card{min-height:190px}.card h3{margin-top:28px}.section-head,.approach{grid-template-columns:1fr;display:grid}.section-head{gap:14px}.approach{gap:18px;padding:68px 0}}@media(max-width:480px){.wrap{width:calc(100% - 32px)}nav{min-height:74px}.brand{font-size:1rem}.nav-links{gap:18px;font-size:.86rem}.preview-label{font-size:.62rem;margin-left:auto;border:0;padding:0}.hero{padding-top:56px}h1{font-size:clamp(2.8rem,13vw,4rem)}.signal{max-width:270px}.paper{padding:66px 0}.card{padding:23px}.section-head p{font-size:.96rem}footer .wrap{display:grid;gap:6px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}"""
    source_lines = "\n".join(
        f"- {row['source_id']}: {row['source_text']}"
        for row in contract.get("customer_content_source_bindings", [])
    )
    review_notes = (
        "# Site Studio customer review notes\n\n"
        f"Draft for: {manifest['job'].get('buyer', 'Website owner')}\n\n"
        "The preview uses the supplied brand headline and three service statements. The supplied subhead identifies this as a controlled draft, so that status is kept here rather than presented as public-facing copy. The draft page itself is branded for the customer and contains no DIO builder labels, inquiry form, or invented contact route.\n\n"
        "## Customer-supplied copy\n\n" + source_lines + "\n\n"
        "## Owner decisions before publication\n\n"
        "- Confirm the brand spelling, logo, visual direction, and whether the current headline is approved.\n"
        "- Confirm service descriptions and provide any factual proof, credentials, case studies, or outcomes you want included. None have been invented.\n"
        "- Supply the preferred contact method and destination before adding a contact link or form; none was supplied in this packet.\n"
        "- Review mobile and keyboard behavior, then approve the finished content and release through the publication owner.\n\n"
        "Publication remains refused by this controlled route. This file is a review handoff, not a public page.\n"
    )
    strategy = {
        "schema": "dio.site_studio_composition_plan.v1",
        "studio_id": manifest["studio_id"],
        "customer_job": manifest["job"]["request"],
        "buyer": manifest["job"]["buyer"],
        "positioning": contract["positioning"],
        "positioning_source_state": contract.get("positioning_source_state", "TEMPLATE_CONTENT_SOURCE_NOT_DECLARED"),
        "customer_content_source_bindings": contract.get("customer_content_source_bindings", []),
        "interpretation_boundary": "Source bindings identify packet records used for customer-facing copy. Template positioning fields are unverified assumptions and are not evidence of customer facts.",
        "required_sections": [str(row["title"]) for row in sections],
        "publication": "REFUSE",
        "human_gate": "NEEDS_YOU",
    }
    return {
        "marketfront/index.html": page,
        "marketfront/styles.css": css,
        "site-review/CUSTOMER_REVIEW_NOTES.md": review_notes,
    }, strategy


def _render_correspondence(manifest: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    contract = manifest["artifact_contract"]
    draft = contract["draft"]
    body = "\n".join(str(x) for x in draft["body_lines"])
    draft_text = f"Subject: {draft['subject']}\n\n{body}\n"
    brief = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>DIO Correspondence Studio</title></head><body><main><h1>Professional Correspondence Studio</h1>"
        f"<p><strong>Customer job:</strong> {html.escape(str(manifest['job']['request']))}</p>"
        f"<h2>Draft subject</h2><p>{html.escape(str(draft['subject']))}</p><h2>Draft body</h2><pre>{html.escape(body)}</pre>"
        "<p><strong>Boundary:</strong> Draft only. Human approval and send authority remain required.</p></main></body></html>"
    )
    semantic = {
        "schema": "dio.lingua_correspondence_semantic_object.v1",
        "studio_id": manifest["studio_id"],
        "source_request": manifest["job"]["request"],
        "purpose": contract["purpose"],
        "tone": contract["tone"],
        "must_preserve": contract["must_preserve"],
        "must_not_invent": contract["must_not_invent"],
        "meaning_state": "CONTROLLED_TEST_FIXTURE",
        "send_authority": "REFUSE",
        "source_engine": "lingua",
    }
    return {"correspondence/DRAFT_EMAIL.txt": draft_text, "correspondence/RESPONSE_BRIEF.html": brief}, semantic


def _finance_gap_map(contract: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = contract["supplied_evidence_fixture"]
    rows = []
    for requirement in contract["published_requirements_fixture"]:
        supporting_rows = [
            item["evidence_id"] for item in evidence
            if requirement["requirement_id"] in set(item.get("supports") or []) and item.get("state") == "supplied"
        ]
        partial_rows = [
            item for item in evidence
            if requirement["requirement_id"] in set(item.get("supports") or [])
            and item.get("state") == "supplied" and item.get("coverage_state") == "PARTIAL_FOR_REVIEW"
        ]
        supporting = supporting_rows
        rows.append({
            "requirement_id": requirement["requirement_id"],
            "label": requirement["label"],
            "mandatory": requirement["mandatory"],
            "supporting_evidence_ids": supporting,
            "coverage_notes": [str(item.get("coverage_note") or "") for item in partial_rows],
            "state": ("PARTIAL_EVIDENCE_FOR_REVIEW" if partial_rows else
                      "SUPPORTED_FOR_READINESS_REVIEW" if supporting else "EVIDENCE_NEEDED"),
        })
    return rows


def _render_finance_readiness(manifest: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    contract = manifest["artifact_contract"]
    venture = contract["venture"]
    gaps = _finance_gap_map(contract)
    missing = [row for row in gaps if row["state"] == "EVIDENCE_NEEDED"]
    partial = [row for row in gaps if row["state"] == "PARTIAL_EVIDENCE_FOR_REVIEW"]
    incomplete = missing + partial
    rows = "".join(
        f"<tr class='{('partial' if row['state'] == 'PARTIAL_EVIDENCE_FOR_REVIEW' else 'missing' if row['state'] == 'EVIDENCE_NEEDED' else '')}'><td>{html.escape(row['requirement_id'])}</td><td>{html.escape(row['label'])}</td><td>{html.escape(row['state'])}</td><td>{html.escape(', '.join(row['supporting_evidence_ids']) or 'None supplied')}{('<br><strong>Coverage note:</strong> ' + html.escape('; '.join(row.get('coverage_notes') or []))) if row.get('coverage_notes') else ''}</td></tr>"
        for row in gaps
    )
    assumptions = "".join(f"<li>{html.escape(str(value))}</li>" for value in contract["assumptions"])
    reconciliation = contract.get("customer_amount_reconciliation")
    reconciliation_object = None
    reconciliation_html = "<p>No source-bound amount reconciliation was possible from the supplied records.</p>"
    if isinstance(reconciliation, dict) and reconciliation.get("schema") == "dio.finance_readiness.customer_amount_reconciliation.v1":
        request_match = re.search(r"\bR\s*([0-9][0-9,]*)\b", str(reconciliation.get("requested_amount_statement") or ""), re.I)
        use_statement = str(reconciliation.get("use_of_funds_statement") or "")
        uses = [(label.strip(), int(amount.replace(",", ""))) for amount, label in re.findall(r"\bR\s*([0-9][0-9,]*)\s+for\s+([A-Za-z][A-Za-z ]*?)(?=\s+and\s+R|\s*\.?$)", use_statement, re.I)]
        # The regex is deliberately checked against the expected pair order,
        # then represented as integers computed from the exact source text.
        if request_match and uses and all(amount > 0 for _, amount in uses):
            requested = int(request_match.group(1).replace(",", ""))
            total = sum(amount for _, amount in uses)
            variance = requested - total
            reconciliation_object = {
                "schema": "dio.finance_readiness.customer_amount_reconciliation.v1",
                "requested_amount": requested,
                "requested_amount_evidence_id": reconciliation["requested_amount_evidence_id"],
                "requested_amount_source_statement": reconciliation["requested_amount_statement"],
                "uses": [{"category": label.strip(), "amount": amount, "evidence_id": reconciliation["use_of_funds_evidence_id"], "source_statement": use_statement} for label, amount in uses],
                "uses_total": total,
                "arithmetic_variance": variance,
                "arithmetic_state": "CUSTOMER_STATED_AMOUNTS_BALANCE" if variance == 0 else "CUSTOMER_STATED_AMOUNTS_DO_NOT_BALANCE",
                "calculation_basis": reconciliation["calculation_basis"],
                "financial_decision": "NOT_MADE",
                "human_review_required": True,
            }
            reconciliation_html = (
                "<table><thead><tr><th>Customer stated item</th><th>Amount</th><th>Evidence record</th></tr></thead><tbody>"
                f"<tr><td>Funding request</td><td>R{requested:,}</td><td>{html.escape(reconciliation_object['requested_amount_evidence_id'])}</td></tr>"
                + "".join(f"<tr><td>{html.escape(row['category'])}</td><td>R{row['amount']:,}</td><td>{html.escape(row['evidence_id'])}</td></tr>" for row in reconciliation_object["uses"])
                + f"<tr><th>Uses total</th><th>R{total:,}</th><th>Variance: R{variance:,}</th></tr></tbody></table>"
                f"<p>{html.escape(reconciliation_object['calculation_basis'])} State: {html.escape(reconciliation_object['arithmetic_state'])}.</p>"
            )
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>DIO Finance Readiness Studio</title><style>body{font:16px/1.55 system-ui,sans-serif;margin:0;color:#172230;background:#f4f7f7}main{max-width:1000px;margin:auto;padding:44px 24px}h1,h2{color:#113f42}.gate{border-left:5px solid #c07a00;background:#fff3dc;padding:14px 18px;font-weight:700}table{width:100%;border-collapse:collapse;background:white}th,td{border:1px solid #ccd8d8;padding:10px;text-align:left;vertical-align:top}th{background:#e5f1ef}.missing{font-weight:800;color:#8a3b00}.partial{background:#fff5df;color:#6f4800;font-weight:650}</style></head><body><main>"
        "<p>DIO // FINANCE READINESS STUDIO // CONTROLLED PROOF</p>"
        f"<h1>{html.escape(venture['name'])}</h1><p><strong>Funding need:</strong> {html.escape(venture['funding_need'])}</p>"
        f"<p>{html.escape(contract['purpose'])}</p><p class='gate'>{html.escape(contract['decision_boundary'])}</p>"
        f"<h2>Customer amount reconciliation</h2>{reconciliation_html}"
        "<h2>Evidence-readiness matrix</h2><p>This is a DIO starter checklist. Confirm current requirements with the selected lender; no lender checklist was supplied or verified for this review.</p><table><thead><tr><th>ID</th><th>DIO starter checklist item (verify with lender)</th><th>Readiness state</th><th>Evidence</th></tr></thead>"
        f"<tbody>{rows}</tbody></table><h2>Unresolved assumptions</h2><ul>{assumptions}</ul>"
        f"<p class='missing'>Mandatory items needing further review: {len(partial)} partial coverage; {len(missing)} without supporting evidence.</p>"
        "<p>No lender approval, affordability, underwriting, credit-bureau or funding outcome is inferred by this controlled dossier.</p>"
        "</main></body></html>"
    )
    summary = (
        f"Finance Readiness Studio controlled review\nVenture: {venture['name']}\nFunding need: {venture['funding_need']}\n"
        f"Requirements reviewed: {len(gaps)}\nEvidence-needed items: {len(missing)}\nPartial-coverage items: {len(partial)}\n"
        f"Decision boundary: {contract['decision_boundary']}\n"
    )
    readiness = {
        "schema": "dio.finance_readiness_controlled_object.v1",
        "studio_id": manifest["studio_id"],
        "venture": venture,
        "requirement_gap_map": gaps,
        "requirement_basis": "DIO_STARTER_CHECKLIST_NOT_LENDER_VERIFIED",
        "evidence_needed_count": len(missing),
        "evidence_partial_count": len(partial),
        "evidence_incomplete_count": len(incomplete),
        "assumptions": contract["assumptions"],
        "forbidden_claims": contract["forbidden_claims"],
        "decision_boundary": contract["decision_boundary"],
        "readiness_state": "EVIDENCE_GAPS_PRESENT" if incomplete else "EVIDENCE_SET_COMPLETE_FOR_HUMAN_REVIEW",
        "lender_decision": "NOT_MADE",
        "financial_advice": "NOT_PROVIDED",
        "human_gate": "NEEDS_YOU",
        "customer_amount_reconciliation": reconciliation_object,
    }
    return {
        "finance/READINESS_REPORT.html": page,
        "finance/READINESS_SUMMARY.txt": summary,
    }, readiness


def _render_article(manifest: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    contract = manifest["artifact_contract"]
    supported_claims = [row for row in contract["claim_fixture"] if row["state"] == "SUPPORTED"]
    refused_claims = [row for row in contract["claim_fixture"] if row["state"] == "REFUSE"]
    sections = "".join(
        f"<section><h2>{html.escape(str(row['heading']))}</h2><p>{html.escape(str(row['body']))}</p></section>"
        for row in contract["sections"]
    )
    refs = "".join(
        f"<li id='{html.escape(str(row['source_id']))}'>{html.escape(str(row['citation']))}</li>"
        for row in contract["source_fixture"]
    )
    claim_rows = "".join(
        f"<tr><td>{html.escape(str(row['claim_id']))}</td><td>{html.escape(str(row['text']))}</td><td>{html.escape(str(row['state']))}</td><td>{html.escape(', '.join(row['evidence_ids']) or 'None')}</td></tr>"
        for row in contract["claim_fixture"]
    )
    article = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>DIO Article Publication Studio</title><style>body{font:18px/1.65 Georgia,serif;margin:0;color:#202126;background:#fbfaf7}article{max-width:850px;margin:auto;padding:48px 24px}h1{font:700 clamp(2.6rem,7vw,5.2rem)/.98 system-ui,sans-serif;letter-spacing:-.05em}h2{font-family:system-ui,sans-serif;margin-top:2em}.standfirst{font-size:1.25rem;color:#555}.gate{border-top:1px solid #aaa;border-bottom:1px solid #aaa;padding:14px 0;font:700 .85rem system-ui,sans-serif}table{font:14px/1.4 system-ui,sans-serif;width:100%;border-collapse:collapse}th,td{border:1px solid #ccc;padding:8px;text-align:left;vertical-align:top}</style></head><body><article>"
        f"<p>{html.escape(contract['publication'])} // CONTROLLED EDITORIAL FIXTURE</p><h1>{html.escape(contract['headline'])}</h1>"
        f"<p class='standfirst'>{html.escape(contract['standfirst'])}</p><p class='gate'>DRAFT ONLY. HUMAN EDITORIAL REVIEW AND PUBLICATION AUTHORITY REQUIRED.</p>"
        f"{sections}<h2>Claim/source review map</h2><table><thead><tr><th>Claim</th><th>Text</th><th>State</th><th>Evidence</th></tr></thead><tbody>{claim_rows}</tbody></table>"
        f"<h2>References</h2><ol>{refs}</ol><p>This controlled draft does not fabricate quotations or sources and does not publish itself.</p>"
        "</article></body></html>"
    )
    lineage = {
        "schema": "dio.article_publication_lineage_object.v1",
        "studio_id": manifest["studio_id"],
        "publication": contract["publication"],
        "headline": contract["headline"],
        "source_fixture": contract["source_fixture"],
        "claim_fixture": contract["claim_fixture"],
        "supported_claim_count": len(supported_claims),
        "refused_claim_count": len(refused_claims),
        "forbidden_claims": contract["forbidden_claims"],
        "source_lineage_state": "CONTROLLED_FIXTURE_BOUND",
        "publication": "REFUSE",
        "human_gate": "NEEDS_YOU",
    }
    map_text = "\n".join(
        f"{row['claim_id']} | {row['state']} | {','.join(row['evidence_ids']) or 'NO_EVIDENCE'} | {row['text']}"
        for row in contract["claim_fixture"]
    ) + "\n"
    # A claim/source map explains provenance; this separate, deliberately blank
    # worksheet gives an editor a row-bound place to record the actual review.
    sources = {row["source_id"]: row for row in contract["source_fixture"]}
    review = io.StringIO(newline="")
    fields = ["claim_id", "claim_text", "claim_state", "source_ids", "source_record_ids",
              "source_text_sha256", "citation", "support_decision", "source_verified",
              "rights_privacy_attribution_review", "editorial_decision", "revision_reference",
              "rationale", "reviewer_name", "reviewer_role", "reviewed_at_iso8601"]
    writer = csv.DictWriter(review, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for claim in contract["claim_fixture"]:
        linked = [sources[source_id] for source_id in claim["evidence_ids"] if source_id in sources]
        writer.writerow({
            "claim_id": claim["claim_id"], "claim_text": claim["text"], "claim_state": claim["state"],
            "source_ids": ";".join(row["source_id"] for row in linked),
            "source_record_ids": ";".join(row["customer_record_id"] for row in linked),
            "source_text_sha256": ";".join(row["source_text_sha256"] for row in linked),
            "citation": " | ".join(row["citation"] for row in linked),
        })
    return {
        "publication/ARTICLE_DRAFT.html": article,
        "publication/CLAIM_SOURCE_MAP.txt": map_text,
        "publication/EDITORIAL_CLAIM_REVIEW_TEMPLATE.csv": review.getvalue(),
    }, lineage


def _entrypoint(kind: str) -> str:
    if kind == "site":
        return "marketfront/index.html"
    if kind == "finance_readiness":
        return "finance/READINESS_REPORT.html"
    if kind == "article":
        return "publication/ARTICLE_DRAFT.html"
    return "correspondence/RESPONSE_BRIEF.html"


def build_studio_case(*, manifest_path: Path, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    manifest = _load(manifest_path.resolve())
    validate_studio_manifest(manifest)
    bindings = _source_bindings(root, manifest)
    route = _route_job(root, manifest)
    authority = _authority_receipt(manifest)
    measurement = _measurement(manifest)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    kind = manifest["artifact_contract"]["kind"]
    if kind == "site":
        text_files, studio_object = _render_site(manifest)
        studio_object_path = "strategy/SITE_COMPOSITION_PLAN.json"
    elif kind == "correspondence":
        text_files, studio_object = _render_correspondence(manifest)
        studio_object_path = "correspondence/LINGUA_SEMANTIC_OBJECT.json"
    elif kind == "finance_readiness":
        text_files, studio_object = _render_finance_readiness(manifest)
        studio_object_path = "finance/FINANCE_READINESS_OBJECT.json"
    elif kind == "article":
        text_files, studio_object = _render_article(manifest)
        studio_object_path = "publication/ARTICLE_LINEAGE_OBJECT.json"
    else:
        raise StudioHarvestError(f"unsupported Studio Harvest kind: {kind}")

    json_files: dict[str, Any] = {
        studio_object_path: studio_object,
        "operations/AUTHORITY_BOUNDARY.json": authority,
        "operations/COMMERCIAL_MEASUREMENT_CONTRACT.json": measurement,
        "operations/VESPER_ROUTE_RECEIPT.json": {
            "schema": "dio.vesper_studio_route_receipt.v1",
            "studio_id": manifest["studio_id"],
            "request": manifest["job"]["request"],
            "decision": route,
            "route_state": "CONTROLLED_ROUTE_PROVED",
            "external_action": False,
        },
        "operations/ORGAN_BINDINGS.json": {
            "schema": "dio.studio_organ_binding_receipt.v1",
            "studio_id": manifest["studio_id"],
            "bindings": bindings,
            "binding_truth": "SOURCE_BOUND_ONLY_EXCEPT_VESPER_ROUTE_EXECUTED",
        },
    }
    if kind == "correspondence":
        json_files["correspondence/COMMITMENT_BOUNDARY.json"] = {
            "schema": "dio.correspondence_commitment_boundary.v1",
            "studio_id": manifest["studio_id"],
            "forbidden_commitments": manifest["artifact_contract"]["must_not_invent"],
            "admission_authority": "REFUSE",
            "settlement_authority": "REFUSE",
            "send_authority": "REFUSE",
            "human_gate": "NEEDS_YOU",
        }
        json_files["operations/OUTLOOK_DRAFT.json"] = {
            "schema": "dio.outlook_draft_projection.v1",
            "studio_id": manifest["studio_id"],
            "to": None,
            "subject": manifest["artifact_contract"]["draft"]["subject"],
            "body": "\n".join(manifest["artifact_contract"]["draft"]["body_lines"]),
            "state": "DRAFT_ONLY",
            "external_send": "REFUSE",
            "source_engine": "outlook_mail_core",
        }
    else:
        json_files["operations/PRESENCE_RELEASE.json"] = {
            "schema": "dio.presence_release_projection.v1",
            "studio_id": manifest["studio_id"],
            "entrypoint": _entrypoint(kind),
            "hosting_package": "STATIC_READY" if kind == "site" else "REVIEW_PACKAGE_READY",
            "publication": "REFUSE",
            "custom_domain": "UNBOUND",
            "human_gate": "NEEDS_YOU",
            "source_engine": "presence_core",
        }
    if kind == "finance_readiness":
        json_files["finance/FINANCIAL_AUTHORITY_BOUNDARY.json"] = {
            "schema": "dio.finance_readiness_authority_boundary.v1",
            "studio_id": manifest["studio_id"],
            "readiness_assessment": "ALLOW_CONTROLLED",
            "lending_decision": "REFUSE",
            "affordability_decision": "REFUSE",
            "credit_decision": "REFUSE",
            "regulated_financial_advice": "REFUSE",
            "human_gate": "NEEDS_YOU",
        }
    if kind == "article":
        json_files["publication/PUBLICATION_BOUNDARY.json"] = {
            "schema": "dio.article_publication_authority_boundary.v1",
            "studio_id": manifest["studio_id"],
            "draft_generation": "ALLOW_CONTROLLED",
            "fabricated_sources": "REFUSE",
            "fabricated_quotations": "REFUSE",
            "automatic_publication": "REFUSE",
            "human_editorial_review": "NEEDS_YOU",
        }

    for rel, value in text_files.items():
        path = output_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    for rel, value in json_files.items():
        _write_json(output_dir / rel, value)

    artifacts: list[dict[str, Any]] = []
    for path in sorted(p for p in output_dir.rglob("*") if p.is_file() and p.name not in {"PROOF_MANIFEST.json", "STUDIO_EXECUTION_RECEIPT.json"}):
        artifacts.append({"path": str(path.relative_to(output_dir)), "sha256": _sha(path), "bytes": path.stat().st_size})

    proof = {
        "schema": "dio.professional_intelligence_studio_proof_manifest.v1",
        "studio_id": manifest["studio_id"],
        "manifest_sha256": _sha(manifest_path.resolve()),
        "artifacts": artifacts,
        "organ_bindings": bindings,
        "vesper_route": route,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    proof["proof_fingerprint"] = _fingerprint(proof)
    _write_json(output_dir / "PROOF_MANIFEST.json", proof)

    receipt = {
        "schema": "dio.professional_intelligence_studio_execution_receipt.v1",
        "studio_id": manifest["studio_id"],
        "studio_name": manifest["name"],
        "job_resolution": "PASS",
        "capability_binding": "PASS",
        "vesper_routing": "PASS",
        "controlled_artifact_generation": "PASS",
        "authority_boundary": "PASS",
        "artifact_count": len(artifacts),
        "proof_fingerprint": proof["proof_fingerprint"],
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "organ_execution_truth": "SOURCE_BOUND_ONLY_EXCEPT_VESPER_ROUTE_EXECUTED",
    }
    receipt["studio_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "STUDIO_EXECUTION_RECEIPT.json", receipt)
    return {
        "manifest": manifest,
        "receipt": receipt,
        "proof_manifest": proof,
        "bindings": bindings,
        "route": route,
        "output_dir": str(output_dir),
    }


def verify_studio_proof(output_dir: Path, proof: dict[str, Any]) -> None:
    try:
        verify_incarnation_proof(output_dir, proof)
    except IncarnationStudioError as exc:
        raise StudioHarvestError(str(exc)) from exc
