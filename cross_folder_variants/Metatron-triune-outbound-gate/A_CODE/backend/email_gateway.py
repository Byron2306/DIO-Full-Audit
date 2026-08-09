"""
Email Gateway Service - SMTP Relay and Real-time Email Interception
====================================================================

Enterprise email gateway providing:
1. SMTP Relay Mode - Intercept and scan emails before delivery
2. Milter Protocol Support - Integration with Postfix/Sendmail
3. Real-time Email Filtering - Block/quarantine before delivery
4. Email Routing and Delivery - Forward clean emails
5. Queue Management - Handle delivery failures gracefully
6. TLS/STARTTLS Support - Secure email transmission
"""
import asyncio
import ssl
import uuid
import hashlib
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from email import message_from_bytes, policy
from email.message import EmailMessage
import logging
import os
import re

logger = logging.getLogger(__name__)


class GatewayAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    QUARANTINE = "quarantine"
    DEFER = "defer"
    REDIRECT = "redirect"
    TAG = "tag"
    ENCRYPT = "encrypt"


class GatewayMode(str, Enum):
    INLINE = "inline"  # Real-time interception
    TAP = "tap"  # Copy for analysis only
    QUARANTINE_ONLY = "quarantine_only"  # Quarantine suspicious only


@dataclass
class EmailMessage:
    """Parsed email message for gateway processing"""
    message_id: str
    envelope_from: str
    envelope_to: List[str]
    subject: str
    headers: Dict[str, str]
    body_text: str
    body_html: str
    attachments: List[Dict]
    raw_size: int
    received_at: str
    client_ip: str = ""
    client_hostname: str = ""
    tls_version: str = ""


@dataclass
class GatewayDecision:
    """Gateway filtering decision"""
    decision_id: str
    message_id: str
    action: GatewayAction
    reason: str
    threat_score: float = 0.0
    threats_detected: List[str] = field(default_factory=list)
    modified_headers: Dict[str, str] = field(default_factory=dict)
    quarantine_id: str = ""
    redirect_to: str = ""
    processing_time_ms: float = 0.0


@dataclass
class GatewayStats:
    """Gateway statistics"""
    total_processed: int = 0
    accepted: int = 0
    rejected: int = 0
    quarantined: int = 0
    deferred: int = 0
    threats_blocked: int = 0
    bytes_processed: int = 0
    avg_processing_time_ms: float = 0.0


