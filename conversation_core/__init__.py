"""Cross-channel DIO conversation context primitives.

Conversation context may shape expression and response ordering. It is never a source
of commercial truth or execution authority by itself.
"""

from .context import (
    SCHEMA as CONVERSATION_CONTEXT_SCHEMA,
    assert_valid_conversation_context,
    build_conversation_context,
    expression_context_view,
    validate_conversation_context,
    write_conversation_context,
)
from .outlook import build_outlook_conversation_context
from .presence import (
    append_presence_turn,
    build_presence_conversation_context,
    load_presence_turns,
)

__all__ = [
    "CONVERSATION_CONTEXT_SCHEMA",
    "append_presence_turn",
    "assert_valid_conversation_context",
    "build_conversation_context",
    "build_outlook_conversation_context",
    "build_presence_conversation_context",
    "expression_context_view",
    "load_presence_turns",
    "validate_conversation_context",
    "write_conversation_context",
]
