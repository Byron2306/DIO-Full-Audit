#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import run_hymark_history_source_first as source_first
except ModuleNotFoundError:
    import run_hymark_history_source_first as source_first


SCHEMA = source_first.SCHEMA
ENGINE_IDENTITY = source_first.ENGINE_IDENTITY


def _affected_labels(errors: list[str]) -> list[str]:
    labels: list[str] = []
    for error in errors:
        match = re.match(r"^(Source\s+[A-Z])\b", str(error))
        if match and match.group(1) not in labels:
            labels.append(match.group(1))
    return labels


def _section_by_label(plan: dict[str, Any], label: str) -> dict[str, Any]:
    for section in plan.get("source_sections") or []:
        if str(section.get("source_label") or "") == label:
            return dict(section)
    raise RuntimeError(f"saved HOMS plan has no section for {label}")


def _source_by_label(sources: list[dict[str, str]], label: str) -> dict[str, str]:
    for source in sources:
        if source.get("label") == label:
            return source
    raise RuntimeError(f"locked HOMS sources have no source for {label}")


def _sentence_points(text: str, count: int) -> list[str]:
    sentences = [
        re.sub(r"\s+", " ", sentence).strip(" -\n\t")
        for sentence in re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        if re.sub(r"\s+", " ", sentence).strip(" -\n\t")
    ]
    points: list[str] = []
    for sentence in sentences:
        if len(sentence.split()) < 5:
            continue
        points.append(sentence)
        if len(points) >= count:
            break
    return points


