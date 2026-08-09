"""
Backend Tests for P1 and P2 Features
=====================================
Tests for:
- VNS Alerting Pipeline (Slack/Email)
- SOAR Templates (14 templates)
- Quantum Security Status
- Multi-Tenant Service
- New navigation routes
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL environment variable must be set"

# Test credentials
TEST_EMAIL = "test@defender.io"
TEST_PASSWORD = "test123"


def get_auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code == 200:
        return response.json().get("access_token") or response.json().get("token")
    
    # If login fails, try registration
    response = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": "Test User"
    })
    
    if response.status_code in [200, 201]:
        return response.json().get("access_token") or response.json().get("token")
    
    # Try login again after registration
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code == 200:
        return response.json().get("access_token") or response.json().get("token")
    
    return None


# ============================================================================
# VNS ALERTS TESTS
# ============================================================================

def test_vns_alerts_status_endpoint():
    """Test VNS alerts status endpoint returns correct structure"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/advanced/alerts/status",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    
    # Validate response structure
    assert "enabled" in data, "Missing 'enabled' field"
    assert "slack_configured" in data, "Missing 'slack_configured' field"
    assert "email_configured" in data, "Missing 'email_configured' field"
    assert "stats" in data, "Missing 'stats' field"
    
    # Validate stats structure
    stats = data["stats"]
    assert "slack_alerts_sent" in stats, "Missing 'slack_alerts_sent' in stats"
    assert "email_alerts_sent" in stats, "Missing 'email_alerts_sent' in stats"
    assert "alerts_suppressed" in stats, "Missing 'alerts_suppressed' in stats"
    
    print(f"VNS Alerts Status: enabled={data['enabled']}, slack={data['slack_configured']}, email={data['email_configured']}")


def test_vns_alerts_configure_endpoint():
    """Test VNS alerts configuration endpoint"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.post(
        f"{BASE_URL}/api/advanced/alerts/configure",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "slack_webhook_url": "",  # Empty for test
            "email_config": {
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_user": "",
                "smtp_password": "",
                "from_address": "",
                "to_addresses": []
            }
        }
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "status" in data, "Missing 'status' field"
    print(f"VNS Alerts Configure Response: {data}")


# ============================================================================
# SOAR TEMPLATES TESTS - Should have 14 templates
# ============================================================================

def test_soar_templates_count():
    """Test SOAR templates endpoint returns 14 templates"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/soar/templates",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "templates" in data, "Missing 'templates' field"
    assert "count" in data, "Missing 'count' field"
    
    templates = data["templates"]
    count = data["count"]
    
    # Should have 14 templates (6 original + 8 new P2 templates)
    assert count == 14, f"Expected 14 templates, got {count}"
    assert len(templates) == 14, f"Expected 14 templates in array, got {len(templates)}"
    
    # Verify new templates are present
    template_ids = [t["id"] for t in templates]
    new_template_ids = [
        "tpl_phishing_response",
        "tpl_apt_detection",
        "tpl_lateral_movement",
        "tpl_privilege_escalation",
        "tpl_zero_day_exploit",
        "tpl_supply_chain_attack",
        "tpl_dns_tunneling",
        "tpl_cloud_breach"
    ]
    
    for tpl_id in new_template_ids:
        assert tpl_id in template_ids, f"Missing new template: {tpl_id}"
    
    print(f"SOAR Templates count: {count}")
    print(f"Template IDs: {template_ids}")


def test_soar_stats():
    """Test SOAR stats endpoint"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/soar/stats",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "total_templates" in data, "Missing 'total_templates' field"
    assert data["total_templates"] == 14, f"Expected 14 total_templates, got {data['total_templates']}"
    
    print(f"SOAR Stats: {data}")


def test_soar_template_categories():
    """Test SOAR template categories endpoint"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/soar/templates/categories",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "categories" in data, "Missing 'categories' field"
    
    categories = [c["name"] for c in data["categories"]]
    
    # Check for expected categories from new templates
    expected_categories = ["email_security", "advanced_threats", "network", "identity", "vulnerability", "cloud_security"]
    for cat in expected_categories:
        assert cat in categories, f"Missing category: {cat}"
    
    print(f"SOAR Categories: {categories}")


# ============================================================================
# QUANTUM SECURITY TESTS
# ============================================================================

