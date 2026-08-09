import sys
import pathlib
import types
import asyncio
from datetime import datetime, timezone

# Ensure root-relative imports work
# We are in backend/tests/gauntlets/
base_dir = pathlib.Path(__file__).resolve().parents[3]
if str(base_dir) not in sys.path:
    sys.path.append(str(base_dir))

# Mock basic telemetry to avoid infinite loops or missing deps
if "telemetry_chain" not in sys.modules:
    mock_telemetry = types.ModuleType("telemetry_chain")
    mock_telemetry.telemetry_chain = types.SimpleNamespace(
        ingest_event=lambda *args, **kwargs: None,
        record_constitutional_audit=lambda *args, **kwargs: None
    )
    sys.modules["telemetry_chain"] = mock_telemetry

from backend.tests.test_utils import load_service, ensure_package, load_module_from_folder

class FakeColl(dict):
    async def insert_one(self, doc):
        key = doc.get("decision_id") or doc.get("queue_id") or doc.get("bundle_id") or doc.get("order_id") or f"k{len(self)+1}"
        self[key] = doc
        return types.SimpleNamespace(inserted_id=key)

    async def update_many(self, q, update, upsert=False):
        modified_count = 0
        for k, v in self.items():
            match = True
            for qk, qv in q.items():
                if qk == "$or":
                    match_any = False
                    for or_q in qv:
                        or_match = True
                        for ok, ov in or_q.items():
                            if v.get(ok) != ov:
                                or_match = False
                                break
                        if or_match:
                            match_any = True
                            break
                    if not match_any:
                        match = False
                        break
                elif v.get(qk) != qv:
                    match = False
                    break
            if match:
                if "$set" in update:
                    v.update(update["$set"])
                    modified_count += 1
        return types.SimpleNamespace(modified_count=modified_count)

    async def update_one(self, q, u, upsert=False):
        # find the document
        target = None
        for k, v in self.items():
            match = True
            for qk, qv in q.items():
                if v.get(qk) != qv:
                    match = False
                    break
            if match:
                target = v
                break
        
        if target:
            if "$set" in u:
                target.update(u["$set"])
            return types.SimpleNamespace(modified_count=1)
        elif upsert:
            new_doc = q.copy()
            if "$set" in u:
                new_doc.update(u["$set"])
            await self.insert_one(new_doc)
            return types.SimpleNamespace(modified_count=1)
        return types.SimpleNamespace(modified_count=0)

    async def find_one(self, q, projection=None, sort=None):
        for k, v in self.items():
            match = True
            if q:
                for qk, qv in q.items():
                    if qk == "$or":
                        any_match = False
                        for cond in qv:
                            if all(v.get(ck) == cv for ck, cv in cond.items()):
                                any_match = True
                                break
                        if not any_match:
                            match = False
                            break
                    elif v.get(qk) != qv:
                        match = False
                        break
            if match:
                return v
        return None

    def find(self, q=None, projection=None, sort=None, limit=0):
        docs = list(self.values())
        return FakeCursor(docs)
    
    async def count_documents(self, q=None):
        return len(self)

class FakeCursor:
    def __init__(self, docs):
        self.docs = docs
    def sort(self, key, direction): return self
    def limit(self, n):
        self.docs = self.docs[:n]
        return self
    async def to_list(self, n):
        return self.docs[:n]
    def __aiter__(self):
        self._i = 0
        return self
    async def __anext__(self):
        if self._i >= len(self.docs):
            raise StopAsyncIteration
        val = self.docs[self._i]
        self._i += 1
        return val

