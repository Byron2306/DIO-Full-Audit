"""Guided offline editorial review for Report & Pitch customer packages."""
from __future__ import annotations

import csv
import hashlib
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


FIXED_FIELDS = (
    "item_id", "item_type", "source_or_claim_refs", "source_sha256", "source_locator",
    "exact_source_text", "machine_state",
)
REVIEW_FIELDS = (
    "support_decision", "source_authenticity_checked", "rights_privacy_attribution_checked",
    "editorial_decision", "revision_reference", "rationale", "reviewer_name", "reviewer_role",
    "reviewed_at_iso8601",
)
ALLOWED = {
    "support_decision": {"SUPPORTED", "NOT_SUPPORTED", "UNRESOLVED"},
    "source_authenticity_checked": {"VERIFIED", "NOT_VERIFIED", "UNAVAILABLE"},
    "rights_privacy_attribution_checked": {"CLEARED", "ISSUE_FOUND", "UNKNOWN"},
    "editorial_decision": {"APPROVED_FOR_INTERNAL_REVIEW", "REVISE", "REJECT"},
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def validate_report_pitch_review(template_path: Path, submitted_path: Path) -> dict[str, Any]:
    """Validate a returned review CSV against the generated, immutable source rows."""
    template_fields, template = _read_csv(template_path)
    observed_fields, observed = _read_csv(submitted_path)
    issues: list[dict[str, Any]] = []
    required = set(template_fields) | set(REVIEW_FIELDS)
    for field in sorted(required - set(observed_fields)):
        issues.append({"code": "REQUIRED_COLUMN_MISSING", "field": field})
    expected = {str(row.get("item_id") or ""): row for row in template}
    observed_by_id: dict[str, dict[str, str]] = {}
    for line, row in enumerate(observed, 2):
        item_id = str(row.get("item_id") or "").strip()
        if not item_id or item_id not in expected:
            issues.append({"line": line, "code": "UNKNOWN_OR_EMPTY_ITEM_ID", "item_id": item_id})
            continue
        if item_id in observed_by_id:
            issues.append({"line": line, "code": "DUPLICATE_ITEM_ID", "item_id": item_id})
            continue
        observed_by_id[item_id] = row
        source = expected[item_id]
        for field in FIXED_FIELDS:
            if str(row.get(field) or "") != str(source.get(field) or ""):
                issues.append({"line": line, "code": "SOURCE_BOUND_FIELD_CHANGED", "item_id": item_id, "field": field})
        for field, allowed in ALLOWED.items():
            value = str(row.get(field) or "").strip().upper()
            if value not in allowed:
                issues.append({"line": line, "code": "DECISION_INCOMPLETE_OR_INVALID", "item_id": item_id, "field": field})
        for field in ("rationale", "reviewer_name", "reviewer_role", "reviewed_at_iso8601"):
            if not str(row.get(field) or "").strip():
                issues.append({"line": line, "code": "REVIEWER_FIELD_REQUIRED", "item_id": item_id, "field": field})
        stamp = str(row.get("reviewed_at_iso8601") or "").strip()
        if stamp:
            try:
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise ValueError("timezone required")
            except ValueError:
                issues.append({"line": line, "code": "REVIEW_TIME_MUST_INCLUDE_UTC_OFFSET", "item_id": item_id})
        if str(row.get("editorial_decision") or "").strip().upper() == "APPROVED_FOR_INTERNAL_REVIEW":
            for field in ("support_decision", "source_authenticity_checked", "rights_privacy_attribution_checked"):
                if str(row.get(field) or "").strip().upper() not in {"SUPPORTED", "VERIFIED", "CLEARED"}:
                    issues.append({"line": line, "code": "INTERNAL_REVIEW_APPROVAL_REQUIRES_CLEAR_REVIEW_FIELDS", "item_id": item_id, "field": field})
    for item_id in sorted(set(expected) - set(observed_by_id)):
        issues.append({"code": "SOURCE_ROW_MISSING", "item_id": item_id})
    all_approved = bool(template) and not issues and all(
        str(row.get("editorial_decision") or "").strip().upper() == "APPROVED_FOR_INTERNAL_REVIEW"
        for row in observed
    )
    state = (
        "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED" if issues else
        "REVIEW_COMPLETE_PENDING_SEPARATE_RELEASE_AUTHORITY" if all_approved else
        "REVIEW_COMPLETE_WITH_HOLDS"
    )
    return {
        "schema": "dio.report_pitch.editorial_review_validation.v1",
        "state": state,
        "template_sha256": _sha(template_path),
        "submitted_csv_sha256": _sha(submitted_path),
        "source_item_count": len(expected), "review_row_count": len(observed),
        "issues": issues, "publication_authorized": False,
        "authority_created": False, "external_effects": False,
        "claim_boundary": "This validator confirms reviewer completeness and preserves generated source fields. It does not verify source truth, rights, privacy, reviewer competence or publication suitability; report, pitch and article outputs remain drafts and separate release authority is required.",
    }


def build_report_pitch_editorial_surface(package_dir: Path, deliverables: dict[str, str]) -> Path:
    template_path = package_dir / "EDITORIAL_REVIEW_WORKSHEET.csv"
    fields, rows = _read_csv(template_path)
    if not rows:
        raise ValueError("Report & Pitch review page requires claim or evidence review rows")
    cards: list[str] = []
    for index, row in enumerate(rows):
        options = {
            "support_decision": ["SUPPORTED", "NOT_SUPPORTED", "UNRESOLVED"],
            "source_authenticity_checked": ["VERIFIED", "NOT_VERIFIED", "UNAVAILABLE"],
            "rights_privacy_attribution_checked": ["CLEARED", "ISSUE_FOUND", "UNKNOWN"],
            "editorial_decision": ["APPROVED_FOR_INTERNAL_REVIEW", "REVISE", "REJECT"],
        }
        controls = []
        for key, values in options.items():
            label = key.replace("_", " ").capitalize()
            option_html = "".join(
                f'<option value="{html.escape(value)}">{html.escape(value.replace("_", " ").title())}</option>'
                for value in values
            )
            controls.append(
                f'<label>{html.escape(label)}<select data-field="{key}" required><option value="">Choose…</option>{option_html}</select></label>'
            )
        cards.append(
            f'<section class="item" data-index="{index}"><p class="eyebrow">{html.escape(str(row.get("item_type") or "item"))} · {html.escape(str(row.get("item_id") or ""))}</p>'
            f'<h2>Proposed text</h2><label class="wide"><span class="sr">Editable proposed text</span><textarea data-field="proposed_text" rows="3">{html.escape(str(row.get("proposed_text") or ""))}</textarea></label>'
            f'<details><summary>Exact source, locator, and machine state</summary><blockquote>{html.escape(str(row.get("exact_source_text") or "No exact source excerpt supplied."))}</blockquote>'
            f'<dl><dt>References</dt><dd>{html.escape(str(row.get("source_or_claim_refs") or "Not supplied"))}</dd>'
            f'<dt>Source locator</dt><dd>{html.escape(str(row.get("source_locator") or "Not supplied"))}</dd>'
            f'<dt>Source SHA-256</dt><dd><code>{html.escape(str(row.get("source_sha256") or "Not supplied"))}</code></dd>'
            f'<dt>Machine state</dt><dd>{html.escape(str(row.get("machine_state") or "Not stated"))}</dd></dl></details>'
            f'<div class="fields">{"".join(controls)}'
            '<label class="wide">Revision reference<input data-field="revision_reference"></label>'
            '<label class="wide">Reviewer rationale<textarea data-field="rationale" rows="3" required></textarea></label>'
            '<label>Reviewer name<input data-field="reviewer_name" required></label><label>Reviewer role<input data-field="reviewer_role" required></label>'
            '<label class="wide">Reviewed at (ISO 8601 with UTC offset)<input data-field="reviewed_at_iso8601" placeholder="2026-11-02T12:30:00+02:00" required></label>'
            '</div></section>'
        )
    fixed_payload = [{field: row.get(field, "") for field in FIXED_FIELDS} for row in rows]
    link_items = []
    for label, key in (("Open the report PDF", "report_pdf"), ("Open the article PDF", "article_pdf"),
                       ("Open the pitch PDF", "pitch_pdf"), ("Edit the slide deck", "pitch_pptx"),
                       ("View current review validation", "editorial_review_validation")):
        rel = deliverables.get(key)
        if rel:
            link_items.append(f'<li><a href="{html.escape(rel, quote=True)}">{label}</a></li>')
    path = package_dir / "EDITORIAL_REVIEW.html"
    path.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'none'; base-uri 'none'">
<title>Report &amp; Pitch Studio · Editorial review</title><style>
:root{{--ink:#202b29;--muted:#586660;--line:#d5ddd9;--gold:#a66a27;--teal:#075d71;--paper:#f5f6f3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1040px;margin:auto;padding:28px 18px 60px}}h1{{font-size:clamp(1.8rem,4vw,2.6rem);line-height:1.15}}h2{{font-size:1.05rem}}.eyebrow{{color:var(--teal);font-size:.8rem;font-weight:750;letter-spacing:.08em;text-transform:uppercase}}
.notice{{border:1px solid #d9bd8a;border-left:6px solid var(--gold);background:#fff8eb;padding:14px 17px;border-radius:7px;margin:20px 0}}.item{{background:white;border:1px solid var(--line);border-radius:10px;padding:20px;margin:18px 0;box-shadow:0 3px 12px #17251c0b}}
details{{padding:12px;background:#f7f9f7;border-radius:6px}}summary{{cursor:pointer;font-weight:700}}blockquote{{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0;padding:10px;background:#fff;border-left:3px solid #719488}}
dl{{display:grid;grid-template-columns:140px 1fr;gap:5px 12px;overflow-wrap:anywhere}}dt{{font-weight:650;color:var(--muted)}}dd{{margin:0}}.fields{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}}
label{{display:grid;gap:5px;font-size:.9rem;font-weight:650}}.wide{{grid-column:1/-1}}input,select,textarea{{width:100%;font:inherit;font-weight:400;padding:9px;border:1px solid #aebbb4;border-radius:5px;background:white;color:var(--ink)}}:focus-visible{{outline:3px solid #cf9f55;outline-offset:2px}}
button{{font:700 1rem system-ui;padding:12px 18px;border:0;border-radius:6px;color:white;background:var(--teal);cursor:pointer}}.actions{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:22px 0}}#status,.muted{{color:var(--muted)}}.sr{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
@media(max-width:650px){{main{{padding:18px 13px 42px}}.fields{{grid-template-columns:1fr}}.wide{{grid-column:auto}}dl{{grid-template-columns:1fr}}}}
</style></head><body><main><p class="eyebrow">DIO · Report &amp; Pitch Studio</p><h1>Editorial review workspace</h1>
<p>Review each proposed claim, metric, recommendation, and calculation against the exact supplied excerpt and locator. Source fields are carried unchanged into the worksheet export; proposed wording can be revised.</p>
<aside class="notice"><strong>These files are drafts.</strong> Source attribution does not verify truth, rights, or suitability. This page does not publish or send. Approval here means only ready for internal review; separate expert, rights, and release decisions remain required.</aside>
<ul>{''.join(link_items)}<li><a href="EDITORIAL_REVIEW_WORKSHEET.csv">Download original bound worksheet</a></li><li><a href="claim_map.json">View claim map</a></li><li><a href="source_register.json">View source register</a></li></ul>
{''.join(cards)}<div class="actions"><button id="export" type="button">Export completed review CSV</button><span id="status" role="status" aria-live="polite">Complete the decision and reviewer fields for every item.</span></div>
<p class="muted">Run the exported CSV through <code>scripts/validate_report_pitch_editorial_review.py</code>. A complete review never authorizes publication or customer release.</p></main>
<script>
const fixedRows={json.dumps(fixed_payload, ensure_ascii=False).replace('</','<\\/')};const fields={json.dumps(fields, ensure_ascii=False)};
function cell(v){{return '"'+String(v??'').replaceAll('"','""')+'"'}}
document.getElementById('export').addEventListener('click',()=>{{const cards=[...document.querySelectorAll('.item')],rows=[],errors=[];
cards.forEach((card,i)=>{{const row={{...fixedRows[i]}};card.querySelectorAll('[data-field]').forEach(el=>row[el.dataset.field]=el.value.trim());
['support_decision','source_authenticity_checked','rights_privacy_attribution_checked','editorial_decision','rationale','reviewer_name','reviewer_role','reviewed_at_iso8601'].forEach(k=>{{if(!row[k])errors.push(row.item_id+': '+k)}});
if(row.reviewed_at_iso8601&&!/^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}T[0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}}(?:[.][0-9]+)?(?:Z|[+-][0-9]{{2}}:[0-9]{{2}})$/.test(row.reviewed_at_iso8601))errors.push(row.item_id+': review time must include UTC offset');rows.push(row)}});
const status=document.getElementById('status');if(errors.length){{status.textContent='Complete required fields: '+errors.slice(0,4).join('; ')+(errors.length>4?' …':'');return}}
const csv=[fields.map(cell).join(','),...rows.map(row=>fields.map(k=>cell(row[k]??'')).join(','))].join('\\r\\n')+'\\r\\n';const blob=new Blob(['\\ufeff',csv],{{type:'text/csv;charset=utf-8'}}),link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='EDITORIAL_REVIEW_COMPLETED.csv';link.click();URL.revokeObjectURL(link.href);status.textContent='CSV downloaded. Validate it before release; publication remains unauthorized.'}});
</script></main></body></html>\n''', encoding="utf-8")
    return path
