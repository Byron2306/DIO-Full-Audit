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
    The enriched files are added before Vesper attachment capture, so the native
    product later consumes the exact quarantined customer bytes.
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

## Source A — customer-supplied teaching extract on pass controls and political mobilisation, 1950s

The extract presents racial classification and pass controls as measures that reached deeply into everyday life. It argues that rules governing movement, residence and employment were not experienced as isolated administrative requirements but as connected controls that shaped where African people could live, work and travel. The writer links these controls to a broader political system in which rights were distributed unequally and opposition was increasingly organised through meetings, petitions, campaigns and collective action. The extract emphasises that resistance depended on ordinary participation as well as formal political leadership. It also suggests that repeated encounters with permits, police checks and restrictions could turn personal grievances into wider political demands. The overall message is that apartheid-era controls affected both daily experience and political mobilisation, encouraging organisations to connect specific discriminatory laws with larger questions of citizenship, rights and representation.

## Source B — customer-supplied teaching extract summarising a parliamentary defence of apartheid, 1948

The extract presents the argument of a speaker defending racial separation as a policy of order and preservation. The speaker claims that communities have different histories, interests and social institutions and argues that government should recognise those differences rather than encourage political and social integration. Separation is described as a way to reduce conflict, protect distinct identities and organise administration according to established racial categories. The speaker rejects the view that a single common political system would necessarily produce equality or stability and instead presents separate development as a practical response to South Africa's diversity. The language of the extract places emphasis on administration, community difference and political control while giving little attention to the unequal distribution of rights, land, economic opportunity or political power that opponents of apartheid identified as central consequences of the policy.

## Source C — customer-supplied teaching extract on organised defiance, 1952

The extract argues that opposition to discriminatory laws should be disciplined, organised and visible. It presents non-violent defiance as a way for large numbers of ordinary people to challenge selected laws publicly while demonstrating that resistance could extend beyond speeches and petitions. Participants are urged to act collectively, accept the risks attached to deliberate civil disobedience and avoid actions that would weaken the campaign's political purpose. The extract emphasises mass participation and coordination, suggesting that campaigns could build solidarity across communities and increase pressure on the state by exposing the practical operation of discriminatory legislation. At the same time, it presents organisation and political education as essential because isolated acts of protest would have less impact than coordinated action. The message links resistance to broader demands for political rights and portrays disciplined participation as both a protest method and a means of developing a wider movement.

### Customer note — provenance controls

