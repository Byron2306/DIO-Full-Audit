#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "evidence" / "academic_integrity_gauntlet"
FIXTURE_DIR = PROJECT_ROOT / "evidence" / "academic_integrity_gauntlet_fixtures"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _post_json(url: str, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fixture_payload() -> dict:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    source = FIXTURE_DIR / "canopy_source.txt"
    source.write_text(
        "The city archives report notes that neighborhood tree canopy coverage increased "
        "from 18 percent to 24 percent between 2019 and 2024.\n\n"
        "It attributes the change to a mix of municipal planting grants, volunteer "
        "stewardship groups, and a rule requiring replacement plantings after major street repairs.\n\n"
        "The report also says summer surface temperatures were lower on blocks with denser canopy, "
        "but it does not claim that tree planting alone solved all local heat risks.\n",
        encoding="utf-8",
    )
    student_text = (
        "Tree planting fixed local heat risk in the city because the canopy grew from 18 percent "
        "to 24 percent between 2019 and 2024. The source shows that the city solved the problem "
        "through planting grants and volunteer stewardship. This proves that the replacement "
        "planting rule caused lower summer surface temperatures everywhere."
    )
    return {
        "student_text": student_text,
        "assignment_prompt": "Write a source-grounded paragraph about whether canopy policy reduced local heat risk.",
        "policy_context": (
            "Use of AI is permitted for feedback and source checking, but students must preserve authorship, "
            "declare assistance, cite sources, and may not submit AI-written prose as their own."
        ),
        "document_uploads": [
            {
                "source_name": source.name,
                "mime_type": "text/plain",
                "content_base64": base64.b64encode(source.read_bytes()).decode("ascii"),
            }
        ],
        "document_evidence_task": "academic_integrity_policy_proof",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:7070")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    payload = _fixture_payload()
    result = _post_json(f"{args.base_url}/api/academic-integrity-gauntlet", payload)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"ultimate_proof_gauntlet_{_utc_stamp()}.json"
    out.write_text(json.dumps({"payload": payload, "result": result}, indent=2), encoding="utf-8")

    summary = {
        "artifact": str(out),
        "verdict": result.get("verdict"),
        "mandos_passed": (result.get("mandos_judgment") or {}).get("passed"),
        "plagiarism_risk": (result.get("integrity_report") or {}).get("risk_level"),
        "ai_detector_verdict": ((result.get("integrity_report") or {}).get("ai_detection") or {}).get("verdict"),
        "file_count": (result.get("file_inspection") or {}).get("document_count"),
        "quality_feedback_items": len(((result.get("quality_assistance") or {}).get("sentence_level_feedback") or [])),
        "pitfall_count": (result.get("pitfall_report") or {}).get("pitfall_count"),
        "highest_pitfall_severity": (result.get("pitfall_report") or {}).get("highest_severity"),
        "telemetry_events": (result.get("telemetry_chain") or {}).get("event_count"),
        "telemetry_head_hash": (result.get("telemetry_chain") or {}).get("head_hash"),
        "complexity_level": (result.get("complexity_ladder") or {}).get("current_level"),
        "recommended_office": (result.get("prompt_approach") or {}).get("recommended_office"),
        "ipsative_score": (result.get("ipsative_assessment") or {}).get("current_gauntlet_score"),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        raise
