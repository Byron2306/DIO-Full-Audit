from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "dio.phase11_1.evidence_reconciliation.v1"
STOP = {"the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "by", "is", "are", "be", "shall", "must", "with", "from", "this", "that"}
NEGATIVE = ("expired", "failed", "failure", "late", "unsigned", "not signed", "not accepted", "rejected", "defect", "overdue", "non-compliant")


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2 and token not in STOP}


def _json_values(value: Any, prefix: str = "") -> list[str]:
    rows: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.append(f"{prefix}{key}: {item}" if not isinstance(item, (dict, list)) else f"{prefix}{key}")
            rows.extend(_json_values(item, f"{prefix}{key}."))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_json_values(item, prefix))
    return rows


def _signals(text: str, *, now: str) -> tuple[list[str], str, str]:
    lower = text.lower()
    signals: list[str] = []
    for label, patterns in {
        "UNSIGNED": ("unsigned", "signed: false", '"signed": false'),
        "EXPIRED": ("expired", "expiry", "expiration"),
        "LATE_NOTICE": ("late", "30 hours", "thirty hours", "after 24 hours"),
        "FAILED_INSPECTION": ("failed inspection", "inspection: failed", '"inspection_status": "failed"', "remediation required"),
        "PROVISIONAL_ACCEPTANCE": ("provisional acceptance", "final_acceptance: false", '"final_acceptance": false'),
    }.items():
        if any(pattern in lower for pattern in patterns):
            signals.append(label)
    current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    dated = [datetime.fromisoformat(x + "T00:00:00+00:00") for x in re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", text)]
    expired = "EXPIRED" in signals or any(date < current and re.search(r"(?:expir|valid.{0,20})(?:\D{0,20})" + re.escape(date.date().isoformat()), lower) for date in dated)
    freshness = "expired" if expired else "unknown"
    relation = "contradicts" if signals or any(word in lower for word in NEGATIVE) else "supports"
    return signals, freshness, relation


def _targets(text: str, clause_count: int) -> list[int]:
    found: set[int] = set()
    patterns = (
        r"target[_ ]clause\s*[:=#-]?\s*(\d+)",
        r"(?:contract\s+)?clause\s*[:=#-]?\s*(\d+)",
        r"obligation\s*[:=#-]?\s*(\d+)",
    )
    for pattern in patterns:
        found.update(int(value) for value in re.findall(pattern, text, re.I) if 1 <= int(value) <= clause_count)
    return sorted(found)


def reconcile_evidence(manifest: dict[str, Any], source: dict[str, Any], *, now: str, output_path: Path | None = None) -> dict[str, Any]:
    clauses = list(source.get("clauses") or [])
    clause_tokens = [_tokens(str(row.get("text") or "")) for row in clauses]
    mappings: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for attachment in manifest.get("attachments") or []:
        if attachment.get("role") != "evidence":
            continue
        text = str(attachment.get("extracted_text") or "")
        if text.lstrip().startswith(("{", "[")):
            try:
                text += "\n" + "\n".join(_json_values(json.loads(text)))
            except json.JSONDecodeError:
                pass
        explicit = _targets(text, len(clauses))
        basis: list[str] = []
        ordinals = explicit
        if explicit:
            basis.append("explicit_clause_reference")
        else:
            tokens = _tokens(text)
            scored = [(len(tokens & wanted), index + 1) for index, wanted in enumerate(clause_tokens)]
            best = max((score for score, _ in scored), default=0)
            ordinals = [ordinal for score, ordinal in scored if score == best and score >= 2][:2]
            if ordinals:
                basis.append(f"lexical_overlap:{best}")
        signals, freshness, relation = _signals(text, now=now)
        if not ordinals:
            unresolved.append(str(attachment["attachment_id"]))
        mappings.append({
            "attachment_id": attachment["attachment_id"],
            "filename": attachment["filename"],
            "extraction_state": attachment["extraction_state"],
            "target_obligation_ordinals": ordinals,
            "target_locators": [str(clauses[index - 1]["clause_id"]) for index in ordinals],
            "relation": relation,
            "observed_signals": signals,
            "confidence_basis": basis or ["unresolved_no_confident_match"],
            "trust_state": "captured_untrusted",
            "freshness_state": freshness,
            "human_gate": "NEEDS_YOU",
            "automatic_acceptance": False,
        })
    payload = {
        "schema": SCHEMA,
        "source_ref": source.get("source_ref"),
        "mappings": mappings,
        "unresolved_attachment_ids": unresolved,
        "fanout_guard": "PASS" if all(len(row["target_locators"]) < len(clauses) or len(clauses) <= 1 for row in mappings) else "FAIL",
        "authority_created": False,
        "human_gate": "NEEDS_YOU",
    }
    payload["fingerprint"] = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows = "".join(
            "<tr>"
            f"<td><strong>{html.escape(row['filename'])}</strong><br><code>{html.escape(row['attachment_id'])}</code></td>"
            f"<td>{html.escape(', '.join(row['target_locators']) or 'Unresolved')}</td>"
            f"<td><span class='{html.escape(row['relation'])}'>{html.escape(row['relation'].upper())}</span></td>"
            f"<td>{html.escape(', '.join(row['observed_signals']) or 'No deterministic warning signal')}</td>"
            f"<td>{html.escape(row['freshness_state'])}</td>"
            f"<td>{html.escape(', '.join(row['confidence_basis']))}</td>"
            "</tr>" for row in mappings
        )
        page = f"""<!doctype html><html><head><meta charset='utf-8'><title>Evidence Reconciliation Register</title>
<style>body{{font:15px/1.5 system-ui;margin:0;background:#f4f0e8;color:#17221d}}main{{max-width:1180px;margin:36px auto;background:white;padding:34px;border-top:7px solid #123f32;box-shadow:0 8px 35px #0002}}h1{{margin:0}}.kicker{{color:#8b5c1d;text-transform:uppercase;letter-spacing:.12em;font-weight:700}}table{{border-collapse:collapse;width:100%;margin-top:24px}}th,td{{border-bottom:1px solid #d8d5cb;text-align:left;vertical-align:top;padding:12px}}th{{background:#123f32;color:white}}.contradicts{{color:#9c251f;font-weight:800}}.supports{{color:#226b4d;font-weight:800}}code{{font-size:11px}}.gate{{margin-top:24px;padding:16px;background:#fff4dc;border-left:5px solid #c47b16}}</style></head>
<body><main><div class='kicker'>DIO Phase 11.1.1</div><h1>Evidence Reconciliation Register</h1><p>Deterministic candidate mapping only. Nothing in this register establishes fulfilment, acceptance, waiver, legal opinion, or external release.</p>
<table><thead><tr><th>Evidence</th><th>Clause locator</th><th>Candidate relation</th><th>Observed signals</th><th>Freshness</th><th>Mapping basis</th></tr></thead><tbody>{rows}</tbody></table>
<div class='gate'><strong>Human decision required.</strong> {len(unresolved)} attachment(s) remain unresolved. External release: REFUSE.</div></main></body></html>"""
        output_path.with_suffix(".html").write_text(page, encoding="utf-8")
    return payload
