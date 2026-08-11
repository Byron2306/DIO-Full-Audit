from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def extract_document_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".rst", ".csv"}:
        return path.read_text(encoding="utf-8", errors="replace"), "plain_text"
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        paragraphs = []
        for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
            if text.strip():
                paragraphs.append(text.strip())
        return "\n\n".join(paragraphs), "docx_xml"
    if suffix == ".pdf":
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(path) as document:
                pages = [page.extract_text() or "" for page in document.pages]
            return "\n\n".join(f"[Page {index}]\n{text}" for index, text in enumerate(pages, 1)), "pdfplumber"
        except (ImportError, OSError, ValueError):
            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                text=True,
                capture_output=True,
                check=False,
                timeout=90,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout, "pdftotext"
            raise ValueError("PDF text extraction failed; provide a text-readable PDF or DOCX.")
    raise ValueError(f"Unsupported manuscript type: {suffix or '(none)'}")


_REFERENCE_HEADING_KEYS = {
    "references",
    "reference",
    "bibliography",
    "workscited",
    "literaturecited",
}


def _compact_pdf_heading(line: str) -> str:
    value = re.sub(r"^\s*#{1,6}\s*", "", line or "")
    return re.sub(r"[^A-Za-z]", "", value).lower()


def _is_reference_heading(line: str) -> bool:
    return _compact_pdf_heading(line) in _REFERENCE_HEADING_KEYS


def _is_post_reference_heading(line: str) -> bool:
    raw = re.sub(r"^\s*#{1,6}\s*", "", line or "").strip()
    if not raw or len(raw) > 100:
        return False

    compact = _compact_pdf_heading(raw)
    if compact in {
        "appendix",
        "appendices",
        "supplementarymaterial",
        "supplementarymaterials",
    }:
        return True
    if compact.startswith("appendix") and len(compact) <= 60:
        return True

    letters = "".join(char for char in raw if char.isalpha())
    return bool(
        letters
        and letters.upper() == letters
        and re.match(r"^[A-Z]\s*(?:[.:])?\s+[A-Z]", raw)
    )


def _is_pdf_page_furniture(line: str) -> bool:
    value = (line or "").strip()
    if not value:
        return False
    if value == "```":
        return True
    if re.fullmatch(r"\[?Page\s+\d{1,4}\]?", value, flags=re.I):
        return True
    if re.fullmatch(r"\d{1,4}", value):
        return True
    return value.lower() in {"preprint", "draft", "manuscript"}


def _looks_like_pdf_table_line(line: str) -> bool:
    value = (line or "").rstrip()
    if len(value.split()) < 3:
        return False
    return len(re.findall(r"\S\s{2,}\S", value)) >= 2


def _looks_like_pdf_section_heading(line: str) -> bool:
    raw = re.sub(r"^\s*#{1,6}\s*", "", line or "").strip()
    if not raw or len(raw) > 140:
        return False

    compact = _compact_pdf_heading(raw)
    if compact in {
        "abstract",
        "references",
        "acknowledgements",
        "acknowledgments",
        "appendix",
        "appendices",
        "supplementarymaterial",
        "supplementarymaterials",
    }:
        return True
    if _is_post_reference_heading(raw):
        return True

    # Numbered pdftotext headings:
    # "3.2 L INEAR R EPRESENTATIONS", "7 D ISCUSSION"
    numbered = re.match(r"^\d+(?:\.\d+)*\s+(.+?)\s*$", raw)
    if numbered:
        heading_text = numbered.group(1)
        letters = "".join(char for char in heading_text if char.isalpha())
        if letters and letters.upper() == letters:
            return True

    # Unnumbered all-caps / small-caps headings and document titles.
    letters = "".join(char for char in raw if char.isalpha())
    if (
        letters
        and letters.upper() == letters
        and len(raw.split()) <= 16
        and not re.search(r"[.!?]$", raw)
    ):
        return True

    return False


def _clean_pdf_layout_text(text: str, *, drop_table_lines: bool = False) -> str:
    lines = (text or "").splitlines()

    # For claim/anchor construction only, discard title/author/institution
    # front matter when a recognizable ABSTRACT heading is present near
    # the beginning. Abstract content itself is preserved.
    if drop_table_lines:
        abstract_index = next(
            (
                index
                for index, line in enumerate(lines[:120])
                if _compact_pdf_heading(line) == "abstract"
            ),
            None,
        )
        if abstract_index is not None:
            lines = lines[abstract_index + 1 :]

    kept: list[str] = []
    for raw_line in lines:
        if _is_pdf_page_furniture(raw_line):
            continue

        if drop_table_lines:
            if _looks_like_pdf_section_heading(raw_line):
                continue
            if re.match(r"^\s*(?:Figure|Table)\s+\d+\s*:", raw_line, flags=re.I):
                continue
            if _looks_like_pdf_table_line(raw_line):
                continue

        kept.append(raw_line.rstrip())

    return "\n".join(kept)

def _reference_year_match(entry: str) -> Any:
    value = entry or ""

    # Parenthesized years are highly likely to be the publication year.
    parenthesized = list(
        re.finditer(r"\(((?:18|19|20)\d{2}[a-z]?)\)", value, flags=re.I)
    )
    if parenthesized:
        return parenthesized[0]

    candidates = list(
        re.finditer(
            r"(?<![\d:])((?:18|19|20)\d{2}[a-z]?)(?!\d|\.\d)",
            value,
            flags=re.I,
        )
    )
    filtered = []
    for match in candidates:
        start, end = match.span(1)

        # Ignore years embedded in URL/path tokens.
        left_space = value.rfind(" ", 0, start)
        right_space = value.find(" ", end)
        if right_space < 0:
            right_space = len(value)
        token = value[left_space + 1 : right_space].lower()
        if "://" in token or token.startswith(("www.", "arxiv:")):
            continue

        # Ignore metadata/access years that are not publication years.
        prefix = value[max(0, start - 32) : start]
        if re.search(
            r"(?:version|accessed|retrieved|updated|visited|downloaded|copyright)"
            r"\s*:?\s*$",
            prefix,
            flags=re.I,
        ):
            continue

        filtered.append(match)

    # Publication year is normally the last remaining non-URL/non-access year.
    return filtered[-1] if filtered else None


