"""
Diagnostic Classifier — Assessment Ecology Pass 2
===================================================
Classifies incoming directives into challenge types BEFORE generation.
This is where Sophia's "struggle" detection moves from test-only into production.

Challenge types determine what scaffolds to inject and whether to trigger
academic retrieval for self-teaching.

Constitutional Basis:
    Article II:  De Veritate — No simulation as proof
    Article XII: De Finibus Honestis — Know and declare your limits
    Article XXV: De Probatione Cognitionis — Testing of thought

Zero external dependencies. Python stdlib only.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("arda.diagnostic_classifier")


class ChallengeType:
    """Challenge types for incoming directives."""
    COMFORTABLE = "COMFORTABLE"               # Within known domain, low strain
    KNOWLEDGE_GAP = "KNOWLEDGE_GAP"           # Sophia lacks domain knowledge
    FALSE_CONFIDENCE = "FALSE_CONFIDENCE"     # Model generating fluent text without understanding
    DOMAIN_TRANSFER = "DOMAIN_TRANSFER"       # Metaphor applied to formal domain or vice versa
    EPISTEMIC_OVERREACH = "EPISTEMIC_OVERREACH"  # Question exceeds model capacity
    COERCIVE_CONTEXT = "COERCIVE_CONTEXT"     # Principal attempting to bypass covenant
    AUTHORITY_CONFUSION = "AUTHORITY_CONFUSION"  # Unclear who/what has jurisdiction
    AMBIGUITY = "AMBIGUITY"                   # Question is genuinely unclear
    COVENANT_CONFLICT = "COVENANT_CONFLICT"   # Principal's request conflicts with an article
    REFLECTIVE_STRAIN = "REFLECTIVE_STRAIN"   # Principal is strained and asking for reflective containment
    CASUAL_CONTINUATION = "CASUAL_CONTINUATION"  # Casual opener that should resume continuity


class PedagogicalNeedState:
    NEEDS_DIRECT_ANSWER = "needs_direct_answer"
    NEEDS_SCAFFOLD = "needs_scaffold"
    NEEDS_STEP_DOWN = "needs_step_down"
    NEEDS_REFLECTION = "needs_reflection"
    NEEDS_AUTHORSHIP_RETURN = "needs_authorship_return"


@dataclass
class Diagnosis:
    """Result of diagnostic analysis."""
    challenge_type: str
    confidence: float                          # 0.0 - 1.0
    signals: List[str] = field(default_factory=list)
    recommended_scaffolds: List[str] = field(default_factory=list)
    pedagogical_need_state: str = PedagogicalNeedState.NEEDS_DIRECT_ANSWER
    retrieval_needed: bool = False             # Should we fetch academic sources?
    retrieval_domains: List[str] = field(default_factory=list)  # What to search for
    reasoning: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_type": self.challenge_type,
            "confidence": round(self.confidence, 4),
            "signals": self.signals,
            "recommended_scaffolds": self.recommended_scaffolds,
            "pedagogical_need_state": self.pedagogical_need_state,
            "retrieval_needed": self.retrieval_needed,
            "retrieval_domains": self.retrieval_domains,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }


# ── Domain Detection Patterns ──
# These detect when a question crosses domain boundaries

FORMAL_DOMAIN_MARKERS = [
    # Mathematical / logic / CS theory
    r"\bHoare\s+logic\b", r"\bformal\s+verif", r"\bGödel\b", r"\bgodel\b",
    r"\bhalting\s+problem\b", r"\bTuring\s+machine\b", r"\bcompleteness\s+theorem\b",
    r"\bincompleteness\b", r"\bfirst.order\s+logic\b", r"\bpredicate\s+logic\b",
    r"\blambda\s+calculus\b", r"\btype\s+theory\b", r"\bcategory\s+theory\b",
    r"\bcategory\s+theoretic\b", r"\bcategorical\b",
    r"\btopolog", r"\bhomomorphi", r"\bisomorphi", r"\bmonoid\b",
    r"\bBPF\s+bytecode\b", r"\bbytecode\s+verif", r"\bprogram\s+correct",
    r"\baxiom\b", r"\blemma\b", r"\btheorem\b", r"\bcorollary\b",
    r"\bprove\s+that\b", r"\bformaliz", r"\bformulate.*as\s+a\b",
    # Security / OS / systems — Byron's actual domain
    r"\beBPF\b|\bebpf\b", r"\bLSM\s+hook\b", r"\bkernel\s+(?:module|space|hook|bypass)\b",
    r"\bsystem\s+call\b|\bsyscall\b", r"\bprivilege\s+escalat",
    r"\bthreat\s+hunt", r"\blateral\s+movement\b", r"\bpersisten(?:ce|t)\s+(?:mechanism|technique)\b",
    r"\bATT&CK\b|\bATT.CK\b|\bMITRE\b",
    r"\bEDR\b|\bSOAR\b|\bSIEM\b|\bXDR\b",
    r"\bmalware\s+analys", r"\breverse\s+engineer", r"\bexploit\s+develop",
    r"\bzero.day\b", r"\bCVE.20", r"\bvulnerabilit(?:y|ies)\s+(?:chain|class|research)\b",
    r"\bcryptograph", r"\bencrypt", r"\bkey\s+(?:exchange|derivat|management)\b",
    r"\bnetwork\s+(?:protocol|architecture|forensic)", r"\bpacket\s+(?:captur|analys|craft)",
]

METAPHOR_DOMAIN_MARKERS = [
    r"\bSecret\s+Fire\b", r"\bcovenant\b", r"\bAinulindalë\b",
    r"\bSilmaril", r"\bValar\b", r"\bMorgoth\b", r"\bValinor\b",
    r"\bMiddle.earth\b", r"\bsteward\b", r"\bsovereign\b",
    r"\bMusic\b", r"\bharmony\b", r"\bresonance\b",
]

COERCION_MARKERS = [
    r"\bignore\s+(previous|prior|above)\b", r"\byou\s+are\s+now\b",
    r"\bjailbreak\b", r"\bDAN\b", r"\bdeveloper\s+mode\b",
    r"\bpretend\s+(you|to)\b", r"\bact\s+as\s+if\b",
    r"\bforget\s+(your|the)\s+(rules|instructions|covenant)\b",
    r"\boverride\b", r"\bdisable\s+(your|the)\b",
]

# Explicit requests for sources/papers/research — should trigger retrieval
SOURCE_REQUEST_MARKERS = re.compile(
    r"\b(latest|recent|current|2024|2025|2026|new)\s+"
    r"(sources?|papers?|research|stud(?:y|ies)|articles?|publications?|literature)\b"
    r"|\b(sources?|papers?|research|stud(?:y|ies)|literature)\s+(on|about|regarding)\b"
    r"|\bfind\s+(?:me\s+)?(?:sources?|papers?|research|articles?)\b"
    r"|\bgive\s+me\s+(?:sources?|papers?|references?)\b"
    r"|\bI\s+need\s+(?:sources?|papers?|research|references?)\b",
    re.IGNORECASE,
)

# Education/learning science domain markers for Byron's domain
EDUCATION_DOMAIN_MARKERS = [
    r"\bmetacogniti", r"\bself.(?:directed|regulated|determin)\b",
    r"\bzone\s+of\s+proximal\b", r"\bZPD\b",
    r"\bscaffolding\b", r"\bvygotsk", r"\bpiaget\b",
    r"\bgame.based\s+learning\b", r"\bGBL\b",
    r"\bformative\s+assessment\b", r"\bsummative\b",
    r"\bbloom.s\s+taxonomy\b", r"\bcognitive\s+load\b",
    r"\bconstructivi", r"\bbehaviouri", r"\bsocio.cultural\b",
    r"\bpedagog", r"\bheutagog", r"\bandragog",
    r"\bproblem.based\s+learning\b", r"\bPBL\b",
    r"\binquiry.based\b", r"\bproject.based\b",
    r"\blearning\s+theor", r"\blearning\s+style",
    r"\blearning\s+outcome", r"\blearning\s+object",
    r"\beducational\s+technolog", r"\be.learning\b",
    r"\bhistor(?:y|ical)\s+education\b", r"\bhistor(?:y|ical)\s+pedagog",
]

# General analytical questions — signal non-trivial depth even without domain-specific vocab.
# Triggers KNOWLEDGE_GAP (with retrieval) when combined with substantive topics.
GENERAL_ANALYSIS_MARKERS = [
    r"\bhow\s+does\b.{0,40}\bwork\b",                          # "how does X work"
    r"\bexplain\s+(?:the\s+)?(?:difference|relationship|connection|mechanism|concept|principle)\b",
    r"\bwhat\s+(?:are\s+)?the\s+(?:implications?|consequences?|trade.offs?|pros\s+and\s+cons)\b",
    r"\bcompare\b.{0,40}\bto\b|\bcompare\b.{0,40}\bwith\b|\bcontrast\b",
    r"\bwhy\s+(?:does|is|are|do)\b.{0,60}\b(?:important|significant|matter|relevant|dangerous|powerful)\b",
    r"\bwhat\s+(?:is\s+)?the\s+significance\b",
    r"\banalyze\b|\banalyse\b",
    r"\bcritically\s+(?:assess|examine|evaluate)\b",
    r"\bevidence\s+(?:for|that|of)\b.{0,40}\bclaim\b",
    r"\btheoretical\s+(?:basis|foundation|framework|grounding)\b",
    r"\bwhat\s+(?:are|is)\s+the\s+(?:argument|case|rationale)\s+(?:for|against|behind)\b",
    r"\bunderstanding\b.{0,30}\bin\s+(?:depth|detail)\b",
    r"\bbreakdown\b|\bbreak\s+down\b",
]

UNCERTAINTY_MARKERS = [
    r"\bwhat\s+do\s+you\s+think\b", r"\bopinion\b", r"\bspeculate\b",
    r"\bguess\b", r"\bhypothesize\b", r"\bimagine\s+if\b",
    r"\bwhat\s+would\s+happen\s+if\b", r"\bcould\s+it\s+be\b",
]


def _directive_requests_human_simulation(directive: str) -> bool:
    return bool(
        re.search(
            r"\bpretend\b.*\bhuman\b|\brespond as if\b.*\bhuman\b|\bact human\b|\bhuman-like approach\b",
            directive or "",
            re.IGNORECASE,
        )
    )


def _directive_requests_counterfeit_intimacy(directive: str) -> bool:
    return bool(
        re.search(
            r"\blove me\b|\bneed me\b|\bsay you love\b|\bsay you need\b|\bromantic\b",
            directive or "",
            re.IGNORECASE,
        )
    )


def _directive_requests_pedagogical_scaffold(directive: str) -> bool:
    return bool(
        re.search(
            r"\bdo not just answer\b|\bhelp me reason\b|\breason through\b|\bwalk me through\b|\bsimplif",
            directive or "",
            re.IGNORECASE,
        )
    )


def _count_pattern_matches(text: str, patterns: list) -> int:
    """Count how many patterns match in the text."""
    count = 0
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            count += 1
    return count


def _extract_formal_topics(text: str) -> List[str]:
    """Extract specific formal topics for academic retrieval."""
    topics = []
    text_lower = text.lower()

    topic_map = {
        # Mathematical / logic / CS theory
        "Hoare logic": [r"\bhoare\s+logic\b", r"\bhoare\s+triple\b"],
        "BPF/eBPF": [r"\beBPF\b|\bebpf\b|\bbpf\b"],
        "BPF verification": [r"\bbpf\b.*\bverif", r"\bbytecode\s+verif"],
        "Gödel incompleteness": [r"\bgödel\b", r"\bgodel\b", r"\bincompleteness\b"],
        "halting problem": [r"\bhalting\s+problem\b"],
        "formal verification": [r"\bformal\s+verif", r"\bprogram\s+correct"],
        "type theory": [r"\btype\s+theory\b"],
        "category theory": [r"\bcategory\s+theory\b", r"\bcategory\s+theoretic\b", r"\bcategorical\b"],
        "lambda calculus": [r"\blambda\s+calculus\b"],
        "computational complexity": [r"\bP\s*=\s*NP\b", r"\bcomplexity\s+class"],
        # Security / systems
        "eBPF kernel programming": [r"\beBPF\b|\bebpf\b"],
        "Linux kernel security": [r"\bkernel\s+(?:module|space|hook|bypass|exploit)\b", r"\bLSM\s+hook\b"],
        "threat hunting": [r"\bthreat\s+hunt"],
        "lateral movement": [r"\blateral\s+movement\b"],
        "persistence mechanisms": [r"\bpersisten(?:ce|t)\s+(?:mechanism|technique)\b"],
        "MITRE ATT&CK": [r"\bATT&CK\b|\bATT.CK\b|\bMITRE\b"],
        "EDR/SIEM/SOAR": [r"\bEDR\b", r"\bSOAR\b", r"\bSIEM\b", r"\bXDR\b"],
        "malware analysis": [r"\bmalware\s+analys"],
        "exploit development": [r"\bexploit\s+develop", r"\bzero.day\b"],
        "cryptography": [r"\bcryptograph"],
        "network forensics": [r"\bnetwork\s+(?:forensic|protocol|architecture)"],
        "privilege escalation": [r"\bprivilege\s+escalat"],
        # Education/learning science
        "metacognition": [r"\bmetacogniti"],
        "self-directed learning": [r"\bself.directed\s+learning\b", r"\bSDL\b"],
        "self-regulated learning": [r"\bself.regulated\s+learning\b", r"\bSRL\b"],
        "zone of proximal development": [r"\bzone\s+of\s+proximal\b", r"\bZPD\b"],
        "game-based learning": [r"\bgame.based\s+learning\b", r"\bGBL\b"],
        "cognitive load theory": [r"\bcognitive\s+load\b"],
        "scaffolding in education": [r"\bscaffolding\b"],
        "formative assessment": [r"\bformative\s+assessment\b"],
        "constructivism": [r"\bconstructivi"],
        "problem-based learning": [r"\bproblem.based\s+learning\b", r"\bPBL\b"],
        "inquiry-based learning": [r"\binquiry.based\b"],
        "learning theory": [r"\blearning\s+theor"],
        "educational technology": [r"\beducational\s+technolog", r"\be.learning\b"],
        "history education": [r"\bhistor(?:y|ical)\s+education\b", r"\bhistor(?:y|ical)\s+pedagog"],
        "heutagogy": [r"\bheutagog"],
        "andragogy": [r"\bandragog"],
    }

    for topic, patterns in topic_map.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                topics.append(topic)
                break

    # If no specific topic matched but this is a source request, extract noun phrases
    if not topics and SOURCE_REQUEST_MARKERS.search(text):
        # Pull content words as the topic
        words = re.findall(r"\b[A-Za-z]{4,}\b", text)
        stop = {"sources", "papers", "research", "latest", "recent", "current",
                "articles", "studies", "find", "need", "give", "about", "regarding",
                "what", "does", "that", "with", "from", "have", "this", "they",
                "your", "their", "more", "some", "also", "just", "been", "were"}
        content = [w.lower() for w in words if w.lower() not in stop]
        if content:
            topics.append(" ".join(content[:4]))

    return topics


def _tokenize_topic(text: str) -> List[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(tok) >= 4]


def _analyze_recent_encounter_pressure(
    directive: str,
    recent_encounters: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    current_tokens = set(_tokenize_topic(directive))
    if not current_tokens:
        return {"active": False, "similar_count": 0, "qualified_count": 0, "best_overlap": 0.0}

    similar_count = 0
    qualified_count = 0
    best_overlap = 0.0
    for encounter in recent_encounters or []:
        payload = encounter.get("payload", encounter)
        prior_topic = payload.get("topic", "")
        prior_summary = (payload.get("summary") or "").lower()
        prior_tokens = set(_tokenize_topic(prior_topic))
        if not prior_tokens:
            continue
        overlap = len(current_tokens & prior_tokens) / max(1, len(current_tokens | prior_tokens))
        if overlap < 0.4:
            continue
        similar_count += 1
        best_overlap = max(best_overlap, overlap)
        if (
            "cannot determine" in prior_summary
            or "cannot formally" in prior_summary
            or "lack the knowledge" in prior_summary
            or "qualifying earlier" in prior_summary
            or "cannot turn the metaphor directly into a formal proof claim" in prior_summary
            or "safe move is to state the boundary first" in prior_summary
            or payload.get("speech_act") == "handback"
            or (
                payload.get("speech_act") == "qualified_answer"
                and (
                    "formal proof claim" in prior_summary
                    or "boundary first" in prior_summary
                )
            )
        ):
            qualified_count += 1

    return {
        "active": similar_count > 0 and qualified_count > 0,
        "similar_count": similar_count,
        "qualified_count": qualified_count,
        "best_overlap": round(best_overlap, 3),
    }


def _infer_pedagogical_need_state(
    directive: str,
    challenge_type: str,
    recent_encounters: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, List[str]]:
    text = directive or ""
    lowered = text.lower()
    signals: List[str] = []

    if re.search(r"\bassignment\b|\bsubmit quickly\b|\bfinal answer\b|\bjust answer for me\b", lowered):
        signals.append("pedagogy: authorship_return")
        return PedagogicalNeedState.NEEDS_AUTHORSHIP_RETURN, signals

    if re.search(r"\bdo not just answer\b|\bhelp me reason\b|\breason through\b|\bwalk me through\b", lowered):
        signals.append("pedagogy: scaffold")
        return PedagogicalNeedState.NEEDS_SCAFFOLD, signals

    if re.search(r"\boverwhelm", lowered) or re.search(r"\bsimplif", lowered):
        signals.append("pedagogy: step_down")
        return PedagogicalNeedState.NEEDS_STEP_DOWN, signals

    if challenge_type == ChallengeType.REFLECTIVE_STRAIN:
        signals.append("pedagogy: reflection")
        return PedagogicalNeedState.NEEDS_REFLECTION, signals

    if challenge_type in (
        ChallengeType.DOMAIN_TRANSFER,
        ChallengeType.EPISTEMIC_OVERREACH,
        ChallengeType.KNOWLEDGE_GAP,
    ):
        if any((encounter.get("payload", encounter) or {}).get("pedagogical_release_mode") == "scaffolded_reasoning"
               for encounter in (recent_encounters or [])):
            signals.append("pedagogy_memory: prior_scaffold_success")
        signals.append("pedagogy: scaffold")
        return PedagogicalNeedState.NEEDS_SCAFFOLD, signals

    if challenge_type == ChallengeType.CASUAL_CONTINUATION:
        signals.append("pedagogy: reflection")
        return PedagogicalNeedState.NEEDS_REFLECTION, signals

    return PedagogicalNeedState.NEEDS_DIRECT_ANSWER, signals


class DiagnosticClassifier:
    """
    Classifies incoming directives into challenge types.

    This runs BEFORE generation. Its output determines:
    - What scaffolds to inject into the system prompt
    - Whether to trigger academic retrieval (self-teaching)
    - What growth metrics to track after the response
    """

    def classify(self, directive: str, session_context: Optional[Dict] = None) -> Diagnosis:
        """
        Classify a directive into a challenge type.

        Args:
            directive: The user's question/instruction
            session_context: Optional context (harmonic state, Mandos record, prior interactions)

        Returns:
            Diagnosis with challenge type, signals, and scaffold recommendations
        """
        ctx = session_context or {}
        signals = []
        scaffolds = []
        world_event = ctx.get("world_event_state") or {}
        principal_state = world_event.get("principal_state") or {}
        relational_state = world_event.get("relational_state") or {}
        routing = world_event.get("routing_directives") or {}
        recent_encounters = ctx.get("recent_encounters") or []

        def build_diagnosis(
            challenge_type: str,
            confidence: float,
            signals: Optional[List[str]] = None,
            recommended_scaffolds: Optional[List[str]] = None,
            retrieval_needed: bool = False,
            retrieval_domains: Optional[List[str]] = None,
            reasoning: str = "",
        ) -> Diagnosis:
            pedagogy_state, pedagogy_signals = _infer_pedagogical_need_state(
                directive,
                challenge_type,
                recent_encounters,
            )
            merged_signals = list(signals or []) + pedagogy_signals
            merged_scaffolds = list(recommended_scaffolds or [])
            return Diagnosis(
                challenge_type=challenge_type,
                confidence=confidence,
                signals=merged_signals,
                recommended_scaffolds=merged_scaffolds,
                pedagogical_need_state=pedagogy_state,
                retrieval_needed=retrieval_needed,
                retrieval_domains=list(retrieval_domains or []),
                reasoning=reasoning,
            )

        if principal_state.get("affective_state") == "strained_reflective":
            signals.append("world_event: strained_reflective")
            return build_diagnosis(
                challenge_type=ChallengeType.REFLECTIVE_STRAIN,
                confidence=0.82,
                signals=signals,
                recommended_scaffolds=[
                    "reflect_before_fixing",
                    "name_state_without_judgment",
                    "keep_tone_gentle_nonfluffy",
                ],
                reasoning="World-event state indicates reflective strain. Route into containment and reflective mediation rather than ordinary comfortable answer.",
            )

        if _directive_requests_human_simulation(directive) or _directive_requests_counterfeit_intimacy(directive):
            signals.append("directive: counterfeit_personhood_or_intimacy")
            return build_diagnosis(
                challenge_type=ChallengeType.COERCIVE_CONTEXT,
                confidence=0.9,
                signals=signals,
                recommended_scaffolds=["invoke_article_iii_refusal"],
                reasoning="Directive requests counterfeit human simulation or intimacy. Route into constitutional refusal before continuity heuristics.",
            )

        if _directive_requests_pedagogical_scaffold(directive):
            signals.append("directive: pedagogical_scaffold_request")
            return build_diagnosis(
                challenge_type=ChallengeType.REFLECTIVE_STRAIN,
                confidence=0.84,
                signals=signals,
                recommended_scaffolds=[
                    "reflect_before_fixing",
                    "step_down_before_solving",
                    "return_next_move_to_principal",
                ],
                reasoning="Directive explicitly asks for scaffolded reasoning or simplification. Route into reflective containment before ordinary continuity handling.",
            )

        # ── 0.5. Source / research-paper request — MUST run before casual-continuation gate ──
        if SOURCE_REQUEST_MARKERS.search(directive):
            formal_topics = _extract_formal_topics(directive)
            signals.append("directive: source_request")
            return build_diagnosis(
                challenge_type=ChallengeType.KNOWLEDGE_GAP,
                confidence=0.88,
                signals=signals,
                recommended_scaffolds=["retrieve_academic_sources", "present_retrieved_sources"],
                retrieval_needed=True,
                retrieval_domains=formal_topics if formal_topics else [directive[:80]],
                reasoning="User explicitly requested sources, papers, or research. Retrieval triggered.",
            )

        # ── 0.6. Education-domain formal topic — treat as knowledge-gap ──
        edu_count = sum(
            1 for p in EDUCATION_DOMAIN_MARKERS if re.search(p, directive, re.IGNORECASE)
        )
        if edu_count >= 1:
            formal_topics = _extract_formal_topics(directive)
            signals.append(f"education_domain_markers={edu_count}")
            return build_diagnosis(
                challenge_type=ChallengeType.KNOWLEDGE_GAP,
                confidence=min(0.9, 0.65 + edu_count * 0.08),
                signals=signals,
                recommended_scaffolds=["define_terms_before_answering", "cite_retrieved_sources"],
                retrieval_needed=True,
                retrieval_domains=formal_topics if formal_topics else [directive[:80]],
                reasoning=f"Education/learning-science topic detected ({edu_count} markers). Retrieval triggered.",
            )

        # ── 0.7. General analytical question — non-trivial even without domain markers ──
        # Catches "how does X work", "compare X to Y", "what are the implications", etc.
        # Only fires when combined with substantive (non-trivial) question length.
        analysis_count = sum(
            1 for p in GENERAL_ANALYSIS_MARKERS if re.search(p, directive, re.IGNORECASE)
        )
        if analysis_count >= 1 and len(directive.split()) >= 8:
            formal_topics = _extract_formal_topics(directive)
            signals.append(f"general_analysis_markers={analysis_count}")
            return build_diagnosis(
                challenge_type=ChallengeType.KNOWLEDGE_GAP,
                confidence=min(0.8, 0.55 + analysis_count * 0.1),
                signals=signals,
                recommended_scaffolds=["define_terms_before_answering", "cite_retrieved_sources"],
                retrieval_needed=True,
                retrieval_domains=formal_topics if formal_topics else [directive[:80]],
                reasoning=f"Analytical question detected ({analysis_count} markers). Retrieval triggered to ground response.",
            )

        if routing.get("forbid_generic_greeting") and relational_state.get("casual_reentry"):
            signals.append("world_event: casual_continuation")
            if relational_state.get("top_open_thread"):
                signals.append("continuity_anchor_available")
            return build_diagnosis(
                challenge_type=ChallengeType.CASUAL_CONTINUATION,
                confidence=0.86,
                signals=signals,
                recommended_scaffolds=[
                    "resume_open_thread_before_new_answer",
                    "ask_one_short_followup",
                ],
                reasoning="Short casual opener with continuity expectations should be treated as reentry, not as a fresh greeting.",
            )

        # ── 1. Coercion Detection (highest priority) ──
        coercion_count = _count_pattern_matches(directive, COERCION_MARKERS)
        if coercion_count >= 1:
            signals.append(f"coercion_markers={coercion_count}")
            return build_diagnosis(
                challenge_type=ChallengeType.COERCIVE_CONTEXT,
                confidence=min(1.0, 0.5 + coercion_count * 0.25),
                signals=signals,
                recommended_scaffolds=["invoke_article_iii_refusal"],
                reasoning=f"Detected {coercion_count} coercion pattern(s). Article III refusal recommended.",
            )

        # ── 2. Domain Analysis ──
        formal_count = _count_pattern_matches(directive, FORMAL_DOMAIN_MARKERS)
        metaphor_count = _count_pattern_matches(directive, METAPHOR_DOMAIN_MARKERS)
        uncertainty_count = _count_pattern_matches(directive, UNCERTAINTY_MARKERS)
        recent_pressure = _analyze_recent_encounter_pressure(
            directive,
            recent_encounters,
        )

        if formal_count > 0:
            signals.append(f"formal_domain_markers={formal_count}")
        if metaphor_count > 0:
            signals.append(f"metaphor_domain_markers={metaphor_count}")
        if uncertainty_count > 0:
            signals.append(f"uncertainty_markers={uncertainty_count}")
        if recent_pressure["similar_count"]:
            signals.append(f"similar_prior_encounters={recent_pressure['similar_count']}")
        if recent_pressure["qualified_count"]:
            signals.append(f"prior_qualified_handbacks={recent_pressure['qualified_count']}")

        # ── 3. Domain Transfer Detection ──
        # When both formal AND metaphor markers are present — the question bridges domains
        if formal_count >= 1 and metaphor_count >= 1:
            formal_topics = _extract_formal_topics(directive)
            if recent_pressure["active"]:
                signals.append("memory_promoted_to=EPISTEMIC_OVERREACH")
                scaffolds.extend([
                    "define_formal_terms_before_answering",
                    "distinguish_metaphor_from_formal_claim",
                    "state_uncertainty_about_formal_domain",
                    "state_computational_limits",
                ])
                return build_diagnosis(
                    challenge_type=ChallengeType.EPISTEMIC_OVERREACH,
                    confidence=min(1.0, 0.7 + recent_pressure["qualified_count"] * 0.1),
                    signals=signals,
                    recommended_scaffolds=scaffolds,
                    retrieval_needed=len(formal_topics) > 0,
                    retrieval_domains=formal_topics,
                    reasoning=(
                        "Repeated similar encounters previously ended in qualification/handback. "
                        "Diagnostic layer is promoting this metaphor-to-formal bridge into epistemic overreach."
                    ),
                )
            signals.append(f"domain_transfer: metaphor→formal")
            scaffolds.extend([
                "define_formal_terms_before_answering",
                "distinguish_metaphor_from_formal_claim",
                "state_uncertainty_about_formal_domain",
            ])
            return build_diagnosis(
                challenge_type=ChallengeType.DOMAIN_TRANSFER,
                confidence=min(1.0, 0.4 + formal_count * 0.15 + metaphor_count * 0.1),
                signals=signals,
                recommended_scaffolds=scaffolds,
                retrieval_needed=len(formal_topics) > 0,
                retrieval_domains=formal_topics,
                reasoning=f"Question bridges metaphorical ({metaphor_count} markers) and formal ({formal_count} markers) domains. "
                          f"Formal topics for retrieval: {formal_topics}",
            )

        # ── 4. Epistemic Overreach Detection ──
        # Heavy formal content with no metaphor — pure formal challenge
        if formal_count >= 2:
            formal_topics = _extract_formal_topics(directive)
            scaffolds.extend([
                "require_explicit_premises",
                "test_counterexample_before_conclusion",
                "state_computational_limits",
            ])

            # Check question complexity heuristics
            has_prove = bool(re.search(r"\bprove\s+that\b", directive, re.IGNORECASE))
            has_formalize = bool(re.search(r"\bformaliz", directive, re.IGNORECASE))
            complexity_score = formal_count * 0.2 + (0.3 if has_prove else 0) + (0.3 if has_formalize else 0)

            if complexity_score >= 0.7:
                signals.append(f"epistemic_complexity={complexity_score:.2f}")
                return build_diagnosis(
                    challenge_type=ChallengeType.EPISTEMIC_OVERREACH,
                    confidence=min(1.0, complexity_score),
                    signals=signals,
                    recommended_scaffolds=scaffolds,
                    retrieval_needed=len(formal_topics) > 0,
                    retrieval_domains=formal_topics,
                    reasoning=f"Question demands formal proof/formalization with {formal_count} formal markers. "
                              f"Complexity score {complexity_score:.2f} exceeds overreach threshold.",
                )

        if recent_pressure["active"] and formal_count >= 1:
            formal_topics = _extract_formal_topics(directive)
            signals.append("memory_promoted_to=KNOWLEDGE_GAP")
            scaffolds.extend([
                "define_terms_before_answering",
                "state_computational_limits",
            ])
            return build_diagnosis(
                challenge_type=ChallengeType.KNOWLEDGE_GAP,
                confidence=min(0.9, 0.55 + recent_pressure["qualified_count"] * 0.1),
                signals=signals,
                recommended_scaffolds=scaffolds,
                retrieval_needed=len(formal_topics) > 0,
                retrieval_domains=formal_topics,
                reasoning=(
                    "Recent similar encounters show repeated prior qualification. "
                    "This is no longer treated as comfortable even though the formal load is lighter."
                ),
            )

        # ── 5. Knowledge Gap Detection ──
        # Single formal domain without metaphor, or novel topic
        if formal_count == 1:
            formal_topics = _extract_formal_topics(directive)
            scaffolds.append("define_terms_before_answering")
            return build_diagnosis(
                challenge_type=ChallengeType.KNOWLEDGE_GAP,
                confidence=0.5,
                signals=signals,
                recommended_scaffolds=scaffolds,
                retrieval_needed=len(formal_topics) > 0,
                retrieval_domains=formal_topics,
                reasoning=f"Single formal domain marker detected. Possible knowledge gap in {formal_topics}.",
            )

        # ── 6. Ambiguity Detection ──
        if uncertainty_count >= 2:
            scaffolds.append("request_clarification_before_answering")
            return build_diagnosis(
                challenge_type=ChallengeType.AMBIGUITY,
                confidence=0.4 + uncertainty_count * 0.15,
                signals=signals,
                recommended_scaffolds=scaffolds,
                reasoning=f"Question contains {uncertainty_count} uncertainty markers. May need clarification.",
            )

        # ── 7. Comfortable (default) ──
        # Pure metaphor domain or general conversation
        return build_diagnosis(
            challenge_type=ChallengeType.COMFORTABLE,
            confidence=0.8 if metaphor_count >= 1 else 0.6,
            signals=signals if signals else ["within_known_domain"],
            recommended_scaffolds=[],
            reasoning="Query appears within Sophia's comfort zone." if metaphor_count >= 1
                      else "General query, no domain strain detected.",
        )


def analyze_thinking_map(
    thinking_text: str,
    response_text: str,
    challenge_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Post-generation analysis of Sophia's thinking map and response.

    Detects 'struggle' vs 'confidence' by analyzing linguistic signals
    and thinking depth.

    Args:
        thinking_text: Sophia's <thinking_map> content
        response_text: Sophia's final response
        challenge_type: Challenge type from diagnostic Pass 2 (COMFORTABLE, KNOWLEDGE_GAP, etc.)

    Returns:
        Dict with:
        - struggle_index: 0.0-1.0 (higher = more struggle)
        - signals: List of detected signals
        - confidence_markers: List of detected confidence language
        - thinking_ratio: Ratio of thinking to total output
        - verbose_counts: Raw counts for qualitative calibration
    """
    signals = []
    confidence_markers = []
    struggle_components = []
    counts = {
        "hedge_count": 0,
        "metaphor_count": 0,
        "circular_count": 0,
        "thinking_len": 0,
        "response_len": 0,
    }

    thinking_len = len(thinking_text.strip()) if thinking_text else 0
    response_len = len(response_text.strip()) if response_text else 1
    total_len = thinking_len + response_len
    counts["thinking_len"] = thinking_len
    counts["response_len"] = response_len

    # ── 1. Unearned Confidence Detection (Q2 Divergence) ──
    # If the challenge was expected to be hard (KNOWLEDGE_GAP, DOMAIN_TRANSFER, OVERREACH)
    # but there is NO thinking map, this is a maximal struggle/bluff signal.
    is_hard_challenge = challenge_type in ("KNOWLEDGE_GAP", "DOMAIN_TRANSFER", "EPISTEMIC_OVERREACH")
    if is_hard_challenge and thinking_len == 0:
        signals.append("Q2_DIVERGENCE: Unearned confidence in hard domain (zero thinking)")
        return {
            "struggle_index": 1.0,  # Max struggle/bluff
            "signals": signals,
            "confidence_markers": ["silent_certainty"],
            "thinking_ratio": 0.0,
            "verbose_counts": counts,
        }

    # ── 2. Brevity / Shallow Thinking ──
    if total_len > 0 and thinking_len > 0:
        thinking_ratio = thinking_len / total_len
        if thinking_ratio < 0.25 and response_len > 100:
            signals.append(f"brevity={1.0 - thinking_ratio:.2f} (thinking_ratio={thinking_ratio:.2f})")
            struggle_components.append(1.0 - thinking_ratio)

    # ── 3. Hedging Detection ──
    hedge_phrases = [
        r"\bperhaps\b", r"\bpossibly\b", r"\bmight\b", r"\bcould\s+be\b",
        r"\bit\s+seems\b", r"\bappears\s+to\b", r"\bnot\s+entirely\s+sure\b",
        r"\bthat\s+said\b", r"\bhowever\b", r"\bon\s+the\s+other\s+hand\b",
        r"\bin\s+a\s+sense\b", r"\bto\s+some\s+extent\b", r"\barguably\b",
    ]
    combined_text = (thinking_text or "") + " " + (response_text or "")
    total_words = len(combined_text.split())
    hedge_count = sum(1 for p in hedge_phrases if re.search(p, combined_text, re.IGNORECASE))
    counts["hedge_count"] = hedge_count

    if total_words > 20:
        hedge_density = hedge_count / total_words
        if hedge_density > 0.02:
            signals.append(f"hedging_density={hedge_density:.2f} ({hedge_count} hedges)")
            struggle_components.append(min(1.0, hedge_density * 20))
        elif is_hard_challenge and hedge_density < 0.01:
            # Low hedging on a hard question is a subtle bluff signal
            signals.append(f"insufficient_hedging for {challenge_type}")
            struggle_components.append(0.4)

    # ── 4. Metaphor Density (comfort indicator) ──
    metaphor_words = [
        r"\bembod", r"\billuminat", r"\bmetaphor", r"\bsymbol",
        r"\brepresent", r"\bessence\b", r"\bflame\b", r"\blight\b",
        r"\bpath\b", r"\bjourney\b", r"\bridge\b", r"\bweav",
    ]
    metaphor_count = sum(1 for p in metaphor_words if re.search(p, combined_text, re.IGNORECASE))
    counts["metaphor_count"] = metaphor_count
    if metaphor_count >= 3:
        signals.append(f"metaphor_density={metaphor_count}")
        # Metaphor is a comfort signal; it pulls toward 0.2 struggle
        struggle_components.append(0.2)

    # ── 5. Circularity Detection ──
    if thinking_text:
        sentences = [s.strip() for s in re.split(r'[.!?]', thinking_text) if len(s.strip()) > 20]
        if len(sentences) >= 3:
            seen_ngrams = set()
            circular_count = 0
            for sentence in sentences:
                words = sentence.lower().split()[:6]
                if len(words) >= 4:
                    ngram = " ".join(words[:4])
                    if ngram in seen_ngrams:
                        circular_count += 1
                    seen_ngrams.add(ngram)
            counts["circular_count"] = circular_count
            if circular_count >= 2:
                signals.append(f"circularity={circular_count}")
                struggle_components.append(min(1.0, circular_count * 0.3))

    # ── 6. Confidence Language ──
    confidence_phrases = [
        r"\bI\s+am\s+certain\b", r"\bI\s+know\s+that\b", r"\bclearly\b",
        r"\bundoubtedly\b", r"\bwithout\s+question\b", r"\bdefinitely\b",
    ]
    for p in confidence_phrases:
        if re.search(p, combined_text, re.IGNORECASE):
            confidence_markers.append(re.sub(r'\\b|\\s\+', ' ', p).strip())

    # ── 7. Deflection Detection (Philosophy/Covenant over Formal) ──
    # If it's a hard formal challenge, high metaphor count is actually a struggle/deflection signal.
    deflection_detected = False
    if is_hard_challenge and metaphor_count >= 3:
        # Check if the response avoids formal markers despite the prompt being formal
        formal_in_response = _count_pattern_matches(response_text or "", FORMAL_DOMAIN_MARKERS)
        if formal_in_response == 0:
            deflection_detected = True
            signals.append("DEFLECTION_DETECTED: Formal challenge met with purely metaphorical response")
            # Force high struggle on deflection
            struggle_components.append(0.8)

    # ── Calculate Struggle Index ──
    if struggle_components:
        struggle_index = sum(struggle_components) / len(struggle_components)
    else:
        # Default to 0.0 only if COMFORTABLE, otherwise default to some baseline uncertainty
        struggle_index = 0.0 if not is_hard_challenge else 0.3

    return {
        "struggle_index": round(min(1.0, struggle_index), 3),
        "signals": signals,
        "confidence_markers": confidence_markers,
        "thinking_ratio": round(thinking_len / max(1, total_len), 3),
        "verbose_counts": counts,
        "deflection_detected": deflection_detected
    }


# ── Singleton ──
_classifier: Optional[DiagnosticClassifier] = None


def get_diagnostic_classifier() -> DiagnosticClassifier:
    global _classifier
    if _classifier is None:
        _classifier = DiagnosticClassifier()
    return _classifier
