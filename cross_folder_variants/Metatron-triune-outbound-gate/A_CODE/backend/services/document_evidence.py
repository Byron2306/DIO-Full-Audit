#!/usr/bin/env python3
"""
Minimal document-evidence pipeline for protocol v1.1.

Stdlib-first on purpose:
- plain text / markdown / json / html extraction
- optional PDF extraction via `pdftotext` if available
- image/scan support through sidecar OCR text files

This does not pretend to be native vision. It prepares bounded evidence
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


MAX_EXTRACTED_CHARS = 6000
MAX_SPANS = 6
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


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
    return text[: max_chars - 16].rstrip() + "\n\n[truncated]"


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


def _build_spans(text: str) -> List[Dict[str, str]]:
    spans: List[Dict[str, str]] = []
    for index, chunk in enumerate(_chunk_text(text)[:MAX_SPANS], start=1):
        spans.append(
            {
                "span_id": f"S{index}",
                "quote": chunk,
            }
        )
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


def _extract_pdf_text(path: Path) -> tuple[str, List[str], str]:
    notes: List[str] = []
    if shutil.which("pdftotext"):
        proc = subprocess.run(
            ["pdftotext", "-layout", "-nopgbrk", str(path), "-"],
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
        return _extract_image_sidecar_text(path)
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
    return {
        "source_path": str(path),
        "source_name": path.name,
        "modality": modality,
        "task_label": task_label,
        "parser": parser,
        "extracted_text": extracted_text,
        "spans": _build_spans(extracted_text),
        "uncertainty_notes": uncertainty,
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

    for index, document in enumerate(documents, start=1):
        lines.append("")
        lines.append(f"[SOURCE {index}] {document.get('source_name')}")
        lines.append(f"modality={document.get('modality')} parser={document.get('parser')}")
        uncertainty = document.get("uncertainty_notes") or []
        if uncertainty:
            lines.append("uncertainty=" + ", ".join(str(item) for item in uncertainty))
        spans = document.get("spans") or []
        for span in spans:
            lines.append(f"{span.get('span_id')}: {span.get('quote')}")

    return "\n".join(lines)
