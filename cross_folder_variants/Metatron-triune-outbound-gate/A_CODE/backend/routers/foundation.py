"""
Foundation Services Router
==========================
Exposes remaining foundational services with fail-closed optional wiring.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from .dependencies import check_permission, get_current_user, get_db

try:
    from services.alqualonde_teleri import EareFlowGovernor
except Exception:
    EareFlowGovernor = None

try:
    from services.arda_bombadil import require_lawful, run_check
except Exception:
    require_lawful = None
    run_check = None

try:
    from services.arda_fabric_middleware import get_arda_fabric_middleware
except Exception:
    get_arda_fabric_middleware = None

try:
    from services.chorus_engine import get_chorus_engine
except Exception:
    get_chorus_engine = None

try:
    from services.chorus_transport import get_chorus_transport
except Exception:
    get_chorus_transport = None

try:
    from services.earendil_flow import get_earendil_flow
except Exception:
    get_earendil_flow = None

try:
    from services.flame_imperishable import get_flame_imperishable_service
except Exception:
    get_flame_imperishable_service = None

try:
    from services.gates_of_night import get_boundary_guard
except Exception:
    get_boundary_guard = None

try:
    from services.genesis_score import get_genesis_score_service
except Exception:
    get_genesis_score_service = None

try:
    from services.handoff_covenant import get_handoff_covenant_service
except Exception:
    get_handoff_covenant_service = None

try:
    from services.lawful_handoff import get_lawful_handoff
except Exception:
    get_lawful_handoff = None

try:
    from services.mandos_context import get_mandos_context_service
except Exception:
    get_mandos_context_service = None

try:
    from services.preboot_state_sealer import get_preboot_state_sealer
except Exception:
    get_preboot_state_sealer = None

try:
    from services.presence_fastapi import health as presence_health
except Exception:
    presence_health = None

try:
    from services.presence_grounding import get_grounding_service
except Exception:
    get_grounding_service = None

try:
    from services.presence_server import fallback_response, ollama_health
except Exception:
    fallback_response = None
    ollama_health = None

try:
    from services.restoration_controller import RestorationController
except Exception:
    RestorationController = None

try:
    from services.secure_boot import get_secure_boot_service
except Exception:
    get_secure_boot_service = None

try:
    from services.service_heartbeat import ServiceHeartbeat
except Exception:
    ServiceHeartbeat = None

try:
    from services.zpd_shaper import get_zpd_shaper
except Exception:
    get_zpd_shaper = None

router = APIRouter(prefix="/foundation", tags=["Foundation Services"])


@router.get("/alqualonde/flow")
async def shape_alqualonde_flow(
    entity_id: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Shape outbound flow decisions through Alqualonde governance."""
    if not EareFlowGovernor:
        raise HTTPException(status_code=501, detail="Alqualonde service not available")

    try:
        decision = EareFlowGovernor().shape_flow(entity_id)
        return {"success": True, "entity_id": entity_id, "decision": decision}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flow shaping failed: {str(e)}")


