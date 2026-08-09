#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "corpora" / "caps"
DBE_CAPS_MAIN = "https://www.education.gov.za/Curriculum/CurriculumAssessmentPolicyStatements%28CAPS%29.aspx"
USER_AGENT = "KnowEdge-AutoRelease-CAPS-Corpus/1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_slug(value: str, fallback: str = "document") -> str:
    value = unquote(value or "")
    value = re.sub(r"\.(aspx|pdf)$", "", value, flags=re.I)
    value = re.sub(r"[^A-Za-z0-9._ -]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    value = value.replace(" ", "_")
    value = re.sub(r"_+", "_", value).strip("._-")
    return (value or fallback)[:140]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Link:
    text: str
    href: str


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[Link] = []
        self._href_stack: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {k.lower(): v for k, v in attrs}
        href = attrs_dict.get("href")
        if href:
            self._href_stack.append(href)
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href_stack:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
        self.links.append(Link(text=text, href=href))
        self._text_parts = []


def fetch_text(session: requests.Session, url: str, timeout: int = 30) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    encoding = response.encoding or "utf-8"
    return response.content.decode(encoding, errors="ignore")


def extract_links(html: str, base_url: str) -> list[Link]:
    parser = LinkParser()
    parser.feed(html)
    out: list[Link] = []
    for link in parser.links:
        out.append(Link(text=link.text, href=urljoin(base_url, link.href)))
    return out


def is_dbe_url(url: str) -> bool:
    return urlparse(url).netloc.lower().endswith("education.gov.za")


def is_caps_navigation_link(link: Link) -> bool:
    text = link.text.lower()
    href = link.href.lower()
    if not is_dbe_url(link.href):
        return False
    needles = [
        "caps for foundation",
        "caps for intermediate",
        "caps for senior",
        "caps for the fet",
    ]
    if any(item in text for item in needles):
        return True
    parsed = urlparse(link.href)
    query = parse_qs(parsed.query)
    return bool("link" in query and query["link"][0] in {"570", "571", "572", "573"})


def is_document_link(link: Link) -> bool:
    href = link.href.lower()
    if not is_dbe_url(link.href):
        return False
    return (
        ("linkclick.aspx" in href and "fileticket=" in href)
        or ".pdf" in href
        or "fileticket=" in href
    )


def phase_from_url_or_title(url: str, title: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    phase_id = ""
    for candidate in [(query.get("tabid") or [""])[0], (query.get("link") or [""])[0]]:
        if candidate in {"570", "571", "572", "573"}:
            phase_id = candidate
            break
    if phase_id == "571":
        return "foundation_grade_r_3"
    if phase_id == "572":
        return "intermediate_grade_4_6"
    if phase_id == "573":
        return "senior_grade_7_9"
    if phase_id == "570":
        return "fet_grade_10_12"
    text = f"{url} {title}".lower()
    if "foundation" in text or "grade r-3" in text or "grades r-3" in text or "gr r-3" in text:
        return "foundation_grade_r_3"
    if "intermediate" in text or "grade 4-6" in text or "grades 4-6" in text:
        return "intermediate_grade_4_6"
    if "senior" in text or "grade 7-9" in text or "grades 7-9" in text:
        return "senior_grade_7_9"
    if "fet" in text or "grade 10" in text or "grades 10" in text or "10-12" in text:
        return "fet_grade_10_12"
    if "sign language" in text:
        return "sa_sign_language"
    return "policy_and_support"


def canonical_nav_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    link_id = (query.get("link") or [""])[0]
    if link_id in {"570", "571", "572", "573"}:
        return f"https://www.education.gov.za/LinkClick.aspx?link={link_id}&tabid=420&portalid=0&mid=1208"
    return url


def document_id(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "fileticket" in query:
        return "fileticket_" + safe_slug(query["fileticket"][0], "fileticket")
    path_name = Path(parsed.path).name
    return safe_slug(path_name or parsed.path, "document")


def infer_filename(url: str, title: str, content_type: str, content_disposition: str, fallback_id: str) -> str:
    cd_match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', content_disposition or "", flags=re.I)
    if cd_match:
        candidate = safe_slug(cd_match.group(1), fallback_id)
    else:
        path_name = Path(urlparse(url).path).name
        candidate = safe_slug(path_name, "") if path_name.lower().endswith(".pdf") else ""
        if not candidate:
            candidate = safe_slug(title, fallback_id)
    if not candidate.endswith(".pdf") and ("pdf" in content_type.lower() or url.lower().endswith(".pdf")):
        candidate += ".pdf"
    if not candidate.endswith(".pdf"):
        candidate += ".bin"
    return candidate


def discover(session: requests.Session, seed_url: str) -> tuple[list[dict[str, Any]], list[str]]:
    page_queue = [seed_url]
    seen_pages: set[str] = set()
    document_records: dict[str, dict[str, Any]] = {}

    while page_queue:
        page_url = page_queue.pop(0)
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        html = fetch_text(session, page_url)
        links = extract_links(html, page_url)
        for link in links:
            if is_caps_navigation_link(link) and link.href not in seen_pages and link.href not in page_queue:
                page_url_next = canonical_nav_url(link.href)
                if page_url_next not in seen_pages and page_url_next not in page_queue:
                    page_queue.append(page_url_next)
            if not is_document_link(link):
                continue
            doc_key = document_id(link.href)
            phase = phase_from_url_or_title(link.href, link.text)
            if phase == "policy_and_support":
                phase = phase_from_url_or_title(page_url, link.text)
            existing = document_records.get(doc_key)
            if existing:
                existing["seen_on_pages"].append(page_url)
                if link.text and link.text.lower() != "download" and existing["title"].lower() == "download":
                    existing["title"] = link.text
                continue
            document_records[doc_key] = {
                "document_id": doc_key,
                "title": link.text or doc_key,
                "url": link.href,
                "phase": phase,
                "source_page": page_url,
                "seen_on_pages": [page_url],
            }
    return sorted(document_records.values(), key=lambda row: (row["phase"], row["title"], row["document_id"])), sorted(seen_pages)


def download_document(session: requests.Session, record: dict[str, Any], out_dir: Path, force: bool, timeout: int = 90) -> dict[str, Any]:
    phase_dir = out_dir / "pdf" / record["phase"]
    phase_dir.mkdir(parents=True, exist_ok=True)
    response = session.get(record["url"], timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    content = response.content
    content_type = response.headers.get("content-type", "")
    filename = infer_filename(
        response.url,
        record["title"],
        content_type,
        response.headers.get("content-disposition", ""),
        record["document_id"],
    )
    target = phase_dir / filename
    if target.exists() and not force:
        existing = target.read_bytes()
        record.update(
            {
                "status": "already_present",
                "path": str(target),
                "bytes": len(existing),
                "sha256": sha256_bytes(existing),
                "content_type": content_type,
                "final_url": response.url,
            }
        )
        return record
    target.write_bytes(content)
    record.update(
        {
            "status": "downloaded",
            "path": str(target),
            "bytes": len(content),
            "sha256": sha256_bytes(content),
            "content_type": content_type,
            "final_url": response.url,
            "looks_like_pdf": content.startswith(b"%PDF"),
        }
    )
    return record


def write_manifest(out_dir: Path, pages: list[str], records: list[dict[str, Any]], mode: str) -> Path:
    manifest = {
        "schema": "knowedge.caps_corpus_manifest.v1",
        "created_at": utc_now(),
        "source_authority": "South African Department of Basic Education",
        "seed_url": DBE_CAPS_MAIN,
        "mode": mode,
        "page_count": len(pages),
        "document_count": len(records),
        "downloaded_count": sum(1 for row in records if row.get("status") == "downloaded"),
        "already_present_count": sum(1 for row in records if row.get("status") == "already_present"),
        "failed_count": sum(1 for row in records if row.get("status") == "failed"),
        "total_bytes": sum(int(row.get("bytes") or 0) for row in records),
        "source_pages": pages,
        "documents": records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "caps_corpus_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def write_readme(out_dir: Path, records: list[dict[str, Any]], pages: list[str]) -> Path:
    by_phase: dict[str, int] = {}
    for row in records:
        by_phase[row["phase"]] = by_phase.get(row["phase"], 0) + 1
    lines = [
        "# CAPS Corpus",
        "",
        f"Created: {utc_now()}",
        "",
        "Authority: South African Department of Basic Education.",
        "",
        "Seed page:",
        "",
        f"- {DBE_CAPS_MAIN}",
        "",
        "The DBE states that CAPS documents are the Curriculum and Assessment Policy Statements for approved school subjects in the National Curriculum Statement Grades R-12. This local corpus is intended as HOMS Exam Studio source-of-truth material.",
        "",
        "## Counts",
        "",
        f"- Source pages crawled: {len(pages)}",
        f"- Documents discovered: {len(records)}",
        f"- Documents downloaded/present: {sum(1 for row in records if row.get('status') in {'downloaded', 'already_present'})}",
        f"- Failed downloads: {sum(1 for row in records if row.get('status') == 'failed')}",
        "",
        "## By Phase",
        "",
    ]
    for phase, count in sorted(by_phase.items()):
        lines.append(f"- {phase}: {count}")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- Manifest: `caps_corpus_manifest.json`",
            "- PDFs: `pdf/<phase>/...`",
            "",
            "## Use Boundary",
            "",
            "Use CAPS as curriculum authority for grade, subject, assessment scope, progression, and memo constraints. Do not treat CAPS as a replacement for educator review, school policy, moderation, or current DBE circulars.",
        ]
    )
    path = out_dir / "README.md"
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the official DBE CAPS corpus with manifest and hashes.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--seed-url", default=DBE_CAPS_MAIN)
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.15, help="Pause between document downloads.")
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    records, pages = discover(session, args.seed_url)

    mode = "manifest_only" if args.manifest_only else "download"
    if not args.manifest_only:
        completed = []
        for index, record in enumerate(records, start=1):
            try:
                completed.append(download_document(session, record, out_dir, args.force))
            except Exception as exc:
                failed = dict(record)
                failed.update({"status": "failed", "error": str(exc)})
                completed.append(failed)
            if args.sleep > 0 and index < len(records):
                time.sleep(args.sleep)
        records = completed

    manifest_path = write_manifest(out_dir, pages, records, mode)
    readme_path = write_readme(out_dir, records, pages)
    print(
        json.dumps(
            {
                "status": "completed",
                "mode": mode,
                "source_pages": len(pages),
                "documents": len(records),
                "downloaded_or_present": sum(1 for row in records if row.get("status") in {"downloaded", "already_present"}),
                "failed": sum(1 for row in records if row.get("status") == "failed"),
                "total_bytes": sum(int(row.get("bytes") or 0) for row in records),
                "manifest": str(manifest_path),
                "readme": str(readme_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
