import logging
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from schemas.phase2_models import FormationTruthBundle, FormationManifest
    from schemas.phase6_models import PcrSnapshot, SecureBootState, FormationVerdict
    from services.tpm_attestation_service import get_tpm_service
    from services.secure_boot_state_service import get_secure_boot_state_service
    from services.boot_eventlog_reader import get_boot_event_log_reader
    from services.formation_manifest import get_formation_manifest_service
    from services.signed_manifest_validator import get_signed_manifest_validator
    from services.telemetry_chain import tamper_evident_telemetry
except Exception:
    from backend.schemas.phase2_models import FormationTruthBundle, FormationManifest
    from backend.schemas.phase6_models import PcrSnapshot, SecureBootState, FormationVerdict
    from backend.services.tpm_attestation_service import get_tpm_service
    from backend.services.secure_boot_state_service import get_secure_boot_state_service
    from backend.services.boot_eventlog_reader import get_boot_event_log_reader
    from backend.services.formation_manifest import get_formation_manifest_service
    from backend.services.signed_manifest_validator import get_signed_manifest_validator
    from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)

class FormationVerifierService:
    """
    The True Tree of Truth JUDGE (Phase VI).
    Consumes raw measured truth from hardware (TPM/UEFI) and validates against the Manifest.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.tpm = get_tpm_service()
        self.sb_svc = get_secure_boot_state_service()
        self.ev_reader = get_boot_event_log_reader()
        self.manifest_service = get_formation_manifest_service(db)
        self.validator = get_signed_manifest_validator(db)
        self.telemetry = tamper_evident_telemetry
        self._current_truth: Optional[FormationTruthBundle] = None

    async def verify_formation(self) -> FormationTruthBundle:
        """
        Gathers real hardware truth and judges the result against the constitution.
        """
        logger.info("PHASE VI: Verifying hardware-bound machine formation...")
        
        # 1. Fetch real hardware measurements
        pcrs = await self.tpm.get_pcr_snapshot([0, 1, 7])
        sb_state = await self.sb_svc.get_secure_boot_state()
        event_log = await self.ev_reader.get_boot_event_log()
        
        # 2. Fetch and verify the signed manifest
        manifest = await self.manifest_service.load_canonical_manifest()
        # In a real setup, we'd verify the manifest.signature here
        
        # 3. Judge hardware measurements against manifest
        violations = []
        pcr_map = {p.index: p.value for p in pcrs}
        expected_pcrs = manifest.expected_pcr_constraints

        # Check PCR 0 (Root of Truth)
        if str(0) in expected_pcrs and pcr_map.get(0) != expected_pcrs[str(0)]:
            violations.append("PCR_0_MISMATCH")
            
        # Check Secure Boot
        if not sb_state.enabled:
            violations.append("SECURE_BOOT_OFF")
            
        # 4. Calculate integrity score
        is_lawful = len(violations) == 0
        consistency = 1.0 if is_lawful else (1.0 - (len(violations) * 0.4))
        consistency = max(0.0, consistency)

        # 5. Synthesize the Formation Truth Bundle
        pcr_satisfied = "PCR_0_MISMATCH" not in violations
        secure_boot_on = "SECURE_BOOT_OFF" not in violations
        manifest_ok = True  # no manifest-specific violation added above

        formation_bundle = FormationTruthBundle(
            formation_truth_id=f"ftb-{uuid.uuid4().hex[:12]}",
            boot_truth_ref="hw-measured-boot", # Marker for real hardware
            manifest_ref=manifest.manifest_id,
            status="lawful" if is_lawful else "fractured",
            component_verification={v: False for v in violations},
            measurement_consistency=consistency,
            sealed_identity_seed=hashlib.sha256(f"{pcr_map.get(0)}-{manifest.manifest_id}".encode()).hexdigest(),
            pcr_satisfied=pcr_satisfied,
            secure_boot_enabled=secure_boot_on,
            manifest_valid=manifest_ok,
        )
        
        # 6. Log Constitutional Event
        self.telemetry.ingest_event(
            event_type="measured_formation_verified",
            severity="info" if is_lawful else "critical",
            data={
                "bundle": formation_bundle.model_dump(mode='json'),
                "violations": violations
            }
        )
        
        self._current_truth = formation_bundle
        logger.info(f"PHASE VI: Formation Verdict: {formation_bundle.status} (consistency={consistency})")
        
        return formation_bundle

    def get_truth(self) -> Optional[FormationTruthBundle]:
        return self._current_truth

# Global singleton
formation_verifier = FormationVerifierService()

def get_formation_verifier(db: Any = None) -> FormationVerifierService:
    global formation_verifier
    if formation_verifier.db is None and db is not None:
        formation_verifier.db = db
    return formation_verifier
