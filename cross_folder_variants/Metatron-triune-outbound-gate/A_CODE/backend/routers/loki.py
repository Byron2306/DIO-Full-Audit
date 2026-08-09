from fastapi import APIRouter, Depends, HTTPException, Body
import logging
from typing import Any, Dict
from pydantic import BaseModel, Field
from routers.dependencies import get_db, require_machine_token
from services.world_model import WorldModelService, WorldEntity, WorldEdge, EntityType
from services.world_events import emit_world_event
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(tags=["loki"])
verify_loki_ingest_token = require_machine_token(
    env_keys=["LOKI_INGEST_TOKEN", "WORLD_INGEST_TOKEN", "INTEGRATION_API_KEY", "SWARM_AGENT_TOKEN"],
    header_names=["x-loki-token", "x-world-ingest-token", "x-internal-token", "x-agent-token"],
    subject="loki ingest",
)


class LokiIngestRequest(BaseModel):
    kind: str = Field(..., description="Type of ingestion: detection|edge|campaign|file|entity")
    id: str | None = Field(None, description="Optional entity id")
    entity_type: str | None = Field(None, description="Optional entity type for detections")
    attributes: dict | None = Field(None, description="Optional attributes payload")
    source: str | None = Field(None, description="Edge source")
    target: str | None = Field(None, description="Edge target")
    relation: str | None = Field(None, description="Edge relation")



@router.post("/loki/ingest/async")
async def ingest_async(payload: Dict[str, Any], auth: Dict[str, Any] = Depends(verify_loki_ingest_token), db=Depends(get_db)):
    """Attempt to enqueue the Loki ingest as a Celery task. If Celery is not
    available, fall back to running the ingestion synchronously in-process.
    Returns a best-effort acknowledgement including task id when available.
    """
    # Try enqueueing to the Celery task if available
    try:
        from backend.tasks.triune_tasks import loki_ingest
        # if Celery is installed, loki_ingest may be a Task with delay/apply_async
        if hasattr(loki_ingest, "delay"):
            # enqueue async and return task id
            res = loki_ingest.delay(payload)
            return {"status": "enqueued", "task_id": getattr(res, "id", None)}
        # otherwise call synchronously (task is a normal function)
        res = loki_ingest(payload)
        return {"status": "completed", "result": res}
    except Exception:
        # Celery or task import failed; run lightweight runner inline
        logger.info("loki.ingest.async: Celery unavailable, running inline runner")
        # perform same processing as the triune task does (best-effort)
        kind = payload.get("kind") or payload.get("type")
        if not kind:
            raise HTTPException(status_code=400, detail="missing kind in payload")
        wm = WorldModelService(db)
        if kind in ("detection", "entity", "alert", "file"):
            eid = payload.get("id") or str(uuid.uuid4())
            ent_type = payload.get("entity_type") or payload.get("type") or "detection"
            try:
                et = EntityType(ent_type)
            except Exception:
                et = EntityType.detection
            attrs = payload.get("attributes", {}) or {}
            ent = WorldEntity(id=eid, type=et, attributes=attrs)
            await wm.upsert_entity(ent)
            await emit_world_event(
                db,
                event_type="loki_entity_ingested",
                entity_refs=[eid],
                payload=payload,
                trigger_triune=False,
            )
            return {"status": "ok", "id": eid}
        if kind == "edge":
            src = payload.get("source")
            tgt = payload.get("target")
            rel = payload.get("relation", "related_to")
            if not src or not tgt:
                raise HTTPException(status_code=400, detail="edge requires source and target")
            edge = WorldEdge(source=src, target=tgt, relation=rel, created=datetime.now(timezone.utc))
            await wm.add_edge(edge)
            await emit_world_event(
                db,
                event_type="loki_edge_ingested",
                entity_refs=[src, tgt],
                payload=payload,
                trigger_triune=False,
            )
            return {"status": "ok"}
        if kind == "campaign":
            cid = payload.get("id") or str(uuid.uuid4())
            attrs = payload.get("attributes", {}) or {}
            ent = WorldEntity(id=cid, type=EntityType.campaign, attributes=attrs)
            await wm.upsert_entity(ent)
            await emit_world_event(
                db,
                event_type="loki_campaign_ingested",
                entity_refs=[cid],
                payload=payload,
                trigger_triune=False,
            )
            return {"status": "ok", "id": cid}
        raise HTTPException(status_code=400, detail=f"unsupported kind: {kind}")


