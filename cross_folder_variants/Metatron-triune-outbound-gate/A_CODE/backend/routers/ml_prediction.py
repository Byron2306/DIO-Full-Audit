"""
ML Threat Prediction Router
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel

from .dependencies import get_current_user, check_permission
from ml_threat_prediction import ml_predictor, MLThreatPredictor

router = APIRouter(prefix="/ml", tags=["ML Threat Prediction"])


class NetworkPredictionRequest(BaseModel):
    source_ip: str
    bytes_in: int = 0
    bytes_out: int = 0
    packets_in: int = 0
    packets_out: int = 0
    unique_destinations: int = 0
    unique_ports: int = 0
    dns_queries: int = 0
    failed_connections: int = 0
    encrypted_ratio: float = 0.5
    avg_packet_size: float = 500.0
    connection_duration: float = 30.0
    port_scan_score: float = 0.0


class ProcessPredictionRequest(BaseModel):
    process_name: str
    pid: int = 0
    cpu_usage: float = 5.0
    memory_usage: float = 100.0
    file_operations: int = 10
    registry_operations: int = 0
    network_connections: int = 0
    child_processes: int = 0
    dll_loads: int = 10
    suspicious_api_calls: int = 0
    entropy: float = 4.0
    execution_time: float = 10.0


class FilePredictionRequest(BaseModel):
    filename: str
    hash: Optional[str] = None
    size: int = 0
    entropy: float = 5.0
    is_packed: bool = False
    has_signature: bool = True
    import_count: int = 50
    export_count: int = 0
    is_obfuscated: bool = False
    strings_count: int = 100
    has_overlay: bool = False
    section_count: int = 5
    suspicious_sections: bool = False
    vt_detection_ratio: float = 0.0


class UserPredictionRequest(BaseModel):
    user_id: str
    username: str
    login_hour: int = 12
    login_day: int = 3
    failed_logins: int = 0
    resources_accessed: int = 10
    data_transferred: int = 0
    anomaly_score: float = 0.0
    geo_distance: float = 0.0
    device_trust: float = 1.0
    unusual_time: bool = False
    unusual_location: bool = False
    privilege_escalations: int = 0
    sensitive_access: int = 0


@router.get("/stats")
async def get_ml_stats(current_user: dict = Depends(get_current_user)):
    """Get ML prediction service statistics"""
    return ml_predictor.get_stats()


@router.get("/predictions")
async def get_predictions(
    limit: int = 50,
    entity_type: Optional[str] = None,
    min_score: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get recent ML predictions"""
    predictions = await ml_predictor.get_predictions_from_db(
        limit=limit,
        entity_type=entity_type,
        min_score=min_score
    )
    return {"predictions": predictions, "count": len(predictions)}


@router.get("/predictions/{prediction_id}")
async def get_prediction(prediction_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific prediction by ID"""
    prediction = ml_predictor.get_prediction(prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction


@router.post("/predict/network")
async def predict_network_threat(
    request: NetworkPredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze network traffic with ML for threat prediction"""
    prediction = await ml_predictor.predict_network_threat(request.model_dump())
    return {
        "prediction_id": prediction.prediction_id,
        "threat_score": prediction.threat_score,
        "category": prediction.predicted_category.value,
        "risk_level": prediction.risk_level.value,
        "confidence": round(prediction.confidence, 2),
        "contributing_factors": prediction.contributing_factors,
        "recommended_actions": prediction.recommended_actions,
        "mitre_mappings": prediction.mitre_mappings
    }


@router.post("/predict/process")
async def predict_process_threat(
    request: ProcessPredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze process behavior with ML for threat prediction"""
    prediction = await ml_predictor.predict_process_threat(request.model_dump())
    return {
        "prediction_id": prediction.prediction_id,
        "threat_score": prediction.threat_score,
        "category": prediction.predicted_category.value,
        "risk_level": prediction.risk_level.value,
        "confidence": round(prediction.confidence, 2),
        "contributing_factors": prediction.contributing_factors,
        "recommended_actions": prediction.recommended_actions,
        "mitre_mappings": prediction.mitre_mappings
    }


@router.post("/predict/file")
async def predict_file_threat(
    request: FilePredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze file with ML for threat prediction"""
    prediction = await ml_predictor.predict_file_threat(request.model_dump())
    return {
        "prediction_id": prediction.prediction_id,
        "threat_score": prediction.threat_score,
        "category": prediction.predicted_category.value,
        "risk_level": prediction.risk_level.value,
        "confidence": round(prediction.confidence, 2),
        "contributing_factors": prediction.contributing_factors,
        "recommended_actions": prediction.recommended_actions,
        "mitre_mappings": prediction.mitre_mappings
    }


@router.post("/predict/user")
async def predict_user_threat(
    request: UserPredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze user behavior with ML for insider threat prediction (UEBA)"""
    prediction = await ml_predictor.predict_user_threat(request.model_dump())
    return {
        "prediction_id": prediction.prediction_id,
        "threat_score": prediction.threat_score,
        "category": prediction.predicted_category.value,
        "risk_level": prediction.risk_level.value,
        "confidence": round(prediction.confidence, 2),
        "contributing_factors": prediction.contributing_factors,
        "recommended_actions": prediction.recommended_actions,
        "mitre_mappings": prediction.mitre_mappings
    }
