"""
Real-Time WebSocket Service
===========================
Enhanced WebSocket service for real-time communication between
the local agent and the cloud dashboard.

Features:
- Bidirectional communication
- Event streaming from agents
- Real-time alerts and notifications
- Command dispatch to agents
- Connection management and heartbeats
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)

# =============================================================================
# ENUMS AND DATA MODELS
# =============================================================================

class WSMessageType(Enum):
    # Agent -> Server
    AGENT_CONNECT = "agent_connect"
    AGENT_HEARTBEAT = "agent_heartbeat"
    AGENT_EVENT = "agent_event"
    AGENT_ALERT = "agent_alert"
    AGENT_THREAT = "agent_threat"
    AGENT_SCAN_RESULT = "agent_scan_result"
    AGENT_STATUS = "agent_status"
    
    # Server -> Agent
    COMMAND = "command"
    CONFIG_UPDATE = "config_update"
    SCAN_REQUEST = "scan_request"
    BLOCK_IP = "block_ip"
    QUARANTINE_FILE = "quarantine_file"
    
    # Server -> Dashboard
    NEW_THREAT = "new_threat"
    NEW_ALERT = "new_alert"
    THREAT_UPDATE = "threat_update"
    AGENT_UPDATE = "agent_update"
    STATS_UPDATE = "stats_update"
    NOTIFICATION = "notification"

@dataclass
class WSMessage:
    """WebSocket message structure"""
    type: str
    payload: Dict[str, Any]
    source: str  # agent_id or "server" or "dashboard"
    target: Optional[str] = None  # specific agent_id or "all" or "dashboard"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:12])

@dataclass
class AgentConnection:
    """Represents a connected agent"""
    agent_id: str
    agent_name: str
    websocket: Any
    connected_at: str
    last_heartbeat: str
    ip_address: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    status: str = "connected"

# =============================================================================
# WEBSOCKET MANAGER
# =============================================================================

class RealTimeWSManager:
    """
    Enhanced WebSocket connection manager supporting:
    - Multiple agent connections
    - Dashboard connections
    - Bidirectional communication
    - Message routing
    - Event handlers
    """
    
    def __init__(self):
        # Dashboard connections (authenticated users viewing the dashboard)
        self.dashboard_connections: Set[Any] = set()
        
        # Agent connections (local agents reporting data)
        self.agent_connections: Dict[str, AgentConnection] = {}
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Message queue for offline agents
        self._pending_messages: Dict[str, List[WSMessage]] = {}
        
        # Stats
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "agents_connected": 0,
            "dashboards_connected": 0
        }
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    async def connect_dashboard(self, websocket):
        """Connect a dashboard client"""
        self.dashboard_connections.add(websocket)
        self.stats["dashboards_connected"] = len(self.dashboard_connections)
        logger.info(f"Dashboard connected. Total: {len(self.dashboard_connections)}")
        
        # Send initial state
        await self._send_to_websocket(websocket, WSMessage(
            type="connected",
            payload={
                "message": "Connected to real-time updates",
                "agents_online": len(self.agent_connections),
                "agent_ids": list(self.agent_connections.keys())
            },
            source="server"
        ))
    
    async def disconnect_dashboard(self, websocket):
        """Disconnect a dashboard client"""
        self.dashboard_connections.discard(websocket)
        self.stats["dashboards_connected"] = len(self.dashboard_connections)
        logger.info(f"Dashboard disconnected. Total: {len(self.dashboard_connections)}")
    
    async def connect_agent(
        self,
        websocket,
        agent_id: str,
        agent_name: str,
        ip_address: Optional[str] = None,
        capabilities: Optional[List[str]] = None
    ):
        """Connect a local agent"""
        connection = AgentConnection(
            agent_id=agent_id,
            agent_name=agent_name,
            websocket=websocket,
            connected_at=datetime.now(timezone.utc).isoformat(),
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
            ip_address=ip_address,
            capabilities=capabilities or [],
            status="connected"
        )
        
        self.agent_connections[agent_id] = connection
        self.stats["agents_connected"] = len(self.agent_connections)
        
        logger.info(f"Agent connected: {agent_name} ({agent_id})")
        
        # Notify dashboards
        await self.broadcast_to_dashboards(WSMessage(
            type=WSMessageType.AGENT_UPDATE.value,
            payload={
                "event": "agent_connected",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "ip_address": ip_address,
                "capabilities": capabilities
            },
            source="server"
        ))
        
        # Send any pending messages
        if agent_id in self._pending_messages:
            for msg in self._pending_messages[agent_id]:
                await self._send_to_websocket(websocket, msg)
            del self._pending_messages[agent_id]
        
        # Trigger event handlers
        await self._trigger_handlers("agent_connected", connection)
    
    async def disconnect_agent(self, agent_id: str):
        """Disconnect an agent"""
        if agent_id in self.agent_connections:
            agent = self.agent_connections[agent_id]
            del self.agent_connections[agent_id]
            self.stats["agents_connected"] = len(self.agent_connections)
            
            logger.info(f"Agent disconnected: {agent.agent_name} ({agent_id})")
            
            # Notify dashboards
            await self.broadcast_to_dashboards(WSMessage(
                type=WSMessageType.AGENT_UPDATE.value,
                payload={
                    "event": "agent_disconnected",
                    "agent_id": agent_id,
                    "agent_name": agent.agent_name
                },
                source="server"
            ))
            
            # Trigger event handlers
            await self._trigger_handlers("agent_disconnected", agent)
    
    async def update_agent_heartbeat(self, agent_id: str):
        """Update agent's last heartbeat time"""
        if agent_id in self.agent_connections:
            self.agent_connections[agent_id].last_heartbeat = datetime.now(timezone.utc).isoformat()
    
    # =========================================================================
    # MESSAGE SENDING
    # =========================================================================
    
    async def _send_to_websocket(self, websocket, message: WSMessage) -> bool:
        """Send a message to a specific websocket"""
        try:
            await websocket.send_json(asdict(message))
            self.stats["messages_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            return False
    
    async def broadcast_to_dashboards(self, message: WSMessage):
        """Broadcast a message to all connected dashboards"""
        disconnected = set()
        for ws in self.dashboard_connections:
            try:
                await ws.send_json(asdict(message))
                self.stats["messages_sent"] += 1
            except Exception:
                disconnected.add(ws)
        
        # Clean up disconnected
        for ws in disconnected:
            self.dashboard_connections.discard(ws)
        self.stats["dashboards_connected"] = len(self.dashboard_connections)
    
    async def send_to_agent(self, agent_id: str, message: WSMessage) -> bool:
        """Send a message to a specific agent"""
        if agent_id in self.agent_connections:
            return await self._send_to_websocket(
                self.agent_connections[agent_id].websocket,
                message
            )
        else:
            # Queue for when agent reconnects
            if agent_id not in self._pending_messages:
                self._pending_messages[agent_id] = []
            self._pending_messages[agent_id].append(message)
            logger.warning(f"Agent {agent_id} not connected. Message queued.")
            return False
    
    async def broadcast_to_agents(self, message: WSMessage):
        """Broadcast a message to all connected agents"""
        for agent_id, connection in list(self.agent_connections.items()):
            try:
                await connection.websocket.send_json(asdict(message))
                self.stats["messages_sent"] += 1
            except Exception:
                await self.disconnect_agent(agent_id)
    
    async def broadcast(self, data: Dict[str, Any]):
        """Legacy broadcast method - sends to all dashboards"""
        message = WSMessage(
            type=data.get("type", "update"),
            payload=data,
            source="server"
        )
        await self.broadcast_to_dashboards(message)
    
    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================
    
    async def handle_agent_message(self, agent_id: str, data: Dict[str, Any]):
        """Handle incoming message from an agent"""
        self.stats["messages_received"] += 1
        
        msg_type = data.get("type", "unknown")
        payload = data.get("payload", data)
        
        # Update heartbeat
        await self.update_agent_heartbeat(agent_id)
        
        # Create structured message
        message = WSMessage(
            type=msg_type,
            payload=payload,
            source=agent_id
        )
        
        # Handle based on message type
        if msg_type == WSMessageType.AGENT_HEARTBEAT.value:
            await self._handle_heartbeat(agent_id, payload)
        
        elif msg_type == WSMessageType.AGENT_ALERT.value:
            await self._handle_agent_alert(agent_id, payload)
        
        elif msg_type == WSMessageType.AGENT_THREAT.value:
            await self._handle_agent_threat(agent_id, payload)
        
        elif msg_type == WSMessageType.AGENT_SCAN_RESULT.value:
            await self._handle_scan_result(agent_id, payload)
        
        elif msg_type == WSMessageType.AGENT_STATUS.value:
            await self._handle_agent_status(agent_id, payload)
        
        # Forward to dashboards
        await self.broadcast_to_dashboards(message)
        
        # Trigger event handlers
        await self._trigger_handlers(msg_type, message)
    
    async def _handle_heartbeat(self, agent_id: str, payload: Dict):
        """Handle agent heartbeat"""
        if agent_id in self.agent_connections:
            self.agent_connections[agent_id].last_heartbeat = datetime.now(timezone.utc).isoformat()
            
            # Broadcast status update to dashboards
            await self.broadcast_to_dashboards(WSMessage(
                type=WSMessageType.AGENT_UPDATE.value,
                payload={
                    "event": "heartbeat",
                    "agent_id": agent_id,
                    "system_info": payload.get("system_info", {}),
                    "stats": payload.get("stats", {})
                },
                source=agent_id
            ))
    
    async def _handle_agent_alert(self, agent_id: str, payload: Dict):
        """Handle alert from agent"""
        await self.broadcast_to_dashboards(WSMessage(
            type=WSMessageType.NEW_ALERT.value,
            payload={
                "agent_id": agent_id,
                "alert": payload
            },
            source=agent_id
        ))
    
    async def _handle_agent_threat(self, agent_id: str, payload: Dict):
        """Handle threat detection from agent"""
        await self.broadcast_to_dashboards(WSMessage(
            type=WSMessageType.NEW_THREAT.value,
            payload={
                "agent_id": agent_id,
                "threat": payload
            },
            source=agent_id
        ))
    
    async def _handle_scan_result(self, agent_id: str, payload: Dict):
        """Handle scan results from agent"""
        await self.broadcast_to_dashboards(WSMessage(
            type="scan_complete",
            payload={
                "agent_id": agent_id,
                "scan_type": payload.get("scan_type"),
                "results": payload.get("results", {})
            },
            source=agent_id
        ))
    
    async def _handle_agent_status(self, agent_id: str, payload: Dict):
        """Handle status update from agent"""
        if agent_id in self.agent_connections:
            self.agent_connections[agent_id].status = payload.get("status", "connected")
    
    # =========================================================================
    # COMMANDS TO AGENTS
    # =========================================================================
    
    async def send_command(
        self,
        agent_id: str,
        command: str,
        parameters: Optional[Dict] = None
    ) -> bool:
        """Send a command to an agent"""
        message = WSMessage(
            type=WSMessageType.COMMAND.value,
            payload={
                "command": command,
                "parameters": parameters or {}
            },
            source="server",
            target=agent_id
        )
        return await self.send_to_agent(agent_id, message)
    
    async def request_scan(
        self,
        agent_id: str,
        scan_type: str,
        target: Optional[str] = None
    ) -> bool:
        """Request a scan from an agent"""
        message = WSMessage(
            type=WSMessageType.SCAN_REQUEST.value,
            payload={
                "scan_type": scan_type,  # network, yara, clamav, process
                "target": target
            },
            source="server",
            target=agent_id
        )
        return await self.send_to_agent(agent_id, message)
    
    async def send_block_ip_command(self, agent_id: str, ip: str, reason: str) -> bool:
        """Send IP block command to agent"""
        message = WSMessage(
            type=WSMessageType.BLOCK_IP.value,
            payload={
                "ip": ip,
                "reason": reason
            },
            source="server",
            target=agent_id
        )
        return await self.send_to_agent(agent_id, message)
    
    async def send_quarantine_command(
        self,
        agent_id: str,
        filepath: str,
        threat_name: str
    ) -> bool:
        """Send quarantine command to agent"""
        message = WSMessage(
            type=WSMessageType.QUARANTINE_FILE.value,
            payload={
                "filepath": filepath,
                "threat_name": threat_name
            },
            source="server",
            target=agent_id
        )
        return await self.send_to_agent(agent_id, message)
    
    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    
    def on(self, event_type: str, handler: Callable):
        """Register an event handler"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def _trigger_handlers(self, event_type: str, data: Any):
        """Trigger all handlers for an event type"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error for {event_type}: {e}")
    
    # =========================================================================
    # STATUS AND INFO
    # =========================================================================
    
    def get_connected_agents(self) -> List[Dict[str, Any]]:
        """Get list of connected agents"""
        return [
            {
                "agent_id": conn.agent_id,
                "agent_name": conn.agent_name,
                "ip_address": conn.ip_address,
                "connected_at": conn.connected_at,
                "last_heartbeat": conn.last_heartbeat,
                "status": conn.status,
                "capabilities": conn.capabilities
            }
            for conn in self.agent_connections.values()
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket statistics"""
        return {
            **self.stats,
            "pending_messages": sum(len(msgs) for msgs in self._pending_messages.values()),
            "agents": self.get_connected_agents()
        }

# Global instance
realtime_ws = RealTimeWSManager()
