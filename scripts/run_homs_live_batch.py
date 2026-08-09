#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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


RUBRIC = {
    "name": "HOMS Safe Demo Rubric",
    "total_marks": 30,
    "criteria": [
        {
            "name": "Argument and focus",
            "weight": 10,
            "description": "Clear answer to the question, coherent line of argument, and relevant focus.",
        },
        {
            "name": "Evidence and source use",
            "weight": 10,
            "description": "Uses concrete evidence, examples, or references to support claims.",
        },
        {
            "name": "Structure and academic communication",
            "weight": 10,
            "description": "Logical organization, readable academic style, and useful conclusion.",
        },
    ],
}


SUBMISSIONS = {
    "student_alpha.txt": """Student Alpha

Community gardens can support food security because they create a local supply of vegetables and also build practical knowledge. A strong programme would connect garden work with lessons on soil, water use, and household nutrition. The evidence is clearest when attendance records, crop logs, and household feedback are compared across time.

The weakness is that gardens do not solve poverty alone. They need stable coordination, tools, and seasonal planning. In conclusion, community gardens are useful when treated as part of a broader support system rather than a single cure.""",
    "student_beta.txt": """Student Beta

Community gardens are good because food is important. People can plant things and then they have vegetables. This helps the community. There are many examples where gardens are nice and learners can also learn from them.

I think every school should have one because it is positive. The conclusion is that gardens are good and everyone should support them.""",
    "student_gamma.txt": """Student Gamma

Community gardens may improve food security, but the effect depends on participation, land access, water reliability, and whether produce reaches households that need it most. A useful assessment would compare input costs, harvest yield, attendance, and household survey data over several months.

The approach also has educational value. Learners can connect biology, economics, and citizenship by tracking plant growth and reflecting on local inequality. However, the project can fail if it relies only on volunteer enthusiasm. A sustainable plan needs roles, records, and links to existing feeding schemes.""",
}


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
        key = key.replace("export ", "").strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def load_provider_env(path: Path, requested_provider: str) -> dict[str, Any]:
    values = parse_env_file(path)
    for key, value in values.items():
        os.environ.setdefault(key, value)
    provider = "none"
    model = os.environ.get("HOMS_MODEL") or ""
    selected_key_name = ""
    base_url = ""

    if requested_provider in {"auto", "nim", "nvidia", "nvidia_nim"}:
        nvidia_key = values.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_API_KEY") or ""
        if nvidia_key:
            os.environ["HOMS_PROVIDER_API_KEY"] = nvidia_key
            selected_key_name = "NVIDIA_API_KEY"
            provider = "nvidia_nim"
            base_url = os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
            model = model or os.environ.get("HOMS_NIM_MODEL") or os.environ.get("BEAST_NIM_MODEL") or "nvidia/nemotron-3-super-120b-a12b"

    if provider == "none" and requested_provider in {"auto", "openai"}:
        for key_name in ("OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"):
            key_value = values.get(key_name) or os.environ.get(key_name) or ""
            if key_value.startswith("sk-"):
                os.environ["HOMS_PROVIDER_API_KEY"] = key_value
                selected_key_name = key_name
                break
        if selected_key_name:
            provider = "openai"
            model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"

    if provider == "none":
        model = model or "deterministic-fallback"

    if provider == "openai":
        os.environ["OPENAI_API_KEY"] = os.environ["HOMS_PROVIDER_API_KEY"]
    elif provider == "nvidia_nim":
        os.environ["NVIDIA_API_KEY"] = os.environ["HOMS_PROVIDER_API_KEY"]

    if os.environ.get("HOMS_PROVIDER_API_KEY") and selected_key_name:
        provider = "openai"
        if selected_key_name == "NVIDIA_API_KEY":
            provider = "nvidia_nim"
    return {
        "secret_file": str(path),
        "available_keys": sorted(k for k, v in values.items() if v and ("KEY" in k or "TOKEN" in k or "SECRET" in k)),
        "selected_provider": provider,
        "selected_model": model,
        "selected_key_name": selected_key_name,
        "base_url": base_url,
    }


