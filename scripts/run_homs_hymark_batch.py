#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import copy
import importlib.util
import hashlib
import json
import math
import sys
import os
import re
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SECRET_FILE = Path("/home/byron/EdgeK-BEAST/.beast/provider_secrets.env")
DEFAULT_HYMARK_BACKEND = ROOT / "cross_folder_variants" / "NoEdge-Multi-Hymark-main" / "A_CODE" / "backend" / "server.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.replace("export ", "").strip()] = value.strip().strip('"').strip("'")
    return values


def configure_provider(secret_file: Path, provider_name: str, model: str) -> dict[str, Any]:
    values = parse_env_file(secret_file)
    # The fixed sampling seed is specific to local Ollama. Do not carry it
    # into another provider if this helper is called more than once per process.
    os.environ.pop("HOMS_AI_SEED", None)
    for key, value in values.items():
        os.environ.setdefault(key, value)

    provider_name = provider_name.strip().casefold().replace("-", "_")
    if provider_name in {"ollama", "local_ollama", "local"}:
        from sovereign_runtime import ollama_model, ollama_url, require_ollama_provider

        require_ollama_provider(provider_name, component="HOMS HyMark")
        base_url = ollama_url().rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        os.environ["OPENAI_API_KEY"] = "ollama"
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ["HOMS_AI_MODEL"] = model or ollama_model()
        os.environ.setdefault("HOMS_AI_TIMEOUT_SECONDS", "360")
        os.environ.setdefault("HOMS_AI_MAX_RETRIES", "0")
        # A marking response contains feedback and source quotes for every
        # criterion. 512 tokens truncated that JSON even for two learners.
        os.environ.setdefault("HOMS_AI_MAX_TOKENS", "4000")
        # Ollama's OpenAI-compatible API supports a seed; use a stable default
        # so repeated assessments can be compared on the same sampling path.
        os.environ.setdefault("HOMS_AI_SEED", "42")
        selected = "ollama"
        key_name = ""
    elif provider_name in {"nim", "nvidia", "nvidia_nim"}:
        key_name = "NVIDIA_API_KEY"
        api_key = values.get(key_name) or os.environ.get(key_name)
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY was not found in the provider secret file or environment.")
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
        os.environ["HOMS_AI_MODEL"] = model or os.environ.get("HOMS_NIM_MODEL") or os.environ.get("BEAST_NIM_MODEL") or "nvidia/nemotron-3-super-120b-a12b"
        selected = "nvidia_nim"
    else:
        key_name = "OPENAI_API_KEY"
        api_key = values.get(key_name) or os.environ.get(key_name)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY was not found in the provider secret file or environment.")
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ.pop("OPENAI_BASE_URL", None)
        os.environ["HOMS_AI_MODEL"] = model or os.environ.get("OPENAI_MODEL") or "gpt-4o"
        selected = "openai"

    return {
        "selected_provider": selected,
        "selected_model": os.environ["HOMS_AI_MODEL"],
        "selected_key_name": key_name,
        "base_url": os.environ.get("OPENAI_BASE_URL") or None,
        "temperature": float(os.getenv("HOMS_AI_TEMPERATURE", "0.0")),
        "seed": int(os.environ["HOMS_AI_SEED"]) if selected == "ollama" else None,
        "available_secret_names": sorted(k for k, v in values.items() if v and ("KEY" in k or "TOKEN" in k or "SECRET" in k)),
        "values_redacted": True,
    }


