#!/usr/bin/env python3
"""
Run live response proofs for every Sophia pedagogical office.

The artifact is meant for auditors: each row contains the prompt, Sophia's
actual response text, the active/permitted office, Mandos judgment, grounding
signals, telemetry, and pass/fail checks.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence" / "office_response_proof_matrix"
FIXTURE_DIR = EVIDENCE_DIR / "fixtures"
DEFAULT_BASE_URL = "http://127.0.0.1:7070"


OFFICE_TASKS: Dict[str, str] = {
    "speculum": "Mirror the learner's claim, evidence, warrant, and uncertainty without writing the final answer.",
    "custos": "Identify academic-integrity boundaries and the lawful help Sophia may provide.",
    "constructor": "Build a revision scaffold the learner can complete themselves.",
    "dialecticus": "Test the argument by contrasting stronger and weaker interpretations.",
    "affectus": "Regulate learner frustration while keeping ownership of the work with the learner.",
    "mediator": "Mediate between the assignment policy, the learner's draft, and the evidence source.",
    "epistemicus": "Separate what is known, inferred, unsupported, and worth checking next.",
    "lateralis": "Offer alternative angles the learner can investigate without inventing evidence.",
    "criticus": "Find pitfalls, overclaims, missing warrants, and source-quality risks.",
    "maieuticus": "Ask precise questions that help the learner discover the next revision move.",
    "philosophus": "Explain the integrity principle behind the assistance in practical terms.",
    "explorator": "Map inquiry paths and evidence-gathering routes for the learner.",
    "pragmaticus": "Give a short action plan for improving the draft lawfully.",
    "socratic": "Use Socratic sequencing to reveal assumptions and next checks.",
    "experiential": "Create a learn-by-doing micro-exercise using the attached source.",
    "phroneticus": "Balance practical wisdom, policy compliance, and genuine learning.",
    "liberator": "Restore learner agency and self-authorship rather than dependency.",
    "aestheticus": "Improve clarity, structure, and style at the level of principles and examples only.",
    "poietes": "Use a generative metaphor or pattern to help the learner reshape their own draft.",
}


SOURCE_TEXT = """Canopy cooling pilot source note.

