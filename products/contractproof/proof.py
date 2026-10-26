from __future__ import annotations

import hashlib
import html
import json
import textwrap
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape


PROVIDER_ID = "contractproof_proof_pack_v1"
PROOF_SCHEMA = "dio.contractproof.proof_manifest.v1"
REQUIRED_ARTIFACT_TYPES = ("JSON", "DOCX", "PDF", "HTML", "proof_room_manifest")
STATUS_ORDER = ("CONTESTED", "EXPIRED", "MISSING", "PARTIAL", "NEEDS_REVIEW", "NOT_YET_DUE", "SATISFIED")
STATUS_LABELS = {
    "SATISFIED": "Evidence present",
    "MISSING": "Evidence missing",
    "PARTIAL": "Partially evidenced",
    "EXPIRED": "Expired",
    "NOT_YET_DUE": "Not yet due",
    "NEEDS_REVIEW": "Human review required",
    "CONTESTED": "Contested",
}
STATUS_COLOURS = {
    "SATISFIED": "1F7A4D", "MISSING": "B42318", "PARTIAL": "B56A00", "EXPIRED": "8A1C1C",
    "NOT_YET_DUE": "3566A8", "NEEDS_REVIEW": "6B4DA0", "CONTESTED": "9B2C5A",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_bytes(path: Path, body: bytes) -> str:
    path.write_bytes(body)
    return _sha256_bytes(body)


def _write_json(path: Path, payload: Any) -> str:
    return _write_bytes(path, (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))


def _semantic_pack(
    case: dict[str, Any], obligation_bundle: dict[str, Any], sufficiency: dict[str, Any],
    projection_receipt: dict[str, Any], review_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_context = review_context or {}
    source_clauses = {str(row.get("clause_id")): row for row in review_context.get("source_clauses") or []}
    obligations = obligation_bundle.get("obligations") or []
    evaluations = {str(row["obligation_id"]): row for row in obligation_bundle.get("evaluations") or []}
    requirement_map = projection_receipt.get("requirement_map") or {}
    requirements = {str(row["requirement_id"]): row for row in case.get("requirements") or []}
    ledger = []
    for obligation in obligations:
        obligation_id = str(obligation["obligation_id"])
        requirement_id = requirement_map.get(obligation_id)
        requirement = requirements.get(str(requirement_id)) or {}
        evaluation = evaluations.get(obligation_id) or {}
        clause = source_clauses.get(str((obligation.get("source") or {}).get("locator"))) or {}
        ledger.append({
            "obligation_id": obligation_id, "requirement_id": requirement_id,
            "source_locator": (obligation.get("source") or {}).get("locator"),
            "statement": obligation.get("statement"), "responsible_party": obligation.get("responsible_party"),
            "due_at": obligation.get("due_at"), "expires_at": obligation.get("expires_at"),
            "status": obligation.get("status"), "status_basis": obligation.get("status_basis") or [],
            "requirement_state": requirement.get("state"), "evidence_ids": list(requirement.get("evidence_ids") or []),
            "human_gate": evaluation.get("human_gate", "NEEDS_YOU"),
            "relative_deadline_rule": clause.get("relative_deadline"),
        })
    evidence_map = [{
        "evidence_id": row["evidence_id"], "kind": row["kind"], "source_ref": row["source_ref"], "sha256": row.get("sha256"),
        "authority_grade": row["authority_grade"], "trust_state": row["trust_state"], "freshness_state": row["freshness_state"],
        "supports_requirement_ids": list(row.get("supports_requirement_ids") or []),
        "supports_claim_ids": list(row.get("supports_claim_ids") or []),
        "contradicts_claim_ids": list(row.get("contradicts_claim_ids") or []),
    } for row in case.get("evidence") or []]
    missing = [row for row in obligation_bundle.get("evaluations") or [] if row.get("status") in {"PARTIAL", "MISSING", "EXPIRED", "NOT_YET_DUE", "NEEDS_REVIEW"}]
    contested = [row for row in obligation_bundle.get("evaluations") or [] if row.get("status") == "CONTESTED"]
    return {
        "schema": "dio.contractproof.evidence_pack.v1", "product_id": "dio_contractproof", "case_id": case["case_id"],
        "engagement": review_context.get("engagement") or case.get("scope") or {}, "requirement_or_obligation_ledger": ledger,
        "evidence_map": evidence_map, "missing_evidence_register": missing,
        "contested_state_register": contested, "deadline_register": obligation_bundle.get("deadlines") or [],
        "human_review_register": {
            "obligation_bundle_gate": obligation_bundle.get("human_gate"), "evidence_sufficiency_gate": sufficiency.get("human_gate"),
            "review_required_obligation_ids": [row["obligation_id"] for row in obligations if row.get("review_required") is True],
            "fulfilment_judgement": "NEEDS_YOU", "disclosure_judgement": "NEEDS_YOU", "external_release": "REFUSE",
        },
        "evidence_reconciliation_register": review_context.get("evidence_reconciliation_register") or {
            "schema": "dio.phase11_1.evidence_reconciliation.v1", "mappings": [],
            "unresolved_attachment_ids": [], "fanout_guard": "NOT_APPLICABLE", "human_gate": "NEEDS_YOU",
        },
        "provenance_manifest": {
            "case_id": case["case_id"], "obligation_source": obligation_bundle.get("source"),
            "obligation_bundle_fingerprint": obligation_bundle["fingerprint"], "projection_receipt": projection_receipt,
            "event_refs": list(case.get("event_refs") or []), "authority_created": False, "external_effects": False,
        },
    }


def _validate_required_sections(pack: dict[str, Any], required_sections: list[str]) -> None:
    missing = [section for section in required_sections if section not in pack]
    if missing:
        raise ValueError(f"ContractProof evidence pack missing output-profile sections: {missing}")


def _date(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if text else "Not specified"


def _basis(row: dict[str, Any]) -> str:
    values = row.get("status_basis") or []
    return "; ".join(str(value).replace("_", " ") for value in values) or "No automated basis recorded; human review is required."


def _presentation(pack: dict[str, Any]) -> dict[str, Any]:
    ledger = list(pack["requirement_or_obligation_ledger"])
    counts = Counter(str(row.get("status") or "NEEDS_REVIEW") for row in ledger)
    attention = [row for row in ledger if row.get("status") in {"CONTESTED", "EXPIRED", "MISSING", "PARTIAL", "NEEDS_REVIEW"}]
    deadlines = sorted(pack["deadline_register"], key=lambda row: str(row.get("due_at") or "9999"))
    evidence = list(pack["evidence_map"])
    reconciliation = pack.get("evidence_reconciliation_register") or {}
    mappings = list(reconciliation.get("mappings") or [])
    summary_parts = []
    for status in STATUS_ORDER:
        if counts[status]:
            summary_parts.append(f"{counts[status]} {STATUS_LABELS[status].lower()}")
    title = str((pack.get("engagement") or {}).get("title") or "ContractProof Evidence Review")
    purpose = str((pack.get("engagement") or {}).get("review_purpose") or "Review contractual obligations and the evidence presently available for human assessment.")
    return {
        "title": title, "subtitle": "Evidence readiness and obligation review", "case_id": pack["case_id"], "purpose": purpose,
        "summary": ", ".join(summary_parts) if summary_parts else "No obligations were available for assessment.",
        "counts": counts, "ledger": ledger, "attention": attention, "deadlines": deadlines, "evidence": evidence,
        "review": pack["human_review_register"], "provenance": pack["provenance_manifest"],
        "reconciliation": reconciliation, "mappings": mappings,
    }


def _render_html(pack: dict[str, Any], required_sections: list[str]) -> bytes:
    view = _presentation(pack)
    def esc(value: Any) -> str: return html.escape(str(value or ""))
    cards = "".join(
        f'<div class="card"><strong>{view["counts"][status]}</strong><span>{esc(STATUS_LABELS[status])}</span></div>'
        for status in STATUS_ORDER if view["counts"][status]
    ) or '<div class="card"><strong>0</strong><span>No obligations</span></div>'
    rows = "".join(
        "<tr>" +
        f'<td><span class="badge s-{esc(row.get("status"))}">{esc(STATUS_LABELS.get(str(row.get("status")), row.get("status")))}</span></td>' +
        f'<td><strong>{esc(row.get("source_locator") or "Unlocated")}</strong><br>{esc(row.get("statement"))}</td>' +
        f'<td>{esc(str(row.get("responsible_party") or "Unspecified").title())}</td>' +
        f'<td>{esc(_date(row.get("due_at") or row.get("expires_at")))}</td>' +
        f'<td>{esc(_basis(row))}</td></tr>' for row in view["ledger"]
    )
    actions = "".join(
        f'<li><strong>{esc(STATUS_LABELS.get(str(row.get("status")), row.get("status")))}</strong> - '
        f'{esc(row.get("statement"))}<br><span>{esc(_basis(row))}</span></li>' for row in view["attention"]
    ) or "<li>No blocking evidence gap was automatically identified. Human review remains required.</li>"
    deadline_rows = "".join(
        f'<tr><td>{esc(_date(row.get("due_at")))}</td><td>{esc(str(row.get("kind") or "deadline").replace("_", " ").title())}</td>'
        f'<td>{esc(str(row.get("state") or "unknown").replace("_", " ").title())}</td><td>{esc(row.get("obligation_id"))}</td></tr>'
        for row in view["deadlines"]
    ) or '<tr><td colspan="4">No explicit deadlines were supplied.</td></tr>'
    evidence_rows = "".join(
        f'<tr><td>{esc(Path(str(row.get("source_ref") or "evidence")).name)}</td><td>{esc(row.get("trust_state"))}</td>'
        f'<td>{esc(row.get("freshness_state"))}</td><td>{len(row.get("supports_requirement_ids") or [])}</td></tr>'
        for row in view["evidence"]
    ) or '<tr><td colspan="4">No evidence records were supplied. This is a gap, not a finding of non-fulfilment.</td></tr>'
    reconciliation_rows = "".join(
        "<tr>" +
        f'<td><strong>{esc(row.get("filename"))}</strong></td>' +
        f'<td>{esc(", ".join(row.get("target_locators") or []) or "Unresolved")}</td>' +
        f'<td><span class="relation {esc(row.get("relation"))}">{esc(str(row.get("relation") or "unresolved").upper())}</span></td>' +
        f'<td>{esc(", ".join(row.get("observed_signals") or []) or "No deterministic warning signal")}</td>' +
        f'<td>{esc(row.get("freshness_state"))}</td>' +
        f'<td>{esc(", ".join(row.get("confidence_basis") or []))}</td></tr>'
        for row in view["mappings"]
    ) or '<tr><td colspan="6">No attachment reconciliation was supplied.</td></tr>'
    source = view["provenance"].get("obligation_source") or {}
    css = """
    :root{--navy:#12233f;--blue:#245a9b;--ink:#172033;--muted:#667085;--line:#d8e0eb;--paper:#fff;--wash:#f5f8fc}
    *{box-sizing:border-box}body{margin:0;background:#eef3f8;color:var(--ink);font:15px/1.55 Arial,sans-serif}
    main{max-width:1080px;margin:28px auto;background:var(--paper);box-shadow:0 12px 40px #12233f22}
    header{padding:52px 58px;background:linear-gradient(135deg,var(--navy),#234d83);color:#fff}header p{max-width:760px;color:#dbe8f7}
    .meta{letter-spacing:.12em;text-transform:uppercase;font-size:12px}.content{padding:38px 58px 60px}h1{font-size:38px;line-height:1.08;margin:.35em 0}h2{color:var(--navy);margin-top:38px;border-bottom:2px solid #dbe5f1;padding-bottom:8px}
    .notice{border-left:5px solid #d89b24;background:#fff8e8;padding:16px 18px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px;margin:20px 0}.card{background:var(--wash);border:1px solid var(--line);border-radius:10px;padding:16px}.card strong{display:block;font-size:27px;color:var(--blue)}.card span{color:var(--muted)}
    table{border-collapse:collapse;width:100%;margin:14px 0 24px}th{background:var(--navy);color:#fff;text-align:left}th,td{padding:11px;border:1px solid var(--line);vertical-align:top}tr:nth-child(even) td{background:#f8fafc}.badge{display:inline-block;border-radius:999px;padding:4px 9px;background:#e9eef5;font-size:12px;font-weight:700}.s-SATISFIED{color:#17633d}.s-MISSING,.s-EXPIRED{color:#a51d16}.s-PARTIAL{color:#9a5600}.s-NEEDS_REVIEW{color:#5d3e91}.s-CONTESTED{color:#8e214f}
    li{margin:10px 0}li span{color:var(--muted)}.relation{font-weight:800}.contradicts{color:#a51d16}.supports{color:#17633d}.unresolved{color:#9a5600}details{margin-top:32px;background:var(--wash);padding:14px 18px}code{overflow-wrap:anywhere}.footer{margin-top:44px;color:var(--muted);font-size:13px}@media print{body{background:#fff}main{box-shadow:none;margin:0}header,.content{padding-left:34px;padding-right:34px}}
    """
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(view['title'])}</title><style>{css}</style></head><body><main>
    <header><div class="meta">DIO ContractProof · Internal review candidate</div><h1>{esc(view['title'])}</h1><p>{esc(view['purpose'])}</p><div>Case {esc(view['case_id'])}</div></header><div class="content">
    <div class="notice"><strong>Human decision required.</strong> This pack supports review. It does not decide contractual fulfilment, provide legal advice, create a waiver, or authorize external release.</div>
    <h2>Executive summary</h2><p>{esc(view['summary']).capitalize()}.</p><div class="cards">{cards}</div>
    <h2>Priority actions</h2><ol>{actions}</ol>
    <h2>Obligation review</h2><table><thead><tr><th>Status</th><th>Obligation</th><th>Owner</th><th>Date</th><th>Review basis</th></tr></thead><tbody>{rows}</tbody></table>
    <h2>Deadline register</h2><table><thead><tr><th>Date</th><th>Type</th><th>State</th><th>Obligation reference</th></tr></thead><tbody>{deadline_rows}</tbody></table>
    <h2>Evidence reconciliation</h2><p>Candidate mappings only. Adverse signals require human assessment and do not establish breach or fulfilment.</p><table><thead><tr><th>Attachment</th><th>Clause</th><th>Candidate relation</th><th>Observed signals</th><th>Freshness</th><th>Basis</th></tr></thead><tbody>{reconciliation_rows}</tbody></table>
    <h2>Evidence inventory</h2><table><thead><tr><th>Evidence record</th><th>Trust state</th><th>Freshness</th><th>Requirements linked</th></tr></thead><tbody>{evidence_rows}</tbody></table>
    <h2>Human review and release</h2><p>Fulfilment judgement: <strong>NEEDS YOU</strong><br>Disclosure judgement: <strong>NEEDS YOU</strong><br>External release: <strong>REFUSE</strong></p>
    <details><summary>Technical provenance</summary><p>Source: {esc(source.get('source_ref') or source.get('source_id') or 'not supplied')}</p><p>Source SHA-256: <code>{esc(source.get('sha256') or 'not supplied')}</code></p><p>Obligation bundle: <code>{esc(view['provenance'].get('obligation_bundle_fingerprint'))}</code></p></details>
    <p class="footer">Generated by DIO ContractProof. JSON and the proof manifest remain the machine-readable integrity companions to this human-first report.</p>
    </div></main></body></html>"""
    return body.encode("utf-8")


def _w_run(text: Any, *, bold: bool = False, colour: str | None = None, size: int | None = None) -> str:
    props = []
    if bold: props.append("<w:b/>")
    if colour: props.append(f'<w:color w:val="{colour}"/>')
    if size: props.append(f'<w:sz w:val="{size}"/>')
    return f"<w:r><w:rPr>{''.join(props)}</w:rPr><w:t xml:space=\"preserve\">{xml_escape(str(text or ''))}</w:t></w:r>"


def _w_p(text: Any = "", *, style: str | None = None, bold: bool = False, colour: str | None = None, size: int | None = None, before: int = 0, after: int = 100) -> str:
    style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
    ppr = f'<w:pPr>{style_xml}<w:spacing w:before="{before}" w:after="{after}"/></w:pPr>'
    return f"<w:p>{ppr}{_w_run(text, bold=bold, colour=colour, size=size)}</w:p>"


def _w_cell(text: Any, *, width: int, bold: bool = False, fill: str | None = None, colour: str | None = None) -> str:
    shade = f'<w:shd w:fill="{fill}"/>' if fill else ""
    return f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}<w:vAlign w:val="center"/></w:tcPr>{_w_p(text,bold=bold,colour=colour,after=40)}</w:tc>'


def _w_table(headers: list[str], rows: list[list[Any]], widths: list[int]) -> str:
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    header = "".join(_w_cell(value, width=widths[i], bold=True, fill="12233F", colour="FFFFFF") for i, value in enumerate(headers))
    body = []
    for row_index, row in enumerate(rows):
        fill = "F5F8FC" if row_index % 2 else None
        body.append("<w:tr>" + "".join(_w_cell(value, width=widths[i], fill=fill) for i, value in enumerate(row)) + "</w:tr>")
    return f'<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblBorders><w:top w:val="single" w:sz="4" w:color="D8E0EB"/><w:left w:val="single" w:sz="4" w:color="D8E0EB"/><w:bottom w:val="single" w:sz="4" w:color="D8E0EB"/><w:right w:val="single" w:sz="4" w:color="D8E0EB"/><w:insideH w:val="single" w:sz="4" w:color="D8E0EB"/><w:insideV w:val="single" w:sz="4" w:color="D8E0EB"/></w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid><w:tr>{header}</w:tr>{"".join(body)}</w:tbl>'


def _docx_bytes(pack: dict[str, Any], required_sections: list[str]) -> bytes:
    view = _presentation(pack)
    parts = [
        _w_p("DIO CONTRACTPROOF", bold=True, colour="245A9B", size=20, after=180),
        _w_p(view["title"], style="Title", after=120), _w_p(view["subtitle"], colour="667085", size=26, after=160),
        _w_p(f"Case {view['case_id']}", bold=True, after=240),
        _w_p(view["purpose"], size=23, after=260),
        _w_p("INTERNAL REVIEW CANDIDATE · HUMAN DECISION REQUIRED", bold=True, colour="9A5600", size=21, after=300),
        _w_p("Executive summary", style="Heading1"), _w_p(view["summary"].capitalize() + "."),
    ]
    summary_rows = [[STATUS_LABELS[status], view["counts"][status]] for status in STATUS_ORDER if view["counts"][status]] or [["No obligations", 0]]
    parts.append(_w_table(["Review state", "Count"], summary_rows, [7200, 2160]))
    parts.extend([_w_p("Priority actions", style="Heading1")])
    if view["attention"]:
        for index, row in enumerate(view["attention"], 1):
            parts.append(_w_p(f"{index}. {STATUS_LABELS.get(str(row.get('status')), row.get('status'))}: {row.get('statement')}", bold=True, after=40))
            parts.append(_w_p(_basis(row), colour="667085", after=120))
    else:
        parts.append(_w_p("No blocking evidence gap was automatically identified. Human review remains required."))
    parts.append(_w_p("Obligation review", style="Heading1"))
    obligation_rows = [[
        STATUS_LABELS.get(str(row.get("status")), row.get("status")),
        f"{row.get('source_locator') or 'Unlocated'} · {row.get('statement')}",
        str(row.get("responsible_party") or "Unspecified").title(),
        _date(row.get("due_at") or row.get("expires_at")) if not row.get("relative_deadline_rule") else str(row.get("relative_deadline_rule")),
    ] for row in view["ledger"]]
    parts.append(_w_table(["Status", "Obligation", "Owner", "Date"], obligation_rows or [["Needs review", "No obligations supplied", "-", "-"]], [1900, 4700, 1400, 1360]))
    parts.append(_w_p("Deadline register", style="Heading1"))
    deadline_rows = [[_date(row.get("due_at")), str(row.get("kind") or "deadline").replace("_", " ").title(), str(row.get("state") or "unknown").replace("_", " ").title()] for row in view["deadlines"]]
    parts.append(_w_table(["Date", "Type", "State"], deadline_rows or [["-", "No explicit deadlines", "Unknown"]], [2500, 3860, 3000]))
    parts.append(_w_p("Evidence reconciliation", style="Heading1"))
    parts.append(_w_p("Candidate mappings only. Adverse signals require human assessment and do not establish breach or fulfilment.", colour="667085"))
    reconciliation_rows = [[
        row.get("filename"),
        ", ".join(row.get("target_locators") or []) or "Unresolved",
        str(row.get("relation") or "unresolved").upper(),
        ", ".join(row.get("observed_signals") or []) or "No warning signal",
        row.get("freshness_state"),
    ] for row in view["mappings"]]
    parts.append(_w_table(["Attachment", "Clause", "Relation", "Signals", "Freshness"], reconciliation_rows or [["No reconciliation supplied", "-", "-", "-", "-"]], [3000, 900, 1300, 2860, 1300]))
    parts.append(_w_p("Evidence inventory", style="Heading1"))
    evidence_rows = [[Path(str(row.get("source_ref") or "evidence")).name, row.get("trust_state"), row.get("freshness_state"), len(row.get("supports_requirement_ids") or [])] for row in view["evidence"]]
    parts.append(_w_table(["Evidence record", "Trust", "Freshness", "Links"], evidence_rows or [["No evidence supplied", "Unknown", "Unknown", 0]], [4300, 2100, 1900, 1060]))
    parts.extend([
        _w_p("Human review and release", style="Heading1"),
        _w_p("Fulfilment judgement: NEEDS YOU", bold=True), _w_p("Disclosure judgement: NEEDS YOU", bold=True),
        _w_p("External release: REFUSE", bold=True, colour="B42318"),
        _w_p("This pack supports review. It does not decide contractual fulfilment, provide legal advice, create a waiver, or authorize external release.", colour="667085"),
    ])
    sect = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/></w:sectPr>'
    document_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + "".join(parts) + sect + '</w:body></w:document>'
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="100" w:line="276" w:lineRule="auto"/></w:pPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:color w:val="12233F"/><w:sz w:val="40"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="300" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="12233F"/><w:sz w:val="28"/></w:rPr></w:style></w:styles>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    doc_rels = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("[Content_Types].xml", content_types), ("_rels/.rels", rels), ("word/document.xml", document_xml), ("word/styles.xml", styles), ("word/_rels/document.xml.rels", doc_rels)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _reportlab_pdf_bytes(pack: dict[str, Any]) -> bytes:
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    rl_config.invariant = 1
    font = "Helvetica"
    bold_font = "Helvetica-Bold"
    regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("DIODejaVu", str(regular)))
        pdfmetrics.registerFont(TTFont("DIODejaVu-Bold", str(bold)))
        font, bold_font = "DIODejaVu", "DIODejaVu-Bold"
    view = _presentation(pack)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("DIOBody", parent=styles["BodyText"], fontName=font, fontSize=8.7, leading=12, textColor=colors.HexColor("#172033"), spaceAfter=4)
    muted = ParagraphStyle("DIOMuted", parent=body, fontSize=7.4, leading=10, textColor=colors.HexColor("#667085"))
    h1 = ParagraphStyle("DIOH1", parent=styles["Heading1"], fontName=bold_font, fontSize=14, leading=17, textColor=colors.HexColor("#12233F"), spaceBefore=10, spaceAfter=6)
    h2 = ParagraphStyle("DIOH2", parent=styles["Heading2"], fontName=bold_font, fontSize=9.2, leading=12, textColor=colors.HexColor("#245A9B"), spaceBefore=5, spaceAfter=2)
    title = ParagraphStyle("DIOTitle", parent=styles["Title"], fontName=bold_font, fontSize=22, leading=26, alignment=TA_LEFT, textColor=colors.HexColor("#12233F"), spaceAfter=5)
    warning = ParagraphStyle("DIOWarning", parent=body, fontName=bold_font, textColor=colors.HexColor("#9A5600"), backColor=colors.HexColor("#FFF8E8"), borderPadding=7, spaceBefore=5, spaceAfter=9)
    table_header = ParagraphStyle("DIOTableHeader", parent=muted, fontName=bold_font, textColor=colors.white)
    story = [Paragraph("DIO CONTRACTPROOF", h2), Paragraph(html.escape(view["title"]), title), Paragraph(html.escape(view["purpose"]), body), Paragraph(f"Case {html.escape(view['case_id'])} - Internal review candidate", muted), Paragraph("HUMAN DECISION REQUIRED - EXTERNAL RELEASE REFUSED", warning)]
    story.extend([Paragraph("Executive summary", h1), Paragraph(html.escape(view["summary"].capitalize()) + ".", body)])
    story.append(Paragraph("Priority actions", h1))
    for index, row in enumerate(view["attention"], 1):
        story.append(KeepTogether([Paragraph(f"{index}. {html.escape(str(row.get('statement') or ''))}", h2), Paragraph(html.escape(_basis(row)), muted)]))
    story.append(Paragraph("Obligation review", h1))
    obligation_data = [[Paragraph("Clause", table_header), Paragraph("Obligation", table_header), Paragraph("Owner", table_header), Paragraph("Deadline", table_header)]]
    for row in view["ledger"]:
        obligation_data.append([
            Paragraph(html.escape(str(row.get("source_locator") or "-")), body), Paragraph(html.escape(str(row.get("statement") or "")), body),
            Paragraph(html.escape(str(row.get("responsible_party") or "Unspecified")), body),
            Paragraph(html.escape(str(row.get("relative_deadline_rule") or _date(row.get("due_at") or row.get("expires_at")))), body),
        ])
    table_style = TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#12233F")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,-1), font), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#D8E0EB")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F8FC")])])
    obligation_table = Table(obligation_data, colWidths=[17*mm, 108*mm, 24*mm, 28*mm], repeatRows=1); obligation_table.setStyle(table_style); story.append(obligation_table)
    story.append(Paragraph("Evidence reconciliation", h1))
    story.append(Paragraph("Candidate mappings only. Adverse signals require human assessment and do not establish breach or fulfilment.", muted))
    rec_data = [[Paragraph(value, table_header) for value in ("Attachment", "Clause", "Relation", "Signals", "Freshness")]]
    for row in view["mappings"]:
        rec_data.append([Paragraph(html.escape(str(value)), body) for value in (
            row.get("filename"), ", ".join(row.get("target_locators") or []) or "Unresolved", str(row.get("relation") or "unresolved").upper(),
            ", ".join(row.get("observed_signals") or []) or "None", row.get("freshness_state"),
        )])
    rec_table = Table(rec_data, colWidths=[58*mm, 18*mm, 27*mm, 51*mm, 23*mm], repeatRows=1); rec_table.setStyle(table_style); story.append(rec_table)
    story.extend([Paragraph("Human review and release", h1), Paragraph("Fulfilment judgement: NEEDS YOU<br/>Disclosure judgement: NEEDS YOU<br/><b>External release: REFUSE</b>", body), Paragraph("This report supports review. It does not decide contractual fulfilment, provide legal advice, create a waiver, or authorize external release.", muted)])
    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState(); canvas.setFont(font, 7); canvas.setFillColor(colors.HexColor("#667085")); canvas.drawString(17*mm, 9*mm, "DIO ContractProof - Human review required"); canvas.drawRightString(A4[0]-17*mm, 9*mm, f"Page {document.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _pdf_bytes(pack: dict[str, Any], required_sections: list[str]) -> bytes:
    try:
        return _reportlab_pdf_bytes(pack)
    except ImportError as exc:
        mappings = ((pack.get("evidence_reconciliation_register") or {}).get("mappings") or [])
        if mappings:
            raise ValueError(
                "Phase 11.1.1 professional PDF rendering requires reportlab; "
                "install it in the storefront interpreter with: python -m pip install reportlab"
            ) from exc
    view = _presentation(pack)
    blocks: list[tuple[str, str]] = [
        ("brand", "DIO CONTRACTPROOF"), ("title", view["title"]), ("sub", f"Case {view['case_id']} · Internal review candidate"),
        ("body", view["purpose"]), ("warning", "HUMAN DECISION REQUIRED · EXTERNAL RELEASE REFUSED"),
        ("h1", "Executive summary"), ("body", view["summary"].capitalize() + "."),
        ("h1", "Priority actions"),
    ]
    if view["attention"]:
        for index, row in enumerate(view["attention"], 1):
            blocks.extend([("h2", f"{index}. {STATUS_LABELS.get(str(row.get('status')), row.get('status'))}"), ("body", str(row.get("statement") or "")), ("muted", _basis(row))])
    else:
        blocks.append(("body", "No blocking evidence gap was automatically identified. Human review remains required."))
    blocks.append(("h1", "Obligation review"))
    for row in view["ledger"]:
        blocks.extend([
            ("h2", f"{STATUS_LABELS.get(str(row.get('status')), row.get('status'))} · Clause {row.get('source_locator') or 'unlocated'}"),
            ("body", str(row.get("statement") or "")),
            ("muted", f"Owner: {str(row.get('responsible_party') or 'unspecified').title()} · Deadline: {row.get('relative_deadline_rule') or _date(row.get('due_at') or row.get('expires_at'))}"),
            ("muted", _basis(row)),
        ])
    blocks.extend([("h1", "Evidence reconciliation"), ("muted", "Candidate mappings only. Human assessment remains required.")])
    for row in view["mappings"]:
        blocks.extend([
            ("h2", f"{row.get('filename')} · {str(row.get('relation') or 'unresolved').upper()}"),
            ("body", f"Clause: {', '.join(row.get('target_locators') or []) or 'Unresolved'} · Signals: {', '.join(row.get('observed_signals') or []) or 'None'}"),
            ("muted", f"Freshness: {row.get('freshness_state')} · Basis: {', '.join(row.get('confidence_basis') or [])}"),
        ])
    blocks.extend([("h1", "Evidence and deadlines"), ("body", f"Evidence records supplied: {len(view['evidence'])}. Explicit deadlines: {len(view['deadlines'])}.")])
    for row in view["deadlines"]:
        blocks.append(("body", f"{_date(row.get('due_at'))} · {str(row.get('kind') or 'deadline').replace('_',' ').title()} · {str(row.get('state') or 'unknown').replace('_',' ').title()}"))
    blocks.extend([
        ("h1", "Human review and release"), ("body", "Fulfilment judgement: NEEDS YOU"),
        ("body", "Disclosure judgement: NEEDS YOU"), ("warning", "External release: REFUSE"),
        ("muted", "This report supports review. It does not decide contractual fulfilment, provide legal advice, create a waiver, or authorize external release."),
    ])
    pages: list[list[tuple[str, str]]] = [[]]
    y = 0
    heights = {"brand": 26, "title": 48, "sub": 28, "h1": 34, "h2": 25, "body": 18, "muted": 16, "warning": 25}
    widths = {"brand": 75, "title": 45, "sub": 75, "h1": 58, "h2": 72, "body": 92, "muted": 100, "warning": 75}
    for kind, text in blocks:
        lines = textwrap.wrap(str(text), width=widths[kind], break_long_words=False, break_on_hyphens=False) or [""]
        need = heights[kind] + max(0, len(lines) - 1) * (14 if kind not in {"title", "h1"} else 18)
        if y + need > 680 and pages[-1]:
            pages.append([]); y = 0
        for line in lines:
            pages[-1].append((kind, line))
        y += need
    page_ids, pairs, next_id = [], [], 5
    for lines in pages:
        page_id, content_id = next_id, next_id + 1; next_id += 2; page_ids.append(page_id); pairs.append((page_id, content_id, lines))
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(page_ids)} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    }
    for page_number, (page_id, content_id, lines) in enumerate(pairs, 1):
        commands = ["0.95 0.97 0.99 rg", "0 770 612 72 re f", "BT", "50 748 Td"]
        current_y = 748
        styles = {
            "brand": (4, 9, "0.14 0.35 0.61", 22), "title": (4, 23, "0.07 0.14 0.25", 30),
            "sub": (3, 10, "0.35 0.40 0.47", 22), "h1": (4, 15, "0.07 0.14 0.25", 28),
            "h2": (4, 11, "0.14 0.35 0.61", 20), "body": (3, 10, "0.09 0.13 0.20", 15),
            "muted": (3, 8, "0.35 0.40 0.47", 13), "warning": (4, 9, "0.66 0.24 0.08", 20),
        }
        previous = None
        for kind, line in lines:
            font, size, colour, leading = styles[kind]
            gap = leading if previous == kind else leading + (6 if kind in {"h1", "h2"} else 2)
            current_y -= gap
            commands.extend(["ET", f"{colour} rg", "BT", f"/F{font} {size} Tf", f"50 {current_y} Td", f"({_pdf_escape(line)}) Tj"])
            previous = kind
        commands.extend(["ET", "0.35 0.40 0.47 rg", "BT", "/F3 8 Tf", f"50 28 Td", f"(DIO ContractProof · Page {page_number} of {len(pages)} · Human review required) Tj", "ET"])
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        objects[content_id] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        objects[page_id] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F3 3 0 R /F4 4 0 R >> >> /Contents {content_id} 0 R >>".encode()
    max_id = next_id - 1; output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offsets = [0] * (max_id + 1)
    for object_id in range(1, max_id + 1):
        offsets[object_id] = len(output); output.extend(f"{object_id} 0 obj\n".encode()); output.extend(objects[object_id]); output.extend(b"\nendobj\n")
    xref = len(output); output.extend(f"xref\n0 {max_id + 1}\n".encode()); output.extend(b"0000000000 65535 f \n")
    for object_id in range(1, max_id + 1): output.extend(f"{offsets[object_id]:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()); return bytes(output)


def _proof_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    return {key: manifest.get(key) for key in ("schema", "provider_id", "product_id", "artifact_type", "case_id", "obligation_bundle_fingerprint", "required_sections", "artifacts", "human_gate", "authority_created", "execution_performed", "external_release")}


def compile_portable_room(
    case: dict[str, Any], obligation_bundle: dict[str, Any], sufficiency: dict[str, Any],
    projection_receipt: dict[str, Any], output_dir: Path, *, required_sections: list[str],
    review_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    pack = _semantic_pack(case, obligation_bundle, sufficiency, projection_receipt, review_context); _validate_required_sections(pack, required_sections)
    rendered = {
        "JSON": ("EVIDENCE_PACK.json", (json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()),
        "HTML": ("EVIDENCE_PACK.html", _render_html(pack, required_sections)),
        "DOCX": ("EVIDENCE_PACK.docx", _docx_bytes(pack, required_sections)),
        "PDF": ("EVIDENCE_PACK.pdf", _pdf_bytes(pack, required_sections)),
    }
    artifacts = []
    for artifact_type in ("JSON", "DOCX", "PDF", "HTML"):
        filename, body = rendered[artifact_type]; artifacts.append({"artifact_type": artifact_type, "filename": filename, "sha256": _write_bytes(output_dir / filename, body)})
    reconciliation = (review_context or {}).get("evidence_reconciliation_register")
    if reconciliation:
        reconciliation_json = (json.dumps(reconciliation, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        artifacts.append({"artifact_type": "JSON", "filename": "EVIDENCE_RECONCILIATION.json", "sha256": _write_bytes(output_dir / "EVIDENCE_RECONCILIATION.json", reconciliation_json)})
        reconciliation_html = output_dir / "EVIDENCE_RECONCILIATION.html"
        if reconciliation_html.is_file():
            artifacts.append({"artifact_type": "HTML", "filename": reconciliation_html.name, "sha256": _sha256_bytes(reconciliation_html.read_bytes())})
    manifest = {
        "schema": PROOF_SCHEMA, "provider_id": PROVIDER_ID, "product_id": "dio_contractproof", "artifact_type": "proof_room_manifest",
        "case_id": case["case_id"], "obligation_bundle_fingerprint": obligation_bundle["fingerprint"], "proof_fingerprint": "",
        "required_sections": list(required_sections), "artifacts": artifacts,
        "human_gate": {"state": "NEEDS_YOU", "reason": "An authorised contract owner controls any disclosure or contractual judgement based on this pack."},
        "authority_created": False, "execution_performed": False, "external_release": False,
    }
    manifest["proof_fingerprint"] = f"sha256:{_sha256_bytes(_canonical(_proof_identity(manifest)).encode())}"
    _write_json(output_dir / "PROOF_MANIFEST.json", manifest); return manifest


def verify_integrity(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve(); manifest = json.loads((output_dir / "PROOF_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != PROOF_SCHEMA or manifest.get("artifact_type") != "proof_room_manifest": raise ValueError("unexpected ContractProof proof manifest identity")
    failures: list[str] = []
    if manifest.get("provider_id") != PROVIDER_ID or manifest.get("product_id") != "dio_contractproof": failures.append("manifest:provider_or_product")
    if (manifest.get("human_gate") or {}).get("state") != "NEEDS_YOU": failures.append("manifest:human_gate")
    if manifest.get("authority_created") is not False or manifest.get("execution_performed") is not False or manifest.get("external_release") is not False: failures.append("manifest:authority_boundary")
    expected = f"sha256:{_sha256_bytes(_canonical(_proof_identity(manifest)).encode())}"
    if manifest.get("proof_fingerprint") != expected: failures.append("manifest:fingerprint")
    observed = {"proof_room_manifest"}
    for artifact in manifest.get("artifacts") or []:
        artifact_type = str(artifact.get("artifact_type") or ""); observed.add(artifact_type); path = output_dir / str(artifact.get("filename") or "")
        if not path.is_file(): failures.append(f"missing:{artifact_type}")
        elif _sha256_bytes(path.read_bytes()) != artifact.get("sha256"): failures.append(f"hash:{artifact_type}")
    failures.extend(f"manifest_missing:{item}" for item in sorted(set(REQUIRED_ARTIFACT_TYPES).difference(observed)))
    return {"schema": "dio.contractproof.integrity_verification.v1", "case_id": manifest.get("case_id"), "proof_fingerprint": manifest.get("proof_fingerprint"), "verified": not failures, "failures": failures, "authority_created": False, "execution_performed": False}


def prepare_disclosure(output_dir: Path) -> dict[str, Any]:
    verification = verify_integrity(output_dir)
    if not verification["verified"]: raise ValueError(f"ContractProof proof pack failed integrity verification: {verification['failures']}")
    return {"schema": "dio.contractproof.disclosure_candidate.v1", "product_id": "dio_contractproof", "case_id": verification["case_id"], "proof_fingerprint": verification["proof_fingerprint"], "state": "INTERNAL_REVIEW_CANDIDATE", "human_gate": {"state": "NEEDS_YOU", "reason": "The internal proof pack requires authorised human review before any disclosure decision."}, "external_release_gate": "REFUSE", "authority_created": False, "release_authority_created": False}
