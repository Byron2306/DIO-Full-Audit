from enum import Enum
from typing import Dict, Any, Literal
from .verdicts import ChoirVerdict

class ConstitutionalMode(Enum):
    DEVELOPMENT = "development"
    GUARDED = "guarded"
    SOVEREIGN = "sovereign"
    GENESIS = "genesis"

class AinurPolicy:
    """
    Maps ChoirVerdicts to governance outcomes based on the current mode.
    """
    
    @staticmethod
    def get_governance_outcome(verdict: ChoirVerdict, mode: ConstitutionalMode) -> Dict[str, Any]:
        """
        Derive the final governance decision from the choir result.
        """
        outcome = {
            "node_status": "restricted",
            "vote_eligible": False,
            "manifestation_rights": "observer",
            "reason": ""
        }

        success_states = {"heralded", "harmonic"}
        
        if mode == ConstitutionalMode.DEVELOPMENT:
            # Flexible: allowed unless explicitly vetoed
            if verdict.overall_state != "vetoed":
                outcome.update({
                    "node_status": "active",
                    "vote_eligible": True,
                    "manifestation_rights": "worker"
                })
            return outcome

        if mode == ConstitutionalMode.GUARDED:
            if verdict.overall_state in success_states:
                outcome.update({
                    "node_status": "active",
                    "vote_eligible": True,
                    "manifestation_rights": "worker"
                })
            elif verdict.overall_state == "withheld":
                outcome["reason"] = "Restricted due to withheld choir verdict"
            return outcome

        if mode == ConstitutionalMode.SOVEREIGN:
            if verdict.overall_state in success_states:
                outcome.update({
                    "node_status": "sovereign",
                    "vote_eligible": True,
                    "manifestation_rights": "validator"
                })
            else:
                outcome["node_status"] = "excluded"
                outcome["reason"] = f"Sovereign mode requires harmonic/heralded status (current: {verdict.overall_state})"
            return outcome

        if mode == ConstitutionalMode.GENESIS:
            if verdict.overall_state in success_states:
                outcome.update({
                    "node_status": "genesis_root",
                    "vote_eligible": True,
                    "manifestation_rights": "herald"
                })
            else:
                outcome["node_status"] = "vetoed"
                outcome["reason"] = "Genesis requires absolute constitutional harmony"
            return outcome

        return outcome
