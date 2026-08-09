"""
Evidence API Router
===================
Serves per-technique Technique Validation Records (TVRs) and the derived
coverage summary.  Every coverage number returned here is traceable to
individual TVR verdict files on disk — never manually composed.

Endpoints
---------
POST /api/evidence/generate
    Trigger full TVR generation for all techniques (or a filtered subset).
    Returns a synchronous result — may take ~60 s for 400+ techniques.

GET  /api/evidence/summary
    Return coverage_summary.json derived from all TVR verdicts.

GET  /api/evidence/techniques
    List all techniques with a TVR, including tier and score.

GET  /api/evidence/techniques/{technique_id}
    Return the full TVR record (tvr.json) for a technique.

GET  /api/evidence/techniques/{technique_id}/verdict
    Return only the verdict.json for a technique.

GET  /api/evidence/techniques/{technique_id}/manifest
    Return only the manifest.json for a technique.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from routers.dependencies import get_current_user

try:
    from evidence_bundle import EvidenceBundleManager, evidence_bundle_manager
except ImportError:
    from backend.evidence_bundle import EvidenceBundleManager, evidence_bundle_manager  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evidence", tags=["Evidence Bundle"])


# ──────────────────────────────────────────────────────────────────────── #
#  Request / response models                                               #
# ──────────────────────────────────────────────────────────────────────── #

class GenerateRequest(BaseModel):
    techniques: Optional[List[str]] = None  # None = all
    force_reload: bool = False


class GenerateResponse(BaseModel):
    generated: int
    skipped: int
    errors: int
    tier_breakdown: Dict[str, int]
    coverage_summary_path: str


# ──────────────────────────────────────────────────────────────────────── #
#  Helper                                                                   #
# ──────────────────────────────────────────────────────────────────────── #

def _get_technique_list(manager: EvidenceBundleManager) -> List[Dict[str, Any]]:
    """
    Pull the full active technique list from the MITRE catalog and merge in any
    richer metadata from sigma_engine coverage when available.
    """
    sigma_rows: Dict[str, Dict[str, Any]] = {}
    try:
        from sigma_engine import sigma_engine
        cov = sigma_engine.coverage_summary()
        for row in (cov.get("techniques") or []):
            technique_id = str(row.get("technique") or row.get("technique_id") or "").strip().upper()
            if technique_id:
                sigma_rows[technique_id] = dict(row)
    except Exception:
        sigma_rows = {}

    catalog_path = Path(
        os.environ.get(
            "MITRE_TECHNIQUE_CATALOG_PATH",
            str(Path(__file__).resolve().parent.parent / "data" / "generated_mitre_techniques.json"),
        )
    )
    catalog_ids: List[str] = []
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        raw_ids = payload.get("catalog_techniques") or payload.get("techniques") or []
        catalog_ids = [str(technique).strip().upper() for technique in raw_ids if str(technique).strip()]
    except Exception:
        catalog_ids = []

    if not catalog_ids:
        return list(sigma_rows.values())

    technique_rows: List[Dict[str, Any]] = []
    for technique_id in catalog_ids:
        merged = dict(sigma_rows.get(technique_id) or {})
        merged.setdefault("technique", technique_id)
        merged.setdefault("technique_id", technique_id)
        merged.setdefault("name", technique_id)
        merged.setdefault("tactics", [])
        merged.setdefault("platforms", ["Linux"])
        technique_rows.append(merged)
    return technique_rows


# ──────────────────────────────────────────────────────────────────────── #
#  Routes                                                                   #
# ──────────────────────────────────────────────────────────────────────── #

@router.post("/generate", response_model=GenerateResponse)
def generate_evidence_bundle(
    body: GenerateRequest,
    _user: Dict = Depends(get_current_user),
) -> GenerateResponse:
    """
    Generate (or regenerate) TVR records for every technique.

    Uses all available evidence sources:
    - Atomic Red Team run files
    - Sigma rules (all 1759)
    - OSquery query catalog (all 1322)
    - OSquery results telemetry log

    The final coverage_summary.json is derived from the verdicts written,
    not from the sigma_engine aggregate.
    """
    manager = evidence_bundle_manager
    if body.force_reload:
        manager._atomic_runs_cache = None
        manager._sigma_rules_cache = None
        manager._osquery_queries_cache = None
        manager._osquery_events_cache = None

    # Resolve technique list
    if body.techniques:
        tech_rows = [{"technique": t} for t in body.techniques]
    else:
        tech_rows = _get_technique_list(manager)
        if not tech_rows:
            raise HTTPException(status_code=503, detail="Could not load technique list from sigma_engine")

    generated = 0
    skipped = 0
    errors = 0

    for row in tech_rows:
        tech_id = str(row.get("technique") or row.get("technique_id") or "").strip()
        if not tech_id:
            skipped += 1
            continue

        # Extract optional metadata from the coverage row
        technique_name = str(row.get("name") or row.get("technique_name") or tech_id)
        tactics = row.get("tactics") or []
        platforms = row.get("platforms") or ["Linux"]

        try:
            record = manager.generate_tvr_for_technique(
                tech_id,
                technique_name=technique_name,
                tactics=tactics,
                platforms=platforms,
            )
            manager.write_tvr(tech_id, record)
            generated += 1
        except Exception as exc:
            logger.warning("evidence/generate: failed for %s: %s", tech_id, exc)
            errors += 1

    # Build derived coverage summary
    summary = manager.build_coverage_summary()
    tier_breakdown = summary.get("tier_breakdown") or {}

    return GenerateResponse(
        generated=generated,
        skipped=skipped,
        errors=errors,
        tier_breakdown=tier_breakdown,
        coverage_summary_path=str(manager.evidence_root / "coverage_summary.json"),
    )


@router.get("/summary")
def get_coverage_summary(_user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Return the coverage_summary.json derived from TVR verdicts.

    If no TVRs have been generated yet, returns a 404 with instructions.
    Prefer GET /api/mitre/coverage for the live coverage; this endpoint
    returns the TVR-backed evidence-grade summary.
    """
    manager = evidence_bundle_manager
    summary_path = manager.evidence_root / "coverage_summary.json"
    if not summary_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "No coverage_summary.json found. "
                "Call POST /api/evidence/generate first to build the evidence bundle."
            ),
        )
    try:
        return {"source": "technique_validation_records", **__import__("json").loads(summary_path.read_text(encoding="utf-8"))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/techniques")
def list_techniques(
    tier: Optional[str] = Query(None, description="Filter by tier: platinum|gold|silver|bronze|none"),
    min_score: Optional[int] = Query(None, ge=0, le=5),
    _user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    List all techniques that have a TVR on disk, with their tier and score.
    Optionally filter by tier or minimum score.
    """
    manager = evidence_bundle_manager
    technique_ids = manager.list_technique_ids()
    results: List[Dict] = []

    for tech_id in technique_ids:
        verdict = manager.load_latest_verdict(tech_id)
        if not verdict:
            continue
        t_name = str(verdict.get("tier_name") or "none")
        score = int(verdict.get("score") or 0)
        if tier and t_name != tier:
            continue
        if min_score is not None and score < min_score:
            continue
        results.append({
            "technique_id": tech_id,
            "validation_id": verdict.get("validation_id"),
            "tier": t_name,
            "score": score,
            "reviewed": bool(verdict.get("reviewed")),
            "repeated_runs": int(verdict.get("repeated_runs") or 0),
            "reason": verdict.get("reason"),
        })

    return {
        "total": len(results),
        "techniques": results,
    }


@router.get("/techniques/{technique_id}")
def get_technique_tvr(
    technique_id: str,
    _user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the full TVR (tvr.json) for a technique."""
    manager = evidence_bundle_manager
    tvr = manager.load_latest_tvr(technique_id.upper())
    if not tvr:
        raise HTTPException(
            status_code=404,
            detail=f"No TVR found for {technique_id}. Run POST /api/evidence/generate first.",
        )
    return tvr


@router.get("/techniques/{technique_id}/verdict")
def get_technique_verdict(
    technique_id: str,
    _user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return only the verdict.json for a technique (lightweight)."""
    manager = evidence_bundle_manager
    verdict = manager.load_latest_verdict(technique_id.upper())
    if not verdict:
        raise HTTPException(status_code=404, detail=f"No TVR found for {technique_id}")
    return verdict


@router.get("/techniques/{technique_id}/manifest")
def get_technique_manifest(
    technique_id: str,
    _user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the manifest.json for a technique."""
    manager = evidence_bundle_manager
    tech_dir = manager.techniques_dir / technique_id.upper()
    if not tech_dir.exists():
        raise HTTPException(status_code=404, detail=f"No TVR found for {technique_id}")
    for tvr_dir in sorted(tech_dir.iterdir(), reverse=True):
        manifest_file = tvr_dir / "manifest.json"
        if manifest_file.exists():
            try:
                import json
                return json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                continue
    raise HTTPException(status_code=404, detail=f"Manifest not found for {technique_id}")


@router.get("/schema")
def get_tvr_schema(_user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Return the TVR schema definition and scoring ladder."""
    return {
        "schema_version": "1.0.0",
        "record_type": "technique_validation_record",
        "layers": [
            {"layer": "manifest", "file": "manifest.json", "purpose": "Identity and scope"},
            {"layer": "execution", "file": "execution.json", "purpose": "Proof the test ran"},
            {"layer": "telemetry", "file": "telemetry/osquery.ndjson", "purpose": "Raw preserved logs"},
            {"layer": "analytics", "files": ["analytics/sigma_matches.json", "analytics/osquery_correlations.json"], "purpose": "Analytic matches"},
            {"layer": "verdict", "file": "verdict.json", "purpose": "Why it was promoted"},
        ],
        "scoring_ladder": {
            "S2_bronze": {
                "min_score": 2,
                "requirements": ["technique_mapping", "analytic_or_telemetry_source"],
                "note": "Mapping only — no execution evidence",
            },
            "S3_silver": {
                "min_score": 3,
                "requirements": ["successful_execution", "raw_telemetry", "key_events"],
                "note": "Execution-backed but detection incomplete",
            },
            "S4_gold": {
                "min_score": 4,
                "requirements": ["successful_execution", "raw_telemetry", "direct_sigma_detection"],
                "note": "Direct detection confirmed — not yet hardened",
            },
            "S5_platinum": {
                "min_score": 5,
                "requirements": [
                    "successful_execution",
                    "raw_telemetry",
                    "direct_sigma_detection",
                    "analyst_reviewed",
                    "reproducible_3_runs",
                    "clean_baseline",
                ],
                "note": "Fully validated and defensible",
            },
        },
    }