@router.get("/loki/hello")
async def hello():
    return {"msg": "Loki router active"}


@router.post(
    "/loki/ingest",
    summary="Ingest Loki events synchronously",
    response_model=Dict[str, Any],
)
async def ingest(payload: LokiIngestRequest = Body(..., examples={
    "detection": {"summary": "Detection", "value": {"kind": "detection", "id": "d1", "entity_type": "detection", "attributes": {"sig": "x"}}},
    "edge": {"summary": "Edge", "value": {"kind": "edge", "source": "e1", "target": "e2", "relation": "observed"}},
    "campaign": {"summary": "Campaign", "value": {"kind": "campaign", "id": "c1", "attributes": {"stage": "initial"}}},
}), auth: Dict[str, Any] = Depends(verify_loki_ingest_token), db=Depends(get_db)):
    """Ingest events into the world model. Payload must include `kind` (detection|edge|campaign).

    Examples:
    - {"kind": "detection", "id": "d1", "entity_type": "detection", "attributes": {...}}
    - {"kind": "edge", "source": "e1", "target": "e2", "relation": "observed"}
    """
    wm = WorldModelService(db)
    kind = payload.kind
    if not kind:
        logger.debug("loki.ingest: missing kind in payload: %s", payload.dict())
        raise HTTPException(status_code=400, detail="missing kind in payload")

    if kind in ("detection", "entity", "alert", "file"):
        eid = payload.id or str(uuid.uuid4())
        ent_type = payload.entity_type or "detection"
        try:
            et = EntityType(ent_type)
        except Exception:
            et = EntityType.detection
        attrs = payload.attributes or {}
        ent = WorldEntity(id=eid, type=et, attributes=attrs)
        await wm.upsert_entity(ent)
        await emit_world_event(
            db,
            event_type="loki_entity_ingested",
            entity_refs=[eid],
            payload=payload.model_dump(),
            trigger_triune=False,
        )
        logger.info("loki.ingest: upserted entity %s type=%s", eid, et)
        return {"status": "ok", "id": eid}

    if kind == "edge":
        src = payload.source
        tgt = payload.target
        rel = payload.relation or "related_to"
        if not src or not tgt:
            logger.debug("loki.ingest: missing src/tgt for edge payload: %s", payload)
            raise HTTPException(status_code=400, detail="edge requires source and target")
        edge = WorldEdge(source=src, target=tgt, relation=rel, created=datetime.now(timezone.utc))
        await wm.add_edge(edge)
        await emit_world_event(
            db,
            event_type="loki_edge_ingested",
            entity_refs=[src, tgt],
            payload=payload.model_dump(),
            trigger_triune=False,
        )
        logger.info("loki.ingest: added edge %s->%s rel=%s", src, tgt, rel)
        return {"status": "ok"}

    if kind == "campaign":
        cid = payload.id or str(uuid.uuid4())
        attrs = payload.attributes or {}
        ent = WorldEntity(id=cid, type=EntityType.campaign, attributes=attrs)
        await wm.upsert_entity(ent)
        await emit_world_event(
            db,
            event_type="loki_campaign_ingested",
            entity_refs=[cid],
            payload=payload.model_dump(),
            trigger_triune=False,
        )
        logger.info("loki.ingest: upserted campaign %s", cid)
        return {"status": "ok", "id": cid}

    raise HTTPException(status_code=400, detail=f"unsupported kind: {kind}")
