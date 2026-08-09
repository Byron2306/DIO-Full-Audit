#!/usr/bin/env python3
"""Validate Sophia Phase 4 project-store behavior."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
ARDA_ROOT = ROOT / "arda_os"
if str(ARDA_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_ROOT))

from backend.services.sophia_project_store import SophiaProjectStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase4_project_store_latest.json")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        store = SophiaProjectStore(Path(tmp) / "sophia_project_store")
        fides = store.derive_project_identity(
            session_token="session-a",
            document_name="Fides_et_Speculum.pdf",
            document_hash="hash-fides",
            draft_text="Human agency is preserved when the system scaffolds rather than substitutes.",
        )
        gospel = store.derive_project_identity(
            session_token="session-a",
            document_name="Gospel_of_Seraph.pdf",
            document_hash="hash-gospel",
            draft_text="The dossier maps prevention telemetry to adversarial runtime evidence.",
        )
        store.upsert_project(project_id=fides["project_id"], session_token="session-a", document_name="Fides_et_Speculum.pdf", document_hash="hash-fides")
        store.upsert_project(project_id=gospel["project_id"], session_token="session-a", document_name="Gospel_of_Seraph.pdf", document_hash="hash-gospel")
        fides_version = store.add_draft_version(
            project_id=fides["project_id"],
            draft_text="Human agency is preserved when the system scaffolds rather than substitutes.",
            line_start=16,
            line_end=34,
        )
        gospel_version = store.add_draft_version(
            project_id=gospel["project_id"],
            draft_text="The dossier maps prevention telemetry to adversarial runtime evidence.",
            line_start=4,
            line_end=8,
        )
        write = store.append_claim_records(
            project_id=fides["project_id"],
            draft_version_id=fides_version["version_id"],
            records=[
                {
                    "claim": "Human agency is preserved when the system scaffolds rather than substitutes.",
                    "source_name": "UNESCO AI competency framework",
                    "exact_span": "AI systems should support human agency and critical thinking.",
                    "warrant": "The source supplies the policy principle; the paper must operationalize the mechanism.",
                    "limitation": "This is a policy anchor, not proof of learning outcomes.",
                    "status": "partial",
                    "line_start": 16,
                    "line_end": 34,
                }
            ],
        )
        source_pool_write = store.append_source_records(
            project_id=fides["project_id"],
            sources=[
                {
                    "name": "UNESCO AI competency framework",
                    "text": "AI systems should support human agency and critical thinking.",
                    "category": "policy_source",
                }
            ],
        )
        retrieved_write = store.append_retrieved_sources(
            project_id=fides["project_id"],
            sources=[
                {
                    "title": "Human agency in AI-mediated higher education",
                    "url": "https://example.org/agency-ai-higher-ed",
                    "year": 2026,
                    "summary": "A source lead for defining human agency in AI learning contexts.",
                    "source": "test_retrieval",
                }
            ],
        )
        fides_summary = store.summarize_project(fides["project_id"])
        gospel_summary = store.summarize_project(gospel["project_id"])
        contamination = store.contamination_report([fides["project_id"], gospel["project_id"]])

        checks = [
            {
                "check": "project_ids_separate_documents",
                "passed": fides["project_id"] != gospel["project_id"],
            },
            {
                "check": "draft_versions_linked",
                "passed": fides_version["version_id"].startswith("draft-") and gospel_version["version_id"].startswith("draft-"),
            },
            {
                "check": "claim_record_written",
                "passed": write["appended"] == 1 and fides_summary["claim_records"] == 1,
            },
            {
                "check": "no_cross_project_contamination",
                "passed": gospel_summary["claim_records"] == 0,
            },
            {
                "check": "dashboard_counts_present",
                "passed": (
                    fides_summary["weak_warrants"] == 1
                    and "partial" in fides_summary["status_counts"]
                    and fides_summary["source_pool_records"] == 1
                    and fides_summary["retrieved_sources"] == 1
                ),
            },
            {
                "check": "source_pool_written_without_claiming_support",
                "passed": source_pool_write["appended"] == 1 and fides_summary["source_pool_records"] == 1,
            },
            {
                "check": "retrieved_leads_written_as_unmapped",
                "passed": retrieved_write["appended"] == 1 and fides_summary["retrieved_sources"] == 1,
            },
            {
                "check": "contamination_report_clean",
                "passed": contamination["passed"] is True and contamination["contamination_signals"] == 0,
            },
        ]

    passed = sum(1 for row in checks if row["passed"])
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase4_project_store",
        "summary": {
            "passed": passed,
            "total": len(checks),
            "pass_rate": round(passed / len(checks), 4),
        },
        "checks": checks,
        "diagnostics": {
            "fides_project_id": fides["project_id"],
            "gospel_project_id": gospel["project_id"],
            "fides_summary": fides_summary,
            "gospel_summary": gospel_summary,
            "contamination": contamination,
        },
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
