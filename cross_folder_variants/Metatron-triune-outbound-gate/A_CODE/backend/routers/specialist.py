"""
Specialized Services Router
===========================
Exposes specialized orchestration, CLI, and advanced domain services.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any, List

from .dependencies import get_current_user, check_permission

# Optional specialized services
try:
    from services.cli_events import get_cli_event_bus
except ImportError:
    get_cli_event_bus = None

try:
    from services.triune_orchestrator import TriuneOrchestrator
except ImportError:
    TriuneOrchestrator = None

try:
    from services.sophia_curriculum_gate import SophiaCurriculumGate
except ImportError:
    SophiaCurriculumGate = None

try:
    from services.coronation_cli import CoronationCLI
except ImportError:
    CoronationCLI = None

try:
    from services.unified_adapter import UnifiedAdapter
except ImportError:
    UnifiedAdapter = None

try:
    from services.seraph_proxy import SeraphProxy
except ImportError:
    SeraphProxy = None

try:
    from services.openclaw import OpenClaw
except ImportError:
    OpenClaw = None

try:
    from services.quorum_engine import QuorumEngine
except ImportError:
    QuorumEngine = None

try:
    from services.tulkas_executor import TulkasExecutor
except ImportError:
    TulkasExecutor = None

try:
    from services.manwe_herald import ManweHerald
except ImportError:
    ManweHerald = None

router = APIRouter(prefix="/specialist", tags=["Specialist Services"])


@router.post("/cli/event")
async def emit_cli_event(
    event_type: str,
    data: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Emit a CLI event."""
    if not get_cli_event_bus:
        raise HTTPException(status_code=501, detail="CLI event bus not available")
    
    try:
        bus = get_cli_event_bus()
        result = await bus.emit(event_type, data)
        return {
            "success": True,
            "event_type": event_type,
            "event_id": result.get("id"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event emission failed: {str(e)}")


@router.post("/triune/orchestrate")
async def orchestrate_triune(
    workflow: str,
    parameters: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Orchestrate Triune workflow."""
    if not TriuneOrchestrator:
        raise HTTPException(status_code=501, detail="Triune orchestrator not available")
    
    try:
        orchestrator = TriuneOrchestrator()
        result = await orchestrator.orchestrate(workflow, parameters)
        return {
            "success": True,
            "workflow": workflow,
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


@router.post("/sophia/curriculum/gate")
async def sophia_curriculum_gate(
    student_id: str,
    lesson: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Access Sophia curriculum gating."""
    if not SophiaCurriculumGate:
        raise HTTPException(status_code=501, detail="Sophia curriculum gate not available")
    
    try:
        gate = SophiaCurriculumGate()
        result = await gate.check_eligibility(student_id, lesson)
        return {
            "success": True,
            "student_id": student_id,
            "lesson": lesson,
            "eligible": result.get("eligible", False),
            "prerequisites": result.get("prerequisites", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gate check failed: {str(e)}")


@router.post("/coronation/cli/invoke")
async def invoke_coronation_cli(
    command: str,
    args: List[str],
    current_user: dict = Depends(check_permission("write")),
):
    """Invoke coronation CLI command."""
    if not CoronationCLI:
        raise HTTPException(status_code=501, detail="Coronation CLI not available")
    
    try:
        cli = CoronationCLI()
        result = await cli.invoke(command, args)
        return {
            "success": True,
            "command": command,
            "output": result.get("output"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLI invocation failed: {str(e)}")


@router.post("/adapter/unify")
async def unify_with_adapter(
    source_system: str,
    target_system: str,
    mapping: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Unify data between systems using adapter."""
    if not UnifiedAdapter:
        raise HTTPException(status_code=501, detail="Unified adapter not available")
    
    try:
        adapter = UnifiedAdapter()
        result = await adapter.unify(source_system, target_system, mapping)
        return {
            "success": True,
            "unified_records": result.get("count", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unification failed: {str(e)}")


@router.post("/seraph/proxy/forward")
async def seraph_proxy_forward(
    destination: str,
    request_data: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Forward request via Seraph proxy."""
    if not SeraphProxy:
        raise HTTPException(status_code=501, detail="Seraph proxy not available")
    
    try:
        proxy = SeraphProxy()
        result = await proxy.forward(destination, request_data)
        return {
            "success": True,
            "destination": destination,
            "proxy_result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy forward failed: {str(e)}")


@router.post("/openclaw/execute")
async def execute_openclaw(
    script: str,
    context: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Execute OpenClaw script."""
    if not OpenClaw:
        raise HTTPException(status_code=501, detail="OpenClaw not available")
    
    try:
        claw = OpenClaw()
        result = await claw.execute(script, context)
        return {
            "success": True,
            "execution_result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get("/quorum/status")
async def get_quorum_status(
    current_user: dict = Depends(get_current_user),
):
    """Get quorum engine status."""
    if not QuorumEngine:
        raise HTTPException(status_code=501, detail="Quorum engine not available")
    
    try:
        engine = QuorumEngine()
        status = await engine.get_status()
        return {
            "success": True,
            "quorum_status": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/tulkas/execute")
async def execute_tulkas_command(
    command: str,
    parameters: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Execute Tulkas command."""
    if not TulkasExecutor:
        raise HTTPException(status_code=501, detail="Tulkas executor not available")
    
    try:
        executor = TulkasExecutor()
        result = await executor.execute(command, parameters)
        return {
            "success": True,
            "command": command,
            "execution_result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get("/manwe/herald/status")
async def get_manwe_herald_status(
    current_user: dict = Depends(get_current_user),
):
    """Get Manwë herald status."""
    if not ManweHerald:
        raise HTTPException(status_code=501, detail="Manwë herald not available")
    
    try:
        herald = ManweHerald()
        status = await herald.get_status()
        return {
            "success": True,
            "herald_status": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
