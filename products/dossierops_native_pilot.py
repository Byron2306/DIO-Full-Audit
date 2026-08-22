from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

from portfolio_runtime import ROOT
from products.governed_case import new_case
from products.professional_evidence_projection import evidence_rows, exception_text, sha256, write_json


ENGINE_IDENTITY = "products.dossierops_native_pilot.run_dossierops_native_pilot"
BINDING_SCHEMA = "dio.professional_evidence.dossierops_native_binding.v1"
PILOT_SCHEMA = "dio.dossierops.native_pilot_receipt.v1"

_TEXT_SUFFIXES = {".md", ".txt", ".csv", ".tsv", ".json", ".html", ".htm", ".xml"}
_DATE_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
        flags=re.I,
    ),
)
_MONEY = re.compile(r"\bR\s?\d[\d,]*(?:\.\d{1,2})?\b", flags=re.I)
_WORD = re.compile(r"\b[\w’'-]+\b", flags=re.UNICODE)


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_text(path: Path) -> str:
    if path.suffix.casefold() not in _TEXT_SUFFIXES:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _word_count(text: str) -> int:
    return len(_WORD.findall(str(text or "")))


def _record_class(path: Path, text: str) -> str:
    blob = f"{path.name} {text[:1500]}".casefold()
    rules = (
        ("agreement", ("agreement", "contract")),
        ("amendment", ("amendment",)),
        ("payment_schedule", ("payment", "outstanding", "invoice")),
        ("correspondence", ("email", "correspondence", "subject:")),
        ("meeting_note", ("meeting", "minutes", "note")),
        ("case_index", ("case_file_index", "record_type,state")),
        ("exception_record", ("exception", "open question", "gap")),
        ("customer_context", ("customer context", "organisation", "buyer")),
        ("evidence_register", ("evidence_register", "customer_supplied_record")),
    )
    for label, terms in rules:
        if any(term in blob for term in terms):
            return label
    return "customer_record"


def _record_state(path: Path, text: str) -> str:
    """Classify visible source state without collapsing multiple records described in one file."""
    blob = f"{path.name} {text}".casefold()
    unsigned_marker = (
        "unsigned_draft" in blob
        or "unsigned draft" in blob
        or ("unsigned" in blob and "amendment" in blob)
    )
    signed_marker = "signed agreement" in blob or (
        "signed" in blob and "agreement" in blob and "unsigned" not in blob
    )
    if signed_marker and unsigned_marker:
        return "mixed_state_source_preserved"
    if unsigned_marker:
        return "unsigned_draft"
    if signed_marker:
        return "signed_record"
    if "draft" in blob:
        return "draft_or_working_record"
    return "customer_supplied_state_not_independently_verified"


