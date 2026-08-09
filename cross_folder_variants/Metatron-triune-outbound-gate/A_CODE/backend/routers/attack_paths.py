"""
Attack Path Analysis API Router
================================
REST API endpoints for crown jewel asset protection, blast radius analysis,
and attack path visualization.

Endpoints:
- POST /assets - Register a crown jewel asset
- GET /assets - List crown jewel assets
- GET /assets/{asset_id} - Get asset details
- DELETE /assets/{asset_id} - Remove asset
- GET /assets/{asset_id}/blast-radius - Get blast radius
- GET /assets/{asset_id}/attack-paths - Get attack paths to asset
- POST /analysis/full - Run full attack path analysis
- GET /graph - Get attack graph visualization

Author: Seraph Security Team
Version: 1.0.0
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import asyncio
import logging
import ipaddress

from attack_path_analysis import (
    get_attack_path_analyzer,
    AttackPathAnalyzer,
    CrownJewelAsset,
    AssetType,
    CriticalityLevel,
    AttackPath,
    BlastRadiusResult,
)
from .dependencies import check_permission, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attack-paths", tags=["Attack Path Analysis"])

_CROWN_JEWELS_COLLECTION = "attack_path_crown_jewels"


async def _persist_crown_jewel(asset: CrownJewelAsset) -> None:
    db = get_db()
    if db is None:
        return
    await db[_CROWN_JEWELS_COLLECTION].update_one(
        {"asset_id": asset.asset_id},
        {
            "$set": {
                "asset_id": asset.asset_id,
                "name": asset.name,
                "asset_type": asset.asset_type.value,
                "identifier": asset.identifier,
                "criticality": asset.criticality.value,
                "description": asset.description,
                "owner": asset.owner,
                "data_classification": asset.data_classification,
                "compliance_scope": asset.compliance_scope,
                "tags": asset.tags,
                "dependencies": asset.dependencies,
                "network_zone": asset.network_zone,
                "created_at": asset.created_at,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )


async def _remove_crown_jewel(asset_id: str) -> None:
    db = get_db()
    if db is None:
        return
    await db[_CROWN_JEWELS_COLLECTION].delete_one({"asset_id": asset_id})


async def _hydrate_crown_jewels_from_db() -> None:
    """Rehydrate in-memory analyzer from persisted crown jewel records."""
    analyzer = get_attack_path_analyzer()
    if analyzer.crown_jewels:
        return

    db = get_db()
    if db is None:
        return

    docs = await db[_CROWN_JEWELS_COLLECTION].find({}, {"_id": 0}).to_list(1000)
    for doc in docs:
        try:
            asset = CrownJewelAsset(
                name=doc.get("name", "Unnamed Asset"),
                asset_type=AssetType(doc.get("asset_type", "application_server")),
                identifier=doc.get("identifier", "unknown"),
                criticality=CriticalityLevel(doc.get("criticality", "high")),
                description=doc.get("description", ""),
                owner=doc.get("owner", ""),
                data_classification=doc.get("data_classification", "confidential"),
                compliance_scope=doc.get("compliance_scope", []),
                tags=doc.get("tags", {}),
                dependencies=doc.get("dependencies", []),
                network_zone=doc.get("network_zone", "internal"),
                asset_id=doc.get("asset_id"),
                created_at=doc.get("created_at") or datetime.now(timezone.utc).isoformat(),
                updated_at=doc.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            )
            analyzer.register_crown_jewel(asset)
        except Exception as exc:
            logger.warning(f"Skipping invalid persisted crown jewel record: {exc}")


async def _create_crown_jewel(request: "AssetCreateRequest") -> CrownJewelAsset:
    try:
        asset_type = AssetType(request.asset_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset type: {request.asset_type}. "
                   f"Valid types: {[t.value for t in AssetType]}"
        )

    try:
        criticality = CriticalityLevel(request.criticality)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid criticality: {request.criticality}. "
                   f"Valid levels: {[c.value for c in CriticalityLevel]}"
        )

    analyzer = get_attack_path_analyzer()
    asset = CrownJewelAsset(
        name=request.name,
        asset_type=asset_type,
        identifier=request.identifier,
        criticality=criticality,
        description=request.description or "",
        owner=request.owner or "",
        data_classification=request.data_classification or "confidential",
        compliance_scope=request.compliance_scope or [],
        tags=request.tags or {},
        dependencies=request.dependencies or [],
        network_zone=request.network_zone or "internal",
    )

    analyzer.register_crown_jewel(asset)
    await _persist_crown_jewel(asset)
    return asset


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AssetCreateRequest(BaseModel):
    """Request to register a crown jewel asset"""
    name: str = Field(..., description="Asset name")
    asset_type: str = Field(..., description="Asset type: server, database, application, network_device, identity_store, secrets_vault, endpoint, container, cloud_resource")
    identifier: str = Field(..., description="Unique identifier (IP, hostname, ARN, etc.)")
    criticality: str = Field(default="high", description="Criticality: low, medium, high, critical, crown_jewel")
    description: Optional[str] = Field(None, description="Asset description")
    owner: Optional[str] = Field(None, description="Asset owner/team")
    data_classification: Optional[str] = Field(None, description="Data sensitivity level")
    compliance_scope: Optional[List[str]] = Field(None, description="Compliance frameworks")
    tags: Optional[Dict[str, str]] = Field(None, description="Custom tags")
    dependencies: Optional[List[str]] = Field(None, description="List of dependent asset IDs")
    network_zone: Optional[str] = Field(None, description="Network zone (dmz, internal, cloud, etc.)")


class AssetResponse(BaseModel):
    """Crown jewel asset response"""
    asset_id: str
    name: str
    asset_type: str
    identifier: str
    criticality: str
    criticality_score: int
    description: Optional[str]
    owner: Optional[str]
    data_classification: Optional[str]
    compliance_scope: List[str]
    tags: Dict[str, str]
    dependencies: List[str]
    network_zone: str
    created_at: str
    updated_at: str


class AssetListResponse(BaseModel):
    """List of assets response"""
    total: int
    assets: List[AssetResponse]


class AttackPathResponse(BaseModel):
    """Attack path response"""
    path_id: str
    source: str
    target: str
    path_length: int
    risk_score: int
    mitre_techniques: List[str]
    steps: List[Dict[str, Any]]
    mitigations: List[str]


class BlastRadiusResponse(BaseModel):
    """Blast radius analysis response"""
    asset_id: str
    asset_name: str
    total_affected: int
    affected_by_criticality: Dict[str, int]
    affected_assets: List[Dict[str, Any]]
    risk_summary: Dict[str, Any]
    recommendations: List[str]


class FullAnalysisRequest(BaseModel):
    """Request for full attack path analysis"""
    include_external_threats: bool = Field(default=True)
    max_path_length: int = Field(default=10, ge=1, le=20)
    min_risk_score: int = Field(default=0, ge=0, le=100)


class FullAnalysisResponse(BaseModel):
    """Full analysis result"""
    analysis_id: str
    timestamp: str
    total_assets: int
    total_paths: int
    high_risk_paths: int
    critical_findings: List[Dict[str, Any]]
    risk_heatmap: Dict[str, int]
    recommendations: List[str]


class GraphResponse(BaseModel):
    """Attack graph visualization data"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    clusters: List[Dict[str, Any]]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/assets", response_model=AssetResponse, status_code=201)
