from celery_app import celery_app
from services.world_model import WorldModelService, WorldEntity, WorldEdge
from services.world_events import emit_world_event
from typing import Dict, Any

@celery_app.task(name="backend.tasks.world_ingest.ingest_entity")
async def ingest_entity_task(db_config: Dict[str, Any], payload: Dict[str, Any]):
    # db_config could be connection settings; for now we assume app-level Mongo client accessible
    from backend.server import db as global_db
    wm = WorldModelService(global_db)
    entity = WorldEntity(**payload)
    await wm.upsert_entity(entity)
    triune = await emit_world_event(global_db, event_type="entity_ingested", entity_refs=[entity.id], payload=payload)
    return {"status": "ok", "id": entity.id, "triune": triune.get("triune")}

@celery_app.task(name="backend.tasks.world_ingest.ingest_edge")
async def ingest_edge_task(db_config: Dict[str, Any], payload: Dict[str, Any]):
    from backend.server import db as global_db
    wm = WorldModelService(global_db)
    edge = WorldEdge(**payload)
    await wm.add_edge(edge)
    triune = await emit_world_event(global_db, event_type="edge_ingested", entity_refs=[edge.source, edge.target], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@celery_app.task(name="backend.tasks.world_ingest.ingest_detection")
async def ingest_detection_task(db_config: Dict[str, Any], payload: Dict[str, Any]):
    from backend.server import db as global_db
    wm = WorldModelService(global_db)
    eid = payload.get("entity_id")
    if eid:
        await wm.entities.update_one({"id": eid}, {"$push": {"attributes.detections": payload}}, upsert=True)
        if hasattr(wm, "calculate_risk"):
            await wm.calculate_risk(eid)
    triune = await emit_world_event(global_db, event_type="detection_ingested", entity_refs=[eid] if eid else [], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@celery_app.task(name="backend.tasks.world_ingest.ingest_alert")
async def ingest_alert_task(db_config: Dict[str, Any], payload: Dict[str, Any]):
    from backend.server import db as global_db
    wm = WorldModelService(global_db)
    eid = payload.get("entity_id") or payload.get("id")
    if eid:
        ent = WorldEntity(id=eid, type=payload.get("type", "alert"), attributes=payload)
        await wm.upsert_entity(ent)
        if hasattr(wm, "calculate_risk"):
            await wm.calculate_risk(eid)
    triune = await emit_world_event(global_db, event_type="alert_ingested", entity_refs=[eid] if eid else [], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@celery_app.task(name="backend.tasks.world_ingest.ingest_policy_violation")
async def ingest_policy_violation_task(db_config: Dict[str, Any], payload: Dict[str, Any]):
    from backend.server import db as global_db
    wm = WorldModelService(global_db)
    eid = payload.get("entity_id")
    if eid:
        await wm.entities.update_one({"id": eid}, {"$set": {"attributes.policy_violation": True}}, upsert=True)
        if hasattr(wm, "calculate_risk"):
            await wm.calculate_risk(eid)
    triune = await emit_world_event(global_db, event_type="policy_violation_ingested", entity_refs=[eid] if eid else [], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}

@celery_app.task(name="backend.tasks.world_ingest.ingest_token_event")
async def ingest_token_event_task(db_config: Dict[str, Any], payload: Dict[str, Any]):
    from backend.server import db as global_db
    wm = WorldModelService(global_db)
    eid = payload.get("token_id")
    if eid:
        await wm.entities.update_one({"id": eid}, {"$push": {"attributes.token_events": payload}}, upsert=True)
        if hasattr(wm, "calculate_risk"):
            await wm.calculate_risk(eid)
    triune = await emit_world_event(global_db, event_type="token_event_ingested", entity_refs=[eid] if eid else [], payload=payload)
    return {"status": "ok", "triune": triune.get("triune")}
