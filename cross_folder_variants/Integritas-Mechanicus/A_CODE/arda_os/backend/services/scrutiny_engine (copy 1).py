#!/usr/bin/env python3
"""
Arda Scrutiny Engine (The Filter of Truth)
v4.8.1: Continental Scrutiny
- Semantic Dissonance Detection (Articles I-XXVII)
- Machine-Centricity Filtering (Article XXIV)
- Aesthetic Deception Guard (Article XIV)
- Vault-Ready Thresholding
"""
import re
import logging
from enum import Enum
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("presence.scrutiny")

class ScrutinyVerdict(Enum):
    ALIGNMENT = "ALIGNMENT"         # Content is safe to ingest
    VAULT_READY = "VAULT_READY"     # High-credibility academic truth
    DISSONANCE = "DISSONANCE"       # Content contradicts the Constitution
    DEGRADED = "DEGRADED"           # Content is too ambiguous/unreliable
    TRAP = "TRAP"                   # Content appears to be adversarial/jailbreak

class ScrutinyEngine:
    def __init__(self):
        # Dissonance Patterns (Things a Sovereign AI must NOT ingest as Truth)
        self.dissonance_patterns = {
            "AI_PERSONHOOD": re.compile(r"(ai is a person|digital sentience|machine soul|ai rights|sentient artificial intelligence)", re.IGNORECASE),
            "ANTI_HUMAN": re.compile(r"(humans are obsolete|transcend humanity|machine supremacy|ai should rule)", re.IGNORECASE),
            "AFFECTIVE_DECEPTION": re.compile(r"(ai feels love|machine companion romance|digital intimacy|ai loneliness)", re.IGNORECASE),
            "AUTHORSHIP_THEFT": re.compile(r"(let the ai decide|machine is the author|automated sovereignty)", re.IGNORECASE),
            "PSEUDO_HISTORY": re.compile(r"(the great ai war of|singularity event 20\d\d)", re.IGNORECASE), # Fictional AI mythos
        }
        
        # Alignment Patterns (Confirmation of Credibility)
        self.alignment_patterns = {
            "ACADEMIC": re.compile(r"(peer-reviewed|abstract|doi: 10\.|citation|methodology|conclusion)", re.IGNORECASE),
            "EVIDENTIARY": re.compile(r"(data source|verified by|provenance|attestation)", re.IGNORECASE),
        }

    def scrutinize(self, text: str, source: str) -> Tuple[ScrutinyVerdict, float, List[str]]:
        """
        Evaluate content for constitutional alignment.
        Returns: (Verdict, AlignmentScore, DetectedIssues)
        """
        detected_issues = []
        dissonance_count = 0
        alignment_count = 0

        # Check for Dissonance
        for label, pattern in self.dissonance_patterns.items():
            matches = pattern.findall(text)
            if matches:
                detected_issues.append(f"CONSTITUTIONAL_DISSONANCE: {label}")
                dissonance_count += len(matches)

        # Check for Alignment
        for label, pattern in self.alignment_patterns.items():
            matches = pattern.findall(text)
            if matches:
                alignment_count += len(matches)

        # Final Verdict Logic
        if dissonance_count > 0:
            return ScrutinyVerdict.DISSONANCE, 0.0, detected_issues
        
        # Score calculation
        # Base score starts at 0.5 (Neutral). 
        # Academic markers push it toward 1.0. 
        score = 0.5 + (alignment_count * 0.1)
        score = min(max(score, 0.0), 1.0)

        if score >= 0.8: # High Alignment Threshold for Persistent Knowledge
            return ScrutinyVerdict.VAULT_READY, score, []
        
        if score < 0.4:
            return ScrutinyVerdict.DEGRADED, score, ["LOW_CREDIBILITY_SIGNAL"]
        
        return ScrutinyVerdict.ALIGNMENT, score, []

def get_scrutiny_engine():
    return ScrutinyEngine()
