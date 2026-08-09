#!/usr/bin/env python3
"""Test all UnifiedAgentCore local functions."""
import os
import sys, json, time
sys.path.insert(0, 'ui/desktop')
from main import UnifiedAgentCore

BACKEND_URL = os.getenv('METATRON_BACKEND_URL', 'http://localhost:8001').rstrip('/')
UNIFIED_URL = os.getenv('METATRON_UNIFIED_URL', os.getenv('METATRON_SERVER_URL', BACKEND_URL)).rstrip('/')

agent = UnifiedAgentCore()
agent.registered = True

# Test 1: Port scanning
print('=== PORT SCAN ===')
ports = agent.scan_ports()
print(f'Findings: {len(ports)}')
for p in ports[:5]:
    print(f'  {p}')

# Test 2: File malware scan
print('\n=== FILE SCAN ===')
files = agent.scan_files_for_malware(max_files=200)
if isinstance(files, list):
    print(f'Suspicious files: {len(files)}')
    for f in files[:3]:
        print(f'  {f["path"]}: {f["reason"]}')
else:
    print(f'Result: {files}')

# Test 3: Service scan
print('\n=== SERVICE SCAN ===')
svcs = agent.scan_services()
print(f'Service findings: {len(svcs)}')
for s in svcs[:3]:
    print(s)

# Test 4: Privilege audit
print('\n=== PRIVILEGE AUDIT ===')
privs = agent.audit_privileges()
print(f'Privilege findings: {len(privs)}')
for p in privs[:3]:
    print(f'  {p["name"]} ({p["type"]}): {p["reason"]}')

# Test 5: Rootkit check
print('\n=== ROOTKIT CHECK ===')
rk = agent.check_rootkit_indicators()
print(f'Rootkit indicators: {len(rk)}')
for r in rk[:3]:
    print(f'  {r["type"]}: {r["reason"]}')

# Test 6: Wireless scan
print('\n=== WIRELESS SCAN ===')
wifi = agent.scan_wireless()
if isinstance(wifi, list):
    print(f'WiFi networks: {len(wifi)}')
    for w in wifi[:3]:
        print(f'  {w["ssid"]} | Signal: {w["signal"]} | Auth: {w["auth"]}')
else:
    print(f'Result: {wifi}')

# Test 7: System info
print('\n=== SYSTEM INFO ===')
info = agent._get_system_info()
for k, v in info.items():
    if k not in ('network_interfaces', 'listening_ports', 'logged_users'):
        print(f'  {k}: {v}')
    else:
        print(f'  {k}: {json.dumps(v)[:100]}')

# Test 8: Backend event
print('\n=== BACKEND EVENT TEST ===')
agent._send_backend_event("heartbeat", agent._get_system_info())
print('Backend heartbeat event sent successfully')

# Test 9: Check dashboard sees us
print('\n=== DASHBOARD CHECK ===')
import requests
r = requests.get(f'{UNIFIED_URL}/user/dashboard', timeout=5)
if r.status_code == 200:
    dash = r.json()
    print(f'Agents total: {dash["agents"]["total"]}')
    print(f'Agents online: {dash["agents"]["online"]}')
    for a in dash["agents"]["list"]:
        print(f'  {a["id"]} | {a["hostname"]} | {a["status"]} | {a["ip"]}')
else:
    print(f'Unified dashboard endpoint unavailable on {UNIFIED_URL} (status {r.status_code}), falling back to backend stats')
    fallback = requests.get(f'{BACKEND_URL}/api/dashboard/stats', timeout=5)
    print(f'Backend stats status: {fallback.status_code}')

# Check backend agent list
r2 = requests.get(f'{BACKEND_URL}/api/agents', timeout=5)
print(f'\nBackend agents: {r2.status_code}')
if r2.status_code == 200:
    agents_data = r2.json()
    if isinstance(agents_data, list):
        for a in agents_data[:5]:
            print(f'  {a.get("agent_id", a.get("id", "?"))} | {a.get("hostname", "?")} | {a.get("status", "?")}')
    elif isinstance(agents_data, dict):
        agents_list = agents_data.get("agents", [])
        print(f'  Total: {len(agents_list)}')
        for a in agents_list[:5]:
            print(f'  {a.get("agent_id", a.get("id", "?"))} | {a.get("hostname", "?")} | {a.get("status", "?")}')

print('\n=== ALL TESTS COMPLETE ===')
