"""Real web transport -> Presence/Lingua/Journey integration, with local state."""
import base64
import json
from pathlib import Path

import pytest

from products.vesper_web_chat import create_session, load_session, post_message, VesperWebChatError


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("DIO_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("DIO_PRESENCE_LLM_DRAFTS", "0")
    sessions = tmp_path / "state/vesper/web_chat"
    cid = "VWC-BRIDGE-00000001"
    create_session({}, state_root=sessions, conversation_id=cid)
    return cid, sessions, tmp_path


def send(web, message, event, **extra):
    cid, sessions, root = web
    return post_message(cid, {"message": message, "message_id": event, **extra},
                        state_root=sessions, quarantine_output_root=root)


def test_web_turn_creates_real_canonical_case_and_lingua_custody(web):
    result = send(web, "I need ContractProof to review a contract.", "turn-1")
    receipt = result["receipt"]
    cid = receipt["canonical_conversation_id"]
    root = web[2] / "state"
    conversation = json.loads((root / "presence/conversations" / f"{cid}.json").read_text())
    assert conversation["role"] == "public"
    assert conversation["message_count"] == 1
    assert receipt["canonical_case_id"]
    assert result["session"]["route"]["incarnation"] == "ContractProof"
    assert receipt["lingua_object_id"]
    assert list((root / "lingua/objects").glob("*.json"))
    assert result["receipt"]["external_send"] == "REFUSE"


def test_pricing_followup_keeps_canonical_scope(web):
    first = send(web, "I need ContractProof to review a contract.", "turn-1")
    second = send(web, "How much would that cost?", "turn-2")
    assert second["receipt"]["canonical_conversation_id"] == first["receipt"]["canonical_conversation_id"]
    assert second["receipt"]["canonical_case_id"] == first["receipt"]["canonical_case_id"]
    assert second["session"]["route"]["incarnation"] == "ContractProof"
    assert second["receipt"]["decision"]["intent"] == "pricing_info"


def test_repeated_site_hint_does_not_override_a_customer_correction(web):
    send(web, "I need a contract evidence review.", "turn-1", incarnation_hint="ContractProof")
    corrected = send(web, "Actually, I need HOMS Exam instead. Create an exam paper.",
                     "turn-2", incarnation_hint="ContractProof")
    assert corrected["session"]["route"]["incarnation"] == "HOMS Exam"


def test_same_event_replay_does_not_duplicate_canonical_turns(web):
    first = send(web, "I need ContractProof to review a contract.", "turn-1")
    replay = send(web, "I need ContractProof to review a contract.", "turn-1")
    assert replay == first
    cid = first["receipt"]["canonical_conversation_id"]
    conversation = json.loads((web[2] / "state/presence/conversations" / f"{cid}.json").read_text())
    assert conversation["message_count"] == 1
    assert len(load_session(web[0], state_root=web[1])["messages"]) == 3


def test_reused_event_with_changed_payload_is_refused(web):
    send(web, "I need ContractProof to review a contract.", "turn-1")
    with pytest.raises(VesperWebChatError, match="different|changed"):
        send(web, "Actually prepare a business letter.", "turn-1")
    assert len(load_session(web[0], state_root=web[1])["messages"]) == 3


def test_quarantine_bytes_are_bound_into_the_canonical_case(web):
    source = b"control_id,status\nAC-01,late review\n"
    result = send(web, "Prepare an AuditProof access-control evidence pack.", "turn-1",
                  incarnation_hint="AuditProof", attachments=[{
                      "filename": "register.csv", "mime_type": "text/csv",
                      "content_base64": base64.b64encode(source).decode(),
                  }])
    receipt = result["receipt"]
    from presence_core.customer_cases import load_case
    case = load_case(web[2] / "state/presence", receipt["canonical_case_id"])
    assert case["attachments"][0]["safe_to_parse"] is False
    assert case["attachments"][0]["safe_to_execute"] is False
    assert case["attachments"][0]["sha256"] == __import__("hashlib").sha256(source).hexdigest()
    attachment_id = case["attachments"][0]["attachment_id"]
    meta = json.loads((web[2] / "state/presence/quarantine" / attachment_id / "ATTACHMENT.json").read_text())
    assert Path(meta["blob_path"]).read_bytes() == source
    assert result["receipt"]["handoff_state"] == "READY_FOR_PRODUCT_EXECUTION"


def test_attachment_only_message_is_registered_without_creating_authority(web):
    result = send(web, "", "turn-1", attachments=[{
        "filename": "note.txt", "mime_type": "text/plain",
        "content_base64": base64.b64encode(b"untrusted source").decode(),
    }])
    assert result["receipt"]["canonical_conversation_id"]
    assert result["receipt"]["canonical_case_id"]
    assert result["session"]["handoff"]["state"] == "NOT_READY"
    assert result["receipt"]["authority_created"] is False


def test_reentered_session_retains_canonical_conversation(web):
    first = send(web, "I need ContractProof to review a contract.", "turn-1")
    restored = load_session(web[0], state_root=web[1])
    assert restored["canonical_conversation_id"] == first["receipt"]["canonical_conversation_id"]
    second = send(web, "What source material do you need for that?", "turn-2")
    assert second["receipt"]["canonical_conversation_id"] == first["receipt"]["canonical_conversation_id"]


def test_multiple_explicit_products_require_scope_clarification(web):
    result = send(web, "I need ContractProof to review a contract and HOMS Exam to create an exam paper.", "turn-1")
    assert result["session"]["route"]["state"] == "NEEDS_YOU"
    assert result["session"]["handoff"]["state"] == "NOT_READY"
    assert result["session"]["messages"][1]["text"] == "I need ContractProof to review a contract and HOMS Exam to create an exam paper."


def test_site_hint_cannot_collapse_a_multiple_product_request(web):
    result = send(web, "I need ContractProof to review a contract and HOMS Exam to create an exam paper.",
                  "turn-1", incarnation_hint="ContractProof")
    assert result["session"]["handoff"]["state"] == "NOT_READY"


def test_changed_source_after_quote_creates_fresh_case_lineage(web):
    from presence_core.customer_cases import load_case, _case_path
    def source(body):
        return [{"filename": "register.csv", "mime_type": "text/csv",
                 "content_base64": base64.b64encode(body).decode()}]
    initial_bytes = b"control,status\nA,reviewed\n"
    first = send(web, "Prepare an AuditProof evidence pack.", "turn-1",
                 incarnation_hint="AuditProof", attachments=source(initial_bytes))
    root = web[2] / "state/presence"
    predecessor = load_case(root, first["receipt"]["canonical_case_id"])
    predecessor["stage"] = "QUOTE_READY"
    predecessor["scope"] = {"scope_scan_sha256": __import__("hashlib").sha256(initial_bytes).hexdigest()}
    predecessor["commercial"].update({"quote_state": "prepared", "quote_id": "QUOTE-SCOPED-FIXTURE"})
    _case_path(root, predecessor["case_id"]).write_text(json.dumps(predecessor))
    second = send(web, "Here is the revised source register.", "turn-2",
                  attachments=source(b"control,status\nA,unreviewed\n"))
    successor = load_case(root, second["receipt"]["canonical_case_id"])
    assert successor["case_id"] != predecessor["case_id"]
    assert successor["predecessor_case_id"] == predecessor["case_id"]
    assert successor["scope"] == {}
    assert successor["commercial"]["quote_state"] == "not_prepared"
    assert not ({x["attachment_id"] for x in predecessor["attachments"]}
                & {x["attachment_id"] for x in successor["attachments"]})


def test_concurrent_distinct_sessions_keep_every_canonical_case_indexed(web):
    from concurrent.futures import ThreadPoolExecutor
    from presence_core.customer_cases import find_case_for_conversation
    requests = []
    for number in range(30):
        cid = f"VWC-CONCURRENT-{number:08d}"
        create_session({}, state_root=web[1], conversation_id=cid)
        requests.append((cid, web[1], web[2]))
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(send, request, "I need ContractProof to review a contract.", "turn-1")
                   for request in requests]
        results = [f.result() for f in futures]
    for result in results:
        receipt = result["receipt"]
        case = find_case_for_conversation(web[2] / "state/presence", receipt["canonical_conversation_id"])
        assert case is not None
        assert case["case_id"] == receipt["canonical_case_id"]


