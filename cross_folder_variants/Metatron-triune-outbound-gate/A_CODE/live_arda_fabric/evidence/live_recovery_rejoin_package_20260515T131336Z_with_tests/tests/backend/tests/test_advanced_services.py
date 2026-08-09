"""
Test Advanced Security Services
================================
Tests for MCP Server, Vector Memory, VNS, Quantum Security, and AI Reasoning endpoints.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://seraph-security.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "test@defender.io"
TEST_PASSWORD = "test123"


class TestAdvancedServicesAuthentication:
    """Test authentication for advanced services"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - cannot run tests")
    
    def test_login_for_advanced_services(self, auth_token):
        """Verify login works for test user"""
        assert auth_token is not None
        print(f"✓ Login successful, token obtained")


class TestAdvancedDashboard:
    """Test /api/advanced/dashboard endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_dashboard_returns_all_service_statuses(self, auth_token):
        """Test /api/advanced/dashboard returns MCP, Memory, VNS, Quantum, AI statuses"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/dashboard",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all service sections are present
        assert "mcp" in data, "Missing MCP section"
        assert "memory" in data, "Missing memory section"
        assert "vns" in data, "Missing VNS section"
        assert "quantum" in data, "Missing quantum section"
        assert "ai" in data, "Missing AI section"
        
        # Verify MCP structure
        assert "tools_registered" in data["mcp"]
        assert "total_executions" in data["mcp"]
        print(f"✓ Dashboard returned all 5 service sections")
        print(f"  - MCP: {data['mcp']['tools_registered']} tools registered")
        print(f"  - Memory: {data['memory'].get('total_entries', 0)} entries")
        print(f"  - VNS: {data['vns'].get('total_flows', 0)} flows")
        print(f"  - Quantum: {data['quantum'].get('mode', 'unknown')} mode")
        print(f"  - AI: Ollama {data['ai'].get('ollama', {}).get('status', 'unknown')}")


class TestMCPServer:
    """Test MCP Server endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_mcp_tools_list(self, auth_token):
        """Test /api/advanced/mcp/tools returns tool registry"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/mcp/tools",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "tools" in data
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) >= 6, "Expected at least 6 built-in MCP tools"
        
        # Verify tool structure
        if len(data["tools"]) > 0:
            tool = data["tools"][0]
            assert "tool_id" in tool
            assert "name" in tool
            assert "category" in tool
            print(f"✓ MCP tools endpoint returned {len(data['tools'])} tools")
            for t in data["tools"][:3]:
                print(f"  - {t['tool_id']}: {t['name']}")
    
    def test_mcp_status(self, auth_token):
        """Test /api/advanced/mcp/status returns server status"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/mcp/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "tools_registered" in data
        assert "total_executions" in data
        assert "message_history_size" in data
        print(f"✓ MCP status: {data['tools_registered']} tools, {data['total_executions']} executions")


class TestVectorMemory:
    """Test Vector Memory endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_memory_store(self, auth_token):
        """Test /api/advanced/memory/store can store a memory entry"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/memory/store",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "content": "TEST_memory_entry: Suspicious PowerShell activity detected on workstation WS-001",
                "namespace": "observations",
                "trust_level": "medium",
                "confidence": 0.75
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "entry_id" in data
        assert "namespace" in data
        assert data["namespace"] == "observations"
        print(f"✓ Memory stored with entry_id: {data['entry_id']}")
    
    def test_memory_search(self, auth_token):
        """Test /api/advanced/memory/search can search stored memories"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/memory/search",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "query": "PowerShell suspicious activity",
                "top_k": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)
        print(f"✓ Memory search returned {data['count']} results")
        if data["count"] > 0:
            print(f"  - Top result similarity: {data['results'][0].get('similarity', 0):.2f}")
    
    def test_memory_stats(self, auth_token):
        """Test /api/advanced/memory/stats returns statistics"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/memory/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total_entries" in data
        assert "total_cases" in data
        assert "embedding_dimension" in data
        print(f"✓ Memory stats: {data['total_entries']} entries, {data['total_cases']} cases")


class TestVNS:
    """Test Virtual Network Sensor endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_vns_record_flow(self, auth_token):
        """Test /api/advanced/vns/flow can record network flows"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/vns/flow",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "src_ip": "192.168.1.100",
                "src_port": 54321,
                "dst_ip": "8.8.8.8",
                "dst_port": 443,
                "protocol": "TCP",
                "bytes_sent": 1500,
                "bytes_recv": 3000
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "flow_id" in data
        assert "direction" in data
        assert "status" in data
        assert "threat_score" in data
        print(f"✓ Flow recorded: {data['flow_id']}, direction: {data['direction']}, threat_score: {data['threat_score']}")
    
    def test_vns_stats(self, auth_token):
        """Test /api/advanced/vns/stats returns VNS statistics"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/vns/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total_flows" in data
        assert "suspicious_flows" in data
        assert "total_dns_queries" in data
        assert "beacon_detections" in data
        print(f"✓ VNS stats: {data['total_flows']} flows, {data['suspicious_flows']} suspicious")
    
    def test_vns_flows_query(self, auth_token):
        """Test /api/advanced/vns/flows returns flow list"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/vns/flows?limit=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "flows" in data
        assert "count" in data
        print(f"✓ VNS flows query returned {data['count']} flows")


class TestQuantumSecurity:
    """Test Quantum Security endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_quantum_status(self, auth_token):
        """Test /api/advanced/quantum/status returns quantum crypto status"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/quantum/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "mode" in data
        assert data["mode"] == "simulation", "Expected simulation mode"
        assert "algorithms" in data
        assert "keypairs" in data
        print(f"✓ Quantum status: mode={data['mode']}, keypairs={data['keypairs'].get('total', 0)}")
    
    def test_quantum_generate_kyber_keypair(self, auth_token):
        """Test /api/advanced/quantum/keypair/kyber generates Kyber key pair"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/quantum/keypair/kyber",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "key_id" in data
        assert "algorithm" in data
        assert "KYBER" in data["algorithm"]
        assert "public_key" in data
        print(f"✓ Generated Kyber keypair: {data['key_id']}, algorithm: {data['algorithm']}")
    
    def test_quantum_generate_dilithium_keypair(self, auth_token):
        """Test /api/advanced/quantum/keypair/dilithium generates Dilithium key pair"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/quantum/keypair/dilithium",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "key_id" in data
        assert "algorithm" in data
        assert "DILITHIUM" in data["algorithm"]
        print(f"✓ Generated Dilithium keypair: {data['key_id']}, algorithm: {data['algorithm']}")


class TestAIReasoning:
    """Test AI Reasoning endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_ai_analyze_threat(self, auth_token):
        """Test /api/advanced/ai/analyze performs threat analysis"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/ai/analyze",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "title": "TEST_Mimikatz Credential Theft Detected",
                "description": "Process mimikatz.exe detected accessing LSASS memory for credential dumping",
                "indicators": ["mimikatz.exe", "lsass.exe"],
                "command_line": "mimikatz.exe sekurlsa::logonpasswords"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "analysis_id" in data
        assert "threat_type" in data
        assert "severity" in data
        assert "risk_score" in data
        assert "recommended_actions" in data
        assert "reasoning_chain" in data
        
        # Should classify as credential theft
        assert data["threat_type"] == "credential_theft" or data["severity"] in ["critical", "high"]
        print(f"✓ Threat analysis: {data['threat_type']}, severity: {data['severity']}, risk_score: {data['risk_score']}")
    
    def test_ai_query(self, auth_token):
        """Test /api/advanced/ai/query responds to security queries"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/ai/query",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "question": "What is MITRE technique T1003?"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "result_id" in data
        assert "conclusion" in data
        assert "confidence" in data
        assert "model_used" in data
        print(f"✓ AI query response: {data['conclusion'][:100]}...")
    
    def test_ai_ollama_status(self, auth_token):
        """Test /api/advanced/ai/ollama/status returns Ollama connection status"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/ai/ollama/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "url" in data
        # Status should be either "connected" or "disconnected"
        assert data["status"] in ["connected", "disconnected"]
        print(f"✓ Ollama status: {data['status']}, url: {data['url']}")
    
    def test_ai_stats(self, auth_token):
        """Test /api/advanced/ai/stats returns AI reasoning statistics"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/ai/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "model_name" in data
        assert "mitre_techniques_loaded" in data
        assert "threat_patterns_loaded" in data
        print(f"✓ AI stats: {data['mitre_techniques_loaded']} MITRE techniques, {data['threat_patterns_loaded']} patterns")


