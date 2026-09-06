from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _beast_imports():
    repo_root = Path(__file__).resolve().parents[2]
    beast_root = repo_root / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
    if not beast_root.is_dir():
        return None
    if str(beast_root) not in sys.path:
        sys.path.insert(0, str(beast_root))
    try:
        from app.kernel.compute.operator_language import realize_answer_frame
        from app.kernel.compute.residual_contracts import sha256_digest
        from app.kernel.compute.semantic_generalizer import (
            SemanticCrystalRegistry,
            SemanticGeneralizer,
            SemanticReuseKey,
            normalize_utterance,
            semantic_intent_fingerprint,
        )
    except (ImportError, ModuleNotFoundError):
        return None
    return {
        "SemanticCrystalRegistry": SemanticCrystalRegistry,
        "SemanticGeneralizer": SemanticGeneralizer,
        "SemanticReuseKey": SemanticReuseKey,
        "normalize_utterance": normalize_utterance,
        "semantic_intent_fingerprint": semantic_intent_fingerprint,
        "sha256_digest": sha256_digest,
        "realize_answer_frame": realize_answer_frame,
    }


def resolve_conversation_crystal(
    *,
    root: Path,
    text: str,
    registry_path: Path | None = None,
    tone: str = "concise",
) -> dict[str, Any] | None:
    api = _beast_imports()
    if api is None:
        return None

    path = registry_path or root / "state" / "lingua" / "vesper_conversation_semantic_crystals.jsonl"
    if not path.is_file():
        return None

    try:
        registry = api["SemanticCrystalRegistry"](path)
        registry.load()
        records = registry.records()
    except (OSError, ValueError, TypeError, KeyError):
        return None

    normalized = api["normalize_utterance"](text)
    fingerprint = api["semantic_intent_fingerprint"](text)
    semantic_digest = api["sha256_digest"](fingerprint)
    normalized_digest = api["sha256_digest"](normalized)
    generalizer = api["SemanticGeneralizer"]()

    for record in records:
        sealed = record.semantic_reuse_key
        try:
            request_key = api["SemanticReuseKey"](
                semantic_fingerprint_digest=semantic_digest,
                normalized_utterance_digest=normalized_digest,
                schema_digest=sealed.schema_digest,
                discourse_digest=sealed.discourse_digest,
                world_digest=sealed.world_digest,
                capability_digest=sealed.capability_digest,
                evidence_digest=sealed.evidence_digest,
                policy_digest=sealed.policy_digest,
                temporal_scope_digest=sealed.temporal_scope_digest,
            )
            outcome = generalizer.replay_record(
                record,
                request_key,
                provider_enabled=False,
            )
        except (ValueError, TypeError, KeyError):
            continue
        if not outcome.reused or outcome.answer_frame is None:
            continue
        try:
            reply = api["realize_answer_frame"](outcome.answer_frame, tone=tone)
        except (ValueError, TypeError):
            continue
        return {
            "schema": "dio.vesper.conversation_crystal_reuse.v1",
            "reply": reply,
            "source": "lingua_crystal",
            "crystal_id": record.crystal.crystal_id,
            "reuse_receipt_digest": outcome.receipt_digest,
            "provider_called": False,
            "authority_created": False,
        }
    return None
