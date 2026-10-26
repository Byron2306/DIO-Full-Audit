#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ATLAS_DEFAULTS = [
    Path.home() / "Desktop" / "DIO_META_Portfolio_Atlas.xlsx",
    Path.home() / "Downloads" / "DIO_META_Portfolio_Atlas.xlsx",
]

SHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "product"


def candidate_id(name: str) -> str:
    digest = hashlib.sha1(f"dio-meta-atlas:{name}".encode("utf-8")).hexdigest().upper()
    return f"PC-ATLAS-{digest[:16]}"


def column_index(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha())
    value = 0
    for character in letters:
        value = value * 26 + ord(character.upper()) - 64
    return value - 1


def read_xlsx(path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("a:si", SHEET_NS):
                text = "".join(
                    node.text or ""
                    for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                )
                shared_strings.append(text)

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relationships}
        sheets: dict[str, str] = {}
        for sheet in workbook.findall("a:sheets/a:sheet", SHEET_NS):
            target = targets[sheet.attrib[OFFICE_REL]]
            sheets[sheet.attrib["name"]] = f"xl/{target}"

        parsed: dict[str, list[list[str]]] = {}
        for sheet_name, sheet_path in sheets.items():
            sheet_root = ET.fromstring(archive.read(sheet_path))
            rows: list[list[str]] = []
            for row in sheet_root.findall("a:sheetData/a:row", SHEET_NS):
                cells: dict[int, str] = {}
                for cell in row.findall("a:c", SHEET_NS):
                    ref = cell.attrib.get("r", "A1")
                    value_node = cell.find("a:v", SHEET_NS)
                    inline_node = cell.find("a:is", SHEET_NS)
                    value = ""
                    if cell.attrib.get("t") == "s" and value_node is not None:
                        value = shared_strings[int(value_node.text or "0")]
                    elif cell.attrib.get("t") == "inlineStr" and inline_node is not None:
                        value = "".join(
                            node.text or ""
                            for node in inline_node.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                        )
                    elif value_node is not None:
                        value = value_node.text or ""
                    cells[column_index(ref)] = value.strip()
                if cells:
                    rows.append([cells.get(index, "") for index in range(max(cells) + 1)])
            parsed[sheet_name] = rows
        return parsed


def table_from_sheet(rows: list[list[str]], first_header: str) -> list[dict[str, str]]:
    header_index = None
    for index, row in enumerate(rows):
        if row and row[0] == first_header:
            header_index = index
            break
    if header_index is None:
        return []
    headers = rows[header_index]
    records = []
    for row in rows[header_index + 1 :]:
        if not any(row):
            continue
        record = {
            headers[index]: row[index] if index < len(row) else ""
            for index in range(len(headers))
            if headers[index]
        }
        if any(record.values()):
            records.append(record)
    return records


def split_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r";|\+", value or "") if part.strip()]


def state_for_maturity(maturity: str) -> str:
    lowered = maturity.lower()
    if any(marker in lowered for marker in ("production proof", "controlled transaction", "internal proof", "internal capability", "implemented", "fusion core")):
        return "pilot_ready"
    if any(marker in lowered for marker in ("architecture seeded", "profile extension", "meta primitive", "meta foundation")):
        return "incarnated"
    return "candidate"


def claim_ceiling(maturity: str) -> str:
    lowered = maturity.lower()
    if any(marker in lowered for marker in ("production proof", "controlled transaction", "internal proof", "internal capability", "implemented", "fusion core")):
        return "CONTROLLED_PROOF"
    return "HYPOTHESIS"


