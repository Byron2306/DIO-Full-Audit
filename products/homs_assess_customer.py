"""Local-only customer execution route for HOMS Assess marking support."""
from __future__ import annotations

import hashlib
import html
import json
import os
import csv
import math
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from products.professional_evidence_projection import load_packet, homs_assess_projection, write_json
from scripts.run_homs_hymark_batch import DEFAULT_HYMARK_BACKEND, DEFAULT_SECRET_FILE, load_hymark_backend, run_batch, score_is_blocked

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_timezone_aware_iso_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _question_answer_blocks(text: str) -> dict[str, dict[str, Any]]:
    """Extract explicitly numbered learner answer blocks without scoring them."""
    heading = re.compile(r"(?im)^[ \t]*(?:question[ \t]+)?(?P<id>\d+(?:\.\d+)+)(?=[ \t.):\]-]|$)")
    matches = list(heading.finditer(text))
    blocks: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        question_id = match.group("id")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        start = match.start()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        block = text[start:end]
        if block and question_id not in blocks:
            blocks[question_id] = {
                "text": block, "character_start": start, "character_end_exclusive": end,
                "utf8_byte_start": len(text[:start].encode("utf-8")),
                "utf8_byte_end_exclusive": len(text[:end].encode("utf-8")),
                "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest(),
            }
    return blocks


_QUOTE_SUGGESTION_STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "give", "gives", "identifies",
    "include", "includes", "is", "it", "mark", "marks", "of", "or", "point", "states",
    "the", "to", "use", "uses", "with", "correct", "one", "two", "three", "four",
    "five", "six", "seven", "eight", "nine", "ten", "answer", "calculation", "calculates",
}


def suggest_exact_question_source_spans(answer_text: str, memo_point: str, *, limit: int = 2) -> list[dict[str, Any]]:
    """Suggest verbatim answer sentences for educator navigation, never for scoring."""
    point_terms = {
        token.casefold() for token in re.findall(r"[\w]+(?:[·/\-][\w]+)*", memo_point, flags=re.UNICODE)
        if token.casefold() not in _QUOTE_SUGGESTION_STOPWORDS and len(token) > 1
    }
    if not point_terms:
        return []
    # Keep decimals intact while splitting prose into small, verbatim spans.
    spans = re.split(r"(?<=[!?;])\s+|(?<!\d)\.\s+(?=[A-Z0-9])", answer_text.strip())
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, span in enumerate(spans):
        exact = " ".join(span.split())
        normalized = exact.casefold()
        if not exact or normalized in seen:
            continue
        seen.add(normalized)
        answer_terms = {
            token.casefold() for token in re.findall(r"[\w]+(?:[·/\-][\w]+)*", exact, flags=re.UNICODE)
        }
        overlap = point_terms & answer_terms
        if len(overlap) < 2:
            continue
        score = len(overlap) / max(1, len(point_terms))
        ranked.append((score, -index, {
            "text": exact,
            "state": "EXACT_QUESTION_SCOPED_SOURCE_SPAN_SUGGESTION",
            "matched_memo_terms": sorted(overlap),
            "binding_scope": "question_answer_block",
            "not_verified_as_point_evidence": True,
        }))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in ranked[:max(0, limit)]]


