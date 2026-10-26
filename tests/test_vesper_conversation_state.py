from presence_core.state import (
    append_conversation_turn,
    load_conversation_state,
    load_recent_conversation_turns,
    save_conversation_state,
)


def test_conversation_state_defaults_have_no_authority(tmp_path):
    state = load_conversation_state(tmp_path, "CONV-123")
    assert state["schema"] == "dio.vesper.conversation_state.v1"
    assert state["conversation_id"] == "CONV-123"
    assert state["turn_count"] == 0
    assert state["candidate_products"] == []
    assert state["selected_product"] is None
    assert "authority" not in state
    assert "authorized" not in state


def test_recent_turns_are_bounded(tmp_path):
    for index in range(9):
        append_conversation_turn(
            tmp_path,
            "CONV-123",
            role="user" if index % 2 == 0 else "vesper",
            text=f"turn-{index}",
            max_turns=6,
        )
    turns = load_recent_conversation_turns(tmp_path, "CONV-123")
    assert [row["text"] for row in turns] == [f"turn-{i}" for i in range(3, 9)]


def test_save_state_rejects_wrong_schema_or_conversation(tmp_path):
    state = load_conversation_state(tmp_path, "CONV-123")
    state["schema"] = "wrong"
    try:
        save_conversation_state(tmp_path, state)
    except ValueError as exc:
        assert "schema" in str(exc)
    else:
        raise AssertionError("wrong schema must fail closed")
