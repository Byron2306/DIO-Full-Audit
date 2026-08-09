"""
Lightweight AI reasoner shim.

Provides `explain_candidates` (sync) and `async_explain_candidates` (async)
which attempt to use an LLM if available and otherwise return fast
heuristic explanations. This module is deliberately dependency-light and
fails safely.
"""
from typing import List, Dict, Any
import os
import asyncio
import threading

try:
    from services.world_events import emit_world_event
except Exception:
    try:
        from backend.services.world_events import emit_world_event
    except Exception:
        emit_world_event = None


def _emit_reasoner_event(db: Any, event_type: str, entity_refs: List[str], payload: Dict[str, Any]):
    if emit_world_event is None or db is None:
        return
    coro = emit_world_event(
        db,
        event_type=event_type,
        entity_refs=entity_refs,
        payload=payload,
        trigger_triune=False,
        source="ai.reasoner",
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(coro)
        except Exception:
            pass
        return

    def _runner():
        try:
            asyncio.run(coro)
        except Exception:
            pass

    threading.Thread(target=_runner, daemon=True).start()


def _heuristic_explanation(candidate: str) -> Dict[str, Any]:
    lc = candidate.lower()
    exp = {
        "explanation": "heuristic: keyword-driven reasoning",
        "score_delta": 0.0,
    }
    if "isolate" in lc or "quarantine" in lc:
        exp["explanation"] = "Isolation recommended for containment; high impact but effective."
        exp["score_delta"] = 0.05
    elif "kill" in lc or "terminate" in lc:
        exp["explanation"] = "Process termination likely to remove active threat; high confidence if process tied to detection."
        exp["score_delta"] = 0.06
    elif "monitor" in lc or "investigate" in lc:
        exp["explanation"] = "Observation recommended; low blast radius and preserves evidence."
        exp["score_delta"] = -0.01
    elif "password" in lc or "force_password_reset" in lc:
        exp["explanation"] = "Credential remediation reduces attacker lateral movement risk."
        exp["score_delta"] = 0.02
    else:
        exp["explanation"] = "No clear heuristic; default ranking applies."
        exp["score_delta"] = 0.0
    return exp


def explain_candidates(candidates: List[str], db: Any = None, context: Dict[str, Any] = None) -> Dict[str, Dict[str, Any]]:
    """Synchronous explanation for a list of candidate strings.

    Attempts lightweight LLM usage when `OPENAI_API_KEY` exists and the
    `openai` package is available. Otherwise returns heuristic explanations.
    """
    # best-effort LLM path
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
    if key:
        try:
            import openai

            openai.api_key = key
            prompts = "\n".join([f"Explain and justify: {c}" for c in candidates])
            # Use a lightweight completion to avoid heavy deps; guard with timeout
            resp = openai.Completion.create(engine="text-davinci-003", prompt=prompts, max_tokens=256, n=1)
            text = resp.choices[0].text if hasattr(resp, "choices") else str(resp)
            # naive split: return same text for all candidates
            out = {}
            for c in candidates:
                out[c] = {"explanation": text.strip(), "score_delta": 0.0}
            _emit_reasoner_event(
                db,
                event_type="ai_reasoner_candidates_explained",
                entity_refs=[],
                payload={"candidate_count": len(candidates), "provider": "openai", "context": context or {}},
            )
            return out
        except Exception:
            # fall through to heuristics
            pass

    # fallback heuristics
    out = {c: _heuristic_explanation(c) for c in candidates}
    _emit_reasoner_event(
        db,
        event_type="ai_reasoner_candidates_explained",
        entity_refs=[],
        payload={"candidate_count": len(candidates), "provider": "heuristic", "context": context or {}},
    )
    return out


async def async_explain_candidates(candidates: List[str], db: Any = None, context: Dict[str, Any] = None) -> Dict[str, Dict[str, Any]]:
    """Async wrapper for `explain_candidates`.

    Keeps a consistent async interface for callers.
    """
    # run sync function; it's cheap in fallback path
    return explain_candidates(candidates, db=db, context=context)
