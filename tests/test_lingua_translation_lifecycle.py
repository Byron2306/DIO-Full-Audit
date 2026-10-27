from __future__ import annotations

from adapters.lingua.translation_lifecycle import TranslationState, resolve_translation


def test_exact_human_approved_translation_is_reusable() -> None:
    lane = {"locale": "zu", "source_digest": "sha256:source", "state": "human_approved_crystallized", "text": "Sawubona"}
    result = resolve_translation(lane, locale="zu", source_digest="sha256:source")
    assert result.reusable is True
    assert result.text == "Sawubona"


def test_changed_source_or_locale_cannot_reuse_approved_translation() -> None:
    lane = {"locale": "zu", "source_digest": "sha256:source", "state": "human_approved_crystallized", "text": "Sawubona"}
    assert resolve_translation(lane, locale="zu", source_digest="sha256:changed").reusable is False
    assert resolve_translation(lane, locale="af", source_digest="sha256:source").reusable is False


def test_legacy_approved_alias_is_normalised_but_not_english_fallback() -> None:
    lane = {"locale": "zu", "source_digest": "sha256:source", "state": "approved", "text": "Sawubona"}
    result = resolve_translation(lane, locale="zu", source_digest="sha256:source")
    assert result.state is TranslationState.HUMAN_APPROVED_CRYSTALLIZED
    assert result.reusable is True
    assert resolve_translation(None, locale="zu", source_digest="sha256:source").text is None
