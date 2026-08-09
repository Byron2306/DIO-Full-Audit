"""
eBPF Kernel Sensors API Router
===============================
REST API endpoints for kernel-level telemetry management and monitoring.

Endpoints:
- GET /sensors - List all sensor states
- POST /sensors/{type}/start - Start a sensor
- POST /sensors/{type}/stop - Stop a sensor
- GET /sensors/stats - Get sensor statistics
- GET /events - Get recent kernel events
- GET /events/{event_id} - Get specific event
- POST /events/subscribe - WebSocket subscription
- GET /capabilities - Get platform capabilities

Author: Seraph Security Team
Version: 1.0.0
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio
import logging

from ebpf_kernel_sensors import (
    get_kernel_sensor_manager,
    KernelSensorManager,
    SensorType,
    SensorStatus,
    EventType,
    KernelEvent,
    ProcessEvent,
    FileEvent,
    NetworkEvent,
    MemoryEvent,
    ModuleEvent,
    Platform,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kernel", tags=["Kernel Sensors"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SensorStateResponse(BaseModel):
    """Sensor state response"""
    sensor_type: str
    status: str
    loaded_at: Optional[str] = None
    error_message: Optional[str] = None
    events_captured: int = 0
    events_dropped: int = 0
    last_event_at: Optional[str] = None


class SensorListResponse(BaseModel):
    """List of all sensor states"""
    platform: str
    kernel_version: str
    ebpf_available: bool
    sensors: Dict[str, SensorStateResponse]


class SensorActionRequest(BaseModel):
    """Request to start/stop sensor"""
    force: bool = Field(default=False, description="Force action even if sensor in error state")


class SensorActionResponse(BaseModel):
    """Response from sensor action"""
    success: bool
    sensor_type: str
    status: str
    message: str


class SensorStatsResponse(BaseModel):
    """Sensor statistics response"""
    platform: str
    kernel_version: str
    ebpf_available: bool
    events_total: int
    events_by_type: Dict[str, int]
    events_dropped: int
    errors: int
    uptime_seconds: Optional[float] = None
    sensors: Dict[str, SensorStateResponse]


class KernelEventResponse(BaseModel):
    """Kernel event response"""
    event_id: str
    event_type: str
    timestamp: str
    pid: int
    ppid: int
    uid: int
    gid: int
    comm: str
    container_id: Optional[str] = None
    namespace_pid: Optional[int] = None
    data: Dict[str, Any] = {}
    mitre_techniques: List[str] = []
    risk_score: int = 0


class EventListResponse(BaseModel):
    """List of kernel events"""
    total: int
    events: List[KernelEventResponse]
    page: int
    page_size: int


class ProcessEventResponse(KernelEventResponse):
    """Process event details"""
    filename: str = ""
    args: List[str] = []
    cwd: str = ""
    exit_code: Optional[int] = None
    cap_effective: int = 0


class FileEventResponse(KernelEventResponse):
    """File event details"""
    path: str = ""
    flags: int = 0
    mode: int = 0
    new_path: str = ""
    inode: int = 0


class NetworkEventResponse(KernelEventResponse):
    """Network event details"""
    family: int = 0
    protocol: int = 0
    local_addr: str = ""
    local_port: int = 0
    remote_addr: str = ""
    remote_port: int = 0
    direction: str = ""


class CapabilitiesResponse(BaseModel):
    """Platform capabilities response"""
    platform: str
    kernel_version: str
    ebpf_support: bool
    btf_support: bool
    available_sensors: List[str]
    required_capabilities: List[str]
    requirements_met: bool
    missing_requirements: List[str] = []


class EventFilterRequest(BaseModel):
    """Event filter for subscriptions"""
    event_types: Optional[List[str]] = None
    min_risk_score: int = 0
    process_names: Optional[List[str]] = None
    pids: Optional[List[int]] = None
    mitre_techniques: Optional[List[str]] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/sensors", response_model=SensorListResponse)
async def list_sensors():
    """
    List all kernel sensor states.
    
    Returns the current status of each sensor type including:
    - Whether the sensor is active, disabled, or in error
    - Event capture statistics
    - Platform and capability information
    """
    manager = get_kernel_sensor_manager()
    stats = manager.get_stats()
    
    sensors = {}
    for sensor_type, state in stats.get("sensors", {}).items():
        sensors[sensor_type] = SensorStateResponse(
            sensor_type=state["sensor_type"],
            status=state["status"],
            loaded_at=state.get("loaded_at"),
            error_message=state.get("error_message"),
            events_captured=state.get("events_captured", 0),
            events_dropped=state.get("events_dropped", 0),
            last_event_at=state.get("last_event_at"),
        )
    
    return SensorListResponse(
        platform=stats["platform"],
        kernel_version=stats["kernel_version"],
        ebpf_available=stats["ebpf_available"],
        sensors=sensors,
    )


@router.post("/sensors/{sensor_type}/start", response_model=SensorActionResponse)
async def start_sensor(sensor_type: str, request: SensorActionRequest = SensorActionRequest()):
    """
    Start a kernel sensor.
    
    Starts the specified sensor type for kernel-level event monitoring.
    Requires appropriate privileges (CAP_BPF, CAP_SYS_ADMIN on Linux).
    
    Args:
        sensor_type: One of: process, file, network, memory, module, syscall
        request: Optional configuration for force starting
    
    Returns:
        Status of the start operation
    """
    try:
        sensor = SensorType(sensor_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sensor type: {sensor_type}. "
                   f"Valid types: {[s.value for s in SensorType]}"
        )
    
    manager = get_kernel_sensor_manager()
    
    # Check current state
    current_state = manager.sensors.get(sensor)
    if current_state and current_state.status == SensorStatus.ACTIVE and not request.force:
        return SensorActionResponse(
            success=True,
            sensor_type=sensor_type,
            status="active",
            message=f"Sensor {sensor_type} is already active",
        )
    
    try:
        success = await manager.start_sensor(sensor)
        
        new_state = manager.sensors.get(sensor)
        
        return SensorActionResponse(
            success=success,
            sensor_type=sensor_type,
            status=new_state.status.value if new_state else "unknown",
            message=f"Sensor {sensor_type} started successfully" if success 
                    else f"Failed to start sensor: {new_state.error_message if new_state else 'Unknown error'}",
        )
        
    except Exception as e:
        logger.error(f"Error starting sensor {sensor_type}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start sensor: {str(e)}"
        )


@router.post("/sensors/{sensor_type}/stop", response_model=SensorActionResponse)
async def stop_sensor(sensor_type: str):
    """
    Stop a kernel sensor.
    
    Stops the specified sensor and releases kernel resources.
    """
    try:
        sensor = SensorType(sensor_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sensor type: {sensor_type}"
        )
    
    manager = get_kernel_sensor_manager()
    
    try:
        await manager.stop_sensor(sensor)
        
        return SensorActionResponse(
            success=True,
            sensor_type=sensor_type,
            status="disabled",
            message=f"Sensor {sensor_type} stopped successfully",
        )
        
    except Exception as e:
        logger.error(f"Error stopping sensor {sensor_type}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop sensor: {str(e)}"
        )


@router.post("/sensors/start-all")
async def start_all_sensors():
    """
    Start all available kernel sensors.
    
    Starts process, file, network, memory, and module sensors.
    Returns the status of each sensor start operation.
    """
    manager = get_kernel_sensor_manager()
    results = {}
    
    for sensor_type in SensorType:
        try:
            success = await manager.start_sensor(sensor_type)
            state = manager.sensors.get(sensor_type)
            results[sensor_type.value] = {
                "success": success,
                "status": state.status.value if state else "unknown",
                "error": state.error_message if state and state.error_message else None,
            }
        except Exception as e:
            results[sensor_type.value] = {
                "success": False,
                "status": "error",
                "error": str(e),
            }
    
    return {
        "message": "Sensor start operation completed",
        "results": results,
    }


@router.post("/sensors/stop-all")
async def stop_all_sensors():
    """Stop all active kernel sensors."""
    manager = get_kernel_sensor_manager()
    await manager.stop_all()
    
    return {
        "message": "All sensors stopped",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/sensors/stats", response_model=SensorStatsResponse)
async def get_sensor_stats():
    """
    Get comprehensive sensor statistics.
    
    Returns:
    - Total events captured
    - Events by type breakdown
    - Events dropped due to buffer overflow
    - Error count
    - Per-sensor statistics
    """
    manager = get_kernel_sensor_manager()
    stats = manager.get_stats()
    
    sensors = {}
    for sensor_type, state in stats.get("sensors", {}).items():
        sensors[sensor_type] = SensorStateResponse(
            sensor_type=state["sensor_type"],
            status=state["status"],
            loaded_at=state.get("loaded_at"),
            error_message=state.get("error_message"),
            events_captured=state.get("events_captured", 0),
            events_dropped=state.get("events_dropped", 0),
            last_event_at=state.get("last_event_at"),
        )
    
    # Calculate uptime
    uptime = None
    if stats.get("start_time"):
        start = datetime.fromisoformat(stats["start_time"])
        uptime = (datetime.now(timezone.utc) - start).total_seconds()
    
    return SensorStatsResponse(
        platform=stats["platform"],
        kernel_version=stats["kernel_version"],
        ebpf_available=stats["ebpf_available"],
        events_total=stats["events_total"],
        events_by_type=dict(stats["events_by_type"]),
        events_dropped=stats["events_dropped"],
        errors=stats["errors"],
        uptime_seconds=uptime,
        sensors=sensors,
    )


@router.get("/events", response_model=EventListResponse)
async def get_events(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Events per page"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    min_risk_score: int = Query(0, ge=0, le=100, description="Minimum risk score"),
    pid: Optional[int] = Query(None, description="Filter by process ID"),
    comm: Optional[str] = Query(None, description="Filter by process name"),
):
    """
    Get recent kernel events.
    
    Supports filtering by:
    - Event type (process_exec, file_open, net_connect, etc.)
    - Minimum risk score
    - Process ID
    - Process name (comm)
    
    Returns paginated results sorted by timestamp (newest first).
    """
    manager = get_kernel_sensor_manager()
    
    # Get events from buffer
    event_type_filter = None
    if event_type:
        try:
            event_type_filter = EventType(event_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event type: {event_type}"
            )
    
    events = manager.get_recent_events(count=page_size * page, event_type=event_type_filter)
    
    # Apply filters
    filtered = []
    for event in events:
        if min_risk_score > 0 and event.risk_score < min_risk_score:
            continue
        if pid and event.pid != pid:
            continue
        if comm and comm.lower() not in event.comm.lower():
            continue
        filtered.append(event)
    
    # Paginate
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_events = filtered[start_idx:end_idx]
    
    # Convert to response format
    event_responses = []
    for event in page_events:
        event_responses.append(KernelEventResponse(
            event_id=event.event_id,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            pid=event.pid,
            ppid=event.ppid,
            uid=event.uid,
            gid=event.gid,
            comm=event.comm,
            container_id=event.container_id,
            namespace_pid=event.namespace_pid,
            data=event.data,
            mitre_techniques=event.mitre_techniques,
            risk_score=event.risk_score,
        ))
    
    return EventListResponse(
        total=len(filtered),
        events=event_responses,
        page=page,
        page_size=page_size,
    )


@router.get("/events/high-risk")
async def get_high_risk_events(
    min_score: int = Query(70, ge=0, le=100),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Get high-risk kernel events.
    
    Returns events with risk score at or above the threshold,
    sorted by risk score descending.
    """
    manager = get_kernel_sensor_manager()
    events = manager.get_recent_events(count=limit * 10)
    
    # Filter and sort by risk
    high_risk = [e for e in events if e.risk_score >= min_score]
    high_risk.sort(key=lambda e: e.risk_score, reverse=True)
    
    return {
        "total": len(high_risk),
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type.value,
                "timestamp": e.timestamp,
                "pid": e.pid,
                "comm": e.comm,
                "mitre_techniques": e.mitre_techniques,
                "risk_score": e.risk_score,
            }
            for e in high_risk[:limit]
        ]
    }