def sanitize_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"((?:sk|csk|gsk|nvapi|or|xai)-)[A-Za-z0-9_*\\-]{8,}", r"\1<redacted>", text)
    text = re.sub(r"(Incorrect API key provided: )[^.\\s]+", r"\1<redacted>", text)
    return text


def clamp_score(value: Any, max_score: float) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    if score < 0:
        return 0.0
    if score > max_score:
        return float(max_score)
    return round(score, 2)


def deterministic_assess(text: str, rubric: dict[str, Any]) -> dict[str, Any]:
    words = re.findall(r"[A-Za-z]{3,}", text.lower())
    unique = len(set(words))
    length = len(words)
    evidence_terms = sum(1 for term in ["evidence", "records", "data", "compare", "survey", "logs", "examples"] if term in text.lower())
    structure_terms = sum(1 for term in ["because", "however", "conclusion", "therefore", "depends"] if term in text.lower())
    arg = clamp_score(min(10, 3 + length / 35 + structure_terms * 1.1), 10)
    ev = clamp_score(min(10, 2 + evidence_terms * 1.4 + unique / 45), 10)
    st = clamp_score(min(10, 3 + structure_terms * 1.2 + (1 if "\n\n" in text else 0)), 10)
    total = round(arg + ev + st, 2)
    return {
        "total_score": total,
        "criteria_scores": {
            "Argument and focus": {"score": arg, "feedback": "Heuristic pass: checks focus, length, and argumentative connectors."},
            "Evidence and source use": {"score": ev, "feedback": "Heuristic pass: checks evidence/data/reference language."},
            "Structure and academic communication": {"score": st, "feedback": "Heuristic pass: checks paragraphing and structural markers."},
        },
        "overall_feedback": "Draft feedback generated by deterministic fallback. Use provider mode for richer comments.",
        "strengths": ["Submission contains assessable academic prose."],
        "areas_for_improvement": ["Educator should review final score and feedback before release."],
        "provider": "deterministic_fallback",
    }