def candidate_from_incarnation(row: dict[str, str], generated_at: str, atlas_path: Path, atlas_hash: str, receipt_path: Path) -> dict[str, Any]:
    name = row["Incarnation"]
    product_id = slug(name)
    state = state_for_maturity(row.get("Maturity", ""))
    proof_ceiling = claim_ceiling(row.get("Maturity", ""))
    return {
        "schema": "dio.product_candidate.v1",
        "candidate_id": candidate_id(name),
        "product_id": product_id,
        "name": name,
        "state": state,
        "created_at": generated_at,
        "updated_at": generated_at,
        "source_signals": [
            {
                "type": "portfolio_atlas_row",
                "source": str(atlas_path),
                "source_sha256": atlas_hash,
                "suite": row.get("Suite", ""),
                "primary_family": row.get("Primary family", ""),
                "maturity": row.get("Maturity", ""),
                "horizon": row.get("Horizon", ""),
                "reuse_score": row.get("Reuse score", ""),
                "build_burden": row.get("Build burden", ""),
                "validation_burden": row.get("Validation burden", ""),
            }
        ],
        "audience": {
            "buyer_market": row.get("Buyer / market", ""),
            "segments": split_list(row.get("Buyer / market", "")),
            "suite": row.get("Suite", ""),
            "horizon": row.get("Horizon", ""),
        },
        "pain": row.get("Problem solved", ""),
        "offer": {
            "suite": row.get("Suite", ""),
            "primary_family": row.get("Primary family", ""),
            "work_patterns": split_list(row.get("Work patterns", "")),
            "meta_composition": row.get("META composition", ""),
            "key_profiles": split_list(row.get("Key profiles", "")),
            "output": row.get("Output", ""),
            "commercial_position": "portfolio_class_registered",
        },
        "proof": {
            "claim_ceiling": proof_ceiling,
            "manifest_path": str(receipt_path.relative_to(ROOT)),
            "unsupported_inferences": [
                "paid market demand is not proven by atlas registration",
                "repeatable fulfilment economics are not proven by atlas registration",
                "public campaign performance is not proven by atlas registration",
            ],
            "maturity": row.get("Maturity", ""),
        },
        "incarnation": {
            "receipt_path": str(receipt_path.relative_to(ROOT)),
            "source_archive": str(atlas_path),
            "fingerprint": atlas_hash,
            "artifact_integrity": "ATLAS_REGISTERED",
            "human_gate": "NEEDS_YOU",
            "artifact_count": 0,
            "main_organs": split_list(row.get("Main organs", "")),
        },
        "campaign": {
            "state": "ready_for_market_command_scaffold",
            "permission_boundary": "outreach, publish and spend remain operator-gated",
        },
        "marketfront": {
            "state": "public_page_or_offer_block_required",
            "route": "dio.public_intake.v1",
        },
        "fulfilment_route": {
            "state": "routable_from_atlas_profile",
            "main_organs": split_list(row.get("Main organs", "")),
            "work_patterns": split_list(row.get("Work patterns", "")),
            "profiles": split_list(row.get("Key profiles", "")),
            "output": row.get("Output", ""),
        },
        "approval": {
            "state": "needs_operator",
            "release_boundary": "Registered product class may be scaffolded internally; client processing, paid release, outreach, publication and delivery still require the configured DIO gates.",
        },
        "commercial_metrics": {
            "paid_orders": 0,
            "verified_revenue_minor": 0,
            "qualified_leads": 0,
            "repeatability_score": 0,
        },
        "decision": {
            "state": "pilot" if state == "pilot_ready" else "candidate",
            "reason": f"Imported from DIO Meta Portfolio Atlas as {row.get('Maturity', 'unclassified')} with horizon {row.get('Horizon', 'unknown')}.",
        },
    }


def build_markdown_report(registry: dict[str, Any]) -> str:
    suite_lines = []
    for suite in registry["suites"]:
        suite_lines.append(
            f"| {suite['Suite']} | {suite['Anchor products']} | {suite['Expansion products']} | {suite['Best entry wedge']} | {suite['Horizon']} |"
        )

    incarnation_lines = []
    for item in registry["incarnations"]:
        incarnation_lines.append(
            f"| {item['Incarnation']} | {item['Suite']} | {item['Maturity']} | {item['Horizon']} | {item['candidate_id']} | {item['state']} |"
        )

    counts = registry["summary"]
    return "\n".join(
        [
            "# DIO Meta Portfolio Atlas Activation",
            "",
            f"Generated: `{registry['generated_at']}`",
            f"Source workbook: `{registry['source']['path']}`",
            f"Workbook SHA-256: `{registry['source']['sha256']}`",
            "",
            "## Activation Verdict",
            "",
            "All atlas product classes are now registered as governed DIO product candidates. This makes them visible to the product registry, routable through the shared DIO intake/approval model, and available for Market Command scaffolding without pretending every class has paid-market proof.",
            "",
            f"- Meta primitives: `{counts['meta_primitives']}`",
            f"- Work patterns: `{counts['work_patterns']}`",
            f"- Profile rows: `{counts['profiles']}`",
            f"- Sellable suites: `{counts['suites']}`",
            f"- Commercial incarnations: `{counts['incarnations']}`",
            f"- Pilot-ready / controlled-proof classes: `{counts['pilot_ready']}`",
            f"- Incarnated architecture/profile classes: `{counts['incarnated']}`",
            f"- Candidate-only classes: `{counts['candidate']}`",
            "",
            "## Suites",
            "",
            "| Suite | Anchors | Expansion | Entry wedge | Horizon |",
            "| --- | --- | --- | --- | --- |",
            *suite_lines,
            "",
            "## Product Classes",
            "",
            "| Product class | Suite | Maturity | Horizon | Candidate | State |",
            "| --- | --- | --- | --- | --- | --- |",
            *incarnation_lines,
            "",
            "## Operating Boundary",
            "",
            "Registered means DIO can route, scaffold, brief, campaign-plan, and prepare governed demos for the class. It does not mean DIO may publish, spend, contact prospects, process sensitive client material, issue payment, or deliver final work without the relevant operator gate.",
            "",
        ]
    )


