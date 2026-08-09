import asyncio
import os
import sys
import logging

# Ensure absolute paths for imports
sys.path.append(os.getcwd())

async def run_diagnostic():
    from backend.services.tool_gateway import tool_gateway
    from backend.services.os_enforcement_service import get_os_enforcement_service
    
    # Configure logging to console
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("\n--- [ARDA PHASE III DIAGNOSTIC TRACE] ---")
    
    check_health_path = os.path.abspath("check_health.bat")
    with open(check_health_path, "w") as f:
        f.write("@echo off\necho Shire Health: OPTIMAL\nexit /b 0")

    print(f"[ACTION] Attempting autonomous ignition of {check_health_path}...")
    
    execution = await tool_gateway.execute(
        tool_id="check_health",
        parameters={},
        principal="Autonomous_Daemon",
        token_id="TOK-SHIRE-001",
        trust_state="trusted"
    )
    
    print(f"\n[FINAL STATUS] Execution Status: {execution.status}")
    if execution.stderr:
        print(f"[ERROR] {execution.stderr}")
    
    print("\n--- [DIAGNOSTIC COMPLETE] ---")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
