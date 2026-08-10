#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_LOCAL_HOMS_ROOT = Path("/home/byron/Downloads/NoEdge-Multi-Hymark-main/Marker/homs")
VENDORED_LOCAL_HOMS_ROOT = REPO_ROOT / "cross_folder_variants" / "NoEdge-Multi-Hymark-main" / "A_CODE" / "Marker" / "homs"
DEFAULT_LOCAL_HOMS_ROOT = EXTERNAL_LOCAL_HOMS_ROOT


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_lower(value: Any) -> str:
    return _norm(value).casefold()


def quote_is_grounded(quote: Any, submission_text: str) -> bool:
    q = _norm_lower(quote)
    body = _norm_lower(submission_text)
    return bool(q and len(q) >= 8 and q in body)


def _criterion_lookup(criteria_scores: dict[str, Any], name: str) -> dict[str, Any] | None:
    wanted = _norm_lower(name)
    for key, value in criteria_scores.items():
        key_norm = _norm_lower(key)
        if key_norm == wanted or key_norm in wanted or wanted in key_norm:
            return value if isinstance(value, dict) else None
    return None


def assessment_contract(
    assessment: dict[str, Any],
    rubric: dict[str, Any],
    submission_text: str,
    *,
    min_annotation_count: int = 3,
    min_feedback_chars: int = 24,
) -> dict[str, Any]:
    """Validate the buyer-facing Smart Assessor bundle before DIO calls it review-ready."""
    errors: list[str] = []
    warnings: list[str] = []
    verified_quotes = 0
    requested_quotes = 0
    criteria_scores = assessment.get("criteria_scores") or {}
    if not isinstance(criteria_scores, dict):
        criteria_scores = {}
        errors.append("criteria_scores is not an object")

    score_sum = 0.0
    rubric_total = 0.0
    criterion_receipts: list[dict[str, Any]] = []
    for criterion in rubric.get("criteria") or []:
        name = _norm(criterion.get("name") or "Unnamed criterion")
        max_score = float(criterion.get("weight") or 0)
        rubric_total += max_score
        item = _criterion_lookup(criteria_scores, name)
        if not item:
            errors.append(f"missing criterion result: {name}")
            criterion_receipts.append({"criterion": name, "state": "missing"})
            continue
        score = float(item.get("score") or 0)
        score_sum += score
        feedback = _norm(item.get("feedback") or item.get("comment") or "")
        if len(feedback) < min_feedback_chars:
            errors.append(f"criterion feedback too thin: {name}")
        quotes = item.get("quotes") or []
        if isinstance(quotes, str):
            quotes = [quotes]
        grounded = []
        for quote in quotes:
            if not _norm(quote):
                continue
            requested_quotes += 1
            ok = quote_is_grounded(quote, submission_text)
            grounded.append({"quote": _norm(quote), "grounded": ok})
            if ok:
                verified_quotes += 1
        if not grounded:
            errors.append(f"criterion has no quoted submission evidence: {name}")
        elif not any(row["grounded"] for row in grounded):
            errors.append(f"criterion quotations are not grounded in submission: {name}")
        if score < 0 or score > max_score + 1e-6:
            errors.append(f"criterion score outside rubric range: {name}")
        criterion_receipts.append(
            {
                "criterion": name,
                "score": score,
                "max_score": max_score,
                "feedback_chars": len(feedback),
                "quoted_evidence": grounded,
                "state": "complete" if feedback and any(row["grounded"] for row in grounded) else "incomplete",
            }
        )

    stated_total = float(assessment.get("total_score") or 0)
    max_score = float(assessment.get("max_score") or rubric.get("total_marks") or rubric_total or 0)
    if abs(stated_total - score_sum) > 0.01:
        errors.append(f"score reconciliation failed: stated={stated_total}, criteria_sum={round(score_sum, 2)}")
    if max_score and rubric_total and abs(max_score - rubric_total) > 0.01:
        warnings.append(f"assessment max_score {max_score} differs from rubric weight sum {rubric_total}")

    annotations = assessment.get("annotations") or []
    if not isinstance(annotations, list):
        annotations = []
        errors.append("annotations is not a list")
    if len(annotations) < min_annotation_count:
        errors.append(f"too few anchored annotations: {len(annotations)} < {min_annotation_count}")
    annotation_receipts = []
    for index, annotation in enumerate(annotations, 1):
        quote = _norm(annotation.get("quote") if isinstance(annotation, dict) else "")
        comment = _norm(annotation.get("comment") if isinstance(annotation, dict) else "")
        grounded = quote_is_grounded(quote, submission_text)
        if not quote or not grounded:
            errors.append(f"annotation {index} has no grounded exact quotation")
        if len(comment) < min_feedback_chars:
            errors.append(f"annotation {index} comment too thin")
        annotation_receipts.append({"index": index, "quote": quote, "grounded": grounded, "comment_chars": len(comment)})

    if len(_norm(assessment.get("overall_feedback"))) < 50:
        errors.append("overall feedback is missing or too thin")
    if not assessment.get("strengths"):
        errors.append("strengths list is empty")
    if not assessment.get("areas_for_improvement"):
        errors.append("areas_for_improvement list is empty")

    return {
        "schema": "knowedge.homs_marking_quality_contract.v1",
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "criterion_receipts": criterion_receipts,
        "annotation_receipts": annotation_receipts,
        "verified_quote_count": verified_quotes,
        "requested_quote_count": requested_quotes,
        "criterion_count": len(rubric.get("criteria") or []),
        "annotation_count": len(annotations),
        "score_sum": round(score_sum, 2),
        "stated_total": stated_total,
        "human_review_required": True,
        "execution_authority_granted": False,
    }


