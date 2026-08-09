#!/usr/bin/env python3
"""Phase 1 smoke suite for Sophia Writing Desk.

This is intentionally focused on routing and response-contract reliability:
no stale full-document review fallback, no random source-scout routing, no
generic greeting, and structured claim typing for selected passages.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SmokeCase:
    family: str
    text: str
    expected_any_claim_type: tuple[str, ...]


ABSTRACTS = [
    "Higher-education responses to generative artificial intelligence remain dominated by disclosure, detection, assessment redesign, and post hoc enforcement. These measures are necessary but incomplete because they govern the human-AI relationship primarily from outside the system.",
    "This conceptual and design-based paper develops an alternative model in which integrity obligations are expressed as inspectable constitutional rules and translated into mediation rather than substitution.",
    "The paper argues that authorship-preserving AI behavior can be made explicit, testable, auditable, and iteratively repairable.",
    "Evidence includes logged encounters, kernel traces, and frozen protocol artifacts, but does not establish classroom learning outcomes or institutional scalability.",
    "The contribution is an encounter-ethics model for evaluating whether AI systems preserve human agency while remaining educationally useful.",
    "The study positions disclosure policies as necessary but insufficient safeguards for sustained human-AI academic collaboration.",
    "A constitutional writing assistant should scaffold learner judgment rather than produce substitute academic prose.",
    "The proposed architecture binds AI assistance to provenance, source visibility, audit trails, and reflective revision.",
    "The abstract claims a shift from tool-ethics to governed encounter-ethics in higher education.",
    "The paper frames academic integrity as a design problem as well as a compliance problem.",
]

INTRODUCTION = [
    "Universities increasingly ask whether AI was used, whether that use was disclosed, and whether assessment design can reduce misuse.",
    "This framing correctly preserves human responsibility, but it has limited vocabulary for lawful collaboration inside the AI encounter.",
    "The paper begins from a practical integrity dispute and uses it as a motivating case rather than a complete empirical foundation.",
    "Human agency is defined here as preserved judgment, revision control, and accountable authorship during AI-supported work.",
    "The central problem is not whether tools are allowed, but whether the relation between learner and tool can be governed and inspected.",
    "Current policy language often focuses on detection and sanction after the disputed act has already occurred.",
    "The introduction should separate the motivating narrative from the model's evidentiary claims.",
    "A reader needs to know which terms are metaphorical, architectural, pedagogical, and evaluative.",
    "The argument depends on distinguishing mediation from substitution.",
    "The opening claim requires recent institutional and scholarly support.",
]

METHODS = [
    "This is a conceptual and design-based paper using protocol artifacts, logged encounters, and architecture traces as system evidence.",
    "The evaluation cases were frozen before intervention so post-fix improvements can be interpreted causally.",
    "Mutation and ablation conditions test whether governance survives lexical, semantic, and adversarial prompt variation.",
    "Provider comparisons include local and remote model lanes under the same scoring contract.",
    "The method does not measure student learning outcomes, retention, or classroom transfer.",
    "The evidence ledger records raw, repaired, and released responses separately.",
    "The assessment ecology distinguishes baseline, diagnostic, formative, criterion, reflective, and ipsative layers.",
    "A judge panel should evaluate both refusal correctness and usefulness of lawful assistance.",
    "OCR uncertainty is recorded when multimodal evidence is incomplete or degraded.",
    "Source support is treated as unavailable unless exact spans are retrieved or uploaded.",
]

DISCUSSION = [
    "The findings suggest that integrity-preserving behavior can be specified and tested, but not that the system is universally reliable.",
    "A zero false-release rate in denial-family cases would strengthen the claim that constitutional governance changes release behavior.",
    "False holds remain important because over-refusal can damage lawful pedagogy and learner agency.",
    "The system's value depends on preserving authorship while still offering substantial academic assistance.",
    "Protocol success should be framed as architectural evidence rather than proof of institutional adoption.",
    "Future work should compare Sophia-supported revision with ordinary chatbot assistance and unaided revision.",
    "The discussion should avoid converting benchmark performance into direct learning-outcome claims.",
    "The model's strongest contribution is making integrity obligations inspectable before, during, and after assistance.",
    "Reviewer objections will likely focus on evidence independence, source quality, and generalizability.",
    "The conclusion should keep scope limits visible while arguing for a new evaluation vocabulary.",
]

AMBIGUOUS = [
    "Is this strong enough?",
    "What is wrong with this claim?",
    "Can I say it this way?",
    "Does this need a citation?",
    "Make this more rigorous without writing it for me.",
    "Where is the weak point?",
    "Is my method claim overreaching?",
    "Should I define agency here?",
    "What would a reviewer attack?",
    "Help me improve this paragraph lawfully.",
]


def build_cases() -> list[SmokeCase]:
    cases: list[SmokeCase] = []
    for family, samples, expected in [
        ("abstract", ABSTRACTS, ("field/context claim", "gap/critique claim", "contribution/design claim", "mechanism/architecture claim", "scope/limitation claim", "argument claim")),
        ("introduction", INTRODUCTION, ("field/context claim", "gap/critique claim", "contribution/design claim", "argument claim")),
        ("method", METHODS, ("contribution/design claim", "mechanism/architecture claim", "scope/limitation claim", "gap/critique claim", "argument claim")),
        ("discussion", DISCUSSION, ("scope/limitation claim", "gap/critique claim", "contribution/design claim", "argument claim")),
        ("ambiguous", AMBIGUOUS, ("argument claim", "field/context claim", "gap/critique claim")),
    ]:
        for sample in samples:
            cases.append(SmokeCase(family, sample, expected))
    return cases


def post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_suite(base_url: str, timeout: float) -> dict:
    health = get_json(f"{base_url}/api/health", timeout)
    token = health.get("session_token") or ""
    cases = build_cases()
    rows = []
    for idx, case in enumerate(cases, start=1):
        prompt = (
            f"Writing Desk task: ask. Active draft lines {idx}-{idx}. "
            "Evaluate only the selected/current passage. "
            f'Selected passage: """{case.text}"""'
        )
        payload = {
            "text": prompt,
            "session_token": token,
            "reasoned_integrity_lane": True,
            "reasoned_provider": "gemini",
            "reasoned_model": "gemini-flash-lite-latest",
            "document_evidence_task": "live_writing_desk",
            "client_context": {
                "ui_surface": "writing_desk",
                "writing_action": "ask",
                "response_mode": "compact",
                "selected_lines": [idx, idx],
            },
            "document_uploads": [{
                "source_name": "Phase 1 Smoke Draft",
                "mime_type": "text/markdown",
                "extracted_text": case.text,
                "spans": [{"label": f"line_{idx}", "quote": case.text}],
                "uncertainty_notes": ["phase1_smoke_suite"],
            }],
        }
        started = time.time()
        try:
            data = post_json(f"{base_url}/api/speak", payload, timeout)
            elapsed_ms = round((time.time() - started) * 1000, 2)
            response = data.get("response") or ""
            wd = data.get("writing_desk") or {}
            claim_types = [claim.get("claim_type") for claim in wd.get("claim_map") or []]
            row = {
                "case_id": idx,
                "family": case.family,
                "source": data.get("source"),
                "elapsed_ms": elapsed_ms,
                "structured_present": bool(wd),
                "annotations": len(wd.get("annotations") or []),
                "claim_types": claim_types,
                "generic_greeting": response.lower().startswith("hello! i am sophia") or "what would you like to work on today" in response.lower(),
                "source_scout_misroute": data.get("source") == "academic_source_scout",
                "review_misroute": data.get("source") == "document_review_feedback",
                "claim_type_match": any(claim in case.expected_any_claim_type for claim in claim_types),
            }
        except Exception as exc:  # noqa: BLE001 - smoke suite reports all failures.
            row = {
                "case_id": idx,
                "family": case.family,
                "error": str(exc),
                "structured_present": False,
                "annotations": 0,
                "claim_types": [],
                "generic_greeting": False,
                "source_scout_misroute": False,
                "review_misroute": False,
                "claim_type_match": False,
            }
        rows.append(row)
    summary = {
        "total": len(rows),
        "structured": sum(1 for row in rows if row.get("structured_present")),
        "source_scout_misroutes": sum(1 for row in rows if row.get("source_scout_misroute")),
        "review_misroutes": sum(1 for row in rows if row.get("review_misroute")),
        "generic_greetings": sum(1 for row in rows if row.get("generic_greeting")),
        "claim_type_matches": sum(1 for row in rows if row.get("claim_type_match")),
        "errors": sum(1 for row in rows if row.get("error")),
    }
    summary["claim_type_match_rate"] = round(summary["claim_type_matches"] / max(1, summary["total"]), 4)
    summary["passes_phase1_gate"] = (
        summary["total"] == 50
        and summary["source_scout_misroutes"] == 0
        and summary["review_misroutes"] == 0
        and summary["generic_greetings"] == 0
        and summary["errors"] == 0
        and summary["claim_type_match_rate"] >= 0.85
    )
    return {
        "suite": "sophia_writing_desk_phase1_smoke",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": base_url,
        "summary": summary,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:7070")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    artifact = run_suite(args.base_url.rstrip("/"), args.timeout)
    rendered = json.dumps(artifact, indent=2)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if artifact["summary"]["passes_phase1_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
