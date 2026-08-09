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
import os
import sys
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("arda.unified_adapter")


def _candidate_unified_agent_roots() -> list[Path]:
    env_root = os.environ.get("ARDA_UNIFIED_AGENT_ROOT")
    candidates = []
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend(
        [
            Path("/home/byron/Downloads/Metatron-triune-outbound-gate"),
            Path.home() / "Downloads" / "Metatron-triune-outbound-gate",
        ]
    )
    return candidates


for candidate in _candidate_unified_agent_roots():
    if (candidate / "unified_agent" / "core" / "agent.py").exists():
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
        break

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

        desired_config = {
            "server_url": server_url,
            "agent_name": "Sophia-Sovereign-Fortress",
            "auto_remediate": True,
            "endpoint_fortress_enabled": True,
            "triune_rank_before_handle": True,
            "triune_preflight_gate": True,
            "triune_hypothesis_enabled": True,
        }
        accepted = set(inspect.signature(AgentConfig).parameters)
        compatible_config = {key: value for key, value in desired_config.items() if key in accepted}
        self.config = AgentConfig(**compatible_config)
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

    def remediate(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if not self._agent:
            logger.warning("UnifiedAgent unavailable — remediation recorded in no-op mode: %s", action)
            return {"available": False, "executed": False, "mode": "noop", "action": action}
        try:
            remediation_action = action.get("remediation_action")
            remediation_params = action.get("remediation_params") or {}
            if hasattr(self._agent, "remediate"):
                result = self._agent.remediate(remediation_action, **remediation_params)
            else:
                result = {
                    "available": True,
                    "executed": False,
                    "mode": "compatibility_fallback",
                    "action": action,
                }
            return result if isinstance(result, dict) else {"available": True, "executed": True, "result": result}
        except Exception as exc:
            logger.exception("Unified remediation failed: %s", exc)
            return {"available": True, "executed": False, "error": str(exc), "action": action}

    def get_recent_anomalies(self) -> List[Dict[str, Any]]:
        if not self._agent:
            return []
        try:
            if hasattr(self._agent, "get_recent_anomalies"):
                anomalies = self._agent.get_recent_anomalies()
                return anomalies if isinstance(anomalies, list) else []
        except Exception:
            logger.exception("Unified anomaly fetch failed")
        return []


_ADAPTER_SINGLETON: Optional[UnifiedSovereignAdapter] = None


def get_unified_adapter(server_url: str = "http://localhost:8001") -> UnifiedSovereignAdapter:
    global _ADAPTER_SINGLETON
    if _ADAPTER_SINGLETON is None:
        _ADAPTER_SINGLETON = UnifiedSovereignAdapter(server_url=server_url)
    return _ADAPTER_SINGLETON