def repair_instructions(contract: dict[str, Any]) -> str:
    errors = contract.get("errors") or []
    return (
        "QUALITY REPAIR PASS. The previous draft is not release-ready. Repair every listed defect without changing the rubric or inventing evidence. "
        "For every rubric criterion provide a substantive criterion-specific comment and at least one verbatim quotation copied from the submission. "
        "Provide at least three annotations whose quote field is exact text from the submission and whose comment explains the issue or strength. "
        "Reconcile criterion scores exactly to total_score. Keep human educator review mandatory. Defects: "
        + "; ".join(str(item) for item in errors)
    )


def valid_student_ids_from_csv(path: Path) -> set[str]:
    import csv

    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    starts = [0, 2] if len(text) > 2 else [0]
    ids: set[str] = set()
    for start in starts:
        try:
            reader = csv.DictReader(text[start:])
            for row in reader:
                for key in ("student_id", "ID", "Display ID", "Student ID"):
                    value = _norm(row.get(key))
                    if value.isdigit() and len(value) >= 5:
                        ids.add(value)
        except Exception:
            continue
    return ids


def extract_group_members(
    first_page_text: str,
    valid_student_ids: set[str],
    primary_student_id: str,
    *,
    backend: Any | None = None,
) -> list[str]:
    members: list[str] = []
    if backend is not None and hasattr(backend, "extract_group_member_ids"):
        try:
            members = list(backend.extract_group_member_ids(first_page_text, valid_student_ids))
        except Exception:
            members = []
    if not members:
        candidates = re.findall(r"\b\d{5,10}\b", first_page_text)
        members = [sid for sid in candidates if sid in valid_student_ids]
    out: list[str] = []
    for sid in members:
        if sid == primary_student_id or sid in out:
            continue
        out.append(sid)
    return out


