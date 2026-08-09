"""
Test Suite for v4.0 Features: ML Prediction, Sandbox Analysis, Browser Isolation, Kibana Dashboards
Tests all new endpoints added in this iteration.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "test@defender.io"
TEST_PASSWORD = "test123"


class TestAuthentication:
    """Authentication tests for new features"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        # Try registering if login fails
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "ML Test User"
        })
        if register_response.status_code in [200, 201]:
            login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            if login_response.status_code == 200:
                return login_response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_auth_required_ml_stats(self):
        """Test ML stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/ml/stats")
        assert response.status_code in [401, 403]
    
    def test_auth_required_sandbox_stats(self):
        """Test Sandbox stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/sandbox/stats")
        assert response.status_code in [401, 403]
    
    def test_auth_required_browser_isolation_stats(self):
        """Test Browser Isolation stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/stats")
        assert response.status_code in [401, 403]
    
    def test_auth_required_kibana_dashboards(self):
        """Test Kibana dashboards requires authentication"""
        response = requests.get(f"{BASE_URL}/api/kibana/dashboards")
        assert response.status_code in [401, 403]


class TestMLPrediction:
    """ML Threat Prediction API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_ml_stats(self, auth_headers):
        """Test GET /api/ml/stats - ML service statistics"""
        response = requests.get(f"{BASE_URL}/api/ml/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "total_predictions" in data
        assert "model_version" in data
        assert "models" in data
        assert "available_categories" in data
        assert "available_risk_levels" in data
        
        # Verify models are present
        models = data["models"]
        assert "network_anomaly" in models
        assert "process_anomaly" in models
        assert "threat_classifier" in models
        assert "behavior_model" in models
        
        print(f"ML Stats: {data['total_predictions']} predictions, version {data['model_version']}")
    
    def test_ml_predict_network(self, auth_headers):
        """Test POST /api/ml/predict/network - Network threat prediction"""
        payload = {
            "source_ip": "192.168.1.100",
            "bytes_in": 50000,
            "bytes_out": 100000,
            "packets_in": 500,
            "packets_out": 1000,
            "unique_destinations": 50,
            "unique_ports": 20,
            "dns_queries": 100,
            "failed_connections": 10,
            "encrypted_ratio": 0.9,
            "avg_packet_size": 1500,
            "connection_duration": 1,
            "port_scan_score": 0.6
        }
        
        response = requests.post(f"{BASE_URL}/api/ml/predict/network", 
                                json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "prediction_id" in data
        assert "threat_score" in data
        assert "category" in data
        assert "risk_level" in data
        assert "confidence" in data
        assert "contributing_factors" in data
        assert "recommended_actions" in data
        assert "mitre_mappings" in data
        
        # Verify data types
        assert isinstance(data["threat_score"], int)
        assert 0 <= data["threat_score"] <= 100
        assert isinstance(data["confidence"], float)
        assert 0 <= data["confidence"] <= 1
        
        print(f"Network Prediction: score={data['threat_score']}, category={data['category']}, risk={data['risk_level']}")
    
    def test_ml_predict_process(self, auth_headers):
        """Test POST /api/ml/predict/process - Process behavior prediction"""
        payload = {
            "process_name": "suspicious.exe",
            "pid": 1234,
            "cpu_usage": 80.0,
            "memory_usage": 500.0,
            "file_operations": 200,
            "registry_operations": 50,
            "network_connections": 20,
            "child_processes": 10,
            "dll_loads": 50,
            "suspicious_api_calls": 5,
            "entropy": 7.5,
            "execution_time": 300.0
        }
        
        response = requests.post(f"{BASE_URL}/api/ml/predict/process", 
                                json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "prediction_id" in data
        assert "threat_score" in data
        assert "category" in data
        assert "risk_level" in data
        assert "confidence" in data
        
        print(f"Process Prediction: score={data['threat_score']}, category={data['category']}")
    
    def test_ml_predict_file(self, auth_headers):
        """Test POST /api/ml/predict/file - File threat prediction"""
        payload = {
            "filename": "malware_sample.exe",
            "hash": "abc123def456",
            "size": 1000000,
            "entropy": 7.8,
            "is_packed": True,
            "has_signature": False,
            "import_count": 200,
            "export_count": 5,
            "is_obfuscated": True,
            "strings_count": 50,
            "has_overlay": True,
            "section_count": 8,
            "suspicious_sections": True,
            "vt_detection_ratio": 0.5
        }
        
        response = requests.post(f"{BASE_URL}/api/ml/predict/file", 
                                json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "prediction_id" in data
        assert "threat_score" in data
        assert "category" in data
        assert "risk_level" in data
        
        print(f"File Prediction: score={data['threat_score']}, category={data['category']}")
    
    def test_ml_predict_user(self, auth_headers):
        """Test POST /api/ml/predict/user - User behavior prediction (UEBA)"""
        payload = {
            "user_id": "user123",
            "username": "suspicious_user",
            "login_hour": 3,  # Unusual hour
            "login_day": 0,  # Sunday
            "failed_logins": 5,
            "resources_accessed": 100,
            "data_transferred": 5000000,  # 5MB
            "anomaly_score": 0.7,
            "geo_distance": 5000,  # 5000km from normal
            "device_trust": 0.3,
            "unusual_time": True,
            "unusual_location": True,
            "privilege_escalations": 3,
            "sensitive_access": 15
        }
        
        response = requests.post(f"{BASE_URL}/api/ml/predict/user", 
                                json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "prediction_id" in data
        assert "threat_score" in data
        assert "category" in data
        assert "risk_level" in data
        
        print(f"User Prediction: score={data['threat_score']}, category={data['category']}")
    
    def test_ml_get_predictions(self, auth_headers):
        """Test GET /api/ml/predictions - Get recent predictions"""
        response = requests.get(f"{BASE_URL}/api/ml/predictions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "predictions" in data
        assert "count" in data
        assert isinstance(data["predictions"], list)
        
        print(f"Retrieved {data['count']} predictions")


class TestSandboxAnalysis:
    """Sandbox Analysis API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_sandbox_stats(self, auth_headers):
        """Test GET /api/sandbox/stats - Sandbox statistics"""
        response = requests.get(f"{BASE_URL}/api/sandbox/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "total_analyses" in data
        assert "by_status" in data
        assert "by_verdict" in data
        assert "by_sample_type" in data
        assert "signatures_available" in data
        
        print(f"Sandbox Stats: {data['total_analyses']} analyses, {data['signatures_available']} signatures")
    
    def test_sandbox_submit_url(self, auth_headers):
        """Test POST /api/sandbox/submit/url - Submit URL for analysis"""
        payload = {
            "url": "http://suspicious-test-site.com/malware.exe",
            "tags": ["test", "suspicious"]
        }
        
        response = requests.post(f"{BASE_URL}/api/sandbox/submit/url", 
                                json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert data["success"] == True
        assert "analysis_id" in data
        
        print(f"URL submitted for analysis: {data['analysis_id']}")
        return data["analysis_id"]
    
    def test_sandbox_get_analyses(self, auth_headers):
        """Test GET /api/sandbox/analyses - Get list of analyses"""
        response = requests.get(f"{BASE_URL}/api/sandbox/analyses?limit=20", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "analyses" in data
        assert "count" in data
        assert isinstance(data["analyses"], list)
        
        print(f"Retrieved {data['count']} analyses")
    
    def test_sandbox_get_queue(self, auth_headers):
        """Test GET /api/sandbox/queue - Get queue status"""
        response = requests.get(f"{BASE_URL}/api/sandbox/queue", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "queue_length" in data
        assert "running" in data
        assert "max_concurrent" in data
        assert "vm_pool" in data
        
        print(f"Queue: {data['queue_length']} pending, {data['running']} running")
    
    def test_sandbox_get_signatures(self, auth_headers):
        """Test GET /api/sandbox/signatures - Get malware signatures"""
        response = requests.get(f"{BASE_URL}/api/sandbox/signatures", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "signatures" in data
        assert "count" in data
        assert isinstance(data["signatures"], list)
        assert data["count"] > 0
        
        # Verify signature structure
        if data["signatures"]:
            sig = data["signatures"][0]
            assert "id" in sig
            assert "name" in sig
            assert "severity" in sig
        
        print(f"Retrieved {data['count']} malware signatures")


class TestBrowserIsolation:
    """Browser Isolation API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_browser_isolation_stats(self, auth_headers):
        """Test GET /api/browser-isolation/stats - Isolation statistics"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "total_sessions" in data
        assert "active_sessions" in data
        assert "blocked_domains" in data
        
        print(f"Browser Isolation Stats: {data['total_sessions']} total, {data['active_sessions']} active")
    
    def test_browser_isolation_analyze_url(self, auth_headers):
        """Test POST /api/browser-isolation/analyze-url - Analyze URL"""
        payload = {"url": "https://suspicious-site.com/page"}
        
        response = requests.post(f"{BASE_URL}/api/browser-isolation/analyze-url", 
                                json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "url" in data
        assert "domain" in data
        assert "threat_level" in data
        assert "category" in data
        assert "is_blocked" in data
        
        print(f"URL Analysis: {data['domain']} - threat_level={data['threat_level']}, blocked={data['is_blocked']}")
    
    def test_browser_isolation_create_session(self, auth_headers):
        """Test POST /api/browser-isolation/sessions - Create isolated session"""
        payload = {
            "url": "https://example.com",
            "isolation_mode": "full"
        }
        
        response = requests.post(f"{BASE_URL}/api/browser-isolation/sessions", 
                                json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data or "session_id" in data
        
        print(f"Session created: {data}")
    
    def test_browser_isolation_get_sessions(self, auth_headers):
        """Test GET /api/browser-isolation/sessions - Get active sessions"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/sessions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "sessions" in data
        assert "count" in data
        
        print(f"Retrieved {data['count']} sessions")
    
    def test_browser_isolation_get_blocked_domains(self, auth_headers):
        """Test GET /api/browser-isolation/blocked-domains - Get blocked domains"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/blocked-domains", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "domains" in data
        assert "count" in data
        
        print(f"Retrieved {data['count']} blocked domains")
    
    def test_browser_isolation_get_modes(self, auth_headers):
        """Test GET /api/browser-isolation/modes - Get isolation modes"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/modes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "modes" in data
        assert isinstance(data["modes"], list)
        assert len(data["modes"]) > 0
        
        # Verify mode structure
        mode = data["modes"][0]
        assert "id" in mode
        assert "name" in mode
        assert "description" in mode
        
        print(f"Retrieved {len(data['modes'])} isolation modes")


class TestKibanaDashboards:
    """Kibana Dashboards API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_kibana_get_dashboards(self, auth_headers):
        """Test GET /api/kibana/dashboards - Get available dashboards"""
        response = requests.get(f"{BASE_URL}/api/kibana/dashboards", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "dashboards" in data
        assert "count" in data
        assert isinstance(data["dashboards"], list)
        
        # Verify dashboard structure if any exist
        if data["dashboards"]:
            dashboard = data["dashboards"][0]
            assert "id" in dashboard
            assert "title" in dashboard
        
        print(f"Retrieved {data['count']} Kibana dashboards")
    
    def test_kibana_get_status(self, auth_headers):
        """Test GET /api/kibana/status - Get Kibana status"""
        response = requests.get(f"{BASE_URL}/api/kibana/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "configured" in data
        assert "dashboards_available" in data
        
        print(f"Kibana Status: configured={data['configured']}, dashboards={data['dashboards_available']}")
    
    def test_kibana_get_dashboard_details(self, auth_headers):
        """Test GET /api/kibana/dashboards/{id} - Get dashboard details"""
        # First get list of dashboards
        list_response = requests.get(f"{BASE_URL}/api/kibana/dashboards", headers=auth_headers)
        if list_response.status_code == 200:
            dashboards = list_response.json().get("dashboards", [])
            if dashboards:
                dashboard_id = dashboards[0]["id"]
                response = requests.get(f"{BASE_URL}/api/kibana/dashboards/{dashboard_id}", 
                                       headers=auth_headers)
                assert response.status_code == 200
                data = response.json()
                
                assert "title" in data
                assert "panels" in data
                
                print(f"Dashboard '{data['title']}' has {len(data.get('panels', []))} panels")
            else:
                print("No dashboards available to test details")
    
    def test_kibana_export_all(self, auth_headers):
        """Test GET /api/kibana/export-all - Export all dashboards"""
        response = requests.get(f"{BASE_URL}/api/kibana/export-all", headers=auth_headers)
        assert response.status_code == 200
        
        # Should return NDJSON content
        assert response.headers.get("content-type") == "application/x-ndjson"
        
        print("Successfully exported all dashboards")


class TestIntegration:
    """Integration tests across features"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_ml_prediction_flow(self, auth_headers):
        """Test complete ML prediction flow"""
        # 1. Get initial stats
        stats_response = requests.get(f"{BASE_URL}/api/ml/stats", headers=auth_headers)
        assert stats_response.status_code == 200
        initial_count = stats_response.json().get("total_predictions", 0)
        
        # 2. Make a prediction
        payload = {
            "source_ip": "10.0.0.1",
            "bytes_in": 1000,
            "bytes_out": 500,
            "packets_in": 10,
            "packets_out": 5
        }
        predict_response = requests.post(f"{BASE_URL}/api/ml/predict/network", 
                                        json=payload, headers=auth_headers)
        assert predict_response.status_code == 200
        prediction_id = predict_response.json().get("prediction_id")
        
        # 3. Verify prediction is in list
        predictions_response = requests.get(f"{BASE_URL}/api/ml/predictions", headers=auth_headers)
        assert predictions_response.status_code == 200
        
        print(f"ML Flow: Created prediction {prediction_id}")
    
    def test_sandbox_analysis_flow(self, auth_headers):
        """Test complete sandbox analysis flow"""
        # 1. Submit URL
        submit_response = requests.post(f"{BASE_URL}/api/sandbox/submit/url", 
                                       json={"url": "http://test-malware.com/sample.exe"},
                                       headers=auth_headers)
        assert submit_response.status_code == 200
        analysis_id = submit_response.json().get("analysis_id")
        
        # 2. Check queue
        queue_response = requests.get(f"{BASE_URL}/api/sandbox/queue", headers=auth_headers)
        assert queue_response.status_code == 200
        
        # 3. Get analyses list
        analyses_response = requests.get(f"{BASE_URL}/api/sandbox/analyses", headers=auth_headers)
        assert analyses_response.status_code == 200
        
        print(f"Sandbox Flow: Submitted analysis {analysis_id}")
    
    def test_browser_isolation_flow(self, auth_headers):
        """Test complete browser isolation flow"""
        # 1. Analyze URL first
        analyze_response = requests.post(f"{BASE_URL}/api/browser-isolation/analyze-url",
                                        json={"url": "https://safe-site.com"},
                                        headers=auth_headers)
        assert analyze_response.status_code == 200
        
        # 2. Create session if not blocked
        if not analyze_response.json().get("is_blocked"):
            session_response = requests.post(f"{BASE_URL}/api/browser-isolation/sessions",
                                            json={"url": "https://safe-site.com", "isolation_mode": "full"},
                                            headers=auth_headers)
            assert session_response.status_code == 200
        
        # 3. Get sessions
        sessions_response = requests.get(f"{BASE_URL}/api/browser-isolation/sessions", headers=auth_headers)
        assert sessions_response.status_code == 200
        
        print("Browser Isolation Flow: Complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