def validate_pointwise_adjudication_csv(
    csv_path: str | Path,
    rubric: Mapping[str, Any],
    results: list[dict[str, Any]],
    *,
    customer_packet_fingerprint: str,
    quality_flags_csv: str | Path | None = None,
    source_submissions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate point decisions and reconcile completed educator marks without issuing them."""
    path = Path(csv_path).resolve()
    expected: dict[tuple[str, str, str], dict[str, Any]] = {}
    answer_blocks = {str(student_id): _question_answer_blocks(str(text))
                     for student_id, text in (source_submissions or {}).items()}
    for result in results:
        student_id = str(result.get("student_id") or "")
        scores = result.get("criteria_scores") or {}
        for criterion in rubric.get("criteria") or []:
            criterion_id = str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0])
            score = next((value for key, value in scores.items()
                          if str(key).split(":", 1)[0].strip() == criterion_id), {})
            proposals = {str(row.get("point_id") or ""): row for row in score.get("point_scores") or []}
            answer_block = answer_blocks.get(student_id, {}).get(criterion_id, {})
            answer_text = " ".join(str(answer_block.get("text") or "").split())
            for point in criterion.get("marking_points") or []:
                point_id = str(point.get("point_id") or "")
                proposal = proposals.get(point_id, {})
                quote_values = proposal.get("quotes") or []
                if isinstance(quote_values, str):
                    quote_values = [quote_values]
                model_quote_grounded = any(
                    isinstance(value, str) and " ".join(value.split()) in answer_text
                    for value in quote_values if value.strip()
                )
                expected[(student_id, criterion_id, point_id)] = {
                    "maximum": float(point.get("marks") or 0),
                    "model_proposal": proposal.get("score"),
                    "model_quote_grounded": model_quote_grounded,
                    "answer_block_text": answer_text,
                }
    required_fields = {
        "packet_fingerprint", "student_id", "criterion_id", "point_id", "maximum_marks",
        "model_proposed_marks", "educator_verified_marks", "educator_decision",
        "educator_rationale", "educator_reviewer", "reviewed_at", "educator_verified_source_quote",
    }
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if not required_fields.issubset(fields):
            raise ValueError("adjudication CSV is missing required pointwise fields")
        rows = list(reader)
    observed: dict[tuple[str, str, str], dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    incomplete = unresolved = accepted = changed = 0
    for line_number, row in enumerate(rows, 2):
        key = (str(row.get("student_id") or "").strip(),
               str(row.get("criterion_id") or "").strip(),
               str(row.get("point_id") or "").strip())
        if key not in expected:
            issues.append({"line": line_number, "code": "UNKNOWN_SOURCE_POINT", "key": list(key)})
            continue
        if key in observed:
            issues.append({"line": line_number, "code": "DUPLICATE_SOURCE_POINT", "key": list(key)})
            continue
        observed[key] = row
        if str(row.get("packet_fingerprint") or "").strip() != customer_packet_fingerprint:
            issues.append({"line": line_number, "code": "PACKET_FINGERPRINT_MISMATCH", "key": list(key)})
            continue
        source = expected[key]
        try:
            maximum = float(row.get("maximum_marks") or "nan")
        except (TypeError, ValueError):
            maximum = float("nan")
        if not math.isfinite(maximum) or abs(maximum - source["maximum"]) > 0.001:
            issues.append({"line": line_number, "code": "SOURCE_MAXIMUM_MISMATCH", "key": list(key)})
            continue
        proposal_cell = str(row.get("model_proposed_marks") or "").strip()
        source_proposal = source["model_proposal"]
        if source_proposal is None:
            proposal_matches = not proposal_cell and str(row.get("model_state") or "") == "UNRETURNED_UNSCORED"
        else:
            try:
                proposal_matches = (
                    bool(proposal_cell)
                    and abs(float(proposal_cell) - float(source_proposal)) <= 0.001
                    and str(row.get("model_state") or "") == "PROPOSAL_REQUIRES_EDUCATOR_VERIFICATION"
                )
            except (TypeError, ValueError):
                proposal_matches = False
        if not proposal_matches:
            issues.append({"line": line_number, "code": "MODEL_PROPOSAL_MISMATCH", "key": list(key)})
            continue
        decision = str(row.get("educator_decision") or "").strip().upper()
        entered = str(row.get("educator_verified_marks") or "").strip()
        rationale = str(row.get("educator_rationale") or "").strip()
        reviewer = str(row.get("educator_reviewer") or "").strip()
        reviewed_at = str(row.get("reviewed_at") or "").strip()
        if not decision and not entered and not rationale and not reviewer and not reviewed_at:
            incomplete += 1
            continue
        if decision not in {"ACCEPT", "CHANGE", "UNRESOLVED"}:
            issues.append({"line": line_number, "code": "INVALID_OR_MISSING_DECISION", "key": list(key)})
            continue
        if not reviewer or not reviewed_at:
            issues.append({"line": line_number, "code": "REVIEWER_AND_TIMESTAMP_REQUIRED", "key": list(key)})
            continue
        if not _has_timezone_aware_iso_timestamp(reviewed_at):
            issues.append({"line": line_number, "code": "REVIEW_TIMESTAMP_MUST_BE_ISO_WITH_TIMEZONE", "key": list(key)})
            continue
        if decision == "UNRESOLVED":
            if entered or not rationale:
                issues.append({"line": line_number, "code": "UNRESOLVED_ROW_MUST_HAVE_BLANK_MARK_AND_RATIONALE", "key": list(key)})
            else:
                unresolved += 1
            continue
        try:
            mark = float(entered)
        except (TypeError, ValueError):
            mark = float("nan")
        if not math.isfinite(mark) or mark < 0 or mark > source["maximum"]:
            issues.append({"line": line_number, "code": "EDUCATOR_MARK_OUT_OF_RANGE", "key": list(key)})
            continue
        if decision == "ACCEPT":
            proposal = source["model_proposal"]
            if proposal is None or abs(mark - float(proposal)) > 0.001:
                issues.append({"line": line_number, "code": "ACCEPT_MUST_MATCH_EXISTING_MODEL_PROPOSAL", "key": list(key)})
                continue
            if float(proposal or 0) > 0 and not source["model_quote_grounded"]:
                educator_quote = " ".join(str(row.get("educator_verified_source_quote") or "").split())
                answer_text = source["answer_block_text"]
                if not answer_text or not educator_quote or educator_quote not in answer_text:
                    issues.append({"line": line_number, "code": "UNGROUNDED_POSITIVE_ACCEPT_REQUIRES_EXACT_QUESTION_SCOPED_EDUCATOR_QUOTE", "key": list(key)})
                    continue
            accepted += 1
        else:
            if not rationale:
                issues.append({"line": line_number, "code": "CHANGED_MARK_REQUIRES_RATIONALE", "key": list(key)})
                continue
            changed += 1
    missing_keys = sorted(set(expected) - set(observed))
    if missing_keys:
        issues.extend({"code": "SOURCE_POINT_ROW_MISSING", "key": list(key)} for key in missing_keys)
    expected_flags: dict[tuple[str, str, str, str], str] = {}
    for result in results:
        student_id = str(result.get("student_id") or "")
        for flag in result.get("unresolved_marking_quality_flags") or []:
            canonical = json.dumps(flag, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            flag_hash = hashlib.sha256(canonical).hexdigest()
            key = (student_id, str(flag.get("code") or ""), str(flag.get("criterion") or ""), flag_hash)
            expected_flags[key] = flag_hash
    flag_unresolved = 0
    if expected_flags and quality_flags_csv is None:
        flag_unresolved = len(expected_flags)
    elif quality_flags_csv is not None:
        flag_path = Path(quality_flags_csv).resolve()
        if not flag_path.is_file():
            issues.append({"code": "QUALITY_FLAG_REVIEW_FILE_MISSING", "path": str(flag_path)})
            flag_unresolved = len(expected_flags)
        else:
            required_flag_fields = {"packet_fingerprint", "student_id", "flag_code", "flag_criterion", "source_flag_sha256",
                                    "educator_resolution", "educator_rationale", "educator_reviewer", "reviewed_at"}
            with flag_path.open("r", encoding="utf-8-sig", newline="") as handle:
                flag_reader = csv.DictReader(handle)
                if not required_flag_fields.issubset(set(flag_reader.fieldnames or [])):
                    issues.append({"code": "QUALITY_FLAG_REVIEW_FIELDS_MISSING"})
                    flag_rows = []
                else:
                    flag_rows = list(flag_reader)
            seen_flags: set[tuple[str, str, str]] = set()
            for line_number, flag_row in enumerate(flag_rows, 2):
                key = (str(flag_row.get("student_id") or "").strip(), str(flag_row.get("flag_code") or "").strip(),
                       str(flag_row.get("flag_criterion") or "").strip(), str(flag_row.get("source_flag_sha256") or "").strip())
                if key not in expected_flags:
                    issues.append({"line": line_number, "code": "UNKNOWN_SOURCE_QUALITY_FLAG", "key": list(key)})
                    continue
                if key in seen_flags:
                    issues.append({"line": line_number, "code": "DUPLICATE_SOURCE_QUALITY_FLAG", "key": list(key)})
                    continue
                seen_flags.add(key)
                if (str(flag_row.get("packet_fingerprint") or "").strip() != customer_packet_fingerprint
                        or str(flag_row.get("source_flag_sha256") or "").strip() != expected_flags[key]):
                    issues.append({"line": line_number, "code": "SOURCE_QUALITY_FLAG_BINDING_MISMATCH", "key": list(key)})
                    continue
                resolution = str(flag_row.get("educator_resolution") or "").strip().upper()
                rationale = str(flag_row.get("educator_rationale") or "").strip()
                reviewer = str(flag_row.get("educator_reviewer") or "").strip()
                reviewed_at = str(flag_row.get("reviewed_at") or "").strip()
                if not resolution and not rationale and not reviewer and not reviewed_at:
                    flag_unresolved += 1
                    continue
                if resolution not in {"RESOLVE", "UNRESOLVED"} or not rationale or not reviewer or not reviewed_at:
                    issues.append({"line": line_number, "code": "QUALITY_FLAG_REVIEW_DECISION_INCOMPLETE", "key": list(key)})
                    continue
                if not _has_timezone_aware_iso_timestamp(reviewed_at):
                    issues.append({"line": line_number, "code": "QUALITY_FLAG_REVIEW_TIMESTAMP_MUST_BE_ISO_WITH_TIMEZONE", "key": list(key)})
                    continue
                if resolution == "UNRESOLVED":
                    flag_unresolved += 1
            missing_flags = sorted(set(expected_flags) - seen_flags)
            flag_unresolved += len(missing_flags)
    if issues:
        state = "INVALID_RETURN_REQUIRES_CORRECTION"
    elif incomplete or missing_keys:
        state = "NEEDS_EDUCATOR_COMPLETION"
    elif unresolved:
        state = "NEEDS_EDUCATOR_RESOLUTION"
    elif flag_unresolved:
        state = "NEEDS_MARKING_QUALITY_FLAG_RESOLUTION"
    else:
        state = "EDUCATOR_TOTALS_RECONCILED_REVIEW_REQUIRED"
    totals_calculated = not issues and not incomplete and not missing_keys and not unresolved and not flag_unresolved
    reconciled_totals: list[dict[str, Any]] = []
    if totals_calculated:
        by_student: dict[str, dict[str, Any]] = {}
        criterion_maxima = {
            str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0]): sum(
                float(point.get("marks") or 0) for point in criterion.get("marking_points") or []
            )
            for criterion in rubric.get("criteria") or []
        }
        for (student_id, criterion_id, point_id), row in observed.items():
            # This branch is reached only after each row has passed its source,
            # decision, reviewer, timestamp and range checks above.
            mark = float(str(row.get("educator_verified_marks")).strip())
            student = by_student.setdefault(student_id, {"criterion_totals": {}, "total": 0.0})
            criterion_total = student["criterion_totals"].setdefault(
                criterion_id, {"marks": 0.0, "maximum_marks": criterion_maxima[criterion_id], "point_count": 0}
            )
            criterion_total["marks"] += mark
            criterion_total["point_count"] += 1
            student["total"] += mark
        maximum_total = sum(criterion_maxima.values())
        for student_id, values in sorted(by_student.items()):
            criterion_rows = []
            for criterion_id, data in values["criterion_totals"].items():
                criterion_rows.append({
                    "criterion_id": criterion_id,
                    "marks": round(data["marks"], 3),
                    "maximum_marks": round(data["maximum_marks"], 3),
                    "point_count": data["point_count"],
                })
            reconciled_totals.append({
                "student_id": student_id,
                "criterion_totals": sorted(criterion_rows, key=lambda row: row["criterion_id"]),
                "total_marks": round(values["total"], 3),
                "maximum_marks": round(maximum_total, 3),
                "percentage": round(values["total"] / maximum_total * 100, 2) if maximum_total else None,
                "state": "EDUCATOR_ENTERED_RECONCILIATION_REQUIRES_FINAL_REVIEW",
            })
    return {
        "schema": "dio.homs.assess.pointwise_adjudication_validation.v1",
        "source_csv": str(path), "source_csv_sha256": _sha(path),
        "customer_packet_fingerprint": customer_packet_fingerprint,
        "source_point_count": len(expected), "observed_row_count": len(rows),
        "accepted_model_proposals": accepted, "educator_changed_points": changed,
        "unresolved_points": unresolved, "incomplete_points": incomplete + len(missing_keys),
        "source_quality_flag_count": len(expected_flags), "unresolved_quality_flag_count": flag_unresolved,
        "issues": issues, "state": state,
        "totals_calculated": totals_calculated,
        "educator_reconciled_totals": reconciled_totals,
        "totals_are_reconciliation_only": True,
        "marks_issued": False,
        "classroom_release_authorized": False,
    }


def build_pointwise_educator_review(
    input_dir: Path,
    rubric: Mapping[str, Any],
    results: list[dict[str, Any]],
    results_path: Path,
    output_dir: Path,
    *,
    customer_packet_fingerprint: str,
) -> dict[str, Any]:
    """Render source-linked point proposals for educators; never issue marks."""
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        output_dir.chmod(0o700)
    except OSError:
        pass
    paper = next((path for path in sorted((input_dir / "uploads").glob("*"))
                  if path.is_file() and "question_paper" in path.stem.casefold().replace("-", "_").replace(" ", "_")), None)
    memo = input_dir / "memo.md"
    rubric_path = input_dir / "rubric.json"
    source_paths = [path for path in (rubric_path, memo, paper, results_path) if path and path.is_file()]
    submission_paths: list[tuple[str, Path]] = []
    answer_block_bindings: list[dict[str, Any]] = []
    criterion_answer_block_bindings: list[dict[str, Any]] = []
    sections = []
    adjudication_rows: list[dict[str, Any]] = []
    withheld = provisional = 0
    quality_flag_ui_index = 0
    for result in results:
        student_id = str(result.get("student_id") or "learner")
        submission_path = input_dir / "uploads" / str(result.get("submission_file") or f"{student_id}.txt")
        if not submission_path.is_file():
            raise ValueError(f"No source submission is available for educator review: {student_id}")
        source_bytes = submission_path.read_bytes()
        source_file_sha256 = hashlib.sha256(source_bytes).hexdigest()
        direct_utf8_source = submission_path.suffix.lower() in {".txt", ".md"}
        if direct_utf8_source:
            try:
                source_text = source_bytes.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                source_text = source_bytes.decode("utf-8", errors="replace")
                direct_utf8_source = False
        else:
            extractor = load_hymark_backend(Path(DEFAULT_HYMARK_BACKEND))
            source_text = str(extractor.extract_document_content(submission_path) or "")
        question_answer_blocks = _question_answer_blocks(source_text)
        normalized_source = " ".join(source_text.split())
        source_paths.append(submission_path)
        submission_paths.append((student_id, submission_path))
        blocked = score_is_blocked(result)
        withheld += int(blocked)
        provisional += int(not blocked)
        proposal = result.get("proposed_total_score", result.get("total_score"))
        maximum = result.get("max_score")
        status = ("NOT SCORED · proposed total withheld pending educator resolution" if blocked
                  else "PROVISIONAL · educator verification required")
        criteria = []
        result_scores = result.get("criteria_scores") or {}
        result_flags = result.get("unresolved_marking_quality_flags") or []
        for criterion in rubric.get("criteria") or []:
            criterion_id = str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0])
            score = next((value for key, value in result_scores.items()
                          if str(key).split(":", 1)[0].strip() == criterion_id), {})
            criterion_flags = [flag for flag in result_flags
                               if str(flag.get("criterion") or "") in {criterion_id, "ALL"}]
            concept_conflict = next((flag for flag in criterion_flags
                                     if flag.get("code") == "learner_quote_conflicts_with_motion_graph_rubric"), None)
            raw_quotes = score.get("quotes") or []
            if isinstance(raw_quotes, str):
                raw_quotes = [raw_quotes]
            quotes = [" ".join(str(value).split()) for value in raw_quotes
                      if isinstance(value, str) and " ".join(value.split()) in normalized_source]
            quote_markup = ("<blockquote>" + "<br>".join(html.escape(value) for value in quotes) + "</blockquote>"
                            if quotes else "<p class='missing'>No verified exact answer excerpt. Read the complete learner response before reviewing points.</p>")
            source_answer_block = question_answer_blocks.get(criterion_id)
            if source_answer_block:
                source_byte_start = source_answer_block["utf8_byte_start"] if direct_utf8_source else ""
                source_byte_end = source_answer_block["utf8_byte_end_exclusive"] if direct_utf8_source else ""
                if (direct_utf8_source
                        and source_bytes[int(source_byte_start):int(source_byte_end)].decode("utf-8")
                        != source_answer_block["text"]):
                    raise ValueError("Criterion answer block does not match its learner-source byte span")
                criterion_answer_block_bindings.append({
                    "student_id": student_id,
                    "criterion_id": criterion_id,
                    "source_file": str(submission_path.relative_to(ROOT)),
                    "source_file_sha256": source_file_sha256,
                    "answer_block_sha256": source_answer_block["sha256"],
                    "character_start": source_answer_block["character_start"],
                    "character_end_exclusive": source_answer_block["character_end_exclusive"],
                    "byte_start": source_byte_start,
                    "byte_end_exclusive": source_byte_end,
                    "coordinate_basis": ("original_utf8_file_bytes" if direct_utf8_source
                                         else "extracted_document_text_characters"),
                })
                source_answer_markup = (
                    "<details class='source-answer'><summary>Complete learner answer for this question · source text, not scored</summary>"
                    "<blockquote>" + html.escape(source_answer_block["text"]) + "</blockquote><small>Source SHA-256 "
                    + html.escape(source_answer_block["sha256"]) + " · learner file SHA-256 "
                    + html.escape(source_file_sha256) + "</small></details>"
                )
            else:
                source_answer_markup = (
                    "<p class='missing'>No numbered answer block was found for this question. Open the complete learner submission before reviewing any point.</p>"
                )
            point_rows = []
            score_by_id = {str(point.get("point_id") or ""): point for point in score.get("point_scores") or []}
            for point in criterion.get("marking_points") or []:
                point_id = str(point.get("point_id") or "")
                proposal_row = score_by_id.get(point_id) or {}
                proposed_score = proposal_row.get("score")
                point_quotes = proposal_row.get("quotes") or []
                if isinstance(point_quotes, str):
                    point_quotes = [point_quotes]
                answer_block_for_quote = question_answer_blocks.get(criterion_id)
                answer_text_for_quote = answer_block_for_quote.get("text", "") if answer_block_for_quote else ""
                bound_point_quotes = [
                    " ".join(value.split()) for value in point_quotes
                    if isinstance(value, str) and value.strip()
                    and " ".join(value.split()) in " ".join(answer_text_for_quote.split())
                ]
                point_quote = bound_point_quotes[0] if bound_point_quotes else ""
                unbound_quote_candidates = [
                    str(value)[:500] for value in (proposal_row.get("unbound_quote_candidates") or [])
                    if isinstance(value, str) and value.strip()
                ][:5]
                question_text_normalized = " ".join(answer_text_for_quote.split())
                citation_candidates = []
                for value in [*point_quotes, *unbound_quote_candidates]:
                    candidate = " ".join(str(value).split())[:500]
                    if (not candidate or candidate in question_text_normalized
                            or any(row["text"] == candidate for row in citation_candidates)):
                        continue
                    citation_candidates.append({
                        "text": candidate,
                        "state": "EXACT_TEXT_OUTSIDE_QUESTION" if candidate in normalized_source else "NOT_FOUND_IN_SUBMISSION",
                    })
                source_quote_suggestions = (
                    suggest_exact_question_source_spans(answer_text_for_quote, str(point.get("point") or ""))
                    if proposed_score is not None and float(proposed_score or 0) > 0 and not point_quote else []
                )
                for suggestion in source_quote_suggestions:
                    suggestion["answer_block_sha256"] = answer_block_for_quote.get("sha256", "") if answer_block_for_quote else ""
                    suggestion["source_file_sha256"] = source_file_sha256
                point_quote_state = (
                    "EXACT_QUESTION_SCOPED_QUOTE_BOUND" if point_quote else
                    "NO_EXACT_QUESTION_SCOPED_QUOTE" if proposed_score is not None and float(proposed_score or 0) > 0 else
                    "NOT_REQUIRED_FOR_ZERO_OR_UNRETURNED_POINT"
                )
                point_quote_char_start = source_text.find(point_quote) if point_quote else -1
                if point_quote_char_start < 0:
                    point_quote = ""
                    point_quote_state = (
                        "NO_EXACT_QUESTION_SCOPED_QUOTE" if proposed_score is not None and float(proposed_score or 0) > 0 else
                        "NOT_REQUIRED_FOR_ZERO_OR_UNRETURNED_POINT"
                    )
                    point_quote_char_start = ""
                point_quote_char_end = (int(point_quote_char_start) + len(point_quote)) if point_quote else ""
                point_quote_byte_start = (len(source_text[:int(point_quote_char_start)].encode("utf-8"))
                                          if point_quote and direct_utf8_source else "")
                point_quote_byte_end = (len(source_text[:int(point_quote_char_end)].encode("utf-8"))
                                        if point_quote and direct_utf8_source else "")
                # Give educators the exact question-scoped source block when a
                # positive proposal has no bound quotation, as well as when a
                # point was not returned. This is review context only: it does
                # not create a quote, validate the proposal, or release marks.
                needs_answer_context = (
                    proposed_score is None
                    or (float(proposed_score or 0) > 0 and not point_quote)
                )
                answer_block = question_answer_blocks.get(criterion_id) if needs_answer_context else None
                answer_excerpt = answer_block.get("text", "") if answer_block else ""
                byte_start = answer_block.get("utf8_byte_start") if answer_block and direct_utf8_source else ""
                byte_end = answer_block.get("utf8_byte_end_exclusive") if answer_block and direct_utf8_source else ""
                if answer_block:
                    if direct_utf8_source and source_bytes[int(byte_start):int(byte_end)].decode("utf-8") != answer_excerpt:
                        raise ValueError("Question answer excerpt does not match its learner-source byte span")
                    answer_block_bindings.append({
                        "student_id": student_id, "criterion_id": criterion_id, "point_id": point_id,
                        "source_file": str(submission_path.relative_to(ROOT)),
                        "source_file_sha256": source_file_sha256,
                        "answer_excerpt_sha256": answer_block["sha256"],
                        "character_start": answer_block["character_start"],
                        "character_end_exclusive": answer_block["character_end_exclusive"],
                        "byte_start": byte_start, "byte_end_exclusive": byte_end,
                        "coordinate_basis": "original_utf8_file_bytes" if direct_utf8_source else "extracted_document_text_characters",
                    })
                adjudication_rows.append({
                    "packet_fingerprint": customer_packet_fingerprint,
                    "student_id": student_id,
                    "criterion_id": criterion_id,
                    "question_prompt": str(criterion.get("question_prompt") or criterion.get("question") or ""),
                    "point_id": point_id,
                    "memo_point": str(point.get("point") or ""),
                    "maximum_marks": point.get("marks", ""),
                    "model_proposed_marks": "" if proposed_score is None else proposed_score,
                    "model_state": "UNRETURNED_UNSCORED" if proposed_score is None else "PROPOSAL_REQUIRES_EDUCATOR_VERIFICATION",
                    "point_quote_state": point_quote_state,
                    "model_quote_candidates_not_bound_to_question_json": json.dumps(citation_candidates, ensure_ascii=False),
                    "exact_question_source_quote_suggestions_json": json.dumps(source_quote_suggestions, ensure_ascii=False),
                    "learner_answer_excerpt": point_quote,
                    "point_quote_source_character_start": point_quote_char_start,
                    "point_quote_source_character_end_exclusive": point_quote_char_end,
                    "point_quote_source_byte_start": point_quote_byte_start,
                    "point_quote_source_byte_end_exclusive": point_quote_byte_end,
                    "point_quote_source_file_sha256": source_file_sha256 if point_quote else "",
                    "missing_point_answer_source_excerpt": answer_excerpt,
                    "missing_point_answer_sha256": answer_block.get("sha256", "") if answer_block else "",
                    "missing_point_answer_character_start": answer_block.get("character_start", "") if answer_block else "",
                    "missing_point_answer_character_end_exclusive": answer_block.get("character_end_exclusive", "") if answer_block else "",
                    "missing_point_answer_byte_start": answer_block.get("utf8_byte_start", "") if answer_block and direct_utf8_source else "",
                    "missing_point_answer_byte_end_exclusive": answer_block.get("utf8_byte_end_exclusive", "") if answer_block and direct_utf8_source else "",
                    "missing_point_source_file_sha256": source_file_sha256 if answer_block else "",
                    "missing_point_answer_coordinate_basis": "original_utf8_file_bytes" if answer_block and direct_utf8_source else ("extracted_document_text_characters" if answer_block else ""),
                    "missing_point_answer_state": (
                        "QUESTION_BLOCK_FOR_UNGROUNDED_POSITIVE_PROPOSAL_REVIEW"
                        if answer_block and proposed_score is not None and float(proposed_score or 0) > 0
                        else "EXACT_QUESTION_BLOCK_FOR_EDUCATOR_REVIEW" if answer_block else
                                                   ("QUESTION_BLOCK_NOT_FOUND_REVIEW_FULL_SUBMISSION" if proposed_score is None else "NOT_APPLICABLE")),
                    "educator_verified_marks": "",
                    "educator_decision": "",
                    "educator_rationale": "",
                    "educator_reviewer": "",
                    "reviewed_at": "",
                    "educator_verified_source_quote": "",
                })
                point_rows.append(
                    "<tr data-point-row='" + str(len(adjudication_rows) - 1) + "' data-student='" + html.escape(student_id, quote=True)
                    + "' data-criterion='" + html.escape(criterion_id, quote=True) + "'><th scope='row'><code>" + html.escape(point_id) + "</code><br>"
                    + html.escape(str(point.get("point") or "")) + "</th><td>"
                    + ("not returned" if proposal_row.get("score") is None else html.escape(f"{proposal_row.get('score')} / {point.get('marks', '—')}"))
                    + ("<p class='point-quote-ok'><strong>Exact quote from this question:</strong> " + html.escape(point_quote) + "</p>"
                       if point_quote else
                       ("<p class='missing'><strong>No exact question-scoped quote.</strong> This positive proposal remains ungrounded and must not be accepted as a mark.</p>"
                        if proposed_score is not None and float(proposed_score or 0) > 0 else ""))
                    + ("<details class='unbound'><summary>Model citation candidates not bound to this question · review only</summary><ul>"
                       + "".join("<li><strong>" + html.escape(value["state"]) + ":</strong> <q>" + html.escape(value["text"]) + "</q></li>" for value in citation_candidates)
                       + "</ul><small>These candidates are not evidence for this point. Some may match text elsewhere in the submission; none is bound to this question's answer block.</small></details>"
                       if citation_candidates else "")
                    + ("<details class='source-suggestions'><summary>Possible exact excerpts from this question · educator verification required</summary><ul>"
                       + "".join("<li><q>" + html.escape(value["text"]) + "</q><br><small>Matched memo terms: "
                                 + html.escape(", ".join(value["matched_memo_terms"]))
                                 + " · suggestion only; not verified point evidence</small></li>" for value in source_quote_suggestions)
                       + "</ul></details>" if source_quote_suggestions else "")
                    + ("<details><summary>Exact answer block for educator review · not scored</summary><blockquote>" + html.escape(answer_excerpt) + "</blockquote><small>Source SHA-256 " + html.escape(answer_block['sha256']) + "</small></details>" if answer_block else "")
                    + "<fieldset class='decision-fields'><legend>Educator decision · review required</legend>"
                    + "<label>Verified marks <input data-field='educator_verified_marks' type='number' min='0' max='" + html.escape(str(point.get('marks', ''))) + "' step='any'></label>"
                    + "<label>Decision <select data-field='educator_decision'><option value=''>Choose…</option><option>ACCEPT</option><option>CHANGE</option><option>UNRESOLVED</option></select></label>"
                    + "<label class='wide'>Exact answer quote for a positive proposal without a bound quote<textarea data-field='educator_verified_source_quote' rows='2'></textarea></label>"
                    + "<label class='wide'>Rationale for a changed or unresolved decision<textarea data-field='educator_rationale' rows='2'></textarea></label>"
                    + "<label>Educator/reviewer <input data-field='educator_reviewer' autocomplete='name'></label>"
                    + "<label>Local review date/time <input data-field='reviewed_at' type='datetime-local'></label></fieldset>"
                    + "</td></tr>"
                )
            omitted = score.get("unreturned_point_ids") or []
            omission_note = ("<p class='missing'>These memo point IDs were not returned and remain unscored: <code>"
                             + html.escape(", ".join(str(value) for value in omitted)) + "</code>. The criterion total is unavailable.</p>" if omitted else "")
            conflict_note = ("<aside class='conflict-hold'><strong>MODEL PROPOSAL HELD — NOT A MARK.</strong> "
                             + html.escape(str(concept_conflict.get("detail") or "A direct answer conflict requires educator review."))
                             + ("<blockquote>" + html.escape(str(concept_conflict.get("source_quote") or "")) + "</blockquote>"
                                if concept_conflict.get("source_quote") else "")
                             + "Reassess every point in this question against the complete learner response and source memo.</aside>"
                             if concept_conflict else "")
            feedback = html.escape(str(score.get("feedback") or "No criterion feedback supplied."))
            criterion_summary = ("model proposal held pending concept review" if concept_conflict else
                                 (f"proposed {score.get('score')} / {criterion.get('weight', '—')}"
                                  if score.get("score") is not None else "criterion total unavailable"))
            criteria.append(
                "<details open><summary><strong>Question " + html.escape(criterion_id) + "</strong> · "
                + html.escape(criterion_summary) + "</summary>"
                + "<p class='prompt'>" + html.escape(str(criterion.get("question_prompt") or criterion.get("question") or "")) + "</p>"
                + conflict_note
                + "<h4>Exact learner answer excerpt</h4>" + quote_markup
                + source_answer_markup
                + "<table><thead><tr><th>Memo point</th><th>" + ("Unaccepted model proposal (not a mark)" if concept_conflict else "Model proposal") + "</th></tr></thead><tbody>"
                + "".join(point_rows) + "</tbody></table>" + omission_note
                + "<p><strong>Draft feedback:</strong> " + feedback + "</p></details>"
            )
        flags = result.get("unresolved_marking_quality_flags") or []
        flag_markup_items = []
        for flag in flags:
            flag_markup_items.append(
                "<li data-flag-row='" + str(quality_flag_ui_index) + "' data-student='" + html.escape(student_id, quote=True) + "'><strong>" + html.escape(str(flag.get("criterion") or "")) + ":</strong> "
                + html.escape(str(flag.get("detail") or ""))
                + ("<blockquote>" + html.escape(str(flag.get("source_quote") or "")) + "</blockquote>" if flag.get("source_quote") else "")
                + "<fieldset class='decision-fields'><legend>Educator flag resolution</legend>"
                + "<label>Resolution <select data-field='educator_resolution'><option value=''>Choose…</option><option>RESOLVE</option><option>UNRESOLVED</option></select></label>"
                + "<label>Educator/reviewer <input data-field='educator_reviewer' autocomplete='name'></label>"
                + "<label>Local review date/time <input data-field='reviewed_at' type='datetime-local'></label>"
                + "<label class='wide'>Rationale<textarea data-field='educator_rationale' rows='2'></textarea></label></fieldset></li>"
            )
            quality_flag_ui_index += 1
        flag_markup = ("<div class='flags'><h3>Unresolved marking flags</h3><ul>"
                       + "".join(flag_markup_items) + "</ul></div>" if flags else "")
        sections.append(
            "<section class='learner'><h2>" + html.escape(student_id) + "</h2><p class='status'>" + html.escape(status) + "</p>"
            + "<p><strong>Model proposal total:</strong> " + html.escape(f"{proposal if proposal is not None else '—'} / {maximum if maximum is not None else '—'}")
            + (" <span class='withheld'>withheld; do not enter as a mark</span>" if blocked else " <span class='provisional'>not a final mark</span>")
            + "</p>" + flag_markup + "".join(criteria) + "</section>"
        )
    adjudication_path = output_dir / "EDUCATOR_POINTWISE_ADJUDICATION.csv"
    adjudication_fields = [
        "packet_fingerprint", "student_id", "criterion_id", "question_prompt", "point_id",
        "memo_point", "maximum_marks", "model_proposed_marks", "model_state",
        "point_quote_state", "model_quote_candidates_not_bound_to_question_json", "exact_question_source_quote_suggestions_json", "learner_answer_excerpt", "point_quote_source_character_start",
        "point_quote_source_character_end_exclusive", "point_quote_source_byte_start",
        "point_quote_source_byte_end_exclusive", "point_quote_source_file_sha256",
        "educator_verified_source_quote",
        "missing_point_answer_source_excerpt", "missing_point_answer_sha256",
        "missing_point_answer_character_start", "missing_point_answer_character_end_exclusive",
        "missing_point_answer_byte_start", "missing_point_answer_byte_end_exclusive",
        "missing_point_source_file_sha256", "missing_point_answer_coordinate_basis",
        "missing_point_answer_state", "educator_verified_marks", "educator_decision",
        "educator_rationale", "educator_reviewer", "reviewed_at",
    ]
    with adjudication_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=adjudication_fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(adjudication_rows)
    try:
        adjudication_path.chmod(0o600)
    except OSError:
        pass
    quality_flag_fields = ["packet_fingerprint", "student_id", "flag_code", "flag_criterion", "source_flag_sha256",
                           "flag_detail", "educator_resolution", "educator_rationale", "educator_reviewer", "reviewed_at"]
    quality_flag_rows = []
    for result in results:
        for flag in result.get("unresolved_marking_quality_flags") or []:
            canonical = json.dumps(flag, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            quality_flag_rows.append({
                "packet_fingerprint": customer_packet_fingerprint,
                "student_id": str(result.get("student_id") or ""),
                "flag_code": str(flag.get("code") or ""),
                "flag_criterion": str(flag.get("criterion") or ""),
                "source_flag_sha256": hashlib.sha256(canonical).hexdigest(),
                "flag_detail": str(flag.get("detail") or ""),
                "educator_resolution": "", "educator_rationale": "", "educator_reviewer": "", "reviewed_at": "",
            })
    quality_flags_path = output_dir / "EDUCATOR_MARKING_QUALITY_FLAGS.csv"
    with quality_flags_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=quality_flag_fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(quality_flag_rows)
    try:
        quality_flags_path.chmod(0o600)
    except OSError:
        pass
    adjudication_receipt = {
        "schema": "dio.homs.assess.pointwise_adjudication_template.v1",
        "path": adjudication_path.name,
        "sha256": _sha(adjudication_path),
        "customer_packet_fingerprint": customer_packet_fingerprint,
        "source_rubric_sha256": _sha(rubric_path),
        "source_results_sha256": _sha(results_path),
        "submission_count": len(results),
        "point_row_count": len(adjudication_rows),
        "unreturned_point_row_count": sum(row["model_state"] == "UNRETURNED_UNSCORED" for row in adjudication_rows),
        "educator_fields_initially_blank": all(
            not row[key] for row in adjudication_rows
            for key in ("educator_verified_marks", "educator_decision", "educator_rationale", "educator_reviewer", "reviewed_at")
        ),
        "source_quality_flag_row_count": len(quality_flag_rows),
        "quality_flag_fields_initially_blank": all(
            not row[key] for row in quality_flag_rows
            for key in ("educator_resolution", "educator_rationale", "educator_reviewer", "reviewed_at")
        ),
        "blank_is_zero": False,
        "automatic_acceptance": False,
        "assessment_total_issued": False,
        "human_review_required": True,
        "classroom_release_authorized": False,
    }
    adjudication_receipt_path = output_dir / "EDUCATOR_POINTWISE_ADJUDICATION_RECEIPT.json"
    write_json(adjudication_receipt_path, adjudication_receipt)
    guide_path = output_dir / "EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md"
    guide_path.write_text(
        "# HOMS Assess pointwise educator adjudication\n\n"
        "This file is a blank decision template. The model proposal is a draft for review, not a mark.\n\n"
        "1. Open the linked learner submission, source question paper, and marking memo.\n"
        "2. Review each `point_id` against the full learner answer and memo.\n"
        "3. Enter `educator_verified_marks` only after review. It must be between 0 and `maximum_marks`.\n"
        "4. Set `educator_decision` to `ACCEPT` when confirming the model proposal, `CHANGE` when replacing it, or `UNRESOLVED` when the evidence is insufficient.\n"
        "5. For `CHANGE` or `UNRESOLVED`, explain the decision in `educator_rationale`. For unresolved rows, leave the verified mark blank.\n"
        "5a. If a positive model proposal has no exact quote in this question's answer, enter an exact excerpt from that answer in `educator_verified_source_quote` before choosing `ACCEPT`. The validator checks the quote against the original question-scoped answer block; an ungrounded positive cannot be accepted with rationale alone.\n"
        "6. Fill in reviewer identity and review time for every completed row. Blank fields remain unresolved; they are never interpreted as zero.\n\n"
        "7. Review every source-bound marking-quality flag in `EDUCATOR_MARKING_QUALITY_FLAGS.csv`; select `RESOLVE` only when the underlying concern is addressed, or `UNRESOLVED` to keep totals blocked. Add a rationale, reviewer and timestamp.\n\n"
        "8. `model_quote_candidates_not_bound_to_question_json` records candidate strings that are not exact spans in the current question's answer block. The state distinguishes text found elsewhere in the submission from text not found at all. Treat all candidates only as diagnostic clues; none can support a mark without an exact question-scoped binding and educator review.\n\n"
        "9. `exact_question_source_quote_suggestions_json` contains at most two exact sentences from the same numbered answer, ranked by shared wording with the memo point. These are search aids only. Confirm that a sentence supports the point; never copy a suggestion into the verified quote field without checking the full response and memo. Suggestions do not change proposals or totals.\n\n"
        "10. Use the review filters to narrow by learner or answer text. Download a JSON review draft to resume later; the draft contains educator-entered fields only and is bound to this packet fingerprint and row set. Loading a draft does not validate its decisions.\n\n"
        "Validate both completed CSVs: `python scripts/validate_homs_assess_adjudication.py --run-dir <HOMS-Assess-run> --csv <completed-pointwise-csv> --quality-flags-csv <completed-quality-flags-csv>`.\n\n"
        "When every point and quality flag is complete, validation calculates an educator-entered reconciliation subtotal and total for checking. These are not issued marks. It does not authorize gradebook entry or classroom release.\n",
        encoding="utf-8",
    )
    try:
        adjudication_receipt_path.chmod(0o600)
        guide_path.chmod(0o600)
    except OSError:
        pass
    links = []
    for label, path in (("Original question paper", paper), ("Original marking memo", memo)):
        if path and path.is_file():
            href = os.path.relpath(path.resolve(), output_dir.resolve()).replace(os.sep, "/")
            links.append("<li><a href='" + html.escape(href, quote=True) + "'>" + html.escape(label) + "</a></li>")
    links.append("<li><a href='EDUCATOR_POINTWISE_ADJUDICATION.csv'>Download blank point-level educator adjudication CSV</a></li>")
    links.append("<li><a href='EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md'>Read educator adjudication instructions</a></li>")
    links.append("<li><a href='EDUCATOR_MARKING_QUALITY_FLAGS.csv'>Download blank marking-quality flag review CSV</a></li>")
    for student_id, path in submission_paths:
        href = os.path.relpath(path.resolve(), output_dir.resolve()).replace(os.sep, "/")
        links.append("<li><a href='" + html.escape(href, quote=True) + "'>Full learner submission: " + html.escape(student_id) + "</a></li>")
    point_fields_json = json.dumps(adjudication_fields, ensure_ascii=False).replace("<", "\\u003c")
    point_rows_json = json.dumps(adjudication_rows, ensure_ascii=False).replace("<", "\\u003c")
    flag_fields_json = json.dumps(quality_flag_fields, ensure_ascii=False).replace("<", "\\u003c")
    flag_rows_json = json.dumps(quality_flag_rows, ensure_ascii=False).replace("<", "\\u003c")
    point_editable_fields = {"educator_verified_marks", "educator_decision", "educator_verified_source_quote",
                             "educator_rationale", "educator_reviewer", "reviewed_at"}
    flag_editable_fields = {"educator_resolution", "educator_rationale", "educator_reviewer", "reviewed_at"}
    draft_context = {
        "point_rows": [{key: row.get(key, "") for key in adjudication_fields if key not in point_editable_fields}
                       for row in adjudication_rows],
        "quality_flag_rows": [{key: row.get(key, "") for key in quality_flag_fields if key not in flag_editable_fields}
                              for row in quality_flag_rows],
    }
    draft_context_sha256 = hashlib.sha256(json.dumps(
        draft_context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    review_context_json = json.dumps({
        "packet_fingerprint": customer_packet_fingerprint,
        "context_sha256": draft_context_sha256,
        "point_row_count": len(adjudication_rows),
        "quality_flag_row_count": len(quality_flag_rows),
    }, ensure_ascii=False).replace("<", "\\u003c")
    filter_student_options = "".join(
        "<option value='" + html.escape(str(result.get("student_id") or ""), quote=True) + "'>"
        + html.escape(str(result.get("student_id") or "")) + "</option>"
        for result in results if result.get("student_id")
    )
    review_export_script = r"""<script>(function(){
const pointFields=JSON.parse(document.getElementById('point-fields').textContent);
const pointRows=JSON.parse(document.getElementById('point-rows').textContent);
const reviewContext=JSON.parse(document.getElementById('review-context').textContent);
const flagFields=JSON.parse(document.getElementById('flag-fields').textContent);
const flagRows=JSON.parse(document.getElementById('flag-rows').textContent);
const editablePoint=['educator_verified_marks','educator_decision','educator_verified_source_quote','educator_rationale','educator_reviewer','reviewed_at'];
const editableFlag=['educator_resolution','educator_rationale','educator_reviewer','reviewed_at'];
const status=document.getElementById('review-status');
const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';
const download=(name,blob)=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
const downloadCsv=(name,fields,rows)=>{const lines=[fields.map(cell).join(','),...rows.map(r=>fields.map(k=>cell(r[k])).join(','))];download(name,new Blob(['\ufeff',lines.join('\r\n')],{type:'text/csv;charset=utf-8'}))};
const stamp=v=>v?new Date(v).toISOString():'';
const inputDate=v=>{if(!v)return '';const d=new Date(v);if(Number.isNaN(d.valueOf()))return '';d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,16)};
const pointKey=r=>[r.student_id,r.criterion_id,r.point_id].join('\u001f');
const flagKey=r=>[r.student_id,r.flag_code,r.flag_criterion,r.source_flag_sha256].join('\u001f');
function collect(){
 document.querySelectorAll('[data-point-row]').forEach(tr=>{const row=pointRows[Number(tr.dataset.pointRow)];tr.querySelectorAll('[data-field]').forEach(el=>row[el.dataset.field]=el.dataset.field==='reviewed_at'?stamp(el.value):el.value)});
 document.querySelectorAll('[data-flag-row]').forEach(li=>{const row=flagRows[Number(li.dataset.flagRow)];li.querySelectorAll('[data-field]').forEach(el=>row[el.dataset.field]=el.dataset.field==='reviewed_at'?stamp(el.value):el.value)});
}
function fill(){
 document.querySelectorAll('[data-point-row]').forEach(tr=>{const row=pointRows[Number(tr.dataset.pointRow)];tr.querySelectorAll('[data-field]').forEach(el=>el.value=el.dataset.field==='reviewed_at'?inputDate(row[el.dataset.field]):(row[el.dataset.field]??''))});
 document.querySelectorAll('[data-flag-row]').forEach(li=>{const row=flagRows[Number(li.dataset.flagRow)];li.querySelectorAll('[data-field]').forEach(el=>el.value=el.dataset.field==='reviewed_at'?inputDate(row[el.dataset.field]):(row[el.dataset.field]??''))});
 updateProgress();
}
function pointComplete(r){
 const decision=r.educator_decision, marks=String(r.educator_verified_marks??'').trim(), reviewer=String(r.educator_reviewer??'').trim(), reviewed=String(r.reviewed_at??'').trim();
 if(!decision||!reviewer||!reviewed)return false;
 if(decision==='UNRESOLVED')return !marks&&!!String(r.educator_rationale??'').trim();
 const n=Number(marks),max=Number(r.maximum_marks);if(!marks||!Number.isFinite(n)||n<0||n>max)return false;
 if(decision==='CHANGE'&&!String(r.educator_rationale??'').trim())return false;
 if(decision==='ACCEPT'&&Number(r.model_proposed_marks)>0&&r.point_quote_state!=='EXACT_QUESTION_SCOPED_QUOTE'&&!String(r.educator_verified_source_quote??'').trim())return false;
 return true;
}
function updateProgress(){
 const p=pointRows.filter(pointComplete).length;
 const f=flagRows.filter(r=>Boolean(r.educator_resolution&&String(r.educator_rationale??'').trim()&&String(r.educator_reviewer??'').trim()&&String(r.reviewed_at??'').trim())).length;
 document.getElementById('review-progress').textContent=`Point decisions recorded: ${p} / ${pointRows.length} · quality flags reviewed: ${f} / ${flagRows.length}. This is completion tracking only; it does not validate or issue marks.`;
}
function applyFilters(){
 const student=document.getElementById('filter-student').value;
 const query=document.getElementById('filter-search').value.trim().toLocaleLowerCase();
 const unresolved=document.getElementById('filter-unresolved').checked;
 const visible=new Set();
 document.querySelectorAll('[data-point-row]').forEach(tr=>{const row=pointRows[Number(tr.dataset.pointRow)];const pending=!pointComplete(row);const matchStudent=!student||tr.dataset.student===student;const matchText=!query||tr.textContent.toLocaleLowerCase().includes(query);const show=matchStudent&&matchText&&(!unresolved||pending);tr.hidden=!show;if(show)visible.add(tr.closest('.learner'))});
 document.querySelectorAll('[data-flag-row]').forEach(li=>{const row=flagRows[Number(li.dataset.flagRow)];const pending=!(row.educator_resolution&&String(row.educator_rationale??'').trim()&&String(row.educator_reviewer??'').trim()&&String(row.reviewed_at??'').trim());const matchStudent=!student||li.dataset.student===student;const matchText=!query||li.textContent.toLocaleLowerCase().includes(query);const show=matchStudent&&matchText&&(!unresolved||pending);li.hidden=!show;if(show)visible.add(li.closest('.learner'))});
 document.querySelectorAll('.learner').forEach(section=>section.hidden=!visible.has(section));
 document.querySelectorAll('.learner details').forEach(detail=>{const rows=[...detail.querySelectorAll('[data-point-row]')];if(rows.length)detail.hidden=!rows.some(row=>!row.hidden)});
}
function makeDraft(){collect();return {schema:'dio.homs.assess.educator_review_draft.v1',packet_fingerprint:reviewContext.packet_fingerprint,context_sha256:reviewContext.context_sha256,saved_at:new Date().toISOString(),point_rows:pointRows.map(r=>({key:pointKey(r),values:Object.fromEntries(editablePoint.map(k=>[k,r[k]??'']))})),quality_flag_rows:flagRows.map(r=>({key:flagKey(r),values:Object.fromEntries(editableFlag.map(k=>[k,r[k]??'']))}))}}
function applyDraft(d){
 if(!d||d.schema!=='dio.homs.assess.educator_review_draft.v1'||d.packet_fingerprint!==reviewContext.packet_fingerprint||d.context_sha256!==reviewContext.context_sha256)throw new Error('Draft type, packet fingerprint or source/proposal context does not match this review.');
 if(!Array.isArray(d.point_rows)||!Array.isArray(d.quality_flag_rows)||d.point_rows.length!==reviewContext.point_row_count||d.quality_flag_rows.length!==reviewContext.quality_flag_row_count||d.point_rows.length!==pointRows.length||d.quality_flag_rows.length!==flagRows.length)throw new Error('Draft row counts do not match this review.');
 const p=new Map(d.point_rows.map(r=>[r.key,r])), f=new Map(d.quality_flag_rows.map(r=>[r.key,r]));
 if(p.size!==pointRows.length||pointRows.some(r=>!p.has(pointKey(r)))||f.size!==flagRows.length||flagRows.some(r=>!f.has(flagKey(r))))throw new Error('Draft rows do not match this packet and source flags.');
 for(const row of pointRows){const v=p.get(pointKey(row)).values;if(!v||Object.keys(v).some(k=>!editablePoint.includes(k)))throw new Error('Draft contains an unexpected point field.');for(const k of editablePoint)row[k]=v[k]??''}
 for(const row of flagRows){const v=f.get(flagKey(row)).values;if(!v||Object.keys(v).some(k=>!editableFlag.includes(k)))throw new Error('Draft contains an unexpected quality-flag field.');for(const k of editableFlag)row[k]=v[k]??''}
 fill();applyFilters();
}
document.getElementById('download-adjudication').addEventListener('click',()=>{collect();downloadCsv('EDUCATOR_POINTWISE_ADJUDICATION_COMPLETED.csv',pointFields,pointRows);downloadCsv('EDUCATOR_MARKING_QUALITY_FLAGS_COMPLETED.csv',flagFields,flagRows);status.textContent='CSV review files downloaded. Run the documented validator before using the educator reconciliation.'});
document.getElementById('save-review-draft').addEventListener('click',()=>{const d=makeDraft();download('HOMS_ASSESS_EDUCATOR_REVIEW_DRAFT.json',new Blob([JSON.stringify(d,null,2)+'\n'],{type:'application/json'}));status.textContent='Review draft downloaded. Keep it with the matching packet and load it here to resume.'});
document.getElementById('load-review-draft').addEventListener('change',async e=>{const file=e.target.files?.[0];if(!file)return;try{if(file.size>5_000_000)throw new Error('Draft file exceeds the 5 MB limit.');applyDraft(JSON.parse(await file.text()));status.textContent='Matching review draft loaded. Confirm every entry against the original submission and memo before export.'}catch(err){status.textContent=err.message||'Draft could not be loaded.'}finally{e.target.value=''}});
for(const el of document.querySelectorAll('[data-field]')){const changed=()=>{collect();updateProgress();applyFilters()};el.addEventListener('input',changed);el.addEventListener('change',changed)}
for(const id of ['filter-student','filter-search','filter-unresolved']){document.getElementById(id).addEventListener('input',applyFilters);document.getElementById(id).addEventListener('change',applyFilters)}
fill();applyFilters();
})();</script>"""
    page = output_dir / "index.html"
    page.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>HOMS Assess · pointwise educator review</title>"
        "<style>body{font:16px/1.55 system-ui,sans-serif;max-width:1080px;margin:32px auto;padding:0 18px;color:#20302f}h1,h2{line-height:1.2}a{color:#075d71}:focus-visible{outline:3px solid #a66a27;outline-offset:2px}.banner,.flags{padding:14px;border-left:4px solid #a66a27;background:#fff7e8;margin:16px 0}.learner{border-top:2px solid #ccd5cf;margin-top:30px;padding-top:12px}.status{font-weight:700}.withheld{color:#8a2e24;font-weight:700}.provisional{color:#815d16;font-weight:700}.prompt{font-weight:600}details{border:1px solid #ccd5cf;border-radius:8px;padding:12px;margin:12px 0}summary{cursor:pointer}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #ccd5cf}blockquote{margin:8px 0 12px;padding:10px 14px;background:#f4f7f5;border-left:3px solid #517e72;white-space:pre-wrap}.unbound{background:#fff1ef;border-color:#a12b22}.source-suggestions{background:#f2f6ff;border-color:#517eae}.conflict-hold{padding:14px;border-left:5px solid #a12b22;background:#fff0ed;color:#5f1712;margin:14px 0}.missing{color:#8a2e24}.review-tools{padding:16px;border:1px solid #b8c6bf;border-radius:8px;background:#f5f8f6;margin:18px 0}.review-tools label{display:inline-grid;gap:5px;margin:6px 12px 6px 0}.review-tools input,.review-tools select{font:inherit;padding:8px;border:1px solid #98aaa2;border-radius:4px}.review-tools button,.review-tools .file-label{margin:6px 8px 6px 0}.review-tools [hidden]{display:none!important}[hidden]{display:none!important}.review-status{min-height:1.5em;font-weight:600}</style><style>.decision-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:14px 0;padding:12px;border:1px solid #c4cec8;border-radius:8px}.decision-fields legend{font-weight:700}.decision-fields label{display:grid;gap:4px;font-size:13px}.decision-fields .wide{grid-column:1/-1}.decision-fields input,.decision-fields select,.decision-fields textarea{font:inherit;padding:7px;border:1px solid #98aaa2;border-radius:4px;max-width:100%}button{font:600 15px system-ui;padding:12px 18px;color:#fff;background:#075d71;border:0;border-radius:5px;cursor:pointer}button:focus-visible{outline:3px solid #a66a27;outline-offset:3px}.export-note{padding:12px;background:#eef5f3;border-left:4px solid #517e72}@media(max-width:700px){.decision-fields{grid-template-columns:1fr}.decision-fields .wide{grid-column:auto}.review-tools label{display:grid}}</style><main>"
        "<p>HOMS ASSESS · SOURCE-BOUND EDUCATOR REVIEW</p><h1>Pointwise marking proposals</h1>"
        "<div class='banner'><strong>Review only.</strong> Every displayed mark is a machine proposal, not an issued score. Exact learner excerpts are question-level anchors and do not prove each memo point. Verify every point against the complete response, source paper and memo. Resolve all flags before using any total. Unreturned point IDs remain unscored; no zero mark is inferred.</div>"
        "<p>Record educator decisions below and download completed CSVs for validation. Possible exact excerpts are retrieved from the same answer using shared memo wording; they are navigation aids, not verified point evidence. Review times are entered in local time and exported as timezone-aware UTC. Empty fields remain unresolved; the export does not issue marks or authorize release.</p>"
        "<p>Packet fingerprint: <code>" + html.escape(customer_packet_fingerprint) + "</code></p>"
        "<ul>" + "".join(links) + "</ul><section class='review-tools' aria-label='Educator review controls'>"
        "<h2>Review workspace</h2><p id='review-progress' aria-live='polite'></p>"
        "<label>Filter learner <select id='filter-student'><option value=''>All learners</option>" + filter_student_options + "</select></label>"
        "<label>Find question, memo point, answer or flag <input id='filter-search' type='search' autocomplete='off'></label>"
        "<label><input id='filter-unresolved' type='checkbox'> Show unresolved decisions only</label><br>"
        "<button id='save-review-draft' type='button'>Save review draft JSON</button>"
        "<label class='file-label'>Resume from draft JSON <input id='load-review-draft' type='file' accept='application/json,.json'></label>"
        "<button id='download-adjudication' type='button'>Download educator review CSVs</button>"
        "<p id='review-status' class='review-status' role='status' aria-live='polite'></p>"
        "<p class='export-note'>JSON drafts contain educator-entered decisions only and are downloaded to this device; this page does not save learner records in browser storage or send them over the network. Keep a draft with its matching packet. CSV export includes the bound review evidence. Totals remain held until review is complete and the documented validator passes.</p></section>"
        "<script type='application/json' id='point-fields'>" + point_fields_json + "</script>"
        "<script type='application/json' id='point-rows'>" + point_rows_json + "</script>"
        "<script type='application/json' id='review-context'>" + review_context_json + "</script>"
        "<script type='application/json' id='flag-fields'>" + flag_fields_json + "</script>"
        "<script type='application/json' id='flag-rows'>" + flag_rows_json + "</script>"
        + "".join(sections)
        + "<p>" + html.escape(str(withheld)) + " total(s) withheld · " + html.escape(str(provisional)) + " provisional total(s) · no classroom release authorized.</p></main>"
        + review_export_script + "</body></html>\n",
        encoding="utf-8",
    )
    try:
        page.chmod(0o600)
    except OSError:
        pass
    receipt = {
        "schema": "dio.homs.assess.pointwise_educator_review.v1",
        "page": page.name,
        "page_sha256": _sha(page),
        "customer_packet_fingerprint": customer_packet_fingerprint,
        "source_hashes": {str(path.relative_to(ROOT)): _sha(path) for path in source_paths},
        "grade": int(rubric.get("grade") or 0), "subject": rubric.get("subject"),
        "criterion_count": len(rubric.get("criteria") or []),
        "submission_count": len(results), "withheld_score_count": withheld,
        "provisional_score_count": provisional,
        "criterion_answer_block_count": len(criterion_answer_block_bindings),
        "criterion_answer_blocks": criterion_answer_block_bindings,
        "missing_point_answer_block_count": len(answer_block_bindings),
        "missing_point_answer_blocks": answer_block_bindings,
        "model_quote_candidate_not_bound_to_question_count": sum(
            len(json.loads(row["model_quote_candidates_not_bound_to_question_json"])) for row in adjudication_rows
        ),
        "points_with_quote_candidates_not_bound_to_question": sum(
            bool(json.loads(row["model_quote_candidates_not_bound_to_question_json"])) for row in adjudication_rows
        ),
        "exact_question_source_quote_suggestion_count": sum(
            len(json.loads(row["exact_question_source_quote_suggestions_json"])) for row in adjudication_rows
        ),
        "points_with_exact_question_source_quote_suggestions": sum(
            bool(json.loads(row["exact_question_source_quote_suggestions_json"])) for row in adjudication_rows
        ),
        "suggestions_are_unverified_and_do_not_mutate_proposals": True,
        "draft_export_schema": "dio.homs.assess.educator_review_draft.v1",
        "draft_resume_supported": True,
        "draft_contains_educator_fields_only": True,
        "draft_context_sha256": draft_context_sha256,
        "draft_context_binds_source_and_model_proposals": True,
        "browser_storage_used": False,
        "network_requests_from_review_surface": False,
        "source_results_sha256": _sha(results_path),
        "score_mutation_performed": False,
        "suggestion_method": "verbatim sentence retrieval ranked by lexical overlap with memo-point wording; not a semantic scoring decision",
        "marks_are_final": False, "educator_review_required": True,
        "classroom_release_authorized": False, "external_processing": False,
    }
    receipt_path = output_dir / "POINTWISE_REVIEW_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        receipt_path.chmod(0o600)
    except OSError:
        pass
    return {
        "path": page, "sha256": _sha(page), "receipt_path": receipt_path,
        "receipt_sha256": _sha(receipt_path), "receipt": receipt,
        "adjudication_path": adjudication_path,
        "adjudication_sha256": _sha(adjudication_path),
        "quality_flags_path": quality_flags_path,
        "quality_flags_sha256": _sha(quality_flags_path),
        "adjudication_receipt_path": adjudication_receipt_path,
        "adjudication_receipt_sha256": _sha(adjudication_receipt_path),
        "adjudication_receipt": adjudication_receipt,
        "adjudication_guide_path": guide_path,
        "adjudication_guide_sha256": _sha(guide_path),
    }


def build_homs_assess_customer_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    if packet.get("owner_authorized") is not True:
        raise ValueError("owner_authorized=true is required before processing learner submissions")
    customer_packet_dir = Path(str(packet.get("customer_packet_dir") or "")).expanduser().resolve()
    if not customer_packet_dir.is_dir() or "EXAMINER" in {part.upper() for part in customer_packet_dir.parts}:
        raise ValueError("customer_packet_dir must identify a manifested CUSTOMER_PACKET, not examiner material")
    source_packet = load_packet(customer_packet_dir)
    if source_packet["manifest"].get("incarnation") != "HOMS Assess":
        raise ValueError("customer packet manifest must identify HOMS Assess")
    try:
        grade = int(packet.get("grade") or source_packet["intake"].get("grade") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("grade must be an integer from 1 through 12") from exc
    if grade not in range(1, 13):
        raise ValueError("grade must be an integer from 1 through 12")
    rubric = source_packet["packet_dir"] / "SOURCES/hymark_input/rubric.json"
    if not rubric.is_file():
        raise ValueError("customer HOMS Assess packet must bind a rubric and original assessment sources")
    rubric_data = json.loads(rubric.read_text(encoding="utf-8"))
    if int(rubric_data.get("grade") or 0) != grade:
        raise ValueError("requested grade does not match the packet-bound assessment rubric")
    subject = str(rubric_data.get("subject") or "")
    if packet.get("subject") and str(packet["subject"]).strip().casefold() != subject.casefold():
        raise ValueError("requested subject does not match the packet-bound assessment rubric")
    model = str(packet.get("model") or "granite3.3:2b").strip()
    if len(model) > 120 or any(char in model for char in "\r\n"):
        raise ValueError("invalid local model identifier")
    temperature = float(packet.get("temperature", 0.0))
    if not 0.0 <= temperature <= 1.0:
        raise ValueError("temperature must be between 0.0 and 1.0")

    out = Path(output_dir).resolve()
    projection_path = out / "projection" / "ENGINE_INPUT.json"
    projection_path.parent.mkdir(parents=True, exist_ok=True)
    engine_input = out / "input"
    projection = homs_assess_projection(source_packet, engine_input)
    write_json(projection_path, projection)
    projected_rubric = json.loads((engine_input / "rubric.json").read_text(encoding="utf-8"))
    pointwise_criterion_count = sum(bool(row.get("marking_points")) for row in projected_rubric.get("criteria") or [])
    pointwise_mark_count = sum(len(row.get("marking_points") or []) for row in projected_rubric.get("criteria") or [])
    # Customer use is local-only by contract. A model outage/error is retained
    # as a failed provider run; it never falls back to remote inference.
    os.environ["HOMS_AI_TEMPERATURE"] = str(temperature)
    os.environ.setdefault("HOMS_AI_MAX_RETRIES", "0")
    os.environ.setdefault("HOMS_AI_MAX_TOKENS", "4000")
    run_root = out / "hymark"
    batch_receipt = run_batch(
        engine_input, run_root, Path(DEFAULT_SECRET_FILE), Path(DEFAULT_HYMARK_BACKEND), "ollama", model,
    )
    provider_config = batch_receipt.get("provider") or {}
    scoring_configuration = {
        "provider": provider_config.get("selected_provider"),
        "model": provider_config.get("selected_model") or model,
        "temperature": temperature,
        "seed": provider_config.get("seed"),
        "reasoning_mode": (
            "QWEN3_NON_THINKING_PROMPT_SWITCH"
            if os.getenv("HOMS_AI_NO_THINK", "").strip().casefold() in {"1", "true", "yes"}
            and model.casefold().startswith("qwen3") else "PROVIDER_DEFAULT"
        ),
        "assessor_backend_sha256": _sha(Path(DEFAULT_HYMARK_BACKEND)),
        "rubric_sha256": _sha(rubric),
        "input_file_sha256": batch_receipt.get("input_file_sha256") or {},
        "comparability_boundary": "A score proposal is specific to its packet, assessment binding, rubric, model, temperature, seed and assessor backend. Changes to any of these create a different proposal; none is an educator-issued mark.",
    }
    job_dir = Path(str(batch_receipt["outputs"]["job_dir"])).resolve()
    if not job_dir.is_relative_to(out) or not job_dir.is_dir():
        raise RuntimeError("HOMS Assess output escaped the customer job directory")
    results_path = Path(str(batch_receipt["outputs"]["results"])).resolve()
    results = json.loads(results_path.read_text(encoding="utf-8"))
    marks_path = Path(str(batch_receipt["outputs"]["marks_csv"])).resolve()
    with marks_path.open("r", encoding="utf-8", newline="") as handle:
        marks_rows = {row.get("student_id"): row for row in csv.DictReader(handle)}
    summary_path = Path(str(batch_receipt["outputs"]["lecturer_summary"])).resolve()
    summary_text = summary_path.read_text(encoding="utf-8")
    for row in results:
        mark_row = marks_rows.get(row.get("student_id"))
        if not mark_row:
            raise RuntimeError("HOMS Assess did not emit a matching review marks row")
        if score_is_blocked(row):
            incomplete = row.get("score_status") == "BLOCKED_INCOMPLETE_POINTWISE_RESPONSE"
            proposal_valid = row.get("proposed_total_score") is None if incomplete else isinstance(row.get("proposed_total_score"), (int, float))
            if row.get("total_score") is not None or row.get("percentage") is not None or row.get("score_issued") is not False or not proposal_valid:
                raise RuntimeError("HOMS Assess score-withholding invariant failed in result JSON")
            if mark_row.get("score", "") != "" or (incomplete and mark_row.get("proposed_score", "") != "") or (not incomplete and mark_row.get("proposed_score", "") == ""):
                raise RuntimeError("HOMS Assess score-withholding invariant failed in marks CSV")
            if f"- {row.get('student_id')}: NOT SCORED" not in summary_text:
                raise RuntimeError("HOMS Assess withheld score is not reported as NOT SCORED")
        elif (row.get("score_status") != "PROVISIONAL_EDUCATOR_REVIEW_REQUIRED"
              or row.get("total_score") is not None or row.get("percentage") is not None or row.get("score_issued") is not False
              or not isinstance(row.get("proposed_total_score"), (int, float))
              or not isinstance(row.get("proposed_percentage"), (int, float))
              or mark_row.get("score", "") != "" or mark_row.get("percentage", "") != ""
              or mark_row.get("proposed_score", "") == ""):
            raise RuntimeError("HOMS Assess issued an automated total or lost the educator-review proposal")
    withheld = sum(1 for row in results if score_is_blocked(row))
    provisional = len(results) - withheld
    defaulted_zero_proposal_count = sum(
        len(criterion.get("omitted_point_ids_defaulted_to_zero") or [])
        for result in results
        for criterion in (result.get("criteria_scores") or {}).values()
        if isinstance(criterion, dict)
    )
    unreturned_point_count = sum(
        len(criterion.get("unreturned_point_ids") or [])
        for result in results
        for criterion in (result.get("criteria_scores") or {}).values()
        if isinstance(criterion, dict)
    )
    status_counts: dict[str, int] = {}
    for row in results:
        state = str(row.get("score_status") or "PROVISIONAL_EDUCATOR_REVIEW_REQUIRED")
        status_counts[state] = status_counts.get(state, 0) + 1
    pointwise_review = build_pointwise_educator_review(
        engine_input, projected_rubric, results, results_path, out / "educator_review",
        customer_packet_fingerprint=source_packet["packet_fingerprint"],
    )
    review_zip_path = Path(str(batch_receipt["outputs"].get("review_zip") or "")).resolve()
    if review_zip_path.is_file() and review_zip_path.is_relative_to(out):
        with zipfile.ZipFile(review_zip_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(pointwise_review["path"], "educator_review/index.html")
            archive.write(pointwise_review["receipt_path"], "educator_review/POINTWISE_REVIEW_RECEIPT.json")
            archive.write(pointwise_review["adjudication_path"], "educator_review/EDUCATOR_POINTWISE_ADJUDICATION.csv")
            archive.write(pointwise_review["quality_flags_path"], "educator_review/EDUCATOR_MARKING_QUALITY_FLAGS.csv")
            archive.write(pointwise_review["adjudication_receipt_path"], "educator_review/EDUCATOR_POINTWISE_ADJUDICATION_RECEIPT.json")
            archive.write(pointwise_review["adjudication_guide_path"], "educator_review/EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md")
    package = {
        "schema": "dio.homs.assess.customer_execution.v1",
        "product_name": "HOMS Assess", "grade": grade, "subject": subject,
        "customer_packet_fingerprint": source_packet["packet_fingerprint"],
        "source_packet_manifest_sha256": _sha(source_packet["manifest_path"]),
        "assessment_binding_sha256": _sha(engine_input / "ASSESSMENT_BINDING_RECEIPT.json"),
        "local_provider": batch_receipt.get("provider"),
        "scoring_configuration": scoring_configuration,
        "provider_errors": batch_receipt.get("provider_errors") or [], "temperature": temperature,
        "submission_count": len(results), "withheld_score_count": withheld,
        "provisional_score_count": provisional, "score_status_counts": status_counts,
        "pointwise_marking_criterion_count": pointwise_criterion_count,
        "pointwise_marking_point_count": pointwise_mark_count,
        "pointwise_marking_state": projection.get("pointwise_marking_state"),
        "omitted_point_ids_defaulted_to_zero": defaulted_zero_proposal_count,
        "unreturned_point_count": unreturned_point_count,
        "score_withholding_invariants_passed": True,
        "controlled_synthetic_demo": bool(packet.get("controlled_synthetic_demo")),
        "marks_are_final": False, "educator_review_required": True,
        "classroom_release_authorized": False, "external_processing": False,
        "outputs": {
            key: (str(Path(value).resolve().relative_to(out)) if value and Path(value).resolve().is_relative_to(out) else None)
            for key, value in (batch_receipt.get("outputs") or {}).items()
        },
    }
    package["outputs"]["pointwise_educator_review"] = pointwise_review["path"].relative_to(out).as_posix()
    package["outputs"]["pointwise_review_receipt"] = pointwise_review["receipt_path"].relative_to(out).as_posix()
    package["outputs"]["pointwise_adjudication_csv"] = pointwise_review["adjudication_path"].relative_to(out).as_posix()
    package["outputs"]["quality_flag_review_csv"] = pointwise_review["quality_flags_path"].relative_to(out).as_posix()
    package["outputs"]["pointwise_adjudication_receipt"] = pointwise_review["adjudication_receipt_path"].relative_to(out).as_posix()
    package["outputs"]["pointwise_adjudication_guide"] = pointwise_review["adjudication_guide_path"].relative_to(out).as_posix()
    package["pointwise_review_sha256"] = pointwise_review["sha256"]
    package["pointwise_review_receipt_sha256"] = pointwise_review["receipt_sha256"]
    package["pointwise_adjudication_sha256"] = pointwise_review["adjudication_sha256"]
    package["quality_flag_review_sha256"] = pointwise_review["quality_flags_sha256"]
    package["pointwise_adjudication_receipt_sha256"] = pointwise_review["adjudication_receipt_sha256"]
    package["pointwise_adjudication_guide_sha256"] = pointwise_review["adjudication_guide_sha256"]
    package_path = out / "CUSTOMER_PACKAGE_RECEIPT.json"
    package_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    items = []
    for key, label in (("results", "Machine-readable proposals"), ("marks_csv", "Review-only marks CSV"), ("lecturer_summary", "Lecturer review summary"), ("review_zip", "Held review bundle"), ("pointwise_adjudication_csv", "Blank point-level adjudication CSV"), ("quality_flag_review_csv", "Blank marking-quality flag review CSV"), ("pointwise_adjudication_guide", "Point-level adjudication instructions")):
        relative = package["outputs"].get(key)
        if relative:
            items.append(f"<li><a href='{html.escape(relative, quote=True)}'>{html.escape(label)}</a></li>")
    run_context_html = (
        "<section class='note'><h2>Scoring run context</h2><p>"
        + html.escape(str(scoring_configuration.get("provider") or "unknown")) + " / "
        + html.escape(str(scoring_configuration.get("model") or "unknown"))
        + " · temperature " + html.escape(str(temperature))
        + (" · seed " + html.escape(str(scoring_configuration["seed"])) if scoring_configuration.get("seed") is not None else "")
        + "</p><p>" + html.escape(scoring_configuration["comparability_boundary"]) + "</p>"
        + "<p>Packet fingerprint: <code>" + html.escape(source_packet["packet_fingerprint"]) + "</code><br>Rubric SHA-256: <code>" + html.escape(scoring_configuration["rubric_sha256"]) + "</code></p>"
        + "<p>Assessor backend SHA-256: <code>" + html.escape(scoring_configuration["assessor_backend_sha256"]) + "</code></p></section>"
    )
    (out / "CUSTOMER_ASSESS_REVIEW.html").write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>HOMS Assess · Grade {grade}</title><style>body{{font:16px/1.55 system-ui,sans-serif;max-width:900px;margin:36px auto;padding:0 18px;color:#20302f}}.note{{border-left:4px solid #a66a27;padding:14px;background:#fff7e8}}a{{color:#075d71}}code{{overflow-wrap:anywhere}}</style><main><p>HOMS ASSESS · GRADE {grade} · {html.escape(subject)}</p><h1>Educator marking review</h1><p>{len(results)} submission(s) · {withheld} score(s) withheld · {provisional} provisional for educator review.</p><p>{pointwise_criterion_count} source-bound criteria with {pointwise_mark_count} separately allocated memo points; {unreturned_point_count} unreturned point ID(s) remain unscored and block their total. No omitted point is treated as zero.</p>"
        + run_context_html
        + "<ul>" + "".join(items)
        + f"<li><a href='{html.escape(package['outputs']['pointwise_educator_review'], quote=True)}'>Open pointwise educator review surface</a></li></ul><p class='note'>Automated marks are not final. A withheld score stays blank in exported score fields. Review each criterion's complete source-bound learner answer block and compare every point proposal against the bound memo before gradebook use. Unreturned point IDs remain unscored and prevent criterion and assessment totals. No external processing or classroom release was authorized.</p></main></html>\n",
        encoding="utf-8",
    )
    package["customer_review_html"] = "CUSTOMER_ASSESS_REVIEW.html"
    package["customer_review_html_sha256"] = _sha(out / "CUSTOMER_ASSESS_REVIEW.html")
    package_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package
