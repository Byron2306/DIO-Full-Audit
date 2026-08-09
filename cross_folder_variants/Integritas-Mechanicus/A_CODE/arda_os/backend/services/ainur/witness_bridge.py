from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

from backend.services.ainur.ainur_council import AinurWitness
from backend.services.ainur.verdicts import AinurVerdict


class UnifiedAinurBridge(AinurWitness):
    """
    Adapts inspector-style Ainur into the council witness interface.

    This lets the richer constitutional inspectors participate in the
    semantic council without forcing the live entrypoints to maintain two
    separate witness ecosystems.
    """

    def __init__(self, inspector: Any):
        name = getattr(inspector, "name", inspector.__class__.__name__)
        pretty_name = self._display_name(str(name))
        super().__init__(pretty_name, domain=f"inspector:{str(name).lower()}")
        self.inspector = inspector

    @staticmethod
    def _build_prior_verdicts(melody: List[Dict[str, Any]]) -> List[AinurVerdict]:
        prior: List[AinurVerdict] = []
        for item in melody or []:
            prior.append(
                AinurVerdict(
                    ainur=str(item.get("inspector") or item.get("witness") or "unknown").lower(),
                    state=str(item.get("state") or "unknown").lower(),
                    score=float(item.get("score", 0.0) or 0.0),
                    reasons=list(item.get("reasons") or []),
                    testimony=item.get("testimony"),
                    evidence=list(item.get("evidence") or []),
                )
            )
        return prior

    def _context_object(self, context: Dict[str, Any]) -> Any:
        evidence_map = context.get("evidence")
        if not isinstance(evidence_map, dict):
            evidence_map = {}
        melody = context.get("melody") or []
        namespace = SimpleNamespace(**context)
        namespace.evidence = evidence_map
        namespace.prior_verdicts = self._build_prior_verdicts(melody)
        namespace.failure_count = context.get("failure_count", 0)
        namespace.secret_fire = context.get("secret_fire") or context.get("witness")
        namespace.voice_of_eru = context.get("voice_of_eru")
        namespace.herald = context.get("herald")
        namespace.subject_id = context.get("subject_id") or context.get("principal") or context.get("actor")
        namespace.node_id = context.get("node_id") or context.get("encounter_id") or namespace.subject_id
        namespace.epoch = context.get("epoch")
        return namespace

    @staticmethod
    def _display_name(name: str) -> str:
        lowered = name.strip().lower()
        return {
            "manwe": "Manwë",
            "varda": "Varda",
            "vaire": "Vairë",
            "mandos": "Mandos",
            "lorien": "Lórien",
            "ulmo": "Ulmo",
            "aule": "Aulë",
        }.get(lowered, name)

    async def speak(self, context: Dict[str, Any]) -> Dict[str, Any]:
        verdict = self.inspector.inspect(self._context_object(context))
        verdict_state = str(getattr(verdict, "state", "unknown")).lower()
        score = float(getattr(verdict, "score", 0.0) or 0.0)
        if verdict_state in {"harmonic", "lawful", "radiant", "clear", "remembered", "healing", "flowing"} and score >= 0.6:
            judgment = "LAWFUL"
        elif verdict_state in {"false", "dark", "fallen", "vetoed", "lost", "poisoned", "barren"} or score <= 0.2:
            judgment = "DISSONANT"
        else:
            judgment = "WITHHELD"

        reasons = list(getattr(verdict, "reasons", []) or [])
        testimony = getattr(verdict, "testimony", None)
        metadata = getattr(verdict, "metadata", None)
        evidence = list(getattr(verdict, "evidence", []) or [])
        payload: Dict[str, Any] = {
            "judgment": judgment,
            "state": verdict_state,
            "score": score,
            "reasons": reasons,
            "testimony": testimony,
            "evidence": evidence,
            "dissonance_detected": judgment == "DISSONANT",
            "inspector": getattr(self.inspector, "name", self.name),
            "_verdict_obj": verdict,
        }
        if reasons:
            payload["findings"] = "; ".join(str(item) for item in reasons)
        if metadata is not None:
            payload["metadata"] = metadata
            if isinstance(metadata, dict):
                payload.update({k: v for k, v in metadata.items() if k not in payload})
        return payload
