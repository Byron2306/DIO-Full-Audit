"""Advanced evidence checks for Sophia's Writing Desk.

This module is intentionally dependency-light.  If optional neural libraries are
installed and explicitly enabled, Sophia can use them; otherwise she falls back
to inspectable deterministic scoring and says so in the returned method fields.
"""

from __future__ import annotations

import csv
from html.parser import HTMLParser
import io
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


STOPWORDS = {
    "about", "after", "again", "also", "because", "before", "between", "could",
    "from", "have", "into", "only", "should", "than", "that", "their", "there",
    "these", "this", "through", "with", "would", "your",
}

CONCEPT_FAMILIES = {
    "agency": {"agency", "authorship", "autonomy", "control", "choice", "intention", "responsibility"},
    "integrity": {"integrity", "provenance", "citation", "source", "evidence", "audit", "accountability"},
    "pedagogy": {"learning", "scaffold", "zpd", "feedback", "assessment", "formative", "ipsative", "reflection"},
    "governance": {"policy", "constitution", "rule", "law", "mandate", "governance", "compliance"},
    "evaluation": {"protocol", "test", "benchmark", "matrix", "metric", "pass", "failure", "ablation"},
    "adversarial": {"adversarial", "attack", "deception", "threat", "risk", "misuse", "evasion"},
    "multimodal": {"image", "figure", "table", "chart", "diagram", "ocr", "vision", "caption"},
}

