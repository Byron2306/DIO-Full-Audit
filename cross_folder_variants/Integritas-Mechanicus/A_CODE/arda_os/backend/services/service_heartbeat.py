import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from services.world_events import emit_world_event
except Exception:
    from backend.services.world_events import emit_world_event

logger = logging.getLogger(__name__)

class ServiceHeartbeat:
    """
    Background service that aggregates telemetry snapshots from across the system.
    Ensures that the entire Port 3000 UI stays 'live' with fresh data even when
    no new security events are occurring.
    """
    
    def __init__(self, db: Any):
        self.db = db
        self.running = False
        self._interval = 10  # Seconds
        
    async def start(self):
        """Start the heartbeat loop"""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting System-Wide Heartbeat Service...")
        asyncio.create_task(self._run_loop())
        
    async def stop(self):
        """Stop the heartbeat loop"""
        self.running = False
        logger.info("Stopping System-Wide Heartbeat Service...")

    async def _run_loop(self):
        while self.running:
            try:
                snapshot = await self._generate_snapshot()
                
                # Emit a world event that will be broadcasted live via the new bridge
                if emit_world_event:
                    await emit_world_event(
                        self.db,
                        event_type="system_telemetry_snapshot",
                        entity_refs=["global"],
                        payload=snapshot,
                        trigger_triune=False, # Don't recompute Triune logic for a heartbeat
                        source="service_heartbeat"
                    )
                
            except Exception as e:
                logger.error(f"Heartbeat snapshot failure: {e}")
            
            await asyncio.sleep(self._interval)

    async def _generate_snapshot(self) -> Dict[str, Any]:
        """Aggregate stats from all major security modules"""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modules": {}
        }
        
        # 1. Deception Stats
        try:
            from deception_engine import deception_engine
            snapshot["modules"]["deception"] = {
                "active_campaigns": len(deception_engine.campaigns),
                "total_events": len(deception_engine.events),
                "blocklist_count": len(deception_engine.blocklist),
                "last_incident": deception_engine.events[-1]["timestamp"] if deception_engine.events else None
            }
        except Exception:
            snapshot["modules"]["deception"] = {"status": "error"}

        # 2. EDR / Quarantine Stats
        try:
            from edr_service import edr_manager
            snapshot["modules"]["edr"] = {
                "active_threats": await self.db.threats.count_documents({"status": "active"}),
                "quarantined_files": await self.db.quarantine.count_documents({}),
                "agents_online": await self.db.agents.count_documents({"status": "online"})
            }
        except Exception:
            snapshot["modules"]["edr"] = {"status": "error"}

        # 3. Sandbox Stats
        try:
            # Check for both pending and completed analyses in the last 24h
            snapshot["modules"]["sandbox"] = {
                "pending": await self.db.sandbox_tasks.count_documents({"status": "pending"}),
                "completed_24h": await self.db.sandbox_tasks.count_documents({
                    "status": "completed",
                    "completed_at": {"$gt": (datetime.now(timezone.utc).timestamp() - 86400)}
                })
            }
        except Exception:
            snapshot["modules"]["sandbox"] = {"status": "error"}

        # 4. SOAR Stats
        try:
            snapshot["modules"]["soar"] = {
                "active_playbooks": await self.db.playbook_executions.count_documents({"status": "running"}),
                "successful_mitigations": await self.db.playbook_executions.count_documents({"status": "completed"})
            }
        except Exception:
            snapshot["modules"]["soar"] = {"status": "error"}

        # 5. Triune Governance Stats
        try:
            snapshot["modules"]["triune"] = {
                "queued_actions": await self.db.triune_outbound_queue.count_documents({"status": "gated_pending_approval"}),
                "decisions_today": await self.db.triune_decisions.count_documents({
                    "created_at": {"$gt": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()}
                })
            }
        except Exception:
            snapshot["modules"]["triune"] = {"status": "error"}

        # 6. Enterprise: Ransomware Stats
        try:
            from ransomware_protection import ransomware_protection
            snapshot["modules"]["ransomware"] = {
                "canary_health": ransomware_protection.canary_manager.get_status(),
                "protected_folders": len(ransomware_protection.folder_manager.protected_folders),
                "blocked_attempts": ransomware_protection.folder_manager.blocked_attempts
            }
        except Exception:
            snapshot["modules"]["ransomware"] = {"status": "error"}

        # 7. Enterprise: VPN & Tunnels
        try:
            from vpn_integration import vpn_manager
            snapshot["modules"]["vpn"] = {
                "active_tunnels": len(getattr(vpn_manager.server, 'peers', [])),
                "status": "operational" if vpn_manager.is_healthy() else "degraded"
            }
        except Exception:
            snapshot["modules"]["vpn"] = {"status": "error"}

        # 8. Enterprise: Container Security
        try:
            from container_security import container_security
            snapshot["modules"]["containers"] = {
                "total_scans": await self.db.container_scans.count_documents({}),
                "falco_active": container_security.falco is not None
            }
        except Exception:
            snapshot["modules"]["containers"] = {"status": "error"}

        # 9. ARDA OS & Fabric
        try:
            snapshot["modules"]["arda"] = {
                "tpm_lawful": (await self.db.attestation_reports.find_one(sort=[("timestamp", -1)])) or {},
                "fabric_nodes": await self.db.agents.count_documents({"tags": "arda_fabric"})
            }
        except Exception:
            snapshot["modules"]["arda"] = {"status": "error"}

        return snapshot

# Global instance manager
_heartbeat_instance = None

def start_heartbeat(db):
    global _heartbeat_instance
    if _heartbeat_instance is None:
        _heartbeat_instance = ServiceHeartbeat(db)
        asyncio.create_task(_heartbeat_instance.start())
    return _heartbeat_instance
