import importlib
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .dependencies import get_current_user, check_permission, get_db

atomic_validation_module = importlib.import_module("atomic_validation")
atomic_validation_manager = getattr(atomic_validation_module, "atomic_validation", None)


def _manager() -> Any:
    return atomic_validation_manager

router = APIRouter(prefix="/atomic-validation", tags=["Atomic Validation"])


class RunAtomicJobRequest(BaseModel):
    job_id: str
    dry_run: bool = False


@router.get("/status")
async def atomic_status(current_user: dict = Depends(get_current_user)):
    _manager().set_db(get_db())
    return _manager().get_status()


@router.get("/jobs")
async def atomic_jobs(current_user: dict = Depends(get_current_user)):
    _manager().set_db(get_db())
    return _manager().list_jobs()


@router.get("/runs")
async def atomic_runs(
    limit: int = Query(50, ge=1, le=300),
    current_user: dict = Depends(get_current_user),
):
    _manager().set_db(get_db())
    return _manager().list_runs(limit=limit)


@router.post("/run")
async def atomic_run_job(
    payload: RunAtomicJobRequest,
    current_user: dict = Depends(check_permission("write")),
):
    _manager().set_db(get_db())
    return _manager().run_job(payload.job_id, dry_run=payload.dry_run)
