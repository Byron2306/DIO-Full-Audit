#!/usr/bin/env python3
"""
High-level threat simulation E2E test for Seraph/Metatron.

This suite validates end-to-end pipeline movement:
ingest -> detection -> governance queue -> approval -> executor -> feedback surfaces.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8001/api").rstrip("/")
REPORT_DIR = Path("test_reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JSON_REPORT = REPORT_DIR / "threat_pipeline_e2e_report.json"
MD_REPORT = REPORT_DIR / "threat_pipeline_e2e_report.md"
SCORE_JSON_REPORT = REPORT_DIR / "system_scoring_report.json"
SCORE_MD_REPORT = REPORT_DIR / "system_scoring_report.md"
AGENT_ENROLLMENT_KEY = "dev-agent-secret-change-in-production"


@dataclass
class StepResult:
    name: str
    passed: bool
    status_code: int
    latency_ms: float
    details: str = ""


class ThreatPipelineE2E:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.results: List[StepResult] = []
        self.artifacts: Dict[str, Any] = {}
        self.domain_summary: Dict[str, Dict[str, int]] = {}

    def _track_domain(self, domain: Optional[str], passed: bool) -> None:
        if not domain:
            return
        stats = self.domain_summary.setdefault(domain, {"total": 0, "passed": 0, "failed": 0})
        stats["total"] += 1
        if passed:
            stats["passed"] += 1
        else:
            stats["failed"] += 1

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        name: str,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_codes: Optional[List[int]] = None,
        domain: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        expected = expected_codes or [200, 201]
        merged_headers = self._auth_headers()
        if headers:
            merged_headers.update(headers)
        url = f"{BASE_URL}{path}"
        started = time.perf_counter()
        resp = self.session.request(method, url, json=json_body, params=params, headers=merged_headers, timeout=45)
        latency_ms = (time.perf_counter() - started) * 1000
        passed = resp.status_code in expected
        details = ""
        if not passed:
            details = resp.text[:300]
        self.results.append(
            StepResult(
                name=name,
                passed=passed,
                status_code=resp.status_code,
                latency_ms=latency_ms,
                details=details,
            )
        )
        self._track_domain(domain, passed)
        return resp

    def _register_and_login(self) -> None:
        suffix = uuid.uuid4().hex[:8]
        email = f"threat-e2e-{suffix}@local"
        password = "ChangeMe123!"
        self._request(
            "register_user",
            "POST",
            "/auth/register",
            json_body={"email": email, "password": password, "name": "Threat E2E"},
            expected_codes=[200, 201, 400],
            domain="core_auth",
        )
        login = self._request(
            "login_user",
            "POST",
            "/auth/login",
            json_body={"email": email, "password": password},
            expected_codes=[200],
            domain="core_auth",
        )
        data = login.json()
        self.token = data.get("access_token")
        if not self.token:
            raise RuntimeError("Authentication failed: access_token missing")
        self.artifacts["user_email"] = email

    def _simulate_ingest_and_detection(self) -> None:
        # 1) Threat ingestion
        threat_resp = self._request(
            "create_threat",
            "POST",
            "/threats",
            json_body={
                "name": f"Ransomware Campaign {uuid.uuid4().hex[:6]}",
                "type": "ransomware",
                "severity": "critical",
                "source_ip": "203.0.113.55",
                "target_system": "finance-workstation-07",
                "description": "Simulated multi-stage threat for E2E pipeline test",
                "indicators": ["suspicious_ps_exec", "mass_file_rename", "shadowcopy_delete"],
            },
            expected_codes=[200, 201],
            domain="threat_management",
        )
        threat = threat_resp.json()
        self.artifacts["threat_id"] = threat.get("id")

        # 2) AI CLI behavior analysis (AATL)
        aatl_resp = self._request(
            "aatl_analyze_cli_session",
            "POST",
            "/ai-threats/aatl/analyze",
            json_body={
                "host_id": "finance-workstation-07",
                "session_id": f"sess-{uuid.uuid4().hex[:8]}",
                "commands": [
                    {"command": "whoami", "ts": datetime.now(timezone.utc).isoformat()},
                    {"command": "nltest /dclist:corp.local", "ts": datetime.now(timezone.utc).isoformat()},
                    {"command": "vssadmin delete shadows /all /quiet", "ts": datetime.now(timezone.utc).isoformat()},
                    {"command": "powershell -enc SQBFAFgA", "ts": datetime.now(timezone.utc).isoformat()},
                ],
            },
            expected_codes=[200, 201],
            domain="ai_ml",
        )
        self.artifacts["aatl_response"] = aatl_resp.json()

        # 3) Email threat detection
        email_resp = self._request(
            "email_protection_analyze",
            "POST",
            "/email-protection/analyze",
            json_body={
                "sender": "accounts-payable@lookalike-vendor-secure.com",
                "recipient": "finance-team@corp.local",
                "subject": "Urgent wire transfer approval needed",
                "body": "Please open attachment and complete payment today.",
                "attachments": [{"filename": "wire-transfer.xlsm", "size": 124000}],
                "sender_ip": "198.51.100.23",
            },
            expected_codes=[200, 201],
            domain="email_web",
        )
        email_data = email_resp.json()
        self.artifacts["email_assessment_id"] = email_data.get("assessment_id")
        self.artifacts["email_threat_score"] = email_data.get("threat_score")

        # 4) Browser isolation session
        browser_resp = self._request(
            "browser_isolation_session_create",
            "POST",
            "/browser-isolation/sessions",
            json_body={"url": "https://suspicious-auth-gateway.invalid/login", "isolation_mode": "full"},
            expected_codes=[200, 201],
            domain="email_web",
        )
        browser_data = browser_resp.json()
        self.artifacts["browser_session_id"] = browser_data.get("session_id")

        # 5) Mobile threat signal
        device_name = f"e2e-mobile-{uuid.uuid4().hex[:6]}"
        mobile_resp = self._request(
            "mobile_register_device",
            "POST",
            "/mobile-security/devices",
            json_body={
                "device_name": device_name,
                "platform": "android",
                "os_version": "14",
                "model": "Pixel 8",
                "serial_number": f"SN-{uuid.uuid4().hex[:10]}",
                "user_email": "analyst@corp.local",
            },
            expected_codes=[200, 201],
            domain="mobile_mdm",
        )
        mobile_data = mobile_resp.json()
        device_id = mobile_data.get("device_id")
        self.artifacts["mobile_device_id"] = device_id
        if device_id:
            self._request(
                "mobile_update_device_status",
                "PUT",
                f"/mobile-security/devices/{device_id}/status",
                json_body={
                    "is_jailbroken": True,
                    "is_encrypted": False,
                    "has_passcode": False,
                    "mdm_enrolled": False,
                    "network_info": {"wifi": "rogue-ap", "mitm_detected": True},
                },
                expected_codes=[200],
                domain="mobile_mdm",
            )

    def _simulate_governed_response_pipeline(self) -> None:
        # Baseline governance pending count
        pending_before_resp = self._request(
            "governance_pending_before",
            "GET",
            "/governance/decisions/pending?limit=100",
            expected_codes=[200],
            domain="governance",
        )
        pending_before = int((pending_before_resp.json() or {}).get("count", 0))
        self.artifacts["pending_before"] = pending_before

        # 6) Register an agent via enrollment-key path
        agent_id = f"e2e-agent-{uuid.uuid4().hex[:8]}"
        self.artifacts["agent_id"] = agent_id
        reg_resp = self._request(
            "unified_agent_register",
            "POST",
            "/unified/agents/register",
            json_body={
                "agent_id": agent_id,
                "platform": "linux",
                "hostname": "finance-workstation-07",
                "ip_address": "10.10.20.15",
                "version": "7.0.0",
                "capabilities": ["process", "network", "registry", "edr"],
            },
            headers={"x-enrollment-key": AGENT_ENROLLMENT_KEY},
            expected_codes=[200, 201],
            domain="endpoint_unified_agent",
        )
        reg_data = reg_resp.json()
        self.artifacts["agent_auth_token_present"] = bool(reg_data.get("auth_token"))

        # 7) Heartbeat telemetry submission
        self._request(
            "unified_agent_heartbeat",
            "POST",
            f"/unified/agents/{agent_id}/heartbeat",
            json_body={
                "agent_id": agent_id,
                "status": "online",
                "cpu_usage": 81,
                "memory_usage": 77,
                "threat_count": 3,
                "network_connections": 124,
                "alerts": [
                    {"type": "privilege_escalation", "severity": "high"},
                    {"type": "ransomware_behavior", "severity": "critical"},
                ],
                "monitors": {
                    "registry": {"events": 12, "detections": 2, "enabled": True},
                    "process_tree": {"events": 34, "detections": 3, "enabled": True},
                    "firewall": {"events": 15, "detections": 2, "enabled": True},
                },
            },
            headers={"x-enrollment-key": AGENT_ENROLLMENT_KEY},
            expected_codes=[200],
            domain="endpoint_unified_agent",
        )

        # 8) Propose high-impact remediation -> outbound gate / governance queue
        proposal_resp = self._request(
            "remediation_propose_block_ip",
            "POST",
            f"/unified/agents/{agent_id}/remediation/propose",
            json_body={
                "action": "block_ip",
                "parameters": {"ip": "203.0.113.55"},
                "priority": "critical",
                "reason": "Threat simulation escalation",
            },
            headers={"x-enrollment-key": AGENT_ENROLLMENT_KEY},
            expected_codes=[200],
            domain="governance",
        )
        proposal = proposal_resp.json()
        decision_id = proposal.get("decision_id")
        self.artifacts["decision_id"] = decision_id
        self.artifacts["proposal_status"] = proposal.get("status")

        # 9) Verify pending increased or decision is visible
        pending_after_resp = self._request(
            "governance_pending_after",
            "GET",
            "/governance/decisions/pending?limit=200",
            expected_codes=[200],
            domain="governance",
        )
        pending_after_payload = pending_after_resp.json() or {}
        pending_after = int(pending_after_payload.get("count", 0))
        self.artifacts["pending_after"] = pending_after
        items = pending_after_payload.get("items") or []
        self.artifacts["decision_present_in_pending"] = bool(
            decision_id and any(item.get("decision_id") == decision_id for item in items)
        )

        # 10) Approve decision and run executor to complete movement
        if decision_id:
            approve_resp = self._request(
                "governance_approve_decision",
                "POST",
                f"/governance/decisions/{decision_id}/approve",
                json_body={"reason": "E2E threat pipeline approval"},
                expected_codes=[200],
                domain="governance",
            )
            approve_payload = approve_resp.json() or {}
            summary = approve_payload.get("execution_summary") or {}
            self.artifacts["approve_execution_summary"] = summary

        exec_resp = self._request(
            "governance_executor_run_once",
            "POST",
            "/governance/executor/run-once",
            json_body={"limit": 100},
            expected_codes=[200],
            domain="governance",
        )
        self.artifacts["executor_summary"] = (exec_resp.json() or {}).get("summary")

    def _approve_decision_if_present(self, decision_id: Optional[str], reason: str) -> None:
        if not decision_id:
            return
        self._request(
            f"governance_approve_{decision_id}",
            "POST",
            f"/governance/decisions/{decision_id}/approve",
            json_body={"reason": reason},
            expected_codes=[200],
            domain="governance",
        )

    def _simulate_additional_domain_threats(self) -> None:
        scenario_session = f"sess-{uuid.uuid4().hex[:8]}"

        # Network response domain
        block_ip_resp = self._request(
            "threat_response_block_ip",
            "POST",
            "/threat-response/block-ip",
            json_body={"ip": "198.51.100.200", "reason": "multi-domain simulation", "duration_hours": 4},
            expected_codes=[200],
            domain="network_response",
        )
        block_ip_data = block_ip_resp.json() or {}
        self._approve_decision_if_present(block_ip_data.get("decision_id"), "E2E network response approval")

        # Zero-trust domain
        zt_device_id = f"zt-{uuid.uuid4().hex[:6]}"
        self._request(
            "zero_trust_register_device",
            "POST",
            "/zero-trust/devices",
            json_body={
                "device_id": zt_device_id,
                "device_name": "E2E Finance Laptop",
                "device_type": "laptop",
                "os_info": {"name": "Windows", "version": "11"},
                "security_posture": {"edr": True, "disk_encryption": True, "secure_boot": True},
            },
            expected_codes=[200, 201],
            domain="zero_trust",
        )
        self._request(
            "zero_trust_evaluate_access",
            "POST",
            "/zero-trust/evaluate",
            json_body={
                "resource": "finance-app",
                "device_id": zt_device_id,
                "auth_method": "mfa",
                "anomaly_score": 0.72,
                "recent_incidents": 1,
            },
            expected_codes=[200],
            domain="zero_trust",
        )
        self._request(
            "zero_trust_trust_score",
            "POST",
            "/zero-trust/trust-score",
            json_body={
                "resource": "crown-jewel-db",
                "device_id": zt_device_id,
                "auth_method": "password",
                "anomaly_score": 0.18,
                "recent_incidents": 0,
            },
            expected_codes=[200],
            domain="zero_trust",
        )

        # VPN domain (queued through governance)
        vpn_peer_name = f"e2e-peer-{uuid.uuid4().hex[:4]}"
        vpn_peer_resp = self._request(
            "vpn_add_peer",
            "POST",
            "/vpn/peers",
            json_body={"name": vpn_peer_name},
            expected_codes=[200],
            domain="vpn",
        )
        self._approve_decision_if_present((vpn_peer_resp.json() or {}).get("decision_id"), "E2E VPN peer approval")
        vpn_start_resp = self._request(
            "vpn_start",
            "POST",
            "/vpn/start",
            json_body={},
            expected_codes=[200],
            domain="vpn",
        )
        self._approve_decision_if_present((vpn_start_resp.json() or {}).get("decision_id"), "E2E VPN start approval")
        vpn_stop_resp = self._request(
            "vpn_stop",
            "POST",
            "/vpn/stop",
            json_body={},
            expected_codes=[200],
            domain="vpn",
        )
        self._approve_decision_if_present((vpn_stop_resp.json() or {}).get("decision_id"), "E2E VPN stop approval")

        # Deception and traps
        self._request(
            "deception_assess_risk",
            "POST",
            "/deception/assess",
            json_body={
                "ip": "203.0.113.90",
                "path": "/admin/login",
                "headers": {"user-agent": "sqlmap/1.8"},
                "behavior_flags": {"credential_stuffing": True, "rapid_retries": True},
            },
            expected_codes=[200],
            domain="deception",
        )
        self._request(
            "deception_decoy_interaction",
            "POST",
            "/deception/decoy/interaction",
            json_body={
                "ip": "203.0.113.90",
                "decoy_type": "api_key",
                "decoy_id": f"decoy-{uuid.uuid4().hex[:6]}",
                "headers": {"user-agent": "curl/8.0"},
            },
            expected_codes=[200],
            domain="deception",
        )

        # Threat intel and hunting support
        self._request(
            "threat_intel_check_indicator",
            "POST",
            "/threat-intel/check",
            json_body={"value": "198.51.100.200", "ioc_type": "ip"},
            expected_codes=[200],
            domain="threat_intel",
        )

        # Honey token and honeypot
        honey_create_resp = self._request(
            "honey_token_create_api_key",
            "POST",
            "/honey-tokens",
            json_body={
                "name": "E2E API honey token",
                "token_type": "api_key",
                "description": "multi-domain e2e simulation",
                "location": "e2e-ci",
            },
            expected_codes=[200, 201],
            domain="deception",
        )
        honey_token_id = (honey_create_resp.json() or {}).get("id")
        if honey_token_id:
            self._request(
                "honey_token_toggle",
                "POST",
                f"/honey-tokens/{honey_token_id}/toggle",
                expected_codes=[200],
                domain="deception",
            )
        honeypot_resp = self._request(
            "honeypot_create",
            "POST",
            "/honeypots",
            json_body={
                "name": f"e2e-ssh-{uuid.uuid4().hex[:4]}",
                "type": "ssh",
                "ip": "10.22.33.44",
                "port": 2222,
                "description": "E2E honeypot simulation",
            },
            expected_codes=[200, 201],
            domain="deception",
        )
        honeypot_id = (honeypot_resp.json() or {}).get("id")
        if honeypot_id:
            self._request(
                "honeypot_record_interaction",
                "POST",
                f"/honeypots/{honeypot_id}/interaction",
                params={
                    "source_ip": "198.51.100.201",
                    "action": "login_attempt",
                },
                expected_codes=[200, 201, 422],
                domain="deception",
            )

        # SOAR simulation trigger
        self._request(
            "soar_trigger_playbook",
            "POST",
            "/soar/trigger",
            json_body={
                "trigger_type": "threat_detected",
                "severity": "high",
                "source_ip": "198.51.100.200",
                "agent_id": self.artifacts.get("agent_id", "agent-e2e"),
                "confidence": "0.93",
                "extra": {"simulation": "multi-domain"},
            },
            expected_codes=[200],
            domain="soar",
        )

        # Enterprise policy evaluation domain
        self._request(
            "enterprise_policy_evaluate",
            "POST",
            "/enterprise/policy/evaluate",
            json_body={
                "principal": "agent:e2e-agent",
                "action": "isolate_endpoint",
                "targets": ["host:finance-workstation-07"],
                "trust_state": "degraded",
                "role": "agent",
                "evidence_confidence": 0.88,
            },
            expected_codes=[200],
            domain="enterprise_policy",
        )

        # Cloud and container domain
        self._request(
            "cspm_scan_trigger",
            "POST",
            "/v1/cspm/scan",
            json_body={
                "providers": ["aws"],
                "regions": ["us-east-1"],
                "resource_types": ["virtual_machine"],
                "severity_filter": ["high"],
            },
            expected_codes=[200],
            domain="cloud_cspm",
        )
        self._request(
            "container_image_scan",
            "POST",
            "/containers/scan",
            json_body={"image_name": "nginx:latest", "force": False},
            expected_codes=[200],
            domain="container_security",
        )

        # Quantum cryptography domain
        dilithium_resp = self._request(
            "quantum_generate_dilithium_keypair",
            "POST",
            "/advanced/quantum/keypair/dilithium",
            expected_codes=[200],
            domain="quantum_security",
        )
        dilithium = dilithium_resp.json() or {}
        dilithium_key_id = dilithium.get("key_id")
        signature_id: Optional[str] = None
        if dilithium_key_id:
            sign_resp = self._request(
                "quantum_sign",
                "POST",
                "/advanced/quantum/sign",
                json_body={"key_id": dilithium_key_id, "data": "multi-domain-threat-simulation"},
                expected_codes=[200],
                domain="quantum_security",
            )
            sign_data = sign_resp.json() or {}
            signature_id = sign_data.get("signature_id")
            if signature_id:
                self._request(
                    "quantum_verify_stored_signature",
                    "POST",
                    "/advanced/quantum/verify/stored",
                    json_body={"signature_id": signature_id, "data": "multi-domain-threat-simulation"},
                    expected_codes=[200],
                    domain="quantum_security",
                )
        self._request(
            "quantum_hash_data",
            "POST",
            "/advanced/quantum/hash",
            json_body={"data": "multi-domain-threat-simulation"},
            expected_codes=[200],
            domain="quantum_security",
        )
        kyber_resp = self._request(
            "quantum_generate_kyber_keypair",
            "POST",
            "/advanced/quantum/keypair/kyber",
            expected_codes=[200],
            domain="quantum_security",
        )
        kyber = kyber_resp.json() or {}
        if kyber.get("public_key"):
            self._request(
                "quantum_encrypt_payload",
                "POST",
                "/advanced/quantum/encrypt",
                params={"plaintext": "sensitive-e2e-payload", "recipient_public_key": kyber["public_key"]},
                expected_codes=[200],
                domain="quantum_security",
            )

        # AI defensive action domain
        self._request(
            "ai_defense_escalate",
            "POST",
            "/ai-threats/defense/escalate",
            params={
                "session_id": scenario_session,
                "escalation_level": "high",
                "threat_type": "autonomous_agent",
                "severity": "high",
            },
            expected_codes=[200],
            domain="ai_ml",
        )
        self._request(
            "ai_defense_deploy_decoy",
            "POST",
            "/ai-threats/defense/deploy-decoy",
            json_body=["fake_creds"],
            params={"host_id": "finance-workstation-07", "decoy_type": "credentials", "placement": "filesystem"},
            expected_codes=[200],
            domain="ai_ml",
        )
        self._request(
            "ai_defense_engage_tarpit",
            "POST",
            "/ai-threats/defense/engage-tarpit",
            params={"session_id": scenario_session, "host_id": "finance-workstation-07", "mode": "latency"},
            expected_codes=[200],
            domain="ai_ml",
        )

        # Endpoint/CLI/extension ingest simulation
        self._request(
            "agent_event_ingest",
            "POST",
            "/agent/event",
            json_body={
                "agent_id": self.artifacts.get("agent_id", "agent-e2e"),
                "agent_name": "E2E Agent",
                "event_type": "threat_detected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"severity": "high", "vector": "lateral_movement"},
            },
            expected_codes=[200],
            domain="endpoint_unified_agent",
        )
        self._request(
            "cli_event_ingest",
            "POST",
            "/cli/event",
            json_body={
                "host_id": "finance-workstation-07",
                "session_id": scenario_session,
                "user": "SYSTEM",
                "shell_type": "powershell",
                "command": "vssadmin delete shadows /all /quiet",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            expected_codes=[200],
            domain="endpoint_unified_agent",
        )
        self._request(
            "extension_report_alerts",
            "POST",
            "/extension/report-alerts",
            json_body={"alerts": [{"type": "phishing", "severity": "high", "url": "https://evil.invalid"}]},
            expected_codes=[200],
            domain="email_web",
        )

        # Machine-token boundaries should reject user-token requests.
        self._request(
            "enterprise_machine_token_boundary",
            "POST",
            "/enterprise/telemetry/event",
            json_body={"event_type": "e2e_boundary_check", "severity": "high", "data": {"source": "e2e"}},
            expected_codes=[401],
            domain="enterprise_policy",
        )
        self._request(
            "swarm_cli_machine_token_boundary",
            "POST",
            "/swarm/cli/event",
            json_body={"host_id": "finance-workstation-07", "session_id": scenario_session, "command": "whoami"},
            expected_codes=[401],
            domain="endpoint_unified_agent",
        )

    def _simulate_stack_observability_scenarios(self) -> None:
        # Advanced stack observability checks for IDS/SIEM/sandbox toolchain.
        falco_status = self._request(
            "containers_falco_status",
            "GET",
            "/containers/falco/status",
            expected_codes=[200],
            domain="stack_observability",
        )
        falco_alerts = self._request(
            "containers_falco_alerts",
            "GET",
            "/containers/falco/alerts?limit=10",
            expected_codes=[200],
            domain="stack_observability",
        )
        suricata_stats = self._request(
            "containers_suricata_stats",
            "GET",
            "/containers/suricata/stats",
            expected_codes=[200],
            domain="stack_observability",
        )
        self._request(
            "containers_suricata_alerts",
            "GET",
            "/containers/suricata/alerts?limit=20",
            expected_codes=[200],
            domain="stack_observability",
        )
        zeek_status = self._request(
            "zeek_status",
            "GET",
            "/zeek/status",
            expected_codes=[200],
            domain="stack_observability",
        )
        self._request(
            "zeek_stats",
            "GET",
            "/zeek/stats",
            expected_codes=[200],
            domain="stack_observability",
        )
        self._request(
            "zeek_detection_beaconing",
            "GET",
            "/zeek/detections/beaconing?min_events=3&limit=10",
            expected_codes=[200],
            domain="stack_observability",
        )
        self._request(
            "zeek_detection_dns_tunneling",
            "GET",
            "/zeek/detections/dns-tunneling?min_queries=5&limit=10",
            expected_codes=[200],
            domain="stack_observability",
        )
        elastic_status = self._request(
            "elasticsearch_status",
            "GET",
            "/settings/elasticsearch/status",
            expected_codes=[200],
            domain="stack_observability",
        )
        kibana_status = self._request(
            "kibana_status",
            "GET",
            "/kibana/status",
            expected_codes=[200],
            domain="stack_observability",
        )
        self._request(
            "kibana_dashboards",
            "GET",
            "/kibana/dashboards",
            expected_codes=[200],
            domain="stack_observability",
        )
        sandbox_status = self._request(
            "advanced_sandbox_status",
            "GET",
            "/advanced/sandbox/status",
            expected_codes=[200],
            domain="stack_observability",
        )
        yara_status = self._request(
            "containers_yara_status",
            "GET",
            "/containers/yara/status",
            expected_codes=[200],
            domain="stack_observability",
        )
        self.artifacts["advanced_stack_snapshot"] = {
            "falco_available": bool((falco_status.json() or {}).get("falco_available")),
            "falco_alert_count": int((falco_alerts.json() or {}).get("count", 0)),
            "suricata_available": bool((suricata_stats.json() or {}).get("available")),
            "zeek_available": bool((zeek_status.json() or {}).get("available")),
            "elasticsearch_connected": bool((elastic_status.json() or {}).get("connected")),
            "kibana_configured": bool((kibana_status.json() or {}).get("configured")),
            "sandbox_available": bool((sandbox_status.json() or {}).get("available")),
            "yara_available": bool((yara_status.json() or {}).get("available")),
        }

    def _validate_feedback_surfaces(self) -> None:
        # Correlation and threat intelligence surfaces
        corr_resp = self._request(
            "correlation_all_active",
            "POST",
            "/correlation/all-active",
            expected_codes=[200],
            domain="hunting_correlation",
        )
        corr_payload = corr_resp.json() or {}
        self.artifacts["correlation_summary"] = corr_payload.get("summary")

        # Timeline and audit availability
        timeline_resp = self._request(
            "timeline_recent",
            "GET",
            "/timelines/recent?limit=25",
            expected_codes=[200],
            domain="analytics_reporting",
        )
        timeline_payload = timeline_resp.json() or {}
        self.artifacts["timeline_count"] = int(timeline_payload.get("count", 0))

        audit_resp = self._request(
            "audit_recent",
            "GET",
            "/audit/recent?limit=25",
            expected_codes=[200],
            domain="analytics_reporting",
        )
        try:
            audit_data = audit_resp.json()
            self.artifacts["audit_recent_count"] = len(audit_data) if isinstance(audit_data, list) else 0
        except Exception:
            self.artifacts["audit_recent_count"] = 0

        mitre_resp = self._request(
            "mitre_coverage_snapshot",
            "GET",
            "/mitre/coverage",
            expected_codes=[200],
            domain="mitre_posture",
        )
        mitre_payload = mitre_resp.json() or {}
        self.artifacts["mitre_snapshot"] = {
            "coverage_percent_gte3": mitre_payload.get("coverage_percent_gte3"),
            "covered_score_gte3": mitre_payload.get("covered_score_gte3"),
            "covered_score_gte4": mitre_payload.get("covered_score_gte4"),
            "observed_techniques": mitre_payload.get("observed_techniques"),
        }

    def _pipeline_assertions(self) -> List[StepResult]:
        assertions: List[StepResult] = []

        def add(name: str, ok: bool, details: str = "") -> None:
            assertions.append(StepResult(name=name, passed=ok, status_code=200 if ok else 500, latency_ms=0.0, details=details))

        add(
            "assert_ingest_artifacts_created",
            bool(self.artifacts.get("threat_id") and self.artifacts.get("email_assessment_id") and self.artifacts.get("mobile_device_id")),
            f"artifacts={self.artifacts.get('threat_id')},{self.artifacts.get('email_assessment_id')},{self.artifacts.get('mobile_device_id')}",
        )
        add(
            "assert_governance_queue_created",
            self.artifacts.get("proposal_status") == "queued_for_triune_approval",
            f"proposal_status={self.artifacts.get('proposal_status')}",
        )
        add(
            "assert_decision_visible_or_pending_increased",
            bool(self.artifacts.get("decision_present_in_pending"))
            or int(self.artifacts.get("pending_after", 0)) > int(self.artifacts.get("pending_before", 0)),
            f"pending_before={self.artifacts.get('pending_before')} pending_after={self.artifacts.get('pending_after')} decision_visible={self.artifacts.get('decision_present_in_pending')}",
        )
        summary = self.artifacts.get("approve_execution_summary") or {}
        add(
            "assert_approved_decision_executed",
            int(summary.get("executed", 0)) >= 1 or int(summary.get("processed", 0)) >= 1,
            f"approve_summary={summary}",
        )
        mitre = self.artifacts.get("mitre_snapshot") or {}
        add(
            "assert_mitre_feedback_available",
            bool(mitre.get("covered_score_gte3")) and bool(mitre.get("coverage_percent_gte3")),
            f"mitre_snapshot={mitre}",
        )

        return assertions

    def run(self) -> Dict[str, Any]:
        self._register_and_login()
        self._simulate_ingest_and_detection()
        self._simulate_governed_response_pipeline()
        self._simulate_additional_domain_threats()
        self._simulate_stack_observability_scenarios()
        self._validate_feedback_surfaces()

        assertion_steps = self._pipeline_assertions()
        self.results.extend(assertion_steps)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        pass_rate = (passed / total * 100.0) if total else 0.0
        avg_latency = sum(r.latency_ms for r in self.results if r.latency_ms > 0) / max(
            1, sum(1 for r in self.results if r.latency_ms > 0)
        )
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_url": BASE_URL,
            "total_steps": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "artifacts": self.artifacts,
            "domain_summary": self.domain_summary,
            "steps": [asdict(step) for step in self.results],
        }
        return report


def write_reports(report: Dict[str, Any]) -> None:
    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Threat Pipeline E2E Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Base URL: `{report['base_url']}`",
        f"- Total Steps: **{report['total_steps']}**",
        f"- Passed: **{report['passed']}**",
        f"- Failed: **{report['failed']}**",
        f"- Pass Rate: **{report['pass_rate']}%**",
        f"- Avg Latency: **{report['avg_latency_ms']} ms**",
        "",
        "## Domain Summary",
        "",
        "| Domain | Passed | Total | Pass Rate |",
        "|---|---:|---:|---:|",
    ]
    for domain, stats in sorted((report.get("domain_summary") or {}).items()):
        total = int(stats.get("total", 0))
        passed = int(stats.get("passed", 0))
        rate = (passed / total * 100.0) if total else 0.0
        lines.append(f"| `{domain}` | {passed} | {total} | {rate:.1f}% |")
    lines.extend([
        "",
        "## Pipeline Artifacts",
        "",
        "```json",
        json.dumps(report.get("artifacts", {}), indent=2),
        "```",
        "",
        "## Step Results",
        "",
        "| Step | Result | HTTP | Latency (ms) | Details |",
        "|---|---|---:|---:|---|",
    ])
    for step in report.get("steps", []):
        icon = "PASS" if step["passed"] else "FAIL"
        details = (step.get("details") or "").replace("|", "/")
        lines.append(
            f"| `{step['name']}` | {icon} | {step['status_code']} | {step['latency_ms']:.2f} | {details} |"
        )
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_load_json(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_system_score(report: Dict[str, Any]) -> Dict[str, Any]:
    # Pull complementary suite results if available.
    feature = _safe_load_json(REPORT_DIR / "feature_test_report.json")
    e2e = _safe_load_json(REPORT_DIR / "e2e_report.json")
    openapi = _safe_load_json(REPORT_DIR / "openapi_e2e_report.json")
    mitre = (report.get("artifacts") or {}).get("mitre_snapshot") or {}

    sim_pass_rate = float(report.get("pass_rate") or 0.0)
    domains = report.get("domain_summary") or {}
    domain_total = len(domains)
    domain_full_pass = sum(
        1 for stats in domains.values() if int(stats.get("total", 0)) > 0 and int(stats.get("failed", 0)) == 0
    )
    domain_coverage_rate = (domain_full_pass / domain_total * 100.0) if domain_total else 0.0

    feature_rate = float(feature.get("pass_rate") or 0.0)
    e2e_rate = float(e2e.get("pass_rate") or 0.0)
    methods_total = float(openapi.get("methods_total") or 0.0)
    methods_non_5xx = float(openapi.get("methods_non_5xx") or 0.0)
    openapi_rate = (methods_non_5xx / methods_total * 100.0) if methods_total else 0.0
    mitre_gte3 = float(mitre.get("coverage_percent_gte3") or 0.0)
    mitre_gte4_count = float(mitre.get("covered_score_gte4") or 0.0)

    component_weights = {
        "threat_simulation_quality": 30.0,
        "domain_coverage_breadth": 25.0,
        "full_feature_e2e": 15.0,
        "system_e2e": 15.0,
        "openapi_reachability": 10.0,
        "mitre_operational_posture": 5.0,
    }

    component_raw = {
        "threat_simulation_quality": sim_pass_rate,
        "domain_coverage_breadth": domain_coverage_rate,
        "full_feature_e2e": feature_rate,
        "system_e2e": e2e_rate,
        "openapi_reachability": openapi_rate,
        # Normalize against enterprise target line; cap to 100.
        "mitre_operational_posture": min(100.0, (mitre_gte3 / 70.0) * 100.0) if mitre_gte3 else 0.0,
    }

    weighted_total = 0.0
    components_scored: Dict[str, Dict[str, float]] = {}
    for name, weight in component_weights.items():
        raw = float(component_raw.get(name, 0.0))
        weighted = (raw / 100.0) * weight
        weighted_total += weighted
        components_scored[name] = {"raw_percent": round(raw, 2), "weight": weight, "weighted_points": round(weighted, 2)}

    score_100 = round(weighted_total, 2)
    score_10 = round(score_100 / 10.0, 2)
    rating = (
        "exceptional" if score_10 >= 9.0 else
        "excellent" if score_10 >= 8.0 else
        "strong" if score_10 >= 7.0 else
        "developing"
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score_100": score_100,
        "score_10": score_10,
        "rating": rating,
        "domains_simulated": {
            "total": domain_total,
            "fully_passing": domain_full_pass,
            "coverage_rate_percent": round(domain_coverage_rate, 2),
        },
        "mitre_snapshot": {
            "coverage_percent_gte3": mitre_gte3,
            "covered_score_gte4": mitre_gte4_count,
        },
        "components": components_scored,
        "source_pass_rates": {
            "threat_pipeline_simulation": round(sim_pass_rate, 2),
            "full_feature_e2e": round(feature_rate, 2),
            "system_e2e": round(e2e_rate, 2),
            "openapi_reachability": round(openapi_rate, 2),
        },
    }


def write_system_score(score: Dict[str, Any]) -> None:
    SCORE_JSON_REPORT.write_text(json.dumps(score, indent=2), encoding="utf-8")
    lines = [
        "# System Scoring Report (Post Multi-Domain Simulation)",
        "",
        f"- Generated: {score.get('generated_at')}",
        f"- Composite Score: **{score.get('score_100')}/100** (**{score.get('score_10')}/10**, {score.get('rating')})",
        "",
        "## Domain Simulation Coverage",
        "",
        f"- Domains simulated: **{(score.get('domains_simulated') or {}).get('total', 0)}**",
        f"- Fully passing domains: **{(score.get('domains_simulated') or {}).get('fully_passing', 0)}**",
        f"- Domain coverage rate: **{(score.get('domains_simulated') or {}).get('coverage_rate_percent', 0)}%**",
        "",
        "## MITRE Snapshot",
        "",
        f"- coverage_percent_gte3: **{(score.get('mitre_snapshot') or {}).get('coverage_percent_gte3')}**",
        f"- covered_score_gte4: **{(score.get('mitre_snapshot') or {}).get('covered_score_gte4')}**",
        "",
        "## Weighted Components",
        "",
        "| Component | Raw % | Weight | Weighted Points |",
        "|---|---:|---:|---:|",
    ]
    for name, comp in (score.get("components") or {}).items():
        lines.append(
            f"| `{name}` | {comp.get('raw_percent')} | {comp.get('weight')} | {comp.get('weighted_points')} |"
        )
    SCORE_MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    runner = ThreatPipelineE2E()
    report = runner.run()
    write_reports(report)
    score = build_system_score(report)
    write_system_score(score)
    print(json.dumps(
        {
            "total_steps": report["total_steps"],
            "passed": report["passed"],
            "failed": report["failed"],
            "pass_rate": report["pass_rate"],
            "avg_latency_ms": report["avg_latency_ms"],
            "score_100": score.get("score_100"),
            "score_10": score.get("score_10"),
            "rating": score.get("rating"),
        },
        indent=2,
    ))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
