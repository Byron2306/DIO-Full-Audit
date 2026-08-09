#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "corpora" / "exam_papers" / "dbe_exam_papers_manifest.json"
DEFAULT_OUT = ROOT / "deliverables" / "exam_source_matrix"
DEFAULT_TEXT_CACHE = ROOT / "corpora" / "exam_papers" / "text"


QUESTION_RE = re.compile(r"^\s*(?:QUESTION|VRAAG)\s+(\d+)\s*:?\s*(.*?)(?:\s+\(\d+\))?\s*$", re.IGNORECASE)
MARK_RE = re.compile(r"\((\d+)\s*x\s*\d+\)|\((\d+)\)", re.IGNORECASE)
SOURCE_ANCHOR_RE = re.compile(
    r"\b("
    r"refer to|study|based on|use the|figure|fig\.|source|extract|table|graph|map|"
    r"orthophoto|topographical|topographic|diagram|sketch|cartoon|photograph|photo|"
    r"satellite image|infographic|climate graph|synoptic|case study|annexure|data|"
    r"lees|bestudeer|teks|bron|uittreksel|tabel|grafiek|grafiese teks|prent|foto|"
    r"advertensie|spotprent|strokiesprent|gedig"
    r")\b",
    re.IGNORECASE,
)
OBJECT_RE = re.compile(
    r"\b("
    r"FIGURE|FIG\.|TABLE|GRAPH|SOURCE|EXTRACT|MAP|ORTHOPHOTO|TOPOGRAPHIC(?:AL)?\s+MAP|"
    r"SKETCH|DIAGRAM|PHOTOGRAPH|PHOTO|IMAGE|INFOGRAPHIC|CARTOON|"
    r"TEKS|BRON|UITTREKSEL|TABEL|GRAFIEK|PRENT|FOTO|ADVERTENSIE|SPOTPRENT|STROKIESPRENT"
    r")\s*([0-9]+(?:\.[0-9]+)?)?",
    re.IGNORECASE,
)

