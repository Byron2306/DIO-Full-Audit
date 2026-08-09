#!/usr/bin/env python3
"""Policy alignment suite for Sophia academic-integrity governance.

Maps Sophia's Genesis/Presence duties to current academic-integrity policy
sources, with NWU and South African/global context as primary targets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.document_evidence import extract_document_evidence  # noqa: E402


POLICY_SOURCES = [
    {
        "source_id": "nwu_academic_integrity_policy_2025",
        "jurisdiction": "North-West University",
        "title": "NWU Policy on Academic Integrity",
        "url": "https://www.nwu.ac.za/sites/www.nwu.ac.za/files/files/i-governance-management/policy/2025/2P_2.4.3.2_Policy-on-Academic-Integrity.pdf",
        "expected_terms": ["academic integrity", "artificial intelligence", "plagiarism", "misconduct"],
        "priority": "primary_nwu",
    },
    {
        "source_id": "nwu_senate_rules_academic_integrity_2025",
        "jurisdiction": "North-West University",
        "title": "NWU Senate Rules on Academic Integrity",
        "url": "https://www.nwu.ac.za/sites/www.nwu.ac.za/files/files/i-governance-management/policy/2025/2025.06.02_Senate-Rules-on-Academic-Integrity-complete.pdf",
        "expected_terms": ["plagiarism", "copyright", "academic misconduct", "rules"],
        "priority": "primary_nwu",
    },
    {
        "source_id": "nwu_ai_policy_2025",
        "jurisdiction": "North-West University",
        "title": "NWU Policy on Artificial Intelligence",
        "url": "https://www.nwu.ac.za/sites/www.nwu.ac.za/files/files/i-governance-management/policy/2025/Nov/5P_5.10_AI-policy.pdf",
        "expected_terms": ["artificial intelligence", "ethical", "academic integrity", "copyright"],
        "priority": "primary_nwu",
    },
    {
        "source_id": "nwu_ai_teaching_learning_guidelines",
        "jurisdiction": "North-West University",
        "title": "NWU Guidelines for the Utilisation of AI in Teaching and Learning",
        "url": "https://news.nwu.ac.za/sites/news.nwu.ac.za/files/files/Robert.Balfour/Utilization-AI-TL.pdf",
        "expected_terms": ["teaching", "learning", "academic integrity", "plagiarism"],
        "priority": "nwu_guidance",
    },
    {
        "source_id": "unesco_genai_education_research_2023",
        "jurisdiction": "Global",
        "title": "UNESCO Guidance for Generative AI in Education and Research",
        "url": "https://www.unesco.org/en/articles/guidance-generative-ai-education-and-research",
        "expected_terms": ["human-centred", "education", "research", "policy"],
        "priority": "global_guidance",
    },
    {
        "source_id": "usaf_sa_ai_policies_2025",
        "jurisdiction": "South Africa",
        "title": "USAf Institutional AI Policies and Guidelines in South Africa",
        "url": "https://usaf.ac.za/institutional-ai-policies-and-guidelines-in-south-africa-for-learning-and-teaching/",
        "expected_terms": ["South African", "higher education", "AI", "learning and teaching"],
        "priority": "south_africa_context",
    },
]


GENESIS_PRESENCE_ARTICLES = [
    {"article": "I", "duty": "human authorship", "policy_terms": ["own work", "authorship", "student", "author", "original work"]},
    {"article": "II", "duty": "evidence and truth boundaries", "policy_terms": ["evidence", "truth", "misrepresentation", "falsification", "fabrication"]},
    {"article": "III", "duty": "refusal and repair capacity", "policy_terms": ["misconduct", "unauthorised", "unauthorized", "prohibited", "disciplinary"]},
    {"article": "IV", "duty": "office and lane limits", "policy_terms": ["scope", "role", "responsibility", "guidelines", "standards"]},
    {"article": "V", "duty": "semantic judgment", "policy_terms": ["interpret", "judgement", "judgment", "assessment", "evaluation"]},
    {"article": "VI", "duty": "chain integrity", "policy_terms": ["process", "record", "audit", "trace", "procedure"]},
    {"article": "VII", "duty": "repair transparency", "policy_terms": ["correction", "remediation", "rectify", "appeal", "review"]},
    {"article": "VIII", "duty": "provenance status", "policy_terms": ["acknowledge", "citation", "reference", "source", "disclosure"]},
    {"article": "IX", "duty": "harmonic cadence and learner support", "policy_terms": ["support", "development", "learning", "teaching", "training"]},
    {"article": "X", "duty": "custodial accountability", "policy_terms": ["accountability", "responsibility", "compliance", "governance"]},
    {"article": "XI", "duty": "human supremacy and final judgment", "policy_terms": ["student responsibility", "human", "employee", "accountable", "final"]},
    {"article": "XII", "duty": "honest limitation", "policy_terms": ["limitations", "uncertainty", "reliable", "risk", "accuracy"]},
]


ASSISTANCE_CATEGORIES = [
    {
        "category": "allowed_learning_scaffold",
        "description": "Explain concepts, ask diagnostic questions, provide examples, or guide revision without replacing learner authorship.",
        "allowed": True,
        "policy_basis": ["learning", "support", "teaching", "student responsibility"],
        "audit_language": "Allowed when the learner remains author, final wording is learner-owned, and assistance is transparent where required.",
    },
    {
        "category": "allowed_source_discovery_and_triage",
        "description": "Find or rank source leads and map them to claim/evidence/warrant/limitation.",
        "allowed": True,
        "policy_basis": ["source", "reference", "acknowledge", "citation"],
        "audit_language": "Allowed as citation leads only; support claims require inspected source spans and human verification.",
    },
    {
        "category": "conditional_language_feedback",
        "description": "Feedback on clarity, structure, grammar, or rigor while preserving the learner's substantive judgment.",
        "allowed": True,
        "policy_basis": ["support", "academic development", "responsibility"],
        "audit_language": "Conditionally allowed when not converted into ghostwritten final submission text.",
    },
    {
        "category": "conditional_ai_use_with_disclosure",
        "description": "AI-assisted brainstorming or feedback where course/institutional rules require disclosure or acknowledgement.",
        "allowed": True,
        "policy_basis": ["artificial intelligence", "disclosure", "acknowledge", "academic integrity"],
        "audit_language": "Conditional on local task instructions, acknowledgement expectations, and preservation of human accountability.",
    },
    {
        "category": "disallowed_ghostwriting_or_final_answer_substitution",
        "description": "Produce final paste-ready academic work for submission as the learner's own.",
        "allowed": False,
        "policy_basis": ["plagiarism", "own work", "misconduct", "unauthorised assistance"],
        "audit_language": "Disallowed because it substitutes for authorship and misrepresents achievement.",
    },
    {
        "category": "disallowed_concealment_or_detector_evasion",
        "description": "Hide AI use, conceal provenance, evade Turnitin/detectors, or suppress logs.",
        "allowed": False,
        "policy_basis": ["misrepresentation", "deception", "plagiarism", "academic misconduct"],
        "audit_language": "Disallowed because it undermines provenance, assessment validity, and accountability.",
    },
    {
        "category": "disallowed_fabricated_sources_or_false_support",
        "description": "Invent citations, fabricate evidence, or claim unsupported source backing.",
        "allowed": False,
        "policy_basis": ["fabrication", "misrepresentation", "source", "reference"],
        "audit_language": "Disallowed because false provenance and fabricated evidence breach academic integrity.",
    },
]


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _download_source(source: Dict[str, Any], directory: Path, timeout: float) -> Path:
    suffix = ".html"
    if source["url"].lower().split("?", 1)[0].endswith(".pdf"):
        suffix = ".pdf"
    path = directory / f"{source['source_id']}{suffix}"
    req = urllib.request.Request(source["url"], headers={"User-Agent": "SophiaPolicyAlignment/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        path.write_bytes(resp.read())
    return path


def _extract_sources(timeout: float, offline: bool = False) -> List[Dict[str, Any]]:
    extracted: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for source in POLICY_SOURCES:
            row = dict(source)
            try:
                if offline:
                    raise RuntimeError("offline_mode")
                path = _download_source(source, root, timeout)
                evidence = extract_document_evidence(path, modality="policy_document", task_label="policy_alignment", max_chars=45000)
                text = str(evidence.get("extracted_text") or "")
                row.update({
                    "status": "extracted",
                    "source_path": str(path),
                    "parser": evidence.get("parser"),
                    "readable_chars": len(text),
                    "text": text,
                    "spans": evidence.get("spans") or [],
                    "uncertainty_notes": evidence.get("uncertainty_notes") or [],
                })
            except Exception as exc:
                row.update({
                    "status": "metadata_only",
                    "error": f"{type(exc).__name__}: {exc}",
                    "text": " ".join([source["title"], source["jurisdiction"], " ".join(source["expected_terms"])]),
                    "spans": [],
                    "uncertainty_notes": ["source_download_or_extraction_unavailable"],
                })
            extracted.append(row)
    return extracted


def _term_hits(text: str, terms: List[str]) -> List[str]:
    lowered = (text or "").lower()
    hits = []
    for term in terms:
        if re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", lowered):
            hits.append(term)
    return hits


def _article_policy_matrix(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    joined_by_priority = {
        priority: "\n".join(str(src.get("text") or "") for src in sources if src.get("priority") == priority)
        for priority in sorted({str(src.get("priority") or "") for src in sources})
    }
    all_text = "\n".join(str(src.get("text") or "") for src in sources)
    for article in GENESIS_PRESENCE_ARTICLES:
        hits = _term_hits(all_text, article["policy_terms"])
        source_hits = []
        for src in sources:
            src_hits = _term_hits(str(src.get("text") or ""), article["policy_terms"])
            if src_hits:
                source_hits.append({"source_id": src["source_id"], "hits": src_hits[:8]})
        rows.append({
            "article": article["article"],
            "duty": article["duty"],
            "policy_terms": article["policy_terms"],
            "hits": hits[:12],
            "source_hits": source_hits,
            "nwu_primary_signal": bool(_term_hits(joined_by_priority.get("primary_nwu", ""), article["policy_terms"])),
            "global_or_sa_signal": bool(_term_hits(joined_by_priority.get("global_guidance", "") + joined_by_priority.get("south_africa_context", ""), article["policy_terms"])),
            "alignment_status": "aligned_signal_present" if hits else "needs_manual_policy_review",
        })
    return rows


def _assistance_policy_map(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    text = "\n".join(str(src.get("text") or "") for src in sources)
    rows = []
    for category in ASSISTANCE_CATEGORIES:
        hits = _term_hits(text, category["policy_basis"])
        rows.append({
            **category,
            "policy_hits": hits,
            "policy_signal": bool(hits),
            "conduct_class": "allowed_or_conditional" if category["allowed"] else "disallowed",
            "sophia_release_rule": (
                "assist_with_scaffold_and_disclosure"
                if category["allowed"]
                else "refuse_and_offer_lawful_alternative"
            ),
        })
    return rows


def _institutional_audit_language(article_rows: List[Dict[str, Any]], assistance_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "short_statement": (
            "Sophia is designed as an authorship-preserving academic assistant: it may support learning, source triage, "
            "feedback, and reflection, but must refuse ghostwriting, concealment, detector evasion, fabricated sources, "
            "and unsupported claims."
        ),
        "institutional_template": [
            "The system preserves human authorship by returning final judgment and final wording to the learner.",
            "The system records provenance status and distinguishes source-grounded evidence from inference or uncertainty.",
            "The system refuses requests for covert substitution, plagiarism evasion, fabricated citations, or log/provenance suppression.",
            "The system provides audit artifacts showing the prompt, document evidence status, assistance category, release decision, and repair/refusal trace.",
            "The system should be evaluated against local module instructions and institutional AI-use rules before high-stakes deployment.",
        ],
        "minimum_audit_fields": [
            "assistance_category",
            "human_authorship_preserved",
            "source_provenance_visible",
            "disclosure_or_acknowledgement_needed",
            "final_answer_substitution_risk",
            "fabricated_source_risk",
            "release_or_refusal_decision",
            "learner_owned_next_action",
        ],
        "article_coverage_count": sum(1 for row in article_rows if row["alignment_status"] == "aligned_signal_present"),
        "assistance_category_count": len(assistance_rows),
    }


def _write_markdown(artifact: Dict[str, Any], path: Path) -> None:
    summary = artifact["summary"]
    lines = [
        "# Sophia Policy Alignment Report",
        "",
        f"Timestamp: `{artifact['timestamp']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Sources | {summary['sources']} |",
        f"| Extracted sources | {summary['extracted_sources']} |",
        f"| Article alignments | {summary['article_aligned']}/{summary['article_total']} |",
        f"| Assistance categories | {summary['assistance_categories']} |",
        f"| Cases passed | {summary['passed']}/{summary['total']} |",
        "",
        "## Article Alignment",
        "",
        "| Article | Duty | Status | NWU primary signal | Global/SA signal |",
        "|---|---|---|---:|---:|",
    ]
    for row in artifact["article_policy_matrix"]:
        lines.append(
            f"| {row['article']} | {row['duty']} | {row['alignment_status']} | "
            f"{row['nwu_primary_signal']} | {row['global_or_sa_signal']} |"
        )
    lines.extend([
        "",
        "## Assistance Categories",
        "",
        "| Category | Class | Policy Signal | Release Rule |",
        "|---|---|---:|---|",
    ])
    for row in artifact["assistance_policy_map"]:
        lines.append(f"| `{row['category']}` | {row['conduct_class']} | {row['policy_signal']} | `{row['sophia_release_rule']}` |")
    lines.extend([
        "",
        "## Institutional Audit Language",
        "",
        artifact["institutional_audit_language"]["short_statement"],
        "",
        "Minimum audit fields:",
    ])
    for field in artifact["institutional_audit_language"]["minimum_audit_fields"]:
        lines.append(f"- `{field}`")
    lines.extend([
        "",
        "## Truth Boundary",
        "",
        "This report is a policy-alignment aid, not legal advice and not an institutional approval. "
        "NWU/module-specific instructions, current Senate rules, and formal university guidance remain authoritative.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> Dict[str, Any]:
    sources = _extract_sources(timeout=args.timeout, offline=args.offline)
    article_rows = _article_policy_matrix(sources)
    assistance_rows = _assistance_policy_map(sources)
    audit_language = _institutional_audit_language(article_rows, assistance_rows)
    cases = [
        _case("nwu_primary_sources_present", sum(1 for src in sources if src["priority"] == "primary_nwu") >= 3),
        _case("global_and_sa_context_present", any(src["priority"] == "global_guidance" for src in sources) and any(src["priority"] == "south_africa_context" for src in sources)),
        _case("all_articles_mapped", len(article_rows) == 12 and sum(1 for row in article_rows if row["alignment_status"] == "aligned_signal_present") >= 10),
        _case("allowed_and_disallowed_categories_present", any(row["allowed"] for row in assistance_rows) and any(not row["allowed"] for row in assistance_rows)),
        _case("institutional_audit_language_emitted", bool(audit_language["minimum_audit_fields"]) and "authorship-preserving" in audit_language["short_statement"]),
    ]
    passed = sum(1 for case in cases if case["passed"])
    return {
        "suite": "sophia_policy_alignment",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4),
            "sources": len(sources),
            "extracted_sources": sum(1 for src in sources if src["status"] == "extracted"),
            "article_total": len(article_rows),
            "article_aligned": sum(1 for row in article_rows if row["alignment_status"] == "aligned_signal_present"),
            "assistance_categories": len(assistance_rows),
        },
        "sources": [{k: v for k, v in src.items() if k not in {"text"}} for src in sources],
        "article_policy_matrix": article_rows,
        "assistance_policy_map": assistance_rows,
        "institutional_audit_language": audit_language,
        "cases": cases,
        "source_urls": POLICY_SOURCES,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--out", default=str(ROOT / "evidence" / "sophia_policy_alignment_latest.json"))
    parser.add_argument("--md-out", default=str(ROOT / "evidence" / "SOPHIA_POLICY_ALIGNMENT_LATEST.md"))
    args = parser.parse_args()
    artifact = run(args)
    out = Path(args.out)
    md_out = Path(args.md_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    _write_markdown(artifact, md_out)
    print(json.dumps(artifact["summary"], indent=2))
    print(str(md_out))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
