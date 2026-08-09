"""Feature store used by Metatron and other ML consumers."""
from typing import Any, Dict

try:
    from backend.services.world_events import emit_world_event
except Exception:
    emit_world_event = None

class FeatureStore:
    def __init__(self, db: Any = None):
        self.db = db
        self.collection = None
        if db is not None:
            self.collection = db.feature_store

    def set_database(self, db: Any):
        self.__init__(db)

    async def store(self, key: str, features: Dict[str, Any]):
        if self.collection is None:
            raise RuntimeError("database not configured")
        await self.collection.update_one({"key": key}, {"$set": {"features": features}}, upsert=True)
        if emit_world_event is not None and self.db is not None:
            try:
                await emit_world_event(
                    self.db,
                    event_type="ml_feature_store_updated",
                    entity_refs=[key],
                    payload={"feature_count": len(features or {})},
                    trigger_triune=False,
                    source="ml.feature_store",
                )
            except Exception:
                pass

    async def fetch(self, key: str) -> Dict[str, Any]:
        if self.collection is None:
            raise RuntimeError("database not configured")
        doc = await self.collection.find_one({"key": key})
        return doc.get("features") if doc else {}
