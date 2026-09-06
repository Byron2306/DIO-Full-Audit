from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BEAST_CODE_ROOT = REPO_ROOT / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"


def _beast_api():
    if not BEAST_CODE_ROOT.exists():
        return None
    if str(BEAST_CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(BEAST_CODE_ROOT))
    try:
        from app.kernel.compute.operator_language import realize_answer_frame
        from app.kernel.compute.residual_contracts import sha256_digest
        from app.kernel.compute.semantic_generalizer import (
            SemanticCrystalLifecycleState,
            SemanticCrystalRegistry,
            SemanticGeneralizer,
            SemanticReuseKey,
            normalize_utterance,
            semantic_intent_fingerprint,
        )
    except Exception:
        return None
    return {
        "realize_answer_frame": realize_answer_frame,
        "sha256_digest": sha256_digest,
        "SemanticCrystalLifecycleState": SemanticCrystalLifecycleState,
        "SemanticCrystalRegistry": SemanticCrystalRegistry,
        "SemanticGeneralizer": SemanticGeneralizer,
        "SemanticReuseKey": SemanticReuseKey,
        "normalize_utterance": normalize_utterance,
        "semantic_intent_fingerprint": semantic_intent_fingerprint,
    }


def resolve_conversation_crystal(
    *,
    root: Path,
    text: str,
    registry_path: Path | None = None,
    tone: str = "concise",
) -> dict[str, Any] | None:
    api = _beast_api()
    if api is None:
        return None

    path = Path(registry_path) if registry_path is not None else (
        Path(root) / "state" / "lingua" / "vesper_conversation_semantic_crystals.jsonl"
    )
    if not path.exists():
        return None

    try:
        registry = api["SemanticCrystalRegistry"](path)
        registry.load()
        fingerprint_digest = api["sha256_digest"](api["semantic_intent_fingerprint"](text))
        normalized_digest = api["sha256_digest"](api["normalize_utterance"](text))
        generalizer = api["SemanticGeneralizer"]()
        active_state = api["SemanticCrystalLifecycleState"].ACTIVE

        for record in registry.records():
            if record.lifecycle_state is not active_state:
                continue
            sealed = record.semantic_reuse_key
            request_key = api["SemanticReuseKey"](
                semantic_fingerprint_digest=fingerprint_digest,
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
            if not outcome.reused or outcome.answer_frame is None or outcome.provider_called:
                continue
            realized = api["realize_answer_frame"](outcome.answer_frame, tone=tone).strip()
            if not realized:
                continue
            return {
                "schema": "dio.vesper.conversation_crystal_reuse.v1",
                "reply": realized,
                "source": "lingua_crystal",
                "crystal_id": record.crystal.crystal_id,
                "reuse_receipt_digest": outcome.receipt_digest,
                "provider_called": False,
                "authority_created": False,
            }
    except Exception:
        return None
    return None
