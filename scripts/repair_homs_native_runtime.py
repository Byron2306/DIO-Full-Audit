#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = Path("/home/byron/Downloads/NoEdge-Multi-Hymark-main/homs_production/venv/bin/python")
DEFAULT_BACKEND = Path("/home/byron/Downloads/NoEdge-Multi-Hymark-main/backend/server.py")
DEFAULT_REQUIREMENTS = ROOT / "config" / "homs_native_runtime_requirements.txt"
REQUIRED_IMPORTS = (
    "bson",
    "pymongo",
    "dotenv",
    "fastapi",
    "openai",
    "pydantic",
    "docx",
    "multipart",
    "PyPDF2",
)


def native_env(python: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key in {
            "VIRTUAL_ENV",
            "VIRTUAL_ENV_PROMPT",
            "PYTHONHOME",
            "PYTHONPATH",
            "PYTHONNOUSERSITE",
        } or key.startswith("CONDA_") or key.startswith("_CE_"):
            env.pop(key, None)
    env["PATH"] = f"{python.parent}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    return env


def run_import_audit(python: Path) -> dict[str, object]:
    code = r'''
import importlib
import json
mods = json.loads(__import__("os").environ["DIO_HOMS_REQUIRED_IMPORTS"])
results = {}
for name in mods:
    try:
        module = importlib.import_module(name)
        results[name] = {
            "ok": True,
            "version": str(getattr(module, "__version__", "")),
        }
    except Exception as exc:
        results[name] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
print(json.dumps(results, sort_keys=True))
'''
    env = native_env(python)
    env["DIO_HOMS_REQUIRED_IMPORTS"] = json.dumps(REQUIRED_IMPORTS)
    completed = subprocess.run(
        [str(python), "-c", code],
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=120,
    )
    if completed.returncode != 0:
        return {
            "audit_process_ok": False,
            "stderr": (completed.stderr or "")[-2000:],
            "stdout": (completed.stdout or "")[-2000:],
            "imports": {},
        }
    try:
        imports = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {
            "audit_process_ok": False,
            "stderr": f"Could not parse import audit: {exc}",
            "stdout": completed.stdout[-2000:],
            "imports": {},
        }
    return {"audit_process_ok": True, "imports": imports}


def run_backend_import(python: Path, backend: Path) -> dict[str, object]:
    code = r'''
import importlib.util
import os
from pathlib import Path
path = Path(os.environ["DIO_HOMS_BACKEND"])
spec = importlib.util.spec_from_file_location("dio_homs_runtime_preflight", path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load backend spec from {path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print("HOMS_NATIVE_BACKEND_IMPORT_OK")
'''
    env = native_env(python)
    env["DIO_HOMS_BACKEND"] = str(backend)
    completed = subprocess.run(
        [str(python), "-c", code],
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=120,
    )
    return {
        "ok": completed.returncode == 0,
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
    }


def run_pip_check(python: Path) -> dict[str, object]:
    completed = subprocess.run(
        [str(python), "-m", "pip", "check"],
        text=True,
        capture_output=True,
        check=False,
        env=native_env(python),
        timeout=120,
    )
    return {
        "ok": completed.returncode == 0,
        "stdout": (completed.stdout or "")[-3000:],
        "stderr": (completed.stderr or "")[-3000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit or repair the isolated native HyMark runtime used by DIO.")
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--backend", type=Path, default=DEFAULT_BACKEND)
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--install", action="store_true", help="Install/repair the declared native runtime dependencies before auditing.")
    args = parser.parse_args()

    python = args.python.expanduser().resolve()
    backend = args.backend.expanduser().resolve()
    requirements = args.requirements.expanduser().resolve()
    if not python.is_file():
        raise SystemExit(f"Native HyMark Python missing: {python}")
    if not backend.is_file():
        raise SystemExit(f"Native HyMark backend missing: {backend}")
    if not requirements.is_file():
        raise SystemExit(f"Native HyMark requirements contract missing: {requirements}")

    install_result = None
    if args.install:
        completed = subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(requirements)],
            text=True,
            capture_output=True,
            check=False,
            env=native_env(python),
            timeout=900,
        )
        install_result = {
            "returncode": completed.returncode,
            "stdout_tail": (completed.stdout or "")[-3000:],
            "stderr_tail": (completed.stderr or "")[-3000:],
        }
        if completed.returncode != 0:
            print(json.dumps({"installed": False, "install": install_result}, indent=2))
            return 2

    audit = run_import_audit(python)
    imports = dict(audit.get("imports") or {})
    failed_imports = [name for name, row in imports.items() if not bool((row or {}).get("ok"))]
    backend_check = run_backend_import(python, backend) if not failed_imports and audit.get("audit_process_ok") else {"ok": False, "skipped": True}
    pip_check = run_pip_check(python)
    passed = (
        bool(audit.get("audit_process_ok"))
        and not failed_imports
        and bool(backend_check.get("ok"))
        and bool(pip_check.get("ok"))
    )

    result = {
        "schema": "dio.homs.native_runtime_preflight.v1",
        "python": str(python),
        "backend": str(backend),
        "requirements": str(requirements),
        "install_attempted": args.install,
        "install": install_result,
        "imports": imports,
        "failed_imports": failed_imports,
        "backend_import": backend_check,
        "pip_check": pip_check,
        "environment_isolated": True,
        "passed": passed,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
