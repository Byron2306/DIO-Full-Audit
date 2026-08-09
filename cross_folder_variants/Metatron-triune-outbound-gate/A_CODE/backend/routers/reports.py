"""
Reports Router
==============
Enhanced PDF reporting with multiple report types and robust error handling.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List
import os
import io
import traceback

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

from .dependencies import (
    get_current_user, get_db, check_permission, logger
)
from .ai_analysis import call_openai

router = APIRouter(prefix="/reports", tags=["Reports"])


# Route-level dashboard modules from frontend App.js.
# Kept in backend so report summaries can explicitly reason over all major pages.
DASHBOARD_MODULES = [
    "dashboard",
    "ai-detection",
    "alerts",
    "threats",
    "network",
    "hunting",
    "honeypots",
    "reports",
    "quarantine",
    "response",
    "timeline",
    "audit",
    "settings",
    "threat-intel",
    "ransomware",
    "containers",
    "vpn",
    "correlation",
    "edr",
    "soar",
    "honey-tokens",
    "zero-trust",
    "ml-prediction",
    "sandbox",
    "browser-isolation",
    "kibana",
    "cli-sessions",
    "ai-threats",
    "command-center",
    "advanced",
    "heatmap",
    "vns-alerts",
    "browser-extension",
    "setup-guide",
    "tenants",
    "unified-agent",
    "cspm",
    "attack-paths",
    "deception",
    "kernel-sensors",
    "secure-boot",
    "detection-engineering",
    "identity",
    "email-protection",
    "mobile-security",
    "email-gateway",
    "mdm",
    "sophia",
    "world",
    "investigation",
    "ai-activity",
    "command",
    "response-operations",
    "email-security",
    "endpoint-mobility",
    "zeek",
    "osquery-fleet",
]


async def _safe_count(db: Any, collection_name: str, query: Optional[Dict[str, Any]] = None) -> int:
    """Count documents safely; return 0 if collection doesn't exist or query fails."""
    try:
        return await db[collection_name].count_documents(query or {})
    except Exception:
        return 0


