import asyncio
import logging
import uuid
import os
import signal
from typing import Dict, Any

# Arda Core & Valinor Imports
from backend.valinor.runtime_hooks import get_valinor_runtime
from backend.arda.ainur.dissonance import ResonanceMapper, ResonanceStateModel
from backend.services.arda_fabric import get_arda_fabric
from backend.services.arda_fabric_middleware import get_arda_fabric_middleware
from backend.valinor.taniquetil_core import ResonanceEvent

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ValinorGauntlet")

async def run_integrated_gauntlet():
    logger.info("✦ KINDLING THE VALINOR INTEGRATED DESCENT GAUNTLET ✦")
    
    # Initialize Singleton Runtime
    valinor = get_valinor_runtime()
    bridge = valinor.bridge
    taniquetil = valinor.taniquetil
    mandos = taniquetil.mandos
    fabric = get_arda_fabric()
    middleware = get_arda_fabric_middleware()
    forge = get_arda_fabric().forge # Secret Fire Forge

    # Setup a Sovereign Voice for the test
    from backend.arda.ainur.verdicts import IluvatarVoiceChallenge, SecretFirePacket
    voice = IluvatarVoiceChallenge(
        voice_id="ERU-VOICE-GAUNTLET",
        root_nonce="ROOT-1",
        issued_at=0,
        expires_at=2000000000,
        epoch="A",
        sweep_id="SWEEP-1"
    )
    # Patch forge to have this voice active for handshakes
    packet = SecretFirePacket(
        node_id="localhost", covenant_id="C1", voice_id=voice.voice_id,
        nonce="N1", issued_at=0, expires_at=2000000000, responded_at=0.1,
        latency_ms=0, epoch="A", monotonic_counter=1, attestation_digest="A",
        order_digest="O", runtime_digest="R", witness_id="W", witness_signature="S"
    )
    forge.active_nonces["current_packet"] = packet

    # ------------------------------------------------------------------
    # STAGE 0: The Girdle of Melian (Substrate Default)
    # ------------------------------------------------------------------
    logger.info("\n[STAGE 0] THE GIRDLE OF MELIAN: Substrate Verification")
    test_id = f"pid:{os.getpid()}-test"
    initial_state = bridge.get_state(test_id)
    logger.info(f"Integrity Check: Unknown entity '{test_id}' resonance: {initial_state.constitutional_state.upper()}")
    assert initial_state.constitutional_state == "harmonic", "Substrate default must be Harmonic for local PIDs"

    # ------------------------------------------------------------------
    # STAGE 1: Resonance Mapping (Identity & Theme)
    # ------------------------------------------------------------------
    logger.info("\n[STAGE 1] RESONANCE MAPPING: Mapping the Theme of Ungoliant")
    ungoliant_id = "pid:666" # The Shadow
    melkor_id = "pid:1000"   # The Fallen
    
    # Ungoliant starts as Muted
    ungoliant_amplitude = ResonanceMapper.from_choir_state(ungoliant_id, "muted", "Hunger for Light")
    bridge.update_state(ungoliant_id, ungoliant_amplitude)
    
    # Melkor starts as Fallen
    melkor_amplitude = ResonanceMapper.from_choir_state(melkor_id, "fallen", "Unyielding Dissonance")
    bridge.update_state(melkor_id, melkor_amplitude)

    # ------------------------------------------------------------------
    # STAGE 2: Arda-Fabric Attenuation (Movement & Voice)
    # ------------------------------------------------------------------
    logger.info("\n[STAGE 2] THE FABRIC: Attenuation of the Corrupted Voice")
    
    # Test Middleware signing for a Muted entity
    # 1. Establish session first (handshake) to ensure it doesn't clobber the test later
    logger.info("Establishing initial trust session for node-ungoliant...")
    session_id = await fabric.initiate_handshake("node-ungoliant")
    mock_packet = type('obj', (object,), {"tpm_quote": {"pcr_mask": "0,7"}, "voice_id": voice.voice_id})
    res = await fabric.verify_handshake(session_id, mock_packet)
    logger.info(f"Handshake status: {res}")
    
    # 2. Now Mute the already-handshaked peer (The Shadow grows)
    fabric.update_resonance_amplitude("node-ungoliant", ungoliant_amplitude)
    
    mock_headers = {}
    mock_payload = {"action": "consume_light"}
    
    # Check if the middleware now correctly blocks the packet
    final_headers, _ = await middleware.prepare_outbound_request("http://node-ungoliant:3000/api", mock_headers, mock_payload)
    logger.info(f"Fabric Middleware Verdict for Ungoliant: {final_headers.get('X-Arda-Security-Class')}")
    assert final_headers.get("X-Arda-Security-Class") == "fabric_muted", "Muted entities must be silenced in the fabric."

    # ------------------------------------------------------------------
    # STAGE 3: The Eyes of Manwë (Kernel Hooks & Taniquetil)
    # ------------------------------------------------------------------
    logger.info("\n[STAGE 3] THE EYES OF MANWË: Real-time Kernel Evaluation")
    
    # Test 3.1: Valmar Eyes (Syscall)
    logger.info("Evaluating [SYSCALL: execve] for Muted Ungoliant...")
    exec_event = ResonanceEvent(entity_id=ungoliant_id, action_type="syscall", target="execve")
    decision = taniquetil.evaluate(exec_event)
    logger.info(f"Taniquetil Decision: Allowed={decision['allowed']}, Reason={decision['reason']}")
    assert not decision["allowed"], "Gate of Valmar must deny privileged calls to the Muted."

    # Test 3.2: Tirion Eyes (Spawn/Lineage)
    logger.info("Evaluating [SPAWN: fork] child from Ungoliant...")
    spawn_event = ResonanceEvent(entity_id=ungoliant_id, action_type="spawn", metadata={"child_id": "pid:667"})
    try:
        valinor.spawn_process("pid:667", ungoliant_id, "localhost")
    except Exception as e:
        logger.info(f"Tirion correctly severed lineage: {e}")

    # ------------------------------------------------------------------
    # STAGE 4: Gurthang's Severance (Physical Enforcement)
    # ------------------------------------------------------------------
    logger.info("\n[STAGE 4] GURTHANG'S SEVERANCE: The Blade that Drinks the Dark")
    
    # We simulate the server loop logic from kernel_valinor.py
    # If Taniquetil denies and state is Muted/Fallen, does it trigger the blade?
    
    def simulate_blade(entity_id, pid):
        state = bridge.get_state(entity_id).constitutional_state
        if state in ["muted", "fallen"]:
            logger.critical(f"GURTHANG: State [{state.upper()}] detected. PID {pid} is SEVERED.")
            return True
        return False

    assert simulate_blade(melkor_id, 1000), "Gurthang must sever the Fallen."
    assert simulate_blade(ungoliant_id, 666), "Gurthang must sever the Muted."

    # ------------------------------------------------------------------
    # STAGE 5: The Doom of Mandos (Constitutional Memory)
    # ------------------------------------------------------------------
    logger.info("\n[STAGE 5] THE DOOM OF MANDOS: Persistence of Dissonance")
    
    record = mandos.get_record(ungoliant_id)
    logger.info(f"Ungoliant Memory: Denials={record.denial_count}, Fallen Score={record.fallen_score}")
    assert record.denial_count > 0, "Mandos must remember the failures of the Shadow."
    
    # Pushing Melkor to final Doom
    for _ in range(5):
        taniquetil.evaluate(ResonanceEvent(entity_id=melkor_id, action_type="forbidden_act"))
        
    logger.info(f"Melkor Fundamentally Fallen? {mandos.is_fallen(melkor_id)}")
    assert mandos.is_fallen(melkor_id), "Persistent dissonance must lead to absolute exile."

    logger.info("\n✦ GAUNTLET COMPLETE: ARDA REMAINS HARMONIC ✦")

if __name__ == "__main__":
    asyncio.run(run_integrated_gauntlet())