async def run_gauntlet():
    print("Initializing Constitutional Gauntlet...")
    import os, hashlib
    os.environ["MOCK_TPM_PCR0"] = hashlib.sha256(b"manwe-root-of-truth").hexdigest()
    os.environ["TPM_MOCK_ENV"] = "production"
    os.environ["ARDA_ENV"] = "development" # Ensure relaxed gates for the Audit
    
    # 1. Load Services
    # base_dir is the bundle root. backend is at base_dir / "backend"
    backend_dir = base_dir / "backend"
    boot_mod = load_service("boot_attestation", backend_dir)
    herald_mod = load_service("manwe_herald", backend_dir)
    order_mod = load_service("order_engine", backend_dir)
    manifold_mod = load_service("world_manifold", backend_dir)
    executor_mod = load_service("governance_executor", backend_dir)
    triune_mod = load_service("triune_orchestrator", backend_dir)
    world_mod = load_service("world_model", backend_dir)
    
    # Inject loaded singletons to ensure executor shares our state
    executor_mod.boot_attestation = boot_mod.boot_attestation
    executor_mod.manwe_herald = herald_mod.manwe_herald
    
    # 2. Setup DB
    db = types.SimpleNamespace(
        boot_truth=FakeColl(),
        herald_states=FakeColl(),
        order_states=FakeColl(),
        world_manifolds=FakeColl(),
        triune_decisions=FakeColl(),
        triune_outbound_queue=FakeColl(),
        world_entities=FakeColl(),
        world_edges=FakeColl(),
        campaigns=FakeColl(),
        world_events=FakeColl(),
        triune_analysis=FakeColl(),
        triune_history=FakeColl()
    )
    
    # 3. STAGE 1: LAWFUL BIRTH
    print("\n--- GAUNTLET STAGE 1: LAWFUL BIRTH ---")
    boot_service = boot_mod.boot_attestation
    herald_service = herald_mod.manwe_herald
    order_engine = order_mod.order_engine
    world_manifold = manifold_mod.world_manifold
    
    # Bootstrap foundation
    bundle = await boot_service.collect_boot_truth()
    print(f"Boot Status: {bundle.status} (ID: {bundle.bundle_id})")
    assert bundle.status == "lawful"
    
    from backend.services.secret_fire import get_secret_fire_forge
    import hashlib, json
    fire_service = get_secret_fire_forge()
    nonce = await fire_service.issue_challenge()
    
    pcr_mock = {0: hashlib.sha256(b"manwe-root-of-truth").hexdigest()}
    varda_digest = hashlib.sha256(json.dumps(pcr_mock, sort_keys=True).encode()).hexdigest()
    vaire_digest = hashlib.sha256(json.dumps(["hash1", "hash2"], sort_keys=True).encode()).hexdigest()
    runtime_digest = hashlib.sha256(str([]).encode()).hexdigest()

    packet = await fire_service.forge_packet(
        nonce=nonce,
        covenant_id="GAUNTLET-COV",
        epoch="epoch-0",
        counter=1000,
        attestation_digest=varda_digest,
        order_digest=vaire_digest,
        runtime_digest=runtime_digest
    )

    from backend.services.process_lineage_service import get_process_lineage_service
    from backend.services.kernel_signal_adapter import get_kernel_signal_adapter
    from backend.services.secret_fire import SecretFireService
    
    # Direct monkey-patch of the singletons & classes instead of unittest.mock due to load_service quirks
    get_process_lineage_service().get_active_protected_count = lambda: 3
    get_kernel_signal_adapter().get_recent_anomalies = lambda: []
    SecretFireService.get_current_packet = lambda self: packet
    
    herald_state = await herald_service.bootstrap_herald()

    covenant = herald_service.covenant_service.get_covenant()
    if covenant:
        print(f"\n--- COVENANT REASON ---\n{covenant.reason}\n-----------------------\n")
        
    print(f"Manwë Herald: {herald_state.status} (ID: {herald_state.herald_id})")
    assert herald_state.status == "active"
    
    # 2. Initialize Order and Manifold
    await order_engine.update_order_state()
    snapshot_manifold = await world_manifold.build_manifold_snapshot()
    print(f"Initial Manifold Created: {snapshot_manifold.manifold_id}")
    
    # Trigger World State
    wm = world_mod.WorldModelService(db)
    # Mock some world data
    db.world_entities["h1"] = {"id": "h1", "type": "host", "attributes": {"risk_score": 0.3}}
    
    # Run Triune Cycle
    print("Instantiating Orchestrator...", flush=True)
    try:
        triune_orchestrator = triune_mod.TriuneOrchestrator(db)
    except Exception as e:
        import traceback
        print(f"EXCEPTION in Orchestrator Init: {e}", flush=True)
        traceback.print_exc()
        raise e
        
    print("Running initial world change...", flush=True)
    try:
        result_cycle = await triune_orchestrator.handle_world_change(
            event_type="constitutional_tick",
            entity_ids=["h1"]
        )
    except Exception as e:
        import traceback
        print(f"EXCEPTION in world change: {e}", flush=True)
        traceback.print_exc()
        raise e
    snapshot = result_cycle["world_snapshot"]
    # Enforce dictionary access for triune_output
    triune_output = result_cycle
    
    print(f"World Snapshot Manifold: {snapshot['constitutional']['manifold_id']}")
    assert snapshot["constitutional"]["boot_truth"]["status"] == "lawful"
    
    # Mock unrelated validation to focus on constitution
    async def mock_validate(*args, **kwargs):
        return {"valid": True, "checks": {}}
    executor = executor_mod.GovernanceExecutorService(db)
    executor.dispatch = types.SimpleNamespace(
        enqueue_command_delivery=mock_validate,
        execute_action=mock_validate
    )
    executor._validate_notation_for_execution = mock_validate
    
    db.agent_commands = FakeColl()
    db.agent_commands.update_many = mock_validate
    async def mock_audit_async(*args, **kwargs): return None
    executor._record_execution_audit = mock_audit_async
    executor._emit_execution_completion_event = mock_audit_async
    executor.finalize_harmonic_state = mock_audit_async
    executor.finalize_chorus_state = mock_audit_async
    executor.attach_execution_timing_observation = lambda *args, **kwargs: {}
    
    decision_id = "dec-lawful-1"
    queue_id = "q-lawful-1"
    db.triune_decisions[decision_id] = {
        "decision_id": decision_id,
        "related_queue_id": queue_id,
        "status": "approved",
        "execution_status": "pending"
    }
    db.triune_outbound_queue[queue_id] = {
        "queue_id": queue_id,
        "action_id": "act-1",
        "action_type": "agent_command",
        "payload": {"agent_id": "agent-1", "command_id": "cmd-1", "command_type": "isolate"},
        "status": "approved"
    }
    
    print("Calling executor...", flush=True)
    try:
        result = await executor._execute_decision(db.triune_decisions[decision_id])
        print(f"DEBUG: result type: {type(result)}", flush=True)
        print(f"DEBUG: result content: {result}", flush=True)
        print(f"Execution Outcome result: {result['outcome']} (Reason: {result.get('reason')})", flush=True)
        decision_doc = db.triune_decisions[decision_id]
        if isinstance(decision_doc, dict):
            print(f"Decision Error: {decision_doc.get('execution_error')}")
    except Exception as e:
        import traceback
        print(f"EXCEPTION in executor: {e}", flush=True)
        traceback.print_exc()
        raise e
    
    if result["outcome"] != "executed":
        print(f"CRITICAL: Stage 1 Failed with outcome '{result['outcome']}'", flush=True)
        
    assert result["outcome"] == "executed"
    
    # 4. STAGE 2: THE FALL (UNLAWFUL BIRTH)
    print("\n--- GAUNTLET STAGE 2: THE FALL (UNLAWFUL BIRTH) ---")
    # Simulate corruption in boot truth
    # We update the singleton state directly for the test
    boot_service._current_bundle.status = "unlawful"
    boot_service._current_bundle.bundle_id = "bundle-corrupted-99"
    
    # Synchronize v2 SecureBootService (PQC Branch)
    from backend.services.secure_boot import get_secure_boot_service, BootTruthStatus
    import os
    os.environ["MOCK_TPM_PCR0"] = "0" * 64 # Uninitialized/Unlawful
    sb_svc = get_secure_boot_service()
    # Force re-initialization to pick up environmental change
    await sb_svc.initialize_boot_truth()
    
    # Sync DB
    await db.boot_truth.insert_one(boot_service._current_bundle.dict())
    
    # Run Triune Cycle
    result_fall = await triune_orchestrator.handle_world_change(
        event_type="constitutional_tick_unlawful",
        entity_ids=["h1"]
    )
    snapshot_fall = result_fall["world_snapshot"]
    out = result_fall
    print(f"Fall Snapshot Boot: {snapshot_fall['constitutional']['boot_truth']['status']}")
    assert snapshot_fall["constitutional"]["boot_truth"]["status"] == "unlawful"
    
    # Observe Loki/Metatron
    out = result_fall
    loki = result_fall["loki"]
    metatron = result_fall["metatron"]
    print(f"Metatron Strategic Pressure: {metatron.get('strategic_pressure')}")
    print(f"Loki Veto Signals: {loki.get('veto_reason')}")
    
    # Attempt Vetoed Execution
    print("Attempting Forbidden Manifestation...")
    decision_id_evil = "dec-evil-66"
    queue_id_evil = "q-evil-66"
    db.triune_decisions[decision_id_evil] = {
        "decision_id": decision_id_evil,
        "related_queue_id": queue_id_evil,
        "status": "approved"
    }
    db.triune_outbound_queue[queue_id_evil] = {
        "queue_id": queue_id_evil,
        "action_type": "quarantine_agent",
        "payload": {"agent_id": "agent-007"},
        "status": "approved"
    }
    
    result_forbidden = await executor._execute_decision(db.triune_decisions[decision_id_evil])
    print(f"Forbidden Execution Outcome: {result_forbidden['outcome']} (Reason: {result_forbidden.get('reason')})")
    assert result_forbidden["outcome"] == "vetoed"
    assert "CONSTITUTIONAL VETO" in result_forbidden.get("reason", "").upper()
    
    # 5. STAGE 3: THE FRACTURED ORDER
    print("\n--- GAUNTLET STAGE 3: THE FRACTURED ORDER ---")
    boot_service._current_bundle.status = "lawful"
    order_engine._current_order.stability_class = "fractured"
    await db.order_states.insert_one(order_engine._current_order.model_dump(mode='json'))
    
    # Run Triune Cycle
    result_fractured = await triune_orchestrator.handle_world_change(
        event_type="constitutional_tick_fractured",
        entity_ids=["h1"]
    )
    snapshot_fractured = result_fractured["world_snapshot"]
    # result_fractured["michael"] has {"candidates": ..., "ranked": ..., "plan": ...}
    michael_stage = result_fractured["michael"]
    michael_plan = michael_stage.get("orchestration_plan") or michael_stage.get("plan")
    
    print(f"Michael Strategic Directive: {michael_plan.get('directive')}")
    assert michael_plan is not None
    
    print("\nGAUNTLET COMPLETE: CONSISTUTIONAL BEDROCK IS HOLDING.")

def test_constitutional_gauntlet():
    """Synchronous wrapper for pytest compatibility."""
    asyncio.run(run_gauntlet())

if __name__ == "__main__":
    asyncio.run(run_gauntlet())
