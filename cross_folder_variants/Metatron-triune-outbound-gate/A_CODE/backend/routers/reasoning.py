"""
Advanced Reasoning and Resonance Router
========================================
Exposes advanced reasoning, resonance, and harmonic enforcement endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any

from .dependencies import get_current_user, check_permission

# Optional reasoning and resonance services
try:
    from services.sophic_reasoning import SophicReasoning
except ImportError:
    SophicReasoning = None

try:
    from services.resonance_engine import ResonanceEngine
except ImportError:
    ResonanceEngine = None

try:
    from services.resonance_service import ResonanceService
except ImportError:
    ResonanceService = None

try:
    from services.harmonic_engine import HarmonicEngine
except ImportError:
    HarmonicEngine = None

try:
    from services.secret_fire import SecretFire
except ImportError:
    SecretFire = None

try:
    from services.verity_engine import VerityEngine
except ImportError:
    VerityEngine = None

try:
    from services.scrutiny_engine import ScrutinyEngine
except ImportError:
    ScrutinyEngine = None

router = APIRouter(prefix="/reasoning", tags=["Reasoning"])


@router.post("/sophic/reason")
async def sophic_reasoning_endpoint(
    query: str,
    context: Dict[str, Any],
    current_user: dict = Depends(check_permission("read")),
):
    """Perform sophic reasoning on a query."""
    if not SophicReasoning:
        raise HTTPException(status_code=501, detail="Sophic reasoning not available")
    
    try:
        reasoner = SophicReasoning()
        result = await reasoner.reason(query, context)
        return {
            "success": True,
            "query": query,
            "reasoning": result.get("reasoning"),
            "conclusion": result.get("conclusion"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reasoning failed: {str(e)}")


@router.post("/resonance/analyze")
async def analyze_resonance(
    signal: Dict[str, Any],
    current_user: dict = Depends(check_permission("read")),
):
    """Analyze resonance patterns."""
    if not ResonanceEngine:
        raise HTTPException(status_code=501, detail="Resonance engine not available")
    
    try:
        engine = ResonanceEngine()
        analysis = await engine.analyze(signal)
        return {
            "success": True,
            "resonance_score": analysis.get("score", 0.0),
            "patterns": analysis.get("patterns", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resonance analysis failed: {str(e)}")


@router.get("/resonance/state")
async def get_resonance_state(
    current_user: dict = Depends(get_current_user),
):
    """Get current resonance state."""
    if not ResonanceService:
        raise HTTPException(status_code=501, detail="Resonance service not available")
    
    try:
        service = ResonanceService()
        state = await service.get_state()
        return {
            "success": True,
            "resonance_state": state,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get state: {str(e)}")


@router.post("/harmonic/enforce")
async def enforce_harmonic_constraints(
    constraints: Dict[str, Any],
    current_user: dict = Depends(check_permission("write")),
):
    """Enforce harmonic constraints."""
    if not HarmonicEngine:
        raise HTTPException(status_code=501, detail="Harmonic engine not available")
    
    try:
        engine = HarmonicEngine()
        result = await engine.enforce(constraints)
        return {
            "success": True,
            "enforced": result.get("enforced", False),
            "violations": result.get("violations", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enforcement failed: {str(e)}")


@router.post("/secret-fire/invoke")
async def invoke_secret_fire(
    target: str,
    intent: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Invoke secret fire protection."""
    if not SecretFire:
        raise HTTPException(status_code=501, detail="Secret fire not available")
    
    try:
        sf = SecretFire()
        result = await sf.invoke(target, intent)
        return {
            "success": True,
            "target": target,
            "fire_result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Secret fire invocation failed: {str(e)}")


@router.post("/verity/verify")
async def verify_with_verity(
    claim: str,
    evidence: Dict[str, Any],
    current_user: dict = Depends(check_permission("read")),
):
    """Verify a claim with verity engine."""
    if not VerityEngine:
        raise HTTPException(status_code=501, detail="Verity engine not available")
    
    try:
        engine = VerityEngine()
        verification = await engine.verify(claim, evidence)
        return {
            "success": True,
            "claim": claim,
            "verified": verification.get("verified", False),
            "confidence": verification.get("confidence", 0.0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/scrutiny/deep-analyze")
async def deep_scrutiny_analysis(
    target: str,
    depth: str = "comprehensive",
    current_user: dict = Depends(check_permission("read")),
):
    """Perform deep scrutiny analysis."""
    if not ScrutinyEngine:
        raise HTTPException(status_code=501, detail="Scrutiny engine not available")
    
    try:
        engine = ScrutinyEngine()
        analysis = await engine.deep_analyze(target, depth=depth)
        return {
            "success": True,
            "target": target,
            "depth": depth,
            "analysis": analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deep analysis failed: {str(e)}")
