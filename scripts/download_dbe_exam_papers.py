#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "corpora" / "exam_papers" / "dbe"
DEFAULT_MANIFEST = ROOT / "corpora" / "exam_papers" / "dbe_exam_papers_manifest.json"
USER_AGENT = "KnowEdge-AutoRelease-Exam-Paper-Corpus/1.0"


SEEDED_GEOGRAPHY_PAPERS = [
    {
        "title": "Geography P1 November 2025",
        "subject": "Geography",
        "year": 2025,
        "session": "november",
        "paper": "P1",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2025NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=-yt9PT3ew3w%3D&mid=14839&portalid=0&tabid=5742",
    },
    {
        "title": "Geography P2 November 2025",
        "subject": "Geography",
        "year": 2025,
        "session": "november",
        "paper": "P2",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2025NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=q-0mpNmbw9Q%3D&mid=14839&portalid=0&tabid=5742",
    },
    {
        "title": "Geography P1 May June 2025",
        "subject": "Geography",
        "year": 2025,
        "session": "may_june",
        "paper": "P1",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2025NSCMayJunepastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=SeR59ikc1gc%3D&mid=14238&portalid=0&tabid=5475",
    },
    {
        "title": "Geography P2 May June 2025",
        "subject": "Geography",
        "year": 2025,
        "session": "may_june",
        "paper": "P2",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2025NSCMayJunepastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=3LThLqo5qzA%3D&mid=14238&portalid=0&tabid=5475",
    },
    {
        "title": "Geography P1 November 2024",
        "subject": "Geography",
        "year": 2024,
        "session": "november",
        "paper": "P1",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2024NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=Hc8_CaQJpd4%3D&mid=13717&portalid=0&tabid=5193",
    },
    {
        "title": "Geography P2 November 2024",
        "subject": "Geography",
        "year": 2024,
        "session": "november",
        "paper": "P2",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2024NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=LrQ39-VlNh4%3D&mid=13717&portalid=0&tabid=5193",
    },
    {
        "title": "Geography P1 May June 2024",
        "subject": "Geography",
        "year": 2024,
        "session": "may_june",
        "paper": "P1",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2024NSCMayJunepastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=5lhg9xHnA2s%3D&mid=13140&portalid=0&tabid=4933",
    },
    {
        "title": "Geography P2 May June 2024",
        "subject": "Geography",
        "year": 2024,
        "session": "may_june",
        "paper": "P2",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2024NSCMayJunepastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=1iZYBxy7a7k%3D&mid=13140&portalid=0&tabid=4933",
    },
    {
        "title": "Geography P1 November 2023",
        "subject": "Geography",
        "year": 2023,
        "session": "november",
        "paper": "P1",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2023NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=sOLlvteQCeM%3D&mid=12674&portalid=0&tabid=4682",
    },
    {
        "title": "Geography P2 November 2023",
        "subject": "Geography",
        "year": 2023,
        "session": "november",
        "paper": "P2",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2023NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=qCvbCunZPCY%3D&mid=12674&portalid=0&tabid=4682",
    },
    {
        "title": "Geography P1 November 2022",
        "subject": "Geography",
        "year": 2022,
        "session": "november",
        "paper": "P1",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2022NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=T4gsWEf6_A0%3D&forcedownload=true&mid=12719&portalid=0&tabid=4683",
    },
    {
        "title": "Geography P2 November 2022",
        "subject": "Geography",
        "year": 2022,
        "session": "november",
        "paper": "P2",
        "kind": "question_paper",
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": "https://www.education.gov.za/Curriculum/NationalSeniorCertificate%28NSC%29Examinations/2022NSCNovemberpastpapers.aspx",
        "pdf_url": "https://www.education.gov.za/LinkClick.aspx?fileticket=yFfqSPQtFNw%3D&mid=10979&portalid=0&tabid=3294",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_slug(value: str, fallback: str = "paper") -> str:
    value = unquote(value or "")
    value = re.sub(r"\.(aspx|pdf)$", "", value, flags=re.I)
    value = re.sub(r"[^A-Za-z0-9._ -]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower().replace(" ", "_")
    return (re.sub(r"_+", "_", value).strip("._-") or fallback)[:140]


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
        href = {k.lower(): v for k, v in attrs}.get("href")
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


def infer_page_context(page_url: str) -> dict[str, Any]:
    lower = page_url.lower()
    year_match = re.search(r"\b(20\d{2})\b", lower)
    if "may" in lower and "june" in lower:
        session = "may_june"
    elif "sept" in lower:
        session = "september"
    else:
        session = "november"
    return {
        "year": int(year_match.group(1)) if year_match else None,
        "session": session,
    }


def infer_record(text: str, href: str, page_url: str, subject: str) -> dict[str, Any] | None:
    haystack = f"{text} {href}".lower()
    if subject.lower() not in haystack:
        return None
    if not ("linkclick.aspx" in href.lower() or href.lower().endswith(".pdf")):
        return None
    kind = "memo" if re.search(r"\b(memo|memorandum|marking|guideline)\b", haystack) else "question_paper"
    paper_match = re.search(r"\bp\s*([123])\b|paper\s*([123])", haystack, flags=re.I)
    year_match = re.search(r"\b(20\d{2})\b", haystack)
    page_context = infer_page_context(page_url)
    year = int(year_match.group(1)) if year_match else page_context["year"]
    if not paper_match or not year:
        return None
    session = "may_june" if re.search(r"may\s*/?\s*june|junie", haystack, flags=re.I) else page_context["session"]
    paper = f"P{paper_match.group(1) or paper_match.group(2)}"
    return {
        "title": text or f"{subject} {paper} {year}",
        "subject": subject,
        "year": year,
        "session": session,
        "paper": paper,
        "kind": kind,
        "phase": "fet_grade_10_12",
        "grade": 12,
        "source_url": page_url,
        "pdf_url": href,
    }


def discover_from_pages(session: requests.Session, page_urls: list[str], subject: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page_url in page_urls:
        response = session.get(page_url, timeout=30)
        response.raise_for_status()
        parser = LinkParser()
        parser.feed(response.text)
        for link in parser.links:
            href = urljoin(page_url, link.href)
            record = infer_record(link.text, href, page_url, subject)
            if record:
                records.append(record)
    return records


def load_seed_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("papers") or []
    else:
        rows = payload
    out = []
    for row in rows:
        if not row.get("pdf_url"):
            continue
        title = str(row.get("title") or "")
        inferred = infer_record(title, str(row["pdf_url"]), str(row.get("source_url") or ""), str(row.get("subject") or ""))
        merged = {**(inferred or {}), **row}
        merged.setdefault("phase", "fet_grade_10_12")
        merged.setdefault("grade", 12)
        merged.setdefault("kind", "question_paper")
        if not all(key in merged for key in ["subject", "year", "session", "paper", "title"]):
            raise ValueError(f"Seed row lacks required metadata: {row}")
        out.append(merged)
    return out


def paper_path(base: Path, record: dict[str, Any]) -> Path:
    subject = safe_slug(str(record["subject"]))
    year = str(record["year"])
    session = safe_slug(str(record["session"]))
    paper = safe_slug(str(record["paper"]))
    kind = safe_slug(str(record["kind"]))
    filename = f"{subject}_{year}_{session}_{paper}_{kind}.pdf"
    return base / "fet_grade_12" / subject / year / session / filename


def download_record(session: requests.Session, base: Path, record: dict[str, Any], refresh: bool) -> dict[str, Any]:
    out_path = paper_path(base, record)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not refresh:
        data = out_path.read_bytes()
    else:
        response = session.get(record["pdf_url"], timeout=60)
        response.raise_for_status()
        data = response.content
        if not data.startswith(b"%PDF"):
            raise RuntimeError(f"Expected PDF for {record['title']}, got {response.headers.get('content-type')}")
        out_path.write_bytes(data)
    return {
        **record,
        "path": str(out_path),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "downloaded_at": utc_now(),
    }


def dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record.get("pdf_url") or record.get("title"))
        out[key] = record
    return sorted(out.values(), key=lambda r: (r["year"], r["session"], r["paper"], r["kind"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download official DBE past exam papers into a local exemplar corpus.")
    parser.add_argument("--subject", default="Geography")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--page-url", action="append", default=[], help="Official DBE past-paper page to crawl.")
    parser.add_argument("--seed-geography", action="store_true", help="Use verified official Geography P1/P2 PDF seeds.")
    parser.add_argument("--seed-file", type=Path, help="JSON file containing official DBE PDF seed records.")
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    records: list[dict[str, Any]] = []
    if args.seed_geography and args.subject.lower() == "geography":
        records.extend(SEEDED_GEOGRAPHY_PAPERS)
    if args.seed_file:
        records.extend(load_seed_file(args.seed_file))
    if args.page_url:
        records.extend(discover_from_pages(session, args.page_url, args.subject))
    records = dedupe(records)
    if not records:
        raise SystemExit("No matching DBE paper links found.")
    downloaded = [download_record(session, args.out, record, args.refresh) for record in records]
    manifest = {
        "generated_at": utc_now(),
        "source": "Department of Basic Education official NSC past examination paper PDFs",
        "subject": args.subject,
        "paper_count": len(downloaded),
        "papers": downloaded,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Downloaded/indexed {len(downloaded)} paper(s)")
    print(args.manifest)


if __name__ == "__main__":
    main()
