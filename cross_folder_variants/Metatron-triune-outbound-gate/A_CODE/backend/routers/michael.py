from fastapi import APIRouter, Depends, HTTPException
from typing import Any, List, Optional
from routers.dependencies import get_db
from backend.services.world_model import WorldModelService
try:
    from triune import MichaelService
except ImportError:
    from backend.triune.michael import MichaelService

router = APIRouter()


@router.get("/michael/hello")
async def hello():
    return {"msg": "Michael router active"}


@router.post("/michael/analyze")
async def analyze(entity_ids: Optional[List[str]] = None, db=Depends(get_db)):
    """Perform lightweight analysis/ranking over candidate responses or entity actions.

    If `entity_ids` is provided, Michael will rank inferred actions for those entities;
    otherwise Michael will score the top actions suggested by the world model.
    """
    wm = WorldModelService(db)
    michael = MichaelService(db)

    if entity_ids:
        candidates = []
        for eid in entity_ids:
            doc = await wm.entities.find_one({"id": eid}, {"_id": 0})
            if doc:
                # prefer explicit suggested_action if present
                attrs = doc.get("attributes", {})
                cand = attrs.get("suggested_action") or f"investigate:{eid}"
                candidates.append(cand)
    else:
        actions = await wm.list_actions(limit=10)
        candidates = [f"{a['action']}:{a['entity_id']}" for a in actions]

    ranked = await michael.rank_responses(candidates)
    return {"ranked": ranked, "count": len(ranked)}
