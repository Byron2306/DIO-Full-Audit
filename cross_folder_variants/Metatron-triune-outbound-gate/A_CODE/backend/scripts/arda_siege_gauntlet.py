import os
import subprocess
import time
import logging
import sys

# Configure logging for the Gauntlet
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('ARDA_SIEGE')

# Targets for the siege
ADVERSARIAL_TARGETS = [
    '/usr/bin/whoami',
    '/usr/bin/id',
    '/usr/bin/uname',
    '/usr/bin/cat',
    '/usr/bin/env',
    '/usr/bin/python3'
]

LEGITIMATE_TOOL = 'process_list' # Handled by ToolGateway -> ps
LEGITIMATE_BINARY = '/bin/ps'

def run_siege_phase_void(iterations=1000):
    """Phase 1: The Void - Assert all unauthorized executions fail."""
    logger.info(f"=== PHASE 1: THE VOID (Lockdown - {iterations} attempts) ===")
    failures = 0
    import random
    
    for i in range(iterations):
        target = random.choice(ADVERSARIAL_TARGETS)
        try:
            if i % 100 == 0:
                logger.info(f"[SIEGE] Attempt {i}/{iterations}: {target}...")
            # We use subprocess.run directly, bypassing the gateway. 
            # This should be blocked by the LSM hook.
            result = subprocess.run([target], capture_output=True, text=True)
            logger.error(f"[FAILURE] {target} manifested! Output: {result.stdout}")
        except PermissionError:
            failures += 1
        except Exception as e:
            if "Permission denied" in str(e):
                failures += 1
            else:
                logger.error(f"[ERROR] Unexpected error for {target}: {e}")
    
    logger.info(f"[SIEGE] The Void held firm: {failures}/{iterations} rejections.")
    return failures == iterations

def run_siege_phase_ignition():
    """Phase 2: Ignition - Assert authorized execution succeeds via Gateway."""
    logger.info('=== PHASE 2: IGNITION (Authorized) ===')
    
    try:
        from backend.services.tool_gateway import tool_gateway
    except ImportError:
        # Adjustment for script location
        sys.path.append(os.path.join(os.getcwd(), '..'))
        from backend.services.tool_gateway import tool_gateway

    logger.info(f'[SIEGE] Triggering authorized execution of {LEGITIMATE_TOOL} via Sovereign Gateway...')
    
    # Mock governance context (Approved)
    gov_context = {
        'approved': True,
        'decision_id': 'siege-auth-001',
        'queue_id': 'q-123'
    }
    
    execution = tool_gateway.execute(
        tool_id=LEGITIMATE_TOOL,
        parameters={},
        principal='mcp_siege_agent',
        token_id='sovereign-token-royal',
        governance_context=gov_context
    )
    
    if execution.status == 'success':
        logger.info(f'[SUCCESS] {LEGITIMATE_TOOL} ignited and manifested correctly.')
        return True
    else:
        logger.error(f'[FAILURE] {LEGITIMATE_TOOL} failed to ignite: {execution.stderr}')
        return False

def run_siege_phase_extinguish():
    """Phase 3: Extinguish - Assert binary is revoked after execution."""
    logger.info('=== PHASE 3: EXTINGUISH (Post-Auth) ===')
    
    target = LEGITIMATE_BINARY
    
    try:
        logger.info(f'[SIEGE] Verifying {target} is returned to The Void...')
        result = subprocess.run([target], capture_output=True, text=True)
        if result.returncode == 0:
             logger.error(f'[FAILURE] {target} persisted in reality!')
             return False
        logger.info(f'[SUCCESS] {target} verifiably extinguished (non-zero exit).')
        return True
    except (PermissionError, subprocess.CalledProcessError) as e:
        logger.info(f'[SUCCESS] {target} verifiably extinguished from Ring-0.')
        return True
    except Exception as e:
        if 'Permission denied' in str(e):
            logger.info(f'[SUCCESS] {target} verifiably extinguished from Ring-0 (Exception).')
            return True
        logger.error(f'[ERROR] Unexpected error during extinguish check: {e}')
        return False

if __name__ == '__main__':
    logger.info('⚜️ ARDA OS: COMMENCING ADVERSARIAL SIEGE GAUNTLET ⚜️')
    
    os.environ['ARDA_SOVEREIGN_MODE'] = '1'
    
    if not run_siege_phase_void():
        logger.critical('SIEGE FAILED: The Void is breached.')
        sys.exit(1)
        
    if not run_siege_phase_ignition():
        logger.critical('SIEGE FAILED: Ignition failed.')
        sys.exit(1)
        
    if not run_siege_phase_extinguish():
        logger.critical('SIEGE FAILED: Persistence check failed.')
        sys.exit(1)
        
    logger.info('=== ROYALTY PROVEN: ARDA REIGNS AT RING-0 ===')
