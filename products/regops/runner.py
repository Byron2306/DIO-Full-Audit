from __future__ import annotations

import hashlib
import html
import json
import csv
from pathlib import Path
from typing import Any

from products.governed_case import canonical_hash, validate_case
from products.regulatory.core import build_regulatory_context
from products.regulatory.seraph_review import challenge_ai_regulatory_context

from .materializer import materialize_regops_case


COMPONENT_PRODUCT_ID = "dio_airegreadiness"
COMPONENT_RELATION = "composition_reuse"
COMPONENT_SOURCE_TYPE = "ai_regulatory_context"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, value: bytes) -> str:
    path.write_bytes(value)
    return _sha(value)


def _gate(case: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(row for row in case["gates"] if row["gate_id"] == gate_id)


def _component_binding(
    payload: dict[str, Any] | None,
    *,
    now: str,
) -> dict[str, Any]:
    if payload is None:
        return {
            "reusable_component_product_id": COMPONENT_PRODUCT_ID,
            "relationship": COMPONENT_RELATION,
            "state": "NOT_EVALUATED",
            "reason": "No AI regulatory-readiness context was supplied.",
            "authority_created": False,
            "external_effects": False,
            "external_release": "REFUSE",
        }

    if payload.get("source_type") != COMPONENT_SOURCE_TYPE:
        raise ValueError(
            f"RegOps AI component requires source_type={COMPONENT_SOURCE_TYPE}"
        )

    envelope = build_regulatory_context(
        COMPONENT_PRODUCT_ID,
        payload,
        now=now,
    )
    if envelope["authority_created"] is not False:
        raise RuntimeError("AIRegReadiness component illegally created authority.")
    if envelope["external_effects"] is not False:
        raise RuntimeError("AIRegReadiness component illegally created external effects.")
    if envelope["external_release"] != "REFUSE":
        raise RuntimeError("AIRegReadiness component external release boundary drifted.")
    seraph = challenge_ai_regulatory_context(envelope, payload, now=now)
    if seraph["coverage_state"] != "partial" or seraph["execution_authorized"] is not False:
        raise RuntimeError("AIRegReadiness Seraph challenge boundary drifted.")

    return {
        "reusable_component_product_id": COMPONENT_PRODUCT_ID,
        "relationship": COMPONENT_RELATION,
        "state": "CONTROLLED_CONTEXT_EVALUATED",
        "envelope_fingerprint": envelope["envelope_fingerprint"],
        "seraph_challenge": seraph,
        "dimensions": {
            row["dimension"]: row["state"]
            for row in envelope["dimensions"]
        },
        "human_gate": envelope["human_gate"],
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }


def _review_pack(
    case: dict[str, Any],
    materialization: dict[str, Any],
    component: dict[str, Any],
    customer_review_register: list[dict[str, Any]],
) -> dict[str, Any]:
    matrix = materialization["prerequisite_matrix"]
    evidence = {row["evidence_id"]: row for row in case["evidence"]}
    used_evidence_ids = sorted(
        {
            evidence_id
            for row in matrix
            for evidence_id in row["evidence_ids"]
        }
    )
    evidence_receipts = [
        {
            "evidence_id": evidence_id,
            "source_ref": evidence[evidence_id]["source_ref"],
            "sha256": evidence[evidence_id].get("sha256"),
            "authority_grade": evidence[evidence_id]["authority_grade"],
            "trust_state": evidence[evidence_id]["trust_state"],
            "freshness_state": evidence[evidence_id]["freshness_state"],
        }
        for evidence_id in used_evidence_ids
        if evidence_id in evidence
    ]
    deadline_queue = [
        {
            "prerequisite_id": row["prerequisite_id"],
            "due_at": row["due_at"],
            "expires_at": row["expires_at"],
            "deadline_state": row["deadline_state"],
        }
        for row in matrix
        if row["deadline_state"] != "NONE"
    ]
    professional_ids = [
        row["prerequisite_id"]
        for row in matrix
        if row["professional_review_required"]
    ]

    return {
        "schema": "dio.regops.readiness_pack.v1",
        "product_id": "dio_regops",
        "case_id": case["case_id"],
        "profile_id": materialization["profile_id"],
        "requirement_register": matrix,
        "evidence_receipt_set": evidence_receipts,
        "deadline_and_renewal_queue": deadline_queue,
        "customer_statement_review_register": customer_review_register,
        "customer_statement_review_as_of_date": next((row.get("review_as_of_date") for row in customer_review_register if row.get("review_as_of_date")), None),
        "customer_statement_review_boundary": "Rows below classify and bind customer statements for follow-up. Any date comparison is against the stated review date only; dates and roles remain customer-stated candidates. No legal deadline, regulatory applicability, truth, or authorised owner is established.",
        "readiness_decision": materialization["readiness_decision"],
        "professional_escalation_record": {
            "state": "NEEDS_YOU" if professional_ids else "NOT_REQUIRED_BY_PROFILE",
            "prerequisite_ids": professional_ids,
            "professional_decision_created": False,
        },
        "ai_regulatory_component_binding": component,
        "risk_boundary": (
            "RegOps evaluates configured operational prerequisites and evidence for readiness review. "
            "It does not provide legal, accounting, tax, regulatory, or professional advice; an ALLOW "
            "readiness state is not legal clearance and creates no execution, filing, or release authority."
        ),
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }


def _html_pack(pack: dict[str, Any]) -> bytes:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['prerequisite_id']))}</td>"
        f"<td>{html.escape(str(row['readiness_state']))}</td>"
        f"<td>{html.escape(str(row['deadline_state']))}</td>"
        f"<td>{html.escape(str(row['statement']))}</td>"
        "</tr>"
        for row in pack["requirement_register"]
    )
    decision = html.escape(str(pack["readiness_decision"]["state"]))
    review_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('record_id') or ''))}</td>"
        f"<td>{html.escape(str(row.get('record_kind') or ''))}</td>"
        f"<td>{html.escape(str(row.get('customer_statement') or ''))}</td>"
        f"<td>{html.escape(str(row.get('customer_stated_date_candidate') or 'Not stated'))}</td>"
        f"<td>{html.escape(str(row.get('date_candidate_timing_state') or 'Not assessed'))}</td>"
        f"<td>{html.escape(str(row.get('customer_stated_role_candidate') or 'Not stated'))}</td>"
        f"<td>{html.escape(str(row.get('requested_follow_up') or ''))}</td>"
        f"<td>{html.escape(str(row.get('source_ref') or ''))}</td>"
        "</tr>"
        for row in pack.get("customer_statement_review_register") or []
    )
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>DIO RegOps · Controlled readiness review</title>"
        "<style>"
        ":root{color-scheme:light;--ink:#182b3a;--muted:#536576;--line:#ced8df;--paper:#fff;--wash:#f2f6f8;--teal:#176b67;--amber:#8b5310}"
        "*{box-sizing:border-box}body{margin:0;background:#eaf0f3;color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}"
        "main{max-width:1200px;margin:32px auto;padding:0 22px 56px}.masthead,section,.boundary{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:22px;margin:0 0 18px}"
        ".eyebrow{color:var(--teal);font-size:.78rem;font-weight:750;letter-spacing:.12em;text-transform:uppercase;margin:0 0 6px}h1,h2{line-height:1.2;margin:.2em 0 .5em}h1{font-size:clamp(1.7rem,4vw,2.5rem)}h2{font-size:1.25rem}"
        ".status{display:inline-block;border-radius:99px;padding:5px 12px;background:#fff3df;color:#6f3d05;font-weight:750}.boundary{border-left:5px solid var(--amber);background:#fffaf1}"
        ".table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px}table{border-collapse:collapse;width:100%;min-width:780px;background:white}th,td{padding:12px 13px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:var(--wash);font-size:.82rem;color:#314b5d}tbody tr:last-child td{border-bottom:0}td{overflow-wrap:anywhere}"
        "a{color:#075f83;text-underline-offset:3px}a:focus-visible{outline:3px solid #d08a1f;outline-offset:3px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--wash);padding:14px;border-radius:8px}"
        "@media(max-width:640px){main{margin:14px auto;padding:0 12px 32px}.masthead,section,.boundary{padding:16px;border-radius:9px}}"
        "</style></head><body><main>"
        "<header class='masthead'><p class='eyebrow'>DIO RegOps · Customer review pack</p>"
        "<h1>Controlled readiness review</h1>"
        f"<p>Configured readiness <span class='status'>{decision}</span></p>"
        "<p>Operational preparation only. Professional decisions remain with the authorised reviewer; external filing and release are refused.</p></header>"
        "<aside class='boundary'><strong>Review boundary.</strong> "
        "An ALLOW state would describe configured operational prerequisites only. It is not legal clearance, professional advice, filing authority, or release authority.</aside>"
        "<section aria-labelledby='requirements'><h2 id='requirements'>Configured prerequisite register</h2><div class='table-wrap'><table><thead><tr>"
        "<th scope='col'>Prerequisite</th><th scope='col'>Evidence state</th><th scope='col'>Deadline state</th><th scope='col'>Customer statement</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div></section>"
        "<section aria-labelledby='customer-statements'><h2 id='customer-statements'>Customer statement review register</h2>"
        f"<p>{html.escape(str(pack.get('customer_statement_review_boundary') or ''))}</p>"
        f"<p>Review date for customer-stated date comparisons: <strong>{html.escape(str(pack.get('customer_statement_review_as_of_date') or 'Not supplied'))}</strong>. A past-date flag is a calendar comparison only; it does not find a filing late or establish that the asserted deadline applies.</p>"
        "<p><a href='REGOPS_CUSTOMER_REVIEW_REGISTER.csv' download>Download editable customer review register (CSV)</a></p>"
        "<div class='table-wrap'><table><thead><tr><th scope='col'>Record</th><th scope='col'>Preliminary type</th><th scope='col'>Customer statement</th><th scope='col'>Stated date candidate</th><th scope='col'>Date comparison state</th><th scope='col'>Stated role candidate</th><th scope='col'>Follow-up requested</th><th scope='col'>Exact source row</th></tr></thead>"
        f"<tbody>{review_rows}</tbody></table></div></section>"
        "<section aria-labelledby='ai-context'><h2 id='ai-context'>AI regulatory component review</h2>"
        f"<pre>{html.escape(json.dumps(pack['ai_regulatory_component_binding'], indent=2, sort_keys=True))}</pre></section>"
        "</main></body></html>"
    )
    return page.encode("utf-8")


