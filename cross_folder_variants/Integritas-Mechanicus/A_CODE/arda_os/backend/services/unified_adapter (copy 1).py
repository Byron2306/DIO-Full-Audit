"""
Unified Sovereign Adapter
=========================
Bridge between ARDA OS's Sophic Reasoning and the Seraph Unified Agent.

Now that ARDA and Seraph are merged, this imports directly from the shared
package rather than injecting a hardcoded path into sys.path.

The merged system lives at:
  /home/byron/Downloads/Metatron-triune-outbound-gate/
"""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("arda.unified_adapter")

try:
    from unified_agent.core.agent import UnifiedAgent, AgentConfig, ThreatSeverity, Threat
    _AGENT_AVAILABLE = True
except ImportError as e:
    logger.error(f"Seraph UnifiedAgent not importable: {e}")
    _AGENT_AVAILABLE = False


class UnifiedSovereignAdapter:
    """
    Bridge between Sophia's Sophic Reasoning and the Seraph Unified Agent.
    Implements the 'Brawn' of the Sovereign Presence.
    """

    def __init__(self, server_url: str = "http://localhost:8001"):
        if not _AGENT_AVAILABLE:
            logger.warning("UnifiedAgent unavailable — adapter running in no-op mode")
            self._agent = None
            return

        self.config = AgentConfig(
            server_url=server_url,
            agent_name="Sophia-Sovereign-Fortress",
            auto_remediate=True,
            endpoint_fortress_enabled=True,
            triune_rank_before_handle=True,
            triune_preflight_gate=True,
            triune_hypothesis_enabled=True,
        )
        self._agent = UnifiedAgent(config=self.config)
        logger.info("Unified Sovereign Adapter initialized (server=%s)", server_url)

    def start_fortress(self):
        if self._agent:
            self._agent.start(blocking=False)
            logger.info("Sovereign Fortress monitoring active.")

    def stop_fortress(self):
        if self._agent:
            self._agent.stop()

    def get_fortress_status(self) -> Dict[str, Any]:
        if not self._agent:
            return {"available": False}
        return self._agent.get_status()

    def trigger_scan(self) -> Dict[str, Any]:
        if not self._agent:
            return {"available": False}
        return self._agent.scan_all()

    def check_is_trusted(
        self,
        process_name: str,
        path: Optional[str] = None,
        cmdline: Optional[str] = None,
    ) -> bool:
        if not self._agent:
            return True  # fail-open when agent unavailable
        try:
            result = self._agent.triune_gate.preflight(
                process_name=process_name,
                path=path,
                cmdline=cmdline,
            )
            return result.get("allowed", True)
        except Exception:
            return True

    def discover_lan_devices(self) -> List[Dict[str, Any]]:
        if not self._agent:
            return []
        try:
            return self._agent.discover_lan_devices(report=False)
        except Exception:
            return []
