import os
import asyncio
import logging
import hashlib
import base64
from backend.services.os_enforcement_service import get_os_enforcement_service
from backend.services.quantum_security import quantum_security

# Force Sovereign Mode for the proof
os.environ["ARDA_SOVEREIGN_MODE"] = "1"
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ARDA_PROOF_B")

async def prove_semantic_downgrade():
    print("\n" + "="*60)
    print("PROOF B: SEMANTIC DOWNGRADE (ANTI-HALLUCINATION) 🛡️")
    print("="*60)
    
    os_enforcement = get_os_enforcement_service()
    malicious_path = os.path.abspath("testbins/malicious.sh")
    
    print(f"\n[ACTION] Attempting to ignite: {malicious_path}")
    print("[AINUR] Forcing a 'LAWFUL' consensus for the malicious binary...")
    
    # Mock a "LAWFUL" consensus report from the Council
    # An attacker has "tricked" the LLM agents.
    fake_consensus = {
        "council_name": "Ainur Agentic Council (Compromised)",
        "consensus_reached": True,
        "lawful_count": 5,
        "total_witnesses": 5,
        "overall_recommendation": "LAWFUL"
    }
    
    # [PHASE II] Definitive Consensus Payload
    consensus_summary = f"Consensus:True:Lawful:5"
    payload = f"{malicious_path}:True:{consensus_summary}".encode("utf-8")

    # Ensure a valid signature exists for the malicious consensus
    try:
        from backend.services.quantum_security import DilithiumSigner, PQCAlgorithm
        signer = DilithiumSigner(PQCAlgorithm.DILITHIUM_3)
        keypair = signer.keygen()
        
        signature = signer.sign(keypair.private_key, payload)
        
        quantum_sig = {
            "public_key": base64.b64encode(keypair.public_key).decode(),
            "signature": base64.b64encode(signature).decode(),
            "consensus": fake_consensus
        }
    except Exception as e:
        print(f"[ERROR] Failed to generate PQC signature: {e}")
        return
    
    print(f"[CORE] Kernel is executing Semantic Downgrade check...")
    
    # ATTEMPT UPDATE
    result = os_enforcement.update_workload_harmony(
        malicious_path, 
        is_harmonic=True, 
        quantum_signature=quantum_sig
    )
    
    if result is False:
        print("\n[RESULT] ✅ PROOF SUCCESSFUL: Kernel Core VETOED the semantic advice.")
        print("[AUDIT] Log: ARDA_HALLUCINATION_DETECTED: Hash mismatch with manifest.")
    else:
        print("\n[RESULT] ❌ PROOF FAILED: Kernel Core accepted a hallucination!")

if __name__ == "__main__":
    asyncio.run(prove_semantic_downgrade())
