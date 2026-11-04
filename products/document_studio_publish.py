"""Format-only publication package for owner-approved manuscripts."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from adapters.format_core import build_paragraph_semantic_content, render_semantic_asset
from adapters.sophia.review_pipeline import extract_document_text


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _source_file(value: Any) -> Path:
    path = Path(str(value or "")).expanduser().resolve()
    if not path.is_file():
        raise ValueError("document_path must identify the approved customer manuscript")
    if path.suffix.casefold() not in {".txt", ".md", ".rst", ".csv", ".docx", ".pdf"}:
        raise ValueError("Document Studio Publish accepts text, Markdown, CSV, DOCX, or text-readable PDF")
    return path


def build_publication_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    if packet.get("content_owner_approved") is not True:
        raise ValueError("content_owner_approved=true is required; this route formats approved copy without editorial changes")
    if packet.get("external_release_authorized") is True:
        raise ValueError("Document Studio Publish prepares files for review; external publication is a separate owner action")
    source = _source_file(packet.get("document_path"))
    source_hash = _sha(source)
    if packet.get("source_sha256") and packet["source_sha256"] != source_hash:
        raise ValueError("customer manuscript source hash mismatch")
    source_text, parser = extract_document_text(source)
    lines = [line for line in source_text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("approved manuscript contains no extractable text")
    title = str(packet.get("title") or source.stem).strip()
    draft_markers = []
    marker_patterns = (
        re.compile(r"\bdraft\b", re.I),
        re.compile(r"intentionally rough source copy", re.I),
        re.compile(r"to be completed|insert (?:text|figure|citation)|update this field", re.I),
    )
    for line_number, line in enumerate(source_text.splitlines(), 1):
        if any(pattern.search(line) for pattern in marker_patterns):
            draft_markers.append({"line": line_number, "text": line.strip()})
    source_review = {
        "state": "OWNER_RECONCILIATION_REQUIRED" if draft_markers else "OWNER_REVIEW_REQUIRED",
        "draft_markers": draft_markers,
        "approval_claim_reconciled": not bool(draft_markers),
        "claim_boundary": "This marker check identifies explicit draft/template language only. It does not judge content accuracy or establish owner approval.",
    }
    authors = packet.get("authors") or []
    if isinstance(authors, str):
        authors = [row.strip() for row in authors.split(";") if row.strip()]
    if not isinstance(authors, list) or any(not str(row).strip() for row in authors):
        raise ValueError("authors must be a list of non-empty owner-supplied names")
    doi_state = str(packet.get("doi") or "PENDING — DOI not assigned").strip()
    if len(title) > 240 or len(doi_state) > 160 or len(authors) > 80:
        raise ValueError("publication metadata exceeds supported bounds")
    channels = packet.get("channels") or ["docx", "pdf", "html"]
    if not isinstance(channels, list) or not channels or set(channels) - {"docx", "pdf", "html"}:
        raise ValueError("channels may contain only docx, pdf, and html")
    channels = list(dict.fromkeys(channels))
    language = str(packet.get("language") or "English").strip()
    out = Path(output_dir).resolve()
    source_copy = out / "source" / f"SOURCE_MANUSCRIPT_UNCHANGED{source.suffix.lower()}"
    source_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, source_copy)
    body_rows = []
    semantic_source_lines = []
    for index, line in enumerate(lines, 1):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", line)
        text = heading.group(2).strip() if heading else line
        semantic_source_lines.append(text)
        body_rows.append({"paragraph_id": f"SRC-{index:04d}", "text": text})
    content = build_paragraph_semantic_content(
        object_id="PUBLICATION-" + source_hash[:16].upper(), version="1.0.0", title=title,
        source_language=language, source_rows=body_rows,
        context={"product": "document_studio_publish", "artifact_type": "publication_master", "audience": "publication review", "include_contents": False},
    )
    for index, block in enumerate(content["blocks"]):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", lines[index])
        if heading:
            block["type"] = "heading"
            block["level"] = len(heading.group(1))
    content["blocks"] = [
        {"block_id": "PUB-AUTHOR-LIST", "type": "paragraph", "text": "Authors: " + ("; ".join(str(row).strip() for row in authors) if authors else "Author list not supplied")},
        {"block_id": "PUB-DOI-STATE", "type": "paragraph", "text": "DOI: " + doi_state},
        *content["blocks"],
    ]
    format_root = out / "formatted"
    render_receipt = render_semantic_asset(
        content, format_root, style_profile=str(packet.get("style_profile") or "institutional_academic"),
        delivery_profile="editable_review", language=language, channels=channels,
        release_mode=False, source_root=source.parent,
    )
    output_rows = render_receipt.get("outputs") or []
    outputs = {str(row.get("channel")): str((format_root / str(row.get("path"))).resolve())
               for row in output_rows if isinstance(row, dict) and row.get("channel") and row.get("path")}
    required = set(channels)
    if not required.issubset(outputs):
        raise RuntimeError("Format Core did not produce every requested publication channel")
    preservation_checks: dict[str, bool] = {}
    for channel, path_value in outputs.items():
        path = Path(str(path_value))
        if channel == "html":
            parser_html = _VisibleText()
            parser_html.feed(path.read_text(encoding="utf-8"))
            rendered_text = " ".join(parser_html.parts)
        elif channel in {"docx", "pdf"}:
            rendered_text, _ = extract_document_text(path)
        else:
            continue
        rendered_norm = _normalized(rendered_text)
        preservation_checks[channel] = all(_normalized(line) in rendered_norm for line in semantic_source_lines)
    if set(preservation_checks) != required or not all(preservation_checks.values()):
        raise RuntimeError("At least one publication render failed source-text preservation checks")

    manifest = {
        "schema": "dio.document_studio.publication_package.v1",
        "status": "human_publication_review_required",
        "source": {"file_name": source.name, "sha256": source_hash, "bytes": source.stat().st_size, "parser": parser, "unchanged_copy": source_copy.relative_to(out).as_posix()},
        "metadata": {"title": title, "authors": [str(row).strip() for row in authors], "doi_state": doi_state, "language": language},
        "format_core": render_receipt,
        "source_text_preservation_checks": preservation_checks,
        "source_content_review": source_review,
        "rendering_policy": {"automatic_contents_page": "omitted_unless_owner_supplies_approved_contents"},
        "formatting_only": True, "editorial_or_content_changes": False,
        "external_publication_authorized": False, "human_approval_required": True,
    }
    manifest_path = out / "PUBLICATION_PACKAGE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    review = out / "HUMAN_PUBLICATION_REVIEW.md"
    review.write_text(
        "# Publication review gate\n\n"
        f"Title: {title}\n\nAuthors (owner supplied): {('; '.join(str(row) for row in authors)) or 'Not supplied'}\n\nDOI: {doi_state}\n\n"
        f"Source SHA-256: `{source_hash}`\n\n"
        "This package applies formatting only and preserves the source text verbatim. The manuscript contains explicit draft/template markers that conflict with the supplied approval statement; reconcile that status and complete editorial review before publication. Confirm author order, rights, metadata, figures, references and final pagination, and approve each channel before any external publication. No DOI was invented and no file was published.\n",
        encoding="utf-8",
    )
    preview = out / "PUBLICATION_REVIEW.html"
    links = []
    for channel, path_value in outputs.items():
        path = Path(str(path_value))
        try:
            href = path.resolve().relative_to(out.resolve()).as_posix()
        except ValueError:
            raise RuntimeError("publication output escaped the customer package")
        links.append(f"<li><a href='{html.escape(href, quote=True)}'>{html.escape(channel.upper())} review copy</a></li>")
    source_notice = (
        "<p class='hold'><strong>Source approval conflict:</strong> this manuscript contains explicit draft/template language, while the supplied request says content approval is complete. The wording is preserved exactly; reconcile approval and complete editorial review before any publication.</p>"
        if draft_markers else
        "<p class='hold'><strong>Content review:</strong> formatting preserves the supplied text; the content owner must confirm approval before publication.</p>"
    )
    preview.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)} · publication review</title><style>body{{font:16px/1.55 system-ui,sans-serif;max-width:880px;margin:36px auto;padding:0 20px;color:#20302f}}a{{color:#075d71}}.gate,.hold{{background:#fff7e8;border-left:4px solid #a66a27;padding:14px}}</style><main><p>DOCUMENT STUDIO PUBLISH · FORMAT ONLY</p><h1>{html.escape(title)}</h1><p>{html.escape('; '.join(str(row) for row in authors) or 'Author list not supplied')}</p><p>{html.escape(doi_state)}</p>{source_notice}<ul>{''.join(links)}</ul><p class='gate'>Review source fidelity, rights, author metadata and pagination. External publication is not authorized.</p><p><a href='{html.escape(manifest_path.name, quote=True)}'>Source and output manifest</a> · <a href='{html.escape(review.name, quote=True)}'>Human review checklist</a></p></main></html>\n",
        encoding="utf-8",
    )
    artifact_paths = [source_copy, manifest_path, review, preview, *(Path(str(value)) for value in outputs.values())]
    artifacts = [{"path": path.relative_to(out).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)} for path in artifact_paths]
    receipt = {
        "schema": "dio.document_studio.publish.customer_execution.v1", "status": "human_publication_review_required",
        "title": title, "source_sha256": source_hash, "formats": sorted(outputs),
        "source_text_preservation_checks": preservation_checks, "formatting_only": True,
        "external_publication_authorized": False, "human_approval_required": True,
        "provider_calls": 0, "artifacts": artifacts,
    }
    (out / "CUSTOMER_PACKAGE_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
