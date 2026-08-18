from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from adapters.format_core.renderer import build_paragraph_semantic_content, render_semantic_asset
from adapters.lingua.communicator import register_communication
from market_command.core import MarketStore
from products.commercial_truth import evaluate_product, load_config
from products.studio_harvest import build_studio_case
from scripts.build_multichannel_campaign_factory import copy_package
from scripts.manage_mail_intent import create_intent_from_payload
from scripts.run_evidex_jobs import build_intake as build_evidex_intake

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN = "DIO_STUDIO_NATIVE_EXECUTION_READY"


class StudioNativeActivationError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalise_lingua(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": receipt.get("schema"),
        "object_id": receipt.get("object_id"),
        "source_document_hash": receipt.get("source_document_hash"),
        "owner": receipt.get("owner"),
        "artifact_type": receipt.get("artifact_type"),
        "channel": receipt.get("channel"),
        "source_language": receipt.get("source_language"),
        "target_language": receipt.get("target_language"),
        "translation_state": receipt.get("translation_state"),
        "semantic_lineage_created": receipt.get("semantic_lineage_created") is True,
        "external_action_executed": receipt.get("external_action_executed") is True,
        "publication_authorized": receipt.get("publication_authorized") is True,
        "send_authorized": receipt.get("send_authorized") is True,
        "authority_created": receipt.get("authority_created") is True,
    }


def _lingua_body(manifest: dict[str, Any]) -> tuple[str, str]:
    contract = manifest["artifact_contract"]
    if contract["kind"] == "site":
        brand = contract["brand"]
        sections = contract["sections"]
        body = "\n\n".join([
            str(brand["headline"]),
            str(brand["subhead"]),
            *[f"{row['title']}: {row['body']}" for row in sections],
        ])
        return str(brand["title"]), body
    draft = contract["draft"]
    return str(draft["subject"]), "\n".join(str(row) for row in draft["body_lines"])


def _invoke_lingua(manifest: dict[str, Any], sandbox_root: Path) -> dict[str, Any]:
    subject, body = _lingua_body(manifest)
    receipt = register_communication(
        dio_root=sandbox_root,
        owner=manifest["studio_id"],
        artifact_type=f"{manifest['artifact_contract']['kind']}_studio_controlled_draft",
        channel="studio_harvest",
        subject=subject,
        body=body,
        audience=str(manifest["job"]["buyer"]),
        privacy_domain="controlled_studio_proof",
        correlation_id=f"STUDIO-{manifest['studio_id'].upper()}",
        source_message_id="CONTROLLED-CASE-001",
        source_language="English",
        target_language="English",
        purpose="controlled_studio_execution",
        authority_boundary="LINGUA preserves Studio meaning but cannot publish, send, spend, take payment, create professional authority, or release work.",
        product_context=manifest["studio_id"],
    )
    normalized = _normalise_lingua(receipt)
    if not normalized["semantic_lineage_created"] or normalized["authority_created"]:
        raise StudioNativeActivationError("LINGUA native execution did not preserve the authority boundary")
    return normalized


def _semantic_content(manifest: dict[str, Any]) -> dict[str, Any]:
    subject, body = _lingua_body(manifest)
    rows = [{"paragraph_id": "P1", "text": subject}]
    for index, paragraph in enumerate([part.strip() for part in body.split("\n") if part.strip()], 2):
        rows.append({"paragraph_id": f"P{index}", "text": paragraph})
    return build_paragraph_semantic_content(
        object_id=f"STUDIO-{manifest['studio_id'].upper()}",
        version=str(manifest.get("studio_version") or "1.0.0"),
        title=subject,
        source_language="English",
        source_rows=rows,
        context={
            "product": manifest["studio_id"],
            "artifact_type": f"{manifest['artifact_contract']['kind']}_studio_preview",
            "audience": str(manifest["job"]["buyer"]),
        },
    )


