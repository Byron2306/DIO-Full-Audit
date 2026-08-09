import asyncio
import logging
import os
from typing import Dict, Any

# Arda & Valinor Core
from backend.valinor.runtime_hooks import get_valinor_runtime
from backend.arda.ainur.dissonance import ResonanceMapper
from backend.services.earendil_flow import get_earendil_flow
from backend.valinor.taniquetil_core import ResonanceEvent

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("GreatCrossingGauntlet")

async def run_the_great_crossing():
    print("[+] INITIALIZING THE GREAT CROSSING: Multi-Node Resonance Sync [+]")
    
    # 1. Initialize Resonance Environment (Representing Node ALPHA and Node BETA together)
    # In this test, we use the same LightBridge but simulate the separate roles
    valinor = get_valinor_runtime()
    bridge = valinor.bridge
    taniquetil = valinor.taniquetil
    earendil = get_earendil_flow()
    fabric = earendil.fabric

    # Setup a Sovereign Voice for the test
    from backend.arda.ainur.verdicts import IluvatarVoiceChallenge, SecretFirePacket
    voice = IluvatarVoiceChallenge(
        voice_id="VOICE-GAUNTLET", root_nonce="A", issued_at=0, expires_at=2000000000, epoch="A", sweep_id="S1"
    )
    packet = SecretFirePacket(
        node_id="localhost", covenant_id="C1", voice_id=voice.voice_id,
        nonce="N1", issued_at=0, expires_at=2000000000, responded_at=0.1,
        latency_ms=0, epoch="A", monotonic_counter=1, attestation_digest="A",
        order_digest="O", runtime_digest="R", witness_id="W", witness_signature="S"
    )
    fabric.forge.active_nonces["current_packet"] = packet

    # Ensure a session exists for the test peer (metatron-beta)
    session_id = await fabric.initiate_handshake("metatron-beta")
    mock_packet = type('obj', (object,), {"tpm_quote": {"pcr_mask": "0,7"}, "voice_id": voice.voice_id})
    await fabric.verify_handshake(session_id, mock_packet)

    # ------------------------------------------------------------------
    # PHASE 1: DISCOVERY (Node Alpha)
    # ------------------------------------------------------------------
    print("\n[NODE ALPHA] DISCOVERY & ENFORCEMENT")
    shadow_id = "pid:666" # The Shadow (Ungoliant)
    
    # Simulate Taniquetil identifying the shadow as MUTED
    muted_amplitude = ResonanceMapper.from_choir_state(shadow_id, "muted", "Discovery of Dissonance")
    bridge.update_state(shadow_id, muted_amplitude)
    
    print(f"[NODE ALPHA] Tulkas: Attenuating resonance for {shadow_id} to MUTED.")
    
    # ------------------------------------------------------------------
    # PHASE 2: PROPAGATION (The Light of Eärendil)
    # ------------------------------------------------------------------
    print("\n[NODE ALPHA] EÄRENDIL FLOW: Shining Light across the Fabric")
    
    # We simulate Node Alpha shining the light cluster-wide
    # This involves calling the orchestrator
    await earendil.shine_light(shadow_id, muted_amplitude, source_reason="Tulkas Enforcement on Node Alpha")
    
    # ------------------------------------------------------------------
    # PHASE 3: RECEIPT & SYNC (Node Beta)
    # ------------------------------------------------------------------
    print("\n[NODE BETA] EÄRENDIL FLOW: Receiving the Sovereign Summons")
    
    # Structure the message that Node Beta would receive
    mock_summons = {
        "type": "earendil_signal",
        "entity_id": shadow_id,
        "resonance": muted_amplitude.model_dump(),
        "reason": "Tulkas Enforcement on Node Alpha",
        "issuer": "metatron-alpha"
    }
    
    # We call receive_summons on the same orchestrator (simulating Beta's receive path)
    await earendil.receive_summons(mock_summons)
    
    # Verify the sync in the local truth
    synced_state = bridge.get_state(shadow_id)
    print(f"[NODE BETA] Sync Verified: {shadow_id} resonance is {synced_state.constitutional_state.upper()}")
    assert synced_state.constitutional_state == "muted", "Node Beta failed to sync resonance amplitude!"

    # ------------------------------------------------------------------
    # PHASE 4: ENFORCEMENT (The Eyes & Blade on Beta)
    # ------------------------------------------------------------------
    print("\n[NODE BETA] THE EYES & THE BLADE: Substrate Enforcement")
    
    # Now simulate the shadow attempting action on Node Beta
    # The Eyes (Manwë) see the motion
    motion_event = ResonanceEvent(entity_id=shadow_id, action_type="syscall", target="execve")
    
    # Taniquetil deliberates using the Sync'd truth
    print(f"[NODE BETA] Taniquetil: Evaluating intercepted motion for {shadow_id}...")
    verdict = taniquetil.evaluate(motion_event)
    
    assert verdict["allowed"] == False, "Node Beta incorrectly allowed motion for a globally muted shadow!"
    
    # We verify that Mandos on Node Beta remembered the remote summons
    if taniquetil.mandos:
         record = taniquetil.mandos.get_record(shadow_id)
         print(f"[NODE BETA] Mandos Audit: Found {record.denial_count} local denials following global sync.")
         assert record.denial_count >= 1, "Mandos on Node Beta failed to record the enforcement."

    print("\n[+] GAUNTLET COMPLETE: THE GREAT CROSSING IS ESTABLISHED [+]")
    print("Truth is Unified across Arda.")

if __name__ == "__main__":
    asyncio.run(run_the_great_crossing())
