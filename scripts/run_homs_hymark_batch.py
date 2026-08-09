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
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
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
            quotes = item.get("quotes") or []
        else:
            score = clamp(item, max_score)
            level = ""
            feedback = ""
            quotes = []
        total += score
        normalized[name] = {
            "level": level,
            "score": score,
            "max_score": max_score,
            "feedback": feedback,
            "quotes": quotes,
        }

    raw["criteria_scores"] = normalized
    raw["total_score"] = round(total, 2)
    raw["max_score"] = rubric.get("total_marks", total)
    raw["percentage"] = round((raw["total_score"] / raw["max_score"]) * 100, 2) if raw["max_score"] else 0.0
    raw.setdefault("annotations", [])
    raw.setdefault("strengths", [])
    raw.setdefault("areas_for_improvement", [])
    return raw


def zip_dir(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file() and path.resolve() != target.resolve():
                zf.write(path, path.relative_to(source))


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


def run_batch(input_dir: Path, out_root: Path, secret_file: Path, backend_path: Path, provider_name: str, model: str) -> dict[str, Any]:
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

    uploads = job_dir / "uploads"
    if not uploads.exists():
        raise FileNotFoundError(f"Input folder must contain uploads/: {input_dir}")
    rubric_path = job_dir / "rubric.json"
    if not rubric_path.exists():
        raise FileNotFoundError(f"Input folder must contain rubric.json: {input_dir}")
    rubric = ensure_rubric_levels(json.loads(rubric_path.read_text(encoding="utf-8")))
    (job_dir / "rubric.hymark.normalized.json").write_text(json.dumps(rubric, indent=2), encoding="utf-8")
    instructions = (job_dir / "memo.md").read_text(encoding="utf-8", errors="ignore") if (job_dir / "memo.md").exists() else ""

    feedback_dir = job_dir / "feedback"
    feedback_dir.mkdir(exist_ok=True)
    results: list[dict[str, Any]] = []
    provider_errors: list[str] = []

    for submission in sorted(p for p in uploads.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".md", ".docx", ".pdf"}):
        if submission.suffix.lower() in {".txt", ".md"}:
            text = submission.read_text(encoding="utf-8", errors="ignore")
        else:
            text = hymark.extract_document_content(submission)
        try:
            raw = asyncio.run(hymark.assess_with_ai(text, rubric, instructions))
        except Exception as exc:
            provider_errors.append(f"{submission.name}: {type(exc).__name__}: provider failure redacted")
            raw = {"total_score": 0, "criteria_scores": {}, "overall_feedback": "Assessment failed.", "annotations": []}

        result = normalize_assessment(raw, rubric)
        result["student_id"] = submission.stem
        result["submission_file"] = submission.name
        result["provider"] = provider["selected_provider"]
        result["model"] = provider["selected_model"]
        result["requires_review"] = True
        results.append(result)

        feedback_path = feedback_dir / f"{submission.stem}_FEEDBACK.txt"
        hymark.create_feedback_txt(feedback_path, result)

    with (job_dir / "marks.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "score", "max_score", "percentage", "provider", "requires_review"])
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "student_id": result["student_id"],
                    "score": result["total_score"],
                    "max_score": result["max_score"],
                    "percentage": result["percentage"],
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
        summary_lines.append(f"- {result['student_id']}: {result['total_score']}/{result['max_score']} ({result['percentage']}%)")
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
        "assessor": {
            "name": "HyMark Smart Assessor",
            "backend_path": str(backend_path),
            "prompt_source": "backend.server.assess_with_ai",
        },
        "provider": provider,
        "submissions": len(results),
        "provider_errors": provider_errors,
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
    parser.add_argument("--provider", default="nim", choices=["nim", "nvidia", "nvidia_nim", "openai"])
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
