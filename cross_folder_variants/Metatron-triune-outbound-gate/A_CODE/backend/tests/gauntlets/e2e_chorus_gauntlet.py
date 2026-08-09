import sys
import os
import asyncio
import logging
import hashlib
import uuid
from typing import Any, Dict
from datetime import datetime, timezone

# Add backend to path
sys.path.append(os.getcwd())

from backend.services.secure_boot import get_secure_boot_service
from backend.services.handoff_covenant import get_handoff_covenant_service
from backend.services.manwe_herald import manwe_herald
from backend.services.resonance_engine import get_resonance_engine
from backend.services.metatron_heartbeat import get_metatron_heartbeat
from backend.services.world_manifold import world_manifold
from backend.services.governance_executor import GovernanceExecutorService
from backend.schemas.phase3_models import ResonanceStatus, HeartbeatProof

class MockCollection:
    async def insert_one(self, *args, **kwargs): return type('Result', (), {'inserted_id': uuid.uuid4().hex})
    async def update_one(self, *args, **kwargs): return type('Result', (), {'modified_count': 1, 'matched_count': 1})
    async def update_many(self, *args, **kwargs): return type('Result', (), {'modified_count': 1, 'matched_count': 1})
    async def count_documents(self, *args, **kwargs): return 1
    async def find_one(self, *args, **kwargs): return None
    def find(self, *args, **kwargs): return self
    async def to_list(self, *args, **kwargs): return []
    def sort(self, *args, **kwargs): return self
    def limit(self, *args, **kwargs): return self
    def __aiter__(self):
        self._iter_data = iter([])
        return self
    async def __anext__(self):
        try: return next(self._iter_data)
        except StopIteration: raise StopAsyncIteration

class MockDB:
    def __init__(self):
        self.boot_truth_audit = MockCollection()
        self.triune_outbound_queue = MockCollection()
        self.triune_decisions = MockCollection()
        self.entities = MockCollection()
        self.world_entities = MockCollection()
        self.world_edges = MockCollection()
        self.campaigns = MockCollection()
        self.governance_epoch_audit = MockCollection()

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("Chorus_Gauntlet")

async def main():
    print("\n--- PHASE III: THE CHORUS GAUNTLET ---")
    db = MockDB()
    executor = GovernanceExecutorService(db)
    resonance = get_resonance_engine(db)
    heartbeat = get_metatron_heartbeat(db)
    
    # 1. LAWFUL STARTUP
    os.environ["MOCK_TPM_PCR0"] = hashlib.sha256(b"manwe-root-of-truth").hexdigest()
    print("[1] Bootstrapping Lawful Node...")
    await manwe_herald.bootstrap_herald()
    await heartbeat.emit_now() # Start at 100%
    
    # Pre-register target agent so quarantine doesn't fail on identity check
    from backend.services.identity import identity_service, WorkloadIdentity, TrustState
    
    identity_service.identities["target-0"] = WorkloadIdentity(
        spiffe_id="spiffe://seraph/agent/target-0",
        agent_id="target-0",
        hostname="mock-agent",
        os_type="linux",
        cert_fingerprint="mock-fp",
        issued_at=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
        attestation={},
        trust_state=TrustState.TRUSTED,
        trust_score=100
    )
    
    # 2. SUCCESSFUL EXECUTION (HEART IS RESONANT)
    print("[2] Executing Lawful Action (Resonant Union)...")
    res1 = await executor._execute_domain_operation(
        decision={"decision_id": "dec-lawful"},
        queue_doc={"queue_id": "q-lawful"},
        payload={"agent_id": "target-0"},
        actor="gauntlet_operator",
        action_type="quarantine_agent"
    )
    print(f"    Outcome: {res1.get('outcome')} (Expected: executed)")
    
    # 3. INDUCE DISSONANCE (THE ATTACK ON THE CHORUS)
    print("\n[3] !!! SIMULATING NETWORK DISSONANCE (PEER COMPROMISED) !!!")
    # We simulate another peer node sending a fractured heartbeat to tank the collective score
    peer_proof = HeartbeatProof(
        proof_id="hb-compromised-peer",
        node_id="peer-node-alpha",
        manifold_state_hash="tampered-hash",
        order_pulse_ref="missing-ref",
        signature="invalid-sig",
        status=ResonanceStatus.FRACTURED
    )
    await resonance.record_heartbeat(peer_proof)
    
    manifold = await world_manifold.build_manifold_snapshot()
    print(f"    Cluster Health: {manifold.triune_health_score * 100}%")
    
    # 4. FAILED EXECUTION (LOGICALLY VETOED BY CHORUS)
    print("[4] Attempting Execution on Lawful local node during Network Dissonance...")
    res2 = await executor._execute_domain_operation(
        decision={"decision_id": "dec-blocked"},
        queue_doc={"queue_id": "q-blocked"},
        payload={"agent_id": "target-0"},
        actor="gauntlet_operator",
        action_type="quarantine_agent"
    )
    print(f"    Outcome: {res2.get('outcome')} (Expected: vetoed)")
    print(f"    Reason: {res2.get('reason')}")
    
    # 5. RESTORE HARMONY
    print("\n[5] Restoring Harmony (Peer Node Sanitized)...")
    peer_proof.status = ResonanceStatus.RESONANT
    await resonance.record_heartbeat(peer_proof)
    
    manifold_v3 = await world_manifold.build_manifold_snapshot()
    print(f"    Restored Health: {manifold_v3.triune_health_score * 100}%")
    
    # 6. SUCCESSFUL EXECUTION (UNION REGAINED)
    print("[6] Re-executing Action...")
    res3 = await executor._execute_domain_operation(
        decision={"decision_id": "dec-recovered"},
        queue_doc={"queue_id": "q-recovered"},
        payload={"agent_id": "target-0"},
        actor="gauntlet_operator",
        action_type="quarantine_agent"
    )
    print(f"    Outcome: {res3.get('outcome')} (Expected: executed)")
    
    print("\n--- GAUNTLET COMPLETE: THE TRIUNE CHORUS HAS SPOKEN ---")
    await heartbeat.stop()

def test_chorus_gauntlet():
    """Synchronous wrapper for pytest compatibility."""
    asyncio.run(main())

if __name__ == "__main__":
    main()