def smart_to_local_assessment(result: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    annotations: dict[str, dict[str, Any]] = {}
    passed = 0
    for name, item in (result.get("criteria_scores") or {}).items():
        if not isinstance(item, dict):
            continue
        score = float(item.get("score") or 0)
        max_score = float(item.get("max_score") or 0)
        satisfied = bool(max_score and score / max_score >= 0.60)
        annotations[str(name)] = {"satisfied": satisfied, "score": score, "max_score": max_score}
        passed += int(satisfied)
    return {
        "status": "success" if contract.get("passed") else "quality_blocked",
        "student_id": result.get("student_id"),
        "final_score": float(result.get("percentage") or 0),
        "annotations": annotations,
        "total_annotations": len(annotations),
        "passed_annotations": passed,
        "timestamp": result.get("assessed_at") or "",
    }


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Local HOMS module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_local_homs_root(preferred: Path | None = None) -> tuple[Path, str]:
    candidates: list[tuple[Path, str]] = []
    if preferred is not None:
        candidates.append((preferred, "requested"))
    candidates.extend(
        [
            (EXTERNAL_LOCAL_HOMS_ROOT, "external_download_tree"),
            (VENDORED_LOCAL_HOMS_ROOT, "vendored_repository_copy"),
        ]
    )
    seen: set[str] = set()
    for candidate, source in candidates:
        key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        root = candidate.expanduser().resolve()
        if (root / "core" / "moderation_agent.py").is_file() and (root / "core" / "learning_agent.py").is_file():
            return root, source
    return (preferred or DEFAULT_LOCAL_HOMS_ROOT).expanduser().resolve(), "unresolved"


def run_local_homs_governance(
    results: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    local_homs_root: Path = DEFAULT_LOCAL_HOMS_ROOT,
) -> dict[str, Any]:
    resolved_root, root_source = resolve_local_homs_root(local_homs_root)
    moderation_path = resolved_root / "core" / "moderation_agent.py"
    learning_path = resolved_root / "core" / "learning_agent.py"
    if not moderation_path.is_file() or not learning_path.is_file():
        return {
            "available": False,
            "reason": "Local HOMS moderation/learning modules not found in requested, external or vendored roots",
            "requested_root": str(local_homs_root),
            "resolved_root": str(resolved_root),
            "root_source": root_source,
            "moderation": [],
            "moderation_report": {},
            "learning_insights": {},
        }
    mod_module = _load_module(moderation_path, "homs_local_moderation")
    learn_module = _load_module(learning_path, "homs_local_learning")
    local_rows = [smart_to_local_assessment(result, contract) for result, contract in zip(results, contracts)]
    moderator = mod_module.ModerationAgent({})
    moderations = moderator.batch_moderate(local_rows)
    learner = learn_module.LearningAgent({"min_samples_for_recommendations": 5})
    learner.learn_from_assessments(local_rows, moderations)
    return {
        "available": True,
        "requested_root": str(local_homs_root),
        "source_root": str(resolved_root),
        "root_source": root_source,
        "moderation": moderations,
        "moderation_report": moderator.get_moderation_report(),
        "learning_insights": learner.get_insights(),
        "schema_adapter": "smart_assessor_result -> Local HOMS percentage/criterion-satisfaction view",
        "human_review_required": True,
    }


def _word_shingles(text: str, n: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", str(text or "").casefold())
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def similarity_review_candidates(submissions: Iterable[dict[str, Any]], threshold: float = 0.55) -> dict[str, Any]:
    rows = list(submissions)
    candidates: list[dict[str, Any]] = []
    for i, left in enumerate(rows):
        a = _word_shingles(str(left.get("text") or ""))
        if not a:
            continue
        for right in rows[i + 1 :]:
            b = _word_shingles(str(right.get("text") or ""))
            if not b:
                continue
            union = len(a | b)
            score = len(a & b) / union if union else 0.0
            if score >= threshold:
                candidates.append(
                    {
                        "student_1": left.get("student_id"),
                        "student_2": right.get("student_id"),
                        "five_word_shingle_jaccard": round(score, 4),
                        "review_required": True,
                    }
                )
    return {
        "schema": "knowedge.homs_text_similarity_review.v1",
        "threshold": threshold,
        "candidates": candidates,
        "is_plagiarism_finding": False,
        "boundary": "Similarity only. A human must inspect source attribution, collaboration rules and legitimate shared wording.",
    }


def cohort_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(row.get("percentage") or 0) for row in results]
    if not scores:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    ordered = sorted(scores)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {
        "count": len(scores),
        "mean": round(sum(scores) / len(scores), 2),
        "median": round(median, 2),
        "min": round(min(scores), 2),
        "max": round(max(scores), 2),
        "bands": dict(Counter("<50" if s < 50 else "50-64" if s < 65 else "65-79" if s < 80 else "80+" for s in scores)),
    }