def load_hymark_backend(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("hymark_backend_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load HyMark backend module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_rubric_levels(rubric: dict[str, Any]) -> dict[str, Any]:
    enriched = json.loads(json.dumps(rubric))
    total = 0.0
    for criterion in enriched.get("criteria", []):
        weight = float(criterion.get("weight", 0) or 0)
        total += weight
        marking_points = criterion.get("marking_points") or []
        if marking_points:
            point_ids = [str(point.get("point_id") or "") for point in marking_points if isinstance(point, dict)]
            if (len(point_ids) != len(marking_points) or any(not value for value in point_ids)
                    or len(set(point_ids)) != len(point_ids)
                    or any(not str(point.get("point") or "").strip() or float(point.get("marks") or 0) <= 0 for point in marking_points)
                    or abs(sum(float(point.get("marks") or 0) for point in marking_points) - weight) > 0.01):
                raise ValueError(f"Pointwise marking allocation must use unique IDs and sum to criterion weight: {criterion.get('name')}")
            continue
        if criterion.get("levels"):
            continue
        criterion["levels"] = {
            "Excellent": {
                "description": f"Strong, specific, well-supported performance for {criterion.get('name', 'this criterion')}.",
                "min_score": round(weight * 0.8, 2),
                "max_score": weight,
            },
            "Good": {
                "description": f"Clear and mostly well-supported performance for {criterion.get('name', 'this criterion')}.",
                "min_score": round(weight * 0.6, 2),
                "max_score": round(weight * 0.79, 2),
            },
            "Satisfactory": {
                "description": f"Basic but incomplete performance for {criterion.get('name', 'this criterion')}.",
                "min_score": round(weight * 0.4, 2),
                "max_score": round(weight * 0.59, 2),
            },
            "Needs Improvement": {
                "description": f"Limited, unsupported, or unclear performance for {criterion.get('name', 'this criterion')}.",
                "min_score": 0,
                "max_score": round(weight * 0.39, 2),
            },
        }
    if not enriched.get("total_marks"):
        enriched["total_marks"] = total
    return enriched


def clamp(value: Any, max_value: float) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    return round(max(0.0, min(score, max_value)), 2)


def normalize_assessment(raw: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    criteria_raw = raw.get("criteria_scores") or {}
    normalized: dict[str, Any] = {}
    total = 0.0
    pointwise_total_complete = True
    for criterion in rubric.get("criteria", []):
        name = str(criterion.get("name", "Unnamed criterion"))
        max_score = float(criterion.get("weight", 0) or 0)
        item = criteria_raw.get(name)
        if item is None:
            item = next(
                (
                    value
                    for key, value in criteria_raw.items()
                    if str(key).strip().lower() == name.strip().lower()
                    or str(key).strip().lower() in name.strip().lower()
                    or name.strip().lower() in str(key).strip().lower()
                ),
                {},
            )
        if isinstance(item, dict):
            score = clamp(item.get("score", item.get("marks", item.get("mark", 0))), max_score)
            level = str(item.get("level") or "").strip()
            feedback = str(item.get("feedback") or item.get("comment") or item.get("comments") or "").strip()
            provider_feedback = feedback
            quotes = item.get("quotes") or []
            if isinstance(quotes, str):
                quotes = [quotes]
            elif not isinstance(quotes, list):
                quotes = []
            quote_basis = str(item.get("quote_basis") or "")
            point_scores = []
            pointwise_complete = True
            omitted_point_ids: list[str] = []
            pointwise_validation: dict[str, Any] = {}
            marking_points = criterion.get("marking_points") or []
            if marking_points:
                raw_points = item.get("point_scores")
                if isinstance(raw_points, dict):
                    point_map = {str(key): value for key, value in raw_points.items()}
                elif isinstance(raw_points, list):
                    point_map = {
                        str(point.get("point_id") or ""): point
                        for point in raw_points if isinstance(point, dict)
                    }
                    pointwise_complete = (
                        len(point_map) == len(raw_points)
                        and all(isinstance(point, dict) for point in raw_points)
                    )
                else:
                    point_map = {}
                    pointwise_complete = False
                expected_ids = [str(point["point_id"]) for point in marking_points]
                expected_set = set(expected_ids)
                pointwise_complete = pointwise_complete and set(point_map) == expected_set
                unknown_point_ids = sorted(set(point_map) - expected_set)
                point_total = 0.0
                explicit_point_total = 0.0
                invalid_mark_point_ids: list[str] = []
                for point_spec in marking_points:
                    point_id = str(point_spec["point_id"])
                    point_max = float(point_spec.get("marks") or 0)
                    point_raw = point_map.get(point_id)
                    if isinstance(point_raw, dict):
                        raw_mark = point_raw.get("score", point_raw.get("marks", 0))
                        try:
                            numeric_mark = float(raw_mark)
                        except (TypeError, ValueError):
                            numeric_mark = float("nan")
                        if not math.isfinite(numeric_mark) or numeric_mark < 0 or numeric_mark > point_max:
                            pointwise_complete = False
                            invalid_mark_point_ids.append(point_id)
                        point_score = clamp(numeric_mark, point_max) if math.isfinite(numeric_mark) else 0.0
                        explicit_point_total += point_score
                        point_quotes = point_raw.get("quotes") or []
                        if isinstance(point_quotes, str):
                            point_quotes = [point_quotes]
                        elif not isinstance(point_quotes, list):
                            point_quotes = []
                    elif isinstance(point_raw, (int, float)) and not isinstance(point_raw, bool):
                        numeric_mark = float(point_raw)
                        if not math.isfinite(numeric_mark) or numeric_mark < 0 or numeric_mark > point_max:
                            pointwise_complete = False
                            invalid_mark_point_ids.append(point_id)
                        point_score = clamp(numeric_mark, point_max) if math.isfinite(numeric_mark) else 0.0
                        explicit_point_total += point_score
                        point_quotes = []
                    else:
                        pointwise_complete = False
                        point_score = None
                        point_quotes = []
                        omitted_point_ids.append(point_id)
                    if point_score is not None:
                        point_total += point_score
                    point_scores.append({
                        "point_id": point_id,
                        "point": str(point_spec.get("point") or ""),
                        "score": point_score,
                        "max_score": point_max,
                        "quotes": [str(value) for value in point_quotes if isinstance(value, str)],
                        "unbound_quote_candidates": (
                            [str(value) for value in (point_raw.get("unbound_quote_candidates") or []) if isinstance(value, str)]
                            if isinstance(point_raw, dict) else []
                        ),
                        "proposal_basis": "PROVIDER_POINT_SCORE" if point_id in point_map else "PROVIDER_POINT_NOT_RETURNED",
                    })
                if not point_map and float(item.get("score", 0) or 0) != 0:
                    pointwise_complete = False
                declared_value = item.get("score", item.get("marks", item.get("mark")))
                declared_criterion_score = None
                if declared_value is not None:
                    try:
                        declared_criterion_score = float(declared_value)
                    except (TypeError, ValueError):
                        declared_criterion_score = float("nan")
                    # The point list is the scoring source of truth. Retain a
                    # redundant provider criterion total for diagnostics, but
                    # calculate the actual criterion score from point values.
                if not point_map and declared_criterion_score != 0:
                    pointwise_complete = False
                pointwise_validation = {
                    "returned_point_id_count": len(point_map),
                    "missing_point_ids": omitted_point_ids,
                    "missing_point_ids_defaulted_to_zero": [],
                    "unknown_point_ids": unknown_point_ids,
                    "invalid_mark_point_ids": invalid_mark_point_ids,
                    "declared_criterion_score": declared_criterion_score,
                    "explicit_point_score_sum": round(explicit_point_total, 2),
                    "criterion_sum_agreement": (
                        abs(declared_criterion_score - explicit_point_total) <= 0.01
                        if isinstance(declared_criterion_score, (int, float)) and math.isfinite(declared_criterion_score)
                        else None
                    ),
                }
                score = round(point_total, 2) if pointwise_complete else None
                awarded = [point["point"] for point in point_scores if point["score"] is not None and point["score"] > 0]
                not_fully_awarded = [point["point"] for point in point_scores if point["score"] is None or point["score"] < point["max_score"]]
                feedback = (
                    (f"Pointwise model proposal: {score:g}/{max_score:g}. " if score is not None
                     else f"Pointwise response incomplete: {len(omitted_point_ids)} memo point(s) were not returned; no criterion score is computed. ")
                    + ("Proposed marks on: " + "; ".join(awarded) + ". " if awarded else "No marking points received a positive model proposal. ")
                    + ("Points with zero or partial proposed marks: " + "; ".join(not_fully_awarded) + ". " if not_fully_awarded else "All marking points received their full proposed marks. ")
                    + (f"Unreturned point IDs: {', '.join(omitted_point_ids)}. " if omitted_point_ids else "")
                    + "Educator must verify each point score against the exact answer and memo."
                )
        else:
            score = clamp(item, max_score)
            level = ""
            feedback = ""
            quotes = []
            quote_basis = ""
            point_scores = []
            pointwise_complete = not bool(criterion.get("marking_points"))
            provider_feedback = ""
        if score is not None:
            total += score
        if criterion.get("marking_points") and score is None:
            pointwise_total_complete = False
        normalized[name] = {
            "level": level,
            "score": score,
            "max_score": max_score,
            "feedback": feedback,
            "quotes": quotes,
            "quote_basis": quote_basis,
            **({"point_scores": point_scores, "pointwise_complete": pointwise_complete,
            "unreturned_point_ids": omitted_point_ids,
            "omitted_point_ids_defaulted_to_zero": [],
                "pointwise_validation": pointwise_validation} if criterion.get("marking_points") else {}),
            **({"provider_feedback": provider_feedback} if criterion.get("marking_points") else {}),
        }

    raw["criteria_scores"] = normalized
    raw["total_score"] = round(total, 2) if pointwise_total_complete else None
    raw["max_score"] = rubric.get("total_marks", sum(float(row.get("weight") or 0) for row in rubric.get("criteria") or []))
    raw["percentage"] = round((raw["total_score"] / raw["max_score"]) * 100, 2) if raw["total_score"] is not None and raw["max_score"] else None
    raw["pointwise_proposals_complete"] = pointwise_total_complete
    raw.setdefault("annotations", [])
    for key in ("strengths", "areas_for_improvement"):
        value = raw.get(key)
        if isinstance(value, str):
            raw[key] = [value.strip()] if value.strip() else []
        elif isinstance(value, list):
            raw[key] = [str(item).strip() for item in value if str(item).strip()]
        else:
            raw[key] = []
    return raw


def retain_exact_source_quotes(raw: dict[str, Any], rubric: dict[str, Any], submission_text: str) -> None:
    """Keep verbatim learner spans; use a labeled answer line only for criterion navigation."""
    source = " ".join(submission_text.split())
    source_lines = [line.strip() for line in submission_text.splitlines() if line.strip()]
    scores = raw.get("criteria_scores")
    if not isinstance(scores, dict):
        return
    for key, value in scores.items():
        if not isinstance(value, dict):
            continue
        quotes = value.get("quotes") or []
        if isinstance(quotes, str):
            quotes = [quotes]
        if not isinstance(quotes, list):
            value["quotes"] = []
            continue
        exact: list[str] = []
        for candidate in quotes:
            if not isinstance(candidate, str):
                continue
            parts = [candidate, *candidate.split(";")]
            for part in parts:
                span = " ".join(part.split()).strip('\'"`“”‘’;')
                if span and span in source and span not in exact:
                    exact.append(span)
        if not exact:
            def question_label(criterion: dict[str, Any]) -> str:
                explicit = str(criterion.get("question") or "").strip()
                if explicit:
                    return explicit
                return str(criterion.get("name") or "").split(":", 1)[0].strip()

            rubric_criterion = next(
                (
                    criterion for criterion in rubric.get("criteria") or []
                    if str(key).strip().casefold().startswith(question_label(criterion).casefold() + ":")
                    or str(key).strip().casefold() == question_label(criterion).casefold()
                ),
                None,
            )
            question = question_label(rubric_criterion) if rubric_criterion else ""
            if question:
                label_pattern = re.compile(r"^\s*(?:q\s*)?" + re.escape(question) + r"(?:\s*[.):]|\s+)", re.IGNORECASE)
                matched = next((line for line in source_lines if label_pattern.match(line)), None)
                if matched:
                    exact.append(" ".join(matched.split()))
                    value["quote_basis"] = "EXACT_LEARNER_LINE_MATCHED_BY_QUESTION_LABEL"
        value["quotes"] = exact
        point_scores = value.get("point_scores")
        if isinstance(point_scores, dict):
            point_score_rows = [row for row in point_scores.values() if isinstance(row, dict)]
        elif isinstance(point_scores, list):
            point_score_rows = [row for row in point_scores if isinstance(row, dict)]
        else:
            point_score_rows = []
        for point_score in point_score_rows:
            point_quotes = point_score.get("quotes") or []
            if isinstance(point_quotes, str):
                point_quotes = [point_quotes]
            if not isinstance(point_quotes, list):
                point_quotes = []
            exact_point_quotes = []
            prior_unbound = point_score.get("unbound_quote_candidates") or []
            unbound_point_quotes = [
                " ".join(value.split())[:500]
                for value in prior_unbound
                if isinstance(value, str) and value.strip() and " ".join(value.split()) not in source
            ] if isinstance(prior_unbound, list) else []
            for candidate in point_quotes:
                if not isinstance(candidate, str):
                    continue
                for part in [candidate, *candidate.split(";")]:
                    span = " ".join(part.split()).strip('\'`"“”‘’;')
                    if span and span in source and span not in exact_point_quotes:
                        exact_point_quotes.append(span)
                    elif span and span not in unbound_point_quotes:
                        unbound_point_quotes.append(span[:500])
            point_score["quotes"] = exact_point_quotes
            point_score["unbound_quote_candidates"] = list(dict.fromkeys(unbound_point_quotes))[:5]

def score_is_blocked(result: dict[str, Any]) -> bool:
    return str(result.get("score_status") or "").startswith("BLOCKED_")


def write_feedback_txt(path: Path, result: dict[str, Any]) -> None:
    """Render feedback without treating provider strings as character lists."""
    if score_is_blocked(result) or result.get("total_score") is None:
        if result.get("score_status") == "BLOCKED_MISSING_QUESTION_PAPER":
            reason = "the original question paper was not supplied"
        elif result.get("score_status") == "BLOCKED_MISSING_PAPER_AND_QUALITY_FLAGS":
            reason = "the original question paper is missing and marking quality flags remain unresolved"
        elif result.get("score_status") == "BLOCKED_INCOMPLETE_POINTWISE_RESPONSE":
            reason = "the provider omitted source-bound memo point IDs, so no complete total exists"
        elif result.get("score_status") == "PROVISIONAL_EDUCATOR_REVIEW_REQUIRED":
            reason = "an educator has not adjudicated the proposed marks"
        else:
            reason = "marking quality flags remain unresolved"
        total_line = f"Score: NOT ISSUED (proposed {result.get('proposed_total_score', 0)} / {result.get('max_score', 0)} is withheld because {reason})"
    else:
        total_line = f"Total Score: {result.get('total_score', 0)} / {result.get('max_score', 0)}"
    lines = ["=" * 44, "ASSESSMENT FEEDBACK", "=" * 44, "", total_line, ""]
    for label, key in (("OVERALL FEEDBACK", "overall_feedback"), ("STRENGTHS", "strengths"), ("AREAS FOR IMPROVEMENT", "areas_for_improvement")):
        lines.extend([label + ":"])
        value = result.get(key)
        items = value if isinstance(value, list) else ([value] if isinstance(value, str) and value.strip() else [])
        if not items:
            lines.append("  Educator review required; no provider text supplied.")
        else:
            for item in items:
                text = " ".join(str(item).split())
                if text:
                    lines.append("  - " + text)
        lines.append("")
    criterion_heading = "CRITERION FEEDBACK (proposed marks are not issued):" if result.get("total_score") is None else "CRITERION FEEDBACK:"
    lines.extend([criterion_heading])
    for criterion, score in (result.get("criteria_scores") or {}).items():
        lines.append(f"  - {criterion}: {score.get('score', 0)}/{score.get('max_score', 0)} — {score.get('feedback', '')}")
    flags = result.get("marking_quality_flags") or []
    if flags:
        lines.extend(["", "MARKING QUALITY FLAGS — DO NOT ACCEPT PROPOSED SCORE WITHOUT EDUCATOR REVIEW:"])
        for flag in flags:
            lines.append(f"  - {flag.get('criterion')}: {flag.get('detail')} Source: {flag.get('source_quote')}")
    if score_is_blocked(result):
        lines.extend(["", "SCORING BLOCK: " + (result.get("score_withheld_reason") or "resolve all marking quality flags before accepting proposed marks.")])
    lines.extend(["", "Review status: PROVISIONAL — educator must verify source answer, rubric interpretation, score, and feedback before release.", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def assessment_response_is_complete(raw: dict[str, Any], rubric: dict[str, Any], *, submission_text: str | None = None) -> bool:
    if raw.get("error") or not isinstance(raw.get("criteria_scores"), dict):
        return False
    if not rubric.get("criteria") or not raw["criteria_scores"]:
        return False

    normalized = normalize_assessment(dict(raw), rubric)
    if submission_text is not None:
        retain_exact_source_quotes(normalized, rubric, submission_text)
    if not all(item["feedback"] for item in normalized["criteria_scores"].values()):
        return False
    for name, item in normalized["criteria_scores"].items():
        criterion = next((row for row in rubric.get("criteria") or [] if str(row.get("name") or "") == name), None)
        if criterion and criterion.get("marking_points"):
            expected_ids = {str(point.get("point_id") or "") for point in criterion.get("marking_points") or []}
            returned_ids = {str(point.get("point_id") or "") for point in item.get("point_scores") or []
                            if point.get("score") is not None}
            if item.get("pointwise_complete") is not True or returned_ids != expected_ids:
                return False
    if submission_text is not None:
        source = " ".join(submission_text.split())
        for item in normalized["criteria_scores"].values():
            quotes = item.get("quotes")
            if not isinstance(quotes, list) or not quotes:
                return False
            if any(not isinstance(quote, str) or not quote.strip() or " ".join(quote.split()) not in source for quote in quotes):
                return False
        # Criterion-level quotes locate an answer but do not support its
        # individual marks. Keep the response incomplete until every positive
        # memo-point proposal has an exact quote from that question's answer.
        if point_quote_grounding_flags(normalized, rubric, submission_text):
            return False
    return True


def pointwise_repair_rubric(raw: dict[str, Any], rubric: dict[str, Any], *, submission_text: str | None = None) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Retry omitted memo points and positive proposals without exact answer evidence."""
    normalized = normalize_assessment(copy.deepcopy(raw), rubric)
    quote_flags = point_quote_grounding_flags(normalized, rubric, submission_text or "") if submission_text is not None else []
    quote_repairs = {
        (str(flag.get("criterion") or ""), str(flag.get("memo_point_id") or ""))
        for flag in quote_flags
    }
    repair = copy.deepcopy(rubric)
    repair_criteria: list[dict[str, Any]] = []
    missing_by_criterion: dict[str, list[dict[str, Any]]] = {}
    total_marks = 0.0
    for criterion in rubric.get("criteria") or []:
        name = str(criterion.get("name") or "")
        score = normalized.get("criteria_scores", {}).get(name, {})
        returned = {
            str(point.get("point_id") or "")
            for point in score.get("point_scores") or []
            if point.get("score") is not None
        }
        missing = [
            copy.deepcopy(point) for point in criterion.get("marking_points") or []
            if (str(point.get("point_id") or "") not in returned
                or (str(criterion.get("question") or name.split(":", 1)[0]).strip(), str(point.get("point_id") or "")) in quote_repairs)
        ]
        if not missing:
            continue
        repair_criterion = copy.deepcopy(criterion)
        repair_criterion["marking_points"] = missing
        repair_criterion["weight"] = sum(float(point.get("marks") or 0) for point in missing)
        repair_criterion["levels"] = {}
        repair_criteria.append(repair_criterion)
        missing_by_criterion[name] = missing
        total_marks += repair_criterion["weight"]
    repair["criteria"] = repair_criteria
    repair["total_marks"] = total_marks
    return repair, missing_by_criterion


def merge_pointwise_repair(raw: dict[str, Any], repair_raw: dict[str, Any],
                           missing_by_criterion: dict[str, list[dict[str, Any]]], *,
                           rubric: dict[str, Any], submission_text: str) -> dict[str, Any]:
    """Merge individually valid repair points; one bad quote cannot discard good rows."""
    merged = copy.deepcopy(raw)
    repair_scores = repair_raw.get("criteria_scores") or {}
    base_scores = merged.setdefault("criteria_scores", {})
    for name, missing_points in missing_by_criterion.items():
        repair_item = repair_scores.get(name)
        base_item = base_scores.get(name)
        if not isinstance(repair_item, dict) or not isinstance(base_item, dict):
            continue
        def point_map(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
            points = item.get("point_scores") or []
            if isinstance(points, dict):
                return {
                    str(key): ({**copy.deepcopy(value), "point_id": str(key)} if isinstance(value, dict)
                               else {"point_id": str(key), "score": value})
                    for key, value in points.items()
                }
            return {str(point.get("point_id") or ""): copy.deepcopy(point)
                    for point in points if isinstance(point, dict)}
        base_points = point_map(base_item)
        repair_points = point_map(repair_item)
        criterion = next((row for row in rubric.get("criteria") or [] if str(row.get("name") or "") == name), {})
        question_id = str(criterion.get("question") or name.split(":", 1)[0]).strip()
        answer = question_answer_block(submission_text, question_id) or submission_text
        normalized_answer = " ".join(answer.split())
        for point in missing_points:
            point_id = str(point.get("point_id") or "")
            candidate = repair_points.get(point_id)
            if candidate is None:
                continue
            try:
                candidate_score = float(candidate.get("score"))
                maximum = float(point.get("marks") or 0)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(candidate_score) or candidate_score < 0 or candidate_score > maximum:
                continue
            quotes = candidate.get("quotes") or []
            if isinstance(quotes, str):
                quotes = [quotes]
            exact_quotes = [" ".join(str(value).split()) for value in quotes
                            if isinstance(value, str) and str(value).strip()]
            if candidate_score > 0 and not any(value in normalized_answer for value in exact_quotes):
                base_point = base_points.get(point_id)
                if base_point is not None:
                    rejected = list(base_point.get("unbound_quote_candidates") or [])
                    rejected.extend(value[:500] for value in exact_quotes if value not in rejected)
                    base_point["unbound_quote_candidates"] = rejected[:5]
                continue
            candidate["quotes"] = [value for value in exact_quotes if value in normalized_answer]
            base_points[point_id] = candidate
        base_item["point_scores"] = list(base_points.values())
        if not base_item.get("quotes") and repair_item.get("quotes"):
            base_item["quotes"] = copy.deepcopy(repair_item["quotes"])
    return merged


def answer_key_conflict_flags(rubric: dict[str, Any], submission_text: str) -> list[dict[str, str]]:
    """Flag explicit conflicts with source-bound motion concepts for educator review."""
    flags: list[dict[str, str]] = []
    heading_pattern = re.compile(r"(?im)^[ \t]*(?:question[ \t]+)?(?P<id>\d+(?:\.\d+)+)(?=[ \t.):\]-]|$)")
    headings = list(heading_pattern.finditer(submission_text))
    answer_blocks: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(submission_text)
        answer_blocks.setdefault(heading.group("id"), submission_text[heading.start():end].strip())
    for criterion in rubric.get("criteria") or []:
        criterion_id = str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0]).strip()
        memo = " ".join([
            str(criterion.get("memo") or ""),
            str(criterion.get("question_prompt") or ""),
            " ".join(str(point.get("point") or "") for point in criterion.get("marking_points") or [] if isinstance(point, dict)),
            str(criterion.get("name") or ""),
        ]).casefold()
        has_path_definition = "path travelled" in memo or "path length" in memo
        has_position_change_definition = "initial to final position" in memo or "change in position" in memo
        has_distance_rubric = all(("distance" in memo, "displacement" in memo,
                                   has_path_definition, has_position_change_definition))
        has_graph_rubric = "position-time" in memo and "velocity-time" in memo and "signed area" in memo
        if not (has_distance_rubric or has_graph_rubric):
            continue
        # A source memo can bind a concrete straight-path distance. If a
        # numbered learner answer explicitly gives a different distance in a
        # recognized metric unit, hold the proposals for a subject educator.
        # This is a review flag only: it never edits a mark or infers credit.
        answer_block = answer_blocks.get(criterion_id, "")
        if not answer_block:
            # Never borrow evidence from another response when this numbered
            # answer cannot be resolved in the learner's source document.
            continue
        learner_distance = re.search(
            r"\bdistance\b[^.;\n]{0,45}?(?:(?:is|equals?|was)\s*|[:=]\s*)"
            r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|km|m)\b",
            answer_block, re.I,
        )
        if learner_distance:
            unit_to_metres = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}
            learner_metres = float(learner_distance.group("value")) * unit_to_metres[learner_distance.group("unit").casefold()]
            for point in criterion.get("marking_points") or []:
                point_text = str(point.get("point") or "")
                if not re.search(r"\bcalculat(?:e|es|ed|ing)\b", point_text, re.I):
                    continue
                expected_distance = re.search(
                    r"\bdistance\b[^.;\n]{0,50}?(?P<value>[+-]?\d+(?:\.\d+)?)\s*"
                    r"(?P<unit>mm|cm|km|m)\b",
                    point_text, re.I,
                )
                if not expected_distance:
                    continue
                expected_metres = float(expected_distance.group("value")) * unit_to_metres[expected_distance.group("unit").casefold()]
                if abs(learner_metres - expected_metres) > 1e-9:
                    flags.append({
                        "code": "answer_key_distance_value_conflict_review_required",
                        "criterion": criterion_id,
                        "detail": (f"The learner's numbered answer gives distance {learner_distance.group('value')} "
                                   f"{learner_distance.group('unit')}; memo point {point.get('point_id')} specifies "
                                   f"{expected_distance.group('value')} {expected_distance.group('unit')}. "
                                   "A Physical Sciences educator must resolve the discrepancy and review every proposed point."),
                        "source_quote": learner_distance.group(0).strip(),
                        "memo_point_id": str(point.get("point_id") or ""),
                        "memo_point": point_text,
                        "learner_value_metres": learner_metres,
                        "memo_value_metres": expected_metres,
                        "conflicts": ["distance_value_mismatch"],
                        "resolution_eligible": False,
                    })
                    break
        # Catch either side of the common definition swap. Earlier handling
        # required both reversed definitions in one exact wording, which let a
        # single explicit misconception pass unflagged.
        reversed_distance = re.search(
            r"\bdistance\b.{0,100}\b(?:ends? from where .*started|start to finish|initial to final position|"
            r"(?:is|means|equals|defined as|refers to)\s+(?:the\s+)?(?:change in position|displacement|"
            r"difference between (?:the )?initial and final positions|endpoint separation))\b",
            answer_block, re.I,
        )
        reversed_displacement = re.search(
            r"\bdisplacement\b.{0,100}\b(?:total path travelled|(?:is|means|equals|defined as|refers to)\s+"
            r"(?:the\s+)?(?:total (?:distance|path)|distance travelled|length of the path|path length))\b",
            answer_block, re.I,
        )
        if reversed_distance or reversed_displacement:
            quotes = [match.group(0).strip() for match in (reversed_distance, reversed_displacement) if match]
            flags.append({
                "code": "answer_key_definition_conflict_review_required",
                "criterion": str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0]),
                "detail": "Learner wording appears to assign endpoint change to distance or total path length to displacement, contrary to the supplied memo. The proposed criterion score is not accepted; educator must resolve the concept.",
                "source_quote": " … ".join(quotes),
                "conflicts": [name for name, match in (("distance_defined_as_endpoint_change", reversed_distance),
                                                        ("displacement_defined_as_path_length", reversed_displacement)) if match],
                "resolution_eligible": False,
            })
        if has_graph_rubric:
            graph_conflicts = []
            for pattern, detail in (
                (r"\bposition[- ]time graph\s+(?:shows?|plots?)\s+(?:the\s+)?speed\b",
                 "position-time graph is described as showing speed instead of position"),
                (r"\bvelocity[- ]time graph\s+(?:shows?|plots?)\s+(?:the\s+)?(?:path|distance) travelled\b",
                 "velocity-time graph is described as showing travelled path instead of velocity"),
            ):
                for match in re.finditer(pattern, answer_block, re.I):
                    prefix = answer_block[max(0, match.start() - 24):match.start()]
                    if re.search(r"\b(?:not|never|doesn't|does not|isn't|is not)\s+$", prefix, re.I):
                        continue
                    graph_conflicts.append((match.group(0), detail))
            if graph_conflicts:
                quotes = list(dict.fromkeys(match for match, _ in graph_conflicts))
                details = list(dict.fromkeys(detail for _, detail in graph_conflicts))
                flags.append({
                    "code": "learner_quote_conflicts_with_motion_graph_rubric",
                    "criterion": str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0]),
                    "detail": "The learner's source submission explicitly assigns a motion-graph quantity to the wrong graph. Reconcile the answer and every point proposal with a Physical Sciences educator before use.",
                    "source_quote": " … ".join(quotes),
                    "conflicts": details,
                    "resolution_eligible": False,
                })
    return flags


def point_quote_grounding_flags(result: dict[str, Any], rubric: dict[str, Any], submission_text: str) -> list[dict[str, Any]]:
    """Require each positive point proposal to cite an exact quote from its answer block."""
    headings = list(re.finditer(r"(?im)^[ \t]*(?:question[ \t]+)?(?P<id>\d+(?:\.\d+)+)(?=[ \t.):\]-]|$)", submission_text))
    blocks: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(submission_text)
        blocks.setdefault(heading.group("id"), submission_text[heading.start():end])
    flags: list[dict[str, Any]] = []
    criteria_scores = result.get("criteria_scores") or {}
    for criterion in rubric.get("criteria") or []:
        if not isinstance(criterion, dict):
            continue
        question_id = str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0]).strip()
        criterion_name = str(criterion.get("name") or "")
        proposal = criteria_scores.get(criterion_name) or {}
        if not isinstance(proposal, dict):
            continue
        answer_block = " ".join(blocks.get(question_id, "").split())
        for point in proposal.get("point_scores") or []:
            if not isinstance(point, dict) or point.get("score") is None or float(point.get("score") or 0) <= 0:
                continue
            quotes = point.get("quotes") or []
            if isinstance(quotes, str):
                quotes = [quotes]
            exact = [" ".join(str(q).split()) for q in quotes if isinstance(q, str) and str(q).strip()]
            bound = [quote for quote in exact if quote in answer_block]
            if not bound:
                flags.append({
                    "code": "positive_point_proposal_lacks_question_scoped_quote",
                    "criterion": question_id,
                    "memo_point_id": str(point.get("point_id") or ""),
                    "proposed_mark": point.get("score"),
                    "detail": "A positive memo-point proposal has no exact learner quotation bound to this question's answer block. Keep the mark unissued until an educator checks the answer against the source memo.",
                    "resolution_eligible": False,
                })
    return flags


def question_answer_block(submission_text: str, question_id: str) -> str:
    """Return one numbered learner answer while retaining its original heading."""
    headings = list(re.finditer(
        r"(?im)^[ \t]*(?:question[ \t]+)?(?P<id>\d+(?:\.\d+)+)(?=[ \t.):\]-]|$)",
        submission_text,
    ))
    for index, heading in enumerate(headings):
        if heading.group("id").strip() != str(question_id).strip():
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(submission_text)
        return submission_text[heading.start():end].strip()
    return ""


def canonicalize_pointwise_response(raw: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    """Wrap direct single-criterion provider JSON and strip only an exact POINT_ prefix."""
    normalized = copy.deepcopy(raw)
    scores = normalized.get("criteria_scores")
    if not isinstance(scores, dict):
        scores = {}
        normalized["criteria_scores"] = scores
    for criterion in rubric.get("criteria") or []:
        if not isinstance(criterion, dict) or not criterion.get("marking_points"):
            continue
        name = str(criterion.get("name") or "")
        item = scores.get(name)
        if not isinstance(item, dict):
            item = normalized.get(name)
        if not isinstance(item, dict):
            continue
        expected = {str(point.get("point_id") or "") for point in criterion.get("marking_points") or []}
        candidate = item.get("point_scores")
        if not isinstance(candidate, dict):
            candidate = {
                key: value for key, value in item.items()
                if isinstance(key, str) and (key in expected or key.removeprefix("POINT_") in expected)
            }
        if not isinstance(candidate, dict) or not candidate:
            continue
        canonical: dict[str, Any] = {}
        ambiguous = False
        for point_id, value in candidate.items():
            key = str(point_id)
            if key not in expected and key.startswith("POINT_") and key[6:] in expected:
                key = key[6:]
            if key not in expected or key in canonical:
                ambiguous = True
                break
            canonical[key] = value
        if ambiguous:
            continue
        adapted = copy.deepcopy(item)
        adapted.pop("point_scores", None)
        for point_id in list(adapted):
            if point_id in expected or (isinstance(point_id, str) and point_id.startswith("POINT_") and point_id[6:] in expected):
                adapted.pop(point_id, None)
        adapted["point_scores"] = canonical
        scores[name] = adapted
    return normalized


def assess_pointwise_question_scoped(hymark: Any, submission_text: str, rubric: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Score each pointwise criterion separately to keep local model output bounded."""
    aggregate: dict[str, Any] = {"criteria_scores": {}}
    errors: list[str] = []
    for criterion in rubric.get("criteria") or []:
        if not isinstance(criterion, dict) or not criterion.get("marking_points"):
            continue
        name = str(criterion.get("name") or "")
        question_id = str(criterion.get("question") or name.split(":", 1)[0]).strip()
        answer = question_answer_block(submission_text, question_id) or submission_text
        one_rubric = copy.deepcopy(rubric)
        one_rubric["criteria"] = [copy.deepcopy(criterion)]
        one_rubric["total_marks"] = sum(float(point.get("marks") or 0) for point in criterion.get("marking_points") or [])
        instructions = (
            "Assess only the supplied numbered answer against this one criterion and its memo points. "
            "Return every memo point ID exactly once with a score from zero to its listed marks. "
            "For each positive point include one concise verbatim quote copied from this answer that supports that point. "
            "Do not infer missing content. Return JSON only; all marks are provisional for educator review."
        )
        # Qwen3's hybrid reasoning mode can be disabled for bounded local
        # latency comparisons. This prompt switch is opt-in and only applies
        # to Qwen 3 models; the production/default scoring path is unchanged.
        model_name = str(os.getenv("HOMS_AI_MODEL") or "").casefold()
        if (os.getenv("HOMS_AI_NO_THINK", "").strip().casefold() in {"1", "true", "yes"}
                and model_name.startswith("qwen3")):
            instructions = "/no_think\n" + instructions
        try:
            result = asyncio.run(hymark.assess_with_ai(answer, one_rubric, instructions))
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}")
            continue
        result = canonicalize_pointwise_response(result, one_rubric)
        retain_exact_source_quotes(result, one_rubric, answer)
        item = (result.get("criteria_scores") or {}).get(name)
        if isinstance(item, dict):
            aggregate["criteria_scores"][name] = item
        else:
            # Preserve an empty slot so validated bounded repairs can merge
            # pointwise even when the provider omitted the criterion object.
            aggregate["criteria_scores"][name] = {"point_scores": {}}
            errors.append(f"{name}: missing criterion response")
    if not aggregate["criteria_scores"] and errors:
        aggregate["error"] = "Question-scoped scoring returned no criterion responses."
    return aggregate, errors


def rubric_mark_allocation_flags(rubric: dict[str, Any]) -> list[dict[str, str]]:
    """Withhold scores when criterion totals have no source-bound point allocation."""
    return [
        {
            "code": "rubric_pointwise_mark_allocation_missing",
            "criterion": str(criterion.get("name") or "Unnamed criterion").split(":", 1)[0],
            "detail": "This criterion has a total weight but no pointwise marking allocation. Provide source-bound marking points and marks before accepting a numerical proposal.",
            "source_quote": "",
        }
        for criterion in rubric.get("criteria") or []
        if not isinstance(criterion.get("marking_points"), list) or not criterion.get("marking_points")
    ]


def feedback_quote_consistency_flags(result: dict[str, Any], rubric: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Flag feedback that contradicts an exact learner quote on basic evidence."""
    flags: list[dict[str, str]] = []
    missing_direction = re.compile(
        r"\b(?:should|must|needs? to|could)\b.{0,100}\b(?:state|mention|include|give|specify)\b"
        r".{0,80}\b(?:direction|north|south|east|west)\b",
        re.I,
    )
    directions = re.compile(r"\b(?:north|south|east|west)\b", re.I)
    # Only treat explicit absence as a contradiction. Coaching such as
    # "could be more explicit" can still be valid when some quantities carry
    # units but others in the same calculation do not.
    missing_unit = re.compile(
        r"\b(?:missing|omitted|no|lacks?)\b.{0,60}\b(?:si\s+)?units?\b|"
        r"\b(?:unit|units)\s+(?:is|are)\s+missing\b",
        re.I,
    )
    requests_unit = re.compile(
        r"\b(?:should|must|needs? to|could(?: benefit from)?)\b.{0,100}"
        r"\b(?:provide|include|mention|state|specify|give)\b.{0,60}"
        r"\b(?:the\s+)?(?:si\s+)?units?\b|"
        r"\b(?:more|a)\s+explicit\s+(?:mention|statement|reference)\s+"
        r"(?:of|to)\s+(?:the\s+)?(?:si\s+)?units?\b",
        re.I,
    )
    physical_unit = re.compile(
        r"(?<![A-Za-z])(?:m\s*[·⋅/]\s*s\s*(?:\^?\s*[-−]?\s*1|⁻¹|−1)?|"
        r"m\s*s\s*(?:[-−]\s*1|⁻¹)|km\s*/\s*h|kg|N|J|W|V|A|Hz|°C|K|Pa|C)(?![A-Za-z])",
        re.I,
    )
    for criterion, item in (result.get("criteria_scores") or {}).items():
        feedback = str(item.get("feedback") or "")
        quotes = item.get("quotes") or []
        quote = " ".join(str(value) for value in quotes if isinstance(value, str))
        criterion_id = str(criterion).split(":", 1)[0]
        rubric_criterion = next((
            " ".join([
                str(row.get("name") or ""),
                str(row.get("question_prompt") or ""),
                " ".join(str(point.get("point") or "") for point in row.get("marking_points") or [] if isinstance(point, dict)),
                str(row.get("memo") or ""),
            ]) for row in (rubric or {}).get("criteria") or []
            if str(row.get("name") or "").split(":", 1)[0] == criterion_id
        ), "")
        if missing_direction.search(feedback) and quote and directions.search(quote):
            expected_directions = {value.casefold() for value in directions.findall(rubric_criterion)}
            quoted_directions = {value.casefold() for value in directions.findall(quote)}
            flags.append({
                "code": "feedback_claims_direction_missing_despite_exact_quote",
                "criterion": criterion_id,
                "detail": "The criterion feedback says a direction is missing, but the exact learner quotation contains a cardinal direction. Verify the criterion score and feedback before release.",
                "source_quote": quote,
                "original_feedback": feedback,
                "resolution_eligible": bool(expected_directions & quoted_directions),
            })
        normalized_quote = re.sub(r"\s+", " ", quote.casefold())
        rubric_requires_graph_relationships = (
            "position-time" in rubric_criterion.casefold()
            and "velocity-time" in rubric_criterion.casefold()
            and "signed area" in rubric_criterion.casefold()
        )
        graph_conflicts = []
        if rubric_requires_graph_relationships:
            if re.search(r"\bposition[- ]time graph\s+(?:shows?|plots?)\s+(?:the\s+)?speed\b", normalized_quote):
                graph_conflicts.append("position-time graph is described as showing speed instead of position; its gradient represents velocity")
            if re.search(r"\bvelocity[- ]time graph\s+(?:shows?|plots?)\s+(?:the\s+)?(?:path|distance) travelled\b", normalized_quote):
                graph_conflicts.append("velocity-time graph is described as showing travelled path instead of velocity; signed area represents displacement")
        has_source_graph_conflict = any(
            flag.get("code") == "learner_quote_conflicts_with_motion_graph_rubric"
            and str(flag.get("criterion") or "") == criterion_id
            for flag in result.get("marking_quality_flags") or []
        )
        if graph_conflicts and not has_source_graph_conflict:
            flags.append({
                "code": "learner_quote_conflicts_with_motion_graph_rubric",
                "criterion": criterion_id,
                "detail": "The exact learner quotation contains a graph relationship that may conflict with the rubric. A subject educator must resolve the concept, feedback, and proposed mark before use.",
                "source_quote": quote,
                "original_feedback": feedback,
                "conflicts": graph_conflicts,
                "resolution_eligible": False,
            })
        if quote and (missing_unit.search(feedback) or requests_unit.search(feedback)) and physical_unit.search(quote):
            explicit_absence = bool(missing_unit.search(feedback))
            flags.append({
                "code": "feedback_claims_unit_missing_despite_exact_quote" if explicit_absence else "feedback_requests_unit_clarification_despite_exact_quote",
                "criterion": str(criterion).split(":", 1)[0],
                "detail": "The criterion feedback requests a unit or clearer unit statement while the exact learner quotation already contains a recognizable physical-unit expression. Check whether all required units are present and dimensionally correct; do not infer completeness from token presence.",
                "source_quote": quote,
                "original_feedback": feedback,
            })
    return flags


def replace_contradictory_draft_feedback(result: dict[str, Any]) -> None:
    """Correct contradictory prose without treating the disputed mark as resolved."""
    by_question = {str(key).split(":", 1)[0]: value for key, value in (result.get("criteria_scores") or {}).items()}
    for flag in result.get("marking_quality_flags") or []:
        criterion = str(flag.get("criterion") or "")
        item = by_question.get(criterion)
        if item is None:
            continue
        # Replacing a sentence can repair the feedback shown to a learner, but
        # it cannot establish that the proposed point score is correct. Keep
        # every such flag unresolved for score withholding until an educator
        # adjudicates the point against the original answer and memo.
        flag["feedback_replacement_applied"] = True
        flag["scoring_resolution_state"] = "UNRESOLVED_EDUCATOR_REVIEW"
        if flag.get("code") == "feedback_claims_direction_missing_despite_exact_quote":
            if flag.get("resolution_eligible") is True:
                item["feedback"] = "The exact quoted answer includes the direction required by the rubric. The direction is present; educator review of the proposed mark is still required."
                flag["resolution_state"] = "FEEDBACK_CORRECTED_MARK_UNRESOLVED"
                flag["resolution_basis"] = "Exact learner quotation contains the cardinal direction named in the rubric, while draft feedback claimed that direction was absent. Correcting feedback does not adjudicate the proposed mark."
            else:
                item["feedback"] = "REVIEW REQUIRED: The direction feedback conflicts with the source quote; confirm the rubric's expected direction and proposed mark before use."
        elif flag.get("code") == "feedback_claims_unit_missing_despite_exact_quote":
            item["feedback"] = "The exact quoted answer contains a unit token, so a blanket claim that units are absent is inaccurate. Educator review must still verify dimensional correctness and the proposed mark."
            flag["resolution_state"] = "FEEDBACK_CORRECTED_MARK_UNRESOLVED"
            flag["resolution_basis"] = "Exact learner quotation contains a unit token. This does not establish unit completeness, dimensional correctness, or the proposed mark."
        elif flag.get("code") == "feedback_requests_unit_clarification_despite_exact_quote":
            item["feedback"] = "The exact quoted answer already includes a unit expression. Educator review must check that every required unit is present and dimensionally correct; the proposed mark remains provisional."
            flag["resolution_state"] = "FEEDBACK_CORRECTED_MARK_UNRESOLVED"
            flag["resolution_basis"] = "The model requested a clearer unit statement despite an exact quote containing a unit expression. This does not prove unit completeness, dimensional correctness, or the proposed mark."
        elif flag.get("code") == "learner_quote_conflicts_with_motion_graph_rubric":
            item["feedback"] = "REVIEW REQUIRED: The exact quoted graph relationships may conflict with the rubric. A Physical Sciences educator must resolve the concepts and proposed mark before learner feedback is released."


def find_question_paper(input_dir: Path) -> Path | None:
    """Find an explicitly named question paper without mistaking a memo for one."""
    candidates = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".md", ".docx", ".pdf"}]
    return next((p for p in sorted(candidates) if "question_paper" in p.stem.casefold().replace("-", "_").replace(" ", "_")), None)


def zip_dir(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file() and path.resolve() != target.resolve():
                zf.write(path, path.relative_to(source))


def clear_inherited_assessment_outputs(job_dir: Path) -> list[str]:
    """Remove generated files copied from an earlier run before a new score starts."""
    stale_names = (
        "results.json", "marks.csv", "gradebook_marked.csv",
        "LECTURER_REVIEW_SUMMARY.md", "HOMS_HYMARK_REVIEW_PACK.zip",
        "HOMS_HYMARK_BATCH_RECEIPT.json", "rubric.hymark.normalized.json",
    )
    removed = []
    for name in stale_names:
        path = job_dir / name
        if path.is_file() or path.is_symlink():
            path.unlink()
            removed.append(name)
    feedback = job_dir / "feedback"
    if feedback.is_dir():
        shutil.rmtree(feedback)
        removed.append("feedback/")
    return removed


def assessment_input_hashes(job_dir: Path) -> dict[str, str]:
    """Fingerprint all source material that can affect assessment execution."""
    inputs = [job_dir / "rubric.json", job_dir / "memo.md", job_dir / "ASSESSMENT_BINDING_RECEIPT.json",
              job_dir / "gradebook.csv"]
    uploads = job_dir / "uploads"
    if uploads.is_dir():
        inputs.extend(path for path in uploads.rglob("*") if path.is_file())
    inputs.extend(path for path in job_dir.rglob("*") if path.is_file()
                  and path != job_dir / "gradebook.csv"
                  and path.name != "rubric.hymark.normalized.json"
                  and "feedback" not in path.relative_to(job_dir).parts
                  and ("question_paper" in path.stem.casefold().replace("-", "_").replace(" ", "_")
                       or path.name == "ASSESSMENT_BINDING_RECEIPT.json"))
    result = {}
    for path in sorted(set(path for path in inputs if path.is_file())):
        result[path.relative_to(job_dir).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def write_marked_gradebook(job_dir: Path, results: list[dict[str, Any]]) -> Path | None:
    gradebook = job_dir / "gradebook.csv"
    if not gradebook.exists():
        return None
    by_id: dict[str, dict[str, Any]] = {}
    for result in results:
        full = str(result.get("student_id", ""))
        by_id[full] = result
        by_id[full.split("_", 1)[0]] = result

    with gradebook.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for field in ["grade", "percentage", "provider", "requires_review"]:
        if field not in fieldnames:
            fieldnames.append(field)
    for row in rows:
        result = by_id.get(str(row.get("student_id", "")).strip())
        if result:
            if result.get("total_score") is None:
                row["grade"] = ""
                row["percentage"] = ""
            else:
                row["grade"] = str(result.get("total_score", ""))
                row["percentage"] = str(result.get("percentage", ""))
            row["provider"] = str(result.get("provider", ""))
            row["requires_review"] = "yes"

    marked = job_dir / "gradebook_marked.csv"
    with marked.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return marked


def run_batch(
    input_dir: Path,
    out_root: Path,
    secret_file: Path = DEFAULT_SECRET_FILE,
    backend_path: Path = DEFAULT_HYMARK_BACKEND,
    provider_name: str = "ollama",
    model: str = "",
) -> dict[str, Any]:
    started = time.perf_counter()
    provider = configure_provider(secret_file, provider_name, model)
    hymark = load_hymark_backend(backend_path)

    out_root.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", input_dir.name).strip("-").lower()
    job_id = "homs-hymark-" + stem + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_dir = out_root / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    shutil.copytree(input_dir, job_dir)
    inherited_outputs_removed = clear_inherited_assessment_outputs(job_dir)
    input_file_hashes = assessment_input_hashes(job_dir)

    uploads = job_dir / "uploads"
    if not uploads.exists():
        raise FileNotFoundError(f"Input folder must contain uploads/: {input_dir}")
    rubric_path = job_dir / "rubric.json"
    if not rubric_path.exists():
        raise FileNotFoundError(f"Input folder must contain rubric.json: {input_dir}")
    rubric = ensure_rubric_levels(json.loads(rubric_path.read_text(encoding="utf-8")))
    (job_dir / "rubric.hymark.normalized.json").write_text(json.dumps(rubric, indent=2), encoding="utf-8")
    instructions = (job_dir / "memo.md").read_text(encoding="utf-8", errors="ignore") if (job_dir / "memo.md").exists() else ""
    instructions += (
        "\n\nPOINT-LEVEL EVIDENCE REQUIREMENT: For every positive memo-point mark, include in that point's `quotes` "
        "one concise verbatim span copied from the learner's answer to the same numbered question and specifically "
        "supporting that point. Do not copy a quote from another question, paraphrase, or use the criterion-wide "
        "quote as a substitute. If no exact supporting span exists, leave the quote list empty and do not guess; "
        "the proposal will be held for educator review. A quote is traceability evidence, not proof that the mark is correct."
    )
    question_paper = find_question_paper(job_dir)

    feedback_dir = job_dir / "feedback"
    feedback_dir.mkdir(exist_ok=True)
    results: list[dict[str, Any]] = []
    provider_errors: list[str] = []

    paper_path = question_paper.resolve() if question_paper is not None else None
    for submission in sorted(
        p for p in uploads.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".txt", ".md", ".docx", ".pdf"}
        and (paper_path is None or p.resolve() != paper_path)
    ):
        if submission.suffix.lower() in {".txt", ".md"}:
            text = submission.read_text(encoding="utf-8", errors="ignore")
        else:
            text = hymark.extract_document_content(submission)
        provider_failed = False
        recovery_used = False
        pointwise_repair_used = False
        pointwise_repair_point_count = 0
        pointwise_repair_completed = False
        pointwise_repair_attempt_count = 0
        pointwise_repair_response_complete_count = 0
        raw: dict[str, Any] = {}
        grounded = False
        pointwise_mode = any(
            isinstance(criterion, dict) and criterion.get("marking_points")
            for criterion in rubric.get("criteria") or []
        )
        if pointwise_mode:
            raw, scoped_errors = assess_pointwise_question_scoped(hymark, text, rubric)
            if scoped_errors:
                provider_errors.extend(f"{submission.name}: {error}" for error in scoped_errors)
            retain_exact_source_quotes(raw, rubric, text)
            grounded = assessment_response_is_complete(raw, rubric, submission_text=text)
        else:
          for attempt in range(2):
            repair = ""
            if attempt:
                recovery_used = True
                repair = (
                    "\n\nREPAIR: The previous response failed automated completeness or exact-source-quote validation. "
                    "Return a fresh JSON assessment with every exact rubric criterion, concise feedback for each, and "
                    "short verbatim quotes copied exactly from the learner submission. For every positive point mark, "
                    "also cite a concise exact span from that same numbered answer in that point's quotes list. Never invent a quote or infer "
                    "illegible content. Keep all marks provisional for educator review."
                )
            try:
                raw = asyncio.run(hymark.assess_with_ai(text, rubric, instructions + repair))
            except Exception as exc:
                raw = {"error": f"{type(exc).__name__}: provider failure", "total_score": 0, "criteria_scores": {}, "overall_feedback": "Assessment failed.", "annotations": []}
            retain_exact_source_quotes(raw, rubric, text)
            grounded = assessment_response_is_complete(raw, rubric, submission_text=text)
            if grounded:
                break

        # A small model can return the early memo IDs but omit later IDs in a
        # long response. Ask only for those exact missing points once, then
        # merge only validated point IDs. Anything still missing stays held.
        if not grounded and not raw.get("error"):
            repair_rubric, missing_by_criterion = pointwise_repair_rubric(raw, rubric, submission_text=text)
            pointwise_repair_point_count = sum(len(points) for points in missing_by_criterion.values())
            if pointwise_repair_point_count:
                pointwise_repair_used = True
                # Keep retries question-scoped and cap each response at four
                # points. Single-point calls were less complete on this
                # local model, so retain the better-performing group size.
                for criterion_name, missing_points in missing_by_criterion.items():
                    base_criterion_rubric = copy.deepcopy(repair_rubric)
                    base_criterion_rubric["criteria"] = [
                        criterion for criterion in repair_rubric.get("criteria") or []
                        if str(criterion.get("name") or "") == criterion_name
                    ]
                    if not base_criterion_rubric["criteria"]:
                        continue
                    repair_criterion = base_criterion_rubric["criteria"][0]
                    repair_question_id = str(repair_criterion.get("question") or criterion_name.split(":", 1)[0]).strip()
                    repair_answer_text = question_answer_block(text, repair_question_id) or text
                    for offset in range(0, len(missing_points), 4):
                        point_chunk = missing_points[offset:offset + 4]
                        criterion_rubric = copy.deepcopy(base_criterion_rubric)
                        criterion_rubric["criteria"][0]["marking_points"] = point_chunk
                        criterion_rubric["criteria"][0]["weight"] = sum(
                            float(point.get("marks") or 0) for point in point_chunk
                        )
                        criterion_rubric["total_marks"] = criterion_rubric["criteria"][0]["weight"]
                        criterion_missing = {criterion_name: point_chunk}
                        pointwise_repair_attempt_count += 1
                        # The narrowed rubric already contains the authoritative
                        # memo points. Reattaching the full memo defeats the
                        # context reduction and can truncate local-model JSON.
                        repair_instructions = (
                            f"BOUNDED QUESTION-SCOPED REPAIR for criterion {criterion_name}: "
                            "Return every listed memo point ID exactly once, including explicit zero scores. "
                            "For each positive point include one concise exact quote from this question's answer. "
                            "Score only the listed IDs. Do not infer missing content or reuse evidence from another question. "
                            "If uncertain, leave the point unscored. Marks remain provisional for educator review."
                        )
                        try:
                            repair_raw = asyncio.run(
                                hymark.assess_with_ai(repair_answer_text, criterion_rubric, repair_instructions)
                            )
                        except Exception as exc:
                            repair_raw = {"error": f"{type(exc).__name__}: question-scoped repair failed"}
                        repair_raw = canonicalize_pointwise_response(repair_raw, criterion_rubric)
                        retain_exact_source_quotes(repair_raw, criterion_rubric, repair_answer_text)
                        if assessment_response_is_complete(
                            repair_raw, criterion_rubric, submission_text=repair_answer_text
                        ):
                            pointwise_repair_response_complete_count += 1
                        raw = merge_pointwise_repair(
                            raw, repair_raw, criterion_missing,
                            rubric=criterion_rubric, submission_text=repair_answer_text,
                        )
                # A compact tail can remain unreturned after a four-point
                # repair. If at most four points remain across the whole
                # paper, make one bounded, exact-ID recovery pass per point.
                # This is a completeness recovery only: quote grounding,
                # independent repeatability, quality flags, and educator
                # review still control whether any total can be proposed.
                _, residual_by_criterion = pointwise_repair_rubric(raw, rubric, submission_text=text)
                residual_points = sum(len(points) for points in residual_by_criterion.values())
                if 0 < residual_points <= 4:
                    for criterion_name, residual_points_for_criterion in residual_by_criterion.items():
                        base_criterion = copy.deepcopy(rubric)
                        base_criterion["criteria"] = [
                            criterion for criterion in rubric.get("criteria") or []
                            if str(criterion.get("name") or "") == criterion_name
                        ]
                        if not base_criterion["criteria"]:
                            continue
                        base_row = base_criterion["criteria"][0]
                        question_id = str(base_row.get("question") or criterion_name.split(":", 1)[0]).strip()
                        answer_text = question_answer_block(text, question_id) or text
                        for point in residual_points_for_criterion:
                            single_point_rubric = copy.deepcopy(base_criterion)
                            single_point_rubric["criteria"][0]["marking_points"] = [point]
                            single_point_rubric["criteria"][0]["weight"] = float(point.get("marks") or 0)
                            single_point_rubric["total_marks"] = float(point.get("marks") or 0)
                            missing_for_merge = {criterion_name: [point]}
                            pointwise_repair_attempt_count += 1
                            instructions_for_point = (
                                f"FINAL BOUNDED RECOVERY for criterion {criterion_name}, point {point.get('point_id')}: "
                                "Return this exact memo point ID once with an explicit mark from zero through its maximum. "
                                "For a positive mark, include one concise verbatim supporting quote from this question's answer. "
                                "Do not score any other point, infer absent work, or copy evidence from another question. "
                                "Keep the proposal provisional for educator review."
                            )
                            try:
                                point_raw = asyncio.run(
                                    hymark.assess_with_ai(answer_text, single_point_rubric, instructions_for_point)
                                )
                            except Exception as exc:
                                point_raw = {"error": f"{type(exc).__name__}: final bounded point recovery failed"}
                            point_raw = canonicalize_pointwise_response(point_raw, single_point_rubric)
                            retain_exact_source_quotes(point_raw, single_point_rubric, answer_text)
                            if assessment_response_is_complete(
                                point_raw, single_point_rubric, submission_text=answer_text
                            ):
                                pointwise_repair_response_complete_count += 1
                            raw = merge_pointwise_repair(
                                raw, point_raw, missing_for_merge,
                                rubric=single_point_rubric, submission_text=answer_text,
                            )
                retain_exact_source_quotes(raw, rubric, text)
                grounded = assessment_response_is_complete(raw, rubric, submission_text=text)
                pointwise_repair_completed = grounded

        provider_failed = bool(raw.get("error"))
        if provider_failed:
            provider_errors.append(f"{submission.name}: provider failure after bounded retry; details redacted")
        elif not grounded:
            provider_errors.append(f"{submission.name}: incomplete or ungrounded provider assessment after bounded retry; details redacted")

        retain_exact_source_quotes(raw, rubric, text)
        result = normalize_assessment(raw, rubric)
        repeatability: dict[str, Any]
        if grounded and not provider_failed:
            try:
                if pointwise_mode:
                    repeat_raw, repeat_errors = assess_pointwise_question_scoped(hymark, text, rubric)
                    if repeat_errors:
                        repeat_raw["question_scoped_errors"] = repeat_errors
                else:
                    repeat_raw = asyncio.run(hymark.assess_with_ai(text, rubric, instructions))
            except Exception:
                repeat_raw = {"error": "repeatability provider failure"}
            retain_exact_source_quotes(repeat_raw, rubric, text)
            repeat_grounded = assessment_response_is_complete(repeat_raw, rubric, submission_text=text)
            if repeat_grounded and not repeat_raw.get("error"):
                repeat_assessment = normalize_assessment(repeat_raw, rubric)
                def score_vector(assessment: dict[str, Any]) -> dict[str, float]:
                    vector: dict[str, float] = {}
                    for key, value in (assessment.get("criteria_scores") or {}).items():
                        vector[str(key)] = round(float(value.get("score") or 0), 4)
                        for point in value.get("point_scores") or []:
                            vector[f"{key} [{point.get('point_id')}]" ] = round(float(point.get("score") or 0), 4)
                    return vector

                first_scores = score_vector(result)
                repeat_scores = score_vector(repeat_assessment)
                mismatches = [
                    {"criterion": key, "first_pass_score": first_scores.get(key), "repeat_pass_score": repeat_scores.get(key)}
                    for key in sorted(set(first_scores) | set(repeat_scores))
                    if first_scores.get(key) is None or repeat_scores.get(key) is None
                    or abs(first_scores[key] - repeat_scores[key]) > 0.01
                ]
                repeatability = {
                    "state": "NONREPRODUCIBLE" if mismatches else "MATCHED_TWO_PASS",
                    "selected_provider": provider["selected_provider"],
                    "selected_model": provider["selected_model"],
                    "temperature": float(os.getenv("HOMS_AI_TEMPERATURE", "0.0")),
                    "first_pass_total": result.get("total_score"),
                    "repeat_pass_total": repeat_assessment.get("total_score"),
                    "criterion_mismatches": mismatches,
                }
            else:
                repeatability = {
                    "state": "CHECK_INCOMPLETE",
                    "selected_provider": provider["selected_provider"],
                    "selected_model": provider["selected_model"],
                    "temperature": float(os.getenv("HOMS_AI_TEMPERATURE", "0.0")),
                    "criterion_mismatches": [],
                }
        else:
            repeatability = {
                "state": "CHECK_SKIPPED_UNGROUNDED_FIRST_PASS",
                "selected_provider": provider["selected_provider"],
                "selected_model": provider["selected_model"],
                "temperature": float(os.getenv("HOMS_AI_TEMPERATURE", "0.0")),
                "criterion_mismatches": [],
            }
        result["score_repeatability_check"] = repeatability
        result["student_id"] = submission.stem
        result["submission_file"] = submission.name
        result["provider"] = provider["selected_provider"]
        result["model"] = provider["selected_model"]
        result["requires_review"] = True
        result["source_quote_grounding_passed"] = grounded
        result["bounded_recovery_used"] = recovery_used
        result["pointwise_repair_used"] = pointwise_repair_used
        result["pointwise_repair_point_count"] = pointwise_repair_point_count
        result["pointwise_repair_completed"] = pointwise_repair_completed
        result["pointwise_repair_attempt_count"] = pointwise_repair_attempt_count
        result["pointwise_repair_response_complete_count"] = pointwise_repair_response_complete_count
        result["marking_quality_flags"] = answer_key_conflict_flags(rubric, text)
        result["marking_quality_flags"].extend(rubric_mark_allocation_flags(rubric))
        result["marking_quality_flags"].extend(point_quote_grounding_flags(result, rubric, text))
        result["marking_quality_flags"].extend(feedback_quote_consistency_flags(result, rubric))
        for criterion_name, criterion_result in (result.get("criteria_scores") or {}).items():
            unreturned = criterion_result.get("unreturned_point_ids") or []
            validation = criterion_result.get("pointwise_validation") or {}
            pointwise_incomplete = criterion_result.get("pointwise_complete") is False
            if unreturned or pointwise_incomplete:
                details = []
                if unreturned:
                    details.append("unreturned point IDs: " + ", ".join(unreturned))
                if validation.get("unknown_point_ids"):
                    details.append("unknown point IDs: " + ", ".join(validation["unknown_point_ids"]))
                if validation.get("invalid_mark_point_ids"):
                    details.append("invalid marks for point IDs: " + ", ".join(validation["invalid_mark_point_ids"]))
                result["marking_quality_flags"].append({
                    "code": "incomplete_pointwise_marking_response" if unreturned else "invalid_pointwise_marking_response",
                    "criterion": str(criterion_name).split(":", 1)[0],
                    "detail": "Pointwise marking response is incomplete or invalid (" + "; ".join(details or ["memo point IDs or marks failed validation"]) + "). Unreturned points remain unscored; do not infer zero credit or calculate a criterion or assessment total.",
                    "unreturned_point_ids": unreturned,
                })
        if repeatability["state"] in {"NONREPRODUCIBLE", "CHECK_INCOMPLETE", "CHECK_SKIPPED_UNGROUNDED_FIRST_PASS"}:
            result["marking_quality_flags"].append({
                "code": "score_repeatability_not_established",
                "criterion": "ALL",
                "detail": "Independent local scoring passes did not produce a complete matching score set. Numeric score is withheld until an educator reconciles the proposed marks against the source assessment and marking memo.",
                "repeatability_state": repeatability["state"],
            })
        replace_contradictory_draft_feedback(result)
        # No automated wording repair resolves a disputed mark. Every quality
        # flag stays score-blocking until an educator adjudicates it.
        unresolved_quality_flags = list(result["marking_quality_flags"])
        result["unresolved_marking_quality_flags"] = unresolved_quality_flags
        if unresolved_quality_flags:
            result["proposed_total_score"] = result.get("total_score")
            result["proposed_percentage"] = result.get("percentage")
            result["total_score"] = None
            result["percentage"] = None
            if any(flag.get("code") in {"incomplete_pointwise_marking_response", "invalid_pointwise_marking_response"} for flag in unresolved_quality_flags):
                result["score_status"] = "BLOCKED_INCOMPLETE_POINTWISE_RESPONSE"
                result["score_withheld_reason"] = "One or more source-bound memo point IDs were not returned; a complete criterion and assessment total cannot be calculated."
            else:
                result["score_status"] = "BLOCKED_MARKING_QUALITY_FLAGS"
                result["score_withheld_reason"] = "Resolve the listed source, answer-key, or feedback contradiction flags and have an educator verify the proposed mark."
        if question_paper is None:
            if result.get("proposed_total_score") is None:
                result["proposed_total_score"] = result.get("total_score")
                result["proposed_percentage"] = result.get("percentage")
            result["total_score"] = None
            result["percentage"] = None
            if unresolved_quality_flags:
                result["score_status"] = "BLOCKED_MISSING_PAPER_AND_QUALITY_FLAGS"
                result["score_withheld_reason"] = "The original question paper is missing and marking quality flags also require educator resolution."
            else:
                result["score_status"] = "BLOCKED_MISSING_QUESTION_PAPER"
                result["score_withheld_reason"] = "The original question paper is required to validate answers and issue a proposed mark."
            result["marking_quality_flags"].append({
                "code": "missing_question_paper_score_withheld",
                "criterion": "ALL",
                "detail": "The original question paper was not supplied. Numeric marks are retained only as unissued model proposals and are withheld from gradebook and score fields.",
                "source_quote": "",
            })
        else:
            if not unresolved_quality_flags:
                result["proposed_total_score"] = result.get("total_score")
                result["proposed_percentage"] = result.get("percentage")
                result["total_score"] = None
                result["percentage"] = None
                result["score_status"] = "PROVISIONAL_EDUCATOR_REVIEW_REQUIRED"
                result["score_withheld_reason"] = "An educator must adjudicate the pointwise proposals before a total score or percentage is issued."
        result["score_issued"] = result.get("total_score") is not None and result.get("score_status") == "EDUCATOR_ADJUDICATED"
        results.append(result)

        feedback_path = feedback_dir / f"{submission.stem}_FEEDBACK.txt"
        write_feedback_txt(feedback_path, result)

    with (job_dir / "marks.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "score", "proposed_score", "max_score", "percentage", "proposed_percentage", "score_status", "provider", "requires_review"])
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "student_id": result["student_id"],
                    "score": result["total_score"] if result.get("total_score") is not None else "",
                    "proposed_score": result.get("proposed_total_score", result.get("total_score", "")),
                    "max_score": result["max_score"],
                    "percentage": result["percentage"],
                    "proposed_percentage": result.get("proposed_percentage", result.get("percentage", "")),
                    "score_status": result.get("score_status", "PROVISIONAL_EDUCATOR_REVIEW_REQUIRED"),
                    "provider": result["provider"],
                    "requires_review": "yes",
                }
            )

    marked_gradebook = write_marked_gradebook(job_dir, results)
    (job_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    summary_lines = [
        "# HOMS HyMark Lecturer Review Summary",
        "",
        f"Job: `{job_id}`",
        f"Created: {utc_now()}",
        f"Assessor: HyMark backend `{backend_path}`",
        f"Provider: {provider['selected_provider']} / {provider['selected_model']}",
        "",
        "## Batch Results",
    ]
    for result in results:
        if score_is_blocked(result):
            summary_lines.append(f"- {result['student_id']}: NOT SCORED (proposal withheld; {result.get('score_withheld_reason', 'educator review required')})")
        elif result.get("total_score") is None:
            summary_lines.append(f"- {result['student_id']}: NOT SCORED (proposed {result.get('proposed_total_score')}/{result['max_score']}; educator adjudication required)")
        else:
            summary_lines.append(f"- {result['student_id']}: {result['total_score']}/{result['max_score']} ({result['percentage']}%) — provisional")
    summary_lines.extend(["", "## Review Boundary", "Draft marking-support outputs only. Educator review and approval remain required."])
    if provider_errors:
        summary_lines.extend(["", "## Provider Errors", *[f"- {error}" for error in provider_errors]])
    (job_dir / "LECTURER_REVIEW_SUMMARY.md").write_text("\n".join(summary_lines).strip() + "\n", encoding="utf-8")

    zip_path = job_dir / "HOMS_HYMARK_REVIEW_PACK.zip"
    receipt = {
        "schema": "knowedge.homs_hymark_batch_receipt.v1",
        "created_at": utc_now(),
        "job_id": job_id,
        "status": "completed",
        "input_dir": str(input_dir),
        "input_file_sha256": input_file_hashes,
        "inherited_generated_outputs_removed": inherited_outputs_removed,
        "fresh_output_state": "NO_PRIOR_SCORE_ARTIFACTS_CARRIED_INTO_THIS_RUN",
        "assessor": {
            "name": "HyMark Smart Assessor",
            "backend_path": str(backend_path),
            "prompt_source": "backend.server.assess_with_ai",
        },
        "provider": provider,
        "submissions": len(results),
        "provider_errors": provider_errors,
        "question_paper": str(question_paper) if question_paper else None,
        "score_issuance": (
            "BLOCKED_MISSING_QUESTION_PAPER" if question_paper is None else
            "BLOCKED_MARKING_QUALITY_FLAGS" if any(result.get("score_status") == "BLOCKED_MARKING_QUALITY_FLAGS" for result in results) else
            "PROVISIONAL_EDUCATOR_REVIEW_REQUIRED"
        ),
        "score_issued_count": sum(result.get("score_issued") is True for result in results),
        "score_proposal_count": sum(isinstance(result.get("proposed_total_score"), (int, float)) for result in results),
        "score_field_policy": "TOTALS_AND_PERCENTAGES_REMAIN_BLANK_UNTIL_EDUCATOR_ADJUDICATION",
        "duration_seconds": round(time.perf_counter() - started, 3),
        "outputs": {
            "job_dir": str(job_dir),
            "results": str(job_dir / "results.json"),
            "marks_csv": str(job_dir / "marks.csv"),
            "marked_gradebook": str(marked_gradebook) if marked_gradebook else None,
            "lecturer_summary": str(job_dir / "LECTURER_REVIEW_SUMMARY.md"),
            "review_zip": str(zip_path),
        },
    }
    (job_dir / "HOMS_HYMARK_BATCH_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    zip_dir(job_dir, zip_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a HOMS mirror batch through the HyMark Smart Assessor.")
    parser.add_argument("--input", required=True, help="HOMS job folder with rubric.json and uploads/.")
    parser.add_argument("--out", default="/home/byron/KnowEdge_Microsoft_Mirror/HOMS/done")
    parser.add_argument("--secret-file", default=str(DEFAULT_SECRET_FILE))
    parser.add_argument("--backend", default=str(DEFAULT_HYMARK_BACKEND))
    parser.add_argument("--provider", default="ollama", choices=["ollama", "nim", "nvidia", "nvidia_nim", "openai"])
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    receipt = run_batch(
        Path(args.input).expanduser().resolve(),
        Path(args.out).expanduser().resolve(),
        Path(args.secret_file).expanduser().resolve(),
        Path(args.backend).expanduser().resolve(),
        args.provider,
        args.model,
    )
    print(json.dumps({"status": receipt["status"], "assessor": receipt["assessor"]["name"], "provider": receipt["provider"]["selected_provider"], "outputs": receipt["outputs"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
