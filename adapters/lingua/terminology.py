"""Explicit machine-proposed terminology profiles; never approval authority."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from adapters.lingua.lifecycle import digest_text


def prepare_translation_inputs(
    request: dict[str, Any], source: str
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    supplied = list(request.get("preferred_terms") or [])
    profile_id = str(request.get("lingua_terminology_profile") or "")
    receipt = {
        "profile_id": profile_id or None,
        "source_digest": digest_text(source),
        "human_approved": False,
        "applied_terms": [],
        "source_normalizations": [],
    }
    if not profile_id:
        return source, supplied, receipt
    if profile_id != "professional_af_v1":
        raise ValueError("Unknown Lingua terminology profile: " + profile_id)
    if (request["source_language"], request["target_language"]) != (
        "English",
        "Afrikaans",
    ):
        raise ValueError("professional_af_v1 supports English to Afrikaans only")
    profile = json.loads(
        Path(__file__).with_name("professional_af_v1.json").read_text()
    )
    normalized = source
    # Correct a possessive contraction only after a completed business action.
    # No general it's→its replacement; e.g. "it's review time" stays untouched.
    pattern = re.compile(
        r"\b(has|have|had)\s+(completed|submitted|finalised|approved|revised|updated)\s+it['’]s\s+(?=(?:review|report|findings|budget|assessment)\b)",
        re.I,
    )
    normalized = pattern.sub(
        lambda match: re.sub(r"it['’]s", "its", match.group(), flags=re.I), normalized
    )
    if normalized != source:
        receipt["source_normalizations"].append(
            {
                "rule": "completed_action_possessive",
                "before": source,
                "after": normalized,
                "provenance": "machine_proposed_review_required",
            }
        )
    authoritative_sources = [
        str(term.get("source") or term.get("source_term") or "").casefold()
        for term in supplied
    ]
    terms = list(supplied)
    for entry in profile["terms"]:
        term_source = entry["source"]
        if any(
            s and (s in term_source.casefold() or term_source.casefold() in s)
            for s in authoritative_sources
        ):
            continue
        if re.search(
            r"(?<!\w)" + re.escape(term_source) + r"(?!\w)", normalized, flags=re.I
        ):
            term = {**entry, "provenance": "machine_proposed_review_required"}
            terms.append(term)
            receipt["applied_terms"].append(term)
    receipt["normalized_source_digest"] = digest_text(normalized)
    receipt["profile_version"] = profile["version"]
    return normalized, terms, receipt
