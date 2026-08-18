from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HOSTILITY_TERMS = {
    "fuck", "fucking", "shit", "bullshit", "useless", "idiot", "stupid", "ridiculous",
    "angry", "furious", "pissed", "terrible", "awful", "pathetic", "scam", "fraud",
}
COMPLAINT_PATTERNS = (
    "not working", "doesn't work", "does not work", "still broken", "you charged", "charged me",
    "no response", "nobody replied", "still waiting", "where is my", "i want a refund", "cancel this",
)
CONFUSION_PATTERNS = (
    "i don't understand", "i dont understand", "what does that mean", "what do you mean", "i'm confused",
    "im confused", "this makes no sense", "explain that", "can you explain", "how does this work",
)
URGENCY_PATTERNS = (
    "urgent", "asap", "right now", "immediately", "today", "before close", "deadline", "by tomorrow",
    "within the hour", "this morning", "this afternoon",
)
SKEPTICISM_PATTERNS = (
    "prove it", "show me proof", "why should i trust", "i don't trust", "i dont trust", "is this a scam",
    "sounds like a scam", "too good to be true", "what evidence", "how do i know", "is this real",
)
PRICE_PATTERNS = (
    "too expensive", "expensive", "price", "pricing", "cost", "budget", "can't afford", "cant afford",
    "cheaper", "discount",
)
POSITIVE_PATTERNS = (
    "sounds good", "that works", "great", "perfect", "tell me more", "interested", "let's do it", "lets do it",
    "yes please", "sign me up",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contains_any(text: str, patterns: tuple[str, ...] | set[str]) -> list[str]:
    low = text.casefold()
    return sorted({pattern for pattern in patterns if pattern in low})


def _all_caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def _hostility_score(text: str) -> tuple[float, list[str]]:
    low = text.casefold()
    words = re.findall(r"[a-zA-Z']+", low)
    matched = sorted({word for word in words if word in HOSTILITY_TERMS})
    score = min(1.0, len(matched) * 0.22)
    caps = _all_caps_ratio(text)
    if len(text) >= 12 and caps >= 0.65:
        score += 0.22
        matched.append("high_all_caps_ratio")
    bangs = text.count("!")
    if bangs >= 3:
        score += min(0.18, bangs * 0.03)
        matched.append("repeated_exclamation")
    direct_attack = bool(re.search(r"\b(you|your)\s+(are|re|sound|look)\s+(useless|stupid|idiot|pathetic|terrible)\b", low))
    if direct_attack:
        score += 0.28
        matched.append("direct_attack_phrase")
    return min(1.0, round(score, 3)), sorted(set(matched))


def _delivery_policy(signals: dict[str, Any]) -> dict[str, Any]:
    hostility = float(signals["hostility"]["score"])
    complaint = bool(signals["complaint"]["detected"])
    confusion = bool(signals["confusion"]["detected"])
    urgency = bool(signals["urgency"]["detected"])
    skepticism = bool(signals["skepticism"]["detected"])
    price = bool(signals["price_objection"]["detected"])

    policy: dict[str, Any] = {
        "mode": "warm_professional",
        "sales_pressure_allowed": True,
        "humour_allowed": True,
        "jargon_level": "normal",
        "proof_priority": "normal",
        "max_sentences": 5,
        "ask_at_most_one_question": False,
        "single_next_action": False,
        "acknowledge_without_emotion_claim": False,
        "mirror_profanity": False,
        "voice": {
            "pace": "normal",
            "piper_length_scale": 1.0,
            "expressiveness": "medium",
        },
        "avoid": ["invented_emotion_labels", "false_urgency", "pressure_after_refusal"],
    }

    if hostility >= 0.35 or complaint:
        policy.update({
            "mode": "calm_service_recovery",
            "sales_pressure_allowed": False,
            "humour_allowed": False,
            "jargon_level": "low",
            "proof_priority": "high",
            "max_sentences": 3,
            "ask_at_most_one_question": True,
            "single_next_action": True,
            "acknowledge_without_emotion_claim": True,
            "avoid": [
                "invented_emotion_labels", "upsell", "cross_sell", "scarcity_pressure", "mirrored_hostility",
                "defensiveness", "false_urgency", "pressure_after_refusal",
            ],
            "voice": {"pace": "slower", "piper_length_scale": 1.08, "expressiveness": "low"},
        })
        return policy

    if confusion:
        policy.update({
            "mode": "clarify_gently",
            "sales_pressure_allowed": False,
            "humour_allowed": False,
            "jargon_level": "low",
            "max_sentences": 4,
            "ask_at_most_one_question": True,
            "single_next_action": True,
            "voice": {"pace": "slower", "piper_length_scale": 1.06, "expressiveness": "low"},
        })
        return policy

    if skepticism:
        policy.update({
            "mode": "proof_first",
            "sales_pressure_allowed": True,
            "humour_allowed": False,
            "proof_priority": "high",
            "max_sentences": 5,
            "ask_at_most_one_question": True,
            "voice": {"pace": "measured", "piper_length_scale": 1.03, "expressiveness": "low"},
        })

    if price:
        policy["mode"] = "transparent_value" if policy["mode"] == "warm_professional" else policy["mode"]
        policy["proof_priority"] = "high"
        policy["avoid"] = sorted(set(policy["avoid"] + ["hidden_pricing", "invented_discount", "pressure_discounting"]))

    if urgency:
        policy["mode"] = "direct_action" if policy["mode"] == "warm_professional" else policy["mode"]
        policy["max_sentences"] = min(int(policy["max_sentences"]), 4)
        policy["single_next_action"] = True
        policy["voice"] = {"pace": "normal", "piper_length_scale": 0.98, "expressiveness": "low"}
        policy["avoid"] = sorted(set(policy["avoid"] + ["delivery_promise", "deadline_promise_without_evidence"]))

    return policy


def observe_interaction(
    *,
    state_root: Path,
    conversation_id: str,
    text: str,
    channel: str,
    role: str,
    source_message_id: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Observe explicit linguistic cues and derive bounded delivery regulation.

    This deliberately does not diagnose emotion, mental state, personality, vulnerability or intent
    beyond observable textual interaction cues. The result can regulate presentation only; it does
    not create product, pricing, send, payment, fulfilment or publication authority.
    """
    text = str(text or "")
    hostility_score, hostility_evidence = _hostility_score(text)
    complaint = _contains_any(text, COMPLAINT_PATTERNS)
    confusion = _contains_any(text, CONFUSION_PATTERNS)
    urgency = _contains_any(text, URGENCY_PATTERNS)
    skepticism = _contains_any(text, SKEPTICISM_PATTERNS)
    price = _contains_any(text, PRICE_PATTERNS)
    positive = _contains_any(text, POSITIVE_PATTERNS)
    word_count = len(re.findall(r"\S+", text))

    signals = {
        "hostility": {"score": hostility_score, "evidence": hostility_evidence},
        "complaint": {"detected": bool(complaint), "evidence": complaint},
        "confusion": {"detected": bool(confusion), "evidence": confusion},
        "urgency": {"detected": bool(urgency), "evidence": urgency},
        "skepticism": {"detected": bool(skepticism), "evidence": skepticism},
        "price_objection": {"detected": bool(price), "evidence": price},
        "positive_engagement": {"detected": bool(positive), "evidence": positive},
        "message_shape": {
            "word_count": word_count,
            "question_marks": text.count("?"),
            "exclamation_marks": text.count("!"),
            "all_caps_ratio": round(_all_caps_ratio(text), 3),
        },
    }
    policy = _delivery_policy(signals)
    observation_id = "LINGUA-INTERACTION-" + _digest(
        "|".join([conversation_id, source_message_id or "", channel, role, text])
    )[:20].upper()
    receipt = {
        "schema": "dio.lingua.interaction_observation.v1",
        "observation_id": observation_id,
        "observed_at": _now(),
        "conversation_id": conversation_id,
        "source_message_id": source_message_id,
        "channel": channel,
        "role": role,
        "text_sha256": _digest(text),
        "signals": signals,
        "delivery_policy": policy,
        "persona_identity_locked": True,
        "avatar_profile_mutation_allowed": False,
        "voice_identity_mutation_allowed": False,
        "delivery_parameter_adaptation_allowed": True,
        "sales_learning_eligible": role == "public",
        "external_action_authorized": False,
        "emotion_diagnosed": False,
        "personality_diagnosed": False,
        "vulnerability_inferred": False,
        "truth_boundary": (
            "This receipt records observable language cues and bounded presentation policy only. "
            "It does not claim the person's emotion, personality, mental state, vulnerability or purchase intent."
        ),
    }
    if persist:
        target = Path(state_root) / "interaction_observations" / conversation_id / f"{observation_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        receipt["receipt_path"] = str(target)
    return receipt


def llm_style_instruction(observation: dict[str, Any] | None) -> str:
    if not observation:
        return "Use the default warm professional Vesper delivery style."
    policy = observation.get("delivery_policy") or {}
    avoid = ", ".join(str(x) for x in policy.get("avoid") or [])
    return (
        f"Delivery mode: {policy.get('mode','warm_professional')}. "
        f"Sales pressure allowed: {bool(policy.get('sales_pressure_allowed', True))}. "
        f"Humour allowed: {bool(policy.get('humour_allowed', True))}. "
        f"Jargon level: {policy.get('jargon_level','normal')}. "
        f"Proof priority: {policy.get('proof_priority','normal')}. "
        f"Maximum sentences: {int(policy.get('max_sentences',5))}. "
        f"Single next action: {bool(policy.get('single_next_action', False))}. "
        f"Never diagnose the user's emotion or personality. Do not mirror profanity. Avoid: {avoid or 'none'}.")
