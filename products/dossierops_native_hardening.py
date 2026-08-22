from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


METADATA_STATE = "metadata_container_not_record_state"
MIXED_RECORD_CLASS = "mixed_agreement_amendment_extract"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def date_key(value: str) -> tuple[int, str]:
    raw = str(value or "").strip()
    for fmt in ("%d %B %Y", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(raw, fmt).strftime("%Y%m%d")), raw
        except ValueError:
            continue
    return 99999999, raw


def _source_text(case_root: Path, row: dict[str, Any]) -> str:
    path = case_root / "CUSTOMER_PACKET" / str(row.get("path") or "")
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def harden_source_manifest(case_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    hardened = dict(payload)
    sources: list[dict[str, Any]] = []
    for raw in payload.get("sources") or []:
        row = dict(raw)
        text = _source_text(case_root, row).casefold()
        if row.get("record_state") != METADATA_STATE:
            if ("agreement" in text or "contract" in text) and "amendment" in text:
                row["record_class"] = MIXED_RECORD_CLASS
        sources.append(row)
    hardened["schema"] = "dio.dossierops.source_manifest.finalized.v1"
    hardened["sources"] = sources
    hardened["classification_hardened"] = True
    return hardened


def expected_classes(statement: str) -> set[str]:
    value = str(statement or "").casefold()
    if "payment" in value or "spreadsheet" in value or "invoice" in value:
        return {"payment_schedule", "financial_record", "invoice"}
    if "email" in value or "correspondence" in value:
        return {"correspondence"}
    if "amendment" in value:
        return {"amendment", MIXED_RECORD_CLASS}
    if "agreement" in value or "contract" in value:
        return {"agreement", MIXED_RECORD_CLASS}
    return set()


def harden_cross_reference(manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    by_path = {str(row.get("path") or ""): dict(row) for row in manifest.get("sources") or []}
    claims: list[dict[str, Any]] = []
    for raw in payload.get("claims") or []:
        row = dict(raw)
        expected = expected_classes(str(row.get("customer_statement") or ""))
        actual: list[dict[str, Any]] = []
        metadata: list[dict[str, Any]] = []
        nonmatching: list[dict[str, Any]] = []
        for original_link in row.get("corroborating_records") or []:
            link = dict(original_link)
            source = by_path.get(str(link.get("path") or ""), {})
            link["record_class"] = source.get("record_class")
            link["record_state"] = source.get("record_state") or link.get("record_state")
            if link.get("record_state") == METADATA_STATE:
                metadata.append(link)
            elif expected and str(link.get("record_class") or "") not in expected:
                nonmatching.append(link)
            else:
                actual.append(link)
        row.pop("corroborating_records", None)
        row["candidate_record_links"] = actual
        row["metadata_mentions"] = metadata
        row["nonmatching_record_mentions"] = nonmatching
        row["corroboration_state"] = "candidate_correlated_record" if actual else "register_only_no_separate_record_matched"
        row["claim_support_determined"] = False
        claims.append(row)
    return {
        "schema": "dio.dossierops.claim_record_cross_reference.finalized.v1",
        "packet_fingerprint": payload.get("packet_fingerprint"),
        "method": "deterministic_token_overlap_navigation_with_record_class_filtering",
        "claim_support_determined": False,
        "claims": claims,
    }


def build_chronology(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in manifest.get("sources") or []:
        level = "metadata_assertion" if source.get("record_state") == METADATA_STATE else "record_text"
        for date in source.get("explicit_dates") or []:
            rows.append({
                "date_as_supplied": str(date),
                "source_level": level,
                "record_id": str(source.get("record_id") or ""),
                "filename": str(source.get("filename") or ""),
                "record_class": str(source.get("record_class") or ""),
                "record_state": str(source.get("record_state") or ""),
                "legal_effect_determined": "false",
            })
    rows.sort(key=lambda row: (date_key(row["date_as_supplied"]), row["source_level"], row["record_id"]))
    return rows


def claim_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("claim_id") or ""): dict(row) for row in payload.get("claims") or []}