async def register_asset(
    request: AssetCreateRequest,
    current_user: dict = Depends(check_permission("manage_users")),
):
    """
    Register a crown jewel asset for attack path monitoring.
    
    Crown jewels are critical assets that require enhanced protection.
    Registering them enables:
    - Blast radius analysis
    - Attack path discovery
    - Priority alerting
    - Compliance tracking
    """
    _ = current_user
    await _hydrate_crown_jewels_from_db()
    asset = await _create_crown_jewel(request)
    
    return AssetResponse(
        asset_id=asset.asset_id,
        name=asset.name,
        asset_type=asset.asset_type.value,
        identifier=asset.identifier,
        criticality=asset.criticality.value,
        criticality_score=asset.criticality_score,
        description=asset.description,
        owner=asset.owner,
        data_classification=asset.data_classification,
        compliance_scope=asset.compliance_scope,
        tags=asset.tags,
        dependencies=asset.dependencies,
        network_zone=asset.network_zone,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


@router.get("/assets", response_model=AssetListResponse)
async def list_assets(
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    criticality: Optional[str] = Query(None, description="Filter by criticality"),
    network_zone: Optional[str] = Query(None, description="Filter by network zone"),
    tag_key: Optional[str] = Query(None, description="Filter by tag key"),
    tag_value: Optional[str] = Query(None, description="Filter by tag value"),
):
    """
    List registered crown jewel assets.
    
    Supports filtering by various criteria.
    """
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    assets = list(analyzer.crown_jewels.values())
    
    # Apply filters
    if asset_type:
        assets = [a for a in assets if a.asset_type.value == asset_type]
    
    if criticality:
        assets = [a for a in assets if a.criticality.value == criticality]
    
    if network_zone:
        assets = [a for a in assets if a.network_zone == network_zone]
    
    if tag_key and tag_value:
        assets = [a for a in assets if a.tags.get(tag_key) == tag_value]
    elif tag_key:
        assets = [a for a in assets if tag_key in a.tags]
    
    return AssetListResponse(
        total=len(assets),
        assets=[
            AssetResponse(
                asset_id=a.asset_id,
                name=a.name,
                asset_type=a.asset_type.value,
                identifier=a.identifier,
                criticality=a.criticality.value,
                criticality_score=a.criticality_score,
                description=a.description,
                owner=a.owner,
                data_classification=a.data_classification,
                compliance_scope=a.compliance_scope,
                tags=a.tags,
                dependencies=a.dependencies,
                network_zone=a.network_zone,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in assets
        ]
    )


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: str):
    """Get details of a specific crown jewel asset."""
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    
    asset = analyzer.crown_jewels.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    
    return AssetResponse(
        asset_id=asset.asset_id,
        name=asset.name,
        asset_type=asset.asset_type.value,
        identifier=asset.identifier,
        criticality=asset.criticality.value,
        criticality_score=asset.criticality_score,
        description=asset.description,
        owner=asset.owner,
        data_classification=asset.data_classification,
        compliance_scope=asset.compliance_scope,
        tags=asset.tags,
        dependencies=asset.dependencies,
        network_zone=asset.network_zone,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: str,
    current_user: dict = Depends(check_permission("manage_users")),
):
    """Remove a crown jewel asset from monitoring."""
    _ = current_user
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    
    if asset_id not in analyzer.crown_jewels:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    
    del analyzer.crown_jewels[asset_id]
    await _remove_crown_jewel(asset_id)
    
    return {"message": f"Asset {asset_id} removed", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/assets/{asset_id}/blast-radius", response_model=BlastRadiusResponse)
async def get_blast_radius(
    asset_id: str,
    depth: int = Query(3, ge=1, le=10, description="Analysis depth"),
):
    """
    Calculate blast radius if an asset is compromised.
    
    Returns all assets that could be affected by the compromise,
    categorized by criticality and impact level.
    """
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    
    if asset_id not in analyzer.crown_jewels:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    
    result = await analyzer.calculate_blast_radius(asset_id, max_depth=depth)
    
    return BlastRadiusResponse(
        asset_id=result.source_asset,
        asset_name=analyzer.crown_jewels[asset_id].name,
        total_affected=result.total_affected,
        affected_by_criticality={
            k.value if hasattr(k, 'value') else str(k): v 
            for k, v in result.affected_by_criticality.items()
        },
        affected_assets=[
            {
                "asset_id": a.asset_id,
                "name": a.name,
                "criticality": a.criticality.value,
                "impact_level": result.impact_by_asset.get(a.asset_id, "unknown"),
            }
            for a in result.affected_assets
        ],
        risk_summary={
            "blast_radius_score": result.blast_radius_score,
            "max_criticality_affected": result.max_criticality_affected.value if result.max_criticality_affected else "none",
        },
        recommendations=result.recommendations,
    )


@router.get("/assets/{asset_id}/attack-paths")
async def get_attack_paths(
    asset_id: str,
    max_paths: int = Query(10, ge=1, le=50),
    min_risk: int = Query(0, ge=0, le=100),
):
    """
    Discover attack paths leading to a crown jewel asset.
    
    Identifies potential attack chains from external or internal
    threat sources to the target asset.
    """
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    
    if asset_id not in analyzer.crown_jewels:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    
    paths = await analyzer.find_attack_paths(
        target_asset_id=asset_id,
        max_paths=max_paths,
        min_risk_score=min_risk,
    )
    
    return {
        "target_asset": asset_id,
        "total_paths": len(paths),
        "paths": [
            AttackPathResponse(
                path_id=p.path_id,
                source=p.source_asset,
                target=p.target_asset,
                path_length=len(p.steps),
                risk_score=p.risk_score,
                mitre_techniques=p.mitre_techniques,
                steps=[
                    {
                        "step": i + 1,
                        "from_asset": step.get("from"),
                        "to_asset": step.get("to"),
                        "technique": step.get("technique"),
                        "description": step.get("description"),
                    }
                    for i, step in enumerate(p.steps)
                ],
                mitigations=p.mitigations,
            )
            for p in paths
        ]
    }


@router.post("/analysis/full", response_model=FullAnalysisResponse)
async def run_full_analysis(
    request: FullAnalysisRequest,
    background_tasks: BackgroundTasks,
):
    """
    Run comprehensive attack path analysis across all assets.
    
    Analyzes all crown jewel assets to identify:
    - All attack paths
    - High-risk paths requiring immediate attention
    - Common vulnerabilities across paths
    - Risk heatmap by asset and zone
    """
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    
    if not analyzer.crown_jewels:
        raise HTTPException(
            status_code=400, 
            detail="No crown jewel assets registered. Register assets first."
        )
    
    analysis_id = f"analysis-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    # Run analysis
    all_paths = []
    for asset_id in analyzer.crown_jewels:
        paths = await analyzer.find_attack_paths(
            target_asset_id=asset_id,
            max_paths=20,
            min_risk_score=request.min_risk_score,
        )
        all_paths.extend(paths)
    
    # Calculate risk heatmap
    risk_heatmap = {}
    for path in all_paths:
        for step in path.steps:
            asset = step.get("to", step.get("from"))
            if asset:
                risk_heatmap[asset] = risk_heatmap.get(asset, 0) + path.risk_score // len(path.steps)
    
    # Identify critical findings
    high_risk_paths = [p for p in all_paths if p.risk_score >= 70]
    critical_findings = [
        {
            "path_id": p.path_id,
            "risk_score": p.risk_score,
            "target": p.target_asset,
            "techniques": p.mitre_techniques[:3],
            "recommendation": p.mitigations[0] if p.mitigations else "Review path manually",
        }
        for p in sorted(high_risk_paths, key=lambda x: x.risk_score, reverse=True)[:10]
    ]
    
    # Generate recommendations
    recommendations = []
    if high_risk_paths:
        recommendations.append(f"Address {len(high_risk_paths)} high-risk attack paths immediately")
    
    # Common techniques across paths
    technique_counts: Dict[str, int] = {}
    for path in all_paths:
        for tech in path.mitre_techniques:
            technique_counts[tech] = technique_counts.get(tech, 0) + 1
    
    top_techniques = sorted(technique_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    for tech, count in top_techniques:
        recommendations.append(f"Implement controls for {tech} (appears in {count} paths)")
    
    return FullAnalysisResponse(
        analysis_id=analysis_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_assets=len(analyzer.crown_jewels),
        total_paths=len(all_paths),
        high_risk_paths=len(high_risk_paths),
        critical_findings=critical_findings,
        risk_heatmap=risk_heatmap,
        recommendations=recommendations,
    )


@router.get("/graph", response_model=GraphResponse)
async def get_attack_graph(
    include_paths: bool = Query(True, description="Include attack paths in graph"),
    min_criticality: str = Query("medium", description="Minimum asset criticality to include"),
):
    """
    Get attack graph data for visualization.
    
    Returns nodes (assets) and edges (relationships/paths)
    suitable for graph visualization libraries.
    """
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    
    # Build nodes
    nodes = []
    for asset_id, asset in analyzer.crown_jewels.items():
        nodes.append({
            "id": asset_id,
            "label": asset.name,
            "type": asset.asset_type.value,
            "criticality": asset.criticality.value,
            "criticality_score": asset.criticality_score,
            "network_zone": asset.network_zone,
            "size": 10 + asset.criticality_score // 10,  # Size based on criticality
        })
    
    # Build edges from dependencies
    edges = []
    edge_id = 0
    for asset_id, asset in analyzer.crown_jewels.items():
        for dep_id in asset.dependencies:
            if dep_id in analyzer.crown_jewels:
                edges.append({
                    "id": f"edge-{edge_id}",
                    "source": dep_id,
                    "target": asset_id,
                    "type": "dependency",
                    "label": "depends_on",
                })
                edge_id += 1
    
    # Include attack paths as edges
    if include_paths:
        for path in analyzer.attack_paths.values():
            for i, step in enumerate(path.steps[:-1]):
                from_asset = step.get("from") or step.get("to")
                to_asset = path.steps[i + 1].get("to") or path.steps[i + 1].get("from")
                if from_asset and to_asset:
                    edges.append({
                        "id": f"path-{path.path_id}-{i}",
                        "source": from_asset,
                        "target": to_asset,
                        "type": "attack_path",
                        "risk_score": path.risk_score,
                        "technique": step.get("technique", "unknown"),
                    })
    
    # Group by network zone
    clusters = []
    zones = set(a.network_zone for a in analyzer.crown_jewels.values())
    for zone in zones:
        zone_assets = [a.asset_id for a in analyzer.crown_jewels.values() if a.network_zone == zone]
        clusters.append({
            "id": f"zone-{zone}",
            "label": zone.upper(),
            "members": zone_assets,
        })
    
    return GraphResponse(
        nodes=nodes,
        edges=edges,
        clusters=clusters,
    )


# =============================================================================
# FRONTEND COMPATIBILITY ENDPOINTS
# =============================================================================

def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        return int(str(value).strip())
    except Exception:
        return default


def _severity_to_risk(severity: str) -> int:
    s = str(severity or "").lower().strip()
    if s == "critical":
        return 95
    if s == "high":
        return 80
    if s == "medium":
        return 60
    if s == "low":
        return 35
    return 50


def _severity_to_probability(severity: str) -> float:
    s = str(severity or "").lower().strip()
    if s == "critical":
        return 0.9
    if s == "high":
        return 0.75
    if s == "medium":
        return 0.55
    if s == "low":
        return 0.35
    return 0.5


def _is_private_ip(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(str(value).strip())
        return bool(addr.is_private or addr.is_loopback or addr.is_link_local)
    except Exception:
        return False


def _attack_source_id(ip_value: str) -> str:
    raw = str(ip_value or "").strip()
    return f"src:{raw}" if raw else "src:unknown"


def _asset_node_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "asset:unknown"
    # Avoid collisions with source node ids.
    return raw if raw.startswith(("asset:", "host:", "cj:", "threat:")) else f"asset:{raw}"


async def _build_connected_attack_graph(
    *,
    max_nodes: int = 200,
    max_edges: int = 400,
) -> Dict[str, Any]:
    """Build a connected, UI-friendly attack graph from DB + crown jewels.

    The core AttackPathAnalyzer focuses on crown jewel registration. The React
    AttackPathsPage expects a graph even on fresh installs, so we derive a
    lightweight graph from recent threats/alerts and discovered agents.
    """
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    db = get_db()

    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    # 1) Crown jewels: persisted, otherwise inferred from most-targeted assets.
    crown_jewels: List[Dict[str, Any]] = []
    if analyzer.crown_jewels:
        for asset in analyzer.crown_jewels.values():
            nid = asset.asset_id
            risk_score = max(75, min(99, _as_int(asset.criticality_score, 90)))
            node = {
                "id": nid,
                "name": asset.name,
                "type": "crown_jewel",
                "asset_type": asset.asset_type.value,
                "criticality": asset.criticality.value,
                "identifier": asset.identifier,
                "risk_score": risk_score,
                "is_critical": True,
                "vulnerabilities": [],
            }
            nodes_by_id[nid] = node
            crown_jewels.append(
                {
                    "id": asset.asset_id,
                    "name": asset.name,
                    "criticality": asset.criticality.value,
                    "type": asset.asset_type.value,
                    "paths_to": 0,
                }
            )
    elif db is not None:
        # Infer jewels from recent targets.
        threats = await db.threats.find({}, {"_id": 0, "target_system": 1, "severity": 1}).sort("created_at", -1).limit(200).to_list(200)
        target_scores: Dict[str, int] = {}
        for t in threats:
            target = str(t.get("target_system") or "").strip()
            if not target:
                continue
            target_scores[target] = target_scores.get(target, 0) + _severity_to_risk(t.get("severity"))
        for target, score in sorted(target_scores.items(), key=lambda kv: kv[1], reverse=True)[:5]:
            nid = _asset_node_id(target)
            nodes_by_id[nid] = {
                "id": nid,
                "name": target,
                "type": "crown_jewel",
                "asset_type": "inferred",
                "criticality": "critical",
                "identifier": target,
                "risk_score": min(99, max(80, int(score / max(1, len(threats)) * 10))),
                "is_critical": True,
                "vulnerabilities": [],
            }
            crown_jewels.append(
                {"id": nid, "name": target, "criticality": "critical", "type": "inferred", "paths_to": 0}
            )

    # 2) Fleet assets: registered agents + discovered devices (best-effort).
    if db is not None:
        agents = await db.unified_agents.find(
            {},
            {"_id": 0, "agent_id": 1, "hostname": 1, "ip_address": 1, "platform": 1, "threat_count": 1, "last_heartbeat": 1},
        ).sort("last_heartbeat", -1).limit(80).to_list(80)
        for a in agents:
            hostname = a.get("hostname") or a.get("agent_id")
            ip_addr = a.get("ip_address")
            nid = _asset_node_id(hostname or ip_addr or a.get("agent_id"))
            if nid in nodes_by_id:
                continue
            threat_count = _as_int(a.get("threat_count"), 0)
            nodes_by_id[nid] = {
                "id": nid,
                "name": hostname or nid,
                "type": "asset",
                "asset_type": "endpoint",
                "platform": a.get("platform"),
                "ip": ip_addr,
                "risk_score": min(90, 20 + threat_count * 15),
                "is_critical": False,
                "vulnerabilities": [],
            }

        discovered = await db.discovered_devices.find(
            {}, {"_id": 0, "hostname": 1, "ip_address": 1, "last_seen": 1, "risk_score": 1}
        ).sort("last_seen", -1).limit(80).to_list(80)
        for d in discovered:
            hostname = d.get("hostname") or d.get("ip_address")
            nid = _asset_node_id(hostname)
            if nid in nodes_by_id:
                continue
            nodes_by_id[nid] = {
                "id": nid,
                "name": hostname or nid,
                "type": "asset",
                "asset_type": "discovered",
                "ip": d.get("ip_address"),
                "risk_score": min(90, max(0, _as_int(d.get("risk_score"), 45))),
                "is_critical": False,
                "vulnerabilities": [],
            }

    # 3) Threat edges: source_ip -> target_system/asset. Use technique fields when present.
    entry_sources: List[str] = []
    if db is not None:
        threats = await db.threats.find(
            {},
            {"_id": 0, "id": 1, "type": 1, "severity": 1, "status": 1, "source_ip": 1, "target_system": 1, "created_at": 1, "mitre_techniques": 1},
        ).sort("created_at", -1).limit(250).to_list(250)
        for t in threats:
            src_ip = str(t.get("source_ip") or "").strip()
            target = str(t.get("target_system") or "").strip()
            if not src_ip or not target:
                continue

            src_id = _attack_source_id(src_ip)
            if src_id not in nodes_by_id:
                nodes_by_id[src_id] = {
                    "id": src_id,
                    "name": src_ip,
                    "type": "attack_source",
                    "risk_score": min(95, _severity_to_risk(t.get("severity"))),
                    "is_critical": False,
                    "vulnerabilities": [],
                }
            if not _is_private_ip(src_ip):
                entry_sources.append(src_id)

            target_id = None
            # If we have an inferred crown jewel for the raw target, reuse it.
            for candidate in (target, _asset_node_id(target)):
                if candidate in nodes_by_id:
                    target_id = candidate
                    break
            if target_id is None:
                target_id = _asset_node_id(target)
                nodes_by_id.setdefault(
                    target_id,
                    {
                        "id": target_id,
                        "name": target,
                        "type": "asset",
                        "asset_type": "target",
                        "risk_score": 40,
                        "is_critical": False,
                        "vulnerabilities": [],
                    },
                )

            mitre = t.get("mitre_techniques") or []
            mitre_id = mitre[0] if isinstance(mitre, list) and mitre else None
            is_critical = bool(nodes_by_id.get(target_id, {}).get("type") == "crown_jewel")
            edges.append(
                {
                    "source": src_id,
                    "target": target_id,
                    "technique": str(t.get("type") or "threat_signal"),
                    "mitre_id": mitre_id,
                    "probability": _severity_to_probability(t.get("severity")),
                    "is_critical": is_critical,
                }
            )

    # Enforce size limits deterministically.
    nodes = list(nodes_by_id.values())[: max(1, int(max_nodes))]
    allowed = {n["id"] for n in nodes}
    edges = [e for e in edges if e.get("source") in allowed and e.get("target") in allowed][: max(0, int(max_edges))]

    # Compute critical paths (shortest paths from entry sources to crown jewels).
    adjacency: Dict[str, List[str]] = {}
    for e in edges:
        adjacency.setdefault(e["source"], []).append(e["target"])

    jewel_ids = [j["id"] for j in crown_jewels]
    entry_sources = list(dict.fromkeys(entry_sources))  # stable dedupe
    if not entry_sources:
        # If we have no external sources, allow any attack_source as entry.
        entry_sources = [n["id"] for n in nodes if n.get("type") == "attack_source"][:10]

    critical_paths: List[Dict[str, Any]] = []
    for jewel_id in jewel_ids[:6]:
        # BFS for shortest path.
        best_path = None
        for start in entry_sources[:10]:
            queue: List[List[str]] = [[start]]
            seen = {start}
            while queue and len(critical_paths) < 20:
                path = queue.pop(0)
                current = path[-1]
                if len(path) > 10:
                    continue
                if current == jewel_id:
                    best_path = path
                    queue = []
                    break
                for nxt in adjacency.get(current, [])[:20]:
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    queue.append([*path, nxt])
        if best_path and len(best_path) >= 2:
            # Compute risk score from nodes + edges.
            node_risk = max((_as_int(nodes_by_id.get(nid, {}).get("risk_score"), 0) for nid in best_path), default=0)
            critical_paths.append(
                {
                    "id": f"path:{best_path[0]}->{jewel_id}",
                    "name": " → ".join(nodes_by_id.get(n, {}).get("name", n) for n in best_path),
                    "risk_score": max(50, node_risk),
                    "length": len(best_path),
                    "techniques": [],
                    "blocked": False,
                    "steps": [
                        {"from": best_path[i], "to": best_path[i + 1], "technique": "path_edge"}
                        for i in range(len(best_path) - 1)
                    ],
                }
            )

    # Populate crown jewel inbound path counts.
    inbound_counts: Dict[str, int] = {}
    for e in edges:
        if e.get("target") in jewel_ids:
            inbound_counts[e["target"]] = inbound_counts.get(e["target"], 0) + 1
    for j in crown_jewels:
        j["paths_to"] = inbound_counts.get(j["id"], 0)

    return {
        "nodes": nodes,
        "edges": edges,
        "crown_jewels": crown_jewels,
        "critical_paths": critical_paths,
    }


@router.get("/analysis")
async def get_analysis_compat():
    """Compatibility endpoint for AttackPathsPage initial load."""
    view = await _build_connected_attack_graph()
    return {
        "attack_graph": {
            "nodes": view.get("nodes", []),
            "edges": view.get("edges", []),
        },
        "critical_paths": view.get("critical_paths", []),
    }


@router.get("/crown-jewels")
async def get_crown_jewels_compat():
    """Compatibility endpoint for AttackPathsPage crown jewel panel."""
    view = await _build_connected_attack_graph()
    jewels = view.get("crown_jewels", [])
    return {"crown_jewels": jewels, "count": len(jewels)}


@router.post("/crown-jewels")
async def add_crown_jewel_compat(
    payload: Dict[str, Any],
    current_user: dict = Depends(check_permission("manage_users")),
):
    """Compatibility endpoint for quickly adding crown jewels from the UI."""
    _ = current_user
    await _hydrate_crown_jewels_from_db()
    name = (payload.get("name") or "").strip()
    identifier = (payload.get("identifier") or payload.get("ip") or payload.get("hostname") or "").strip()
    if not name or not identifier:
        raise HTTPException(status_code=400, detail="name and identifier are required")

    raw_asset_type = (payload.get("asset_type") or payload.get("type") or "application_server").strip().lower()
    asset_type_aliases = {
        "server": "application_server",
        "database": "database_server",
        "db": "database_server",
        "identity": "domain_controller",
        "secrets_vault": "secret_vault",
        "network": "network_device",
    }
    normalized_asset_type = asset_type_aliases.get(raw_asset_type, raw_asset_type)

    request = AssetCreateRequest(
        name=name,
        asset_type=normalized_asset_type,
        identifier=identifier,
        criticality=(payload.get("criticality") or "critical"),
        description=payload.get("description"),
        owner=payload.get("owner"),
        data_classification=payload.get("data_classification"),
        compliance_scope=payload.get("compliance_scope"),
        tags=payload.get("tags"),
        dependencies=payload.get("dependencies"),
        network_zone=payload.get("network_zone"),
    )

    created_asset = await _create_crown_jewel(request)
    created = AssetResponse(
        asset_id=created_asset.asset_id,
        name=created_asset.name,
        asset_type=created_asset.asset_type.value,
        identifier=created_asset.identifier,
        criticality=created_asset.criticality.value,
        criticality_score=created_asset.criticality_score,
        description=created_asset.description,
        owner=created_asset.owner,
        data_classification=created_asset.data_classification,
        compliance_scope=created_asset.compliance_scope,
        tags=created_asset.tags,
        dependencies=created_asset.dependencies,
        network_zone=created_asset.network_zone,
        created_at=created_asset.created_at,
        updated_at=created_asset.updated_at,
    )
    created_data = created.model_dump() if hasattr(created, "model_dump") else created.dict()

    return {
        "status": "created",
        "asset": {
            "id": created_data.get("asset_id"),
            "name": created_data.get("name"),
            "criticality": created_data.get("criticality"),
            "type": created_data.get("asset_type"),
            "identifier": created_data.get("identifier"),
        }
    }


@router.get("/stats")
async def get_stats_compat():
    """Compatibility endpoint for AttackPathsPage stat cards."""
    view = await _build_connected_attack_graph()
    nodes = view.get("nodes", [])
    critical_paths = view.get("critical_paths", [])
    total_assets = len([n for n in nodes if n.get("type") in {"asset", "crown_jewel"}])
    high_risk_nodes = len([n for n in nodes if _as_int(n.get("risk_score"), 0) >= 70])
    avg_path_length = (
        round(sum(_as_int(p.get("length"), 0) for p in critical_paths) / len(critical_paths), 2)
        if critical_paths
        else 0
    )
    blocked_paths = len([p for p in critical_paths if p.get("blocked")])
    return {
        "total_assets": total_assets,
        "critical_paths": len(critical_paths),
        "high_risk_nodes": high_risk_nodes,
        "avg_path_length": avg_path_length,
        "blocked_paths": blocked_paths,
    }


@router.post("/analyze")
async def analyze_compat(payload: Dict[str, Any]):
    """Compatibility endpoint for AttackPathsPage manual analysis action."""
    request = FullAnalysisRequest(
        include_external_threats=bool(payload.get("include_external_threats", True)),
        max_path_length=int(payload.get("max_depth", 10) or 10),
        min_risk_score=int(payload.get("min_risk_score", 0) or 0),
    )
    result = await run_full_analysis(request=request, background_tasks=BackgroundTasks())
    return result.model_dump() if hasattr(result, "model_dump") else result.dict()


@router.get("/blast-radius/{node_id}")
async def get_blast_radius_compat(node_id: str):
    """Compatibility endpoint for AttackPathsPage node click blast-radius request."""
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()

    # Frontend may click non-asset graph nodes; fail open with a neutral payload.
    if node_id not in analyzer.crown_jewels:
        return {
            "source_node": node_id,
            "affected_assets": 0,
            "critical_assets_at_risk": 0,
            "max_depth": 0,
            "affected_nodes": [],
        }

    result = await analyzer.calculate_blast_radius(node_id, max_depth=3)
    return {
        "source_node": node_id,
        "affected_assets": result.total_affected,
        "critical_assets_at_risk": len([
            a for a in result.affected_assets if getattr(a.criticality, "value", str(a.criticality)) in {"critical", "crown_jewel"}
        ]),
        "max_depth": 3,
        "affected_nodes": [a.asset_id for a in result.affected_assets],
    }


@router.get("/health")
async def health_check():
    """Health check for attack path analysis service."""
    await _hydrate_crown_jewels_from_db()
    analyzer = get_attack_path_analyzer()
    
    return {
        "status": "healthy",
        "total_assets": len(analyzer.crown_jewels),
        "total_paths": len(analyzer.attack_paths),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
