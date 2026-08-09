"""
VNS Alert Service - Slack/Email Notifications
==============================================
Automated alerting for VNS detections including:
- Suspicious network flows
- C2 beacon detections
- DNS anomalies
- Canary triggers
"""

import os
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import urllib.request

logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    """Alert configuration"""
    slack_webhook_url: str = ""
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_to: List[str] = None
    min_severity: str = "high"  # Only alert for high+ severity
    cooldown_minutes: int = 5   # Prevent alert spam


class VNSAlertService:
    """
    Automated alerting service for VNS detections.
    Supports Slack webhooks and email notifications.
    """
    
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
        
        # Load config from environment
        self.config = AlertConfig(
            slack_webhook_url=os.environ.get('SLACK_WEBHOOK_URL', ''),
            email_smtp_host=os.environ.get('SMTP_HOST', ''),
            email_smtp_port=int(os.environ.get('SMTP_PORT', '587')),
            email_smtp_user=os.environ.get('SMTP_USER', ''),
            email_smtp_password=os.environ.get('SMTP_PASSWORD', ''),
            email_from=os.environ.get('ALERT_EMAIL_FROM', 'seraph@alerts.local'),
            email_to=(os.environ.get('ALERT_EMAIL_TO', '')).split(',') if os.environ.get('ALERT_EMAIL_TO') else [],
            min_severity=os.environ.get('ALERT_MIN_SEVERITY', 'high'),
            cooldown_minutes=int(os.environ.get('ALERT_COOLDOWN_MINUTES', '5'))
        )
        
        # Alert history for deduplication
        self.alert_history: Dict[str, datetime] = {}
        
        # Statistics
        self.stats = {
            "slack_alerts_sent": 0,
            "email_alerts_sent": 0,
            "alerts_suppressed": 0,
            "last_alert": None
        }
        
        self.enabled = bool(self.config.slack_webhook_url or self.config.email_smtp_host)
        
        if self.enabled:
            logger.info(f"VNS Alert Service initialized (Slack: {bool(self.config.slack_webhook_url)}, Email: {bool(self.config.email_smtp_host)})")
        else:
            logger.info("VNS Alert Service initialized (no channels configured)")
    
    def _should_alert(self, alert_key: str, severity: str) -> bool:
        """Check if we should send this alert (cooldown + severity check)"""
        severity_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        
        # Check severity
        if severity_levels.get(severity, 0) < severity_levels.get(self.config.min_severity, 3):
            return False
        
        # Check cooldown
        now = datetime.now(timezone.utc)
        last_alert = self.alert_history.get(alert_key)
        
        if last_alert:
            elapsed = (now - last_alert).total_seconds() / 60
            if elapsed < self.config.cooldown_minutes:
                self.stats["alerts_suppressed"] += 1
                return False
        
        self.alert_history[alert_key] = now
        return True
    
    def alert_suspicious_flow(self, flow: Dict[str, Any]):
        """Alert on suspicious network flow"""
        alert_key = f"flow:{flow.get('src_ip')}:{flow.get('dst_ip')}"
        
        threat_score = flow.get('threat_score', 0)
        severity = "critical" if threat_score >= 80 else "high" if threat_score >= 60 else "medium"
        
        if not self._should_alert(alert_key, severity):
            return
        
        title = "Suspicious Network Flow Detected"
        message = f"""
**Source:** {flow.get('src_ip')}:{flow.get('src_port')}
**Destination:** {flow.get('dst_ip')}:{flow.get('dst_port')}
**Protocol:** {flow.get('protocol', 'TCP')}
**Threat Score:** {threat_score}/100
**Indicators:** {', '.join(flow.get('threat_indicators', []))}
**Service:** {flow.get('service', 'Unknown')}
"""
        
        self._send_alert(title, message, severity)
    
    def alert_beacon_detection(self, beacon: Dict[str, Any]):
        """Alert on C2 beacon detection"""
        alert_key = f"beacon:{beacon.get('src_ip')}:{beacon.get('dst_ip')}"
        
        severity = "critical" if beacon.get('is_confirmed') else "high"
        
        if not self._should_alert(alert_key, severity):
            return
        
        title = "C2 Beacon Activity Detected"
        confirmed_status = "CONFIRMED" if beacon.get('is_confirmed') else "SUSPECTED"
        message = f"""
**Status:** {confirmed_status}
**Source:** {beacon.get('src_ip')}
**Destination:** {beacon.get('dst_ip')}:{beacon.get('dst_port')}
**Beacon Interval:** {beacon.get('interval_seconds', 0):.1f}s
**Jitter:** {beacon.get('interval_jitter', 0):.2f}
**Confidence:** {beacon.get('confidence', 0) * 100:.0f}%
**Algorithm:** {beacon.get('algorithm', 'Unknown')}
**First Seen:** {beacon.get('first_seen')}
"""
        
        self._send_alert(title, message, severity)
    
    def alert_dns_anomaly(self, dns_query: Dict[str, Any]):
        """Alert on suspicious DNS activity"""
        alert_key = f"dns:{dns_query.get('src_ip')}:{dns_query.get('query_name')}"
        
        severity = "high" if dns_query.get('is_suspicious') else "medium"
        
        if not self._should_alert(alert_key, severity):
            return
        
        title = "Suspicious DNS Activity"
        message = f"""
**Source:** {dns_query.get('src_ip')}
**Query:** {dns_query.get('query_name')}
**Type:** {dns_query.get('query_type', 'A')}
**Indicators:** {', '.join(dns_query.get('threat_indicators', []))}
**Response Code:** {dns_query.get('response_code')}
"""
        
        self._send_alert(title, message, severity)
    
    def alert_canary_trigger(self, canary_type: str, value: str, triggered_by: str):
        """Alert on canary trigger (deception detection)"""
        alert_key = f"canary:{canary_type}:{value}"
        severity = "critical"  # Canary triggers are always critical
        
        if not self._should_alert(alert_key, severity):
            return
        
        title = f"CANARY TRIGGERED - {canary_type.upper()}"
        message = f"""
**INTRUSION DETECTED**

**Canary Type:** {canary_type}
**Canary Value:** {value}
**Triggered By:** {triggered_by}
**Time:** {datetime.now(timezone.utc).isoformat()}

This is a high-confidence intrusion indicator. Immediate investigation recommended.
"""
        
        self._send_alert(title, message, severity)
    
    def alert_threat_analysis(self, analysis: Dict[str, Any]):
        """Alert on AI threat analysis results"""
        alert_key = f"threat:{analysis.get('analysis_id')}"
        
        severity = analysis.get('severity', 'medium')
        
        if not self._should_alert(alert_key, severity):
            return
        
        title = f"AI Threat Analysis: {analysis.get('threat_type', 'Unknown')}"
        message = f"""
**Threat Type:** {analysis.get('threat_type', 'Unknown').replace('_', ' ').title()}
**Severity:** {severity.upper()}
**Risk Score:** {analysis.get('risk_score', 0)}/100
**MITRE Techniques:** {', '.join(analysis.get('mitre_techniques', [])[:5])}

**Description:**
{analysis.get('description', 'No description available')}

**Recommended Actions:**
{chr(10).join(['- ' + action for action in analysis.get('recommended_actions', [])[:3]])}
"""
        
        self._send_alert(title, message, severity)
    
    def _send_alert(self, title: str, message: str, severity: str):
        """Send alert to all configured channels"""
        self.stats["last_alert"] = datetime.now(timezone.utc).isoformat()
        
        # Send to Slack
        if self.config.slack_webhook_url:
            self._send_slack_alert(title, message, severity)
        
        # Send email
        if self.config.email_smtp_host and self.config.email_to:
            self._send_email_alert(title, message, severity)
    
    def _send_slack_alert(self, title: str, message: str, severity: str):
        """Send alert to Slack webhook"""
        try:
            # Color based on severity
            colors = {
                "critical": "#FF0000",
                "high": "#FF6600",
                "medium": "#FFCC00",
                "low": "#00CC00"
            }
            
            payload = {
                "attachments": [{
                    "color": colors.get(severity, "#808080"),
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"🚨 {title}",
                                "emoji": True
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": message
                            }
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Severity:* {severity.upper()} | *Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                                }
                            ]
                        }
                    ]
                }]
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.config.slack_webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            urllib.request.urlopen(req, timeout=10)
            self.stats["slack_alerts_sent"] += 1
            logger.info(f"Slack alert sent: {title}")
            
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
    
    def _send_email_alert(self, title: str, message: str, severity: str):
        """Send alert via email"""
        try:
            # Create HTML email
            html_message = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #1a1a2e; color: #eaeaea; padding: 20px;">
                <div style="background-color: #16213e; border-radius: 8px; padding: 20px; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: {'#ff4444' if severity == 'critical' else '#ff8c00' if severity == 'high' else '#ffcc00'};">
                        🚨 {title}
                    </h2>
                    <div style="background-color: #0f3460; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <pre style="white-space: pre-wrap; color: #eaeaea; margin: 0;">{message}</pre>
                    </div>
                    <p style="color: #888; font-size: 12px;">
                        Severity: {severity.upper()} | Generated by Seraph AI Defense System
                    </p>
                </div>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{severity.upper()}] {title}"
            msg['From'] = self.config.email_from
            msg['To'] = ', '.join(self.config.email_to)
            
            # Attach both plain text and HTML versions
            msg.attach(MIMEText(message, 'plain'))
            msg.attach(MIMEText(html_message, 'html'))
            
            # Send email
            with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port) as server:
                server.starttls()
                if self.config.email_smtp_user:
                    server.login(self.config.email_smtp_user, self.config.email_smtp_password)
                server.sendmail(self.config.email_from, self.config.email_to, msg.as_string())
            
            self.stats["email_alerts_sent"] += 1
            logger.info(f"Email alert sent: {title}")
            
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
    
    def configure(self, slack_webhook: str = None, email_config: Dict = None):
        """Configure alert channels"""
        if slack_webhook:
            self.config.slack_webhook_url = slack_webhook
        
        if email_config:
            self.config.email_smtp_host = email_config.get('smtp_host', '')
            self.config.email_smtp_port = email_config.get('smtp_port', 587)
            self.config.email_smtp_user = email_config.get('smtp_user', '')
            self.config.email_smtp_password = email_config.get('smtp_password', '')
            self.config.email_from = email_config.get('from_address', '')
            self.config.email_to = email_config.get('to_addresses', [])
        
        self.enabled = bool(self.config.slack_webhook_url or self.config.email_smtp_host)
        
        return {
            "slack_configured": bool(self.config.slack_webhook_url),
            "email_configured": bool(self.config.email_smtp_host and self.config.email_to),
            "enabled": self.enabled
        }
    
    def get_status(self) -> Dict:
        """Get alert service status"""
        return {
            "enabled": self.enabled,
            "slack_configured": bool(self.config.slack_webhook_url),
            "email_configured": bool(self.config.email_smtp_host),
            "email_recipients": len(self.config.email_to or []),
            "min_severity": self.config.min_severity,
            "cooldown_minutes": self.config.cooldown_minutes,
            "stats": self.stats
        }
    
    def test_alert(self, channel: str = "all") -> Dict:
        """Send a test alert"""
        title = "Test Alert - Seraph AI"
        message = f"""
This is a test alert from the Seraph AI Defense System.

**Time:** {datetime.now(timezone.utc).isoformat()}
**Channel:** {channel}

If you received this alert, your notification system is working correctly.
"""
        
        results = {"slack": None, "email": None}
        
        if channel in ["all", "slack"] and self.config.slack_webhook_url:
            try:
                self._send_slack_alert(title, message, "low")
                results["slack"] = "success"
            except Exception as e:
                results["slack"] = f"failed: {str(e)}"
        
        if channel in ["all", "email"] and self.config.email_smtp_host:
            try:
                self._send_email_alert(title, message, "low")
                results["email"] = "success"
            except Exception as e:
                results["email"] = f"failed: {str(e)}"
        
        return results


# Global singleton
vns_alert_service = VNSAlertService()
