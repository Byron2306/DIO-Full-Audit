import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

try:
    from schemas.phase2_models import HandoffCovenant, FormationTruthBundle
    from schemas.phase7_models import KernelPolicyProjection, SyscallConstraint
except Exception:
    from backend.schemas.phase2_models import HandoffCovenant, FormationTruthBundle
    from backend.schemas.phase7_models import KernelPolicyProjection, SyscallConstraint

logger = logging.getLogger(__name__)

class KernelPolicyProjectionService:
    """
    The Machine Law Compiler.
    Transforms philosophical Triune state into actionable kernel enforcement.
    """
    
    def __init__(self, db: Any = None):
        self.db = db

    def project_policy(
        self, 
        covenant: HandoffCovenant, 
        formation: FormationTruthBundle,
        quorum_status: str = "resonant",
        resonance_score: float = 1.0
    ) -> KernelPolicyProjection:
        """
        Compiles the current world state into a local kernel policy.
        """
        logger.info(f"PHASE VII: Projecting Kernel Policy from Covenant {covenant.covenant_id}...")
        
        is_lawful = (covenant.status == "lawful" and formation.status == "lawful")
        is_fractured = (covenant.status == "fractured" or formation.status == "fractured")
        
        # Determine strictness based on Quorum and Resonance
        enforce_exec = True
        lineage_strictness = True
        
        if quorum_status in ["fractured", "veto"]:
            logger.warning("PHASE VII: Quorum FRACTURED. Escalating to Hard Kernel Lockdown.")
            enforce_exec = True
            lineage_strictness = True
        elif resonance_score < 0.5:
             logger.warning("PHASE VII: Resonance Low. Tightening lineage enforcement.")
             lineage_strictness = True

        # Build Syscall Constraints
        constraints = self._build_default_constraints(is_lawful, quorum_status)

        # Binary Lists (Mocked/Simplified for now)
        whitelisted = ["/usr/bin/python3", "/usr/bin/bash", "/usr/bin/ls"]
        blacklisted = ["/tmp/malware", "/usr/bin/nc", "/usr/bin/nmap"]

        if not is_lawful:
             # In unverified state, we blacklist almost everything sensitive
             blacklisted.extend(["/usr/bin/ssh", "/usr/bin/scp", "/usr/bin/curl"])

        return KernelPolicyProjection(
            policy_id=f"kpol-{uuid.uuid4().hex[:8]}",
            covenant_authority_id=covenant.covenant_id,
            enforce_exec_protection=enforce_exec,
            enforce_lineage_strictness=lineage_strictness,
            syscall_constraints=constraints,
            whitelisted_binaries=whitelisted,
            blacklisted_binaries=blacklisted,
            generated_at=datetime.now(timezone.utc)
        )

    def _build_default_constraints(self, is_lawful: bool, quorum: str) -> Dict[str, List[SyscallConstraint]]:
        """
        Builds syscall constraint maps for different manifestation classes.
        """
        standard_profile = [
            SyscallConstraint(class_id="network", action="allow"),
            SyscallConstraint(class_id="filesystem", action="allow"),
            SyscallConstraint(class_id="privilege", action="trace")
        ]
        
        restricted_profile = [
            SyscallConstraint(class_id="network", action="deny"),
            SyscallConstraint(class_id="filesystem", action="trace"),
            SyscallConstraint(class_id="privilege", action="deny")
        ]

        if not is_lawful or quorum == "veto":
            return {
                "default": restricted_profile,
                "admin": restricted_profile,
                "service": restricted_profile
            }
        
        return {
            "default": standard_profile,
            "admin": [SyscallConstraint(class_id="privilege", action="allow")] + standard_profile,
            "service": standard_profile
        }

# Global Singleton
_policy_service = None

def get_policy_projection_service(db: Any = None) -> KernelPolicyProjectionService:
    global _policy_service
    if _policy_service is None:
        _policy_service = KernelPolicyProjectionService(db)
    return _policy_service