def _invoke_format_core(manifest: dict[str, Any], sandbox_root: Path, native_dir: Path) -> dict[str, Any]:
    content = _semantic_content(manifest)
    render_dir = sandbox_root / "format-render"
    receipt = render_semantic_asset(
        content,
        render_dir,
        style_profile="dio_professional",
        delivery_profile="editable_review",
        language="English",
        channels=["html"],
        release_mode=False,
        source_root=ROOT,
    )
    html_row = next((row for row in receipt.get("outputs") or [] if row.get("channel") == "html"), None)
    if not html_row:
        raise StudioNativeActivationError("Format Core did not produce the requested HTML review asset")
    source = render_dir / str(html_row["path"])
    target = native_dir / "document_studio" / "CONTROLLED_PREVIEW.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    normalized = {
        "schema": receipt.get("schema"),
        "object_id": receipt.get("object_id"),
        "status": receipt.get("status"),
        "style_profile": receipt.get("style_profile"),
        "style_profile_hash": receipt.get("style_profile_hash"),
        "delivery_profile": receipt.get("delivery_profile"),
        "delivery_profile_hash": receipt.get("delivery_profile_hash"),
        "release_mode": receipt.get("release_mode"),
        "semantic_source_hash": receipt.get("semantic_source_hash"),
        "semantic_blocks": receipt.get("semantic_blocks"),
        "qa": receipt.get("qa"),
        "outputs": [{"channel": "html", "sha256": _sha(target), "bytes": target.stat().st_size}],
        "authority_created": False,
        "publication_authorized": False,
    }
    if normalized["status"] != "rendered_review_candidate" or not (normalized.get("qa") or {}).get("passed"):
        raise StudioNativeActivationError("Format Core native Studio render did not pass controlled review QA")
    _write_json(native_dir / "document_studio" / "FORMAT_CORE_NORMALIZED_RECEIPT.json", normalized)
    return normalized