def load_rubric(batch_dir: Path) -> dict[str, Any]:
    rubric_path = batch_dir / "rubric.json"
    if rubric_path.exists():
        rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        if rubric.get("criteria") and rubric.get("total_marks"):
            return rubric
    return RUBRIC


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def provider_assess(text: str, provider: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    from openai import OpenAI

    kwargs: dict[str, str] = {"api_key": os.environ["HOMS_PROVIDER_API_KEY"]}
    if provider.get("base_url"):
        kwargs["base_url"] = provider["base_url"]
    client = OpenAI(**kwargs)
    rubric_text = json.dumps(rubric, indent=2)
    prompt = f"""Assess this safe dummy student submission against the rubric.

Return only JSON with:
total_score, criteria_scores, overall_feedback, strengths, areas_for_improvement.

Rules:
- Scores must sum to max 30.
- Keep feedback draft-only.
- Mention that educator review is required before final marks.

Rubric:
{rubric_text}

Submission:
{text}
"""
    response = client.chat.completions.create(
        model=provider["selected_model"],
        messages=[
            {"role": "system", "content": "You are a careful academic marking assistant. Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1200,
    )
    content = response.choices[0].message.content or "{}"
    parsed = extract_json_object(content)
    criteria_scores_raw = parsed.get("criteria_scores") or {}
    if isinstance(criteria_scores_raw, list):
        criteria_scores: dict[str, Any] = {}
        for item in criteria_scores_raw:
            if not isinstance(item, dict):
                continue
            criterion_name = (
                item.get("name")
                or item.get("criterion")
                or item.get("criterion_name")
                or item.get("criteria")
                or ""
            )
            if criterion_name:
                criteria_scores[str(criterion_name)] = item
    elif isinstance(criteria_scores_raw, dict):
        criteria_scores = criteria_scores_raw
    else:
        criteria_scores = {}
    total = 0.0
    normalized: dict[str, Any] = {}
    weights = {c["name"]: float(c["weight"]) for c in rubric["criteria"]}
    for name, max_score in weights.items():
        raw = criteria_scores.get(name, {})
        if not raw:
            raw = next(
                (
                    value
                    for key, value in criteria_scores.items()
                    if str(key).strip().lower() == name.strip().lower()
                ),
                {},
            )
        if isinstance(raw, dict):
            score = clamp_score(raw.get("score", 0), max_score)
            feedback = str(raw.get("feedback") or raw.get("comment") or raw.get("comments") or "").strip()
        else:
            score = clamp_score(raw, max_score)
            feedback = ""
        total += score
        normalized[name] = {"score": score, "max_score": max_score, "feedback": feedback}
    parsed["criteria_scores"] = normalized
    parsed["total_score"] = round(total, 2)
    parsed["provider"] = provider["selected_provider"]
    parsed["model"] = provider["selected_model"]
    return parsed


def write_demo_inputs(batch_dir: Path) -> Path:
    uploads = batch_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (batch_dir / "rubric.json").write_text(json.dumps(RUBRIC, indent=2), encoding="utf-8")
    (batch_dir / "intake.json").write_text(
        json.dumps(
            {
                "schema": "knowedge.homs_batch_intake.v1",
                "created_at": utc_now(),
                "client": "Controlled HOMS dummy pilot",
                "boundary": "Fake/non-sensitive submissions only. Educator approval required.",
                "requested_outputs": ["draft feedback", "marks csv", "lecturer review summary", "return zip"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for name, text in SUBMISSIONS.items():
        (uploads / name).write_text(text.strip() + "\n", encoding="utf-8")
    return uploads


def copy_input_batch(input_dir: Path, job_dir: Path) -> Path:
    if not input_dir.exists():
        raise FileNotFoundError(f"HOMS input folder not found: {input_dir}")
    shutil.copytree(input_dir, job_dir, dirs_exist_ok=True)
    uploads = job_dir / "uploads"
    if not uploads.exists():
        raise FileNotFoundError(f"HOMS input folder must contain uploads/: {input_dir}")
    submissions = sorted(uploads.glob("*.txt"))
    if not submissions:
        raise FileNotFoundError(f"HOMS input uploads/ must contain at least one .txt submission: {uploads}")
    return uploads


def zip_dir(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file():
                if path.resolve() == target.resolve():
                    continue
                zf.write(path, path.relative_to(source))


def write_marked_gradebook(job_dir: Path, results: list[dict[str, Any]]) -> Path | None:
    gradebook = job_dir / "gradebook.csv"
    if not gradebook.exists():
        return None
    result_by_short_id: dict[str, dict[str, Any]] = {}
    for result in results:
        full_id = str(result.get("student_id", ""))
        short_id = full_id.split("_", 1)[0]
        result_by_short_id[short_id] = result
        result_by_short_id[full_id] = result

    with gradebook.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for field in ["grade", "percentage", "provider", "requires_review"]:
        if field not in fieldnames:
            fieldnames.append(field)

    for row in rows:
        result = result_by_short_id.get(str(row.get("student_id", "")).strip())
        if not result:
            continue
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
    secret_file: Path,
    out_root: Path,
    force_fallback: bool,
    requested_provider: str,
    input_dir: Path | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    out_root.mkdir(parents=True, exist_ok=True)
    stem = "live-dummy" if input_dir is None else re.sub(r"[^A-Za-z0-9_-]+", "-", input_dir.name).strip("-").lower()
    job_id = "homs-" + stem + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_dir = out_root / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)

    uploads = copy_input_batch(input_dir, job_dir) if input_dir else write_demo_inputs(job_dir)
    rubric = load_rubric(job_dir)
    provider = load_provider_env(secret_file, requested_provider)
    feedback_dir = job_dir / "feedback"
    feedback_dir.mkdir()

    results: list[dict[str, Any]] = []
    provider_errors: list[str] = []
    for submission in sorted(uploads.glob("*.txt")):
        text = submission.read_text(encoding="utf-8")
        result: dict[str, Any]
        if provider["selected_provider"] in {"openai", "nvidia_nim"} and not force_fallback:
            try:
                result = provider_assess(text, provider, rubric)
            except Exception as exc:
                provider_errors.append(f"{submission.name}: {sanitize_error(exc)}")
                result = deterministic_assess(text, rubric)
        else:
            result = deterministic_assess(text, rubric)

        result["student_id"] = submission.stem
        result["submission_file"] = submission.name
        result["max_score"] = rubric["total_marks"]
        result["percentage"] = round((float(result.get("total_score", 0)) / rubric["total_marks"]) * 100, 2)
        results.append(result)

        feedback = [
            f"# Draft Feedback: {submission.stem}",
            "",
            f"Score: {result['total_score']}/{rubric['total_marks']} ({result['percentage']}%)",
            "",
            str(result.get("overall_feedback", "")).strip(),
            "",
            "## Criteria",
        ]
        for name, detail in (result.get("criteria_scores") or {}).items():
            feedback.append(f"- {name}: {detail.get('score', 0)}/{detail.get('max_score', '')} - {detail.get('feedback', '')}")
        feedback.extend(["", "## Boundary", "Draft marking support only. Educator review and approval remain required."])
        (feedback_dir / f"{submission.stem}_feedback.md").write_text("\n".join(feedback).strip() + "\n", encoding="utf-8")

    with (job_dir / "marks.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "score", "max_score", "percentage", "provider", "requires_review"])
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "student_id": r["student_id"],
                    "score": r["total_score"],
                    "max_score": r["max_score"],
                    "percentage": r["percentage"],
                    "provider": r.get("provider", provider["selected_provider"]),
                    "requires_review": "yes",
                }
            )

    marked_gradebook = write_marked_gradebook(job_dir, results)

    lecturer_summary = [
        "# HOMS Lecturer Review Summary",
        "",
        f"Job: `{job_id}`",
        f"Created: {utc_now()}",
        f"Provider: {provider['selected_provider']} / {provider['selected_model']}",
        "",
        "## Batch Results",
    ]
    for r in results:
        lecturer_summary.append(f"- {r['student_id']}: {r['total_score']}/{r['max_score']} ({r['percentage']}%)")
    lecturer_summary.extend(
        [
            "",
            "## Review Boundary",
            "These are draft marking-support outputs for a controlled fake batch. Educator approval is required before final marks or feedback.",
        ]
    )
    if provider_errors:
        lecturer_summary.extend(["", "## Provider Errors", *[f"- {e}" for e in provider_errors]])
    (job_dir / "LECTURER_REVIEW_SUMMARY.md").write_text("\n".join(lecturer_summary).strip() + "\n", encoding="utf-8")
    (job_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    zip_path = job_dir / "HOMS_REVIEW_PACK.zip"
    receipt = {
        "schema": "knowedge.homs_live_batch_receipt.v1",
        "created_at": utc_now(),
        "job_id": job_id,
        "status": "completed",
        "input_dir": str(input_dir) if input_dir else None,
        "secret_file_used": str(secret_file),
        "rubric": {
            "name": rubric.get("name", "unnamed"),
            "total_marks": rubric.get("total_marks"),
            "criteria": [c.get("name", "unnamed") for c in rubric.get("criteria", [])],
        },
        "provider": {
            "selected_provider": provider["selected_provider"],
            "selected_model": provider["selected_model"],
            "selected_key_name": provider["selected_key_name"],
            "base_url": provider["base_url"] or None,
            "available_secret_names": provider["available_keys"],
            "values_redacted": True,
        },
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
    (job_dir / "HOMS_LIVE_BATCH_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    zip_dir(job_dir, zip_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a safe provider-backed HOMS demo batch.")
    parser.add_argument("--secret-file", default=str(DEFAULT_SECRET_FILE))
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "homs_live_batch_test"))
    parser.add_argument("--input", default="", help="Optional HOMS job folder with rubric.json and uploads/*.txt.")
    parser.add_argument("--provider", default="nim", choices=["auto", "nim", "nvidia", "nvidia_nim", "openai"])
    parser.add_argument("--force-fallback", action="store_true", help="Skip provider call and use deterministic fallback.")
    args = parser.parse_args()

    receipt = run_batch(
        Path(args.secret_file).expanduser(),
        Path(args.out).expanduser().resolve(),
        args.force_fallback,
        args.provider,
        Path(args.input).expanduser().resolve() if args.input else None,
    )
    print(json.dumps({"status": receipt["status"], "provider": receipt["provider"]["selected_provider"], "outputs": receipt["outputs"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
