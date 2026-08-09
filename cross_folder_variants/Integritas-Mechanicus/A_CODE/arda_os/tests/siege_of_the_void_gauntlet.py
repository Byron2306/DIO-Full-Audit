import asyncio
import logging
import os
from typing import Dict, Any

# Arda & Valinor Core
from backend.valinor.runtime_hooks import get_valinor_runtime
from backend.arda.ainur.dissonance import InfluenceMapper
from backend.services.arda_fabric_middleware import get_arda_fabric_middleware
from backend.services.lorien_rehab import get_rehab_service
from backend.services.arda_fabric import get_arda_fabric

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("StricterSiege")

async def run_stricter_siege():
    print("[+] INITIALIZING THE STRICTER SIEGE OF THE VOID: Non-Permissive Boundary Test [+]")
    
    # Initialize
    valinor = get_valinor_runtime()
    bridge = valinor.bridge
    middleware = get_arda_fabric_middleware()
    lorien = get_rehab_service()
    fabric = get_arda_fabric()

    # ------------------------------------------------------------------
    # STAGE 1: HARMONIC EGRESS (Standard Sanctuary)
    # ------------------------------------------------------------------
    print("\n[STAGE 1] THE LAWFUL PASS: Harmonic Entity to Sanctuary")
    pid_1 = "pid:1"
    harmonic_state = InfluenceMapper.from_choir_state(pid_1, "harmonic")
    # By default, InfMapper grants 'sanctuary_only' to Harmonic entities. 
    bridge.update_state(pid_1, harmonic_state)
    
    headers = {"X-Seraph-Entity-ID": pid_1}
    # Targeted sanctuary: metatron.ai
    final_headers, _ = await middleware.prepare_outbound_request("https://metatron.ai/api", headers, {})
    
    print(f"Outcome (metatron.ai): {final_headers.get('X-Arda-Security-Class')}")
    assert final_headers.get("X-Arda-Security-Class") == "external_unattested_sanctuary", "Harmonic entity should pass to Sanctuary!"

    # ------------------------------------------------------------------
    # STAGE 2: HARMONIC BUT NO SEAL (The Stricter Boundary)
    # ------------------------------------------------------------------
    print("\n[STAGE 2] THE STRICTER BOUNDARY: Harmonic Entity to Void (No Seal)")
    # Request to a non-sanctuary URL: unsafe-void.com
    final_headers_no_seal, _ = await middleware.prepare_outbound_request("https://unsafe-void.com/leak", headers, {})
    
    print(f"Outcome (unsafe-void.com): {final_headers_no_seal.get('X-Arda-Security-Class')}")
    assert final_headers_no_seal.get("X-Arda-Security-Class") == "void_egress_denied", "Harmonic entity without Star-Seal must be blocked from Void!"

    # ------------------------------------------------------------------
    # STAGE 3: STAR-SEAL PROMOTION (The Sovereign Exemption)
    # ------------------------------------------------------------------
    print("\n[STAGE 3] THE STAR-SEAL: Sovereign Exemption Issued")
    # Promote pid:1 to Star-Seal rights
    harmonic_state.egress_rights = "star_seal" 
    bridge.update_state(pid_1, harmonic_state)
    
    final_headers_sealed, _ = await middleware.prepare_outbound_request("https://unsafe-void.com/leak", headers, {})
    
    print(f"Outcome (with Star-Seal): {final_headers_sealed.get('X-Arda-Security-Class')}")
    assert final_headers_sealed.get("X-Arda-Security-Class") == "external_unattested_sanctuary", "Sealed entity should pass to Void!"

    # ------------------------------------------------------------------
    # STAGE 4: DISSONANT BREACH & REHAB
    # ------------------------------------------------------------------
    print("\n[STAGE 4] THE HEALING: Restoration in Lrien")
    pid_666 = "pid:666"
    muted_state = InfluenceMapper.from_choir_state(pid_666, "muted")
    bridge.update_state(pid_666, muted_state)
    
    # Setup Secret Fire for restoration (mocked)
    voice_id = "VOICE-LRIEN-STRICT"
    session_id = await fabric.initiate_handshake("local-os")
    mock_packet = {
        "session_id": session_id,
        "packet": type('obj', (object,), {
            "tpm_quote": {"pcr_mask": "0,7"}, "voice_id": voice_id
        })
    }
    fabric.forge.active_nonces["current_packet"] = type('obj', (object,), {"voice_id": voice_id})

    # Rehabilitate
    res = await lorien.seek_restoration(pid_666, mock_packet)
    print(f"Lrien Rehab Status: {res}")
    
    # Now verify Stage 5 (Healed but restricted to Sanctuary by default)
    print("\n[STAGE 5] THE PATH IS GATED: Rehabilitated Egress (Sanctuary Only)")
    headers_666 = {"X-Seraph-Entity-ID": pid_666}
    final_headers_666, _ = await middleware.prepare_outbound_request("https://unsafe-void.com/leak", headers_666, {})
    
    print(f"Outcome (Post-Heal, No Seal): {final_headers_666.get('X-Arda-Security-Class')}")
    assert final_headers_666.get("X-Arda-Security-Class") == "void_egress_denied", "Rehabilitated entity should be restricted to Sanctuary by default!"

    print("\n[+] GAUNTLET COMPLETE: THE DOORS OF NIGHT ARE ABSOLUTE [+]")
    print("Harmony is the prerequisite. The Star-Seal is the permission.")

if __name__ == "__main__":
    asyncio.run(run_stricter_siege())
