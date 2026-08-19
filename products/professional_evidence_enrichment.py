from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(manifest: dict[str, Any]) -> str:
    core = {key: value for key, value in manifest.items() if key != "packet_fingerprint"}
    return "sha256:" + hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def enrich_customer_packet(incarnation: str, packet_dir: Path) -> dict[str, Any]:
    """Add realistic product-shaped customer files and rebind the packet manifest.

    Enrichment may only add customer-facing source material. It never reads the
    sibling EXAMINER directory and therefore cannot leak the blind rubric.
    """
    packet_dir = packet_dir.resolve()
    manifest_path = packet_dir / "CUSTOMER_PACKET_MANIFEST.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    added: list[Path] = []
    sources = packet_dir / "SOURCES"

    if incarnation == "HOMS Exam":
        added.append(_write_json(sources / "exam_scope.json", {
            "grade": 11,
            "subject": "History",
            "assessment": "Mid-Year Examination",
            "duration_minutes": 120,
            "total_marks": 150,
            "source_based_marks": 90,
            "essay_marks": 60,
            "essay_choice": 2,
            "topics": ["Nationalism in South Africa", "Apartheid, 1940s-1960s"],
            "moderation_required": True,
        }))
        added.append(_write(sources / "source_pack.md", """# Grade 11 History customer source pack

## Source A — political meeting leaflet, 1950s

A reproduced classroom extract from a political meeting leaflet argues that racial classification and pass controls were restructuring everyday citizenship and calls for organised resistance. The customer did not supply a publication date for this extract. **Do not invent one.**

## Source B — parliamentary speech extract, 1948

The speaker argues that separate development is necessary to preserve distinct communities and frames the policy as administrative order rather than coercion.

## Source C — resistance organisation statement, 1952

The statement calls for disciplined defiance of selected discriminatory laws and emphasises mass participation, non-violent protest and political organisation.

### Customer note

These are teaching extracts supplied for question construction. They are not a licence to invent provenance beyond the labels above.
"""))

    elif incarnation == "HOMS Curriculum":
        plan = sources / "annual_plan.csv"
        plan.parent.mkdir(parents=True, exist_ok=True)
        with plan.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["term", "weeks", "strand", "topic", "customer_note"])
            writer.writerows([
                [1, 6, "Geography", "Map skills", "Current allocation"],
                [1, 2, "Geography", "Settlement", "Current allocation"],
                [2, 4, "History", "Industrialisation", "Current allocation"],
                [3, 3, "History", "Industrialisation", "Repeated coverage"],
                [4, 4, "Geography", "Development", "Current allocation"],
            ])
        added.append(plan)
        added.append(_write(sources / "curriculum_requirements.md", """# Customer-supplied curriculum requirements

- History and Geography must both appear in every semester.
- The annual plan must include the required heritage topic.
- Map skills and settlement are included in the current Term 1 plan.
- The customer wants duplication and sequencing risks surfaced, not silently rewritten.
"""))

    elif incarnation == "HOMS Accreditation":
        added.append(_write(sources / "criterion_4_checklist.md", """# Accreditation Criterion 4 — customer checklist

Criterion 4 requires documented assessment governance and evidence that the approved assessment process is actually implemented. The customer asks DIO to prepare a readiness pack only. Accreditation decisions and signatory attestations remain outside DIO authority.
"""))
        staff = sources / "staff_records.csv"
        with staff.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["staff_id", "cv_current", "professional_registration", "registration_state"])
            writer.writerow(["FAC-001", "yes", "PR-101", "current"])
            writer.writerow(["FAC-002", "yes", "PR-102", "current"])
            writer.writerow(["FAC-003", "yes", "PR-103", "expired"])
        added.append(staff)

    elif incarnation == "DossierOps":
        added.append(_write(sources / "agreement_extract.md", """# Signed agreement extract supplied by customer

Agreement date: 3 February 2026. The signed agreement is authoritative only for the terms contained in the signed record. A later amendment dated 18 April 2026 is supplied as an **unsigned draft**.
"""))
        index = sources / "case_file_index.csv"
        with index.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["item", "record_type", "state"])
            writer.writerow(["Agreement", "contract", "signed"])
            writer.writerow(["Amendment 18 April", "amendment", "unsigned_draft"])
            writer.writerow(["Payment schedule", "spreadsheet", "customer_supplied"])
            writer.writerow(["Agreement-in-principle email", "correspondence", "customer_supplied"])
        added.append(index)

    elif incarnation == "Accessible Publish":
        added.append(_write(sources / "accessibility_issue_log.md", """# Customer accessibility issue log

- Figures 4, 7 and 11 currently have no alternative-text descriptions.
- Heading hierarchy skips from H2 to H4 in two sections.
- One status table uses colour alone to distinguish two states.
- The customer requests preparation and QA, not formal WCAG or PDF/UA certification.
"""))

    if not added:
        return manifest

    by_path = {str(row.get("path") or ""): row for row in manifest.get("files") or []}
    for path in added:
        relative = str(path.relative_to(packet_dir))
        by_path[relative] = {"path": relative, "sha256": _sha(path), "bytes": path.stat().st_size}
    manifest["files"] = [by_path[key] for key in sorted(by_path)]
    manifest["product_shaped_enrichment"] = True
    manifest["enriched_file_count"] = len(added)
    manifest["packet_fingerprint"] = _fingerprint(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


__all__ = ["enrich_customer_packet"]
