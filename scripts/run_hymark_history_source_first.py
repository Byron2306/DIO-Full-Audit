#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_homs_design_law import (  # noqa: E402
    DEFAULT_ASSESSMENT_DESIGN,
    DEFAULT_DESIGN_LAW,
    apply_design_law,
    assessment_design_for_pack,
    load_json as load_design_json,
    render_docx,
)
from run_hymark_exam_builder import (  # noqa: E402
    configure_provider,
    create_shell_memo_docx,
    load_hymark_backend,
    model_json,
    sum_question_marks,
    sum_rubric_marks,
    validate_assessment_pack,
    write_validation_report,
)


SCHEMA = "knowedge.hymark_exam_builder_receipt.v1"
ENGINE_IDENTITY = "scripts.run_hymark_history_source_first.run_builder"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_customer_sources(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = list(re.finditer(r"^##\s+(Source\s+[A-Z])\s*[—-]\s*(.+?)\s*$", text, flags=re.MULTILINE))
    sources: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end]
        content = re.split(r"^###\s+Customer note", content, maxsplit=1, flags=re.MULTILINE)[0]
        content = "\n".join(line.rstrip() for line in content.strip().splitlines()).strip()
        if not content:
            raise RuntimeError(f"customer source {match.group(1)} has no content")
        sources.append(
            {
                "label": match.group(1).strip(),
                "title": match.group(2).strip(),
                "content": content,
                "source_type": "text_extract",
                "provenance": "customer_supplied_exact_text",
            }
        )
    if len(sources) < 3:
        raise RuntimeError(f"History source-first builder requires at least three customer sources; found {len(sources)}")
    return sources


def _locked_sources_text(sources: list[dict[str, str]]) -> str:
    blocks = []
    for source in sources:
        blocks.append(
            f"{source['label']} — {source['title']}\n"
            f"PROVENANCE: customer supplied; no provenance may be invented.\n"
            f"LOCKED TEXT:\n{source['content']}"
        )
    return "\n\n".join(blocks)


def _generation_prompt(request: dict[str, Any], sources: list[dict[str, str]], opportunity: int) -> str:
    variation = (
        "First opportunity."
        if opportunity == 1
        else "Second opportunity. Keep equivalent difficulty and the same locked sources, but use materially different question wording, analytical moves and essay choices."
    )
    return f"""Create the QUESTION AND MEMORANDUM PLAN for a Grade {request.get('grade')} South African History examination.

{variation}
Total marks: {request.get('total_marks')}
Duration: {request.get('duration_hours')} hours
Topics: {'; '.join(request.get('topics') or [])}
Customer request: {request.get('customer_request', '')}

NON-NEGOTIABLE SOURCE LAW
- The source text below is immutable. Do not rewrite, expand, embellish or replace it.
- Do not invent any author, historian, photographer, publication, date, quotation, caption or provenance.
- Do not invent a photograph, cartoon, image, map or graph. If it is not in LOCKED SOURCES, it does not exist.
- Do not use words such as "fictional", "based on real historiography", "imagined", or "reconstructed source".
- Generate QUESTIONS AND SPECIFIC MEMORANDUM ANSWERS only.
- Each of the three source sections must total exactly 30 marks. Together they total 90 marks.
- Each source section should contain 5-8 substantive subquestions with a progression from retrieval/contextualisation through inference, reliability/usefulness, comparison or evaluation where warranted by the source itself.
- Every memo array must contain actual expected answer points and acceptable source-grounded alternatives. Never write generic phrases such as "credit a valid answer".
- The essay section is ONE 60-mark learner question offering TWO alternatives from which the learner chooses ONE. Give a detailed marking outline for both alternatives.
- Do not require information that the locked source does not provide unless the question explicitly tests contextual historical knowledge within the supplied topic scope.

LOCKED SOURCES
{_locked_sources_text(sources)}

Return strict JSON only:
{{
  "source_sections": [
    {{
      "source_label": "Source A",
      "questions": [
        {{"question": "...", "marks": 2, "memo": ["specific answer point", "acceptable alternative"]}}
      ]
    }}
  ],
  "essay": {{
    "option_a": "...",
    "option_b": "...",
    "memo_option_a": ["detailed content/argument point"],
    "memo_option_b": ["detailed content/argument point"],
    "marking_guidance": ["argument", "evidence", "analysis", "structure"]
  }}
}}
"""


