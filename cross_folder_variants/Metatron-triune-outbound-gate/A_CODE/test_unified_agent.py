#!/usr/bin/env python3
"""Unified Agent Endpoint Test"""
import requests
import time
import json

BASE_URL = "http://localhost:8001/api"

# Auth
email = f"unified_test_{int(time.time())}@test.com"
r = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "password": "Test123!", "name": "Test"})
token = r.json().get("access_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

endpoints = [
    ("GET", "/unified/agents", None),
    ("GET", "/unified/deployments", None),
    ("GET", "/unified/stats", None),
    ("GET", "/unified/dashboard", None),
    ("GET", "/unified/alerts", None),
    ("GET", "/unified/edm/datasets", None),
    ("GET", "/unified/edm/telemetry/summary", None),
    ("GET", "/unified/edm/rollouts", None),
    ("GET", "/unified/agent/download", None),
    ("GET", "/unified/agent/download/windows", None),
    ("GET", "/unified/agent/install-script", None),
    ("GET", "/unified/agent/install-windows", None),
    ("GET", "/unified/agent/install-macos", None),
    ("GET", "/unified/agent/install-android", None),
    ("POST", "/unified/agents/register", {"hostname": "test-host", "os": "windows", "version": "1.0.0", "ip_address": "10.0.0.100"}),
]

print("=" * 60)
print("UNIFIED AGENT ENDPOINT TEST")
print("=" * 60)

passed = 0
failed = 0
results = []

for method, ep, data in endpoints:
    url = f"{BASE_URL}{ep}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        else:
            r = requests.post(url, headers=headers, json=data or {}, timeout=10)
        
        ok = r.status_code in [200, 201, 307]
        status = "✓" if ok else "✗"
        results.append((ep, ok, r.status_code))
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"{status} {method} {ep}: {r.status_code}")
    except Exception as e:
        results.append((ep, False, 0))
        failed += 1
        print(f"✗ {method} {ep}: ERROR - {e}")

print("=" * 60)
print(f"RESULTS: {passed}/{len(results)} passed ({100*passed/len(results):.1f}%)")
if failed > 0:
    print(f"Failed: {failed}")
print("=" * 60)
