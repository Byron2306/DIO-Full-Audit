"""Deterministic, provenance-bound capture of customer-stated scope for any DIO product."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any


SCOPE_OBSERVATIONS_SCHEMA = "dio.customer_scope_observations.v1"

_FORMAT_NAMES = (
    "DOCX", "DOC", "PDF", "ODT", "RTF", "TXT", "HTML", "PPTX", "PPT",
    "XLSX", "XLS", "CSV", "JSON", "XML", "SVG", "PNG", "JPEG", "JPG",
    "WEBP", "MP3", "WAV", "FLAC", "OGG", "MP4", "MOV", "WEBM", "SRT",
    "VTT", "EPUB",
)
_COMMON_UNITS = {
    "page", "word", "document", "report", "file", "revision", "student",
    "learner", "essay", "script", "question", "item", "claim", "record",
    "evidence", "evidence item", "case", "customer", "contact", "lead",
    "invoice", "quote", "contract", "clause", "obligation", "source",
    "citation", "reference", "slide", "presentation", "lesson", "unit",
    "worksheet", "assessment", "exam", "memo", "campaign", "asset", "image",
    "video", "audio", "song", "track", "scene", "render", "frame", "minute",
    "hour", "day", "week", "month", "year", "application", "opportunity",
    "grant", "market", "segment", "organization", "organisation", "business",
    "employee", "role", "task", "objective", "standard", "control", "finding",
    "incident", "event", "transaction", "payment", "product", "variant",
    "deliverable", "output", "package", "message", "email", "recipient",
    "channel", "language", "meeting", "workshop", "session", "course",
}
_UNIT_IRREGULAR = {"people": "person", "children": "child", "indices": "index"}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", str(text or "")) if part.strip()]


def _singular(unit: str) -> str:
    value = re.sub(r"\s+", " ", str(unit or "").strip().casefold().replace("_", " "))
    if value in _UNIT_IRREGULAR:
        return _UNIT_IRREGULAR[value]
    words = value.split()
    if words and words[-1].endswith("ies") and len(words[-1]) > 4:
        words[-1] = words[-1][:-3] + "y"
    elif words and words[-1].endswith("s") and not words[-1].endswith(("ss", "us", "is")):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def _unit_from_tail(tail: str, recognized_units: set[str]) -> str:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z_-]*", tail.casefold())
    tokens = [token for token in tokens if token not in {"each", "total", "combined", "overall", "approximately", "about"}]
    if not tokens:
        return "unspecified"
    normalized = " ".join(tokens).replace("_", " ")
    candidates = sorted(recognized_units, key=lambda x: (-len(x.split()), -len(x)))
    for candidate in candidates:
        forms = {candidate, candidate + "s", candidate.replace("y", "ies") if candidate.endswith("y") else candidate + "s"}
        for form in forms:
            pattern = r"(?<![a-z])" + re.escape(form).replace(r"\ ", r"[ _-]+") + r"(?![a-z])"
            if re.search(pattern, normalized):
                return candidate
    # Keep the observed head noun, rather than guessing a product-specific unit.
    return _singular(tokens[-1])


def _quantity_observations(text: str, recognized_units: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?<![\w.])(?P<low>\d+)\s*(?:(?:to|[-–—])\s*(?P<high>\d+)\s*)?"
        r"(?P<tail>[A-Za-z][A-Za-z0-9_-]*(?:\s+[A-Za-z][A-Za-z0-9_-]*){0,4})"
    )
    for match in pattern.finditer(str(text or "")):
        raw_tail = match.group("tail")
        unit = _unit_from_tail(raw_tail, recognized_units)
        before = str(text[max(0, match.start() - 72):match.start()]).casefold()
        if re.search(r"\b(?:maximum|max\.?|at most|up to|no more than|not exceeding|cap(?:ped)? at)\b", before):
            qualifier = "maximum"
        elif re.search(r"\b(?:approximately|approx\.?|about|around|roughly)\b", before):
            qualifier = "approximate"
        elif re.search(r"\b(?:minimum|min\.?|at least|no fewer than)\b", before):
            qualifier = "minimum"
        else:
            qualifier = "customer_stated"
        low = int(match.group("low"))
        high_text = match.group("high")
        value: int | dict[str, int] = {"minimum": low, "maximum": int(high_text)} if high_text else low
        raw = str(text[match.start():match.end()]).strip()
        if not raw or not unit:
            continue
        rows.append({"kind": "quantity", "value": value, "unit": unit, "qualifier": qualifier, "source_text": raw})
    # The two parsers can encounter the same numeric span only once; preserve
    # independently stated caps/ranges because their qualifiers carry meaning.
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (json_key(row["value"]), row["unit"], row["qualifier"])
        unique[key] = row
    return list(unique.values())


def json_key(value: Any) -> str:
    if isinstance(value, dict):
        return ",".join(f"{key}:{value[key]}" for key in sorted(value))
    return str(value)


def extract_customer_scope_observations(
    text: str,
    *,
    source_message_id: str | None = None,
    product_id: str | None = None,
    recognized_units: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Extract literal scope claims without treating them as verified facts."""
    message = str(text or "").strip()
    if not message:
        return {"schema": SCOPE_OBSERVATIONS_SCHEMA, "message_sha256": _digest(""), "facts": []}
    known = {_singular(unit) for unit in _COMMON_UNITS | set(map(str, recognized_units)) if str(unit).strip()}
    sentences = _sentences(message)
    quantities = _quantity_observations(message, known)
    formats: list[dict[str, str]] = []
    for match in re.finditer(r"\b(" + "|".join(map(re.escape, sorted(_FORMAT_NAMES, key=len, reverse=True))) + r")\b", message, re.I):
        before = message[max(0, match.start() - 48):match.start()].casefold()
        preference = "optional" if re.search(r"\b(?:optional|optionally|if requested|if useful)\b", before) else "required_or_requested"
        formats.append({"format": match.group(1).upper(), "preference": preference, "source_text": match.group(0)})
    deduped_formats = list({(row["format"], row["preference"]): row for row in formats}.values())
    exclusions: list[dict[str, str]] = []
    for sentence in sentences:
        match = re.search(r"\b(?:exclude|excluding|do not include|must not include|without)\s+(.+)$", sentence, re.I)
        if match:
            tail = re.sub(r"[.!?]+$", "", match.group(1)).strip()
            for item in re.split(r",|\band\b|\bor\b", tail, flags=re.I):
                item = re.sub(r"^(?:any|all|the)\s+", "", item.strip(), flags=re.I)
                if item:
                    exclusions.append({"item": item, "source_text": sentence})
    requirements = [
        {"statement": sentence, "source_text": sentence}
        for sentence in sentences
        if re.search(r"\b(?:require|requires|required|need|needs|want|wants|would like|must|should include|with consistent|including)\b", sentence, re.I)
    ]
    deadlines = [
        {"statement": sentence, "source_text": sentence}
        for sentence in sentences
        if re.search(r"\b(?:deadline|due date|turnaround|delivery schedule|schedule|fixed date)\b", sentence, re.I)
    ]
    data_classification = [
        {"statement": sentence, "source_text": sentence}
        for sentence in sentences
        if re.search(r"\b(?:synthetic|synthetically generated|test material|not confidential|confidential|anonymi[sz]ed|personal data|public data)\b", sentence, re.I)
    ]
    outcomes = [
        sentence for sentence in sentences
        if re.search(r"\b(?:i need|i require|i want|i would like|i'd like|we need|we require|we want|please prepare|please create|please provide)\b", sentence, re.I)
    ]
    return {
        "schema": SCOPE_OBSERVATIONS_SCHEMA,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "product_id": product_id,
        "source_message_id": str(source_message_id or "").strip() or None,
        "message_sha256": _digest(message),
        "provenance": "customer_stated_unverified",
        "requested_outcome_statements": outcomes,
        "quantities": quantities,
        "requested_formats": deduped_formats,
        "requirements": requirements,
        "exclusions": exclusions,
        "deadline_statements": deadlines,
        "data_classification_statements": data_classification,
        "authority_created": False,
        "external_effects": False,
    }