@router.get("/events/mitre/{technique}")
async def get_events_by_mitre(
    technique: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Get events matching a MITRE ATT&CK technique.
    
    Args:
        technique: MITRE technique ID (e.g., T1055, T1059)
    """
    manager = get_kernel_sensor_manager()
    events = manager.get_recent_events(count=limit * 10)
    
    # Normalize technique ID
    technique = technique.upper()
    if not technique.startswith("T"):
        technique = f"T{technique}"
    
    matching = [e for e in events if technique in e.mitre_techniques]
    
    return {
        "technique": technique,
        "total": len(matching),
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type.value,
                "timestamp": e.timestamp,
                "pid": e.pid,
                "comm": e.comm,
                "risk_score": e.risk_score,
            }
            for e in matching[:limit]
        ]
    }


@router.get("/events/{event_id}")
async def get_event_details(event_id: str):
    """
    Get detailed information about a specific event.
    
    Returns the full event data including all fields.
    """
    manager = get_kernel_sensor_manager()
    events = manager.get_recent_events(count=10000)
    
    for event in events:
        if event.event_id == event_id:
            # Return full event details based on type
            if isinstance(event, ProcessEvent):
                return ProcessEventResponse(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    timestamp=event.timestamp,
                    pid=event.pid,
                    ppid=event.ppid,
                    uid=event.uid,
                    gid=event.gid,
                    comm=event.comm,
                    container_id=event.container_id,
                    namespace_pid=event.namespace_pid,
                    data=event.data,
                    mitre_techniques=event.mitre_techniques,
                    risk_score=event.risk_score,
                    filename=event.filename,
                    args=event.args,
                    cwd=event.cwd,
                    exit_code=event.exit_code,
                    cap_effective=event.cap_effective,
                )
            elif isinstance(event, FileEvent):
                return FileEventResponse(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    timestamp=event.timestamp,
                    pid=event.pid,
                    ppid=event.ppid,
                    uid=event.uid,
                    gid=event.gid,
                    comm=event.comm,
                    container_id=event.container_id,
                    namespace_pid=event.namespace_pid,
                    data=event.data,
                    mitre_techniques=event.mitre_techniques,
                    risk_score=event.risk_score,
                    path=event.path,
                    flags=event.flags,
                    mode=event.mode,
                    new_path=event.new_path,
                    inode=event.inode,
                )
            elif isinstance(event, NetworkEvent):
                return NetworkEventResponse(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    timestamp=event.timestamp,
                    pid=event.pid,
                    ppid=event.ppid,
                    uid=event.uid,
                    gid=event.gid,
                    comm=event.comm,
                    container_id=event.container_id,
                    namespace_pid=event.namespace_pid,
                    data=event.data,
                    mitre_techniques=event.mitre_techniques,
                    risk_score=event.risk_score,
                    family=event.family,
                    protocol=event.protocol,
                    local_addr=event.local_addr,
                    local_port=event.local_port,
                    remote_addr=event.remote_addr,
                    remote_port=event.remote_port,
                    direction=event.direction,
                )
            else:
                return KernelEventResponse(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    timestamp=event.timestamp,
                    pid=event.pid,
                    ppid=event.ppid,
                    uid=event.uid,
                    gid=event.gid,
                    comm=event.comm,
                    container_id=event.container_id,
                    namespace_pid=event.namespace_pid,
                    data=event.data,
                    mitre_techniques=event.mitre_techniques,
                    risk_score=event.risk_score,
                )
    
    raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities():
    """
    Get platform capabilities for kernel sensors.
    
    Returns:
    - Platform type (linux, windows, macos)
    - Kernel version
    - eBPF support status
    - Available sensor types
    - Required capabilities/privileges
    - Whether requirements are met
    """
    manager = get_kernel_sensor_manager()
    stats = manager.get_stats()
    
    # Check platform capabilities
    missing = []
    requirements_met = True
    
    if stats["platform"] == "linux":
        required_caps = ["CAP_BPF", "CAP_SYS_ADMIN", "CAP_PERFMON"]
        
        # Check kernel version
        try:
            major, minor = map(int, stats["kernel_version"].split(".")[:2])
            if major < 4 or (major == 4 and minor < 15):
                missing.append("Kernel 4.15+ required for eBPF")
                requirements_met = False
        except ValueError:
            pass
        
        # Check BCC availability
        if not stats["ebpf_available"]:
            missing.append("BCC library not installed (pip install bcc)")
            requirements_met = False
    
    elif stats["platform"] == "windows":
        required_caps = ["Administrator", "SeDebugPrivilege"]
    else:
        required_caps = ["root"]
    
    # Determine BTF support
    btf_support = False
    if stats["platform"] == "linux":
        try:
            major, minor = map(int, stats["kernel_version"].split(".")[:2])
            btf_support = major >= 5 and minor >= 2
        except ValueError:
            pass
    
    return CapabilitiesResponse(
        platform=stats["platform"],
        kernel_version=stats["kernel_version"],
        ebpf_support=stats["ebpf_available"],
        btf_support=btf_support,
        available_sensors=[s.value for s in SensorType],
        required_capabilities=required_caps,
        requirements_met=requirements_met,
        missing_requirements=missing,
    )


# =============================================================================
# WEBSOCKET ENDPOINT FOR REAL-TIME EVENTS
# =============================================================================

# Track active WebSocket connections
active_connections: List[WebSocket] = []


@router.websocket("/events/stream")
async def stream_events(websocket: WebSocket):
    """
    WebSocket endpoint for real-time kernel event streaming.
    
    Connect to receive kernel events as they occur.
    Send JSON filter configuration to customize which events to receive:
    
    {
        "event_types": ["process_exec", "file_write"],
        "min_risk_score": 50,
        "process_names": ["bash", "python"],
        "mitre_techniques": ["T1055", "T1059"]
    }
    """
    await websocket.accept()
    active_connections.append(websocket)
    
    # Default filter
    event_filter = EventFilterRequest()
    
    manager = get_kernel_sensor_manager()
    
    # Track last seen event
    last_event_count = manager.stats["events_total"]
    
    try:
        while True:
            # Check for filter updates (non-blocking)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=0.1
                )
                event_filter = EventFilterRequest(**data)
                await websocket.send_json({
                    "type": "filter_updated",
                    "filter": event_filter.dict()
                })
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass
            
            # Check for new events
            current_count = manager.stats["events_total"]
            if current_count > last_event_count:
                new_events = manager.get_recent_events(count=current_count - last_event_count)
                
                for event in new_events:
                    # Apply filters
                    if event_filter.event_types:
                        if event.event_type.value not in event_filter.event_types:
                            continue
                    
                    if event.risk_score < event_filter.min_risk_score:
                        continue
                    
                    if event_filter.process_names:
                        if not any(n.lower() in event.comm.lower() for n in event_filter.process_names):
                            continue
                    
                    if event_filter.pids:
                        if event.pid not in event_filter.pids:
                            continue
                    
                    if event_filter.mitre_techniques:
                        if not any(t in event.mitre_techniques for t in event_filter.mitre_techniques):
                            continue
                    
                    # Send event
                    await websocket.send_json({
                        "type": "event",
                        "event": {
                            "event_id": event.event_id,
                            "event_type": event.event_type.value,
                            "timestamp": event.timestamp,
                            "pid": event.pid,
                            "ppid": event.ppid,
                            "uid": event.uid,
                            "comm": event.comm,
                            "mitre_techniques": event.mitre_techniques,
                            "risk_score": event.risk_score,
                        }
                    })
                
                last_event_count = current_count
            
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for kernel sensor subsystem.
    
    Returns:
    - Overall health status
    - Individual sensor statuses
    - Event processing rate
    """
    manager = get_kernel_sensor_manager()
    stats = manager.get_stats()
    
    # Determine health
    active_sensors = sum(
        1 for s in stats.get("sensors", {}).values()
        if s["status"] == "active"
    )
    error_sensors = sum(
        1 for s in stats.get("sensors", {}).values()
        if s["status"] == "error"
    )
    
    if error_sensors > 0:
        status = "degraded"
    elif active_sensors == 0:
        status = "inactive"
    else:
        status = "healthy"
    
    return {
        "status": status,
        "platform": stats["platform"],
        "ebpf_available": stats["ebpf_available"],
        "active_sensors": active_sensors,
        "error_sensors": error_sensors,
        "events_total": stats["events_total"],
        "events_dropped": stats["events_dropped"],
        "websocket_clients": len(active_connections),
    }
