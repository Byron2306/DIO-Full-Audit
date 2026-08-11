from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dio_epistemic_spine import (
    append_hash_chained_event,
    criticism_authority,
    epistemic_tokens,
    factual_assertion_risk,
)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_lower(value: Any) -> str:
    return _norm(value).casefold()


def _sentences(text: str) -> list[str]:
    cleaned = _norm(text)
    if not cleaned:
        return []
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned) if p.strip()]


def _criticism_target(comment: str) -> str:
    match = re.search(
        r"(?i)\b(?:lacks?|missing|fails?\s+to|does\s+not|doesn't|insufficient|limited)\b(?P<tail>.*)$",
        _norm(comment),
    )
    return str(match.group("tail") if match else "").strip(" .,:;-")


def _criterion_lookup(criteria_scores: dict[str, Any], name: str) -> dict[str, Any] | None:
    wanted = _norm_lower(name)
    for key, value in criteria_scores.items():
        key_norm = _norm_lower(key)
        if key_norm == wanted or key_norm in wanted or wanted in key_norm:
            return value if isinstance(value, dict) else None
    return None


def assessment_argument_topology(assessment: dict[str, Any], submission_text: str) -> dict[str, Any]:
    sentences = _sentences(submission_text)
    probes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for index, annotation in enumerate(assessment.get("annotations") or [], start=1):
        if not isinstance(annotation, dict):
            continue
        quote = _norm(annotation.get("quote"))
        comment = _norm(annotation.get("comment"))
        target = _criticism_target(comment)
        target_tokens = epistemic_tokens(target)
        if not quote or len(target_tokens) < 2:
            continue
        quote_index = next(
            (i for i, sentence in enumerate(sentences) if _norm_lower(quote) in _norm_lower(sentence)),
            None,
        )
        if quote_index is None:
            continue
        nearby = [
            i for i in range(max(0, quote_index - 1), min(len(sentences), quote_index + 3))
            if i != quote_index
        ]
        best_overlap: list[str] = []
        best_sentence = ""
        for i in nearby:
            overlap = sorted(target_tokens & epistemic_tokens(sentences[i]))
            if len(overlap) > len(best_overlap):
                best_overlap = overlap
                best_sentence = sentences[i]
        conflict = len(best_overlap) >= 2
        row = {
            "annotation_index": index,
            "criticism": comment,
            "target": target,
            "quote": quote,
            "nearby_overlap_tokens": best_overlap,
            "nearby_sentence": best_sentence,
            "possibly_satisfied_elsewhere_in_argument_unit": conflict,
        }
        probes.append(row)
        if conflict:
            conflicts.append(row)
    return {
        "schema": "dio.homs.assessment_argument_topology.v1",
        "passed": not conflicts,
        "probes": probes,
        "conflicts": conflicts,
        "boundary": "Conflict means re-evaluate the criticism in context; it does not automatically award credit.",
    }


def factual_verification_queue(submission_text: str, limit: int = 24) -> dict[str, Any]:
    rows = []
    for index, sentence in enumerate(_sentences(submission_text), start=1):
        risk = factual_assertion_risk(sentence)
        if risk.get("verification_required"):
            rows.append({"sentence_index": index, "statement": sentence, **risk})
        if len(rows) >= limit:
            break
    return {
        "schema": "dio.homs.factual_verification_queue.v1",
        "count": len(rows),
        "items": rows,
        "truth_determined": False,
        "human_or_source_verification_required": bool(rows),
    }


def criticism_authority_receipts(assessment: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    criteria_scores = assessment.get("criteria_scores") or {}
    receipts: list[dict[str, Any]] = []
    unauthorized: list[dict[str, Any]] = []
    for criterion in rubric.get("criteria") or []:
        name = str(criterion.get("name") or "Unnamed criterion")
        item = _criterion_lookup(criteria_scores, name) or {}
        feedback = str(item.get("feedback") or "")
        authority_parts = [name, str(criterion.get("description") or "")]
        for level_name, payload in (criterion.get("levels") or {}).items():
            authority_parts.extend([str(level_name), str((payload or {}).get("description") or "")])
        authority_text = " ".join(authority_parts)
        for sentence in _sentences(feedback):
            if not _criticism_target(sentence):
                continue
            row = {
                "criterion": name,
                "criticism": sentence,
                **criticism_authority(sentence, authority_text, minimum_overlap=1),
            }
            receipts.append(row)
            if not row.get("authorized_to_affect_score"):
                unauthorized.append(row)
    return {
        "schema": "dio.homs.criticism_authority_receipts.v1",
        "passed": not unauthorized,
        "receipts": receipts,
        "unauthorized_penalty_candidates": unauthorized,
        "law": "Enrichment outside the governing rubric may be suggested but may not reduce the score.",
    }


def harden_contract(
    contract: dict[str, Any],
    assessment: dict[str, Any],
    rubric: dict[str, Any],
    submission_text: str,
) -> dict[str, Any]:
    enriched = dict(contract or {})
    topology = assessment_argument_topology(assessment, submission_text)
    factual = factual_verification_queue(submission_text)
    authority = criticism_authority_receipts(assessment, rubric)
    errors = list(enriched.get("errors") or [])
    if not topology.get("passed"):
        errors.append("argument-topology conflict: criticism may already be satisfied nearby")
    if not authority.get("passed"):
        errors.append("rubric drift: criticism lacks governing rubric authority")
    enriched.update({
        "schema": "knowedge.homs_marking_quality_contract.v2.1",
        "errors": errors,
        "passed": not errors,
        "argument_topology": topology,
        "factual_verification_queue": factual,
        "criticism_authority": authority,
        "argument_topology_passed": bool(topology.get("passed")),
        "criticism_authority_passed": bool(authority.get("passed")),
    })
    return enriched


def append_learner_lineage(
    out_root: Path,
    job_id: str,
    submission_name: str,
    result: dict[str, Any],
    contract: dict[str, Any],
) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", submission_name)
    path = Path(out_root) / "_homs_learner_lineage" / f"{safe}.jsonl"
    append_hash_chained_event(
        path,
        "assessment_attempt",
        submission_name,
        {
            "job_id": job_id,
            "score": result.get("total_score"),
            "max_score": result.get("max_score"),
            "percentage": result.get("percentage"),
            "criteria": {
                name: {
                    "level": item.get("level"),
                    "score": item.get("score"),
                    "max_score": item.get("max_score"),
                }
                for name, item in (result.get("criteria_scores") or {}).items()
                if isinstance(item, dict)
            },
            "quality_passed": bool(contract.get("passed")),
            "argument_topology_passed": bool(contract.get("argument_topology_passed")),
            "criticism_authority_passed": bool(contract.get("criticism_authority_passed")),
            "factual_verification_items": int((contract.get("factual_verification_queue") or {}).get("count") or 0),
            "human_review_required": True,
        },
    )
    return path
