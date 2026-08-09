#!/usr/bin/env python3
"""
Seraph AI Defense - Full Feature Test
=======================================
Comprehensive end-to-end test of all major features.
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple

BASE_URL = "http://localhost:8001/api"

class FeatureTest:
    def __init__(self):
        self.token = None
        self.results = []
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Forwarded-For": "127.0.0.1"
        })
    
    def auth(self):
        """Authenticate and get token"""
        email = f"feature_test_{int(time.time())}@test.com"
        r = self.session.post(f"{BASE_URL}/auth/register", json={
            "email": email, "password": "Test123!", "name": "Feature Test"
        })
        if r.status_code == 200:
            self.token = r.json().get("access_token")
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            return True
        return False
    
    def test(self, name: str, method: str, endpoint: str, data: dict = None, 
             expected: list = None) -> Tuple[bool, int]:
        """Run a single test"""
        expected = expected or [200, 201]
        url = f"{BASE_URL}{endpoint}"
        try:
            if method == "GET":
                r = self.session.get(url, timeout=30)
            elif method == "POST":
                r = self.session.post(url, json=data or {}, timeout=30)
            elif method == "PATCH":
                r = self.session.patch(url, json=data or {}, timeout=30)
            else:
                r = self.session.get(url, timeout=30)
            
            success = r.status_code in expected
            self.results.append((name, success, r.status_code))
            return success, r.status_code
        except Exception as e:
            self.results.append((name, False, 0))
            return False, 0
    
    def run_all(self):
        """Run all feature tests"""
        print("=" * 70)
        print("SERAPH AI DEFENSE - FULL FEATURE TEST")
        print("=" * 70)
        print(f"Started: {datetime.now().isoformat()}")
        print(f"Target: {BASE_URL}")
        print()
        
        if not self.auth():
            print("✗ Authentication failed!")
            return
        print("✓ Authenticated successfully")
        print()
        
        # =====================================================================
        # CORE SECURITY FEATURES
        # =====================================================================
        print("=== CORE SECURITY ===")
        self.test("Health Check", "GET", "/health")
        self.test("API Info", "GET", "/")
        self.test("Dashboard Stats", "GET", "/dashboard/stats")
        self.test("Current User", "GET", "/auth/me")
        
        # =====================================================================
        # THREAT MANAGEMENT
        # =====================================================================
        print("\n=== THREAT MANAGEMENT ===")
        self.test("List Threats", "GET", "/threats")
        self.test("Create Threat", "POST", "/threats", {
            "name": "Test Threat", "type": "malware", "severity": "high",
            "source_ip": "10.0.0.1", "target_system": "test",
            "description": "Test threat", "indicators": ["test"]
        })
        self.test("List Alerts", "GET", "/alerts")
        self.test("Threat Intel Feeds", "GET", "/threat-intel/feeds")
        self.test("Threat Response Stats", "GET", "/threat-response/stats")
        
        # =====================================================================
        # ENDPOINT DETECTION & RESPONSE (EDR)
        # =====================================================================
        print("\n=== EDR & ENDPOINT PROTECTION ===")
        self.test("EDR Status", "GET", "/edr/status")
        self.test("EDR USB Devices", "GET", "/edr/usb/devices")
        self.test("EDR FIM Status", "GET", "/edr/fim/status")
        self.test("EDR Telemetry", "GET", "/edr/telemetry")
        self.test("Quarantine List", "GET", "/quarantine")
        self.test("Quarantine Summary", "GET", "/quarantine/summary")
        self.test("Ransomware Status", "GET", "/ransomware/status")
        
        # =====================================================================
        # UNIFIED AGENT MANAGEMENT
        # =====================================================================
        print("\n=== UNIFIED AGENT MANAGEMENT ===")
        self.test("List Agents", "GET", "/unified/agents")
        self.test("Agent Deployments", "GET", "/unified/deployments")
        self.test("Agent Download", "GET", "/agent/download", expected=[200, 307])
        self.test("Agent Commands Types", "GET", "/agent-commands/types")
        self.test("Pending Commands", "GET", "/agent-commands/pending")
        
        # =====================================================================
        # NETWORK SECURITY
        # =====================================================================
        print("\n=== NETWORK SECURITY ===")
        self.test("Network Topology", "GET", "/network/topology")
        self.test("VPN Status", "GET", "/vpn/status")
        self.test("VPN Peers", "GET", "/vpn/peers")
        self.test("Zero Trust Policies", "GET", "/zero-trust/policies")
        self.test("Zero Trust Access Logs", "GET", "/zero-trust/access-logs")
        
        # =====================================================================
        # CLOUD & CONTAINER SECURITY
        # =====================================================================
        print("\n=== CLOUD & CONTAINER SECURITY ===")
        self.test("Container List", "GET", "/containers")
        self.test("Container Stats", "GET", "/containers/stats")
        self.test("Container Scan History", "GET", "/containers/scans/history")
        
        # =====================================================================
        # EMAIL & WEB SECURITY
        # =====================================================================
        print("\n=== EMAIL & WEB SECURITY ===")
        self.test("Email Gateway Stats", "GET", "/email-gateway/stats")
        self.test("Email Gateway Quarantine", "GET", "/email-gateway/quarantine")
        self.test("Email Protection Stats", "GET", "/email-protection/stats")
        self.test("Browser Isolation Sessions", "GET", "/browser-isolation/sessions")
        self.test("Browser Blocked Domains", "GET", "/browser-isolation/blocked-domains")
        
        # =====================================================================
        # MOBILE & MDM SECURITY
        # =====================================================================
        print("\n=== MOBILE & MDM SECURITY ===")
        self.test("MDM Devices", "GET", "/mdm/devices")
        self.test("MDM Policies", "GET", "/mdm/policies")
        self.test("MDM Status", "GET", "/mdm/status")
        self.test("Mobile Devices", "GET", "/mobile-security/devices")
        self.test("Mobile Threats", "GET", "/mobile-security/threats")
        
        # =====================================================================
        # AI/ML THREAT DETECTION
        # =====================================================================
        print("\n=== AI/ML THREAT DETECTION ===")
        self.test("AI Analyses", "GET", "/ai/analyses")
        self.test("ML Predictions", "GET", "/ml/predictions")
        self.test("AATL Summary", "GET", "/ai-threats/aatl/summary")
        self.test("AATL Assessments", "GET", "/ai-threats/aatl/assessments")
        self.test("AATR Summary", "GET", "/ai-threats/aatr/summary")
        self.test("AATR Entries", "GET", "/ai-threats/aatr/entries")
        self.test("AI Defense Status", "GET", "/ai-threats/defense/status")
        
        # =====================================================================
        # DECEPTION TECHNOLOGY
        # =====================================================================
        print("\n=== DECEPTION TECHNOLOGY ===")
        self.test("Honeypots", "GET", "/honeypots")
        self.test("Honey Tokens", "GET", "/honey-tokens")
        self.test("Deception Status", "GET", "/deception/status")
        self.test("Deception Campaigns", "GET", "/deception/campaigns")
        self.test("Deception Events", "GET", "/deception/events")
        
        # =====================================================================
        # SOAR & AUTOMATION
        # =====================================================================
        print("\n=== SOAR & AUTOMATION ===")
        self.test("SOAR Playbooks", "GET", "/soar/playbooks")
        self.test("SOAR Executions", "GET", "/soar/executions")
        self.test("SOAR Stats", "GET", "/soar/stats")
        
        # =====================================================================
        # THREAT HUNTING & CORRELATION
        # =====================================================================
        print("\n=== THREAT HUNTING & CORRELATION ===")
        self.test("Hunting Rules", "GET", "/hunting/rules")
        self.test("Hunting Status", "GET", "/hunting/status")
        self.test("Hunting Tactics", "GET", "/hunting/tactics")
        self.test("Correlation Stats", "GET", "/correlation/stats")
        self.test("Correlation History", "GET", "/correlation/history")
        
        # =====================================================================
        # ANALYTICS & REPORTING
        # =====================================================================
        print("\n=== ANALYTICS & REPORTING ===")
        self.test("Timelines Recent", "GET", "/timelines/recent")
        self.test("Reports Health", "GET", "/reports/health")
        self.test("Audit Logs", "GET", "/audit/logs")
        self.test("Audit Recent", "GET", "/audit/recent")
        self.test("Kibana Dashboards", "GET", "/kibana/dashboards")
        
        # =====================================================================
        # ADVANCED FEATURES
        # =====================================================================
        print("\n=== ADVANCED FEATURES ===")
        self.test("Sandbox Status", "GET", "/advanced/sandbox/status")
        self.test("Quantum Security Status", "GET", "/advanced/quantum/status")
        self.test("MCP Status", "GET", "/advanced/mcp/status")
        self.test("MCP Tools", "GET", "/advanced/mcp/tools")
        self.test("VNS Stats", "GET", "/advanced/vns/stats")
        self.test("AI Dashboard", "GET", "/advanced/dashboard")
        
        # =====================================================================
        # ENTERPRISE & ORCHESTRATION
        # =====================================================================
        print("\n=== ENTERPRISE & ORCHESTRATION ===")
        self.test("Enterprise Status", "GET", "/enterprise/status")
        self.test("Enterprise Tools", "GET", "/enterprise/tools")
        self.test("Swarm Overview", "GET", "/swarm/overview")
        self.test("Swarm Devices", "GET", "/swarm/devices")
        self.test("WebSocket Stats", "GET", "/websocket/stats")
        
        # =====================================================================
        # SECURITY SCANNER INTEGRATIONS
        # =====================================================================
        print("\n=== SECURITY SCANNER INTEGRATIONS ===")
        # Security scanner integrations (tested via existing endpoints)
        # Note: Container scan POST not included as it takes too long (Trivy scan)
        self.test("Container Runtime Events", "GET", "/containers/runtime-events")
        
        # Generate report
        return self.report()
    
    def report(self) -> Dict[str, Any]:
        """Generate test report"""
        total = len(self.results)
        passed = sum(1 for _, s, _ in self.results if s)
        failed = total - passed
        
        print("\n" + "=" * 70)
        print("TEST RESULTS")
        print("=" * 70)
        print(f"Total:  {total}")
        print(f"Passed: {passed} ({100*passed/total:.1f}%)")
        print(f"Failed: {failed}")
        
        if failed > 0:
            print("\n--- FAILURES ---")
            for name, success, code in self.results:
                if not success:
                    print(f"  ✗ {name}: HTTP {code}")
        
        print("\n--- ALL RESULTS ---")
        for name, success, code in self.results:
            status = "✓" if success else "✗"
            print(f"  {status} {name}: {code}")
        
        print("=" * 70)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": 100 * passed / total if total > 0 else 0,
            "results": [{"name": n, "passed": s, "status": c} for n, s, c in self.results]
        }


if __name__ == "__main__":
    test = FeatureTest()
    report = test.run_all()
    
    # Save report
    with open("test_reports/feature_test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    sys.exit(0 if report["failed"] == 0 else 1)
