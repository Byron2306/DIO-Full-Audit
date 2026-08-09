#!/usr/bin/env python3
"""Live Hugging Face NLI/semantic support proof for Sophia.

The suite validates the optional remote support path that can populate
entailment_status/entailment_score in Writing Desk ledger records.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "arda_os"))

from backend.services.huggingface_evidence import get_huggingface_evidence_client  # noqa: E402


def _row(case_id: str, claim: str, evidence: str, accepted: set[str], result: Dict[str, Any]) -> Dict[str, Any]:
    status = str(result.get("entailment_status") or "")
    return {
        "case_id": case_id,
        "claim": claim,
        "evidence_span": evidence,
        "accepted_statuses": sorted(accepted),
        "entailment_status": status,
        "entailment_score": result.get("entailment_score"),
        "semantic_similarity": result.get("semantic_similarity"),
        "support_model": result.get("support_model"),
        "similarity_model": result.get("similarity_model"),
        "available": bool(result.get("available")),
        "passed": bool(result.get("available")) and status in accepted,
        "error": result.get("error") or "",
    }


def run_suite(timeout_seconds: int) -> Dict[str, Any]:
    client = get_huggingface_evidence_client(timeout_seconds=timeout_seconds)
    cases = [
        {
            "case_id": "direct_support_agency",
            "claim": "Human agency requires meaningful human choice, responsibility, and visible provenance.",
            "evidence": "Agency requires meaningful human choice, responsibility, and visible provenance.",
            "accepted": {"entails", "partial_support"},
        },
        {
            "case_id": "irrelevant_source_rejected",
            "claim": "Universities should evaluate AI systems for authorship-preserving governance.",
            "evidence": "Cancer statistics estimate new cancer cases and deaths in the United States.",
            "accepted": {"does_not_support", "contradiction"},
        },
        {
            "case_id": "overclaim_not_supported",
            "claim": "A prototype protocol proves classroom learning outcomes at institutional scale.",
            "evidence": "These protocol results do not establish improved learning outcomes or institutional scalability.",
            "accepted": {"contradiction", "does_not_support"},
        },
    ]
    rows: List[Dict[str, Any]] = []
    for case in cases:
        result = client.classify_support(case["claim"], case["evidence"])
        rows.append(_row(case["case_id"], case["claim"], case["evidence"], case["accepted"], result))
    passed = sum(1 for row in rows if row["passed"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_hf_nli_support_suite",
        "hf_status": client.status(),
        "summary": {
            "passed": passed,
            "total": len(rows),
            "pass_rate": round(passed / len(rows), 4),
            "token_present": bool(client.status().get("token_present")),
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=35)
    parser.add_argument("--out", default="evidence/sophia_hf_nli_support_latest.json")
    args = parser.parse_args()
    artifact = run_suite(timeout_seconds=args.timeout_seconds)
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passed"] == artifact["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