def _plan_errors(plan: dict[str, Any], sources: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    sections = list(plan.get("source_sections") or [])
    if len(sections) != 3:
        errors.append(f"expected 3 source sections, found {len(sections)}")
    expected_labels = [source["label"] for source in sources[:3]]
    for index, label in enumerate(expected_labels):
        if index >= len(sections):
            continue
        section = sections[index]
        if str(section.get("source_label") or "") != label:
            errors.append(f"source section {index + 1} must bind to {label}")
        questions = list(section.get("questions") or [])
        total = sum(int(question.get("marks") or 0) for question in questions)
        if total != 30:
            errors.append(f"{label} questions total {total}, expected 30")
        if not 5 <= len(questions) <= 8:
            errors.append(f"{label} has {len(questions)} subquestions, expected 5-8")
        for q_index, question in enumerate(questions, 1):
            if not str(question.get("question") or "").strip():
                errors.append(f"{label} question {q_index} is empty")
            if int(question.get("marks") or 0) <= 0:
                errors.append(f"{label} question {q_index} has no marks")
            memo = [str(item).strip() for item in question.get("memo") or [] if str(item).strip()]
            if not memo:
                errors.append(f"{label} question {q_index} has no specific memo")
            if any("credit a valid" in item.casefold() for item in memo):
                errors.append(f"{label} question {q_index} contains generic memo language")
    essay = dict(plan.get("essay") or {})
    for key in ("option_a", "option_b"):
        if len(str(essay.get(key) or "").split()) < 10:
            errors.append(f"essay {key} is too thin")
    for key in ("memo_option_a", "memo_option_b"):
        if len(list(essay.get(key) or [])) < 6:
            errors.append(f"essay {key} needs at least 6 substantive marking points")
    blob = json.dumps(plan, ensure_ascii=False).casefold()
    for forbidden in ("fictional", "based on real historiography", "imagined source", "reconstructed source"):
        if forbidden in blob:
            errors.append(f"forbidden invented-source marker: {forbidden}")
    if any(term in blob for term in ("photograph", "cartoon", "image showing", "map extract", "graph shows")):
        errors.append("question plan references a visual that is not in the locked customer source set")
    return sorted(set(errors))


def _generate_plan(hymark: Any, request: dict[str, Any], sources: list[dict[str, str]], opportunity: int, opportunity_dir: Path) -> dict[str, Any]:
    system = (
        "You are an experienced South African FET History examiner. The source texts are immutable evidence objects. "
        "You write only rigorous source-based questions and specific marking memoranda. Return JSON only."
    )
    prompt = _generation_prompt(request, sources, opportunity)
    plan = model_json(hymark, system, prompt, max_tokens=5200, temperature=0.35)
    (opportunity_dir / "HOMS_SOURCE_FIRST_PLAN_ATTEMPT_1.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    errors = _plan_errors(plan, sources)
    if errors:
        repair = prompt + "\n\nThe previous plan failed these hard checks:\n" + "\n".join(f"- {error}" for error in errors) + "\nReturn a complete corrected JSON plan only."
        plan = model_json(hymark, system, repair, max_tokens=5600, temperature=0.18)
        (opportunity_dir / "HOMS_SOURCE_FIRST_PLAN_ATTEMPT_2.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        errors = _plan_errors(plan, sources)
    if errors:
        raise RuntimeError("History source-first provider plan failed after repair: " + "; ".join(errors))
    return plan


def _pack_from_plan(
    request: dict[str, Any],
    sources: list[dict[str, str]],
    plan: dict[str, Any],
    opportunity: int,
) -> dict[str, Any]:
    sections = []
    for index, (source, planned) in enumerate(zip(sources[:3], plan["source_sections"]), 1):
        questions = []
        for q_index, raw in enumerate(planned.get("questions") or [], 1):
            questions.append(
                {
                    "number": f"{index}.{q_index}",
                    "source_reference": source["label"],
                    "question": str(raw.get("question") or "").strip(),
                    "marks": int(raw.get("marks") or 0),
                    "memo": [str(item).strip() for item in raw.get("memo") or [] if str(item).strip()],
                }
            )
        sections.append(
            {
                "title": f"QUESTION {index}: {source['label']} — {source['title']}",
                "mode": "source_response",
                "instructions": f"Study {source['label']} and answer all questions that follow.",
                "stimulus": source["content"],
                "source_provenance": {
                    "label": source["label"],
                    "title": source["title"],
                    "state": "customer_supplied_exact_text",
                    "provenance_not_invented": True,
                },
                "questions": questions,
            }
        )

    essay = dict(plan["essay"])
    essay_question = (
        "Answer ONE of the following essay questions:\n\n"
        f"OPTION A: {essay['option_a']}\n\nOR\n\n"
        f"OPTION B: {essay['option_b']}"
    )
    essay_memo = [
        "OPTION A — acceptable argument/content:",
        *[str(item) for item in essay.get("memo_option_a") or []],
        "OPTION B — acceptable argument/content:",
        *[str(item) for item in essay.get("memo_option_b") or []],
        "Marking guidance:",
        *[str(item) for item in essay.get("marking_guidance") or []],
    ]
    sections.append(
        {
            "title": "QUESTION 4: ESSAY",
            "mode": "extended_response",
            "instructions": "Answer ONE essay. Develop a sustained historical argument supported by relevant evidence.",
            "stimulus": "Choose ONE of the two alternatives below.",
            "questions": [
                {
                    "number": "4",
                    "question": essay_question,
                    "marks": 60,
                    "memo": essay_memo,
                }
            ],
        }
    )

    pack = {
        "assessment_title": f"Grade {request.get('grade')} History Examination — {'First' if opportunity == 1 else 'Second'} Opportunity",
        "subject": "History",
        "grade": int(request.get("grade") or 11),
        "phase": "FET",
        "canonical_profile_id": "fet.history",
        "blueprint": "source_based_plus_essay",
        "render_shell": "source_essay_paper",
        "language_of_assessment": "English",
        "duration": f"{request.get('duration_hours')} hours",
        "total_marks": int(request.get("total_marks") or 150),
        "instructions": (
            "Answer Questions 1, 2 and 3. In Question 4 answer ONE essay only. "
            "Use source evidence where the question requires it and support extended responses with accurate historical knowledge."
        ),
        "source_lock": {
            "source_count": len(sources[:3]),
            "all_customer_text_immutable": True,
            "invented_provenance_allowed": False,
            "described_missing_visual_allowed": False,
        },
        "visual_blueprint": {
            "schema": "knowedge.homs_visual_blueprint.v1",
            "subject": "History",
            "grade": int(request.get("grade") or 11),
            "assessment_family": "source_based_plus_essay",
            "render_shell": "source_essay_paper",
            "required_visuals": [],
            "generation_constraints": [
                "The three customer-supplied text sources are the learner-facing source evidence for this job.",
                "No visual may be described or referenced unless a real bound asset is embedded.",
            ],
        },
        "sections": sections,
        "rubric": [
            {"criterion": "Question 1 source-based responses", "marks": 30, "descriptor": "Allocate marks according to the question-specific memorandum."},
            {"criterion": "Question 2 source-based responses", "marks": 30, "descriptor": "Allocate marks according to the question-specific memorandum."},
            {"criterion": "Question 3 source-based responses", "marks": 30, "descriptor": "Allocate marks according to the question-specific memorandum."},
            {"criterion": "Question 4 historical essay", "marks": 60, "descriptor": "Assess argument, relevant historical evidence, analysis, synthesis and structure using the detailed memorandum outline."},
        ],
        "teacher_review_checklist": [
            "Verify that every displayed source matches the customer-supplied source booklet exactly.",
            "Verify that no source provenance, date, author or quotation has been invented.",
            "Verify all question and memorandum content for Grade-level historical accuracy and fairness.",
            "Approve the final paper and memorandum before learner release.",
        ],
        "generation_backend": "hymark_history_source_first",
        "opportunity": opportunity,
    }
    return pack


def _attach_real_assets(pack: dict[str, Any], request: dict[str, Any]) -> None:
    federation = dict(request.get("dio_homs_source_federation") or {})
    selected = [dict(row) for row in federation.get("selected_assets") or [] if isinstance(row, dict)]
    if not selected:
        return
    # Assets have already been topic-bound by DIO before this native runner. Do
    # not select again here. Preserve the exact provenance-bound paths.
    pack["source_assets"] = [
        {key: value for key, value in row.items() if key not in {"preferred_png_absolute", "preferred_png_sha256"}}
        for row in selected
    ]
    pack.setdefault("source_embedding", {})
    pack["source_embedding"].update(
        {
            "schema": "knowedge.homs_source_embedding.v1",
            "asset_count": len(selected),
            "generated_visual_policy": "suppress_generated_visuals_when_source_assets_present",
            "policy": "Topic-bound real source assets only. Human crop/readability/licensing review remains required.",
        }
    )
    pack["visual_blueprint"]["required_visuals"] = [
        {
            "id": f"bound_source_{index:02d}",
            "title": str(row.get("title") or row.get("source_type") or "Bound source asset"),
            "role": "supplemental_source_evidence",
            "visual_kind": "photograph" if row.get("source_type") == "photograph_or_image" else str(row.get("source_type") or "image"),
            "assessment_use": "Real source exemplar available for human-reviewed integration; not a prose substitute.",
        }
        for index, row in enumerate(selected, 1)
    ]


def _render_opportunity(
    *,
    job_dir: Path,
    request: dict[str, Any],
    sources: list[dict[str, str]],
    plan: dict[str, Any],
    opportunity: int,
) -> dict[str, Any]:
    suffix = "1stOpp" if opportunity == 1 else "2ndOpp"
    opportunity_dir = job_dir / suffix
    opportunity_dir.mkdir(parents=True, exist_ok=True)
    pack = _pack_from_plan(request, sources, plan, opportunity)
    _attach_real_assets(pack, request)
    errors = validate_assessment_pack(pack, {
        "total_marks": pack["total_marks"],
        "duration_hours": request.get("duration_hours"),
        "subject_profile": {"subject_id": "history", "display_name": "History"},
        "grade_profile": {"grade": pack["grade"], "phase": "FET"},
        "visual_blueprint": pack["visual_blueprint"],
    })
    if errors:
        raise RuntimeError("source-first assessment pack failed validation: " + "; ".join(errors))
    pack_path = opportunity_dir / "assessment_pack.json"
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_validation_report(opportunity_dir / "HYMARK_ASSESSMENT_VALIDATION.md", [], pack)

    design_receipt = apply_design_law(opportunity_dir, DEFAULT_DESIGN_LAW, DEFAULT_ASSESSMENT_DESIGN)
    design_law = load_design_json(DEFAULT_DESIGN_LAW)
    design_payload = load_design_json(DEFAULT_ASSESSMENT_DESIGN)
    assessment_design = assessment_design_for_pack(pack, design_payload)
    learner = render_docx(
        opportunity_dir,
        pack,
        design_law,
        design_receipt.get("assets") or [],
        assessment_design,
        include_memo_sections=False,
        output_name=f"ASSESSMENT_LEARNER_{suffix}.docx",
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exam = job_dir / f"{request['module_code']}_Exam_{suffix}_{timestamp}.docx"
    memo = job_dir / f"{request['module_code']}_Memo_{suffix}_{timestamp}.docx"
    shutil.copy2(learner, exam)
    create_shell_memo_docx(pack, memo)
    return {
        "opportunity": opportunity,
        "assessment_pack": str(pack_path),
        "exam": str(exam),
        "memo": str(memo),
        "question_marks": sum_question_marks(pack),
        "rubric_marks": sum_rubric_marks(pack),
        "source_assets": len(pack.get("source_assets") or []),
        "generation_backend": pack["generation_backend"],
    }


def _zip_job(job_dir: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(job_dir.rglob("*")):
            if path.is_file() and path != target:
                archive.write(path, arcname=str(path.relative_to(job_dir)))


def run_builder(
    request_path: Path,
    out_root: Path,
    secret_file: Path,
    backend_path: Path,
    provider_name: str,
    model: str,
    opportunities: str = "both",
) -> dict[str, Any]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    source_booklet = Path(str(request.get("dio_customer_source_booklet") or "")).expanduser().resolve()
    if not source_booklet.is_file():
        raise RuntimeError("source-first History builder requires the DIO customer source booklet")
    expected_source_hash = str(request.get("dio_customer_source_booklet_sha256") or "")
    if expected_source_hash and sha256(source_booklet) != expected_source_hash:
        raise RuntimeError("customer source booklet hash drifted before History generation")
    sources = _parse_customer_sources(source_booklet)
    request["grade"] = int(re.search(r"Grade\s+(\d+)", str(request.get("module_name") or "Grade 11"), re.I).group(1))
    request["customer_request"] = str(request.get("additional_instructions") or "").split("CUSTOMER EXCEPTION", 1)[0][-3000:]

    provider = configure_provider(secret_file, provider_name, model)
    hymark = load_hymark_backend(backend_path)

    out_root.mkdir(parents=True, exist_ok=True)
    job_id = (
        f"hymark-history-source-first-{str(request.get('module_code') or 'history').lower()}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    job_dir = out_root / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(request_path, job_dir / "exam_builder_request.json")
    shutil.copy2(source_booklet, job_dir / "CUSTOMER_SOURCE_BOOKLET.md")
    (job_dir / "HOMS_LOCKED_CUSTOMER_SOURCES.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if request.get("dio_homs_source_federation"):
        (job_dir / "HOMS_SOURCE_FEDERATION.json").write_text(
            json.dumps(request["dio_homs_source_federation"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    wanted = [1, 2] if opportunities == "both" else ([1] if opportunities == "first" else [2])
    results: dict[int, dict[str, Any]] = {}
    plans: dict[int, dict[str, Any]] = {}
    for opportunity in wanted:
        opportunity_dir = job_dir / ("1stOpp" if opportunity == 1 else "2ndOpp")
        opportunity_dir.mkdir(parents=True, exist_ok=True)
        plan = _generate_plan(hymark, request, sources, opportunity, opportunity_dir)
        plans[opportunity] = plan
        results[opportunity] = _render_opportunity(
            job_dir=job_dir,
            request=request,
            sources=sources,
            plan=plan,
            opportunity=opportunity,
        )

    if 1 in plans and 2 in plans:
        if json.dumps(plans[1], sort_keys=True) == json.dumps(plans[2], sort_keys=True):
            raise RuntimeError("first and second opportunity plans are identical")

    review_zip = job_dir / f"{request['module_code']}_HOMS_SOURCE_FIRST_REVIEW.zip"
    _zip_job(job_dir, review_zip)
    outputs = {
        "job_dir": str(job_dir),
        "review_zip": str(review_zip),
    }
    if 1 in results:
        outputs["first_exam"] = results[1]["exam"]
        outputs["first_memo"] = results[1]["memo"]
    if 2 in results:
        outputs["second_exam"] = results[2]["exam"]
        outputs["second_memo"] = results[2]["memo"]

    receipt = {
        "schema": SCHEMA,
        "status": "completed",
        "job_id": job_id,
        "created_at": utc_now(),
        "assessor": {
            "name": "HyMark Exam Builder",
            "generation_backend": "hymark_history_source_first",
            "native_engine": ENGINE_IDENTITY,
        },
        "provider": provider,
        "source_contract": {
            "customer_source_booklet": str(source_booklet),
            "customer_source_sha256": sha256(source_booklet),
            "locked_text_source_count": len(sources),
            "invented_provenance_allowed": False,
            "described_missing_visual_allowed": False,
            "source_bank_federation": request.get("dio_homs_source_federation") or {},
        },
        "opportunities": results,
        "outputs": outputs,
        "human_review_required": True,
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    (job_dir / "HYMARK_EXAM_BUILDER_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run restored source-first HyMark History examination builder.")
    parser.add_argument("--request", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--secret-file", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--provider", default="nim")
    parser.add_argument("--model", default="")
    parser.add_argument("--opportunities", choices=["first", "second", "both"], default="both")
    args = parser.parse_args()
    receipt = run_builder(
        Path(args.request).expanduser().resolve(),
        Path(args.out).expanduser().resolve(),
        Path(args.secret_file).expanduser().resolve(),
        Path(args.backend).expanduser().resolve(),
        args.provider,
        args.model,
        args.opportunities,
    )
    print(json.dumps({
        "status": receipt["status"],
        "job_id": receipt["job_id"],
        "native_engine": ENGINE_IDENTITY,
        "outputs": receipt["outputs"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
