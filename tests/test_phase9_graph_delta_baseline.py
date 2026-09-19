from pathlib import Path
import pytest
import scripts.sync_outlook_mail as outlook


class Graph:
    def __init__(self):
        self.calls = 0

    def json(self, method, resource, **kwargs):
        assert method == "GET"
        self.calls += 1
        if self.calls == 1:
            return {
                "value": [{"id": "old-1"}, {"id": "old-2"}],
                "@odata.nextLink": "page-2",
            }
        return {
            "value": [
                {"id": "old-3"},
                {"id": "gone", "@removed": {}},
            ],
            "@odata.deltaLink": "fresh-delta",
        }


def test_baseline_archives_and_creates_no_ingress(tmp_path: Path):
    delta = tmp_path / "microsoft_graph" / "mail_delta.json"
    delta.parent.mkdir(parents=True)

    outlook.write_json(delta, {
        "schema": "dio.graph_delta_state.v1",
        "updated_at": "old",
        "delta_link": "expired-delta",
    })

    receipt = outlook.establish_delta_baseline(Graph(), delta)

    assert outlook.read_json(delta)["delta_link"] == "fresh-delta"
    assert receipt["pages_observed"] == 2
    assert receipt["provider_objects_observed"] == 4
    assert receipt["provider_removed_observed"] == 1
    assert receipt["ingress_created"] == 0
    assert receipt["attachments_captured"] == 0
    assert receipt["mail_received_events_emitted"] == 0

    archive = Path(receipt["previous_state_archive"])
    assert archive.exists()
    assert outlook.read_json(archive)["delta_link"] == "expired-delta"


def test_baseline_refuses_without_terminal_cursor(tmp_path: Path):
    class BrokenGraph:
        def json(self, method, resource, **kwargs):
            assert method == "GET"
            return {"value": [{"id": "old"}]}

    delta = tmp_path / "mail_delta.json"

    with pytest.raises(RuntimeError, match="GRAPH_BASELINE_REFUSED"):
        outlook.establish_delta_baseline(BrokenGraph(), delta)

    assert not delta.exists()


def test_sparse_delta_message_is_hydrated_before_ingress(tmp_path):
    import json
    import scripts.sync_outlook_mail as sync

    message_id = "GRAPH-SPARSE-MESSAGE-1"
    delta_url = "https://graph.microsoft.com/v1.0/delta-final"

    class FakeGraph:
        def __init__(self):
            self.calls = []

        def json(self, method, resource, **kwargs):
            self.calls.append((method, resource))

            if resource.startswith("/me/mailFolders/inbox/messages/delta"):
                return {
                    "value": [{"id": message_id}],
                    "@odata.deltaLink": delta_url,
                }

            if resource.startswith(f"/me/messages/{message_id}"):
                return {
                    "id": message_id,
                    "conversationId": "conversation-1",
                    "internetMessageId": "<proof@example.test>",
                    "subject": "DIO Phase 9 sparse delta proof",
                    "from": {
                        "emailAddress": {
                            "name": "Proof Sender",
                            "address": "proof@example.test",
                        }
                    },
                    "toRecipients": [],
                    "receivedDateTime": "2026-09-19T18:57:13Z",
                    "isRead": False,
                    "hasAttachments": False,
                    "bodyPreview": "Test",
                    "body": {
                        "contentType": "text",
                        "content": "Test",
                    },
                }

            raise AssertionError(f"unexpected Graph request: {method} {resource}")

    ingress = tmp_path / "mail_ingress"
    delta = tmp_path / "microsoft_graph" / "mail_delta.json"
    events = tmp_path / "telemetry" / "dio_events.jsonl"

    receipt = sync.pull_messages(
        FakeGraph(),
        ingress,
        delta,
        events,
    )

    assert receipt["received"] == [{
        "mail_ingress_id": sync.ingress_id(message_id),
        "state": "created",
    }]

    record = json.loads(
        (ingress / f"{sync.ingress_id(message_id)}.json").read_text()
    )

    assert record["provider"] == "microsoft_graph"
    assert record["provider_message_id"] == message_id
    assert record["subject"] == "DIO Phase 9 sparse delta proof"
    assert record["received_at"] == "2026-09-19T18:57:13Z"
    assert record["sender"]["address"] == "proof@example.test"
    assert record["conversation_id"] == "conversation-1"
    assert record["internet_message_id"] == "<proof@example.test>"
