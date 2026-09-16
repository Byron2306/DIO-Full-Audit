from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


SUPERSESSION_PATTERNS = (
    r"\bactually\b",
    r"\binstead\b",
    r"\brather\b",
    r"\bforget (?:that|it|the|about)\b",
    r"\bchange (?:that|topic|direction)\b",
    r"\bswitch (?:to|from)\b",
)

# Strong evidence that the substantive job itself is changing.
#
# Weak discourse markers such as "actually", "instead" and "rather"
# are deliberately excluded. They may introduce a correction inside
# the current job, such as a buyer-scope override.
HARD_SUPERSESSION_PATTERNS = (
    r"\bforget (?:that|it|the|about)\b",
    r"\bchange (?:that|topic|direction)\b",
    r"\bswitch (?:to|from)\b",
)

DEICTIC_PATTERNS = (
    r"\bthat\b",
    r"\bit\b",
    r"\bthis\b",
    r"\bthe same\b",
    r"\bthat one\b",
    r"\bthis one\b",
)

BUYER_SCOPE_PATTERNS = (
    # Individual / professional
    r"\bjust me\b",
    r"\bonly me\b",
    r"\bmyself\b",
    r"\bfor myself\b",
    r"\bby myself\b",
    r"\bon my own\b",
    r"\bindividual\b",
    r"\bsolo\b",
    r"\bnot (?:a|the|my|our) department\b",
    r"\bnot (?:a|the|my|our) team\b",

    # Team / department
    r"\bfor (?:our|my|the) department\b",
    r"\b(?:our|my|the) department\b",
    r"\bfor (?:our|my|the) team\b",
    r"\b(?:our|my|the) team\b",
    r"\bdepartment[- ]wide\b",
    r"\bteam[- ]wide\b",

    # Enterprise / programme
    r"\bcompany[- ]wide\b",
    r"\borganisation[- ]wide\b",
    r"\borganization[- ]wide\b",
    r"\benterprise[- ]wide\b",
    r"\bfor the whole company\b",
    r"\bfor our whole company\b",
    r"\bwhole organisation\b",
    r"\bwhole organization\b",
    r"\benterprise programme\b",
    r"\benterprise program\b",
)

PRICING_PATTERNS = (
    r"\bhow much\b",
    r"\bwhat (?:would|does|will) (?:that|it|this) cost\b",
    r"\bwhat do i pay(?: for (?:that|it|this))?\b",
    r"\bhow much do i pay(?: for (?:that|it|this))?\b",
    r"\bwhat (?:is|would be) the price\b",
    r"\band (?:what about )?the price\b",
    r"\bwhat(?:'s| is) the cost\b",
    r"\bprice(?: for (?:that|it|this))?\b",
)

