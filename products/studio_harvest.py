from __future__ import annotations

import hashlib
import html
import json
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
    cards = "".join(
        f"<article class='card'><div class='num'>{idx:02d}</div><h3>{html.escape(str(row['title']))}</h3><p>{html.escape(str(row['body']))}</p></article>"
        for idx, row in enumerate(sections, 1)
    )
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(str(brand['title']))}</title><link rel='stylesheet' href='styles.css'></head><body>"
        "<header class='wrap'><nav><strong>DIO // SITE STUDIO</strong><span class='pill'>CONTROLLED COMPOSITION PROOF</span></nav>"
        "<section class='hero'><div>"
        f"<div class='kicker'>{html.escape(str(brand['eyebrow']))}</div><h1>{html.escape(str(brand['headline']))}</h1>"
        f"<p class='lead'>{html.escape(str(brand['subhead']))}</p><a class='cta' href='#intake'>Prepare a website brief</a></div>"
        "<div class='signal' aria-hidden='true'></div></section></header><main><section class='paper'><div class='wrap'>"
        "<div class='kicker'>COMPOSED FROM EXISTING DIO CAPABILITIES</div>"
        f"<div class='grid'>{cards}</div></div></section><section id='intake'><div class='wrap'><div class='kicker'>CONTROLLED INTAKE</div>"
        "<h2>Prepare the brief locally.</h2><p class='notice'>This proof does not publish a website, upload files, take payment, or create external authority.</p>"
        "<form id='site-intake'><label>Name<input id='name' required></label><label>Organisation<input id='org' required></label>"
        "<label>Website goal<textarea id='goal' rows='4' required></textarea></label><button class='cta' type='submit'>Prepare local brief</button>"
        "<p id='status' aria-live='polite'></p></form></div></section></main>"
        "<footer><div class='wrap'>DIO Site Studio · Controlled composition proof · Human release required.</div></footer>"
        "<script src='app.js'></script></body></html>"
    )
    css = """*{box-sizing:border-box}:root{--ink:#07111f;--paper:#f5f1e8;--cyan:#29d3c2;--amber:#ffb547}body{margin:0;background:var(--ink);color:#eef6f5;font-family:Arial,sans-serif}.wrap{width:min(1120px,calc(100% - 36px));margin:auto}nav{display:flex;justify-content:space-between;padding:24px 0}.pill{border:1px solid #ffffff35;border-radius:999px;padding:8px 12px}.hero{min-height:72vh;display:grid;grid-template-columns:1.2fr .8fr;gap:48px;align-items:center}.kicker{color:var(--cyan);font-weight:800;letter-spacing:.12em}h1{font-size:clamp(2.8rem,7vw,6rem);line-height:.94;margin:18px 0}.lead{font-size:1.15rem;line-height:1.65;color:#bfd1d1}.signal{aspect-ratio:1;border-radius:28px;background:radial-gradient(circle at 65% 35%,#29d3c255,transparent 22%),linear-gradient(145deg,#10243b,#07111f);border:1px solid #ffffff24}.cta{display:inline-block;background:var(--amber);color:#15100a;border:0;border-radius:8px;padding:14px 18px;font-weight:800;text-decoration:none;cursor:pointer}section{padding:72px 0}.paper{background:var(--paper);color:#142231}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.card{background:white;border-radius:14px;padding:24px;border:1px solid #17304b22}.num{color:#098b80;font-weight:900}form{display:grid;gap:14px;max-width:720px}label{font-weight:800}input,textarea{width:100%;padding:13px;background:#ffffff0d;color:white;border:1px solid #ffffff32;border-radius:8px}.notice{padding:16px;border-left:4px solid var(--amber);background:#ffb54715;color:#ffdca3}footer{padding:36px 0;color:#8fa9ad;border-top:1px solid #ffffff18}@media(max-width:800px){.hero{grid-template-columns:1fr}.grid{grid-template-columns:1fr}.signal{max-width:420px}}"""
    studio_id = json.dumps(manifest["studio_id"])
    download_name = json.dumps(str(contract.get("intake_filename") or "SITE_STUDIO_INTAKE_DRAFT.json"))
    js = f"""const form=document.querySelector('#site-intake');const status=document.querySelector('#status');form.addEventListener('submit',e=>{{e.preventDefault();const draft={{schema:'dio.site_studio_intake.v1',studio_id:{studio_id},name:document.querySelector('#name').value,organisation:document.querySelector('#org').value,goal:document.querySelector('#goal').value,state:'LOCAL_DRAFT_ONLY',external_send:'REFUSE',publication:'REFUSE',payment:'REFUSE'}};const blob=new Blob([JSON.stringify(draft,null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download={download_name};a.click();URL.revokeObjectURL(a.href);status.textContent='Local website brief prepared. Nothing was uploaded, published, sent, or paid.';}});"""
    strategy = {
        "schema": "dio.site_studio_composition_plan.v1",
        "studio_id": manifest["studio_id"],
        "customer_job": manifest["job"]["request"],
        "buyer": manifest["job"]["buyer"],
        "positioning": contract["positioning"],
        "required_sections": [str(row["title"]) for row in sections],
        "publication": "REFUSE",
        "human_gate": "NEEDS_YOU",
    }
    return {"marketfront/index.html": page, "marketfront/styles.css": css, "marketfront/app.js": js}, strategy


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
        supporting = [
            item["evidence_id"] for item in evidence
            if requirement["requirement_id"] in set(item.get("supports") or []) and item.get("state") == "supplied"
        ]
        rows.append({
            "requirement_id": requirement["requirement_id"],
            "label": requirement["label"],
            "mandatory": requirement["mandatory"],
            "supporting_evidence_ids": supporting,
            "state": "SUPPORTED_FOR_READINESS_REVIEW" if supporting else "EVIDENCE_NEEDED",
        })
    return rows