@router.post("/bombadil/lawful")
async def verify_bombadil_lawful(
    current_user: dict = Depends(check_permission("read")),
):
    """Query Bombadil lawful status gate."""
    if not require_lawful:
        raise HTTPException(status_code=501, detail="Bombadil service not available")

    try:
        verdict = require_lawful()
        return {"success": True, "lawful": verdict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bombadil lawful check failed: {str(e)}")


@router.post("/bombadil/check")
async def run_bombadil_check(
    config: Dict[str, Any] | None = None,
    current_user: dict = Depends(check_permission("read")),
):
    """Run Bombadil covenant check chain."""
    if not run_check:
        raise HTTPException(status_code=501, detail="Bombadil checker not available")

    try:
        result = run_check(config or {})
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bombadil check failed: {str(e)}")


@router.post("/fabric/verify")
async def verify_arda_fabric_inbound(
    node_id: str,
    headers: Dict[str, Any] | None = None,
    body: Dict[str, Any] | None = None,
    current_user: dict = Depends(check_permission("read")),
):
    """Verify inbound ARDA fabric request authenticity."""
    if not get_arda_fabric_middleware:
        raise HTTPException(status_code=501, detail="ARDA fabric middleware not available")

    try:
        middleware = get_arda_fabric_middleware()
        valid = middleware.verify_inbound_request(node_id, headers or {}, body or {})
        return {"success": True, "node_id": node_id, "valid": valid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fabric verification failed: {str(e)}")


@router.get("/chorus/state")
async def get_chorus_state(
    current_user: dict = Depends(get_current_user),
):
    """Get assembled chorus state from the resonance chorus engine."""
    if not get_chorus_engine:
        raise HTTPException(status_code=501, detail="Chorus engine not available")

    try:
        engine = get_chorus_engine()
        state = engine.assemble_chorus_state()
        return {"success": True, "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chorus state retrieval failed: {str(e)}")


@router.post("/chorus/broadcast")
async def broadcast_chorus_envelope(
    envelope: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Broadcast a chorus transport envelope."""
    if not get_chorus_transport:
        raise HTTPException(status_code=501, detail="Chorus transport not available")

    try:
        transport = get_chorus_transport()
        await transport.broadcast_envelope(envelope)
        return {"success": True, "broadcasted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chorus broadcast failed: {str(e)}")


@router.post("/earendil/shine")
async def invoke_earendil_shine(
    entity_id: str,
    budget: float = 1.0,
    source_reason: str = "manual",
    current_user: dict = Depends(check_permission("write")),
):
    """Invoke Earendil flow orchestration."""
    if not get_earendil_flow:
        raise HTTPException(status_code=501, detail="Earendil flow not available")

    try:
        orchestrator = get_earendil_flow()
        result = await orchestrator.shine_light(entity_id, budget, source_reason)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Earendil invocation failed: {str(e)}")


@router.get("/flame/key")
async def get_flame_key(
    current_user: dict = Depends(check_permission("read")),
):
    """Get the active flame-imperishable key material."""
    if not get_flame_imperishable_service:
        raise HTTPException(status_code=501, detail="Flame service not available")

    try:
        flame = get_flame_imperishable_service()
        key = flame.get_key()
        return {"success": True, "key": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flame key retrieval failed: {str(e)}")


@router.post("/gates/egress")
async def evaluate_gates_of_night(
    target_url: str,
    request_metadata: Dict[str, Any] | None = None,
    current_user: dict = Depends(check_permission("read")),
):
    """Evaluate outbound gate policy before egress."""
    if not get_boundary_guard:
        raise HTTPException(status_code=501, detail="Gates of Night service not available")

    try:
        guard = get_boundary_guard()
        verdict = guard.evaluate_egress(target_url, request_metadata or {})
        return {"success": True, "target_url": target_url, "verdict": verdict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gate evaluation failed: {str(e)}")


@router.get("/genesis/score")
async def get_genesis_score(
    db: Any = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get current genesis score."""
    if not get_genesis_score_service:
        raise HTTPException(status_code=501, detail="Genesis score service not available")

    try:
        service = get_genesis_score_service(db)
        score = await service.get_score()
        return {"success": True, "score": score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Genesis score retrieval failed: {str(e)}")


@router.post("/handoff/covenant/seal")
async def seal_handoff_covenant(
    db: Any = Depends(get_db),
    current_user: dict = Depends(check_permission("write")),
):
    """Seal a lawful handoff covenant."""
    if not get_handoff_covenant_service:
        raise HTTPException(status_code=501, detail="Handoff covenant service not available")

    try:
        service = get_handoff_covenant_service(db)
        covenant = await service.seal_covenant()
        return {"success": True, "covenant": covenant}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Covenant sealing failed: {str(e)}")


@router.get("/handoff/lawful/verify")
async def verify_lawful_handoff(
    db: Any = Depends(get_db),
    current_user: dict = Depends(check_permission("read")),
):
    """Verify lawful handoff preconditions."""
    if not get_lawful_handoff:
        raise HTTPException(status_code=501, detail="Lawful handoff service not available")

    try:
        service = get_lawful_handoff(db)
        verification = await service.verify_handoff()
        return {"success": True, "verification": verification}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lawful handoff verification failed: {str(e)}")


@router.get("/mandos/context")
async def get_mandos_context(
    current_topic: str,
    n_encounters: int = 5,
    current_user: dict = Depends(check_permission("read")),
):
    """Build Mandos pre-response context."""
    if not get_mandos_context_service:
        raise HTTPException(status_code=501, detail="Mandos context service not available")

    try:
        service = get_mandos_context_service()
        context = await service.build_context(current_topic, n_encounters)
        return {"success": True, "context": context.model_dump(mode="json")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mandos context build failed: {str(e)}")


@router.post("/preboot/seal")
async def seal_preboot_state(
    current_user: dict = Depends(check_permission("write")),
):
    """Generate and seal a preboot covenant state."""
    if not get_preboot_state_sealer:
        raise HTTPException(status_code=501, detail="Preboot sealer service not available")

    try:
        sealer = get_preboot_state_sealer()
        covenant = sealer.generate_lawful_covenant()
        blob = sealer.seal_covenant(covenant)
        return {"success": True, "sealed": True, "size": len(blob)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preboot sealing failed: {str(e)}")


@router.get("/presence/health")
async def get_presence_health(
    current_user: dict = Depends(get_current_user),
):
    """Return health from the standalone presence FastAPI service module."""
    if not presence_health:
        raise HTTPException(status_code=501, detail="Presence service not available")

    try:
        result = await presence_health()
        return {"success": True, "health": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presence health failed: {str(e)}")


@router.get("/presence/grounding")
async def ground_presence_query(
    query: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Evaluate grounding necessity against local presence vault search results."""
    if not get_grounding_service:
        raise HTTPException(status_code=501, detail="Presence grounding service not available")

    try:
        grounding = get_grounding_service()
        local_results = grounding.search_local_vault(query)
        verdict = grounding.evaluate_necessity(query, local_results)
        return {
            "success": True,
            "query": query,
            "local_results": local_results,
            "necessity": verdict,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presence grounding failed: {str(e)}")


@router.get("/presence/server-health")
async def get_presence_server_health(
    current_user: dict = Depends(get_current_user),
):
    """Return health from the presence server orchestration module."""
    if not ollama_health:
        raise HTTPException(status_code=501, detail="Presence server not available")

    try:
        health = ollama_health()
        return {"success": True, "server_health": health}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presence server health failed: {str(e)}")


@router.post("/presence/fallback")
async def get_presence_fallback(
    directive: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Generate a fallback response through the presence server chain."""
    if not fallback_response:
        raise HTTPException(status_code=501, detail="Presence fallback service not available")

    try:
        response = fallback_response(directive)
        return {"success": True, "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presence fallback generation failed: {str(e)}")


@router.post("/restoration/plea")
async def submit_restoration_plea(
    command_name: str,
    principal: str,
    manifest_path: str,
    secure_storage: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Submit restoration plea for fractured command integrity."""
    if not RestorationController:
        raise HTTPException(status_code=501, detail="Restoration controller not available")

    try:
        controller = RestorationController(manifest_path=manifest_path, secure_storage=secure_storage)
        restored = await controller.plea_for_restoration(command_name, principal)
        return {"success": True, "restored": restored}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restoration plea failed: {str(e)}")


@router.get("/secure-boot/truth")
async def get_secure_boot_truth(
    db: Any = Depends(get_db),
    current_user: dict = Depends(check_permission("read")),
):
    """Get current secure boot truth bundle."""
    if not get_secure_boot_service:
        raise HTTPException(status_code=501, detail="Secure boot service not available")

    try:
        service = get_secure_boot_service(db)
        truth = await service.get_current_truth()
        return {"success": True, "truth": truth.model_dump(mode="json")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Secure boot truth failed: {str(e)}")


@router.post("/heartbeat/start")
async def start_service_heartbeat(
    db: Any = Depends(get_db),
    current_user: dict = Depends(check_permission("write")),
):
    """Start foundation heartbeat telemetry loop."""
    if not ServiceHeartbeat:
        raise HTTPException(status_code=501, detail="Service heartbeat not available")

    try:
        heartbeat = ServiceHeartbeat(db)
        await heartbeat.start()
        return {"success": True, "running": heartbeat.running}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Heartbeat start failed: {str(e)}")


@router.post("/heartbeat/stop")
async def stop_service_heartbeat(
    db: Any = Depends(get_db),
    current_user: dict = Depends(check_permission("write")),
):
    """Stop foundation heartbeat telemetry loop."""
    if not ServiceHeartbeat:
        raise HTTPException(status_code=501, detail="Service heartbeat not available")

    try:
        heartbeat = ServiceHeartbeat(db)
        await heartbeat.stop()
        return {"success": True, "running": heartbeat.running}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Heartbeat stop failed: {str(e)}")


@router.get("/zpd/estimate")
async def estimate_zpd(
    current_topic: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Estimate ZPD for current topic using default safe context payloads."""
    if not get_zpd_shaper:
        raise HTTPException(status_code=501, detail="ZPD shaper service not available")

    try:
        shaper = get_zpd_shaper()
        estimate = shaper.estimate_zpd(
            resonance_profile={},
            calibration=None,
            encounter_history=[],
            current_topic=current_topic,
        )
        return {"success": True, "estimate": estimate.model_dump(mode="json")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ZPD estimate failed: {str(e)}")