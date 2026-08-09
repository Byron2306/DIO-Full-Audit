from datetime import timezone
import asyncio
import logging
import os
import json
import base64
import hashlib
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PHASE-VI-GAUNTLET")

async def run_lawful_birth_gauntlet():
    """
    Gauntlet 6.1: The Lawful Birth.
    Verifies that a node with correct TPM/SecureBoot state can bootstrap its herald.
    """
    logger.info("--- GAUNTLET 6.1: STARTING LAWFUL BIRTH VERIFICATION ---")

    # 1. Setup Environment
    os.environ["TPM_MOCK_ENV"] = "production" # Tell mocks to use production defaults
    
    # 2. Imports (Lazy to ensure environment is set)
    try:
        from backend.services.formation_verifier import get_formation_verifier
        from backend.services.handoff_covenant import get_handoff_covenant_service
        from backend.services.manwe_herald import manwe_herald
        from backend.services.metatron_heartbeat import get_metatron_heartbeat
        from backend.services.preboot_state_sealer import get_preboot_state_sealer
    except ImportError:
        from services.formation_verifier import get_formation_verifier
        from services.handoff_covenant import get_handoff_covenant_service
        from services.manwe_herald import manwe_herald
        from services.metatron_heartbeat import get_metatron_heartbeat
        from services.preboot_state_sealer import get_preboot_state_sealer

    # 3. Step I: Pre-boot Sealing (Simulate Initramfs Stage)
    logger.info("STEP I: Simulating Pre-Boot Covenant Sealing...")
    sealer = get_preboot_state_sealer()
    # In a real setup, the initramfs script does this.
    preboot_payload = {
        "covenant_id": "init-cov-001",
        "formation_verdict": {
            "is_lawful": True,
            "confidence_score": 1.0,
            "violations": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        "boot_id": "boot-001",
        "manifest_hash": hashlib.sha256(b"manifest").hexdigest(),
        "sealed_data": "hmac-signed-legacy-v6",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Manually seal it to the volatile path
    volatile_path = "/tmp/seraph/preboot_covenant.sealed" if os.name != 'nt' else "C:\\Users\\User\\AppData\\Local\\Temp\\seraph\\preboot_covenant.sealed"
    os.makedirs(os.path.dirname(volatile_path), exist_ok=True)
    with open(volatile_path, 'w') as f:
        json.dump(preboot_payload, f)
    
    logger.info(f"Preboot Covenant sealed at {volatile_path}")

    # 4. Step II: Formation Verification (Hardware Bridge)
    logger.info("STEP II: Verifying Hardware-Bound Formation...")
    verifier = get_formation_verifier()
    truth_bundle = await verifier.verify_formation()
    
    if truth_bundle.status != "lawful":
        logger.error(f"GAUNTLET FAILED: Formation status is {truth_bundle.status}")
        return False
    
    logger.info(f"Formation VERIFIED. Integrity Score: {truth_bundle.measurement_consistency}")

    # 5. Step III: Runtime Covenant Sealing
    logger.info("STEP III: Sealing Runtime Handoff Covenant...")
    covenant_svc = get_handoff_covenant_service()
    runtime_covenant = await covenant_svc.seal_covenant()
    
    if not runtime_covenant.runtime_permission:
        logger.error(f"GAUNTLET FAILED: Runtime permission DENIED. Reason: {runtime_covenant.reason}")
        return False
    
    logger.info(f"Handoff Covenant SEALED. Preboot Ref: {runtime_covenant.preboot_covenant_ref}")

    # 6. Step IV: Herald Activation
    logger.info("STEP IV: Activating Attested Manwe Herald...")
    herald_state = await manwe_herald.bootstrap_herald()
    
    if herald_state.status != "active":
         logger.error(f"GAUNTLET FAILED: Herald status is {herald_state.status}")
         return False
         
    if not herald_state.attested_state_ref:
         logger.error("GAUNTLET FAILED: Herald is not bound to physical attestation.")
         return False

    logger.info(f"Herald ACTIVE. Identity: {herald_state.runtime_identity}")
    logger.info(f"Attested Birth Proof: {herald_state.attested_state_ref}")

    # 7. Step V: Heartbeat Emission
    logger.info("STEP V: Emitting Attested Heartbeat...")
    heartbeat = get_metatron_heartbeat()
    proof = await heartbeat.emit_now()
    
    if not proof.attestation_ref:
        logger.error("GAUNTLET FAILED: Heartbeat Proof lacks attestation reference.")
        return False

    logger.info(f"Heartbeat EMITTED. Proof ID: {proof.proof_id}")
    logger.info(f"Measured Formation Hash: {proof.measured_formation_hash}")

    logger.info("--- GAUNTLET 6.1: SUCCESS ---")
    return True

if __name__ == "__main__":
    asyncio.run(run_lawful_birth_gauntlet())
