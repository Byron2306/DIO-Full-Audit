from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


BUNDLE_SCHEMA = "dio.obligation_bundle.v1"
ENGINE_VERSION = "0.1.0"
CANONICAL_STATES = {
    "SATISFIED",
    "PARTIAL",
    "MISSING",
    "CONTESTED",
    "EXPIRED",
    "NOT_YET_DUE",
    "NEEDS_REVIEW",
}
RESERVED_VERDICTS = {"COMPLIANT", "LEGAL", "VALID", "APPROVED"}
OBLIGATION_KINDS = {
    "deliverable",
    "payment",
    "reporting",
    "notification",
    "approval_prerequisite",
    "maintenance",
    "retention",
    "access",
    "other",
}
SOURCE_TYPES = {"contract", "grant", "policy", "permit", "tender", "standard", "other"}
EVIDENCE_TRUST_STATES = {"captured_untrusted", "trusted_for_review", "rejected", "quarantined"}
EVIDENCE_FRESHNESS_STATES = {"unknown", "current", "stale", "expired"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def require_sha256(value: str) -> str:
    digest = str(value or "").lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("source sha256 must be a 64-character hexadecimal digest")
    return digest


def require_source(source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError("authoritative source must be an object")
    source_id = normalize_space(source.get("source_id"))
    source_ref = normalize_space(source.get("source_ref"))
    source_type = normalize_space(source.get("source_type"))
    if not source_id:
        raise ValueError("authoritative source requires source_id")
    if not source_ref:
        raise ValueError("authoritative source requires source_ref")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"unsupported obligation source_type: {source_type}")
    digest = require_sha256(str(source.get("sha256") or ""))
    clauses = source.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        raise ValueError("authoritative source requires a non-empty clauses list")
    return {
        "source_id": source_id,
        "source_type": source_type,
        "source_ref": source_ref,
        "sha256": digest,
        "effective_at": source.get("effective_at"),
        "expires_at": source.get("expires_at"),
    }
