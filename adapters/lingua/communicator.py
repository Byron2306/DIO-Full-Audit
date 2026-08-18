from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from adapters.lingua.lifecycle import register_product_source

LANGUAGE_ALIASES = {"english": "English", "en": "English", "afrikaans": "Afrikaans", "af": "Afrikaans", "isizulu": "isiZulu", "zulu": "isiZulu", "zu": "isiZulu", "sesotho": "Sesotho", "sotho": "Sesotho", "st": "Sesotho", "setswana": "Setswana", "tswana": "Setswana", "tn": "Setswana"}
APPROVED_TRANSLATION_STATES = {"approved", "human_approved", "crystallized", "crystallised"}

def _safe_id(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-")
    return clean[:80] or "COMM"

def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def plain_text_from_html(value: str | None) -> str:
    if not value: return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()

def _normalize_language(value: str) -> str:
    raw = str(value or "").strip()
    if not raw: return "English"
    key = raw.casefold().replace("_", "-")
    if key in LANGUAGE_ALIASES: return LANGUAGE_ALIASES[key]
    prefix = key.split("-", 1)[0]
    if prefix in LANGUAGE_ALIASES: return LANGUAGE_ALIASES[prefix]
    return raw

def requested_language(text: str = "", explicit: str | None = None) -> str:
    if explicit: return _normalize_language(explicit)
    low = str(text or "").casefold()
    for token, language in LANGUAGE_ALIASES.items():
        if len(token) > 2 and re.search(rf"\b{re.escape(token)}\b", low): return language
    return "English"

def _communication_object_id(*, owner: str, channel: str, correlation_id: str | None, source_message_id: str | None, subject: str, body: str) -> str:
    anchor = "|".join([str(owner or "vesper"), str(channel or "conversation"), str(correlation_id or ""), str(source_message_id or ""), subject, body])
    return f"{_safe_id(owner or 'VESPER').upper()}-COMM-{_digest(anchor)[:20].upper()}"

def register_communication(*, dio_root: Path, owner: str, artifact_type: str, channel: str, body: str, subject: str = "", audience: str = "public", privacy_domain: str = "public_communication", correlation_id: str | None = None, source_message_id: str | None = None, source_language: str = "English", target_language: str | None = None, purpose: str = "response", authority_boundary: str = "No external authority is created by linguistic rendering.", product_context: str | None = None, interaction_context: dict[str,Any] | None = None, source_version: str = "1.0.0") -> dict[str, Any]:
    """Register shared communication meaning. This never sends, publishes, approves, spends or creates authority."""
    body = str(body or "").strip(); subject = str(subject or "").strip()
    if not body and not subject: raise ValueError("communication requires subject or body")
    source_language = _normalize_language(source_language); target = requested_language(body, target_language)
    object_id = _communication_object_id(owner=owner, channel=channel, correlation_id=correlation_id, source_message_id=source_message_id, subject=subject, body=body)
    rows: list[dict[str, str]] = []
    if subject: rows.append({"unit_id": "SUBJECT", "unit_type": "communication_subject", "text": subject})
    if body: rows.append({"unit_id": "BODY", "unit_type": "communication_body", "text": body})
    origin={"product": owner, "artifact_type": artifact_type, "artifact_id": correlation_id or source_message_id or object_id, "audience": audience, "channel": channel, "privacy_domain": privacy_domain, "correlation_id": correlation_id, "source_message_id": source_message_id, "purpose": purpose, "target_language": target, "product_context": product_context, "authority_boundary": authority_boundary}
    if interaction_context:
        origin["interaction_context"] = interaction_context
    semantic, receipt = register_product_source(state_root=Path(dio_root) / "state" / "lingua", object_id=object_id, source_version=source_version, source_language=source_language, source_rows=rows, origin=origin, domain="DIO governed communication")
    lane = (semantic.get("translations") or {}).get(target) if target != source_language else None
    selected_text, selected_subject, translation_state = body, subject, "source_language"
    if target != source_language:
        translation_state = "translation_review_required"
        if lane and str(lane.get("status") or "").casefold() in APPROVED_TRANSLATION_STATES:
            units = {str(row.get("unit_id")): row for row in lane.get("units") or []}; current = {str(row.get("unit_id")): row for row in semantic.get("source", {}).get("units") or []}; usable = True
            for unit_id, source_row in current.items():
                translated = units.get(unit_id)
                if not translated or translated.get("source_hash") != source_row.get("source_hash") or str(translated.get("status") or "").casefold() not in APPROVED_TRANSLATION_STATES:
                    usable = False; break
            if usable:
                selected_subject = str((units.get("SUBJECT") or {}).get("target_text") or subject); selected_text = str((units.get("BODY") or {}).get("target_text") or body); translation_state = "approved_translation"
    return {"schema": "dio.lingua.communication_receipt.v1", "object_id": object_id, "source_document_hash": receipt["source_document_hash"], "object_path": receipt["object_path"], "owner": owner, "artifact_type": artifact_type, "channel": channel, "source_language": source_language, "target_language": target, "translation_state": translation_state, "selected_subject": selected_subject, "selected_text": selected_text, "interaction_context": interaction_context, "semantic_lineage_created": True, "external_action_executed": False, "publication_authorized": False, "send_authorized": False, "authority_created": False, "authority_boundary": authority_boundary}

def communication_manifest(receipt: dict[str, Any]) -> str:
    payload = {"object_id": receipt.get("object_id"), "source_document_hash": receipt.get("source_document_hash"), "owner": receipt.get("owner"), "channel": receipt.get("channel"), "translation_state": receipt.get("translation_state")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
