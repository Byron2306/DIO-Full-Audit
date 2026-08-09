"""Graph-native risk computations for the world model."""

from typing import Any

try:
    from backend.services.world_events import emit_world_event
except Exception:
    emit_world_event = None

# placeholder: will use networkx or similar when implemented


def crown_jewel_distance(graph: Any, node: str) -> int:
    """Compute distance from a node to the nearest crown jewel."""
    # stub
    return 0


def compute_centrality(graph: Any) -> dict:
    """Return centrality scores for nodes."""
    return {}


def propagate_trust_collapse(graph: Any, start: str) -> list:
    """Return nodes likely affected when trust collapses from start."""
    return []


async def emit_graph_risk_snapshot(db: Any, scope: str, payload: dict):
    """Emit canonical risk snapshot events for downstream Triune consumption."""
    if emit_world_event is None or db is None:
        return
    try:
        await emit_world_event(
            db,
            event_type="ml_graph_risk_snapshot",
            entity_refs=[scope],
            payload=payload,
            trigger_triune=False,
            source="ml.graph_risk",
        )
    except Exception:
        pass
