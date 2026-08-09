"""
Threat Correlation Router
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from .dependencies import get_current_user, check_permission, get_db

# Import correlation engine
from threat_correlation import correlation_engine, ThreatCorrelationEngine
from threat_intel import threat_intel

router = APIRouter(prefix="/correlation", tags=["Threat Correlation"])

# Initialize correlation engine with threat intel
correlation_engine.set_threat_intel(threat_intel)

@router.get("/stats")
async def get_correlation_stats(current_user: dict = Depends(get_current_user)):
    """Get correlation engine statistics"""
    return correlation_engine.get_stats()

@router.post("/threat/{threat_id}")
async def correlate_threat(threat_id: str, current_user: dict = Depends(get_current_user)):
    """Correlate a specific threat with threat intelligence"""
    db = get_db()
    if db is not None:
        ThreatCorrelationEngine.set_database(db)
    
    # Get threat from database
    threat = await db.threats.find_one({"id": threat_id}, {"_id": 0})
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    # Perform correlation
    from dataclasses import asdict
    result = await correlation_engine.correlate_threat(threat)
    response = asdict(result)

    # Ollama-assisted reasoning enrichment (with graceful fallback)
    try:
        from services.ai_reasoning import ai_reasoning
        ai_response = await ai_reasoning.ollama_analyze_threat({
            "title": threat.get("name", f"Threat {threat_id}"),
            "description": threat.get("description", ""),
            "source": threat.get("source_ip"),
            "indicators": threat.get("indicators", [])
        })
        response["ai_reasoning"] = ai_response
    except Exception as e:
        response["ai_reasoning"] = {
            "method": "unavailable",
            "error": str(e)
        }

    return response

@router.get("/threat/{threat_id}")
async def get_correlation(threat_id: str, current_user: dict = Depends(get_current_user)):
    """Get cached correlation result for a threat"""
    result = correlation_engine.get_correlation(threat_id)
    
    if not result:
        # Try to get from database
        db = get_db()
        stored = await db.threat_correlations.find_one(
            {"threat_id": threat_id}, 
            {"_id": 0}
        )
        if stored:
            return stored
        raise HTTPException(status_code=404, detail="Correlation not found")
    
    from dataclasses import asdict
    return asdict(result)

@router.post("/all-active")
async def correlate_all_active(current_user: dict = Depends(check_permission("write"))):
    """Correlate all active threats"""
    db = get_db()
    if db is not None:
        ThreatCorrelationEngine.set_database(db)

    from dataclasses import asdict
    results = await correlation_engine.correlate_all_active_threats()
    correlations = [asdict(r) for r in results]

    # Add high-level AI recommendation for operator triage context
    ai_summary = None
    try:
        from services.ai_reasoning import ai_reasoning
        confidence_breakdown = {
            "high": len([r for r in results if r.confidence == "high"]),
            "medium": len([r for r in results if r.confidence == "medium"]),
            "low": len([r for r in results if r.confidence == "low"]),
            "none": len([r for r in results if r.confidence == "none"])
        }
        ai_summary_result = ai_reasoning.query(
            "Prioritize correlation response actions for active threats",
            {
                "total_correlations": len(results),
                "confidence": confidence_breakdown
            }
        )
        ai_summary = {
            "conclusion": ai_summary_result.conclusion,
            "recommendations": ai_summary_result.recommendations,
            "confidence": ai_summary_result.confidence,
            "method": "rule_based_or_ollama"
        }
    except Exception as e:
        ai_summary = {
            "method": "unavailable",
            "error": str(e)
        }

    return {
        "message": f"Correlated {len(results)} active threats",
        "correlations": correlations,
        "ai_summary": ai_summary,
        "summary": {
            "total": len(results),
            "high_confidence": len([r for r in results if r.confidence == "high"]),
            "medium_confidence": len([r for r in results if r.confidence == "medium"]),
            "low_confidence": len([r for r in results if r.confidence == "low"]),
            "no_correlation": len([r for r in results if r.confidence == "none"])
        }
    }


@router.post("/threat/{threat_id}/ai")
async def correlate_threat_with_ai(threat_id: str, current_user: dict = Depends(get_current_user)):
    """Run correlation and return AI-assisted analysis for a single threat"""
    return await correlate_threat(threat_id, current_user)

@router.get("/history")
async def get_correlation_history(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get correlation history"""
    db = get_db()
    
    correlations = await db.threat_correlations.find(
        {}, 
        {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)
    
    return {
        "correlations": correlations,
        "count": len(correlations)
    }

@router.get("/auto-actions")
async def get_auto_actions(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get auto-action history"""
    db = get_db()
    
    actions = await db.auto_actions.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)
    
    return {
        "actions": actions,
        "count": len(actions)
    }

@router.post("/settings")
async def update_correlation_settings(
    auto_correlate: bool = True,
    current_user: dict = Depends(check_permission("write"))
):
    """Update correlation engine settings"""
    correlation_engine.auto_correlate_enabled = auto_correlate
    
    return {
        "message": "Settings updated",
        "auto_correlate_enabled": correlation_engine.auto_correlate_enabled
    }