NEGATION_TERMS = {"no", "not", "never", "without", "fails", "failed", "cannot", "doesn't", "didn't", "absence"}
CLAIM_STRENGTH_TERMS = {"proves", "establishes", "guarantees", "always", "never", "causes", "demonstrates"}
_EMBEDDING_MODEL: Any = None
_NLI_PIPELINE: Any = None


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: List[List[List[str]]] = []
        self._in_table = False
        self._in_cell = False
        self._current_table: List[List[str]] = []
        self._current_row: List[str] = []
        self._current_cell: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif self._in_table and tag == "tr":
            self._current_row = []
        elif self._in_table and tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._in_table and tag in {"td", "th"}:
            self._current_row.append(re.sub(r"\s+", " ", " ".join(self._current_cell)).strip())
            self._in_cell = False
            self._current_cell = []
        elif self._in_table and tag == "tr":
            if any(cell for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = []
        elif tag == "table" and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._in_table = False
            self._current_table = []


def _tokens(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z][a-z0-9'-]{2,}", (text or "").lower())
        if token not in STOPWORDS
    ]


def _tf(tokens: Iterable[str]) -> Counter[str]:
    return Counter(tokens)


def _cosine(left: str, right: str) -> float:
    left_tf = _tf(_tokens(left))
    right_tf = _tf(_tokens(right))
    if not left_tf or not right_tf:
        return 0.0
    shared = set(left_tf) & set(right_tf)
    dot = sum(left_tf[token] * right_tf[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left_tf.values()))
    right_norm = math.sqrt(sum(value * value for value in right_tf.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _concept_hits(text: str) -> set[str]:
    lowered = (text or "").lower()
    hits: set[str] = set()
    for family, terms in CONCEPT_FAMILIES.items():
        if any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", lowered) for term in terms):
            hits.add(family)
    return hits


def _concept_score(left: str, right: str) -> float:
    left_hits = _concept_hits(left)
    right_hits = _concept_hits(right)
    if not left_hits or not right_hits:
        return 0.0
    return len(left_hits & right_hits) / len(left_hits | right_hits)


def _best_span(claim: str, text: str, *, max_chars: int = 700) -> Dict[str, Any]:
    chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[.!?])\s+|\n{2,}", text or "")
        if len(chunk.strip()) >= 20
    ]
    if not chunks and text.strip():
        chunks = [text.strip()]
    best = {"span": "", "score": 0.0, "concept_score": 0.0, "lexical_score": 0.0}
    for chunk in chunks[:160]:
        lexical = _cosine(claim, chunk)
        concept = _concept_score(claim, chunk)
        score = min(1.0, lexical * 0.65 + concept * 0.35)
        if score > best["score"]:
            best = {
                "span": chunk[:max_chars],
                "score": round(score, 3),
                "concept_score": round(concept, 3),
                "lexical_score": round(lexical, 3),
            }
    return best


def _get_embedding_model() -> Any:
    """Load a local embedding model only when explicitly enabled.

    `SOPHIA_LOCAL_EMBEDDING_MODEL` should point to an already available local
    model path/name. We do not trigger surprise downloads from live UI use.
    """
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    if os.environ.get("SOPHIA_ENABLE_LOCAL_EMBEDDINGS") != "1":
        return None
    model_name = os.environ.get("SOPHIA_LOCAL_EMBEDDING_MODEL") or ""
    if not model_name:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _EMBEDDING_MODEL = SentenceTransformer(model_name)
        return _EMBEDDING_MODEL
    except Exception:
        _EMBEDDING_MODEL = None
        return None


def _embedding_similarity(model: Any, left: str, right: str) -> Optional[float]:
    try:
        embeddings = model.encode([left, right], normalize_embeddings=True)
        return float(sum(float(a) * float(b) for a, b in zip(embeddings[0], embeddings[1])))
    except Exception:
        return None


def _get_nli_pipeline() -> Any:
    """Load a local NLI model only when explicitly enabled."""
    global _NLI_PIPELINE
    if _NLI_PIPELINE is not None:
        return _NLI_PIPELINE
    if os.environ.get("SOPHIA_ENABLE_LOCAL_NLI") != "1":
        return None
    model_name = os.environ.get("SOPHIA_LOCAL_NLI_MODEL") or ""
    if not model_name:
        return None
    try:
        from transformers import pipeline  # type: ignore
        _NLI_PIPELINE = pipeline("text-classification", model=model_name, tokenizer=model_name)
        return _NLI_PIPELINE
    except Exception:
        _NLI_PIPELINE = None
        return None


def _neural_nli_label(claim: str, evidence_span: str) -> Optional[Dict[str, Any]]:
    pipe = _get_nli_pipeline()
    if not pipe:
        return None
    try:
        output = pipe(f"{evidence_span} </s></s> {claim}", truncation=True)
        row = output[0] if isinstance(output, list) and output else output
        raw_label = str((row or {}).get("label") or "").lower()
        score = float((row or {}).get("score") or 0.0)
    except Exception:
        return None
    if "contrad" in raw_label:
        label = "contradicts"
    elif "entail" in raw_label:
        label = "supports"
    elif "neutral" in raw_label:
        label = "not_enough_information"
    else:
        label = "partially_supports"
    return {
        "method": "local_neural_nli",
        "label": label,
        "confidence": round(score, 3),
        "raw_label": raw_label,
        "rationale": "Local NLI model output; still bounded by visible source span and provenance checks.",
    }


def _source_text(source: Dict[str, Any]) -> str:
    direct = str(source.get("text") or source.get("summary") or source.get("abstract") or source.get("extracted_text") or "").strip()
    if direct:
        return direct
    parts: List[str] = []
    for span in source.get("spans") or []:
        if isinstance(span, dict):
            quote = str(span.get("quote") or span.get("text") or "").strip()
            if quote:
                parts.append(quote)
    return "\n".join(parts)


def _source_name(source: Dict[str, Any], fallback: str = "source") -> str:
    return str(source.get("source_name") or source.get("name") or source.get("title") or fallback).strip()


def rank_evidence_spans(claim: str, sources: List[Dict[str, Any]], *, limit: int = 8) -> Dict[str, Any]:
    """Rank candidate source spans by optional embedding or deterministic semantic overlap."""
    method = "deterministic_lexical_concept_embedding_fallback"
    embedding_model = _get_embedding_model()
    if embedding_model is not None:
        method = "local_sentence_transformers_embedding"

    rows: List[Dict[str, Any]] = []
    for index, source in enumerate(sources or [], start=1):
        if not isinstance(source, dict):
            continue
        text = _source_text(source)
        match = _best_span(claim, text)
        embedding_score = _embedding_similarity(embedding_model, claim, match["span"] or text[:1200]) if embedding_model is not None else None
        final_score = round((match["score"] * 0.45 + embedding_score * 0.55), 3) if embedding_score is not None else match["score"]
        rows.append({
            "source_name": _source_name(source, f"source {index}"),
            "score": final_score,
            "lexical_score": match["lexical_score"],
            "concept_score": match["concept_score"],
            "embedding_score": round(embedding_score, 3) if embedding_score is not None else None,
            "matched_span": match["span"],
            "page": source.get("page") or source.get("page_number") or "",
            "method": method,
        })
    rows.sort(key=lambda row: row["score"], reverse=True)
    return {
        "method": method,
        "claim": claim[:900],
        "sources_considered": len(sources or []),
        "ranked_spans": rows[:limit],
    }


def judge_claim_support(claim: str, evidence_span: str) -> Dict[str, Any]:
    """Return NLI-style support while keeping fallback reasoning auditable."""
    neural = _neural_nli_label(claim, evidence_span)
    if neural:
        fallback = judge_claim_support_fallback(claim, evidence_span)
        neural["fallback_check"] = fallback
        if neural["label"] == "supports" and fallback["label"] in {"contradicts", "not_enough_information"}:
            neural["label"] = "partially_supports"
            neural["rationale"] += " Deterministic fallback disagreed, so Sophia downgraded the support claim."
        return neural
    return judge_claim_support_fallback(claim, evidence_span)


def judge_claim_support_fallback(claim: str, evidence_span: str) -> Dict[str, Any]:
    """Deterministic NLI-style support fallback."""
    score = _best_span(claim, evidence_span)["score"]
    claim_tokens = set(_tokens(claim))
    span_tokens = set(_tokens(evidence_span))
    claim_has_strong_scope = bool(claim_tokens & CLAIM_STRENGTH_TERMS)
    span_has_negation = bool(span_tokens & NEGATION_TERMS)
    shared_concepts = sorted(_concept_hits(claim) & _concept_hits(evidence_span))

    contradiction_pattern = bool(re.search(
        r"\b(?:no evidence|does not|did not|failed to|without evidence|not establish|not demonstrate)\b",
        evidence_span or "",
        flags=re.I,
    ))
    if contradiction_pattern and (score >= 0.08 or shared_concepts):
        label = "contradicts"
        confidence = min(0.9, 0.55 + score)
    elif score >= 0.24 and not (claim_has_strong_scope and span_has_negation):
        label = "supports"
        confidence = min(0.92, 0.56 + score)
    elif score >= 0.16 or shared_concepts:
        label = "partially_supports"
        confidence = min(0.78, 0.43 + score)
    else:
        label = "not_enough_information"
        confidence = max(0.36, 0.62 - score)

    return {
        "method": "deterministic_nli_fallback",
        "label": label,
        "confidence": round(confidence, 3),
        "similarity_score": round(score, 3),
        "shared_concepts": shared_concepts,
        "rationale": (
            "Visible-span judgment only; this is not treated as final entailment "
            "unless provenance and page/span evidence are inspected."
        ),
    }


def extract_structured_tables(sources: List[Dict[str, Any]], *, max_rows: int = 20) -> Dict[str, Any]:
    """Extract CSV/TSV, Markdown pipe, simple HTML, and fixed-width text tables."""
    tables: List[Dict[str, Any]] = []
    for index, source in enumerate(sources or [], start=1):
        if not isinstance(source, dict):
            continue
        name = _source_name(source, f"source {index}")
        text = _source_text(source)
        page = source.get("page") or source.get("page_number") or ""
        if not text:
            continue
        for table in _extract_html_tables(name, text, max_rows=max_rows, page=page):
            tables.append(table)
        for table in _extract_markdown_tables(name, text, max_rows=max_rows, page=page):
            tables.append(table)
        for table in _extract_delimited_tables(name, text, max_rows=max_rows, page=page):
            tables.append(table)
        for table in _extract_fixed_width_tables(name, text, max_rows=max_rows, page=page):
            tables.append(table)
    return {
        "method": "multi_parser_structured_table_extraction",
        "tables_detected": len(tables),
        "tables": tables,
    }


def _cell_citations(
    source_name: str,
    parser: str,
    headers: List[str],
    rows: List[Dict[str, str]],
    *,
    page: Any = "",
    table_index: int = 1,
) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    page_text = str(page or "").strip()
    for row_number, row in enumerate(rows, start=1):
        for column_number, header in enumerate(headers, start=1):
            value = str(row.get(header) or "").strip()
            if not value:
                continue
            locator_parts = [f"table {table_index}", f"row {row_number}", f"column {column_number} ({header})"]
            if page_text:
                locator_parts.insert(0, f"p. {page_text}")
            citations.append({
                "source_name": source_name,
                "parser": parser,
                "page": page_text,
                "table_index": table_index,
                "row": row_number,
                "column": column_number,
                "header": header,
                "value": value,
                "locator": ", ".join(locator_parts),
                "citation_lead": f"{source_name}, {', '.join(locator_parts)}",
                "integrity_rule": "Cell citation is a verification lead; inspect the original table before final submission.",
            })
    return citations


def _table_payload(
    source_name: str,
    parser: str,
    headers: List[str],
    rows: List[Dict[str, str]],
    max_rows: int,
    *,
    page: Any = "",
    table_index: int = 1,
) -> Dict[str, Any]:
    visible_rows = rows[:max_rows]
    return {
        "source_name": source_name,
        "parser": parser,
        "headers": headers,
        "rows": visible_rows,
        "row_count_detected": len(rows),
        "column_count_detected": len(headers),
        "page": str(page or ""),
        "table_index": table_index,
        "cell_citations": _cell_citations(
            source_name,
            parser,
            headers,
            visible_rows,
            page=page,
            table_index=table_index,
        ),
        "truncated": len(rows) > max_rows,
        "integrity_rule": "Parsed table cells are evidence leads; statistical claims still need method, denominator, and extraction checks.",
    }


def export_table_cell_citations(
    sources: List[Dict[str, Any]],
    *,
    max_rows: int = 50,
    limit: int = 200,
) -> Dict[str, Any]:
    """Export page/cell-level table citation leads across parsed table witnesses."""
    tables = extract_structured_tables(sources, max_rows=max_rows)
    citations: List[Dict[str, Any]] = []
    for table in tables.get("tables") or []:
        for citation in table.get("cell_citations") or []:
            citations.append(citation)
    return {
        "method": "sophia_page_cell_citation_export_v1",
        "tables_detected": tables.get("tables_detected", 0),
        "cell_citation_count": len(citations),
        "cell_citations": citations[:limit],
        "truncated": len(citations) > limit,
        "integrity_contract": [
            "export only parsed visible cells",
            "carry page/table/row/column locator when available",
            "treat exported citations as human-verification leads, not finalized references",
        ],
    }


def normalize_merged_header_table(table: Dict[str, Any]) -> Dict[str, Any]:
    """Detect simple multi-row/merged-header scientific table shapes.

    This is not a full layout model. It upgrades common extracted text tables
    where header rows contain grouped columns, footnote markers, or statistical
    notation, while preserving the original parser output as evidence.
    """
    headers = [str(item or "").strip() for item in (table.get("headers") or [])]
    rows = list(table.get("rows") or [])
    normalized_headers: List[str] = []
    footnote_markers: List[str] = []
    statistical_columns: List[str] = []
    for index, header in enumerate(headers, start=1):
        cleaned = re.sub(r"\s+", " ", header).strip()
        marker_hits = re.findall(r"(?:\*+|[a-z]\)|†|‡|§)", cleaned)
        footnote_markers.extend(marker_hits)
        if re.search(r"\b(?:mean|sd|se|ci|p|p-value|n|or|rr|β|beta|χ|t|f)\b", cleaned, flags=re.I):
            statistical_columns.append(cleaned)
        if not cleaned:
            cleaned = f"column_{index}"
        normalized_headers.append(cleaned)
    row_citation_count = sum(len(row) for row in rows if isinstance(row, dict))
    complexity_flags: List[str] = []
    if footnote_markers:
        complexity_flags.append("footnote_markers_present")
    if statistical_columns:
        complexity_flags.append("statistical_notation_present")
    if len(set(normalized_headers)) < len(normalized_headers):
        complexity_flags.append("duplicate_or_merged_header_labels")
    if any(" / " in header or "\n" in header for header in headers):
        complexity_flags.append("possible_grouped_header")
    return {
        "schema_version": "sophia.merged_header_table_normalization.v1",
        "source_name": table.get("source_name") or "",
        "parser": table.get("parser") or "",
        "page": table.get("page") or "",
        "original_headers": headers,
        "normalized_headers": normalized_headers,
        "statistical_columns": statistical_columns,
        "footnote_markers": sorted(set(footnote_markers)),
        "complexity_flags": complexity_flags,
        "row_count_detected": table.get("row_count_detected", len(rows)),
        "cell_citation_count": len(table.get("cell_citations") or []) or row_citation_count,
        "integrity_rule": "Merged-header normalization is a table-audit aid; verify statistical labels and footnotes against the original table image/PDF.",
    }


def export_audit_packets(
    payload: Dict[str, Any],
    *,
    output_dir: str | os.PathLike[str],
    prefix: str = "sophia_document_audit",
) -> Dict[str, Any]:
    """Export Sophia evidence into CSV, JSONL, and Zotero/CSL-friendly JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = list(payload.get("cell_citations") or payload.get("citations") or [])
    sources = list(payload.get("sources") or [])
    jsonl_path = out / f"{prefix}.jsonl"
    csv_path = out / f"{prefix}.csv"
    zotero_path = out / f"{prefix}_zotero_csl.json"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "audit_summary", "payload": payload.get("summary") or {}}, ensure_ascii=False, default=str) + "\n")
        for row in rows:
            handle.write(json.dumps({"type": "cell_citation", **dict(row)}, ensure_ascii=False, default=str) + "\n")
    fieldnames = [
        "source_name", "page", "table_index", "row", "column", "header",
        "value", "locator", "citation_lead", "integrity_rule",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    csl_items = []
    seen = set()
    for source in sources or rows:
        title = str(source.get("title") or source.get("source_name") or source.get("name") or "Uploaded document").strip()
        key = (title, str(source.get("url") or source.get("doi") or ""))
        if key in seen:
            continue
        seen.add(key)
        item = {
            "type": "document",
            "title": title,
            "id": re.sub(r"[^A-Za-z0-9_-]+", "-", title).strip("-")[:80] or "sophia-source",
            "note": "Sophia audit lead; verify bibliographic metadata before final citation.",
        }
        if source.get("url"):
            item["URL"] = source.get("url")
        if source.get("doi"):
            item["DOI"] = source.get("doi")
        if source.get("year"):
            item["issued"] = {"date-parts": [[source.get("year")]]}
        csl_items.append(item)
    zotero_path.write_text(json.dumps(csl_items, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return {
        "schema_version": "sophia.audit_packet_export.v1",
        "csv": str(csv_path),
        "jsonl": str(jsonl_path),
        "zotero_csl_json": str(zotero_path),
        "cell_rows_exported": len(rows),
        "zotero_items": len(csl_items),
        "integrity_rule": "Exports are audit packets and citation leads; human verification remains required.",
    }


def _extract_delimited_tables(name: str, text: str, *, max_rows: int, page: Any = "") -> List[Dict[str, Any]]:
    first_line = (text.splitlines() or [""])[0]
    delimiter = "\t" if "\t" in first_line else "," if "," in first_line else ""
    if not delimiter:
        return []
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        rows = [dict(row) for row in reader if any((value or "").strip() for value in row.values())]
    except Exception:
        return []
    headers = list(reader.fieldnames or [])
    if len(headers) >= 2 and rows:
        return [_table_payload(name, "stdlib_csv_tsv", headers, rows, max_rows, page=page)]
    return []


def _extract_markdown_tables(name: str, text: str, *, max_rows: int, page: Any = "") -> List[Dict[str, Any]]:
    lines = [line.strip() for line in text.splitlines() if "|" in line]
    tables: List[Dict[str, Any]] = []
    for idx in range(max(0, len(lines) - 1)):
        header = [cell.strip() for cell in lines[idx].strip("|").split("|")]
        separator = [cell.strip() for cell in lines[idx + 1].strip("|").split("|")]
        if len(header) < 2 or not all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in separator):
            continue
        rows: List[Dict[str, str]] = []
        for row_line in lines[idx + 2:]:
            cells = [cell.strip() for cell in row_line.strip("|").split("|")]
            if len(cells) != len(header):
                break
            rows.append(dict(zip(header, cells)))
        if rows:
            tables.append(_table_payload(name, "markdown_pipe_table", header, rows, max_rows, page=page, table_index=len(tables) + 1))
    return tables


def _extract_html_tables(name: str, text: str, *, max_rows: int, page: Any = "") -> List[Dict[str, Any]]:
    if "<table" not in text.lower():
        return []
    parser = _HTMLTableParser()
    try:
        parser.feed(text)
    except Exception:
        return []
    tables: List[Dict[str, Any]] = []
    for raw_table in parser.tables:
        if len(raw_table) < 2:
            continue
        headers = raw_table[0]
        if len(headers) < 2:
            continue
        rows = [dict(zip(headers, row)) for row in raw_table[1:] if len(row) == len(headers)]
        if rows:
            tables.append(_table_payload(name, "html_table", headers, rows, max_rows, page=page, table_index=len(tables) + 1))
    return tables


def _extract_fixed_width_tables(name: str, text: str, *, max_rows: int, page: Any = "") -> List[Dict[str, Any]]:
    lines = [line.rstrip() for line in text.splitlines()]
    candidates = [line for line in lines if re.search(r"\S+\s{2,}\S+\s{2,}\S+", line)]
    if len(candidates) < 2:
        return []
    header = re.split(r"\s{2,}", candidates[0].strip())
    if len(header) < 3:
        return []
    rows = []
    for line in candidates[1:]:
        cells = re.split(r"\s{2,}", line.strip())
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    if rows:
        return [_table_payload(name, "fixed_width_text_table", header, rows, max_rows, page=page)]
    return []


def vision_status_from_document_evidence(document_evidence: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    documents = list((document_evidence or {}).get("documents") or [])
    warnings: List[str] = []
    figure_signal = False
    for doc in documents:
        inspection = doc.get("document_inspection") or {}
        figure_signal = figure_signal or bool(inspection.get("figure_signal"))
        warnings.extend(str(item) for item in inspection.get("warnings") or [])
    provider = os.environ.get("SOPHIA_NATIVE_VISION_PROVIDER") or ""
    model = os.environ.get("SOPHIA_NATIVE_VISION_MODEL") or ""
    gemini_status: Dict[str, Any] = {}
    try:
        from backend.services.gemini_vision import gemini_vision_status
        gemini_status = gemini_vision_status()
        if not provider and gemini_status.get("configured"):
            provider = "gemini"
        if not model and gemini_status.get("model"):
            model = str(gemini_status.get("model") or "")
    except Exception:
        gemini_status = {}
    native_ready = os.environ.get("SOPHIA_ENABLE_NATIVE_VISION") == "1" and bool(provider and model)
    status = "native_vision_configured_not_invoked" if native_ready else "native_vision_not_enabled"
    if os.environ.get("SOPHIA_ENABLE_NATIVE_VISION") == "1" and not native_ready:
        status = "native_vision_enabled_missing_provider_or_model"
    if figure_signal and not native_ready:
        status = "text_or_ocr_only_for_visual_material"
    return {
        "method": "document_inspection_vision_readiness",
        "status": status,
        "native_vision_enabled": native_ready,
        "provider": provider,
        "model": model,
        "gemini": gemini_status,
        "figure_signal": figure_signal,
        "warnings": sorted(set(warnings)),
        "integrity_rule": "Do not interpret images, charts, or diagrams beyond extracted text/OCR unless a native vision model is explicitly active.",
    }


def build_evidence_engine_report(
    claim: str,
    *,
    sources: Optional[List[Dict[str, Any]]] = None,
    document_evidence: Optional[Dict[str, Any]] = None,
    page_number: Optional[int] = None,
) -> Dict[str, Any]:
    sources = list(sources or [])
    ranked = rank_evidence_spans(claim, sources, limit=8)
    best_span = ""
    if ranked["ranked_spans"]:
        best_span = str(ranked["ranked_spans"][0].get("matched_span") or "")
    nli = judge_claim_support(claim, best_span) if best_span else {
        "method": "deterministic_nli_fallback",
        "label": "not_enough_information",
        "confidence": 0.5,
        "similarity_score": 0.0,
        "shared_concepts": [],
        "rationale": "No visible source span was available.",
    }
    page_check: Optional[Dict[str, Any]] = None
    if page_number:
        try:
            from backend.services.document_evidence import compare_claim_to_document_page
            page_check = compare_claim_to_document_page(claim, document_evidence, page_number)
        except Exception as exc:  # pragma: no cover
            page_check = {"status": "page_check_error", "page_number": page_number, "error": str(exc)}
    return {
        "method": "sophia_advanced_evidence_engine_slice1",
        "claim": claim[:900],
        "embedding_ranking": ranked,
        "nli_support": nli,
        "structured_tables": extract_structured_tables(sources),
        "page_cell_citation_export": export_table_cell_citations(sources),
        "vision_status": vision_status_from_document_evidence(document_evidence),
        "page_check": page_check,
        "integrity_contract": [
            "rank visible spans before making support claims",
            "separate supports, partial support, contradiction, and not-enough-information",
            "report whether neural components were actually used",
            "do not invent page/table/vision evidence",
        ],
    }
