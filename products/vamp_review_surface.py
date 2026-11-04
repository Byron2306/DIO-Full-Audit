"""Build a source-bound, offline reviewer handoff for VAMP evidence candidates.

The surface records a relevance decision only. It cannot accept evidence,
attest achievement, issue a rating, or authorize an employment decision.
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_COLUMNS = [
    "packet_fingerprint", "evidence_id", "objective_id", "source_ref",
    "source_file_sha256", "source_statement_sha256", "customer_statement",
    "objective_statement", "candidate_reason", "decision", "reviewer_name", "reviewer_role",
    "reviewed_at_iso8601", "rationale", "underlying_artifact_received",
    "event_date_verified",
]
DECISIONS = {"RELEVANT_FOR_REVIEW", "NOT_RELEVANT", "REQUEST_UNDERLYING_ARTIFACT"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: row.get(key, "") for key in REVIEW_COLUMNS} for row in rows)
    return stream.getvalue().encode("utf-8")


def _build_html(packet_fingerprint: str, rows: list[dict[str, Any]]) -> str:
    safe_rows = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    safe_rows = safe_rows.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    parts = []
    for index, row in enumerate(rows):
        parts.append(
            "<article class='candidate' data-index='" + str(index) + "'>"
            "<div class='candidate-head'><span>Candidate " + str(index + 1).zfill(2) + "</span>"
            "<code>" + html.escape(str(row["evidence_id"])) + " → " + html.escape(str(row["objective_id"])) + "</code></div>"
            "<h2>" + html.escape(str(row["objective_statement"])) + "</h2>"
            "<p class='source-label'>Customer-supplied statement · " + html.escape(str(row["source_ref"])) + "</p>"
            "<blockquote>" + html.escape(str(row["customer_statement"])) + "</blockquote>"
            "<p class='reason'>Candidate rationale: " + html.escape(str(row["candidate_reason"])) + "</p>"
            "<p class='hashes'>Source file SHA-256 <code>" + html.escape(str(row["source_file_sha256"]))
            + "</code><br>Statement SHA-256 <code>" + html.escape(str(row["source_statement_sha256"])) + "</code></p>"
            "<div class='fields'><label>Relevance decision<select data-field='decision'><option value=''>Choose…</option>"
            "<option>RELEVANT_FOR_REVIEW</option><option>NOT_RELEVANT</option>"
            "<option>REQUEST_UNDERLYING_ARTIFACT</option></select></label>"
            "<label>Reviewer name<input data-field='reviewer_name' autocomplete='name'></label>"
            "<label>Reviewer role<input data-field='reviewer_role' autocomplete='organization-title'></label>"
            "<label>Reviewed at (ISO 8601 with UTC offset)<input data-field='reviewed_at_iso8601' placeholder='2026-11-04T14:30:00+02:00'></label>"
            "<label>Rationale<textarea data-field='rationale' rows='3'></textarea></label>"
            "<label class='check'><input type='checkbox' data-field='underlying_artifact_received'>Underlying artifact received and inspected</label>"
            "<label class='check'><input type='checkbox' data-field='event_date_verified'>Event date verified from the underlying source</label></div>"
            "</article>"
        )
    body = "".join(parts) if parts else "<p>No candidate mappings were produced for this packet.</p>"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VAMP evidence relevance review</title>
<style>
:root{{--ink:#17211f;--muted:#52615d;--line:#d4ded9;--panel:#fff;--paper:#f3f6f3;--accent:#17594e;--gold:#a37429;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:1040px;margin:auto;padding:32px 20px 64px}}h1{{font-size:clamp(2rem,4vw,3rem);line-height:1.08;margin:.2em 0}}
.lede{{color:var(--muted);max-width:800px}}.boundary{{border-left:5px solid var(--gold);background:#fff7e8;padding:14px 18px;margin:22px 0}}
.toolbar{{position:sticky;top:0;z-index:2;background:#fffffff2;border:1px solid var(--line);padding:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
button{{border:0;border-radius:8px;background:var(--accent);color:white;padding:11px 15px;font:inherit;font-weight:700;cursor:pointer}}
button.secondary{{background:#e7ece9;color:var(--ink)}}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{{outline:3px solid #d6a44d;outline-offset:2px}}
.candidate{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;margin:18px 0;box-shadow:0 4px 14px #17211f0a}}
.candidate-head{{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:.9rem}}h2{{font-size:1.25rem;margin:.8em 0 .4em}}
.source-label,.hashes{{color:var(--muted);font-size:.88rem;overflow-wrap:anywhere}}blockquote{{margin:12px 0;padding:14px 16px;border-left:3px solid var(--accent);background:#f4f8f6}}
.reason{{color:#344640}}.fields{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:16px}}
label{{display:grid;gap:5px;font-weight:650}}input,select,textarea{{width:100%;border:1px solid #9aa9a2;border-radius:7px;background:white;color:var(--ink);padding:9px;font:inherit}}
label.check{{display:flex;align-items:flex-start;font-weight:500;grid-column:span 2}}label.check input{{width:auto;margin:5px 5px 0 0}}
.status{{min-width:180px;color:var(--muted)}}footer{{margin-top:28px;color:var(--muted);font-size:.9rem}}@media(max-width:620px){{.fields{{grid-template-columns:1fr}}label.check{{grid-column:auto}}.candidate-head{{display:grid}}}}
</style></head><body><main>
<p><strong>VAMP · source-bound reviewer handoff</strong></p><h1>Review candidate evidence links</h1>
<p class="lede">Packet <code>{html.escape(packet_fingerprint)}</code> · {len(rows)} candidate mapping(s). The candidate engine proposes where a customer statement may relate to an objective. A reviewer records relevance and what verification remains.</p>
<section class="boundary"><strong>These decisions do not accept evidence or establish achievement.</strong> Customer statements remain unverified. Obtain and inspect the underlying artifact and its event date before using it as performance evidence. This page creates no rating, promotion, CPD decision, employment action, or external release.</section>
<div class="toolbar"><button id="download">Download reviewer CSV</button><button class="secondary" id="clear">Clear decisions</button><span id="status" class="status" aria-live="polite">No reviewer decisions recorded.</span></div>
{body}
<footer>Offline review page. Download the CSV and use the included <a href="VAMP_EVIDENCE_REVIEW_TOOL.py">review validator</a> to record a source-bound decision receipt. The receipt records relevance only; it does not accept evidence or create a rating.</footer>
</main><script>
const packetFingerprint={json.dumps(packet_fingerprint)};const rows={safe_rows};
const fields=['decision','reviewer_name','reviewer_role','reviewed_at_iso8601','rationale','underlying_artifact_received','event_date_verified'];
function current(row){{const card=document.querySelector(`[data-index="${{rows.indexOf(row)}}"]`);const values={{...row}};for(const field of fields){{const node=card?.querySelector(`[data-field="${{field}}"]`);values[field]=node?.type==='checkbox'?(node.checked?'true':'false'):(node?.value||'').trim();}}return values;}}
function refresh(){{let n=0;document.querySelectorAll('.candidate').forEach(card=>{{const chosen=card.querySelector('[data-field="decision"]')?.value;if(chosen)n++;}});document.getElementById('status').textContent=n?`${{n}} of ${{rows.length}} relevance decisions recorded; review fields are local to this page.`:'No reviewer decisions recorded.';}}
document.querySelectorAll('input,select,textarea').forEach(node=>node.addEventListener('input',refresh));
document.getElementById('clear').addEventListener('click',()=>{{document.querySelectorAll('input,select,textarea').forEach(node=>{{if(node.type==='checkbox')node.checked=false;else node.value='';}});refresh();}});
document.getElementById('download').addEventListener('click',()=>{{
 const output=rows.map(row=>current(row));
 const incomplete=output.find(r=>!r.decision||!r.reviewer_name||!r.reviewer_role||!r.reviewed_at_iso8601||!r.rationale);
 if(incomplete){{document.getElementById('status').textContent='Complete each decision, reviewer name and role, review time, and rationale before export.';return;}}
 const invalidTime=output.find(r=>!/^\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}(?:\\.\\d+)?(?:Z|[+-]\\d{{2}}:\\d{{2}})$/.test(r.reviewed_at_iso8601)||Number.isNaN(Date.parse(r.reviewed_at_iso8601)));
 if(invalidTime){{document.getElementById('status').textContent='Enter a valid ISO 8601 review time with UTC offset for every candidate.';return;}}
 const impossibleDate=output.find(r=>r.event_date_verified==='true'&&r.underlying_artifact_received!=='true');
 if(impossibleDate){{document.getElementById('status').textContent='An event date cannot be marked verified until the underlying artifact is received and inspected.';return;}}
 const columns={json.dumps(REVIEW_COLUMNS)};const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
 const csv=[columns.join(','),...output.map(r=>columns.map(k=>quote(r[k])).join(','))].join('\\n');
 const blob=new Blob([csv],{{type:'text/csv;charset=utf-8'}});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='VAMP_EVIDENCE_REVIEW.csv';a.click();URL.revokeObjectURL(url);
 document.getElementById('status').textContent='Reviewer CSV downloaded. Evidence acceptance and rating remain disabled.';
}});refresh();
</script></body></html>'''


def build_vamp_review_surface(
    projection_path: Path,
    snapshot_path: Path,
    binding_path: Path,
    source_register_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    source_register_bytes = source_register_path.read_bytes()
    source_register_sha256 = hashlib.sha256(source_register_bytes).hexdigest()
    fingerprint = str(projection.get("packet_fingerprint") or "")
    if (not fingerprint or binding.get("packet_fingerprint") != fingerprint
            or binding.get("snapshot_sha256") != _sha(snapshot_path)
            or binding.get("source_rows_match_snapshot") is not True):
        raise ValueError("VAMP review surface inputs are not bound to the current customer snapshot")
    objectives = {
        str(row.get("task_id") or ""): row
        for row in (projection.get("rows") or []) if row.get("task_id")
    }
    snapshot_pairs = {
        (str(evidence.get("evidence_id") or ""), str(mapping.get("objective_id") or ""))
        for evidence in snapshot.get("evidence") or []
        for mapping in evidence.get("mappings") or []
        if mapping.get("decision") == "candidate"
    }
    candidates: list[dict[str, Any]] = []
    for row in projection.get("rows") or []:
        objective_id = str(row.get("candidate_task_id") or "")
        evidence_id = str(row.get("evidence_id") or "")
        binding_row = row.get("source_binding") or {}
        if not objective_id:
            continue
        if (evidence_id, objective_id) not in snapshot_pairs:
            raise ValueError(f"VAMP candidate {evidence_id} → {objective_id} is absent from the snapshot candidate set")
        objective_row = objectives.get(objective_id)
        if objective_row is None:
            raise ValueError(f"VAMP candidate refers to an objective absent from the source projection: {objective_id}")
        byte_start = int(binding_row.get("source_byte_start", -1))
        byte_end = int(binding_row.get("source_byte_end_exclusive", -1))
        statement_bytes = source_register_bytes[byte_start:byte_end] if 0 <= byte_start < byte_end <= len(source_register_bytes) else b""
        statement_text = statement_bytes.decode("utf-8", errors="strict") if statement_bytes else ""
        if binding_row.get("source_statement_csv_escaped") is True:
            statement_text = statement_text.replace('""', '"')
        if (not statement_bytes or statement_text != str(row.get("record") or "")
                or source_register_sha256 != binding_row.get("source_file_sha256")
                or hashlib.sha256(statement_bytes).hexdigest() != binding_row.get("source_statement_sha256")):
            raise ValueError(f"VAMP candidate {evidence_id} has no exact source-register byte binding")
        candidates.append({
            "packet_fingerprint": fingerprint,
            "evidence_id": evidence_id,
            "objective_id": objective_id,
            "source_ref": str(binding_row.get("source_ref") or ""),
            "source_file_sha256": str(binding_row.get("source_file_sha256") or ""),
            "source_statement_sha256": str(binding_row.get("source_statement_sha256") or ""),
            "customer_statement": str(row.get("record") or ""),
            "objective_statement": str(objective_row.get("record") or ""),
            "candidate_reason": str(row.get("candidate_mapping_reason") or "Candidate requires human relevance review."),
            "decision": "", "reviewer_name": "", "reviewer_role": "", "reviewed_at_iso8601": "", "rationale": "",
            "underlying_artifact_received": "", "event_date_verified": "",
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "VAMP_EVIDENCE_REVIEW.csv"
    csv_path.write_bytes(_csv_bytes(candidates))
    html_path = output_dir / "VAMP_EVIDENCE_REVIEW.html"
    html_path.write_text(_build_html(fingerprint, candidates), encoding="utf-8")
    guide_path = output_dir / "VAMP_EVIDENCE_REVIEW_GUIDE.md"
    guide_path.write_text(
        "# VAMP evidence relevance review\n\n"
        f"Packet fingerprint: `{fingerprint}`\n\n"
        f"Candidate mappings: {len(candidates)}. The HTML page and CSV bind each candidate to its packet, evidence id, objective id, exact customer statement, source reference, and source hashes.\n\n"
        "For each candidate, choose `RELEVANT_FOR_REVIEW`, `NOT_RELEVANT`, or `REQUEST_UNDERLYING_ARTIFACT`; enter the reviewer and rationale. Record artifact/date checks only after inspecting the underlying source. These fields capture a human relevance decision only: they do not accept a performance claim, update a rating, establish achievement, authorize employment action, or release the pack. Customer statements and uploaded documents remain unverified until separately validated.\n\n"
        "Complete decisions in the offline HTML page and download the CSV, or edit the blank CSV directly. Keep the packet fingerprint and source binding columns unchanged. After review, run the included validator from the route root:\n\n"
        "```sh\npython EXECUTION/vamp_evidence_review/VAMP_EVIDENCE_REVIEW_TOOL.py \\\n  --projection PROJECTION/VAMP_DOMAIN_PROJECTION.json \\\n  --source-register CUSTOMER_PACKET/SOURCES/02_evidence_register.csv \\\n  --review-csv EXECUTION/vamp_evidence_review/VAMP_EVIDENCE_REVIEW.csv \\\n  --output EXECUTION/vamp_evidence_review/VAMP_EVIDENCE_REVIEW_RECEIPT.json\n```\n\n"
        "The resulting receipt records the reviewer’s statements only; the route still treats the mappings as unaccepted until underlying evidence is separately validated.\n",
        encoding="utf-8",
    )
    tool_path = output_dir / "VAMP_EVIDENCE_REVIEW_TOOL.py"
    shutil.copyfile(Path(__file__).resolve(), tool_path)
    receipt = {
        "schema": "dio.vamp.evidence_relevance_review_surface.v1",
        "packet_fingerprint": fingerprint,
        "snapshot_sha256": _sha(snapshot_path),
        "customer_snapshot_binding_sha256": _sha(binding_path),
        "candidate_count": len(candidates),
        "review_state": "PENDING_HUMAN_REVIEW",
        "human_review_required": True,
        "accepted_evidence_count": 0,
        "rating_generated": False,
        "employment_decision_generated": False,
        "external_release_authorized": False,
        "artifacts": {
            name: {"path": path.name, "sha256": _sha(path), "bytes": path.stat().st_size}
            for name, path in (("csv", csv_path), ("html", html_path), ("guide", guide_path), ("tool", tool_path))
        },
        "claim_boundary": "Reviewer input can record relevance only. It does not accept evidence or establish truth, dates, objective achievement, rating, or authority.",
    }
    receipt_path = output_dir / "VAMP_EVIDENCE_REVIEW_SURFACE_RECEIPT.json"
    _write_json(receipt_path, receipt)
    receipt["receipt_sha256"] = _sha(receipt_path)
    return receipt


def validate_vamp_evidence_review(
    projection_path: Path,
    source_register_path: Path,
    review_csv_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Validate a completed reviewer CSV without accepting evidence or ratings."""
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    projection_rows = projection.get("rows") or []
    objectives = {str(row.get("task_id") or ""): row for row in projection_rows if row.get("task_id")}
    expected: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for item in projection_rows:
        evidence_id = str(item.get("evidence_id") or "")
        objective_id = str(item.get("candidate_task_id") or "")
        if evidence_id and objective_id:
            objective = objectives.get(objective_id)
            if objective is None:
                raise ValueError(f"candidate objective is not in the source projection: {objective_id}")
            expected[(evidence_id, objective_id)] = (item, objective)
    with review_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REVIEW_COLUMNS:
            raise ValueError("review CSV columns do not match the issued review schema")
        submitted_rows = list(reader)
    if len(submitted_rows) != len(expected):
        raise ValueError("review CSV must contain exactly one decision for every issued candidate")
    source_bytes = source_register_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    observed: set[tuple[str, str]] = set()
    decisions: list[dict[str, Any]] = []
    for row in submitted_rows:
        key = (str(row.get("evidence_id") or ""), str(row.get("objective_id") or ""))
        if key in observed or key not in expected:
            raise ValueError(f"duplicate or unknown candidate decision: {key}")
        observed.add(key)
        candidate, objective = expected[key]
        binding = candidate.get("source_binding") or {}
        expected_fields = {
            "packet_fingerprint": projection.get("packet_fingerprint"),
            "source_ref": binding.get("source_ref"),
            "source_file_sha256": binding.get("source_file_sha256"),
            "source_statement_sha256": binding.get("source_statement_sha256"),
            "customer_statement": candidate.get("record"),
            "objective_statement": objective.get("record"),
            "candidate_reason": candidate.get("candidate_mapping_reason"),
        }
        if any(str(row.get(field) or "") != str(value or "") for field, value in expected_fields.items()):
            raise ValueError(f"review CSV changed immutable source or candidate fields for {key}")
        try:
            start, end = (int(value) for value in str(binding.get("source_ref") or "").rsplit("#bytes=", 1)[1].split(":", 1))
        except (IndexError, ValueError):
            raise ValueError(f"candidate has no parseable source byte span: {key}") from None
        span = source_bytes[start:end] if 0 <= start < end <= len(source_bytes) else b""
        source_text = span.decode("utf-8", errors="strict") if span else ""
        if binding.get("source_statement_csv_escaped") is True:
            source_text = source_text.replace('""', '"')
        if (not span or source_hash != binding.get("source_file_sha256")
                or source_text != str(candidate.get("record") or "")
                or hashlib.sha256(str(candidate.get("record") or "").encode("utf-8")).hexdigest() != binding.get("source_statement_sha256")):
            raise ValueError(f"source register bytes no longer match candidate statement {key}")
        decision = str(row.get("decision") or "").strip()
        reviewer = str(row.get("reviewer_name") or "").strip()
        reviewer_role = str(row.get("reviewer_role") or "").strip()
        rationale = str(row.get("rationale") or "").strip()
        reviewed_at = str(row.get("reviewed_at_iso8601") or "").strip()
        if decision not in DECISIONS or not reviewer or not reviewer_role or not rationale:
            raise ValueError(f"decision, reviewer name/role, and rationale are required for {key}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", reviewed_at):
            raise ValueError(f"review timestamp must be ISO-8601 with a UTC offset for {key}")
        try:
            parsed_time = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"review timestamp must be ISO-8601 with a timezone for {key}") from None
        if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
            raise ValueError(f"review timestamp must include a timezone for {key}")
        artifact_received = str(row.get("underlying_artifact_received") or "").strip().lower()
        date_verified = str(row.get("event_date_verified") or "").strip().lower()
        if artifact_received not in {"true", "false"} or date_verified not in {"true", "false"}:
            raise ValueError(f"artifact/date review fields must be explicit true/false values for {key}")
        if date_verified == "true" and artifact_received != "true":
            raise ValueError(f"event date cannot be marked verified unless the underlying artifact was received for {key}")
        decisions.append({
            "evidence_id": key[0], "objective_id": key[1], "source_ref": binding["source_ref"],
            "source_file_sha256": binding["source_file_sha256"],
            "source_statement_sha256": binding["source_statement_sha256"],
            "decision": decision, "reviewer_name": reviewer, "reviewer_role": reviewer_role,
            "reviewed_at_utc": parsed_time.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            "rationale": rationale, "underlying_artifact_received_reported_by_reviewer": artifact_received == "true",
            "event_date_verified_reported_by_reviewer": date_verified == "true",
        })
    if observed != set(expected):
        raise ValueError("one or more candidate decisions are missing")
    receipt = {
        "schema": "dio.vamp.evidence_relevance_review_decisions.v1",
        "packet_fingerprint": projection.get("packet_fingerprint"),
        "projection_sha256": _sha(projection_path),
        "source_register_sha256": source_hash,
        "review_csv_sha256": _sha(review_csv_path),
        "decision_count": len(decisions),
        "review_state": "REVIEWER_DECISIONS_CAPTURED_NOT_ACCEPTED",
        "decisions": decisions,
        "accepted_evidence_count": 0,
        "rating_generated": False,
        "employment_decision_generated": False,
        "external_effects": False,
        "claim_boundary": "Reviewer relevance decisions and artifact/date receipt flags are self-reported. This receipt does not establish source authenticity, event dates, evidence sufficiency, objective achievement, accepted evidence mappings, ratings, or employment decisions.",
    }
    _write_json(output_path, receipt)
    return receipt


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate a completed VAMP evidence-relevance review CSV")
    parser.add_argument("--projection", required=True, type=Path)
    parser.add_argument("--source-register", required=True, type=Path)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = validate_vamp_evidence_review(args.projection, args.source_register, args.review_csv, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"review_state": receipt["review_state"], "decision_count": receipt["decision_count"],
                      "accepted_evidence_count": 0, "rating_generated": False, "external_effects": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
