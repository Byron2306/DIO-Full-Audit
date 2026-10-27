from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class TranslationState(StrEnum):
    MACHINE_REVIEW_CANDIDATE = "machine_review_candidate"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    HUMAN_APPROVED_CRYSTALLIZED = "human_approved_crystallized"
    STALE_SOURCE_CHANGED = "stale_source_changed"
    MISSING = "missing"


_ALIASES = {
    "approved": TranslationState.HUMAN_APPROVED_CRYSTALLIZED,
    "human_approved": TranslationState.HUMAN_APPROVED_CRYSTALLIZED,
    "crystallized": TranslationState.HUMAN_APPROVED_CRYSTALLIZED,
    "crystallised": TranslationState.HUMAN_APPROVED_CRYSTALLIZED,
}


@dataclass(frozen=True)
class TranslationResolution:
    state: TranslationState
    reusable: bool
    text: str | None
    reason: str


def resolve_translation(lane: Mapping[str, Any] | None, *, locale: str, source_digest: str) -> TranslationResolution:
    if not lane:
        return TranslationResolution(TranslationState.MISSING, False, None, "translation_missing")
    raw = str(lane.get("state") or lane.get("status") or TranslationState.MISSING)
    state = _ALIASES.get(raw, TranslationState(raw) if raw in TranslationState._value2member_map_ else TranslationState.MISSING)
    if str(lane.get("locale") or lane.get("language") or "") != locale:
        return TranslationResolution(state, False, None, "locale_mismatch")
    if str(lane.get("source_digest") or lane.get("source_document_hash") or "") != source_digest:
        return TranslationResolution(TranslationState.STALE_SOURCE_CHANGED, False, None, "source_digest_mismatch")
    text = lane.get("text") or lane.get("target_text")
    reusable = state is TranslationState.HUMAN_APPROVED_CRYSTALLIZED and bool(text)
    return TranslationResolution(state, reusable, str(text) if reusable else None, "reusable" if reusable else "approval_required")
