#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.dio_mail_branding import branded_email  # noqa: E402
from scripts.manage_document_studio_commercial import (  # noqa: E402
    DEFAULT_EVENT_LOG as DOCUMENT_EVENT_LOG,
    DEFAULT_JOB_ROOT as DOCUMENT_JOB_ROOT,
    DEFAULT_SERVICE_CONFIG as DOCUMENT_SERVICE_CONFIG,
    create_job as create_document_job,
)
from scripts.manage_mail_intent import create_intent, emit_event, write_json  # noqa: E402
from scripts.manage_product_workflow import (  # noqa: E402
    DEFAULT_RUNS_ROOT,
    DEFAULT_STATE_ROOT as PRODUCT_STATE_ROOT,
    bootstrap_job,
)
from scripts.manage_sophia_commercial import (  # noqa: E402
    DEFAULT_EVENT_LOG as SOPHIA_EVENT_LOG,
    DEFAULT_JOB_ROOT as SOPHIA_JOB_ROOT,
    DEFAULT_SERVICE_CONFIG as SOPHIA_SERVICE_CONFIG,
    create_job as create_sophia_job,
)


DEFAULT_LEAD_ROOT = ROOT / "state" / "leads"
DEFAULT_PROMOTION_ROOT = ROOT / "state" / "lead_promotions"
DEFAULT_MAIL_ROOT = ROOT / "state" / "mail_intents"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
DEFAULT_ROUTE_CONFIG = ROOT / "config" / "product_class_routes.json"

ENGINE_PRODUCTS = {"evidex", "homs"}
COMMERCIAL_PRODUCTS = {"sophia", "document_studio"}
MATERIAL_PATH_KEYS = (
    "hymark_input_dir",
    "input_dir",
    "source_dir",
    "upload_dir",
    "batch_dir",
    "job_folder",
    "document_path",
    "manuscript_path",
    "evidence_path",
    "source_path",
)
DOCUMENT_CONSENTS = (
    "document_owner_authorized",
    "remote_processing_approved",
    "human_review_required",
    "certified_translation_not_requested",
)
SOPHIA_CONSENTS = (
    "manuscript_owner_authorized",
    "gemini_remote_processing_approved",
    "service_terms_accepted",
)


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_id(value: str, label: str = "id") -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,120}", value):
        raise ValueError(f"Invalid {label}.")
    return value


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def load_route_config(path: Path = DEFAULT_ROUTE_CONFIG) -> dict[str, Any]:
    payload = read_json(path)
    if payload.get("schema") != "dio.product_class_routes.v1":
        raise ValueError("Unsupported product-class route contract.")
    return payload


def normalize_product(value: str, route_config: dict[str, Any] | None = None) -> str:
    config = route_config or load_route_config()
    product = slug(value)
    product = str((config.get("aliases") or {}).get(product, product))
    known = set((config.get("direct_products") or {})) | set((config.get("product_classes") or {}))
    if product not in known:
        raise ValueError(f"Unsupported lead product for promotion: {product or 'missing'}")
    return product


