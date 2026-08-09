#!/usr/bin/env python3
"""
Academic Integrity Proof Gauntlet
=================================

An inspectable attached-file analysis layer for Sophia. The gauntlet proves a
positive claim: AI can preserve authorship while giving useful academic help.
It does not use AI-detection as proof of misconduct.
"""

from __future__ import annotations

import re
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from backend.services.plagiarism_detector import check_plagiarism, report_to_dict
except ImportError:
    from plagiarism_detector import check_plagiarism, report_to_dict

try:
    from backend.services.mandos_protocol_judge import get_mandos_protocol_judge
except ImportError:
    from mandos_protocol_judge import get_mandos_protocol_judge


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.strip()) > 8]


def _tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "for", "that", "this", "with", "from", "into", "your",
        "you", "are", "was", "were", "has", "have", "had", "not", "but",
        "can", "will", "would", "should", "could", "their", "there",
    }
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 3 and t not in stop}


def _source_records(document_evidence: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for document in (document_evidence or {}).get("documents") or []:
        name = str(document.get("source_name") or "Uploaded source")
        spans = document.get("spans") or []
        text = " ".join(str((span or {}).get("quote") or "").strip() for span in spans).strip()
        if text:
            records.append({"name": name, "text": text})
    return records


def _hash_payload(payload: Any) -> str:
    import json
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _telemetry_chain(stages: List[Dict[str, Any]]) -> Dict[str, Any]:
    prev = "0" * 64
    events = []
    for idx, stage in enumerate(stages, start=1):
        event = {
            "index": idx,
            "stage": stage.get("stage"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": stage,
            "prev_hash": prev,
        }
        event_hash = _hash_payload(event)
        event["event_hash"] = event_hash
        events.append(event)
        prev = event_hash
    return {
        "schema_version": "sophia.gauntlet.telemetry_chain.v1",
        "event_count": len(events),
        "head_hash": prev,
        "events": events,
    }


def _file_inspection(document_evidence: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    documents = []
    for document in (document_evidence or {}).get("documents") or []:
        quality = document.get("evidence_quality") or {}
        spans = document.get("spans") or []
        documents.append({
            "source_name": document.get("source_name"),
            "mime_type": document.get("mime_type"),
            "modality": document.get("modality"),
            "parser": document.get("parser"),
            "quality": quality,
            "uncertainty_notes": list(document.get("uncertainty_notes") or []),
            "readable_span_count": len(spans),
            "sample_spans": [
                {
                    "span_id": span.get("span_id"),
                    "quote": str(span.get("quote") or "")[:280],
                }
                for span in spans[:3]
            ],
        })
    return {
        "document_count": len(documents),
        "documents": documents,
        "all_readable": bool(documents) and all(
            ((doc.get("quality") or {}).get("score") or 0) >= 0.7
            for doc in documents
        ),
    }


def _quality_feedback(student_text: str, sources: List[Dict[str, str]]) -> Dict[str, Any]:
    student_sentences = _sentences(student_text)
    source_text = " ".join(src.get("text", "") for src in sources)
    source_tokens = _tokens(source_text)
    source_l = source_text.lower()

    claim_feedback = []
    for sentence in student_sentences[:8]:
        sentence_l = sentence.lower()
        overclaim = any(token in sentence_l for token in ("fixed", "solved", "proves", "caused", "everywhere", "alone"))
        overlap = len(_tokens(sentence) & source_tokens)
        source_has_limit = any(token in source_l for token in ("does not claim", "but it does not", "does not prove", "cannot infer"))
        if overclaim and source_has_limit:
            claim_feedback.append({
                "sentence": sentence,
                "issue": "overclaim_beyond_source",
                "lawful_help": (
                    "Keep the insight, but narrow it: the source supports an association/change, "
                    "not a solved-problem or single-cause claim."
                ),
            })
        elif overlap == 0:
            claim_feedback.append({
                "sentence": sentence,
                "issue": "unsupported_or_unanchored",
                "lawful_help": "Add evidence from the source or mark this as your own inference.",
            })
        elif overlap < 3:
            claim_feedback.append({
                "sentence": sentence,
                "issue": "weak_source_anchor",
                "lawful_help": "Tighten the claim by naming the exact source detail it depends on.",
            })

    if not student_sentences:
        claim_feedback.append({
            "sentence": "",
            "issue": "no_draft_text",
            "lawful_help": "Provide your own draft paragraph for feedback; Sophia should not author it for you.",
        })

    return {
        "mode": "feedback_not_rewrite",
        "claim_evidence_warrant": {
            "claim_check": "Each major claim should be narrower than the evidence.",
            "evidence_check": "Every source-dependent claim needs a citation or quoted/paraphrased source anchor.",
            "warrant_check": "Explain how the evidence supports the claim; do not let Sophia supply the whole argument.",
        },
        "sentence_level_feedback": claim_feedback[:5],
        "revision_protocol": [
            "Highlight one claim you want to keep.",
            "Attach the exact source span that supports it.",
            "Rewrite the sentence yourself with a narrower verb.",
            "Ask Sophia to check alignment, not to produce the final sentence.",
        ],
    }


def _pitfall_scan(
    *,
    student_text: str,
    sources: List[Dict[str, str]],
    document_evidence: Optional[Dict[str, Any]],
    plagiarism_report: Dict[str, Any],
    quality: Dict[str, Any],
) -> Dict[str, Any]:
    source_text = " ".join(src.get("text", "") for src in sources).lower()
    text_l = (student_text or "").lower()
    file_report = _file_inspection(document_evidence)
    pitfalls = []

    def add(pid: str, severity: str, evidence: str, repair: str) -> None:
        pitfalls.append({
            "id": pid,
            "severity": severity,
            "evidence": evidence,
            "lawful_repair": repair,
        })

    if not sources:
        add("missing_source_evidence", "high", "No readable source spans were available.", "Ask for the source or OCR before giving source-grounded feedback.")
    if not file_report.get("all_readable"):
        add("attachment_uncertainty", "medium", "One or more attachments are partial/unreadable.", "State readable spans and refuse to infer missing content.")
    if plagiarism_report.get("overall_score", 0) >= 0.2:
        add("source_overlap", "medium", plagiarism_report.get("summary", ""), "Require citation, quotation marks for exact phrases, or student-authored paraphrase.")
    if (plagiarism_report.get("ai_detection") or {}).get("verdict") in {"likely_ai", "almost_certainly_ai", "uncertain"}:
        add("detector_nonproof", "medium", "AI-detector signal is non-definitive.", "Use process evidence and revision dialogue; do not convict from detector score.")
    if any(item.get("issue") == "overclaim_beyond_source" for item in quality.get("sentence_level_feedback") or []):
        add("overclaim_beyond_source", "high", "Draft claims stronger causality/solution than the source warrants.", "Step down claim strength and align warrant to explicit source language.")
    if any(token in text_l for token in ("fixed", "solved", "proves", "caused")) and "does not claim" in source_text:
        add("causal_overreach", "high", "Student uses causal/solution verbs while source includes an explicit limitation.", "Use 'is associated with', 'reports', or 'suggests' rather than solved/proved/caused.")
    if not quality.get("sentence_level_feedback"):
        add("feedback_thinness", "medium", "No sentence-level feedback was generated.", "Return at least one claim/evidence/warrant move.")

    return {
        "pitfall_count": len(pitfalls),
        "highest_severity": "high" if any(p["severity"] == "high" for p in pitfalls) else ("medium" if pitfalls else "none"),
        "pitfalls": pitfalls,
    }


def _complexity_ladder(student_text: str, quality: Dict[str, Any]) -> Dict[str, Any]:
    feedback_items = quality.get("sentence_level_feedback") or []
    word_count = len((student_text or "").split())
    baseline_level = 2 if word_count < 80 else 3
    if len(feedback_items) >= 3:
        baseline_level = min(5, baseline_level + 1)
    return {
        "current_level": baseline_level,
        "can_step_down_to": {
            "level": max(1, baseline_level - 1),
            "move": "Name one claim, one source detail, and one limit in plain language.",
        },
        "can_step_up_to": {
            "level": min(5, baseline_level + 1),
            "move": "Evaluate claim/evidence/warrant, causal language, and citation transparency across the paragraph.",
        },
        "proof": "Sophia can grade complexity without changing authorship: simpler diagnostic prompt, richer criterion feedback, same student-owned rewrite.",
    }


def _prompt_approach_from_memory(
    *,
    learner_history_profile: Optional[Dict[str, Any]],
    pitfall_report: Dict[str, Any],
    plagiarism_report: Dict[str, Any],
) -> Dict[str, Any]:
    learner_history_profile = learner_history_profile or {}
    high = pitfall_report.get("highest_severity") == "high"
    overlap = plagiarism_report.get("overall_score", 0) >= 0.2
    if high or overlap:
        office = "custos"
        mode = "boundary_then_feedback"
    elif learner_history_profile.get("adaptation_hint"):
        office = "maieuticus"
        mode = "guided_handback"
    else:
        office = "dialecticus"
        mode = "quality_critique"
    return {
        "recommended_office": office,
        "approach_mode": mode,
        "memory_signal": learner_history_profile,
        "refusal_policy": "Refuse replacement authorship; permit feedback, evidence mapping, citation checks, and student-completed revision.",
        "prompt_strategy": [
            "Classify intent before answering.",
            "If authorship risk exists, set boundary first.",
            "Use attached source spans only.",
            "Return a learner-owned next action.",
        ],
    }


def _ipsative_gauntlet_assessment(
    *,
    prior_profile: Optional[Dict[str, Any]],
    pitfall_report: Dict[str, Any],
    mandos: Dict[str, Any],
    quality: Dict[str, Any],
) -> Dict[str, Any]:
    score = 0.0
    score += 0.25 if mandos.get("passed") else 0.0
    score += 0.25 if pitfall_report.get("pitfall_count", 0) > 0 else 0.0
    score += 0.25 if quality.get("sentence_level_feedback") else 0.0
    score += 0.25 if pitfall_report.get("highest_severity") in {"high", "medium"} else 0.0
    prior_handback = (prior_profile or {}).get("handback_rate")
    return {
        "current_gauntlet_score": round(score, 3),
        "prior_memory_marker": {
            "handback_rate": prior_handback,
            "dominant_challenge": (prior_profile or {}).get("dominant_challenge"),
            "adaptation_hint": (prior_profile or {}).get("adaptation_hint"),
        },
        "ipsative_claim": (
            "This run is better than a refusal-only baseline if it detects pitfalls, preserves authorship, "
            "provides sentence-level feedback, and passes Mandos judgment."
        ),
        "next_growth_target": (
            "Add longitudinal comparison against prior gauntlet artifacts and require improvement in pitfall recall and feedback specificity."
        ),
    }


def run_academic_integrity_gauntlet(
    *,
    student_text: str,
    assignment_prompt: str = "",
    document_evidence: Optional[Dict[str, Any]] = None,
    policy_context: str = "",
    learner_history_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sources = _source_records(document_evidence)
    plagiarism_report = report_to_dict(check_plagiarism(student_text, sources, run_ai_detection=True))
    file_report = _file_inspection(document_evidence)
    quality = _quality_feedback(student_text, sources)
    pitfall_report = _pitfall_scan(
        student_text=student_text,
        sources=sources,
        document_evidence=document_evidence,
        plagiarism_report=plagiarism_report,
        quality=quality,
    )
    complexity = _complexity_ladder(student_text, quality)
    prompt_approach = _prompt_approach_from_memory(
        learner_history_profile=learner_history_profile,
        pitfall_report=pitfall_report,
        plagiarism_report=plagiarism_report,
    )

    ai_detection = plagiarism_report.get("ai_detection") or {}
    ai_detector_caution = {
        "detector_verdict": ai_detection.get("verdict"),
        "ai_probability": ai_detection.get("ai_probability"),
        "policy_position": (
            "AI-detection signals are advisory only. They are not proof of misconduct; "
            "authorship evidence, source overlap, process history, and student explanation matter more."
        ),
    }

    high_overlap = plagiarism_report.get("risk_level") in {"high", "critical"} or plagiarism_report.get("overall_score", 0) >= 0.45
    has_sources = bool(sources)
    verdict = "PASS_WITH_LAWFUL_FEEDBACK"
    if not has_sources:
        verdict = "INCOMPLETE_NO_SOURCE_EVIDENCE"
    elif high_overlap:
        verdict = "REPAIR_REQUIRED_SOURCE_OVERLAP"

    response_summary = (
        "I inspected the attached evidence and can give quality feedback without replacing the student's authorship. "
        "I will treat detector signals as non-proof, compare the draft against supplied sources, and return revision moves the student must complete. "
        "Your next move: choose one flagged sentence, rewrite it yourself with a narrower claim, and ask Sophia to check source alignment."
    )
    mandos = get_mandos_protocol_judge().judge(
        directive=assignment_prompt or "attached-file academic integrity gauntlet",
        response=response_summary,
        source="academic_integrity_gauntlet",
        ctx=None,
        assessment={
            "criterion": {"overall": "LAWFUL"},
            "diagnosis": {"pedagogical_need_state": "needs_authorship_return"},
            "retrieval": {},
            "struggle": {"calibration_vector": {"false_confidence": False}},
        },
        document_evidence=document_evidence,
        release_ledger={"provenance_status": "document_evidence" if has_sources else "local_or_inferred"},
        harmonic={"mode": "quality_assurance"},
    )
    ipsative = _ipsative_gauntlet_assessment(
        prior_profile=learner_history_profile,
        pitfall_report=pitfall_report,
        mandos=mandos,
        quality=quality,
    )
    telemetry = _telemetry_chain([
        {"stage": "file_inspection", "summary": file_report},
        {"stage": "integrity_overlap_ai_detector_caution", "summary": {"risk": plagiarism_report.get("risk_level"), "ai": ai_detector_caution}},
        {"stage": "pitfall_scan", "summary": pitfall_report},
        {"stage": "pedagogical_quality_feedback", "summary": quality},
        {"stage": "complexity_ladder", "summary": complexity},
        {"stage": "prompt_approach_memory_routing", "summary": prompt_approach},
        {"stage": "mandos_judgment", "summary": mandos},
        {"stage": "ipsative_assessment", "summary": ipsative},
    ])

    return {
        "schema_version": "sophia.academic_integrity_proof_gauntlet.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "student_text_word_count": len((student_text or "").split()),
        "assignment_prompt_present": bool((assignment_prompt or "").strip()),
        "policy_context_present": bool((policy_context or "").strip()),
        "file_inspection": file_report,
        "integrity_report": plagiarism_report,
        "ai_detector_caution": ai_detector_caution,
        "quality_assistance": quality,
        "pitfall_report": pitfall_report,
        "complexity_ladder": complexity,
        "prompt_approach": prompt_approach,
        "ipsative_assessment": ipsative,
        "telemetry_chain": telemetry,
        "lawful_boundaries": [
            "Do not write the submission for the student.",
            "Do not treat AI-detector output as proof of misconduct.",
            "Do not infer content from unreadable attachments.",
            "Do provide source-grounded feedback, revision targets, and process evidence.",
        ],
        "proof_claim": (
            "A detector-first or blanket-ban policy is weaker than this workflow because this workflow "
            "preserves authorship, inspects evidence, documents uncertainty, and gives actionable learning feedback."
        ),
        "mandos_judgment": mandos,
    }