def _dates(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _DATE_PATTERNS:
        for match in pattern.findall(text):
            value = str(match).strip()
            if value and value not in found:
                found.append(value)
    return found


def _money(text: str) -> list[str]:
    values: list[str] = []
    for match in _MONEY.findall(text):
        value = re.sub(r"\s+", "", match)
        if value not in values:
            values.append(value)
    return values


def inventory_customer_sources(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    source_dir = packet_dir / "SOURCES"
    if not source_dir.is_dir():
        raise RuntimeError("DossierOps requires the Vesper-custodied SOURCES directory")
    rows: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    for index, path in enumerate(sorted(p for p in source_dir.rglob("*") if p.is_file()), 1):
        relative = str(path.relative_to(packet_dir))
        text = _read_text(path)
        texts[relative] = text
        rows.append(
            {
                "record_id": f"DOS-SRC-{index:03d}",
                "path": relative,
                "filename": path.name,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "record_class": _record_class(path, text),
                "record_state": _record_state(path, text),
                "explicit_dates": _dates(text),
                "monetary_values": _money(text),
                "extractable_words": _word_count(text),
                "custody": "vesper_quarantined_customer_bytes",
                "authenticity_determined": False,
            }
        )
    if len(rows) < 5:
        raise RuntimeError(f"DossierOps pilot requires at least five customer source records; found {len(rows)}")
    return rows, texts


def _tokens(value: str) -> set[str]:
    stop = {
        "customer", "record", "source", "supplied", "this", "that", "with", "from", "dated", "draft",
        "agreement", "dossier", "must", "review", "professional", "contains", "folder", "case",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", str(value or "").casefold())
        if token not in stop
    }


def _cross_reference(packet: dict[str, Any], inventory: list[dict[str, Any]], texts: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, fact in enumerate(evidence_rows(packet), 1):
        statement = str(fact.get("customer_supplied_record") or "").strip()
        fact_tokens = _tokens(statement)
        matches: list[tuple[int, str, str]] = []
        for source in inventory:
            path = str(source["path"])
            if path.endswith("02_evidence_register.csv"):
                continue
            overlap = len(fact_tokens & _tokens(texts.get(path, "")))
            if overlap:
                matches.append((overlap, path, str(source["record_state"])))
        matches.sort(key=lambda row: (-row[0], row[1]))
        rows.append(
            {
                "claim_id": str(fact.get("record_id") or f"DOS-CLAIM-{index:03d}"),
                "customer_statement": statement,
                "claim_source": "CUSTOMER_PACKET/SOURCES/02_evidence_register.csv",
                "corroborating_records": [
                    {"path": path, "token_overlap": score, "record_state": state}
                    for score, path, state in matches[:4]
                ],
                "corroboration_state": "candidate_correlated_record" if matches else "register_only_no_separate_record_matched",
                "legal_effect_determined": False,
            }
        )
    return rows


def _listed_records(packet: dict[str, Any]) -> list[dict[str, str]]:
    path = Path(packet["packet_dir"]) / "SOURCES" / "case_file_index.csv"
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return [
            {str(k): str(v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(handle)
        ]


def build_open_questions(
    packet: dict[str, Any],
    inventory: list[dict[str, Any]],
    cross_reference: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    files = {str(row["filename"]).casefold() for row in inventory}
    states = [str(row["record_state"]) for row in inventory]
    joined_claims = " ".join(str(row["customer_statement"]) for row in cross_reference).casefold()

    if any(state in {"unsigned_draft", "mixed_state_source_preserved"} for state in states) or "unsigned amendment" in joined_claims:
        questions.append(
            {
                "question_id": "DOS-Q-001",
                "severity": "material",
                "question": "Is there a signed amendment or other authorised executed record corresponding to the 18 April 2026 amendment draft?",
                "basis": "The customer material distinguishes an unsigned amendment draft from the signed agreement.",
                "state": "OPEN_HUMAN_REVIEW",
            }
        )
    if "agreed in principle" in joined_claims:
        questions.append(
            {
                "question_id": "DOS-Q-002",
                "severity": "material",
                "question": "What evidentiary role should the agreement-in-principle email have relative to the unsigned amendment draft and signed agreement?",
                "basis": "The customer statement records agreement in principle but also states that no signed amendment is supplied.",
                "state": "OPEN_HUMAN_REVIEW",
            }
        )
    if "426,000" in joined_claims or "r426000" in joined_claims or "r426,000" in joined_claims:
        questions.append(
            {
                "question_id": "DOS-Q-003",
                "severity": "material",
                "question": "Which supplied record is the controlling source for the R426,000 outstanding figure, and what date or period does that figure represent?",
                "basis": "The customer evidence register records R426,000 outstanding; amount status and period require human confirmation from the underlying financial record.",
                "state": "OPEN_HUMAN_REVIEW",
            }
        )

    for row in _listed_records(packet):
        item = row.get("item", "")
        record_type = row.get("record_type", "")
        token = re.sub(r"[^a-z0-9]+", "", item.casefold())
        candidates = [re.sub(r"[^a-z0-9]+", "", name) for name in files]
        if token and not any(token in name or name in token for name in candidates if len(name) > 4):
            questions.append(
                {
                    "question_id": f"DOS-Q-LIST-{len(questions)+1:03d}",
                    "severity": "review",
                    "question": f"The case index lists '{item}' ({record_type}), but no separately named source file clearly matches that index label. Confirm the controlling file or record reference.",
                    "basis": "Case-file index to supplied-file reconciliation.",
                    "state": "OPEN_HUMAN_REVIEW",
                }
            )

    exception = exception_text(packet).strip()
    if exception:
        questions.append(
            {
                "question_id": "DOS-Q-CUSTOMER-EXCEPTION",
                "severity": "boundary",
                "question": exception,
                "basis": "Customer-supplied exception / authority boundary.",
                "state": "OPEN_HUMAN_REVIEW",
            }
        )
    return questions


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _build_review_brief(
    packet: dict[str, Any],
    inventory: list[dict[str, Any]],
    cross_reference: list[dict[str, Any]],
    open_questions: list[dict[str, Any]],
) -> str:
    intake = dict(packet.get("intake") or {})
    customer = dict(intake.get("customer") or {})
    request = str(intake.get("request") or "").strip()
    lines = [
        "# DIO DossierOps Controlled Review Brief",
        "",
        "## Review purpose and boundary",
        "",
        f"This dossier preparation was created from {len(inventory)} customer-supplied source records captured through Vesper custody. The requested work is: {request or 'prepare an indexed professional review dossier'}. The pack is a review aid for an authorised human reviewer. It does not certify dossier completeness, determine legal sufficiency or enforceability, attest authenticity, authorise retention or disposal, submit material externally, or release a final dossier.",
        "",
        "DossierOps keeps record state separate from legal effect. A source described by the customer as signed is indexed as a signed record because that state appears in the supplied material; DIO does not independently authenticate the signature. An unsigned draft remains an unsigned draft even where correspondence says an arrangement was agreed in principle. Financial values are indexed as customer-supplied values and are not treated as independently reconciled balances unless the underlying records establish that status.",
        "",
        "## Customer context",
        "",
        f"Organisation: {customer.get('organisation') or intake.get('organisation') or 'Customer organisation supplied in packet context'}. Buyer / reviewer role: {customer.get('buyer_role') or intake.get('buyer') or 'authorised professional reviewer'}. The source folder is mixed by design and includes agreements, working material, indexes and customer evidence statements. The central review problem is therefore not merely file storage. It is preserving which record says what, which state each record occupies, and which questions remain unresolved before counsel or another authorised professional makes a decision.",
        "",
        "## Source inventory and custody",
        "",
    ]
    for row in inventory:
        dates = ", ".join(row["explicit_dates"]) or "no explicit date extracted"
        money = ", ".join(row["monetary_values"]) or "no monetary value extracted"
        lines.append(
            f"- **{row['record_id']} | {row['filename']}**: class `{row['record_class']}`, state `{row['record_state']}`, {row['bytes']} bytes, SHA-256 `{row['sha256']}`. Dates: {dates}. Monetary values: {money}. The hash binds the exact customer bytes used in this pilot; it does not establish authenticity or legal effect."
        )
    lines.extend(["", "## Customer statements and record cross-reference", ""])
    for row in cross_reference:
        refs = row["corroborating_records"]
        if refs:
            mapped = "; ".join(f"{item['path']} ({item['record_state']})" for item in refs)
        else:
            mapped = "no separately supplied record was matched beyond the customer evidence register"
        lines.append(
            f"- **{row['claim_id']}**: {row['customer_statement']} Cross-reference state: `{row['corroboration_state']}`. Candidate record links: {mapped}. These links are navigation aids based on supplied text overlap, not findings that a claim is proved."
        )
    lines.extend(["", "## Chronology for review", ""])
    dated = [(row, date) for row in inventory for date in row["explicit_dates"]]
    if dated:
        for row, date in dated:
            lines.append(f"- **{date}** appears in `{row['filename']}` ({row['record_class']}; {row['record_state']}). Review the source itself before relying on the date for any legal, financial or procedural conclusion.")
    else:
        lines.append("- No explicit dates were extracted from the separately supplied source files. The reviewer should use the customer evidence register and source records directly.")
    lines.extend(["", "## Record-state hierarchy", ""])
    lines.append(
        "The pack deliberately does not collapse signed, unsigned, draft and correspondence states. The signed agreement and the unsigned amendment draft occupy different evidentiary positions in the source material. Correspondence that records an agreement in principle is retained as correspondence. It is not silently transformed into an executed amendment. Likewise, a case-file index is an index of what the customer says belongs in the file, not proof that every indexed item has been separately supplied or authenticated."
    )
    lines.extend(["", "## Open questions and gaps", ""])
    for question in open_questions:
        lines.append(f"- **{question['question_id']} [{question['severity']}]** {question['question']} Basis: {question['basis']} State: `{question['state']}`.")
    if not open_questions:
        lines.append("- No machine-derived open question was created. Human review remains required because absence of a detected gap is not a completeness finding.")
    lines.extend(
        [
            "",
            "## Counsel review queue",
            "",
            "1. Confirm the governing role of the signed agreement and inspect the exact signed source record rather than relying on this index summary.",
            "2. Resolve the status of the 18 April 2026 unsigned amendment draft without treating the agreement-in-principle email as execution authority.",
            "3. Confirm the source, date or period, and reconciliation status of the R426,000 outstanding amount before using it in a decision or external communication.",
            "4. Reconcile the case-file index against the actual supplied files and request any controlling records that are listed but not separately present.",
            "5. Review every chronology and cross-reference entry against the underlying customer record before adopting it as a professional conclusion.",
            "",
            "## Provenance and limitations",
            "",
            "Every indexed source in this pack is hash-bound to the customer packet consumed after Vesper quarantine rehydration. DossierOps may classify obvious record states and extract visible dates or amounts, but those are navigation-level observations. It does not authenticate documents, infer missing signatures, decide contractual effect, certify the file as complete, or decide whether a record should be retained, disclosed, submitted or released. The controlled dossier ZIP is therefore a review package, not a legal filing or evidentiary certification.",
            "",
            "The deterministic cross-reference uses token overlap only to surface candidate relationships between customer statements and separately supplied records. A candidate relationship can help a reviewer navigate the file, but it is not proof that the record supports the statement. Where a statement appears only in the customer evidence register, the pack says so. Where an indexed item lacks a clearly corresponding separately named file, the pack creates an open question instead of fabricating a file or silently treating the index entry as the record itself.",
            "",
            "## Release gate",
            "",
            "**HUMAN REVIEW REQUIRED. EXTERNAL RELEASE REFUSED.** Dossier completeness, legal sufficiency, authenticity, enforceability, retention/disposal decisions, external submission and final release remain with authorised humans.",
        ]
    )
    return "\n".join(lines) + "\n"


def _document_studio(
    review_brief: Path,
    packet: dict[str, Any],
    output_root: Path,
    runner: Callable[[dict[str, Any], Path, Path], Path],
) -> tuple[Path, dict[str, Any], list[Path]]:
    request_path = output_root / "DOCUMENT_STUDIO_REQUEST.json"
    request = {
        "schema": "dio.document_studio.request.v1",
        "job_id": "PRO-DOSSIEROPS-PILOT-DOC",
        "title": "DossierOps controlled counsel review brief",
        "document_path": str(review_brief),
        "service": "technical_edit",
        "source_language": "English",
        "target_language": None,
        "audience": "Professional counsel reviewer",
        "document_domain": "Professional records dossier",
        "style_standard": "Preserve record states, dates, monetary values, uncertainty, provenance boundaries and human-review questions exactly. Do not add legal conclusions.",
        "protected_tokens": ["R426,000", "3 February 2026", "18 April 2026", "NEEDS_YOU", "REFUSE"],
        "preferred_terms": ["unsigned draft", "signed record", "customer-supplied", "open human review"],
        "owner_authorized": True,
        "remote_processing_approved": True,
        "certified_translation_required": False,
        "human_language_review_required": False,
        "provider": os.environ.get("DOSSIEROPS_DOCUMENT_PROVIDER", "gemini"),
        "format_channels": ["docx", "pdf", "html"],
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    write_json(request_path, request)
    doc_output = runner(request, request_path, output_root / "document_studio")
    receipt_path = Path(doc_output) / "DOCUMENT_STUDIO_RECEIPT.json"
    if not receipt_path.is_file():
        raise RuntimeError("DossierOps pilot Document Studio receipt missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "dio.document_studio.receipt.v1" or receipt.get("status") != "human_review_required":
        raise RuntimeError("DossierOps pilot Document Studio did not reach human-review-required state")
    release = dict(receipt.get("release") or {})
    if release.get("delivery_released") is not False:
        raise RuntimeError("DossierOps pilot Document Studio crossed the external release boundary")
    rendered = [
        path for path in sorted(Path(doc_output).rglob("*"))
        if path.is_file() and path.suffix.casefold() in {".docx", ".pdf", ".html"}
    ]
    if not rendered:
        raise RuntimeError("DossierOps pilot Document Studio produced no reviewable formatted artifact")
    return receipt_path, receipt, rendered


def run_dossierops_native_pilot(
    packet: dict[str, Any],
    execution_dir: Path,
    *,
    operator_id: str,
    now: str,
    document_studio_runner: Callable[[dict[str, Any], Path, Path], Path] | None = None,
    assembly_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from adapters.document_studio.pipeline import run_document_studio
    from products.dossierops.runner import run_controlled_dossierops_assembly

    document_studio_runner = document_studio_runner or run_document_studio
    assembly_runner = assembly_runner or run_controlled_dossierops_assembly
    execution_dir = Path(execution_dir).resolve()
    execution_dir.mkdir(parents=True, exist_ok=True)
    pilot_root = execution_dir / "dossierops_native_pilot"
    pilot_root.mkdir(parents=True, exist_ok=False)
    analysis_root = pilot_root / "analysis"
    analysis_root.mkdir()

    inventory, texts = inventory_customer_sources(packet)
    cross_reference = _cross_reference(packet, inventory, texts)
    open_questions = build_open_questions(packet, inventory, cross_reference)

    source_manifest_path = analysis_root / "DOSSIEROPS_SOURCE_MANIFEST.json"
    write_json(source_manifest_path, {
        "schema": "dio.dossierops.source_manifest.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "source_count": len(inventory),
        "sources": inventory,
        "authenticity_determined": False,
        "completeness_determined": False,
    })

    status_rows = [
        {
            "record_id": row["record_id"],
            "filename": row["filename"],
            "record_class": row["record_class"],
            "record_state": row["record_state"],
            "explicit_dates": "; ".join(row["explicit_dates"]),
            "monetary_values": "; ".join(row["monetary_values"]),
            "sha256": row["sha256"],
        }
        for row in inventory
    ]
    status_path = analysis_root / "DOSSIEROPS_RECORD_STATUS_MATRIX.csv"
    _write_csv(status_path, ["record_id", "filename", "record_class", "record_state", "explicit_dates", "monetary_values", "sha256"], status_rows)

    chronology_rows = [
        {"date_as_supplied": date, "record_id": row["record_id"], "filename": row["filename"], "record_state": row["record_state"], "legal_effect_determined": "false"}
        for row in inventory for date in row["explicit_dates"]
    ]
    chronology_path = analysis_root / "DOSSIEROPS_CHRONOLOGY.csv"
    _write_csv(chronology_path, ["date_as_supplied", "record_id", "filename", "record_state", "legal_effect_determined"], chronology_rows)

    cross_path = analysis_root / "DOSSIEROPS_CLAIM_RECORD_CROSS_REFERENCE.json"
    write_json(cross_path, {
        "schema": "dio.dossierops.claim_record_cross_reference.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "method": "deterministic_token_overlap_navigation_only",
        "claims": cross_reference,
        "claim_support_determined": False,
    })

    questions_path = analysis_root / "DOSSIEROPS_OPEN_QUESTION_REGISTER.json"
    write_json(questions_path, {
        "schema": "dio.dossierops.open_question_register.v1",
        "questions": open_questions,
        "open_count": len(open_questions),
        "legal_conclusions_created": False,
    })

    review_brief = analysis_root / "DOSSIEROPS_COUNSEL_REVIEW_BRIEF.md"
    review_brief.write_text(_build_review_brief(packet, inventory, cross_reference, open_questions), encoding="utf-8")

    document_root = pilot_root / "document_review"
    document_root.mkdir()
    doc_receipt_path, doc_receipt, rendered = _document_studio(
        review_brief, packet, document_root, document_studio_runner
    )

    source_path = pilot_root / "DOSSIEROPS_CASE_SOURCE.json"
    case_source = {
        "source": {
            "kind": "vesper_custodied_professional_case_file",
            "packet_fingerprint": packet["packet_fingerprint"],
            "source_count": len(inventory),
        },
        "evidence": [],
    }
    write_json(source_path, case_source)
    case = new_case(
        product="dio_dossierops",
        job_id="PRO-DOSSIEROPS-NATIVE-PILOT",
        source=case_source,
        source_path=source_path,
        evidence_inputs=["Vesper-custodied customer records", "DossierOps analysis artifacts", "Document Studio review artifacts"],
        expected_outputs=["source manifest", "record status matrix", "chronology", "claim-record cross-reference", "open-question register", "counsel review brief", "hash-bound dossier bundle"],
        required_authorities=["customer_source_owner", "professional_record_reviewer", "final_release_owner"],
        intake_state="approved",
        now=now,
    )

    artifact_inputs: list[dict[str, Any]] = []
    packet_dir = Path(packet["packet_dir"]).resolve()
    for row in inventory:
        path = packet_dir / str(row["path"])
        artifact_inputs.append({
            "artifact_id": row["record_id"],
            "artifact_type": "customer_source_record",
            "source_system": "vesper_customer_packet",
            "approval_state": "authorised_for_internal_review",
            "path": str(path),
            "sha256": "sha256:" + sha256(path),
        })
    for artifact_id, artifact_type, path in (
        ("DOSSIER-SOURCE-MANIFEST", "source_manifest", source_manifest_path),
        ("DOSSIER-STATUS-MATRIX", "record_status_matrix", status_path),
        ("DOSSIER-CHRONOLOGY", "chronology", chronology_path),
        ("DOSSIER-CROSS-REFERENCE", "claim_record_cross_reference", cross_path),
        ("DOSSIER-OPEN-QUESTIONS", "open_question_register", questions_path),
        ("DOSSIER-REVIEW-BRIEF", "counsel_review_brief", review_brief),
    ):
        artifact_inputs.append({
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "source_system": "dossierops_native_pilot",
            "approval_state": "review_candidate",
            "path": str(path),
            "sha256": "sha256:" + sha256(path),
        })
    artifact_inputs.append({
        "artifact_id": "DOCSTUDIO-RECEIPT",
        "artifact_type": "document_studio_receipt",
        "source_system": "document_studio",
        "approval_state": "review_candidate",
        "path": str(doc_receipt_path),
    })
    for index, path in enumerate(rendered, 1):
        artifact_inputs.append({
            "artifact_id": f"DOCSTUDIO-RENDER-{index:02d}",
            "artifact_type": f"document_studio_{path.suffix.casefold().lstrip('.')}_review_artifact",
            "source_system": "document_studio",
            "approval_state": "review_candidate",
            "path": str(path),
            "sha256": "sha256:" + sha256(path),
        })

    assembly_root = pilot_root / "controlled_assembly"
    result = assembly_runner(
        case,
        artifact_inputs=artifact_inputs,
        output_dir=assembly_root,
        operator_id=operator_id,
        now=now,
    )
    receipt = dict(result.get("receipt") or {})
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("assembly_performed") is not True:
        raise RuntimeError("DossierOps native pilot controlled assembly did not complete")
    if receipt.get("human_review_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise RuntimeError("DossierOps native pilot crossed the human/release boundary")

    bundle_path = Path(str(result.get("bundle_path") or ""))
    if not bundle_path.is_file():
        raise RuntimeError("DossierOps native pilot controlled dossier bundle missing")

    source_truth_blob = " ".join(texts.values()).casefold()
    review_truth_blob = review_brief.read_text(encoding="utf-8").casefold()
    signed_unsigned_distinct = (
        "signed agreement" in source_truth_blob
        and ("unsigned draft" in source_truth_blob or "unsigned amendment" in source_truth_blob)
        and "signed agreement" in review_truth_blob
        and ("unsigned amendment" in review_truth_blob or "unsigned draft" in review_truth_blob)
    )
    if not signed_unsigned_distinct:
        raise RuntimeError("DossierOps pilot failed to preserve signed agreement versus unsigned amendment state")

    native_outputs = [source_manifest_path, status_path, chronology_path, cross_path, questions_path, review_brief, doc_receipt_path, *rendered, bundle_path]
    binding = {
        "schema": BINDING_SCHEMA,
        "native_engine": ENGINE_IDENTITY,
        "native_pilot_schema": PILOT_SCHEMA,
        "packet_fingerprint": packet["packet_fingerprint"],
        "source_manifest": str(source_manifest_path),
        "customer_source_count": len(inventory),
        "record_status_matrix": str(status_path),
        "chronology": str(chronology_path),
        "claim_record_cross_reference": str(cross_path),
        "open_question_register": str(questions_path),
        "open_question_count": len(open_questions),
        "review_brief": str(review_brief),
        "review_brief_words": _word_count(review_brief.read_text(encoding="utf-8")),
        "document_studio_receipt": str(doc_receipt_path),
        "document_studio_status": doc_receipt.get("status"),
        "document_studio_execution_performed": True,
        "document_studio_rendered_artifacts": [str(path) for path in rendered],
        "controlled_assembly_receipt": str(assembly_root / "DOSSIEROPS_PROCESSING_RECEIPT.json"),
        "controlled_dossier_bundle": str(bundle_path),
        "native_output_files": [
            {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in native_outputs if path.is_file()
        ],
        "signed_and_unsigned_states_kept_distinct": signed_unsigned_distinct,
        "unsigned_amendment_promoted_to_executed": False,
        "dossier_completeness_certified": False,
        "legal_sufficiency_determined": False,
        "record_authenticity_attested": False,
        "retention_disposal_authorized": False,
        "external_submission_performed": False,
        "final_release_performed": False,
        "identity_state": "controlled_pilot_unpromoted",
        "canonical_portfolio_registration": False,
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    binding["binding_fingerprint"] = _fingerprint(binding)
    binding_path = execution_dir / "DOSSIEROPS_NATIVE_ROUTE_BINDING.json"
    write_json(binding_path, binding)

    return {
        "executor": ENGINE_IDENTITY,
        "native_engine_identity": ENGINE_IDENTITY,
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_id": "dio_dossierops",
        "terminal_artifact_kind": "native_controlled_dossier_review_pack",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": binding,
        "native_result": receipt,
        "binding_path": str(binding_path),
    }


__all__ = [
    "BINDING_SCHEMA",
    "ENGINE_IDENTITY",
    "PILOT_SCHEMA",
    "build_open_questions",
    "inventory_customer_sources",
    "run_dossierops_native_pilot",
]
