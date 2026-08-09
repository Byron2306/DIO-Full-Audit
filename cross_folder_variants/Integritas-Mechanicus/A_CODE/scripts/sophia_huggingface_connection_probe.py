#!/usr/bin/env python3
"""Probe Hugging Face online capabilities for Sophia without exposing secrets.

This is intentionally small and operational: it checks whether the configured
token can authenticate, then verifies the online routes Sophia needs for
remote embeddings, NLI/zero-shot support checks, and lightweight table QA.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


TOKEN_KEYS = (
    "HF_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "HUGGINGFACE_API_KEY",
)

ENV_CANDIDATES = (
    Path("/home/byron/EdgeK-BEAST/.beast/provider_secrets.env"),
    Path("/home/byron/Downloads/Metatron-triune-outbound-gate/.env"),
    Path("/home/byron/Downloads/Metatron-triune-outbound-gate/backend/.env"),
    Path("/home/byron/Downloads/NicheFoundry_Phase11/.env"),
    Path.cwd() / ".env",
    Path.cwd() / "secrets.env",
    Path.cwd() / "provider_secrets.env",
)


def load_env_files() -> list[str]:
    loaded: list[str] = []
    for path in ENV_CANDIDATES:
        if not path.exists():
            continue
        for raw in path.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().replace("export ", "")
            if key not in TOKEN_KEYS:
                continue
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))
            loaded.append(f"{path}:{key}")
    return loaded


def token() -> str | None:
    for key in TOKEN_KEYS:
        value = os.getenv(key)
        if value:
            return value
    return None


def request_json(url: str, bearer: str, payload: Any | None = None) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    method = "GET" if payload is None else "POST"
    started = time.time()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = resp.read(1500).decode("utf-8", "replace")
            return {
                "ok": True,
                "status": resp.status,
                "latency_ms": int((time.time() - started) * 1000),
                "sample": body[:600],
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(1500).decode("utf-8", "replace")
        return {
            "ok": False,
            "status": exc.code,
            "latency_ms": int((time.time() - started) * 1000),
            "sample": body[:600],
        }
    except Exception as exc:  # pragma: no cover - operational probe
        return {
            "ok": False,
            "status": "EXCEPTION",
            "latency_ms": int((time.time() - started) * 1000),
            "sample": f"{type(exc).__name__}: {str(exc)[:400]}",
        }


def main() -> int:
    loaded = load_env_files()
    bearer = token()
    artifact: dict[str, Any] = {
        "token_present": bool(bearer),
        "env_sources_with_token_keys": loaded,
        "probes": [],
    }
    if not bearer:
        print("HF token not found in environment or known secrets files.")
        return 1

    router = "https://router.huggingface.co/hf-inference/models/"
    probes = [
        {
            "name": "auth_whoami",
            "capability": "authentication",
            "url": "https://huggingface.co/api/whoami-v2",
            "payload": None,
        },
        {
            "name": "bge_small_embedding",
            "capability": "remote_embeddings",
            "url": router + "BAAI/bge-small-en-v1.5",
            "payload": {
                "inputs": [
                    "Sophia preserves human agency through provenance.",
                    "The system scaffolds learning rather than substituting authorship.",
                ],
                "options": {"wait_for_model": True},
            },
        },
        {
            "name": "e5_sentence_similarity",
            "capability": "semantic_similarity",
            "url": router + "intfloat/e5-small-v2",
            "payload": {
                "inputs": {
                    "source_sentence": "query: academic integrity and human agency",
                    "sentences": [
                        "passage: provenance-bound AI writing assistance",
                        "passage: unrelated cricket schedule",
                    ],
                },
                "options": {"wait_for_model": True},
            },
        },
        {
            "name": "deberta_mnli",
            "capability": "nli_entailment",
            "url": router + "microsoft/deberta-base-mnli",
            "payload": {
                "inputs": (
                    "Premise: Sophia preserves authorship by requiring provenance. "
                    "Hypothesis: Sophia supports academic integrity."
                ),
                "options": {"wait_for_model": True},
            },
        },
        {
            "name": "bart_zero_shot_provenance",
            "capability": "zero_shot_support_classification",
            "url": router + "facebook/bart-large-mnli",
            "payload": {
                "inputs": "The uploaded document does not include a citation for this claim.",
                "parameters": {
                    "candidate_labels": [
                        "supported by source",
                        "unsupported claim",
                        "needs provenance",
                    ]
                },
                "options": {"wait_for_model": True},
            },
        },
        {
            "name": "tapas_table_qa",
            "capability": "table_question_answering",
            "url": router + "google/tapas-base-finetuned-wtq",
            "payload": {
                "inputs": {
                    "query": "What is the highest score?",
                    "table": {"system": ["Sophia", "Baseline"], "score": ["92", "71"]},
                },
                "options": {"wait_for_model": True},
            },
        },
    ]

    for probe in probes:
        result = request_json(probe["url"], bearer, probe["payload"])
        artifact["probes"].append({**probe, **result, "url": probe["url"]})
        print(
            f"{probe['name']}: status={result['status']} ok={result['ok']} "
            f"latency_ms={result['latency_ms']}"
        )

    out = Path("evidence/sophia_huggingface_connection_probe_latest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Wrote {out}")

    required = {
        "auth_whoami",
        "bge_small_embedding",
        "e5_sentence_similarity",
        "deberta_mnli",
        "bart_zero_shot_provenance",
        "tapas_table_qa",
    }
    passed = {p["name"] for p in artifact["probes"] if p["ok"]}
    return 0 if required <= passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