def _render_finance_readiness(manifest: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    contract = manifest["artifact_contract"]
    venture = contract["venture"]
    gaps = _finance_gap_map(contract)
    missing = [row for row in gaps if row["state"] == "EVIDENCE_NEEDED"]
    rows = "".join(
        f"<tr><td>{html.escape(row['requirement_id'])}</td><td>{html.escape(row['label'])}</td><td>{html.escape(row['state'])}</td><td>{html.escape(', '.join(row['supporting_evidence_ids']) or 'None supplied')}</td></tr>"
        for row in gaps
    )
    assumptions = "".join(f"<li>{html.escape(str(value))}</li>" for value in contract["assumptions"])
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>DIO Finance Readiness Studio</title><style>body{font:16px/1.55 system-ui,sans-serif;margin:0;color:#172230;background:#f4f7f7}main{max-width:1000px;margin:auto;padding:44px 24px}h1,h2{color:#113f42}.gate{border-left:5px solid #c07a00;background:#fff3dc;padding:14px 18px;font-weight:700}table{width:100%;border-collapse:collapse;background:white}th,td{border:1px solid #ccd8d8;padding:10px;text-align:left;vertical-align:top}th{background:#e5f1ef}.missing{font-weight:800;color:#8a3b00}</style></head><body><main>"
        "<p>DIO // FINANCE READINESS STUDIO // CONTROLLED PROOF</p>"
        f"<h1>{html.escape(venture['name'])}</h1><p><strong>Funding need:</strong> {html.escape(venture['funding_need'])}</p>"
        f"<p>{html.escape(contract['purpose'])}</p><p class='gate'>{html.escape(contract['decision_boundary'])}</p>"
        "<h2>Evidence-readiness matrix</h2><table><thead><tr><th>ID</th><th>Published requirement fixture</th><th>Readiness state</th><th>Evidence</th></tr></thead>"
        f"<tbody>{rows}</tbody></table><h2>Unresolved assumptions</h2><ul>{assumptions}</ul>"
        f"<p class='missing'>Missing mandatory evidence items: {len(missing)}.</p>"
        "<p>No lender approval, affordability, underwriting, credit-bureau or funding outcome is inferred by this controlled dossier.</p>"
        "</main></body></html>"
    )
    summary = (
        f"Finance Readiness Studio controlled review\nVenture: {venture['name']}\nFunding need: {venture['funding_need']}\n"
        f"Requirements reviewed: {len(gaps)}\nEvidence-needed items: {len(missing)}\n"
        f"Decision boundary: {contract['decision_boundary']}\n"
    )
    readiness = {
        "schema": "dio.finance_readiness_controlled_object.v1",
        "studio_id": manifest["studio_id"],
        "venture": venture,
        "requirement_gap_map": gaps,
        "evidence_needed_count": len(missing),
        "assumptions": contract["assumptions"],
        "forbidden_claims": contract["forbidden_claims"],
        "decision_boundary": contract["decision_boundary"],
        "readiness_state": "EVIDENCE_GAPS_PRESENT" if missing else "EVIDENCE_SET_COMPLETE_FOR_HUMAN_REVIEW",
        "lender_decision": "NOT_MADE",
        "financial_advice": "NOT_PROVIDED",
        "human_gate": "NEEDS_YOU",
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
    return {
        "publication/ARTICLE_DRAFT.html": article,
        "publication/CLAIM_SOURCE_MAP.txt": map_text,
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
