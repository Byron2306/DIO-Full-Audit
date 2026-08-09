"""Verify command results stored in MongoDB via the backend API"""
import os
import requests, json

BACKEND = os.getenv("METATRON_BACKEND_URL", "http://localhost:8001").rstrip('/')
resp = requests.post(f"{BACKEND}/api/auth/login", json={
    "email": "admin@seraph.io", "password": "TestAdmin123!"
})
TOKEN = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {TOKEN}"}

print("=== COMMAND HISTORY (agent-commands/history) ===")
r = requests.get(f"{BACKEND}/api/agent-commands/history", headers=headers)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    cmds = data if isinstance(data, list) else data.get("commands", data.get("history", [data]))
    if isinstance(cmds, list):
        for c in cmds[-8:]:
            cid = c.get("command_id", "?")
            ctype = c.get("type", "?")
            cstatus = c.get("status", "?")
            agent = c.get("agent_id", "?")
            print(f"  {cid}: type={ctype} status={cstatus} agent={agent}")
            if c.get("result"):
                r2 = c["result"]
                success = r2.get("success")
                output = str(r2.get("output", ""))[:150]
                print(f"    success={success}, output={output}")
    else:
        print(f"  Raw: {str(cmds)[:500]}")
else:
    print(f"  Body: {r.text[:300]}")

# Also check via swarm overview
print("\n=== SWARM OVERVIEW ===")
r2 = requests.get(f"{BACKEND}/api/swarm/overview", headers=headers)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    overview = r2.json()
    print(json.dumps(overview, indent=2, default=str)[:800])