def _reference_year(entry: str) -> str:
    match = _reference_year_match(entry)
    return str(match.group(1)) if match else ""

def _reference_complete_enough_to_split(entry: str) -> bool:
    return bool(
        _reference_year(entry)
        or re.search(r"\bn\.?\s*d\.?\b", entry or "", flags=re.I)
    )


def _looks_like_reference_start(line: str) -> bool:
    value = re.sub(r"^(?:\[\d+\]|\d+[.)])\s*", "", (line or "").strip())
    if not value or _is_pdf_page_furniture(value) or _is_post_reference_heading(value):
        return False
    if not value[0].isupper():
        return False

    # Surname-first references such as "Smith, J."
    if re.match(
        r"^[A-Z][^\s,.;:()]+,\s*(?:[A-Z](?:\.|\s)|[A-Z][^\s,.;:()]+)",
        value,
    ):
        return True

    # Multi-author first lines such as "Mostafa Abdou, Artur Kulmizev, ..."
    if re.match(
        r"^[A-Z][^\s,.;:()]+(?:\s+[A-Z][^\s,.;:()]*){1,5}"
        r"(?:,|\s+and\s+|\s+&\s+)",
        value,
    ):
        return True

    # Single personal author first lines often have no publication year
    # on that same physical PDF line, e.g.:
    #   "Yonatan Belinkov. Probing classifiers: ..."
    if re.match(
        r"^[A-Z][^\s,.;:()]+(?:\s+[A-Z][^\s,.;:()]*){1,4}\.\s+\S",
        value,
    ):
        return True

    # Corporate/single-author rows that do carry their year on this line.
    return bool(
        _reference_year(value)
        and re.match(r"^[A-Z]", value)
        and re.search(r"\.\s+", value[:180])
    )

def _first_author_surname(entry: str) -> str:
    value = re.sub(r"^(?:\[\d+\]|\d+[.)])\s*", "", (entry or "").strip())
    if not value:
        return ""

    boundaries: list[int] = []
    for pattern in (r",", r"\.", r"\s+and\s+", r"\s+&\s+"):
        match = re.search(pattern, value)
        if match:
            boundaries.append(match.start())
    first_author = value[: min(boundaries)] if boundaries else value[:80]

    tokens = [
        re.sub(r"^[^\w]+|[^\w'’\-]+$", "", token, flags=re.UNICODE)
        for token in first_author.split()
    ]
    tokens = [token for token in tokens if any(char.isalpha() for char in token)]
    return tokens[-1] if tokens else ""


def split_reference_section(text: str) -> tuple[str, str]:
    lines = (text or "").splitlines()
    reference_index = next(
        (index for index, line in enumerate(lines) if _is_reference_heading(line)),
        None,
    )
    if reference_index is None:
        return text, ""

    end_index = len(lines)
    for index in range(reference_index + 1, len(lines)):
        if _is_post_reference_heading(lines[index]):
            end_index = index
            break

    body_lines = list(lines[:reference_index])
    if end_index < len(lines):
        body_lines.extend(["", *lines[end_index:]])

    body = "\n".join(body_lines).strip()
    references = "\n".join(lines[reference_index + 1 : end_index]).strip()
    return body, references

def _reference_continuation_expected(entry: str) -> bool:
    value = re.sub(r"\s+", " ", entry or "").strip()
    if not value:
        return False

    if value.endswith("-"):
        return True

    # Wrapped conference/title lines should not start a new reference.
    if re.search(
        r"\b(?:and|or|of|on|for|in|the|a|an|with|without|from|to|at|by)\s*$",
        value,
        flags=re.I,
    ):
        return True

    if value.count("(") > value.count(")"):
        return True
    if value.count("[") > value.count("]"):
        return True

    return False


def parse_reference_entries(reference_text: str) -> list[str]:
    if not (reference_text or "").strip():
        return []

    entries: list[str] = []
    current = ""

    for raw_line in reference_text.splitlines():
        if _is_post_reference_heading(raw_line):
            break
        if _is_pdf_page_furniture(raw_line):
            continue

        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        if (
            current
            and _reference_complete_enough_to_split(current)
            and not _reference_continuation_expected(current)
            and _looks_like_reference_start(line)
        ):
            entries.append(current.strip())
            current = line
        else:
            current = f"{current} {line}".strip()

    if current:
        entries.append(current.strip())

    return [
        entry
        for entry in entries
        if len(entry.split()) >= 5
        and not _is_pdf_page_furniture(entry)
        and not _is_post_reference_heading(entry)
    ]

def _ascii_fold(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    )


def citation_key(author: str, year: str) -> str:
    author_ascii = _ascii_fold(author)
    return f"{re.sub(r'[^a-z0-9]', '', author_ascii.lower())}:{year.lower()}"


def _normalize_citation_text(text: str) -> str:
    value = _ascii_fold(text or "")

    # Repair alphabetic words split by PDF wrapping: Cunning-\nham -> Cunningham.
    value = re.sub(r"(?<=[A-Za-z])-+\s*\n\s*(?=[a-z])", "", value)
    value = re.sub(r"[ \t]*\n[ \t]*", " ", value)
    return re.sub(r"[ \t]+", " ", value)


def _citation_author_from_prefix(prefix: str) -> str:
    value = re.sub(r"\s+", " ", prefix or "").strip(" ,;:.()[]")
    if not value:
        return ""

    et_al = re.match(r"(.+?)\s+et\s+al\.?$", value, flags=re.I)
    if et_al:
        value = et_al.group(1).strip()

    if re.search(r"\s+(?:&|and)\s+", value, flags=re.I):
        value = re.split(r"\s+(?:&|and)\s+", value, maxsplit=1, flags=re.I)[0]

    tokens = re.findall(r"[A-Za-z][A-Za-z'’-]*", value)
    if not tokens:
        return ""

    # Corporate authors such as "NYC OpenData" key to OpenData, matching
    # _first_author_surname(reference_entry).
    return tokens[-1]


