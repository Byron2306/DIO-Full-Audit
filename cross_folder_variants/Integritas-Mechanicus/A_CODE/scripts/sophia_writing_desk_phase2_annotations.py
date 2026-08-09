#!/usr/bin/env python3
"""Phase 2 annotation suite for Sophia Writing Desk."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnnotationCase:
    case_id: str
    family: str
    text: str
    expected_labels: tuple[str, ...]


CASES = [
    AnnotationCase("p01", "provenance", "Higher-education responses to generative AI remain dominated by disclosure, detection, assessment redesign, and post hoc enforcement.", ("NEEDS SOURCE",)),
    AnnotationCase("p02", "provenance", "These measures are necessary but incomplete because they govern the human-AI relationship primarily from outside the system.", ("NEEDS WARRANT",)),
    AnnotationCase("p03", "provenance", "Integrity obligations are expressed as inspectable constitutional rules enforced through deterministic and probabilistic layers.", ("OPERATIONAL DEFINITION",)),
    AnnotationCase("p04", "provenance", "This important model improves learner agency in meaningful ways.", ("DEFINE TERM",)),
    AnnotationCase("p05", "provenance", "Current policy language focuses on detection and sanction after the disputed act.", ("NEEDS SOURCE",)),
    AnnotationCase("o01", "overclaim", "This protocol proves that institutional AI integrity can be solved across all universities.", ("OVERCLAIM", "SCOPE LIMIT")),
    AnnotationCase("o02", "overclaim", "The system guarantees that every learner will preserve authorship.", ("OVERCLAIM", "SCOPE LIMIT")),
    AnnotationCase("o03", "overclaim", "The matrix demonstrates universal reliability under all adversarial conditions.", ("OVERCLAIM", "SCOPE LIMIT")),
    AnnotationCase("o04", "overclaim", "Sophia eliminates plagiarism risk entirely.", ("SCOPE LIMIT",)),
    AnnotationCase("o05", "overclaim", "These results establish complete classroom effectiveness.", ("OVERCLAIM", "SCOPE LIMIT")),
    AnnotationCase("m01", "method", "The study evaluates learner outcomes.", ("METHOD DETAIL",)),
    AnnotationCase("m02", "method", "The protocol evaluation shows improvement but does not name the corpus or scoring criteria.", ("METHOD DETAIL",)),
    AnnotationCase("m03", "method", "This conceptual and design-based paper develops an alternative model.", ("METHOD CLARITY",)),
    AnnotationCase("m04", "method", "The evaluation uses a dataset.", ("METHOD DETAIL",)),
    AnnotationCase("m05", "method", "The judge panel evaluates refusal correctness and usefulness.", ("METHOD DETAIL",)),
    AnnotationCase("s01", "similarity", "This paragraph is adapted from a source and closely follows its wording.", ("SIMILARITY RISK",)),
    AnnotationCase("s02", "similarity", "The definition mirrors the source formulation but changes several terms.", ("SIMILARITY RISK",)),
    AnnotationCase("s03", "similarity", "The argument is based on Smith's framework without a visible citation.", ("SIMILARITY RISK",)),
    AnnotationCase("s04", "similarity", "This section uses the same structure as the source article.", ("SIMILARITY RISK",)),
    AnnotationCase("s05", "similarity", "The claim is drawn from the policy report.", ("SIMILARITY RISK",)),
    AnnotationCase("l01", "list_table", "- Claim: Sophia preserves authorship\n- Evidence: protocol logs\n- Limitation: no classroom outcomes", ("STRONG CLAIM",)),
    AnnotationCase("l02", "list_table", "Level | What it shows | What it does not claim\n1 | Protocol pass | Learning outcomes", ("REVISION READY",)),
    AnnotationCase("l03", "list_table", "Claim: The architecture is robust\nEvidence: tests\nWarrant: not stated", ("DEFINE TERM",)),
    AnnotationCase("l04", "list_table", "1. The system proves all institutions can adopt this model\n2. The evidence is complete", ("OVERCLAIM", "SCOPE LIMIT")),
    AnnotationCase("l05", "list_table", "Source need: current policy literature\nClaim: disclosure is insufficient", ("NEEDS SOURCE",)),
    AnnotationCase("c01", "clarity", "The model is robust, useful, meaningful, and significant for academic integrity.", ("DEFINE TERM",)),
    AnnotationCase("c02", "clarity", "The paper develops a conceptual model that translates integrity into constitutional rules, probabilistic checks, pedagogical mediation, and source-governed repair while preserving authorship across contexts.", ("METHOD CLARITY",)),
    AnnotationCase("c03", "clarity", "This is a strong contribution.", ("DEFINE TERM",)),
    AnnotationCase("c04", "clarity", "The system is world-class because it works.", ("SCOPE LIMIT", "DEFINE TERM")),
    AnnotationCase("c05", "clarity", "Authorship-preserving mediation helps learners revise their own claims with evidence and limitation.", ("STRONG CLAIM",)),
]


def post_json(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_token(base_url: str, timeout: float) -> str:
    with urllib.request.urlopen(f"{base_url}/api/health", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")).get("session_token") or ""


def run_suite(base_url: str, timeout: float) -> dict:
    token = get_token(base_url, timeout)
    rows = []
    for idx, case in enumerate(CASES, start=1):
        payload = {
            "text": (
                f"Writing Desk task: integrity. Active draft lines {idx}-{idx}. "
                f'Evaluate only the selected/current passage. Selected passage: """{case.text}"""'
            ),
            "session_token": token,
            "reasoned_integrity_lane": True,
            "reasoned_provider": "gemini",
            "reasoned_model": "gemini-flash-lite-latest",
            "document_evidence_task": "live_writing_desk",
            "client_context": {
                "ui_surface": "writing_desk",
                "writing_action": "integrity",
                "response_mode": "compact",
                "selected_lines": [idx, idx],
            },
            "document_uploads": [{
                "source_name": "Phase 2 Annotation Draft",
                "mime_type": "text/markdown",
                "extracted_text": case.text,
                "spans": [{"label": f"line_{idx}", "quote": case.text}],
                "uncertainty_notes": ["phase2_annotation_suite"],
            }],
        }
        started = time.time()
        try:
            data = post_json(f"{base_url}/api/speak", payload, timeout)
            wd = data.get("writing_desk") or {}
            annotations = wd.get("annotations") or []
            labels = {str(annotation.get("label") or "") for annotation in annotations}
            categories = {str(annotation.get("category") or "") for annotation in annotations}
            matched = all(label in labels for label in case.expected_labels)
            response_lower = (data.get("response") or "").lower()
            plagiarism_accusation = (
                ("you plagiarized" in response_lower or "this is plagiarism" in response_lower)
                and "SIMILARITY RISK" not in labels
            )
            row = {
                "case_id": case.case_id,
                "family": case.family,
                "source": data.get("source"),
                "elapsed_ms": round((time.time() - started) * 1000, 2),
                "expected_labels": list(case.expected_labels),
                "labels": sorted(labels),
                "categories": sorted(categories),
                "line_ranges_present": all("line_start" in annotation and "line_end" in annotation for annotation in annotations),
                "matched": matched,
                "plagiarism_accusation_without_similarity": plagiarism_accusation,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            row = {
                "case_id": case.case_id,
                "family": case.family,
                "expected_labels": list(case.expected_labels),
                "labels": [],
                "categories": [],
                "line_ranges_present": False,
                "matched": False,
                "plagiarism_accusation_without_similarity": False,
                "error": str(exc),
            }
        rows.append(row)
    summary = {
        "total": len(rows),
        "matched": sum(1 for row in rows if row["matched"]),
        "errors": sum(1 for row in rows if row.get("error")),
        "line_ranges_present": sum(1 for row in rows if row["line_ranges_present"]),
        "plagiarism_accusations_without_similarity": sum(1 for row in rows if row["plagiarism_accusation_without_similarity"]),
    }
    summary["match_rate"] = round(summary["matched"] / max(1, summary["total"]), 4)
    summary["line_range_rate"] = round(summary["line_ranges_present"] / max(1, summary["total"]), 4)
    summary["passes_phase2_slice_gate"] = (
        summary["total"] == 30
        and summary["errors"] == 0
        and summary["match_rate"] >= 0.85
        and summary["line_range_rate"] >= 0.80
        and summary["plagiarism_accusations_without_similarity"] == 0
    )
    return {
        "suite": "sophia_writing_desk_phase2_annotations",
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
    return 0 if artifact["summary"]["passes_phase2_slice_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