FOLLOWUP_PATTERNS = (
    r"\bhow much\b",
    r"\bwhat (?:would|does|will) (?:that|it|this) cost\b",
    r"\bwhat about the price\b",
    r"\bwhat would the price be\b",
    r"\bwhat happens next\b",
    r"\bwhat would happen next\b",
    r"\bcan you explain that\b",
    r"\btell me more about that\b",
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _matches_any(text: str, patterns: Sequence[str]) -> list[str]:
    low = text.casefold()
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, low)
    ]


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "sha256:" + hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def resolve_conversation_semantics(
    *,
    text: str,
    conversation_state: Mapping[str, Any] | None,
    recent_turns: Sequence[Mapping[str, Any]] | None,
    interaction: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve bounded conversation continuity before commercial cognition.

    Lingua may preserve semantic continuity and resolve conversational
    references. It does not create product, pricing, identity, payment,
    execution, send, fulfilment or release authority.
    """

    state = dict(conversation_state or {})
    turns = list(recent_turns or [])
    interaction = dict(interaction or {})
    signals = interaction.get("signals") or {}

    active_product = _clean(state.get("selected_product")) or None

    supersession_hits = _matches_any(
        text,
        SUPERSESSION_PATTERNS,
    )
    hard_supersession_hits = _matches_any(
        text,
        HARD_SUPERSESSION_PATTERNS,
    )
    deictic_hits = _matches_any(
        text,
        DEICTIC_PATTERNS,
    )
    buyer_scope_hits = _matches_any(
        text,
        BUYER_SCOPE_PATTERNS,
    )
    followup_hits = _matches_any(
        text,
        FOLLOWUP_PATTERNS,
    )

    pricing_hits = _matches_any(
        text,
        PRICING_PATTERNS,
    )

    interaction_price_signal = bool(
        (
            signals.get("price_objection")
            or {}
        ).get("detected")
    )

    price_signal = bool(
        interaction_price_signal
        or pricing_hits
    )

    word_count = len(re.findall(r"\S+", text))
    short_question = (
        "?" in text
        and word_count <= 14
    )

    relation = "UNRESOLVED"
    speech_act = "UNRESOLVED"
    retain_active_referent = False
    supersedes_previous = False
    semantic_basis: list[str] = []

    if hard_supersession_hits:
        relation = "SUPERSESSION"
        speech_act = "NEW_SUBSTANTIVE_JOB"
        supersedes_previous = True
        semantic_basis.append(
            "explicit_hard_supersession_language"
        )

    elif active_product and buyer_scope_hits:
        relation = "CONTINUATION"
        speech_act = "BUYER_SCOPE_REFINEMENT"
        retain_active_referent = True
        semantic_basis.append(
            "buyer_scope_refinement"
        )

        if supersession_hits:
            semantic_basis.append(
                "scope_correction_over_soft_supersession_marker"
            )

    elif supersession_hits:
        relation = "SUPERSESSION"
        speech_act = "NEW_SUBSTANTIVE_JOB"
        supersedes_previous = True
        semantic_basis.append(
            "explicit_supersession_language"
        )

    elif (
        active_product
        and price_signal
        and (
            deictic_hits
            or followup_hits
            or short_question
        )
    ):
        relation = "CONTINUATION"
        speech_act = "PRICING_FOLLOWUP"
        retain_active_referent = True
        semantic_basis.append("price_signal")
        semantic_basis.append("active_product_referent")

    elif (
        active_product
        and followup_hits
    ):
        relation = "CONTINUATION"
        speech_act = "GENERAL_FOLLOWUP"
        retain_active_referent = True
        semantic_basis.append("explicit_followup_language")

    discourse_payload = {
        "relation": relation,
        "speech_act": speech_act,
        "active_product": (
            active_product
            if retain_active_referent
            else None
        ),
        "supersedes_previous": supersedes_previous,
        "candidate_products": [
            _clean(value)
            for value in (
                state.get("candidate_products")
                or []
            )
            if _clean(value)
        ],
        "current_need": _clean(
            state.get("current_need")
        ) or None,
        "current_topic": _clean(
            state.get("current_topic")
        ) or None,
        "open_question": _clean(
            state.get("open_question")
        ) or None,
        "known_constraints": [
            _clean(value)
            for value in (
                state.get("known_constraints")
                or []
            )
            if _clean(value)
        ],
        "recent_turn_count": len(turns),
    }

    return {
        "schema": "dio.lingua.semantic_continuity.v1",
        "relation": relation,
        "speech_act": speech_act,
        "active_referent": (
            {
                "kind": "product",
                "value": active_product,
            }
            if retain_active_referent
            and active_product
            else None
        ),
        "retain_active_referent": (
            retain_active_referent
        ),
        "supersedes_previous": (
            supersedes_previous
        ),
        "new_job_evidence": bool(
            supersedes_previous
        ),
        "evidence": {
            "supersession_patterns": (
                supersession_hits
            ),
            "hard_supersession_patterns": (
                hard_supersession_hits
            ),
            "deictic_patterns": deictic_hits,
            "buyer_scope_patterns": (
                buyer_scope_hits
            ),
            "followup_patterns": followup_hits,
            "pricing_patterns": pricing_hits,
            "interaction_price_signal":
                interaction_price_signal,
            "price_signal": price_signal,
            "short_question": short_question,
        },
        "semantic_basis": semantic_basis,
        "discourse": discourse_payload,
        "discourse_digest": _digest(
            discourse_payload
        ),
        "authority_created": False,
        "external_effects": False,
        "truth_boundary": (
            "Lingua resolves bounded conversational "
            "continuity only. It does not create "
            "commercial, execution, identity, payment, "
            "send, fulfilment or release authority."
        ),
    }
