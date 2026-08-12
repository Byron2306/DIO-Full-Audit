from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any


INTAKE_SCHEMA = "dio.contractproof.email_intake.v1"
DATE_FORMATS = ("%d %B %Y", "%d %b %Y")


class ContractProofIntakeError(ValueError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _iso_date(value: str, *, midday: bool) -> str:
    value = " ".join(value.strip().split())
    parsed = None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ContractProofIntakeError(f"unsupported explicit contract date: {value}")
    hour = 12 if midday else 0
    return parsed.replace(hour=hour, tzinfo=timezone.utc).isoformat()


def _message_body(message) -> str:
    part = message.get_body(preferencelist=("plain",))
    if part is None:
        return ""
    try:
        return str(part.get_content()).strip()
    except Exception:
        payload = part.get_payload(decode=True) or b""
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()


def _attachment_text(payload: bytes, filename: str) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractProofIntakeError(f"Phase 5.1 golden intake accepts UTF-8 text attachments only: {filename}") from exc


def _split_contract_clauses(text: str) -> list[tuple[str, str, str]]:
    matches = list(re.finditer(r"(?m)^(?P<locator>\d+\.\d+)\s+(?P<title>[^\n]+)\n", text))
    rows: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        rows.append((match.group("locator"), match.group("title").strip(), body))
    if not rows:
        raise ContractProofIntakeError("contract attachment contains no numbered clauses such as 4.2")
    return rows


def _evidence_requirements(body: str) -> list[str]:
    normalized = body.lower()
    mappings = (
        ("delivery receipt", "delivery_receipt"),
        ("payment receipt", "payment_receipt"),
        ("signed form", "signed_form"),
        ("identity copy", "identity_copy"),
        ("current certificate", "certificate"),
        ("certificate must be retained", "certificate"),
        ("notice receipt", "notice_receipt"),
        ("incident notice", "incident_notice"),
    )
    found: list[str] = []
    for phrase, evidence_kind in mappings:
        if phrase in normalized and evidence_kind not in found:
            found.append(evidence_kind)
    return found


def _obligation_kind(title: str, body: str) -> str:
    value = f"{title} {body}".lower()
    if "report" in value:
        return "reporting"
    if "payment" in value or "invoice" in value:
        return "payment"
    if "onboarding" in value or "dossier" in value:
        return "deliverable"
    if "certificate" in value or "certification" in value:
        return "maintenance"
    if "notice" in value or "notify" in value:
        return "notification"
    return "other"


def _contract_source(payload: bytes, *, filename: str, source_ref: str, message_id: str) -> dict[str, Any]:
    text = _attachment_text(payload, filename)
    effective_match = re.search(r"(?im)^Effective date:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s*$", text)
    effective_at = _iso_date(effective_match.group(1), midday=False) if effective_match else None
    clauses: list[dict[str, Any]] = []
    for locator, title, body in _split_contract_clauses(text):
        statement_match = re.search(r"(?is)\b((?:Supplier|Customer)\s+(?:shall|must)\b.*?)(?:\.|\n|$)", body)
        statement = " ".join((statement_match.group(1) if statement_match else body.splitlines()[0]).split())
        actor_match = re.match(r"(?i)^(Supplier|Customer)\s+(?:shall|must)\b", statement)
        responsible_party = actor_match.group(1).lower() if actor_match else None

        due_match = re.search(r"(?i)(?:no later than|\bby)\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", body)
        expiry_match = re.search(r"(?i)valid through\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", body)
        due_at = _iso_date(due_match.group(1), midday=True) if due_match else None
        expires_at = _iso_date(expiry_match.group(1), midday=True) if expiry_match else None
        evidence_requirements = _evidence_requirements(body)

        row: dict[str, Any] = {
            "clause_id": locator,
            "text": statement + ".",
            "obligation_kind": _obligation_kind(title, body),
            "responsible_party": responsible_party,
            "due_at": due_at,
            "expires_at": expires_at,
            "evidence_requirements": evidence_requirements,
        }
        # Conservative rule: only structured obligations with an explicit temporal
        # anchor and evidence expectation graduate automatically. Other deontic
        # language remains a candidate for human interpretation.
        if responsible_party and evidence_requirements and (due_at or expires_at):
            row["obligation"] = True
        clauses.append(row)

    return {
        "source_id": f"email-{message_id.strip('<>').replace('@', '-')}",
        "source_type": "contract",
        "source_ref": source_ref,
        "sha256": _sha256_bytes(payload),
        "effective_at": effective_at,
        "expires_at": None,
        "clauses": clauses,
    }


def _parse_evidence_headers(text: str, filename: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            if headers:
                break
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = key.strip().lower().replace("-", "_")
        if normalized in {
            "evidence_type", "target_clause", "observed_at", "effective_at", "expires_at",
            "authority_grade", "trust_state", "freshness_state", "relation",
        }:
            headers[normalized] = value.strip()
    required = {"evidence_type", "target_clause"}
    missing = sorted(required.difference(headers))
    if missing:
        raise ContractProofIntakeError(f"evidence attachment {filename} is missing metadata headers: {missing}")
    return headers


def parse_contractproof_email(path: Path) -> dict[str, Any]:
    """Parse a bounded email envelope into ContractProof source/evidence inputs.

    This is a vertical Golden-Proof adapter, not a generic WP08 Intake runtime.
    It accepts one UTF-8 text contract attachment and zero or more UTF-8 text
    evidence attachments. Attachment hashes are computed from the actual bytes.
    """
    path = path.resolve()
    raw_message = path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    message_id = str(message.get("Message-ID") or f"<{_sha256_bytes(raw_message)[:24]}@local>")
    attachments: list[dict[str, Any]] = []
    contract_attachment: dict[str, Any] | None = None
    evidence_records: list[dict[str, Any]] = []

    for part in message.iter_attachments():
        filename = str(part.get_filename() or "attachment.bin")
        payload = part.get_payload(decode=True) or b""
        content_type = str(part.get_content_type() or "application/octet-stream")
        source_ref = f"email://{message_id.strip('<>')}/attachment/{filename}"
        metadata = {
            "filename": filename,
            "content_type": content_type,
            "sha256": _sha256_bytes(payload),
            "source_ref": source_ref,
            "payload": payload,
        }
        if filename.upper().startswith("SERVICE_AGREEMENT"):
            if contract_attachment is not None:
                raise ContractProofIntakeError("golden email must contain exactly one SERVICE_AGREEMENT attachment")
            metadata["role"] = "authoritative_source"
            contract_attachment = metadata
            continue

        metadata["role"] = "evidence"
        text = _attachment_text(payload, filename)
        headers = _parse_evidence_headers(text, filename)
        evidence_records.append({
            "attachment_filename": filename,
            "target_locators": [item.strip() for item in headers["target_clause"].split(",") if item.strip()],
            "evidence_kind": headers["evidence_type"],
            "source_ref": source_ref,
            "sha256": metadata["sha256"],
            "observed_at": headers.get("observed_at"),
            "effective_at": headers.get("effective_at"),
            "expires_at": headers.get("expires_at"),
            "authority_grade": headers.get("authority_grade", "source_backed"),
            "trust_state": headers.get("trust_state", "captured_untrusted"),
            "freshness_state": headers.get("freshness_state", "unknown"),
            "relation": headers.get("relation", "supports"),
        })
        attachments.append(metadata)

    if contract_attachment is None:
        raise ContractProofIntakeError("golden email does not contain SERVICE_AGREEMENT attachment")
    attachments.insert(0, contract_attachment)
    source = _contract_source(
        contract_attachment["payload"],
        filename=contract_attachment["filename"],
        source_ref=contract_attachment["source_ref"],
        message_id=message_id,
    )
    return {
        "schema": INTAKE_SCHEMA,
        "message": {
            "message_id": message_id,
            "from": str(message.get("From") or ""),
            "to": str(message.get("To") or ""),
            "subject": str(message.get("Subject") or ""),
            "date": str(message.get("Date") or ""),
            "body": _message_body(message),
            "sha256": _sha256_bytes(raw_message),
            "source_path": str(path),
        },
        "source": source,
        "evidence_records": evidence_records,
        "attachments": attachments,
        "raw_message": raw_message,
    }


def write_intake_sources(intake: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    """Materialize the inbound envelope and attachments inside the proof room."""
    sources = output_dir.resolve() / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []

    inbound = sources / "INBOUND.eml"
    inbound.write_bytes(intake["raw_message"])
    artifacts.append({
        "artifact_role": "inbound_message",
        "filename": "INBOUND.eml",
        "relative_path": "sources/INBOUND.eml",
        "sha256": _sha256_bytes(intake["raw_message"]),
        "source_ref": str((intake.get("message") or {}).get("message_id") or ""),
    })

    for attachment in intake.get("attachments") or []:
        filename = str(attachment["filename"])
        target = sources / filename
        target.write_bytes(attachment["payload"])
        artifacts.append({
            "artifact_role": attachment["role"],
            "filename": filename,
            "relative_path": f"sources/{filename}",
            "sha256": attachment["sha256"],
            "source_ref": attachment["source_ref"],
        })
    return artifacts


def public_intake_summary(intake: dict[str, Any]) -> dict[str, Any]:
    message = intake.get("message") or {}
    return {
        "schema": INTAKE_SCHEMA,
        "message_id": message.get("message_id"),
        "from": message.get("from"),
        "to": message.get("to"),
        "subject": message.get("subject"),
        "date": message.get("date"),
        "body": message.get("body"),
        "message_sha256": message.get("sha256"),
        "attachment_count": len(intake.get("attachments") or []),
        "attachments": [
            {
                "filename": row["filename"],
                "role": row["role"],
                "content_type": row["content_type"],
                "sha256": row["sha256"],
                "source_ref": row["source_ref"],
            }
            for row in intake.get("attachments") or []
        ],
    }
