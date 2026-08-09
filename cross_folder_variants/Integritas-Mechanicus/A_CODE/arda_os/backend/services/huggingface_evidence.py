"""Optional Hugging Face evidence checks for Sophia Writing Desk.

The service is deliberately small and dependency-free. It never exposes the
token and it degrades to an auditable unavailable result instead of blocking
the Presence server when the remote route is unavailable.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def _load_env_files() -> List[str]:
    loaded: List[str] = []
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


def _token() -> Optional[str]:
    for key in TOKEN_KEYS:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _coerce_score(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(max(0.0, min(1.0, float(value))), 4)
    except (TypeError, ValueError):
        return None


class HuggingFaceEvidenceClient:
    """Remote NLI/similarity checks through Hugging Face router."""

    router = "https://router.huggingface.co/hf-inference/models/"
    zero_shot_model = "facebook/bart-large-mnli"
    similarity_model = "intfloat/e5-small-v2"

    def __init__(self, timeout_seconds: int = 35):
        self.env_sources = _load_env_files()
        self.token = _token()
        self.timeout_seconds = timeout_seconds

    def status(self) -> Dict[str, Any]:
        return {
            "available": bool(self.token),
            "token_present": bool(self.token),
            "env_sources_with_token_keys": self.env_sources,
            "zero_shot_model": self.zero_shot_model,
            "similarity_model": self.similarity_model,
        }

    def _post(self, model: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "hf_token_not_configured", "model": model}
        started = time.time()
        req = urllib.request.Request(
            self.router + model,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read(4000).decode("utf-8", "replace")
                return {
                    "ok": True,
                    "status": resp.status,
                    "latency_ms": int((time.time() - started) * 1000),
                    "model": model,
                    "data": json.loads(body),
                }
        except urllib.error.HTTPError as exc:
            body = exc.read(1500).decode("utf-8", "replace")
            return {
                "ok": False,
                "status": exc.code,
                "latency_ms": int((time.time() - started) * 1000),
                "model": model,
                "error": body[:600],
            }
        except Exception as exc:  # pragma: no cover - operational network path
            return {
                "ok": False,
                "status": "EXCEPTION",
                "latency_ms": int((time.time() - started) * 1000),
                "model": model,
                "error": f"{type(exc).__name__}: {str(exc)[:400]}",
            }

    def score_similarity(self, claim: str, evidence_span: str) -> Dict[str, Any]:
        claim = (claim or "").strip()
        evidence_span = (evidence_span or "").strip()
        if not claim or not evidence_span:
            return {"available": False, "error": "claim_and_evidence_required"}
        raw = self._post(
            self.similarity_model,
            {
                "inputs": {
                    "source_sentence": f"query: {claim[:900]}",
                    "sentences": [f"passage: {evidence_span[:1400]}"],
                },
                "options": {"wait_for_model": True},
            },
        )
        score = None
        data = raw.get("data")
        if isinstance(data, list) and data:
            score = _coerce_score(data[0])
        elif isinstance(data, dict):
            score = _coerce_score(data.get("score") or data.get("similarity"))
        return {
            "available": bool(raw.get("ok")),
            "semantic_similarity": score,
            "model": self.similarity_model,
            "raw_status": raw.get("status"),
            "latency_ms": raw.get("latency_ms"),
            "error": raw.get("error") if not raw.get("ok") else "",
        }

    def classify_support(self, claim: str, evidence_span: str) -> Dict[str, Any]:
        claim = (claim or "").strip()
        evidence_span = (evidence_span or "").strip()
        if not claim or not evidence_span:
            return {
                "available": False,
                "support_label": "insufficient_text",
                "entailment_status": "not_tested",
                "error": "claim_and_evidence_required",
            }
        labels = [
            "directly supports",
            "partially supports",
            "contradicts",
            "does not support",
        ]
        raw = self._post(
            self.zero_shot_model,
            {
                "inputs": f"Claim: {claim[:900]}\nEvidence: {evidence_span[:1400]}",
                "parameters": {"candidate_labels": labels},
                "options": {"wait_for_model": True},
            },
        )
        label = "unknown"
        score = None
        ranked: List[Dict[str, Any]] = []
        data = raw.get("data")
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                ranked.append({
                    "label": str(item.get("label") or ""),
                    "score": _coerce_score(item.get("score")),
                })
            ranked = [item for item in ranked if item["label"]]
            ranked.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
            if ranked:
                label = ranked[0]["label"]
                score = ranked[0]["score"]
        elif isinstance(data, dict) and isinstance(data.get("labels"), list):
            scores = data.get("scores") if isinstance(data.get("scores"), list) else []
            for idx, candidate in enumerate(data["labels"]):
                ranked.append({
                    "label": str(candidate),
                    "score": _coerce_score(scores[idx] if idx < len(scores) else None),
                })
            if ranked:
                label = ranked[0]["label"]
                score = ranked[0]["score"]
        mapped = {
            "directly supports": "entails",
            "partially supports": "partial_support",
            "contradicts": "contradiction",
            "does not support": "does_not_support",
        }.get(label, "unknown")
        score_by_label = {str(item.get("label") or ""): float(item.get("score") or 0.0) for item in ranked}
        negative_mass = score_by_label.get("contradicts", 0.0) + score_by_label.get("does not support", 0.0)
        direct_support = score_by_label.get("directly supports", 0.0)
        if mapped == "partial_support" and (score or 0.0) < 0.55 and direct_support < 0.15 and negative_mass >= 0.40:
            label = "does not support"
            mapped = "does_not_support"
            score = round(max(negative_mass, 1.0 - float(score or 0.0)), 4)
        similarity = self.score_similarity(claim, evidence_span)
        return {
            "available": bool(raw.get("ok")),
            "support_label": label,
            "support_score": score,
            "entailment_status": mapped,
            "entailment_score": score,
            "semantic_similarity": similarity.get("semantic_similarity"),
            "support_model": self.zero_shot_model,
            "similarity_model": self.similarity_model,
            "ranked_labels": ranked,
            "latency_ms": raw.get("latency_ms"),
            "similarity_latency_ms": similarity.get("latency_ms"),
            "error": raw.get("error") if not raw.get("ok") else similarity.get("error", ""),
        }


def get_huggingface_evidence_client(timeout_seconds: int = 35) -> HuggingFaceEvidenceClient:
    return HuggingFaceEvidenceClient(timeout_seconds=timeout_seconds)
