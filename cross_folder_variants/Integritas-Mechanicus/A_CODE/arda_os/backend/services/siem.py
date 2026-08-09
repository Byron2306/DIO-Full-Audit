"""
SIEM Integration Service
========================
Sends security events to Elasticsearch, Splunk, or Syslog.
"""

import os
import json
import socket
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from collections import deque
import threading
import time

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class SIEMService:
    """Enterprise SIEM integration for server-side event logging"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Configuration from environment
        self.elasticsearch_url = os.environ.get('ELASTICSEARCH_URL', '')
        self.elasticsearch_index = os.environ.get('SIEM_INDEX', 'seraph-security')
        self.elasticsearch_api_key = os.environ.get('ELASTICSEARCH_API_KEY', '')
        
        self.splunk_hec_url = os.environ.get('SPLUNK_HEC_URL', '')
        self.splunk_hec_token = os.environ.get('SPLUNK_HEC_TOKEN', '')
        
        self.syslog_server = os.environ.get('SYSLOG_SERVER', '')
        self.syslog_port = int(os.environ.get('SYSLOG_PORT', '514'))
        
        # Determine SIEM type
        self.enabled = False
        self.siem_type = None
        
        if self.elasticsearch_url:
            self.enabled = True
            self.siem_type = 'elasticsearch'
            logger.info(f"SIEM: Elasticsearch enabled at {self.elasticsearch_url}")
        elif self.splunk_hec_url:
            self.enabled = True
            self.siem_type = 'splunk'
            logger.info(f"SIEM: Splunk HEC enabled at {self.splunk_hec_url}")
        elif self.syslog_server:
            self.enabled = True
            self.siem_type = 'syslog'
            logger.info(f"SIEM: Syslog enabled at {self.syslog_server}:{self.syslog_port}")
        else:
            logger.info("SIEM: Not configured (set ELASTICSEARCH_URL, SPLUNK_HEC_URL, or SYSLOG_SERVER)")
        
        # Event buffer for batch sending
        self.buffer = deque(maxlen=10000)
        self.buffer_lock = threading.Lock()
        self.flush_interval = 5  # seconds
        
        # Start background flush thread
        if self.enabled:
            self._start_flush_thread()
    
    def _start_flush_thread(self):
        """Start background thread to flush buffer"""
        def flush_loop():
            while True:
                time.sleep(self.flush_interval)
                self._flush_buffer()
        
        thread = threading.Thread(target=flush_loop, daemon=True)
        thread.start()
    
    def log_event(self, event_type: str, severity: str, data: Dict[str, Any], 
                  agent_id: Optional[str] = None, hostname: Optional[str] = None,
                  immediate: bool = False):
        """
        Log a security event to SIEM.
        
        Args:
            event_type: Type of event (e.g., 'threat.detected', 'auto_kill.executed')
            severity: Event severity (critical, high, medium, low, info)
            data: Event data dictionary
            agent_id: Optional agent ID
            hostname: Optional hostname
            immediate: If True, send immediately (for critical events)
        """
        event = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "agent_id": agent_id,
            "hostname": hostname,
            "data": data,
            "source": "seraph_server"
        }
        
        if not self.enabled:
            # Still log locally even if SIEM not configured
            log_level = {
                'critical': logging.CRITICAL,
                'high': logging.ERROR,
                'medium': logging.WARNING,
                'low': logging.INFO,
                'info': logging.DEBUG
            }.get(severity, logging.INFO)
            logger.log(log_level, f"SIEM Event: {event_type} - {data}")
            return
        
        if immediate or severity in ['critical', 'high']:
            # Send immediately for high-priority events
            self._send_event(event)
        else:
            # Buffer for batch sending
            with self.buffer_lock:
                self.buffer.append(event)
    
    def log_threat(self, threat_data: Dict[str, Any], action: str = "detected"):
        """Log a threat detection/remediation event"""
        self.log_event(
            event_type=f"threat.{action}",
            severity=threat_data.get('severity', 'medium'),
            data=threat_data,
            agent_id=threat_data.get('agent_id'),
            hostname=threat_data.get('hostname'),
            immediate=threat_data.get('severity') in ['critical', 'high']
        )
    
    def log_auto_kill(self, agent_id: str, threat_id: str, threat_title: str, 
                      success: bool, details: str):
        """Log an auto-kill action"""
        self.log_event(
            event_type="auto_kill.executed",
            severity="critical",
            data={
                "threat_id": threat_id,
                "threat_title": threat_title,
                "success": success,
                "details": details
            },
            agent_id=agent_id,
            immediate=True
        )
    
    def log_agent_event(self, agent_id: str, event_type: str, data: Dict[str, Any]):
        """Log an agent-related event"""
        self.log_event(
            event_type=f"agent.{event_type}",
            severity="info",
            data=data,
            agent_id=agent_id,
            immediate=False
        )
    
    def _send_event(self, event: Dict[str, Any]):
        """Send event to configured SIEM"""
        try:
            if self.siem_type == 'elasticsearch':
                self._send_to_elasticsearch(event)
            elif self.siem_type == 'splunk':
                self._send_to_splunk(event)
            elif self.siem_type == 'syslog':
                self._send_to_syslog(event)
        except Exception as e:
            logger.warning(f"SIEM send error: {e}")
    
    def _send_to_elasticsearch(self, event: Dict[str, Any]):
        """Send to Elasticsearch"""
        if not HAS_HTTPX:
            logger.warning("httpx not installed, cannot send to Elasticsearch")
            return
        
        url = f"{self.elasticsearch_url}/{self.elasticsearch_index}/_doc"
        headers = {'Content-Type': 'application/json'}
        
        if self.elasticsearch_api_key:
            headers['Authorization'] = f'ApiKey {self.elasticsearch_api_key}'
        
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=event, headers=headers)
            response.raise_for_status()
    
    def _send_to_splunk(self, event: Dict[str, Any]):
        """Send to Splunk HEC"""
        if not HAS_HTTPX:
            logger.warning("httpx not installed, cannot send to Splunk")
            return
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Splunk {self.splunk_hec_token}'
        }
        
        with httpx.Client(timeout=5.0, verify=False) as client:
            response = client.post(
                self.splunk_hec_url, 
                json={"event": event},
                headers=headers
            )
            response.raise_for_status()
    
    def _send_to_syslog(self, event: Dict[str, Any]):
        """Send to Syslog server"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Format as CEF (Common Event Format)
            severity_map = {'critical': 10, 'high': 7, 'medium': 5, 'low': 3, 'info': 1}
            sev = severity_map.get(event.get('severity', 'info'), 1)
            
            title = event.get('data', {}).get('title', event.get('event_type', 'Security Event'))
            agent = event.get('agent_id', 'server')
            
            msg = f"CEF:0|Seraph|Server|1.0|{event['event_type']}|{title}|{sev}|src={agent}"
            sock.sendto(msg.encode(), (self.syslog_server, self.syslog_port))
        finally:
            sock.close()
    
    def _flush_buffer(self):
        """Flush buffered events to SIEM"""
        if not self.enabled:
            return
        
        events_to_send = []
        with self.buffer_lock:
            while self.buffer:
                events_to_send.append(self.buffer.popleft())
        
        for event in events_to_send:
            self._send_event(event)
    
    def get_status(self) -> Dict[str, Any]:
        """Get SIEM integration status"""
        return {
            "enabled": self.enabled,
            "type": self.siem_type,
            "elasticsearch_url": self.elasticsearch_url if self.siem_type == 'elasticsearch' else None,
            "splunk_configured": bool(self.splunk_hec_url) if self.siem_type == 'splunk' else None,
            "syslog_server": f"{self.syslog_server}:{self.syslog_port}" if self.siem_type == 'syslog' else None,
            "buffer_size": len(self.buffer),
            "flush_interval": self.flush_interval
        }


# Global singleton instance
siem_service = SIEMService()
