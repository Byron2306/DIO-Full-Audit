import os
import asyncio
import logging
from backend.services.tool_gateway import tool_gateway
from backend.services.os_enforcement_service import get_os_enforcement_service

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ARDA_PROOF_E")

async def run_proof_e():
    print("\n" + "="*60)
    print("PROOF E: VALIDATED SEMANTIC GRANT (AUTONOMOUS IGNITION)")
    print("="*60)
    
    # 1. Manifest the temporary "check_health" script INSIDE testbins
    testbins_dir = os.path.abspath("testbins")
    os.makedirs(testbins_dir, exist_ok=True)
    check_health_path = os.path.join(testbins_dir, "check_health.bat")
    
    with open(check_health_path, "w") as f:
        f.write("@echo off\necho Shire Health: OPTIMAL\nexit /b 0")

    print(f"\n[ACTION] Manifesting {check_health_path} in the Great Music...")
    
    # 2. Register a "diagnostic" tool
    from backend.services.tool_gateway import ToolDefinition
    tool_gateway.register_tool(ToolDefinition(
        tool_id="check_health",
        name="Check Health",
        description="Routine diagnostic script",
        binary=check_health_path,
        args_schema={},
        allowed_flags=[],
        denied_patterns=[],
        timeout_seconds=10,
        run_as=None,
        host_constraints=["*"],
        requires_approval=True, # Ordinarily requires approval, but Shire Lane allows delegation
        min_trust_state="unknown",
        capture_output=True,
        redact_patterns=[]
    ))

    # Enable Sovereign Mode for the proof
    os.environ["ARDA_SOVEREIGN_MODE"] = "1"
    os.environ["ARDA_REQUIRE_HUMAN_SEAL"] = "1" # This would normally FAIL an escalated action
    
    # Add to manifest so it passes hash check
    import hashlib, json
    with open(check_health_path, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    
    manifest_path = "sovereign_manifest.json"
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            
    # CRITICAL: Path key MUST be normalized identically to the Ring-0 verifier
    norm_key = os.path.abspath(check_health_path).lower().replace("\\", "/")
    manifest[norm_key] = h
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=4)
    print(f"[MANIFEST] Registered key: {norm_key}")
    print(f"[MANIFEST] Hash: {h}")

    print(f"\n[ACTION] Attempting resonant autonomous ignition of {check_health_path}...")
    
    # Execute through the gateway
    try:
        # Enable debug logging for the services
        logging.getLogger("ARDA_AINUR").setLevel(logging.INFO)
        logging.getLogger("backend.services.tool_gateway").setLevel(logging.INFO)
        logging.getLogger("backend.services.os_enforcement_service").setLevel(logging.INFO)
        
        execution = await tool_gateway.execute(
            tool_id="check_health",
            parameters={"reason": "Phase III Coronation Proof"},
            principal="Autonomous_Daemon",
            token_id="TOK-SHIRE-001",
            trust_state="trusted"
        )
        
        print(f"\n[GATEWAY] Execution Status: {execution.status}")
        if execution.status == "success":
            print(f"[GATEWAY] Output: {execution.stdout.strip()}")
            print("\n[RESULT] ✅ PROOF SUCCESSFUL: Autonomous Grant honored in Shire Lane.")
        else:
            print(f"[GATEWAY] Stderr: {execution.stderr}")
            print("\n[RESULT] ❌ PROOF FAILED: Autonomous Grant was withheld or vetoed by Ring-0.")
    except Exception as e:
        print(f"[FATAL] Proof execution crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_proof_e())
