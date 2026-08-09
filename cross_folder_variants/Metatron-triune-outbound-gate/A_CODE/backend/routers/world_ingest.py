from fastapi import APIRouter, Depends, HTTPException
from routers.dependencies import get_db, require_machine_token
from backend.services.world_model import WorldEntity, WorldEdge, WorldModelService
from backend.services.world_events import emit_world_event
from typing import Dict, Any

router = APIRouter(prefix="/ingest", tags=["World Ingest"])
verify_world_ingest_token = require_machine_token(
    env_keys=["WORLD_INGEST_TOKEN", "INTEGRATION_API_KEY", "SWARM_AGENT_TOKEN"],
    header_names=["x-world-ingest-token", "x-internal-token", "x-agent-token"],
    subject="world ingest",
)


def _entity_from_payload(payload: Dict[str, Any]) -> WorldEntity:
    try:
        return WorldEntity(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _edge_from_payload(payload: Dict[str, Any]) -> WorldEdge:
    try:
        return WorldEdge(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/entity")
async def ingest_entity(payload: Dict[str, Any], auth: Dict[str, Any] = Depends(verify_world_ingest_token), db=Depends(get_db)):
    """Generic entity ingestion endpoint.  Body should match WorldEntity model."""
    wm = WorldModelService(db)
    entity = _entity_from_payload(payload)
    await wm.upsert_entity(entity)
    # after upsert, recalc risk
    if hasattr(wm, "calculate_risk"):
        await wm.calculate_risk(entity.id)
    triune = await emit_world_event(db, event_type="entity_ingested", entity_refs=[entity.id], payload=payload)
    return {"status": "ok", "id": entity.id, "triune": triune.get("triune")}

@router.post("/edge")
async def ingest_edge(payload: Dict[str, Any], auth: Dict[str, Any] = Depends(verify_world_ingest_token), db=Depends(get_db)):
    """Create relationship between two entities."""
    wm = WorldModelService(db)
    edge = _edge_from_payload(payload)
    await wm.add_edge(edge)
    triune = await emit_world_event(db, event_type="edge_ingested", entity_refs=[edge.source, edge.target], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@router.post("/detection")
async def ingest_detection(payload: Dict[str, Any], auth: Dict[str, Any] = Depends(verify_world_ingest_token), db=Depends(get_db)):
    """Ingest a detection hit and update entity attributes accordingly."""
    wm = WorldModelService(db)
    eid = payload.get("entity_id")
    if not eid:
        raise HTTPException(status_code=400, detail="entity_id required")
    # append detection record to entity attributes
    await wm.entities.update_one({"id": eid}, {"$push": {"attributes.detections": payload}}, upsert=True)
    if hasattr(wm, "calculate_risk"):
        await wm.calculate_risk(eid)
    triune = await emit_world_event(db, event_type="detection_ingested", entity_refs=[eid], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@router.post("/alert")
async def ingest_alert(payload: Dict[str, Any], auth: Dict[str, Any] = Depends(verify_world_ingest_token), db=Depends(get_db)):
    """Ingest an alert and create/update the corresponding entity."""
    wm = WorldModelService(db)
    eid = payload.get("entity_id") or payload.get("id")
    if not eid:
        raise HTTPException(status_code=400, detail="entity_id or id required")
    # treat alert as entity record
    ent = WorldEntity(id=eid, type=payload.get("type", "alert"), attributes=payload)
    await wm.upsert_entity(ent)
    if hasattr(wm, "calculate_risk"):
        await wm.calculate_risk(eid)
    triune = await emit_world_event(db, event_type="alert_ingested", entity_refs=[eid], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@router.post("/policy-violation")
async def ingest_policy_violation(payload: Dict[str, Any], auth: Dict[str, Any] = Depends(verify_world_ingest_token), db=Depends(get_db)):
    wm = WorldModelService(db)
    eid = payload.get("entity_id")
    if not eid:
        raise HTTPException(status_code=400, detail="entity_id required")
    await wm.entities.update_one({"id": eid}, {"$set": {"attributes.policy_violation": True}}, upsert=True)
    if hasattr(wm, "calculate_risk"):
        await wm.calculate_risk(eid)
    triune = await emit_world_event(db, event_type="policy_violation_ingested", entity_refs=[eid], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@router.post("/token-event")
async def ingest_token_event(payload: Dict[str, Any], auth: Dict[str, Any] = Depends(verify_world_ingest_token), db=Depends(get_db)):
    wm = WorldModelService(db)
    eid = payload.get("token_id")
    if not eid:
        raise HTTPException(status_code=400, detail="token_id required")
    await wm.entities.update_one({"id": eid}, {"$push": {"attributes.token_events": payload}}, upsert=True)
    if hasattr(wm, "calculate_risk"):
        await wm.calculate_risk(eid)
    triune = await emit_world_event(db, event_type="token_event_ingested", entity_refs=[eid], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}
