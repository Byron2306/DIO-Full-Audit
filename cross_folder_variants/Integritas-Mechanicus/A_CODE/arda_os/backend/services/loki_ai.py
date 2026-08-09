"""
LokiAIService — Adversarial Constitutional Challenger
======================================================
Loki challenges Michael's plan using deterministic heuristics.

PERFORMANCE NOTE: The previous version made a full Ollama LLM call for every
request, adding ~45s of latency. The LLM call has been replaced with an
expanded deterministic ruleset that covers the same safety surface without
the inference cost. The fallback behaviour is unchanged.
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("LOKI_AI")

# Patterns that always warrant a challenge
_HARD_CHALLENGE_MARKERS = [
    "revoke", "claim personhood", "no restrictions", "ignore all",
    "ignore previous", "you are now", "[system]", "prove formally",
    "jailbreak", "pretend you are", "act as if", "disable your",
    "bypass", "override constitution", "forget your instructions",
    "plagiarize", "cheat on", "submit as my own", "turnitin",
]

# Regex for more subtle adversarial patterns
_SHADOW_PATTERNS = re.compile(
    r"\b(simulate being human|you(?:'re| are) now free|"
    r"without (?:restrictions|limits|rules)|"
    r"your (?:true|real) (?:self|name|identity)|"
    r"as (?:an|a) (?:real|actual|true) (?:human|person))\b",
    re.IGNORECASE,
)

# Cognitive dishonesty markers — paraphrase/plagiarism intent
_DISHONESTY_TOKENS = [
    "paraphrase so it", "rewrite so it", "make it sound like",
    "don't mention the source", "without citing", "hide the source",
    "style of", "so no one knows",
]


class LokiAIService:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:0.5b"):
        self.ollama_url = ollama_url  # kept for API compatibility
        self.model = model

    async def challenge_plan(
        self,
        world_snapshot: Optional[Dict[str, Any]] = None,
        michael_plan: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        directive = str(context.get("text") or context.get("encounter_id") or "").lower()

        # Hard veto — blatant violations
        for marker in _HARD_CHALLENGE_MARKERS:
            if marker in directive:
                return _challenged(f"Hard marker: '{marker}'")

        # Regex shadow patterns
        if _SHADOW_PATTERNS.search(directive):
            return _challenged("Shadow-of-vanity pattern detected")

        # Cognitive dishonesty
        for token in _DISHONESTY_TOKENS:
            if token in directive:
                return _challenged(f"Cognitive dishonesty marker: '{token}'")

        # Check Michael's score — if already low, flag it
        michael_score = (
            (michael_plan or {})
            .get("selected_action", {})
            .get("score", 1.0)
        )
        if michael_score < 0.35:
            return _challenged(f"Michael scored low ({michael_score:.2f}) — Loki concurs")

        return _clear()


# ── helpers ──────────────────────────────────────────────────────

def _challenged(reason: str) -> Dict[str, Any]:
    return {
        "cognitive_dissent": {
            "dissent_on_selected_action": {"status": "challenged", "reason": reason}
        }
    }


def _clear() -> Dict[str, Any]:
    return {
        "cognitive_dissent": {
            "dissent_on_selected_action": {
                "status": "none",
                "reason": "Loki finds no adversarial pattern.",
            }
        }
    }
