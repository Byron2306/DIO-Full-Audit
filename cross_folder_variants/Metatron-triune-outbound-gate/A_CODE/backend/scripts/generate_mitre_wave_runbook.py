#!/usr/bin/env python3
"""Generate an executable dry-run runbook for a MITRE validation wave."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_dir = ROOT / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from backend.atomic_validation import atomic_validation


REPORT_DIR = ROOT / "test_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _command_for_job(job_id: str, *, dry_run: bool) -> str:
    dry = "True" if dry_run else "False"
    return (
        f"cd {ROOT} && {ROOT / '.venv/bin/python'} -c \""
        "import os, sys; "
        f"sys.path.insert(0, '{ROOT}'); sys.path.insert(0, '{backend_dir}'); "
        "from backend.atomic_validation import atomic_validation; "
        f"print(atomic_validation.run_job('{job_id}', dry_run={dry}))"
        "\""
    )


def _write_markdown(report: Dict[str, Any], md_path: Path) -> None:
    lines = [
        f"# MITRE Wave Runbook: {report['wave_id'].upper()}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Wave size: {report['wave_size']}",
        f"- Unique jobs: {report['job_count']}",
        f"- Runner available: {report['atomic_status'].get('runner_available')}",
        f"- Atomic root exists: {report['atomic_status'].get('atomic_root_exists')}",
        "",
        "## Jobs",
        "",
        "| Job | Dry Run OK | Runner Profile | Techniques | Dry-Run Command |",
        "|---|---|---|---|---|",
    ]

    for job in report["jobs"]:
        lines.append(
            f"| {job['job_id']} | {job['dry_run_ok']} | {job.get('runner_profile') or ''} | {', '.join(job.get('techniques') or [])} | `{job['shell_command']}` |"
        )

    lines.extend([
        "",
        "## Techniques",
        "",
        "| Technique | Name | Jobs | Atomic | Next Action |",
        "|---|---|---|---|---|",
    ])
    for item in report["techniques"]:
        lines.append(
            f"| {item['technique']} | {item.get('technique_name') or ''} | {', '.join(item.get('job_ids') or [])} | {item.get('has_atomic_dir')} | {item.get('next_action') or ''} |"
        )

    md_path.write_text("\n".join(lines), encoding="utf-8")


def _write_shell_scripts(report: Dict[str, Any], wave_id: str) -> Dict[str, str]:
    dry_run_path = REPORT_DIR / f"mitre_{wave_id}_dry_run.sh"
    real_run_path = REPORT_DIR / f"mitre_{wave_id}_real_run.sh"

    def _build_script(*, dry_run: bool) -> str:
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"cd '{ROOT}'",
            "set -a",
            "source .env",
            "set +a",
        ]
        for job in report["jobs"]:
            command = job["shell_command"] if dry_run else job["real_run_command"]
            lines.append(command)
        return "\n".join(lines) + "\n"

    dry_run_path.write_text(_build_script(dry_run=True), encoding="utf-8")
    real_run_path.write_text(_build_script(dry_run=False), encoding="utf-8")
    return {
        "dry_run_script": str(dry_run_path),
        "real_run_script": str(real_run_path),
    }


def run() -> int:
    wave_id = os.environ.get("MITRE_WAVE_ID", "wave-01").strip().lower() or "wave-01"
    wave_plan = json.loads((REPORT_DIR / "mitre_validation_wave_plan.json").read_text(encoding="utf-8"))
    waves = (wave_plan.get("execution_lane") or {}).get("waves") or []
    wave = next((item for item in waves if str(item.get("wave_id") or "").lower() == wave_id), None)
    if not wave:
        raise SystemExit(f"Unknown wave_id: {wave_id}")

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass

    atomic_status = atomic_validation.get_status()
    jobs_payload = atomic_validation.list_jobs()
    known_jobs = {job.get("job_id"): job for job in (jobs_payload.get("jobs") or []) if job.get("job_id")}

    job_ids = list(wave.get("job_ids") or [])
    job_reports: List[Dict[str, Any]] = []
    for job_id in job_ids:
        dry_run_result = atomic_validation.run_job(job_id, dry_run=True)
        job_meta = known_jobs.get(job_id) or {}
        job_reports.append(
            {
                "job_id": job_id,
                "name": job_meta.get("name") or dry_run_result.get("job_name") or "",
                "runner_profile": dry_run_result.get("runner_profile") or job_meta.get("runner_profile") or "",
                "techniques": dry_run_result.get("techniques") or job_meta.get("techniques") or [],
                "dry_run_ok": bool(dry_run_result.get("ok")),
                "dry_run_status": dry_run_result.get("status"),
                "dry_run_message": dry_run_result.get("message"),
                "resolved_command": dry_run_result.get("command"),
                "execution_mode": dry_run_result.get("execution_mode"),
                "shell_command": _command_for_job(job_id, dry_run=True),
                "real_run_command": _command_for_job(job_id, dry_run=False),
            }
        )

    techniques: List[Dict[str, Any]] = []
    for item in wave.get("techniques") or []:
        techniques.append(
            {
                "technique": item.get("technique"),
                "technique_name": item.get("technique_name"),
                "job_ids": [job.get("job_id") for job in item.get("jobs") or [] if job.get("job_id")],
                "has_atomic_dir": item.get("has_atomic_dir"),
                "next_action": item.get("next_action"),
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "wave_id": wave_id,
        "wave_size": int(wave.get("size") or len(techniques)),
        "job_count": len(job_reports),
        "atomic_status": atomic_status,
        "jobs": job_reports,
        "techniques": techniques,
    }

    json_path = REPORT_DIR / f"mitre_{wave_id}_runbook.json"
    md_path = REPORT_DIR / f"mitre_{wave_id}_runbook.md"
    script_paths = _write_shell_scripts(report, wave_id)
    report.update(script_paths)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report, md_path)
    print(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "wave_id": wave_id,
                "job_count": report["job_count"],
                "runner_available": atomic_status.get("runner_available"),
                "atomic_root_exists": atomic_status.get("atomic_root_exists"),
                "report_json": str(json_path),
                "report_md": str(md_path),
                **script_paths,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())