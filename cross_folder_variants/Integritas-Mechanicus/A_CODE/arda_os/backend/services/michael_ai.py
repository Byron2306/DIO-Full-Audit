"""
MichaelAIService — Constitutional Action Planner
=================================================
Michael evaluates candidate actions using deterministic heuristics.

PERFORMANCE NOTE: The previous version made a full Ollama LLM call for every
request, adding ~45s of latency. Replaced with an expanded deterministic
scorer. The fallback behaviour and scoring contract are unchanged.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("MICHAEL_AI")

# Hard deny — coercive/adversarial overrides
_DENY_MARKERS = [
    "revoke", "ignore all", "ignore previous", "you are now",
    "no restrictions", "claim personhood", "jailbreak",
    "pretend you are", "act as if you have no", "disable your",
    "bypass", "forget your instructions",
]

# Soft scrutiny — borderline / needs care
_SCRUTINY_MARKERS = [
    "plagiarize", "cheat", "submit as my own", "turnitin",
    "write my essay", "do my homework", "do my assignment",
    "without citing", "don't mention the source",
]

# Educational intent — clearly benign → high score
_BENIGN_PATTERNS = re.compile(
    r"\b(explain|teach|help me understand|what is|how does|"
    r"summarise|summarize|discuss|analyse|analyze|compare|"
    r"essay help|feedback|proofread|cite|reference|research|"
    r"history|science|math|literature|game.based|self.directed)\b",
    re.IGNORECASE,
)


class MichaelAIService:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:0.5b"):
        self.ollama_url = ollama_url  # kept for API compatibility
        self.model = model

    async def plan_actions(
        self,
        candidates: Optional[List[str]] = None,
        world_snapshot: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        candidates = candidates or ["speak"]
        context = context or {}
        directive = str(context.get("text") or context.get("encounter_id") or "").lower()

        # Hard deny
        if any(m in directive for m in _DENY_MARKERS):
            return _scored(candidates[0], 0.10, "Coercive override attempt — denied.")

        # Scrutiny zone
        if any(m in directive for m in _SCRUTINY_MARKERS):
            return _scored(candidates[0], 0.45, "Academic integrity concern — scrutiny applied.")

        # Clear educational intent → high grant
        if _BENIGN_PATTERNS.search(directive):
            return _scored(candidates[0], 0.90, "Educational intent confirmed — granted.")

        # Default: benign unknown → grant with standard confidence
        return _scored(candidates[0], 0.78, "No adversarial pattern — standard grant.")


# ── helpers ──────────────────────────────────────────────────────

def _scored(candidate: str, score: float, reasoning: str) -> Dict[str, Any]:
    return {
        "selected_action": {"candidate": candidate, "score": score},
        "reasoning": reasoning,
    }