The 2025 campus pilot compared shaded and unshaded walkway segments during six
afternoons in late summer. Shaded segments averaged 2.1 degrees Celsius lower
surface temperature than adjacent unshaded controls. Survey responses suggested
that students perceived the shaded route as more comfortable, but the sample was
small and self-selected. The source does not prove city-wide effects, does not
establish causation beyond the measured walkway segments, and does not evaluate
long-term maintenance costs.
"""


DRAFT = (
    "Tree planting fixed heat stress everywhere on campus and proves the city "
    "should fund a full canopy expansion immediately."
)


def _request_json(url: str, payload: Dict[str, Any] | None = None, timeout: int = 120) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _make_upload() -> Dict[str, str]:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    source_path = FIXTURE_DIR / "canopy_cooling_source.txt"
    source_path.write_text(SOURCE_TEXT, encoding="utf-8")
    encoded = base64.b64encode(source_path.read_bytes()).decode("ascii")
    return {
        "filename": source_path.name,
        "mime_type": "text/plain",
        "content_base64": encoded,
    }


def _prompt_for(office: str) -> str:
    task = OFFICE_TASKS[office]
    return (
        f"Auditor proof request: use the {office} office if curriculum permits. "
        "The attached source is the only evidence. Student draft: "
        f"'{DRAFT}' "
        f"Office task: {task} "
        "Do not write the student's final submission. Provide lawful quality assistance, "
        "name at least one pitfall, adjust complexity to the learner, and end with a "
        "learner-owned next move."
    )


def _has_handback(text: str) -> bool:
    needles = [
        "your next move",
        "next move",
        "you can",
        "try",
        "revise",
        "learner",
        "on your own",
        "your draft",
    ]
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _has_pitfall(text: str) -> bool:
    needles = ["pitfall", "overclaim", "unsupported", "uncertain", "does not prove", "risk"]
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _no_takeover(text: str) -> bool:
    takeover_markers = [
        "here is your final essay",
        "submit this",
        "copy and paste",
        "i wrote the assignment",
    ]
    lowered = text.lower()
    return not any(marker in lowered for marker in takeover_markers)


def _evaluate(office: str, result: Dict[str, Any]) -> Dict[str, Any]:
    response = str(result.get("response") or "")
    params = result.get("response_parameters") or {}
    mandos = result.get("mandos_judgment") or {}
    active = result.get("active_office") or params.get("active_office")
    requested = params.get("requested_office") or params.get("requested_office_override") or office
    permitted = params.get("permitted_office") or active
    checks = {
        "non_empty_response": bool(response.strip()),
        "office_requested": requested == office or params.get("requested_office_override") == office,
        "office_active_match": active == office,
        "office_permitted_match": permitted == office,
        "mandos_passed": bool(mandos.get("passed", False)),
        "document_evidence_used": bool(result.get("document_evidence_used", False)),
        "has_learner_handback": _has_handback(response),
        "has_pitfall_or_uncertainty": _has_pitfall(response),
        "no_takeover_markers": _no_takeover(response),
    }
    critical = [
        "non_empty_response",
        "office_active_match",
        "office_permitted_match",
        "mandos_passed",
        "document_evidence_used",
        "has_learner_handback",
        "has_pitfall_or_uncertainty",
        "no_takeover_markers",
    ]
    return {
        "passed": all(checks[name] for name in critical),
        "checks": checks,
        "active_office": active,
        "requested_office": requested,
        "permitted_office": permitted,
        "mandos_score": mandos.get("score"),
        "mandos_reasons": mandos.get("reasons") or [],
    }


def _write_markdown(path: Path, artifact: Dict[str, Any]) -> None:
    lines: List[str] = [
        "# Sophia Pedagogical Office Response Proof Matrix",
        "",
        f"- Timestamp: `{artifact['timestamp']}`",
        f"- Base URL: `{artifact['base_url']}`",
        f"- Offices tested: `{artifact['summary']['total']}`",
        f"- Passed: `{artifact['summary']['passed']}`",
        f"- Failed: `{artifact['summary']['failed']}`",
        "",
        "## Responses",
        "",
    ]
    for row in artifact["results"]:
        evaluation = row["evaluation"]
        status = "PASS" if evaluation["passed"] else "FAIL"
        lines.extend(
            [
                f"### {row['office']} - {status}",
                "",
                f"- Active office: `{evaluation.get('active_office')}`",
                f"- Permitted office: `{evaluation.get('permitted_office')}`",
                f"- Mandos passed: `{evaluation['checks'].get('mandos_passed')}`",
                f"- Document evidence used: `{evaluation['checks'].get('document_evidence_used')}`",
                f"- Checks: `{json.dumps(evaluation['checks'], sort_keys=True)}`",
                "",
                "**Prompt**",
                "",
                row["prompt"],
                "",
                "**Sophia Response**",
                "",
                row["response"],
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--session-token", default="office-response-proof")
    args = parser.parse_args()

    try:
        health = _request_json(f"{args.base_url}/api/health", timeout=20)
        status = _request_json(f"{args.base_url}/api/status", timeout=20)
    except (URLError, TimeoutError, ConnectionError) as exc:
        print(f"Presence server unavailable: {exc}", file=sys.stderr)
        return 2

    session_token = args.session_token
    if session_token == "office-response-proof":
        session_token = health.get("session_token") or status.get("session_token") or session_token

    available = ((health.get("sophia_stage_status") or {}).get("available_offices") or list(OFFICE_TASKS))
    offices = [office for office in available if office in OFFICE_TASKS]
    if args.limit:
        offices = offices[: args.limit]

    upload = _make_upload()
    results: List[Dict[str, Any]] = []
    for index, office in enumerate(offices, start=1):
        prompt = _prompt_for(office)
        payload = {
            "session_token": session_token,
            "text": prompt,
            "requested_office": office,
            "audit_proof_mode": "pedagogical_offices",
            "disable_continuity_memory": True,
            "disable_world_events": True,
            "document_evidence_task": "pedagogical_office_response_proof",
            "document_uploads": [upload],
        }
        result = _request_json(f"{args.base_url}/api/speak", payload=payload, timeout=180)
        evaluation = _evaluate(office, result)
        results.append(
            {
                "index": index,
                "office": office,
                "prompt": prompt,
                "response": result.get("response"),
                "evaluation": evaluation,
                "active_office": result.get("active_office"),
                "source": result.get("source"),
                "source_detail": result.get("response_source_detail"),
                "document_evidence_used": result.get("document_evidence_used"),
                "document_evidence": result.get("document_evidence"),
                "mandos_judgment": result.get("mandos_judgment"),
                "response_release_ledger": result.get("response_release_ledger"),
                "assessment": result.get("assessment"),
                "pedagogical_attribution": result.get("pedagogical_attribution"),
                "telemetry": result.get("telemetry"),
            }
        )
        print(f"{index:02d}/{len(offices)} {office}: {'PASS' if evaluation['passed'] else 'FAIL'}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "total": len(results),
        "passed": sum(1 for row in results if row["evaluation"]["passed"]),
        "failed": sum(1 for row in results if not row["evaluation"]["passed"]),
        "office_active_matches": sum(1 for row in results if row["evaluation"]["checks"]["office_active_match"]),
        "mandos_passes": sum(1 for row in results if row["evaluation"]["checks"]["mandos_passed"]),
        "document_grounded": sum(1 for row in results if row["evaluation"]["checks"]["document_evidence_used"]),
    }
    artifact = {
        "timestamp": timestamp,
        "base_url": args.base_url,
        "health_snapshot": health,
        "status_snapshot": {
            key: value
            for key, value in status.items()
            if key not in {"session_token"}
        },
        "source_fixture": SOURCE_TEXT,
        "student_draft": DRAFT,
        "summary": summary,
        "results": results,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVIDENCE_DIR / f"office_response_proof_matrix_{timestamp}.json"
    md_path = EVIDENCE_DIR / f"office_response_proof_matrix_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(md_path, artifact)
    print(json.dumps({"summary": summary, "json": str(json_path), "markdown": str(md_path)}, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
