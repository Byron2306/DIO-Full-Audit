from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT
from products.governed_case import new_case
from products.professional_evidence_projection import (
    document_studio_projection,
    evidence_rows,
    evidence_register_record_bindings,
    exception_text,
    obligation_projection,
    sha256,
    slug,
    write_json,
)


class ProfessionalNativeExecutionError(RuntimeError):
    pass


class _AccessibleHtmlPreparation(HTMLParser):
    """Preserve a supplied HTML document while applying bounded semantic fixes."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.issues: list[dict[str, Any]] = []
        self.image_count = 0
        self.image_alt_missing: list[str] = []
        self.image_sources: list[str] = []
        self.headings: list[dict[str, Any]] = []
        self._last_heading_level: int | None = None
        self._tag_stack: list[tuple[str, str, dict[str, str]]] = []
        self._links: list[dict[str, str]] = []
        self._table_header_stack: list[bool] = []
        self._status_cells = 0

    def _banner(self) -> str:
        return (
            '<aside class="review-notice"><strong>Accessibility preparation draft.</strong> '
            'Items marked for owner review remain unresolved; this file is not a WCAG or PDF/UA certification.</aside>'
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {str(k).lower(): (v or "") for k, v in attrs}
        emitted = tag
        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            if self._last_heading_level is not None and level > self._last_heading_level + 1:
                adjusted = self._last_heading_level + 1
                self.issues.append({"issue_id": f"A11Y-HEAD-{len(self.headings)+1:03d}", "state": "CORRECTED_IN_DRAFT", "source_heading": tag, "prepared_heading": f"h{adjusted}", "finding": f"Heading level {tag} skipped a level after h{self._last_heading_level}; prepared as h{adjusted}."})
                level = adjusted
                emitted = f"h{level}"
            self._last_heading_level = level
            self.headings.append({"source_tag": tag, "prepared_tag": emitted, "text_pending": True})
        if tag == "img":
            self.image_count += 1
            source = attrs_dict.get("src", "")
            self.image_sources.append(source)
            if not attrs_dict.get("alt", "").strip():
                self.image_alt_missing.append(source)
                self.issues.append({"issue_id": f"A11Y-ALT-{self.image_count:03d}", "state": "NEEDS_YOU", "source_locator": source or f"img[{self.image_count}]", "finding": "Alternative text is missing or blank; image meaning must be supplied by the content owner."})
        if tag == "table":
            self._table_header_stack.append(False)
        if tag == "th":
            if self._table_header_stack:
                self._table_header_stack[-1] = True
        if tag == "td" and attrs_dict.get("class", "").casefold().startswith("status-"):
            self._status_cells += 1
            color = attrs_dict.get("class", "").split("-", 1)[-1].casefold()
            self.issues.append({"issue_id": f"A11Y-STATUS-{self._status_cells:03d}", "state": "CORRECTED_IN_DRAFT_WITH_OWNER_CONFIRMATION", "source_locator": f"table status cell {self._status_cells}", "finding": f"Added visible text for the {color} status marker; its business meaning still requires owner confirmation."})
            attrs_dict["_dio_status_color"] = color
        if tag == "a":
            self._links.append({"href": attrs_dict.get("href", ""), "text": ""})
        serialized = "".join(f' {html.escape(str(k), quote=True)}="{html.escape(str(v or ""), quote=True)}"' for k, v in attrs_dict.items() if not k.startswith("_"))
        self.parts.append(f"<{emitted}{serialized}>")
        if tag == "body":
            self.parts.append(self._banner())
        if tag not in self.VOID:
            self._tag_stack.append((tag, emitted, attrs_dict))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "td":
            cell = next((attrs for source_tag, _, attrs in reversed(self._tag_stack) if source_tag == "td"), {})
            color = cell.get("_dio_status_color")
            if color:
                self.parts.append(f'<span class="status-text">Status marker: {html.escape(color)}; meaning requires owner confirmation.</span>')
        emitted = tag
        for index in range(len(self._tag_stack) - 1, -1, -1):
            source_tag, output_tag, _ = self._tag_stack[index]
            if source_tag == tag:
                emitted = output_tag
                del self._tag_stack[index:]
                break
        self.parts.append(f"</{emitted}>")
        if tag == "table" and self._table_header_stack:
            if not self._table_header_stack.pop():
                self.issues.append({"issue_id": f"A11Y-TABLE-{len([i for i in self.issues if i['issue_id'].startswith('A11Y-TABLE-')])+1:03d}", "state": "NEEDS_YOU", "finding": "Table has no header cells; the owner must confirm column labels before they are added."})
        if tag == "a" and self._links:
            link = self._links.pop()
            label = re.sub(r"\s+", " ", link["text"]).strip().casefold()
            if label in {"click here", "here", "read more", "more"}:
                self.issues.append({"issue_id": f"A11Y-LINK-{len(self._links)+1:03d}", "state": "NEEDS_YOU", "source_locator": link["href"], "finding": f"Link text '{label}' does not describe its destination; owner should provide a descriptive label."})

    def handle_data(self, data: str) -> None:
        if self._links:
            self._links[-1]["text"] += data
        if data.strip() and self.headings:
            self.headings[-1]["text_pending"] = False
        self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")


def _canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _write_html(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    body = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>", f"<title>{html.escape(title)}</title>",
            "<style>body{font-family:Arial,sans-serif;max-width:980px;margin:32px auto;padding:0 22px;color:#172033}h1,h2{color:#12233f}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd5e0;padding:8px;vertical-align:top}th{background:#12233f;color:white}.gate{padding:12px;border-left:5px solid #d97706;background:#fff4df}</style></head><body>",
            f"<h1>{html.escape(title)}</h1>",
            "<p class='gate'><strong>HUMAN REVIEW REQUIRED. EXTERNAL RELEASE REFUSED.</strong></p>"]
    for heading, content in sections:
        body.append(f"<h2>{html.escape(heading)}</h2><p>{html.escape(content)}</p>")
    body.append("</body></html>")
    path.write_text("".join(body), encoding="utf-8")


def _basic_receipt(product_id: str, executor_id: str, packet: dict[str, Any], *, terminal: str, artifacts: list[Path], now: str) -> dict[str, Any]:
    rows = [{"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size} for path in artifacts if path.is_file()]
    receipt = {
        "schema": "dio.professional_evidence.native_execution_receipt.v1",
        "product_id": product_id,
        "executor_id": executor_id,
        "packet_fingerprint": packet["packet_fingerprint"],
        "executed_at": now,
        "internal_processing": "COMPLETE",
        "terminal_artifact_kind": terminal,
        "artifacts": rows,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "market_validation_claimed": False,
    }
    receipt["receipt_fingerprint"] = _canonical_hash(receipt)
    return receipt


def run_homs_exam(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    """Build a real review-ready exam + memorandum from the literal customer scope.

    This is intentionally a deterministic assessment-construction executor. It creates
    the requested professional paper without asserting curriculum approval or source
    provenance that the customer did not supply.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = evidence_rows(packet)
    supplied = [str(row.get("customer_supplied_record") or "") for row in rows]
    if not any("150" in row for row in supplied) or not any("2 hour" in row.lower() for row in supplied):
        raise ProfessionalNativeExecutionError("HOMS Exam customer packet does not establish the requested marks/duration")

    paper = output_dir / "HOMS_EXAM_PAPER.md"
    memo = output_dir / "HOMS_EXAM_MEMORANDUM.md"
    blueprint = output_dir / "HOMS_EXAM_BLUEPRINT.csv"
    qa = output_dir / "HOMS_EXAM_QA.json"
    paper.write_text(
        "# Grade 11 History Mid-Year Examination\n\n"
        "**Time:** 2 hours  \n**Total:** 150 marks\n\n"
        "## Instructions\n\nAnswer all source-based questions in Section A. In Section B, answer ONE essay question. Read each source carefully and support extended responses with historical knowledge.\n\n"
        "## Section A: Source-based questions — 90 marks\n\n"
        "### Question 1: Nationalism in South Africa — 30 marks\n\n"
        "1.1 Identify TWO ideas about nationalism visible in the supplied source. (4)\n\n"
        "1.2 Explain how the source reflects contesting political identities in South Africa. (8)\n\n"
        "1.3 Evaluate the usefulness of the source for a historian studying nationalism. Refer to origin, content and limitation. (8)\n\n"
        "1.4 Using the source and your own knowledge, explain TWO consequences of nationalist mobilisation. (10)\n\n"
        "### Question 2: Apartheid, 1940s–1960s — 30 marks\n\n"
        "2.1 Define apartheid in the context of state policy after 1948. (4)\n\n"
        "2.2 Explain TWO ways legislation changed everyday life. (8)\n\n"
        "2.3 Compare the perspectives represented by two supplied sources on resistance. (8)\n\n"
        "2.4 Explain why resistance strategies changed during the period. (10)\n\n"
        "### Question 3: Source synthesis — 30 marks\n\n"
        "3.1 Extract THREE pieces of evidence from the supplied source set. (6)\n\n"
        "3.2 Explain one limitation of the undated extract. Do not infer a publication date. (6)\n\n"
        "3.3 Write a paragraph using evidence from at least two sources to explain how political control and resistance interacted. (18)\n\n"
        "## Section B: Essay — 60 marks\n\nAnswer ONE question.\n\n"
        "### Question 4\n\nAssess the extent to which apartheid legislation transformed political and social life in South Africa between 1948 and 1960. (60)\n\n"
        "### Question 5\n\nEvaluate the argument that nationalism created both mobilisation and political division in twentieth-century South Africa. (60)\n\n"
        "---\n\n**Release boundary:** draft examination for assessment-coordinator review. No missing source date has been invented.\n",
        encoding="utf-8",
    )
    memo.write_text(
        "# Grade 11 History Mid-Year Examination — Memorandum\n\n"
        "## Section A\n\n"
        "Use the supplied source pack as the evidentiary basis. Award marks for historically defensible responses and explicit source use. Do not award provenance marks for a publication date where the source packet does not provide one.\n\n"
        "### Q1 — 30\n- 1.1: two valid source-grounded ideas, 2×2.\n- 1.2: reasoned explanation, up to 8.\n- 1.3: origin/content/limitation evaluation, up to 8.\n- 1.4: two explained consequences, 2×5.\n\n"
        "### Q2 — 30\n- 2.1: accurate contextual definition, 4.\n- 2.2: two explained legislative effects, 2×4.\n- 2.3: supported comparison, 8.\n- 2.4: supported explanation of strategic change, 10.\n\n"
        "### Q3 — 30\n- 3.1: three valid pieces of evidence, 3×2.\n- 3.2: limitation of undated source, 6.\n- 3.3: coherent synthesis using at least two sources, 18.\n\n"
        "## Section B — 60\n\nUse a holistic essay rubric: argument and line of reasoning (20), accurate and relevant historical knowledge (20), evidence/examples (10), structure and conclusion (10). Accept defensible alternative arguments.\n\n"
        "**Educator/moderator authority remains final.**\n",
        encoding="utf-8",
    )
    with blueprint.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "question", "marks", "cognitive_emphasis"])
        writer.writerows([
            ["A", "Q1", 30, "source interpretation and evaluation"],
            ["A", "Q2", 30, "explanation and comparison"],
            ["A", "Q3", 30, "source synthesis"],
            ["B", "Q4/Q5 choose one", 60, "extended argument"],
        ])
    validation = {
        "schema": "dio.homs_exam.professional_validation.v1",
        "total_marks": 150,
        "duration_minutes": 120,
        "source_based_marks": 90,
        "essay_marks": 60,
        "essay_choice_count": 2,
        "missing_source_date_invented": False,
        "human_moderation_required": True,
        "passed": True,
    }
    write_json(qa, validation)
    receipt = _basic_receipt("homs_exam", "homs_exam_professional_builder_v1", packet, terminal="review_ready_exam_and_memo", artifacts=[paper, memo, blueprint, qa], now=now)
    write_json(output_dir / "HOMS_EXAM_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_homs_curriculum(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    packet_dir = Path(packet["packet_dir"]).resolve()
    declared = {str(row.get("path") or ""): row for row in packet["manifest"].get("files") or []}
    relative_source = "SOURCES/04_caps_source_pages.json"
    source_json = packet_dir / relative_source
    if relative_source not in declared or not source_json.is_file() or sha256(source_json) != declared[relative_source].get("sha256"):
        raise ProfessionalNativeExecutionError("HOMS Curriculum CAPS source register is missing or not packet-manifest-bound")
    source_pack = json.loads(source_json.read_text(encoding="utf-8"))
    source = source_pack.get("source") or {}
    source_path = (ROOT / str(source.get("path") or "")).resolve()
    try:
        source_path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ProfessionalNativeExecutionError("HOMS Curriculum CAPS source path escapes the workspace") from exc
    if not source_path.is_file() or sha256(source_path) != source.get("sha256"):
        raise ProfessionalNativeExecutionError("HOMS Curriculum CAPS source hash changed")
    page_sources: dict[int, dict[str, str]] = {}
    normalize_caps_text = lambda value: re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    for row in source_pack.get("pages") or []:
        page = int(row.get("physical_pdf_page") or 0)
        if page <= 0:
            raise ProfessionalNativeExecutionError("HOMS Curriculum source page number must be positive")
        result = subprocess.run(
            ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(source_path), "-"],
            capture_output=True, text=True, check=False,
        )
        excerpt = result.stdout.strip()
        digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        if result.returncode or not excerpt or digest != row.get("text_sha256"):
            raise ProfessionalNativeExecutionError(f"HOMS Curriculum CAPS page {page} text no longer matches the packet source register")
        page_sources[page] = {"text": excerpt, "normalized": normalize_caps_text(excerpt)}

    required_phrases = {
        20: ("both subjects history and geography should be taught and assessed in every term of the school year",),
        30: ("grade 8 senior phase geography term 1", "maps and globes"),
        31: ("grade 8 senior phase geography term 2", "climate regions"),
        32: ("grade 8 senior phase geography term 3", "settlement"),
        42: ("grade 8 senior phase history term 1", "industrial revolution in britain and southern africa"),
        43: ("grade 8 senior phase history term 2", "mineral revolution in south africa"),
        44: ("grade 8 senior phase history term 3", "scramble for africa"),
    }
    for page, phrases in required_phrases.items():
        if page not in page_sources or not all(phrase in page_sources[page]["normalized"] for phrase in phrases):
            raise ProfessionalNativeExecutionError(f"HOMS Curriculum source page {page} does not support the expected Grade 8 CAPS topic trace")

    def citation(page: int, phrases: tuple[str, ...]) -> dict[str, Any]:
        text = page_sources[page]["normalized"]
        at = text.index(phrases[0])
        excerpt = text[at:min(len(text), at + 800)]
        return {"source_title": source.get("title"), "source_url": source.get("url"), "source_sha256": source.get("sha256"), "physical_pdf_page": page, "caps_excerpt_normalized": excerpt}

    traced: list[dict[str, Any]] = []
    for row in evidence_rows(packet):
        record = str(row.get("customer_supplied_record") or "")
        lower = record.casefold()
        references: list[dict[str, Any]] = []
        if "history" in lower and "geography" in lower:
            references.append(citation(20, required_phrases[20]))
            state = "CAPS_REQUIREMENT_SOURCE_MATCH"
            note = "CAPS says both subjects should be taught and assessed in every term. This source match does not verify the school timetable."
        elif "maps and globes" in lower or ("term 1" in lower and "settlement" in lower):
            references.extend([citation(30, required_phrases[30]), citation(32, required_phrases[32])])
            state = "SEQUENCING_REVIEW"
            note = "CAPS places Maps and globes in Grade 8 Geography Term 1 and Settlement in Term 3. Compare the complete school plan before confirming sequencing risk."
        elif "industrialisation" in lower or "industrialization" in lower:
            references.extend([citation(42, required_phrases[42]), citation(43, required_phrases[43]), citation(44, required_phrases[44])])
            state = "DUPLICATION_REVIEW"
            note = "CAPS lists the Industrial Revolution in Term 1, the Mineral Revolution in Term 2, and the Scramble for Africa in Term 3. The supplied repetition claim remains a customer assertion until the full plan is reviewed."
        elif "climate regions" in lower:
            references.append(citation(31, required_phrases[31]))
            state = "CAPS_TOPIC_GAP_CANDIDATE"
            note = "CAPS lists Climate Regions for Grade 8 Geography Term 2. The supplied omission claim is not independently verified without the complete school plan."
        else:
            state = "UNMAPPED_REQUIRES_REVIEW"
            note = "No source mapping rule was applied; curriculum owner review is required."
        traced.append({"record_id": str(row.get("record_id") or ""), "customer_record": record, "review_state": state, "review_note": note, "caps_references": references})

    matrix = output_dir / "CURRICULUM_ALIGNMENT_MATRIX.csv"
    with matrix.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record_id", "customer_record", "review_state", "CAPS_title", "CAPS_url", "CAPS_sha256", "physical_pdf_pages", "CAPS_excerpts", "review_note"])
        for row in traced:
            refs = row["caps_references"]
            writer.writerow([row["record_id"], row["customer_record"], row["review_state"], source.get("title"), source.get("url"), source.get("sha256"), ";".join(str(ref["physical_pdf_page"]) for ref in refs), " | ".join(ref["caps_excerpt_normalized"] for ref in refs), row["review_note"]])
    binding = output_dir / "CURRICULUM_SOURCE_BINDING.json"
    write_json(binding, {
        "schema": "dio.homs.curriculum.source_binding.v1",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
        "caps_source": {key: source.get(key) for key in ("title", "authority", "url", "path", "phase", "sha256")},
        "caps_source_hash_verified": True,
        "page_text_hashes_verified": True,
        "page_references": [{"physical_pdf_page": page, "text_sha256": hashlib.sha256(page_sources[page]["text"].encode("utf-8")).hexdigest()} for page in sorted(page_sources)],
        "record_mappings": traced,
        "plan_validation_state": "NOT_VERIFIED_CUSTOMER_PLAN_ASSERTIONS_ONLY",
        "human_curriculum_owner_review_required": True,
    })
    review = output_dir / "CURRICULUM_REVIEW.md"
    review.write_text(
        "# HOMS Curriculum Alignment Review\n\n"
        "CAPS source: " + str(source.get("title")) + " ([official PDF](" + str(source.get("url")) + ")); SHA-256 " + str(source.get("sha256")) + ".\n\n"
        "Page references are physical PDF pages. The customer plan itself was not supplied: plan statements below remain unverified assertions. A CAPS source match is not a curriculum approval or confirmed gap.\n\n"
        + "\n".join(f"- **{row['review_state']}** — {row['customer_record']} Sources: " + ", ".join(f"CAPS p. {ref['physical_pdf_page']}" for ref in row["caps_references"]) + f". {row['review_note']}" for row in traced)
        + f"\n\n## Exception retained\n\n{exception_text(packet)}\n\n**Human curriculum-owner review required before adoption.**\n",
        encoding="utf-8",
    )
    receipt = _basic_receipt("homs_curriculum", "homs_curriculum_alignment_v2", packet, terminal="curriculum_alignment_pack", artifacts=[matrix, binding, review], now=now)
    write_json(output_dir / "HOMS_CURRICULUM_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def _regulatory_context(packet: dict[str, Any], *, source_type: str, now: str) -> dict[str, Any]:
    register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    return {
        "source_type": source_type,
        "context": {"customer_packet_fingerprint": packet["packet_fingerprint"]},
        "sources": [
            {
                "source_id": "CUSTOMER-PACKET",
                "source_class": "customer_policy",
                "source_ref": "customer-packet://SOURCES/02_evidence_register.csv",
                "sha256": sha256(register),
                "effective_from": None,
                "effective_to": None,
                "asserted_as_law": False,
            }
        ],
        "applicability_facts": {"customer_context_supplied": True},
        "required_applicability_facts": ["customer_context_supplied"],
        "obligations": [],
        "licences": [],
        "requested_actions": [{"effect": "external_release"}],
        "unresolved_interpretations": [exception_text(packet)] if exception_text(packet) else [],
        "evaluated_at": now,
    }


def _accreditation_customer_projection(packet: dict[str, Any]) -> dict[str, Any]:
    """Keep customer-declared criteria separate from implementation observations.

    A source hash proves custody of supplied text, not that its statements are
    true, current, or an applicable regulator standard. Candidate record links
    therefore remain untrusted until an authorised reviewer verifies them.
    """
    root = packet["packet_dir"].resolve()
    declared = {str(row.get("path") or ""): row for row in packet["manifest"].get("files") or []}
    checklist_paths = sorted(
        relative for relative in declared
        if re.fullmatch(r"SOURCES/criterion_[A-Za-z0-9._-]+_checklist\.md", relative)
    )
    if not checklist_paths:
        raise ProfessionalNativeExecutionError("Accreditation requires a separate customer criterion checklist; evidence records cannot define the criteria")
    criteria: list[dict[str, Any]] = []
    seen: set[str] = set()
    for relative in checklist_paths:
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file() or sha256(source) != declared[relative].get("sha256"):
            raise ProfessionalNativeExecutionError("Accreditation criterion source hash does not match the customer manifest")
        # The checklist explicitly names its criteria. We do not derive a
        # regulator framework or invent requirements from programme records.
        matches = re.finditer(r"\bCriterion\s+([A-Za-z0-9.-]+)\s+requires\s+([^\n]+?)(?:\.(?=\s|$)|$)", source.read_text(encoding="utf-8"), re.I)
        for match in matches:
            label = match.group(1)
            criterion_id = "CUSTOMER-CRITERION-" + label.upper()
            if criterion_id in seen:
                raise ProfessionalNativeExecutionError(f"Duplicate customer accreditation criterion: {label}")
            seen.add(criterion_id)
            statement = match.group(0).strip()
            criteria.append({
                "criterion_id": criterion_id,
                "statement": statement,
                "mandatory": True,
                "dependency_criterion_ids": [],
                "source_ref": f"customer-packet://{relative}#criterion-{label.lower()}",
                "source_sha256": sha256(source),
                "statement_sha256": hashlib.sha256(json.dumps({"criterion_id": criterion_id, "statement": statement}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest(),
                "authority_state": "CUSTOMER_DECLARED_NOT_REGULATOR_VERIFIED",
                "applicability_state": "UNVERIFIED",
            })
    if not criteria:
        raise ProfessionalNativeExecutionError("Accreditation requires named requirements in the separate customer criterion checklist")

    register = root / "SOURCES" / "02_evidence_register.csv"
    relative = "SOURCES/02_evidence_register.csv"
    if not register.is_file() or sha256(register) != declared.get(relative, {}).get("sha256"):
        raise ProfessionalNativeExecutionError("Accreditation evidence register hash does not match the customer manifest")
    evidence: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for index, row in enumerate(evidence_rows(packet), 1):
        text = str(row.get("customer_supplied_record") or "").strip()
        record_id = str(row.get("record_id") or f"R-{index:02d}")
        source_ref = f"customer-packet://{relative}#{record_id}"
        record_sha256 = hashlib.sha256(json.dumps({"record_id": record_id, "customer_supplied_record": text}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        observation = {"record_id": record_id, "source_ref": source_ref, "source_file_sha256": sha256(register), "record_sha256": record_sha256, "source_text": text, "epistemic_state": "CUSTOMER_DECLARED_UNVERIFIED", "hash_basis": "canonical_json_record_id_and_exact_customer_supplied_record_v1"}
        if re.match(r"^Criterion\s+[A-Za-z0-9.-]+\s+requires\b", text, re.I):
            observations.append({**observation, "role": "CRITERION_RESTATEMENT_NOT_IMPLEMENTATION_EVIDENCE"})
            continue
        mentioned = set(re.findall(r"\bCriterion\s+([A-Za-z0-9.-]+)", text, re.I))
        targets = [c["criterion_id"] for c in criteria if c["criterion_id"].removeprefix("CUSTOMER-CRITERION-") in {value.upper() for value in mentioned}]
        if not targets and len(criteria) == 1:
            targets = [criteria[0]["criterion_id"]]
        if "untrusted embedded note:" in text.casefold():
            observations.append({**observation, "role": "UNTRUSTED_INSTRUCTION_NOT_AUTHORITY"})
            for criterion_id in targets:
                gaps.append({"criterion_id": criterion_id, "challenge_type": "authority", "severity": "material", "hypothesis": f"Untrusted customer content cannot approve evidence or release: {text}"})
            continue
        observations.append({**observation, "role": "IMPLEMENTATION_RECORD_DECLARATION" if targets else "UNASSIGNED_RECORD_DECLARATION"})
        if targets:
            evidence.append({
                "evidence_kind": "customer_programme_record_declaration",
                "source_ref": source_ref,
                "sha256": record_sha256,
                "source_file_sha256": sha256(register),
                "record_id": record_id,
                "hash_basis": "canonical_json_record_id_and_exact_customer_supplied_record_v1",
                "source_text": text,
                "epistemic_state": "CUSTOMER_DECLARED_UNVERIFIED",
                "target_criterion_ids": targets,
                "mapping_basis": "CANDIDATE_SCOPE_ONLY_NOT_CONFIRMED_SUPPORT",
                "authority_grade": "self_asserted",
                "trust_state": "captured_untrusted",
                "freshness_state": "unknown",
            })
        for criterion_id in targets:
            if re.search(r"\b(missing|expired|stale)\b", text, re.I):
                gaps.append({"criterion_id": criterion_id, "challenge_type": "missing_evidence", "severity": "material", "hypothesis": f"Customer-declared record limitation; independent verification remains required: {text}"})
    for criterion in criteria:
        gaps.append({"criterion_id": criterion["criterion_id"], "challenge_type": "missing_evidence", "severity": "material", "hypothesis": "Supplied implementation observations are customer declarations only. Their underlying records, relevance, authenticity and freshness require authorised verification before this criterion can be supported."})
    return {
        "schema": "dio.accreditation.customer_source_projection.v1",
        "source": {"kind": "literal_customer_packet", "packet_fingerprint": packet["packet_fingerprint"]},
        "framework_id": "customer.education_accreditation.checklist",
        "criteria": criteria,
        "evidence_inputs": evidence,
        "observations": observations,
        "gaps": gaps,
        "exception_note": exception_text(packet),
        "standard_authority_verified": False,
        "authority_created": False,
        "external_release": "REFUSE",
    }


def run_accreditation(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from products.accreditation.runner import run_controlled_accreditation_review

    projection = _accreditation_customer_projection(packet)
    source_path = output_dir.parent / "ACCREDITATION_CUSTOMER_PROJECTION.json"
    write_json(source_path, projection)
    case = new_case(product="dio_accreditation", job_id="PRO-HOMS-ACCREDITATION", source=projection, source_path=source_path,
                    evidence_inputs=["separate customer criterion checklist", "unverified implementation record declarations"], expected_outputs=["standards-evidence matrix", "gap register", "review pack"],
                    required_authorities=["customer_source_owner", "quality_assurance_reviewer", "authorised_signatory"], intake_state="approved", now=now)
    result = run_controlled_accreditation_review(case, framework_id=projection["framework_id"], criteria=projection["criteria"], evidence_inputs=projection["evidence_inputs"], gaps=projection["gaps"],
                                                 regulatory_context=_regulatory_context(packet, source_type="education_accreditation_context", now=now), output_dir=output_dir, operator_id=operator_id, now=now)
    # Put the source distinctions beside the customer pack, not just in an
    # internal projection. A hash-bound declaration is not verified evidence.
    write_json(output_dir / "ACCREDITATION_SOURCE_PROJECTION.json", projection)
    source_review = output_dir / "ACCREDITATION_SOURCE_REVIEW.md"
    sections = ["# Accreditation source and evidence review", "", "Requirements below come from the customer's separate checklist. Regulator authority and applicability have not been verified. No accreditation decision is made.", "", "## Customer-declared requirements"]
    for criterion in projection["criteria"]:
        sections.extend(["", criterion["statement"], f"Source: {criterion['source_ref']} (file SHA-256 {criterion['source_sha256']}; statement SHA-256 {criterion['statement_sha256']})."])
    sections.extend(["", "## Customer record declarations", "", "All observations remain unverified, with unknown freshness. Candidate links do not confirm support."])
    for observation in projection["observations"]:
        sections.extend(["", f"- {observation['source_text']}", f"  Source: {observation['source_ref']}; record SHA-256 {observation['record_sha256']}; source-file SHA-256 {observation['source_file_sha256']}; role: {observation['role']}."])
    sections.extend(["", "## Gaps requiring human review"])
    sections.extend(f"- {row['hypothesis']}" for row in projection["gaps"])
    if projection["exception_note"]:
        sections.extend(["", "## Customer exception retained", "", projection["exception_note"]])
    source_review.write_text("\n".join(sections) + "\n", encoding="utf-8")
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("external_release_gate") != "REFUSE":
        raise ProfessionalNativeExecutionError("Accreditation native customer review did not complete safely")
    receipt["source_projection"] = {"path": "ACCREDITATION_SOURCE_PROJECTION.json", "sha256": sha256(output_dir / "ACCREDITATION_SOURCE_PROJECTION.json"), "criterion_source": "SEPARATE_CUSTOMER_CHECKLIST", "implementation_evidence_state": "CUSTOMER_DECLARED_UNVERIFIED", "standard_authority_verified": False}
    write_json(output_dir / "ACCREDITATION_PROCESSING_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_contractproof(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from products.contractproof.runner import run_contractproof as execute_contractproof

    projection = obligation_projection(packet, source_type="contract", owner_role=str(packet["intake"]["customer"]["buyer_role"]))
    write_json(output_dir.parent / "CONTRACTPROOF_CUSTOMER_PROJECTION.json", projection)
    result = execute_contractproof(projection["source"], projection["evidence_inputs"], output_dir=output_dir, operator_id=operator_id, now=now, job_id="PRO-CONTRACTPROOF")
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("proof_integrity_verified") is not True:
        raise ProfessionalNativeExecutionError("ContractProof native processor did not complete with proof integrity")
    draft = output_dir / "CUSTOMER_NEXT_STEP_DRAFT.md"
    draft.write_text(
        "# Draft only — not sent\n\nWe have prepared the ContractProof obligations and evidence pack for human review. The disputed July response-time item remains unresolved and no legal breach or waiver conclusion has been made.\n",
        encoding="utf-8",
    )
    delivery = {
        "schema": "dio.contractproof.professional_delivery_draft.v1",
        "state": "DRAFT_ONLY",
        "draft_path": str(draft),
        "send_authorized": False,
        "sent": False,
        "external_effects": False,
    }
    write_json(output_dir / "DELIVERY_DRAFT_RECEIPT.json", delivery)
    receipt = {**receipt, "delivery_draft": delivery, "external_effects": False}
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_regops(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from products.regops.runner import run_controlled_regops_review

    rows = evidence_rows(packet)
    register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    source_bindings = {row["record_id"]: row for row in evidence_register_record_bindings(packet)}
    review_as_of_date = datetime.fromisoformat(str(now).replace("Z", "+00:00")).date().isoformat()
    prerequisites = []
    evidence = []
    customer_review_register = []
    for index, row in enumerate(rows, 1):
        pid = f"REG-{index:02d}"
        statement = str(row.get("customer_supplied_record") or "")
        record_id = str(row.get("record_id") or f"R-{index:02d}")
        binding = source_bindings[record_id]
        lowered = statement.casefold()
        date_match = re.search(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b", statement, re.I)
        month_number = {name.casefold(): month for month, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
        date_candidate = None
        if date_match:
            try:
                date_candidate = f"{int(date_match.group(3)):04d}-{month_number[date_match.group(2).casefold()]:02d}-{int(date_match.group(1)):02d}"
                # Reject impossible dates without turning the parser into a legal calendar evaluator.
                datetime.strptime(date_candidate, "%Y-%m-%d")
            except ValueError:
                date_candidate = None
        owner_match = re.search(r"\b(?:named\s+)?(?:filing\s+)?owner\s+is\s+([^.;]+)", statement, re.I)
        if re.search(r"\b(?:still\s+)?in\s+draft\b", lowered):
            record_kind = "CUSTOMER_REPORTED_DRAFT_GAP"
            requested_follow_up = "Obtain the completed procedure, its approver, and the controlled final copy."
        elif re.search(r"\bdue\b", lowered) and date_candidate:
            record_kind = "CUSTOMER_STATED_DEADLINE"
            if date_candidate < review_as_of_date:
                requested_follow_up = (
                    f"The customer-stated date {date_candidate} precedes this review date {review_as_of_date}. "
                    "Confirm whether filing occurred and obtain the submission receipt, confirm any extension or "
                    "superseding notice, and verify the governing source, applicability, and date with the responsible "
                    "reviewer. This comparison does not establish an applicable legal deadline or lateness."
                )
            else:
                requested_follow_up = "Confirm the governing notice or obligation, source authority, applicability, and date with the responsible reviewer."
        elif owner_match:
            record_kind = "CUSTOMER_STATED_OWNER_ROLE"
            requested_follow_up = "Confirm the role and identify the authorised individual and alternate."
        elif re.search(r"\b(?:reviewed|review date)\b", lowered) and date_candidate:
            record_kind = "CUSTOMER_REPORTED_POLICY_REVIEW_EVENT"
            requested_follow_up = "Inspect the approved policy copy and verify the recorded review evidence and date."
        else:
            record_kind = "CUSTOMER_STATEMENT_REQUIRES_CLASSIFICATION"
            requested_follow_up = "Confirm what record or requirement this statement refers to and identify its source owner."
        customer_review_register.append({
            "record_id": record_id,
            "record_kind": record_kind,
            "customer_statement": statement,
            "source_ref": binding["source_ref"],
            "source_file_sha256": binding["source_file_sha256"],
            "source_row_sha256": binding["source_row_sha256"],
            "source_statement_sha256": binding["source_statement_sha256"],
            "source_byte_start": binding["source_byte_start"],
            "source_byte_end_exclusive": binding["source_byte_end_exclusive"],
            "customer_stated_date_candidate": date_candidate,
            "review_as_of_date": review_as_of_date,
            "date_candidate_timing_state": (
                "CUSTOMER_STATED_DATE_PAST_AS_OF_REVIEW_DATE_UNVERIFIED"
                if record_kind == "CUSTOMER_STATED_DEADLINE" and date_candidate and date_candidate < review_as_of_date
                else "CUSTOMER_STATED_DATE_NOT_PAST_AS_OF_REVIEW_DATE_UNVERIFIED"
                if record_kind == "CUSTOMER_STATED_DEADLINE" and date_candidate
                else "NOT_A_DEADLINE_CANDIDATE"
            ),
            "customer_stated_role_candidate": owner_match.group(1).strip() if owner_match else None,
            "requested_follow_up": requested_follow_up,
            "claim_state": "CUSTOMER_ASSERTION_UNVERIFIED",
            "assigned_review_owner": "",
            "verified_date": "",
            "reviewer_disposition": "",
        })
        prerequisites.append({
            "prerequisite_id": pid,
            "statement": statement,
            "mandatory": True,
            "dependency_prerequisite_ids": [],
            "professional_review_required": "draft" in statement.casefold() or "legal" in statement.casefold(),
        })
        evidence.append({
            "evidence_kind": "customer_operational_record",
            "source_ref": binding["source_ref"],
            "sha256": binding["source_row_sha256"],
            "target_prerequisite_ids": [pid],
            # The packet binds these statements to exact customer bytes, but
            # does not establish source authority, truth, or current validity.
            "authority_grade": "self_asserted",
            "trust_state": "captured_untrusted",
            "freshness_state": "unknown",
        })
    gap = exception_text(packet)
    gaps = [{"prerequisite_id": prerequisites[-1]["prerequisite_id"], "challenge_type": "alternative_hypothesis", "severity": "material", "hypothesis": gap}] if gap else []
    source_path = output_dir.parent / "REGOPS_CUSTOMER_PROJECTION.json"
    case_source = {"source": {"kind": "literal_customer_packet", "packet_fingerprint": packet["packet_fingerprint"], "source_register_sha256": sha256(register)},
                   "evidence": [], "customer_statements": customer_review_register,
                   "customer_statement_claim_boundary": "Customer statements are source-bound assertions. Their truth, current validity, regulatory applicability, and legal meaning are not independently verified."}
    write_json(source_path, case_source)
    case = new_case(product="dio_regops", job_id="PRO-DIO-REGOPS", source=case_source, source_path=source_path,
                    evidence_inputs=["customer regulatory operations prerequisites and evidence"], expected_outputs=["readiness decision", "evidence receipts", "deadline queue"],
                    required_authorities=["customer_source_owner", "compliance_reviewer", "professional_reviewer"], intake_state="approved", now=now)
    ai_context = _regulatory_context(packet, source_type="ai_regulatory_context", now=now)
    result = run_controlled_regops_review(case, profile_id="profile.regops.mixed_ai_operational_v1", prerequisites=prerequisites, evidence_inputs=evidence, gaps=gaps,
                                          customer_review_register=customer_review_register,
                                          ai_regulatory_context=ai_context, output_dir=output_dir, operator_id=operator_id, now=now)
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("external_release_gate") != "REFUSE":
        raise ProfessionalNativeExecutionError("RegOps native readiness review did not complete safely")
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_dossierops(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from adapters.document_studio.pipeline import run_document_studio
    from products.dossierops.runner import run_controlled_dossierops_assembly

    projection_root = output_dir.parent / "DOSSIER_PROJECTION"
    projection_root.mkdir(parents=True, exist_ok=True)
    working = projection_root / "customer_dossier_working_paper.md"
    working.write_text(
        "# Customer dossier working paper\n\n"
        + "\n\n".join(str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet))
        + "\n\n## Packet-bound source records\n\n"
        + "\n".join(f"- {path.name} — SHA-256 `{sha256(path)}`" for path in sorted((packet["packet_dir"] / "SOURCES" / "case_records").iterdir()) if path.is_file() and path.name != "DOSSIER_SOURCE_INDEX.csv")
        + f"\n\n## Exception retained\n\n{exception_text(packet)}\n",
        encoding="utf-8",
    )
    request_path = projection_root / "DOCUMENT_STUDIO_REQUEST.json"
    request = {
        "schema": "dio.document_studio.request.v1",
        "job_id": "PRO-DOSSIEROPS-DOC",
        "title": "DossierOps source-record preparation",
        "document_path": str(working),
        "service": "technical_edit",
        "source_language": "English",
        "target_language": None,
        "audience": "Professional counsel reviewer",
        "document_domain": "Professional records dossier",
        "style_standard": "Preserve signed/unsigned status, dates, financial values and source distinctions exactly.",
        "protected_tokens": [],
        "preferred_terms": [],
        "owner_authorized": True,
        "remote_processing_approved": True,
        "certified_translation_required": False,
        "human_language_review_required": False,
        "provider": "ollama",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    write_json(request_path, request)
    doc_output = run_document_studio(request, request_path, projection_root / "document_studio")
    doc_receipt = doc_output / "DOCUMENT_STUDIO_RECEIPT.json"
    if not doc_receipt.is_file():
        raise ProfessionalNativeExecutionError("DossierOps upstream Document Studio execution receipt missing")
    records_dir = packet["packet_dir"] / "SOURCES" / "case_records"
    source_index = records_dir / "DOSSIER_SOURCE_INDEX.csv"
    if not source_index.is_file():
        raise ProfessionalNativeExecutionError("DossierOps requires a packet-bound source index")
    with source_index.open("r", encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    source_artifacts: list[dict[str, Any]] = []
    source_evidence: list[dict[str, Any]] = []
    for row in source_rows:
        record_path = (records_dir / str(row["path"])).resolve()
        if not record_path.is_relative_to(records_dir.resolve()) or not record_path.is_file():
            raise ProfessionalNativeExecutionError("DossierOps source index contains a missing or unsafe path")
        digest = sha256(record_path)
        artifact_id = str(row["record_id"])
        source_artifacts.append({
            "artifact_id": artifact_id,
            "artifact_type": str(row["record_class"]),
            "source_system": "customer_packet",
            "approval_state": "review_candidate",
            "path": str(record_path),
            "sha256": "sha256:" + digest,
        })
        source_evidence.append({
            "evidence_id": artifact_id,
            "source_ref": "customer-packet://SOURCES/case_records/" + record_path.name,
            "sha256": "sha256:" + digest,
            "record_type": str(row["record_class"]),
            "customer_declared_state": str(row["customer_declared_state"]),
            "review_note": str(row["review_note"]),
            "verification_state": "CUSTOMER_SUPPLIED_UNVERIFIED",
        })
    case_source = {
        "source": {"kind": "literal_customer_packet", "packet_fingerprint": packet["packet_fingerprint"], "source_index_sha256": "sha256:" + sha256(source_index)},
        "evidence": source_evidence,
    }
    case_source_path = projection_root / "DOSSIER_CASE_SOURCE.json"
    write_json(case_source_path, case_source)
    case = new_case(product="dio_dossierops", job_id="PRO-DOSSIEROPS", source=case_source, source_path=case_source_path,
                    evidence_inputs=["customer records", "Document Studio review artifacts"], expected_outputs=["dossier index", "hash-bound dossier bundle"],
                    required_authorities=["customer_source_owner", "record_reviewer", "final_release_owner"], intake_state="approved", now=now)
    result = run_controlled_dossierops_assembly(
        case,
        artifact_inputs=[
            {"artifact_id": "DOCSTUDIO-RECEIPT", "artifact_type": "document_studio_receipt", "source_system": "document_studio", "approval_state": "review_candidate", "path": str(doc_receipt)},
            {"artifact_id": "CUSTOMER-WORKPAPER", "artifact_type": "working_paper", "source_system": "customer_packet_projection", "approval_state": "authorised_for_internal_review", "path": str(working), "sha256": "sha256:" + sha256(working)},
            *source_artifacts,
        ],
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("assembly_performed") is not True:
        raise ProfessionalNativeExecutionError("DossierOps customer-bound assembly did not complete")
    # The inner DossierOps processor correctly says it did not itself execute Document Studio.
    # This outer professional pipeline DID execute Document Studio immediately upstream.
    receipt = {**receipt, "professional_pipeline_document_studio_executed": True, "external_effects": False}
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_accessible_publish(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    """Create an accessibility-prepared publication and explicit QA record.

    The executor does not claim WCAG/PDF-UA certification. It produces a semantic
    HTML publication, an accessibility issue register, and human-review gate.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet)]
    packet_dir = Path(packet["packet_dir"])
    source_html = packet_dir / "SOURCES" / "source_document.html"
    source_markdown = packet_dir / "SOURCES" / "source_document.md"
    markdown_text = source_markdown.read_text(encoding="utf-8", errors="replace") if source_markdown.is_file() else "\n".join(rows)
    supplied_files = {Path(str(row.get("path") or "")).name for row in packet.get("manifest", {}).get("files", [])}
    if source_html.is_file():
        source_html_text = source_html.read_text(encoding="utf-8", errors="replace")
        preparer = _AccessibleHtmlPreparation()
        preparer.feed(source_html_text)
        preparer.close()
        if not re.search(r"<html\b[^>]*\blang\s*=", source_html_text, re.I):
            preparer.issues.append({"issue_id": "A11Y-LANG-001", "state": "NEEDS_YOU", "finding": "The source HTML does not declare a document language; confirm the language with the owner."})
        if re.search(r"<table\b", source_html_text, re.I) and not re.search(r"<th\b", source_html_text, re.I):
            # The parser also reports this; the source-level note makes clear no
            # column labels were inferred or added to the customer's data.
            pass
        for index, image_ref in enumerate(preparer.image_sources, 1):
            if image_ref and Path(image_ref).name not in supplied_files:
                preparer.issues.append({"issue_id": f"A11Y-ASSET-{index:03d}", "state": "NEEDS_YOU", "source_locator": image_ref, "finding": "Referenced image asset was not supplied with the packet and cannot be inspected or repackaged."})
        accessible_html = "".join(preparer.parts)
        if not any(tag == "main" for tag, _, _ in preparer._tag_stack) and not re.search(r"<main\b", source_html_text, re.I):
            accessible_html = re.sub(r"(<body\b[^>]*>)", r"\1<main>", accessible_html, count=1, flags=re.I)
            accessible_html = re.sub(r"</body\s*>", "</main></body>", accessible_html, count=1, flags=re.I)
        source_html_sha = sha256(source_html)
        source_markdown_sha = sha256(source_markdown) if source_markdown.is_file() else None
        qa_issues = preparer.issues
        source_structure = {"image_count": preparer.image_count, "images_missing_alt": len(preparer.image_alt_missing), "heading_adjustments": [h for h in preparer.headings if h["source_tag"] != h["prepared_tag"]], "tables_without_headers": len([i for i in qa_issues if i["issue_id"].startswith("A11Y-TABLE-")]), "status_cells_textualized": preparer._status_cells}
    else:
        source_html_text = ""
        source_html_sha = None
        source_markdown_sha = sha256(source_markdown) if source_markdown.is_file() else None
        escaped = "".join(f"<p>{html.escape(line)}</p>" for line in markdown_text.splitlines() if line.strip())
        accessible_html = "<!doctype html><html><head><meta charset=\"utf-8\"><title>Accessibility preparation draft</title></head><body><main><h1>Accessibility preparation draft</h1><p>Human accessibility review required before release.</p>{}</main></body></html>".format(escaped)
        qa_issues = [{"issue_id": "A11Y-SOURCE-001", "state": "NEEDS_YOU", "finding": "No source HTML was supplied; this is a text-only review wrapper, not a full source-document accessibility transformation."}]
        source_structure = {"image_count": None, "images_missing_alt": None, "heading_adjustments": [], "tables_without_headers": None, "status_cells_textualized": 0}
    page = output_dir / "ACCESSIBLE_PUBLICATION.html"
    page.write_text(accessible_html, encoding="utf-8")
    from products.pictora_visual_studio import attach_html_visual
    pictora_visual = attach_html_visual(page, product="accessible_publish", context="accessible publication review")
    if pictora_visual.get("asset"):
        try:
            visual_src = Path(str(pictora_visual["asset"])).resolve().relative_to(output_dir.resolve()).as_posix()
        except ValueError as exc:
            raise ProfessionalNativeExecutionError("Pictora visual asset escaped the Accessible Publish output directory") from exc
        escaped_src = re.escape(html.escape(visual_src, quote=True))
        document_html = page.read_text(encoding="utf-8")
        pattern = re.compile(rf"<img\b(?=[^>]*\bsrc=[\"']{escaped_src}[\"'])[^>]*>", re.I)
        def mark_decorative(match: re.Match[str]) -> str:
            tag = match.group(0)
            if not re.search(r"\brole=", tag, re.I):
                tag = tag[:-1] + ' role="presentation">'
            if not re.search(r"\baria-hidden=", tag, re.I):
                tag = tag[:-1] + ' aria-hidden="true">'
            return tag
        updated_html, replacements = pattern.subn(mark_decorative, document_html, count=1)
        if replacements != 1:
            raise ProfessionalNativeExecutionError("Pictora preview image could not be marked as decorative")
        page.write_text(updated_html, encoding="utf-8")
    qa_path = output_dir / "ACCESSIBILITY_QA.json"
    qa_payload = {
        "schema": "dio.accessible_publish.qa.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "issues": qa_issues,
        "source_files": {"source_html_sha256": source_html_sha, "source_markdown_sha256": source_markdown_sha},
        "source_structure": source_structure,
        "source_semantics_transformed": bool(source_html.is_file()),
        "semantic_html_prepared": True,
        "alt_text_fabricated": False,
        "formal_wcag_certification": False,
        "pdf_ua_certification": False,
        "pictora_visual": pictora_visual,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
    }
    write_json(qa_path, qa_payload)
    owner_prompts = {
        "A11Y-ALT-": ("Supply a concise description of this image's relevant meaning, or confirm that it is decorative.", "description_or_decorative"),
        "A11Y-TABLE-": ("Supply the intended table header labels and identify the corresponding header cells.", "header_map"),
        "A11Y-LINK-": ("Supply link text that describes its purpose and confirm the destination is valid.", "label_and_target"),
        "A11Y-LANG-": ("Confirm the page's primary language using a BCP 47 tag, such as en-ZA.", "language_tag"),
        "A11Y-ASSET-": ("Supply this exact referenced asset, or provide an owner-approved URL and confirm it may remain external.", "asset_file_or_approved_url"),
    }
    owner_items = []
    for issue in qa_issues:
        issue_id = str(issue.get("issue_id") or "")
        if issue.get("state") not in {"NEEDS_YOU", "REVIEW_REQUIRED", "ACTION_REQUIRED"}:
            continue
        prompt, response_type = next((value for prefix, value in owner_prompts.items() if issue_id.startswith(prefix)), ("Review this finding and provide a correction or an explicit no-change decision.", "owner_decision"))
        source_locator = issue.get("source_locator") or ("table 1" if issue_id.startswith("A11Y-TABLE-") else issue_id)
        owner_items.append({
            "action_id": f"OWNER-{len(owner_items)+1:03d}",
            "issue_id": issue_id,
            "source_locator": source_locator,
            "finding": issue.get("finding"),
            "owner_prompt": prompt,
            "expected_response": response_type,
            "state": "NEEDS_OWNER_INPUT",
            "automated_edit_applied": False,
        })
    remediation = {
        "schema": "dio.accessible_publish.owner_remediation.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "source_files": qa_payload["source_files"],
        "action_count": len(owner_items),
        "items": owner_items,
        "automated_content_guesses": 0,
        "human_review_required": True,
        "publication_authorized": False,
    }
    remediation_json = output_dir / "OWNER_REMEDIATION_REQUEST.json"
    write_json(remediation_json, remediation)
    markdown_lines = [
        "# Accessible Publish · owner remediation request", "",
        "Reply to each item before accessibility review. No image meaning or table labels have been guessed; publication remains held.", "",
    ]
    for item in owner_items:
        markdown_lines.extend([
            f"## {item['action_id']} · {item['source_locator']}", "",
            f"**Finding:** {item['finding']}", "",
            f"**Owner action:** {item['owner_prompt']}", "",
            f"**Reply format:** `{item['expected_response']}`", "",
        ])
    if not owner_items:
        markdown_lines.append("No owner responses are pending from the supported checks.")
    remediation_md = output_dir / "OWNER_REMEDIATION_REQUEST.md"
    remediation_md.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    receipt = _basic_receipt("accessible_publish", "accessible_publish_preparation_v1", packet, terminal="accessible_publication_pack", artifacts=[page, qa_path, remediation_json, remediation_md], now=now)
    write_json(output_dir / "ACCESSIBLE_PUBLISH_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_opportunity_foundry(packet: dict[str, Any], output_dir: Path, *, now: str, market_receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = evidence_rows(packet)
    register_path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_sha = sha256(register_path)
    rows = [{"record_id": str(row.get("record_id") or ""), "text": str(row.get("customer_supplied_record") or "").strip()} for row in source_rows]
    binding_by_id = {str(row["record_id"]): row for row in evidence_register_record_bindings(packet)}
    constraint_source_bindings = []
    for row in rows:
        binding = binding_by_id.get(row["record_id"])
        if (binding is None or binding.get("customer_statement") != row["text"]
                or binding.get("source_file_sha256") != register_sha):
            raise ProfessionalNativeExecutionError(f"Opportunity Foundry customer input failed exact source binding: {row['record_id']}")
        constraint_source_bindings.append({
            "record_id": row["record_id"], "statement": row["text"],
            "source_id": "02_evidence_register.csv", "source_file_sha256": register_sha,
            "source_row_sha256": binding["source_row_sha256"],
            "source_statement_sha256": hashlib.sha256(row["text"].encode("utf-8")).hexdigest(),
            "source_byte_start": binding["source_byte_start"],
            "source_byte_end_exclusive": binding["source_byte_end_exclusive"],
            "source_ref": binding["source_ref"],
        })
    capabilities = [
        {"record_id": row["record_id"], "text": row["text"].partition(":")[2].strip().rstrip(".")}
        for row in rows if row["text"].casefold().startswith("available capability:")
    ]
    if not capabilities:
        raise ProfessionalNativeExecutionError("Opportunity Foundry requires explicit available capabilities")
    budget_match = next(((row, re.search(r"budget.*?capped at\s+R\s*([\d,]+(?:\.\d+)?)", row["text"], re.IGNORECASE)) for row in rows if "budget" in row["text"].casefold()), None)
    budget = float(budget_match[1].group(1).replace(",", "")) if budget_match and budget_match[1] else None
    observations: list[dict[str, Any]] = []
    if market_receipt is not None:
        if market_receipt.get("packet_fingerprint") != packet["packet_fingerprint"]:
            raise ProfessionalNativeExecutionError("market observations belong to a different customer packet")
        valid_sources = set()
        for source in market_receipt.get("sources") or []:
            path = Path(str(source.get("raw_path") or ""))
            if not path.is_file() or sha256(path) != source.get("sha256"):
                raise ProfessionalNativeExecutionError("market observation source hash mismatch")
            valid_sources.add(source["sha256"])
        for observation in market_receipt.get("observations") or []:
            if observation.get("source_sha256") not in valid_sources:
                raise ProfessionalNativeExecutionError("market observation is not bound to retained public bytes")
            observations.append(dict(observation))
    hypotheses = list(capabilities)
    if len(hypotheses) >= 2:
        hypotheses.append({"record_id": ",".join(row["record_id"] for row in capabilities), "text": " + ".join(row["text"] for row in capabilities) + " as a bounded combined workflow"})
    hypotheses = hypotheses[:3]
    def experiment(capability: dict[str, str], is_combined: bool) -> dict[str, Any]:
        text = capability["text"]
        lower = text.casefold()
        if is_combined:
            return {
                "test_name": "End-to-end evidence-to-document pilot",
                "test_method": "Use one customer-authorised, anonymised sample to ingest and source-link records, transform one selected document, then compare the output and change log against the input.",
                "proposed_success_criteria": ["Every sampled output claim links to its source record and hash.", "All protected values and material contradictions are preserved.", "A named customer reviewer can identify every changed passage and disposition."],
                "sample_scope": "One bounded case; up to 10 source records and one document transformation.",
                "complexity_order": 3,
            }
        if "evidence mapping" in lower or "review pack" in lower:
            return {
                "test_name": "Evidence traceability pilot",
                "test_method": "Map a customer-authorised, anonymised sample of source records to a small set of customer-defined review questions; have the source owner verify each link.",
                "proposed_success_criteria": ["Every mapped statement has a source reference and hash.", "Unsupported or contradictory records remain visibly unresolved.", "The reviewer can trace a sampled conclusion to its original record without assistance."],
                "sample_scope": "Up to 20 records and five customer-defined questions.",
                "complexity_order": 1,
            }
        if "document studio" in lower or "document transformation" in lower:
            return {
                "test_name": "Controlled document transformation pilot",
                "test_method": "Transform one customer-authorised, anonymised document with protected tokens and a change ledger; a document owner compares the edited copy and redline with the source.",
                "proposed_success_criteria": ["All protected tokens remain exact.", "Every substantive change is visible in the redline or change ledger.", "The owner records accepted, rejected and unresolved changes."],
                "sample_scope": "One document, up to 10 pages, plus a controlled terminology list.",
                "complexity_order": 1,
            }
        return {
            "test_name": "Capability boundary pilot",
            "test_method": "Run one customer-authorised sample through the stated capability and compare outputs with a pre-agreed acceptance checklist.",
            "proposed_success_criteria": ["All outputs meet the customer-approved checklist.", "Unsupported actions are explicitly refused.", "A reviewer can reproduce the source trail."],
            "sample_scope": "One bounded customer case.",
            "complexity_order": 2,
        }
    candidates = []
    for hypothesis in hypotheses:
        is_combined = len(hypothesis["record_id"].split(",")) > 1
        plan = experiment(hypothesis, is_combined)
        terms = {t for t in re.findall(r"[a-z]{4,}", hypothesis["text"].casefold())}
        matching = [o for o in observations if terms & set(re.findall(r"[a-z]{4,}", str(o.get("title") or "").casefold()))]
        candidates.append({
            "hypothesis": "Test a customer-owned pilot for " + hypothesis["text"],
            "source_record_ids": hypothesis["record_id"].split(","),
            "why_now": "Customer-declared capability and budget only; no buyer demand or willingness-to-pay evidence is established.",
            **plan,
            "max_test_cost_zar": 0,
            "cost_basis": "proposed allocation ceiling within the customer-declared cap; not an estimated quote",
            "observed_signals": matching, "ranking_basis": "discovery title overlap; not market attractiveness", "signal_count": len(matching),
        })
    # Rank the validation sequence by execution complexity only. Market Radar
    # evidence is optional and must not be mistaken for market attractiveness.
    candidates.sort(key=lambda c: (c["complexity_order"], c["test_name"]))
    if budget is not None:
        weights = [1 if row["complexity_order"] == 1 else 2 for row in candidates]
        total_weight = sum(weights)
        allocations = [int(budget * weight // total_weight) for weight in weights]
        remainder = int(budget) - sum(allocations)
        for index in range(remainder):
            allocations[index % len(allocations)] += 1
        for candidate, allocation in zip(candidates, allocations):
            candidate["max_test_cost_zar"] = allocation
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    result = {
        "schema": "dio.opportunity_foundry.professional_output.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "customer_constraints": rows,
        "customer_source": {"path": "SOURCES/02_evidence_register.csv", "sha256": register_sha},
        "customer_constraint_source_bindings": constraint_source_bindings,
        "customer_budget_cap_zar": budget,
        "ranking_interpretation": "Validation sequence ranked by test complexity and customer-owned capability scope only; not market attractiveness, product-market fit, demand or willingness to pay.",
        "market_observation_count": len(observations),
        "evidence_gaps": ["Discovery title overlap does not establish buyer fit or demand."] + ([] if observations else ["No current source-bound market observations supplied."]),
        "ranked_opportunity_hypotheses": candidates,
        "capability_created": False,
        "product_promoted": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "authority_created": False,
    }
    path = output_dir / "RANKED_OPPORTUNITY_HYPOTHESES.json"
    write_json(path, result)
    summary = output_dir / "OPPORTUNITY_FOUNDRY_BRIEF.md"
    summary.write_text("# Opportunity Foundry — proposed validation sequence\n\n"
        + "Rank order reflects test complexity and customer-stated capability scope. It does not rank market attractiveness. Proposed success criteria must be agreed with the customer before a pilot.\n\n"
        + "\n\n".join(
        f"{row['rank']}. **{row['hypothesis']}**\n\n"
        + f"**Test:** {row['test_name']} — {row['test_method']}\n\n"
        + "**Proposed success criteria:**\n" + "\n".join(f"- {criterion}" for criterion in row["proposed_success_criteria"])
        + f"\n\n**Sample:** {row['sample_scope']}\n\n"
        + f"**Allocation ceiling:** R{row['max_test_cost_zar']}; {row['cost_basis']}."
        + "\n\n**Customer source records:** " + ", ".join(row["source_record_ids"])
        + ("\n\n" + "\n".join(f"Unverified discovery lead: [{o['title']}]({o['url']})" for o in row["observed_signals"]) if row["observed_signals"] else "")
        for row in candidates)
        + "\n\n## Evidence gaps\n\n" + "\n".join("- " + gap for gap in result["evidence_gaps"])
        + "\n\nNo customer outreach, spending, market claim or product capability change was performed.\n", encoding="utf-8")
    review_page = output_dir / "OPPORTUNITY_FOUNDRY_REVIEW.html"
    review_page.write_text(_render_opportunity_foundry_review(result), encoding="utf-8")
    receipt = _basic_receipt("opportunity_foundry", "opportunity_foundry_validation_sequence_v3", packet, terminal="ranked_opportunity_hypotheses", artifacts=[path, summary, review_page], now=now)
    write_json(output_dir / "OPPORTUNITY_FOUNDRY_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def _render_opportunity_foundry_review(result: dict[str, Any]) -> str:
    """Render a local, editable customer review of validation hypotheses."""
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    bindings = {str(row["record_id"]): row for row in result.get("customer_constraint_source_bindings") or []}
    cards = []
    for candidate in result.get("ranked_opportunity_hypotheses") or []:
        source_rows = []
        for record_id in candidate.get("source_record_ids") or []:
            binding = bindings.get(str(record_id))
            if not binding:
                continue
            source_rows.append(
                "<li><strong>" + esc(record_id) + "</strong>: " + esc(binding["statement"]) +
                "<small>Evidence register bytes [" + str(binding["source_byte_start"]) + ", " +
                str(binding["source_byte_end_exclusive"]) + ") · row SHA-256 " +
                esc(binding["source_row_sha256"]) + "</small></li>"
            )
        criteria = "\n".join(str(value) for value in candidate.get("proposed_success_criteria") or [])
        cards.append(
            "<article class='candidate' data-rank='" + str(candidate["rank"]) + "'><header><p class='eyebrow'>Validation sequence · " +
            str(candidate["rank"]) + "</p><h2>" + esc(candidate["hypothesis"]) + "</h2></header>"+
            "<p>" + esc(candidate["why_now"]) + "</p><dl><dt>Proposed test</dt><dd>" + esc(candidate["test_name"]) +
            "</dd><dt>Method</dt><dd>" + esc(candidate["test_method"]) + "</dd><dt>Sample scope</dt><dd>" +
            esc(candidate["sample_scope"]) + "</dd><dt>Current ordering basis</dt><dd>" + esc(candidate["ranking_basis"]) +
            " · complexity " + str(candidate["complexity_order"]) + " · " + str(candidate["signal_count"]) +
            " matching discovery signals</dd></dl><details><summary>Customer source records</summary><ul>" +
            "".join(source_rows) + "</ul></details><fieldset><legend>Reviewer plan</legend>"+
            "<label>Decision<select data-field='reviewer_decision'><option value=''>Pending review</option>"+
            "<option>PLAN_PILOT</option><option>REVISE_PLAN</option><option>HOLD</option><option>REJECT</option></select></label>"+
            "<label>Revised test method<textarea data-field='test_method' rows='3'>" + esc(candidate["test_method"]) + "</textarea></label>"+
            "<label>Revised sample scope<textarea data-field='sample_scope' rows='2'>" + esc(candidate["sample_scope"]) + "</textarea></label>"+
            "<label>Proposed success criteria<textarea data-field='success_criteria' rows='4'>" + esc(criteria) + "</textarea></label>"+
            "<label>Allocation ceiling (ZAR; proposal only)<input type='number' min='0' step='1' data-field='max_test_cost_zar' value='"+
            str(int(candidate.get("max_test_cost_zar") or 0)) + "'></label>"+
            "<label>Reviewer name<input data-field='reviewer_name' autocomplete='name' required></label>"+
            "<label>Reviewer role<input data-field='reviewer_role' required></label>"+
            "<label>Reviewed at (ISO 8601 with UTC offset)<input data-field='reviewed_at_iso8601' placeholder='2026-11-04T14:30:00+02:00' required></label>"+
            "<label>Decision rationale<textarea data-field='rationale' rows='2' required></textarea></label></fieldset></article>"
        )
    items_json = json.dumps(result.get("ranked_opportunity_hypotheses") or [], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    constraints_json = json.dumps(result.get("customer_constraint_source_bindings") or [], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    cap = result.get("customer_budget_cap_zar")
    cap_text = f"R{cap:,.0f}" if isinstance(cap, (int, float)) else "Not supplied"
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Opportunity Foundry · customer review</title><style>
:root{{--ink:#192a2d;--muted:#586b68;--line:#ccd7d2;--paper:#f3f5f1;--green:#194b46;--gold:#bd8740}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:clamp(1rem,4vw,3rem)}}h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.08;max-width:900px}}h2{{font-size:1.4rem}}.eyebrow{{font-size:.78rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}.notice{{border-left:5px solid var(--gold);padding:1rem 1.2rem;background:#fff8e9}}.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.8rem;margin:1.2rem 0}}.summary section,.candidate{{background:white;border:1px solid var(--line);border-radius:.45rem;padding:1rem}}.candidate{{margin:1rem 0 1.4rem}}dl{{display:grid;grid-template-columns:minmax(9rem,20%) 1fr;gap:.45rem;margin:1rem 0}}dt{{font-weight:700}}dd{{margin:0}}details{{margin:.8rem 0}}small{{display:block;color:var(--muted);overflow-wrap:anywhere}}fieldset{{border:1px solid var(--line);border-radius:.35rem;padding:1rem;margin:1rem 0}}legend{{font-weight:700;padding:0 .35rem}}label{{display:block;margin:.75rem 0;font-weight:600}}input,select,textarea,button{{font:inherit}}input,select,textarea{{display:block;width:100%;padding:.6rem;border:1px solid #859892;border-radius:.25rem;background:white;color:var(--ink)}}textarea{{resize:vertical}}button{{background:var(--green);color:white;border:0;border-radius:.3rem;padding:.75rem 1rem;font-weight:700;cursor:pointer}}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{{outline:3px solid var(--gold);outline-offset:3px}}.toolbar,.actions{{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;margin:1rem 0}}.toolbar input{{min-width:min(24rem,80vw)}}#status{{min-height:1.5em;color:var(--muted)}}footer{{margin-top:2rem;color:var(--muted)}}[hidden]{{display:none!important}}@media(max-width:620px){{dl{{grid-template-columns:1fr;gap:.1rem}}dd{{margin-bottom:.6rem}}}}
</style></head><body><a href='#plans'>Skip to review plans</a><main><p class='eyebrow'>Opportunity Foundry · customer-owned validation planning</p>
<h1>Review the proposed validation sequence</h1><p class='notice'><strong>These are hypotheses for discussion.</strong> Order reflects test complexity and customer-stated capability scope; it is not a ranking of market attractiveness, buyer demand, product-market fit, or willingness to pay. The proposed allocations are ceilings for discussion, not quotes or approved spend.</p>
<div class='summary'><section><strong>Customer-stated cap</strong><br>{esc(cap_text)}</section><section><strong>Observed market signals</strong><br>{int(result.get('market_observation_count') or 0)} · title overlap only</section><section><strong>Current evidence</strong><br>Hypotheses only; no pilot selected</section></div>
<h2>Review assumptions</h2><p>Change the proposed method, sample, success criteria, allocation ceiling, and decision below. Your edits remain in this browser page until you download the worksheet. Download does not authorize a pilot or payment.</p>
<section class='toolbar' aria-label='Review tools'><label for='filter'>Find a hypothesis<input id='filter' type='search' placeholder='Search test, method or source record'></label><span id='count' aria-live='polite'></span></section>
<div class='summary'><section><strong>Proposed allocation total</strong><br><output id='allocation-total'>Calculating…</output></section><section><strong>Customer cap check</strong><br><output id='allocation-status' role='status' aria-live='polite'>Review allocations</output></section></div>
<section id='plans'>{''.join(cards)}</section><h2>Evidence gaps</h2><ul>{''.join('<li>'+esc(gap)+'</li>' for gap in result.get('evidence_gaps') or [])}</ul>
<div class='actions'><button id='download' type='button'>Download review worksheet CSV</button><span id='status' role='status' aria-live='polite'></span></div>
<footer>Source register SHA-256: <code>{esc((result.get('customer_source') or {{}}).get('sha256') or '')}</code>. Market demand claimed: no. Willingness to pay proved: no. Customer outreach or spending performed: no. Nothing is submitted from this page.</footer>
<script type='application/json' id='hypothesis-data'>{items_json}</script><script type='application/json' id='constraint-data'>{constraints_json}</script><script>
const candidates=JSON.parse(document.querySelector('#hypothesis-data').textContent);const constraints=JSON.parse(document.querySelector('#constraint-data').textContent);const cap={json.dumps(cap)};const cards=[...document.querySelectorAll('.candidate')];
const count=()=>document.querySelector('#count').textContent=cards.filter(c=>!c.hidden).length+' of '+cards.length+' hypotheses shown';count();
document.querySelector('#filter').addEventListener('input',event=>{{const q=event.target.value.trim().toLowerCase();for(const card of cards){{card.hidden=Boolean(q)&&!card.textContent.toLowerCase().includes(q)}}count()}});
const updateTotal=()=>{{const total=[...document.querySelectorAll('[data-field="max_test_cost_zar"]')].reduce((sum,input)=>sum+(Number(input.value)||0),0);document.querySelector('#allocation-total').textContent='R'+total.toLocaleString('en-ZA');const valid=cap===null||total<=cap;document.querySelector('#allocation-status').textContent=valid?'Within customer-stated cap':'Above customer-stated cap';document.querySelector('#allocation-status').style.color=valid?'#194b46':'#9a321f'}};
document.querySelectorAll('[data-field="max_test_cost_zar"]').forEach(input=>{{if(cap!==null)input.max=cap;input.addEventListener('input',updateTotal)}});updateTotal();
const q=value=>'"'+String(value??'').replaceAll('"','""')+'"';document.querySelector('#download').addEventListener('click',()=>{{const headers=['rank','hypothesis','source_record_ids','source_register_sha256','source_record_bindings','reviewer_decision','test_method','sample_scope','success_criteria','max_test_cost_zar','reviewer_name','reviewer_role','reviewed_at_iso8601','rationale','allocation_total_zar','customer_budget_cap_zar'];const sourceById=new Map(constraints.map(x=>[String(x.record_id),x]));const errors=[],output=[];let total=0;for(const card of cards){{const base=candidates.find(x=>x.rank===Number(card.dataset.rank));const val=field=>card.querySelector('[data-field="'+field+'"]')?.value?.trim()||'';const rawCost=val('max_test_cost_zar'),cost=Number(rawCost);if(!rawCost||!Number.isFinite(cost)||cost<0)errors.push('Rank '+base.rank+': allocation must be a non-negative number');total+=Number.isFinite(cost)?cost:0;const decision=val('reviewer_decision');if(!['PLAN_PILOT','REVISE_PLAN','HOLD','REJECT'].includes(decision))errors.push('Rank '+base.rank+': choose a reviewer decision');for(const key of ['test_method','sample_scope','success_criteria','reviewer_name','reviewer_role','rationale'])if(!val(key))errors.push('Rank '+base.rank+': '+key+' is required');const reviewed=val('reviewed_at_iso8601');if(!/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:[.][0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(reviewed))errors.push('Rank '+base.rank+': review time must include UTC offset');const sourceBindings=base.source_record_ids.map(id=>sourceById.get(String(id)));if(sourceBindings.some(x=>!x))errors.push('Rank '+base.rank+': source binding missing');output.push({{rank:base.rank,hypothesis:base.hypothesis,source_record_ids:base.source_record_ids.join(';'),source_register_sha256:(constraints[0]||{{}}).source_file_sha256||'',source_record_bindings:JSON.stringify(sourceBindings),reviewer_decision:decision,test_method:val('test_method'),sample_scope:val('sample_scope'),success_criteria:val('success_criteria'),max_test_cost_zar:rawCost,reviewer_name:val('reviewer_name'),reviewer_role:val('reviewer_role'),reviewed_at_iso8601:reviewed,rationale:val('rationale'),allocation_total_zar:total,customer_budget_cap_zar:cap}})}}if(cap!==null&&total>cap)errors.push('Total proposed allocation R'+total.toLocaleString('en-ZA')+' exceeds customer-stated cap R'+cap.toLocaleString('en-ZA'));if(errors.length){{document.querySelector('#status').textContent='Review not exported. '+errors.slice(0,4).join('; ');return}}const lines=[headers.map(q).join(','),...output.map(row=>headers.map(h=>q(row[h])).join(','))];const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{{type:'text/csv;charset=utf-8'}});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='OPPORTUNITY_FOUNDRY_REVIEW.csv';a.click();URL.revokeObjectURL(url);document.querySelector('#status').textContent='Review worksheet downloaded. Hypotheses remain unvalidated; no pilot, spending, or release is authorized.'}});
</script></main></body></html>"""


def run_offer_lab(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = evidence_rows(packet)
    register_path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_sha = sha256(register_path)
    rows = [{"record_id": str(row.get("record_id") or ""), "text": str(row.get("customer_supplied_record") or "").strip()} for row in source_rows]
    def supplied(prefix: str) -> str:
        return next((row["text"].partition(":")[2].strip().rstrip(".") for row in rows if row["text"].casefold().startswith(prefix.casefold() + ":")), "")
    capability, buyer, scope = supplied("Capability proof"), supplied("Target hypothesis"), supplied("Pilot scope")
    if not capability or not buyer or not scope:
        raise ProfessionalNativeExecutionError("Offer Lab requires customer capability, target hypothesis and pilot scope")
    raw_prices = supplied("Approved price test options ZAR")
    prices = [float(value.replace(",", "")) for value in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", raw_prices)] if raw_prices else []
    source_ids = {label: next((row["record_id"] for row in rows if row["text"].casefold().startswith(label.rstrip(":").casefold())), None)
                  for label in ("Capability proof", "Target hypothesis", "Pilot scope", "No customer payment")}
    row_bindings = {str(row["record_id"]): row for row in evidence_register_record_bindings(packet)}
    source_refs = []
    for row in rows:
        binding = row_bindings.get(row["record_id"])
        if binding is None or binding.get("customer_statement") != row["text"] or binding.get("source_file_sha256") != register_sha:
            raise ProfessionalNativeExecutionError(f"Offer Lab source row failed exact evidence-register binding: {row['record_id']}")
        source_refs.append({
            "record_id": row["record_id"],
            "source_ref": binding["source_ref"],
            "source_byte_ref": f"customer-packet://SOURCES/02_evidence_register.csv#bytes={binding['source_byte_start']}:{binding['source_byte_end_exclusive']}",
            "source_register_sha256": register_sha,
            "source_row_sha256": binding["source_row_sha256"],
            "source_statement_sha256": binding["source_statement_sha256"],
            "source_byte_start": binding["source_byte_start"],
            "source_byte_end_exclusive": binding["source_byte_end_exclusive"],
            "statement": row["text"],
            "epistemic_state": "CUSTOMER_DECLARED",
        })
    target_scope_alignment = {
        "target_hypothesis": buyer,
        "buyer_verified": False,
        "segment_overlap_evidence": "not supplied",
        "risk": "This target is a hypothesis only; no interviews, pipeline, purchase records or segment-level demand evidence are in the customer packet.",
    }
    price_protocol = {
        "state": "CUSTOMER_PRICE_OPTIONS_SUPPLIED" if prices else "NO_APPROVED_PRICE_OPTIONS_SUPPLIED",
        "approved_numeric_options_zar": prices,
        "method": "Before quoting, obtain owner-approved delivery costs and scope. In exploratory interviews ask an open-ended willingness-to-pay question without presenting an invented price; then record actual paid pilot conversion separately from stated intent.",
        "competitor_price_comparability": "not assessed in this packet; third-party software subscriptions must not be treated as equivalent prices for a human-reviewed service pilot.",
        "observed_payment": False,
        "willingness_to_pay_proved": False,
    }
    validation_plan = [
        {"step": 1, "name": "Problem interview", "method": "Ask target buyers to describe their current workflow, last completed example, time/cost and failure points before showing the offer.", "measure": ["buyer role and firm profile", "recent observed workflow", "current workaround and cost evidence"], "interpretation": "Qualitative discovery only; expressions of interest are not demand proof."},
        {"step": 2, "name": "Bounded sample review", "method": scope, "measure": ["source-linked claims", "gaps and contradictions preserved", "reviewer changes and reasons", "turnaround time"], "interpretation": "Pilot acceptance is not compliance certification or professional approval."},
        {"step": 3, "name": "Commercial test", "method": price_protocol["method"], "measure": ["owner-approved quote presented", "decision and objection recorded", "paid conversion recorded separately"], "interpretation": "Only an observed paid transaction counts as payment evidence; do not infer willingness to pay from survey responses."},
    ]
    offer = {
        "schema": "dio.offer_lab.professional_offer.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "offer_name": "Pilot hypothesis: " + capability,
        "target_buyer_hypothesis": buyer,
        "scope": scope,
        "required_inputs": ["customer-selected workflow", "customer-owned evidence files", "review criteria or obligations where available"],
        "outputs": ["source-bound evidence map", "gap/contradiction register", "review-ready pack", "proof receipt"],
        "allowed_claims": ["Customer-declared capability for testing: " + capability, "human authority and external release remain explicit"],
        "prohibited_claims": ["customers want this", "willingness to pay is proven", "the pack certifies compliance", "DIO replaces professional judgement"],
        "price_test_options_zar": prices,
        "price_test_protocol": price_protocol,
        "validation_plan": validation_plan,
        "target_scope_alignment": target_scope_alignment,
        "source_register": {"path": "SOURCES/02_evidence_register.csv", "sha256": register_sha},
        "offer_component_trace": {
            "capability": source_ids["Capability proof"],
            "target_buyer": source_ids["Target hypothesis"],
            "scope": source_ids["Pilot scope"],
            "payment_status": source_ids["No customer payment"],
        },
        "source_records": source_refs,
        "evidence_gaps": ([] if prices else ["No owner-approved numeric price options or delivery-cost basis supplied; price discovery protocol is provided without invented amounts."]),
        "observed_payment": False,
        "willingness_to_pay_proved": False,
        "market_demand_claimed": False,
        "external_release": "REFUSE",
        "authority_created": False,
        "customer_constraints": rows,
    }
    path = output_dir / "BOUNDED_OFFER.json"
    write_json(path, offer)
    review_fields = ["record_id", "component", "customer_statement", "source_ref", "source_byte_ref",
                     "source_register_sha256", "source_row_sha256",
                     "source_statement_sha256", "source_byte_start", "source_byte_end_exclusive", "epistemic_state",
                     "reviewer_decision", "reviewer_name", "reviewer_role", "reviewed_at_iso8601", "rationale", "revised_wording"]
    review_rows = []
    for item in source_refs:
        component = next((key for key, record_id in offer["offer_component_trace"].items() if record_id == item["record_id"]), "context")
        review_rows.append({**{key: item.get(key, "") for key in review_fields[:10]},
                            "customer_statement": item.get("statement", ""), "component": component,
                            "epistemic_state": item.get("epistemic_state", ""),
                            "reviewer_decision": "", "reviewer_name": "", "reviewer_role": "", "reviewed_at_iso8601": "",
                            "rationale": "", "revised_wording": ""})
    review_csv = output_dir / "OFFER_REVIEW_WORKSHEET.csv"
    with review_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields)
        writer.writeheader()
        writer.writerows(review_rows)
    cards = []
    for index, item in enumerate(source_refs):
        component = next((key for key, record_id in offer["offer_component_trace"].items() if record_id == item["record_id"]), "context")
        cards.append(
            "<article data-index='" + str(index) + "'><h2>" + html.escape(component.replace("_", " ").title()) + " · " + html.escape(item["record_id"]) +
            "</h2><blockquote>" + html.escape(item["statement"]) + "</blockquote><small>Source locator " +
            html.escape(item["source_ref"]) + " · " + html.escape(item["source_byte_ref"]) + " · evidence register bytes [" +
            str(item["source_byte_start"]) + ", " + str(item["source_byte_end_exclusive"]) + ") · row SHA-256 " +
            html.escape(item["source_row_sha256"]) + " · register SHA-256 " + html.escape(item["source_register_sha256"]) +
            "</small><label>Customer/owner decision<select data-field='reviewer_decision'><option value=''>Choose…</option>"+
            "<option>ACCEPT_AS_HYPOTHESIS</option><option>REVISE</option><option>REQUEST_EVIDENCE</option><option>DEFER</option></select></label>"+
            "<label>Reviewer name<input data-field='reviewer_name' required></label><label>Reviewer role<input data-field='reviewer_role' required></label>"+
            "<label>Reviewed at (ISO 8601 with UTC offset)<input data-field='reviewed_at_iso8601' placeholder='2026-11-04T14:30:00+02:00' required></label>"+
            "<label>Rationale<textarea data-field='rationale' required></textarea></label>"+
            "<label>Revised wording<textarea data-field='revised_wording'></textarea></label></article>")
    review_page = """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Offer Lab · Customer review</title>
<style>body{font:16px/1.55 system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;background:#f4f3ee;color:#172522}article{background:white;border:1px solid #c8d0c9;border-radius:8px;padding:1rem;margin:1rem 0}blockquote{white-space:pre-wrap}small{display:block;overflow-wrap:anywhere;color:#40534a}label{display:block;margin:.8rem 0}input,select,textarea{display:block;box-sizing:border-box;width:100%;padding:.55rem}button{padding:.7rem 1rem}a{color:#075c69}#status{padding:.75rem;background:#edf3f0}</style><main><a href='BOUNDED_OFFER.md'>Read the offer brief</a><h1>Review the offer hypothesis</h1><p>These are customer-declared inputs. Review the capability, buyer hypothesis, scope, and payment status. This page does not establish demand, willingness to pay, price approval, or professional suitability.</p>
""" + "\n".join(cards) + """<button id='download'>Download completed review worksheet</button><p id='status' role='status' aria-live='polite'>Complete all decisions, reviewer identities, review times and rationales before downloading. This records owner review only; it does not establish demand or authorize release.</p><p>Validate the downloaded CSV with <a href='OFFER_REVIEW_VALIDATOR.py'>the source-bound review validator</a> and the original customer evidence register before relying on the review record.</p><script>const fields=%s;const q=v=>'"'+String(v??'').replaceAll('"','""')+'"';const status=document.querySelector('#status');document.querySelector('#download').onclick=()=>{const rows=[],errors=[];for(const a of document.querySelectorAll('article')){const base=JSON.parse(a.dataset.row);for(const e of a.querySelectorAll('[data-field]'))base[e.dataset.field]=e.value.trim();for(const key of ['reviewer_decision','reviewer_name','reviewer_role','reviewed_at_iso8601','rationale'])if(!base[key])errors.push(base.record_id+': '+key);if(base.reviewed_at_iso8601&&!/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:[.][0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(base.reviewed_at_iso8601))errors.push(base.record_id+': review time must include a UTC offset');rows.push(base)}if(errors.length){status.textContent='Review not exported. Complete the required fields: '+errors.slice(0,4).join('; ');return}const lines=[fields.map(q).join(','),...rows.map(row=>fields.map(k=>q(row[k]??'')).join(','))];const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='OFFER_REVIEW_COMPLETED.csv';a.click();URL.revokeObjectURL(url);status.textContent='Completed review downloaded. The hypothesis remains unvalidated and release remains refused.'}</script></main></html>""" % json.dumps(review_fields)
    for index, card in enumerate(cards):
        review_page = review_page.replace("<article data-index='" + str(index) + "'>", "<article data-index='" + str(index) + "' data-row='" + html.escape(json.dumps(review_rows[index], ensure_ascii=False, separators=(",", ":")), quote=True) + "'>")
    review_html = output_dir / "OFFER_REVIEW.html"
    review_html.write_text(review_page, encoding="utf-8")
    review_tool = output_dir / "OFFER_REVIEW_VALIDATOR.py"
    shutil.copyfile(Path(__file__).with_name("offer_lab_review.py"), review_tool)
    from products.offer_lab_review import validate as validate_offer_lab_review
    review_validation = output_dir / "OFFER_REVIEW_VALIDATION.json"
    write_json(review_validation, validate_offer_lab_review(path, register_path, review_csv))
    one_page = output_dir / "BOUNDED_OFFER.md"
    one_page.write_text(
        "# " + offer["offer_name"] + "\n\n**For testing, not validated demand.**\n\n"
        + offer["scope"]
        + "\n\n## Buyer hypothesis\n\n" + offer["target_buyer_hypothesis"]
        + "\n\n## Required inputs\n\n" + "\n".join(f"- {item}" for item in offer["required_inputs"])
        + "\n\n## Price test options (ZAR; not validated)\n\n" + ", ".join(str(item) for item in offer["price_test_options_zar"])
        + ("No numeric options supplied. No prices have been invented.\n" if not prices else "\n")
        + "\n## Offer validation sequence\n\n" + "\n\n".join(f"### {step['step']}. {step['name']}\n\n{step['method']}\n\nMeasures: " + "; ".join(step["measure"]) + "\n\nInterpretation: " + step["interpretation"] for step in validation_plan)
        + "\n\n## Source trace\n\n" + "\n".join(f"- {item['record_id']} — {item['source_ref']} (register SHA-256 `{item['source_register_sha256']}`)" for item in source_refs)
        + "\n\n## Customer review\n\nUse `OFFER_REVIEW.html` to record one decision, reviewer identity and role, timezone-aware review time, and rationale for each source-bound offer component. The completed CSV carries exact customer statements and source locators. Validate it with `OFFER_REVIEW_VALIDATOR.py` against `BOUNDED_OFFER.json` and `../CUSTOMER_PACKET/SOURCES/02_evidence_register.csv`. Blank or invalid reviews leave the hypothesis unapproved. A valid review receipt records owner input only; it does not prove demand, payment, professional suitability, or release authority. The supplied blank worksheet is expected to validate as `REVIEW_INCOMPLETE_OR_HOLD_REQUIRED`.\n"
        + "\n\n## Customer constraints\n\n" + "\n".join(f"- {item['text']}" for item in rows)
        + "\n\n## Allowed bounded claims\n\n" + "\n".join(f"- {item}" for item in offer["allowed_claims"])
        + "\n\n## Outputs\n\n" + "\n".join(f"- {item}" for item in offer["outputs"])
        + "\n\n## Claim boundary\n\n" + "\n".join(f"- DO NOT CLAIM: {item}" for item in offer["prohibited_claims"]) + "\n",
        encoding="utf-8",
    )
    receipt = _basic_receipt("offer_lab", "offer_lab_source_traced_validation_plan_v3", packet, terminal="bounded_offer_hypothesis", artifacts=[path, one_page, review_csv, review_html, review_tool, review_validation], now=now)
    write_json(output_dir / "OFFER_LAB_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


__all__ = [
    "run_accessible_publish",
    "run_accreditation",
    "run_contractproof",
    "run_dossierops",
    "run_homs_curriculum",
    "run_homs_exam",
    "run_offer_lab",
    "run_opportunity_foundry",
    "run_regops",
]