def run_controlled_regops_review(
    case: dict[str, Any],
    *,
    profile_id: str,
    prerequisites: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    gaps: list[dict[str, Any]] | None,
    ai_regulatory_context: dict[str, Any] | None,
    customer_review_register: list[dict[str, Any]] | None = None,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ValueError("RegOps controlled processing requires an explicit operator_id.")

    validate_case(case)
    if _gate(case, "intake_authority")["state"] != "allow":
        raise RuntimeError("RegOps controlled processing requires approved intake authority.")
    if _gate(case, "generic_executor")["state"] != "refuse":
        raise RuntimeError("Generic executor boundary drifted before RegOps processing.")
    if _gate(case, "external_release")["state"] == "allow":
        raise RuntimeError("RegOps controlled processing cannot start with external release ALLOW.")

    materialization = materialize_regops_case(
        case,
        profile_id=profile_id,
        prerequisites=prerequisites,
        evidence_inputs=evidence_inputs,
        gaps=gaps,
        raised_by=operator_id,
        now=now,
    )
    component = _component_binding(ai_regulatory_context, now=now)
    customer_review_register = list(customer_review_register or [])
    pack = _review_pack(case, materialization, component, customer_review_register)
    validate_case(case)

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "JSON": (
            "REGOPS_READINESS_PACK.json",
            json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
            + b"\n",
        ),
        "HTML": ("REGOPS_READINESS_PACK.html", _html_pack(pack)),
    }
    register_path = output_dir / "REGOPS_CUSTOMER_REVIEW_REGISTER.csv"
    register_fields = ["record_id", "record_kind", "customer_statement", "source_ref", "source_file_sha256", "source_row_sha256", "source_statement_sha256", "source_byte_start", "source_byte_end_exclusive", "customer_stated_date_candidate", "review_as_of_date", "date_candidate_timing_state", "customer_stated_role_candidate", "requested_follow_up", "claim_state", "assigned_review_owner", "verified_date", "reviewer_disposition"]
    with register_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=register_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(customer_review_register)
    rendered["CUSTOMER_REVIEW_REGISTER"] = (
        register_path.name,
        register_path.read_bytes(),
    )
    artifacts = [
        {
            "artifact_type": kind,
            "filename": filename,
            "sha256": _write(output_dir / filename, body),
        }
        for kind, (filename, body) in rendered.items()
    ]

    pack_fingerprint = "sha256:" + _sha(_canonical(pack))
    proof = {
        "schema": "dio.regops.controlled_proof_manifest.v1",
        "provider_id": "regops_controlled_readiness_v1",
        "product_id": "dio_regops",
        "artifact_type": "proof_room_manifest",
        "case_id": case["case_id"],
        "profile_id": profile_id,
        "readiness_state": materialization["readiness_decision"]["state"],
        "readiness_pack_fingerprint": pack_fingerprint,
        "ai_regulatory_component": {
            "product_id": COMPONENT_PRODUCT_ID,
            "relationship": COMPONENT_RELATION,
            "state": component["state"],
            "envelope_fingerprint": component.get("envelope_fingerprint"),
        },
        "case_sha256": canonical_hash(case),
        "artifacts": artifacts,
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": (
                "Professional interpretation, consequential action, filing, and external release "
                "remain human-authority bound."
            ),
        },
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    proof["proof_fingerprint"] = "sha256:" + _sha(_canonical(proof))
    _write(
        output_dir / "PROOF_MANIFEST.json",
        json.dumps(proof, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )

    receipt = {
        "schema": "dio.regops.controlled_processing_receipt.v1",
        "processor_id": "regops_controlled_readiness_v1",
        "product_id": "dio_regops",
        "case_id": case["case_id"],
        "operator_id": operator_id,
        "processed_at": now,
        "profile_id": profile_id,
        "internal_processing": "COMPLETE",
        "readiness_state": materialization["readiness_decision"]["state"],
        "readiness_pack_fingerprint": pack_fingerprint,
        "proof_fingerprint": proof["proof_fingerprint"],
        "ai_regulatory_component_state": component["state"],
        "ai_regulatory_component_fingerprint": component.get("envelope_fingerprint"),
        "seraph_challenge_sha256": (component.get("seraph_challenge") or {}).get("receipt_sha256"),
        "seraph_verdict": (component.get("seraph_challenge") or {}).get("verdict"),
        "seraph_coverage_state": (component.get("seraph_challenge") or {}).get("coverage_state"),
        "generic_executor_gate": _gate(case, "generic_executor")["state"],
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "legal_clearance_created": False,
        "professional_decision_created": False,
        "filing_authority_created": False,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    _write(
        output_dir / "REGOPS_PROCESSING_RECEIPT.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )

    return {
        "case": case,
        "materialization": materialization,
        "ai_regulatory_component": component,
        "readiness_pack": pack,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
    }
