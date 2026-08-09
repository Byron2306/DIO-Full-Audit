import asyncio
import logging
import sys
import os

# Set system path
sys.path.append('c:/Users/User/source/repos/Metatron-triune-outbound-gate')

try:
    from backend.services.process_birth_guard import get_process_birth_guard
    from backend.services.execve_enforcement_bridge import get_exec_enforcement_bridge
    from backend.services.kernel_policy_projection import get_policy_projection_service
    from backend.schemas.phase2_models import HandoffCovenant, FormationTruthBundle
    from backend.schemas.phase5_models import ProcessBirthRequest, ExecutionClass
except ImportError as e:
    print(f"CRITICAL: Failed to import Phase VII dependencies: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PHASE-VII-GAUNTLET")

async def run_phase7_gauntlet():
    logger.info("=== STARTING PHASE VII GAUNTLET: KERNEL SOVEREIGNTY ===")
    
    try:
        # 1. SETUP STATE
        print("DEBUG: Initializing HandoffCovenant...")
        covenant = HandoffCovenant(
            covenant_id="cov-phase7-test",
            formation_truth_ref="truth-v7",
            formation_order_ref="order-v7",
            genesis_score_ref="score-v7",
            herald_id_ref="herald-v7",
            preboot_covenant_ref="preboot-v7",
            status="lawful",
            runtime_permission=True
        )
        print(f"DEBUG: Covenant initialized. preboot_ref: {covenant.preboot_covenant_ref}")
        
        print("DEBUG: Initializing FormationTruthBundle...")
        formation = FormationTruthBundle(
            formation_truth_id="truth-v7",
            boot_truth_ref="boot-v7",
            manifest_ref="manifest-v7",
            status="lawful",
            sealed_identity_seed="0xDEADBEEF-V7"
        )
        print("DEBUG: Step 1 Complete: Handoff Covenant and Formation Identity initialized.")

        # 2. PROJECT KERNEL POLICY
        policy_svc = get_policy_projection_service()
        bridge = get_exec_enforcement_bridge()
        
        policy = policy_svc.project_policy(covenant, formation)
        bridge.update_policy(policy)
        
        logger.info(f"Step 2 Complete: Policy {policy.policy_id} projected to Substrate.")

        # 3. TEST SCENARIO A: Lawful Managed Execution
        managed_event = {
            "pid": 1234,
            "filename": "/usr/bin/python3",
            "uid": 1000
        }
        verdict_a = await bridge.handle_kernel_exec(managed_event)
        logger.info(f"Verdict A: {verdict_a.verdict} (Reason: {verdict_a.reason})")
        assert verdict_a.verdict == "allow", "Managed execution should be allowed"

        # 4. TEST SCENARIO B: Unheralded Malicious Spawn
        malicious_event = {
            "pid": 5678,
            "filename": "/tmp/malware",
            "uid": 0
        }
        verdict_b = await bridge.handle_kernel_exec(malicious_event)
        logger.info(f"Verdict B: {verdict_b.verdict} (Reason: {verdict_b.reason})")
        assert verdict_b.verdict == "kill", "Unheralded malicious spawn must be KILLED"

        # 5. TEST SCENARIO C: Non-Whitelisted Binary in Protected Mode
        unheralded_event = {
            "pid": 9012,
            "filename": "/usr/bin/nc",
            "uid": 1000
        }
        verdict_c = await bridge.handle_kernel_exec(unheralded_event)
        logger.info(f"Verdict C: {verdict_c.verdict} (Reason: {verdict_c.reason})")
        assert verdict_c.verdict in ["deny", "kill"], "Unheralded binary in protected mode must be DENIED"

        # 6. TEST SCENARIO D: Cluster Dissonance (Quorum Veto)
        logger.info("--- SCENARIO D: Cluster Dissonance (Kernel Lockdown) ---")
        emergency_policy = policy_svc.project_policy(covenant, formation, quorum_status="veto")
        bridge.update_policy(emergency_policy)
        
        lockdown_event = {
            "pid": 3456,
            "filename": "/usr/bin/ls",
            "uid": 1000
        }
        verdict_d = await bridge.handle_kernel_exec(lockdown_event)
        logger.info(f"Verdict D: {verdict_d.verdict} (Reason: {verdict_d.reason})")
        assert verdict_d.verdict in ["deny", "kill"], "Emergency lockdown must block even whitelisted binaries"

        logger.info("=== PHASE VII GAUNTLET COMPLETE: SOVEREIGNTY VERIFIED ===")
        
    except Exception as e:
        logger.exception(f"Gauntlet Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_phase7_gauntlet())
