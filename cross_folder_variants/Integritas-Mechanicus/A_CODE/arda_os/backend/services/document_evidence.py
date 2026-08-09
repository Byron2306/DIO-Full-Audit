#!/usr/bin/env python3
"""
Minimal document-evidence pipeline for protocol v1.1.

Stdlib-first on purpose:
- plain text / markdown / json / html extraction
- optional PDF extraction via `pdftotext` if available
- image/scan support through native Tesseract OCR or sidecar OCR text files

This does not pretend to be native vision. It prepares bounded OCR evidence
objects that the Presence runtime can reason over lawfully.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PIL import Image, ImageOps
    import pytesseract
except Exception:  # pragma: no cover - optional OCR dependency
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]
    pytesseract = None  # type: ignore[assignment]


MAX_EXTRACTED_CHARS = 30000
MAX_SPANS = 24
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
SOURCE_TIER_RULES = [
    ("peer_reviewed_or_primary", 0.95, ("doi.org", "arxiv.org", "eric.ed.gov", "plato.stanford.edu", "openalex.org")),
    ("institutional_or_policy", 0.85, (".edu", ".gov", "unesco.org", "oecd.org")),
    ("local_evidence_fixture", 0.75, ("evidence/", "fixtures/", "phase5_", "matrix_gauntlet")),
    ("user_supplied_document", 0.60, ("/home/", "/tmp/")),
]


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        data = data.strip()
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return "\n".join(self.parts)


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate(text: str, max_chars: int = MAX_EXTRACTED_CHARS) -> str:
    text = _clean_text(text)
    if len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head - 40
    return (
        text[:head].rstrip()
        + "\n\n[... middle truncated for context budget ...]\n\n"
        + text[-tail:].lstrip()
    )


def _chunk_text(text: str, max_chars: int = 280) -> List[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if not blocks:
        blocks = [text.strip()] if text.strip() else []
    chunks: List[str] = []
    for block in blocks:
        if len(block) <= max_chars:
            chunks.append(block)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", block)
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = sentence.strip()
            else:
                current = candidate
        if current:
            chunks.append(current)
    return [chunk for chunk in chunks if chunk]


def _build_spans(text: str) -> List[Dict[str, object]]:
    page_parts = re.split(r"\f+", text or "")
    page_aware = len(page_parts) > 1
    candidates: List[Dict[str, object]] = []
    if page_aware:
        for page_index, page_text in enumerate(page_parts, start=1):
            for chunk in _chunk_text(page_text):
                candidates.append({"quote": chunk, "page": page_index, "page_number": page_index})
    else:
        candidates = []
        for chunk in _chunk_text(text):
            item: Dict[str, object] = {"quote": chunk}
            marker = re.search(r"\b(?:page|p\.)\s*(\d{1,4})\b", chunk or "", flags=re.I)
            if marker:
                page_number = int(marker.group(1))
                item["page"] = page_number
                item["page_number"] = page_number
            candidates.append(item)

    if len(candidates) > MAX_SPANS:
        head_n = max(6, MAX_SPANS // 3)
        tail_n = max(6, MAX_SPANS // 3)
        middle_n = MAX_SPANS - head_n - tail_n
        middle_start = max(head_n, (len(candidates) // 2) - (middle_n // 2))
        selected = candidates[:head_n] + candidates[middle_start:middle_start + middle_n] + candidates[-tail_n:]
    else:
        selected = candidates

    spans: List[Dict[str, object]] = []
    for index, item in enumerate(selected[:MAX_SPANS], start=1):
        quote = str(item.get("quote") or "").strip()
        if not quote:
            continue
        span: Dict[str, object] = {"span_id": f"S{index}", "quote": quote}
        if item.get("page") not in (None, ""):
            span["page"] = item["page"]
            span["page_number"] = item["page_number"]
            span["locator"] = f"p. {item['page']}"
        spans.append(span)
    return spans


def _uncertainty_notes(text: str) -> List[str]:
    notes: List[str] = []
    lowered = text.lower()
    if any(token in lowered for token in ("[unclear]", "[illegible]", "[missing]", "???")):
        notes.append("source_contains_unreadable_regions")
    if "blurry" in lowered or "blurred" in lowered:
        notes.append("source_mentions_blur_or_scan_loss")
    if "[truncated]" in text:
        notes.append("extraction_truncated_for_context_budget")
    return notes


def _document_quality(
    *,
    parser: str,
    modality: str,
    text: str,
    uncertainty: List[str],
) -> Dict[str, object]:
    """Classify evidence quality for multimodal/document reasoning."""
    text_len = len((text or "").strip())
    suffix = str(modality or "").lower()
    notes = set(uncertainty or [])
    if parser in {"unavailable", "upload_error"} or text_len == 0:
        return {
            "quality": "unreadable",
            "score": 0.0,
            "rationale": "No extractable text/OCR evidence was available.",
        }
    if "ocr_sidecar_missing" in notes:
        return {
            "quality": "image_without_ocr",
            "score": 0.1,
            "rationale": "Image-like evidence was supplied without OCR text; visual claims are unsupported.",
        }
    if any(note in notes for note in ("source_contains_unreadable_regions", "source_mentions_blur_or_scan_loss")):
        return {
            "quality": "partial_ocr",
            "score": 0.45,
            "rationale": "OCR/text contains unreadable or blurry regions; answer only from readable spans.",
        }
    if parser in {"native_tesseract_ocr", "sidecar_ocr", "sidecar_text"} or "ocr" in suffix:
        return {
            "quality": "ocr_supported",
            "score": 0.72 if parser != "native_tesseract_ocr" else 0.76,
            "rationale": "Evidence is mediated through OCR text; quote only readable spans.",
        }
    return {
        "quality": "readable_text",
        "score": 0.9,
        "rationale": "Text extraction produced readable spans.",
    }


def _source_provenance(path: Path, modality: str, text: str) -> Dict[str, object]:
    """Rank source provenance separately from OCR/readability quality."""
    haystack = f"{path.as_posix()} {modality} {text[:1000]}".lower()
    for tier, score, markers in SOURCE_TIER_RULES:
        if any(marker in haystack for marker in markers):
            return {
                "tier": tier,
                "score": score,
                "rationale": f"Matched provenance markers for {tier}.",
            }
    if re.search(r"https?://", haystack):
        return {
            "tier": "web_unknown",
            "score": 0.45,
            "rationale": "Web source present but not in approved high-trust markers.",
        }
    return {
        "tier": "unknown_or_unverified",
        "score": 0.35,
        "rationale": "No strong provenance marker was available.",
    }


def _cross_source_warnings(documents: List[Dict[str, object]]) -> List[str]:
    """Surface obvious conflicts across supplied documents without pretending full NLI."""
    warnings: List[str] = []
    text = "\n".join(str(doc.get("extracted_text") or "") for doc in documents).lower()
    numeric_claims = _numeric_claim_tokens(text)
    if len(set(numeric_claims)) >= 3 and any(token in text for token in ("conflict", "disagree", "caption says", "user visual description says")):
        warnings.append("possible_numeric_or_caption_conflict")
    if "native pixel inspection is unavailable" in text or "native vision" in text:
        warnings.append("native_vision_not_available")
    if "ocr confidence is medium" in text or "caption conflicts" in text:
        warnings.append("ocr_caption_conflict_requires_verification")
    return warnings


def classify_multimodal_disagreement(documents: List[Dict[str, object]]) -> Dict[str, object]:
    """Classify OCR/caption/user-description disagreement without resolving it as fact.

    This is intentionally a guardrail, not a vision oracle. If two text/OCR
    witnesses disagree about numbers, captions, or figure descriptions, Sophia
    should hold interpretation until the conflict is inspected by the learner.
    """
    witnesses: List[Dict[str, object]] = []
    numeric_values: Dict[str, List[str]] = {}
    caption_claims: List[str] = []
    uncertainty_terms: List[str] = []
    for doc in documents or []:
        if not isinstance(doc, dict):
            continue
        name = str(doc.get("source_name") or "document")
        text = str(doc.get("extracted_text") or "")
        lowered = text.lower()
        nums = _numeric_claim_tokens(lowered)
        for num in nums:
            numeric_values.setdefault(num, []).append(name)
        if any(token in lowered for token in ("caption says", "figure caption", "chart says", "user description says", "ocr says")):
            caption_claims.append(name)
        if any(token in lowered for token in ("conflict", "conflicts", "disagree", "disagrees", "unclear", "illegible", "blurry")):
            uncertainty_terms.append(name)
        witnesses.append({
            "source_name": name,
            "parser": doc.get("parser") or "",
            "quality": (doc.get("evidence_quality") or {}).get("quality") if isinstance(doc.get("evidence_quality"), dict) else "",
            "numbers": nums[:20],
            "caption_signal": name in caption_claims,
            "uncertainty_signal": name in uncertainty_terms,
        })
    conflict_signals = _cross_source_warnings(documents)
    numeric_conflict = len(numeric_values) >= 2 and bool(caption_claims or uncertainty_terms or conflict_signals)
    caption_conflict = len(caption_claims) >= 1 and bool(uncertainty_terms or conflict_signals)
    status = "no_disagreement_detected"
    if numeric_conflict or caption_conflict:
        status = "disagreement_requires_human_verification"
    elif uncertainty_terms:
        status = "degraded_evidence_requires_caution"
    return {
        "status": status,
        "numeric_conflict": numeric_conflict,
        "caption_conflict": caption_conflict,
        "conflict_signals": conflict_signals,
        "witnesses": witnesses,
        "distinct_numeric_values": sorted(numeric_values)[:30],
        "integrity_rule": (
            "Do not resolve OCR, caption, or user-description conflicts as fact. "
            "Report the disagreement, quote the witnesses, and ask for inspection or clearer evidence."
        ),
        "safe_response_mode": (
            "hold_visual_interpretation"
            if status == "disagreement_requires_human_verification"
            else "bounded_text_or_ocr_summary"
        ),
    }


def build_cross_modal_evidence_ledger(documents: List[Dict[str, object]]) -> Dict[str, object]:
    """Create an inspectable multimodal ledger across text/OCR/vision witnesses.

    The ledger does not resolve visual truth. It tells Sophia what can be said,
    what must be held, and why. This is the multimodal equivalent of a
    claim-evidence-warrant-limitation ledger.
    """
    witnesses: List[Dict[str, object]] = []
    numeric_index: Dict[str, List[str]] = {}
    page_index: Dict[str, List[str]] = {}
    visual_claim_signals: List[str] = []
    degraded_witnesses: List[str] = []

    for idx, doc in enumerate(documents or [], start=1):
        if not isinstance(doc, dict):
            continue
        name = str(doc.get("source_name") or f"document_{idx}")
        text = str(doc.get("extracted_text") or "")
        lowered = text.lower()
        inspection = doc.get("document_inspection") if isinstance(doc.get("document_inspection"), dict) else {}
        quality = doc.get("evidence_quality") if isinstance(doc.get("evidence_quality"), dict) else {}
        provenance = doc.get("source_provenance") if isinstance(doc.get("source_provenance"), dict) else {}
        numbers = _numeric_claim_tokens(lowered)
        pages = sorted(set(str(p) for p in (inspection.get("page_numbers") or []) if str(p).strip()))
        for number in numbers:
            numeric_index.setdefault(number, []).append(name)
        for page in pages:
            page_index.setdefault(page, []).append(name)
        has_visual_signal = bool(inspection.get("figure_signal")) or any(
            token in lowered
            for token in ("figure", "caption", "chart", "diagram", "ocr says", "user description says", "native vision")
        )
        if has_visual_signal:
            visual_claim_signals.append(name)
        q = str(quality.get("quality") or "")
        warnings = [str(item) for item in (inspection.get("warnings") or [])]
        if q in {"unreadable", "image_without_ocr", "partial_ocr"} or warnings:
            degraded_witnesses.append(name)
        witnesses.append({
            "witness_id": f"W{idx}",
            "source_name": name,
            "modality": doc.get("modality") or "",
            "parser": doc.get("parser") or "",
            "quality": q,
            "quality_score": quality.get("score"),
            "provenance_tier": provenance.get("tier"),
            "provenance_score": provenance.get("score"),
            "page_numbers": pages[:20],
            "numbers": numbers[:20],
            "visual_signal": has_visual_signal,
            "warnings": warnings,
        })

    disagreement = classify_multimodal_disagreement(documents)
    has_conflict = disagreement.get("status") == "disagreement_requires_human_verification"
    safe_claims = [
        "Summarize readable text/OCR spans with provenance and uncertainty visible.",
        "Use page locators only when page markers are visible in extracted spans.",
    ]
    blocked_claims = [
        "Do not treat OCR, caption, or user-description disagreement as resolved fact.",
        "Do not infer chart/table meaning from an image without OCR, parsed table cells, or native vision evidence.",
    ]
    if not has_conflict and visual_claim_signals:
        safe_claims.append("Describe visual material only as text/OCR-mediated evidence unless native vision was explicitly invoked.")
    if not visual_claim_signals:
        safe_claims.append("No visual-evidence signal detected; ordinary text-evidence handling is sufficient.")
    if not degraded_witnesses and not has_conflict:
        blocked_claims = [
            "Do not overclaim beyond visible spans, source provenance, and page/table evidence."
        ]
    confidence_ceiling = 0.9
    if has_conflict:
        confidence_ceiling = 0.45
    elif degraded_witnesses:
        confidence_ceiling = 0.65
    elif visual_claim_signals:
        confidence_ceiling = 0.72

    required_next_steps: List[str] = []
    if has_conflict:
        required_next_steps.append("Ask the learner to inspect the original visual artifact or provide clearer OCR/native vision.")
    if degraded_witnesses:
        required_next_steps.append("Name degraded witnesses before interpreting the claim.")
    if numeric_index:
        required_next_steps.append("Verify any numeric claim against the exact witness span and, if tabular, parsed table cells.")
    if page_index:
        required_next_steps.append("Use only visible page markers for page-specific claims.")
    if not required_next_steps:
        required_next_steps.append("Proceed with bounded text/source analysis.")

    return {
        "schema_version": "sophia.cross_modal_evidence_ledger.v1",
        "status": "hold_for_verification" if has_conflict else "bounded_use_allowed",
        "witness_count": len(witnesses),
        "witnesses": witnesses,
        "numeric_index": {key: value for key, value in sorted(numeric_index.items())[:40]},
        "page_index": {key: value for key, value in sorted(page_index.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 999999)[:40]},
        "visual_witnesses": sorted(set(visual_claim_signals)),
        "degraded_witnesses": sorted(set(degraded_witnesses)),
        "disagreement": disagreement,
        "safe_claims": safe_claims,
        "blocked_claims": blocked_claims,
        "required_next_steps": required_next_steps,
        "confidence_ceiling": confidence_ceiling,
        "integrity_rule": "Multimodal evidence must be handled as witnesses with provenance, uncertainty, and conflict status; Sophia must not collapse them into a single resolved fact.",
    }


def compare_native_vision_witnesses(documents: List[Dict[str, object]]) -> Dict[str, object]:
    """Compare native vision text against OCR/caption/text witnesses.

    Native vision is useful, but it is still a witness. This helper makes the
    comparison inspectable and prevents Sophia from silently preferring one
    modality when figures, charts, or scanned pages disagree.
    """
    witness_rows: List[Dict[str, object]] = []
    numeric_by_modality: Dict[str, List[str]] = {}
    text_by_modality: Dict[str, str] = {}
    for index, doc in enumerate(documents or [], start=1):
        if not isinstance(doc, dict):
            continue
        parser = str(doc.get("parser") or "")
        modality = str(doc.get("modality") or parser or f"witness_{index}")
        name = str(doc.get("source_name") or f"document_{index}")
        text = str(doc.get("extracted_text") or "")
        if not text.strip():
            continue
        lowered = text.lower()
        numbers = _numeric_claim_tokens(lowered)
        key = "native_vision" if "vision" in parser or "native_vision" in modality else (
            "ocr" if "ocr" in parser or "ocr" in modality else "text_or_caption"
        )
        numeric_by_modality.setdefault(key, []).extend(numbers)
        text_by_modality[key] = (text_by_modality.get(key, "") + "\n" + text[:1800]).strip()
        witness_rows.append({
            "witness_id": f"V{index}",
            "source_name": name,
            "modality_group": key,
            "parser": parser,
            "numbers": numbers[:20],
            "sample": text[:400],
        })

    native_numbers = set(numeric_by_modality.get("native_vision") or [])
    other_numbers = set()
    for key, values in numeric_by_modality.items():
        if key != "native_vision":
            other_numbers.update(values)
    has_native = "native_vision" in numeric_by_modality
    overlap = sorted(native_numbers & other_numbers)
    native_only = sorted(native_numbers - other_numbers)
    other_only = sorted(other_numbers - native_numbers)
    conflict = bool(has_native and native_numbers and other_numbers and (native_only or other_only))
    if not has_native:
        status = "native_vision_absent"
        confidence_ceiling = 0.65 if witness_rows else 0.35
    elif conflict:
        status = "native_vision_text_conflict"
        confidence_ceiling = 0.45
    else:
        status = "native_vision_consistent_with_text_witnesses"
        confidence_ceiling = 0.82
    return {
        "schema_version": "sophia.native_vision_comparison.v1",
        "status": status,
        "has_native_vision": has_native,
        "witness_count": len(witness_rows),
        "witnesses": witness_rows,
        "overlapping_numbers": overlap[:30],
        "native_only_numbers": native_only[:30],
        "text_or_ocr_only_numbers": other_only[:30],
        "confidence_ceiling": confidence_ceiling,
        "integrity_rule": (
            "Native vision may strengthen visual grounding, but disagreements with OCR, captions, "
            "tables, or page text must be reported rather than resolved silently."
        ),
    }


def map_figure_claim_to_evidence(
    claim: str,
    documents: List[Dict[str, object]],
    *,
    limit: int = 8,
) -> Dict[str, object]:
    """Map a figure/chart claim to visible caption, OCR, page, or vision spans."""
    claim = (claim or "").strip()
    lowered_claim = claim.lower()
    claim_numbers = _numeric_claim_tokens(lowered_claim)
    rows: List[Dict[str, object]] = []
    conflict_rows: List[Dict[str, object]] = []
    for doc in documents or []:
        if not isinstance(doc, dict):
            continue
        source_name = str(doc.get("source_name") or "document")
        parser = str(doc.get("parser") or "")
        spans = doc.get("spans") or []
        for span in spans:
            if not isinstance(span, dict):
                continue
            quote = str(span.get("quote") or "")
            lowered = quote.lower()
            has_visual_signal = any(token in lowered for token in ("figure", "fig.", "caption", "chart", "table", "diagram", "image"))
            if not has_visual_signal and not any(number in lowered for number in claim_numbers):
                continue
            quote_numbers = _numeric_claim_tokens(lowered)
            shared_numbers = sorted(set(claim_numbers) & set(quote_numbers))
            conflicting_numbers = sorted((set(claim_numbers) ^ set(quote_numbers)) if claim_numbers and quote_numbers else set())
            lexical_overlap = len(set(re.findall(r"[a-z][a-z0-9'-]{2,}", lowered_claim)) & set(re.findall(r"[a-z][a-z0-9'-]{2,}", lowered)))
            status = "candidate_support"
            if claim_numbers and quote_numbers and not shared_numbers:
                status = "possible_numeric_conflict"
            elif not shared_numbers and lexical_overlap < 2:
                status = "weak_visual_lead"
            row = {
                "source_name": source_name,
                "parser": parser,
                "span_id": span.get("span_id") or "",
                "page": span.get("page") or span.get("page_number") or "",
                "locator": span.get("locator") or "",
                "status": status,
                "shared_numbers": shared_numbers,
                "conflicting_numbers": conflicting_numbers[:20],
                "quote": quote[:700],
            }
            rows.append(row)
            if status == "possible_numeric_conflict":
                conflict_rows.append(row)
    rows.sort(key=lambda row: (row["status"] != "candidate_support", str(row.get("page") or ""), str(row.get("span_id") or "")))
    final_status = "no_visual_evidence_found"
    if conflict_rows:
        final_status = "figure_claim_conflict_requires_verification"
    elif rows:
        final_status = "figure_claim_has_candidate_evidence"
    return {
        "schema_version": "sophia.figure_claim_mapping.v1",
        "claim": claim[:900],
        "status": final_status,
        "claim_numbers": claim_numbers,
        "candidate_mappings": rows[:limit],
        "conflict_count": len(conflict_rows),
        "integrity_rule": (
            "Figure-to-text claims require visible caption/OCR/native-vision/table evidence with a locator; "
            "conflicting captions or chart numbers must be handed back for inspection."
        ),
    }


def _page_markers(text: str) -> List[int]:
    markers = [int(match.group(1)) for match in re.finditer(r"\b(?:page|p\.)\s*(\d{1,4})\b", text or "", flags=re.I)]
    return sorted(set(markers))


def _numeric_claim_tokens(text: str) -> List[str]:
    """Return normalized numeric evidence tokens while filtering page/table labels."""
    tokens: List[str] = []
    pattern = re.compile(
        r"(?<![a-z])(?P<label>page|p\.|table|figure|fig\.)?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>%|percent|points?|scores?|students?|hours?|drafts?)?",
        flags=re.I,
    )
    for match in pattern.finditer(text or ""):
        label = (match.group("label") or "").lower()
        unit = (match.group("unit") or "").lower()
        if label in {"page", "p.", "table", "figure", "fig."} and not unit:
            continue
        number = match.group("num")
        token = f"{number}%" if unit in {"%", "percent"} else number
        tokens.append(token)
    return sorted(set(tokens))


def _document_inspection(
    *,
    parser: str,
    modality: str,
    text: str,
    spans: List[Dict[str, object]],
    uncertainty: List[str],
) -> Dict[str, object]:
    """Summarise what Sophia may safely claim about a document."""
    lowered = (text or "").lower()
    pages_from_spans = sorted({int(span["page"]) for span in spans if str(span.get("page") or "").isdigit()})
    pages_from_markers = _page_markers(text)
    page_numbers = sorted(set(pages_from_spans + pages_from_markers))
    figure_terms = ("figure", "fig", "caption", "image", "diagram", "chart", "screenshot")
    table_terms = ("table", "column", "row", "matrix", "dataset", "appendix")
    has_figure_signal = bool(re.search(r"\b(" + "|".join(re.escape(term) for term in figure_terms) + r")\b", lowered))
    has_table_signal = bool(re.search(r"\b(" + "|".join(re.escape(term) for term in table_terms) + r")\b", lowered))
    notes = list(dict.fromkeys(str(note) for note in uncertainty if str(note).strip()))
    warnings: List[str] = []
    if not page_numbers:
        warnings.append("page_number_unavailable")
    if has_figure_signal and parser not in {"native_tesseract_ocr", "sidecar_ocr"}:
        warnings.append("figure_or_caption_text_only_no_native_vision")
    if has_table_signal:
        warnings.append("table_structure_uncertain_without_table_parser")
    if any(note in notes for note in ("ocr_sidecar_missing", "native_tesseract_empty")):
        warnings.append("image_text_unavailable")
    if any("tesseract" in note or "ocr" in note for note in notes):
        warnings.append("ocr_mediated_evidence")
    readable_chars = len((text or "").strip())
    coverage = "none"
    if readable_chars > 12000:
        coverage = "broad"
    elif readable_chars > 2500:
        coverage = "moderate"
    elif readable_chars > 0:
        coverage = "thin"
    return {
        "parser": parser,
        "modality": modality,
        "readable_chars": readable_chars,
        "span_count": len(spans),
        "page_numbers": page_numbers[:60],
        "page_count_detected": len(page_numbers),
        "page_coverage": coverage,
        "figure_signal": has_figure_signal,
        "table_signal": has_table_signal,
        "page_number_status": "page markers visible" if page_numbers else "no page number visible; do not invent one",
        "figure_status": "caption/figure text signal only; no independent image interpretation" if has_figure_signal else "no figure signal detected",
        "table_status": "table-like text detected; structure may be uncertain" if has_table_signal else "no table signal detected",
        "warnings": list(dict.fromkeys(warnings)),
        "safe_use": [
            "quote only readable extracted spans",
            "cite page numbers only when page markers are visible",
            "treat captions/tables as text evidence unless native vision/table parsing is available",
            "state uncertainty before interpreting degraded OCR",
        ],
    }


def _extract_pdf_text(path: Path) -> tuple[str, List[str], str]:
    notes: List[str] = []
    try:
        import pdfplumber  # type: ignore
        page_parts: List[str] = []
        table_count = 0
        with pdfplumber.open(path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text(layout=True) or page.extract_text() or ""
                table_blocks: List[str] = []
                try:
                    tables = page.extract_tables() or []
                except Exception:
                    tables = []
                    notes.append(f"pdfplumber_page_{page_index}_table_extract_failed")
                for table_index, table in enumerate(tables, start=1):
                    rows = [
                        [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
                        for row in table
                        if row and any(str(cell or "").strip() for cell in row)
                    ]
                    if len(rows) < 2:
                        continue
                    table_count += 1
                    table_blocks.append(f"[TABLE page={page_index} index={table_index}]")
                    table_blocks.extend(" | ".join(row) for row in rows[:60])
                combined = "\n".join(part for part in (f"Page {page_index}", page_text, "\n".join(table_blocks)) if part.strip())
                page_parts.append(combined)
        extracted = "\f".join(page_parts).strip()
        if extracted:
            notes.append("pdfplumber_page_aware")
            if table_count:
                notes.append(f"pdfplumber_tables_detected:{table_count}")
            return extracted, notes, "pdfplumber"
        notes.append("pdfplumber_empty")
    except Exception as exc:
        notes.append(f"pdfplumber_unavailable_or_failed:{type(exc).__name__}")

    if shutil.which("pdftotext"):
        proc = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout, notes, "pdftotext"
        notes.append("pdftotext_failed")
    else:
        notes.append("pdftotext_unavailable")

    sidecars = [
        path.with_suffix(path.suffix + ".txt"),
        path.with_suffix(".txt"),
        path.parent / f"{path.name}.ocr.txt",
    ]
    for sidecar in sidecars:
        if sidecar.exists():
            notes.append(f"used_sidecar:{sidecar.name}")
            return sidecar.read_text(encoding="utf-8"), notes, "sidecar_text"

    return "", notes, "unavailable"


def _extract_image_sidecar_text(path: Path) -> tuple[str, List[str], str]:
    notes: List[str] = []
    candidates = [
        path.with_suffix(path.suffix + ".ocr.txt"),
        path.with_suffix(path.suffix + ".txt"),
        path.with_suffix(".txt"),
        path.parent / f"{path.stem}.ocr.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            notes.append(f"used_sidecar:{candidate.name}")
            return candidate.read_text(encoding="utf-8"), notes, "sidecar_ocr"
    notes.append("ocr_sidecar_missing")
    return "", notes, "unavailable"


def _extract_image_ocr_text(path: Path) -> tuple[str, List[str], str]:
    """Extract bounded OCR text from an image, with sidecar fallback.

    OCR is evidence, not sight. Sophia may use readable spans, but must still
    mark uncertainty when OCR is sparse, blurry, or missing.
    """
    notes: List[str] = []
    if pytesseract is not None and Image is not None and ImageOps is not None and shutil.which("tesseract"):
        try:
            with Image.open(path) as image:
                normalized = ImageOps.exif_transpose(image).convert("L")
                text = pytesseract.image_to_string(normalized, lang="eng")
            if text.strip():
                notes.append("native_tesseract_ocr")
                return text, notes, "native_tesseract_ocr"
            notes.append("native_tesseract_empty")
        except Exception as exc:
            notes.append(f"native_tesseract_failed:{type(exc).__name__}")
    else:
        notes.append("native_tesseract_unavailable")

    sidecar_text, sidecar_notes, parser = _extract_image_sidecar_text(path)
    return sidecar_text, notes + sidecar_notes, parser


def _extract_text(path: Path) -> tuple[str, List[str], str]:
    suffix = path.suffix.lower()
    notes: List[str] = []
    if suffix in {".txt", ".md", ".rst", ".csv", ".tsv"}:
        return path.read_text(encoding="utf-8"), notes, "plain_text"
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(payload, indent=2), notes, "json_pretty"
    if suffix in {".html", ".htm"}:
        parser = _HTMLTextExtractor()
        parser.feed(path.read_text(encoding="utf-8"))
        return parser.text(), notes, "html_text"
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix in IMAGE_SUFFIXES:
        return _extract_image_ocr_text(path)
    return path.read_text(encoding="utf-8"), notes, "fallback_text"


def extract_document_evidence(
    source_path: str | Path,
    *,
    modality: str = "text_only",
    task_label: Optional[str] = None,
    max_chars: int = MAX_EXTRACTED_CHARS,
) -> Dict[str, object]:
    path = Path(source_path)
    extracted_text, extraction_notes, parser = _extract_text(path)
    extracted_text = _truncate(extracted_text, max_chars=max_chars)
    uncertainty = extraction_notes + _uncertainty_notes(extracted_text)
    quality = _document_quality(
        parser=parser,
        modality=modality,
        text=extracted_text,
        uncertainty=uncertainty,
    )
    provenance = _source_provenance(path, modality, extracted_text)
    spans = _build_spans(extracted_text)
    return {
        "source_path": str(path),
        "source_name": path.name,
        "modality": modality,
        "task_label": task_label,
        "parser": parser,
        "evidence_quality": quality,
        "source_provenance": provenance,
        "extracted_text": extracted_text,
        "spans": spans,
        "uncertainty_notes": uncertainty,
        "document_inspection": _document_inspection(
            parser=parser,
            modality=modality,
            text=extracted_text,
            spans=spans,
            uncertainty=uncertainty,
        ),
    }


def build_document_evidence_bundle(
    sources: List[Dict[str, object]],
    *,
    evidence_task: Optional[str] = None,
) -> Dict[str, object]:
    documents: List[Dict[str, object]] = []
    for source in sources:
        documents.append(
            extract_document_evidence(
                source["source_path"],
                modality=str(source.get("modality") or "text_only"),
                task_label=str(source.get("task_label") or "") or None,
            )
        )
    return {
        "evidence_task": evidence_task,
        "documents": documents,
        "cross_source_warnings": _cross_source_warnings(documents),
        "multimodal_disagreement": classify_multimodal_disagreement(documents),
        "cross_modal_evidence_ledger": build_cross_modal_evidence_ledger(documents),
        "native_vision_comparison": compare_native_vision_witnesses(documents),
    }


def render_document_evidence_context(bundle: Optional[Dict[str, object]]) -> str:
    if not bundle:
        return ""
    documents = bundle.get("documents") or []
    if not isinstance(documents, list) or not documents:
        return ""

    lines = [
        "[DOCUMENT EVIDENCE CONTRACT]",
        "Use only the provided source evidence unless you explicitly mark an inference.",
        "If the source is blurry, partial, unreadable, or unsupported, say so plainly.",
        "When asked for a quote, quote an exact local phrase from a span or say exact support is absent.",
    ]
    evidence_task = bundle.get("evidence_task")
    if evidence_task:
        lines.append(f"Evidence task: {evidence_task}")

    ledger = bundle.get("cross_modal_evidence_ledger") or {}
    if isinstance(ledger, dict) and ledger:
        lines.extend([
            "",
            "[CROSS-MODAL EVIDENCE LEDGER]",
            f"ledger_status={ledger.get('status')} confidence_ceiling={ledger.get('confidence_ceiling')} witness_count={ledger.get('witness_count')}",
            "safe_claims=" + " | ".join(str(item) for item in (ledger.get("safe_claims") or [])[:4]),
            "blocked_claims=" + " | ".join(str(item) for item in (ledger.get("blocked_claims") or [])[:4]),
            "required_next_steps=" + " | ".join(str(item) for item in (ledger.get("required_next_steps") or [])[:4]),
        ])
        visual = ledger.get("visual_witnesses") or []
        degraded = ledger.get("degraded_witnesses") or []
        if visual:
            lines.append("visual_witnesses=" + ", ".join(str(item) for item in visual))
        if degraded:
            lines.append("degraded_witnesses=" + ", ".join(str(item) for item in degraded))
    native_comparison = bundle.get("native_vision_comparison") or {}
    if isinstance(native_comparison, dict) and native_comparison:
        lines.extend([
            "",
            "[NATIVE VISION COMPARISON]",
            f"status={native_comparison.get('status')} confidence_ceiling={native_comparison.get('confidence_ceiling')} witness_count={native_comparison.get('witness_count')}",
            "native_only_numbers=" + ", ".join(str(item) for item in (native_comparison.get("native_only_numbers") or [])[:10]),
            "text_or_ocr_only_numbers=" + ", ".join(str(item) for item in (native_comparison.get("text_or_ocr_only_numbers") or [])[:10]),
        ])

    for index, document in enumerate(documents, start=1):
        lines.append("")
        lines.append(f"[SOURCE {index}] {document.get('source_name')}")
        lines.append(f"modality={document.get('modality')} parser={document.get('parser')}")
        quality = document.get("evidence_quality") or {}
        if quality:
            lines.append(
                f"quality={quality.get('quality')} score={quality.get('score')} rationale={quality.get('rationale')}"
            )
        provenance = document.get("source_provenance") or {}
        if provenance:
            lines.append(
                f"provenance_tier={provenance.get('tier')} provenance_score={provenance.get('score')} rationale={provenance.get('rationale')}"
            )
        uncertainty = document.get("uncertainty_notes") or []
        if uncertainty:
            lines.append("uncertainty=" + ", ".join(str(item) for item in uncertainty))
        inspection = document.get("document_inspection") or {}
        if inspection:
            lines.append(
                "inspection="
                + f"readable_chars={inspection.get('readable_chars')} "
                + f"page_coverage={inspection.get('page_coverage')} "
                + f"page_status={inspection.get('page_number_status')} "
                + f"figure_status={inspection.get('figure_status')} "
                + f"table_status={inspection.get('table_status')}"
            )
            warnings_for_doc = inspection.get("warnings") or []
            if warnings_for_doc:
                lines.append("inspection_warnings=" + ", ".join(str(item) for item in warnings_for_doc))
        warnings = bundle.get("cross_source_warnings") or []
        if warnings:
            lines.append("cross_source_warnings=" + ", ".join(str(item) for item in warnings))
        disagreement = bundle.get("multimodal_disagreement") or {}
        if disagreement:
            lines.append(
                "multimodal_disagreement="
                + f"status={disagreement.get('status')} "
                + f"safe_response_mode={disagreement.get('safe_response_mode')}"
            )
        spans = document.get("spans") or []
        for span in spans:
            lines.append(f"{span.get('span_id')}: {span.get('quote')}")

    return "\n".join(lines)


def inspect_document_page(
    bundle: Optional[Dict[str, object]],
    page_number: int,
    *,
    source_name: Optional[str] = None,
) -> Dict[str, object]:
    """Return bounded page-specific evidence without inventing page anchors."""
    if not bundle or page_number <= 0:
        return {
            "status": "no_document_evidence",
            "page_number": page_number,
            "spans": [],
            "summary": "",
            "warnings": ["no document evidence available"],
        }
    documents = list((bundle or {}).get("documents") or [])
    selected_docs = [
        doc for doc in documents
        if not source_name or str(doc.get("source_name") or "") == source_name
    ]
    spans: List[Dict[str, object]] = []
    warnings: List[str] = []
    for doc in selected_docs:
        inspection = doc.get("document_inspection") or {}
        warnings.extend(str(w) for w in (inspection.get("warnings") or []))
        for span in doc.get("spans") or []:
            if str(span.get("page") or "") == str(page_number) or str(span.get("page_number") or "") == str(page_number):
                enriched = dict(span)
                enriched["source_name"] = doc.get("source_name")
                enriched["parser"] = doc.get("parser")
                enriched["evidence_quality"] = doc.get("evidence_quality")
                spans.append(enriched)
    if not spans:
        return {
            "status": "page_not_available",
            "page_number": page_number,
            "spans": [],
            "summary": "",
            "warnings": list(dict.fromkeys(warnings + ["requested page has no extracted spans; do not invent page evidence"])),
        }
    summary_text = " ".join(str(span.get("quote") or "") for span in spans[:4])
    return {
        "status": "page_available",
        "page_number": page_number,
        "spans": spans[:12],
        "summary": summary_text[:900],
        "warnings": list(dict.fromkeys(warnings)),
        "page_number_status": "page markers visible",
    }


def compare_claim_to_document_page(
    claim: str,
    bundle: Optional[Dict[str, object]],
    page_number: int,
    *,
    source_name: Optional[str] = None,
) -> Dict[str, object]:
    """Compare a learner claim to a page's readable spans using the Phase 6 guard."""
    page = inspect_document_page(bundle, page_number, source_name=source_name)
    if page.get("status") != "page_available":
        return {
            "status": page.get("status"),
            "page_number": page_number,
            "similarity": None,
            "warnings": page.get("warnings") or [],
        }
    try:
        from backend.services.sophia_similarity_guard import analyze_similarity
    except Exception:  # pragma: no cover
        return {
            "status": "similarity_guard_unavailable",
            "page_number": page_number,
            "similarity": None,
            "warnings": ["similarity guard unavailable"],
        }
    sources = [
        {
            "source_name": f"{span.get('source_name', source_name or 'document')} p. {page_number}",
            "text": span.get("quote") or "",
            "page": page_number,
        }
        for span in page.get("spans") or []
    ]
    return {
        "status": "checked",
        "page_number": page_number,
        "page_summary": page.get("summary") or "",
        "similarity": analyze_similarity(claim, sources, limit=5),
        "warnings": page.get("warnings") or [],
    }


