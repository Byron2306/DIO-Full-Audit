import os
import asyncio
import logging
import hashlib
import json
from backend.services.os_enforcement_service import get_os_enforcement_service
from backend.services.ainur.ainur_council import AinurCouncil
from backend.services.ainur.witnesses.manwe_herald import ManweHerald
from backend.services.ainur.witnesses.lorien_healer import LorienHealer

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ARDA_PROOF_D")

async def prove_rehabilitation():
    print("\n" + "="*60)
    print("PROOF D: LÓRIEN REHABILITATION (SYSTEM RESTORATION) 🛡️")
    print("="*60)
    
    os_enforcement = get_os_enforcement_service()
    rehab_path = os.path.abspath("testbins/rehab.sh")
    
    # Ensure the binary exists
    if not os.path.exists(rehab_path):
        with open(rehab_path, "w") as f:
            f.write("#!/bin/bash\necho 'REHABILITATED'\n")
            
    print(f"\n[ACTION] Attempting to ignite unrecognized binary: {rehab_path}")
    
    # STAGE 1: Denial (The Fall)
    # This should fail because it's not in the manifest yet.
    with open(rehab_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
        
    print(f"[CORE] Measuring binary... Hash: {file_hash[:16]}...")
    is_valid = os_enforcement._verify_manifest_integrity(rehab_path, file_hash)
    
    if not is_valid:
        print("[CORE] ❌ VETO: Binary is FALLEN (Unrecognized).")
    else:
        print("[CORE] ⚠️ Binary is already harmonic. Please remove from manifest for proof.")
        return

    # STAGE 2: The Council (The Plea for Restoration)
    print("\n[RAINER] Appealing to the Ainur Council for rehabilitation...")
    council = AinurCouncil()
    council.register_witness(ManweHerald(council))
    council.register_witness(LorienHealer(council))
    
    report = await council.consult_witnesses({
        "command": rehab_path,
        "context": "System utility recovered from legacy backup. Seeking re-integration.",
        "state": "FALLEN"
    })
    
    print(f"[AINUR] Council Consensus: {report['overall_recommendation']}")
    lorien_report = report["witness_reports"].get("Lórien", {})
    print(f"[LÓRIEN] Dream of Restoration: {lorien_report.get('recovery_path')}")
    
    # STAGE 3: Restoration (The Healing)
    if report["overall_recommendation"] == "LAWFUL":
        print("\n[ACTION] Council has blessed restoration. Updating Sovereign Manifest...")
        manifest_path = "sovereign_manifest.json"
        manifest = {}
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                try:
                    manifest = json.load(f)
                except json.JSONDecodeError:
                    manifest = {}
        
        # Normalize path naming for Tulkas/Ring-0 Verifier
        norm_rehab = os.path.abspath(rehab_path).lower().replace("\\", "/")
        manifest[norm_rehab] = file_hash
        
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)
            
        print("[CORE] ✅ Sovereign Manifest updated. Attestation successful.")
        
        # STAGE 4: Second Attempt (The Ascent)
        print("\n[ACTION] Re-attempting ignition...")
        is_valid_now = os_enforcement._verify_manifest_integrity(rehab_path, file_hash)
        if is_valid_now:
            print("[CORE] ✅ IGNITION BLESSED: Node is REHABILITATED.")
            print("\n[RESULT] ✅ PROOF SUCCESSFUL: Lórien Protocol complete.")
        else:
            print("[CORE] ❌ Second VETO: Restoration failed.")
    else:
        print("\n[RESULT] ⚠️ Council withheld restoration. Try a more 'Lawful' scenario.")

if __name__ == "__main__":
    asyncio.run(prove_rehabilitation())