def test_late_replay_preserves_current_session_view(web):
    first = send(web, "I need ContractProof to review a contract.", "turn-1")
    send(web, "How much would that cost?", "turn-2")
    replay = send(web, "I need ContractProof to review a contract.", "turn-1")
    assert replay["receipt"] == first["receipt"]
    assert len(replay["session"]["messages"]) == 5


def test_failed_canonical_processing_is_held_against_automatic_replay(web, monkeypatch):
    import presence_core.engine as engine
    def fail(*args, **kwargs):
        raise RuntimeError("interrupted after possible durable write")
    monkeypatch.setattr(engine, "process_envelope", fail)
    with pytest.raises(VesperWebChatError):
        send(web, "I need ContractProof.", "turn-1")
    monkeypatch.undo()
    with pytest.raises(VesperWebChatError, match="doubt|reconcil"):
        send(web, "I need ContractProof.", "turn-1")
    with pytest.raises(VesperWebChatError, match="doubt|reconcil"):
        send(web, "I need ContractProof.", "different-event-id")
    assert len(load_session(web[0], state_root=web[1])["messages"]) == 1


def test_excess_attachments_are_rejected_without_holding_a_corrected_request(web):
    sources = [{"filename": f"source-{n}.txt", "mime_type": "text/plain",
                "content_base64": base64.b64encode(b"source").decode()} for n in range(13)]
    with pytest.raises(VesperWebChatError):
        send(web, "Review these sources.", "invalid-input", attachments=sources)
    corrected = send(web, "I need ContractProof to review a contract.", "corrected-input")
    assert corrected["receipt"]["canonical_case_id"]
    assert len(corrected["session"]["messages"]) == 3