def _invoke_nichefoundry_site(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    positioning = contract["positioning"]
    product = {
        "id": manifest["studio_id"],
        "short_name": "Site Studio",
        "name": manifest["name"],
        "cta": "Prepare a website brief",
        "proof": "Controlled Studio composition produces a reviewable website package while publication remains human-held.",
        "promise": positioning["desired_outcome"],
    }
    audience = {
        "id": "controlled-buyer",
        "name": str(manifest["job"]["buyer"]),
        "pain": positioning["buyer_problem"],
        "outcome": positioning["desired_outcome"],
    }
    package = copy_package(product, audience, "LINKEDIN_ORGANIC")
    if not package.get("headline") or not package.get("body") or not package.get("cta"):
        raise StudioNativeActivationError("NicheFoundry native copy package is incomplete")
    return {
        "schema": "dio.studio_native_nichefoundry_receipt.v1",
        "studio_id": manifest["studio_id"],
        "channel": "LINKEDIN_ORGANIC",
        "copy": package,
        "publication": "REFUSE",
        "spend": "REFUSE",
        "authority_created": False,
    }


def _invoke_market_command_site(manifest: dict[str, Any], sandbox_root: Path) -> dict[str, Any]:
    store = MarketStore(
        db_path=sandbox_root / "state" / "market_command" / "market.db",
        event_log=sandbox_root / "telemetry" / "dio_events.jsonl",
        config={
            "max_experiment_budget_minor": 0,
            "default_experiment_window_days": 14,
            "require_approved_content_for_activation": False,
        },
    )
    campaign = store.create_campaign({
        "campaign_id": "MKT-STUDIO-SITE-CONTROLLED",
        "product_line_id": manifest["studio_id"],
        "name": "Site Studio controlled demand observation",
        "audience": str(manifest["job"]["buyer"]),
        "channel_id": "LINKEDIN_ORGANIC",
        "mode": "controlled_proof",
        "objective": "Prepare a bounded, zero-spend campaign shell for the Site Studio controlled proof.",
        "budget_cap_minor": 0,
        "currency": "ZAR",
        "creative_brief": "Use only proof-backed Site Studio copy. Publication remains held.",
        "source_lineage": {"studio_id": manifest["studio_id"]},
    })
    normalized = {
        "schema": "dio.studio_native_market_command_receipt.v1",
        "campaign_id": campaign["campaign_id"],
        "product_line_id": campaign["product_line_id"],
        "name": campaign["name"],
        "audience": campaign["audience"],
        "channel_id": campaign["channel_id"],
        "mode": campaign["mode"],
        "objective": campaign["objective"],
        "budget_cap_minor": campaign["budget_cap_minor"],
        "currency": campaign["currency"],
        "state": campaign["state"],
        "approval_state": campaign["approval_state"],
        "publication_state": campaign["publication_state"],
        "governance": campaign["governance"],
        "utm": campaign["utm"],
        "spend_executed": False,
        "publication_executed": False,
        "authority_created": False,
    }
    if normalized["budget_cap_minor"] != 0 or normalized["publication_state"] != "held" or normalized["approval_state"] != "pending":
        raise StudioNativeActivationError("Market Command Studio campaign escaped its held zero-spend boundary")
    return normalized


def _evidex_job(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    if contract["kind"] == "site":
        evidence_text = " ".join(str(row["body"]) for row in contract["sections"])
        subject = f"{contract['brand']['title']} controlled website evidence intake"
    else:
        evidence_text = " ".join(str(row) for row in contract["must_preserve"])
        subject = "Controlled invoice-dispute correspondence evidence intake"
    return {
        "job_id": f"STUDIO-{manifest['studio_id'].upper()}-001",
        "created_at": "2026-08-18T00:00:00+00:00",
        "route": {"product": manifest["studio_id"], "confidence": 1.0, "reason": "Studio Harvest controlled native adapter proof"},
        "risk": "controlled",
        "inputs": [{
            "sender": "Controlled Studio Fixture <fixture@example.invalid>",
            "subject": subject,
            "attachment_names": "none",
            "intent": "controlled Studio evidence intake",
            "urgency": "normal",
            "next_step": "human review",
        }],
        "evidence": [{"text_extract": evidence_text}],
    }


def _invoke_evidex_intake(manifest: dict[str, Any]) -> dict[str, Any]:
    intake = build_evidex_intake(_evidex_job(manifest))
    return {
        "schema": "dio.studio_native_evidex_adapter_receipt.v1",
        "studio_id": manifest["studio_id"],
        "adapter": "scripts.run_evidex_jobs.build_intake",
        "capability_executed": "evidence.intake.structure",
        "intake": intake,
        "full_evidex_engine_invoked": False,
        "authority_created": False,
    }


def _invoke_commercial_truth(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    result = evaluate_product(manifest["studio_id"], [], load_config(root))
    claims = result.get("claims") or {}
    if any(value != "UNKNOWN" for value in claims.values()):
        raise StudioNativeActivationError("Commercial Truth inflated an unobserved Studio into supported market truth")
    if result.get("authority_created") or result.get("external_release_authorized"):
        raise StudioNativeActivationError("Commercial Truth created forbidden Studio authority")
    return result


def _invoke_outlook_correspondence(manifest: dict[str, Any], sandbox_root: Path) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    draft = contract["draft"]
    intent = create_intent_from_payload(
        {
            "mail_intent_id": "MAIL-STUDIO-HARVEST-CORRESPONDENCE-001",
            "purpose": "professional_correspondence_controlled_draft",
            "recipient": "client@example.invalid",
            "subject": str(draft["subject"]),
            "body": "\n".join(str(row) for row in draft["body_lines"]),
            "attachments": [],
            "risk": "moderate",
            "product": manifest["studio_id"],
            "audience": "controlled_fixture_recipient",
            "privacy_domain": "controlled_studio_proof",
        },
        sandbox_root / "state" / "mail_intents",
        sandbox_root / "telemetry" / "dio_events.jsonl",
    )
    lingua = intent.get("lingua") or {}
    normalized = {
        "schema": intent.get("schema"),
        "mail_intent_id": intent.get("mail_intent_id"),
        "direction": intent.get("direction"),
        "purpose": intent.get("purpose"),
        "recipient": intent.get("recipient"),
        "subject": intent.get("subject"),
        "body": intent.get("body"),
        "risk": intent.get("risk"),
        "approval": {
            "required": (intent.get("approval") or {}).get("required"),
            "state": (intent.get("approval") or {}).get("state"),
        },
        "send_state": intent.get("send_state"),
        "lingua": {
            "schema": lingua.get("schema"),
            "object_id": lingua.get("object_id"),
            "source_document_hash": lingua.get("source_document_hash"),
            "translation_state": lingua.get("translation_state"),
            "semantic_lineage_created": lingua.get("semantic_lineage_created") is True,
            "send_authorized": lingua.get("send_authorized") is True,
            "authority_created": lingua.get("authority_created") is True,
        },
        "external_send_executed": False,
        "authority_created": False,
    }
    if normalized["send_state"] != "draft" or normalized["approval"] != {"required": True, "state": "pending"}:
        raise StudioNativeActivationError("Outlook Mail Core did not preserve draft-only human approval")
    return normalized


def _organ_ledger(manifest: dict[str, Any], executed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for organ in manifest["required_organs"]:
        engine_id = str(organ["engine_id"])
        required_caps = list(organ.get("capabilities") or [])
        actual = executed.get(engine_id)
        if not actual:
            rows.append({
                "engine_id": engine_id,
                "required_capabilities": required_caps,
                "executed_capabilities": [],
                "execution_state": "SOURCE_BOUND_ONLY",
                "provider_ref": organ["source_ref"],
            })
            continue
        executed_caps = list(actual.get("capabilities") or [])
        unexpected = [cap for cap in executed_caps if cap not in required_caps]
        if unexpected:
            raise StudioNativeActivationError(f"{engine_id} claimed undeclared Studio capabilities: {unexpected}")
        missing = [cap for cap in required_caps if cap not in executed_caps]
        rows.append({
            "engine_id": engine_id,
            "required_capabilities": required_caps,
            "executed_capabilities": executed_caps,
            "execution_state": "NATIVE_EXECUTED" if not missing else "PARTIAL_NATIVE_EXECUTION",
            "provider_ref": actual.get("provider_ref") or organ["source_ref"],
            "receipt_ref": actual.get("receipt_ref"),
            "missing_capabilities": missing,
        })
    native = [row for row in rows if row["execution_state"] == "NATIVE_EXECUTED"]
    partial = [row for row in rows if row["execution_state"] == "PARTIAL_NATIVE_EXECUTION"]
    pending = [row for row in rows if row["execution_state"] == "SOURCE_BOUND_ONLY"]
    if len(native) == len(rows):
        truth = "NATIVE_MULTI_ORGAN_EXECUTION_PROVED"
    elif len(native) >= 2:
        truth = "NATIVE_MULTI_ORGAN_EXECUTION_PROVED_WITH_AUXILIARY_GAPS"
    else:
        truth = "SOURCE_BOUND_EXECUTION_NOT_YET_PROVED"
    return {
        "schema": "dio.studio_native_organ_execution_ledger.v1",
        "studio_id": manifest["studio_id"],
        "organs": rows,
        "native_organ_count": len(native),
        "partial_organ_count": len(partial),
        "source_bound_only_count": len(pending),
        "organ_execution_truth": truth,
        "new_engine_created": False,
    }


def _required_caps(manifest: dict[str, Any], engine_id: str) -> list[str]:
    organ = next((row for row in manifest["required_organs"] if row["engine_id"] == engine_id), None)
    if not organ:
        raise StudioNativeActivationError(f"Studio manifest does not declare organ: {engine_id}")
    return list(organ.get("capabilities") or [])


def activate_studio_case(*, manifest_path: Path, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    composition = build_studio_case(manifest_path=manifest_path, output_dir=output_dir / "composition", root=root)
    manifest = composition["manifest"]
    native_dir = output_dir / "native"
    native_dir.mkdir(parents=True, exist_ok=True)
    executed: dict[str, dict[str, Any]] = {
        "vesper": {
            "capabilities": ["storefront.route.bind"],
            "provider_ref": "presence_core/router.py",
            "receipt_ref": "composition/operations/VESPER_ROUTE_RECEIPT.json",
        }
    }

    with tempfile.TemporaryDirectory(prefix=f"dio-native-{manifest['studio_id']}-") as temp:
        sandbox_root = Path(temp)
        lingua = _invoke_lingua(manifest, sandbox_root)
        _write_json(native_dir / "lingua" / "LINGUA_NATIVE_RECEIPT.json", lingua)
        executed["lingua"] = {
            "capabilities": ["communication.meaning.register", "communication.render.bound"],
            "provider_ref": "adapters/lingua/communicator.py",
            "receipt_ref": "native/lingua/LINGUA_NATIVE_RECEIPT.json",
        }

        _invoke_format_core(manifest, sandbox_root, native_dir)
        executed["document_studio"] = {
            "capabilities": ["document.preview.render"],
            "provider_ref": "adapters/format_core/renderer.py",
            "receipt_ref": "native/document_studio/FORMAT_CORE_NORMALIZED_RECEIPT.json",
        }

        commercial = _invoke_commercial_truth(manifest, root)
        _write_json(native_dir / "commercial_truth" / "COMMERCIAL_TRUTH_EVALUATION.json", commercial)
        executed["commercial_truth"] = {
            "capabilities": ["commercial.claim.boundary"],
            "provider_ref": "products/commercial_truth.py",
            "receipt_ref": "native/commercial_truth/COMMERCIAL_TRUTH_EVALUATION.json",
        }

        if manifest["artifact_contract"]["kind"] == "site":
            niche = _invoke_nichefoundry_site(manifest)
            _write_json(native_dir / "nichefoundry" / "NICHEFOUNDRY_NATIVE_COPY.json", niche)
            executed["nichefoundry"] = {
                "capabilities": ["media.creative.compose"],
                "provider_ref": "scripts/build_multichannel_campaign_factory.py",
                "receipt_ref": "native/nichefoundry/NICHEFOUNDRY_NATIVE_COPY.json",
            }
            market = _invoke_market_command_site(manifest, sandbox_root)
            _write_json(native_dir / "market_command" / "MARKET_COMMAND_NATIVE_RECEIPT.json", market)
            executed["market_command"] = {
                "capabilities": ["campaign.plan"],
                "provider_ref": "market_command/core.py",
                "receipt_ref": "native/market_command/MARKET_COMMAND_NATIVE_RECEIPT.json",
            }
            evidex = _invoke_evidex_intake(manifest)
            _write_json(native_dir / "evidex" / "EVIDEX_NATIVE_ADAPTER_RECEIPT.json", evidex)
            executed["evidex"] = {
                "capabilities": ["evidence.intake.structure"],
                "provider_ref": "scripts/run_evidex_jobs.py",
                "receipt_ref": "native/evidex/EVIDEX_NATIVE_ADAPTER_RECEIPT.json",
            }
        else:
            outlook = _invoke_outlook_correspondence(manifest, sandbox_root)
            _write_json(native_dir / "outlook_mail_core" / "OUTLOOK_NATIVE_DRAFT_RECEIPT.json", outlook)
            executed["outlook_mail_core"] = {
                "capabilities": ["outlook.mail.draft.prepare"],
                "provider_ref": "scripts/manage_mail_intent.py",
                "receipt_ref": "native/outlook_mail_core/OUTLOOK_NATIVE_DRAFT_RECEIPT.json",
            }

    for engine_id, actual in executed.items():
        declared = _required_caps(manifest, engine_id)
        undeclared = [cap for cap in actual["capabilities"] if cap not in declared]
        if undeclared:
            raise StudioNativeActivationError(f"{engine_id} execution escaped the Studio manifest: {undeclared}")

    ledger = _organ_ledger(manifest, executed)
    _write_json(output_dir / "NATIVE_ORGAN_EXECUTION_LEDGER.json", ledger)

    artifacts = []
    for path in sorted(p for p in native_dir.rglob("*") if p.is_file()):
        artifacts.append({"path": str(path.relative_to(output_dir)), "sha256": _sha(path), "bytes": path.stat().st_size})
    artifacts.append({
        "path": "NATIVE_ORGAN_EXECUTION_LEDGER.json",
        "sha256": _sha(output_dir / "NATIVE_ORGAN_EXECUTION_LEDGER.json"),
        "bytes": (output_dir / "NATIVE_ORGAN_EXECUTION_LEDGER.json").stat().st_size,
    })
    proof = {
        "schema": "dio.studio_native_execution_proof_manifest.v1",
        "studio_id": manifest["studio_id"],
        "composition_proof_fingerprint": composition["proof_manifest"]["proof_fingerprint"],
        "artifacts": artifacts,
        "organ_execution_truth": ledger["organ_execution_truth"],
        "native_organ_count": ledger["native_organ_count"],
        "partial_organ_count": ledger["partial_organ_count"],
        "source_bound_only_count": ledger["source_bound_only_count"],
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    proof["proof_fingerprint"] = _fingerprint(proof)
    _write_json(output_dir / "NATIVE_EXECUTION_PROOF_MANIFEST.json", proof)

    receipt = {
        "schema": "dio.studio_native_execution_receipt.v1",
        "studio_id": manifest["studio_id"],
        "studio_name": manifest["name"],
        "composition_execution": "PASS",
        "native_multi_organ_execution": "PASS" if ledger["native_organ_count"] >= 2 else "REFUSE",
        "organ_execution_truth": ledger["organ_execution_truth"],
        "native_organ_count": ledger["native_organ_count"],
        "partial_organ_count": ledger["partial_organ_count"],
        "source_bound_only_count": ledger["source_bound_only_count"],
        "proof_fingerprint": proof["proof_fingerprint"],
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "human_gate": "NEEDS_YOU",
        "authority_created": False,
        "external_effects": False,
        "new_engine_created": False,
    }
    receipt["native_execution_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "NATIVE_EXECUTION_RECEIPT.json", receipt)
    return {
        "manifest": manifest,
        "composition": composition,
        "ledger": ledger,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
    }


def verify_native_execution_proof(output_dir: Path, proof: dict[str, Any]) -> None:
    output_dir = output_dir.resolve()
    for row in proof.get("artifacts") or []:
        path = (output_dir / str(row["path"])).resolve()
        if not path.is_relative_to(output_dir) or not path.is_file() or _sha(path) != row["sha256"]:
            raise StudioNativeActivationError(f"native Studio artifact integrity failure: {row.get('path')}")