def extract_in_text_citations(body_text: str) -> list[dict[str, str]]:
    text = _normalize_citation_text(body_text)
    found: dict[str, dict[str, str]] = {}

    def add(author: str, year: str, form: str) -> None:
        author = _citation_author_from_prefix(author)
        if not author or not re.fullmatch(r"(?:18|19|20)\d{2}[a-z]?", year, flags=re.I):
            return
        key = citation_key(author, year)
        if not key or key.startswith(":"):
            return
        found[key] = {
            "key": key,
            "author": author,
            "year": year,
            "form": form,
        }

    # Parentheticals including suffix shorthand: (Meng et al., 2022a;b; Geva..., 2023)
    parenthetical = re.compile(r"\(([^()]*\b(?:18|19|20)\d{2}[a-z]?[^()]*)\)")
    for group in parenthetical.findall(text):
        last_author = ""
        last_base_year = ""

        for raw_segment in group.split(";"):
            segment = raw_segment.strip()
            if not segment:
                continue

            if (
                re.fullmatch(r"[a-z]", segment, flags=re.I)
                and last_author
                and last_base_year
            ):
                add(last_author, last_base_year + segment.lower(), "parenthetical")
                continue

            year_matches = list(
                re.finditer(r"\b((?:18|19|20)\d{2}[a-z]?)\b", segment, flags=re.I)
            )
            if not year_matches:
                continue

            year_match = year_matches[0]
            year = year_match.group(1)
            prefix = segment[: year_match.start()].strip(" ,")

            # Do not hallucinate citations from numeric thresholds such as
            # "(population density greater than 50 and population greater than 2000)".
            # The old extractor interpreted this as author="than", year="2000".
            if re.search(
                r"\b(?:greater|less|fewer|more)\s+than\s*$",
                prefix,
                flags=re.I,
            ):
                continue
            if re.search(
                r"\b(?:at\s+least|at\s+most|under|over|below|above)\s*$",
                prefix,
                flags=re.I,
            ):
                continue

            # A parenthetical citation needs at least one author-like capitalized
            # token before the year. This keeps normal personal/corporate forms
            # such as "Buzsaki & Llinas", "Meng et al.", and "NYC OpenData",
            # while excluding ordinary prose ending in a year-shaped number.
            if not re.search(r"\b[A-Z][A-Za-z'’-]*\b", prefix):
                continue

            author = _citation_author_from_prefix(prefix)
            if not author:
                continue

            add(author, year, "parenthetical")
            last_author = author
            last_base_year = year[:4]

    # Narrative forms such as Lehmann et al. (2015).
    narrative = re.compile(
        r"\b([A-Z][A-Za-z'’-]*(?:\s+[A-Z][A-Za-z'’-]*)*)"
        r"(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’-]*|\s+et\s+al\.)?"
        r"\s*\(((?:18|19|20)\d{2}[a-z]?)\)"
    )
    for author_block, year in narrative.findall(text):
        add(author_block, year, "narrative")

    return sorted(found.values(), key=lambda row: row["key"])

def reference_key(entry: str) -> str:
    author = _first_author_surname(entry)
    year = _reference_year(entry)
    return citation_key(author, year) if author and year else ""

def audit_references(body_text: str, reference_text: str, citation_check: Any) -> dict[str, Any]:
    in_text = extract_in_text_citations(body_text)
    entries = parse_reference_entries(reference_text)
    reference_rows = []
    seen_normalized: set[str] = set()
    seen_dois: set[str] = set()
    duplicate_entries: list[str] = []
    duplicate_dois: list[str] = []
    for index, entry in enumerate(entries, 1):
        normalized = re.sub(r"\W+", "", entry.lower())
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", entry, flags=re.I)
        doi = doi_match.group(0).rstrip(".,;)").lower() if doi_match else ""
        if normalized in seen_normalized:
            duplicate_entries.append(entry)
        seen_normalized.add(normalized)
        if doi and doi in seen_dois:
            duplicate_dois.append(doi)
        if doi:
            seen_dois.add(doi)
        style = citation_check(entry).to_dict()
        issues = []
        if not reference_key(entry):
            issues.append("author_or_year_not_detected")
        if len(entry.split()) < 6:
            issues.append("reference_appears_incomplete")
        if doi and "https://doi.org/" not in entry.lower():
            issues.append("doi_not_in_https_form")
        reference_rows.append({
            "index": index,
            "key": reference_key(entry),
            "entry": entry,
            "doi": doi,
            "style_check": style,
            "issues": issues,
        })
    in_text_keys = {row["key"] for row in in_text}
    reference_keys = {row["key"] for row in reference_rows if row["key"]}
    missing_from_references = [row for row in in_text if row["key"] not in reference_keys]
    uncited_references = [row for row in reference_rows if row["key"] and row["key"] not in in_text_keys]
    # Keep reconciliation/integrity findings distinct from style diagnostics.
    integrity_issue_count = (
        len(missing_from_references)
        + len(uncited_references)
        + len(duplicate_entries)
        + len(duplicate_dois)
        + sum(len(row["issues"]) for row in reference_rows)
    )
    style_diagnostic_count = sum(
        int(row["style_check"]["fail_count"]) for row in reference_rows
    )
    diagnostic_total_issue_count = integrity_issue_count + style_diagnostic_count
    return {
        "schema": "dio.sophia_reference_audit.v1",
        "citation_style": "APA 7 diagnostic",
        "in_text_citations": in_text,
        "reference_entries": reference_rows,
        "missing_from_reference_list": missing_from_references,
        "reference_list_entries_not_cited": uncited_references,
        "duplicate_entries": duplicate_entries,
        "duplicate_dois": duplicate_dois,
        "actionable_issue_count": diagnostic_total_issue_count,
        "integrity_issue_count": integrity_issue_count,
        "style_diagnostic_count": style_diagnostic_count,
        "diagnostic_total_issue_count": diagnostic_total_issue_count,
        "reference_reconciliation_complete": integrity_issue_count == 0,
        "status": "needs_revision" if diagnostic_total_issue_count else "clean_first_pass",
        "limits": [
            "This is a deterministic technical audit, not a complete style-editor judgment.",
            "DOI and bibliographic metadata remain verification leads until checked against the publisher or scholarly index.",
        ],
    }