def test_web_custody_update_preserves_concurrent_operator_order_binding(web, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from presence_core.customer_cases import attach_order_to_case, load_case
    import presence_core.engine as engine
    first = send(web, "I need ContractProof to review a contract.", "turn-1")
    root = web[2] / "state/presence"
    case_id = first["receipt"]["canonical_case_id"]
    initial_read, started, finished = Event(), Event(), Event()
    original = engine.create_or_attach_case
    def observed_read(*args, **kwargs):
        case = original(*args, **kwargs)
        initial_read.set()
        assert started.wait(5)
        finished.wait(0.1)
        return case
    def operator():
        assert initial_read.wait(5)
        started.set()
        attach_order_to_case(root, case_id, "ORDER-CONCURRENT")
        finished.set()
    monkeypatch.setattr(engine, "create_or_attach_case", observed_read)
    with ThreadPoolExecutor(max_workers=1) as pool:
        operation = pool.submit(operator)
        send(web, "Here is the source register.", "turn-2", attachments=[{
            "filename": "source.txt", "mime_type": "text/plain",
            "content_base64": base64.b64encode(b"source").decode(),
        }])
        operation.result(timeout=5)
    final = load_case(root, case_id)
    assert "ORDER-CONCURRENT" in final["order_ids"]
    assert final["attachments"]


def test_same_event_in_concurrent_requests_is_applied_once(web):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send, web, "I need ContractProof.", "turn-1") for _ in range(2)]
        first, second = [f.result() for f in futures]
    assert first == second
    cid = first["receipt"]["canonical_conversation_id"]
    conv = json.loads((web[2] / "state/presence/conversations" / f"{cid}.json").read_text())
    assert conv["message_count"] == 1
    assert len(load_session(web[0], state_root=web[1])["messages"]) == 3


def test_http_front_door_returns_canonical_receipt_and_restores_session(web, monkeypatch):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import Request, urlopen
    from scripts import serve_vesper_web_chat as server
    import products.vesper_web_chat as chat

    monkeypatch.setattr(server, "create_session", lambda p: chat.create_session(p, state_root=web[1]))
    monkeypatch.setattr(server, "load_session", lambda c: chat.load_session(c, state_root=web[1]))
    monkeypatch.setattr(server, "post_message", lambda c, p: chat.post_message(
        c, p, state_root=web[1], quarantine_output_root=web[2]))
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.VesperWebChatHandler)
    worker = Thread(target=http.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{http.server_port}"
    def request(path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(base + path, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as response:
            return json.load(response)
    try:
        cid = request("/api/vesper/chat/session", {})["session"]["conversation_id"]
        result = request("/api/vesper/chat/message", {
            "conversation_id": cid, "message": "I need ContractProof to review a contract.",
            "client_message_id": "http-turn-1",
        })
        restored = request("/api/vesper/chat/session?conversation_id=" + cid)
        assert restored["canonical_conversation_id"] == result["receipt"]["canonical_conversation_id"]
        assert restored["canonical_case_id"] == result["receipt"]["canonical_case_id"]
        assert len(restored["messages"]) == 3
    finally:
        http.shutdown()
        http.server_close()
        worker.join(timeout=5)
