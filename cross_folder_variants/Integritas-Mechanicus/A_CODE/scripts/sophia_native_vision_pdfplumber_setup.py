#!/usr/bin/env python3
"""Validate optional native vision and pdfplumber setup for Sophia."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "arda_os"))


def _load_env_files() -> List[str]:
    candidates = [
        Path("/home/byron/EdgeK-BEAST/.beast/provider_secrets.env"),
        Path("/home/byron/Downloads/Metatron-triune-outbound-gate/.env"),
        Path("/home/byron/Downloads/Metatron-triune-outbound-gate/backend/.env"),
        Path("/home/byron/Downloads/NicheFoundry_Phase11/.env"),
        REPO_ROOT / "provider_secrets.env",
        REPO_ROOT / "secrets.env",
        REPO_ROOT / ".env",
    ]
    loaded = []
    for path in candidates:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value
        loaded.append(str(path))
    return loaded


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def run_suite(*, probe_gemini: bool = False) -> Dict[str, Any]:
    loaded = _load_env_files()
    cases: List[Dict[str, Any]] = []
    try:
        import pdfplumber  # type: ignore
        cases.append(_case("pdfplumber_import", True, version=getattr(pdfplumber, "__version__", "unknown")))
    except Exception as exc:
        cases.append(_case("pdfplumber_import", False, error=type(exc).__name__))

    try:
        from PIL import Image, ImageDraw
        cases.append(_case("pillow_import", True))
    except Exception as exc:
        Image = None  # type: ignore
        ImageDraw = None  # type: ignore
        cases.append(_case("pillow_import", False, error=type(exc).__name__))

    from backend.services.gemini_vision import analyze_image_with_gemini, gemini_vision_status

    status = gemini_vision_status()
    cases.append(_case(
        "gemini_key_detected_without_exposure",
        bool(status.get("configured")),
        status={k: v for k, v in status.items() if k != "api_key"},
        env_files_loaded_count=len(loaded),
    ))

    os.environ["SOPHIA_ENABLE_NATIVE_VISION"] = os.environ.get("SOPHIA_ENABLE_NATIVE_VISION") or "1"
    os.environ["SOPHIA_NATIVE_VISION_PROVIDER"] = os.environ.get("SOPHIA_NATIVE_VISION_PROVIDER") or "gemini"
    status_after_enable = gemini_vision_status()
    cases.append(_case(
        "native_vision_status_ready_if_key_present",
        (not status_after_enable.get("configured")) or status_after_enable.get("status") == "ready",
        status=status_after_enable,
    ))

    if probe_gemini and status_after_enable.get("configured") and Image is not None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sophia_vision_probe.png"
            image = Image.new("RGB", (640, 220), color="white")
            draw = ImageDraw.Draw(image)
            draw.text((24, 70), "Sophia vision probe: agency + provenance", fill="black")
            image.save(path)
            result = analyze_image_with_gemini(
                path,
                prompt="Read the visible text. Return one short line and uncertainty if any.",
                timeout=30.0,
            )
            text = str(result.get("text") or "").lower()
            cases.append(_case(
                "gemini_native_vision_probe",
                result.get("status") == "checked" and ("sophia" in text or "agency" in text or "provenance" in text),
                result={**result, "text": str(result.get("text") or "")[:500]},
            ))
    else:
        cases.append(_case(
            "gemini_native_vision_probe_skipped",
            True,
            reason="use --probe-gemini and a configured key to run a live image call",
            configured=bool(status_after_enable.get("configured")),
        ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "suite": "sophia_native_vision_pdfplumber_setup",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-gemini", action="store_true")
    parser.add_argument("--out", default=str(REPO_ROOT / "evidence" / "sophia_native_vision_pdfplumber_setup_latest.json"))
    args = parser.parse_args()
    artifact = run_suite(probe_gemini=args.probe_gemini)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
