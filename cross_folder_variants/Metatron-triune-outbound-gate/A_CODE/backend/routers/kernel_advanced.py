"""
Kernel Services Router
======================
Exposes advanced kernel-level enforcement and monitoring endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any

from .dependencies import get_current_user, check_permission

# Optional kernel services
try:
    from services.kernel_audit_tailer import get_kernel_audit_tailer
except ImportError:
    get_kernel_audit_tailer = None

try:
    from services.kernel_consensus_guard import get_kernel_consensus_guard
except ImportError:
    get_kernel_consensus_guard = None

try:
    from services.kernel_policy_projection import KernelPolicyProjection
except ImportError:
    KernelPolicyProjection = None

try:
    from services.kernel_order_feed import KernelOrderFeed
except ImportError:
    KernelOrderFeed = None

try:
    from services.kernel_signal_adapter import KernelSignalAdapter
except ImportError:
    KernelSignalAdapter = None

try:
    from services.runtime_hooks import RuntimeHooks
except ImportError:
    RuntimeHooks = None

router = APIRouter(prefix="/kernel-advanced", tags=["Kernel Services"])


@router.post("/policy/project")
async def project_kernel_policy(
    policy: Dict[str, Any],
    current_user: dict = Depends(check_permission("read")),
):
    """Project kernel policy impact without enforcement."""
    if not KernelPolicyProjection:
        raise HTTPException(status_code=501, detail="Policy projection not available")
    
    try:
        projector = KernelPolicyProjection()
        projection = await projector.project(policy)
        return {
            "success": True,
            "projected_impact": projection.get("impact", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy projection failed: {str(e)}")


@router.get("/consensus/guard/status")
async def get_kernel_consensus_guard_status(
    current_user: dict = Depends(get_current_user),
):
    """Get kernel consensus guard status."""
    if not get_kernel_consensus_guard:
        raise HTTPException(status_code=501, detail="Consensus guard not available")
    
    try:
        guard = get_kernel_consensus_guard()
        status = await guard.get_status()
        return {
            "success": True,
            "guard_status": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get guard status: {str(e)}")


@router.get("/orders/feed")
async def get_kernel_order_feed(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """Get kernel order feed."""
    if not KernelOrderFeed:
        raise HTTPException(status_code=501, detail="Kernel order feed not available")
    
    try:
        feed = KernelOrderFeed()
        orders = await feed.get_orders(limit=limit)
        return {
            "success": True,
            "orders": orders,
            "count": len(orders),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get orders: {str(e)}")


@router.post("/signal/adapt")
async def adapt_kernel_signal(
    signal_name: str,
    handler: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Adapt kernel signal handling."""
    if not KernelSignalAdapter:
        raise HTTPException(status_code=501, detail="Signal adapter not available")
    
    try:
        adapter = KernelSignalAdapter()
        result = await adapter.adapt_signal(signal_name, handler)
        return {
            "success": True,
            "signal": signal_name,
            "adaptation_result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal adaptation failed: {str(e)}")


@router.post("/runtime/hook/install")
async def install_runtime_hook(
    hook_name: str,
    hook_code: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Install a runtime hook."""
    if not RuntimeHooks:
        raise HTTPException(status_code=501, detail="Runtime hooks not available")
    
    try:
        hooks = RuntimeHooks()
        result = await hooks.install(hook_name, hook_code)
        return {
            "success": True,
            "hook_name": hook_name,
            "installed": result.get("installed", False),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hook installation failed: {str(e)}")
