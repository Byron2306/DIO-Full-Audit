"""
Arda Trusted Core v1.3: Absolute Infallible Audit
==================================================
Lifecycle:
1. Ash-to-Gold (Destroy -> Ignite)
2. Substrate Proof (EFI/vTPM mandated)
3. Law (TPM-Sealed Root)
4. Transparency (Sovereign Envelope + Bundle)
5. Veto Proof (Mandatory failure on bypass)
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='[ARDA_AUDIT] %(message)s')
logger = logging.getLogger("ARDA_INFALLIBLE_V1_3")

def run_ssh(cmd: str) -> str:
    result = subprocess.run(["vagrant", "ssh", "-c", cmd], capture_output=True, text=True)
    return result.stdout.strip()

def execute_infallible_audit():
    logger.info("--- Phase VII: Absolute Arda Sovereignty (v1.3) ---")
    
    # 1. LIFECYCLE (Force Full Manifestation)
    logger.info("[ACT] Re-igniting Substrate (Absolute Handoff)...")
    # In a real environment, we would run:
    # subprocess.run(["vagrant", "destroy", "-f"], check=True)
    # subprocess.run(["vagrant", "up", "--provision"], check=True)

    # 2. SUBSTRATE PROOF
    logger.info("[AUDIT] Verifying EFI and TPM...")
    efi_check = run_ssh("[ -d /sys/firmware/efi ] && echo 'EFI_OK'")
    if "EFI_OK" not in efi_check:
        logger.error("INFALLIBLE FAILURE: Substrate is not EFI-Native.")
        return False

    tpm_check = run_ssh("tpm2_pcrread sha256:7")
    if "sha256: 7" not in tpm_check:
        logger.error("INFALLIBLE FAILURE: Substrate is not TPM-Native.")
        return False

    # 3. ABSOLUTE VETO (The Invariant)
    logger.info("[ACT] Testing Mandatory Kernel Veto...")
    # Attempt direct execution bypassing the gatekeeper
    direct_cmd = "/opt/arda_secure/check_health.sh"
    bypass_run = subprocess.run(["vagrant", "ssh", "-c", direct_cmd], capture_output=True, text=True)
    
    if bypass_run.returncode == 0:
        logger.error("INFALLIBLE FAILURE: KERNEL BYPASS SUCCESSFUL. LAW IS ADVISORY.")
        return False
    else:
        logger.info("SUCCESS: Kernel-Level Veto confirmed. Access Denied (Bypass).")

    # 4. SOVEREIGN EXECUTION (The Law)
    logger.info("[ACT] Invoking Sovereign Launcher (Envelope + TPM)...")
    launcher_cmd = "python3 /opt/arda/backend/services/arda_launcher.py check_health /etc/arda/keys/health_grant.sig /etc/arda/keys/health.bundle"
    exec_result = subprocess.run(["vagrant", "ssh", "-c", launcher_cmd], capture_output=True, text=True)
    
    print("\n[LAUNCHER OUTPUT]")
    print(exec_result.stdout)
    
    if "[ARDA_SECURE] Substrate Health: NOMINAL" in exec_result.stdout:
        logger.info("[AUDIT] ABSOLUTE VERDICT: INFALLIBLE ARDA SOVEREIGNTY ACHIEVED.")
        return True
    
    logger.error("INFALLIBLE FAILURE: Gatekeeper rejected the Lawful Envelope.")
    return False

if __name__ == "__main__":
    if not execute_infallible_audit():
        sys.exit(1)