class TestOllamaConfiguration:
    """Test Ollama configuration endpoint (expects disconnected for external server)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_ollama_configure_endpoint(self, auth_token):
        """Test /api/advanced/ai/ollama/configure accepts configuration"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/ai/ollama/configure",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "base_url": "http://161.35.129.192:11434",
                "model": "mistral"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response should have status - either connected or failed
        assert "status" in data
        print(f"✓ Ollama configure response: {data['status']}")
        if data["status"] == "connected":
            print(f"  - Available models: {data.get('available_models', [])}")
        else:
            print(f"  - Note: {data.get('note', 'Ollama not reachable on external server')}")


class TestDNSRecording:
    """Test VNS DNS recording"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_vns_record_dns_query(self, auth_token):
        """Test /api/advanced/vns/dns can record DNS queries"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/vns/dns",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "src_ip": "192.168.1.100",
                "query_name": "suspicious-domain.duckdns.org",
                "query_type": "A",
                "response_code": "NOERROR",
                "response_ips": ["1.2.3.4"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "query_id" in data
        assert "is_suspicious" in data
        # Should detect duckdns.org as suspicious
        assert data["is_suspicious"] == True, "Expected suspicious DNS to be flagged"
        print(f"✓ DNS query recorded: {data['query_id']}, suspicious: {data['is_suspicious']}")


class TestIncidentCase:
    """Test Vector Memory incident case creation"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        return response.json().get("access_token") if response.status_code == 200 else None
    
    def test_create_incident_case(self, auth_token):
        """Test /api/advanced/memory/case can create incident case"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/memory/case",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "title": "TEST_Ransomware Attack on Finance Department",
                "symptoms": [{"type": "file_encryption", "pattern": "*.locked"}],
                "indicators": ["ransom.exe", "bitcoin_address"],
                "affected_hosts": ["WS-FINANCE-001", "WS-FINANCE-002"],
                "confidence": 0.85
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "case_id" in data
        assert "title" in data
        assert "status" in data
        assert data["status"] == "open"
        print(f"✓ Incident case created: {data['case_id']}, status: {data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