def import_atlas(atlas_path: Path) -> dict[str, Any]:
    generated_at = utc_now()
    atlas_path = atlas_path.resolve()
    atlas_hash = sha256(atlas_path)
    workbook = read_xlsx(atlas_path)
    meta = table_from_sheet(workbook.get("01_META", []), "Primitive")
    work_patterns = table_from_sheet(workbook.get("02_WORK_PATTERNS", []), "ID")
    profiles = table_from_sheet(workbook.get("03_PROFILE_LIBRARY", []), "Profile class")
    incarnations = table_from_sheet(workbook.get("04_INCARNATIONS", []), "Incarnation")
    suites = table_from_sheet(workbook.get("05_SUITES", []), "Suite")
    receipt_path = ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"

    candidates = []
    for row in incarnations:
        candidate = candidate_from_incarnation(row, generated_at, atlas_path, atlas_hash, receipt_path)
        candidate_path = ROOT / "state" / "product_candidates" / candidate["candidate_id"] / "PRODUCT_CANDIDATE.json"
        write_json(candidate_path, candidate)
        row["candidate_id"] = candidate["candidate_id"]
        row["product_id"] = candidate["product_id"]
        row["state"] = candidate["state"]
        row["claim_ceiling"] = candidate["proof"]["claim_ceiling"]
        row["candidate_path"] = str(candidate_path.relative_to(ROOT))
        candidates.append(
            {
                "candidate_id": candidate["candidate_id"],
                "product_id": candidate["product_id"],
                "name": candidate["name"],
                "suite": row.get("Suite", ""),
                "state": candidate["state"],
                "maturity": row.get("Maturity", ""),
                "horizon": row.get("Horizon", ""),
                "path": str(candidate_path.relative_to(ROOT)),
            }
        )

    state_counts = {state: sum(candidate["state"] == state for candidate in candidates) for state in ("pilot_ready", "incarnated", "candidate")}
    registry = {
        "schema": "dio.meta_portfolio_atlas.v1",
        "generated_at": generated_at,
        "source": {
            "path": str(atlas_path),
            "sha256": atlas_hash,
        },
        "summary": {
            "meta_primitives": len(meta),
            "work_patterns": len(work_patterns),
            "profiles": len(profiles),
            "suites": len(suites),
            "incarnations": len(incarnations),
            **state_counts,
        },
        "meta_primitives": meta,
        "work_patterns": work_patterns,
        "profiles": profiles,
        "suites": suites,
        "incarnations": incarnations,
        "candidates": candidates,
    }
    write_json(receipt_path, registry)
    write_json(ROOT / "config" / "dio_product_classes.json", registry)
    report_path = ROOT / "docs" / "DIO_META_PORTFOLIO_ATLAS_PRODUCT_CLASS_ACTIVATION_2026-08-16.md"
    write_text(report_path, build_markdown_report(registry))
    registry["report_path"] = str(report_path.relative_to(ROOT))
    write_json(receipt_path, registry)
    write_json(ROOT / "config" / "dio_product_classes.json", registry)
    return registry


def choose_atlas(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            raise FileNotFoundError(path)
        return path
    existing = [path for path in ATLAS_DEFAULTS if path.exists()]
    if not existing:
        raise FileNotFoundError("DIO_META_Portfolio_Atlas.xlsx was not found in Desktop or Downloads.")
    return max(existing, key=lambda path: (path.stat().st_mtime, path.stat().st_size))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the DIO Meta Portfolio Atlas into governed DIO product candidates.")
    parser.add_argument("--atlas", help="Path to DIO_META_Portfolio_Atlas.xlsx")
    args = parser.parse_args()
    registry = import_atlas(choose_atlas(args.atlas))
    print(json.dumps({
        "schema": registry["schema"],
        "source": registry["source"],
        "summary": registry["summary"],
        "report_path": registry["report_path"],
    }, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
