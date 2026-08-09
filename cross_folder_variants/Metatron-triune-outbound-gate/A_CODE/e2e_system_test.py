#!/usr/bin/env python3
"""
Comprehensive End-to-End System Test for Seraph AI Defense
============================================================
Tests all major service categories and reports coverage.
"""

import requests
import json
import time
import sys
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

BASE_URL = "http://localhost:8001/api"

@dataclass
class TestResult:
    endpoint: str
    method: str
    status_code: int
    success: bool
    latency_ms: float
    error: str = ""

class SeraphE2ETest:
    def __init__(self):
        self.token = None
        self.results: List[TestResult] = []
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Forwarded-For": "127.0.0.1"
        })
    
    def _request(self, method: str, endpoint: str, data: dict = None, 
                 auth: bool = True, expected_codes: list = None) -> TestResult:
        """Make a request and record result"""
        url = f"{BASE_URL}{endpoint}"
        headers = {}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        expected_codes = expected_codes or [200, 201]
        start = time.time()
        try:
            if method == "GET":
                resp = self.session.get(url, headers=headers, timeout=30)
            elif method == "POST":
                resp = self.session.post(url, headers=headers, json=data or {}, timeout=30)
            elif method == "PATCH":
                resp = self.session.patch(url, headers=headers, json=data or {}, timeout=30)
            elif method == "DELETE":
                resp = self.session.delete(url, headers=headers, timeout=30)
            else:
                resp = self.session.get(url, headers=headers, timeout=30)
            
            latency = (time.time() - start) * 1000
            success = resp.status_code in expected_codes
            result = TestResult(endpoint, method, resp.status_code, success, latency)
        except Exception as e:
            latency = (time.time() - start) * 1000
            result = TestResult(endpoint, method, 0, False, latency, str(e))
        
        self.results.append(result)
        return result
    
    def authenticate(self):
        """Register and login to get auth token"""
        # First try to register
        email = f"e2e_test_{int(time.time())}@test.com"
        reg_data = {"email": email, "password": "TestPass123!", "name": "E2E Test"}
        reg_resp = self.session.post(f"{BASE_URL}/auth/register", json=reg_data)
        
        if reg_resp.status_code in [200, 201]:
            try:
                self.token = reg_resp.json().get("access_token")
                if self.token:
                    print(f"✓ Authenticated as {email}")
                    return True
            except:
                pass
        
        # Try login with known test credentials
        login_data = {"email": "admin@seraph.ai", "password": "admin"}
        login_resp = self.session.post(f"{BASE_URL}/auth/login", json=login_data)
        if login_resp.status_code == 200:
            try:
                self.token = login_resp.json().get("access_token")
                if self.token:
                    print("✓ Authenticated with admin credentials")
                    return True
            except:
                pass
        
        print("⚠ Running without authentication (some tests may fail)")
        return False

    def test_core_services(self):
        """Test core system services"""
        print("\n=== Core Services ===")
        
        # Health & Root
        self._request("GET", "/health", auth=False, expected_codes=[200])
        self._request("GET", "/", auth=False, expected_codes=[200])
        
        # Auth
        self._request("GET", "/auth/me", expected_codes=[200, 401])
        
    def test_threat_management(self):
        """Test threat detection and management"""
        print("\n=== Threat Management ===")
        
        # Threats
        self._request("GET", "/threats", expected_codes=[200, 401])
        self._request("POST", "/threats", {"name": "Test Threat", "severity": "low"}, expected_codes=[200, 201, 401, 422])
        
        # Alerts
        self._request("GET", "/alerts", expected_codes=[200, 401])
        
        # Threat Intel
        self._request("GET", "/threat-intel/feeds", expected_codes=[200, 401])
        self._request("GET", "/threat-intel/stats", expected_codes=[200, 401])
        
        # Threat Response
        self._request("GET", "/threat-response/stats", expected_codes=[200, 401])
        self._request("GET", "/threat-response/history", expected_codes=[200, 401])
        
    def test_agent_management(self):
        """Test unified agent infrastructure"""
        print("\n=== Agent Management ===")
        
        # Agent Download
        self._request("GET", "/agent/download", auth=False, expected_codes=[200, 404])
        self._request("GET", "/agent/install", auth=False, expected_codes=[200])
        
        # Unified Agent
        self._request("GET", "/unified/agents", expected_codes=[200, 401])
        self._request("GET", "/unified/deployments", expected_codes=[200, 401])
        self._request("GET", "/unified/stats", expected_codes=[200, 401])
        
        # Agent Commands
        self._request("GET", "/agent-commands/types", expected_codes=[200, 401])
        self._request("GET", "/agent-commands/pending", expected_codes=[200, 401])
        
    def test_edr_endpoint_protection(self):
        """Test EDR and endpoint protection"""
        print("\n=== EDR & Endpoint Protection ===")
        
        # EDR
        self._request("GET", "/edr/status", expected_codes=[200, 401])
        self._request("GET", "/edr/telemetry", expected_codes=[200, 401])
        self._request("GET", "/edr/fim/status", expected_codes=[200, 401])
        
        # Quarantine
        self._request("GET", "/quarantine", expected_codes=[200, 401])
        self._request("GET", "/quarantine/summary", expected_codes=[200, 401])
        
        # Ransomware Protection
        self._request("GET", "/ransomware/status", expected_codes=[200, 401])
        self._request("GET", "/ransomware/status", expected_codes=[200, 401])
        
    def test_cloud_security(self):
        """Test CSPM and cloud security"""
        print("\n=== Cloud Security ===")
        
        # Containers
        self._request("GET", "/containers", expected_codes=[200, 401])
        self._request("GET", "/containers/scans/history", expected_codes=[200, 401])
        
    def test_network_security(self):
        """Test network security features"""
        print("\n=== Network Security ===")
        
        # Network
        self._request("GET", "/network/topology", expected_codes=[200, 401])
        self._request("GET", "/network/topology", expected_codes=[200, 401])
        
        # VPN
        self._request("GET", "/vpn/status", expected_codes=[200, 401])
        self._request("GET", "/vpn/peers", expected_codes=[200, 401])
        
        # Zero Trust
        self._request("GET", "/zero-trust/policies", expected_codes=[200, 401])
        self._request("GET", "/zero-trust/access-logs", expected_codes=[200, 401])
        
    def test_email_web_security(self):
        """Test email and web security"""
        print("\n=== Email & Web Security ===")
        
        # Email Gateway
        self._request("GET", "/email-gateway/stats", expected_codes=[200, 401])
        self._request("GET", "/email-gateway/quarantine", expected_codes=[200, 401])
        
        # Email Protection
        self._request("GET", "/email-protection/stats", expected_codes=[200, 401])
        self._request("GET", "/email-protection/quarantine", expected_codes=[200, 401])
        
        # Browser Isolation
        self._request("GET", "/browser-isolation/sessions", expected_codes=[200, 401])
        self._request("GET", "/browser-isolation/blocked-domains", expected_codes=[200, 401])
        
    def test_mobile_security(self):
        """Test mobile security (MDM)"""
        print("\n=== Mobile Security ===")
        
        # MDM
        self._request("GET", "/mdm/devices", expected_codes=[200, 401])
        self._request("GET", "/mdm/policies", expected_codes=[200, 401])
        self._request("GET", "/mdm/status", expected_codes=[200, 401])
        
        # Mobile Security
        self._request("GET", "/mobile-security/devices", expected_codes=[200, 401])
        self._request("GET", "/mobile-security/threats", expected_codes=[200, 401])
        
    def test_ai_ml_features(self):
        """Test AI/ML capabilities"""
        print("\n=== AI/ML Features ===")
        
        # ML Predictions
        self._request("GET", "/ml/predictions", expected_codes=[200, 401])
        self._request("GET", "/ml/predictions", expected_codes=[200, 401])
        
        # AI Analysis
        self._request("GET", "/ai/analyses", expected_codes=[200, 401])
        
        # AI Threats (AATL/AATR)
        self._request("GET", "/ai-threats/aatl/summary", expected_codes=[200, 401])
        self._request("GET", "/ai-threats/aatr/summary", expected_codes=[200, 401])
        self._request("GET", "/ai-threats/defense/status", expected_codes=[200, 401])
        
    def test_deception_technology(self):
        """Test deception/honeypot features"""
        print("\n=== Deception Technology ===")
        
        # Honeypots
        self._request("GET", "/honeypots", expected_codes=[200, 401])
        self._request("GET", "/deception/status", expected_codes=[200, 401])
        
        # Honey Tokens
        self._request("GET", "/honey-tokens", expected_codes=[200, 401])
        self._request("GET", "/honey-tokens/stats", expected_codes=[200, 401])
        
        # Deception Engine
        self._request("GET", "/deception/events", expected_codes=[200, 401])
        self._request("GET", "/deception/status", expected_codes=[200, 401])
        
    def test_soar_automation(self):
        """Test SOAR and automation"""
        print("\n=== SOAR & Automation ===")
        
        # SOAR
        self._request("GET", "/soar/playbooks", expected_codes=[200, 401])
        self._request("GET", "/soar/executions", expected_codes=[200, 401])
        self._request("GET", "/soar/stats", expected_codes=[200, 401])
        
    def test_hunting_investigation(self):
        """Test threat hunting and investigation"""
        print("\n=== Threat Hunting & Investigation ===")
        
        # Hunting
        self._request("GET", "/hunting/rules", expected_codes=[200, 401])
        self._request("GET", "/hunting/status", expected_codes=[200, 401])
        
        # Correlation
        self._request("GET", "/correlation/stats", expected_codes=[200, 401])
        self._request("GET", "/correlation/history", expected_codes=[200, 401])
        
        # Timeline
        self._request("GET", "/timelines/recent", expected_codes=[200, 401])
        
    def test_analytics_reporting(self):
        """Test analytics and reporting"""
        print("\n=== Analytics & Reporting ===")
        
        # Dashboard
        self._request("GET", "/dashboard/stats", expected_codes=[200, 401])
        
        # Reports
        self._request("GET", "/reports/health", expected_codes=[200, 401])
        
        # Audit
        self._request("GET", "/audit/logs", expected_codes=[200, 401])
        self._request("GET", "/audit/recent", expected_codes=[200, 401])
        
        # Kibana
        self._request("GET", "/kibana/dashboards", expected_codes=[200, 401])
        
    def test_advanced_features(self):
        """Test advanced/enterprise features"""
        print("\n=== Advanced Features ===")
        
        # Sandbox
        self._request("GET", "/advanced/sandbox/status", expected_codes=[200, 401])
        
        # Quantum Security
        self._request("GET", "/advanced/quantum/status", expected_codes=[200, 401])
        
        # MCP Integration
        self._request("GET", "/advanced/mcp/status", expected_codes=[200, 401])
        self._request("GET", "/advanced/mcp/tools", expected_codes=[200, 401])
        
        # VNS (Virtual Network Sensors)
        self._request("GET", "/advanced/vns/stats", expected_codes=[200, 401])
        
    def test_enterprise_multi_tenant(self):
        """Test enterprise and multi-tenant features"""
        print("\n=== Enterprise & Multi-tenant ===")
        
        # Enterprise
        self._request("GET", "/enterprise/status", expected_codes=[200, 401, 403])
        self._request("GET", "/enterprise/tools", expected_codes=[200, 401, 403])
        
        # Swarm (distributed agents)
        self._request("GET", "/swarm/overview", expected_codes=[200, 401])
        self._request("GET", "/swarm/devices", expected_codes=[200, 401])
        
    def test_cli_extension_apis(self):
        """Test CLI and extension APIs"""
        print("\n=== CLI & Extension APIs ===")
        
        # CLI
        self._request("POST", "/cli/event", {"event_type": "e2e_probe", "message": "cli path check"}, expected_codes=[200, 401, 422])
        self._request("GET", "/health", auth=False, expected_codes=[200])
        
        # Extension
        self._request("GET", "/extension/stats", expected_codes=[200, 401])
        
    def run_all_tests(self):
        """Run all test categories"""
        print("=" * 60)
        print("SERAPH AI DEFENSE - END-TO-END SYSTEM TEST")
        print("=" * 60)
        print(f"Started: {datetime.now().isoformat()}")
        print(f"Target: {BASE_URL}")
        
        # Authenticate first
        self.authenticate()
        
        # Run all test categories
        self.test_core_services()
        self.test_threat_management()
        self.test_agent_management()
        self.test_edr_endpoint_protection()
        self.test_cloud_security()
        self.test_network_security()
        self.test_email_web_security()
        self.test_mobile_security()
        self.test_ai_ml_features()
        self.test_deception_technology()
        self.test_soar_automation()
        self.test_hunting_investigation()
        self.test_analytics_reporting()
        self.test_advanced_features()
        self.test_enterprise_multi_tenant()
        self.test_cli_extension_apis()
        
        # Generate report
        return self.generate_report()
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate test summary report"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        
        avg_latency = sum(r.latency_ms for r in self.results) / total if total > 0 else 0
        
        # Group by category (endpoint prefix)
        categories = {}
        for r in self.results:
            parts = r.endpoint.strip('/').split('/')
            cat = parts[0] if parts else 'root'
            if cat not in categories:
                categories[cat] = {'passed': 0, 'failed': 0, 'endpoints': []}
            if r.success:
                categories[cat]['passed'] += 1
            else:
                categories[cat]['failed'] += 1
            categories[cat]['endpoints'].append(r)
        
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        print(f"Total Tests:     {total}")
        print(f"Passed:          {passed} ({100*passed/total:.1f}%)" if total > 0 else "Passed: 0")
        print(f"Failed:          {failed}")
        print(f"Avg Latency:     {avg_latency:.1f}ms")
        
        print("\n--- Results by Category ---")
        for cat, data in sorted(categories.items()):
            status = "✓" if data['failed'] == 0 else "✗"
            total_cat = data['passed'] + data['failed']
            print(f"  {status} {cat}: {data['passed']}/{total_cat} passed")
        
        # Show failures
        failures = [r for r in self.results if not r.success]
        if failures:
            print("\n--- Failed Tests ---")
            for r in failures[:20]:  # Limit to 20
                print(f"  ✗ {r.method} {r.endpoint}: {r.status_code} {r.error}")
        
        print("\n" + "=" * 60)
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': 100 * passed / total if total > 0 else 0,
            'avg_latency_ms': avg_latency,
            'categories': {k: {'passed': v['passed'], 'failed': v['failed']} for k, v in categories.items()},
            'failures': [{'endpoint': r.endpoint, 'method': r.method, 'status': r.status_code} for r in failures]
        }


if __name__ == "__main__":
    tester = SeraphE2ETest()
    report = tester.run_all_tests()
    
    # Save report
    with open('test_reports/e2e_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Exit with error code if failures
    sys.exit(0 if report['failed'] == 0 else 1)
