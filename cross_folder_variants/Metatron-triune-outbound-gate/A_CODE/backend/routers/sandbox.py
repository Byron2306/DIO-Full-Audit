"""
Sandbox Analysis Router - Dynamic malware analysis
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from typing import Optional, List
from pydantic import BaseModel

from .dependencies import get_current_user, check_permission
from sandbox_analysis import sandbox_service, SandboxService

router = APIRouter(prefix="/sandbox", tags=["Sandbox Analysis"])


class SubmitURLRequest(BaseModel):
    url: str
    tags: Optional[List[str]] = None


class SubmitHashRequest(BaseModel):
    sample_hash: str
    sample_name: str
    tags: Optional[List[str]] = None


@router.get("/stats")
async def get_sandbox_stats(current_user: dict = Depends(get_current_user)):
    """Get sandbox analysis statistics"""
    return sandbox_service.get_stats()


@router.get("/analyses")
async def get_analyses(
    limit: int = 50,
    status: Optional[str] = None,
    verdict: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get list of sandbox analyses"""
    analyses = sandbox_service.get_analyses(
        limit=limit,
        status=status,
        verdict=verdict
    )
    return {"analyses": analyses, "count": len(analyses)}


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed analysis results"""
    analysis = sandbox_service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.post("/submit/file")
async def submit_file_for_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tags: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Submit a file for sandbox analysis"""
    # Read file content
    content = await file.read()
    
    # Parse tags
    tag_list = tags.split(",") if tags else []
    
    # Submit sample
    result = sandbox_service.submit_sample(
        sample_name=file.filename,
        sample_data=content,
        submitted_by=current_user.get("email", "anonymous"),
        tags=tag_list
    )
    
    # Start analysis in background
    if result.get("success") and not result.get("cached"):
        background_tasks.add_task(
            sandbox_service.run_analysis,
            result["analysis_id"]
        )
    
    return result


@router.post("/submit/url")
async def submit_url_for_analysis(
    request: SubmitURLRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Submit a URL for sandbox analysis"""
    result = sandbox_service.submit_url(
        url=request.url,
        submitted_by=current_user.get("email", "anonymous"),
        tags=request.tags
    )
    
    # Start analysis in background
    if result.get("success"):
        background_tasks.add_task(
            sandbox_service.run_analysis,
            result["analysis_id"]
        )
    
    return result


@router.post("/analyses/{analysis_id}/rerun")
async def rerun_analysis(
    analysis_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(check_permission("write"))
):
    """Re-run a sandbox analysis"""
    analysis = sandbox_service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Start re-analysis in background
    background_tasks.add_task(
        sandbox_service.run_analysis,
        analysis_id
    )
    
    return {"message": "Analysis queued for re-run", "analysis_id": analysis_id}


@router.get("/signatures")
async def get_signatures(current_user: dict = Depends(get_current_user)):
    """Get available malware signatures"""
    return {
        "signatures": sandbox_service.signatures,
        "count": len(sandbox_service.signatures)
    }


@router.get("/queue")
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """Get sandbox queue status"""
    return {
        "queue_length": len(sandbox_service.queue),
        "running": sandbox_service.running_count,
        "max_concurrent": sandbox_service.max_concurrent,
        "vm_pool": sandbox_service.vm_pool,
        "queued_ids": sandbox_service.queue[:10]  # First 10
    }
