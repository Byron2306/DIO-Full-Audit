from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

BEAST_CODE_ROOT = (
    REPO_ROOT
    / "cross_folder_variants"
    / "EdgeK-BEAST"
    / "A_CODE"
)

PUBLIC_REGISTRY = (
    "vesper_public_semantic_crystals.jsonl"
)

OPERATOR_REGISTRY = (
    "vesper_operator_semantic_crystals.jsonl"
)


def _beast_api():
    if not BEAST_CODE_ROOT.exists():
        return None

    if str(BEAST_CODE_ROOT) not in sys.path:
        sys.path.insert(
            0,
            str(BEAST_CODE_ROOT),
        )

    try:
        from app.kernel.compute.operator_language import (
            realize_answer_frame,
        )
        from app.kernel.compute.semantic_generalizer import (
            SemanticCrystalLifecycleState,
            SemanticCrystalRegistry,
            SemanticGeneralizer,
        )
    except Exception:
        return None

    return {
        "realize_answer_frame":
            realize_answer_frame,
        "SemanticCrystalLifecycleState":
            SemanticCrystalLifecycleState,
        "SemanticCrystalRegistry":
            SemanticCrystalRegistry,
        "SemanticGeneralizer":
            SemanticGeneralizer,
    }


def registry_path_for_role(
    *,
    root: Path,
    role: str,
) -> Path:
    role = str(role or "").strip().casefold()

    if role == "operator":
        filename = OPERATOR_REGISTRY
    elif role == "public":
        filename = PUBLIC_REGISTRY
    else:
        raise ValueError(
            "semantic crystal role must be "
            "public or operator"
        )

    return (
        Path(root)
        / "state"
        / "lingua"
        / filename
    )


def resolve_conversation_crystal(
    *,
    root: Path,
    text: str,
    role: str,
    semantic_context: Mapping[str, Any],
    registry_path: Path | None = None,
    tone: str = "concise",
) -> dict[str, Any] | None:
    """Replay a semantic crystal against CURRENT context.

    Applicability fields MUST come from semantic_context,
    which was constructed from the current request.

    No applicability digest may be copied from a stored
    candidate crystal.

    Public and operator crystal registries are isolated.
    Semantic reuse never creates authority.
    """

    api = _beast_api()

    if api is None:
        return None

    role = str(role or "").strip().casefold()

    if role not in {
        "public",
        "operator",
    }:
        return None

    if not isinstance(
        semantic_context,
        Mapping,
    ):
        return None

    expected_domain = (
        "vesper_operator"
        if role == "operator"
        else "vesper_public"
    )

    if (
        semantic_context.get(
            "semantic_domain"
        )
        != expected_domain
    ):
        return None

    request_key = semantic_context.get(
        "reuse_key"
    )

    if request_key is None:
        return None

    path = (
        Path(registry_path)
        if registry_path is not None
        else registry_path_for_role(
            root=root,
            role=role,
        )
    )

    if not path.exists():
        return None

    try:
        registry = api[
            "SemanticCrystalRegistry"
        ](path)

        registry.load()

        generalizer = api[
            "SemanticGeneralizer"
        ]()

        active_state = api[
            "SemanticCrystalLifecycleState"
        ].ACTIVE

        for record in registry.records():
            if (
                record.lifecycle_state
                is not active_state
            ):
                continue

            outcome = (
                generalizer.replay_record(
                    record,
                    request_key,
                    provider_enabled=False,
                )
            )

            if (
                not outcome.reused
                or outcome.answer_frame
                    is None
                or outcome.provider_called
            ):
                continue

            realized = api[
                "realize_answer_frame"
            ](
                outcome.answer_frame,
                tone=tone,
            ).strip()

            if not realized:
                continue

            return {
                "schema":
                    "dio.vesper."
                    "conversation_crystal_reuse.v2",
                "reply": realized,
                "source": "lingua_crystal",
                "semantic_domain":
                    expected_domain,
                "crystal_id":
                    record.crystal.crystal_id,
                "semantic_match_digest":
                    semantic_context.get(
                        "semantic_match_digest"
                    ),
                "reuse_receipt_digest":
                    outcome.receipt_digest,
                "provider_called": False,
                "authority_created": False,
                "external_effects": False,
                "context_source":
                    "CURRENT_REQUEST_ONLY",
            }

    except Exception:
        return None

    return None
