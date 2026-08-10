#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from homs_assessment_convergence import (  # noqa: E402
    DEFAULT_LOCAL_HOMS_ROOT,
    assessment_contract,
    cohort_summary,
    extract_group_members,
    repair_instructions,
    run_local_homs_governance,
    similarity_review_candidates,
    valid_student_ids_from_csv,
)

DEFAULT_SECRET_FILE = Path("/home/byron/EdgeK-BEAST/.beast/provider_secrets.env")
DEFAULT_HYMARK_BACKEND = Path("/home/byron/Downloads/NoEdge-Multi-Hymark-main/backend/server.py")


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
    for key, value in values.items():
        os.environ.setdefault(key, value)
    if provider_name in {"nim", "nvidia", "nvidia_nim"}:
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
        if criterion.get("levels"):
            continue
        criterion["levels"] = {
            "Excellent": {"description": "Strong, specific, well-supported performance.", "min_score": round(weight * 0.8, 2), "max_score": weight},
            "Good": {"description": "Clear and mostly well-supported performance.", "min_score": round(weight * 0.6, 2), "max_score": round(weight * 0.79, 2)},
            "Satisfactory": {"description": "Basic but incomplete performance.", "min_score": round(weight * 0.4, 2), "max_score": round(weight * 0.59, 2)},
            "Needs Improvement": {"description": "Limited, unsupported, or unclear performance.", "min_score": 0, "max_score": round(weight * 0.39, 2)},
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
    raw = dict(raw or {})
    criteria_raw = raw.get("criteria_scores") or {}
    normalized: dict[str, Any] = {}
    total = 0.0
    for criterion in rubric.get("criteria", []):
        name = str(criterion.get("name", "Unnamed criterion"))
        max_score = float(criterion.get("weight", 0) or 0)
        item = criteria_raw.get(name)
        if item is None:
            item = next((value for key, value in criteria_raw.items() if str(key).strip().lower() == name.strip().lower() or str(key).strip().lower() in name.strip().lower() or name.strip().lower() in str(key).strip().lower()), {})
        if isinstance(item, dict):
            score = clamp(item.get("score", item.get("marks", item.get("mark", 0))), max_score)
            level = str(item.get("level") or "").strip()
            feedback = str(item.get("feedback") or item.get("comment") or item.get("comments") or "").strip()
            quotes = item.get("quotes") or []
            if isinstance(quotes, str):
                quotes = [quotes]
        else:
            score, level, feedback, quotes = clamp(item, max_score), "", "", []
        total += score
        normalized[name] = {"level": level, "score": score, "max_score": max_score, "feedback": feedback, "quotes": quotes}
    raw["criteria_scores"] = normalized
    raw["total_score"] = round(total, 2)
    raw["max_score"] = float(rubric.get("total_marks", total) or total)
    raw["percentage"] = round((raw["total_score"] / raw["max_score"]) * 100, 2) if raw["max_score"] else 0.0
    raw.setdefault("annotations", [])
    raw.setdefault("strengths", [])
    raw.setdefault("areas_for_improvement", [])
    return raw


def long_form_window(text: str, limit: int = 14500) -> tuple[str, dict[str, Any]]:
    if len(text) <= limit:
        return text, {"mode": "full_text", "original_chars": len(text), "assessor_chars": len(text), "estimated_char_coverage": 1.0}
    head = int(limit * 0.35)
    middle = int(limit * 0.30)
    tail = limit - head - middle
    midpoint = len(text) // 2
    middle_start = max(head, midpoint - middle // 2)
    sample = text[:head] + "\n\n[... MIDDLE OF SUBMISSION ...]\n\n" + text[middle_start : middle_start + middle] + "\n\n[... CONCLUSION / END OF SUBMISSION ...]\n\n" + text[-tail:]
    return sample[:limit], {
        "mode": "opening_middle_conclusion_window",
        "original_chars": len(text),
        "assessor_chars": min(len(sample), limit),
        "estimated_char_coverage": round(limit / len(text), 4),
        "boundary": "Smart Assessor upstream prompt currently caps assessment text; C8 samples opening, middle and conclusion instead of silently dropping the end.",
    }


def zip_dir(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file() and path.resolve() != target.resolve():
                zf.write(path, path.relative_to(source))


def write_marked_gradebook(job_dir: Path, results: list[dict[str, Any]], group_map: dict[str, list[str]]) -> Path:
    source = job_dir / "gradebook.csv"
    target = job_dir / "gradebook_marked.csv"
    rows: list[dict[str, str]] = []
    fields = ["student_id", "grade", "percentage", "provider", "requires_review", "grade_source", "primary_submission_id"]
    if source.is_file():
        with source.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fields = list(reader.fieldnames or [])
        for field in ["grade", "percentage", "provider", "requires_review", "grade_source", "primary_submission_id"]:
            if field not in fields:
                fields.append(field)
    by_id: dict[str, dict[str, Any]] = {}
    for result in results:
        sid = str(result.get("student_id") or "")
        by_id[sid] = result
        by_id[sid.split("_", 1)[0]] = result
        for member in group_map.get(sid, []):
            by_id[member] = {**result, "_group_primary": sid}
    if not rows:
        ids = sorted({key for key in by_id if key and "_" not in key})
        rows = [{"student_id": sid} for sid in ids]
    for row in rows:
        sid = str(row.get("student_id") or row.get("ID") or row.get("Display ID") or "").strip()
        result = by_id.get(sid)
        if not result:
            continue
        row["grade"] = str(result.get("total_score", ""))
        row["percentage"] = str(result.get("percentage", ""))
        row["provider"] = str(result.get("provider", ""))
        row["requires_review"] = "yes"
        primary = result.get("_group_primary")
        row["grade_source"] = "validated_group_member" if primary else "primary_submission"
        row["primary_submission_id"] = str(primary or result.get("student_id") or "")
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return target


def criterion_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [f"# Criterion Feedback: {result['student_id']}", "", f"Draft score: {result['total_score']}/{result['max_score']} ({result['percentage']}%)", "", "Human educator review is required.", ""]
    for name, item in (result.get("criteria_scores") or {}).items():
        lines.extend([f"## {name}", f"Score: {item.get('score')}/{item.get('max_score')} · {item.get('level') or 'level not supplied'}", "", str(item.get("feedback") or ""), "", "Quoted evidence:"])
        for quote in item.get("quotes") or []:
            lines.append(f"> {str(quote).strip()}")
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def run_batch(input_dir: Path, out_root: Path, secret_file: Path, backend_path: Path, provider_name: str, model: str, local_homs_root: Path = DEFAULT_LOCAL_HOMS_ROOT, quality_retries: int = 1) -> dict[str, Any]:
    started = time.perf_counter()
    provider = configure_provider(secret_file, provider_name, model)
    hymark = load_hymark_backend(backend_path)
    out_root.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", input_dir.name).strip("-").lower()
    job_id = "homs-hymark-c8-" + stem + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_dir = out_root / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    shutil.copytree(input_dir, job_dir)
    uploads = job_dir / "uploads"
    rubric_path = job_dir / "rubric.json"
    if not uploads.is_dir() or not rubric_path.is_file():
        raise FileNotFoundError("Input folder must contain uploads/ and rubric.json")
    rubric = ensure_rubric_levels(json.loads(rubric_path.read_text(encoding="utf-8")))
    (job_dir / "rubric.hymark.normalized.json").write_text(json.dumps(rubric, indent=2), encoding="utf-8")
    base_instructions = (job_dir / "memo.md").read_text(encoding="utf-8", errors="ignore") if (job_dir / "memo.md").is_file() else ""

    feedback_dir, annotated_dir, rubric_dir, quality_dir = (job_dir / "feedback", job_dir / "annotated", job_dir / "rubric_feedback", job_dir / "quality")
    for folder in (feedback_dir, annotated_dir, rubric_dir, quality_dir):
        folder.mkdir(exist_ok=True)

    gradebook_source = job_dir / "gradebook.csv"
    valid_ids = valid_student_ids_from_csv(gradebook_source)
    if not valid_ids and (job_dir / "grades.csv").is_file():
        valid_ids = valid_student_ids_from_csv(job_dir / "grades.csv")

    results: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    provider_errors: list[str] = []
    group_map: dict[str, list[str]] = {}
    similarity_inputs: list[dict[str, Any]] = []

    submissions = sorted(p for p in uploads.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".md", ".docx", ".pdf"})
    for submission in submissions:
        full_text = submission.read_text(encoding="utf-8", errors="ignore") if submission.suffix.lower() in {".txt", ".md"} else hymark.extract_document_content(submission)
        assessor_text, coverage = long_form_window(full_text)
        raw: dict[str, Any] = {}
        contract: dict[str, Any] = {"passed": False, "errors": ["assessment not attempted"]}
        for attempt in range(max(0, quality_retries) + 1):
            instructions = base_instructions
            if attempt:
                instructions = (instructions + "\n\n" + repair_instructions(contract)).strip()
            try:
                raw = asyncio.run(hymark.assess_with_ai(assessor_text, rubric, instructions))
            except Exception as exc:
                provider_errors.append(f"{submission.name}: {type(exc).__name__}: provider failure redacted")
                raw = {"total_score": 0, "criteria_scores": {}, "overall_feedback": "Assessment failed.", "annotations": []}
            result = normalize_assessment(raw, rubric)
            contract = assessment_contract(result, rubric, full_text)
            if contract["passed"]:
                break
        result["student_id"] = submission.stem
        result["submission_file"] = submission.name
        result["provider"] = provider["selected_provider"]
        result["model"] = provider["selected_model"]
        result["requires_review"] = True
        result["quality_contract_passed"] = bool(contract["passed"])
        result["long_form_coverage"] = coverage
        result["assessed_at"] = utc_now()
        results.append(result)
        contracts.append(contract)
        similarity_inputs.append({"student_id": submission.stem, "text": full_text})
        (quality_dir / f"{submission.stem}_QUALITY.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

        hymark.create_feedback_txt(feedback_dir / f"{submission.stem}_FEEDBACK.txt", result)
        criterion_markdown(feedback_dir / f"{submission.stem}_CRITERION_FEEDBACK.md", result)
        if submission.suffix.lower() == ".docx" and hasattr(hymark, "annotate_docx_with_feedback"):
            hymark.annotate_docx_with_feedback(submission, annotated_dir / f"{submission.stem}_ANNOTATED.docx", result.get("annotations", []), result.get("overall_feedback", ""), result.get("criteria_scores", {}), result.get("total_score", 0), result.get("max_score", 0), result.get("strengths", []))
        elif submission.suffix.lower() == ".pdf" and hasattr(hymark, "annotate_pdf_with_feedback"):
            hymark.annotate_pdf_with_feedback(submission, annotated_dir / f"{submission.stem}_ANNOTATED.pdf", result.get("annotations", []), result.get("overall_feedback", ""), result.get("criteria_scores", {}), result.get("total_score", 0), result.get("max_score", 0))
        if hasattr(hymark, "create_rubric_feedback_document"):
            hymark.create_rubric_feedback_document(rubric_dir / f"{submission.stem}_RUBRIC_FEEDBACK.docx", rubric, result, submission.stem)

        first_page = hymark.get_first_page_text(submission) if hasattr(hymark, "get_first_page_text") else full_text[:3000]
        group_map[submission.stem] = extract_group_members(first_page, valid_ids, submission.stem, backend=hymark)

    with (job_dir / "marks.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["student_id", "score", "max_score", "percentage", "provider", "quality_contract", "requires_review"])
        writer.writeheader()
        for result in results:
            writer.writerow({"student_id": result["student_id"], "score": result["total_score"], "max_score": result["max_score"], "percentage": result["percentage"], "provider": result["provider"], "quality_contract": "pass" if result["quality_contract_passed"] else "blocked", "requires_review": "yes"})

    marked_gradebook = write_marked_gradebook(job_dir, results, group_map)
    local = run_local_homs_governance(results, contracts, local_homs_root)
    similarity = similarity_review_candidates(similarity_inputs)
    (job_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (job_dir / "GROUP_MEMBER_MAP.json").write_text(json.dumps(group_map, indent=2), encoding="utf-8")
    (job_dir / "MODERATION_REPORT.json").write_text(json.dumps({"moderation": local.get("moderation"), "report": local.get("moderation_report")}, indent=2), encoding="utf-8")
    (job_dir / "LEARNING_INSIGHTS.json").write_text(json.dumps(local.get("learning_insights") or {}, indent=2), encoding="utf-8")
    (job_dir / "SIMILARITY_REVIEW.json").write_text(json.dumps(similarity, indent=2), encoding="utf-8")
    (job_dir / "COHORT_SUMMARY.json").write_text(json.dumps(cohort_summary(results), indent=2), encoding="utf-8")

    bundle_manifest = {
        "schema": "knowedge.homs_marking_relief_bundle.v1",
        "required": ["criterion comments", "grounded quotations", "anchored annotations", "rubric feedback document", "compiled gradebook", "group-member map", "cohort moderation", "learning insights", "similarity review"],
        "submissions": len(results),
        "quality_passed": sum(1 for contract in contracts if contract.get("passed")),
        "quality_blocked": sum(1 for contract in contracts if not contract.get("passed")),
        "local_homs_available": bool(local.get("available")),
        "human_educator_approval_required": True,
    }
    (job_dir / "BUNDLE_MANIFEST.json").write_text(json.dumps(bundle_manifest, indent=2), encoding="utf-8")

    all_quality_passed = bool(results) and all(contract.get("passed") for contract in contracts)
    status = "completed_review_ready" if all_quality_passed else "completed_blocked_incomplete_feedback"
    summary_lines = ["# HOMS C8 Lecturer Review Summary", "", f"Job: `{job_id}`", f"Created: {utc_now()}", f"Smart Assessor: `{backend_path}`", f"Provider: {provider['selected_provider']} / {provider['selected_model']}", f"Bundle status: **{status}**", "", "## Batch Results"]
    for result in results:
        summary_lines.append(f"- {result['student_id']}: {result['total_score']}/{result['max_score']} ({result['percentage']}%) · quality {'PASS' if result['quality_contract_passed'] else 'BLOCKED'} · coverage {result['long_form_coverage']['mode']}")
    summary_lines.extend(["", "## Converged Layers", "- Smart Assessor: semantic rubric judgement, criterion feedback, exact quotations and anchored document feedback.", "- Local HOMS: cohort moderation and cross-submission learning via a compatibility projection.", "- C8: quality completeness, quote grounding, group-member validation, similarity review and buyer-facing bundle manifest.", "", "## Boundary", "All marks and feedback remain draft decision support. Educator review and approval remain final. Similarity candidates are not plagiarism findings."])
    (job_dir / "LECTURER_REVIEW_SUMMARY.md").write_text("\n".join(summary_lines).strip() + "\n", encoding="utf-8")

    zip_path = job_dir / "HOMS_C8_REVIEW_PACK.zip"
    receipt = {
        "schema": "knowedge.homs_assessment_convergence_receipt.v1",
        "created_at": utc_now(),
        "job_id": job_id,
        "status": status,
        "input_dir": str(input_dir),
        "assessor": {"name": "HyMark Smart Assessor + Local HOMS governance", "smart_backend_path": str(backend_path), "local_homs_root": str(local_homs_root), "prompt_source": "backend.server.assess_with_ai"},
        "provider": provider,
        "submissions": len(results),
        "provider_errors": provider_errors,
        "bundle_manifest": bundle_manifest,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "outputs": {"job_dir": str(job_dir), "results": str(job_dir / "results.json"), "marks_csv": str(job_dir / "marks.csv"), "marked_gradebook": str(marked_gradebook), "group_map": str(job_dir / "GROUP_MEMBER_MAP.json"), "moderation_report": str(job_dir / "MODERATION_REPORT.json"), "learning_insights": str(job_dir / "LEARNING_INSIGHTS.json"), "similarity_review": str(job_dir / "SIMILARITY_REVIEW.json"), "lecturer_summary": str(job_dir / "LECTURER_REVIEW_SUMMARY.md"), "review_zip": str(zip_path)},
        "human_educator_approval_required": True,
        "release_authority_granted": False,
    }
    (job_dir / "HOMS_C8_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    zip_dir(job_dir, zip_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HOMS Marking Relief through Smart Assessor plus Local HOMS governance.")
    parser.add_argument("--input", required=True, help="HOMS job folder with rubric.json and uploads/.")
    parser.add_argument("--out", default="/home/byron/KnowEdge_Microsoft_Mirror/HOMS/done")
    parser.add_argument("--secret-file", default=str(DEFAULT_SECRET_FILE))
    parser.add_argument("--backend", default=str(DEFAULT_HYMARK_BACKEND))
    parser.add_argument("--local-homs-root", default=str(DEFAULT_LOCAL_HOMS_ROOT))
    parser.add_argument("--provider", default="nim", choices=["nim", "nvidia", "nvidia_nim", "openai"])
    parser.add_argument("--model", default="")
    parser.add_argument("--quality-retries", type=int, default=1, choices=[0, 1, 2])
    args = parser.parse_args()
    receipt = run_batch(Path(args.input).expanduser().resolve(), Path(args.out).expanduser().resolve(), Path(args.secret_file).expanduser().resolve(), Path(args.backend).expanduser().resolve(), args.provider, args.model, Path(args.local_homs_root).expanduser().resolve(), args.quality_retries)
    print(json.dumps({"status": receipt["status"], "assessor": receipt["assessor"]["name"], "provider": receipt["provider"]["selected_provider"], "outputs": receipt["outputs"]}, indent=2))
    return 0 if receipt["status"] == "completed_review_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
