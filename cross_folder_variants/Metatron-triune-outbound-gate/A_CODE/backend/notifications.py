"""
Notification Service - Handles Email and Slack notifications for security alerts
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class NotificationConfig:
    """Configuration for notification services"""
    def __init__(self):
        self.slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
        self.sendgrid_api_key = os.environ.get("SENDGRID_API_KEY", "")
        self.sender_email = os.environ.get("SENDER_EMAIL", "alerts@anti-ai-defense.io")
        self.alert_recipients = os.environ.get("ALERT_RECIPIENTS", "").split(",")
        self.elasticsearch_url = os.environ.get("ELASTICSEARCH_URL", "")
        self.elasticsearch_api_key = os.environ.get("ELASTICSEARCH_API_KEY", "")
        # Twilio settings
        self.twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.twilio_from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
        self.sms_recipients = os.environ.get("SMS_RECIPIENTS", "").split(",")
        
    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_webhook_url)
    
    @property
    def email_enabled(self) -> bool:
        return bool(self.sendgrid_api_key and self.alert_recipients[0])
    
    @property
    def elasticsearch_enabled(self) -> bool:
        return bool(self.elasticsearch_url)
    
    @property
    def sms_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number)

config = NotificationConfig()

# =============================================================================
# SLACK NOTIFICATIONS
# =============================================================================

async def send_slack_notification(
    title: str,
    message: str,
    severity: str = "medium",
    fields: Optional[Dict[str, str]] = None,
    webhook_url: Optional[str] = None
) -> bool:
    """
    Send a notification to Slack via webhook
    
    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity (critical, high, medium, low)
        fields: Additional fields to display
        webhook_url: Optional override for webhook URL
    
    Returns:
        bool: True if successful
    """
    url = webhook_url or config.slack_webhook_url
    if not url:
        logger.warning("Slack webhook URL not configured")
        return False
    
    # Severity colors
    colors = {
        "critical": "#FF0000",  # Red
        "high": "#FF6600",      # Orange
        "medium": "#FFCC00",    # Yellow
        "low": "#00CC00"        # Green
    }
    
    color = colors.get(severity.lower(), colors["medium"])
    
    # Build Slack message payload
    payload = {
        "attachments": [{
            "color": color,
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
    
    # Add additional fields if provided
    if fields:
        field_blocks = []
        for key, value in fields.items():
            field_blocks.append({
                "type": "mrkdwn",
                "text": f"*{key}:*\n{value}"
            })
        
        if field_blocks:
            payload["attachments"][0]["blocks"].insert(2, {
                "type": "section",
                "fields": field_blocks[:10]  # Slack limits to 10 fields
            })
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Slack notification sent: {title}")
                return True
            else:
                logger.error(f"Slack notification failed: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Slack notification error: {e}")
        return False

# =============================================================================
# EMAIL NOTIFICATIONS
# =============================================================================

async def send_email_notification(
    subject: str,
    body: str,
    severity: str = "medium",
    recipients: Optional[List[str]] = None,
    html_body: Optional[str] = None
) -> bool:
    """
    Send email notification via SendGrid
    
    Args:
        subject: Email subject
        body: Plain text body
        severity: Alert severity
        recipients: List of email recipients (uses config if not provided)
        html_body: Optional HTML body
    
    Returns:
        bool: True if successful
    """
    if not config.sendgrid_api_key:
        logger.warning("SendGrid API key not configured")
        return False
    
    to_emails = recipients or [r for r in config.alert_recipients if r]
    if not to_emails:
        logger.warning("No email recipients configured")
        return False
    
    # Severity colors for HTML
    colors = {
        "critical": "#dc2626",
        "high": "#ea580c",
        "medium": "#ca8a04",
        "low": "#16a34a"
    }
    color = colors.get(severity.lower(), colors["medium"])
    
    # Build HTML email if not provided
    if not html_body:
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 8px; overflow: hidden; }}
                .header {{ background: {color}; padding: 20px; }}
                .header h1 {{ margin: 0; font-size: 20px; }}
                .content {{ padding: 20px; }}
                .severity {{ display: inline-block; padding: 4px 12px; border-radius: 4px; background: {color}; font-weight: bold; font-size: 12px; }}
                .footer {{ padding: 20px; border-top: 1px solid #334155; font-size: 12px; color: #94a3b8; }}
                pre {{ background: #0f172a; padding: 12px; border-radius: 4px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 Security Alert: {subject}</h1>
                </div>
                <div class="content">
                    <p><span class="severity">{severity.upper()}</span></p>
                    <div>{body.replace(chr(10), '<br>')}</div>
                </div>
                <div class="footer">
                    <p>Anti-AI Defense System | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <p>This is an automated security alert. Do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    # SendGrid API payload
    payload = {
        "personalizations": [{"to": [{"email": email} for email in to_emails]}],
        "from": {"email": config.sender_email, "name": "Anti-AI Defense System"},
        "subject": f"[{severity.upper()}] {subject}",
        "content": [
            {"type": "text/plain", "value": body},
            {"type": "text/html", "value": html_body}
        ]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {config.sendgrid_api_key}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            if response.status_code in [200, 202]:
                logger.info(f"Email notification sent: {subject} to {to_emails}")
                return True
            else:
                logger.error(f"Email notification failed: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Email notification error: {e}")
        return False

# =============================================================================
# SMS NOTIFICATIONS (TWILIO)
# =============================================================================

async def send_sms_notification(
    message: str,
    severity: str = "critical",
    recipients: Optional[List[str]] = None,
    account_sid: Optional[str] = None,
    auth_token: Optional[str] = None,
    from_number: Optional[str] = None
) -> bool:
    """
    Send SMS notification via Twilio
    
    Args:
        message: SMS message (max 1600 chars)
        severity: Alert severity
        recipients: List of phone numbers (E.164 format)
        account_sid: Twilio Account SID (optional, uses config if not provided)
        auth_token: Twilio Auth Token (optional, uses config if not provided)
        from_number: Twilio phone number (optional, uses config if not provided)
    
    Returns:
        bool: True if at least one SMS was sent successfully
    """
    sid = account_sid or config.twilio_account_sid
    token = auth_token or config.twilio_auth_token
    from_num = from_number or config.twilio_from_number
    
    if not all([sid, token, from_num]):
        logger.warning("Twilio credentials not configured")
        return False
    
    to_numbers = recipients or [r for r in config.sms_recipients if r]
    if not to_numbers:
        logger.warning("No SMS recipients configured")
        return False
    
    # Truncate message if too long
    sms_text = f"🚨 [{severity.upper()}] {message}"[:1600]
    
    success_count = 0
    
    for to_number in to_numbers:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                    data={
                        "To": to_number,
                        "From": from_num,
                        "Body": sms_text
                    },
                    auth=(sid, token),
                    timeout=10
                )
                if response.status_code in [200, 201]:
                    logger.info(f"SMS sent to {to_number}")
                    success_count += 1
                else:
                    logger.error(f"SMS failed to {to_number}: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"SMS error for {to_number}: {e}")
    
    return success_count > 0

# =============================================================================
# ELASTICSEARCH LOGGING
# =============================================================================

async def log_to_elasticsearch(
    index: str,
    document: Dict[str, Any],
    doc_id: Optional[str] = None
) -> bool:
    """
    Log a document to Elasticsearch
    
    Args:
        index: Elasticsearch index name
        document: Document to index
        doc_id: Optional document ID
    
    Returns:
        bool: True if successful
    """
    if not config.elasticsearch_enabled:
        return False
    
    # Add timestamp if not present
    if "@timestamp" not in document:
        document["@timestamp"] = datetime.now(timezone.utc).isoformat()
    
    url = f"{config.elasticsearch_url}/{index}/_doc"
    if doc_id:
        url += f"/{doc_id}"
    
    headers = {"Content-Type": "application/json"}
    if config.elasticsearch_api_key:
        headers["Authorization"] = f"ApiKey {config.elasticsearch_api_key}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=document, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                logger.debug(f"Elasticsearch document indexed: {index}")
                return True
            else:
                logger.warning(f"Elasticsearch indexing failed: {response.status_code}")
                return False
    except Exception as e:
        logger.warning(f"Elasticsearch error: {e}")
        return False

async def create_elasticsearch_index_template(template_name: str = "security-events") -> Dict:
    """
    Create index template for security events (for Kibana dashboards)
    
    Args:
        template_name: Name for the index template
    
    Returns:
        dict: Result of the operation
    """
    if not config.elasticsearch_enabled:
        return {"success": False, "error": "Elasticsearch not configured"}
    
    # Index template for security events
    template = {
        "index_patterns": ["security-events-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.lifecycle.name": "security-events-policy",
                "index.lifecycle.rollover_alias": "security-events"
            },
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "event_type": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "source_ip": {"type": "ip"},
                    "destination_ip": {"type": "ip"},
                    "user": {"type": "keyword"},
                    "device_id": {"type": "keyword"},
                    "threat_name": {"type": "keyword"},
                    "threat_type": {"type": "keyword"},
                    "action_taken": {"type": "keyword"},
                    "playbook_id": {"type": "keyword"},
                    "playbook_name": {"type": "keyword"},
                    "alert_id": {"type": "keyword"},
                    "agent_id": {"type": "keyword"},
                    "file_path": {"type": "text"},
                    "file_hash": {"type": "keyword"},
                    "process_name": {"type": "keyword"},
                    "process_id": {"type": "long"},
                    "command_line": {"type": "text"},
                    "description": {"type": "text"},
                    "raw_log": {"type": "text"},
                    "tags": {"type": "keyword"},
                    "geo": {
                        "properties": {
                            "country": {"type": "keyword"},
                            "city": {"type": "keyword"},
                            "location": {"type": "geo_point"}
                        }
                    },
                    "mitre": {
                        "properties": {
                            "tactic": {"type": "keyword"},
                            "technique": {"type": "keyword"},
                            "subtechnique": {"type": "keyword"}
                        }
                    }
                }
            }
        }
    }
    
    url = f"{config.elasticsearch_url}/_index_template/{template_name}"
    headers = {"Content-Type": "application/json"}
    if config.elasticsearch_api_key:
        headers["Authorization"] = f"ApiKey {config.elasticsearch_api_key}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=template, headers=headers, timeout=30)
            if response.status_code in [200, 201]:
                logger.info(f"Created Elasticsearch index template: {template_name}")
                return {"success": True, "template_name": template_name}
            else:
                return {"success": False, "error": response.text}
    except Exception as e:
        logger.error(f"Failed to create index template: {e}")
        return {"success": False, "error": str(e)}

async def log_security_event(
    event_type: str,
    severity: str,
    description: str,
    source_ip: Optional[str] = None,
    user: Optional[str] = None,
    threat_name: Optional[str] = None,
    action_taken: Optional[str] = None,
    extra_fields: Optional[Dict] = None
) -> bool:
    """
    Log a security event to Elasticsearch with proper structure
    
    Args:
        event_type: Type of event (threat_detected, alert, playbook_executed, etc.)
        severity: Event severity (critical, high, medium, low, info)
        description: Human-readable description
        source_ip: Source IP address
        user: User associated with event
        threat_name: Name of detected threat
        action_taken: Action taken in response
        extra_fields: Additional fields to include
    
    Returns:
        bool: True if logged successfully
    """
    # Create index name with date for easy rollover
    today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    index = f"security-events-{today}"
    
    document = {
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "severity": severity,
        "description": description
    }
    
    if source_ip:
        document["source_ip"] = source_ip
    if user:
        document["user"] = user
    if threat_name:
        document["threat_name"] = threat_name
    if action_taken:
        document["action_taken"] = action_taken
    if extra_fields:
        document.update(extra_fields)
    
    return await log_to_elasticsearch(index, document)

# =============================================================================
# UNIFIED NOTIFICATION DISPATCHER
# =============================================================================

class NotificationDispatcher:
    """
    Dispatches notifications to all configured channels based on severity
    """
    
    # Minimum severity for each channel (lower number = higher severity)
    SEVERITY_LEVELS = {"critical": 1, "high": 2, "medium": 3, "low": 4}
    
    # Which channels receive which minimum severity
    CHANNEL_THRESHOLDS = {
        "slack": 3,      # medium and above
        "email": 2,      # high and above
        "elasticsearch": 4  # all severities
    }
    
    def __init__(self):
        self.pending_notifications = []
    
    def _should_notify(self, channel: str, severity: str) -> bool:
        """Check if channel should receive notification at this severity"""
        severity_level = self.SEVERITY_LEVELS.get(severity.lower(), 3)
        threshold = self.CHANNEL_THRESHOLDS.get(channel, 3)
        return severity_level <= threshold
    
    async def dispatch(
        self,
        event_type: str,
        title: str,
        message: str,
        severity: str = "medium",
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        force_all: bool = False
    ) -> Dict[str, bool]:
        """
        Dispatch notification to all appropriate channels
        
        Args:
            event_type: Type of event (threat, alert, scan, etc.)
            title: Notification title
            message: Notification message
            severity: Event severity
            source: Source of the event (agent name, system, etc.)
            details: Additional details
            force_all: Force send to all channels regardless of threshold
        
        Returns:
            Dict with success status for each channel
        """
        results = {"slack": False, "email": False, "elasticsearch": False}
        
        # Prepare common data
        fields = {"Source": source or "System", "Event Type": event_type}
        if details:
            for k, v in list(details.items())[:5]:
                fields[k] = str(v)[:100]
        
        # Slack notification
        if config.slack_enabled and (force_all or self._should_notify("slack", severity)):
            results["slack"] = await send_slack_notification(
                title=title,
                message=message,
                severity=severity,
                fields=fields
            )
        
        # Email notification
        if config.email_enabled and (force_all or self._should_notify("email", severity)):
            results["email"] = await send_email_notification(
                subject=title,
                body=f"{message}\n\nSource: {source or 'System'}\nEvent Type: {event_type}\n\nDetails:\n{details}",
                severity=severity
            )
        
        # Elasticsearch logging (always log if configured)
        if config.elasticsearch_enabled:
            doc = {
                "event_type": event_type,
                "title": title,
                "message": message,
                "severity": severity,
                "source": source,
                "details": details,
                "notifications_sent": results
            }
            results["elasticsearch"] = await log_to_elasticsearch(
                index=f"security-events-{datetime.now().strftime('%Y.%m')}",
                document=doc
            )
        
        logger.info(f"Notification dispatched: {title} - Results: {results}")
        return results

# Global dispatcher instance
dispatcher = NotificationDispatcher()

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def notify_critical_threat(
    threat_name: str,
    description: str,
    source_ip: Optional[str] = None,
    target_system: Optional[str] = None,
    agent_name: Optional[str] = None
) -> Dict[str, bool]:
    """Send critical threat notification"""
    return await dispatcher.dispatch(
        event_type="threat",
        title=f"Critical Threat Detected: {threat_name}",
        message=description,
        severity="critical",
        source=agent_name,
        details={
            "Source IP": source_ip or "Unknown",
            "Target": target_system or "Unknown"
        }
    )

async def notify_malware_detected(
    filepath: str,
    malware_type: str,
    action_taken: str,
    agent_name: Optional[str] = None
) -> Dict[str, bool]:
    """Send malware detection notification"""
    return await dispatcher.dispatch(
        event_type="malware",
        title=f"Malware Detected: {malware_type}",
        message=f"Malware found in: {filepath}\nAction: {action_taken}",
        severity="critical",
        source=agent_name,
        details={
            "File Path": filepath,
            "Malware Type": malware_type,
            "Action Taken": action_taken
        }
    )

async def notify_quarantine_action(
    filepath: str,
    threat_name: str,
    quarantine_path: str,
    agent_name: Optional[str] = None
) -> Dict[str, bool]:
    """Send quarantine action notification"""
    return await dispatcher.dispatch(
        event_type="quarantine",
        title=f"File Quarantined: {threat_name}",
        message=f"Infected file has been automatically quarantined.\nOriginal: {filepath}\nQuarantined to: {quarantine_path}",
        severity="high",
        source=agent_name,
        details={
            "Original Path": filepath,
            "Quarantine Path": quarantine_path,
            "Threat": threat_name
        }
    )

async def notify_new_host_discovered(
    ip_address: str,
    hostname: Optional[str] = None,
    mac_address: Optional[str] = None,
    agent_name: Optional[str] = None
) -> Dict[str, bool]:
    """Send new host discovery notification"""
    return await dispatcher.dispatch(
        event_type="discovery",
        title=f"New Host Discovered: {ip_address}",
        message="A new device has been detected on the network.",
        severity="low",
        source=agent_name,
        details={
            "IP Address": ip_address,
            "Hostname": hostname or "Unknown",
            "MAC Address": mac_address or "Unknown"
        }
    )

async def notify_intrusion_attempt(
    signature: str,
    source_ip: str,
    dest_ip: str,
    category: Optional[str] = None,
    agent_name: Optional[str] = None
) -> Dict[str, bool]:
    """Send intrusion detection notification"""
    return await dispatcher.dispatch(
        event_type="intrusion",
        title=f"Intrusion Attempt: {signature}",
        message="IDS alert triggered. Potential intrusion attempt detected.",
        severity="high",
        source=agent_name,
        details={
            "Signature": signature,
            "Source IP": source_ip,
            "Destination IP": dest_ip,
            "Category": category or "Unknown"
        }
    )
