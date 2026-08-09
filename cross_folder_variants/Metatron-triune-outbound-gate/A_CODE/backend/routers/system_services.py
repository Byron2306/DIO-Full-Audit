"""
System Services and Discovery Router
=====================================
Exposes ARDA discovery, system services, and infrastructure services.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, List, Any

from .dependencies import get_current_user, check_permission, get_db

# Optional system and discovery services
try:
    from services.arda_discover import ArdaDiscover
except ImportError:
    ArdaDiscover = None

try:
    from services.arda_launcher import ArdaLauncher
except ImportError:
    ArdaLauncher = None

try:
    from services.arda_seeder import ArdaSeeder
except ImportError:
    ArdaSeeder = None

try:
    from services.world_manifold import get_world_manifold
except ImportError:
    get_world_manifold = None

try:
    from services.formation_order import FormationOrder
except ImportError:
    FormationOrder = None

try:
    from services.process_lineage_service import ProcessLineageService
except ImportError:
    ProcessLineageService = None

try:
    from services.plagiarism_detector import PlagiarismDetector
except ImportError:
    PlagiarismDetector = None

router = APIRouter(prefix="/system", tags=["System Services"])


@router.get("/discover/nodes")
async def discover_arda_nodes(
    current_user: dict = Depends(get_current_user),
):
    """Discover available ARDA nodes in the cluster."""
    if not ArdaDiscover:
        raise HTTPException(status_code=501, detail="ARDA discovery service not available")
    
    try:
        discover = ArdaDiscover()
        nodes = await discover.discover_nodes()
        return {
            "success": True,
            "nodes": nodes,
            "count": len(nodes),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Node discovery failed: {str(e)}")


@router.post("/arda/launch")
async def launch_arda_service(
    service_name: str,
    config: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Launch an ARDA service."""
    if not ArdaLauncher:
        raise HTTPException(status_code=501, detail="ARDA launcher not available")
    
    try:
        launcher = ArdaLauncher()
        result = await launcher.launch(service_name, config)
        return {
            "success": True,
            "service": service_name,
            "launch_result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service launch failed: {str(e)}")


@router.post("/arda/seed")
async def seed_arda_data(
    dataset_name: str,
    data: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Seed initial ARDA data."""
    if not ArdaSeeder:
        raise HTTPException(status_code=501, detail="ARDA seeder not available")
    
    try:
        seeder = ArdaSeeder()
        result = await seeder.seed(dataset_name, data)
        return {
            "success": True,
            "dataset": dataset_name,
            "seeded_records": result.get("count", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data seeding failed: {str(e)}")


@router.get("/world/manifold/state")
async def get_world_manifold_state(
    current_user: dict = Depends(get_current_user),
):
    """Get current world manifold state."""
    if not get_world_manifold:
        raise HTTPException(status_code=501, detail="World manifold service not available")
    
    try:
        manifold = get_world_manifold()
        state = await manifold.get_state()
        return {
            "success": True,
            "manifold_state": state,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get manifold state: {str(e)}")


@router.post("/formation/order")
async def issue_formation_order(
    order_content: Dict[str, Any],
    priority: str = "normal",
    current_user: dict = Depends(check_permission("write")),
):
    """Issue a formation order."""
    if not FormationOrder:
        raise HTTPException(status_code=501, detail="Formation order service not available")
    
    try:
        order_service = FormationOrder()
        order = await order_service.issue(order_content, priority=priority)
        return {
            "success": True,
            "order_id": order.get("id"),
            "priority": priority,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order issuance failed: {str(e)}")


@router.get("/process/lineage/{process_id}")
async def get_process_lineage(
    process_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get process lineage (parent-child relationships)."""
    if not ProcessLineageService:
        raise HTTPException(status_code=501, detail="Process lineage service not available")
    
    try:
        service = ProcessLineageService()
        lineage = await service.get_lineage(process_id)
        return {
            "success": True,
            "process_id": process_id,
            "lineage": lineage,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get lineage: {str(e)}")


@router.post("/plagiarism/scan")
async def scan_for_plagiarism(
    content: str,
    content_type: str = "code",
    current_user: dict = Depends(check_permission("read")),
):
    """Scan content for plagiarism."""
    if not PlagiarismDetector:
        raise HTTPException(status_code=501, detail="Plagiarism detector not available")
    
    try:
        detector = PlagiarismDetector()
        results = await detector.scan(content, content_type=content_type)
        return {
            "success": True,
            "plagiarism_score": results.get("score", 0.0),
            "matches": results.get("matches", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plagiarism scan failed: {str(e)}")