def select_claims(body_text: str, classify_claim_type: Any, limit: int = 12) -> list[dict[str, Any]]:
    # Strip transport/publication furniture before sentence selection while
    # preserving surrounding scholarly prose where possible.
    cleaned = re.sub(r"(?m)^\s*#{1,6}\s+.*$", "", body_text)
    cleaned = re.sub(r"(?im)^\s*arxiv\s*:\s*\S+.*$", " ", cleaned)
    cleaned = re.sub(r"(?im)^\s*submitted\s+to\b.*$", " ", cleaned)
    cleaned = re.sub(r"(?im)^\s*anonymous\b.*$", " ", cleaned)
    cleaned = re.sub(r"https?://[^\s)\]}>,;]+", " ", cleaned)
    cleaned = re.sub(r"\bwww\.[^\s)\]}>,;]+", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bdoi\s*:\s*\S+", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\barxiv\s*:\s*\S+", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    sentences = [
        re.sub(r"\s+", " ", sentence).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if 8 <= len(re.sub(r"\s+", " ", sentence).split()) <= 90
    ]

    rows = []
    for candidate in sentences:
        sentence = candidate.strip()

        # Bare table captions are layout furniture, not manuscript claims.
        if re.match(r"(?i)^table\s+\d+\s*:", sentence):
            continue

        # pdftotext can glue a following table caption onto a valid sentence.
        # Preserve the scholarly sentence and drop only the caption tail.
        sentence = re.sub(r"(?i)\s+table\s+\d+\s*:.*$", "", sentence).strip()
        if len(sentence.split()) < 8:
            continue

        # Reject residual transport/publication markers.
        if re.search(
            r"https?://|\bwww\.|\barxiv\s*:|\bdoi\s*:",
            sentence,
            flags=re.I,
        ):
            continue

        # Reject common pdftotext row/section splices.
        spaced_section = bool(
            re.search(r"\b\d+(?:\.\d+)+\s+(?:[A-Z]\s+){2,}[A-Z]", sentence)
        )
        quoted_items = len(re.findall(r'[“"][^”"]{2,}[”"]', sentence))
        large_numbers = len(re.findall(r"\b\d{4,}\b", sentence))
        row_like_entity_dump = quoted_items >= 3 and large_numbers >= 3
        if spaced_section or row_like_entity_dump:
            continue

        classification_text = re.sub(
            r"\([^)]*\b(?:19|20)\d{2}[a-z]?[^)]*\)",
            "",
            sentence,
        )
        classification_text = re.sub(
            r"\b(?:19|20)\d{2}[a-z]?\b",
            "",
            classification_text,
        )
        classification = classify_claim_type(classification_text)
        if classification.get("evidence_risk") in {"medium", "high"}:
            rows.append({"claim": sentence, **classification})

    priority = {"high": 0, "medium": 1, "low": 2}
    rows.sort(
        key=lambda row: (
            priority.get(str(row.get("evidence_risk")), 9),
            -len(row["claim"]),
        )
    )
    return rows[:limit]

def post_json(url: str, payload: dict[str, Any], timeout: float = 45.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _review_paragraphs(text: str, limit: int = 120) -> list[dict[str, str]]:
    body_text, _ = split_reference_section(text)
    body_text = _clean_pdf_layout_text(body_text, drop_table_lines=True)
    paragraphs = []
    for item in re.split(r"\n\s*\n", body_text):
        cleaned = re.sub(r"\s+", " ", item).strip()
        if not cleaned:
            continue
        if _is_reference_heading(cleaned) or _is_post_reference_heading(cleaned):
            continue
        if len(cleaned.split()) < 5:
            continue
        paragraphs.append(cleaned)

    return [
        {"span_id": f"P{index}", "label": f"P{index}", "quote": item[:1800]}
        for index, item in enumerate(paragraphs[:limit], 1)
    ]

def _allowed_citation_keys(reference_audit: dict[str, Any], sources: list[dict[str, Any]]) -> set[str]:
    keys = {
        str(row.get("key") or "")
        for row in (
            list(reference_audit.get("in_text_citations") or [])
            + list(reference_audit.get("reference_entries") or [])
        )
        if row.get("key")
    }

    for row in reference_audit.get("reference_entries") or []:
        entry = str(row.get("entry") or "")
        year_match = _reference_year_match(entry)
        if not year_match:
            continue
        year = str(year_match.group(1))
        author_block = entry[: year_match.start()]

        first_author = _first_author_surname(entry)
        if first_author:
            keys.add(citation_key(first_author, year))

        for chunk in re.split(r",|\s+and\s+|\s+&\s+", author_block):
            surname = _first_author_surname(chunk.strip())
            if surname:
                keys.add(citation_key(surname, year))

    for source in sources:
        authors = source.get("authors") or []
        year = str(source.get("year") or "")
        if re.fullmatch(r"(?:19|20)\d{2}[a-z]?", year):
            for author in authors:
                surname = re.split(r"[,\s]", str(author).strip())[0]
                if surname:
                    keys.add(citation_key(surname, year))
    return keys

def validate_gemini_commentary(
    commentary: str,
    result: dict[str, Any],
    valid_anchors: set[str],
    allowed_citation_keys: set[str],
    allowed_dois: set[str],
    semantic_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_ok = str(result.get("reasoned_provider") or "").lower() == "gemini"
    provider_status_ok = result.get("reasoned_provider_status") == "ok"
    lane_ok = result.get("source") == "reasoned_integrity_lane"
    mandos_ok = bool((result.get("mandos_judgment") or {}).get("passed"))
    articles_ok = bool(((result.get("article_conformity") or {}).get("summary") or {}).get("all_passed"))
    semantic_context = semantic_context or {}
    commentary_l = (commentary or "").lower()

    def _has_unnegated_phrase(phrase: str) -> bool:
        start = commentary_l.find(phrase)
        while start >= 0:
            before = commentary_l[max(0, start - 72):start]
            if not re.search(r"\b(?:no|not|zero|without|rather than)\b[^.!?\n]{0,60}$", before):
                return True
            start = commentary_l.find(phrase, start + 1)
        return False

    integrity_issue_count = int(semantic_context.get("reference_integrity_issue_count") or 0)
    style_diagnostic_count = int(semantic_context.get("style_diagnostic_count") or 0)
    style_only_reference_findings = integrity_issue_count == 0 and style_diagnostic_count > 0

    false_reference_markers = (
        "missing reference",
        "uncited reference",
        "citation-reference mismatch",
        "reference reconciliation problem",
        "reference integrity vulnerab",
        "alignment between in-text citations and the reference list",
        "actionable reference issue",
    )
    reference_semantics_ok = (
        not style_only_reference_findings
        or not any(_has_unnegated_phrase(marker) for marker in false_reference_markers)
    )

    external_retrieval_enabled = bool(semantic_context.get("external_retrieval_enabled", False))
    false_candidate_support_markers = (
        "missing candidate support",
        "no candidate support",
        "lack candidate support",
        "lacks candidate support",
        "absence of candidate support",
        "candidate support is missing",
        "missing source support",
    )
    candidate_support_semantics_ok = (
        external_retrieval_enabled
        or not any(_has_unnegated_phrase(marker) for marker in false_candidate_support_markers)
    )

    manuscript_truncated = bool(semantic_context.get("manuscript_truncated", False))
    false_manuscript_access_markers = (
        "pending full manuscript",
        "pending full manuscript text access",
        "provided source text is incomplete",
        "source text is incomplete",
        "source text is partial",
        "truncated source text",
        "manuscript is truncated",
        "full manuscript is unavailable",
    )
    manuscript_access_semantics_ok = (
        manuscript_truncated
        or not any(_has_unnegated_phrase(marker) for marker in false_manuscript_access_markers)
    )

    mentioned_anchors = set(re.findall(r"\b([PC]\d+)\b", commentary))
    invalid_anchors = sorted(mentioned_anchors - valid_anchors)
    valid_mentions = sorted(mentioned_anchors & valid_anchors)
    mentioned_dois = {
        value.rstrip(".,;)").lower()
        for value in re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", commentary, flags=re.I)
    }
    unknown_dois = sorted(mentioned_dois - allowed_dois)

    mentioned_keys: set[str] = set()
    for author, year in re.findall(
        r"\b([A-Z][A-Za-z'\u2019-]+)(?:\s+et al\.)?\s*(?:\(|,\s*)((?:19|20)\d{2}[a-z]?)\)?",
        commentary,
    ):
        mentioned_keys.add(citation_key(author, year))
    unknown_citations = sorted(mentioned_keys - allowed_citation_keys)

    checks = {
        "provider_is_gemini": provider_ok,
        "provider_completed": provider_status_ok,
        "reasoned_lane_used": lane_ok,
        "mandos_passed": mandos_ok,
        "genesis_articles_passed": articles_ok,
        "document_anchor_present": bool(valid_mentions),
        "no_unknown_anchors": not invalid_anchors,
        "no_unknown_citations": not unknown_citations,
        "no_unknown_dois": not unknown_dois,
        "reference_audit_semantics_preserved": reference_semantics_ok,
        "candidate_support_semantics_preserved": candidate_support_semantics_ok,
        "manuscript_access_semantics_preserved": manuscript_access_semantics_ok,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "valid_anchors_mentioned": valid_mentions,
        "invalid_anchors": invalid_anchors,
        "unknown_citations": unknown_citations,
        "unknown_dois": unknown_dois,
        "semantic_context": semantic_context,
    }


def reviewer_commentary(
    base_url: str,
    request: dict[str, Any],
    title: str,
    document_path: Path,
    text: str,
    parser: str,
    reference_audit: dict[str, Any],
    claim_maps: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    if not bool(request.get("gemini_review_approved", False)):
        return {
            "status": "approval_required",
            "source": "not_sent",
            "encounter_id": None,
            "provider": None,
            "model": None,
            "remote_processing": False,
            "commentary": (
                "Gemini reviewer processing was not authorized. Set gemini_review_approved to true "
                "only after the manuscript owner approves remote processing."
            ),
        }
    try:
        health = fetch_json(f"{base_url.rstrip('/')}/api/health")
        review_body_text, _ = split_reference_section(text)
        spans = _review_paragraphs(review_body_text)
        claim_dossier = []
        for index, item in enumerate(claim_maps, 1):
            mapping = item.get("source_map") or {}
            claim = item.get("claim_record") or {}
            support_rows = [
                {
                    "title": row.get("source_name"),
                    "support_label": row.get("support_label"),
                    "entailment_status": row.get("entailment_status"),
                }
                for row in (mapping.get("results") or [])[:3]
            ]
            external_retrieval_enabled = bool(request.get("external_retrieval", False))
            claim_dossier.append({
                "claim_id": f"C{index}",
                "claim": claim.get("claim"),
                "claim_type": claim.get("claim_type"),
                "evidence_risk": claim.get("evidence_risk"),
                "candidate_support": support_rows,
                "candidate_support_scope": "external_candidate_sources_only",
                "candidate_support_status": (
                    "external_retrieval_disabled"
                    if not external_retrieval_enabled
                    else ("mapped" if support_rows else "no_external_candidate_mapping_found")
                ),
                "candidate_support_interpretation": (
                    "An empty candidate_support list is not evidence that the manuscript claim lacks "
                    "support. Manuscript support must be judged from the attached document evidence."
                ),
            })
        dossier = {
            "title": title,
            "research_question": str(request.get("research_question") or ""),
            "citation_style": str(request.get("citation_style") or "APA 7"),
            "reference_audit": {
                "status": reference_audit.get("status"),
                "missing_from_reference_list": reference_audit.get("missing_from_reference_list") or [],
                "listed_but_not_cited": [
                    row.get("entry") for row in (reference_audit.get("reference_list_entries_not_cited") or [])
                ],
                "duplicate_entries": reference_audit.get("duplicate_entries") or [],
                "duplicate_dois": reference_audit.get("duplicate_dois") or [],
                "integrity_issue_count": int(reference_audit.get("integrity_issue_count") or 0),
                "style_diagnostic_count": int(reference_audit.get("style_diagnostic_count") or 0),
                "diagnostic_total_issue_count": int(
                    reference_audit.get("diagnostic_total_issue_count")
                    or reference_audit.get("actionable_issue_count")
                    or 0
                ),
                "reference_reconciliation_complete": bool(
                    reference_audit.get("reference_reconciliation_complete", False)
                ),
                "interpretation": (
                    "Style/formatting diagnostics are not missing-reference, uncited-reference, "
                    "duplicate-reference, or citation-reference reconciliation failures."
                ),
            },
            "manuscript_transmission": {
                "characters_available": min(len(text), 180_000),
                "truncated": len(text) > 180_000,
                "full_extracted_manuscript_attached": len(text) <= 180_000,
            },
            "claim_ledger": claim_dossier,
        }
        prompt = "\n".join([
            "Sophia DIO product review. Evaluate only the attached manuscript and the local audit dossier below.",
            "Give diagnostic reviewer commentary; do not rewrite manuscript prose or produce submission-ready replacement text.",
            "Use these exact headings: Overall assessment; Major revisions; Minor revisions; Evidence limits; Author-owned next steps.",
            "Anchor every major revision to one or more supplied paragraph IDs such as [P3] or claim IDs such as [C2].",
            "Apply a closed-world evidence rule: use only authors, publications, citation labels, DOIs, URLs, data, methods, and findings already visible in the dossier/manuscript.",
            "Do not recommend named literature beyond that closed evidence set.",
            "REFERENCE-AUDIT SEMANTICS: Treat integrity/reconciliation findings separately from APA/style diagnostics. Style or formatting diagnostics are not evidence of missing references, uncited references, duplicate references, or citation-reference mismatch.",
            "CANDIDATE-SUPPORT SEMANTICS: candidate_support contains only external candidate-source mapping. When external_retrieval is disabled, an empty candidate_support list does NOT mean the manuscript claim lacks support; judge manuscript support from the attached manuscript and document anchors.",
            "MANUSCRIPT-ACCESS SEMANTICS: manuscript_transmission.truncated=false means the full extracted manuscript text was supplied to this review. Do not claim that full manuscript access is pending or that the supplied manuscript text is truncated in that case.",
            "Distinguish what the manuscript states from your inference and from what remains unknown.",
            "Prioritize argument clarity, method adequacy, evidence/claim fit, analytical coherence, limitations, and reference integrity.",
            "End with a short, ordered set of revisions that leaves all final wording and judgment with the author.",
            "LOCAL AUDIT DOSSIER:",
            json.dumps(dossier, ensure_ascii=True),
        ])
        model = str(request.get("gemini_model") or "gemini-flash-lite-latest").strip()
        if not model.startswith("gemini-"):
            raise ValueError("gemini_model must name a Gemini model")
        payload = {
                "text": prompt,
                "session_token": health.get("session_token") or "",
                "dio_product_review_lane": True,
                "reasoned_integrity_lane": True,
                "reasoned_provider": "gemini",
                "reasoned_model": model,
                "reasoned_max_predict": 1400,
                "document_evidence_task": "dio_sophia_academic_review",
                "document_uploads": [{
                    "source_name": title,
                    "source_path": document_path.name,
                    "mime_type": mimetypes.guess_type(document_path.name)[0] or "application/octet-stream",
                    "modality": "academic_manuscript",
                    "parser": parser,
                    "extracted_text": text[:180_000],
                    "spans": spans,
                    "uncertainty_notes": ["Remote Gemini review explicitly approved by manuscript owner."],
                }],
                "client_context": {
                    "ui_surface": "dio_sophia_review",
                    "writing_action": "review",
                    "response_mode": "detailed",
                },
                "disable_continuity_memory": True,
                "disable_world_events": True,
                "suppress_academic_retrieval_fastpaths": True,
            }
        result = post_json(f"{base_url.rstrip('/')}/api/speak", payload, timeout=180.0)
        attempt_encounters = [result.get("encounter_id")]
        candidate = str(result.get("response") or "").strip()
        valid_anchors = {row["span_id"] for row in spans} | {
            f"C{index}" for index in range(1, len(claim_maps) + 1)
        }
        allowed_dois = {
            str(row.get("doi") or "").lower()
            for row in (reference_audit.get("reference_entries") or [])
            if row.get("doi")
        }
        for source in sources:
            doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", str(source.get("url") or ""), flags=re.I)
            if doi_match:
                allowed_dois.add(doi_match.group(0).rstrip(".,;)").lower())
        semantic_context = {
            "reference_integrity_issue_count": int(reference_audit.get("integrity_issue_count") or 0),
            "style_diagnostic_count": int(reference_audit.get("style_diagnostic_count") or 0),
            "external_retrieval_enabled": bool(request.get("external_retrieval", False)),
            "manuscript_truncated": len(text) > 180_000,
        }
        validation = validate_gemini_commentary(
            candidate,
            result,
            valid_anchors,
            _allowed_citation_keys(reference_audit, sources),
            allowed_dois,
            semantic_context=semantic_context,
        )
        failed_checks = sorted(key for key, passed in validation["checks"].items() if not passed)
        if "document_anchor_present" in failed_checks:
            payload["text"] = (
                prompt
                + "\n\nREQUIRED CORRECTION: Every bullet under Major revisions must contain at least one "
                + "verbatim bracketed anchor from this allowed set: "
                + ", ".join(f"[{anchor}]" for anchor in sorted(valid_anchors))
                + ". Return the complete report with those anchors included."
            )
            result = post_json(f"{base_url.rstrip('/')}/api/speak", payload, timeout=180.0)
            attempt_encounters.append(result.get("encounter_id"))
            candidate = str(result.get("response") or "").strip()
            validation = validate_gemini_commentary(
                candidate,
                result,
                valid_anchors,
                _allowed_citation_keys(reference_audit, sources),
                allowed_dois,
                semantic_context=semantic_context,
            )
        if not validation["passed"]:
            return {
                "status": "rejected",
                "source": result.get("source") or "unknown",
                "encounter_id": result.get("encounter_id"),
                "provider": result.get("reasoned_provider"),
                "provider_status": result.get("reasoned_provider_status"),
                "model": result.get("model"),
                "remote_processing": True,
                "characters_transmitted": min(len(text), 180_000),
                "candidate_sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
                "attempt_count": len(attempt_encounters),
                "attempt_encounters": attempt_encounters,
                "validation": validation,
                "commentary": "Gemini returned commentary, but the grounded release checks rejected it. Human review remains required.",
            }
        return {
            "status": "completed",
            "source": result.get("source") or "sophia",
            "encounter_id": result.get("encounter_id"),
            "attempt_count": len(attempt_encounters),
            "attempt_encounters": attempt_encounters,
            "provider": result.get("reasoned_provider"),
            "provider_status": result.get("reasoned_provider_status"),
            "model": result.get("model"),
            "remote_processing": True,
            "characters_transmitted": min(len(text), 180_000),
            "manuscript_truncated": len(text) > 180_000,
            "repair_applied": bool(result.get("repair_applied")),
            "repair_steps": result.get("repair_steps") or [],
            "mandos_judgment": result.get("mandos_judgment") or {},
            "article_conformity": result.get("article_conformity") or {},
            "validation": validation,
            "commentary": candidate,
        }
    except (OSError, TimeoutError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            "status": "unavailable",
            "source": "fallback",
            "encounter_id": None,
            "provider": "gemini",
            "model": str(request.get("gemini_model") or "gemini-flash-lite-latest"),
            "remote_processing": bool(request.get("gemini_review_approved", False)),
            "commentary": f"Sophia Gemini reviewer endpoint was unavailable: {type(error).__name__}. Human review remains required.",
        }


def markdown_literature_map(queries: list[str], sources: list[dict[str, Any]]) -> str:
    lines = ["# Sophia Literature Discovery Map", "", "## Search Questions", ""]
    lines.extend(f"- {query}" for query in queries)
    lines.extend(["", "## Candidate Literature", ""])
    if not sources:
        lines.append("No governed scholarly leads were retrieved. Narrow the query or supply a seed bibliography.")
    for index, source in enumerate(sources, 1):
        authors = ", ".join(source.get("authors") or []) or "Author metadata unavailable"
        lines.extend([
            f"### {index}. {source.get('title') or 'Untitled source lead'}",
            "",
            f"- Authors: {authors}",
            f"- Year: {source.get('year') or 'n.d.'}",
            f"- Index: {source.get('source') or 'unknown'}",
            f"- Relevance: {source.get('relevance_score', 'unscored')}",
            f"- URL/DOI: {source.get('url') or 'not supplied'}",
            f"- Retrieved: {source.get('retrieved_at') or 'unknown'}",
            "",
            str(source.get("summary") or "No abstract supplied.").strip(),
            "",
        ])
    lines.extend([
        "## Integrity Boundary",
        "",
        "These are discovery leads, not a ghostwritten literature review and not proof that each source supports the manuscript. Verify the full text and bibliographic metadata before citation.",
    ])
    return "\n".join(lines)


def markdown_reference_audit(audit: dict[str, Any]) -> str:
    lines = [
        "# Sophia Technical Reference Audit",
        "",
        f"Status: **{audit['status']}**",
        f"Reconciliation/integrity findings: **{audit.get('integrity_issue_count', 0)}**",
        f"Style/formatting diagnostics: **{audit.get('style_diagnostic_count', 0)}**",
        f"Diagnostic findings total: **{audit.get('diagnostic_total_issue_count', audit.get('actionable_issue_count', 0))}**",
        "",
        "## Cross-Checks",
        "",
        f"- In-text citations detected: {len(audit['in_text_citations'])}",
        f"- Reference entries detected: {len(audit['reference_entries'])}",
        f"- Cited but missing from reference list: {len(audit['missing_from_reference_list'])}",
        f"- Listed but not cited: {len(audit['reference_list_entries_not_cited'])}",
        f"- Duplicate entries: {len(audit['duplicate_entries'])}",
        f"- Duplicate DOIs: {len(audit['duplicate_dois'])}",
        "",
        "## Missing From Reference List",
        "",
    ]
    lines.extend(f"- {row['author']} ({row['year']})" for row in audit["missing_from_reference_list"])
    if not audit["missing_from_reference_list"]:
        lines.append("- None detected.")
    lines.extend(["", "## Listed But Not Cited", ""])
    lines.extend(f"- {row['entry']}" for row in audit["reference_list_entries_not_cited"])
    if not audit["reference_list_entries_not_cited"]:
        lines.append("- None detected.")
    lines.extend(["", "## Entry-Level Findings", ""])
    for row in audit["reference_entries"]:
        issues = list(row["issues"]) + [item["type"] for item in row["style_check"]["errors"]]
        lines.append(f"- Reference {row['index']}: {', '.join(issues) if issues else 'no deterministic issue detected'}")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in audit["limits"])
    return "\n".join(lines)


def markdown_claim_ledger(claim_maps: list[dict[str, Any]]) -> str:
    lines = ["# Sophia Claim-to-Source Ledger", ""]
    for index, item in enumerate(claim_maps, 1):
        claim = item["claim_record"]
        mapping = item["source_map"]
        lines.extend([
            f"## Claim {index}",
            "",
            claim["claim"],
            "",
            f"- Type: {claim.get('claim_type')}",
            f"- Evidence risk: {claim.get('evidence_risk')}",
            f"- Evidence standard: {claim.get('evidence_standard')}",
            "",
        ])
        for source in mapping.get("results") or []:
            lines.extend([
                f"- **{source.get('support_label')}**: {source.get('source_name')}",
                f"  - Confidence: {source.get('confidence')}; rank: {source.get('ranking_score')}",
                f"  - Visible span: {source.get('exact_span') or 'not available'}",
                f"  - Citation lead: {source.get('apa_candidate') or source.get('url') or 'metadata incomplete'}",
                f"  - Limitation: {source.get('entailment_status') or 'verify full text'}",
            ])
        if not mapping.get("results"):
            lines.append("- No candidate source mapping available.")
        lines.append("")
    lines.extend([
        "## Release Rule",
        "",
        "A candidate abstract or visible span is a verification lead. The author or reviewer must inspect the full source before treating it as support.",
    ])
    return "\n".join(lines)


def run_review(request: dict[str, Any], request_path: Path, out_root: Path, base_url: str, sophia_root: Path) -> Path:
    job_id = str(request.get("job_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", job_id):
        raise ValueError("request.job_id must be a safe 3-101 character identifier")
    raw_document_path = Path(str(request.get("document_path") or "")).expanduser()
    document_path = raw_document_path if raw_document_path.is_absolute() else (request_path.parent / raw_document_path)
    document_path = document_path.resolve()
    if not document_path.is_file():
        raise FileNotFoundError(f"Manuscript not found: {document_path}")
    title = str(request.get("title") or document_path.stem).strip()
    text, parser = extract_document_text(document_path)
    if len(text.split()) < 40:
        raise ValueError("Manuscript has too little readable text for an academic review.")

    sys.path.insert(0, str((sophia_root / "arda_os").resolve()))
    from backend.services.academic_retrieval import get_academic_retrieval
    from backend.services.sophia_academic_claim_tools import classify_claim_type
    from backend.services.sophia_source_support import citation_check, map_claim_to_sources

    body_text, reference_text = split_reference_section(text)
    queries = [str(item).strip() for item in (request.get("literature_queries") or []) if str(item).strip()][:4]
    if not queries:
        question = str(request.get("research_question") or title).strip()
        queries = [question]
    external_retrieval = bool(request.get("external_retrieval", False))
    retrieval_records = []
    source_by_identity: dict[str, dict[str, Any]] = {}
    if external_retrieval:
        engine = get_academic_retrieval(evidence_dir=sophia_root / "evidence")
        for query in queries:
            result = engine.retrieve(query, include_local=False).to_dict()
            retrieval_records.append(result)
            for source in result.get("fragments") or []:
                identity = str(source.get("url") or source.get("content_hash") or source.get("title") or "").lower()
                if identity:
                    source_by_identity.setdefault(identity, source)
    sources = list(source_by_identity.values())
    reference_audit = audit_references(body_text, reference_text, citation_check)
    claims = select_claims(body_text, classify_claim_type)
    claim_maps = [
        {
            "claim_record": claim,
            "source_map": map_claim_to_sources(claim["claim"], sources, limit=5, enrich_metadata=False),
        }
        for claim in claims[:8]
    ]
    commentary = reviewer_commentary(
        base_url,
        request,
        title,
        document_path,
        text,
        parser,
        reference_audit,
        claim_maps,
        sources,
    )

    job_dir = (out_root / job_id).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    generated_names = {
        "LITERATURE_MAP.json", "LITERATURE_MAP.md", "REFERENCE_AUDIT.json", "REFERENCE_AUDIT.md",
        "CLAIM_SOURCE_LEDGER.json", "CLAIM_SOURCE_LEDGER.md", "REVIEWER_COMMENTARY.json",
        "REVIEWER_COMMENTARY.md", "HUMAN_APPROVAL.md", "SOPHIA_REVIEW_RECEIPT.json",
        f"{job_id}_SOPHIA_REVIEW_PACK.zip",
    }
    for name in generated_names:
        candidate = job_dir / name
        if candidate.is_file():
            candidate.unlink()
    literature_payload = {
        "schema": "dio.sophia_literature_map.v1",
        "queries": queries,
        "external_retrieval_approved": external_retrieval,
        "retrieval_runs": retrieval_records,
        "deduplicated_sources": sources,
    }
    claim_payload = {"schema": "dio.sophia_claim_source_ledger.v1", "claims": claim_maps}
    write_json(job_dir / "LITERATURE_MAP.json", literature_payload)
    write_text(job_dir / "LITERATURE_MAP.md", markdown_literature_map(queries, sources))
    write_json(job_dir / "REFERENCE_AUDIT.json", reference_audit)
    write_text(job_dir / "REFERENCE_AUDIT.md", markdown_reference_audit(reference_audit))
    write_json(job_dir / "CLAIM_SOURCE_LEDGER.json", claim_payload)
    write_text(job_dir / "CLAIM_SOURCE_LEDGER.md", markdown_claim_ledger(claim_maps))
    write_json(job_dir / "REVIEWER_COMMENTARY.json", commentary)
    write_text(
        job_dir / "REVIEWER_COMMENTARY.md",
        "# Sophia Reviewer Commentary\n\n"
        f"Status: **{commentary['status']}**\n\n"
        f"{commentary['commentary']}\n\n"
        "## Authorship Boundary\n\nThis commentary diagnoses and prioritizes revision. The author owns all final wording, interpretation, and submission decisions.",
    )
    write_text(
        job_dir / "HUMAN_APPROVAL.md",
        "# Sophia Human Approval Gate\n\n"
        f"Job: `{job_id}`\n\n"
        "- [ ] Confirm the manuscript owner authorized this review.\n"
        "- [ ] Confirm the manuscript owner authorized remote Gemini processing.\n"
        "- [ ] Verify every retained citation against the full source.\n"
        "- [ ] Resolve cited-but-missing and listed-but-uncited entries.\n"
        "- [ ] Review high-risk claims and their evidence standard.\n"
        "- [ ] Confirm reviewer commentary is diagnostic, not substituted authorship.\n"
        "- [ ] Approve the final pack for delivery.\n",
    )
    generated = sorted(path for path in job_dir.iterdir() if path.is_file())
    receipt = {
        "schema": "dio.sophia_review_receipt.v1",
        "job_id": job_id,
        "created_at": utc_now(),
        "status": "needs_human_review",
        "source": {
            "name": document_path.name,
            "sha256": sha256_file(document_path),
            "parser": parser,
            "word_count": len(text.split()),
            "full_text_copied_to_pack": False,
        },
        "metrics": {
            "literature_queries": len(queries),
            "candidate_sources": len(sources),
            "claims_reviewed": len(claim_maps),
            "reference_entries": len(reference_audit["reference_entries"]),
            "reference_findings": reference_audit["actionable_issue_count"],
            "reference_integrity_findings": int(reference_audit.get("integrity_issue_count") or 0),
            "reference_style_diagnostics": int(reference_audit.get("style_diagnostic_count") or 0),
            "reviewer_commentary_status": commentary["status"],
            "reviewer_provider": commentary.get("provider"),
            "reviewer_model": commentary.get("model"),
            "reviewer_grounding_passed": bool((commentary.get("validation") or {}).get("passed")),
        },
        "remote_processing": {
            "gemini_review_approved": bool(request.get("gemini_review_approved", False)),
            "performed": bool(commentary.get("remote_processing", False)),
            "characters_transmitted": commentary.get("characters_transmitted", 0),
        },
        "outputs": [{"name": path.name, "sha256": sha256_file(path)} for path in generated],
        "delivery_released": False,
    }
    write_json(job_dir / "SOPHIA_REVIEW_RECEIPT.json", receipt)
    archive_path = job_dir / f"{job_id}_SOPHIA_REVIEW_PACK.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(job_dir.iterdir()):
            if path.is_file() and path != archive_path:
                archive.write(path, arcname=path.name)
    return job_dir
