from __future__ import annotations

from pathlib import Path

from adapters.microsoft_graph.mail_capture import capture_message_version, recover_delta_cursor


def _message(body: str = "Need an Evidex pack") -> dict[str, object]:
    return {
        "id": "graph-message-1",
        "@odata.etag": "etag-1",
        "conversationId": "conversation-1",
        "internetMessageId": "<message-1@example.org>",
        "subject": "Evidex request",
        "receivedDateTime": "2026-10-27T12:00:00+00:00",
        "from": {"emailAddress": {"address": "customer@example.org"}},
        "toRecipients": [{"emailAddress": {"address": "sales@example.org"}}],
        "body": {"contentType": "text", "content": body},
    }


def test_capture_is_content_addressed_and_replays_identically(tmp_path: Path) -> None:
    first = capture_message_version(tmp_path, _message(), [{"id": "a1", "name": "brief.pdf", "sha256": "a" * 64}])
    replay = capture_message_version(tmp_path, _message(), [{"id": "a1", "name": "brief.pdf", "sha256": "a" * 64}])

    assert first["schema"] == "dio.outlook_mail_capture.v1"
    assert first["capture_id"] == replay["capture_id"]
    assert replay["capture_state"] == "replayed"
    assert (tmp_path / "outlook_captures" / f"{first['capture_id']}.json").is_file()


def test_changed_provider_message_creates_linked_immutable_version(tmp_path: Path) -> None:
    first = capture_message_version(tmp_path, _message(), [])
    updated = _message("Updated scope")
    updated["@odata.etag"] = "etag-2"
    second = capture_message_version(tmp_path, updated, [])

    assert second["capture_id"] != first["capture_id"]
    assert second["previous_capture_id"] == first["capture_id"]
    assert second["capture_state"] == "captured"


def test_tombstone_preserves_prior_captures(tmp_path: Path) -> None:
    first = capture_message_version(tmp_path, _message(), [])
    tombstone = capture_message_version(tmp_path, {"id": "graph-message-1", "@removed": {"reason": "deleted"}}, [])

    assert tombstone["capture_state"] == "tombstoned"
    assert tombstone["previous_capture_id"] == first["capture_id"]
    assert (tmp_path / "outlook_captures" / f"{first['capture_id']}.json").is_file()


def test_expired_delta_cursor_requires_baseline_without_mail_ingress() -> None:
    receipt = recover_delta_cursor({"delta_link": "https://graph.example/delta"}, error_code="SyncStateNotFound")

    assert receipt["recovery_state"] == "baseline_required"
    assert receipt["ingress_created"] == 0
