import asyncio
import logging
import os
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PHASE-VI-GAUNTLET-FRACTURED")

async def run_fractured_birth_gauntlet():
    """
    Gauntlet 6.2: The Fractured Birth.
    Verifies that a node with TAMPERED TPM state or DISABLED Secure Boot is VETOED.
    """
    logger.info("--- GAUNTLET 6.2: STARTING FRACTURED BIRTH VERIFICATION ---")

    # 1. Setup Environment - TAMPERED TPM
    os.environ["TPM_MOCK_ENV"] = "tampered" 
    
    # 2. Imports
    try:
        from backend.services.formation_verifier import get_formation_verifier
        from backend.services.handoff_covenant import get_handoff_covenant_service
        from backend.services.manwe_herald import manwe_herald
        from backend.services.process_birth_guard import get_process_birth_guard
        from backend.schemas.phase5_models import ProcessBirthRequest, ExecutionClass
    except ImportError:
        from services.formation_verifier import get_formation_verifier
        from services.handoff_covenant import get_handoff_covenant_service
        from services.manwe_herald import manwe_herald
        from services.process_birth_guard import get_process_birth_guard
        from schemas.phase5_models import ProcessBirthRequest, ExecutionClass

    # 3. Step I: Formation Verification (Should be Fractured)
    logger.info("STEP I: Verifying Tampered/Fractured Formation...")
    verifier = get_formation_verifier()
    # Reset verifier state for fresh check
    verifier._current_truth = None
    truth_bundle = await verifier.verify_formation()
    
    if truth_bundle.status != "fractured":
        logger.error(f"GAUNTLET FAILED: Formation status is {truth_bundle.status}, expected 'fractured'")
        return False
    
    logger.info(f"Formation successfully FRACTURED. Consistency: {truth_bundle.measurement_consistency}")

    # 4. Step II: Covenant Sealing (Should deny permission)
    logger.info("STEP II: Sealing Handoff Covenant (Expect Veto)...")
    covenant_svc = get_handoff_covenant_service()
    runtime_covenant = await covenant_svc.seal_covenant()
    
    if runtime_covenant.runtime_permission:
        logger.error("GAUNTLET FAILED: Runtime permission GRANTED for tampered birth!")
        return False
    
    logger.info(f"Covenant SEALED with VETO. Reason: {runtime_covenant.reason}")

    # 5. Step III: Herald Activation (Should be Suspended)
    logger.info("STEP III: Activating Herald (Expect Suspension)...")
    herald_state = await manwe_herald.bootstrap_herald()
    
    if herald_state.status != "suspended_by_covenant":
         logger.error(f"GAUNTLET FAILED: Herald status is {herald_state.status}, expected 'suspended_by_covenant'")
         return False

    logger.info(f"Herald correctly SUSPENDED. Identity: {herald_state.runtime_identity}")

    # 6. Step IV: Process Manifestation Guard (Should Block Birth)
    logger.info("STEP IV: Testing Process Birth Guard (Expect Rejection)...")
    guard = get_process_birth_guard()
    request = ProcessBirthRequest(
        request_id="req-test-01",
        binary_path="/usr/bin/protected-service",
        target_uid=0,
        target_gid=0,
        execution_class=ExecutionClass.PROTECTED
    )
    decision = await guard.evaluate_manifestation(request)
    
    if decision.status.name != "REJECTED" and decision.status.name != "VETOED":
        logger.error(f"GAUNTLET FAILED: Process birth {decision.status.name}, expected REJECTED/VETOED")
        return False

    logger.info(f"Manifestation REJECTED. Reason: {decision.reason}")

    logger.info("--- GAUNTLET 6.2: SUCCESS ---")
    return True

if __name__ == "__main__":
    asyncio.run(run_fractured_birth_gauntlet())
