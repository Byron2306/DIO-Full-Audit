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


def _repair_sections(
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
        max_tokens=3600,
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

    path = out_dir / f"HOMS_SOURCE_FIRST_SECTION_REPAIR_ATTEMPT_{attempt}.json"
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

    provider = source_first.configure_provider(secret_file, provider_name, model)
    hymark = source_first.load_hymark_backend(backend_path)

    out_root.mkdir(parents=True, exist_ok=True)
    job_id = f"hymark-history-source-first-resume-second-{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
    job_dir = out_root / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(request_path, job_dir / "exam_builder_request.json")
    shutil.copy2(source_booklet, job_dir / "CUSTOMER_SOURCE_BOOKLET.md")
    shutil.copy2(locked_path, job_dir / "HOMS_LOCKED_CUSTOMER_SOURCES.json")
    shutil.copy2(saved_plan_path, job_dir / "HOMS_SAVED_SECOND_PLAN.json")

    if labels:
        for attempt in (1, 2):
            plan = _repair_sections(
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

    affected = set(labels)
    original_sections = {str(row.get("source_label") or ""): row for row in original_plan.get("source_sections") or []}
    repaired_sections = {str(row.get("source_label") or ""): row for row in plan.get("source_sections") or []}
    for label, section in original_sections.items():
        if label not in affected and repaired_sections.get(label) != section:
            raise RuntimeError(f"targeted repair illegally altered untouched section {label}")
    if plan.get("essay") != original_plan.get("essay"):
        raise RuntimeError("targeted section repair illegally altered the accepted essay")

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
