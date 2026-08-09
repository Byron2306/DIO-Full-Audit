from celery_app import celery_app
from services.world_model import WorldModelService
from services.world_events import emit_world_event
from services.triune_orchestrator import TriuneOrchestrator

# simple periodic metatron tick task
@celery_app.task(name="backend.tasks.triune_tasks.metatron_tick")
async def metatron_tick():
    # Canonical periodic triune recomputation entrypoint.
    from backend.server import db
    orchestrator = TriuneOrchestrator(db)
    bundle = await orchestrator.handle_world_change(
        event_type="triune_periodic_tick",
        entity_ids=[],
        context={"source": "task.triune.metatron_tick"},
    )
    await emit_world_event(
        db,
        event_type="triune_periodic_tick_completed",
        entity_refs=[],
        payload={"ranked_count": len(bundle.get("michael", {}).get("ranked", []))},
        trigger_triune=False,
        source="task.triune",
    )
    return {
        "status": "ok",
        "event_type": bundle.get("event_type"),
        "ranked_count": len(bundle.get("michael", {}).get("ranked", [])),
    }


# Loki ingestion task (sync Celery task that runs async world model operations)
@celery_app.task(name="backend.tasks.triune_tasks.loki_ingest")
def loki_ingest(payload: dict):
    """Process an ingestion payload from Loki (or other collectors) into the world model.

    This is a synchronous Celery task that delegates to the async WorldModelService methods.
    """
    import asyncio
    from backend.server import db
    from services.world_model import WorldEntity, WorldEdge, EntityType
    import uuid
    from datetime import datetime, timezone

    wm = WorldModelService(db)

    async def _process():
        kind = payload.get("kind") or payload.get("type")
        if not kind:
            return {"error": "missing kind"}
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
                trigger_triune=True,
                source="task.triune.loki_ingest",
            )
            return {"status": "ok", "id": eid}
        if kind == "edge":
            src = payload.get("source")
            tgt = payload.get("target")
            rel = payload.get("relation", "related_to")
            if not src or not tgt:
                return {"error": "edge requires source and target"}
            edge = WorldEdge(source=src, target=tgt, relation=rel, created=datetime.now(timezone.utc))
            await wm.add_edge(edge)
            await emit_world_event(
                db,
                event_type="loki_edge_ingested",
                entity_refs=[src, tgt],
                payload=payload,
                trigger_triune=True,
                source="task.triune.loki_ingest",
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
                trigger_triune=True,
                source="task.triune.loki_ingest",
            )
            return {"status": "ok", "id": cid}
        return {"error": f"unsupported kind: {kind}"}

    return asyncio.run(_process())


@celery_app.task(name="backend.tasks.triune_tasks.michael_analyze")
def michael_analyze(entity_ids: list = None):
    """Background analysis task that asks Michael to score/rank candidate responses and persists results."""
    import asyncio
    from backend.server import db
    from services.world_model import WorldModelService
    from services.triune_orchestrator import TriuneOrchestrator
    from datetime import datetime, timezone
    import uuid

    wm = WorldModelService(db)
    orchestrator = TriuneOrchestrator(db)

    async def _run():
        if entity_ids:
            candidates = []
            for eid in entity_ids:
                doc = await wm.entities.find_one({"id": eid}, {"_id": 0})
                if doc:
                    attrs = doc.get("attributes", {})
                    candidates.append(attrs.get("suggested_action") or f"investigate:{eid}")
        else:
            actions = await wm.list_actions(limit=20)
            candidates = [f"{a['action']}:{a['entity_id']}" for a in actions]

        bundle = await orchestrator.handle_world_change(
            event_type="michael_analysis_requested",
            entity_ids=entity_ids or [],
            context={
                "source": "task.triune.michael_analyze",
                "candidate_count": len(candidates),
            },
        )
        ranked = bundle.get("michael", {}).get("ranked", [])
        # persist results for dashboard / Metatron consumption
        doc = {
            "id": str(uuid.uuid4()),
            "created": datetime.now(timezone.utc),
            "entities": entity_ids or [],
            "candidates": candidates,
            "ranked": ranked,
        }
        try:
            await db.triune_analysis.insert_one(doc)
        except Exception:
            # best-effort: ignore persistence errors
            pass
        await emit_world_event(
            db,
            event_type="michael_analysis_completed",
            entity_refs=entity_ids or [],
            payload={"ranked_count": len(ranked), "candidate_count": len(candidates)},
            trigger_triune=False,
            source="task.triune",
        )
        return {"id": doc["id"], "ranked_count": len(ranked)}

    return asyncio.run(_run())