async def _safe_recent(db: Any, collection_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch recent docs safely using created_at/timestamp fallback."""
    try:
        docs = await db[collection_name].find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        if docs:
            return docs
        return await db[collection_name].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    except Exception:
        return []


def _calc_global_risk_score(snapshot: Dict[str, Any]) -> int:
    """Compute deterministic system-wide risk score from aggregated signals."""
    active_threats = snapshot["core"]["active_threats"]
    critical_alerts = snapshot["core"]["critical_alerts"]
    high_alerts = snapshot["core"]["high_alerts"]
    unresolved_alerts = snapshot["core"]["unresolved_alerts"]
    quarantined = snapshot["core"]["quarantined_items"]

    cspm_open = snapshot["cloud"]["open_findings"]
    cspm_high_critical = snapshot["cloud"]["high_critical_findings"]
    public_cloud_exposure = snapshot["cloud"]["public_exposures"]

    email_quarantine = snapshot["email"]["quarantined_messages"]
    email_high = snapshot["email"]["high_risk_assessments"]

    mobile_non_compliant = snapshot["mobile"]["non_compliant_devices"]
    mobile_active_threats = snapshot["mobile"]["active_threats"]

    attack_paths = snapshot["advanced"]["attack_paths"]
    deception_hits = snapshot["advanced"]["deception_hits"]
    kernel_critical = snapshot["advanced"]["kernel_critical_events"]

    signal = (
        (active_threats * 5)
        + (critical_alerts * 7)
        + (high_alerts * 4)
        + (unresolved_alerts * 2)
        + (quarantined * 2)
        + (cspm_open * 2)
        + (cspm_high_critical * 5)
        + (public_cloud_exposure * 6)
        + (email_quarantine * 2)
        + (email_high * 4)
        + (mobile_non_compliant * 3)
        + (mobile_active_threats * 5)
        + (attack_paths * 3)
        + (deception_hits * 2)
        + (kernel_critical * 5)
    )

    # Dampen when strong recovery signals exist.
    resolved_threats = snapshot["core"]["resolved_threats"]
    contained_threats = snapshot["core"]["contained_threats"]
    mitigations = (resolved_threats * 2) + (contained_threats * 2)
    score = max(5, min(100, int(signal - mitigations)))
    return score


def _build_local_summary(snapshot: Dict[str, Any]) -> str:
    """Build a rich deterministic summary for environments without external AI keys."""
    score = _calc_global_risk_score(snapshot)
    severity_band = "critical" if score >= 85 else "high" if score >= 65 else "medium" if score >= 40 else "low"

    indicators: List[str] = []
    if snapshot["core"]["active_threats"] > 0:
        indicators.append(
            f"{snapshot['core']['active_threats']} active threat(s) with {snapshot['core']['critical_alerts']} critical alert(s) currently open"
        )
    if snapshot["cloud"]["high_critical_findings"] > 0:
        indicators.append(
            f"Cloud posture has {snapshot['cloud']['high_critical_findings']} high/critical finding(s) across {snapshot['cloud']['providers_observed']} provider signal(s)"
        )
    if snapshot["email"]["quarantined_messages"] > 0:
        indicators.append(
            f"Email security quarantined {snapshot['email']['quarantined_messages']} message(s); {snapshot['email']['high_risk_assessments']} high-risk assessment(s) detected"
        )
    if snapshot["mobile"]["active_threats"] > 0 or snapshot["mobile"]["non_compliant_devices"] > 0:
        indicators.append(
            f"Endpoint mobility reports {snapshot['mobile']['active_threats']} active threat(s) and {snapshot['mobile']['non_compliant_devices']} non-compliant device(s)"
        )
    if snapshot["advanced"]["attack_paths"] > 0:
        indicators.append(
            f"Attack path analysis contains {snapshot['advanced']['attack_paths']} modeled path(s), indicating reachable chained risk"
        )
    if snapshot["operations"]["agents"] > 0:
        indicators.append(
            f"{snapshot['operations']['agents']} active agent(s) are reporting with {snapshot['operations']['timeline_events']} timeline/event artifact(s) available"
        )
    if snapshot["advanced"]["secure_boot_failures"] > 0:
        indicators.append(
            f"Secure boot telemetry includes {snapshot['advanced']['secure_boot_failures']} failure/tamper event(s) requiring host integrity review"
        )
    if not indicators:
        indicators.append("No high-severity indicators observed; environment appears mostly baseline or demo-seeded")

    recommendations: List[str] = []
    if snapshot["cloud"]["high_critical_findings"] > 0 or snapshot["cloud"]["public_exposures"] > 0:
        recommendations.append("Prioritize cloud remediation: close public exposures and resolve high/critical CSPM findings first")
    if snapshot["email"]["high_risk_assessments"] > 0:
        recommendations.append("Tighten email controls: enforce DMARC/SPF/DKIM alignment and block repeat malicious sender patterns")
    if snapshot["mobile"]["non_compliant_devices"] > 0 or snapshot["mobile"]["active_threats"] > 0:
        recommendations.append("Enforce endpoint compliance policy and isolate high-risk mobile devices until remediated")
    if snapshot["core"]["critical_alerts"] > 0 or snapshot["core"]["active_threats"] > 0:
        recommendations.append("Run response playbooks on active incidents and verify containment-to-resolution SLA adherence")
    if snapshot["advanced"]["kernel_critical_events"] > 0:
        recommendations.append("Investigate kernel critical events immediately and validate host integrity controls")
    if snapshot["operations"]["audit_logs"] == 0:
        recommendations.append("Enable and retain audit telemetry for better incident reconstruction and compliance traceability")
    if not recommendations:
        recommendations.append("Continue continuous monitoring and schedule routine validation drills across all security domains")

    modules_count = len(snapshot.get("dashboard_modules", []))
    core = snapshot["core"]
    cloud = snapshot["cloud"]
    email = snapshot["email"]
    mobile = snapshot["mobile"]
    operations = snapshot["operations"]
    advanced = snapshot["advanced"]

    recent_threats = ", ".join(core.get("recent_threat_names", [])[:5]) or "none"
    recent_alerts = ", ".join(core.get("recent_alert_titles", [])[:5]) or "none"

    return (
        f"RISK SCORE: {score}\n"
        f"RISK BAND: {severity_band.upper()}\n"
        f"THREAT INDICATORS:\n"
        + "\n".join(f"- {item}" for item in indicators[:10])
        + "\n"
        + "ANALYSIS:\n"
        + (
            "System-wide synthesis completed across dashboard modules and backend telemetry collections. "
            f"Coverage included {modules_count} dashboard module(s) spanning detection, prevention, response, "
            "governance, and endpoint/cloud/email domains.\n\n"
            f"Core posture: threats={core['total_threats']} (active={core['active_threats']}, contained={core['contained_threats']}, resolved={core['resolved_threats']}), "
            f"alerts={core['total_alerts']} (critical={core['critical_alerts']}, high={core['high_alerts']}, unresolved={core['unresolved_alerts']}).\n"
            f"Cloud posture: providers={cloud['providers_observed']}, scans={cloud['scans']}, open_findings={cloud['open_findings']}, "
            f"high_or_critical={cloud['high_critical_findings']}, public_exposures={cloud['public_exposures']}.\n"
            f"Email posture: assessments={email['assessments']}, quarantined_messages={email['quarantined_messages']}, "
            f"high_risk={email['high_risk_assessments']}, blocked_senders={email['blocked_senders']}, trusted_domains={email['trusted_domains']}.\n"
            f"Endpoint mobility posture: devices={mobile['devices']}, non_compliant={mobile['non_compliant_devices']}, "
            f"active_mobile_threats={mobile['active_threats']}, policies={mobile['policies']}.\n"
            f"Operations posture: response_actions={operations['response_actions']}, audit_logs={operations['audit_logs']}, "
            f"timeline_events={operations['timeline_events']}, agents={operations['agents']}, network_scans={operations['network_scans']}.\n"
            f"Advanced detections: attack_paths={advanced['attack_paths']}, deception_hits={advanced['deception_hits']}, "
            f"kernel_critical_or_high={advanced['kernel_critical_events']}, secure_boot_failures={advanced['secure_boot_failures']}, "
            f"osquery_findings={advanced['osquery_findings']}, zeek_events={advanced['zeek_events']}, sigma_matches={advanced['sigma_matches']}.\n\n"
            f"Recent threat names: {recent_threats}.\n"
            f"Recent alert titles: {recent_alerts}.\n"
            "This summary is generated from current datastore state rather than a static template."
        )
        + "\n"
        + "RECOMMENDATIONS:\n"
        + "\n".join(f"- {item}" for item in recommendations[:8])
        + "\n"
    )


async def _build_full_system_snapshot(db: Any) -> Dict[str, Any]:
    """Aggregate a broad snapshot spanning all dashboard domains."""
    severity_critical_q = {"severity": {"$in": ["critical", "Critical"]}}
    severity_high_q = {"severity": {"$in": ["high", "High"]}}

    threats = await _safe_recent(db, "threats", 20)
    alerts = await _safe_recent(db, "alerts", 30)

    snapshot: Dict[str, Any] = {
        "dashboard_modules": DASHBOARD_MODULES,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "core": {
            "total_threats": await _safe_count(db, "threats"),
            "active_threats": await _safe_count(db, "threats", {"status": "active"}),
            "contained_threats": await _safe_count(db, "threats", {"status": "contained"}),
            "resolved_threats": await _safe_count(db, "threats", {"status": "resolved"}),
            "total_alerts": await _safe_count(db, "alerts"),
            "critical_alerts": await _safe_count(db, "alerts", {"severity": "critical", "status": {"$ne": "resolved"}}),
            "high_alerts": await _safe_count(db, "alerts", {"severity": "high", "status": {"$ne": "resolved"}}),
            "unresolved_alerts": await _safe_count(db, "alerts", {"status": {"$in": ["new", "active", "open", "acknowledged"]}}),
            "quarantined_items": await _safe_count(db, "quarantine_entries") + await _safe_count(db, "quarantine"),
            "recent_threat_names": [t.get("name", "Unknown") for t in threats[:8]],
            "recent_alert_titles": [a.get("title", a.get("message", "Alert")) for a in alerts[:8]],
        },
        "cloud": {
            "providers_observed": await _safe_count(db, "cspm_providers") + await _safe_count(db, "cloud_providers"),
            "scans": await _safe_count(db, "cspm_scans"),
            "open_findings": await _safe_count(db, "cspm_findings", {"status": {"$in": ["open", "OPEN"]}}),
            "high_critical_findings": await _safe_count(db, "cspm_findings", {"severity": {"$in": ["high", "critical", "HIGH", "CRITICAL"]}}),
            "public_exposures": await _safe_count(db, "cspm_findings", {"title": {"$regex": "public|exposed", "$options": "i"}}),
        },
        "email": {
            "assessments": await _safe_count(db, "email_assessments"),
            "quarantined_messages": await _safe_count(db, "email_quarantine") + await _safe_count(db, "quarantined_emails"),
            "high_risk_assessments": await _safe_count(db, "email_assessments", {"risk_level": {"$in": ["high", "critical"]}}),
            "blocked_senders": await _safe_count(db, "blocked_senders"),
            "trusted_domains": await _safe_count(db, "trusted_domains"),
        },
        "mobile": {
            "devices": await _safe_count(db, "mobile_devices") + await _safe_count(db, "mdm_devices"),
            "non_compliant_devices": await _safe_count(db, "mobile_devices", {"status": {"$in": ["non_compliant", "at_risk", "compromised"]}})
            + await _safe_count(db, "mdm_devices", {"status": {"$in": ["non_compliant", "at_risk", "compromised"]}}),
            "active_threats": await _safe_count(db, "mobile_threats", {"is_resolved": {"$ne": True}}) + await _safe_count(db, "mdm_threats", {"is_resolved": {"$ne": True}}),
            "policies": await _safe_count(db, "mobile_policies") + await _safe_count(db, "mdm_policies"),
        },
        "operations": {
            "response_actions": await _safe_count(db, "response_actions"),
            "audit_logs": await _safe_count(db, "audit_logs") + await _safe_count(db, "audit_entries"),
            "timeline_events": await _safe_count(db, "timeline_events") + await _safe_count(db, "agent_events"),
            "agents": await _safe_count(db, "agents"),
            "network_scans": await _safe_count(db, "network_scans"),
            "discovered_hosts": await _safe_count(db, "discovered_hosts"),
        },
        "advanced": {
            "attack_paths": await _safe_count(db, "attack_paths"),
            "deception_hits": await _safe_count(db, "deception_hits"),
            "kernel_critical_events": await _safe_count(db, "kernel_events", severity_critical_q) + await _safe_count(db, "kernel_events", severity_high_q),
            "secure_boot_failures": await _safe_count(db, "secure_boot_events", {"status": {"$in": ["failed", "invalid", "tampered"]}}),
            "osquery_findings": await _safe_count(db, "osquery_findings"),
            "zeek_events": await _safe_count(db, "zeek_events"),
            "sigma_matches": await _safe_count(db, "sigma_matches"),
        },
    }

    snapshot["global_risk_score"] = _calc_global_risk_score(snapshot)
    return snapshot


def safe_str(value, max_length=50, default="N/A"):
    """Safely convert value to string with length limit"""
    try:
        if value is None:
            return default
        result = str(value)
        if len(result) > max_length:
            return result[:max_length-3] + "..."
        return result
    except Exception:
        return default


def create_pie_chart(data: dict, width=200, height=150):
    """Create a pie chart drawing"""
    try:
        drawing = Drawing(width, height)
        pie = Pie()
        pie.x = 50
        pie.y = 25
        pie.width = 100
        pie.height = 100
        
        values = list(data.values())
        labels = list(data.keys())
        
        if sum(values) == 0:
            return None
        
        pie.data = values
        pie.labels = labels
        pie.slices.strokeWidth = 0.5
        
        # Color scheme
        chart_colors = [
            colors.HexColor('#EF4444'),  # Red
            colors.HexColor('#F97316'),  # Orange
            colors.HexColor('#FBBF24'),  # Yellow
            colors.HexColor('#22C55E'),  # Green
            colors.HexColor('#3B82F6'),  # Blue
        ]
        
        for i, _ in enumerate(values):
            if i < len(chart_colors):
                pie.slices[i].fillColor = chart_colors[i]
        
        drawing.add(pie)
        return drawing
    except Exception as e:
        logger.warning(f"Chart creation failed: {e}")
        return None


def generate_threat_report_pdf(threats: list, alerts: list, stats: dict, 
                                include_charts: bool = True) -> io.BytesIO:
    """Generate PDF threat intelligence report with enhanced formatting"""
    buffer = io.BytesIO()
    
    try:
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4, 
            rightMargin=50, 
            leftMargin=50, 
            topMargin=50, 
            bottomMargin=50
        )
        
        styles = getSampleStyleSheet()
        
        # Define custom styles
        styles.add(ParagraphStyle(
            name='TitleStyle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#3B82F6'),
            alignment=1  # Center
        ))
        styles.add(ParagraphStyle(
            name='SubtitleStyle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            textColor=colors.HexColor('#64748B'),
            alignment=1  # Center
        ))
        styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#1E293B')
        ))
        styles.add(ParagraphStyle(
            name='CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=8
        ))
        styles.add(ParagraphStyle(
            name='FooterStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#94A3B8'),
            alignment=1
        ))
        
        elements = []
        
        # Title Page
        elements.append(Spacer(1, 100))
        elements.append(Paragraph("SERAPH AI", styles['TitleStyle']))
        elements.append(Paragraph("THREAT INTELLIGENCE REPORT", styles['TitleStyle']))
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", 
            styles['SubtitleStyle']
        ))
        elements.append(Paragraph("Classification: CONFIDENTIAL", styles['SubtitleStyle']))
        elements.append(PageBreak())
        
        # Executive Summary
        elements.append(Paragraph("EXECUTIVE SUMMARY", styles['SectionTitle']))
        
        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Threats', str(stats.get('total_threats', 0)), 
             'Critical' if stats.get('total_threats', 0) > 50 else 'Normal'],
            ['Active Threats', str(stats.get('active_threats', 0)),
             'Critical' if stats.get('active_threats', 0) > 10 else 'Normal'],
            ['Contained Threats', str(stats.get('contained_threats', 0)), 'Resolved'],
            ['Resolved Threats', str(stats.get('resolved_threats', 0)), 'Resolved'],
            ['Critical Alerts', str(stats.get('critical_alerts', 0)),
             'Critical' if stats.get('critical_alerts', 0) > 0 else 'Normal'],
            ['System Health', f"{stats.get('system_health', 100):.1f}%",
             'Good' if stats.get('system_health', 100) >= 80 else 'Degraded']
        ]
        
        summary_table = Table(summary_data, colWidths=[180, 100, 80])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E293B')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 28),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 30))
        
        # Severity Distribution Chart
        if include_charts:
            severity_data = {
                'Critical': len([t for t in threats if t.get('severity') == 'critical']),
                'High': len([t for t in threats if t.get('severity') == 'high']),
                'Medium': len([t for t in threats if t.get('severity') == 'medium']),
                'Low': len([t for t in threats if t.get('severity') == 'low']),
            }
            
            if sum(severity_data.values()) > 0:
                elements.append(Paragraph("THREAT SEVERITY DISTRIBUTION", styles['SectionTitle']))
                chart = create_pie_chart(severity_data)
                if chart:
                    elements.append(chart)
                elements.append(Spacer(1, 20))
        
        # Active Threats Section
        elements.append(Paragraph("ACTIVE THREATS", styles['SectionTitle']))
        active_threats = [t for t in threats if t.get('status') == 'active']
        
        if active_threats:
            threat_data = [['Name', 'Type', 'Severity', 'Source']]
            for threat in active_threats[:15]:
                threat_data.append([
                    safe_str(threat.get('name', 'Unknown'), 35),
                    safe_str(threat.get('type', 'Unknown'), 20),
                    safe_str(threat.get('severity', 'Unknown'), 10).upper(),
                    safe_str(threat.get('source_ip', 'N/A'), 15)
                ])
            
            threat_table = Table(threat_data, colWidths=[150, 100, 70, 100])
            threat_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EF4444')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
                ('ROWHEIGHT', (0, 0), (-1, -1), 24),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Alternate row colors
                *[('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FEF2F2' if i % 2 == 0 else '#FFFFFF')) 
                  for i in range(1, len(threat_data))]
            ]))
            elements.append(threat_table)
        else:
            elements.append(Paragraph("No active threats at this time.", styles['CustomBody']))
        
        elements.append(Spacer(1, 30))
        
        # Recent Alerts Section
        elements.append(Paragraph("RECENT ALERTS", styles['SectionTitle']))
        if alerts:
            alert_data = [['Title', 'Type', 'Severity', 'Status']]
            for alert in alerts[:15]:
                alert_data.append([
                    safe_str(alert.get('title', 'Unknown'), 40),
                    safe_str(alert.get('type', 'Unknown'), 20),
                    safe_str(alert.get('severity', 'Unknown'), 10).upper(),
                    safe_str(alert.get('status', 'Unknown'), 15)
                ])
            
            alert_table = Table(alert_data, colWidths=[170, 100, 70, 80])
            alert_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
                ('ROWHEIGHT', (0, 0), (-1, -1), 24),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(alert_table)
        else:
            elements.append(Paragraph("No recent alerts.", styles['CustomBody']))
        
        elements.append(Spacer(1, 50))
        
        # Footer
        elements.append(Paragraph("--- End of Report ---", styles['FooterStyle']))
        elements.append(Paragraph("Generated by Seraph AI Defense System", styles['FooterStyle']))
        elements.append(Paragraph("This report is confidential and intended for authorized personnel only.", styles['FooterStyle']))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}\n{traceback.format_exc()}")
        # Return a simple error PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = [
            Paragraph("Error Generating Report", styles['Heading1']),
            Paragraph(f"An error occurred: {safe_str(str(e), 200)}", styles['Normal']),
            Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", styles['Normal']),
        ]
        doc.build(elements)
        buffer.seek(0)
        return buffer

@router.get("/threat-intelligence")
async def generate_threat_report(current_user: dict = Depends(check_permission("export_reports"))):
    """Generate PDF threat intelligence report"""
    db = get_db()
    
    # Gather data
    threats = await db.threats.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    
    # Calculate stats
    total_threats = len(threats)
    active_threats = len([t for t in threats if t.get('status') == 'active'])
    contained_threats = len([t for t in threats if t.get('status') == 'contained'])
    resolved_threats = len([t for t in threats if t.get('status') == 'resolved'])
    critical_alerts = len([a for a in alerts if a.get('severity') == 'critical' and a.get('status') != 'resolved'])
    
    system_health = 100.0
    if total_threats > 0:
        system_health = ((contained_threats + resolved_threats) / total_threats) * 100
    
    stats = {
        'total_threats': total_threats,
        'active_threats': active_threats,
        'contained_threats': contained_threats,
        'resolved_threats': resolved_threats,
        'critical_alerts': critical_alerts,
        'system_health': system_health
    }
    
    # Generate PDF
    pdf_buffer = generate_threat_report_pdf(threats, alerts, stats)
    
    filename = f"threat_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/ai-summary")
async def generate_ai_summary_report(current_user: dict = Depends(check_permission("export_reports"))):
    """Generate AI-powered threat summary"""
    db = get_db()
    snapshot = await _build_full_system_snapshot(db)
    threats_analyzed = snapshot["core"]["total_threats"]
    alerts_analyzed = snapshot["core"]["total_alerts"]

    context = (
        "SYSTEM-WIDE DASHBOARD STATE (ALL MODULES):\n"
        f"- Modules covered ({len(DASHBOARD_MODULES)}): {', '.join(DASHBOARD_MODULES)}\n"
        f"- Generated at: {snapshot['generated_at']}\n"
        f"- Computed global risk score: {snapshot['global_risk_score']}\n\n"
        "CORE SECURITY:\n"
        f"- Threats total/active/contained/resolved: {snapshot['core']['total_threats']}/"
        f"{snapshot['core']['active_threats']}/{snapshot['core']['contained_threats']}/{snapshot['core']['resolved_threats']}\n"
        f"- Alerts total/critical/high/unresolved: {snapshot['core']['total_alerts']}/"
        f"{snapshot['core']['critical_alerts']}/{snapshot['core']['high_alerts']}/{snapshot['core']['unresolved_alerts']}\n"
        f"- Quarantined items: {snapshot['core']['quarantined_items']}\n"
        f"- Recent threat names: {', '.join(snapshot['core']['recent_threat_names'][:6]) or 'none'}\n\n"
        "CLOUD / CSPM:\n"
        f"- Providers observed: {snapshot['cloud']['providers_observed']}\n"
        f"- Scans: {snapshot['cloud']['scans']}\n"
        f"- Open findings: {snapshot['cloud']['open_findings']}\n"
        f"- High/Critical findings: {snapshot['cloud']['high_critical_findings']}\n"
        f"- Public exposure findings: {snapshot['cloud']['public_exposures']}\n\n"
        "EMAIL SECURITY:\n"
        f"- Assessments: {snapshot['email']['assessments']}\n"
        f"- Quarantined messages: {snapshot['email']['quarantined_messages']}\n"
        f"- High-risk assessments: {snapshot['email']['high_risk_assessments']}\n"
        f"- Blocked senders: {snapshot['email']['blocked_senders']}\n"
        f"- Trusted domains: {snapshot['email']['trusted_domains']}\n\n"
        "ENDPOINT MOBILITY / MDM:\n"
        f"- Devices: {snapshot['mobile']['devices']}\n"
        f"- Non-compliant devices: {snapshot['mobile']['non_compliant_devices']}\n"
        f"- Active mobile threats: {snapshot['mobile']['active_threats']}\n"
        f"- Policies: {snapshot['mobile']['policies']}\n\n"
        "OPERATIONS:\n"
        f"- Response actions: {snapshot['operations']['response_actions']}\n"
        f"- Audit logs: {snapshot['operations']['audit_logs']}\n"
        f"- Timeline/agent events: {snapshot['operations']['timeline_events']}\n"
        f"- Agents: {snapshot['operations']['agents']}\n"
        f"- Network scans/discovered hosts: {snapshot['operations']['network_scans']}/"
        f"{snapshot['operations']['discovered_hosts']}\n\n"
        "ADVANCED DETECTION:\n"
        f"- Attack paths: {snapshot['advanced']['attack_paths']}\n"
        f"- Deception hits: {snapshot['advanced']['deception_hits']}\n"
        f"- Kernel critical/high events: {snapshot['advanced']['kernel_critical_events']}\n"
        f"- Secure boot failures: {snapshot['advanced']['secure_boot_failures']}\n"
        f"- Osquery findings: {snapshot['advanced']['osquery_findings']}\n"
        f"- Zeek events: {snapshot['advanced']['zeek_events']}\n"
        f"- Sigma matches: {snapshot['advanced']['sigma_matches']}\n"
    )

    system_message = """You are a principal SOC analyst. Build a true full-system executive report from ALL provided dashboard domains.

Rules:
- Use the data exactly as provided; do not ignore any domain.
- Produce this exact section format:
RISK SCORE: [0-100]
THREAT INDICATORS:
- [indicator]
ANALYSIS:
[multi-paragraph synthesis of entire environment]
RECOMMENDATIONS:
- [prioritized action]
- Include cross-domain relationships (cloud + identity + endpoint + email + network + response).
- If data appears demo-seeded, mention that while still reasoning from values.
"""

    try:
        has_external_ai = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY"))
        if has_external_ai:
            summary = await call_openai(system_message, f"Analyze this security data and provide an executive summary:\n{context}")
        else:
            summary = _build_local_summary(snapshot)
        return {
            "summary": summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_points": {
                "threats_analyzed": threats_analyzed,
                "alerts_analyzed": alerts_analyzed,
                "dashboard_modules_covered": len(DASHBOARD_MODULES),
                "global_risk_score": snapshot["global_risk_score"],
            }
        }
    except Exception as e:
        logger.error(f"AI summary generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")



@router.get("/stress-test")
async def stress_test_reports(
    iterations: int = Query(default=10, le=100, ge=1),
    current_user: dict = Depends(get_current_user)
):
    """
    Stress test PDF report generation.
    Generates multiple reports to verify stability.
    """
    results = {
        "total_iterations": iterations,
        "successful": 0,
        "failed": 0,
        "errors": [],
        "timing_ms": []
    }
    
    # Generate test data
    test_threats = [
        {
            "id": f"threat_{i}",
            "name": f"Test Threat {i}",
            "severity": ["critical", "high", "medium", "low"][i % 4],
            "type": ["malware", "phishing", "ransomware", "credential_theft"][i % 4],
            "status": "active",
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "description": f"This is test threat number {i} for stress testing the PDF generation system."
        }
        for i in range(50)
    ]
    
    test_alerts = [
        {
            "id": f"alert_{i}",
            "message": f"Test alert message {i}",
            "severity": ["critical", "high", "medium", "low"][i % 4],
            "acknowledged": i % 2 == 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        for i in range(100)
    ]
    
    test_stats = {
        "critical_threats": 10,
        "high_threats": 15,
        "medium_threats": 20,
        "low_threats": 5,
        "total_alerts": 100,
        "acknowledged_alerts": 50,
        "active_agents": 5
    }
    
    import time
    
    for i in range(iterations):
        start_time = time.time()
        try:
            pdf_buffer = generate_threat_report_pdf(
                test_threats,
                test_alerts,
                test_stats,
                include_charts=True
            )
            
            # Verify PDF is valid
            pdf_data = pdf_buffer.getvalue()
            if pdf_data[:4] != b'%PDF':
                raise ValueError("Invalid PDF header")
            
            results["successful"] += 1
            
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "iteration": i + 1,
                "error": str(e),
                "traceback": traceback.format_exc()[:500]
            })
        
        elapsed_ms = (time.time() - start_time) * 1000
        results["timing_ms"].append(round(elapsed_ms, 2))
    
    # Calculate statistics
    if results["timing_ms"]:
        results["avg_time_ms"] = round(sum(results["timing_ms"]) / len(results["timing_ms"]), 2)
        results["min_time_ms"] = min(results["timing_ms"])
        results["max_time_ms"] = max(results["timing_ms"])
    
    results["success_rate"] = f"{(results['successful'] / iterations) * 100:.1f}%"
    
    # Only keep first 5 errors to avoid huge response
    results["errors"] = results["errors"][:5]
    # Remove individual timings if too many
    if len(results["timing_ms"]) > 20:
        results["timing_ms"] = results["timing_ms"][:20] + ["..."]
    
    return results


@router.get("/health")
async def report_health():
    """Check PDF generation health"""
    try:
        # Generate a minimal PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [Paragraph("Health Check", styles['Heading1'])]
        doc.build(story)
        
        pdf_data = buffer.getvalue()
        
        return {
            "status": "healthy",
            "pdf_generation": "working",
            "pdf_size_bytes": len(pdf_data),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
