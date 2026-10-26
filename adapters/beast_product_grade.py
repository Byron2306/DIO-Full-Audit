from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class BeastProductGradeError(RuntimeError):
    pass


def run_beast_artifact_checks(*, dio_root: Path, workspace: Path, timeout_seconds: int = 20) -> dict[str, Any]:
    """Run selected existing BEAST QualityCascade checks in an isolated process.

    This adapter does not reimplement BEAST quality logic. It imports the existing
    BEAST QualityCascade from the harvested EdgeK-BEAST source tree and asks it to
    inspect the generated customer package. A skipped optional tool is reported as
    skipped; an actual syntax failure is a ProductGrade mechanical failure.
    """
    dio_root = Path(dio_root).resolve()
    workspace = Path(workspace).resolve()
    beast_root = dio_root / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
    source = beast_root / "app" / "kernel" / "data_processing" / "quality_cascade.py"
    if not source.is_file():
        raise BeastProductGradeError(f"BEAST QualityCascade source missing: {source}")
    if not workspace.is_dir():
        raise BeastProductGradeError(f"ProductGrade workspace missing: {workspace}")

    program = r'''
import json
import sys
from pathlib import Path
beast_root = Path(sys.argv[1]).resolve()
workspace = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(beast_root))
from app.kernel.data_processing.quality_cascade import QualityCascade
cascade = QualityCascade()
checks = [
    cascade.check_language_inventory(workspace).to_dict(),
    cascade.check_html_syntax(workspace).to_dict(),
    cascade.check_javascript_syntax(workspace, timeout_seconds=15).to_dict(),
]
failed = [row for row in checks if row.get("status") == "failed"]
print(json.dumps({
    "schema": "dio.beast.product_grade_artifact_checks.v1",
    "source": "EdgeK-BEAST/app/kernel/data_processing/quality_cascade.py",
    "workspace": str(workspace),
    "checks": checks,
    "failed_count": len(failed),
    "mechanical_pass": not failed,
}, sort_keys=True))
'''
    result = subprocess.run(
        [sys.executable, "-c", program, str(beast_root), str(workspace)],
        cwd=str(dio_root),
        capture_output=True,
        text=True,
        timeout=max(5, int(timeout_seconds)),
        check=False,
    )
    if result.returncode != 0:
        raise BeastProductGradeError(
            "BEAST ProductGrade subprocess failed: " + (result.stderr or result.stdout or "unknown error")[-2000:]
        )
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise BeastProductGradeError("BEAST ProductGrade subprocess returned invalid JSON") from exc
    payload["quality_cascade_source_sha256"] = _sha256(source)
    return payload


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
