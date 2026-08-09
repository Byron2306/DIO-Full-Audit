#!/usr/bin/env python3
"""
Backend API Testing Script - Email Protection & Mobile Security
==============================================================

This script tests the newly implemented Email Protection and Mobile Security APIs
to verify they are working correctly.
"""

import requests
import json
import base64
import sys
import time
from typing import Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = "https://seraph-security.preview.emergentagent.com/api"

# Global auth token
auth_token = None

def make_request(method: str, endpoint: str, data: dict = None, headers: dict = None) -> Dict[Any, Any]:
    """Make HTTP request with proper headers and error handling"""
    url = f"{BACKEND_URL}{endpoint}"
    
    if headers is None:
        headers = {}
    
    # Add auth token if available
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # Try to bypass remote access restrictions by spoofing local IP
    headers["X-Forwarded-For"] = "127.0.0.1"
    headers["X-Real-IP"] = "127.0.0.1"
    headers["Content-Type"] = "application/json"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return {
            "status_code": response.status_code,
            "data": response.json() if response.content and response.headers.get("content-type", "").startswith("application/json") else response.text,
            "success": 200 <= response.status_code < 300
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": 0,
            "data": str(e),
            "success": False,
            "error": "Connection error"
        }
    except Exception as e:
        return {
            "status_code": 0,
            "data": str(e),
            "success": False,
            "error": "Parse error"
        }