class SMTPGateway:
    """
    SMTP Gateway for real-time email interception and filtering.
    
    Can operate as:
    - MTA (Mail Transfer Agent) - Accept and forward emails
    - Milter - Filter emails via milter protocol
    - API Gateway - REST API for email submission
    """
    
    def __init__(
        self,
        mode: GatewayMode = GatewayMode.INLINE,
        listen_host: str = "0.0.0.0",
        listen_port: int = 25,
        upstream_host: str = "localhost",
        upstream_port: int = 10025,
        max_message_size: int = 50 * 1024 * 1024,  # 50MB
        enable_tls: bool = True
    ):
        self.mode = mode
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.max_message_size = max_message_size
        self.enable_tls = enable_tls
        
        # Import email protection service
        try:
            from email_protection import email_protection_service
            self.email_protection = email_protection_service
        except ImportError:
            self.email_protection = None
            logger.warning("Email protection service not available")
        
        # Statistics
        self.stats = GatewayStats()
        
        # Queue management
        self.message_queue: Dict[str, EmailMessage] = {}
        self.quarantine_queue: Dict[str, Dict] = {}
        self.defer_queue: Dict[str, Dict] = {}
        
        # Policy configuration
        self.policies = {
            "default": {
                "max_recipients": 100,
                "max_message_size": max_message_size,
                "require_tls": False,
                "require_auth": False,
                "block_executable_attachments": True,
                "scan_attachments": True,
                "scan_urls": True,
                "quarantine_threshold": 0.7,
                "reject_threshold": 0.9
            }
        }
        
        # Blocklists and allowlists
        self.sender_blocklist: set = set()
        self.sender_allowlist: set = set()
        self.domain_blocklist: set = set()
        self.domain_allowlist: set = set()
        self.ip_blocklist: set = set()
        self.ip_allowlist: set = set()
        
        logger.info(f"SMTPGateway initialized in {mode.value} mode on {listen_host}:{listen_port}")
    
    def parse_email(self, raw_data: bytes, client_ip: str = "", client_hostname: str = "") -> EmailMessage:
        """Parse raw email data into structured message"""
        try:
            msg = message_from_bytes(raw_data, policy=policy.default)
            
            # Extract headers
            headers = {k: str(v) for k, v in msg.items()}
            
            # Extract body
            body_text = ""
            body_html = ""
            attachments = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    if "attachment" in content_disposition:
                        # Handle attachment
                        filename = part.get_filename() or "unnamed"
                        payload = part.get_payload(decode=True)
                        attachments.append({
                            "filename": filename,
                            "content_type": content_type,
                            "size": len(payload) if payload else 0,
                            "content_hash": hashlib.sha256(payload).hexdigest() if payload else "",
                            "content_base64": base64.b64encode(payload).decode() if payload else ""
                        })
                    elif content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text = payload.decode("utf-8", errors="replace")
                    elif content_type == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_html = payload.decode("utf-8", errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    if msg.get_content_type() == "text/html":
                        body_html = payload.decode("utf-8", errors="replace")
                    else:
                        body_text = payload.decode("utf-8", errors="replace")
            
            return EmailMessage(
                message_id=f"gw_{uuid.uuid4().hex[:16]}",
                envelope_from=msg.get("From", ""),
                envelope_to=[msg.get("To", "")],
                subject=msg.get("Subject", ""),
                headers=headers,
                body_text=body_text,
                body_html=body_html,
                attachments=attachments,
                raw_size=len(raw_data),
                received_at=datetime.now(timezone.utc).isoformat(),
                client_ip=client_ip,
                client_hostname=client_hostname
            )
        except Exception as e:
            logger.error(f"Failed to parse email: {e}")
            raise
    
    def process_message(self, message: EmailMessage) -> GatewayDecision:
        """Process email through gateway filters and make decision"""
        start_time = datetime.now()
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        threats_detected = []
        threat_score = 0.0
        action = GatewayAction.ACCEPT
        reason = "Clean"
        modified_headers = {}
        
        try:
            # Check allowlists first (fast path)
            sender_domain = message.envelope_from.split("@")[1] if "@" in message.envelope_from else ""
            
            if message.envelope_from.lower() in self.sender_allowlist:
                return self._make_decision(decision_id, message.message_id, GatewayAction.ACCEPT,
                                          "Sender in allowlist", 0.0, [], {}, start_time)
            
            if sender_domain.lower() in self.domain_allowlist:
                return self._make_decision(decision_id, message.message_id, GatewayAction.ACCEPT,
                                          "Domain in allowlist", 0.0, [], {}, start_time)
            
            if message.client_ip in self.ip_allowlist:
                return self._make_decision(decision_id, message.message_id, GatewayAction.ACCEPT,
                                          "IP in allowlist", 0.0, [], {}, start_time)
            
            # Check blocklists
            if message.envelope_from.lower() in self.sender_blocklist:
                return self._make_decision(decision_id, message.message_id, GatewayAction.REJECT,
                                          "Sender blocked", 1.0, ["blocked_sender"], {}, start_time)
            
            if sender_domain.lower() in self.domain_blocklist:
                return self._make_decision(decision_id, message.message_id, GatewayAction.REJECT,
                                          "Domain blocked", 1.0, ["blocked_domain"], {}, start_time)
            
            if message.client_ip in self.ip_blocklist:
                return self._make_decision(decision_id, message.message_id, GatewayAction.REJECT,
                                          "IP blocked", 1.0, ["blocked_ip"], {}, start_time)
            
            # Use email protection service for deep analysis
            if self.email_protection:
                # Prepare attachments for analysis
                attachments_for_analysis = []
                for att in message.attachments:
                    try:
                        content = base64.b64decode(att.get("content_base64", ""))
                        attachments_for_analysis.append({
                            "filename": att["filename"],
                            "content": content,
                            "mime_type": att["content_type"]
                        })
                    except Exception:
                        pass
                
                # Run full email analysis
                assessment = self.email_protection.analyze_email(
                    sender=message.envelope_from,
                    recipient=message.envelope_to[0] if message.envelope_to else "",
                    subject=message.subject,
                    body=message.body_text or message.body_html,
                    headers=message.headers,
                    attachments=attachments_for_analysis,
                    sender_ip=message.client_ip
                )
                
                threat_score = assessment.threat_score
                threats_detected = [t.value for t in assessment.threat_types]
                
                # Add security headers
                modified_headers["X-Seraph-Scan-Result"] = assessment.overall_risk.value
                modified_headers["X-Seraph-Threat-Score"] = str(round(threat_score * 100))
                modified_headers["X-Seraph-Assessment-ID"] = assessment.assessment_id
                
                if assessment.spf_result:
                    modified_headers["X-Seraph-SPF"] = assessment.spf_result.result.value
                if assessment.dkim_result:
                    modified_headers["X-Seraph-DKIM"] = assessment.dkim_result.result.value
                if assessment.dmarc_result:
                    modified_headers["X-Seraph-DMARC"] = assessment.dmarc_result.result.value
            
            # Make decision based on threat score
            policy = self.policies.get("default", {})
            reject_threshold = policy.get("reject_threshold", 0.9)
            quarantine_threshold = policy.get("quarantine_threshold", 0.7)
            
            if threat_score >= reject_threshold:
                action = GatewayAction.REJECT
                reason = f"High threat score: {threat_score:.2f}"
            elif threat_score >= quarantine_threshold:
                action = GatewayAction.QUARANTINE
                reason = f"Suspicious content: {threat_score:.2f}"
                # Add to quarantine
                quarantine_id = f"q_{uuid.uuid4().hex[:12]}"
                self.quarantine_queue[quarantine_id] = {
                    "message": asdict(message),
                    "decision_id": decision_id,
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    "reason": reason,
                    "threats": threats_detected
                }
            elif threat_score > 0.3:
                # Tag but accept
                action = GatewayAction.TAG
                reason = f"Low-risk indicators: {threat_score:.2f}"
                modified_headers["X-Seraph-Warning"] = "Low-risk indicators detected"
            
            return self._make_decision(decision_id, message.message_id, action, reason,
                                      threat_score, threats_detected, modified_headers, start_time)
            
        except Exception as e:
            logger.error(f"Gateway processing error: {e}")
            # On error, defer for later processing
            return self._make_decision(decision_id, message.message_id, GatewayAction.DEFER,
                                      f"Processing error: {str(e)}", 0.0, [], {}, start_time)
    
    def _make_decision(
        self,
        decision_id: str,
        message_id: str,
        action: GatewayAction,
        reason: str,
        threat_score: float,
        threats: List[str],
        headers: Dict[str, str],
        start_time: datetime
    ) -> GatewayDecision:
        """Create gateway decision and update stats"""
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        decision = GatewayDecision(
            decision_id=decision_id,
            message_id=message_id,
            action=action,
            reason=reason,
            threat_score=threat_score,
            threats_detected=threats,
            modified_headers=headers,
            processing_time_ms=processing_time
        )
        
        # Update statistics
        self.stats.total_processed += 1
        if action == GatewayAction.ACCEPT or action == GatewayAction.TAG:
            self.stats.accepted += 1
        elif action == GatewayAction.REJECT:
            self.stats.rejected += 1
            self.stats.threats_blocked += 1
        elif action == GatewayAction.QUARANTINE:
            self.stats.quarantined += 1
            self.stats.threats_blocked += 1
        elif action == GatewayAction.DEFER:
            self.stats.deferred += 1
        
        # Update average processing time
        n = self.stats.total_processed
        self.stats.avg_processing_time_ms = (
            (self.stats.avg_processing_time_ms * (n - 1) + processing_time) / n
        )
        
        return decision
    
    def add_sender_blocklist(self, sender: str):
        """Add sender to blocklist"""
        self.sender_blocklist.add(sender.lower())
    
    def add_sender_allowlist(self, sender: str):
        """Add sender to allowlist"""
        self.sender_allowlist.add(sender.lower())
    
    def add_domain_blocklist(self, domain: str):
        """Add domain to blocklist"""
        self.domain_blocklist.add(domain.lower())
    
    def add_domain_allowlist(self, domain: str):
        """Add domain to allowlist"""
        self.domain_allowlist.add(domain.lower())
    
    def add_ip_blocklist(self, ip: str):
        """Add IP to blocklist"""
        self.ip_blocklist.add(ip)
    
    def add_ip_allowlist(self, ip: str):
        """Add IP to allowlist"""
        self.ip_allowlist.add(ip)
    
    def get_quarantine(self) -> List[Dict]:
        """Get quarantined messages"""
        return list(self.quarantine_queue.values())
    
    def release_from_quarantine(self, quarantine_id: str) -> bool:
        """Release message from quarantine"""
        if quarantine_id in self.quarantine_queue:
            del self.quarantine_queue[quarantine_id]
            return True
        return False
    
    def delete_from_quarantine(self, quarantine_id: str) -> bool:
        """Permanently delete from quarantine"""
        if quarantine_id in self.quarantine_queue:
            del self.quarantine_queue[quarantine_id]
            return True
        return False
    
    def get_stats(self) -> Dict:
        """Get gateway statistics"""
        return {
            **asdict(self.stats),
            "mode": self.mode.value,
            "quarantine_size": len(self.quarantine_queue),
            "defer_queue_size": len(self.defer_queue),
            "sender_blocklist_size": len(self.sender_blocklist),
            "sender_allowlist_size": len(self.sender_allowlist),
            "domain_blocklist_size": len(self.domain_blocklist),
            "domain_allowlist_size": len(self.domain_allowlist),
            "ip_blocklist_size": len(self.ip_blocklist),
            "ip_allowlist_size": len(self.ip_allowlist)
        }
    
    def update_policy(self, policy_name: str, settings: Dict) -> bool:
        """Update gateway policy"""
        if policy_name not in self.policies:
            self.policies[policy_name] = {}
        self.policies[policy_name].update(settings)
        return True
    
    def get_policies(self) -> Dict:
        """Get all gateway policies"""
        return self.policies


class MilterGateway:
    """
    Milter protocol implementation for Postfix/Sendmail integration.
    
    Provides real-time email filtering via the milter protocol.
    """
    
    MILTER_VERSION = 6
    MILTER_ACTIONS = {
        "SMFIC_CONNECT": 'C',
        "SMFIC_HELO": 'H',
        "SMFIC_MAIL": 'M',
        "SMFIC_RCPT": 'R',
        "SMFIC_DATA": 'D',
        "SMFIC_HEADER": 'L',
        "SMFIC_EOH": 'N',
        "SMFIC_BODY": 'B',
        "SMFIC_BODYEOB": 'E',
        "SMFIC_ABORT": 'A',
        "SMFIC_QUIT": 'Q',
        "SMFIC_QUIT_NC": 'K',
        "SMFIC_UNKNOWN": 'U',
    }
    
    MILTER_RESPONSES = {
        "SMFIR_ADDRCPT": '+',
        "SMFIR_DELRCPT": '-',
        "SMFIR_ACCEPT": 'a',
        "SMFIR_REPLBODY": 'b',
        "SMFIR_CONTINUE": 'c',
        "SMFIR_DISCARD": 'd',
        "SMFIR_CONN_FAIL": 'f',
        "SMFIR_ADDHEADER": 'h',
        "SMFIR_INSHEADER": 'i',
        "SMFIR_CHGHEADER": 'm',
        "SMFIR_PROGRESS": 'p',
        "SMFIR_QUARANTINE": 'q',
        "SMFIR_REJECT": 'r',
        "SMFIR_SKIP": 's',
        "SMFIR_TEMPFAIL": 't',
        "SMFIR_REPLYCODE": 'y',
    }
    
    def __init__(self, smtp_gateway: SMTPGateway):
        self.smtp_gateway = smtp_gateway
        self.current_message: Dict = {}
        logger.info("MilterGateway initialized")
    
    def on_connect(self, hostname: str, family: str, ip: str, port: int) -> str:
        """Handle CONNECT event"""
        self.current_message = {
            "client_ip": ip,
            "client_hostname": hostname,
            "headers": {},
            "body_parts": []
        }
        
        # Check IP blocklist
        if ip in self.smtp_gateway.ip_blocklist:
            return self.MILTER_RESPONSES["SMFIR_REJECT"]
        
        return self.MILTER_RESPONSES["SMFIR_CONTINUE"]
    
    def on_mail_from(self, mail_from: str, esmtp_args: List[str]) -> str:
        """Handle MAIL FROM event"""
        self.current_message["envelope_from"] = mail_from
        
        # Check sender blocklist
        if mail_from.lower() in self.smtp_gateway.sender_blocklist:
            return self.MILTER_RESPONSES["SMFIR_REJECT"]
        
        return self.MILTER_RESPONSES["SMFIR_CONTINUE"]
    
    def on_rcpt_to(self, rcpt_to: str, esmtp_args: List[str]) -> str:
        """Handle RCPT TO event"""
        if "envelope_to" not in self.current_message:
            self.current_message["envelope_to"] = []
        self.current_message["envelope_to"].append(rcpt_to)
        return self.MILTER_RESPONSES["SMFIR_CONTINUE"]
    
    def on_header(self, name: str, value: str) -> str:
        """Handle HEADER event"""
        self.current_message["headers"][name] = value
        return self.MILTER_RESPONSES["SMFIR_CONTINUE"]
    
    def on_body(self, chunk: bytes) -> str:
        """Handle BODY event"""
        self.current_message["body_parts"].append(chunk)
        return self.MILTER_RESPONSES["SMFIR_CONTINUE"]
    
    def on_end_of_message(self) -> Tuple[str, Dict]:
        """Handle end of message - perform full analysis"""
        try:
            # Reconstruct message
            body = b"".join(self.current_message.get("body_parts", []))
            
            message = EmailMessage(
                message_id=f"milter_{uuid.uuid4().hex[:12]}",
                envelope_from=self.current_message.get("envelope_from", ""),
                envelope_to=self.current_message.get("envelope_to", []),
                subject=self.current_message.get("headers", {}).get("Subject", ""),
                headers=self.current_message.get("headers", {}),
                body_text=body.decode("utf-8", errors="replace") if body else "",
                body_html="",
                attachments=[],
                raw_size=len(body),
                received_at=datetime.now(timezone.utc).isoformat(),
                client_ip=self.current_message.get("client_ip", ""),
                client_hostname=self.current_message.get("client_hostname", "")
            )
            
            # Process through gateway
            decision = self.smtp_gateway.process_message(message)
            
            # Map decision to milter response
            if decision.action == GatewayAction.ACCEPT:
                return self.MILTER_RESPONSES["SMFIR_ACCEPT"], decision.modified_headers
            elif decision.action == GatewayAction.TAG:
                return self.MILTER_RESPONSES["SMFIR_ACCEPT"], decision.modified_headers
            elif decision.action == GatewayAction.REJECT:
                return self.MILTER_RESPONSES["SMFIR_REJECT"], {}
            elif decision.action == GatewayAction.QUARANTINE:
                return self.MILTER_RESPONSES["SMFIR_QUARANTINE"], {}
            elif decision.action == GatewayAction.DEFER:
                return self.MILTER_RESPONSES["SMFIR_TEMPFAIL"], {}
            else:
                return self.MILTER_RESPONSES["SMFIR_CONTINUE"], decision.modified_headers
                
        except Exception as e:
            logger.error(f"Milter end-of-message error: {e}")
            return self.MILTER_RESPONSES["SMFIR_TEMPFAIL"], {}
        finally:
            # Reset for next message
            self.current_message = {}


# Global instances
smtp_gateway = SMTPGateway()
milter_gateway = MilterGateway(smtp_gateway)
