#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
ACQUIRE = ROOT / "scripts" / "acquire_visual_material_pack.py"
PRODUCTION = ROOT / "scripts" / "run_site_format_core_production.py"
INTERNAL = ROOT / "scripts" / "build_site_internal_visual_materials.py"
VERIFY = ROOT / "scripts" / "verify_visual_material_pack.py"
ACQUISITION_MANIFEST = ROOT / "config" / "visual_material_packs" / "research_consultancy_alpha_acquisition.json"
PACK = ROOT / "config" / "visual_material_packs" / "research_consultancy_alpha.json"
RECEIPT_SCHEMA = "dio.site_studio.research_consultancy_visual_pack_bootstrap_receipt.v1"


def _run(command: list[str]) -> dict[str, Any]:
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    parsed: Any = None
    if process.stdout.strip():
        try:
            parsed = json.loads(process.stdout)
        except json.JSONDecodeError:
            parsed = {"stdout": process.stdout.strip()}
    return {
        "command": command,
        "returncode": process.returncode,
        "result": parsed,
        "stderr": process.stderr.strip() or None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the governed Research Consultancy Alpha customer visual pack.")
    parser.add_argument("--acknowledge-source-terms", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "site_studio_format_core_production")
    args = parser.parse_args()

    if not args.acknowledge_source_terms:
        raise SystemExit("REFUSE: pass --acknowledge-source-terms after reviewing the curated source license/terms")

    output = args.output.expanduser().resolve()
    phases: list[dict[str, Any]] = []

    acquire = _run([
        PYTHON,
        str(ACQUIRE),
        "--manifest", str(ACQUISITION_MANIFEST),
        "--acknowledge-source-terms",
    ])
    phases.append({"phase": "acquire_curated_materials", **acquire})
    if acquire["returncode"] != 0:
        print(json.dumps({"schema": RECEIPT_SCHEMA, "state": "REFUSE", "phases": phases}, indent=2, ensure_ascii=False))
        return 2

    initial = _run([PYTHON, str(PRODUCTION), "--output", str(output)])
    phases.append({"phase": "initial_site_build", **initial})
    if initial["returncode"] != 0:
        print(json.dumps({"schema": RECEIPT_SCHEMA, "state": "REFUSE", "phases": phases}, indent=2, ensure_ascii=False))
        return 2

    internal = _run([
        PYTHON,
        str(INTERNAL),
        "--site-root", str(output / "customer" / "FULL_GRADE_SITE"),
    ])
    phases.append({"phase": "build_internal_artifact_materials", **internal})
    if internal["returncode"] != 0:
        print(json.dumps({"schema": RECEIPT_SCHEMA, "state": "REFUSE", "phases": phases}, indent=2, ensure_ascii=False))
        return 2

    verify = _run([PYTHON, str(VERIFY), "--pack", str(PACK), "--strict"])
    phases.append({"phase": "verify_customer_visual_pack", **verify})
    if verify["returncode"] != 0:
        print(json.dumps({"schema": RECEIPT_SCHEMA, "state": "REFUSE", "phases": phases}, indent=2, ensure_ascii=False))
        return 2

    final = _run([
        PYTHON,
        str(PRODUCTION),
        "--output", str(output),
        "--require-customer-visual-pack",
    ])
    phases.append({"phase": "final_customer_pack_site_build", **final})
    state = "PASS_NEEDS_YOU" if final["returncode"] == 0 else "REFUSE"
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "state": state,
        "output": str(output),
        "pack": str(PACK),
        "phases": phases,
        "customer_visual_pack": "READY_NEEDS_YOU" if state == "PASS_NEEDS_YOU" else "REFUSE",
        "commercial_validation": "UNPROVED",
        "human_visual_release": "NEEDS_YOU",
        "automatic_publication": "REFUSE",
        "authority_created": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if final["returncode"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