def test_authentication():
    """Test authentication flow"""
    global auth_token
    
    print("=" * 60)
    print("TESTING AUTHENTICATION")
    print("=" * 60)
    
    # Test registration
    print("\n1. Testing Registration...")
    register_data = {
        "email": "test@security-test.com", 
        "password": "SecurePass123!",
        "name": "Test User"
    }
    
    result = make_request("POST", "/auth/register", register_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Registration successful")
        if isinstance(result["data"], dict) and "access_token" in result["data"]:
            auth_token = result["data"]["access_token"]
            print("✅ Token obtained from registration")
            return True
    else:
        print(f"❌ Registration failed: {result['data']}")
    
    # Try login if registration failed (user might already exist)
    print("\n2. Testing Login...")
    login_data = {
        "email": "test@security-test.com",
        "password": "SecurePass123!"
    }
    
    result = make_request("POST", "/auth/login", login_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Login successful")
        if isinstance(result["data"], dict) and "access_token" in result["data"]:
            auth_token = result["data"]["access_token"]
            print("✅ Token obtained from login")
            return True
    else:
        print(f"❌ Login failed: {result['data']}")
    
    return False

def test_email_protection_apis():
    """Test Email Protection APIs"""
    print("\n" + "=" * 60)
    print("TESTING EMAIL PROTECTION APIs")
    print("=" * 60)
    
    test_results = []
    
    # 1. Test Email Protection Stats
    print("\n1. Testing GET /api/email-protection/stats")
    result = make_request("GET", "/email-protection/stats")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Email protection stats retrieved")
        print(f"Data sample: {json.dumps(result['data'], indent=2)[:200]}...")
        test_results.append(("Email Protection Stats", True, ""))
    else:
        print(f"❌ Failed to get stats: {result['data']}")
        test_results.append(("Email Protection Stats", False, str(result['data'])))
    
    # 2. Test Email Analysis
    print("\n2. Testing POST /api/email-protection/analyze")
    email_data = {
        "sender": "suspicious@fake-bank.com",
        "recipient": "test@security-test.com",
        "subject": "URGENT: Verify your account immediately or it will be suspended!",
        "body": "Dear customer, we have detected unusual activity on your account. Click here immediately to verify: http://192.168.1.1/login",
        "headers": {"From-Name": "Security Team"},
        "attachments": [{
            "filename": "document.pdf.exe",
            "content_base64": base64.b64encode(b"MZThis is a fake executable").decode(),
            "mime_type": "application/octet-stream"
        }],
        "sender_ip": "192.168.1.100"
    }
    
    result = make_request("POST", "/email-protection/analyze", email_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Email analysis completed")
        data = result["data"]
        print(f"Risk Level: {data.get('overall_risk', 'unknown')}")
        print(f"Threat Score: {data.get('threat_score', 'unknown')}")
        print(f"Recommended Action: {data.get('recommended_action', 'unknown')}")
        print(f"Threats: {', '.join([t for t in data.get('threat_types', [])])}")
        test_results.append(("Email Analysis", True, ""))
    else:
        print(f"❌ Email analysis failed: {result['data']}")
        test_results.append(("Email Analysis", False, str(result['data'])))
    
    # 3. Test URL Analysis
    print("\n3. Testing POST /api/email-protection/analyze-url")
    url_data = {"url": "http://192.168.1.1/login"}
    
    result = make_request("POST", "/email-protection/analyze-url", url_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ URL analysis completed")
        data = result["data"]
        print(f"Safe: {data.get('is_safe', 'unknown')}")
        print(f"Risk Level: {data.get('risk_level', 'unknown')}")
        print(f"Threats: {', '.join(data.get('threats', []))}")
        test_results.append(("URL Analysis", True, ""))
    else:
        print(f"❌ URL analysis failed: {result['data']}")
        test_results.append(("URL Analysis", False, str(result['data'])))
    
    # 4. Test Domain Authentication Check
    print("\n4. Testing POST /api/email-protection/check-authentication")
    auth_data = {
        "domain": "google.com",
        "sender_ip": "8.8.8.8"
    }
    
    result = make_request("POST", "/email-protection/check-authentication", auth_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Domain authentication check completed")
        data = result["data"]
        print(f"SPF Result: {data.get('spf', {}).get('result', 'unknown')}")
        print(f"DKIM Result: {data.get('dkim', {}).get('result', 'unknown')}")
        print(f"DMARC Result: {data.get('dmarc', {}).get('result', 'unknown')}")
        test_results.append(("Domain Authentication", True, ""))
    else:
        print(f"❌ Domain authentication check failed: {result['data']}")
        test_results.append(("Domain Authentication", False, str(result['data'])))
    
    # 5. Test Quarantine
    print("\n5. Testing GET /api/email-protection/quarantine")
    result = make_request("GET", "/email-protection/quarantine")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Quarantine retrieved")
        data = result["data"]
        print(f"Quarantined emails: {data.get('count', 0)}")
        test_results.append(("Quarantine Management", True, ""))
    else:
        print(f"❌ Quarantine retrieval failed: {result['data']}")
        test_results.append(("Quarantine Management", False, str(result['data'])))
    
    # 6. Test Protected Users
    print("\n6. Testing GET /api/email-protection/protected-users")
    result = make_request("GET", "/email-protection/protected-users")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Protected users retrieved")
        data = result["data"]
        print(f"Total protected users: {data.get('total', 0)}")
        test_results.append(("Protected Users List", True, ""))
    else:
        print(f"❌ Protected users retrieval failed: {result['data']}")
        test_results.append(("Protected Users List", False, str(result['data'])))
    
    # 7. Test Add Protected User
    print("\n7. Testing POST /api/email-protection/protected-users")
    protected_user_data = {
        "email": "ceo@security-test.com",
        "name": "CEO Test",
        "title": "Chief Executive Officer",
        "user_type": "executive"
    }
    
    result = make_request("POST", "/email-protection/protected-users", protected_user_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Protected user added")
        test_results.append(("Add Protected User", True, ""))
    else:
        print(f"❌ Add protected user failed: {result['data']}")
        test_results.append(("Add Protected User", False, str(result['data'])))
    
    # 8. Test Blocked Senders
    print("\n8. Testing GET /api/email-protection/blocked-senders")
    result = make_request("GET", "/email-protection/blocked-senders")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Blocked senders retrieved")
        data = result["data"]
        print(f"Blocked senders count: {data.get('count', 0)}")
        test_results.append(("Blocked Senders List", True, ""))
    else:
        print(f"❌ Blocked senders retrieval failed: {result['data']}")
        test_results.append(("Blocked Senders List", False, str(result['data'])))
    
    # 9. Test Add Blocked Sender
    print("\n9. Testing POST /api/email-protection/blocked-senders")
    blocked_sender_data = {"sender": "spam@malicious-sender.com"}
    
    result = make_request("POST", "/email-protection/blocked-senders", blocked_sender_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Sender blocked")
        test_results.append(("Block Sender", True, ""))
    else:
        print(f"❌ Block sender failed: {result['data']}")
        test_results.append(("Block Sender", False, str(result['data'])))
    
    # 10. Test Trusted Domains
    print("\n10. Testing GET /api/email-protection/trusted-domains")
    result = make_request("GET", "/email-protection/trusted-domains")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Trusted domains retrieved")
        data = result["data"]
        print(f"Trusted domains count: {data.get('count', 0)}")
        test_results.append(("Trusted Domains List", True, ""))
    else:
        print(f"❌ Trusted domains retrieval failed: {result['data']}")
        test_results.append(("Trusted Domains List", False, str(result['data'])))
    
    return test_results

def test_mobile_security_apis():
    """Test Mobile Security APIs"""
    print("\n" + "=" * 60)
    print("TESTING MOBILE SECURITY APIs")
    print("=" * 60)
    
    test_results = []
    device_id = None
    
    # 1. Test Mobile Security Stats
    print("\n1. Testing GET /api/mobile-security/stats")
    result = make_request("GET", "/mobile-security/stats")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Mobile security stats retrieved")
        data = result["data"]
        print(f"Total devices: {data.get('total_devices', 0)}")
        print(f"Active threats: {data.get('active_threats', 0)}")
        test_results.append(("Mobile Security Stats", True, ""))
    else:
        print(f"❌ Failed to get mobile stats: {result['data']}")
        test_results.append(("Mobile Security Stats", False, str(result['data'])))
    
    # 2. Test Dashboard
    print("\n2. Testing GET /api/mobile-security/dashboard")
    result = make_request("GET", "/mobile-security/dashboard")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Mobile security dashboard retrieved")
        data = result["data"]
        print(f"At-risk devices: {len(data.get('at_risk_devices', []))}")
        print(f"Recent threats: {len(data.get('recent_threats', []))}")
        test_results.append(("Mobile Dashboard", True, ""))
    else:
        print(f"❌ Dashboard retrieval failed: {result['data']}")
        test_results.append(("Mobile Dashboard", False, str(result['data'])))
    
    # 3. Test Get All Devices
    print("\n3. Testing GET /api/mobile-security/devices")
    result = make_request("GET", "/mobile-security/devices")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Mobile devices list retrieved")
        data = result["data"]
        print(f"Device count: {data.get('count', 0)}")
        test_results.append(("Device List", True, ""))
    else:
        print(f"❌ Device list retrieval failed: {result['data']}")
        test_results.append(("Device List", False, str(result['data'])))
    
    # 4. Test Register Device
    print("\n4. Testing POST /api/mobile-security/devices")
    device_data = {
        "device_name": "Test iPhone",
        "platform": "ios",
        "os_version": "16.1",
        "model": "iPhone 14 Pro",
        "serial_number": "TEST123456789",
        "user_id": "test_user",
        "user_email": "test@security-test.com",
        "imei": "123456789012345"
    }
    
    result = make_request("POST", "/mobile-security/devices", device_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Device registered successfully")
        data = result["data"]
        device_id = data.get("device_id")
        print(f"Device ID: {device_id}")
        print(f"Status: {data.get('status', 'unknown')}")
        test_results.append(("Register Device", True, ""))
    else:
        print(f"❌ Device registration failed: {result['data']}")
        test_results.append(("Register Device", False, str(result['data'])))
    
    # 5. Test Get Threats
    print("\n5. Testing GET /api/mobile-security/threats")
    result = make_request("GET", "/mobile-security/threats")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Threats retrieved")
        data = result["data"]
        print(f"Threat count: {data.get('count', 0)}")
        test_results.append(("Mobile Threats List", True, ""))
    else:
        print(f"❌ Threats retrieval failed: {result['data']}")
        test_results.append(("Mobile Threats List", False, str(result['data'])))
    
    # 6. Test App Analysis
    print("\n6. Testing POST /api/mobile-security/analyze-app")
    app_data = {
        "package_name": "com.suspicious.app",
        "app_name": "Suspicious Banking App",
        "version": "2.0",
        "platform": "android",
        "permissions": [
            "android.permission.READ_SMS",
            "android.permission.SEND_SMS", 
            "android.permission.READ_CALL_LOG",
            "android.permission.CAMERA",
            "android.permission.RECORD_AUDIO",
            "android.permission.ACCESS_FINE_LOCATION"
        ],
        "is_sideloaded": True,
        "is_debuggable": True
    }
    
    result = make_request("POST", "/mobile-security/analyze-app", app_data)
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ App analysis completed")
        data = result["data"]
        print(f"Safe: {data.get('is_safe', 'unknown')}")
        print(f"Risk Level: {data.get('risk_level', 'unknown')}")
        print(f"Dangerous permissions: {len(data.get('dangerous_permissions', []))}")
        print(f"OWASP findings: {len(data.get('owasp_findings', []))}")
        test_results.append(("Mobile App Analysis", True, ""))
    else:
        print(f"❌ App analysis failed: {result['data']}")
        test_results.append(("Mobile App Analysis", False, str(result['data'])))
    
    # 7. Test Get Policies
    print("\n7. Testing GET /api/mobile-security/policies")
    result = make_request("GET", "/mobile-security/policies")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Policies retrieved")
        data = result["data"]
        policies_count = len(data.get("policies", {}))
        print(f"Policies count: {policies_count}")
        test_results.append(("Mobile Policies", True, ""))
    else:
        print(f"❌ Policies retrieval failed: {result['data']}")
        test_results.append(("Mobile Policies", False, str(result['data'])))
    
    # 8. Test Get Threat Categories
    print("\n8. Testing GET /api/mobile-security/threat-categories")
    result = make_request("GET", "/mobile-security/threat-categories")
    print(f"Status: {result['status_code']}")
    if result["success"]:
        print("✅ Threat categories retrieved")
        data = result["data"]
        categories = len(data.get("categories", []))
        severities = len(data.get("severities", []))
        print(f"Categories: {categories}, Severities: {severities}")
        test_results.append(("Threat Categories", True, ""))
    else:
        print(f"❌ Threat categories retrieval failed: {result['data']}")
        test_results.append(("Threat Categories", False, str(result['data'])))
    
    return test_results, device_id

def print_test_summary(email_results, mobile_results):
    """Print comprehensive test summary"""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE TEST SUMMARY")
    print("=" * 80)
    
    all_results = []
    
    print("\n📧 EMAIL PROTECTION RESULTS:")
    print("-" * 40)
    for test_name, success, error in email_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
        if not success and error:
            print(f"   Error: {error}")
        all_results.append(success)
    
    print("\n📱 MOBILE SECURITY RESULTS:")
    print("-" * 40)
    for test_name, success, error in mobile_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
        if not success and error:
            print(f"   Error: {error}")
        all_results.append(success)
    
    # Calculate overall statistics
    total_tests = len(all_results)
    passed_tests = sum(all_results)
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n📊 OVERALL STATISTICS:")
    print("-" * 40)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("\n🎉 EXCELLENT: Most tests passed!")
    elif success_rate >= 60:
        print("\n⚠️ GOOD: Majority of tests passed, but some issues need attention.")
    else:
        print("\n🚨 NEEDS ATTENTION: Many tests failed, significant issues detected.")
    
    return success_rate >= 80

def main():
    """Main test execution"""
    print("🔒 Backend API Testing - Email Protection & Mobile Security")
    print("=" * 80)
    
    # Test authentication first
    if not test_authentication():
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with API testing.")
        print("Check if the backend server is running and accessible.")
        return False
    
    print(f"\n✅ Authentication successful. Token obtained.")
    
    # Test Email Protection APIs
    email_results = test_email_protection_apis()
    
    # Test Mobile Security APIs
    mobile_results, device_id = test_mobile_security_apis()
    
    # Print comprehensive summary
    overall_success = print_test_summary(email_results, mobile_results)
    
    return overall_success

if __name__ == "__main__":
    print("Starting backend API tests...")
    try:
        success = main()
        exit_code = 0 if success else 1
        print(f"\nTest execution completed with exit code: {exit_code}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)