def route_definition(product: str, route_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = route_config or load_route_config()
    direct = (config.get("direct_products") or {}).get(product)
    if direct:
        return {"product": product, "registered_as": "direct_product", **direct}
    product_class = (config.get("product_classes") or {}).get(product)
    if product_class:
        return {"product": product, "registered_as": "product_class", **product_class}
    raise ValueError(f"No product route contract found for {product}.")


def stable_suffix(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def lead_path(lead_root: Path, lead_id: str) -> Path:
    lead_id = safe_id(lead_id.upper(), "lead id")
    return lead_root / f"{lead_id}.json"


def load_lead(lead_root: Path, lead_id: str) -> tuple[Path, dict[str, Any]]:
    path = lead_path(lead_root, lead_id)
    if not path.is_file():
        raise FileNotFoundError(f"Lead does not exist: {lead_id}")
    return path, read_json(path)


def qualified(lead: dict[str, Any]) -> bool:
    return lead.get("state") == "qualified" or (lead.get("qualification") or {}).get("state") == "qualified"


def promotion_path(promotion_root: Path, lead_id: str) -> Path:
    return promotion_root / safe_id(lead_id.upper(), "lead id") / "LEAD_PROMOTION_RECEIPT.json"


def lead_contact(lead: dict[str, Any]) -> dict[str, str]:
    contact = lead.get("contact") or {}
    return {
        "name": str(contact.get("name") or "there").strip(),
        "email": str(contact.get("email") or "").strip(),
        "organisation": str(contact.get("organisation") or contact.get("organization") or "").strip(),
    }


def request_value(lead: dict[str, Any], keys: tuple[str, ...]) -> str:
    request = lead.get("request") or {}
    for key in keys:
        value = request.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def explicit_consents(lead: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    top_level = lead.get("consents") or {}
    request_level = (lead.get("request") or {}).get("consents") or {}
    if isinstance(top_level, dict):
        merged.update(top_level)
    if isinstance(request_level, dict):
        merged.update(request_level)
    return merged


def missing_consents(lead: dict[str, Any], required: tuple[str, ...]) -> list[str]:
    consents = explicit_consents(lead)
    return [f"consent:{key}" for key in required if consents.get(key) is not True]


def resolve_material_fields(lead: dict[str, Any]) -> dict[str, str]:
    request = lead.get("request") or {}
    resolved: dict[str, str] = {}
    for key in MATERIAL_PATH_KEYS:
        raw = request.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        else:
            path = path.resolve()
        resolved[key] = str(path)
    return resolved


def material_paths_present(lead: dict[str, Any], product: str) -> bool:
    if any(Path(value).exists() for value in resolve_material_fields(lead).values()):
        return True
    request = lead.get("request") or {}
    return product == "evidex" and bool(str(request.get("evidence_text") or request.get("scope") or "").strip())


def existing_engine_workflows(lead_id: str, product: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for path in PRODUCT_STATE_ROOT.glob("*/JOB.json"):
        try:
            workflow = read_json(path)
            source_path = Path(str(workflow.get("source_job_path") or ""))
            source = read_json(source_path) if source_path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            continue
        if workflow.get("product") == product and (source.get("source") or {}).get("lead_id") == lead_id:
            matches.append({
                "job_id": workflow.get("job_id"),
                "workflow_path": str(path),
                "source_job_path": str(source_path),
                "processing_state": (workflow.get("processing") or {}).get("state"),
                "notification_state": (workflow.get("notification") or {}).get("state"),
            })
    return sorted(matches, key=lambda item: str(item.get("job_id") or ""))


def write_engine_source_job(lead: dict[str, Any], product: str, runs_root: Path, lead_root: Path = DEFAULT_LEAD_ROOT) -> Path:
    lead_id = safe_id(str(lead["lead_id"]).upper(), "lead id")
    job_id = f"{product}-{stable_suffix(lead_id + ':' + product)}"
    path = runs_root / "public_leads" / lead_id / product / f"{job_id}.json"
    if path.exists():
        return path.resolve()
    request = lead.get("request") or {}
    contact = lead_contact(lead)
    material_fields = resolve_material_fields(lead)
    path.parent.mkdir(parents=True, exist_ok=True)
    source_metadata: dict[str, Any] = {
        "kind": "public_lead",
        "lead_id": lead_id,
        "conversation_id": lead.get("conversation_id"),
        "lead_path": str((lead_root / f"{lead_id}.json").resolve()),
        "source_materials": material_fields,
    }
    source_metadata.update(material_fields)
    payload: dict[str, Any] = {
        "schema": "dio.autorelease_job.v1",
        "job_id": job_id,
        "created_at": timestamp(),
        "status": "needs_review",
        "client_id": contact.get("organisation") or contact["email"] or "public-lead",
        "source": source_metadata,
        "route": {
            "product": product,
            "confidence": 0.9,
            "reason": "Qualified public lead promoted through an explicit direct-product route contract.",
        },
        "risk": "moderate",
        "inputs": [
            {
                "kind": "public_intake",
                "sender": f"{contact['name']} <{contact['email']}>",
                "subject": str(lead.get("offer") or f"{product} request"),
                "scope": str(request.get("scope") or request.get("summary") or request),
                "source_material_state": "present" if material_paths_present(lead, product) else "missing_or_unverified",
                "source_materials": material_fields,
            }
        ],
        "evidence": [
            {
                "evidence_id": stable_suffix(lead_id),
                "source_type": "public_intake",
                "source_path": str((lead_root / f"{lead_id}.json").resolve()),
                "title": str(lead.get("offer") or f"{product} intake"),
                "date_observed": timestamp(),
                "text_extract": str(request.get("scope") or request.get("summary") or request)[:2500],
                "hash": stable_suffix(json.dumps(request, sort_keys=True, ensure_ascii=True)),
                "claims": [],
                "mapped_to": [],
                "confidence": 0.8,
                "review_status": "candidate",
            }
        ],
        "outputs": [],
        "approval": {"required": True, "state": "pending"},
        "billing": {"invoice_id": None, "payment_status": "pending"},
    }
    # HOMS' canonical resolver checks these names at the job root as well as nested containers.
    payload.update({key: value for key, value in material_fields.items() if key in {"hymark_input_dir", "input_dir", "job_folder", "batch_dir", "source_dir", "upload_dir"}})
    write_json(path, payload)
    path.chmod(0o600)
    return path.resolve()


def missing_input_copy(product: str, lead: dict[str, Any], missing_inputs: list[str] | None = None) -> tuple[str, str, list[str], str, str]:
    missing_inputs = missing_inputs or []
    authority_missing = [item.removeprefix("consent:") for item in missing_inputs if item.startswith("consent:")]
    if authority_missing:
        readable = ", ".join(item.replace("_", " ") for item in authority_missing)
        return (
            "DIO authority confirmation needed",
            "Your request is scoped, but DIO does not yet have the authority needed to process the source material.",
            [
                f"Please confirm the required authority fields before processing: {readable}.",
                "Qualification of a request is not permission to process documents remotely, use a model provider, or accept service terms on your behalf.",
                "Once the required authority is recorded, DIO can continue through the normal review and delivery gates.",
            ],
            "Review DIO Workflows",
            "https://byron2306.github.io/DIO-Workflows/",
        )
    if product == "homs":
        return (
            "HOMS intake materials needed",
            "Your HOMS assessment workflow is scoped. Please send the teaching materials so we can prepare the pack.",
            [
                "Please reply with the subject, grade, term, assessment type, rubric or memo, and any required source documents or learner submissions.",
                "For marking batches, include the electronic submissions, mark list, memo or rubric, and any institutional moderation instructions.",
                "For exam or learning-material jobs, include the topic coverage, marks, duration, cognitive level expectations and any house style requirements.",
            ],
            "View HOMS Assessment Desk",
            "https://byron2306.github.io/DIO-Workflows/sites/homs/",
        )
    if product == "evidex":
        return (
            "Evidex source files needed",
            "Your Evidex evidence-pack workflow is scoped. Please send the source archive so we can map claims to evidence.",
            [
                "Please reply with the documents, messages, spreadsheets, PDFs or links you want included in the evidence pack.",
                "Add the decision, claim, dispute or audit question you want the pack to answer.",
                "DIO will prepare a reviewable evidence table, provenance map and finished pack after the source material is available.",
            ],
            "View Evidex Evidence Packs",
            "https://byron2306.github.io/DIO-Workflows/sites/evidex/",
        )
    if product == "sophia":
        return (
            "Sophia manuscript intake needed",
            "Your Sophia academic review request is scoped. Please send the manuscript and review question through the private intake route.",
            [
                "Please provide the manuscript or chapter, your research question, discipline, citation style, and the sections you want reviewed.",
                "Sophia can prepare literature-alignment notes, reference checks, claim-to-source review and reviewer-style commentary.",
                "Remote retrieval and document processing only proceed once the required authority fields are recorded.",
            ],
            "View Sophia Academic Review",
            "https://byron2306.github.io/DIO-Workflows/sites/sophia/",
        )
    if product == "vamp":
        return (
            "VAMP evidence intake needed",
            "Your VAMP snapshot request is scoped. Please send the review profile and evidence sources we should map.",
            [
                "Please provide the role profile, KPAs or review criteria, review period, and the evidence sources you want mapped.",
                "VAMP prepares a performance-evidence snapshot showing supported claims, weak evidence and missing material before review day.",
                "Sensitive performance material remains held behind human review and delivery approval.",
            ],
            "View VAMP Evidence Snapshot",
            "https://byron2306.github.io/DIO-Workflows/sites/vamp/",
        )
    return (
        "Document Studio source file needed",
        "Your Document Studio request is scoped. Please send the document and language or formatting requirements.",
        [
            "Please provide the source document, target language where applicable, audience, document domain and deadline.",
            "Document Studio can prepare technical edits, translation review candidates, redlines, clean copies and formatted delivery packs.",
            "Certified, sworn or legally attested translation is outside this pilot unless separately arranged.",
        ],
        "View DIO Document Studio",
        "https://byron2306.github.io/DIO-Workflows/sites/document-studio/",
    )


def create_missing_input_intent(
    lead: dict[str, Any],
    product: str,
    promotion_dir: Path,
    mail_root: Path,
    event_log: Path,
    missing_inputs: list[str] | None = None,
) -> dict[str, Any]:
    contact = lead_contact(lead)
    if not contact["email"]:
        return {"state": "blocked", "reason": "Lead has no recipient email."}
    existing = promotion_dir / "MISSING_INPUT_MAIL_INTENT.json"
    if existing.is_file():
        return read_json(existing)
    eyebrow, headline, body, cta_label, cta_url = missing_input_copy(product, lead, missing_inputs)
    plain, body_html = branded_email(
        product=product,
        eyebrow="INTAKE MATERIALS",
        headline=headline,
        greeting=f"Hello {contact['name']},",
        intro="Thanks. We can keep the request staged, but DIO will not cross a missing source or authority boundary.",
        body=body,
        reference=str(lead.get("lead_id") or ""),
        cta_label=cta_label,
        cta_url=cta_url,
        caution="Please do not send passwords. If the files are sensitive, reply first and DIO will provide the safest available intake route.",
    )
    spec_path = promotion_dir / "MISSING_INPUT_MAIL_SPEC.json"
    write_json(spec_path, {
        "purpose": "missing_input_request",
        "lead_id": lead.get("lead_id"),
        "conversation_id": lead.get("conversation_id"),
        "recipient": contact["email"],
        "subject": f"{eyebrow} ({lead.get('lead_id')})",
        "body": plain,
        "body_html": body_html,
        "attachments": [],
        "risk": "moderate",
    })
    intent = create_intent(spec_path, mail_root, event_log)
    write_json(existing, intent)
    return intent


def commercial_spec_from_lead(lead: dict[str, Any], product: str, promotion_dir: Path) -> tuple[Path | None, list[str]]:
    request = lead.get("request") or {}
    contact = lead_contact(lead)
    missing: list[str] = []
    if product == "document_studio":
        document_path = request_value(lead, ("document_path", "source_document_path", "file_path"))
        service = str(request.get("service") or request.get("lane") or "technical_edit").strip().lower()
        service = {
            "edit": "technical_edit",
            "formatting": "technical_edit",
            "translation_review": "translation",
            "edit_translation": "edit_and_translate",
        }.get(service, service)
        if service not in {"technical_edit", "translation", "edit_and_translate"}:
            service = "technical_edit"
        if not document_path:
            missing.append("document_path")
        if service in {"translation", "edit_and_translate"} and not str(request.get("target_language") or "").strip():
            missing.append("target_language")
        if missing:
            return None, missing
        missing = missing_consents(lead, DOCUMENT_CONSENTS)
        if missing:
            return None, missing
        consents = explicit_consents(lead)
        spec = {
            "job_id": f"DOC-{stable_suffix(str(lead['lead_id']))}",
            "customer": {"name": contact["name"], "email": contact["email"], "organization": contact["organisation"] or None},
            "service": service,
            "title": str(request.get("title") or lead.get("offer") or "Document Studio request"),
            "document_path": document_path,
            "source_language": str(request.get("source_language") or "English"),
            "target_language": request.get("target_language"),
            "document_domain": str(request.get("document_domain") or "professional document"),
            "audience": str(request.get("audience") or "professional reader"),
            "provider": str(request.get("provider") or "nim"),
            "consents": {key: True for key in DOCUMENT_CONSENTS if consents.get(key) is True},
        }
    else:
        document_path = request_value(lead, ("document_path", "manuscript_path", "source_document_path", "file_path"))
        research_question = str(request.get("research_question") or request.get("scope") or "").strip()
        if not document_path:
            missing.append("document_path")
        if len(research_question) < 8:
            missing.append("research_question")
        if missing:
            return None, missing
        missing = missing_consents(lead, SOPHIA_CONSENTS)
        if missing:
            return None, missing
        consents = explicit_consents(lead)
        spec = {
            "job_id": f"SOPHIA-{stable_suffix(str(lead['lead_id']))}",
            "customer": {"name": contact["name"], "email": contact["email"], "institution": contact["organisation"]},
            "title": str(request.get("title") or lead.get("offer") or "Sophia academic review"),
            "document_path": document_path,
            "research_question": research_question,
            "literature_queries": request.get("literature_queries") or [research_question],
            "citation_style": str(request.get("citation_style") or "APA 7"),
            "consents": {key: True for key in SOPHIA_CONSENTS if consents.get(key) is True},
        }
    spec_path = promotion_dir / f"{product.upper()}_JOB_SPEC.json"
    write_json(spec_path, spec)
    spec_path.chmod(0o600)
    return spec_path, []


def promote_lead(
    lead_id: str,
    *,
    lead_root: Path = DEFAULT_LEAD_ROOT,
    promotion_root: Path = DEFAULT_PROMOTION_ROOT,
    runs_root: Path = DEFAULT_RUNS_ROOT,
    mail_root: Path = DEFAULT_MAIL_ROOT,
    event_log: Path = DEFAULT_EVENT_LOG,
    controlled: bool = False,
    force: bool = False,
    route_config_path: Path = DEFAULT_ROUTE_CONFIG,
) -> dict[str, Any]:
    _, lead = load_lead(lead_root, lead_id)
    lead_id = safe_id(str(lead["lead_id"]).upper(), "lead id")
    route_config = load_route_config(route_config_path)
    product = normalize_product(str(lead.get("product") or ""), route_config)
    route = route_definition(product, route_config)
    if not qualified(lead) and not force:
        raise ValueError("Only qualified leads can be promoted. Qualify the lead first or pass --force.")

    receipt_path = promotion_path(promotion_root, lead_id)
    if receipt_path.is_file():
        return read_json(receipt_path)
    promotion_dir = receipt_path.parent
    promotion_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "schema": "dio.lead_promotion_receipt.v1",
        "lead_id": lead_id,
        "product": product,
        "state": "promoted",
        "created_at": timestamp(),
        "controlled": controlled,
        "lead_path": str((lead_root / f"{lead_id}.json").resolve()),
        "route_contract": route,
        "outputs": {},
        "missing_inputs": [],
    }

    route_kind = str(route.get("route_kind") or "")
    if route_kind == "engine" and route.get("auto_promotable") is True:
        engine = str(route.get("engine") or "")
        if engine not in ENGINE_PRODUCTS:
            raise ValueError(f"Unsupported direct engine route: {engine}")
        existing = existing_engine_workflows(lead_id, engine)
        if existing:
            result["state"] = "already_promoted"
            result["outputs"]["product_workflows"] = existing
        else:
            source_path = write_engine_source_job(lead, engine, runs_root, lead_root)
            workflow = bootstrap_job(source_path, PRODUCT_STATE_ROOT, runs_root)
            result["outputs"]["source_job_path"] = str(source_path)
            result["outputs"]["product_workflow_path"] = str(PRODUCT_STATE_ROOT / workflow["job_id"] / "JOB.json")
            result["outputs"]["product_job_id"] = workflow["job_id"]
            result["outputs"]["next_state"] = "awaiting_intake_approval"
        if not material_paths_present(lead, engine):
            result["missing_inputs"] = ["source_materials"]
            intent = create_missing_input_intent(lead, engine, promotion_dir, mail_root, event_log, result["missing_inputs"])
            result["outputs"]["missing_input_mail_intent_id"] = intent.get("mail_intent_id")
            result["state"] = "promoted_awaiting_source_materials"
    elif route_kind == "commercial" and route.get("auto_promotable") is True:
        engine = str(route.get("engine") or "")
        if engine not in COMMERCIAL_PRODUCTS:
            raise ValueError(f"Unsupported direct commercial route: {engine}")
        spec_path, missing = commercial_spec_from_lead(lead, engine, promotion_dir)
        result["missing_inputs"] = missing
        if spec_path:
            if engine == "document_studio":
                job = create_document_job(spec_path, DOCUMENT_JOB_ROOT, DOCUMENT_EVENT_LOG, DOCUMENT_SERVICE_CONFIG, controlled=controlled)
                result["outputs"]["document_studio_job_id"] = job["job_id"]
                result["outputs"]["document_studio_job_path"] = str(DOCUMENT_JOB_ROOT / job["job_id"] / "JOB.json")
            else:
                job = create_sophia_job(spec_path, SOPHIA_JOB_ROOT, SOPHIA_EVENT_LOG, SOPHIA_SERVICE_CONFIG, controlled=controlled)
                result["outputs"]["sophia_job_id"] = job["job_id"]
                result["outputs"]["sophia_job_path"] = str(SOPHIA_JOB_ROOT / job["job_id"] / "JOB.json")
        else:
            authority_missing = any(item.startswith("consent:") for item in missing)
            result["state"] = "awaiting_authority" if authority_missing else "awaiting_private_intake"
            intent = create_missing_input_intent(lead, engine, promotion_dir, mail_root, event_log, missing)
            result["outputs"]["missing_input_mail_intent_id"] = intent.get("mail_intent_id")
    elif route_kind == "profile_extension":
        result["state"] = "awaiting_typed_route"
        result["missing_inputs"] = ["typed_product_profile", "operator_route_approval"]
        result["outputs"]["suggested_engine"] = route.get("suggested_engine")
        result["outputs"]["processing_started"] = False
    else:
        suggested = str(route.get("engine") or route.get("suggested_engine") or product)
        intent = create_missing_input_intent(lead, "vamp" if suggested == "vamp" else "document_studio", promotion_dir, mail_root, event_log, ["specialist_source_profile"])
        result["state"] = "awaiting_specialist_intake"
        result["missing_inputs"] = ["specialist_source_profile"]
        result["outputs"]["missing_input_mail_intent_id"] = intent.get("mail_intent_id")

    write_json(receipt_path, result)
    receipt_path.chmod(0o600)
    lead["promotion"] = {
        "state": result["state"],
        "promoted_at": result["created_at"],
        "receipt_path": str(receipt_path),
        "route_contract": result["route_contract"],
        "outputs": result["outputs"],
        "missing_inputs": result["missing_inputs"],
    }
    lead["updated_at"] = timestamp()
    write_json(lead_root / f"{lead_id}.json", lead)
    emit_event(event_log, "lead.promoted_to_product_route", "action", "lead", lead_id, {"product": product, "state": result["state"], "route_kind": route_kind}, lead_id)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a qualified public DIO lead into a governed product route.")
    parser.add_argument("lead_id")
    parser.add_argument("--controlled", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--route-config", type=Path, default=DEFAULT_ROUTE_CONFIG)
    args = parser.parse_args()
    print(json.dumps(promote_lead(args.lead_id, controlled=args.controlled, force=args.force, route_config_path=args.route_config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