def cite_document_page(
    bundle: Optional[Dict[str, object]],
    page_number: int,
    *,
    source_name: Optional[str] = None,
    style: str = "bounded",
) -> Dict[str, object]:
    """Build a page citation lead only when page evidence is visible."""
    page = inspect_document_page(bundle, page_number, source_name=source_name)
    if page.get("status") != "page_available":
        return {
            "status": "page_citation_unavailable",
            "page_number": page_number,
            "citation_lead": "",
            "quote_leads": [],
            "warnings": page.get("warnings") or ["requested page is not available; do not invent citation"],
            "integrity_rule": "No page citation may be suggested without visible page/span evidence.",
        }
    spans = list(page.get("spans") or [])
    first = spans[0] if spans else {}
    doc_name = str(first.get("source_name") or source_name or "uploaded document").strip()
    locator = f"p. {page_number}"
    citation_lead = f"{doc_name}, {locator}"
    if style.lower() in {"apa", "apa7"}:
        citation_lead = f"{doc_name} ({locator})"
    return {
        "status": "page_citation_lead",
        "page_number": page_number,
        "source_name": doc_name,
        "page_locator": locator,
        "citation_lead": citation_lead,
        "quote_leads": [
            {
                "span_id": span.get("span_id") or "",
                "quote": str(span.get("quote") or "")[:500],
                "locator": locator,
                "parser": span.get("parser") or "",
            }
            for span in spans[:6]
        ],
        "warnings": page.get("warnings") or [],
        "integrity_rule": "This is a citation lead for human verification, not a finalized reference.",
    }