def _merge_smallest_adjacent_pair(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(questions) < 2:
        return questions
    pair_index = min(
        range(len(questions) - 1),
        key=lambda index: int(questions[index].get("marks") or 0) + int(questions[index + 1].get("marks") or 0),
    )
    left = dict(questions[pair_index])
    right = dict(questions[pair_index + 1])
    left_q = str(left.get("question") or "").strip()
    right_q = str(right.get("question") or "").strip()
    merged = {
        "question": f"Answer BOTH parts: (a) {left_q} (b) {right_q}",
        "marks": int(left.get("marks") or 0) + int(right.get("marks") or 0),
        "memo": [
            *[str(item).strip() for item in left.get("memo") or [] if str(item).strip()],
            *[str(item).strip() for item in right.get("memo") or [] if str(item).strip()],
        ],
        "dio_deterministic_merge": True,
    }
    return [*questions[:pair_index], merged, *questions[pair_index + 2 :]]


def _repair_section_deterministically(section: dict[str, Any], source: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Repair structural mark/count defects without asking a model to rewrite valid content."""
    updated = json.loads(json.dumps(section))
    questions = [dict(row) for row in updated.get("questions") or []]
    actions: list[str] = []

    while len(questions) > 10:
        questions = _merge_smallest_adjacent_pair(questions)
        actions.append("merged_smallest_adjacent_question_pair")

    total = sum(int(question.get("marks") or 0) for question in questions)
    deficit = 30 - total
    if deficit > 0:
        # Prefer adding a new, explicitly source-grounded question. This preserves
        # the mark values and memo semantics of every existing generated question.
        if len(questions) >= 10:
            questions = _merge_smallest_adjacent_pair(questions)
            actions.append("merged_pair_to_create_grounded_question_slot")
        points = _sentence_points(source.get("content", ""), deficit)
        if len(points) >= deficit and deficit <= 4 and len(questions) < 10:
            number_word = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR"}[deficit]
            questions.append(
                {
                    "question": f"Identify {number_word} distinct ideas or arguments presented in {source['label']}.",
                    "marks": deficit,
                    "memo": points[:deficit],
                    "dio_deterministic_source_grounded_fill": True,
                }
            )
            actions.append(f"added_source_grounded_{deficit}_mark_question")
        else:
            # Conservative fallback: only increase marks where the existing memo
            # already contains more explicit answer points than the question's
            # current allocation. No new historical claim is invented.
            remaining = deficit
            ranked = sorted(
                range(len(questions)),
                key=lambda index: len([item for item in questions[index].get("memo") or [] if str(item).strip()])
                - int(questions[index].get("marks") or 0),
                reverse=True,
            )
            for index in ranked:
                if remaining <= 0:
                    break
                question = questions[index]
                memo_count = len([item for item in question.get("memo") or [] if str(item).strip()])
                marks = int(question.get("marks") or 0)
                capacity = max(0, memo_count - marks)
                if capacity <= 0:
                    continue
                add = min(capacity, remaining)
                question["marks"] = marks + add
                remaining -= add
                actions.append(f"reallocated_{add}_marks_to_existing_explicit_memo_points")
            if remaining:
                raise RuntimeError(
                    f"deterministic repair cannot fill {remaining} remaining marks for {source['label']} without inventing content"
                )
    elif deficit < 0:
        raise RuntimeError(
            f"deterministic repair refuses to remove {-deficit} marks from {source['label']}; provider review required"
        )

    updated["questions"] = questions
    return updated, actions


def _deterministic_repair(
    *,
    plan: dict[str, Any],
    sources: list[dict[str, str]],
    labels: list[str],
    out_dir: Path,
) -> tuple[dict[str, Any], list[str]]:
    updated = json.loads(json.dumps(plan))
    actions: list[str] = []
    for index, section in enumerate(updated.get("source_sections") or []):
        label = str(section.get("source_label") or "")
        if label not in labels:
            continue
        repaired, section_actions = _repair_section_deterministically(
            dict(section), _source_by_label(sources, label)
        )
        updated["source_sections"][index] = repaired
        actions.extend(f"{label}:{action}" for action in section_actions)

    path = out_dir / "HOMS_SOURCE_FIRST_DETERMINISTIC_SECTION_REPAIR.json"
    path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated, actions


def _repair_sections_with_provider(
    hymark: Any,
    *,
    plan: dict[str, Any],
    sources: list[dict[str, str]],
    labels: list[str],
    errors: list[str],
    attempt: int,
    out_dir: Path,
) -> dict[str, Any]:
    if not labels:
        raise RuntimeError("section repair requested with no affected source labels")

    repair_payload = []
    for label in labels:
        source = _source_by_label(sources, label)
        existing = _section_by_label(plan, label)
        repair_payload.append(
            {
                "source_label": label,
                "locked_source_text": source["content"],
                "existing_questions": existing.get("questions") or [],
            }
        )

    prompt = f"""Repair ONLY the invalid source-question blocks in an existing Grade 11 South African History examination plan.

CURRENT VALIDATION ERRORS
{chr(10).join(f'- {error}' for error in errors)}

SOURCE BLOCKS TO REPAIR
{json.dumps(repair_payload, ensure_ascii=False, indent=2)}

NON-NEGOTIABLE RULES
- Return replacements ONLY for the listed source labels.
- Each returned source block must total exactly 30 marks.
- Each returned source block must contain 5-10 substantive subquestions.
- Preserve the locked source text exactly. Do not rewrite or expand it.
- Every question must have a positive integer mark value and a specific memorandum array containing actual expected answer points.
- Use a sensible progression of historical skills: extraction/contextualisation, inference, usefulness/reliability, interpretation/comparison/evaluation where supported by the source.
- Do not invent an author, historian, quotation, publication, date, photograph, cartoon, image, map, graph or source provenance.
- Do not use generic memo instructions such as 'credit a valid answer'.
- Do not return or alter Source C or the essay unless one of them is explicitly listed above.

Return strict JSON only:
{{
  "source_sections": [
    {{
      "source_label": "Source A",
      "questions": [
        {{"question": "...", "marks": 2, "memo": ["specific answer point", "acceptable alternative"]}}
      ]
    }}
  ]
}}
"""
    repaired = source_first.model_json(
        hymark,
        "You are a South African FET History assessment repair specialist. Repair only the named source-question blocks and return JSON only.",
        prompt,
        max_tokens=2400,
        temperature=0.12 if attempt > 1 else 0.18,
    )
    returned = [dict(row) for row in repaired.get("source_sections") or [] if isinstance(row, dict)]
    returned_by_label = {str(row.get("source_label") or ""): row for row in returned}
    missing = [label for label in labels if label not in returned_by_label]
    if missing:
        raise RuntimeError("section repair omitted required labels: " + ", ".join(missing))

    updated = json.loads(json.dumps(plan))
    for index, section in enumerate(updated.get("source_sections") or []):
        label = str(section.get("source_label") or "")
        if label in returned_by_label:
            updated["source_sections"][index] = returned_by_label[label]

    path = out_dir / f"HOMS_SOURCE_FIRST_PROVIDER_SECTION_REPAIR_ATTEMPT_{attempt}.json"
    path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated


def repair_and_render(
    *,
    request_path: Path,
    saved_job: Path,
    out_root: Path,
    secret_file: Path,
    backend_path: Path,
    provider_name: str,
    model: str,
) -> dict[str, Any]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    source_booklet = Path(str(request.get("dio_customer_source_booklet") or "")).expanduser().resolve()
    if not source_booklet.is_file():
        raise RuntimeError("saved-plan repair requires the DIO customer source booklet")
    expected_hash = str(request.get("dio_customer_source_booklet_sha256") or "")
    if expected_hash and source_first.sha256(source_booklet) != expected_hash:
        raise RuntimeError("customer source booklet hash drifted before saved-plan repair")

    saved_job = saved_job.expanduser().resolve()
    locked_path = saved_job / "HOMS_LOCKED_CUSTOMER_SOURCES.json"
    if not locked_path.is_file():
        raise RuntimeError("interrupted HOMS job has no locked customer source record")
    sources = json.loads(locked_path.read_text(encoding="utf-8"))

    attempts = sorted((saved_job / "2ndOpp").glob("HOMS_SOURCE_FIRST_PLAN_ATTEMPT_*.json"))
    if not attempts:
        raise RuntimeError("interrupted HOMS job has no saved second-opportunity plan")
    saved_plan_path = attempts[-1]
    plan = json.loads(saved_plan_path.read_text(encoding="utf-8"))
    original_plan = json.loads(json.dumps(plan))
    errors = source_first._plan_errors(plan, sources)
    if not errors:
        labels: list[str] = []
    else:
        essay_errors = [error for error in errors if error.startswith("essay ")]
        other_errors = [error for error in errors if not error.startswith("essay ")]
        if essay_errors:
            raise RuntimeError("saved second plan has essay defects; section-only repair refuses to alter the essay")
        labels = _affected_labels(other_errors)
        if not labels or any(not error.startswith(tuple(labels)) for error in other_errors):
            raise RuntimeError("saved second plan requires broader-than-section repair: " + "; ".join(errors))

    out_root.mkdir(parents=True, exist_ok=True)
    job_id = f"hymark-history-source-first-resume-second-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    job_dir = out_root / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(request_path, job_dir / "exam_builder_request.json")
    shutil.copy2(source_booklet, job_dir / "CUSTOMER_SOURCE_BOOKLET.md")
    shutil.copy2(locked_path, job_dir / "HOMS_LOCKED_CUSTOMER_SOURCES.json")
    shutil.copy2(saved_plan_path, job_dir / "HOMS_SAVED_SECOND_PLAN.json")

    repair_mode = "saved_plan_already_valid"
    deterministic_actions: list[str] = []
    if labels:
        deterministic_error = ""
        try:
            plan, deterministic_actions = _deterministic_repair(
                plan=plan,
                sources=sources,
                labels=labels,
                out_dir=job_dir,
            )
            errors = source_first._plan_errors(plan, sources)
            if errors:
                deterministic_error = "; ".join(errors)
                plan = json.loads(json.dumps(original_plan))
        except RuntimeError as exc:
            deterministic_error = str(exc)
            plan = json.loads(json.dumps(original_plan))

        if not deterministic_error:
            repair_mode = "deterministic_structural_repair_no_provider"
        else:
            # Provider fallback is deliberately lazy. A model is contacted only
            # when local transformations cannot preserve truth and mark integrity.
            provider = source_first.configure_provider(secret_file, provider_name, model)
            hymark = source_first.load_hymark_backend(backend_path)
            for attempt in (1, 2):
                plan = _repair_sections_with_provider(
                    hymark,
                    plan=plan,
                    sources=sources,
                    labels=labels,
                    errors=source_first._plan_errors(plan, sources),
                    attempt=attempt,
                    out_dir=job_dir,
                )
                errors = source_first._plan_errors(plan, sources)
                if not errors:
                    break
            if errors:
                raise RuntimeError("targeted second-opportunity section repair failed: " + "; ".join(errors))
            repair_mode = "provider_section_repair_fallback"
    else:
        provider = {"selected_provider": "not_required_saved_plan_valid"}

    if repair_mode == "deterministic_structural_repair_no_provider":
        provider = {"selected_provider": "not_required_deterministic_repair"}

    affected = set(labels)
    original_sections = {str(row.get("source_label") or ""): row for row in original_plan.get("source_sections") or []}
    repaired_sections = {str(row.get("source_label") or ""): row for row in plan.get("source_sections") or []}
    for label, section in original_sections.items():
        if label not in affected and repaired_sections.get(label) != section:
            raise RuntimeError(f"targeted repair illegally altered untouched section {label}")
    if plan.get("essay") != original_plan.get("essay"):
        raise RuntimeError("targeted section repair illegally altered the accepted essay")

    final_errors = source_first._plan_errors(plan, sources)
    if final_errors:
        raise RuntimeError("saved-plan repair remained invalid: " + "; ".join(final_errors))

    result = source_first._render_opportunity(
        job_dir=job_dir,
        request=request,
        sources=sources,
        plan=plan,
        opportunity=2,
    )
    receipt = {
        "schema": SCHEMA,
        "status": "completed",
        "job_id": job_id,
        "assessor": {
            "name": "HyMark Exam Builder",
            "generation_backend": "hymark_history_source_first_saved_plan_section_repair",
            "native_engine": ENGINE_IDENTITY,
        },
        "provider": provider,
        "source_contract": {
            "customer_source_booklet": str(source_booklet),
            "customer_source_sha256": source_first.sha256(source_booklet),
            "locked_text_source_count": len(sources),
            "invented_provenance_allowed": False,
            "described_missing_visual_allowed": False,
        },
        "opportunities": {"second": result},
        "outputs": {
            "job_dir": str(job_dir),
            "second_exam": result["exam"],
            "second_memo": result["memo"],
        },
        "resume": {
            "saved_job": str(saved_job),
            "saved_plan": str(saved_plan_path),
            "affected_sections": labels,
            "repair_mode": repair_mode,
            "deterministic_actions": deterministic_actions,
            "source_c_preserved": "Source C" not in affected,
            "essay_preserved": True,
            "full_second_opportunity_regeneration": False,
        },
        "human_review_required": True,
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt_path = job_dir / "HYMARK_EXAM_BUILDER_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"receipt": str(receipt_path), "payload": receipt}


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair only invalid source sections in a saved HOMS second-opportunity plan, then render it.")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--saved-job", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--provider", default="nim")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    result = repair_and_render(
        request_path=args.request.expanduser().resolve(),
        saved_job=args.saved_job.expanduser().resolve(),
        out_root=args.out.expanduser().resolve(),
        secret_file=args.secret_file.expanduser().resolve(),
        backend_path=args.backend.expanduser().resolve(),
        provider_name=args.provider,
        model=args.model,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
