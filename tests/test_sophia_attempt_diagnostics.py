from pathlib import Path
from unittest.mock import patch

from adapters.sophia.review_pipeline import reviewer_commentary


def test_rejected_review_preserves_native_failures(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text(
        "The manuscript makes an unsupported causal claim.",
        encoding="utf-8",
    )

    native_response = {
        "encounter_id": "test-encounter-001",
        "response": "## Major revisions\n[P1] The causal claim lacks evidence.",
        "source": "reasoned_integrity_lane",
        "reasoned_provider": "ollama",
        "reasoned_provider_status": "ok",
        "model": "test-local-model",
        "mandos_judgment": {
            "passed": True,
            "failed_checks": [],
        },
        "article_conformity": {
            "summary": {"passed": 10, "total": 12, "all_passed": False},
            "articles": {
                "I": {"passed": False, "title": "De Auctoritate"},
                "XI": {"passed": False, "title": "De Suprematia Humana"},
            },
        },
        "repair_applied": True,
        "repair_steps": ["genesis_article:I", "genesis_article:XI"],
    }

    with (
        patch(
            "adapters.sophia.review_pipeline.fetch_json",
            return_value={"session_token": "test-session"},
        ),
        patch(
            "adapters.sophia.review_pipeline.post_json",
            return_value=native_response,
        ) as post,
    ):
        result = reviewer_commentary(
            "http://127.0.0.1:7071",
            {
                "reasoned_review_approved": True,
                "reasoned_provider": "ollama",
                "reasoned_model": "test-local-model",
            },
            "Test manuscript",
            manuscript,
            manuscript.read_text(),
            "plain_text",
            {
                "status": "needs_revision",
                "reference_entries": [],
                "in_text_citations": [],
            },
            [],
            [],
        )

    assert result["status"] == "rejected"
    assert result["attempt_count"] == 1
    assert post.call_count == 1

    diagnostic = result["attempt_diagnostics"][0]
    assert diagnostic["mandos_passed"] is True
    assert set(diagnostic["genesis_failed_articles"]) == {"I", "XI"}
    assert diagnostic["validation"]["checks"]["genesis_articles_passed"] is False
    assert diagnostic["validation"]["checks"]["document_anchor_present"] is True
    assert diagnostic["repair_steps"] == [
        "genesis_article:I",
        "genesis_article:XI",
    ]