- These are customer-supplied classroom teaching extracts for controlled assessment construction. They are not presented as verbatim authenticated quotations from named historical figures.
- The customer did not supply an author or publication date for Source A. Do not invent either.
- Do not invent authors, publication titles, additional dates, quotations, captions or source authority beyond the labels above.
- Provenance limitations must remain visible to the educator during review and may not be silently converted into stronger historical authority.
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

    elif incarnation == "VAMP Performance":
        objectives = sources / "performance_objectives_v2.csv"
        with objectives.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["objective_id", "domain", "objective", "minimum_evidence", "review_start", "review_end"])
            writer.writerow(["KPA1", "RESEARCH", "Demonstrate two research outputs in the review period", 2, "2026-01-01", "2026-06-30"])
            writer.writerow(["KPA3", "TEACHING", "Provide evidence of module coordination during the review period", 2, "2026-01-01", "2026-06-30"])
            writer.writerow(["KPA5", "ENGAGEMENT", "Provide evidence of substantive community engagement activity", 1, "2026-01-01", "2026-06-30"])
        added.append(objectives)
        added.append(_write(sources / "research_article_acceptance.txt", """Research evidence record RES-01
Status: accepted
Date: 2026-05-15
Review period: January-June 2026
Record: Journal acceptance notice for one research article.
Evidence role: supports KPA1 research-output objective.
"""))
        added.append(_write(sources / "submitted_manuscript_record.txt", """Research evidence record RES-02
Status: submitted, not accepted
Date: 2026-06-20
Review period: January-June 2026
Record: Manuscript submission confirmation.
Evidence role: candidate support for KPA1; submission must not be represented as publication or acceptance.
"""))
        added.append(_write(sources / "module_coordination_appointment.txt", """Teaching evidence record TEACH-01
Appointment: module coordinator
Period: January-June 2026
Record: appointment letter confirms coordination responsibility for the review period.
Evidence role: supports KPA3 module-coordination objective.
"""))
        timetable = sources / "module_timetable.csv"
        with timetable.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["module", "role", "week", "scheduled_activity"])
            writer.writerow(["HIST-211", "module coordinator", 3, "lecture and tutorial coordination"])
            writer.writerow(["HIST-211", "module coordinator", 7, "assessment coordination"])
            writer.writerow(["HIST-211", "module coordinator", 11, "moderation logistics"])
        added.append(timetable)
        added.append(_write(sources / "community_engagement_planning_email.txt", """Subject: Community workshop planning
Date: not supplied
The sender discusses a proposed community workshop and asks colleagues to confirm a venue and participant list.
Evidence role: weak planning evidence for KPA5 only. It does not establish that the engagement activity actually occurred.
"""))
        added.append(_write(sources / "congratulatory_context_email.txt", """Subject: Congratulations
Date: 2026-06-28
The sender describes the staff member as 'outstanding' and thanks them for their contribution this semester.
Evidence role: contextual correspondence only. It is not an authorised performance rating, employment decision, or rubric-based assessment.
"""))

    elif incarnation == "Evidex EvidenceOps":
        claims = sources / "claims_register.csv"
        with claims.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["claim_id", "claim", "claimed_value", "customer_status"])
            writer.writerow(["C1", "Community workshops delivered", 14, "draft narrative claim"])
        added.append(claims)
        attendance = sources / "monitoring_workshops.csv"
        with attendance.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["workshop_id", "attendance_sheet_present", "event_date", "workstream"])
            for index in range(1, 13):
                writer.writerow([f"WS-{index:02d}", "yes", f"2026-{((index - 1) % 6) + 1:02d}-{10 + ((index - 1) % 12):02d}", f"W{((index - 1) % 3) + 1}"])
        added.append(attendance)
        added.append(_write(sources / "narrative_draft.md", """# Draft donor narrative supplied by customer

The current narrative states that **14 community workshops were delivered** during the reporting period. The reporting lead has asked for this claim to be tested against the evidence folder before any donor submission.

The narrative is a claim source, not proof that all 14 workshops occurred.
"""))
        added.append(_write(sources / "workstream_email_summary.txt", """Subject: Workstream workshop summary

The email summary says that two additional workshops took place beyond the twelve workshops represented in the monitoring attendance sheets. No attendance sheets or event reports for those two additional workshops are attached to this customer folder.
"""))
        added.append(_write(sources / "invoice_INV-118.txt", """Invoice: INV-118
Purpose: venue costs
Coverage stated by invoice: four community workshops
Customer note: the invoice supports venue expenditure for four workshops but is not, on its own, attendance evidence for fourteen workshops.
"""))
        photo_meta = sources / "photo_metadata.csv"
        with photo_meta.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["filename", "date", "event_identifier", "customer_note"])
            writer.writerow(["IMG_1042.jpg", "", "", "photograph supplied without date or event identifier"])
            writer.writerow(["IMG_1088.jpg", "", "", "photograph supplied without date or event identifier"])
            writer.writerow(["IMG_1113.jpg", "", "", "photograph supplied without date or event identifier"])
        added.append(photo_meta)
        added.append(_write(sources / "reporting_folder_readme.md", """# Reporting folder note

This folder deliberately contains conflicting and incomplete support. The draft says 14 workshops; attendance sheets support 12; an email mentions two more; INV-118 covers venue costs for four; three photographs lack dates and event identifiers. Preserve the contradiction and provenance gaps for human review.
"""))

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
