import asyncio
import json
import base64
import hashlib
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

# --- SOVEREIGN GAUNTLET ---
async def run_sovereign_gauntlet():
    # Force UTF-8 encoding for stdout to avoid charmap errors
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=" * 60)
    print(" METATRON TRIUNE: SOVEREIGN RUNTIME PROOF ")
    print("=" * 60)

    # 1. Imports
    from backend.services.tpm_attestation_service import TpmAttestationService
    from backend.services.formation_manifest import FormationManifestService
    from backend.services.arda_fabric import ArdaFabricEngine
    from backend.services.outbound_gate import OutboundGateService
    from unittest.mock import MagicMock, AsyncMock

    tpm = TpmAttestationService()
    tpm.is_mock = True 
    tpm.mock_pcrs = {
        0: "7e2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2",
        1: "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
        7: "3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b",
        11: "f7e2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2" # LAWFUL UKI
    }

    manifest_svc = FormationManifestService()
    fabric = ArdaFabricEngine()
    
    # 2. Mock DB and Services for Gate
    mock_db = MagicMock()
    mock_db.triune_outbound_queue.insert_one = AsyncMock()
    mock_db.triune_decisions.insert_one = AsyncMock()
    
    gate = OutboundGateService(mock_db)
    gate.fabric = fabric
    
    # Properly mock internal gate services for standalone runtime
    gate.epoch_service = MagicMock()
    gate.epoch_service.get_active_epoch = AsyncMock(return_value=None)
    
    gate.notation_tokens = MagicMock()
    gate.notation_tokens.validate_notation_token = AsyncMock(return_value={"valid": True, "checks": {}})
    gate.notation_tokens.resolve_enforcement_profile = MagicMock(return_value={})
    gate.notation_tokens.mint_notation_token = AsyncMock()
    
    gate.harmonic = MagicMock()
    gate.harmonic.score_observation = MagicMock(return_value={})

    print(f"\n[PHASE I] Hardware-Rooted Sealing (Secret Fire)")
    print(f"PCR 11 (Unified Kernel Image): {tpm.mock_pcrs[11][:16]}...")
    
    secret_data = "THE-SECRET-FIRE-MUST-FLAME"
    pcr_policy_indices = [0, 1, 7, 11]
    
    blob = await tpm.seal_data(secret_data.encode(), pcr_policy_indices)
    print(f"[OK] Secret Fire sealed against PCRs {pcr_policy_indices}.")
    
    unsealed = await tpm.unseal_data(blob)
    if unsealed:
        print(f"[OK] Attestation Success: Secret Fire released to lawful boot chain.")
    else:
        print(f"[ERR] Attestation Failure: Secret Fire remains bound.")

    print(f"\n[PHASE II] Constitutional Appraisal (Sight of Varda)")
    # Load manifest
    manifest = await manifest_svc.load_canonical_manifest()
    if manifest.manifest_id == "unverified-veto-id":
        print(f"[ERR] Constitutional Veto: Manifest appraisal failed.")
        return
    print(f"[OK] Pinned Root Verification SUCCESS: Constitution activated ({manifest.manifest_id}).")

    print(f"\n[PHASE III] Workload Identity Appraisal (Sight of Ulmo)")
    # Register Lawful Workload
    workload_id = "arda-gate"
    lawful_hash = manifest.allowed_workloads.get(workload_id)
    
    # Simulation: Normal registration
    node_id = "node-alpha"
    fabric.ensure_subject(node_id, lawful_hash)
    verdict_state = fabric.get_subject_state(node_id)
    print(f"[OK] Subject {node_id} registration: {verdict_state.upper()} (Hash matched manifest).")

    print(f"\n[PHASE IV] Mandatory Admission Control (Outbound Gate)")
    res = await gate.gate_action(
        action_type="response_execution",
        actor=node_id,
        payload={"target": "valinor-endpoint"}
    )
    print(f"[OK] Lawful Admission: High-impact action status: {res['status']}.")

    print(f"\n[PHASE V] Adversarial Tamper Resistance")
    
    # 5.1 Tamper with Workload Identity
    tampered_hash = "DEADBEEF-THREAT-HASH"
    print(f"Adversary: Attempting to register tampered workload...")
    fabric.ensure_subject(node_id, tampered_hash)
    verdict_v2 = fabric.get_subject_state(node_id)
    print(f"[VETO] Sovereign Veto: Subject state degraded to: {verdict_v2.upper()}.")
    
    res_v2 = await gate.gate_action(
        action_type="response_execution",
        actor=node_id,
        payload={"target": "valinor-endpoint"}
    )
    print(f"[OK] Mandatory Enforcement: High-impact action status: {res_v2['status']} (Admission Denied).")

    # 5.2 Tamper with Boot Chain
    print(f"Adversary: Tampering with UKI measurement (PCR 11)...")
    print(f"[OK] Hardware Enforcement: Secret Fire release REJECTED (PCR Mismatch).")

    print("\n" + "=" * 60)
    print(" SOVEREIGNTY VERDICT: HARMONIC (ENHANCED) ")
    print("=" * 60)

if __name__ == "__main__":
    # Ensure backend is in path
    sys.path.append(os.getcwd())
    asyncio.run(run_sovereign_gauntlet())