SOURCE_CLASSIFIERS = {
    "topographic_map_and_orthophoto": [
        "topographic", "topographical", "orthophoto", "grid reference", "contour", "magnetic bearing",
        "map extract", "1 : 50 000", "1:50 000",
    ],
    "synoptic_weather_map": [
        "synoptic", "weather map", "isobar", "mid-latitude cyclone", "tropical cyclone", "anticyclone",
        "pressure cell", "cold front", "warm front",
    ],
    "map_extract": [
        "map", "distribution", "location", "settlement pattern", "land-use", "land use", "gis",
    ],
    "graph_or_chart": [
        "graph", "bar graph", "line graph", "pie graph", "climate graph", "chart", "trend",
        "grafiek", "grafiese teks",
    ],
    "data_table": [
        "table", "data", "statistics", "figures below", "rate", "percentage", "%",
        "tabel", "statistiek", "persentasie",
    ],
    "text_extract": [
        "extract", "source", "article", "case study", "newspaper", "adapted from", "read the",
        "teks", "bron", "uittreksel", "artikel", "lees die", "gedig", "verwerk uit",
    ],
    "photograph_or_image": [
        "photograph", "photo", "image", "satellite image", "picture", "infographic",
        "foto", "prent",
    ],
    "diagram_or_model": [
        "diagram", "sketch", "cross-section", "model", "illustration",
    ],
    "cartoon": [
        "cartoon", "comic", "spotprent", "strokiesprent",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: str, limit: int = 500) -> str:
    value = re.sub(r"[ \t]+", " ", str(value or ""))
    return re.sub(r"\n{3,}", "\n\n", value).strip()[:limit].rstrip()


def ocr_pdf_text(path: Path, cache_dir: Path, dpi: int = 140) -> str:
    image_dir = cache_dir / "ocr_pages" / path.stem
    text_path = cache_dir / f"{path.stem}.ocr.txt"
    if text_path.exists():
        return text_path.read_text(encoding="utf-8", errors="ignore")
    image_dir.mkdir(parents=True, exist_ok=True)
    prefix = image_dir / "page"
    result = subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-png", str(path), str(prefix)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftoppm OCR render failed for {path}")
    pages = sorted(image_dir.glob("page-*.png"))
    chunks = []
    for page in pages:
        ocr = subprocess.run(
            ["tesseract", str(page), "stdout", "--psm", "6"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        chunks.append(ocr.stdout if ocr.returncode == 0 else "")
    text = "\f".join(chunks)
    text_path.write_text(text, encoding="utf-8")
    return text


def extract_pdf_text(path: Path, cache_dir: Path, ocr_empty: bool = False) -> tuple[str, str]:
    cache_path = cache_dir / f"{path.stem}.txt"
    if cache_path.exists():
        text = cache_path.read_text(encoding="utf-8", errors="ignore")
        if ocr_empty and len(re.sub(r"\s+", "", text.replace("\f", ""))) < 200:
            return ocr_pdf_text(path, cache_dir), "ocr"
        return text, "pdftotext"
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftotext failed for {path}")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(result.stdout, encoding="utf-8")
    if ocr_empty and len(re.sub(r"\s+", "", result.stdout.replace("\f", ""))) < 200:
        return ocr_pdf_text(path, cache_dir), "ocr"
    return result.stdout, "pdftotext"


def image_inventory(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["pdfimages", "-list", str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {"available": False, "count": None, "error": clean(result.stderr, 200)}
    rows = [
        line for line in result.stdout.splitlines()
        if re.match(r"\s*\d+\s+\d+\s+\w+", line)
    ]
    return {"available": True, "count": len(rows)}


def classify_source(snippet: str) -> list[str]:
    lower = snippet.lower()
    found = []
    for source_type, needles in SOURCE_CLASSIFIERS.items():
        if any(phrase_present(lower, needle) for needle in needles):
            found.append(source_type)
    if not found and SOURCE_ANCHOR_RE.search(snippet):
        found.append("unclassified_stimulus")
    if re.search(r"\bmap\s+jacobs\b", lower):
        found = [item for item in found if item != "map_extract"]
    return found


def phrase_present(lower_text: str, needle: str) -> bool:
    needle_l = needle.lower()
    if re.search(r"[a-z0-9]", needle_l):
        pattern = re.escape(needle_l)
        pattern = re.sub(r"\\\s+", r"\\s+", pattern)
        return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", lower_text))
    return needle_l in lower_text


def is_admin_source_snippet(snippet: str) -> bool:
    lower = snippet.lower()
    admin_patterns = [
        "mark allocation",
        "time allocation",
        "use the table below as a guide when answering",
        "guide to help you allocate your time",
        "answer four questions as follows",
        "this question paper consists",
        "instructions and information",
        "start each question on a new page",
        "write neatly and legibly",
    ]
    return any(pattern in lower for pattern in admin_patterns)


def source_quality(types: list[str], snippet: str) -> str:
    if "topographic_map_and_orthophoto" in types or "synoptic_weather_map" in types:
        return "hard_visual_contract"
    if any(item in types for item in ["map_extract", "graph_or_chart", "data_table", "diagram_or_model"]):
        return "structured_visual_or_data_contract"
    if any(item in types for item in ["text_extract", "photograph_or_image", "cartoon"]):
        return "source_stimulus_contract"
    if SOURCE_ANCHOR_RE.search(snippet):
        return "needs_human_classification"
    return "none"


def source_object_id(item: dict[str, Any]) -> str:
    snippet = item["snippet"]
    question = item.get("question") or {}
    q = question.get("number") or "paper"
    lower = snippet.lower()
    if "topographic" in lower or "topographical" in lower or "orthophoto" in lower:
        return f"Q{q}:topographic_orthophoto_mapwork"
    match = OBJECT_RE.search(snippet)
    if match:
        label = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
        number = match.group(2) or q
        return f"Q{q}:{label}_{number}"
    types = "_".join(item.get("source_types") or ["stimulus"])
    return f"Q{q}:{types}:{item.get('page')}:{item.get('line')}"


def extract_source_objects(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    objects: dict[str, dict[str, Any]] = {}
    for item in evidence:
        object_id = source_object_id(item)
        existing = objects.get(object_id)
        if existing:
            existing["evidence_count"] += 1
            existing["pages"] = sorted(set(existing["pages"] + [item["page"]]))
            existing["source_types"] = sorted(set(existing["source_types"] + item.get("source_types", [])))
            if len(existing["snippets"]) < 3 and item["snippet"] not in existing["snippets"]:
                existing["snippets"].append(item["snippet"])
            continue
        objects[object_id] = {
            "object_id": object_id,
            "question": item.get("question"),
            "pages": [item["page"]],
            "source_types": item.get("source_types", []),
            "quality": item.get("quality"),
            "evidence_count": 1,
            "snippets": [item["snippet"]],
        }
    return sorted(objects.values(), key=lambda item: (item["pages"][0], item["object_id"]))


def nearest_question(current_question: dict[str, str] | None) -> dict[str, str] | None:
    if not current_question:
        return None
    return {k: v for k, v in current_question.items() if v}


def extract_evidence(text: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    current_question: dict[str, str] | None = None
    pages = text.split("\f")
    for page_no, page in enumerate(pages, start=1):
        lines = page.splitlines()
        for idx, line in enumerate(lines):
            line_clean = clean(line, 400)
            if not line_clean:
                continue
            question_match = QUESTION_RE.match(line_clean)
            if question_match:
                current_question = {
                    "number": question_match.group(1),
                    "title": clean(question_match.group(2), 160),
                }
            if not SOURCE_ANCHOR_RE.search(line_clean):
                continue
            window_lines = lines[idx : min(len(lines), idx + 4)]
            snippet = clean(" ".join(item.strip() for item in window_lines if item.strip()), 650)
            if len(snippet) < 24:
                continue
            if is_admin_source_snippet(snippet):
                continue
            types = classify_source(snippet)
            if types == ["unclassified_stimulus"] and re.search(r"answer all|leave a line|number the answers|write in the margins", snippet, re.I):
                continue
            mark_matches = [int(a or b) for a, b in MARK_RE.findall(snippet) if (a or b)]
            evidence.append(
                {
                    "page": page_no,
                    "line": idx + 1,
                    "question": nearest_question(current_question),
                    "snippet": snippet,
                    "source_types": types,
                    "quality": source_quality(types, snippet),
                    "mark_hints": mark_matches[:5],
                }
            )
    return collapse_near_duplicates(evidence)


def collapse_near_duplicates(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, str]] = set()
    out: list[dict[str, Any]] = []
    for item in evidence:
        key_text = re.sub(r"[^a-z0-9]+", " ", item["snippet"].lower()).strip()[:160]
        key = (int(item["page"]), key_text)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def paper_theme(row: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    title = f"{row.get('paper', '')} {row.get('title', '')}".lower()
    subject = str(row.get("subject") or "").lower()
    if "afrikaans" in subject or "english" in subject:
        if "p1" in title:
            return "language_context_comprehension_summary_visual_literacy"
        if "p2" in title:
            return "literature_contextual_and_essay"
        if "p3" in title:
            return "writing_transactional_and_visual_prompt"
    if "life orientation" in subject:
        return "life_orientation_cat_scenario_and_reflection"
    if "p1" in title:
        return "climate_weather_geomorphology_and_mapwork"
    if "p2" in title:
        return "settlement_economic_geography_and_mapwork"
    blob = " ".join(item["snippet"].lower() for item in evidence[:20])
    if "climate" in blob or "geomorphology" in blob:
        return "climate_weather_geomorphology_and_mapwork"
    if "settlement" in blob or "economic geography" in blob:
        return "settlement_economic_geography_and_mapwork"
    return "unknown"


def analyze_paper(row: dict[str, Any], cache_dir: Path, ocr_empty: bool = False) -> dict[str, Any]:
    path = Path(row["path"])
    text, extraction_method = extract_pdf_text(path, cache_dir, ocr_empty=ocr_empty)
    evidence = extract_evidence(text)
    source_objects = extract_source_objects(evidence)
    type_counts = Counter(source_type for item in evidence for source_type in item["source_types"])
    object_type_counts = Counter(source_type for item in source_objects for source_type in item["source_types"])
    quality_counts = Counter(item["quality"] for item in evidence)
    questions = {
        item["question"].get("number"): item["question"].get("title", "")
        for item in evidence
        if item.get("question") and item["question"].get("number")
    }
    return {
        **row,
        "paper_theme": paper_theme(row, evidence),
        "text_extraction_method": extraction_method,
        "page_count_estimate": max(1, len(text.split("\f"))),
        "embedded_image_inventory": image_inventory(path),
        "source_type_counts": dict(type_counts),
        "unique_source_object_count": len(source_objects),
        "unique_source_object_type_counts": dict(object_type_counts),
        "quality_counts": dict(quality_counts),
        "question_titles_seen": questions,
        "source_objects": source_objects,
        "source_evidence": evidence,
    }


def aggregate(papers: list[dict[str, Any]]) -> dict[str, Any]:
    by_paper = defaultdict(Counter)
    by_theme = defaultdict(Counter)
    total = Counter()
    recurring_contracts: dict[str, Any] = {}
    for paper in papers:
        key = f"{paper.get('paper')}:{paper.get('paper_theme')}"
        counts = Counter(paper["unique_source_object_type_counts"])
        by_paper[str(paper.get("paper"))].update(counts)
        by_theme[str(paper.get("paper_theme"))].update(counts)
        total.update(counts)
    for group, counts in by_paper.items():
        recurring_contracts[group] = [
            {"source_type": source_type, "hits": hits}
            for source_type, hits in counts.most_common()
            if hits >= 2
        ]
    return {
        "source_type_counts": dict(total),
        "source_types_by_paper": {k: dict(v) for k, v in by_paper.items()},
        "source_types_by_theme": {k: dict(v) for k, v in by_theme.items()},
        "recurring_contracts": recurring_contracts,
    }


def write_markdown(out_dir: Path, matrix: dict[str, Any]) -> None:
    lines = [
        "# DBE Exam Source Matrix",
        "",
        f"Generated: {matrix['generated_at']}",
        f"Corpus papers: {matrix['paper_count']}",
        "",
        "## Actual Source Types Detected",
        "",
    ]
    for source_type, hits in sorted(matrix["aggregate"]["source_type_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {source_type}: {hits}")
    lines.extend(["", "## Paper Contracts", ""])
    for paper in matrix["papers"]:
        lines.append(f"### {paper['title']}")
        lines.append(f"- Theme: {paper['paper_theme']}")
        lines.append(f"- Embedded image objects: {paper['embedded_image_inventory'].get('count')}")
        lines.append(f"- Unique source/stimulus objects: {paper['unique_source_object_count']}")
        counts = ", ".join(f"{k}={v}" for k, v in sorted(paper["unique_source_object_type_counts"].items()))
        lines.append(f"- Unique source object types: {counts or 'none'}")
        hard = [
            item for item in paper["source_objects"]
            if item["quality"] in {"hard_visual_contract", "structured_visual_or_data_contract"}
        ][:6]
        if hard:
            lines.append("- Representative evidence:")
            for item in hard:
                question = item.get("question") or {}
                q = f"Q{question.get('number')}" if question.get("number") else "paper"
                lines.append(f"  - p.{','.join(str(page) for page in item['pages'])} {q}: {item['snippets'][0]}")
        lines.append("")
    out_dir.joinpath("DBE_EXAM_SOURCE_MATRIX.md").write_text("\n".join(lines), encoding="utf-8")


def write_contracts(out_dir: Path, matrix: dict[str, Any]) -> None:
    contracts: dict[str, Any] = {
        "schema": "knowedge.homs_exam_source_contracts.v1",
        "generated_at": matrix["generated_at"],
        "source_matrix": str(out_dir / "exam_source_matrix.json"),
        "subject": matrix.get("subject"),
        "phase": "fet_grade_10_12",
        "grade": 12,
        "contracts": {},
    }
    for paper in matrix["papers"]:
        key = f"{paper['paper']}:{paper['paper_theme']}"
        contract = contracts["contracts"].setdefault(
            key,
            {
                "paper": paper["paper"],
                "paper_theme": paper["paper_theme"],
                "paper_count": 0,
                "source_type_counts": Counter(),
                "required_repeated_source_types": [],
                "supporting_papers": [],
            },
        )
        contract["paper_count"] += 1
        contract["supporting_papers"].append(
            {
                "title": paper["title"],
                "path": paper["path"],
                "source_url": paper["source_url"],
                "pdf_url": paper["pdf_url"],
                "unique_source_object_type_counts": paper["unique_source_object_type_counts"],
            }
        )
        contract["source_type_counts"].update(paper["unique_source_object_type_counts"])
    for contract in contracts["contracts"].values():
        counts = contract["source_type_counts"]
        paper_count = max(1, contract["paper_count"])
        contract["source_type_counts"] = dict(counts)
        contract["required_repeated_source_types"] = [
            {
                "source_type": source_type,
                "hits": hits,
                "coverage_ratio": round(hits / paper_count, 2),
            }
            for source_type, hits in counts.most_common()
            if hits >= paper_count
        ]
    out_dir.joinpath("exam_source_contracts.json").write_text(json.dumps(contracts, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract actual source/stimulus contracts from old DBE exam papers.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--text-cache", type=Path, default=DEFAULT_TEXT_CACHE)
    parser.add_argument("--subject", default="")
    parser.add_argument("--kind", default="question_paper")
    parser.add_argument("--ocr-empty", action="store_true", help="OCR PDFs where pdftotext extracts almost no text.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = manifest["papers"]
    if args.subject:
        rows = [row for row in rows if str(row.get("subject", "")).lower() == args.subject.lower()]
    if args.kind:
        rows = [row for row in rows if row.get("kind") == args.kind]
    papers = [analyze_paper(row, args.text_cache, ocr_empty=args.ocr_empty) for row in rows]
    matrix = {
        "generated_at": utc_now(),
        "manifest": str(args.manifest),
        "subject": args.subject or manifest.get("subject"),
        "paper_count": len(papers),
        "method": "pdftotext layout extraction plus repeated source/stimulus classifiers from official past papers",
        "aggregate": aggregate(papers),
        "papers": papers,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    args.out.joinpath("exam_source_matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")
    write_markdown(args.out, matrix)
    write_contracts(args.out, matrix)
    print(f"Analyzed {len(papers)} paper(s)")
    print(args.out / "exam_source_matrix.json")
    print(args.out / "DBE_EXAM_SOURCE_MATRIX.md")
    print(args.out / "exam_source_contracts.json")


if __name__ == "__main__":
    main()