def test_quantum_status_endpoint():
    """Test quantum security status endpoint"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/advanced/quantum/status",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    
    # Validate response structure
    assert "mode" in data, "Missing 'mode' field"
    assert "algorithms" in data, "Missing 'algorithms' field"
    
    # Should have Kyber and Dilithium algorithms
    assert "kem" in data["algorithms"], "Missing 'kem' algorithms"
    assert "signatures" in data["algorithms"], "Missing 'signatures' algorithms"
    
    print(f"Quantum Security Status: mode={data['mode']}")


# ============================================================================
# MULTI-TENANT SERVICE TESTS
# ============================================================================

def test_multi_tenant_service_import():
    """Test that multi-tenant service can be imported and instantiated"""
    import sys
    sys.path.insert(0, '/app/backend')
    
    from services.multi_tenant import multi_tenant_service, TenantTier, TenantStatus
    
    # Verify singleton pattern
    assert multi_tenant_service is not None, "multi_tenant_service should not be None"
    
    # Test create tenant
    tenant = multi_tenant_service.create_tenant(
        name="Test Tenant P2",
        contact_email="test_p2@example.com",
        tier=TenantTier.STARTER
    )
    
    assert tenant is not None, "Created tenant should not be None"
    assert tenant.name == "Test Tenant P2", f"Expected 'Test Tenant P2', got '{tenant.name}'"
    assert tenant.tier == TenantTier.STARTER, f"Expected STARTER tier, got {tenant.tier}"
    
    # Test get tenant
    fetched_tenant = multi_tenant_service.get_tenant(tenant.id)
    assert fetched_tenant is not None, "Fetched tenant should not be None"
    assert fetched_tenant.id == tenant.id, "Tenant IDs should match"
    
    # Test list tenants
    tenants = multi_tenant_service.list_tenants()
    assert len(tenants) >= 1, "Should have at least one tenant"
    
    # Test tenant stats
    stats = multi_tenant_service.get_tenant_stats()
    assert "total_tenants" in stats, "Missing 'total_tenants' in stats"
    assert stats["total_tenants"] >= 1, "Should have at least 1 tenant"
    
    print(f"Multi-Tenant Service: Created tenant {tenant.id}")
    print(f"Multi-Tenant Stats: {stats}")


def test_multi_tenant_quota_management():
    """Test tenant quota and feature management"""
    import sys
    sys.path.insert(0, '/app/backend')
    
    from services.multi_tenant import multi_tenant_service, TenantTier, TIER_QUOTAS
    
    # Verify tier quotas exist
    assert TenantTier.FREE in TIER_QUOTAS, "FREE tier should have quota"
    assert TenantTier.STARTER in TIER_QUOTAS, "STARTER tier should have quota"
    assert TenantTier.PROFESSIONAL in TIER_QUOTAS, "PROFESSIONAL tier should have quota"
    assert TenantTier.ENTERPRISE in TIER_QUOTAS, "ENTERPRISE tier should have quota"
    
    # Verify enterprise tier has unlimited features
    enterprise_quota = TIER_QUOTAS[TenantTier.ENTERPRISE]
    assert enterprise_quota.max_agents == -1, "Enterprise should have unlimited agents"
    assert "all" in enterprise_quota.features, "Enterprise should have 'all' features"
    
    # Verify default tenant exists
    default_tenant = multi_tenant_service.get_tenant("tenant_default")
    assert default_tenant is not None, "Default tenant should exist"
    assert default_tenant.tier == TenantTier.ENTERPRISE, "Default tenant should be Enterprise tier"
    
    print("Multi-Tenant Quota Management: OK")


# ============================================================================
# HEALTH AND ADVANCED DASHBOARD TESTS
# ============================================================================

def test_health_endpoint():
    """Test health check endpoint"""
    response = requests.get(f"{BASE_URL}/api/health")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert data.get("status") == "healthy", "Health status should be 'healthy'"
    
    print(f"Health Check: {data}")


def test_api_root():
    """Test API root endpoint"""
    response = requests.get(f"{BASE_URL}/api/")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert "status" in data, "Missing 'status' field"
    assert data["status"] == "operational", "Status should be 'operational'"
    
    print(f"API Root: {data.get('name')} v{data.get('version')}")


def test_advanced_dashboard_endpoint():
    """Test advanced security dashboard endpoint"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/advanced/dashboard",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    
    # Validate dashboard contains all advanced service data
    assert "mcp" in data, "Missing 'mcp' field in dashboard"
    assert "memory" in data, "Missing 'memory' field in dashboard"
    assert "vns" in data, "Missing 'vns' field in dashboard"
    assert "quantum" in data, "Missing 'quantum' field in dashboard"
    assert "ai" in data, "Missing 'ai' field in dashboard"
    
    print(f"Advanced Dashboard sections: {list(data.keys())}")


# ============================================================================
# CUCKOO SANDBOX TESTS
# ============================================================================

def test_sandbox_status_endpoint():
    """Test Cuckoo sandbox status endpoint"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/advanced/sandbox/status",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    
    # Validate response structure - should have some status fields
    assert "enabled" in data or "mode" in data or "status" in data, \
        "Should have some status indicator"
    
    print(f"Cuckoo Sandbox Status: {data}")


# ============================================================================
# VNS STATS TESTS
# ============================================================================

def test_vns_stats_endpoint():
    """Test VNS stats endpoint"""
    token = get_auth_token()
    assert token is not None, "Failed to get auth token"
    
    response = requests.get(
        f"{BASE_URL}/api/advanced/vns/stats",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    print(f"VNS Stats: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
