"""Source-bound, human-reviewed HOMS Curriculum customer packet workflow.

Current automated coverage is deliberately limited to Grade 8 Social Sciences,
the grade/subject scope for which this workspace has a checked CAPS page map.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CAPS_PDF = ROOT / "corpora/caps/pdf/senior_grade_7_9/caps_sp_social_science_gr_7-9.pdf"
CAPS_URL = "https://www.education.gov.za/LinkClick.aspx?fileticket=6jpCz5DCZ08%3d&tabid=573&portalid=0&mid=1629"
PAGE_TOPICS = {
    30: ("geography", "term 1", ("maps and globes",)),
    31: ("geography", "term 2", ("climate regions",)),
    32: ("geography", "term 3", ("settlement",)),
    42: ("history", "term 1", ("industrial revolution in britain and southern africa",)),
    43: ("history", "term 2", ("mineral revolution in south africa",)),
    44: ("history", "term 3", ("scramble for africa",)),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _source_path(value: Any, label: str) -> Path:
    path = Path(str(value or "")).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} must identify an existing customer source file")
    return path


def _render_page_text(page: int) -> str:
    import subprocess

    result = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(CAPS_PDF), "-"],
        capture_output=True, text=True, check=False,
    )
    text = result.stdout.strip()
    if result.returncode or not text:
        raise RuntimeError(f"Could not extract CAPS PDF page {page}")
    return text


def build_homs_curriculum_customer_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Map a supplied complete Grade 8 Social Sciences plan to checked CAPS pages.

    The customer attestation establishes packet scope only. It does not prove a
    school's schedule, CAPS applicability, or whether a mapped item is adequate.
    """
    grade = int(packet.get("grade") or 0)
    subject = str(packet.get("subject") or "").strip().casefold()
    if grade != 8 or subject not in {"social sciences", "social science"}:
        raise ValueError("Automated customer mapping is currently supported only for Grade 8 Social Sciences; other scopes remain available for human planning.")
    plan_path = _source_path(packet.get("annual_plan_path"), "annual_plan_path")
    if not CAPS_PDF.is_file():
        raise FileNotFoundError("Official Social Sciences CAPS PDF is unavailable in the verified workspace corpus")

    raw = plan_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("annual plan must be UTF-8 CSV") from exc
    reader = csv.DictReader(text.splitlines())
    normalized_headers = {str(v or "").strip().casefold() for v in (reader.fieldnames or [])}
    if not reader.fieldnames or not ({"subject", "strand"} & normalized_headers) or not {"term", "topic"}.issubset(normalized_headers):
        raise ValueError("annual plan CSV requires subject (or strand), term, and topic columns")
    rows = list(reader)
    if not rows:
        raise ValueError("annual plan contains no curriculum rows")
    headers = {str(v or "").strip().casefold(): v for v in reader.fieldnames}
    subject_header = headers.get("subject") or headers.get("strand")
    for index, row in enumerate(rows, 1):
        row_subject = str(row.get(subject_header) or "").strip().casefold()
        term = str(row.get(headers["term"]) or "").strip().casefold()
        topic = str(row.get(headers["topic"]) or "").strip()
        if row_subject not in {"history", "geography"} or not re.fullmatch(r"(?:term\s*)?[1-4]", term) or not topic:
            raise ValueError(f"annual plan row {index + 1} needs History/Geography, a numbered term, and a non-empty topic")

    page_texts = {page: _render_page_text(page) for page in (*PAGE_TOPICS, 20)}
    normalized = {page: _normalize(value) for page, value in page_texts.items()}
    required_phrases = {
        20: ("both subjects history and geography should be taught and assessed in every term of the school year",),
        **{page: phrases for page, (_, _, phrases) in PAGE_TOPICS.items()},
    }
    for page, phrases in required_phrases.items():
        if not all(phrase in normalized[page] for phrase in phrases):
            raise RuntimeError(f"CAPS page {page} no longer matches the checked Grade 8 source mapping")

    mapped: list[dict[str, Any]] = []
    source_sha = _sha(CAPS_PDF.read_bytes())
    seen: dict[tuple[str, str, str], list[int]] = {}
    for index, row in enumerate(rows, 1):
        row_subject = str(row.get(subject_header) or "").strip().casefold()
        term_value = re.sub(r"\s+", " ", str(row.get(headers["term"]) or "").strip().casefold())
        if term_value.isdigit():
            term_value = "term " + term_value
        topic = str(row.get(headers["topic"]) or "").strip()
        normalized_topic = _normalize(topic)
        match = next((page for page, (caps_subject, caps_term, topics) in PAGE_TOPICS.items()
                      if caps_subject == row_subject and caps_term == term_value
                      and any(_normalize(candidate) in normalized_topic or normalized_topic in _normalize(candidate) for candidate in topics)), None)
        key = (row_subject, term_value, normalized_topic)
        seen.setdefault(key, []).append(index + 1)
        mapped.append({
            "plan_record": f"PLAN-{index:03d}",
            "source_file": plan_path.name,
            "source_sha256": _sha(raw),
            "source_csv_row_number": index + 1,
            "source_record_sha256": _sha(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")),
            "record_hash_basis": "canonical_json_csv_dict_sorted_keys_v1",
            "subject": row_subject.title(), "term": term_value.title(), "customer_topic": topic,
            "review_state": ("INVALID_TERM_REVIEW_REQUIRED" if term_value == "term 4" else
                             "CAPS_TOPIC_SOURCE_MATCH_REVIEW_REQUIRED" if match else "UNMAPPED_REQUIRES_CURRICULUM_OWNER_REVIEW"),
            "caps_page": match,
            "caps_source_sha256": source_sha if match else "",
            "caps_page_text_sha256": _sha(page_texts[match].encode("utf-8")) if match else "",
            "note": "Source mapping only; customer plan truth, completeness, adequacy, sequencing and CAPS applicability require qualified curriculum-owner review.",
        })
    for item in mapped:
        key = (item["subject"].casefold(), item["term"].casefold(), _normalize(item["customer_topic"]))
        if len(seen.get(key, [])) > 1:
            item["review_state"] = "DUPLICATE_ENTRY_REVIEW_REQUIRED"

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    matrix_path = out / "CURRICULUM_ALIGNMENT_MATRIX.csv"
    fields = list(mapped[0])
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(mapped)

    plan_template_path = out / "CURRICULUM_PLAN_INPUT_TEMPLATE.csv"
    plan_template_fields = [
        "subject", "term", "topic", "week_start", "week_count",
        "learning_objective", "assessment_activity", "source_reference",
    ]
    with plan_template_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=plan_template_fields)
        writer.writeheader()

    owner_review_path = out / "CURRICULUM_OWNER_REVIEW_TEMPLATE.csv"
    owner_fields = [
        "plan_record", "source_file", "source_sha256", "source_csv_row_number",
        "source_record_sha256", "subject", "term", "customer_topic", "caps_page",
        "reviewer_decision", "confirmed_subject", "confirmed_term", "complete_plan_checked",
        "term_fit", "scope_coverage_fit", "sequence_fit", "allocation_fit",
        "required_revision", "reviewer_rationale", "reviewer", "reviewed_at",
    ]
    owner_rows = [{
        "plan_record": row["plan_record"], "source_file": row["source_file"],
        "source_sha256": row["source_sha256"], "source_csv_row_number": row["source_csv_row_number"],
        "source_record_sha256": row["source_record_sha256"], "subject": row["subject"],
        "term": row["term"], "customer_topic": row["customer_topic"], "caps_page": row["caps_page"],
        "reviewer_decision": "", "confirmed_subject": "", "confirmed_term": "",
        "complete_plan_checked": "", "term_fit": "", "scope_coverage_fit": "",
        "sequence_fit": "", "allocation_fit": "", "required_revision": "",
        "reviewer_rationale": "", "reviewer": "", "reviewed_at": "",
    } for row in mapped]
    with owner_review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=owner_fields)
        writer.writeheader()
        writer.writerows(owner_rows)

    manifest = {
        "schema": "dio.homs.curriculum.customer_source_binding.v1",
        "grade": 8, "subject": "Social Sciences", "customer_plan": {"file_name": plan_path.name, "sha256": _sha(raw), "complete_plan_attested": packet.get("complete_plan_attested") is True, "attestation_scope": "customer-declared completeness only; not independently verified"},
        "caps_source": {"title": "Social Science CAPS Grade 7-9", "authority": "South African Department of Basic Education", "url": CAPS_URL, "path": CAPS_PDF.resolve().relative_to(ROOT.resolve()).as_posix(), "sha256": source_sha},
        "caps_pages": [{"physical_pdf_page": p, "text_sha256": _sha(page_texts[p].encode("utf-8"))} for p in sorted(page_texts)],
        "plan_rows": mapped,
        "candidate_omissions": "NOT_COMPUTED: requires an authoritative complete subject/term inventory and curriculum-owner review",
        "human_curriculum_owner_review_required": True,
        "release_authorized": False,
    }
    manifest_path = out / "CURRICULUM_SOURCE_BINDING.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    review_path = out / "CURRICULUM_REVIEW.md"
    review_path.write_text(
        "# HOMS Curriculum Alignment Review\n\n"
        "Scope: Grade 8 Social Sciences. The annual plan is a customer-supplied source; its hash proves which bytes were reviewed, not that it is accurate, approved, current, or truly complete.\n\n"
        f"Plan SHA-256: `{_sha(raw)}`  \nCAPS SHA-256: `{source_sha}` ([official source]({CAPS_URL}))\n\n"
        "The matrix lists source-topic matches and unresolved entries. It does not conclude that any CAPS requirement is met or omitted. Candidate omissions are withheld because this mapper does not yet hold a verified complete CAPS inventory for this scope. A curriculum owner must compare the approved school plan and confirm the applicable CAPS edition before acting.\n\n"
        "Use `CURRICULUM_PLAN_INPUT_TEMPLATE.csv` to structure supplied records. Complete `CURRICULUM_OWNER_REVIEW_TEMPLATE.csv` against the approved complete school plan; its decision and fit fields are intentionally blank. A topic match does not confirm completeness, term fit, sequencing, teaching-time allocation, or approval.\n",
        encoding="utf-8",
    )
    outputs = []
    for path in (matrix_path, manifest_path, review_path, plan_template_path, owner_review_path):
        outputs.append({"path": path.name, "sha256": _sha(path.read_bytes()), "bytes": path.stat().st_size})
    receipt = {
        "schema": "dio.homs.curriculum.customer_execution.v1",
        "product_name": "HOMS Curriculum", "grade": 8, "subject": "Social Sciences",
        "case_id": str(packet.get("case_id") or "HOMS-CURRICULUM-CUSTOMER"),
        "customer_plan_sha256": _sha(raw), "caps_source_sha256": source_sha,
        "mapped_plan_row_count": len(mapped),
        "unmapped_plan_row_count": sum(1 for x in mapped if x["caps_page"] is None),
        "human_review_required": True, "professional_conclusion": False,
        "external_release_authorized": False, "outputs": outputs,
    }
    (out / "CUSTOMER_PACKAGE_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
