from pathlib import Path

from presence_core.commercial_cognition import (
    resolve_commercial_cognition,
)


ROOT = Path("/srv/dio/presence")


def resolved_name(text: str) -> str | None:
    result = resolve_commercial_cognition(
        ROOT,
        text,
    )
    return (
        (result.get("product") or {})
        .get("name")
    )


def test_contractproof_spoken_form_resolves():
    assert resolved_name(
        "What is contract proof?"
    ) == "ContractProof"


def test_contractproof_compact_form_resolves():
    assert resolved_name(
        "What is ContractProof?"
    ) == "ContractProof"


def test_projectproof_spoken_form_does_not_steal_contractproof():
    assert resolved_name(
        "Give me a one sentence description of contract proof."
    ) == "ContractProof"


def test_projectproof_spoken_form_resolves():
    assert resolved_name(
        "What is project proof?"
    ) == "ProjectProof"


def test_grantproof_spoken_form_resolves():
    assert resolved_name(
        "What is grant proof?"
    ) == "GrantProof"
