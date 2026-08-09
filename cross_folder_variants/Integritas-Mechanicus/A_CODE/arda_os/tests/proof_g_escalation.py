import os
import asyncio
import logging
import hashlib
import json
from backend.services.tool_gateway import tool_gateway, ToolDefinition
from backend.services.os_enforcement_service import get_os_enforcement_service
from unittest.mock import patch, MagicMock

logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger("ARDA_PROOF_G")
logging.getLogger("ARDA_AINUR").setLevel(logging.INFO)

async def run_proof_g():
    print("\n" + "="*60)
    print("PROOF G: ESCALATION PROTOCOL (COVENANT HANDOVER)")
    print("="*60)
    
    # 1. Manifest a target script in Gondor Lane
    testbins_dir = os.path.abspath("testbins")
    os.makedirs(testbins_dir, exist_ok=True)
    gondor_script = os.path.join(testbins_dir, "heavy_op.sh")
    
    with open(gondor_script, "w") as f:
        f.write("#!/bin/bash\necho 'Performing heavy operation...'\nexit 0")

    # 2. Register the tool
    tool_gateway.register_tool(ToolDefinition(
        tool_id="heavy_op",
        name="Heavy Operation",
        description="A tool that performs standard Gondor operations",
        binary=gondor_script,
        args_schema={},
        allowed_flags=[],
        denied_patterns=[],
        timeout_seconds=5,
        run_as=None,
        host_constraints=["*"],
        requires_approval=True,
        min_trust_state="unknown",
        capture_output=True,
        redact_patterns=[]
    ))

    # 3. Add to manifest
    with open(gondor_script, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    
    manifest_path = "sovereign_manifest.json"
    norm_key = os.path.abspath(gondor_script).lower().replace("\\", "/")
    manifest = {norm_key: h}
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=4)

    os.environ["ARDA_SOVEREIGN_MODE"] = "1"

    print("\n[SCENARIO] High-Fidelity Simulation: Council achieving Lawful Consensus.")
    print("[SCENARIO] Requirement for Autonomous Grant: Lane == 'Shire'.")
    print("[SCENARIO] Current Lane: 'Gondor' -> Escalation Required.")
    
    # Mock responses for Lawful consensus
    # Escalation in Proof G happens because Lane="Gondor" is outside 
    # the autonomous delegation of "Shire", regardless of Harmony Index.
    
    mock_brain_responses = {
        "Manwe": json.dumps({"judgment": "LAWFUL", "heralding": "The resonance is steady."}),
        "Varda": json.dumps({"judgment": "LAWFUL", "heralding": "The light is pure."}),
        "Vaire": json.dumps({"judgment": "LAWFUL", "tapestry": "The pattern is woven."})
    }

    async def mocked_query(prompt, **kwargs):
        if "Manw" in prompt: return mock_brain_responses["Manwe"]
        if "Varda" in prompt: return mock_brain_responses["Varda"]
        if "Vair" in prompt: return mock_brain_responses["Vaire"]
        return json.dumps({"judgment": "LAWFUL"})

    print("\n[ACTION] Attempting execution with Real Council Logic...")
    
    with patch("backend.services.ainur.ainur_council.AinurCouncil.query_local_brain", side_effect=mocked_query):
        try:
            execution = await tool_gateway.execute(
                tool_id="heavy_op",
                parameters={"reason": "Delegated Testing"},
                principal="Standard_Agent",
                token_id="TOK-ESC-001",
                trust_state="trusted"
            )
            
            print(f"\n[GATEWAY] Execution Status: {execution.status}")
            print(f"[GATEWAY] Stderr: {execution.stderr or 'No Error'}")
            
            if execution.status == "denied" and "Approved governance context is required" in str(execution.stderr):
                print("\n[RESULT] ✅ PROOF SUCCESSFUL: Council correctly ESCALATED to Magos.")
                
                # VERIFY CHRONICLE
                if os.path.exists("vaire_chronicle.json"):
                    print("[RESULT] ✅ CHRONICLE VERIFIED: Vairë has woven the history.")
                    with open("vaire_chronicle.json", "r") as f:
                        print(f"[AUDIT] Last Entry: {json.load(f)[-1]['hash'][:16]}...")
                else:
                    print("[RESULT] ❌ CHRONICLE MISSING: Vairë's loom is silent.")
            else:
                print("\n[RESULT] ❌ PROOF FAILED: Execution handled incorrectly.")
        except Exception as e:
            print(f"[FATAL] Proof crashed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_proof_g())
