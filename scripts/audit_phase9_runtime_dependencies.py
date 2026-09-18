#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ACTIVE_LLM_RUNTIME_FILES = [
    Path("presence_core/llm.py"),
    Path("adapters/document_studio/pipeline.py"),
    Path("adapters/sophia/review_pipeline.py"),
    Path("scripts/manage_sophia_commercial.py"),
    Path("sovereign_runtime.py"),
]

FORBIDDEN_RUNTIME_MARKERS = {
    "https://router.huggingface.co": "hugging_face_inference_router",
    "generativelanguage.googleapis.com": "gemini_api",
    "api.openai.com": "openai_api",
    "api.anthropic.com": "anthropic_api",
    "integrate.api.nvidia.com": "nvidia_nim_api",
    "document_studio_gemini_bridge.py": "document_studio_gemini_bridge",
    "document_studio_nim_bridge.py": "document_studio_nim_bridge",
}

ALLOWED_PROVIDER_MARKERS = {
    "ollama",
    "local",
    "local_ollama",
}


def audit() -> dict:
    findings = []
    inspected = []
    for relative in ACTIVE_LLM_RUNTIME_FILES:
        path = ROOT / relative
        if not path.is_file():
            findings.append({
                "path": str(relative),
                "kind": "missing_active_runtime_file",
                "marker": None,
            })
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        inspected.append(str(relative))
        for marker, kind in FORBIDDEN_RUNTIME_MARKERS.items():
            if marker in text:
                findings.append({
                    "path": str(relative),
                    "kind": kind,
                    "marker": marker,
                })

    return {
        "schema": "dio.phase9.runtime_dependency_audit.v1",
        "active_runtime_files": inspected,
        "active_llm_provider": "ollama",
        "cloud_llm_runtime_calls": len(findings),
        "hf_runtime_dependencies": sum(
            1 for row in findings
            if row["kind"] == "hugging_face_inference_router"
        ),
        "findings": findings,
        "historical_artifacts_scoped_out": True,
        "cross_folder_variants_scoped_out": True,
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["findings"]:
        return 1
    print("ACTIVE_LLM_PROVIDERS=ollama")
    print("CLOUD_LLM_RUNTIME_CALLS=0")
    print("HF_RUNTIME_DEPENDENCIES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
